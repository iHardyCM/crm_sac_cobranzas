/* =====================================================================================
   DIAGNÓSTICO — SCORE TELEFÓNICO (solo lectura)
   Fecha: 14/11/2026

   Para qué: antes de rehacer el score, saber
     A. cómo calcula hoy el score la vista del CRM y de qué objetos depende;
     B. cómo lo calculan las consultas de score por cartera que usa la operación;
     C. qué tan grande es y cómo se refresca;
     D. qué hay de teléfono en TEMP_TELEFONOS;
     E. hasta qué fecha llegan los cortes de Biznescob Analytics por cartera.

   No modifica nada: solo SELECT sobre metadatos y conteos.
   Cada bloque está separado por GO: si un bloque falla (objeto inexistente o sin permiso),
   los demás siguen. Guarda TODA la salida (también los mensajes de error) y pásamela.

   Recomendado en SSMS: Resultados en texto (Ctrl+T) o guardar cada grilla.
   Las definiciones largas (columna "definicion") se cortan en la grilla: para verlas completas,
   Herramientas → Opciones → Resultados de consulta → Texto → máximo 8192, o copia la celda.
   ===================================================================================== */

SET NOCOUNT ON;
SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED;
GO

/* -------------------------------------------------------------------------------------
   0. Instancia y bases (¿Analytics y CobAuto están en el mismo servidor?)
   ------------------------------------------------------------------------------------- */
SELECT @@SERVERNAME AS servidor, DB_NAME() AS base_actual;

SELECT name AS base, state_desc
FROM sys.databases
WHERE name IN ('CobAuto', 'SISCOB', 'Desarrollo', 'ControlCobranza',
               'Financiera_OH_Cobranzas', 'Interbank_Cobranzas', 'Interbank_Propia_Cobranzas',
               'Compartamos_Vigente_Cobranzas', 'Compartamos_Castigo_Cobranzas',
               'PROPIA_COBRANZAS', 'MiBanco_Cobranzas')
ORDER BY name;
GO

/* -------------------------------------------------------------------------------------
   A1. Definición de la vista y del SP del score del CRM (CobAuto)
   ------------------------------------------------------------------------------------- */
SELECT o.name AS objeto, o.type_desc AS tipo, o.modify_date, LEN(m.definition) AS largo,
       m.definition AS definicion
FROM CobAuto.sys.objects o
LEFT JOIN CobAuto.sys.sql_modules m ON m.object_id = o.object_id
WHERE o.name IN ('VW_SCORE_TELEFONICO_CRM', 'SP_REFRESCAR_SCORE_TELEFONICO_CRM',
                 'SP_SCORE_TELEFONICO_APLICAR_LISTA_NEGRA')
ORDER BY o.name;
GO

/* A2. Objetos de los que depende la vista (vistas/tablas/funciones que lee).
       Si aparecen vistas intermedias de CobAuto, sus definiciones salen en A3. */
SELECT o.name AS objeto,
       d.referenced_server_name AS servidor, d.referenced_database_name AS base,
       d.referenced_schema_name AS esquema, d.referenced_entity_name AS referencia
FROM CobAuto.sys.sql_expression_dependencies d
JOIN CobAuto.sys.objects o ON o.object_id = d.referencing_id
WHERE o.name IN ('VW_SCORE_TELEFONICO_CRM', 'SP_REFRESCAR_SCORE_TELEFONICO_CRM')
ORDER BY o.name, d.referenced_database_name, d.referenced_entity_name;
GO

/* A3. Definición de las vistas/funciones de CobAuto que usa la vista (primer nivel) */
SELECT r.name AS objeto, r.type_desc AS tipo, r.modify_date, LEN(m.definition) AS largo,
       m.definition AS definicion
FROM CobAuto.sys.sql_expression_dependencies d
JOIN CobAuto.sys.objects o ON o.object_id = d.referencing_id
JOIN CobAuto.sys.objects r ON r.object_id = d.referenced_id
LEFT JOIN CobAuto.sys.sql_modules m ON m.object_id = r.object_id
WHERE o.name = 'VW_SCORE_TELEFONICO_CRM'
  AND r.type IN ('V', 'FN', 'IF', 'TF')
ORDER BY r.name;
GO

/* -------------------------------------------------------------------------------------
   B. Consultas de score por cartera que usa la operación (definición + dependencias)
   ------------------------------------------------------------------------------------- */
SELECT 'Financiera_OH_Cobranzas' AS base, o.name AS objeto, o.type_desc AS tipo, o.modify_date,
       LEN(m.definition) AS largo, m.definition AS definicion
FROM Financiera_OH_Cobranzas.sys.objects o
LEFT JOIN Financiera_OH_Cobranzas.sys.sql_modules m ON m.object_id = o.object_id
WHERE o.name LIKE '%SCORE%';
GO
SELECT 'Interbank_Cobranzas' AS base, o.name AS objeto, o.type_desc AS tipo, o.modify_date,
       LEN(m.definition) AS largo, m.definition AS definicion
FROM Interbank_Cobranzas.sys.objects o
LEFT JOIN Interbank_Cobranzas.sys.sql_modules m ON m.object_id = o.object_id
WHERE o.name LIKE '%SCORE%';
GO
SELECT 'Compartamos_Vigente_Cobranzas' AS base, o.name AS objeto, o.type_desc AS tipo, o.modify_date,
       LEN(m.definition) AS largo, m.definition AS definicion
FROM Compartamos_Vigente_Cobranzas.sys.objects o
LEFT JOIN Compartamos_Vigente_Cobranzas.sys.sql_modules m ON m.object_id = o.object_id
WHERE o.name LIKE '%SCORE%' AND o.name NOT LIKE 'COMP_%SCORE%MES%';  -- excluye la foto del score de riesgo del banco
GO
SELECT 'Compartamos_Castigo_Cobranzas' AS base, o.name AS objeto, o.type_desc AS tipo, o.modify_date,
       LEN(m.definition) AS largo, m.definition AS definicion
FROM Compartamos_Castigo_Cobranzas.sys.objects o
LEFT JOIN Compartamos_Castigo_Cobranzas.sys.sql_modules m ON m.object_id = o.object_id
WHERE o.name LIKE '%SCORE%';
GO
SELECT 'MiBanco_Cobranzas' AS base, o.name AS objeto, o.type_desc AS tipo, o.modify_date,
       LEN(m.definition) AS largo, m.definition AS definicion
FROM MiBanco_Cobranzas.sys.objects o
LEFT JOIN MiBanco_Cobranzas.sys.sql_modules m ON m.object_id = o.object_id
WHERE o.name LIKE '%SCORE%';
GO

/* -------------------------------------------------------------------------------------
   C1. Tamaño y contenido del score actual, por cartera
   ------------------------------------------------------------------------------------- */
SELECT IDCARTERA, MAX(CARTERA_SCORE) AS cartera_score,
       COUNT_BIG(*) AS filas,
       COUNT(DISTINCT DNI) AS clientes,
       COUNT(DISTINCT TELEFONO) AS telefonos,
       MIN(SCORE_TELEFONO) AS score_min, MAX(SCORE_TELEFONO) AS score_max,
       AVG(CAST(SCORE_TELEFONO AS decimal(10,2))) AS score_prom,
       COUNT(DISTINCT SCORE_TELEFONO) AS valores_distintos_score
FROM CobAuto.dbo.TBL_SCORE_TELEFONICO_CRM WITH (NOLOCK)
GROUP BY IDCARTERA
ORDER BY IDCARTERA;
GO

/* C2. Prioridad calculada vs prioridad de origen (para entender PRIORIDAD_CONTACTO) */
SELECT TOP 60 PRIORIDAD_FONO, PRIORIDAD_CONTACTO, COUNT_BIG(*) AS filas,
       MIN(SCORE_TELEFONO) AS score_min, MAX(SCORE_TELEFONO) AS score_max
FROM CobAuto.dbo.TBL_SCORE_TELEFONICO_CRM WITH (NOLOCK)
GROUP BY PRIORIDAD_FONO, PRIORIDAD_CONTACTO
ORDER BY filas DESC;
GO

/* C3. Mismo teléfono en varios clientes (por cartera) */
SELECT IDCARTERA,
       SUM(CASE WHEN n_dni = 1 THEN 1 ELSE 0 END) AS telefonos_1_cliente,
       SUM(CASE WHEN n_dni BETWEEN 2 AND 4 THEN 1 ELSE 0 END) AS telefonos_2_a_4_clientes,
       SUM(CASE WHEN n_dni >= 5 THEN 1 ELSE 0 END) AS telefonos_5_o_mas_clientes
FROM (SELECT IDCARTERA, TELEFONO, COUNT(DISTINCT DNI) AS n_dni
      FROM CobAuto.dbo.TBL_SCORE_TELEFONICO_CRM WITH (NOLOCK)
      GROUP BY IDCARTERA, TELEFONO) t
GROUP BY IDCARTERA
ORDER BY IDCARTERA;
GO

/* C4. ¿Está instalada la versión del refresco con lista negra? ¿Hay log? */
SELECT
    CASE WHEN OBJECT_ID('CobAuto.dbo.TBL_SCORE_TELEFONICO_CRM_EXCLUIDOS', 'U') IS NULL THEN 'NO' ELSE 'SI' END AS existe_tabla_excluidos,
    CASE WHEN OBJECT_DEFINITION(OBJECT_ID('CobAuto.dbo.SP_REFRESCAR_SCORE_TELEFONICO_CRM'))
              LIKE '%vw_ListaNegraVigentePorCartera%' THEN 'SI' ELSE 'NO' END AS sp_aplica_lista_negra,
    CASE WHEN OBJECT_ID('CobAuto.dbo.score_telefonico_refresh_log', 'U') IS NULL THEN 'NO' ELSE 'SI' END AS existe_log;
GO
IF OBJECT_ID('CobAuto.dbo.score_telefonico_refresh_log', 'U') IS NOT NULL
    EXEC ('SELECT TOP 10 * FROM CobAuto.dbo.score_telefonico_refresh_log WITH (NOLOCK) ORDER BY 1 DESC');
GO

/* C5. ¿Quién ejecuta el refresco? (Jobs del Agente que lo llaman; puede pedir permiso en msdb) */
SELECT j.name AS job, j.enabled, s.step_name, s.database_name, s.command
FROM msdb.dbo.sysjobs j
JOIN msdb.dbo.sysjobsteps s ON s.job_id = j.job_id
WHERE s.command LIKE '%SCORE_TELEFONIC%' OR s.command LIKE '%SCORE_FONO%' OR s.command LIKE '%DASH_%';
GO

/* -------------------------------------------------------------------------------------
   D. TEMP_TELEFONOS (origen de las características del teléfono)
   ------------------------------------------------------------------------------------- */
SELECT c.column_id, c.name AS columna, t.name AS tipo, c.max_length
FROM Desarrollo.sys.columns c
JOIN Desarrollo.sys.types t ON t.user_type_id = c.user_type_id
WHERE c.object_id = OBJECT_ID('Desarrollo.dbo.TEMP_TELEFONOS')
ORDER BY c.column_id;

SELECT SUM(p.rows) AS filas_aprox
FROM Desarrollo.sys.partitions p
WHERE p.object_id = OBJECT_ID('Desarrollo.dbo.TEMP_TELEFONOS') AND p.index_id IN (0, 1);

SELECT i.name AS indice, i.type_desc,
       STUFF((SELECT ',' + c.name FROM Desarrollo.sys.index_columns ic
              JOIN Desarrollo.sys.columns c ON c.object_id = ic.object_id AND c.column_id = ic.column_id
              WHERE ic.object_id = i.object_id AND ic.index_id = i.index_id AND ic.is_included_column = 0
              ORDER BY ic.key_ordinal FOR XML PATH('')), 1, 1, '') AS columnas
FROM Desarrollo.sys.indexes i
WHERE i.object_id = OBJECT_ID('Desarrollo.dbo.TEMP_TELEFONOS') AND i.index_id > 0;
GO

/* -------------------------------------------------------------------------------------
   E. Último corte guardado de Biznescob Analytics por cartera
      (fuentes que usa Analytics en resumen_estandar/compromisos.py)
   ------------------------------------------------------------------------------------- */
SELECT '132 SIP' AS cartera, MAX(FECHA_CORTE) AS ultimo_corte
FROM Financiera_OH_Cobranzas.dbo.TBL_SIP_CLIENTE_BI_HISTORICO WITH (NOLOCK);
GO
SELECT '117 Interbank' AS cartera, MAX(FECHA_CORTE_ANALITICA) AS ultimo_corte
FROM Interbank_Cobranzas.dbo.TBL_IBK_CUENTA_HISTORICO WITH (NOLOCK);
GO
SELECT '126/128 Vigente IND/CCM' AS cartera, ID_CARTERA, MAX(FECHA_CORTE) AS ultimo_corte
FROM Compartamos_Vigente_Cobranzas.dbo.COMP_VIGENTE_CLIENTE_BI_HISTORICO WITH (NOLOCK)
GROUP BY ID_CARTERA;
GO
SELECT '133 Grupal' AS cartera, MAX(FECHA_CORTE) AS ultimo_corte
FROM Compartamos_Vigente_Cobranzas.dbo.COMP_GRUPAL_INTEGRANTE_BI_HISTORICO WITH (NOLOCK);
GO
SELECT '144 Castigo grupal' AS cartera, MAX(FECHA_CORTE) AS ultimo_corte
FROM Compartamos_Castigo_Cobranzas.dbo.CASTIGO_GRUPAL_DIMENSION_CUENTA_HISTORICO WITH (NOLOCK);
GO
SELECT '137 Propia IBK' AS cartera, MAX(FECHA_CORTE) AS ultimo_corte
FROM Interbank_Propia_Cobranzas.dbo.PROPIA_CUENTA_CORTE WITH (NOLOCK);
GO
SELECT '148 Propia SIP' AS cartera, MAX(FECHA_CORTE) AS ultimo_corte
FROM PROPIA_COBRANZAS.dbo.PROPIA_CUENTA_CORTE WITH (NOLOCK);
GO
SELECT '112 MiBanco castigo' AS cartera, MAX(FECHA_CORTE) AS ultimo_corte
FROM MiBanco_Cobranzas.dbo.MB_CASTIGO_PRESTAMO_CORTE WITH (NOLOCK);
GO
/* 124 Castigo individual no guarda corte diario en Analytics: lee la asignación del periodo
   (VW_CASTIGO_IND_ASIGNACION_BI_LIMPIA). 135 y 143 (MiBanco vigente) no tienen fuente en Analytics. */
