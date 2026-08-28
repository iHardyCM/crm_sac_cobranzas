from datetime import date, datetime
from decimal import Decimal

from app.core.database import get_connection


CARTERAS = {
    112: "MIBANCO 1",
    143: "MIBANCO 2",
    135: "MIBANCO VIGENTE",
    124: "COMPARTAMOS CASTIGO INDIVIDUAL",
    126: "COMPARTAMOS VIGENTE INDIVIDUAL",
    128: "COMPARTAMOS VIGENTE CCM",
    133: "COMPARTAMOS VIGENTE GRUPAL / CSM",
    144: "COMPARTAMOS CASTIGO GRUPAL",
    132: "FINANCIERA OH",
    117: "INTERBANK",
    137: "INTERBANK CEDIDA",
    148: "FINANCIERA OH PROPIA",
}

CARTERAS_PERMITIDAS = {112, 117, 124, 126, 128, 132, 133, 135, 137, 143, 144, 148}


def serialize_value(value):
    if isinstance(value, Decimal):
        return float(value)

    if isinstance(value, (datetime, date)):
        return value.isoformat()

    return value


def fetch_resultset(cursor):
    if cursor.description is None:
        return []

    columns = [col[0] for col in cursor.description]
    rows = cursor.fetchall()

    return [
        {columns[i]: serialize_value(value) for i, value in enumerate(row)}
        for row in rows
    ]


def normalizar(texto):
    return str(texto or "").strip().upper()


def obtener_campo(row, *nombres):
    for nombre in nombres:
        if nombre in row and row.get(nombre) not in (None, ""):
            return row.get(nombre)

    nombres_normalizados = {str(k).lower(): k for k in row.keys()}
    for nombre in nombres:
        key = nombres_normalizados.get(str(nombre).lower())
        if key and row.get(key) not in (None, ""):
            return row.get(key)

    return None


def obtener_nombre_cliente(rows):
    for row in rows or []:
        nombre = obtener_campo(row, "nombre_cliente", "NOMBRE_CLIENTE", "nom_cli", "NOM_CLI")
        if nombre:
            return str(nombre).strip()

    return None


def es_si(valor):
    return normalizar(valor) in ("SI", "SÍ", "1", "TRUE")


def detectar_tipo_busqueda(q):
    q = str(q or "").strip()

    if len(q) == 8 and q.isdigit():
        return "DNI"

    if len(q) == 9 and q.isdigit():
        return "TELEFONO"

    return "IDCLIENTE"


def score_osiptel(valor):
    texto = normalizar(valor)

    if texto in ("SI", "SÍ"):
        return 30

    if texto == "SV":
        return 8

    if texto in ("NO", "LN"):
        return 0

    return 0


def score_whatsapp(valor):
    texto = normalizar(valor)

    if texto in ("SI", "SÍ"):
        return 5

    return 0


def score_timbra(valor):
    try:
        timbra = int(valor or 0)
    except (TypeError, ValueError):
        timbra = 0

    if timbra == 4:
        return 25
    if timbra == 3:
        return 20
    if timbra == 2:
        return 12
    if timbra == 1:
        return 6
    if timbra == 5:
        return 5  # marca de prueba, no debe ganar

    return 0


def score_tipo_fono(valor):
    texto = normalizar(valor)

    if "CEL" in texto:
        return 15
    if "FIJO" in texto:
        return 5

    return 0


def score_prioridad(valor):
    texto = normalizar(valor)

    mapa = {
        "V": 25,   # Verde: contacto efectivo
        "P": 18,   # Plomo: nuevo / potencial
        "Q": 18,   # Plomo: nuevo / potencial
        "T": 14,   # Turqueza: tercero familiar
        "A": 10,   # Amarillo: no contesta
        "F": -15,  # Fucsia: fallado
        "R": -30,  # Rojo: equivocado
    }

    return mapa.get(texto, 0)

def score_anio_fecha(valor):
    texto = normalizar(valor)

    if texto == "EMPRESA":
        return 10

    try:
        anio = int(texto)
    except (TypeError, ValueError):
        return 0

    if anio >= 2026:
        return 10
    if anio == 2025:
        return 8
    if anio == 2024:
        return 6
    if anio == 2023:
        return 4
    if anio <= 2022:
        return 2

    return 0


def score_anomes(valor):
    texto = normalizar(valor)

    try:
        anomes = int(texto)
    except (TypeError, ValueError):
        return 0

    if anomes >= 202606:
        return 10
    if anomes >= 202501:
        return 8
    if anomes >= 202401:
        return 6
    if anomes >= 202301:
        return 4

    return 2

def score_origen(origen, tipo_base=None, t_emp=None):
    origen = normalizar(origen)

    if origen == "EMPRESA":
        return 15

    if origen == "BASES INTERNAS":
        return 12

    if origen == "SEARCH":
        return 10

    if origen in ("AVAL", "CONYUGE", "REP LEGAL", "HERMANO"):
        return 5

    if origen == "OTRO":
        return 3

    return 0


def penalizacion_por_relacion(total_dnis, total_carteras, origen):
    origen = normalizar(origen)

    if total_dnis <= 1:
        return 0

    if origen == "AVAL":
        return -5

    if origen == "CONYUGE":
        return -5

    if origen == "REP LEGAL":
        return -10

    if origen == "HERMANO":
        return -8

    if origen == "EMPRESA":
        return -12

    if total_dnis >= 5:
        return -35

    if total_dnis >= 2:
        return -25

    return 0


def obtener_condicion_telefono(total_dnis, total_carteras, origen):
    origen = normalizar(origen)

    if total_dnis <= 1 and total_carteras <= 1:
        return "Único cliente"

    if total_dnis <= 1 and total_carteras > 1:
        return "Multicartera mismo cliente"

    if origen == "AVAL":
        return "Aval de otro cliente"

    if origen == "CONYUGE":
        return "Cónyuge de otro cliente"

    if origen == "REP LEGAL":
        return "Representante legal"

    if origen == "HERMANO":
        return "Hermano / familiar"

    if origen == "EMPRESA":
        return "Teléfono empresa compartido"

    return "Compartido sin relación clara"


def obtener_recomendacion(score, condicion):
    condicion = normalizar(condicion)

    if "COMPARTIDO SIN RELACION" in condicion:
        if score >= 70:
            return "Usar validando identidad"
        return "Baja confiabilidad"

    if score >= 80:
        return "Recomendado para contacto"

    if score >= 60:
        return "Buena alternativa"

    if score >= 40:
        return "Usar validando identidad"

    return "No priorizar"


def obtener_contexto_telefonos(cursor, telefonos):
    if not telefonos:
        return {}

    placeholders = ",".join("?" for _ in telefonos)

    cursor.execute(
        f"""
        SELECT
            TELEFONO,
            COUNT(DISTINCT DNI) AS TOTAL_DNIS,
            COUNT(DISTINCT IDCARTERA) AS TOTAL_CARTERAS
        FROM DESARROLLO.DBO.TEMP_TELEFONOS WITH(NOLOCK)
        WHERE TELEFONO IN ({placeholders})
        GROUP BY TELEFONO
        """,
        *telefonos
    )

    contexto = {}

    for telefono, total_dnis, total_carteras in cursor.fetchall():
        contexto[str(telefono)] = {
            "TOTAL_DNIS": int(total_dnis or 0),
            "TOTAL_CARTERAS": int(total_carteras or 0),
        }

    return contexto


def enriquecer_telefonos(rows, contexto):
    data = []

    for row in rows:
        telefono = str(row.get("TELEFONO") or "").strip()
        item_contexto = contexto.get(telefono, {})

        total_dnis = int(item_contexto.get("TOTAL_DNIS", 1))
        total_carteras = int(item_contexto.get("TOTAL_CARTERAS", 1))

        condicion = obtener_condicion_telefono(
            total_dnis=total_dnis,
            total_carteras=total_carteras,
            origen=row.get("ORIGEN"),
        )

        score_base = (
            score_osiptel(row.get("OSIPTEL"))
            + score_timbra(row.get("TIMBRA"))
            + score_prioridad(row.get("PRIORIDAD"))
            + score_origen(row.get("ORIGEN"), row.get("TIPO_BASE"), row.get("T_EMP"))
            + score_anio_fecha(row.get("AÑO_FECH_TELF"))
            + score_anomes(row.get("AÑOMES_TELF"))
            + score_whatsapp(row.get("WHATSAPP"))
        )

        penalizacion = penalizacion_por_relacion(
            total_dnis=total_dnis,
            total_carteras=total_carteras,
            origen=row.get("ORIGEN"),
        )

        score_final = max(0, min(100, score_base + penalizacion))
        nombre_cliente = obtener_campo(row, "nombre_cliente", "NOMBRE_CLIENTE", "nom_cli", "NOM_CLI")

        item = dict(row)
        item["nombre_cliente"] = str(nombre_cliente).strip() if nombre_cliente else None
        item["NOMBRE_CLIENTE"] = item["nombre_cliente"]
        item["CARTERA"] = CARTERAS.get(int(row["IDCARTERA"]), f"Cartera {row['IDCARTERA']}") if row.get("IDCARTERA") is not None else None
        item["TOTAL_DNIS_ASOCIADOS"] = total_dnis
        item["TOTAL_CARTERAS_ASOCIADAS"] = total_carteras
        item["CONDICION_TELEFONO"] = condicion
        item["SCORE_CONTACTO"] = score_final
        item["RECOMENDACION"] = obtener_recomendacion(score_final, condicion)

        data.append(item)

    data.sort(
        key=lambda x: (
            int(x.get("SCORE_CONTACTO") or 0),
            int(x.get("TIMBRA") or 0) if str(x.get("TIMBRA") or "").isdigit() else 0,
        ),
        reverse=True
    )

    return data


def construir_resumen(rows):
    if not rows:
        return {
            "dni": None,
            "idcliente": None,
            "nombre_cliente": None,
            "carteras": [],
            "total_telefonos": 0,
            "con_osiptel": 0,
            "con_whatsapp": 0,
            "timbran": 0,
            "telefono_recomendado": None,
            "score_recomendado": None,
            "tiene_compartidos": False,
            "tiene_multicartera": False,
        }

    telefonos = sorted({str(r.get("TELEFONO")) for r in rows if r.get("TELEFONO")})
    carteras = sorted({str(r.get("IDCARTERA")) for r in rows if r.get("IDCARTERA")})

    con_osiptel = sum(1 for r in rows if es_si(r.get("OSIPTEL")))
    con_whatsapp = sum(1 for r in rows if es_si(r.get("WHATSAPP")))

    timbran = 0
    for r in rows:
        try:
            if int(r.get("TIMBRA") or 0) > 0:
                timbran += 1
        except (TypeError, ValueError):
            pass

    recomendado = rows[0] if rows else {}

    return {
        "dni": rows[0].get("DNI"),
        "idcliente": rows[0].get("IDCLIENTE"),
        "nombre_cliente": obtener_nombre_cliente(rows),
        "carteras": carteras,
        "total_telefonos": len(telefonos),
        "con_osiptel": con_osiptel,
        "con_whatsapp": con_whatsapp,
        "timbran": timbran,
        "telefono_recomendado": recomendado.get("TELEFONO"),
        "score_recomendado": recomendado.get("SCORE_CONTACTO"),
        "tiene_compartidos": any(int(r.get("TOTAL_DNIS_ASOCIADOS") or 0) > 1 for r in rows),
        "tiene_multicartera": any(int(r.get("TOTAL_CARTERAS_ASOCIADAS") or 0) > 1 for r in rows),
    }


def obtener_relacionados_telefono(cursor, telefono):
    cursor.execute(
        """
        SELECT DISTINCT
            DNI,
            IDCLIENTE,
            RTRIM(LTRIM(nom_cli)) AS NOMBRE_CLIENTE,
            IDCARTERA,
            ORIGEN,
            TIPO_BASE,
            T_EMP
        FROM DESARROLLO.DBO.TEMP_TELEFONOS WITH(NOLOCK)
        WHERE TELEFONO = ?
        ORDER BY DNI, IDCARTERA
        """,
        telefono
    )

    rows = fetch_resultset(cursor)

    for row in rows:
        row["CARTERA"] = CARTERAS.get(int(row["IDCARTERA"]), f"Cartera {row['IDCARTERA']}") if row.get("IDCARTERA") is not None else None

    return rows


def buscar_telefonos_cliente(q, idcartera=None, osiptel=None, whatsapp=None, timbra=None, tipo=None, origen=None):
    q = str(q or "").strip()

    if not q:
        raise ValueError("Debe ingresar DNI, ID Cliente o teléfono.")

    conn = None
    cursor = None

    try:
        conn = get_connection()
        cursor = conn.cursor()

        where = """
            (
                RTRIM(LTRIM(DNI)) = ?
                OR CAST(IDCLIENTE AS VARCHAR(50)) = ?
                OR CAST(TELEFONO AS VARCHAR(50)) = ?
                OR UPPER(RTRIM(LTRIM(nom_cli))) LIKE ?
            )
        """
        params = [q, q, q, f"%{q.upper()}%"]

        if idcartera and idcartera != "TODOS":
            where += " AND IDCARTERA = ?"
            params.append(idcartera)

        if osiptel and osiptel != "TODOS":
            where += " AND OSIPTEL = ?"
            params.append(osiptel)

        if whatsapp and whatsapp != "TODOS":
            where += " AND WHATSAPP = ?"
            params.append(whatsapp)

        if timbra and timbra != "TODOS":
            where += " AND CAST(TIMBRA AS VARCHAR(20)) = ?"
            params.append(timbra)

        if tipo and tipo != "TODOS":
            where += " AND TIPO_FONO = ?"
            params.append(tipo)

        if origen and origen != "TODOS":
            where += " AND ORIGEN = ?"
            params.append(origen)

        cursor.execute(
            f"""
            SELECT TOP 200
                RTRIM(LTRIM(DNI)) AS DNI,
                IDCLIENTE,
                RTRIM(LTRIM(nom_cli)) AS NOMBRE_CLIENTE,
                TELEFONO,
                PRIORIDAD,
                IDCARTERA,
                TIPO_FONO,
                ORIGEN,
                [AÑO_FECH_TELF],
                TIPO_BASE,
                [AÑOMES_TELF],
                WHATSAPP,
                TIMBRA,
                OSIPTEL,
                T_EMP
            FROM DESARROLLO.DBO.TEMP_TELEFONOS WITH(NOLOCK)
            WHERE {where}
            ORDER BY
                CASE WHEN OSIPTEL = 'SI' THEN 1 ELSE 0 END DESC,
                CASE 
                    WHEN TRY_CAST(TIMBRA AS INT) = 4 THEN 5
                    WHEN TRY_CAST(TIMBRA AS INT) = 3 THEN 4
                    WHEN TRY_CAST(TIMBRA AS INT) = 2 THEN 3
                    WHEN TRY_CAST(TIMBRA AS INT) = 1 THEN 2
                    WHEN TRY_CAST(TIMBRA AS INT) = 5 THEN 1
                    ELSE 0
                END DESC,
                CASE PRIORIDAD
                    WHEN 'V' THEN 1
                    WHEN 'P' THEN 2
                    WHEN 'Q' THEN 2
                    WHEN 'T' THEN 3
                    WHEN 'A' THEN 4
                    WHEN 'F' THEN 5
                    WHEN 'R' THEN 6
                    ELSE 7
                END ASC,
                CASE 
                    WHEN ORIGEN = 'EMPRESA' THEN 1
                    WHEN ORIGEN = 'BASES INTERNAS' THEN 2
                    WHEN ORIGEN = 'SEARCH' THEN 3
                    ELSE 4
                END ASC,
                CASE 
                    WHEN TRY_CAST([AÑO_FECH_TELF] AS INT) IS NOT NULL THEN TRY_CAST([AÑO_FECH_TELF] AS INT)
                    ELSE 0
                END DESC,
                CASE 
                    WHEN TRY_CAST([AÑOMES_TELF] AS INT) IS NOT NULL THEN TRY_CAST([AÑOMES_TELF] AS INT)
                    ELSE 0
                END DESC,
                CASE WHEN WHATSAPP = 'SI' THEN 1 ELSE 0 END DESC
            """,
            *params
        )

        rows = fetch_resultset(cursor)

        if not rows:
            return {
                "ok": True,
                "message": "No se encontraron teléfonos activos.",
                "data": {
                    "modo_busqueda": detectar_tipo_busqueda(q),
                    "resumen": construir_resumen([]),
                    "telefonos": [],
                    "relacionados": [],
                }
            }

        telefonos = sorted({str(row["TELEFONO"]) for row in rows if row.get("TELEFONO")})
        contexto = obtener_contexto_telefonos(cursor, telefonos)
        telefonos_enriquecidos = enriquecer_telefonos(rows, contexto)

        relacionados = []

        if detectar_tipo_busqueda(q) == "TELEFONO":
            relacionados = obtener_relacionados_telefono(cursor, q)

        return {
            "ok": True,
            "message": "Consulta realizada correctamente.",
            "data": {
                "modo_busqueda": detectar_tipo_busqueda(q),
                "resumen": construir_resumen(telefonos_enriquecidos),
                "telefonos": telefonos_enriquecidos,
                "relacionados": relacionados,
            }
        }

    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()


def listar_filtros_telefonos():
    conn = None
    cursor = None

    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT DISTINCT IDCARTERA
            FROM DESARROLLO.DBO.TEMP_TELEFONOS WITH(NOLOCK)
            ORDER BY IDCARTERA
        """)
        carteras = [
            {
                "idcartera": int(row[0]),
                "cartera": CARTERAS.get(int(row[0]), f"Cartera {row[0]}")
            }
            for row in cursor.fetchall()
            if row[0] is not None and int(row[0]) in CARTERAS_PERMITIDAS
        ]

        cursor.execute("""
            SELECT DISTINCT OSIPTEL
            FROM DESARROLLO.DBO.TEMP_TELEFONOS WITH(NOLOCK)
            WHERE OSIPTEL IS NOT NULL
            ORDER BY OSIPTEL
        """)
        osiptel = [row[0] for row in cursor.fetchall()]

        cursor.execute("""
            SELECT DISTINCT WHATSAPP
            FROM DESARROLLO.DBO.TEMP_TELEFONOS WITH(NOLOCK)
            WHERE WHATSAPP IS NOT NULL
            ORDER BY WHATSAPP
        """)
        whatsapp = [row[0] for row in cursor.fetchall()]

        cursor.execute("""
            SELECT DISTINCT TIMBRA
            FROM DESARROLLO.DBO.TEMP_TELEFONOS WITH(NOLOCK)
            WHERE TIMBRA IS NOT NULL
            ORDER BY TRY_CAST(TIMBRA AS INT) DESC
        """)
        timbra = [row[0] for row in cursor.fetchall()]

        cursor.execute("""
            SELECT DISTINCT TIPO_FONO
            FROM DESARROLLO.DBO.TEMP_TELEFONOS WITH(NOLOCK)
            WHERE TIPO_FONO IS NOT NULL
            ORDER BY TIPO_FONO
        """)
        tipo = [row[0] for row in cursor.fetchall()]

        cursor.execute("""
            SELECT DISTINCT ORIGEN
            FROM DESARROLLO.DBO.TEMP_TELEFONOS WITH(NOLOCK)
            WHERE ORIGEN IS NOT NULL
            ORDER BY ORIGEN
        """)
        origen = [row[0] for row in cursor.fetchall()]

        return {
            "data": {
                "carteras": carteras,
                "osiptel": osiptel,
                "whatsapp": whatsapp,
                "timbra": timbra,
                "tipo": tipo,
                "origen": origen,
            }
        }

    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()


def obtener_detalle_telefono(telefono):
    telefono = str(telefono or "").strip()

    if not telefono:
        raise ValueError("Teléfono inválido.")

    conn = None
    cursor = None

    try:
        conn = get_connection()
        cursor = conn.cursor()

        relacionados = obtener_relacionados_telefono(cursor, telefono)

        if not relacionados:
            raise ValueError("No se encontraron registros para el teléfono.")

        return {
            "ok": True,
            "data": relacionados
        }

    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()
