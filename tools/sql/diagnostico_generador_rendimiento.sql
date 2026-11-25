/* =====================================================================================
   Generador de bases · diagnóstico de rendimiento y de campos para estrategias (SOLO LECTURA)
   Base: CobAuto · esquema score · 20/11/2026

   Para qué:
     1. Medir con datos reales cuánto cuesta lo que hoy se repite en CADA clic de la pantalla:
        leer toda la cartera desde score.vw_BaseTrabajo (6 tablas unidas) y copiarla a tempdb.
     2. Ver si el servidor admite índices columnstore (la propuesta de optimización los usa).
     3. Sacar los valores REALES de los campos que usarían las estrategias (CEF del mes, PDP caída,
        NOC puro, etc.), para armarlas sin inventar códigos.

   No crea tablas permanentes ni modifica datos: solo usa tablas temporales (#).
   Cambia @Cartera para medir otra cartera (por defecto la 144, la más grande).
   Ejecutar completo y guardar el resultado en tools/salidas/diagnostico_generador_rendimiento.txt
   ===================================================================================== */
USE CobAuto;
GO
SET NOCOUNT ON;

DECLARE @Cartera INT = 144;
DECLARE @t0 DATETIME2(3), @ms INT;

/* ---- A. Versión de SQL Server (columnstore no agrupado: 2016 SP1 o superior, cualquier edición) ---- */
SELECT 'A' AS Bloque, @@VERSION AS Version,
       SERVERPROPERTY('ProductVersion') AS ProductVersion, SERVERPROPERTY('Edition') AS Edicion,
       (SELECT compatibility_level FROM sys.databases WHERE name = DB_NAME()) AS NivelCompatibilidad;

/* ---- B. Tamaño de lo que lee cada clic, por cartera ---- */
SELECT 'B' AS Bloque, IdCartera, COUNT(*) AS Telefonos, COUNT(DISTINCT DNI) AS Clientes
FROM score.vw_BaseTrabajo
GROUP BY IdCartera
ORDER BY Telefonos DESC;

/* ---- C. Costo de lo que hoy se repite en cada clic (cartera @Cartera) ---- */
-- C1: leer la vista y copiar toda la cartera a tempdb (lo que hace sql_materializar)
IF OBJECT_ID('tempdb..#m') IS NOT NULL DROP TABLE #m;
SET @t0 = SYSDATETIME();
SELECT t.* INTO #m FROM score.vw_BaseTrabajo AS t WHERE t.IdCartera = @Cartera;
CREATE CLUSTERED INDEX IX_m ON #m (DNI);
SET @ms = DATEDIFF(MILLISECOND, @t0, SYSDATETIME());
SELECT 'C1' AS Bloque, @Cartera AS Cartera, (SELECT COUNT(*) FROM #m) AS Filas,
       @ms AS Ms_leer_vista_y_copiar_a_tempdb;

-- C2: el mismo conteo leyendo la copia ya armada (lo que costaría si la cartera estuviera guardada)
SET @t0 = SYSDATETIME();
SELECT 'C2' AS Bloque, COUNT(*) AS Telefonos, COUNT(DISTINCT DNI) AS Clientes,
       SUM(CASE WHEN MgContacto = 'CEF' THEN 1 ELSE 0 END) AS TelConClienteCefMes
FROM #m WHERE Descartado = 0;
SELECT 'C2' AS Bloque, DATEDIFF(MILLISECOND, @t0, SYSDATETIME()) AS Ms_contar_sobre_copia;

-- C3: un conteo tipo "segmentador" (por valor de 6 campos) sobre la copia
SET @t0 = SYSDATETIME();
SELECT COUNT(*) AS N FROM (
    SELECT MgContacto, EstadoPdp, EstadoSeguimiento, MgTel6m, Osiptel, Timbra FROM #m WHERE Descartado = 0
) AS x GROUP BY GROUPING SETS ((MgContacto), (EstadoPdp), (EstadoSeguimiento), (MgTel6m), (Osiptel), (Timbra));
SELECT 'C3' AS Bloque, DATEDIFF(MILLISECOND, @t0, SYSDATETIME()) AS Ms_segmentadores_sobre_copia;

-- C4: condiciones del día (lectura en vivo de SISCOB, hoy)
SET @t0 = SYSDATETIME();
SELECT COUNT(DISTINCT g.IdCliente) AS ClientesGestionadosHoy
FROM siscob.dbo.gestion AS g WITH (NOLOCK)
WHERE g.Fecha >= CAST(GETDATE() AS DATE) AND g.idCartera = @Cartera;
SELECT 'C4' AS Bloque, DATEDIFF(MILLISECOND, @t0, SYSDATETIME()) AS Ms_gestion_de_hoy;

-- C5: campos por cuenta (score.vw_DatoCliente) de la cartera
SET @t0 = SYSDATETIME();
SELECT COUNT(*) AS Filas, COUNT(DISTINCT Campo) AS Campos FROM score.vw_DatoCliente WHERE IdCartera = @Cartera;
SELECT 'C5' AS Bloque, DATEDIFF(MILLISECOND, @t0, SYSDATETIME()) AS Ms_leer_datos_por_cuenta;

/* ---- D. Tamaño e índices de las tablas que une la vista ---- */
SELECT 'D' AS Bloque, s.name + '.' + o.name AS Tabla, SUM(p.rows) AS Filas,
       CAST(SUM(a.total_pages) * 8 / 1024.0 AS DECIMAL(12, 1)) AS MB
FROM sys.objects AS o
JOIN sys.schemas AS s ON s.schema_id = o.schema_id
JOIN sys.partitions AS p ON p.object_id = o.object_id AND p.index_id IN (0, 1)
JOIN sys.allocation_units AS a ON a.container_id = p.partition_id
WHERE s.name = 'score' AND o.type = 'U'
  AND o.name IN ('TelefonoScore', 'TelefonoUniverso', 'BaseTrabajoCliente', 'BaseTrabajoDato',
                 'GestionCliente', 'GestionTelefono', 'Caracteristicas', 'SegmentoCliente')
GROUP BY s.name, o.name
ORDER BY Filas DESC;

SELECT 'D' AS Bloque, OBJECT_NAME(i.object_id) AS Tabla, i.name AS Indice, i.type_desc AS Tipo,
       ic.key_ordinal AS Orden, c.name AS Columna, ic.is_included_column AS Incluida
FROM sys.indexes AS i
JOIN sys.index_columns AS ic ON ic.object_id = i.object_id AND ic.index_id = i.index_id
JOIN sys.columns AS c ON c.object_id = ic.object_id AND c.column_id = ic.column_id
WHERE i.object_id IN (OBJECT_ID('score.TelefonoScore'), OBJECT_ID('score.TelefonoUniverso'),
                      OBJECT_ID('score.BaseTrabajoCliente'), OBJECT_ID('score.BaseTrabajoDato'),
                      OBJECT_ID('score.GestionCliente'), OBJECT_ID('score.GestionTelefono'),
                      OBJECT_ID('score.Caracteristicas'))
ORDER BY Tabla, Indice, Incluida, Orden;

/* ---- E. Valores reales de los campos de las estrategias (cartera @Cartera, sin descartados) ---- */
SELECT 'E' AS Bloque, x.Campo, x.Valor, x.Telefonos, x.Clientes
FROM (
    SELECT CASE WHEN GROUPING(MgContacto) = 0 THEN 'MgContacto (mejor contacto del cliente, mes)'
                WHEN GROUPING(UgContacto) = 0 THEN 'UgContacto (último contacto del cliente, mes)'
                WHEN GROUPING(EstadoPdp) = 0 THEN 'EstadoPdp'
                WHEN GROUPING(EstadoSeguimiento) = 0 THEN 'EstadoSeguimiento'
                WHEN GROUPING(UltCefTramo) = 0 THEN 'UltCefTramo (último CEF del cliente)'
                WHEN GROUPING(MgTelMes) = 0 THEN 'MgTelMes (mejor resultado del teléfono, mes)'
                WHEN GROUPING(MgTel6m) = 0 THEN 'MgTel6m (mejor resultado del teléfono, 6 meses)'
                WHEN GROUPING(UgTel6m) = 0 THEN 'UgTel6m (último resultado del teléfono, 6 meses)'
                WHEN GROUPING(Relacion) = 0 THEN 'Relacion (titular, dependiente...)'
                WHEN GROUPING(FuenteDato) = 0 THEN 'FuenteDato (tipo de base)'
                WHEN GROUPING(OrigenDato) = 0 THEN 'OrigenDato'
                WHEN GROUPING(Osiptel) = 0 THEN 'Osiptel'
                WHEN GROUPING(Timbra) = 0 THEN 'Timbra'
                WHEN GROUPING(PrioridadColor) = 0 THEN 'PrioridadColor (semáforo SISCOB)'
                WHEN GROUPING(GestionesTelMesTramo) = 0 THEN 'Gestiones del teléfono en el mes (0 / 1+)'
                WHEN GROUPING(CoberturaTramo) = 0 THEN 'Cobertura del cliente en el mes (0 / 1+)' END AS Campo,
           ISNULL(COALESCE(
               CASE WHEN GROUPING(MgContacto) = 0 THEN MgContacto END,
               CASE WHEN GROUPING(UgContacto) = 0 THEN UgContacto END,
               CASE WHEN GROUPING(EstadoPdp) = 0 THEN EstadoPdp END,
               CASE WHEN GROUPING(EstadoSeguimiento) = 0 THEN EstadoSeguimiento END,
               CASE WHEN GROUPING(UltCefTramo) = 0 THEN UltCefTramo END,
               CASE WHEN GROUPING(MgTelMes) = 0 THEN MgTelMes END,
               CASE WHEN GROUPING(MgTel6m) = 0 THEN MgTel6m END,
               CASE WHEN GROUPING(UgTel6m) = 0 THEN UgTel6m END,
               CASE WHEN GROUPING(Relacion) = 0 THEN Relacion END,
               CASE WHEN GROUPING(FuenteDato) = 0 THEN FuenteDato END,
               CASE WHEN GROUPING(OrigenDato) = 0 THEN OrigenDato END,
               CASE WHEN GROUPING(Osiptel) = 0 THEN Osiptel END,
               CASE WHEN GROUPING(Timbra) = 0 THEN Timbra END,
               CASE WHEN GROUPING(PrioridadColor) = 0 THEN PrioridadColor END,
               CASE WHEN GROUPING(GestionesTelMesTramo) = 0 THEN GestionesTelMesTramo END,
               CASE WHEN GROUPING(CoberturaTramo) = 0 THEN CoberturaTramo END), N'(vacío)') AS Valor,
           COUNT(*) AS Telefonos, COUNT(DISTINCT DNI) AS Clientes
    FROM (
        SELECT DNI,
               CONVERT(NVARCHAR(200), MgContacto) AS MgContacto, CONVERT(NVARCHAR(200), UgContacto) AS UgContacto,
               CONVERT(NVARCHAR(200), EstadoPdp) AS EstadoPdp, CONVERT(NVARCHAR(200), EstadoSeguimiento) AS EstadoSeguimiento,
               CONVERT(NVARCHAR(200), UltCefTramo) AS UltCefTramo,
               CONVERT(NVARCHAR(200), MgTelMes) AS MgTelMes, CONVERT(NVARCHAR(200), MgTel6m) AS MgTel6m,
               CONVERT(NVARCHAR(200), UgTel6m) AS UgTel6m, CONVERT(NVARCHAR(200), Relacion) AS Relacion,
               CONVERT(NVARCHAR(200), FuenteDato) AS FuenteDato, CONVERT(NVARCHAR(200), OrigenDato) AS OrigenDato,
               CONVERT(NVARCHAR(200), Osiptel) AS Osiptel, CONVERT(NVARCHAR(200), Timbra) AS Timbra,
               CONVERT(NVARCHAR(200), PrioridadColor) AS PrioridadColor,
               CONVERT(NVARCHAR(200), CASE WHEN ISNULL(GestionesTelMes, 0) = 0 THEN '0' ELSE '1+' END) AS GestionesTelMesTramo,
               CONVERT(NVARCHAR(200), CASE WHEN ISNULL(TRY_CONVERT(INT, Cobertura), 0) = 0 THEN '0' ELSE '1+' END) AS CoberturaTramo
        FROM #m WHERE Descartado = 0
    ) AS b
    GROUP BY GROUPING SETS ((MgContacto), (UgContacto), (EstadoPdp), (EstadoSeguimiento), (UltCefTramo),
                            (MgTelMes), (MgTel6m), (UgTel6m), (Relacion), (FuenteDato), (OrigenDato),
                            (Osiptel), (Timbra), (PrioridadColor), (GestionesTelMesTramo), (CoberturaTramo))
) AS x
ORDER BY x.Campo, x.Telefonos DESC;

/* ---- F. Resultados de teléfono posibles (orden: menor = mejor) y cuáles son CEF ---- */
SELECT 'F' AS Bloque, * FROM score.ResultadoTelefono ORDER BY Orden;

/* ---- G. Campos activos del catálogo (código, etiqueta, grupo, columna) para mapear las estrategias ---- */
SELECT 'G' AS Bloque, Codigo, Etiqueta, Grupo, TipoFiltro, Origen, ColumnaOrigen, TodasLasCarteras
FROM score.Campo
WHERE Activo = 1
ORDER BY Grupo, Codigo;

DROP TABLE #m;
GO
