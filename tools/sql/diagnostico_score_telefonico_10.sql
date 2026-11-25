/* =====================================================================================
   SCORE TELEFÓNICO · DIAGNÓSTICO 10 — ¿"NO CONTACTO" ES EL EQUIVOCADO DE COMPARTAMOS?
   Fecha: 14/11/2026 · Solo lectura.

   Contexto: en Compartamos (124, 126, 128, 133, 139, 144) no existe la tipificación de equivocado ni la de
   "no existe". Hardy sospecha que los asesores usan 1032 "NO CONTACTO" (NOC) para el número equivocado,
   porque esa tipificación pone el teléfono en rojo. Hoy el score la cuenta como "no contesta".

   Qué mide:
     1. Qué tipificaciones se usan en 90 días, por cartera, y qué resultado les da el score.
     2. Qué pasa con el teléfono en los 30 días siguientes a cada tipificación: si se vuelve a marcar
        y si se logra contacto directo (titular o tercero con acuerdo).
        Si "NO CONTACTO" se comporta como el EQUIVOCADO de las otras carteras (casi nunca vuelve a dar
        contacto) y distinto de "NO CONTESTA", la sospecha se confirma.
     3. Color actual del teléfono según la última tipificación humana del par cliente + teléfono.
     4. Las columnas de esas tipificaciones en siscob.dbo.Indicador (por si ahí está la regla del color).

   No muestra DNI ni teléfonos. Guardar la salida en tools/salidas/resultados_diagnostico_score_10.txt
   ===================================================================================== */

USE CobAuto;
SET NOCOUNT ON;

DECLARE @Hoy DATE = CAST(GETDATE() AS DATE);
DECLARE @Ini90 DATE = DATEADD(DAY, -90, @Hoy);
DECLARE @FinObs DATE = DATEADD(DAY, -30, @Hoy);   -- eventos hasta aquí, para tener 30 días después

IF OBJECT_ID('tempdb..#comp') IS NOT NULL DROP TABLE #comp;
CREATE TABLE #comp (IdCartera INT PRIMARY KEY);
INSERT INTO #comp VALUES (124), (126), (128), (133), (139), (144);

/* Gestiones humanas de 90 días de las carteras del score, con su tipificación y el resultado del score */
IF OBJECT_ID('tempdb..#g') IS NOT NULL DROP TABLE #g;
SELECT g.idCartera AS IdCartera,
       LEFT(LTRIM(RTRIM(ISNULL(COALESCE(NULLIF(LTRIM(RTRIM(g.DNI)), ''), c.Dni), ''))), 20) COLLATE DATABASE_DEFAULT AS DNI,
       CONVERT(CHAR(9), g.telefono) COLLATE DATABASE_DEFAULT AS Telefono,
       CAST(g.Fecha AS DATE) AS Fecha,
       g.IdGestion,
       g.IdIndicador,
       ISNULL(r.Resultado, 'SIN_CLASIFICAR') AS Resultado,
       CAST(CASE WHEN g.idCartera IN (SELECT IdCartera FROM #comp) THEN 1 ELSE 0 END AS BIT) AS EsCompartamos
INTO #g
FROM siscob.dbo.gestion AS g WITH (NOLOCK)
LEFT JOIN siscob.dbo.Cliente AS c WITH (NOLOCK) ON c.IdCliente = g.IdCliente
LEFT JOIN score.IndicadorResultado AS r ON r.IdIndicador = g.IdIndicador
WHERE g.Fecha >= @Ini90 AND g.Fecha < @Hoy
  AND g.idCartera IN (SELECT IdCartera FROM ControlCobranza.bl.EntidadCartera)
  AND g.telefono BETWEEN 900000000 AND 999999999;

DELETE FROM #g WHERE DNI = '';
CREATE CLUSTERED INDEX IX_g ON #g (IdCartera, DNI, Telefono, Fecha);

/* 1. Tipificaciones usadas en 90 días (Compartamos completo; en las demás, solo equivocado y no contesta) */
SELECT g.IdCartera, g.IdIndicador, ir.Descripcion, ir.TipoContactoSiscob, g.Resultado AS resultado_score,
       COUNT(*) AS gestiones,
       CAST(100.0 * COUNT(*) / MAX(tot.n) AS DECIMAL(6, 2)) AS pct_de_la_cartera
FROM #g AS g
INNER JOIN (SELECT IdCartera, COUNT(*) AS n FROM #g GROUP BY IdCartera) AS tot ON tot.IdCartera = g.IdCartera
LEFT JOIN score.IndicadorResultado AS ir ON ir.IdIndicador = g.IdIndicador
WHERE g.EsCompartamos = 1 OR g.Resultado IN ('EQUIVOCADO', 'NO_EXISTE')
GROUP BY g.IdCartera, g.IdIndicador, ir.Descripcion, ir.TipoContactoSiscob, g.Resultado
ORDER BY g.IdCartera, gestiones DESC;

/* 2. Qué pasa en los 30 días siguientes.
      Grupo por par cliente + teléfono: la primera vez que recibió esa tipificación entre el día -90 y el -30. */
IF OBJECT_ID('tempdb..#pares') IS NOT NULL DROP TABLE #pares;
SELECT x.Grupo, x.IdCartera, x.DNI, x.Telefono, MIN(x.Fecha) AS Fecha0
INTO #pares
FROM (
    SELECT CASE
             WHEN g.EsCompartamos = 1 AND g.IdIndicador = 1032 THEN 'COMPARTAMOS · 1032 NO CONTACTO'
             WHEN g.EsCompartamos = 1 AND g.IdIndicador = 1031 THEN 'COMPARTAMOS · 1031 NO CONTESTA'
             WHEN g.EsCompartamos = 1 AND g.IdIndicador = 919  THEN 'COMPARTAMOS · 919 MENSAJE A TERCERO'
             WHEN g.EsCompartamos = 0 AND g.Resultado = 'EQUIVOCADO'  THEN 'OTRAS · EQUIVOCADO'
             WHEN g.EsCompartamos = 0 AND g.Resultado = 'NO_CONTESTA' THEN 'OTRAS · NO CONTESTA'
             WHEN g.EsCompartamos = 0 AND g.Resultado = 'TERCERO'     THEN 'OTRAS · MENSAJE A TERCERO'
           END AS Grupo,
           g.IdCartera, g.DNI, g.Telefono, g.Fecha
    FROM #g AS g
    WHERE g.Fecha < @FinObs
) AS x
WHERE x.Grupo IS NOT NULL
GROUP BY x.Grupo, x.IdCartera, x.DNI, x.Telefono;

CREATE CLUSTERED INDEX IX_p ON #pares (IdCartera, DNI, Telefono);

-- Lo que pasó después, del historial del score (incluye máquina y centralita)
IF OBJECT_ID('tempdb..#despues') IS NOT NULL DROP TABLE #despues;
SELECT p.Grupo, p.IdCartera, p.DNI, p.Telefono,
       SUM(d.IntentosHumano + d.IntentosMaquina) AS Intentos30,
       SUM(d.N_TITULAR + d.N_TERCERO_ACUERDO) AS Cef30,
       SUM(d.N_TERCERO) AS Tercero30
INTO #despues
FROM #pares AS p
INNER JOIN score.TelefonoDia AS d
        ON d.IdCartera = p.IdCartera AND d.DNI = p.DNI AND d.Telefono = p.Telefono
       AND d.Fecha > p.Fecha0 AND d.Fecha <= DATEADD(DAY, 30, p.Fecha0)
WHERE d.Fecha > @Ini90
GROUP BY p.Grupo, p.IdCartera, p.DNI, p.Telefono;

SELECT p.Grupo,
       COUNT(*) AS pares,
       SUM(CASE WHEN ISNULL(a.Intentos30, 0) > 0 THEN 1 ELSE 0 END) AS remarcados_30d,
       CAST(100.0 * AVG(CASE WHEN ISNULL(a.Intentos30, 0) > 0 THEN 1.0 ELSE 0 END) AS DECIMAL(6, 2)) AS pct_remarcados,
       SUM(CASE WHEN ISNULL(a.Cef30, 0) > 0 THEN 1 ELSE 0 END) AS con_contacto_directo_30d,
       -- La medida que importa: de los que se volvieron a marcar, cuántos dieron contacto directo
       CAST(100.0 * SUM(CASE WHEN ISNULL(a.Cef30, 0) > 0 THEN 1 ELSE 0 END)
            / NULLIF(SUM(CASE WHEN ISNULL(a.Intentos30, 0) > 0 THEN 1 ELSE 0 END), 0) AS DECIMAL(6, 2)) AS pct_contacto_de_remarcados,
       CAST(100.0 * SUM(CASE WHEN ISNULL(a.Tercero30, 0) > 0 THEN 1 ELSE 0 END)
            / NULLIF(SUM(CASE WHEN ISNULL(a.Intentos30, 0) > 0 THEN 1 ELSE 0 END), 0) AS DECIMAL(6, 2)) AS pct_tercero_de_remarcados
FROM #pares AS p
LEFT JOIN #despues AS a ON a.Grupo = p.Grupo AND a.IdCartera = p.IdCartera AND a.DNI = p.DNI AND a.Telefono = p.Telefono
GROUP BY p.Grupo
ORDER BY p.Grupo;

-- Lo mismo por cartera de Compartamos (para ver si el uso de "NO CONTACTO" cambia entre carteras)
SELECT p.IdCartera, p.Grupo,
       COUNT(*) AS pares,
       CAST(100.0 * AVG(CASE WHEN ISNULL(a.Intentos30, 0) > 0 THEN 1.0 ELSE 0 END) AS DECIMAL(6, 2)) AS pct_remarcados,
       CAST(100.0 * SUM(CASE WHEN ISNULL(a.Cef30, 0) > 0 THEN 1 ELSE 0 END)
            / NULLIF(SUM(CASE WHEN ISNULL(a.Intentos30, 0) > 0 THEN 1 ELSE 0 END), 0) AS DECIMAL(6, 2)) AS pct_contacto_de_remarcados
FROM #pares AS p
LEFT JOIN #despues AS a ON a.Grupo = p.Grupo AND a.IdCartera = p.IdCartera AND a.DNI = p.DNI AND a.Telefono = p.Telefono
WHERE p.IdCartera IN (SELECT IdCartera FROM #comp)
GROUP BY p.IdCartera, p.Grupo
ORDER BY p.IdCartera, p.Grupo;

/* 3. Color actual del teléfono según la última tipificación humana (universo de hoy) */
;WITH ult AS (
    SELECT g.IdCartera, g.DNI, g.Telefono, g.IdIndicador, g.Resultado, g.EsCompartamos,
           ROW_NUMBER() OVER (PARTITION BY g.IdCartera, g.DNI, g.Telefono ORDER BY g.Fecha DESC, g.IdGestion DESC) AS rn
    FROM #g AS g
)
SELECT k.ultima_tipificacion,
       COUNT(*) AS telefonos,
       SUM(CASE WHEN t.PrioridadColor = 'V' THEN 1 ELSE 0 END) AS V,
       SUM(CASE WHEN t.PrioridadColor = 'A' THEN 1 ELSE 0 END) AS A,
       SUM(CASE WHEN t.PrioridadColor = 'T' THEN 1 ELSE 0 END) AS T,
       SUM(CASE WHEN t.PrioridadColor = 'R' THEN 1 ELSE 0 END) AS R,
       SUM(CASE WHEN t.PrioridadColor = 'F' THEN 1 ELSE 0 END) AS F,
       SUM(CASE WHEN t.PrioridadColor IN ('P', 'Q') THEN 1 ELSE 0 END) AS PQ,
       SUM(CASE WHEN t.PrioridadColor IS NULL OR t.PrioridadColor NOT IN ('V', 'A', 'T', 'R', 'F', 'P', 'Q') THEN 1 ELSE 0 END) AS otro,
       CAST(100.0 * AVG(CASE WHEN t.PrioridadColor = 'R' THEN 1.0 ELSE 0 END) AS DECIMAL(6, 2)) AS pct_rojo
FROM ult AS u
CROSS APPLY (SELECT CASE
         WHEN u.EsCompartamos = 1 AND u.IdIndicador = 1032 THEN 'COMPARTAMOS · 1032 NO CONTACTO'
         WHEN u.EsCompartamos = 1 AND u.IdIndicador = 1031 THEN 'COMPARTAMOS · 1031 NO CONTESTA'
         WHEN u.EsCompartamos = 1 AND u.IdIndicador = 919  THEN 'COMPARTAMOS · 919 MENSAJE A TERCERO'
         WHEN u.EsCompartamos = 1 AND u.Resultado = 'TITULAR' THEN 'COMPARTAMOS · CONTACTO TITULAR'
         WHEN u.EsCompartamos = 0 AND u.Resultado = 'EQUIVOCADO'  THEN 'OTRAS · EQUIVOCADO'
         WHEN u.EsCompartamos = 0 AND u.Resultado = 'NO_CONTESTA' THEN 'OTRAS · NO CONTESTA'
         WHEN u.EsCompartamos = 0 AND u.Resultado = 'TITULAR'     THEN 'OTRAS · CONTACTO TITULAR'
       END AS ultima_tipificacion) AS k
INNER JOIN score.TelefonoUniverso AS t
        ON t.IdCartera = u.IdCartera AND t.DNI = u.DNI AND t.Telefono = u.Telefono
WHERE u.rn = 1 AND k.ultima_tipificacion IS NOT NULL
GROUP BY k.ultima_tipificacion
ORDER BY k.ultima_tipificacion;

/* 4. La tabla de tipificaciones de SISCOB para estos códigos (todas sus columnas) */
SELECT *
FROM siscob.dbo.Indicador WITH (NOLOCK)
WHERE IdIndicador IN (1031, 1032, 919, 1132, 973, 1200, 1073, 1133);
GO
