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
    139: "COMPARTAMOS BANCO",
    132: "FINANCIERA OH",
    117: "INTERBANK",
    137: "INTERBANK CEDIDA",
}


GRUPOS_CARTERA = {
    112: {"id": "MIBANCO", "nombre": "MIBANCO", "ids": [112, 143, 135]},
    143: {"id": "MIBANCO", "nombre": "MIBANCO", "ids": [112, 143, 135]},
    135: {"id": "MIBANCO", "nombre": "MIBANCO", "ids": [112, 143, 135]},
    124: {"id": "COMPARTAMOS_CASTIGO", "nombre": "COMPARTAMOS CASTIGO", "ids": [124, 144]},
    144: {"id": "COMPARTAMOS_CASTIGO", "nombre": "COMPARTAMOS CASTIGO", "ids": [124, 144]},
    126: {"id": "COMPARTAMOS_VIGENTE", "nombre": "COMPARTAMOS VIGENTE", "ids": [126, 128, 133]},
    128: {"id": "COMPARTAMOS_VIGENTE", "nombre": "COMPARTAMOS VIGENTE", "ids": [126, 128, 133]},
    133: {"id": "COMPARTAMOS_VIGENTE", "nombre": "COMPARTAMOS VIGENTE", "ids": [126, 128, 133]},
    132: {"id": "132", "nombre": "FINANCIERA OH", "ids": [132]},
    117: {"id": "117", "nombre": "INTERBANK", "ids": [117]},
    137: {"id": "137", "nombre": "INTERBANK CEDIDA", "ids": [137]},
}


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


def obtener_mapa_usuarios(cursor):
    cursor.execute("""
        SELECT
            IDUSUARIO,
            LTRIM(RTRIM(USUARIO)) AS USUARIO,
            IDCARTERA,
            UPPER(LTRIM(RTRIM(ISNULL(TIPOUSUARIO, '')))) AS TIPOUSUARIO
        FROM SISCOB.DBO.USUARIO WITH(NOLOCK)
        WHERE IDCARTERA IS NOT NULL
    """)

    mapa_id = {}
    mapa_usuario = {}

    for idusuario, usuario, idcartera, tipousuario in cursor.fetchall():
        item = {
            "idusuario": int(idusuario) if idusuario is not None else None,
            "usuario": str(usuario).strip() if usuario is not None else None,
            "idcartera": int(idcartera) if idcartera is not None else None,
            "cartera": CARTERAS.get(int(idcartera), f"Cartera {idcartera}") if idcartera is not None else None,
            "tipousuario": str(tipousuario).strip().upper() if tipousuario is not None else "",
        }

        if item["idusuario"] is not None:
            mapa_id[item["idusuario"]] = item
        if item["usuario"]:
            mapa_usuario[item["usuario"]] = item

    return mapa_id, mapa_usuario


def obtener_dotacion_grupos(cursor):
    cursor.execute("""
        SELECT
            IDCARTERA,
            COUNT(1) AS agentes_asignados
        FROM SISCOB.DBO.USUARIO WITH(NOLOCK)
        WHERE IDCARTERA IS NOT NULL
          AND UPPER(LTRIM(RTRIM(ISNULL(TIPOUSUARIO, '')))) = 'GESTOR'
        GROUP BY IDCARTERA
    """)

    dotacion = {}

    for idcartera, agentes in cursor.fetchall():
        try:
            cartera = int(idcartera)
            grupo = obtener_grupo_cartera(cartera)
        except (TypeError, ValueError):
            continue

        dotacion[str(cartera)] = dotacion.get(str(cartera), 0) + int(agentes or 0)
        dotacion[grupo["id"]] = dotacion.get(grupo["id"], 0) + int(agentes or 0)

    return dotacion


def valor_por_claves(row, claves):
    normalizado = {normalizar(k): v for k, v in row.items()}

    for clave in claves:
        valor = normalizado.get(normalizar(clave))
        if valor not in (None, ""):
            return valor

    return None


def normalizar(texto):
    return "".join(ch for ch in str(texto or "").upper() if ch.isalnum())


def obtener_grupo_cartera(idcartera):
    try:
        cartera = int(idcartera)
    except (TypeError, ValueError):
        return {"id": str(idcartera), "nombre": f"Cartera {idcartera}", "ids": [idcartera]}

    return GRUPOS_CARTERA.get(cartera, {
        "id": str(cartera),
        "nombre": CARTERAS.get(cartera, f"Cartera {cartera}"),
        "ids": [cartera],
    })


def extraer_usuario_agente(valor):
    texto = str(valor or "").strip()
    if not texto:
        return None

    posible = texto.split("-")[0].strip()
    return posible or None


def enriquecer_por_usuario(rows, mapa_id, mapa_usuario):
    data = []

    for row in rows:
        idcartera_resultado = valor_por_claves(row, ["IDCARTERA", "IdCartera", "idcartera", "ID_CARTERA"])
        idusuario = valor_por_claves(row, ["IDUSUARIO", "IdUsuario", "id_usuario"])
        usuario = valor_por_claves(row, ["USUARIO", "Usuario", "dni_usuario"])
        agente = valor_por_claves(row, ["AGENTE", "Agente", "nombre_agente"])

        info = None

        if idusuario not in (None, ""):
            try:
                info = mapa_id.get(int(idusuario))
            except (TypeError, ValueError):
                info = None

        if info is None and usuario not in (None, ""):
            info = mapa_usuario.get(str(usuario).strip())

        if info is None and agente not in (None, ""):
            info = mapa_usuario.get(extraer_usuario_agente(agente))

        if info is None:
            continue

        if info.get("tipousuario") != "GESTOR":
            continue

        if idcartera_resultado is None:
            continue

        grupo_gestion = obtener_grupo_cartera(idcartera_resultado)
        grupo_usuario = obtener_grupo_cartera(info["idcartera"])

        item = dict(row)
        item["IDUSUARIO"] = info["idusuario"]
        item["USUARIO"] = info["usuario"]
        item["IDCARTERA_ORIGINAL"] = int(idcartera_resultado)
        item["IDCARTERA_USUARIO"] = info["idcartera"]
        item["CARTERA_USUARIO"] = info["cartera"]
        item["ID_GRUPO_CARTERA"] = grupo_gestion["id"]
        item["GRUPO_CARTERA"] = grupo_gestion["nombre"]
        item["IDS_CARTERA_GRUPO"] = ",".join(str(x) for x in grupo_gestion["ids"])
        item["ES_APOYO_CARTERA"] = 1 if grupo_gestion["id"] != grupo_usuario["id"] else 0
        item["IDCARTERA"] = grupo_gestion["id"]
        item["CARTERA"] = grupo_gestion["nombre"]
        data.append(item)

    return data


def obtener_resumen_control_horario(fecha=None, idcartera=None, idusuario=None):
    conn = None
    cursor = None

    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            EXEC dbo.SP_CRM_CONTROL_HORARIO_GESTION_RECUPERO
                @Fecha = ?,
                @IdCartera = ?,
                @IdUsuario = ?
            """,
            fecha,
            idcartera,
            idusuario
        )

        resultsets = []

        while True:
            if cursor.description is not None:
                resultsets.append(fetch_resultset(cursor))

            if not cursor.nextset():
                break

        mapa_id, mapa_usuario = obtener_mapa_usuarios(cursor)
        dotacion_grupos = obtener_dotacion_grupos(cursor)

        detalle = enriquecer_por_usuario(
            resultsets[0] if len(resultsets) > 0 else [],
            mapa_id,
            mapa_usuario
        )
        agente_hora = enriquecer_por_usuario(
            resultsets[6] if len(resultsets) > 6 else [],
            mapa_id,
            mapa_usuario
        )

        return {
            "detalle": detalle,
            "kpis": resultsets[1][0] if len(resultsets) > 1 and resultsets[1] else {},
            "top_avance": resultsets[2] if len(resultsets) > 2 else [],
            "pendientes_criticos": resultsets[3] if len(resultsets) > 3 else [],
            "alertas": resultsets[4] if len(resultsets) > 4 else [],
            "horas": resultsets[5] if len(resultsets) > 5 else [],
            "agente_hora": agente_hora,
            "dotacion_grupos": dotacion_grupos,
        }

    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()
