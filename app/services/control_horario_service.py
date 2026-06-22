from calendar import monthrange
from datetime import date, datetime, timedelta
from decimal import Decimal

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

        if info.get("estado") == "E":
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


def obtener_matriz_mensual_control_horario(fecha=None, idcartera=None, idusuario=None):
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
            "UPPER(LTRIM(RTRIM(ISNULL(U.TIPOUSUARIO, '')))) = 'GESTOR'",
            "UPPER(LTRIM(RTRIM(ISNULL(U.ESTADO, '')))) <> 'E'",
        ]
        params_extra = []

        if idcartera not in (None, ""):
            filtros.append("G.IDCARTERA = ?")
            params_extra.append(idcartera)

        if idusuario not in (None, ""):
            filtros.append("G.IDUSUARIO = ?")
            params_extra.append(idusuario)

        where_extra = " AND ".join(filtros)

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
                WHERE
                    C.FECHAGENERO >= ?
                    AND C.FECHAGENERO < ?
                    AND ISNULL(C.MONTO, 0) > 0
                    AND {where_extra}
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
                WHERE
                    C.FECHAPAGO >= ?
                    AND C.FECHAPAGO < ?
                    AND ISNULL(C.MONTOPAGADO, 0) > 0
                    AND {where_extra}
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
                WHERE
                    C.FECHACOMPROMISO >= ?
                    AND C.FECHACOMPROMISO < ?
                    AND ISNULL(C.MONTO, 0) > 0
                    AND {where_extra}
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
                WHERE
                    C.FECHAGENERO >= ?
                    AND C.FECHAGENERO < ?
                    AND ISNULL(C.MONTO, 0) > 0
                    AND {where_extra}
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
                WHERE
                    C.FECHAPAGO >= ?
                    AND C.FECHAPAGO < ?
                    AND ISNULL(C.MONTOPAGADO, 0) > 0
                    AND {where_extra}
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
                WHERE
                    C.FECHACOMPROMISO >= ?
                    AND C.FECHACOMPROMISO < ?
                    AND ISNULL(C.MONTO, 0) > 0
                    AND {where_extra}
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
