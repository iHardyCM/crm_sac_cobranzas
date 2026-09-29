/* =============================================================================
   Tarifas de la API de IA — CRM_IA_TARIFA_MODELO
   Base: CobAuto. Ejecutar DESPUÉS de tools/sql/crear_consumo_ia.sql.

   DE DÓNDE SALEN LOS PRECIOS
   gpt-4o-transcribe-diarize: de la ficha del modelo en la consola de OpenAI,
   sección Pricing > Audio tokens (revisada el 23/09/2026):
       Input  $2.50 por 1M tokens
       Output $10.00 por 1M tokens

   SUPUESTO QUE DEBES VALIDAR
   La ficha publica un solo precio de entrada. Tu panel de gasto separa
   "audio, input", "text, input" y "text, output" para ese mismo modelo, así que
   aquí se cargan los tokens de texto de entrada al mismo precio que los de
   audio ($2.50). Si tu factura muestra otro valor para el texto, corrige la
   fila AUDIO/INPUT correspondiente.

   PENDIENTE
   gpt-4o-mini: falta el precio de input, cached input y output (está en la
   tabla de modelos de TEXTO, no en la de transcripción). Mientras no se cargue,
   la pantalla mostrará los tokens del análisis sin costo.

   Este script es idempotente: borra la tarifa vigente del mismo día antes de
   insertar, así se puede volver a ejecutar sin duplicar.
   ============================================================================= */

USE CobAuto;
GO

DECLARE @hoy DATE = CAST(GETDATE() AS DATE);

DELETE FROM dbo.CRM_IA_TARIFA_MODELO
WHERE vigente_desde = @hoy
  AND modelo IN ('gpt-4o-transcribe-diarize', 'gpt-4o-mini-transcribe', 'gpt-4o-transcribe');

INSERT INTO dbo.CRM_IA_TARIFA_MODELO (modelo, concepto, precio, unidad, vigente_desde, nota) VALUES
  ('gpt-4o-transcribe-diarize', 'INPUT',  2.50,  1000000, @hoy, 'Ficha del modelo 23/09/2026: tokens de entrada (audio y texto)'),
  ('gpt-4o-transcribe-diarize', 'AUDIO',  2.50,  1000000, @hoy, 'Ficha del modelo 23/09/2026: audio tokens input'),
  ('gpt-4o-transcribe-diarize', 'OUTPUT', 10.00, 1000000, @hoy, 'Ficha del modelo 23/09/2026: output'),
  -- Modelos de respaldo, por si alguna transcripción cae al fallback:
  ('gpt-4o-transcribe',         'INPUT',  2.50,  1000000, @hoy, 'Tabla de modelos de transcripción 23/09/2026'),
  ('gpt-4o-transcribe',         'AUDIO',  2.50,  1000000, @hoy, 'Tabla de modelos de transcripción 23/09/2026'),
  ('gpt-4o-transcribe',         'OUTPUT', 10.00, 1000000, @hoy, 'Tabla de modelos de transcripción 23/09/2026'),
  ('gpt-4o-mini-transcribe',    'INPUT',  1.25,  1000000, @hoy, 'Tabla de modelos de transcripción 23/09/2026'),
  ('gpt-4o-mini-transcribe',    'AUDIO',  1.25,  1000000, @hoy, 'Tabla de modelos de transcripción 23/09/2026'),
  ('gpt-4o-mini-transcribe',    'OUTPUT', 5.00,  1000000, @hoy, 'Tabla de modelos de transcripción 23/09/2026');
GO

/* -----------------------------------------------------------------------------
   FALTA gpt-4o-mini. Reemplaza los 0.00 con los precios de la tabla de modelos
   de texto de tu consola y descomenta este bloque.

DECLARE @hoy2 DATE = CAST(GETDATE() AS DATE);
DELETE FROM dbo.CRM_IA_TARIFA_MODELO WHERE vigente_desde = @hoy2 AND modelo = 'gpt-4o-mini';
INSERT INTO dbo.CRM_IA_TARIFA_MODELO (modelo, concepto, precio, unidad, vigente_desde, nota) VALUES
  ('gpt-4o-mini', 'INPUT',    0.00, 1000000, @hoy2, 'Consola OpenAI, tabla de modelos de texto'),
  ('gpt-4o-mini', 'CACHEADO', 0.00, 1000000, @hoy2, 'Precio de cached input'),
  ('gpt-4o-mini', 'OUTPUT',   0.00, 1000000, @hoy2, 'Precio de output');
----------------------------------------------------------------------------- */

-- Verificación: tarifas cargadas y precio por token resultante
SELECT modelo, concepto, precio, unidad,
       precio_por_token = precio / NULLIF(unidad, 0),
       vigente_desde
FROM dbo.CRM_IA_TARIFA_MODELO
ORDER BY modelo, concepto, vigente_desde DESC;
GO

-- Qué modelos ya registraron consumo pero todavía no tienen tarifa cargada
SELECT C.modelo,
       llamadas = COUNT(*),
       tokens = SUM(C.tokens_input + C.tokens_output + C.tokens_audio),
       tiene_tarifa = CASE WHEN EXISTS (SELECT 1 FROM dbo.CRM_IA_TARIFA_MODELO T WHERE T.modelo = C.modelo)
                           THEN 'SI' ELSE 'NO — carga su precio' END
FROM dbo.CRM_IA_CONSUMO_API C
GROUP BY C.modelo
ORDER BY tokens DESC;
GO
