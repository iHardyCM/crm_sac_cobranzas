/* =====================================================================================
   Score telefónico · fase 11 · Estado de seguimiento para todas las carteras        (17/11/2026)
   Base: CobAuto (esquema score). Se puede volver a ejecutar completo.

   Reglas (Hardy, 17/11/2026):
   - Seguimiento = gestión con un indicador de seguimiento / negociación / volver a llamar de SU cartera.
     Lista: Biznescob_Analytics.dbo.CFG_SEGUIMIENTO_INDICADOR (la misma de la bolsa de seguimientos de Analytics,
     02-03/11): Compartamos 915 · SIP 1068 · Interbank 958, 959 · MiBanco 1119, 1120, 1125, 1089, 1124 ·
     Propia 1188, 1189. Agregar o quitar un indicador ahí cambia las dos cosas.
   - Fecha = la del ÚLTIMO seguimiento del cliente: un seguimiento nuevo reinicia el plazo. Toda la historia
     (desde 2022): se guarda en score.SeguimientoCliente y cada actualización lee solo los últimos 7 días.
   - Tope = fecha del último seguimiento + días hábiles (lunes a sábado; los feriados cuentan), según el día del
     mes del seguimiento (score.SeguimientoPlazo, Hardy 17/11, como la vista anterior de MiBanco):
       día 1 al 19      → 3 días. Ej.: lunes 9 → martes y miércoles VIGENTE, jueves 12 HOY, viernes CAÍDO.
       día 20 en adelante → 1 día. Ej.: viernes 20 → ese día VIGENTE, sábado 21 HOY, lunes 23 CAÍDO.
     Diferencias con la vista anterior: ella contaba días calendario (el domingo contaba) y a fin de mes ponía HOY
     desde el mismo día del seguimiento.
   - Estado (grupo Gestión del cliente, campo "Estado de seguimiento"):
       VIGENTE  antes del tope (incluye el mismo día del seguimiento)
       HOY      es el día tope
       CAÍDO    pasó el tope (sin límite de antigüedad)
       PDP ...  hay una PDP (monto > 0) generada después del último seguimiento; se mira la última (17/11):
                PDP VIGENTE (compromiso de hoy en adelante: respetar) · PDP CAÍDA (compromiso pasado sin pago:
                se puede gestionar) · PDP PAGADA · PDP SIN FECHA
       SIN SEG  nunca tuvo seguimiento en la cartera
   - El estado se calcula en la vista con la fecha de hoy: no envejece si un día no se actualiza.
   - Los datos llegan hasta ayer, como el resto de la gestión. Un seguimiento tipificado HOY se ve en la
     condición del día "Contacto directo (CEF) hoy" (si el indicador es CEF) y entra al estado en la siguiente
     actualización.
   - Reemplaza al campo de la 112 que venía de MiBanco_Cobranzas.dbo.VW_SEGUIMIENTOS (mismo código
     SEGUIMIENTO_ACTUAL, ahora para todas las carteras).
   - No se detectan pagos sin PDP (no hay una fuente de pagos común en SISCOB).

   ORDEN
     BLOQUE 0 · Tablas, columnas y función de días hábiles
     BLOQUE 1 · score.sp_ArmarGestion (paso 5 nuevo)
     BLOQUE 2 · score.vw_BaseTrabajo (estado calculado)
     BLOQUE 3 · Catálogo
     BLOQUE 4 · Prueba (ejecutar por partes, después de los bloques 0 a 3)
   Después: reiniciar no hace falta (el generador lee la vista); recargar el generador.
   ===================================================================================== */
USE CobAuto;
GO

IF DB_ID('Biznescob_Analytics') IS NULL OR OBJECT_ID('Biznescob_Analytics.dbo.CFG_SEGUIMIENTO_INDICADOR') IS NULL
    THROW 51101, 'No existe Biznescob_Analytics.dbo.CFG_SEGUIMIENTO_INDICADOR (lista de indicadores de seguimiento).', 1;
GO

/* =====================================================================================
   BLOQUE 0 · Tablas, columnas y función
   ===================================================================================== */
IF OBJECT_ID('score.SeguimientoCliente', 'U') IS NULL
CREATE TABLE score.SeguimientoCliente (
    IdCartera       INT           NOT NULL,
    DNI             VARCHAR(20)   NOT NULL,
    UltSeguimiento  DATETIME2(0)  NOT NULL,     -- fecha y hora del último seguimiento (hasta el día anterior al armado)
    IdGestion       INT           NOT NULL,     -- siscob.dbo.gestion de ese seguimiento
    Actualizado     DATETIME2(0)  NOT NULL,
    CONSTRAINT PK_score_SeguimientoCliente PRIMARY KEY CLUSTERED (IdCartera, DNI)
);
GO

IF OBJECT_ID('score.SeguimientoLectura', 'U') IS NULL
CREATE TABLE score.SeguimientoLectura (
    IdCartera    INT           NOT NULL CONSTRAINT PK_score_SeguimientoLectura PRIMARY KEY,
    LeidoHasta   DATE          NOT NULL,        -- último día leído de siscob; la siguiente lectura repasa 7 días antes
    Actualizado  DATETIME2(0)  NOT NULL
);
GO

IF COL_LENGTH('score.GestionCliente', 'FechaLimiteSeguimiento') IS NULL
    ALTER TABLE score.GestionCliente ADD FechaLimiteSeguimiento DATE NULL;
IF COL_LENGTH('score.GestionCliente', 'PdpTrasSeguimiento') IS NULL
    ALTER TABLE score.GestionCliente ADD PdpTrasSeguimiento BIT NULL;
IF COL_LENGTH('score.GestionCliente', 'PdpTrasFechaCompromiso') IS NULL
    ALTER TABLE score.GestionCliente ADD PdpTrasFechaCompromiso DATE NULL;
IF COL_LENGTH('score.GestionCliente', 'PdpTrasPagada') IS NULL
    ALTER TABLE score.GestionCliente ADD PdpTrasPagada BIT NULL;
GO

-- Plazo según el día del mes del seguimiento (se puede cambiar sin tocar código; luego volver a armar)
IF OBJECT_ID('score.SeguimientoPlazo', 'U') IS NULL
CREATE TABLE score.SeguimientoPlazo (
    DiaDesde     TINYINT  NOT NULL CONSTRAINT PK_score_SeguimientoPlazo PRIMARY KEY,
    DiaHasta     TINYINT  NOT NULL,
    DiasHabiles  TINYINT  NOT NULL CONSTRAINT CK_score_SeguimientoPlazo_Dias CHECK (DiasHabiles BETWEEN 1 AND 15),
    CONSTRAINT CK_score_SeguimientoPlazo_Rango CHECK (DiaDesde BETWEEN 1 AND 31 AND DiaHasta BETWEEN DiaDesde AND 31)
);
GO
MERGE score.SeguimientoPlazo AS t
USING (VALUES (1, 19, 3), (20, 31, 1)) AS s (DiaDesde, DiaHasta, DiasHabiles)
ON t.DiaDesde = s.DiaDesde
WHEN MATCHED THEN UPDATE SET DiaHasta = s.DiaHasta, DiasHabiles = s.DiasHabiles
WHEN NOT MATCHED BY TARGET THEN INSERT (DiaDesde, DiaHasta, DiasHabiles) VALUES (s.DiaDesde, s.DiaHasta, s.DiasHabiles)
WHEN NOT MATCHED BY SOURCE THEN DELETE;
GO

-- @Dias días hábiles después de @Desde, contando de lunes a sábado (el domingo no cuenta; 07/01/1900 fue domingo).
CREATE OR ALTER FUNCTION score.fn_SumarDiasHabiles (@Desde DATE, @Dias INT)
RETURNS TABLE
AS
RETURN
    SELECT MAX(x.Dia) AS Fecha
    FROM (SELECT TOP (@Dias) DATEADD(DAY, n.n, @Desde) AS Dia
          FROM (VALUES (1), (2), (3), (4), (5), (6), (7), (8), (9), (10), (11), (12), (13), (14), (15), (16), (17), (18))
               AS n (n)
          WHERE DATEDIFF(DAY, '19000107', DATEADD(DAY, n.n, @Desde)) % 7 <> 0
          ORDER BY n.n) AS x;
GO

/* =====================================================================================
   BLOQUE 1 · Procedimiento (igual a la fase 7 salvo el paso 5, el guardado y la simulación)
   ===================================================================================== */
CREATE OR ALTER PROCEDURE score.sp_ArmarGestion
    @IdCartera INT,
    @Simular   BIT = 1,                     -- 1 = no escribe; devuelve distribuciones y tiempos
    @Hoy       DATE = NULL,                 -- NULL = hoy (los datos llegan hasta el día anterior)
    @Aviso     NVARCHAR(1000) = NULL OUTPUT, -- lo que no se pudo armar (p. ej. la lectura de seguimientos)
    @DiasSeguimiento INT = NULL             -- NULL = plazo de score.SeguimientoPlazo según el día del mes; un número lo fuerza
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    IF @Hoy IS NULL SET @Hoy = CAST(GETDATE() AS DATE);
    DECLARE @IniMes DATE = DATEFROMPARTS(YEAR(@Hoy), MONTH(@Hoy), 1);
    DECLARE @Ini6 DATE = DATEADD(MONTH, -6, @IniMes),
            @Ayer DATE = DATEADD(DAY, -1, @Hoy),
            @Ahora DATETIME2(0) = SYSDATETIME();
    DECLARE @T TABLE (Orden INT IDENTITY(1, 1), Seccion VARCHAR(40), Filas INT, Ms INT);
    DECLARE @t0 DATETIME2(3) = SYSDATETIME();
    SET @Aviso = NULL;

    /* 0. Universo: los teléfonos y clientes de la cartera hoy */
    CREATE TABLE #tel (DNI VARCHAR(20) COLLATE DATABASE_DEFAULT NOT NULL,
                       Telefono CHAR(9) COLLATE DATABASE_DEFAULT NOT NULL,
                       PRIMARY KEY (DNI, Telefono));
    INSERT INTO #tel (DNI, Telefono)
    SELECT DISTINCT LEFT(u.DNI, 20), CONVERT(CHAR(9), u.Telefono)
    FROM score.TelefonoUniverso AS u
    WHERE u.IdCartera = @IdCartera;

    CREATE TABLE #dni (DNI VARCHAR(20) COLLATE DATABASE_DEFAULT NOT NULL PRIMARY KEY);
    INSERT INTO #dni (DNI) SELECT DISTINCT DNI FROM #tel;
    IF NOT EXISTS (SELECT 1 FROM #dni)
        THROW 50701, 'La cartera no tiene teléfonos en score.TelefonoUniverso.', 1;
    INSERT INTO @T VALUES ('universo', (SELECT COUNT(*) FROM #tel), DATEDIFF(MILLISECOND, @t0, SYSDATETIME())); SET @t0 = SYSDATETIME();

    /* 1. Condición de SISCOB. Si el DNI tiene varios clientes en la cartera: activo (A/N) y el más reciente. */
    CREATE TABLE #cond (DNI VARCHAR(20) COLLATE DATABASE_DEFAULT NOT NULL PRIMARY KEY, Condicion NVARCHAR(100) NULL);
    ;WITH c AS (
        SELECT CONVERT(VARCHAR(20), LEFT(LTRIM(RTRIM(cl.Dni)), 20)) COLLATE DATABASE_DEFAULT AS DNI,
               CONVERT(NVARCHAR(100), COALESCE(NULLIF(LTRIM(RTRIM(CONVERT(NVARCHAR(200), cn.Descripcion))), N''),
                                               NULLIF(LTRIM(RTRIM(CONVERT(NVARCHAR(200), cn.Codigo))), N''))) AS Condicion,
               ROW_NUMBER() OVER (PARTITION BY LTRIM(RTRIM(cl.Dni))
                                  ORDER BY CASE WHEN UPPER(LTRIM(RTRIM(ISNULL(cl.Estado, '')))) IN ('A', 'N') THEN 0 ELSE 1 END,
                                           cl.IdCliente DESC) AS rn
        FROM siscob.dbo.Cliente AS cl WITH (NOLOCK)
        LEFT JOIN siscob.dbo.Condicion AS cn WITH (NOLOCK) ON cn.IdCondicion = cl.IdCondicion
        WHERE cl.IdCartera = @IdCartera
    )
    INSERT INTO #cond (DNI, Condicion)
    SELECT c.DNI, c.Condicion FROM c INNER JOIN #dni AS d ON d.DNI = c.DNI WHERE c.rn = 1;
    INSERT INTO @T VALUES ('condicion', @@ROWCOUNT, DATEDIFF(MILLISECOND, @t0, SYSDATETIME())); SET @t0 = SYSDATETIME();

    /* 2. Gestión humana: todo el mes y los CEF de 6 meses (hasta ayer). DNI de la gestión; si viene vacío,
          el del cliente (misma regla de score.sp_CargarTelefonoDia y de Analytics). */
    CREATE TABLE #gh (
        IdGestion   INT           NOT NULL,
        DNI         VARCHAR(20)   COLLATE DATABASE_DEFAULT NOT NULL,
        Momento     DATETIME2(0)  NOT NULL,
        IdIndicador INT           NULL,
        Tipo        VARCHAR(10)   COLLATE DATABASE_DEFAULT NOT NULL,
        Rango       TINYINT       NOT NULL,     -- 1 CEF · 2 CNE · 3 NOC · 4 sin tipo
        Indicador   NVARCHAR(200) COLLATE DATABASE_DEFAULT NOT NULL
    );
    -- 2a. Candidatas con el índice de siscob (Fecha, idCartera), que ya trae IdGestion, IdCliente, IdIndicador y DNI:
    --     todo el mes y, de antes, las que pueden ser CEF (indicador CEF o sin tipo de contacto en el indicador).
    CREATE TABLE #cand (IdGestion INT NOT NULL PRIMARY KEY, IdCliente INT NULL, DNI VARCHAR(40) COLLATE DATABASE_DEFAULT NULL,
                        IdIndicador INT NULL, TipoIndicador VARCHAR(10) COLLATE DATABASE_DEFAULT NULL,
                        Indicador NVARCHAR(200) COLLATE DATABASE_DEFAULT NULL);
    INSERT INTO #cand (IdGestion, IdCliente, DNI, IdIndicador, TipoIndicador, Indicador)
    SELECT g.IdGestion, g.IdCliente, LEFT(LTRIM(RTRIM(g.DNI)), 40), g.IdIndicador,
           LEFT(LTRIM(RTRIM(i.TipoContacto)), 10), CONVERT(NVARCHAR(200), LTRIM(RTRIM(i.DescripcionIndicador)))
    FROM siscob.dbo.gestion AS g WITH (NOLOCK)
    LEFT JOIN siscob.dbo.Indicador AS i WITH (NOLOCK) ON i.IdIndicador = g.IdIndicador
    WHERE g.Fecha >= @Ini6 AND g.Fecha < @Hoy AND g.idCartera = @IdCartera
      AND (g.Fecha >= @IniMes OR ISNULL(LTRIM(RTRIM(i.TipoContacto)), '') NOT IN ('CNE', 'NOC'))
    OPTION (RECOMPILE);

    -- 2b. Hora y tipo de contacto de la gestión solo para las candidatas (búsqueda por la llave)
    INSERT INTO #gh (IdGestion, DNI, Momento, IdIndicador, Tipo, Rango, Indicador)
    SELECT k.IdGestion, x.DNI,
           CAST(CAST(CAST(g.Fecha AS DATE) AS DATETIME) + CAST(ISNULL(CAST(g.Hora AS TIME(0)), CAST('00:00' AS TIME(0))) AS DATETIME) AS DATETIME2(0)),
           k.IdIndicador, t.Tipo,
           CASE t.Tipo WHEN 'CEF' THEN 1 WHEN 'CNE' THEN 2 WHEN 'NOC' THEN 3 ELSE 4 END,
           CONVERT(NVARCHAR(200), t.Tipo + N' · ' + COALESCE(NULLIF(k.Indicador, N''),
                                                            N'Indicador ' + CONVERT(NVARCHAR(12), k.IdIndicador), N'Sin indicador'))
    FROM #cand AS k
    INNER JOIN siscob.dbo.gestion AS g WITH (NOLOCK) ON g.IdGestion = k.IdGestion
    LEFT JOIN siscob.dbo.Cliente AS c WITH (NOLOCK) ON c.IdCliente = k.IdCliente
    CROSS APPLY (SELECT CONVERT(VARCHAR(20), LEFT(LTRIM(RTRIM(ISNULL(COALESCE(NULLIF(k.DNI, ''), c.Dni), ''))), 20))
                        COLLATE DATABASE_DEFAULT AS DNI) AS x
    CROSS APPLY (SELECT CASE WHEN k.TipoIndicador IN ('CEF', 'CNE', 'NOC') THEN k.TipoIndicador
                             WHEN g.TipoContacto = 1 THEN 'CEF'
                             ELSE 'SIN_TIPO' END COLLATE DATABASE_DEFAULT AS Tipo) AS t
    WHERE (g.Fecha >= @IniMes OR t.Tipo = 'CEF')
      AND EXISTS (SELECT 1 FROM #dni AS d WHERE d.DNI = x.DNI)
    OPTION (RECOMPILE);
    INSERT INTO @T VALUES ('gestion_humana', @@ROWCOUNT, DATEDIFF(MILLISECOND, @t0, SYSDATETIME())); SET @t0 = SYSDATETIME();
    CREATE CLUSTERED INDEX IX_gh ON #gh (DNI, Momento);

    /* 3. Días del mes con gestión: humana (gestion) + máquina y centralita (score.TelefonoDia) */
    CREATE TABLE #dia (DNI VARCHAR(20) COLLATE DATABASE_DEFAULT NOT NULL, Dia DATE NOT NULL);
    INSERT INTO #dia (DNI, Dia)
    SELECT DNI, CAST(Momento AS DATE) FROM #gh WHERE Momento >= @IniMes
    UNION
    SELECT td.DNI, td.Fecha
    FROM score.TelefonoDia AS td
    WHERE td.IdCartera = @IdCartera AND td.Fecha >= @IniMes AND td.Fecha < @Hoy
      AND (td.IntentosMaquina > 0 OR td.LlamadasCentralita > 0 OR td.IntentosHumano > 0)
      AND EXISTS (SELECT 1 FROM #dni AS d WHERE d.DNI = td.DNI)
    OPTION (RECOMPILE);
    INSERT INTO @T VALUES ('dias_gestion', @@ROWCOUNT, DATEDIFF(MILLISECOND, @t0, SYSDATETIME())); SET @t0 = SYSDATETIME();
    CREATE CLUSTERED INDEX IX_dia ON #dia (DNI, Dia);

    /* 4. PDP: la última generada en el mes (monto > 0), por la gestión que la registró */
    CREATE TABLE #pdp (DNI VARCHAR(20) COLLATE DATABASE_DEFAULT NOT NULL PRIMARY KEY,
                       EstadoPdp NVARCHAR(10) NOT NULL, FechaCompromiso DATE NULL);
    ;WITH p AS (
        SELECT h.DNI, CAST(cp.FechaCompromiso AS DATE) AS FechaCompromiso,
               UPPER(LTRIM(RTRIM(ISNULL(CONVERT(VARCHAR(10), cp.Pagado), '')))) AS Pagado,
               ROW_NUMBER() OVER (PARTITION BY h.DNI ORDER BY h.Momento DESC, cp.IdCompromiso DESC) AS rn
        FROM siscob.dbo.COMPROMISO AS cp WITH (NOLOCK)
        INNER JOIN #gh AS h ON h.IdGestion = cp.IdGestion
        WHERE h.Momento >= @IniMes AND cp.Monto > 0
    )
    INSERT INTO #pdp (DNI, EstadoPdp, FechaCompromiso)
    SELECT DNI,
           CASE WHEN Pagado IN ('SI', 'S') THEN N'PAGADA'
                WHEN FechaCompromiso IS NULL THEN N'SIN FECHA'
                WHEN FechaCompromiso >= @Hoy THEN N'VIGENTE'
                ELSE N'CAÍDA' END,
           FechaCompromiso
    FROM p WHERE rn = 1;
    INSERT INTO @T VALUES ('pdp', @@ROWCOUNT, DATEDIFF(MILLISECOND, @t0, SYSDATETIME())); SET @t0 = SYSDATETIME();

    /* 5. Seguimiento (fase 11, Hardy 17/11/2026). Último seguimiento del cliente con los indicadores de
          seguimiento / negociación / volver a llamar de SU cartera (Biznescob_Analytics.dbo.CFG_SEGUIMIENTO_INDICADOR,
          la misma lista de la bolsa de seguimientos de Analytics). Toda la historia: se guarda en
          score.SeguimientoCliente y cada vez solo se leen los últimos días (la primera vez, desde 2022).
          Tope = fecha del último seguimiento + días hábiles (lunes a sábado) según el día del mes del seguimiento
          (score.SeguimientoPlazo: del 1 al 19 → 3; del 20 en adelante → 1, como la vista anterior de MiBanco). Una PDP generada
          después del último seguimiento lo corta: PDP VIGENTE / PDP CAÍDA / PDP PAGADA / PDP SIN FECHA según la última. El estado (VIGENTE / HOY / CAÍDO) lo calcula la vista
          con la fecha del día, para que no envejezca entre una actualización y otra. */
    IF @DiasSeguimiento IS NOT NULL AND (@DiasSeguimiento < 1 OR @DiasSeguimiento > 15)
        THROW 50702, '@DiasSeguimiento debe estar entre 1 y 15.', 1;
    DECLARE @LeidoHasta DATE = (SELECT LeidoHasta FROM score.SeguimientoLectura WHERE IdCartera = @IdCartera);
    DECLARE @DesdeSeg DATE = CASE WHEN @LeidoHasta IS NULL THEN '20220101' ELSE DATEADD(DAY, -7, @LeidoHasta) END;
    CREATE TABLE #tseg (DNI VARCHAR(20) COLLATE DATABASE_DEFAULT NOT NULL, Momento DATETIME2(0) NOT NULL, IdGestion INT NOT NULL);
    BEGIN TRY
        -- 5a. Toques de seguimiento nuevos (por el índice de siscob (Fecha, idCartera) + llave para la hora)
        CREATE TABLE #cseg (IdGestion INT NOT NULL PRIMARY KEY, IdCliente INT NULL, DNI VARCHAR(40) COLLATE DATABASE_DEFAULT NULL);
        INSERT INTO #cseg (IdGestion, IdCliente, DNI)
        SELECT g.IdGestion, g.IdCliente, LEFT(LTRIM(RTRIM(g.DNI)), 40)
        FROM siscob.dbo.gestion AS g WITH (NOLOCK)
        INNER JOIN Biznescob_Analytics.dbo.CFG_SEGUIMIENTO_INDICADOR AS f
                ON f.IDCARTERA = @IdCartera AND f.IDINDICADOR = g.IdIndicador AND f.ESTADO = 'A'
        WHERE g.Fecha >= @DesdeSeg AND g.Fecha < @Hoy AND g.idCartera = @IdCartera
        OPTION (RECOMPILE);
        INSERT INTO #tseg (DNI, Momento, IdGestion)
        SELECT x.DNI,
               CAST(CAST(CAST(g.Fecha AS DATE) AS DATETIME) + CAST(ISNULL(CAST(g.Hora AS TIME(0)), CAST('00:00' AS TIME(0))) AS DATETIME) AS DATETIME2(0)),
               k.IdGestion
        FROM #cseg AS k
        INNER JOIN siscob.dbo.gestion AS g WITH (NOLOCK) ON g.IdGestion = k.IdGestion
        LEFT JOIN siscob.dbo.Cliente AS c WITH (NOLOCK) ON c.IdCliente = k.IdCliente
        CROSS APPLY (SELECT CONVERT(VARCHAR(20), LEFT(LTRIM(RTRIM(ISNULL(COALESCE(NULLIF(k.DNI, ''), c.Dni), ''))), 20))
                            COLLATE DATABASE_DEFAULT AS DNI) AS x
        WHERE x.DNI <> ''
        OPTION (RECOMPILE);
    END TRY
    BEGIN CATCH
        SET @Aviso = LEFT(N'No se leyeron los seguimientos nuevos (se usa lo guardado): ' + ERROR_MESSAGE(), 1000);
        TRUNCATE TABLE #tseg;
        SET @LeidoHasta = NULL;      -- no se marca como leído
    END CATCH;
    INSERT INTO @T VALUES ('seguimiento_lectura', (SELECT COUNT(*) FROM #tseg), DATEDIFF(MILLISECOND, @t0, SYSDATETIME())); SET @t0 = SYSDATETIME();

    -- 5b. Último seguimiento por cliente: lo guardado + lo nuevo
    CREATE TABLE #segult (DNI VARCHAR(20) COLLATE DATABASE_DEFAULT NOT NULL PRIMARY KEY, UltSeguimiento DATETIME2(0) NOT NULL,
                          IdGestion INT NOT NULL, ToquesNuevos INT NOT NULL);
    ;WITH todo AS (
        SELECT DNI, UltSeguimiento AS Momento, IdGestion, 0 AS Nuevo FROM score.SeguimientoCliente WHERE IdCartera = @IdCartera
        UNION ALL
        SELECT DNI, Momento, IdGestion, 1 FROM #tseg
    ), r AS (
        SELECT DNI, Momento, IdGestion, SUM(Nuevo) OVER (PARTITION BY DNI) AS ToquesNuevos,
               ROW_NUMBER() OVER (PARTITION BY DNI ORDER BY Momento DESC, IdGestion DESC) AS rn
        FROM todo
    )
    INSERT INTO #segult (DNI, UltSeguimiento, IdGestion, ToquesNuevos)
    SELECT DNI, Momento, IdGestion, ToquesNuevos FROM r WHERE rn = 1;

    -- 5c. Clientes de la cartera hoy: tope en días hábiles y PDP generada después del último seguimiento
    CREATE TABLE #seg (DNI VARCHAR(20) COLLATE DATABASE_DEFAULT NOT NULL PRIMARY KEY,
                       FechaSeguimiento DATE NOT NULL, UltSeguimiento DATETIME2(0) NOT NULL, FechaLimite DATE NOT NULL,
                       PdpPosterior BIT NOT NULL DEFAULT (0), PdpFechaCompromiso DATE NULL, PdpPagada BIT NULL,
                       EstadoSeguimiento NVARCHAR(60) NULL);
    INSERT INTO #seg (DNI, FechaSeguimiento, UltSeguimiento, FechaLimite)
    SELECT s.DNI, CAST(s.UltSeguimiento AS DATE), s.UltSeguimiento, h.Fecha
    FROM #segult AS s
    INNER JOIN #dni AS d ON d.DNI = s.DNI
    CROSS APPLY (SELECT ISNULL(@DiasSeguimiento,
                               ISNULL((SELECT TOP (1) z.DiasHabiles FROM score.SeguimientoPlazo AS z
                                       WHERE DAY(s.UltSeguimiento) BETWEEN z.DiaDesde AND z.DiaHasta
                                       ORDER BY z.DiaDesde), 3)) AS Dias) AS pz
    CROSS APPLY score.fn_SumarDiasHabiles(CAST(s.UltSeguimiento AS DATE), pz.Dias) AS h;

    CREATE TABLE #segcli (IdCliente INT NOT NULL PRIMARY KEY, DNI VARCHAR(20) COLLATE DATABASE_DEFAULT NOT NULL);
    INSERT INTO #segcli (IdCliente, DNI)
    SELECT cl.IdCliente, s.DNI
    FROM siscob.dbo.Cliente AS cl WITH (NOLOCK)
    INNER JOIN #seg AS s ON s.DNI = CONVERT(VARCHAR(20), LEFT(LTRIM(RTRIM(cl.Dni)), 20)) COLLATE DATABASE_DEFAULT
    WHERE cl.IdCartera = @IdCartera;
    -- La última PDP (monto > 0) generada después del último seguimiento: su fecha de compromiso y si se pagó
    UPDATE s SET PdpPosterior = 1, PdpFechaCompromiso = p.FechaCompromiso, PdpPagada = p.Pagada
    FROM #seg AS s
    CROSS APPLY (SELECT TOP (1) CAST(cp.FechaCompromiso AS DATE) AS FechaCompromiso,
                        CONVERT(BIT, CASE WHEN UPPER(LTRIM(RTRIM(ISNULL(CONVERT(VARCHAR(10), cp.Pagado), '')))) IN ('SI', 'S')
                                          THEN 1 ELSE 0 END) AS Pagada
                 FROM #segcli AS k
                 INNER JOIN siscob.dbo.COMPROMISO AS cp WITH (NOLOCK) ON cp.IdCliente = k.IdCliente
                 WHERE k.DNI = s.DNI AND cp.Monto > 0
                   AND cp.FechaGenero >= s.UltSeguimiento AND cp.FechaGenero < @Hoy
                 ORDER BY cp.FechaGenero DESC, cp.IdCompromiso DESC) AS p;
    -- Estado a la fecha del armado (para la simulación; la vista lo recalcula cada día con la misma regla)
    UPDATE #seg SET EstadoSeguimiento = CASE WHEN PdpPosterior = 1 THEN
                                                  CASE WHEN PdpPagada = 1 THEN N'PDP PAGADA'
                                                       WHEN PdpFechaCompromiso IS NULL THEN N'PDP SIN FECHA'
                                                       WHEN PdpFechaCompromiso >= @Hoy THEN N'PDP VIGENTE'
                                                       ELSE N'PDP CAÍDA' END
                                             WHEN @Hoy < FechaLimite THEN N'VIGENTE'
                                             WHEN @Hoy = FechaLimite THEN N'HOY'
                                             ELSE N'CAÍDO' END;
    INSERT INTO @T VALUES ('seguimiento', (SELECT COUNT(*) FROM #seg), DATEDIFF(MILLISECOND, @t0, SYSDATETIME())); SET @t0 = SYSDATETIME();

    /* 6. Una fila por cliente */
    CREATE TABLE #gc (
        DNI VARCHAR(20) COLLATE DATABASE_DEFAULT NOT NULL PRIMARY KEY,
        Condicion NVARCHAR(100) NULL,
        MgContacto VARCHAR(10) NOT NULL, MgIndicador NVARCHAR(200) NOT NULL, MgFecha DATETIME2(0) NULL, MgFechaTramo NVARCHAR(40) NOT NULL,
        UgContacto VARCHAR(10) NOT NULL, UgIndicador NVARCHAR(200) NOT NULL, UgFecha DATETIME2(0) NULL, UgFechaTramo NVARCHAR(40) NOT NULL,
        Cobertura BIT NOT NULL, Frecuencia SMALLINT NOT NULL, FrecuenciaHumana SMALLINT NOT NULL, GestionesHumanas INT NOT NULL,
        EstadoPdp NVARCHAR(10) NOT NULL, FechaCompromiso DATE NULL,
        UltCefFecha DATETIME2(0) NULL, UltCefTramo NVARCHAR(40) NOT NULL,
        EstadoSeguimiento NVARCHAR(60) NULL, FechaSeguimiento DATE NULL,
        FechaLimiteSeguimiento DATE NULL, PdpTrasSeguimiento BIT NULL,
        PdpTrasFechaCompromiso DATE NULL, PdpTrasPagada BIT NULL);
    INSERT INTO #gc
    SELECT d.DNI, co.Condicion,
           ISNULL(mg.Tipo, 'SG'), ISNULL(mg.Indicador, N'SG'), mg.Momento, tmg.Tramo,
           ISNULL(ug.Tipo, 'SG'), ISNULL(ug.Indicador, N'SG'), ug.Momento, tug.Tramo,
           CASE WHEN ISNULL(fr.Dias, 0) > 0 THEN 1 ELSE 0 END, ISNULL(fr.Dias, 0),
           ISNULL(hh.Dias, 0), ISNULL(hh.Gestiones, 0),
           ISNULL(p.EstadoPdp, N'SIN PDP'), p.FechaCompromiso,
           cef.UltCef, tcef.Tramo,
           ISNULL(s.EstadoSeguimiento, N'SIN SEG'), s.FechaSeguimiento, s.FechaLimite, s.PdpPosterior,
           s.PdpFechaCompromiso, s.PdpPagada
    FROM #dni AS d
    LEFT JOIN #cond AS co ON co.DNI = d.DNI
    LEFT JOIN #pdp AS p ON p.DNI = d.DNI
    LEFT JOIN #seg AS s ON s.DNI = d.DNI
    OUTER APPLY (SELECT TOP (1) h.Tipo, h.Indicador, h.Momento FROM #gh AS h
                 WHERE h.DNI = d.DNI AND h.Momento >= @IniMes
                 ORDER BY h.Rango, ISNULL(h.IdIndicador, 2147483647), h.Momento DESC, h.IdGestion DESC) AS mg
    OUTER APPLY (SELECT TOP (1) h.Tipo, h.Indicador, h.Momento FROM #gh AS h
                 WHERE h.DNI = d.DNI AND h.Momento >= @IniMes
                 ORDER BY h.Momento DESC, h.IdGestion DESC) AS ug
    OUTER APPLY (SELECT MAX(h.Momento) AS UltCef FROM #gh AS h WHERE h.DNI = d.DNI AND h.Tipo = 'CEF') AS cef
    OUTER APPLY (SELECT COUNT(*) AS Gestiones, COUNT(DISTINCT CAST(h.Momento AS DATE)) AS Dias FROM #gh AS h
                 WHERE h.DNI = d.DNI AND h.Momento >= @IniMes) AS hh
    OUTER APPLY (SELECT COUNT(*) AS Dias FROM #dia AS x WHERE x.DNI = d.DNI) AS fr
    CROSS APPLY score.fn_TramoFecha(CAST(mg.Momento AS DATE), @IniMes, N'Sin gestión humana en el mes') AS tmg
    CROSS APPLY score.fn_TramoFecha(CAST(ug.Momento AS DATE), @IniMes, N'Sin gestión humana en el mes') AS tug
    CROSS APPLY score.fn_TramoFecha(CAST(cef.UltCef AS DATE), @IniMes, N'Sin CEF en 6 meses') AS tcef;
    INSERT INTO @T VALUES ('clientes', @@ROWCOUNT, DATEDIFF(MILLISECOND, @t0, SYSDATETIME())); SET @t0 = SYSDATETIME();

    /* 7. Una fila por teléfono (6 meses de score.TelefonoDia). Mejor = menor Orden de score.ResultadoTelefono;
          último = último resultado CON información (se saltan los intentos de máquina sin resultado; si el último
          evento del día no tiene resultado, se usa el mejor resultado de ese día). Solo intentos sin resultado =
          SIN_INFORMACION. La fecha de la última gestión sí cuenta cualquier intento. */
    CREATE TABLE #gt (
        DNI VARCHAR(20) COLLATE DATABASE_DEFAULT NOT NULL, Telefono CHAR(9) COLLATE DATABASE_DEFAULT NOT NULL,
        MgTelMes VARCHAR(20) NOT NULL, UgTelMes VARCHAR(20) NOT NULL, MgTel6m VARCHAR(20) NOT NULL, UgTel6m VARCHAR(20) NOT NULL,
        UltGestionTel DATETIME2(0) NULL, UltGestionTelTramo NVARCHAR(40) NOT NULL,
        GestionesTelMes INT NOT NULL, GestionesTel6m INT NOT NULL, EquivocadosTel6m INT NOT NULL,
        PRIMARY KEY (DNI, Telefono));
    ;WITH a AS (
        SELECT td.DNI, td.Telefono,
               SUM(CASE WHEN td.Fecha >= @IniMes THEN 1 ELSE 0 END) AS DiasMes,
               SUM(CASE WHEN td.Fecha >= @IniMes THEN td.IntentosHumano + td.IntentosMaquina + td.LlamadasCentralita ELSE 0 END) AS GestionesMes,
               SUM(td.IntentosHumano + td.IntentosMaquina + td.LlamadasCentralita) AS Gestiones6m,
               SUM(td.N_EQUIVOCADO) AS Equivocados6m,
               MIN(CASE WHEN td.Fecha >= @IniMes THEN rt.Orden END) AS MgOrdenMes,
               MIN(rt.Orden) AS MgOrden6m,
               MAX(CASE WHEN td.Fecha >= @IniMes THEN u.Dato END) AS UgMes,
               MAX(u.Dato) AS Ug6m,
               MAX(CONVERT(CHAR(19), ISNULL(td.UltimoEvento, CAST(td.Fecha AS DATETIME2(0))), 120)) AS Ult6m
        FROM score.TelefonoDia AS td
        LEFT JOIN score.ResultadoTelefono AS rt ON rt.Codigo = td.MejorResultado
        CROSS APPLY (SELECT CASE WHEN td.UltimoResultado IS NOT NULL AND td.UltimoResultado <> 'SIN_INFORMACION'
                                 THEN CONVERT(CHAR(19), ISNULL(td.UltimoEvento, CAST(td.Fecha AS DATETIME2(0))), 120) + td.UltimoResultado
                                 WHEN td.MejorResultado IS NOT NULL AND td.MejorResultado <> 'SIN_INFORMACION'
                                 THEN CONVERT(CHAR(19), ISNULL(td.MomentoMejor, CAST(td.Fecha AS DATETIME2(0))), 120) + td.MejorResultado
                            END AS Dato) AS u
        WHERE td.IdCartera = @IdCartera AND td.Fecha >= @Ini6 AND td.Fecha < @Hoy
        GROUP BY td.DNI, td.Telefono
    )
    INSERT INTO #gt
    SELECT t.DNI, t.Telefono,
           CASE WHEN ISNULL(a.DiasMes, 0) = 0 THEN 'SIN_GESTION' ELSE ISNULL(rm.Codigo, 'SIN_INFORMACION') END,
           CASE WHEN ISNULL(a.DiasMes, 0) = 0 THEN 'SIN_GESTION' ELSE ISNULL(SUBSTRING(a.UgMes, 20, 20), 'SIN_INFORMACION') END,
           CASE WHEN a.DNI IS NULL THEN 'SIN_GESTION' ELSE ISNULL(r6.Codigo, 'SIN_INFORMACION') END,
           CASE WHEN a.DNI IS NULL THEN 'SIN_GESTION' ELSE ISNULL(SUBSTRING(a.Ug6m, 20, 20), 'SIN_INFORMACION') END,
           TRY_CONVERT(DATETIME2(0), a.Ult6m, 120), tf.Tramo,
           ISNULL(a.GestionesMes, 0), ISNULL(a.Gestiones6m, 0), ISNULL(a.Equivocados6m, 0)
    FROM #tel AS t
    LEFT JOIN a ON a.DNI = t.DNI AND a.Telefono = t.Telefono
    OUTER APPLY (SELECT TOP (1) r.Codigo FROM score.ResultadoTelefono AS r WHERE r.Orden = a.MgOrdenMes ORDER BY r.Codigo) AS rm
    OUTER APPLY (SELECT TOP (1) r.Codigo FROM score.ResultadoTelefono AS r WHERE r.Orden = a.MgOrden6m ORDER BY r.Codigo) AS r6
    CROSS APPLY score.fn_TramoFecha(CAST(TRY_CONVERT(DATETIME2(0), a.Ult6m, 120) AS DATE), @IniMes, N'Sin gestión en 6 meses') AS tf
    OPTION (RECOMPILE);
    INSERT INTO @T VALUES ('telefonos', @@ROWCOUNT, DATEDIFF(MILLISECOND, @t0, SYSDATETIME())); SET @t0 = SYSDATETIME();

    /* 8. Simulación: distribuciones para revisar antes de guardar */
    IF @Simular = 1
    BEGIN
        SELECT 'SIMULACION' AS Resultado, @IdCartera AS IdCartera, @IniMes AS MesDesde, @Ayer AS DatosHasta, @Ini6 AS Historial6mDesde,
               (SELECT COUNT(*) FROM #gc) AS Clientes, (SELECT COUNT(*) FROM #gt) AS Telefonos, @Aviso AS Aviso;
        SELECT 'Cliente' AS Nivel, x.Campo, x.Valor, COUNT(*) AS Cantidad
        FROM #gc AS g
        CROSS APPLY (VALUES ('Condicion', CONVERT(NVARCHAR(200), g.Condicion)), ('MgContacto', CONVERT(NVARCHAR(200), g.MgContacto)),
                            ('UgContacto', CONVERT(NVARCHAR(200), g.UgContacto)), ('Cobertura', CONVERT(NVARCHAR(200), g.Cobertura)),
                            ('EstadoPdp', CONVERT(NVARCHAR(200), g.EstadoPdp)), ('UltCefTramo', CONVERT(NVARCHAR(200), g.UltCefTramo)),
                            ('EstadoSeguimiento', CONVERT(NVARCHAR(200), g.EstadoSeguimiento))) AS x (Campo, Valor)
        GROUP BY x.Campo, x.Valor
        UNION ALL
        SELECT 'Telefono', x.Campo, x.Valor, COUNT(*)
        FROM #gt AS g
        CROSS APPLY (VALUES ('MgTelMes', CONVERT(NVARCHAR(200), g.MgTelMes)), ('MgTel6m', CONVERT(NVARCHAR(200), g.MgTel6m)),
                            ('UgTel6m', CONVERT(NVARCHAR(200), g.UgTel6m)), ('UltGestionTelTramo', CONVERT(NVARCHAR(200), g.UltGestionTelTramo))) AS x (Campo, Valor)
        GROUP BY x.Campo, x.Valor
        ORDER BY 1, 2, 4 DESC;
        SELECT 'Seguimiento' AS Detalle, @DesdeSeg AS LeidoDesde, @Ayer AS LeidoHasta,
               (SELECT COUNT(*) FROM #tseg) AS ToquesLeidos, (SELECT COUNT(*) FROM #segult) AS ClientesConSeguimientoHistoria,
               (SELECT COUNT(*) FROM #seg) AS ClientesConSeguimientoEnCartera,
               (SELECT MIN(FechaSeguimiento) FROM #seg) AS SeguimientoMasAntiguo, (SELECT MAX(FechaSeguimiento) FROM #seg) AS SeguimientoMasReciente;
        SELECT 'Seguimiento por fecha' AS Detalle, FechaSeguimiento, FechaLimite, EstadoSeguimiento, COUNT(*) AS Clientes
        FROM #seg WHERE FechaSeguimiento >= DATEADD(DAY, -15, @Hoy)
        GROUP BY FechaSeguimiento, FechaLimite, EstadoSeguimiento ORDER BY FechaSeguimiento DESC;
        SELECT 'Malla (top 40)' AS Detalle, MgIndicador, COUNT(*) AS Clientes
        FROM #gc GROUP BY MgIndicador ORDER BY COUNT(*) DESC OFFSET 0 ROWS FETCH NEXT 40 ROWS ONLY;
        SELECT 'Numéricos' AS Detalle, AVG(CAST(Frecuencia AS DECIMAL(9, 2))) AS FrecuenciaProm, MAX(Frecuencia) AS FrecuenciaMax,
               AVG(CAST(FrecuenciaHumana AS DECIMAL(9, 2))) AS FrecHumanaProm, SUM(GestionesHumanas) AS GestionesHumanas
        FROM #gc;
        SELECT Seccion, Filas, Ms FROM @T ORDER BY Orden;
        RETURN 0;
    END;

    /* 9. Guardar (reemplaza la cartera). Sin resultados: el que llama lee solo la bitácora. */
    BEGIN TRANSACTION;
        DELETE FROM score.GestionCliente WHERE IdCartera = @IdCartera;
        INSERT INTO score.GestionCliente (IdCartera, DNI, Condicion, MgContacto, MgIndicador, MgFecha, MgFechaTramo,
               UgContacto, UgIndicador, UgFecha, UgFechaTramo, Cobertura, Frecuencia, FrecuenciaHumana, GestionesHumanas,
               EstadoPdp, FechaCompromiso, UltCefFecha, UltCefTramo, EstadoSeguimiento, FechaSeguimiento,
               FechaLimiteSeguimiento, PdpTrasSeguimiento, PdpTrasFechaCompromiso, PdpTrasPagada, DatosHasta, FechaArmado)
        SELECT @IdCartera, DNI, Condicion, MgContacto, MgIndicador, MgFecha, MgFechaTramo,
               UgContacto, UgIndicador, UgFecha, UgFechaTramo, Cobertura, Frecuencia, FrecuenciaHumana, GestionesHumanas,
               EstadoPdp, FechaCompromiso, UltCefFecha, UltCefTramo, EstadoSeguimiento, FechaSeguimiento,
               FechaLimiteSeguimiento, PdpTrasSeguimiento, PdpTrasFechaCompromiso, PdpTrasPagada, @Ayer, @Ahora
        FROM #gc;

        -- Historia de seguimientos: solo crece (el último de cada cliente) y se marca hasta dónde se leyó
        MERGE score.SeguimientoCliente AS t
        USING (SELECT DNI, UltSeguimiento, IdGestion FROM #segult WHERE ToquesNuevos > 0) AS s
        ON t.IdCartera = @IdCartera AND t.DNI = s.DNI
        WHEN MATCHED AND s.UltSeguimiento > t.UltSeguimiento
            THEN UPDATE SET UltSeguimiento = s.UltSeguimiento, IdGestion = s.IdGestion, Actualizado = @Ahora
        WHEN NOT MATCHED
            THEN INSERT (IdCartera, DNI, UltSeguimiento, IdGestion, Actualizado) VALUES (@IdCartera, s.DNI, s.UltSeguimiento, s.IdGestion, @Ahora);
        IF @Aviso IS NULL OR @Aviso NOT LIKE N'No se leyeron los seguimientos%'
            MERGE score.SeguimientoLectura AS t
            USING (SELECT @IdCartera AS IdCartera) AS s ON t.IdCartera = s.IdCartera
            WHEN MATCHED THEN UPDATE SET LeidoHasta = @Ayer, Actualizado = @Ahora
            WHEN NOT MATCHED THEN INSERT (IdCartera, LeidoHasta, Actualizado) VALUES (@IdCartera, @Ayer, @Ahora);

        DELETE FROM score.GestionTelefono WHERE IdCartera = @IdCartera;
        INSERT INTO score.GestionTelefono (IdCartera, DNI, Telefono, MgTelMes, UgTelMes, MgTel6m, UgTel6m,
               UltGestionTel, UltGestionTelTramo, GestionesTelMes, GestionesTel6m, EquivocadosTel6m, DatosHasta, FechaArmado)
        SELECT @IdCartera, DNI, Telefono, MgTelMes, UgTelMes, MgTel6m, UgTel6m,
               UltGestionTel, UltGestionTelTramo, GestionesTelMes, GestionesTel6m, EquivocadosTel6m, @Ayer, @Ahora
        FROM #gt;
    COMMIT TRANSACTION;
    RETURN 0;
END;
GO

/* =====================================================================================
   BLOQUE 2 · Vista de trabajo: igual a la fase 7 salvo EstadoSeguimiento
   ===================================================================================== */
CREATE OR ALTER VIEW score.vw_BaseTrabajo
AS
WITH ult AS (
    SELECT IdCartera, MAX(FechaCorte) AS FechaCorte FROM score.TelefonoScore GROUP BY IdCartera
)
SELECT s.IdCartera, s.DNI, s.Telefono, s.FechaCorte AS FechaScore, s.Version,
       s.Score, s.Tramo, s.OrdenCliente, s.Descartado, s.MotivoDescarte,
       s.Razon1, s.Razon2, s.Razon3, s.Razon_Resta,
       u.IdCliente, u.PrioridadColor, u.Osiptel, u.Whatsapp, u.Timbra, u.Operador, u.EsEmpresa,
       u.N_DNI_Comparten, u.AnioMesDato, u.OrigenTexto, u.ObservacionTexto,
       c.FechaCorteFuente, c.Capital, c.RangoCapital, c.Cuentas, c.Meta,
       c.GestionesHumanasMes, c.GestionesMaquinaMes, c.ContactoDirectoMes, c.FechaUltimoCef, c.PdpGeneradasMes,
       -- fase 7 · gestión del cliente (score.GestionCliente)
       gc.Condicion, gc.MgContacto, gc.MgIndicador, gc.MgFechaTramo, gc.UgContacto, gc.UgIndicador, gc.UgFechaTramo,
       gc.Cobertura, gc.Frecuencia, gc.FrecuenciaHumana, gc.GestionesHumanas AS GestionesHumanasSiscob,
       gc.EstadoPdp, gc.UltCefTramo,
       -- fase 11 · estado de seguimiento calculado con la fecha de hoy (no envejece entre actualizaciones)
       CONVERT(NVARCHAR(60), CASE WHEN gc.DNI IS NULL THEN NULL
                                  WHEN gc.FechaLimiteSeguimiento IS NULL THEN N'SIN SEG'
                                  WHEN gc.PdpTrasSeguimiento = 1 THEN
                                       CASE WHEN gc.PdpTrasPagada = 1 THEN N'PDP PAGADA'
                                            WHEN gc.PdpTrasFechaCompromiso IS NULL THEN N'PDP SIN FECHA'
                                            WHEN gc.PdpTrasFechaCompromiso >= CAST(GETDATE() AS DATE) THEN N'PDP VIGENTE'
                                            ELSE N'PDP CAÍDA' END
                                  WHEN CAST(GETDATE() AS DATE) < gc.FechaLimiteSeguimiento THEN N'VIGENTE'
                                  WHEN CAST(GETDATE() AS DATE) = gc.FechaLimiteSeguimiento THEN N'HOY'
                                  ELSE N'CAÍDO' END) AS EstadoSeguimiento,
       gc.DatosHasta AS GestionHasta,
       -- fase 7 · gestión del teléfono (score.GestionTelefono)
       gt.MgTelMes, gt.UgTelMes, gt.MgTel6m, gt.UgTel6m, gt.UltGestionTelTramo,
       gt.GestionesTelMes, gt.GestionesTel6m, gt.EquivocadosTel6m,
       -- fase 7 · tramos del teléfono del score del día (score.Caracteristicas)
       k.S_ORIGEN AS OrigenDato, k.S_FUENTE AS FuenteDato, k.S_ANTIG_DATO AS AntiguedadDato,
       k.S_TIPO_LINEA AS TipoLinea, k.S_RELACION AS Relacion,
       k.T_ULT_CEF AS TramoUltCefTel, k.T_TASA_CEF_90 AS TramoTasaCef90, k.T_INTENTOS_30 AS TramoIntentos30,
       k.T_ULT_INTENTO AS TramoUltIntento, k.T_MAQUINA_90 AS TramoNoConecta90
FROM score.TelefonoScore AS s
INNER JOIN ult ON ult.IdCartera = s.IdCartera AND ult.FechaCorte = s.FechaCorte
LEFT JOIN score.TelefonoUniverso AS u
       ON u.IdCartera = s.IdCartera AND u.DNI = s.DNI AND u.Telefono = s.Telefono
LEFT JOIN score.BaseTrabajoCliente AS c
       ON c.IdCartera = s.IdCartera AND c.DNI = s.DNI
LEFT JOIN score.GestionCliente AS gc
       ON gc.IdCartera = s.IdCartera AND gc.DNI = s.DNI
LEFT JOIN score.GestionTelefono AS gt
       ON gt.IdCartera = s.IdCartera AND gt.DNI = s.DNI AND gt.Telefono = s.Telefono
LEFT JOIN score.Caracteristicas AS k
       ON k.FechaCorte = s.FechaCorte AND k.Poblacion = 'UNIVERSO' AND k.IdCartera = s.IdCartera
      AND k.DNI = s.DNI AND k.Telefono = s.Telefono;
GO

/* =====================================================================================
   BLOQUE 3 · Catálogo: el campo de la 112 pasa a ser de todas las carteras
   ===================================================================================== */
UPDATE score.Campo
SET Etiqueta = N'Estado de seguimiento',
    OrdenValores = N'VIGENTE|HOY|CAÍDO|PDP VIGENTE|PDP CAÍDA|PDP PAGADA|PDP SIN FECHA|SIN SEG',
    Descripcion = N'Último seguimiento / negociación / volver a llamar + 3 días hábiles lun-sáb (1 si fue del día 20 en adelante). VIGENTE, HOY = día tope, CAÍDO = pasó el tope. PDP VIGENTE / CAÍDA / PAGADA / SIN FECHA = última PDP generada después del seguimiento. SIN SEG = nunca tuvo.',
    Fuente = N'score.GestionCliente + score.SeguimientoCliente ← siscob.dbo.gestion (indicadores de Biznescob_Analytics.dbo.CFG_SEGUIMIENTO_INDICADOR) + siscob.dbo.COMPROMISO',
    Actualizacion = N'Seguimientos hasta ayer en cada actualización; el estado se recalcula con la fecha de hoy',
    TodasLasCarteras = 1
WHERE Codigo = N'SEGUIMIENTO_ACTUAL';
IF NOT EXISTS (SELECT 1 FROM score.Campo WHERE Codigo = N'SEGUIMIENTO_ACTUAL')
    THROW 51102, 'No existe el campo SEGUIMIENTO_ACTUAL: ejecutar antes la fase 7.', 1;
DELETE FROM score.CampoCartera WHERE Campo = N'SEGUIMIENTO_ACTUAL';   -- ya no depende de la cartera
GO

/* =====================================================================================
   BLOQUE 4 · Prueba (ejecutar por partes)
   ===================================================================================== */
/* 4.0 · Lista de indicadores que cuentan como seguimiento, y candidatos por descripción que no están en la lista
SELECT CASE WHEN f.IDINDICADOR IS NOT NULL THEN 'EN LISTA' ELSE 'CANDIDATO' END AS Lista,
       f.IDCARTERA, f.GRUPO, i.IdIndicador, i.CodIndicador, i.DescripcionIndicador, i.TipoContacto
FROM siscob.dbo.Indicador AS i WITH (NOLOCK)
LEFT JOIN Biznescob_Analytics.dbo.CFG_SEGUIMIENTO_INDICADOR AS f ON f.IDINDICADOR = i.IdIndicador AND f.ESTADO = 'A'
WHERE f.IDINDICADOR IS NOT NULL
   OR i.DescripcionIndicador LIKE '%SEGUIM%' OR i.DescripcionIndicador LIKE '%NEGOCI%'
   OR i.DescripcionIndicador LIKE '%VOLVER%LLAM%' OR i.DescripcionIndicador LIKE '%REPROGRAM%'
ORDER BY Lista DESC, f.IDCARTERA, i.IdIndicador;
*/

/* 4.1 · Simular una cartera (no escribe). La primera vez lee los seguimientos desde 2022: anotar el tiempo
         de "seguimiento_lectura" en la última tabla.
DECLARE @Aviso NVARCHAR(1000);
EXEC score.sp_ArmarGestion @IdCartera = 126, @Simular = 1, @Aviso = @Aviso OUTPUT;
SELECT @Aviso AS Aviso;
*/

/* 4.2 · Armar en real todas las carteras (guarda la historia de seguimientos; la siguiente vez lee 7 días)
DECLARE @Id INT, @Aviso NVARCHAR(1000), @t DATETIME2(3);
DECLARE @R TABLE (IdCartera INT, Segundos INT, Aviso NVARCHAR(1000), Error NVARCHAR(2000));
DECLARE c CURSOR LOCAL FAST_FORWARD FOR SELECT DISTINCT IdCartera FROM score.GestionCliente ORDER BY IdCartera;
OPEN c; FETCH NEXT FROM c INTO @Id;
WHILE @@FETCH_STATUS = 0
BEGIN
    SET @t = SYSDATETIME(); SET @Aviso = NULL;
    BEGIN TRY
        EXEC score.sp_ArmarGestion @IdCartera = @Id, @Simular = 0, @Aviso = @Aviso OUTPUT;
        INSERT INTO @R VALUES (@Id, DATEDIFF(SECOND, @t, SYSDATETIME()), @Aviso, NULL);
    END TRY
    BEGIN CATCH
        INSERT INTO @R VALUES (@Id, DATEDIFF(SECOND, @t, SYSDATETIME()), @Aviso, ERROR_MESSAGE());
    END CATCH;
    FETCH NEXT FROM c INTO @Id;
END;
CLOSE c; DEALLOCATE c;
SELECT * FROM @R ORDER BY IdCartera;
*/

/* 4.3 · Control: clientes por estado y cartera, lectura guardada y una muestra de HOY / VIGENTE
SELECT IdCartera, EstadoSeguimiento, COUNT(DISTINCT DNI) AS Clientes
FROM score.vw_BaseTrabajo GROUP BY IdCartera, EstadoSeguimiento ORDER BY IdCartera, EstadoSeguimiento;

SELECT l.IdCartera, l.LeidoHasta, COUNT(s.DNI) AS ClientesConHistoria, MIN(s.UltSeguimiento) AS MasAntiguo,
       MAX(s.UltSeguimiento) AS MasReciente
FROM score.SeguimientoLectura AS l
LEFT JOIN score.SeguimientoCliente AS s ON s.IdCartera = l.IdCartera
GROUP BY l.IdCartera, l.LeidoHasta ORDER BY l.IdCartera;

SELECT TOP 30 g.IdCartera, g.DNI, g.FechaSeguimiento, g.FechaLimiteSeguimiento, g.PdpTrasSeguimiento,
       v.EstadoSeguimiento, g.EstadoPdp, g.MgIndicador
FROM score.GestionCliente AS g
CROSS APPLY (SELECT TOP 1 EstadoSeguimiento FROM score.vw_BaseTrabajo AS b
             WHERE b.IdCartera = g.IdCartera AND b.DNI = g.DNI) AS v
WHERE v.EstadoSeguimiento IN (N'HOY', N'VIGENTE')
ORDER BY g.FechaLimiteSeguimiento, g.IdCartera;
*/

/* 4.4 · Comparación en la 112 con la vista que se usaba (MiBanco_Cobranzas.dbo.VW_SEGUIMIENTOS, la regla anterior).
         Las diferencias se revisan caso por caso antes de dar por buena la regla nueva.
;WITH viejo AS (
    SELECT CONVERT(VARCHAR(20), LEFT(LTRIM(RTRIM(CONVERT(NVARCHAR(40), s.DNI))), 20)) AS DNI,
           MAX(NULLIF(LTRIM(RTRIM(CONVERT(NVARCHAR(60), s.ESTADO))), N'')) AS EstadoVista, MAX(TRY_CONVERT(DATE, s.FECHA)) AS FechaVista
    FROM MiBanco_Cobranzas.dbo.VW_SEGUIMIENTOS AS s GROUP BY LEFT(LTRIM(RTRIM(CONVERT(NVARCHAR(40), s.DNI))), 20)
), nuevo AS (
    SELECT DISTINCT b.DNI, b.EstadoSeguimiento FROM score.vw_BaseTrabajo AS b WHERE b.IdCartera = 112
)
SELECT ISNULL(v.EstadoVista, N'(no está en la vista)') AS EstadoVista, n.EstadoSeguimiento AS EstadoNuevo, COUNT(*) AS Clientes
FROM nuevo AS n LEFT JOIN viejo AS v ON v.DNI = n.DNI
GROUP BY v.EstadoVista, n.EstadoSeguimiento ORDER BY 1, 2;
*/
