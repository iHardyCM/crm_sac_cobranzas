/* =====================================================================
   Diagnóstico — Cierre histórico Compartamos VIGENTE INDIVIDUAL
   Error: "Error converting data type varchar to float"
   SOLO LECTURA. Copiar todo y ejecutar en SSMS: es UNA sola consulta.

   Revisa cada columna que el cierre copia de
     Desarrollo.dbo.compartamos_individual -> Compartamos_Vigente_Cobranzas.dbo.HIST_COMPARTAMOS_INDIVIDUAL
   y devuelve SOLO las columnas que rompen el cierre: el histórico las
   guarda como número y en el origen hay textos que no son número.
   Muestra cuántas filas fallan y dos ejemplos de valor.

   Nota: la columna [Cancelación%] del histórico hoy se llena desde
   [Cancelacion] del origen (así lo arma el programa). También se revisa.
   ===================================================================== */
WITH diagnostico AS (
SELECT N'Gestor/Externo' AS columna_historico, N'Gestor/Externo' AS columna_origen,
       (SELECT TOP 1 ty.name FROM Compartamos_Vigente_Cobranzas.sys.columns c JOIN Compartamos_Vigente_Cobranzas.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Compartamos_Vigente_Cobranzas.dbo.HIST_COMPARTAMOS_INDIVIDUAL') AND c.name = N'Gestor/Externo') AS tipo_historico,
       (SELECT TOP 1 ty.name FROM Desarrollo.sys.columns c JOIN Desarrollo.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Desarrollo.dbo.compartamos_individual') AND c.name = N'Gestor/Externo') AS tipo_origen,
       a.filas_no_numericas, a.ejemplo_1, a.ejemplo_2
FROM (SELECT SUM(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN 1 ELSE 0 END) AS filas_no_numericas,
             MIN(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_1,
             MAX(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_2
      FROM (SELECT NULLIF(LTRIM(RTRIM(CONVERT(NVARCHAR(200), [Gestor/Externo]))), N'') AS v
            FROM Desarrollo.dbo.compartamos_individual WITH (NOLOCK)) x) a
UNION ALL
SELECT N'Oficina' AS columna_historico, N'Oficina' AS columna_origen,
       (SELECT TOP 1 ty.name FROM Compartamos_Vigente_Cobranzas.sys.columns c JOIN Compartamos_Vigente_Cobranzas.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Compartamos_Vigente_Cobranzas.dbo.HIST_COMPARTAMOS_INDIVIDUAL') AND c.name = N'Oficina') AS tipo_historico,
       (SELECT TOP 1 ty.name FROM Desarrollo.sys.columns c JOIN Desarrollo.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Desarrollo.dbo.compartamos_individual') AND c.name = N'Oficina') AS tipo_origen,
       a.filas_no_numericas, a.ejemplo_1, a.ejemplo_2
FROM (SELECT SUM(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN 1 ELSE 0 END) AS filas_no_numericas,
             MIN(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_1,
             MAX(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_2
      FROM (SELECT NULLIF(LTRIM(RTRIM(CONVERT(NVARCHAR(200), [Oficina]))), N'') AS v
            FROM Desarrollo.dbo.compartamos_individual WITH (NOLOCK)) x) a
UNION ALL
SELECT N'codclienteCFIS' AS columna_historico, N'codclienteCFIS' AS columna_origen,
       (SELECT TOP 1 ty.name FROM Compartamos_Vigente_Cobranzas.sys.columns c JOIN Compartamos_Vigente_Cobranzas.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Compartamos_Vigente_Cobranzas.dbo.HIST_COMPARTAMOS_INDIVIDUAL') AND c.name = N'codclienteCFIS') AS tipo_historico,
       (SELECT TOP 1 ty.name FROM Desarrollo.sys.columns c JOIN Desarrollo.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Desarrollo.dbo.compartamos_individual') AND c.name = N'codclienteCFIS') AS tipo_origen,
       a.filas_no_numericas, a.ejemplo_1, a.ejemplo_2
FROM (SELECT SUM(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN 1 ELSE 0 END) AS filas_no_numericas,
             MIN(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_1,
             MAX(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_2
      FROM (SELECT NULLIF(LTRIM(RTRIM(CONVERT(NVARCHAR(200), [codclienteCFIS]))), N'') AS v
            FROM Desarrollo.dbo.compartamos_individual WITH (NOLOCK)) x) a
UNION ALL
SELECT N'codcuentaCFIS' AS columna_historico, N'codcuentaCFIS' AS columna_origen,
       (SELECT TOP 1 ty.name FROM Compartamos_Vigente_Cobranzas.sys.columns c JOIN Compartamos_Vigente_Cobranzas.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Compartamos_Vigente_Cobranzas.dbo.HIST_COMPARTAMOS_INDIVIDUAL') AND c.name = N'codcuentaCFIS') AS tipo_historico,
       (SELECT TOP 1 ty.name FROM Desarrollo.sys.columns c JOIN Desarrollo.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Desarrollo.dbo.compartamos_individual') AND c.name = N'codcuentaCFIS') AS tipo_origen,
       a.filas_no_numericas, a.ejemplo_1, a.ejemplo_2
FROM (SELECT SUM(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN 1 ELSE 0 END) AS filas_no_numericas,
             MIN(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_1,
             MAX(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_2
      FROM (SELECT NULLIF(LTRIM(RTRIM(CONVERT(NVARCHAR(200), [codcuentaCFIS]))), N'') AS v
            FROM Desarrollo.dbo.compartamos_individual WITH (NOLOCK)) x) a
UNION ALL
SELECT N'CodclienteBT' AS columna_historico, N'CodclienteBT' AS columna_origen,
       (SELECT TOP 1 ty.name FROM Compartamos_Vigente_Cobranzas.sys.columns c JOIN Compartamos_Vigente_Cobranzas.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Compartamos_Vigente_Cobranzas.dbo.HIST_COMPARTAMOS_INDIVIDUAL') AND c.name = N'CodclienteBT') AS tipo_historico,
       (SELECT TOP 1 ty.name FROM Desarrollo.sys.columns c JOIN Desarrollo.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Desarrollo.dbo.compartamos_individual') AND c.name = N'CodclienteBT') AS tipo_origen,
       a.filas_no_numericas, a.ejemplo_1, a.ejemplo_2
FROM (SELECT SUM(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN 1 ELSE 0 END) AS filas_no_numericas,
             MIN(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_1,
             MAX(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_2
      FROM (SELECT NULLIF(LTRIM(RTRIM(CONVERT(NVARCHAR(200), [CodclienteBT]))), N'') AS v
            FROM Desarrollo.dbo.compartamos_individual WITH (NOLOCK)) x) a
UNION ALL
SELECT N'Operacion' AS columna_historico, N'Operacion' AS columna_origen,
       (SELECT TOP 1 ty.name FROM Compartamos_Vigente_Cobranzas.sys.columns c JOIN Compartamos_Vigente_Cobranzas.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Compartamos_Vigente_Cobranzas.dbo.HIST_COMPARTAMOS_INDIVIDUAL') AND c.name = N'Operacion') AS tipo_historico,
       (SELECT TOP 1 ty.name FROM Desarrollo.sys.columns c JOIN Desarrollo.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Desarrollo.dbo.compartamos_individual') AND c.name = N'Operacion') AS tipo_origen,
       a.filas_no_numericas, a.ejemplo_1, a.ejemplo_2
FROM (SELECT SUM(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN 1 ELSE 0 END) AS filas_no_numericas,
             MIN(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_1,
             MAX(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_2
      FROM (SELECT NULLIF(LTRIM(RTRIM(CONVERT(NVARCHAR(200), [Operacion]))), N'') AS v
            FROM Desarrollo.dbo.compartamos_individual WITH (NOLOCK)) x) a
UNION ALL
SELECT N'ctacliente' AS columna_historico, N'ctacliente' AS columna_origen,
       (SELECT TOP 1 ty.name FROM Compartamos_Vigente_Cobranzas.sys.columns c JOIN Compartamos_Vigente_Cobranzas.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Compartamos_Vigente_Cobranzas.dbo.HIST_COMPARTAMOS_INDIVIDUAL') AND c.name = N'ctacliente') AS tipo_historico,
       (SELECT TOP 1 ty.name FROM Desarrollo.sys.columns c JOIN Desarrollo.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Desarrollo.dbo.compartamos_individual') AND c.name = N'ctacliente') AS tipo_origen,
       a.filas_no_numericas, a.ejemplo_1, a.ejemplo_2
FROM (SELECT SUM(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN 1 ELSE 0 END) AS filas_no_numericas,
             MIN(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_1,
             MAX(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_2
      FROM (SELECT NULLIF(LTRIM(RTRIM(CONVERT(NVARCHAR(200), [ctacliente]))), N'') AS v
            FROM Desarrollo.dbo.compartamos_individual WITH (NOLOCK)) x) a
UNION ALL
SELECT N'codcuenta' AS columna_historico, N'codcuenta' AS columna_origen,
       (SELECT TOP 1 ty.name FROM Compartamos_Vigente_Cobranzas.sys.columns c JOIN Compartamos_Vigente_Cobranzas.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Compartamos_Vigente_Cobranzas.dbo.HIST_COMPARTAMOS_INDIVIDUAL') AND c.name = N'codcuenta') AS tipo_historico,
       (SELECT TOP 1 ty.name FROM Desarrollo.sys.columns c JOIN Desarrollo.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Desarrollo.dbo.compartamos_individual') AND c.name = N'codcuenta') AS tipo_origen,
       a.filas_no_numericas, a.ejemplo_1, a.ejemplo_2
FROM (SELECT SUM(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN 1 ELSE 0 END) AS filas_no_numericas,
             MIN(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_1,
             MAX(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_2
      FROM (SELECT NULLIF(LTRIM(RTRIM(CONVERT(NVARCHAR(200), [codcuenta]))), N'') AS v
            FROM Desarrollo.dbo.compartamos_individual WITH (NOLOCK)) x) a
UNION ALL
SELECT N'FLG_CLIENTE' AS columna_historico, N'FLG_CLIENTE' AS columna_origen,
       (SELECT TOP 1 ty.name FROM Compartamos_Vigente_Cobranzas.sys.columns c JOIN Compartamos_Vigente_Cobranzas.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Compartamos_Vigente_Cobranzas.dbo.HIST_COMPARTAMOS_INDIVIDUAL') AND c.name = N'FLG_CLIENTE') AS tipo_historico,
       (SELECT TOP 1 ty.name FROM Desarrollo.sys.columns c JOIN Desarrollo.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Desarrollo.dbo.compartamos_individual') AND c.name = N'FLG_CLIENTE') AS tipo_origen,
       a.filas_no_numericas, a.ejemplo_1, a.ejemplo_2
FROM (SELECT SUM(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN 1 ELSE 0 END) AS filas_no_numericas,
             MIN(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_1,
             MAX(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_2
      FROM (SELECT NULLIF(LTRIM(RTRIM(CONVERT(NVARCHAR(200), [FLG_CLIENTE]))), N'') AS v
            FROM Desarrollo.dbo.compartamos_individual WITH (NOLOCK)) x) a
UNION ALL
SELECT N'LineaNegocio' AS columna_historico, N'LineaNegocio' AS columna_origen,
       (SELECT TOP 1 ty.name FROM Compartamos_Vigente_Cobranzas.sys.columns c JOIN Compartamos_Vigente_Cobranzas.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Compartamos_Vigente_Cobranzas.dbo.HIST_COMPARTAMOS_INDIVIDUAL') AND c.name = N'LineaNegocio') AS tipo_historico,
       (SELECT TOP 1 ty.name FROM Desarrollo.sys.columns c JOIN Desarrollo.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Desarrollo.dbo.compartamos_individual') AND c.name = N'LineaNegocio') AS tipo_origen,
       a.filas_no_numericas, a.ejemplo_1, a.ejemplo_2
FROM (SELECT SUM(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN 1 ELSE 0 END) AS filas_no_numericas,
             MIN(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_1,
             MAX(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_2
      FROM (SELECT NULLIF(LTRIM(RTRIM(CONVERT(NVARCHAR(200), [LineaNegocio]))), N'') AS v
            FROM Desarrollo.dbo.compartamos_individual WITH (NOLOCK)) x) a
UNION ALL
SELECT N'Tipo Gestión' AS columna_historico, N'Tipo Gestión' AS columna_origen,
       (SELECT TOP 1 ty.name FROM Compartamos_Vigente_Cobranzas.sys.columns c JOIN Compartamos_Vigente_Cobranzas.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Compartamos_Vigente_Cobranzas.dbo.HIST_COMPARTAMOS_INDIVIDUAL') AND c.name = N'Tipo Gestión') AS tipo_historico,
       (SELECT TOP 1 ty.name FROM Desarrollo.sys.columns c JOIN Desarrollo.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Desarrollo.dbo.compartamos_individual') AND c.name = N'Tipo Gestión') AS tipo_origen,
       a.filas_no_numericas, a.ejemplo_1, a.ejemplo_2
FROM (SELECT SUM(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN 1 ELSE 0 END) AS filas_no_numericas,
             MIN(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_1,
             MAX(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_2
      FROM (SELECT NULLIF(LTRIM(RTRIM(CONVERT(NVARCHAR(200), [Tipo Gestión]))), N'') AS v
            FROM Desarrollo.dbo.compartamos_individual WITH (NOLOCK)) x) a
UNION ALL
SELECT N'Nomcliente' AS columna_historico, N'Nomcliente' AS columna_origen,
       (SELECT TOP 1 ty.name FROM Compartamos_Vigente_Cobranzas.sys.columns c JOIN Compartamos_Vigente_Cobranzas.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Compartamos_Vigente_Cobranzas.dbo.HIST_COMPARTAMOS_INDIVIDUAL') AND c.name = N'Nomcliente') AS tipo_historico,
       (SELECT TOP 1 ty.name FROM Desarrollo.sys.columns c JOIN Desarrollo.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Desarrollo.dbo.compartamos_individual') AND c.name = N'Nomcliente') AS tipo_origen,
       a.filas_no_numericas, a.ejemplo_1, a.ejemplo_2
FROM (SELECT SUM(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN 1 ELSE 0 END) AS filas_no_numericas,
             MIN(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_1,
             MAX(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_2
      FROM (SELECT NULLIF(LTRIM(RTRIM(CONVERT(NVARCHAR(200), [Nomcliente]))), N'') AS v
            FROM Desarrollo.dbo.compartamos_individual WITH (NOLOCK)) x) a
UNION ALL
SELECT N'DireccionPrincipal' AS columna_historico, N'DireccionPrincipal' AS columna_origen,
       (SELECT TOP 1 ty.name FROM Compartamos_Vigente_Cobranzas.sys.columns c JOIN Compartamos_Vigente_Cobranzas.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Compartamos_Vigente_Cobranzas.dbo.HIST_COMPARTAMOS_INDIVIDUAL') AND c.name = N'DireccionPrincipal') AS tipo_historico,
       (SELECT TOP 1 ty.name FROM Desarrollo.sys.columns c JOIN Desarrollo.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Desarrollo.dbo.compartamos_individual') AND c.name = N'DireccionPrincipal') AS tipo_origen,
       a.filas_no_numericas, a.ejemplo_1, a.ejemplo_2
FROM (SELECT SUM(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN 1 ELSE 0 END) AS filas_no_numericas,
             MIN(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_1,
             MAX(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_2
      FROM (SELECT NULLIF(LTRIM(RTRIM(CONVERT(NVARCHAR(200), [DireccionPrincipal]))), N'') AS v
            FROM Desarrollo.dbo.compartamos_individual WITH (NOLOCK)) x) a
UNION ALL
SELECT N'ProvinciaPrincipal' AS columna_historico, N'ProvinciaPrincipal' AS columna_origen,
       (SELECT TOP 1 ty.name FROM Compartamos_Vigente_Cobranzas.sys.columns c JOIN Compartamos_Vigente_Cobranzas.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Compartamos_Vigente_Cobranzas.dbo.HIST_COMPARTAMOS_INDIVIDUAL') AND c.name = N'ProvinciaPrincipal') AS tipo_historico,
       (SELECT TOP 1 ty.name FROM Desarrollo.sys.columns c JOIN Desarrollo.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Desarrollo.dbo.compartamos_individual') AND c.name = N'ProvinciaPrincipal') AS tipo_origen,
       a.filas_no_numericas, a.ejemplo_1, a.ejemplo_2
FROM (SELECT SUM(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN 1 ELSE 0 END) AS filas_no_numericas,
             MIN(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_1,
             MAX(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_2
      FROM (SELECT NULLIF(LTRIM(RTRIM(CONVERT(NVARCHAR(200), [ProvinciaPrincipal]))), N'') AS v
            FROM Desarrollo.dbo.compartamos_individual WITH (NOLOCK)) x) a
UNION ALL
SELECT N'DistritoPrincipal' AS columna_historico, N'DistritoPrincipal' AS columna_origen,
       (SELECT TOP 1 ty.name FROM Compartamos_Vigente_Cobranzas.sys.columns c JOIN Compartamos_Vigente_Cobranzas.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Compartamos_Vigente_Cobranzas.dbo.HIST_COMPARTAMOS_INDIVIDUAL') AND c.name = N'DistritoPrincipal') AS tipo_historico,
       (SELECT TOP 1 ty.name FROM Desarrollo.sys.columns c JOIN Desarrollo.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Desarrollo.dbo.compartamos_individual') AND c.name = N'DistritoPrincipal') AS tipo_origen,
       a.filas_no_numericas, a.ejemplo_1, a.ejemplo_2
FROM (SELECT SUM(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN 1 ELSE 0 END) AS filas_no_numericas,
             MIN(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_1,
             MAX(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_2
      FROM (SELECT NULLIF(LTRIM(RTRIM(CONVERT(NVARCHAR(200), [DistritoPrincipal]))), N'') AS v
            FROM Desarrollo.dbo.compartamos_individual WITH (NOLOCK)) x) a
UNION ALL
SELECT N'DireccionNegocio' AS columna_historico, N'DireccionNegocio' AS columna_origen,
       (SELECT TOP 1 ty.name FROM Compartamos_Vigente_Cobranzas.sys.columns c JOIN Compartamos_Vigente_Cobranzas.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Compartamos_Vigente_Cobranzas.dbo.HIST_COMPARTAMOS_INDIVIDUAL') AND c.name = N'DireccionNegocio') AS tipo_historico,
       (SELECT TOP 1 ty.name FROM Desarrollo.sys.columns c JOIN Desarrollo.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Desarrollo.dbo.compartamos_individual') AND c.name = N'DireccionNegocio') AS tipo_origen,
       a.filas_no_numericas, a.ejemplo_1, a.ejemplo_2
FROM (SELECT SUM(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN 1 ELSE 0 END) AS filas_no_numericas,
             MIN(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_1,
             MAX(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_2
      FROM (SELECT NULLIF(LTRIM(RTRIM(CONVERT(NVARCHAR(200), [DireccionNegocio]))), N'') AS v
            FROM Desarrollo.dbo.compartamos_individual WITH (NOLOCK)) x) a
UNION ALL
SELECT N'ProvinciaNegoci' AS columna_historico, N'ProvinciaNegoci' AS columna_origen,
       (SELECT TOP 1 ty.name FROM Compartamos_Vigente_Cobranzas.sys.columns c JOIN Compartamos_Vigente_Cobranzas.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Compartamos_Vigente_Cobranzas.dbo.HIST_COMPARTAMOS_INDIVIDUAL') AND c.name = N'ProvinciaNegoci') AS tipo_historico,
       (SELECT TOP 1 ty.name FROM Desarrollo.sys.columns c JOIN Desarrollo.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Desarrollo.dbo.compartamos_individual') AND c.name = N'ProvinciaNegoci') AS tipo_origen,
       a.filas_no_numericas, a.ejemplo_1, a.ejemplo_2
FROM (SELECT SUM(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN 1 ELSE 0 END) AS filas_no_numericas,
             MIN(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_1,
             MAX(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_2
      FROM (SELECT NULLIF(LTRIM(RTRIM(CONVERT(NVARCHAR(200), [ProvinciaNegoci]))), N'') AS v
            FROM Desarrollo.dbo.compartamos_individual WITH (NOLOCK)) x) a
UNION ALL
SELECT N'DistritoNegocio' AS columna_historico, N'DistritoNegocio' AS columna_origen,
       (SELECT TOP 1 ty.name FROM Compartamos_Vigente_Cobranzas.sys.columns c JOIN Compartamos_Vigente_Cobranzas.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Compartamos_Vigente_Cobranzas.dbo.HIST_COMPARTAMOS_INDIVIDUAL') AND c.name = N'DistritoNegocio') AS tipo_historico,
       (SELECT TOP 1 ty.name FROM Desarrollo.sys.columns c JOIN Desarrollo.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Desarrollo.dbo.compartamos_individual') AND c.name = N'DistritoNegocio') AS tipo_origen,
       a.filas_no_numericas, a.ejemplo_1, a.ejemplo_2
FROM (SELECT SUM(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN 1 ELSE 0 END) AS filas_no_numericas,
             MIN(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_1,
             MAX(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_2
      FROM (SELECT NULLIF(LTRIM(RTRIM(CONVERT(NVARCHAR(200), [DistritoNegocio]))), N'') AS v
            FROM Desarrollo.dbo.compartamos_individual WITH (NOLOCK)) x) a
UNION ALL
SELECT N'Calificación Inicial' AS columna_historico, N'Calificación Inicial' AS columna_origen,
       (SELECT TOP 1 ty.name FROM Compartamos_Vigente_Cobranzas.sys.columns c JOIN Compartamos_Vigente_Cobranzas.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Compartamos_Vigente_Cobranzas.dbo.HIST_COMPARTAMOS_INDIVIDUAL') AND c.name = N'Calificación Inicial') AS tipo_historico,
       (SELECT TOP 1 ty.name FROM Desarrollo.sys.columns c JOIN Desarrollo.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Desarrollo.dbo.compartamos_individual') AND c.name = N'Calificación Inicial') AS tipo_origen,
       a.filas_no_numericas, a.ejemplo_1, a.ejemplo_2
FROM (SELECT SUM(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN 1 ELSE 0 END) AS filas_no_numericas,
             MIN(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_1,
             MAX(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_2
      FROM (SELECT NULLIF(LTRIM(RTRIM(CONVERT(NVARCHAR(200), [Calificación Inicial]))), N'') AS v
            FROM Desarrollo.dbo.compartamos_individual WITH (NOLOCK)) x) a
UNION ALL
SELECT N'Saldo Capital por Cuenta' AS columna_historico, N'Saldo Capital por Cuenta' AS columna_origen,
       (SELECT TOP 1 ty.name FROM Compartamos_Vigente_Cobranzas.sys.columns c JOIN Compartamos_Vigente_Cobranzas.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Compartamos_Vigente_Cobranzas.dbo.HIST_COMPARTAMOS_INDIVIDUAL') AND c.name = N'Saldo Capital por Cuenta') AS tipo_historico,
       (SELECT TOP 1 ty.name FROM Desarrollo.sys.columns c JOIN Desarrollo.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Desarrollo.dbo.compartamos_individual') AND c.name = N'Saldo Capital por Cuenta') AS tipo_origen,
       a.filas_no_numericas, a.ejemplo_1, a.ejemplo_2
FROM (SELECT SUM(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN 1 ELSE 0 END) AS filas_no_numericas,
             MIN(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_1,
             MAX(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_2
      FROM (SELECT NULLIF(LTRIM(RTRIM(CONVERT(NVARCHAR(200), [Saldo Capital por Cuenta]))), N'') AS v
            FROM Desarrollo.dbo.compartamos_individual WITH (NOLOCK)) x) a
UNION ALL
SELECT N'Saldo Total x Cliente' AS columna_historico, N'Saldo Total x Cliente' AS columna_origen,
       (SELECT TOP 1 ty.name FROM Compartamos_Vigente_Cobranzas.sys.columns c JOIN Compartamos_Vigente_Cobranzas.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Compartamos_Vigente_Cobranzas.dbo.HIST_COMPARTAMOS_INDIVIDUAL') AND c.name = N'Saldo Total x Cliente') AS tipo_historico,
       (SELECT TOP 1 ty.name FROM Desarrollo.sys.columns c JOIN Desarrollo.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Desarrollo.dbo.compartamos_individual') AND c.name = N'Saldo Total x Cliente') AS tipo_origen,
       a.filas_no_numericas, a.ejemplo_1, a.ejemplo_2
FROM (SELECT SUM(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN 1 ELSE 0 END) AS filas_no_numericas,
             MIN(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_1,
             MAX(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_2
      FROM (SELECT NULLIF(LTRIM(RTRIM(CONVERT(NVARCHAR(200), [Saldo Total x Cliente]))), N'') AS v
            FROM Desarrollo.dbo.compartamos_individual WITH (NOLOCK)) x) a
UNION ALL
SELECT N'Dias Atraso' AS columna_historico, N'Dias Atraso' AS columna_origen,
       (SELECT TOP 1 ty.name FROM Compartamos_Vigente_Cobranzas.sys.columns c JOIN Compartamos_Vigente_Cobranzas.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Compartamos_Vigente_Cobranzas.dbo.HIST_COMPARTAMOS_INDIVIDUAL') AND c.name = N'Dias Atraso') AS tipo_historico,
       (SELECT TOP 1 ty.name FROM Desarrollo.sys.columns c JOIN Desarrollo.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Desarrollo.dbo.compartamos_individual') AND c.name = N'Dias Atraso') AS tipo_origen,
       a.filas_no_numericas, a.ejemplo_1, a.ejemplo_2
FROM (SELECT SUM(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN 1 ELSE 0 END) AS filas_no_numericas,
             MIN(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_1,
             MAX(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_2
      FROM (SELECT NULLIF(LTRIM(RTRIM(CONVERT(NVARCHAR(200), [Dias Atraso]))), N'') AS v
            FROM Desarrollo.dbo.compartamos_individual WITH (NOLOCK)) x) a
UNION ALL
SELECT N'Telefono1' AS columna_historico, N'Telefono1' AS columna_origen,
       (SELECT TOP 1 ty.name FROM Compartamos_Vigente_Cobranzas.sys.columns c JOIN Compartamos_Vigente_Cobranzas.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Compartamos_Vigente_Cobranzas.dbo.HIST_COMPARTAMOS_INDIVIDUAL') AND c.name = N'Telefono1') AS tipo_historico,
       (SELECT TOP 1 ty.name FROM Desarrollo.sys.columns c JOIN Desarrollo.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Desarrollo.dbo.compartamos_individual') AND c.name = N'Telefono1') AS tipo_origen,
       a.filas_no_numericas, a.ejemplo_1, a.ejemplo_2
FROM (SELECT SUM(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN 1 ELSE 0 END) AS filas_no_numericas,
             MIN(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_1,
             MAX(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_2
      FROM (SELECT NULLIF(LTRIM(RTRIM(CONVERT(NVARCHAR(200), [Telefono1]))), N'') AS v
            FROM Desarrollo.dbo.compartamos_individual WITH (NOLOCK)) x) a
UNION ALL
SELECT N'Telefono2' AS columna_historico, N'Telefono2' AS columna_origen,
       (SELECT TOP 1 ty.name FROM Compartamos_Vigente_Cobranzas.sys.columns c JOIN Compartamos_Vigente_Cobranzas.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Compartamos_Vigente_Cobranzas.dbo.HIST_COMPARTAMOS_INDIVIDUAL') AND c.name = N'Telefono2') AS tipo_historico,
       (SELECT TOP 1 ty.name FROM Desarrollo.sys.columns c JOIN Desarrollo.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Desarrollo.dbo.compartamos_individual') AND c.name = N'Telefono2') AS tipo_origen,
       a.filas_no_numericas, a.ejemplo_1, a.ejemplo_2
FROM (SELECT SUM(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN 1 ELSE 0 END) AS filas_no_numericas,
             MIN(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_1,
             MAX(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_2
      FROM (SELECT NULLIF(LTRIM(RTRIM(CONVERT(NVARCHAR(200), [Telefono2]))), N'') AS v
            FROM Desarrollo.dbo.compartamos_individual WITH (NOLOCK)) x) a
UNION ALL
SELECT N'MtoDesembolso' AS columna_historico, N'MtoDesembolso' AS columna_origen,
       (SELECT TOP 1 ty.name FROM Compartamos_Vigente_Cobranzas.sys.columns c JOIN Compartamos_Vigente_Cobranzas.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Compartamos_Vigente_Cobranzas.dbo.HIST_COMPARTAMOS_INDIVIDUAL') AND c.name = N'MtoDesembolso') AS tipo_historico,
       (SELECT TOP 1 ty.name FROM Desarrollo.sys.columns c JOIN Desarrollo.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Desarrollo.dbo.compartamos_individual') AND c.name = N'MtoDesembolso') AS tipo_origen,
       a.filas_no_numericas, a.ejemplo_1, a.ejemplo_2
FROM (SELECT SUM(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN 1 ELSE 0 END) AS filas_no_numericas,
             MIN(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_1,
             MAX(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_2
      FROM (SELECT NULLIF(LTRIM(RTRIM(CONVERT(NVARCHAR(200), [MtoDesembolso]))), N'') AS v
            FROM Desarrollo.dbo.compartamos_individual WITH (NOLOCK)) x) a
UNION ALL
SELECT N'Zona_Recuperaciones' AS columna_historico, N'Zona_Recuperaciones' AS columna_origen,
       (SELECT TOP 1 ty.name FROM Compartamos_Vigente_Cobranzas.sys.columns c JOIN Compartamos_Vigente_Cobranzas.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Compartamos_Vigente_Cobranzas.dbo.HIST_COMPARTAMOS_INDIVIDUAL') AND c.name = N'Zona_Recuperaciones') AS tipo_historico,
       (SELECT TOP 1 ty.name FROM Desarrollo.sys.columns c JOIN Desarrollo.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Desarrollo.dbo.compartamos_individual') AND c.name = N'Zona_Recuperaciones') AS tipo_origen,
       a.filas_no_numericas, a.ejemplo_1, a.ejemplo_2
FROM (SELECT SUM(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN 1 ELSE 0 END) AS filas_no_numericas,
             MIN(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_1,
             MAX(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_2
      FROM (SELECT NULLIF(LTRIM(RTRIM(CONVERT(NVARCHAR(200), [Zona_Recuperaciones]))), N'') AS v
            FROM Desarrollo.dbo.compartamos_individual WITH (NOLOCK)) x) a
UNION ALL
SELECT N'Zona_Cobex' AS columna_historico, N'Zona_Cobex' AS columna_origen,
       (SELECT TOP 1 ty.name FROM Compartamos_Vigente_Cobranzas.sys.columns c JOIN Compartamos_Vigente_Cobranzas.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Compartamos_Vigente_Cobranzas.dbo.HIST_COMPARTAMOS_INDIVIDUAL') AND c.name = N'Zona_Cobex') AS tipo_historico,
       (SELECT TOP 1 ty.name FROM Desarrollo.sys.columns c JOIN Desarrollo.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Desarrollo.dbo.compartamos_individual') AND c.name = N'Zona_Cobex') AS tipo_origen,
       a.filas_no_numericas, a.ejemplo_1, a.ejemplo_2
FROM (SELECT SUM(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN 1 ELSE 0 END) AS filas_no_numericas,
             MIN(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_1,
             MAX(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_2
      FROM (SELECT NULLIF(LTRIM(RTRIM(CONVERT(NVARCHAR(200), [Zona_Cobex]))), N'') AS v
            FROM Desarrollo.dbo.compartamos_individual WITH (NOLOCK)) x) a
UNION ALL
SELECT N'NumDoc' AS columna_historico, N'NumDoc' AS columna_origen,
       (SELECT TOP 1 ty.name FROM Compartamos_Vigente_Cobranzas.sys.columns c JOIN Compartamos_Vigente_Cobranzas.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Compartamos_Vigente_Cobranzas.dbo.HIST_COMPARTAMOS_INDIVIDUAL') AND c.name = N'NumDoc') AS tipo_historico,
       (SELECT TOP 1 ty.name FROM Desarrollo.sys.columns c JOIN Desarrollo.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Desarrollo.dbo.compartamos_individual') AND c.name = N'NumDoc') AS tipo_origen,
       a.filas_no_numericas, a.ejemplo_1, a.ejemplo_2
FROM (SELECT SUM(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN 1 ELSE 0 END) AS filas_no_numericas,
             MIN(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_1,
             MAX(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_2
      FROM (SELECT NULLIF(LTRIM(RTRIM(CONVERT(NVARCHAR(200), [NumDoc]))), N'') AS v
            FROM Desarrollo.dbo.compartamos_individual WITH (NOLOCK)) x) a
UNION ALL
SELECT N'Aval' AS columna_historico, N'Aval' AS columna_origen,
       (SELECT TOP 1 ty.name FROM Compartamos_Vigente_Cobranzas.sys.columns c JOIN Compartamos_Vigente_Cobranzas.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Compartamos_Vigente_Cobranzas.dbo.HIST_COMPARTAMOS_INDIVIDUAL') AND c.name = N'Aval') AS tipo_historico,
       (SELECT TOP 1 ty.name FROM Desarrollo.sys.columns c JOIN Desarrollo.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Desarrollo.dbo.compartamos_individual') AND c.name = N'Aval') AS tipo_origen,
       a.filas_no_numericas, a.ejemplo_1, a.ejemplo_2
FROM (SELECT SUM(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN 1 ELSE 0 END) AS filas_no_numericas,
             MIN(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_1,
             MAX(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_2
      FROM (SELECT NULLIF(LTRIM(RTRIM(CONVERT(NVARCHAR(200), [Aval]))), N'') AS v
            FROM Desarrollo.dbo.compartamos_individual WITH (NOLOCK)) x) a
UNION ALL
SELECT N'DireccionAval' AS columna_historico, N'DireccionAval' AS columna_origen,
       (SELECT TOP 1 ty.name FROM Compartamos_Vigente_Cobranzas.sys.columns c JOIN Compartamos_Vigente_Cobranzas.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Compartamos_Vigente_Cobranzas.dbo.HIST_COMPARTAMOS_INDIVIDUAL') AND c.name = N'DireccionAval') AS tipo_historico,
       (SELECT TOP 1 ty.name FROM Desarrollo.sys.columns c JOIN Desarrollo.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Desarrollo.dbo.compartamos_individual') AND c.name = N'DireccionAval') AS tipo_origen,
       a.filas_no_numericas, a.ejemplo_1, a.ejemplo_2
FROM (SELECT SUM(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN 1 ELSE 0 END) AS filas_no_numericas,
             MIN(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_1,
             MAX(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_2
      FROM (SELECT NULLIF(LTRIM(RTRIM(CONVERT(NVARCHAR(200), [DireccionAval]))), N'') AS v
            FROM Desarrollo.dbo.compartamos_individual WITH (NOLOCK)) x) a
UNION ALL
SELECT N'DistritoAval' AS columna_historico, N'DistritoAval' AS columna_origen,
       (SELECT TOP 1 ty.name FROM Compartamos_Vigente_Cobranzas.sys.columns c JOIN Compartamos_Vigente_Cobranzas.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Compartamos_Vigente_Cobranzas.dbo.HIST_COMPARTAMOS_INDIVIDUAL') AND c.name = N'DistritoAval') AS tipo_historico,
       (SELECT TOP 1 ty.name FROM Desarrollo.sys.columns c JOIN Desarrollo.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Desarrollo.dbo.compartamos_individual') AND c.name = N'DistritoAval') AS tipo_origen,
       a.filas_no_numericas, a.ejemplo_1, a.ejemplo_2
FROM (SELECT SUM(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN 1 ELSE 0 END) AS filas_no_numericas,
             MIN(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_1,
             MAX(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_2
      FROM (SELECT NULLIF(LTRIM(RTRIM(CONVERT(NVARCHAR(200), [DistritoAval]))), N'') AS v
            FROM Desarrollo.dbo.compartamos_individual WITH (NOLOCK)) x) a
UNION ALL
SELECT N'Telefono Aval' AS columna_historico, N'Telefono Aval' AS columna_origen,
       (SELECT TOP 1 ty.name FROM Compartamos_Vigente_Cobranzas.sys.columns c JOIN Compartamos_Vigente_Cobranzas.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Compartamos_Vigente_Cobranzas.dbo.HIST_COMPARTAMOS_INDIVIDUAL') AND c.name = N'Telefono Aval') AS tipo_historico,
       (SELECT TOP 1 ty.name FROM Desarrollo.sys.columns c JOIN Desarrollo.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Desarrollo.dbo.compartamos_individual') AND c.name = N'Telefono Aval') AS tipo_origen,
       a.filas_no_numericas, a.ejemplo_1, a.ejemplo_2
FROM (SELECT SUM(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN 1 ELSE 0 END) AS filas_no_numericas,
             MIN(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_1,
             MAX(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_2
      FROM (SELECT NULLIF(LTRIM(RTRIM(CONVERT(NVARCHAR(200), [Telefono Aval]))), N'') AS v
            FROM Desarrollo.dbo.compartamos_individual WITH (NOLOCK)) x) a
UNION ALL
SELECT N'DNIAval' AS columna_historico, N'DNIAval' AS columna_origen,
       (SELECT TOP 1 ty.name FROM Compartamos_Vigente_Cobranzas.sys.columns c JOIN Compartamos_Vigente_Cobranzas.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Compartamos_Vigente_Cobranzas.dbo.HIST_COMPARTAMOS_INDIVIDUAL') AND c.name = N'DNIAval') AS tipo_historico,
       (SELECT TOP 1 ty.name FROM Desarrollo.sys.columns c JOIN Desarrollo.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Desarrollo.dbo.compartamos_individual') AND c.name = N'DNIAval') AS tipo_origen,
       a.filas_no_numericas, a.ejemplo_1, a.ejemplo_2
FROM (SELECT SUM(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN 1 ELSE 0 END) AS filas_no_numericas,
             MIN(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_1,
             MAX(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_2
      FROM (SELECT NULLIF(LTRIM(RTRIM(CONVERT(NVARCHAR(200), [DNIAval]))), N'') AS v
            FROM Desarrollo.dbo.compartamos_individual WITH (NOLOCK)) x) a
UNION ALL
SELECT N'Conyuge' AS columna_historico, N'Conyuge' AS columna_origen,
       (SELECT TOP 1 ty.name FROM Compartamos_Vigente_Cobranzas.sys.columns c JOIN Compartamos_Vigente_Cobranzas.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Compartamos_Vigente_Cobranzas.dbo.HIST_COMPARTAMOS_INDIVIDUAL') AND c.name = N'Conyuge') AS tipo_historico,
       (SELECT TOP 1 ty.name FROM Desarrollo.sys.columns c JOIN Desarrollo.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Desarrollo.dbo.compartamos_individual') AND c.name = N'Conyuge') AS tipo_origen,
       a.filas_no_numericas, a.ejemplo_1, a.ejemplo_2
FROM (SELECT SUM(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN 1 ELSE 0 END) AS filas_no_numericas,
             MIN(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_1,
             MAX(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_2
      FROM (SELECT NULLIF(LTRIM(RTRIM(CONVERT(NVARCHAR(200), [Conyuge]))), N'') AS v
            FROM Desarrollo.dbo.compartamos_individual WITH (NOLOCK)) x) a
UNION ALL
SELECT N'DNIConyuge' AS columna_historico, N'DNIConyuge' AS columna_origen,
       (SELECT TOP 1 ty.name FROM Compartamos_Vigente_Cobranzas.sys.columns c JOIN Compartamos_Vigente_Cobranzas.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Compartamos_Vigente_Cobranzas.dbo.HIST_COMPARTAMOS_INDIVIDUAL') AND c.name = N'DNIConyuge') AS tipo_historico,
       (SELECT TOP 1 ty.name FROM Desarrollo.sys.columns c JOIN Desarrollo.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Desarrollo.dbo.compartamos_individual') AND c.name = N'DNIConyuge') AS tipo_origen,
       a.filas_no_numericas, a.ejemplo_1, a.ejemplo_2
FROM (SELECT SUM(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN 1 ELSE 0 END) AS filas_no_numericas,
             MIN(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_1,
             MAX(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_2
      FROM (SELECT NULLIF(LTRIM(RTRIM(CONVERT(NVARCHAR(200), [DNIConyuge]))), N'') AS v
            FROM Desarrollo.dbo.compartamos_individual WITH (NOLOCK)) x) a
UNION ALL
SELECT N'Sexo' AS columna_historico, N'Sexo' AS columna_origen,
       (SELECT TOP 1 ty.name FROM Compartamos_Vigente_Cobranzas.sys.columns c JOIN Compartamos_Vigente_Cobranzas.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Compartamos_Vigente_Cobranzas.dbo.HIST_COMPARTAMOS_INDIVIDUAL') AND c.name = N'Sexo') AS tipo_historico,
       (SELECT TOP 1 ty.name FROM Desarrollo.sys.columns c JOIN Desarrollo.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Desarrollo.dbo.compartamos_individual') AND c.name = N'Sexo') AS tipo_origen,
       a.filas_no_numericas, a.ejemplo_1, a.ejemplo_2
FROM (SELECT SUM(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN 1 ELSE 0 END) AS filas_no_numericas,
             MIN(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_1,
             MAX(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_2
      FROM (SELECT NULLIF(LTRIM(RTRIM(CONVERT(NVARCHAR(200), [Sexo]))), N'') AS v
            FROM Desarrollo.dbo.compartamos_individual WITH (NOLOCK)) x) a
UNION ALL
SELECT N'Edad' AS columna_historico, N'Edad' AS columna_origen,
       (SELECT TOP 1 ty.name FROM Compartamos_Vigente_Cobranzas.sys.columns c JOIN Compartamos_Vigente_Cobranzas.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Compartamos_Vigente_Cobranzas.dbo.HIST_COMPARTAMOS_INDIVIDUAL') AND c.name = N'Edad') AS tipo_historico,
       (SELECT TOP 1 ty.name FROM Desarrollo.sys.columns c JOIN Desarrollo.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Desarrollo.dbo.compartamos_individual') AND c.name = N'Edad') AS tipo_origen,
       a.filas_no_numericas, a.ejemplo_1, a.ejemplo_2
FROM (SELECT SUM(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN 1 ELSE 0 END) AS filas_no_numericas,
             MIN(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_1,
             MAX(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_2
      FROM (SELECT NULLIF(LTRIM(RTRIM(CONVERT(NVARCHAR(200), [Edad]))), N'') AS v
            FROM Desarrollo.dbo.compartamos_individual WITH (NOLOCK)) x) a
UNION ALL
SELECT N'NroReprogramaciones' AS columna_historico, N'NroReprogramaciones' AS columna_origen,
       (SELECT TOP 1 ty.name FROM Compartamos_Vigente_Cobranzas.sys.columns c JOIN Compartamos_Vigente_Cobranzas.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Compartamos_Vigente_Cobranzas.dbo.HIST_COMPARTAMOS_INDIVIDUAL') AND c.name = N'NroReprogramaciones') AS tipo_historico,
       (SELECT TOP 1 ty.name FROM Desarrollo.sys.columns c JOIN Desarrollo.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Desarrollo.dbo.compartamos_individual') AND c.name = N'NroReprogramaciones') AS tipo_origen,
       a.filas_no_numericas, a.ejemplo_1, a.ejemplo_2
FROM (SELECT SUM(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN 1 ELSE 0 END) AS filas_no_numericas,
             MIN(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_1,
             MAX(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_2
      FROM (SELECT NULLIF(LTRIM(RTRIM(CONVERT(NVARCHAR(200), [NroReprogramaciones]))), N'') AS v
            FROM Desarrollo.dbo.compartamos_individual WITH (NOLOCK)) x) a
UNION ALL
SELECT N'FLG_ReprogramadoCheck' AS columna_historico, N'FLG_ReprogramadoCheck' AS columna_origen,
       (SELECT TOP 1 ty.name FROM Compartamos_Vigente_Cobranzas.sys.columns c JOIN Compartamos_Vigente_Cobranzas.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Compartamos_Vigente_Cobranzas.dbo.HIST_COMPARTAMOS_INDIVIDUAL') AND c.name = N'FLG_ReprogramadoCheck') AS tipo_historico,
       (SELECT TOP 1 ty.name FROM Desarrollo.sys.columns c JOIN Desarrollo.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Desarrollo.dbo.compartamos_individual') AND c.name = N'FLG_ReprogramadoCheck') AS tipo_origen,
       a.filas_no_numericas, a.ejemplo_1, a.ejemplo_2
FROM (SELECT SUM(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN 1 ELSE 0 END) AS filas_no_numericas,
             MIN(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_1,
             MAX(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_2
      FROM (SELECT NULLIF(LTRIM(RTRIM(CONVERT(NVARCHAR(200), [FLG_ReprogramadoCheck]))), N'') AS v
            FROM Desarrollo.dbo.compartamos_individual WITH (NOLOCK)) x) a
UNION ALL
SELECT N'FLG_CliRef' AS columna_historico, N'FLG_CliRef' AS columna_origen,
       (SELECT TOP 1 ty.name FROM Compartamos_Vigente_Cobranzas.sys.columns c JOIN Compartamos_Vigente_Cobranzas.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Compartamos_Vigente_Cobranzas.dbo.HIST_COMPARTAMOS_INDIVIDUAL') AND c.name = N'FLG_CliRef') AS tipo_historico,
       (SELECT TOP 1 ty.name FROM Desarrollo.sys.columns c JOIN Desarrollo.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Desarrollo.dbo.compartamos_individual') AND c.name = N'FLG_CliRef') AS tipo_origen,
       a.filas_no_numericas, a.ejemplo_1, a.ejemplo_2
FROM (SELECT SUM(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN 1 ELSE 0 END) AS filas_no_numericas,
             MIN(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_1,
             MAX(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_2
      FROM (SELECT NULLIF(LTRIM(RTRIM(CONVERT(NVARCHAR(200), [FLG_CliRef]))), N'') AS v
            FROM Desarrollo.dbo.compartamos_individual WITH (NOLOCK)) x) a
UNION ALL
SELECT N'REAC_FAE' AS columna_historico, N'REAC_FAE' AS columna_origen,
       (SELECT TOP 1 ty.name FROM Compartamos_Vigente_Cobranzas.sys.columns c JOIN Compartamos_Vigente_Cobranzas.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Compartamos_Vigente_Cobranzas.dbo.HIST_COMPARTAMOS_INDIVIDUAL') AND c.name = N'REAC_FAE') AS tipo_historico,
       (SELECT TOP 1 ty.name FROM Desarrollo.sys.columns c JOIN Desarrollo.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Desarrollo.dbo.compartamos_individual') AND c.name = N'REAC_FAE') AS tipo_origen,
       a.filas_no_numericas, a.ejemplo_1, a.ejemplo_2
FROM (SELECT SUM(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN 1 ELSE 0 END) AS filas_no_numericas,
             MIN(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_1,
             MAX(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_2
      FROM (SELECT NULLIF(LTRIM(RTRIM(CONVERT(NVARCHAR(200), [REAC_FAE]))), N'') AS v
            FROM Desarrollo.dbo.compartamos_individual WITH (NOLOCK)) x) a
UNION ALL
SELECT N'Tipo_Congelamiento' AS columna_historico, N'Tipo_Congelamiento' AS columna_origen,
       (SELECT TOP 1 ty.name FROM Compartamos_Vigente_Cobranzas.sys.columns c JOIN Compartamos_Vigente_Cobranzas.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Compartamos_Vigente_Cobranzas.dbo.HIST_COMPARTAMOS_INDIVIDUAL') AND c.name = N'Tipo_Congelamiento') AS tipo_historico,
       (SELECT TOP 1 ty.name FROM Desarrollo.sys.columns c JOIN Desarrollo.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Desarrollo.dbo.compartamos_individual') AND c.name = N'Tipo_Congelamiento') AS tipo_origen,
       a.filas_no_numericas, a.ejemplo_1, a.ejemplo_2
FROM (SELECT SUM(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN 1 ELSE 0 END) AS filas_no_numericas,
             MIN(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_1,
             MAX(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_2
      FROM (SELECT NULLIF(LTRIM(RTRIM(CONVERT(NVARCHAR(200), [Tipo_Congelamiento]))), N'') AS v
            FROM Desarrollo.dbo.compartamos_individual WITH (NOLOCK)) x) a
UNION ALL
SELECT N'Rubro' AS columna_historico, N'Rubro' AS columna_origen,
       (SELECT TOP 1 ty.name FROM Compartamos_Vigente_Cobranzas.sys.columns c JOIN Compartamos_Vigente_Cobranzas.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Compartamos_Vigente_Cobranzas.dbo.HIST_COMPARTAMOS_INDIVIDUAL') AND c.name = N'Rubro') AS tipo_historico,
       (SELECT TOP 1 ty.name FROM Desarrollo.sys.columns c JOIN Desarrollo.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Desarrollo.dbo.compartamos_individual') AND c.name = N'Rubro') AS tipo_origen,
       a.filas_no_numericas, a.ejemplo_1, a.ejemplo_2
FROM (SELECT SUM(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN 1 ELSE 0 END) AS filas_no_numericas,
             MIN(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_1,
             MAX(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_2
      FROM (SELECT NULLIF(LTRIM(RTRIM(CONVERT(NVARCHAR(200), [Rubro]))), N'') AS v
            FROM Desarrollo.dbo.compartamos_individual WITH (NOLOCK)) x) a
UNION ALL
SELECT N'ActividadEconómica' AS columna_historico, N'ActividadEconómica' AS columna_origen,
       (SELECT TOP 1 ty.name FROM Compartamos_Vigente_Cobranzas.sys.columns c JOIN Compartamos_Vigente_Cobranzas.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Compartamos_Vigente_Cobranzas.dbo.HIST_COMPARTAMOS_INDIVIDUAL') AND c.name = N'ActividadEconómica') AS tipo_historico,
       (SELECT TOP 1 ty.name FROM Desarrollo.sys.columns c JOIN Desarrollo.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Desarrollo.dbo.compartamos_individual') AND c.name = N'ActividadEconómica') AS tipo_origen,
       a.filas_no_numericas, a.ejemplo_1, a.ejemplo_2
FROM (SELECT SUM(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN 1 ELSE 0 END) AS filas_no_numericas,
             MIN(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_1,
             MAX(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_2
      FROM (SELECT NULLIF(LTRIM(RTRIM(CONVERT(NVARCHAR(200), [ActividadEconómica]))), N'') AS v
            FROM Desarrollo.dbo.compartamos_individual WITH (NOLOCK)) x) a
UNION ALL
SELECT N'Segmentov' AS columna_historico, N'Segmentov' AS columna_origen,
       (SELECT TOP 1 ty.name FROM Compartamos_Vigente_Cobranzas.sys.columns c JOIN Compartamos_Vigente_Cobranzas.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Compartamos_Vigente_Cobranzas.dbo.HIST_COMPARTAMOS_INDIVIDUAL') AND c.name = N'Segmentov') AS tipo_historico,
       (SELECT TOP 1 ty.name FROM Desarrollo.sys.columns c JOIN Desarrollo.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Desarrollo.dbo.compartamos_individual') AND c.name = N'Segmentov') AS tipo_origen,
       a.filas_no_numericas, a.ejemplo_1, a.ejemplo_2
FROM (SELECT SUM(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN 1 ELSE 0 END) AS filas_no_numericas,
             MIN(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_1,
             MAX(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_2
      FROM (SELECT NULLIF(LTRIM(RTRIM(CONVERT(NVARCHAR(200), [Segmentov]))), N'') AS v
            FROM Desarrollo.dbo.compartamos_individual WITH (NOLOCK)) x) a
UNION ALL
SELECT N'TipoReprog' AS columna_historico, N'TipoReprog' AS columna_origen,
       (SELECT TOP 1 ty.name FROM Compartamos_Vigente_Cobranzas.sys.columns c JOIN Compartamos_Vigente_Cobranzas.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Compartamos_Vigente_Cobranzas.dbo.HIST_COMPARTAMOS_INDIVIDUAL') AND c.name = N'TipoReprog') AS tipo_historico,
       (SELECT TOP 1 ty.name FROM Desarrollo.sys.columns c JOIN Desarrollo.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Desarrollo.dbo.compartamos_individual') AND c.name = N'TipoReprog') AS tipo_origen,
       a.filas_no_numericas, a.ejemplo_1, a.ejemplo_2
FROM (SELECT SUM(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN 1 ELSE 0 END) AS filas_no_numericas,
             MIN(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_1,
             MAX(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_2
      FROM (SELECT NULLIF(LTRIM(RTRIM(CONVERT(NVARCHAR(200), [TipoReprog]))), N'') AS v
            FROM Desarrollo.dbo.compartamos_individual WITH (NOLOCK)) x) a
UNION ALL
SELECT N'Calif_Provisiones' AS columna_historico, N'Calif_Provisiones' AS columna_origen,
       (SELECT TOP 1 ty.name FROM Compartamos_Vigente_Cobranzas.sys.columns c JOIN Compartamos_Vigente_Cobranzas.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Compartamos_Vigente_Cobranzas.dbo.HIST_COMPARTAMOS_INDIVIDUAL') AND c.name = N'Calif_Provisiones') AS tipo_historico,
       (SELECT TOP 1 ty.name FROM Desarrollo.sys.columns c JOIN Desarrollo.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Desarrollo.dbo.compartamos_individual') AND c.name = N'Calif_Provisiones') AS tipo_origen,
       a.filas_no_numericas, a.ejemplo_1, a.ejemplo_2
FROM (SELECT SUM(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN 1 ELSE 0 END) AS filas_no_numericas,
             MIN(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_1,
             MAX(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_2
      FROM (SELECT NULLIF(LTRIM(RTRIM(CONVERT(NVARCHAR(200), [Calif_Provisiones]))), N'') AS v
            FROM Desarrollo.dbo.compartamos_individual WITH (NOLOCK)) x) a
UNION ALL
SELECT N'CCALINT' AS columna_historico, N'CCALINT' AS columna_origen,
       (SELECT TOP 1 ty.name FROM Compartamos_Vigente_Cobranzas.sys.columns c JOIN Compartamos_Vigente_Cobranzas.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Compartamos_Vigente_Cobranzas.dbo.HIST_COMPARTAMOS_INDIVIDUAL') AND c.name = N'CCALINT') AS tipo_historico,
       (SELECT TOP 1 ty.name FROM Desarrollo.sys.columns c JOIN Desarrollo.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Desarrollo.dbo.compartamos_individual') AND c.name = N'CCALINT') AS tipo_origen,
       a.filas_no_numericas, a.ejemplo_1, a.ejemplo_2
FROM (SELECT SUM(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN 1 ELSE 0 END) AS filas_no_numericas,
             MIN(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_1,
             MAX(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_2
      FROM (SELECT NULLIF(LTRIM(RTRIM(CONVERT(NVARCHAR(200), [CCALINT]))), N'') AS v
            FROM Desarrollo.dbo.compartamos_individual WITH (NOLOCK)) x) a
UNION ALL
SELECT N'Calif_Cronograma' AS columna_historico, N'Calif_Cronograma' AS columna_origen,
       (SELECT TOP 1 ty.name FROM Compartamos_Vigente_Cobranzas.sys.columns c JOIN Compartamos_Vigente_Cobranzas.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Compartamos_Vigente_Cobranzas.dbo.HIST_COMPARTAMOS_INDIVIDUAL') AND c.name = N'Calif_Cronograma') AS tipo_historico,
       (SELECT TOP 1 ty.name FROM Desarrollo.sys.columns c JOIN Desarrollo.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Desarrollo.dbo.compartamos_individual') AND c.name = N'Calif_Cronograma') AS tipo_origen,
       a.filas_no_numericas, a.ejemplo_1, a.ejemplo_2
FROM (SELECT SUM(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN 1 ELSE 0 END) AS filas_no_numericas,
             MIN(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_1,
             MAX(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_2
      FROM (SELECT NULLIF(LTRIM(RTRIM(CONVERT(NVARCHAR(200), [Calif_Cronograma]))), N'') AS v
            FROM Desarrollo.dbo.compartamos_individual WITH (NOLOCK)) x) a
UNION ALL
SELECT N'SCORE_RIESGOS' AS columna_historico, N'SCORE_RIESGOS' AS columna_origen,
       (SELECT TOP 1 ty.name FROM Compartamos_Vigente_Cobranzas.sys.columns c JOIN Compartamos_Vigente_Cobranzas.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Compartamos_Vigente_Cobranzas.dbo.HIST_COMPARTAMOS_INDIVIDUAL') AND c.name = N'SCORE_RIESGOS') AS tipo_historico,
       (SELECT TOP 1 ty.name FROM Desarrollo.sys.columns c JOIN Desarrollo.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Desarrollo.dbo.compartamos_individual') AND c.name = N'SCORE_RIESGOS') AS tipo_origen,
       a.filas_no_numericas, a.ejemplo_1, a.ejemplo_2
FROM (SELECT SUM(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN 1 ELSE 0 END) AS filas_no_numericas,
             MIN(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_1,
             MAX(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_2
      FROM (SELECT NULLIF(LTRIM(RTRIM(CONVERT(NVARCHAR(200), [SCORE_RIESGOS]))), N'') AS v
            FROM Desarrollo.dbo.compartamos_individual WITH (NOLOCK)) x) a
UNION ALL
SELECT N'SCORE_RIESGOS_ACUM' AS columna_historico, N'SCORE_RIESGOS_ACUM' AS columna_origen,
       (SELECT TOP 1 ty.name FROM Compartamos_Vigente_Cobranzas.sys.columns c JOIN Compartamos_Vigente_Cobranzas.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Compartamos_Vigente_Cobranzas.dbo.HIST_COMPARTAMOS_INDIVIDUAL') AND c.name = N'SCORE_RIESGOS_ACUM') AS tipo_historico,
       (SELECT TOP 1 ty.name FROM Desarrollo.sys.columns c JOIN Desarrollo.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Desarrollo.dbo.compartamos_individual') AND c.name = N'SCORE_RIESGOS_ACUM') AS tipo_origen,
       a.filas_no_numericas, a.ejemplo_1, a.ejemplo_2
FROM (SELECT SUM(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN 1 ELSE 0 END) AS filas_no_numericas,
             MIN(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_1,
             MAX(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_2
      FROM (SELECT NULLIF(LTRIM(RTRIM(CONVERT(NVARCHAR(200), [SCORE_RIESGOS_ACUM]))), N'') AS v
            FROM Desarrollo.dbo.compartamos_individual WITH (NOLOCK)) x) a
UNION ALL
SELECT N'FLG_Recuperaciones' AS columna_historico, N'FLG_Recuperaciones' AS columna_origen,
       (SELECT TOP 1 ty.name FROM Compartamos_Vigente_Cobranzas.sys.columns c JOIN Compartamos_Vigente_Cobranzas.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Compartamos_Vigente_Cobranzas.dbo.HIST_COMPARTAMOS_INDIVIDUAL') AND c.name = N'FLG_Recuperaciones') AS tipo_historico,
       (SELECT TOP 1 ty.name FROM Desarrollo.sys.columns c JOIN Desarrollo.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Desarrollo.dbo.compartamos_individual') AND c.name = N'FLG_Recuperaciones') AS tipo_origen,
       a.filas_no_numericas, a.ejemplo_1, a.ejemplo_2
FROM (SELECT SUM(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN 1 ELSE 0 END) AS filas_no_numericas,
             MIN(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_1,
             MAX(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_2
      FROM (SELECT NULLIF(LTRIM(RTRIM(CONVERT(NVARCHAR(200), [FLG_Recuperaciones]))), N'') AS v
            FROM Desarrollo.dbo.compartamos_individual WITH (NOLOCK)) x) a
UNION ALL
SELECT N'tipcartera' AS columna_historico, N'tipcartera' AS columna_origen,
       (SELECT TOP 1 ty.name FROM Compartamos_Vigente_Cobranzas.sys.columns c JOIN Compartamos_Vigente_Cobranzas.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Compartamos_Vigente_Cobranzas.dbo.HIST_COMPARTAMOS_INDIVIDUAL') AND c.name = N'tipcartera') AS tipo_historico,
       (SELECT TOP 1 ty.name FROM Desarrollo.sys.columns c JOIN Desarrollo.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Desarrollo.dbo.compartamos_individual') AND c.name = N'tipcartera') AS tipo_origen,
       a.filas_no_numericas, a.ejemplo_1, a.ejemplo_2
FROM (SELECT SUM(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN 1 ELSE 0 END) AS filas_no_numericas,
             MIN(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_1,
             MAX(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_2
      FROM (SELECT NULLIF(LTRIM(RTRIM(CONVERT(NVARCHAR(200), [tipcartera]))), N'') AS v
            FROM Desarrollo.dbo.compartamos_individual WITH (NOLOCK)) x) a
UNION ALL
SELECT N'CalifCta' AS columna_historico, N'CalifCta' AS columna_origen,
       (SELECT TOP 1 ty.name FROM Compartamos_Vigente_Cobranzas.sys.columns c JOIN Compartamos_Vigente_Cobranzas.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Compartamos_Vigente_Cobranzas.dbo.HIST_COMPARTAMOS_INDIVIDUAL') AND c.name = N'CalifCta') AS tipo_historico,
       (SELECT TOP 1 ty.name FROM Desarrollo.sys.columns c JOIN Desarrollo.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Desarrollo.dbo.compartamos_individual') AND c.name = N'CalifCta') AS tipo_origen,
       a.filas_no_numericas, a.ejemplo_1, a.ejemplo_2
FROM (SELECT SUM(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN 1 ELSE 0 END) AS filas_no_numericas,
             MIN(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_1,
             MAX(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_2
      FROM (SELECT NULLIF(LTRIM(RTRIM(CONVERT(NVARCHAR(200), [CalifCta]))), N'') AS v
            FROM Desarrollo.dbo.compartamos_individual WITH (NOLOCK)) x) a
UNION ALL
SELECT N'Nivel_A' AS columna_historico, N'Nivel_A' AS columna_origen,
       (SELECT TOP 1 ty.name FROM Compartamos_Vigente_Cobranzas.sys.columns c JOIN Compartamos_Vigente_Cobranzas.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Compartamos_Vigente_Cobranzas.dbo.HIST_COMPARTAMOS_INDIVIDUAL') AND c.name = N'Nivel_A') AS tipo_historico,
       (SELECT TOP 1 ty.name FROM Desarrollo.sys.columns c JOIN Desarrollo.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Desarrollo.dbo.compartamos_individual') AND c.name = N'Nivel_A') AS tipo_origen,
       a.filas_no_numericas, a.ejemplo_1, a.ejemplo_2
FROM (SELECT SUM(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN 1 ELSE 0 END) AS filas_no_numericas,
             MIN(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_1,
             MAX(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_2
      FROM (SELECT NULLIF(LTRIM(RTRIM(CONVERT(NVARCHAR(200), [Nivel_A]))), N'') AS v
            FROM Desarrollo.dbo.compartamos_individual WITH (NOLOCK)) x) a
UNION ALL
SELECT N'Producto' AS columna_historico, N'Producto' AS columna_origen,
       (SELECT TOP 1 ty.name FROM Compartamos_Vigente_Cobranzas.sys.columns c JOIN Compartamos_Vigente_Cobranzas.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Compartamos_Vigente_Cobranzas.dbo.HIST_COMPARTAMOS_INDIVIDUAL') AND c.name = N'Producto') AS tipo_historico,
       (SELECT TOP 1 ty.name FROM Desarrollo.sys.columns c JOIN Desarrollo.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Desarrollo.dbo.compartamos_individual') AND c.name = N'Producto') AS tipo_origen,
       a.filas_no_numericas, a.ejemplo_1, a.ejemplo_2
FROM (SELECT SUM(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN 1 ELSE 0 END) AS filas_no_numericas,
             MIN(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_1,
             MAX(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_2
      FROM (SELECT NULLIF(LTRIM(RTRIM(CONVERT(NVARCHAR(200), [Producto]))), N'') AS v
            FROM Desarrollo.dbo.compartamos_individual WITH (NOLOCK)) x) a
UNION ALL
SELECT N'ASESORNEGOCIO' AS columna_historico, N'ASESORNEGOCIO' AS columna_origen,
       (SELECT TOP 1 ty.name FROM Compartamos_Vigente_Cobranzas.sys.columns c JOIN Compartamos_Vigente_Cobranzas.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Compartamos_Vigente_Cobranzas.dbo.HIST_COMPARTAMOS_INDIVIDUAL') AND c.name = N'ASESORNEGOCIO') AS tipo_historico,
       (SELECT TOP 1 ty.name FROM Desarrollo.sys.columns c JOIN Desarrollo.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Desarrollo.dbo.compartamos_individual') AND c.name = N'ASESORNEGOCIO') AS tipo_origen,
       a.filas_no_numericas, a.ejemplo_1, a.ejemplo_2
FROM (SELECT SUM(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN 1 ELSE 0 END) AS filas_no_numericas,
             MIN(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_1,
             MAX(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_2
      FROM (SELECT NULLIF(LTRIM(RTRIM(CONVERT(NVARCHAR(200), [ASESORNEGOCIO]))), N'') AS v
            FROM Desarrollo.dbo.compartamos_individual WITH (NOLOCK)) x) a
UNION ALL
SELECT N'Cuota_Atrasada_CAP' AS columna_historico, N'Cuota_Atrasada_CAP' AS columna_origen,
       (SELECT TOP 1 ty.name FROM Compartamos_Vigente_Cobranzas.sys.columns c JOIN Compartamos_Vigente_Cobranzas.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Compartamos_Vigente_Cobranzas.dbo.HIST_COMPARTAMOS_INDIVIDUAL') AND c.name = N'Cuota_Atrasada_CAP') AS tipo_historico,
       (SELECT TOP 1 ty.name FROM Desarrollo.sys.columns c JOIN Desarrollo.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Desarrollo.dbo.compartamos_individual') AND c.name = N'Cuota_Atrasada_CAP') AS tipo_origen,
       a.filas_no_numericas, a.ejemplo_1, a.ejemplo_2
FROM (SELECT SUM(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN 1 ELSE 0 END) AS filas_no_numericas,
             MIN(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_1,
             MAX(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_2
      FROM (SELECT NULLIF(LTRIM(RTRIM(CONVERT(NVARCHAR(200), [Cuota_Atrasada_CAP]))), N'') AS v
            FROM Desarrollo.dbo.compartamos_individual WITH (NOLOCK)) x) a
UNION ALL
SELECT N'Cuota_Atrasada' AS columna_historico, N'Cuota_Atrasada' AS columna_origen,
       (SELECT TOP 1 ty.name FROM Compartamos_Vigente_Cobranzas.sys.columns c JOIN Compartamos_Vigente_Cobranzas.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Compartamos_Vigente_Cobranzas.dbo.HIST_COMPARTAMOS_INDIVIDUAL') AND c.name = N'Cuota_Atrasada') AS tipo_historico,
       (SELECT TOP 1 ty.name FROM Desarrollo.sys.columns c JOIN Desarrollo.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Desarrollo.dbo.compartamos_individual') AND c.name = N'Cuota_Atrasada') AS tipo_origen,
       a.filas_no_numericas, a.ejemplo_1, a.ejemplo_2
FROM (SELECT SUM(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN 1 ELSE 0 END) AS filas_no_numericas,
             MIN(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_1,
             MAX(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_2
      FROM (SELECT NULLIF(LTRIM(RTRIM(CONVERT(NVARCHAR(200), [Cuota_Atrasada]))), N'') AS v
            FROM Desarrollo.dbo.compartamos_individual WITH (NOLOCK)) x) a
UNION ALL
SELECT N'NROCUOTAS' AS columna_historico, N'NROCUOTAS' AS columna_origen,
       (SELECT TOP 1 ty.name FROM Compartamos_Vigente_Cobranzas.sys.columns c JOIN Compartamos_Vigente_Cobranzas.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Compartamos_Vigente_Cobranzas.dbo.HIST_COMPARTAMOS_INDIVIDUAL') AND c.name = N'NROCUOTAS') AS tipo_historico,
       (SELECT TOP 1 ty.name FROM Desarrollo.sys.columns c JOIN Desarrollo.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Desarrollo.dbo.compartamos_individual') AND c.name = N'NROCUOTAS') AS tipo_origen,
       a.filas_no_numericas, a.ejemplo_1, a.ejemplo_2
FROM (SELECT SUM(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN 1 ELSE 0 END) AS filas_no_numericas,
             MIN(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_1,
             MAX(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_2
      FROM (SELECT NULLIF(LTRIM(RTRIM(CONVERT(NVARCHAR(200), [NROCUOTAS]))), N'') AS v
            FROM Desarrollo.dbo.compartamos_individual WITH (NOLOCK)) x) a
UNION ALL
SELECT N'NROCUOTASPAGADAS' AS columna_historico, N'NROCUOTASPAGADAS' AS columna_origen,
       (SELECT TOP 1 ty.name FROM Compartamos_Vigente_Cobranzas.sys.columns c JOIN Compartamos_Vigente_Cobranzas.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Compartamos_Vigente_Cobranzas.dbo.HIST_COMPARTAMOS_INDIVIDUAL') AND c.name = N'NROCUOTASPAGADAS') AS tipo_historico,
       (SELECT TOP 1 ty.name FROM Desarrollo.sys.columns c JOIN Desarrollo.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Desarrollo.dbo.compartamos_individual') AND c.name = N'NROCUOTASPAGADAS') AS tipo_origen,
       a.filas_no_numericas, a.ejemplo_1, a.ejemplo_2
FROM (SELECT SUM(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN 1 ELSE 0 END) AS filas_no_numericas,
             MIN(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_1,
             MAX(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_2
      FROM (SELECT NULLIF(LTRIM(RTRIM(CONVERT(NVARCHAR(200), [NROCUOTASPAGADAS]))), N'') AS v
            FROM Desarrollo.dbo.compartamos_individual WITH (NOLOCK)) x) a
UNION ALL
SELECT N'Camp1Cuota%' AS columna_historico, N'Camp1Cuota%' AS columna_origen,
       (SELECT TOP 1 ty.name FROM Compartamos_Vigente_Cobranzas.sys.columns c JOIN Compartamos_Vigente_Cobranzas.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Compartamos_Vigente_Cobranzas.dbo.HIST_COMPARTAMOS_INDIVIDUAL') AND c.name = N'Camp1Cuota%') AS tipo_historico,
       (SELECT TOP 1 ty.name FROM Desarrollo.sys.columns c JOIN Desarrollo.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Desarrollo.dbo.compartamos_individual') AND c.name = N'Camp1Cuota%') AS tipo_origen,
       a.filas_no_numericas, a.ejemplo_1, a.ejemplo_2
FROM (SELECT SUM(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN 1 ELSE 0 END) AS filas_no_numericas,
             MIN(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_1,
             MAX(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_2
      FROM (SELECT NULLIF(LTRIM(RTRIM(CONVERT(NVARCHAR(200), [Camp1Cuota%]))), N'') AS v
            FROM Desarrollo.dbo.compartamos_individual WITH (NOLOCK)) x) a
UNION ALL
SELECT N'Camp2Cuota%' AS columna_historico, N'Camp2Cuota%' AS columna_origen,
       (SELECT TOP 1 ty.name FROM Compartamos_Vigente_Cobranzas.sys.columns c JOIN Compartamos_Vigente_Cobranzas.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Compartamos_Vigente_Cobranzas.dbo.HIST_COMPARTAMOS_INDIVIDUAL') AND c.name = N'Camp2Cuota%') AS tipo_historico,
       (SELECT TOP 1 ty.name FROM Desarrollo.sys.columns c JOIN Desarrollo.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Desarrollo.dbo.compartamos_individual') AND c.name = N'Camp2Cuota%') AS tipo_origen,
       a.filas_no_numericas, a.ejemplo_1, a.ejemplo_2
FROM (SELECT SUM(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN 1 ELSE 0 END) AS filas_no_numericas,
             MIN(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_1,
             MAX(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_2
      FROM (SELECT NULLIF(LTRIM(RTRIM(CONVERT(NVARCHAR(200), [Camp2Cuota%]))), N'') AS v
            FROM Desarrollo.dbo.compartamos_individual WITH (NOLOCK)) x) a
UNION ALL
SELECT N'Camp3Cuota%' AS columna_historico, N'Camp3Cuota%' AS columna_origen,
       (SELECT TOP 1 ty.name FROM Compartamos_Vigente_Cobranzas.sys.columns c JOIN Compartamos_Vigente_Cobranzas.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Compartamos_Vigente_Cobranzas.dbo.HIST_COMPARTAMOS_INDIVIDUAL') AND c.name = N'Camp3Cuota%') AS tipo_historico,
       (SELECT TOP 1 ty.name FROM Desarrollo.sys.columns c JOIN Desarrollo.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Desarrollo.dbo.compartamos_individual') AND c.name = N'Camp3Cuota%') AS tipo_origen,
       a.filas_no_numericas, a.ejemplo_1, a.ejemplo_2
FROM (SELECT SUM(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN 1 ELSE 0 END) AS filas_no_numericas,
             MIN(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_1,
             MAX(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_2
      FROM (SELECT NULLIF(LTRIM(RTRIM(CONVERT(NVARCHAR(200), [Camp3Cuota%]))), N'') AS v
            FROM Desarrollo.dbo.compartamos_individual WITH (NOLOCK)) x) a
UNION ALL
SELECT N'Camp4Cuota%' AS columna_historico, N'Camp4Cuota%' AS columna_origen,
       (SELECT TOP 1 ty.name FROM Compartamos_Vigente_Cobranzas.sys.columns c JOIN Compartamos_Vigente_Cobranzas.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Compartamos_Vigente_Cobranzas.dbo.HIST_COMPARTAMOS_INDIVIDUAL') AND c.name = N'Camp4Cuota%') AS tipo_historico,
       (SELECT TOP 1 ty.name FROM Desarrollo.sys.columns c JOIN Desarrollo.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Desarrollo.dbo.compartamos_individual') AND c.name = N'Camp4Cuota%') AS tipo_origen,
       a.filas_no_numericas, a.ejemplo_1, a.ejemplo_2
FROM (SELECT SUM(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN 1 ELSE 0 END) AS filas_no_numericas,
             MIN(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_1,
             MAX(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_2
      FROM (SELECT NULLIF(LTRIM(RTRIM(CONVERT(NVARCHAR(200), [Camp4Cuota%]))), N'') AS v
            FROM Desarrollo.dbo.compartamos_individual WITH (NOLOCK)) x) a
UNION ALL
SELECT N'Cancelación%' AS columna_historico, N'Cancelacion' AS columna_origen,
       (SELECT TOP 1 ty.name FROM Compartamos_Vigente_Cobranzas.sys.columns c JOIN Compartamos_Vigente_Cobranzas.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Compartamos_Vigente_Cobranzas.dbo.HIST_COMPARTAMOS_INDIVIDUAL') AND c.name = N'Cancelación%') AS tipo_historico,
       (SELECT TOP 1 ty.name FROM Desarrollo.sys.columns c JOIN Desarrollo.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Desarrollo.dbo.compartamos_individual') AND c.name = N'Cancelacion') AS tipo_origen,
       a.filas_no_numericas, a.ejemplo_1, a.ejemplo_2
FROM (SELECT SUM(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN 1 ELSE 0 END) AS filas_no_numericas,
             MIN(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_1,
             MAX(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_2
      FROM (SELECT NULLIF(LTRIM(RTRIM(CONVERT(NVARCHAR(200), [Cancelacion]))), N'') AS v
            FROM Desarrollo.dbo.compartamos_individual WITH (NOLOCK)) x) a
UNION ALL
SELECT N'Campaña Final 1 Cuota' AS columna_historico, N'Campaña Final 1 Cuota' AS columna_origen,
       (SELECT TOP 1 ty.name FROM Compartamos_Vigente_Cobranzas.sys.columns c JOIN Compartamos_Vigente_Cobranzas.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Compartamos_Vigente_Cobranzas.dbo.HIST_COMPARTAMOS_INDIVIDUAL') AND c.name = N'Campaña Final 1 Cuota') AS tipo_historico,
       (SELECT TOP 1 ty.name FROM Desarrollo.sys.columns c JOIN Desarrollo.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Desarrollo.dbo.compartamos_individual') AND c.name = N'Campaña Final 1 Cuota') AS tipo_origen,
       a.filas_no_numericas, a.ejemplo_1, a.ejemplo_2
FROM (SELECT SUM(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN 1 ELSE 0 END) AS filas_no_numericas,
             MIN(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_1,
             MAX(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_2
      FROM (SELECT NULLIF(LTRIM(RTRIM(CONVERT(NVARCHAR(200), [Campaña Final 1 Cuota]))), N'') AS v
            FROM Desarrollo.dbo.compartamos_individual WITH (NOLOCK)) x) a
UNION ALL
SELECT N'Campaña Final 2 Cuota' AS columna_historico, N'Campaña Final 2 Cuota' AS columna_origen,
       (SELECT TOP 1 ty.name FROM Compartamos_Vigente_Cobranzas.sys.columns c JOIN Compartamos_Vigente_Cobranzas.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Compartamos_Vigente_Cobranzas.dbo.HIST_COMPARTAMOS_INDIVIDUAL') AND c.name = N'Campaña Final 2 Cuota') AS tipo_historico,
       (SELECT TOP 1 ty.name FROM Desarrollo.sys.columns c JOIN Desarrollo.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Desarrollo.dbo.compartamos_individual') AND c.name = N'Campaña Final 2 Cuota') AS tipo_origen,
       a.filas_no_numericas, a.ejemplo_1, a.ejemplo_2
FROM (SELECT SUM(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN 1 ELSE 0 END) AS filas_no_numericas,
             MIN(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_1,
             MAX(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_2
      FROM (SELECT NULLIF(LTRIM(RTRIM(CONVERT(NVARCHAR(200), [Campaña Final 2 Cuota]))), N'') AS v
            FROM Desarrollo.dbo.compartamos_individual WITH (NOLOCK)) x) a
UNION ALL
SELECT N'Campaña Final 3 Cuota' AS columna_historico, N'Campaña Final 3 Cuota' AS columna_origen,
       (SELECT TOP 1 ty.name FROM Compartamos_Vigente_Cobranzas.sys.columns c JOIN Compartamos_Vigente_Cobranzas.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Compartamos_Vigente_Cobranzas.dbo.HIST_COMPARTAMOS_INDIVIDUAL') AND c.name = N'Campaña Final 3 Cuota') AS tipo_historico,
       (SELECT TOP 1 ty.name FROM Desarrollo.sys.columns c JOIN Desarrollo.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Desarrollo.dbo.compartamos_individual') AND c.name = N'Campaña Final 3 Cuota') AS tipo_origen,
       a.filas_no_numericas, a.ejemplo_1, a.ejemplo_2
FROM (SELECT SUM(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN 1 ELSE 0 END) AS filas_no_numericas,
             MIN(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_1,
             MAX(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_2
      FROM (SELECT NULLIF(LTRIM(RTRIM(CONVERT(NVARCHAR(200), [Campaña Final 3 Cuota]))), N'') AS v
            FROM Desarrollo.dbo.compartamos_individual WITH (NOLOCK)) x) a
UNION ALL
SELECT N'Campaña Final 4 Cuota' AS columna_historico, N'Campaña Final 4 Cuota' AS columna_origen,
       (SELECT TOP 1 ty.name FROM Compartamos_Vigente_Cobranzas.sys.columns c JOIN Compartamos_Vigente_Cobranzas.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Compartamos_Vigente_Cobranzas.dbo.HIST_COMPARTAMOS_INDIVIDUAL') AND c.name = N'Campaña Final 4 Cuota') AS tipo_historico,
       (SELECT TOP 1 ty.name FROM Desarrollo.sys.columns c JOIN Desarrollo.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Desarrollo.dbo.compartamos_individual') AND c.name = N'Campaña Final 4 Cuota') AS tipo_origen,
       a.filas_no_numericas, a.ejemplo_1, a.ejemplo_2
FROM (SELECT SUM(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN 1 ELSE 0 END) AS filas_no_numericas,
             MIN(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_1,
             MAX(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_2
      FROM (SELECT NULLIF(LTRIM(RTRIM(CONVERT(NVARCHAR(200), [Campaña Final 4 Cuota]))), N'') AS v
            FROM Desarrollo.dbo.compartamos_individual WITH (NOLOCK)) x) a
UNION ALL
SELECT N'Cancelacion' AS columna_historico, N'Cancelacion' AS columna_origen,
       (SELECT TOP 1 ty.name FROM Compartamos_Vigente_Cobranzas.sys.columns c JOIN Compartamos_Vigente_Cobranzas.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Compartamos_Vigente_Cobranzas.dbo.HIST_COMPARTAMOS_INDIVIDUAL') AND c.name = N'Cancelacion') AS tipo_historico,
       (SELECT TOP 1 ty.name FROM Desarrollo.sys.columns c JOIN Desarrollo.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Desarrollo.dbo.compartamos_individual') AND c.name = N'Cancelacion') AS tipo_origen,
       a.filas_no_numericas, a.ejemplo_1, a.ejemplo_2
FROM (SELECT SUM(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN 1 ELSE 0 END) AS filas_no_numericas,
             MIN(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_1,
             MAX(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_2
      FROM (SELECT NULLIF(LTRIM(RTRIM(CONVERT(NVARCHAR(200), [Cancelacion]))), N'') AS v
            FROM Desarrollo.dbo.compartamos_individual WITH (NOLOCK)) x) a
UNION ALL
SELECT N'FLG_IMPULSO' AS columna_historico, N'FLG_IMPULSO' AS columna_origen,
       (SELECT TOP 1 ty.name FROM Compartamos_Vigente_Cobranzas.sys.columns c JOIN Compartamos_Vigente_Cobranzas.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Compartamos_Vigente_Cobranzas.dbo.HIST_COMPARTAMOS_INDIVIDUAL') AND c.name = N'FLG_IMPULSO') AS tipo_historico,
       (SELECT TOP 1 ty.name FROM Desarrollo.sys.columns c JOIN Desarrollo.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Desarrollo.dbo.compartamos_individual') AND c.name = N'FLG_IMPULSO') AS tipo_origen,
       a.filas_no_numericas, a.ejemplo_1, a.ejemplo_2
FROM (SELECT SUM(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN 1 ELSE 0 END) AS filas_no_numericas,
             MIN(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_1,
             MAX(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_2
      FROM (SELECT NULLIF(LTRIM(RTRIM(CONVERT(NVARCHAR(200), [FLG_IMPULSO]))), N'') AS v
            FROM Desarrollo.dbo.compartamos_individual WITH (NOLOCK)) x) a
UNION ALL
SELECT N'FLG_DOBLE SALTO' AS columna_historico, N'FLG_DOBLE SALTO' AS columna_origen,
       (SELECT TOP 1 ty.name FROM Compartamos_Vigente_Cobranzas.sys.columns c JOIN Compartamos_Vigente_Cobranzas.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Compartamos_Vigente_Cobranzas.dbo.HIST_COMPARTAMOS_INDIVIDUAL') AND c.name = N'FLG_DOBLE SALTO') AS tipo_historico,
       (SELECT TOP 1 ty.name FROM Desarrollo.sys.columns c JOIN Desarrollo.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Desarrollo.dbo.compartamos_individual') AND c.name = N'FLG_DOBLE SALTO') AS tipo_origen,
       a.filas_no_numericas, a.ejemplo_1, a.ejemplo_2
FROM (SELECT SUM(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN 1 ELSE 0 END) AS filas_no_numericas,
             MIN(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_1,
             MAX(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_2
      FROM (SELECT NULLIF(LTRIM(RTRIM(CONVERT(NVARCHAR(200), [FLG_DOBLE SALTO]))), N'') AS v
            FROM Desarrollo.dbo.compartamos_individual WITH (NOLOCK)) x) a
UNION ALL
SELECT N'META' AS columna_historico, N'META' AS columna_origen,
       (SELECT TOP 1 ty.name FROM Compartamos_Vigente_Cobranzas.sys.columns c JOIN Compartamos_Vigente_Cobranzas.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Compartamos_Vigente_Cobranzas.dbo.HIST_COMPARTAMOS_INDIVIDUAL') AND c.name = N'META') AS tipo_historico,
       (SELECT TOP 1 ty.name FROM Desarrollo.sys.columns c JOIN Desarrollo.sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID('Desarrollo.dbo.compartamos_individual') AND c.name = N'META') AS tipo_origen,
       a.filas_no_numericas, a.ejemplo_1, a.ejemplo_2
FROM (SELECT SUM(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN 1 ELSE 0 END) AS filas_no_numericas,
             MIN(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_1,
             MAX(CASE WHEN v IS NOT NULL AND TRY_CONVERT(float, v) IS NULL THEN v END) AS ejemplo_2
      FROM (SELECT NULLIF(LTRIM(RTRIM(CONVERT(NVARCHAR(200), [META]))), N'') AS v
            FROM Desarrollo.dbo.compartamos_individual WITH (NOLOCK)) x) a
)
SELECT *
FROM diagnostico
WHERE tipo_historico IN ('float', 'real', 'decimal', 'numeric', 'money', 'smallmoney', 'int', 'bigint', 'smallint', 'tinyint')
  AND filas_no_numericas > 0
ORDER BY filas_no_numericas DESC;
