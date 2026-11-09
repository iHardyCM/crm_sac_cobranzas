/* =====================================================================
   PAUTA GENERAL DE EVALUACION - VERSION 3
   Calibración propuesta por Calidad (28/10/2026)
   Fuente: Propuesta_Calibracion_Pauta_Calidad_COPC.xlsx

   POR QUE
   La v2 era binaria: cada criterio daba el peso completo o cero. Calidad
   reportó que el modelo es demasiado rígido. Esta versión:

   1. Reparte los 100 puntos según el Resumen de la propuesta:
        PECUF Calidad de atención      43
        PECN  Efectividad del negocio  22
        PECC  Cumplimiento y legal     15
        PENC  Experiencia y trato      20
      Dentro de PECN y PECC se repartió en proporción a los puntos de la
      Matriz, que sumaba 115 (31 y 21) y no 100. Decisión del 28/10/2026.

   2. Habilita un único nivel PARCIAL (50% del peso) en seis criterios, cada
      uno con su condición escrita en regla_parcial:
        PECUF.3 Declaración escalonada de montos
        PECN.1  Sondeo y diagnóstico
        PECN.2  Alternativas de pago
        PECN.3  Manejo de objeciones
        PECN.4  Cierre de negociación
        PENC.5  Empatía y disposición de ayuda
      Los demás criterios siguen siendo binarios.

   3. PECUF.3 mantiene el orden estricto de la escalera (16/09/2026). Lo que
      cambia: si declaró la deuda total con su monto y después saltó u omitió
      un nivel, es PARCIAL. Solo es NO_CUMPLE si nunca declaró la deuda total.

   4. PECN.3 deja de aplicar cuando el cliente no objeta (antes se resolvía
      CUMPLE/NO_CUMPLE aunque no hubiera objeción).

   5. PECN.4 vuelve al bloque PECN, con criticidad de negocio (problema 6.3
      del contrato del módulo).

   6. PECC.1 pasa a ser "Identificación del gestor y la entidad", cargado
      como ANULANTE DE BLOQUE: sin peso propio; si el asesor no se identifica
      con su nombre ni con la entidad, el bloque PECC queda en cero.
      PENC.1 queda solo como saludo, para no castigar dos veces lo mismo.

   7. Criterios nuevos:
        PECC.4 Protección de datos (titularidad)    5 pts, binario
        PENC.5 Empatía y disposición de ayuda       8 pts, admite parcial

   8. PECC.3 (tipificación, 4 pts) y PENC.2 (tono, 4 pts) conservan su peso
      dentro de los 100, pero se siguen declarando NO_EVALUABLE: no hay
      fuente para medirlos. Se miden 92 de 100 puntos y el score se calcula
      sobre lo observado.

   COMO SE EJECUTA
   Ejecutar el script completo en SSMS. Tiene tres partes separadas por GO:
     0. Columnas nuevas (admite_parcial, regla_parcial). Idempotente.
     1. Permite PARCIAL_MEDIO como resultado corregido en calibración.
     2. Clona la pauta PUBLICADA (v2) como v3 en BORRADOR y aplica los
        cambios. La v2 no se modifica.
   La v3 se revisa y se publica desde la pantalla Pautas de evaluación.
   Mientras no se publique, las llamadas se siguen evaluando con la v2.

   Las evaluaciones ya hechas NO se recalculan: conservan la pauta con la
   que se evaluaron.
   ===================================================================== */

SET NOCOUNT ON;
GO

/* =====================================================================
   0. Columnas nuevas en CRM_IA_PAUTA_CRITERIO
   (el servidor también las crea al arrancar; aquí por si el script corre
   antes de que la aplicación las haya creado)
   ===================================================================== */
IF COL_LENGTH('CobAuto.dbo.CRM_IA_PAUTA_CRITERIO', 'admite_parcial') IS NULL
    ALTER TABLE CobAuto.dbo.CRM_IA_PAUTA_CRITERIO
        ADD admite_parcial BIT NOT NULL
            CONSTRAINT DF_CRM_IA_PAUTA_CRITERIO_ADMITE_PARCIAL DEFAULT 0;

IF COL_LENGTH('CobAuto.dbo.CRM_IA_PAUTA_CRITERIO', 'regla_parcial') IS NULL
    ALTER TABLE CobAuto.dbo.CRM_IA_PAUTA_CRITERIO
        ADD regla_parcial NVARCHAR(MAX) NULL;
GO

/* =====================================================================
   1. Calibración: Calidad puede corregir un criterio a PARCIAL_MEDIO.
   sys.check_constraints va calificado con CobAuto: el script no hace USE y,
   ejecutado desde otra base, la búsqueda no encontraba la restricción, no la
   borraba e intentaba crearla de nuevo (error 2714 del 28/10/2026).
   El servicio valida además que el criterio admita parcial en la pauta
   con la que se evaluó la llamada.
   ===================================================================== */
IF EXISTS (
    SELECT 1 FROM CobAuto.sys.check_constraints
    WHERE name = 'CK_CRM_IA_CALIB_RESULTADO'
      AND definition NOT LIKE '%PARCIAL_MEDIO%'
)
    ALTER TABLE CobAuto.dbo.CRM_IA_CALIBRACION_CRITERIO
        DROP CONSTRAINT CK_CRM_IA_CALIB_RESULTADO;

IF NOT EXISTS (SELECT 1 FROM CobAuto.sys.check_constraints WHERE name = 'CK_CRM_IA_CALIB_RESULTADO')
    ALTER TABLE CobAuto.dbo.CRM_IA_CALIBRACION_CRITERIO
    ADD CONSTRAINT CK_CRM_IA_CALIB_RESULTADO
        CHECK (
            (accion = 'CORREGIR' AND resultado_esperado IN ('CUMPLE', 'PARCIAL_MEDIO', 'NO_CUMPLE', 'NO_APLICA', 'NO_EVALUABLE'))
         OR (accion = 'CONFIRMAR' AND resultado_esperado IS NULL)
        );
GO

/* =====================================================================
   2. Pauta v3
   ===================================================================== */
SET XACT_ABORT ON;

DECLARE @id_pauta_origen INT;
DECLARE @id_pauta_nueva  INT;
DECLARE @version_nueva   INT;
DECLARE @nombre          NVARCHAR(160);
DECLARE @usuario         NVARCHAR(100) = N'hcruz';

/* ---------- 2.1 Pauta de origen: la publicada ---------- */
SELECT TOP 1 @id_pauta_origen = id_pauta, @nombre = nombre
FROM CobAuto.dbo.CRM_IA_PAUTA
WHERE estado = 'PUBLICADA' AND aplica_todas = 1
ORDER BY version DESC, id_pauta DESC;

IF @id_pauta_origen IS NULL
BEGIN
    RAISERROR('No hay una pauta general PUBLICADA para clonar.', 16, 1);
    RETURN;
END

/* Un segundo borrador de la misma pauta confundiría cuál se publica. */
IF EXISTS (SELECT 1 FROM CobAuto.dbo.CRM_IA_PAUTA WHERE nombre = @nombre AND estado = 'BORRADOR')
BEGIN
    RAISERROR('Ya existe un BORRADOR de esta pauta. Publícalo o elimínalo antes de volver a ejecutar el script.', 16, 1);
    RETURN;
END

SELECT @version_nueva = ISNULL(MAX(version), 0) + 1
FROM CobAuto.dbo.CRM_IA_PAUTA
WHERE nombre = @nombre;

PRINT CONCAT('Clonando pauta ', @id_pauta_origen, ' como versión ', @version_nueva);

BEGIN TRANSACTION;

/* ---------- 2.2 Cabecera ---------- */
INSERT INTO CobAuto.dbo.CRM_IA_PAUTA
    (nombre, version, descripcion, estado, aplica_todas,
     vigencia_desde, vigencia_hasta, creado_por, actualizado_por)
SELECT
    nombre,
    @version_nueva,
    N'Pauta general de evaluación. v3 (calibración de Calidad, 28/10/2026): pesos por bloque PECUF 43, PECN 22, PECC 15, PENC 20; puntaje parcial (50%) en seis criterios; identificación del gestor como anulante del bloque de cumplimiento; nuevos criterios de protección de datos y empatía.',
    'BORRADOR',
    aplica_todas,
    vigencia_desde,
    vigencia_hasta,
    @usuario,
    @usuario
FROM CobAuto.dbo.CRM_IA_PAUTA
WHERE id_pauta = @id_pauta_origen;

SET @id_pauta_nueva = SCOPE_IDENTITY();

/* ---------- 2.3 Bloques ---------- */
DECLARE @mapa_bloques TABLE (id_bloque_origen INT, id_bloque_nuevo INT, codigo NVARCHAR(50));

MERGE CobAuto.dbo.CRM_IA_PAUTA_BLOQUE AS destino
USING (
    SELECT id_bloque, codigo, nombre, categoria, descripcion, orden, activo
    FROM CobAuto.dbo.CRM_IA_PAUTA_BLOQUE
    WHERE id_pauta = @id_pauta_origen
) AS origen
ON 1 = 0
WHEN NOT MATCHED THEN
    INSERT (id_pauta, codigo, nombre, categoria, descripcion, orden, activo)
    VALUES (@id_pauta_nueva, origen.codigo, origen.nombre, origen.categoria,
            origen.descripcion, origen.orden, origen.activo)
OUTPUT origen.id_bloque, inserted.id_bloque, inserted.codigo
INTO @mapa_bloques (id_bloque_origen, id_bloque_nuevo, codigo);

/* ---------- 2.4 Criterios (copia exacta de la v2) ---------- */
INSERT INTO CobAuto.dbo.CRM_IA_PAUTA_CRITERIO
    (id_pauta, id_bloque, codigo_criterio, nombre, tipo_criterio, peso, detalle,
     regla_evaluacion, regla_cumple, regla_no_cumple, regla_aplicabilidad,
     criticidad, fuente_evidencia, requiere_evidencia, puede_descalificar,
     recomendacion, orden, activo, admite_parcial, regla_parcial)
SELECT
    @id_pauta_nueva, M.id_bloque_nuevo, C.codigo_criterio, C.nombre, C.tipo_criterio,
    C.peso, C.detalle, C.regla_evaluacion, C.regla_cumple, C.regla_no_cumple,
    C.regla_aplicabilidad, C.criticidad, C.fuente_evidencia, C.requiere_evidencia,
    C.puede_descalificar, C.recomendacion, C.orden, C.activo, 0, NULL
FROM CobAuto.dbo.CRM_IA_PAUTA_CRITERIO AS C
JOIN @mapa_bloques AS M ON M.id_bloque_origen = C.id_bloque
WHERE C.id_pauta = @id_pauta_origen;

/* ---------- 2.5 Carteras de alcance (si la pauta no aplica a todas) ---------- */
INSERT INTO CobAuto.dbo.CRM_IA_PAUTA_CARTERA (id_pauta, idcartera, grupo_nombre)
SELECT @id_pauta_nueva, idcartera, grupo_nombre
FROM CobAuto.dbo.CRM_IA_PAUTA_CARTERA
WHERE id_pauta = @id_pauta_origen;

/* ---------- 2.6 Criterios nuevos (con peso 0; se fija en 2.7) ---------- */
INSERT INTO CobAuto.dbo.CRM_IA_PAUTA_CRITERIO
    (id_pauta, id_bloque, codigo_criterio, nombre, tipo_criterio, peso, detalle,
     regla_evaluacion, regla_cumple, regla_no_cumple, regla_aplicabilidad,
     criticidad, fuente_evidencia, requiere_evidencia, puede_descalificar,
     recomendacion, orden, activo, admite_parcial, regla_parcial)
SELECT @id_pauta_nueva, M.id_bloque_nuevo, N'PECC.4', N'Protección de datos (titularidad)',
       'PUNTUABLE', 0, N'Confirma la titularidad antes de dar información de la deuda',
       N'Antes de comunicar montos o detalle de la deuda, el asesor confirma que habla con el titular. No exige DNI ni fecha de nacimiento: basta la confirmación de titularidad (por ejemplo, pregunta por el titular por su nombre y la persona confirma que es ella).',
       N'Cumple cuando el asesor confirma que habla con el titular antes de comunicar montos o detalle de la deuda.',
       N'No cumple cuando comunica montos o detalle de la deuda a un tercero, o antes de confirmar que habla con el titular.',
       N'Aplica cuando el asesor comunica montos o detalle de la deuda. Si en la llamada no se comunica información de la deuda, es NO_APLICA.',
       N'ERROR_CRITICO_CUMPLIMIENTO', N'TRANSCRIPCION', 1, 0,
       N'Confirmar que se habla con el titular antes de mencionar cualquier monto; ante un tercero, dejar solo un mensaje de contacto.',
       12, 1, 0, NULL
FROM @mapa_bloques AS M WHERE M.codigo = N'PECC';

INSERT INTO CobAuto.dbo.CRM_IA_PAUTA_CRITERIO
    (id_pauta, id_bloque, codigo_criterio, nombre, tipo_criterio, peso, detalle,
     regla_evaluacion, regla_cumple, regla_no_cumple, regla_aplicabilidad,
     criticidad, fuente_evidencia, requiere_evidencia, puede_descalificar,
     recomendacion, orden, activo, admite_parcial, regla_parcial)
SELECT @id_pauta_nueva, M.id_bloque_nuevo, N'PENC.5', N'Empatía y disposición de ayuda',
       'PUNTUABLE', 0, N'Reconoce la situación del cliente y se ofrece a ayudar',
       N'Cuando el cliente expresa una dificultad, preocupación o malestar, el asesor la reconoce verbalmente y muestra disposición a buscar una solución con él. No se evalúa el tono de voz (PENC.2) ni el manejo de silencios y tiempos (PECUF.2).',
       N'Cumple cuando reconoce verbalmente la situación del cliente (por ejemplo, "entiendo su situación", "lamento lo que me cuenta") y se ofrece a buscar una alternativa con él.',
       N'No cumple cuando el cliente expresa una dificultad o malestar y el asesor la ignora y continúa con la cobranza como si no la hubiera escuchado.',
       N'Aplica cuando el cliente expresa una dificultad, preocupación o malestar. Si no lo hace, es NO_APLICA.',
       N'ERROR_NO_CRITICO', N'TRANSCRIPCION', 0, 0,
       N'Nombrar lo que el cliente contó antes de proponer: "entiendo que este mes se le complicó; veamos juntos una opción".',
       17, 1, 1,
       N'Parcial cuando hace solo una de las dos: reconoce la situación del cliente pero no se ofrece a ayudar, o se ofrece a ayudar sin reconocer lo que el cliente expresó.'
FROM @mapa_bloques AS M WHERE M.codigo = N'PENC';

/* ---------- 2.7 Pesos, orden, bloque y parcial ---------- */
DECLARE @v3 TABLE (
    codigo_criterio NVARCHAR(80) PRIMARY KEY,
    bloque          NVARCHAR(50),
    peso            DECIMAL(10,2),
    orden           INT,
    admite_parcial  BIT
);
INSERT INTO @v3 (codigo_criterio, bloque, peso, orden, admite_parcial) VALUES
    (N'PECUF.1', N'PECUF', 20, 1,  0),
    (N'PECUF.2', N'PECUF',  7, 2,  0),
    (N'PECUF.3', N'PECUF',  9, 3,  1),
    (N'PECUF.4', N'PECUF',  7, 4,  0),
    (N'PECN.1',  N'PECN',   6, 5,  1),
    (N'PECN.2',  N'PECN',   6, 6,  1),
    (N'PECN.3',  N'PECN',   6, 7,  1),
    (N'PECN.4',  N'PECN',   4, 8,  1),
    (N'PECC.1',  N'PECC',   0, 9,  0),   -- anulante: sin peso
    (N'PECC.2',  N'PECC',   6, 10, 0),
    (N'PECC.3',  N'PECC',   4, 11, 0),
    (N'PECC.4',  N'PECC',   5, 12, 0),
    (N'PENC.1',  N'PENC',   2, 13, 0),
    (N'PENC.2',  N'PENC',   4, 14, 0),
    (N'PENC.3',  N'PENC',   4, 15, 0),
    (N'PENC.4',  N'PENC',   2, 16, 0),
    (N'PENC.5',  N'PENC',   8, 17, 1);

/* Todo criterio de la v3 debe estar en la tabla de arriba y viceversa. */
IF EXISTS (
    SELECT codigo_criterio FROM CobAuto.dbo.CRM_IA_PAUTA_CRITERIO WHERE id_pauta = @id_pauta_nueva
    EXCEPT SELECT codigo_criterio FROM @v3
) OR EXISTS (
    SELECT codigo_criterio FROM @v3
    EXCEPT SELECT codigo_criterio FROM CobAuto.dbo.CRM_IA_PAUTA_CRITERIO WHERE id_pauta = @id_pauta_nueva
)
BEGIN
    RAISERROR('Los criterios clonados no coinciden con los 17 esperados de la v3. No se crea nada.', 16, 1);
    ROLLBACK TRANSACTION;
    RETURN;
END

UPDATE C
SET C.peso = V.peso,
    C.orden = V.orden,
    C.admite_parcial = V.admite_parcial,
    C.id_bloque = M.id_bloque_nuevo
FROM CobAuto.dbo.CRM_IA_PAUTA_CRITERIO AS C
JOIN @v3 AS V ON V.codigo_criterio = C.codigo_criterio
JOIN @mapa_bloques AS M ON M.codigo = V.bloque
WHERE C.id_pauta = @id_pauta_nueva;

/* ---------- 2.8 Reglas que cambian ---------- */

-- PECUF.2: silencios justificados no son falta de escucha.
UPDATE CobAuto.dbo.CRM_IA_PAUTA_CRITERIO
SET regla_aplicabilidad = N'Aplica cuando el cliente entrega información, objeta, consulta o requiere comprensión del asesor. Un silencio o una espera justificados ante el cliente (por ejemplo, "permítame un momento, reviso su cuenta") no son falta de escucha.'
WHERE id_pauta = @id_pauta_nueva AND codigo_criterio = N'PECUF.2';

-- PECUF.3: misma escalera estricta; omitir o saltar un nivel después de
-- declarar la deuda total pasa de NO_CUMPLE a PARCIAL.
UPDATE CobAuto.dbo.CRM_IA_PAUTA_CRITERIO
SET regla_cumple = N'Cumple cuando declara la deuda total con su importe y el cliente no la rechaza; o cuando, ante rechazo explícito, ofrece el capital con su importe; o cuando, ante un segundo rechazo, ofrece el monto de campaña. El orden es estricto: deuda total, capital, campaña.',
    regla_no_cumple = N'No cumple cuando no declara la deuda total con su importe en ningún momento de la llamada.',
    regla_parcial = N'Parcial cuando declara la deuda total con su importe, pero ante el rechazo explícito del cliente omite o salta un nivel: no ofrece el capital, pasa a la campaña sin ofrecer antes el capital, o no llega a la campaña tras el rechazo del capital.'
WHERE id_pauta = @id_pauta_nueva AND codigo_criterio = N'PECUF.3';

-- PECN.1: causa o capacidad por separado es diagnóstico incompleto.
UPDATE CobAuto.dbo.CRM_IA_PAUTA_CRITERIO
SET regla_cumple = N'Cumple cuando identifica la causa del atraso y la posibilidad real de pago, preguntando o retomando lo que el cliente cuenta por iniciativa propia; no se exige un cuestionario. Con un tercero, confirma el vínculo o una vía legítima de contacto.',
    regla_no_cumple = N'No cumple cuando, existiendo interacción suficiente, no identifica ni la causa del atraso ni la capacidad de pago, ni realiza el sondeo mínimo frente a un tercero.',
    regla_parcial = N'Parcial cuando identifica solo uno de los dos: la causa del atraso o la capacidad real de pago.'
WHERE id_pauta = @id_pauta_nueva AND codigo_criterio = N'PECN.1';

-- PECN.2: se evalúa lo que ofrece el asesor, no lo que decide el cliente.
UPDATE CobAuto.dbo.CRM_IA_PAUTA_CRITERIO
SET regla_cumple = N'Cumple cuando propone o ajusta una forma de pago concreta -cuotas, plazos, fecha o canal- conectada con lo que el cliente expuso. Cumple aunque el cliente rechace la alternativa.',
    regla_no_cumple = N'No cumple cuando, existiendo oportunidad de negociar, el asesor no ofrece ninguna alternativa de forma de pago.',
    regla_parcial = N'Parcial cuando ofrece una alternativa de forma de pago, pero genérica: no retoma la causa, el ingreso o la fecha que el cliente planteó.'
WHERE id_pauta = @id_pauta_nueva AND codigo_criterio = N'PECN.2';

-- PECN.3: sin objeción no hay nada que rebatir.
UPDATE CobAuto.dbo.CRM_IA_PAUTA_CRITERIO
SET regla_cumple = N'Cumple cuando reconoce la objeción y responde con una alternativa o argumento válido conectado con lo que el cliente planteó, reconduciendo hacia una solución.',
    regla_no_cumple = N'No cumple cuando el cliente objeta y el asesor ignora la objeción, la evade o presiona sin ofrecer alternativa.',
    regla_aplicabilidad = N'Aplica cuando el cliente plantea una objeción, negativa, imposibilidad o postergación. Si el cliente no objeta, es NO_APLICA. También es NO_APLICA ante tercero confirmado o corte abrupto que impida responder.',
    regla_parcial = N'Parcial cuando responde a la objeción de forma incompleta: la reconoce de forma explícita ("entiendo", "comprendo") sin ofrecer una alternativa, o propone una alternativa genérica sin reconocer ni retomar lo que el cliente planteó.'
WHERE id_pauta = @id_pauta_nueva AND codigo_criterio = N'PECN.3';

-- PECN.4: vuelve al bloque de negocio; intentar cerrar sin lograrlo es parcial.
UPDATE CobAuto.dbo.CRM_IA_PAUTA_CRITERIO
SET criticidad = N'ERROR_CRITICO_NEGOCIO',
    regla_no_cumple = N'No cumple cuando, existiendo oportunidad de gestión, el asesor no intenta concretar ningún compromiso, monto, fecha ni siguiente acción.',
    regla_parcial = N'Parcial cuando intenta concretar -pregunta por fecha, monto o una siguiente acción- pero la llamada termina sin una promesa ni una acción verificable aceptada por el cliente.'
WHERE id_pauta = @id_pauta_nueva AND codigo_criterio = N'PECN.4';

-- PECC.1: identificación como anulante del bloque de cumplimiento.
UPDATE CobAuto.dbo.CRM_IA_PAUTA_CRITERIO
SET nombre = N'Identificación del gestor y la entidad',
    tipo_criterio = 'ANULANTE_BLOQUE',
    peso = 0,
    detalle = N'Criterio de control: se identifica con su nombre y en representación de la entidad',
    regla_evaluacion = N'Al inicio de la llamada el asesor dice su nombre e indica la entidad a la que representa (por ejemplo, "le saluda Ana Pérez en representación de Compartamos Banco"). Se nombra la entidad, nunca la campaña interna. Es anulante: si no se cumple, el bloque de cumplimiento queda en cero.',
    regla_cumple = N'Cumple cuando el asesor dice su nombre y la entidad que representa.',
    regla_no_cumple = N'No cumple cuando el asesor no dice ni su nombre ni la entidad que representa. Si solo se reconoce uno de los dos, lo confirma una persona (puede ser una falla de transcripción).',
    regla_aplicabilidad = N'Aplica en toda llamada con intervención audible del asesor.',
    criticidad = N'ERROR_CRITICO_CUMPLIMIENTO',
    fuente_evidencia = N'TRANSCRIPCION',
    requiere_evidencia = 0,
    puede_descalificar = 0,
    admite_parcial = 0,
    regla_parcial = NULL,
    recomendacion = N'Decir al inicio: "le saluda <nombre> en representación de <entidad>".'
WHERE id_pauta = @id_pauta_nueva AND codigo_criterio = N'PECC.1';

-- PECC.2: la confirmación incluye el canal.
UPDATE CobAuto.dbo.CRM_IA_PAUTA_CRITERIO
SET regla_cumple = N'Cumple cuando, ante un acuerdo, recapitula de forma clara para el cliente las condiciones principales: monto, fecha y canal de pago.'
WHERE id_pauta = @id_pauta_nueva AND codigo_criterio = N'PECC.2';

-- PENC.1: solo saludo; la identificación se evalúa en PECC.1.
UPDATE CobAuto.dbo.CRM_IA_PAUTA_CRITERIO
SET regla_evaluacion = N'Saluda al inicio de la interacción de forma natural dentro del flujo de la conversación. La identificación con nombre y entidad se evalúa en PECC.1.',
    regla_cumple = N'Cumple cuando inicia la llamada con un saludo.',
    regla_no_cumple = N'No cumple cuando omite el saludo en una apertura audible.'
WHERE id_pauta = @id_pauta_nueva AND codigo_criterio = N'PENC.1';

/* ---------- 2.9 Controles antes de confirmar ---------- */
DECLARE @suma DECIMAL(10,2) = (
    SELECT SUM(peso) FROM CobAuto.dbo.CRM_IA_PAUTA_CRITERIO
    WHERE id_pauta = @id_pauta_nueva AND activo = 1 AND tipo_criterio = 'PUNTUABLE'
);
IF ISNULL(@suma, 0) <> 100
BEGIN
    DECLARE @suma_txt NVARCHAR(20) = CAST(ISNULL(@suma, 0) AS NVARCHAR(20));
    RAISERROR('Los pesos de la v3 suman %s y no 100. No se crea nada.', 16, 1, @suma_txt);
    ROLLBACK TRANSACTION;
    RETURN;
END

IF EXISTS (
    SELECT 1 FROM CobAuto.dbo.CRM_IA_PAUTA_CRITERIO
    WHERE id_pauta = @id_pauta_nueva AND admite_parcial = 1
      AND (regla_parcial IS NULL OR LTRIM(RTRIM(regla_parcial)) = '')
)
BEGIN
    RAISERROR('Hay criterios que admiten parcial sin regla parcial. No se crea nada.', 16, 1);
    ROLLBACK TRANSACTION;
    RETURN;
END

COMMIT TRANSACTION;

PRINT CONCAT('Pauta v', @version_nueva, ' creada en BORRADOR con id_pauta = ', @id_pauta_nueva);
GO


/* =====================================================================
   VERIFICACION - ejecutar después del script
   ===================================================================== */

-- 1. La v3 existe en BORRADOR y la v2 sigue PUBLICADA
SELECT id_pauta, nombre, version, estado, aplica_todas
FROM CobAuto.dbo.CRM_IA_PAUTA
ORDER BY nombre, version;

-- 2. Pesos por bloque de la v3: PECUF 43, PECN 22, PECC 15, PENC 20 = 100
SELECT B.codigo AS bloque, SUM(C.peso) AS peso, COUNT(*) AS criterios
FROM CobAuto.dbo.CRM_IA_PAUTA_CRITERIO C
JOIN CobAuto.dbo.CRM_IA_PAUTA_BLOQUE B ON B.id_bloque = C.id_bloque
WHERE C.id_pauta = (SELECT MAX(id_pauta) FROM CobAuto.dbo.CRM_IA_PAUTA WHERE estado = 'BORRADOR')
GROUP BY B.codigo
ORDER BY MIN(C.orden);

-- 3. Detalle de la v3
SELECT B.codigo AS bloque, C.codigo_criterio, C.nombre, C.tipo_criterio, C.peso,
       C.admite_parcial, C.fuente_evidencia, C.criticidad, C.regla_parcial
FROM CobAuto.dbo.CRM_IA_PAUTA_CRITERIO C
JOIN CobAuto.dbo.CRM_IA_PAUTA_BLOQUE B ON B.id_bloque = C.id_bloque
WHERE C.id_pauta = (SELECT MAX(id_pauta) FROM CobAuto.dbo.CRM_IA_PAUTA WHERE estado = 'BORRADOR')
ORDER BY C.orden;
GO
