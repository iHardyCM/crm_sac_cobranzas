/* =====================================================================================
   SCORE TELEFÓNICO · DIAGNÓSTICO 7 — dónde está el código de cliente y de operación del banco
   (solo lectura) · 14/11/2026

   Para qué: los Excel de segmentos del banco no traen DNI; traen el código de cliente del banco
   (CO_CLIENTE, COD_CLI, CtaCliente) o el de operación (Operacion, COD_PRE). Para cargarlos hay que
   saber, por cartera, en qué tabla de asignación están esos códigos junto al DNI.

   Busca en cada base columnas con esos nombres (y parecidos) y lista tabla o vista, columna y tipo.
   Guardar en tools\salidas\resultados_diagnostico_score_7.txt
   ===================================================================================== */
SET NOCOUNT ON;

DECLARE @patrones TABLE (p NVARCHAR(50));
INSERT INTO @patrones VALUES
    (N'%CO[_]CLIENTE%'), (N'%COD[_]CLI%'), (N'%CODCLIENTE%'), (N'%CTACLIENTE%'), (N'%CTA[_]CLIENTE%'),
    (N'%COD[_]PRE%'), (N'OPERACION'), (N'%CODOPERACION%'), (N'%NUMOPERACION%'), (N'%NRO[_]OPERACION%'),
    (N'%COD[_]OPERACION%'), (N'NRO[_]DOC'), (N'%DOCUMENTO%');

SELECT 'Desarrollo' AS base, s.name AS esquema, o.name AS objeto, o.type_desc AS tipo, c.name AS columna, t.name AS tipo_dato
FROM Desarrollo.sys.columns AS c
JOIN Desarrollo.sys.objects AS o ON o.object_id = c.object_id
JOIN Desarrollo.sys.schemas AS s ON s.schema_id = o.schema_id
JOIN Desarrollo.sys.types AS t ON t.user_type_id = c.user_type_id
WHERE o.type IN ('U', 'V') AND EXISTS (SELECT 1 FROM @patrones AS x WHERE UPPER(c.name) LIKE x.p)
UNION ALL
SELECT 'Compartamos_Vigente_Cobranzas', s.name, o.name, o.type_desc, c.name, t.name
FROM Compartamos_Vigente_Cobranzas.sys.columns AS c
JOIN Compartamos_Vigente_Cobranzas.sys.objects AS o ON o.object_id = c.object_id
JOIN Compartamos_Vigente_Cobranzas.sys.schemas AS s ON s.schema_id = o.schema_id
JOIN Compartamos_Vigente_Cobranzas.sys.types AS t ON t.user_type_id = c.user_type_id
WHERE o.type IN ('U', 'V') AND EXISTS (SELECT 1 FROM @patrones AS x WHERE UPPER(c.name) LIKE x.p)
UNION ALL
SELECT 'Compartamos_Castigo_Cobranzas', s.name, o.name, o.type_desc, c.name, t.name
FROM Compartamos_Castigo_Cobranzas.sys.columns AS c
JOIN Compartamos_Castigo_Cobranzas.sys.objects AS o ON o.object_id = c.object_id
JOIN Compartamos_Castigo_Cobranzas.sys.schemas AS s ON s.schema_id = o.schema_id
JOIN Compartamos_Castigo_Cobranzas.sys.types AS t ON t.user_type_id = c.user_type_id
WHERE o.type IN ('U', 'V') AND EXISTS (SELECT 1 FROM @patrones AS x WHERE UPPER(c.name) LIKE x.p)
UNION ALL
SELECT 'MiBanco_Cobranzas', s.name, o.name, o.type_desc, c.name, t.name
FROM MiBanco_Cobranzas.sys.columns AS c
JOIN MiBanco_Cobranzas.sys.objects AS o ON o.object_id = c.object_id
JOIN MiBanco_Cobranzas.sys.schemas AS s ON s.schema_id = o.schema_id
JOIN MiBanco_Cobranzas.sys.types AS t ON t.user_type_id = c.user_type_id
WHERE o.type IN ('U', 'V') AND EXISTS (SELECT 1 FROM @patrones AS x WHERE UPPER(c.name) LIKE x.p)
UNION ALL
SELECT 'Financiera_OH_Cobranzas', s.name, o.name, o.type_desc, c.name, t.name
FROM Financiera_OH_Cobranzas.sys.columns AS c
JOIN Financiera_OH_Cobranzas.sys.objects AS o ON o.object_id = c.object_id
JOIN Financiera_OH_Cobranzas.sys.schemas AS s ON s.schema_id = o.schema_id
JOIN Financiera_OH_Cobranzas.sys.types AS t ON t.user_type_id = c.user_type_id
WHERE o.type IN ('U', 'V') AND EXISTS (SELECT 1 FROM @patrones AS x WHERE UPPER(c.name) LIKE x.p)
UNION ALL
SELECT 'Interbank_Cobranzas', s.name, o.name, o.type_desc, c.name, t.name
FROM Interbank_Cobranzas.sys.columns AS c
JOIN Interbank_Cobranzas.sys.objects AS o ON o.object_id = c.object_id
JOIN Interbank_Cobranzas.sys.schemas AS s ON s.schema_id = o.schema_id
JOIN Interbank_Cobranzas.sys.types AS t ON t.user_type_id = c.user_type_id
WHERE o.type IN ('U', 'V') AND EXISTS (SELECT 1 FROM @patrones AS x WHERE UPPER(c.name) LIKE x.p)
UNION ALL
SELECT 'CobAuto', s.name, o.name, o.type_desc, c.name, t.name
FROM CobAuto.sys.columns AS c
JOIN CobAuto.sys.objects AS o ON o.object_id = c.object_id
JOIN CobAuto.sys.schemas AS s ON s.schema_id = o.schema_id
JOIN CobAuto.sys.types AS t ON t.user_type_id = c.user_type_id
WHERE o.type IN ('U', 'V') AND EXISTS (SELECT 1 FROM @patrones AS x WHERE UPPER(c.name) LIKE x.p)
ORDER BY base, objeto, columna;
