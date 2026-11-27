/* =====================================================================================
   score_telefonico_fase16_recupero.sql · 25/11/2026
   Bases de recupero (Hardy): PDP caídas del mes / históricas y seguimientos caídos del mes / históricos.

   1. score.PdpAnteriorCliente: la última PDP (monto > 0) generada en los 6 meses ANTERIORES al mes en curso,
      por cliente y cartera: CAÍDA / PAGADA / VIGENTE / SIN FECHA, con su fecha de generación y de compromiso.
      Se arma dentro de score.sp_ArmarGestion (mismo paso GESTION de "Actualizar" y de la carga programada),
      con las gestiones que ese procedimiento ya lee (#gh: 6 meses, gestiones CEF o sin tipo de contacto).
   2. score.sp_ArmarGestion: se le agregan dos bloques. NO se reemplaza el procedimiento: se toma el que está
      instalado (con los cambios que tenga) y se le insertan los bloques en dos puntos fijos. Si no los encuentra,
      se detiene sin cambiar nada.
   3. score.vw_BaseTrabajo: se le agregan tres columnas, de la misma forma (sobre la vista instalada):
        EstadoPdpAnterior  · CAÍDA / PAGADA / VIGENTE / SIN FECHA / SIN PDP ANT
        PdpAnteriorMes     · Mes anterior / Hace 2-3 meses / Hace 4-6 meses / SIN PDP ANT
        SeguimientoMes     · Este mes / Mes anterior / Hace 2-3 meses / Hace 4-6 meses / Más de 6 meses / SIN SEG
                             (cuándo fue el último seguimiento; el estado sigue en EstadoSeguimiento)
   4. Catálogo: tres filtros nuevos de "Gestión del cliente" para todas las carteras.
   5. Armado de todas las carteras con la gestión (el mismo bucle de la fase 11) y controles.

   Bloques 1 a 4: segundos. Bloque 5: lo que tarda un "Actualizar" de gestión por cartera.
   ===================================================================================== */
USE CobAuto;
GO

/* =====================================================================================
   BLOQUE 1 · Tabla
   ===================================================================================== */
IF OBJECT_ID('score.PdpAnteriorCliente') IS NULL
BEGIN
    CREATE TABLE score.PdpAnteriorCliente (
        IdCartera          INT           NOT NULL,
        DNI                VARCHAR(20)   NOT NULL,
        EstadoPdpAnterior  NVARCHAR(10)  NOT NULL,   -- CAÍDA / PAGADA / VIGENTE / SIN FECHA
        FechaGeneracion    DATE          NOT NULL,   -- día de la gestión que registró la PDP
        FechaCompromiso    DATE          NULL,
        FechaArmado        DATETIME2(0)  NOT NULL CONSTRAINT DF_score_PdpAnterior_Armado DEFAULT (SYSDATETIME()),
        CONSTRAINT PK_score_PdpAnteriorCliente PRIMARY KEY CLUSTERED (IdCartera, DNI)
    );
END;
GO

/* =====================================================================================
   BLOQUE 2 · sp_ArmarGestion: calcula y guarda la PDP anterior (sobre el procedimiento instalado)
   ===================================================================================== */
DECLARE @def NVARCHAR(MAX) = OBJECT_DEFINITION(OBJECT_ID('score.sp_ArmarGestion'));
IF @def IS NULL THROW 51601, 'No existe score.sp_ArmarGestion: ejecutar antes las fases 7 y 11.', 1;

IF CHARINDEX(N'#pdpant', @def) > 0
    PRINT 'sp_ArmarGestion ya tiene la PDP anterior: no se cambia.';
ELSE
BEGIN
    DECLARE @a1 INT = CHARINDEX(N'VALUES (''pdp'', @@ROWCOUNT', @def);
    DECLARE @fin1 INT = CASE WHEN @a1 > 0 THEN CHARINDEX(N'SET @t0 = SYSDATETIME();', @def, @a1) END;
    DECLARE @a2 INT = CHARINDEX(N'/* 9. Guardar', @def);
    IF ISNULL(@a1, 0) = 0 OR ISNULL(@fin1, 0) = 0 OR ISNULL(@a2, 0) = 0
        THROW 51602, 'No se encontraron los puntos de inserción en sp_ArmarGestion (paso de PDP y "9. Guardar"). No se cambió nada.', 1;
    SET @fin1 = @fin1 + LEN(N'SET @t0 = SYSDATETIME();');

    DECLARE @bloque1 NVARCHAR(MAX) = N'

    /* 4b. PDP anterior (fase 16, 25/11/2026): la última PDP (monto > 0) generada en los 6 meses ANTERIORES al mes,
           con las gestiones ya leídas en #gh (de meses pasados solo trae CEF o sin tipo de contacto). */
    CREATE TABLE #pdpant (DNI VARCHAR(20) COLLATE DATABASE_DEFAULT NOT NULL PRIMARY KEY,
                          EstadoPdpAnterior NVARCHAR(10) NOT NULL, FechaGeneracion DATE NOT NULL, FechaCompromiso DATE NULL);
    ;WITH pa AS (
        SELECT h.DNI, CAST(h.Momento AS DATE) AS FechaGeneracion, CAST(cp.FechaCompromiso AS DATE) AS FechaCompromiso,
               UPPER(LTRIM(RTRIM(ISNULL(CONVERT(VARCHAR(10), cp.Pagado), '''')))) AS Pagado,
               ROW_NUMBER() OVER (PARTITION BY h.DNI ORDER BY h.Momento DESC, cp.IdCompromiso DESC) AS rn
        FROM siscob.dbo.COMPROMISO AS cp WITH (NOLOCK)
        INNER JOIN #gh AS h ON h.IdGestion = cp.IdGestion
        WHERE h.Momento < @IniMes AND cp.Monto > 0
    )
    INSERT INTO #pdpant (DNI, EstadoPdpAnterior, FechaGeneracion, FechaCompromiso)
    SELECT DNI,
           CASE WHEN Pagado IN (''SI'', ''S'') THEN N''PAGADA''
                WHEN FechaCompromiso IS NULL THEN N''SIN FECHA''
                WHEN FechaCompromiso >= @Hoy THEN N''VIGENTE''
                ELSE N''CAÍDA'' END,
           FechaGeneracion, FechaCompromiso
    FROM pa WHERE rn = 1;
    INSERT INTO @T VALUES (''pdp_anterior'', @@ROWCOUNT, DATEDIFF(MILLISECOND, @t0, SYSDATETIME())); SET @t0 = SYSDATETIME();';

    DECLARE @bloque2 NVARCHAR(MAX) = N'/* 8b. PDP anterior (fase 16): reemplaza la de la cartera */
    BEGIN TRANSACTION;
        DELETE FROM score.PdpAnteriorCliente WHERE IdCartera = @IdCartera;
        INSERT INTO score.PdpAnteriorCliente (IdCartera, DNI, EstadoPdpAnterior, FechaGeneracion, FechaCompromiso, FechaArmado)
        SELECT @IdCartera, DNI, EstadoPdpAnterior, FechaGeneracion, FechaCompromiso, @Ahora FROM #pdpant;
    COMMIT TRANSACTION;

    ';

    -- Primero el punto de más adelante, para no mover el otro
    SET @def = STUFF(@def, @a2, 0, @bloque2);
    SET @def = STUFF(@def, @fin1, 0, @bloque1);
    -- CREATE … PROCEDURE → CREATE OR ALTER PROCEDURE
    DECLARE @pc INT = CHARINDEX(N'CREATE', @def), @pp INT = CHARINDEX(N'PROCEDURE', @def);
    SET @def = STUFF(@def, @pc, @pp - @pc, N'CREATE OR ALTER ');
    EXEC sys.sp_executesql @def;
    PRINT 'sp_ArmarGestion: agregada la PDP anterior.';
END;
GO

/* =====================================================================================
   BLOQUE 3 · vw_BaseTrabajo: tres columnas nuevas (sobre la vista instalada)
   ===================================================================================== */
DECLARE @v NVARCHAR(MAX) = OBJECT_DEFINITION(OBJECT_ID('score.vw_BaseTrabajo'));
IF @v IS NULL THROW 51603, 'No existe score.vw_BaseTrabajo.', 1;
IF CHARINDEX(N'PdpAnteriorCliente', @v) > 0
    PRINT 'vw_BaseTrabajo ya tiene las columnas de recupero: no se cambia.';
ELSE
BEGIN
    DECLARE @c1 INT = CHARINDEX(N'gc.EstadoPdp,', @v);
    DECLARE @c2 INT = CHARINDEX(N'LEFT JOIN score.GestionTelefono', @v);
    IF @c1 = 0 OR @c2 = 0
        THROW 51604, 'No se encontraron los puntos de inserción en vw_BaseTrabajo (gc.EstadoPdp y el JOIN de GestionTelefono). No se cambió nada.', 1;
    DECLARE @cols NVARCHAR(MAX) = N'
       -- fase 16 · recupero: PDP de meses anteriores y antigüedad del último seguimiento
       CONVERT(NVARCHAR(12), CASE WHEN gc.DNI IS NULL THEN NULL ELSE ISNULL(pa.EstadoPdpAnterior, N''SIN PDP ANT'') END) AS EstadoPdpAnterior,
       CONVERT(NVARCHAR(20), CASE WHEN gc.DNI IS NULL THEN NULL
                                  WHEN pa.FechaGeneracion IS NULL THEN N''SIN PDP ANT''
                                  WHEN DATEDIFF(MONTH, pa.FechaGeneracion, GETDATE()) <= 1 THEN N''Mes anterior''
                                  WHEN DATEDIFF(MONTH, pa.FechaGeneracion, GETDATE()) <= 3 THEN N''Hace 2-3 meses''
                                  ELSE N''Hace 4-6 meses'' END) AS PdpAnteriorMes,
       CONVERT(NVARCHAR(20), CASE WHEN gc.DNI IS NULL THEN NULL
                                  WHEN gc.FechaSeguimiento IS NULL THEN N''SIN SEG''
                                  WHEN DATEDIFF(MONTH, gc.FechaSeguimiento, GETDATE()) = 0 THEN N''Este mes''
                                  WHEN DATEDIFF(MONTH, gc.FechaSeguimiento, GETDATE()) = 1 THEN N''Mes anterior''
                                  WHEN DATEDIFF(MONTH, gc.FechaSeguimiento, GETDATE()) <= 3 THEN N''Hace 2-3 meses''
                                  WHEN DATEDIFF(MONTH, gc.FechaSeguimiento, GETDATE()) <= 6 THEN N''Hace 4-6 meses''
                                  ELSE N''Más de 6 meses'' END) AS SeguimientoMes,
       ';
    DECLARE @join NVARCHAR(MAX) = N'LEFT JOIN score.PdpAnteriorCliente AS pa
       ON pa.IdCartera = s.IdCartera AND pa.DNI = s.DNI
';
    SET @v = STUFF(@v, @c2, 0, @join);
    SET @v = STUFF(@v, @c1, 0, @cols);
    DECLARE @vc INT = CHARINDEX(N'CREATE', @v), @vv INT = CHARINDEX(N'VIEW', @v);
    SET @v = STUFF(@v, @vc, @vv - @vc, N'CREATE OR ALTER ');
    EXEC sys.sp_executesql @v;
    PRINT 'vw_BaseTrabajo: agregadas EstadoPdpAnterior, PdpAnteriorMes y SeguimientoMes.';
END;
GO

/* =====================================================================================
   BLOQUE 4 · Catálogo
   ===================================================================================== */
MERGE score.Campo AS t
USING (VALUES
    (N'PDP_ANTERIOR', N'PDP de meses anteriores', N'PDPA', N'GESTION_CLIENTE', N'LISTA', N'TRABAJO', N'EstadoPdpAnterior',
     N'CAÍDA|PAGADA|VIGENTE|SIN FECHA|SIN PDP ANT',
     N'Estado de la última PDP (monto > 0) generada en los 6 meses anteriores al mes en curso. CAÍDA = la fecha de compromiso pasó sin pago. SIN PDP ANT = no tuvo PDP en esos meses. La PDP del mes está en "Estado de la PDP".',
     N'score.PdpAnteriorCliente ← siscob.dbo.gestion + COMPROMISO (en sp_ArmarGestion)', N'Cada actualización de la cartera (datos hasta ayer)', 1),
    (N'PDP_ANTERIOR_MES', N'Cuándo fue la PDP anterior', N'PDPAM', N'GESTION_CLIENTE', N'LISTA', N'TRABAJO', N'PdpAnteriorMes',
     N'Mes anterior|Hace 2-3 meses|Hace 4-6 meses|SIN PDP ANT',
     N'Mes en que se generó la PDP de meses anteriores.',
     N'score.PdpAnteriorCliente', N'Cada actualización de la cartera (datos hasta ayer)', 1),
    (N'SEGUIMIENTO_MES', N'Cuándo fue el último seguimiento', N'SEGM', N'GESTION_CLIENTE', N'LISTA', N'TRABAJO', N'SeguimientoMes',
     N'Este mes|Mes anterior|Hace 2-3 meses|Hace 4-6 meses|Más de 6 meses|SIN SEG',
     N'Mes del último seguimiento / negociación / volver a llamar (historia desde 2022). Junto con "Estado de seguimiento" separa los caídos del mes de los históricos.',
     N'score.GestionCliente.FechaSeguimiento', N'Cada actualización de la cartera; el mes se calcula con la fecha de hoy', 1)
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
GO

/* =====================================================================================
   BLOQUE 5 · Armar la gestión de todas las carteras (llena la PDP anterior) y controles
   ===================================================================================== */
-- 5.1 Prueba en una cartera (no escribe): debe aparecer la fila "pdp_anterior" en los tiempos
DECLARE @Aviso NVARCHAR(1000);
EXEC score.sp_ArmarGestion @IdCartera = 126, @Simular = 1, @Aviso = @Aviso OUTPUT;
GO

-- 5.2 Todas las carteras con tabla de trabajo
DECLARE @Id INT, @Aviso NVARCHAR(1000);
DECLARE c CURSOR LOCAL FAST_FORWARD FOR SELECT DISTINCT IdCartera FROM score.GestionCliente ORDER BY IdCartera;
OPEN c; FETCH NEXT FROM c INTO @Id;
WHILE @@FETCH_STATUS = 0
BEGIN
    EXEC score.sp_ArmarGestion @IdCartera = @Id, @Simular = 0, @Aviso = @Aviso OUTPUT;
    PRINT CONCAT('Cartera ', @Id, ' armada', CASE WHEN @Aviso IS NOT NULL THEN ' · aviso: ' + @Aviso ELSE '' END);
    FETCH NEXT FROM c INTO @Id;
END;
CLOSE c; DEALLOCATE c;
GO

-- 5.3 Controles: PDP anterior y antigüedad de seguimientos por cartera
SELECT IdCartera, EstadoPdpAnterior, PdpAnteriorMes, EstadoPdp AS PdpDelMes, COUNT(DISTINCT DNI) AS Clientes
FROM score.vw_BaseTrabajo
GROUP BY IdCartera, EstadoPdpAnterior, PdpAnteriorMes, EstadoPdp
ORDER BY IdCartera, EstadoPdpAnterior, PdpAnteriorMes, EstadoPdp;

SELECT IdCartera, EstadoSeguimiento, SeguimientoMes, COUNT(DISTINCT DNI) AS Clientes
FROM score.vw_BaseTrabajo
WHERE EstadoSeguimiento IN (N'CAÍDO', N'PDP CAÍDA')
GROUP BY IdCartera, EstadoSeguimiento, SeguimientoMes
ORDER BY IdCartera, EstadoSeguimiento, SeguimientoMes;
GO
