/* =====================================================================================
   LISTA NEGRA - FASE 1 (versión para probar)
   Base: ControlCobranza   Esquema: bl
   Autor: CRM SAC Cobranzas

   Qué crea:
     - bl.Entidad, bl.EntidadCartera   (alcance del bloqueo = entidad/banco)
     - bl.Motivo                       (catálogo de motivos)
     - bl.ListaNegra                   (registro maestro; nunca se borra)
     - bl.ListaNegraEvento             (historial: ALTA, EXTENSION, RATIFICACION, LEVANTAMIENTO)
     - bl.ListaNegra_Stg               (filas del archivo o del alta individual)
     - bl.fn_NormalizarTelefono
     - bl.vw_ListaNegra, bl.vw_ListaNegraVigente, bl.vw_ListaNegraVigentePorCartera
     - bl.fn_BloqueoContacto           (¿esta cartera/DNI/teléfono está bloqueado?)
     - bl.sp_ListaNegra_CrearCarga, bl.sp_ListaNegra_ProcesarCarga, bl.sp_ListaNegra_Levantar

   Qué modifica:
     - bl.ControlCarga: SOLO agrega columnas nulas (no altera datos existentes).

   Qué NO toca:
     - bl.ListaNegraCartera, bl.ListaNegraCartera_Stg, bl.sp_ProcesarListaNegra
       (quedan como están; se retiran cuando la nueva estructura esté validada).

   Tipos de bloqueo:
     T = TELEFONO          -> el teléfono no se contacta para NINGÚN cliente de la entidad.
                              El DNI, si viene, es solo referencia.
     D = CLIENTE           -> el cliente (DNI) no se contacta en ningún teléfono de la entidad,
                              incluidos teléfonos que lleguen en cargas futuras.
     A = TELEFONO_CLIENTE  -> ese teléfono no se usa para ESE cliente; otros clientes de la
                              entidad que compartan el número sí pueden contactarse.

   El script es re-ejecutable (IF NOT EXISTS / CREATE OR ALTER).
   Requiere SQL Server 2016 SP1 o superior.
   ===================================================================================== */

USE ControlCobranza;
GO
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

/* -------------------------------------------------------------------------------------
   0. PRE-VALIDACIÓN (solo lectura): qué hay hoy en los objetos anteriores
   ------------------------------------------------------------------------------------- */
SELECT 'bl.ListaNegraCartera'     AS Tabla, COUNT(*) AS Filas FROM bl.ListaNegraCartera
UNION ALL
SELECT 'bl.ListaNegraCartera_Stg', COUNT(*) FROM bl.ListaNegraCartera_Stg
UNION ALL
SELECT 'bl.ControlCarga',          COUNT(*) FROM bl.ControlCarga;
GO

IF SCHEMA_ID('bl') IS NULL EXEC('CREATE SCHEMA bl');
GO

/* -------------------------------------------------------------------------------------
   1. ENTIDAD y ENTIDAD-CARTERA
   ------------------------------------------------------------------------------------- */
IF OBJECT_ID('bl.Entidad', 'U') IS NULL
CREATE TABLE bl.Entidad (
    IdEntidad     INT           NOT NULL CONSTRAINT PK_bl_Entidad PRIMARY KEY,
    Codigo        VARCHAR(30)   NOT NULL CONSTRAINT UQ_bl_Entidad_Codigo UNIQUE,
    Nombre        VARCHAR(100)  NOT NULL,
    Activo        BIT           NOT NULL CONSTRAINT DF_bl_Entidad_Activo DEFAULT (1),
    FechaRegistro DATETIME2(0)  NOT NULL CONSTRAINT DF_bl_Entidad_Fecha  DEFAULT (SYSDATETIME())
);
GO

INSERT INTO bl.Entidad (IdEntidad, Codigo, Nombre)
SELECT v.IdEntidad, v.Codigo, v.Nombre
FROM (VALUES
    (1, 'COMPARTAMOS',   'Compartamos Banco'),
    (2, 'MIBANCO',       'Mibanco'),
    (3, 'INTERBANK',     'Interbank'),
    (4, 'FINANCIERA_OH', 'Financiera OH'),
    (5, 'PROPIA',        'Cartera propia')
) v (IdEntidad, Codigo, Nombre)
WHERE NOT EXISTS (SELECT 1 FROM bl.Entidad e WHERE e.IdEntidad = v.IdEntidad);
GO

IF OBJECT_ID('bl.EntidadCartera', 'U') IS NULL
CREATE TABLE bl.EntidadCartera (
    IdCartera     INT           NOT NULL CONSTRAINT PK_bl_EntidadCartera PRIMARY KEY, -- una cartera pertenece a una sola entidad
    IdEntidad     INT           NOT NULL CONSTRAINT FK_bl_EntidadCartera_Entidad REFERENCES bl.Entidad (IdEntidad),
    NombreCartera VARCHAR(100)  NOT NULL,
    Activa        BIT           NOT NULL CONSTRAINT DF_bl_EntidadCartera_Activa DEFAULT (1), -- informativo: el bloqueo aplica igual
    Observacion   VARCHAR(255)  NULL,
    FechaRegistro DATETIME2(0)  NOT NULL CONSTRAINT DF_bl_EntidadCartera_Fecha DEFAULT (SYSDATETIME())
);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_bl_EntidadCartera_Entidad' AND object_id = OBJECT_ID('bl.EntidadCartera'))
    CREATE INDEX IX_bl_EntidadCartera_Entidad ON bl.EntidadCartera (IdEntidad);
GO

INSERT INTO bl.EntidadCartera (IdCartera, IdEntidad, NombreCartera, Activa, Observacion)
SELECT v.IdCartera, v.IdEntidad, v.NombreCartera, v.Activa, v.Observacion
FROM (VALUES
    (124, 1, 'COMPARTAMOS CASTIGO INDIVIDUAL',   1, NULL),
    (126, 1, 'COMPARTAMOS VIGENTE INDIVIDUAL',   1, NULL),
    (128, 1, 'COMPARTAMOS VIGENTE CCM',          1, NULL),
    (133, 1, 'COMPARTAMOS VIGENTE GRUPAL / CSM', 1, NULL),
    (144, 1, 'COMPARTAMOS CASTIGO GRUPAL',       1, NULL),
    (139, 1, 'COMPARTAMOS DUAL',                 1, 'Cartera de transición: clientes que pasan de vigente a castigo'),
    (112, 2, 'MIBANCO 1',                        1, NULL),
    (135, 2, 'MIBANCO VIGENTE',                  1, NULL),
    (143, 2, 'MIBANCO 2',                        0, 'Cartera no activa'),
    (117, 3, 'INTERBANK',                        1, NULL),
    (132, 4, 'FINANCIERA OH',                    1, NULL),
    (137, 5, 'INTERBANK CEDIDA',                 1, NULL),
    (148, 5, 'FINANCIERA OH PROPIA',             1, NULL)
) v (IdCartera, IdEntidad, NombreCartera, Activa, Observacion)
WHERE NOT EXISTS (SELECT 1 FROM bl.EntidadCartera ec WHERE ec.IdCartera = v.IdCartera);
-- PENDIENTE: cartera 141 (dual). Agregar cuando se confirme su entidad.
GO

/* -------------------------------------------------------------------------------------
   2. MOTIVO (catálogo). Los valores iniciales son una PROPUESTA editable.
   ------------------------------------------------------------------------------------- */
IF OBJECT_ID('bl.Motivo', 'U') IS NULL
CREATE TABLE bl.Motivo (
    IdMotivo      INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_bl_Motivo PRIMARY KEY,
    Codigo        VARCHAR(30)   NOT NULL CONSTRAINT UQ_bl_Motivo_Codigo UNIQUE,
    Descripcion   VARCHAR(150)  NOT NULL,
    Activo        BIT           NOT NULL CONSTRAINT DF_bl_Motivo_Activo DEFAULT (1),
    FechaRegistro DATETIME2(0)  NOT NULL CONSTRAINT DF_bl_Motivo_Fecha  DEFAULT (SYSDATETIME())
);
GO

INSERT INTO bl.Motivo (Codigo, Descripcion)
SELECT v.Codigo, v.Descripcion
FROM (VALUES
    ('SOLICITUD_ENTIDAD', 'Solicitud de la entidad'),
    ('SOLICITUD_TITULAR', 'Solicitud del titular'),
    ('TERCERO',           'Teléfono de un tercero / no titular'),
    ('RECLAMO',           'Reclamo (Indecopi, SBS u otro)'),
    ('FALLECIDO',         'Titular fallecido'),
    ('OTRO',              'Otro (detallar en observación)')
) v (Codigo, Descripcion)
WHERE NOT EXISTS (SELECT 1 FROM bl.Motivo m WHERE m.Codigo = v.Codigo);
GO

/* -------------------------------------------------------------------------------------
   3. CONTROL DE CARGA: se reutiliza bl.ControlCarga y solo se agregan columnas
   Estados: PROCESANDO, PREVISUALIZADO, CONFIRMADO, OBSERVADO (confirmado con errores), ERROR
   ------------------------------------------------------------------------------------- */
IF COL_LENGTH('bl.ControlCarga', 'IdEntidad')           IS NULL ALTER TABLE bl.ControlCarga ADD IdEntidad INT NULL;
IF COL_LENGTH('bl.ControlCarga', 'Modo')                IS NULL ALTER TABLE bl.ControlCarga ADD Modo VARCHAR(15) NULL;          -- MASIVA / INDIVIDUAL
IF COL_LENGTH('bl.ControlCarga', 'HashArchivo')         IS NULL ALTER TABLE bl.ControlCarga ADD HashArchivo CHAR(64) NULL;      -- SHA-256 del archivo
IF COL_LENGTH('bl.ControlCarga', 'RegistrosNuevos')     IS NULL ALTER TABLE bl.ControlCarga ADD RegistrosNuevos INT NULL;
IF COL_LENGTH('bl.ControlCarga', 'RegistrosExtendidos') IS NULL ALTER TABLE bl.ControlCarga ADD RegistrosExtendidos INT NULL;
IF COL_LENGTH('bl.ControlCarga', 'RegistrosSinCambio')  IS NULL ALTER TABLE bl.ControlCarga ADD RegistrosSinCambio INT NULL;
IF COL_LENGTH('bl.ControlCarga', 'RegistrosDuplicados') IS NULL ALTER TABLE bl.ControlCarga ADD RegistrosDuplicados INT NULL;
IF COL_LENGTH('bl.ControlCarga', 'FechaConfirmacion')   IS NULL ALTER TABLE bl.ControlCarga ADD FechaConfirmacion DATETIME2(0) NULL;
IF COL_LENGTH('bl.ControlCarga', 'Observacion')         IS NULL ALTER TABLE bl.ControlCarga ADD Observacion VARCHAR(500) NULL;
GO

/* -------------------------------------------------------------------------------------
   4. LISTA NEGRA (maestro)
   Regla: como máximo UNA fila activa por llave y entidad (índices únicos filtrados).
   Un nuevo reporte de la misma llave no duplica: ratifica o extiende la vigencia.
   ------------------------------------------------------------------------------------- */
IF OBJECT_ID('bl.ListaNegra', 'U') IS NULL
CREATE TABLE bl.ListaNegra (
    IdListaNegra    INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_bl_ListaNegra PRIMARY KEY,
    IdEntidad       INT           NOT NULL CONSTRAINT FK_bl_ListaNegra_Entidad REFERENCES bl.Entidad (IdEntidad),
    TipoBloqueo     CHAR(1)       NOT NULL,
    Telefono        VARCHAR(15)   NULL,
    DNI             VARCHAR(20)   NULL,
    IdCarteraOrigen INT           NULL CONSTRAINT FK_bl_ListaNegra_Cartera REFERENCES bl.EntidadCartera (IdCartera),
    IdMotivo        INT           NOT NULL CONSTRAINT FK_bl_ListaNegra_Motivo REFERENCES bl.Motivo (IdMotivo),
    FechaInicio     DATE          NOT NULL,
    FechaFin        DATE          NULL,          -- NULL = permanente
    Estado          CHAR(1)       NOT NULL CONSTRAINT DF_bl_ListaNegra_Estado DEFAULT ('A'), -- A activo, L levantado
    Referencia      VARCHAR(100)  NULL,          -- n° de carta, correo o ticket de la entidad
    Observacion     VARCHAR(500)  NULL,
    Origen          VARCHAR(20)   NOT NULL,      -- MASIVA, INDIVIDUAL, MIGRACION
    IdCarga         INT           NULL CONSTRAINT FK_bl_ListaNegra_Carga REFERENCES bl.ControlCarga (IdCarga),
    UsuarioRegistro VARCHAR(20)   NOT NULL,      -- DNI del usuario CRM
    FechaRegistro   DATETIME2(0)  NOT NULL CONSTRAINT DF_bl_ListaNegra_FechaRegistro DEFAULT (SYSDATETIME()),
    UsuarioLevanta  VARCHAR(20)   NULL,
    FechaLevanta    DATETIME2(0)  NULL,
    MotivoLevanta   VARCHAR(500)  NULL,
    CONSTRAINT CK_bl_ListaNegra_Tipo CHECK (
           (TipoBloqueo = 'T' AND Telefono IS NOT NULL)
        OR (TipoBloqueo = 'D' AND DNI IS NOT NULL AND Telefono IS NULL)
        OR (TipoBloqueo = 'A' AND DNI IS NOT NULL AND Telefono IS NOT NULL)
    ),
    CONSTRAINT CK_bl_ListaNegra_Estado   CHECK (Estado IN ('A', 'L')),
    CONSTRAINT CK_bl_ListaNegra_Vigencia CHECK (FechaFin IS NULL OR FechaFin >= FechaInicio),
    CONSTRAINT CK_bl_ListaNegra_Levanta  CHECK (
        Estado = 'A' OR (UsuarioLevanta IS NOT NULL AND FechaLevanta IS NOT NULL AND MotivoLevanta IS NOT NULL)
    )
);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'UX_bl_ListaNegra_T' AND object_id = OBJECT_ID('bl.ListaNegra'))
    CREATE UNIQUE INDEX UX_bl_ListaNegra_T ON bl.ListaNegra (IdEntidad, Telefono)      WHERE Estado = 'A' AND TipoBloqueo = 'T';
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'UX_bl_ListaNegra_D' AND object_id = OBJECT_ID('bl.ListaNegra'))
    CREATE UNIQUE INDEX UX_bl_ListaNegra_D ON bl.ListaNegra (IdEntidad, DNI)           WHERE Estado = 'A' AND TipoBloqueo = 'D';
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'UX_bl_ListaNegra_A' AND object_id = OBJECT_ID('bl.ListaNegra'))
    CREATE UNIQUE INDEX UX_bl_ListaNegra_A ON bl.ListaNegra (IdEntidad, DNI, Telefono) WHERE Estado = 'A' AND TipoBloqueo = 'A';
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_bl_ListaNegra_Telefono' AND object_id = OBJECT_ID('bl.ListaNegra'))
    CREATE INDEX IX_bl_ListaNegra_Telefono ON bl.ListaNegra (Telefono)
        INCLUDE (IdEntidad, TipoBloqueo, DNI, Estado, FechaInicio, FechaFin);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_bl_ListaNegra_DNI' AND object_id = OBJECT_ID('bl.ListaNegra'))
    CREATE INDEX IX_bl_ListaNegra_DNI ON bl.ListaNegra (DNI)
        INCLUDE (IdEntidad, TipoBloqueo, Telefono, Estado, FechaInicio, FechaFin);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_bl_ListaNegra_Carga' AND object_id = OBJECT_ID('bl.ListaNegra'))
    CREATE INDEX IX_bl_ListaNegra_Carga ON bl.ListaNegra (IdCarga);
GO

/* -------------------------------------------------------------------------------------
   5. HISTORIAL DE EVENTOS (solo inserta; nunca se actualiza ni se borra)
   ------------------------------------------------------------------------------------- */
IF OBJECT_ID('bl.ListaNegraEvento', 'U') IS NULL
CREATE TABLE bl.ListaNegraEvento (
    IdEvento         BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT PK_bl_ListaNegraEvento PRIMARY KEY,
    IdListaNegra     INT           NOT NULL CONSTRAINT FK_bl_ListaNegraEvento_ListaNegra REFERENCES bl.ListaNegra (IdListaNegra),
    TipoEvento       VARCHAR(20)   NOT NULL,   -- ALTA, EXTENSION, RATIFICACION, LEVANTAMIENTO
    FechaFinAnterior DATE          NULL,
    FechaFinNueva    DATE          NULL,
    Detalle          VARCHAR(500)  NULL,
    IdCarga          INT           NULL,
    Usuario          VARCHAR(20)   NOT NULL,
    FechaEvento      DATETIME2(0)  NOT NULL CONSTRAINT DF_bl_ListaNegraEvento_Fecha DEFAULT (SYSDATETIME()),
    CONSTRAINT CK_bl_ListaNegraEvento_Tipo CHECK (TipoEvento IN ('ALTA', 'EXTENSION', 'RATIFICACION', 'LEVANTAMIENTO'))
);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_bl_ListaNegraEvento_Registro' AND object_id = OBJECT_ID('bl.ListaNegraEvento'))
    CREATE INDEX IX_bl_ListaNegraEvento_Registro ON bl.ListaNegraEvento (IdListaNegra, FechaEvento);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_bl_ListaNegraEvento_Fecha' AND object_id = OBJECT_ID('bl.ListaNegraEvento'))
    CREATE INDEX IX_bl_ListaNegraEvento_Fecha ON bl.ListaNegraEvento (FechaEvento) INCLUDE (TipoEvento, Usuario, IdCarga);
GO

/* -------------------------------------------------------------------------------------
   6. STAGING: guarda el dato original y el normalizado de cada fila
   La carga masiva y el alta individual pasan por aquí (una sola ruta de validación).
   ------------------------------------------------------------------------------------- */
IF OBJECT_ID('bl.ListaNegra_Stg', 'U') IS NULL
CREATE TABLE bl.ListaNegra_Stg (
    IdStg            BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT PK_bl_ListaNegra_Stg PRIMARY KEY,
    IdCarga          INT           NOT NULL CONSTRAINT FK_bl_ListaNegra_Stg_Carga REFERENCES bl.ControlCarga (IdCarga),
    Fila             INT           NOT NULL,   -- n° de fila en el archivo
    -- tal como vino
    TipoBloqueoOrig  VARCHAR(30)   NULL,
    TelefonoOrig     VARCHAR(50)   NULL,
    DniOrig          VARCHAR(30)   NULL,
    IdCarteraOrig    VARCHAR(20)   NULL,
    MotivoOrig       VARCHAR(50)   NULL,
    FechaInicioOrig  VARCHAR(30)   NULL,
    FechaFinOrig     VARCHAR(30)   NULL,
    Referencia       VARCHAR(100)  NULL,
    Observacion      VARCHAR(500)  NULL,
    -- normalizado
    TipoBloqueo      CHAR(1)       NULL,
    Telefono         VARCHAR(15)   NULL,
    DNI              VARCHAR(20)   NULL,
    IdCarteraOrigen  INT           NULL,
    IdMotivo         INT           NULL,
    FechaInicio      DATE          NULL,
    FechaFin         DATE          NULL,
    -- resultado
    EstadoFila       VARCHAR(30)   NULL,  -- ERROR, DUPLICADO_ARCHIVO, NUEVO, EXTIENDE_VIGENCIA, SIN_CAMBIO, YA_CUBIERTO
    Error            VARCHAR(255)  NULL,
    IdListaNegra     INT           NULL
);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_bl_ListaNegra_Stg_Carga' AND object_id = OBJECT_ID('bl.ListaNegra_Stg'))
    CREATE INDEX IX_bl_ListaNegra_Stg_Carga ON bl.ListaNegra_Stg (IdCarga, Fila);
GO

/* -------------------------------------------------------------------------------------
   7. NORMALIZACIÓN DE TELÉFONO
   Quita espacios, guiones, +, paréntesis y puntos. Si viene 51 + 9 dígitos, deja 9 dígitos.
   Devuelve NULL si queda vacío, si tiene letras o si no tiene entre 6 y 9 dígitos.
   ------------------------------------------------------------------------------------- */
CREATE OR ALTER FUNCTION bl.fn_NormalizarTelefono (@Valor VARCHAR(50))
RETURNS VARCHAR(15)
WITH SCHEMABINDING
AS
BEGIN
    DECLARE @t VARCHAR(50) = LTRIM(RTRIM(ISNULL(@Valor, '')));

    SET @t = REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(
                @t, ' ', ''), '-', ''), '+', ''), '(', ''), ')', ''), '.', ''), CHAR(9), ''), CHAR(160), '');

    IF @t = '' OR @t LIKE '%[^0-9]%' RETURN NULL;
    IF LEN(@t) = 11 AND LEFT(@t, 2) = '51' SET @t = RIGHT(@t, 9);
    IF LEN(@t) NOT BETWEEN 6 AND 9 RETURN NULL;

    RETURN @t;
END;
GO

/* -------------------------------------------------------------------------------------
   8. VISTAS
   ------------------------------------------------------------------------------------- */
-- Todos los registros, con su situación de vigencia (para el módulo y la auditoría)
CREATE OR ALTER VIEW bl.vw_ListaNegra
AS
SELECT
    l.IdListaNegra,
    l.IdEntidad,
    e.Codigo       AS Entidad,
    l.TipoBloqueo,
    CASE l.TipoBloqueo WHEN 'T' THEN 'TELEFONO' WHEN 'D' THEN 'CLIENTE' WHEN 'A' THEN 'TELEFONO_CLIENTE' END AS TipoBloqueoDesc,
    l.Telefono,
    l.DNI,
    l.IdCarteraOrigen,
    l.IdMotivo,
    m.Codigo       AS Motivo,
    m.Descripcion  AS MotivoDesc,
    l.FechaInicio,
    l.FechaFin,
    l.Estado,
    CASE
        WHEN l.Estado = 'L'                                 THEN 'LEVANTADO'
        WHEN l.FechaInicio > CAST(GETDATE() AS DATE)        THEN 'PROGRAMADO'
        WHEN l.FechaFin   < CAST(GETDATE() AS DATE)         THEN 'VENCIDO'
        ELSE 'VIGENTE'
    END            AS SituacionVigencia,
    l.Referencia,
    l.Observacion,
    l.Origen,
    l.IdCarga,
    l.UsuarioRegistro,
    l.FechaRegistro,
    l.UsuarioLevanta,
    l.FechaLevanta,
    l.MotivoLevanta
FROM bl.ListaNegra l
INNER JOIN bl.Entidad e ON e.IdEntidad = l.IdEntidad
INNER JOIN bl.Motivo  m ON m.IdMotivo  = l.IdMotivo;
GO

-- Contrato oficial: lo que HOY no se debe contactar
CREATE OR ALTER VIEW bl.vw_ListaNegraVigente
AS
SELECT
    l.IdListaNegra,
    l.IdEntidad,
    l.TipoBloqueo,
    l.Telefono,
    l.DNI,
    l.IdMotivo,
    l.FechaInicio,
    l.FechaFin
FROM bl.ListaNegra l
WHERE l.Estado = 'A'
  AND l.FechaInicio <= CAST(GETDATE() AS DATE)
  AND (l.FechaFin IS NULL OR l.FechaFin >= CAST(GETDATE() AS DATE));
GO

-- El bloqueo de la entidad expandido a cada una de sus carteras (para cruces masivos)
CREATE OR ALTER VIEW bl.vw_ListaNegraVigentePorCartera
AS
SELECT
    ec.IdCartera,
    v.IdListaNegra,
    v.IdEntidad,
    v.TipoBloqueo,
    v.Telefono,
    v.DNI,
    v.IdMotivo,
    v.FechaInicio,
    v.FechaFin
FROM bl.vw_ListaNegraVigente v
INNER JOIN bl.EntidadCartera ec ON ec.IdEntidad = v.IdEntidad;
GO

-- ¿Este contacto (cartera + DNI + teléfono) está bloqueado? Devuelve las filas que lo bloquean.
-- Uso: WHERE NOT EXISTS (SELECT 1 FROM ControlCobranza.bl.fn_BloqueoContacto(t.IDCARTERA, t.DNI, t.TELEFONO))
CREATE OR ALTER FUNCTION bl.fn_BloqueoContacto (@IdCartera INT, @DNI VARCHAR(20), @Telefono VARCHAR(15))
RETURNS TABLE
AS
RETURN
    SELECT v.IdListaNegra, v.TipoBloqueo, v.IdMotivo, v.FechaInicio, v.FechaFin
    FROM bl.vw_ListaNegraVigentePorCartera v
    WHERE v.IdCartera = @IdCartera AND v.TipoBloqueo = 'T' AND v.Telefono = @Telefono
    UNION ALL
    SELECT v.IdListaNegra, v.TipoBloqueo, v.IdMotivo, v.FechaInicio, v.FechaFin
    FROM bl.vw_ListaNegraVigentePorCartera v
    WHERE v.IdCartera = @IdCartera AND v.TipoBloqueo = 'D' AND v.DNI = LTRIM(RTRIM(@DNI))
    UNION ALL
    SELECT v.IdListaNegra, v.TipoBloqueo, v.IdMotivo, v.FechaInicio, v.FechaFin
    FROM bl.vw_ListaNegraVigentePorCartera v
    WHERE v.IdCartera = @IdCartera AND v.TipoBloqueo = 'A' AND v.DNI = LTRIM(RTRIM(@DNI)) AND v.Telefono = @Telefono;
GO

/* -------------------------------------------------------------------------------------
   9. SP: CREAR CARGA (masiva o individual)
   Devuelve IdCarga y, si el mismo archivo ya se confirmó antes para la entidad,
   el IdCarga anterior (el CRM avisa; no bloquea).
   ------------------------------------------------------------------------------------- */
CREATE OR ALTER PROCEDURE bl.sp_ListaNegra_CrearCarga
    @IdEntidad   INT,
    @Modo        VARCHAR(15),
    @Usuario     VARCHAR(20),
    @Archivo     VARCHAR(200) = NULL,
    @HashArchivo CHAR(64)     = NULL
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    IF NOT EXISTS (SELECT 1 FROM bl.Entidad WHERE IdEntidad = @IdEntidad AND Activo = 1)
        THROW 50001, 'Entidad no válida.', 1;
    IF @Modo NOT IN ('MASIVA', 'INDIVIDUAL')
        THROW 50002, 'Modo de carga no válido (MASIVA o INDIVIDUAL).', 1;
    IF NULLIF(LTRIM(RTRIM(@Usuario)), '') IS NULL
        THROW 50003, 'El usuario es obligatorio.', 1;

    DECLARE @IdCarga INT;

    INSERT INTO bl.ControlCarga (Archivo, FechaInicio, UsuarioCarga, Estado, IdEntidad, Modo, HashArchivo)
    VALUES (@Archivo, GETDATE(), @Usuario, 'PROCESANDO', @IdEntidad, @Modo, @HashArchivo);

    SET @IdCarga = SCOPE_IDENTITY();

    SELECT
        @IdCarga AS IdCarga,
        (SELECT TOP 1 c.IdCarga
         FROM bl.ControlCarga c
         WHERE @HashArchivo IS NOT NULL
           AND c.HashArchivo = @HashArchivo
           AND c.IdEntidad = @IdEntidad
           AND c.Estado IN ('CONFIRMADO', 'OBSERVADO')
           AND c.IdCarga <> @IdCarga
         ORDER BY c.IdCarga DESC) AS IdCargaPreviaMismoArchivo;
END;
GO

/* -------------------------------------------------------------------------------------
   10. SP: PROCESAR CARGA
   @Confirmar = 0 -> solo valida y clasifica (previsualización). Se puede ejecutar varias veces.
   @Confirmar = 1 -> valida, clasifica y aplica en una sola transacción.
   Clasificación por fila:
     ERROR              no se carga (ver columna Error)
     DUPLICADO_ARCHIVO  misma llave repetida en el archivo; se toma la primera fila
     NUEVO              se crea el bloqueo
     EXTIENDE_VIGENCIA  ya existe con fecha de fin; la nueva es posterior o permanente
     SIN_CAMBIO         ya existe con igual o mayor vigencia (queda evento RATIFICACION)
     YA_CUBIERTO        TELEFONO_CLIENTE ya cubierto por un bloqueo TELEFONO o CLIENTE
   Una carga nunca acorta una vigencia: para eso se usa el levantamiento.
   ------------------------------------------------------------------------------------- */
CREATE OR ALTER PROCEDURE bl.sp_ListaNegra_ProcesarCarga
    @IdCarga   INT,
    @Confirmar BIT,
    @Usuario   VARCHAR(20)
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    DECLARE @IdEntidad INT, @Modo VARCHAR(15), @EstadoCarga VARCHAR(20);
    DECLARE @Hoy DATE = CAST(GETDATE() AS DATE);

    SELECT @IdEntidad = IdEntidad, @Modo = Modo, @EstadoCarga = Estado
    FROM bl.ControlCarga
    WHERE IdCarga = @IdCarga;

    IF @IdEntidad IS NULL
        THROW 50010, 'La carga no existe o no pertenece al módulo de lista negra.', 1;
    IF @EstadoCarga NOT IN ('PROCESANDO', 'PREVISUALIZADO')
        THROW 50011, 'La carga ya fue confirmada o terminó con error; no se puede volver a procesar.', 1;
    IF NULLIF(LTRIM(RTRIM(@Usuario)), '') IS NULL
        THROW 50003, 'El usuario es obligatorio.', 1;

    BEGIN TRY
        BEGIN TRAN;

        -- Evita que dos cargas de la misma entidad se crucen
        DECLARE @Recurso NVARCHAR(100) = CONCAT(N'bl_ListaNegra_Entidad_', @IdEntidad);
        DECLARE @Lock INT;
        EXEC @Lock = sp_getapplock @Resource = @Recurso, @LockMode = 'Exclusive', @LockOwner = 'Transaction', @LockTimeout = 30000;
        IF @Lock < 0
            THROW 50012, 'Otra carga de la misma entidad se está procesando. Intenta en unos segundos.', 1;

        /* 10.1 Normalizar */
        UPDATE s
        SET TipoBloqueo     = n.TipoBloqueo,
            Telefono        = CASE WHEN n.TipoBloqueo = 'D' THEN NULL ELSE bl.fn_NormalizarTelefono(s.TelefonoOrig) END,
            DNI             = NULLIF(REPLACE(LTRIM(RTRIM(ISNULL(s.DniOrig, ''))), ' ', ''), ''),
            IdCarteraOrigen = TRY_CONVERT(INT, NULLIF(LTRIM(RTRIM(s.IdCarteraOrig)), '')),
            IdMotivo        = (SELECT m.IdMotivo FROM bl.Motivo m
                               WHERE m.Activo = 1 AND m.Codigo = UPPER(LTRIM(RTRIM(s.MotivoOrig)))),
            FechaInicio     = COALESCE(TRY_CONVERT(DATE, LTRIM(RTRIM(s.FechaInicioOrig)), 103),
                                       TRY_CONVERT(DATE, LTRIM(RTRIM(s.FechaInicioOrig)), 23),
                                       TRY_CONVERT(DATE, LTRIM(RTRIM(s.FechaInicioOrig)), 120)),
            FechaFin        = COALESCE(TRY_CONVERT(DATE, LTRIM(RTRIM(s.FechaFinOrig)), 103),
                                       TRY_CONVERT(DATE, LTRIM(RTRIM(s.FechaFinOrig)), 23),
                                       TRY_CONVERT(DATE, LTRIM(RTRIM(s.FechaFinOrig)), 120)),
            EstadoFila      = NULL,
            Error           = NULL,
            IdListaNegra    = NULL
        FROM bl.ListaNegra_Stg s
        CROSS APPLY (
            SELECT CASE UPPER(LTRIM(RTRIM(ISNULL(s.TipoBloqueoOrig, ''))))
                       WHEN 'T'                THEN 'T'
                       WHEN 'TELEFONO'         THEN 'T'
                       WHEN 'TELÉFONO'         THEN 'T'
                       WHEN 'D'                THEN 'D'
                       WHEN 'CLIENTE'          THEN 'D'
                       WHEN 'DNI'              THEN 'D'
                       WHEN 'A'                THEN 'A'
                       WHEN 'TELEFONO_CLIENTE' THEN 'A'
                       WHEN 'TELÉFONO_CLIENTE' THEN 'A'
                   END AS TipoBloqueo
        ) n
        WHERE s.IdCarga = @IdCarga;

        /* 10.2 Validar (se registra el primer error de cada fila) */
        UPDATE s
        SET Error = CASE
                WHEN s.TipoBloqueo IS NULL
                    THEN 'Tipo de bloqueo no válido (TELEFONO, CLIENTE o TELEFONO_CLIENTE).'
                WHEN s.TipoBloqueo IN ('T', 'A') AND s.Telefono IS NULL
                    THEN 'Teléfono vacío o con formato no válido.'
                WHEN s.TipoBloqueo IN ('D', 'A') AND s.DNI IS NULL
                    THEN 'El DNI es obligatorio para este tipo de bloqueo.'
                WHEN s.DNI IS NOT NULL AND s.DNI LIKE '%[^0-9A-Za-z]%'
                    THEN 'El DNI tiene caracteres no válidos.'
                WHEN s.DNI IS NOT NULL AND LEN(s.DNI) < 8
                    THEN 'El DNI tiene menos de 8 caracteres (¿se perdió un cero inicial?).'
                WHEN NULLIF(LTRIM(RTRIM(s.IdCarteraOrig)), '') IS NOT NULL
                     AND NOT EXISTS (SELECT 1 FROM bl.EntidadCartera ec
                                     WHERE ec.IdCartera = s.IdCarteraOrigen AND ec.IdEntidad = @IdEntidad)
                    THEN 'La cartera no existe o no pertenece a la entidad de la carga.'
                WHEN s.IdMotivo IS NULL
                    THEN 'Motivo vacío o no válido.'
                WHEN NULLIF(LTRIM(RTRIM(s.FechaInicioOrig)), '') IS NOT NULL AND s.FechaInicio IS NULL
                    THEN 'Fecha de inicio no válida (usar dd/mm/aaaa).'
                WHEN NULLIF(LTRIM(RTRIM(s.FechaFinOrig)), '') IS NOT NULL AND s.FechaFin IS NULL
                    THEN 'Fecha de fin no válida (usar dd/mm/aaaa).'
                WHEN s.FechaFin IS NOT NULL AND s.FechaFin < ISNULL(s.FechaInicio, @Hoy)
                    THEN 'La fecha de fin es anterior a la fecha de inicio.'
            END
        FROM bl.ListaNegra_Stg s
        WHERE s.IdCarga = @IdCarga;

        UPDATE bl.ListaNegra_Stg
        SET EstadoFila = 'ERROR'
        WHERE IdCarga = @IdCarga AND Error IS NOT NULL;

        UPDATE bl.ListaNegra_Stg
        SET FechaInicio = @Hoy
        WHERE IdCarga = @IdCarga AND Error IS NULL AND FechaInicio IS NULL;

        /* 10.3 Duplicados dentro del archivo (misma llave) */
        ;WITH d AS (
            SELECT s.IdStg,
                   ROW_NUMBER() OVER (
                       PARTITION BY s.TipoBloqueo,
                                    CASE WHEN s.TipoBloqueo IN ('T', 'A') THEN s.Telefono END,
                                    CASE WHEN s.TipoBloqueo IN ('D', 'A') THEN s.DNI END
                       ORDER BY s.Fila, s.IdStg) AS rn
            FROM bl.ListaNegra_Stg s
            WHERE s.IdCarga = @IdCarga AND s.EstadoFila IS NULL
        )
        UPDATE s
        SET EstadoFila = 'DUPLICADO_ARCHIVO'
        FROM bl.ListaNegra_Stg s
        INNER JOIN d ON d.IdStg = s.IdStg
        WHERE d.rn > 1;

        /* 10.4 Comparar con lo que ya existe activo en la entidad (misma llave) */
        UPDATE s
        SET IdListaNegra = x.IdListaNegra,
            EstadoFila = CASE
                WHEN x.IdListaNegra IS NULL                         THEN 'NUEVO'
                WHEN x.FechaFin IS NULL                             THEN 'SIN_CAMBIO'
                WHEN s.FechaFin IS NULL OR s.FechaFin > x.FechaFin  THEN 'EXTIENDE_VIGENCIA'
                ELSE 'SIN_CAMBIO'
            END
        FROM bl.ListaNegra_Stg s
        OUTER APPLY (
            SELECT TOP 1 l.IdListaNegra, l.FechaFin
            FROM bl.ListaNegra l
            WHERE l.IdEntidad = @IdEntidad
              AND l.Estado = 'A'
              AND l.TipoBloqueo = s.TipoBloqueo
              AND (s.TipoBloqueo = 'D' OR l.Telefono = s.Telefono)
              AND (s.TipoBloqueo = 'T' OR l.DNI = s.DNI)
        ) x
        WHERE s.IdCarga = @IdCarga AND s.EstadoFila IS NULL;

        /* 10.5 TELEFONO_CLIENTE nuevo pero ya cubierto por un bloqueo TELEFONO o CLIENTE de igual o mayor vigencia */
        UPDATE s
        SET EstadoFila = 'YA_CUBIERTO',
            IdListaNegra = c.IdListaNegra
        FROM bl.ListaNegra_Stg s
        CROSS APPLY (
            SELECT TOP 1 l.IdListaNegra
            FROM bl.ListaNegra l
            WHERE l.IdEntidad = @IdEntidad
              AND l.Estado = 'A'
              AND ((l.TipoBloqueo = 'T' AND l.Telefono = s.Telefono)
                OR (l.TipoBloqueo = 'D' AND l.DNI = s.DNI))
              AND (l.FechaFin IS NULL OR (s.FechaFin IS NOT NULL AND l.FechaFin >= s.FechaFin))
            ORDER BY CASE WHEN l.FechaFin IS NULL THEN 0 ELSE 1 END
        ) c
        WHERE s.IdCarga = @IdCarga AND s.EstadoFila = 'NUEVO' AND s.TipoBloqueo = 'A';

        /* 10.6 Aplicar (solo si se confirma) */
        IF @Confirmar = 1
        BEGIN
            DECLARE @Altas TABLE (IdListaNegra INT NOT NULL, IdStg BIGINT NOT NULL);
            DECLARE @Extensiones TABLE (IdListaNegra INT NOT NULL, FechaFinAnterior DATE NULL, FechaFinNueva DATE NULL);

            -- Altas
            MERGE bl.ListaNegra AS t
            USING (
                SELECT * FROM bl.ListaNegra_Stg WHERE IdCarga = @IdCarga AND EstadoFila = 'NUEVO'
            ) AS s
            ON 1 = 0
            WHEN NOT MATCHED THEN
                INSERT (IdEntidad, TipoBloqueo, Telefono, DNI, IdCarteraOrigen, IdMotivo, FechaInicio, FechaFin,
                        Estado, Referencia, Observacion, Origen, IdCarga, UsuarioRegistro)
                VALUES (@IdEntidad, s.TipoBloqueo, s.Telefono, s.DNI, s.IdCarteraOrigen, s.IdMotivo, s.FechaInicio, s.FechaFin,
                        'A', s.Referencia, s.Observacion, @Modo, @IdCarga, @Usuario)
            OUTPUT inserted.IdListaNegra, s.IdStg INTO @Altas (IdListaNegra, IdStg);

            UPDATE s
            SET IdListaNegra = a.IdListaNegra
            FROM bl.ListaNegra_Stg s
            INNER JOIN @Altas a ON a.IdStg = s.IdStg;

            INSERT INTO bl.ListaNegraEvento (IdListaNegra, TipoEvento, FechaFinNueva, IdCarga, Usuario)
            SELECT a.IdListaNegra, 'ALTA', s.FechaFin, @IdCarga, @Usuario
            FROM @Altas a
            INNER JOIN bl.ListaNegra_Stg s ON s.IdStg = a.IdStg;

            -- Extensiones de vigencia
            UPDATE l
            SET FechaFin = s.FechaFin
            OUTPUT inserted.IdListaNegra, deleted.FechaFin, inserted.FechaFin
                INTO @Extensiones (IdListaNegra, FechaFinAnterior, FechaFinNueva)
            FROM bl.ListaNegra l
            INNER JOIN bl.ListaNegra_Stg s ON s.IdListaNegra = l.IdListaNegra
            WHERE s.IdCarga = @IdCarga
              AND s.EstadoFila = 'EXTIENDE_VIGENCIA'
              AND l.Estado = 'A';

            INSERT INTO bl.ListaNegraEvento (IdListaNegra, TipoEvento, FechaFinAnterior, FechaFinNueva, Detalle, IdCarga, Usuario)
            SELECT e.IdListaNegra, 'EXTENSION', e.FechaFinAnterior, e.FechaFinNueva,
                   CASE WHEN e.FechaFinNueva IS NULL THEN 'Pasa a bloqueo permanente' END,
                   @IdCarga, @Usuario
            FROM @Extensiones e;

            -- Ratificaciones: la entidad volvió a reportar algo que ya estaba bloqueado
            INSERT INTO bl.ListaNegraEvento (IdListaNegra, TipoEvento, FechaFinNueva, Detalle, IdCarga, Usuario)
            SELECT s.IdListaNegra, 'RATIFICACION', s.FechaFin,
                   CASE s.EstadoFila
                       WHEN 'SIN_CAMBIO'  THEN 'Reportado nuevamente; ya estaba bloqueado con igual o mayor vigencia'
                       WHEN 'YA_CUBIERTO' THEN CONCAT('Teléfono-cliente ', s.Telefono, ' / ', s.DNI, ' ya cubierto por este bloqueo')
                   END,
                   @IdCarga, @Usuario
            FROM bl.ListaNegra_Stg s
            WHERE s.IdCarga = @IdCarga
              AND s.EstadoFila IN ('SIN_CAMBIO', 'YA_CUBIERTO')
              AND s.IdListaNegra IS NOT NULL;
        END;

        /* 10.7 Totales del lote */
        DECLARE @Total INT, @Nuevos INT, @Extendidos INT, @SinCambio INT, @Duplicados INT, @Errores INT;

        SELECT
            @Total      = COUNT(*),
            @Nuevos     = SUM(CASE WHEN EstadoFila = 'NUEVO'                       THEN 1 ELSE 0 END),
            @Extendidos = SUM(CASE WHEN EstadoFila = 'EXTIENDE_VIGENCIA'           THEN 1 ELSE 0 END),
            @SinCambio  = SUM(CASE WHEN EstadoFila IN ('SIN_CAMBIO', 'YA_CUBIERTO') THEN 1 ELSE 0 END),
            @Duplicados = SUM(CASE WHEN EstadoFila = 'DUPLICADO_ARCHIVO'           THEN 1 ELSE 0 END),
            @Errores    = SUM(CASE WHEN EstadoFila = 'ERROR'                       THEN 1 ELSE 0 END)
        FROM bl.ListaNegra_Stg
        WHERE IdCarga = @IdCarga;

        UPDATE bl.ControlCarga
        SET TotalRegistros      = ISNULL(@Total, 0),
            RegistrosOk         = ISNULL(@Nuevos, 0) + ISNULL(@Extendidos, 0),
            RegistrosError      = ISNULL(@Errores, 0),
            RegistrosNuevos     = ISNULL(@Nuevos, 0),
            RegistrosExtendidos = ISNULL(@Extendidos, 0),
            RegistrosSinCambio  = ISNULL(@SinCambio, 0),
            RegistrosDuplicados = ISNULL(@Duplicados, 0),
            Estado = CASE
                         WHEN @Confirmar = 0 THEN 'PREVISUALIZADO'
                         WHEN ISNULL(@Errores, 0) > 0 THEN 'OBSERVADO'
                         ELSE 'CONFIRMADO'
                     END,
            FechaFin          = CASE WHEN @Confirmar = 1 THEN GETDATE() END,
            FechaConfirmacion = CASE WHEN @Confirmar = 1 THEN SYSDATETIME() END
        WHERE IdCarga = @IdCarga;

        COMMIT;

        -- Resumen por clasificación
        SELECT EstadoFila, COUNT(*) AS Registros
        FROM bl.ListaNegra_Stg
        WHERE IdCarga = @IdCarga
        GROUP BY EstadoFila
        ORDER BY EstadoFila;
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0 ROLLBACK;

        UPDATE bl.ControlCarga
        SET Estado = 'ERROR',
            FechaFin = GETDATE(),
            Observacion = LEFT(CONCAT('Error ', ERROR_NUMBER(), ': ', ERROR_MESSAGE()), 500)
        WHERE IdCarga = @IdCarga;

        THROW;
    END CATCH;
END;
GO

/* -------------------------------------------------------------------------------------
   11. SP: LEVANTAR UN BLOQUEO (no se borra; queda estado L y evento)
   ------------------------------------------------------------------------------------- */
CREATE OR ALTER PROCEDURE bl.sp_ListaNegra_Levantar
    @IdListaNegra INT,
    @Motivo       VARCHAR(500),
    @Usuario      VARCHAR(20)
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    IF NULLIF(LTRIM(RTRIM(@Motivo)), '') IS NULL
        THROW 50020, 'Indica el motivo del levantamiento.', 1;
    IF NULLIF(LTRIM(RTRIM(@Usuario)), '') IS NULL
        THROW 50003, 'El usuario es obligatorio.', 1;

    BEGIN TRAN;

    UPDATE bl.ListaNegra
    SET Estado = 'L',
        UsuarioLevanta = @Usuario,
        FechaLevanta = SYSDATETIME(),
        MotivoLevanta = LTRIM(RTRIM(@Motivo))
    WHERE IdListaNegra = @IdListaNegra
      AND Estado = 'A';

    IF @@ROWCOUNT = 0
    BEGIN
        ROLLBACK;
        THROW 50021, 'El bloqueo no existe o ya fue levantado.', 1;
    END;

    INSERT INTO bl.ListaNegraEvento (IdListaNegra, TipoEvento, Detalle, Usuario)
    VALUES (@IdListaNegra, 'LEVANTAMIENTO', LEFT(LTRIM(RTRIM(@Motivo)), 500), @Usuario);

    COMMIT;

    SELECT * FROM bl.vw_ListaNegra WHERE IdListaNegra = @IdListaNegra;
END;
GO

/* -------------------------------------------------------------------------------------
   12. PERMISOS DEL USUARIO SQL DEL CRM (completar el nombre real y descomentar)
   ------------------------------------------------------------------------------------- */
-- CREATE USER [<usuario_sql_crm>] FOR LOGIN [<usuario_sql_crm>];
-- GRANT SELECT, INSERT ON bl.ListaNegra_Stg TO [<usuario_sql_crm>];
-- GRANT SELECT ON SCHEMA::bl TO [<usuario_sql_crm>];
-- GRANT EXECUTE ON SCHEMA::bl TO [<usuario_sql_crm>];
GO

/* -------------------------------------------------------------------------------------
   13. VALIDACIÓN POSTERIOR (solo lectura)
   ------------------------------------------------------------------------------------- */
SELECT e.Codigo AS Entidad, ec.IdCartera, ec.NombreCartera, ec.Activa
FROM bl.EntidadCartera ec
INNER JOIN bl.Entidad e ON e.IdEntidad = ec.IdEntidad
ORDER BY e.IdEntidad, ec.IdCartera;

SELECT Codigo, Descripcion FROM bl.Motivo ORDER BY IdMotivo;

SELECT bl.fn_NormalizarTelefono('+51 987-654-321') AS Caso1_esperado_987654321,
       bl.fn_NormalizarTelefono('51987654321')     AS Caso2_esperado_987654321,
       bl.fn_NormalizarTelefono('98765A321')       AS Caso3_esperado_NULL,
       bl.fn_NormalizarTelefono('9876543210')      AS Caso4_esperado_NULL;
GO

/* -------------------------------------------------------------------------------------
   14. PRUEBA COMPLETA SIN DEJAR DATOS (todo termina en ROLLBACK)
   Seleccionar desde BEGIN TRAN hasta ROLLBACK y ejecutar.
   ------------------------------------------------------------------------------------- */
/*
BEGIN TRAN;

    DECLARE @r TABLE (IdCarga INT, IdCargaPreviaMismoArchivo INT);
    INSERT INTO @r EXEC bl.sp_ListaNegra_CrearCarga @IdEntidad = 1, @Modo = 'MASIVA', @Usuario = '00000000', @Archivo = 'prueba.xlsx';
    DECLARE @IdCarga INT = (SELECT IdCarga FROM @r);

    INSERT INTO bl.ListaNegra_Stg (IdCarga, Fila, TipoBloqueoOrig, TelefonoOrig, DniOrig, IdCarteraOrig, MotivoOrig, FechaInicioOrig, FechaFinOrig)
    VALUES
        (@IdCarga, 2, 'TELEFONO',         '+51 900 000 001', '12345678', '126', 'SOLICITUD_ENTIDAD', NULL,         NULL),          -- NUEVO
        (@IdCarga, 3, 'TELEFONO',         '900000001',       NULL,       NULL,  'SOLICITUD_ENTIDAD', NULL,         NULL),          -- DUPLICADO_ARCHIVO
        (@IdCarga, 4, 'CLIENTE',          NULL,              '87654321', '144', 'FALLECIDO',         NULL,         NULL),          -- NUEVO
        (@IdCarga, 5, 'TELEFONO_CLIENTE', '900000001',       '11112222', NULL,  'TERCERO',           NULL,         NULL),          -- NUEVO (el bloqueo TELEFONO de la fila 2 aún no existía)
        (@IdCarga, 6, 'TELEFONO',         '90000000X',       NULL,       NULL,  'SOLICITUD_ENTIDAD', NULL,         NULL),          -- ERROR teléfono
        (@IdCarga, 7, 'CLIENTE',          NULL,              '1234567',  NULL,  'SOLICITUD_ENTIDAD', NULL,         NULL),          -- ERROR DNI corto
        (@IdCarga, 8, 'TELEFONO',         '900000002',       NULL,       '117', 'SOLICITUD_ENTIDAD', NULL,         NULL),          -- ERROR cartera de otra entidad
        (@IdCarga, 9, 'TELEFONO',         '900000003',       NULL,       NULL,  'SOLICITUD_ENTIDAD', '01/10/2026', '31/12/2026');  -- NUEVO temporal

    EXEC bl.sp_ListaNegra_ProcesarCarga @IdCarga = @IdCarga, @Confirmar = 0, @Usuario = '00000000';  -- previsualizar
    EXEC bl.sp_ListaNegra_ProcesarCarga @IdCarga = @IdCarga, @Confirmar = 1, @Usuario = '00000000';  -- confirmar

    SELECT Fila, TipoBloqueo, Telefono, DNI, EstadoFila, Error, IdListaNegra
    FROM bl.ListaNegra_Stg WHERE IdCarga = @IdCarga ORDER BY Fila;

    SELECT * FROM bl.vw_ListaNegra WHERE IdCarga = @IdCarga;
    SELECT * FROM bl.ListaNegraEvento WHERE IdCarga = @IdCarga;
    SELECT * FROM bl.ControlCarga WHERE IdCarga = @IdCarga;

    -- ¿Bloqueado en otra cartera de la misma entidad? (esperado: 1 fila)
    SELECT * FROM bl.fn_BloqueoContacto(133, '99999999', '900000001');
    -- ¿Bloqueado en otra entidad? (esperado: 0 filas)
    SELECT * FROM bl.fn_BloqueoContacto(117, '99999999', '900000001');

ROLLBACK;
*/
GO

/* -------------------------------------------------------------------------------------
   15. IMPACTO EN TELÉFONOS ACTUALES (solo lectura; ejecutar cuando haya bloqueos cargados)
   Si aparece un error de intercalación (collation), agregar COLLATE DATABASE_DEFAULT en las comparaciones.
   ------------------------------------------------------------------------------------- */
/*
SELECT t.IDCARTERA, COUNT(*) AS FilasBloqueadas, COUNT(DISTINCT t.DNI) AS ClientesAfectados
FROM DESARROLLO.dbo.TEMP_TELEFONOS t WITH (NOLOCK)
WHERE EXISTS (SELECT 1 FROM ControlCobranza.bl.fn_BloqueoContacto(t.IDCARTERA, RTRIM(LTRIM(t.DNI)), t.TELEFONO))
GROUP BY t.IDCARTERA
ORDER BY t.IDCARTERA;
*/
GO
