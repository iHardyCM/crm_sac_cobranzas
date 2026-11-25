/* =====================================================================================
   SCORE TELEFÓNICO · ¿CÓMO LE FUE AL SCORE CON EL USO? (solo lectura)                  24/11/2026
   Para decidir qué optimizar con datos y no por intuición. No escribe nada.
   Guardar la salida en tools/salidas/diagnostico_score_uso_1.txt (Resultados en texto).

   0. Frescura: días de historial cargados y cortes de score calculados (¿se recalcula a diario?)
   1. Uso del generador desde el 14/11: bases, teléfonos enviados y su tramo
   2. Rendimiento de las bases por tramo y por orden en el cliente (mismo día de la base)
   3. Acierto del score por tramo: semana siguiente (como se calibró) y mismo día (como se usa)
   4. Dónde cayeron los CEF: qué tramo y qué orden tenían esos teléfonos (¿el orden acierta?)
   5. Intensidad: intentos por teléfono marcado según el tramo (¿se gasta marcación en D/E?)
   6. Clientes cuyo mejor teléfono es D o E (candidatos a búsqueda, no a más marcación)

   CEF del score = TITULAR + TERCERO_ACUERDO (lo calibrado). CEF paleta = N_CEF_SISCOB (TipoContacto del
   indicador, la regla del 20/11). Se muestran los dos.
   ===================================================================================== */
USE CobAuto;
SET NOCOUNT ON;

DECLARE @Desde DATE = '2026-11-14';
DECLARE @UltDia DATE = (SELECT MAX(Fecha) FROM score.TelefonoDiaControl);
-- Último corte con su semana completa en el historial, y último corte con su mismo día cargado
DECLARE @CorteSemana DATE = (SELECT MAX(FechaCorte) FROM score.TelefonoScore WHERE FechaCorte <= DATEADD(DAY, -6, @UltDia));
DECLARE @CorteDia DATE = (SELECT MAX(FechaCorte) FROM score.TelefonoScore WHERE FechaCorte <= @UltDia);

SELECT @UltDia AS HistorialHasta, @CorteSemana AS CorteParaSemana, @CorteDia AS CorteParaMismoDia;

/* ---------- 0. Frescura ---------- */
SELECT Fecha, EventosHumano, EventosMaquina, EventosCentralita, Filas, IndicadoresSinClasificar
FROM score.TelefonoDiaControl WHERE Fecha >= DATEADD(DAY, -14, @UltDia) ORDER BY Fecha;

SELECT FechaCorte, IdCartera, MAX(Version) AS Version, COUNT(*) AS Telefonos
FROM score.TelefonoScore WHERE FechaCorte >= @Desde
GROUP BY FechaCorte, IdCartera ORDER BY FechaCorte, IdCartera;

/* ---------- 1. Uso del generador ---------- */
SELECT CAST(b.FechaGeneracion AS DATE) AS Dia, b.IdCartera, b.Canal,
       COUNT(DISTINCT b.IdBase) AS Bases, COUNT(*) AS Telefonos, COUNT(DISTINCT d.DNI) AS Clientes,
       SUM(CASE WHEN d.Tramo = 'A' THEN 1 ELSE 0 END) AS A, SUM(CASE WHEN d.Tramo = 'B' THEN 1 ELSE 0 END) AS B,
       SUM(CASE WHEN d.Tramo = 'C' THEN 1 ELSE 0 END) AS C, SUM(CASE WHEN d.Tramo = 'D' THEN 1 ELSE 0 END) AS D,
       SUM(CASE WHEN d.Tramo = 'E' THEN 1 ELSE 0 END) AS E,
       SUM(CASE WHEN d.OrdenCliente = 1 THEN 1 ELSE 0 END) AS PrimerTelefono
FROM score.Base AS b
INNER JOIN score.BaseDetalle AS d ON d.IdBase = b.IdBase
WHERE b.FechaGeneracion >= @Desde
GROUP BY CAST(b.FechaGeneracion AS DATE), b.IdCartera, b.Canal
ORDER BY Dia, b.IdCartera, b.Canal;

/* ---------- 2. Rendimiento de las bases (mismo día; un teléfono cuenta una vez por día) ---------- */
IF OBJECT_ID('tempdb..#env') IS NOT NULL DROP TABLE #env;
SELECT CAST(b.FechaGeneracion AS DATE) AS Dia, d.IdCartera, d.DNI, d.Telefono,
       MIN(d.Tramo) AS Tramo, MIN(d.OrdenCliente) AS OrdenCliente, MIN(b.Canal) AS Canal
INTO #env
FROM score.Base AS b
INNER JOIN score.BaseDetalle AS d ON d.IdBase = b.IdBase
WHERE b.FechaGeneracion >= @Desde AND CAST(b.FechaGeneracion AS DATE) <= @UltDia
GROUP BY CAST(b.FechaGeneracion AS DATE), d.IdCartera, d.DNI, d.Telefono;

SELECT e.Canal, e.Tramo,
       COUNT(*) AS Enviados,
       SUM(CASE WHEN t.IntentosHumano + t.IntentosMaquina > 0 THEN 1 ELSE 0 END) AS Marcados,
       SUM(CASE WHEN t.N_TITULAR + t.N_TERCERO_ACUERDO > 0 THEN 1 ELSE 0 END) AS ConCefScore,
       SUM(CASE WHEN t.N_CEF_SISCOB > 0 THEN 1 ELSE 0 END) AS ConCefPaleta,
       CAST(100.0 * SUM(CASE WHEN t.N_TITULAR + t.N_TERCERO_ACUERDO > 0 THEN 1 ELSE 0 END)
            / NULLIF(SUM(CASE WHEN t.IntentosHumano + t.IntentosMaquina > 0 THEN 1 ELSE 0 END), 0) AS DECIMAL(6, 2)) AS PctCefSobreMarcados
FROM #env AS e
LEFT JOIN score.TelefonoDia AS t
       ON t.Fecha = e.Dia AND t.IdCartera = e.IdCartera AND t.DNI = e.DNI AND t.Telefono = e.Telefono
GROUP BY e.Canal, e.Tramo
ORDER BY e.Canal, e.Tramo;

SELECT e.Canal, CASE WHEN e.OrdenCliente >= 3 THEN '3+' ELSE CONVERT(VARCHAR(2), e.OrdenCliente) END AS OrdenEnCliente,
       COUNT(*) AS Enviados,
       SUM(CASE WHEN t.IntentosHumano + t.IntentosMaquina > 0 THEN 1 ELSE 0 END) AS Marcados,
       SUM(CASE WHEN t.N_TITULAR + t.N_TERCERO_ACUERDO > 0 THEN 1 ELSE 0 END) AS ConCefScore
FROM #env AS e
LEFT JOIN score.TelefonoDia AS t
       ON t.Fecha = e.Dia AND t.IdCartera = e.IdCartera AND t.DNI = e.DNI AND t.Telefono = e.Telefono
GROUP BY e.Canal, CASE WHEN e.OrdenCliente >= 3 THEN '3+' ELSE CONVERT(VARCHAR(2), e.OrdenCliente) END
ORDER BY e.Canal, OrdenEnCliente;

/* ---------- 3. Acierto del score por tramo ---------- */
-- 3a. Semana siguiente al corte (la regla de la calibración)
IF OBJECT_ID('tempdb..#sem') IS NOT NULL DROP TABLE #sem;
SELECT IdCartera, DNI, Telefono,
       SUM(IntentosHumano + IntentosMaquina) AS Intentos,
       SUM(N_TITULAR + N_TERCERO_ACUERDO) AS Cef, SUM(N_CEF_SISCOB) AS CefPaleta
INTO #sem
FROM score.TelefonoDia
WHERE Fecha >= @CorteSemana AND Fecha < DATEADD(DAY, 7, @CorteSemana)
GROUP BY IdCartera, DNI, Telefono;
CREATE CLUSTERED INDEX IX_sem ON #sem (IdCartera, DNI, Telefono);

SELECT 'Semana siguiente' AS Ventana, @CorteSemana AS Corte, s.IdCartera, s.Tramo,
       COUNT(*) AS Marcados,
       CAST(100.0 * SUM(CASE WHEN w.Cef > 0 THEN 1 ELSE 0 END) / COUNT(*) AS DECIMAL(6, 2)) AS PctCefScore,
       CAST(100.0 * SUM(CASE WHEN w.CefPaleta > 0 THEN 1 ELSE 0 END) / COUNT(*) AS DECIMAL(6, 2)) AS PctCefPaleta,
       CAST(AVG(CAST(w.Intentos AS FLOAT)) AS DECIMAL(8, 2)) AS IntentosPorTelefono
FROM score.TelefonoScore AS s
INNER JOIN #sem AS w ON w.IdCartera = s.IdCartera AND w.DNI = s.DNI AND w.Telefono = s.Telefono
WHERE s.FechaCorte = @CorteSemana AND w.Intentos > 0
GROUP BY s.IdCartera, s.Tramo
ORDER BY s.IdCartera, s.Tramo;

-- 3b. Mismo día del corte (como se usan las bases: duran un día)
IF OBJECT_ID('tempdb..#dia') IS NOT NULL DROP TABLE #dia;
SELECT IdCartera, DNI, Telefono, IntentosHumano + IntentosMaquina AS Intentos,
       N_TITULAR + N_TERCERO_ACUERDO AS Cef, N_CEF_SISCOB AS CefPaleta
INTO #dia
FROM score.TelefonoDia WHERE Fecha = @CorteDia;
CREATE CLUSTERED INDEX IX_dia ON #dia (IdCartera, DNI, Telefono);

SELECT 'Mismo día' AS Ventana, @CorteDia AS Corte, s.Tramo,
       COUNT(*) AS Marcados,
       CAST(100.0 * SUM(CASE WHEN w.Cef > 0 THEN 1 ELSE 0 END) / COUNT(*) AS DECIMAL(6, 2)) AS PctCefScore,
       CAST(100.0 * SUM(CASE WHEN w.CefPaleta > 0 THEN 1 ELSE 0 END) / COUNT(*) AS DECIMAL(6, 2)) AS PctCefPaleta
FROM score.TelefonoScore AS s
INNER JOIN #dia AS w ON w.IdCartera = s.IdCartera AND w.DNI = s.DNI AND w.Telefono = s.Telefono
WHERE s.FechaCorte = @CorteDia AND w.Intentos > 0
GROUP BY s.Tramo
ORDER BY s.Tramo;

/* ---------- 4. Dónde cayeron los CEF de la semana (de los teléfonos que tuvieron CEF) ---------- */
SELECT s.IdCartera, s.Tramo,
       CASE WHEN s.OrdenCliente >= 3 THEN '3+' ELSE CONVERT(VARCHAR(2), s.OrdenCliente) END AS OrdenEnCliente,
       COUNT(*) AS TelefonosConCef
FROM score.TelefonoScore AS s
INNER JOIN #sem AS w ON w.IdCartera = s.IdCartera AND w.DNI = s.DNI AND w.Telefono = s.Telefono
WHERE s.FechaCorte = @CorteSemana AND w.Cef > 0
GROUP BY s.IdCartera, s.Tramo, CASE WHEN s.OrdenCliente >= 3 THEN '3+' ELSE CONVERT(VARCHAR(2), s.OrdenCliente) END
ORDER BY s.IdCartera, s.Tramo, OrdenEnCliente;

-- CEF en teléfonos que NO estaban en el score del corte (números nuevos o fuera del universo)
SELECT w.IdCartera, COUNT(*) AS TelefonosConCefFueraDelScore
FROM #sem AS w
WHERE w.Cef > 0
  AND NOT EXISTS (SELECT 1 FROM score.TelefonoScore AS s
                  WHERE s.FechaCorte = @CorteSemana AND s.IdCartera = w.IdCartera AND s.DNI = w.DNI AND s.Telefono = w.Telefono)
GROUP BY w.IdCartera ORDER BY w.IdCartera;

/* ---------- 5. Intensidad: dónde se gasta la marcación en la semana ---------- */
SELECT s.Tramo,
       COUNT(*) AS TelefonosMarcados,
       SUM(w.Intentos) AS Intentos,
       CAST(100.0 * SUM(w.Intentos) / SUM(SUM(w.Intentos)) OVER () AS DECIMAL(5, 1)) AS PctDeLosIntentos,
       SUM(CASE WHEN w.Cef > 0 THEN 1 ELSE 0 END) AS TelefonosConCef,
       CAST(100.0 * SUM(CASE WHEN w.Cef > 0 THEN 1 ELSE 0 END) / SUM(SUM(CASE WHEN w.Cef > 0 THEN 1 ELSE 0 END)) OVER () AS DECIMAL(5, 1)) AS PctDeLosCef
FROM score.TelefonoScore AS s
INNER JOIN #sem AS w ON w.IdCartera = s.IdCartera AND w.DNI = s.DNI AND w.Telefono = s.Telefono
WHERE s.FechaCorte = @CorteSemana AND w.Intentos > 0
GROUP BY s.Tramo
ORDER BY s.Tramo;

/* ---------- 6. Clientes cuyo mejor teléfono es D o E (último corte) ---------- */
DECLARE @Ultimo DATE = (SELECT MAX(FechaCorte) FROM score.TelefonoScore);
SELECT s.IdCartera, COUNT(*) AS Clientes,
       SUM(CASE WHEN s.Tramo IN ('D', 'E') THEN 1 ELSE 0 END) AS MejorEnDoE,
       CAST(100.0 * SUM(CASE WHEN s.Tramo IN ('D', 'E') THEN 1 ELSE 0 END) / COUNT(*) AS DECIMAL(5, 1)) AS Pct
FROM score.TelefonoScore AS s
WHERE s.FechaCorte = @Ultimo AND s.OrdenCliente = 1
GROUP BY s.IdCartera ORDER BY s.IdCartera;
