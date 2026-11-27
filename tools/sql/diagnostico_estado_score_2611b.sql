/* =====================================================================================
   diagnostico_estado_score_2611b.sql  ·  solo lectura  ·  1-2 min
   Completa diagnostico_estado_score_2611.sql (la sección 5 falló):
     A. ¿Llegó el SAC de hoy?
     B. ¿Qué pasó con las llamadas de máquina del 23/11 y de hoy en la copia local de SISCOB?
     C. ¿Una llamada del predictivo que llega a un asesor se cuenta dos veces (pgestion + gestion)?
     D. ¿La centralita repite las llamadas de pgestion? (los filtros "Gestiones del teléfono"
        suman humana + máquina + centralita; el score no usa centralita en sus intentos)
   Ejecutar con Resultados a texto (Ctrl+T) y guardar en tools/salidas/resultado_estado_score_2611b.txt
   ===================================================================================== */
SET NOCOUNT ON;
SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED;

PRINT '=== A. SAC en origen (Desarrollo.dbo.SAC_CAR_BIZNESCOB) ===';
SELECT CAST(FechaCarga AS DATE) AS DiaCarga, COUNT_BIG(*) AS Filas,
       MIN(FechaCarga) AS Primera, MAX(FechaCarga) AS Ultima
FROM Desarrollo.dbo.SAC_CAR_BIZNESCOB WITH (NOLOCK)
GROUP BY CAST(FechaCarga AS DATE)
ORDER BY DiaCarga DESC;
IF OBJECT_ID('score.SacCarga') IS NOT NULL SELECT TOP (3) * FROM score.SacCarga ORDER BY FechaSac DESC;
GO

PRINT '=== B.1 Llamadas por día (copia local de SISCOB) ===';
DECLARE @d10 DATE = DATEADD(DAY, -10, CAST(GETDATE() AS DATE));
;WITH M AS (SELECT CAST(Fecha AS DATE) AS Dia, COUNT_BIG(*) AS Maquina, MAX(CAST(Hora AS TIME(0))) AS UltimaHoraMaquina
            FROM siscob.dbo.pgestion WITH (NOLOCK) WHERE Fecha >= @d10 GROUP BY CAST(Fecha AS DATE)),
      H AS (SELECT CAST(Fecha AS DATE) AS Dia, COUNT_BIG(*) AS Humana, MAX(CAST(Hora AS TIME(0))) AS UltimaHoraHumana
            FROM siscob.dbo.gestion WITH (NOLOCK) WHERE Fecha >= @d10 GROUP BY CAST(Fecha AS DATE))
SELECT COALESCE(m.Dia, h.Dia) AS Dia, DATENAME(WEEKDAY, COALESCE(m.Dia, h.Dia)) AS DiaSemana,
       ISNULL(m.Maquina, 0) AS Maquina, ISNULL(h.Humana, 0) AS Humana, m.UltimaHoraMaquina, h.UltimaHoraHumana
FROM M AS m FULL JOIN H AS h ON h.Dia = m.Dia
ORDER BY Dia DESC;

PRINT '=== B.2 23/11 por cartera: humana, máquina (pgestion) y centralita ===';
;WITH H AS (SELECT idCartera, COUNT_BIG(*) AS Humana FROM siscob.dbo.gestion WITH (NOLOCK)
            WHERE Fecha >= '2026-11-23' AND Fecha < '2026-11-24' GROUP BY idCartera),
      M AS (SELECT idCartera, COUNT_BIG(*) AS Maquina FROM siscob.dbo.pgestion WITH (NOLOCK)
            WHERE Fecha >= '2026-11-23' AND Fecha < '2026-11-24' GROUP BY idCartera),
      C AS (SELECT TRY_CONVERT(INT, idCartera) AS idCartera, COUNT_BIG(*) AS Centralita
            FROM Desarrollo.dbo.CENTRALITA WITH (NOLOCK)
            WHERE [start] >= '2026-11-23' AND [start] < '2026-11-24' GROUP BY TRY_CONVERT(INT, idCartera))
SELECT COALESCE(h.idCartera, m.idCartera, c.idCartera) AS IdCartera,
       ISNULL(h.Humana, 0) AS Humana, ISNULL(m.Maquina, 0) AS Maquina, ISNULL(c.Centralita, 0) AS Centralita
FROM H AS h FULL JOIN M AS m ON m.idCartera = h.idCartera
FULL JOIN C AS c ON c.idCartera = COALESCE(h.idCartera, m.idCartera)
ORDER BY IdCartera;
GO

PRINT '=== C. Predictivo que llega al asesor: ¿la misma llamada está en pgestion y en gestion? ===';
PRINT '    (gestión humana con una llamada de máquina al mismo teléfono y cartera 0-180 s antes; último día completo con máquina)';
DECLARE @dia DATE = (SELECT MAX(CAST(Fecha AS DATE)) FROM siscob.dbo.pgestion WITH (NOLOCK)
                     WHERE Fecha >= DATEADD(DAY, -10, CAST(GETDATE() AS DATE)) AND Fecha < CAST(GETDATE() AS DATE));
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

SELECT @dia AS Dia, h.idCartera,
       COUNT(*) AS GestionesHumanas,
       SUM(CASE WHEN x.Hay IS NOT NULL THEN 1 ELSE 0 END) AS ConMaquinaAntes,
       CAST(100.0 * SUM(CASE WHEN x.Hay IS NOT NULL THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0) AS DECIMAL(5, 1)) AS PctConMaquinaAntes
FROM #h AS h
OUTER APPLY (SELECT TOP (1) 1 AS Hay FROM #m AS m
             WHERE m.Tel = h.Tel AND m.idCartera = h.idCartera
               AND m.Momento BETWEEN DATEADD(SECOND, -180, h.Momento) AND h.Momento) AS x
GROUP BY ROLLUP (h.idCartera)
ORDER BY CASE WHEN h.idCartera IS NULL THEN 1 ELSE 0 END, h.idCartera;
SELECT @dia AS Dia, (SELECT COUNT(*) FROM #m) AS LlamadasMaquina, (SELECT COUNT(*) FROM #h) AS GestionesHumanas;
GO

PRINT '=== D. ¿La centralita repite pgestion? (último día con ambas fuentes, mismo teléfono y cartera ±90 s) ===';
DECLARE @diaC DATE = (SELECT MAX(Fecha) FROM score.TelefonoDiaControl WHERE EventosMaquina > 0 AND EventosCentralita > 0);
IF OBJECT_ID('tempdb..#m2') IS NOT NULL DROP TABLE #m2;
IF OBJECT_ID('tempdb..#c2') IS NOT NULL DROP TABLE #c2;
SELECT g.idCartera, CONVERT(CHAR(9), g.telefono) AS Tel,
       CAST(CAST(g.Fecha AS DATE) AS DATETIME) + CAST(CAST(g.Hora AS TIME(0)) AS DATETIME) AS Momento
INTO #m2 FROM siscob.dbo.pgestion AS g WITH (NOLOCK)
WHERE g.Fecha >= @diaC AND g.Fecha < DATEADD(DAY, 1, @diaC) AND g.telefono BETWEEN 900000000 AND 999999999;
SELECT TRY_CONVERT(INT, ce.idCartera) AS idCartera, CAST(RIGHT(LTRIM(RTRIM(ce.telefono)), 9) AS CHAR(9)) COLLATE DATABASE_DEFAULT AS Tel,
       CAST(ce.[start] AS DATETIME) AS Momento,
       CASE WHEN ce.anexo IS NULL OR LTRIM(RTRIM(ce.anexo)) IN (N'', N'0') THEN 0 ELSE 1 END AS LlegoAAsesor
INTO #c2 FROM Desarrollo.dbo.CENTRALITA AS ce WITH (NOLOCK)
WHERE ce.[start] >= @diaC AND ce.[start] < DATEADD(DAY, 1, @diaC);
CREATE INDEX IX_c2 ON #c2 (Tel, idCartera, Momento);

SELECT @diaC AS Dia,
       COUNT(*) AS LlamadasMaquina,
       SUM(CASE WHEN x.Hay IS NOT NULL THEN 1 ELSE 0 END) AS TambienEnCentralita,
       CAST(100.0 * SUM(CASE WHEN x.Hay IS NOT NULL THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0) AS DECIMAL(5, 1)) AS PctTambienEnCentralita
FROM #m2 AS m
OUTER APPLY (SELECT TOP (1) 1 AS Hay FROM #c2 AS c
             WHERE c.Tel = m.Tel AND c.idCartera = m.idCartera
               AND c.Momento BETWEEN DATEADD(SECOND, -90, m.Momento) AND DATEADD(SECOND, 90, m.Momento)) AS x;

SELECT @diaC AS Dia, LlegoAAsesor, COUNT(*) AS LlamadasCentralita,
       SUM(CASE WHEN x.Hay IS NOT NULL THEN 1 ELSE 0 END) AS TambienEnPgestion,
       CAST(100.0 * SUM(CASE WHEN x.Hay IS NOT NULL THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0) AS DECIMAL(5, 1)) AS PctTambienEnPgestion
FROM #c2 AS c
OUTER APPLY (SELECT TOP (1) 1 AS Hay FROM #m2 AS m
             WHERE m.Tel = c.Tel AND m.idCartera = c.idCartera
               AND m.Momento BETWEEN DATEADD(SECOND, -90, c.Momento) AND DATEADD(SECOND, 90, c.Momento)) AS x
GROUP BY LlegoAAsesor ORDER BY LlegoAAsesor;
GO
