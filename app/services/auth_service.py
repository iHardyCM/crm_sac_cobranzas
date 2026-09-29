"""Autenticacion del CRM.

Fuentes:
  - SISCOB.dbo.USUARIO: fuente oficial de existencia, estado laboral, perfil
    (TipoUsuario), nombre y cartera principal. Solo se autentica si Estado = 'A'.
    SISCOB.dbo.USUARIO.Clave NO se usa.
  - CobAuto.dbo.CRM_USUARIO_ACCESO: credencial propia del CRM (hash Argon2),
    cuenta activa, intentos fallidos y bloqueo temporal.

Reglas:
  - 5 intentos fallidos consecutivos bloquean la cuenta 15 minutos.
  - Mientras el bloqueo esta vigente se rechaza el login sin contar intentos.
  - Cuando el bloqueo vence, el contador arranca de nuevo (5 intentos nuevos).
  - Todas las fechas se toman del reloj de SQL Server (SYSDATETIME).
  - Nunca se registra la clave, el hash ni el token en el log.

Cambio de clave propia (POST /auth/cambiar-clave):
  - El usuario se identifica solo por el JWT; el DNI nunca viene del payload.
  - Politica minima: 8 a 128 caracteres, distinta del DNI y de la clave actual.
"""

import logging
import secrets
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, Iterator, Optional

from sqlalchemy import text

# db_siscob carga el .env (load_dotenv); debe importarse antes que security,
# que lee CRM_JWT_SECRET al importarse.
from app.core.db_siscob import engine_siscob
from app.core.security import crear_access_token, generar_hash_clave, verificar_clave


logger = logging.getLogger(__name__)

MAX_INTENTOS_FALLIDOS = 5
MINUTOS_BLOQUEO = 15

# Motivos internos: solo para el log, nunca se devuelven al navegador.
MOTIVO_OK = "OK"
MOTIVO_USUARIO_NO_VALIDO = "USUARIO_NO_VALIDO"      # no existe en SISCOB o Estado <> 'A'
MOTIVO_SIN_CUENTA_CRM = "SIN_CUENTA_CRM"
MOTIVO_CUENTA_INACTIVA = "CUENTA_INACTIVA"
MOTIVO_SIN_CLAVE = "SIN_CLAVE"
MOTIVO_BLOQUEADO = "BLOQUEADO"
MOTIVO_CLAVE_INCORRECTA = "CLAVE_INCORRECTA"


# ---------------------------------------------------------------------------
# Carteras del usuario (logica existente, sin cambios de regla)
# ---------------------------------------------------------------------------

def obtener_carteras_usuario(dni, idcartera):
    carteras = []

    if idcartera is not None:
        carteras.append(int(idcartera))

    carteras.extend(obtener_carteras_adicionales(dni))

    return sorted(set(carteras))


def asegurar_tabla_supervisor_cartera(conn):
    conn.execute(text("""
        IF OBJECT_ID('CobAuto.dbo.CRM_SUPERVISOR_CARTERA', 'U') IS NULL
        BEGIN
            CREATE TABLE CobAuto.dbo.CRM_SUPERVISOR_CARTERA (
                id INT IDENTITY(1,1) PRIMARY KEY,
                usuario VARCHAR(50) NOT NULL,
                idcartera INT NOT NULL,
                activo BIT NOT NULL DEFAULT 1,
                usuario_actualizacion VARCHAR(50) NULL,
                fecha_actualizacion DATETIME NOT NULL DEFAULT GETDATE()
            );

            CREATE INDEX IX_CRM_SUPERVISOR_CARTERA_USUARIO
            ON CobAuto.dbo.CRM_SUPERVISOR_CARTERA(usuario, activo);
        END
    """))


def obtener_carteras_adicionales(dni):
    try:
        query = text("""
            SELECT idcartera
            FROM CobAuto.dbo.CRM_SUPERVISOR_CARTERA WITH(NOLOCK)
            WHERE LTRIM(RTRIM(usuario)) = LTRIM(RTRIM(:dni))
              AND activo = 1
        """)

        with engine_siscob.begin() as conn:
            asegurar_tabla_supervisor_cartera(conn)
            rows = conn.execute(query, {"dni": str(dni).strip()}).fetchall()

        return [int(row.idcartera) for row in rows if row.idcartera is not None]
    except Exception:
        logger.exception("Error obteniendo carteras adicionales usuario=%s", dni)
        return []


# ---------------------------------------------------------------------------
# Identidad del usuario segun SISCOB
# ---------------------------------------------------------------------------

def _buscar_usuario_siscob_activo(dni: str) -> Optional[Dict]:
    """Devuelve el usuario de SISCOB solo si existe y tiene Estado = 'A'.

    No distingue entre "no existe" e "inactivo": ambos devuelven None.
    Las excepciones de BD se propagan (las maneja quien llama).
    """
    query = text("""
        SELECT TOP 1
            U.USUARIO,
            U.Nombres,
            U.Apellidos,
            U.TipoUsuario,
            U.IDCARTERA
        FROM SISCOB.DBO.USUARIO U WITH(NOLOCK)
        WHERE LTRIM(RTRIM(U.USUARIO)) = LTRIM(RTRIM(:dni))
          AND LTRIM(RTRIM(ISNULL(U.Estado, ''))) = 'A'
    """)

    with engine_siscob.connect() as conn:
        r = conn.execute(query, {"dni": dni}).fetchone()

    if not r:
        return None

    return {
        "usuario": str(r.USUARIO).strip(),
        "nombres": r.Nombres,
        "apellidos": r.Apellidos,
        "tipo": r.TipoUsuario,
        "idcartera": r.IDCARTERA,
    }


def obtener_identidad_usuario(dni: str) -> Optional[Dict]:
    """Identidad que el BACKEND reconoce hoy para un DNI.

    Se resuelve siempre desde el servidor (SISCOB + CRM_SUPERVISOR_CARTERA),
    nunca desde datos enviados por el navegador. Devuelve None si el usuario
    no existe o no esta activo en SISCOB.
    """
    r = _buscar_usuario_siscob_activo(dni)
    if not r:
        return None

    return _armar_identidad(r)


def _armar_identidad(r: Dict) -> Dict:
    """Mismo formato que devolvia el login anterior (dni, agente, tipo,
    idcartera, idcarteras) para no romper las pantallas actuales."""
    return {
        "dni": r["usuario"],
        "agente": f"{r['usuario']} - {r['nombres']} {r['apellidos']}",
        "tipo": r["tipo"],
        "idcartera": r["idcartera"],
        "idcarteras": obtener_carteras_usuario(r["usuario"], r["idcartera"]),
    }


# ---------------------------------------------------------------------------
# Cuenta de acceso CRM (CobAuto.dbo.CRM_USUARIO_ACCESO)
# ---------------------------------------------------------------------------

class RepositorioAcceso:
    """Operaciones sobre CRM_USUARIO_ACCESO dentro de UNA transaccion.

    La lectura toma UPDLOCK sobre la fila del usuario para que dos intentos
    simultaneos del mismo DNI no cuenten mal los fallos.
    """

    def __init__(self, conn):
        self.conn = conn

    def leer_cuenta_para_login(self, dni: str) -> Optional[Dict]:
        row = self.conn.execute(text("""
            SELECT TOP 1
                A.USUARIO,
                A.PASSWORD_HASH,
                A.FLG_ACTIVO,
                A.FLG_CAMBIO_OBLIGATORIO,
                A.INTENTOS_FALLIDOS,
                A.BLOQUEADO_HASTA,
                SYSDATETIME() AS AHORA
            FROM CobAuto.dbo.CRM_USUARIO_ACCESO A WITH (UPDLOCK, ROWLOCK)
            WHERE A.USUARIO = :dni
        """), {"dni": dni}).mappings().fetchone()

        return dict(row) if row else None

    def registrar_fallo(self, dni: str, intentos: int, bloqueado_hasta: Optional[datetime]) -> None:
        self.conn.execute(text("""
            UPDATE CobAuto.dbo.CRM_USUARIO_ACCESO
            SET INTENTOS_FALLIDOS = :intentos,
                BLOQUEADO_HASTA = :bloqueado_hasta,
                FECHA_ULTIMO_FALLO = SYSDATETIME()
            WHERE USUARIO = :dni
        """), {"dni": dni, "intentos": intentos, "bloqueado_hasta": bloqueado_hasta})

    def actualizar_clave_propia(self, dni: str, password_hash: str) -> None:
        """Guarda la clave definitiva elegida por el propio usuario."""
        self.conn.execute(text("""
            UPDATE CobAuto.dbo.CRM_USUARIO_ACCESO
            SET PASSWORD_HASH = :password_hash,
                FLG_CAMBIO_OBLIGATORIO = 0,
                INTENTOS_FALLIDOS = 0,
                BLOQUEADO_HASTA = NULL,
                FECHA_CAMBIO_CLAVE = SYSDATETIME(),
                USUARIO_ACTUALIZACION = :dni,
                FECHA_ACTUALIZACION = SYSDATETIME()
            WHERE USUARIO = :dni
        """), {"dni": dni, "password_hash": password_hash})

    def registrar_login_exitoso(self, dni: str) -> None:
        self.conn.execute(text("""
            UPDATE CobAuto.dbo.CRM_USUARIO_ACCESO
            SET INTENTOS_FALLIDOS = 0,
                BLOQUEADO_HASTA = NULL,
                FECHA_ULTIMO_LOGIN = SYSDATETIME()
            WHERE USUARIO = :dni
        """), {"dni": dni})


@contextmanager
def _transaccion_acceso() -> Iterator[RepositorioAcceso]:
    with engine_siscob.begin() as conn:
        yield RepositorioAcceso(conn)


def bloqueo_vigente(bloqueado_hasta: Optional[datetime], ahora: datetime) -> bool:
    return bloqueado_hasta is not None and bloqueado_hasta > ahora


def calcular_fallo(intentos_actuales: int, bloqueado_hasta: Optional[datetime], ahora: datetime):
    """Nuevo (intentos, bloqueado_hasta) tras una clave incorrecta.

    Si habia un bloqueo ya vencido, el ciclo empieza de cero. Al llegar a
    MAX_INTENTOS_FALLIDOS se bloquea MINUTOS_BLOQUEO minutos desde `ahora`.
    """
    base = int(intentos_actuales or 0)
    if bloqueado_hasta is not None and bloqueado_hasta <= ahora:
        base = 0

    intentos = base + 1
    if intentos >= MAX_INTENTOS_FALLIDOS:
        return intentos, ahora + timedelta(minutes=MINUTOS_BLOQUEO)
    return intentos, None


_HASH_SENUELO: Optional[str] = None


def _gastar_tiempo_de_verificacion(clave: str) -> None:
    """Verifica contra un hash senuelo para que un DNI inexistente tarde lo
    mismo que uno con cuenta, y no se pueda distinguir por tiempo de respuesta."""
    global _HASH_SENUELO
    if _HASH_SENUELO is None:
        _HASH_SENUELO = generar_hash_clave(secrets.token_urlsafe(16))
    verificar_clave(clave, _HASH_SENUELO)


# ---------------------------------------------------------------------------
# Autenticacion
# ---------------------------------------------------------------------------

@dataclass
class ResultadoAutenticacion:
    ok: bool
    motivo: str
    usuario: Optional[Dict] = None
    access_token: Optional[str] = None
    requiere_cambio_clave: bool = False


def autenticar_usuario(dni: str, clave: str) -> ResultadoAutenticacion:
    """Autentica DNI + clave.

    Flujo: SISCOB (Estado='A') -> cuenta CRM (activa, con hash, sin bloqueo)
    -> verificacion Argon2 -> registro de fallo o de exito -> token.

    Devuelve un ResultadoAutenticacion; `motivo` es solo para el log.
    Los errores tecnicos (BD caida, etc.) se propagan como excepcion.
    """
    dni = str(dni or "").strip()

    usuario_siscob = _buscar_usuario_siscob_activo(dni)
    if not usuario_siscob:
        _gastar_tiempo_de_verificacion(clave)
        logger.info("Login rechazado usuario=%s motivo=%s", dni, MOTIVO_USUARIO_NO_VALIDO)
        return ResultadoAutenticacion(ok=False, motivo=MOTIVO_USUARIO_NO_VALIDO)

    with _transaccion_acceso() as repo:
        cuenta = repo.leer_cuenta_para_login(dni)

        motivo = None
        if not cuenta:
            motivo = MOTIVO_SIN_CUENTA_CRM
        elif not cuenta.get("FLG_ACTIVO"):
            motivo = MOTIVO_CUENTA_INACTIVA
        elif not cuenta.get("PASSWORD_HASH"):
            motivo = MOTIVO_SIN_CLAVE

        if motivo:
            _gastar_tiempo_de_verificacion(clave)
            logger.info("Login rechazado usuario=%s motivo=%s", dni, motivo)
            return ResultadoAutenticacion(ok=False, motivo=motivo)

        ahora = cuenta["AHORA"]
        if bloqueo_vigente(cuenta.get("BLOQUEADO_HASTA"), ahora):
            logger.info(
                "Login rechazado usuario=%s motivo=%s bloqueado_hasta=%s",
                dni, MOTIVO_BLOQUEADO, cuenta.get("BLOQUEADO_HASTA"),
            )
            return ResultadoAutenticacion(ok=False, motivo=MOTIVO_BLOQUEADO)

        if not verificar_clave(clave, cuenta["PASSWORD_HASH"]):
            intentos, bloqueado_hasta = calcular_fallo(
                cuenta.get("INTENTOS_FALLIDOS"), cuenta.get("BLOQUEADO_HASTA"), ahora
            )
            repo.registrar_fallo(dni, intentos, bloqueado_hasta)
            if bloqueado_hasta:
                logger.warning(
                    "Cuenta bloqueada usuario=%s intentos=%s bloqueado_hasta=%s",
                    dni, intentos, bloqueado_hasta,
                )
            else:
                logger.info(
                    "Login rechazado usuario=%s motivo=%s intentos=%s",
                    dni, MOTIVO_CLAVE_INCORRECTA, intentos,
                )
            return ResultadoAutenticacion(ok=False, motivo=MOTIVO_CLAVE_INCORRECTA)

        repo.registrar_login_exitoso(dni)
        requiere_cambio = bool(cuenta.get("FLG_CAMBIO_OBLIGATORIO"))

    usuario = _armar_identidad(usuario_siscob)

    logger.info("Login correcto usuario=%s requiere_cambio_clave=%s", dni, requiere_cambio)

    return ResultadoAutenticacion(
        ok=True,
        motivo=MOTIVO_OK,
        usuario=usuario,
        access_token=crear_access_token(dni),
        requiere_cambio_clave=requiere_cambio,
    )


# ---------------------------------------------------------------------------
# Cambio de clave del propio usuario
# ---------------------------------------------------------------------------

LARGO_MINIMO_CLAVE = 8
LARGO_MAXIMO_CLAVE = 128


class ErrorCambioClave(ValueError):
    """Error de negocio del cambio de clave. El mensaje es seguro para mostrar."""


def validar_politica_clave(dni: str, clave_nueva: str) -> None:
    """Politica minima: largo 8-128 y distinta del DNI. Sin reglas arbitrarias."""
    if len(clave_nueva) < LARGO_MINIMO_CLAVE:
        raise ErrorCambioClave(f"La nueva contraseña debe tener al menos {LARGO_MINIMO_CLAVE} caracteres.")
    if len(clave_nueva) > LARGO_MAXIMO_CLAVE:
        raise ErrorCambioClave(f"La nueva contraseña no puede superar {LARGO_MAXIMO_CLAVE} caracteres.")
    if not clave_nueva.strip():
        raise ErrorCambioClave("La nueva contraseña no puede estar en blanco.")
    if clave_nueva.strip() == str(dni).strip():
        raise ErrorCambioClave("La nueva contraseña no puede ser igual a tu DNI.")


def cambiar_clave_propia(dni: str, clave_actual: str, clave_nueva: str, confirmacion: str) -> None:
    """Cambia la clave del usuario identificado por el JWT (`dni`).

    Lanza ErrorCambioClave ante datos invalidos (mensaje apto para el usuario).
    Los errores tecnicos se propagan como excepcion.
    """
    dni = str(dni or "").strip()
    clave_actual = clave_actual or ""
    clave_nueva = clave_nueva or ""
    confirmacion = confirmacion or ""

    if not clave_actual or not clave_nueva or not confirmacion:
        raise ErrorCambioClave("Completa la contraseña actual, la nueva y su confirmación.")
    if len(clave_actual) > LARGO_MAXIMO_CLAVE:
        raise ErrorCambioClave("La contraseña actual no es correcta.")
    if clave_nueva != confirmacion:
        raise ErrorCambioClave("La nueva contraseña y su confirmación no coinciden.")
    validar_politica_clave(dni, clave_nueva)

    with _transaccion_acceso() as repo:
        cuenta = repo.leer_cuenta_para_login(dni)
        if not cuenta or not cuenta.get("FLG_ACTIVO") or not cuenta.get("PASSWORD_HASH"):
            logger.info("Cambio de clave rechazado usuario=%s motivo=CUENTA_NO_DISPONIBLE", dni)
            raise ErrorCambioClave("Tu acceso no está disponible. Contacta al administrador.")

        if not verificar_clave(clave_actual, cuenta["PASSWORD_HASH"]):
            logger.info("Cambio de clave rechazado usuario=%s motivo=CLAVE_ACTUAL_INCORRECTA", dni)
            raise ErrorCambioClave("La contraseña actual no es correcta.")

        if clave_nueva == clave_actual:
            raise ErrorCambioClave("La nueva contraseña debe ser distinta de la actual.")

        repo.actualizar_clave_propia(dni, generar_hash_clave(clave_nueva))

    logger.info("Clave propia cambiada usuario=%s resultado=OK", dni)
