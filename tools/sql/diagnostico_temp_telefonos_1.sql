/* =====================================================================================
   diagnostico_temp_telefonos_1.sql · 24/11/2026 · SOLO LECTURA
   ¿Por qué TEMP_TELEFONOS (matriz antigua) tiene ~28 mil teléfonos de la 126 y el score ~27 mil?
   Compara por DNI + teléfono contra el universo del score (score.TelefonoUniverso) y el score del último corte
   (score.TelefonoScore). Cambia @IdCartera para ver otra cartera.
   ===================================================================================== */
USE CobAuto;
GO
DECLARE @IdCartera INT = 126;
DECLARE @Corte DATE = (SELECT MAX(FechaCorte) FROM score.TelefonoScore WHERE IdCartera = @IdCartera);

IF OBJECT_ID('tempdb..#tmp') IS NOT NULL DROP TABLE #tmp;
SELECT LTRIM(RTRIM(CONVERT(VARCHAR(20), t.DNI))) COLLATE DATABASE_DEFAULT AS DNI,
       CONVERT(CHAR(9), LTRIM(RTRIM(CONVERT(VARCHAR(20), t.TELEFONO)))) COLLATE DATABASE_DEFAULT AS Telefono,
       COUNT(*) AS Filas, COUNT(DISTINCT t.IDCLIENTE) AS IdClientes,
       MAX(t.PRIORIDAD) AS Prioridad, MAX(t.OSIPTEL) AS Osiptel, MAX(t.AÑO_FECH_TELF) AS AnioDato
INTO #tmp
FROM Desarrollo.dbo.TEMP_TELEFONOS AS t
WHERE t.IDCARTERA = @IdCartera
GROUP BY LTRIM(RTRIM(CONVERT(VARCHAR(20), t.DNI))), CONVERT(CHAR(9), LTRIM(RTRIM(CONVERT(VARCHAR(20), t.TELEFONO))));
CREATE CLUSTERED INDEX cx ON #tmp (DNI, Telefono);

IF OBJECT_ID('tempdb..#sco') IS NOT NULL DROP TABLE #sco;
SELECT s.DNI, s.Telefono, s.Descartado, s.Tramo
INTO #sco
FROM score.TelefonoScore AS s
WHERE s.FechaCorte = @Corte AND s.IdCartera = @IdCartera;
CREATE CLUSTERED INDEX cx ON #sco (DNI, Telefono);

-- 1. Totales de cada lado
SELECT 'TEMP_TELEFONOS (filas)' AS Fuente, SUM(Filas) AS Cantidad FROM #tmp
UNION ALL SELECT 'TEMP_TELEFONOS (DNI + teléfono distintos)', COUNT(*) FROM #tmp
UNION ALL SELECT 'TEMP_TELEFONOS (mismo DNI + teléfono en 2+ IdCliente)', COUNT(*) FROM #tmp WHERE IdClientes > 1
UNION ALL SELECT 'Universo score (todos)', COUNT(*) FROM score.TelefonoUniverso WHERE IdCartera = @IdCartera
UNION ALL SELECT 'Universo score (excluidos por lista negra)', COUNT(*) FROM score.TelefonoUniverso WHERE IdCartera = @IdCartera AND ExcluidoListaNegra = 1
UNION ALL SELECT CONCAT('Score del ', CONVERT(CHAR(10), @Corte, 103), ' (con score)'), COUNT(*) FROM #sco
UNION ALL SELECT 'Score: descartados (2+ equivocados)', COUNT(*) FROM #sco WHERE Descartado = 1
UNION ALL SELECT 'Score sin descartados (lo que entra al generador)', COUNT(*) FROM #sco WHERE Descartado = 0;

-- 2. Están en TEMP_TELEFONOS y no en el score: por qué
SELECT CASE
           WHEN u.DNI IS NULL THEN '1. No está en el universo (teléfono o cliente ya no está activo en SISCOB, u otro filtro)'
           WHEN u.ExcluidoListaNegra = 1 THEN '2. Excluido por lista negra de su banco'
           ELSE '3. En el universo pero sin score en el último corte (alta posterior al cálculo)'
       END AS Motivo,
       COUNT(*) AS Telefonos
FROM #tmp AS t
LEFT JOIN score.TelefonoUniverso AS u
       ON u.IdCartera = @IdCartera AND u.DNI = t.DNI AND u.Telefono = t.Telefono
WHERE NOT EXISTS (SELECT 1 FROM #sco AS s WHERE s.DNI = t.DNI AND s.Telefono = t.Telefono)
GROUP BY CASE
           WHEN u.DNI IS NULL THEN '1. No está en el universo (teléfono o cliente ya no está activo en SISCOB, u otro filtro)'
           WHEN u.ExcluidoListaNegra = 1 THEN '2. Excluido por lista negra de su banco'
           ELSE '3. En el universo pero sin score en el último corte (alta posterior al cálculo)'
       END
ORDER BY Motivo;

-- 2.1 Muestra de los que no están en el universo, con lo que dice siscob.dbo.telefonos hoy
SELECT TOP 30 t.DNI, t.Telefono, t.Prioridad, t.Osiptel, t.AnioDato,
       (SELECT COUNT(*) FROM siscob.dbo.telefonos AS f WITH (NOLOCK)
        WHERE LTRIM(RTRIM(f.DNI)) = t.DNI AND CONVERT(VARCHAR(20), f.telefono) = t.Telefono) AS EnTelefonosHoy,
       (SELECT MAX(c.Estado) FROM siscob.dbo.Cliente AS c WITH (NOLOCK)
        WHERE LTRIM(RTRIM(c.Dni)) = t.DNI AND c.IdCartera = @IdCartera) AS EstadoCliente
FROM #tmp AS t
WHERE NOT EXISTS (SELECT 1 FROM score.TelefonoUniverso AS u WHERE u.IdCartera = @IdCartera AND u.DNI = t.DNI AND u.Telefono = t.Telefono)
ORDER BY t.DNI;

-- 3. Están en el score y no en TEMP_TELEFONOS
SELECT CASE WHEN s.Descartado = 1 THEN 'Descartado' ELSE 'Activo' END AS EnScore, COUNT(*) AS Telefonos
FROM #sco AS s
WHERE NOT EXISTS (SELECT 1 FROM #tmp AS t WHERE t.DNI = s.DNI AND t.Telefono = s.Telefono)
GROUP BY CASE WHEN s.Descartado = 1 THEN 'Descartado' ELSE 'Activo' END;
GO
