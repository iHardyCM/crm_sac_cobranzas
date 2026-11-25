/* =====================================================================================
   indicador_954.sql · 24/11/2026
   954 "PAGO EN TRAMITE" (CEF en SISCOB, cartera 117) apareció el 17/11 sin resultado en el catálogo.
   Va a TITULAR, igual que los otros "pago en trámite" (catálogo aprobado el 14/11).
   Luego se recarga el 17/11 y se rearma su rendimiento.
   ===================================================================================== */
USE CobAuto;
GO

-- 1. Antes: confirma que no está
SELECT * FROM score.IndicadorResultado WHERE IdIndicador = 954;
GO

-- 2. Alta en el catálogo
IF NOT EXISTS (SELECT 1 FROM score.IndicadorResultado WHERE IdIndicador = 954)
    INSERT INTO score.IndicadorResultado (IdIndicador, Descripcion, TipoContactoSiscob, Resultado, CarterasObservadas)
    VALUES (954, N'PAGO EN TRAMITE', 'CEF', 'TITULAR', '117');
GO

-- 3. Recarga del 17/11 y su rendimiento (unos segundos)
EXEC score.sp_CargarTelefonoDia @Fecha = '2026-11-17', @Simular = 0;     -- EventosSinClasificar debe salir 0
EXEC score.sp_ArmarRendimientoDia @Fecha = '2026-11-17', @Simular = 0;
GO
