/* =====================================================================
   Feedback_IA - Base de calibracion y medicion de precision
   Base de datos: CobAuto
   Script idempotente. Se puede ejecutar varias veces sin efecto adicional.
   No modifica ni borra datos existentes de ia_feedback_llamadas.

   Contenido:
     1. CRM_IA_CALIBRACION_MOTIVO      catalogo de motivos de calibracion
     2. CRM_IA_EVALUACION_CRITERIO     resultado IA por criterio (INMUTABLE)
     3. CRM_IA_CALIBRACION_CRITERIO    acto humano sobre cada criterio
     4. Columnas nuevas en ia_feedback_llamadas (scores y trazabilidad de pauta)
     5. Carga inicial del catalogo de motivos
   ===================================================================== */

USE CobAuto;
GO

/* ---------------------------------------------------------------------
   1. CATALOGO DE MOTIVOS DE CALIBRACION
   Tabla, no CHECK: el catalogo crece sin tocar el esquema y las
   calibraciones historicas conservan su motivo original.
   categoria indica donde actuar: IA (prompt/modelo), PAUTA (definicion),
   FUENTE (audio, diarizacion, datos no disponibles).
   --------------------------------------------------------------------- */
IF OBJECT_ID('CobAuto.dbo.CRM_IA_CALIBRACION_MOTIVO', 'U') IS NULL
BEGIN
    CREATE TABLE CobAuto.dbo.CRM_IA_CALIBRACION_MOTIVO (
        id_motivo           INT IDENTITY(1,1) PRIMARY KEY,
        codigo              VARCHAR(50)   NOT NULL,
        nombre              NVARCHAR(200) NOT NULL,
        descripcion         NVARCHAR(MAX) NULL,
        prueba_decision     NVARCHAR(MAX) NULL,   -- como decidir si aplica este motivo
        categoria           VARCHAR(20)   NOT NULL,  -- IA | PAUTA | FUENTE
        aplica_resultado    BIT NOT NULL DEFAULT 1,  -- usable cuando se corrige el resultado
        aplica_evidencia    BIT NOT NULL DEFAULT 1,  -- usable cuando se objeta la evidencia
        orden               INT NOT NULL DEFAULT 1,
        activo              BIT NOT NULL DEFAULT 1,
        fecha_creacion      DATETIME NOT NULL DEFAULT GETDATE(),
        CONSTRAINT UQ_CRM_IA_CALIB_MOTIVO_CODIGO UNIQUE (codigo)
    );
END;
GO

/* ---------------------------------------------------------------------
   2. EVALUACION IA POR CRITERIO  -  INMUTABLE
   Una fila por (id_feedback, codigo_criterio), escrita una sola vez al
   finalizar el analisis. NUNCA se actualiza: es el registro contra el que
   se mide la precision. Las correcciones viven en la tabla 3.
   --------------------------------------------------------------------- */
IF OBJECT_ID('CobAuto.dbo.CRM_IA_EVALUACION_CRITERIO', 'U') IS NULL
BEGIN
    CREATE TABLE CobAuto.dbo.CRM_IA_EVALUACION_CRITERIO (
        id_evaluacion_criterio  BIGINT IDENTITY(1,1) PRIMARY KEY,
        id_feedback             INT NOT NULL,

        -- trazabilidad de la pauta usada en ESE analisis
        id_pauta                INT NULL,
        pauta_version           INT NULL,
        codigo_bloque           VARCHAR(50)  NULL,
        nombre_bloque           NVARCHAR(180) NULL,

        -- definicion del criterio congelada al momento del analisis
        codigo_criterio         VARCHAR(80)  NOT NULL,
        nombre_criterio         NVARCHAR(220) NULL,
        tipo_criterio           VARCHAR(30)  NULL,   -- PUNTUABLE | ANULANTE_BLOQUE
        peso                    DECIMAL(10,2) NULL,
        fuente_evidencia        VARCHAR(30)  NULL,

        -- resultado de la IA
        resultado_ia            VARCHAR(20)  NOT NULL,  -- CUMPLE | NO_CUMPLE | NO_APLICA | NO_EVALUABLE
        puntaje_obtenido        DECIMAL(10,2) NULL,
        bloque_anulado          BIT NOT NULL DEFAULT 0,
        confianza_ia            VARCHAR(20)  NULL,      -- ALTA | MEDIA | BAJA
        motivo_ia               NVARCHAR(MAX) NULL,     -- justificacion dada por la IA
        recomendacion_ia        NVARCHAR(MAX) NULL,

        -- evidencia citada por la IA
        evidencia_texto         NVARCHAR(MAX) NULL,
        evidencia_hablante      VARCHAR(20)  NULL,      -- AGENTE | CLIENTE | INDETERMINADO
        momento_llamada         VARCHAR(30)  NULL,      -- INICIO | DESARROLLO | CIERRE u hh:mm:ss

        fecha_registro          DATETIME NOT NULL DEFAULT GETDATE(),

        CONSTRAINT UQ_CRM_IA_EVAL_CRITERIO UNIQUE (id_feedback, codigo_criterio)
    );

    CREATE INDEX IX_CRM_IA_EVAL_CRITERIO_FEEDBACK
        ON CobAuto.dbo.CRM_IA_EVALUACION_CRITERIO (id_feedback);

    CREATE INDEX IX_CRM_IA_EVAL_CRITERIO_PAUTA
        ON CobAuto.dbo.CRM_IA_EVALUACION_CRITERIO (id_pauta, pauta_version, codigo_criterio)
        INCLUDE (resultado_ia);
END;
GO

/* ---------------------------------------------------------------------
   3. CALIBRACION HUMANA POR CRITERIO
   Un acto explicito de Calidad sobre un criterio evaluado.
   Solo los criterios con una fila aqui entran al denominador de precision.
   Un criterio sin fila es un no-dato, no una coincidencia.

   accion            se refiere al RESULTADO del criterio
   evidencia_valida  es independiente del resultado
   estado            BORRADOR -> EN_REVISION -> PUBLICADA | RECHAZADA
                     Solo PUBLICADA afecta el score de la llamada.
   --------------------------------------------------------------------- */
IF OBJECT_ID('CobAuto.dbo.CRM_IA_CALIBRACION_CRITERIO', 'U') IS NULL
BEGIN
    CREATE TABLE CobAuto.dbo.CRM_IA_CALIBRACION_CRITERIO (
        id_calibracion          BIGINT IDENTITY(1,1) PRIMARY KEY,
        id_evaluacion_criterio  BIGINT NOT NULL,
        id_feedback             INT NOT NULL,          -- denormalizado para filtros
        codigo_criterio         VARCHAR(80) NOT NULL,  -- denormalizado, congelado

        accion                  VARCHAR(20) NOT NULL,  -- CONFIRMAR | CORREGIR
        resultado_esperado      VARCHAR(20) NULL,      -- obligatorio si accion = CORREGIR
        evidencia_valida        VARCHAR(10) NOT NULL,  -- SI | NO | PARCIAL
        id_motivo               INT NULL,              -- obligatorio salvo CONFIRMAR + evidencia SI

        evidencia_revisor       NVARCHAR(MAX) NULL,    -- cita correcta segun Calidad
        comentario              NVARCHAR(MAX) NULL,

        estado                  VARCHAR(20) NOT NULL DEFAULT 'BORRADOR',

        creado_por              VARCHAR(150) NULL,
        fecha_creacion          DATETIME NOT NULL DEFAULT GETDATE(),
        actualizado_por         VARCHAR(150) NULL,
        fecha_actualizacion     DATETIME NOT NULL DEFAULT GETDATE(),
        revisado_por            VARCHAR(150) NULL,
        fecha_revision          DATETIME NULL,
        publicado_por           VARCHAR(150) NULL,
        fecha_publicacion       DATETIME NULL,
        motivo_rechazo          NVARCHAR(MAX) NULL,

        CONSTRAINT FK_CRM_IA_CALIB_EVALUACION
            FOREIGN KEY (id_evaluacion_criterio)
            REFERENCES CobAuto.dbo.CRM_IA_EVALUACION_CRITERIO (id_evaluacion_criterio),
        CONSTRAINT FK_CRM_IA_CALIB_MOTIVO
            FOREIGN KEY (id_motivo)
            REFERENCES CobAuto.dbo.CRM_IA_CALIBRACION_MOTIVO (id_motivo)
    );

    /* Un solo acto vigente por criterio. Si se rechaza, se puede volver a calibrar. */
    CREATE UNIQUE INDEX UX_CRM_IA_CALIB_VIGENTE
        ON CobAuto.dbo.CRM_IA_CALIBRACION_CRITERIO (id_evaluacion_criterio)
        WHERE estado <> 'RECHAZADA';

    CREATE INDEX IX_CRM_IA_CALIB_FEEDBACK
        ON CobAuto.dbo.CRM_IA_CALIBRACION_CRITERIO (id_feedback, estado);

    CREATE INDEX IX_CRM_IA_CALIB_MOTIVO
        ON CobAuto.dbo.CRM_IA_CALIBRACION_CRITERIO (id_motivo, estado)
        INCLUDE (codigo_criterio, accion, evidencia_valida);
END;
GO

/* ---------------------------------------------------------------------
   3.b Reglas de dominio e integridad del acto humano
   Estas son las unicas restricciones incluidas. No son controles
   operativos: sostienen directamente la validez de la metrica.
   Si en pruebas estorban, se pueden desactivar con:
       ALTER TABLE ... NOCHECK CONSTRAINT <nombre>
   --------------------------------------------------------------------- */
IF NOT EXISTS (SELECT 1 FROM sys.check_constraints WHERE name = 'CK_CRM_IA_CALIB_ACCION')
    ALTER TABLE CobAuto.dbo.CRM_IA_CALIBRACION_CRITERIO
    ADD CONSTRAINT CK_CRM_IA_CALIB_ACCION
        CHECK (accion IN ('CONFIRMAR', 'CORREGIR'));
GO

IF NOT EXISTS (SELECT 1 FROM sys.check_constraints WHERE name = 'CK_CRM_IA_CALIB_EVIDENCIA')
    ALTER TABLE CobAuto.dbo.CRM_IA_CALIBRACION_CRITERIO
    ADD CONSTRAINT CK_CRM_IA_CALIB_EVIDENCIA
        CHECK (evidencia_valida IN ('SI', 'NO', 'PARCIAL'));
GO

IF NOT EXISTS (SELECT 1 FROM sys.check_constraints WHERE name = 'CK_CRM_IA_CALIB_ESTADO')
    ALTER TABLE CobAuto.dbo.CRM_IA_CALIBRACION_CRITERIO
    ADD CONSTRAINT CK_CRM_IA_CALIB_ESTADO
        CHECK (estado IN ('BORRADOR', 'EN_REVISION', 'PUBLICADA', 'RECHAZADA'));
GO

/* CORREGIR exige resultado esperado; CONFIRMAR no lo lleva. */
IF NOT EXISTS (SELECT 1 FROM sys.check_constraints WHERE name = 'CK_CRM_IA_CALIB_RESULTADO')
    ALTER TABLE CobAuto.dbo.CRM_IA_CALIBRACION_CRITERIO
    ADD CONSTRAINT CK_CRM_IA_CALIB_RESULTADO
        CHECK (
            (accion = 'CORREGIR' AND resultado_esperado IN ('CUMPLE', 'NO_CUMPLE', 'NO_APLICA', 'NO_EVALUABLE'))
         OR (accion = 'CONFIRMAR' AND resultado_esperado IS NULL)
        );
GO

/* Motivo obligatorio salvo confirmacion limpia (resultado y evidencia correctos). */
IF NOT EXISTS (SELECT 1 FROM sys.check_constraints WHERE name = 'CK_CRM_IA_CALIB_MOTIVO_OBLIG')
    ALTER TABLE CobAuto.dbo.CRM_IA_CALIBRACION_CRITERIO
    ADD CONSTRAINT CK_CRM_IA_CALIB_MOTIVO_OBLIG
        CHECK (
            (accion = 'CONFIRMAR' AND evidencia_valida = 'SI' AND id_motivo IS NULL)
         OR id_motivo IS NOT NULL
        );
GO

/* ---------------------------------------------------------------------
   4. COLUMNAS NUEVAS EN ia_feedback_llamadas
   score_calidad_ia  ya existe y queda como score IA congelado.
   score_calibrado   solo se llena con calibraciones PUBLICADAS.
   score_final       pasa a ser el score vigente (lo que ya lee el frontend).
   origen_score      dice de donde viene el score_final mostrado.
   --------------------------------------------------------------------- */
IF COL_LENGTH('CobAuto.dbo.ia_feedback_llamadas', 'score_calibrado') IS NULL
    ALTER TABLE CobAuto.dbo.ia_feedback_llamadas
    ADD score_calibrado DECIMAL(5,2) NULL;
GO

IF COL_LENGTH('CobAuto.dbo.ia_feedback_llamadas', 'origen_score') IS NULL
    ALTER TABLE CobAuto.dbo.ia_feedback_llamadas
    ADD origen_score VARCHAR(20) NULL;   -- IA | CALIBRACION
GO

IF COL_LENGTH('CobAuto.dbo.ia_feedback_llamadas', 'id_pauta') IS NULL
    ALTER TABLE CobAuto.dbo.ia_feedback_llamadas
    ADD id_pauta INT NULL;
GO

IF COL_LENGTH('CobAuto.dbo.ia_feedback_llamadas', 'pauta_version') IS NULL
    ALTER TABLE CobAuto.dbo.ia_feedback_llamadas
    ADD pauta_version INT NULL;
GO

IF COL_LENGTH('CobAuto.dbo.ia_feedback_llamadas', 'caso_referencia') IS NULL
    ALTER TABLE CobAuto.dbo.ia_feedback_llamadas
    ADD caso_referencia BIT NOT NULL DEFAULT 0;   -- banco de casos aprobados por Calidad
GO

IF COL_LENGTH('CobAuto.dbo.ia_feedback_llamadas', 'fecha_caso_referencia') IS NULL
    ALTER TABLE CobAuto.dbo.ia_feedback_llamadas
    ADD fecha_caso_referencia DATETIME NULL;
GO

IF COL_LENGTH('CobAuto.dbo.ia_feedback_llamadas', 'aprobado_caso_por') IS NULL
    ALTER TABLE CobAuto.dbo.ia_feedback_llamadas
    ADD aprobado_caso_por VARCHAR(150) NULL;
GO

/* ---------------------------------------------------------------------
   5. CARGA INICIAL DEL CATALOGO DE MOTIVOS
   Inserta solo los que no existan. No modifica los ya cargados.
   --------------------------------------------------------------------- */
MERGE CobAuto.dbo.CRM_IA_CALIBRACION_MOTIVO AS destino
USING (VALUES
    ('RESULTADO_INCORRECTO',
     N'La IA calificó mal el criterio',
     N'El resultado del criterio es incorrecto: cambia entre Cumple, No cumple o No aplica.',
     N'El resultado asignado no corresponde a lo ocurrido en la llamada.',
     'IA', 1, 0, 1),

    ('EVIDENCIA_NO_EXISTE',
     N'La evidencia citada no existe en la llamada',
     N'La IA citó una frase que no aparece en la transcripción. Caso crítico para precisión.',
     N'Buscar la cita literal en la transcripción. Si no aparece, es este motivo.',
     'IA', 1, 1, 2),

    ('EVIDENCIA_INCORRECTA',
     N'La cita existe pero no sustenta la conclusión',
     N'La conclusión puede ser válida, pero la evidencia elegida no la respalda.',
     N'La cita existe en la transcripción, pero no demuestra lo que la IA concluyó.',
     'IA', 1, 1, 3),

    ('EVIDENCIA_INCOMPLETA',
     N'La evidencia es parcial o le falta contexto',
     N'La cita apunta al lugar correcto pero omite parte necesaria para sostener el criterio.',
     N'La cita existe y apunta bien, pero le falta una porción del intercambio.',
     'IA', 1, 1, 4),

    ('REGLA_MAL_APLICADA',
     N'La IA aplicó mal una condición de la pauta',
     N'La regla de evaluación, la aplicabilidad o el criterio anulante fueron interpretados incorrectamente. La pauta está bien definida.',
     N'La regla de la pauta es clara, pero la IA no la aplicó como está escrita.',
     'IA', 1, 0, 5),

    ('ROL_INCORRECTO',
     N'Frase atribuida al hablante equivocado',
     N'Problema de diarización: lo dicho por el cliente se atribuyó al agente o viceversa.',
     N'El contenido de la cita es correcto, pero el hablante asignado no lo es.',
     'FUENTE', 1, 1, 6),

    ('TRANSCRIPCION_INCORRECTA',
     N'El audio fue entendido de forma errónea',
     N'Ruido, nombres, montos o frases mal transcritos que cambian la evaluación.',
     N'Al escuchar el audio, lo transcrito no coincide con lo dicho.',
     'FUENTE', 1, 1, 7),

    ('CRITERIO_NO_EVALUABLE',
     N'El criterio requería una fuente no disponible',
     N'Falta información de sistema, tipificación o el audio es insuficiente para evaluar el criterio.',
     N'Con la fuente disponible, ningún evaluador humano podría concluir el criterio.',
     'FUENTE', 1, 0, 8),

    ('CRITERIO_AMBIGUO',
     N'La pauta necesita mejor definición',
     N'La regla admite más de una lectura razonable. Corresponde ajustar la pauta, no el prompt.',
     N'Dos evaluadores humanos con la misma regla podrían concluir distinto.',
     'PAUTA', 1, 1, 9)
) AS origen (codigo, nombre, descripcion, prueba_decision, categoria, aplica_resultado, aplica_evidencia, orden)
    ON destino.codigo = origen.codigo
WHEN NOT MATCHED BY TARGET THEN
    INSERT (codigo, nombre, descripcion, prueba_decision, categoria, aplica_resultado, aplica_evidencia, orden, activo)
    VALUES (origen.codigo, origen.nombre, origen.descripcion, origen.prueba_decision,
            origen.categoria, origen.aplica_resultado, origen.aplica_evidencia, origen.orden, 1);
GO

/* ---------------------------------------------------------------------
   VERIFICACION
   --------------------------------------------------------------------- */
SELECT codigo, categoria, aplica_resultado, aplica_evidencia, activo
FROM CobAuto.dbo.CRM_IA_CALIBRACION_MOTIVO
ORDER BY orden;

SELECT
    (SELECT COUNT(*) FROM CobAuto.dbo.CRM_IA_CALIBRACION_MOTIVO)    AS motivos,
    (SELECT COUNT(*) FROM CobAuto.dbo.CRM_IA_EVALUACION_CRITERIO)   AS criterios_evaluados,
    (SELECT COUNT(*) FROM CobAuto.dbo.CRM_IA_CALIBRACION_CRITERIO)  AS actos_calibracion;
GO
