from fastapi import APIRouter
from app.services.compromisos_service import obtener_compromisos

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
            C.FECHAGENERO,
            C.FECHACOMPROMISO,
            C.MONTO,
            C.MONEDA,
            C.NUMOPERACION,
            C.TIPOPAGO,
            C.MONTOPAGADO,

            G.GESTION,
            G.DNI,
            G.TELEFONO,

            CL.NOMBRECLIENTE,

            CONCAT(U.USUARIO,' - ',U.Nombres,' ',U.Apellidos) AS AGENTE

        FROM SISCOB.DBO.COMPROMISO C WITH(NOLOCK)

        LEFT JOIN SISCOB.DBO.GESTION G WITH(NOLOCK)
            ON G.IDGESTION = C.IDGESTION

        LEFT JOIN SISCOB.DBO.CLIENTE CL WITH(NOLOCK)
            ON CL.IDCLIENTE = G.IDCLIENTE

        LEFT JOIN SISCOB.DBO.USUARIO U
            ON U.IDUSUARIO = G.IDUSUARIO

        WHERE C.IDCOMPROMISO = :id
    """)

    try:
        with engine_siscob.connect() as conn:
            r = conn.execute(query, {"id": id}).fetchone()

            if not r:
                return {"msg": "No encontrado"}

            return {
                "id": r.IDCOMPROMISO,
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
                "agente": r.AGENTE
            }

    except Exception as e:
        print("ERROR DETALLE:", e)
        return {"msg": "Error interno"}


# 📊 LISTADO
@router.get("/{dni}")
def get_compromisos(dni: str):
    return {"data": obtener_compromisos(dni)}