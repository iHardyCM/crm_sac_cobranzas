from datetime import datetime
from io import BytesIO
import math
import re
import unicodedata
from typing import Dict, List, Optional, Tuple

import pandas as pd
from sqlalchemy import text

from app.core.db_siscob import engine_siscob


CANALES = {"SMS", "WAPI", "EMAIL", "IVR", "BOT"}

CARTERAS_PERMITIDAS = {
    112: "MIBANCO",
    117: "INTERBANK",
    124: "COMPARTAMOS IND",
    126: "COMPARTAMOS VIG",
    128: "COMPARTAMOS CCM",
    132: "FINANCIERAOH",
    133: "COMPARTAMOS VIGEN CSM",
    135: "MIBANCO VIGENTE",
    137: "IBK 112024 CARTERA PROPIA",
    143: "MI BANCO 2",
    144: "COMPARTAMOS CAST CSM",
    148: "FOH 062026 CARTERA PROPIA",
}

ALIASES = {
    "documento": ["dni", "documento", "doc", "nro_documento", "nro doc", "num_documento"],
    "telefono": ["numero", "telefono", "telefono_1", "celular", "fono", "nro_telefono", "nro celular"],
    "mensaje": ["mensaje", "sms", "texto", "tenor"],
    "email": ["correo", "mail", "email", "e-mail", "correo_electronico", "correo electronico"],
    "idcliente": ["idcliente", "id_cliente", "codcliente", "codigo_cliente"],
    "cliente": ["cliente", "nombre_cliente", "nom_cliente"],
    "num_operacion": ["num_operacion", "operacion", "cod_operacion", "codigo_operacion"],
    "moneda": ["moneda"],
    "monto": ["monto", "saldo", "importe"],
    "fecha_compromiso": ["fecha_compromiso", "fecha compromiso", "fec_compromiso"],
}

REQUERIDAS = {
    "SMS": ["documento", "telefono", "mensaje"],
    "WAPI": ["documento", "telefono", "mensaje"],
    "EMAIL": ["documento", "email"],
    "IVR": ["documento", "telefono"],
    "BOT": ["documento", "telefono"],
}


class CanalesColumnError(Exception):
    def __init__(self, payload: Dict):
        self.payload = payload
        super().__init__(payload.get("error", "Columnas requeridas faltantes."))


def listar_carteras_canales() -> List[Dict]:
    query = text("""
        SELECT idcartera, cartera
        FROM CobAuto.dbo.canales_cartera_ref WITH(NOLOCK)
        WHERE ISNULL(activo, 1) = 1
        ORDER BY cartera
    """)
    with engine_siscob.connect() as conn:
        rows = conn.execute(query).mappings().all()

    carteras = {
        int(row["idcartera"]): row["cartera"]
        for row in rows
        if row["idcartera"] is not None
    }

    for idcartera, cartera in CARTERAS_PERMITIDAS.items():
        carteras.setdefault(idcartera, cartera)

    return [
        {"idcartera": idcartera, "cartera": cartera}
        for idcartera, cartera in sorted(carteras.items(), key=lambda item: item[0])
    ]


def importar_canales(
    canal: str,
    idcartera: int,
    cartera: str,
    usuario_carga: str,
    archivo_nombre: str,
    contenido: bytes,
) -> Dict:
    canal = normalizar_canal(canal)
    usuario_carga = (usuario_carga or "").strip() or "SIN_USUARIO"
    cartera = (cartera or "").strip()

    with engine_siscob.begin() as conn:
        id_carga = crear_cabecera(conn, canal, idcartera, cartera, archivo_nombre, usuario_carga)

    df = leer_excel(contenido)
    columnas = mapear_columnas(df)
    faltantes = [col for col in REQUERIDAS[canal] if col not in columnas]

    if faltantes:
        with engine_siscob.begin() as conn:
            actualizar_cabecera(conn, id_carga, 0, 0, 0, "ERROR")
        raise CanalesColumnError({
            "error": f"El archivo no contiene las columnas mínimas para {canal}",
            "requeridas": REQUERIDAS[canal],
            "faltantes": faltantes,
            "columnas_detectadas": list(df.columns),
        })

    with engine_siscob.begin() as conn:
        totales = insertar_detalle(conn, id_carga, canal, idcartera, df, columnas)
        actualizar_cabecera(
            conn,
            id_carga,
            totales["total_registros"],
            totales["registros_validos"],
            totales["registros_error"],
            "PROCESADO",
        )

    return {
        "id_carga": id_carga,
        "canal": canal,
        "archivo_nombre": archivo_nombre,
        **totales,
        "mensaje": "Importación procesada correctamente",
    }


def listar_importaciones_canales(limit: int = 100) -> List[Dict]:
    query = text("""
        SELECT TOP (:limit)
            id_carga, fecha_carga, canal, idcartera, cartera, archivo_nombre,
            usuario_carga, total_registros, registros_validos, registros_error, estado
        FROM CobAuto.dbo.canales_carga WITH(NOLOCK)
        ORDER BY fecha_carga DESC, id_carga DESC
    """)
    with engine_siscob.connect() as conn:
        rows = conn.execute(query, {"limit": limit}).mappings().all()
    return [serializar(dict(row)) for row in rows]


def obtener_importacion_canales(id_carga: int) -> Dict:
    cabecera_query = text("""
        SELECT
            id_carga, fecha_carga, canal, idcartera, cartera, archivo_nombre,
            usuario_carga, total_registros, registros_validos, registros_error, estado
        FROM CobAuto.dbo.canales_carga WITH(NOLOCK)
        WHERE id_carga = :id_carga
    """)
    detalle_query = text("""
        SELECT
            id_detalle, documento, telefono, email, mensaje, canal, idcartera,
            estado_registro, observacion, fecha_registro
        FROM CobAuto.dbo.canales_carga_detalle WITH(NOLOCK)
        WHERE id_carga = :id_carga
        ORDER BY id_detalle
    """)
    with engine_siscob.connect() as conn:
        cabecera = conn.execute(cabecera_query, {"id_carga": id_carga}).mappings().first()
        if not cabecera:
            raise ValueError("Carga no encontrada.")
        detalle = conn.execute(detalle_query, {"id_carga": id_carga}).mappings().all()

    return {
        "cabecera": serializar(dict(cabecera)),
        "detalle": [serializar(dict(row)) for row in detalle],
    }


def crear_cabecera(conn, canal, idcartera, cartera, archivo_nombre, usuario_carga) -> int:
    query = text("""
        INSERT INTO CobAuto.dbo.canales_carga
            (canal, idcartera, cartera, archivo_nombre, usuario_carga, estado, fecha_carga)
        OUTPUT INSERTED.id_carga
        VALUES
            (:canal, :idcartera, :cartera, :archivo_nombre, :usuario_carga, 'RECIBIDO', GETDATE())
    """)
    return int(conn.execute(query, {
        "canal": canal,
        "idcartera": idcartera,
        "cartera": cartera,
        "archivo_nombre": archivo_nombre,
        "usuario_carga": usuario_carga,
    }).scalar())


def actualizar_cabecera(conn, id_carga, total, validos, errores, estado):
    conn.execute(text("""
        UPDATE CobAuto.dbo.canales_carga
        SET total_registros = :total,
            registros_validos = :validos,
            registros_error = :errores,
            estado = :estado,
            fecha_carga = ISNULL(fecha_carga, GETDATE())
        WHERE id_carga = :id_carga
    """), {
        "id_carga": id_carga,
        "total": total,
        "validos": validos,
        "errores": errores,
        "estado": estado,
    })


def insertar_detalle(conn, id_carga, canal, idcartera, df, columnas) -> Dict:
    total = validos = errores = 0
    filas_insert = []

    for _idx, row in df.iterrows():
        total += 1
        normalizado, observaciones = normalizar_fila(row, columnas, canal)
        estado = "ERROR" if observaciones else "VALIDO"
        if estado == "VALIDO":
            validos += 1
        else:
            errores += 1

        filas_insert.append({
            "id_carga": id_carga,
            "documento": normalizado.get("documento"),
            "cliente": normalizado.get("cliente"),
            "telefono": normalizado.get("telefono"),
            "email": normalizado.get("email"),
            "num_operacion": normalizado.get("num_operacion") or normalizado.get("idcliente"),
            "moneda": normalizado.get("moneda"),
            "monto": normalizado.get("monto"),
            "fecha_compromiso": normalizado.get("fecha_compromiso"),
            "mensaje": normalizado.get("mensaje"),
            "canal": canal,
            "idcartera": idcartera,
            "estado_registro": estado,
            "observacion": " | ".join(observaciones) if observaciones else None,
        })

    if filas_insert:
        conn.execute(text("""
            INSERT INTO CobAuto.dbo.canales_carga_detalle
                (id_carga, documento, cliente, telefono, email, num_operacion, moneda, monto,
                 fecha_compromiso, mensaje, canal, idcartera, estado_registro, observacion, fecha_registro)
            VALUES
                (:id_carga, :documento, :cliente, :telefono, :email, :num_operacion, :moneda, :monto,
                 :fecha_compromiso, :mensaje, :canal, :idcartera, :estado_registro, :observacion, GETDATE())
        """), filas_insert)

    return {
        "total_registros": total,
        "registros_validos": validos,
        "registros_error": errores,
    }


def normalizar_fila(row, columnas: Dict[str, str], canal: str) -> Tuple[Dict, List[str]]:
    data = {campo: valor_celda(row, columna) for campo, columna in columnas.items()}
    data["documento"] = limpiar_texto(data.get("documento"))
    data["telefono"] = limpiar_telefono(data.get("telefono"))
    data["mensaje"] = limpiar_texto(data.get("mensaje"))
    data["email"] = limpiar_texto(data.get("email")).lower()
    data["monto"] = normalizar_monto(data.get("monto"))
    data["fecha_compromiso"] = normalizar_fecha(data.get("fecha_compromiso"))

    observaciones = []
    for campo in REQUERIDAS[canal]:
        if not data.get(campo):
            observaciones.append(f"{campo} vacío")

    if "telefono" in REQUERIDAS[canal] and data.get("telefono") and len(data["telefono"]) < 7:
        observaciones.append("Teléfono con menos de 7 dígitos")

    if canal == "EMAIL" and data.get("email") and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", data["email"]):
        observaciones.append("Email inválido")

    return data, observaciones


def leer_excel(contenido: bytes) -> pd.DataFrame:
    return pd.read_excel(BytesIO(contenido), sheet_name=0, dtype=str)


def mapear_columnas(df: pd.DataFrame) -> Dict[str, str]:
    columnas_normalizadas = {normalizar_columna(col): col for col in df.columns}
    resultado = {}

    for campo, aliases in ALIASES.items():
        for alias in aliases:
            normalizado = normalizar_columna(alias)
            if normalizado in columnas_normalizadas:
                resultado[campo] = columnas_normalizadas[normalizado]
                break

    return resultado


def normalizar_columna(columna) -> str:
    texto = quitar_tildes(str(columna or "").strip().lower())
    texto = re.sub(r"\s+", " ", texto)
    texto = texto.replace(" ", "_").replace("-", "_")
    texto = re.sub(r"[^a-z0-9_]", "", texto)
    texto = re.sub(r"_+", "_", texto).strip("_")
    return texto


def normalizar_canal(canal: str) -> str:
    valor = (canal or "").strip().upper()
    if valor not in CANALES:
        raise ValueError("Canal no soportado.")
    return valor


def valor_celda(row, columna: Optional[str]) -> str:
    if not columna:
        return ""
    value = row.get(columna)
    if pd.isna(value):
        return ""
    return str(value).strip()


def limpiar_texto(value) -> str:
    return str(value or "").strip()


def limpiar_telefono(value) -> str:
    telefono = re.sub(r"\D", "", str(value or ""))
    if telefono.startswith("51") and len(telefono) > 9:
        telefono = telefono[2:]
    return telefono


def normalizar_monto(value):
    texto = limpiar_texto(value)
    if not texto:
        return None
    texto = texto.replace(",", "")
    try:
        monto = float(texto)
        if math.isnan(monto):
            return None
        return round(monto, 2)
    except Exception:
        return None


def normalizar_fecha(value):
    texto = limpiar_texto(value)
    if not texto:
        return None
    fecha = pd.to_datetime(texto, errors="coerce", dayfirst=True)
    if pd.isna(fecha):
        return None
    return fecha.to_pydatetime().date()


def quitar_tildes(value: str) -> str:
    return "".join(
        ch for ch in unicodedata.normalize("NFD", value)
        if unicodedata.category(ch) != "Mn"
    )


def serializar(row: Dict) -> Dict:
    result = {}
    for key, value in row.items():
        if isinstance(value, (datetime, pd.Timestamp)):
            result[key] = value.isoformat()
        elif hasattr(value, "isoformat"):
            result[key] = value.isoformat()
        else:
            result[key] = value
    return result
