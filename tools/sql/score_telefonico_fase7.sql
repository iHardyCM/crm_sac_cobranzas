/* =====================================================================================
   Generador de bases · fase 7 · gestión del cliente y del teléfono            (16/11/2026)
   Base: CobAuto (esquema score). Se puede volver a ejecutar completo.

   Reglas confirmadas por Hardy (16/11/2026):
     1. Mejor contacto del cliente: CEF > CNE > NOC; SG si no tiene gestión humana en el mes.
        Mejor indicador: dentro del mejor tipo, el de menor IdIndicador (siscob.dbo.Indicador no tiene
        columna de orden ni de peso: diagnóstico 13, sección 3).
     2. Cobertura: cualquier gestión del mes, humana o de máquina (predictivo y centralita).
     3. Frecuencia: días distintos del mes con alguna gestión. Frecuencia humana: días con gestión humana.
     4. Estado de la PDP (última PDP generada en el mes): VIGENTE / CAÍDA / PAGADA / SIN PDP.
     5. Historial del teléfono: 6 meses (score.TelefonoDia tiene desde el 14/05/2026: diagnóstico 13, sección 7).

   Ventanas: "mes" = del día 1 del mes en curso hasta AYER (lo de hoy lo cubren las condiciones del día).
             "6 meses" = desde el día 1 de hace 6 meses hasta ayer.
   Fuentes:  gestión humana  siscob.dbo.gestion + siscob.dbo.Indicador (tipo de contacto e indicador)
             máquina         score.TelefonoDia (IntentosMaquina, LlamadasCentralita; solo celulares, como el score)
             PDP             siscob.dbo.COMPROMISO (Pagado, FechaCompromiso, Monto) por IdGestion
             condición       siscob.dbo.Cliente.IdCondicion → siscob.dbo.Condicion (Descripcion, si no Codigo)
             seguimiento     MiBanco_Cobranzas.dbo.VW_SEGUIMIENTOS (solo cartera 112, la del Excel)
             teléfono        score.TelefonoDia (6 meses) y score.Caracteristicas (tramos del score del día)

   BLOQUE 0 · Tablas y columnas nuevas
   BLOQUE 1 · score.fn_TramoFecha y score.sp_ArmarGestion
   BLOQUE 2 · Vista score.vw_BaseTrabajo con los campos nuevos
   BLOQUE 3 · Catálogo (score.Campo) y paso GESTION en score.sp_ActualizarCartera
   BLOQUE 4 · Prueba: simular una cartera (no escribe), luego armar en real y revisar tiempos
   ===================================================================================== */
USE CobAuto;
GO

/* =====================================================================================
   BLOQUE 0 · Tablas y columnas nuevas
   ===================================================================================== */
IF OBJECT_ID('score.GestionCliente', 'U') IS NULL
CREATE TABLE score.GestionCliente (
    IdCartera          INT            NOT NULL,
    DNI                VARCHAR(20)    NOT NULL,
    Condicion          NVARCHAR(100)  NULL,
    MgContacto         VARCHAR(10)    NOT NULL,   -- CEF · CNE · NOC · SIN_TIPO · SG
    MgIndicador        NVARCHAR(200)  NOT NULL,   -- "CEF · PROMESA DE PAGO" (malla) · SG
    MgFecha            DATETIME2(0)   NULL,
    MgFechaTramo       NVARCHAR(40)   NOT NULL,
    UgContacto         VARCHAR(10)    NOT NULL,
    UgIndicador        NVARCHAR(200)  NOT NULL,
    UgFecha            DATETIME2(0)   NULL,
    UgFechaTramo       NVARCHAR(40)   NOT NULL,
    Cobertura          BIT            NOT NULL,
    Frecuencia         SMALLINT       NOT NULL,
    FrecuenciaHumana   SMALLINT       NOT NULL,
    GestionesHumanas   INT            NOT NULL,
    EstadoPdp          NVARCHAR(10)   NOT NULL,   -- VIGENTE · CAÍDA · PAGADA · SIN FECHA · SIN PDP
    FechaCompromiso    DATE           NULL,
    UltCefFecha        DATETIME2(0)   NULL,
    UltCefTramo        NVARCHAR(40)   NOT NULL,
    EstadoSeguimiento  NVARCHAR(60)   NULL,       -- solo carteras con fuente de seguimiento (112)
    FechaSeguimiento   DATE           NULL,
    DatosHasta         DATE           NOT NULL,   -- último día incluido (ayer al armar)
    FechaArmado        DATETIME2(0)   NOT NULL,
    CONSTRAINT PK_score_GestionCliente PRIMARY KEY CLUSTERED (IdCartera, DNI)
);
GO

IF OBJECT_ID('score.GestionTelefono', 'U') IS NULL
CREATE TABLE score.GestionTelefono (
    IdCartera           INT            NOT NULL,
    DNI                 VARCHAR(20)    NOT NULL,
    Telefono            CHAR(9)        NOT NULL,
    MgTelMes            VARCHAR(20)    NOT NULL,   -- código de score.ResultadoTelefono · SIN_GESTION
    UgTelMes            VARCHAR(20)    NOT NULL,
    MgTel6m             VARCHAR(20)    NOT NULL,
    UgTel6m             VARCHAR(20)    NOT NULL,
    UltGestionTel       DATETIME2(0)   NULL,
    UltGestionTelTramo  NVARCHAR(40)   NOT NULL,
    GestionesTelMes     INT            NOT NULL,
    GestionesTel6m      INT            NOT NULL,
    EquivocadosTel6m    INT            NOT NULL,
    DatosHasta          DATE           NOT NULL,
    FechaArmado         DATETIME2(0)   NOT NULL,
    CONSTRAINT PK_score_GestionTelefono PRIMARY KEY CLUSTERED (IdCartera, DNI, Telefono)
);
GO

-- Campos que existen para todas las carteras (no necesitan fila en score.CampoCartera)
IF COL_LENGTH('score.Campo', 'TodasLasCarteras') IS NULL
    ALTER TABLE score.Campo ADD TodasLasCarteras BIT NOT NULL
        CONSTRAINT DF_score_Campo_TodasLasCarteras DEFAULT (0);
GO

-- Grupo nuevo: gestión del teléfono
IF EXISTS (SELECT 1 FROM sys.check_constraints WHERE name = 'CK_score_Campo_Grupo'
                                                 AND parent_object_id = OBJECT_ID('score.Campo'))
    ALTER TABLE score.Campo DROP CONSTRAINT CK_score_Campo_Grupo;
ALTER TABLE score.Campo ADD CONSTRAINT CK_score_Campo_Grupo CHECK (Grupo IN ('SCORE', 'TELEFONO', 'CLIENTE',
    'GESTION_CLIENTE', 'GESTION_TELEFONO', 'SEGMENTO_BANCO', 'SEGMENTO_PROPIO', 'CONDICION_DIA'));
GO

IF COL_LENGTH('score.ActualizacionCartera', 'SegGestion') IS NULL
    ALTER TABLE score.ActualizacionCartera ADD SegGestion INT NULL;
GO

/* =====================================================================================
   BLOQUE 1 · Función de tramos de fecha y procedimiento
   ===================================================================================== */

-- Tramo de una fecha para filtrar sin escribir: "Día 14" (mes en curso), "Mes anterior",
-- "Hace 2-3 meses", "Hace 4-6 meses" o el texto de "sin fecha". Las etiquetas no dependen de la hora del
-- armado: la tabla se rehace cada día y el mes en curso es el del armado.
CREATE OR ALTER FUNCTION score.fn_TramoFecha (@Fecha DATE, @IniMes DATE, @SinFecha NVARCHAR(40))
RETURNS TABLE
AS
RETURN
    SELECT CONVERT(NVARCHAR(40),
           CASE WHEN @Fecha IS NULL THEN @SinFecha
                WHEN @Fecha >= @IniMes THEN N'Día ' + RIGHT('0' + CONVERT(VARCHAR(2), DAY(@Fecha)), 2)
                WHEN @Fecha >= DATEADD(MONTH, -1, @IniMes) THEN N'Mes anterior'
                WHEN @Fecha >= DATEADD(MONTH, -3, @IniMes) THEN N'Hace 2-3 meses'
                ELSE N'Hace 4-6 meses' END) AS Tramo;
GO

CREATE OR ALTER PROCEDURE score.sp_ArmarGestion
    @IdCartera INT,
    @Simular   BIT = 1,                     -- 1 = no escribe; devuelve distribuciones y tiempos
    @Hoy       DATE = NULL,                 -- NULL = hoy (los datos llegan hasta el día anterior)
    @Aviso     NVARCHAR(1000) = NULL OUTPUT -- lo que no se pudo armar (p. ej. la vista de seguimiento)
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

    /* 5. Seguimiento: solo donde hay fuente (112, vista del Excel de MiBanco). Si la vista falla, se avisa. */
    CREATE TABLE #seg (DNI VARCHAR(20) COLLATE DATABASE_DEFAULT NOT NULL PRIMARY KEY,
                       EstadoSeguimiento NVARCHAR(60) NULL, FechaSeguimiento DATE NULL);
    DECLARE @ConSeguimiento BIT = CASE WHEN @IdCartera = 112 THEN 1 ELSE 0 END;
    IF @ConSeguimiento = 1
    BEGIN
        BEGIN TRY
            INSERT INTO #seg (DNI, EstadoSeguimiento, FechaSeguimiento)
            EXEC sys.sp_executesql N'
                SELECT x.DNI, MAX(x.Estado), MAX(x.Fecha)
                FROM (SELECT CONVERT(VARCHAR(20), LEFT(LTRIM(RTRIM(CONVERT(NVARCHAR(40), s.DNI))), 20)) COLLATE DATABASE_DEFAULT AS DNI,
                             NULLIF(LTRIM(RTRIM(CONVERT(NVARCHAR(60), s.ESTADO))), N'''') AS Estado,
                             TRY_CONVERT(DATE, s.FECHA) AS Fecha
                      FROM MiBanco_Cobranzas.dbo.VW_SEGUIMIENTOS AS s) AS x
                WHERE x.DNI <> ''''
                GROUP BY x.DNI;';
        END TRY
        BEGIN CATCH
            SET @ConSeguimiento = 0;
            SET @Aviso = LEFT(N'No se leyó el estado de seguimiento (VW_SEGUIMIENTOS): ' + ERROR_MESSAGE(), 1000);
        END CATCH;
    END;
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
        EstadoSeguimiento NVARCHAR(60) NULL, FechaSeguimiento DATE NULL);
    INSERT INTO #gc
    SELECT d.DNI, co.Condicion,
           ISNULL(mg.Tipo, 'SG'), ISNULL(mg.Indicador, N'SG'), mg.Momento, tmg.Tramo,
           ISNULL(ug.Tipo, 'SG'), ISNULL(ug.Indicador, N'SG'), ug.Momento, tug.Tramo,
           CASE WHEN ISNULL(fr.Dias, 0) > 0 THEN 1 ELSE 0 END, ISNULL(fr.Dias, 0),
           ISNULL(hh.Dias, 0), ISNULL(hh.Gestiones, 0),
           ISNULL(p.EstadoPdp, N'SIN PDP'), p.FechaCompromiso,
           cef.UltCef, tcef.Tramo,
           CASE WHEN @ConSeguimiento = 1 THEN ISNULL(s.EstadoSeguimiento, N'SIN SEGUIMIENTO') END, s.FechaSeguimiento
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
               EstadoPdp, FechaCompromiso, UltCefFecha, UltCefTramo, EstadoSeguimiento, FechaSeguimiento, DatosHasta, FechaArmado)
        SELECT @IdCartera, DNI, Condicion, MgContacto, MgIndicador, MgFecha, MgFechaTramo,
               UgContacto, UgIndicador, UgFecha, UgFechaTramo, Cobertura, Frecuencia, FrecuenciaHumana, GestionesHumanas,
               EstadoPdp, FechaCompromiso, UltCefFecha, UltCefTramo, EstadoSeguimiento, FechaSeguimiento, @Ayer, @Ahora
        FROM #gc;

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
   BLOQUE 2 · Vista de trabajo con la gestión y los tramos del teléfono
   Columnas anteriores sin cambios; se agregan al final.
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
       gc.EstadoPdp, gc.UltCefTramo, gc.EstadoSeguimiento, gc.DatosHasta AS GestionHasta,
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
   BLOQUE 3 · Catálogo y paso GESTION de la actualización
   ===================================================================================== */
-- Score y datos del teléfono ya eran de todas las carteras
UPDATE score.Campo SET TodasLasCarteras = 1 WHERE Grupo IN ('SCORE', 'TELEFONO') AND TodasLasCarteras = 0;
GO

MERGE score.Campo AS t
USING (VALUES
    (N'SISCOB_CONDICION', N'Condición SISCOB (hoy)', N'CSISH', N'CLIENTE', N'LISTA', N'TRABAJO', N'Condicion', NULL, N'Condición del cliente en SISCOB (Cliente.IdCondicion → Condicion). Si el DNI tiene varios clientes en la cartera, el activo más reciente.', N'score.GestionCliente ← siscob.dbo.Cliente.IdCondicion + siscob.dbo.Condicion', N'Cada actualización de la cartera (datos hasta ayer)', 1),
    (N'MG_CONTACTO_MES', N'Mejor contacto del mes', N'MGC', N'GESTION_CLIENTE', N'LISTA', N'TRABAJO', N'MgContacto', N'CEF|CNE|NOC|SIN_TIPO|SG', N'Mejor tipo de contacto de la gestión humana del mes: CEF > CNE > NOC. SG = sin gestión humana en el mes (la máquina no tiene indicador).', N'score.GestionCliente ← siscob.dbo.gestion + Indicador (humana), score.TelefonoDia (máquina y centralita)', N'Cada actualización de la cartera (datos hasta ayer)', 1),
    (N'MG_INDICADOR_MES', N'Malla: mejor indicador del mes', N'MGI', N'GESTION_CLIENTE', N'LISTA', N'TRABAJO', N'MgIndicador', NULL, N'Tipo de contacto · indicador de la mejor gestión humana del mes. Dentro del mejor tipo, el de menor IdIndicador (siscob.dbo.Indicador no tiene orden propio).', N'score.GestionCliente ← siscob.dbo.gestion + Indicador (humana), score.TelefonoDia (máquina y centralita)', N'Cada actualización de la cartera (datos hasta ayer)', 1),
    (N'MG_FECHA_MES', N'Fecha de la mejor gestión', N'MGF', N'GESTION_CLIENTE', N'LISTA', N'TRABAJO', N'MgFechaTramo', N'Día 31|Día 30|Día 29|Día 28|Día 27|Día 26|Día 25|Día 24|Día 23|Día 22|Día 21|Día 20|Día 19|Día 18|Día 17|Día 16|Día 15|Día 14|Día 13|Día 12|Día 11|Día 10|Día 09|Día 08|Día 07|Día 06|Día 05|Día 04|Día 03|Día 02|Día 01|Sin gestión humana en el mes', N'Día del mes en curso de la mejor gestión humana.', N'score.GestionCliente ← siscob.dbo.gestion + Indicador (humana), score.TelefonoDia (máquina y centralita)', N'Cada actualización de la cartera (datos hasta ayer)', 1),
    (N'UG_CONTACTO_MES', N'Última gestión: tipo de contacto', N'UGC', N'GESTION_CLIENTE', N'LISTA', N'TRABAJO', N'UgContacto', N'CEF|CNE|NOC|SIN_TIPO|SG', N'Tipo de contacto de la última gestión humana del mes. SG = sin gestión humana en el mes.', N'score.GestionCliente ← siscob.dbo.gestion + Indicador (humana), score.TelefonoDia (máquina y centralita)', N'Cada actualización de la cartera (datos hasta ayer)', 1),
    (N'UG_INDICADOR_MES', N'Última gestión: indicador', N'UGI', N'GESTION_CLIENTE', N'LISTA', N'TRABAJO', N'UgIndicador', NULL, N'Tipo de contacto · indicador de la última gestión humana del mes.', N'score.GestionCliente ← siscob.dbo.gestion + Indicador (humana), score.TelefonoDia (máquina y centralita)', N'Cada actualización de la cartera (datos hasta ayer)', 1),
    (N'UG_FECHA_MES', N'Fecha de la última gestión', N'UGF', N'GESTION_CLIENTE', N'LISTA', N'TRABAJO', N'UgFechaTramo', N'Día 31|Día 30|Día 29|Día 28|Día 27|Día 26|Día 25|Día 24|Día 23|Día 22|Día 21|Día 20|Día 19|Día 18|Día 17|Día 16|Día 15|Día 14|Día 13|Día 12|Día 11|Día 10|Día 09|Día 08|Día 07|Día 06|Día 05|Día 04|Día 03|Día 02|Día 01|Sin gestión humana en el mes', N'Día del mes en curso de la última gestión humana: sirve para quitar a los gestionados ayer, esta semana, etc.', N'score.GestionCliente ← siscob.dbo.gestion + Indicador (humana), score.TelefonoDia (máquina y centralita)', N'Cada actualización de la cartera (datos hasta ayer)', 1),
    (N'COBERTURA_MES', N'Coberturado en el mes', N'COB', N'GESTION_CLIENTE', N'SINO', N'TRABAJO', N'Cobertura', NULL, N'Sí = el cliente tuvo al menos una gestión en el mes, humana o de máquina (predictivo o centralita).', N'score.GestionCliente ← siscob.dbo.gestion + Indicador (humana), score.TelefonoDia (máquina y centralita)', N'Cada actualización de la cartera (datos hasta ayer)', 1),
    (N'FRECUENCIA_MES', N'Frecuencia de llamada', N'FRE', N'GESTION_CLIENTE', N'RANGO', N'TRABAJO', N'Frecuencia', NULL, N'Días distintos del mes con alguna gestión (humana o máquina).', N'score.GestionCliente ← siscob.dbo.gestion + Indicador (humana), score.TelefonoDia (máquina y centralita)', N'Cada actualización de la cartera (datos hasta ayer)', 1),
    (N'FRECUENCIA_HUMANA_MES', N'Frecuencia humana', N'FREH', N'GESTION_CLIENTE', N'RANGO', N'TRABAJO', N'FrecuenciaHumana', NULL, N'Días distintos del mes con gestión humana.', N'score.GestionCliente ← siscob.dbo.gestion + Indicador (humana), score.TelefonoDia (máquina y centralita)', N'Cada actualización de la cartera (datos hasta ayer)', 1),
    (N'GESTIONES_HUMANAS_SISCOB', N'Cantidad de gestión humana', N'CGH', N'GESTION_CLIENTE', N'RANGO', N'TRABAJO', N'GestionesHumanasSiscob', NULL, N'Gestiones humanas del mes en SISCOB (todas las del cliente en esta cartera).', N'score.GestionCliente ← siscob.dbo.gestion + Indicador (humana), score.TelefonoDia (máquina y centralita)', N'Cada actualización de la cartera (datos hasta ayer)', 1),
    (N'ESTADO_PDP', N'Estado de la PDP', N'EPDP', N'GESTION_CLIENTE', N'LISTA', N'TRABAJO', N'EstadoPdp', N'VIGENTE|CAÍDA|PAGADA|SIN FECHA|SIN PDP', N'Última PDP generada en el mes (monto > 0): PAGADA si Pagado = SI/S; VIGENTE si la fecha de compromiso es hoy o después; CAÍDA si ya pasó.', N'score.GestionCliente ← siscob.dbo.COMPROMISO + siscob.dbo.gestion', N'Cada actualización de la cartera (datos hasta ayer)', 1),
    (N'ULTIMO_CEF', N'Último contacto efectivo (CEF)', N'UCEF6', N'GESTION_CLIENTE', N'LISTA', N'TRABAJO', N'UltCefTramo', N'Día 31|Día 30|Día 29|Día 28|Día 27|Día 26|Día 25|Día 24|Día 23|Día 22|Día 21|Día 20|Día 19|Día 18|Día 17|Día 16|Día 15|Día 14|Día 13|Día 12|Día 11|Día 10|Día 09|Día 08|Día 07|Día 06|Día 05|Día 04|Día 03|Día 02|Día 01|Mes anterior|Hace 2-3 meses|Hace 4-6 meses|Sin CEF en 6 meses', N'Fecha de la última gestión humana CEF: día del mes en curso, o antigüedad en meses (hasta 6).', N'score.GestionCliente ← siscob.dbo.gestion + Indicador (humana), score.TelefonoDia (máquina y centralita)', N'Cada actualización de la cartera (datos hasta ayer)', 1),
    (N'SEGUIMIENTO_ACTUAL', N'Estado de seguimiento', N'SEGA', N'GESTION_CLIENTE', N'LISTA', N'TRABAJO', N'EstadoSeguimiento', NULL, N'Estado de la vista de seguimientos de MiBanco (dificultad de pago en seguimiento o negociación, sin PDP). SIN SEGUIMIENTO = no está en la vista.', N'score.GestionCliente ← MiBanco_Cobranzas.dbo.VW_SEGUIMIENTOS (la misma vista del Excel de MiBanco)', N'Cada actualización de la cartera (datos hasta ayer)', 0),
    (N'MG_TEL_MES', N'Mejor resultado del teléfono (mes)', N'MGT', N'GESTION_TELEFONO', N'LISTA', N'TRABAJO', N'MgTelMes', N'TITULAR|TERCERO_ACUERDO|TERCERO|FALLECIDO|CONTESTA_SIN_ID|NO_CONTESTA|BUZON|APAGADO|SIN_INFORMACION|EQUIVOCADO|NO_EXISTE|NO_APLICA|SIN_CLASIFICAR|SIN_GESTION', N'Mejor resultado del número en el mes (orden de score.ResultadoTelefono). SIN_INFORMACION = solo intentos de máquina sin resultado.', N'score.GestionTelefono ← score.TelefonoDia (humana, máquina y centralita; 6 meses)', N'Cada actualización de la cartera (datos hasta ayer)', 1),
    (N'UG_TEL_MES', N'Último resultado del teléfono (mes)', N'UGT', N'GESTION_TELEFONO', N'LISTA', N'TRABAJO', N'UgTelMes', N'TITULAR|TERCERO_ACUERDO|TERCERO|FALLECIDO|CONTESTA_SIN_ID|NO_CONTESTA|BUZON|APAGADO|SIN_INFORMACION|EQUIVOCADO|NO_EXISTE|NO_APLICA|SIN_CLASIFICAR|SIN_GESTION', N'Último resultado con información del número en el mes (se saltan los intentos de máquina sin resultado). SIN_INFORMACION = solo hubo intentos sin resultado.', N'score.GestionTelefono ← score.TelefonoDia (humana, máquina y centralita; 6 meses)', N'Cada actualización de la cartera (datos hasta ayer)', 1),
    (N'MG_TEL_6M', N'Mejor resultado del teléfono (6 meses)', N'MGT6', N'GESTION_TELEFONO', N'LISTA', N'TRABAJO', N'MgTel6m', N'TITULAR|TERCERO_ACUERDO|TERCERO|FALLECIDO|CONTESTA_SIN_ID|NO_CONTESTA|BUZON|APAGADO|SIN_INFORMACION|EQUIVOCADO|NO_EXISTE|NO_APLICA|SIN_CLASIFICAR|SIN_GESTION', N'Mejor resultado histórico del número (6 meses): por ejemplo TITULAR para teléfonos con CEF en la historia.', N'score.GestionTelefono ← score.TelefonoDia (humana, máquina y centralita; 6 meses)', N'Cada actualización de la cartera (datos hasta ayer)', 1),
    (N'UG_TEL_6M', N'Último resultado del teléfono (6 meses)', N'UGT6', N'GESTION_TELEFONO', N'LISTA', N'TRABAJO', N'UgTel6m', N'TITULAR|TERCERO_ACUERDO|TERCERO|FALLECIDO|CONTESTA_SIN_ID|NO_CONTESTA|BUZON|APAGADO|SIN_INFORMACION|EQUIVOCADO|NO_EXISTE|NO_APLICA|SIN_CLASIFICAR|SIN_GESTION', N'Último resultado con información del número en 6 meses (se saltan los intentos de máquina sin resultado): sirve para quitar apagados, no existe, equivocados.', N'score.GestionTelefono ← score.TelefonoDia (humana, máquina y centralita; 6 meses)', N'Cada actualización de la cartera (datos hasta ayer)', 1),
    (N'ULT_GESTION_TEL', N'Última gestión del teléfono', N'UGTF', N'GESTION_TELEFONO', N'LISTA', N'TRABAJO', N'UltGestionTelTramo', N'Día 31|Día 30|Día 29|Día 28|Día 27|Día 26|Día 25|Día 24|Día 23|Día 22|Día 21|Día 20|Día 19|Día 18|Día 17|Día 16|Día 15|Día 14|Día 13|Día 12|Día 11|Día 10|Día 09|Día 08|Día 07|Día 06|Día 05|Día 04|Día 03|Día 02|Día 01|Mes anterior|Hace 2-3 meses|Hace 4-6 meses|Sin gestión en 6 meses', N'Fecha de la última gestión del número (humana, máquina o centralita): día del mes en curso o antigüedad. Sirve para tomar no tocados este mes o esta semana.', N'score.GestionTelefono ← score.TelefonoDia (humana, máquina y centralita; 6 meses)', N'Cada actualización de la cartera (datos hasta ayer)', 1),
    (N'GESTIONES_TEL_MES', N'Gestiones del teléfono en el mes', N'GTM', N'GESTION_TELEFONO', N'RANGO', N'TRABAJO', N'GestionesTelMes', NULL, N'Intentos del mes al número: humanos + máquina + centralita.', N'score.GestionTelefono ← score.TelefonoDia (humana, máquina y centralita; 6 meses)', N'Cada actualización de la cartera (datos hasta ayer)', 1),
    (N'GESTIONES_TEL_6M', N'Gestiones del teléfono en 6 meses', N'GT6', N'GESTION_TELEFONO', N'RANGO', N'TRABAJO', N'GestionesTel6m', NULL, N'Intentos al número en 6 meses: humanos + máquina + centralita.', N'score.GestionTelefono ← score.TelefonoDia (humana, máquina y centralita; 6 meses)', N'Cada actualización de la cartera (datos hasta ayer)', 1),
    (N'EQUIVOCADOS_TEL_6M', N'Equivocados del teléfono (6 meses)', N'EQ6', N'GESTION_TELEFONO', N'RANGO', N'TRABAJO', N'EquivocadosTel6m', NULL, N'Veces que el número se tipificó como equivocado para este cliente en 6 meses.', N'score.GestionTelefono ← score.TelefonoDia (humana, máquina y centralita; 6 meses)', N'Cada actualización de la cartera (datos hasta ayer)', 1),
    (N'DIAS_ULT_CEF_TEL', N'Días desde el último CEF del teléfono', N'UCT', N'GESTION_TELEFONO', N'LISTA', N'TRABAJO', N'TramoUltCefTel', N'1-7|8-30|31-90|SIN_CEF_90', N'Tramo del score: días desde el último contacto (titular o tercero con acuerdo) en este número, en 90 días.', N'score.Caracteristicas (las mismas del score del día)', N'Cada actualización de la cartera', 1),
    (N'TASA_CEF_TEL_90', N'Tasa de CEF del teléfono (90 días)', N'TCT', N'GESTION_TELEFONO', N'LISTA', N'TRABAJO', N'TramoTasaCef90', N'>=15%|5-15%|<5%|0|SIN_INTENTOS', N'Tramo del score: CEF ÷ intentos del número en 90 días.', N'score.Caracteristicas (las mismas del score del día)', N'Cada actualización de la cartera', 1),
    (N'INTENTOS_TEL_30', N'Intentos al teléfono (30 días)', N'IT30', N'GESTION_TELEFONO', N'LISTA', N'TRABAJO', N'TramoIntentos30', N'0|1-3|4-10|11-30|>30', N'Tramo del score: intentos al número en 30 días.', N'score.Caracteristicas (las mismas del score del día)', N'Cada actualización de la cartera', 1),
    (N'DIAS_ULT_INTENTO_TEL', N'Días desde el último intento', N'UINT', N'GESTION_TELEFONO', N'LISTA', N'TRABAJO', N'TramoUltIntento', N'1-7|8-30|31-90|SIN_INT_90', N'Tramo del score: días desde el último intento al número, en 90 días.', N'score.Caracteristicas (las mismas del score del día)', N'Cada actualización de la cartera', 1),
    (N'NO_CONECTA_TEL_90', N'Qué pasa cuando no conecta', N'NCT', N'GESTION_TELEFONO', N'LISTA', N'TRABAJO', N'TramoNoConecta90', N'CONTESTA|TIMBRA|BUZON|APAGADO|SIN_DATO', N'Tramo del score: resultado más frecuente cuando no hay contacto en 90 días (centralita y resultados humanos).', N'score.Caracteristicas (las mismas del score del día)', N'Cada actualización de la cartera', 1),
    (N'ORIGEN_DATO', N'Origen del teléfono', N'ORI', N'TELEFONO', N'LISTA', N'TRABAJO', N'OrigenDato', N'EMPRESA|CLIENTE|BUSQUEDA|OPERADORA|OTRO|SIN_DATO', N'Origen normalizado del número (el mismo del score): EMPRESA = lo envió el banco.', N'score.Caracteristicas (las mismas del score del día)', N'Cada actualización de la cartera', 1),
    (N'FUENTE_DATO', N'Fuente o tipo de base del teléfono', N'FUE', N'TELEFONO', N'LISTA', N'TRABAJO', N'FuenteDato', N'BASE_INTERNA|SEARCH|ENRIQUECIMIENTO|OTRA|SIN_DATO', N'Fuente normalizada del número según la observación de SISCOB (el mismo tramo del score).', N'score.Caracteristicas (las mismas del score del día)', N'Cada actualización de la cartera', 1),
    (N'ANTIGUEDAD_DATO', N'Antigüedad del dato', N'ANT', N'TELEFONO', N'LISTA', N'TRABAJO', N'AntiguedadDato', N'<1A|1-2A|3-5A|>5A|SIN_DATO', N'Años desde el año-mes del dato (origen "M 202306").', N'score.Caracteristicas (las mismas del score del día)', N'Cada actualización de la cartera', 1),
    (N'TIPO_LINEA', N'Tipo de línea', N'TLI', N'TELEFONO', N'LISTA', N'TRABAJO', N'TipoLinea', N'POSTPAGO|CONTROL|PREPAGO|NO_INFORMA|SIN_DATO', N'Según la observación del número en SISCOB.', N'score.Caracteristicas (las mismas del score del día)', N'Cada actualización de la cartera', 1),
    (N'RELACION_TEL', N'Relación del teléfono', N'REL', N'TELEFONO', N'LISTA', N'TRABAJO', N'Relacion', N'TITULAR|CONYUGE|AVAL|FAMILIAR|REFERENCIA|NO_INFORMA|SIN_DATO', N'A quién pertenece el número según la observación en SISCOB.', N'score.Caracteristicas (las mismas del score del día)', N'Cada actualización de la cartera', 1)
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

-- Seguimiento: solo la cartera que tiene fuente (112)
MERGE score.CampoCartera AS t
USING (VALUES (N'SEGUIMIENTO_ACTUAL', 112, N'CLIENTE', N'MiBanco_Cobranzas.dbo.VW_SEGUIMIENTOS', N'ESTADO'))
      AS s (Campo, IdCartera, Nivel, Tabla, Columna)
ON t.Campo = s.Campo AND t.IdCartera = s.IdCartera
WHEN MATCHED THEN UPDATE SET Nivel = s.Nivel, Tabla = s.Tabla, Columna = s.Columna
WHEN NOT MATCHED THEN INSERT (Campo, IdCartera, Nivel, Tabla, Columna) VALUES (s.Campo, s.IdCartera, s.Nivel, s.Tabla, s.Columna);
GO

-- Actualización de una cartera: igual que en fase 3, con el paso 8 GESTION después de BASE
CREATE OR ALTER PROCEDURE score.sp_ActualizarCartera
    @IdCartera INT,
    @Usuario   NVARCHAR(128) = NULL,     -- DNI del usuario del CRM, o 'JOB'
    @Origen    VARCHAR(12)   = 'MANUAL', -- MANUAL · PROGRAMADA
    @Alinear   BIT           = 1,        -- alinear con producción antes de rehacer el universo
    @Simular   BIT           = 1,
    @AvisoPrevio NVARCHAR(1000) = NULL   -- aviso de un paso hecho antes por el job (p. ej. alineación fallida)
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    DECLARE @Hoy DATE = CAST(GETDATE() AS DATE),
            @Recurso NVARCHAR(100) = N'SCORE_CARTERA_' + CONVERT(NVARCHAR(10), @IdCartera),
            @Id INT, @Lock INT, @t DATETIME2(3), @Paso VARCHAR(20) = 'INICIO',
            @Aviso NVARCHAR(1000) = NULLIF(LTRIM(RTRIM(@AvisoPrevio)), N''), @Version INT, @Carteras VARCHAR(10) = CONVERT(VARCHAR(10), @IdCartera);

    SET @Usuario = ISNULL(NULLIF(LTRIM(RTRIM(@Usuario)), N''), ORIGINAL_LOGIN());

    IF @Origen NOT IN ('MANUAL', 'PROGRAMADA')
        THROW 50421, 'Origen debe ser MANUAL o PROGRAMADA.', 1;
    IF NOT EXISTS (SELECT 1 FROM ControlCobranza.bl.EntidadCartera WHERE IdCartera = @IdCartera)
        THROW 50422, 'La cartera no está en ControlCobranza.bl.EntidadCartera.', 1;
    SELECT @Version = Version FROM score.PesoVersion WHERE Estado = 'PUBLICADA';
    IF @Simular = 0 AND @Version IS NULL
        THROW 50423, 'No hay una versión de pesos publicada.', 1;

    -- Candado de la cartera: sin espera. Si está ocupada, se informa y no se lanza otra corrida.
    EXEC @Lock = sp_getapplock @Resource = @Recurso, @LockMode = 'Exclusive', @LockOwner = 'Session', @LockTimeout = 0;
    IF @Lock < 0
    BEGIN
        SELECT TOP 1 'OCUPADA' AS Resultado, a.IdActualizacion, a.IdCartera, a.Usuario, a.Inicio, a.Paso
        FROM score.ActualizacionCartera AS a
        WHERE a.IdCartera = @IdCartera AND a.Estado = 'EN_CURSO'
        ORDER BY a.Inicio DESC;
        RETURN 1;
    END;

    BEGIN TRY
        -- Corridas que quedaron abiertas (proceso cortado): ya no tienen el candado
        UPDATE score.ActualizacionCartera SET Estado = 'INTERRUMPIDA', Fin = SYSDATETIME()
        WHERE IdCartera = @IdCartera AND Estado = 'EN_CURSO';

        INSERT INTO score.ActualizacionCartera (IdCartera, Origen, Modo, Usuario, Inicio, Estado, Paso, Version)
        VALUES (@IdCartera, @Origen, CASE WHEN @Simular = 1 THEN 'SIMULACION' ELSE 'REAL' END,
                @Usuario, SYSDATETIME(), 'EN_CURSO', @Paso, @Version);
        SET @Id = SCOPE_IDENTITY();

        -- 1. Historial de ayer
        IF @Simular = 0
        BEGIN
            SET @Paso = 'HISTORIAL'; SET @t = SYSDATETIME();
            UPDATE score.ActualizacionCartera SET Paso = @Paso WHERE IdActualizacion = @Id;
            EXEC score.sp_AsegurarHistorial;
            UPDATE score.ActualizacionCartera SET SegHistorial = DATEDIFF(SECOND, @t, SYSDATETIME()) WHERE IdActualizacion = @Id;
        END;
        UPDATE score.ActualizacionCartera
        SET HistorialHasta = (SELECT MAX(Fecha) FROM score.TelefonoDiaControl WHERE Fecha < @Hoy)
        WHERE IdActualizacion = @Id;

        -- 2. Alineación con producción. Si producción no responde, se avisa y se sigue con la copia local.
        IF @Alinear = 1
        BEGIN
            SET @Paso = 'ALINEACION'; SET @t = SYSDATETIME();
            UPDATE score.ActualizacionCartera SET Paso = @Paso WHERE IdActualizacion = @Id;
            BEGIN TRY
                EXEC score.sp_AlinearAtributosTelefono @Carteras = @Carteras, @Simular = @Simular;
            END TRY
            BEGIN CATCH
                IF XACT_STATE() <> 0 ROLLBACK;
                SET @Aviso = LEFT(N'No se pudo alinear con producción; se usó la copia local. ' + ERROR_MESSAGE(), 1000);
            END CATCH;
            UPDATE score.ActualizacionCartera SET SegAlineacion = DATEDIFF(SECOND, @t, SYSDATETIME()) WHERE IdActualizacion = @Id;
        END;

        -- 3. Universo de la cartera
        SET @Paso = 'UNIVERSO'; SET @t = SYSDATETIME();
        UPDATE score.ActualizacionCartera SET Paso = @Paso WHERE IdActualizacion = @Id;
        EXEC score.sp_ArmarUniversoCartera @IdCartera = @IdCartera, @Simular = @Simular;
        UPDATE score.ActualizacionCartera SET SegUniverso = DATEDIFF(SECOND, @t, SYSDATETIME()) WHERE IdActualizacion = @Id;

        IF @Simular = 1
        BEGIN
            -- En simulación se llega hasta el universo: lo que sigue necesita el universo nuevo guardado
            UPDATE score.ActualizacionCartera
            SET Estado = 'SIMULADA', Fin = SYSDATETIME(), Paso = 'FIN',
                Mensaje = CONCAT(@Aviso, CASE WHEN @Aviso IS NULL THEN N'' ELSE N' ' END,
                                 N'Simulación hasta el universo; características y score se calculan solo en modo real.')
            WHERE IdActualizacion = @Id;
        END
        ELSE
        BEGIN
            -- 4. Historial de atributos (semáforo, OSIPTEL, WhatsApp, timbrado)
            SET @Paso = 'ATRIBUTOS';
            UPDATE score.ActualizacionCartera SET Paso = @Paso WHERE IdActualizacion = @Id;
            EXEC score.sp_RegistrarAtributosTelefono @IdCartera = @IdCartera;

            -- 5. Características (historial hasta ayer)
            SET @Paso = 'CARACTERISTICAS'; SET @t = SYSDATETIME();
            UPDATE score.ActualizacionCartera SET Paso = @Paso WHERE IdActualizacion = @Id;
            EXEC score.sp_ArmarCaracteristicas @FechaCorte = @Hoy, @Poblacion = 'UNIVERSO', @Simular = 0, @IdCartera = @IdCartera;
            UPDATE score.ActualizacionCartera SET SegCaracteristicas = DATEDIFF(SECOND, @t, SYSDATETIME()) WHERE IdActualizacion = @Id;

            -- 6. Score
            SET @Paso = 'SCORE'; SET @t = SYSDATETIME();
            UPDATE score.ActualizacionCartera SET Paso = @Paso WHERE IdActualizacion = @Id;
            EXEC score.sp_CalcularScore @FechaCorte = @Hoy, @Simular = 0, @IdCartera = @IdCartera;
            UPDATE score.ActualizacionCartera SET SegScore = DATEDIFF(SECOND, @t, SYSDATETIME()) WHERE IdActualizacion = @Id;

            -- 7. Tabla de trabajo del generador (datos del cliente del corte de Analytics). Si falla, el score
            --    ya quedó actualizado: se avisa y la pantalla sigue con los datos del cliente anteriores.
            SET @Paso = 'BASE'; SET @t = SYSDATETIME();
            UPDATE score.ActualizacionCartera SET Paso = @Paso WHERE IdActualizacion = @Id;
            BEGIN TRY
                EXEC score.sp_ArmarBaseTrabajoCliente @IdCartera = @IdCartera, @Simular = 0;
            END TRY
            BEGIN CATCH
                IF XACT_STATE() <> 0 ROLLBACK;
                SET @Aviso = LEFT(CONCAT(@Aviso, CASE WHEN @Aviso IS NULL THEN N'' ELSE N' ' END,
                                         N'No se actualizó la tabla de trabajo: ', ERROR_MESSAGE()), 1000);
            END CATCH;
            UPDATE score.ActualizacionCartera SET SegBase = DATEDIFF(SECOND, @t, SYSDATETIME()) WHERE IdActualizacion = @Id;

            -- 8. Gestión del cliente y del teléfono para el generador (fase 7). Si falla, se avisa y la
            --    pantalla sigue con la gestión anterior.
            SET @Paso = 'GESTION'; SET @t = SYSDATETIME();
            UPDATE score.ActualizacionCartera SET Paso = @Paso WHERE IdActualizacion = @Id;
            BEGIN TRY
                DECLARE @AvisoGestion NVARCHAR(1000) = NULL;
                EXEC score.sp_ArmarGestion @IdCartera = @IdCartera, @Simular = 0, @Aviso = @AvisoGestion OUTPUT;
                IF @AvisoGestion IS NOT NULL
                    SET @Aviso = LEFT(CONCAT(@Aviso, CASE WHEN @Aviso IS NULL THEN N'' ELSE N' ' END, @AvisoGestion), 1000);
            END TRY
            BEGIN CATCH
                IF XACT_STATE() <> 0 ROLLBACK;
                SET @Aviso = LEFT(CONCAT(@Aviso, CASE WHEN @Aviso IS NULL THEN N'' ELSE N' ' END,
                                         N'No se actualizó la gestión del generador: ', ERROR_MESSAGE()), 1000);
            END CATCH;

            UPDATE score.ActualizacionCartera
            SET SegGestion = DATEDIFF(SECOND, @t, SYSDATETIME()),
                Estado = 'OK', Fin = SYSDATETIME(), Paso = 'FIN', Mensaje = @Aviso,
                Telefonos = (SELECT COUNT(*) FROM score.TelefonoScore WHERE FechaCorte = @Hoy AND IdCartera = @IdCartera),
                Excluidos = (SELECT COUNT(*) FROM score.TelefonoUniverso WHERE IdCartera = @IdCartera AND ExcluidoListaNegra = 1)
            WHERE IdActualizacion = @Id;
        END;

        EXEC sp_releaseapplock @Resource = @Recurso, @LockOwner = 'Session';
    END TRY
    BEGIN CATCH
        IF XACT_STATE() <> 0 ROLLBACK;
        DECLARE @Err NVARCHAR(2000) = LEFT(CONCAT(N'Paso ', @Paso, N': ', ERROR_MESSAGE()), 2000);
        IF @Id IS NOT NULL
            UPDATE score.ActualizacionCartera SET Estado = 'ERROR', Fin = SYSDATETIME(), Mensaje = @Err
            WHERE IdActualizacion = @Id;
        IF APPLOCK_MODE('public', @Recurso, 'Session') <> 'NoLock'
            EXEC sp_releaseapplock @Resource = @Recurso, @LockOwner = 'Session';
        THROW;
    END CATCH;

    SELECT 'TERMINADA' AS Resultado, a.*
    FROM score.ActualizacionCartera AS a WHERE a.IdActualizacion = @Id;
    RETURN 0;
END;
GO

/* =====================================================================================
   BLOQUE 4 · Prueba (ejecutar por partes)
   ===================================================================================== */
/*
-- 4.1 Simular una cartera: no escribe. Revisar distribuciones, malla y tiempos (última tabla).
DECLARE @Aviso NVARCHAR(1000);
EXEC score.sp_ArmarGestion @IdCartera = 124, @Simular = 1, @Aviso = @Aviso OUTPUT;
SELECT @Aviso AS Aviso;

-- 4.2 Armar en real las carteras activas (la próxima actualización ya lo hace sola en el paso GESTION)
DECLARE @Id INT, @Aviso2 NVARCHAR(1000), @t DATETIME2(3);
DECLARE c CURSOR LOCAL FAST_FORWARD FOR SELECT DISTINCT IdCartera FROM score.TelefonoUniverso ORDER BY IdCartera;
OPEN c; FETCH NEXT FROM c INTO @Id;
WHILE @@FETCH_STATUS = 0
BEGIN
    SET @t = SYSDATETIME();
    EXEC score.sp_ArmarGestion @IdCartera = @Id, @Simular = 0, @Aviso = @Aviso2 OUTPUT;
    PRINT CONCAT('Cartera ', @Id, ': ', DATEDIFF(SECOND, @t, SYSDATETIME()), ' s', ISNULL(' · ' + @Aviso2, ''));
    FETCH NEXT FROM c INTO @Id;
END;
CLOSE c; DEALLOCATE c;

-- 4.3 Control
SELECT IdCartera, COUNT(*) AS Clientes, SUM(CAST(Cobertura AS INT)) AS Coberturados,
       SUM(CASE WHEN MgContacto = 'CEF' THEN 1 ELSE 0 END) AS ConCEF, MIN(DatosHasta) AS DatosHasta, MIN(FechaArmado) AS Armado
FROM score.GestionCliente GROUP BY IdCartera ORDER BY IdCartera;
SELECT IdCartera, COUNT(*) AS Telefonos, SUM(CASE WHEN MgTel6m = 'TITULAR' THEN 1 ELSE 0 END) AS ConTitular6m
FROM score.GestionTelefono GROUP BY IdCartera ORDER BY IdCartera;
*/
