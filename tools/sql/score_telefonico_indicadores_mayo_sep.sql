/* =====================================================================================
   SCORE TELEFÓNICO · Indicadores que faltaban en el catálogo (mayo–septiembre 2026)
   Fecha: 14/11/2026

   1. Agrega los 7 indicadores que aparecieron sin clasificar (269 gestiones entre el 14/05 y el 30/09).
   2. Vuelve a cargar SOLO los días que tuvieron eventos sin clasificar (la carga es idempotente:
      reemplaza el día completo).
   3. Verifica que no quede ninguno.
   ===================================================================================== */
USE CobAuto;
GO
SET NOCOUNT ON;
GO

/* 1. Catálogo */
INSERT INTO score.IndicadorResultado (IdIndicador, Descripcion, TipoContactoSiscob, Resultado, CarterasObservadas)
SELECT v.IdIndicador, v.Descripcion, v.TipoContactoSiscob, v.Resultado, v.CarterasObservadas
FROM (VALUES
    (1119, N'EN NEGOCIACIÓN - PARCIAL', 'CEF', 'TITULAR',         '112,143'),
    (1192, N'SOLICITARA RECLAMO',       'CEF', 'TITULAR',         '137,148'),
    (1027, N'COMPROMISO INCIERTO',      'CEF', 'TITULAR',         '117'),
    (1207, N'TRANSACCION',              'CEF', 'TITULAR',         '112,143'),
    (1184, N'PAGO EN TRAMITE',          'CEF', 'TITULAR',         '148'),
    (1079, N'TEL. FALLADO',             'NOC', 'SIN_INFORMACION', '132'),
    (1036, N'FALLAOO',                  'NOC', 'SIN_INFORMACION', '117')
) v (IdIndicador, Descripcion, TipoContactoSiscob, Resultado, CarterasObservadas)
WHERE NOT EXISTS (SELECT 1 FROM score.IndicadorResultado r WHERE r.IdIndicador = v.IdIndicador);
GO

/* 2. Días a recargar (antes de recargar) */
SELECT Fecha, IndicadoresSinClasificar
FROM score.TelefonoDiaControl
WHERE IndicadoresSinClasificar > 0
ORDER BY Fecha;
GO

DECLARE @f DATE;
DECLARE dias CURSOR LOCAL FAST_FORWARD FOR
    SELECT Fecha FROM score.TelefonoDiaControl WHERE IndicadoresSinClasificar > 0 ORDER BY Fecha;
OPEN dias;
FETCH NEXT FROM dias INTO @f;
WHILE @@FETCH_STATUS = 0
BEGIN
    EXEC score.sp_CargarTelefonoDia @Fecha = @f, @Simular = 0;
    FETCH NEXT FROM dias INTO @f;
END;
CLOSE dias;
DEALLOCATE dias;
GO

/* 3. Verificación: debe salir 0 en todos los meses */
SELECT FORMAT(Fecha, 'yyyyMM') AS mes, SUM(IndicadoresSinClasificar) AS sin_clasificar
FROM score.TelefonoDiaControl
GROUP BY FORMAT(Fecha, 'yyyyMM')
ORDER BY mes;
GO
