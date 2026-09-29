"""Dependencias de autenticacion para FastAPI.

Uso en un endpoint:

    from fastapi import Depends
    from app.core.auth_dependencies import obtener_usuario_actual

    @router.get("/algo")
    def algo(usuario: dict = Depends(obtener_usuario_actual)):
        ...

El token solo aporta el DNI. En cada peticion se vuelve a comprobar que la
cuenta CRM exista y este activa (CRM_USUARIO_ACCESO.FLG_ACTIVO = 1) y que el
usuario siga activo en SISCOB; perfil y carteras se resuelven desde SISCOB.
Nunca se toman del navegador (localStorage, payload, query string).
"""

import logging
import unicodedata
from typing import Dict, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import text

# auth_service importa db_siscob (carga el .env) antes que security.
from app.services.auth_service import obtener_identidad_usuario
from app.core.db_siscob import engine_siscob
from app.core.security import decodificar_access_token


logger = logging.getLogger(__name__)

_bearer = HTTPBearer(auto_error=False)

MENSAJE_SESION_INVALIDA = "Sesion no valida o expirada. Inicia sesion nuevamente."
MENSAJE_ERROR_TECNICO = "No se pudo validar la sesion en este momento."
MENSAJE_SIN_PERMISO = "No tienes permiso para realizar esta accion."
MENSAJE_CAMBIO_CLAVE = "Debes cambiar tu contraseña antes de continuar."

PERFIL_ADMINISTRADOR = "ADMINISTRADOR"


def _no_autorizado() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=MENSAJE_SESION_INVALIDA,
        headers={"WWW-Authenticate": "Bearer"},
    )


def cuenta_crm_activa(dni: str) -> bool:
    """True si el DNI tiene cuenta en CRM_USUARIO_ACCESO con FLG_ACTIVO = 1.

    Sin NOLOCK: una cuenta deshabilitada debe dejar de entrar en cuanto se
    confirma el cambio, sin esperar a que venza el token.
    """
    with engine_siscob.connect() as conn:
        row = conn.execute(text("""
            SELECT TOP 1 1 AS ACTIVA
            FROM CobAuto.dbo.CRM_USUARIO_ACCESO
            WHERE USUARIO = :dni
              AND FLG_ACTIVO = 1
        """), {"dni": dni}).fetchone()

    return row is not None


def cuenta_requiere_cambio_clave(dni: str) -> bool:
    """True si la cuenta CRM tiene FLG_CAMBIO_OBLIGATORIO = 1 (o no se puede
    confirmar que no lo tenga). Se lee de la BD, nunca del navegador."""
    with engine_siscob.connect() as conn:
        row = conn.execute(text("""
            SELECT TOP 1 FLG_CAMBIO_OBLIGATORIO
            FROM CobAuto.dbo.CRM_USUARIO_ACCESO
            WHERE USUARIO = :dni
              AND FLG_ACTIVO = 1
        """), {"dni": dni}).fetchone()

    return row is None or bool(row.FLG_CAMBIO_OBLIGATORIO)


def obtener_usuario_actual(
    credenciales: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> Dict:
    """Usuario autenticado segun el backend.

    401 si: no hay token, el token es invalido o expiro, la cuenta CRM no
    existe o esta deshabilitada (FLG_ACTIVO = 0), o el usuario ya no esta
    activo en SISCOB (Estado <> 'A').
    """
    if credenciales is None or (credenciales.scheme or "").lower() != "bearer":
        raise _no_autorizado()

    payload = decodificar_access_token(credenciales.credentials)
    if not payload:
        raise _no_autorizado()

    dni = str(payload.get("sub") or "").strip()
    if not (len(dni) == 8 and dni.isdigit()):
        raise _no_autorizado()

    try:
        if not cuenta_crm_activa(dni):
            logger.info("Token rechazado: cuenta CRM inexistente o deshabilitada usuario=%s", dni)
            raise _no_autorizado()

        usuario = obtener_identidad_usuario(dni)
    except HTTPException:
        raise
    except Exception:
        logger.exception("Error resolviendo usuario actual usuario=%s", dni)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=MENSAJE_ERROR_TECNICO,
        )

    if not usuario:
        logger.info("Token rechazado: usuario no activo en SISCOB usuario=%s", dni)
        raise _no_autorizado()

    return usuario


def normalizar_tipo_usuario(tipo) -> str:
    """Mayusculas, sin tildes y sin espacios extremos ('Administrador ' -> 'ADMINISTRADOR')."""
    texto = unicodedata.normalize("NFD", str(tipo or "").strip())
    return "".join(c for c in texto if unicodedata.category(c) != "Mn").upper()


def requiere_clave_definitiva(usuario: Dict = Depends(obtener_usuario_actual)) -> Dict:
    """Bloquea a las cuentas con FLG_CAMBIO_OBLIGATORIO = 1 (clave temporal).

    Mientras la cuenta no cambie su clave solo puede usar los endpoints que
    dependen unicamente de obtener_usuario_actual: GET /auth/me y
    POST /auth/cambiar-clave. Cualquier otro endpoint que use esta dependencia
    (o requiere_administrador) responde 403.
    """
    dni = usuario.get("dni")
    try:
        requiere_cambio = cuenta_requiere_cambio_clave(dni)
    except Exception:
        logger.exception("Error verificando cambio obligatorio usuario=%s", dni)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=MENSAJE_ERROR_TECNICO,
        )

    if requiere_cambio:
        logger.info("Acceso denegado por cambio de clave obligatorio usuario=%s", dni)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=MENSAJE_CAMBIO_CLAVE)
    return usuario


def requiere_administrador(usuario: Dict = Depends(requiere_clave_definitiva)) -> Dict:
    """Solo deja pasar a TipoUsuario = ADMINISTRADOR, leido desde SISCOB, con
    clave definitiva (FLG_CAMBIO_OBLIGATORIO = 0).

    El perfil sale de obtener_usuario_actual (servidor), nunca del navegador.
    401 si no hay sesion valida; 403 si la cuenta tiene clave temporal o si la
    sesion es valida pero no es admin.
    """
    if normalizar_tipo_usuario(usuario.get("tipo")) != PERFIL_ADMINISTRADOR:
        logger.warning(
            "Acceso administrativo denegado usuario=%s tipo=%s",
            usuario.get("dni"), usuario.get("tipo"),
        )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=MENSAJE_SIN_PERMISO)
    return usuario
