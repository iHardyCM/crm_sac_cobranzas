/* =====================================================================================
   diagnostico_estado_score_2611c.sql  ·  solo lectura  ·  ~1 min
   Sección D de 2611b sin depender del esquema score (corre en cualquier base del servidor).
   ¿La centralita registra las mismas llamadas que pgestion? Los filtros "Gestiones del teléfono"
   suman humana + máquina + centralita; si se repiten, esos filtros cuentan doble.
   Ctrl+T y guardar en tools/salidas/resultado_estado_score_2611c.txt
   ===================================================================================== */
SET NOCOUNT ON;
SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED;

PRINT '=== D. ¿La centralita repite pgestion? (20/11, mismo teléfono y cartera ±90 s) ===';
DECLARE @diaC DATE = '2026-11-20';   -- viernes con máquina (pgestion) y centralita completas
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
