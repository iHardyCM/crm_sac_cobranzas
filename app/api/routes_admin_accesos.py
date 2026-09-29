"""Administracion de accesos al CRM.

Todos los endpoints exigen un JWT valido de un usuario con TipoUsuario =
ADMINISTRADOR (dependencia requiere_administrador). El administrador que
audita cada cambio sale del token, nunca del payload.
"""

import logging
from typing import Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.core.auth_dependencies import requiere_administrador
from app.services import admin_accesos_service as servicio
from app.services.admin_accesos_service import ErrorAccesos


logger = logging.getLogger(__name__)

router = APIRouter()

MENSAJE_ERROR_TECNICO = "No se pudo completar la operacion. Intenta nuevamente."


def _ejecutar(accion: str, admin: Dict, funcion, *args, **kwargs):
    try:
        return funcion(*args, **kwargs)
    except ErrorAccesos as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.mensaje)
    except Exception:
        logger.exception("Error tecnico admin accesos accion=%s admin=%s", accion, admin.get("dni"))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=MENSAJE_ERROR_TECNICO)


def _sin_cache(response: Response) -> None:
    # Las respuestas con clave temporal no deben quedar en caches del navegador o proxies.
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"


@router.get("/usuarios")
def listar_usuarios(
    response: Response,
    q: Optional[str] = Query(default=None, max_length=100),
    limite: int = Query(default=100, ge=1, le=servicio.LIMITE_MAXIMO_LISTADO),
    admin: Dict = Depends(requiere_administrador),
):
    _sin_cache(response)
    data = _ejecutar("LISTAR", admin, servicio.listar_usuarios, q=q, limite=limite)
    return {"data": data}


@router.post("/{dni}/habilitar")
def habilitar_acceso(dni: str, response: Response, admin: Dict = Depends(requiere_administrador)):
    _sin_cache(response)
    return _ejecutar("HABILITAR", admin, servicio.habilitar_acceso, dni, admin["dni"])


@router.post("/{dni}/reset-clave")
def resetear_clave(dni: str, response: Response, admin: Dict = Depends(requiere_administrador)):
    _sin_cache(response)
    return _ejecutar("RESET_CLAVE", admin, servicio.resetear_clave, dni, admin["dni"])


@router.post("/{dni}/desbloquear")
def desbloquear(dni: str, response: Response, admin: Dict = Depends(requiere_administrador)):
    _sin_cache(response)
    return _ejecutar("DESBLOQUEAR", admin, servicio.desbloquear, dni, admin["dni"])


@router.post("/{dni}/deshabilitar")
def deshabilitar(dni: str, response: Response, admin: Dict = Depends(requiere_administrador)):
    _sin_cache(response)
    return _ejecutar("DESHABILITAR", admin, servicio.deshabilitar, dni, admin["dni"])
