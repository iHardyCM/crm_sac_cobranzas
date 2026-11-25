/* =====================================================================================
   SCORE TELEFÓNICO · FASE 1 — CIMIENTOS DE DATOS
   Fecha: 14/11/2026 · Diseño: claude/diseno_score_telefonico.md (proyecto crm_cobranzas)

   Qué crea (todo nuevo; no modifica ni borra ningún objeto existente):
     ControlCobranza.bl.EmpresaSiscob          idempresa de SISCOB → entidad (para la lista negra de SISCOB)
     CobAuto.score.ResultadoTelefono           catálogo único: qué dice una llamada sobre el número
     CobAuto.score.IndicadorResultado          indicador de SISCOB → resultado del teléfono
     CobAuto.score.CentralitaResultado         estado de la centralita → resultado del teléfono
     CobAuto.score.TelefonoInvalido            números de relleno que nunca se marcan
     CobAuto.score.TelefonoDia                 historial diario por cartera + DNI + teléfono (incremental)
     CobAuto.score.TelefonoDiaControl          qué días se cargaron y con qué fuentes
     CobAuto.score.TelefonoUniverso            universo de teléfonos de hoy (se rehace cada día)
     CobAuto.score.sp_CargarTelefonoDia        carga un día del historial      (@Simular = 1 por defecto)
     CobAuto.score.sp_CargarTelefonoDiaRango   carga un rango de días          (@Simular = 1 por defecto)
     CobAuto.score.sp_ArmarTelefonoUniverso    arma el universo de hoy         (@Simular = 1 por defecto)

   Reglas aplicadas (acordadas con Hardy el 14/11/2026):
     - Solo celulares: 9 dígitos que empiezan con 9. Los fijos no entran.
     - Carteras: las de ControlCobranza.bl.EntidadCartera (la 141 queda fuera hasta conocer su entidad).
     - Lista negra por ENTIDAD: la del CRM (bl.vw_ListaNegraVigentePorCartera) y la de SISCOB
       (Telefonos_LN), traduciendo idempresa → entidad con bl.EmpresaSiscob. Hoy SISCOB se aplica a todos
       los bancos; aquí solo al banco que la pidió.
     - Lo excluido por lista negra NO se borra del universo: queda marcado con su motivo (auditoría).
     - Resultado del teléfono: catálogo propio de Biznescob, independiente del CEF/CNE/NOC del banco.
       El CEF del banco se guarda aparte (N_CEF_SISCOB) para conciliar con Analytics.
     - Mejor resultado del día: el de menor Orden del catálogo; a igual resultado, el más reciente.
     - Fuentes del historial:
         H = gestión humana (siscob.dbo.gestion): intentos y resultado.
         M = máquina (siscob.dbo.pgestion): solo intentos; su indicador es "no contesta" o vacío.
         C = centralita (Desarrollo.dbo.CENTRALITA), solo llamadas SIN anexo (las que tienen anexo ya están
             en gestion): resultado real de lo que no conectó (buzón, apagado, timbra…).
       Los resultados salen de H y C; M solo suma intentos. Así un mismo intento no cuenta dos veces.
     - Franjas (las de Analytics): mañana 06:00–11:59, medio 12:00–14:59, tarde 15:00–17:59, noche 18:00+.

   Cómo ejecutarlo:
     1. Bloque 0: solo lectura. Revisa sus resultados antes de seguir.
     2. Bloques 1 a 3: crean los objetos (no tocan datos existentes).
     3. Bloque 4: pruebas en SIMULACIÓN (no escriben).
     4. Bloque 5: carga real, comentada. Ejecutar solo después de revisar el bloque 4.
   ===================================================================================== */

/* =====================================================================================
   BLOQUE 0 · PRE-VALIDACIÓN (solo lectura)
   ===================================================================================== */
USE CobAuto;
GO
SET NOCOUNT ON;
GO

-- 0.1 Carteras que entrarán (deben ser las 13 de bl.EntidadCartera)
SELECT ec.IdCartera, ec.NombreCartera, e.Codigo AS Entidad, ec.Activa
FROM ControlCobranza.bl.EntidadCartera AS ec
INNER JOIN ControlCobranza.bl.Entidad AS e ON e.IdEntidad = ec.IdEntidad
ORDER BY ec.IdCartera;
GO

-- 0.2 ¿gestion.Estado distingue gestiones anuladas? (hoy no se filtra; si hay anuladas, se decide)
SELECT Estado, COUNT_BIG(*) AS gestiones
FROM siscob.dbo.gestion WITH (NOLOCK)
WHERE Fecha >= DATEADD(DAY, -30, CAST(GETDATE() AS DATE))
GROUP BY Estado;
GO

-- 0.3 Indicadores usados en 6 meses que todavía NO tienen resultado asignado en el catálogo
--     (después de crear los objetos; si el catálogo no existe aún, ejecutar al final)
IF OBJECT_ID('CobAuto.score.IndicadorResultado', 'U') IS NOT NULL
SELECT g.idCartera, g.IdIndicador, i.DescripcionIndicador, i.TipoContacto, COUNT_BIG(*) AS gestiones_6m
FROM siscob.dbo.gestion AS g WITH (NOLOCK)
LEFT JOIN siscob.dbo.Indicador AS i WITH (NOLOCK) ON i.IdIndicador = g.IdIndicador
WHERE g.Fecha >= DATEADD(MONTH, -6, CAST(GETDATE() AS DATE))
  AND g.idCartera IN (SELECT IdCartera FROM ControlCobranza.bl.EntidadCartera)
  AND NOT EXISTS (SELECT 1 FROM CobAuto.score.IndicadorResultado AS r WHERE r.IdIndicador = g.IdIndicador)
GROUP BY g.idCartera, g.IdIndicador, i.DescripcionIndicador, i.TipoContacto
ORDER BY gestiones_6m DESC;
GO

-- 0.4 Valores de "observación" y "origen" de los teléfonos (para clasificar la fuente del dato en la fase 2)
SELECT TOP 60 LTRIM(RTRIM(CONVERT(NVARCHAR(200), observacion))) AS observacion, COUNT_BIG(*) AS telefonos
FROM siscob.dbo.telefonos WITH (NOLOCK)
WHERE telefono BETWEEN 900000000 AND 999999999
GROUP BY LTRIM(RTRIM(CONVERT(NVARCHAR(200), observacion)))
ORDER BY telefonos DESC;

SELECT TOP 40 LTRIM(RTRIM(Origen)) AS origen, COUNT_BIG(*) AS telefonos
FROM siscob.dbo.telefonos WITH (NOLOCK)
WHERE telefono BETWEEN 900000000 AND 999999999
GROUP BY LTRIM(RTRIM(Origen))
ORDER BY telefonos DESC;
GO

/* =====================================================================================
   BLOQUE 1 · ControlCobranza: idempresa de SISCOB → entidad
   Si SISCOB cambia su tabla de empresas, solo se actualiza esta tabla.
   ===================================================================================== */
USE ControlCobranza;
GO

IF OBJECT_ID('bl.EmpresaSiscob', 'U') IS NULL
CREATE TABLE bl.EmpresaSiscob (
    IdEmpresaSiscob INT           NOT NULL CONSTRAINT PK_bl_EmpresaSiscob PRIMARY KEY,
    Nombre          VARCHAR(100)  NOT NULL,
    IdEntidad       INT           NULL CONSTRAINT FK_bl_EmpresaSiscob_Entidad REFERENCES bl.Entidad (IdEntidad),
    Observacion     VARCHAR(255)  NULL,
    FechaRegistro   DATETIME2(0)  NOT NULL CONSTRAINT DF_bl_EmpresaSiscob_Fecha DEFAULT (SYSDATETIME())
);
GO

-- Tabla de empresas de SISCOB (captura de Hardy, 14/11/2026). IdEntidad NULL = sin carteras en el CRM.
INSERT INTO bl.EmpresaSiscob (IdEmpresaSiscob, Nombre, IdEntidad, Observacion)
SELECT v.IdEmpresaSiscob, v.Nombre, v.IdEntidad, v.Observacion
FROM (VALUES
    (1,  'CONECTA',          NULL, NULL),
    (2,  'REFINANCIA',       NULL, NULL),
    (3,  'MI BANCO',         2,    NULL),
    (4,  'ESSEN',            NULL, NULL),
    (5,  'INTERBANK',        3,    NULL),
    (7,  'COMPARTAMOS',      1,    NULL),
    (8,  'FINANCIERA OH',    4,    NULL),
    (9,  'GPS',              NULL, NULL),
    (10, 'IBK 1124 COMPRA',  5,    'Cartera propia Interbank (137). POR CONFIRMAR'),
    (12, 'BIZNESCOB',        5,    'Cartera propia. POR CONFIRMAR si corresponde a 137, 148 o ambas'),
    (13, 'LOS ANDES',        NULL, NULL)
) v (IdEmpresaSiscob, Nombre, IdEntidad, Observacion)
WHERE NOT EXISTS (SELECT 1 FROM bl.EmpresaSiscob e WHERE e.IdEmpresaSiscob = v.IdEmpresaSiscob);
GO

/* =====================================================================================
   BLOQUE 2 · CobAuto: esquema, catálogos y tablas
   ===================================================================================== */
USE CobAuto;
GO
IF SCHEMA_ID('score') IS NULL EXEC ('CREATE SCHEMA score AUTHORIZATION dbo;');
GO

-- 2.1 Catálogo de resultados del teléfono
IF OBJECT_ID('score.ResultadoTelefono', 'U') IS NULL
CREATE TABLE score.ResultadoTelefono (
    Codigo       VARCHAR(20)   NOT NULL CONSTRAINT PK_score_ResultadoTelefono PRIMARY KEY,
    Descripcion  VARCHAR(200)  NOT NULL,
    Orden        TINYINT       NOT NULL,   -- menor = mejor resultado para el número
    EsContacto   BIT           NOT NULL,   -- alguien respondió por el cliente
    Alcance      VARCHAR(10)   NOT NULL,   -- DNI: descarta el número solo para ese cliente · TELEFONO: para todos · NINGUNO
    CONSTRAINT CK_score_ResultadoTelefono_Alcance CHECK (Alcance IN ('DNI', 'TELEFONO', 'NINGUNO'))
);
GO

INSERT INTO score.ResultadoTelefono (Codigo, Descripcion, Orden, EsContacto, Alcance)
SELECT v.Codigo, v.Descripcion, v.Orden, v.EsContacto, v.Alcance
FROM (VALUES
    ('TITULAR',          'Contacto con el titular',                                            1,  1, 'NINGUNO'),
    ('TERCERO_ACUERDO',  'Tercero con quien se puede llegar a un acuerdo (cónyuge, aval, encargado de pago)', 2, 1, 'NINGUNO'),
    ('TERCERO',          'Tercero que conoce al cliente (familiar, mensaje)',                  3,  1, 'NINGUNO'),
    ('FALLECIDO',        'Informan que el cliente falleció',                                   4,  1, 'NINGUNO'),
    ('CONTESTA_SIN_ID',  'Contestan pero no se identifica (centralita: atendido sin agente, contesta y corta)', 5, 1, 'NINGUNO'),
    ('NO_CONTESTA',      'Sin interacción: no contesta, timbra, ocupado, no contacto',         6,  0, 'NINGUNO'),
    ('BUZON',            'Buzón de voz o grabadora',                                           7,  0, 'NINGUNO'),
    ('APAGADO',          'Apagado o sin cobertura',                                            8,  0, 'NINGUNO'),
    ('SIN_INFORMACION',  'La llamada no informa sobre el número (inconclusa, vacía, fallada)', 9,  0, 'NINGUNO'),
    ('EQUIVOCADO',       'El número no corresponde a este cliente',                            10, 0, 'DNI'),
    ('NO_EXISTE',        'El número no existe o está fuera de servicio',                       11, 0, 'TELEFONO'),
    ('NO_APLICA',        'Gestión que no es telefónica (visita de campo)',                     12, 0, 'NINGUNO'),
    ('SIN_CLASIFICAR',   'Indicador sin resultado asignado: revisar el catálogo',              99, 0, 'NINGUNO')
) v (Codigo, Descripcion, Orden, EsContacto, Alcance)
WHERE NOT EXISTS (SELECT 1 FROM score.ResultadoTelefono r WHERE r.Codigo = v.Codigo);
GO

-- 2.2 Indicador de SISCOB → resultado del teléfono
IF OBJECT_ID('score.IndicadorResultado', 'U') IS NULL
CREATE TABLE score.IndicadorResultado (
    IdIndicador          INT            NOT NULL CONSTRAINT PK_score_IndicadorResultado PRIMARY KEY,
    Descripcion          NVARCHAR(255)  NOT NULL,
    TipoContactoSiscob   CHAR(3)        NULL,
    Resultado            VARCHAR(20)    NOT NULL CONSTRAINT FK_score_IndicadorResultado_Resultado REFERENCES score.ResultadoTelefono (Codigo),
    CarterasObservadas   VARCHAR(100)   NULL,
    FechaRegistro        DATETIME2(0)   NOT NULL CONSTRAINT DF_score_IndicadorResultado_Fecha DEFAULT (SYSDATETIME())
);
GO

-- Indicadores usados en los 30 días previos al 14/11/2026 (diagnóstico 4).
-- Los que aparezcan después y no estén aquí quedan SIN_CLASIFICAR y salen en la consulta 0.3.
INSERT INTO score.IndicadorResultado (IdIndicador, Descripcion, TipoContactoSiscob, Resultado, CarterasObservadas)
SELECT v.IdIndicador, v.Descripcion, v.TipoContactoSiscob, v.Resultado, v.CarterasObservadas
FROM (VALUES
    (910, N'PAGO PARCIAL', 'CEF', 'TITULAR', '124,126,128,133,139,144'),
    (911, N'PAGO TOTAL', 'CEF', 'TITULAR', '124,126,128,133,139,144'),
    (912, N'PROMESA DE PAGO', 'CEF', 'TITULAR', '124,126,128,133,139,144'),
    (913, N'RECORDATORIO DE PAGO', 'CEF', 'TITULAR', '124,126,128,133,139,144'),
    (914, N'COMPROMISO INCUMPLIDO', 'CEF', 'TITULAR', '124,126,128,133,139,144'),
    (915, N'SEGUIMIENTO', 'CEF', 'TITULAR', '124,126,128,133,139,144'),
    (916, N'DIFICULTAD PAGO', 'CEF', 'TITULAR', '124,126,128,133,139,144'),
    (917, N'CLIENTE CON RECLAMO', 'CEF', 'TITULAR', '124,126,133,139,144'),
    (918, N'RENUENTE', 'CEF', 'TITULAR', '124,126,128,133,139,144'),
    (919, N'MENSAJE A TERCERO', 'CNE', 'TERCERO', '124,126,128,133,139,144'),
    (949, N'AL DIA', 'CEF', 'TITULAR', '117'),
    (950, N'CANCELADO', 'CEF', 'TITULAR', '117'),
    (951, N'CONFIRMACION DE PROMESA DE PAGO', 'CEF', 'TITULAR', '117'),
    (952, N'PROMESA DE PAGO', 'CEF', 'TITULAR', '117'),
    (953, N'TRANSACCION', 'CEF', 'TITULAR', '117'),
    (955, N'MENSAJE A ENCARGADO DE PAGO', 'CEF', 'TERCERO_ACUERDO', '117'),
    (956, N'MENSAJE CONYUGUE', 'CEF', 'TERCERO_ACUERDO', '117'),
    (957, N'MENSAJE FAMILIAR', 'CNE', 'TERCERO', '117'),
    (958, N'SOLICITA AUTORIZACION', 'CEF', 'TITULAR', '117'),
    (959, N'TITULAR DESEA QUE LO VUELVAN A LLAMAR', 'CEF', 'TITULAR', '117'),
    (960, N'TITULAR/RENUENTE AL PAGO', 'CEF', 'TITULAR', '117'),
    (961, N'NO PUEDE PAGAR', 'CEF', 'TITULAR', '117'),
    (962, N'SOLICITARA RECLAMO', 'CEF', 'TITULAR', '117'),
    (963, N'FALLECIDO', 'CNE', 'FALLECIDO', '117'),
    (966, N'MENSAJE CON TERCEROS', 'CNE', 'TERCERO', '117'),
    (968, N'MENSAJE EN GRABADORA', 'NOC', 'BUZON', '117'),
    (969, N'LLAMADA INCONCLUSA', 'NOC', 'SIN_INFORMACION', '117'),
    (970, N'TELEFONO FUERA DE SERVICIO', 'NOC', 'NO_EXISTE', '117'),
    (971, N'TELEFONO NO CONTESTA', 'NOC', 'NO_CONTESTA', '117'),
    (972, N'TELEFONO OCUPADO', 'NOC', 'NO_CONTESTA', '117'),
    (973, N'TELEFONO NO CORRESPONDE', 'NOC', 'EQUIVOCADO', '117'),
    (974, N'TELEFONO NO EXISTE', 'NOC', 'NO_EXISTE', '117'),
    (1029, N'COMPROMISO INCIERTO', 'CEF', 'TITULAR', '124,133,144'),
    (1031, N'NO CONTESTA', 'NOC', 'NO_CONTESTA', '124,126,128,133,139,144'),
    (1032, N'NO CONTACTO', 'NOC', 'NO_CONTESTA', '124,126,128,133,139,144'),
    (1034, N'FALLAOO', 'NOC', 'SIN_INFORMACION', '124,126,133'),
    (1060, N'COLGO', 'CEF', 'TITULAR', '132'),
    (1061, N'DIFICULTAD DE PAGO', 'CEF', 'TITULAR', '132'),
    (1062, N'FALLECIO', 'CEF', 'FALLECIDO', '132'),
    (1063, N'PROMESA', 'CEF', 'TITULAR', '132'),
    (1064, N'PROMESA INCIERTA', 'CEF', 'TITULAR', '132'),
    (1065, N'RECORDATORIO CONVENIO', 'CEF', 'TITULAR', '132'),
    (1066, N'RECORDATORIO DE PROMESA PAGO', 'CEF', 'TITULAR', '132'),
    (1067, N'RENUENTE', 'CEF', 'TITULAR', '132'),
    (1068, N'SEGUIMIENTO', 'CEF', 'TITULAR', '132'),
    (1069, N'YA PAGO', 'CEF', 'TITULAR', '132'),
    (1070, N'COLGO', 'CNE', 'TERCERO', '132'),
    (1071, N'FALLECIO', 'CNE', 'FALLECIDO', '132'),
    (1072, N'MENSAJE', 'CNE', 'TERCERO', '132'),
    (1073, N'NUMERO EQUIVOCADO', 'CNE', 'EQUIVOCADO', '132'),
    (1074, N'GRABADORA', 'NOC', 'BUZON', '132'),
    (1075, N'LLAMADA VACIA', 'NOC', 'SIN_INFORMACION', '132'),
    (1077, N'NO CONTESTA', 'NOC', 'NO_CONTESTA', '132'),
    (1078, N'NUMERO NO EXISTE/ INVALIDO', 'NOC', 'NO_EXISTE', '132'),
    (1115, N'PAGO', 'CEF', 'TITULAR', '112'),
    (1116, N'PROMESA - PARCIAL', 'CEF', 'TITULAR', '112'),
    (1117, N'PROMESA - TOTAL', 'CEF', 'TITULAR', '112'),
    (1118, N'RECORDATORIO DE PAGO', 'CEF', 'TITULAR', '112'),
    (1120, N'EN NEGOCIACIÓN - TOTAL', 'CEF', 'TITULAR', '112'),
    (1121, N'RESPONSABLE DE PAGO - AVAL', 'CEF', 'TERCERO_ACUERDO', '112'),
    (1122, N'RESPONSABLE DE PAGO - INTERESADO', 'CEF', 'TERCERO_ACUERDO', '112'),
    (1123, N'DIFICULTAD DE PAGO - PROBLEMA PERSONAL DEL CLIENTE', 'CEF', 'TITULAR', '112'),
    (1124, N'DIFICULTAD DE PAGO - DIFICULTAD EN EL NEGOCIO', 'CEF', 'TITULAR', '112'),
    (1125, N'DIFICULTAD DE PAGO - SEGUIMIENTO DE SOLUCION DE PAGO', 'CEF', 'TITULAR', '112'),
    (1126, N'DIFICULTAD DE PAGO - ZONA ALEJADA', 'CEF', 'TITULAR', '112'),
    (1127, N'DIFICULTAD DE PAGO - NO ESPECIFICA', 'CEF', 'TITULAR', '112'),
    (1128, N'RENUENTE', 'CEF', 'TITULAR', '112'),
    (1129, N'RECLAMO', 'CEF', 'TITULAR', '112'),
    (1130, N'MENSAJE A TERCERO', 'CNE', 'TERCERO', '112'),
    (1131, N'FALLECIDO', 'CNE', 'FALLECIDO', '112'),
    (1132, N'EQUIVOCADO', 'CNE', 'EQUIVOCADO', '112'),
    (1133, N'TIMBRA NO CONTESTA', 'NOC', 'NO_CONTESTA', '112'),
    (1134, N'BUZON DE VOZ', 'NOC', 'BUZON', '112'),
    (1135, N'TELF NO EXISTE', 'NOC', 'NO_EXISTE', '112'),
    (1179, N'AL DIA', 'CEF', 'TITULAR', '137,148'),
    (1180, N'CANCELADO', 'CEF', 'TITULAR', '137,148'),
    (1181, N'CONFIRMACION DE PROMESA DE PAGO', 'CEF', 'TITULAR', '137,148'),
    (1182, N'PROMESA DE PAGO', 'CEF', 'TITULAR', '137,148'),
    (1185, N'MENSAJE A ENCARGADO DE PAGO', 'CEF', 'TERCERO_ACUERDO', '148'),
    (1186, N'MENSAJE CONYUGUE', 'CEF', 'TERCERO_ACUERDO', '148'),
    (1187, N'MENSAJE FAMILIAR', 'CNE', 'TERCERO', '137,148'),
    (1188, N'SOLICITA AUTORIZACION', 'CEF', 'TITULAR', '137,148'),
    (1189, N'TITULAR DESEA QUE LO VUELVAN A LLAMAR', 'CEF', 'TITULAR', '137,148'),
    (1190, N'TITULAR/RENUENTE AL PAGO', 'CEF', 'TITULAR', '137,148'),
    (1191, N'NO PUEDE PAGAR', 'CEF', 'TITULAR', '137,148'),
    (1193, N'FALLECIDO', 'CNE', 'FALLECIDO', '148'),
    (1194, N'MENSAJE CON TERCEROS', 'CNE', 'TERCERO', '137,148'),
    (1195, N'MENSAJE EN GRABADORA', 'NOC', 'BUZON', '137,148'),
    (1196, N'LLAMADA INCONCLUSA', 'NOC', 'SIN_INFORMACION', '137,148'),
    (1197, N'TELEFONO FUERA DE SERVICIO', 'NOC', 'NO_EXISTE', '137,148'),
    (1198, N'TELEFONO NO CONTESTA', 'NOC', 'NO_CONTESTA', '137,148'),
    (1199, N'TELEFONO OCUPADO', 'NOC', 'NO_CONTESTA', '137,148'),
    (1200, N'TELEFONO NO CORRESPONDE', 'NOC', 'EQUIVOCADO', '137,148'),
    (1201, N'TELEFONO NO EXISTE', 'NOC', 'NO_EXISTE', '137,148'),
    (1203, N'COMPROMISO INCIERTO', 'CEF', 'TITULAR', '137'),
    (1204, N'FALLAOO', 'NOC', 'SIN_INFORMACION', '137,148'),
    (1210, N'TRANSACCION', 'CEF', 'TITULAR', '124'),
    (1211, N'TRANSACCION', 'CEF', 'TITULAR', '132'),
    (1214, N'PAGO', 'CEF', 'TITULAR', '141'),
    (1215, N'CON COMPROMISO DE PAGO', 'CEF', 'TITULAR', '141'),
    (1216, N'SIN COMPROMISO DE PAGO', 'CEF', 'TITULAR', '141'),
    (1218, N'CONTACTO CON TERCERO', 'CNE', 'TERCERO', '141'),
    (1219, N'SE VOLVERA A LLAMAR / NO CONTESTO', 'NOC', 'NO_CONTESTA', '141'),
    (1220, N'SE VOLVERA A VISITAR / NO SE UBICO', 'NOC', 'NO_APLICA', '141'),
    (1222, N'N° APAGADO', 'NOC', 'APAGADO', '141'),
    (1223, N'N° EQUIVOCADO', 'NOC', 'EQUIVOCADO', '141')
) v (IdIndicador, Descripcion, TipoContactoSiscob, Resultado, CarterasObservadas)
WHERE NOT EXISTS (SELECT 1 FROM score.IndicadorResultado r WHERE r.IdIndicador = v.IdIndicador);
GO

-- 2.3 Estado de la centralita → resultado del teléfono
IF OBJECT_ID('score.CentralitaResultado', 'U') IS NULL
CREATE TABLE score.CentralitaResultado (
    Estado     NVARCHAR(100)  NOT NULL CONSTRAINT PK_score_CentralitaResultado PRIMARY KEY,
    Resultado  VARCHAR(20)    NOT NULL CONSTRAINT FK_score_CentralitaResultado_Resultado REFERENCES score.ResultadoTelefono (Codigo)
);
GO

INSERT INTO score.CentralitaResultado (Estado, Resultado)
SELECT v.Estado, v.Resultado
FROM (VALUES
    (N'BUZON',                           'BUZON'),
    (N'SI_TIMBRA',                       'NO_CONTESTA'),
    (N'APAGADO',                         'APAGADO'),
    (N'ATENDIDO',                        'CONTESTA_SIN_ID'),
    (N'ATENDID',                         'CONTESTA_SIN_ID'),
    (N'CONTESTA Y CORTA INMEDIATAMENTE', 'CONTESTA_SIN_ID'),
    (N'CONTESTA CORTA INMEDIATAMENTE',   'CONTESTA_SIN_ID'),
    (N'DEAD_MEDIA',                      'SIN_INFORMACION'),
    (N'NO EXISTE',                       'NO_EXISTE'),
    (N'NO_EXISTE',                       'NO_EXISTE'),
    (N'TELF NO EXISTE',                  'NO_EXISTE'),
    (N'TELEFONO NO EXISTE',              'NO_EXISTE'),
    (N'DESACTIVADO',                     'NO_EXISTE'),
    (N'',                                'SIN_INFORMACION')
) v (Estado, Resultado)
WHERE NOT EXISTS (SELECT 1 FROM score.CentralitaResultado r WHERE r.Estado = v.Estado);
GO

-- 2.4 Números de relleno
IF OBJECT_ID('score.TelefonoInvalido', 'U') IS NULL
CREATE TABLE score.TelefonoInvalido (
    Telefono  CHAR(9)       NOT NULL CONSTRAINT PK_score_TelefonoInvalido PRIMARY KEY,
    Motivo    VARCHAR(100)  NOT NULL
);
GO
INSERT INTO score.TelefonoInvalido (Telefono, Motivo)
SELECT v.Telefono, v.Motivo
FROM (VALUES ('999999999', 'Relleno'), ('999999991', 'Relleno'), ('900000000', 'Relleno')) v (Telefono, Motivo)
WHERE NOT EXISTS (SELECT 1 FROM score.TelefonoInvalido t WHERE t.Telefono = v.Telefono);
GO

-- 2.5 Historial diario por cartera + DNI + teléfono
IF OBJECT_ID('score.TelefonoDia', 'U') IS NULL
CREATE TABLE score.TelefonoDia (
    Fecha               DATE          NOT NULL,
    IdCartera           INT           NOT NULL,
    DNI                 VARCHAR(20)   NOT NULL,
    Telefono            CHAR(9)       NOT NULL,
    IntentosHumano      SMALLINT      NOT NULL,
    IntentosMaquina     SMALLINT      NOT NULL,
    LlamadasCentralita  SMALLINT      NOT NULL,
    N_TITULAR           SMALLINT      NOT NULL,
    N_TERCERO_ACUERDO   SMALLINT      NOT NULL,
    N_TERCERO           SMALLINT      NOT NULL,
    N_FALLECIDO         SMALLINT      NOT NULL,
    N_CONTESTA_SIN_ID   SMALLINT      NOT NULL,
    N_NO_CONTESTA       SMALLINT      NOT NULL,
    N_BUZON             SMALLINT      NOT NULL,
    N_APAGADO           SMALLINT      NOT NULL,
    N_SIN_INFORMACION   SMALLINT      NOT NULL,
    N_EQUIVOCADO        SMALLINT      NOT NULL,
    N_NO_EXISTE         SMALLINT      NOT NULL,
    N_NO_APLICA         SMALLINT      NOT NULL,
    N_SIN_CLASIFICAR    SMALLINT      NOT NULL,
    N_CEF_SISCOB        SMALLINT      NOT NULL,   -- CEF según la paleta del banco (para conciliar con Analytics)
    Contactos_Manana    SMALLINT      NOT NULL,   -- titular o tercero con acuerdo, por franja
    Contactos_Medio     SMALLINT      NOT NULL,
    Contactos_Tarde     SMALLINT      NOT NULL,
    Contactos_Noche     SMALLINT      NOT NULL,
    UltimoEvento        DATETIME2(0)  NULL,
    UltimoResultado     VARCHAR(20)   NULL,
    MejorResultado      VARCHAR(20)   NULL,
    MomentoMejor        DATETIME2(0)  NULL,
    FechaCarga          DATETIME2(0)  NOT NULL CONSTRAINT DF_score_TelefonoDia_FechaCarga DEFAULT (SYSDATETIME()),
    CONSTRAINT PK_score_TelefonoDia PRIMARY KEY CLUSTERED (Fecha, IdCartera, DNI, Telefono)
);
GO

IF OBJECT_ID('score.TelefonoDiaControl', 'U') IS NULL
CREATE TABLE score.TelefonoDiaControl (
    Fecha                DATE          NOT NULL CONSTRAINT PK_score_TelefonoDiaControl PRIMARY KEY,
    EventosHumano        INT           NOT NULL,
    EventosMaquina       INT           NOT NULL,
    EventosCentralita    INT           NOT NULL,   -- 0 = la centralita no tiene ese día
    Filas                INT           NOT NULL,
    IndicadoresSinClasificar INT       NOT NULL,
    FechaCarga           DATETIME2(0)  NOT NULL,
    Usuario              NVARCHAR(128) NOT NULL
);
GO

/* =====================================================================================
   BLOQUE 3 · Procedimientos
   ===================================================================================== */

-- 3.1 Carga (o simula) un día del historial. Es idempotente: reemplaza solo ese día.
CREATE OR ALTER PROCEDURE score.sp_CargarTelefonoDia
    @Fecha   DATE,
    @Simular BIT = 1
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    IF @Fecha IS NULL OR @Fecha > CAST(GETDATE() AS DATE)
        THROW 50201, 'Fecha no válida.', 1;

    DECLARE @Sig DATE = DATEADD(DAY, 1, @Fecha);

    CREATE TABLE #car (IdCartera INT NOT NULL PRIMARY KEY);
    INSERT INTO #car (IdCartera) SELECT IdCartera FROM ControlCobranza.bl.EntidadCartera;

    CREATE TABLE #ev (
        Fuente      CHAR(1)      NOT NULL,   -- H humana · M máquina · C centralita
        IdEvento    BIGINT       NOT NULL,   -- para desempatar
        IdCartera   INT          NOT NULL,
        DNI         VARCHAR(20)  COLLATE DATABASE_DEFAULT NOT NULL,
        Telefono    CHAR(9)      COLLATE DATABASE_DEFAULT NOT NULL,
        Momento     DATETIME2(0) NOT NULL,
        Resultado   VARCHAR(20)  COLLATE DATABASE_DEFAULT NULL,   -- NULL en máquina: solo cuenta el intento
        EsCefSiscob BIT          NOT NULL
    );

    -- H · gestión humana. DNI de la gestión; si viene vacío, el del cliente (misma regla de Analytics).
    INSERT INTO #ev (Fuente, IdEvento, IdCartera, DNI, Telefono, Momento, Resultado, EsCefSiscob)
    SELECT 'H', g.IdGestion, g.idCartera,
           LEFT(LTRIM(RTRIM(ISNULL(COALESCE(NULLIF(LTRIM(RTRIM(g.DNI)), ''), c.Dni), ''))), 20),
           CONVERT(CHAR(9), g.telefono),
           CAST(CAST(CAST(g.Fecha AS DATE) AS DATETIME) + CAST(CAST(g.Hora AS TIME(0)) AS DATETIME) AS DATETIME2(0)),
           ISNULL(r.Resultado, 'SIN_CLASIFICAR'),
           CASE WHEN LTRIM(RTRIM(i.TipoContacto)) = 'CEF' THEN 1
                WHEN LTRIM(RTRIM(i.TipoContacto)) IN ('CNE', 'NOC') THEN 0
                WHEN g.TipoContacto = 1 THEN 1 ELSE 0 END
    FROM siscob.dbo.gestion AS g WITH (NOLOCK)
    LEFT JOIN siscob.dbo.Cliente AS c WITH (NOLOCK) ON c.IdCliente = g.IdCliente
    LEFT JOIN siscob.dbo.Indicador AS i WITH (NOLOCK) ON i.IdIndicador = g.IdIndicador
    LEFT JOIN score.IndicadorResultado AS r ON r.IdIndicador = g.IdIndicador
    WHERE g.Fecha >= @Fecha AND g.Fecha < @Sig
      AND g.idCartera IN (SELECT IdCartera FROM #car)
      AND g.telefono BETWEEN 900000000 AND 999999999;

    -- M · máquina (solo intentos)
    INSERT INTO #ev (Fuente, IdEvento, IdCartera, DNI, Telefono, Momento, Resultado, EsCefSiscob)
    SELECT 'M', g.IdGestion, g.idCartera,
           LEFT(LTRIM(RTRIM(ISNULL(COALESCE(NULLIF(LTRIM(RTRIM(g.DNI)), ''), c.Dni), ''))), 20),
           CONVERT(CHAR(9), g.telefono),
           CAST(CAST(CAST(g.Fecha AS DATE) AS DATETIME) + CAST(CAST(g.Hora AS TIME(0)) AS DATETIME) AS DATETIME2(0)),
           NULL, 0
    FROM siscob.dbo.pgestion AS g WITH (NOLOCK)
    LEFT JOIN siscob.dbo.Cliente AS c WITH (NOLOCK) ON c.IdCliente = g.IdCliente
    WHERE g.idCartera IN (SELECT IdCartera FROM #car)
      AND g.Fecha >= @Fecha AND g.Fecha < @Sig
      AND g.telefono BETWEEN 900000000 AND 999999999;

    -- C · centralita, solo llamadas que no llegaron a un agente
    INSERT INTO #ev (Fuente, IdEvento, IdCartera, DNI, Telefono, Momento, Resultado, EsCefSiscob)
    SELECT 'C', ROW_NUMBER() OVER (ORDER BY x.Momento), x.IdCartera, x.DNI, x.Telefono, x.Momento,
           ISNULL(cr.Resultado, 'SIN_CLASIFICAR'), 0
    FROM (
        SELECT TRY_CONVERT(INT, ce.idCartera) AS IdCartera,
               LEFT(LTRIM(RTRIM(ce.DNI)), 20) AS DNI,
               RIGHT(LTRIM(RTRIM(ce.telefono)), 9) AS Telefono,
               CAST(ce.[start] AS DATETIME2(0)) AS Momento,
               UPPER(LTRIM(RTRIM(ISNULL(ce.estado, N'')))) AS Estado
        FROM Desarrollo.dbo.CENTRALITA AS ce WITH (NOLOCK)
        WHERE ce.[start] >= @Fecha AND ce.[start] < @Sig
          AND (ce.anexo IS NULL OR LTRIM(RTRIM(ce.anexo)) IN (N'', N'0'))
    ) AS x
    LEFT JOIN score.CentralitaResultado AS cr ON cr.Estado = x.Estado
    WHERE x.IdCartera IN (SELECT IdCartera FROM #car)
      AND x.DNI <> ''
      AND x.Telefono LIKE '9[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]';

    DELETE e FROM #ev AS e WHERE e.DNI = '' OR EXISTS (SELECT 1 FROM score.TelefonoInvalido AS t WHERE t.Telefono = e.Telefono);

    -- Resumen por cartera + DNI + teléfono
    ;WITH R AS (
        SELECT e.*, rt.Orden,
               ROW_NUMBER() OVER (PARTITION BY e.IdCartera, e.DNI, e.Telefono
                                  ORDER BY e.Momento DESC, e.IdEvento DESC) AS rn_ultimo,
               ROW_NUMBER() OVER (PARTITION BY e.IdCartera, e.DNI, e.Telefono
                                  ORDER BY CASE WHEN e.Resultado IS NULL THEN 255 ELSE rt.Orden END ASC,
                                           e.Momento DESC, e.IdEvento DESC) AS rn_mejor
        FROM #ev AS e
        LEFT JOIN score.ResultadoTelefono AS rt ON rt.Codigo = e.Resultado
    )
    SELECT
        @Fecha AS Fecha, IdCartera, DNI, Telefono,
        SUM(CASE WHEN Fuente = 'H' THEN 1 ELSE 0 END) AS IntentosHumano,
        SUM(CASE WHEN Fuente = 'M' THEN 1 ELSE 0 END) AS IntentosMaquina,
        SUM(CASE WHEN Fuente = 'C' THEN 1 ELSE 0 END) AS LlamadasCentralita,
        SUM(CASE WHEN Resultado = 'TITULAR'         THEN 1 ELSE 0 END) AS N_TITULAR,
        SUM(CASE WHEN Resultado = 'TERCERO_ACUERDO' THEN 1 ELSE 0 END) AS N_TERCERO_ACUERDO,
        SUM(CASE WHEN Resultado = 'TERCERO'         THEN 1 ELSE 0 END) AS N_TERCERO,
        SUM(CASE WHEN Resultado = 'FALLECIDO'       THEN 1 ELSE 0 END) AS N_FALLECIDO,
        SUM(CASE WHEN Resultado = 'CONTESTA_SIN_ID' THEN 1 ELSE 0 END) AS N_CONTESTA_SIN_ID,
        SUM(CASE WHEN Resultado = 'NO_CONTESTA'     THEN 1 ELSE 0 END) AS N_NO_CONTESTA,
        SUM(CASE WHEN Resultado = 'BUZON'           THEN 1 ELSE 0 END) AS N_BUZON,
        SUM(CASE WHEN Resultado = 'APAGADO'         THEN 1 ELSE 0 END) AS N_APAGADO,
        SUM(CASE WHEN Resultado = 'SIN_INFORMACION' THEN 1 ELSE 0 END) AS N_SIN_INFORMACION,
        SUM(CASE WHEN Resultado = 'EQUIVOCADO'      THEN 1 ELSE 0 END) AS N_EQUIVOCADO,
        SUM(CASE WHEN Resultado = 'NO_EXISTE'       THEN 1 ELSE 0 END) AS N_NO_EXISTE,
        SUM(CASE WHEN Resultado = 'NO_APLICA'       THEN 1 ELSE 0 END) AS N_NO_APLICA,
        SUM(CASE WHEN Resultado = 'SIN_CLASIFICAR'  THEN 1 ELSE 0 END) AS N_SIN_CLASIFICAR,
        SUM(CAST(EsCefSiscob AS INT)) AS N_CEF_SISCOB,
        SUM(CASE WHEN Resultado IN ('TITULAR', 'TERCERO_ACUERDO') AND DATEPART(HOUR, Momento) BETWEEN 6 AND 11  THEN 1 ELSE 0 END) AS Contactos_Manana,
        SUM(CASE WHEN Resultado IN ('TITULAR', 'TERCERO_ACUERDO') AND DATEPART(HOUR, Momento) BETWEEN 12 AND 14 THEN 1 ELSE 0 END) AS Contactos_Medio,
        SUM(CASE WHEN Resultado IN ('TITULAR', 'TERCERO_ACUERDO') AND DATEPART(HOUR, Momento) BETWEEN 15 AND 17 THEN 1 ELSE 0 END) AS Contactos_Tarde,
        SUM(CASE WHEN Resultado IN ('TITULAR', 'TERCERO_ACUERDO') AND DATEPART(HOUR, Momento) >= 18             THEN 1 ELSE 0 END) AS Contactos_Noche,
        MAX(CASE WHEN rn_ultimo = 1 THEN Momento END) AS UltimoEvento,
        MAX(CASE WHEN rn_ultimo = 1 THEN ISNULL(Resultado, 'SIN_INFORMACION') END) AS UltimoResultado,
        MAX(CASE WHEN rn_mejor = 1 THEN Resultado END) AS MejorResultado,
        MAX(CASE WHEN rn_mejor = 1 AND Resultado IS NOT NULL THEN Momento END) AS MomentoMejor
    INTO #dia
    FROM R
    GROUP BY IdCartera, DNI, Telefono;

    DECLARE @EvH INT = (SELECT COUNT(*) FROM #ev WHERE Fuente = 'H'),
            @EvM INT = (SELECT COUNT(*) FROM #ev WHERE Fuente = 'M'),
            @EvC INT = (SELECT COUNT(*) FROM #ev WHERE Fuente = 'C'),
            @Filas INT = (SELECT COUNT(*) FROM #dia),
            @SinClas INT = (SELECT COUNT(*) FROM #ev WHERE Resultado = 'SIN_CLASIFICAR');

    IF @Simular = 1
    BEGIN
        SELECT 'SIMULACION' AS Modo, @Fecha AS Fecha, @EvH AS EventosHumano, @EvM AS EventosMaquina,
               @EvC AS EventosCentralita, @Filas AS Filas, @SinClas AS EventosSinClasificar;

        SELECT IdCartera, COUNT(*) AS telefonos, COUNT(DISTINCT DNI) AS clientes,
               SUM(IntentosHumano) AS humano, SUM(IntentosMaquina) AS maquina, SUM(LlamadasCentralita) AS centralita,
               SUM(N_TITULAR) AS titular, SUM(N_TERCERO_ACUERDO) AS tercero_acuerdo, SUM(N_TERCERO) AS tercero,
               SUM(N_CONTESTA_SIN_ID) AS contesta_sin_id, SUM(N_NO_CONTESTA) AS no_contesta, SUM(N_BUZON) AS buzon,
               SUM(N_APAGADO) AS apagado, SUM(N_EQUIVOCADO) AS equivocado, SUM(N_NO_EXISTE) AS no_existe,
               SUM(N_SIN_CLASIFICAR) AS sin_clasificar, SUM(N_CEF_SISCOB) AS cef_siscob
        FROM #dia GROUP BY IdCartera ORDER BY IdCartera;

        SELECT e.Fuente, e.IdCartera, COUNT(*) AS eventos_sin_clasificar
        FROM #ev AS e WHERE e.Resultado = 'SIN_CLASIFICAR'
        GROUP BY e.Fuente, e.IdCartera;
        RETURN;
    END;

    BEGIN TRAN;
        DELETE FROM score.TelefonoDia WHERE Fecha = @Fecha;

        INSERT INTO score.TelefonoDia (
            Fecha, IdCartera, DNI, Telefono, IntentosHumano, IntentosMaquina, LlamadasCentralita,
            N_TITULAR, N_TERCERO_ACUERDO, N_TERCERO, N_FALLECIDO, N_CONTESTA_SIN_ID, N_NO_CONTESTA, N_BUZON,
            N_APAGADO, N_SIN_INFORMACION, N_EQUIVOCADO, N_NO_EXISTE, N_NO_APLICA, N_SIN_CLASIFICAR, N_CEF_SISCOB,
            Contactos_Manana, Contactos_Medio, Contactos_Tarde, Contactos_Noche,
            UltimoEvento, UltimoResultado, MejorResultado, MomentoMejor)
        SELECT Fecha, IdCartera, DNI, Telefono, IntentosHumano, IntentosMaquina, LlamadasCentralita,
            N_TITULAR, N_TERCERO_ACUERDO, N_TERCERO, N_FALLECIDO, N_CONTESTA_SIN_ID, N_NO_CONTESTA, N_BUZON,
            N_APAGADO, N_SIN_INFORMACION, N_EQUIVOCADO, N_NO_EXISTE, N_NO_APLICA, N_SIN_CLASIFICAR, N_CEF_SISCOB,
            Contactos_Manana, Contactos_Medio, Contactos_Tarde, Contactos_Noche,
            UltimoEvento, UltimoResultado, MejorResultado, MomentoMejor
        FROM #dia;

        DELETE FROM score.TelefonoDiaControl WHERE Fecha = @Fecha;
        INSERT INTO score.TelefonoDiaControl (Fecha, EventosHumano, EventosMaquina, EventosCentralita, Filas,
                                              IndicadoresSinClasificar, FechaCarga, Usuario)
        VALUES (@Fecha, @EvH, @EvM, @EvC, @Filas, @SinClas, SYSDATETIME(), ORIGINAL_LOGIN());
    COMMIT;

    SELECT 'CARGADO' AS Modo, @Fecha AS Fecha, @EvH AS EventosHumano, @EvM AS EventosMaquina,
           @EvC AS EventosCentralita, @Filas AS Filas, @SinClas AS EventosSinClasificar;
END;
GO

-- 3.2 Carga un rango de días, uno por uno (para el histórico de 6 meses y para recargas)
CREATE OR ALTER PROCEDURE score.sp_CargarTelefonoDiaRango
    @Desde   DATE,
    @Hasta   DATE,
    @Simular BIT = 1
AS
BEGIN
    SET NOCOUNT ON;
    IF @Desde IS NULL OR @Hasta IS NULL OR @Desde > @Hasta
        THROW 50202, 'Rango de fechas no válido.', 1;

    DECLARE @f DATE = @Desde;
    WHILE @f <= @Hasta
    BEGIN
        EXEC score.sp_CargarTelefonoDia @Fecha = @f, @Simular = @Simular;
        SET @f = DATEADD(DAY, 1, @f);
    END;
END;
GO

-- 3.3 Universo de teléfonos de hoy. Se arma aparte y se intercambia en una transacción corta:
--     mientras se arma, el CRM sigue leyendo el universo anterior.
CREATE OR ALTER PROCEDURE score.sp_ArmarTelefonoUniverso
    @Simular BIT = 1
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    -- Clientes activos de las carteras del score
    SELECT c.IdCartera, ec.IdEntidad, c.IdCliente,
           LEFT(LTRIM(RTRIM(c.Dni)), 20) COLLATE DATABASE_DEFAULT AS DNI
    INTO #cli
    FROM siscob.dbo.Cliente AS c WITH (NOLOCK)
    INNER JOIN ControlCobranza.bl.EntidadCartera AS ec ON ec.IdCartera = c.IdCartera
    WHERE c.Estado IN ('A', 'N')
      AND LTRIM(RTRIM(ISNULL(c.Dni, ''))) <> '';

    -- Un registro por cartera + DNI (si hay varios IdCliente, el mayor)
    ;WITH X AS (SELECT *, ROW_NUMBER() OVER (PARTITION BY IdCartera, DNI ORDER BY IdCliente DESC) AS rn FROM #cli)
    DELETE FROM X WHERE rn > 1;
    CREATE CLUSTERED INDEX IX_cli ON #cli (DNI, IdCartera);

    -- Celulares de SISCOB de esos DNI
    SELECT LEFT(LTRIM(RTRIM(t.DNI)), 20) COLLATE DATABASE_DEFAULT AS DNI,
           CONVERT(CHAR(9), CONVERT(BIGINT, t.telefono)) COLLATE DATABASE_DEFAULT AS Telefono,
           UPPER(LTRIM(RTRIM(t.Prioridad))) AS PrioridadColor,
           CASE UPPER(LTRIM(RTRIM(t.osiptel))) WHEN 'S' THEN 'SI' WHEN 'N' THEN 'NO' WHEN 'L' THEN 'LN' ELSE 'SV' END AS Osiptel,
           CASE UPPER(LTRIM(RTRIM(t.wsp))) WHEN 'SI' THEN 'SI' WHEN 'NO' THEN 'NO' WHEN 'LN' THEN 'LN' ELSE 'SV' END AS Whatsapp,
           TRY_CONVERT(TINYINT, LTRIM(RTRIM(t.timbra))) AS Timbra,
           LTRIM(RTRIM(t.apagado)) AS ApagadoSiscob,
           LTRIM(RTRIM(t.fallado)) AS FalladoSiscob,
           LTRIM(RTRIM(t.Origen)) AS OrigenTexto,
           LEFT(LTRIM(RTRIM(CONVERT(NVARCHAR(200), t.observacion))), 200) AS ObservacionTexto,
           CASE WHEN UPPER(ISNULL(t.t_emp, '')) LIKE '%EMP%' THEN 1 ELSE 0 END AS EsEmpresa,
           t.fecha AS FechaAltaSiscob,
           t.fecha_actualizacion AS FechaActSiscob,
           t.idtelefono
    INTO #tel
    FROM siscob.dbo.telefonos AS t WITH (NOLOCK)
    INNER JOIN (SELECT DISTINCT DNI FROM #cli) AS d
        ON d.DNI = LEFT(LTRIM(RTRIM(t.DNI)), 20) COLLATE DATABASE_DEFAULT
    WHERE t.telefono BETWEEN 900000000 AND 999999999;

    CREATE INDEX IX_tel ON #tel (DNI);

    SELECT c.IdCartera, c.IdEntidad, c.IdCliente, c.DNI, t.Telefono, t.PrioridadColor, t.Osiptel, t.Whatsapp,
           t.Timbra, t.ApagadoSiscob, t.FalladoSiscob, t.OrigenTexto, t.ObservacionTexto, t.EsEmpresa,
           t.FechaAltaSiscob, t.FechaActSiscob,
           CAST(NULL AS VARCHAR(15)) AS Operador, CAST(NULL AS CHAR(6)) AS AnioMesDato,
           CAST(NULL AS INT) AS N_DNI_Comparten, CAST(0 AS BIT) AS ExcluidoListaNegra,
           CAST(NULL AS VARCHAR(100)) AS MotivoExclusion,
           ROW_NUMBER() OVER (PARTITION BY c.IdCartera, c.DNI, t.Telefono
                              ORDER BY t.FechaActSiscob DESC, t.idtelefono DESC) AS rn
    INTO #u
    FROM #cli AS c
    INNER JOIN #tel AS t ON t.DNI = c.DNI;

    DELETE FROM #u WHERE rn > 1;
    DELETE u FROM #u AS u WHERE EXISTS (SELECT 1 FROM score.TelefonoInvalido AS i WHERE i.Telefono = u.Telefono);

    -- Atributos derivados del texto de origen ("E 202301" = operador + año-mes del dato)
    UPDATE #u SET
        Operador = CASE LEFT(ISNULL(OrigenTexto, ''), 2)
                       WHEN 'E ' THEN 'ENTEL' WHEN 'M ' THEN 'MOVISTAR' WHEN 'C ' THEN 'CLARO'
                       ELSE 'NO_RECONOCIDO' END,
        AnioMesDato = CASE WHEN SUBSTRING(ISNULL(OrigenTexto, ''), 3, 6) LIKE '20[0-9][0-9][01][0-9]'
                           THEN SUBSTRING(OrigenTexto, 3, 6) END;

    UPDATE u SET N_DNI_Comparten = x.n
    FROM #u AS u
    INNER JOIN (SELECT Telefono, COUNT(DISTINCT DNI) AS n FROM #u GROUP BY Telefono) AS x ON x.Telefono = u.Telefono;

    -- Lista negra del CRM (por entidad, expandida a sus carteras)
    UPDATE u SET ExcluidoListaNegra = 1,
                 MotivoExclusion = 'LN_CRM ' + b.TipoBloqueo + ' #' + CONVERT(VARCHAR(12), b.IdListaNegra)
    FROM #u AS u
    CROSS APPLY (SELECT TOP 1 l.TipoBloqueo, l.IdListaNegra
                 FROM ControlCobranza.bl.vw_ListaNegraVigentePorCartera AS l
                 WHERE l.IdCartera = u.IdCartera
                   AND ((l.TipoBloqueo = 'T' AND l.Telefono COLLATE DATABASE_DEFAULT = u.Telefono)
                     OR (l.TipoBloqueo = 'D' AND l.DNI COLLATE DATABASE_DEFAULT = u.DNI)
                     OR (l.TipoBloqueo = 'A' AND l.DNI COLLATE DATABASE_DEFAULT = u.DNI
                                              AND l.Telefono COLLATE DATABASE_DEFAULT = u.Telefono))
                 ORDER BY l.IdListaNegra) AS b;

    -- Lista negra de SISCOB, solo para la entidad de la empresa que la pidió
    UPDATE u SET ExcluidoListaNegra = 1,
                 MotivoExclusion = 'LN_SISCOB empresa ' + CONVERT(VARCHAR(5), ln.idempresa)
    FROM #u AS u
    INNER JOIN siscob.dbo.Telefonos_LN AS ln WITH (NOLOCK)
        ON ln.telefono = CONVERT(INT, u.Telefono)
    INNER JOIN ControlCobranza.bl.EmpresaSiscob AS es
        ON es.IdEmpresaSiscob = ln.idempresa AND es.IdEntidad = u.IdEntidad
    WHERE u.ExcluidoListaNegra = 0
      AND ISNULL(ln.estado, 'A') = 'A';

    IF @Simular = 1
    BEGIN
        SELECT 'SIMULACION' AS Modo, COUNT(*) AS filas, COUNT(DISTINCT DNI) AS clientes,
               COUNT(DISTINCT Telefono) AS telefonos, SUM(CAST(ExcluidoListaNegra AS INT)) AS excluidos_lista_negra
        FROM #u;

        SELECT u.IdCartera, COUNT(*) AS filas, COUNT(DISTINCT u.DNI) AS clientes,
               SUM(CASE WHEN u.ExcluidoListaNegra = 0 THEN 1 ELSE 0 END) AS filas_utiles,
               SUM(CASE WHEN u.MotivoExclusion LIKE 'LN_SISCOB%' THEN 1 ELSE 0 END) AS excluidos_ln_siscob,
               SUM(CASE WHEN u.MotivoExclusion LIKE 'LN_CRM%' THEN 1 ELSE 0 END) AS excluidos_ln_crm,
               SUM(CASE WHEN u.Operador = 'NO_RECONOCIDO' THEN 1 ELSE 0 END) AS operador_no_reconocido,
               SUM(CASE WHEN u.N_DNI_Comparten > 1 THEN 1 ELSE 0 END) AS compartidos
        FROM #u AS u GROUP BY u.IdCartera ORDER BY u.IdCartera;

        -- Lo que hoy se pierde con la regla actual (lista negra de SISCOB aplicada a todos los bancos)
        SELECT u.IdCartera, COUNT(*) AS filas_que_hoy_se_excluyen_por_LN_de_otro_banco
        FROM #u AS u
        WHERE u.ExcluidoListaNegra = 0
          AND EXISTS (SELECT 1 FROM siscob.dbo.Telefonos_LN AS ln WITH (NOLOCK) WHERE ln.telefono = CONVERT(INT, u.Telefono))
        GROUP BY u.IdCartera ORDER BY u.IdCartera;
        RETURN;
    END;

    -- Construcción de la tabla nueva y cambio en una transacción corta
    IF OBJECT_ID('score.TelefonoUniverso_Nuevo', 'U') IS NOT NULL DROP TABLE score.TelefonoUniverso_Nuevo;

    SELECT CAST(GETDATE() AS DATE) AS FechaProceso, IdCartera, IdEntidad, IdCliente, DNI, Telefono,
           PrioridadColor, Osiptel, Whatsapp, Timbra, ApagadoSiscob, FalladoSiscob, Operador, AnioMesDato,
           OrigenTexto, ObservacionTexto, CAST(EsEmpresa AS BIT) AS EsEmpresa, FechaAltaSiscob, FechaActSiscob,
           N_DNI_Comparten, ExcluidoListaNegra, MotivoExclusion
    INTO score.TelefonoUniverso_Nuevo
    FROM #u;

    -- Índices (sus nombres son por tabla: no chocan después del cambio de nombre)
    CREATE UNIQUE CLUSTERED INDEX IX_Clave ON score.TelefonoUniverso_Nuevo (IdCartera, DNI, Telefono);
    CREATE INDEX IX_Telefono ON score.TelefonoUniverso_Nuevo (Telefono);

    BEGIN TRAN;
        DECLARE @Lock INT;
        EXEC @Lock = sp_getapplock @Resource = N'SCORE_TELEFONO_UNIVERSO', @LockMode = 'Exclusive',
                                   @LockOwner = 'Transaction', @LockTimeout = 60000;
        IF @Lock < 0 THROW 50203, 'Otro proceso está actualizando el universo.', 1;

        IF OBJECT_ID('score.TelefonoUniverso', 'U') IS NOT NULL
            EXEC sp_rename 'score.TelefonoUniverso', 'TelefonoUniverso_Anterior';
        EXEC sp_rename 'score.TelefonoUniverso_Nuevo', 'TelefonoUniverso';
    COMMIT;

    IF OBJECT_ID('score.TelefonoUniverso_Anterior', 'U') IS NOT NULL DROP TABLE score.TelefonoUniverso_Anterior;

    SELECT 'ACTUALIZADO' AS Modo, COUNT(*) AS filas, SUM(CAST(ExcluidoListaNegra AS INT)) AS excluidos_lista_negra
    FROM score.TelefonoUniverso;
END;
GO

/* =====================================================================================
   BLOQUE 4 · PRUEBAS EN SIMULACIÓN (no escriben nada)
   ===================================================================================== */
-- 4.1 Un día de octubre con centralita (las tres fuentes)
EXEC CobAuto.score.sp_CargarTelefonoDia @Fecha = '2026-10-29', @Simular = 1;
GO
-- 4.2 Ayer (sin centralita: EventosCentralita debe salir 0)
DECLARE @ayer DATE = DATEADD(DAY, -1, CAST(GETDATE() AS DATE));
EXEC CobAuto.score.sp_CargarTelefonoDia @Fecha = @ayer, @Simular = 1;
GO
-- 4.3 Universo de hoy
EXEC CobAuto.score.sp_ArmarTelefonoUniverso @Simular = 1;
GO

/* =====================================================================================
   BLOQUE 5 · CARGA REAL (comentada). Ejecutar solo después de revisar el bloque 4.
   El histórico de 6 meses lee ~25 millones de filas de pgestion: correrlo fuera de horario,
   de preferencia por meses.
   ===================================================================================== */
/*
EXEC CobAuto.score.sp_ArmarTelefonoUniverso @Simular = 0;

EXEC CobAuto.score.sp_CargarTelefonoDiaRango @Desde = '2026-05-14', @Hasta = '2026-06-30', @Simular = 0;
EXEC CobAuto.score.sp_CargarTelefonoDiaRango @Desde = '2026-07-01', @Hasta = '2026-08-31', @Simular = 0;
EXEC CobAuto.score.sp_CargarTelefonoDiaRango @Desde = '2026-09-01', @Hasta = '2026-10-31', @Simular = 0;
EXEC CobAuto.score.sp_CargarTelefonoDiaRango @Desde = '2026-11-01', @Hasta = '2026-11-14', @Simular = 0;

-- Control: días cargados y fuentes disponibles
SELECT * FROM CobAuto.score.TelefonoDiaControl ORDER BY Fecha;
*/
GO
