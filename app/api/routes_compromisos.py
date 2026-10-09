# routes_compromisos
import logging
from typing import Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from app.core import autorizacion_carteras as autorizacion
from app.core.auth_dependencies import requiere_clave_definitiva
from app.core.permisos_vistas import exigir_vista, tiene_vista
from app.services.compromisos_service import obtener_compromisos
from app.core.db_siscob import engine_siscob
from sqlalchemy import text

from fastapi.responses import StreamingResponse
import pandas as pd
from io import BytesIO
from datetime import datetime

router = APIRouter()
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Seguridad: todos los endpoints exigen sesion valida (requiere_clave_definitiva).
# El DNI del supervisor sale del JWT; el "dni" de la query ya no decide la
# cartera. Ver compromisos de otro agente exige vision global o que la cartera
# principal del agente este entre las carteras del supervisor.
# ---------------------------------------------------------------------------
UsuarioCompromisos = Depends(requiere_clave_definitiva)

MENSAJE_ERROR_TECNICO = "No se pudo completar la consulta de compromisos. Intenta nuevamente."
MENSAJE_AGENTE_NO_PERMITIDO = "No tienes acceso a los compromisos de ese agente."
MENSAJE_COMPROMISO_NO_PERMITIDO = "No tienes acceso a este compromiso."


def _error_tecnico(contexto: str, usuario: Dict) -> HTTPException:
    logger.exception("Error en compromisos (%s) usuario=%s", contexto, usuario.get("dni"))
    return HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=MENSAJE_ERROR_TECNICO)


def _autorizar_compromisos_de_agente(usuario: Dict, dni_agente: str) -> str:
    """Devuelve el DNI del agente a consultar si el usuario puede verlo."""
    if not (tiene_vista(usuario, "compromisos") or tiene_vista(usuario, "gestiones")):
        exigir_vista(usuario, "compromisos")
    dni_agente = str(dni_agente or "").strip()
    if dni_agente == str(usuario.get("dni") or "").strip():
        return dni_agente
    if autorizacion.tiene_vision_global(usuario):
        return dni_agente
    if tiene_vista(usuario, "gestiones"):
        try:
            cartera_agente = autorizacion.cartera_principal_de_usuario(dni_agente)
        except Exception:
            raise _error_tecnico("cartera del agente", usuario)
        if cartera_agente is not None and autorizacion.cartera_permitida(usuario, cartera_agente):
            return dni_agente
    logger.info("Compromisos de agente denegados usuario=%s agente=%s", usuario.get("dni"), dni_agente)
    raise autorizacion.prohibido(MENSAJE_AGENTE_NO_PERMITIDO)


def _autorizar_detalle_compromiso(usuario: Dict, id_compromiso: int, dni_agente,
                                  cartera_agente, cartera_compromiso) -> None:
    """Autorizacion por objeto del detalle (evita IDOR por id).

    Todo sale de la BD (SISCOB), nunca del navegador:
      - dni_agente: USUARIO.Usuario del agente que registro la gestion del
        compromiso (el mismo criterio que usa el listado: U.USUARIO = dni).
      - cartera_agente: USUARIO.IdCartera de ese agente (misma cartera que usa
        _autorizar_compromisos_de_agente).
      - cartera_compromiso: GESTION.IdCartera de la gestion del compromiso.

    Vision global: todo. Cualquier otro perfil: sus propios compromisos.
    Supervisor: ademas, los de agentes de sus carteras, siempre que la cartera
    del compromiso tambien este entre las suyas. Sin datos: 403.
    """
    if autorizacion.tiene_vision_global(usuario):
        return
    dni_agente = str(dni_agente or "").strip()
    if dni_agente and dni_agente == str(usuario.get("dni") or "").strip():
        return
    if (
        tiene_vista(usuario, "gestiones")
        and dni_agente
        and autorizacion.cartera_permitida(usuario, cartera_agente)
        and autorizacion.cartera_permitida(usuario, cartera_compromiso)
    ):
        return
    logger.info(
        "Detalle de compromiso denegado usuario=%s id=%s cartera_agente=%s cartera_compromiso=%s",
        usuario.get("dni"), id_compromiso, cartera_agente, cartera_compromiso,
    )
    raise autorizacion.prohibido(MENSAJE_COMPROMISO_NO_PERMITIDO)


def _exigir_supervision(usuario: Dict) -> None:
    """Vista del equipo: perfil base o asignacion individual, siempre por cartera."""
    exigir_vista(usuario, "gestiones")


TABLAS = {
    "compartamos_vigente": "TBL_COMPROMISOS_VIGENTE"
}

# 🔍 DETALLE
@router.get("/detalle/{id}")
def detalle(id: int, usuario: Dict = UsuarioCompromisos):
    if not (tiene_vista(usuario, "compromisos") or tiene_vista(usuario, "gestiones")):
        exigir_vista(usuario, "compromisos")
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
            G.IDCARTERA AS IDCARTERA_GESTION,
            LTRIM(RTRIM(U.USUARIO)) AS DNI_AGENTE,
            U.IDCARTERA AS IDCARTERA_AGENTE,

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
            AND UPPER(LTRIM(RTRIM(ISNULL(CL.ESTADO, '')))) IN ('A', 'N')
    """)

    try:
        with engine_siscob.connect() as conn:
            r = conn.execute(query, {"id": id}).fetchone()

            if not r:
                return {"msg": "No encontrado"}

            # Propietario (agente) + cartera, leidos de SISCOB.
            _autorizar_detalle_compromiso(
                usuario, id, r.DNI_AGENTE, r.IDCARTERA_AGENTE, r.IDCARTERA_GESTION,
            )

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

    except HTTPException:
        raise
    except Exception:
        logger.exception("Error en detalle de compromiso id=%s usuario=%s", id, usuario.get("dni"))
        return {"msg": "Error interno"}


# 📊 LISTADO
@router.get("/{dni}")
def get_compromisos(dni: str, usuario: Dict = UsuarioCompromisos):
    dni_agente = _autorizar_compromisos_de_agente(usuario, dni)
    try:
        return {"data": obtener_compromisos(dni_agente)}
    except Exception:
        raise _error_tecnico("listado", usuario)

@router.get("/supervisor/resumen")
def resumen_supervisor(dni: Optional[str] = None, usuario: Dict = UsuarioCompromisos):
    # El "dni" de la query se ignora: el supervisor es el usuario autenticado.
    _exigir_supervision(usuario)
    dni = usuario["dni"]

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
            result_cartera = conn.execute(query_cartera, {"dni": dni}).fetchone()
        
        if not result_cartera:
            return {"ok": False, "msg": "Supervisor no encontrado"}

        cartera = result_cartera.IDCARTERA

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
                AND UPPER(LTRIM(RTRIM(ISNULL(CL.ESTADO, '')))) IN ('A', 'N')
            GROUP BY U.USUARIO, U.Nombres, U.Apellidos
            ORDER BY TOTAL DESC
        """)

        with engine_siscob.connect() as conn:
            result = conn.execute(query, {"cartera": cartera}).fetchall()

        data = [dict(r._mapping) for r in result]

        return {"ok": True, "data": data}

    except Exception:
        logger.exception("Error en resumen de supervisor usuario=%s", dni)
        return {"ok": False, "error": MENSAJE_ERROR_TECNICO}


@router.get("/agente/compromisos")
def compromisos_agente(agente: str, usuario: Dict = UsuarioCompromisos):

    dni_agente = _autorizar_compromisos_de_agente(usuario, agente)
    try:
        data = obtener_compromisos(dni_agente)
    except Exception:
        raise _error_tecnico("compromisos de agente", usuario)

    return {
        "ok": True,
        "data": data
    }


@router.get("/supervisor/exportar-cartera")
def exportar_cartera(dni: Optional[str] = None, usuario: Dict = UsuarioCompromisos):
    # El "dni" de la query se ignora: se exporta la cartera del usuario autenticado.
    _exigir_supervision(usuario)
    dni = usuario["dni"]

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
            AND UPPER(LTRIM(RTRIM(ISNULL(CL.ESTADO, '')))) IN ('A', 'N')
            AND CAST(C.FECHAGENERO AS DATE)
                BETWEEN DATEADD(MONTH,-1,DATEADD(DAY,1,EOMONTH(GETDATE())))
                AND GETDATE()
        ORDER BY
            U.USUARIO,
            C.FECHACOMPROMISO DESC

    """)

    try:
        with engine_siscob.connect() as conn:

            rows = conn.execute(query, {
                "dni": dni
            }).fetchall()
    except Exception:
        raise _error_tecnico("exportar cartera", usuario)

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
            f"attachment; filename={nombre_archivo}",
            # El frontend descarga con fetch (para enviar Authorization) y lee el nombre.
            "Access-Control-Expose-Headers": "Content-Disposition",
        }
    )
