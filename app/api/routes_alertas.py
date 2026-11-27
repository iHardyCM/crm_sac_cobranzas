"""Alertas visibles en todas las pantallas del CRM."""
import logging
import time
from threading import Lock
from typing import Dict

from fastapi import APIRouter, Depends, HTTPException
from starlette.concurrency import run_in_threadpool

from app.core import autorizacion_carteras as autorizacion
from app.core.auth_dependencies import requiere_clave_definitiva
from app.core.db_siscob import engine_siscob
from app.core.permisos_vistas import tiene_vista
from app.services import respuestas_sms_tabla as sms
from app.services import zonas_restringidas_service as zonas


router = APIRouter()
logger = logging.getLogger(__name__)
_SMS_VIGENCIA_SEGUNDOS = 180
_sms_cache: dict[tuple[int, ...] | None, tuple[float, dict]] = {}
_sms_cache_lock = Lock()
_bandeja_cache: dict[tuple[str, tuple[int, ...]], tuple[float, dict]] = {}
_bandeja_cache_lock = Lock()


def _resumen_sms(carteras: set[int] | None) -> dict:
    clave = None if carteras is None else tuple(sorted(carteras))
    with _sms_cache_lock:
        ahora = time.monotonic()
        entrada = _sms_cache.get(clave)
        if entrada and ahora - entrada[0] < _SMS_VIGENCIA_SEGUNDOS:
            return entrada[1]
        resultado = sms.sin_atender(carteras)
        _sms_cache[clave] = (time.monotonic(), resultado)
        return resultado


def _resumen_bandeja(usuario: str, carteras: set[int]) -> dict:
    clave = (usuario, tuple(sorted(carteras)))
    with _bandeja_cache_lock:
        ahora = time.monotonic()
        entrada = _bandeja_cache.get(clave)
        if entrada and ahora - entrada[0] < _SMS_VIGENCIA_SEGUNDOS:
            return entrada[1]
        datos = sms.bandeja_asignada(carteras, usuario)
        resultado = {"clientes": datos["clientes"], "respuestas": datos["respuestas"],
                     "completo": datos["completo"]}
        _bandeja_cache[clave] = (time.monotonic(), resultado)
        return resultado


def _alerta_zona(grupo: list[dict], puede_abrir: bool) -> dict:
    grupo = sorted(grupo, key=lambda z: z["IdZona"])
    zona = grupo[0]
    vigente = zona["Estado"] == "VIGENTE"
    departamentos = [z["Departamento"].title() for z in grupo]
    nombres = departamentos[0] if len(departamentos) == 1 else ", ".join(departamentos[:-1]) + " y " + departamentos[-1]
    alcance = "todas las carteras" if zona["AplicaTodas"] else "carteras " + ", ".join(map(str, zona["Carteras"]))
    hasta = f" hasta {zona['Hasta']:%d/%m/%Y}" if zona["Hasta"] else ""
    return {
        "id": "zona:" + "-".join(str(z["IdZona"]) for z in grupo), "tipo": "zona_restringida",
        "nivel": "rojo" if vigente else "info",
        "titulo": f"{'Gestión detenida' if vigente else 'Restricción programada'}: {nombres}",
        "detalle": f"{zona['Origen'].title()} · {alcance} · desde {zona['Desde']:%d/%m/%Y}{hasta}. {zona['Motivo']}",
        "enlace": "zonas.html" if puede_abrir else None,
    }


def _alertas_zonas(filas: list[dict], puede_abrir: bool) -> list[dict]:
    grupos: dict[tuple, list[dict]] = {}
    for zona in filas:
        if not zona["Activo"] or zona["Estado"] not in ("VIGENTE", "PROGRAMADA"):
            continue
        clave = (zona["Estado"], zona["Origen"], zona["AplicaTodas"],
                 tuple(sorted(zona["Carteras"])), zona["Desde"], zona["Hasta"], zona["Motivo"])
        grupos.setdefault(clave, []).append(zona)
    return [_alerta_zona(grupo, puede_abrir) for grupo in
            sorted(grupos.values(), key=lambda g: min(z["IdZona"] for z in g))]


def _alerta_sms(resultado: dict) -> dict | None:
    clientes = int(resultado["clientes"])
    if clientes <= 0:
        return None
    parcial = not resultado["completo"]
    cantidad = f"Al menos {clientes}" if parcial else str(clientes)
    return {
        "id": "sms:sin-atender", "tipo": "sms_sin_atender", "nivel": "ambar",
        "cantidad_clientes": clientes,
        "titulo": "Respuestas SMS sin atender",
        "detalle": f"{cantidad} clientes con respuestas sin gestión posterior."
                   + (" Consulta parcial." if parcial else ""),
        "enlace": "respuestas_mowa.html",
    }


def _alerta_bandeja(resultado: dict) -> dict | None:
    clientes = int(resultado["clientes"])
    if clientes <= 0:
        return None
    respuestas = int(resultado["respuestas"])
    detalle = f"{clientes} clientes asignados · {respuestas} respuestas pendientes"
    if not resultado["completo"]:
        detalle += " · datos parciales"
    return {
        "id": "sms:mis-asignaciones", "tipo": "sms_mis_asignaciones", "nivel": "ambar",
        "titulo": "Tienes respuestas SMS por atender", "detalle": detalle,
        "cantidad_clientes": clientes, "enlace": "respuestas_mowa.html",
    }


@router.get("/resumen")
async def resumen(usuario: Dict = Depends(requiere_clave_definitiva)):
    """Zonas para todos; SMS solo para perfiles con consulta general y vista habilitada."""
    def consultar():
        with engine_siscob.connect() as conn:
            filas = zonas.zonas(conn)
        puede_abrir_zonas = autorizacion.tiene_vision_global(usuario) or autorizacion.es_supervisor(usuario)
        alertas = _alertas_zonas(filas, puede_abrir_zonas)
        if puede_abrir_zonas and tiene_vista(usuario, "respuestas_mowa"):
            carteras = autorizacion.carteras_permitidas(usuario)
            if carteras is None or carteras:
                try:
                    alerta = _alerta_sms(_resumen_sms(carteras))
                    if alerta:
                        alertas.append(alerta)
                except Exception:
                    logger.exception("Error consultando alertas SMS usuario=%s", usuario.get("dni"))
        elif autorizacion.perfil(usuario) == "GESTOR" and tiene_vista(usuario, "respuestas_mowa"):
            carteras = autorizacion.carteras_permitidas(usuario)
            if carteras:
                try:
                    alerta = _alerta_bandeja(_resumen_bandeja(str(usuario["dni"]), carteras))
                    if alerta:
                        alertas.append(alerta)
                except Exception:
                    logger.exception("Error consultando asignaciones SMS usuario=%s", usuario.get("dni"))
        return alertas

    try:
        return await run_in_threadpool(consultar)
    except Exception:
        logger.exception("Error consultando alertas usuario=%s", usuario.get("dni"))
        raise HTTPException(status_code=503, detail="No se pudieron consultar las alertas.")
