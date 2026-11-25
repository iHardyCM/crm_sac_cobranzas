/* =====================================================================================
   SCORE TELEFÓNICO · FASE 3 — ACTUALIZACIÓN POR CARTERA, CATÁLOGO Y SEGMENTOS
   Fecha: 14/11/2026 · Diseño: claude/diseno_generador_bases.md (proyecto crm_cobranzas)
   Requiere: fase 1, fase 2 y score_telefonico_alineacion.sql instalados.

   Cambios 14/11 (después de la primera corrida real):
     - sp_ActualizarTodas: si la alineación falla, el aviso queda en la bitácora de cada cartera
       (antes solo salía en la salida del job). sp_ActualizarCartera acepta @AvisoPrevio para eso.
     - sp_ArmarCaracteristicas: @Tiempos = 1 devuelve cuánto tarda cada sección (diagnóstico).
     - sp_ArmarCaracteristicas: equivocados después del último CEF calculados en bloque (diagnóstico 8:
       esa sección tomaba 110-120 s en las carteras con equivocados; mismo resultado).
     - sp_ActualizarCartera: paso 7, tabla de trabajo del generador (score_telefonico_fase4.sql). Si falla,
       queda como aviso; el score ya quedó actualizado. Nueva columna SegBase en la bitácora.
     - score.Campo: origen DATO (campos guardados en score.BaseTrabajoDato).

   Qué hace:
     1. "Actualizar cartera" (botón del CRM y job programado), con bitácora:
          historial de ayer (si falta o quedó a medias) → alineación con producción → universo de la
          cartera → historial de atributos → características → score.
        Cada cartera tiene su propio candado: dos carteras distintas no se esperan; si alguien ya está
        actualizando la misma, la segunda llamada devuelve "OCUPADA" y no lanza otra corrida.
     2. Universo por cartera: score.sp_ArmarUniversoCartera (mismas reglas que la fase 1, solo una cartera).
     3. Características, score e historial de atributos aceptan @IdCartera (NULL = todas, como hasta hoy;
        nada de lo que ya funciona cambia).
     4. "Actualizar todas" para el job: alinea una vez, actualiza cartera por cartera y retira del universo
        las carteras que ya no tienen clientes activos.
     5. Tablas del catálogo de campos y de segmentos del banco (se llenan en la fase siguiente, con la
        tabla de trabajo del CRM y la pantalla de carga).

   El historial del score sigue llegando hasta AYER (así se calibró). Lo de hoy se usa en vivo como
   condiciones del día al generar la base.

   Cómo ejecutarlo:
     Bloques 1 y 2: crean tablas y procedimientos (se pueden volver a ejecutar).
     Bloque 3: simulación de una cartera (no escribe).
     Bloque 4 (comentado): actualización real de una cartera y de todas.
     Bloque 5 (comentado): job del Agente SQL.
   ===================================================================================== */

USE CobAuto;
GO
SET NOCOUNT ON;
GO

/* =====================================================================================
   BLOQUE 1 · Tablas
   ===================================================================================== */

-- 1.1 Bitácora de actualizaciones
IF OBJECT_ID('score.ActualizacionCartera', 'U') IS NULL
CREATE TABLE score.ActualizacionCartera (
    IdActualizacion  INT IDENTITY(1, 1) NOT NULL CONSTRAINT PK_score_ActualizacionCartera PRIMARY KEY,
    IdCartera        INT            NOT NULL,
    Origen           VARCHAR(12)    NOT NULL,   -- MANUAL · PROGRAMADA
    Modo             VARCHAR(10)    NOT NULL,   -- REAL · SIMULACION
    Usuario          NVARCHAR(128)  NOT NULL,   -- DNI del usuario del CRM o JOB
    Inicio           DATETIME2(0)   NOT NULL,
    Fin              DATETIME2(0)   NULL,
    Estado           VARCHAR(12)    NOT NULL,   -- EN_CURSO · OK · SIMULADA · ERROR · INTERRUMPIDA
    Paso             VARCHAR(20)    NULL,       -- último paso iniciado
    HistorialHasta   DATE           NULL,       -- último día del historial que usó el score
    Version          INT            NULL,       -- versión de pesos
    Telefonos        INT            NULL,       -- teléfonos con score
    Excluidos        INT            NULL,       -- teléfonos excluidos por lista negra
    SegHistorial     INT            NULL,
    SegAlineacion    INT            NULL,
    SegUniverso      INT            NULL,
    SegCaracteristicas INT          NULL,
    SegScore         INT            NULL,
    Mensaje          NVARCHAR(2000) NULL,       -- error o aviso (por ejemplo, alineación no disponible)
    CONSTRAINT CK_score_ActualizacionCartera_Estado
        CHECK (Estado IN ('EN_CURSO', 'OK', 'SIMULADA', 'ERROR', 'INTERRUMPIDA'))
);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_ActualizacionCartera_Cartera' AND object_id = OBJECT_ID('score.ActualizacionCartera'))
    CREATE INDEX IX_ActualizacionCartera_Cartera ON score.ActualizacionCartera (IdCartera, Inicio DESC);
GO
-- Tiempo del paso de la tabla de trabajo (fase 4)
IF COL_LENGTH('score.ActualizacionCartera', 'SegBase') IS NULL
    ALTER TABLE score.ActualizacionCartera ADD SegBase INT NULL;
GO

-- 1.2 Catálogo de campos (diccionario de datos del generador de bases)
IF OBJECT_ID('score.Campo', 'U') IS NULL
CREATE TABLE score.Campo (
    Codigo         VARCHAR(60)    NOT NULL CONSTRAINT PK_score_Campo PRIMARY KEY,
    Etiqueta       NVARCHAR(100)  NOT NULL,
    Abreviatura    VARCHAR(12)    NULL,       -- para el nombre del archivo exportado
    Grupo          VARCHAR(20)    NOT NULL,
    TipoFiltro     VARCHAR(10)    NOT NULL,
    Origen         VARCHAR(10)    NOT NULL,   -- TRABAJO (columna de la tabla de trabajo) · DATO (score.BaseTrabajoDato) · SEGMENTO · DIA (en vivo)
    ColumnaOrigen  NVARCHAR(128)  NULL,
    IdEntidad      INT            NULL,       -- NULL = todas las entidades
    OrdenValores   NVARCHAR(1000) NULL,       -- valores de mejor a peor, separados por "|" (para ordenar y mostrar)
    Descripcion    NVARCHAR(500)  NOT NULL,   -- qué es
    Fuente         NVARCHAR(300)  NOT NULL,   -- de dónde sale
    Actualizacion  NVARCHAR(200)  NULL,       -- cada cuánto cambia
    Activo         BIT            NOT NULL CONSTRAINT DF_score_Campo_Activo DEFAULT (1),
    FechaCreacion  DATETIME2(0)   NOT NULL CONSTRAINT DF_score_Campo_Fecha DEFAULT (SYSDATETIME()),
    Usuario        NVARCHAR(128)  NOT NULL CONSTRAINT DF_score_Campo_Usuario DEFAULT (ORIGINAL_LOGIN()),
    CONSTRAINT CK_score_Campo_Grupo CHECK (Grupo IN ('SCORE', 'TELEFONO', 'CLIENTE', 'GESTION_CLIENTE',
                                                     'SEGMENTO_BANCO', 'SEGMENTO_PROPIO', 'CONDICION_DIA')),
    CONSTRAINT CK_score_Campo_Tipo CHECK (TipoFiltro IN ('LISTA', 'RANGO', 'FECHA', 'SINO', 'TEXTO')),
    CONSTRAINT CK_score_Campo_Origen CHECK (Origen IN ('TRABAJO', 'SEGMENTO', 'DIA', 'DATO'))
);
GO

-- 1.3 Dónde se traduce el código de cliente del banco a DNI, por entidad
IF OBJECT_ID('score.EntidadClaveCliente', 'U') IS NULL
CREATE TABLE score.EntidadClaveCliente (
    IdEntidad      INT            NOT NULL,
    Objeto         NVARCHAR(256)  NOT NULL,   -- tabla de asignación (3 partes)
    ColumnaCodigo  NVARCHAR(128)  NOT NULL,   -- código de cliente del banco
    ColumnaDNI     NVARCHAR(128)  NOT NULL,
    Nota           NVARCHAR(300)  NULL,
    Activo         BIT            NOT NULL CONSTRAINT DF_score_EntidadClaveCliente_Activo DEFAULT (1),
    CONSTRAINT PK_score_EntidadClaveCliente PRIMARY KEY (IdEntidad, Objeto)
);
GO
-- MiBanco castigo (diagnóstico 7 y Hardy, 14/11): COD_CLI es el identificador único del cliente en el banco
INSERT INTO score.EntidadClaveCliente (IdEntidad, Objeto, ColumnaCodigo, ColumnaDNI, Nota)
SELECT e.IdEntidad, N'Desarrollo.dbo.act_mibanco_castigo', N'COD_CLI', N'NRO_DOC',
       N'Asignación vigente de MiBanco castigo. COD_CLI es float: comparar como entero.'
FROM ControlCobranza.bl.Entidad AS e
WHERE e.Codigo = 'MIBANCO'
  AND NOT EXISTS (SELECT 1 FROM score.EntidadClaveCliente AS k
                  WHERE k.IdEntidad = e.IdEntidad AND k.Objeto = N'Desarrollo.dbo.act_mibanco_castigo');
GO

-- 1.4 Segmentos que envía el banco (o propios de Biznescob): una carga por archivo
IF OBJECT_ID('score.SegmentoCarga', 'U') IS NULL
CREATE TABLE score.SegmentoCarga (
    IdCarga          INT IDENTITY(1, 1) NOT NULL CONSTRAINT PK_score_SegmentoCarga PRIMARY KEY,
    IdEntidad        INT            NOT NULL,
    Fuente           VARCHAR(10)    NOT NULL,   -- BANCO · BIZNESCOB
    Segmento         NVARCHAR(100)  NOT NULL,   -- nombre de la carga (una carga nueva con el mismo nombre reemplaza a la vigente)
    Periodo          CHAR(6)        NOT NULL,   -- AAAAMM
    Archivo          NVARCHAR(260)  NOT NULL,
    ColumnaClave     NVARCHAR(128)  NOT NULL,
    TipoClave        VARCHAR(12)    NOT NULL,   -- CODIGO_BANCO · DNI
    FilasArchivo     INT            NOT NULL,
    ClientesCargados INT            NOT NULL,
    CodigosSinCruce  INT            NOT NULL,
    Estado           VARCHAR(12)    NOT NULL,   -- VIGENTE · REEMPLAZADA · ANULADA
    Usuario          NVARCHAR(128)  NOT NULL,
    FechaCarga       DATETIME2(0)   NOT NULL CONSTRAINT DF_score_SegmentoCarga_Fecha DEFAULT (SYSDATETIME()),
    CONSTRAINT CK_score_SegmentoCarga_Fuente CHECK (Fuente IN ('BANCO', 'BIZNESCOB')),
    CONSTRAINT CK_score_SegmentoCarga_Clave CHECK (TipoClave IN ('CODIGO_BANCO', 'DNI')),
    CONSTRAINT CK_score_SegmentoCarga_Estado CHECK (Estado IN ('VIGENTE', 'REEMPLAZADA', 'ANULADA'))
);
GO

IF OBJECT_ID('score.SegmentoCliente', 'U') IS NULL
CREATE TABLE score.SegmentoCliente (
    IdCarga      INT            NOT NULL CONSTRAINT FK_score_SegmentoCliente_Carga REFERENCES score.SegmentoCarga (IdCarga),
    Campo        VARCHAR(60)    NOT NULL CONSTRAINT FK_score_SegmentoCliente_Campo REFERENCES score.Campo (Codigo),
    CodigoBanco  VARCHAR(30)    NULL,
    DNI          VARCHAR(20)    NOT NULL,
    Valor        NVARCHAR(400)  NULL
);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_SegmentoCliente' AND object_id = OBJECT_ID('score.SegmentoCliente'))
    CREATE CLUSTERED INDEX IX_SegmentoCliente ON score.SegmentoCliente (IdCarga, Campo, DNI);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_SegmentoCliente_DNI' AND object_id = OBJECT_ID('score.SegmentoCliente'))
    CREATE INDEX IX_SegmentoCliente_DNI ON score.SegmentoCliente (DNI) INCLUDE (Campo, Valor);
GO

/* =====================================================================================
   BLOQUE 2 · Procedimientos
   ===================================================================================== */
-- 2.1 Universo de una cartera (mismas reglas que score.sp_ArmarTelefonoUniverso)
CREATE OR ALTER PROCEDURE score.sp_ArmarUniversoCartera
    @IdCartera INT,
    @Simular   BIT = 1
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    IF NOT EXISTS (SELECT 1 FROM ControlCobranza.bl.EntidadCartera WHERE IdCartera = @IdCartera)
        THROW 50401, 'La cartera no está en ControlCobranza.bl.EntidadCartera.', 1;
    IF OBJECT_ID('score.TelefonoUniverso', 'U') IS NULL
        THROW 50402, 'No existe score.TelefonoUniverso: ejecutar una vez score.sp_ArmarTelefonoUniverso (fase 1).', 1;

    -- Clientes activos de las carteras del score
    SELECT c.IdCartera, ec.IdEntidad, c.IdCliente,
           LEFT(LTRIM(RTRIM(c.Dni)), 20) COLLATE DATABASE_DEFAULT AS DNI
    INTO #cli
    FROM siscob.dbo.Cliente AS c WITH (NOLOCK)
    INNER JOIN ControlCobranza.bl.EntidadCartera AS ec ON ec.IdCartera = c.IdCartera
    WHERE c.Estado IN ('A', 'N')
      AND c.IdCartera = @IdCartera
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

    -- DNI que comparten el número: los de esta cartera más los que ya están en el universo de las demás
    UPDATE u SET N_DNI_Comparten = x.n
    FROM #u AS u
    INNER JOIN (SELECT Telefono, COUNT(DISTINCT DNI) AS n
                FROM (SELECT Telefono, DNI FROM #u
                      UNION
                      SELECT o.Telefono, o.DNI FROM score.TelefonoUniverso AS o
                      WHERE o.IdCartera <> @IdCartera AND o.Telefono IN (SELECT Telefono FROM #u)) AS t
                GROUP BY Telefono) AS x ON x.Telefono = u.Telefono;

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

    -- OSIPTEL = 'LN' también es lista negra (confirmado por Hardy el 14/11/2026)
    UPDATE u SET ExcluidoListaNegra = 1, MotivoExclusion = 'OSIPTEL_LN'
    FROM #u AS u
    WHERE u.ExcluidoListaNegra = 0 AND u.Osiptel = 'LN';

    IF @Simular = 1
    BEGIN
        SELECT 'SIMULACION' AS Modo, COUNT(*) AS filas, COUNT(DISTINCT DNI) AS clientes,
               COUNT(DISTINCT Telefono) AS telefonos, SUM(CAST(ExcluidoListaNegra AS INT)) AS excluidos_lista_negra
        FROM #u;

        SELECT u.IdCartera, COUNT(*) AS filas, COUNT(DISTINCT u.DNI) AS clientes,
               SUM(CASE WHEN u.ExcluidoListaNegra = 0 THEN 1 ELSE 0 END) AS filas_utiles,
               SUM(CASE WHEN u.MotivoExclusion LIKE 'LN_SISCOB%' THEN 1 ELSE 0 END) AS excluidos_ln_siscob,
               SUM(CASE WHEN u.MotivoExclusion LIKE 'LN_CRM%' THEN 1 ELSE 0 END) AS excluidos_ln_crm,
               SUM(CASE WHEN u.MotivoExclusion = 'OSIPTEL_LN' THEN 1 ELSE 0 END) AS excluidos_osiptel_ln,
               SUM(CASE WHEN u.Operador = 'NO_RECONOCIDO' THEN 1 ELSE 0 END) AS operador_no_reconocido,
               SUM(CASE WHEN u.N_DNI_Comparten > 1 THEN 1 ELSE 0 END) AS compartidos
        FROM #u AS u GROUP BY u.IdCartera ORDER BY u.IdCartera;

        RETURN;
    END;

    -- Reemplaza solo esta cartera. El candado compartido evita chocar con una reconstrucción completa
    -- (score.sp_ArmarTelefonoUniverso toma el mismo recurso en modo exclusivo para cambiar la tabla).
    BEGIN TRAN;
        DECLARE @Lock INT;
        EXEC @Lock = sp_getapplock @Resource = N'SCORE_TELEFONO_UNIVERSO', @LockMode = 'Shared',
                                   @LockOwner = 'Transaction', @LockTimeout = 60000;
        IF @Lock < 0 THROW 50403, 'Se está reconstruyendo el universo completo; intentar en unos minutos.', 1;

        DELETE FROM score.TelefonoUniverso WHERE IdCartera = @IdCartera;

        INSERT INTO score.TelefonoUniverso (
            FechaProceso, IdCartera, IdEntidad, IdCliente, DNI, Telefono,
            PrioridadColor, Osiptel, Whatsapp, Timbra, ApagadoSiscob, FalladoSiscob, Operador, AnioMesDato,
            OrigenTexto, ObservacionTexto, EsEmpresa, FechaAltaSiscob, FechaActSiscob,
            N_DNI_Comparten, ExcluidoListaNegra, MotivoExclusion)
        SELECT CAST(GETDATE() AS DATE), IdCartera, IdEntidad, IdCliente, DNI, Telefono,
               PrioridadColor, Osiptel, Whatsapp, Timbra, ApagadoSiscob, FalladoSiscob, Operador, AnioMesDato,
               OrigenTexto, ObservacionTexto, CAST(EsEmpresa AS BIT), FechaAltaSiscob, FechaActSiscob,
               N_DNI_Comparten, ExcluidoListaNegra, MotivoExclusion
        FROM #u;
    COMMIT;

    SELECT 'ACTUALIZADO' AS Modo, @IdCartera AS IdCartera, COUNT(*) AS filas,
           SUM(CAST(ExcluidoListaNegra AS INT)) AS excluidos_lista_negra
    FROM score.TelefonoUniverso WHERE IdCartera = @IdCartera;
END;
GO

-- 2.2 Historial de atributos: ahora acepta @IdCartera (NULL = todas, como antes)
CREATE OR ALTER PROCEDURE score.sp_RegistrarAtributosTelefono
    @IdCartera INT = NULL      -- NULL = todas las carteras
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    DECLARE @Hoy DATE = CAST(GETDATE() AS DATE);

    IF OBJECT_ID('score.TelefonoUniverso', 'U') IS NULL
        THROW 50301, 'No existe score.TelefonoUniverso. Ejecutar antes score.sp_ArmarTelefonoUniverso.', 1;

    BEGIN TRAN;
        -- Si ya corrió hoy (por ejemplo, antes de alinear con producción), la foto de hoy se corrige en su lugar
        UPDATE h SET PrioridadColor = u.PrioridadColor, Osiptel = u.Osiptel, Whatsapp = u.Whatsapp, Timbra = u.Timbra
        FROM score.TelefonoAtributoHist AS h
        INNER JOIN score.TelefonoUniverso AS u
                ON u.IdCartera = h.IdCartera AND u.DNI = h.DNI AND u.Telefono = h.Telefono
        WHERE h.Desde = @Hoy AND (@IdCartera IS NULL OR h.IdCartera = @IdCartera);

        DELETE h FROM score.TelefonoAtributoHist AS h
        WHERE h.Desde = @Hoy AND (@IdCartera IS NULL OR h.IdCartera = @IdCartera)
          AND NOT EXISTS (SELECT 1 FROM score.TelefonoUniverso AS u
                          WHERE u.IdCartera = h.IdCartera AND u.DNI = h.DNI AND u.Telefono = h.Telefono);

        -- Cierra lo que cambió o ya no está en el universo
        UPDATE h SET Hasta = DATEADD(DAY, -1, @Hoy)
        FROM score.TelefonoAtributoHist AS h
        LEFT JOIN score.TelefonoUniverso AS u
               ON u.IdCartera = h.IdCartera AND u.DNI = h.DNI AND u.Telefono = h.Telefono
        WHERE h.Hasta IS NULL
          AND h.Desde < @Hoy
          AND (@IdCartera IS NULL OR h.IdCartera = @IdCartera)
          AND (u.Telefono IS NULL
               OR ISNULL(u.PrioridadColor, '') <> ISNULL(h.PrioridadColor, '')
               OR ISNULL(u.Osiptel, '')        <> ISNULL(h.Osiptel, '')
               OR ISNULL(u.Whatsapp, '')       <> ISNULL(h.Whatsapp, '')
               OR ISNULL(u.Timbra, 255)        <> ISNULL(h.Timbra, 255));

        -- Abre una fila para lo nuevo o lo que cambió
        INSERT INTO score.TelefonoAtributoHist (IdCartera, DNI, Telefono, Desde, Hasta, PrioridadColor, Osiptel, Whatsapp, Timbra)
        SELECT u.IdCartera, u.DNI, u.Telefono, @Hoy, NULL, u.PrioridadColor, u.Osiptel, u.Whatsapp, u.Timbra
        FROM score.TelefonoUniverso AS u
        WHERE (@IdCartera IS NULL OR u.IdCartera = @IdCartera)
          AND NOT EXISTS (SELECT 1 FROM score.TelefonoAtributoHist AS h
                          WHERE h.IdCartera = u.IdCartera AND h.DNI = u.DNI AND h.Telefono = u.Telefono
                            AND (h.Hasta IS NULL OR h.Desde = @Hoy));
    COMMIT;

    SELECT @Hoy AS Fecha,
           SUM(CASE WHEN Desde = @Hoy THEN 1 ELSE 0 END) AS filas_abiertas_hoy,
           SUM(CASE WHEN Hasta = DATEADD(DAY, -1, @Hoy) THEN 1 ELSE 0 END) AS filas_cerradas_hoy
    FROM score.TelefonoAtributoHist
    WHERE (Desde = @Hoy OR Hasta = DATEADD(DAY, -1, @Hoy))
      AND (@IdCartera IS NULL OR IdCartera = @IdCartera);
END;
GO

-- 2.3 Características: ahora acepta @IdCartera (NULL = todas, como antes)
CREATE OR ALTER PROCEDURE score.sp_ArmarCaracteristicas
    @FechaCorte DATE,
    @Poblacion  VARCHAR(10) = 'UNIVERSO',   -- MARCADOS | UNIVERSO
    @Simular    BIT = 1,
    @IdCartera  INT = NULL,                 -- NULL = todas las carteras
    @Tiempos    BIT = 0                     -- 1 = devuelve al final cuánto tardó cada sección (diagnóstico)
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    DECLARE @T TABLE (Orden INT IDENTITY(1, 1), Seccion VARCHAR(40), Filas INT, Ms INT);
    DECLARE @t0 DATETIME2(3) = SYSDATETIME();

    IF @Poblacion NOT IN ('MARCADOS', 'UNIVERSO')
        THROW 50311, 'Poblacion debe ser MARCADOS o UNIVERSO.', 1;

    DECLARE @Ini90 DATE = DATEADD(DAY, -90, @FechaCorte),
            @Ini30 DATE = DATEADD(DAY, -30, @FechaCorte),
            @FinFut DATE = DATEADD(DAY, 7, @FechaCorte),
            @PrimerDia DATE = (SELECT MIN(Fecha) FROM score.TelefonoDiaControl),
            @UltimoDia DATE = (SELECT MAX(Fecha) FROM score.TelefonoDiaControl);

    IF @PrimerDia IS NULL OR @Ini90 < @PrimerDia
        THROW 50312, 'No hay 90 días de historial antes de la fecha de corte.', 1;
    IF @Poblacion = 'MARCADOS' AND DATEADD(DAY, 6, @FechaCorte) > @UltimoDia
        THROW 50313, 'Para MARCADOS hace falta el historial de la semana siguiente a la fecha de corte (D a D+6).', 1;
    IF @Poblacion = 'UNIVERSO' AND OBJECT_ID('score.TelefonoUniverso', 'U') IS NULL
        THROW 50314, 'No existe score.TelefonoUniverso.', 1;

    /* 1. Población */
    CREATE TABLE #pob (
        IdCartera INT NOT NULL, DNI VARCHAR(20) COLLATE DATABASE_DEFAULT NOT NULL,
        Telefono CHAR(9) COLLATE DATABASE_DEFAULT NOT NULL,
        IntentosFut INT NULL, EXITO BIT NULL,
        PRIMARY KEY (IdCartera, DNI, Telefono));

    IF @Poblacion = 'MARCADOS'
        INSERT INTO #pob (IdCartera, DNI, Telefono, IntentosFut, EXITO)
        SELECT IdCartera, DNI, Telefono,
               SUM(IntentosHumano + IntentosMaquina),
               MAX(CASE WHEN N_TITULAR + N_TERCERO_ACUERDO > 0 THEN 1 ELSE 0 END)
        FROM score.TelefonoDia
        WHERE Fecha >= @FechaCorte AND Fecha < @FinFut
          AND (@IdCartera IS NULL OR IdCartera = @IdCartera)
        GROUP BY IdCartera, DNI, Telefono
        HAVING SUM(IntentosHumano + IntentosMaquina) > 0;
    ELSE
        INSERT INTO #pob (IdCartera, DNI, Telefono)
        SELECT IdCartera, DNI, Telefono
        FROM score.TelefonoUniverso
        WHERE ExcluidoListaNegra = 0
          AND (@IdCartera IS NULL OR IdCartera = @IdCartera);

    INSERT INTO @T VALUES ('1_POBLACION', (SELECT COUNT(*) FROM #pob), DATEDIFF(MILLISECOND, @t0, SYSDATETIME()));
    SET @t0 = SYSDATETIME();

    /* 2. Historial de 90 días por cartera + DNI + teléfono */
    SELECT d.IdCartera, d.DNI, d.Telefono,
           SUM(d.IntentosHumano + d.IntentosMaquina) AS Intentos90,
           SUM(CASE WHEN d.Fecha >= @Ini30 THEN d.IntentosHumano + d.IntentosMaquina ELSE 0 END) AS Intentos30,
           SUM(d.N_TITULAR + d.N_TERCERO_ACUERDO) AS Cef90,
           MAX(CASE WHEN d.N_TITULAR + d.N_TERCERO_ACUERDO > 0 THEN d.Fecha END) AS UltCef,
           MAX(CASE WHEN d.N_TERCERO > 0 THEN d.Fecha END) AS UltTercero,
           MAX(CASE WHEN d.IntentosHumano + d.IntentosMaquina > 0 THEN d.Fecha END) AS UltIntento,
           MAX(CASE WHEN d.N_EQUIVOCADO > 0 THEN d.Fecha END) AS UltEquivocado,
           SUM(d.LlamadasCentralita) AS Central90,
           SUM(d.N_NO_CONTESTA) AS NoContesta90, SUM(d.N_BUZON) AS Buzon90,
           SUM(d.N_APAGADO) AS Apagado90, SUM(d.N_CONTESTA_SIN_ID) AS ContestaSinId90,
           SUM(d.Contactos_Manana) AS cM, SUM(d.Contactos_Medio) AS cMe,
           SUM(d.Contactos_Tarde) AS cT, SUM(d.Contactos_Noche) AS cN,
           CAST(NULL AS INT) AS EquivSinCef
    INTO #h
    FROM score.TelefonoDia AS d
    INNER JOIN #pob AS p ON p.IdCartera = d.IdCartera AND p.DNI = d.DNI AND p.Telefono = d.Telefono
    WHERE d.Fecha >= @Ini90 AND d.Fecha < @FechaCorte
    GROUP BY d.IdCartera, d.DNI, d.Telefono;

    CREATE CLUSTERED INDEX IX_h ON #h (IdCartera, DNI, Telefono);

    INSERT INTO @T VALUES ('2_HISTORIAL_90', (SELECT COUNT(*) FROM #h), DATEDIFF(MILLISECOND, @t0, SYSDATETIME()));
    SET @t0 = SYSDATETIME();

    /* Equivocados para este DNI después del último CEF (diagnóstico 5: con 1 solo evento el teléfono
       tuvo 7,2 % de CEF la semana siguiente; con 2 o más, 1,5 %).
       Diagnóstico 8 (14/11): la versión anterior buscaba fila por fila en score.TelefonoDia, cuyo índice
       empieza por Fecha, y releía los 90 días por cada teléfono (121 s para 80 teléfonos en la 112).
       Ahora se leen una sola vez los días con equivocado de la población y se cruzan en bloque.
       El resultado es el mismo: suma de equivocados con fecha posterior al último CEF. */
    SELECT d.IdCartera, d.DNI, d.Telefono, d.Fecha, d.N_EQUIVOCADO
    INTO #eq
    FROM score.TelefonoDia AS d
    INNER JOIN #pob AS p ON p.IdCartera = d.IdCartera AND p.DNI = d.DNI AND p.Telefono = d.Telefono
    WHERE d.Fecha >= @Ini90 AND d.Fecha < @FechaCorte
      AND d.N_EQUIVOCADO > 0;

    UPDATE h SET EquivSinCef = x.n
    FROM #h AS h
    INNER JOIN (
        SELECT e.IdCartera, e.DNI, e.Telefono, SUM(e.N_EQUIVOCADO) AS n
        FROM #eq AS e
        INNER JOIN #h AS h2 ON h2.IdCartera = e.IdCartera AND h2.DNI = e.DNI AND h2.Telefono = e.Telefono
        WHERE e.Fecha > ISNULL(h2.UltCef, '19000101')
        GROUP BY e.IdCartera, e.DNI, e.Telefono
    ) AS x ON x.IdCartera = h.IdCartera AND x.DNI = h.DNI AND x.Telefono = h.Telefono;

    INSERT INTO @T VALUES ('2B_EQUIVOCADOS', (SELECT COUNT(*) FROM #h WHERE UltEquivocado IS NOT NULL),
                           DATEDIFF(MILLISECOND, @t0, SYSDATETIME()));
    SET @t0 = SYSDATETIME();

    /* 3. "No existe" se mira por número (cualquier cliente), con el último CEF del número */
    SELECT d.Telefono,
           MAX(CASE WHEN d.N_NO_EXISTE > 0 THEN d.Fecha END) AS UltNoExiste,
           MAX(CASE WHEN d.N_TITULAR + d.N_TERCERO_ACUERDO > 0 THEN d.Fecha END) AS UltCefTel
    INTO #ne
    FROM score.TelefonoDia AS d
    WHERE d.Fecha >= @Ini90 AND d.Fecha < @FechaCorte
      AND d.Telefono IN (SELECT Telefono FROM #pob)
    GROUP BY d.Telefono
    HAVING MAX(CASE WHEN d.N_NO_EXISTE > 0 THEN 1 ELSE 0 END) = 1;

    CREATE CLUSTERED INDEX IX_ne ON #ne (Telefono);

    INSERT INTO @T VALUES ('3_NO_EXISTE', (SELECT COUNT(*) FROM #ne), DATEDIFF(MILLISECOND, @t0, SYSDATETIME()));
    SET @t0 = SYSDATETIME();

    /* 4. Características en tramos */
    SELECT
        @FechaCorte AS FechaCorte, @Poblacion AS Poblacion, p.IdCartera, p.DNI, p.Telefono,

        CASE WHEN h.UltCef IS NULL THEN 'SIN_CEF_90'
             WHEN DATEDIFF(DAY, h.UltCef, @FechaCorte) <= 7  THEN '1-7'
             WHEN DATEDIFF(DAY, h.UltCef, @FechaCorte) <= 30 THEN '8-30'
             ELSE '31-90' END AS T_ULT_CEF,

        CASE WHEN h.UltTercero IS NULL THEN 'SIN_TERC_90'
             WHEN DATEDIFF(DAY, h.UltTercero, @FechaCorte) <= 30 THEN '1-30'
             ELSE '31-90' END AS T_ULT_TERCERO,

        CASE WHEN ISNULL(h.Intentos90, 0) = 0 THEN 'SIN_INTENTOS'
             WHEN h.Cef90 = 0 THEN '0'
             WHEN 1.0 * h.Cef90 / h.Intentos90 < 0.05 THEN '<5%'
             WHEN 1.0 * h.Cef90 / h.Intentos90 < 0.15 THEN '5-15%'
             ELSE '>=15%' END AS T_TASA_CEF_90,

        CASE WHEN ISNULL(h.Intentos30, 0) = 0 THEN '0'
             WHEN h.Intentos30 <= 3  THEN '1-3'
             WHEN h.Intentos30 <= 10 THEN '4-10'
             WHEN h.Intentos30 <= 30 THEN '11-30'
             ELSE '>30' END AS T_INTENTOS_30,

        CASE WHEN h.UltIntento IS NULL THEN 'SIN_INT_90'
             WHEN DATEDIFF(DAY, h.UltIntento, @FechaCorte) <= 7  THEN '1-7'
             WHEN DATEDIFF(DAY, h.UltIntento, @FechaCorte) <= 30 THEN '8-30'
             ELSE '31-90' END AS T_ULT_INTENTO,

        CASE WHEN ISNULL(h.ContestaSinId90, 0) > 0 THEN 'CONTESTA'
             WHEN ISNULL(h.NoContesta90, 0) + ISNULL(h.Buzon90, 0) + ISNULL(h.Apagado90, 0) = 0 THEN 'SIN_DATO'
             WHEN 2 * h.Apagado90 > h.NoContesta90 + h.Buzon90 + h.Apagado90 THEN 'APAGADO'
             WHEN 2 * h.Buzon90   > h.NoContesta90 + h.Buzon90 + h.Apagado90 THEN 'BUZON'
             ELSE 'TIMBRA' END AS T_MAQUINA_90,

        CASE WHEN ISNULL(h.EquivSinCef, 0) >= 2 THEN 'SI' ELSE 'NO' END AS F_EQUIVOCADO_DNI,

        CASE WHEN ne.UltNoExiste IS NOT NULL AND (ne.UltCefTel IS NULL OR ne.UltNoExiste > ne.UltCefTel)
             THEN 'SI' ELSE 'NO' END AS F_NO_EXISTE,

        CASE WHEN a.Telefono IS NULL THEN 'SIN_DATO'
             WHEN UPPER(a.OrigenTexto) = 'EMPRESA' OR a.EsEmpresa = 1
                  OR UPPER(ISNULL(a.ObservacionTexto, N'')) LIKE N'EMP%' THEN 'EMPRESA'
             WHEN a.Operador IN ('ENTEL', 'MOVISTAR', 'CLARO') THEN 'OPERADORA'
             WHEN UPPER(a.OrigenTexto) = 'BUSQUEDA' THEN 'BUSQUEDA'
             WHEN UPPER(a.OrigenTexto) = 'CLIENTE' THEN 'CLIENTE'
             ELSE 'OTRO' END AS S_ORIGEN,

        CASE WHEN a.Telefono IS NULL THEN 'SIN_DATO'
             WHEN UPPER(ISNULL(a.ObservacionTexto, N'')) LIKE N'BI%'
               OR UPPER(ISNULL(a.ObservacionTexto, N'')) LIKE N'B I%' THEN 'BASE_INTERNA'
             WHEN UPPER(ISNULL(a.ObservacionTexto, N'')) LIKE N'%SEARCH%' THEN 'SEARCH'
             WHEN UPPER(ISNULL(a.ObservacionTexto, N'')) LIKE N'%ENRIQUEC%' THEN 'ENRIQUECIMIENTO'
             ELSE 'OTRA' END AS S_FUENTE,

        CASE WHEN m.MesesDato IS NULL OR m.MesesDato < 0 THEN 'SIN_DATO'
             WHEN m.MesesDato < 12 THEN '<1A'
             WHEN m.MesesDato < 36 THEN '1-2A'
             WHEN m.MesesDato < 72 THEN '3-5A'
             ELSE '>5A' END AS S_ANTIG_DATO,

        CASE WHEN a.Osiptel IS NULL THEN 'SIN_DATO' ELSE CAST(a.Osiptel AS VARCHAR(12)) END AS S_OSIPTEL,
        CASE WHEN a.Whatsapp IS NULL THEN 'SIN_DATO' ELSE CAST(a.Whatsapp AS VARCHAR(12)) END AS S_WHATSAPP,
        CASE WHEN a.Telefono IS NULL OR a.Timbra IS NULL THEN 'SIN_DATO'
             ELSE CONVERT(VARCHAR(12), a.Timbra) END AS S_TIMBRA,

        CASE WHEN a.Telefono IS NULL THEN 'SIN_DATO'
             WHEN UPPER(ISNULL(a.ObservacionTexto, N'')) LIKE N'%PREPAGO%' THEN 'PREPAGO'
             WHEN UPPER(ISNULL(a.ObservacionTexto, N'')) LIKE N'%POSTPAGO%'
               OR UPPER(ISNULL(a.ObservacionTexto, N'')) LIKE N'%POST PAGO%' THEN 'POSTPAGO'
             WHEN UPPER(ISNULL(a.ObservacionTexto, N'')) LIKE N'%CONTROL%' THEN 'CONTROL'
             ELSE 'NO_INFORMA' END AS S_TIPO_LINEA,

        CASE WHEN a.Telefono IS NULL THEN 'SIN_DATO'
             WHEN UPPER(ISNULL(a.ObservacionTexto, N'')) LIKE N'%AVAL%' THEN 'AVAL'
             WHEN UPPER(ISNULL(a.ObservacionTexto, N'')) LIKE N'%CONYUG%' THEN 'CONYUGE'
             WHEN UPPER(ISNULL(a.ObservacionTexto, N'')) LIKE N'%HIJ%'
               OR UPPER(ISNULL(a.ObservacionTexto, N'')) LIKE N'%HERMAN%'
               OR UPPER(ISNULL(a.ObservacionTexto, N'')) LIKE N'%PADRE%'
               OR UPPER(ISNULL(a.ObservacionTexto, N'')) LIKE N'%MADRE%'
               OR UPPER(ISNULL(a.ObservacionTexto, N'')) LIKE N'%FAMILI%' THEN 'FAMILIAR'
             WHEN UPPER(ISNULL(a.ObservacionTexto, N'')) LIKE N'%TITULAR%' THEN 'TITULAR'
             WHEN UPPER(ISNULL(a.ObservacionTexto, N'')) LIKE N'%REFERENCIA%' THEN 'REFERENCIA'
             ELSE 'NO_INFORMA' END AS S_RELACION,

        CASE WHEN a.N_DNI_Comparten IS NULL THEN 'SIN_DATO'
             WHEN a.N_DNI_Comparten = 1 THEN '1'
             WHEN a.N_DNI_Comparten <= 4 THEN '2-4'
             ELSE '5+' END AS S_COMPARTIDO,

        CASE WHEN a.Telefono IS NULL THEN 'SIN_DATO'
             WHEN a.PrioridadColor IN ('V', 'T', 'A', 'R', 'F') THEN CAST(a.PrioridadColor AS VARCHAR(12))
             WHEN a.PrioridadColor IN ('P', 'Q') THEN 'PQ'
             ELSE 'OTRO' END AS S_COLOR,

        DATEDIFF(DAY, h.UltCef, @FechaCorte) AS DiasUltCef,
        h.UltIntento AS UltimoIntento,
        CASE WHEN ISNULL(h.cM, 0) + ISNULL(h.cMe, 0) + ISNULL(h.cT, 0) + ISNULL(h.cN, 0) = 0 THEN NULL
             WHEN h.cM >= h.cMe AND h.cM >= h.cT AND h.cM >= h.cN THEN 'MANANA'
             WHEN h.cMe >= h.cT AND h.cMe >= h.cN THEN 'MEDIO'
             WHEN h.cT >= h.cN THEN 'TARDE'
             ELSE 'NOCHE' END AS FranjaContacto,

        p.IntentosFut,
        CASE WHEN p.IntentosFut IS NULL THEN NULL
             WHEN p.IntentosFut = 1 THEN '1'
             WHEN p.IntentosFut <= 3 THEN '2-3'
             WHEN p.IntentosFut <= 10 THEN '4-10'
             ELSE '>10' END AS C_INTENTOS_FUT,
        p.EXITO,
        CASE WHEN CAST(a.FechaAltaSiscob AS DATE) >= @FechaCorte THEN 1 ELSE 0 END AS AltaDesdeCorte
    INTO #c
    FROM #pob AS p
    LEFT JOIN #h AS h ON h.IdCartera = p.IdCartera AND h.DNI = p.DNI AND h.Telefono = p.Telefono
    LEFT JOIN #ne AS ne ON ne.Telefono = p.Telefono
    OUTER APPLY (
        SELECT TOP 1 u.Telefono, u.OrigenTexto, u.EsEmpresa, u.ObservacionTexto, u.Operador, u.AnioMesDato,
               u.Osiptel, u.Whatsapp, u.Timbra, u.N_DNI_Comparten, u.PrioridadColor, u.FechaAltaSiscob
        FROM score.TelefonoUniverso AS u
        WHERE u.Telefono = p.Telefono AND u.DNI = p.DNI
        ORDER BY CASE WHEN u.IdCartera = p.IdCartera THEN 0 ELSE 1 END
    ) AS a
    OUTER APPLY (SELECT DATEDIFF(MONTH, TRY_CONVERT(DATE, a.AnioMesDato + '01', 112), @FechaCorte) AS MesesDato) AS m;

    INSERT INTO @T VALUES ('4_TRAMOS', (SELECT COUNT(*) FROM #c), DATEDIFF(MILLISECOND, @t0, SYSDATETIME()));
    SET @t0 = SYSDATETIME();

    /* En entrenamiento se dejan fuera los teléfonos que ya no están en el universo de hoy: no tienen atributos
       y, sobre todo, muchos salieron porque el cliente pagó o dejó la asignación; mantenerlos haría que
       "sin atributos" pareciera un buen tramo, algo que en el score de hoy casi no existe. */
    DECLARE @SinAtributos INT = 0, @AltaDesdeCorte INT = 0;
    IF @Poblacion = 'MARCADOS'
    BEGIN
        DELETE FROM #c WHERE S_ORIGEN = 'SIN_DATO';
        SET @SinAtributos = @@ROWCOUNT;

        /* Tampoco entran los teléfonos dados de alta en SISCOB desde la fecha de corte: no existían al corte.
           Diagnóstico 5: muchos son números que el cliente dio en la misma llamada del CEF (hasta 64 % de
           "éxito"), lo que haría que un número nuevo sin validar pareciera el mejor. */
        DELETE FROM #c WHERE AltaDesdeCorte = 1;
        SET @AltaDesdeCorte = @@ROWCOUNT;
    END;

    IF @Simular = 1
    BEGIN
        SELECT 'SIMULACION' AS Modo, @FechaCorte AS FechaCorte, @Poblacion AS Poblacion,
               COUNT(*) AS filas, COUNT(DISTINCT DNI) AS clientes,
               SUM(CAST(EXITO AS INT)) AS exitos,
               CAST(100.0 * AVG(CAST(EXITO AS FLOAT)) AS DECIMAL(6, 2)) AS tasa_exito_pct,
               @SinAtributos AS descartados_sin_atributos, @AltaDesdeCorte AS descartados_alta_desde_corte
        FROM #c;
        SELECT T_ULT_CEF, COUNT(*) AS filas, CAST(100.0 * AVG(CAST(EXITO AS FLOAT)) AS DECIMAL(6, 2)) AS tasa_exito_pct
        FROM #c GROUP BY T_ULT_CEF ORDER BY T_ULT_CEF;
        IF @Tiempos = 1
            SELECT Seccion, Filas, Ms, CAST(Ms / 1000.0 AS DECIMAL(9, 1)) AS Segundos FROM @T ORDER BY Orden;
        RETURN;
    END;

    BEGIN TRAN;
        DELETE FROM score.Caracteristicas
        WHERE FechaCorte = @FechaCorte AND Poblacion = @Poblacion
          AND (@IdCartera IS NULL OR IdCartera = @IdCartera);

        INSERT INTO score.Caracteristicas (
            FechaCorte, Poblacion, IdCartera, DNI, Telefono,
            T_ULT_CEF, T_ULT_TERCERO, T_TASA_CEF_90, T_INTENTOS_30, T_ULT_INTENTO, T_MAQUINA_90,
            F_EQUIVOCADO_DNI, F_NO_EXISTE,
            S_ORIGEN, S_FUENTE, S_ANTIG_DATO, S_OSIPTEL, S_WHATSAPP, S_TIMBRA, S_TIPO_LINEA, S_RELACION,
            S_COMPARTIDO, S_COLOR, DiasUltCef, UltimoIntento, FranjaContacto, IntentosFut, C_INTENTOS_FUT, EXITO)
        SELECT FechaCorte, Poblacion, IdCartera, DNI, Telefono,
            T_ULT_CEF, T_ULT_TERCERO, T_TASA_CEF_90, T_INTENTOS_30, T_ULT_INTENTO, T_MAQUINA_90,
            F_EQUIVOCADO_DNI, F_NO_EXISTE,
            S_ORIGEN, S_FUENTE, S_ANTIG_DATO, S_OSIPTEL, S_WHATSAPP, S_TIMBRA, S_TIPO_LINEA, S_RELACION,
            S_COMPARTIDO, S_COLOR, DiasUltCef, UltimoIntento, FranjaContacto, IntentosFut, C_INTENTOS_FUT, EXITO
        FROM #c;

        -- El universo diario solo se guarda 7 días (el score diario queda en score.TelefonoScore)
        IF @Poblacion = 'UNIVERSO'
            DELETE FROM score.Caracteristicas
            WHERE Poblacion = 'UNIVERSO' AND FechaCorte < DATEADD(DAY, -7, @FechaCorte);
    COMMIT;

    INSERT INTO @T VALUES ('5_GUARDAR', (SELECT COUNT(*) FROM #c), DATEDIFF(MILLISECOND, @t0, SYSDATETIME()));
    IF @Tiempos = 1
        SELECT Seccion, Filas, Ms, CAST(Ms / 1000.0 AS DECIMAL(9, 1)) AS Segundos FROM @T ORDER BY Orden;

    SELECT 'GUARDADO' AS Modo, @FechaCorte AS FechaCorte, @Poblacion AS Poblacion, @IdCartera AS IdCartera, COUNT(*) AS filas,
           SUM(CAST(EXITO AS INT)) AS exitos, @SinAtributos AS descartados_sin_atributos,
           @AltaDesdeCorte AS descartados_alta_desde_corte
    FROM #c;
END;
GO

-- 2.4 Score: ahora acepta @IdCartera (NULL = todas, como antes)
CREATE OR ALTER PROCEDURE score.sp_CalcularScore
    @FechaCorte  DATE = NULL,     -- por defecto hoy
    @Version     INT  = NULL,     -- por defecto la publicada
    @Simular     BIT  = 1,
    @DiasHistoria INT = 90,       -- días de score que se conservan (para medir el acierto)
    @IdCartera   INT  = NULL      -- NULL = todas las carteras
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    SET @FechaCorte = ISNULL(@FechaCorte, CAST(GETDATE() AS DATE));
    IF @Version IS NULL SELECT @Version = Version FROM score.PesoVersion WHERE Estado = 'PUBLICADA';
    IF @Version IS NULL THROW 50331, 'No hay una versión de pesos publicada (o indique @Version).', 1;
    IF NOT EXISTS (SELECT 1 FROM score.Caracteristicas WHERE FechaCorte = @FechaCorte AND Poblacion = 'UNIVERSO'
                   AND (@IdCartera IS NULL OR IdCartera = @IdCartera))
        THROW 50332, 'Faltan las características del universo para esa fecha (score.sp_ArmarCaracteristicas).', 1;

    DECLARE @Max DECIMAL(9, 2), @A DECIMAL(5, 1), @B DECIMAL(5, 1), @C DECIMAL(5, 1), @D DECIMAL(5, 1);
    SELECT @Max = PuntosMaximos, @A = Tramo_A, @B = Tramo_B, @C = Tramo_C, @D = Tramo_D
    FROM score.PesoVersion WHERE Version = @Version;

    -- Características que usa la versión (las demás no suman)
    SELECT DISTINCT Caracteristica INTO #cv FROM score.Peso WHERE Version = @Version;

    -- Puntos por característica. Un tramo que la versión no conoce recibe los puntos del tramo de
    -- referencia (fila Tramo = '*') y se cuenta en TramosSinPeso.
    SELECT c.IdCartera, c.DNI, c.Telefono, v.Caracteristica, v.Tramo,
           COALESCE(p.Puntos, pd.Puntos, 0) AS Puntos,
           ISNULL(pd.Puntos, 0) AS PuntosRef,   -- puntos del tramo más común (fila '*')
           CASE WHEN p.Puntos IS NULL THEN 1 ELSE 0 END AS SinPeso
    INTO #pts
    FROM score.Caracteristicas AS c
    CROSS APPLY (VALUES
        ('T_ULT_CEF', c.T_ULT_CEF), ('T_ULT_TERCERO', c.T_ULT_TERCERO), ('T_TASA_CEF_90', c.T_TASA_CEF_90),
        ('T_INTENTOS_30', c.T_INTENTOS_30), ('T_ULT_INTENTO', c.T_ULT_INTENTO), ('T_MAQUINA_90', c.T_MAQUINA_90),
        ('F_EQUIVOCADO_DNI', c.F_EQUIVOCADO_DNI), ('F_NO_EXISTE', c.F_NO_EXISTE),
        ('S_ORIGEN', c.S_ORIGEN), ('S_FUENTE', c.S_FUENTE), ('S_ANTIG_DATO', c.S_ANTIG_DATO),
        ('S_OSIPTEL', c.S_OSIPTEL), ('S_WHATSAPP', c.S_WHATSAPP), ('S_TIMBRA', c.S_TIMBRA),
        ('S_TIPO_LINEA', c.S_TIPO_LINEA), ('S_RELACION', c.S_RELACION), ('S_COMPARTIDO', c.S_COMPARTIDO),
        ('S_COLOR', c.S_COLOR)
    ) AS v (Caracteristica, Tramo)
    INNER JOIN #cv AS cv ON cv.Caracteristica = v.Caracteristica
    LEFT JOIN score.Peso AS p
           ON p.Version = @Version AND p.Caracteristica = v.Caracteristica AND p.Tramo = v.Tramo
    LEFT JOIN score.Peso AS pd
           ON pd.Version = @Version AND pd.Caracteristica = v.Caracteristica AND pd.Tramo = '*'
    WHERE c.FechaCorte = @FechaCorte AND c.Poblacion = 'UNIVERSO'
      AND (@IdCartera IS NULL OR c.IdCartera = @IdCartera);

    /* Razones = lo que hace a este teléfono distinto de uno típico: diferencia contra el tramo más común
       de cada característica. Un valor común (por ejemplo, relación "no informa") no es razón.
       Solo se muestran diferencias a favor (Razon1..3) y la mayor en contra (Razon_Resta). */
    ;WITH R AS (
        SELECT *, Puntos - PuntosRef AS Delta,
               ROW_NUMBER() OVER (PARTITION BY IdCartera, DNI, Telefono ORDER BY Puntos - PuntosRef DESC, Caracteristica) AS rn_mas,
               ROW_NUMBER() OVER (PARTITION BY IdCartera, DNI, Telefono ORDER BY Puntos - PuntosRef ASC, Caracteristica) AS rn_menos
        FROM #pts
    )
    SELECT IdCartera, DNI, Telefono,
           SUM(Puntos) AS Puntos,
           SUM(SinPeso) AS SinPeso,
           MAX(CASE WHEN rn_mas = 1 AND Delta > 0 THEN Caracteristica + ':' + Tramo END) AS Razon1,
           MAX(CASE WHEN rn_mas = 2 AND Delta > 0 THEN Caracteristica + ':' + Tramo END) AS Razon2,
           MAX(CASE WHEN rn_mas = 3 AND Delta > 0 THEN Caracteristica + ':' + Tramo END) AS Razon3,
           MAX(CASE WHEN rn_menos = 1 AND Delta < 0 THEN Caracteristica + ':' + Tramo END) AS Razon_Resta
    INTO #s
    FROM R
    GROUP BY IdCartera, DNI, Telefono;

    SELECT s.IdCartera, s.DNI, s.Telefono,
           CAST(CASE WHEN @Max > 0 THEN ROUND(100.0 * s.Puntos / @Max, 0) ELSE 0 END AS TINYINT) AS Score,
           s.Razon1, s.Razon2, s.Razon3, s.Razon_Resta, CAST(s.SinPeso AS TINYINT) AS TramosSinPeso,
           CAST(CASE WHEN c.F_EQUIVOCADO_DNI = 'SI' THEN 1 ELSE 0 END AS BIT) AS Descartado,
           CASE WHEN c.F_EQUIVOCADO_DNI = 'SI' THEN 'EQUIVOCADO_2_O_MAS' END AS MotivoDescarte
    INTO #f
    FROM #s AS s
    INNER JOIN score.Caracteristicas AS c
            ON c.FechaCorte = @FechaCorte AND c.Poblacion = 'UNIVERSO'
           AND c.IdCartera = s.IdCartera AND c.DNI = s.DNI AND c.Telefono = s.Telefono;

    SELECT f.*,
           CASE WHEN f.Score >= @A THEN 'A' WHEN f.Score >= @B THEN 'B' WHEN f.Score >= @C THEN 'C'
                WHEN f.Score >= @D THEN 'D' ELSE 'E' END AS Tramo,
           ROW_NUMBER() OVER (PARTITION BY f.IdCartera, f.DNI
                              ORDER BY f.Descartado ASC, f.Score DESC, f.Telefono ASC) AS OrdenCliente
    INTO #fin
    FROM #f AS f;

    IF @Simular = 1
    BEGIN
        SELECT 'SIMULACION' AS Modo, @FechaCorte AS FechaCorte, @Version AS Version, COUNT(*) AS telefonos,
               SUM(CAST(Descartado AS INT)) AS descartados, SUM(CASE WHEN TramosSinPeso > 0 THEN 1 ELSE 0 END) AS con_tramos_sin_peso
        FROM #fin;
        SELECT IdCartera, Tramo, COUNT(*) AS telefonos, AVG(CAST(Score AS FLOAT)) AS score_prom
        FROM #fin GROUP BY IdCartera, Tramo ORDER BY IdCartera, Tramo;
        RETURN;
    END;

    BEGIN TRAN;
        DELETE FROM score.TelefonoScore
        WHERE FechaCorte = @FechaCorte AND (@IdCartera IS NULL OR IdCartera = @IdCartera);
        INSERT INTO score.TelefonoScore (FechaCorte, IdCartera, DNI, Telefono, Version, Score, Tramo, OrdenCliente,
                                         Descartado, MotivoDescarte, Razon1, Razon2, Razon3, Razon_Resta, TramosSinPeso)
        SELECT @FechaCorte, IdCartera, DNI, Telefono, @Version, Score, Tramo, OrdenCliente,
               Descartado, MotivoDescarte, Razon1, Razon2, Razon3, Razon_Resta, TramosSinPeso
        FROM #fin;
        DELETE FROM score.TelefonoScore WHERE FechaCorte < DATEADD(DAY, -@DiasHistoria, @FechaCorte);
    COMMIT;

    SELECT 'GUARDADO' AS Modo, @FechaCorte AS FechaCorte, @Version AS Version, @IdCartera AS IdCartera, COUNT(*) AS telefonos
    FROM #fin;
END;
GO

-- 2.5 Historial de ayer completo (o los días que falten, hasta @MaxDias).
--     Un día está completo si se cargó después de terminado (FechaCarga >= día siguiente 00:00);
--     así, un día cargado a medias (como el 14/11) se vuelve a cargar al día siguiente.
CREATE OR ALTER PROCEDURE score.sp_AsegurarHistorial
    @MaxDias INT = 7
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    DECLARE @Ayer DATE = DATEADD(DAY, -1, CAST(GETDATE() AS DATE));

    IF EXISTS (SELECT 1 FROM score.TelefonoDiaControl
               WHERE Fecha = @Ayer AND FechaCarga >= CAST(DATEADD(DAY, 1, @Ayer) AS DATETIME2(0)))
        RETURN 0;

    -- Un solo proceso carga a la vez; los demás esperan y luego encuentran el día ya cargado
    DECLARE @Lock INT;
    EXEC @Lock = sp_getapplock @Resource = N'SCORE_CARGA_HISTORIAL', @LockMode = 'Exclusive',
                               @LockOwner = 'Session', @LockTimeout = 900000;
    IF @Lock < 0 THROW 50411, 'No se pudo obtener el turno para cargar el historial (15 minutos de espera).', 1;

    BEGIN TRY
        DECLARE @Ultimo DATE = (SELECT MAX(Fecha) FROM score.TelefonoDiaControl
                                WHERE FechaCarga >= CAST(DATEADD(DAY, 1, Fecha) AS DATETIME2(0)));
        DECLARE @d DATE = CASE WHEN @Ultimo IS NULL THEN @Ayer ELSE DATEADD(DAY, 1, @Ultimo) END;

        IF DATEDIFF(DAY, @d, @Ayer) + 1 > @MaxDias
        BEGIN
            DECLARE @Msg NVARCHAR(400) = CONCAT(N'Faltan ', DATEDIFF(DAY, @d, @Ayer) + 1,
                N' días de historial (desde ', CONVERT(CHAR(10), @d, 103),
                N'). Cargarlos con score.sp_CargarTelefonoDiaRango antes de actualizar.');
            THROW 50412, @Msg, 1;
        END;

        WHILE @d <= @Ayer
        BEGIN
            EXEC score.sp_CargarTelefonoDia @Fecha = @d, @Simular = 0;
            SET @d = DATEADD(DAY, 1, @d);
        END;

        EXEC sp_releaseapplock @Resource = N'SCORE_CARGA_HISTORIAL', @LockOwner = 'Session';
    END TRY
    BEGIN CATCH
        IF XACT_STATE() <> 0 ROLLBACK;
        IF APPLOCK_MODE('public', N'SCORE_CARGA_HISTORIAL', 'Session') <> 'NoLock'
            EXEC sp_releaseapplock @Resource = N'SCORE_CARGA_HISTORIAL', @LockOwner = 'Session';
        THROW;
    END CATCH;
    RETURN 1;
END;
GO

-- 2.6 Actualizar una cartera (botón del CRM). Devuelve como ÚLTIMO resultado la fila de la bitácora
--     (los pasos internos también devuelven sus resúmenes: el backend debe leer el último resultado).
CREATE OR ALTER PROCEDURE score.sp_ActualizarCartera
    @IdCartera INT,
    @Usuario   NVARCHAR(128) = NULL,     -- DNI del usuario del CRM, o 'JOB'
    @Origen    VARCHAR(12)   = 'MANUAL', -- MANUAL · PROGRAMADA
    @Alinear   BIT           = 1,        -- alinear con producción antes de rehacer el universo
    @Simular   BIT           = 1,
    @AvisoPrevio NVARCHAR(1000) = NULL   -- aviso de un paso hecho antes por el job (p. ej. alineación fallida)
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    DECLARE @Hoy DATE = CAST(GETDATE() AS DATE),
            @Recurso NVARCHAR(100) = N'SCORE_CARTERA_' + CONVERT(NVARCHAR(10), @IdCartera),
            @Id INT, @Lock INT, @t DATETIME2(3), @Paso VARCHAR(20) = 'INICIO',
            @Aviso NVARCHAR(1000) = NULLIF(LTRIM(RTRIM(@AvisoPrevio)), N''), @Version INT, @Carteras VARCHAR(10) = CONVERT(VARCHAR(10), @IdCartera);

    SET @Usuario = ISNULL(NULLIF(LTRIM(RTRIM(@Usuario)), N''), ORIGINAL_LOGIN());

    IF @Origen NOT IN ('MANUAL', 'PROGRAMADA')
        THROW 50421, 'Origen debe ser MANUAL o PROGRAMADA.', 1;
    IF NOT EXISTS (SELECT 1 FROM ControlCobranza.bl.EntidadCartera WHERE IdCartera = @IdCartera)
        THROW 50422, 'La cartera no está en ControlCobranza.bl.EntidadCartera.', 1;
    SELECT @Version = Version FROM score.PesoVersion WHERE Estado = 'PUBLICADA';
    IF @Simular = 0 AND @Version IS NULL
        THROW 50423, 'No hay una versión de pesos publicada.', 1;

    -- Candado de la cartera: sin espera. Si está ocupada, se informa y no se lanza otra corrida.
    EXEC @Lock = sp_getapplock @Resource = @Recurso, @LockMode = 'Exclusive', @LockOwner = 'Session', @LockTimeout = 0;
    IF @Lock < 0
    BEGIN
        SELECT TOP 1 'OCUPADA' AS Resultado, a.IdActualizacion, a.IdCartera, a.Usuario, a.Inicio, a.Paso
        FROM score.ActualizacionCartera AS a
        WHERE a.IdCartera = @IdCartera AND a.Estado = 'EN_CURSO'
        ORDER BY a.Inicio DESC;
        RETURN 1;
    END;

    BEGIN TRY
        -- Corridas que quedaron abiertas (proceso cortado): ya no tienen el candado
        UPDATE score.ActualizacionCartera SET Estado = 'INTERRUMPIDA', Fin = SYSDATETIME()
        WHERE IdCartera = @IdCartera AND Estado = 'EN_CURSO';

        INSERT INTO score.ActualizacionCartera (IdCartera, Origen, Modo, Usuario, Inicio, Estado, Paso, Version)
        VALUES (@IdCartera, @Origen, CASE WHEN @Simular = 1 THEN 'SIMULACION' ELSE 'REAL' END,
                @Usuario, SYSDATETIME(), 'EN_CURSO', @Paso, @Version);
        SET @Id = SCOPE_IDENTITY();

        -- 1. Historial de ayer
        IF @Simular = 0
        BEGIN
            SET @Paso = 'HISTORIAL'; SET @t = SYSDATETIME();
            UPDATE score.ActualizacionCartera SET Paso = @Paso WHERE IdActualizacion = @Id;
            EXEC score.sp_AsegurarHistorial;
            UPDATE score.ActualizacionCartera SET SegHistorial = DATEDIFF(SECOND, @t, SYSDATETIME()) WHERE IdActualizacion = @Id;
        END;
        UPDATE score.ActualizacionCartera
        SET HistorialHasta = (SELECT MAX(Fecha) FROM score.TelefonoDiaControl WHERE Fecha < @Hoy)
        WHERE IdActualizacion = @Id;

        -- 2. Alineación con producción. Si producción no responde, se avisa y se sigue con la copia local.
        IF @Alinear = 1
        BEGIN
            SET @Paso = 'ALINEACION'; SET @t = SYSDATETIME();
            UPDATE score.ActualizacionCartera SET Paso = @Paso WHERE IdActualizacion = @Id;
            BEGIN TRY
                EXEC score.sp_AlinearAtributosTelefono @Carteras = @Carteras, @Simular = @Simular;
            END TRY
            BEGIN CATCH
                IF XACT_STATE() <> 0 ROLLBACK;
                SET @Aviso = LEFT(N'No se pudo alinear con producción; se usó la copia local. ' + ERROR_MESSAGE(), 1000);
            END CATCH;
            UPDATE score.ActualizacionCartera SET SegAlineacion = DATEDIFF(SECOND, @t, SYSDATETIME()) WHERE IdActualizacion = @Id;
        END;

        -- 3. Universo de la cartera
        SET @Paso = 'UNIVERSO'; SET @t = SYSDATETIME();
        UPDATE score.ActualizacionCartera SET Paso = @Paso WHERE IdActualizacion = @Id;
        EXEC score.sp_ArmarUniversoCartera @IdCartera = @IdCartera, @Simular = @Simular;
        UPDATE score.ActualizacionCartera SET SegUniverso = DATEDIFF(SECOND, @t, SYSDATETIME()) WHERE IdActualizacion = @Id;

        IF @Simular = 1
        BEGIN
            -- En simulación se llega hasta el universo: lo que sigue necesita el universo nuevo guardado
            UPDATE score.ActualizacionCartera
            SET Estado = 'SIMULADA', Fin = SYSDATETIME(), Paso = 'FIN',
                Mensaje = CONCAT(@Aviso, CASE WHEN @Aviso IS NULL THEN N'' ELSE N' ' END,
                                 N'Simulación hasta el universo; características y score se calculan solo en modo real.')
            WHERE IdActualizacion = @Id;
        END
        ELSE
        BEGIN
            -- 4. Historial de atributos (semáforo, OSIPTEL, WhatsApp, timbrado)
            SET @Paso = 'ATRIBUTOS';
            UPDATE score.ActualizacionCartera SET Paso = @Paso WHERE IdActualizacion = @Id;
            EXEC score.sp_RegistrarAtributosTelefono @IdCartera = @IdCartera;

            -- 5. Características (historial hasta ayer)
            SET @Paso = 'CARACTERISTICAS'; SET @t = SYSDATETIME();
            UPDATE score.ActualizacionCartera SET Paso = @Paso WHERE IdActualizacion = @Id;
            EXEC score.sp_ArmarCaracteristicas @FechaCorte = @Hoy, @Poblacion = 'UNIVERSO', @Simular = 0, @IdCartera = @IdCartera;
            UPDATE score.ActualizacionCartera SET SegCaracteristicas = DATEDIFF(SECOND, @t, SYSDATETIME()) WHERE IdActualizacion = @Id;

            -- 6. Score
            SET @Paso = 'SCORE'; SET @t = SYSDATETIME();
            UPDATE score.ActualizacionCartera SET Paso = @Paso WHERE IdActualizacion = @Id;
            EXEC score.sp_CalcularScore @FechaCorte = @Hoy, @Simular = 0, @IdCartera = @IdCartera;
            UPDATE score.ActualizacionCartera SET SegScore = DATEDIFF(SECOND, @t, SYSDATETIME()) WHERE IdActualizacion = @Id;

            -- 7. Tabla de trabajo del generador (datos del cliente del corte de Analytics). Si falla, el score
            --    ya quedó actualizado: se avisa y la pantalla sigue con los datos del cliente anteriores.
            SET @Paso = 'BASE'; SET @t = SYSDATETIME();
            UPDATE score.ActualizacionCartera SET Paso = @Paso WHERE IdActualizacion = @Id;
            BEGIN TRY
                EXEC score.sp_ArmarBaseTrabajoCliente @IdCartera = @IdCartera, @Simular = 0;
            END TRY
            BEGIN CATCH
                IF XACT_STATE() <> 0 ROLLBACK;
                SET @Aviso = LEFT(CONCAT(@Aviso, CASE WHEN @Aviso IS NULL THEN N'' ELSE N' ' END,
                                         N'No se actualizó la tabla de trabajo: ', ERROR_MESSAGE()), 1000);
            END CATCH;

            UPDATE score.ActualizacionCartera
            SET SegBase = DATEDIFF(SECOND, @t, SYSDATETIME()),
                Estado = 'OK', Fin = SYSDATETIME(), Paso = 'FIN', Mensaje = @Aviso,
                Telefonos = (SELECT COUNT(*) FROM score.TelefonoScore WHERE FechaCorte = @Hoy AND IdCartera = @IdCartera),
                Excluidos = (SELECT COUNT(*) FROM score.TelefonoUniverso WHERE IdCartera = @IdCartera AND ExcluidoListaNegra = 1)
            WHERE IdActualizacion = @Id;
        END;

        EXEC sp_releaseapplock @Resource = @Recurso, @LockOwner = 'Session';
    END TRY
    BEGIN CATCH
        IF XACT_STATE() <> 0 ROLLBACK;
        DECLARE @Err NVARCHAR(2000) = LEFT(CONCAT(N'Paso ', @Paso, N': ', ERROR_MESSAGE()), 2000);
        IF @Id IS NOT NULL
            UPDATE score.ActualizacionCartera SET Estado = 'ERROR', Fin = SYSDATETIME(), Mensaje = @Err
            WHERE IdActualizacion = @Id;
        IF APPLOCK_MODE('public', @Recurso, 'Session') <> 'NoLock'
            EXEC sp_releaseapplock @Resource = @Recurso, @LockOwner = 'Session';
        THROW;
    END CATCH;

    SELECT 'TERMINADA' AS Resultado, a.*
    FROM score.ActualizacionCartera AS a WHERE a.IdActualizacion = @Id;
    RETURN 0;
END;
GO

-- 2.7 Actualizar todas las carteras con clientes activos (para el job programado)
CREATE OR ALTER PROCEDURE score.sp_ActualizarTodas
    @Alinear BIT = 1
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @Inicio DATETIME2(0) = SYSDATETIME(), @Hoy DATE = CAST(GETDATE() AS DATE), @c INT,
            @AvisoAlineacion NVARCHAR(1000) = NULL;

    -- Carteras con clientes activos hoy
    DECLARE @Activas TABLE (IdCartera INT PRIMARY KEY);
    INSERT INTO @Activas (IdCartera)
    SELECT ec.IdCartera
    FROM (SELECT DISTINCT IdCartera FROM ControlCobranza.bl.EntidadCartera) AS ec
    WHERE EXISTS (SELECT 1 FROM siscob.dbo.Cliente AS cl WITH (NOLOCK)
                  WHERE cl.IdCartera = ec.IdCartera AND cl.Estado IN ('A', 'N'));

    IF NOT EXISTS (SELECT 1 FROM @Activas)
        THROW 50431, 'Ninguna cartera tiene clientes activos en la copia de SISCOB: no se actualiza nada (revisar la réplica).', 1;

    -- Historial de ayer, una sola vez
    EXEC score.sp_AsegurarHistorial;

    -- Alineación con producción, una sola vez para todas
    IF @Alinear = 1
    BEGIN
        BEGIN TRY
            EXEC score.sp_AlinearAtributosTelefono @Carteras = NULL, @Simular = 0;
        END TRY
        BEGIN CATCH
            IF XACT_STATE() <> 0 ROLLBACK;
            -- Queda en la bitácora de cada cartera, no solo en la salida del job
            SET @AvisoAlineacion = LEFT(N'No se pudo alinear con producción; se usó la copia local. ' + ERROR_MESSAGE(), 1000);
            PRINT @AvisoAlineacion;
        END CATCH;
    END;

    -- Carteras que ya no tienen clientes activos: salen del universo y del score de hoy
    DELETE FROM score.TelefonoUniverso WHERE IdCartera NOT IN (SELECT IdCartera FROM @Activas);
    DELETE FROM score.TelefonoScore WHERE FechaCorte = @Hoy AND IdCartera NOT IN (SELECT IdCartera FROM @Activas);

    -- Cartera por cartera; si una falla, queda en la bitácora y se sigue con la siguiente
    DECLARE cur CURSOR LOCAL FAST_FORWARD FOR SELECT IdCartera FROM @Activas ORDER BY IdCartera;
    OPEN cur;
    FETCH NEXT FROM cur INTO @c;
    WHILE @@FETCH_STATUS = 0
    BEGIN
        BEGIN TRY
            EXEC score.sp_ActualizarCartera @IdCartera = @c, @Usuario = N'JOB', @Origen = 'PROGRAMADA',
                                            @Alinear = 0, @Simular = 0, @AvisoPrevio = @AvisoAlineacion;
        END TRY
        BEGIN CATCH
            IF XACT_STATE() <> 0 ROLLBACK;
            PRINT CONCAT(N'Cartera ', @c, N': ', ERROR_MESSAGE());
        END CATCH;
        FETCH NEXT FROM cur INTO @c;
    END;
    CLOSE cur; DEALLOCATE cur;

    SELECT a.IdCartera, a.Estado, a.Inicio, a.Fin, DATEDIFF(SECOND, a.Inicio, a.Fin) AS Segundos,
           a.Telefonos, a.Excluidos, a.HistorialHasta, a.Mensaje
    FROM score.ActualizacionCartera AS a
    WHERE a.Origen = 'PROGRAMADA' AND a.Inicio >= @Inicio
    ORDER BY a.IdCartera;
END;
GO

-- Segmentos vigentes, con el periodo para avisar si quedaron de un mes anterior
CREATE OR ALTER VIEW score.vw_SegmentoVigente
AS
SELECT k.IdEntidad, k.Fuente, k.Segmento, k.Periodo, k.IdCarga, s.Campo, s.CodigoBanco, s.DNI, s.Valor,
       CAST(CASE WHEN k.Periodo < CONVERT(CHAR(6), GETDATE(), 112) THEN 1 ELSE 0 END AS BIT) AS PeriodoAnterior
FROM score.SegmentoCarga AS k
INNER JOIN score.SegmentoCliente AS s ON s.IdCarga = k.IdCarga
WHERE k.Estado = 'VIGENTE';
GO

-- Estado de actualización por cartera (lo que muestra la pantalla: última actualización y si hay una en curso)
CREATE OR ALTER VIEW score.vw_ActualizacionCarteraEstado
AS
WITH Ult AS (
    SELECT a.*, ROW_NUMBER() OVER (PARTITION BY a.IdCartera ORDER BY a.Inicio DESC) AS rn
    FROM score.ActualizacionCartera AS a
    WHERE a.Estado = 'OK' AND a.Modo = 'REAL'
)
SELECT u.IdCartera, u.Fin AS UltimaActualizacion, u.Usuario, u.Origen, u.HistorialHasta, u.Version,
       u.Telefonos, u.Excluidos, u.Mensaje AS Aviso,
       DATEDIFF(SECOND, u.Inicio, u.Fin) AS Segundos,
       CAST(CASE WHEN EXISTS (SELECT 1 FROM score.ActualizacionCartera AS e
                              WHERE e.IdCartera = u.IdCartera AND e.Estado = 'EN_CURSO') THEN 1 ELSE 0 END AS BIT) AS EnCurso
FROM Ult AS u
WHERE u.rn = 1;
GO

/* =====================================================================================
   BLOQUE 3 · Simulación de una cartera (no escribe en el score; la alineación tampoco)
   ===================================================================================== */
EXEC CobAuto.score.sp_ActualizarCartera @IdCartera = 112, @Usuario = N'prueba', @Simular = 1;
GO

/* =====================================================================================
   BLOQUE 4 · Ejecución real (comentado)
   ===================================================================================== */
/*
-- Una cartera (lo mismo que hará el botón "Actualizar" del CRM)
EXEC CobAuto.score.sp_ActualizarCartera @IdCartera = 112, @Usuario = N'<tu DNI>', @Simular = 0;

-- Estado por cartera (lo que mostrará la pantalla)
SELECT * FROM CobAuto.score.vw_ActualizacionCarteraEstado ORDER BY IdCartera;

-- Todas las carteras activas (lo mismo que hará el job)
EXEC CobAuto.score.sp_ActualizarTodas;

-- Bitácora
SELECT TOP 50 * FROM CobAuto.score.ActualizacionCartera ORDER BY IdActualizacion DESC;
*/
GO

/* =====================================================================================
   BLOQUE 5 · Job programado (comentado). Alternativa: agregar el paso al Jb Maestro existente.
   Corre todos los días a las 05:20, antes de que empiece la gestión.
   ===================================================================================== */
/*
USE msdb;
EXEC dbo.sp_add_job        @job_name = N'Score telefónico - actualizar carteras';
EXEC dbo.sp_add_jobstep    @job_name = N'Score telefónico - actualizar carteras', @step_name = N'Actualizar todas',
                           @subsystem = N'TSQL', @database_name = N'CobAuto',
                           @command = N'EXEC score.sp_ActualizarTodas;';
EXEC dbo.sp_add_schedule   @schedule_name = N'Score telefónico 05:20', @freq_type = 4, @freq_interval = 1,
                           @active_start_time = 052000;
EXEC dbo.sp_attach_schedule @job_name = N'Score telefónico - actualizar carteras', @schedule_name = N'Score telefónico 05:20';
EXEC dbo.sp_add_jobserver  @job_name = N'Score telefónico - actualizar carteras';
*/
GO
