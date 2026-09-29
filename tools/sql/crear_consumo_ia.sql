/* =============================================================================
   Consumo de la API de IA por evaluación — CRM_IA_CONSUMO_API + tarifas
   Base: CobAuto (nivel de compatibilidad 120). Script idempotente.

   POR QUÉ
   Hoy la factura de la API se ve por modelo y por día, pero no por llamada
   evaluada: no se puede decir cuánto costó la evaluación #114 ni qué paso del
   análisis se lleva los tokens. Esta tabla guarda lo que la propia API informa
   en cada respuesta (tokens y modelo), con el id_feedback y el paso.

   QUÉ GUARDA
   Una fila por llamada a la API: la transcripción y cada paso del análisis
   (roles, hablantes, hechos, criterios, auditoría, corrección, feedback).

   COSTOS
   Los precios NO se hardcodean: van en CRM_IA_TARIFA_MODELO, con vigencia.
   El reporte multiplica tokens por tarifa; si un modelo no tiene tarifa
   cargada, muestra tokens y deja el costo vacío en vez de inventarlo.
   Carga las tarifas desde la página de precios de tu proveedor (al final hay
   una plantilla comentada).
   ============================================================================= */

USE CobAuto;
GO

IF OBJECT_ID('dbo.CRM_IA_CONSUMO_API', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.CRM_IA_CONSUMO_API (
        id_consumo        BIGINT IDENTITY(1,1) NOT NULL
            CONSTRAINT PK_CRM_IA_CONSUMO_API PRIMARY KEY,
        id_feedback       INT            NULL,      -- NULL: llamada fuera del flujo de una evaluación
        paso              VARCHAR(40)    NOT NULL,  -- TRANSCRIPCION, ROLES, HECHOS, CRITERIOS, ...
        modelo            NVARCHAR(100)  NOT NULL,
        tokens_input      INT            NOT NULL CONSTRAINT DF_CRM_IA_CONSUMO_in   DEFAULT (0),
        tokens_cacheados  INT            NOT NULL CONSTRAINT DF_CRM_IA_CONSUMO_cac  DEFAULT (0),
        tokens_output     INT            NOT NULL CONSTRAINT DF_CRM_IA_CONSUMO_out  DEFAULT (0),
        tokens_audio      INT            NOT NULL CONSTRAINT DF_CRM_IA_CONSUMO_aud  DEFAULT (0),
        segundos_audio    DECIMAL(10,2)  NULL,      -- solo transcripción
        duracion_ms       INT            NULL,      -- cuánto tardó la llamada
        exito             BIT            NOT NULL CONSTRAINT DF_CRM_IA_CONSUMO_ok   DEFAULT (1),
        detalle_error     NVARCHAR(400)  NULL,
        fecha             DATETIME       NOT NULL CONSTRAINT DF_CRM_IA_CONSUMO_fec  DEFAULT (GETDATE())
    );
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_CRM_IA_CONSUMO_API_feedback'
               AND object_id = OBJECT_ID('dbo.CRM_IA_CONSUMO_API'))
    CREATE INDEX IX_CRM_IA_CONSUMO_API_feedback
        ON dbo.CRM_IA_CONSUMO_API (id_feedback) INCLUDE (paso, modelo, tokens_input, tokens_output);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_CRM_IA_CONSUMO_API_fecha'
               AND object_id = OBJECT_ID('dbo.CRM_IA_CONSUMO_API'))
    CREATE INDEX IX_CRM_IA_CONSUMO_API_fecha ON dbo.CRM_IA_CONSUMO_API (fecha);
GO

/* Tarifas por modelo y concepto. unidad = por cuántas unidades aplica el precio
   (1000000 = precio por millón de tokens; 60 = precio por minuto expresado en
   segundos). vigente_desde permite cambiar precios sin perder el histórico. */
IF OBJECT_ID('dbo.CRM_IA_TARIFA_MODELO', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.CRM_IA_TARIFA_MODELO (
        id_tarifa      INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_CRM_IA_TARIFA_MODELO PRIMARY KEY,
        modelo         NVARCHAR(100) NOT NULL,
        concepto       VARCHAR(20)   NOT NULL,   -- INPUT | CACHEADO | OUTPUT | AUDIO
        precio         DECIMAL(18,8) NOT NULL,   -- en USD
        unidad         INT           NOT NULL,   -- unidades que cubre ese precio
        vigente_desde  DATE          NOT NULL CONSTRAINT DF_CRM_IA_TARIFA_desde DEFAULT (CAST(GETDATE() AS DATE)),
        nota           NVARCHAR(200) NULL,
        CONSTRAINT CK_CRM_IA_TARIFA_concepto CHECK (concepto IN ('INPUT', 'CACHEADO', 'OUTPUT', 'AUDIO'))
    );
    CREATE UNIQUE INDEX UX_CRM_IA_TARIFA_MODELO
        ON dbo.CRM_IA_TARIFA_MODELO (modelo, concepto, vigente_desde);
END
GO

/* -----------------------------------------------------------------------------
   PLANTILLA DE TARIFAS — descomenta y reemplaza los precios con los de tu
   proveedor. No se cargan valores por defecto a propósito: un precio inventado
   produciría un costo inventado.

INSERT INTO dbo.CRM_IA_TARIFA_MODELO (modelo, concepto, precio, unidad, nota) VALUES
  ('gpt-4o-mini',               'INPUT',    0.000000, 1000000, 'USD por millón de tokens'),
  ('gpt-4o-mini',               'CACHEADO', 0.000000, 1000000, 'USD por millón de tokens'),
  ('gpt-4o-mini',               'OUTPUT',   0.000000, 1000000, 'USD por millón de tokens'),
  ('gpt-4o-transcribe-diarize', 'INPUT',    0.000000, 1000000, 'texto de entrada'),
  ('gpt-4o-transcribe-diarize', 'OUTPUT',   0.000000, 1000000, 'texto de salida'),
  ('gpt-4o-transcribe-diarize', 'AUDIO',    0.000000, 1000000, 'tokens de audio de entrada');
----------------------------------------------------------------------------- */

-- Verificación
SELECT tabla = 'CRM_IA_CONSUMO_API', filas = COUNT(*) FROM dbo.CRM_IA_CONSUMO_API;
SELECT tabla = 'CRM_IA_TARIFA_MODELO', filas = COUNT(*) FROM dbo.CRM_IA_TARIFA_MODELO;
