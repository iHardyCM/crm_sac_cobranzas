/* =====================================================================================
   score_telefonico_fase15_preview.sql · 24/11/2026
   Canal PREVIEW (marcador, igual que el predictivo):
   1. score.Base acepta el canal PREVIEW.
   2. score.sp_ArmarRendimientoDia reconoce PREVIEW (prioridad PRED > PREVIEW > IVR > SMS cuando un teléfono salió
      en varias bases el mismo día). Resto del procedimiento igual a la fase 13.
   Nombre de la base: la columna NombreArchivo (NVARCHAR(120)) ya alcanza; no cambia.
   ===================================================================================== */
USE CobAuto;
GO

/* 1. Restricción del canal */
IF EXISTS (SELECT 1 FROM sys.check_constraints WHERE name = 'CK_score_Base_Canal' AND parent_object_id = OBJECT_ID('score.Base'))
    ALTER TABLE score.Base DROP CONSTRAINT CK_score_Base_Canal;
GO
ALTER TABLE score.Base WITH CHECK ADD CONSTRAINT CK_score_Base_Canal CHECK (Canal IN ('PRED', 'PREVIEW', 'IVR', 'SMS', 'OTRO'));
GO

/* 2. Rendimiento por día con PREVIEW */
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
           CASE MIN(CASE b.Canal WHEN 'PRED' THEN 1 WHEN 'PREVIEW' THEN 2 WHEN 'IVR' THEN 3 WHEN 'SMS' THEN 4 ELSE 5 END)
                WHEN 1 THEN 'PRED' WHEN 2 THEN 'PREVIEW' WHEN 3 THEN 'IVR' WHEN 4 THEN 'SMS' ELSE 'OTRO' END
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

/* 3. Control */
SELECT name, definition FROM sys.check_constraints WHERE name = 'CK_score_Base_Canal';
SELECT CASE WHEN OBJECT_DEFINITION(OBJECT_ID('score.sp_ArmarRendimientoDia')) LIKE '%PREVIEW%' THEN 'OK' ELSE 'FALTA' END AS RendimientoConPreview;
GO
