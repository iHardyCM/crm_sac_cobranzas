/* =====================================================================================
   Generador de bases · prueba 2 de los conteos de los filtros (SOLO LECTURA) · 20/11/2026
   Diseño: claude/diseno_generador_estrategias.md

   Resultado de la prueba 1 (14:02): el columnstore NO acelera los conteos (144: 15,5 s contra
   17,5 s por teléfono, y 12,6 s contra 4,2 s por cliente). La hipótesis es que el costo está
   en GROUPING SETS: SQL Server guarda la lectura y la recorre una vez por cada campo (29 + 23 pasadas).

   Esta prueba compara, sobre la misma copia normal:
     A. GROUPING SETS (como hoy)
     B. Una sola pasada: cada fila se "despliega" en (campo, valor) y se agrupa una vez
        (CROSS APPLY VALUES + GROUP BY)
   Repite la copia de la cartera como referencia de la carga del servidor (en la mañana la 144 copió
   en 2,2 s y en la prueba 1 en 17,2 s: el servidor estaba más cargado).

   Solo usa tablas temporales (#). Guardar el resultado en tools/salidas/diagnostico_generador_conteos_2.txt
   ===================================================================================== */
USE CobAuto;
GO
SET NOCOUNT ON;

DECLARE @Carteras TABLE (Orden INT IDENTITY, IdCartera INT);
INSERT INTO @Carteras (IdCartera) VALUES (144), (112), (126);

IF OBJECT_ID('tempdb..#resultado') IS NOT NULL DROP TABLE #resultado;
CREATE TABLE #resultado (
    IdCartera INT, Telefonos INT, CamposTelefono INT, CamposCliente INT,
    Ms_copia INT,
    Ms_tel_A_grouping_sets INT, Ms_tel_B_una_pasada INT,
    Ms_cli_A_grouping_sets INT, Ms_cli_B_una_pasada INT,
    Filas_A_tel INT, Filas_B_tel INT, Filas_A_cli INT, Filas_B_cli INT);

DECLARE @i INT = 1, @n INT = (SELECT COUNT(*) FROM @Carteras), @c INT;
DECLARE @t0 DATETIME2(3), @copia INT, @telA INT, @telB INT, @cliA INT, @cliB INT,
        @fTA INT, @fTB INT, @fCA INT, @fCB INT;
DECLARE @colsTel NVARCHAR(MAX), @setsTel NVARCHAR(MAX), @valsTel NVARCHAR(MAX),
        @colsCli NVARCHAR(MAX), @setsCli NVARCHAR(MAX), @valsCli NVARCHAR(MAX),
        @nTel INT, @nCli INT, @ejec NVARCHAR(MAX);

WHILE @i <= @n
BEGIN
    SELECT @c = IdCartera FROM @Carteras WHERE Orden = @i;

    IF OBJECT_ID('tempdb..#m') IS NOT NULL DROP TABLE #m;
    IF OBJECT_ID('tempdb..#ra') IS NOT NULL DROP TABLE #ra;
    IF OBJECT_ID('tempdb..#rb') IS NOT NULL DROP TABLE #rb;
    CREATE TABLE #ra (Campo NVARCHAR(10), Valor NVARCHAR(200), N INT);
    CREATE TABLE #rb (Campo NVARCHAR(10), Valor NVARCHAR(200), N INT);

    SET @t0 = SYSDATETIME();
    SELECT t.* INTO #m FROM score.vw_BaseTrabajo AS t WHERE t.IdCartera = @c;
    CREATE CLUSTERED INDEX IX_m ON #m (Descartado, DNI);
    SET @copia = DATEDIFF(MILLISECOND, @t0, SYSDATETIME());

    SELECT @colsTel = NULL, @setsTel = NULL, @valsTel = NULL, @colsCli = NULL, @setsCli = NULL, @valsCli = NULL;
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
           @valsTel = STUFF((SELECT N', (N''' + CONVERT(NVARCHAR(10), k) + N''', CONVERT(NVARCHAR(200), a.[' + ColumnaOrigen + N']))'
                             FROM campos WHERE EsTel = 1 ORDER BY k FOR XML PATH(''), TYPE).value('.', 'NVARCHAR(MAX)'), 1, 2, N''),
           @colsCli = STUFF((SELECT N', CONVERT(NVARCHAR(200), [' + ColumnaOrigen + N']) AS v' + CONVERT(NVARCHAR(10), k)
                             FROM campos WHERE EsTel = 0 ORDER BY k FOR XML PATH(''), TYPE).value('.', 'NVARCHAR(MAX)'), 1, 2, N''),
           @setsCli = STUFF((SELECT N', (v' + CONVERT(NVARCHAR(10), k) + N')'
                             FROM campos WHERE EsTel = 0 ORDER BY k FOR XML PATH(''), TYPE).value('.', 'NVARCHAR(MAX)'), 1, 2, N''),
           @valsCli = STUFF((SELECT N', (N''' + CONVERT(NVARCHAR(10), k) + N''', a.v' + CONVERT(NVARCHAR(10), k) + N')'
                             FROM campos WHERE EsTel = 0 ORDER BY k FOR XML PATH(''), TYPE).value('.', 'NVARCHAR(MAX)'), 1, 2, N''),
           @nTel = (SELECT COUNT(*) FROM campos WHERE EsTel = 1),
           @nCli = (SELECT COUNT(*) FROM campos WHERE EsTel = 0);

    -- Por teléfono · A: GROUPING SETS (como hoy)
    SET @ejec = N'INSERT INTO #ra SELECT NULL, NULL, COUNT(*) FROM (SELECT ' + @colsTel
              + N' FROM #m WHERE Descartado = 0) AS x GROUP BY GROUPING SETS (' + @setsTel + N');';
    SET @t0 = SYSDATETIME(); EXEC (@ejec); SET @telA = DATEDIFF(MILLISECOND, @t0, SYSDATETIME());
    SET @fTA = (SELECT COUNT(*) FROM #ra);

    -- Por teléfono · B: una pasada
    SET @ejec = N'INSERT INTO #rb SELECT u.Campo, u.Valor, COUNT(*) FROM #m AS a CROSS APPLY (VALUES '
              + @valsTel + N') AS u (Campo, Valor) WHERE a.Descartado = 0 GROUP BY u.Campo, u.Valor;';
    SET @t0 = SYSDATETIME(); EXEC (@ejec); SET @telB = DATEDIFF(MILLISECOND, @t0, SYSDATETIME());
    SET @fTB = (SELECT COUNT(*) FROM #rb);

    TRUNCATE TABLE #ra; TRUNCATE TABLE #rb;

    -- Por cliente · A: GROUPING SETS sobre una fila por DNI (como hoy)
    SET @ejec = N'INSERT INTO #ra SELECT NULL, NULL, COUNT(*) FROM (SELECT DISTINCT DNI, ' + @colsCli
              + N' FROM #m WHERE Descartado = 0) AS x GROUP BY GROUPING SETS (' + @setsCli + N');';
    SET @t0 = SYSDATETIME(); EXEC (@ejec); SET @cliA = DATEDIFF(MILLISECOND, @t0, SYSDATETIME());
    SET @fCA = (SELECT COUNT(*) FROM #ra);

    -- Por cliente · B: una fila por DNI y una pasada
    SET @ejec = N'INSERT INTO #rb SELECT u.Campo, u.Valor, COUNT(*) FROM (SELECT DISTINCT DNI, ' + @colsCli
              + N' FROM #m WHERE Descartado = 0) AS a CROSS APPLY (VALUES ' + @valsCli
              + N') AS u (Campo, Valor) GROUP BY u.Campo, u.Valor;';
    SET @t0 = SYSDATETIME(); EXEC (@ejec); SET @cliB = DATEDIFF(MILLISECOND, @t0, SYSDATETIME());
    SET @fCB = (SELECT COUNT(*) FROM #rb);

    INSERT INTO #resultado VALUES (@c, (SELECT COUNT(*) FROM #m), @nTel, @nCli, @copia,
                                   @telA, @telB, @cliA, @cliB, @fTA, @fTB, @fCA, @fCB);
    SET @i += 1;
END;

-- Filas_A y Filas_B deben ser iguales por cartera: es la verificación de que ambas formas cuentan lo mismo.
SELECT * FROM #resultado ORDER BY Telefonos DESC;

DROP TABLE #m; DROP TABLE #ra; DROP TABLE #rb; DROP TABLE #resultado;
GO
