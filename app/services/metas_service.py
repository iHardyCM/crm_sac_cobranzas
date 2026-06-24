from calendar import monthrange
from datetime import date, datetime
from io import BytesIO
import re
import unicodedata
from typing import Dict, List, Optional, Tuple

import pandas as pd
from sqlalchemy import bindparam, text

from app.core.db_siscob import engine_siscob


GRUPOS_CARTERA = {
    "MIBANCO": [0, 112, 135, 143],
    "INTERBANK": [117, 137],
    "FINANCIERA_OH": [132, 148],
    "COMPARTAMOS_VIGENTE": [126, 128, 133],
    "COMPARTAMOS_CASTIGO": [124, 144],
    "COMPARTAMOS": [124, 126, 128, 133, 144],
}

CARTERAS_MIBANCO_META = {
    "BIZNESCOB": (112, "MIBANCO"),
    "BIZNESCOB - IRRE": (0, "MIBANCO IRRE"),
}

COLUMNAS_MIBANCO_META = {
    "funcionario": ["funcionario", "funcionarios"],
    "ant_castigo": ["ant_castigo", "ant castigo", "antiguedad", "antigüedad"],
    "ran_ticket": ["ran_ticket", "ran ticket", "rango ticket", "ticket"],
    "cluster": ["clust", "cluster"],
    "monto_meta": ["monto_meta", "monto meta", "meta", "monto"],
}


def importar_metas_mibanco(
    codmes: Optional[str],
    archivo_nombre: str,
    contenido: bytes,
    usuario: Optional[str] = None,
) -> Dict:
    codmes_limpio = normalizar_codmes(codmes)
    if not contenido:
        raise ValueError("Archivo obligatorio.")

    asegurar_columnas_metas_mibanco()
    df = leer_archivo_metas(archivo_nombre, contenido)
    columnas = mapear_columnas_mibanco(df)
    faltantes = [campo for campo in COLUMNAS_MIBANCO_META if campo not in columnas]
    if faltantes:
        raise ValueError("Columnas obligatorias faltantes: " + ", ".join(faltantes))

    detalle, errores = normalizar_metas_mibanco(df, columnas, codmes_limpio)
    if not detalle:
        raise ValueError("No se encontraron filas validas para importar.")

    usuario_limpio = str(usuario or "SIN_USUARIO").strip()[:50]
    ids_mibanco = tuple(sorted({row["idcartera"] for row in detalle}))
    for row in detalle:
        row["usuario_registro"] = usuario_limpio
        row["fecha_registro"] = datetime.now()
        row["archivo_origen"] = archivo_nombre[:255]

    with engine_siscob.begin() as conn:
        query_desactivar = text("""
            UPDATE CobAuto.dbo.METAS_MENSUALES
            SET activo = 0,
                usuario_modificacion = :usuario,
                fecha_modificacion = GETDATE()
            WHERE codmes = :codmes
              AND idcartera IN :ids_mibanco
              AND UPPER(LTRIM(RTRIM(tipo_medicion))) = 'RECUPERO'
              AND ISNULL(activo, 0) = 1
        """).bindparams(bindparam("ids_mibanco", expanding=True))
        result = conn.execute(query_desactivar, {
            "codmes": int(codmes_limpio),
            "ids_mibanco": ids_mibanco,
            "usuario": usuario_limpio,
        })
        reemplazadas = int(result.rowcount or 0)

        insertar_metas_mensuales(conn, detalle)

    return {
        "ok": True,
        "codmes": codmes_limpio,
        "archivo": archivo_nombre,
        "filas_archivo": int(len(df)),
        "filas_validas": len(detalle),
        "filas_error": len(errores),
        "metas_principales": len(detalle),
        "metas_reemplazadas": reemplazadas,
        "total_meta": round(sum(numero(row["meta_mensual"]) for row in detalle), 2),
        "detalle_por_cartera": [
            {
                "idcartera": idcartera,
                "cartera": cartera,
                "meta_mensual": round(sum(numero(row["meta_mensual"]) for row in rows), 2),
            }
            for (idcartera, cartera), rows in agrupar_detalle_metas_mibanco(detalle).items()
        ],
        "errores_preview": errores[:10],
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
    asegurar_columnas_metas_mibanco()
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
        SELECT
            m.*,
            ISNULL(p.monto_pago_activo, 0) AS pago_monto_pago,
            ISNULL(p.capital_contenido_activo, 0) AS pago_capital_contenido,
            ISNULL(p.registros_pago, 0) AS pago_registros,
            p.ultimo_corte AS pago_ultimo_corte
        FROM CobAuto.dbo.METAS_MENSUALES m WITH(NOLOCK)
        OUTER APPLY (
            SELECT
                SUM(ISNULL(pb.monto_pago_soles, ISNULL(pb.monto_pago, 0))) AS monto_pago_activo,
                SUM(ISNULL(pb.capital_contenido, 0)) AS capital_contenido_activo,
                COUNT(1) AS registros_pago,
                MAX(pb.fecha_corte) AS ultimo_corte
            FROM CobAuto.dbo.PAGOS_BI_NORMALIZADO pb WITH(NOLOCK)
            LEFT JOIN Desarrollo.dbo.act_mibanco_castigo mb WITH(NOLOCK)
                ON NULLIF(LTRIM(RTRIM(ISNULL(m.funcionario, ''))), '') IS NOT NULL
               AND (
                    REPLACE(LTRIM(RTRIM(ISNULL(CAST(mb.NRO_DOC AS VARCHAR(100)), ''))), CHAR(160), '')
                    = REPLACE(LTRIM(RTRIM(ISNULL(CAST(pb.documento AS VARCHAR(100)), ''))), CHAR(160), '')
                    OR REPLACE(LTRIM(RTRIM(ISNULL(CAST(mb.NRO_DOC AS VARCHAR(100)), ''))), CHAR(160), '')
                    = REPLACE(LTRIM(RTRIM(ISNULL(CAST(pb.dni AS VARCHAR(100)), ''))), CHAR(160), '')
               )
               AND REPLACE(LTRIM(RTRIM(ISNULL(CAST(mb.COD_PRE AS VARCHAR(100)), ''))), CHAR(160), '')
                   = REPLACE(LTRIM(RTRIM(ISNULL(CAST(pb.num_operacion AS VARCHAR(100)), ''))), CHAR(160), '')
            WHERE pb.codmes = m.codmes
              AND ISNULL(pb.activo, 0) = 1
              AND (
                    (NULLIF(LTRIM(RTRIM(ISNULL(m.funcionario, ''))), '') IS NOT NULL
                     AND UPPER(LTRIM(RTRIM(ISNULL(NULLIF(pb.usuario_asignado, ''), ISNULL(mb.USU_FIN, ''))))) = UPPER(LTRIM(RTRIM(m.funcionario))))
                    OR
                    (NULLIF(LTRIM(RTRIM(ISNULL(m.funcionario, ''))), '') IS NULL
                     AND pb.idcartera = m.idcartera)
                  )
              AND (
                    NULLIF(LTRIM(RTRIM(ISNULL(m.cluster_meta, ''))), '') IS NULL
                    OR UPPER(LTRIM(RTRIM(ISNULL(NULLIF(pb.segmentacion, ''), ISNULL(mb.CLUSTER_RFP, ''))))) = UPPER(LTRIM(RTRIM(m.cluster_meta)))
                  )
              AND (
                    NULLIF(LTRIM(RTRIM(ISNULL(m.cuenta_meta, ''))), '') IS NULL
                    OR REPLACE(LTRIM(RTRIM(ISNULL(CAST(pb.num_cuenta AS VARCHAR(100)), ''))), CHAR(160), '') = REPLACE(LTRIM(RTRIM(m.cuenta_meta)), CHAR(160), '')
                    OR REPLACE(LTRIM(RTRIM(ISNULL(CAST(pb.cod_credito AS VARCHAR(100)), ''))), CHAR(160), '') = REPLACE(LTRIM(RTRIM(m.cuenta_meta)), CHAR(160), '')
                    OR REPLACE(LTRIM(RTRIM(ISNULL(CAST(pb.num_operacion AS VARCHAR(100)), ''))), CHAR(160), '') = REPLACE(LTRIM(RTRIM(m.cuenta_meta)), CHAR(160), '')
                  )
              AND (
                    NULLIF(LTRIM(RTRIM(ISNULL(m.clasificacion_sbs, ''))), '') IS NULL
                    OR UPPER(LTRIM(RTRIM(ISNULL(pb.clasificacion_sbs, '')))) = UPPER(LTRIM(RTRIM(m.clasificacion_sbs)))
                  )
              AND (
                    NULLIF(LTRIM(RTRIM(ISNULL(m.tipo_producto, ''))), '') IS NULL
                    OR UPPER(LTRIM(RTRIM(ISNULL(pb.tipo_producto, '')))) = UPPER(LTRIM(RTRIM(m.tipo_producto)))
                  )
              AND (
                    ISNULL(m.excluir_impulso, 0) = 0
                    OR UPPER(LTRIM(RTRIM(ISNULL(pb.tipo_producto, '')))) <> 'IMPULSO'
                  )
        ) p
        WHERE {' AND '.join(filtros)}
        ORDER BY m.tipo_medicion, m.cartera
    """)

    if ids_grupo:
        query = query.bindparams(bindparam("ids_grupo", expanding=True))

    with engine_siscob.connect() as conn:
        rows = conn.execute(query, params).mappings().all()

    return [normalizar_fila(dict(row)) for row in rows]


def asegurar_columnas_metas_mibanco() -> None:
    ddl = text("""
        IF COL_LENGTH('CobAuto.dbo.METAS_MENSUALES', 'funcionario') IS NULL
            ALTER TABLE CobAuto.dbo.METAS_MENSUALES ADD funcionario VARCHAR(100) NULL

        IF COL_LENGTH('CobAuto.dbo.METAS_MENSUALES', 'ant_castigo') IS NULL
            ALTER TABLE CobAuto.dbo.METAS_MENSUALES ADD ant_castigo VARCHAR(50) NULL

        IF COL_LENGTH('CobAuto.dbo.METAS_MENSUALES', 'ran_ticket') IS NULL
            ALTER TABLE CobAuto.dbo.METAS_MENSUALES ADD ran_ticket VARCHAR(50) NULL

        IF COL_LENGTH('CobAuto.dbo.METAS_MENSUALES', 'cluster_meta') IS NULL
            ALTER TABLE CobAuto.dbo.METAS_MENSUALES ADD cluster_meta VARCHAR(50) NULL

        IF COL_LENGTH('CobAuto.dbo.METAS_MENSUALES', 'cuenta_meta') IS NULL
            ALTER TABLE CobAuto.dbo.METAS_MENSUALES ADD cuenta_meta VARCHAR(100) NULL

        IF COL_LENGTH('CobAuto.dbo.METAS_MENSUALES', 'archivo_origen') IS NULL
            ALTER TABLE CobAuto.dbo.METAS_MENSUALES ADD archivo_origen VARCHAR(255) NULL
    """)
    with engine_siscob.begin() as conn:
        conn.execute(ddl)


def leer_archivo_metas(archivo_nombre: str, contenido: bytes) -> pd.DataFrame:
    extension = archivo_nombre.lower().rsplit(".", 1)[-1] if "." in archivo_nombre else ""
    stream = BytesIO(contenido)

    if extension in {"csv", "txt"}:
        try:
            return pd.read_csv(stream, dtype=str)
        except Exception:
            stream.seek(0)
            return pd.read_csv(stream, sep=";", dtype=str)

    if extension == "xls":
        return pd.read_excel(stream, dtype=str, engine="xlrd")

    return pd.read_excel(stream, dtype=str, engine="openpyxl")


def mapear_columnas_mibanco(df: pd.DataFrame) -> Dict[str, str]:
    columnas = {normalizar_columna_meta(col): str(col) for col in df.columns}
    resultado = {}

    for campo, aliases in COLUMNAS_MIBANCO_META.items():
        for alias in aliases:
            normalizado = normalizar_columna_meta(alias)
            if normalizado in columnas:
                resultado[campo] = columnas[normalizado]
                break

    return resultado


def normalizar_metas_mibanco(
    df: pd.DataFrame,
    columnas: Dict[str, str],
    codmes: str,
) -> Tuple[List[Dict], List[Dict]]:
    detalle = []
    errores = []

    for idx, row in df.iterrows():
        fila_excel = int(idx) + 2
        funcionario = limpiar_texto_meta(row.get(columnas["funcionario"]))
        ant_castigo = limpiar_texto_meta(row.get(columnas["ant_castigo"]))
        ran_ticket = limpiar_texto_meta(row.get(columnas["ran_ticket"]))
        cluster = limpiar_texto_meta(row.get(columnas["cluster"]))
        monto = numero(row.get(columnas["monto_meta"]))

        if not funcionario and not ant_castigo and not ran_ticket and not cluster and monto <= 0:
            continue

        idcartera, cartera = cartera_mibanco_por_funcionario(funcionario)
        motivos = []
        if not idcartera:
            motivos.append(f"Funcionario no mapeado: {funcionario or '-'}")
        if monto <= 0:
            motivos.append("Monto meta invalido o cero.")
        if not cluster:
            motivos.append("Cluster vacio.")

        if motivos:
            errores.append({
                "fila_excel": fila_excel,
                "funcionario": funcionario,
                "cluster": cluster,
                "error": " | ".join(motivos),
            })
            continue

        detalle.append({
            "codmes": int(codmes),
            "idcartera": idcartera,
            "cartera": cartera,
            "tipo_medicion": "RECUPERO",
            "meta_mensual": monto,
            "tipo_producto": None,
            "clasificacion_sbs": None,
            "segmentacion": None,
            "excluir_impulso": 0,
            "es_meta_principal": 1,
            "activo": 1,
            "observacion": f"Meta MiBanco detalle {cluster} | {ant_castigo} | {ran_ticket}",
            "funcionario": funcionario,
            "ant_castigo": ant_castigo,
            "ran_ticket": ran_ticket,
            "cluster_meta": cluster,
        })

    return detalle, errores


def agrupar_detalle_metas_mibanco(detalle: List[Dict]) -> Dict[Tuple[int, str], List[Dict]]:
    grupos: Dict[Tuple[int, str], List[Dict]] = {}
    for row in detalle:
        key = (int(row["idcartera"]), str(row["cartera"]))
        grupos.setdefault(key, []).append(row)
    return grupos


def insertar_metas_mensuales(conn, filas: List[Dict]) -> None:
    if not filas:
        return

    columnas_disponibles = columnas_tabla_metas(conn, "METAS_MENSUALES")
    columnas = [
        "codmes", "idcartera", "cartera", "tipo_medicion", "meta_mensual",
        "tipo_producto", "clasificacion_sbs", "segmentacion", "excluir_impulso",
        "es_meta_principal", "activo", "observacion", "usuario_registro",
        "fecha_registro", "funcionario", "ant_castigo", "ran_ticket",
        "cluster_meta", "cuenta_meta", "archivo_origen",
    ]
    columnas = [col for col in columnas if col in columnas_disponibles]
    columnas_sql = ", ".join(columnas)
    valores_sql = ", ".join(f":{col}" for col in columnas)

    payload = []
    for row in filas:
        item = {col: row.get(col) for col in columnas}
        item.setdefault("usuario_registro", row.get("usuario_registro") or "SIN_USUARIO")
        payload.append(item)

    conn.execute(text(f"""
        INSERT INTO CobAuto.dbo.METAS_MENSUALES ({columnas_sql})
        VALUES ({valores_sql})
    """), payload)


def columnas_tabla_metas(conn, table: str) -> set:
    rows = conn.execute(text("""
        SELECT LOWER(COLUMN_NAME) AS column_name
        FROM CobAuto.INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = 'dbo'
          AND TABLE_NAME = :table
    """), {"table": table}).fetchall()
    return {row.column_name for row in rows}


def cartera_mibanco_por_funcionario(funcionario: str) -> Tuple[Optional[int], Optional[str]]:
    valor = re.sub(r"\s+", " ", str(funcionario or "").strip().upper())
    valor_compacto = re.sub(r"[^A-Z0-9]+", "", valor)
    if "IRRE" in valor:
        return CARTERAS_MIBANCO_META["BIZNESCOB - IRRE"]
    if valor_compacto in {"BIZNESCOB", "BIZNECOB"}:
        return CARTERAS_MIBANCO_META["BIZNESCOB"]
    return None, None


def limpiar_texto_meta(value) -> str:
    if value is None or pd.isna(value):
        return ""
    return re.sub(r"\s+", " ", str(value).replace("\u00a0", " ").strip())


def normalizar_columna_meta(value) -> str:
    texto_valor = str(value or "").strip().lower()
    texto_valor = unicodedata.normalize("NFKD", texto_valor)
    texto_valor = "".join(char for char in texto_valor if not unicodedata.combining(char))
    texto_valor = re.sub(r"[^a-z0-9]+", "_", texto_valor)
    return re.sub(r"_+", "_", texto_valor).strip("_")


def normalizar_fila(row: Dict) -> Dict:
    normalizada = {str(key).lower(): serializar_valor(value) for key, value in row.items()}
    if normalizada.get("cluster_meta") and not normalizada.get("segmentacion"):
        normalizada["segmentacion"] = normalizada.get("cluster_meta")
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
