/* =====================================================================================
   DIAGNÓSTICO 4 — CATÁLOGO DE RESULTADOS Y VOLÚMENES (solo lectura)
   Fecha: 14/11/2026

   Para qué: el score nuevo se arma desde los eventos de marcación (gestión humana, máquina y
   centralita) con UN catálogo de resultados para todas las carteras. Necesito:
     1. el catálogo de indicadores de SISCOB;
     2. qué indicadores se usan de verdad por cartera (últimos 30 días);
     3. qué estados trae la centralita (últimos 30 días);
     4. el volumen de 6 meses, para dimensionar el proceso;
     5. la estructura de los teléfonos y de la lista negra de SISCOB;
     6. los índices de las tablas grandes, para que el proceso no las recorra completas.

   No modifica nada. Puede tardar unos minutos (lee gestiones de 30 días y cuenta 6 meses):
   ejecútalo cuando la operación no esté cargada.
   Ejecutar igual que el 3: Resultados en archivo (Ctrl+Shift+F) y F5.
   ===================================================================================== */

USE siscob;
GO
SET NOCOUNT ON;
SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED;
GO

/* 1. Catálogo completo de indicadores */
SELECT * FROM siscob.dbo.INDICADOR WITH (NOLOCK) ORDER BY IdIndicador;
GO

/* 2a. Gestión humana de los últimos 30 días, por cartera e indicador */
DECLARE @desde DATE = DATEADD(DAY, -30, CAST(GETDATE() AS DATE));
SELECT g.idCartera, g.IdIndicador, i.DescripcionIndicador, i.TipoContacto,
       COUNT_BIG(*) AS gestiones, COUNT(DISTINCT g.telefono) AS telefonos
FROM siscob.dbo.gestion AS g WITH (NOLOCK)
LEFT JOIN siscob.dbo.INDICADOR AS i WITH (NOLOCK) ON i.IdIndicador = g.IdIndicador
WHERE g.Fecha >= @desde
GROUP BY g.idCartera, g.IdIndicador, i.DescripcionIndicador, i.TipoContacto
ORDER BY g.idCartera, gestiones DESC;
GO

/* 2b. Lo mismo para pgestion (¿gestión de máquina / predictivo?) */
DECLARE @desde DATE = DATEADD(DAY, -30, CAST(GETDATE() AS DATE));
SELECT g.idCartera, g.IdIndicador, i.DescripcionIndicador, i.TipoContacto,
       COUNT_BIG(*) AS gestiones, COUNT(DISTINCT g.telefono) AS telefonos
FROM siscob.dbo.pgestion AS g WITH (NOLOCK)
LEFT JOIN siscob.dbo.INDICADOR AS i WITH (NOLOCK) ON i.IdIndicador = g.IdIndicador
WHERE g.Fecha >= @desde
GROUP BY g.idCartera, g.IdIndicador, i.DescripcionIndicador, i.TipoContacto
ORDER BY g.idCartera, gestiones DESC;
GO

/* 3. Estados de la centralita de los últimos 30 días */
DECLARE @desde DATE = DATEADD(DAY, -30, CAST(GETDATE() AS DATE));
SELECT c.ESTADO,
       CASE WHEN ISNULL(c.ANEXO, 0) = 0 THEN 'SIN ANEXO (no llegó a agente)' ELSE 'CON ANEXO' END AS anexo,
       COUNT_BIG(*) AS llamadas, COUNT(DISTINCT c.TELEFONO) AS telefonos
FROM Desarrollo.dbo.CENTRALITA AS c WITH (NOLOCK)
WHERE c.[START] >= @desde
GROUP BY c.ESTADO, CASE WHEN ISNULL(c.ANEXO, 0) = 0 THEN 'SIN ANEXO (no llegó a agente)' ELSE 'CON ANEXO' END
ORDER BY llamadas DESC;
GO

/* 4. Volumen de 6 meses por mes */
DECLARE @desde6 DATE = DATEADD(MONTH, -6, CAST(GETDATE() AS DATE));
SELECT 'gestion' AS tabla, FORMAT(Fecha, 'yyyyMM') AS mes, COUNT_BIG(*) AS filas
FROM siscob.dbo.gestion WITH (NOLOCK) WHERE Fecha >= @desde6 GROUP BY FORMAT(Fecha, 'yyyyMM')
UNION ALL
SELECT 'pgestion', FORMAT(Fecha, 'yyyyMM'), COUNT_BIG(*)
FROM siscob.dbo.pgestion WITH (NOLOCK) WHERE Fecha >= @desde6 GROUP BY FORMAT(Fecha, 'yyyyMM')
UNION ALL
SELECT 'CENTRALITA', FORMAT([START], 'yyyyMM'), COUNT_BIG(*)
FROM Desarrollo.dbo.CENTRALITA WITH (NOLOCK) WHERE [START] >= @desde6 GROUP BY FORMAT([START], 'yyyyMM')
ORDER BY tabla, mes;
GO

/* 5a. Columnas de las tablas de origen */
SELECT 'siscob.dbo.' + t.name AS tabla, c.column_id, c.name AS columna, ty.name AS tipo, c.max_length
FROM siscob.sys.tables AS t
INNER JOIN siscob.sys.columns AS c ON c.[object_id] = t.[object_id]
INNER JOIN siscob.sys.types AS ty ON ty.user_type_id = c.user_type_id
WHERE t.name IN ('telefonos', 'telefonos_LN', 'gestion', 'pgestion', 'CLIENTE', 'INDICADOR')
UNION ALL
SELECT 'Desarrollo.dbo.' + t.name, c.column_id, c.name, ty.name, c.max_length
FROM Desarrollo.sys.tables AS t
INNER JOIN Desarrollo.sys.columns AS c ON c.[object_id] = t.[object_id]
INNER JOIN Desarrollo.sys.types AS ty ON ty.user_type_id = c.user_type_id
WHERE t.name IN ('CENTRALITA')
ORDER BY tabla, column_id;
GO

/* 5b. Teléfonos de SISCOB: largo y primer dígito (¿cuántos fijos se descartan hoy?) */
SELECT LEN(LTRIM(RTRIM(telefono))) AS largo, LEFT(LTRIM(RTRIM(telefono)), 1) AS primer_digito,
       COUNT_BIG(*) AS filas
FROM siscob.dbo.telefonos WITH (NOLOCK)
GROUP BY LEN(LTRIM(RTRIM(telefono))), LEFT(LTRIM(RTRIM(telefono)), 1)
ORDER BY filas DESC;
GO

/* 5c. Lista negra de SISCOB por empresa */
SELECT idempresa, estado, COUNT_BIG(*) AS filas, MIN(fecha) AS desde, MAX(fecha) AS hasta
FROM siscob.dbo.telefonos_LN WITH (NOLOCK)
GROUP BY idempresa, estado
ORDER BY idempresa, estado;
GO

/* 6. Índices de las tablas grandes */
SELECT 'siscob.dbo.' + t.name AS tabla, i.name AS indice, i.type_desc,
       STUFF((SELECT ',' + c.name FROM siscob.sys.index_columns AS ic
              INNER JOIN siscob.sys.columns AS c ON c.[object_id] = ic.[object_id] AND c.column_id = ic.column_id
              WHERE ic.[object_id] = i.[object_id] AND ic.index_id = i.index_id AND ic.is_included_column = 0
              ORDER BY ic.key_ordinal FOR XML PATH(''), TYPE).value('.', 'nvarchar(max)'), 1, 1, '') AS columnas,
       (SELECT SUM(p.[rows]) FROM siscob.sys.partitions AS p
        WHERE p.[object_id] = t.[object_id] AND p.index_id IN (0, 1)) AS filas_tabla
FROM siscob.sys.tables AS t
INNER JOIN siscob.sys.indexes AS i ON i.[object_id] = t.[object_id]
WHERE t.name IN ('telefonos', 'telefonos_LN', 'gestion', 'pgestion', 'CLIENTE')
UNION ALL
SELECT 'Desarrollo.dbo.' + t.name, i.name, i.type_desc,
       STUFF((SELECT ',' + c.name FROM Desarrollo.sys.index_columns AS ic
              INNER JOIN Desarrollo.sys.columns AS c ON c.[object_id] = ic.[object_id] AND c.column_id = ic.column_id
              WHERE ic.[object_id] = i.[object_id] AND ic.index_id = i.index_id AND ic.is_included_column = 0
              ORDER BY ic.key_ordinal FOR XML PATH(''), TYPE).value('.', 'nvarchar(max)'), 1, 1, ''),
       (SELECT SUM(p.[rows]) FROM Desarrollo.sys.partitions AS p
        WHERE p.[object_id] = t.[object_id] AND p.index_id IN (0, 1))
FROM Desarrollo.sys.tables AS t
INNER JOIN Desarrollo.sys.indexes AS i ON i.[object_id] = t.[object_id]
WHERE t.name IN ('CENTRALITA')
ORDER BY tabla, indice;
GO
