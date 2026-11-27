/* =====================================================================================
   score_telefonico_fase17_sac.sql · 25/11/2026
   Capital del día para las vigentes de Compartamos (126 IND, 128 CCM, 133 grupal) desde el SAC
   (Desarrollo.dbo.SAC_CAR_BIZNESCOB), sin tocar la asignación ni Analytics, y con traza.

   Reglas (Hardy, 25/11):
   - Capital del cliente = suma de [SdoCapital] de sus operaciones de ESA cartera en el SAC del día.
     La operación se cruza con la asignación de la cartera quitando los ceros a la izquierda
     ("00000000000019362539" = "19362539").
   - El SAC se reemplaza cada día (una sola carga, ~09:45). Aquí se guarda una foto por día (score.SacClienteDia),
     así queda la traza de cómo cambió el saldo de cada cliente.
   - Si en la mañana el SAC de hoy aún no llegó, vale la foto del día hábil anterior. Si la última foto es más
     vieja (p. ej. el SAC no se cargó en días), "En el SAC" vale SAC DESACTUALIZADO y una base que pida
     "En el SAC = SI" sale vacía: nunca se llama con un SAC viejo a un cliente que ya canceló.
   - Un cliente de la cartera que NO está en el SAC del día pagó / canceló / salió (por fuera o por reclamo).

   Objetos:
   - score.SacCartera: carteras que se cruzan con el SAC y su tabla de asignación.
   - score.SacCarga + score.SacCargaCartera: cada foto (fecha de carga del SAC) y el cruce por cartera.
   - score.SacClienteDia: la foto por día, cartera y cliente. Se guardan 120 días.
   - score.sp_CargarSac: toma la foto si el SAC tiene una carga nueva (si ya la tomó, no hace nada).
     La llama el generador solo, como máximo una vez por minuto; también se puede correr a mano.
   - score.vw_BaseTrabajo: + CapitalSac, RangoCapitalSac, EnSac (sobre la vista instalada, como la fase 16).
   - Catálogo: CAPITAL_SAC, RANGO_CAPITAL_SAC y EN_SAC para las carteras de score.SacCartera.
   ===================================================================================== */
USE CobAuto;
GO

/* =====================================================================================
   BLOQUE 1 · Tablas
   ===================================================================================== */
IF OBJECT_ID('score.SacCartera') IS NULL
    CREATE TABLE score.SacCartera (
        IdCartera        INT           NOT NULL CONSTRAINT PK_score_SacCartera PRIMARY KEY,
        TablaAsignacion  NVARCHAR(256) NOT NULL,   -- tabla de Desarrollo con las operaciones de la cartera
        Activo           BIT           NOT NULL CONSTRAINT DF_score_SacCartera_Activo DEFAULT (1)
    );
GO
MERGE score.SacCartera AS t
USING (VALUES (126, N'compartamos_individual'), (128, N'compartamos_ccm'), (133, N'compartamos_grupal'))
      AS s (IdCartera, TablaAsignacion)
ON t.IdCartera = s.IdCartera
WHEN MATCHED THEN UPDATE SET TablaAsignacion = s.TablaAsignacion
WHEN NOT MATCHED THEN INSERT (IdCartera, TablaAsignacion) VALUES (s.IdCartera, s.TablaAsignacion);
GO

IF OBJECT_ID('score.SacCarga') IS NULL
    CREATE TABLE score.SacCarga (
        FechaSac      DATE          NOT NULL CONSTRAINT PK_score_SacCarga PRIMARY KEY,
        FechaCarga    DATETIME      NOT NULL,      -- FechaCarga del SAC que se fotografió
        FilasSac      INT           NOT NULL,
        Armado        DATETIME2(0)  NOT NULL CONSTRAINT DF_score_SacCarga_Armado DEFAULT (SYSDATETIME())
    );
IF OBJECT_ID('score.SacCargaCartera') IS NULL
    CREATE TABLE score.SacCargaCartera (
        FechaSac            DATE         NOT NULL,
        IdCartera           INT          NOT NULL,
        Metodo              VARCHAR(10)  NOT NULL,  -- OPERACION · DNI (si la asignación no se pudo leer o no cruzó)
        OperacionesCartera  INT          NOT NULL,  -- operaciones en la asignación
        OperacionesEnSac    INT          NOT NULL,  -- de esas, cuántas están en el SAC del día
        ClientesCartera     INT          NOT NULL,  -- clientes de score.BaseTrabajoCliente
        ClientesEnSac       INT          NOT NULL,
        Aviso               NVARCHAR(400) NULL,
        CONSTRAINT PK_score_SacCargaCartera PRIMARY KEY (FechaSac, IdCartera)
    );
IF OBJECT_ID('score.SacClienteDia') IS NULL
    CREATE TABLE score.SacClienteDia (
        FechaSac           DATE           NOT NULL,
        IdCartera          INT            NOT NULL,
        DNI                VARCHAR(20)    NOT NULL,   -- como está en score.BaseTrabajoCliente
        Operaciones        SMALLINT       NOT NULL,
        SdoCapital         DECIMAL(18, 2) NULL,       -- suma de [SdoCapital]
        SdoCapitalVencido  DECIMAL(18, 2) NULL,
        DeudaTotal         DECIMAL(18, 2) NULL,
        DiasAtrasoMax      INT            NULL,
        CONSTRAINT PK_score_SacClienteDia PRIMARY KEY CLUSTERED (FechaSac, IdCartera, DNI)
    );
GO

/* =====================================================================================
   BLOQUE 2 · Procedimiento: foto del SAC del día
   ===================================================================================== */
CREATE OR ALTER PROCEDURE score.sp_CargarSac
    @Simular BIT = 0,     -- 1 = no escribe: muestra el cruce por cartera
    @Forzar  BIT = 0      -- 1 = vuelve a tomar la foto aunque esa carga ya esté
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;
    DECLARE @FechaCarga DATETIME = (SELECT MAX(FechaCarga) FROM Desarrollo.dbo.SAC_CAR_BIZNESCOB WITH (NOLOCK));
    IF @FechaCarga IS NULL BEGIN PRINT 'El SAC está vacío.'; RETURN 0; END;
    DECLARE @FechaSac DATE = CAST(@FechaCarga AS DATE);
    IF @Forzar = 0 AND @Simular = 0 AND EXISTS (SELECT 1 FROM score.SacCarga WHERE FechaSac = @FechaSac AND FechaCarga = @FechaCarga)
        RETURN 0;   -- esa carga ya está fotografiada

    -- Candado: dos usuarios del generador a la vez no toman la misma foto dos veces
    DECLARE @lock INT;
    IF @Simular = 0
    BEGIN
        EXEC @lock = sys.sp_getapplock @Resource = 'score.sp_CargarSac', @LockMode = 'Exclusive', @LockOwner = 'Session', @LockTimeout = 30000;
        IF @lock < 0 BEGIN PRINT 'Otra sesión está cargando el SAC.'; RETURN 0; END;
        IF @Forzar = 0 AND EXISTS (SELECT 1 FROM score.SacCarga WHERE FechaSac = @FechaSac AND FechaCarga = @FechaCarga)
        BEGIN
            EXEC sys.sp_releaseapplock @Resource = 'score.sp_CargarSac', @LockOwner = 'Session';
            RETURN 0;
        END;
    END;

    BEGIN TRY
        -- SAC del día: operación y DNI sin ceros a la izquierda
        CREATE TABLE #sac (Op NVARCHAR(60) COLLATE DATABASE_DEFAULT NOT NULL, DniN NVARCHAR(30) COLLATE DATABASE_DEFAULT NOT NULL,
                           SdoCapital FLOAT NULL, SdoCapitalVencido FLOAT NULL, DeudaTotal FLOAT NULL, DiasAtraso FLOAT NULL);
        INSERT INTO #sac (Op, DniN, SdoCapital, SdoCapitalVencido, DeudaTotal, DiasAtraso)
        SELECT CASE WHEN o.x LIKE N'%[^0]%' THEN SUBSTRING(o.x, PATINDEX(N'%[^0]%', o.x), 60) ELSE N'0' END,
               CASE WHEN d.x LIKE N'%[^0]%' THEN SUBSTRING(d.x, PATINDEX(N'%[^0]%', d.x), 30) ELSE N'0' END,
               s.SdoCapital, s.SdoCapitalVencido, s.Deuda_Total, s.DiasAtraso
        FROM Desarrollo.dbo.SAC_CAR_BIZNESCOB AS s WITH (NOLOCK)
        CROSS APPLY (SELECT LTRIM(RTRIM(CONVERT(NVARCHAR(60), s.[Cod Operación]))) AS x) AS o
        CROSS APPLY (SELECT LTRIM(RTRIM(CONVERT(NVARCHAR(30), s.DNI))) AS x) AS d
        -- Todo el día de la carga: FechaCarga cambia fila a fila mientras se carga (09:47:34 … 09:48:28)
        WHERE s.FechaCarga >= CONVERT(DATETIME, @FechaSac) AND s.FechaCarga < DATEADD(DAY, 1, CONVERT(DATETIME, @FechaSac))
          AND s.DNI IS NOT NULL;
        DECLARE @FilasSac INT = @@ROWCOUNT;
        CREATE INDEX IX_op ON #sac (Op);
        CREATE INDEX IX_dni ON #sac (DniN);

        -- Clientes del generador de las carteras del SAC (DNI sin ceros para el cruce)
        CREATE TABLE #cli (IdCartera INT NOT NULL, DNI VARCHAR(20) COLLATE DATABASE_DEFAULT NOT NULL,
                           DniN NVARCHAR(30) COLLATE DATABASE_DEFAULT NOT NULL, PRIMARY KEY (IdCartera, DniN, DNI));
        INSERT INTO #cli (IdCartera, DNI, DniN)
        SELECT DISTINCT b.IdCartera, b.DNI,
               CASE WHEN x.x LIKE N'%[^0]%' THEN SUBSTRING(x.x, PATINDEX(N'%[^0]%', x.x), 30) ELSE N'0' END
        FROM score.BaseTrabajoCliente AS b
        INNER JOIN score.SacCartera AS sc ON sc.IdCartera = b.IdCartera AND sc.Activo = 1
        CROSS APPLY (SELECT LTRIM(RTRIM(CONVERT(NVARCHAR(30), b.DNI))) AS x) AS x;

        -- Operaciones de cada cartera, leídas de su tabla de asignación (columna de operación detectada)
        CREATE TABLE #ops (IdCartera INT NOT NULL, Op NVARCHAR(60) COLLATE DATABASE_DEFAULT NOT NULL, PRIMARY KEY (IdCartera, Op));
        CREATE TABLE #met (IdCartera INT NOT NULL PRIMARY KEY, Metodo VARCHAR(10) NOT NULL, Aviso NVARCHAR(400) NULL);
        DECLARE @Id INT, @Tabla NVARCHAR(256), @Obj INT, @Col SYSNAME, @Tipo SYSNAME, @sql NVARCHAR(MAX), @expr NVARCHAR(400);
        DECLARE c CURSOR LOCAL FAST_FORWARD FOR SELECT IdCartera, TablaAsignacion FROM score.SacCartera WHERE Activo = 1;
        OPEN c; FETCH NEXT FROM c INTO @Id, @Tabla;
        WHILE @@FETCH_STATUS = 0
        BEGIN
            SET @Obj = OBJECT_ID(N'Desarrollo.dbo.' + QUOTENAME(@Tabla));
            SET @Col = NULL;
            IF @Obj IS NOT NULL
                SELECT TOP (1) @Col = c2.name, @Tipo = t2.name
                FROM Desarrollo.sys.columns AS c2
                JOIN Desarrollo.sys.types AS t2 ON t2.user_type_id = c2.user_type_id
                WHERE c2.object_id = @Obj AND c2.name IN (N'Operacion', N'CodOperacion', N'Cod Operación', N'Cod Operacion', N'OPERACION')
                ORDER BY CASE c2.name WHEN N'Operacion' THEN 1 WHEN N'CodOperacion' THEN 2 ELSE 3 END;
            IF @Col IS NULL
                INSERT INTO #met VALUES (@Id, 'DNI', N'No se encontró la tabla ' + @Tabla + N' o su columna de operación: se cruza por DNI.');
            ELSE
            BEGIN
                SET @expr = CASE WHEN @Tipo IN (N'float', N'real', N'decimal', N'numeric', N'bigint', N'int')
                                 THEN N'CONVERT(NVARCHAR(60), CONVERT(DECIMAL(38, 0), a.' + QUOTENAME(@Col) + N'))'
                                 ELSE N'CONVERT(NVARCHAR(60), a.' + QUOTENAME(@Col) + N')' END;
                SET @sql = N'INSERT INTO #ops (IdCartera, Op)
                    SELECT DISTINCT @Id, CASE WHEN o.x LIKE N''%[^0]%'' THEN SUBSTRING(o.x, PATINDEX(N''%[^0]%'', o.x), 60) ELSE N''0'' END
                    FROM Desarrollo.dbo.' + QUOTENAME(@Tabla) + N' AS a WITH (NOLOCK)
                    CROSS APPLY (SELECT LTRIM(RTRIM(' + @expr + N')) COLLATE DATABASE_DEFAULT AS x) AS o
                    WHERE a.' + QUOTENAME(@Col) + N' IS NOT NULL;';
                EXEC sys.sp_executesql @sql, N'@Id INT', @Id = @Id;
                IF EXISTS (SELECT 1 FROM #ops AS p INNER JOIN #sac AS s ON s.Op = p.Op WHERE p.IdCartera = @Id)
                    INSERT INTO #met VALUES (@Id, 'OPERACION', NULL);
                ELSE
                    INSERT INTO #met VALUES (@Id, 'DNI', N'Ninguna operación de ' + @Tabla + N' cruzó con el SAC: se cruza por DNI.');
            END;
            FETCH NEXT FROM c INTO @Id, @Tabla;
        END;
        CLOSE c; DEALLOCATE c;

        -- Filas del SAC de cada cliente en cada cartera
        CREATE TABLE #fila (IdCartera INT NOT NULL, DNI VARCHAR(20) COLLATE DATABASE_DEFAULT NOT NULL, Op NVARCHAR(60) COLLATE DATABASE_DEFAULT NOT NULL,
                            SdoCapital FLOAT NULL, SdoCapitalVencido FLOAT NULL, DeudaTotal FLOAT NULL, DiasAtraso FLOAT NULL);
        INSERT INTO #fila
        SELECT k.IdCartera, k.DNI, s.Op, s.SdoCapital, s.SdoCapitalVencido, s.DeudaTotal, s.DiasAtraso
        FROM #sac AS s
        INNER JOIN #cli AS k ON k.DniN = s.DniN
        INNER JOIN #met AS m ON m.IdCartera = k.IdCartera
        WHERE m.Metodo = 'DNI'
           OR EXISTS (SELECT 1 FROM #ops AS p WHERE p.IdCartera = k.IdCartera AND p.Op = s.Op);

        CREATE TABLE #res (IdCartera INT NOT NULL, DNI VARCHAR(20) COLLATE DATABASE_DEFAULT NOT NULL, Operaciones SMALLINT NOT NULL,
                           SdoCapital DECIMAL(18, 2) NULL, SdoCapitalVencido DECIMAL(18, 2) NULL, DeudaTotal DECIMAL(18, 2) NULL,
                           DiasAtrasoMax INT NULL, PRIMARY KEY (IdCartera, DNI));
        INSERT INTO #res
        SELECT IdCartera, DNI, COUNT(DISTINCT Op), ROUND(SUM(SdoCapital), 2), ROUND(SUM(SdoCapitalVencido), 2),
               ROUND(SUM(DeudaTotal), 2), CONVERT(INT, MAX(DiasAtraso))
        FROM #fila GROUP BY IdCartera, DNI;

        -- Resumen del cruce por cartera
        CREATE TABLE #resumen (IdCartera INT NOT NULL PRIMARY KEY, Metodo VARCHAR(10) NOT NULL, OperacionesCartera INT NOT NULL,
                               OperacionesEnSac INT NOT NULL, ClientesCartera INT NOT NULL, ClientesEnSac INT NOT NULL, Aviso NVARCHAR(400) NULL);
        INSERT INTO #resumen
        SELECT m.IdCartera, m.Metodo,
               (SELECT COUNT(*) FROM #ops AS p WHERE p.IdCartera = m.IdCartera),
               (SELECT COUNT(*) FROM #ops AS p WHERE p.IdCartera = m.IdCartera AND EXISTS (SELECT 1 FROM #sac AS s WHERE s.Op = p.Op)),
               (SELECT COUNT(DISTINCT DNI) FROM #cli AS k WHERE k.IdCartera = m.IdCartera),
               (SELECT COUNT(*) FROM #res AS r WHERE r.IdCartera = m.IdCartera),
               m.Aviso
        FROM #met AS m;

        IF @Simular = 1
        BEGIN
            SELECT @FechaCarga AS FechaCargaSac, @FilasSac AS FilasSac;
            SELECT * FROM #resumen ORDER BY IdCartera;
            SELECT TOP 20 r.*, b.Capital AS CapitalAnalytics
            FROM #res AS r
            LEFT JOIN score.BaseTrabajoCliente AS b ON b.IdCartera = r.IdCartera AND b.DNI = r.DNI
            ORDER BY ABS(ISNULL(r.SdoCapital, 0) - ISNULL(b.Capital, 0)) DESC;
            RETURN 0;
        END;

        BEGIN TRANSACTION;
            DELETE FROM score.SacClienteDia WHERE FechaSac = @FechaSac;
            INSERT INTO score.SacClienteDia (FechaSac, IdCartera, DNI, Operaciones, SdoCapital, SdoCapitalVencido, DeudaTotal, DiasAtrasoMax)
            SELECT @FechaSac, IdCartera, DNI, Operaciones, SdoCapital, SdoCapitalVencido, DeudaTotal, DiasAtrasoMax FROM #res;
            DELETE FROM score.SacCargaCartera WHERE FechaSac = @FechaSac;
            INSERT INTO score.SacCargaCartera (FechaSac, IdCartera, Metodo, OperacionesCartera, OperacionesEnSac, ClientesCartera, ClientesEnSac, Aviso)
            SELECT @FechaSac, IdCartera, Metodo, OperacionesCartera, OperacionesEnSac, ClientesCartera, ClientesEnSac, Aviso FROM #resumen;
            DELETE FROM score.SacCarga WHERE FechaSac = @FechaSac;
            INSERT INTO score.SacCarga (FechaSac, FechaCarga, FilasSac) VALUES (@FechaSac, @FechaCarga, @FilasSac);
            -- 120 días de historia
            DELETE FROM score.SacClienteDia WHERE FechaSac < DATEADD(DAY, -120, @FechaSac);
            DELETE FROM score.SacCargaCartera WHERE FechaSac < DATEADD(DAY, -120, @FechaSac);
            DELETE FROM score.SacCarga WHERE FechaSac < DATEADD(DAY, -120, @FechaSac);
        COMMIT TRANSACTION;
        EXEC sys.sp_releaseapplock @Resource = 'score.sp_CargarSac', @LockOwner = 'Session';
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
        IF @Simular = 0 AND APPLOCK_MODE('public', 'score.sp_CargarSac', 'Session') <> 'NoLock'
            EXEC sys.sp_releaseapplock @Resource = 'score.sp_CargarSac', @LockOwner = 'Session';
        THROW;
    END CATCH;
    RETURN 0;
END;
GO

/* =====================================================================================
   BLOQUE 3 · Simulación (no escribe): cómo cruza cada cartera
   ===================================================================================== */
EXEC score.sp_CargarSac @Simular = 1;
GO

/* =====================================================================================
   BLOQUE 4 · vw_BaseTrabajo: + CapitalSac, RangoCapitalSac, EnSac (sobre la vista instalada)
   ===================================================================================== */
DECLARE @v NVARCHAR(MAX) = OBJECT_DEFINITION(OBJECT_ID('score.vw_BaseTrabajo'));
IF @v IS NULL THROW 51701, 'No existe score.vw_BaseTrabajo.', 1;
IF CHARINDEX(N'SacClienteDia', @v) > 0
    PRINT 'vw_BaseTrabajo ya tiene las columnas del SAC: no se cambia.';
ELSE
BEGIN
    DECLARE @c1 INT = CHARINDEX(N'gc.EstadoPdp,', @v);
    DECLARE @c2 INT = CHARINDEX(N'LEFT JOIN score.GestionTelefono', @v);
    IF @c1 = 0 OR @c2 = 0
        THROW 51702, 'No se encontraron los puntos de inserción en vw_BaseTrabajo. No se cambió nada.', 1;
    DECLARE @cols NVARCHAR(MAX) = N'
       -- fase 17 · SAC del día (Compartamos vigente): capital del día y si el cliente sigue en el SAC
       CONVERT(DECIMAL(18, 2), CASE WHEN sc.IdCartera IS NOT NULL THEN sac.SdoCapital END) AS CapitalSac,
       CONVERT(NVARCHAR(30), CASE WHEN sc.IdCartera IS NULL THEN NULL
                                  WHEN sac.DNI IS NULL THEN N''NO ESTÁ EN SAC''
                                  WHEN sac.SdoCapital IS NULL THEN N''0. SIN INFORMACION''
                                  WHEN sac.SdoCapital < 500 THEN N''1. [0 - 499.99]''
                                  WHEN sac.SdoCapital < 1000 THEN N''2. [500 - 999.99]''
                                  WHEN sac.SdoCapital < 2500 THEN N''3. [1,000 - 2,499.99]''
                                  WHEN sac.SdoCapital < 5000 THEN N''4. [2,500 - 4,999.99]''
                                  WHEN sac.SdoCapital < 10000 THEN N''5. [5,000 - 9,999.99]''
                                  WHEN sac.SdoCapital < 20000 THEN N''6. [10,000 - 19,999.99]''
                                  ELSE N''7. [20,000+]'' END) AS RangoCapitalSac,
       CONVERT(NVARCHAR(20), CASE WHEN sc.IdCartera IS NULL THEN NULL
                                  -- la foto vale hoy y el día siguiente (el lunes, también la del sábado)
                                  WHEN sacu.FechaSac IS NULL
                                    OR DATEDIFF(DAY, sacu.FechaSac, GETDATE())
                                       > CASE WHEN DATEDIFF(DAY, ''19000101'', GETDATE()) % 7 = 0 THEN 2 ELSE 1 END
                                       THEN N''SAC DESACTUALIZADO''
                                  WHEN sac.DNI IS NULL THEN N''NO''
                                  ELSE N''SI'' END) AS EnSac,
       ';
    DECLARE @join NVARCHAR(MAX) = N'LEFT JOIN score.SacCartera AS sc
       ON sc.IdCartera = s.IdCartera AND sc.Activo = 1
OUTER APPLY (SELECT MAX(FechaSac) AS FechaSac FROM score.SacCarga) AS sacu
LEFT JOIN score.SacClienteDia AS sac
       ON sac.FechaSac = sacu.FechaSac AND sac.IdCartera = s.IdCartera AND sac.DNI = s.DNI
';
    SET @v = STUFF(@v, @c2, 0, @join);
    SET @v = STUFF(@v, @c1, 0, @cols);
    DECLARE @vc INT = CHARINDEX(N'CREATE', @v), @vv INT = CHARINDEX(N'VIEW', @v);
    SET @v = STUFF(@v, @vc, @vv - @vc, N'CREATE OR ALTER ');
    EXEC sys.sp_executesql @v;
    PRINT 'vw_BaseTrabajo: agregadas CapitalSac, RangoCapitalSac y EnSac.';
END;
GO

/* =====================================================================================
   BLOQUE 5 · Catálogo (solo para las carteras del SAC)
   ===================================================================================== */
MERGE score.Campo AS t
USING (VALUES
    (N'EN_SAC', N'En el SAC del día', N'SAC', N'CLIENTE', N'LISTA', N'TRABAJO', N'EnSac', N'SI|NO|SAC DESACTUALIZADO',
     N'SI = el cliente tiene operaciones de la cartera en el SAC del día. NO = ya no está (pagó, canceló o salió, con o sin gestión). SAC DESACTUALIZADO = la última foto del SAC es de antes del día hábil anterior: no se puede saber.',
     N'score.SacClienteDia ← Desarrollo.dbo.SAC_CAR_BIZNESCOB', N'Cada carga del SAC (el generador toma la foto solo)', 0),
    (N'RANGO_CAPITAL_SAC', N'Rango de capital (SAC del día)', N'RCS', N'CLIENTE', N'LISTA', N'TRABAJO', N'RangoCapitalSac',
     N'7. [20,000+]|6. [10,000 - 19,999.99]|5. [5,000 - 9,999.99]|4. [2,500 - 4,999.99]|3. [1,000 - 2,499.99]|2. [500 - 999.99]|1. [0 - 499.99]|0. SIN INFORMACION|NO ESTÁ EN SAC',
     N'Escala estándar sobre la suma del saldo capital [SdoCapital] de las operaciones del cliente en la cartera, en el SAC del día.',
     N'score.SacClienteDia ← Desarrollo.dbo.SAC_CAR_BIZNESCOB', N'Cada carga del SAC', 0),
    (N'CAPITAL_SAC', N'Saldo capital (SAC del día)', N'KS', N'CLIENTE', N'RANGO', N'TRABAJO', N'CapitalSac', NULL,
     N'Suma de [SdoCapital] de las operaciones del cliente en la cartera, en el SAC del día.',
     N'score.SacClienteDia ← Desarrollo.dbo.SAC_CAR_BIZNESCOB', N'Cada carga del SAC', 0)
) AS s (Codigo, Etiqueta, Abreviatura, Grupo, TipoFiltro, Origen, ColumnaOrigen, OrdenValores, Descripcion, Fuente,
        Actualizacion, TodasLasCarteras)
ON t.Codigo = s.Codigo
WHEN MATCHED THEN UPDATE SET Etiqueta = s.Etiqueta, Abreviatura = s.Abreviatura, Grupo = s.Grupo,
     TipoFiltro = s.TipoFiltro, Origen = s.Origen, ColumnaOrigen = s.ColumnaOrigen, OrdenValores = s.OrdenValores,
     Descripcion = s.Descripcion, Fuente = s.Fuente, Actualizacion = s.Actualizacion, TodasLasCarteras = s.TodasLasCarteras
WHEN NOT MATCHED THEN INSERT (Codigo, Etiqueta, Abreviatura, Grupo, TipoFiltro, Origen, ColumnaOrigen, OrdenValores,
     Descripcion, Fuente, Actualizacion, TodasLasCarteras)
     VALUES (s.Codigo, s.Etiqueta, s.Abreviatura, s.Grupo, s.TipoFiltro, s.Origen, s.ColumnaOrigen, s.OrdenValores,
             s.Descripcion, s.Fuente, s.Actualizacion, s.TodasLasCarteras);

MERGE score.CampoCartera AS t
USING (SELECT f.Campo, sc.IdCartera, N'CLIENTE' AS Nivel, N'score.SacClienteDia' AS Tabla, f.Columna
       FROM score.SacCartera AS sc
       CROSS JOIN (VALUES (N'EN_SAC', N'EnSac'), (N'RANGO_CAPITAL_SAC', N'RangoCapitalSac'), (N'CAPITAL_SAC', N'CapitalSac')) AS f (Campo, Columna)
       WHERE sc.Activo = 1) AS s
ON t.Campo = s.Campo AND t.IdCartera = s.IdCartera
WHEN MATCHED THEN UPDATE SET Nivel = s.Nivel, Tabla = s.Tabla, Columna = s.Columna
WHEN NOT MATCHED THEN INSERT (Campo, IdCartera, Nivel, Tabla, Columna) VALUES (s.Campo, s.IdCartera, s.Nivel, s.Tabla, s.Columna);
GO

/* =====================================================================================
   BLOQUE 6 · Primera foto (real) y controles
   ===================================================================================== */
EXEC score.sp_CargarSac @Simular = 0;
GO
SELECT * FROM score.SacCarga ORDER BY FechaSac DESC;
SELECT * FROM score.SacCargaCartera ORDER BY FechaSac DESC, IdCartera;
SELECT IdCartera, EnSac, RangoCapitalSac, COUNT(DISTINCT DNI) AS Clientes
FROM score.vw_BaseTrabajo WHERE IdCartera IN (126, 128, 133)
GROUP BY IdCartera, EnSac, RangoCapitalSac
ORDER BY IdCartera, EnSac, RangoCapitalSac;
GO
