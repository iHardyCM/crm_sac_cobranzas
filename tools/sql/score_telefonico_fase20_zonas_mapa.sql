/* =====================================================================================
   score_telefonico_fase20_zonas_mapa.sql  ·  Zonas restringidas desde el CRM (Hardy, 27/11/2026)
   Requiere fase19 (score.ZonaRestringida, score.ZonaRestringidaCartera, score.vw_ClienteZonaRestringida).

   La pantalla «Zonas restringidas» del CRM (mapa del Perú) registra los departamentos con su nombre en
   mayúsculas y sin tildes: SAN MARTIN, APURIMAC, HUANUCO, JUNIN, ANCASH...
   Cada cartera puede traerlo escrito distinto (con tilde, con espacios). Por eso:

   1. La vista score.vw_ClienteZonaRestringida compara sin distinguir tildes ni mayúsculas
      (APURÍMAC = APURIMAC). La restricción de Piura que ya está registrada sigue igual.
   2. Diagnóstico: valores de DEPARTAMENTO de cada cartera que NO corresponden a ninguno de los 25
      departamentos. Esos clientes no los puede excluir el mapa hasta que se corrija el valor o se agregue
      una equivalencia (por ejemplo «PROV. CONST. DEL CALLAO»). Si sale vacío, no hay nada que hacer.

   No modifica datos: solo la vista y consultas de lectura. Se puede correr más de una vez.
   ===================================================================================== */
USE CobAuto;
GO
SET NOCOUNT ON;
GO

CREATE OR ALTER VIEW score.vw_ClienteZonaRestringida
AS
/* Clientes que caen en una zona restringida vigente hoy, por cartera.
   Compara sin tildes ni mayúsculas: la pantalla guarda SAN MARTIN y la asignación puede traer San Martín. */
SELECT DISTINCT d.IdCartera, d.DNI, z.IdZona, z.Nivel, z.Valor, z.Origen
FROM score.ZonaRestringida AS z
INNER JOIN score.vw_DatoCliente AS d
        ON d.Campo = z.Nivel
       AND LTRIM(RTRIM(d.Valor)) COLLATE Latin1_General_CI_AI = z.Valor COLLATE Latin1_General_CI_AI
WHERE z.Activo = 1
  AND (z.AplicaTodas = 1
       OR EXISTS (SELECT 1 FROM score.ZonaRestringidaCartera AS zc WHERE zc.IdZona = z.IdZona AND zc.IdCartera = d.IdCartera))
  AND z.Desde <= CAST(GETDATE() AS DATE)
  AND (z.Hasta IS NULL OR z.Hasta >= CAST(GETDATE() AS DATE));
GO

/* ---------------------------------------------------------------- 1. control: la restricción vigente sigue igual */
PRINT '=== 1. Clientes excluidos hoy por cartera (debe dar lo mismo que antes: 112=632, 117=125, ...) ===';
SELECT IdCartera, COUNT(DISTINCT DNI) AS ClientesExcluidos
FROM score.vw_ClienteZonaRestringida
GROUP BY IdCartera
ORDER BY IdCartera;

/* ---------------------------------------------------------------- 2. valores que el mapa no reconoce */
DECLARE @dep TABLE (Departamento NVARCHAR(40) COLLATE Latin1_General_CI_AI PRIMARY KEY);
INSERT INTO @dep (Departamento) VALUES
 (N'AMAZONAS'), (N'ANCASH'), (N'APURIMAC'), (N'AREQUIPA'), (N'AYACUCHO'), (N'CAJAMARCA'), (N'CALLAO'),
 (N'CUSCO'), (N'HUANCAVELICA'), (N'HUANUCO'), (N'ICA'), (N'JUNIN'), (N'LA LIBERTAD'), (N'LAMBAYEQUE'),
 (N'LIMA'), (N'LORETO'), (N'MADRE DE DIOS'), (N'MOQUEGUA'), (N'PASCO'), (N'PIURA'), (N'PUNO'),
 (N'SAN MARTIN'), (N'TACNA'), (N'TUMBES'), (N'UCAYALI');

PRINT '=== 2. Valores de DEPARTAMENTO que no son ninguno de los 25 (vacío = todo cruza) ===';
SELECT d.IdCartera,
       LTRIM(RTRIM(d.Valor)) AS ValorEnAsignacion,
       COUNT(DISTINCT d.DNI) AS Clientes
FROM score.vw_DatoCliente AS d
WHERE d.Campo = 'DEPARTAMENTO'
  AND NULLIF(LTRIM(RTRIM(d.Valor)), '') IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM @dep AS x
                  WHERE x.Departamento = LTRIM(RTRIM(d.Valor)) COLLATE Latin1_General_CI_AI)
GROUP BY d.IdCartera, LTRIM(RTRIM(d.Valor))
ORDER BY d.IdCartera, Clientes DESC;

/* ---------------------------------------------------------------- 3. cobertura de ubicación por cartera */
PRINT '=== 3. Carteras con DEPARTAMENTO en el generador: clientes con y sin valor ===';
SELECT c.IdCartera,
       COUNT(DISTINCT CASE WHEN NULLIF(LTRIM(RTRIM(d.Valor)), '') IS NOT NULL THEN d.DNI END) AS ClientesConDepartamento,
       COUNT(DISTINCT CASE WHEN NULLIF(LTRIM(RTRIM(d.Valor)), '') IS NULL THEN d.DNI END)     AS ClientesValorVacio
FROM (SELECT DISTINCT IdCartera FROM score.CampoCartera WHERE Campo = 'DEPARTAMENTO') AS c
LEFT JOIN score.vw_DatoCliente AS d ON d.IdCartera = c.IdCartera AND d.Campo = 'DEPARTAMENTO'
GROUP BY c.IdCartera
ORDER BY c.IdCartera;
GO
