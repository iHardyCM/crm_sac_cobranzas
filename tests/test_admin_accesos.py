"""Tests de administracion de accesos y cambio de clave propia.

No usan la base de datos: SISCOB y CRM_USUARIO_ACCESO se simulan en memoria.
Ejecutar desde la raiz del proyecto:

    python -m unittest tests.test_admin_accesos -v
"""

import os
import string
import unittest
from contextlib import contextmanager
from datetime import datetime, timedelta
from unittest.mock import patch

# Debe existir antes de importar app.core.security (lo lee al importarse).
os.environ.setdefault("CRM_JWT_SECRET", "secreto-solo-para-tests-no-productivo-0123456789")

from fastapi import HTTPException, Response  # noqa: E402
from fastapi.security import HTTPAuthorizationCredentials  # noqa: E402

from app.core import auth_dependencies, security  # noqa: E402
from app.services import admin_accesos_service as servicio  # noqa: E402
from app.services import auth_service  # noqa: E402
from app.api import routes_admin_accesos, routes_auth  # noqa: E402


AHORA = datetime(2026, 9, 29, 10, 0, 0)
ADMIN = "11111111"
GESTOR = "22222222"
OBJETIVO = "33333333"
INACTIVO = "44444444"   # no aparece en SISCOB activo


class BaseFalsa:
    """Implementa en memoria los repositorios de auth_service y admin_accesos_service."""

    def __init__(self, usuarios, cuentas, ahora):
        self.usuarios = usuarios
        self.cuentas = cuentas
        self.ahora = ahora

    # --- RepositorioAcceso (login / cambio de clave) ---
    def leer_cuenta_para_login(self, dni):
        cuenta = self.cuentas.get(dni)
        return {**cuenta, "AHORA": self.ahora} if cuenta else None

    def registrar_fallo(self, dni, intentos, bloqueado_hasta):
        self.cuentas[dni].update(INTENTOS_FALLIDOS=intentos, BLOQUEADO_HASTA=bloqueado_hasta,
                                 FECHA_ULTIMO_FALLO=self.ahora)

    def registrar_login_exitoso(self, dni):
        self.cuentas[dni].update(INTENTOS_FALLIDOS=0, BLOQUEADO_HASTA=None, FECHA_ULTIMO_LOGIN=self.ahora)

    def actualizar_clave_propia(self, dni, password_hash):
        self.cuentas[dni].update(
            PASSWORD_HASH=password_hash, FLG_CAMBIO_OBLIGATORIO=False, INTENTOS_FALLIDOS=0,
            BLOQUEADO_HASTA=None, FECHA_CAMBIO_CLAVE=self.ahora,
            USUARIO_ACTUALIZACION=dni, FECHA_ACTUALIZACION=self.ahora,
        )

    # --- RepositorioAdminAccesos ---
    def listar_usuarios(self, q, limite):
        filas = []
        for dni, u in sorted(self.usuarios.items()):
            texto = f"{dni} {u['nombres']} {u['apellidos']}".lower()
            if q and q.lower() not in texto:
                continue
            c = self.cuentas.get(dni) or {}
            filas.append({
                "USUARIO": dni, "Nombres": u["nombres"], "Apellidos": u["apellidos"],
                "TipoUsuario": u["tipo"], "IDCARTERA": u["idcartera"], "Estado": "A",
                "USUARIO_ACCESO": c.get("USUARIO"), "FLG_ACTIVO": c.get("FLG_ACTIVO"),
                "FLG_CAMBIO_OBLIGATORIO": c.get("FLG_CAMBIO_OBLIGATORIO"),
                "INTENTOS_FALLIDOS": c.get("INTENTOS_FALLIDOS"), "BLOQUEADO_HASTA": c.get("BLOQUEADO_HASTA"),
                "FECHA_ULTIMO_LOGIN": c.get("FECHA_ULTIMO_LOGIN"), "FECHA_ULTIMO_FALLO": c.get("FECHA_ULTIMO_FALLO"),
                "TIENE_CLAVE": 1 if c.get("PASSWORD_HASH") else 0, "AHORA": self.ahora,
            })
        return filas[:limite]

    def leer_cuenta(self, dni):
        cuenta = self.cuentas.get(dni)
        return dict(cuenta) if cuenta else None

    def crear_cuenta(self, dni, password_hash, admin):
        self.cuentas[dni] = {
            "USUARIO": dni, "PASSWORD_HASH": password_hash, "FLG_ACTIVO": True,
            "FLG_CAMBIO_OBLIGATORIO": True, "INTENTOS_FALLIDOS": 0, "BLOQUEADO_HASTA": None,
            "FECHA_CAMBIO_CLAVE": None, "USUARIO_CREACION": admin, "USUARIO_ACTUALIZACION": None,
        }

    def asignar_clave_temporal(self, dni, password_hash, admin):
        self.cuentas[dni].update(
            PASSWORD_HASH=password_hash, FLG_ACTIVO=True, FLG_CAMBIO_OBLIGATORIO=True,
            INTENTOS_FALLIDOS=0, BLOQUEADO_HASTA=None, FECHA_CAMBIO_CLAVE=None,
            USUARIO_ACTUALIZACION=admin, FECHA_ACTUALIZACION=self.ahora,
        )

    def desbloquear(self, dni, admin):
        self.cuentas[dni].update(INTENTOS_FALLIDOS=0, BLOQUEADO_HASTA=None,
                                 USUARIO_ACTUALIZACION=admin, FECHA_ACTUALIZACION=self.ahora)

    def deshabilitar(self, dni, admin):
        self.cuentas[dni].update(FLG_ACTIVO=False, USUARIO_ACTUALIZACION=admin, FECHA_ACTUALIZACION=self.ahora)


class BaseAccesosTest(unittest.TestCase):
    CLAVE_ADMIN = "Clave-Admin#2026"
    CLAVE_GESTOR = "Clave-Gestor#2026"

    @classmethod
    def setUpClass(cls):
        cls.hash_admin = security.generar_hash_clave(cls.CLAVE_ADMIN)
        cls.hash_gestor = security.generar_hash_clave(cls.CLAVE_GESTOR)

    def setUp(self):
        self.usuarios = {
            ADMIN: {"usuario": ADMIN, "nombres": "ANA", "apellidos": "ADMIN", "tipo": "Administrador ", "idcartera": 124},
            GESTOR: {"usuario": GESTOR, "nombres": "GINO", "apellidos": "GESTOR", "tipo": "GESTOR", "idcartera": 112},
            OBJETIVO: {"usuario": OBJETIVO, "nombres": "OLGA", "apellidos": "OBJETIVO", "tipo": "GESTOR", "idcartera": 117},
        }
        base = {"FLG_ACTIVO": True, "FLG_CAMBIO_OBLIGATORIO": False, "INTENTOS_FALLIDOS": 0,
                "BLOQUEADO_HASTA": None, "FECHA_CAMBIO_CLAVE": None}
        self.cuentas = {
            ADMIN: {"USUARIO": ADMIN, "PASSWORD_HASH": self.hash_admin, **base},
            GESTOR: {"USUARIO": GESTOR, "PASSWORD_HASH": self.hash_gestor, **base},
            INACTIVO: {"USUARIO": INACTIVO, "PASSWORD_HASH": self.hash_gestor, **base},
        }
        self.bd = BaseFalsa(self.usuarios, self.cuentas, AHORA)

        @contextmanager
        def transaccion():
            yield self.bd

        def identidad(dni):
            return auth_service._armar_identidad(self.usuarios[dni]) if dni in self.usuarios else None

        self.parches = [
            patch.object(auth_service, "_transaccion_acceso", transaccion),
            patch.object(servicio, "_transaccion", transaccion),
            patch.object(auth_service, "_buscar_usuario_siscob_activo", side_effect=lambda d: self.usuarios.get(d)),
            patch.object(auth_service, "obtener_carteras_usuario", side_effect=lambda d, i: [int(i)]),
            patch.object(auth_dependencies, "cuenta_crm_activa",
                         side_effect=lambda d: bool(self.cuentas.get(d, {}).get("FLG_ACTIVO"))),
            patch.object(auth_dependencies, "obtener_identidad_usuario", side_effect=identidad),
            patch.object(auth_dependencies, "cuenta_requiere_cambio_clave",
                         side_effect=lambda d: bool(self.cuentas.get(d, {}).get("FLG_CAMBIO_OBLIGATORIO", True))),
        ]
        for p in self.parches:
            p.start()

    def tearDown(self):
        for p in self.parches:
            p.stop()

    # --- utilidades ---
    def usuario_actual(self, dni):
        token = security.crear_access_token(dni)
        return auth_dependencies.obtener_usuario_actual(
            HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        )

    def admin(self):
        # Misma cadena que FastAPI: obtener_usuario_actual -> requiere_clave_definitiva -> requiere_administrador.
        return auth_dependencies.requiere_administrador(
            auth_dependencies.requiere_clave_definitiva(self.usuario_actual(ADMIN))
        )


class AutorizacionAdminTests(BaseAccesosTest):
    def test_no_administrador_recibe_403(self):
        with self.assertRaises(HTTPException) as ctx:
            auth_dependencies.requiere_administrador(self.usuario_actual(GESTOR))
        self.assertEqual(ctx.exception.status_code, 403)

    def test_administrador_se_reconoce_normalizado_desde_siscob(self):
        # SISCOB trae "Administrador " (minusculas y espacio): igual es ADMINISTRADOR.
        self.assertEqual(self.admin()["dni"], ADMIN)

    def test_perfil_sale_del_servidor_no_del_token(self):
        # Si SISCOB le quita el perfil, pierde el acceso aunque el token siga vigente.
        token_usuario = self.usuario_actual(ADMIN)
        self.usuarios[ADMIN]["tipo"] = "GESTOR"
        with self.assertRaises(HTTPException) as ctx:
            auth_dependencies.requiere_administrador(self.usuario_actual(ADMIN))
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertEqual(token_usuario["dni"], ADMIN)


class CambioObligatorioBackendTests(BaseAccesosTest):
    NUEVA = "ClaveDefinitiva2026"

    def test_admin_con_cambio_obligatorio_recibe_403(self):
        self.cuentas[ADMIN]["FLG_CAMBIO_OBLIGATORIO"] = True

        with self.assertRaises(HTTPException) as ctx:
            self.admin()
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertEqual(ctx.exception.detail, "Debes cambiar tu contraseña antes de continuar.")

    def test_con_cambio_obligatorio_puede_usar_me_y_cambiar_clave(self):
        self.cuentas[ADMIN]["FLG_CAMBIO_OBLIGATORIO"] = True

        # /auth/me y /auth/cambiar-clave solo dependen de obtener_usuario_actual.
        self.assertEqual(routes_auth.me(usuario=self.usuario_actual(ADMIN))["dni"], ADMIN)
        payload = routes_auth.CambiarClaveRequest(
            clave_actual=self.CLAVE_ADMIN, clave_nueva=self.NUEVA, confirmacion=self.NUEVA
        )
        routes_auth.cambiar_clave(payload, usuario=self.usuario_actual(ADMIN))

        self.assertFalse(self.cuentas[ADMIN]["FLG_CAMBIO_OBLIGATORIO"])
        self.assertEqual(self.admin()["dni"], ADMIN)
        resp = routes_admin_accesos.listar_usuarios(Response(), q=None, limite=10, admin=self.admin())
        self.assertTrue(resp["data"])

    def test_auth_me_informa_cambio_obligatorio_desde_la_bd(self):
        self.assertFalse(routes_auth.me(usuario=self.usuario_actual(ADMIN))["requiere_cambio_clave"])
        self.cuentas[ADMIN]["FLG_CAMBIO_OBLIGATORIO"] = True
        self.assertTrue(routes_auth.me(usuario=self.usuario_actual(ADMIN))["requiere_cambio_clave"])

    def test_requiere_administrador_depende_de_clave_definitiva(self):
        import inspect
        dependencia = inspect.signature(auth_dependencies.requiere_administrador).parameters["usuario"].default
        self.assertIs(dependencia.dependency, auth_dependencies.requiere_clave_definitiva)


class ListadoTests(BaseAccesosTest):
    def test_administrador_puede_listar_sin_datos_sensibles(self):
        resp = routes_admin_accesos.listar_usuarios(Response(), q=None, limite=100, admin=self.admin())

        filas = {f["dni"]: f for f in resp["data"]}
        self.assertEqual(set(filas), {ADMIN, GESTOR, OBJETIVO})
        self.assertEqual(filas[OBJETIVO]["estado_acceso"], "SIN_ACCESO")
        self.assertFalse(filas[OBJETIVO]["tiene_acceso"])
        self.assertEqual(filas[GESTOR]["estado_acceso"], "ACTIVO")
        texto = str(resp)
        self.assertNotIn("PASSWORD_HASH", texto)
        self.assertNotIn(self.hash_gestor, texto)

    def test_busqueda_por_nombre(self):
        data = routes_admin_accesos.listar_usuarios(Response(), q="olga", limite=100, admin=self.admin())["data"]
        self.assertEqual([f["dni"] for f in data], [OBJETIVO])

    def test_estados_derivados(self):
        d = servicio.derivar_estado_acceso
        base = {"USUARIO": "x", "FLG_ACTIVO": True, "FLG_CAMBIO_OBLIGATORIO": False,
                "BLOQUEADO_HASTA": None, "TIENE_CLAVE": 1}
        self.assertEqual(d(None, AHORA), "SIN_ACCESO")
        self.assertEqual(d(base, AHORA), "ACTIVO")
        self.assertEqual(d({**base, "FLG_CAMBIO_OBLIGATORIO": True}, AHORA), "CAMBIO_OBLIGATORIO")
        self.assertEqual(d({**base, "BLOQUEADO_HASTA": AHORA + timedelta(minutes=5)}, AHORA), "BLOQUEADO")
        self.assertEqual(d({**base, "BLOQUEADO_HASTA": AHORA - timedelta(minutes=5)}, AHORA), "ACTIVO")
        self.assertEqual(d({**base, "FLG_ACTIVO": False}, AHORA), "DESHABILITADO")
        self.assertEqual(d({**base, "TIENE_CLAVE": 0}, AHORA), "SIN_CLAVE")

    def test_escapa_comodines_like(self):
        self.assertEqual(servicio._texto_busqueda_like("50%_a[b"), "%50[%][_]a[[]b%")


class HabilitarTests(BaseAccesosTest):
    def test_habilitar_crea_cuenta_con_clave_temporal_hasheada(self):
        resp = routes_admin_accesos.habilitar_acceso(OBJETIVO, Response(), admin=self.admin())

        clave = resp["clave_temporal"]
        cuenta = self.cuentas[OBJETIVO]
        self.assertTrue(resp["ok"])
        self.assertTrue(resp["requiere_cambio_clave"])
        self.assertEqual(resp["accion"], "HABILITAR")
        self.assertTrue(cuenta["FLG_ACTIVO"])
        self.assertTrue(cuenta["FLG_CAMBIO_OBLIGATORIO"])
        self.assertEqual(cuenta["INTENTOS_FALLIDOS"], 0)
        self.assertIsNone(cuenta["BLOQUEADO_HASTA"])
        self.assertEqual(cuenta["USUARIO_CREACION"], ADMIN)
        # Solo hash, nunca el texto plano.
        self.assertNotEqual(cuenta["PASSWORD_HASH"], clave)
        self.assertNotIn(clave, cuenta["PASSWORD_HASH"])
        self.assertTrue(cuenta["PASSWORD_HASH"].startswith("$argon2"))
        self.assertTrue(security.verificar_clave(clave, cuenta["PASSWORD_HASH"]))
        self.assertNotIn("PASSWORD_HASH", str(resp))

    def test_clave_temporal_segura(self):
        claves = {servicio.generar_clave_temporal() for _ in range(50)}
        self.assertEqual(len(claves), 50)
        for clave in claves:
            self.assertEqual(len(clave), servicio.LARGO_CLAVE_TEMPORAL)
            self.assertTrue(set(clave) <= set(servicio.ALFABETO_CLAVE_TEMPORAL))
            self.assertTrue(any(c in string.ascii_uppercase for c in clave))
            self.assertTrue(any(c in string.ascii_lowercase for c in clave))
            self.assertTrue(any(c in string.digits for c in clave))
            self.assertNotIn(OBJETIVO, clave)

    def test_clave_temporal_usa_secrets(self):
        with patch.object(servicio.secrets, "choice", side_effect=list("Ab3")) as choice, \
             patch.object(servicio, "LARGO_CLAVE_TEMPORAL", 3):
            self.assertEqual(servicio.generar_clave_temporal(), "Ab3")
        self.assertEqual(choice.call_count, 3)

    def test_habilitar_usuario_no_activo_en_siscob_da_404(self):
        with self.assertRaises(HTTPException) as ctx:
            routes_admin_accesos.habilitar_acceso(INACTIVO, Response(), admin=self.admin())
        self.assertEqual(ctx.exception.status_code, 404)

    def test_habilitar_cuenta_ya_activa_da_409(self):
        with self.assertRaises(HTTPException) as ctx:
            routes_admin_accesos.habilitar_acceso(GESTOR, Response(), admin=self.admin())
        self.assertEqual(ctx.exception.status_code, 409)

    def test_dni_invalido_da_400(self):
        with self.assertRaises(HTTPException) as ctx:
            routes_admin_accesos.habilitar_acceso("12AB", Response(), admin=self.admin())
        self.assertEqual(ctx.exception.status_code, 400)

    def test_respuesta_con_clave_no_se_cachea(self):
        response = Response()
        routes_admin_accesos.habilitar_acceso(OBJETIVO, response, admin=self.admin())
        self.assertEqual(response.headers["Cache-Control"], "no-store")


class ResetDesbloqueoDeshabilitarTests(BaseAccesosTest):
    def test_reset_genera_clave_distinta_y_la_anterior_deja_de_servir(self):
        clave1 = routes_admin_accesos.habilitar_acceso(OBJETIVO, Response(), admin=self.admin())["clave_temporal"]
        self.cuentas[OBJETIVO].update(INTENTOS_FALLIDOS=5, BLOQUEADO_HASTA=AHORA + timedelta(minutes=10),
                                      FECHA_CAMBIO_CLAVE=AHORA)

        resp = routes_admin_accesos.resetear_clave(OBJETIVO, Response(), admin=self.admin())

        clave2 = resp["clave_temporal"]
        cuenta = self.cuentas[OBJETIVO]
        self.assertNotEqual(clave1, clave2)
        self.assertTrue(security.verificar_clave(clave2, cuenta["PASSWORD_HASH"]))
        self.assertFalse(security.verificar_clave(clave1, cuenta["PASSWORD_HASH"]))
        self.assertTrue(cuenta["FLG_CAMBIO_OBLIGATORIO"])
        self.assertEqual(cuenta["INTENTOS_FALLIDOS"], 0)
        self.assertIsNone(cuenta["BLOQUEADO_HASTA"])
        self.assertIsNone(cuenta["FECHA_CAMBIO_CLAVE"])
        self.assertEqual(cuenta["USUARIO_ACTUALIZACION"], ADMIN)

    def test_reset_sin_cuenta_da_404_y_deshabilitada_da_409(self):
        with self.assertRaises(HTTPException) as ctx:
            routes_admin_accesos.resetear_clave(OBJETIVO, Response(), admin=self.admin())
        self.assertEqual(ctx.exception.status_code, 404)

        self.cuentas[GESTOR]["FLG_ACTIVO"] = False
        with self.assertRaises(HTTPException) as ctx:
            routes_admin_accesos.resetear_clave(GESTOR, Response(), admin=self.admin())
        self.assertEqual(ctx.exception.status_code, 409)

    def test_desbloquear_limpia_intentos_y_bloqueo(self):
        self.cuentas[GESTOR].update(INTENTOS_FALLIDOS=5, BLOQUEADO_HASTA=AHORA + timedelta(minutes=10))

        routes_admin_accesos.desbloquear(GESTOR, Response(), admin=self.admin())

        cuenta = self.cuentas[GESTOR]
        self.assertEqual(cuenta["INTENTOS_FALLIDOS"], 0)
        self.assertIsNone(cuenta["BLOQUEADO_HASTA"])
        self.assertEqual(cuenta["USUARIO_ACTUALIZACION"], ADMIN)
        self.assertTrue(auth_service.autenticar_usuario(GESTOR, self.CLAVE_GESTOR).ok)

    def test_deshabilitar_pone_flg_activo_0_y_revoca_de_inmediato(self):
        # Con token vigente pasa...
        self.assertEqual(self.usuario_actual(GESTOR)["dni"], GESTOR)
        token = security.crear_access_token(GESTOR)

        routes_admin_accesos.deshabilitar(GESTOR, Response(), admin=self.admin())

        self.assertFalse(self.cuentas[GESTOR]["FLG_ACTIVO"])
        self.assertIn(GESTOR, self.cuentas)          # no se borra la cuenta
        self.assertEqual(self.cuentas[GESTOR]["PASSWORD_HASH"], self.hash_gestor)
        # ...y el mismo token deja de servir sin esperar a que venza.
        with self.assertRaises(HTTPException) as ctx:
            auth_dependencies.obtener_usuario_actual(HTTPAuthorizationCredentials(scheme="Bearer", credentials=token))
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertFalse(auth_service.autenticar_usuario(GESTOR, self.CLAVE_GESTOR).ok)

    def test_admin_no_puede_deshabilitar_su_propia_cuenta(self):
        with self.assertRaises(HTTPException) as ctx:
            routes_admin_accesos.deshabilitar(ADMIN, Response(), admin=self.admin())

        self.assertEqual(ctx.exception.status_code, 409)
        self.assertEqual(ctx.exception.detail, "No puedes deshabilitar tu propia cuenta.")
        self.assertTrue(self.cuentas[ADMIN]["FLG_ACTIVO"])

    def test_deshabilitar_dos_veces_no_falla(self):
        routes_admin_accesos.deshabilitar(GESTOR, Response(), admin=self.admin())
        resp = routes_admin_accesos.deshabilitar(GESTOR, Response(), admin=self.admin())
        self.assertTrue(resp.get("sin_cambios"))

    def test_rehabilitar_genera_clave_nueva_y_obliga_cambio(self):
        routes_admin_accesos.deshabilitar(GESTOR, Response(), admin=self.admin())

        resp = routes_admin_accesos.habilitar_acceso(GESTOR, Response(), admin=self.admin())

        cuenta = self.cuentas[GESTOR]
        self.assertEqual(resp["accion"], "REHABILITAR")
        self.assertTrue(cuenta["FLG_ACTIVO"])
        self.assertTrue(cuenta["FLG_CAMBIO_OBLIGATORIO"])
        self.assertEqual(cuenta["INTENTOS_FALLIDOS"], 0)
        self.assertIsNone(cuenta["BLOQUEADO_HASTA"])
        # No reutiliza la clave antigua.
        self.assertFalse(security.verificar_clave(self.CLAVE_GESTOR, cuenta["PASSWORD_HASH"]))
        login = auth_service.autenticar_usuario(GESTOR, resp["clave_temporal"])
        self.assertTrue(login.ok)
        self.assertTrue(login.requiere_cambio_clave)

    def test_error_tecnico_no_se_expone(self):
        with patch.object(servicio, "listar_usuarios", side_effect=RuntimeError("SQL interno secreto")):
            with self.assertLogs("app.api.routes_admin_accesos", level="ERROR"):
                with self.assertRaises(HTTPException) as ctx:
                    routes_admin_accesos.listar_usuarios(Response(), q=None, limite=10, admin=self.admin())
        self.assertEqual(ctx.exception.status_code, 500)
        self.assertNotIn("SQL interno secreto", str(ctx.exception.detail))

    def test_logs_admin_no_contienen_claves_ni_hash(self):
        with self.assertLogs("app.services.admin_accesos_service", level="INFO") as logs:
            r1 = routes_admin_accesos.habilitar_acceso(OBJETIVO, Response(), admin=self.admin())
            r2 = routes_admin_accesos.resetear_clave(OBJETIVO, Response(), admin=self.admin())

        texto = "\n".join(logs.output)
        self.assertIn("accion=HABILITAR admin=11111111 objetivo=33333333 resultado=OK", texto)
        self.assertIn("accion=RESET_CLAVE", texto)
        for secreto in (r1["clave_temporal"], r2["clave_temporal"], self.cuentas[OBJETIVO]["PASSWORD_HASH"]):
            self.assertNotIn(secreto, texto)


class CambioClavePropiaTests(BaseAccesosTest):
    NUEVA = "MiClaveNueva2026"

    def cambiar(self, dueno_token, actual, nueva, confirmacion, **extra_payload):
        payload = routes_auth.CambiarClaveRequest(
            clave_actual=actual, clave_nueva=nueva, confirmacion=confirmacion, **extra_payload
        )
        return routes_auth.cambiar_clave(payload, usuario=self.usuario_actual(dueno_token))

    def test_cambio_exige_jwt(self):
        with self.assertRaises(HTTPException) as ctx:
            auth_dependencies.obtener_usuario_actual(None)
        self.assertEqual(ctx.exception.status_code, 401)

    def test_clave_actual_incorrecta_falla(self):
        with self.assertRaises(HTTPException) as ctx:
            self.cambiar(GESTOR, "no-es-la-actual", self.NUEVA, self.NUEVA)
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertEqual(self.cuentas[GESTOR]["PASSWORD_HASH"], self.hash_gestor)

    def test_confirmacion_diferente_falla(self):
        with self.assertRaises(HTTPException) as ctx:
            self.cambiar(GESTOR, self.CLAVE_GESTOR, self.NUEVA, self.NUEVA + "x")
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertEqual(self.cuentas[GESTOR]["PASSWORD_HASH"], self.hash_gestor)

    def test_politica_minima(self):
        for nueva in ("corta7!", GESTOR, self.CLAVE_GESTOR, "        "):
            with self.subTest(nueva=nueva):
                with self.assertRaises(HTTPException) as ctx:
                    self.cambiar(GESTOR, self.CLAVE_GESTOR, nueva, nueva)
                self.assertEqual(ctx.exception.status_code, 400)
        self.assertEqual(self.cuentas[GESTOR]["PASSWORD_HASH"], self.hash_gestor)

    def test_clave_valida_cambia_hash_y_quita_cambio_obligatorio(self):
        self.cuentas[GESTOR].update(FLG_CAMBIO_OBLIGATORIO=True, INTENTOS_FALLIDOS=2)

        resp = self.cambiar(GESTOR, self.CLAVE_GESTOR, self.NUEVA, self.NUEVA)

        cuenta = self.cuentas[GESTOR]
        self.assertEqual(resp, {"ok": True, "requiere_cambio_clave": False})
        self.assertNotEqual(cuenta["PASSWORD_HASH"], self.hash_gestor)
        self.assertTrue(security.verificar_clave(self.NUEVA, cuenta["PASSWORD_HASH"]))
        self.assertFalse(security.verificar_clave(self.CLAVE_GESTOR, cuenta["PASSWORD_HASH"]))
        self.assertFalse(cuenta["FLG_CAMBIO_OBLIGATORIO"])
        self.assertEqual(cuenta["INTENTOS_FALLIDOS"], 0)
        self.assertIsNone(cuenta["BLOQUEADO_HASTA"])
        self.assertEqual(cuenta["FECHA_CAMBIO_CLAVE"], AHORA)
        self.assertEqual(cuenta["USUARIO_ACTUALIZACION"], GESTOR)

    def test_dni_no_viene_del_payload(self):
        # Un "dni" en el payload se ignora: se cambia la clave del dueno del token.
        self.cambiar(GESTOR, self.CLAVE_GESTOR, self.NUEVA, self.NUEVA, dni=ADMIN)

        self.assertTrue(security.verificar_clave(self.NUEVA, self.cuentas[GESTOR]["PASSWORD_HASH"]))
        self.assertEqual(self.cuentas[ADMIN]["PASSWORD_HASH"], self.hash_admin)
        self.assertNotIn("dni", routes_auth.CambiarClaveRequest.model_fields)

    def test_flujo_completo_alta_primer_ingreso_y_cambio(self):
        temporal = routes_admin_accesos.habilitar_acceso(OBJETIVO, Response(), admin=self.admin())["clave_temporal"]

        primer = routes_auth.login(routes_auth.LoginRequest(dni=OBJETIVO, clave=temporal))
        self.assertTrue(primer["requiere_cambio_clave"])

        self.cambiar(OBJETIVO, temporal, self.NUEVA, self.NUEVA)

        segundo = routes_auth.login(routes_auth.LoginRequest(dni=OBJETIVO, clave=self.NUEVA))
        self.assertFalse(segundo["requiere_cambio_clave"])
        self.assertEqual(routes_auth.login(routes_auth.LoginRequest(dni=OBJETIVO, clave=temporal)).status_code, 401)

    def test_logs_no_contienen_claves_hash_ni_token(self):
        token = security.crear_access_token(GESTOR)
        with self.assertLogs(level="INFO") as logs:
            with self.assertRaises(HTTPException):
                self.cambiar(GESTOR, "actual-equivocada-xyz", self.NUEVA, self.NUEVA)
            self.cambiar(GESTOR, self.CLAVE_GESTOR, self.NUEVA, self.NUEVA)

        texto = "\n".join(logs.output)
        self.assertIn("Clave propia cambiada usuario=22222222", texto)
        for secreto in ("actual-equivocada-xyz", self.CLAVE_GESTOR, self.NUEVA,
                        self.hash_gestor, self.cuentas[GESTOR]["PASSWORD_HASH"], token):
            self.assertNotIn(secreto, texto)


try:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    _HAY_TESTCLIENT = True
except Exception:  # httpx no instalado
    _HAY_TESTCLIENT = False


@unittest.skipUnless(_HAY_TESTCLIENT, "TestClient requiere httpx (pip install httpx)")
class HttpAccesosTests(BaseAccesosTest):
    def setUp(self):
        super().setUp()
        app = FastAPI()
        app.include_router(routes_auth.router, prefix="/auth")
        app.include_router(routes_admin_accesos.router, prefix="/admin-accesos")
        self.client = TestClient(app)

    def auth(self, dni):
        return {"Authorization": f"Bearer {security.crear_access_token(dni)}"}

    def test_endpoints_admin_sin_token_401_y_no_admin_403(self):
        rutas = [("get", "/admin-accesos/usuarios"), ("post", f"/admin-accesos/{OBJETIVO}/habilitar"),
                 ("post", f"/admin-accesos/{GESTOR}/reset-clave"), ("post", f"/admin-accesos/{GESTOR}/desbloquear"),
                 ("post", f"/admin-accesos/{GESTOR}/deshabilitar")]
        for metodo, ruta in rutas:
            with self.subTest(ruta=ruta):
                self.assertEqual(getattr(self.client, metodo)(ruta).status_code, 401)
                resp = getattr(self.client, metodo)(ruta, headers=self.auth(GESTOR))
                self.assertEqual(resp.status_code, 403)
        # Nada cambio en la BD.
        self.assertNotIn(OBJETIVO, self.cuentas)
        self.assertTrue(self.cuentas[GESTOR]["FLG_ACTIVO"])

    def test_admin_con_clave_temporal_bloqueado_hasta_cambiarla(self):
        self.cuentas[ADMIN]["FLG_CAMBIO_OBLIGATORIO"] = True
        headers = self.auth(ADMIN)

        rutas = [("get", "/admin-accesos/usuarios"), ("post", f"/admin-accesos/{OBJETIVO}/habilitar"),
                 ("post", f"/admin-accesos/{GESTOR}/reset-clave"), ("post", f"/admin-accesos/{GESTOR}/desbloquear"),
                 ("post", f"/admin-accesos/{GESTOR}/deshabilitar")]
        for metodo, ruta in rutas:
            with self.subTest(ruta=ruta):
                resp = getattr(self.client, metodo)(ruta, headers=headers)
                self.assertEqual(resp.status_code, 403)
                self.assertEqual(resp.json()["detail"], "Debes cambiar tu contraseña antes de continuar.")
        self.assertNotIn(OBJETIVO, self.cuentas)

        # Solo /auth/me y /auth/cambiar-clave siguen disponibles.
        self.assertEqual(self.client.get("/auth/me", headers=headers).status_code, 200)
        cambio = self.client.post("/auth/cambiar-clave", headers=headers, json={
            "clave_actual": self.CLAVE_ADMIN, "clave_nueva": "ClaveDefinitiva2026", "confirmacion": "ClaveDefinitiva2026",
        })
        self.assertEqual(cambio.status_code, 200)

        # Con FLG_CAMBIO_OBLIGATORIO = 0 ya puede administrar (mismo token).
        self.assertEqual(self.client.get("/admin-accesos/usuarios", headers=headers).status_code, 200)

    def test_admin_no_puede_deshabilitarse_por_http(self):
        resp = self.client.post(f"/admin-accesos/{ADMIN}/deshabilitar", headers=self.auth(ADMIN))
        self.assertEqual(resp.status_code, 409)
        self.assertEqual(resp.json()["detail"], "No puedes deshabilitar tu propia cuenta.")
        self.assertTrue(self.cuentas[ADMIN]["FLG_ACTIVO"])

    def test_perfil_en_query_o_payload_no_da_permiso(self):
        resp = self.client.get("/admin-accesos/usuarios?perfil=ADMINISTRADOR&tipo=ADMINISTRADOR",
                               headers=self.auth(GESTOR))
        self.assertEqual(resp.status_code, 403)

    def test_admin_habilita_y_auditoria_sale_del_token(self):
        resp = self.client.post(
            f"/admin-accesos/{OBJETIVO}/habilitar",
            headers=self.auth(ADMIN),
            json={"usuario_actualizacion": "99999999", "usuario_creacion": "99999999"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.headers["cache-control"], "no-store")
        self.assertEqual(self.cuentas[OBJETIVO]["USUARIO_CREACION"], ADMIN)

    def test_cambiar_clave_exige_token_e_ignora_dni(self):
        body = {"clave_actual": self.CLAVE_GESTOR, "clave_nueva": "OtraClave2026", "confirmacion": "OtraClave2026",
                "dni": ADMIN}
        self.assertEqual(self.client.post("/auth/cambiar-clave", json=body).status_code, 401)

        resp = self.client.post("/auth/cambiar-clave", json=body, headers=self.auth(GESTOR))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(security.verificar_clave("OtraClave2026", self.cuentas[GESTOR]["PASSWORD_HASH"]))
        self.assertEqual(self.cuentas[ADMIN]["PASSWORD_HASH"], self.hash_admin)


if __name__ == "__main__":
    unittest.main()
