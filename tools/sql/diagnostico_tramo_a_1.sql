/* =====================================================================================
   SCORE TELEFÓNICO · ¿POR QUÉ NO SE MARCA EL TRAMO A? (solo lectura)              27/11/2026
   No escribe nada. Guardar la salida en tools/salidas/diagnostico_tramo_a_1.txt (Resultados en texto).

   Contexto: el tramo A da 5.02 CEF por cada 100 intentos (B 1.76, C 0.87, D 0.49, E 0.16),
   pero un día cualquiera solo se marca alrededor del 25 % de sus teléfonos.
   Antes de cambiar el generador hay que saber POR QUÉ no se marcan.

   Unidad: teléfono-día del tramo A (un teléfono A contado una vez por cada día).
   Días: los últimos @Dias días completos que tienen score del día y llamadas de máquina cargadas
   (los días sin máquina harían parecer "no marcados" a teléfonos que sí se llamaron).

   0. Días usados
   1. Tramo A por cartera y por canal de la base en la que salió ese día (1b: por orden en el cliente)
   2. Motivo por el que un teléfono A NO se marcó (excluyente, en este orden):
        1 Descartado en el score
        2 El cliente ya tuvo CEF ese día por otro teléfono
        3 El cliente tenía PDP vigente ese día
        4 El cliente sí fue marcado ese día por otro teléfono (sin CEF)
        5 Estaba en una base de llamada (PRED/IVR) y no se marcó   -> faltó marcación
        6 Solo estaba en una base SMS
        7 El cliente tuvo CEF en los 3 días anteriores
        8 No estuvo en ninguna base y no hay motivo visible        -> oportunidad
   3. Tamaño diario de la oportunidad (motivos 5 y 8) y estimación de CEF (marcada como estimación)
   4. Dónde se van hoy los intentos (por tramo y cartera, promedio diario)
   5. Teléfonos A en bases PRED: ¿se marcan menos los que van al final del archivo?
   ===================================================================================== */
USE CobAuto;
GO
SET NOCOUNT ON;
GO

DECLARE @Dias INT = 7;

/* ---------------------------------------------------------------- 0. días usados */
DECLARE @d TABLE (Fecha DATE PRIMARY KEY);
INSERT INTO @d (Fecha)
SELECT TOP (@Dias) c.Fecha
FROM score.TelefonoDiaControl AS c
WHERE c.Fecha < CAST(GETDATE() AS DATE)
  AND c.EventosMaquina > 0
  AND EXISTS (SELECT 1 FROM score.TelefonoScore AS s WHERE s.FechaCorte = c.Fecha)
ORDER BY c.Fecha DESC;

DECLARE @Desde DATE = (SELECT MIN(Fecha) FROM @d), @Hasta DATE = (SELECT MAX(Fecha) FROM @d);
DECLARE @N INT = (SELECT COUNT(*) FROM @d);

PRINT '=== 0. Días usados (completos, con score del día y con máquina) ===';
SELECT c.Fecha, DATENAME(WEEKDAY, c.Fecha) AS Dia, c.EventosHumano, c.EventosMaquina, c.EventosCentralita
FROM score.TelefonoDiaControl AS c INNER JOIN @d AS d ON d.Fecha = c.Fecha
ORDER BY c.Fecha;

/* ---------------------------------------------------------------- teléfonos A por día */
IF OBJECT_ID('tempdb..#a') IS NOT NULL DROP TABLE #a;
CREATE TABLE #a (
    Fecha DATE NOT NULL, IdCartera INT NOT NULL,
    DNI VARCHAR(20) COLLATE DATABASE_DEFAULT NOT NULL, Telefono CHAR(9) COLLATE DATABASE_DEFAULT NOT NULL,
    OrdenCliente SMALLINT NOT NULL, Descartado BIT NOT NULL,
    Marcado BIT NOT NULL DEFAULT 0, Intentos INT NOT NULL DEFAULT 0, Cef BIT NOT NULL DEFAULT 0,
    Canal VARCHAR(10) NULL, PosRelPred DECIMAL(9, 4) NULL,
    CliCefHoy BIT NOT NULL DEFAULT 0, CliMarcadoHoy BIT NOT NULL DEFAULT 0,
    CliCefPrevio BIT NOT NULL DEFAULT 0, CliPdp BIT NOT NULL DEFAULT 0,
    Motivo TINYINT NULL,
    PRIMARY KEY (Fecha, IdCartera, DNI, Telefono));

INSERT INTO #a (Fecha, IdCartera, DNI, Telefono, OrdenCliente, Descartado)
SELECT s.FechaCorte, s.IdCartera, s.DNI, s.Telefono, s.OrdenCliente, s.Descartado
FROM score.TelefonoScore AS s INNER JOIN @d AS d ON d.Fecha = s.FechaCorte
WHERE s.Tramo = 'A';

-- Llamadas de ese teléfono ese día (humano + máquina, como el score)
UPDATE a SET Marcado = CASE WHEN t.IntentosHumano + t.IntentosMaquina > 0 THEN 1 ELSE 0 END,
             Intentos = t.IntentosHumano + t.IntentosMaquina,
             Cef = CASE WHEN t.N_TITULAR + t.N_TERCERO_ACUERDO > 0 THEN 1 ELSE 0 END
FROM #a AS a
INNER JOIN score.TelefonoDia AS t
        ON t.Fecha = a.Fecha AND t.IdCartera = a.IdCartera AND t.DNI = a.DNI AND t.Telefono = a.Telefono;

-- Bases del periodo, una fila por teléfono-día: canal (prioridad PRED > IVR > SMS, como el rendimiento)
-- y la mejor posición relativa dentro de una base PRED (0 = primera fila, 1 = última).
IF OBJECT_ID('tempdb..#b') IS NOT NULL DROP TABLE #b;
SELECT CAST(x.FechaGeneracion AS DATE) AS Fecha, bd.IdCartera, bd.DNI, bd.Telefono,
       MIN(CASE x.Canal WHEN 'PRED' THEN 1 WHEN 'IVR' THEN 2 WHEN 'SMS' THEN 3 ELSE 4 END) AS Prioridad,
       MIN(CASE WHEN x.Canal = 'PRED' THEN 1.0 * bd.Posicion / NULLIF(x.Telefonos, 0) END) AS PosRelPred
INTO #b
FROM score.Base AS x
INNER JOIN score.BaseDetalle AS bd ON bd.IdBase = x.IdBase
WHERE x.FechaGeneracion >= @Desde AND x.FechaGeneracion < DATEADD(DAY, 1, @Hasta)
GROUP BY CAST(x.FechaGeneracion AS DATE), bd.IdCartera, bd.DNI, bd.Telefono;
CREATE CLUSTERED INDEX IX_b ON #b (Fecha, IdCartera, DNI, Telefono);

UPDATE a SET Canal = CASE b.Prioridad WHEN 1 THEN 'PRED' WHEN 2 THEN 'IVR' WHEN 3 THEN 'SMS' ELSE 'OTRO' END,
             PosRelPred = b.PosRelPred
FROM #a AS a
INNER JOIN #b AS b ON b.Fecha = a.Fecha AND b.IdCartera = a.IdCartera AND b.DNI = a.DNI AND b.Telefono = a.Telefono;

-- Lo que pasó con el CLIENTE (todos sus teléfonos) ese día y los 3 anteriores
IF OBJECT_ID('tempdb..#cli') IS NOT NULL DROP TABLE #cli;
SELECT t.Fecha, t.IdCartera, t.DNI,
       MAX(CASE WHEN t.IntentosHumano + t.IntentosMaquina > 0 THEN 1 ELSE 0 END) AS Marcado,
       MAX(CASE WHEN t.N_TITULAR + t.N_TERCERO_ACUERDO > 0 THEN 1 ELSE 0 END) AS Cef
INTO #cli
FROM score.TelefonoDia AS t
WHERE t.Fecha >= DATEADD(DAY, -3, @Desde) AND t.Fecha <= @Hasta
GROUP BY t.Fecha, t.IdCartera, t.DNI;
CREATE CLUSTERED INDEX IX_cli ON #cli (IdCartera, DNI, Fecha);

UPDATE a SET CliCefHoy = ISNULL(h.Cef, 0), CliMarcadoHoy = ISNULL(h.Marcado, 0)
FROM #a AS a
LEFT JOIN #cli AS h ON h.Fecha = a.Fecha AND h.IdCartera = a.IdCartera AND h.DNI = a.DNI;

UPDATE a SET CliCefPrevio = 1
FROM #a AS a
WHERE EXISTS (SELECT 1 FROM #cli AS p
              WHERE p.IdCartera = a.IdCartera AND p.DNI = a.DNI AND p.Cef = 1
                AND p.Fecha >= DATEADD(DAY, -3, a.Fecha) AND p.Fecha < a.Fecha);

-- PDP vigente ese día: registrada antes de terminar el día, con compromiso de ese día en adelante,
-- monto > 0 y todavía no pagada ese día (si se pagó después, ese día seguía vigente).
-- Se arma una vez para el periodo y solo para las carteras con teléfonos A.
IF OBJECT_ID('tempdb..#pdp') IS NOT NULL DROP TABLE #pdp;
SELECT cl.IdCartera, LTRIM(RTRIM(cl.Dni)) COLLATE DATABASE_DEFAULT AS DNI,
       CAST(cp.FechaGenero AS DATE) AS Genero, CAST(cp.FechaCompromiso AS DATE) AS Compromiso,
       CASE WHEN ISNULL(UPPER(LTRIM(RTRIM(cp.Pagado))), '') IN ('SI', 'S') THEN CAST(cp.FechaPago AS DATE) END AS PagadaEl
INTO #pdp
FROM siscob.dbo.COMPROMISO AS cp WITH (NOLOCK)
INNER JOIN siscob.dbo.Cliente AS cl WITH (NOLOCK) ON cl.IdCliente = cp.IdCliente
WHERE cp.Monto > 0
  AND cp.FechaCompromiso >= @Desde
  AND cp.FechaGenero < DATEADD(DAY, 1, @Hasta)
  AND cl.IdCartera IN (SELECT DISTINCT IdCartera FROM #a);
CREATE CLUSTERED INDEX IX_pdp ON #pdp (IdCartera, DNI);

UPDATE a SET CliPdp = 1
FROM #a AS a
WHERE EXISTS (SELECT 1 FROM #pdp AS p
              WHERE p.IdCartera = a.IdCartera AND p.DNI = a.DNI
                AND p.Genero <= a.Fecha AND p.Compromiso >= a.Fecha
                AND (p.PagadaEl IS NULL OR p.PagadaEl >= a.Fecha));

-- Motivo excluyente para los NO marcados
UPDATE #a SET Motivo = CASE
    WHEN Descartado = 1 THEN 1
    WHEN CliCefHoy = 1 THEN 2
    WHEN CliPdp = 1 THEN 3
    WHEN CliMarcadoHoy = 1 THEN 4
    WHEN Canal IN ('PRED', 'IVR') THEN 5
    WHEN Canal IN ('SMS', 'OTRO') THEN 6
    WHEN CliCefPrevio = 1 THEN 7
    ELSE 8 END
WHERE Marcado = 0;

/* ---------------------------------------------------------------- 1. tramo A por cartera y canal */
PRINT '=== 1. Tramo A: teléfono-días, marcados y canal de la base (última fila = total) ===';
SELECT IdCartera,
       COUNT(*) AS TelDiasA,
       COUNT(*) / NULLIF(@N, 0) AS TelA_PromDia,
       CAST(100.0 * SUM(CAST(Marcado AS INT)) / NULLIF(COUNT(*), 0) AS DECIMAL(5, 1)) AS PctMarcado,
       CAST(100.0 * SUM(CASE WHEN Canal IS NULL THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0) AS DECIMAL(5, 1)) AS PctSinBase,
       CAST(100.0 * SUM(CASE WHEN Canal = 'PRED' THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0) AS DECIMAL(5, 1)) AS PctEnPred,
       CAST(100.0 * SUM(CASE WHEN Canal = 'PRED' AND Marcado = 1 THEN 1 ELSE 0 END)
            / NULLIF(SUM(CASE WHEN Canal = 'PRED' THEN 1 ELSE 0 END), 0) AS DECIMAL(5, 1)) AS PctMarcadoSiEstaEnPred,
       SUM(CAST(Cef AS INT)) AS TelDiasConCef
FROM #a
GROUP BY ROLLUP (IdCartera)
ORDER BY GROUPING(IdCartera), IdCartera;

PRINT '=== 1b. Tramo A por orden del teléfono dentro del cliente ===';
SELECT CASE WHEN OrdenCliente >= 3 THEN '3+' ELSE CONVERT(VARCHAR(3), OrdenCliente) END AS Orden,
       COUNT(*) AS TelDiasA,
       CAST(100.0 * SUM(CAST(Marcado AS INT)) / NULLIF(COUNT(*), 0) AS DECIMAL(5, 1)) AS PctMarcado,
       CAST(100.0 * SUM(CASE WHEN Marcado = 0 AND CliMarcadoHoy = 1 THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0) AS DECIMAL(5, 1)) AS PctNoMarcadoPeroClienteSi
FROM #a
GROUP BY CASE WHEN OrdenCliente >= 3 THEN '3+' ELSE CONVERT(VARCHAR(3), OrdenCliente) END
ORDER BY Orden;

/* ---------------------------------------------------------------- 2. motivos */
PRINT '=== 2. Teléfonos A NO marcados: motivo (excluyente) ===';
SELECT a.Motivo,
       CASE a.Motivo
            WHEN 1 THEN 'Descartado en el score'
            WHEN 2 THEN 'Cliente ya con CEF ese día por otro teléfono'
            WHEN 3 THEN 'Cliente con PDP vigente'
            WHEN 4 THEN 'Cliente marcado ese día por otro teléfono'
            WHEN 5 THEN 'En base PRED/IVR y no se marcó (faltó marcación)'
            WHEN 6 THEN 'Solo en base SMS'
            WHEN 7 THEN 'Cliente con CEF en los 3 días anteriores'
            WHEN 8 THEN 'Sin base y sin motivo visible (oportunidad)' END AS Motivo_Texto,
       COUNT(*) AS TelDias,
       COUNT(*) / NULLIF(@N, 0) AS PromedioDia,
       CAST(100.0 * COUNT(*) / NULLIF(SUM(COUNT(*)) OVER (), 0) AS DECIMAL(5, 1)) AS PctDeNoMarcados,
       COUNT(DISTINCT CONCAT(a.IdCartera, '|', a.DNI)) AS ClientesDistintos
FROM #a AS a
WHERE a.Marcado = 0
GROUP BY a.Motivo
ORDER BY a.Motivo;

PRINT '=== 2b. Motivos por cartera (teléfono-días) ===';
SELECT IdCartera,
       SUM(CASE WHEN Motivo = 1 THEN 1 ELSE 0 END) AS M1_Descartado,
       SUM(CASE WHEN Motivo = 2 THEN 1 ELSE 0 END) AS M2_CefHoyOtroTel,
       SUM(CASE WHEN Motivo = 3 THEN 1 ELSE 0 END) AS M3_PdpVigente,
       SUM(CASE WHEN Motivo = 4 THEN 1 ELSE 0 END) AS M4_ClienteMarcadoOtroTel,
       SUM(CASE WHEN Motivo = 5 THEN 1 ELSE 0 END) AS M5_EnBaseNoMarcado,
       SUM(CASE WHEN Motivo = 6 THEN 1 ELSE 0 END) AS M6_SoloSms,
       SUM(CASE WHEN Motivo = 7 THEN 1 ELSE 0 END) AS M7_CefPrevio3d,
       SUM(CASE WHEN Motivo = 8 THEN 1 ELSE 0 END) AS M8_Oportunidad
FROM #a WHERE Marcado = 0
GROUP BY IdCartera ORDER BY IdCartera;

/* ---------------------------------------------------------------- 3. tamaño de la oportunidad */
PRINT '=== 3. Oportunidad diaria por cartera (motivos 5 y 8) ===';
PRINT '    CefEstimadoDia = teléfonos por día x CEF por teléfono A marcado de esa cartera en el periodo.';
PRINT '    ES UNA ESTIMACIÓN: supone que esos teléfonos rinden igual que los A que sí se marcaron.';
WITH tasa AS (
    SELECT IdCartera,
           1.0 * SUM(CAST(Cef AS INT)) / NULLIF(SUM(CAST(Marcado AS INT)), 0) AS CefPorMarcado,
           1.0 * SUM(Intentos) / NULLIF(SUM(CAST(Marcado AS INT)), 0) AS IntentosPorMarcado
    FROM #a GROUP BY IdCartera)
SELECT a.IdCartera,
       SUM(CASE WHEN a.Motivo = 8 THEN 1 ELSE 0 END) / NULLIF(@N, 0) AS M8_TelPorDia,
       COUNT(DISTINCT CASE WHEN a.Motivo = 8 THEN a.DNI END) AS M8_ClientesDistintosPeriodo,
       SUM(CASE WHEN a.Motivo = 5 THEN 1 ELSE 0 END) / NULLIF(@N, 0) AS M5_TelPorDia,
       CAST(MAX(t.CefPorMarcado) * 100 AS DECIMAL(6, 2)) AS PctCefPorAMarcado,
       CAST(MAX(t.IntentosPorMarcado) AS DECIMAL(6, 2)) AS IntentosPorAMarcado,
       CAST(SUM(CASE WHEN a.Motivo IN (5, 8) THEN 1 ELSE 0 END) * 1.0 / NULLIF(@N, 0) * MAX(t.CefPorMarcado) AS DECIMAL(10, 1)) AS CefEstimadoDia_ESTIMACION,
       CAST(SUM(CASE WHEN a.Motivo IN (5, 8) THEN 1 ELSE 0 END) * 1.0 / NULLIF(@N, 0) * MAX(t.IntentosPorMarcado) AS DECIMAL(10, 0)) AS IntentosNecesariosDia_ESTIMACION
FROM #a AS a INNER JOIN tasa AS t ON t.IdCartera = a.IdCartera
WHERE a.Marcado = 0
GROUP BY a.IdCartera
ORDER BY a.IdCartera;

/* ---------------------------------------------------------------- 4. dónde se van los intentos */
PRINT '=== 4. Intentos promedio por día, por cartera y tramo (score.RendimientoDia) ===';
SELECT r.IdCartera,
       SUM(CASE WHEN r.Tramo = 'A' THEN r.Intentos ELSE 0 END) / NULLIF(@N, 0) AS Int_A,
       SUM(CASE WHEN r.Tramo = 'B' THEN r.Intentos ELSE 0 END) / NULLIF(@N, 0) AS Int_B,
       SUM(CASE WHEN r.Tramo = 'C' THEN r.Intentos ELSE 0 END) / NULLIF(@N, 0) AS Int_C,
       SUM(CASE WHEN r.Tramo = 'D' THEN r.Intentos ELSE 0 END) / NULLIF(@N, 0) AS Int_D,
       SUM(CASE WHEN r.Tramo = 'E' THEN r.Intentos ELSE 0 END) / NULLIF(@N, 0) AS Int_E,
       SUM(CASE WHEN r.Tramo = 'SIN SCORE' THEN r.Intentos ELSE 0 END) / NULLIF(@N, 0) AS Int_SinScore,
       SUM(CASE WHEN r.Tramo IN ('D', 'E') THEN r.R_Cef ELSE 0 END) AS TelConCef_DE_Periodo
FROM score.RendimientoDia AS r INNER JOIN @d AS d ON d.Fecha = r.Fecha
GROUP BY r.IdCartera ORDER BY r.IdCartera;

/* ---------------------------------------------------------------- 5. posición en las bases PRED */
PRINT '=== 5. Teléfonos A en bases PRED: % marcado según su posición en el archivo (quintil 1 = arriba) ===';
SELECT CASE WHEN PosRelPred <= 0.2 THEN '1 (0-20 %)' WHEN PosRelPred <= 0.4 THEN '2 (20-40 %)'
            WHEN PosRelPred <= 0.6 THEN '3 (40-60 %)' WHEN PosRelPred <= 0.8 THEN '4 (60-80 %)'
            WHEN PosRelPred IS NOT NULL THEN '5 (80-100 %)' ELSE 'sin dato' END AS QuintilPosicion,
       COUNT(*) AS TelDiasA,
       CAST(100.0 * SUM(CAST(Marcado AS INT)) / NULLIF(COUNT(*), 0) AS DECIMAL(5, 1)) AS PctMarcado
FROM #a
WHERE Canal = 'PRED'
GROUP BY CASE WHEN PosRelPred <= 0.2 THEN '1 (0-20 %)' WHEN PosRelPred <= 0.4 THEN '2 (20-40 %)'
              WHEN PosRelPred <= 0.6 THEN '3 (40-60 %)' WHEN PosRelPred <= 0.8 THEN '4 (60-80 %)'
              WHEN PosRelPred IS NOT NULL THEN '5 (80-100 %)' ELSE 'sin dato' END
ORDER BY QuintilPosicion;

DROP TABLE #a;
DROP TABLE #b;
DROP TABLE #cli;
DROP TABLE #pdp;
GO
