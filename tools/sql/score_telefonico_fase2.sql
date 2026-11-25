/* =====================================================================================
   SCORE TELEFÓNICO · FASE 2 — CARACTERÍSTICAS, PESOS Y SCORE
   Fecha: 14/11/2026 · Diseño: claude/diseno_score_telefonico.md (proyecto crm_cobranzas)
   Requiere la fase 1 instalada y el historial cargado (score.TelefonoDia desde el 14/05/2026).
   Nota: sp_RegistrarAtributosTelefono, sp_ArmarCaracteristicas y sp_CalcularScore son las mismas versiones
   que en la fase 3 (con @IdCartera). Volver a ejecutar este script no rompe la actualización por cartera.

   Qué crea (todo nuevo; no modifica objetos de la fase 1):
     score.TelefonoAtributoHist           historial de cambios del semáforo, OSIPTEL, WhatsApp y timbrado
     score.sp_RegistrarAtributosTelefono  registra los cambios del día (una fila solo cuando algo cambia)
     score.Caracteristicas                características por teléfono a una fecha de corte, en tramos
     score.sp_ArmarCaracteristicas        las calcula para una fecha: MARCADOS (entrenamiento) o UNIVERSO (hoy)
     score.sp_ArmarEntrenamiento          las calcula para varios lunes (base de la calibración)
     score.PesoVersion / score.Peso       pesos versionados (los escribe tools/score_telefonico_calibrar.py)
     score.sp_PublicarPeso                publica una versión (archiva la anterior)
     score.TelefonoScore                  score diario por teléfono, con el desglose de puntos
     score.sp_CalcularScore               calcula el score de hoy con la versión publicada

   Reglas (acordadas con Hardy el 14/11/2026):
     - Corte D: las características usan solo lo ocurrido ANTES de D (de D-90 a D-1).
       El resultado que se predice es lo que pasa de D a D+6. Así, al calibrar, nada del futuro
       se cuela en las características.
     - Éxito = contacto con el titular o con un tercero con acuerdo (= CEF del banco) en D…D+6,
       medido solo sobre los teléfonos que se marcaron en esa semana.
     - Ventanas de 30 y 90 días. La de 180 entra cuando el historial lo permita (empieza el 14/05).
     - El semáforo (color de prioridad) se guarda pero NO entra a la calibración todavía: solo existe
       el color de hoy y depende de las llamadas, así que usarlo en fechas pasadas metería el futuro
       en el modelo. Entra cuando score.TelefonoAtributoHist tenga algunas semanas.
     - OSIPTEL, WhatsApp y timbrado vienen de validaciones externas, no del resultado de las llamadas:
       se usan con su valor de hoy.
     - Pesos generales para todas las carteras; la calibración controla el nivel base de cada cartera.
     Ajustes del diagnóstico 5 (14/11/2026):
     - El entrenamiento excluye los teléfonos dados de alta en SISCOB desde la fecha de corte.
     - Descartado = 2 o más equivocados para ese DNI después del último CEF. "No existe" ya no descarta.
     - Un tramo que la versión no conoce toma los puntos del tramo de referencia (fila Tramo = '*').

   Cómo ejecutarlo:
     Bloque 1 a 3: crean objetos.
     Bloque 4: carga inicial del historial de atributos y armado del entrenamiento (escribe solo en
               tablas nuevas del esquema score). Luego: python tools/score_telefonico_calibrar.py
     Bloque 5 (comentado): publicar la versión y calcular el score de hoy.
   ===================================================================================== */

USE CobAuto;
GO
SET NOCOUNT ON;
GO

/* =====================================================================================
   BLOQUE 1 · Historial de atributos del teléfono
   ===================================================================================== */
IF OBJECT_ID('score.TelefonoAtributoHist', 'U') IS NULL
CREATE TABLE score.TelefonoAtributoHist (
    IdCartera       INT          NOT NULL,
    DNI             VARCHAR(20)  NOT NULL,
    Telefono        CHAR(9)      NOT NULL,
    Desde           DATE         NOT NULL,
    Hasta           DATE         NULL,          -- NULL = vigente
    PrioridadColor  VARCHAR(2)   NULL,
    Osiptel         VARCHAR(2)   NULL,
    Whatsapp        VARCHAR(2)   NULL,
    Timbra          TINYINT      NULL,
    CONSTRAINT PK_score_TelefonoAtributoHist PRIMARY KEY CLUSTERED (IdCartera, DNI, Telefono, Desde)
);
GO

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

/* =====================================================================================
   BLOQUE 2 · Características por teléfono a una fecha de corte
   ===================================================================================== */
IF OBJECT_ID('score.Caracteristicas', 'U') IS NULL
CREATE TABLE score.Caracteristicas (
    FechaCorte           DATE          NOT NULL,
    Poblacion            VARCHAR(10)   NOT NULL,   -- MARCADOS (entrenamiento) · UNIVERSO (score del día)
    IdCartera            INT           NOT NULL,
    DNI                  VARCHAR(20)   NOT NULL,
    Telefono             CHAR(9)       NOT NULL,
    -- Historial de marcación (D-90 … D-1)
    T_ULT_CEF            VARCHAR(12)   NOT NULL,   -- días desde el último CEF (titular o tercero con acuerdo)
    T_ULT_TERCERO        VARCHAR(12)   NOT NULL,   -- días desde el último contacto con un tercero
    T_TASA_CEF_90        VARCHAR(12)   NOT NULL,   -- CEF ÷ intentos en 90 días
    T_INTENTOS_30        VARCHAR(12)   NOT NULL,   -- intentos en 30 días
    T_ULT_INTENTO        VARCHAR(12)   NOT NULL,   -- días desde el último intento
    T_MAQUINA_90         VARCHAR(12)   NOT NULL,   -- qué pasa cuando no conecta (centralita y resultados humanos)
    F_EQUIVOCADO_DNI     VARCHAR(2)    NOT NULL,   -- 2 o más equivocados para este DNI después del último CEF
    F_NO_EXISTE          VARCHAR(2)    NOT NULL,   -- no existe (cualquier DNI), sin CEF posterior. Informativo:
                                                   -- no descarta ni entra al modelo (diagnóstico 5)
    -- Atributos del número (valor de hoy)
    S_ORIGEN             VARCHAR(12)   NOT NULL,   -- EMPRESA · OPERADORA · BUSQUEDA · CLIENTE · OTRO · SIN_DATO
    S_FUENTE             VARCHAR(16)   NOT NULL,   -- BASE_INTERNA · SEARCH · ENRIQUECIMIENTO · OTRA · SIN_DATO
    S_ANTIG_DATO         VARCHAR(12)   NOT NULL,   -- antigüedad del dato (de Origen "M 202306")
    S_OSIPTEL            VARCHAR(12)   NOT NULL,
    S_WHATSAPP           VARCHAR(12)   NOT NULL,
    S_TIMBRA             VARCHAR(12)   NOT NULL,
    S_TIPO_LINEA         VARCHAR(12)   NOT NULL,   -- PREPAGO · POSTPAGO · CONTROL · NO_INFORMA
    S_RELACION           VARCHAR(12)   NOT NULL,   -- TITULAR · AVAL · CONYUGE · FAMILIAR · REFERENCIA · NO_INFORMA
    S_COMPARTIDO         VARCHAR(12)   NOT NULL,   -- DNI que comparten el número
    S_COLOR              VARCHAR(12)   NOT NULL,   -- semáforo (no entra a la calibración v1)
    -- Datos para mostrar en el CRM
    DiasUltCef           INT           NULL,
    UltimoIntento        DATE          NULL,
    FranjaContacto       VARCHAR(10)   NULL,       -- franja con más contactos en 90 días
    -- Solo entrenamiento (D … D+6)
    IntentosFut          INT           NULL,
    C_INTENTOS_FUT       VARCHAR(12)   NULL,
    EXITO                BIT           NULL,
    FechaCarga           DATETIME2(0)  NOT NULL CONSTRAINT DF_score_Caracteristicas_FechaCarga DEFAULT (SYSDATETIME()),
    CONSTRAINT PK_score_Caracteristicas PRIMARY KEY CLUSTERED (FechaCorte, Poblacion, IdCartera, DNI, Telefono)
);
GO

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

-- Entrenamiento: características de los teléfonos marcados, un corte por lunes
CREATE OR ALTER PROCEDURE score.sp_ArmarEntrenamiento
    @Desde DATE,
    @Hasta DATE
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @f DATE = @Desde;
    -- Primer lunes desde @Desde (independiente de SET DATEFIRST)
    WHILE DATEDIFF(DAY, '19000101', @f) % 7 <> 0 SET @f = DATEADD(DAY, 1, @f);   -- 01/01/1900 fue lunes
    WHILE @f <= @Hasta
    BEGIN
        EXEC score.sp_ArmarCaracteristicas @FechaCorte = @f, @Poblacion = 'MARCADOS', @Simular = 0;
        SET @f = DATEADD(DAY, 7, @f);
    END;
END;
GO

/* =====================================================================================
   BLOQUE 3 · Pesos versionados y score
   ===================================================================================== */
IF OBJECT_ID('score.PesoVersion', 'U') IS NULL
CREATE TABLE score.PesoVersion (
    Version          INT            NOT NULL CONSTRAINT PK_score_PesoVersion PRIMARY KEY,
    Estado           VARCHAR(12)    NOT NULL,   -- BORRADOR · PUBLICADA · ARCHIVADA
    Descripcion      NVARCHAR(500)  NULL,
    CorteDesde       DATE           NULL,       -- fechas de corte usadas para calibrar
    CorteHasta       DATE           NULL,
    PuntosMaximos    DECIMAL(9, 2)  NOT NULL,   -- suma de los máximos de cada característica (score 100)
    Tramo_A          DECIMAL(5, 1)  NOT NULL,   -- score mínimo de cada tramo (A el mejor)
    Tramo_B          DECIMAL(5, 1)  NOT NULL,
    Tramo_C          DECIMAL(5, 1)  NOT NULL,
    Tramo_D          DECIMAL(5, 1)  NOT NULL,
    Metricas         NVARCHAR(MAX)  NULL,       -- JSON con AUC, lift, etc.
    FechaCreacion    DATETIME2(0)   NOT NULL CONSTRAINT DF_score_PesoVersion_Fecha DEFAULT (SYSDATETIME()),
    UsuarioCreacion  NVARCHAR(128)  NOT NULL CONSTRAINT DF_score_PesoVersion_Usuario DEFAULT (ORIGINAL_LOGIN()),
    FechaPublicacion DATETIME2(0)   NULL,
    CONSTRAINT CK_score_PesoVersion_Estado CHECK (Estado IN ('BORRADOR', 'PUBLICADA', 'ARCHIVADA'))
);
GO

IF OBJECT_ID('score.Peso', 'U') IS NULL
CREATE TABLE score.Peso (
    Version        INT            NOT NULL CONSTRAINT FK_score_Peso_Version REFERENCES score.PesoVersion (Version),
    Caracteristica VARCHAR(30)    NOT NULL,
    Tramo          VARCHAR(16)    NOT NULL,
    Puntos         DECIMAL(9, 2)  NOT NULL,
    Coeficiente    FLOAT          NULL,
    N              INT            NULL,       -- teléfonos de entrenamiento en el tramo
    TasaExito      FLOAT          NULL,       -- tasa observada en el tramo (entrenamiento)
    CONSTRAINT PK_score_Peso PRIMARY KEY CLUSTERED (Version, Caracteristica, Tramo)
);
GO

CREATE OR ALTER PROCEDURE score.sp_PublicarPeso
    @Version INT
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;
    IF NOT EXISTS (SELECT 1 FROM score.PesoVersion WHERE Version = @Version AND Estado = 'BORRADOR')
        THROW 50321, 'La versión no existe o no está en BORRADOR.', 1;
    BEGIN TRAN;
        UPDATE score.PesoVersion SET Estado = 'ARCHIVADA' WHERE Estado = 'PUBLICADA';
        UPDATE score.PesoVersion SET Estado = 'PUBLICADA', FechaPublicacion = SYSDATETIME() WHERE Version = @Version;
    COMMIT;
    SELECT Version, Estado, FechaPublicacion FROM score.PesoVersion WHERE Version = @Version;
END;
GO

IF OBJECT_ID('score.TelefonoScore', 'U') IS NULL
CREATE TABLE score.TelefonoScore (
    FechaCorte       DATE          NOT NULL,
    IdCartera        INT           NOT NULL,
    DNI              VARCHAR(20)   NOT NULL,
    Telefono         CHAR(9)       NOT NULL,
    Version          INT           NOT NULL,
    Score            TINYINT       NOT NULL,   -- 0 a 100
    Tramo            CHAR(1)       NOT NULL,   -- A (mejor) … E
    OrdenCliente     SMALLINT      NOT NULL,   -- 1 = primer teléfono a marcar del cliente
    Descartado       BIT           NOT NULL,
    MotivoDescarte   VARCHAR(30)   NULL,
    Razon1           VARCHAR(50)   NULL,       -- característica:tramo que más suma
    Razon2           VARCHAR(50)   NULL,
    Razon3           VARCHAR(50)   NULL,
    Razon_Resta      VARCHAR(50)   NULL,       -- característica:tramo que menos suma
    TramosSinPeso    TINYINT       NOT NULL,   -- tramos que la versión no conoce (sumaron 0)
    FechaCarga       DATETIME2(0)  NOT NULL CONSTRAINT DF_score_TelefonoScore_FechaCarga DEFAULT (SYSDATETIME()),
    CONSTRAINT PK_score_TelefonoScore PRIMARY KEY CLUSTERED (FechaCorte, IdCartera, DNI, Telefono)
);
GO

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

/* =====================================================================================
   BLOQUE 4 · Carga inicial y entrenamiento
   ===================================================================================== */
-- 4.1 Historial de atributos: primera foto (todas las filas abren hoy)
EXEC CobAuto.score.sp_RegistrarAtributosTelefono;
GO

-- 4.2 Prueba de un corte, sin escribir
EXEC CobAuto.score.sp_ArmarCaracteristicas @FechaCorte = '2026-10-19', @Poblacion = 'MARCADOS', @Simular = 1;
GO

-- 4.3 Entrenamiento: lunes del 17/08 al 03/11 (12 cortes; cada uno necesita 90 días antes y 7 después)
EXEC CobAuto.score.sp_ArmarEntrenamiento @Desde = '2026-08-17', @Hasta = '2026-11-03';
GO

SELECT FechaCorte, COUNT(*) AS telefonos, SUM(CAST(EXITO AS INT)) AS exitos,
       CAST(100.0 * AVG(CAST(EXITO AS FLOAT)) AS DECIMAL(6, 2)) AS tasa_exito_pct
FROM CobAuto.score.Caracteristicas
WHERE Poblacion = 'MARCADOS'
GROUP BY FechaCorte
ORDER BY FechaCorte;
GO
-- Siguiente paso: python tools/score_telefonico_calibrar.py   (desde la carpeta del CRM)

/* =====================================================================================
   BLOQUE 5 · Después de revisar la calibración (comentado)
   ===================================================================================== */
/*
EXEC CobAuto.score.sp_PublicarPeso @Version = 1;

-- Score de hoy (el universo y el historial deben estar al día)
DECLARE @hoy DATE = CAST(GETDATE() AS DATE);
EXEC CobAuto.score.sp_ArmarCaracteristicas @FechaCorte = @hoy, @Poblacion = 'UNIVERSO', @Simular = 0;
EXEC CobAuto.score.sp_CalcularScore @FechaCorte = @hoy, @Simular = 1;
EXEC CobAuto.score.sp_CalcularScore @FechaCorte = @hoy, @Simular = 0;
*/
GO
