"""Rendimiento del score telefónico (vista "Rendimiento del score", fase 13, 24/11/2026).

Lee score.RendimientoDia: un resumen por día, cartera, canal de la base, tramo, orden del teléfono en el cliente y
atributos (OSIPTEL, timbrado, WhatsApp, origen, fuente, color). Unidad: teléfono-día, es decir, el tramo que el
teléfono tenía ese día contra lo que pasó ese día. Solo mide: no cambia ninguna regla del score.

Pestañas:
- CARTERA: todos los teléfonos con score de la cartera (marcados o no).
- BASES: solo los teléfonos que salieron ese día en una base del generador (canal PRED, IVR o SMS).
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from app.core.db_siscob import engine_siscob
from app.services import generador_bases_service as generador

DIAS_PERMITIDOS = (7, 14, 30)
UNIVERSOS = ("CARTERA", "BASES")
# Dimensiones que se pueden filtrar y desglosar (columna de score.RendimientoDia)
DIMENSIONES = ("Tramo", "Orden", "Canal", "Osiptel", "Timbra", "Whatsapp", "Origen", "Fuente", "Color")
DESGLOSES = ("Orden", "Canal", "Osiptel", "Timbra", "Whatsapp", "Origen", "Fuente", "Color", "Fecha")
MEDIDAS = ("Telefonos", "Marcados", "Intentos", "IntentosHumano", "IntentosMaquina", "Cef", "ConCefPaleta",
           "R_Cef", "R_Tercero", "R_ContestaSinId", "R_NoContesta", "R_Buzon", "R_Apagado", "R_NoExiste",
           "R_Equivocado", "R_Otro", "R_SinResultado", "Int_Manana", "Int_Medio", "Int_Tarde", "Int_Noche",
           "Cef_Manana", "Cef_Medio", "Cef_Tarde", "Cef_Noche")
MAX_VALORES_FILTRO = 50


class ConsultaInvalida(ValueError):
    pass


def _filtros_validos(filtros: Optional[Dict[str, Any]]) -> Dict[str, List[str]]:
    salida: Dict[str, List[str]] = {}
    for dim, valores in (filtros or {}).items():
        if dim not in DIMENSIONES:
            raise ConsultaInvalida(f"Filtro no permitido: {dim}")
        if valores is None:
            continue
        if not isinstance(valores, list) or len(valores) > MAX_VALORES_FILTRO:
            raise ConsultaInvalida(f"Valores no válidos para {dim}")
        limpios = [str(v)[:20] for v in valores if v is not None and str(v).strip() != ""]
        if limpios:
            salida[dim] = limpios
    return salida


def sql_rendimiento(carteras: List[int], universo: str, filtros: Dict[str, List[str]]) -> tuple[str, Dict[str, Any]]:
    """Una lectura con GROUPING SETS: por tramo y por (desglose, tramo). Las columnas de dimensión nunca son NULL
    en la tabla, así que la que vale NULL en una fila es la que no se agrupó."""
    en = ", ".join(str(int(c)) for c in carteras)
    donde = [f"IdCartera IN ({en})", "Fecha BETWEEN :desde AND :hasta"]
    params: Dict[str, Any] = {}
    if universo == "BASES":
        donde.append("Canal <> 'SIN BASE'")
    for i, (dim, valores) in enumerate(sorted(filtros.items())):
        marcas = []
        for j, v in enumerate(valores):
            params[f"f{i}_{j}"] = v
            marcas.append(f":f{i}_{j}")
        donde.append(f"{dim} IN ({', '.join(marcas)})")
    sumas = ", ".join(f"SUM(CAST({m} AS BIGINT)) AS {m}" for m in MEDIDAS)
    conjuntos = ", ".join(["(Tramo)"] + [f"({d}, Tramo)" for d in DESGLOSES])
    etiqueta = " ".join(f"WHEN GROUPING({d}) = 0 THEN '{d}'" for d in DESGLOSES)
    valor = ", ".join([f"{d}" for d in DESGLOSES if d != "Fecha"] + ["CONVERT(CHAR(10), Fecha, 23)"])
    sql = f"""
        SELECT CASE {etiqueta} ELSE 'Total' END AS Dimension,
               COALESCE({valor}) AS Valor, Tramo, COUNT(DISTINCT Fecha) AS Dias, {sumas}
        FROM score.RendimientoDia
        WHERE {' AND '.join(donde)}
        GROUP BY GROUPING SETS ({conjuntos})
    """
    return sql, params


def _a_fecha(v):
    if v is None or isinstance(v, date):
        return v
    return date.fromisoformat(str(v)[:10])


def _periodo(conn, carteras: List[int], dias: int):
    """(desde, hasta, desde_pedido): hasta = último día armado; desde = primer día con datos dentro de los N días."""
    en = ", ".join(str(int(c)) for c in carteras)
    hasta = _a_fecha(conn.execute(text(f"SELECT MAX(Fecha) FROM score.RendimientoDia WHERE IdCartera IN ({en})")).scalar())
    if hasta is None:
        return None
    desde_pedido = hasta - timedelta(days=dias - 1)
    primero = _a_fecha(conn.execute(text(f"SELECT MIN(Fecha) FROM score.RendimientoDia WHERE IdCartera IN ({en}) "
                                         "AND Fecha BETWEEN :d AND :h"), {"d": desde_pedido, "h": hasta}).scalar())
    return primero or desde_pedido, hasta, desde_pedido


def _validar(dias: int, universo: str, filtros) -> tuple:
    if dias not in DIAS_PERMITIDOS:
        raise ConsultaInvalida("El periodo debe ser 7, 14 o 30 días.")
    universo = (universo or "CARTERA").upper()
    if universo not in UNIVERSOS:
        raise ConsultaInvalida("Universo no válido.")
    return universo, _filtros_validos(filtros)


def rendimiento(idcartera: int, dias: int, universo: str, filtros: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    universo, filtros_ok = _validar(dias, universo, filtros)

    with engine_siscob.connect() as conn:
        if conn.execute(text("SELECT OBJECT_ID('score.RendimientoDia')")).scalar() is None:
            return {"sin_datos": True, "mensaje": "Falta ejecutar la fase 13 (score.RendimientoDia)."}
        carteras = generador.carteras_de(conn, idcartera)
        en = ", ".join(str(int(c)) for c in carteras)
        periodo = _periodo(conn, carteras, dias)
        if periodo is None:
            return {"sin_datos": True, "carteras": carteras,
                    "mensaje": "La cartera todavía no tiene días armados. Se arman al cargar el historial."}
        desde, hasta, desde_pedido = periodo
        # Calidad de cada día cargado (para avisar días sin máquina o sin centralita)
        control = [
            {"fecha": (f["Fecha"].isoformat() if hasattr(f["Fecha"], "isoformat") else str(f["Fecha"])[:10]),
             "humano": int(f["EventosHumano"]), "maquina": int(f["EventosMaquina"]),
             "centralita": int(f["EventosCentralita"])}
            for f in conn.execute(text(
                "SELECT Fecha, EventosHumano, EventosMaquina, EventosCentralita FROM score.TelefonoDiaControl "
                "WHERE Fecha BETWEEN :d AND :h ORDER BY Fecha"), {"d": desde, "h": hasta}).mappings()
        ]
        sql, params = sql_rendimiento(carteras, universo, filtros_ok)
        filas = conn.execute(text(sql), {**params, "desde": desde, "hasta": hasta}).mappings().all()
        # Valores disponibles para los filtros: del periodo, sin filtros, para no perder opciones al filtrar
        valores_sql = " UNION ALL ".join(
            f"SELECT DISTINCT '{d}' AS Dimension, CONVERT(VARCHAR(20), {d}) AS Valor FROM score.RendimientoDia "
            f"WHERE IdCartera IN ({en}) AND Fecha BETWEEN :desde AND :hasta" for d in DIMENSIONES)
        valores: Dict[str, List[str]] = {d: [] for d in DIMENSIONES}
        for v in conn.execute(text(valores_sql), {"desde": desde, "hasta": hasta}).mappings():
            valores[v["Dimension"]].append(v["Valor"])

    datos = [{k: (int(v) if k in MEDIDAS or k == "Dias" else v) for k, v in dict(f).items()} for f in filas]
    for lista in valores.values():
        lista.sort()
    return {
        "sin_datos": not datos,
        "idcartera": idcartera, "carteras": carteras, "universo": universo, "dias": dias,
        "desde": desde.isoformat(), "hasta": hasta.isoformat(), "desde_pedido": desde_pedido.isoformat(),
        "control": control,
        "filtros": filtros_ok, "valores": valores, "filas": datos,
    }


# ---------------------------------------------------------------------------------------------------------------
# Cobertura del periodo (24/11/2026): de los teléfonos que estuvieron en un tramo algún día del periodo, cuántos
# recibieron al menos una llamada en un día en que estaban en ese tramo. Un teléfono que pasó por A y por B cuenta
# en los dos. Solo teléfonos con score (SIN SCORE no tiene tramo que cubrir).
# Atributos (OSIPTEL, timbrado, …): los del último corte de características, porque score.Caracteristicas guarda
# 7 días; el orden y el canal sí son los de cada día.
# ---------------------------------------------------------------------------------------------------------------
COLUMNA_ATRIBUTO = {"Osiptel": "S_OSIPTEL", "Timbra": "S_TIMBRA", "Whatsapp": "S_WHATSAPP",
                    "Origen": "S_ORIGEN", "Fuente": "S_FUENTE", "Color": "S_COLOR"}


def sql_cobertura(carteras: List[int], universo: str, filtros: Dict[str, List[str]]) -> tuple[str, Dict[str, Any]]:
    en = ", ".join(str(int(c)) for c in carteras)
    params: Dict[str, Any] = {}
    donde: List[str] = []
    con_base = universo == "BASES" or "Canal" in filtros
    con_atributos = any(d in COLUMNA_ATRIBUTO for d in filtros)
    for i, (dim, valores) in enumerate(sorted(filtros.items())):
        marcas = []
        for j, v in enumerate(valores):
            params[f"c{i}_{j}"] = v
            marcas.append(f":c{i}_{j}")
        if dim == "Tramo":
            expr = "p.Tramo"
        elif dim == "Orden":
            expr = "p.Orden"
        elif dim == "Canal":
            expr = "ISNULL(b.Canal, 'SIN BASE')"
        else:
            expr = f"ISNULL(c.{COLUMNA_ATRIBUTO[dim]}, 'SIN_DATO')"
        donde.append(f"{expr} IN ({', '.join(marcas)})")
    if universo == "BASES":
        donde.append("b.Canal IS NOT NULL")
    union_base = """
        LEFT JOIN (
            SELECT d.IdCartera, d.DNI, d.Telefono, CAST(x.FechaGeneracion AS DATE) AS Fecha,
                   CASE MIN(CASE x.Canal WHEN 'PRED' THEN 1 WHEN 'PREVIEW' THEN 2 WHEN 'IVR' THEN 3 WHEN 'SMS' THEN 4 ELSE 5 END)
                        WHEN 1 THEN 'PRED' WHEN 2 THEN 'PREVIEW' WHEN 3 THEN 'IVR' WHEN 4 THEN 'SMS' ELSE 'OTRO' END AS Canal
            FROM score.Base AS x
            INNER JOIN score.BaseDetalle AS d ON d.IdBase = x.IdBase
            WHERE x.FechaGeneracion >= :desde AND x.FechaGeneracion < DATEADD(DAY, 1, :hasta)
              AND d.IdCartera IN ({en})
            GROUP BY d.IdCartera, d.DNI, d.Telefono, CAST(x.FechaGeneracion AS DATE)
        ) AS b ON b.IdCartera = p.IdCartera AND b.DNI = p.DNI AND b.Telefono = p.Telefono AND b.Fecha = p.Fecha""".format(en=en) if con_base else ""
    union_atr = """
        LEFT JOIN score.Caracteristicas AS c
               ON c.FechaCorte = (SELECT MAX(FechaCorte) FROM score.Caracteristicas WHERE Poblacion = 'UNIVERSO')
              AND c.Poblacion = 'UNIVERSO'
              AND c.IdCartera = p.IdCartera AND c.DNI = p.DNI AND c.Telefono = p.Telefono""" if con_atributos else ""
    sql = f"""
        WITH p AS (
            SELECT s.FechaCorte AS Fecha, s.IdCartera, s.DNI, s.Telefono, CONVERT(VARCHAR(10), s.Tramo) AS Tramo,
                   CASE WHEN s.OrdenCliente >= 3 THEN '3+' ELSE CONVERT(VARCHAR(3), s.OrdenCliente) END AS Orden
            FROM score.TelefonoScore AS s
            WHERE s.IdCartera IN ({en}) AND s.FechaCorte BETWEEN :desde AND :hasta
        ), cli AS (
            -- Lo que pasó con el cliente en el periodo por cualquiera de sus teléfonos
            SELECT d.IdCartera, d.DNI,
                   MAX(CASE WHEN d.IntentosHumano + d.IntentosMaquina > 0 THEN 1 ELSE 0 END) AS LlamadoCli,
                   MAX(CASE WHEN ISNULL(d.N_TITULAR, 0) + ISNULL(d.N_TERCERO_ACUERDO, 0) > 0 THEN 1 ELSE 0 END) AS CefCli
            FROM score.TelefonoDia AS d
            WHERE d.IdCartera IN ({en}) AND d.Fecha BETWEEN :desde AND :hasta
            GROUP BY d.IdCartera, d.DNI
        ), t AS (
            SELECT p.Tramo, p.IdCartera, p.DNI, p.Telefono,
                   COUNT(*) AS DiasEnTramo,
                   SUM(CASE WHEN ISNULL(d.IntentosHumano, 0) + ISNULL(d.IntentosMaquina, 0) > 0 THEN 1 ELSE 0 END) AS DiasLlamado,
                   SUM(CASE WHEN ISNULL(d.IntentosHumano, 0) > 0 THEN 1 ELSE 0 END) AS DiasAsesor
            FROM p
            LEFT JOIN score.TelefonoDia AS d
                   ON d.Fecha = p.Fecha AND d.IdCartera = p.IdCartera AND d.DNI = p.DNI AND d.Telefono = p.Telefono
            {union_base}
            {union_atr}
            {"WHERE " + " AND ".join(donde) if donde else ""}
            GROUP BY p.Tramo, p.IdCartera, p.DNI, p.Telefono
        )
        , m AS (
            -- Por qué un teléfono no recibió ninguna llamada (en este orden; el estado de la promesa es el de hoy)
            SELECT t.*,
                   CASE WHEN t.DiasLlamado > 0 THEN NULL
                        WHEN gc.EstadoPdp IN (N'VIGENTE', N'PAGADA') THEN 'PDP'
                        WHEN ISNULL(c.CefCli, 0) = 1 THEN 'CEF_OTRO'
                        WHEN ISNULL(c.LlamadoCli, 0) = 1 THEN 'LLAMADO_OTRO'
                        ELSE 'CLIENTE_SIN_LLAMADA' END AS Motivo
            FROM t
            LEFT JOIN cli AS c ON c.IdCartera = t.IdCartera AND c.DNI = t.DNI
            LEFT JOIN score.GestionCliente AS gc ON gc.IdCartera = t.IdCartera AND gc.DNI = t.DNI
        )
        SELECT Tramo,
               COUNT(*) AS TelefonosDistintos,
               SUM(CASE WHEN DiasLlamado > 0 THEN 1 ELSE 0 END) AS Llamados,
               SUM(CASE WHEN DiasAsesor > 0 THEN 1 ELSE 0 END) AS LlamadosAsesor,
               SUM(DiasLlamado) AS DiasLlamado,
               SUM(DiasEnTramo) AS DiasEnTramo,
               SUM(CASE WHEN Motivo = 'PDP' THEN 1 ELSE 0 END) AS SinLlamadaPdp,
               SUM(CASE WHEN Motivo = 'CEF_OTRO' THEN 1 ELSE 0 END) AS SinLlamadaCefOtro,
               SUM(CASE WHEN Motivo = 'LLAMADO_OTRO' THEN 1 ELSE 0 END) AS SinLlamadaOtroTel,
               SUM(CASE WHEN Motivo = 'CLIENTE_SIN_LLAMADA' THEN 1 ELSE 0 END) AS SinLlamadaCliente,
               COUNT(DISTINCT CASE WHEN Motivo = 'CLIENTE_SIN_LLAMADA' THEN CONCAT(IdCartera, '|', DNI) END) AS ClientesSinLlamada
        FROM m
        GROUP BY Tramo
        OPTION (RECOMPILE)
    """
    return sql, params


def cobertura(idcartera: int, dias: int, universo: str, filtros: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    universo, filtros_ok = _validar(dias, universo, filtros)
    with engine_siscob.connect() as conn:
        if conn.execute(text("SELECT OBJECT_ID('score.RendimientoDia')")).scalar() is None:
            return {"sin_datos": True, "filas": []}
        carteras = generador.carteras_de(conn, idcartera)
        periodo = _periodo(conn, carteras, dias)
        if periodo is None:
            return {"sin_datos": True, "filas": []}
        desde, hasta, _ = periodo
        sql, params = sql_cobertura(carteras, universo, filtros_ok)
        filas = conn.execute(text(sql), {**params, "desde": desde, "hasta": hasta}).mappings().all()
    datos = [{k: (v if k == "Tramo" else int(v or 0)) for k, v in dict(f).items()} for f in filas]
    return {"sin_datos": not datos, "desde": desde.isoformat(), "hasta": hasta.isoformat(), "filas": datos}


# ---------------------------------------------------------------------------------------------------------------
# Rendimiento por base generada (25/11/2026; reglas del 14/11, diseño §7)
# - Ventana: desde la hora de generación hasta el fin del día; si se generó desde las 18:00, hasta el fin del día
#   siguiente. Mientras la ventana no termina, el resultado es "en curso".
# - Se atribuye por teléfono: cada llamada (gestión humana o de máquina de SISCOB) va a la base MÁS RECIENTE generada
#   antes de la llamada que tenga ese teléfono y cuya ventana siga abierta. Así un teléfono en dos bases no cuenta doble.
# - CEF = gestión humana con indicador CEF según la paleta (o sin tipo y TipoContacto = 1), como en el resto del score.
# - PDP = compromisos (monto > 0) registrados en esas gestiones CEF atribuidas.
# - "Clientes con CEF (cualquier teléfono)": CEF del cliente en la ventana por cualquiera de sus teléfonos (útil en
#   SMS e IVR, que no devuelven el resultado por teléfono).
# ---------------------------------------------------------------------------------------------------------------
HORA_BASE_NOCHE = "18:00"
DIAS_RENDIMIENTO_BASES = (1, 3, 7)
# Canales que no marcan: su base no se lleva llamadas; se mide lo que pasó después, sin exclusividad.
CANALES_NO_EXCLUSIVOS = ("SMS",)


def sql_rendimiento_bases() -> List[str]:
    """Sentencias en orden; la última devuelve una fila por base. Parámetros: :id, :desde."""
    return [
        "IF OBJECT_ID('tempdb..#rb') IS NOT NULL DROP TABLE #rb;",
        f"""
        SELECT b.IdBase, b.Codigo, b.NombreArchivo, b.Canal, b.FechaGeneracion,
               CASE WHEN CAST(b.FechaGeneracion AS TIME) >= '{HORA_BASE_NOCHE}'
                    THEN DATEADD(DAY, 2, CAST(CAST(b.FechaGeneracion AS DATE) AS DATETIME))
                    ELSE DATEADD(DAY, 1, CAST(CAST(b.FechaGeneracion AS DATE) AS DATETIME)) END AS VentanaFin
        INTO #rb
        FROM score.Base AS b
        WHERE b.IdCartera = :id AND b.Codigo IS NOT NULL AND b.FechaGeneracion >= :desde;
        """,
        "IF OBJECT_ID('tempdb..#rd') IS NOT NULL DROP TABLE #rd;",
        """
        SELECT d.IdBase, d.IdCartera, d.DNI, d.Telefono, b.FechaGeneracion, b.VentanaFin,
               CASE WHEN b.Canal IN ({canales}) THEN 0 ELSE 1 END AS Exclusiva
        INTO #rd
        FROM score.BaseDetalle AS d INNER JOIN #rb AS b ON b.IdBase = d.IdBase;
        CREATE INDEX IX_rd ON #rd (Telefono, IdCartera, FechaGeneracion) INCLUDE (IdBase, VentanaFin, DNI, Exclusiva);
        """.format(canales=", ".join(f"'{c}'" for c in CANALES_NO_EXCLUSIVOS)),
        "IF OBJECT_ID('tempdb..#rt') IS NOT NULL DROP TABLE #rt;",
        """
        SELECT DISTINCT IdCartera, Telefono INTO #rt FROM #rd;
        CREATE UNIQUE CLUSTERED INDEX IX_rt ON #rt (Telefono, IdCartera);
        """,
        "IF OBJECT_ID('tempdb..#re') IS NOT NULL DROP TABLE #re;",
        """
        DECLARE @ini DATE = (SELECT CAST(MIN(FechaGeneracion) AS DATE) FROM #rb);
        DECLARE @fin DATE = (SELECT CAST(MAX(VentanaFin) AS DATE) FROM #rb);
        CREATE TABLE #re (Fuente CHAR(1) NOT NULL, IdGestion BIGINT NOT NULL, IdCartera INT NOT NULL,
                          Telefono CHAR(9) COLLATE DATABASE_DEFAULT NOT NULL, Momento DATETIME NOT NULL, EsCef BIT NOT NULL);
        IF @ini IS NOT NULL
        BEGIN
            INSERT INTO #re (Fuente, IdGestion, IdCartera, Telefono, Momento, EsCef)
            SELECT 'H', g.IdGestion, g.idCartera, CONVERT(CHAR(9), g.telefono),
                   CAST(CAST(g.Fecha AS DATE) AS DATETIME) + CAST(ISNULL(CAST(g.Hora AS TIME(0)), '00:00') AS DATETIME),
                   CASE WHEN LTRIM(RTRIM(i.TipoContacto)) = 'CEF' THEN 1
                        WHEN LTRIM(RTRIM(i.TipoContacto)) IN ('CNE', 'NOC') THEN 0
                        WHEN g.TipoContacto = 1 THEN 1 ELSE 0 END
            FROM siscob.dbo.gestion AS g WITH (NOLOCK)
            LEFT JOIN siscob.dbo.Indicador AS i WITH (NOLOCK) ON i.IdIndicador = g.IdIndicador
            WHERE g.Fecha >= @ini AND g.Fecha < @fin
              AND g.idCartera IN (SELECT DISTINCT IdCartera FROM #rt)
              AND g.telefono BETWEEN 900000000 AND 999999999
              AND EXISTS (SELECT 1 FROM #rt AS t WHERE t.Telefono = CONVERT(CHAR(9), g.telefono) AND t.IdCartera = g.idCartera)
            OPTION (RECOMPILE);
            INSERT INTO #re (Fuente, IdGestion, IdCartera, Telefono, Momento, EsCef)
            SELECT 'M', g.IdGestion, g.idCartera, CONVERT(CHAR(9), g.telefono),
                   CAST(CAST(g.Fecha AS DATE) AS DATETIME) + CAST(ISNULL(CAST(g.Hora AS TIME(0)), '00:00') AS DATETIME), 0
            FROM siscob.dbo.pgestion AS g WITH (NOLOCK)
            WHERE g.Fecha >= @ini AND g.Fecha < @fin
              AND g.idCartera IN (SELECT DISTINCT IdCartera FROM #rt)
              AND g.telefono BETWEEN 900000000 AND 999999999
              AND EXISTS (SELECT 1 FROM #rt AS t WHERE t.Telefono = CONVERT(CHAR(9), g.telefono) AND t.IdCartera = g.idCartera)
            OPTION (RECOMPILE);
        END;
        """,
        "IF OBJECT_ID('tempdb..#ra') IS NOT NULL DROP TABLE #ra;",
        """
        -- Bases de llamada (predictivo, preview, IVR): cada llamada va a la base más reciente generada
        -- antes, con ventana abierta y ese teléfono. Una llamada cuenta en una sola base.
        SELECT e.Fuente, e.IdGestion, e.EsCef, e.Telefono, x.IdBase, x.DNI
        INTO #ra
        FROM #re AS e
        CROSS APPLY (SELECT TOP (1) d.IdBase, d.DNI FROM #rd AS d
                     WHERE d.Telefono = e.Telefono AND d.IdCartera = e.IdCartera AND d.Exclusiva = 1
                       AND d.FechaGeneracion <= e.Momento AND e.Momento < d.VentanaFin
                     ORDER BY d.FechaGeneracion DESC, d.IdBase DESC) AS x;
        -- Bases de SMS: no se llevan llamadas. Muestran lo que pasó después del envío con los teléfonos
        -- de la base (cualquier llamada en su ventana), aunque esa llamada ya cuente en otra base.
        INSERT INTO #ra (Fuente, IdGestion, EsCef, Telefono, IdBase, DNI)
        SELECT e.Fuente, e.IdGestion, e.EsCef, e.Telefono, x.IdBase, x.DNI
        FROM #re AS e
        CROSS APPLY (SELECT d.IdBase, MIN(d.DNI) AS DNI FROM #rd AS d
                     WHERE d.Telefono = e.Telefono AND d.IdCartera = e.IdCartera AND d.Exclusiva = 0
                       AND d.FechaGeneracion <= e.Momento AND e.Momento < d.VentanaFin
                     GROUP BY d.IdBase) AS x;
        """,
        "IF OBJECT_ID('tempdb..#rp') IS NOT NULL DROP TABLE #rp;",
        """
        -- PDP de las gestiones CEF atribuidas
        SELECT a.IdBase, a.DNI, cp.Monto
        INTO #rp
        FROM #ra AS a
        INNER JOIN siscob.dbo.COMPROMISO AS cp WITH (NOLOCK) ON cp.IdGestion = a.IdGestion
        WHERE a.Fuente = 'H' AND a.EsCef = 1 AND cp.Monto > 0;
        """,
        """
        SELECT b.IdBase, b.Codigo, b.NombreArchivo, b.Canal, b.FechaGeneracion, b.VentanaFin,
               CASE WHEN GETDATE() < b.VentanaFin THEN 1 ELSE 0 END AS EnCurso,
               CASE WHEN b.Canal IN ({canales}) THEN 0 ELSE 1 END AS Exclusiva,
               (SELECT COUNT(*) FROM #rd AS d WHERE d.IdBase = b.IdBase) AS Telefonos,
               (SELECT COUNT(DISTINCT d.DNI) FROM #rd AS d WHERE d.IdBase = b.IdBase) AS Clientes,
               (SELECT COUNT(DISTINCT a.Telefono) FROM #ra AS a WHERE a.IdBase = b.IdBase) AS TelMarcados,
               (SELECT COUNT(DISTINCT a.DNI) FROM #ra AS a WHERE a.IdBase = b.IdBase) AS CliMarcados,
               (SELECT COUNT(*) FROM #ra AS a WHERE a.IdBase = b.IdBase) AS Intentos,
               (SELECT COUNT(*) FROM #ra AS a WHERE a.IdBase = b.IdBase AND a.Fuente = 'H') AS IntentosHumano,
               (SELECT COUNT(*) FROM #ra AS a WHERE a.IdBase = b.IdBase AND a.Fuente = 'M') AS IntentosMaquina,
               (SELECT COUNT(DISTINCT a.Telefono) FROM #ra AS a WHERE a.IdBase = b.IdBase AND a.EsCef = 1) AS TelCef,
               (SELECT COUNT(DISTINCT a.DNI) FROM #ra AS a WHERE a.IdBase = b.IdBase AND a.EsCef = 1) AS CliCef,
               (SELECT COUNT(*) FROM #rp AS p WHERE p.IdBase = b.IdBase) AS Pdp,
               (SELECT COUNT(DISTINCT p.DNI) FROM #rp AS p WHERE p.IdBase = b.IdBase) AS CliPdp,
               (SELECT SUM(CONVERT(DECIMAL(18, 2), p.Monto)) FROM #rp AS p WHERE p.IdBase = b.IdBase) AS MontoPdp,
               (SELECT COUNT(*) FROM #re AS e WHERE e.Fuente = 'M'
                  AND e.Momento >= b.FechaGeneracion AND e.Momento < b.VentanaFin) AS MaquinaEnVentana
        FROM #rb AS b
        ORDER BY b.FechaGeneracion DESC;
        """.format(canales=", ".join(f"'{c}'" for c in CANALES_NO_EXCLUSIVOS)),
    ]


def rendimiento_bases(idcartera: int, dias: int = 3) -> Dict[str, Any]:
    if dias not in DIAS_RENDIMIENTO_BASES:
        raise ConsultaInvalida("El periodo debe ser 1, 3 o 7 días.")
    desde = date.today() - timedelta(days=dias - 1)
    sentencias = sql_rendimiento_bases()
    with engine_siscob.connect() as conn:
        for sql in sentencias[:-1]:
            conn.execute(text(sql), {"id": idcartera, "desde": desde})
        filas = conn.execute(text(sentencias[-1])).mappings().all()
    datos = []
    for f in filas:
        d = dict(f)
        for k in ("Telefonos", "Clientes", "TelMarcados", "CliMarcados", "Intentos", "IntentosHumano", "IntentosMaquina",
                  "TelCef", "CliCef", "Pdp", "CliPdp", "MaquinaEnVentana", "EnCurso", "Exclusiva"):
            d[k] = int(d[k] or 0)
        d["MontoPdp"] = float(d["MontoPdp"]) if d["MontoPdp"] is not None else 0.0
        d["Exclusiva"] = bool(d["Exclusiva"])
        d["SinMaquina"] = d["Canal"] in ("PRED", "IVR") and d["MaquinaEnVentana"] == 0   # el preview lo marca el asesor
        datos.append(d)
    return {"idcartera": idcartera, "dias": dias, "desde": desde.isoformat(), "hora_noche": HORA_BASE_NOCHE,
            "bases": datos}
