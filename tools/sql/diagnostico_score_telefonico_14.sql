/* =====================================================================================
   Diagnóstico 14 · IVR/SMS y validación de la fase 7
   SOLO LECTURA. 16/11/2026.

   1 · Estructura de las tablas de IVR y SMS encontradas en el diagnóstico 13 (sección 6): columnas,
       rango de fechas y valores de las columnas de estado/resultado/cartera (muestra de 300 mil filas).
       Con esto se decide si "resultado de IVR/TTS" y "no tocado por IVR o SMS" se pueden armar.
   2 · Regla de ESTADO de MiBanco_Cobranzas.dbo.VW_SEGUIMIENTOS (el diagnóstico 13 no trajo esas líneas)
       y sus valores de hoy.
   3 · siscob.dbo.Condicion completa (49 filas): para revisar las etiquetas de la condición SISCOB.
   4 · Índices de siscob.dbo.gestion, siscob.dbo.COMPROMISO y siscob.dbo.Cliente (velocidad de la fase 7).

   Sugerencia: Herramientas > Opciones > Resultados de consultas > Texto: "Máximo de caracteres" = 8192,
   y guarda el resultado (Ctrl+Shift+F) en tools/salidas/resultados_diagnostico_score_14.txt.
   ===================================================================================== */
USE CobAuto;
SET NOCOUNT ON;

DECLARE @Tablas TABLE (Orden INT IDENTITY(1, 1), Base SYSNAME, Esquema SYSNAME, Tabla SYSNAME);
INSERT INTO @Tablas (Base, Esquema, Tabla) VALUES
    ('CANALES_ALTERNOS', 'dbo', 'CAMPAIGN_IVR'),
    ('CANALES_ALTERNOS', 'dbo', 'CAMPAIGN_SMS'),
    ('MiBanco_Cobranzas', 'dbo', 'detalle_sms'),
    ('Compartamos_Castigo_Cobranzas', 'dbo', 'detalle_sms'),
    ('Interbank_Cobranzas', 'dbo', 'Resultados_IVR'),
    ('Interbank_Cobranzas', 'dbo', 'Resultados_SMS'),
    ('Centro_Financiero', 'consumo', 'SmsTimbrado');

DECLARE @i INT = 1, @n INT = (SELECT COUNT(*) FROM @Tablas), @Base SYSNAME, @Esq SYSNAME, @Tab SYSNAME,
        @Obj NVARCHAR(400), @sql NVARCHAR(MAX), @Col SYSNAME;

WHILE @i <= @n
BEGIN
    SELECT @Base = Base, @Esq = Esquema, @Tab = Tabla FROM @Tablas WHERE Orden = @i;
    SET @Obj = QUOTENAME(@Base) + N'.' + QUOTENAME(@Esq) + N'.' + QUOTENAME(@Tab);
    PRINT '';
    PRINT CONCAT('--- 1.', @i, ' · ', @Base, '.', @Esq, '.', @Tab);

    BEGIN TRY
        -- Columnas
        SET @sql = N'SELECT c.column_id AS N, c.name AS Columna, t.name AS Tipo, c.max_length AS Largo
                     FROM ' + QUOTENAME(@Base) + N'.sys.columns AS c
                     INNER JOIN ' + QUOTENAME(@Base) + N'.sys.types AS t ON t.user_type_id = c.user_type_id
                     WHERE c.object_id = OBJECT_ID(@o) ORDER BY c.column_id;';
        EXEC sys.sp_executesql @sql, N'@o NVARCHAR(400)', @o = @Obj;

        -- Rango de cada columna de fecha
        CREATE TABLE #col (Columna SYSNAME, Tipo SYSNAME);
        SET @sql = N'INSERT INTO #col (Columna, Tipo)
                     SELECT c.name, t.name FROM ' + QUOTENAME(@Base) + N'.sys.columns AS c
                     INNER JOIN ' + QUOTENAME(@Base) + N'.sys.types AS t ON t.user_type_id = c.user_type_id
                     WHERE c.object_id = OBJECT_ID(@o);';
        EXEC sys.sp_executesql @sql, N'@o NVARCHAR(400)', @o = @Obj;

        DECLARE cf CURSOR LOCAL FAST_FORWARD FOR
            SELECT Columna FROM #col WHERE Tipo IN ('date', 'datetime', 'datetime2', 'smalldatetime', 'datetimeoffset');
        OPEN cf; FETCH NEXT FROM cf INTO @Col;
        WHILE @@FETCH_STATUS = 0
        BEGIN
            SET @sql = N'SELECT ''' + REPLACE(@Col, '''', '''''') + N''' AS ColumnaFecha, MIN(' + QUOTENAME(@Col) + N') AS Desde,
                                MAX(' + QUOTENAME(@Col) + N') AS Hasta,
                                SUM(CASE WHEN ' + QUOTENAME(@Col) + N' >= DATEADD(DAY, -30, GETDATE()) THEN 1 ELSE 0 END) AS Filas30Dias
                         FROM ' + @Obj + N' WITH (NOLOCK);';
            EXEC sys.sp_executesql @sql;
            FETCH NEXT FROM cf INTO @Col;
        END;
        CLOSE cf; DEALLOCATE cf;

        -- Valores de estado / resultado / cartera / campaña (muestra de 300 mil filas)
        DECLARE cv CURSOR LOCAL FAST_FORWARD FOR
            SELECT Columna FROM #col
            WHERE Tipo IN ('varchar', 'nvarchar', 'char', 'nchar', 'int', 'smallint', 'tinyint', 'bit')
              AND (Columna LIKE '%estado%' OR Columna LIKE '%status%' OR Columna LIKE '%result%' OR Columna LIKE '%respuesta%'
                   OR Columna LIKE '%cartera%' OR Columna LIKE '%campa%' OR Columna LIKE '%tipo%' OR Columna LIKE '%entreg%'
                   OR Columna LIKE '%contest%' OR Columna LIKE '%dur%' OR Columna LIKE '%opcion%' OR Columna LIKE '%digit%');
        OPEN cv; FETCH NEXT FROM cv INTO @Col;
        WHILE @@FETCH_STATUS = 0
        BEGIN
            SET @sql = N'SELECT TOP (15) ''' + REPLACE(@Col, '''', '''''') + N''' AS Columna, CONVERT(NVARCHAR(100), x.v) AS Valor, COUNT(*) AS Filas
                         FROM (SELECT TOP (300000) ' + QUOTENAME(@Col) + N' AS v FROM ' + @Obj + N' WITH (NOLOCK)) AS x
                         GROUP BY x.v ORDER BY COUNT(*) DESC;';
            EXEC sys.sp_executesql @sql;
            FETCH NEXT FROM cv INTO @Col;
        END;
        CLOSE cv; DEALLOCATE cv;
        DROP TABLE #col;
    END TRY
    BEGIN CATCH
        PRINT CONCAT('    No se pudo leer: ', ERROR_MESSAGE());
        IF CURSOR_STATUS('local', 'cf') >= -1 DEALLOCATE cf;
        IF CURSOR_STATUS('local', 'cv') >= -1 DEALLOCATE cv;
        IF OBJECT_ID('tempdb..#col') IS NOT NULL DROP TABLE #col;
    END CATCH;
    SET @i += 1;
END;

PRINT '';
PRINT '--- 2 · MiBanco_Cobranzas.dbo.VW_SEGUIMIENTOS: líneas 9 a 60 de la definición';
;WITH d AS (SELECT OBJECT_DEFINITION(OBJECT_ID('MiBanco_Cobranzas.dbo.VW_SEGUIMIENTOS')) AS Texto),
l AS (
    SELECT CAST(1 AS INT) AS N, CAST(NULL AS NVARCHAR(MAX)) AS Linea,
           REPLACE((SELECT Texto FROM d), CHAR(13), N'') + CHAR(10) AS Resto
    UNION ALL
    SELECT N + 1, LEFT(Resto, CHARINDEX(CHAR(10), Resto) - 1), STUFF(Resto, 1, CHARINDEX(CHAR(10), Resto), N'')
    FROM l WHERE CHARINDEX(CHAR(10), Resto) > 0 AND N <= 120
)
SELECT N - 1 AS N, Linea FROM l WHERE N - 1 BETWEEN 9 AND 60 ORDER BY N
OPTION (MAXRECURSION 200);

PRINT '--- 2b · Valores de hoy en VW_SEGUIMIENTOS';
BEGIN TRY
    EXEC sys.sp_executesql N'SELECT ESTADO, COUNT(*) AS Clientes, MIN(FECHA) AS FechaMin, MAX(FECHA) AS FechaMax
                             FROM MiBanco_Cobranzas.dbo.VW_SEGUIMIENTOS GROUP BY ESTADO ORDER BY COUNT(*) DESC;';
END TRY
BEGIN CATCH
    PRINT CONCAT('    No se pudo leer: ', ERROR_MESSAGE());
END CATCH;

PRINT '--- 3 · siscob.dbo.Condicion';
SELECT * FROM siscob.dbo.Condicion WITH (NOLOCK) ORDER BY IdCondicion;

PRINT '--- 3b · Clientes por condición (carteras con score)';
SELECT cl.IdCartera, cl.IdCondicion, COUNT(*) AS Clientes
FROM siscob.dbo.Cliente AS cl WITH (NOLOCK)
WHERE cl.IdCartera IN (SELECT DISTINCT IdCartera FROM score.TelefonoUniverso)
  AND UPPER(LTRIM(RTRIM(ISNULL(cl.Estado, '')))) IN ('A', 'N')
GROUP BY cl.IdCartera, cl.IdCondicion
ORDER BY cl.IdCartera, COUNT(*) DESC;

PRINT '--- 4 · Índices de gestion, COMPROMISO y Cliente (siscob)';
SELECT o.name AS Tabla, i.name AS Indice, i.type_desc AS Tipo,
       STUFF((SELECT ', ' + c.name FROM siscob.sys.index_columns AS ic
              INNER JOIN siscob.sys.columns AS c ON c.object_id = ic.object_id AND c.column_id = ic.column_id
              WHERE ic.object_id = i.object_id AND ic.index_id = i.index_id AND ic.is_included_column = 0
              ORDER BY ic.key_ordinal FOR XML PATH('')), 1, 2, '') AS Claves,
       STUFF((SELECT ', ' + c.name FROM siscob.sys.index_columns AS ic
              INNER JOIN siscob.sys.columns AS c ON c.object_id = ic.object_id AND c.column_id = ic.column_id
              WHERE ic.object_id = i.object_id AND ic.index_id = i.index_id AND ic.is_included_column = 1
              FOR XML PATH('')), 1, 2, '') AS Incluidas
FROM siscob.sys.indexes AS i
INNER JOIN siscob.sys.objects AS o ON o.object_id = i.object_id
WHERE o.name IN ('gestion', 'COMPROMISO', 'Cliente', 'pgestion') AND i.type > 0
ORDER BY o.name, i.index_id;

PRINT '--- 4b · Columnas de siscob.dbo.COMPROMISO';
SELECT c.column_id AS N, c.name AS Columna, t.name AS Tipo
FROM siscob.sys.columns AS c
INNER JOIN siscob.sys.types AS t ON t.user_type_id = c.user_type_id
WHERE c.object_id = OBJECT_ID('siscob.dbo.COMPROMISO')
ORDER BY c.column_id;

PRINT '';
PRINT CONCAT('Hora de finalización: ', CONVERT(VARCHAR(33), SYSDATETIMEOFFSET(), 126));
