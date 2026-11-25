/* =====================================================================================
   SCORE TELEFÓNICO · DIAGNÓSTICO 6 — fecha_actualizacion y origen de la "q" (solo lectura)
   Fecha: 14/11/2026

   A. ¿Qué mueve telefonos.fecha_actualizacion?
      Si son cargas masivas: pocos días con picos grandes, a horas fijas, casi sin gestión ese día.
      Si la toca el asesor o la gestión: todos los días hábiles, en horario de call, y una parte alta
      de esos teléfonos tuvo gestión humana ese mismo día (la base es ~1 % del universo por día).
   B. ¿Quién escribe la "q" del semáforo?
      B.1 Valores del semáforo distinguiendo mayúsculas, en la copia local y en producción.
      B.2 Procedimientos, vistas y triggers de la instancia que mencionan Prioridad y 'Q'.
      B.3 Pasos de jobs del Agente SQL que mencionan Prioridad y 'Q'.

   Guardar en tools\salidas\resultados_diagnostico_score_6.txt
   ===================================================================================== */
USE CobAuto;
SET NOCOUNT ON;

/* ---------- A.1 Por mes: cuántos teléfonos tienen esa fecha de actualización ---------- */
SELECT CONVERT(CHAR(6), t.fecha_actualizacion, 112) AS mes_actualizacion,
       COUNT(*) AS telefonos,
       SUM(CASE WHEN CONVERT(CHAR(6), t.fecha, 112) = CONVERT(CHAR(6), t.fecha_actualizacion, 112) THEN 1 ELSE 0 END) AS alta_el_mismo_mes
FROM siscob.dbo.telefonos AS t WITH (NOLOCK)
WHERE t.fecha_actualizacion >= '2025-01-01'
GROUP BY CONVERT(CHAR(6), t.fecha_actualizacion, 112)
ORDER BY mes_actualizacion;

/* ---------- A.2 Desde agosto, por día: ¿coincide con gestión de ese teléfono ese mismo día? ---------- */
SELECT d.Fecha, d.DNI, d.Telefono,
       MAX(CASE WHEN d.IntentosHumano > 0 THEN 1 ELSE 0 END) AS GestionHumana,
       MAX(CASE WHEN d.N_TITULAR + d.N_TERCERO_ACUERDO > 0 THEN 1 ELSE 0 END) AS Cef
INTO #g
FROM score.TelefonoDia AS d WITH (NOLOCK)
WHERE d.Fecha >= '2026-08-01'
GROUP BY d.Fecha, d.DNI, d.Telefono;

CREATE CLUSTERED INDEX IX_g ON #g (Fecha, DNI, Telefono);

SELECT CAST(t.fecha_actualizacion AS DATE) AS dia,
       DATENAME(WEEKDAY, t.fecha_actualizacion) AS dia_semana,
       COUNT(*) AS telefonos_actualizados,
       SUM(CASE WHEN CAST(t.fecha AS DATE) = CAST(t.fecha_actualizacion AS DATE) THEN 1 ELSE 0 END) AS alta_el_mismo_dia,
       SUM(ISNULL(g.GestionHumana, 0)) AS con_gestion_humana_ese_dia,
       CAST(100.0 * SUM(ISNULL(g.GestionHumana, 0)) / COUNT(*) AS DECIMAL(6, 2)) AS pct_con_gestion,
       SUM(ISNULL(g.Cef, 0)) AS con_cef_ese_dia,
       MIN(CONVERT(CHAR(5), t.fecha_actualizacion, 108)) AS primera_hora,
       MAX(CONVERT(CHAR(5), t.fecha_actualizacion, 108)) AS ultima_hora
FROM siscob.dbo.telefonos AS t WITH (NOLOCK)
LEFT JOIN #g AS g
       ON g.Fecha = CAST(t.fecha_actualizacion AS DATE)
      AND g.DNI = LEFT(LTRIM(RTRIM(t.DNI)), 20) COLLATE DATABASE_DEFAULT
      AND g.Telefono = CONVERT(CHAR(9), CONVERT(BIGINT, t.telefono)) COLLATE DATABASE_DEFAULT
WHERE t.fecha_actualizacion >= '2026-08-01'
  AND t.telefono BETWEEN 900000000 AND 999999999
GROUP BY CAST(t.fecha_actualizacion AS DATE), DATENAME(WEEKDAY, t.fecha_actualizacion)
ORDER BY dia;

/* ---------- A.3 Hora del día de las actualizaciones (últimos 60 días) ---------- */
SELECT DATEPART(HOUR, t.fecha_actualizacion) AS hora, COUNT(*) AS telefonos
FROM siscob.dbo.telefonos AS t WITH (NOLOCK)
WHERE t.fecha_actualizacion >= DATEADD(DAY, -60, CAST(GETDATE() AS DATE))
GROUP BY DATEPART(HOUR, t.fecha_actualizacion)
ORDER BY hora;

DROP TABLE #g;

/* ---------- B.1 Semáforo distinguiendo mayúsculas: copia local y producción ---------- */
SELECT 'LOCAL' AS origen, t.Prioridad COLLATE Latin1_General_CS_AS AS prioridad,
       ASCII(t.Prioridad) AS codigo_ascii, COUNT(*) AS telefonos
FROM siscob.dbo.telefonos AS t WITH (NOLOCK)
GROUP BY t.Prioridad COLLATE Latin1_General_CS_AS, ASCII(t.Prioridad)
ORDER BY prioridad;

SELECT 'PRODUCCION' AS origen, p.prioridad, p.codigo_ascii, p.telefonos
FROM OPENQUERY([192.168.7.12\BIZNESCOB],
    'SELECT PRIORIDAD COLLATE Latin1_General_CS_AS AS prioridad, ASCII(PRIORIDAD) AS codigo_ascii, COUNT(*) AS telefonos
     FROM SISCOB.dbo.TELEFONOS WITH (NOLOCK)
     GROUP BY PRIORIDAD COLLATE Latin1_General_CS_AS, ASCII(PRIORIDAD)') AS p
ORDER BY p.prioridad;

/* ---------- B.2 Código de la instancia que asigna Prioridad 'Q' (cualquier mayúscula/minúscula) ---------- */
SELECT 'siscob' AS base, OBJECT_SCHEMA_NAME(m.object_id, DB_ID('siscob')) + '.' + OBJECT_NAME(m.object_id, DB_ID('siscob')) AS objeto, o.type_desc
FROM siscob.sys.sql_modules AS m INNER JOIN siscob.sys.objects AS o ON o.object_id = m.object_id
WHERE m.definition LIKE '%PRIORIDAD%' AND (m.definition LIKE '%''Q''%' OR m.definition LIKE '%= ''q''%')
UNION ALL
SELECT 'Desarrollo', OBJECT_SCHEMA_NAME(m.object_id, DB_ID('Desarrollo')) + '.' + OBJECT_NAME(m.object_id, DB_ID('Desarrollo')), o.type_desc
FROM Desarrollo.sys.sql_modules AS m INNER JOIN Desarrollo.sys.objects AS o ON o.object_id = m.object_id
WHERE m.definition LIKE '%PRIORIDAD%' AND m.definition LIKE '%''Q''%'
UNION ALL
SELECT 'CobAuto', OBJECT_SCHEMA_NAME(m.object_id, DB_ID('CobAuto')) + '.' + OBJECT_NAME(m.object_id, DB_ID('CobAuto')), o.type_desc
FROM CobAuto.sys.sql_modules AS m INNER JOIN CobAuto.sys.objects AS o ON o.object_id = m.object_id
WHERE m.definition LIKE '%PRIORIDAD%' AND m.definition LIKE '%''Q''%'
UNION ALL
SELECT 'Financiera_OH_Cobranzas', OBJECT_SCHEMA_NAME(m.object_id, DB_ID('Financiera_OH_Cobranzas')) + '.' + OBJECT_NAME(m.object_id, DB_ID('Financiera_OH_Cobranzas')), o.type_desc
FROM Financiera_OH_Cobranzas.sys.sql_modules AS m INNER JOIN Financiera_OH_Cobranzas.sys.objects AS o ON o.object_id = m.object_id
WHERE m.definition LIKE '%PRIORIDAD%' AND m.definition LIKE '%''Q''%'
UNION ALL
SELECT 'Interbank_Cobranzas', OBJECT_SCHEMA_NAME(m.object_id, DB_ID('Interbank_Cobranzas')) + '.' + OBJECT_NAME(m.object_id, DB_ID('Interbank_Cobranzas')), o.type_desc
FROM Interbank_Cobranzas.sys.sql_modules AS m INNER JOIN Interbank_Cobranzas.sys.objects AS o ON o.object_id = m.object_id
WHERE m.definition LIKE '%PRIORIDAD%' AND m.definition LIKE '%''Q''%'
UNION ALL
SELECT 'Interbank_Propia_Cobranzas', OBJECT_SCHEMA_NAME(m.object_id, DB_ID('Interbank_Propia_Cobranzas')) + '.' + OBJECT_NAME(m.object_id, DB_ID('Interbank_Propia_Cobranzas')), o.type_desc
FROM Interbank_Propia_Cobranzas.sys.sql_modules AS m INNER JOIN Interbank_Propia_Cobranzas.sys.objects AS o ON o.object_id = m.object_id
WHERE m.definition LIKE '%PRIORIDAD%' AND m.definition LIKE '%''Q''%'
UNION ALL
SELECT 'Compartamos_Vigente_Cobranzas', OBJECT_SCHEMA_NAME(m.object_id, DB_ID('Compartamos_Vigente_Cobranzas')) + '.' + OBJECT_NAME(m.object_id, DB_ID('Compartamos_Vigente_Cobranzas')), o.type_desc
FROM Compartamos_Vigente_Cobranzas.sys.sql_modules AS m INNER JOIN Compartamos_Vigente_Cobranzas.sys.objects AS o ON o.object_id = m.object_id
WHERE m.definition LIKE '%PRIORIDAD%' AND m.definition LIKE '%''Q''%'
UNION ALL
SELECT 'Compartamos_Castigo_Cobranzas', OBJECT_SCHEMA_NAME(m.object_id, DB_ID('Compartamos_Castigo_Cobranzas')) + '.' + OBJECT_NAME(m.object_id, DB_ID('Compartamos_Castigo_Cobranzas')), o.type_desc
FROM Compartamos_Castigo_Cobranzas.sys.sql_modules AS m INNER JOIN Compartamos_Castigo_Cobranzas.sys.objects AS o ON o.object_id = m.object_id
WHERE m.definition LIKE '%PRIORIDAD%' AND m.definition LIKE '%''Q''%'
UNION ALL
SELECT 'PROPIA_COBRANZAS', OBJECT_SCHEMA_NAME(m.object_id, DB_ID('PROPIA_COBRANZAS')) + '.' + OBJECT_NAME(m.object_id, DB_ID('PROPIA_COBRANZAS')), o.type_desc
FROM PROPIA_COBRANZAS.sys.sql_modules AS m INNER JOIN PROPIA_COBRANZAS.sys.objects AS o ON o.object_id = m.object_id
WHERE m.definition LIKE '%PRIORIDAD%' AND m.definition LIKE '%''Q''%'
UNION ALL
SELECT 'MiBanco_Cobranzas', OBJECT_SCHEMA_NAME(m.object_id, DB_ID('MiBanco_Cobranzas')) + '.' + OBJECT_NAME(m.object_id, DB_ID('MiBanco_Cobranzas')), o.type_desc
FROM MiBanco_Cobranzas.sys.sql_modules AS m INNER JOIN MiBanco_Cobranzas.sys.objects AS o ON o.object_id = m.object_id
WHERE m.definition LIKE '%PRIORIDAD%' AND m.definition LIKE '%''Q''%'
ORDER BY base, objeto;

-- Triggers sobre siscob.dbo.telefonos (cualquiera, para ver si alguno toca el semáforo)
SELECT tr.name AS trigger_nombre, tr.is_disabled, te.type_desc AS evento
FROM siscob.sys.triggers AS tr
INNER JOIN siscob.sys.trigger_events AS te ON te.object_id = tr.object_id
WHERE tr.parent_id = OBJECT_ID('siscob.dbo.telefonos');

/* ---------- B.3 Jobs del Agente SQL que mencionan Prioridad y 'Q' ---------- */
SELECT j.name AS job, j.enabled, s.step_id, s.step_name, s.database_name
FROM msdb.dbo.sysjobs AS j
INNER JOIN msdb.dbo.sysjobsteps AS s ON s.job_id = j.job_id
WHERE s.command LIKE '%PRIORIDAD%' AND s.command LIKE '%''Q''%'
ORDER BY j.name, s.step_id;
