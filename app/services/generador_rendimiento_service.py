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
