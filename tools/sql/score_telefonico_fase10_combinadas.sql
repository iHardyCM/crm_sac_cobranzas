/* =====================================================================================
   Generador de bases · fase 10 · carteras combinadas                           (16/11/2026)
   Base: CobAuto (esquema score). Se puede volver a ejecutar completo.

   Una cartera combinada junta varias carteras reales en una sola opción del generador (Hardy, 16/11):
     901 = COMPARTAMOS VIGENTE IND + CCM (126 + 128).
   Reglas:
     - Cada fila conserva su cartera real (IDCARTERA del archivo, gestiones, segmentos, condiciones del día).
     - Un mismo cliente + teléfono que está en ambas carteras va UNA vez: la fila que cumple los filtros y,
       entre esas, la de mejor score (a igual score, la cartera de número menor).
     - 126 y 128 siguen disponibles por separado.
     - "Ya enviado hoy" se mira por la cartera de cada fila enviada: lo que salió en la combinada cuenta para
       126 y 128, y al revés.
     - Actualizar la combinada actualiza 126 y luego 128.
     - Permisos: el usuario debe tener las dos carteras.
     - Nombre del archivo: empieza con CarteraArchivo (el cargador de LunaTel toma la cartera de los 3 primeros
       dígitos) y luego la abreviatura. Ej.: 126_1611-1030_PRED_INDCCM_..._B123. PENDIENTE de confirmar.

   ORDEN: ejecutar este archivo y luego reiniciar el backend. Sin este archivo el generador funciona igual
   (no muestra combinadas).
   ===================================================================================== */
USE CobAuto;
GO

IF OBJECT_ID('score.CarteraCombinada') IS NULL
    CREATE TABLE score.CarteraCombinada (
        IdCartera      INT           NOT NULL CONSTRAINT PK_score_CarteraCombinada PRIMARY KEY, -- número propio, no existe en SISCOB
        Nombre         NVARCHAR(100) NOT NULL,
        Abreviatura    VARCHAR(12)   NOT NULL,     -- va en el nombre del archivo
        CarteraArchivo INT           NOT NULL,     -- 3 primeros dígitos del nombre del archivo
        Activo         BIT           NOT NULL CONSTRAINT DF_score_CarteraCombinada_Activo DEFAULT (1),
        FechaCreacion  DATETIME2(0)  NOT NULL CONSTRAINT DF_score_CarteraCombinada_Fecha DEFAULT (SYSDATETIME())
    );
GO

IF OBJECT_ID('score.CarteraCombinadaMiembro') IS NULL
    CREATE TABLE score.CarteraCombinadaMiembro (
        IdCartera        INT NOT NULL CONSTRAINT FK_score_CarteraCombinadaMiembro
                                      REFERENCES score.CarteraCombinada (IdCartera),
        IdCarteraMiembro INT NOT NULL,
        CONSTRAINT PK_score_CarteraCombinadaMiembro PRIMARY KEY (IdCartera, IdCarteraMiembro)
    );
GO

-- El número de la combinada no puede ser una cartera real
IF EXISTS (SELECT 1 FROM score.BaseTrabajoEstado WHERE IdCartera = 901)
   OR EXISTS (SELECT 1 FROM ControlCobranza.bl.EntidadCartera WHERE IdCartera = 901)
    THROW 50001, 'La cartera 901 ya existe como cartera real: elige otro número para la combinada.', 1;

MERGE score.CarteraCombinada AS t
USING (SELECT 901 AS IdCartera, N'COMPARTAMOS VIGENTE IND + CCM' AS Nombre, 'INDCCM' AS Abreviatura,
              126 AS CarteraArchivo) AS s
ON t.IdCartera = s.IdCartera
WHEN MATCHED THEN UPDATE SET Nombre = s.Nombre, Abreviatura = s.Abreviatura, CarteraArchivo = s.CarteraArchivo, Activo = 1
WHEN NOT MATCHED THEN INSERT (IdCartera, Nombre, Abreviatura, CarteraArchivo) VALUES (s.IdCartera, s.Nombre, s.Abreviatura, s.CarteraArchivo);

MERGE score.CarteraCombinadaMiembro AS t
USING (VALUES (901, 126), (901, 128)) AS s (IdCartera, IdCarteraMiembro)
ON t.IdCartera = s.IdCartera AND t.IdCarteraMiembro = s.IdCarteraMiembro
WHEN NOT MATCHED BY TARGET THEN INSERT (IdCartera, IdCarteraMiembro) VALUES (s.IdCartera, s.IdCarteraMiembro)
WHEN NOT MATCHED BY SOURCE AND t.IdCartera = 901 THEN DELETE;
GO

-- La base combinada se guarda con IdCartera = 901 en score.Base: revisar que no haya una llave foránea que lo impida
SELECT fk.name AS LlaveForanea, OBJECT_NAME(fk.parent_object_id) AS Tabla, OBJECT_NAME(fk.referenced_object_id) AS Referencia
FROM sys.foreign_keys AS fk
WHERE fk.parent_object_id IN (OBJECT_ID('score.Base'), OBJECT_ID('score.BaseDetalle'));
GO

/* Control (ejecutar aparte)
-- 1. La combinada
SELECT c.*, m.IdCarteraMiembro FROM score.CarteraCombinada AS c
INNER JOIN score.CarteraCombinadaMiembro AS m ON m.IdCartera = c.IdCartera;

-- 2. Cuántos clientes y teléfonos están en las dos carteras (son los que la combinada deja una vez)
SELECT COUNT(DISTINCT a.DNI) AS ClientesEnAmbas,
       SUM(CASE WHEN b.Telefono IS NOT NULL THEN 1 ELSE 0 END) AS TelefonosEnAmbas
FROM score.vw_BaseTrabajo AS a
LEFT JOIN score.vw_BaseTrabajo AS b ON b.IdCartera = 128 AND b.DNI = a.DNI AND b.Telefono = a.Telefono
WHERE a.IdCartera = 126
  AND EXISTS (SELECT 1 FROM score.vw_BaseTrabajo AS c WHERE c.IdCartera = 128 AND c.DNI = a.DNI);
*/
