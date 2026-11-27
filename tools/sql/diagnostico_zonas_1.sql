/* =====================================================================================
   diagnostico_zonas_1.sql  ·  solo lectura  ·  < 1 min
   Control de zonas (27/11/2026): Interbank pidió detener toda gestión en Piura (columna PROVINCIA_CLIENTE de la
   base de cuentas activas). Antes de construir el bloqueo por zona hay que saber, por cartera, de dónde sale la
   ubicación del cliente. Este script busca en todas las bases del servidor las columnas de ubicación.
   Ctrl+T y guardar en tools/salidas/resultado_zonas_1.txt
   ===================================================================================== */
SET NOCOUNT ON;

IF OBJECT_ID('tempdb..#col') IS NOT NULL DROP TABLE #col;
CREATE TABLE #col (Base SYSNAME, Esquema SYSNAME, Tabla SYSNAME, Columna SYSNAME, Tipo SYSNAME, Filas BIGINT NULL);

DECLARE @db SYSNAME, @sql NVARCHAR(MAX);
DECLARE c CURSOR LOCAL FAST_FORWARD FOR
    SELECT name FROM sys.databases
    WHERE database_id > 4 AND state_desc = 'ONLINE' AND HAS_DBACCESS(name) = 1;
OPEN c; FETCH NEXT FROM c INTO @db;
WHILE @@FETCH_STATUS = 0
BEGIN
    SET @sql = N'USE ' + QUOTENAME(@db) + N';
        INSERT INTO #col (Base, Esquema, Tabla, Columna, Tipo, Filas)
        SELECT DB_NAME(), s.name, t.name, col.name, ty.name,
               (SELECT SUM(p.rows) FROM sys.partitions p WHERE p.object_id = t.object_id AND p.index_id IN (0, 1))
        FROM sys.tables t
        JOIN sys.schemas s ON s.schema_id = t.schema_id
        JOIN sys.columns col ON col.object_id = t.object_id
        JOIN sys.types ty ON ty.user_type_id = col.user_type_id
        WHERE col.name LIKE ''%PROVINCIA%'' OR col.name LIKE ''%DEPARTAMENTO%'' OR col.name LIKE ''%DISTRITO%''
           OR col.name LIKE ''%UBIGEO%'' OR col.name LIKE ''%REGION%'' OR col.name LIKE ''%DEPARTAM%'';';
    BEGIN TRY EXEC sys.sp_executesql @sql; END TRY BEGIN CATCH END CATCH;
    FETCH NEXT FROM c INTO @db;
END
CLOSE c; DEALLOCATE c;

PRINT '=== 1. Columnas de ubicación por base y tabla (tablas con filas) ===';
SELECT Base, Esquema, Tabla, Filas, STRING_AGG(Columna, ', ') WITHIN GROUP (ORDER BY Columna) AS Columnas
FROM #col WHERE ISNULL(Filas, 0) > 0
GROUP BY Base, Esquema, Tabla, Filas
ORDER BY Base, Tabla;

PRINT '=== 2. Valores de PROVINCIA_CLIENTE (Interbank) donde exista esa columna ===';
DECLARE @b SYSNAME, @e SYSNAME, @t SYSNAME;
DECLARE c2 CURSOR LOCAL FAST_FORWARD FOR
    SELECT Base, Esquema, Tabla FROM #col WHERE Columna = 'PROVINCIA_CLIENTE' AND ISNULL(Filas, 0) > 0;
OPEN c2; FETCH NEXT FROM c2 INTO @b, @e, @t;
WHILE @@FETCH_STATUS = 0
BEGIN
    SET @sql = N'SELECT ''' + @b + N'.' + @e + N'.' + @t + N''' AS Tabla, UPPER(LTRIM(RTRIM(PROVINCIA_CLIENTE))) AS Provincia, COUNT(*) AS Filas
                 FROM ' + QUOTENAME(@b) + N'.' + QUOTENAME(@e) + N'.' + QUOTENAME(@t) + N' WITH (NOLOCK)
                 GROUP BY UPPER(LTRIM(RTRIM(PROVINCIA_CLIENTE))) ORDER BY Filas DESC;';
    BEGIN TRY EXEC sys.sp_executesql @sql; END TRY BEGIN CATCH SELECT @b + '.' + @t AS Tabla, ERROR_MESSAGE() AS Error; END CATCH;
    FETCH NEXT FROM c2 INTO @b, @e, @t;
END
CLOSE c2; DEALLOCATE c2;

PRINT '=== 3. Campos de ubicación ya registrados en el generador (score.Campo / CampoCartera) ===';
IF OBJECT_ID('CobAuto.score.CampoCartera') IS NOT NULL
    SELECT cc.IdCartera, cc.Campo, cc.Nivel, cc.Tabla, cc.Columna
    FROM CobAuto.score.CampoCartera AS cc
    WHERE cc.Columna LIKE '%PROVINCIA%' OR cc.Columna LIKE '%DEPART%' OR cc.Columna LIKE '%DISTRITO%' OR cc.Columna LIKE '%UBIGEO%'
    ORDER BY cc.IdCartera;
GO
