import logging
from typing import Dict, Optional

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.services.auth_service import autenticar_usuario
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
    """Identidad que el backend reconoce para el token enviado."""
    return usuario
