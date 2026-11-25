/* =====================================================================================
   Diagnóstico de una carga de segmentos · solo lectura                          (16/11/2026)
   Para qué: ver por qué un segmento cargado no aparece (o aparece vacío) en el generador.
   Cambiar @IdCarga y ejecutar todo. Base: CobAuto.
   ===================================================================================== */
USE CobAuto;
GO
DECLARE @IdCarga INT = 4;

-- 1. La carga
SELECT k.IdCarga, e.Codigo AS Entidad, k.Segmento, k.Periodo, k.Archivo, k.ColumnaClave, k.TipoClave,
       k.FilasArchivo, k.ClientesCargados, k.Estado, k.Usuario, k.FechaCarga
FROM score.SegmentoCarga AS k
INNER JOIN ControlCobranza.bl.Entidad AS e ON e.IdEntidad = k.IdEntidad
WHERE k.IdCarga = @IdCarga;

-- 2. Campos de la carga y cómo quedaron en el catálogo (Activo, Grupo, Origen)
SELECT s.Campo, COUNT(*) AS Filas, COUNT(DISTINCT s.DNI) AS Clientes,
       c.Etiqueta, c.Grupo, c.Origen, c.TipoFiltro, c.Activo
FROM score.SegmentoCliente AS s
LEFT JOIN score.Campo AS c ON c.Codigo = s.Campo
WHERE s.IdCarga = @IdCarga
GROUP BY s.Campo, c.Etiqueta, c.Grupo, c.Origen, c.TipoFiltro, c.Activo;

-- 3. Largo del DNI guardado (si salen DNI de 7 dígitos, Excel perdió el 0 de la izquierda)
SELECT LEN(s.DNI) AS LargoDNI, COUNT(DISTINCT s.DNI) AS Clientes, MIN(s.DNI) AS Ejemplo
FROM score.SegmentoCliente AS s
WHERE s.IdCarga = @IdCarga
GROUP BY LEN(s.DNI)
ORDER BY LargoDNI;

-- 4. Por cartera de la entidad: ¿el campo está habilitado y cuántos clientes cruzan con la base del score?
--    ClientesExactos = lo que ve hoy el generador. ClientesCon0 = los que cruzarían completando el DNI a 8 dígitos.
SELECT ec.IdCartera,
       (SELECT COUNT(*) FROM score.BaseTrabajoCliente AS b WHERE b.IdCartera = ec.IdCartera) AS ClientesEnScore,
       (SELECT COUNT(DISTINCT cc.Campo) FROM score.CampoCartera AS cc
         WHERE cc.IdCartera = ec.IdCartera
           AND cc.Campo IN (SELECT Campo FROM score.SegmentoCliente WHERE IdCarga = @IdCarga)) AS CamposHabilitados,
       (SELECT COUNT(DISTINCT s.DNI) FROM score.SegmentoCliente AS s
         WHERE s.IdCarga = @IdCarga
           AND EXISTS (SELECT 1 FROM score.BaseTrabajoCliente AS b
                       WHERE b.IdCartera = ec.IdCartera AND b.DNI = s.DNI)) AS ClientesExactos,
       (SELECT COUNT(DISTINCT s.DNI) FROM score.SegmentoCliente AS s
         WHERE s.IdCarga = @IdCarga
           AND EXISTS (SELECT 1 FROM score.BaseTrabajoCliente AS b
                       WHERE b.IdCartera = ec.IdCartera
                         AND b.DNI = CASE WHEN s.DNI NOT LIKE '%[^0-9]%' AND LEN(s.DNI) < 8
                                          THEN RIGHT('00000000' + s.DNI, 8) ELSE s.DNI END)) AS ClientesCon0
FROM score.SegmentoCarga AS k
INNER JOIN ControlCobranza.bl.EntidadCartera AS ec ON ec.IdEntidad = k.IdEntidad
WHERE k.IdCarga = @IdCarga
ORDER BY ec.IdCartera;

-- 5. Lo que lee el generador (vista score.vw_DatoCliente), por cartera, campo y valor
SELECT v.IdCartera, v.Campo, v.Valor, COUNT(DISTINCT v.DNI) AS Clientes
FROM score.vw_DatoCliente AS v
WHERE v.Campo IN (SELECT Campo FROM score.SegmentoCliente WHERE IdCarga = @IdCarga)
GROUP BY v.IdCartera, v.Campo, v.Valor
ORDER BY v.IdCartera, v.Campo, Clientes DESC;
