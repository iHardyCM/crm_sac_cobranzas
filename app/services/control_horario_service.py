from calendar import monthrange
from datetime import date, datetime, timedelta
from decimal import Decimal
from io import BytesIO

import pandas as pd

from app.core.database import get_connection
from app.core.db_siscob import engine_siscob


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
    148: {"id": "148", "nombre": "FINANCIERA OH PROPIA", "ids": [148]},
    117: {"id": "117", "nombre": "INTERBANK", "ids": [117]},
    137: {"id": "137", "nombre": "INTERBANK CEDIDA", "ids": [137]},
}

PERFILES_RECUPERO_APOYO = {"ADM", "SUPERVISOR", "JEFE"}


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


def serialize_row_mapping(row):
    return {key: serialize_value(value) for key, value in dict(row).items()}


def obtener_mapa_usuarios(cursor):
    cursor.execute("""
        SELECT
            IDUSUARIO,
            LTRIM(RTRIM(USUARIO)) AS USUARIO,
            IDCARTERA,
            UPPER(LTRIM(RTRIM(ISNULL(TIPOUSUARIO, '')))) AS TIPOUSUARIO,
            UPPER(LTRIM(RTRIM(ISNULL(ESTADO, '')))) AS ESTADO
        FROM SISCOB.DBO.USUARIO WITH(NOLOCK)
        WHERE IDCARTERA IS NOT NULL
    """)

    mapa_id = {}
    mapa_usuario = {}

    for idusuario, usuario, idcartera, tipousuario, estado in cursor.fetchall():
        item = {
            "idusuario": int(idusuario) if idusuario is not None else None,
            "usuario": str(usuario).strip() if usuario is not None else None,
            "idcartera": int(idcartera) if idcartera is not None else None,
            "cartera": CARTERAS.get(int(idcartera), f"Cartera {idcartera}") if idcartera is not None else None,
            "tipousuario": str(tipousuario).strip().upper() if tipousuario is not None else "",
            "estado": str(estado).strip().upper() if estado is not None else "",
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
          AND UPPER(LTRIM(RTRIM(ISNULL(ESTADO, '')))) <> 'E'
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


def es_perfil_recupero_apoyo(info):
    return str(info.get("tipousuario") or "").strip().upper() in PERFILES_RECUPERO_APOYO


def enriquecer_por_usuario(rows, mapa_id, mapa_usuario, incluir_apoyo_recupero=False):
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

        if info.get("estado") == "E":
            continue

        es_gestor = info.get("tipousuario") == "GESTOR"
        es_apoyo_recupero = incluir_apoyo_recupero and es_perfil_recupero_apoyo(info)

        if not es_gestor and not es_apoyo_recupero:
            continue

        if idcartera_resultado is None:
            continue

        grupo_gestion = obtener_grupo_cartera(idcartera_resultado)
        grupo_usuario = obtener_grupo_cartera(info["idcartera"])

        item = dict(row)
        item["IDUSUARIO"] = info["idusuario"]
        item["USUARIO"] = info["usuario"]
        item["TIPOUSUARIO"] = info["tipousuario"]
        item["ES_RECUPERO_APOYO"] = 0 if es_gestor else 1
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


def obtener_clientes_unicos_control(cursor, fecha=None, idcartera=None, idusuario=None, incluir_apoyo_recupero=False):
    fecha_base = fecha_desde_parametro(fecha)
    fecha_fin = fecha_base + timedelta(days=1)
    params = [fecha_base, fecha_fin]
    filtros = [
        "G.FECHA >= ?",
        "G.FECHA < ?",
        "G.IDCLIENTE IS NOT NULL",
        "G.IDUSUARIO IS NOT NULL",
        "G.IDCARTERA IS NOT NULL",
        "G.IDCARTERA NOT IN (106, 100, 108, 110, 104, 141, 125, 119, 127, 121, 120, 130, 98, 122)",
        "UPPER(LTRIM(RTRIM(ISNULL(U.ESTADO, '')))) <> 'E'",
    ]

    if incluir_apoyo_recupero:
        filtros.append("UPPER(LTRIM(RTRIM(ISNULL(U.TIPOUSUARIO, '')))) IN ('GESTOR', 'ADM', 'SUPERVISOR', 'JEFE')")
    else:
        filtros.append("UPPER(LTRIM(RTRIM(ISNULL(U.TIPOUSUARIO, '')))) = 'GESTOR'")

    if idcartera is not None:
        filtros.append("G.IDCARTERA = ?")
        params.append(idcartera)

    if idusuario is not None:
        filtros.append("G.IDUSUARIO = ?")
        params.append(idusuario)

    cursor.execute(
        f"""
        SELECT
            G.IDUSUARIO,
            G.IDCARTERA,
            COUNT(DISTINCT G.IDCLIENTE) AS CLIENTES_UNICOS_GESTION,
            COUNT(DISTINCT CASE
                WHEN UPPER(LTRIM(RTRIM(ISNULL(I.TIPOCONTACTO, '')))) = 'CEF'
                THEN G.IDCLIENTE
            END) AS CLIENTES_UNICOS_CEF
        FROM SISCOB.DBO.GESTION G WITH(NOLOCK)
        LEFT JOIN SISCOB.DBO.USUARIO U WITH(NOLOCK)
            ON U.IDUSUARIO = G.IDUSUARIO
        LEFT JOIN SISCOB.DBO.INDICADOR I WITH(NOLOCK)
            ON I.IDINDICADOR = G.IDINDICADOR
        WHERE {" AND ".join(filtros)}
        GROUP BY G.IDUSUARIO, G.IDCARTERA
        """,
        *params
    )

    resultado = {}
    for id_usuario, id_cartera, clientes_gestion, clientes_cef in cursor.fetchall():
        try:
            key = (int(id_usuario), int(id_cartera))
        except (TypeError, ValueError):
            continue

        resultado[key] = {
            "CLIENTES_UNICOS_GESTION": int(clientes_gestion or 0),
            "CLIENTES_UNICOS_CEF": int(clientes_cef or 0),
        }

    return resultado


def aplicar_clientes_unicos(detalle, clientes_unicos):
    for row in detalle:
        try:
            idusuario = int(row.get("IDUSUARIO"))
            idcartera = int(row.get("IDCARTERA_ORIGINAL", row.get("IDCARTERA")))
        except (TypeError, ValueError):
            continue

        valores = clientes_unicos.get((idusuario, idcartera), {})
        row["CLIENTES_UNICOS_GESTION"] = valores.get("CLIENTES_UNICOS_GESTION", 0)
        row["CLIENTES_UNICOS_CEF"] = valores.get("CLIENTES_UNICOS_CEF", 0)


def obtener_compromisos_activos_control(cursor, fecha=None, idcartera=None, idusuario=None, incluir_apoyo_recupero=False):
    fecha_base = fecha_desde_parametro(fecha)
    fecha_fin = fecha_base + timedelta(days=1)
    params = [fecha_base, fecha_fin, fecha_base, fecha_fin]
    filtros = [
        "((C.FECHAGENERO >= ? AND C.FECHAGENERO < ?) OR (C.FECHACOMPROMISO >= ? AND C.FECHACOMPROMISO < ?))",
        "ISNULL(C.MONTO, 0) > 0",
        "G.IDUSUARIO IS NOT NULL",
        "G.IDCARTERA IS NOT NULL",
        "G.IDCARTERA NOT IN (106, 100, 108, 110, 104, 141, 125, 119, 127, 121, 120, 130, 98, 122)",
        "UPPER(LTRIM(RTRIM(ISNULL(U.ESTADO, '')))) <> 'E'",
        "UPPER(LTRIM(RTRIM(ISNULL(CL.ESTADO, '')))) IN ('A', 'N')",
    ]

    if incluir_apoyo_recupero:
        filtros.append("UPPER(LTRIM(RTRIM(ISNULL(U.TIPOUSUARIO, '')))) IN ('GESTOR', 'ADM', 'SUPERVISOR', 'JEFE')")
    else:
        filtros.append("UPPER(LTRIM(RTRIM(ISNULL(U.TIPOUSUARIO, '')))) = 'GESTOR'")

    if idcartera is not None:
        filtros.append("G.IDCARTERA = ?")
        params.append(idcartera)

    if idusuario is not None:
        filtros.append("G.IDUSUARIO = ?")
        params.append(idusuario)

    cursor.execute(
        f"""
        SELECT
            G.IDUSUARIO,
            G.IDCARTERA,
            SUM(CASE WHEN C.FECHAGENERO >= ? AND C.FECHAGENERO < ? THEN 1 ELSE 0 END) AS Q_PDP_ACTIVO,
            SUM(CASE WHEN C.FECHAGENERO >= ? AND C.FECHAGENERO < ? THEN ISNULL(C.MONTO, 0) ELSE 0 END) AS PDP_ACTIVO,
            SUM(CASE WHEN C.FECHACOMPROMISO >= ? AND C.FECHACOMPROMISO < ? THEN 1 ELSE 0 END) AS Q_PROYECTADO_ACTIVO,
            SUM(CASE WHEN C.FECHACOMPROMISO >= ? AND C.FECHACOMPROMISO < ? THEN ISNULL(C.MONTO, 0) ELSE 0 END) AS PROYECTADO_ACTIVO
        FROM SISCOB.DBO.COMPROMISO C WITH(NOLOCK)
        LEFT JOIN SISCOB.DBO.GESTION G WITH(NOLOCK)
            ON G.IDGESTION = C.IDGESTION
        LEFT JOIN SISCOB.DBO.USUARIO U WITH(NOLOCK)
            ON U.IDUSUARIO = G.IDUSUARIO
        LEFT JOIN SISCOB.DBO.CLIENTE CL WITH(NOLOCK)
            ON CL.IDCLIENTE = G.IDCLIENTE
        WHERE {" AND ".join(filtros)}
        GROUP BY G.IDUSUARIO, G.IDCARTERA
        """,
        fecha_base,
        fecha_fin,
        fecha_base,
        fecha_fin,
        fecha_base,
        fecha_fin,
        fecha_base,
        fecha_fin,
        *params
    )

    resultado = {}
    for id_usuario, id_cartera, q_pdp, pdp, q_proyectado, proyectado in cursor.fetchall():
        try:
            key = (int(id_usuario), int(id_cartera))
        except (TypeError, ValueError):
            continue

        resultado[key] = {
            "Q_PDP_GEN": int(q_pdp or 0),
            "PDP_GEN": float(pdp or 0),
            "Q_PROYECTADO": int(q_proyectado or 0),
            "PROYECTADO": float(proyectado or 0),
        }

    return resultado


def aplicar_compromisos_activos(detalle, compromisos_activos):
    for row in detalle:
        try:
            idusuario = int(row.get("IDUSUARIO"))
            idcartera = int(row.get("IDCARTERA_ORIGINAL", row.get("IDCARTERA")))
        except (TypeError, ValueError):
            continue

        valores = compromisos_activos.get(
            (idusuario, idcartera),
            {"Q_PDP_GEN": 0, "PDP_GEN": 0, "Q_PROYECTADO": 0, "PROYECTADO": 0}
        )
        pago = float(valor_por_claves(row, ["PAGO", "pago", "PAGO_HOY", "pago_hoy", "MONTO_PAGO"]) or 0)
        proyectado = float(valores.get("PROYECTADO") or 0)
        row["Q_PDP_GEN"] = valores.get("Q_PDP_GEN", 0)
        row["PDP_GEN"] = valores.get("PDP_GEN", 0)
        row["Q_PROYECTADO"] = valores.get("Q_PROYECTADO", 0)
        row["PROYECTADO"] = proyectado
        row["PENDIENTE"] = max(proyectado - pago, 0)
        row["AVANCE"] = (pago * 100 / proyectado) if proyectado else 0


def obtener_resumen_control_horario(fecha=None, idcartera=None, idusuario=None, incluir_apoyo_recupero=False):
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
            mapa_usuario,
            incluir_apoyo_recupero=incluir_apoyo_recupero
        )
        agente_hora = enriquecer_por_usuario(
            resultsets[6] if len(resultsets) > 6 else [],
            mapa_id,
            mapa_usuario,
            incluir_apoyo_recupero=incluir_apoyo_recupero
        )
        clientes_unicos = obtener_clientes_unicos_control(
            cursor,
            fecha=fecha,
            idcartera=idcartera,
            idusuario=idusuario,
            incluir_apoyo_recupero=incluir_apoyo_recupero
        )
        compromisos_activos = obtener_compromisos_activos_control(
            cursor,
            fecha=fecha,
            idcartera=idcartera,
            idusuario=idusuario,
            incluir_apoyo_recupero=incluir_apoyo_recupero
        )
        aplicar_clientes_unicos(detalle, clientes_unicos)
        aplicar_compromisos_activos(detalle, compromisos_activos)

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


def fecha_desde_parametro(fecha=None):
    if isinstance(fecha, date):
        return fecha

    texto = str(fecha or "").strip()
    if not texto:
        return date.today()

    try:
        return datetime.strptime(texto[:10], "%Y-%m-%d").date()
    except ValueError:
        return date.today()


def numero_export(row, claves):
    valor = valor_por_claves(row, claves)
    try:
        return float(valor or 0)
    except (TypeError, ValueError):
        return 0


def texto_export(row, claves, default=""):
    valor = valor_por_claves(row, claves)
    return default if valor in (None, "") else valor


def pct_export(numerador, denominador):
    return numerador / denominador if denominador else 0


def filas_control_para_exportar(fecha=None, idcarteras=None, idusuario=None, incluir_apoyo_recupero=False):
    ids = [int(item) for item in (idcarteras or []) if str(item).strip()]
    if not ids:
        return [obtener_resumen_control_horario(
            fecha=fecha,
            idcartera=None,
            idusuario=idusuario,
            incluir_apoyo_recupero=incluir_apoyo_recupero
        )]

    return [
        obtener_resumen_control_horario(
            fecha=fecha,
            idcartera=idcartera,
            idusuario=idusuario,
            incluir_apoyo_recupero=incluir_apoyo_recupero
        )
        for idcartera in ids
    ]


def construir_resumen_export(detalle):
    resumen = {}

    for row in detalle:
        idcartera = texto_export(row, ["IDCARTERA", "idcartera"], "")
        cartera = texto_export(row, ["CARTERA", "cartera"], f"Cartera {idcartera}")
        key = str(idcartera)

        item = resumen.setdefault(key, {
            "Cartera": cartera,
            "Gestiones": 0,
            "CEF": 0,
            "% CEF": 0,
            "PDP generado": 0,
            "Proyectado": 0,
            "Pago": 0,
            "Avance": 0,
            "Pendiente": 0,
            "Criticos": 0,
            "_agentes": set(),
        })

        gestiones = numero_export(row, ["GESTIONES", "gestiones", "TOTAL_GESTIONES"])
        cef = numero_export(row, ["CEF", "cef"])
        proyectado = numero_export(row, ["PROYECTADO", "proyectado", "PROYECTADO_HOY"])
        pago = numero_export(row, ["PAGO", "pago", "PAGO_HOY"])
        pendiente = numero_export(row, ["PENDIENTE", "pendiente", "PENDIENTE_HOY"])

        item["Gestiones"] += gestiones
        item["CEF"] += cef
        item["PDP generado"] += numero_export(row, ["PDP_GEN", "pdp_gen", "PDP_GENERADO", "MONTO_GENERADO"])
        item["Proyectado"] += proyectado
        item["Pago"] += pago
        item["Pendiente"] += pendiente
        if pendiente > 0 and pago <= 0:
            item["Criticos"] += 1

        idusuario = texto_export(row, ["IDUSUARIO", "idusuario"], "")
        if idusuario and (gestiones > 0 or cef > 0 or proyectado > 0 or pago > 0 or pendiente > 0):
            item["_agentes"].add(str(idusuario))

    data = []
    for item in resumen.values():
        item["Agentes activos"] = len(item.pop("_agentes"))
        item["% CEF"] = pct_export(item["CEF"], item["Gestiones"])
        item["Avance"] = pct_export(item["Pago"], item["Proyectado"])
        data.append(item)

    return data


def construir_detalle_agentes_export(detalle):
    agentes = {}

    for row in detalle:
        idusuario = texto_export(row, ["IDUSUARIO", "idusuario"], "")
        agente = texto_export(row, ["AGENTE", "agente"], f"Agente {idusuario}")
        if not idusuario and not agente:
            continue

        key = str(idusuario or agente)
        item = agentes.setdefault(key, {
            "Id usuario": idusuario,
            "Agente": agente,
            "Tipo usuario": texto_export(row, ["TIPOUSUARIO", "tipousuario"], ""),
            "Cartera": texto_export(row, ["CARTERA", "cartera"], ""),
            "Cartera usuario": texto_export(row, ["CARTERA_USUARIO", "cartera_usuario"], ""),
            "Gestiones": 0,
            "Clientes gestion": 0,
            "CEF": 0,
            "Clientes CEF": 0,
            "% CEF": 0,
            "PDP generado": 0,
            "Proyectado": 0,
            "Pago": 0,
            "Avance": 0,
            "Pendiente": 0,
            "_fuentes_clientes_unicos": set(),
        })

        item["Gestiones"] += numero_export(row, ["GESTIONES", "gestiones", "TOTAL_GESTIONES"])
        fuente_clientes = (
            str(idusuario or agente),
            str(texto_export(row, ["IDCARTERA_ORIGINAL", "idcartera_original", "IDCARTERA", "idcartera"], "")),
        )
        if fuente_clientes not in item["_fuentes_clientes_unicos"]:
            item["Clientes gestion"] += numero_export(row, ["CLIENTES_UNICOS_GESTION", "clientes_unicos_gestion"])
            item["Clientes CEF"] += numero_export(row, ["CLIENTES_UNICOS_CEF", "clientes_unicos_cef"])
            item["_fuentes_clientes_unicos"].add(fuente_clientes)
        item["CEF"] += numero_export(row, ["CEF", "cef"])
        item["PDP generado"] += numero_export(row, ["PDP_GEN", "pdp_gen", "PDP_GENERADO", "MONTO_GENERADO"])
        item["Proyectado"] += numero_export(row, ["PROYECTADO", "proyectado", "PROYECTADO_HOY"])
        item["Pago"] += numero_export(row, ["PAGO", "pago", "PAGO_HOY"])
        item["Pendiente"] += numero_export(row, ["PENDIENTE", "pendiente", "PENDIENTE_HOY"])
        item["% CEF"] = pct_export(item["CEF"], item["Gestiones"])
        item["Avance"] = pct_export(item["Pago"], item["Proyectado"])

    data = []
    for item in agentes.values():
        item.pop("_fuentes_clientes_unicos", None)
        data.append(item)

    return data


def construir_detalle_base_export(detalle):
    return [
        {
            "Id usuario": texto_export(row, ["IDUSUARIO", "idusuario"], ""),
            "Usuario": texto_export(row, ["USUARIO", "usuario"], ""),
            "Agente": texto_export(row, ["AGENTE", "agente"], ""),
            "Tipo usuario": texto_export(row, ["TIPOUSUARIO", "tipousuario"], ""),
            "Cartera": texto_export(row, ["CARTERA", "cartera"], ""),
            "Id cartera original": texto_export(row, ["IDCARTERA_ORIGINAL", "idcartera_original"], ""),
            "Cartera usuario": texto_export(row, ["CARTERA_USUARIO", "cartera_usuario"], ""),
            "Gestiones": numero_export(row, ["GESTIONES", "gestiones", "TOTAL_GESTIONES"]),
            "Clientes mes": numero_export(row, ["CLIENTES_GESTIONADOS_MES", "clientes_gestionados_mes"]),
            "Clientes gestion": numero_export(row, ["CLIENTES_UNICOS_GESTION", "clientes_unicos_gestion"]),
            "CEF": numero_export(row, ["CEF", "cef"]),
            "Clientes CEF": numero_export(row, ["CLIENTES_UNICOS_CEF", "clientes_unicos_cef"]),
            "CNE": numero_export(row, ["CNE", "cne"]),
            "NOC": numero_export(row, ["NOC", "noc"]),
            "Q PDP": numero_export(row, ["Q_PDP_GEN", "q_pdp_gen", "Q_PDP"]),
            "PDP generado": numero_export(row, ["PDP_GEN", "pdp_gen", "PDP_GENERADO", "MONTO_GENERADO"]),
            "Proyectado": numero_export(row, ["PROYECTADO", "proyectado", "PROYECTADO_HOY"]),
            "Pago": numero_export(row, ["PAGO", "pago", "PAGO_HOY"]),
            "Pendiente": numero_export(row, ["PENDIENTE", "pendiente", "PENDIENTE_HOY"]),
        }
        for row in detalle
    ]


def construir_agente_hora_export(rows):
    return [
        {
            "Hora": texto_export(row, ["HORA", "hora", "TRAMO", "tramo"], ""),
            "Id usuario": texto_export(row, ["IDUSUARIO", "idusuario"], ""),
            "Agente": texto_export(row, ["AGENTE", "agente"], ""),
            "Tipo usuario": texto_export(row, ["TIPOUSUARIO", "tipousuario"], ""),
            "Cartera": texto_export(row, ["CARTERA", "cartera"], ""),
            "Gestiones": numero_export(row, ["GESTIONES", "gestiones", "TOTAL_GESTIONES"]),
            "CEF": numero_export(row, ["CEF", "cef"]),
            "Q PDP": numero_export(row, ["Q_PDP_GEN", "q_pdp_gen", "Q_PDP"]),
            "PDP generado": numero_export(row, ["PDP_GEN", "pdp_gen", "PDP_GENERADO", "MONTO_GENERADO"]),
            "Pago": numero_export(row, ["PAGO", "pago", "PAGO_HOY"]),
        }
        for row in rows
    ]


def generar_excel_control_horario(fecha=None, idcarteras=None, idusuario=None, incluir_apoyo_recupero=False):
    resultados = filas_control_para_exportar(
        fecha=fecha,
        idcarteras=idcarteras,
        idusuario=idusuario,
        incluir_apoyo_recupero=incluir_apoyo_recupero
    )
    detalle = []
    agente_hora = []
    for data in resultados:
        detalle.extend(data.get("detalle") or [])
        agente_hora.extend(data.get("agente_hora") or [])

    fecha_base = fecha_desde_parametro(fecha)
    parametros = [{
        "Fecha": fecha_base.isoformat(),
        "Carteras": ", ".join(str(x) for x in (idcarteras or [])) or "Todas",
        "Id usuario": idusuario or "Todos",
        "Incluye apoyo operativo": "Si" if incluir_apoyo_recupero else "No",
        "Generado": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }]

    output = BytesIO()
    hojas = {
        "Parametros": parametros,
        "Resumen_Cartera": construir_resumen_export(detalle),
        "Detalle_Agentes": construir_detalle_agentes_export(detalle),
        "Detalle_Base": construir_detalle_base_export(detalle),
        "Agente_Hora": construir_agente_hora_export(agente_hora),
    }

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        for nombre, filas in hojas.items():
            df = pd.DataFrame(filas)
            df.to_excel(writer, index=False, sheet_name=nombre)

        for sheet in writer.sheets.values():
            sheet.freeze_panes = "A2"
            for column_cells in sheet.columns:
                max_length = max(
                    len(str(cell.value)) if cell.value is not None else 0
                    for cell in column_cells
                )
                sheet.column_dimensions[column_cells[0].column_letter].width = min(max_length + 2, 42)

    output.seek(0)
    nombre_archivo = f"Gestion_Recupero_{fecha_base.strftime('%Y%m%d')}_{datetime.now().strftime('%H%M')}.xlsx"
    return output, nombre_archivo


def ejecutar_sp_control_horario(cursor, fecha=None, idcartera=None, idusuario=None):
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

    return resultsets


def agregar_valor_matriz(item, row, fecha_key):
    valores_dia = item["dias"].setdefault(fecha_key, {
        "generacion": 0,
        "recupero": 0,
    })

    valores_dia["generacion"] += float(valor_por_claves(row, [
        "PDP_GEN",
        "pdp_gen",
        "PDP_GENERADO",
        "pdp_generado",
        "MONTO_GENERADO",
        "MONTO_PDP_GENERADO",
        "PROYECTADO",
    ]) or 0)
    valores_dia["recupero"] += float(valor_por_claves(row, [
        "PAGO",
        "pago",
        "PAGO_HOY",
        "pago_hoy",
        "MONTO_PAGO",
    ]) or 0)


def rango_mes(fecha_base):
    inicio = date(fecha_base.year, fecha_base.month, 1)
    fin = date(fecha_base.year, fecha_base.month, monthrange(fecha_base.year, fecha_base.month)[1])
    return inicio, fin


def agregar_movimiento_matriz(agentes, row, fecha_key):
    id_agente = row.get("IDUSUARIO")
    if id_agente in (None, ""):
        return

    key = str(id_agente)
    item = agentes.setdefault(key, {
        "idusuario": id_agente,
        "agente": row.get("AGENTE") or f"Agente {id_agente}",
        "idcartera": row.get("IDCARTERA"),
        "idcartera_original": row.get("IDCARTERA"),
        "ids_cartera": str(row.get("IDCARTERA") or ""),
        "cartera": row.get("CARTERA") or "",
        "dias": {},
        "mes_anterior": {
            "generacion": 0,
            "recupero": 0,
            "proyectado": 0,
        },
        "mes_anterior_total": {
            "generacion": 0,
            "recupero": 0,
            "proyectado": 0,
        },
    })

    if item.get("cartera") and row.get("CARTERA") and item["cartera"] != row["CARTERA"]:
        item["cartera"] = "Varias carteras"

    valores = item["dias"].setdefault(fecha_key, {
        "generacion": 0,
        "recupero": 0,
        "proyectado": 0,
    })
    valores["generacion"] += float(row.get("GENERACION") or 0)
    valores["recupero"] += float(row.get("RECUPERO") or 0)
    valores["proyectado"] += float(row.get("PROYECTADO") or 0)


def obtener_matriz_mensual_control_horario(fecha=None, idcartera=None, idusuario=None, incluir_apoyo_recupero=False):
    fecha_base = fecha_desde_parametro(fecha)
    ultimo_dia = monthrange(fecha_base.year, fecha_base.month)[1]
    fechas_mes = [
        date(fecha_base.year, fecha_base.month, dia)
        for dia in range(1, ultimo_dia + 1)
    ]

    primer_dia_mes = date(fecha_base.year, fecha_base.month, 1)
    ultimo_mes_anterior = primer_dia_mes - timedelta(days=1)
    dia_comparativo = min(fecha_base.day, ultimo_mes_anterior.day)
    fecha_mes_anterior = date(ultimo_mes_anterior.year, ultimo_mes_anterior.month, dia_comparativo)
    inicio_mes_anterior = date(ultimo_mes_anterior.year, ultimo_mes_anterior.month, 1)
    fin_mes_anterior = ultimo_mes_anterior
    fin_mes_anterior_exclusivo = fin_mes_anterior + timedelta(days=1)
    inicio_mes, fin_mes = rango_mes(fecha_base)
    fin_mes_exclusivo = fin_mes + timedelta(days=1)
    fecha_mes_anterior_fin = fecha_mes_anterior + timedelta(days=1)

    try:
        agentes = {}

        filtros = [
            "G.IDCARTERA NOT IN (106, 100, 108, 110, 104, 141, 125, 119, 127, 121, 120, 130, 98, 122)",
            "G.IDCARTERA IS NOT NULL",
            "G.IDUSUARIO IS NOT NULL",
            "UPPER(LTRIM(RTRIM(ISNULL(U.ESTADO, '')))) <> 'E'",
        ]
        params_extra = []

        if idcartera not in (None, ""):
            filtros.append("G.IDCARTERA = ?")
            params_extra.append(idcartera)

        if idusuario not in (None, ""):
            filtros.append("G.IDUSUARIO = ?")
            params_extra.append(idusuario)

        where_base = " AND ".join(filtros)
        filtro_perfiles = (
            "UPPER(LTRIM(RTRIM(ISNULL(U.TIPOUSUARIO, '')))) IN ('GESTOR', 'ADM', 'SUPERVISOR', 'JEFE')"
            if incluir_apoyo_recupero else
            "UPPER(LTRIM(RTRIM(ISNULL(U.TIPOUSUARIO, '')))) = 'GESTOR'"
        )
        where_perfiles = f"{where_base} AND {filtro_perfiles}"
        where_perfiles_activos = f"{where_perfiles} AND UPPER(LTRIM(RTRIM(ISNULL(CL.ESTADO, '')))) IN ('A', 'N')"

        query = f"""
            WITH MOVIMIENTOS AS (
                SELECT
                    G.IDUSUARIO,
                    CONCAT(U.USUARIO, ' - ', U.Nombres, ' ', U.Apellidos) AS AGENTE,
                    G.IDCARTERA,
                    CAST(C.FECHAGENERO AS DATE) AS FECHA,
                    SUM(ISNULL(C.MONTO, 0)) AS GENERACION,
                    CAST(0 AS DECIMAL(18,2)) AS RECUPERO,
                    CAST(0 AS DECIMAL(18,2)) AS PROYECTADO
                FROM SISCOB.DBO.COMPROMISO C WITH(NOLOCK)
                LEFT JOIN SISCOB.DBO.GESTION G WITH(NOLOCK)
                    ON G.IDGESTION = C.IDGESTION
                LEFT JOIN SISCOB.DBO.USUARIO U WITH(NOLOCK)
                    ON U.IDUSUARIO = G.IDUSUARIO
                LEFT JOIN SISCOB.DBO.CLIENTE CL WITH(NOLOCK)
                    ON CL.IDCLIENTE = G.IDCLIENTE
                WHERE
                    C.FECHAGENERO >= ?
                    AND C.FECHAGENERO < ?
                    AND ISNULL(C.MONTO, 0) > 0
                    AND {where_perfiles_activos}
                GROUP BY
                    G.IDUSUARIO,
                    CONCAT(U.USUARIO, ' - ', U.Nombres, ' ', U.Apellidos),
                    G.IDCARTERA,
                    CAST(C.FECHAGENERO AS DATE)

                UNION ALL

                SELECT
                    G.IDUSUARIO,
                    CONCAT(U.USUARIO, ' - ', U.Nombres, ' ', U.Apellidos) AS AGENTE,
                    G.IDCARTERA,
                    CAST(C.FECHAPAGO AS DATE) AS FECHA,
                    CAST(0 AS DECIMAL(18,2)) AS GENERACION,
                    SUM(ISNULL(C.MONTOPAGADO, 0)) AS RECUPERO,
                    CAST(0 AS DECIMAL(18,2)) AS PROYECTADO
                FROM SISCOB.DBO.COMPROMISO C WITH(NOLOCK)
                LEFT JOIN SISCOB.DBO.GESTION G WITH(NOLOCK)
                    ON G.IDGESTION = C.IDGESTION
                LEFT JOIN SISCOB.DBO.USUARIO U WITH(NOLOCK)
                    ON U.IDUSUARIO = G.IDUSUARIO
                LEFT JOIN SISCOB.DBO.CLIENTE CL WITH(NOLOCK)
                    ON CL.IDCLIENTE = G.IDCLIENTE
                WHERE
                    C.FECHAPAGO >= ?
                    AND C.FECHAPAGO < ?
                    AND ISNULL(C.MONTOPAGADO, 0) > 0
                    AND {where_perfiles}
                GROUP BY
                    G.IDUSUARIO,
                    CONCAT(U.USUARIO, ' - ', U.Nombres, ' ', U.Apellidos),
                    G.IDCARTERA,
                    CAST(C.FECHAPAGO AS DATE)

                UNION ALL

                SELECT
                    G.IDUSUARIO,
                    CONCAT(U.USUARIO, ' - ', U.Nombres, ' ', U.Apellidos) AS AGENTE,
                    G.IDCARTERA,
                    CAST(C.FECHACOMPROMISO AS DATE) AS FECHA,
                    CAST(0 AS DECIMAL(18,2)) AS GENERACION,
                    CAST(0 AS DECIMAL(18,2)) AS RECUPERO,
                    SUM(ISNULL(C.MONTO, 0)) AS PROYECTADO
                FROM SISCOB.DBO.COMPROMISO C WITH(NOLOCK)
                LEFT JOIN SISCOB.DBO.GESTION G WITH(NOLOCK)
                    ON G.IDGESTION = C.IDGESTION
                LEFT JOIN SISCOB.DBO.USUARIO U WITH(NOLOCK)
                    ON U.IDUSUARIO = G.IDUSUARIO
                LEFT JOIN SISCOB.DBO.CLIENTE CL WITH(NOLOCK)
                    ON CL.IDCLIENTE = G.IDCLIENTE
                WHERE
                    C.FECHACOMPROMISO >= ?
                    AND C.FECHACOMPROMISO < ?
                    AND ISNULL(C.MONTO, 0) > 0
                    AND {where_perfiles_activos}
                GROUP BY
                    G.IDUSUARIO,
                    CONCAT(U.USUARIO, ' - ', U.Nombres, ' ', U.Apellidos),
                    G.IDCARTERA,
                    CAST(C.FECHACOMPROMISO AS DATE)
            )
            SELECT
                IDUSUARIO,
                AGENTE,
                IDCARTERA,
                CASE
                    WHEN IDCARTERA = 112 THEN 'MIBANCO 1'
                    WHEN IDCARTERA = 143 THEN 'MIBANCO 2'
                    WHEN IDCARTERA = 135 THEN 'MIBANCO VIGENTE'
                    WHEN IDCARTERA = 124 THEN 'COMPARTAMOS CASTIGO INDIVIDUAL'
                    WHEN IDCARTERA = 144 THEN 'COMPARTAMOS CASTIGO GRUPAL'
                    WHEN IDCARTERA = 126 THEN 'COMPARTAMOS VIGENTE INDIVIDUAL'
                    WHEN IDCARTERA = 128 THEN 'COMPARTAMOS VIGENTE CCM'
                    WHEN IDCARTERA = 133 THEN 'COMPARTAMOS VIGENTE GRUPAL / CSM'
                    WHEN IDCARTERA = 117 THEN 'INTERBANK'
                    WHEN IDCARTERA = 132 THEN 'FINANCIERA OH'
                    WHEN IDCARTERA = 137 THEN 'INTERBANK CEDIDA'
                    WHEN IDCARTERA = 148 THEN 'FINANCIERA OH PROPIA'
                    ELSE CONCAT('Cartera ', IDCARTERA)
                END AS CARTERA,
                FECHA,
                SUM(GENERACION) AS GENERACION,
                SUM(RECUPERO) AS RECUPERO,
                SUM(PROYECTADO) AS PROYECTADO
            FROM MOVIMIENTOS
            GROUP BY
                IDUSUARIO,
                AGENTE,
                IDCARTERA,
                FECHA
            ORDER BY
                AGENTE,
                FECHA
        """

        params = [
            inicio_mes,
            fin_mes_exclusivo,
            *params_extra,
            inicio_mes,
            fin_mes_exclusivo,
            *params_extra,
            inicio_mes,
            fin_mes_exclusivo,
            *params_extra,
        ]

        with engine_siscob.connect() as conn:
            for row in conn.exec_driver_sql(query, tuple(params)).mappings().all():
                row = serialize_row_mapping(row)
                agregar_movimiento_matriz(agentes, row, str(row.get("FECHA"))[:10])

            query_anterior = f"""
            WITH MOVIMIENTOS AS (
                SELECT
                    G.IDUSUARIO,
                    CONCAT(U.USUARIO, ' - ', U.Nombres, ' ', U.Apellidos) AS AGENTE,
                    G.IDCARTERA,
                    SUM(ISNULL(C.MONTO, 0)) AS GENERACION,
                    CAST(0 AS DECIMAL(18,2)) AS RECUPERO,
                    CAST(0 AS DECIMAL(18,2)) AS PROYECTADO
                FROM SISCOB.DBO.COMPROMISO C WITH(NOLOCK)
                LEFT JOIN SISCOB.DBO.GESTION G WITH(NOLOCK)
                    ON G.IDGESTION = C.IDGESTION
                LEFT JOIN SISCOB.DBO.USUARIO U WITH(NOLOCK)
                    ON U.IDUSUARIO = G.IDUSUARIO
                LEFT JOIN SISCOB.DBO.CLIENTE CL WITH(NOLOCK)
                    ON CL.IDCLIENTE = G.IDCLIENTE
                WHERE
                    C.FECHAGENERO >= ?
                    AND C.FECHAGENERO < ?
                    AND ISNULL(C.MONTO, 0) > 0
                    AND {where_perfiles_activos}
                GROUP BY
                    G.IDUSUARIO,
                    CONCAT(U.USUARIO, ' - ', U.Nombres, ' ', U.Apellidos),
                    G.IDCARTERA

                UNION ALL

                SELECT
                    G.IDUSUARIO,
                    CONCAT(U.USUARIO, ' - ', U.Nombres, ' ', U.Apellidos) AS AGENTE,
                    G.IDCARTERA,
                    CAST(0 AS DECIMAL(18,2)) AS GENERACION,
                    SUM(ISNULL(C.MONTOPAGADO, 0)) AS RECUPERO,
                    CAST(0 AS DECIMAL(18,2)) AS PROYECTADO
                FROM SISCOB.DBO.COMPROMISO C WITH(NOLOCK)
                LEFT JOIN SISCOB.DBO.GESTION G WITH(NOLOCK)
                    ON G.IDGESTION = C.IDGESTION
                LEFT JOIN SISCOB.DBO.USUARIO U WITH(NOLOCK)
                    ON U.IDUSUARIO = G.IDUSUARIO
                LEFT JOIN SISCOB.DBO.CLIENTE CL WITH(NOLOCK)
                    ON CL.IDCLIENTE = G.IDCLIENTE
                WHERE
                    C.FECHAPAGO >= ?
                    AND C.FECHAPAGO < ?
                    AND ISNULL(C.MONTOPAGADO, 0) > 0
                    AND {where_perfiles}
                GROUP BY
                    G.IDUSUARIO,
                    CONCAT(U.USUARIO, ' - ', U.Nombres, ' ', U.Apellidos),
                    G.IDCARTERA

                UNION ALL

                SELECT
                    G.IDUSUARIO,
                    CONCAT(U.USUARIO, ' - ', U.Nombres, ' ', U.Apellidos) AS AGENTE,
                    G.IDCARTERA,
                    CAST(0 AS DECIMAL(18,2)) AS GENERACION,
                    CAST(0 AS DECIMAL(18,2)) AS RECUPERO,
                    SUM(ISNULL(C.MONTO, 0)) AS PROYECTADO
                FROM SISCOB.DBO.COMPROMISO C WITH(NOLOCK)
                LEFT JOIN SISCOB.DBO.GESTION G WITH(NOLOCK)
                    ON G.IDGESTION = C.IDGESTION
                LEFT JOIN SISCOB.DBO.USUARIO U WITH(NOLOCK)
                    ON U.IDUSUARIO = G.IDUSUARIO
                LEFT JOIN SISCOB.DBO.CLIENTE CL WITH(NOLOCK)
                    ON CL.IDCLIENTE = G.IDCLIENTE
                WHERE
                    C.FECHACOMPROMISO >= ?
                    AND C.FECHACOMPROMISO < ?
                    AND ISNULL(C.MONTO, 0) > 0
                    AND {where_perfiles_activos}
                GROUP BY
                    G.IDUSUARIO,
                    CONCAT(U.USUARIO, ' - ', U.Nombres, ' ', U.Apellidos),
                    G.IDCARTERA
            )
            SELECT
                IDUSUARIO,
                AGENTE,
                IDCARTERA,
                SUM(GENERACION) AS GENERACION,
                SUM(RECUPERO) AS RECUPERO,
                SUM(PROYECTADO) AS PROYECTADO
            FROM MOVIMIENTOS
            GROUP BY
                IDUSUARIO,
                AGENTE,
                IDCARTERA
            ORDER BY
                AGENTE
        """
            params_anterior = [
                inicio_mes_anterior,
                fecha_mes_anterior_fin,
                *params_extra,
                inicio_mes_anterior,
                fecha_mes_anterior_fin,
                *params_extra,
                inicio_mes_anterior,
                fecha_mes_anterior_fin,
                *params_extra,
            ]

            for row in conn.exec_driver_sql(query_anterior, tuple(params_anterior)).mappings().all():
                row = serialize_row_mapping(row)
                key = str(row.get("IDUSUARIO") or "")
                if not key:
                    continue
                if key not in agentes:
                    continue
                item = agentes[key]
                item["mes_anterior"]["generacion"] += float(row.get("GENERACION") or 0)
                item["mes_anterior"]["recupero"] += float(row.get("RECUPERO") or 0)
                item["mes_anterior"]["proyectado"] += float(row.get("PROYECTADO") or 0)

            query_anterior_total = query_anterior
            params_anterior_total = [
                inicio_mes_anterior,
                fin_mes_anterior_exclusivo,
                *params_extra,
                inicio_mes_anterior,
                fin_mes_anterior_exclusivo,
                *params_extra,
                inicio_mes_anterior,
                fin_mes_anterior_exclusivo,
                *params_extra,
            ]

            for row in conn.exec_driver_sql(query_anterior_total, tuple(params_anterior_total)).mappings().all():
                row = serialize_row_mapping(row)
                key = str(row.get("IDUSUARIO") or "")
                if not key:
                    continue
                if key not in agentes:
                    continue
                item = agentes[key]
                item["mes_anterior_total"]["generacion"] += float(row.get("GENERACION") or 0)
                item["mes_anterior_total"]["recupero"] += float(row.get("RECUPERO") or 0)
                item["mes_anterior_total"]["proyectado"] += float(row.get("PROYECTADO") or 0)

        return {
            "fecha": fecha_base.isoformat(),
            "mes": fecha_base.strftime("%Y-%m"),
            "fechas": [item.isoformat() for item in fechas_mes],
            "fecha_mes_anterior": fecha_mes_anterior.isoformat(),
            "agentes": sorted(
                agentes.values(),
                key=lambda item: str(item.get("agente") or "")
            ),
        }

    except Exception as exc:
        print("ERROR MATRIZ MENSUAL CONTROL HORARIO:", exc)
        raise
