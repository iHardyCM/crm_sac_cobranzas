# documento_service.py
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from copy import deepcopy
import re
import unicodedata
import zipfile
import json
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo

from app.core.database import get_connection


ROOT_DIR = Path(__file__).resolve().parents[2]
TEMPLATES_DIR = ROOT_DIR / "app" / "templates" / "documentos"
OUTPUT_DIR = ROOT_DIR / "app" / "generated_documents"
FONT_FAMILY = "Calibri"
GERENTE_NOMBRE = "LUIS PORTUGUEZ BERROCAL"
GERENTE_DNI = "10416012"
GERENTE_CARGO = "GERENTE GENERAL"
FIRMA_LUIS_PATH = TEMPLATES_DIR / "firma_luis_portuguez.png"
LOGO_MIBANCO_PATH = TEMPLATES_DIR / "logo_mibanco.png"
SIP_TEMPLATE_PATH = TEMPLATES_DIR / "convenio_pagos_sip_template.docx"
LOGO_SIP_PATH = TEMPLATES_DIR / "logo_sip.png"

DOCUMENT_TYPES = {
    "transaccion_cancelacion": {
        "id": "transaccion_cancelacion",
        "nombre": "Transaccion extrajudicial y cancelacion de deuda",
        "descripcion": "Carta de transaccion extrajudicial, cancelacion y nota de abono.",
        "cartera_id": 133,
        "cartera_nombre": "Compartamos vigente grupal",
        "plantilla_correo": "vigente_grupal_transaccion_cancelacion",
    },
    "cancelacion_grupal": {
        "id": "cancelacion_grupal",
        "nombre": "Convenio de pago y cancelacion de deuda grupal",
        "descripcion": "Convenio grupal con encargado, integrantes, montos manuales y nota de abono.",
        "cartera_id": 133,
        "cartera_nombre": "Compartamos vigente grupal",
        "plantilla_correo": "vigente_grupal_cancelacion_grupal",
    },
    "compromiso_cuota_grupal": {
        "id": "compromiso_cuota_grupal",
        "nombre": "Compromiso de pago producto grupal",
        "descripcion": "Compromiso grupal por cuota con fiador, cuotas calculadas y monto manual.",
        "cartera_id": 133,
        "cartera_nombre": "Compartamos vigente grupal",
        "plantilla_correo": "vigente_grupal_compromiso_cuota",
    },
    "compromiso_cuota_individual": {
        "id": "compromiso_cuota_individual",
        "nombre": "Convenio cuota individual grupal",
        "descripcion": "Compromiso por cuota para un integrante de credito grupal.",
        "cartera_id": 133,
        "cartera_nombre": "Compartamos vigente grupal",
        "plantilla_correo": "vigente_grupal_compromiso_cuota_individual",
    },
    "correo_pago_directo_cancelacion": {
        "id": "correo_pago_directo_cancelacion",
        "nombre": "Correo pago directo - cancelacion total",
        "descripcion": "Formato de correo de pago directo por cancelacion total para agencia y sectorista.",
        "cartera_id": 133,
        "cartera_nombre": "Compartamos vigente grupal",
        "plantilla_correo": "vigente_grupal_pago_directo_cancelacion",
        "solo_correo": True,
    },
    "correo_pago_directo_cuota": {
        "id": "correo_pago_directo_cuota",
        "nombre": "Correo pago directo - cuota",
        "descripcion": "Formato de correo de pago directo por cuota para agencia y sectorista.",
        "cartera_id": 133,
        "cartera_nombre": "Compartamos vigente grupal",
        "plantilla_correo": "vigente_grupal_pago_directo_cuota",
        "solo_correo": True,
    },
    "castigo_individual_convenio": {
        "id": "castigo_individual_convenio",
        "nombre": "Castigo - convenio / compromiso de pago",
        "descripcion": "Correo de convenio o compromiso de pago para cartera castigo individual.",
        "cartera_id": 124,
        "cartera_nombre": "Compartamos castigo individual",
        "plantilla_correo": "castigo_convenio",
        "solo_correo": True,
    },
    "castigo_individual_formatos": {
        "id": "castigo_individual_formatos",
        "nombre": "Castigo - formatos cortos",
        "descripcion": "Correos cortos de pago a cuenta y pago sobre deuda total.",
        "cartera_id": 124,
        "cartera_nombre": "Compartamos castigo individual",
        "plantilla_correo": "castigo_formatos",
        "solo_correo": True,
    },
    "castigo_grupal_convenio": {
        "id": "castigo_grupal_convenio",
        "nombre": "Castigo grupal - convenio / compromiso de pago",
        "descripcion": "Correo de convenio o compromiso de pago para cartera castigo grupal.",
        "cartera_id": 144,
        "cartera_nombre": "Compartamos castigo grupal",
        "plantilla_correo": "castigo_convenio",
        "solo_correo": True,
    },
    "castigo_grupal_formatos": {
        "id": "castigo_grupal_formatos",
        "nombre": "Castigo grupal - formatos cortos",
        "descripcion": "Correos cortos de pago a cuenta y pago sobre deuda total para castigo grupal.",
        "cartera_id": 144,
        "cartera_nombre": "Compartamos castigo grupal",
        "plantilla_correo": "castigo_formatos",
        "solo_correo": True,
    },
    "vigente_individual_cancelacion": {
        "id": "vigente_individual_cancelacion",
        "nombre": "Vigente individual - cancelacion",
        "descripcion": "Convenio de cancelacion para cartera vigente individual.",
        "cartera_id": 126,
        "cartera_nombre": "Compartamos vigente individual",
        "plantilla_correo": "vigente_individual_cancelacion",
        "document_kind": "cancelacion_individual",
    },
    "vigente_individual_cuota": {
        "id": "vigente_individual_cuota",
        "nombre": "Vigente individual - pago de cuota",
        "descripcion": "Compromiso de pago de cuota para cartera vigente individual.",
        "cartera_id": 126,
        "cartera_nombre": "Compartamos vigente individual",
        "plantilla_correo": "vigente_individual_cuota",
        "document_kind": "cuota_individual",
    },
    "ccm_cancelacion": {
        "id": "ccm_cancelacion",
        "nombre": "CCM - cancelacion",
        "descripcion": "Convenio de cancelacion para cartera CCM.",
        "cartera_id": 128,
        "cartera_nombre": "Compartamos CCM",
        "plantilla_correo": "vigente_individual_cancelacion",
        "document_kind": "cancelacion_individual",
    },
    "ccm_cuota": {
        "id": "ccm_cuota",
        "nombre": "CCM - pago de cuota",
        "descripcion": "Compromiso de pago de cuota para cartera CCM.",
        "cartera_id": 128,
        "cartera_nombre": "Compartamos CCM",
        "plantilla_correo": "vigente_individual_cuota",
        "document_kind": "cuota_individual",
    },
    "mibanco_castigo_contado": {
        "id": "mibanco_castigo_contado",
        "nombre": "Acuerdo de cancelacion de deuda - contado",
        "descripcion": "Acuerdo Mibanco de cancelacion total con descuento.",
        "cartera_id": 112,
        "cartera_nombre": "Mibanco castigo",
        "document_kind": "mibanco_contado",
        "sin_correo": True,
    },
    "mibanco_castigo_cuotas": {
        "id": "mibanco_castigo_cuotas",
        "nombre": "Acuerdo de cancelacion de deuda - cuotas",
        "descripcion": "Acuerdo Mibanco de cancelacion con cuota inicial y cronograma.",
        "cartera_id": 112,
        "cartera_nombre": "Mibanco castigo",
        "document_kind": "mibanco_cuotas",
        "sin_correo": True,
    },
    "sip_convenio_pagos_mes": {
        "id": "sip_convenio_pagos_mes",
        "nombre": "Convenio de pagos por mes - Tarjeta SIP",
        "descripcion": "Convenio SIP con cuota inicial, cuotas mensuales y cronograma de pago.",
        "cartera_id": 132,
        "cartera_nombre": "Financiera OH - SIP",
        "document_kind": "sip_convenio",
        "sin_correo": True,
    },
    "sip_constancia_pago": {
        "id": "sip_constancia_pago",
        "nombre": "Constancia de pago - Tarjeta SIP",
        "descripcion": "Constancia SIP por un abono realizado por el cliente.",
        "cartera_id": 132,
        "cartera_nombre": "Financiera OH - SIP",
        "document_kind": "sip_constancia",
        "sin_correo": True,
    },
}

DOCUMENT_QUERY_SCOPES = {
    133: {
        "nombre": "Compartamos vigente grupal",
        "entidad": "Compartamos Banco",
        "consulta": "compartamos_grupal_vigente",
        "activo": True,
    },
    124: {
        "nombre": "Compartamos castigo individual",
        "entidad": "Compartamos Banco",
        "consulta": "compartamos_castigo_individual",
        "activo": True,
    },
    144: {
        "nombre": "Compartamos castigo grupal",
        "entidad": "Compartamos Banco",
        "consulta": "compartamos_castigo_grupal",
        "activo": True,
    },
    126: {
        "nombre": "Compartamos vigente individual",
        "entidad": "Compartamos Banco",
        "consulta": "compartamos_vigente_individual",
        "activo": True,
    },
    128: {
        "nombre": "Compartamos CCM",
        "entidad": "Compartamos Banco",
        "consulta": "compartamos_ccm",
        "activo": True,
    },
    112: {
        "nombre": "Mibanco castigo",
        "entidad": "Mibanco",
        "consulta": "act_mibanco_castigo",
        "activo": True,
    },
    132: {
        "nombre": "Financiera OH - SIP",
        "entidad": "Financiera OH",
        "consulta": "actualizacionfoh_sip",
        "activo": True,
    },
}

EMAIL_TEMPLATE_SCOPES = {
    "vigente_grupal_transaccion_cancelacion": {
        "asunto": "Transaccion extrajudicial y cancelacion de deuda - {cliente}",
        "requiere_adjunto": True,
    },
    "vigente_grupal_cancelacion_grupal": {
        "asunto": "Convenio de pago y cancelacion de deuda grupal - {grupo}",
        "requiere_adjunto": True,
    },
    "vigente_grupal_compromiso_cuota": {
        "asunto": "Compromiso de pago producto grupal - {grupo}",
        "requiere_adjunto": True,
    },
    "vigente_grupal_compromiso_cuota_individual": {
        "asunto": "MITIGACION_CUOTA_VIGENTE GRUPAL_{cliente}_{operacion}",
        "requiere_adjunto": True,
    },
    "vigente_grupal_pago_directo_cancelacion": {
        "asunto": "APLICACION PAGOS PARCIALES_CANCELACION_{cliente}_{agencia}",
        "requiere_adjunto": False,
    },
    "vigente_grupal_pago_directo_cuota": {
        "asunto": "APLICACION PAGOS PARCIALES_CUOTA_{cliente}_{agencia}",
        "requiere_adjunto": False,
    },
    "castigo_convenio": {
        "asunto": "CAMPANA_CASTIGO_{tipo_acuerdo}_{cliente}_{agencia}_OPERACION_{operacion}",
        "requiere_adjunto": False,
    },
    "castigo_formatos": {
        "asunto": "Formatos castigo - {cliente}",
        "requiere_adjunto": False,
    },
    "vigente_individual_cancelacion": {
        "asunto": "MITIGACION_VIG_CANCELACION_{cliente}_{agencia}_OPERACION_{operacion}",
        "requiere_adjunto": True,
    },
    "vigente_individual_cuota": {
        "asunto": "IND_VIGENTE_CAMPANA_CUOTAS_{cliente}_{agencia}_OPERACION_{operacion}",
        "requiere_adjunto": True,
    },
}

DIRECTORIO_AGENCIAS_TABLE = "CobAuto.dbo.CRM_DIRECTORIO_AGENCIAS"
AUDITORIA_DOCUMENTOS_TABLE = "CobAuto.dbo.CRM_DOCUMENTOS_AUDITORIA"

MESES = {
    1: "enero",
    2: "febrero",
    3: "marzo",
    4: "abril",
    5: "mayo",
    6: "junio",
    7: "julio",
    8: "agosto",
    9: "septiembre",
    10: "octubre",
    11: "noviembre",
    12: "diciembre",
}


def listar_tipos_documento():
    return list(DOCUMENT_TYPES.values())


def asegurar_tabla_auditoria_documentos(conn):
    cursor = conn.cursor()
    try:
        cursor.execute(
            f"""
            IF OBJECT_ID('{AUDITORIA_DOCUMENTOS_TABLE}', 'U') IS NULL
            BEGIN
                CREATE TABLE {AUDITORIA_DOCUMENTOS_TABLE} (
                    id_auditoria BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
                    fecha_generacion DATETIME2 NOT NULL CONSTRAINT DF_CRM_DOCUMENTOS_AUDITORIA_FECHA DEFAULT SYSDATETIME(),
                    usuario VARCHAR(50) NOT NULL,
                    nombre_usuario VARCHAR(180) NULL,
                    perfil_usuario VARCHAR(80) NULL,
                    entidad VARCHAR(100) NOT NULL,
                    id_cartera INT NOT NULL,
                    cartera VARCHAR(160) NOT NULL,
                    tipo_documento VARCHAR(100) NOT NULL,
                    formato VARCHAR(10) NOT NULL,
                    archivo_nombre VARCHAR(260) NOT NULL,
                    dni_cliente VARCHAR(50) NULL,
                    cliente VARCHAR(260) NULL,
                    operacion VARCHAR(80) NULL,
                    monto_campania DECIMAL(18,2) NULL,
                    monto_cancelacion DECIMAL(18,2) NULL,
                    detalle_json NVARCHAR(MAX) NULL
                );
                CREATE INDEX IX_CRM_DOCUMENTOS_AUDITORIA_FECHA
                    ON {AUDITORIA_DOCUMENTOS_TABLE}(fecha_generacion DESC);
                CREATE INDEX IX_CRM_DOCUMENTOS_AUDITORIA_USUARIO
                    ON {AUDITORIA_DOCUMENTOS_TABLE}(usuario, fecha_generacion DESC);
            END
            IF COL_LENGTH('{AUDITORIA_DOCUMENTOS_TABLE}', 'monto_campania') IS NULL
                ALTER TABLE {AUDITORIA_DOCUMENTOS_TABLE} ADD monto_campania DECIMAL(18,2) NULL;
            """
        )
        conn.commit()
    finally:
        cursor.close()


def registrar_auditoria_documento(result, documento_tipo, usuario=None, nombre_usuario=None, perfil_usuario=None, cancelacion=None, operaciones=None, excepcion=False, detalle_operaciones=None):
    config = obtener_config_documento(documento_tipo)
    cartera_id = int(config.get("cartera_id") or 0)
    cartera = DOCUMENT_QUERY_SCOPES.get(cartera_id, {})
    registro = result.get("registro") or {}
    if isinstance(detalle_operaciones, dict):
        detalle = dict(detalle_operaciones)
        operaciones_detalle = detalle.get("operaciones") or []
    else:
        operaciones_detalle = detalle_operaciones or [{"operacion": clave_operacion(item)} for item in (operaciones or [])]
        detalle = {"operaciones": operaciones_detalle}
    campania_total = sum((decimal_value(item.get("campania"), Decimal("0")) or Decimal("0")) for item in operaciones_detalle)
    if not campania_total:
        campania_total = decimal_value(registro.get("MtoCancelacionCliente"), Decimal("0")) or Decimal("0")
    detalle["excepcion"] = bool(excepcion)
    conn = None
    cursor = None
    try:
        conn = get_connection()
        asegurar_tabla_auditoria_documentos(conn)
        cursor = conn.cursor()
        cursor.execute(
            f"""
            INSERT INTO {AUDITORIA_DOCUMENTOS_TABLE} (
                usuario, nombre_usuario, perfil_usuario, entidad, id_cartera, cartera,
                tipo_documento, formato, archivo_nombre, dni_cliente, cliente, operacion,
                monto_campania, monto_cancelacion, detalle_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (str(usuario or "SIN_USUARIO").strip()[:50], str(nombre_usuario or "").strip()[:180] or None,
             str(perfil_usuario or "").strip()[:80] or None, cartera.get("entidad", "Sin entidad"), cartera_id,
             config.get("cartera_nombre", cartera.get("nombre", "Sin cartera")), documento_tipo,
             result.get("formato", "docx"), result.get("filename", ""),
             str(registro.get("NumDocumento") or "")[:50] or None, str(registro.get("NomCliente") or registro.get("NomGrupo") or "")[:260] or None,
             clave_operacion(registro.get("Operacion"))[:80] or None, campania_total, decimal_value(cancelacion), json.dumps(detalle, ensure_ascii=False)),
        )
        conn.commit()
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()


def listar_carteras_documento():
    return [
        {
            "id": cartera_id,
            "nombre": config["nombre"],
            "entidad": config.get("entidad", "Compartamos Banco"),
            "activo": bool(config.get("activo")),
            "consulta": config.get("consulta"),
        }
        for cartera_id, config in DOCUMENT_QUERY_SCOPES.items()
    ]


def obtener_config_documento(documento_tipo):
    config = DOCUMENT_TYPES.get(documento_tipo)
    if not config:
        raise ValueError("Tipo de documento no soportado.")

    cartera_id = config.get("cartera_id")
    if cartera_id not in DOCUMENT_QUERY_SCOPES:
        raise ValueError(f"No hay consulta configurada para la cartera {cartera_id}.")

    return config


def obtener_config_correo(documento_tipo):
    config = obtener_config_documento(documento_tipo)
    plantilla_id = config.get("plantilla_correo")
    return EMAIL_TEMPLATE_SCOPES.get(plantilla_id, {})


def decimal_value(value, default=None):
    if value is None or value == "":
        return default

    try:
        return Decimal(str(value).replace(",", ""))
    except (InvalidOperation, ValueError):
        return default


def serialize_value(value):
    if isinstance(value, Decimal):
        return float(value)

    if isinstance(value, (datetime, date)):
        return value.isoformat()

    return value


def fetch_resultset(cursor):
    columns = [col[0] for col in cursor.description]
    rows = cursor.fetchall()
    return [
        {columns[i]: serialize_value(value) for i, value in enumerate(row)}
        for row in rows
    ]


def asegurar_tabla_directorio_agencias(conn):
    cursor = conn.cursor()
    cursor.execute(
        f"""
        IF OBJECT_ID('{DIRECTORIO_AGENCIAS_TABLE}', 'U') IS NULL
        BEGIN
            CREATE TABLE {DIRECTORIO_AGENCIAS_TABLE} (
                id INT IDENTITY(1,1) PRIMARY KEY,
                cod NVARCHAR(50) NULL,
                agencia NVARCHAR(255) NULL,
                clas_fisica NVARCHAR(120) NULL,
                clas_prod NVARCHAR(120) NULL,
                gerente_agencia NVARCHAR(255) NULL,
                anexo NVARCHAR(50) NULL,
                celular_ga NVARCHAR(80) NULL,
                correo_ga NVARCHAR(255) NULL,
                correo_agencia NVARCHAR(255) NULL,
                estado NVARCHAR(80) NULL,
                region NVARCHAR(120) NULL,
                apertura_lv NVARCHAR(80) NULL,
                cierre_lv NVARCHAR(80) NULL,
                apertura_sab NVARCHAR(80) NULL,
                cierre_sab NVARCHAR(80) NULL,
                departamento NVARCHAR(120) NULL,
                provincia NVARCHAR(120) NULL,
                distrito NVARCHAR(160) NULL,
                direccion NVARCHAR(500) NULL,
                tipo_sucursal NVARCHAR(120) NULL,
                archivo_origen NVARCHAR(255) NULL,
                fecha_importacion DATETIME NOT NULL DEFAULT GETDATE()
            )
        END
        """
    )
    conn.commit()
    cursor.close()


def normalizar_columna_excel(value):
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"[^A-Z0-9]+", "_", text.upper()).strip("_")


def valor_excel_texto(value):
    if value is None:
        return ""
    try:
        import pandas as pd
        if pd.isna(value):
            return ""
    except Exception:
        pass
    if isinstance(value, (datetime, date)):
        return value.strftime("%H:%M:%S") if isinstance(value, datetime) and value.date() == date(1899, 12, 30) else value.strftime("%d/%m/%Y")
    return str(value).strip()


def importar_directorio_agencias(path, archivo_nombre=""):
    try:
        import pandas as pd
    except ImportError as exc:
        raise ValueError("No se pudo importar Excel: falta pandas/openpyxl en el servidor.") from exc

    df = pd.read_excel(path, sheet_name=0)
    if df.empty:
        raise ValueError("El archivo de directorio no tiene filas para importar.")

    df.columns = [normalizar_columna_excel(col) for col in df.columns]
    columnas = {
        "cod": ["COD", "CODIGO"],
        "agencia": ["AGENCIA", "OFICINA"],
        "clas_fisica": ["CLAS_FISICA"],
        "clas_prod": ["CLAS_PROD"],
        "gerente_agencia": ["GERENTE_AGENCIA", "GERENTE"],
        "anexo": ["ANEXO"],
        "celular_ga": ["CELULAR_GA", "CELULAR"],
        "correo_ga": ["CORREO_GA"],
        "correo_agencia": ["CORREO_AGENCIA"],
        "estado": ["ESTADO"],
        "region": ["REGION"],
        "apertura_lv": ["APERTURA_L_V"],
        "cierre_lv": ["CIERRE_L_V"],
        "apertura_sab": ["APERTURA_SAB"],
        "cierre_sab": ["CIERRE_SAB"],
        "departamento": ["DEPARTAMENTO"],
        "provincia": ["PROVINCIA"],
        "distrito": ["DISTRITO"],
        "direccion": ["DIRECCION"],
        "tipo_sucursal": ["TIPO_SUCURSAL"],
    }

    def get_value(row, names):
        for name in names:
            if name in row:
                return valor_excel_texto(row.get(name))
        return ""

    records = []
    for _, row in df.iterrows():
        item = {field: get_value(row, names) for field, names in columnas.items()}
        if not any(item.values()):
            continue
        records.append(item)

    if not records:
        raise ValueError("No se encontraron columnas validas para importar el directorio.")

    conn = get_connection()
    cursor = None
    try:
        asegurar_tabla_directorio_agencias(conn)
        cursor = conn.cursor()
        cursor.execute(f"DELETE FROM {DIRECTORIO_AGENCIAS_TABLE}")
        insert_sql = f"""
            INSERT INTO {DIRECTORIO_AGENCIAS_TABLE} (
                cod, agencia, clas_fisica, clas_prod, gerente_agencia, anexo, celular_ga,
                correo_ga, correo_agencia, estado, region, apertura_lv, cierre_lv,
                apertura_sab, cierre_sab, departamento, provincia, distrito, direccion,
                tipo_sucursal, archivo_origen, fecha_importacion
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, GETDATE())
        """
        values = [
            (
                item["cod"], item["agencia"], item["clas_fisica"], item["clas_prod"],
                item["gerente_agencia"], item["anexo"], item["celular_ga"], item["correo_ga"],
                item["correo_agencia"], item["estado"], item["region"], item["apertura_lv"],
                item["cierre_lv"], item["apertura_sab"], item["cierre_sab"], item["departamento"],
                item["provincia"], item["distrito"], item["direccion"], item["tipo_sucursal"],
                archivo_nombre,
            )
            for item in records
        ]
        cursor.fast_executemany = True
        cursor.executemany(insert_sql, values)
        conn.commit()
        return {"total": len(records), "archivo": archivo_nombre}
    finally:
        if cursor is not None:
            cursor.close()
        conn.close()


def listar_directorio_agencias(q=None, limit=300):
    conn = get_connection()
    cursor = None
    try:
        asegurar_tabla_directorio_agencias(conn)
        cursor = conn.cursor()
        params = []
        where = ""
        if limpiar_texto(q):
            where = """
                WHERE agencia LIKE ? OR gerente_agencia LIKE ? OR correo_ga LIKE ?
                   OR correo_agencia LIKE ? OR distrito LIKE ? OR provincia LIKE ? OR region LIKE ?
            """
            term = f"%{limpiar_texto(q)}%"
            params = [term] * 7
        cursor.execute(
            f"""
            SELECT TOP {int(limit)}
                cod, agencia, clas_fisica, clas_prod, gerente_agencia, anexo, celular_ga,
                correo_ga, correo_agencia, estado, region, apertura_lv, cierre_lv,
                apertura_sab, cierre_sab, departamento, provincia, distrito, direccion,
                tipo_sucursal, archivo_origen, fecha_importacion
            FROM {DIRECTORIO_AGENCIAS_TABLE}
            {where}
            ORDER BY agencia
            """,
            *params,
        )
        return fetch_resultset(cursor)
    finally:
        if cursor is not None:
            cursor.close()
        conn.close()


def limpiar_texto(value):
    return str(value or "").strip()


def clave_operacion(value):
    """Normaliza operaciones SQL sin eliminar ceros significativos del identificador."""
    text = limpiar_texto(value)
    if not text:
        return ""
    try:
        number = Decimal(text)
    except (InvalidOperation, ValueError):
        return text.upper()
    # SQL/pandas puede entregar el código como 121035810.0. Se elimina solo
    # la fracción técnica; nunca los ceros finales de la parte entera.
    if number == number.to_integral_value():
        return format(number.quantize(Decimal("1")), "f")
    return format(number.normalize(), "f").rstrip("0").rstrip(".") or "0"


def format_money(value):
    amount = decimal_value(value, Decimal("0"))
    return f"{amount:,.2f}"


def calcular_cuota_grupal(row):
    return sum(
        decimal_value(row.get(field), Decimal("0"))
        for field in ("CT1", "CT11", "CT12", "CT13", "CT14", "CT15")
    )


def calcular_cuota_grupal_numero(row, numero):
    suffixes = [str(numero), *[f"{numero}{index}" for index in range(1, 6)]]
    return sum(
        decimal_value(row.get(f"CT{suffix}"), Decimal("0"))
        for suffix in suffixes
    )


def calcular_cuotas_grupal_acumuladas(row, cantidad):
    cantidad = max(1, min(5, int(cantidad or 1)))
    return sum(calcular_cuota_grupal_numero(row, numero) for numero in range(1, cantidad + 1))


def obtener_nro_cuota_atrasada(row):
    return limpiar_texto(row.get("UltCuotaAtrasada")) or "1"


def obtener_nros_cuotas_individual(row, cantidad):
    inicio_texto = limpiar_texto(row.get("UltCuotaAtrasada"))
    if not inicio_texto:
        return ""
    try:
        inicio = int(float(str(inicio_texto).replace(",", ".")))
    except (TypeError, ValueError):
        return inicio_texto
    numeros = [str(inicio + index) for index in range(max(1, int(cantidad or 1)))]
    return " y ".join(numeros) if len(numeros) == 2 else ", ".join(numeros)


def format_fecha_pago(value):
    if not value:
        return ""

    try:
        parsed = datetime.strptime(str(value), "%Y-%m-%d").date()
        return parsed.strftime("%d/%m/%Y")
    except ValueError:
        return str(value)


def fecha_larga_hoy():
    today = datetime.now(ZoneInfo("America/Lima")).date()
    return f"{today.day} de {MESES[today.month]} del {today.year}"


def fecha_larga_modelo_hoy():
    today = datetime.now(ZoneInfo("America/Lima")).date()
    return f"{today.day} de {MESES[today.month].capitalize()} de {today.year}"


def filtros_documento(dni=None, operacion=None, codigo_grupo=None, cod_cre_grupal=None):
    filtros = []
    params = []

    if limpiar_texto(operacion):
        return "CAST(CG.Operacion AS VARCHAR(50)) = ?", [limpiar_texto(operacion)]

    if limpiar_texto(dni):
        filtros.append("RTRIM(LTRIM(CG.NumDocumento)) = ?")
        params.append(limpiar_texto(dni))

    if limpiar_texto(codigo_grupo):
        filtros.append("CAST(CG.CodigoGrupo AS VARCHAR(50)) = ?")
        params.append(limpiar_texto(codigo_grupo))

    if limpiar_texto(cod_cre_grupal):
        filtros.append("CAST(CG.CodCreGrupal AS VARCHAR(50)) = ?")
        params.append(limpiar_texto(cod_cre_grupal))

    if not filtros:
        raise ValueError("Ingresa al menos DNI, operacion, cuenta grupal o codigo grupal.")

    return " AND ".join(filtros), params


def columna_tabla(columns, candidates):
    for candidate in candidates:
        actual = columns.get(candidate.lower())
        if actual:
            return actual
    return None


def normalizar_nombre_columna(value):
    return "".join(ch for ch in str(value or "").lower() if ch.isalnum())


def columna_tabla_flexible(columns, candidates):
    actual = columna_tabla(columns, candidates)
    if actual:
        return actual

    normalizadas = {normalizar_nombre_columna(key): value for key, value in columns.items()}
    for candidate in candidates:
        actual = normalizadas.get(normalizar_nombre_columna(candidate))
        if actual:
            return actual
    return None


def column_expr(alias, columns, candidates, sql_type="NVARCHAR(255)"):
    actual = columna_tabla_flexible(columns, candidates)
    if actual:
        return f"CG.[{actual}] AS {alias}"
    return f"CAST(NULL AS {sql_type}) AS {alias}"


def cast_column_expr(alias, columns, candidates, sql_type="NVARCHAR(50)"):
    actual = columna_tabla_flexible(columns, candidates)
    if actual:
        return f"CAST(CG.[{actual}] AS {sql_type}) AS {alias}"
    return f"CAST(NULL AS {sql_type}) AS {alias}"


def numeric_source_expr(table_alias, alias, columns, candidates, fallback="0"):
    actual = columna_tabla_flexible(columns, candidates)
    if actual:
        return f"COALESCE(TRY_CAST({table_alias}.[{actual}] AS DECIMAL(18,2)), {fallback}) AS {alias}"
    return f"CAST({fallback} AS DECIMAL(18,2)) AS {alias}"


def obtener_columnas_tabla(cursor, table_name):
    cursor.execute(
        """
        SELECT COLUMN_NAME
        FROM Desarrollo.INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = 'dbo' AND TABLE_NAME = ?
        """,
        table_name,
    )
    return {str(row[0]).lower(): str(row[0]) for row in cursor.fetchall()}


def sac_column_expr(columns, column_name):
    actual = columna_tabla_flexible(columns, [column_name, f"{column_name} "])
    if not actual:
        return None
    return f"COALESCE(S.[{actual}], 0)"


def sac_value_expr(alias, columns, candidates, fallback_expr):
    actual = columna_tabla_flexible(columns, candidates)
    if actual:
        return f"COALESCE(CAST(S.[{actual}] AS NVARCHAR(50)), {fallback_expr}) AS {alias}"
    return f"{fallback_expr} AS {alias}"


def sac_cuota_part_expr(columns, numero):
    suffixes = [str(numero), *[f"{numero}{index}" for index in range(1, 6)]]
    parts = [sac_column_expr(columns, f"CT {suffix}") for suffix in suffixes]
    parts = [part for part in parts if part]
    if not parts:
        return "CAST(0 AS DECIMAL(18,2))", False
    return " + ".join(parts), True


def sac_cuota_acumulada_expr(columns, hasta, fallback_expr):
    parts = []
    all_present = True
    for numero in range(1, hasta + 1):
        expr, present = sac_cuota_part_expr(columns, numero)
        parts.append(f"({expr})")
        all_present = all_present and present

    if not all_present:
        return f"({fallback_expr} * {hasta})"

    total_expr = " + ".join(parts)
    return f"COALESCE(NULLIF(({total_expr}), 0), ({fallback_expr} * {hasta}))"


def filtros_documento_castigo(dni=None, operacion=None):
    if limpiar_texto(operacion):
        return "CAST(C.Operacion AS VARCHAR(50)) = ?", [limpiar_texto(operacion)]

    if limpiar_texto(dni):
        return "RTRIM(LTRIM(CAST(C.NumDoc AS VARCHAR(50)))) = ?", [limpiar_texto(dni)]

    raise ValueError("Ingresa DNI u operacion para buscar en cartera castigo.")


def consultar_datos_documento(dni=None, operacion=None, codigo_grupo=None, cod_cre_grupal=None, codigo_cliente=None, nombre_cliente=None, limit=20, cartera_id=133):
    cartera_id = int(cartera_id or 133)
    if cartera_id == 112:
        return consultar_datos_documento_mibanco(dni=dni, operacion=operacion, codigo_cliente=codigo_cliente, nombre_cliente=nombre_cliente, limit=limit)
    if cartera_id == 132:
        return consultar_datos_documento_sip(dni=dni, operacion=operacion, nombre_cliente=nombre_cliente, limit=limit)
    if cartera_id in (124, 144):
        return consultar_datos_documento_castigo(
            cartera_id=cartera_id,
            dni=dni,
            operacion=operacion,
            limit=limit,
        )
    if cartera_id in (126, 128):
        return consultar_datos_documento_vigente_individual(
            cartera_id=cartera_id,
            dni=dni,
            operacion=operacion,
            limit=limit,
        )

    where, params = filtros_documento(
        dni=dni,
        operacion=operacion,
        codigo_grupo=codigo_grupo,
        cod_cre_grupal=cod_cre_grupal,
    )

    conn = None
    cursor = None

    try:
        conn = get_connection()
        cursor = conn.cursor()
        cg_columns = obtener_columnas_tabla(cursor, "compartamos_grupal")
        sac_columns = obtener_columnas_tabla(cursor, "SAC_CAR_BIZNESCOB")
        campania_cuota_expr = numeric_source_expr(
            "CG",
            "MtoCuotaCampania",
            cg_columns,
            [
                "Mto_SDO_paraContener_Desc%",
                "Mto_SDO_paraContener_Desc",
                "Mto SDO paraContener Desc%",
                "Mto SDO paraContener Desc",
            ],
        )
        ct_selects = []
        for cuota_numero in range(1, 6):
            suffixes = [str(cuota_numero), *[f"{cuota_numero}{index}" for index in range(1, 6)]]
            for suffix in suffixes:
                ct_selects.append(
                    "                "
                    + numeric_source_expr(
                        "SB",
                        f"CT{suffix}",
                        sac_columns,
                        [f"CT {suffix}", f"CT{suffix}", f"CT {suffix} "],
                    )
                    + ","
                )
        ct_select_sql = "\n".join(ct_selects)
        cursor.execute(
            f"""
            SELECT TOP {int(limit)}
                CG.NumDocumento,
                CG.Operacion,
                CG.NomCliente,
                CG.Direccion_Principal AS DireccionPrincipal,
                CG.Distrito_Principal,
                CG.[Mto CancelacionCliente] AS MtoCancelacionCliente,
                CG.NroCuotas_Aprobadas,
                CG.NroCuotasPagadas,
                CG.NroCuotas,
                CG.DiasAtraso,
                CG.CodCuenta,
                CG.CtaCliente,
                CG.CodigoGrupo,
                CG.CodCreGrupal,
                CG.NomGrupo,
                CG.NomOficina,
                {campania_cuota_expr},
                SB.[SdoCapital ] AS SdoCapital,
                SB.[Deuda_Total ] AS DeudaTotal,
{ct_select_sql}
                SB.[Ult_CuotaAtrasada ] AS UltCuotaAtrasada
            FROM Desarrollo.DBO.compartamos_grupal CG WITH(NOLOCK)
            LEFT JOIN Desarrollo.DBO.SAC_CAR_BIZNESCOB SB WITH(NOLOCK)
                ON RIGHT('00000000000000000000' + CAST(CG.Operacion AS NVARCHAR(20)), 20) = SB.[Cod Operación]
            WHERE {where}
            ORDER BY CG.NomCliente, CG.Operacion
            """,
            *params,
        )
        return fetch_resultset(cursor)
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()


def consultar_datos_documento_vigente_individual(cartera_id=126, dni=None, operacion=None, limit=20):
    cartera_id = int(cartera_id or 126)
    if limpiar_texto(operacion):
        where = "CAST(C.Operacion AS VARCHAR(50)) = ?"
        params = [limpiar_texto(operacion)]
    elif limpiar_texto(dni):
        dni_col = "C.NumDoc" if cartera_id == 126 else "C.DNI"
        where = f"RTRIM(LTRIM(CAST({dni_col} AS VARCHAR(50)))) = ?"
        params = [limpiar_texto(dni)]
    else:
        raise ValueError("Ingresa DNI u operacion para buscar en cartera vigente individual.")

    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        sac_columns = obtener_columnas_tabla(cursor, "SAC_CAR_BIZNESCOB")

        if cartera_id == 126:
            table = "Desarrollo.dbo.compartamos_individual"
            cuota_fallback = "C.Cuota_Atrasada"
            ult_cuota_expr = sac_value_expr(
                "UltCuotaAtrasada",
                sac_columns,
                [
                    "ULT_CUOTA_ATRASADA",
                    "ULT_CUOTA_ATRASADA ",
                    "Ult_CuotaAtrasada",
                    "Ult_CuotaAtrasada ",
                    "ULT_CUOTAATRASADA",
                    "UltCuotaAtrasada",
                    "UltimaCuotaAtrasada",
                    "Ult_Cuota_Atrasada",
                ],
                "CAST(NULL AS NVARCHAR(50))",
            )
            select_sql = f"""
                    C.NumDoc AS NumDocumento,
                    C.Operacion,
                    C.Nomcliente AS NomCliente,
                    C.DireccionPrincipal,
                    C.DistritoPrincipal,
                    C.ProvinciaPrincipal,
                    C.Cancelacion AS MtoCancelacionCliente,
                    C.ctacliente AS CtaCliente,
                    C.codcuenta AS CodCuenta,
                    CAST(NULL AS NVARCHAR(50)) AS CodigoGrupo,
                    CAST(NULL AS NVARCHAR(50)) AS CodCreGrupal,
                    CAST(NULL AS NVARCHAR(255)) AS NomGrupo,
                    C.Oficina AS NomOficina,
                    C.[Saldo Capital por Cuenta] AS SdoCapital,
                    C.[Saldo Total x Cliente] AS DeudaTotal,
                    {sac_cuota_acumulada_expr(sac_columns, 1, cuota_fallback)} AS CT1,
                    {sac_cuota_acumulada_expr(sac_columns, 2, cuota_fallback)} AS CT2,
                    {sac_cuota_acumulada_expr(sac_columns, 3, cuota_fallback)} AS CT3,
                    {sac_cuota_acumulada_expr(sac_columns, 4, cuota_fallback)} AS CT4,
                    C.[Campaña Final 1 Cuota] AS MtoCuotaCampania,
                    C.[Campaña Final 1 Cuota] AS MtoCuotaCampania1,
                    C.[Campaña Final 2 Cuota] AS MtoCuotaCampania2,
                    C.[Campaña Final 3 Cuota] AS MtoCuotaCampania3,
                    C.[Campaña Final 4 Cuota] AS MtoCuotaCampania4,
                    CAST(NULL AS DECIMAL(18,2)) AS CT11,
                    CAST(NULL AS DECIMAL(18,2)) AS CT12,
                    CAST(NULL AS DECIMAL(18,2)) AS CT13,
                    CAST(NULL AS DECIMAL(18,2)) AS CT14,
                    CAST(NULL AS DECIMAL(18,2)) AS CT15,
                    CAST(NULL AS DECIMAL(18,2)) AS CT21,
                    CAST(NULL AS DECIMAL(18,2)) AS CT22,
                    CAST(NULL AS DECIMAL(18,2)) AS CT23,
                    CAST(NULL AS DECIMAL(18,2)) AS CT24,
                    CAST(NULL AS DECIMAL(18,2)) AS CT25,
                    {ult_cuota_expr},
                    C.Producto,
                    C.[Saldo Capital por Cuenta] AS CapitalActual,
                    C.[Saldo Total x Cliente] AS DeudaTotalActual
            """
        else:
            table = "Desarrollo.dbo.compartamos_ccm"
            cuota_fallback = "C.CuotaAtrasada"
            ult_cuota_expr = sac_value_expr(
                "UltCuotaAtrasada",
                sac_columns,
                [
                    "ULT_CUOTA_ATRASADA",
                    "ULT_CUOTA_ATRASADA ",
                    "Ult_CuotaAtrasada",
                    "Ult_CuotaAtrasada ",
                    "ULT_CUOTAATRASADA",
                    "UltCuotaAtrasada",
                    "UltimaCuotaAtrasada",
                    "Ult_Cuota_Atrasada",
                ],
                "CAST(NULL AS NVARCHAR(50))",
            )
            select_sql = f"""
                    C.DNI AS NumDocumento,
                    C.Operacion,
                    C.[Nombre Cliente] AS NomCliente,
                    C.DireccionPrincipal,
                    C.DistritoPrincipal,
                    C.ProvinciaPrincipal,
                    C.Cancelacion AS MtoCancelacionCliente,
                    C.ctacliente AS CtaCliente,
                    C.codcuenta AS CodCuenta,
                    CAST(NULL AS NVARCHAR(50)) AS CodigoGrupo,
                    CAST(NULL AS NVARCHAR(50)) AS CodCreGrupal,
                    CAST(NULL AS NVARCHAR(255)) AS NomGrupo,
                    C.Oficina AS NomOficina,
                    C.[Saldo Capital por Cuenta] AS SdoCapital,
                    C.[Saldo Total x Cliente] AS DeudaTotal,
                    {sac_cuota_acumulada_expr(sac_columns, 1, cuota_fallback)} AS CT1,
                    {sac_cuota_acumulada_expr(sac_columns, 2, cuota_fallback)} AS CT2,
                    {sac_cuota_acumulada_expr(sac_columns, 3, cuota_fallback)} AS CT3,
                    {sac_cuota_acumulada_expr(sac_columns, 4, cuota_fallback)} AS CT4,
                    C.[Campaña Final 1 Cuota] AS MtoCuotaCampania,
                    C.[Campaña Final 1 Cuota] AS MtoCuotaCampania1,
                    C.[Campaña Final 2 Cuota] AS MtoCuotaCampania2,
                    C.[Campaña Final 3 Cuota] AS MtoCuotaCampania3,
                    C.[Campaña Final 4 Cuota] AS MtoCuotaCampania4,
                    CAST(NULL AS DECIMAL(18,2)) AS CT11,
                    CAST(NULL AS DECIMAL(18,2)) AS CT12,
                    CAST(NULL AS DECIMAL(18,2)) AS CT13,
                    CAST(NULL AS DECIMAL(18,2)) AS CT14,
                    CAST(NULL AS DECIMAL(18,2)) AS CT15,
                    CAST(NULL AS DECIMAL(18,2)) AS CT21,
                    CAST(NULL AS DECIMAL(18,2)) AS CT22,
                    CAST(NULL AS DECIMAL(18,2)) AS CT23,
                    CAST(NULL AS DECIMAL(18,2)) AS CT24,
                    CAST(NULL AS DECIMAL(18,2)) AS CT25,
                    {ult_cuota_expr},
                    C.LineaNegocio AS Producto,
                    C.[Saldo Capital por Cuenta] AS CapitalActual,
                    C.[Saldo Total x Cliente] AS DeudaTotalActual
            """

        cursor.execute(
            f"""
            SELECT TOP {int(limit)}
                {select_sql},
                {cartera_id} AS CarteraId
            FROM {table} C WITH(NOLOCK)
            LEFT JOIN Desarrollo.dbo.SAC_CAR_BIZNESCOB S WITH(NOLOCK)
                ON RIGHT('00000000000000000000' + CAST(C.Operacion AS NVARCHAR(20)), 20) = S.[Cod Operación]
            WHERE {where}
            ORDER BY C.Operacion
            """,
            *params,
        )
        return fetch_resultset(cursor)
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()


def consultar_datos_documento_castigo(cartera_id=124, dni=None, operacion=None, limit=20):
    table = "Desarrollo.dbo.COMPARTAMOS_CASTIGO" if int(cartera_id or 124) == 124 else "Desarrollo.dbo.COMPARTAMOS_GRUPAL_CASTIGO"
    producto_sql = "PRODUCTO INDIVIDUAL" if int(cartera_id or 124) == 124 else "PRODUCTO GRUPAL"
    where, params = filtros_documento_castigo(dni=dni, operacion=operacion)

    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            f"""
            SELECT TOP {int(limit)}
                C.NumDoc AS NumDocumento,
                C.Operacion,
                C.NomCliente,
                CAST(NULL AS NVARCHAR(500)) AS DireccionPrincipal,
                CAST(NULL AS NVARCHAR(160)) AS Distrito_Principal,
                (C.SdoCap * (1 - C.Porcent_Camp)) AS MtoCancelacionCliente,
                CAST(NULL AS INT) AS NroCuotas_Aprobadas,
                CAST(NULL AS INT) AS NroCuotasPagadas,
                CAST(NULL AS INT) AS NroCuotas,
                CAST(NULL AS INT) AS DiasAtraso,
                CAST(NULL AS NVARCHAR(50)) AS CodCuenta,
                C.CtaCliente,
                CAST(NULL AS NVARCHAR(50)) AS CodigoGrupo,
                CAST(NULL AS NVARCHAR(50)) AS CodCreGrupal,
                CAST(NULL AS NVARCHAR(255)) AS NomGrupo,
                C.NomOficina,
                C.SdoCap AS SdoCapital,
                S.[Deuda_Total ] AS DeudaTotal,
                CAST(NULL AS DECIMAL(18,2)) AS CT1,
                CAST(NULL AS DECIMAL(18,2)) AS CT11,
                CAST(NULL AS DECIMAL(18,2)) AS CT12,
                CAST(NULL AS DECIMAL(18,2)) AS CT13,
                CAST(NULL AS DECIMAL(18,2)) AS CT14,
                CAST(NULL AS DECIMAL(18,2)) AS CT15,
                CAST(NULL AS DECIMAL(18,2)) AS CT2,
                CAST(NULL AS DECIMAL(18,2)) AS CT21,
                CAST(NULL AS DECIMAL(18,2)) AS CT22,
                CAST(NULL AS DECIMAL(18,2)) AS CT23,
                CAST(NULL AS DECIMAL(18,2)) AS CT24,
                CAST(NULL AS DECIMAL(18,2)) AS CT25,
                CAST(NULL AS NVARCHAR(50)) AS UltCuotaAtrasada,
                CAST('{producto_sql}' AS NVARCHAR(120)) AS Producto,
                C.SdoCap AS CapitalActual,
                S.[Deuda_Total ] AS DeudaTotalActual,
                {cartera_id} AS CarteraId
            FROM {table} C WITH(NOLOCK)
            LEFT JOIN Desarrollo.dbo.SAC_CAR_BIZNESCOB S WITH(NOLOCK)
                ON RIGHT(REPLICATE('0',20) + CAST(CAST(C.Operacion AS BIGINT) AS VARCHAR(20)),20) = S.[Cod Operación]
            WHERE {where}
              AND (S.[SEGMENTO ] IS NULL OR S.[SEGMENTO ] <> 'INCENTIVO DOBLE')
            ORDER BY C.NomCliente, C.Operacion
            """,
            *params,
        )
        return fetch_resultset(cursor)
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()


def factor_campania_mibanco(prioridad, dias_mora):
    """Descuento de la matriz Mibanco; fuera de matriz se usa 50% del capital."""
    prioridad = limpiar_texto(prioridad).upper()
    dias = int(decimal_value(dias_mora, Decimal("0")) or 0)
    tramos = [
        (151, 360, {"PRIORIDAD 3": Decimal("0.60"), "PRIORIDAD 2": Decimal("0.65"), "PRIORIDAD 1": Decimal("0.70")} ),
        (361, 720, {"PRIORIDAD 3": Decimal("0.65"), "PRIORIDAD 2": Decimal("0.70"), "PRIORIDAD 1": Decimal("0.75")} ),
        (721, 1440, {"PRIORIDAD 3": Decimal("0.70"), "PRIORIDAD 2": Decimal("0.75"), "PRIORIDAD 1": Decimal("0.80")} ),
        (1441, 2160, {"PRIORIDAD 3": Decimal("0.75"), "PRIORIDAD 2": Decimal("0.80"), "PRIORIDAD 1": Decimal("0.85")} ),
        (2161, 2700, {"PRIORIDAD 3": Decimal("0.80"), "PRIORIDAD 2": Decimal("0.85"), "PRIORIDAD 1": Decimal("0.90")} ),
        (2701, 3240, {"PRIORIDAD 3": Decimal("0.85"), "PRIORIDAD 2": Decimal("0.90"), "PRIORIDAD 1": Decimal("0.95")} ),
        (3241, None, {"PRIORIDAD 3": Decimal("0.85"), "PRIORIDAD 2": Decimal("0.90"), "PRIORIDAD 1": Decimal("0.95")} ),
    ]
    for inicio, fin, factores in tramos:
        if dias >= inicio and (fin is None or dias <= fin):
            return factores.get(prioridad)
    return None


def calcular_campania_mibanco(row):
    capital = decimal_value(row.get("SdoCapital"), Decimal("0")) or Decimal("0")
    factor = factor_campania_mibanco(row.get("PrioridadCastigo"), row.get("DiasAtraso"))
    porcentaje_pago = Decimal("0.50") if factor is None else Decimal("1") - factor
    # CEILING de SQL para preservar la regla entregada por Mibanco.
    return (capital * porcentaje_pago).to_integral_value(rounding="ROUND_CEILING")


def consultar_datos_documento_mibanco(dni=None, operacion=None, codigo_cliente=None, nombre_cliente=None, limit=100):
    if limpiar_texto(operacion):
        where, params = "CAST(C.COD_PRE AS VARCHAR(50)) = ?", [limpiar_texto(operacion)]
    elif limpiar_texto(dni):
        where, params = "RTRIM(LTRIM(CAST(C.NRO_DOC AS VARCHAR(50)))) = ?", [limpiar_texto(dni)]
    elif limpiar_texto(codigo_cliente):
        where, params = "RTRIM(LTRIM(CAST(C.COD_CLI AS VARCHAR(50)))) = ?", [limpiar_texto(codigo_cliente)]
    elif limpiar_texto(nombre_cliente):
        where, params = "UPPER(RTRIM(LTRIM(C.NOM_CLI))) LIKE ?", [f"%{limpiar_texto(nombre_cliente).upper()}%"]
    else:
        raise ValueError("Ingresa DNI, operacion, codigo de cliente o nombre para buscar en Mibanco castigo.")

    conn = cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            f"""
            SELECT TOP {int(limit)}
                C.NRO_DOC AS NumDocumento, C.COD_PRE AS Operacion, C.COD_CLI AS CtaCliente,
                C.NOM_CLI AS NomCliente, C.DIR_DOM AS DireccionPrincipal, C.PRODUCTO AS Producto,
                C.SAL_PRE AS SdoCapital, C.IMP_TOT_DEU AS DeudaTotal,
                C.DIA_MOR AS DiasAtraso, C.PRIORIDAD_CAST_COBEX AS PrioridadCastigo,
                C.TIPO_PRODUCTO AS TipoProducto,
                CASE WHEN TRY_CONVERT(INT, C.MONEDA) = 1 THEN 'S' ELSE RTRIM(LTRIM(CAST(C.MONEDA AS VARCHAR(20)))) END AS Moneda,
                CAST(NULL AS NVARCHAR(100)) AS CodigoGrupo,
                CAST(NULL AS NVARCHAR(100)) AS CodCreGrupal,
                CAST(NULL AS NVARCHAR(255)) AS NomGrupo,
                CAST(NULL AS NVARCHAR(100)) AS NomOficina,
                112 AS CarteraId
            FROM Desarrollo.dbo.ACT_MIBANCO_CASTIGO C WITH(NOLOCK)
            WHERE {where}
              AND UPPER(RTRIM(LTRIM(C.ESTADO))) = 'CASTIGADO'
              AND UPPER(RTRIM(LTRIM(C.TIPO_PRODUCTO))) = 'PRODUCTOS PROPIOS'
            ORDER BY C.COD_PRE
            """,
            *params,
        )
        rows = fetch_resultset(cursor)
        for row in rows:
            row["MtoCancelacionCliente"] = float(calcular_campania_mibanco(row))
        return rows
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()


def consultar_datos_documento_sip(dni=None, operacion=None, nombre_cliente=None, limit=20):
    if limpiar_texto(operacion):
        where, params = "RTRIM(LTRIM(CAST(F.NUM_CUENTA_ORI AS VARCHAR(50)))) = ?", [limpiar_texto(operacion)]
    elif limpiar_texto(dni):
        where, params = "RTRIM(LTRIM(CAST(F.DNI AS VARCHAR(50)))) = ?", [limpiar_texto(dni)]
    elif limpiar_texto(nombre_cliente):
        where, params = "UPPER(RTRIM(LTRIM(F.NOMBRE_COMPLETO))) LIKE ?", [f"%{limpiar_texto(nombre_cliente).upper()}%"]
    else:
        raise ValueError("Ingresa documento, nombre u operacion para buscar en Financiera OH - SIP.")

    conn = cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            f"""
            SELECT TOP {int(limit)}
                CASE UPPER(LEFT(RTRIM(LTRIM(CAST(F.IDENTITY_CODE AS VARCHAR(50)))), 1))
                    WHEN 'D' THEN 'DNI'
                    WHEN 'C' THEN 'C.E.'
                    WHEN 'R' THEN 'RUC'
                    ELSE LEFT(RTRIM(LTRIM(CAST(F.IDENTITY_CODE AS VARCHAR(50)))), 1)
                END AS TipoDocumento,
                F.DNI AS NumDocumento,
                F.NOMBRE_COMPLETO AS NomCliente,
                F.NUM_CUENTA_ORI AS Operacion,
                F.NUM_CUENTA_ORI AS CtaCliente,
                F.SLD_TOTAL_ASIG AS DeudaTotal,
                M.MejorLTD,
                TRY_CONVERT(DECIMAL(18, 2), M.MejorLTD) AS MtoCancelacionCliente,
                CAST(NULL AS NVARCHAR(255)) AS DireccionPrincipal,
                CAST(NULL AS NVARCHAR(100)) AS CodigoGrupo,
                CAST(NULL AS NVARCHAR(100)) AS CodCreGrupal,
                CAST(NULL AS NVARCHAR(255)) AS NomGrupo,
                CAST(NULL AS NVARCHAR(100)) AS NomOficina,
                CAST(NULL AS DECIMAL(18, 2)) AS SdoCapital,
                'S' AS Moneda,
                132 AS CarteraId
            FROM Desarrollo.dbo.actualizacionfoh F WITH(NOLOCK)
            CROSS APPLY (
                SELECT CASE
                    WHEN F.LTD_PLUS <> 0 AND F.LTD_PLUS IS NOT NULL THEN CAST(F.LTD_PLUS AS VARCHAR(50))
                    WHEN F.LTD_ESPECIAL_FERIA <> 0 AND F.LTD_ESPECIAL_FERIA IS NOT NULL THEN CAST(F.LTD_ESPECIAL_FERIA AS VARCHAR(50))
                    WHEN F.LTD <> 0 AND F.LTD IS NOT NULL THEN CAST(F.LTD AS VARCHAR(50))
                    ELSE 'CONVENIO'
                END AS MejorLTD
            ) M
            WHERE {where}
            ORDER BY F.NOMBRE_COMPLETO, F.NUM_CUENTA_ORI
            """,
            *params,
        )
        return fetch_resultset(cursor)
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()


def obtener_registro_unico(dni=None, operacion=None, codigo_grupo=None, cod_cre_grupal=None, cartera_id=133):
    rows = consultar_datos_documento(
        dni=dni,
        operacion=operacion,
        codigo_grupo=codigo_grupo,
        cod_cre_grupal=cod_cre_grupal,
        limit=2,
        cartera_id=cartera_id,
    )

    if not rows:
        raise ValueError("No se encontro informacion para generar el documento.")

    if len(rows) > 1 and not limpiar_texto(operacion):
        raise ValueError("La busqueda devolvio mas de una operacion. Selecciona una operacion antes de generar.")

    return rows[0]


def validar_cancelacion(cancelacion, minimo, excepcion=False):
    monto_cancelacion = decimal_value(cancelacion)
    monto_minimo = decimal_value(minimo, Decimal("0"))

    if monto_cancelacion is None or monto_cancelacion <= 0:
        raise ValueError("Ingresa un monto de cancelacion valido.")

    if not excepcion and monto_cancelacion <= monto_minimo:
        raise ValueError(
            f"La cancelacion debe ser mayor a S/ {format_money(monto_minimo)} "
            f"(Mto CancelacionCliente de la consulta SQL)."
        )

    return monto_cancelacion, monto_minimo


def safe_filename(value):
    text = re.sub(r"[^A-Za-z0-9_-]+", "_", limpiar_texto(value))
    return text.strip("_") or "documento"


W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def extract_mergefield_name(instr_text):
    match = re.search(r'MERGEFIELD\s+"?([^"\\\s]+)"?', instr_text, flags=re.IGNORECASE)
    return match.group(1).strip() if match else None


def normalizar_field_name(value):
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(char for char in text if not unicodedata.combining(char))
    return text.strip().upper()


def flatten_mergefields(xml, field_values):
    normalized_values = {
        normalizar_field_name(key): value
        for key, value in field_values.items()
    }

    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        return xml

    def fld_char_type(run):
        fld = run.find(f"{{{W_NS}}}fldChar")
        if fld is None:
            return None
        return fld.attrib.get(f"{{{W_NS}}}fldCharType")

    def field_name_from_runs(runs):
        instr_text = "".join(
            node.text or ""
            for run in runs
            for node in run.iter(f"{{{W_NS}}}instrText")
        )
        return extract_mergefield_name(instr_text)

    def run_text(run):
        return "".join(node.text or "" for node in run.iter(f"{{{W_NS}}}t"))

    for paragraph in root.iter(f"{{{W_NS}}}p"):
        children = list(paragraph)
        index = 0

        while index < len(children):
            child = children[index]

            if child.tag != f"{{{W_NS}}}r" or fld_char_type(child) != "begin":
                index += 1
                continue

            end_index = None
            for candidate in range(index + 1, len(children)):
                if children[candidate].tag == f"{{{W_NS}}}r" and fld_char_type(children[candidate]) == "end":
                    end_index = candidate
                    break

            if end_index is None:
                index += 1
                continue

            field_runs = children[index:end_index + 1]
            field_name = field_name_from_runs(field_runs)
            normalized_name = normalizar_field_name(field_name)

            if normalized_name not in normalized_values:
                index = end_index + 1
                continue

            if (
                normalized_name == "CANCELACION"
                and end_index + 1 < len(children)
                and children[end_index + 1].tag == f"{{{W_NS}}}r"
                and run_text(children[end_index + 1]) == ".00"
            ):
                field_runs = children[index:end_index + 2]

            run = ET.Element(f"{{{W_NS}}}r")
            text = ET.SubElement(run, f"{{{W_NS}}}t")
            text.text = str(normalized_values[normalized_name])

            for old_run in field_runs:
                paragraph.remove(old_run)

            paragraph.insert(index, run)
            children = list(paragraph)
            index += 1

    return ET.tostring(root, encoding="unicode")


def replace_in_xml(xml, replacements, field_values, flatten_fields=False):
    xml = re.sub(r"<w:mailMerge\b.*?</w:mailMerge>", "", xml, flags=re.DOTALL)

    if flatten_fields:
        xml = flatten_mergefields(xml, field_values)

    for source, target in replacements.items():
        xml = xml.replace(source, escape(str(target)))

    xml = re.sub(r"<w:highlight\b[^>]*/>", "", xml)
    return xml


def generar_docx_desde_template(template_path, output_path, replacements):
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(template_path, "r") as zin, zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)

            if item.filename.startswith("word/") and item.filename.endswith(".xml"):
                xml = data.decode("utf-8")
                data = replace_in_xml(
                    xml,
                    replacements,
                    replacements,
                    flatten_fields=item.filename == "word/document.xml",
                ).encode("utf-8")

            if item.filename == "word/_rels/settings.xml.rels":
                data = (
                    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>'
                ).encode("utf-8")

            zout.writestr(item, data)


WORD_NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}


def reemplazar_texto_ooxml(element, value):
    textos = element.findall(".//w:t", WORD_NS)
    if not textos:
        return
    textos[0].text = str(value or "")
    for texto in textos[1:]:
        texto.text = ""


def reemplazar_texto_parrafo_ooxml(paragraph, marker, value):
    """Cambia solo el texto de datos y conserva los rótulos decorativos del modelo."""
    for texto in paragraph.findall(".//w:t", WORD_NS):
        if marker in (texto.text or ""):
            texto.text = str(value or "")
            return


def reemplazar_nodo_texto_ooxml(paragraph, index, value):
    textos = paragraph.findall(".//w:t", WORD_NS)
    if 0 <= index < len(textos):
        textos[index].text = str(value or "")


def celdas_ooxml(row):
    return row.findall("w:tc", WORD_NS)


def generar_docx_sip_desde_template(output_path, context):
    """Completa la plantilla SIP preservando su estructura, estilos y espacios."""
    if not SIP_TEMPLATE_PATH.exists():
        generar_docx_limpio(output_path, context, document_kind="sip_convenio")
        return

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(SIP_TEMPLATE_PATH, "r") as zin, zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == "word/document.xml":
                root = ET.fromstring(data)
                body = root.find("w:body", WORD_NS)
                paragraphs = body.findall("w:p", WORD_NS) if body is not None else []
                tables = body.findall("w:tbl", WORD_NS) if body is not None else []

                # Solo se tocan los nodos de datos: los títulos gráficos y su formato
                # permanecen intactos dentro de la plantilla.
                if len(paragraphs) > 2:
                    reemplazar_nodo_texto_ooxml(paragraphs[2], 1, context["tipo_documento"])
                    reemplazar_nodo_texto_ooxml(paragraphs[2], 5, context["dni"])
                if len(paragraphs) > 3:
                    reemplazar_nodo_texto_ooxml(paragraphs[3], 5, context["cliente"])
                if len(paragraphs) > 5:
                    reemplazar_nodo_texto_ooxml(paragraphs[5], 15, context["tarjeta"])
                if len(paragraphs) > 7:
                    reemplazar_nodo_texto_ooxml(paragraphs[7], 1, f" {context['cuota_inicial']} ")
                    reemplazar_nodo_texto_ooxml(paragraphs[7], 2, "")
                    reemplazar_nodo_texto_ooxml(paragraphs[7], 3, "")
                    reemplazar_nodo_texto_ooxml(paragraphs[7], 4, "")
                # Los tres canales se muestran como lista tanto en Word como en PDF.
                for index in (17, 18, 19):
                    if len(paragraphs) > index:
                        texto = "".join(node.text or "" for node in paragraphs[index].findall(".//w:t", WORD_NS)).strip()
                        reemplazar_texto_ooxml(paragraphs[index], f"• {texto}")

                if len(tables) >= 2:
                    resumen = tables[0].findall("w:tr", WORD_NS)
                    resumen_values = [
                        [f"Fecha Solicitud:            {context['fecha_solicitud']}", "           Deuda total: ", f"S/{context['deuda_total']}"],
                        ["Tipo de facilidad:         Convenio Pago", "           Monto Cuota:", f"S/{context['cuota_regular']}"],
                        [f"Monto Convenio:          {context['monto_convenio']} SOLES", "Nro. Cuotas:", str(context['cantidad_cuotas'])],
                    ]
                    for row, values in zip(resumen, resumen_values):
                        for cell, value in zip(celdas_ooxml(row), values):
                            reemplazar_texto_ooxml(cell, value)

                    detalle = tables[1].findall("w:tr", WORD_NS)
                    detalle_values = [
                        ["Monto convenio", context["monto_convenio"]],
                        ["Cuota Inicial", context["cuota_inicial"]],
                        ["Numero de Cuotas", str(context["cantidad_cuotas"])],
                        ["Monto de cuota", context["cuota_regular"]],
                    ]
                    for row, values in zip(detalle, detalle_values):
                        for cell, value in zip(celdas_ooxml(row), values):
                            reemplazar_texto_ooxml(cell, value)

                if len(tables) >= 3:
                    cronograma_table = tables[2]
                    cronograma_rows = cronograma_table.findall("w:tr", WORD_NS)
                    cronograma = tabla_cronograma_sip(context)
                    if len(cronograma) > len(cronograma_rows) - 1 and len(cronograma_rows) > 1:
                        row_template = cronograma_rows[-1]
                        for _ in range(len(cronograma) - (len(cronograma_rows) - 1)):
                            cronograma_table.append(deepcopy(row_template))
                        cronograma_rows = cronograma_table.findall("w:tr", WORD_NS)
                    for row in cronograma_rows[1:]:
                        for cell in celdas_ooxml(row):
                            reemplazar_texto_ooxml(cell, "")
                    for row, values in zip(cronograma_rows[1:], cronograma):
                        for cell, value in zip(celdas_ooxml(row), values):
                            reemplazar_texto_ooxml(cell, value)

                ET.register_namespace("w", WORD_NS["w"])
                data = ET.tostring(root, encoding="utf-8", xml_declaration=True)
            zout.writestr(item, data)


def xml_text(value):
    return escape(str(value or ""))


def run_xml(text, bold=False, size=19, underline=False, color=None):
    bold_xml = "<w:b/>" if bold else ""
    underline_xml = '<w:u w:val="single"/>' if underline else ""
    color_xml = f'<w:color w:val="{color}"/>' if color else ""
    return (
        "<w:r><w:rPr>"
        f'<w:rFonts w:ascii="{FONT_FAMILY}" w:hAnsi="{FONT_FAMILY}" w:cs="{FONT_FAMILY}"/>'
        f"{bold_xml}{underline_xml}{color_xml}<w:sz w:val=\"{size}\"/><w:szCs w:val=\"{size}\"/>"
        f"</w:rPr><w:t xml:space=\"preserve\">{xml_text(text)}</w:t></w:r>"
    )


def paragraph_xml(text="", bold=False, align="both", before=0, after=72, size=19, keep_next=False):
    keep_xml = "<w:keepNext/>" if keep_next else ""
    return (
        "<w:p><w:pPr>"
        f"{keep_xml}<w:spacing w:before=\"{before}\" w:after=\"{after}\" w:line=\"240\" w:lineRule=\"auto\"/>"
        f"<w:jc w:val=\"{align}\"/>"
        "</w:pPr>"
        f"{run_xml(text, bold=bold, size=size)}"
        "</w:p>"
    )


def paragraph_runs_xml(runs, align="both", before=0, after=72, size=19, keep_next=False):
    keep_xml = "<w:keepNext/>" if keep_next else ""
    runs_body = "".join(
        run_xml(
            item.get("text", ""),
            bold=item.get("bold", False),
            underline=item.get("underline", False),
            size=item.get("size", size),
            color=item.get("color"),
        )
        for item in runs
    )
    return (
        "<w:p><w:pPr>"
        f"{keep_xml}<w:spacing w:before=\"{before}\" w:after=\"{after}\" w:line=\"240\" w:lineRule=\"auto\"/>"
        f"<w:jc w:val=\"{align}\"/>"
        "</w:pPr>"
        f"{runs_body}"
        "</w:p>"
    )


def title_xml(text):
    return paragraph_xml(text, bold=True, align="center", before=0, after=130, size=22, keep_next=True)


def centered_xml(text="", bold=False, before=0, after=50, size=18):
    return paragraph_xml(text, bold=bold, align="center", before=before, after=after, size=size)


def right_xml(text="", bold=False, before=0, after=70, size=18):
    return paragraph_xml(text, bold=bold, align="right", before=before, after=after, size=size)


def image_xml(rel_id="rIdFirmaLuis", doc_id=1, cx=1500000, cy=760000, align="center"):
    return (
        f"<w:p><w:pPr><w:spacing w:before=\"0\" w:after=\"0\"/><w:jc w:val=\"{align}\"/></w:pPr><w:r>"
        "<w:drawing>"
        "<wp:inline xmlns:wp=\"http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing\" distT=\"0\" distB=\"0\" distL=\"0\" distR=\"0\">"
        f"<wp:extent cx=\"{cx}\" cy=\"{cy}\"/>"
        "<wp:effectExtent l=\"0\" t=\"0\" r=\"0\" b=\"0\"/>"
        f"<wp:docPr id=\"{doc_id}\" name=\"Firma Luis Portuguez\"/>"
        "<wp:cNvGraphicFramePr><a:graphicFrameLocks xmlns:a=\"http://schemas.openxmlformats.org/drawingml/2006/main\" noChangeAspect=\"1\"/></wp:cNvGraphicFramePr>"
        "<a:graphic xmlns:a=\"http://schemas.openxmlformats.org/drawingml/2006/main\">"
        "<a:graphicData uri=\"http://schemas.openxmlformats.org/drawingml/2006/picture\">"
        "<pic:pic xmlns:pic=\"http://schemas.openxmlformats.org/drawingml/2006/picture\">"
        "<pic:nvPicPr><pic:cNvPr id=\"1\" name=\"firma_luis_portuguez.png\"/><pic:cNvPicPr/></pic:nvPicPr>"
        "<pic:blipFill>"
        f"<a:blip xmlns:r=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships\" r:embed=\"{rel_id}\"/>"
        "<a:stretch><a:fillRect/></a:stretch>"
        "</pic:blipFill>"
        "<pic:spPr><a:xfrm><a:off x=\"0\" y=\"0\"/>"
        f"<a:ext cx=\"{cx}\" cy=\"{cy}\"/>"
        "</a:xfrm><a:prstGeom prst=\"rect\"><a:avLst/></a:prstGeom></pic:spPr>"
        "</pic:pic></a:graphicData></a:graphic>"
        "</wp:inline>"
        "</w:drawing>"
        "</w:r></w:p>"
    )


def table_cell(text, bold=False, width=2400, align="center"):
    return (
        "<w:tc><w:tcPr>"
        f"<w:tcW w:w=\"{width}\" w:type=\"dxa\"/>"
        '<w:vAlign w:val="center"/>'
        '<w:tcMar><w:top w:w="50" w:type="dxa"/><w:left w:w="100" w:type="dxa"/>'
        '<w:bottom w:w="50" w:type="dxa"/><w:right w:w="100" w:type="dxa"/></w:tcMar>'
        "</w:tcPr>"
        f"{paragraph_xml(text, bold=bold, align=align, after=0, size=18)}"
        "</w:tc>"
    )


def payment_table_xml(cancelacion, fecha_pago):
    borders = (
        "<w:tblBorders>"
        '<w:top w:val="single" w:sz="8" w:space="0" w:color="000000"/>'
        '<w:left w:val="single" w:sz="8" w:space="0" w:color="000000"/>'
        '<w:bottom w:val="single" w:sz="8" w:space="0" w:color="000000"/>'
        '<w:right w:val="single" w:sz="8" w:space="0" w:color="000000"/>'
        '<w:insideH w:val="single" w:sz="8" w:space="0" w:color="000000"/>'
        '<w:insideV w:val="single" w:sz="8" w:space="0" w:color="000000"/>'
        "</w:tblBorders>"
    )
    return (
        "<w:tbl><w:tblPr>"
        '<w:tblW w:w="4400" w:type="dxa"/>'
        '<w:jc w:val="center"/>'
        f"{borders}"
        '<w:tblCellMar><w:top w:w="80" w:type="dxa"/><w:left w:w="100" w:type="dxa"/>'
        '<w:bottom w:w="80" w:type="dxa"/><w:right w:w="100" w:type="dxa"/></w:tblCellMar>'
        "</w:tblPr>"
        '<w:tblGrid><w:gridCol w:w="2200"/><w:gridCol w:w="2200"/></w:tblGrid>'
        f"<w:tr>{table_cell('Monto', bold=True)}{table_cell('Fecha de Pago/ Cancelación', bold=True)}</w:tr>"
        f"<w:tr>{table_cell(f'S/ {cancelacion}')}{table_cell(fecha_pago)}</w:tr>"
        "</w:tbl>"
    )


def simple_table_xml(headers, rows, col_widths, font_size=17):
    borders = (
        "<w:tblBorders>"
        '<w:top w:val="single" w:sz="8" w:space="0" w:color="000000"/>'
        '<w:left w:val="single" w:sz="8" w:space="0" w:color="000000"/>'
        '<w:bottom w:val="single" w:sz="8" w:space="0" w:color="000000"/>'
        '<w:right w:val="single" w:sz="8" w:space="0" w:color="000000"/>'
        '<w:insideH w:val="single" w:sz="8" w:space="0" w:color="000000"/>'
        '<w:insideV w:val="single" w:sz="8" w:space="0" w:color="000000"/>'
        "</w:tblBorders>"
    )
    total_width = sum(col_widths)
    grid = "".join(f'<w:gridCol w:w="{width}"/>' for width in col_widths)

    def cell(value, width, bold=False, align="center"):
        return (
            "<w:tc><w:tcPr>"
            f'<w:tcW w:w="{width}" w:type="dxa"/>'
            '<w:vAlign w:val="center"/>'
            '<w:tcMar><w:top w:w="70" w:type="dxa"/><w:left w:w="95" w:type="dxa"/>'
            '<w:bottom w:w="70" w:type="dxa"/><w:right w:w="95" w:type="dxa"/></w:tcMar>'
            "</w:tcPr>"
            f"{paragraph_xml(str(value), bold=bold, align=align, after=0, size=font_size)}"
            "</w:tc>"
        )

    header_row = "<w:tr>" + "".join(cell(h, col_widths[i], bold=True) for i, h in enumerate(headers)) + "</w:tr>"
    body_rows = "".join(
        "<w:tr>" + "".join(cell(value, col_widths[i], align="left" if i == 2 else "center") for i, value in enumerate(row)) + "</w:tr>"
        for row in rows
    )
    return (
        "<w:tbl><w:tblPr>"
        f'<w:tblW w:w="{total_width}" w:type="dxa"/>'
        '<w:tblLayout w:type="fixed"/>'
        '<w:tblInd w:w="0" w:type="dxa"/>'
        '<w:jc w:val="center"/>'
        f"{borders}</w:tblPr><w:tblGrid>{grid}</w:tblGrid>{header_row}{body_rows}</w:tbl>"
    )


def mibanco_schedule_table_xml(headers, rows):
    col_widths = [1200, 1200, 1050, 1050, 1050, 800, 1050, 1600]
    borders = (
        "<w:tblBorders>"
        '<w:top w:val="single" w:sz="8" w:color="000000"/>'
        '<w:left w:val="single" w:sz="8" w:color="000000"/>'
        '<w:bottom w:val="single" w:sz="8" w:color="000000"/>'
        '<w:right w:val="single" w:sz="8" w:color="000000"/>'
        '<w:insideH w:val="single" w:sz="8" w:color="000000"/>'
        '<w:insideV w:val="single" w:sz="8" w:color="000000"/>'
        "</w:tblBorders>"
    )
    grid = "".join(f'<w:gridCol w:w="{width}"/>' for width in col_widths)

    def cell(value, width, header=False, highlight=False, bold=False):
        shading = '<w:shd w:val="clear" w:color="auto" w:fill="008D48"/>' if header else (
            '<w:shd w:val="clear" w:color="auto" w:fill="FFF200"/>' if highlight else ""
        )
        color = "FFFFFF" if header else None
        return (
            '<w:tc><w:tcPr>'
            f'<w:tcW w:w="{width}" w:type="dxa"/>{shading}'
            '<w:vAlign w:val="center"/>'
            '<w:tcMar><w:top w:w="80" w:type="dxa"/><w:left w:w="80" w:type="dxa"/>'
            '<w:bottom w:w="80" w:type="dxa"/><w:right w:w="80" w:type="dxa"/></w:tcMar>'
            '</w:tcPr>'
            f'{paragraph_runs_xml([{"text": str(value), "bold": header or bold, "color": color}], align="center", after=0, size=14)}'
            '</w:tc>'
        )

    header_row = '<w:tr>' + ''.join(cell(value, col_widths[index], header=True) for index, value in enumerate(headers)) + '</w:tr>'
    body_rows = ''.join(
        '<w:tr>' + ''.join(
            cell(value, col_widths[index], highlight=index == 2 and bool(value), bold=row[0] == 'TOTAL')
            for index, value in enumerate(row)
        ) + '</w:tr>'
        for row in rows
    )
    return (
        '<w:tbl><w:tblPr><w:tblW w:w="9000" w:type="dxa"/><w:tblLayout w:type="fixed"/>'
        '<w:tblInd w:w="0" w:type="dxa"/><w:jc w:val="center"/>'
        f'{borders}</w:tblPr><w:tblGrid>{grid}</w:tblGrid>{header_row}{body_rows}</w:tbl>'
    )


def mibanco_title_bar_xml():
    return (
        '<w:tbl><w:tblPr><w:tblW w:w="9000" w:type="dxa"/><w:tblLayout w:type="fixed"/>'
        '<w:tblInd w:w="0" w:type="dxa"/><w:jc w:val="center"/>'
        '<w:tblBorders><w:top w:val="single" w:sz="12" w:color="000000"/><w:left w:val="single" w:sz="12" w:color="000000"/>'
        '<w:bottom w:val="single" w:sz="12" w:color="000000"/><w:right w:val="single" w:sz="12" w:color="000000"/></w:tblBorders></w:tblPr>'
        '<w:tblGrid><w:gridCol w:w="9000"/></w:tblGrid><w:tr><w:tc><w:tcPr><w:tcW w:w="9000" w:type="dxa"/>'
        '<w:shd w:val="clear" w:color="auto" w:fill="008D48"/></w:tcPr>'
        '<w:p><w:pPr><w:jc w:val="center"/><w:spacing w:before="45" w:after="45"/></w:pPr>'
        f'{run_xml("ACUERDO DE CANCELACION DE DEUDA", bold=True, size=22, color="FFFFFF")}</w:p></w:tc></w:tr></w:tbl>'
    )


def mibanco_signature_table_xml(context, before=260, after=20):
    left = signature_cell_xml("ROSARIO RODRIGUEZ MOSCOSO", cargo="REPRESENTANTE\nMIBANCO", width=4500)
    right = signature_cell_xml(context["cliente"], dni=context["dni"], cargo="CLIENTE", width=4500)
    return (
        paragraph_runs_xml([{"text": "Área de Recuperaciones", "bold": True, "underline": True}], align="center", before=before, after=210, size=18)
        + '<w:tbl><w:tblPr><w:tblW w:w="9000" w:type="dxa"/><w:tblLayout w:type="fixed"/>'
        '<w:tblInd w:w="0" w:type="dxa"/><w:jc w:val="center"/></w:tblPr>'
        '<w:tblGrid><w:gridCol w:w="4500"/><w:gridCol w:w="4500"/></w:tblGrid>'
        f"<w:tr>{left}{right}</w:tr></w:tbl>" + paragraph_xml("", after=after)
    )


def signature_cell_xml(label, dni="", cargo="", width=3600, firma=False, doc_id=1):
    firma_xml = image_xml(doc_id=doc_id) if firma and FIRMA_LUIS_PATH.exists() else ""
    if firma_xml:
        return (
            "<w:tc><w:tcPr>"
            f"<w:tcW w:w=\"{width}\" w:type=\"dxa\"/>"
            '<w:vAlign w:val="bottom"/>'
            '<w:tcMar><w:top w:w="80" w:type="dxa"/><w:left w:w="120" w:type="dxa"/>'
            '<w:bottom w:w="80" w:type="dxa"/><w:right w:w="120" w:type="dxa"/></w:tcMar>'
            "</w:tcPr>"
            + firma_xml
            + "</w:tc>"
        )

    return (
        "<w:tc><w:tcPr>"
        f"<w:tcW w:w=\"{width}\" w:type=\"dxa\"/>"
        '<w:vAlign w:val="bottom"/>'
        '<w:tcMar><w:top w:w="80" w:type="dxa"/><w:left w:w="120" w:type="dxa"/>'
        '<w:bottom w:w="80" w:type="dxa"/><w:right w:w="120" w:type="dxa"/></w:tcMar>'
        "</w:tcPr>"
        + centered_xml("____________________________", before=0, after=10, size=17)
        + centered_xml(label, bold=True, after=6, size=17)
        + (centered_xml(f"D.N.I. {dni}", bold=True, after=6, size=17) if dni else "")
        + (centered_xml(cargo, bold=True, after=0, size=16) if cargo else "")
        + "</w:tc>"
    )


def signature_table_xml(dni, before=230, after=60, doc_id=1):
    return (
        paragraph_xml("", before=before, after=0)
        + "<w:tbl><w:tblPr>"
        '<w:tblW w:w="7600" w:type="dxa"/>'
        '<w:jc w:val="center"/>'
        "</w:tblPr>"
        '<w:tblGrid><w:gridCol w:w="3800"/><w:gridCol w:w="3800"/></w:tblGrid>'
        f"<w:tr>{signature_cell_xml('EL/LA DEUDOR/A', dni=dni, width=3800)}{signature_cell_xml(GERENTE_NOMBRE, width=3800, firma=True, doc_id=doc_id)}</w:tr>"
        "</w:tbl>"
        + paragraph_xml("", before=0, after=after)
    )


def page_break_xml():
    return '<w:p><w:r><w:br w:type="page"/></w:r></w:p>'


def clause_xml(label, text, after=120):
    return paragraph_runs_xml(
        [
            {"text": f"{label}.- ", "bold": True, "underline": True},
            {"text": text},
        ],
        after=after,
        size=18,
    )


def clause_exact_xml(label, text, after=70):
    return paragraph_runs_xml(
        [
            {"text": label, "bold": True, "underline": True},
            {"text": text},
        ],
        after=after,
        size=18,
    )


def horizontal_rule_xml(before=80, after=85):
    return (
        "<w:p><w:pPr>"
        f'<w:spacing w:before="{before}" w:after="{after}"/>'
        "<w:pBdr>"
        '<w:bottom w:val="single" w:sz="6" w:space="1" w:color="8A8A8A"/>'
        "</w:pBdr>"
        "</w:pPr></w:p>"
    )


def document_xml(context):
    paragraphs = [
        title_xml("Transacción extrajudicial y Cancelación de Deuda"),
        paragraph_xml(
            "Conste por el presente documento una Transacción Extrajudicial y Cancelación de Deuda, que celebran "
            "de una parte la Empresa de cobranza BIZNESCOB, con RUC 20602593640, con domicilio en Enrique Encinas "
            "284 la victoria y representado por el sr(a) LUIS PORTUGUEZ BERROCAL identificado con DNI 10416012, "
            "por encargo de COMPARTAMOS BANCO S.A.,  en adelante COMPARTAMOS, con domicilio en Av. Paseo de la "
            "Republica N° 5895 – Interior 1301, distrito de Mira flores, provincia y departamento de Lima, inscrita "
            "en la Partida Nro. 13777030 del Registro de Personas Jurídicas de la Zona Registral Nro. IX - Sede Lima "
            f"y de otra parte el/la Sr (a) {context['cliente']} identificado con DNI N°.{context['dni']}, con domicilio "
            f"en {context['direccion']}, distrito de {context['distrito']}, a quien en adelante se le denominara  "
            "EL/LA/DEUDOR/A, en los términos y condiciones siguientes:",
            after=70,
            size=18,
        ),
        clause_exact_xml(
            "PRIMERA.- ",
            f"EL DEUDOR reconoce adeudar a COMPARTAMOS BANCO el crédito {context['operacion']}, cuyo  importe "
            f"asciende  a la suma total de S/  {context['deuda_total']},  según liquidación a la fecha.",
            after=65,
        ),
        clause_exact_xml(
            "SEGUNDA- ",
            "De conformidad con lo señalado en la cláusula anterior EL DEUDOR se obliga a cancelar a   COMPARTAMOS "
            "BANCO la deuda antes descrita de la siguiente manera:",
            after=55,
        ),
        payment_table_xml(context["cancelacion"], context["fecha_corta"]),
        paragraph_xml(
            "La cancelación de la suma antes detallada está sujeta al pago acordado en el párrafo que antecede.",
            before=60,
            after=65,
            size=18,
        ),
        clause_exact_xml(
            "TERCERA .- ",
            "Sin perjuicio de lo señalado, COMPARTAMOS se reserva el derecho de iniciar, interponer o continuar "
            "con las acciones administrativas, legales o judiciales en caso de que el EL/LA/DEUDOR/A incumpla las "
            "obligaciones que por el presente documento asume; COMPARTAMOS quedará expedito para su cobro de "
            "conformidad con lo estipulado por inciso 8 del artículo 688 del Código Proceso Civil.",
        ),
        clause_exact_xml(
            "CUARTA .- ",
            "Las garantías y/o fianzas solidarias constituidas en respaldo de la obligación antes señalada subsisten "
            "en tanto no se cancele totalmente la misma por el monto acordado, por cuanto la suscripción de presente "
            "convenio no constituye una novación de la obligación",
        ),
        clause_exact_xml(
            "QUINTA .- ",
            "El incumplimiento o retraso en el pago del monto señalado en la cláusula segunda, a criterio de "
            "COMPARTAMOS, quedarán sin efecto los beneficios (descuentos u otros) otorgados a EL/LA/DEUDOR/A, "
            "recalculando los intereses y mora que se hayan generado posteriormente.",
        ),
        clause_exact_xml(
            "SÉXTA :  ",
            "EL/LA/DEUDOR/A ratifica su voluntad expresada en el presente instrumento, dejando constancia que no    "
            "ha mediado vicio capaz  de invalidarlo.",
            after=80,
        ),
        right_xml(context["fecha_larga"], after=90, size=18),
        signature_table_xml(context["dni"], before=120, after=35, doc_id=1),
        horizontal_rule_xml(before=25, after=75),
        title_xml("NOTA DE ABONO"),
        paragraph_xml(
            "Por el presente documento COMPARTAMOS, concede condonación sobre la deuda de EL/LA/DEUDOR/A, según "
            "las condiciones ofrecidas en la en el presente documento.",
            after=55,
            size=18,
        ),
        paragraph_xml(
            f"Sr(a):{context['cliente']} con DNI Nº {context['dni']} por la suma de S/ {context['condonacion']}",
            bold=True,
            align="center",
            before=40,
            after=60,
            size=19,
        ),
        paragraph_xml(
            "EL/LA/DEUDOR/A, acepta el descuento indicado, reduciendo la deuda vigente que se detalla en la presente "
            "transacción, la misma que mantiene su validez, si EL/LA/DEUDOR/A cumple todas las condiciones descritas "
            "en el documento.",
            after=55,
            size=18,
        ),
        paragraph_xml(
            f"El descuento está sujeto al cumplimiento del pago de: S/ {context['cancelacion']} en las fechas y "
            "formas acordadas en la cláusula segunda.",
            after=60,
            size=18,
        ),
        signature_table_xml(context["dni"], before=230, after=40, doc_id=2),
    ]

    body = "".join(paragraphs)
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f"<w:body>{body}"
        "<w:sectPr>"
        '<w:pgSz w:w="12240" w:h="15840"/>'
        '<w:pgMar w:top="720" w:right="760" w:bottom="720" w:left="760" w:header="360" w:footer="360" w:gutter="0"/>'
        "</w:sectPr></w:body></w:document>"
    )


def document_cuota_individual_xml(context):
    paragraphs = [
        title_xml("COMPROMISO DE PAGO"),
        paragraph_xml(
            "Conste por el presente documento una Transaccion Extrajudicial y Cancelacion de Deuda, que celebran "
            "de una parte la Empresa de cobranza BIZNESCOB, con RUC 20602593640, con domicilio en Enrique Encinas "
            "284 la victoria y representado por el sr(a) LUIS PORTUGUEZ BERROCAL identificado con DNI 10416012, "
            "por encargo de COMPARTAMOS BANCO S.A., en adelante COMPARTAMOS, con domicilio en Av. Paseo de la "
            "Republica Nro. 5895 - Interior 1301, distrito de Miraflores, provincia y departamento de Lima, inscrita "
            "en la Partida Nro. 13777030 del Registro de Personas Juridicas de la Zona Registral Nro. IX - Sede Lima "
            f"y de otra parte el/la Sr(a) {context['cliente']} identificado con DNI Nro. {context['dni']}, con domicilio "
            f"en {context['direccion']}, distrito de {context['distrito']}, a quien en adelante se le denominara "
            "EL/LA/DEUDOR/A, en los terminos y condiciones siguientes:",
            after=70,
            size=18,
        ),
        clause_exact_xml(
            "PRIMERA.- ",
            f"EL DEUDOR reconoce adeudar a COMPARTAMOS BANCO el(los) credito(s) {context['operacion']}, cuyo importe "
            f"asciende a la suma total de S/ {context['deuda_total']}. Segun liquidacion a la fecha.",
            after=60,
        ),
        paragraph_xml(
            f"Asimismo, detallamos que el importe de las cuotas vencidas Nro. {context['nro_cuota']}, asciende a S/. {context['cuota']}.",
            after=60,
            size=18,
        ),
        clause_exact_xml(
            "SEGUNDA- ",
            "De conformidad con lo senalado en la clausula primera EL/LA/DEUDOR/A se obliga a pagar las cuotas "
            "mencionadas en la clausula primera, a favor de COMPARTAMOS de la siguiente manera:",
            after=55,
        ),
        payment_table_xml(context["cancelacion"], context["fecha_corta"]),
        paragraph_xml(
            "El descuento generado por el compromiso esta sujeto al pago acordado en el parrafo que antecede.",
            before=60,
            after=65,
            size=18,
        ),
        clause_exact_xml(
            "TERCERA .- ",
            "Sin perjuicio de lo senalado, COMPARTAMOS se reserva el derecho de iniciar, interponer o continuar "
            "con las acciones administrativas, legales o judiciales, para lograr el recupero total de la deuda, en "
            "caso de que EL/LA/DEUDOR/A incumpla las obligaciones que por el presente documento asume. El pago "
            "acordado en el presente no significa cancelacion total de la deuda.",
        ),
        clause_exact_xml(
            "CUARTA .- ",
            "El incumplimiento o retraso en el pago del monto senalado en la clausula segunda, a criterio de "
            "COMPARTAMOS, quedaran sin efecto los beneficios (descuentos u otros) otorgados a EL/LA/DEUDOR/A, "
            "recalculando los intereses y moras que se hayan generado posteriormente.",
        ),
        clause_exact_xml(
            "QUINTA .- ",
            "EL/LA/DEUDOR/A ratifica su voluntad expresada en el presente instrumento, dejando constancia que no "
            "ha mediado vicio capaz de invalidarlo.",
            after=80,
        ),
        right_xml(context["fecha_larga"], after=90, size=18),
        signature_table_xml(context["dni"], before=120, after=35, doc_id=1),
        horizontal_rule_xml(before=25, after=75),
        title_xml("NOTA DE ABONO"),
        paragraph_xml(
            "Por el presente documento COMPARTAMOS, concede condonacion sobre la deuda de EL/LA/DEUDOR/A, segun "
            "las condiciones ofrecidas en la en el presente documento.",
            after=55,
            size=18,
        ),
        paragraph_xml(
            f"Sr(a): {context['cliente']} con DNI Nro. {context['dni']} por la suma de S/ {context['condonacion']}",
            bold=True,
            align="center",
            before=40,
            after=60,
            size=19,
        ),
        paragraph_xml(
            "EL/LA/DEUDOR/A, acepta el descuento indicado, reduciendo la deuda vigente que se detalla en la presente "
            "transaccion, la misma que mantiene su validez, si EL/LA/DEUDOR/A cumple todas las condiciones descritas "
            f"en el documento. El descuento esta sujeto al cumplimiento del pago de: S/ {context['cancelacion']} "
            "en las fechas y formas acordadas en la clausula segunda.",
            after=60,
            size=18,
        ),
        signature_table_xml(context["dni"], before=230, after=40, doc_id=2),
    ]

    body = "".join(paragraphs)
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f"<w:body>{body}"
        "<w:sectPr>"
        '<w:pgSz w:w="12240" w:h="15840"/>'
        '<w:pgMar w:top="720" w:right="760" w:bottom="720" w:left="760" w:header="360" w:footer="360" w:gutter="0"/>'
        "</w:sectPr></w:body></w:document>"
    )


def document_grupal_xml(context):
    pago_rows = [
        [
            row["cuenta"],
            row["operacion"],
            row["cliente"],
            row["monto_pago"],
        ]
        for row in context["filas"]
    ]
    abono_rows = [
        [
            row["cuenta"],
            row["operacion"],
            row["cliente"],
            row["monto_condonacion"],
        ]
        for row in context["filas"]
    ]
    col_widths = [1450, 1550, 3900, 1250]

    paragraphs = [
        title_xml("Convenio de Pago y Cancelación de Deuda"),
        paragraph_xml(
            "Conste por el presente documento una Transacción Extrajudicial y Cancelación de Deuda, que celebran "
            "de una parte la Empresa de cobranza BIZNESCOB, con RUC 20602593640, con domicilio en Enrique Encinas "
            "284 la victoria y representado por el sr(a) LUIS PORTUGUEZ BERROCAL identificado con DNI 10416012, "
            "por encargo de COMPARTAMOS BANCO S.A.,  en adelante COMPARTAMOS, con domicilio en Av. Paseo de la "
            "Republica N° 5895 – Interior 1301, distrito de Miraflores, provincia y departamento de Lima, inscrita "
            "en la Partida Nro. 13777030 del Registro de Personas Jurídicas de la Zona Registral Nro. IX - Sede Lima "
            f"Y de otra parte en representación del grupo {context['grupo']} el Sr/Sra. {context['encargado_nombre']}  "
            f"identificado con DNI N° {context['encargado_dni']}, con domicilio {context['encargado_direccion']}, "
            f"distrito de {context['encargado_distrito']}  y provincia {context['encargado_provincia']}, en adelante "
            "se denominará EL/LA/DEUDOR/A, en los términos y condiciones siguientes:",
            after=60,
            size=17,
        ),
        clause_exact_xml(
            "Primera: ",
            f"EL/LA/DEUDOR/A, reconoce adeudar a COMPARTAMOS BANCO, el crédito N° {context['credito_grupal']}, "
            f"cuyo importe asciende a la suma total de S/{context['deuda_total']}, según liquidación a la fecha.",
            after=50,
        ),
        clause_exact_xml(
            "Segunda: ",
            "De conformidad con lo señalado en la cláusula anterior EL DEUDOR se obliga a cancelar a COMPARTAMOS "
            "BANCO la deuda antes descrita de la siguiente manera:",
            after=45,
        ),
        simple_table_xml(["Cuenta", "Operación", "Nombre de cliente", "Monto"], pago_rows, col_widths, font_size=16),
        paragraph_xml(f"MONTO TOTAL A PAGAR     {context['total_pago']}", bold=True, align="right", before=35, after=25, size=17),
        paragraph_xml(f"Fecha de pago / cancelación: {context['fecha_corta']}", before=0, after=40, size=17),
        paragraph_xml(
            "La cancelación de la suma antes detallada está sujeta al pago acordado en el párrafo que antecede.",
            after=50,
            size=17,
        ),
        clause_exact_xml(
            "Tercera: ",
            "Sin perjuicio de lo señalado, COMPARTAMOS se reserva el derecho de iniciar, interponer o continuar "
            "con las acciones administrativas, legales o judiciales en caso de que EL/LA/DEUDOR/A incumpla las "
            "obligaciones que por el presente documento asume; COMPARTAMOS quedara expedito para su cobro de "
            "conformidad con lo estipulado por inciso 8 del artículo 688 del Código Procesal Civil",
            after=45,
        ),
        clause_exact_xml(
            "Cuarta: ",
            "Las garantías y/o fianzas solidarias constituidas en respaldo de la obligación antes señalada subsisten "
            "en tanto no se cancele totalmente la misma por el monto acordado, por cuanto la suscripción de presente "
            "convenio no constituye una novación de la obligación.",
            after=45,
        ),
        clause_exact_xml(
            "Quinta: ",
            "El incumplimiento o retraso en el pago del monto señalado en la cláusula segunda, a criterio de "
            "COMPARTAMOS, quedarán sin efecto los beneficios (descuentos u otros) otorgados a EL/LA/DEUDOR/A, "
            "recalculando los intereses y mora que se hayan generado posteriormente.",
            after=45,
        ),
        clause_exact_xml(
            "Sexta: ",
            "EL/LA/DEUDOR/A ratifica su voluntad expresada en el presente instrumento, dejando constancia que no "
            "ha mediado vicio capaz de invalidarlo.",
            after=45,
        ),
        right_xml(f"Lima, {context['fecha_larga']}", after=50, size=17),
        signature_table_xml(context["encargado_dni"], before=90, after=30, doc_id=1),
        horizontal_rule_xml(before=20, after=60),
        title_xml("NOTA DE ABONO"),
        paragraph_xml(
            "Por el presente documento COMPARTAMOS, concede condonación sobre la deuda de EL/LA/DEUDOR/A, según "
            "las condiciones ofrecidas en la en el presente documento.",
            after=45,
            size=17,
        ),
        paragraph_xml(
            f"Sr(a):  {context['encargado_nombre']}  con DNI Nº  {context['encargado_dni']}",
            align="left",
            before=0,
            after=40,
            size=17,
        ),
        simple_table_xml(["Cuenta", "Operación", "Nombre de cliente", "Monto"], abono_rows, col_widths, font_size=16),
        paragraph_xml(f"POR LA SUMA DE: S/ {context['total_condonacion']}", bold=True, align="left", before=35, after=35, size=17),
        paragraph_xml(
            "EL/LA/DEUDOR/A, acepta el descuento indicado, reduciendo la deuda vigente que se detalla en la presente "
            "transacción, la misma que mantiene su validez, si EL/LA/DEUDOR/A cumple todas las condiciones descritas "
            "en el documento. El descuento está sujeto al cumplimiento del pago de",
            after=30,
            size=17,
        ),
        paragraph_xml(
            f"S/ {context['total_pago']} en las fechas y formas acordadas en la cláusula segunda.",
            after=45,
            size=17,
        ),
        signature_table_xml(context["encargado_dni"], before=90, after=20, doc_id=2),
    ]

    body = "".join(paragraphs)
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f"<w:body>{body}"
        "<w:sectPr>"
        '<w:pgSz w:w="12240" w:h="15840"/>'
        '<w:pgMar w:top="560" w:right="620" w:bottom="560" w:left="620" w:header="300" w:footer="300" w:gutter="0"/>'
        "</w:sectPr></w:body></w:document>"
    )


def document_cuota_grupal_xml(context):
    pago_rows = [
        [
            row["cuenta"],
            row["operacion"],
            row["nro_cuota"],
            row["cliente"],
            row["monto_pago"],
        ]
        for row in context["filas"]
    ]
    abono_rows = [
        [
            row["cuenta"],
            row["operacion"],
            row["nro_cuota"],
            row["cliente"],
            row["monto_condonacion"],
        ]
        for row in context["filas"]
    ]
    col_widths = [1250, 1350, 900, 3450, 1200]

    paragraphs = [
        title_xml("Compromiso de pago Producto Grupal"),
        paragraph_xml(
            "Conste por el presente documento una Transacción Extrajudicial y Cancelación de Deuda, que celebran "
            "de una parte la Empresa de cobranza BIZNESCOB, con RUC 20602593640, con domicilio en Enrique Encinas "
            "284 la victoria y representado por el sr(a) LUIS PORTUGUEZ BERROCAL identificado con DNI 10416012, "
            "por encargo de COMPARTAMOS BANCO S.A.,  en adelante COMPARTAMOS, con domicilio en Av. Paseo de la "
            "Republica N° 5895 – Interior 1301, distrito de Miraflores, provincia y departamento de Lima, inscrita "
            "en la Partida Nro. 13777030 del Registro de Personas Jurídicas de la Zona Registral Nro. IX - Sede Lima "
            f"y de otra parte en representación del grupo {context['grupo']}  el Sr/Sra. {context['fiador_nombre']}  "
            f"identificado con DNI N° {context['fiador_dni']}, con domicilio {context['fiador_direccion']}, "
            f"distrito de {context['fiador_distrito']}  y provincia {context['fiador_provincia']}, en adelante "
            "se denominará EL/LA/DEUDOR/A, en los términos y condiciones siguientes:",
            after=60,
            size=17,
        ),
        clause_exact_xml(
            "Primera: ",
            f"EL/LA/DEUDOR/A, reconoce adeudar a COMPARTAMOS, el(los) crédito(s) N° {context['credito_grupal']}, "
            f"cuyo importe asciende a la suma total de S/{context['deuda_total']}, según liquidación a la fecha.",
            after=45,
        ),
        paragraph_xml(
            f"Asimismo, detallamos que el importe de las cuotas vencidas a pagar asciende a S/.{context['total_cuota']}.",
            after=45,
            size=17,
        ),
        clause_exact_xml(
            "Segunda: ",
            "De conformidad con lo señalado en la cláusula primera EL/LA/DEUDOR/A se obliga a pagar las cuotas "
            "mencionadas en la cláusula primera, a favor de COMPARTAMOS de la siguiente manera:",
            after=45,
        ),
        simple_table_xml(["Cuenta", "Operación", "N° Cuota", "Nombre de cliente", "Monto"], pago_rows, col_widths, font_size=15),
        paragraph_xml(f"MONTO TOTAL A PAGAR     {context['total_pago']}", bold=True, align="right", before=35, after=25, size=17),
        paragraph_xml(f"Fecha de pago / cancelación: {context['fecha_corta']}", before=0, after=40, size=17),
        paragraph_xml(
            "El descuento generado por el compromiso está sujeto al pago acordado en el párrafo que antecede.",
            after=50,
            size=17,
        ),
        clause_exact_xml(
            "TERCERA. - ",
            "Sin perjuicio de lo señalado, COMPARTAMOS se reserva el derecho de iniciar, interponer o continuar "
            "con las acciones administrativas, legales o judiciales, para lograr el recupero total de la deuda, "
            "en caso de que EL/LA/DEUDOR/A incumpla las obligaciones que por el presente documento asume. "
            "El pago acordado en el presente no significa cancelación total de la deuda.",
            after=45,
        ),
        clause_exact_xml(
            "CUARTA. - ",
            "El incumplimiento o retraso en el pago del monto señalado en la cláusula segunda, a criterio de "
            "COMPARTAMOS, quedarán sin efecto los beneficios (descuentos u otros) otorgados a EL/LA/DEUDOR/A, "
            "recalculando los intereses y moras que se hayan generado posteriormente.",
            after=45,
        ),
        clause_exact_xml(
            "QUINTA. - ",
            "EL/LA/DEUDOR/A ratifica su voluntad expresada en el presente instrumento, dejando constancia que "
            "no ha mediado vicio capaz de invalidarlo.",
            after=45,
        ),
        right_xml(f"Lima, {context['fecha_larga']}", after=50, size=17),
        signature_table_xml(context["fiador_dni"], before=90, after=30, doc_id=1),
        horizontal_rule_xml(before=20, after=60),
        title_xml("NOTA DE ABONO"),
        paragraph_xml(
            "Por el presente documento COMPARTAMOS, concede condonación sobre la deuda de EL/LA/DEUDOR/A, según "
            "las condiciones ofrecidas en la en el presente documento.",
            after=45,
            size=17,
        ),
        paragraph_xml(
            f"Sr(a):  {context['fiador_nombre']}  con DNI Nº  {context['fiador_dni']}",
            align="left",
            before=0,
            after=40,
            size=17,
        ),
        simple_table_xml(["Cuenta", "Operación", "N° Cuota", "Nombre de cliente", "Monto"], abono_rows, col_widths, font_size=15),
        paragraph_xml(f"POR LA SUMA DE: S/ {context['total_condonacion']}", bold=True, align="left", before=35, after=35, size=17),
        paragraph_xml(
            "EL/LA/DEUDOR/A, acepta el descuento indicado, reduciendo la deuda vigente que se detalla en la presente "
            "transacción, la misma que mantiene su validez, si EL/LA/DEUDOR/A cumple todas las condiciones descritas "
            "en el documento. El descuento está sujeto al cumplimiento del pago de",
            after=30,
            size=17,
        ),
        paragraph_xml(
            f"S/ {context['total_pago']} en las fechas y formas acordadas en la cláusula segunda.",
            after=45,
            size=17,
        ),
        signature_table_xml(context["fiador_dni"], before=90, after=20, doc_id=2),
    ]

    body = "".join(paragraphs)
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f"<w:body>{body}"
        "<w:sectPr>"
        '<w:pgSz w:w="12240" w:h="15840"/>'
        '<w:pgMar w:top="560" w:right="620" w:bottom="560" w:left="620" w:header="300" w:footer="300" w:gutter="0"/>'
        "</w:sectPr></w:body></w:document>"
    )


def document_mibanco_xml(context):
    headers = ["Producto", "N° préstamo", "Moneda", "Deuda", "Deuda capital", "Días mora", "Cancelación", "Fecha de pago"]
    rows = [
        [row["producto"], row["operacion"], row["moneda"], row["deuda"], row["capital"], row["dias_mora"], row["pago"], context["fecha_corta"]]
        for row in context["operaciones"]
    ]
    paragraphs = [
        image_xml(rel_id="rIdLogoMibanco", doc_id=9, cx=1450000, cy=760000, align="right") if LOGO_MIBANCO_PATH.exists() else "",
        paragraph_xml(f"Señor(a)/(ita): {context['cliente']}                                      DNI: {context['dni']}", align="left", after=35, size=18),
        paragraph_xml(f"Dirección: {context['direccion']}", align="left", after=100, size=18),
        mibanco_title_bar_xml(),
        paragraph_xml(
            f"En MIBANCO estamos comprometidos con nuestros clientes. Este documento busca generar un convenio entre MIBANCO, representado por nuestro proveedor BIZNESCOB y el cliente {context['cliente']}, con DNI: {context['dni']} con el fin de que pueda realizar la cancelación de su deuda bajo las siguientes condiciones.",
            after=55, size=18,
        ),
    ]
    if context["es_cuotas"]:
        cuotas_headers, cuotas_rows = tabla_cuotas_mibanco(context)
        paragraphs.extend([
            paragraph_xml(f"EL CLIENTE contrató con MIBANCO el siguiente préstamo, siendo que a la fecha mantiene un saldo deudor a favor de MIBANCO, monto que RECONOCE EN SU TOTALIDAD. Lima, {context['fecha_larga']}.", after=40, size=18),
            paragraph_xml("El CLIENTE reconoce deber y adeudar, dando estricto cumplimiento al siguiente convenio de pago. Se establecen las siguientes condiciones:", after=40, size=18),
            mibanco_schedule_table_xml(cuotas_headers, cuotas_rows),
            paragraph_xml("El descuento es sobre el capital.", after=38, size=18),
            paragraph_xml("Los pagos se realizarán los siguientes días y por los siguientes montos respectivamente, a través de nuestra red de agencias a nivel nacional.", after=40, size=18),
        ])
    else:
        paragraphs.extend([
            simple_table_xml(headers, rows, [1250, 1100, 850, 1050, 1050, 900, 1100, 1150], font_size=14),
            paragraph_xml("El descuento es sobre el capital.", after=38, size=18),
            paragraph_xml(f"La operación detallada corresponde a la CANCELACIÓN TOTAL CON DESCUENTO de los préstamos indicados. Pago único: S/ {context['monto_total']} el {context['fecha_corta']}.", bold=True, align="center", after=45, size=19),
        ])
    paragraphs.extend([
        paragraph_xml("Este documento carece de valor si no se realiza el pago respectivo en la fecha pactada.", after=38, size=18),
        paragraph_xml("Las cuotas no incluyen I.T.F.", after=50, size=18),
        paragraph_xml(f"Nuestro cliente, {context['cliente']} y MIBANCO, dejan constancia de la conformidad y pleno conocimiento del contenido, reafirmando todas y cada una de las condiciones presentes en este Acuerdo de Cancelación de Deuda.", after=80, size=18),
        mibanco_signature_table_xml(context, before=240, after=20),
    ])
    body = "".join(paragraphs)
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f"<w:body>{body}<w:sectPr><w:pgSz w:w=\"12240\" w:h=\"15840\"/><w:pgMar w:top=\"620\" w:right=\"620\" w:bottom=\"620\" w:left=\"620\" w:header=\"360\" w:footer=\"360\" w:gutter=\"0\"/></w:sectPr></w:body></w:document>"
    )


def tabla_cuotas_mibanco(context):
    headers = ["N° de préstamo", "Deuda total", "Campaña", "Cuota inicial", "Saldo", "N° cuotas", "Monto cuota", "Fecha de pago"]
    pagos = context.get("pagos") or []
    inicial = pagos[0] if pagos else {"monto": "0.00", "fecha": context["fecha_corta"]}
    cuotas = pagos[1:] or pagos
    try:
        saldo = max(Decimal(str(context["monto_total"]).replace(",", "")) - Decimal(str(inicial["monto"]).replace(",", "")), Decimal("0"))
    except (InvalidOperation, ValueError):
        saldo = Decimal("0")
    rows = []
    for index, pago in enumerate(cuotas, start=1):
        if index == 1:
            row = context["operaciones"][0]
            rows.append([row["operacion"], row["deuda"], row["campania"], inicial["monto"], format_money(saldo), str(index), pago["monto"], pago["fecha"]])
        else:
            rows.append(["", "", "", "", "", str(index), pago["monto"], pago["fecha"]])
    rows.append(["TOTAL", context["deuda_total"], context["campania_total"], "", "", "", context["monto_total"], ""])
    return headers, rows


def nombre_mes_sip(value):
    try:
        parsed = datetime.strptime(str(value), "%Y-%m-%d").date()
    except (TypeError, ValueError):
        parsed = datetime.now(ZoneInfo("America/Lima")).date()
    meses = ("ENERO", "FEBRERO", "MARZO", "ABRIL", "MAYO", "JUNIO", "JULIO", "AGOSTO", "SEPTIEMBRE", "OCTUBRE", "NOVIEMBRE", "DICIEMBRE")
    return meses[parsed.month - 1], str(parsed.year), str(parsed.day).zfill(2)


def tabla_cronograma_sip(context):
    rows = []
    for index, pago in enumerate(context["pagos"]):
        mes, anio, dia = nombre_mes_sip(pago["fecha"])
        rows.append([
            "" if index == 0 else str(index),
            "CUOTA INICIAL" if index == 0 else "CUOTA MENSUAL",
            mes,
            anio,
            dia,
            pago["monto"],
            "",
            "",
        ])
    return rows


def document_sip_xml(context):
    resumen_izquierda = [
        [context["fecha_solicitud"], f"S/ {context['deuda_total']}"],
        ["Tipo de facilidad: Convenio Pago", f"Monto Cuota: S/ {context['cuota_regular']}"],
        [f"Monto Convenio: {context['monto_convenio']} SOLES", f"Nro. Cuotas: {context['cantidad_cuotas']}"],
    ]
    detalle = [
        ["Monto convenio", context["monto_convenio"]],
        ["Cuota Inicial", context["cuota_inicial"]],
        ["Numero de Cuotas", str(context["cantidad_cuotas"])],
        ["Monto de cuota", context["cuota_regular"]],
    ]
    cronograma = tabla_cronograma_sip(context)
    paragraphs = [
        title_xml("Pagos por mes  Convenio Tarjeta Sip"),
        paragraph_xml("DATOS DEL CLIENTE", bold=True, align="left", after=28, size=18),
        paragraph_xml(f"Tipo Documento: {context['tipo_documento']}                                      Nro. Documento: {context['dni']}", after=22, size=17),
        paragraph_xml(f"Nombres y Apellidos: {context['cliente']}", after=22, size=17),
        paragraph_xml(f"Producto: TARJETA SIP(OH)                                      Nro. Tarjeta: {context['tarjeta']}", after=50, size=17),
        simple_table_xml(["Fecha Solicitud", "Deuda total"], resumen_izquierda, [4700, 4700], font_size=15),
        paragraph_xml(f"Cuota Inicial: {context['cuota_inicial']} SOLES", before=55, after=45, size=18),
        simple_table_xml(["Concepto", "Monto"], detalle, [4400, 2200], font_size=16),
        paragraph_xml("El saldo del convenio se pagará de acuerdo al siguiente cronograma", before=50, after=30, size=17),
        simple_table_xml(["NUM CUOTA", "CUOTA", "MES", "AÑO", "DIA", "MONTO", "PAGO CUMPLIDO", "MONTO PAGADO"], cronograma, [850, 1600, 1250, 850, 650, 900, 1600, 1600], font_size=14),
        paragraph_xml("1. Al mes de incumplimiento este convenio queda anulado.", before=55, after=18, size=16),
        paragraph_xml("2. Se puede cancelar en:", after=10, size=16),
        paragraph_xml("Plaza Vea (hasta el día de vencimiento de cuota)", after=10, size=16),
        paragraph_xml("Promart, Oechsle, Makro (de preferencia hasta dos días antes del vencimiento de cuota)", after=10, size=16),
        paragraph_xml("Pago link con cualquiera tarjeta de débito (de preferencia un día hábil antes del vencimiento)", after=18, size=16),
        paragraph_xml("3. En caso de pago adelanto de cuotas, este cubrirá sus últimas cuotas.", after=18, size=16),
        paragraph_xml("4. En caso de incumplimiento o simple atraso en el pago de cualquiera de las cuotas establecidas, FINANCIERA OH queda facultada a continuar el ejercicio de las acciones de cobro, cobrándose penalidades.", after=18, size=16),
        paragraph_xml("5. La aplicación de la condonación ofrecida se realizará una vez cancelado el convenio antes mencionado; una vez pagada la última cuota puede solicitar a su sectorista su carta de no adeudo en un plazo de 5 días hábiles.", after=20, size=16),
    ]
    body = "".join(paragraphs)
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{body}<w:sectPr><w:pgSz w:w=\"12240\" w:h=\"15840\"/><w:pgMar w:top=\"620\" w:right=\"720\" w:bottom=\"620\" w:left=\"720\" w:header=\"360\" w:footer=\"360\" w:gutter=\"0\"/></w:sectPr></w:body></w:document>"
    )


def document_sip_constancia_xml(context):
    """Constancia SIP con la misma información mostrada en su preview PDF."""
    paragraphs = [
        image_xml(rel_id="rIdLogoSip", doc_id=41, cx=1250000, cy=760000, align="left"),
        right_xml(f"Lima, {context['fecha_carta']}", after=210, size=20),
        title_xml("CONSTANCIA DE PAGO"),
        paragraph_xml("Estimado(a):", align="left", after=18, size=20),
        paragraph_xml(context["cliente"], align="left", after=12, size=20),
        paragraph_xml(f"{context['tipo_documento']} {context['dni']}", align="left", after=12, size=20),
        paragraph_xml(f"TC {context['operacion']}", align="left", after=150, size=20),
        paragraph_xml(
            f"Le expedimos la presente constancia que acredita el abono realizado por usted el día {context['fecha_pago']}, "
            f"correspondiente a la facilidad de pago denominada \"Limpia Tu Deuda\" por la suma de S/ {context['monto_pagado']}, "
            "en el marco de la campaña vigente.",
            align="both",
            after=130,
            size=20,
        ),
        paragraph_runs_xml([
            {"text": "Este documento ", "bold": False},
            {"text": "confirma la recepción del pago indicado", "bold": True},
            {"text": ", el cual será validado en nuestro sistema. Una vez completada la verificación, se procederá con la condonación de la deuda total conforme a las condiciones pactadas.", "bold": False},
        ], align="both", after=220, size=20),
        paragraph_xml("Cordialmente,", align="left", after=165, size=20),
        paragraph_xml("Financiera Sip\nÁrea de Cobranzas", align="left", after=0, size=20),
    ]
    body = "".join(paragraphs)
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f"<w:body>{body}<w:sectPr><w:pgSz w:w=\"12240\" w:h=\"15840\"/>"
        '<w:pgMar w:top="620" w:right="1150" w:bottom="850" w:left="1150" w:header="360" w:footer="360" w:gutter="0"/>'
        "</w:sectPr></w:body></w:document>"
    )


def styles_xml():
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        '<w:style w:type="paragraph" w:default="1" w:styleId="Normal">'
        '<w:name w:val="Normal"/>'
        f'<w:rPr><w:rFonts w:ascii="{FONT_FAMILY}" w:hAnsi="{FONT_FAMILY}" w:cs="{FONT_FAMILY}"/><w:sz w:val="19"/><w:szCs w:val="19"/></w:rPr>'
        "</w:style></w:styles>"
    )


def generar_docx_limpio(output_path, context, document_kind="transaccion_cancelacion"):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    es_mibanco = document_kind in ("mibanco_contado", "mibanco_cuotas")
    es_sip = document_kind in ("sip_convenio", "sip_constancia")
    if document_kind == "cancelacion_grupal":
        document_body = document_grupal_xml(context)
    elif document_kind == "compromiso_cuota_grupal":
        document_body = document_cuota_grupal_xml(context)
    elif document_kind == "compromiso_cuota_individual":
        document_body = document_cuota_individual_xml(context)
    elif document_kind in ("mibanco_contado", "mibanco_cuotas"):
        document_body = document_mibanco_xml(context)
    elif document_kind == "sip_convenio":
        document_body = document_sip_xml(context)
    elif document_kind == "sip_constancia":
        document_body = document_sip_constancia_xml(context)
    else:
        document_body = document_xml(context)
    document_relationships = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
        '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/settings" Target="settings.xml"/>'
        + ('' if es_mibanco or es_sip else '<Relationship Id="rIdFirmaLuis" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/firma_luis_portuguez.png"/>')
        + ('<Relationship Id="rIdLogoMibanco" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/logo_mibanco.png"/>' if es_mibanco else '')
        + ('<Relationship Id="rIdLogoSip" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/logo_sip.png"/>' if document_kind == "sip_constancia" else '')
        + '</Relationships>'
    )
    parts = {
        "[Content_Types].xml": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Default Extension="png" ContentType="image/png"/>'
            '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
            '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
            '<Override PartName="/word/settings.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.settings+xml"/>'
            "</Types>"
        ),
        "_rels/.rels": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
            "</Relationships>"
        ),
        "word/_rels/document.xml.rels": document_relationships,
        "word/document.xml": document_body,
        "word/styles.xml": styles_xml(),
        "word/settings.xml": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<w:settings xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            '<w:zoom w:percent="100"/>'
            "</w:settings>"
        ),
    }

    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zout:
        for name, content in parts.items():
            zout.writestr(name, content.encode("utf-8"))
        if not es_mibanco and not es_sip and FIRMA_LUIS_PATH.exists():
            zout.write(FIRMA_LUIS_PATH, "word/media/firma_luis_portuguez.png")
        if es_mibanco and LOGO_MIBANCO_PATH.exists():
            zout.write(LOGO_MIBANCO_PATH, "word/media/logo_mibanco.png")
        if document_kind == "sip_constancia" and LOGO_SIP_PATH.exists():
            zout.write(LOGO_SIP_PATH, "word/media/logo_sip.png")


def generar_pdf_limpio(output_path, context):
    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_RIGHT
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import inch
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.platypus import HRFlowable, Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except ImportError as exc:
        raise ValueError("Para descargar en PDF instala la dependencia reportlab y reinicia el servidor.") from exc

    calibri = Path("C:/Windows/Fonts/calibri.ttf")
    calibrib = Path("C:/Windows/Fonts/calibrib.ttf")
    font_name = "Calibri"
    bold_font = "Calibri-Bold"

    if calibri.exists():
        pdfmetrics.registerFont(TTFont(font_name, str(calibri)))
    else:
        font_name = "Helvetica"

    if calibrib.exists():
        pdfmetrics.registerFont(TTFont(bold_font, str(calibrib)))
    else:
        bold_font = "Helvetica-Bold"

    styles = getSampleStyleSheet()
    body = ParagraphStyle(
        "body",
        parent=styles["Normal"],
        fontName=font_name,
        fontSize=8.05,
        leading=9.65,
        alignment=TA_JUSTIFY,
        spaceAfter=5.4,
    )
    title = ParagraphStyle(
        "title",
        parent=body,
        fontName=bold_font,
        fontSize=10.4,
        leading=11.8,
        alignment=TA_CENTER,
        spaceAfter=10,
    )
    center = ParagraphStyle("center", parent=body, alignment=TA_CENTER)
    right = ParagraphStyle("right", parent=body, alignment=TA_RIGHT)
    bold = ParagraphStyle("bold", parent=body, fontName=bold_font)
    bold_center = ParagraphStyle("bold_center", parent=center, fontName=bold_font)

    def p(text, style=body):
        return Paragraph(xml_text(text), style)

    def clause(label, text):
        return Paragraph(f"<b><u>{xml_text(label)}</u></b>{xml_text(text)}", body)

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=letter,
        leftMargin=0.52 * inch,
        rightMargin=0.52 * inch,
        topMargin=0.46 * inch,
        bottomMargin=0.46 * inch,
    )

    payment_table = Table(
        [
            [p("Monto", bold_center), p("Fecha de Pago/ Cancelación", bold_center)],
            [p(f"S/ {context['cancelacion']}", center), p(context["fecha_corta"], center)],
        ],
        colWidths=[1.75 * inch, 1.75 * inch],
    )
    payment_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.6, colors.black),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))

    def signature_table_pdf():
        if FIRMA_LUIS_PATH.exists():
            gerente_firma = [Image(str(FIRMA_LUIS_PATH), width=1.35 * inch, height=0.62 * inch)]
        else:
            gerente_firma = [p("____________________________", center)]
        table = Table(
            [
                [
                    [p("____________________________", center), p("EL/LA DEUDOR/A", bold_center), p(f"D.N.I. {context['dni']}", bold_center)],
                    gerente_firma,
                ],
            ],
            colWidths=[3.0 * inch, 3.0 * inch],
        )
        table.setStyle(TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
            ("FONTSIZE", (0, 0), (-1, -1), 7.4),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ]))
        return table

    story = [
        p("Transacción extrajudicial y Cancelación de Deuda", title),
        p(
            "Conste por el presente documento una Transacción Extrajudicial y Cancelación de Deuda, que celebran "
            "de una parte la Empresa de cobranza BIZNESCOB, con RUC 20602593640, con domicilio en Enrique Encinas "
            "284 la victoria y representado por el sr(a) LUIS PORTUGUEZ BERROCAL identificado con DNI 10416012, "
            "por encargo de COMPARTAMOS BANCO S.A.,  en adelante COMPARTAMOS, con domicilio en Av. Paseo de la "
            "Republica N° 5895 – Interior 1301, distrito de Mira flores, provincia y departamento de Lima, inscrita "
            "en la Partida Nro. 13777030 del Registro de Personas Jurídicas de la Zona Registral Nro. IX - Sede Lima "
            f"y de otra parte el/la Sr (a) {context['cliente']} identificado con DNI N°.{context['dni']}, con domicilio "
            f"en {context['direccion']}, distrito de {context['distrito']}, a quien en adelante se le denominara  "
            "EL/LA/DEUDOR/A, en los términos y condiciones siguientes:"
        ),
        clause("PRIMERA.- ", f"EL DEUDOR reconoce adeudar a COMPARTAMOS BANCO el crédito {context['operacion']}, cuyo  importe asciende  a la suma total de S/  {context['deuda_total']},  según liquidación a la fecha."),
        clause("SEGUNDA- ", "De conformidad con lo señalado en la cláusula anterior EL DEUDOR se obliga a cancelar a   COMPARTAMOS BANCO la deuda antes descrita de la siguiente manera:"),
        payment_table,
        Spacer(1, 6),
        p("La cancelación de la suma antes detallada está sujeta al pago acordado en el párrafo que antecede."),
        clause("TERCERA .- ", "Sin perjuicio de lo señalado, COMPARTAMOS se reserva el derecho de iniciar, interponer o continuar con las acciones administrativas, legales o judiciales en caso de que el EL/LA/DEUDOR/A incumpla las obligaciones que por el presente documento asume; COMPARTAMOS quedará expedito para su cobro de conformidad con lo estipulado por inciso 8 del artículo 688 del Código Proceso Civil."),
        clause("CUARTA .- ", "Las garantías y/o fianzas solidarias constituidas en respaldo de la obligación antes señalada subsisten en tanto no se cancele totalmente la misma por el monto acordado, por cuanto la suscripción de presente convenio no constituye una novación de la obligación"),
        clause("QUINTA .- ", "El incumplimiento o retraso en el pago del monto señalado en la cláusula segunda, a criterio de COMPARTAMOS, quedarán sin efecto los beneficios (descuentos u otros) otorgados a EL/LA/DEUDOR/A, recalculando los intereses y mora que se hayan generado posteriormente."),
        clause("SÉXTA :  ", "EL/LA/DEUDOR/A ratifica su voluntad expresada en el presente instrumento, dejando constancia que no    ha mediado vicio capaz  de invalidarlo."),
        p(context["fecha_larga"], right),
        Spacer(1, 10),
        signature_table_pdf(),
        Spacer(1, 9),
        HRFlowable(width="100%", thickness=0.6, color=colors.grey, spaceBefore=0, spaceAfter=7),
        p("NOTA DE ABONO", title),
        p("Por el presente documento COMPARTAMOS, concede condonación sobre la deuda de EL/LA/DEUDOR/A, según las condiciones ofrecidas en la en el presente documento."),
        p(f"Sr(a):{context['cliente']} con DNI Nº {context['dni']} por la suma de S/ {context['condonacion']}", bold_center),
        p("EL/LA/DEUDOR/A, acepta el descuento indicado, reduciendo la deuda vigente que se detalla en la presente transacción, la misma que mantiene su validez, si EL/LA/DEUDOR/A cumple todas las condiciones descritas en el documento."),
        p(f"El descuento está sujeto al cumplimiento del pago de: S/ {context['cancelacion']} en las fechas y formas acordadas en la cláusula segunda."),
        Spacer(1, 10),
        signature_table_pdf(),
    ]
    doc.build(story)


def generar_pdf_sip(output_path, context):
    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER, TA_LEFT
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import inch
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.platypus import Image, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except ImportError as exc:
        raise ValueError("Para descargar en PDF instala la dependencia reportlab y reinicia el servidor.") from exc

    font = "Calibri" if Path("C:/Windows/Fonts/calibri.ttf").exists() else "Helvetica"
    bold = "Calibri-Bold" if Path("C:/Windows/Fonts/calibrib.ttf").exists() else "Helvetica-Bold"
    if font == "Calibri": pdfmetrics.registerFont(TTFont(font, "C:/Windows/Fonts/calibri.ttf"))
    if bold == "Calibri-Bold": pdfmetrics.registerFont(TTFont(bold, "C:/Windows/Fonts/calibrib.ttf"))
    styles = getSampleStyleSheet()
    body = ParagraphStyle("sip_body", parent=styles["Normal"], fontName=font, fontSize=8.4, leading=10.8)
    indented = ParagraphStyle("sip_indented", parent=body, leftIndent=.52 * inch, rightIndent=.52 * inch)
    center = ParagraphStyle("sip_center", parent=body, alignment=TA_CENTER)
    title = ParagraphStyle("sip_title", parent=body, fontName=bold, fontSize=13, leading=16, alignment=TA_CENTER, spaceAfter=11)
    label = ParagraphStyle("sip_label", parent=body, fontName=bold)
    indented_label = ParagraphStyle("sip_indented_label", parent=indented, fontName=bold)
    section_label = ParagraphStyle("sip_section", parent=body, fontName=bold, textColor=colors.white, alignment=TA_LEFT, fontSize=8.6, leading=10)
    def p(value, style=body): return Paragraph(xml_text(value), style)
    def bullet_item(value): return p(f"•   {value}", indented)
    def datos_en_linea(values, widths):
        row = Table([[p(value, label if index % 2 == 0 else body) for index, value in enumerate(values)]], colWidths=widths)
        row.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ]))
        return row
    def section(title_text):
        band = Table([[p(title_text, section_label)]], colWidths=[6.2 * inch])
        band.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#00B4FF")),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 7),
            ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ]))
        return band
    def header_sip():
        logo = Image(str(LOGO_SIP_PATH), width=.92 * inch, height=.57 * inch)
        header = Table([["", logo]], colWidths=[5.28 * inch, .92 * inch], rowHeights=[.57 * inch])
        header.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#00B4FF")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))
        return header
    def grid(data, widths, header=True):
        table = Table(data, colWidths=widths, repeatRows=1 if header else 0)
        style = [("GRID", (0, 0), (-1, -1), .55, colors.black), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5), ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5)]
        if header:
            style += [("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#00B4FF")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("FONTNAME", (0, 0), (-1, 0), bold), ("ALIGN", (0, 0), (-1, -1), "CENTER")]
        table.setStyle(TableStyle(style))
        return table

    resumen = [
        [p(f"Fecha Solicitud:            {context['fecha_solicitud']}", label), p("Deuda total:", label), p(f"S/{context['deuda_total']}", label)],
        [p("Tipo de facilidad:         Convenio Pago", label), p("Monto Cuota:", label), p(f"S/{context['cuota_regular']}", label)],
        [p(f"Monto Convenio:          {context['monto_convenio']} SOLES", label), p("Nro. Cuotas:", label), p(str(context['cantidad_cuotas']), center)],
    ]
    detalle = [[p("Monto convenio", label), p(context["monto_convenio"], center)], [p("Cuota Inicial", label), p(context["cuota_inicial"], center)], [p("Numero de Cuotas", label), p(str(context["cantidad_cuotas"]), center)], [p("Monto de cuota", label), p(context["cuota_regular"], center)]]
    cronograma = [[p(header, center) for header in ["NUM CUOTA", "CUOTA", "MES", "AÑO", "DIA", "MONTO", "PAGO CUMPLIDO", "MONTO PAGADO"]]]
    cronograma += [[p(value, center) for value in row] for row in tabla_cronograma_sip(context)]
    doc = SimpleDocTemplate(str(output_path), pagesize=letter, leftMargin=.55*inch, rightMargin=.55*inch, topMargin=.48*inch, bottomMargin=.48*inch)
    story = []
    if LOGO_SIP_PATH.exists():
        story.extend([header_sip(), Spacer(1, 10)])
    story.extend([
        p("Pagos por mes  Convenio Tarjeta Sip", title),
        section("DATOS DEL CLIENTE"),
        Spacer(1, 4),
        datos_en_linea(["Tipo de documento:", context["tipo_documento"], "Nro. documento:", context["dni"]], [1.18 * inch, 1.08 * inch, 1.42 * inch, 2.52 * inch]),
        p(f"Nombres y Apellidos: {context['cliente']}", indented),
        Spacer(1, 5), section("DATOS DE LA CUENTA Y TARJETA"), Spacer(1, 4),
        datos_en_linea(["Producto:", "TARJETA SIP(OH)", "Nro. tarjeta:", context["tarjeta"]], [.72 * inch, 1.86 * inch, 1.22 * inch, 2.4 * inch]),
        Spacer(1, 5), section("DATOS DE LA SOLICITUD"), Spacer(1, 5),
        grid(resumen, [3.4*inch, 1.65*inch, 1.15*inch], header=False),
        Spacer(1, 8), p(f"Cuota Inicial: {context['cuota_inicial']} SOLES", indented_label),
        Spacer(1, 5), section("CRONOGRAMA DE PAGOS"), Spacer(1, 5),
        grid([[p("Concepto", center), p("Monto", center)]] + detalle, [3.1*inch, 2.0*inch]),
        Spacer(1, 8), p("El saldo del convenio se pagará de acuerdo al siguiente cronograma", indented),
        Spacer(1, 5), grid(cronograma, [.58*inch, 1.12*inch, .86*inch, .55*inch, .42*inch, .72*inch, 1.12*inch, 1.02*inch]),
    ])
    story.append(KeepTogether([
        Spacer(1, 10), section("CONDICIONES DE PAGO"), Spacer(1, 5),
        p("1. Al mes de incumplimiento este convenio queda anulado.", indented),
        p("2. Se puede cancelar en:", indented),
        bullet_item("Plaza Vea (hasta el día de vencimiento de cuota)"),
        bullet_item("Promart, Oechsle, Makro (de preferencia hasta dos días antes del vencimiento de cuota)"),
        bullet_item("Pago link con cualquiera tarjeta de débito (de preferencia un día hábil antes del vencimiento)"),
        p("3. En caso de pago adelanto de cuotas, este cubrirá sus últimas cuotas.", indented),
        p("4. En caso de incumplimiento o simple atraso en el pago de cualquiera de las cuotas establecidas, FINANCIERA OH queda facultada a continuar el ejercicio de las acciones de cobro, cobrando penalidades.", indented),
        p("5. La aplicación de la condonación ofrecida se realizará una vez cancelado el convenio antes mencionado, una vez pagada la última cuota puede solicitar a su sectorista su carta de no adeudo en un plazo de 5 días hábiles.", indented),
    ]))
    doc.build(story)


def generar_pdf_sip_constancia(output_path, context):
    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_RIGHT
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import inch
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except ImportError as exc:
        raise ValueError("Para descargar en PDF instala la dependencia reportlab y reinicia el servidor.") from exc

    font = "Calibri" if Path("C:/Windows/Fonts/calibri.ttf").exists() else "Helvetica"
    bold = "Calibri-Bold" if Path("C:/Windows/Fonts/calibrib.ttf").exists() else "Helvetica-Bold"
    if font == "Calibri": pdfmetrics.registerFont(TTFont(font, "C:/Windows/Fonts/calibri.ttf"))
    if bold == "Calibri-Bold": pdfmetrics.registerFont(TTFont(bold, "C:/Windows/Fonts/calibrib.ttf"))
    styles = getSampleStyleSheet()
    body = ParagraphStyle("sip_constancia_body", parent=styles["Normal"], fontName=font, fontSize=10.5, leading=14, alignment=TA_JUSTIFY)
    title = ParagraphStyle("sip_constancia_title", parent=body, fontName=bold, fontSize=15, leading=18, alignment=TA_CENTER, spaceAfter=32)
    recipient = ParagraphStyle("sip_constancia_recipient", parent=body, leftIndent=.48 * inch, rightIndent=.48 * inch)
    right = ParagraphStyle("sip_constancia_right", parent=body, alignment=TA_RIGHT)
    def p(value, style=body): return Paragraph(xml_text(value), style)
    doc = SimpleDocTemplate(str(output_path), pagesize=letter, leftMargin=.7*inch, rightMargin=.7*inch, topMargin=.38*inch, bottomMargin=.7*inch)
    story = []
    if LOGO_SIP_PATH.exists():
        logo = Image(str(LOGO_SIP_PATH), width=.98*inch, height=.6*inch)
        header = Table([[logo, ""]], colWidths=[.98*inch, 5.82*inch], rowHeights=[.6*inch])
        header.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#00B4FF")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))
        story.extend([header, Spacer(1, 68)])
    story.extend([
        p(f"Lima, {context['fecha_carta']}", right),
        Spacer(1, 35),
        p("CONSTANCIA DE PAGO", title),
        p("Estimado(a):", recipient),
        p(context["cliente"], recipient),
        p(f"{context['tipo_documento']} {context['dni']}", recipient),
        p(f"TC {context['operacion']}", recipient),
        Spacer(1, 38),
        p(f"Le expedimos la presente constancia que acredita el abono realizado por usted el día {context['fecha_pago']}, correspondiente a la facilidad de pago denominada \"Limpia Tu Deuda\" por la suma de S/ {context['monto_pagado']}, en el marco de la campaña vigente.", recipient),
        Spacer(1, 22),
        Paragraph("Este documento <b>confirma la recepción del pago indicado</b>, el cual será validado en nuestro sistema. Una vez completada la verificación, se procederá con la condonación de la deuda total conforme a las condiciones pactadas.", recipient),
        Spacer(1, 50),
        p("Cordialmente,", recipient),
        Spacer(1, 35),
        Paragraph("Financiera Sip<br/>Área de Cobranzas", recipient),
    ])
    doc.build(story)


def generar_pdf_mibanco(output_path, context):
    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import inch
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except ImportError as exc:
        raise ValueError("Para descargar en PDF instala la dependencia reportlab y reinicia el servidor.") from exc

    font = "Calibri" if Path("C:/Windows/Fonts/calibri.ttf").exists() else "Helvetica"
    bold = "Calibri-Bold" if Path("C:/Windows/Fonts/calibrib.ttf").exists() else "Helvetica-Bold"
    if font == "Calibri": pdfmetrics.registerFont(TTFont(font, "C:/Windows/Fonts/calibri.ttf"))
    if bold == "Calibri-Bold": pdfmetrics.registerFont(TTFont(bold, "C:/Windows/Fonts/calibrib.ttf"))
    styles = getSampleStyleSheet()
    body = ParagraphStyle("mibanco_body", parent=styles["Normal"], fontName=font, fontSize=8.2, leading=10.2, alignment=TA_JUSTIFY)
    indented = ParagraphStyle("mibanco_indented", parent=body, leftIndent=.52 * inch, rightIndent=.52 * inch)
    title = ParagraphStyle("mibanco_title", parent=body, fontName=bold, fontSize=13, leading=15, alignment=TA_CENTER, textColor=colors.white)
    center = ParagraphStyle("mibanco_center", parent=body, alignment=TA_CENTER)
    italic = ParagraphStyle("mibanco_italic", parent=body, fontName=font, fontSize=8.1, leading=15, alignment=TA_JUSTIFY, italic=True)
    indented_italic = ParagraphStyle("mibanco_indented_italic", parent=italic, leftIndent=.52 * inch, rightIndent=.52 * inch)
    signature = ParagraphStyle("mibanco_signature", parent=center, fontName=bold, fontSize=7.5, leading=9)
    def p(value, style=body): return Paragraph(xml_text(value), style)
    doc = SimpleDocTemplate(str(output_path), pagesize=letter, leftMargin=.38*inch, rightMargin=.38*inch, topMargin=.4*inch, bottomMargin=.4*inch)
    data = [[p(h, center) for h in ["PRODUCTO", "N°\nPRÉSTAMO", "MONEDA", "DEUDA", "DEUDA\nCAPITAL", "DÍAS\nMORA", "CANCELACIÓN", "FECHA DE\nPAGO"]]]
    data += [[p(row["producto"], center), p(row["operacion"], center), p(row["moneda"], center), p(row["deuda"], center), p(row["capital"], center), p(row["dias_mora"], center), p(row["pago"], center), p(context["fecha_corta"], center)] for row in context["operaciones"]]
    tabla = Table(data, colWidths=[.88*inch,.77*inch,.67*inch,.72*inch,.76*inch,.55*inch,.89*inch,.86*inch], repeatRows=1)
    tabla.setStyle(TableStyle([("GRID",(0,0),(-1,-1),.75,colors.black),("BACKGROUND",(0,0),(-1,0),colors.HexColor("#008d48")),("TEXTCOLOR",(0,0),(-1,0),colors.white),("BACKGROUND",(6,1),(6,-1),colors.HexColor("#fff200")),("FONTNAME",(0,0),(-1,0),bold),("FONTNAME",(6,1),(6,-1),bold),("VALIGN",(0,0),(-1,-1),"MIDDLE"),("TOPPADDING",(0,0),(-1,-1),7),("BOTTOMPADDING",(0,0),(-1,-1),7)]))
    story = []
    if LOGO_MIBANCO_PATH.exists():
        logo = Image(str(LOGO_MIBANCO_PATH), width=1.15*inch, height=.6*inch)
        logo.hAlign = "RIGHT"
        story += [logo, Spacer(1, 8)]
    datos = Table([[p("Señor(a)/(ita):", body), p(context["cliente"], signature), p("DNI:", body), p(context["dni"], signature)], [p("Dirección:", body), p(context["direccion"], body), p("", body), p("", body)]], colWidths=[.8*inch,3.55*inch,.38*inch,1.7*inch])
    datos.setStyle(TableStyle([("VALIGN",(0,0),(-1,-1),"MIDDLE"),("BOTTOMPADDING",(0,0),(-1,-1),7),("TOPPADDING",(0,0),(-1,-1),0)]))
    barra = Table([[p("ACUERDO DE CANCELACION DE DEUDA", title)]], colWidths=[6.43*inch])
    barra.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),colors.HexColor("#008d48")),("BOX",(0,0),(-1,-1),1.2,colors.black),("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4)]))
    story += [datos, Spacer(1, 11), barra, Spacer(1, 8), p(f"En MIBANCO estamos comprometidos con nuestros clientes. Este documento busca generar un convenio entre MIBANCO, representado por nuestro proveedor BIZNESCOB y el cliente {context['cliente']}, con DNI: {context['dni']} con el fin de que pueda realizar la cancelación de su deuda bajo las siguientes condiciones:", indented_italic)]
    if context["es_cuotas"]:
        cuotas_headers, cuotas_rows = tabla_cuotas_mibanco(context)
        pagos = [[p(header, center) for header in cuotas_headers]] + [[p(cell, center) for cell in row] for row in cuotas_rows]
        cronograma = Table(pagos, colWidths=[.86*inch,.84*inch,.7*inch,.78*inch,.7*inch,.58*inch,.72*inch,.93*inch], repeatRows=1)
        cronograma.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), .6, colors.black),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#008d48")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("BACKGROUND", (2, 1), (2, -2), colors.HexColor("#fff200")),
            ("FONTNAME", (0, 0), (-1, 0), bold),
            ("FONTNAME", (0, -1), (-1, -1), bold),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story += [Spacer(1,7), p(f"EL CLIENTE contrató con MIBANCO el siguiente préstamo, siendo que a la fecha mantiene un saldo deudor a favor de MIBANCO, monto que RECONOCE EN SU TOTALIDAD. Lima, {context['fecha_larga']}.", indented), p("El CLIENTE reconoce deber y adeudar, dando estricto cumplimiento al siguiente convenio de pago. Se establecen las siguientes condiciones:", indented), Spacer(1,5), cronograma, Spacer(1,5), p("El descuento es sobre el capital.", indented), p("Los pagos se realizarán los siguientes días y por los siguientes montos respectivamente, a través de nuestra red de agencias a nivel nacional:", indented)]
    else:
        story += [Spacer(1, 7), tabla, Spacer(1, 7), p("El descuento es sobre el capital.", indented), p(f"La operación detallada corresponde a la CANCELACIÓN TOTAL CON DESCUENTO de los préstamos indicados. Pago único: S/ {context['monto_total']} el {context['fecha_corta']}.", center)]
    firmas = Table(
        [[p("______________________________", center), p("______________________________", center)], [
            Paragraph("ROSARIO RODRIGUEZ MOSCOSO<br/>REPRESENTANTE<br/>MIBANCO", signature),
            Paragraph(f"{xml_text(context['cliente'])}<br/>DNI: {xml_text(context['dni'])}<br/>CLIENTE", signature),
        ]],
        colWidths=[3.2*inch,3.2*inch],
    )
    firmas.setStyle(TableStyle([("ALIGN",(0,0),(-1,-1),"CENTER"),("VALIGN",(0,0),(-1,-1),"BOTTOM"),("TOPPADDING",(0,0),(-1,-1),0),("BOTTOMPADDING",(0,0),(-1,-1),0)]))
    story += [Spacer(1, 7), p("Este documento carece de valor si no se realiza el pago respectivo en la fecha pactada.", signature), p("Las cuotas no incluyen I.T.F.", indented_italic), p(f"Nuestro cliente, {context['cliente']} y MIBANCO, dejamos constancia de la conformidad y pleno conocimiento del contenido, reafirmando todas y cada una de las condiciones presentes en este Acuerdo de Cancelación de Deuda. En señal de lo mencionado, se suscriben al documento.", indented), Spacer(1, 10), p("Área de Recuperaciones", signature), Spacer(1, 48), firmas]
    doc.build(story)


def generar_pdf_cuota_individual_limpio(output_path, context):
    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_RIGHT
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import inch
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.platypus import HRFlowable, Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except ImportError as exc:
        raise ValueError("Para descargar en PDF instala la dependencia reportlab y reinicia el servidor.") from exc

    calibri = Path("C:/Windows/Fonts/calibri.ttf")
    calibrib = Path("C:/Windows/Fonts/calibrib.ttf")
    font_name = "Calibri"
    bold_font = "Calibri-Bold"

    if calibri.exists():
        pdfmetrics.registerFont(TTFont(font_name, str(calibri)))
    else:
        font_name = "Helvetica"

    if calibrib.exists():
        pdfmetrics.registerFont(TTFont(bold_font, str(calibrib)))
    else:
        bold_font = "Helvetica-Bold"

    styles = getSampleStyleSheet()
    body = ParagraphStyle("body_cuota_individual", parent=styles["Normal"], fontName=font_name, fontSize=8.05, leading=9.65, alignment=TA_JUSTIFY, spaceAfter=5.4)
    title = ParagraphStyle("title_cuota_individual", parent=body, fontName=bold_font, fontSize=10.4, leading=11.8, alignment=TA_CENTER, spaceAfter=10)
    center = ParagraphStyle("center_cuota_individual", parent=body, alignment=TA_CENTER)
    right = ParagraphStyle("right_cuota_individual", parent=body, alignment=TA_RIGHT)
    bold_center = ParagraphStyle("bold_center_cuota_individual", parent=center, fontName=bold_font)

    def p(text, style=body):
        return Paragraph(xml_text(text), style)

    def clause(label, text):
        return Paragraph(f"<b><u>{xml_text(label)}</u></b>{xml_text(text)}", body)

    doc = SimpleDocTemplate(str(output_path), pagesize=letter, leftMargin=0.52 * inch, rightMargin=0.52 * inch, topMargin=0.46 * inch, bottomMargin=0.46 * inch)
    payment_table = Table(
        [[p("Monto", bold_center), p("Fecha de Pago/ Cancelacion", bold_center)], [p(f"S/ {context['cancelacion']}", center), p(context["fecha_corta"], center)]],
        colWidths=[1.75 * inch, 1.75 * inch],
    )
    payment_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.6, colors.black),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))

    def signature_table_pdf():
        if FIRMA_LUIS_PATH.exists():
            gerente_firma = [Image(str(FIRMA_LUIS_PATH), width=1.35 * inch, height=0.62 * inch)]
        else:
            gerente_firma = [p("____________________________", center)]
        table = Table(
            [[[p("____________________________", center), p("EL/LA DEUDOR/A", bold_center), p(f"D.N.I. {context['dni']}", bold_center)], gerente_firma]],
            colWidths=[3.0 * inch, 3.0 * inch],
        )
        table.setStyle(TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ]))
        return table

    story = [
        p("COMPROMISO DE PAGO", title),
        p(
            "Conste por el presente documento una Transaccion Extrajudicial y Cancelacion de Deuda, que celebran "
            "de una parte la Empresa de cobranza BIZNESCOB, con RUC 20602593640, con domicilio en Enrique Encinas "
            "284 la victoria y representado por el sr(a) LUIS PORTUGUEZ BERROCAL identificado con DNI 10416012, "
            "por encargo de COMPARTAMOS BANCO S.A., en adelante COMPARTAMOS, con domicilio en Av. Paseo de la "
            "Republica Nro. 5895 - Interior 1301, distrito de Miraflores, provincia y departamento de Lima, inscrita "
            "en la Partida Nro. 13777030 del Registro de Personas Juridicas de la Zona Registral Nro. IX - Sede Lima "
            f"y de otra parte el/la Sr(a) {context['cliente']} identificado con DNI Nro. {context['dni']}, con domicilio "
            f"en {context['direccion']}, distrito de {context['distrito']}, a quien en adelante se le denominara EL/LA/DEUDOR/A, "
            "en los terminos y condiciones siguientes:"
        ),
        clause("PRIMERA.- ", f"EL DEUDOR reconoce adeudar a COMPARTAMOS BANCO el(los) credito(s) {context['operacion']}, cuyo importe asciende a la suma total de S/ {context['deuda_total']}. Segun liquidacion a la fecha."),
        p(f"Asimismo, detallamos que el importe de las cuotas vencidas Nro. {context['nro_cuota']}, asciende a S/. {context['cuota']}."),
        clause("SEGUNDA- ", "De conformidad con lo senalado en la clausula primera EL/LA/DEUDOR/A se obliga a pagar las cuotas mencionadas en la clausula primera, a favor de COMPARTAMOS de la siguiente manera:"),
        payment_table,
        Spacer(1, 6),
        p("El descuento generado por el compromiso esta sujeto al pago acordado en el parrafo que antecede."),
        clause("TERCERA .- ", "Sin perjuicio de lo senalado, COMPARTAMOS se reserva el derecho de iniciar, interponer o continuar con las acciones administrativas, legales o judiciales, para lograr el recupero total de la deuda, en caso de que EL/LA/DEUDOR/A incumpla las obligaciones que por el presente documento asume. El pago acordado en el presente no significa cancelacion total de la deuda."),
        clause("CUARTA .- ", "El incumplimiento o retraso en el pago del monto senalado en la clausula segunda, a criterio de COMPARTAMOS, quedaran sin efecto los beneficios otorgados a EL/LA/DEUDOR/A, recalculando los intereses y moras que se hayan generado posteriormente."),
        clause("QUINTA .- ", "EL/LA/DEUDOR/A ratifica su voluntad expresada en el presente instrumento, dejando constancia que no ha mediado vicio capaz de invalidarlo."),
        p(context["fecha_larga"], right),
        Spacer(1, 10),
        signature_table_pdf(),
        Spacer(1, 9),
        HRFlowable(width="100%", thickness=0.6, color=colors.grey, spaceBefore=0, spaceAfter=7),
        p("NOTA DE ABONO", title),
        p("Por el presente documento COMPARTAMOS, concede condonacion sobre la deuda de EL/LA/DEUDOR/A, segun las condiciones ofrecidas en la en el presente documento."),
        p(f"Sr(a): {context['cliente']} con DNI Nro. {context['dni']} por la suma de S/ {context['condonacion']}", bold_center),
        p(f"EL/LA/DEUDOR/A, acepta el descuento indicado, reduciendo la deuda vigente que se detalla en la presente transaccion, la misma que mantiene su validez, si EL/LA/DEUDOR/A cumple todas las condiciones descritas en el documento. El descuento esta sujeto al cumplimiento del pago de: S/ {context['cancelacion']} en las fechas y formas acordadas en la clausula segunda."),
        Spacer(1, 10),
        signature_table_pdf(),
    ]
    doc.build(story)


def preparar_contexto_grupal(rows, encargado=None, pagos_grupales=None, excepcion=False):
    if not rows:
        raise ValueError("No se encontro informacion del grupo para generar el documento.")

    encargado = encargado or {}
    pagos_grupales = pagos_grupales or []
    modo_encargado = limpiar_texto(encargado.get("modo")).lower() or "participante"
    pago_por_operacion = {}
    operaciones_activas = set()

    for item in pagos_grupales:
        operacion_key = limpiar_texto(item.get("operacion"))
        activo = item.get("activo", True)
        if operacion_key and activo:
            operaciones_activas.add(operacion_key)
        monto = decimal_value(item.get("monto"))
        if not operacion_key:
            continue
        if not activo:
            continue
        if monto is None or monto <= 0:
            raise ValueError(f"Ingresa un monto valido para la operacion {operacion_key}.")
        pago_por_operacion[operacion_key] = monto

    if modo_encargado == "libre":
        encargado_context = {
            "nombre": limpiar_texto(encargado.get("nombre")),
            "dni": limpiar_texto(encargado.get("dni")),
            "direccion": limpiar_texto(encargado.get("direccion")),
            "distrito": limpiar_texto(encargado.get("distrito")),
            "provincia": limpiar_texto(encargado.get("provincia")),
        }
        faltantes = [
            label
            for label, value in {
                "nombre": encargado_context["nombre"],
                "DNI": encargado_context["dni"],
                "direccion": encargado_context["direccion"],
                "distrito": encargado_context["distrito"],
                "provincia": encargado_context["provincia"],
            }.items()
            if not value
        ]
        if faltantes:
            raise ValueError(f"Completa los datos del encargado libre: {', '.join(faltantes)}.")
    else:
        operacion_encargado = limpiar_texto(encargado.get("operacion"))
        dni_encargado = limpiar_texto(encargado.get("dni"))
        registro_encargado = None
        for row in rows:
            if operacion_encargado and limpiar_texto(row.get("Operacion")) == operacion_encargado:
                registro_encargado = row
                break
            if dni_encargado and limpiar_texto(row.get("NumDocumento")) == dni_encargado:
                registro_encargado = row
                break
        if registro_encargado is None:
            registro_encargado = rows[0]

        encargado_context = {
            "nombre": limpiar_texto(registro_encargado.get("NomCliente")),
            "dni": limpiar_texto(registro_encargado.get("NumDocumento")),
            "direccion": limpiar_texto(registro_encargado.get("DireccionPrincipal")),
            "distrito": limpiar_texto(
                encargado.get("distrito")
                or registro_encargado.get("DistritoPrincipal")
                or registro_encargado.get("Distrito_Principal")
                or registro_encargado.get("Distrito")
            ),
            "provincia": limpiar_texto(encargado.get("provincia")),
        }

    filas = []
    total_pago = Decimal("0")
    total_deuda = Decimal("0")
    total_condonacion = Decimal("0")

    rows_activas = [row for row in rows if limpiar_texto(row.get("Operacion")) in operaciones_activas] if pagos_grupales else rows
    if not rows_activas:
        raise ValueError("Selecciona al menos un integrante activo para generar el documento grupal.")

    for row in rows_activas:
        operacion_row = limpiar_texto(row.get("Operacion"))
        if operacion_row not in pago_por_operacion:
            raise ValueError(f"Ingresa el monto manual para la operacion {operacion_row}.")

        deuda = decimal_value(row.get("DeudaTotal"), Decimal("0"))
        pago = pago_por_operacion[operacion_row]
        minimo = decimal_value(row.get("MtoCancelacionCliente"), Decimal("0"))
        if not excepcion and pago <= minimo:
            raise ValueError(
                f"El monto de la operacion {operacion_row} debe ser mayor a S/ {format_money(minimo)} "
                f"(Mto CancelacionCliente de la consulta SQL)."
            )
        condonacion = max(deuda - pago, Decimal("0"))

        total_deuda += deuda
        total_pago += pago
        total_condonacion += condonacion

        filas.append(
            {
                "cuenta": limpiar_texto(row.get("CtaCliente") or row.get("CodigoGrupo")),
                "operacion": operacion_row,
                "cliente": limpiar_texto(row.get("NomCliente")),
                "monto_pago": format_money(pago),
                "monto_condonacion": format_money(condonacion),
            }
        )

    hoy = datetime.now(ZoneInfo("America/Lima")).date()
    primero = rows_activas[0]
    return {
        "grupo": limpiar_texto(primero.get("NomGrupo")),
        "credito_grupal": limpiar_texto(primero.get("CodCreGrupal") or primero.get("CodigoGrupo")),
        "encargado_nombre": encargado_context["nombre"],
        "encargado_dni": encargado_context["dni"],
        "encargado_direccion": encargado_context["direccion"],
        "encargado_distrito": encargado_context["distrito"],
        "encargado_provincia": encargado_context["provincia"],
        "deuda_total": format_money(total_deuda),
        "total_pago": format_money(total_pago),
        "total_condonacion": format_money(total_condonacion),
        "fecha_corta": hoy.strftime("%d/%m/%Y"),
        "fecha_larga": fecha_larga_modelo_hoy(),
        "filas": filas,
    }


def preparar_contexto_cuota_grupal(rows, fiador=None, pagos_grupales=None, excepcion=False):
    if not rows:
        raise ValueError("No se encontro informacion del grupo para generar el documento.")

    fiador = fiador or {}
    pagos_grupales = pagos_grupales or []
    modo_fiador = limpiar_texto(fiador.get("modo")).lower() or "participante"
    pago_por_operacion = {}
    operaciones_activas = set()

    for item in pagos_grupales:
        operacion_key = limpiar_texto(item.get("operacion"))
        activo = item.get("activo", True)
        if operacion_key and activo:
            operaciones_activas.add(operacion_key)
        monto = decimal_value(item.get("monto"))
        if not operacion_key:
            continue
        if not activo:
            continue
        if monto is None or monto <= 0:
            raise ValueError(f"Ingresa un monto valido para la operacion {operacion_key}.")
        pago_por_operacion[operacion_key] = monto

    if modo_fiador == "libre":
        fiador_context = {
            "nombre": limpiar_texto(fiador.get("nombre")),
            "dni": limpiar_texto(fiador.get("dni")),
            "direccion": limpiar_texto(fiador.get("direccion")),
            "distrito": limpiar_texto(fiador.get("distrito")),
            "provincia": limpiar_texto(fiador.get("provincia")),
        }
        faltantes = [
            label
            for label, value in {
                "nombre": fiador_context["nombre"],
                "DNI": fiador_context["dni"],
                "direccion": fiador_context["direccion"],
                "distrito": fiador_context["distrito"],
                "provincia": fiador_context["provincia"],
            }.items()
            if not value
        ]
        if faltantes:
            raise ValueError(f"Completa los datos del fiador externo: {', '.join(faltantes)}.")
    else:
        operacion_fiador = limpiar_texto(fiador.get("operacion"))
        dni_fiador = limpiar_texto(fiador.get("dni"))
        registro_fiador = None
        for row in rows:
            if operacion_fiador and limpiar_texto(row.get("Operacion")) == operacion_fiador:
                registro_fiador = row
                break
            if dni_fiador and limpiar_texto(row.get("NumDocumento")) == dni_fiador:
                registro_fiador = row
                break
        if registro_fiador is None:
            registro_fiador = rows[0]

        fiador_context = {
            "nombre": limpiar_texto(registro_fiador.get("NomCliente")),
            "dni": limpiar_texto(registro_fiador.get("NumDocumento")),
            "direccion": limpiar_texto(registro_fiador.get("DireccionPrincipal")),
            "distrito": limpiar_texto(
                fiador.get("distrito")
                or registro_fiador.get("DistritoPrincipal")
                or registro_fiador.get("Distrito_Principal")
                or registro_fiador.get("Distrito")
            ),
            "provincia": limpiar_texto(fiador.get("provincia")),
        }

    filas = []
    total_pago = Decimal("0")
    total_deuda = Decimal("0")
    total_cuota = Decimal("0")
    total_condonacion = Decimal("0")

    rows_activas = [row for row in rows if limpiar_texto(row.get("Operacion")) in operaciones_activas] if pagos_grupales else rows
    if not rows_activas:
        raise ValueError("Selecciona al menos un integrante activo para generar el documento grupal.")

    for row in rows_activas:
        operacion_row = limpiar_texto(row.get("Operacion"))
        if operacion_row not in pago_por_operacion:
            raise ValueError(f"Ingresa el monto manual para la operacion {operacion_row}.")

        deuda = decimal_value(row.get("DeudaTotal"), Decimal("0"))
        cuota = calcular_cuota_grupal(row)
        pago = pago_por_operacion[operacion_row]
        if not excepcion and pago <= cuota:
            raise ValueError(
                f"El monto de la operacion {operacion_row} debe ser mayor a S/ {format_money(cuota)} "
                "(cuota calculada con CT1 + CT11 + CT12 + CT13 + CT14 + CT15)."
            )
        condonacion = max(deuda - pago, Decimal("0"))

        total_deuda += deuda
        total_cuota += cuota
        total_pago += pago
        total_condonacion += condonacion

        filas.append(
            {
                "cuenta": limpiar_texto(row.get("CtaCliente") or row.get("CodigoGrupo")),
                "operacion": operacion_row,
                "nro_cuota": obtener_nro_cuota_atrasada(row),
                "cliente": limpiar_texto(row.get("NomCliente")),
                "cuota": format_money(cuota),
                "monto_pago": format_money(pago),
                "monto_condonacion": format_money(condonacion),
            }
        )

    hoy = datetime.now(ZoneInfo("America/Lima")).date()
    primero = rows_activas[0]
    return {
        "grupo": limpiar_texto(primero.get("NomGrupo")),
        "credito_grupal": limpiar_texto(primero.get("CodCreGrupal") or primero.get("CodigoGrupo")),
        "fiador_nombre": fiador_context["nombre"],
        "fiador_dni": fiador_context["dni"],
        "fiador_direccion": fiador_context["direccion"],
        "fiador_distrito": fiador_context["distrito"],
        "fiador_provincia": fiador_context["provincia"],
        "deuda_total": format_money(total_deuda),
        "total_cuota": format_money(total_cuota),
        "total_pago": format_money(total_pago),
        "total_condonacion": format_money(total_condonacion),
        "fecha_corta": hoy.strftime("%d/%m/%Y"),
        "fecha_larga": fecha_larga_modelo_hoy(),
        "filas": filas,
    }


def preparar_contexto_cuota_individual(registro, cancelacion=None, fecha_pago=None, excepcion=False, cuotas_individual=1):
    cantidad_cuotas = max(1, min(5, int(cuotas_individual or 1)))
    es_grupal_vigente = int(registro.get("CarteraId") or 0) == 133
    if es_grupal_vigente:
        cuota = calcular_cuotas_grupal_acumuladas(registro, cantidad_cuotas)
        minimo = decimal_value(registro.get("MtoCuotaCampania"), Decimal("0"))
    else:
        cantidad_cuotas = min(cantidad_cuotas, 4)
        cuota = decimal_value(registro.get(f"CT{cantidad_cuotas}"), calcular_cuota_grupal(registro)) or Decimal("0")
        minimo = decimal_value(registro.get(f"MtoCuotaCampania{cantidad_cuotas}"), registro.get("MtoCuotaCampania")) or cuota
    monto_pago, _ = validar_cancelacion(cancelacion, minimo, excepcion=excepcion)
    deuda_total = cuota
    monto_condonacion = max(cuota - monto_pago, Decimal("0"))
    hoy = datetime.now(ZoneInfo("America/Lima")).date()

    return {
        "cliente": limpiar_texto(registro.get("NomCliente")),
        "dni": limpiar_texto(registro.get("NumDocumento")),
        "direccion": limpiar_texto(registro.get("DireccionPrincipal")),
        "distrito": limpiar_texto(registro.get("DistritoPrincipal") or registro.get("Distrito_Principal") or registro.get("Distrito")),
        "operacion": limpiar_texto(registro.get("Operacion")),
        "grupo": limpiar_texto(registro.get("NomGrupo")),
        "codigo_grupo": limpiar_texto(registro.get("CodigoGrupo")),
        "credito_grupal": limpiar_texto(registro.get("CodCreGrupal") or registro.get("CodigoGrupo")),
        "cuenta": limpiar_texto(registro.get("CtaCliente") or registro.get("CodigoGrupo")),
        "nro_cuota": obtener_nros_cuotas_individual(registro, cantidad_cuotas),
        "cantidad_cuotas": cantidad_cuotas,
        "deuda_total": format_money(deuda_total),
        "cuota": format_money(cuota),
        "cancelacion": format_money(monto_pago),
        "condonacion": format_money(monto_condonacion),
        "fecha_corta": format_fecha_pago(fecha_pago) or hoy.strftime("%d/%m/%Y"),
        "fecha_larga": fecha_larga_hoy(),
    }


def generar_pdf_grupal_limpio(output_path, context):
    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_RIGHT
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import inch
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.platypus import HRFlowable, Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except ImportError as exc:
        raise ValueError("Para descargar en PDF instala la dependencia reportlab y reinicia el servidor.") from exc

    calibri = Path("C:/Windows/Fonts/calibri.ttf")
    calibrib = Path("C:/Windows/Fonts/calibrib.ttf")
    font_name = "Calibri"
    bold_font = "Calibri-Bold"

    if calibri.exists():
        pdfmetrics.registerFont(TTFont(font_name, str(calibri)))
    else:
        font_name = "Helvetica"

    if calibrib.exists():
        pdfmetrics.registerFont(TTFont(bold_font, str(calibrib)))
    else:
        bold_font = "Helvetica-Bold"

    styles = getSampleStyleSheet()
    body = ParagraphStyle(
        "body_grupal",
        parent=styles["Normal"],
        fontName=font_name,
        fontSize=7.55,
        leading=8.95,
        alignment=TA_JUSTIFY,
        spaceAfter=4.7,
    )
    title = ParagraphStyle(
        "title_grupal",
        parent=body,
        fontName=bold_font,
        fontSize=10.1,
        leading=11.4,
        alignment=TA_CENTER,
        spaceAfter=9,
    )
    center = ParagraphStyle("center_grupal", parent=body, alignment=TA_CENTER)
    right = ParagraphStyle("right_grupal", parent=body, alignment=TA_RIGHT)
    bold_center = ParagraphStyle("bold_center_grupal", parent=center, fontName=bold_font)

    def p(text, style=body):
        return Paragraph(xml_text(text), style)

    def clause(label, text):
        return Paragraph(f"<b><u>{xml_text(label)}</u></b>{xml_text(text)}", body)

    def filas_tabla(campo_monto):
        return [
            [p("Cuenta", bold_center), p("Operación", bold_center), p("Nombre de cliente", bold_center), p("Monto", bold_center)]
        ] + [
            [p(row["cuenta"], center), p(row["operacion"], center), p(row["cliente"], body), p(row[campo_monto], center)]
            for row in context["filas"]
        ]

    def tabla_grupal(campo_monto):
        table = Table(filas_tabla(campo_monto), colWidths=[0.95 * inch, 1.05 * inch, 3.2 * inch, 1.0 * inch])
        table.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.45, colors.black),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 3),
            ("RIGHTPADDING", (0, 0), (-1, -1), 3),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        return table

    def signature_table_pdf():
        if FIRMA_LUIS_PATH.exists():
            gerente_firma = [Image(str(FIRMA_LUIS_PATH), width=1.35 * inch, height=0.62 * inch)]
        else:
            gerente_firma = [p("____________________________", center)]
        table = Table(
            [
                [
                    [p("____________________________", center), p("EL/LA DEUDOR/A", bold_center), p(f"D.N.I. {context['encargado_dni']}", bold_center)],
                    gerente_firma,
                ],
            ],
            colWidths=[3.0 * inch, 3.0 * inch],
        )
        table.setStyle(TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ]))
        return table

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=letter,
        leftMargin=0.45 * inch,
        rightMargin=0.45 * inch,
        topMargin=0.42 * inch,
        bottomMargin=0.42 * inch,
    )

    story = [
        p("Convenio de Pago y Cancelación de Deuda", title),
        p(
            "Conste por el presente documento una Transacción Extrajudicial y Cancelación de Deuda, que celebran "
            "de una parte la Empresa de cobranza BIZNESCOB, con RUC 20602593640, con domicilio en Enrique Encinas "
            "284 la victoria y representado por el sr(a) LUIS PORTUGUEZ BERROCAL identificado con DNI 10416012, "
            "por encargo de COMPARTAMOS BANCO S.A.,  en adelante COMPARTAMOS, con domicilio en Av. Paseo de la "
            "Republica N° 5895 - Interior 1301, distrito de Miraflores, provincia y departamento de Lima, inscrita "
            "en la Partida Nro. 13777030 del Registro de Personas Jurídicas de la Zona Registral Nro. IX - Sede Lima "
            f"Y de otra parte en representación del grupo {context['grupo']}  el Sr/Sra. {context['encargado_nombre']}  "
            f"identificado con DNI N° {context['encargado_dni']}, con domicilio {context['encargado_direccion']}, "
            f"distrito de {context['encargado_distrito']}  y provincia {context['encargado_provincia']}, en adelante "
            "se denominará EL/LA/DEUDOR/A, en los términos y condiciones siguientes:"
        ),
        clause("Primera: ", f"EL/LA/DEUDOR/A, reconoce adeudar a COMPARTAMOS BANCO, el crédito N° {context['credito_grupal']}, cuyo importe asciende a la suma total de S/{context['deuda_total']}, según liquidación a la fecha."),
        clause("Segunda: ", "De conformidad con lo señalado en la cláusula anterior EL DEUDOR se obliga a cancelar a COMPARTAMOS BANCO la deuda antes descrita de la siguiente manera:"),
        tabla_grupal("monto_pago"),
        p(f"MONTO TOTAL A PAGAR     {context['total_pago']}", right),
        p(f"Fecha de pago / cancelación: {context['fecha_corta']}"),
        p("La cancelación de la suma antes detallada está sujeta al pago acordado en el párrafo que antecede."),
        clause("Tercera: ", "Sin perjuicio de lo señalado, COMPARTAMOS se reserva el derecho de iniciar, interponer o continuar con las acciones administrativas, legales o judiciales en caso de que EL/LA/DEUDOR/A incumpla las obligaciones que por el presente documento asume; COMPARTAMOS quedara expedito para su cobro de conformidad con lo estipulado por inciso 8 del artículo 688 del Código Procesal Civil"),
        clause("Cuarta: ", "Las garantías y/o fianzas solidarias constituidas en respaldo de la obligación antes señalada subsisten en tanto no se cancele totalmente la misma por el monto acordado, por cuanto la suscripción de presente convenio no constituye una novación de la obligación."),
        clause("Quinta: ", "El incumplimiento o retraso en el pago del monto señalado en la cláusula segunda, a criterio de COMPARTAMOS, quedarán sin efecto los beneficios (descuentos u otros) otorgados a EL/LA/DEUDOR/A, recalculando los intereses y mora que se hayan generado posteriormente."),
        clause("Sexta: ", "EL/LA/DEUDOR/A ratifica su voluntad expresada en el presente instrumento, dejando constancia que no ha mediado vicio capaz de invalidarlo."),
        p(f"Lima, {context['fecha_larga']}", right),
        Spacer(1, 10),
        signature_table_pdf(),
        Spacer(1, 9),
        HRFlowable(width="100%", thickness=0.6, color=colors.grey, spaceBefore=0, spaceAfter=7),
        p("NOTA DE ABONO", title),
        p("Por el presente documento COMPARTAMOS, concede condonación sobre la deuda de EL/LA/DEUDOR/A, según las condiciones ofrecidas en la en el presente documento."),
        p(f"Sr(a):  {context['encargado_nombre']}  con DNI Nº  {context['encargado_dni']}"),
        tabla_grupal("monto_condonacion"),
        p(f"POR LA SUMA DE: S/ {context['total_condonacion']}"),
        p("EL/LA/DEUDOR/A, acepta el descuento indicado, reduciendo la deuda vigente que se detalla en la presente transacción, la misma que mantiene su validez, si EL/LA/DEUDOR/A cumple todas las condiciones descritas en el documento. El descuento está sujeto al cumplimiento del pago de"),
        p(f"S/ {context['total_pago']} en las fechas y formas acordadas en la cláusula segunda."),
        Spacer(1, 10),
        signature_table_pdf(),
    ]
    doc.build(story)


def generar_pdf_cuota_grupal_limpio(output_path, context):
    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_RIGHT
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import inch
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.platypus import HRFlowable, Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except ImportError as exc:
        raise ValueError("Para descargar en PDF instala la dependencia reportlab y reinicia el servidor.") from exc

    calibri = Path("C:/Windows/Fonts/calibri.ttf")
    calibrib = Path("C:/Windows/Fonts/calibrib.ttf")
    font_name = "Calibri"
    bold_font = "Calibri-Bold"

    if calibri.exists():
        pdfmetrics.registerFont(TTFont(font_name, str(calibri)))
    else:
        font_name = "Helvetica"

    if calibrib.exists():
        pdfmetrics.registerFont(TTFont(bold_font, str(calibrib)))
    else:
        bold_font = "Helvetica-Bold"

    styles = getSampleStyleSheet()
    body = ParagraphStyle(
        "body_cuota_grupal",
        parent=styles["Normal"],
        fontName=font_name,
        fontSize=7.35,
        leading=8.75,
        alignment=TA_JUSTIFY,
        spaceAfter=4.4,
    )
    title = ParagraphStyle(
        "title_cuota_grupal",
        parent=body,
        fontName=bold_font,
        fontSize=10.0,
        leading=11.2,
        alignment=TA_CENTER,
        spaceAfter=9,
    )
    center = ParagraphStyle("center_cuota_grupal", parent=body, alignment=TA_CENTER)
    right = ParagraphStyle("right_cuota_grupal", parent=body, alignment=TA_RIGHT)
    bold_center = ParagraphStyle("bold_center_cuota_grupal", parent=center, fontName=bold_font)

    def p(text, style=body):
        return Paragraph(xml_text(text), style)

    def clause(label, text):
        return Paragraph(f"<b><u>{xml_text(label)}</u></b>{xml_text(text)}", body)

    def filas_tabla(campo_monto):
        return [
            [p("Cuenta", bold_center), p("Operación", bold_center), p("N° Cuota", bold_center), p("Nombre de cliente", bold_center), p("Monto", bold_center)]
        ] + [
            [p(row["cuenta"], center), p(row["operacion"], center), p(row["nro_cuota"], center), p(row["cliente"], body), p(row[campo_monto], center)]
            for row in context["filas"]
        ]

    def tabla_cuota(campo_monto):
        table = Table(filas_tabla(campo_monto), colWidths=[0.82 * inch, 0.98 * inch, 0.62 * inch, 3.05 * inch, 0.86 * inch])
        table.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.45, colors.black),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 3),
            ("RIGHTPADDING", (0, 0), (-1, -1), 3),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        return table

    def signature_table_pdf():
        if FIRMA_LUIS_PATH.exists():
            gerente_firma = [Image(str(FIRMA_LUIS_PATH), width=1.35 * inch, height=0.62 * inch)]
        else:
            gerente_firma = [p("____________________________", center)]
        table = Table(
            [
                [
                    [p("____________________________", center), p("EL/LA DEUDOR/A", bold_center), p(f"D.N.I. {context['fiador_dni']}", bold_center)],
                    gerente_firma,
                ],
            ],
            colWidths=[3.0 * inch, 3.0 * inch],
        )
        table.setStyle(TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ]))
        return table

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=letter,
        leftMargin=0.45 * inch,
        rightMargin=0.45 * inch,
        topMargin=0.42 * inch,
        bottomMargin=0.42 * inch,
    )

    story = [
        p("Compromiso de pago Producto Grupal", title),
        p(
            "Conste por el presente documento una Transacción Extrajudicial y Cancelación de Deuda, que celebran "
            "de una parte la Empresa de cobranza BIZNESCOB, con RUC 20602593640, con domicilio en Enrique Encinas "
            "284 la victoria y representado por el sr(a) LUIS PORTUGUEZ BERROCAL identificado con DNI 10416012, "
            "por encargo de COMPARTAMOS BANCO S.A.,  en adelante COMPARTAMOS, con domicilio en Av. Paseo de la "
            "Republica N° 5895 - Interior 1301, distrito de Miraflores, provincia y departamento de Lima, inscrita "
            "en la Partida Nro. 13777030 del Registro de Personas Jurídicas de la Zona Registral Nro. IX - Sede Lima "
            f"y de otra parte en representación del grupo {context['grupo']}  el Sr/Sra. {context['fiador_nombre']}  "
            f"identificado con DNI N° {context['fiador_dni']}, con domicilio {context['fiador_direccion']}, "
            f"distrito de {context['fiador_distrito']}  y provincia {context['fiador_provincia']}, en adelante "
            "se denominará EL/LA/DEUDOR/A, en los términos y condiciones siguientes:"
        ),
        clause("Primera: ", f"EL/LA/DEUDOR/A, reconoce adeudar a COMPARTAMOS, el(los) crédito(s) N° {context['credito_grupal']}, cuyo importe asciende a la suma total de S/{context['deuda_total']}, según liquidación a la fecha."),
        p(f"Asimismo, detallamos que el importe de las cuotas vencidas a pagar asciende a S/.{context['total_cuota']}."),
        clause("Segunda: ", "De conformidad con lo señalado en la cláusula primera EL/LA/DEUDOR/A se obliga a pagar las cuotas mencionadas en la cláusula primera, a favor de COMPARTAMOS de la siguiente manera:"),
        tabla_cuota("monto_pago"),
        p(f"MONTO TOTAL A PAGAR     {context['total_pago']}", right),
        p(f"Fecha de pago / cancelación: {context['fecha_corta']}"),
        p("El descuento generado por el compromiso está sujeto al pago acordado en el párrafo que antecede."),
        clause("TERCERA. - ", "Sin perjuicio de lo señalado, COMPARTAMOS se reserva el derecho de iniciar, interponer o continuar con las acciones administrativas, legales o judiciales, para lograr el recupero total de la deuda, en caso de que EL/LA/DEUDOR/A incumpla las obligaciones que por el presente documento asume. El pago acordado en el presente no significa cancelación total de la deuda."),
        clause("CUARTA. - ", "El incumplimiento o retraso en el pago del monto señalado en la cláusula segunda, a criterio de COMPARTAMOS, quedarán sin efecto los beneficios (descuentos u otros) otorgados a EL/LA/DEUDOR/A, recalculando los intereses y moras que se hayan generado posteriormente."),
        clause("QUINTA. - ", "EL/LA/DEUDOR/A ratifica su voluntad expresada en el presente instrumento, dejando constancia que no ha mediado vicio capaz de invalidarlo."),
        p(f"Lima, {context['fecha_larga']}", right),
        Spacer(1, 8),
        signature_table_pdf(),
        Spacer(1, 8),
        HRFlowable(width="100%", thickness=0.6, color=colors.grey, spaceBefore=0, spaceAfter=7),
        p("NOTA DE ABONO", title),
        p("Por el presente documento COMPARTAMOS, concede condonación sobre la deuda de EL/LA/DEUDOR/A, según las condiciones ofrecidas en la en el presente documento."),
        p(f"Sr(a):  {context['fiador_nombre']}  con DNI Nº  {context['fiador_dni']}"),
        tabla_cuota("monto_condonacion"),
        p(f"POR LA SUMA DE: S/ {context['total_condonacion']}"),
        p("EL/LA/DEUDOR/A, acepta el descuento indicado, reduciendo la deuda vigente que se detalla en la presente transacción, la misma que mantiene su validez, si EL/LA/DEUDOR/A cumple todas las condiciones descritas en el documento. El descuento está sujeto al cumplimiento del pago de"),
        p(f"S/ {context['total_pago']} en las fechas y formas acordadas en la cláusula segunda."),
        Spacer(1, 8),
        signature_table_pdf(),
    ]
    doc.build(story)


def generar_documento_grupal(config, dni=None, operacion=None, codigo_grupo=None, cod_cre_grupal=None, formato="docx", excepcion=False, encargado=None, pagos_grupales=None):
    codigo_grupo_limpio = limpiar_texto(codigo_grupo)
    cod_cre_limpio = limpiar_texto(cod_cre_grupal)
    rows = []

    if codigo_grupo_limpio:
        rows = consultar_datos_documento(codigo_grupo=codigo_grupo_limpio, limit=200)

    if not rows and cod_cre_limpio:
        rows = consultar_datos_documento(cod_cre_grupal=cod_cre_limpio, limit=200)

    if not rows:
        rows = consultar_datos_documento(
            dni=dni,
            operacion=None if limpiar_texto(dni) else operacion,
            limit=200,
        )

    context = preparar_contexto_grupal(rows, encargado=encargado, pagos_grupales=pagos_grupales, excepcion=excepcion)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    formato = str(formato or "docx").lower()
    if formato not in ("docx", "pdf"):
        raise ValueError("Formato no soportado. Selecciona Word o PDF.")

    filename = f"{safe_filename(config['nombre'])}_{safe_filename(context['grupo'] or context['encargado_nombre'])}.{formato}"
    output_path = OUTPUT_DIR / filename

    if formato == "pdf":
        generar_pdf_grupal_limpio(output_path, context)
    else:
        generar_docx_limpio(output_path, context, document_kind="cancelacion_grupal")

    return {
        "path": output_path,
        "filename": filename,
        "formato": formato,
        "registro": rows[0],
    }


def generar_documento_cuota_grupal(config, dni=None, operacion=None, codigo_grupo=None, cod_cre_grupal=None, formato="docx", excepcion=False, fiador=None, pagos_grupales=None):
    codigo_grupo_limpio = limpiar_texto(codigo_grupo)
    cod_cre_limpio = limpiar_texto(cod_cre_grupal)
    rows = []

    if codigo_grupo_limpio:
        rows = consultar_datos_documento(codigo_grupo=codigo_grupo_limpio, limit=200)

    if not rows and cod_cre_limpio:
        rows = consultar_datos_documento(cod_cre_grupal=cod_cre_limpio, limit=200)

    if not rows:
        rows = consultar_datos_documento(
            dni=dni,
            operacion=None if limpiar_texto(dni) else operacion,
            limit=200,
        )

    context = preparar_contexto_cuota_grupal(rows, fiador=fiador, pagos_grupales=pagos_grupales, excepcion=excepcion)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    formato = str(formato or "docx").lower()
    if formato not in ("docx", "pdf"):
        raise ValueError("Formato no soportado. Selecciona Word o PDF.")

    filename = f"{safe_filename(config['nombre'])}_{safe_filename(context['grupo'] or context['fiador_nombre'])}.{formato}"
    output_path = OUTPUT_DIR / filename

    if formato == "pdf":
        generar_pdf_cuota_grupal_limpio(output_path, context)
    else:
        generar_docx_limpio(output_path, context, document_kind="compromiso_cuota_grupal")

    return {
        "path": output_path,
        "filename": filename,
        "formato": formato,
        "registro": rows[0],
    }


def preparar_contexto_mibanco(rows, cancelacion, fecha_pago, es_cuotas=False, pagos_mibanco=None, excepcion=False):
    if not rows:
        raise ValueError("Selecciona al menos una operacion de Mibanco.")
    monto_total = decimal_value(cancelacion)
    if monto_total is None or monto_total <= 0:
        raise ValueError("Ingresa el monto total de cancelacion acordado.")
    hoy = datetime.now(ZoneInfo("America/Lima")).date()
    pagos = []
    pagos_operacion = {
        clave_operacion(item.get("operacion")): decimal_value(item.get("monto"), Decimal("0")) or Decimal("0")
        for item in (pagos_mibanco or []) if limpiar_texto(item.get("operacion"))
    }
    if not es_cuotas:
        if not pagos_operacion:
            raise ValueError("Ingresa el monto a pagar para cada operación seleccionada.")
        for row in rows:
            operacion = clave_operacion(row.get("Operacion"))
            pago = pagos_operacion.get(operacion, Decimal("0"))
            campania = decimal_value(row.get("MtoCancelacionCliente"), Decimal("0")) or Decimal("0")
            if pago <= 0:
                raise ValueError(f"Ingresa un monto válido para la operación {operacion}.")
            if not excepcion and pago < campania:
                raise ValueError(f"El pago de la operación {operacion} es menor que su campaña de S/ {format_money(campania)}. Marca Excepción para permitirlo.")
        monto_total = sum(pagos_operacion.get(clave_operacion(row.get("Operacion")), Decimal("0")) for row in rows)
    for item in pagos_mibanco or []:
        monto = decimal_value(item.get("monto"), Decimal("0")) or Decimal("0")
        if monto <= 0:
            raise ValueError("Cada cuota debe tener un monto mayor a cero.")
        pagos.append({"numero": int(item.get("numero") or len(pagos) + 1), "monto": format_money(monto), "fecha": format_fecha_pago(item.get("fecha")) or hoy.strftime("%d/%m/%Y")})
    if es_cuotas and not pagos:
        raise ValueError("Ingresa el cronograma de cuotas para generar el acuerdo.")
    if es_cuotas:
        total_plan = sum((decimal_value(item["monto"], Decimal("0")) or Decimal("0")) for item in pagos)
        if abs(total_plan - monto_total) > Decimal("0.01"):
            raise ValueError("La suma de inicial y cuotas debe coincidir con el monto total de cancelacion.")
    return {
        "cliente": limpiar_texto(rows[0].get("NomCliente")), "dni": limpiar_texto(rows[0].get("NumDocumento")),
        "codigo_cliente": limpiar_texto(rows[0].get("CtaCliente")),
        "direccion": limpiar_texto(rows[0].get("DireccionPrincipal")),
        "fecha_corta": format_fecha_pago(fecha_pago) or hoy.strftime("%d/%m/%Y"), "fecha_larga": fecha_larga_hoy(),
        "monto_total": format_money(monto_total), "es_cuotas": es_cuotas, "pagos": pagos,
        "deuda_total": format_money(sum((decimal_value(row.get("DeudaTotal"), Decimal("0")) or Decimal("0")) for row in rows)),
        "capital_total": format_money(sum((decimal_value(row.get("SdoCapital"), Decimal("0")) or Decimal("0")) for row in rows)),
        "campania_total": format_money(sum((decimal_value(row.get("MtoCancelacionCliente"), Decimal("0")) or Decimal("0")) for row in rows)),
        "operaciones": [{
            "operacion": clave_operacion(row.get("Operacion")), "producto": limpiar_texto(row.get("Producto") or "PRODUCTOS PROPIOS"), "moneda": limpiar_texto(row.get("Moneda") or "S"),
            "deuda": format_money(decimal_value(row.get("DeudaTotal"), Decimal("0")) or Decimal("0")),
            "capital": format_money(decimal_value(row.get("SdoCapital"), Decimal("0")) or Decimal("0")),
            "dias_mora": limpiar_texto(row.get("DiasAtraso")),
            "campania": format_money(decimal_value(row.get("MtoCancelacionCliente"), Decimal("0")) or Decimal("0")),
            "pago": format_money(pagos_operacion.get(clave_operacion(row.get("Operacion")), monto_total if len(rows) == 1 and not es_cuotas else Decimal("0"))),
        } for row in rows],
    }


def generar_documento_mibanco(config, dni=None, operacion=None, cancelacion=None, fecha_pago=None, formato="docx", operaciones_mibanco=None, pagos_mibanco=None, excepcion=False):
    rows = consultar_datos_documento_mibanco(dni=dni, operacion=operacion, limit=100)
    seleccionadas = {clave_operacion(value) for value in (operaciones_mibanco or []) if limpiar_texto(value)}
    if seleccionadas:
        rows = [row for row in rows if clave_operacion(row.get("Operacion")) in seleccionadas]
    es_cuotas = config.get("document_kind") == "mibanco_cuotas"
    context = preparar_contexto_mibanco(rows, cancelacion, fecha_pago, es_cuotas=es_cuotas, pagos_mibanco=pagos_mibanco, excepcion=excepcion)
    formato = str(formato or "docx").lower()
    if formato not in ("docx", "pdf"):
        raise ValueError("Formato no soportado. Selecciona Word o PDF.")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{safe_filename(config['nombre'])}_{safe_filename(context['cliente'])}.{formato}"
    output_path = OUTPUT_DIR / filename
    if formato == "pdf":
        generar_pdf_mibanco(output_path, context)
    else:
        generar_docx_limpio(output_path, context, document_kind=config["document_kind"])
    return {
        "path": output_path,
        "filename": filename,
        "formato": formato,
        "registro": rows[0],
        "auditoria_detalle": {
            "modalidad": "cuotas" if es_cuotas else "contado",
            "monto_total_acordado": context["monto_total"],
            "fecha_pago": context["fecha_corta"],
            "cronograma": context["pagos"] if es_cuotas else [],
            "operaciones": [
                {
                    "operacion": clave_operacion(row.get("operacion")),
                    "campania": row["campania"],
                    "pago": context["monto_total"] if es_cuotas and len(context["operaciones"]) == 1 else (None if es_cuotas else row["pago"]),
                }
                for row in context["operaciones"]
            ],
        },
    }


def preparar_contexto_sip(registro, cancelacion, fecha_pago, pagos_mibanco=None, excepcion=False):
    pagos = []
    for index, item in enumerate(pagos_mibanco or []):
        monto = decimal_value(item.get("monto"), Decimal("0")) or Decimal("0")
        if monto < 0:
            raise ValueError("Los montos de inicial y cuotas SIP no pueden ser negativos.")
        fecha = limpiar_texto(item.get("fecha")) or limpiar_texto(fecha_pago)
        if not fecha:
            fecha = datetime.now(ZoneInfo("America/Lima")).date().isoformat()
        pagos.append({"numero": index, "monto": monto, "fecha": fecha})
    if len(pagos) < 2:
        raise ValueError("Ingresa una cuota inicial y al menos una cuota regular para el convenio SIP.")

    cantidad_cuotas = len(pagos) - 1
    cuota_inicial = pagos[0]["monto"]
    cuotas_regulares = pagos[1:]
    cuota_regular = cuotas_regulares[0]["monto"]
    if any(pago["monto"] <= 0 for pago in cuotas_regulares):
        raise ValueError("Cada cuota regular SIP debe ser mayor a cero.")
    # El cronograma es la fuente de verdad: inicial + cuotas regulares define el convenio.
    monto_convenio = sum((pago["monto"] for pago in pagos), Decimal("0"))

    campania = decimal_value(registro.get("MtoCancelacionCliente"))
    if campania is not None and campania > 0 and not excepcion and monto_convenio < campania:
        raise ValueError(f"El monto del convenio SIP es menor que la campaña de S/ {format_money(campania)}. Marca Excepción para permitirlo.")

    return {
        "cliente": limpiar_texto(registro.get("NomCliente")),
        "dni": limpiar_texto(registro.get("NumDocumento")),
        "tipo_documento": limpiar_texto(registro.get("TipoDocumento")),
        "tarjeta": clave_operacion(registro.get("Operacion")),
        "deuda_total": format_money(decimal_value(registro.get("DeudaTotal"), Decimal("0")) or Decimal("0")),
        "campania": format_money(campania) if campania is not None else "",
        "mejor_ltd": limpiar_texto(registro.get("MejorLTD")),
        "fecha_solicitud": format_fecha_pago(fecha_pago) or datetime.now(ZoneInfo("America/Lima")).date().strftime("%d/%m/%Y"),
        "cuota_inicial": format_money(cuota_inicial),
        "cantidad_cuotas": cantidad_cuotas,
        "cuota_regular": format_money(cuota_regular),
        "monto_convenio": format_money(monto_convenio),
        "pagos": [{"monto": format_money(pago["monto"]), "fecha": pago["fecha"]} for pago in pagos],
    }


def generar_documento_sip(config, dni=None, operacion=None, cancelacion=None, fecha_pago=None, formato="docx", pagos_mibanco=None, excepcion=False):
    rows = consultar_datos_documento_sip(dni=dni, operacion=operacion, limit=2)
    if not rows:
        raise ValueError("No se encontró información SIP para generar el convenio.")
    if len(rows) > 1 and not limpiar_texto(operacion):
        raise ValueError("La búsqueda SIP devolvió más de una operación. Selecciona una operación antes de generar.")
    registro = rows[0]
    context = preparar_contexto_sip(registro, cancelacion, fecha_pago, pagos_mibanco=pagos_mibanco, excepcion=excepcion)
    formato = str(formato or "docx").lower()
    if formato not in ("docx", "pdf"):
        raise ValueError("Formato no soportado. Selecciona Word o PDF.")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{safe_filename(config['nombre'])}_{safe_filename(context['cliente'])}.{formato}"
    output_path = OUTPUT_DIR / filename
    if formato == "pdf":
        generar_pdf_sip(output_path, context)
    else:
        generar_docx_sip_desde_template(output_path, context)
    return {
        "path": output_path,
        "filename": filename,
        "formato": formato,
        "registro": registro,
        "auditoria_detalle": {
            "modalidad": "convenio_pagos_mes",
            "monto_total_acordado": context["monto_convenio"],
            "fecha_pago": context["fecha_solicitud"],
            "cronograma": context["pagos"],
            "operaciones": [{"operacion": context["tarjeta"], "campania": context["campania"], "pago": context["monto_convenio"]}],
        },
    }


def generar_constancia_pago_sip(config, dni=None, operacion=None, cancelacion=None, fecha_pago=None, formato="docx", permitir_monto_cero=False):
    rows = consultar_datos_documento_sip(dni=dni, operacion=operacion, limit=2)
    if not rows:
        raise ValueError("No se encontró información SIP para generar la constancia.")
    if len(rows) > 1 and not limpiar_texto(operacion):
        raise ValueError("La búsqueda SIP devolvió más de una operación. Selecciona una operación antes de generar.")
    monto_pagado = decimal_value(cancelacion)
    if monto_pagado is None or monto_pagado < 0 or (monto_pagado == 0 and not permitir_monto_cero):
        raise ValueError("Ingresa un monto pagado mayor a cero para generar la constancia.")
    registro = rows[0]
    hoy = datetime.now(ZoneInfo("America/Lima")).date()
    context = {
        "cliente": limpiar_texto(registro.get("NomCliente")),
        "dni": limpiar_texto(registro.get("NumDocumento")),
        "tipo_documento": limpiar_texto(registro.get("TipoDocumento")) or "DNI",
        "operacion": clave_operacion(registro.get("Operacion")),
        "fecha_carta": fecha_larga_modelo_hoy(),
        "fecha_pago": format_fecha_pago(fecha_pago) or hoy.strftime("%d/%m/%Y"),
        "monto_pagado": format_money(monto_pagado),
    }
    formato = str(formato or "docx").lower()
    if formato not in ("docx", "pdf"):
        raise ValueError("Formato no soportado. Selecciona Word o PDF.")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{safe_filename(config['nombre'])}_{safe_filename(context['cliente'])}.{formato}"
    output_path = OUTPUT_DIR / filename
    if formato == "pdf":
        generar_pdf_sip_constancia(output_path, context)
    else:
        generar_docx_limpio(output_path, context, document_kind="sip_constancia")
    return {
        "path": output_path,
        "filename": filename,
        "formato": formato,
        "registro": registro,
        "auditoria_detalle": {
            "modalidad": "constancia_pago",
            "fecha_pago": context["fecha_pago"],
            "monto_pagado": context["monto_pagado"],
            "operaciones": [{"operacion": context["operacion"], "pago": context["monto_pagado"]}],
        },
    }


def generar_documento(documento_tipo, dni=None, operacion=None, codigo_grupo=None, cod_cre_grupal=None, cancelacion=None, fecha_pago=None, formato="docx", excepcion=False, encargado=None, pagos_grupales=None, cuotas_individual=None, operaciones_mibanco=None, pagos_mibanco=None, permitir_preview=False):
    config = obtener_config_documento(documento_tipo)
    cartera_id = int(config.get("cartera_id") or 133)

    if config.get("solo_correo"):
        raise ValueError("Este tipo solo genera el preview de correo. No descarga carta.")

    if config.get("document_kind") in ("mibanco_contado", "mibanco_cuotas"):
        return generar_documento_mibanco(config, dni=dni, operacion=operacion, cancelacion=cancelacion, fecha_pago=fecha_pago, formato=formato, operaciones_mibanco=operaciones_mibanco, pagos_mibanco=pagos_mibanco, excepcion=excepcion)

    if config.get("document_kind") == "sip_convenio":
        return generar_documento_sip(config, dni=dni, operacion=operacion, cancelacion=cancelacion, fecha_pago=fecha_pago, formato=formato, pagos_mibanco=pagos_mibanco, excepcion=excepcion)

    if config.get("document_kind") == "sip_constancia":
        return generar_constancia_pago_sip(config, dni=dni, operacion=operacion, cancelacion=cancelacion, fecha_pago=fecha_pago, formato=formato, permitir_monto_cero=permitir_preview)

    if documento_tipo == "cancelacion_grupal":
        return generar_documento_grupal(
            config,
            dni=dni,
            operacion=operacion,
            codigo_grupo=codigo_grupo,
            cod_cre_grupal=cod_cre_grupal,
            formato=formato,
            excepcion=excepcion,
            encargado=encargado,
            pagos_grupales=pagos_grupales,
        )

    if documento_tipo == "compromiso_cuota_grupal":
        return generar_documento_cuota_grupal(
            config,
            dni=dni,
            operacion=operacion,
            codigo_grupo=codigo_grupo,
            cod_cre_grupal=cod_cre_grupal,
            formato=formato,
            excepcion=excepcion,
            fiador=encargado,
            pagos_grupales=pagos_grupales,
        )

    registro = obtener_registro_unico(
        dni=dni,
        operacion=operacion,
        codigo_grupo=codigo_grupo,
        cod_cre_grupal=cod_cre_grupal,
        cartera_id=cartera_id,
    )

    if documento_tipo == "compromiso_cuota_individual" or config.get("document_kind") == "cuota_individual":
        context = preparar_contexto_cuota_individual(
            registro,
            cancelacion=cancelacion,
            fecha_pago=fecha_pago,
            excepcion=excepcion,
            cuotas_individual=cuotas_individual,
        )

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        formato = str(formato or "docx").lower()
        if formato not in ("docx", "pdf"):
            raise ValueError("Formato no soportado. Selecciona Word o PDF.")

        filename = f"{safe_filename(config['nombre'])}_{safe_filename(context['cliente'])}.{formato}"
        output_path = OUTPUT_DIR / filename

        if formato == "pdf":
            generar_pdf_cuota_individual_limpio(output_path, context)
        else:
            generar_docx_limpio(output_path, context, document_kind="compromiso_cuota_individual")

        return {
            "path": output_path,
            "filename": filename,
            "formato": formato,
            "registro": registro,
        }

    monto_cancelacion, _ = validar_cancelacion(cancelacion, registro.get("MtoCancelacionCliente"), excepcion=excepcion)
    deuda_total = decimal_value(registro.get("DeudaTotal"), Decimal("0"))
    monto_condonacion = max(deuda_total - monto_cancelacion, Decimal("0"))
    hoy = datetime.now(ZoneInfo("America/Lima")).date()
    context = {
        "cliente": limpiar_texto(registro.get("NomCliente")),
        "dni": limpiar_texto(registro.get("NumDocumento")),
        "direccion": limpiar_texto(registro.get("DireccionPrincipal")),
        "distrito": limpiar_texto(registro.get("DistritoPrincipal") or registro.get("Distrito_Principal") or registro.get("Distrito")),
        "operacion": limpiar_texto(registro.get("Operacion")),
        "deuda_total": format_money(deuda_total),
        "cancelacion": format_money(monto_cancelacion),
        "condonacion": format_money(monto_condonacion),
        "fecha_corta": hoy.strftime("%d/%m/%Y"),
        "fecha_larga": fecha_larga_hoy(),
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    formato = str(formato or "docx").lower()
    if formato not in ("docx", "pdf"):
        raise ValueError("Formato no soportado. Selecciona Word o PDF.")

    filename = f"{safe_filename(config['nombre'])}_{safe_filename(context['cliente'])}.{formato}"
    output_path = OUTPUT_DIR / filename

    if formato == "pdf":
        generar_pdf_limpio(output_path, context)
    else:
        generar_docx_limpio(output_path, context)

    return {
        "path": output_path,
        "filename": filename,
        "formato": formato,
        "registro": registro,
    }


def limpiar_documentos_generados(dias=2):
    if not OUTPUT_DIR.exists():
        return

    limite = datetime.now().timestamp() - (dias * 24 * 60 * 60)
    for path in list(OUTPUT_DIR.glob("*.docx")) + list(OUTPUT_DIR.glob("*.pdf")):
        if path.stat().st_mtime < limite:
            try:
                path.unlink()
            except OSError:
                pass
