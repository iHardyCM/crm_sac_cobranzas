/* =====================================================================================
   Fase 11 · ajuste de la lista de seguimiento de MiBanco (112)                    (17/11/2026)
   Hardy, 17/11: en MiBanco solo valen las dos de negociación y la de seguimiento de solución de pago.
   Se quita 1124 "DIFICULTAD DE PAGO - DIFICULTAD EN EL NEGOCIO".

   OJO: la lista es Biznescob_Analytics.dbo.CFG_SEGUIMIENTO_INDICADOR, la misma de la bolsa de seguimientos
   de Analytics. El cambio también se refleja allí desde su próxima captura.

   PASO 1 · Solo lectura: uso de cada indicador de MiBanco en la 112 por mes (6 meses)
   PASO 2 · Desactivar 1124 (y 1089 solo si el paso 1 lo justifica: ver la nota)
   PASO 3 · Rehacer la historia de seguimientos de la 112 (se guardó con la lista anterior) y armar la 112
   ===================================================================================== */
USE CobAuto;
GO

/* PASO 1 · Uso por mes. Hay TRES de negociación en la lista: 1089 "EN NEGOCIACION", 1119 "- PARCIAL" y
   1120 "- TOTAL". Si 1089 ya no se usa (paleta anterior) o se usa igual que las otras, decidir aquí. */
SELECT CONVERT(CHAR(7), g.Fecha, 120) AS Mes, g.IdIndicador, i.DescripcionIndicador, COUNT(*) AS Gestiones,
       COUNT(DISTINCT g.IdCliente) AS Clientes
FROM siscob.dbo.gestion AS g WITH (NOLOCK)
INNER JOIN siscob.dbo.Indicador AS i WITH (NOLOCK) ON i.IdIndicador = g.IdIndicador
WHERE g.Fecha >= DATEADD(MONTH, -6, DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1))
  AND g.idCartera = 112
  AND g.IdIndicador IN (1089, 1119, 1120, 1124, 1125)
GROUP BY CONVERT(CHAR(7), g.Fecha, 120), g.IdIndicador, i.DescripcionIndicador
ORDER BY Mes DESC, g.IdIndicador
OPTION (RECOMPILE);
GO

/* PASO 2 · Desactivar (no se borra: queda con ESTADO = 'I'). */
UPDATE Biznescob_Analytics.dbo.CFG_SEGUIMIENTO_INDICADOR
SET ESTADO = 'I'
WHERE IDCARTERA = 112
  AND IDINDICADOR IN (1124 /*, 1089 */);      -- descomentar 1089 solo si se decide quitarlo
SELECT IDCARTERA, IDINDICADOR, GRUPO, ESTADO
FROM Biznescob_Analytics.dbo.CFG_SEGUIMIENTO_INDICADOR WHERE IDCARTERA = 112 ORDER BY IDINDICADOR;
GO

/* PASO 3 · La historia de la 112 se guardó con 1124 incluido: se borra y se vuelve a leer desde 2022 con la
   lista nueva. Solo toca la 112. */
DELETE FROM score.SeguimientoCliente WHERE IdCartera = 112;
DELETE FROM score.SeguimientoLectura WHERE IdCartera = 112;

DECLARE @Aviso NVARCHAR(1000), @t DATETIME2(3) = SYSDATETIME();
EXEC score.sp_ArmarGestion @IdCartera = 112, @Simular = 0, @Aviso = @Aviso OUTPUT;
SELECT DATEDIFF(SECOND, @t, SYSDATETIME()) AS Segundos, @Aviso AS Aviso;

SELECT EstadoSeguimiento, COUNT(DISTINCT DNI) AS Clientes
FROM score.vw_BaseTrabajo WHERE IdCartera = 112
GROUP BY EstadoSeguimiento ORDER BY EstadoSeguimiento;
GO
