/* =====================================================================================
   SCORE TELEFÓNICO + LISTA NEGRA
   Base: CobAuto

   Qué hace:
     1. dbo.TBL_SCORE_TELEFONICO_CRM_EXCLUIDOS: registro de lo que la lista negra quitó del score
        (desde el último refresco), con el bloqueo que lo explica.
     2. dbo.SP_SCORE_TELEFONICO_APLICAR_LISTA_NEGRA: quita del score, en el momento, lo que esté
        bloqueado. Se llama después de confirmar una carga, para no esperar al siguiente refresco.
        Por defecto solo SIMULA (@Simular = 1).
     3. dbo.SP_REFRESCAR_SCORE_TELEFONICO_CRM (versión completa):
          - misma lógica de origen: SELECT * desde dbo.VW_SCORE_TELEFONICO_CRM
          - quita los teléfonos en lista negra vigente (por IDCARTERA → entidad)
          - crea los índices ANTES del intercambio
          - hace el intercambio de tablas dentro de una transacción corta: si algo falla,
            el score anterior queda intacto y nunca hay un momento sin tabla.

   Regla de cruce (ControlCobranza.bl.vw_ListaNegraVigentePorCartera):
     T = TELEFONO          -> misma cartera de la entidad + mismo teléfono
     D = CLIENTE           -> misma cartera de la entidad + mismo DNI
     A = TELEFONO_CLIENTE  -> misma cartera de la entidad + mismo DNI + mismo teléfono

   Requisito: el usuario SQL que ejecuta estos SP (el del CRM y, si existe, el del Job)
   necesita SELECT en ControlCobranza.bl (ver bloque 12 del script de la Fase 1).
   ===================================================================================== */

USE CobAuto;
GO
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

/* -------------------------------------------------------------------------------------
   0. PRE-VALIDACIÓN (solo lectura)
   ------------------------------------------------------------------------------------- */
SELECT COUNT(*) AS FilasScoreActual FROM dbo.TBL_SCORE_TELEFONICO_CRM WITH (NOLOCK);

-- Debe responder sin error de permisos (hoy devolverá 0 si no hay bloqueos cargados)
SELECT COUNT(*) AS BloqueosVigentesPorCartera FROM ControlCobranza.bl.vw_ListaNegraVigentePorCartera;

-- Carteras del score que NO están mapeadas a una entidad (sus teléfonos no se podrían bloquear)
SELECT s.IDCARTERA, MAX(s.CARTERA_SCORE) AS CarteraScore, COUNT(*) AS Filas
FROM dbo.TBL_SCORE_TELEFONICO_CRM s WITH (NOLOCK)
WHERE NOT EXISTS (SELECT 1 FROM ControlCobranza.bl.EntidadCartera ec WHERE ec.IdCartera = s.IDCARTERA)
GROUP BY s.IDCARTERA
ORDER BY s.IDCARTERA;
GO

/* -------------------------------------------------------------------------------------
   1. REGISTRO DE EXCLUIDOS
   Contiene lo que la lista negra quitó del score desde el último refresco.
   El historial permanente de cada bloqueo está en ControlCobranza.bl.ListaNegraEvento.
   ------------------------------------------------------------------------------------- */
IF OBJECT_ID('dbo.TBL_SCORE_TELEFONICO_CRM_EXCLUIDOS', 'U') IS NULL
CREATE TABLE dbo.TBL_SCORE_TELEFONICO_CRM_EXCLUIDOS (
    IdExcluido    BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT PK_TBL_SCORE_TEL_CRM_EXCLUIDOS PRIMARY KEY,
    FechaProceso  DATETIME2(0) NOT NULL CONSTRAINT DF_TBL_SCORE_TEL_CRM_EXCLUIDOS_Fecha DEFAULT (SYSDATETIME()),
    Proceso       VARCHAR(20)  NOT NULL,   -- REFRESCO / LISTA_NEGRA
    IDCARTERA     INT          NULL,
    CARTERA_SCORE VARCHAR(100) NULL,
    DNI           VARCHAR(50)  NULL,
    TELEFONO      VARCHAR(50)  NULL,
    IdListaNegra  INT          NOT NULL,
    TipoBloqueo   CHAR(1)      NOT NULL
);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_TBL_SCORE_TEL_CRM_EXCLUIDOS_Cartera'
               AND object_id = OBJECT_ID('dbo.TBL_SCORE_TELEFONICO_CRM_EXCLUIDOS'))
    CREATE INDEX IX_TBL_SCORE_TEL_CRM_EXCLUIDOS_Cartera
        ON dbo.TBL_SCORE_TELEFONICO_CRM_EXCLUIDOS (IDCARTERA, TELEFONO) INCLUDE (DNI, IdListaNegra, TipoBloqueo);
GO

/* -------------------------------------------------------------------------------------
   2. APLICAR LISTA NEGRA AL SCORE ACTUAL (efecto inmediato después de una carga)
   @Simular = 1 -> solo muestra qué se quitaría (no modifica nada)
   @Simular = 0 -> quita las filas y las registra en TBL_SCORE_TELEFONICO_CRM_EXCLUIDOS
   ------------------------------------------------------------------------------------- */
CREATE OR ALTER PROCEDURE dbo.SP_SCORE_TELEFONICO_APLICAR_LISTA_NEGRA
    @Simular BIT = 1
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    BEGIN TRY
        BEGIN TRAN;

        -- Misma llave que usa el refresco: evita que ambos procesos se crucen
        DECLARE @Lock INT;
        EXEC @Lock = sp_getapplock @Resource = N'SCORE_TELEFONICO_CRM', @LockMode = 'Exclusive',
                                   @LockOwner = 'Transaction', @LockTimeout = 120000;
        IF @Lock < 0
            THROW 50101, 'El score se está refrescando. La lista negra se aplicará en el siguiente intento o refresco.', 1;

        CREATE TABLE #bl (
            IdCartera    INT NOT NULL,
            TipoBloqueo  CHAR(1) NOT NULL,
            Telefono     VARCHAR(15) COLLATE DATABASE_DEFAULT NULL,
            DNI          VARCHAR(20) COLLATE DATABASE_DEFAULT NULL,
            IdListaNegra INT NOT NULL
        );

        INSERT INTO #bl (IdCartera, TipoBloqueo, Telefono, DNI, IdListaNegra)
        SELECT IdCartera, TipoBloqueo, Telefono, DNI, IdListaNegra
        FROM ControlCobranza.bl.vw_ListaNegraVigentePorCartera;

        CREATE INDEX IX_bl_Tel ON #bl (IdCartera, TipoBloqueo, Telefono);
        CREATE INDEX IX_bl_Dni ON #bl (IdCartera, TipoBloqueo, DNI);

        CREATE TABLE #excl (
            IDCARTERA     INT NULL,
            CARTERA_SCORE VARCHAR(100) COLLATE DATABASE_DEFAULT NULL,
            DNI           VARCHAR(50)  COLLATE DATABASE_DEFAULT NULL,
            TELEFONO      VARCHAR(50)  COLLATE DATABASE_DEFAULT NULL,
            IdListaNegra  INT NOT NULL,
            TipoBloqueo   CHAR(1) NOT NULL
        );

        INSERT INTO #excl (IDCARTERA, CARTERA_SCORE, DNI, TELEFONO, IdListaNegra, TipoBloqueo)
        SELECT s.IDCARTERA, s.CARTERA_SCORE, s.DNI, s.TELEFONO, b.IdListaNegra, b.TipoBloqueo
        FROM dbo.TBL_SCORE_TELEFONICO_CRM s
        INNER JOIN #bl b
            ON b.IdCartera = s.IDCARTERA AND b.TipoBloqueo = 'T'
           AND b.Telefono = LTRIM(RTRIM(s.TELEFONO))
        UNION ALL
        SELECT s.IDCARTERA, s.CARTERA_SCORE, s.DNI, s.TELEFONO, b.IdListaNegra, b.TipoBloqueo
        FROM dbo.TBL_SCORE_TELEFONICO_CRM s
        INNER JOIN #bl b
            ON b.IdCartera = s.IDCARTERA AND b.TipoBloqueo = 'D'
           AND b.DNI = LTRIM(RTRIM(s.DNI))
        UNION ALL
        SELECT s.IDCARTERA, s.CARTERA_SCORE, s.DNI, s.TELEFONO, b.IdListaNegra, b.TipoBloqueo
        FROM dbo.TBL_SCORE_TELEFONICO_CRM s
        INNER JOIN #bl b
            ON b.IdCartera = s.IDCARTERA AND b.TipoBloqueo = 'A'
           AND b.DNI = LTRIM(RTRIM(s.DNI))
           AND b.Telefono = LTRIM(RTRIM(s.TELEFONO));

        IF @Simular = 0
        BEGIN
            DELETE s
            FROM dbo.TBL_SCORE_TELEFONICO_CRM s
            WHERE EXISTS (SELECT 1 FROM #bl b
                          WHERE b.IdCartera = s.IDCARTERA AND b.TipoBloqueo = 'T'
                            AND b.Telefono = LTRIM(RTRIM(s.TELEFONO)));

            DELETE s
            FROM dbo.TBL_SCORE_TELEFONICO_CRM s
            WHERE EXISTS (SELECT 1 FROM #bl b
                          WHERE b.IdCartera = s.IDCARTERA AND b.TipoBloqueo = 'D'
                            AND b.DNI = LTRIM(RTRIM(s.DNI)));

            DELETE s
            FROM dbo.TBL_SCORE_TELEFONICO_CRM s
            WHERE EXISTS (SELECT 1 FROM #bl b
                          WHERE b.IdCartera = s.IDCARTERA AND b.TipoBloqueo = 'A'
                            AND b.DNI = LTRIM(RTRIM(s.DNI))
                            AND b.Telefono = LTRIM(RTRIM(s.TELEFONO)));

            INSERT INTO dbo.TBL_SCORE_TELEFONICO_CRM_EXCLUIDOS
                (Proceso, IDCARTERA, CARTERA_SCORE, DNI, TELEFONO, IdListaNegra, TipoBloqueo)
            SELECT 'LISTA_NEGRA', IDCARTERA, CARTERA_SCORE, DNI, TELEFONO, IdListaNegra, TipoBloqueo
            FROM #excl;
        END;

        COMMIT;

        -- Resumen (una fila del score puede coincidir con más de un bloqueo)
        SELECT
            CASE WHEN @Simular = 1 THEN 'SIMULACION' ELSE 'APLICADO' END AS Modo,
            IDCARTERA,
            TipoBloqueo,
            COUNT(*) AS Coincidencias,
            COUNT(DISTINCT TELEFONO) AS Telefonos,
            COUNT(DISTINCT DNI) AS Clientes
        FROM #excl
        GROUP BY IDCARTERA, TipoBloqueo
        ORDER BY IDCARTERA, TipoBloqueo;

        IF @Simular = 1
            SELECT TOP 500 * FROM #excl ORDER BY IDCARTERA, DNI, TELEFONO;
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0 ROLLBACK;
        THROW;
    END CATCH;
END;
GO

/* -------------------------------------------------------------------------------------
   3. REFRESCO DEL SCORE (versión completa)
   ------------------------------------------------------------------------------------- */
CREATE OR ALTER PROCEDURE dbo.SP_REFRESCAR_SCORE_TELEFONICO_CRM
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    BEGIN TRY
        /* 3.1 Construir la tabla nueva SIN tocar la vigente */
        IF OBJECT_ID('dbo.TBL_SCORE_TELEFONICO_CRM_TMP', 'U') IS NOT NULL
            DROP TABLE dbo.TBL_SCORE_TELEFONICO_CRM_TMP;

        SELECT *
        INTO dbo.TBL_SCORE_TELEFONICO_CRM_TMP
        FROM dbo.VW_SCORE_TELEFONICO_CRM;

        /* 3.2 Índices sobre la tabla nueva (los nombres de índice son únicos por tabla) */
        CREATE INDEX IX_SCORE_TEL_CRM_CARTERA_DNI
            ON dbo.TBL_SCORE_TELEFONICO_CRM_TMP (CARTERA_SCORE, DNI);

        CREATE INDEX IX_SCORE_TEL_CRM_CARTERA_TELEFONO
            ON dbo.TBL_SCORE_TELEFONICO_CRM_TMP (CARTERA_SCORE, TELEFONO);

        CREATE INDEX IX_SCORE_TEL_CRM_SCORE
            ON dbo.TBL_SCORE_TELEFONICO_CRM_TMP (CARTERA_SCORE, SCORE_TELEFONO DESC);

        CREATE INDEX IX_SCORE_TEL_CRM_PRIORIDAD
            ON dbo.TBL_SCORE_TELEFONICO_CRM_TMP (CARTERA_SCORE, PRIORIDAD_CONTACTO);

        CREATE INDEX IX_SCORE_TEL_CRM_FLAGS
            ON dbo.TBL_SCORE_TELEFONICO_CRM_TMP (CARTERA_SCORE, FLG_WHATSAPP_VALIDO, FLG_TIMBRA_FUERTE, FLG_OSIPTEL_VALIDO);

        /* 3.3 Lista negra + intercambio, en una transacción corta */
        BEGIN TRAN;

        DECLARE @Lock INT;
        EXEC @Lock = sp_getapplock @Resource = N'SCORE_TELEFONICO_CRM', @LockMode = 'Exclusive',
                                   @LockOwner = 'Transaction', @LockTimeout = 120000;
        IF @Lock < 0
            THROW 50102, 'No se pudo obtener el bloqueo del score telefónico. Intenta nuevamente.', 1;

        -- Bloqueos vigentes al momento del intercambio (incluye cargas confirmadas durante el armado)
        CREATE TABLE #bl (
            IdCartera    INT NOT NULL,
            TipoBloqueo  CHAR(1) NOT NULL,
            Telefono     VARCHAR(15) COLLATE DATABASE_DEFAULT NULL,
            DNI          VARCHAR(20) COLLATE DATABASE_DEFAULT NULL,
            IdListaNegra INT NOT NULL
        );

        INSERT INTO #bl (IdCartera, TipoBloqueo, Telefono, DNI, IdListaNegra)
        SELECT IdCartera, TipoBloqueo, Telefono, DNI, IdListaNegra
        FROM ControlCobranza.bl.vw_ListaNegraVigentePorCartera;

        CREATE INDEX IX_bl_Tel ON #bl (IdCartera, TipoBloqueo, Telefono);
        CREATE INDEX IX_bl_Dni ON #bl (IdCartera, TipoBloqueo, DNI);

        CREATE TABLE #excl (
            IDCARTERA     INT NULL,
            CARTERA_SCORE VARCHAR(100) COLLATE DATABASE_DEFAULT NULL,
            DNI           VARCHAR(50)  COLLATE DATABASE_DEFAULT NULL,
            TELEFONO      VARCHAR(50)  COLLATE DATABASE_DEFAULT NULL,
            IdListaNegra  INT NOT NULL,
            TipoBloqueo   CHAR(1) NOT NULL
        );

        INSERT INTO #excl (IDCARTERA, CARTERA_SCORE, DNI, TELEFONO, IdListaNegra, TipoBloqueo)
        SELECT s.IDCARTERA, s.CARTERA_SCORE, s.DNI, s.TELEFONO, b.IdListaNegra, b.TipoBloqueo
        FROM dbo.TBL_SCORE_TELEFONICO_CRM_TMP s
        INNER JOIN #bl b
            ON b.IdCartera = s.IDCARTERA AND b.TipoBloqueo = 'T'
           AND b.Telefono = LTRIM(RTRIM(s.TELEFONO))
        UNION ALL
        SELECT s.IDCARTERA, s.CARTERA_SCORE, s.DNI, s.TELEFONO, b.IdListaNegra, b.TipoBloqueo
        FROM dbo.TBL_SCORE_TELEFONICO_CRM_TMP s
        INNER JOIN #bl b
            ON b.IdCartera = s.IDCARTERA AND b.TipoBloqueo = 'D'
           AND b.DNI = LTRIM(RTRIM(s.DNI))
        UNION ALL
        SELECT s.IDCARTERA, s.CARTERA_SCORE, s.DNI, s.TELEFONO, b.IdListaNegra, b.TipoBloqueo
        FROM dbo.TBL_SCORE_TELEFONICO_CRM_TMP s
        INNER JOIN #bl b
            ON b.IdCartera = s.IDCARTERA AND b.TipoBloqueo = 'A'
           AND b.DNI = LTRIM(RTRIM(s.DNI))
           AND b.Telefono = LTRIM(RTRIM(s.TELEFONO));

        DELETE s
        FROM dbo.TBL_SCORE_TELEFONICO_CRM_TMP s
        WHERE EXISTS (SELECT 1 FROM #bl b
                      WHERE b.IdCartera = s.IDCARTERA AND b.TipoBloqueo = 'T'
                        AND b.Telefono = LTRIM(RTRIM(s.TELEFONO)));

        DELETE s
        FROM dbo.TBL_SCORE_TELEFONICO_CRM_TMP s
        WHERE EXISTS (SELECT 1 FROM #bl b
                      WHERE b.IdCartera = s.IDCARTERA AND b.TipoBloqueo = 'D'
                        AND b.DNI = LTRIM(RTRIM(s.DNI)));

        DELETE s
        FROM dbo.TBL_SCORE_TELEFONICO_CRM_TMP s
        WHERE EXISTS (SELECT 1 FROM #bl b
                      WHERE b.IdCartera = s.IDCARTERA AND b.TipoBloqueo = 'A'
                        AND b.DNI = LTRIM(RTRIM(s.DNI))
                        AND b.Telefono = LTRIM(RTRIM(s.TELEFONO)));

        -- Intercambio: si algo falla, el ROLLBACK deja la tabla vigente como estaba
        IF OBJECT_ID('dbo.TBL_SCORE_TELEFONICO_CRM', 'U') IS NOT NULL
            DROP TABLE dbo.TBL_SCORE_TELEFONICO_CRM;

        EXEC sp_rename 'dbo.TBL_SCORE_TELEFONICO_CRM_TMP', 'TBL_SCORE_TELEFONICO_CRM';

        -- Registro de lo excluido en este refresco (reemplaza lo anterior)
        DELETE FROM dbo.TBL_SCORE_TELEFONICO_CRM_EXCLUIDOS;

        INSERT INTO dbo.TBL_SCORE_TELEFONICO_CRM_EXCLUIDOS
            (Proceso, IDCARTERA, CARTERA_SCORE, DNI, TELEFONO, IdListaNegra, TipoBloqueo)
        SELECT 'REFRESCO', IDCARTERA, CARTERA_SCORE, DNI, TELEFONO, IdListaNegra, TipoBloqueo
        FROM #excl;

        COMMIT;
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0 ROLLBACK;
        THROW;
    END CATCH;
END;
GO

/* -------------------------------------------------------------------------------------
   4. PRUEBA SIN DEJAR DATOS
   Bloquea en una transacción un teléfono real del score, simula y deshace todo.
   Seleccionar desde BEGIN TRAN hasta ROLLBACK y ejecutar.
   ------------------------------------------------------------------------------------- */
/*
BEGIN TRAN;

    DECLARE @IdCartera INT, @Telefono VARCHAR(50), @Dni VARCHAR(50), @IdEntidad INT;

    SELECT TOP 1 @IdCartera = s.IDCARTERA, @Telefono = LTRIM(RTRIM(s.TELEFONO)), @Dni = LTRIM(RTRIM(s.DNI))
    FROM dbo.TBL_SCORE_TELEFONICO_CRM s WITH (NOLOCK)
    WHERE s.IDCARTERA = 126;            -- cartera de prueba (Compartamos)

    SELECT @IdEntidad = IdEntidad FROM ControlCobranza.bl.EntidadCartera WHERE IdCartera = @IdCartera;

    DECLARE @r TABLE (IdCarga INT, IdCargaPreviaMismoArchivo INT);
    INSERT INTO @r EXEC ControlCobranza.bl.sp_ListaNegra_CrearCarga
        @IdEntidad = @IdEntidad, @Modo = 'INDIVIDUAL', @Usuario = '00000000';
    DECLARE @IdCarga INT = (SELECT IdCarga FROM @r);

    INSERT INTO ControlCobranza.bl.ListaNegra_Stg (IdCarga, Fila, TipoBloqueoOrig, TelefonoOrig, DniOrig, MotivoOrig)
    VALUES (@IdCarga, 1, 'TELEFONO', @Telefono, @Dni, 'SOLICITUD_ENTIDAD');

    EXEC ControlCobranza.bl.sp_ListaNegra_ProcesarCarga @IdCarga = @IdCarga, @Confirmar = 1, @Usuario = '00000000';

    -- Esperado: el teléfono aparece en TODAS las carteras de la entidad donde exista
    EXEC dbo.SP_SCORE_TELEFONICO_APLICAR_LISTA_NEGRA @Simular = 1;

ROLLBACK;
*/
GO
