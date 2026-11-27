/* =====================================================================================
   crm_cierre_turno_fase1.sql  ·  Cierre de turno por agente (tabla diaria de los supervisores)
   Crea en CobAuto:
     · dbo.CRM_CIERRE_TURNO_GRUPO       qué carteras se reportan juntas (un cuadro por grupo)
     · dbo.sp_CRM_CierreTurnoAgentes    una fila por agente del grupo para un día
   Reglas validadas el 26/11 contra los cuadros del 25/11 (ver claude/cierre_turno_agentes.md):
     · Fuente: SISCOB.dbo.COMPROMISO (Monto > 0) + GESTION (agente = usuario que registró la PDP)
     · Generación PDP      = monto de PDP registradas en gestiones del día
     · Proyectado hoy      = monto de PDP con FechaCompromiso = día
     · Pagado hoy          = MontoPagado de PDP pagadas con FechaPago = día
     · Total pagado mes    = MontoPagado de PDP pagadas con FechaPago entre el 1 y el día
     · Agente con su nombre aunque sea de otra cartera; BOLSA = usuario no activo
     · Meta: CobAuto.dbo.CRM_META_AGENTE (hoy vacía → Meta y Alcance salen NULL)
   Solo crea objetos; no modifica datos de SISCOB. Al final corre una prueba con el 25/11.
   ===================================================================================== */
USE CobAuto;
GO
SET NOCOUNT ON;

IF OBJECT_ID('dbo.CRM_CIERRE_TURNO_GRUPO', 'U') IS NULL
    CREATE TABLE dbo.CRM_CIERRE_TURNO_GRUPO (
        IdGrupo   INT           NOT NULL,   -- cartera principal del cuadro
        Nombre    NVARCHAR(80)  NOT NULL,
        IdCartera INT           NOT NULL,   -- cartera de la gestión que suma en el cuadro
        CONSTRAINT PK_CRM_CIERRE_TURNO_GRUPO PRIMARY KEY (IdGrupo, IdCartera)
    );
GO

/* Grupos: confirmados Propias (137+148) y Castigo CSM (144+139). El resto, una cartera por cuadro.
   Para juntar, por ejemplo 126 + 128:  INSERT INTO dbo.CRM_CIERRE_TURNO_GRUPO VALUES (126, N'Vigente individual + CCM', 128);
   (y borrar la fila de IdGrupo 128 si ya no se quiere un cuadro aparte). */
MERGE dbo.CRM_CIERRE_TURNO_GRUPO AS t
USING (VALUES
    (112, N'MiBanco castigo', 112),
    (117, N'Interbank', 117),
    (124, N'Compartamos castigo individual', 124),
    (126, N'Compartamos vigente individual', 126),
    (128, N'Compartamos vigente CCM', 128),
    (132, N'Financiera OH', 132),
    (133, N'Compartamos vigente grupal', 133),
    (137, N'Propias', 137),
    (137, N'Propias', 148),
    (144, N'Compartamos castigo CSM', 144),
    (144, N'Compartamos castigo CSM', 139)
) AS s (IdGrupo, Nombre, IdCartera)
ON t.IdGrupo = s.IdGrupo AND t.IdCartera = s.IdCartera
WHEN NOT MATCHED THEN INSERT (IdGrupo, Nombre, IdCartera) VALUES (s.IdGrupo, s.Nombre, s.IdCartera);
GO

CREATE OR ALTER PROCEDURE dbo.sp_CRM_CierreTurnoAgentes
    @IdGrupo INT,
    @Fecha   DATE = NULL          -- NULL = hoy
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

    -- PDP que pueden tocar alguna columna del día o del mes
    SELECT g.IDUSUARIO,
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
    b AS (   -- BOLSA: usuarios no activos se juntan en una fila
        SELECT CASE WHEN u.Estado = 'A' THEN LTRIM(RTRIM(u.USUARIO)) ELSE N'BOLSA' END AS Usuario,
               CASE WHEN u.Estado = 'A' THEN CONCAT(LTRIM(RTRIM(u.USUARIO)), N' - ', LTRIM(RTRIM(u.Nombres)), N' ', LTRIM(RTRIM(u.Apellidos)))
                    ELSE N'BOLSA' END AS Agente,
               CASE WHEN u.Estado = 'A' THEN u.TipoUsuario END AS TipoUsuario,
               CASE WHEN u.Estado = 'A' THEN u.IDCARTERA END AS CarteraUsuario,
               a.*
        FROM a LEFT JOIN SISCOB.dbo.USUARIO AS u WITH (NOLOCK) ON u.IDUSUARIO = a.IDUSUARIO
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

/* Prueba con el 25/11: Propias debe dar TotalPagadoMes 68,504.50 (cuadro del supervisor: exacto). */
EXEC dbo.sp_CRM_CierreTurnoAgentes @IdGrupo = 137, @Fecha = '2026-11-25';
EXEC dbo.sp_CRM_CierreTurnoAgentes @IdGrupo = 144, @Fecha = '2026-11-25';
GO
