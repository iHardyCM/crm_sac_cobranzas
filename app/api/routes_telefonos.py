# routes_telefonos.py
import logging
from pathlib import Path
from typing import Dict

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool

from app.core import autorizacion_carteras as autorizacion
from app.core.auth_dependencies import requiere_clave_definitiva
from app.core.permisos_vistas import exigir_vista
from app.services.telefonos_service import (
    buscar_telefonos_cliente,
    listar_filtros_telefonos,
    obtener_detalle_telefono,
)


router = APIRouter()
logger = logging.getLogger(__name__)

# Seguridad: todos los endpoints de datos exigen sesion valida. Las carteras
# consultables salen del usuario autenticado (vision global = sin restriccion);
# un "idcartera" enviado por el navegador solo puede acotar, nunca ampliar.
UsuarioTelefonos = Depends(requiere_clave_definitiva)

MENSAJE_ERROR_TECNICO = "No se pudo completar la consulta de teléfonos. Intenta nuevamente."


def _carteras_autorizadas(usuario: Dict):
    exigir_vista(usuario, "telefonos")
    permitidas = autorizacion.carteras_permitidas(usuario)
    return None if permitidas is None else sorted(permitidas)


@router.get("")
def vista_telefonos():
    root = Path(__file__).resolve().parents[2]
    return FileResponse(root / "frontend" / "views" / "telefonos.html")


@router.get("/buscar")
async def buscar_telefonos(
    q: str = Query(..., description="DNI, ID Cliente o teléfono"),
    idcartera: str | None = Query(default=None),
    whatsapp: str | None = Query(default=None),
    timbra: str | None = Query(default=None),
    tipo: str | None = Query(default=None),
    origen: str | None = Query(default=None),
    usuario: Dict = UsuarioTelefonos,
):
    carteras = _carteras_autorizadas(usuario)
    if idcartera and idcartera != "TODOS" and not autorizacion.cartera_permitida(usuario, idcartera):
        raise autorizacion.prohibido()
    try:
        return await run_in_threadpool(
            buscar_telefonos_cliente,
            q=q,
            idcartera=idcartera,
            whatsapp=whatsapp,
            timbra=timbra,
            tipo=tipo,
            origen=origen,
            carteras_permitidas=carteras,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        logger.exception("Error consultando teléfonos usuario=%s", usuario.get("dni"))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=MENSAJE_ERROR_TECNICO)


@router.get("/filtros")
async def filtros_telefonos(usuario: Dict = UsuarioTelefonos):
    carteras = _carteras_autorizadas(usuario)
    try:
        return await run_in_threadpool(listar_filtros_telefonos, carteras)
    except Exception:
        logger.exception("Error obteniendo filtros de teléfonos usuario=%s", usuario.get("dni"))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=MENSAJE_ERROR_TECNICO)


@router.get("/detalle/{telefono}")
async def detalle_telefono(telefono: str, usuario: Dict = UsuarioTelefonos):
    carteras = _carteras_autorizadas(usuario)
    try:
        return await run_in_threadpool(obtener_detalle_telefono, telefono, carteras)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception:
        logger.exception("Error obteniendo detalle de teléfono usuario=%s", usuario.get("dni"))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=MENSAJE_ERROR_TECNICO)
