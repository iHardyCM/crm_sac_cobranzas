#score_telefono_service.py
from decimal import Decimal
from datetime import date, datetime
from typing import Any, Dict, Iterable, List, Optional
from io import BytesIO
import pandas as pd

from sqlalchemy import text

from app.core.db_siscob import engine_siscob


TABLA_SCORE = "dbo.TBL_SCORE_TELEFONICO_CRM"

CARTERAS_SCORE_CONTEXTO = [
    {"idcartera": 112, "nombre": "MIBANCO - EQUIPO 1 - MORA 25+"},
    {"idcartera": 143, "nombre": "MIBANCO - EQUIPO 2 - MORA 0-24"},
    {"idcartera": 135, "nombre": "MIBANCO VIGENTE"},
    {"idcartera": 117, "nombre": "INTERBANK"},
    {"idcartera": 132, "nombre": "FINANCIERA OH"},
    {"idcartera": 124, "nombre": "COMPARTAMOS CASTIGO IND"},
    {"idcartera": 126, "nombre": "COMPARTAMOS VIGENTE IND"},
    {"idcartera": 128, "nombre": "COMPARTAMOS VIGENTE CCM"},
    {"idcartera": 133, "nombre": "COMPARTAMOS GRUPAL VIGENTE"},
    {"idcartera": 144, "nombre": "COMPARTAMOS GRUPAL CASTIGO"},
]

CARTERA_SCORE_NOMBRES = {
    112: ["MIBANCO", "MIBANCO 1", "MIBANCO EQUIPO 1", "MIBANCO CASTIGO 25+"],
    143: ["MIBANCO 2", "MIBANCO EQUIPO 2", "MIBANCO CASTIGO 0-24"],
    135: ["MIBANCO VIGENTE", "MIBANCO ACTIVA"],

    117: ["INTERBANK"],
    132: ["FINANCIERA OH"],
    124: ["COMPARTAMOS CASTIGO IND", "COMPARTAMOS CASTIGO INDIVIDUAL"],
    126: ["COMPARTAMOS VIGENTE IND", "COMPARTAMOS VIGENTE INDIVIDUAL"],
    128: ["COMPARTAMOS VIGENTE CCM"],
    133: ["COMPARTAMOS GRUPAL VIGENTE", "COMPARTAMOS VIGENTE GRUPAL", "COMPARTAMOS VIGENTE GRUPAL / CSM"],
    144: ["COMPARTAMOS GRUPAL CASTIGO", "COMPARTAMOS CASTIGO GRUPAL"],
}

SELECT_COLUMNS = [
    "CARTERA_SCORE",
    "DNI",
    "IDCLIENTE",
    "NOMBRE_CLIENTE",
    "TELEFONO",
    "CAPITAL",
    "SCORE_TELEFONO",
    "PRIORIDAD_CONTACTO",
    "PRIORIDAD_BANCO",
    "CONDICION",
    "FOCO",
    "PRODUCTO_ORIGEN",
    "RANGO_MORA",
    "RANGO_CAPITAL",
    "RANGO_EDAD",
    "EMPRESAS_REPORTANTES",
    "ESTADO_CIVIL",
    "MG_CONTACTO_CLIENTE",
    "MG_INDICADOR_CLIENTE",
    "UG_CONTACTO_CLIENTE",
    "UG_INDICADOR_CLIENTE",
    "ESTADO_PDP",
    "FECHA_COMPROMISO",
    "TIMBRADO",
    "OSIPTEL",
    "WHATSAPP",
    "TIPO_FONO",
    "ORDEN",
    "INTENTOS_EQUIVOCADO",
    "APAGADO_IVR",
    "FALLADOS_IVR",
    "MG_CONTACTO_TELF",
    "MG_RESULTADO_TELF",
    "UG_CONTACTO_TELF",
    "UG_RESULTADO_TELF",
    "ORIGEN",
    "TIPO_BASE",
    "MARCA_OPERATIVA",
    "ZONA",
    "FLG_WHATSAPP_VALIDO",
    "FLG_OSIPTEL_VALIDO",
    "FLG_TIMBRA",
    "FLG_TIMBRA_FUERTE",
    "FLG_CEF_TELEFONO",
    "FLG_CNE_TELEFONO",
    "FLG_NOC_TELEFONO",
]

CATALOGO_FIELDS = {
    "condiciones": "CONDICION",
    "focos": "FOCO",
    "prioridades_banco": "PRIORIDAD_BANCO",
    "prioridades_fono": "PRIORIDAD_CONTACTO",
    "productos": "PRODUCTO_ORIGEN",
    "nuevos": ("NUEVO", "FLG_NUEVO", "ES_NUEVO"),
    "rangos_mora": ("RANGO_MADURACION", "RANGO_MORA"),
    "rangos_capital": "RANGO_CAPITAL",
    "rangos_edad": "RANGO_EDAD",
    "empresas_reportantes": "EMPRESAS_REPORTANTES",
    "cuentas": ("CUENTAS", "CANT_CUENTAS", "NRO_CUENTAS", "NUM_CUENTAS"),
    "anios_cd_historico": ("ANIO_CD_HISTORICO", "ANIO_CD", "ULT_PERIODO_CONTACTO", "ULTIMO_PERIODO_CONTACTO"),
    "clusters_ml": ("CLUSTER_ML", "CLUSTER", "SEGMENTO_ML"),
    "flags_top": ("FLAG_TOP", "FLG_TOP"),
    "rangos_campanas": ("RANGO_CAMPANAS", "RANGO_CAMPANA", "RANGO_CAMPANIAS", "RANGO_CAMPANIA"),
    "caseros": ("CASEROS", "CASERO", "FLG_CASERO"),
    "estados_civiles": "ESTADO_CIVIL",
    "mg_contacto_cliente": "MG_CONTACTO_CLIENTE",
    "mg_indicador_cliente": "MG_INDICADOR_CLIENTE",
    "ug_contacto_cliente": "UG_CONTACTO_CLIENTE",
    "ug_indicador_cliente": "UG_INDICADOR_CLIENTE",
    "estados_pdp": "ESTADO_PDP",
    "origenes": "ORIGEN",
    "tipos_base": "TIPO_BASE",
    "tipos_fono": "TIPO_FONO",
    "ordenes": "ORDEN",
    "osiptel": "OSIPTEL",
    "whatsapp": "WHATSAPP",
    "timbrados": "TIMBRADO",
    "intentos_equivocados": "INTENTOS_EQUIVOCADO",
    "apagados_ivr": "APAGADO_IVR",
    "fallados_ivr": "FALLADOS_IVR",
    "carteras": "CARTERA_SCORE",
    "zonas": "ZONA",
    "marcas_operativas": "MARCA_OPERATIVA",
}


def serializar_valor(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def row_to_dict(row) -> Dict[str, Any]:
    return {key: serializar_valor(value) for key, value in dict(row._mapping).items()}


def normalizar_page_limit(page, limit):
    page = int(page or 1)
    limit = int(limit or 50)
    if page < 1:
        page = 1
    if limit < 1:
        limit = 50
    if limit > 500:
        limit = 500
    offset = (page - 1) * limit
    return page, limit, offset


def columnas_score_disponibles(conn) -> set[str]:
    rows = conn.execute(text("""
        SELECT c.name
        FROM sys.columns c
        INNER JOIN sys.objects o
            ON c.object_id = o.object_id
        INNER JOIN sys.schemas s
            ON o.schema_id = s.schema_id
        WHERE s.name = 'dbo'
          AND o.name = 'TBL_SCORE_TELEFONICO_CRM'
    """)).fetchall()
    return {str(row.name).upper() for row in rows}


def expr_columna(columna: str, disponibles: set[str]) -> str:
    if columna.upper() in disponibles:
        return f"[{columna}]"
    return f"NULL AS [{columna}]"


def expr_valor(columna: str, disponibles: set[str], default: str = "NULL") -> str:
    if columna.upper() in disponibles:
        return f"[{columna}]"
    return default


def existe_columna(columna: str, disponibles: set[str]) -> bool:
    return columna.upper() in disponibles


def construir_filtro_idcartera(disponibles: set[str], idcartera: Optional[int]) -> tuple[str, Dict[str, Any]]:
    if not idcartera:
        return "", {}

    for columna in ("IDCARTERA", "ID_CARTERA", "IDCARTERA_SCORE", "ID_CARTERA_SCORE"):
        if existe_columna(columna, disponibles):
            return f"WHERE TRY_CONVERT(INT, [{columna}]) = :idcartera", {"idcartera": int(idcartera)}

    if existe_columna("CARTERA_SCORE", disponibles):
        nombres = CARTERA_SCORE_NOMBRES.get(int(idcartera), [])
        if nombres:
            placeholders = []
            params = {}
            for index, nombre in enumerate(nombres):
                key = f"cartera_{index}"
                placeholders.append(f":{key}")
                params[key] = nombre.upper()
            return (
                f"WHERE {expr_texto_normalizado('CARTERA_SCORE')} IN ({', '.join(placeholders)})",
                params,
            )

    return "", {}


def expr_alias(columna: str, alias: str, disponibles: set[str], default: str = "NULL") -> str:
    if existe_columna(columna, disponibles):
        return f"[{columna}] AS [{alias}]"
    return f"{default} AS [{alias}]"


def primer_expr_existente(
    disponibles: set[str],
    columnas: Iterable[str],
    default: str = "NULL",
) -> str:
    for columna in columnas:
        if existe_columna(columna, disponibles):
            return f"[{columna}]"
    return default


def construir_where_resultados(
    disponibles: set[str],
    idcartera: Optional[int],
    search: Optional[str],
    filtros_recibidos: Optional[Dict[str, Any]] = None,
) -> tuple[str, Dict[str, Any]]:
    where_sql, params = construir_filtro_idcartera(disponibles, idcartera)
    filtros_extra: List[str] = []

    filtros_secundarios = dict(filtros_recibidos or {})
    filtros_secundarios.pop("cartera", None)
    if search:
        filtros_secundarios["busqueda"] = search

    filtros_sql, filtros_params = construir_filtros(disponibles, filtros_secundarios)
    if filtros_sql:
        filtros_extra.append(filtros_sql.replace("WHERE ", "", 1))
        params.update(filtros_params)

    if filtros_extra:
        if where_sql:
            where_sql = f"{where_sql} AND {' AND '.join(filtros_extra)}"
        else:
            where_sql = f"WHERE {' AND '.join(filtros_extra)}"

    return where_sql, params


def construir_select_resultados(disponibles: set[str]) -> tuple[str, str]:
    score_expr = primer_expr_existente(disponibles, ("SCORE_FINAL", "SCORE_TELEFONO"), "0")
    etiqueta_expr = (
        "[ETIQUETA_SCORE]"
        if existe_columna("ETIQUETA_SCORE", disponibles)
        else f"""
            CASE
                WHEN TRY_CONVERT(DECIMAL(10,2), {score_expr}) >= 85 THEN 'TOP CONTACTABLE'
                WHEN TRY_CONVERT(DECIMAL(10,2), {score_expr}) >= 70 THEN 'CONTACTABLE MEDIO'
                WHEN TRY_CONVERT(DECIMAL(10,2), {score_expr}) >= 50 THEN 'DIGITAL PRIORITARIO'
                ELSE 'BAJA PRIORIDAD'
            END
        """
    )
    whatsapp_expr = (
        "[WHATSAPP]"
        if existe_columna("WHATSAPP", disponibles)
        else "CASE WHEN ISNULL([FLG_WHATSAPP_VALIDO], 0) = 1 THEN 'SI' ELSE 'NO' END"
        if existe_columna("FLG_WHATSAPP_VALIDO", disponibles)
        else "NULL"
    )
    osiptel_expr = (
        "[OSIPTEL]"
        if existe_columna("OSIPTEL", disponibles)
        else "CASE WHEN ISNULL([FLG_OSIPTEL_VALIDO], 0) = 1 THEN 'SI' ELSE 'NO' END"
        if existe_columna("FLG_OSIPTEL_VALIDO", disponibles)
        else "NULL"
    )
    intentos_expr = primer_expr_existente(disponibles, ("INTENTOS_RECIENTES", "INTENTOS_EQUIVOCADO"), "0")
    mejor_resultado_expr = primer_expr_existente(disponibles, ("MEJOR_RESULTADO", "MG_RESULTADO_TELF", "UG_RESULTADO_TELF"), "NULL")

    select_sql = f"""
        {expr_alias('DNI', 'DNI', disponibles)},
        {expr_alias('IDCLIENTE', 'IDCLIENTE', disponibles)},
        {expr_alias('NOMBRE_CLIENTE', 'NOMBRE_CLIENTE', disponibles)},
        {expr_alias('TELEFONO', 'TELEFONO', disponibles)},
        {expr_alias('CAPITAL', 'CAPITAL', disponibles, '0')},
        {score_expr} AS [SCORE_FINAL],
        {score_expr} AS [SCORE_TELEFONO],
        {etiqueta_expr} AS [ETIQUETA_SCORE],
        {expr_alias('TIMBRADO', 'TIMBRADO', disponibles, '0')},
        {whatsapp_expr} AS [WHATSAPP],
        {osiptel_expr} AS [OSIPTEL],
        {intentos_expr} AS [INTENTOS_RECIENTES],
        {mejor_resultado_expr} AS [MEJOR_RESULTADO],
        {expr_alias('ORDEN', 'ORDEN', disponibles, 'NULL')}
    """
    return select_sql, score_expr


def construir_order_resultados(disponibles: set[str], order_by: Optional[str], order_dir: Optional[str]) -> str:
    score_expr = primer_expr_existente(disponibles, ("SCORE_FINAL", "SCORE_TELEFONO"), "0")
    ordenes = {
        "DNI": primer_expr_existente(disponibles, ("DNI",), "NULL"),
        "IDCLIENTE": primer_expr_existente(disponibles, ("IDCLIENTE",), "NULL"),
        "TELEFONO": primer_expr_existente(disponibles, ("TELEFONO",), "NULL"),
        "CAPITAL": primer_expr_existente(disponibles, ("CAPITAL",), "0"),
        "SCORE_FINAL": score_expr,
        "SCORE_TELEFONO": score_expr,
        "TIMBRADO": primer_expr_existente(disponibles, ("TIMBRADO",), "0"),
        "INTENTOS_RECIENTES": primer_expr_existente(disponibles, ("INTENTOS_RECIENTES", "INTENTOS_EQUIVOCADO"), "0"),
        "ORDEN": primer_expr_existente(disponibles, ("ORDEN",), "0"),
    }
    columna = ordenes.get(str(order_by or "SCORE_FINAL").upper(), score_expr)
    direccion = "ASC" if str(order_dir or "").upper() == "ASC" else "DESC"
    dni_expr = primer_expr_existente(disponibles, ("DNI",), "NULL")
    telefono_expr = primer_expr_existente(disponibles, ("TELEFONO",), "NULL")
    return f"{columna} {direccion}, {dni_expr}, {telefono_expr}"


def obtener_contexto_score(usuario: Optional[str] = None, perfil: Optional[str] = None) -> Dict[str, Any]:
    return {
        "usuario": usuario or "SIN_USUARIO",
        "perfil": perfil or "SUPERVISOR",
        "carteras_permitidas": CARTERAS_SCORE_CONTEXTO,
        "cartera_default": 112,
    }


def obtener_ultima_actualizacion_score() -> Dict[str, Any]:
    try:
        with engine_siscob.connect() as conn:
            disponibles = columnas_score_disponibles(conn)
            total = conn.execute(text(f"SELECT COUNT(1) FROM {TABLA_SCORE} WITH(NOLOCK)")).scalar() or 0

            log_exists = conn.execute(text("""
                SELECT OBJECT_ID('CobAuto.dbo.score_telefonico_refresh_log') AS object_id
            """)).scalar()

            fecha = None
            if log_exists:
                columnas_log = conn.execute(text("""
                    SELECT name
                    FROM CobAuto.sys.columns
                    WHERE object_id = OBJECT_ID('CobAuto.dbo.score_telefonico_refresh_log')
                """)).fetchall()
                nombres_log = {str(row.name).lower() for row in columnas_log}
                for candidata in ("fecha_fin", "fecha_actualizacion", "fecha", "fecha_ejecucion", "created_at"):
                    if candidata in nombres_log:
                        fecha = conn.execute(text(f"""
                            SELECT TOP 1 [{candidata}]
                            FROM CobAuto.dbo.score_telefonico_refresh_log WITH(NOLOCK)
                            ORDER BY [{candidata}] DESC
                        """)).scalar()
                        break

            if not fecha:
                for candidata in ("FECHA_ACTUALIZACION", "FECHA_CARGA", "FECHA_REGISTRO", "FECHA_PROCESO"):
                    if existe_columna(candidata, disponibles):
                        fecha = conn.execute(text(f"""
                            SELECT MAX([{candidata}])
                            FROM {TABLA_SCORE} WITH(NOLOCK)
                        """)).scalar()
                        break

        return {
            "fecha": serializar_valor(fecha or datetime.now()),
            "estado": "OK",
            "total_registros": int(total),
        }
    except Exception as e:
        print("ERROR SCORE ULTIMA ACTUALIZACION:", e)
        return {
            "fecha": serializar_valor(datetime.now()),
            "estado": "FALLBACK",
            "total_registros": 0,
        }


def obtener_resumen_score(idcartera: Optional[int] = None, **filtros_recibidos) -> Dict[str, Any]:
    try:
        with engine_siscob.connect() as conn:
            disponibles = columnas_score_disponibles(conn)
            where_universo, params_universo = construir_filtro_idcartera(disponibles, idcartera)
            where_filtrado, params_filtrado = construir_where_resultados(
                disponibles,
                idcartera,
                filtros_recibidos.get("search") or filtros_recibidos.get("busqueda"),
                filtros_recibidos,
            )

            dni_expr = expr_valor("DNI", disponibles, "NULL")
            capital_expr = expr_valor("CAPITAL", disponibles, "0")
            whatsapp_text = expr_valor("WHATSAPP", disponibles, "NULL")
            whatsapp_flag = expr_valor("FLG_WHATSAPP_VALIDO", disponibles, "0")
            timbrado_expr = expr_valor("TIMBRADO", disponibles, "NULL")
            timbra_fuerte = expr_valor("FLG_TIMBRA_FUERTE", disponibles, "0")

            metricas_sql = f"""
                SELECT
                    COUNT(DISTINCT {dni_expr}) AS clientes,
                    COUNT(1) AS telefonos,
                    SUM(
                        CASE
                            WHEN ISNULL({whatsapp_flag}, 0) = 1
                              OR UPPER(LTRIM(RTRIM(CONVERT(VARCHAR(20), {whatsapp_text})))) = 'SI'
                            THEN 1 ELSE 0
                        END
                    ) AS whatsapp_validos,
                    SUM(
                        CASE
                            WHEN ISNULL({timbra_fuerte}, 0) = 1
                              OR TRY_CONVERT(INT, {timbrado_expr}) IN (3, 4)
                            THEN 1 ELSE 0
                        END
                    ) AS timbrado_3_4,
                    SUM(ISNULL(TRY_CONVERT(DECIMAL(18,2), {capital_expr}), 0)) AS capital_total
                FROM {TABLA_SCORE} WITH(NOLOCK)
                {{where_sql}}
            """

            universo_row = conn.execute(
                text(metricas_sql.format(where_sql=where_universo)),
                params_universo,
            ).fetchone()
            filtrado_row = conn.execute(
                text(metricas_sql.format(where_sql=where_filtrado)),
                params_filtrado,
            ).fetchone()

        universo = row_to_dict(universo_row) if universo_row else {}
        filtrado = row_to_dict(filtrado_row) if filtrado_row else {}
        telefonos = filtrado.get("telefonos") or 0
        whatsapp = filtrado.get("whatsapp_validos") or 0
        timbrado = filtrado.get("timbrado_3_4") or 0

        filtrado["porcentaje_whatsapp"] = round(whatsapp * 100 / telefonos, 1) if telefonos else 0
        filtrado["porcentaje_timbrado"] = round(timbrado * 100 / telefonos, 1) if telefonos else 0
        data = {
            "idcartera": idcartera,
            "cartera": next(
                (c["nombre"] for c in CARTERAS_SCORE_CONTEXTO if c["idcartera"] == idcartera),
                None,
            ),
            "universo": {
                "clientes": int(universo.get("clientes") or 0),
                "telefonos": int(universo.get("telefonos") or 0),
                "capital": universo.get("capital_total") or 0,
            },
            "filtrado": {
                "clientes": int(filtrado.get("clientes") or 0),
                "telefonos": int(filtrado.get("telefonos") or 0),
                "whatsapp_validos": int(filtrado.get("whatsapp_validos") or 0),
                "porcentaje_whatsapp": filtrado["porcentaje_whatsapp"],
                "timbrado_3_4": int(filtrado.get("timbrado_3_4") or 0),
                "porcentaje_timbrado": filtrado["porcentaje_timbrado"],
                "capital": filtrado.get("capital_total") or 0,
            },
            # Compatibilidad con la vista anterior.
            "clientes_seleccionados": int(filtrado.get("clientes") or 0),
            "telefonos_seleccionados": int(filtrado.get("telefonos") or 0),
            "whatsapp_validos": int(filtrado.get("whatsapp_validos") or 0),
            "porcentaje_whatsapp": filtrado["porcentaje_whatsapp"],
            "timbrado_3_4": int(filtrado.get("timbrado_3_4") or 0),
            "porcentaje_timbrado": filtrado["porcentaje_timbrado"],
            "capital_total": filtrado.get("capital_total") or 0,
            "total_base_clientes": int(universo.get("clientes") or 0),
        }
        return data
    except Exception as e:
        print("ERROR SCORE RESUMEN:", e)
        raise


def obtener_resultados_score(
    idcartera: int,
    page: int = 1,
    page_size: int = 25,
    search: Optional[str] = None,
    order_by: Optional[str] = "SCORE_FINAL",
    order_dir: Optional[str] = "DESC",
    **filtros_recibidos,
) -> Dict[str, Any]:
    page, page_size, offset = normalizar_page_limit(page, page_size)

    try:
        with engine_siscob.connect() as conn:
            disponibles = columnas_score_disponibles(conn)
            where_sql, params = construir_where_resultados(disponibles, idcartera, search, filtros_recibidos)
            params.update({"offset": offset, "page_size": page_size})

            select_sql, _ = construir_select_resultados(disponibles)
            order_sql = construir_order_resultados(disponibles, order_by, order_dir)

            total = conn.execute(text(f"""
                SELECT COUNT(1)
                FROM {TABLA_SCORE} WITH(NOLOCK)
                {where_sql}
            """), params).scalar() or 0

            rows = conn.execute(text(f"""
                SELECT
                    {select_sql}
                FROM {TABLA_SCORE} WITH(NOLOCK)
                {where_sql}
                ORDER BY {order_sql}
                OFFSET :offset ROWS FETCH NEXT :page_size ROWS ONLY
            """), params).fetchall()

        return {
            "ok": True,
            "total_registros": int(total),
            "total_registros_filtrados": int(total),
            "page": page,
            "page_size": page_size,
            "total_paginas": int((int(total) + page_size - 1) / page_size) if page_size else 0,
            "data": [row_to_dict(row) for row in rows],
        }
    except Exception as e:
        print("ERROR SCORE RESULTADOS:", e)
        raise


def valores_multiples(valor: Optional[Any]) -> List[str]:
    if valor in (None, ""):
        return []
    if isinstance(valor, (list, tuple, set)):
        crudos = valor
    else:
        crudos = str(valor).split(",")
    return [str(v).strip() for v in crudos if str(v).strip()]


def expr_texto_normalizado(columna: str) -> str:
    return f"UPPER(LTRIM(RTRIM(CONVERT(VARCHAR(255), [{columna}] ))))"


def agregar_filtro_igual(
    filtros: List[str],
    params: Dict[str, Any],
    disponibles: set[str],
    columna: str,
    valor: Optional[Any],
    param: str,
    excluir: bool = False,
) -> None:
    if valor in (None, "") or not existe_columna(columna, disponibles):
        return
    valores = [v.upper() for v in valores_multiples(valor)]
    expr = expr_texto_normalizado(columna)
    if len(valores) > 1:
        placeholders = []
        for index, item in enumerate(valores):
            key = f"{param}_{index}"
            placeholders.append(f":{key}")
            params[key] = item
        operador = "NOT IN" if excluir else "IN"
        filtros.append(f"{expr} {operador} ({', '.join(placeholders)})")
        return
    operador = "<>" if excluir else "="
    filtros.append(f"{expr} {operador} :{param}")
    params[param] = valores[0] if valores else str(valor).strip().upper()


def agregar_filtro_maximo(
    filtros: List[str],
    params: Dict[str, Any],
    disponibles: set[str],
    columna: str,
    valor: Optional[Any],
    param: str,
) -> None:
    if valor in (None, "") or not existe_columna(columna, disponibles):
        return
    filtros.append(f"TRY_CONVERT(INT, [{columna}]) <= :{param}")
    params[param] = valor


def agregar_filtro_minimo(
    filtros: List[str],
    params: Dict[str, Any],
    disponibles: set[str],
    columna: str,
    valor: Optional[Any],
    param: str,
) -> None:
    if valor in (None, "") or not existe_columna(columna, disponibles):
        return
    filtros.append(f"TRY_CONVERT(INT, [{columna}]) >= :{param}")
    params[param] = valor


def agregar_filtro_fecha(
    filtros: List[str],
    params: Dict[str, Any],
    disponibles: set[str],
    columna: str,
    valor: Optional[Any],
    param: str,
) -> None:
    if valor in (None, "") or not existe_columna(columna, disponibles):
        return
    filtros.append(f"TRY_CONVERT(DATE, [{columna}]) = TRY_CONVERT(DATE, :{param})")
    params[param] = valor


def agregar_filtro_si_no(
    filtros: List[str],
    params: Dict[str, Any],
    disponibles: set[str],
    columna_texto: str,
    columna_flag: str,
    valor: Optional[Any],
    param: str,
    excluir: bool = False,
) -> None:
    if valor in (None, ""):
        return

    valores = [v.upper() for v in valores_multiples(valor)]
    if len(valores) > 1 and existe_columna(columna_texto, disponibles):
        placeholders = []
        for index, item in enumerate(valores):
            key = f"{param}_{index}"
            placeholders.append(f":{key}")
            params[key] = item
        operador = "NOT IN" if excluir else "IN"
        filtros.append(f"{expr_texto_normalizado(columna_texto)} {operador} ({', '.join(placeholders)})")
        return

    valor_texto = valores[0] if valores else str(valor).strip().upper()
    if valor_texto in {"1", "0"} and existe_columna(columna_flag, disponibles):
        operador = "<>" if excluir else "="
        filtros.append(f"ISNULL([{columna_flag}], 0) {operador} :{param}")
        params[param] = int(valor_texto)
        return

    if existe_columna(columna_texto, disponibles):
        operador = "<>" if excluir else "="
        filtros.append(f"{expr_texto_normalizado(columna_texto)} {operador} :{param}")
        params[param] = valor_texto


def agregar_filtro_busqueda(
    filtros: List[str],
    params: Dict[str, Any],
    disponibles: set[str],
    busqueda: Optional[str],
) -> None:
    if not busqueda:
        return
    columnas = ["DNI", "IDCLIENTE", "TELEFONO", "NOMBRE_CLIENTE"]
    columnas_existentes = [col for col in columnas if existe_columna(col, disponibles)]
    if not columnas_existentes:
        return
    filtros.append("(" + " OR ".join(f"CONVERT(VARCHAR(255), [{col}]) LIKE :busqueda" for col in columnas_existentes) + ")")
    params["busqueda"] = f"%{busqueda.strip()}%"


def construir_filtros(disponibles: set[str], filtros_recibidos: Dict[str, Any]) -> tuple[str, Dict[str, Any]]:
    filtros: List[str] = []
    params: Dict[str, Any] = {}

    equivalencias = {
        "cartera": "CARTERA_SCORE",
        "dni": "DNI",
        "telefono": "TELEFONO",
        "condicion": "CONDICION",
        "foco": "FOCO",
        "prioridad_banco": "PRIORIDAD_BANCO",
        "prioridad": "PRIORIDAD_BANCO",
        "producto": "PRODUCTO_ORIGEN",
        "rango_capital": "RANGO_CAPITAL",
        "rango_edad": "RANGO_EDAD",
        "estado_civil": "ESTADO_CIVIL",
        "empresas_reportantes": "EMPRESAS_REPORTANTES",
        "mg_contacto_cliente": "MG_CONTACTO_CLIENTE",
        "mg_indicador_cliente": "MG_INDICADOR_CLIENTE",
        "ug_contacto_cliente": "UG_CONTACTO_CLIENTE",
        "ug_indicador_cliente": "UG_INDICADOR_CLIENTE",
        "estado_pdp": "ESTADO_PDP",
        "origen": "ORIGEN",
        "tipo_base": "TIPO_BASE",
        "prioridad_fono": "PRIORIDAD_CONTACTO",
        "prioridad_contacto": "PRIORIDAD_CONTACTO",
        "tipo_fono": "TIPO_FONO",
        "orden": "ORDEN",
        "timbrado": "TIMBRADO",
        "apagados_ivr": "APAGADO_IVR",
        "fallados_ivr": "FALLADOS_IVR",
        "marca_operativa": "MARCA_OPERATIVA",
        "zona": "ZONA",
    }

    equivalencias_candidatas = {
        "nuevo": ("NUEVO", "FLG_NUEVO", "ES_NUEVO"),
        "rango_mora": ("RANGO_MADURACION", "RANGO_MORA"),
        "rango_maduracion": ("RANGO_MADURACION", "RANGO_MORA"),
        "cuentas": ("CUENTAS", "CANT_CUENTAS", "NRO_CUENTAS", "NUM_CUENTAS"),
        "anio_cd_historico": ("ANIO_CD_HISTORICO", "ANIO_CD", "ULT_PERIODO_CONTACTO", "ULTIMO_PERIODO_CONTACTO"),
        "cluster_ml": ("CLUSTER_ML", "CLUSTER", "SEGMENTO_ML"),
        "flag_top": ("FLAG_TOP", "FLG_TOP"),
        "rango_campanas": ("RANGO_CAMPANAS", "RANGO_CAMPANA", "RANGO_CAMPANIAS", "RANGO_CAMPANIA"),
        "caseros": ("CASEROS", "CASERO", "FLG_CASERO"),
    }

    for param, columna in equivalencias.items():
        agregar_filtro_igual(filtros, params, disponibles, columna, filtros_recibidos.get(param), param)
        agregar_filtro_igual(
            filtros,
            params,
            disponibles,
            columna,
            filtros_recibidos.get(f"{param}_excluir"),
            f"{param}_excluir",
            excluir=True,
        )

    for param, candidatas in equivalencias_candidatas.items():
        columna = columna_catalogo_existente(param, candidatas, disponibles)
        if not columna:
            continue
        agregar_filtro_igual(filtros, params, disponibles, columna, filtros_recibidos.get(param), param)
        agregar_filtro_igual(
            filtros,
            params,
            disponibles,
            columna,
            filtros_recibidos.get(f"{param}_excluir"),
            f"{param}_excluir",
            excluir=True,
        )

    intentos_columna = columna_catalogo_existente("intentos_equivocados", "INTENTOS_EQUIVOCADO", disponibles)
    if intentos_columna:
        agregar_filtro_igual(
            filtros,
            params,
            disponibles,
            intentos_columna,
            filtros_recibidos.get("intentos_equivocados"),
            "intentos_equivocados",
        )

    agregar_filtro_minimo(filtros, params, disponibles, "TIMBRADO", filtros_recibidos.get("timbrado_min"), "timbrado_min")
    agregar_filtro_minimo(filtros, params, disponibles, "SCORE_TELEFONO", filtros_recibidos.get("score_min"), "score_min")
    agregar_filtro_fecha(filtros, params, disponibles, "FECHA_COMPROMISO", filtros_recibidos.get("fecha_compromiso"), "fecha_compromiso")
    agregar_filtro_si_no(filtros, params, disponibles, "WHATSAPP", "FLG_WHATSAPP_VALIDO", filtros_recibidos.get("whatsapp"), "whatsapp")
    agregar_filtro_si_no(filtros, params, disponibles, "WHATSAPP", "FLG_WHATSAPP_VALIDO", filtros_recibidos.get("whatsapp_excluir"), "whatsapp_excluir", excluir=True)
    agregar_filtro_si_no(filtros, params, disponibles, "OSIPTEL", "FLG_OSIPTEL_VALIDO", filtros_recibidos.get("osiptel"), "osiptel")
    agregar_filtro_si_no(filtros, params, disponibles, "OSIPTEL", "FLG_OSIPTEL_VALIDO", filtros_recibidos.get("osiptel_excluir"), "osiptel_excluir", excluir=True)
    if intentos_columna:
        agregar_filtro_maximo(filtros, params, disponibles, intentos_columna, filtros_recibidos.get("intentos_equivocado_max"), "intentos_equivocado_max")
    agregar_filtro_maximo(filtros, params, disponibles, "APAGADO_IVR", filtros_recibidos.get("apagado_ivr_max"), "apagado_ivr_max")
    agregar_filtro_maximo(filtros, params, disponibles, "FALLADOS_IVR", filtros_recibidos.get("fallados_ivr_max"), "fallados_ivr_max")
    agregar_filtro_busqueda(filtros, params, disponibles, filtros_recibidos.get("busqueda"))

    where_sql = "WHERE " + " AND ".join(filtros) if filtros else ""
    return where_sql, params


def buscar_score_telefonico(
    page=1,
    limit=50,
    **filtros_recibidos,
):
    page, limit, offset = normalizar_page_limit(page, limit)

    try:
        with engine_siscob.connect() as conn:
            disponibles = columnas_score_disponibles(conn)
            where_sql, params = construir_filtros(disponibles, filtros_recibidos)
            params.update({"offset": offset, "limit": limit})

            select_sql = ",\n            ".join(expr_columna(col, disponibles) for col in SELECT_COLUMNS)

            query_count = text(f"""
                SELECT COUNT(1) AS total
                FROM {TABLA_SCORE} WITH(NOLOCK)
                {where_sql}
            """)

            query_resumen = text(f"""
                SELECT
                    COUNT(DISTINCT {expr_valor('DNI', disponibles)}) AS clientes_unicos,
                    COUNT(1) AS telefonos_unicos,
                    SUM(CASE WHEN ISNULL({expr_valor('FLG_WHATSAPP_VALIDO', disponibles, '0')}, 0) = 1 THEN 1 ELSE 0 END) AS whatsapp_validos,
                    SUM(CASE WHEN ISNULL({expr_valor('FLG_TIMBRA_FUERTE', disponibles, '0')}, 0) = 1 THEN 1 ELSE 0 END) AS timbrado_fuerte,
                    SUM(CASE WHEN ISNULL({expr_valor('FLG_CEF_TELEFONO', disponibles, '0')}, 0) = 1 THEN 1 ELSE 0 END) AS contacto_efectivo,
                    SUM(ISNULL(TRY_CONVERT(DECIMAL(18,2), {expr_valor('CAPITAL', disponibles, '0')}), 0)) AS capital_total
                FROM {TABLA_SCORE} WITH(NOLOCK)
                {where_sql}
            """)

            score_order = "[SCORE_TELEFONO]" if existe_columna("SCORE_TELEFONO", disponibles) else "0"
            timbrado_order = "TRY_CONVERT(INT, [TIMBRADO])" if existe_columna("TIMBRADO", disponibles) else "0"
            dni_order = "[DNI]" if existe_columna("DNI", disponibles) else "1"
            telefono_order = "[TELEFONO]" if existe_columna("TELEFONO", disponibles) else "1"
            query_data = text(f"""
                SELECT
                    {select_sql}
                FROM {TABLA_SCORE} WITH(NOLOCK)
                {where_sql}
                ORDER BY
                    {score_order} DESC,
                    {timbrado_order} DESC,
                    {dni_order},
                    {telefono_order}
                OFFSET :offset ROWS FETCH NEXT :limit ROWS ONLY
            """)

            total = conn.execute(query_count, params).scalar() or 0
            resumen_row = conn.execute(query_resumen, params).fetchone()
            rows = conn.execute(query_data, params).fetchall()

        resumen = row_to_dict(resumen_row) if resumen_row else {}
        telefonos_unicos = resumen.get("telefonos_unicos") or 0
        whatsapp_validos = resumen.get("whatsapp_validos") or 0
        timbrado_fuerte = resumen.get("timbrado_fuerte") or 0
        contacto_efectivo = resumen.get("contacto_efectivo") or 0

        resumen["pct_whatsapp"] = round((whatsapp_validos * 100 / telefonos_unicos), 1) if telefonos_unicos else 0
        resumen["pct_timbrado_fuerte"] = round((timbrado_fuerte * 100 / telefonos_unicos), 1) if telefonos_unicos else 0
        resumen["pct_contacto_efectivo"] = round((contacto_efectivo * 100 / telefonos_unicos), 1) if telefonos_unicos else 0

        return {
            "ok": True,
            "page": page,
            "limit": limit,
            "total_registros": total,
            "total_paginas": int((total + limit - 1) / limit) if limit else 0,
            "resumen": resumen,
            "data": [row_to_dict(r) for r in rows],
        }

    except Exception as e:
        print("ERROR SCORE TELEFONICO BUSCAR:", e)
        raise


def obtener_telefonos_cliente(cartera, dni):
    query = text(f"""
        SELECT TOP 200 *
        FROM {TABLA_SCORE} WITH(NOLOCK)
        WHERE CARTERA_SCORE = :cartera
          AND DNI = :dni
        ORDER BY
            SCORE_TELEFONO DESC,
            TRY_CONVERT(INT, TIMBRADO) DESC,
            TELEFONO
    """)
    try:
        with engine_siscob.connect() as conn:
            rows = conn.execute(query, {"cartera": cartera, "dni": dni}).fetchall()
        return {"ok": True, "total": len(rows), "data": [row_to_dict(r) for r in rows]}
    except Exception as e:
        print("ERROR SCORE TELEFONICO CLIENTE:", e)
        raise


def columna_catalogo_existente(catalogo: str, campo: Any, disponibles: set[str]) -> Optional[str]:
    if catalogo == "intentos_equivocados":
        for candidata in ("INTENTOS_EQUIVOCADO", "INTENTOS_RECIENTES"):
            if existe_columna(candidata, disponibles):
                return candidata
        return None

    if isinstance(campo, (list, tuple)):
        for candidata in campo:
            if existe_columna(str(candidata), disponibles):
                return str(candidata)
        return None

    return campo if existe_columna(campo, disponibles) else None


def obtener_lista_distinct(conn, campo, idcartera=None):
    disponibles = columnas_score_disponibles(conn)

    if not existe_columna(campo, disponibles):
        return []

    params = {}
    filtros = [
        f"[{campo}] IS NOT NULL",
        f"LTRIM(RTRIM(CONVERT(VARCHAR(255), [{campo}]))) <> ''"
    ]

    where_cartera, params_cartera = construir_filtro_idcartera(disponibles, idcartera)

    if where_cartera:
        filtros.append(where_cartera.replace("WHERE ", "", 1))
        params.update(params_cartera)

    query = text(f"""
        SELECT TOP 500 valor
        FROM (
            SELECT DISTINCT
                LTRIM(RTRIM(CONVERT(VARCHAR(255), [{campo}]))) AS valor,
                TRY_CONVERT(DECIMAL(18,4), LTRIM(RTRIM(CONVERT(VARCHAR(255), [{campo}]))) ) AS valor_num
            FROM {TABLA_SCORE} WITH(NOLOCK)
            WHERE {" AND ".join(filtros)}
        ) catalogo
        WHERE valor IS NOT NULL
          AND valor <> ''
          AND UPPER(valor) NOT IN ('NULL', 'NULO', 'N/A', 'NA', '-', '--')
        ORDER BY
            CASE WHEN valor_num IS NULL THEN 1 ELSE 0 END,
            valor_num,
            valor
    """)

    rows = conn.execute(query, params).fetchall()
    return [r.valor for r in rows]


def obtener_catalogos_score(idcartera=None):
    try:
        with engine_siscob.connect() as conn:
            disponibles = columnas_score_disponibles(conn)
            result = {
                "ok": True,
                "idcartera": idcartera,
                "carteras": CARTERAS_SCORE_CONTEXTO,
            }

            for key, campo in CATALOGO_FIELDS.items():
                if key == "carteras":
                    continue

                campo_real = columna_catalogo_existente(key, campo, disponibles)

                if not campo_real:
                    result[key] = []
                    continue

                valores = obtener_lista_distinct(
                    conn=conn,
                    campo=campo_real,
                    idcartera=idcartera
                )

                result[key] = valores

            return result

    except Exception as e:
        print("ERROR SCORE TELEFONICO CATALOGOS:", e)
        raise


def refrescar_score_telefonico():
    try:
        with engine_siscob.begin() as conn:
            conn.execute(text("EXEC dbo.SP_REFRESCAR_SCORE_TELEFONICO_CRM"))
        return {"ok": True, "mensaje": "Score telefonico refrescado correctamente."}
    except Exception as e:
        print("ERROR SCORE TELEFONICO REFRESCAR:", e)
        raise


def exportar_resultados_score(
    idcartera: int,
    search: Optional[str] = None,
    order_by: Optional[str] = "SCORE_FINAL",
    order_dir: Optional[str] = "DESC",
    **filtros_recibidos,
) -> Dict[str, Any]:
    try:
        with engine_siscob.connect() as conn:
            disponibles = columnas_score_disponibles(conn)
            where_sql, params = construir_where_resultados(
                disponibles,
                idcartera,
                search,
                filtros_recibidos,
            )

            select_sql, _ = construir_select_resultados(disponibles)
            order_sql = construir_order_resultados(disponibles, order_by, order_dir)

            query = text(f"""
                SELECT TOP 200000
                    {select_sql}
                FROM {TABLA_SCORE} WITH(NOLOCK)
                {where_sql}
                ORDER BY {order_sql}
            """)

            rows = conn.execute(query, params).fetchall()

        data = [row_to_dict(row) for row in rows]
        df = pd.DataFrame(data)

        if df.empty:
            df = pd.DataFrame(columns=[
                "DNI",
                "IDCLIENTE",
                "NOMBRE_CLIENTE",
                "TELEFONO",
                "CAPITAL",
                "SCORE_FINAL",
                "ETIQUETA_SCORE",
                "TIMBRADO",
                "WHATSAPP",
                "OSIPTEL",
                "INTENTOS_RECIENTES",
                "MEJOR_RESULTADO",
                "ORDEN",
            ])

        output = BytesIO()

        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name="BASE_SCORE", index=False)

            ws = writer.sheets["BASE_SCORE"]
            ws.freeze_panes = "A2"

            for column_cells in ws.columns:
                max_length = 0
                column_letter = column_cells[0].column_letter

                for cell in column_cells:
                    value = "" if cell.value is None else str(cell.value)
                    max_length = max(max_length, len(value))

                ws.column_dimensions[column_letter].width = min(max_length + 2, 35)

        output.seek(0)

        fecha = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"score_telefonico_{idcartera}_{fecha}.xlsx"

        return {
            "filename": filename,
            "stream": output,
            "total": len(data),
        }

    except Exception as e:
        print("ERROR SCORE EXPORTAR:", e)
        raise
