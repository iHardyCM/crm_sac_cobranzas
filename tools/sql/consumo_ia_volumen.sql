/* =============================================================================
   ¿Qué explica el consumo de la API? — volumen real del módulo Feedback_IA
   Base: CobAuto. Solo LECTURA: ningún UPDATE, ningún DELETE.

   La API cobra por dos cosas distintas:
     1. Transcripción  -> se paga por MINUTO de audio. Ocurre una vez por audio
                          nuevo (un reanálisis reutiliza la transcripción
                          guardada, salvo que se fuerce).
     2. Análisis       -> se paga por TOKENS. Ocurre en CADA análisis, incluidos
                          los reanálisis.

   Por eso las dos consultas siguientes separan audios nuevos de reanálisis.
   ============================================================================= */

USE CobAuto;
GO

-- 1) Por día: audios cargados, minutos de audio y análisis ejecutados
SELECT
    dia                  = CAST(fecha_creacion AS DATE),
    audios_cargados      = COUNT(*),
    finalizados          = SUM(CASE WHEN estado = 'FINALIZADO' THEN 1 ELSE 0 END),
    con_error            = SUM(CASE WHEN estado = 'ERROR' THEN 1 ELSE 0 END),
    minutos_audio        = CAST(SUM(ISNULL(duracion_segundos, 0)) / 60.0 AS DECIMAL(10,1)),
    minutos_promedio     = CAST(AVG(ISNULL(duracion_segundos, 0) * 1.0) / 60.0 AS DECIMAL(10,1)),
    analisis_ejecutados  = SUM(CASE WHEN fecha_analisis IS NOT NULL THEN 1 ELSE 0 END)
FROM dbo.ia_feedback_llamadas WITH(NOLOCK)
WHERE fecha_creacion >= DATEADD(DAY, -30, CAST(GETDATE() AS DATE))
GROUP BY CAST(fecha_creacion AS DATE)
ORDER BY dia;
GO

-- 2) Reanálisis: llamadas analizadas después del día en que se cargaron.
--    Cada reanálisis paga tokens de análisis otra vez (no transcripción).
SELECT
    dia_analisis   = CAST(fecha_analisis AS DATE),
    reanalisis     = COUNT(*),
    minutos_audio  = CAST(SUM(ISNULL(duracion_segundos, 0)) / 60.0 AS DECIMAL(10,1))
FROM dbo.ia_feedback_llamadas WITH(NOLOCK)
WHERE fecha_analisis IS NOT NULL
  AND CAST(fecha_analisis AS DATE) > CAST(fecha_creacion AS DATE)
  AND fecha_analisis >= DATEADD(DAY, -30, CAST(GETDATE() AS DATE))
GROUP BY CAST(fecha_analisis AS DATE)
ORDER BY dia_analisis;
GO

-- 3) Totales del mes en curso, para dividir contra la factura de la API
SELECT
    audios_cargados   = COUNT(*),
    minutos_audio     = CAST(SUM(ISNULL(duracion_segundos, 0)) / 60.0 AS DECIMAL(10,1)),
    minutos_mas_largo = CAST(MAX(ISNULL(duracion_segundos, 0)) / 60.0 AS DECIMAL(10,1)),
    audios_sobre_10m  = SUM(CASE WHEN ISNULL(duracion_segundos, 0) > 600 THEN 1 ELSE 0 END),
    sin_duracion      = SUM(CASE WHEN duracion_segundos IS NULL THEN 1 ELSE 0 END)
FROM dbo.ia_feedback_llamadas WITH(NOLOCK)
WHERE fecha_creacion >= DATEADD(DAY, 1 - DAY(GETDATE()), CAST(GETDATE() AS DATE));
GO

-- 4) Las 15 llamadas más largas del mes: son las que más cuestan transcribir
SELECT TOP (15)
    id_feedback, cartera, agente,
    minutos = CAST(ISNULL(duracion_segundos, 0) / 60.0 AS DECIMAL(10,1)),
    fecha_creacion, estado
FROM dbo.ia_feedback_llamadas WITH(NOLOCK)
WHERE fecha_creacion >= DATEADD(DAY, 1 - DAY(GETDATE()), CAST(GETDATE() AS DATE))
ORDER BY ISNULL(duracion_segundos, 0) DESC;
GO
