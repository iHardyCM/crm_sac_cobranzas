# routes_compromisos
from fastapi import APIRouter
from app.services.compromisos_service import obtener_compromisos
from app.core.db_siscob import engine_siscob
from sqlalchemy import text

from fastapi.responses import StreamingResponse
import pandas as pd
from io import BytesIO
from datetime import datetime

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

        WHERE 1=1
            AND C.IDCOMPROMISO = :id
            AND C.MONTO > 0
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
            SELECT IDCARTERA,TipoUsuario
            FROM SISCOB.DBO.USUARIO WITH(NOLOCK)
            WHERE LTRIM(RTRIM(USUARIO)) = LTRIM(RTRIM(:dni))
        """)

        with engine_siscob.connect() as conn:
            print("🚀 DNI RECIBIDO FRONT:", dni)
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
                    THEN MONTOPAGADO ELSE 0 END) AS MONTO_PAGADO,
                -- 🔥 BASE VENCIDA AL DÍA POR MONTO
                SUM(CASE 
                    WHEN CAST(C.FECHACOMPROMISO AS DATE) <= CAST(GETDATE() AS DATE)
                    THEN ISNULL(C.MONTO,0) ELSE 0 
                END) AS MONTO_PDP_AL_DIA,
                -- 🔥 MONTO CUMPLIDO AL DÍA
                SUM(CASE 
                    WHEN CAST(C.FECHACOMPROMISO AS DATE) <= CAST(GETDATE() AS DATE)
                    THEN ISNULL(C.MONTOPAGADO,0) ELSE 0 
                END) AS MONTO_PAGADO_AL_DIA,
                -- 🔥 MONTO CAÍDO AL DÍA
                SUM(CASE 
                    WHEN CAST(C.FECHACOMPROMISO AS DATE) <= CAST(GETDATE() AS DATE)
                    THEN ISNULL(C.MONTO,0) - ISNULL(C.MONTOPAGADO,0)
                    ELSE 0 
                END) AS MONTO_CAIDO_AL_DIA
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
                AND C.MONTO > 0
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

    data = obtener_compromisos(agente)

    return {
        "ok": True,
        "data": data
    }


@router.get("/supervisor/exportar-cartera")
def exportar_cartera(dni: str):

    query = text("""

        SELECT
            C.idGestion,
            C.IdCompromiso,
            C.FECHAGENERO,
            CONCAT(U.USUARIO,' - ',U.Nombres,' ',U.Apellidos) AS AGENTE,
            CL.NOMBRECLIENTE AS CLIENTE,
            CL.IDCARTERA,
            G.DNI,
            G.TELEFONO,
            C.NUMOPERACION,
            C.MONTO,
            CAST(C.FECHACOMPROMISO AS DATE) AS FECHA_COMPROMISO,
            CASE 
                WHEN PAGADO = 'SI' THEN 'CUMPLIDA'
                WHEN CAST(C.FECHACOMPROMISO AS DATE) = CAST(GETDATE() AS DATE)
                    THEN 'HOY'
                WHEN CAST(C.FECHACOMPROMISO AS DATE) < GETDATE()
                    THEN 'CAIDA'
                ELSE 'VIGENTE'
            END AS ESTADO,
            C.TIPOPAGO,
            C.MONTOPAGADO,
            -- 🔥 INTENTOS HOY
            ISNULL(INTENTOS.INTENTOS_HOY,0) AS INTENTOS_HOY,
            -- 🔥 GESTIÓN QUE GENERÓ EL COMPROMISO
            G.GESTION AS GESTION_COMPROMISO,
            -- 🔥 ÚLTIMA GESTIÓN
            UG.ULT_GESTION,
            UG.ULT_FECHA,
            UG.ULT_TIPOCONTACTO,
            UG.ULT_INDICADOR,
            UG.ULT_AGENTE
        FROM SISCOB.DBO.COMPROMISO C WITH(NOLOCK)

        LEFT JOIN SISCOB.DBO.GESTION G WITH(NOLOCK)
            ON G.IDGESTION = C.IDGESTION

        LEFT JOIN SISCOB.DBO.USUARIO U WITH(NOLOCK)
            ON U.IDUSUARIO = G.IDUSUARIO

        LEFT JOIN SISCOB.DBO.CLIENTE CL WITH(NOLOCK)
            ON CL.IDCLIENTE = G.IDCLIENTE
        -- 🔥 INTENTOS DEL DÍA
        OUTER APPLY (
            SELECT COUNT(1) AS INTENTOS_HOY
            FROM SISCOB.DBO.GESTION GX WITH(NOLOCK)
            WHERE
                GX.IDCLIENTE = G.IDCLIENTE
                AND CAST(GX.FECHA AS DATE) = CAST(GETDATE() AS DATE)
        ) INTENTOS
        -- 🔥 ÚLTIMA GESTIÓN REAL
        OUTER APPLY (
            SELECT TOP 1
                G2.GESTION AS ULT_GESTION,
                G2.FECHA AS ULT_FECHA,
                I2.TIPOCONTACTO AS ULT_TIPOCONTACTO,
                I2.DESCRIPCIONINDICADOR AS ULT_INDICADOR,
                CONCAT(
                    U2.USUARIO,
                    ' - ',
                    U2.Nombres,
                    ' ',
                    U2.Apellidos
                ) AS ULT_AGENTE
            FROM SISCOB.DBO.GESTION G2 WITH(NOLOCK)
            LEFT JOIN SISCOB.DBO.USUARIO U2 WITH(NOLOCK)
                ON U2.IDUSUARIO = G2.IDUSUARIO
            LEFT JOIN SISCOB.DBO.INDICADOR I2 WITH(NOLOCK)
                ON I2.IDINDICADOR = G2.IDINDICADOR
            WHERE
                G2.IDCLIENTE = G.IDCLIENTE
            ORDER BY G2.FECHA DESC
        ) UG
        WHERE 1=1
            AND G.IDCARTERA = (
                SELECT IDCARTERA
                FROM SISCOB.DBO.USUARIO
                WHERE USUARIO = :dni
            )
            AND C.MONTO > 0
            AND CAST(C.FECHAGENERO AS DATE)
                BETWEEN DATEADD(MONTH,-1,DATEADD(DAY,1,EOMONTH(GETDATE())))
                AND GETDATE()
        ORDER BY
            U.USUARIO,
            C.FECHACOMPROMISO DESC

    """)

    with engine_siscob.connect() as conn:

        rows = conn.execute(query, {
            "dni": dni
        }).fetchall()

    df = pd.DataFrame(rows)

    output = BytesIO()

    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(
            writer,
            index=False,
            sheet_name="Cartera"
        )

    output.seek(0)

    fecha_descarga = datetime.now().strftime("%Y%m%d_%H%M")

    nombre_archivo = (
        f"Compromisos_{dni}_{fecha_descarga}.xlsx"
    )

    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition":
            f"attachment; filename={nombre_archivo}"
        }
    )