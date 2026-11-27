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


def _alerta_zona(zona: dict, puede_abrir: bool) -> dict:
    vigente = zona["Estado"] == "VIGENTE"
    departamento = zona["Departamento"].title()
    alcance = "todas las carteras" if zona["AplicaTodas"] else "carteras " + ", ".join(map(str, zona["Carteras"]))
    hasta = f" hasta {zona['Hasta']:%d/%m/%Y}" if zona["Hasta"] else ""
    return {
        "id": f"zona:{zona['IdZona']}", "tipo": "zona_restringida",
        "nivel": "rojo" if vigente else "info",
        "titulo": f"{'Gestión detenida' if vigente else 'Restricción programada'}: {departamento}",
        "detalle": f"{zona['Origen'].title()} · {alcance} · desde {zona['Desde']:%d/%m/%Y}{hasta}. {zona['Motivo']}",
        "enlace": "zonas.html" if puede_abrir else None,
    }


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


@router.get("/resumen")
async def resumen(usuario: Dict = Depends(requiere_clave_definitiva)):
    """Zonas para todos; SMS solo para perfiles con consulta general y vista habilitada."""
    def consultar():
        with engine_siscob.connect() as conn:
            filas = zonas.zonas(conn)
        puede_abrir_zonas = autorizacion.tiene_vision_global(usuario) or autorizacion.es_supervisor(usuario)
        alertas = [_alerta_zona(z, puede_abrir_zonas) for z in filas
                   if z["Activo"] and z["Estado"] in ("VIGENTE", "PROGRAMADA")]
        if puede_abrir_zonas and tiene_vista(usuario, "respuestas_mowa"):
            carteras = autorizacion.carteras_permitidas(usuario)
            if carteras is None or carteras:
                try:
                    alerta = _alerta_sms(_resumen_sms(carteras))
                    if alerta:
                        alertas.append(alerta)
                except Exception:
                    logger.exception("Error consultando alertas SMS usuario=%s", usuario.get("dni"))
        return alertas

    try:
        return await run_in_threadpool(consultar)
    except Exception:
        logger.exception("Error consultando alertas usuario=%s", usuario.get("dni"))
        raise HTTPException(status_code=503, detail="No se pudieron consultar las alertas.")
