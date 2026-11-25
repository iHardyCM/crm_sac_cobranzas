/* =====================================================================================
   DIAGNÓSTICO 2 — MATRICES DE TELÉFONOS POR CARTERA (solo lectura)
   Fecha: 14/11/2026

   Para qué: el score que usa la operación sale de las tablas TBL_FONOS_<cartera>, que arman los
   SP_MATRIZ_FONOS_* del job "Jb Maestro Biznescob". Necesito ver:
     1. cuándo se refrescó por última vez la tabla del CRM;
     2. qué jobs refrescan cada cartera (Vigente y MiBanco no aparecieron en el diagnóstico 1);
     3. las tablas, vistas y SP de teléfonos de cada base, con filas y fecha;
     4. la definición completa de los SP_MATRIZ_FONOS_* y de las vistas de teléfonos
        (partida en trozos de 4.000 caracteres, para que SSMS no la corte);
     5. las columnas de cada TBL_FONOS_*.

   No modifica nada. Guarda TODA la salida (también los errores) y pásamela.
   Para el bloque 4: Resultados en texto (Ctrl+T) y en Herramientas → Opciones → Resultados de
   consulta → Texto, "Número máximo de caracteres" = 8192.
   ===================================================================================== */

USE CobAuto;
GO
SET NOCOUNT ON;
SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED;
GO

/* 1. Último refresco de la tabla del CRM: el SP la recrea con SELECT INTO, así que su
      fecha de creación es la fecha del último refresco. */
SELECT name AS tabla, create_date AS ultimo_refresco, modify_date
FROM CobAuto.sys.tables
WHERE name = 'TBL_SCORE_TELEFONICO_CRM';
GO

/* 2. Todos los jobs y pasos que tocan teléfonos, dashboards o score (y su horario) */
SELECT j.name AS job, j.enabled, s.step_id, s.step_name, s.database_name,
       LEFT(REPLACE(REPLACE(s.command, CHAR(13), ' '), CHAR(10), ' '), 600) AS comando
FROM msdb.dbo.sysjobs j
JOIN msdb.dbo.sysjobsteps s ON s.job_id = j.job_id
WHERE s.command LIKE '%FONO%' OR s.command LIKE '%DASH%' OR s.command LIKE '%SCORE%'
   OR s.command LIKE '%GESTIONES_DIARIAS%'
ORDER BY j.name, s.step_id;

SELECT j.name AS job, sc.name AS horario, sc.enabled,
       sc.freq_type, sc.freq_interval, sc.freq_subday_type, sc.freq_subday_interval,
       sc.active_start_time AS hora_inicio_hhmmss
FROM msdb.dbo.sysjobs j
JOIN msdb.dbo.sysjobschedules js ON js.job_id = j.job_id
JOIN msdb.dbo.sysschedules sc ON sc.schedule_id = js.schedule_id
WHERE j.name IN (SELECT DISTINCT j2.name FROM msdb.dbo.sysjobs j2
                 JOIN msdb.dbo.sysjobsteps s2 ON s2.job_id = j2.job_id
                 WHERE s2.command LIKE '%FONO%' OR s2.command LIKE '%DASH%');
GO

/* 3, 4 y 5. Se recorre cada base de cartera */
DECLARE @bases TABLE (orden INT IDENTITY, base SYSNAME);
INSERT INTO @bases (base) VALUES
    ('Compartamos_Vigente_Cobranzas'), ('Compartamos_Castigo_Cobranzas'),
    ('Financiera_OH_Cobranzas'), ('Interbank_Cobranzas'), ('Interbank_Propia_Cobranzas'),
    ('PROPIA_COBRANZAS'), ('MiBanco_Cobranzas');

DECLARE @i INT = 1, @n INT = (SELECT COUNT(*) FROM @bases), @base SYSNAME, @sql NVARCHAR(MAX);

WHILE @i <= @n
BEGIN
    SELECT @base = base FROM @bases WHERE orden = @i;

    SET @sql = N'USE ' + QUOTENAME(@base) + N';

    /* 3. Objetos de teléfonos de la base */
    SELECT DB_NAME() AS base, o.name AS objeto, o.type_desc AS tipo, o.create_date, o.modify_date,
           (SELECT SUM(p.rows) FROM sys.partitions p
            WHERE p.object_id = o.object_id AND p.index_id IN (0, 1)) AS filas
    FROM sys.objects o
    WHERE o.type IN (''U'', ''V'', ''P'')
      AND (o.name LIKE ''%FONO%'' OR o.name LIKE ''%TELEF%'' OR o.name LIKE ''%SCORE_PROPIA%'')
    ORDER BY o.type_desc, o.name;

    /* 4. Definición completa de SP de matriz y vistas de teléfonos, en trozos */
    ;WITH N AS (SELECT TOP (200) ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) - 1 AS i FROM sys.all_objects)
    SELECT DB_NAME() AS base, o.name AS objeto, N.i + 1 AS parte,
           SUBSTRING(m.definition, N.i * 4000 + 1, 4000) AS definicion
    FROM sys.objects o
    JOIN sys.sql_modules m ON m.object_id = o.object_id
    JOIN N ON N.i * 4000 < LEN(m.definition)
    WHERE o.name LIKE ''SP_MATRIZ_FONOS%''
       OR (o.type = ''V'' AND (o.name LIKE ''%FONOS%'' OR o.name LIKE ''VW_SCORE_PROPIA%''))
    ORDER BY o.name, N.i;

    /* 5. Columnas de cada TBL_FONOS_* */
    SELECT DB_NAME() AS base, t.name AS tabla,
           STUFF((SELECT '','' + c.name FROM sys.columns c
                  WHERE c.object_id = t.object_id ORDER BY c.column_id
                  FOR XML PATH(''''), TYPE).value(''.'', ''nvarchar(max)''), 1, 1, '''') AS columnas
    FROM sys.tables t
    WHERE t.name LIKE ''TBL_FONOS%''
    ORDER BY t.name;';

    BEGIN TRY
        EXEC sys.sp_executesql @sql;
    END TRY
    BEGIN CATCH
        SELECT @base AS base, ERROR_NUMBER() AS error, ERROR_MESSAGE() AS mensaje;
    END CATCH;

    SET @i += 1;
END;
GO
