/* =====================================================================================
   diagnostico_cierre_turno_1.sql  ·  solo lectura  ·  < 1 min
   Prototipo de la tabla diaria por agente que reportan los supervisores, para el 25/11,
   y así compararla con los cuadros que enviaron ese día.
   Reglas acordadas (26/11):
     · Generación PDP (día)   = monto de PDP (> 0) registradas en gestiones del día, por el agente que las registró
     · Proyectado hoy         = monto de PDP con fecha de compromiso = ese día
     · Pagado hoy             = PDP pagadas en SISCOB "hoy"  → ver sección 1: ¿hay columna de fecha de pago?
     · Total pagado en el mes = PDP pagadas en SISCOB (MONTOPAGADO) con fecha de compromiso en el mes
                                (la misma regla de la vista de meta del agente en el CRM)
     · Meta                   = CobAuto.dbo.CRM_META_AGENTE
     · BOLSA                  = lo registrado por usuarios que no son agentes activos de la cartera
   Ctrl+T y guardar en tools/salidas/resultado_cierre_turno_1.txt
   ===================================================================================== */
SET NOCOUNT ON;
SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED;

PRINT '=== 1. Columnas de SISCOB.dbo.COMPROMISO y de USUARIO (tipo/estado) ===';
SELECT c.name AS Columna, t.name AS Tipo
FROM SISCOB.sys.columns AS c JOIN SISCOB.sys.types AS t ON t.user_type_id = c.user_type_id
WHERE c.object_id = OBJECT_ID('SISCOB.dbo.COMPROMISO') ORDER BY c.column_id;
SELECT TipoUsuario, Estado, COUNT(*) AS Usuarios FROM SISCOB.dbo.USUARIO WITH (NOLOCK)
GROUP BY TipoUsuario, Estado ORDER BY TipoUsuario, Estado;
GO

PRINT '=== 2. Prototipo por cartera y agente, 25/11/2026 ===';
DECLARE @dia DATE = '2026-11-25';
DECLARE @ini DATE = DATEFROMPARTS(YEAR(@dia), MONTH(@dia), 1);
DECLARE @fin DATE = DATEADD(MONTH, 1, @ini);
DECLARE @codmes CHAR(6) = CONVERT(CHAR(6), @dia, 112);

IF OBJECT_ID('tempdb..#p') IS NOT NULL DROP TABLE #p;
SELECT g.idCartera AS IdCartera, g.IDUSUARIO, CAST(g.FECHA AS DATE) AS FechaGestion,
       CAST(c.FECHACOMPROMISO AS DATE) AS FechaCompromiso,
       ISNULL(c.MONTO, 0) AS Monto, ISNULL(c.MONTOPAGADO, 0) AS MontoPagado,
       CASE WHEN c.PAGADO = 'SI' OR ISNULL(c.MONTOPAGADO, 0) > 0 THEN 1 ELSE 0 END AS Pagada
INTO #p
FROM SISCOB.dbo.COMPROMISO AS c WITH (NOLOCK)
JOIN SISCOB.dbo.GESTION AS g WITH (NOLOCK) ON g.IDGESTION = c.IDGESTION
WHERE c.MONTO > 0
  AND (c.FECHACOMPROMISO >= DATEADD(MONTH, -1, @ini) OR g.FECHA >= @ini);

;WITH a AS (
    SELECT p.IdCartera, p.IDUSUARIO,
           SUM(CASE WHEN p.FechaGestion = @dia THEN p.Monto ELSE 0 END) AS GeneracionPdp,
           SUM(CASE WHEN p.FechaGestion = @dia THEN 1 ELSE 0 END) AS PdpGeneradas,
           SUM(CASE WHEN p.FechaCompromiso = @dia THEN p.Monto ELSE 0 END) AS ProyectadoHoy,
           SUM(CASE WHEN p.FechaCompromiso = @dia AND p.Pagada = 1 THEN p.MontoPagado ELSE 0 END) AS PagadoDeLoProyectado,
           SUM(CASE WHEN p.FechaCompromiso >= @ini AND p.FechaCompromiso < @fin AND p.Pagada = 1 THEN p.MontoPagado ELSE 0 END) AS TotalPagadoMes
    FROM #p AS p
    GROUP BY p.IdCartera, p.IDUSUARIO
)
SELECT a.IdCartera,
       CASE WHEN u.Estado = 'A' AND u.IDCARTERA = a.IdCartera THEN CONCAT(LTRIM(RTRIM(u.USUARIO)), ' - ', u.Nombres, ' ', u.Apellidos)
            ELSE 'BOLSA' END AS Agente,
       u.TipoUsuario, u.Estado, u.IDCARTERA AS CarteraUsuario,
       a.GeneracionPdp, a.PdpGeneradas, a.ProyectadoHoy, a.PagadoDeLoProyectado, a.TotalPagadoMes,
       m.meta_mensual AS Meta,
       CAST(100.0 * a.TotalPagadoMes / NULLIF(m.meta_mensual, 0) AS DECIMAL(7, 2)) AS PctAlcance
FROM a
LEFT JOIN SISCOB.dbo.USUARIO AS u WITH (NOLOCK) ON u.IDUSUARIO = a.IDUSUARIO
LEFT JOIN CobAuto.dbo.CRM_META_AGENTE AS m WITH (NOLOCK)
       ON m.codmes = @codmes AND m.activo = 1 AND m.idcartera = a.IdCartera AND LTRIM(RTRIM(m.usuario)) = LTRIM(RTRIM(u.USUARIO))
WHERE a.GeneracionPdp > 0 OR a.ProyectadoHoy > 0 OR a.TotalPagadoMes > 0
ORDER BY a.IdCartera, Agente;

PRINT '--- Totales por cartera ---';
SELECT p.IdCartera,
       SUM(CASE WHEN p.FechaGestion = @dia THEN p.Monto ELSE 0 END) AS GeneracionPdp,
       SUM(CASE WHEN p.FechaCompromiso = @dia THEN p.Monto ELSE 0 END) AS ProyectadoHoy,
       SUM(CASE WHEN p.FechaCompromiso = @dia AND p.Pagada = 1 THEN p.MontoPagado ELSE 0 END) AS PagadoDeLoProyectado,
       SUM(CASE WHEN p.FechaCompromiso >= @ini AND p.FechaCompromiso < @fin AND p.Pagada = 1 THEN p.MontoPagado ELSE 0 END) AS TotalPagadoMes
FROM #p AS p GROUP BY p.IdCartera ORDER BY p.IdCartera;

PRINT '--- Metas por cartera en CRM_META_AGENTE (mes) ---';
SELECT idcartera, COUNT(*) AS Agentes, MIN(meta_mensual) AS MetaMin, MAX(meta_mensual) AS MetaMax, SUM(meta_mensual) AS MetaTotal
FROM CobAuto.dbo.CRM_META_AGENTE WITH (NOLOCK)
WHERE codmes = @codmes AND activo = 1 GROUP BY idcartera ORDER BY idcartera;
GO
