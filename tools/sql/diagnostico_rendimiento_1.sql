/* =====================================================================================
   diagnostico_rendimiento_1.sql · 24/11/2026 · SOLO LECTURA
   1. ¿Por qué el 23/11 (lunes) tiene 0 llamadas de máquina? Compara pgestion por día y cartera.
   2. ¿Qué indicador quedó sin clasificar el 17/11?
   ===================================================================================== */
USE CobAuto;
GO

-- 1.1 Llamadas de máquina en la copia local por día (del 17/11 a hoy)
SELECT CAST(g.Fecha AS DATE) AS Fecha, COUNT_BIG(*) AS Llamadas,
       COUNT(DISTINCT g.idCartera) AS Carteras,
       MIN(CAST(g.Hora AS TIME(0))) AS PrimeraHora, MAX(CAST(g.Hora AS TIME(0))) AS UltimaHora
FROM siscob.dbo.pgestion AS g WITH (NOLOCK)
WHERE g.Fecha >= '2026-11-17' AND g.Fecha < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
GROUP BY CAST(g.Fecha AS DATE)
ORDER BY Fecha;
GO

-- 1.2 Lo mismo por cartera, solo para el 21/11 (sábado) y el 23/11 (lunes)
SELECT CAST(g.Fecha AS DATE) AS Fecha, g.idCartera, COUNT_BIG(*) AS Llamadas
FROM siscob.dbo.pgestion AS g WITH (NOLOCK)
WHERE g.Fecha >= '2026-11-21' AND g.Fecha < '2026-11-24'
GROUP BY CAST(g.Fecha AS DATE), g.idCartera
ORDER BY Fecha, g.idCartera;
GO

-- 1.3 Bases del generador enviadas el 23/11 (si hubo predictivo o IVR, la máquina debió llamar)
SELECT b.IdCartera, b.Canal, COUNT(*) AS Bases, SUM(b.Telefonos) AS Telefonos
FROM score.Base AS b
WHERE b.FechaGeneracion >= '2026-11-23' AND b.FechaGeneracion < '2026-11-24'
GROUP BY b.IdCartera, b.Canal
ORDER BY b.IdCartera, b.Canal;
GO

-- 2. Indicador sin clasificar del 17/11 (gestión humana)
SELECT g.idCartera, g.IdIndicador, i.DescripcionIndicador, i.TipoContacto, COUNT_BIG(*) AS Gestiones
FROM siscob.dbo.gestion AS g WITH (NOLOCK)
LEFT JOIN siscob.dbo.Indicador AS i WITH (NOLOCK) ON i.IdIndicador = g.IdIndicador
WHERE g.Fecha >= '2026-11-17' AND g.Fecha < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
  AND g.idCartera IN (SELECT IdCartera FROM ControlCobranza.bl.EntidadCartera)
  AND g.telefono BETWEEN 900000000 AND 999999999
  AND NOT EXISTS (SELECT 1 FROM score.IndicadorResultado AS r WHERE r.IdIndicador = g.IdIndicador)
GROUP BY g.idCartera, g.IdIndicador, i.DescripcionIndicador, i.TipoContacto
ORDER BY Gestiones DESC;
GO
