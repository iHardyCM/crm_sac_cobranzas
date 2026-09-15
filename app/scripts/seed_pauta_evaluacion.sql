/* =====================================================================
   Feedback_IA - Carga inicial de pauta de evaluacion
   Base de datos: CobAuto

   Genera UNA pauta en estado BORRADOR a partir de la pauta vigente en
   codigo (app/services/mibanco_quality_pauta.py). Contenido identico al
   actual: mismos codigos, pesos, reglas y asignacion de bloque.

   NOTA CONOCIDA: el criterio PECN.4 (Cierre de negociacion) esta
   asignado al bloque PECC en el codigo fuente. Se conserva tal cual
   para no alterar la nota de las llamadas ya evaluadas. Si debe
   corregirse, hacerlo como una version nueva de la pauta.

   COMO USARLO
     1. Ajustar el bloque de PARAMETROS de abajo.
     2. Ejecutar. Crea la pauta en BORRADOR (no publica).
     3. Revisar y publicar desde la pantalla de Pautas de evaluacion,
        para que publicar_pauta archive correctamente pautas en conflicto.
     4. Repetir cambiando los PARAMETROS para la siguiente cartera.

   Idempotente: si ya existe una pauta con ese nombre y version, no hace nada.
   ===================================================================== */

USE CobAuto;
GO

SET NOCOUNT ON;

/* ------------------------- PARAMETROS ------------------------- */
DECLARE @nombre         NVARCHAR(160) = N'Pauta de evaluacion MiBanco';
DECLARE @descripcion    NVARCHAR(MAX) = N'Pauta base de monitoreo de calidad. Migrada desde la definicion en codigo.';
DECLARE @version        INT           = 1;
DECLARE @aplica_todas   BIT           = 0;
DECLARE @grupo_nombre   NVARCHAR(120) = N'MiBanco';
DECLARE @usuario        VARCHAR(80)   = 'carga_inicial';
DECLARE @vigencia_desde DATE          = NULL;
DECLARE @vigencia_hasta DATE          = NULL;

/* Carteras de alcance. MiBanco: 112 y 135. Compartamos Castigo Individual: 124. */
DECLARE @carteras TABLE (idcartera INT PRIMARY KEY);
INSERT INTO @carteras (idcartera) VALUES (112), (135);
/* --------------------------------------------------------------- */

IF EXISTS (SELECT 1 FROM CobAuto.dbo.CRM_IA_PAUTA
           WHERE nombre = @nombre AND version = @version)
BEGIN
    PRINT 'La pauta ya existe. No se realizaron cambios.';
    RETURN;
END

DECLARE @id_pauta INT;
DECLARE @id_bloque INT;

BEGIN TRY
BEGIN TRAN;

INSERT INTO CobAuto.dbo.CRM_IA_PAUTA
    (nombre, version, descripcion, estado, aplica_todas,
     vigencia_desde, vigencia_hasta, creado_por, actualizado_por)
VALUES
    (@nombre, @version, @descripcion, 'BORRADOR', @aplica_todas,
     @vigencia_desde, @vigencia_hasta, @usuario, @usuario);

SET @id_pauta = SCOPE_IDENTITY();

INSERT INTO CobAuto.dbo.CRM_IA_PAUTA_CARTERA (id_pauta, idcartera, grupo_nombre)
SELECT @id_pauta, idcartera, @grupo_nombre FROM @carteras;


/* ---------- BLOQUE PECUF ---------- */
INSERT INTO CobAuto.dbo.CRM_IA_PAUTA_BLOQUE
    (id_pauta, codigo, nombre, categoria, descripcion, orden, activo)
VALUES
    (@id_pauta, N'PECUF', N'Precisión de Error Crítico Usuario Final', N'PEC',
     N'Evalua conductas y comunicaciones del agente que pueden afectar directamente al usuario final, incluyendo el trato, la escucha y la claridad de la informacion entregada.', 1, 1);
SET @id_bloque = SCOPE_IDENTITY();

INSERT INTO CobAuto.dbo.CRM_IA_PAUTA_CRITERIO
    (id_pauta, id_bloque, codigo_criterio, nombre, tipo_criterio, peso, detalle,
     regla_evaluacion, regla_cumple, regla_no_cumple, regla_aplicabilidad,
     criticidad, fuente_evidencia, requiere_evidencia, puede_descalificar,
     recomendacion, orden, activo)
VALUES
    (@id_pauta, @id_bloque, N'PECUF.1', N'Falta de respeto',
     'PUNTUABLE', 20.0, N'Mantiene respeto durante toda la llamada',
     N'No agrede, ridiculiza, descalifica ni utiliza expresiones ofensivas. Una agresión grave se considera causal de descalificación según la regla crítica transversal.',
     N'Cumple cuando el agente mantiene un trato respetuoso, sin insultos, burlas, humillación, descalificación ni juicio ofensivo.',
     N'No cumple cuando el agente profiere insultos, ridiculiza, humilla, desacredita o usa expresiones ofensivas contra el cliente.',
     N'Aplica a toda interacción audible del asesor.',
     N'ERROR_CRITICO_USUARIO_FINAL', N'AUDIO',
     1, 1,
     NULL, 1, 1);

INSERT INTO CobAuto.dbo.CRM_IA_PAUTA_CRITERIO
    (id_pauta, id_bloque, codigo_criterio, nombre, tipo_criterio, peso, detalle,
     regla_evaluacion, regla_cumple, regla_no_cumple, regla_aplicabilidad,
     criticidad, fuente_evidencia, requiere_evidencia, puede_descalificar,
     recomendacion, orden, activo)
VALUES
    (@id_pauta, @id_bloque, N'PECUF.2', N'Escucha activa',
     'PUNTUABLE', 2.0, N'Escucha, comprende y confirma',
     N'Evita interrupciones inoportunas, comprende lo expresado por el cliente y realiza preguntas de confirmación cuando la información no es clara.',
     N'Cumple cuando escucha la explicación, responde a lo planteado y confirma o profundiza cuando es necesario.',
     N'No cumple cuando interrumpe de forma improcedente, ignora la explicación del cliente o continúa sin atender su consulta u objeción.',
     N'Aplica cuando el cliente entrega información, objeta, consulta o requiere comprensión del asesor.',
     N'ERROR_CRITICO_USUARIO_FINAL', N'AUDIO',
     1, 0,
     NULL, 2, 1);

INSERT INTO CobAuto.dbo.CRM_IA_PAUTA_CRITERIO
    (id_pauta, id_bloque, codigo_criterio, nombre, tipo_criterio, peso, detalle,
     regla_evaluacion, regla_cumple, regla_no_cumple, regla_aplicabilidad,
     criticidad, fuente_evidencia, requiere_evidencia, puede_descalificar,
     recomendacion, orden, activo)
VALUES
    (@id_pauta, @id_bloque, N'PECUF.3', N'Precisión de la información de la deuda',
     'PUNTUABLE', 5.0, N'Comunica información financiera exacta',
     N'Brinda únicamente datos vigentes y verificables: deuda, días de mora, producto, cuota u otros conceptos que correspondan al caso.',
     N'Cumple cuando los datos de deuda comunicados por el agente coinciden con la fuente disponible y se explican sin contradicción.',
     N'No cumple cuando comunica un monto, producto, mora, cuota o condición incorrecta frente a la fuente verificable disponible.',
     N'Aplica cuando el asesor comunica deuda, mora, producto, cuota, monto u otros datos financieros.',
     N'ERROR_CRITICO_USUARIO_FINAL', N'MULTIFUENTE',
     1, 0,
     NULL, 3, 1);

INSERT INTO CobAuto.dbo.CRM_IA_PAUTA_CRITERIO
    (id_pauta, id_bloque, codigo_criterio, nombre, tipo_criterio, peso, detalle,
     regla_evaluacion, regla_cumple, regla_no_cumple, regla_aplicabilidad,
     criticidad, fuente_evidencia, requiere_evidencia, puede_descalificar,
     recomendacion, orden, activo)
VALUES
    (@id_pauta, @id_bloque, N'PECUF.4', N'Claridad con la información',
     'PUNTUABLE', 3.0, N'Explicación clara y coherente',
     N'Se expresa con orden, no se contradice, responde de forma comprensible y transmite seguridad sin generar confusión.',
     N'Cumple cuando explica montos, condiciones y alternativas con orden, coherencia y lenguaje comprensible.',
     N'No cumple cuando la explicación contradice información previa, resulta confusa o impide al cliente comprender la gestión.',
     N'Aplica cuando el asesor entrega información o explica condiciones durante la llamada.',
     N'ERROR_CRITICO_USUARIO_FINAL', N'TRANSCRIPCION',
     1, 0,
     NULL, 4, 1);


/* ---------- BLOQUE PECN ---------- */
INSERT INTO CobAuto.dbo.CRM_IA_PAUTA_BLOQUE
    (id_pauta, codigo, nombre, categoria, descripcion, orden, activo)
VALUES
    (@id_pauta, N'PECN', N'Precisión de Error Crítico del Negocio', N'PEC',
     N'Evalua la calidad de la gestion de cobranza: diagnostico de la situacion, desarrollo de alternativas, manejo de objeciones y conduccion hacia una solucion o compromiso.', 2, 1);
SET @id_bloque = SCOPE_IDENTITY();

INSERT INTO CobAuto.dbo.CRM_IA_PAUTA_CRITERIO
    (id_pauta, id_bloque, codigo_criterio, nombre, tipo_criterio, peso, detalle,
     regla_evaluacion, regla_cumple, regla_no_cumple, regla_aplicabilidad,
     criticidad, fuente_evidencia, requiere_evidencia, puede_descalificar,
     recomendacion, orden, activo)
VALUES
    (@id_pauta, @id_bloque, N'PECN.1', N'Sondeo y diagnóstico',
     'PUNTUABLE', 5.0, N'Identifica causa y capacidad de pago',
     N'Realiza preguntas de diagnóstico y seguimiento para comprender la causa del no pago, intención y capacidad, sin convertir el sondeo en un interrogatorio.',
     N'Cumple cuando sondea la causa del atraso y la posibilidad real de pago; con tercero, confirma el vínculo o una vía legítima de contacto.',
     N'No cumple cuando, existiendo interacción suficiente, no indaga causa, situación o posibilidad de pago, ni realiza el sondeo mínimo frente a un tercero.',
     N'Aplica en toda interacción de cobranza, incluso con tercero: el asesor debe sondear si existe vínculo, conocimiento del titular o una vía legítima de contacto. No usa NO_APLICA.',
     N'ERROR_CRITICO_NEGOCIO', N'TRANSCRIPCION',
     1, 0,
     NULL, 5, 1);

INSERT INTO CobAuto.dbo.CRM_IA_PAUTA_CRITERIO
    (id_pauta, id_bloque, codigo_criterio, nombre, tipo_criterio, peso, detalle,
     regla_evaluacion, regla_cumple, regla_no_cumple, regla_aplicabilidad,
     criticidad, fuente_evidencia, requiere_evidencia, puede_descalificar,
     recomendacion, orden, activo)
VALUES
    (@id_pauta, @id_bloque, N'PECN.2', N'Negociación escalonada',
     'PUNTUABLE', 10.0, N'Propone alternativas orientadas al pago',
     N'Construye una propuesta acorde con el diagnóstico, presenta alternativas válidas y busca una acción concreta de pago dentro de las opciones autorizadas.',
     N'Cumple cuando propone o ajusta alternativas de pago según el diagnóstico, buscando una opción concreta y viable.',
     N'No cumple cuando existe oportunidad de negociar y el agente no desarrolla una alternativa posterior o la propuesta ignora la situación planteada.',
     N'Aplica en toda conversación con el titular. Solo puede ser NO_APLICA ante tercero confirmado o corte abrupto que impida responder; una propuesta sola no equivale a compromiso.',
     N'ERROR_CRITICO_NEGOCIO', N'TRANSCRIPCION',
     1, 0,
     NULL, 6, 1);

INSERT INTO CobAuto.dbo.CRM_IA_PAUTA_CRITERIO
    (id_pauta, id_bloque, codigo_criterio, nombre, tipo_criterio, peso, detalle,
     regla_evaluacion, regla_cumple, regla_no_cumple, regla_aplicabilidad,
     criticidad, fuente_evidencia, requiere_evidencia, puede_descalificar,
     recomendacion, orden, activo)
VALUES
    (@id_pauta, @id_bloque, N'PECN.3', N'Manejo de objeciones',
     'PUNTUABLE', 15.0, N'Argumenta según la objeción',
     N'Es una respuesta ante la negativa del cliente utilizando argumentos sólidos y válidos alineados a la objeción expuesta por el cliente.',
     N'Cumple cuando reconoce la objeción, responde con una alternativa o argumento válido y reconduce la conversación hacia una solución.',
     N'No cumple cuando el cliente objeta o expresa imposibilidad y el agente no responde a esa objeción, la evade o presiona sin alternativa.',
     N'Aplica en toda conversación con el titular. Ante objeción, rechazo, imposibilidad o postergación evalúa la respuesta posterior. Solo puede ser NO_APLICA ante tercero confirmado o corte abrupto que impida responder.',
     N'ERROR_CRITICO_NEGOCIO', N'TRANSCRIPCION',
     1, 0,
     NULL, 7, 1);


/* ---------- BLOQUE PECC ---------- */
INSERT INTO CobAuto.dbo.CRM_IA_PAUTA_BLOQUE
    (id_pauta, codigo, nombre, categoria, descripcion, orden, activo)
VALUES
    (@id_pauta, N'PECC', N'Precisión de Error Crítico de Cumplimiento', N'PEC',
     N'Evalua el cumplimiento operativo y la comunicacion de acuerdos, asi como la correcta relacion del agente con la entidad, sus procesos y sus canales.', 3, 1);
SET @id_bloque = SCOPE_IDENTITY();

INSERT INTO CobAuto.dbo.CRM_IA_PAUTA_CRITERIO
    (id_pauta, id_bloque, codigo_criterio, nombre, tipo_criterio, peso, detalle,
     regla_evaluacion, regla_cumple, regla_no_cumple, regla_aplicabilidad,
     criticidad, fuente_evidencia, requiere_evidencia, puede_descalificar,
     recomendacion, orden, activo)
VALUES
    (@id_pauta, @id_bloque, N'PECN.4', N'Cierre de negociación',
     'PUNTUABLE', 10.0, N'Inducir a cierre para una promesa de pago',
     N'Luego de haber informado la deuda y haber hecho frente a sus objeciones, el agente debe cerrar la promesa de pago de forma efectiva y oportuna.',
     N'Cumple cuando induce una promesa de pago o siguiente acción verificable, adecuada a la conversación y a la capacidad expuesta.',
     N'No cumple cuando existía oportunidad de gestión y el agente no intenta concretar un compromiso, monto, fecha o siguiente acción verificable.',
     N'Aplica en toda conversación con el titular. Debe inducir una promesa o siguiente acción verificable. Solo puede ser NO_APLICA ante tercero confirmado o corte abrupto que impida gestionar.',
     N'ERROR_CRITICO_CUMPLIMIENTO', N'TRANSCRIPCION',
     1, 0,
     NULL, 8, 1);

INSERT INTO CobAuto.dbo.CRM_IA_PAUTA_CRITERIO
    (id_pauta, id_bloque, codigo_criterio, nombre, tipo_criterio, peso, detalle,
     regla_evaluacion, regla_cumple, regla_no_cumple, regla_aplicabilidad,
     criticidad, fuente_evidencia, requiere_evidencia, puede_descalificar,
     recomendacion, orden, activo)
VALUES
    (@id_pauta, @id_bloque, N'PECC.1', N'Filosofía Biznescob',
     'PUNTUABLE', 5.0, N'Protege la imagen de Mibanco',
     N'No desacredita a Mibanco, a sus colaboradores, áreas, procesos o canales; tampoco responsabiliza a terceros para justificar una mala gestión.',
     N'Cumple cuando se refiere a Mibanco, sus personas, canales y procesos de forma profesional y sin desacreditarlos.',
     N'No cumple cuando desacredita a Mibanco, sus colaboradores, procesos o canales, o culpa a terceros para justificar una mala gestión.',
     N'Aplica a toda referencia del asesor sobre Mibanco, sus canales, colaboradores o procesos.',
     N'ERROR_CRITICO_CUMPLIMIENTO', N'TRANSCRIPCION',
     1, 0,
     NULL, 9, 1);

INSERT INTO CobAuto.dbo.CRM_IA_PAUTA_CRITERIO
    (id_pauta, id_bloque, codigo_criterio, nombre, tipo_criterio, peso, detalle,
     regla_evaluacion, regla_cumple, regla_no_cumple, regla_aplicabilidad,
     criticidad, fuente_evidencia, requiere_evidencia, puede_descalificar,
     recomendacion, orden, activo)
VALUES
    (@id_pauta, @id_bloque, N'PECC.2', N'Confirmación del acuerdo',
     'PUNTUABLE', 5.0, N'Lectura de speech',
     N'Evalúa el speech de confirmación de promesa de pago verbal al cliente. Debe quedar claro el compromiso y sus condiciones principales.',
     N'Cumple cuando, ante un acuerdo, confirma verbalmente las condiciones relevantes de forma clara para el cliente.',
     N'No cumple cuando existe acuerdo o promesa y el agente omite la confirmación verbal necesaria de sus condiciones principales.',
     N'Aplica cuando existe promesa, compromiso, abono, convenio o acuerdo verbal.',
     N'ERROR_CRITICO_CUMPLIMIENTO', N'TRANSCRIPCION',
     1, 0,
     NULL, 10, 1);

INSERT INTO CobAuto.dbo.CRM_IA_PAUTA_CRITERIO
    (id_pauta, id_bloque, codigo_criterio, nombre, tipo_criterio, peso, detalle,
     regla_evaluacion, regla_cumple, regla_no_cumple, regla_aplicabilidad,
     criticidad, fuente_evidencia, requiere_evidencia, puede_descalificar,
     recomendacion, orden, activo)
VALUES
    (@id_pauta, @id_bloque, N'PECC.3', N'Tipificación de la gestión',
     'PUNTUABLE', 10.0, N'Registra el motivo de llamada de acuerdo al escenario.',
     N'Tipifica de manera correcta el motivo o submotivo de la llamada y en el campo de observaciones deja un detalle completo.',
     N'Cumple cuando la tipificación y observación registradas en la fuente de sistema describen correctamente el resultado de la gestión.',
     N'No cumple cuando la fuente de sistema disponible evidencia tipificación u observación inconsistente con la gestión realizada.',
     N'Aplica cuando existe tipificación o resultado de gestión registrado para la llamada.',
     N'ERROR_CRITICO_CUMPLIMIENTO', N'TIPIFICACION',
     1, 0,
     NULL, 11, 1);


/* ---------- BLOQUE PENC ---------- */
INSERT INTO CobAuto.dbo.CRM_IA_PAUTA_BLOQUE
    (id_pauta, codigo, nombre, categoria, descripcion, orden, activo)
VALUES
    (@id_pauta, N'PENC', N'Precisión de Error No Crítico - Protocolos de Atención', N'PENC',
     N'Evalua protocolos de atencion que sostienen una interaccion profesional, clara y adecuada desde el saludo hasta la despedida.', 4, 1);
SET @id_bloque = SCOPE_IDENTITY();

INSERT INTO CobAuto.dbo.CRM_IA_PAUTA_CRITERIO
    (id_pauta, id_bloque, codigo_criterio, nombre, tipo_criterio, peso, detalle,
     regla_evaluacion, regla_cumple, regla_no_cumple, regla_aplicabilidad,
     criticidad, fuente_evidencia, requiere_evidencia, puede_descalificar,
     recomendacion, orden, activo)
VALUES
    (@id_pauta, @id_bloque, N'PENC.1', N'Saludo de bienvenida',
     'PUNTUABLE', 2.0, N'Saluda oportunamente',
     N'Saluda al inicio de la interacción, indicando nombre y apellidos del ejecutivo, sin omitir que actúa en representación de Mibanco.',
     N'Cumple cuando inicia con saludo, se identifica y comunica que actúa en representación de Mibanco.',
     N'No cumple cuando omite de forma material el saludo o la identificación requerida en una apertura audible.',
     N'Aplica a llamadas con contacto efectivo o intento de apertura audible.',
     N'ERROR_NO_CRITICO', N'AUDIO',
     0, 0,
     NULL, 12, 1);

INSERT INTO CobAuto.dbo.CRM_IA_PAUTA_CRITERIO
    (id_pauta, id_bloque, codigo_criterio, nombre, tipo_criterio, peso, detalle,
     regla_evaluacion, regla_cumple, regla_no_cumple, regla_aplicabilidad,
     criticidad, fuente_evidencia, requiere_evidencia, puede_descalificar,
     recomendacion, orden, activo)
VALUES
    (@id_pauta, @id_bloque, N'PENC.2', N'Tono de voz',
     'PUNTUABLE', 3.0, N'Fluidez, modulación y dicción',
     N'Mantiene tono, velocidad, vocalización y fluidez adecuadas; evita muletillas repetitivas y tecnicismos innecesarios.',
     N'Cumple cuando mantiene volumen, velocidad, dicción, modulación y fluidez apropiadas durante la gestión.',
     N'No cumple cuando el tono, velocidad, dicción o muletillas dificultan de forma observable una atención profesional.',
     N'Aplica cuando el audio permite evaluar locución de forma suficiente.',
     N'ERROR_NO_CRITICO', N'AUDIO',
     0, 0,
     NULL, 13, 1);

INSERT INTO CobAuto.dbo.CRM_IA_PAUTA_CRITERIO
    (id_pauta, id_bloque, codigo_criterio, nombre, tipo_criterio, peso, detalle,
     regla_evaluacion, regla_cumple, regla_no_cumple, regla_aplicabilidad,
     criticidad, fuente_evidencia, requiere_evidencia, puede_descalificar,
     recomendacion, orden, activo)
VALUES
    (@id_pauta, @id_bloque, N'PENC.3', N'Claridad del lenguaje oral',
     'PUNTUABLE', 3.0, N'Explicación clara y coherente',
     N'Se expresa con orden, no se contradice, responde de forma comprensible y transmite seguridad sin generar confusión.',
     N'Cumple cuando utiliza lenguaje claro, ordenado y comprensible, evitando tecnicismos o contradicciones innecesarias.',
     N'No cumple cuando usa un lenguaje confuso, contradictorio o incomprensible que afecta la comprensión del cliente.',
     N'Aplica cuando el asesor entrega información o explica condiciones durante la llamada.',
     N'ERROR_NO_CRITICO', N'TRANSCRIPCION',
     0, 0,
     NULL, 14, 1);

INSERT INTO CobAuto.dbo.CRM_IA_PAUTA_CRITERIO
    (id_pauta, id_bloque, codigo_criterio, nombre, tipo_criterio, peso, detalle,
     regla_evaluacion, regla_cumple, regla_no_cumple, regla_aplicabilidad,
     criticidad, fuente_evidencia, requiere_evidencia, puede_descalificar,
     recomendacion, orden, activo)
VALUES
    (@id_pauta, @id_bloque, N'PENC.4', N'Despedida adecuada',
     'PUNTUABLE', 2.0, N'Cierre cordial',
     N'Finaliza la llamada de forma educada y profesional, una vez concluida la gestión.',
     N'Cumple cuando finaliza la llamada con una despedida cordial y profesional una vez concluida la gestión.',
     N'No cumple cuando, existiendo cierre audible y sin interrupción técnica, finaliza sin cortesía o con una despedida inadecuada.',
     N'Aplica cuando existe cierre audible de la llamada y no se corta por falla técnica o abandono del cliente.',
     N'ERROR_NO_CRITICO', N'AUDIO',
     0, 0,
     NULL, 15, 1);


COMMIT TRAN;

PRINT 'Pauta creada en estado BORRADOR.';

/* ------------------------- VERIFICACION ------------------------- */
SELECT P.id_pauta, P.nombre, P.version, P.estado,
       (SELECT COUNT(*) FROM CobAuto.dbo.CRM_IA_PAUTA_BLOQUE B WHERE B.id_pauta = P.id_pauta) AS bloques,
       (SELECT COUNT(*) FROM CobAuto.dbo.CRM_IA_PAUTA_CRITERIO C WHERE C.id_pauta = P.id_pauta) AS criterios,
       (SELECT SUM(C.peso) FROM CobAuto.dbo.CRM_IA_PAUTA_CRITERIO C
        WHERE C.id_pauta = P.id_pauta AND C.activo = 1 AND C.tipo_criterio = 'PUNTUABLE') AS peso_total
FROM CobAuto.dbo.CRM_IA_PAUTA P
WHERE P.id_pauta = @id_pauta;

/* Peso por bloque: debe dar PECUF 30, PECN 30, PECC 30, PENC 10 */
SELECT B.codigo AS bloque, SUM(C.peso) AS peso
FROM CobAuto.dbo.CRM_IA_PAUTA_BLOQUE B
INNER JOIN CobAuto.dbo.CRM_IA_PAUTA_CRITERIO C ON C.id_bloque = B.id_bloque
WHERE B.id_pauta = @id_pauta
GROUP BY B.codigo
ORDER BY B.codigo;

END TRY
BEGIN CATCH
    IF @@TRANCOUNT > 0 ROLLBACK TRAN;
    PRINT 'Error en la carga. No se escribio nada.';
    THROW;
END CATCH;
GO

