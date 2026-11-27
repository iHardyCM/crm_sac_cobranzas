/* =====================================================================================
   diagnostico_sac_capital_1.sql · 25/11/2026 · SOLO LECTURA
   Capital de las carteras vigentes de Compartamos (126 IND, 128 CCM, 133 grupal):
   ¿qué usa hoy el generador y qué trae el SAC del día (Desarrollo.dbo.SAC_CAR_BIZNESCOB)?
   ===================================================================================== */
USE CobAuto;
GO

-- 1. Lo que usa hoy el generador: capital del corte de Analytics guardado en score.BaseTrabajoCliente
SELECT IdCartera, FechaCorteFuente, COUNT(*) AS Clientes, SUM(Capital) AS CapitalTotal,
       SUM(CASE WHEN Capital IS NULL THEN 1 ELSE 0 END) AS SinCapital
FROM score.BaseTrabajoCliente
WHERE IdCartera IN (126, 128, 133)
GROUP BY IdCartera, FechaCorteFuente
ORDER BY IdCartera, FechaCorteFuente;
GO

-- 2. Columnas del SAC y de la vista de asignación (para elegir el capital correcto)
SELECT 'SAC_CAR_BIZNESCOB' AS Tabla, c.column_id, c.name AS Columna, t.name AS Tipo
FROM Desarrollo.sys.columns AS c
JOIN Desarrollo.sys.types AS t ON t.user_type_id = c.user_type_id
WHERE c.object_id = OBJECT_ID('Desarrollo.dbo.SAC_CAR_BIZNESCOB')
UNION ALL
SELECT 'VW_CLIENTE_CRM_SAC', c.column_id, c.name, t.name
FROM Desarrollo.sys.columns AS c
JOIN Desarrollo.sys.types AS t ON t.user_type_id = c.user_type_id
WHERE c.object_id = OBJECT_ID('Desarrollo.dbo.VW_CLIENTE_CRM_SAC')
ORDER BY Tabla, column_id;
GO

-- 3. Cargas del SAC: ¿se reemplaza cada día o guarda historia? ¿a qué hora llega?
SELECT CAST(FechaCarga AS DATE) AS Dia, MIN(FechaCarga) AS Primera, MAX(FechaCarga) AS Ultima,
       COUNT(*) AS Filas, COUNT(DISTINCT DNI) AS DNIs, COUNT(DISTINCT [Cod Operación]) AS Operaciones
FROM Desarrollo.dbo.SAC_CAR_BIZNESCOB WITH (NOLOCK)
GROUP BY CAST(FechaCarga AS DATE)
ORDER BY Dia DESC;
GO

-- 4. Clientes del generador (126, 128, 133) que NO están en el SAC de la última carga
DECLARE @UltimaCarga DATE = (SELECT MAX(CAST(FechaCarga AS DATE)) FROM Desarrollo.dbo.SAC_CAR_BIZNESCOB WITH (NOLOCK));
IF OBJECT_ID('tempdb..#sac') IS NOT NULL DROP TABLE #sac;
SELECT DISTINCT RIGHT('00000000' + LTRIM(RTRIM(CONVERT(VARCHAR(20), DNI))), 8) AS DNI8
INTO #sac
FROM Desarrollo.dbo.SAC_CAR_BIZNESCOB WITH (NOLOCK)
WHERE CAST(FechaCarga AS DATE) = @UltimaCarga AND DNI IS NOT NULL;

SELECT b.IdCartera, @UltimaCarga AS SacDel,
       COUNT(*) AS ClientesGenerador,
       SUM(CASE WHEN s.DNI8 IS NOT NULL THEN 1 ELSE 0 END) AS EnSac,
       SUM(CASE WHEN s.DNI8 IS NULL THEN 1 ELSE 0 END) AS NoEstanEnSac,
       SUM(CASE WHEN s.DNI8 IS NULL THEN b.Capital ELSE 0 END) AS CapitalDeLosQueNoEstan
FROM score.BaseTrabajoCliente AS b
LEFT JOIN #sac AS s ON s.DNI8 = RIGHT('00000000' + LTRIM(RTRIM(b.DNI)), 8) COLLATE DATABASE_DEFAULT
WHERE b.IdCartera IN (126, 128, 133)
GROUP BY b.IdCartera
ORDER BY b.IdCartera;

-- 4.1 De los que no están en SAC: ¿qué dice su gestión del mes? (pagaron sin gestión, reclamo, etc.)
SELECT b.IdCartera, gc.Condicion, gc.MgContacto, gc.EstadoPdp, COUNT(*) AS Clientes
FROM score.BaseTrabajoCliente AS b
LEFT JOIN #sac AS s ON s.DNI8 = RIGHT('00000000' + LTRIM(RTRIM(b.DNI)), 8) COLLATE DATABASE_DEFAULT
LEFT JOIN score.GestionCliente AS gc ON gc.IdCartera = b.IdCartera AND gc.DNI = b.DNI
WHERE b.IdCartera IN (126, 128, 133) AND s.DNI8 IS NULL
GROUP BY b.IdCartera, gc.Condicion, gc.MgContacto, gc.EstadoPdp
ORDER BY b.IdCartera, COUNT(*) DESC;
GO
