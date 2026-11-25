/* =====================================================================================
   SCORE TELEFÓNICO · DIAGNÓSTICO 8 — TIEMPOS DE "ACTUALIZAR CARTERA"
   Fecha: 14/11/2026 · Solo lectura (las características se corren en simulación: no escriben).

   Qué se quiere saber:
     En la corrida del 14/11 las características tardaron ~90 s en 112, 117, 132, 137 y 148, y menos de
     15 s en 124, 126, 128, 133 y 144, sin relación con el tamaño de la cartera (117 tiene 17 mil teléfonos
     y tardó 97 s; 144 tiene 225 mil y tardó 13 s). Antes de tocar índices hay que ver qué sección se lleva
     el tiempo y si coincide con el volumen de historial de cada cartera.

   Requiere: score_telefonico_fase3.sql actualizado (bloques 1 y 2), por el parámetro @Tiempos.
   Guardar la salida en tools/salidas/resultados_diagnostico_score_8.txt
   ===================================================================================== */

USE CobAuto;
GO
SET NOCOUNT ON;

DECLARE @Hoy DATE = CAST(GETDATE() AS DATE);
DECLARE @Ini90 DATE = DATEADD(DAY, -90, @Hoy);

/* 1. Volumen de historial de 90 días por cartera (lo que leen las secciones 2 y 2B) */
SELECT d.IdCartera,
       COUNT(*) AS filas_90d,
       SUM(CASE WHEN d.N_EQUIVOCADO > 0 THEN 1 ELSE 0 END) AS filas_con_equivocado,
       SUM(CASE WHEN d.N_NO_EXISTE > 0 THEN 1 ELSE 0 END) AS filas_con_no_existe,
       (SELECT COUNT(*) FROM score.TelefonoUniverso AS u WHERE u.IdCartera = d.IdCartera AND u.ExcluidoListaNegra = 0) AS telefonos_universo
FROM score.TelefonoDia AS d
WHERE d.Fecha >= @Ini90 AND d.Fecha < @Hoy
GROUP BY d.IdCartera
ORDER BY d.IdCartera;

/* 2. Tamaño e índices de score.TelefonoDia */
EXEC sp_spaceused 'score.TelefonoDia';

SELECT i.name AS indice, i.type_desc,
       STUFF((SELECT ', ' + c.name + CASE WHEN ic.is_included_column = 1 THEN ' (incl.)' ELSE '' END
              FROM sys.index_columns AS ic
              INNER JOIN sys.columns AS c ON c.object_id = ic.object_id AND c.column_id = ic.column_id
              WHERE ic.object_id = i.object_id AND ic.index_id = i.index_id
              ORDER BY ic.is_included_column, ic.key_ordinal
              FOR XML PATH('')), 1, 2, '') AS columnas
FROM sys.indexes AS i
WHERE i.object_id IN (OBJECT_ID('score.TelefonoDia'), OBJECT_ID('score.TelefonoUniverso'))
  AND i.index_id > 0
ORDER BY i.object_id, i.index_id;
GO

/* 3. Tiempos por sección: una cartera lenta y pequeña (117), una rápida y grande (144) y la 112.
      Cada una devuelve: simulación, tramos de último CEF y la tabla de tiempos (la que interesa). */
DECLARE @Hoy DATE = CAST(GETDATE() AS DATE);
EXEC CobAuto.score.sp_ArmarCaracteristicas @FechaCorte = @Hoy, @Poblacion = 'UNIVERSO', @Simular = 1, @IdCartera = 117, @Tiempos = 1;
EXEC CobAuto.score.sp_ArmarCaracteristicas @FechaCorte = @Hoy, @Poblacion = 'UNIVERSO', @Simular = 1, @IdCartera = 144, @Tiempos = 1;
EXEC CobAuto.score.sp_ArmarCaracteristicas @FechaCorte = @Hoy, @Poblacion = 'UNIVERSO', @Simular = 1, @IdCartera = 112, @Tiempos = 1;
GO

/* 4. Alineación corregida: sin cambios pendientes ahora debe terminar bien y registrar ceros.
      (Escribe una fila en la bitácora de alineación; solo toca siscob si producción tiene diferencias.) */
EXEC CobAuto.score.sp_AlinearAtributosTelefono @Carteras = '112', @Simular = 0;
GO
