/* =====================================================================================
   Generador de bases · prueba de los conteos de los filtros (SOLO LECTURA) · 20/11/2026
   Diseño: claude/diseno_generador_estrategias.md (R1/R2)

   Para qué: después de la caché de condiciones del día (fase 12), lo que más pesa en cada clic son
   los conteos de las listas de filtros (conteos_vista: 2 a 5 s en la 126). Esta prueba mide los
   MISMOS conteos (una agrupación por cada campo del catálogo, por teléfono y por cliente) de dos formas:
     1. Como hoy: copia de la cartera en una tabla temporal normal (rowstore).
     2. Con la copia en un índice columnstore (lo que usaría la tabla guardada de R1).
   Así se decide R1/R2 con datos, no con suposiciones.

   Solo usa tablas temporales (#). Corre las carteras 144, 112 y 126; tarda unos segundos por cartera.
   Guardar el resultado en tools/salidas/diagnostico_generador_conteos.txt
   ===================================================================================== */
USE CobAuto;
GO
SET NOCOUNT ON;

DECLARE @Carteras TABLE (Orden INT IDENTITY, IdCartera INT);
INSERT INTO @Carteras (IdCartera) VALUES (144), (112), (126);

IF OBJECT_ID('tempdb..#resultado') IS NOT NULL DROP TABLE #resultado;
CREATE TABLE #resultado (
    IdCartera INT, Telefonos INT, CamposTelefono INT, CamposCliente INT,
    Ms_copia_rowstore INT, Ms_conteo_tel_rowstore INT, Ms_conteo_cli_rowstore INT,
    Ms_crear_columnstore INT, Ms_conteo_tel_columnstore INT, Ms_conteo_cli_columnstore INT);

DECLARE @i INT = 1, @n INT = (SELECT COUNT(*) FROM @Carteras), @c INT;
DECLARE @t0 DATETIME2(3), @copia INT, @telR INT, @cliR INT, @cci INT, @telC INT, @cliC INT;
DECLARE @colsTel NVARCHAR(MAX), @setsTel NVARCHAR(MAX), @colsCli NVARCHAR(MAX), @setsCli NVARCHAR(MAX),
        @nTel INT, @nCli INT, @sql NVARCHAR(MAX), @ejec NVARCHAR(MAX);

WHILE @i <= @n
BEGIN
    SELECT @c = IdCartera FROM @Carteras WHERE Orden = @i;

    IF OBJECT_ID('tempdb..#m') IS NOT NULL DROP TABLE #m;
    IF OBJECT_ID('tempdb..#mc') IS NOT NULL DROP TABLE #mc;
    IF OBJECT_ID('tempdb..#basura') IS NOT NULL DROP TABLE #basura;
    CREATE TABLE #basura (Campo INT, Valor NVARCHAR(200), N INT);

    -- 1. Copia como hoy (rowstore, índice por Descartado y DNI, parecido a IX_gb_a)
    SET @t0 = SYSDATETIME();
    SELECT t.* INTO #m FROM score.vw_BaseTrabajo AS t WHERE t.IdCartera = @c;
    CREATE CLUSTERED INDEX IX_m ON #m (Descartado, DNI);
    SET @copia = DATEDIFF(MILLISECOND, @t0, SYSDATETIME());

    -- Campos del catálogo que son columnas de la vista (los mismos que cuenta la pantalla)
    SELECT @colsTel = NULL, @setsTel = NULL, @colsCli = NULL, @setsCli = NULL;
    ;WITH campos AS (
        SELECT f.ColumnaOrigen, CASE WHEN f.Grupo IN ('SCORE', 'TELEFONO', 'GESTION_TELEFONO') THEN 1 ELSE 0 END AS EsTel,
               ROW_NUMBER() OVER (ORDER BY f.Codigo) AS k
        FROM score.Campo AS f
        WHERE f.Activo = 1 AND f.Origen = 'TRABAJO'
          AND EXISTS (SELECT 1 FROM tempdb.sys.columns AS sc
                      WHERE sc.object_id = OBJECT_ID('tempdb..#m') AND sc.name = f.ColumnaOrigen)
    )
    SELECT @colsTel = STUFF((SELECT N', CONVERT(NVARCHAR(200), [' + ColumnaOrigen + N']) AS v' + CONVERT(NVARCHAR(10), k)
                             FROM campos WHERE EsTel = 1 ORDER BY k FOR XML PATH(''), TYPE).value('.', 'NVARCHAR(MAX)'), 1, 2, N''),
           @setsTel = STUFF((SELECT N', (v' + CONVERT(NVARCHAR(10), k) + N')'
                             FROM campos WHERE EsTel = 1 ORDER BY k FOR XML PATH(''), TYPE).value('.', 'NVARCHAR(MAX)'), 1, 2, N''),
           @colsCli = STUFF((SELECT N', CONVERT(NVARCHAR(200), [' + ColumnaOrigen + N']) AS v' + CONVERT(NVARCHAR(10), k)
                             FROM campos WHERE EsTel = 0 ORDER BY k FOR XML PATH(''), TYPE).value('.', 'NVARCHAR(MAX)'), 1, 2, N''),
           @setsCli = STUFF((SELECT N', (v' + CONVERT(NVARCHAR(10), k) + N')'
                             FROM campos WHERE EsTel = 0 ORDER BY k FOR XML PATH(''), TYPE).value('.', 'NVARCHAR(MAX)'), 1, 2, N''),
           @nTel = (SELECT COUNT(*) FROM campos WHERE EsTel = 1),
           @nCli = (SELECT COUNT(*) FROM campos WHERE EsTel = 0);

    -- 2. Conteos sobre la copia rowstore (por teléfono: COUNT(*); por cliente: una fila por DNI)
    SET @sql = N'INSERT INTO #basura SELECT 0, NULL, COUNT(*) FROM (SELECT ' + @colsTel + N' FROM #TABLA WHERE Descartado = 0) AS x GROUP BY GROUPING SETS (' + @setsTel + N');';
    SET @ejec = REPLACE(@sql, N'#TABLA', N'#m'); SET @t0 = SYSDATETIME(); EXEC (@ejec); SET @telR = DATEDIFF(MILLISECOND, @t0, SYSDATETIME());
    SET @sql = N'INSERT INTO #basura SELECT 0, NULL, COUNT(*) FROM (SELECT DISTINCT DNI, ' + @colsCli + N' FROM #TABLA WHERE Descartado = 0) AS x GROUP BY GROUPING SETS (' + @setsCli + N');';
    SET @ejec = REPLACE(@sql, N'#TABLA', N'#m'); SET @t0 = SYSDATETIME(); EXEC (@ejec); SET @cliR = DATEDIFF(MILLISECOND, @t0, SYSDATETIME());

    -- 3. La misma copia con índice columnstore
    SET @t0 = SYSDATETIME();
    SELECT * INTO #mc FROM #m;
    CREATE CLUSTERED COLUMNSTORE INDEX CCI_mc ON #mc;
    SET @cci = DATEDIFF(MILLISECOND, @t0, SYSDATETIME());

    SET @sql = N'INSERT INTO #basura SELECT 0, NULL, COUNT(*) FROM (SELECT ' + @colsTel + N' FROM #TABLA WHERE Descartado = 0) AS x GROUP BY GROUPING SETS (' + @setsTel + N');';
    SET @ejec = REPLACE(@sql, N'#TABLA', N'#mc'); SET @t0 = SYSDATETIME(); EXEC (@ejec); SET @telC = DATEDIFF(MILLISECOND, @t0, SYSDATETIME());
    SET @sql = N'INSERT INTO #basura SELECT 0, NULL, COUNT(*) FROM (SELECT DISTINCT DNI, ' + @colsCli + N' FROM #TABLA WHERE Descartado = 0) AS x GROUP BY GROUPING SETS (' + @setsCli + N');';
    SET @ejec = REPLACE(@sql, N'#TABLA', N'#mc'); SET @t0 = SYSDATETIME(); EXEC (@ejec); SET @cliC = DATEDIFF(MILLISECOND, @t0, SYSDATETIME());

    INSERT INTO #resultado VALUES (@c, (SELECT COUNT(*) FROM #m), @nTel, @nCli, @copia, @telR, @cliR, @cci, @telC, @cliC);
    SET @i += 1;
END;

SELECT * FROM #resultado ORDER BY Telefonos DESC;

DROP TABLE #m; DROP TABLE #mc; DROP TABLE #basura; DROP TABLE #resultado;
GO
