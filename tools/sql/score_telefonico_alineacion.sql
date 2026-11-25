/* =====================================================================================
   SCORE TELEFÓNICO · ALINEACIÓN DE ATRIBUTOS CON PRODUCCIÓN
   Fecha: 14/11/2026

   Problema: la copia local de SISCOB no siempre trae los valores vigentes de timbrado, semáforo
   (Prioridad), OSIPTEL y WhatsApp de producción (192.168.7.12). Hoy se corrige a mano, una cartera y
   una columna a la vez.

   Qué hace score.sp_AlinearAtributosTelefono (generaliza el script manual de Hardy):
     1. Trae de producción, con OPENQUERY, los teléfonos de los clientes activos (A/N) de las carteras del
        score (ControlCobranza.bl.EntidadCartera) o de las que se indiquen.
     2. Por cliente + teléfono y por columna: si producción tiene valores distintos para la misma clave,
        esa columna no se toca (conflicto). Igual que el script manual.
     3. Compara con la copia local y actualiza SOLO las 4 columnas que difieren. No toca fecha_actualizacion
        ni ninguna otra columna.
     4. Regla del script manual que se conserva: un valor NULL de producción no borra el valor local.
     5. Simulación por defecto. En modo real deja una fila por ejecución y el detalle de cada cambio
        (antes / después), que se conserva 30 días.

   Orden diario recomendado (antes de las 06:00):
     1. score.sp_AlinearAtributosTelefono
     2. score.sp_CargarTelefonoDia (ayer)
     3. score.sp_ArmarTelefonoUniverso
     4. score.sp_RegistrarAtributosTelefono   ← el historial del semáforo solo es confiable si 1 corrió antes
     5. score.sp_ArmarCaracteristicas (UNIVERSO) y score.sp_CalcularScore
   ===================================================================================== */

USE CobAuto;
GO
SET NOCOUNT ON;
GO

/* =====================================================================================
   BLOQUE 0 · Comprobaciones (solo lectura)
   ===================================================================================== */
-- 0.1 El servidor vinculado existe
SELECT name, data_source, is_linked FROM sys.servers WHERE name = N'192.168.7.12\BIZNESCOB';

-- 0.2 Tipos de las columnas en la copia local
SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH, IS_NULLABLE, COLLATION_NAME
FROM siscob.INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = 'dbo' AND TABLE_NAME = 'telefonos'
  AND COLUMN_NAME IN ('idcliente', 'telefono', 'timbra', 'prioridad', 'osiptel', 'wsp', 'idtelefono');

-- 0.3 Índices de siscob.dbo.telefonos (para estimar el costo del UPDATE)
SELECT i.name, i.type_desc, i.is_unique,
       STUFF((SELECT ', ' + c.name FROM siscob.sys.index_columns AS ic
              INNER JOIN siscob.sys.columns AS c ON c.object_id = ic.object_id AND c.column_id = ic.column_id
              WHERE ic.object_id = i.object_id AND ic.index_id = i.index_id AND ic.is_included_column = 0
              ORDER BY ic.key_ordinal FOR XML PATH('')), 1, 2, '') AS columnas
FROM siscob.sys.indexes AS i
WHERE i.object_id = OBJECT_ID('siscob.dbo.telefonos');
GO

/* =====================================================================================
   BLOQUE 1 · Bitácora
   ===================================================================================== */
IF OBJECT_ID('score.AlineacionAtributoEjecucion', 'U') IS NULL
CREATE TABLE score.AlineacionAtributoEjecucion (
    IdEjecucion        INT IDENTITY(1, 1) NOT NULL CONSTRAINT PK_score_AlineacionAtributoEjecucion PRIMARY KEY,
    FechaInicio        DATETIME2(0)   NOT NULL,
    FechaFin           DATETIME2(0)   NOT NULL,
    Carteras           VARCHAR(500)   NOT NULL,
    FilasProduccion    INT            NOT NULL,
    ClavesProduccion   INT            NOT NULL,
    ClavesConConflicto INT            NOT NULL,
    FilasActualizadas  INT            NOT NULL,
    CambiosTimbra      INT            NOT NULL,
    CambiosPrioridad   INT            NOT NULL,
    CambiosOsiptel     INT            NOT NULL,
    CambiosWsp         INT            NOT NULL,
    Usuario            NVARCHAR(128)  NOT NULL CONSTRAINT DF_score_AlineacionAtributoEjecucion_Usuario DEFAULT (ORIGINAL_LOGIN())
);
GO

IF OBJECT_ID('score.AlineacionAtributoDetalle', 'U') IS NULL
CREATE TABLE score.AlineacionAtributoDetalle (
    IdEjecucion      INT            NOT NULL,
    IdCartera        INT            NULL,
    IdCliente        INT            NOT NULL,
    Telefono         VARCHAR(30)    NOT NULL,
    Timbra_Antes     NVARCHAR(100)  NULL,
    Timbra_Despues   NVARCHAR(100)  NULL,
    Prioridad_Antes  NVARCHAR(100)  NULL,
    Prioridad_Despues NVARCHAR(100) NULL,
    Osiptel_Antes    NVARCHAR(100)  NULL,
    Osiptel_Despues  NVARCHAR(100)  NULL,
    Wsp_Antes        NVARCHAR(100)  NULL,
    Wsp_Despues      NVARCHAR(100)  NULL
);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_AlineacionAtributoDetalle' AND object_id = OBJECT_ID('score.AlineacionAtributoDetalle'))
    CREATE CLUSTERED INDEX IX_AlineacionAtributoDetalle ON score.AlineacionAtributoDetalle (IdEjecucion, IdCliente);
GO

/* =====================================================================================
   BLOQUE 2 · Procedimiento
   ===================================================================================== */
CREATE OR ALTER PROCEDURE score.sp_AlinearAtributosTelefono
    @Carteras VARCHAR(500) = NULL,   -- '112,132' · NULL = todas las de bl.EntidadCartera
    @Simular  BIT = 1
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;
    SET LOCK_TIMEOUT 120000;         -- si la tabla está bloqueada más de 2 minutos, falla en vez de esperar

    DECLARE @Inicio DATETIME2(0) = SYSDATETIME();

    IF @Carteras IS NOT NULL AND (LEN(@Carteras) = 0 OR @Carteras LIKE '%[^0-9,]%')
        THROW 50401, '@Carteras debe ser una lista de números separados por coma, por ejemplo ''112,132''.', 1;

    IF @Carteras IS NULL
        SELECT @Carteras = STUFF((SELECT ',' + CAST(IdCartera AS VARCHAR(10))
                                  FROM ControlCobranza.bl.EntidadCartera
                                  GROUP BY IdCartera ORDER BY IdCartera
                                  FOR XML PATH('')), 1, 1, '');
    IF @Carteras IS NULL
        THROW 50402, 'No hay carteras en ControlCobranza.bl.EntidadCartera.', 1;

    /* 1. Producción. La clave conserva los tipos de la copia local; los atributos se traen como texto,
          como en el script manual, para comparar sin depender del tipo de cada columna. */
    SELECT TOP 0
           CAST(NULL AS INT) AS IdCartera, t.idcliente AS IDCLIENTE, t.telefono AS TELEFONO,
           CAST(NULL AS NVARCHAR(100)) COLLATE DATABASE_DEFAULT AS TIMBRA,
           CAST(NULL AS NVARCHAR(100)) COLLATE DATABASE_DEFAULT AS PRIORIDAD,
           CAST(NULL AS NVARCHAR(100)) COLLATE DATABASE_DEFAULT AS OSIPTEL,
           CAST(NULL AS NVARCHAR(100)) COLLATE DATABASE_DEFAULT AS WSP
    INTO #prod
    FROM siscob.dbo.telefonos AS t;

    DECLARE @remoto NVARCHAR(4000) =
        N'SELECT C.IDCARTERA, T.IDCLIENTE, T.TELEFONO, T.TIMBRA, T.PRIORIDAD, T.OSIPTEL, T.WSP '
      + N'FROM SISCOB.dbo.TELEFONOS T INNER JOIN SISCOB.dbo.CLIENTE C ON T.IDCLIENTE = C.IDCLIENTE '
      + N'WHERE C.IDCARTERA IN (' + CONVERT(NVARCHAR(500), @Carteras) + N') AND C.ESTADO IN (''A'', ''N'')';

    DECLARE @sql NVARCHAR(MAX) =
        N'INSERT INTO #prod (IdCartera, IDCLIENTE, TELEFONO, TIMBRA, PRIORIDAD, OSIPTEL, WSP) '
      + N'SELECT IDCARTERA, IDCLIENTE, TELEFONO, '
      + N'CONVERT(NVARCHAR(100), TIMBRA), CONVERT(NVARCHAR(100), PRIORIDAD), '
      + N'CONVERT(NVARCHAR(100), OSIPTEL), CONVERT(NVARCHAR(100), WSP) '
      + N'FROM OPENQUERY([192.168.7.12\BIZNESCOB], ''' + REPLACE(@remoto, N'''', N'''''') + N''')';

    EXEC sys.sp_executesql @sql;

    DECLARE @FilasProd INT = (SELECT COUNT(*) FROM #prod);

    /* 2. Un valor por clave y columna; si producción se contradice, esa columna no se toca */
    SELECT IDCLIENTE, TELEFONO, MAX(IdCartera) AS IdCartera,
           CASE WHEN COUNT(DISTINCT TIMBRA) = 1    THEN MAX(TIMBRA)    END AS TIMBRA,
           CASE WHEN COUNT(DISTINCT PRIORIDAD) = 1 THEN MAX(PRIORIDAD) END AS PRIORIDAD,
           CASE WHEN COUNT(DISTINCT OSIPTEL) = 1   THEN MAX(OSIPTEL)   END AS OSIPTEL,
           CASE WHEN COUNT(DISTINCT WSP) = 1       THEN MAX(WSP)       END AS WSP,
           CASE WHEN COUNT(DISTINCT TIMBRA) > 1 OR COUNT(DISTINCT PRIORIDAD) > 1
                  OR COUNT(DISTINCT OSIPTEL) > 1 OR COUNT(DISTINCT WSP) > 1 THEN 1 ELSE 0 END AS Conflicto
    INTO #fin
    FROM #prod
    GROUP BY IDCLIENTE, TELEFONO;

    CREATE CLUSTERED INDEX IX_fin ON #fin (IDCLIENTE, TELEFONO);

    DECLARE @Claves INT = (SELECT COUNT(*) FROM #fin),
            @Conflictos INT = ISNULL((SELECT SUM(Conflicto) FROM #fin), 0);

    /* 3. Simulación: qué cambiaría */
    IF @Simular = 1
    BEGIN
        SELECT f.IdCartera, a.idcliente, a.telefono,
               CONVERT(NVARCHAR(100), a.timbra)    AS timbra_local,    f.TIMBRA    AS timbra_produccion,    d.dT,
               CONVERT(NVARCHAR(100), a.prioridad) AS prioridad_local, f.PRIORIDAD AS prioridad_produccion, d.dP,
               CONVERT(NVARCHAR(100), a.osiptel)   AS osiptel_local,   f.OSIPTEL   AS osiptel_produccion,   d.dO,
               CONVERT(NVARCHAR(100), a.wsp)       AS wsp_local,       f.WSP       AS wsp_produccion,       d.dW
        INTO #dif
        FROM siscob.dbo.telefonos AS a WITH (NOLOCK)
        INNER JOIN #fin AS f ON f.IDCLIENTE = a.idcliente AND f.TELEFONO = a.telefono
        CROSS APPLY (SELECT
            CASE WHEN f.TIMBRA IS NOT NULL AND (a.timbra IS NULL
                 OR CONVERT(NVARCHAR(100), a.timbra) COLLATE DATABASE_DEFAULT <> f.TIMBRA) THEN 1 ELSE 0 END AS dT,
            CASE WHEN f.PRIORIDAD IS NOT NULL AND (a.prioridad IS NULL
                 OR CONVERT(NVARCHAR(100), a.prioridad) COLLATE DATABASE_DEFAULT <> f.PRIORIDAD) THEN 1 ELSE 0 END AS dP,
            CASE WHEN f.OSIPTEL IS NOT NULL AND (a.osiptel IS NULL
                 OR CONVERT(NVARCHAR(100), a.osiptel) COLLATE DATABASE_DEFAULT <> f.OSIPTEL) THEN 1 ELSE 0 END AS dO,
            CASE WHEN f.WSP IS NOT NULL AND (a.wsp IS NULL
                 OR CONVERT(NVARCHAR(100), a.wsp) COLLATE DATABASE_DEFAULT <> f.WSP) THEN 1 ELSE 0 END AS dW
        ) AS d
        WHERE d.dT + d.dP + d.dO + d.dW > 0;

        SELECT 'SIMULACION' AS Modo, @Carteras AS Carteras, @FilasProd AS filas_produccion,
               @Claves AS claves_produccion, @Conflictos AS claves_con_conflicto,
               (SELECT COUNT(*) FROM #dif) AS filas_que_cambiarian,
               ISNULL((SELECT SUM(dT) FROM #dif), 0) AS cambios_timbra, ISNULL((SELECT SUM(dP) FROM #dif), 0) AS cambios_prioridad,
               ISNULL((SELECT SUM(dO) FROM #dif), 0) AS cambios_osiptel, ISNULL((SELECT SUM(dW) FROM #dif), 0) AS cambios_wsp;

        SELECT IdCartera, COUNT(*) AS filas, SUM(dT) AS timbra, SUM(dP) AS prioridad, SUM(dO) AS osiptel, SUM(dW) AS wsp
        FROM #dif GROUP BY IdCartera ORDER BY IdCartera;

        -- Qué valores cambian (los 40 pares más frecuentes)
        SELECT TOP 40 x.columna, x.valor_local, x.valor_produccion, COUNT(*) AS filas
        FROM #dif
        CROSS APPLY (VALUES
            ('TIMBRA', timbra_local, timbra_produccion, dT), ('PRIORIDAD', prioridad_local, prioridad_produccion, dP),
            ('OSIPTEL', osiptel_local, osiptel_produccion, dO), ('WSP', wsp_local, wsp_produccion, dW)
        ) AS x (columna, valor_local, valor_produccion, cambia)
        WHERE x.cambia = 1
        GROUP BY x.columna, x.valor_local, x.valor_produccion
        ORDER BY filas DESC;
        RETURN;
    END;

    /* 4. Real: actualiza y registra en la misma transacción */
    CREATE TABLE #cambios (
        IdCartera INT NULL, IdCliente INT NOT NULL, Telefono VARCHAR(30) NOT NULL,
        Timbra_Antes NVARCHAR(100), Timbra_Despues NVARCHAR(100),
        Prioridad_Antes NVARCHAR(100), Prioridad_Despues NVARCHAR(100),
        Osiptel_Antes NVARCHAR(100), Osiptel_Despues NVARCHAR(100),
        Wsp_Antes NVARCHAR(100), Wsp_Despues NVARCHAR(100));

    BEGIN TRAN;
        UPDATE a SET
            timbra    = CASE WHEN d.dT = 1 THEN f.TIMBRA    ELSE a.timbra    END,
            prioridad = CASE WHEN d.dP = 1 THEN f.PRIORIDAD ELSE a.prioridad END,
            osiptel   = CASE WHEN d.dO = 1 THEN f.OSIPTEL   ELSE a.osiptel   END,
            wsp       = CASE WHEN d.dW = 1 THEN f.WSP       ELSE a.wsp       END
        OUTPUT f.IdCartera, inserted.idcliente,
               COALESCE(CONVERT(VARCHAR(30), TRY_CONVERT(BIGINT, inserted.telefono)), CONVERT(VARCHAR(30), inserted.telefono)),
               CONVERT(NVARCHAR(100), deleted.timbra),    CONVERT(NVARCHAR(100), inserted.timbra),
               CONVERT(NVARCHAR(100), deleted.prioridad), CONVERT(NVARCHAR(100), inserted.prioridad),
               CONVERT(NVARCHAR(100), deleted.osiptel),   CONVERT(NVARCHAR(100), inserted.osiptel),
               CONVERT(NVARCHAR(100), deleted.wsp),       CONVERT(NVARCHAR(100), inserted.wsp)
        INTO #cambios
        FROM siscob.dbo.telefonos AS a
        INNER JOIN #fin AS f ON f.IDCLIENTE = a.idcliente AND f.TELEFONO = a.telefono
        CROSS APPLY (SELECT
            CASE WHEN f.TIMBRA IS NOT NULL AND (a.timbra IS NULL
                 OR CONVERT(NVARCHAR(100), a.timbra) COLLATE DATABASE_DEFAULT <> f.TIMBRA) THEN 1 ELSE 0 END AS dT,
            CASE WHEN f.PRIORIDAD IS NOT NULL AND (a.prioridad IS NULL
                 OR CONVERT(NVARCHAR(100), a.prioridad) COLLATE DATABASE_DEFAULT <> f.PRIORIDAD) THEN 1 ELSE 0 END AS dP,
            CASE WHEN f.OSIPTEL IS NOT NULL AND (a.osiptel IS NULL
                 OR CONVERT(NVARCHAR(100), a.osiptel) COLLATE DATABASE_DEFAULT <> f.OSIPTEL) THEN 1 ELSE 0 END AS dO,
            CASE WHEN f.WSP IS NOT NULL AND (a.wsp IS NULL
                 OR CONVERT(NVARCHAR(100), a.wsp) COLLATE DATABASE_DEFAULT <> f.WSP) THEN 1 ELSE 0 END AS dW
        ) AS d
        WHERE d.dT + d.dP + d.dO + d.dW > 0;

        INSERT INTO score.AlineacionAtributoEjecucion (
            FechaInicio, FechaFin, Carteras, FilasProduccion, ClavesProduccion, ClavesConConflicto,
            FilasActualizadas, CambiosTimbra, CambiosPrioridad, CambiosOsiptel, CambiosWsp)
        SELECT @Inicio, SYSDATETIME(), @Carteras, @FilasProd, @Claves, ISNULL(@Conflictos, 0),
               COUNT(*),
               -- ISNULL: sin nada que cambiar, SUM devuelve NULL y la bitácora no lo acepta (falla del 14/11)
               ISNULL(SUM(CASE WHEN ISNULL(Timbra_Antes, N'¬') <> ISNULL(Timbra_Despues, N'¬') THEN 1 ELSE 0 END), 0),
               ISNULL(SUM(CASE WHEN ISNULL(Prioridad_Antes, N'¬') <> ISNULL(Prioridad_Despues, N'¬') THEN 1 ELSE 0 END), 0),
               ISNULL(SUM(CASE WHEN ISNULL(Osiptel_Antes, N'¬') <> ISNULL(Osiptel_Despues, N'¬') THEN 1 ELSE 0 END), 0),
               ISNULL(SUM(CASE WHEN ISNULL(Wsp_Antes, N'¬') <> ISNULL(Wsp_Despues, N'¬') THEN 1 ELSE 0 END), 0)
        FROM #cambios;

        DECLARE @IdEjecucion INT = SCOPE_IDENTITY();

        INSERT INTO score.AlineacionAtributoDetalle (
            IdEjecucion, IdCartera, IdCliente, Telefono, Timbra_Antes, Timbra_Despues, Prioridad_Antes, Prioridad_Despues,
            Osiptel_Antes, Osiptel_Despues, Wsp_Antes, Wsp_Despues)
        SELECT @IdEjecucion, IdCartera, IdCliente, Telefono, Timbra_Antes, Timbra_Despues, Prioridad_Antes, Prioridad_Despues,
               Osiptel_Antes, Osiptel_Despues, Wsp_Antes, Wsp_Despues
        FROM #cambios;

        -- El detalle se conserva 30 días
        DELETE dd FROM score.AlineacionAtributoDetalle AS dd
        INNER JOIN score.AlineacionAtributoEjecucion AS e ON e.IdEjecucion = dd.IdEjecucion
        WHERE e.FechaInicio < DATEADD(DAY, -30, @Inicio);
    COMMIT;

    SELECT * FROM score.AlineacionAtributoEjecucion WHERE IdEjecucion = @IdEjecucion;
END;
GO

/* =====================================================================================
   BLOQUE 3 · Simulaciones (no escriben)
   ===================================================================================== */
-- 3.1 Una cartera, para comparar con el script manual
EXEC CobAuto.score.sp_AlinearAtributosTelefono @Carteras = '112', @Simular = 1;
GO
-- 3.2 Todas las carteras del score
EXEC CobAuto.score.sp_AlinearAtributosTelefono @Simular = 1;
GO

/* =====================================================================================
   BLOQUE 4 · Ejecución real (comentado; revisar antes la simulación)
   ===================================================================================== */
/*
EXEC CobAuto.score.sp_AlinearAtributosTelefono @Simular = 0;

-- Después de alinear, rehacer lo que depende de los atributos:
EXEC CobAuto.score.sp_ArmarTelefonoUniverso @Simular = 0;
EXEC CobAuto.score.sp_RegistrarAtributosTelefono;
EXEC CobAuto.score.sp_ArmarEntrenamiento @Desde = '2026-08-17', @Hasta = '2026-11-03';
-- y volver a correr: python tools/score_telefonico_calibrar.py
*/
GO
