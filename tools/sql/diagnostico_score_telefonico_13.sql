/* =====================================================================================
   Diagnóstico 13 · Fuentes para la gestión del cliente y del teléfono en el generador
   SOLO LECTURA. 15/11/2026.

   Para construir la fase 7 (condición SISCOB, mejor y última gestión del mes, malla, cobertura,
   estado de PDP, frecuencia, seguimiento, IVR/SMS) necesito saber dónde está cada dato:
     1 · Columnas de siscob.dbo.Cliente (¿dónde está la CONDICION?)
     2 · Tablas y vistas de SISCOB con nombres de condición, seguimiento, cobertura o estado
     3 · siscob.dbo.Indicador: columnas y si tiene un orden/peso para elegir el "mejor" indicador
     4 · Columnas de siscob.dbo.gestion y siscob.dbo.pgestion
     5 · De dónde saca el Excel de MiBanco castigo CONDICION, EQUIPO, FOCO, COBERTURA, ESTADO_SEGUIMIENTO,
         FRECUENCIA_LLAMADA (objetos de MiBanco_Cobranzas que los mencionan)
     6 · Tablas en cualquier base con IVR, TTS, LUNA, SMS, MOWA o SINAPSIS en el nombre
     7 · Rango de fechas de score.TelefonoDia (historial disponible por teléfono)

   Sugerencia: Herramientas > Opciones > Resultados de consultas > Texto: "Máximo de caracteres" = 8192,
   y guarda el resultado (Ctrl+Shift+F) en tools/salidas/resultados_diagnostico_score_13.txt.
   ===================================================================================== */
USE CobAuto;
SET NOCOUNT ON;

PRINT '--- 1 · Columnas de siscob.dbo.Cliente';
SELECT c.column_id AS N, c.name AS Columna, t.name AS Tipo, c.max_length AS Largo
FROM siscob.sys.columns AS c
INNER JOIN siscob.sys.types AS t ON t.user_type_id = c.user_type_id
WHERE c.object_id = OBJECT_ID('siscob.dbo.Cliente')
ORDER BY c.column_id;

PRINT '--- 2 · Tablas/vistas de SISCOB por nombre';
SELECT s.name AS Esquema, o.name AS Objeto, o.type_desc AS Tipo,
       (SELECT SUM(p.rows) FROM siscob.sys.partitions AS p WHERE p.object_id = o.object_id AND p.index_id IN (0, 1)) AS Filas
FROM siscob.sys.objects AS o
INNER JOIN siscob.sys.schemas AS s ON s.schema_id = o.schema_id
WHERE o.type IN ('U', 'V')
  AND (o.name LIKE '%condic%' OR o.name LIKE '%segui%' OR o.name LIKE '%cobert%' OR o.name LIKE '%estado%'
       OR o.name LIKE '%equipo%' OR o.name LIKE '%foco%' OR o.name LIKE '%indicador%' OR o.name LIKE '%tipocontacto%')
ORDER BY o.name;

PRINT '--- 2b · Columnas con CONDICION / SEGUIMIENTO / COBERTURA en tablas de SISCOB';
SELECT o.name AS Tabla, c.name AS Columna, t.name AS Tipo
FROM siscob.sys.columns AS c
INNER JOIN siscob.sys.objects AS o ON o.object_id = c.object_id AND o.type IN ('U', 'V')
INNER JOIN siscob.sys.types AS t ON t.user_type_id = c.user_type_id
WHERE c.name LIKE '%condic%' OR c.name LIKE '%segui%' OR c.name LIKE '%cobert%'
ORDER BY o.name, c.name;

PRINT '--- 3 · siscob.dbo.Indicador: columnas';
SELECT c.column_id AS N, c.name AS Columna, t.name AS Tipo
FROM siscob.sys.columns AS c
INNER JOIN siscob.sys.types AS t ON t.user_type_id = c.user_type_id
WHERE c.object_id = OBJECT_ID('siscob.dbo.Indicador')
ORDER BY c.column_id;

PRINT '--- 3b · Indicadores usados en los últimos 60 días por cartera y tipo de contacto';
SELECT g.idCartera AS IdCartera, LTRIM(RTRIM(i.TipoContacto)) AS TipoContacto, g.IdIndicador,
       i.DescripcionIndicador, COUNT_BIG(*) AS Gestiones
FROM siscob.dbo.gestion AS g WITH (NOLOCK)
LEFT JOIN siscob.dbo.Indicador AS i WITH (NOLOCK) ON i.IdIndicador = g.IdIndicador
WHERE g.Fecha >= DATEADD(DAY, -60, CAST(GETDATE() AS DATE))
  AND g.idCartera IN (SELECT IdCartera FROM ControlCobranza.bl.EntidadCartera)
GROUP BY g.idCartera, LTRIM(RTRIM(i.TipoContacto)), g.IdIndicador, i.DescripcionIndicador
ORDER BY g.idCartera, TipoContacto, g.IdIndicador;

PRINT '--- 4 · Columnas de siscob.dbo.gestion';
SELECT c.column_id AS N, c.name AS Columna, t.name AS Tipo
FROM siscob.sys.columns AS c
INNER JOIN siscob.sys.types AS t ON t.user_type_id = c.user_type_id
WHERE c.object_id = OBJECT_ID('siscob.dbo.gestion')
ORDER BY c.column_id;

PRINT '--- 4b · Columnas de siscob.dbo.pgestion';
SELECT c.column_id AS N, c.name AS Columna, t.name AS Tipo
FROM siscob.sys.columns AS c
INNER JOIN siscob.sys.types AS t ON t.user_type_id = c.user_type_id
WHERE c.object_id = OBJECT_ID('siscob.dbo.pgestion')
ORDER BY c.column_id;

PRINT '--- 5 · Objetos de MiBanco_Cobranzas que arman los segmentos del Excel';
SELECT o.name AS Objeto, o.type_desc AS Tipo,
       CASE WHEN m.definition LIKE '%CONDICION%' THEN 'CONDICION ' ELSE '' END
     + CASE WHEN m.definition LIKE '%EQUIPO%' THEN 'EQUIPO ' ELSE '' END
     + CASE WHEN m.definition LIKE '%FOCO%' THEN 'FOCO ' ELSE '' END
     + CASE WHEN m.definition LIKE '%COBERTURA%' THEN 'COBERTURA ' ELSE '' END
     + CASE WHEN m.definition LIKE '%SEGUIMIENTO%' THEN 'SEGUIMIENTO ' ELSE '' END
     + CASE WHEN m.definition LIKE '%FRECUENCIA%' THEN 'FRECUENCIA ' ELSE '' END
     + CASE WHEN m.definition LIKE '%ESTADO_PDP%' THEN 'ESTADO_PDP ' ELSE '' END AS Menciona
FROM MiBanco_Cobranzas.sys.sql_modules AS m
INNER JOIN MiBanco_Cobranzas.sys.objects AS o ON o.object_id = m.object_id
WHERE m.definition LIKE '%COBERTURA%' OR m.definition LIKE '%SEGUIMIENTO%' OR m.definition LIKE '%FRECUENCIA%'
   OR m.definition LIKE '%CONDICION%' OR m.definition LIKE '%ESTADO_PDP%'
ORDER BY o.name;

PRINT '--- 5b · Líneas de esos objetos que calculan los segmentos (una fila por línea)';
IF OBJECT_ID('tempdb..#lineas') IS NOT NULL DROP TABLE #lineas;
CREATE TABLE #lineas (Objeto SYSNAME, N INT, Linea NVARCHAR(4000));
DECLARE @obj SYSNAME, @def NVARCHAR(MAX), @pos INT, @sig INT, @n INT;
DECLARE cur CURSOR LOCAL FAST_FORWARD FOR
    SELECT o.name, m.definition
    FROM MiBanco_Cobranzas.sys.sql_modules AS m
    INNER JOIN MiBanco_Cobranzas.sys.objects AS o ON o.object_id = m.object_id
    WHERE m.definition LIKE '%COBERTURA%' OR m.definition LIKE '%SEGUIMIENTO%' OR m.definition LIKE '%FRECUENCIA%'
       OR m.definition LIKE '%CONDICION%' OR m.definition LIKE '%ESTADO_PDP%';
OPEN cur;
FETCH NEXT FROM cur INTO @obj, @def;
WHILE @@FETCH_STATUS = 0
BEGIN
    SELECT @pos = 1, @n = 0, @def = REPLACE(@def, CHAR(13), '');
    WHILE @pos <= LEN(@def)
    BEGIN
        SET @sig = CHARINDEX(CHAR(10), @def, @pos);
        IF @sig = 0 SET @sig = LEN(@def) + 1;
        SET @n += 1;
        INSERT INTO #lineas VALUES (@obj, @n, LEFT(SUBSTRING(@def, @pos, @sig - @pos), 4000));
        SET @pos = @sig + 1;
    END;
    FETCH NEXT FROM cur INTO @obj, @def;
END;
CLOSE cur; DEALLOCATE cur;
-- Solo las líneas que mencionan los segmentos, con 3 líneas antes y después para entender de dónde salen
SELECT l.Objeto, l.N, l.Linea
FROM #lineas AS l
WHERE EXISTS (SELECT 1 FROM #lineas AS k
              WHERE k.Objeto = l.Objeto AND l.N BETWEEN k.N - 3 AND k.N + 3
                AND (k.Linea LIKE '%COBERTURA%' OR k.Linea LIKE '%SEGUIMIENTO%' OR k.Linea LIKE '%FRECUENCIA%'
                     OR k.Linea LIKE '%CONDICION%' OR k.Linea LIKE '%ESTADO_PDP%' OR k.Linea LIKE '%EQUIPO%'
                     OR k.Linea LIKE '%FOCO%'))
ORDER BY l.Objeto, l.N;

PRINT '--- 6 · Tablas con IVR, TTS, LUNA, SMS, MOWA o SINAPSIS en el nombre (todas las bases)';
IF OBJECT_ID('tempdb..#canales') IS NOT NULL DROP TABLE #canales;
CREATE TABLE #canales (Base SYSNAME, Esquema SYSNAME, Tabla SYSNAME, Filas BIGINT NULL);
DECLARE @db SYSNAME, @sql NVARCHAR(MAX);
DECLARE bases CURSOR LOCAL FAST_FORWARD FOR
    SELECT name FROM sys.databases WHERE state_desc = 'ONLINE' AND database_id > 4 AND HAS_DBACCESS(name) = 1;
OPEN bases;
FETCH NEXT FROM bases INTO @db;
WHILE @@FETCH_STATUS = 0
BEGIN
    SET @sql = N'INSERT INTO #canales SELECT ' + QUOTENAME(@db, '''') + N', s.name, t.name,
        (SELECT SUM(p.rows) FROM ' + QUOTENAME(@db) + N'.sys.partitions AS p WHERE p.object_id = t.object_id AND p.index_id IN (0, 1))
        FROM ' + QUOTENAME(@db) + N'.sys.tables AS t INNER JOIN ' + QUOTENAME(@db) + N'.sys.schemas AS s ON s.schema_id = t.schema_id
        WHERE t.name LIKE ''%IVR%'' OR t.name LIKE ''%TTS%'' OR t.name LIKE ''%LUNA%'' OR t.name LIKE ''%SMS%''
           OR t.name LIKE ''%MOWA%'' OR t.name LIKE ''%SINAPSIS%''';
    BEGIN TRY EXEC sp_executesql @sql; END TRY BEGIN CATCH END CATCH;
    FETCH NEXT FROM bases INTO @db;
END;
CLOSE bases; DEALLOCATE bases;
SELECT * FROM #canales ORDER BY Base, Tabla;

PRINT '--- 7 · Historial disponible en score.TelefonoDia';
SELECT MIN(Fecha) AS Desde, MAX(Fecha) AS Hasta, COUNT_BIG(*) AS Filas FROM score.TelefonoDia;
GO
