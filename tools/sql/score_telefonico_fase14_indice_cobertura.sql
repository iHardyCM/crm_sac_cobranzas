/* =====================================================================================
   score_telefonico_fase14_indice_cobertura.sql · 24/11/2026
   La columna "% llamados en el periodo" (vista Rendimiento del score) cuenta teléfonos distintos del
   score.TelefonoScore de la cartera en 7/14/30 días. El índice IX_TelefonoScore_Cartera (IdCartera, FechaCorte)
   ya existe (fase 5); se le agregan Tramo y OrdenCliente para que esa consulta no vaya a la tabla.
   Reconstruye el índice: unos minutos y bloquea TelefonoScore mientras tanto. Correrlo fuera del horario
   de generación de bases.
   ===================================================================================== */
USE CobAuto;
GO

-- 1. Antes: tamaño del índice actual
SELECT i.name, SUM(ps.used_page_count) * 8 / 1024 AS MB, SUM(ps.row_count) AS Filas
FROM sys.indexes AS i
JOIN sys.dm_db_partition_stats AS ps ON ps.object_id = i.object_id AND ps.index_id = i.index_id
WHERE i.object_id = OBJECT_ID('score.TelefonoScore')
GROUP BY i.name;
GO

-- 2. Índice con Tramo y OrdenCliente
IF EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_TelefonoScore_Cartera' AND object_id = OBJECT_ID('score.TelefonoScore'))
    CREATE INDEX IX_TelefonoScore_Cartera ON score.TelefonoScore (IdCartera, FechaCorte)
        INCLUDE (Tramo, OrdenCliente) WITH (DROP_EXISTING = ON);
ELSE
    CREATE INDEX IX_TelefonoScore_Cartera ON score.TelefonoScore (IdCartera, FechaCorte)
        INCLUDE (Tramo, OrdenCliente);
GO

-- 3. Después: debe mostrar Tramo y OrdenCliente como columnas incluidas
SELECT i.name, c.name AS Columna, ic.is_included_column
FROM sys.indexes AS i
JOIN sys.index_columns AS ic ON ic.object_id = i.object_id AND ic.index_id = i.index_id
JOIN sys.columns AS c ON c.object_id = ic.object_id AND c.column_id = ic.column_id
WHERE i.object_id = OBJECT_ID('score.TelefonoScore') AND i.name = 'IX_TelefonoScore_Cartera'
ORDER BY ic.is_included_column, ic.key_ordinal;
GO
