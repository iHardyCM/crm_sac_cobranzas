import os
from datetime import datetime, timedelta, timezone

import jwt
from dotenv import load_dotenv
from jwt import InvalidTokenError
from pwdlib import PasswordHash


_password_hash = PasswordHash.recommended()

# Carga el .env antes de leer CRM_JWT_SECRET y CRM_JWT_EXPIRE_MINUTES,
# sin depender del orden en que se importen los modulos.
load_dotenv()

JWT_SECRET = os.getenv("CRM_JWT_SECRET")
JWT_ALGORITHM = "HS256"
JWT_ISSUER = "crm-sac-cobranzas"
JWT_EXPIRE_MINUTES = int(os.getenv("CRM_JWT_EXPIRE_MINUTES", "480"))


if not JWT_SECRET:
    raise RuntimeError(
        "Falta configurar CRM_JWT_SECRET en las variables de entorno."
    )


def generar_hash_clave(clave: str) -> str:
    """
    Genera un hash seguro de la contraseña.
    La contraseña original nunca debe almacenarse.
    """
    return _password_hash.hash(clave)


def verificar_clave(clave: str, hash_guardado: str) -> bool:
    if not clave or not hash_guardado:
        return False

    try:
        return _password_hash.verify(clave, hash_guardado)
    except Exception:
        return False


def crear_access_token(dni: str) -> str:
    ahora = datetime.now(timezone.utc)
    expira = ahora + timedelta(minutes=JWT_EXPIRE_MINUTES)

    payload = {
        "sub": str(dni).strip(),
        "iat": ahora,
        "exp": expira,
        "iss": JWT_ISSUER,
        "tipo": "access",
    }

    return jwt.encode(
        payload,
        JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )


def decodificar_access_token(token: str) -> dict | None:
    try:
        payload = jwt.decode(
            token,
            JWT_SECRET,
            algorithms=[JWT_ALGORITHM],
            issuer=JWT_ISSUER,
        )

        if payload.get("tipo") != "access":
            return None

        if not payload.get("sub"):
            return None

        return payload

    except InvalidTokenError:
        return None