/* =====================================================================================
   DIAGNÓSTICO 3 — DEFINICIÓN DE LAS MATRICES DE TELÉFONOS (solo lectura)
   Fecha: 14/11/2026

   Reemplaza los bloques 3, 4 y 5 del diagnóstico 2, que fallaron por un error de sintaxis
   del script (no de la base). Este no usa SQL dinámico: una consulta por base.

   Ejecutar igual que el anterior: Resultados en archivo (Ctrl+Shift+F) y F5,
   con "Número máximo de caracteres" de Resultados en texto = 8192.
   Incluye Desarrollo por SP_FOTO_GESTION y SP_OBTENER_TELEFONOS (paso 1 del Jb Maestro).
   ===================================================================================== */

USE CobAuto;
GO
SET NOCOUNT ON;
GO

/* ===================== Compartamos_Vigente_Cobranzas ===================== */

/* a. Objetos de teléfonos, con filas y fechas */
SELECT 'Compartamos_Vigente_Cobranzas' AS base, o.name AS objeto, o.type_desc AS tipo, o.create_date, o.modify_date,
       (SELECT SUM(p.[rows]) FROM [Compartamos_Vigente_Cobranzas].sys.partitions AS p
        WHERE p.[object_id] = o.[object_id] AND p.index_id IN (0, 1)) AS filas
FROM [Compartamos_Vigente_Cobranzas].sys.objects AS o
WHERE o.type IN ('U', 'V', 'P')
  AND (o.name LIKE '%FONO%' OR o.name LIKE '%TELEF%' OR o.name LIKE '%SCORE_PROPIA%')
ORDER BY o.type_desc, o.name;
GO

/* b. Definición completa, en trozos de 4.000 caracteres */
WITH NUMEROS AS (
    SELECT TOP (200) ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) - 1 AS nro
    FROM sys.all_objects
)
SELECT 'Compartamos_Vigente_Cobranzas' AS base, o.name AS objeto, NUMEROS.nro + 1 AS parte,
       SUBSTRING(m.definition, NUMEROS.nro * 4000 + 1, 4000) AS definicion
FROM [Compartamos_Vigente_Cobranzas].sys.objects AS o
INNER JOIN [Compartamos_Vigente_Cobranzas].sys.sql_modules AS m ON m.[object_id] = o.[object_id]
INNER JOIN NUMEROS ON NUMEROS.nro * 4000 < LEN(m.definition)
WHERE o.name LIKE 'SP_MATRIZ_FONOS%' OR (o.type = 'V' AND (o.name LIKE '%FONOS%' OR o.name LIKE 'VW_SCORE_PROPIA%'))
ORDER BY o.name, NUMEROS.nro;
GO

/* c. Columnas de cada TBL_FONOS_* */
SELECT 'Compartamos_Vigente_Cobranzas' AS base, t.name AS tabla,
       STUFF((SELECT ',' + c.name FROM [Compartamos_Vigente_Cobranzas].sys.columns AS c
              WHERE c.[object_id] = t.[object_id] ORDER BY c.column_id
              FOR XML PATH(''), TYPE).value('.', 'nvarchar(max)'), 1, 1, '') AS columnas
FROM [Compartamos_Vigente_Cobranzas].sys.tables AS t
WHERE t.name LIKE 'TBL_FONOS%'
ORDER BY t.name;
GO

/* ===================== Compartamos_Castigo_Cobranzas ===================== */

/* a. Objetos de teléfonos, con filas y fechas */
SELECT 'Compartamos_Castigo_Cobranzas' AS base, o.name AS objeto, o.type_desc AS tipo, o.create_date, o.modify_date,
       (SELECT SUM(p.[rows]) FROM [Compartamos_Castigo_Cobranzas].sys.partitions AS p
        WHERE p.[object_id] = o.[object_id] AND p.index_id IN (0, 1)) AS filas
FROM [Compartamos_Castigo_Cobranzas].sys.objects AS o
WHERE o.type IN ('U', 'V', 'P')
  AND (o.name LIKE '%FONO%' OR o.name LIKE '%TELEF%' OR o.name LIKE '%SCORE_PROPIA%')
ORDER BY o.type_desc, o.name;
GO

/* b. Definición completa, en trozos de 4.000 caracteres */
WITH NUMEROS AS (
    SELECT TOP (200) ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) - 1 AS nro
    FROM sys.all_objects
)
SELECT 'Compartamos_Castigo_Cobranzas' AS base, o.name AS objeto, NUMEROS.nro + 1 AS parte,
       SUBSTRING(m.definition, NUMEROS.nro * 4000 + 1, 4000) AS definicion
FROM [Compartamos_Castigo_Cobranzas].sys.objects AS o
INNER JOIN [Compartamos_Castigo_Cobranzas].sys.sql_modules AS m ON m.[object_id] = o.[object_id]
INNER JOIN NUMEROS ON NUMEROS.nro * 4000 < LEN(m.definition)
WHERE o.name LIKE 'SP_MATRIZ_FONOS%' OR (o.type = 'V' AND (o.name LIKE '%FONOS%' OR o.name LIKE 'VW_SCORE_PROPIA%'))
ORDER BY o.name, NUMEROS.nro;
GO

/* c. Columnas de cada TBL_FONOS_* */
SELECT 'Compartamos_Castigo_Cobranzas' AS base, t.name AS tabla,
       STUFF((SELECT ',' + c.name FROM [Compartamos_Castigo_Cobranzas].sys.columns AS c
              WHERE c.[object_id] = t.[object_id] ORDER BY c.column_id
              FOR XML PATH(''), TYPE).value('.', 'nvarchar(max)'), 1, 1, '') AS columnas
FROM [Compartamos_Castigo_Cobranzas].sys.tables AS t
WHERE t.name LIKE 'TBL_FONOS%'
ORDER BY t.name;
GO

/* ===================== Financiera_OH_Cobranzas ===================== */

/* a. Objetos de teléfonos, con filas y fechas */
SELECT 'Financiera_OH_Cobranzas' AS base, o.name AS objeto, o.type_desc AS tipo, o.create_date, o.modify_date,
       (SELECT SUM(p.[rows]) FROM [Financiera_OH_Cobranzas].sys.partitions AS p
        WHERE p.[object_id] = o.[object_id] AND p.index_id IN (0, 1)) AS filas
FROM [Financiera_OH_Cobranzas].sys.objects AS o
WHERE o.type IN ('U', 'V', 'P')
  AND (o.name LIKE '%FONO%' OR o.name LIKE '%TELEF%' OR o.name LIKE '%SCORE_PROPIA%')
ORDER BY o.type_desc, o.name;
GO

/* b. Definición completa, en trozos de 4.000 caracteres */
WITH NUMEROS AS (
    SELECT TOP (200) ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) - 1 AS nro
    FROM sys.all_objects
)
SELECT 'Financiera_OH_Cobranzas' AS base, o.name AS objeto, NUMEROS.nro + 1 AS parte,
       SUBSTRING(m.definition, NUMEROS.nro * 4000 + 1, 4000) AS definicion
FROM [Financiera_OH_Cobranzas].sys.objects AS o
INNER JOIN [Financiera_OH_Cobranzas].sys.sql_modules AS m ON m.[object_id] = o.[object_id]
INNER JOIN NUMEROS ON NUMEROS.nro * 4000 < LEN(m.definition)
WHERE o.name LIKE 'SP_MATRIZ_FONOS%' OR (o.type = 'V' AND (o.name LIKE '%FONOS%' OR o.name LIKE 'VW_SCORE_PROPIA%'))
ORDER BY o.name, NUMEROS.nro;
GO

/* c. Columnas de cada TBL_FONOS_* */
SELECT 'Financiera_OH_Cobranzas' AS base, t.name AS tabla,
       STUFF((SELECT ',' + c.name FROM [Financiera_OH_Cobranzas].sys.columns AS c
              WHERE c.[object_id] = t.[object_id] ORDER BY c.column_id
              FOR XML PATH(''), TYPE).value('.', 'nvarchar(max)'), 1, 1, '') AS columnas
FROM [Financiera_OH_Cobranzas].sys.tables AS t
WHERE t.name LIKE 'TBL_FONOS%'
ORDER BY t.name;
GO

/* ===================== Interbank_Cobranzas ===================== */

/* a. Objetos de teléfonos, con filas y fechas */
SELECT 'Interbank_Cobranzas' AS base, o.name AS objeto, o.type_desc AS tipo, o.create_date, o.modify_date,
       (SELECT SUM(p.[rows]) FROM [Interbank_Cobranzas].sys.partitions AS p
        WHERE p.[object_id] = o.[object_id] AND p.index_id IN (0, 1)) AS filas
FROM [Interbank_Cobranzas].sys.objects AS o
WHERE o.type IN ('U', 'V', 'P')
  AND (o.name LIKE '%FONO%' OR o.name LIKE '%TELEF%' OR o.name LIKE '%SCORE_PROPIA%')
ORDER BY o.type_desc, o.name;
GO

/* b. Definición completa, en trozos de 4.000 caracteres */
WITH NUMEROS AS (
    SELECT TOP (200) ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) - 1 AS nro
    FROM sys.all_objects
)
SELECT 'Interbank_Cobranzas' AS base, o.name AS objeto, NUMEROS.nro + 1 AS parte,
       SUBSTRING(m.definition, NUMEROS.nro * 4000 + 1, 4000) AS definicion
FROM [Interbank_Cobranzas].sys.objects AS o
INNER JOIN [Interbank_Cobranzas].sys.sql_modules AS m ON m.[object_id] = o.[object_id]
INNER JOIN NUMEROS ON NUMEROS.nro * 4000 < LEN(m.definition)
WHERE o.name LIKE 'SP_MATRIZ_FONOS%' OR (o.type = 'V' AND (o.name LIKE '%FONOS%' OR o.name LIKE 'VW_SCORE_PROPIA%'))
ORDER BY o.name, NUMEROS.nro;
GO

/* c. Columnas de cada TBL_FONOS_* */
SELECT 'Interbank_Cobranzas' AS base, t.name AS tabla,
       STUFF((SELECT ',' + c.name FROM [Interbank_Cobranzas].sys.columns AS c
              WHERE c.[object_id] = t.[object_id] ORDER BY c.column_id
              FOR XML PATH(''), TYPE).value('.', 'nvarchar(max)'), 1, 1, '') AS columnas
FROM [Interbank_Cobranzas].sys.tables AS t
WHERE t.name LIKE 'TBL_FONOS%'
ORDER BY t.name;
GO

/* ===================== Interbank_Propia_Cobranzas ===================== */

/* a. Objetos de teléfonos, con filas y fechas */
SELECT 'Interbank_Propia_Cobranzas' AS base, o.name AS objeto, o.type_desc AS tipo, o.create_date, o.modify_date,
       (SELECT SUM(p.[rows]) FROM [Interbank_Propia_Cobranzas].sys.partitions AS p
        WHERE p.[object_id] = o.[object_id] AND p.index_id IN (0, 1)) AS filas
FROM [Interbank_Propia_Cobranzas].sys.objects AS o
WHERE o.type IN ('U', 'V', 'P')
  AND (o.name LIKE '%FONO%' OR o.name LIKE '%TELEF%' OR o.name LIKE '%SCORE_PROPIA%')
ORDER BY o.type_desc, o.name;
GO

/* b. Definición completa, en trozos de 4.000 caracteres */
WITH NUMEROS AS (
    SELECT TOP (200) ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) - 1 AS nro
    FROM sys.all_objects
)
SELECT 'Interbank_Propia_Cobranzas' AS base, o.name AS objeto, NUMEROS.nro + 1 AS parte,
       SUBSTRING(m.definition, NUMEROS.nro * 4000 + 1, 4000) AS definicion
FROM [Interbank_Propia_Cobranzas].sys.objects AS o
INNER JOIN [Interbank_Propia_Cobranzas].sys.sql_modules AS m ON m.[object_id] = o.[object_id]
INNER JOIN NUMEROS ON NUMEROS.nro * 4000 < LEN(m.definition)
WHERE o.name LIKE 'SP_MATRIZ_FONOS%' OR (o.type = 'V' AND (o.name LIKE '%FONOS%' OR o.name LIKE 'VW_SCORE_PROPIA%'))
ORDER BY o.name, NUMEROS.nro;
GO

/* c. Columnas de cada TBL_FONOS_* */
SELECT 'Interbank_Propia_Cobranzas' AS base, t.name AS tabla,
       STUFF((SELECT ',' + c.name FROM [Interbank_Propia_Cobranzas].sys.columns AS c
              WHERE c.[object_id] = t.[object_id] ORDER BY c.column_id
              FOR XML PATH(''), TYPE).value('.', 'nvarchar(max)'), 1, 1, '') AS columnas
FROM [Interbank_Propia_Cobranzas].sys.tables AS t
WHERE t.name LIKE 'TBL_FONOS%'
ORDER BY t.name;
GO

/* ===================== PROPIA_COBRANZAS ===================== */

/* a. Objetos de teléfonos, con filas y fechas */
SELECT 'PROPIA_COBRANZAS' AS base, o.name AS objeto, o.type_desc AS tipo, o.create_date, o.modify_date,
       (SELECT SUM(p.[rows]) FROM [PROPIA_COBRANZAS].sys.partitions AS p
        WHERE p.[object_id] = o.[object_id] AND p.index_id IN (0, 1)) AS filas
FROM [PROPIA_COBRANZAS].sys.objects AS o
WHERE o.type IN ('U', 'V', 'P')
  AND (o.name LIKE '%FONO%' OR o.name LIKE '%TELEF%' OR o.name LIKE '%SCORE_PROPIA%')
ORDER BY o.type_desc, o.name;
GO

/* b. Definición completa, en trozos de 4.000 caracteres */
WITH NUMEROS AS (
    SELECT TOP (200) ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) - 1 AS nro
    FROM sys.all_objects
)
SELECT 'PROPIA_COBRANZAS' AS base, o.name AS objeto, NUMEROS.nro + 1 AS parte,
       SUBSTRING(m.definition, NUMEROS.nro * 4000 + 1, 4000) AS definicion
FROM [PROPIA_COBRANZAS].sys.objects AS o
INNER JOIN [PROPIA_COBRANZAS].sys.sql_modules AS m ON m.[object_id] = o.[object_id]
INNER JOIN NUMEROS ON NUMEROS.nro * 4000 < LEN(m.definition)
WHERE o.name LIKE 'SP_MATRIZ_FONOS%' OR (o.type = 'V' AND (o.name LIKE '%FONOS%' OR o.name LIKE 'VW_SCORE_PROPIA%'))
ORDER BY o.name, NUMEROS.nro;
GO

/* c. Columnas de cada TBL_FONOS_* */
SELECT 'PROPIA_COBRANZAS' AS base, t.name AS tabla,
       STUFF((SELECT ',' + c.name FROM [PROPIA_COBRANZAS].sys.columns AS c
              WHERE c.[object_id] = t.[object_id] ORDER BY c.column_id
              FOR XML PATH(''), TYPE).value('.', 'nvarchar(max)'), 1, 1, '') AS columnas
FROM [PROPIA_COBRANZAS].sys.tables AS t
WHERE t.name LIKE 'TBL_FONOS%'
ORDER BY t.name;
GO

/* ===================== MiBanco_Cobranzas ===================== */

/* a. Objetos de teléfonos, con filas y fechas */
SELECT 'MiBanco_Cobranzas' AS base, o.name AS objeto, o.type_desc AS tipo, o.create_date, o.modify_date,
       (SELECT SUM(p.[rows]) FROM [MiBanco_Cobranzas].sys.partitions AS p
        WHERE p.[object_id] = o.[object_id] AND p.index_id IN (0, 1)) AS filas
FROM [MiBanco_Cobranzas].sys.objects AS o
WHERE o.type IN ('U', 'V', 'P')
  AND (o.name LIKE '%FONO%' OR o.name LIKE '%TELEF%' OR o.name LIKE '%SCORE_PROPIA%')
ORDER BY o.type_desc, o.name;
GO

/* b. Definición completa, en trozos de 4.000 caracteres */
WITH NUMEROS AS (
    SELECT TOP (200) ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) - 1 AS nro
    FROM sys.all_objects
)
SELECT 'MiBanco_Cobranzas' AS base, o.name AS objeto, NUMEROS.nro + 1 AS parte,
       SUBSTRING(m.definition, NUMEROS.nro * 4000 + 1, 4000) AS definicion
FROM [MiBanco_Cobranzas].sys.objects AS o
INNER JOIN [MiBanco_Cobranzas].sys.sql_modules AS m ON m.[object_id] = o.[object_id]
INNER JOIN NUMEROS ON NUMEROS.nro * 4000 < LEN(m.definition)
WHERE o.name LIKE 'SP_MATRIZ_FONOS%' OR (o.type = 'V' AND (o.name LIKE '%FONOS%' OR o.name LIKE 'VW_SCORE_PROPIA%'))
ORDER BY o.name, NUMEROS.nro;
GO

/* c. Columnas de cada TBL_FONOS_* */
SELECT 'MiBanco_Cobranzas' AS base, t.name AS tabla,
       STUFF((SELECT ',' + c.name FROM [MiBanco_Cobranzas].sys.columns AS c
              WHERE c.[object_id] = t.[object_id] ORDER BY c.column_id
              FOR XML PATH(''), TYPE).value('.', 'nvarchar(max)'), 1, 1, '') AS columnas
FROM [MiBanco_Cobranzas].sys.tables AS t
WHERE t.name LIKE 'TBL_FONOS%'
ORDER BY t.name;
GO

/* ===================== Desarrollo ===================== */

/* a. Objetos de teléfonos, con filas y fechas */
SELECT 'Desarrollo' AS base, o.name AS objeto, o.type_desc AS tipo, o.create_date, o.modify_date,
       (SELECT SUM(p.[rows]) FROM [Desarrollo].sys.partitions AS p
        WHERE p.[object_id] = o.[object_id] AND p.index_id IN (0, 1)) AS filas
FROM [Desarrollo].sys.objects AS o
WHERE o.type IN ('U', 'V', 'P')
  AND (o.name IN ('SP_FOTO_GESTION', 'SP_OBTENER_TELEFONOS', 'TEMP_TELEFONOS'))
ORDER BY o.type_desc, o.name;
GO

/* b. Definición completa, en trozos de 4.000 caracteres */
WITH NUMEROS AS (
    SELECT TOP (200) ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) - 1 AS nro
    FROM sys.all_objects
)
SELECT 'Desarrollo' AS base, o.name AS objeto, NUMEROS.nro + 1 AS parte,
       SUBSTRING(m.definition, NUMEROS.nro * 4000 + 1, 4000) AS definicion
FROM [Desarrollo].sys.objects AS o
INNER JOIN [Desarrollo].sys.sql_modules AS m ON m.[object_id] = o.[object_id]
INNER JOIN NUMEROS ON NUMEROS.nro * 4000 < LEN(m.definition)
WHERE o.name IN ('SP_FOTO_GESTION', 'SP_OBTENER_TELEFONOS')
ORDER BY o.name, NUMEROS.nro;
GO
