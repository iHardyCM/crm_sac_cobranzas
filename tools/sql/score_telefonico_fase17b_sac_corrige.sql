/* =====================================================================================
   score_telefonico_fase17b_sac_corrige.sql · 25/11/2026
   Corrige score.sp_CargarSac: la foto tomaba solo las filas con la ÚLTIMA hora exacta de FechaCarga (4 filas),
   pero FechaCarga cambia fila a fila mientras el SAC se carga (09:47:34 … 09:48:28). Ahora toma todo el día de la
   carga. Luego rehace la foto de hoy y muestra los controles.
   ===================================================================================== */
USE CobAuto;
GO

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

-- 1. Simulación: el cruce por cartera debe salir por OPERACION en 126, 128 y 133, con miles de clientes en el SAC
EXEC score.sp_CargarSac @Simular = 1;
GO

-- 2. Foto real de hoy (reemplaza la de 4 filas)
EXEC score.sp_CargarSac @Simular = 0, @Forzar = 1;
GO

-- 3. Controles
SELECT * FROM score.SacCarga ORDER BY FechaSac DESC;
SELECT * FROM score.SacCargaCartera ORDER BY FechaSac DESC, IdCartera;
SELECT IdCartera, EnSac, RangoCapitalSac, COUNT(DISTINCT DNI) AS Clientes
FROM score.vw_BaseTrabajo WHERE IdCartera IN (126, 128, 133)
GROUP BY IdCartera, EnSac, RangoCapitalSac
ORDER BY IdCartera, EnSac, RangoCapitalSac;
GO
