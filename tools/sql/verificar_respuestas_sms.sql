/* =============================================================================
   Respuestas SMS — verificación de la carga (solo lectura)
   Ejecutar después de: python tools/sync_respuestas_sms.py --backfill
   ============================================================================= */
USE CobAuto;
GO

-- 1. Últimas corridas: resultado, volumen y avisos.
SELECT TOP (20) IdSincronizacion, Tipo, Inicio, Fin,
       DATEDIFF(SECOND, Inicio, Fin) AS segundos, Resultado,
       CampanasNuevas, CampanasRevisadas, RespuestasNuevas, OrigenesCompletados, Avisos, Detalle
FROM dbo.CRM_SMS_SINCRONIZACION
ORDER BY IdSincronizacion DESC;

-- 2. Campañas por cuenta: cuántas hay, cuántas siguen en revisión y cuántas tienen respuestas.
SELECT Cuenta, COUNT(*) AS campanas,
       SUM(CASE WHEN ProximaRevision IS NOT NULL THEN 1 ELSE 0 END) AS en_revision,
       SUM(CASE WHEN TotalRespuestas > 0 THEN 1 ELSE 0 END) AS con_respuestas,
       SUM(TotalRespuestas) AS respuestas_segun_mowa,
       MIN(CAST(FechaCreacion AS date)) AS primera, MAX(CAST(FechaCreacion AS date)) AS ultima
FROM dbo.CRM_SMS_CAMPANA
GROUP BY Cuenta
ORDER BY Cuenta;

-- 3. Respuestas guardadas por cuenta y estado del SMS de origen.
--    OrigenEstado PENDIENTE alto o NO_ENCONTRADO > 0: avisar antes de seguir.
SELECT Cuenta, OrigenEstado, COUNT(*) AS respuestas,
       SUM(CASE WHEN Dni IS NULL THEN 1 ELSE 0 END) AS sin_dni,
       SUM(CASE WHEN RecepcionConHora = 0 THEN 1 ELSE 0 END) AS sin_hora,
       MIN(FechaRecepcion) AS primera, MAX(FechaRecepcion) AS ultima
FROM dbo.CRM_SMS_RESPUESTA
GROUP BY Cuenta, OrigenEstado
ORDER BY Cuenta, OrigenEstado;

-- 4. Respuestas por día de recepción (deberían empezar el 01/11/2026).
SELECT CAST(FechaRecepcion AS date) AS dia, COUNT(*) AS respuestas
FROM dbo.CRM_SMS_RESPUESTA
GROUP BY CAST(FechaRecepcion AS date)
ORDER BY dia;

-- 5. Primera medición real: días entre el envío del SMS y la respuesta.
SELECT CASE
         WHEN DATEDIFF(DAY, MensajeFechaEnvio, FechaRecepcion) <= 0 THEN '0 mismo día'
         WHEN DATEDIFF(DAY, MensajeFechaEnvio, FechaRecepcion) <= 2 THEN '1-2 días'
         WHEN DATEDIFF(DAY, MensajeFechaEnvio, FechaRecepcion) <= 7 THEN '3-7 días'
         WHEN DATEDIFF(DAY, MensajeFechaEnvio, FechaRecepcion) <= 30 THEN '8-30 días'
         ELSE '31+ días' END AS retraso,
       COUNT(*) AS respuestas
FROM dbo.CRM_SMS_RESPUESTA
WHERE OrigenEstado = 'OK' AND MensajeFechaEnvio IS NOT NULL AND FechaRecepcion IS NOT NULL
GROUP BY CASE
         WHEN DATEDIFF(DAY, MensajeFechaEnvio, FechaRecepcion) <= 0 THEN '0 mismo día'
         WHEN DATEDIFF(DAY, MensajeFechaEnvio, FechaRecepcion) <= 2 THEN '1-2 días'
         WHEN DATEDIFF(DAY, MensajeFechaEnvio, FechaRecepcion) <= 7 THEN '3-7 días'
         WHEN DATEDIFF(DAY, MensajeFechaEnvio, FechaRecepcion) <= 30 THEN '8-30 días'
         ELSE '31+ días' END
ORDER BY retraso;
GO
