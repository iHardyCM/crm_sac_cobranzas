/* =====================================================================================
   SCORE TELEFÓNICO · REVISIÓN DEL SCORE DEL DÍA (solo lectura)
   Fecha: 14/11/2026 · Versión de pesos 1 (publicada el 14/11 18:06)

   1. Por cartera: cuál es el MEJOR teléfono de cada cliente (tramo del teléfono con OrdenCliente = 1).
      Los clientes cuyo mejor teléfono está en D o E no tienen un número bueno: son candidatos a
      búsqueda de teléfonos, no a más marcación.
   2. Ejemplo de 5 clientes: orden de sus teléfonos y las razones que verá el asesor.
   3. Razones más frecuentes en el primer teléfono de cada cliente (para revisar cómo se leen en pantalla).
   4. El teléfono con un tramo que la versión no conoce.
   5. (Desde el 21/11) Acierto real: tasa de CEF por tramo del score del 14/11 en la semana del 14 al 20/11.
   ===================================================================================== */
USE CobAuto;
SET NOCOUNT ON;

DECLARE @f DATE = '2026-11-14';

/* ---------- 1. Mejor teléfono de cada cliente, por cartera ---------- */
SELECT s.IdCartera,
       COUNT(*) AS clientes,
       SUM(CASE WHEN s.Tramo = 'A' THEN 1 ELSE 0 END) AS mejor_A,
       SUM(CASE WHEN s.Tramo = 'B' THEN 1 ELSE 0 END) AS mejor_B,
       SUM(CASE WHEN s.Tramo = 'C' THEN 1 ELSE 0 END) AS mejor_C,
       SUM(CASE WHEN s.Tramo IN ('D', 'E') THEN 1 ELSE 0 END) AS mejor_D_o_E,
       CAST(100.0 * SUM(CASE WHEN s.Tramo IN ('D', 'E') THEN 1 ELSE 0 END) / COUNT(*) AS DECIMAL(5, 1)) AS pct_sin_telefono_bueno,
       SUM(CASE WHEN s.Descartado = 1 THEN 1 ELSE 0 END) AS mejor_descartado,
       AVG(CAST(n.telefonos AS FLOAT)) AS telefonos_por_cliente
FROM score.TelefonoScore AS s
CROSS APPLY (SELECT COUNT(*) AS telefonos FROM score.TelefonoScore AS x
             WHERE x.FechaCorte = s.FechaCorte AND x.IdCartera = s.IdCartera AND x.DNI = s.DNI) AS n
WHERE s.FechaCorte = @f AND s.OrdenCliente = 1
GROUP BY s.IdCartera
ORDER BY s.IdCartera;

/* ---------- 2. Cinco clientes al azar con al menos un teléfono en A: orden y razones ---------- */
;WITH Clientes AS (
    SELECT TOP 5 IdCartera, DNI
    FROM score.TelefonoScore
    WHERE FechaCorte = @f AND OrdenCliente = 1 AND Tramo = 'A'
    ORDER BY NEWID()
)
SELECT s.IdCartera, s.DNI, s.OrdenCliente, s.Telefono, s.Score, s.Tramo, s.Descartado,
       s.Razon1, s.Razon2, s.Razon3, s.Razon_Resta,
       c.T_ULT_CEF, c.T_TASA_CEF_90, c.T_INTENTOS_30, c.T_MAQUINA_90, c.S_OSIPTEL, c.S_WHATSAPP,
       c.S_TIPO_LINEA, c.S_RELACION, c.FranjaContacto, c.UltimoIntento
FROM Clientes AS k
INNER JOIN score.TelefonoScore AS s ON s.FechaCorte = @f AND s.IdCartera = k.IdCartera AND s.DNI = k.DNI
INNER JOIN score.Caracteristicas AS c
        ON c.FechaCorte = @f AND c.Poblacion = 'UNIVERSO'
       AND c.IdCartera = s.IdCartera AND c.DNI = s.DNI AND c.Telefono = s.Telefono
ORDER BY s.IdCartera, s.DNI, s.OrdenCliente;

/* ---------- 3. Razones más frecuentes en el primer teléfono de cada cliente ---------- */
SELECT TOP 20 r.Razon, COUNT(*) AS veces
FROM score.TelefonoScore AS s
CROSS APPLY (VALUES (s.Razon1), (s.Razon2), (s.Razon3)) AS r (Razon)
WHERE s.FechaCorte = @f AND s.OrdenCliente = 1
GROUP BY r.Razon
ORDER BY veces DESC;

/* ---------- 4. Teléfonos con un tramo que la versión no conoce ---------- */
SELECT s.IdCartera, s.DNI, s.Telefono, s.Score, s.TramosSinPeso,
       c.T_ULT_CEF, c.T_ULT_TERCERO, c.T_TASA_CEF_90, c.T_INTENTOS_30, c.T_ULT_INTENTO, c.T_MAQUINA_90,
       c.S_ORIGEN, c.S_FUENTE, c.S_ANTIG_DATO, c.S_OSIPTEL, c.S_WHATSAPP, c.S_TIMBRA,
       c.S_TIPO_LINEA, c.S_RELACION, c.S_COMPARTIDO
FROM score.TelefonoScore AS s
INNER JOIN score.Caracteristicas AS c
        ON c.FechaCorte = @f AND c.Poblacion = 'UNIVERSO'
       AND c.IdCartera = s.IdCartera AND c.DNI = s.DNI AND c.Telefono = s.Telefono
WHERE s.FechaCorte = @f AND s.TramosSinPeso > 0;

/* ---------- 5. Acierto real (ejecutar desde el 21/11, con el historial del 14 al 20/11 cargado) ---------- */
/*
SELECT s.Tramo,
       COUNT(*) AS telefonos_marcados,
       SUM(CASE WHEN f.Cef > 0 THEN 1 ELSE 0 END) AS con_cef,
       CAST(100.0 * SUM(CASE WHEN f.Cef > 0 THEN 1 ELSE 0 END) / COUNT(*) AS DECIMAL(6, 2)) AS tasa_cef_pct
FROM score.TelefonoScore AS s
CROSS APPLY (SELECT SUM(d.IntentosHumano + d.IntentosMaquina) AS Intentos,
                    SUM(d.N_TITULAR + d.N_TERCERO_ACUERDO) AS Cef
             FROM score.TelefonoDia AS d
             WHERE d.IdCartera = s.IdCartera AND d.DNI = s.DNI AND d.Telefono = s.Telefono
               AND d.Fecha >= @f AND d.Fecha < DATEADD(DAY, 7, @f)) AS f
WHERE s.FechaCorte = @f AND f.Intentos > 0
GROUP BY s.Tramo
ORDER BY s.Tramo;
*/
