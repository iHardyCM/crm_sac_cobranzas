/* =====================================================================================
   validar_estado_cuenta_individual.sql
   Paso 0 del "Estado de cuenta individual" (Radar Compartamos).

   SOLO LECTURA: no crea objetos permanentes ni modifica datos (solo tablas #temporales).
   Ejecutar en la base donde vive VW_CLIENTE_CRM_SAC (la que usa el CRM en get_connection).
   Las tablas de Desarrollo se leen con nombre de tres partes.

   Para qué sirve: confirmar con datos reales, ANTES de que Codex construya, que la
   carga SAC alcanza para un estado de cuenta individual. Cada bloque responde una
   pregunta de la especificación (docs/estado_cuenta_individual_compartamos.md, sección 9).

   Los nombres de columna de SAC traen espacios finales y tildes ([CodigoGrupo ],
   [Cod Operación]); por eso el script los busca en INFORMATION_SCHEMA en lugar de
   escribirlos a mano. Si una columna no existe, su valor queda NULL y se informa.

   Costo: por defecto trabaja con una muestra aleatoria de @max_ops operaciones.
   Pon @max_ops = NULL para revisar toda la cartera individual (puede tardar).
   ===================================================================================== */
SET NOCOUNT ON;
SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED;   -- equivale a WITH(NOLOCK) en todo el script

DECLARE @max_ops int = 2000;

/* -------------------------------------------------------------------------------------
   BLOQUE 1. Columnas reales de las tres fuentes.
   Pregunta: ¿qué columnas trae compartamos_individual (campañas, frecuencia, cuotas
   pagadas)? ¿SAC trae fecha de proceso o frecuencia de pago?
   ------------------------------------------------------------------------------------- */
SELECT TABLE_NAME, ORDINAL_POSITION, '[' + COLUMN_NAME + ']' AS columna, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH
FROM Desarrollo.INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = 'dbo'
  AND TABLE_NAME IN ('SAC_CAR_BIZNESCOB', 'compartamos_individual', 'compartamos_ccm')
ORDER BY TABLE_NAME, ORDINAL_POSITION;

/* -------------------------------------------------------------------------------------
   Mapa de columnas: alias limpio -> nombre real.
   Se compara sin espacios, sin guiones bajos, sin mayúsculas y sin tildes.
   tipo: key (código), num (monto), int (entero), date (fecha; acepta AAAAMMDD numérico).
   ------------------------------------------------------------------------------------- */
IF OBJECT_ID('tempdb..#col') IS NOT NULL DROP TABLE #col;
CREATE TABLE #col (
    fuente    varchar(20)   NOT NULL,   -- SAC | VW | IND
    orden     int           NOT NULL,
    alias     sysname       NOT NULL,
    tipo      varchar(5)    NOT NULL,
    real_name sysname       NULL,
    data_type sysname       NULL,
    expr      nvarchar(400) NULL
);

INSERT INTO #col (fuente, orden, alias, tipo) VALUES
 ('SAC', 1, 'CodOperacion', 'key'), ('SAC', 2, 'DNI', 'key'), ('SAC', 3, 'CodigoGrupo', 'key'),
 ('SAC', 4, 'UltCuotaAtrasada', 'int'), ('SAC', 5, 'UltFecVen', 'date'), ('SAC', 6, 'DiasAtraso', 'int'),
 ('SAC', 7, 'CT1', 'num'), ('SAC', 8, 'CT2', 'num'), ('SAC', 9, 'CT3', 'num'),
 ('SAC', 10, 'CT11', 'num'), ('SAC', 11, 'CT12', 'num'), ('SAC', 12, 'CT13', 'num'), ('SAC', 13, 'CT14', 'num'), ('SAC', 14, 'CT15', 'num'),
 ('SAC', 15, 'CT21', 'num'), ('SAC', 16, 'CT22', 'num'), ('SAC', 17, 'CT23', 'num'), ('SAC', 18, 'CT24', 'num'), ('SAC', 19, 'CT25', 'num'),
 ('SAC', 20, 'CT31', 'num'), ('SAC', 21, 'CT32', 'num'), ('SAC', 22, 'CT33', 'num'), ('SAC', 23, 'CT34', 'num'), ('SAC', 24, 'CT35', 'num'),
 ('VW', 1, 'CodOperacion', 'key'), ('VW', 2, 'DNI', 'key'), ('VW', 3, 'Producto', 'key'),
 ('VW', 4, 'NroCuotasAprobadas', 'int'), ('VW', 5, 'NroCuotasAtrasadas', 'int'), ('VW', 6, 'NroCuotasVencidas', 'int'),
 ('VW', 7, 'UltCuotaAtrasada', 'int'), ('VW', 8, 'DiasAtraso', 'int'), ('VW', 9, 'MtoCuota', 'num'),
 ('VW', 10, 'SdoCapital', 'num'), ('VW', 11, 'SdoCapitalVencido', 'num'), ('VW', 12, 'DeudaTotal', 'num'),
 ('VW', 13, 'FecDesemb', 'date'), ('VW', 14, 'FecUltPago', 'date');

-- Nombres reales en Desarrollo (SAC) y en la base actual (VW)
UPDATE c SET real_name = i.COLUMN_NAME, data_type = i.DATA_TYPE
FROM #col c
JOIN Desarrollo.INFORMATION_SCHEMA.COLUMNS i
  ON i.TABLE_SCHEMA = 'dbo' AND i.TABLE_NAME = 'SAC_CAR_BIZNESCOB'
 AND REPLACE(REPLACE(i.COLUMN_NAME, ' ', ''), '_', '') COLLATE Latin1_General_CI_AI = c.alias COLLATE Latin1_General_CI_AI
WHERE c.fuente = 'SAC';

UPDATE c SET real_name = i.COLUMN_NAME, data_type = i.DATA_TYPE
FROM #col c
JOIN INFORMATION_SCHEMA.COLUMNS i
  ON i.TABLE_NAME = 'VW_CLIENTE_CRM_SAC'
 AND REPLACE(REPLACE(i.COLUMN_NAME, ' ', ''), '_', '') COLLATE Latin1_General_CI_AI = c.alias COLLATE Latin1_General_CI_AI
WHERE c.fuente = 'VW';

-- Columnas de compartamos_individual (mismos candidatos que usa el CRM en FUENTES_ASIGNACION)
DECLARE @ind_op sysname, @ind_op_tipo sysname, @ind_doc sysname, @ind_doc_tipo sysname;
SELECT TOP (1) @ind_op = COLUMN_NAME, @ind_op_tipo = DATA_TYPE
FROM Desarrollo.INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = 'dbo' AND TABLE_NAME = 'compartamos_individual'
  AND REPLACE(REPLACE(COLUMN_NAME, ' ', ''), '_', '') COLLATE Latin1_General_CI_AI IN ('Operacion', 'CodOperacion')
ORDER BY CASE WHEN REPLACE(COLUMN_NAME, ' ', '') COLLATE Latin1_General_CI_AI = 'Operacion' THEN 0 ELSE 1 END;
SELECT TOP (1) @ind_doc = COLUMN_NAME, @ind_doc_tipo = DATA_TYPE
FROM Desarrollo.INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = 'dbo' AND TABLE_NAME = 'compartamos_individual'
  AND REPLACE(REPLACE(COLUMN_NAME, ' ', ''), '_', '') COLLATE Latin1_General_CI_AI IN ('NumDoc', 'DNI', 'NumDocumento')
ORDER BY CASE REPLACE(COLUMN_NAME, ' ', '') COLLATE Latin1_General_CI_AI WHEN 'NumDoc' THEN 0 WHEN 'DNI' THEN 1 ELSE 2 END;

INSERT INTO #col (fuente, orden, alias, tipo, real_name, data_type) VALUES
 ('IND', 1, 'CodOperacion', 'key', @ind_op, @ind_op_tipo),
 ('IND', 2, 'DNI', 'key', @ind_doc, @ind_doc_tipo);

-- Expresión de conversión según el tipo real de cada columna
UPDATE #col SET expr =
    CASE
        WHEN real_name IS NULL THEN N'NULL'
        WHEN tipo = 'key' AND data_type IN ('float', 'real', 'decimal', 'numeric', 'money')
            THEN N'CONVERT(varchar(100), CONVERT(decimal(38,0), ' + QUOTENAME(real_name) + N'))'
        WHEN tipo = 'key' THEN N'LTRIM(RTRIM(CONVERT(varchar(100), ' + QUOTENAME(real_name) + N')))'
        WHEN tipo = 'num' AND data_type IN ('date', 'datetime', 'datetime2', 'smalldatetime') THEN N'NULL'
        WHEN tipo = 'num' THEN N'TRY_CONVERT(float, ' + QUOTENAME(real_name) + N')'
        WHEN tipo = 'int' AND data_type IN ('date', 'datetime', 'datetime2', 'smalldatetime') THEN N'NULL'
        WHEN tipo = 'int' THEN N'TRY_CONVERT(int, TRY_CONVERT(float, ' + QUOTENAME(real_name) + N'))'
        WHEN tipo = 'date' AND data_type IN ('date', 'datetime', 'datetime2', 'smalldatetime')
            THEN N'CONVERT(date, ' + QUOTENAME(real_name) + N')'
        WHEN tipo = 'date' AND data_type IN ('float', 'real', 'decimal', 'numeric', 'int', 'bigint')
            THEN N'TRY_CONVERT(date, CONVERT(varchar(8), TRY_CONVERT(int, ' + QUOTENAME(real_name) + N')), 112)'
        WHEN tipo = 'date'
            THEN N'COALESCE(TRY_CONVERT(date, ' + QUOTENAME(real_name) + N', 112), TRY_CONVERT(date, ' + QUOTENAME(real_name) + N', 103), TRY_CONVERT(date, ' + QUOTENAME(real_name) + N'))'
    END;

-- Columnas que no se encontraron (si aparece CodOperacion o UltFecVen aquí, detenerse y revisar)
SELECT fuente, alias AS columna_esperada, 'NO ENCONTRADA' AS estado
FROM #col WHERE real_name IS NULL
ORDER BY fuente, orden;

/* -------------------------------------------------------------------------------------
   Universo: operaciones de compartamos_individual (muestra de @max_ops o todas)
   ------------------------------------------------------------------------------------- */
IF OBJECT_ID('tempdb..#ind') IS NOT NULL DROP TABLE #ind;
CREATE TABLE #ind (operacion varchar(100) NOT NULL, dni varchar(100) NULL);

DECLARE @sql nvarchar(max), @e_op nvarchar(400), @e_doc nvarchar(400);
SELECT @e_op = expr FROM #col WHERE fuente = 'IND' AND alias = 'CodOperacion';
SELECT @e_doc = expr FROM #col WHERE fuente = 'IND' AND alias = 'DNI';

IF @ind_op IS NULL
    RAISERROR('compartamos_individual no tiene columna de operación (Operacion / CodOperacion). Revisar bloque 1.', 16, 1);
ELSE
BEGIN
    SET @sql = N'
        SELECT ' + CASE WHEN @max_ops IS NULL THEN N'' ELSE N'TOP (' + CONVERT(nvarchar(10), @max_ops) + N') ' END + N'
               operacion, MAX(dni)
        FROM (SELECT ' + @e_op + N' AS operacion, ' + @e_doc + N' AS dni
              FROM Desarrollo.dbo.compartamos_individual) x
        WHERE operacion IS NOT NULL AND operacion <> ''''
        GROUP BY operacion
        ORDER BY ' + CASE WHEN @max_ops IS NULL THEN N'operacion' ELSE N'NEWID()' END + N';';
    INSERT INTO #ind (operacion, dni) EXEC sp_executesql @sql;
END;

CREATE CLUSTERED INDEX IX_ind ON #ind (operacion);

/* -------------------------------------------------------------------------------------
   Filas de SAC y de la vista para esas operaciones
   ------------------------------------------------------------------------------------- */
IF OBJECT_ID('tempdb..#sac') IS NOT NULL DROP TABLE #sac;
CREATE TABLE #sac (
    CodOperacion varchar(100), DNI varchar(100), CodigoGrupo varchar(100),
    UltCuotaAtrasada int, UltFecVen date, DiasAtraso int,
    CT1 float, CT2 float, CT3 float,
    CT11 float, CT12 float, CT13 float, CT14 float, CT15 float,
    CT21 float, CT22 float, CT23 float, CT24 float, CT25 float,
    CT31 float, CT32 float, CT33 float, CT34 float, CT35 float
);

DECLARE @lista nvarchar(max), @e_key nvarchar(400);
SELECT @lista = STUFF((SELECT N', ' + expr FROM #col WHERE fuente = 'SAC' ORDER BY orden
                       FOR XML PATH(''), TYPE).value('.', 'nvarchar(max)'), 1, 2, N'');
SELECT @e_key = expr FROM #col WHERE fuente = 'SAC' AND alias = 'CodOperacion';
SET @sql = N'SELECT ' + @lista + N' FROM Desarrollo.dbo.SAC_CAR_BIZNESCOB
             WHERE (' + @e_key + N') COLLATE DATABASE_DEFAULT IN (SELECT operacion COLLATE DATABASE_DEFAULT FROM #ind);';
INSERT INTO #sac EXEC sp_executesql @sql;

IF OBJECT_ID('tempdb..#vw') IS NOT NULL DROP TABLE #vw;
CREATE TABLE #vw (
    CodOperacion varchar(100), DNI varchar(100), Producto varchar(100),
    NroCuotasAprobadas int, NroCuotasAtrasadas int, NroCuotasVencidas int,
    UltCuotaAtrasada int, DiasAtraso int, MtoCuota float,
    SdoCapital float, SdoCapitalVencido float, DeudaTotal float,
    FecDesemb date, FecUltPago date
);
SELECT @lista = STUFF((SELECT N', ' + expr FROM #col WHERE fuente = 'VW' ORDER BY orden
                       FOR XML PATH(''), TYPE).value('.', 'nvarchar(max)'), 1, 2, N'');
SELECT @e_key = expr FROM #col WHERE fuente = 'VW' AND alias = 'CodOperacion';
SET @sql = N'SELECT ' + @lista + N' FROM VW_CLIENTE_CRM_SAC
             WHERE (' + @e_key + N') COLLATE DATABASE_DEFAULT IN (SELECT operacion COLLATE DATABASE_DEFAULT FROM #ind);';
INSERT INTO #vw EXEC sp_executesql @sql;

-- Una fila por operación para los cruces (las duplicadas se cuentan en el bloque 2)
IF OBJECT_ID('tempdb..#base') IS NOT NULL DROP TABLE #base;
SELECT i.operacion,
       s.n_filas_sac, s.UltCuotaAtrasada, s.UltFecVen, s.DiasAtraso AS dias_sac,
       s.CT1, s.CT2, s.CT3, s.cargos1, s.cargos2, s.cargos3,
       v.NroCuotasAprobadas, v.NroCuotasAtrasadas, v.NroCuotasVencidas,
       v.UltCuotaAtrasada AS ult_vw, v.DiasAtraso AS dias_vw, v.MtoCuota,
       v.SdoCapital, v.SdoCapitalVencido, v.FecDesemb, v.Producto
INTO #base
FROM #ind i
OUTER APPLY (
    SELECT COUNT(*) AS n_filas_sac,
           MAX(UltCuotaAtrasada) AS UltCuotaAtrasada, MAX(UltFecVen) AS UltFecVen, MAX(DiasAtraso) AS DiasAtraso,
           MAX(CT1) AS CT1, MAX(CT2) AS CT2, MAX(CT3) AS CT3,
           MAX(ISNULL(CT11,0)+ISNULL(CT12,0)+ISNULL(CT13,0)+ISNULL(CT14,0)+ISNULL(CT15,0)) AS cargos1,
           MAX(ISNULL(CT21,0)+ISNULL(CT22,0)+ISNULL(CT23,0)+ISNULL(CT24,0)+ISNULL(CT25,0)) AS cargos2,
           MAX(ISNULL(CT31,0)+ISNULL(CT32,0)+ISNULL(CT33,0)+ISNULL(CT34,0)+ISNULL(CT35,0)) AS cargos3
    FROM #sac s WHERE s.CodOperacion = i.operacion
) s
OUTER APPLY (SELECT TOP (1) * FROM #vw v WHERE v.CodOperacion = i.operacion) v;

/* -------------------------------------------------------------------------------------
   BLOQUE 2. Cobertura.
   Pregunta: ¿cuántas operaciones individuales tienen en SAC lo necesario para armar
   el estado de cuenta (cuota más atrasada, fecha de vencimiento, CT)?
   ------------------------------------------------------------------------------------- */
SELECT
    COUNT(*)                                                         AS operaciones_individual,
    SUM(CASE WHEN n_filas_sac >= 1 THEN 1 ELSE 0 END)                AS con_fila_sac,
    SUM(CASE WHEN n_filas_sac > 1 THEN 1 ELSE 0 END)                 AS con_fila_sac_duplicada,
    SUM(CASE WHEN UltCuotaAtrasada IS NOT NULL THEN 1 ELSE 0 END)    AS con_ult_cuota_atrasada,
    SUM(CASE WHEN UltFecVen IS NOT NULL THEN 1 ELSE 0 END)           AS con_ultfecven,
    SUM(CASE WHEN CT1 > 0 THEN 1 ELSE 0 END)                         AS con_ct1_positivo,
    SUM(CASE WHEN SdoCapitalVencido > 0 THEN 1 ELSE 0 END)           AS con_capital_vencido_vw,
    SUM(CASE WHEN SdoCapitalVencido > 0 AND ISNULL(CT1, 0) <= 0 THEN 1 ELSE 0 END) AS vencido_sin_ct1,
    SUM(CASE WHEN NroCuotasAprobadas IS NOT NULL THEN 1 ELSE 0 END)  AS en_vista_crm
FROM #base;

-- Duplicadas en SAC con valores distintos (el estado de cuenta no debe elegir una)
SELECT TOP (50) CodOperacion, COUNT(*) AS filas,
       COUNT(DISTINCT UltCuotaAtrasada) AS ult_distintos, COUNT(DISTINCT CT1) AS ct1_distintos,
       COUNT(DISTINCT UltFecVen) AS fechas_distintas
FROM #sac GROUP BY CodOperacion HAVING COUNT(*) > 1
ORDER BY filas DESC;

/* -------------------------------------------------------------------------------------
   BLOQUE 3. ¿CT 1..3 cubre todas las cuotas vencidas?
   Pregunta: si un cliente debe 5 cuotas, SAC solo trae 3 (CT 1, 2, 3).
   ¿Qué tan frecuente es? Define si el estado de cuenta puede llamarse "completo".
   ------------------------------------------------------------------------------------- */
SELECT
    (CASE WHEN CT1 > 0 THEN 1 ELSE 0 END + CASE WHEN CT2 > 0 THEN 1 ELSE 0 END + CASE WHEN CT3 > 0 THEN 1 ELSE 0 END) AS cuotas_con_capital_sac,
    NroCuotasVencidas  AS cuotas_vencidas_vista,
    NroCuotasAtrasadas AS cuotas_atrasadas_vista,
    COUNT(*) AS operaciones
FROM #base
WHERE n_filas_sac >= 1
GROUP BY (CASE WHEN CT1 > 0 THEN 1 ELSE 0 END + CASE WHEN CT2 > 0 THEN 1 ELSE 0 END + CASE WHEN CT3 > 0 THEN 1 ELSE 0 END),
         NroCuotasVencidas, NroCuotasAtrasadas
ORDER BY operaciones DESC;

-- Huecos: CT 2 vacío pero CT 3 con monto (¿cuotas parcialmente pagadas o pagos fuera de orden?)
SELECT COUNT(*) AS operaciones_con_hueco
FROM #base WHERE ISNULL(CT2, 0) <= 0 AND CT3 > 0;

-- Cargos sin capital: la cuota tiene otros cargos pero CT k = 0 o NULL
SELECT
    SUM(CASE WHEN ISNULL(CT1, 0) <= 0 AND cargos1 > 0 THEN 1 ELSE 0 END) AS cargos_sin_capital_c1,
    SUM(CASE WHEN ISNULL(CT2, 0) <= 0 AND cargos2 > 0 THEN 1 ELSE 0 END) AS cargos_sin_capital_c2,
    SUM(CASE WHEN ISNULL(CT3, 0) <= 0 AND cargos3 > 0 THEN 1 ELSE 0 END) AS cargos_sin_capital_c3
FROM #base WHERE n_filas_sac >= 1;

/* -------------------------------------------------------------------------------------
   BLOQUE 4. Conciliación de capital.
   Pregunta: ¿la suma de CT 1..3 cuadra con el capital vencido de la vista?
   ------------------------------------------------------------------------------------- */
SELECT resultado, COUNT(*) AS operaciones
FROM (
    SELECT CASE
        WHEN SdoCapitalVencido IS NULL THEN '5. Sin capital vencido en la vista'
        WHEN ABS(ISNULL(CT1,0) + ISNULL(CT2,0) + ISNULL(CT3,0) - SdoCapitalVencido) <= 0.05 THEN '1. Cuadra (±0.05)'
        WHEN ISNULL(CT1,0) + ISNULL(CT2,0) + ISNULL(CT3,0) < SdoCapitalVencido THEN '2. CT menor que capital vencido'
        ELSE '3. CT mayor que capital vencido'
    END AS resultado
    FROM #base WHERE n_filas_sac >= 1
) x
GROUP BY resultado ORDER BY resultado;

/* -------------------------------------------------------------------------------------
   BLOQUE 5. Fecha de referencia del atraso.
   Pregunta: ¿DiasAtraso (SAC) se mide desde UltFecVen? Si la diferencia contra hoy es
   la misma en casi todas las filas (p. ej. 1 = carga de ayer), entonces
   fecha de corte = UltFecVen + DiasAtraso, y los días vencidos de cada cuota se
   pueden calcular sin inventar una fecha.
   ------------------------------------------------------------------------------------- */
SELECT TOP (15)
    DATEDIFF(day, UltFecVen, CAST(GETDATE() AS date)) - dias_sac AS hoy_menos_ultfecven_menos_diasatraso,
    COUNT(*) AS operaciones
FROM #base
WHERE UltFecVen IS NOT NULL AND dias_sac IS NOT NULL
GROUP BY DATEDIFF(day, UltFecVen, CAST(GETDATE() AS date)) - dias_sac
ORDER BY operaciones DESC;

-- Atraso SAC (hoy) vs atraso de la vista (asignación)
SELECT TOP (15) dias_sac - dias_vw AS dias_sac_menos_dias_vista, COUNT(*) AS operaciones
FROM #base WHERE dias_sac IS NOT NULL AND dias_vw IS NOT NULL
GROUP BY dias_sac - dias_vw ORDER BY operaciones DESC;

-- ¿Ult_CuotaAtrasada coincide entre SAC y la vista?
SELECT CASE WHEN UltCuotaAtrasada = ult_vw THEN 'Igual' WHEN ult_vw IS NULL OR UltCuotaAtrasada IS NULL THEN 'Falta en una fuente' ELSE 'Distinta' END AS ult_cuota,
       COUNT(*) AS operaciones
FROM #base WHERE n_filas_sac >= 1
GROUP BY CASE WHEN UltCuotaAtrasada = ult_vw THEN 'Igual' WHEN ult_vw IS NULL OR UltCuotaAtrasada IS NULL THEN 'Falta en una fuente' ELSE 'Distinta' END;

/* -------------------------------------------------------------------------------------
   BLOQUE 6. Periodicidad (ORIENTATIVO, NO ES UNA REGLA).
   Pregunta: ¿los créditos individuales son mensuales? Solo para saber si hace falta
   pedir la frecuencia de pago. Días promedio por cuota = (UltFecVen - FecDesemb) / Ult_CuotaAtrasada.
   ------------------------------------------------------------------------------------- */
SELECT TOP (20)
    CAST(ROUND(DATEDIFF(day, FecDesemb, UltFecVen) * 1.0 / UltCuotaAtrasada, 0) AS int) AS dias_por_cuota_aprox,
    COUNT(*) AS operaciones
FROM #base
WHERE FecDesemb IS NOT NULL AND UltFecVen IS NOT NULL AND UltCuotaAtrasada > 0
GROUP BY CAST(ROUND(DATEDIFF(day, FecDesemb, UltFecVen) * 1.0 / UltCuotaAtrasada, 0) AS int)
ORDER BY operaciones DESC;

/* -------------------------------------------------------------------------------------
   BLOQUE 7. Muestra para contrastar a mano contra el estado de cuenta de WSAC.
   Elegir 5 operaciones de aquí y comparar cuota por cuota con la pantalla del banco.
   ------------------------------------------------------------------------------------- */
SELECT TOP (20)
    operacion, Producto, NroCuotasAprobadas, NroCuotasVencidas, UltCuotaAtrasada, ult_vw,
    UltFecVen, dias_sac, dias_vw,
    CT1, cargos1, CT2, cargos2, CT3, cargos3,
    ISNULL(CT1,0) + ISNULL(CT2,0) + ISNULL(CT3,0) AS suma_ct_capital,
    SdoCapitalVencido, SdoCapital, MtoCuota, FecDesemb
FROM #base
WHERE n_filas_sac = 1 AND CT1 > 0
ORDER BY NroCuotasVencidas DESC, dias_sac DESC;
