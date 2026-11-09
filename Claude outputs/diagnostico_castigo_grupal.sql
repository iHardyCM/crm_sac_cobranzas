/* =====================================================================
   Castigo Grupal — datos para corregir su configuración de cierre
   SOLO LECTURA sobre las tablas del negocio (usa una tabla temporal #).
   Ejecutar TODO el script en SSMS. Devuelve 4 resultados: A, B, C y D.
   Pásame los 4 tal como salen.
   ===================================================================== */


/* ---------- A. Configuración actual de TODAS las carteras ----------
   Para ver cómo quedó la fila de Castigo Grupal y confirmar que el
   cambio del programa no afecta a las demás. */
SELECT
    'A' AS resultado,
    id_config, cartera, producto,
    tabla_destino, tabla_historica,
    campo_periodo_actual, campo_periodo_historico,
    tipo_periodo, formato_periodo,
    tipo_estructura_historico, activo
FROM CobAuto.dbo.importacion_config_cartera WITH (NOLOCK)
ORDER BY cartera, producto;


/* ---------- B. Columnas del histórico de Castigo Grupal ----------
   existe_en_origen = NO  ->  el cierre no las copia del origen.
   Entre ellas debería estar la columna del periodo (mes). */
SELECT
    'B' AS resultado,
    h.column_id,
    h.name AS columna_historico,
    t.name AS tipo,
    CASE WHEN o.name IS NULL THEN 'NO' ELSE 'SI' END AS existe_en_origen
FROM Compartamos_Castigo_Cobranzas.sys.columns h
JOIN Compartamos_Castigo_Cobranzas.sys.types t ON t.user_type_id = h.user_type_id
LEFT JOIN Desarrollo.sys.columns o
       ON o.object_id = OBJECT_ID('Desarrollo.dbo.compartamos_grupal_castigo')
      AND o.name COLLATE Latin1_General_CI_AI = h.name COLLATE Latin1_General_CI_AI
WHERE h.object_id = OBJECT_ID('Compartamos_Castigo_Cobranzas.dbo.HIST_GRUPAL_CASTIGO')
ORDER BY existe_en_origen, h.column_id;


/* ---------- C. Valores de las columnas del histórico que NO vienen del origen ----------
   Muestra los 5 valores más frecuentes de cada una, para reconocer el
   periodo y su formato (fecha 2026-10-01, texto 202610, etc.). */
IF OBJECT_ID('tempdb..#valores') IS NOT NULL DROP TABLE #valores;
CREATE TABLE #valores (columna SYSNAME, valor NVARCHAR(200), filas INT);

DECLARE @columnas TABLE (id INT IDENTITY(1,1), nombre SYSNAME);
INSERT INTO @columnas (nombre)
SELECT h.name
FROM Compartamos_Castigo_Cobranzas.sys.columns h
WHERE h.object_id = OBJECT_ID('Compartamos_Castigo_Cobranzas.dbo.HIST_GRUPAL_CASTIGO')
  AND NOT EXISTS (
        SELECT 1
        FROM Desarrollo.sys.columns o
        WHERE o.object_id = OBJECT_ID('Desarrollo.dbo.compartamos_grupal_castigo')
          AND o.name COLLATE Latin1_General_CI_AI = h.name COLLATE Latin1_General_CI_AI
  );

DECLARE @i INT = 1, @n INT = (SELECT COUNT(*) FROM @columnas), @col SYSNAME, @sql NVARCHAR(MAX);
WHILE @i <= @n
BEGIN
    SELECT @col = nombre FROM @columnas WHERE id = @i;
    SET @sql = N'INSERT INTO #valores (columna, valor, filas)
                 SELECT TOP 5 ' + QUOTENAME(@col, '''') + N', CONVERT(NVARCHAR(200), ' + QUOTENAME(@col) + N'), COUNT(*)
                 FROM Compartamos_Castigo_Cobranzas.dbo.HIST_GRUPAL_CASTIGO WITH (NOLOCK)
                 GROUP BY ' + QUOTENAME(@col) + N'
                 ORDER BY COUNT(*) DESC;';
    EXEC sp_executesql @sql;
    SET @i += 1;
END

SELECT 'C' AS resultado, columna, valor, filas
FROM #valores
ORDER BY columna, filas DESC;

DROP TABLE #valores;


/* ---------- D. Cierres ya registrados de Compartamos grupal (vigente y castigo) ---------- */
SELECT TOP 30
    'D' AS resultado,
    id_cierre, id_config, producto, periodo,
    tabla_origen, tabla_historica, total_origen, estado, usuario, fecha_inicio
FROM CobAuto.dbo.importacion_cierres_historicos WITH (NOLOCK)
WHERE tabla_origen LIKE '%grupal%'
ORDER BY id_cierre DESC;
