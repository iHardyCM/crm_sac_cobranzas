from datetime import date, datetime, timedelta
from io import BytesIO
import json
import math
import os
import re
from typing import Dict, List, Optional, Tuple

import pandas as pd
from sqlalchemy import text

from app.core.db_siscob import engine_siscob


FORMATS = {
    "MIBANCO": {
        "sheet": "DATOS",
        "required": ["USU_FIN", "PAG_REA_SOL", "FEC_ULT_PAG", "COD_CLI"],
        "filter_col": "USU_FIN",
        "filter_val": "BIZNESCOB",
        "monto": "PAG_REA_SOL",
        "monto_original": "PAG_REA",
        "fecha": "FEC_ULT_PAG",
        "fecha_yyyymmdd": True,
        "idcartera": 112,
        "tipo_medicion": "RECUPERO",
    },
    "INTERBANK": {
        "sheet": "PAGOS",
        "required_extra": ["FECHA_AMORT"],
        "required": ["ESTUDIO", "PERIODOCAMPAÑA", "TOTAL_PAGADOMN"],
        "filter_col": "ESTUDIO",
        "filter_val": "BIZNESCOB",
        "monto": "TOTAL_PAGADOMN",
        "fecha": "FECHA_AMORT",
        "codmes": "PERIODOCAMPAÑA",
        "idcartera": 117,
        "tipo_medicion": "RECUPERO",
    },
    "FINANCIERA_OH": {
        "required": ["GESTOR", "SUMA_PAGOS_MES", "FECHA_PROCESO"],
        "filter_col": "GESTOR",
        "filter_val": "BIZNESCOB",
        "monto": "SUMA_PAGOS_MES",
        "fecha": "FECHA_PROCESO",
        "idcartera": 132,
        "tipo_medicion": "RECUPERO",
    },
    "COMPARTAMOS_CASTIGO": {
        "sheet": "Caja",
        "required": ["USUARIO_2", "Monto", "FECHA_DE_MOVIMIENTO", "LinNeg"],
        "filter_col": "USUARIO_2",
        "filter_val": "EXTERNO - BIZNESCOB",
        "monto": "Monto",
        "fecha": "FECHA_DE_MOVIMIENTO",
        "tipo_medicion": "RECUPERO",
        "linneg": {"IND": 124, "GRU": 144, "CCM": 144},
    },
    "COMPARTAMOS_VIGENTE": {
        "sheet": "base",
        "required": ["Usuario_MesAsig", "MesAsig", "LinNeg", "Recaudo", "Sdo_CON_REC"],
        "filter_col": "Usuario_MesAsig",
        "filter_val": "EXTERNO - BIZNESCOB",
        "monto": "Recaudo",
        "capital": "Sdo_CON_REC",
        "fecha": "MesAsig",
        "codmes": "MesAsig",
        "tipo_medicion": "CONTENCION",
        "linneg": {"IND": 126, "CCM": 128, "GRU": 133, "CSM": 133},
    },
}


CARTERAS = {
    112: "MIBANCO",
    143: "MIBANCO 2",
    135: "MIBANCO VIGENTE",
    117: "INTERBANK",
    132: "FINANCIERA OH",
    124: "COMPARTAMOS CASTIGO INDIVIDUAL",
    144: "COMPARTAMOS CASTIGO GRUPAL",
    126: "COMPARTAMOS VIGENTE INDIVIDUAL",
    128: "COMPARTAMOS VIGENTE CCM",
    133: "COMPARTAMOS VIGENTE GRUPAL",
}


def validar_archivo_pago(
    formato: str,
    filename: str,
    content: bytes,
    usuario_carga: Optional[str] = None,
):
    formato = normalizar_formato(formato)
    config = FORMATS[formato]

    df = leer_archivo(formato, filename, content)
    df = limpiar_columnas_dataframe(df)
    validar_columnas(df, config["required"] + config.get("required_extra", []))
    df = aplicar_filtros_formato(df, formato, config)

    registros = normalizar_registros(df, formato, filename)
    resumen = construir_resumen_previo(formato, filename, registros)
    resumen["usuario_carga"] = (usuario_carga or "").strip() or None

    with engine_siscob.begin() as conn:
        id_importacion = crear_importacion(conn, resumen)
        for registro in registros:
            registro["id_importacion"] = id_importacion
        insertar_staging(conn, registros)

    resumen["id_importacion"] = id_importacion
    return resumen


def confirmar_importacion(id_importacion: int):
    with engine_siscob.begin() as conn:
        staging = obtener_staging_valido(conn, id_importacion)

        if not staging:
            raise ValueError("No hay filas validas para publicar.")

        grupos = {
            (
                row.get("formato"),
                row.get("codmes"),
                row.get("idcartera"),
            )
            for row in staging
        }

        for formato, codmes, idcartera in grupos:
            desactivar_bi_anterior(conn, formato, codmes, idcartera)

        insertados = publicar_bi(conn, staging)
        totales = calcular_totales_staging(conn, id_importacion)
        actualizar_importacion_publicada(conn, id_importacion, totales)
        actualizar_importaciones_reemplazadas(conn, id_importacion, grupos)

    return {
        "ok": True,
        "id_importacion": id_importacion,
        "filas_publicadas": insertados,
        "grupos_reemplazados": len(grupos),
        **totales,
    }


def listar_importaciones(
    limit: int = 50,
    codmes: Optional[str] = None,
    solo_activos: bool = False,
):
    filtros = []
    params = {"limit": limit}

    if codmes:
        filtros.append("codmes = :codmes")
        params["codmes"] = codmes

    if solo_activos:
        filtros.append("ISNULL(activo, 0) = 1")

    where_sql = f"WHERE {' AND '.join(filtros)}" if filtros else ""
    query = text(f"""
        SELECT TOP (:limit) *
        FROM dbo.PAGOS_IMPORTACION WITH(NOLOCK)
        {where_sql}
        ORDER BY id_importacion DESC
    """)
    with engine_siscob.connect() as conn:
        rows = conn.execute(query, params).mappings().all()
    return [normalizar_importacion_historial(dict(row)) for row in rows]


def obtener_resumen_pagos():
    query = text("""
        SELECT *
        FROM dbo.VW_PAGOS_RESUMEN_CARTERA WITH(NOLOCK)
    """)
    with engine_siscob.connect() as conn:
        rows = conn.execute(query).mappings().all()
    return [serializar_dict(dict(row)) for row in rows]


def obtener_cortes_activos(codmes: Optional[str] = None):
    params = {}
    filtros = ["ISNULL(activo, 0) = 1"]

    if codmes:
        filtros.append("codmes = :codmes")
        params["codmes"] = codmes

    query = text(f"""
        SELECT
            formato,
            codmes,
            idcartera,
            MAX(cartera) AS cartera,
            MAX(tipo_medicion) AS tipo_medicion,
            COUNT(*) AS registros,
            SUM(ISNULL(monto_pago_soles, 0)) AS total_pago,
            SUM(ISNULL(capital_contenido, 0)) AS total_capital_contenido,
            MAX(fecha_corte) AS fecha_corte
        FROM dbo.PAGOS_BI_NORMALIZADO WITH(NOLOCK)
        WHERE {' AND '.join(filtros)}
        GROUP BY formato, codmes, idcartera
        ORDER BY formato, codmes, idcartera
    """)
    with engine_siscob.connect() as conn:
        rows = conn.execute(query, params).mappings().all()
    return [serializar_dict(dict(row)) for row in rows]


def normalizar_importacion_historial(row: Dict) -> Dict:
    row = serializar_dict(row)
    row["id_importacion"] = row.get("id_importacion") or 0
    row["formato"] = row.get("formato") or "-"
    row["archivo_nombre"] = row.get("archivo_nombre") or row.get("archivo") or "-"
    row["codmes"] = row.get("codmes") or "-"
    row["fecha_corte"] = row.get("fecha_corte") or None
    row["usuario_carga"] = row.get("usuario_carga") or "-"
    row["fecha_carga"] = row.get("fecha_carga") or row.get("fecha_importacion") or row.get("fecha_registro") or None
    row["estado"] = row.get("estado") or "-"
    row["total_filas_archivo"] = row.get("total_filas_archivo") or row.get("filas_totales") or 0
    row["total_filas_validas"] = row.get("total_filas_validas") or row.get("filas_validas") or 0
    row["total_filas_error"] = row.get("total_filas_error") or row.get("filas_error") or 0
    row["total_monto_pago"] = row.get("total_monto_pago") or row.get("monto_pago") or 0
    row["total_capital_contenido"] = row.get("total_capital_contenido") or 0
    row["activo"] = row.get("activo") or 0
    row["filas_totales"] = row["total_filas_archivo"]
    row["filas_validas"] = row["total_filas_validas"]
    row["filas_error"] = row["total_filas_error"]
    row["monto_pago"] = row["total_monto_pago"]
    return row


def normalizar_formato(formato: str) -> str:
    valor = (formato or "").strip().upper()
    if valor not in FORMATS:
        raise ValueError("Formato no soportado.")
    return valor


def leer_archivo(formato: str, filename: str, content: bytes) -> pd.DataFrame:
    ext = os.path.splitext(filename or "")[1].lower()
    stream = BytesIO(content)

    if formato == "FINANCIERA_OH":
        return leer_financiera_oh(stream, ext)

    config = FORMATS[formato]
    sheet = config.get("sheet")

    if ext == ".xlsb":
        return pd.read_excel(stream, sheet_name=sheet, engine="pyxlsb")

    if ext == ".xls":
        return pd.read_excel(stream, sheet_name=sheet, engine="xlrd")

    return pd.read_excel(stream, sheet_name=sheet, engine="openpyxl")


def leer_financiera_oh(stream: BytesIO, ext: str) -> pd.DataFrame:
    raw = stream.getvalue()

    try:
        return pd.read_csv(BytesIO(raw), sep=",", encoding="utf-8-sig")
    except Exception:
        pass

    try:
        return pd.read_csv(BytesIO(raw), sep=",", encoding="latin1")
    except Exception:
        pass

    stream.seek(0)
    if ext == ".xls":
        return pd.read_excel(stream, engine="xlrd")

    stream.seek(0)
    return pd.read_excel(stream, engine="openpyxl")


def limpiar_columnas_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(col).strip() for col in df.columns]
    return df


def validar_columnas(df: pd.DataFrame, required: List[str]):
    columnas = {normalizar_columna(col): col for col in df.columns}
    faltantes = [col for col in required if normalizar_columna(col) not in columnas]

    if faltantes:
        raise ValueError(f"Columnas obligatorias faltantes: {', '.join(faltantes)}")


def aplicar_filtros_formato(df: pd.DataFrame, formato: str, config: Dict) -> pd.DataFrame:
    col = obtener_columna_real(df, config["filter_col"])
    valor = config["filter_val"]
    filtrado = df[df[col].astype(str).str.strip().str.upper() == valor.upper()].copy()

    if formato == "INTERBANK":
        periodo = obtener_columna_real(filtrado, "PERIODOCAMPAÑA")
        filtrado = filtrado[pd.to_numeric(filtrado[periodo], errors="coerce").fillna(0) != 0]

    if formato == "FINANCIERA_OH":
        monto = obtener_columna_real(filtrado, "SUMA_PAGOS_MES")
        filtrado = filtrado[pd.to_numeric(filtrado[monto], errors="coerce").fillna(0) > 0]

    return filtrado


def normalizar_registros(df: pd.DataFrame, formato: str, filename: str) -> List[Dict]:
    config = FORMATS[formato]
    registros = []

    for idx, row in df.iterrows():
        monto_soles = valor_numero(row, df, config.get("monto"))
        monto = monto_soles
        if formato == "MIBANCO":
            monto_original = valor_numero(row, df, config.get("monto_original"))
            monto = monto_original if monto_original > 0 else monto_soles
        capital = valor_numero(row, df, config.get("capital"))
        fecha_pago = obtener_fecha_pago(row, df, config)
        codmes = obtener_codmes(row, df, config, fecha_pago)
        idcartera, motivo_cartera = obtener_idcartera(row, df, formato, config)
        estado_fila = "VALIDO"
        motivos = []

        if not codmes:
            motivos.append("No se pudo obtener codmes.")

        if config.get("fecha") and not fecha_pago:
            motivos.append(f"Fecha pago invalida: {config.get('fecha')}.")

        if not idcartera:
            motivos.append(motivo_cartera or "No se pudo identificar cartera.")

        if formato == "COMPARTAMOS_VIGENTE":
            if monto_soles <= 0 and capital <= 0:
                motivos.append("Monto pago y capital contenido invalidos o cero.")
        elif monto_soles <= 0:
            motivos.append("Monto pago invalido o cero.")

        if motivos:
            estado_fila = "ERROR"

        registros.append({
            "formato": formato,
            "archivo": filename,
            "archivo_nombre": filename,
            "numero_fila": int(idx) + 2,
            "codmes": codmes,
            "fecha_corte": fecha_pago,
            "fecha_pago": fecha_pago,
            "idcartera": idcartera,
            "cartera": CARTERAS.get(idcartera),
            "tipo_medicion": config.get("tipo_medicion"),
            "tipo_producto": normalizar_tipo_producto(valor_texto(row, df, "TipCartera")),
            "clasificacion_sbs": valor_texto(row, df, "Calif_Provisiones"),
            "segmentacion": valor_texto(row, df, "TIP_CAR"),
            "usuario_asignado": valor_texto(row, df, config.get("filter_col")),
            "cod_cliente": valor_texto(row, df, "COD_CLI") or valor_texto(row, df, "codcliente"),
            "num_operacion": (
                valor_texto(row, df, "COD_PRE")
                or valor_texto(row, df, "NUMOPERACION")
                or valor_texto(row, df, "CodOperacion")
                or valor_texto(row, df, "OPERACION")
            ),
            "documento": valor_texto(row, df, "DNI") or valor_texto(row, df, "NRO_DOCUMENTO"),
            "cliente": valor_texto(row, df, "NOM_CLI") or valor_texto(row, df, "CLIENTE") or valor_texto(row, df, "NomCliente"),
            "monto_pago": monto,
            "monto_pago_soles": monto_soles,
            "capital_contenido": capital,
            "saldo_capital": capital,
            "saldo_base": capital,
            "estado_fila": estado_fila,
            "motivo_error": " | ".join(motivos) if motivos else None,
            "estado": "VALIDADO",
            "activo": 0,
            "data_json": json.dumps(serializar_dict(row.to_dict()), ensure_ascii=False),
            "fecha_registro": datetime.now(),
        })

    return registros


def obtener_idcartera(row, df, formato: str, config: Dict) -> Tuple[Optional[int], Optional[str]]:
    if config.get("idcartera"):
        return config["idcartera"], None

    if config.get("linneg"):
        linneg = valor_texto(row, df, "LinNeg").upper()
        return config["linneg"].get(linneg), f"LinNeg no mapeado: {linneg}" if linneg else "LinNeg vacio"

    if formato == "MIBANCO":
        return identificar_cartera_mibanco(row, df)

    return None, None


def identificar_cartera_mibanco(row, df) -> Tuple[Optional[int], Optional[str]]:
    cod_cli = valor_texto(row, df, "COD_CLI")
    idcartera = valor_texto(row, df, "IDCARTERA") or valor_texto(row, df, "ID_CARTERA")

    if idcartera:
        try:
            valor = int(float(idcartera))
            if valor in {112, 143, 135}:
                return valor, None
        except Exception:
            pass

    if not cod_cli:
        return None, "COD_CLI vacio."

    match = re.search(r"(112|143|135)", cod_cli)
    if match:
        return int(match.group(1)), None

    return None, f"No se identifico cartera por COD_CLI: {cod_cli}"


def obtener_fecha_pago(row, df, config: Dict):
    fecha_col = config.get("fecha")
    if not fecha_col:
        return None
    return valor_fecha(row, df, fecha_col, strict_yyyymmdd=config.get("fecha_yyyymmdd", False))


def obtener_codmes(row, df, config: Dict, fecha_pago):
    codmes_col = config.get("codmes")
    if codmes_col:
        raw = valor_texto(row, df, codmes_col)
        return normalizar_codmes(raw)

    if fecha_pago:
        return fecha_pago.strftime("%Y%m")

    return None


def construir_resumen_previo(formato: str, filename: str, registros: List[Dict]):
    filas_total = len(registros)
    filas_error = sum(1 for r in registros if r["estado_fila"] == "ERROR")
    filas_validas = filas_total - filas_error
    total_monto = sum(r["monto_pago_soles"] or 0 for r in registros if r["estado_fila"] == "VALIDO")
    total_capital = sum(r["capital_contenido"] or 0 for r in registros if r["estado_fila"] == "VALIDO")
    codmeses = sorted({r["codmes"] for r in registros if r.get("codmes") and r["estado_fila"] == "VALIDO"})
    fechas = sorted({r["fecha_corte"] for r in registros if r.get("fecha_corte") and r["estado_fila"] == "VALIDO"})
    resumen_cartera = {}

    for r in registros:
        key = r.get("idcartera") or "SIN_CARTERA"
        item = resumen_cartera.setdefault(key, {
            "idcartera": r.get("idcartera"),
            "cartera": r.get("cartera") or "Sin cartera",
            "filas": 0,
            "validas": 0,
            "errores": 0,
            "monto_pago": 0,
            "capital_contenido": 0,
        })
        item["filas"] += 1
        if r["estado_fila"] == "VALIDO":
            item["validas"] += 1
            item["monto_pago"] += r["monto_pago_soles"] or 0
            item["capital_contenido"] += r["capital_contenido"] or 0
        else:
            item["errores"] += 1

    return {
        "formato": formato,
        "archivo": filename,
        "archivo_nombre": filename,
        "codmes": codmeses[0] if len(codmeses) == 1 else None,
        "codmeses": codmeses,
        "fecha_corte": fechas[-1] if fechas else None,
        "filas_totales": filas_total,
        "filas_validas": filas_validas,
        "filas_error": filas_error,
        "total_filas_archivo": filas_total,
        "total_filas_validas": filas_validas,
        "total_filas_error": filas_error,
        "total_monto_pago": round(total_monto, 2),
        "total_capital_contenido": round(total_capital, 2),
        "resumen_por_cartera": list(resumen_cartera.values()),
        "estado": "VALIDADO",
        "activo": 0,
    }


def crear_importacion(conn, resumen: Dict) -> int:
    row = {
        "formato": resumen["formato"],
        "archivo": resumen["archivo"],
        "archivo_nombre": resumen["archivo_nombre"],
        "codmes": resumen["codmes"],
        "fecha_corte": resumen["fecha_corte"],
        "filas_totales": resumen["filas_totales"],
        "filas_validas": resumen["filas_validas"],
        "filas_error": resumen["filas_error"],
        "total_filas_archivo": resumen["filas_totales"],
        "total_filas_validas": resumen["filas_validas"],
        "total_filas_error": resumen["filas_error"],
        "total_monto_pago": resumen["total_monto_pago"],
        "total_capital_contenido": resumen["total_capital_contenido"],
        "usuario_carga": resumen.get("usuario_carga"),
        "estado": "VALIDADO",
        "activo": 0,
        "fecha_importacion": datetime.now(),
        "fecha_registro": datetime.now(),
    }
    return insertar_dinamico(conn, "PAGOS_IMPORTACION", row, devolver_identity=True)


def insertar_staging(conn, registros: List[Dict]):
    for registro in registros:
        insertar_dinamico(conn, "PAGOS_STAGING_NORMALIZADO", registro)


def obtener_staging_valido(conn, id_importacion: int) -> List[Dict]:
    query = text("""
        SELECT *
        FROM dbo.PAGOS_STAGING_NORMALIZADO WITH(NOLOCK)
        WHERE id_importacion = :id_importacion
            AND UPPER(ISNULL(estado_fila, '')) = 'VALIDO'
    """)
    return [dict(row) for row in conn.execute(query, {"id_importacion": id_importacion}).mappings().all()]


def desactivar_bi_anterior(conn, formato, codmes, idcartera):
    columns = columnas_tabla(conn, "PAGOS_BI_NORMALIZADO")
    if not {"formato", "codmes", "idcartera", "activo"}.issubset(columns):
        return

    conn.execute(text("""
        UPDATE dbo.PAGOS_BI_NORMALIZADO
        SET activo = 0
        WHERE formato = :formato
            AND codmes = :codmes
            AND (
                (:idcartera IS NULL AND idcartera IS NULL)
                OR idcartera = :idcartera
            )
    """), {"formato": formato, "codmes": codmes, "idcartera": idcartera})


def publicar_bi(conn, staging: List[Dict]) -> int:
    total = 0
    for row in staging:
        row = preparar_fila_bi(dict(row))
        row["activo"] = 1
        row["estado"] = "PUBLICADO"
        row["fecha_publicacion"] = datetime.now()
        row.pop("id_staging", None)
        row.pop("id_pago_staging", None)
        insertar_dinamico(conn, "PAGOS_BI_NORMALIZADO", row)
        total += 1
    return total


def preparar_fila_bi(row: Dict) -> Dict:
    monto = primer_valor_numerico(row, ["monto_pago", "monto_pago_soles"])
    monto_soles = primer_valor_numerico(row, ["monto_pago_soles", "monto_pago"])
    capital = primer_valor_numerico(row, ["capital_contenido", "saldo_capital", "saldo_base"])

    row["monto_pago"] = monto
    row["monto_pago_soles"] = monto_soles
    row["capital_contenido"] = capital
    row["saldo_capital"] = primer_valor_numerico(row, ["saldo_capital", "capital_contenido", "saldo_base"])
    row["saldo_base"] = primer_valor_numerico(row, ["saldo_base", "saldo_capital", "capital_contenido"])

    return row


def calcular_totales_staging(conn, id_importacion: int) -> Dict:
    rows = conn.execute(text("""
        SELECT *
        FROM dbo.PAGOS_STAGING_NORMALIZADO WITH(NOLOCK)
        WHERE id_importacion = :id_importacion
    """), {"id_importacion": id_importacion}).mappings().all()

    filas = [dict(row) for row in rows]
    total_filas = len(filas)
    total_validas = sum(1 for row in filas if str(row.get("estado_fila") or "").upper() == "VALIDO")
    total_error = sum(1 for row in filas if str(row.get("estado_fila") or "").upper() != "VALIDO")
    total_monto = sum(primer_valor_numerico(row, ["monto_pago_soles", "monto_pago"]) for row in filas)
    total_capital = sum(primer_valor_numerico(row, ["capital_contenido"]) for row in filas)

    return {
        "total_filas_archivo": total_filas,
        "total_filas_validas": total_validas,
        "total_filas_error": total_error,
        "total_monto_pago": round(total_monto, 2),
        "total_capital_contenido": round(total_capital, 2),
        "filas_totales": total_filas,
        "filas_validas": total_validas,
        "filas_error": total_error,
    }


def actualizar_importacion_publicada(conn, id_importacion: int, totales: Dict):
    columns = columnas_tabla(conn, "PAGOS_IMPORTACION")
    updates = {}

    for col, value in totales.items():
        if col in columns:
            updates[col] = value

    if "estado" in columns:
        updates["estado"] = "PUBLICADO"
    if "activo" in columns:
        updates["activo"] = 1
    if "fecha_publicacion" in columns:
        updates["fecha_publicacion"] = datetime.now()

    if not updates:
        return

    set_sql = ", ".join([f"{col} = :{col}" for col in updates])
    updates["id_importacion"] = id_importacion
    conn.execute(text(f"""
        UPDATE dbo.PAGOS_IMPORTACION
        SET {set_sql}
        WHERE id_importacion = :id_importacion
    """), updates)


def actualizar_importaciones_reemplazadas(conn, id_importacion_actual: int, grupos: set):
    columnas_importacion = columnas_tabla(conn, "PAGOS_IMPORTACION")
    columnas_bi = columnas_tabla(conn, "PAGOS_BI_NORMALIZADO")

    if not {"id_importacion", "formato", "codmes"}.issubset(columnas_importacion):
        return
    if not {"id_importacion", "activo"}.issubset(columnas_bi):
        return

    pares_periodo = {
        (formato, codmes)
        for formato, codmes, _idcartera in grupos
        if formato and codmes
    }

    for formato, codmes in pares_periodo:
        candidatos = conn.execute(text("""
            SELECT id_importacion
            FROM dbo.PAGOS_IMPORTACION WITH(NOLOCK)
            WHERE id_importacion <> :id_importacion_actual
                AND formato = :formato
                AND codmes = :codmes
                AND UPPER(ISNULL(estado, '')) = 'PUBLICADO'
        """), {
            "id_importacion_actual": id_importacion_actual,
            "formato": formato,
            "codmes": codmes,
        }).mappings().all()

        for row in candidatos:
            id_importacion = row.get("id_importacion")
            activos = conn.execute(text("""
                SELECT COUNT(*) AS total
                FROM dbo.PAGOS_BI_NORMALIZADO WITH(NOLOCK)
                WHERE id_importacion = :id_importacion
                    AND ISNULL(activo, 0) = 1
            """), {"id_importacion": id_importacion}).scalar() or 0

            if activos == 0:
                updates = {}
                if "estado" in columnas_importacion:
                    updates["estado"] = "REEMPLAZADO"
                if "activo" in columnas_importacion:
                    updates["activo"] = 0

                if updates:
                    set_sql = ", ".join([f"{col} = :{col}" for col in updates])
                    updates["id_importacion"] = id_importacion
                    conn.execute(text(f"""
                        UPDATE dbo.PAGOS_IMPORTACION
                        SET {set_sql}
                        WHERE id_importacion = :id_importacion
                    """), updates)


def insertar_dinamico(conn, table: str, row: Dict, devolver_identity: bool = False):
    columns = columnas_tabla(conn, table)
    identity = columna_identity(conn, table)
    clean = {}

    for key, value in row.items():
        key_lower = key.lower()
        if key_lower in columns and key_lower != identity:
            clean[key_lower] = normalizar_valor_sql(value)

    if not clean:
        raise ValueError(f"No hay columnas compatibles para insertar en {table}.")

    col_sql = ", ".join(clean.keys())
    val_sql = ", ".join([f":{col}" for col in clean])
    output_sql = f" OUTPUT INSERTED.{identity}" if devolver_identity and identity else ""

    result = conn.execute(text(f"""
        INSERT INTO dbo.{table} ({col_sql})
        {output_sql}
        VALUES ({val_sql})
    """), clean)

    if devolver_identity:
        if identity:
            return int(result.scalar())
        return int(conn.execute(text("SELECT SCOPE_IDENTITY()")).scalar())

    return None


def columnas_tabla(conn, table: str) -> set:
    rows = conn.execute(text("""
        SELECT LOWER(COLUMN_NAME) AS column_name
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = 'dbo' AND TABLE_NAME = :table
    """), {"table": table}).fetchall()
    return {row.column_name for row in rows}


def columna_identity(conn, table: str) -> Optional[str]:
    row = conn.execute(text("""
        SELECT LOWER(c.name) AS column_name
        FROM sys.identity_columns c
        JOIN sys.tables t ON t.object_id = c.object_id
        JOIN sys.schemas s ON s.schema_id = t.schema_id
        WHERE s.name = 'dbo' AND t.name = :table
    """), {"table": table}).fetchone()
    return row.column_name if row else None


def obtener_columna_real(df: pd.DataFrame, expected: str) -> str:
    target = normalizar_columna(expected)
    for col in df.columns:
        if normalizar_columna(col) == target:
            return col
    raise ValueError(f"Columna no encontrada: {expected}")


def normalizar_columna(col) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(col).strip().upper())


def valor_texto(row, df, col: str) -> str:
    if not col:
        return ""
    try:
        real = obtener_columna_real(df, col)
    except ValueError:
        return ""
    value = row.get(real)
    if pd.isna(value):
        return ""
    return str(value).strip()


def valor_numero(row, df, col: Optional[str]) -> float:
    if not col:
        return 0.0
    raw = valor_texto(row, df, col)
    if not raw:
        return 0.0
    raw = raw.replace(",", "")
    try:
        value = float(raw)
        if math.isnan(value):
            return 0.0
        return value
    except Exception:
        return 0.0


def primer_valor_numerico(row: Dict, keys: List[str]) -> float:
    normalizado = {str(k).lower(): v for k, v in row.items()}
    fallback = 0.0

    for key in keys:
        value = normalizado.get(key.lower())
        if value is None:
            continue
        try:
            number = float(str(value).replace(",", ""))
            if math.isnan(number):
                continue
            if number != 0:
                return number
            fallback = number
        except Exception:
            continue

    return fallback


def valor_fecha(row, df, col: str, strict_yyyymmdd: bool = False):
    try:
        raw = row.get(obtener_columna_real(df, col))
    except ValueError:
        return None
    if pd.isna(raw):
        return None
    texto = str(raw).strip()
    if not texto:
        return None

    if re.fullmatch(r"\d+(\.0)?", texto):
        numeros = texto.split(".")[0]
        if re.fullmatch(r"\d{8}", numeros):
            try:
                return datetime.strptime(numeros, "%Y%m%d").date()
            except ValueError:
                return None
        if strict_yyyymmdd:
            return None
        if re.fullmatch(r"\d{6}", numeros):
            try:
                return datetime.strptime(numeros, "%Y%m").date()
            except ValueError:
                return None
        fecha_serial = fecha_desde_serial_excel(numeros)
        if fecha_serial:
            return fecha_serial

    if strict_yyyymmdd:
        numeros = re.sub(r"\D", "", texto)
        if re.fullmatch(r"\d{8}", numeros):
            try:
                return datetime.strptime(numeros, "%Y%m%d").date()
            except ValueError:
                return None
        return None

    fecha_periodo = fecha_desde_periodo_texto(texto)
    if fecha_periodo:
        return fecha_periodo

    fecha = pd.to_datetime(raw, errors="coerce", dayfirst=True)
    if pd.isna(fecha):
        return None
    if fecha.year == 1970 and re.fullmatch(r"\d+(\.0)?", texto):
        return None
    return fecha.to_pydatetime().date()


def normalizar_codmes(raw) -> Optional[str]:
    if raw is None:
        return None
    texto = str(raw).strip()
    if not texto:
        return None
    if re.fullmatch(r"\d+(\.0)?", texto):
        numeros = texto.split(".")[0]
        if re.fullmatch(r"\d{6}", numeros):
            return numeros
        if re.fullmatch(r"\d{8}", numeros):
            try:
                return datetime.strptime(numeros, "%Y%m%d").strftime("%Y%m")
            except ValueError:
                return None
        fecha_serial = fecha_desde_serial_excel(numeros)
        if fecha_serial:
            return fecha_serial.strftime("%Y%m")
    fecha_periodo = fecha_desde_periodo_texto(texto)
    if fecha_periodo:
        return fecha_periodo.strftime("%Y%m")
    fecha = pd.to_datetime(texto, errors="coerce", dayfirst=True)
    if not pd.isna(fecha):
        if fecha.year == 1970 and re.fullmatch(r"\d+(\.0)?", texto):
            return None
        return fecha.strftime("%Y%m")
    numeros = re.sub(r"\D", "", texto)
    if len(numeros) >= 6:
        return numeros[:6]
    return None


def fecha_desde_serial_excel(value) -> Optional[date]:
    try:
        serial = int(float(str(value).strip()))
    except Exception:
        return None
    if serial < 20000 or serial > 60000:
        return None
    return (datetime(1899, 12, 30) + timedelta(days=serial)).date()


def fecha_desde_periodo_texto(value: str):
    texto = quitar_tildes(value or "").strip().upper()
    if not texto:
        return None

    meses = {
        "ENE": 1, "ENERO": 1, "JAN": 1, "JANUARY": 1,
        "FEB": 2, "FEBRERO": 2, "FEBRUARY": 2,
        "MAR": 3, "MARZO": 3, "MARCH": 3,
        "ABR": 4, "ABRIL": 4, "APR": 4, "APRIL": 4,
        "MAY": 5, "MAYO": 5,
        "JUN": 6, "JUNIO": 6, "JUNE": 6,
        "JUL": 7, "JULIO": 7, "JULY": 7,
        "AGO": 8, "AGOSTO": 8, "AUG": 8, "AUGUST": 8,
        "SEP": 9, "SET": 9, "SEPT": 9, "SEPTIEMBRE": 9, "SETIEMBRE": 9, "SEPTEMBER": 9,
        "OCT": 10, "OCTUBRE": 10, "OCTOBER": 10,
        "NOV": 11, "NOVIEMBRE": 11, "NOVEMBER": 11,
        "DIC": 12, "DICIEMBRE": 12, "DEC": 12, "DECEMBER": 12,
    }
    tokens = re.findall(r"[A-Z]+|\d{2,4}", texto)
    mes = next((meses[token] for token in tokens if token in meses), None)
    anio = next((int(token) for token in tokens if token.isdigit() and len(token) == 4), None)

    if anio is None:
        anio_corto = next((int(token) for token in tokens if token.isdigit() and len(token) == 2), None)
        if anio_corto is not None:
            anio = 2000 + anio_corto

    if mes and anio:
        try:
            return datetime(anio, mes, 1).date()
        except ValueError:
            return None

    return None


def quitar_tildes(value: str) -> str:
    reemplazos = str.maketrans("ÁÉÍÓÚÜÑ", "AEIOUUN")
    return str(value).translate(reemplazos)


def normalizar_tipo_producto(value: str) -> Optional[str]:
    valor = (value or "").strip().upper()
    if not valor:
        return None
    if "IMPUL" in valor:
        return "IMPULSO"
    if "TRAD" in valor:
        return "TRADICIONAL"
    return valor


def normalizar_valor_sql(value):
    if pd.isna(value) if not isinstance(value, (list, dict, str, bytes)) else False:
        return None
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.to_pydatetime() if hasattr(value, "to_pydatetime") else value
    return value


def serializar_dict(data: Dict) -> Dict:
    result = {}
    for key, value in data.items():
        if isinstance(value, (datetime, pd.Timestamp)):
            result[key] = value.isoformat()
        elif hasattr(value, "isoformat"):
            result[key] = value.isoformat()
        elif pd.isna(value) if not isinstance(value, (list, dict, str, bytes)) else False:
            result[key] = None
        else:
            result[key] = value
    return result
