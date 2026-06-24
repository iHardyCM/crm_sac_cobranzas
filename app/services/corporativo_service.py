from sqlalchemy import text
from app.core.db_siscob import engine_siscob


CARTERA_CASE = """
    CASE
        WHEN G.IDCARTERA = 112 THEN 'MIBANCO 1'
        WHEN G.IDCARTERA = 143 THEN 'MIBANCO 2'
        WHEN G.IDCARTERA = 135 THEN 'MIBANCO VIGENTE'
        WHEN G.IDCARTERA = 124 THEN 'COMPARTAMOS BANCO - CASTIGO INDIVIDUAL'
        WHEN G.IDCARTERA = 126 THEN 'COMPARTAMOS BANCO - VIGENTE INDIVIDUAL'
        WHEN G.IDCARTERA = 128 THEN 'COMPARTAMOS BANCO - VIGENTE CCM'
        WHEN G.IDCARTERA = 133 THEN 'COMPARTAMOS BANCO - VIGENTE GRUPAL / CSM'
        WHEN G.IDCARTERA = 144 THEN 'COMPARTAMOS BANCO - CASTIGO GRUPAL'
        WHEN G.IDCARTERA = 132 THEN 'FINANCIERA OH'
        WHEN G.IDCARTERA = 117 THEN 'INTERBANK'
        WHEN G.IDCARTERA = 137 THEN 'INTERBANK CEDIDA'
        WHEN G.IDCARTERA = 148 THEN 'FINANCIERA OH PROPIA'
        ELSE 'OTROS'
    END
"""


def normalizar_idcarteras(idcartera=None):
    if idcartera is None:
        return []

    valores = idcartera if isinstance(idcartera, (list, tuple, set)) else [idcartera]
    ids = []

    for valor in valores:
        if valor in (None, ""):
            continue
        ids.append(int(valor))

    return sorted(set(ids))


def construir_filtro_carteras(idcartera=None):
    ids = normalizar_idcarteras(idcartera)

    if not ids:
        return "", {}

    params = {f"idcartera_{i}": valor for i, valor in enumerate(ids)}
    placeholders = ", ".join(f":idcartera_{i}" for i in range(len(ids)))

    return f" AND G.IDCARTERA IN ({placeholders})", params


def obtener_resumen_corporativo(fecha_desde=None, fecha_hasta=None, idcartera=None):

    data = []

    try:
        with engine_siscob.connect() as conn:
            filtro_carteras, params_carteras = construir_filtro_carteras(idcartera)

            query = text(f"""
                WITH BASE AS (
                    SELECT
                        G.IDCARTERA,

                        CARTERA = {CARTERA_CASE},

                        C.IDCOMPROMISO,
                        C.FECHAGENERO,
                        C.FECHACOMPROMISO,
                        C.MONTO,
                        C.MONTOPAGADO,
                        CASE WHEN CAST(C.FECHACOMPROMISO AS DATE) = CAST(GETDATE() AS DATE) THEN C.MONTO ELSE 0 END MONTO_HOY,
                        CASE WHEN CAST(C.FECHACOMPROMISO AS DATE) = CAST(GETDATE() AS DATE) THEN ISNULL(C.MONTOPAGADO, 0) ELSE 0 END MONTO_PAGADO_HOY,

                        ESTADO =
                            CASE
                                WHEN ISNULL(C.MONTOPAGADO, 0) > 0 THEN 'Cumplida'

                                WHEN CAST(C.FECHACOMPROMISO AS DATE) = CAST(GETDATE() AS DATE)
                                     AND ISNULL(C.MONTOPAGADO, 0) = 0 THEN 'Hoy'

                                WHEN CAST(C.FECHACOMPROMISO AS DATE) < CAST(GETDATE() AS DATE)
                                     AND ISNULL(C.MONTOPAGADO, 0) = 0 THEN 'Caída'

                                WHEN CAST(C.FECHACOMPROMISO AS DATE) > CAST(GETDATE() AS DATE)
                                     AND ISNULL(C.MONTOPAGADO, 0) = 0 THEN 'Vigente'
                            END

                    FROM SISCOB.DBO.COMPROMISO C WITH(NOLOCK)

                    LEFT JOIN SISCOB.DBO.GESTION G WITH(NOLOCK)
                        ON G.IDGESTION = C.IDGESTION
                    
                    WHERE 
                        CAST(C.FECHAGENERO AS DATE) BETWEEN 
                            ISNULL(:fecha_desde, DATEADD(MONTH, -1, DATEADD(DAY, 1, EOMONTH(GETDATE()))))
                            AND ISNULL(:fecha_hasta, CAST(GETDATE() AS DATE))
                        AND G.IDCARTERA NOT IN (106, 100, 108, 110, 104, 141, 125,119, 127, 121, 120,130, 98, 122)
                        AND C.MONTO > 0
                        AND G.IDCARTERA IS NOT NULL
                        {filtro_carteras}
                )

                SELECT
                    IDCARTERA,
                    CARTERA,

                    COUNT(1) AS total_promesas,

                    SUM(ISNULL(MONTO, 0)) AS monto_pdp,
                    SUM(ISNULL(MONTO_PAGADO_HOY, 0)) AS monto_pagado,
                    SUM(ISNULL(MONTO_HOY, 0)) AS monto_hoy,
                    SUM(ISNULL(MONTO_HOY, 0)) - SUM(ISNULL(MONTO_PAGADO_HOY, 0)) AS monto_proyectado,

                    SUM(CASE WHEN ESTADO = 'Hoy' THEN 1 ELSE 0 END) AS pdp_hoy,
                    SUM(CASE WHEN ESTADO = 'Caída' THEN 1 ELSE 0 END) AS pdp_caida,
                    SUM(CASE WHEN ESTADO = 'Vigente' THEN 1 ELSE 0 END) AS pdp_vigente,
                    SUM(CASE WHEN ESTADO = 'Cumplida' THEN 1 ELSE 0 END) AS pdp_cumplida,

                    CAST(
                        100.0 * SUM(ISNULL(MONTO_PAGADO_HOY, 0))
                        / NULLIF(SUM(ISNULL(MONTO_HOY, 0)), 0)
                        AS DECIMAL(10,2)
                    ) AS eficacia,

                    CAST(
                        100.0 * (SUM(ISNULL(MONTO_HOY, 0))-SUM(ISNULL(MONTO_PAGADO_HOY, 0)))
                        / NULLIF(SUM(ISNULL(MONTO_HOY, 0)), 0)
                        AS DECIMAL(10,2)
                    ) AS tasa_caida,

                    CAST(
                        100.0 * SUM(ISNULL(MONTO_PAGADO_HOY, 0))
                        / NULLIF(SUM(ISNULL(MONTO_HOY, 0)), 0)
                        AS DECIMAL(10,2)
                    ) AS calidad

                FROM BASE

                GROUP BY
                    IDCARTERA,
                    CARTERA

                ORDER BY
                    total_promesas DESC;
            """)

            params = {
                "fecha_desde": fecha_desde,
                "fecha_hasta": fecha_hasta
            }
            params.update(params_carteras)

            rows = conn.execute(query, params).fetchall()

            for r in rows:
                data.append({
                    "idcartera": r.IDCARTERA,
                    "cartera": r.CARTERA,

                    "total_promesas": int(r.total_promesas or 0),
                    "monto_pdp": float(r.monto_pdp or 0),
                    "monto_pagado": float(r.monto_pagado or 0),
                    "monto_hoy": float(r.monto_hoy or 0),
                    "monto_proyectado": float(r.monto_proyectado or 0),

                    "pdp_hoy": int(r.pdp_hoy or 0),
                    "pdp_caida": int(r.pdp_caida or 0),
                    "pdp_vigente": int(r.pdp_vigente or 0),
                    "pdp_cumplida": int(r.pdp_cumplida or 0),

                    "eficacia": float(r.eficacia or 0),
                    "tasa_caida": float(r.tasa_caida or 0),
                    "calidad": float(r.calidad or 0)
                })

    except Exception as e:
        print("ERROR REAL RESUMEN CORPORATIVO:", e)
        raise

    return data


def obtener_carteras_corporativo():
    data = []

    try:
        with engine_siscob.connect() as conn:
            query = text(f"""
                SELECT DISTINCT
                    G.IDCARTERA,
                    CARTERA = {CARTERA_CASE}
                FROM SISCOB.DBO.COMPROMISO C WITH(NOLOCK)
                LEFT JOIN SISCOB.DBO.GESTION G WITH(NOLOCK)
                    ON G.IDGESTION = C.IDGESTION
                WHERE
                    G.IDCARTERA NOT IN (106, 100, 108, 110, 104, 141, 125, 119, 127, 121, 120, 130, 98, 122)
                    AND C.MONTO > 0
                    AND G.IDCARTERA IS NOT NULL
                ORDER BY
                    CARTERA;
            """)

            rows = conn.execute(query).fetchall()

            for r in rows:
                data.append({
                    "idcartera": r.IDCARTERA,
                    "cartera": r.CARTERA
                })

    except Exception as e:
        print("ERROR REAL CARTERAS CORPORATIVO:", e)
        raise

    return data


def obtener_matriz_compromisos_corporativo(
    fecha_desde=None,
    fecha_hasta=None,
    idcartera=None,
    solo_hoy=False
):
    data = []

    try:
        with engine_siscob.connect() as conn:
            filtro_carteras, params_carteras = construir_filtro_carteras(idcartera)

            query = text(f"""
                SELECT
                    C.IDGESTION AS idgestion,
                    C.IDCOMPROMISO AS idcompromiso,
                    C.FECHAGENERO AS fecha_genero,
                    CAST(C.FECHACOMPROMISO AS DATE) AS fecha_compromiso,

                    G.IDCARTERA AS idcartera,
                    CARTERA = {CARTERA_CASE},

                    CONCAT(U.USUARIO,' - ',U.Nombres,' ',U.Apellidos) AS agente,
                    CL.NOMBRECLIENTE AS cliente,
                    G.DNI AS dni,
                    G.TELEFONO AS telefono,
                    C.NUMOPERACION AS num_operacion,

                    C.MONTO AS monto_pdp,
                    C.MONTOPAGADO AS monto_pagado,
                    CASE
                        WHEN CAST(C.FECHACOMPROMISO AS DATE) = CAST(GETDATE() AS DATE)
                        THEN ISNULL(C.MONTO, 0)
                        ELSE 0
                    END AS monto_proyectado,
                    CASE
                        WHEN CAST(C.FECHACOMPROMISO AS DATE) = CAST(GETDATE() AS DATE)
                        THEN ISNULL(C.MONTO, 0)
                        ELSE 0
                    END AS monto_hoy,
                    CASE
                        WHEN CAST(C.FECHACOMPROMISO AS DATE) = CAST(GETDATE() AS DATE)
                        THEN ISNULL(C.MONTOPAGADO, 0)
                        ELSE 0
                    END AS monto_pagado_hoy,
                    CASE
                        WHEN CAST(C.FECHACOMPROMISO AS DATE) <= CAST(GETDATE() AS DATE)
                        THEN ISNULL(C.MONTO, 0) - ISNULL(C.MONTOPAGADO, 0)
                        ELSE 0
                    END AS monto_caido,

                    CASE
                        WHEN C.PAGADO = 'SI' THEN 'CUMPLIDA'
                        WHEN CAST(C.FECHACOMPROMISO AS DATE) = CAST(GETDATE() AS DATE) THEN 'HOY'
                        WHEN CAST(C.FECHACOMPROMISO AS DATE) < CAST(GETDATE() AS DATE) THEN 'CAIDA'
                        ELSE 'VIGENTE'
                    END AS estado,

                    C.PAGADO AS pagado,
                    C.TIPOPAGO AS tipo_pago,
                    C.FECHAPAGO AS fecha_pago,

                    ISNULL(INTENTOS.INTENTOS_HOY, 0) AS intentos_hoy,

                    G.GESTION AS gestion_compromiso,
                    UG.ULT_GESTION AS ult_gestion,
                    UG.ULT_FECHA AS ult_fecha,
                    UG.ULT_TIPOCONTACTO AS ult_tipocontacto,
                    UG.ULT_INDICADOR AS ult_indicador,
                    UG.ULT_AGENTE AS ult_agente

                FROM SISCOB.DBO.COMPROMISO C WITH(NOLOCK)

                LEFT JOIN SISCOB.DBO.GESTION G WITH(NOLOCK)
                    ON G.IDGESTION = C.IDGESTION

                LEFT JOIN SISCOB.DBO.USUARIO U WITH(NOLOCK)
                    ON U.IDUSUARIO = G.IDUSUARIO

                LEFT JOIN SISCOB.DBO.CLIENTE CL WITH(NOLOCK)
                    ON CL.IDCLIENTE = G.IDCLIENTE

                OUTER APPLY (
                    SELECT COUNT(1) AS INTENTOS_HOY
                    FROM SISCOB.DBO.GESTION GX WITH(NOLOCK)
                    WHERE
                        GX.IDCLIENTE = G.IDCLIENTE
                        AND CAST(GX.FECHA AS DATE) = CAST(GETDATE() AS DATE)
                ) INTENTOS

                OUTER APPLY (
                    SELECT TOP 1
                        G2.GESTION AS ULT_GESTION,
                        G2.FECHA AS ULT_FECHA,
                        I2.TIPOCONTACTO AS ULT_TIPOCONTACTO,
                        I2.DESCRIPCIONINDICADOR AS ULT_INDICADOR,
                        CONCAT(U2.USUARIO,' - ',U2.Nombres,' ',U2.Apellidos) AS ULT_AGENTE
                    FROM SISCOB.DBO.GESTION G2 WITH(NOLOCK)
                    LEFT JOIN SISCOB.DBO.USUARIO U2 WITH(NOLOCK)
                        ON U2.IDUSUARIO = G2.IDUSUARIO
                    LEFT JOIN SISCOB.DBO.INDICADOR I2 WITH(NOLOCK)
                        ON I2.IDINDICADOR = G2.IDINDICADOR
                    WHERE
                        G2.IDCLIENTE = G.IDCLIENTE
                    ORDER BY
                        G2.FECHA DESC
                ) UG

                WHERE
                    CAST(C.FECHAGENERO AS DATE) BETWEEN
                        ISNULL(:fecha_desde, DATEADD(MONTH, -1, DATEADD(DAY, 1, EOMONTH(GETDATE()))))
                        AND ISNULL(:fecha_hasta, CAST(GETDATE() AS DATE))
                    AND G.IDCARTERA NOT IN (106, 100, 108, 110, 104, 141, 125, 119, 127, 121, 120, 130, 98, 122)
                    AND C.MONTO > 0
                    AND G.IDCARTERA IS NOT NULL
                    {filtro_carteras}
                    AND (:solo_hoy = 0 OR CAST(C.FECHACOMPROMISO AS DATE) = CAST(GETDATE() AS DATE))

                ORDER BY
                    CARTERA,
                    agente,
                    C.FECHACOMPROMISO DESC;
            """)

            rows = conn.execute(query, {
                "fecha_desde": fecha_desde,
                "fecha_hasta": fecha_hasta,
                "solo_hoy": 1 if solo_hoy else 0,
                **params_carteras
            }).fetchall()

            data = [dict(r._mapping) for r in rows]

    except Exception as e:
        print("ERROR REAL MATRIZ CORPORATIVO:", e)
        raise

    return data
