/* =============================================================================
   CRM_IA_PLAN_MEJORA — planes de mejora por agente y criterio
   Base: CobAuto (nivel de compatibilidad 120). Script idempotente: se puede
   ejecutar más de una vez; solo crea lo que falta. No modifica datos existentes.

   REGLAS ACORDADAS (21/09/2026)
   - Unidad: un agente + un criterio de la pauta.
   - Candidato: falla el criterio en 2 o más de sus últimas 5 mediciones,
     con al menos 3 mediciones de ese criterio.
   - Línea base: cumplimiento del criterio en esas últimas mediciones, al crear.
   - Meta: 80% de cumplimiento en las 5 mediciones siguientes a la fecha de inicio.
   - Cierre: CUMPLIDO / NO_CUMPLIDO al completar las 5 mediciones;
             VENCIDO si a los 30 días no se completaron.
   - Medición = resultado vigente del criterio (el calibrado si Calidad publicó
     una corrección) con resultado CUMPLE o NO_CUMPLE.

   El avance NO se guarda: se calcula al leer desde CRM_IA_EVALUACION_CRITERIO,
   para que nunca contradiga a las evaluaciones. Solo se guarda el cierre,
   que lo confirma una persona.
   ============================================================================= */

USE CobAuto;
GO

IF OBJECT_ID('dbo.CRM_IA_PLAN_MEJORA', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.CRM_IA_PLAN_MEJORA (
        id_plan               INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_CRM_IA_PLAN_MEJORA PRIMARY KEY,
        agente                NVARCHAR(200)  NOT NULL,   -- mismo texto que ia_feedback_llamadas.agente
        cartera               NVARCHAR(200)  NULL,
        codigo_criterio       NVARCHAR(80)   NOT NULL,
        nombre_criterio       NVARCHAR(300)  NULL,
        id_pauta              INT            NULL,

        -- Foto al crear el plan (por qué se abrió)
        base_mediciones       INT            NOT NULL,
        base_cumple           INT            NOT NULL,
        motivo                NVARCHAR(1000) NULL,

        -- Compromiso
        accion_acordada       NVARCHAR(1000) NULL,
        responsable           NVARCHAR(200)  NULL,
        meta_pct              DECIMAL(5,2)   NOT NULL CONSTRAINT DF_CRM_IA_PLAN_MEJORA_meta DEFAULT (80),
        mediciones_objetivo   INT            NOT NULL CONSTRAINT DF_CRM_IA_PLAN_MEJORA_med  DEFAULT (5),
        fecha_inicio          DATETIME       NOT NULL CONSTRAINT DF_CRM_IA_PLAN_MEJORA_ini  DEFAULT (GETDATE()),
        fecha_vencimiento     DATETIME       NOT NULL,

        -- Estado
        estado                VARCHAR(20)    NOT NULL CONSTRAINT DF_CRM_IA_PLAN_MEJORA_est  DEFAULT ('ACTIVO'),
        cierre_mediciones     INT            NULL,   -- foto del avance al cerrar
        cierre_cumple         INT            NULL,
        comentario_cierre     NVARCHAR(1000) NULL,

        creado_por            NVARCHAR(200)  NULL,
        fecha_creacion        DATETIME       NOT NULL CONSTRAINT DF_CRM_IA_PLAN_MEJORA_fc   DEFAULT (GETDATE()),
        cerrado_por           NVARCHAR(200)  NULL,
        fecha_cierre          DATETIME       NULL,

        CONSTRAINT CK_CRM_IA_PLAN_MEJORA_estado
            CHECK (estado IN ('ACTIVO', 'CUMPLIDO', 'NO_CUMPLIDO', 'VENCIDO', 'ANULADO')),
        CONSTRAINT CK_CRM_IA_PLAN_MEJORA_meta
            CHECK (meta_pct > 0 AND meta_pct <= 100 AND mediciones_objetivo > 0)
    );
END
GO

-- Un solo plan ACTIVO por agente y criterio.
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'UX_CRM_IA_PLAN_MEJORA_activo'
               AND object_id = OBJECT_ID('dbo.CRM_IA_PLAN_MEJORA'))
    CREATE UNIQUE INDEX UX_CRM_IA_PLAN_MEJORA_activo
        ON dbo.CRM_IA_PLAN_MEJORA (agente, codigo_criterio)
        WHERE estado = 'ACTIVO';
GO

-- Para calcular el avance: mediciones de un criterio por llamada.
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_CRM_IA_EVALUACION_CRITERIO_codigo'
               AND object_id = OBJECT_ID('dbo.CRM_IA_EVALUACION_CRITERIO'))
    CREATE INDEX IX_CRM_IA_EVALUACION_CRITERIO_codigo
        ON dbo.CRM_IA_EVALUACION_CRITERIO (codigo_criterio, id_feedback)
        INCLUDE (resultado_ia);
GO

-- Verificación
SELECT name, type_desc FROM sys.indexes WHERE object_id = OBJECT_ID('dbo.CRM_IA_PLAN_MEJORA');
SELECT COUNT(*) AS planes FROM dbo.CRM_IA_PLAN_MEJORA;
