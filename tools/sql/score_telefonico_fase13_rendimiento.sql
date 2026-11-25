/* =====================================================================================
   Score telefónico · fase 13 · Rendimiento del score (datos de la vista)             (24/11/2026)
   Base: CobAuto (esquema score). Se puede volver a ejecutar completo.

   Pedido de Hardy (24/11): una vista para DEMOSTRAR con datos cómo rinde cada tramo y cada orden de
   teléfono (intentos, marcados, CEF…), con desglose por OSIPTEL, timbrado, WhatsApp, origen, fuente, color
   y franja horaria, en dos pestañas (toda la cartera / bases generadas) y periodo de 7, 14 o 30 días.
   No cambia ninguna regla del score: solo mide.

   Qué agrega
   1. score.TelefonoDia: intentos por franja (Intentos_Manana / _Medio / _Tarde / _Noche), con las mismas
      franjas que ya tenían los contactos: 06-11, 12-14, 15-17 y 18 en adelante (lo de antes de las 6 no cuenta
      en ninguna franja). Se cuentan los intentos humanos y de máquina (la centralita son las mismas llamadas
      de la máquina: no se suma dos veces).
   2. score.RendimientoDia: resumen por día, cartera, canal de la base (SIN BASE / PRED / IVR / SMS), tramo,
      orden del teléfono en el cliente y atributos. Unidad: teléfono-día (el tramo que el teléfono tenía ESE
      día contra lo que pasó ESE día). Lo arma score.sp_ArmarRendimientoDia; se conserva 60 días.
      - Tramo y orden: score.TelefonoScore del mismo día. Teléfonos marcados que no estaban en el score
        (números nuevos) quedan como tramo "SIN SCORE".
      - Atributos: score.Caracteristicas (UNIVERSO) del mismo día; Caracteristicas guarda 7 días, así que para
        días más antiguos se usan los del corte más cercano.
      - Mejor resultado del día (excluyentes, suman los marcados): CEF (titular o tercero con acuerdo),
        TERCERO, CONTESTA SIN ID, NO CONTESTA, BUZÓN, APAGADO, NO EXISTE, EQUIVOCADO, OTRO y SIN RESULTADO
        (marcado solo por máquina sin dato de centralita: hoy, todo noviembre).
   3. score.sp_AsegurarHistorial: además de cargar ayer,
      - recarga un día de lunes a sábado que quedó sin llamadas de máquina (como el 23/11), si su última carga
        tiene más de 2 horas;
      - arma el rendimiento de cada día que carga o recarga.

   ORDEN: bloques 0 a 3 completos; luego el bloque 4 (recarga del 14 al 23/11 y armado del rendimiento).
   ===================================================================================== */
USE CobAuto;
GO

/* =====================================================================================
   BLOQUE 0 · Columnas y tabla
   ===================================================================================== */
IF COL_LENGTH('score.TelefonoDia', 'Intentos_Manana') IS NULL
    ALTER TABLE score.TelefonoDia ADD
        Intentos_Manana SMALLINT NOT NULL CONSTRAINT DF_score_TelefonoDia_IntManana DEFAULT (0),
        Intentos_Medio  SMALLINT NOT NULL CONSTRAINT DF_score_TelefonoDia_IntMedio  DEFAULT (0),
        Intentos_Tarde  SMALLINT NOT NULL CONSTRAINT DF_score_TelefonoDia_IntTarde  DEFAULT (0),
        Intentos_Noche  SMALLINT NOT NULL CONSTRAINT DF_score_TelefonoDia_IntNoche  DEFAULT (0);
GO

IF OBJECT_ID('score.RendimientoDia', 'U') IS NULL
CREATE TABLE score.RendimientoDia (
    IdCartera        INT          NOT NULL,
    Fecha            DATE         NOT NULL,
    Canal            VARCHAR(10)  NOT NULL,   -- SIN BASE · PRED · IVR · SMS (si salió en varias bases: PRED > IVR > SMS)
    Tramo            VARCHAR(10)  NOT NULL,   -- A … E · SIN SCORE
    Orden            VARCHAR(3)   NOT NULL,   -- 1 · 2 · 3+ · -
    Osiptel          VARCHAR(12)  NOT NULL,
    Timbra           VARCHAR(12)  NOT NULL,
    Whatsapp         VARCHAR(12)  NOT NULL,
    Origen           VARCHAR(12)  NOT NULL,
    Fuente           VARCHAR(16)  NOT NULL,
    Color            VARCHAR(12)  NOT NULL,
    Telefonos        INT          NOT NULL,   -- teléfonos en la celda ese día (marcados o no)
    Marcados         INT          NOT NULL,   -- con al menos un intento ese día
    Intentos         INT          NOT NULL,
    IntentosHumano   INT          NOT NULL,
    IntentosMaquina  INT          NOT NULL,
    Cef              INT          NOT NULL,   -- eventos CEF (titular o tercero con acuerdo)
    ConCefPaleta     INT          NOT NULL,   -- teléfonos con CEF según la paleta del banco
    R_Cef            INT          NOT NULL,   -- mejor resultado del día (excluyentes; suman Marcados)
    R_Tercero        INT          NOT NULL,
    R_ContestaSinId  INT          NOT NULL,
    R_NoContesta     INT          NOT NULL,
    R_Buzon          INT          NOT NULL,
    R_Apagado        INT          NOT NULL,
    R_NoExiste       INT          NOT NULL,
    R_Equivocado     INT          NOT NULL,
    R_Otro           INT          NOT NULL,
    R_SinResultado   INT          NOT NULL,
    Int_Manana       INT          NOT NULL,
    Int_Medio        INT          NOT NULL,
    Int_Tarde        INT          NOT NULL,
    Int_Noche        INT          NOT NULL,
    Cef_Manana       INT          NOT NULL,
    Cef_Medio        INT          NOT NULL,
    Cef_Tarde        INT          NOT NULL,
    Cef_Noche        INT          NOT NULL,
    FechaArmado      DATETIME2(0) NOT NULL
);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'CIX_score_RendimientoDia' AND object_id = OBJECT_ID('score.RendimientoDia'))
    CREATE CLUSTERED INDEX CIX_score_RendimientoDia ON score.RendimientoDia (IdCartera, Fecha);
GO

/* =====================================================================================
   BLOQUE 1 · score.sp_CargarTelefonoDia (igual a la fase 1 + intentos por franja)
   ===================================================================================== */
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
        -- fase 13: intentos por franja (humanos y de máquina; la centralita son las mismas llamadas de la máquina)
        SUM(CASE WHEN Fuente IN ('H', 'M') AND DATEPART(HOUR, Momento) BETWEEN 6 AND 11  THEN 1 ELSE 0 END) AS Intentos_Manana,
        SUM(CASE WHEN Fuente IN ('H', 'M') AND DATEPART(HOUR, Momento) BETWEEN 12 AND 14 THEN 1 ELSE 0 END) AS Intentos_Medio,
        SUM(CASE WHEN Fuente IN ('H', 'M') AND DATEPART(HOUR, Momento) BETWEEN 15 AND 17 THEN 1 ELSE 0 END) AS Intentos_Tarde,
        SUM(CASE WHEN Fuente IN ('H', 'M') AND DATEPART(HOUR, Momento) >= 18             THEN 1 ELSE 0 END) AS Intentos_Noche,
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
            Intentos_Manana, Intentos_Medio, Intentos_Tarde, Intentos_Noche,
            UltimoEvento, UltimoResultado, MejorResultado, MomentoMejor)
        SELECT Fecha, IdCartera, DNI, Telefono, IntentosHumano, IntentosMaquina, LlamadasCentralita,
            N_TITULAR, N_TERCERO_ACUERDO, N_TERCERO, N_FALLECIDO, N_CONTESTA_SIN_ID, N_NO_CONTESTA, N_BUZON,
            N_APAGADO, N_SIN_INFORMACION, N_EQUIVOCADO, N_NO_EXISTE, N_NO_APLICA, N_SIN_CLASIFICAR, N_CEF_SISCOB,
            Contactos_Manana, Contactos_Medio, Contactos_Tarde, Contactos_Noche,
            Intentos_Manana, Intentos_Medio, Intentos_Tarde, Intentos_Noche,
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

/* =====================================================================================
   BLOQUE 2 · score.sp_ArmarRendimientoDia
   ===================================================================================== */
CREATE OR ALTER PROCEDURE score.sp_ArmarRendimientoDia
    @Fecha     DATE,
    @IdCartera INT = NULL,      -- NULL = todas las carteras con score ese día
    @Simular   BIT = 0
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    IF @Fecha IS NULL OR @Fecha >= CAST(GETDATE() AS DATE)
        THROW 51301, 'El rendimiento se arma para días completos (hasta ayer).', 1;
    IF NOT EXISTS (SELECT 1 FROM score.TelefonoDiaControl WHERE Fecha = @Fecha)
        THROW 51302, 'Ese día no tiene historial cargado (score.TelefonoDia).', 1;

    DECLARE @Sig DATE = DATEADD(DAY, 1, @Fecha), @Ahora DATETIME2(0) = SYSDATETIME();
    -- Atributos: los del mismo día o, si ya no están (Caracteristicas guarda 7 días), los del corte más cercano
    DECLARE @CorteAtr DATE = (SELECT MAX(FechaCorte) FROM score.Caracteristicas
                              WHERE Poblacion = 'UNIVERSO' AND FechaCorte <= @Fecha);
    IF @CorteAtr IS NULL
        SET @CorteAtr = (SELECT MIN(FechaCorte) FROM score.Caracteristicas WHERE Poblacion = 'UNIVERSO');

    -- 1. Teléfonos del día: los del score de ese día + los marcados que no estaban en el score
    CREATE TABLE #p (
        IdCartera INT NOT NULL, DNI VARCHAR(20) COLLATE DATABASE_DEFAULT NOT NULL,
        Telefono CHAR(9) COLLATE DATABASE_DEFAULT NOT NULL,
        Tramo VARCHAR(10) NOT NULL, Orden VARCHAR(3) NOT NULL,
        PRIMARY KEY (IdCartera, DNI, Telefono));
    INSERT INTO #p (IdCartera, DNI, Telefono, Tramo, Orden)
    SELECT s.IdCartera, s.DNI, s.Telefono, s.Tramo,
           CASE WHEN s.OrdenCliente >= 3 THEN '3+' ELSE CONVERT(VARCHAR(3), s.OrdenCliente) END
    FROM score.TelefonoScore AS s
    WHERE s.FechaCorte = @Fecha AND (@IdCartera IS NULL OR s.IdCartera = @IdCartera);

    CREATE TABLE #car (IdCartera INT NOT NULL PRIMARY KEY);
    INSERT INTO #car (IdCartera) SELECT DISTINCT IdCartera FROM #p;

    INSERT INTO #p (IdCartera, DNI, Telefono, Tramo, Orden)
    SELECT d.IdCartera, d.DNI, d.Telefono, 'SIN SCORE', '-'
    FROM score.TelefonoDia AS d
    WHERE d.Fecha = @Fecha AND d.IdCartera IN (SELECT IdCartera FROM #car)
      AND NOT EXISTS (SELECT 1 FROM #p AS p WHERE p.IdCartera = d.IdCartera AND p.DNI = d.DNI AND p.Telefono = d.Telefono);

    -- 2. Canal de la base en la que salió ese día (cada fila de la base conserva su cartera real)
    CREATE TABLE #b (
        IdCartera INT NOT NULL, DNI VARCHAR(20) COLLATE DATABASE_DEFAULT NOT NULL,
        Telefono CHAR(9) COLLATE DATABASE_DEFAULT NOT NULL, Canal VARCHAR(10) NOT NULL,
        PRIMARY KEY (IdCartera, DNI, Telefono));
    INSERT INTO #b (IdCartera, DNI, Telefono, Canal)
    SELECT d.IdCartera, d.DNI, d.Telefono,
           CASE MIN(CASE b.Canal WHEN 'PRED' THEN 1 WHEN 'IVR' THEN 2 WHEN 'SMS' THEN 3 ELSE 4 END)
                WHEN 1 THEN 'PRED' WHEN 2 THEN 'IVR' WHEN 3 THEN 'SMS' ELSE 'OTRO' END
    FROM score.Base AS b
    INNER JOIN score.BaseDetalle AS d ON d.IdBase = b.IdBase
    WHERE b.FechaGeneracion >= @Fecha AND b.FechaGeneracion < @Sig
      AND d.IdCartera IN (SELECT IdCartera FROM #car)
    GROUP BY d.IdCartera, d.DNI, d.Telefono;

    -- 3. Resumen
    SELECT p.IdCartera, @Fecha AS Fecha, ISNULL(b.Canal, 'SIN BASE') AS Canal, p.Tramo, p.Orden,
           ISNULL(c.S_OSIPTEL, 'SIN_DATO') AS Osiptel, ISNULL(c.S_TIMBRA, 'SIN_DATO') AS Timbra,
           ISNULL(c.S_WHATSAPP, 'SIN_DATO') AS Whatsapp, ISNULL(c.S_ORIGEN, 'SIN_DATO') AS Origen,
           ISNULL(c.S_FUENTE, 'SIN_DATO') AS Fuente, ISNULL(c.S_COLOR, 'SIN_DATO') AS Color,
           COUNT(*) AS Telefonos,
           SUM(CASE WHEN ISNULL(t.IntentosHumano, 0) + ISNULL(t.IntentosMaquina, 0) > 0 THEN 1 ELSE 0 END) AS Marcados,
           SUM(ISNULL(t.IntentosHumano, 0) + ISNULL(t.IntentosMaquina, 0)) AS Intentos,
           SUM(ISNULL(t.IntentosHumano, 0)) AS IntentosHumano,
           SUM(ISNULL(t.IntentosMaquina, 0)) AS IntentosMaquina,
           SUM(ISNULL(t.N_TITULAR, 0) + ISNULL(t.N_TERCERO_ACUERDO, 0)) AS Cef,
           SUM(CASE WHEN t.N_CEF_SISCOB > 0 THEN 1 ELSE 0 END) AS ConCefPaleta,
           SUM(CASE WHEN r.Grupo = 'CEF' THEN 1 ELSE 0 END) AS R_Cef,
           SUM(CASE WHEN r.Grupo = 'TERCERO' THEN 1 ELSE 0 END) AS R_Tercero,
           SUM(CASE WHEN r.Grupo = 'CONTESTA_SIN_ID' THEN 1 ELSE 0 END) AS R_ContestaSinId,
           SUM(CASE WHEN r.Grupo = 'NO_CONTESTA' THEN 1 ELSE 0 END) AS R_NoContesta,
           SUM(CASE WHEN r.Grupo = 'BUZON' THEN 1 ELSE 0 END) AS R_Buzon,
           SUM(CASE WHEN r.Grupo = 'APAGADO' THEN 1 ELSE 0 END) AS R_Apagado,
           SUM(CASE WHEN r.Grupo = 'NO_EXISTE' THEN 1 ELSE 0 END) AS R_NoExiste,
           SUM(CASE WHEN r.Grupo = 'EQUIVOCADO' THEN 1 ELSE 0 END) AS R_Equivocado,
           SUM(CASE WHEN r.Grupo = 'OTRO' THEN 1 ELSE 0 END) AS R_Otro,
           SUM(CASE WHEN r.Grupo = 'SIN_RESULTADO' THEN 1 ELSE 0 END) AS R_SinResultado,
           SUM(ISNULL(t.Intentos_Manana, 0)) AS Int_Manana, SUM(ISNULL(t.Intentos_Medio, 0)) AS Int_Medio,
           SUM(ISNULL(t.Intentos_Tarde, 0)) AS Int_Tarde, SUM(ISNULL(t.Intentos_Noche, 0)) AS Int_Noche,
           SUM(ISNULL(t.Contactos_Manana, 0)) AS Cef_Manana, SUM(ISNULL(t.Contactos_Medio, 0)) AS Cef_Medio,
           SUM(ISNULL(t.Contactos_Tarde, 0)) AS Cef_Tarde, SUM(ISNULL(t.Contactos_Noche, 0)) AS Cef_Noche
    INTO #r
    FROM #p AS p
    LEFT JOIN #b AS b ON b.IdCartera = p.IdCartera AND b.DNI = p.DNI AND b.Telefono = p.Telefono
    LEFT JOIN score.TelefonoDia AS t
           ON t.Fecha = @Fecha AND t.IdCartera = p.IdCartera AND t.DNI = p.DNI AND t.Telefono = p.Telefono
    LEFT JOIN score.Caracteristicas AS c
           ON c.FechaCorte = @CorteAtr AND c.Poblacion = 'UNIVERSO'
          AND c.IdCartera = p.IdCartera AND c.DNI = p.DNI AND c.Telefono = p.Telefono
    CROSS APPLY (SELECT CASE
        WHEN ISNULL(t.IntentosHumano, 0) + ISNULL(t.IntentosMaquina, 0) = 0 THEN 'NO_MARCADO'
        WHEN t.MejorResultado IN ('TITULAR', 'TERCERO_ACUERDO') THEN 'CEF'
        WHEN t.MejorResultado IN ('TERCERO', 'FALLECIDO') THEN 'TERCERO'
        WHEN t.MejorResultado = 'CONTESTA_SIN_ID' THEN 'CONTESTA_SIN_ID'
        WHEN t.MejorResultado = 'NO_CONTESTA' THEN 'NO_CONTESTA'
        WHEN t.MejorResultado = 'BUZON' THEN 'BUZON'
        WHEN t.MejorResultado = 'APAGADO' THEN 'APAGADO'
        WHEN t.MejorResultado = 'NO_EXISTE' THEN 'NO_EXISTE'
        WHEN t.MejorResultado = 'EQUIVOCADO' THEN 'EQUIVOCADO'
        WHEN t.MejorResultado IS NULL THEN 'SIN_RESULTADO'
        ELSE 'OTRO' END AS Grupo) AS r
    GROUP BY p.IdCartera, ISNULL(b.Canal, 'SIN BASE'), p.Tramo, p.Orden,
             ISNULL(c.S_OSIPTEL, 'SIN_DATO'), ISNULL(c.S_TIMBRA, 'SIN_DATO'), ISNULL(c.S_WHATSAPP, 'SIN_DATO'),
             ISNULL(c.S_ORIGEN, 'SIN_DATO'), ISNULL(c.S_FUENTE, 'SIN_DATO'), ISNULL(c.S_COLOR, 'SIN_DATO');

    IF @Simular = 1
    BEGIN
        SELECT 'SIMULACION' AS Modo, @Fecha AS Fecha, @CorteAtr AS CorteAtributos, COUNT(*) AS Filas,
               SUM(Telefonos) AS Telefonos, SUM(Marcados) AS Marcados, SUM(Intentos) AS Intentos, SUM(R_Cef) AS ConCef
        FROM #r;
        SELECT Tramo, SUM(Telefonos) AS Telefonos, SUM(Marcados) AS Marcados, SUM(Intentos) AS Intentos,
               SUM(R_Cef) AS ConCef,
               CAST(100.0 * SUM(R_Cef) / NULLIF(SUM(Marcados), 0) AS DECIMAL(6, 2)) AS PctCef
        FROM #r GROUP BY Tramo ORDER BY Tramo;
        RETURN;
    END;

    BEGIN TRAN;
        DELETE FROM score.RendimientoDia
        WHERE Fecha = @Fecha AND (@IdCartera IS NULL OR IdCartera = @IdCartera);
        INSERT INTO score.RendimientoDia (
            IdCartera, Fecha, Canal, Tramo, Orden, Osiptel, Timbra, Whatsapp, Origen, Fuente, Color,
            Telefonos, Marcados, Intentos, IntentosHumano, IntentosMaquina, Cef, ConCefPaleta,
            R_Cef, R_Tercero, R_ContestaSinId, R_NoContesta, R_Buzon, R_Apagado, R_NoExiste, R_Equivocado, R_Otro,
            R_SinResultado, Int_Manana, Int_Medio, Int_Tarde, Int_Noche, Cef_Manana, Cef_Medio, Cef_Tarde, Cef_Noche,
            FechaArmado)
        SELECT IdCartera, Fecha, Canal, Tramo, Orden, Osiptel, Timbra, Whatsapp, Origen, Fuente, Color,
            Telefonos, Marcados, Intentos, IntentosHumano, IntentosMaquina, Cef, ConCefPaleta,
            R_Cef, R_Tercero, R_ContestaSinId, R_NoContesta, R_Buzon, R_Apagado, R_NoExiste, R_Equivocado, R_Otro,
            R_SinResultado, Int_Manana, Int_Medio, Int_Tarde, Int_Noche, Cef_Manana, Cef_Medio, Cef_Tarde, Cef_Noche,
            @Ahora
        FROM #r;
        DELETE FROM score.RendimientoDia WHERE Fecha < DATEADD(DAY, -60, @Fecha);
    COMMIT;

    SELECT 'ARMADO' AS Modo, @Fecha AS Fecha, @CorteAtr AS CorteAtributos, COUNT(*) AS Filas,
           SUM(Telefonos) AS Telefonos, SUM(Marcados) AS Marcados, SUM(R_Cef) AS ConCef
    FROM #r;
END;
GO

/* =====================================================================================
   BLOQUE 3 · score.sp_AsegurarHistorial (igual a la fase 3 + recarga de días sin máquina + rendimiento)
   ===================================================================================== */
CREATE OR ALTER PROCEDURE score.sp_AsegurarHistorial
    @MaxDias INT = 7
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    DECLARE @Ayer DATE = DATEADD(DAY, -1, CAST(GETDATE() AS DATE));

    -- fase 13: días de lunes a sábado de la ventana que quedaron sin llamadas de máquina (el predictivo llegó
    -- después de la carga, como el 23/11). Se recargan si su última carga tiene más de 2 horas.
    DECLARE @Incompletos TABLE (Fecha DATE PRIMARY KEY);
    INSERT INTO @Incompletos (Fecha)
    SELECT Fecha FROM score.TelefonoDiaControl
    WHERE Fecha >= DATEADD(DAY, 1 - @MaxDias, @Ayer) AND Fecha <= @Ayer
      AND EventosMaquina = 0
      AND DATEDIFF(DAY, '19000107', Fecha) % 7 <> 0                -- no domingo (07/01/1900 fue domingo)
      AND FechaCarga < DATEADD(HOUR, -2, SYSDATETIME());

    IF EXISTS (SELECT 1 FROM score.TelefonoDiaControl
               WHERE Fecha = @Ayer AND FechaCarga >= CAST(DATEADD(DAY, 1, @Ayer) AS DATETIME2(0)))
       AND NOT EXISTS (SELECT 1 FROM @Incompletos)
       AND (OBJECT_ID('score.RendimientoDia', 'U') IS NULL
            OR EXISTS (SELECT 1 FROM score.RendimientoDia WHERE Fecha = @Ayer)
            OR NOT EXISTS (SELECT 1 FROM score.TelefonoScore WHERE FechaCorte = @Ayer))
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

        DECLARE @Armar TABLE (Fecha DATE PRIMARY KEY);
        WHILE @d <= @Ayer
        BEGIN
            EXEC score.sp_CargarTelefonoDia @Fecha = @d, @Simular = 0;
            INSERT INTO @Armar (Fecha) VALUES (@d);
            SET @d = DATEADD(DAY, 1, @d);
        END;

        -- Recarga de los días incompletos
        DECLARE @r DATE = (SELECT MIN(Fecha) FROM @Incompletos WHERE Fecha NOT IN (SELECT Fecha FROM @Armar));
        WHILE @r IS NOT NULL
        BEGIN
            EXEC score.sp_CargarTelefonoDia @Fecha = @r, @Simular = 0;
            INSERT INTO @Armar (Fecha) VALUES (@r);
            SET @r = (SELECT MIN(Fecha) FROM @Incompletos WHERE Fecha > @r AND Fecha NOT IN (SELECT Fecha FROM @Armar));
        END;

        -- Rendimiento de ayer si falta (primera vez) y de cada día cargado. Si falla, el historial queda igual.
        IF NOT EXISTS (SELECT 1 FROM @Armar WHERE Fecha = @Ayer)
           AND OBJECT_ID('score.RendimientoDia', 'U') IS NOT NULL
           AND NOT EXISTS (SELECT 1 FROM score.RendimientoDia WHERE Fecha = @Ayer)
            INSERT INTO @Armar (Fecha) VALUES (@Ayer);
        DECLARE @a DATE = (SELECT MIN(Fecha) FROM @Armar);
        WHILE @a IS NOT NULL
        BEGIN
            IF OBJECT_ID('score.sp_ArmarRendimientoDia', 'P') IS NOT NULL
               AND EXISTS (SELECT 1 FROM score.TelefonoScore WHERE FechaCorte = @a)
            BEGIN
                BEGIN TRY
                    EXEC score.sp_ArmarRendimientoDia @Fecha = @a;
                END TRY
                BEGIN CATCH
                    IF XACT_STATE() <> 0 ROLLBACK;
                    PRINT CONCAT(N'Rendimiento del ', CONVERT(CHAR(10), @a, 103), N' no armado: ', ERROR_MESSAGE());
                END CATCH;
            END;
            SET @a = (SELECT MIN(Fecha) FROM @Armar WHERE Fecha > @a);
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

/* =====================================================================================
   BLOQUE 4 · Recarga del 14 al 23/11 y armado del rendimiento (ejecutar por partes)
   ===================================================================================== */
/* 4.1 · Recargar el historial con los intentos por franja (también corrige el 23/11 si ya llegó la máquina).
         Unos segundos por día; anotar los EventosMaquina del 23/11.
EXEC score.sp_CargarTelefonoDiaRango @Desde = '2026-11-14', @Hasta = '2026-11-23', @Simular = 0;
*/

/* 4.2 · Armar el rendimiento de esos días (el score existe desde el 14/11)
DECLARE @d DATE = '2026-11-14';
WHILE @d <= DATEADD(DAY, -1, CAST(GETDATE() AS DATE))
BEGIN
    EXEC score.sp_ArmarRendimientoDia @Fecha = @d;
    SET @d = DATEADD(DAY, 1, @d);
END;
*/

/* 4.3 · Control: días armados, tamaño y la tabla por tramo de las 10 carteras (últimos 7 días)
SELECT Fecha, COUNT(*) AS Filas, SUM(Telefonos) AS Telefonos, SUM(Marcados) AS Marcados, SUM(Intentos) AS Intentos,
       SUM(R_Cef) AS ConCef, SUM(Int_Manana + Int_Medio + Int_Tarde + Int_Noche) AS IntentosConFranja
FROM score.RendimientoDia GROUP BY Fecha ORDER BY Fecha;

SELECT Tramo, SUM(Telefonos) AS TelefonoDias, SUM(Marcados) AS Marcados, SUM(Intentos) AS Intentos, SUM(R_Cef) AS ConCef,
       CAST(100.0 * SUM(R_Cef) / NULLIF(SUM(Marcados), 0) AS DECIMAL(6, 2)) AS PctCefSobreMarcados,
       CAST(100.0 * SUM(Cef) / NULLIF(SUM(Intentos), 0) AS DECIMAL(6, 2)) AS CefPor100Intentos
FROM score.RendimientoDia
WHERE Fecha >= DATEADD(DAY, -7, CAST(GETDATE() AS DATE))
GROUP BY Tramo ORDER BY Tramo;
*/
