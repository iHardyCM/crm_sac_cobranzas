/* =====================================================================================
   Score telefónico · fase 12 · caché de las condiciones del día del generador de bases
   Base: CobAuto · esquema score · 20/11/2026
   Diseño: claude/diseno_generador_estrategias.md (R3)

   Para qué: medido el 20/11, leer las condiciones del día (CEF hoy, PDP vigente, PDP creada hoy,
   pago hoy, equivocado hoy) desde SISCOB en CADA clic costaba 8 a 11 s en la cartera 112. Ahora se
   leen una vez por cartera y condición, se guardan aquí, y la vista previa reutiliza esa foto
   hasta 2 minutos (generador_bases_reglas.SEGUNDOS_CACHE_CONDICIONES).

   - La base que se GENERA (botón Generar) sigue leyendo SISCOB en vivo: el archivo siempre sale al momento.
   - "Ya enviado hoy" sigue en vivo (lee score.Base, es local y depende del canal).
   - Hasta ejecutar este script, la pantalla funciona igual que antes (condiciones en vivo).

   Se puede volver a ejecutar: solo crea lo que no existe. No toca SISCOB ni otras tablas.
   ===================================================================================== */
USE CobAuto;
GO

IF OBJECT_ID('score.CondicionDia', 'U') IS NULL
BEGIN
    CREATE TABLE score.CondicionDia (
        Codigo     VARCHAR(30)  NOT NULL,   -- CEF_HOY, PDP_CREADA_HOY, PDP_VIGENTE, PAGO_HOY, EQUIVOCADO_HOY
        IdCartera  INT          NOT NULL,
        Fecha      DATE         NOT NULL,   -- día al que corresponde la foto
        DNI        VARCHAR(50)  COLLATE DATABASE_DEFAULT NULL,
        Telefono   VARCHAR(20)  COLLATE DATABASE_DEFAULT NULL   -- solo en condiciones por teléfono
    );
    CREATE CLUSTERED INDEX IX_CondicionDia ON score.CondicionDia (Codigo, IdCartera, Fecha, DNI, Telefono);
END
GO

IF OBJECT_ID('score.CondicionDiaEstado', 'U') IS NULL
BEGIN
    CREATE TABLE score.CondicionDiaEstado (
        Codigo       VARCHAR(30)  NOT NULL,
        IdCartera    INT          NOT NULL,
        Fecha        DATE         NOT NULL,
        CalculadoEn  DATETIME2(0) NOT NULL,
        Filas        INT          NULL,
        Ms           INT          NULL,      -- cuánto tardó leer SISCOB (para ver qué condición pesa)
        CONSTRAINT PK_CondicionDiaEstado PRIMARY KEY (Codigo, IdCartera)
    );
END
GO

/* Verificación (solo lectura): después de usar el generador, cuánto tarda cada condición por cartera. */
SELECT Codigo, IdCartera, Fecha, CalculadoEn, Filas, Ms
FROM score.CondicionDiaEstado
ORDER BY Ms DESC;
GO
