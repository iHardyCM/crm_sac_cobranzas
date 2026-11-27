/* =====================================================================================
   score_telefonico_fase19_zonas.sql  ·  Zonas restringidas (Hardy, 27/11/2026)
   Interbank ordenó detener toda gestión en Piura (llamadas y comunicaciones complementarias). Hardy: el control
   va por DEPARTAMENTO completo y en las carteras que él elija.

   Crea en CobAuto:
     · score.ZonaRestringida          una fila por restricción: nivel (DEPARTAMENTO/PROVINCIA/DISTRITO), valor,
                                       motivo, origen (BANCO/INTERNO), vigencia y traza. Nunca se borra: se da de baja.
     · score.ZonaRestringidaCartera   a qué carteras aplica cada restricción.
     · score.vw_ClienteZonaRestringida clientes (IdCartera, DNI) que caen en una restricción vigente, cruzando con la
                                       ubicación que ya usa el generador (score.vw_DatoCliente, campos DEPARTAMENTO /
                                       PROVINCIA / DISTRITO de la asignación).
   El generador de bases (generador_bases_service) agrega el paso forzado «Sin zona restringida» cuando hay una
   restricción vigente para la cartera: rige al generar, sin esperar la actualización del score.

   Ubicación disponible hoy en el generador (diagnostico_zonas_1): 112, 117, 126, 128, 137, 148.
   Sin ubicación todavía: 124, 132, 133, 139, 141, 144 → sus clientes NO se pueden excluir hasta cargarla.

   Alcance (Hardy 27/11): @Todas = 1 → la restricción aplica a TODAS las carteras, también a las que reciban su
   departamento más adelante (no hay que volver a correr nada: la vista toma la ubicación de cada cartera que la tenga).
   @Todas = 0 → solo las carteras de @car.

   Paso 1: correr con @Aplicar = 0. Crea las tablas y la vista (vacías: sin restricciones el generador no cambia) y
           simula cuántos clientes saldrían por cartera y cuántos no tienen ubicación.
   Paso 2: @Aplicar = 1. Registra la restricción de Piura en las carteras de @car: desde ese momento el generador los excluye.
   ===================================================================================== */
USE CobAuto;
GO
SET NOCOUNT ON;

IF OBJECT_ID('score.ZonaRestringida', 'U') IS NULL
CREATE TABLE score.ZonaRestringida (
    IdZona          INT IDENTITY(1, 1) NOT NULL CONSTRAINT PK_score_ZonaRestringida PRIMARY KEY,
    Nivel           VARCHAR(20)    NOT NULL CONSTRAINT CK_score_ZonaRestringida_Nivel CHECK (Nivel IN ('DEPARTAMENTO', 'PROVINCIA', 'DISTRITO')),
    Valor           NVARCHAR(200)  NOT NULL,     -- tal como viene en la asignación (p. ej. PIURA)
    Motivo          NVARCHAR(400)  NOT NULL,
    Origen          VARCHAR(10)    NOT NULL CONSTRAINT CK_score_ZonaRestringida_Origen CHECK (Origen IN ('BANCO', 'INTERNO')),
    Desde           DATE           NOT NULL,
    Hasta           DATE           NULL,         -- NULL = hasta que se levante
    Activo          BIT            NOT NULL CONSTRAINT DF_score_ZonaRestringida_Activo DEFAULT (1),
    UsuarioRegistro VARCHAR(50)    NOT NULL,
    FechaRegistro   DATETIME2(0)   NOT NULL CONSTRAINT DF_score_ZonaRestringida_Fecha DEFAULT (SYSDATETIME()),
    AplicaTodas     BIT            NOT NULL CONSTRAINT DF_score_ZonaRestringida_Todas DEFAULT (0),
    UsuarioBaja     VARCHAR(50)    NULL,
    FechaBaja       DATETIME2(0)   NULL,
    MotivoBaja      NVARCHAR(400)  NULL
);
GO
IF COL_LENGTH('score.ZonaRestringida', 'AplicaTodas') IS NULL
    ALTER TABLE score.ZonaRestringida ADD AplicaTodas BIT NOT NULL CONSTRAINT DF_score_ZonaRestringida_Todas DEFAULT (0);
GO
IF OBJECT_ID('score.ZonaRestringidaCartera', 'U') IS NULL
CREATE TABLE score.ZonaRestringidaCartera (
    IdZona    INT NOT NULL CONSTRAINT FK_score_ZonaRestringidaCartera_Zona REFERENCES score.ZonaRestringida (IdZona),
    IdCartera INT NOT NULL,
    CONSTRAINT PK_score_ZonaRestringidaCartera PRIMARY KEY (IdZona, IdCartera)
);
GO

CREATE OR ALTER VIEW score.vw_ClienteZonaRestringida
AS
/* Clientes que caen en una zona restringida vigente hoy, por cartera. Cruza por el valor tal como viene en la
   asignación (la intercalación de la base no distingue mayúsculas). */
SELECT DISTINCT d.IdCartera, d.DNI, z.IdZona, z.Nivel, z.Valor, z.Origen
FROM score.ZonaRestringida AS z
INNER JOIN score.vw_DatoCliente AS d ON d.Campo = z.Nivel AND LTRIM(RTRIM(d.Valor)) = z.Valor
WHERE z.Activo = 1
  AND (z.AplicaTodas = 1
       OR EXISTS (SELECT 1 FROM score.ZonaRestringidaCartera AS zc WHERE zc.IdZona = z.IdZona AND zc.IdCartera = d.IdCartera))
  AND z.Desde <= CAST(GETDATE() AS DATE)
  AND (z.Hasta IS NULL OR z.Hasta >= CAST(GETDATE() AS DATE));
GO

/* ---------------------------------------------------------------- restricción de Piura */
DECLARE @Aplicar  BIT           = 0;
DECLARE @Todas    BIT           = 1;               -- 1 = todas las carteras (también las que tengan ubicación después)
DECLARE @Usuario  VARCHAR(50)   = 'HCRUZ';
DECLARE @Nivel    VARCHAR(20)   = 'DEPARTAMENTO';
DECLARE @Valor    NVARCHAR(200) = N'PIURA';
DECLARE @Motivo   NVARCHAR(400) = N'Interbank 27/11/2026: detener toda gestión de clientes en Piura (llamadas y comunicaciones complementarias).';
DECLARE @Origen   VARCHAR(10)   = 'BANCO';

-- Con @Todas = 0: las carteras que tú decidas, una por fila (ej. VALUES (117), (137)).
-- (Sin STRING_SPLIT: CobAuto tiene un nivel de compatibilidad que no lo permite.)
DECLARE @car TABLE (IdCartera INT PRIMARY KEY);
IF @Todas = 0
    INSERT INTO @car (IdCartera) VALUES (117);
ELSE   -- simulación de «todas»: las carteras que hoy tienen ese nivel de ubicación en el generador
    INSERT INTO @car (IdCartera) SELECT DISTINCT IdCartera FROM score.CampoCartera WHERE Campo = @Nivel;

IF @Todas = 1
    PRINT 'Alcance: TODAS las carteras. Hoy tienen ' + @Nivel + ' las carteras de la simulación; las demás entrarán solas cuando se les cargue la ubicación.';

PRINT '=== Simulación: clientes de la base de trabajo que saldrían, y clientes sin ubicación ===';
SELECT c.IdCartera,
       (SELECT COUNT(DISTINCT t.DNI) FROM score.vw_BaseTrabajo AS t WHERE t.IdCartera = c.IdCartera) AS ClientesBase,
       (SELECT COUNT(DISTINCT t.DNI) FROM score.vw_BaseTrabajo AS t
         WHERE t.IdCartera = c.IdCartera
           AND EXISTS (SELECT 1 FROM score.vw_DatoCliente AS d WHERE d.IdCartera = t.IdCartera AND d.DNI = t.DNI
                         AND d.Campo = @Nivel AND LTRIM(RTRIM(d.Valor)) = @Valor)) AS ClientesQueSalen,
       (SELECT COUNT(DISTINCT t.DNI) FROM score.vw_BaseTrabajo AS t
         WHERE t.IdCartera = c.IdCartera
           AND NOT EXISTS (SELECT 1 FROM score.vw_DatoCliente AS d WHERE d.IdCartera = t.IdCartera AND d.DNI = t.DNI
                             AND d.Campo = @Nivel AND NULLIF(LTRIM(RTRIM(d.Valor)), '') IS NOT NULL)) AS ClientesSinUbicacion
FROM @car AS c ORDER BY c.IdCartera;

PRINT '=== Valores de ' + @Nivel + ' por cartera (para revisar cómo viene escrito) ===';
SELECT d.IdCartera, LTRIM(RTRIM(d.Valor)) AS Valor, COUNT(DISTINCT d.DNI) AS Clientes
FROM score.vw_DatoCliente AS d INNER JOIN @car AS c ON c.IdCartera = d.IdCartera
WHERE d.Campo = @Nivel
GROUP BY d.IdCartera, LTRIM(RTRIM(d.Valor))
ORDER BY d.IdCartera, Clientes DESC;

IF @Aplicar = 1
BEGIN
    IF EXISTS (SELECT 1 FROM score.ZonaRestringida WHERE Activo = 1 AND Nivel = @Nivel AND Valor = @Valor)
        PRINT 'Ya existe una restricción activa para ' + @Nivel + ' ' + @Valor + ': se actualiza su alcance.';
    ELSE
        INSERT INTO score.ZonaRestringida (Nivel, Valor, Motivo, Origen, Desde, UsuarioRegistro, AplicaTodas)
        VALUES (@Nivel, @Valor, @Motivo, @Origen, CAST(GETDATE() AS DATE), @Usuario, @Todas);

    DECLARE @id INT = (SELECT MAX(IdZona) FROM score.ZonaRestringida WHERE Activo = 1 AND Nivel = @Nivel AND Valor = @Valor);
    IF @Todas = 1
        UPDATE score.ZonaRestringida SET AplicaTodas = 1 WHERE IdZona = @id;
    ELSE
        INSERT INTO score.ZonaRestringidaCartera (IdZona, IdCartera)
        SELECT @id, c.IdCartera FROM @car AS c
        WHERE NOT EXISTS (SELECT 1 FROM score.ZonaRestringidaCartera AS x WHERE x.IdZona = @id AND x.IdCartera = c.IdCartera);

    SELECT z.IdZona, z.Nivel, z.Valor, z.Origen, z.Desde, z.Hasta, z.Motivo,
           CASE WHEN z.AplicaTodas = 1 THEN 'TODAS' END AS Alcance,
           STUFF((SELECT ', ' + CAST(zc.IdCartera AS VARCHAR(10)) FROM score.ZonaRestringidaCartera AS zc
                  WHERE zc.IdZona = z.IdZona ORDER BY zc.IdCartera FOR XML PATH('')), 1, 2, '') AS Carteras
    FROM score.ZonaRestringida AS z
    WHERE z.Activo = 1;

    SELECT IdCartera, COUNT(DISTINCT DNI) AS ClientesRestringidos FROM score.vw_ClienteZonaRestringida GROUP BY IdCartera;
END;
GO

/* Para levantar una restricción (no se borra, queda la traza):
   UPDATE score.ZonaRestringida SET Activo = 0, UsuarioBaja = 'HCRUZ', FechaBaja = SYSDATETIME(), MotivoBaja = N'...'
   WHERE IdZona = ?;
   Para agregar otra cartera a una restricción:  INSERT INTO score.ZonaRestringidaCartera VALUES (IdZona, IdCartera); */
