/* =====================================================================================
   SCORE TELEFÓNICO · DIAGNÓSTICO 11 — FUENTES DEL CLIENTE PARA LA TABLA DE TRABAJO
   Fecha: 14/11/2026 · Solo lectura (metadatos y conteos).

   Para qué: score.BaseTrabajo debe traer los datos del cliente del corte vigente de Analytics por cartera
   (capital y rango, mora o maduración, prioridad banco, PDP, gestión, etc.), con las reglas ya aprobadas
   allá, sin recalcularlas. Antes de escribir el armado necesito las columnas reales de cada fuente.

   Fuentes, tomadas del código de Analytics (backend/app/modules):
     112 MiBanco castigo        MiBanco_Cobranzas.dbo.VW_MB_CASTIGO_CLIENTE_CORTE
     117 Interbank              Interbank_Cobranzas.dbo.TBL_IBK_CLIENTE_HISTORICO (+ TBL_IBK_DIMENSION_CLIENTE_HISTORICO)
     124 Compartamos castigo ind Compartamos_Castigo_Cobranzas.dbo.CASTIGO_IND_CLIENTE_BI_HISTORICO
     126/128 Vigente IND/CCM    Compartamos_Vigente_Cobranzas.dbo.VW_COMPARTAMOS_VIGENTE_CLIENTE_BI_ANALITICO
     132 SIP                    Financiera_OH_Cobranzas.dbo.TBL_SIP_CLIENTE_BI_HISTORICO (+ PRIORIDAD y MEJOR_GESTION)
     133 Vigente grupal         Compartamos_Vigente_Cobranzas.dbo.VW_COMPARTAMOS_GRUPAL_INTEGRANTE_BI_ACTUAL
     137 Propia Interbank       Interbank_Propia_Cobranzas.dbo.VW_PROPIA_CLIENTE_CORTE
     144 Compartamos castigo grupal Compartamos_Castigo_Cobranzas.dbo.VW_CASTIGO_GRUPAL_CLIENTE_CORTE
     148 Propia SIP             PROPIA_COBRANZAS.dbo.VW_PROPIA_CLIENTE_CORTE
   Y siscob.dbo.Cliente, común a todas.

   Ejecutar en el servidor donde corre el score (WIN-93CJSDHI892). Si una base no está en este servidor,
   sale como "NO EXISTE O SIN ACCESO" y lo resolvemos aparte.
   Guardar la salida en tools/salidas/resultados_diagnostico_score_11.txt
   ===================================================================================== */

USE CobAuto;
SET NOCOUNT ON;

IF OBJECT_ID('tempdb..#fuente') IS NOT NULL DROP TABLE #fuente;
CREATE TABLE #fuente (
    Orden INT IDENTITY(1, 1) PRIMARY KEY,
    Carteras VARCHAR(20), Base SYSNAME, Objeto SYSNAME);

INSERT INTO #fuente (Carteras, Base, Objeto) VALUES
('112',     'MiBanco_Cobranzas',             'VW_MB_CASTIGO_CLIENTE_CORTE'),
('117',     'Interbank_Cobranzas',           'TBL_IBK_CLIENTE_HISTORICO'),
('117',     'Interbank_Cobranzas',           'TBL_IBK_DIMENSION_CLIENTE_HISTORICO'),
('124',     'Compartamos_Castigo_Cobranzas', 'CASTIGO_IND_CLIENTE_BI_HISTORICO'),
('126,128', 'Compartamos_Vigente_Cobranzas', 'VW_COMPARTAMOS_VIGENTE_CLIENTE_BI_ANALITICO'),
('132',     'Financiera_OH_Cobranzas',       'TBL_SIP_CLIENTE_BI_HISTORICO'),
('132',     'Financiera_OH_Cobranzas',       'TBL_SIP_PRIORIDAD_HISTORICO'),
('132',     'Financiera_OH_Cobranzas',       'TBL_SIP_MEJOR_GESTION_HISTORICO'),
('133',     'Compartamos_Vigente_Cobranzas', 'VW_COMPARTAMOS_GRUPAL_INTEGRANTE_BI_ACTUAL'),
('137',     'Interbank_Propia_Cobranzas',    'VW_PROPIA_CLIENTE_CORTE'),
('144',     'Compartamos_Castigo_Cobranzas', 'VW_CASTIGO_GRUPAL_CLIENTE_CORTE'),
('148',     'PROPIA_COBRANZAS',              'VW_PROPIA_CLIENTE_CORTE'),
('todas',   'siscob',                        'Cliente');

IF OBJECT_ID('tempdb..#col') IS NOT NULL DROP TABLE #col;
CREATE TABLE #col (Orden INT, Columna SYSNAME, Tipo SYSNAME, Largo INT, Posicion INT);

IF OBJECT_ID('tempdb..#resumen') IS NOT NULL DROP TABLE #resumen;
CREATE TABLE #resumen (Orden INT PRIMARY KEY, Estado VARCHAR(60), Columnas INT,
                       UltimoCorte DATE NULL, FilasUltimoCorte INT NULL, DniUltimoCorte INT NULL,
                       Cortes INT NULL, Error NVARCHAR(400) NULL);

DECLARE @o INT, @b SYSNAME, @obj SYSNAME, @sql NVARCHAR(MAX), @n INT, @colFecha SYSNAME, @colDni SYSNAME;

DECLARE c CURSOR LOCAL FAST_FORWARD FOR SELECT Orden, Base, Objeto FROM #fuente ORDER BY Orden;
OPEN c;
FETCH NEXT FROM c INTO @o, @b, @obj;
WHILE @@FETCH_STATUS = 0
BEGIN
    BEGIN TRY
        IF DB_ID(@b) IS NULL OR HAS_DBACCESS(@b) = 0
        BEGIN
            INSERT INTO #resumen (Orden, Estado, Columnas) VALUES (@o, 'NO EXISTE O SIN ACCESO (BASE)', 0);
        END
        ELSE
        BEGIN
            -- Columnas
            SET @sql = N'INSERT INTO #col (Orden, Columna, Tipo, Largo, Posicion)
                SELECT @o, c.name, t.name, c.max_length, c.column_id
                FROM ' + QUOTENAME(@b) + N'.sys.columns AS c
                INNER JOIN ' + QUOTENAME(@b) + N'.sys.objects AS ob ON ob.object_id = c.object_id
                INNER JOIN ' + QUOTENAME(@b) + N'.sys.schemas AS s ON s.schema_id = ob.schema_id
                INNER JOIN ' + QUOTENAME(@b) + N'.sys.types AS t ON t.user_type_id = c.user_type_id
                WHERE s.name = ''dbo'' AND ob.name = @obj;';
            EXEC sys.sp_executesql @sql, N'@o INT, @obj SYSNAME', @o, @obj;
            SET @n = (SELECT COUNT(*) FROM #col WHERE Orden = @o);

            IF @n = 0
                INSERT INTO #resumen (Orden, Estado, Columnas) VALUES (@o, 'NO EXISTE O SIN ACCESO (OBJETO)', 0);
            ELSE
            BEGIN
                SET @colFecha = (SELECT TOP 1 Columna FROM #col WHERE Orden = @o
                                 AND Columna IN ('FECHA_CORTE', 'FECHACORTE', 'FECHA_CIERRE', 'FECHA') ORDER BY
                                 CASE Columna WHEN 'FECHA_CORTE' THEN 1 WHEN 'FECHACORTE' THEN 2 WHEN 'FECHA_CIERRE' THEN 3 ELSE 4 END);
                SET @colDni = (SELECT TOP 1 Columna FROM #col WHERE Orden = @o
                               AND Columna IN ('DNI', 'NRO_DOC', 'DOCUMENTO', 'Dni') ORDER BY
                               CASE Columna WHEN 'DNI' THEN 1 WHEN 'Dni' THEN 2 WHEN 'NRO_DOC' THEN 3 ELSE 4 END);

                IF @colFecha IS NOT NULL
                BEGIN
                    SET @sql = N'
                        DECLARE @u DATE = (SELECT MAX(CAST(' + QUOTENAME(@colFecha) + N' AS DATE)) FROM ' + QUOTENAME(@b) + N'.dbo.' + QUOTENAME(@obj) + N' WITH (NOLOCK));
                        INSERT INTO #resumen (Orden, Estado, Columnas, UltimoCorte, FilasUltimoCorte, DniUltimoCorte, Cortes)
                        SELECT @o, ''OK (fecha: ' + @colFecha + N')'', @n, @u, COUNT(*), '
                        + CASE WHEN @colDni IS NULL THEN N'NULL' ELSE N'COUNT(DISTINCT ' + QUOTENAME(@colDni) + N')' END + N',
                               (SELECT COUNT(DISTINCT CAST(' + QUOTENAME(@colFecha) + N' AS DATE)) FROM ' + QUOTENAME(@b) + N'.dbo.' + QUOTENAME(@obj) + N' WITH (NOLOCK))
                        FROM ' + QUOTENAME(@b) + N'.dbo.' + QUOTENAME(@obj) + N' WITH (NOLOCK)
                        WHERE CAST(' + QUOTENAME(@colFecha) + N' AS DATE) = @u;';
                    EXEC sys.sp_executesql @sql, N'@o INT, @n INT', @o, @n;
                END
                ELSE
                BEGIN
                    SET @sql = N'
                        INSERT INTO #resumen (Orden, Estado, Columnas, FilasUltimoCorte, DniUltimoCorte)
                        SELECT @o, ''OK (sin columna de fecha de corte)'', @n, COUNT(*), '
                        + CASE WHEN @colDni IS NULL THEN N'NULL' ELSE N'COUNT(DISTINCT ' + QUOTENAME(@colDni) + N')' END + N'
                        FROM ' + QUOTENAME(@b) + N'.dbo.' + QUOTENAME(@obj) + N' WITH (NOLOCK);';
                    EXEC sys.sp_executesql @sql, N'@o INT, @n INT', @o, @n;
                END;
            END;
        END;
    END TRY
    BEGIN CATCH
        IF NOT EXISTS (SELECT 1 FROM #resumen WHERE Orden = @o)
            INSERT INTO #resumen (Orden, Estado, Columnas, Error) VALUES (@o, 'ERROR', NULL, LEFT(ERROR_MESSAGE(), 400));
        ELSE
            UPDATE #resumen SET Error = LEFT(ERROR_MESSAGE(), 400) WHERE Orden = @o;
    END CATCH;
    FETCH NEXT FROM c INTO @o, @b, @obj;
END;
CLOSE c; DEALLOCATE c;

/* 1. Resumen por fuente */
SELECT f.Orden, f.Carteras, f.Base, f.Objeto, r.Estado, r.Columnas, r.UltimoCorte, r.Cortes,
       r.FilasUltimoCorte, r.DniUltimoCorte, r.Error
FROM #fuente AS f
LEFT JOIN #resumen AS r ON r.Orden = f.Orden
ORDER BY f.Orden;

/* 2. Columnas de cada fuente, en una sola fila por fuente (más fácil de leer en el .txt) */
SELECT f.Orden, f.Carteras, f.Objeto,
       STUFF((SELECT ', ' + c.Columna + ' ' + c.Tipo
              FROM #col AS c WHERE c.Orden = f.Orden ORDER BY c.Posicion
              FOR XML PATH(''), TYPE).value('.', 'NVARCHAR(MAX)'), 1, 2, '') AS columnas
FROM #fuente AS f
ORDER BY f.Orden;

/* 3. Cortes publicados por cartera en CobAuto (si existe la tabla común de cortes) */
IF OBJECT_ID('CobAuto.dbo.CORTE_PUBLICADO') IS NOT NULL
    EXEC ('SELECT TOP 40 * FROM CobAuto.dbo.CORTE_PUBLICADO ORDER BY 1 DESC');
GO
