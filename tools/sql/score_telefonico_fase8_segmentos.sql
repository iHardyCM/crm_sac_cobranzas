/* =====================================================================================
   Generador de bases · fase 8 · segmentos del banco                             (16/11/2026)
   Base: CobAuto (esquema score). Se puede volver a ejecutar completo.

   Las tablas score.SegmentoCarga y score.SegmentoCliente existen desde la fase 3. Aquí se agrega la vista
   que el generador lee para todos los datos por cliente o cuenta:
     - los del corte de Analytics (score.BaseTrabajoDato), como hasta ahora;
     - los segmentos cargados (score.SegmentoCliente, cargas VIGENTES), pegados a cada cartera de la entidad
       (ControlCobranza.bl.EntidadCartera) y solo para los clientes de esa cartera (score.BaseTrabajoCliente).

   ORDEN: ejecutar este archivo ANTES de reiniciar el backend (el código nuevo lee score.vw_DatoCliente).
   La carga de los archivos se hace con tools/cargar_segmentos.py (primero sin --cargar, para revisar).
   ===================================================================================== */
USE CobAuto;
GO

CREATE OR ALTER VIEW score.vw_DatoCliente
AS
SELECT d.IdCartera, d.DNI, d.Campo, d.Cuenta, d.Valor, d.ValorNum, d.FechaFuente
FROM score.BaseTrabajoDato AS d
UNION ALL
SELECT ec.IdCartera, s.DNI, s.Campo, CAST(NULL AS NVARCHAR(60)) AS Cuenta,
       CONVERT(NVARCHAR(200), s.Valor) AS Valor,
       TRY_CONVERT(DECIMAL(18, 4), s.Valor) AS ValorNum,
       CAST(k.FechaCarga AS DATE) AS FechaFuente
FROM score.SegmentoCarga AS k
INNER JOIN score.SegmentoCliente AS s ON s.IdCarga = k.IdCarga
INNER JOIN ControlCobranza.bl.EntidadCartera AS ec ON ec.IdEntidad = k.IdEntidad
WHERE k.Estado = 'VIGENTE'
  AND EXISTS (SELECT 1 FROM score.BaseTrabajoCliente AS b WHERE b.IdCartera = ec.IdCartera AND b.DNI = s.DNI);
GO

-- Para leer por campo y valor (conteos del generador)
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_SegmentoCliente_Campo'
                                         AND object_id = OBJECT_ID('score.SegmentoCliente'))
    CREATE INDEX IX_SegmentoCliente_Campo ON score.SegmentoCliente (Campo, DNI) INCLUDE (IdCarga, Valor);
GO

/* Control después de cargar (ejecutar aparte)
SELECT k.IdCarga, e.Codigo AS Entidad, k.Segmento, k.Periodo, k.Archivo, k.FilasArchivo, k.ClientesCargados,
       k.CodigosSinCruce, k.Estado, k.Usuario, k.FechaCarga
FROM score.SegmentoCarga AS k
INNER JOIN ControlCobranza.bl.Entidad AS e ON e.IdEntidad = k.IdEntidad
ORDER BY k.IdCarga DESC;

SELECT Campo, Valor, COUNT(DISTINCT DNI) AS Clientes
FROM score.vw_DatoCliente
WHERE IdCartera = 112 AND Campo IN ('SEG_COBEX_CAST', 'SUBSEG_COBEX_CAST', 'DSCTO_PREFIERA', 'GESTION_PRIO_MB', 'RANGO_MES_CLASIF_MB')
GROUP BY Campo, Valor
ORDER BY Campo, Clientes DESC;
*/
