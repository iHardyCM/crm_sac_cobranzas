"""Administracion de accesos al CRM (solo ADMINISTRADOR).

Fuentes:
  - SISCOB.dbo.USUARIO: usuarios, perfil, cartera y Estado (solo 'A').
  - CobAuto.dbo.CRM_USUARIO_ACCESO: cuenta CRM, hash, bloqueo y auditoria.

Reglas:
  - Las claves temporales se generan con `secrets`, se devuelven UNA sola vez
    y solo se guarda su hash Argon2. Nunca se registran en el log.
  - Habilitar / rehabilitar / resetear dejan FLG_CAMBIO_OBLIGATORIO = 1,
    INTENTOS_FALLIDOS = 0, BLOQUEADO_HASTA = NULL y FECHA_CAMBIO_CLAVE = NULL
    (se completa cuando el usuario crea su clave definitiva).
  - Deshabilitar no borra la cuenta: FLG_ACTIVO = 0. La revocacion es inmediata
    porque obtener_usuario_actual revalida FLG_ACTIVO en cada peticion.
  - La auditoria (USUARIO_CREACION / USUARIO_ACTUALIZACION) sale del
    administrador autenticado por JWT, nunca del payload.
"""

import logging
import secrets
from contextlib import contextmanager
from datetime import datetime
from typing import Dict, Iterator, List, Optional

from sqlalchemy import text

from app.core.db_siscob import engine_siscob
from app.core.security import generar_hash_clave
from app.services import auth_service


logger = logging.getLogger(__name__)

LIMITE_MAXIMO_LISTADO = 200
LARGO_CLAVE_TEMPORAL = 12
# Sin caracteres que se confunden al dictarlos o copiarlos (0/O, 1/l/I).
ALFABETO_CLAVE_TEMPORAL = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789"

ESTADO_SIN_ACCESO = "SIN_ACCESO"
ESTADO_ACTIVO = "ACTIVO"
ESTADO_CAMBIO_OBLIGATORIO = "CAMBIO_OBLIGATORIO"
ESTADO_BLOQUEADO = "BLOQUEADO"
ESTADO_DESHABILITADO = "DESHABILITADO"
ESTADO_SIN_CLAVE = "SIN_CLAVE"


class ErrorAccesos(Exception):
    """Error de negocio. El mensaje es seguro para mostrar al administrador."""

    def __init__(self, mensaje: str, status_code: int = 400):
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.status_code = status_code


# ---------------------------------------------------------------------------
# Utilidades puras
# ---------------------------------------------------------------------------

def generar_clave_temporal() -> str:
    """Clave temporal aleatoria (CSPRNG). Siempre incluye mayuscula, minuscula y digito."""
    while True:
        clave = "".join(secrets.choice(ALFABETO_CLAVE_TEMPORAL) for _ in range(LARGO_CLAVE_TEMPORAL))
        if (any(c.isupper() for c in clave)
                and any(c.islower() for c in clave)
                and any(c.isdigit() for c in clave)):
            return clave


def validar_dni(dni) -> str:
    dni = str(dni or "").strip()
    if len(dni) != 8 or not dni.isdigit():
        raise ErrorAccesos("El DNI debe tener 8 digitos.", 400)
    return dni


def derivar_estado_acceso(cuenta: Optional[Dict], ahora: datetime) -> str:
    """Estado de acceso a partir de la fila de CRM_USUARIO_ACCESO (o None)."""
    if not cuenta or cuenta.get("USUARIO") is None:
        return ESTADO_SIN_ACCESO
    if not cuenta.get("FLG_ACTIVO"):
        return ESTADO_DESHABILITADO
    if auth_service.bloqueo_vigente(cuenta.get("BLOQUEADO_HASTA"), ahora):
        return ESTADO_BLOQUEADO
    if not cuenta.get("TIENE_CLAVE"):
        return ESTADO_SIN_CLAVE
    if cuenta.get("FLG_CAMBIO_OBLIGATORIO"):
        return ESTADO_CAMBIO_OBLIGATORIO
    return ESTADO_ACTIVO


def _texto_busqueda_like(q: str) -> str:
    """Escapa comodines de LIKE para que la busqueda sea literal."""
    escapado = q.replace("[", "[[]").replace("%", "[%]").replace("_", "[_]")
    return f"%{escapado}%"


def _fecha(valor) -> Optional[str]:
    return valor.isoformat() if isinstance(valor, datetime) else valor


def _armar_fila_listado(row: Dict) -> Dict:
    ahora = row["AHORA"]
    tiene_acceso = row.get("USUARIO_ACCESO") is not None
    cuenta = {
        "USUARIO": row.get("USUARIO_ACCESO"),
        "FLG_ACTIVO": row.get("FLG_ACTIVO"),
        "FLG_CAMBIO_OBLIGATORIO": row.get("FLG_CAMBIO_OBLIGATORIO"),
        "BLOQUEADO_HASTA": row.get("BLOQUEADO_HASTA"),
        "TIENE_CLAVE": row.get("TIENE_CLAVE"),
    } if tiene_acceso else None

    return {
        "dni": str(row["USUARIO"]).strip(),
        "nombres": row.get("Nombres"),
        "apellidos": row.get("Apellidos"),
        "tipo": row.get("TipoUsuario"),
        "idcartera": row.get("IDCARTERA"),
        "estado_siscob": str(row.get("Estado") or "").strip(),
        "tiene_acceso": tiene_acceso,
        "flg_activo": bool(row.get("FLG_ACTIVO")) if tiene_acceso else False,
        "flg_cambio_obligatorio": bool(row.get("FLG_CAMBIO_OBLIGATORIO")) if tiene_acceso else False,
        "intentos_fallidos": int(row.get("INTENTOS_FALLIDOS") or 0) if tiene_acceso else 0,
        "bloqueado_hasta": _fecha(row.get("BLOQUEADO_HASTA")),
        "fecha_ultimo_login": _fecha(row.get("FECHA_ULTIMO_LOGIN")),
        "fecha_ultimo_fallo": _fecha(row.get("FECHA_ULTIMO_FALLO")),
        "estado_acceso": derivar_estado_acceso(cuenta, ahora),
    }


# ---------------------------------------------------------------------------
# Acceso a datos
# ---------------------------------------------------------------------------

class RepositorioAdminAccesos:
    """Operaciones sobre CRM_USUARIO_ACCESO dentro de UNA transaccion."""

    def __init__(self, conn):
        self.conn = conn

    def listar_usuarios(self, q: Optional[str], limite: int) -> List[Dict]:
        filtro = ""
        params = {"limite": int(limite)}
        if q:
            filtro = """
              AND (
                    LTRIM(RTRIM(U.USUARIO)) LIKE :q
                 OR U.Nombres LIKE :q
                 OR U.Apellidos LIKE :q
                 OR (ISNULL(U.Nombres, '') + ' ' + ISNULL(U.Apellidos, '')) LIKE :q
              )"""
            params["q"] = _texto_busqueda_like(q)

        rows = self.conn.execute(text(f"""
            SELECT TOP (:limite)
                LTRIM(RTRIM(U.USUARIO)) AS USUARIO,
                U.Nombres,
                U.Apellidos,
                U.TipoUsuario,
                U.IDCARTERA,
                U.Estado,
                A.USUARIO AS USUARIO_ACCESO,
                A.FLG_ACTIVO,
                A.FLG_CAMBIO_OBLIGATORIO,
                A.INTENTOS_FALLIDOS,
                A.BLOQUEADO_HASTA,
                A.FECHA_ULTIMO_LOGIN,
                A.FECHA_ULTIMO_FALLO,
                CASE WHEN A.PASSWORD_HASH IS NULL THEN 0 ELSE 1 END AS TIENE_CLAVE,
                SYSDATETIME() AS AHORA
            FROM SISCOB.dbo.USUARIO U WITH (NOLOCK)
            LEFT JOIN CobAuto.dbo.CRM_USUARIO_ACCESO A
                ON A.USUARIO COLLATE DATABASE_DEFAULT = LTRIM(RTRIM(U.USUARIO)) COLLATE DATABASE_DEFAULT
            WHERE LTRIM(RTRIM(ISNULL(U.Estado, ''))) = 'A'
            {filtro}
            ORDER BY U.Apellidos, U.Nombres, U.USUARIO
        """), params).mappings().all()
        return [dict(r) for r in rows]

    def leer_cuenta(self, dni: str) -> Optional[Dict]:
        """Lee la cuenta bloqueando la fila (y el hueco si no existe) hasta el commit."""
        row = self.conn.execute(text("""
            SELECT TOP 1
                USUARIO, FLG_ACTIVO, FLG_CAMBIO_OBLIGATORIO,
                INTENTOS_FALLIDOS, BLOQUEADO_HASTA
            FROM CobAuto.dbo.CRM_USUARIO_ACCESO WITH (UPDLOCK, HOLDLOCK)
            WHERE USUARIO = :dni
        """), {"dni": dni}).mappings().fetchone()
        return dict(row) if row else None

    def crear_cuenta(self, dni: str, password_hash: str, admin: str) -> None:
        self.conn.execute(text("""
            INSERT INTO CobAuto.dbo.CRM_USUARIO_ACCESO
                (USUARIO, PASSWORD_HASH, FLG_ACTIVO, FLG_CAMBIO_OBLIGATORIO,
                 INTENTOS_FALLIDOS, BLOQUEADO_HASTA, FECHA_CAMBIO_CLAVE, USUARIO_CREACION)
            VALUES
                (:dni, :password_hash, 1, 1, 0, NULL, NULL, :admin)
        """), {"dni": dni, "password_hash": password_hash, "admin": admin})

    def asignar_clave_temporal(self, dni: str, password_hash: str, admin: str) -> None:
        """Rehabilitar o resetear: nueva clave temporal, cuenta activa y sin bloqueo."""
        self.conn.execute(text("""
            UPDATE CobAuto.dbo.CRM_USUARIO_ACCESO
            SET PASSWORD_HASH = :password_hash,
                FLG_ACTIVO = 1,
                FLG_CAMBIO_OBLIGATORIO = 1,
                INTENTOS_FALLIDOS = 0,
                BLOQUEADO_HASTA = NULL,
                FECHA_CAMBIO_CLAVE = NULL,
                USUARIO_ACTUALIZACION = :admin,
                FECHA_ACTUALIZACION = SYSDATETIME()
            WHERE USUARIO = :dni
        """), {"dni": dni, "password_hash": password_hash, "admin": admin})

    def desbloquear(self, dni: str, admin: str) -> None:
        self.conn.execute(text("""
            UPDATE CobAuto.dbo.CRM_USUARIO_ACCESO
            SET INTENTOS_FALLIDOS = 0,
                BLOQUEADO_HASTA = NULL,
                USUARIO_ACTUALIZACION = :admin,
                FECHA_ACTUALIZACION = SYSDATETIME()
            WHERE USUARIO = :dni
        """), {"dni": dni, "admin": admin})

    def deshabilitar(self, dni: str, admin: str) -> None:
        self.conn.execute(text("""
            UPDATE CobAuto.dbo.CRM_USUARIO_ACCESO
            SET FLG_ACTIVO = 0,
                USUARIO_ACTUALIZACION = :admin,
                FECHA_ACTUALIZACION = SYSDATETIME()
            WHERE USUARIO = :dni
        """), {"dni": dni, "admin": admin})


@contextmanager
def _transaccion() -> Iterator[RepositorioAdminAccesos]:
    with engine_siscob.begin() as conn:
        yield RepositorioAdminAccesos(conn)


def _registrar(accion: str, admin: str, objetivo: str, resultado: str) -> None:
    logger.info(
        "Admin accesos accion=%s admin=%s objetivo=%s resultado=%s",
        accion, admin, objetivo, resultado,
    )


def _exigir_usuario_siscob_activo(dni: str) -> Dict:
    usuario = auth_service._buscar_usuario_siscob_activo(dni)
    if not usuario:
        raise ErrorAccesos("El usuario no existe o no esta activo en SISCOB.", 404)
    return usuario


def _exigir_cuenta(repo: RepositorioAdminAccesos, dni: str) -> Dict:
    cuenta = repo.leer_cuenta(dni)
    if not cuenta:
        raise ErrorAccesos("El usuario no tiene acceso CRM. Usa Habilitar acceso.", 404)
    return cuenta


# ---------------------------------------------------------------------------
# Casos de uso
# ---------------------------------------------------------------------------

def listar_usuarios(q: Optional[str] = None, limite: int = 100) -> List[Dict]:
    q = (q or "").strip()[:100] or None
    limite = max(1, min(int(limite or 100), LIMITE_MAXIMO_LISTADO))
    with _transaccion() as repo:
        filas = repo.listar_usuarios(q, limite)
    return [_armar_fila_listado(f) for f in filas]


def habilitar_acceso(dni: str, admin: str) -> Dict:
    """Crea la cuenta o reactiva una deshabilitada, con clave temporal nueva.

    409 si la cuenta ya esta activa (para eso existe reset-clave).
    """
    dni = validar_dni(dni)
    _exigir_usuario_siscob_activo(dni)
    clave_temporal = generar_clave_temporal()

    with _transaccion() as repo:
        cuenta = repo.leer_cuenta(dni)
        if cuenta and cuenta.get("FLG_ACTIVO"):
            _registrar("HABILITAR", admin, dni, "RECHAZADO_YA_ACTIVA")
            raise ErrorAccesos("La cuenta ya esta habilitada. Usa Resetear clave si necesita una nueva.", 409)

        password_hash = generar_hash_clave(clave_temporal)
        if cuenta:
            repo.asignar_clave_temporal(dni, password_hash, admin)
            accion = "REHABILITAR"
        else:
            repo.crear_cuenta(dni, password_hash, admin)
            accion = "HABILITAR"

    _registrar(accion, admin, dni, "OK")
    return {
        "ok": True,
        "dni": dni,
        "accion": accion,
        "clave_temporal": clave_temporal,
        "requiere_cambio_clave": True,
    }


def resetear_clave(dni: str, admin: str) -> Dict:
    """Nueva clave temporal para una cuenta activa. La anterior deja de servir."""
    dni = validar_dni(dni)
    _exigir_usuario_siscob_activo(dni)
    clave_temporal = generar_clave_temporal()

    with _transaccion() as repo:
        cuenta = _exigir_cuenta(repo, dni)
        if not cuenta.get("FLG_ACTIVO"):
            _registrar("RESET_CLAVE", admin, dni, "RECHAZADO_DESHABILITADA")
            raise ErrorAccesos("La cuenta esta deshabilitada. Usa Habilitar acceso.", 409)
        repo.asignar_clave_temporal(dni, generar_hash_clave(clave_temporal), admin)

    _registrar("RESET_CLAVE", admin, dni, "OK")
    return {
        "ok": True,
        "dni": dni,
        "accion": "RESET_CLAVE",
        "clave_temporal": clave_temporal,
        "requiere_cambio_clave": True,
    }


def desbloquear(dni: str, admin: str) -> Dict:
    dni = validar_dni(dni)
    with _transaccion() as repo:
        _exigir_cuenta(repo, dni)
        repo.desbloquear(dni, admin)

    _registrar("DESBLOQUEAR", admin, dni, "OK")
    return {"ok": True, "dni": dni, "accion": "DESBLOQUEAR"}


def deshabilitar(dni: str, admin: str) -> Dict:
    """FLG_ACTIVO = 0. No borra la cuenta ni su historial.

    `admin` es el DNI del administrador autenticado (JWT): no puede
    deshabilitar su propia cuenta.
    """
    dni = validar_dni(dni)
    if dni == str(admin or "").strip():
        _registrar("DESHABILITAR", admin, dni, "RECHAZADO_PROPIA_CUENTA")
        raise ErrorAccesos("No puedes deshabilitar tu propia cuenta.", 409)
    with _transaccion() as repo:
        cuenta = _exigir_cuenta(repo, dni)
        if not cuenta.get("FLG_ACTIVO"):
            _registrar("DESHABILITAR", admin, dni, "SIN_CAMBIO_YA_DESHABILITADA")
            return {"ok": True, "dni": dni, "accion": "DESHABILITAR", "sin_cambios": True}
        repo.deshabilitar(dni, admin)

    _registrar("DESHABILITAR", admin, dni, "OK")
    return {"ok": True, "dni": dni, "accion": "DESHABILITAR"}
