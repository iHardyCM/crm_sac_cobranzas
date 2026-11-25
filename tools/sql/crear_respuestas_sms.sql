/* =============================================================================
   Respuestas SMS (Mowa) — tablas de la carga programada en CobAuto
   Diseño: claude/diseno_respuestas_sms.md (proyecto crm_cobranzas)

   Qué crea (solo si no existen; se puede ejecutar más de una vez):
     CRM_SMS_CUENTA_CARTERA   qué carteras puede contener cada cuenta Mowa
     CRM_SMS_CAMPANA          campañas conocidas y cuándo revisarlas de nuevo
     CRM_SMS_RESPUESTA        una fila por respuesta recibida (desde el 01/11/2026)
     CRM_SMS_SINCRONIZACION   bitácora de cada corrida de la carga

   No modifica SISCOB ni ninguna tabla existente. El estado atendida/pendiente
   NO se guarda: se calcula al consultar contra SISCOB.dbo.GESTION.
   ============================================================================= */
USE CobAuto;
GO

IF OBJECT_ID('dbo.CRM_SMS_CUENTA_CARTERA', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.CRM_SMS_CUENTA_CARTERA (
        Cuenta     varchar(30) NOT NULL,
        IdCartera  int         NOT NULL,
        CONSTRAINT PK_CRM_SMS_CUENTA_CARTERA PRIMARY KEY (Cuenta, IdCartera)
    );
END
GO

-- Mismo mapeo que CUENTAS en app/services/respuestas_mowa_service.py.
-- MI_BANCO_CAS incluye la 143 aunque ya no está activa, para no perder histórico.
INSERT INTO dbo.CRM_SMS_CUENTA_CARTERA (Cuenta, IdCartera)
SELECT v.Cuenta, v.IdCartera
FROM (VALUES
    ('INTERBANK_BC', 117),
    ('COMPARVIGENTE', 126), ('COMPARVIGENTE', 128), ('COMPARVIGENTE', 133),
    ('COMPARCARTIGO', 124),
    ('FINANCIERA_OH', 132),
    ('PROPIA_BIZNES', 137), ('PROPIA_BIZNES', 148),
    ('COMPGRUPAL', 133),
    ('COMPARCAST_CSM', 144),
    ('MIBANCO_VIG', 135),
    ('MI_BANCO_CAS', 112), ('MI_BANCO_CAS', 143)
) AS v (Cuenta, IdCartera)
WHERE NOT EXISTS (SELECT 1 FROM dbo.CRM_SMS_CUENTA_CARTERA x
                  WHERE x.Cuenta = v.Cuenta AND x.IdCartera = v.IdCartera);
GO

IF OBJECT_ID('dbo.CRM_SMS_CAMPANA', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.CRM_SMS_CAMPANA (
        Cuenta            varchar(30)   NOT NULL,
        CampaignId        bigint        NOT NULL,
        Descripcion       nvarchar(200) NULL,
        FechaCreacion     datetime2(0)  NULL,
        FechaEnvio        datetime2(0)  NULL,
        TotalMensajes     int           NULL,
        TotalRespuestas   int           NOT NULL CONSTRAINT DF_CRM_SMS_CAMPANA_TOTRESP DEFAULT (0),
        FechaDescubierta  datetime2(0)  NOT NULL CONSTRAINT DF_CRM_SMS_CAMPANA_DESC DEFAULT (SYSDATETIME()),
        UltimaRevision    datetime2(0)  NULL,
        ProximaRevision   datetime2(0)  NULL,   -- NULL = fuera de los 60 días, ya no se revisa
        CONSTRAINT PK_CRM_SMS_CAMPANA PRIMARY KEY (Cuenta, CampaignId)
    );
    CREATE INDEX IX_CRM_SMS_CAMPANA_PROXIMA ON dbo.CRM_SMS_CAMPANA (ProximaRevision)
        INCLUDE (FechaCreacion, TotalRespuestas) WHERE ProximaRevision IS NOT NULL;
END
GO

IF OBJECT_ID('dbo.CRM_SMS_RESPUESTA', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.CRM_SMS_RESPUESTA (
        Cuenta             varchar(30)   NOT NULL,
        CampaignId         bigint        NOT NULL,
        RespuestaId        bigint        NOT NULL,
        MessageId          bigint        NOT NULL,
        Msisdn             varchar(15)   NULL,
        Texto              nvarchar(1000) NULL,
        FechaRecepcion     datetime2(0)  NULL,
        RecepcionConHora   bit           NOT NULL,
        EstadoMowa         int           NULL,
        EtiquetaMowa       nvarchar(100) NULL,
        -- Datos del SMS de origen (búsqueda de campañas filtrada por CampaignId).
        Dni                varchar(20)   NULL,
        CarteraMowa        int           NULL,
        MensajeTexto       nvarchar(400) NULL,
        MensajeFechaEnvio  datetime2(0)  NULL,
        OrigenEstado       varchar(15)   NOT NULL CONSTRAINT DF_CRM_SMS_RESP_ORIGEN DEFAULT ('PENDIENTE'),
                           -- PENDIENTE / OK / NO_ENCONTRADO (tras 5 intentos)
        OrigenIntentos     tinyint       NOT NULL CONSTRAINT DF_CRM_SMS_RESP_INTENTOS DEFAULT (0),
        FechaCarga         datetime2(0)  NOT NULL CONSTRAINT DF_CRM_SMS_RESP_CARGA DEFAULT (SYSDATETIME()),
        CONSTRAINT PK_CRM_SMS_RESPUESTA PRIMARY KEY (Cuenta, CampaignId, RespuestaId)
    );
    CREATE INDEX IX_CRM_SMS_RESPUESTA_RECEPCION ON dbo.CRM_SMS_RESPUESTA (FechaRecepcion)
        INCLUDE (Cuenta, Dni, CarteraMowa, OrigenEstado);
    CREATE INDEX IX_CRM_SMS_RESPUESTA_DNI ON dbo.CRM_SMS_RESPUESTA (Dni, Cuenta)
        INCLUDE (FechaRecepcion, RecepcionConHora);
    CREATE INDEX IX_CRM_SMS_RESPUESTA_ORIGEN ON dbo.CRM_SMS_RESPUESTA (OrigenEstado)
        WHERE OrigenEstado = 'PENDIENTE';
END
GO

IF OBJECT_ID('dbo.CRM_SMS_SINCRONIZACION', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.CRM_SMS_SINCRONIZACION (
        IdSincronizacion   bigint IDENTITY(1,1) NOT NULL
                           CONSTRAINT PK_CRM_SMS_SINCRONIZACION PRIMARY KEY,
        Inicio             datetime2(0)  NOT NULL,
        Fin                datetime2(0)  NULL,
        Tipo               varchar(20)   NOT NULL,   -- PROGRAMADA / MANUAL / BACKFILL
        Resultado          varchar(20)   NULL,       -- OK / CON_AVISOS / ERROR
        CampanasNuevas     int NULL,
        CampanasRevisadas  int NULL,
        RespuestasNuevas   int NULL,
        OrigenesCompletados int NULL,
        Avisos             int NULL,
        Detalle            nvarchar(max) NULL         -- avisos por cuenta, sin llaves ni datos personales
    );
END
GO

/* -----------------------------------------------------------------------------
   VERIFICACIÓN (solo lectura). Ejecutar después de crear las tablas.
   ----------------------------------------------------------------------------- */
SELECT 'CRM_SMS_CUENTA_CARTERA' AS tabla, COUNT(*) AS filas FROM dbo.CRM_SMS_CUENTA_CARTERA
UNION ALL SELECT 'CRM_SMS_CAMPANA', COUNT(*) FROM dbo.CRM_SMS_CAMPANA
UNION ALL SELECT 'CRM_SMS_RESPUESTA', COUNT(*) FROM dbo.CRM_SMS_RESPUESTA
UNION ALL SELECT 'CRM_SMS_SINCRONIZACION', COUNT(*) FROM dbo.CRM_SMS_SINCRONIZACION;

-- Índices que usará la vista al cruzar con SISCOB (deberían existir; si no aparece
-- uno que empiece por Dni en CLIENTE o por IdCliente en GESTION, avísame antes de seguir).
SELECT OBJECT_NAME(i.object_id, DB_ID('SISCOB')) AS tabla, i.name AS indice,
       ic.key_ordinal AS orden, c.name AS columna
FROM SISCOB.sys.indexes i
JOIN SISCOB.sys.index_columns ic ON ic.object_id = i.object_id AND ic.index_id = i.index_id AND ic.is_included_column = 0
JOIN SISCOB.sys.columns c ON c.object_id = ic.object_id AND c.column_id = ic.column_id
WHERE i.object_id IN (OBJECT_ID('SISCOB.dbo.CLIENTE'), OBJECT_ID('SISCOB.dbo.GESTION'))
ORDER BY tabla, indice, orden;
GO
