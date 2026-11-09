/* =====================================================================
   Cierre histórico Compartamos VIGENTE INDIVIDUAL — columna FLG_CliRef
   Origen : Desarrollo.dbo.compartamos_individual.FLG_CliRef  (varchar: 'N', 'R', ...)
   Destino: Compartamos_Vigente_Cobranzas.dbo.HIST_COMPARTAMOS_INDIVIDUAL.FLG_CliRef (float)

   PASO 1 = solo lectura. Ejecutar y revisar ANTES del paso 2.
   PASO 2 = cambio de estructura (comentado). Solo si apruebas la opción A.
   ===================================================================== */


/* ---------- PASO 1.1  Valores que trae la asignación actual ---------- */
SELECT
    FLG_CliRef,
    COUNT(*) AS filas
FROM Desarrollo.dbo.compartamos_individual WITH (NOLOCK)
GROUP BY FLG_CliRef
ORDER BY filas DESC;


/* ---------- PASO 1.2  Valores que ya tiene el histórico, por periodo ---------- */
SELECT
    PERIODO,
    FLG_CliRef,
    COUNT(*) AS filas
FROM Compartamos_Vigente_Cobranzas.dbo.HIST_COMPARTAMOS_INDIVIDUAL WITH (NOLOCK)
GROUP BY PERIODO, FLG_CliRef
ORDER BY PERIODO DESC, filas DESC;


/* ---------- PASO 1.3  Definición actual de la columna en el histórico ---------- */
SELECT
    c.name AS columna, t.name AS tipo, c.max_length, c.precision, c.scale, c.is_nullable
FROM Compartamos_Vigente_Cobranzas.sys.columns c
JOIN Compartamos_Vigente_Cobranzas.sys.types t ON t.user_type_id = c.user_type_id
WHERE c.object_id = OBJECT_ID('Compartamos_Vigente_Cobranzas.dbo.HIST_COMPARTAMOS_INDIVIDUAL')
  AND c.name = 'FLG_CliRef';


/* ---------- PASO 1.4  ¿Algún índice, vista o procedimiento usa FLG_CliRef? ----------
   Si algo hace cálculos numéricos con esta columna, cambiar su tipo lo afectaría. */
SELECT i.name AS indice
FROM Compartamos_Vigente_Cobranzas.sys.index_columns ic
JOIN Compartamos_Vigente_Cobranzas.sys.indexes i
  ON i.object_id = ic.object_id AND i.index_id = ic.index_id
JOIN Compartamos_Vigente_Cobranzas.sys.columns c
  ON c.object_id = ic.object_id AND c.column_id = ic.column_id
WHERE ic.object_id = OBJECT_ID('Compartamos_Vigente_Cobranzas.dbo.HIST_COMPARTAMOS_INDIVIDUAL')
  AND c.name = 'FLG_CliRef';

SELECT
    OBJECT_SCHEMA_NAME(m.object_id) + '.' + OBJECT_NAME(m.object_id) AS objeto,
    o.type_desc
FROM Compartamos_Vigente_Cobranzas.sys.sql_modules m
JOIN Compartamos_Vigente_Cobranzas.sys.objects o ON o.object_id = m.object_id
WHERE m.definition LIKE '%FLG_CliRef%';
/* Repetir esta última consulta en las otras bases donde haya reportes
   que lean el histórico (por ejemplo Desarrollo o CobAuto). */


/* =====================================================================
   PASO 2 — OPCIÓN A: guardar en el histórico lo que manda el banco
   Cambia FLG_CliRef de float a VARCHAR(10). Los valores históricos
   numéricos se conservan como texto ('0', '1', ...).
   Descomentar y ejecutar solo después de revisar el PASO 1.
   ===================================================================== */
/*
BEGIN TRANSACTION;

ALTER TABLE Compartamos_Vigente_Cobranzas.dbo.HIST_COMPARTAMOS_INDIVIDUAL
    ALTER COLUMN FLG_CliRef VARCHAR(10) NULL;

-- Verificación: debe mostrar varchar(10)
SELECT c.name, t.name AS tipo, c.max_length
FROM Compartamos_Vigente_Cobranzas.sys.columns c
JOIN Compartamos_Vigente_Cobranzas.sys.types t ON t.user_type_id = c.user_type_id
WHERE c.object_id = OBJECT_ID('Compartamos_Vigente_Cobranzas.dbo.HIST_COMPARTAMOS_INDIVIDUAL')
  AND c.name = 'FLG_CliRef';

-- Si todo está bien:
COMMIT TRANSACTION;
-- Si algo no cuadra:
-- ROLLBACK TRANSACTION;
*/


/* =====================================================================
   PASO 3 — Revisión de la otra falla: [Cancelación%] recibe el monto
   El programa llena HIST.[Cancelación%] con ORIGEN.[Cancelacion].
   Esta consulta muestra si en periodos ya cerrados ambas columnas
   quedaron iguales (señal de que se guardó el monto en lugar del %).
   ===================================================================== */
SELECT
    PERIODO,
    COUNT(*) AS filas,
    SUM(CASE WHEN TRY_CONVERT(float, CONVERT(NVARCHAR(100), [Cancelación%]))
                = TRY_CONVERT(float, CONVERT(NVARCHAR(100), [Cancelacion])) THEN 1 ELSE 0 END) AS filas_porcentaje_igual_monto,
    MIN(TRY_CONVERT(float, CONVERT(NVARCHAR(100), [Cancelación%]))) AS min_cancelacion_pct,
    MAX(TRY_CONVERT(float, CONVERT(NVARCHAR(100), [Cancelación%]))) AS max_cancelacion_pct
FROM Compartamos_Vigente_Cobranzas.dbo.HIST_COMPARTAMOS_INDIVIDUAL WITH (NOLOCK)
GROUP BY PERIODO
ORDER BY PERIODO DESC;

/* ¿El origen tiene alguna columna de % de cancelación? */
SELECT c.name AS columna
FROM Desarrollo.sys.columns c
WHERE c.object_id = OBJECT_ID('Desarrollo.dbo.compartamos_individual')
  AND c.name LIKE '%Cancel%';
