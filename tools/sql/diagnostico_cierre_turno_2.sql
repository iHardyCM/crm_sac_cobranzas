/* =====================================================================================
   diagnostico_cierre_turno_2.sql  ·  solo lectura  ·  < 1 min
   Segunda vuelta contra los cuadros de los supervisores del 25/11. Cambios frente a la versión 1:
     · Pagado hoy        = PDP pagadas con FechaPago = ese día (antes: pagado de lo proyectado)
     · Total pagado mes  = PDP pagadas con FechaPago entre el 1 y ese día (antes: fecha de compromiso en
                           el mes, que sumaba pagos registrados después del cierre del turno)
     · BOLSA solo si el usuario no está activo; un agente activo de otra cartera sale con su nombre
       (ej. IVON y PAMELA, de 126, en el cuadro de propias)
     · Propias = 137 + 148 juntas, como el cuadro del supervisor
     · Detalle de las PDP del 25/11 en 144 (Castigo CSM), donde la generación no cuadra
   Ctrl+T y guardar en tools/salidas/resultado_cierre_turno_2.txt
   ===================================================================================== */
SET NOCOUNT ON;
SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED;

DECLARE @dia DATE = '2026-11-25';
DECLARE @ini DATE = DATEFROMPARTS(YEAR(@dia), MONTH(@dia), 1);

IF OBJECT_ID('tempdb..#p') IS NOT NULL DROP TABLE #p;
SELECT CASE WHEN g.idCartera IN (137, 148) THEN 137 ELSE g.idCartera END AS Grupo,
       g.idCartera AS IdCartera, g.IDUSUARIO, CAST(g.FECHA AS DATE) AS FechaGestion,
       CAST(c.FechaCompromiso AS DATE) AS FechaCompromiso, CAST(c.FechaPago AS DATE) AS FechaPago,
       c.FechaGenero, c.TipoPago, c.IdCompromiso, c.NumOperacion,
       ISNULL(c.Monto, 0) AS Monto, ISNULL(c.MontoPagado, 0) AS MontoPagado,
       CASE WHEN c.Pagado = 'SI' OR ISNULL(c.MontoPagado, 0) > 0 THEN 1 ELSE 0 END AS Pagada
INTO #p
FROM SISCOB.dbo.COMPROMISO AS c WITH (NOLOCK)
JOIN SISCOB.dbo.GESTION AS g WITH (NOLOCK) ON g.IDGESTION = c.idGestion
WHERE c.Monto > 0
  AND (c.FechaCompromiso >= DATEADD(MONTH, -2, @ini) OR g.FECHA >= @ini OR c.FechaPago >= @ini);

PRINT '=== 1. Por grupo de cartera y agente (25/11) ===';
;WITH a AS (
    SELECT p.Grupo, p.IDUSUARIO,
           SUM(CASE WHEN p.FechaGestion = @dia THEN p.Monto ELSE 0 END) AS GeneracionPdp,
           SUM(CASE WHEN p.FechaGestion = @dia THEN 1 ELSE 0 END) AS PdpGeneradas,
           SUM(CASE WHEN p.FechaCompromiso = @dia THEN p.Monto ELSE 0 END) AS ProyectadoHoy,
           SUM(CASE WHEN p.FechaCompromiso = @dia AND p.Pagada = 1 THEN p.MontoPagado ELSE 0 END) AS PagadoDeLoProyectado,
           SUM(CASE WHEN p.Pagada = 1 AND p.FechaPago = @dia THEN p.MontoPagado ELSE 0 END) AS PagadoHoy_FechaPago,
           SUM(CASE WHEN p.Pagada = 1 AND p.FechaPago >= @ini AND p.FechaPago <= @dia THEN p.MontoPagado ELSE 0 END) AS TotalMes_FechaPago,
           SUM(CASE WHEN p.Pagada = 1 AND p.FechaCompromiso >= @ini AND p.FechaCompromiso <= @dia THEN p.MontoPagado ELSE 0 END) AS TotalMes_FechaCompromiso,
           SUM(CASE WHEN p.Pagada = 1 AND p.FechaPago IS NULL AND p.FechaCompromiso >= @ini THEN 1 ELSE 0 END) AS PagadasSinFechaPago
    FROM #p AS p
    GROUP BY p.Grupo, p.IDUSUARIO
)
SELECT a.Grupo,
       CASE WHEN u.Estado = 'A' THEN CONCAT(LTRIM(RTRIM(u.USUARIO)), ' - ', u.Nombres, ' ', u.Apellidos) ELSE 'BOLSA' END AS Agente,
       u.TipoUsuario, u.IDCARTERA AS CarteraUsuario,
       a.GeneracionPdp, a.PdpGeneradas, a.ProyectadoHoy, a.PagadoDeLoProyectado, a.PagadoHoy_FechaPago,
       a.TotalMes_FechaPago, a.TotalMes_FechaCompromiso, a.PagadasSinFechaPago
FROM a
LEFT JOIN SISCOB.dbo.USUARIO AS u WITH (NOLOCK) ON u.IDUSUARIO = a.IDUSUARIO
WHERE a.GeneracionPdp > 0 OR a.ProyectadoHoy > 0 OR a.TotalMes_FechaPago > 0 OR a.TotalMes_FechaCompromiso > 0
ORDER BY a.Grupo, Agente;

PRINT '=== 2. Totales por grupo de cartera ===';
SELECT p.Grupo,
       SUM(CASE WHEN p.FechaGestion = @dia THEN p.Monto ELSE 0 END) AS GeneracionPdp,
       SUM(CASE WHEN p.FechaCompromiso = @dia THEN p.Monto ELSE 0 END) AS ProyectadoHoy,
       SUM(CASE WHEN p.Pagada = 1 AND p.FechaPago = @dia THEN p.MontoPagado ELSE 0 END) AS PagadoHoy_FechaPago,
       SUM(CASE WHEN p.Pagada = 1 AND p.FechaPago >= @ini AND p.FechaPago <= @dia THEN p.MontoPagado ELSE 0 END) AS TotalMes_FechaPago
FROM #p AS p GROUP BY p.Grupo ORDER BY p.Grupo;

PRINT '=== 3. 144 Castigo CSM: PDP registradas el 25/11 (la generación del supervisor es menor) ===';
SELECT CONCAT(LTRIM(RTRIM(u.USUARIO)), ' - ', u.Nombres) AS Agente, p.IdCompromiso, p.NumOperacion, p.TipoPago,
       p.FechaGenero, p.FechaGestion, p.FechaCompromiso, p.Monto, p.Pagada, p.FechaPago, p.MontoPagado
FROM #p AS p LEFT JOIN SISCOB.dbo.USUARIO AS u WITH (NOLOCK) ON u.IDUSUARIO = p.IDUSUARIO
WHERE p.IdCartera = 144 AND p.FechaGestion = @dia
ORDER BY Agente, p.FechaGenero;
GO
