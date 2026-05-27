from calendar import monthrange
from datetime import date, datetime
from typing import Dict, List, Optional

from sqlalchemy import bindparam, text

from app.core.db_siscob import engine_siscob


GRUPOS_CARTERA = {
    "MIBANCO": [112, 135, 143],
    "INTERBANK": [117, 137],
    "FINANCIERA_OH": [132],
    "COMPARTAMOS_VIGENTE": [126, 128, 133],
    "COMPARTAMOS_CASTIGO": [124, 144],
    "COMPARTAMOS": [124, 126, 128, 133, 144],
}


def obtener_resumen_metas(
    codmes: Optional[str] = None,
    tipo_medicion: Optional[str] = None,
    grupo_cartera: Optional[str] = None,
) -> Dict:
    codmes = normalizar_codmes(codmes)
    filas = consultar_metas(codmes, tipo_medicion, grupo_cartera)
    timing_base = obtener_timing_base(codmes)
    dias_habiles_mes = timing_base["dias_habiles_mes"]
    dias_habiles_transcurridos = timing_base["dias_habiles_transcurridos"]
    dias_habiles_restantes = timing_base["dias_habiles_restantes"]
    avance_esperado_pct = timing_base["avance_esperado_pct"]

    meta_total = sum(numero(row.get("meta_mensual")) for row in filas)
    avance_actual = sum(numero(row.get("avance_actual")) for row in filas)
    proyeccion_cierre_total = sum(calcular_proyeccion(numero(row.get("avance_actual")), dias_habiles_transcurridos, dias_habiles_mes) for row in filas)
    meta_recupero = sum(numero(row.get("meta_mensual")) for row in filas if texto(row.get("tipo_medicion")) == "RECUPERO")
    meta_contencion = sum(numero(row.get("meta_mensual")) for row in filas if texto(row.get("tipo_medicion")) == "CONTENCION")
    avance_recupero = sum(numero(row.get("avance_actual")) for row in filas if texto(row.get("tipo_medicion")) == "RECUPERO")
    avance_contencion = sum(numero(row.get("avance_actual")) for row in filas if texto(row.get("tipo_medicion")) == "CONTENCION")

    cumplimiento_global = dividir(avance_actual, meta_total)
    cumplimiento_estimado_global = dividir(proyeccion_cierre_total, meta_total)
    brecha_total = max(meta_total - avance_actual, 0)
    brecha_proyectada_total = max(meta_total - proyeccion_cierre_total, 0)
    esperado_a_la_fecha = meta_total * avance_esperado_pct
    desvio_pct = cumplimiento_global - avance_esperado_pct
    necesario_diario = calcular_necesario_diario(brecha_total, dias_habiles_restantes)

    return {
        "codmes": codmes,
        "meta_total": round(meta_total, 2),
        "avance_actual": round(avance_actual, 2),
        "cumplimiento_global": round(cumplimiento_global, 6),
        "proyeccion_cierre_total": round(proyeccion_cierre_total, 2),
        "cumplimiento_estimado_global": round(cumplimiento_estimado_global, 6),
        "brecha_total": round(brecha_total, 2),
        "brecha_proyectada_total": round(brecha_proyectada_total, 2),
        "meta_recupero": round(meta_recupero, 2),
        "meta_contencion": round(meta_contencion, 2),
        "avance_recupero": round(avance_recupero, 2),
        "avance_contencion": round(avance_contencion, 2),
        "comparativo_tipo": construir_comparativo_tipo(filas, dias_habiles_transcurridos, dias_habiles_mes),
        "timing": {
            "dia_actual": timing_base["fecha_referencia"].day,
            "dias_mes": timing_base["dias_mes"],
            "dias_restantes": timing_base["dias_restantes"],
            "dias_habiles_mes": dias_habiles_mes,
            "dias_habiles_transcurridos": dias_habiles_transcurridos,
            "dias_habiles_restantes": dias_habiles_restantes,
            "avance_esperado_pct": round(avance_esperado_pct, 6),
            "cumplimiento_actual_pct": round(cumplimiento_global, 6),
            "cumplimiento_estimado_pct": round(cumplimiento_estimado_global, 6),
            "desvio_pct": round(desvio_pct, 6),
            "necesario_diario": round(necesario_diario, 2),
            "esperado_a_la_fecha": round(esperado_a_la_fecha, 2),
        },
    }


def obtener_detalle_metas(
    codmes: Optional[str] = None,
    tipo_medicion: Optional[str] = None,
    grupo_cartera: Optional[str] = None,
) -> List[Dict]:
    codmes = normalizar_codmes(codmes)
    filas = consultar_metas(codmes, tipo_medicion, grupo_cartera)
    timing_base = obtener_timing_base(codmes)
    dias_habiles_mes = timing_base["dias_habiles_mes"]
    dias_habiles_transcurridos = timing_base["dias_habiles_transcurridos"]
    dias_habiles_restantes = timing_base["dias_habiles_restantes"]
    avance_esperado_pct = timing_base["avance_esperado_pct"]

    detalle = []
    for row in filas:
        meta_mensual = numero(row.get("meta_mensual"))
        avance_actual = numero(row.get("avance_actual"))
        cumplimiento_pct = dividir(avance_actual, meta_mensual)
        esperado_a_la_fecha = meta_mensual * avance_esperado_pct
        desvio = avance_actual - esperado_a_la_fecha
        brecha = max(meta_mensual - avance_actual, 0)
        proyeccion_cierre = calcular_proyeccion(avance_actual, dias_habiles_transcurridos, dias_habiles_mes)
        cumplimiento_estimado_pct = dividir(proyeccion_cierre, meta_mensual)
        brecha_proyectada = max(meta_mensual - proyeccion_cierre, 0)
        necesario_diario = calcular_necesario_diario(brecha, dias_habiles_restantes)

        detalle.append({
            "codmes": row.get("codmes") or codmes,
            "idcartera": row.get("idcartera"),
            "cartera": row.get("cartera"),
            "tipo_medicion": row.get("tipo_medicion"),
            "tipo_producto": row.get("tipo_producto"),
            "meta_mensual": round(meta_mensual, 2),
            "avance_actual": round(avance_actual, 2),
            "cumplimiento_pct": round(cumplimiento_pct, 6),
            "esperado_a_la_fecha": round(esperado_a_la_fecha, 2),
            "desvio": round(desvio, 2),
            "brecha": round(brecha, 2),
            "proyeccion_cierre": round(proyeccion_cierre, 2),
            "cumplimiento_estimado_pct": round(cumplimiento_estimado_pct, 6),
            "brecha_proyectada": round(brecha_proyectada, 2),
            "necesario_diario": round(necesario_diario, 2),
            "estado": calcular_estado(meta_mensual, avance_actual, proyeccion_cierre),
            "ultimo_corte": row.get("ultimo_corte") or row.get("fecha_corte"),
            "registros": int(numero(row.get("registros"))),
        })

    return detalle


def consultar_metas(
    codmes: str,
    tipo_medicion: Optional[str] = None,
    grupo_cartera: Optional[str] = None,
) -> List[Dict]:
    filtros = [
        "m.codmes = :codmes",
        "ISNULL(m.activo, 0) = 1",
        "ISNULL(m.es_meta_principal, 0) = 1",
    ]
    params = {"codmes": codmes}

    tipo = texto(tipo_medicion)
    if tipo in {"RECUPERO", "CONTENCION"}:
        filtros.append("UPPER(LTRIM(RTRIM(m.tipo_medicion))) = :tipo_medicion")
        params["tipo_medicion"] = tipo

    ids_grupo = obtener_ids_grupo_cartera(grupo_cartera)
    if ids_grupo:
        filtros.append("m.idcartera IN :ids_grupo")
        params["ids_grupo"] = tuple(ids_grupo)

    query = text(f"""
        WITH pagos_activos AS (
            SELECT
                codmes,
                idcartera,
                SUM(ISNULL(monto_pago_soles, ISNULL(monto_pago, 0))) AS monto_pago_activo,
                SUM(ISNULL(capital_contenido, 0)) AS capital_contenido_activo,
                COUNT(1) AS registros_pago,
                MAX(fecha_corte) AS ultimo_corte
            FROM CobAuto.dbo.PAGOS_BI_NORMALIZADO WITH(NOLOCK)
            WHERE codmes = :codmes
                AND ISNULL(activo, 0) = 1
            GROUP BY codmes, idcartera
        )
        SELECT
            m.*,
            ISNULL(p.monto_pago_activo, 0) AS pago_monto_pago,
            ISNULL(p.capital_contenido_activo, 0) AS pago_capital_contenido,
            ISNULL(p.registros_pago, 0) AS pago_registros,
            p.ultimo_corte AS pago_ultimo_corte
        FROM CobAuto.dbo.VW_METAS_VS_AVANCE_ACTIVO m WITH(NOLOCK)
        LEFT JOIN pagos_activos p
            ON p.codmes = m.codmes
            AND p.idcartera = m.idcartera
        WHERE {' AND '.join(filtros)}
        ORDER BY m.tipo_medicion, m.cartera
    """)

    if ids_grupo:
        query = query.bindparams(bindparam("ids_grupo", expanding=True))

    with engine_siscob.connect() as conn:
        rows = conn.execute(query, params).mappings().all()

    return [normalizar_fila(dict(row)) for row in rows]


def normalizar_fila(row: Dict) -> Dict:
    normalizada = {str(key).lower(): serializar_valor(value) for key, value in row.items()}
    normalizada["avance_actual"] = (
        normalizada.get("pago_monto_pago")
        if texto(normalizada.get("tipo_medicion")) == "RECUPERO"
        else normalizada.get("pago_capital_contenido")
    )
    normalizada["monto_pago"] = normalizada.get("pago_monto_pago")
    normalizada["capital_contenido"] = normalizada.get("pago_capital_contenido")
    normalizada["registros"] = normalizada.get("pago_registros")
    normalizada["ultimo_corte"] = normalizada.get("pago_ultimo_corte")
    return normalizada


def obtener_ids_grupo_cartera(grupo_cartera: Optional[str]) -> List[int]:
    grupo = texto(grupo_cartera)
    return GRUPOS_CARTERA.get(grupo, [])


def obtener_timing_base(codmes: str):
    hoy_real = date.today()
    year = int(codmes[:4])
    month = int(codmes[4:6])
    dias_mes = monthrange(year, month)[1]
    inicio = date(year, month, 1)
    fin = date(year, month, dias_mes)

    if hoy_real.year == year and hoy_real.month == month:
        fecha_referencia = hoy_real
    elif hoy_real < inicio:
        fecha_referencia = date(year, month, 1)
    else:
        fecha_referencia = fin

    dias_habiles_mes = contar_dias_habiles(inicio, fin)
    dias_habiles_transcurridos = contar_dias_habiles(inicio, min(fecha_referencia, fin))
    dias_habiles_restantes = contar_dias_habiles(fecha_referencia, fin, incluir_inicio=False)
    dias_restantes = max(dias_mes - fecha_referencia.day, 0)
    avance_esperado_pct = dividir(dias_habiles_transcurridos, dias_habiles_mes)

    return {
        "fecha_referencia": fecha_referencia,
        "dias_mes": dias_mes,
        "dias_restantes": dias_restantes,
        "dias_habiles_mes": dias_habiles_mes,
        "dias_habiles_transcurridos": dias_habiles_transcurridos,
        "dias_habiles_restantes": dias_habiles_restantes,
        "avance_esperado_pct": avance_esperado_pct,
    }


def contar_dias_habiles(inicio: date, fin: date, incluir_inicio: bool = True) -> float:
    return contar_jornadas_habiles(inicio, fin, incluir_inicio)


def contar_jornadas_habiles(inicio: date, fin: date, incluir_inicio: bool = True) -> float:
    if fin < inicio:
        return 0.0

    cursor = inicio if incluir_inicio else avanzar_dia(inicio)
    total = 0.0

    while cursor <= fin:
        total += peso_jornada(cursor)
        cursor = avanzar_dia(cursor)

    return total


def peso_jornada(valor: date) -> float:
    if valor.weekday() < 5:
        return 1.0
    if valor.weekday() == 5:
        return 0.5
    return 0.0


def avanzar_dia(valor: date) -> date:
    return date.fromordinal(valor.toordinal() + 1)


def calcular_proyeccion(avance_actual: float, dias_transcurridos: int, dias_mes: int) -> float:
    if avance_actual <= 0 or dias_transcurridos <= 0 or dias_mes <= 0:
        return 0
    return dividir(avance_actual, dias_transcurridos) * dias_mes


def calcular_necesario_diario(brecha: float, dias_restantes: int) -> float:
    if brecha <= 0:
        return 0
    if dias_restantes <= 0:
        return brecha
    return dividir(brecha, dias_restantes)


def construir_comparativo_tipo(filas: List[Dict], dias_transcurridos: int, dias_mes: int) -> List[Dict]:
    comparativo = []

    for tipo_medicion in ["RECUPERO", "CONTENCION"]:
        filas_tipo = [row for row in filas if texto(row.get("tipo_medicion")) == tipo_medicion]
        meta = sum(numero(row.get("meta_mensual")) for row in filas_tipo)
        avance = sum(numero(row.get("avance_actual")) for row in filas_tipo)
        proyeccion = sum(calcular_proyeccion(numero(row.get("avance_actual")), dias_transcurridos, dias_mes) for row in filas_tipo)
        brecha_proyectada = max(meta - proyeccion, 0)

        if meta <= 0 and avance <= 0 and proyeccion <= 0:
            continue

        comparativo.append({
            "tipo_medicion": tipo_medicion,
            "meta": round(meta, 2),
            "avance_actual": round(avance, 2),
            "proyeccion_cierre": round(proyeccion, 2),
            "cumplimiento_actual_pct": round(dividir(avance, meta), 6),
            "cumplimiento_estimado_pct": round(dividir(proyeccion, meta), 6),
            "brecha_proyectada": round(brecha_proyectada, 2),
            "estado": calcular_estado(meta, avance, proyeccion) if meta > 0 else "-",
        })

    return comparativo


def calcular_estado(meta_mensual: float, avance_actual: float, proyeccion_cierre: float) -> str:
    if avance_actual >= meta_mensual:
        return "SUPERADO"
    if proyeccion_cierre >= meta_mensual:
        return "EN META"
    if proyeccion_cierre >= meta_mensual * 0.90:
        return "RIESGO"
    return "CRITICO"


def normalizar_codmes(codmes: Optional[str]) -> str:
    valor = "".join(ch for ch in str(codmes or "") if ch.isdigit())
    if len(valor) == 6:
        return valor
    hoy = date.today()
    return f"{hoy.year}{hoy.month:02d}"


def texto(value) -> str:
    return str(value or "").strip().upper()


def numero(value) -> float:
    try:
        if value is None:
            return 0.0
        return float(str(value).replace(",", ""))
    except Exception:
        return 0.0


def dividir(numerador: float, denominador: float) -> float:
    return numerador / denominador if denominador else 0.0


def serializar_valor(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value
