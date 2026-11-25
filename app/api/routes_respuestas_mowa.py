"""Vista autenticada de respuestas recibidas por Mowa."""

import logging
from datetime import date, datetime, timedelta
from pathlib import Path
from threading import Lock
from typing import Dict
from zoneinfo import ZoneInfo

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from app.core import autorizacion_carteras as autorizacion
from app.core.auth_dependencies import requiere_clave_definitiva
from app.core.db_siscob import engine_siscob
from app.core.permisos_vistas import exigir_vista
from app.services.respuestas_mowa_service import (
    CUENTAS, NOMBRES_CUENTAS, MowaError, SnapshotNoDisponible,
    cuenta_reportable, _cuentas_reportables,
    consultar_respuestas, consultar_historial, enviar_respuesta,
)
from app.services.respuestas_mowa_export import generar_excel_respuestas
from app.services import respuestas_sms_tabla as tabla
from app.services import respuestas_sms_sync as sync_sms
from app.services.respuestas_sms_sync import ahora_lima


router = APIRouter()
logger = logging.getLogger(__name__)
_carga_manual_local = Lock()


class EnvioSms(BaseModel):
    cuenta: str
    campana_id: int = Field(gt=0)
    respuesta_id: int = Field(gt=0)
    mensaje_id: int = Field(gt=0)
    fecha_campana: date
    texto: str = Field(min_length=1, max_length=160)


class ExportacionSms(BaseModel):
    desde: date
    hasta: date
    cuenta: str | None = None
    estado_filtro: str | None = None
    etiqueta_rango: str | None = Field(default=None, max_length=40)
    completo: bool
    advertencias: list[str] = Field(default_factory=list, max_length=1000)
    conversaciones: list[dict] = Field(min_length=1, max_length=20000)


class ActualizacionSms(BaseModel):
    dias: int = Field(default=7, ge=1, le=60)


def _exigir_actualizacion_sms(usuario: Dict) -> None:
    exigir_vista(usuario, "respuestas_mowa")
    if not autorizacion.tiene_vision_global(usuario):
        raise autorizacion.prohibido("Solo administradores y jefes pueden actualizar las respuestas SMS.")


def _ejecutar_actualizacion_sms(desde: date, dni: str) -> None:
    try:
        sync_sms.ejecutar(engine_siscob, tipo="MANUAL", desde=desde)
    except Exception:
        logger.exception("Error en actualización manual SMS usuario=%s", dni)
    finally:
        _carga_manual_local.release()


@router.get("")
def vista_respuestas_mowa():
    root = Path(__file__).resolve().parents[2]
    return FileResponse(root / "frontend" / "views" / "respuestas_mowa.html")


@router.get("/opciones")
def opciones_respuestas_mowa(usuario: Dict = Depends(requiere_clave_definitiva)):
    exigir_vista(usuario, "respuestas_mowa")
    autorizacion.exigir_no_monitor_calidad(usuario)
    carteras = autorizacion.carteras_permitidas(usuario)
    return {
        "alcance_carteras": None if carteras is None else sorted(carteras),
        "puede_actualizar": autorizacion.tiene_vision_global(usuario),
        "cuentas": [
            {"id": nombre, "nombre": NOMBRES_CUENTAS[nombre],
             "carteras": sorted(candidatas if carteras is None else set(candidatas) & carteras)}
            for nombre, candidatas, _ in _cuentas_reportables(carteras)
        ],
    }


@router.get("/sincronizacion")
async def estado_actualizacion_sms(usuario: Dict = Depends(requiere_clave_definitiva)):
    _exigir_actualizacion_sms(usuario)
    try:
        return await run_in_threadpool(tabla.estado_carga)
    except Exception:
        logger.exception("Error consultando estado de actualización SMS usuario=%s", usuario.get("dni"))
        raise HTTPException(status_code=503, detail="No se pudo consultar la actualización SMS.")


@router.post("/sincronizacion", status_code=202)
async def iniciar_actualizacion_sms(
    payload: ActualizacionSms, background_tasks: BackgroundTasks,
    usuario: Dict = Depends(requiere_clave_definitiva),
):
    _exigir_actualizacion_sms(usuario)
    try:
        estado = await run_in_threadpool(tabla.estado_carga)
    except Exception:
        logger.exception("Error verificando actualización SMS usuario=%s", usuario.get("dni"))
        raise HTTPException(status_code=503, detail="No se pudo verificar la carga SMS.")
    if estado["en_curso"] or not _carga_manual_local.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="Ya hay una actualización SMS en curso.")
    hoy = ahora_lima().date()
    desde = hoy - timedelta(days=payload.dias - 1)
    try:
        background_tasks.add_task(_ejecutar_actualizacion_sms, desde, str(usuario.get("dni") or ""))
    except Exception:
        _carga_manual_local.release()
        raise
    logger.info("Actualización SMS solicitada usuario=%s desde=%s", usuario.get("dni"), desde)
    return {"aceptada": True, "id_anterior": estado["id"],
            "desde": desde.isoformat(), "hasta": hoy.isoformat()}


@router.get("/consultar")
async def respuestas_mowa(
    desde: date = Query(...), hasta: date = Query(...),
    cuenta: str | None = Query(default=None),
    offset: int = Query(default=0, ge=0, le=100000),
    snapshot_token: str | None = Query(default=None, max_length=80),
    usuario: Dict = Depends(requiere_clave_definitiva),
):
    exigir_vista(usuario, "respuestas_mowa")
    autorizacion.exigir_no_monitor_calidad(usuario)
    if hasta < desde or hasta - desde > timedelta(days=6) or hasta > datetime.now(ZoneInfo("America/Lima")).date():
        raise HTTPException(status_code=400, detail="Selecciona un rango de hasta 7 días, sin fechas futuras.")
    carteras = autorizacion.carteras_permitidas(usuario)
    if carteras is not None and not carteras:
        raise autorizacion.prohibido()
    if cuenta and not cuenta_reportable(cuenta):
        raise HTTPException(status_code=400, detail="Cuenta SMS no válida.")
    if cuenta and carteras is not None and not set(CUENTAS[cuenta]) & carteras:
        raise autorizacion.prohibido()
    try:
        return await run_in_threadpool(consultar_respuestas, desde, hasta, carteras, cuenta,
                                       offset, snapshot_token, usuario.get("dni") or "")
    except SnapshotNoDisponible as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception:
        logger.exception("Error consultando respuestas Mowa usuario=%s", usuario.get("dni"))
        raise HTTPException(status_code=503, detail="No se pudo verificar las respuestas y gestiones. Intenta nuevamente.")


MAX_CARTERAS_EN_NOMBRE = 5


def nombre_excel_sms(base: str, carteras, parcial: bool, rango: str = "",
                     ahora: datetime | None = None) -> str:
    """Nombre único y descriptivo: base, carteras del contenido, rango y fecha-hora de generación.

    Ej.: SMS_sin_atender_C124_20261120_100512.xlsx
         Respuestas_SMS_C126-128_2026-11-19_a_2026-11-20_20261120_100512_PARCIAL.xlsx
    La hora con segundos evita que el navegador agregue (1), (2) al descargar varias veces.
    """
    ids = sorted({int(c) for c in carteras if str(c or "").strip().isdigit()})
    if not ids:
        pieza = ""
    elif len(ids) <= MAX_CARTERAS_EN_NOMBRE:
        pieza = "C" + "-".join(map(str, ids))
    else:
        pieza = "Varias_carteras"
    hora = (ahora or ahora_lima()).strftime("%Y%m%d_%H%M%S")
    nombre = "_".join(p for p in (base, pieza, rango, hora) if p)
    return f"{nombre}{'_PARCIAL' if parcial else ''}.xlsx"


def _carteras_y_cuenta(usuario: Dict, cuenta: str | None):
    exigir_vista(usuario, "respuestas_mowa")
    autorizacion.exigir_no_monitor_calidad(usuario)
    carteras = autorizacion.carteras_permitidas(usuario)
    if carteras is not None and not carteras:
        raise autorizacion.prohibido()
    if cuenta and not cuenta_reportable(cuenta):
        raise HTTPException(status_code=400, detail="Cuenta SMS no válida.")
    if cuenta and carteras is not None and not set(CUENTAS[cuenta]) & carteras:
        raise autorizacion.prohibido()
    return carteras


@router.get("/recibidas")
async def respuestas_recibidas(
    desde: date = Query(...), hasta: date = Query(...),
    cuenta: str | None = Query(default=None),
    usuario: Dict = Depends(requiere_clave_definitiva),
):
    """Respuestas recibidas en el rango (fecha de recepción), leídas de CobAuto."""
    carteras = _carteras_y_cuenta(usuario, cuenta)
    if hasta < desde or hasta - desde > timedelta(days=30) or hasta > datetime.now(ZoneInfo("America/Lima")).date():
        raise HTTPException(status_code=400, detail="Selecciona un rango de hasta 31 días, sin fechas futuras.")
    try:
        return await run_in_threadpool(tabla.consultar_recibidas, desde, hasta, carteras, cuenta)
    except Exception:
        logger.exception("Error consultando respuestas SMS de la tabla usuario=%s", usuario.get("dni"))
        raise HTTPException(status_code=503, detail="No se pudo consultar las respuestas SMS. Intenta nuevamente.")


@router.get("/sin-atender")
async def resumen_sin_atender(cuenta: str | None = Query(default=None),
                              usuario: Dict = Depends(requiere_clave_definitiva)):
    """Clientes activos con respuestas sin gestión posterior, sin límite de fecha."""
    carteras = _carteras_y_cuenta(usuario, cuenta)
    try:
        resultado = await run_in_threadpool(tabla.sin_atender, carteras, cuenta)
    except Exception:
        logger.exception("Error calculando respuestas SMS sin atender usuario=%s", usuario.get("dni"))
        raise HTTPException(status_code=503, detail="No se pudo calcular los clientes sin atender.")
    resultado.pop("grupos", None)
    return resultado


@router.get("/sin-atender/detalle")
async def detalle_sin_atender(cartera: int = Query(..., gt=0),
                             cuenta: str | None = Query(default=None),
                             usuario: Dict = Depends(requiere_clave_definitiva)):
    """Pendientes acumulados de una cartera autorizada, para abrirlos desde el gráfico."""
    carteras = _carteras_y_cuenta(usuario, cuenta)
    if carteras is not None and cartera not in carteras:
        raise autorizacion.prohibido()
    try:
        return await run_in_threadpool(tabla.sin_atender, carteras, cuenta, cartera)
    except Exception:
        logger.exception("Error consultando pendientes SMS cartera=%s usuario=%s", cartera, usuario.get("dni"))
        raise HTTPException(status_code=503, detail="No se pudo consultar los pendientes de la cartera.")


@router.get("/sin-atender/excel")
async def excel_sin_atender(cuenta: str | None = Query(default=None),
                            cartera: int | None = Query(default=None, gt=0),
                            usuario: Dict = Depends(requiere_clave_definitiva)):
    carteras = _carteras_y_cuenta(usuario, cuenta)
    if cartera is not None and carteras is not None and cartera not in carteras:
        raise autorizacion.prohibido()
    try:
        resultado = await run_in_threadpool(tabla.sin_atender, carteras, cuenta, cartera)
    except Exception:
        logger.exception("Error generando Excel de SMS sin atender usuario=%s", usuario.get("dni"))
        raise HTTPException(status_code=503, detail="No se pudo generar el Excel de clientes sin atender.")
    hoy = ahora_lima().date().isoformat()
    datos = {"desde": resultado["desde"], "hasta": hoy, "cuenta": cuenta,
             "estado_filtro": "PENDIENTE", "completo": resultado["completo"],
             "advertencias": resultado["advertencias"], "conversaciones": resultado["grupos"],
             "etiqueta_rango": "Respuestas recibidas",
             "origen": "Clientes activos con respuestas SMS sin gestión SISCOB posterior (tabla CRM_SMS_RESPUESTA)"}
    archivo = await run_in_threadpool(generar_excel_respuestas, datos, carteras)
    nombre = nombre_excel_sms(
        "SMS_sin_atender",
        (f.get("idcartera") for g in resultado["grupos"] for f in g["filas"]),
        not resultado["completo"])
    logger.info("Excel SMS sin atender usuario=%s clientes=%s", usuario.get("dni"), resultado["clientes"])
    return Response(content=archivo,
                    media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f'attachment; filename="{nombre}"'})


@router.post("/enviar")
async def enviar_sms_mowa(payload: EnvioSms, usuario: Dict = Depends(requiere_clave_definitiva)):
    exigir_vista(usuario, "respuestas_mowa")
    autorizacion.exigir_no_monitor_calidad(usuario)
    carteras = autorizacion.carteras_permitidas(usuario)
    if carteras is not None and not carteras:
        raise autorizacion.prohibido()
    if payload.cuenta not in CUENTAS or (carteras is not None
                                        and not set(CUENTAS[payload.cuenta]) & carteras):
        raise autorizacion.prohibido()
    if payload.fecha_campana > datetime.now(ZoneInfo("America/Lima")).date():
        raise HTTPException(status_code=400, detail="La fecha de la campaña no puede ser futura.")
    try:
        resultado = await run_in_threadpool(
            enviar_respuesta, payload.cuenta, payload.campana_id,
            payload.respuesta_id, payload.mensaje_id, payload.fecha_campana,
            payload.texto, carteras,
        )
        logger.info("SMS Mowa aceptado usuario=%s cuenta=%s cartera=%s cliente=%s mensaje=%s",
                    usuario.get("dni"), payload.cuenta, resultado["idcartera"],
                    resultado["idcliente"], resultado["mensaje_id"])
        return resultado
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except MowaError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception:
        logger.exception("Error enviando SMS Mowa usuario=%s", usuario.get("dni"))
        raise HTTPException(status_code=503, detail="No se confirmó el envío. Verifica Mowa antes de reintentar.")


@router.get("/historial")
async def historial_sms_mowa(
    cuenta: str = Query(...), campana_id: int = Query(..., gt=0),
    respuesta_id: int = Query(..., gt=0), mensaje_id: int = Query(..., gt=0),
    fecha_campana: date = Query(...),
    desde: date = Query(...), hasta: date = Query(...),
    usuario: Dict = Depends(requiere_clave_definitiva),
):
    exigir_vista(usuario, "respuestas_mowa")
    autorizacion.exigir_no_monitor_calidad(usuario)
    if hasta < desde or hasta - desde > timedelta(days=30) or hasta > datetime.now(ZoneInfo("America/Lima")).date():
        raise HTTPException(status_code=400, detail="Selecciona un rango de hasta 31 días, sin fechas futuras.")
    if fecha_campana < desde or fecha_campana > hasta:
        raise HTTPException(status_code=400, detail="La campaña original debe estar dentro del rango consultado.")
    carteras = autorizacion.carteras_permitidas(usuario)
    if carteras is not None and not carteras:
        raise autorizacion.prohibido()
    if cuenta not in CUENTAS or (carteras is not None and not set(CUENTAS[cuenta]) & carteras):
        raise autorizacion.prohibido()
    try:
        return await run_in_threadpool(consultar_historial, cuenta, campana_id,
                                       respuesta_id, mensaje_id, fecha_campana,
                                       desde, hasta, carteras)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except MowaError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception:
        logger.exception("Error consultando historial SMS usuario=%s", usuario.get("dni"))
        raise HTTPException(status_code=503, detail="No se pudo completar el historial SMS.")


@router.post("/exportar")
async def exportar_sms_mowa(payload: ExportacionSms,
                           usuario: Dict = Depends(requiere_clave_definitiva)):
    exigir_vista(usuario, "respuestas_mowa")
    autorizacion.exigir_no_monitor_calidad(usuario)
    carteras = autorizacion.carteras_permitidas(usuario)
    if carteras is not None and not carteras:
        raise autorizacion.prohibido()
    if (payload.hasta < payload.desde or payload.hasta - payload.desde > timedelta(days=30)
            or payload.hasta > datetime.now(ZoneInfo("America/Lima")).date()):
        raise HTTPException(status_code=400, detail="El rango exportado debe tener hasta 31 días, sin fechas futuras.")
    if payload.cuenta and (not cuenta_reportable(payload.cuenta) or
                           (carteras is not None and not set(CUENTAS[payload.cuenta]) & carteras)):
        raise autorizacion.prohibido()
    total_filas = 0
    for grupo in payload.conversaciones:
        filas = grupo.get("filas")
        if not isinstance(filas, list) or not filas:
            raise HTTPException(status_code=400, detail="El Excel requiere conversaciones con respuestas.")
        total_filas += len(filas)
        if total_filas > 20000:
            raise HTTPException(status_code=400, detail="El Excel supera 20 000 respuestas; acota los filtros.")
        for fila in filas:
            if not isinstance(fila, dict) or not cuenta_reportable(fila.get("cuenta")):
                raise HTTPException(status_code=400, detail="Hay una respuesta sin cuenta válida.")
            if payload.cuenta and fila["cuenta"] != payload.cuenta:
                raise HTTPException(status_code=400, detail="Hay respuestas fuera de la cuenta seleccionada.")
            try:
                idcartera = int(fila.get("idcartera"))
            except (TypeError, ValueError):
                idcartera = None
            if carteras is not None and (idcartera not in carteras or
                                         idcartera not in CUENTAS[fila["cuenta"]]):
                raise autorizacion.prohibido()
    datos = payload.model_dump(mode="json")
    archivo = await run_in_threadpool(generar_excel_respuestas, datos, carteras)
    nombre = nombre_excel_sms(
        "Respuestas_SMS",
        (f.get("idcartera") for g in payload.conversaciones for f in g.get("filas", [])),
        not payload.completo, f"{payload.desde}_a_{payload.hasta}")
    return Response(content=archivo,
                    media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f'attachment; filename="{nombre}"'})
