/* =====================================================================================
   Score telefónico · fase 6 · índice para el "mejor resultado" en la pantalla del generador
   Base: CobAuto · esquema score · 15/11/2026

   Para qué: la tabla de teléfonos del generador muestra, por cada fila de la página, el mejor
   resultado del teléfono y del cliente en los últimos 90 días y el último resultado del teléfono
   (score.TelefonoDia). score.TelefonoDia tiene la clave por (Fecha, IdCartera, DNI, Telefono):
   buscar por cliente obliga a recorrer los 90 días de la cartera. Este índice permite ir directo
   al cliente y al teléfono.

   Ejecutar por bloques:
     Bloque 0 · solo lectura: tamaño de score.TelefonoDia y sus índices actuales.
     Bloque 1 · crea el índice (si no existe). Puede tardar según el tamaño que dé el bloque 0.
     Bloque 2 · solo lectura: prueba con 50 teléfonos de la cartera 112 y su tiempo.
   ===================================================================================== */
USE CobAuto;
GO

/* ------------------------------------------------------------------------------------
   BLOQUE 0 · Tamaño e índices actuales (solo lectura)
   ------------------------------------------------------------------------------------ */
SELECT  'score.TelefonoDia' AS Tabla,
        SUM(p.rows) AS Filas,
        CAST(SUM(a.total_pages) * 8 / 1024.0 AS DECIMAL(12, 1)) AS MB,
        (SELECT MIN(Fecha) FROM score.TelefonoDia) AS DesdeFecha,
        (SELECT MAX(Fecha) FROM score.TelefonoDia) AS HastaFecha
FROM sys.partitions AS p
INNER JOIN sys.allocation_units AS a ON a.container_id = p.partition_id
WHERE p.object_id = OBJECT_ID('score.TelefonoDia') AND p.index_id IN (0, 1);

SELECT i.name AS Indice, i.type_desc AS Tipo,
       STUFF((SELECT ', ' + c.name FROM sys.index_columns AS ic
              INNER JOIN sys.columns AS c ON c.object_id = ic.object_id AND c.column_id = ic.column_id
              WHERE ic.object_id = i.object_id AND ic.index_id = i.index_id AND ic.is_included_column = 0
              ORDER BY ic.key_ordinal FOR XML PATH('')), 1, 2, '') AS Columnas
FROM sys.indexes AS i
WHERE i.object_id = OBJECT_ID('score.TelefonoDia') AND i.index_id > 0;
GO

/* ------------------------------------------------------------------------------------
   BLOQUE 1 · Índice por cliente y teléfono
   ------------------------------------------------------------------------------------ */
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID('score.TelefonoDia') AND name = 'IX_TelefonoDia_Cliente')
BEGIN
    CREATE NONCLUSTERED INDEX IX_TelefonoDia_Cliente
        ON score.TelefonoDia (IdCartera, DNI, Telefono, Fecha)
        INCLUDE (MejorResultado, UltimoResultado, UltimoEvento);
    PRINT 'Índice IX_TelefonoDia_Cliente creado.';
END
ELSE
    PRINT 'El índice IX_TelefonoDia_Cliente ya existía.';
GO

/* ------------------------------------------------------------------------------------
   BLOQUE 2 · Prueba (solo lectura): la misma búsqueda que hace la pantalla, para 50 teléfonos
   ------------------------------------------------------------------------------------ */
SET STATISTICS TIME ON;

DECLARE @DesdeHist DATE = DATEADD(DAY, -90, CAST(GETDATE() AS DATE));

WITH pg AS (
    SELECT TOP 50 IdCartera, DNI, Telefono
    FROM score.vw_BaseTrabajo
    WHERE IdCartera = 112 AND Descartado = 0
    ORDER BY Score DESC, DNI
)
SELECT pg.DNI, pg.Telefono,
       mt.MejorResultado AS MejorResultadoTel, mt.Fecha AS FechaMejorTel,
       mc.MejorResultado AS MejorResultadoCli,
       ut.UltimoResultado AS UltimoResultadoTel, ut.UltimoEvento
FROM pg
OUTER APPLY (SELECT TOP 1 d.MejorResultado, d.Fecha
             FROM score.TelefonoDia AS d INNER JOIN score.ResultadoTelefono AS r ON r.Codigo = d.MejorResultado
             WHERE d.IdCartera = pg.IdCartera AND d.DNI = pg.DNI AND d.Telefono = pg.Telefono AND d.Fecha >= @DesdeHist
             ORDER BY r.Orden, d.Fecha DESC) AS mt
OUTER APPLY (SELECT TOP 1 d.MejorResultado
             FROM score.TelefonoDia AS d INNER JOIN score.ResultadoTelefono AS r ON r.Codigo = d.MejorResultado
             WHERE d.IdCartera = pg.IdCartera AND d.DNI = pg.DNI AND d.Fecha >= @DesdeHist
             ORDER BY r.Orden, d.Fecha DESC) AS mc
OUTER APPLY (SELECT TOP 1 d.UltimoResultado, d.UltimoEvento
             FROM score.TelefonoDia AS d
             WHERE d.IdCartera = pg.IdCartera AND d.DNI = pg.DNI AND d.Telefono = pg.Telefono AND d.Fecha >= @DesdeHist
               AND d.UltimoEvento IS NOT NULL
             ORDER BY d.UltimoEvento DESC) AS ut;

SET STATISTICS TIME OFF;
GO

/* ------------------------------------------------------------------------------------
   BLOQUE 3 · Tasa de CEF por tramo en la versión 1 del score (para el detalle en la pantalla)
   La calibración del 14/11/2026 18:06 (tools/salidas/score_calibracion_20261114_1806.md) guardó en
   score.PesoVersion.Metricas solo la tasa de los tramos A y E. Este bloque agrega la tabla completa
   de la PRUEBA (cortes 19/10, 26/10 y 02/11) copiada de ese informe: por tramo, por decil y por entidad.
   Solo actúa si la versión 1 tiene los mismos cortes y puntos máximos que ese informe.
   ------------------------------------------------------------------------------------ */
DECLARE @Tramos NVARCHAR(MAX) = N'[
 {"tramo":"A","telefonos":68298,"cef":10611,"tasa_cef_pct":15.54},
 {"tramo":"B","telefonos":39585,"cef":1371,"tasa_cef_pct":3.46},
 {"tramo":"C","telefonos":50589,"cef":954,"tasa_cef_pct":1.89},
 {"tramo":"D","telefonos":44790,"cef":327,"tasa_cef_pct":0.73},
 {"tramo":"E","telefonos":27574,"cef":87,"tasa_cef_pct":0.32}]';
DECLARE @Deciles NVARCHAR(MAX) = N'[
 {"decil":1,"telefonos":24240,"cef":7132,"tasa_cef_pct":29.42},{"decil":2,"telefonos":22948,"cef":2206,"tasa_cef_pct":9.61},
 {"decil":3,"telefonos":30745,"cef":1723,"tasa_cef_pct":5.6},{"decil":4,"telefonos":19953,"cef":624,"tasa_cef_pct":3.13},
 {"decil":5,"telefonos":24702,"cef":649,"tasa_cef_pct":2.63},{"decil":6,"telefonos":24301,"cef":439,"tasa_cef_pct":1.81},
 {"decil":7,"telefonos":20787,"cef":275,"tasa_cef_pct":1.32},{"decil":8,"telefonos":17560,"cef":140,"tasa_cef_pct":0.8},
 {"decil":9,"telefonos":25745,"cef":108,"tasa_cef_pct":0.42},{"decil":10,"telefonos":19855,"cef":54,"tasa_cef_pct":0.27}]';
DECLARE @Entidades NVARCHAR(MAX) = N'[
 {"entidad":"COMPARTAMOS","tramo":"A","telefonos":39219,"cef":6108,"tasa_cef_pct":15.57},
 {"entidad":"COMPARTAMOS","tramo":"B","telefonos":21623,"cef":975,"tasa_cef_pct":4.51},
 {"entidad":"COMPARTAMOS","tramo":"C","telefonos":22128,"cef":586,"tasa_cef_pct":2.65},
 {"entidad":"COMPARTAMOS","tramo":"D","telefonos":21889,"cef":209,"tasa_cef_pct":0.95},
 {"entidad":"COMPARTAMOS","tramo":"E","telefonos":11908,"cef":43,"tasa_cef_pct":0.36},
 {"entidad":"FINANCIERA_OH","tramo":"A","telefonos":17071,"cef":2242,"tasa_cef_pct":13.13},
 {"entidad":"FINANCIERA_OH","tramo":"B","telefonos":9926,"cef":164,"tasa_cef_pct":1.65},
 {"entidad":"FINANCIERA_OH","tramo":"C","telefonos":16437,"cef":178,"tasa_cef_pct":1.08},
 {"entidad":"FINANCIERA_OH","tramo":"D","telefonos":13959,"cef":45,"tasa_cef_pct":0.32},
 {"entidad":"FINANCIERA_OH","tramo":"E","telefonos":9471,"cef":18,"tasa_cef_pct":0.19},
 {"entidad":"INTERBANK","tramo":"A","telefonos":2992,"cef":983,"tasa_cef_pct":32.85},
 {"entidad":"INTERBANK","tramo":"B","telefonos":1962,"cef":50,"tasa_cef_pct":2.55},
 {"entidad":"INTERBANK","tramo":"C","telefonos":4143,"cef":55,"tasa_cef_pct":1.33},
 {"entidad":"INTERBANK","tramo":"D","telefonos":2898,"cef":26,"tasa_cef_pct":0.9},
 {"entidad":"INTERBANK","tramo":"E","telefonos":1875,"cef":6,"tasa_cef_pct":0.32},
 {"entidad":"MIBANCO","tramo":"A","telefonos":1343,"cef":124,"tasa_cef_pct":9.23},
 {"entidad":"MIBANCO","tramo":"B","telefonos":1279,"cef":51,"tasa_cef_pct":3.99},
 {"entidad":"MIBANCO","tramo":"C","telefonos":1492,"cef":23,"tasa_cef_pct":1.54},
 {"entidad":"MIBANCO","tramo":"D","telefonos":1083,"cef":16,"tasa_cef_pct":1.48},
 {"entidad":"MIBANCO","tramo":"E","telefonos":918,"cef":5,"tasa_cef_pct":0.54},
 {"entidad":"PROPIA","tramo":"A","telefonos":7673,"cef":1154,"tasa_cef_pct":15.04},
 {"entidad":"PROPIA","tramo":"B","telefonos":4795,"cef":131,"tasa_cef_pct":2.73},
 {"entidad":"PROPIA","tramo":"C","telefonos":6389,"cef":112,"tasa_cef_pct":1.75},
 {"entidad":"PROPIA","tramo":"D","telefonos":4961,"cef":31,"tasa_cef_pct":0.62},
 {"entidad":"PROPIA","tramo":"E","telefonos":3402,"cef":15,"tasa_cef_pct":0.44}]';

IF EXISTS (SELECT 1 FROM score.PesoVersion
           WHERE Version = 1 AND Tramo_A = 51 AND Tramo_B = 47 AND Tramo_C = 43 AND Tramo_D = 38
             AND PuntosMaximos = 316.49 AND ISJSON(Metricas) = 1)
BEGIN
    UPDATE score.PesoVersion
    SET Metricas = JSON_MODIFY(JSON_MODIFY(JSON_MODIFY(Metricas,
                       '$.tasa_por_tramo', JSON_QUERY(@Tramos)),
                       '$.tasa_por_decil', JSON_QUERY(@Deciles)),
                       '$.tasa_por_entidad_tramo', JSON_QUERY(@Entidades))
    WHERE Version = 1;
    SELECT Version, JSON_QUERY(Metricas, '$.tasa_por_tramo') AS TasaPorTramo FROM score.PesoVersion WHERE Version = 1;
END
ELSE
    SELECT 'La versión 1 no coincide con el informe del 14/11 18:06 (cortes 51/47/43/38, máximo 316.49): no se tocó.' AS Resultado,
           Version, Tramo_A, Tramo_B, Tramo_C, Tramo_D, PuntosMaximos, ISJSON(Metricas) AS MetricasJson
    FROM score.PesoVersion WHERE Version = 1;
GO
