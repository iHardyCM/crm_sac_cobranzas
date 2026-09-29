import logging
from typing import Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.services.auth_service import ErrorCambioClave, autenticar_usuario, cambiar_clave_propia
from app.core import auth_dependencies
from app.core.auth_dependencies import obtener_usuario_actual


logger = logging.getLogger(__name__)

router = APIRouter()

MENSAJE_CREDENCIALES = "Usuario o contraseña incorrectos."
MENSAJE_ERROR_TECNICO = "No se pudo validar el acceso en este momento. Intenta nuevamente."

# Limite para no aceptar cadenas enormes en el hash (Argon2 es costoso).
MAX_LARGO_CLAVE = 128


class LoginRequest(BaseModel):
    dni: Optional[str] = None
    clave: Optional[str] = None


class CambiarClaveRequest(BaseModel):
    # Sin campo DNI: el usuario sale exclusivamente del JWT.
    clave_actual: Optional[str] = None
    clave_nueva: Optional[str] = None
    confirmacion: Optional[str] = None


def _respuesta_error(status_code: int, mensaje: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"ok": False, "msg": mensaje})


@router.post("/login")
def login(payload: LoginRequest):
    dni = (payload.dni or "").strip()
    clave = payload.clave or ""

    if not dni or len(dni) != 8 or not dni.isdigit():
        return _respuesta_error(status.HTTP_400_BAD_REQUEST, "Ingresa un DNI valido de 8 digitos.")

    if not clave:
        return _respuesta_error(status.HTTP_400_BAD_REQUEST, "Ingresa tu contraseña.")

    if len(clave) > MAX_LARGO_CLAVE:
        return _respuesta_error(status.HTTP_401_UNAUTHORIZED, MENSAJE_CREDENCIALES)

    try:
        resultado = autenticar_usuario(dni, clave)
    except Exception:
        logger.exception("Error tecnico en login usuario=%s", dni)
        return _respuesta_error(status.HTTP_503_SERVICE_UNAVAILABLE, MENSAJE_ERROR_TECNICO)

    if not resultado.ok:
        return _respuesta_error(status.HTTP_401_UNAUTHORIZED, MENSAJE_CREDENCIALES)

    return {
        "ok": True,
        "access_token": resultado.access_token,
        "token_type": "bearer",
        "requiere_cambio_clave": resultado.requiere_cambio_clave,
        "user": resultado.usuario,
    }


@router.get("/me")
def me(usuario: Dict = Depends(obtener_usuario_actual)):
    """Identidad que el backend reconoce para el token enviado.

    Incluye requiere_cambio_clave (leido de CRM_USUARIO_ACCESO) para que el
    frontend envie al cambio de clave sin depender de localStorage.
    """
    try:
        requiere_cambio = auth_dependencies.cuenta_requiere_cambio_clave(usuario["dni"])
    except Exception:
        logger.exception("Error verificando cambio obligatorio en /auth/me usuario=%s", usuario.get("dni"))
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=MENSAJE_ERROR_TECNICO)
    return {**usuario, "requiere_cambio_clave": bool(requiere_cambio)}


@router.post("/cambiar-clave")
def cambiar_clave(payload: CambiarClaveRequest, usuario: Dict = Depends(obtener_usuario_actual)):
    """Cambia la clave del usuario autenticado y quita el cambio obligatorio."""
    dni = usuario["dni"]
    try:
        cambiar_clave_propia(dni, payload.clave_actual, payload.clave_nueva, payload.confirmacion)
    except ErrorCambioClave as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception:
        logger.exception("Error tecnico cambiando clave usuario=%s", dni)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=MENSAJE_ERROR_TECNICO)

    return {"ok": True, "requiere_cambio_clave": False}
