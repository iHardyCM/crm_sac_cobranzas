/* =====================================================================================
   crm_cierre_turno_fase4.sql  ·  Cierre de turno: detalle para el Excel de corroboración
   Hardy (27/11/2026): «exportar Excel: primera hoja la misma tabla, segunda hoja todos los clientes que
   participaron para ese resultado (operación, monto pagado, monto generado…) para corroborar».
   Agrega @Detalle a dbo.sp_CRM_CierreTurnoAgentes: con @Detalle = 1 devuelve una fila por PDP que suma en alguna
   columna, con las mismas reglas y el mismo agente/BOLSA que la tabla (sumar las columnas del detalle por agente da
   la tabla). Sin @Detalle el resultado es el mismo de la fase 2. No modifica datos.
   ===================================================================================== */
USE CobAuto;
GO
CREATE OR ALTER PROCEDURE dbo.sp_CRM_CierreTurnoAgentes
    @IdGrupo INT,
    @Fecha   DATE = NULL,         -- NULL = hoy
    @Detalle BIT  = 0             -- 1 = una fila por PDP que suma en alguna columna (para el Excel de corroboración)
AS
BEGIN
    SET NOCOUNT ON;
    SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED;

    DECLARE @dia DATE = ISNULL(@Fecha, CAST(GETDATE() AS DATE));
    DECLARE @ini DATE = DATEFROMPARTS(YEAR(@dia), MONTH(@dia), 1);
    DECLARE @sig DATE = DATEADD(DAY, 1, @dia);
    DECLARE @codmes CHAR(6) = CONVERT(CHAR(6), @dia, 112);

    IF NOT EXISTS (SELECT 1 FROM dbo.CRM_CIERRE_TURNO_GRUPO WHERE IdGrupo = @IdGrupo)
        THROW 50001, 'El grupo no está configurado en CRM_CIERRE_TURNO_GRUPO.', 1;

    CREATE TABLE #car (IdCartera INT PRIMARY KEY);
    INSERT INTO #car SELECT IdCartera FROM dbo.CRM_CIERRE_TURNO_GRUPO WHERE IdGrupo = @IdGrupo;
    DECLARE @externosEnBolsa BIT = (SELECT MAX(CAST(ExternosEnBolsa AS INT)) FROM dbo.CRM_CIERRE_TURNO_GRUPO WHERE IdGrupo = @IdGrupo);

    -- PDP que pueden tocar alguna columna del día o del mes
    SELECT g.IDUSUARIO,
           g.idCartera                       AS IdCartera,
           LTRIM(RTRIM(CONVERT(VARCHAR(20), g.DNI))) AS DNI,
           c.IdCliente,
           LTRIM(RTRIM(CONVERT(VARCHAR(100), c.NumOperacion))) AS Operacion,
           c.IdCompromiso,
           c.TipoPago,
           g.FECHA                           AS FechaHoraGestion,
           CAST(g.FECHA AS DATE)             AS FechaGestion,
           CAST(c.FechaCompromiso AS DATE)   AS FechaCompromiso,
           CAST(c.FechaPago AS DATE)         AS FechaPago,
           ISNULL(c.Monto, 0)                AS Monto,
           ISNULL(c.MontoPagado, 0)          AS MontoPagado,
           CASE WHEN c.Pagado = 'SI' OR ISNULL(c.MontoPagado, 0) > 0 THEN 1 ELSE 0 END AS Pagada
    INTO #p
    FROM SISCOB.dbo.COMPROMISO AS c WITH (NOLOCK)
    JOIN SISCOB.dbo.GESTION AS g WITH (NOLOCK) ON g.IDGESTION = c.idGestion
    WHERE c.Monto > 0
      AND g.idCartera IN (SELECT IdCartera FROM #car)
      AND (  (g.FECHA >= @dia AND g.FECHA < @sig)
          OR (c.FechaCompromiso >= @dia AND c.FechaCompromiso < @sig)
          OR (c.FechaPago >= @ini AND c.FechaPago < @sig));

    IF @Detalle = 1
    BEGIN
        SELECT p.IdCartera,
               CASE WHEN u.Estado = 'A' AND (@externosEnBolsa = 0 OR u.IDCARTERA IN (SELECT IdCartera FROM #car))
                    THEN CONCAT(LTRIM(RTRIM(u.USUARIO)), N' - ', LTRIM(RTRIM(u.Nombres)), N' ', LTRIM(RTRIM(u.Apellidos)))
                    ELSE N'BOLSA' END                                   AS Agente,
               LTRIM(RTRIM(u.USUARIO))                                  AS UsuarioRegistro,
               u.Estado                                                 AS EstadoUsuario,
               u.IDCARTERA                                              AS CarteraUsuario,
               p.DNI, p.IdCliente, p.Operacion, p.IdCompromiso, p.TipoPago,
               p.FechaHoraGestion, p.FechaCompromiso, p.Monto,
               CASE WHEN p.Pagada = 1 THEN 'SI' ELSE 'NO' END            AS Pagada,
               CASE WHEN p.FechaPago > '1901-01-01' THEN p.FechaPago END AS FechaPago,
               p.MontoPagado,
               CASE WHEN p.FechaGestion = @dia THEN p.Monto ELSE 0 END                           AS GeneracionPdp,
               CASE WHEN p.FechaCompromiso = @dia THEN p.Monto ELSE 0 END                        AS ProyectadoHoy,
               CASE WHEN p.Pagada = 1 AND p.FechaPago = @dia THEN p.MontoPagado ELSE 0 END       AS PagadoHoy,
               CASE WHEN p.Pagada = 1 AND p.FechaPago >= @ini AND p.FechaPago <= @dia
                    THEN p.MontoPagado ELSE 0 END                                                AS TotalPagadoMes
        FROM #p AS p
        LEFT JOIN SISCOB.dbo.USUARIO AS u WITH (NOLOCK) ON u.IDUSUARIO = p.IDUSUARIO
        WHERE p.FechaGestion = @dia OR p.FechaCompromiso = @dia
           OR (p.Pagada = 1 AND p.FechaPago >= @ini AND p.FechaPago <= @dia)
        ORDER BY Agente, p.DNI, p.Operacion, p.IdCompromiso;
        RETURN;
    END;

    ;WITH a AS (
        SELECT p.IDUSUARIO,
               SUM(CASE WHEN p.FechaGestion = @dia THEN p.Monto ELSE 0 END)                         AS GeneracionPdp,
               SUM(CASE WHEN p.FechaGestion = @dia THEN 1 ELSE 0 END)                               AS PdpGeneradas,
               SUM(CASE WHEN p.FechaCompromiso = @dia THEN p.Monto ELSE 0 END)                      AS ProyectadoHoy,
               SUM(CASE WHEN p.FechaCompromiso = @dia AND p.Pagada = 1 THEN p.MontoPagado ELSE 0 END) AS PagadoDeLoProyectado,
               SUM(CASE WHEN p.Pagada = 1 AND p.FechaPago = @dia THEN p.MontoPagado ELSE 0 END)     AS PagadoHoy,
               SUM(CASE WHEN p.Pagada = 1 AND p.FechaPago >= @ini AND p.FechaPago <= @dia
                        THEN p.MontoPagado ELSE 0 END)                                              AS TotalPagadoMes
        FROM #p AS p
        GROUP BY p.IDUSUARIO
    ),
    u2 AS (
        SELECT a.*, u.USUARIO, u.Nombres, u.Apellidos, u.TipoUsuario AS Tipo, u.IDCARTERA,
               CASE WHEN u.Estado = 'A'
                     AND (@externosEnBolsa = 0 OR u.IDCARTERA IN (SELECT IdCartera FROM #car))
                    THEN 0 ELSE 1 END AS EsBolsa
        FROM a LEFT JOIN SISCOB.dbo.USUARIO AS u WITH (NOLOCK) ON u.IDUSUARIO = a.IDUSUARIO
    ),
    b AS (   -- BOLSA: usuarios no activos (y de otra cartera si el grupo lo pide) en una sola fila
        SELECT CASE WHEN EsBolsa = 0 THEN LTRIM(RTRIM(USUARIO)) ELSE N'BOLSA' END AS Usuario,
               CASE WHEN EsBolsa = 0 THEN CONCAT(LTRIM(RTRIM(USUARIO)), N' - ', LTRIM(RTRIM(Nombres)), N' ', LTRIM(RTRIM(Apellidos)))
                    ELSE N'BOLSA' END AS Agente,
               CASE WHEN EsBolsa = 0 THEN Tipo END AS TipoUsuario,
               CASE WHEN EsBolsa = 0 THEN IDCARTERA END AS CarteraUsuario,
               GeneracionPdp, PdpGeneradas, ProyectadoHoy, PagadoDeLoProyectado, PagadoHoy, TotalPagadoMes
        FROM u2
    ),
    r AS (
        SELECT Usuario, Agente, MAX(TipoUsuario) AS TipoUsuario, MAX(CarteraUsuario) AS CarteraUsuario,
               SUM(GeneracionPdp) AS GeneracionPdp, SUM(PdpGeneradas) AS PdpGeneradas,
               SUM(ProyectadoHoy) AS ProyectadoHoy, SUM(PagadoDeLoProyectado) AS PagadoDeLoProyectado,
               SUM(PagadoHoy) AS PagadoHoy, SUM(TotalPagadoMes) AS TotalPagadoMes
        FROM b GROUP BY Usuario, Agente
    )
    SELECT @IdGrupo AS IdGrupo, (SELECT TOP (1) Nombre FROM dbo.CRM_CIERRE_TURNO_GRUPO WHERE IdGrupo = @IdGrupo) AS Grupo,
           @dia AS Fecha,
           r.Agente, r.TipoUsuario, r.CarteraUsuario,
           r.GeneracionPdp, r.PdpGeneradas, r.ProyectadoHoy, r.PagadoHoy, r.PagadoDeLoProyectado,
           CAST(100.0 * r.PagadoDeLoProyectado / NULLIF(r.ProyectadoHoy, 0) AS DECIMAL(6, 1)) AS PctProyectadoPagado,
           r.TotalPagadoMes,
           m.Meta,
           CAST(100.0 * r.TotalPagadoMes / NULLIF(m.Meta, 0) AS DECIMAL(7, 2)) AS PctAlcance
    FROM r
    OUTER APPLY (SELECT SUM(ma.meta_mensual) AS Meta
                 FROM dbo.CRM_META_AGENTE AS ma WITH (NOLOCK)
                 WHERE ma.codmes = @codmes AND ma.activo = 1 AND r.Usuario <> N'BOLSA'
                   AND LTRIM(RTRIM(ma.usuario)) = r.Usuario
                   AND ma.idcartera IN (SELECT IdCartera FROM #car)) AS m
    WHERE r.GeneracionPdp > 0 OR r.ProyectadoHoy > 0 OR r.PagadoHoy > 0 OR r.TotalPagadoMes > 0
    ORDER BY CASE WHEN r.Agente = N'BOLSA' THEN 1 ELSE 0 END, r.Agente;
END;
GO


/* Prueba: la suma del detalle debe dar el total de la tabla (Propias, 25/11: TotalPagadoMes 68,504.50). */
DECLARE @d TABLE (IdCartera INT, Agente NVARCHAR(300), UsuarioRegistro VARCHAR(50), EstadoUsuario VARCHAR(5), CarteraUsuario INT,
                  DNI VARCHAR(20), IdCliente BIGINT, Operacion VARCHAR(100), IdCompromiso BIGINT, TipoPago NVARCHAR(100),
                  FechaHoraGestion DATETIME, FechaCompromiso DATE, Monto DECIMAL(18, 2), Pagada VARCHAR(2), FechaPago DATE,
                  MontoPagado DECIMAL(18, 2), GeneracionPdp DECIMAL(18, 2), ProyectadoHoy DECIMAL(18, 2), PagadoHoy DECIMAL(18, 2),
                  TotalPagadoMes DECIMAL(18, 2));
INSERT INTO @d EXEC dbo.sp_CRM_CierreTurnoAgentes @IdGrupo = 137, @Fecha = '2026-11-25', @Detalle = 1;
SELECT COUNT(*) AS FilasDetalle, SUM(GeneracionPdp) AS GeneracionPdp, SUM(ProyectadoHoy) AS ProyectadoHoy,
       SUM(PagadoHoy) AS PagadoHoy, SUM(TotalPagadoMes) AS TotalPagadoMes_Debe68504_50 FROM @d;
GO
