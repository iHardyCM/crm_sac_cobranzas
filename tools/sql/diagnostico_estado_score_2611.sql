/* =====================================================================================
   diagnostico_estado_score_2611.sql · 26/11/2026 · SOLO LECTURA (puede tardar 1-3 min: lee gestiones de 10 días)
   1. ¿Se actualiza solo el score? (job y bitácora)
   2. ¿Llegan las llamadas de máquina, la gestión humana y la centralita a la copia de SISCOB?
   3. Efectividad de las bases generadas (últimos 10 días), por base, canal y tipo de base usual
   4. Acierto del score por tramo en los días recientes
   5. ¿Una llamada del predictivo que pasa a un asesor cuenta dos veces?
   Guardar los resultados como texto: tools/salidas/resultado_estado_score_2611.txt
   ===================================================================================== */
USE CobAuto;
SET NOCOUNT ON;
GO

PRINT '=== 1.1 Jobs del Agente SQL relacionados con el score ===';
SELECT j.name AS Job, j.enabled AS Activo, s.name AS Programacion, s.active_start_time AS HoraInicio,
       h.run_date AS UltimaEjecucion, h.run_time AS Hora,
       CASE h.run_status WHEN 0 THEN 'ERROR' WHEN 1 THEN 'OK' WHEN 3 THEN 'CANCELADO' ELSE CONVERT(VARCHAR(5), h.run_status) END AS Estado
FROM msdb.dbo.sysjobs AS j
LEFT JOIN msdb.dbo.sysjobschedules AS js ON js.job_id = j.job_id
LEFT JOIN msdb.dbo.sysschedules AS s ON s.schedule_id = js.schedule_id
OUTER APPLY (SELECT TOP (1) run_date, run_time, run_status FROM msdb.dbo.sysjobhistory AS x
             WHERE x.job_id = j.job_id AND x.step_id = 0 ORDER BY run_date DESC, run_time DESC) AS h
WHERE j.name LIKE N'%score%' OR j.name LIKE N'%Maestro%' OR j.name LIKE N'%CobAuto%'
ORDER BY j.name;
GO

PRINT '=== 1.2 Bitácora de actualizaciones, últimos 10 días (por día y origen) ===';
SELECT CAST(Inicio AS DATE) AS Dia, Origen, Estado, COUNT(*) AS Ejecuciones, COUNT(DISTINCT IdCartera) AS Carteras,
       MIN(CONVERT(TIME(0), Inicio)) AS PrimeraHora, MAX(CONVERT(TIME(0), Inicio)) AS UltimaHora,
       MAX(HistorialHasta) AS HistorialHasta
FROM score.ActualizacionCartera
WHERE Inicio >= DATEADD(DAY, -10, CAST(GETDATE() AS DATE)) AND Modo = 'REAL'
GROUP BY CAST(Inicio AS DATE), Origen, Estado
ORDER BY Dia DESC, Origen, Estado;

PRINT '=== 1.3 Último score por cartera ===';
SELECT IdCartera, MAX(FechaCorte) AS UltimoScore, COUNT(DISTINCT FechaCorte) AS DiasConScoreUlt10
FROM score.TelefonoScore WHERE FechaCorte >= DATEADD(DAY, -10, CAST(GETDATE() AS DATE))
GROUP BY IdCartera ORDER BY IdCartera;
GO

PRINT '=== 2.1 Llamadas por día en la copia local de SISCOB (máquina y humana) ===';
DECLARE @d10 DATE = DATEADD(DAY, -10, CAST(GETDATE() AS DATE));
SELECT x.Dia, x.Maquina, y.Humana, x.UltimaHoraMaquina
FROM (SELECT CAST(Fecha AS DATE) AS Dia, COUNT_BIG(*) AS Maquina, MAX(CAST(Hora AS TIME(0))) AS UltimaHoraMaquina
      FROM siscob.dbo.pgestion WITH (NOLOCK) WHERE Fecha >= @d10 GROUP BY CAST(Fecha AS DATE)) AS x
FULL JOIN (SELECT CAST(Fecha AS DATE) AS Dia, COUNT_BIG(*) AS Humana
           FROM siscob.dbo.gestion WITH (NOLOCK) WHERE Fecha >= @d10 GROUP BY CAST(Fecha AS DATE)) AS y ON y.Dia = x.Dia
ORDER BY COALESCE(x.Dia, y.Dia) DESC;

PRINT '=== 2.2 Historial cargado en el score (TelefonoDiaControl) ===';
SELECT TOP (12) * FROM score.TelefonoDiaControl ORDER BY Fecha DESC;

PRINT '=== 2.3 Centralita por día (noviembre) ===';
SELECT CAST([start] AS DATE) AS Dia, COUNT_BIG(*) AS Llamadas
FROM Desarrollo.dbo.CENTRALITA WITH (NOLOCK)
WHERE [start] >= '2026-11-01'
GROUP BY CAST([start] AS DATE) ORDER BY Dia DESC;

PRINT '=== 2.4 Fotos del SAC ===';
IF OBJECT_ID('score.SacCarga') IS NOT NULL SELECT TOP (5) * FROM score.SacCarga ORDER BY FechaSac DESC;
GO

PRINT '=== 3. Efectividad de las bases generadas, últimos 10 días ===';
DECLARE @Desde DATE = DATEADD(DAY, -9, CAST(GETDATE() AS DATE));
IF OBJECT_ID('tempdb..#rb') IS NOT NULL DROP TABLE #rb;

        SELECT b.IdBase, b.IdCartera, b.Codigo, b.NombreArchivo, b.Canal, b.FechaGeneracion,
               CASE WHEN CAST(b.FechaGeneracion AS TIME) >= '18:00'
                    THEN DATEADD(DAY, 2, CAST(CAST(b.FechaGeneracion AS DATE) AS DATETIME))
                    ELSE DATEADD(DAY, 1, CAST(CAST(b.FechaGeneracion AS DATE) AS DATETIME)) END AS VentanaFin
        INTO #rb
        FROM score.Base AS b
        WHERE b.Codigo IS NOT NULL AND b.FechaGeneracion >= @Desde;
        
IF OBJECT_ID('tempdb..#rd') IS NOT NULL DROP TABLE #rd;

        SELECT d.IdBase, d.IdCartera, d.DNI, d.Telefono, b.FechaGeneracion, b.VentanaFin
        INTO #rd
        FROM score.BaseDetalle AS d INNER JOIN #rb AS b ON b.IdBase = d.IdBase;
        CREATE INDEX IX_rd ON #rd (Telefono, IdCartera, FechaGeneracion) INCLUDE (IdBase, VentanaFin, DNI);
        
IF OBJECT_ID('tempdb..#rt') IS NOT NULL DROP TABLE #rt;

        SELECT DISTINCT IdCartera, Telefono INTO #rt FROM #rd;
        CREATE UNIQUE CLUSTERED INDEX IX_rt ON #rt (Telefono, IdCartera);
        
IF OBJECT_ID('tempdb..#re') IS NOT NULL DROP TABLE #re;

        DECLARE @ini DATE = (SELECT CAST(MIN(FechaGeneracion) AS DATE) FROM #rb);
        DECLARE @fin DATE = (SELECT CAST(MAX(VentanaFin) AS DATE) FROM #rb);
        CREATE TABLE #re (Fuente CHAR(1) NOT NULL, IdGestion BIGINT NOT NULL, IdCartera INT NOT NULL,
                          Telefono CHAR(9) COLLATE DATABASE_DEFAULT NOT NULL, Momento DATETIME NOT NULL, EsCef BIT NOT NULL);
        IF @ini IS NOT NULL
        BEGIN
            INSERT INTO #re (Fuente, IdGestion, IdCartera, Telefono, Momento, EsCef)
            SELECT 'H', g.IdGestion, g.idCartera, CONVERT(CHAR(9), g.telefono),
                   CAST(CAST(g.Fecha AS DATE) AS DATETIME) + CAST(ISNULL(CAST(g.Hora AS TIME(0)), '00:00') AS DATETIME),
                   CASE WHEN LTRIM(RTRIM(i.TipoContacto)) = 'CEF' THEN 1
                        WHEN LTRIM(RTRIM(i.TipoContacto)) IN ('CNE', 'NOC') THEN 0
                        WHEN g.TipoContacto = 1 THEN 1 ELSE 0 END
            FROM siscob.dbo.gestion AS g WITH (NOLOCK)
            LEFT JOIN siscob.dbo.Indicador AS i WITH (NOLOCK) ON i.IdIndicador = g.IdIndicador
            WHERE g.Fecha >= @ini AND g.Fecha < @fin
              AND g.idCartera IN (SELECT DISTINCT IdCartera FROM #rt)
              AND g.telefono BETWEEN 900000000 AND 999999999
              AND EXISTS (SELECT 1 FROM #rt AS t WHERE t.Telefono = CONVERT(CHAR(9), g.telefono) AND t.IdCartera = g.idCartera)
            OPTION (RECOMPILE);
            INSERT INTO #re (Fuente, IdGestion, IdCartera, Telefono, Momento, EsCef)
            SELECT 'M', g.IdGestion, g.idCartera, CONVERT(CHAR(9), g.telefono),
                   CAST(CAST(g.Fecha AS DATE) AS DATETIME) + CAST(ISNULL(CAST(g.Hora AS TIME(0)), '00:00') AS DATETIME), 0
            FROM siscob.dbo.pgestion AS g WITH (NOLOCK)
            WHERE g.Fecha >= @ini AND g.Fecha < @fin
              AND g.idCartera IN (SELECT DISTINCT IdCartera FROM #rt)
              AND g.telefono BETWEEN 900000000 AND 999999999
              AND EXISTS (SELECT 1 FROM #rt AS t WHERE t.Telefono = CONVERT(CHAR(9), g.telefono) AND t.IdCartera = g.idCartera)
            OPTION (RECOMPILE);
        END;
        
IF OBJECT_ID('tempdb..#ra') IS NOT NULL DROP TABLE #ra;

        -- Cada llamada a la base más reciente generada antes, con ventana abierta y ese teléfono
        SELECT e.Fuente, e.IdGestion, e.EsCef, e.Telefono, x.IdBase, x.DNI
        INTO #ra
        FROM #re AS e
        CROSS APPLY (SELECT TOP (1) d.IdBase, d.DNI FROM #rd AS d
                     WHERE d.Telefono = e.Telefono AND d.IdCartera = e.IdCartera
                       AND d.FechaGeneracion <= e.Momento AND e.Momento < d.VentanaFin
                     ORDER BY d.FechaGeneracion DESC, d.IdBase DESC) AS x;
        
IF OBJECT_ID('tempdb..#rp') IS NOT NULL DROP TABLE #rp;

        -- PDP de las gestiones CEF atribuidas
        SELECT a.IdBase, a.DNI, cp.Monto
        INTO #rp
        FROM #ra AS a
        INNER JOIN siscob.dbo.COMPROMISO AS cp WITH (NOLOCK) ON cp.IdGestion = a.IdGestion
        WHERE a.Fuente = 'H' AND a.EsCef = 1 AND cp.Monto > 0;
        

        SELECT b.IdBase, b.IdCartera, b.Codigo, b.NombreArchivo, b.Canal, b.FechaGeneracion, b.VentanaFin,
               CASE WHEN GETDATE() < b.VentanaFin THEN 1 ELSE 0 END AS EnCurso,
               (SELECT COUNT(*) FROM #rd AS d WHERE d.IdBase = b.IdBase) AS Telefonos,
               (SELECT COUNT(DISTINCT d.DNI) FROM #rd AS d WHERE d.IdBase = b.IdBase) AS Clientes,
               (SELECT COUNT(DISTINCT a.Telefono) FROM #ra AS a WHERE a.IdBase = b.IdBase) AS TelMarcados,
               (SELECT COUNT(DISTINCT a.DNI) FROM #ra AS a WHERE a.IdBase = b.IdBase) AS CliMarcados,
               (SELECT COUNT(*) FROM #ra AS a WHERE a.IdBase = b.IdBase) AS Intentos,
               (SELECT COUNT(*) FROM #ra AS a WHERE a.IdBase = b.IdBase AND a.Fuente = 'H') AS IntentosHumano,
               (SELECT COUNT(*) FROM #ra AS a WHERE a.IdBase = b.IdBase AND a.Fuente = 'M') AS IntentosMaquina,
               (SELECT COUNT(DISTINCT a.Telefono) FROM #ra AS a WHERE a.IdBase = b.IdBase AND a.EsCef = 1) AS TelCef,
               (SELECT COUNT(DISTINCT a.DNI) FROM #ra AS a WHERE a.IdBase = b.IdBase AND a.EsCef = 1) AS CliCef,
               (SELECT COUNT(*) FROM #rp AS p WHERE p.IdBase = b.IdBase) AS Pdp,
               (SELECT COUNT(DISTINCT p.DNI) FROM #rp AS p WHERE p.IdBase = b.IdBase) AS CliPdp,
               (SELECT SUM(CONVERT(DECIMAL(18, 2), p.Monto)) FROM #rp AS p WHERE p.IdBase = b.IdBase) AS MontoPdp,
               (SELECT COUNT(*) FROM #re AS e WHERE e.Fuente = 'M'
                  AND e.Momento >= b.FechaGeneracion AND e.Momento < b.VentanaFin) AS MaquinaEnVentana
        INTO #res FROM #rb AS b;
        

PRINT '--- 3.1 Por base ---';
SELECT IdCartera, Codigo, NombreArchivo, Canal, FechaGeneracion, EnCurso, Telefonos, Clientes, TelMarcados,
       CliMarcados, Intentos, IntentosHumano, IntentosMaquina, TelCef, CliCef, Pdp, MontoPdp, MaquinaEnVentana,
       CAST(100.0 * TelMarcados / NULLIF(Telefonos, 0) AS DECIMAL(6, 1)) AS PctCobertura,
       CAST(100.0 * CliCef / NULLIF(CliMarcados, 0) AS DECIMAL(6, 1)) AS PctContacto,
       CAST(100.0 * Pdp / NULLIF(CliCef, 0) AS DECIMAL(6, 1)) AS PctPdpSobreCef
FROM #res ORDER BY FechaGeneracion DESC;

PRINT '--- 3.2 Por tipo de base (según el nombre) y canal ---';
;WITH t AS (
    SELECT r.*, CASE
        WHEN r.NombreArchivo LIKE N'% PDP CAIDA MES %' THEN 'PDP CAIDA MES'
        WHEN r.NombreArchivo LIKE N'% PDP CAIDA HIST %' THEN 'PDP CAIDA HIST'
        WHEN r.NombreArchivo LIKE N'% SEG CAIDO MES %' THEN 'SEG CAIDO MES'
        WHEN r.NombreArchivo LIKE N'% SEG CAIDO HIST %' THEN 'SEG CAIDO HIST'
        WHEN r.NombreArchivo LIKE N'% CEF MES %' THEN 'CEF MES'
        WHEN r.NombreArchivo LIKE N'% CEF HIST %' THEN 'CEF HIST'
        WHEN r.NombreArchivo LIKE N'% NOC %' THEN 'NOC'
        WHEN r.NombreArchivo LIKE N'% MIX CONTACTO %' THEN 'MIX CONTACTO'
        ELSE 'NOMBRE ANTIGUO / OTRO' END AS Tipo
    FROM #res AS r WHERE r.EnCurso = 0
)
SELECT Tipo, Canal, COUNT(*) AS Bases, SUM(Telefonos) AS Telefonos, SUM(TelMarcados) AS TelMarcados,
       SUM(CliMarcados) AS CliMarcados, SUM(Intentos) AS Intentos, SUM(CliCef) AS CliCef, SUM(Pdp) AS Pdp, SUM(MontoPdp) AS MontoPdp,
       CAST(100.0 * SUM(TelMarcados) / NULLIF(SUM(Telefonos), 0) AS DECIMAL(6, 1)) AS PctCobertura,
       CAST(100.0 * SUM(CliCef) / NULLIF(SUM(CliMarcados), 0) AS DECIMAL(6, 1)) AS PctContacto,
       CAST(100.0 * SUM(TelCef) / NULLIF(SUM(Intentos), 0) AS DECIMAL(6, 2)) AS CefPor100Intentos
FROM t GROUP BY Tipo, Canal ORDER BY Tipo, Canal;

PRINT '--- 3.3 Por tramo de score de la base (según el nombre) ---';
SELECT CASE WHEN NombreArchivo LIKE N'% MIX SCORE %' THEN 'MIX SCORE'
            WHEN NombreArchivo LIKE N'% SCORE %' THEN SUBSTRING(NombreArchivo, CHARINDEX(N' SCORE ', NombreArchivo) + 1, 11)
            ELSE 'SIN DATO' END AS Score,
       COUNT(*) AS Bases, SUM(Telefonos) AS Telefonos, SUM(TelMarcados) AS TelMarcados, SUM(CliCef) AS CliCef,
       CAST(100.0 * SUM(CliCef) / NULLIF(SUM(CliMarcados), 0) AS DECIMAL(6, 1)) AS PctContacto
FROM #res WHERE EnCurso = 0
GROUP BY CASE WHEN NombreArchivo LIKE N'% MIX SCORE %' THEN 'MIX SCORE'
              WHEN NombreArchivo LIKE N'% SCORE %' THEN SUBSTRING(NombreArchivo, CHARINDEX(N' SCORE ', NombreArchivo) + 1, 11)
              ELSE 'SIN DATO' END
ORDER BY 1;
GO

PRINT '=== 4. Acierto del score por tramo (teléfono-día, últimos 7 días armados) ===';
IF OBJECT_ID('score.RendimientoDia') IS NOT NULL
BEGIN
    DECLARE @h DATE = (SELECT MAX(Fecha) FROM score.RendimientoDia);
    SELECT Tramo, SUM(Telefonos) AS TelefonoDias, SUM(Marcados) AS Marcados, SUM(Intentos) AS Intentos, SUM(Cef) AS Cef,
           CAST(100.0 * SUM(Marcados) / NULLIF(SUM(Telefonos), 0) AS DECIMAL(6, 1)) AS PctMarcados,
           CAST(100.0 * SUM(Cef) / NULLIF(SUM(Intentos), 0) AS DECIMAL(6, 2)) AS CefPor100Intentos,
           CAST(100.0 * SUM(R_Cef) / NULLIF(SUM(Marcados), 0) AS DECIMAL(6, 2)) AS PctMarcadosConCef
    FROM score.RendimientoDia
    WHERE Fecha > DATEADD(DAY, -7, @h)
    GROUP BY Tramo ORDER BY Tramo;
    -- por día: para ver si algún día quedó incompleto
    SELECT Fecha, SUM(Telefonos) AS TelefonoDias, SUM(Marcados) AS Marcados, SUM(Intentos) AS Intentos,
           SUM(IntentosMaquina) AS IntentosMaquina, SUM(Cef) AS Cef
    FROM score.RendimientoDia WHERE Fecha > DATEADD(DAY, -10, @h)
    GROUP BY Fecha ORDER BY Fecha DESC;
END;
GO

PRINT '=== 5. ¿Doble conteo? Gestiones humanas con una llamada de máquina al mismo teléfono 0-180 s antes ===';
DECLARE @dia DATE = (SELECT MAX(CAST(Fecha AS DATE)) FROM siscob.dbo.pgestion WITH (NOLOCK) WHERE Fecha < CAST(GETDATE() AS DATE));
IF OBJECT_ID('tempdb..#h') IS NOT NULL DROP TABLE #h;
IF OBJECT_ID('tempdb..#m') IS NOT NULL DROP TABLE #m;
SELECT g.idCartera, CONVERT(CHAR(9), g.telefono) AS Tel,
       CAST(CAST(g.Fecha AS DATE) AS DATETIME) + CAST(CAST(g.Hora AS TIME(0)) AS DATETIME) AS Momento
INTO #h FROM siscob.dbo.gestion AS g WITH (NOLOCK)
WHERE g.Fecha >= @dia AND g.Fecha < DATEADD(DAY, 1, @dia) AND g.telefono BETWEEN 900000000 AND 999999999;
SELECT g.idCartera, CONVERT(CHAR(9), g.telefono) AS Tel,
       CAST(CAST(g.Fecha AS DATE) AS DATETIME) + CAST(CAST(g.Hora AS TIME(0)) AS DATETIME) AS Momento
INTO #m FROM siscob.dbo.pgestion AS g WITH (NOLOCK)
WHERE g.Fecha >= @dia AND g.Fecha < DATEADD(DAY, 1, @dia) AND g.telefono BETWEEN 900000000 AND 999999999;
CREATE INDEX IX_m ON #m (Tel, idCartera, Momento);
SELECT @dia AS Dia, COUNT(*) AS GestionesHumanas,
       SUM(CASE WHEN EXISTS (SELECT 1 FROM #m AS m WHERE m.Tel = h.Tel AND m.idCartera = h.idCartera
                             AND m.Momento BETWEEN DATEADD(SECOND, -180, h.Momento) AND h.Momento) THEN 1 ELSE 0 END) AS ConLlamadaMaquinaAntes,
       (SELECT COUNT(*) FROM #m) AS LlamadasMaquina
FROM #h AS h;
GO
