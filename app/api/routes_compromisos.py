from fastapi import APIRouter
from app.services.compromisos_service import obtener_compromisos
from app.core.db_siscob import engine_siscob
from sqlalchemy import text

router = APIRouter()

TABLAS = {
    "compartamos_vigente": "TBL_COMPROMISOS_VIGENTE"
}

# 🔍 DETALLE
@router.get("/detalle/{id}")
def detalle(id: int):

    from app.core.db_siscob import engine_siscob
    from sqlalchemy import text

    query = text("""
        SELECT TOP 1
            C.IDCOMPROMISO,
            i.DescripcionIndicador,
			i.TipoContacto,
            G.FECHA AS FECHAGENERO,
            C.FECHACOMPROMISO,
            C.MONTO,
            C.MONEDA,
            C.NUMOPERACION,
            C.TIPOPAGO,
            C.MONTOPAGADO,

            G.GESTION,
            G.DNI,
            G.TELEFONO,
            G.IDCLIENTE,

            CL.NOMBRECLIENTE,

            CONCAT(U.USUARIO,' - ',U.Nombres,' ',U.Apellidos) AS AGENTE,

            -- 🔥 ÚLTIMA GESTIÓN REAL
            UG.GESTION AS ULT_GESTION,
            UG.FECHA AS ULT_FECHA,
            UG.AGENTE AS ULT_AGENTE,
            UG.TIPOCONTACTO AS ULT_CONTACTO,
			UG.DESCRIPCIONINDICADOR AS ULT_INDICADOR

        FROM SISCOB.DBO.COMPROMISO C WITH(NOLOCK)

        LEFT JOIN SISCOB.DBO.GESTION G WITH(NOLOCK)
            ON G.IDGESTION = C.IDGESTION

        LEFT JOIN SISCOB.DBO.CLIENTE CL WITH(NOLOCK)
            ON CL.IDCLIENTE = G.IDCLIENTE

        LEFT JOIN SISCOB.DBO.USUARIO U WITH(NOLOCK)
            ON U.IDUSUARIO = G.IDUSUARIO
                 
        LEFT JOIN SISCOB.DBO.INDICADOR I WITH(NOLOCK)
            ON I.IDINDICADOR = G.IDINDICADOR

        OUTER APPLY (
            SELECT TOP 1
                G2.GESTION,
                G2.FECHA,
                I2.TIPOCONTACTO,
				I2.DESCRIPCIONINDICADOR,
                CONCAT(U2.USUARIO,' - ',U2.Nombres,' ',U2.Apellidos) AS AGENTE
            FROM SISCOB.DBO.GESTION G2 WITH(NOLOCK)
            LEFT JOIN SISCOB.DBO.USUARIO U2 WITH(NOLOCK)
                ON U2.IDUSUARIO = G2.IDUSUARIO
			LEFT JOIN SISCOB.DBO.INDICADOR I2 WITH(NOLOCK)
				ON I2.IDINDICADOR = G2.IDINDICADOR
            WHERE G2.IDCLIENTE = G.IDCLIENTE
            ORDER BY G2.FECHA DESC
        ) UG

        WHERE C.IDCOMPROMISO = :id
    """)

    try:
        with engine_siscob.connect() as conn:
            r = conn.execute(query, {"id": id}).fetchone()

            if not r:
                return {"msg": "No encontrado"}
            
            # 🔥 DEBUG AQUÍ
            print("ULT:", r.ULT_GESTION, r.ULT_FECHA, r.ULT_AGENTE)

            return {
                "id": r.IDCOMPROMISO,
                "contacto": r.TipoContacto,
                "indicador": r.DescripcionIndicador,
                "cliente": r.NOMBRECLIENTE,
                "dni": r.DNI,
                "telefono": r.TELEFONO,
                "monto": float(r.MONTO),
                "moneda": r.MONEDA,
                "fecha_compromiso": str(r.FECHACOMPROMISO),
                "fecha_generado": str(r.FECHAGENERO),
                "monto_pagado": float(r.MONTOPAGADO or 0),
                "tipo_pago": r.TIPOPAGO,
                "operacion": r.NUMOPERACION,
                "gestion": r.GESTION,
                "agente": r.AGENTE,
                "ult_gestion": r.ULT_GESTION,
                "ult_fecha": str(r.ULT_FECHA) if r.ULT_FECHA else None,
                "ult_agente": r.ULT_AGENTE,
                "ult_tipocontacto": r.ULT_CONTACTO,
                "ult_indicador": r.ULT_INDICADOR
            }

    except Exception as e:
        print("ERROR DETALLE:", e)
        return {"msg": "Error interno"}


# 📊 LISTADO
@router.get("/{dni}")
def get_compromisos(dni: str):
    return {"data": obtener_compromisos(dni)}

@router.get("/supervisor/resumen")
def resumen_supervisor(dni: str):

    from app.core.db_siscob import engine_siscob
    from sqlalchemy import text

    try:

        # 🔥 1. OBTENER CARTERA DEL SUPERVISOR
        query_cartera = text("""
            SELECT IDCARTERA
            FROM SISCOB.DBO.USUARIO WITH(NOLOCK)
            WHERE LTRIM(RTRIM(USUARIO)) = LTRIM(RTRIM(:dni))
        """)

        with engine_siscob.connect() as conn:
            result_cartera = conn.execute(query_cartera, {"dni": dni}).fetchone()

        if not result_cartera:
            return {"ok": False, "msg": "Supervisor no encontrado"}

        cartera = result_cartera.IDCARTERA

        print("SUPERVISOR:", dni)
        print("CARTERA:", cartera)

        print("DNI RECIBIDO:", dni)
        print("RESULT CARTERA:", result_cartera)

        # 🔥 2. QUERY PRINCIPAL (YA SIN HARDCODE)
        query = text("""
            SELECT 
                CONCAT(U.USUARIO,' - ',U.Nombres,' ',U.Apellidos) AS AGENTE,

                COUNT(*) AS TOTAL,

                SUM(CASE 
                    WHEN CAST(C.FECHACOMPROMISO AS DATE) = CAST(GETDATE() AS DATE)
                    THEN 1 ELSE 0 END) AS HOY,

                SUM(CASE 
                    WHEN CAST(C.FECHACOMPROMISO AS DATE) < CAST(GETDATE() AS DATE) AND ISNULL(C.MONTOPAGADO,0) = 0
                    THEN 1 ELSE 0 END) AS CAIDA,

                SUM(CASE 
                    WHEN CAST(C.FECHACOMPROMISO AS DATE) > CAST(GETDATE() AS DATE) AND ISNULL(C.MONTOPAGADO,0) = 0
                    THEN 1 ELSE 0 END) AS VIGENTE,

                SUM(CASE 
                    WHEN PAGADO = 'SI'
                    THEN 1 ELSE 0 END) AS CUMPLIDA,

                SUM(C.MONTO) AS MONTO_TOTAL,

                SUM(CASE 
                    WHEN PAGADO = 'SI'
                    THEN MONTOPAGADO ELSE 0 END) AS MONTO_PAGADO

            FROM SISCOB.DBO.COMPROMISO C WITH(NOLOCK)

            LEFT JOIN SISCOB.DBO.GESTION G WITH(NOLOCK)
                ON G.IDGESTION = C.IDGESTION

            LEFT JOIN SISCOB.DBO.USUARIO U WITH(NOLOCK)
                ON U.IDUSUARIO = G.IDUSUARIO

            LEFT JOIN SISCOB.DBO.CLIENTE CL WITH(NOLOCK)
                ON CL.IDCLIENTE = G.IDCLIENTE

            WHERE 
                G.IDCARTERA = :cartera
                AND CAST(C.FECHAGENERO AS DATE) BETWEEN 
                    DATEADD(MONTH, -1, DATEADD(DAY, 1, EOMONTH(GETDATE()))) 
                    AND GETDATE()

            GROUP BY U.USUARIO, U.Nombres, U.Apellidos

            ORDER BY TOTAL DESC
        """)

        with engine_siscob.connect() as conn:
            result = conn.execute(query, {"cartera": cartera}).fetchall()

        data = [dict(r._mapping) for r in result]

        return {"ok": True, "data": data}

    except Exception as e:
        print("ERROR SUPERVISOR:", e)
        return {"ok": False, "error": str(e)}


@router.get("/agente/compromisos")
def compromisos_agente(agente: str):

    from app.core.db_siscob import engine_siscob
    from sqlalchemy import text

    query = """
        SELECT
            C.IDCOMPROMISO,
            CL.NOMBRECLIENTE AS CLIENTE,
            G.DNI,
            G.TELEFONO,
            C.MONTO,
            C.MontoPagado,
            CAST(C.FECHACOMPROMISO AS DATE) AS FECHA,

            CASE 
                WHEN PAGADO = 'SI' THEN 'CUMPLIDA'
                WHEN CAST(C.FECHACOMPROMISO AS DATE) = CAST(GETDATE() AS DATE) THEN 'HOY'
                WHEN CAST(C.FECHACOMPROMISO AS DATE) < GETDATE() THEN 'CAIDA'
                ELSE 'VIGENTE'
            END AS ESTADO,

            CONCAT(U.USUARIO,' - ',U.Nombres,' ',U.Apellidos) AS AGENTE
        FROM SISCOB.DBO.COMPROMISO C WITH(NOLOCK)

        LEFT JOIN SISCOB.DBO.GESTION G WITH(NOLOCK)
            ON G.IDGESTION = C.IDGESTION

        LEFT JOIN SISCOB.DBO.USUARIO U WITH(NOLOCK)
            ON U.IDUSUARIO = G.IDUSUARIO

        LEFT JOIN SISCOB.DBO.CLIENTE CL WITH(NOLOCK)
            ON CL.IDCLIENTE = G.IDCLIENTE

        WHERE 
            CL.IDCARTERA IN (112,117,124,126,128,132,133,135,137,139,143,144)
            AND CAST(C.FECHAGENERO AS DATE) BETWEEN DATEADD(MONTH, -1, DATEADD(DAY, 1, EOMONTH(GETDATE()))) AND GETDATE()
            AND LTRIM(RTRIM(U.USUARIO)) = LTRIM(RTRIM(:agente))
            
        ORDER BY C.FECHACOMPROMISO DESC
    """

    with engine_siscob.connect() as conn:
        result = conn.execute(text(query), {"agente": agente}).fetchall()

    data = [dict(r._mapping) for r in result]

    return {"ok": True, "data": data}