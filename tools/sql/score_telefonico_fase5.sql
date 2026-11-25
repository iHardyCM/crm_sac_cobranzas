/* =====================================================================================
   SCORE TELEFÓNICO · FASE 5 — BASES GENERADAS (TRAZA)
   Fecha: 14/11/2026 · Diseño: claude/diseno_generador_bases.md (proyecto crm_cobranzas)
   Requiere: fases 1 a 4.

   Qué crea:
     score.Base          una fila por base generada: receta exacta (JSON), canal, usuario, fecha y hora, versión
                         del score, fecha del corte del cliente, totales y nombre del archivo exportado.
     score.BaseDetalle   cada teléfono que salió en la base, con su posición en el archivo.
   La base no se edita ni se borra: es la traza para medir su rendimiento y para repetirla.

   El código de la base (B + número) va al final del nombre del archivo: es lo que permite ligar los
   resultados de UCM (campana), LunaTel (nom), Mowa y Sinapsis (nombre de campaña) con la base exacta.

   Cómo ejecutarlo: bloque 0 (solo lectura), bloque 1 (tablas). No hay datos que migrar.
   ===================================================================================== */

USE CobAuto;
GO
SET NOCOUNT ON;
GO

/* =====================================================================================
   BLOQUE 0 · Comprobación (solo lectura): columnas de SISCOB.COMPROMISO
   Para "pago hoy" hace falta la columna de la fecha de pago; el CRM hoy solo usa PAGADO y MONTOPAGADO.
   ===================================================================================== */
SELECT c.name AS columna, t.name AS tipo, c.max_length, c.is_nullable
FROM siscob.sys.columns AS c
INNER JOIN siscob.sys.types AS t ON t.user_type_id = c.user_type_id
WHERE c.object_id = OBJECT_ID('siscob.dbo.COMPROMISO')
ORDER BY c.column_id;

SELECT TOP 5 PAGADO, COUNT(*) AS filas
FROM siscob.dbo.COMPROMISO WITH (NOLOCK)
GROUP BY PAGADO
ORDER BY filas DESC;
GO

/* =====================================================================================
   BLOQUE 1 · Tablas
   ===================================================================================== */
IF OBJECT_ID('score.Base', 'U') IS NULL
CREATE TABLE score.Base (
    IdBase              INT IDENTITY(1, 1) NOT NULL CONSTRAINT PK_score_Base PRIMARY KEY,
    Codigo              VARCHAR(12)    NULL,       -- B + IdBase (va al final del nombre del archivo)
    NombreArchivo       NVARCHAR(120)  NULL,       -- CCC_DDMM-HHMM_TIPO_RESUMEN_CODIGO
    IdCartera           INT            NOT NULL,
    Canal               VARCHAR(10)    NOT NULL,   -- PRED · IVR · SMS · OTRO
    Descripcion         NVARCHAR(200)  NULL,
    Receta              NVARCHAR(MAX)  NOT NULL,   -- filtros, condiciones del día y opciones, tal como se usaron (JSON)
    Usuario             VARCHAR(20)    NOT NULL,   -- DNI del usuario del CRM
    FechaGeneracion     DATETIME2(0)   NOT NULL CONSTRAINT DF_score_Base_Fecha DEFAULT (SYSDATETIME()),
    FechaScore          DATE           NULL,       -- fecha del score usado
    VersionScore        INT            NULL,
    FechaCorteCliente   DATE           NULL,       -- corte de Analytics de los datos del cliente
    UltimaActualizacion DATETIME2(0)   NULL,       -- última actualización OK de la cartera al generar
    Clientes            INT            NULL,
    Telefonos           INT            NULL,
    Capital             DECIMAL(18, 2) NULL,
    ScorePromedio       DECIMAL(6, 2)  NULL,
    IdBaseOrigen        INT            NULL,       -- si es la repetición de otra base
    CONSTRAINT CK_score_Base_Canal CHECK (Canal IN ('PRED', 'IVR', 'SMS', 'OTRO'))
);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_Base_Cartera' AND object_id = OBJECT_ID('score.Base'))
    CREATE INDEX IX_Base_Cartera ON score.Base (IdCartera, FechaGeneracion DESC) INCLUDE (Canal, Codigo);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'UX_Base_Codigo' AND object_id = OBJECT_ID('score.Base'))
    CREATE UNIQUE INDEX UX_Base_Codigo ON score.Base (Codigo) WHERE Codigo IS NOT NULL;
GO

IF OBJECT_ID('score.BaseDetalle', 'U') IS NULL
CREATE TABLE score.BaseDetalle (
    IdBase        INT          NOT NULL,
    Posicion      INT          NOT NULL,   -- orden en el archivo (1 = primera fila)
    IdCartera     INT          NOT NULL,
    DNI           VARCHAR(20)  NOT NULL,
    Telefono      CHAR(9)      NOT NULL,
    Score         TINYINT      NULL,
    Tramo         CHAR(1)      NULL,
    OrdenCliente  SMALLINT     NULL,       -- orden del teléfono dentro del cliente en esta base
    CONSTRAINT PK_score_BaseDetalle PRIMARY KEY CLUSTERED (IdBase, Posicion)
);
GO
-- Para atribuir resultados por teléfono ("la base más reciente generada antes del evento")
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_BaseDetalle_Telefono' AND object_id = OBJECT_ID('score.BaseDetalle'))
    CREATE INDEX IX_BaseDetalle_Telefono ON score.BaseDetalle (Telefono, IdBase) INCLUDE (DNI);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_BaseDetalle_Dni' AND object_id = OBJECT_ID('score.BaseDetalle'))
    CREATE INDEX IX_BaseDetalle_Dni ON score.BaseDetalle (IdCartera, DNI) INCLUDE (IdBase);
GO

-- La vista score.vw_BaseTrabajo busca el último score de cada cartera: sin este índice tendría que recorrer
-- los 90 días que guarda score.TelefonoScore (unos 850 mil teléfonos por día).
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_TelefonoScore_Cartera' AND object_id = OBJECT_ID('score.TelefonoScore'))
    CREATE INDEX IX_TelefonoScore_Cartera ON score.TelefonoScore (IdCartera, FechaCorte);
GO

SELECT 'OK' AS Estado,
       OBJECT_ID('score.Base') AS Base, OBJECT_ID('score.BaseDetalle') AS BaseDetalle;
GO
