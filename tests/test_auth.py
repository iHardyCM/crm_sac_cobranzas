"""Tests de autenticacion del CRM.

No usan la base de datos: SISCOB y CRM_USUARIO_ACCESO se simulan en memoria.
Ejecutar desde la raiz del proyecto:

    python -m unittest tests.test_auth -v
"""

import os
import unittest
from contextlib import contextmanager
from datetime import datetime, timedelta
from unittest.mock import patch

# Debe existir antes de importar app.core.security (lo lee al importarse).
os.environ.setdefault("CRM_JWT_SECRET", "secreto-solo-para-tests-no-productivo-0123456789")

from fastapi import HTTPException  # noqa: E402
from fastapi.security import HTTPAuthorizationCredentials  # noqa: E402

from app.services import auth_service  # noqa: E402
from app.core import security  # noqa: E402
from app.core import auth_dependencies  # noqa: E402
from app.api import routes_auth  # noqa: E402


DNI = "12345678"
CLAVE = "Clave-Correcta#2026"
AHORA = datetime(2026, 9, 29, 10, 0, 0)

USUARIO_SISCOB = {
    "usuario": DNI,
    "nombres": "ANA",
    "apellidos": "PEREZ",
    "tipo": "GESTOR",
    "idcartera": 124,
}


class RepoFalso:
    """Imita CRM_USUARIO_ACCESO en memoria, con un reloj controlable."""

    def __init__(self, cuentas, ahora):
        self.cuentas = cuentas
        self.ahora = ahora

    def leer_cuenta_para_login(self, dni):
        cuenta = self.cuentas.get(dni)
        if cuenta is None:
            return None
        return {**cuenta, "AHORA": self.ahora}

    def registrar_fallo(self, dni, intentos, bloqueado_hasta):
        self.cuentas[dni]["INTENTOS_FALLIDOS"] = intentos
        self.cuentas[dni]["BLOQUEADO_HASTA"] = bloqueado_hasta
        self.cuentas[dni]["FECHA_ULTIMO_FALLO"] = self.ahora

    def registrar_login_exitoso(self, dni):
        self.cuentas[dni]["INTENTOS_FALLIDOS"] = 0
        self.cuentas[dni]["BLOQUEADO_HASTA"] = None
        self.cuentas[dni]["FECHA_ULTIMO_LOGIN"] = self.ahora


class BaseAuthTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.hash_clave = security.generar_hash_clave(CLAVE)

    def setUp(self):
        self.cuentas = {
            DNI: {
                "USUARIO": DNI,
                "PASSWORD_HASH": self.hash_clave,
                "FLG_ACTIVO": True,
                "FLG_CAMBIO_OBLIGATORIO": False,
                "INTENTOS_FALLIDOS": 0,
                "BLOQUEADO_HASTA": None,
            }
        }
        self.repo = RepoFalso(self.cuentas, AHORA)
        self.usuarios_siscob = {DNI: dict(USUARIO_SISCOB)}

        @contextmanager
        def transaccion_falsa():
            yield self.repo

        self.parches = [
            patch.object(auth_service, "_transaccion_acceso", transaccion_falsa),
            patch.object(
                auth_service,
                "_buscar_usuario_siscob_activo",
                side_effect=lambda dni: self.usuarios_siscob.get(dni),
            ),
            patch.object(
                auth_service,
                "obtener_carteras_usuario",
                side_effect=lambda dni, idcartera: sorted({int(idcartera), 144}),
            ),
            patch.object(
                auth_dependencies,
                "cuenta_crm_activa",
                side_effect=lambda dni: bool(self.cuentas.get(dni, {}).get("FLG_ACTIVO")),
            ),
        ]
        for p in self.parches:
            p.start()

    def tearDown(self):
        for p in self.parches:
            p.stop()

    def cuenta(self):
        return self.cuentas[DNI]


class AutenticarUsuarioTests(BaseAuthTest):
    def test_clave_correcta_autentica_y_genera_token(self):
        r = auth_service.autenticar_usuario(DNI, CLAVE)

        self.assertTrue(r.ok)
        self.assertEqual(r.usuario["dni"], DNI)
        self.assertEqual(r.usuario["tipo"], "GESTOR")
        self.assertEqual(r.usuario["idcarteras"], [124, 144])
        self.assertFalse(r.requiere_cambio_clave)
        payload = security.decodificar_access_token(r.access_token)
        self.assertEqual(payload["sub"], DNI)
        self.assertEqual(self.cuenta()["FECHA_ULTIMO_LOGIN"], AHORA)

    def test_clave_incorrecta_rechaza_y_cuenta_intento(self):
        r = auth_service.autenticar_usuario(DNI, "otra-clave")

        self.assertFalse(r.ok)
        self.assertEqual(r.motivo, auth_service.MOTIVO_CLAVE_INCORRECTA)
        self.assertIsNone(r.access_token)
        self.assertEqual(self.cuenta()["INTENTOS_FALLIDOS"], 1)
        self.assertEqual(self.cuenta()["FECHA_ULTIMO_FALLO"], AHORA)
        self.assertIsNone(self.cuenta()["BLOQUEADO_HASTA"])

    def test_usuario_siscob_no_activo_se_rechaza(self):
        # _buscar_usuario_siscob_activo devuelve None si no existe o Estado <> 'A'.
        self.usuarios_siscob.clear()

        r = auth_service.autenticar_usuario(DNI, CLAVE)

        self.assertFalse(r.ok)
        self.assertEqual(r.motivo, auth_service.MOTIVO_USUARIO_NO_VALIDO)
        self.assertEqual(self.cuenta()["INTENTOS_FALLIDOS"], 0)

    def test_cuenta_crm_deshabilitada_se_rechaza(self):
        self.cuenta()["FLG_ACTIVO"] = False

        r = auth_service.autenticar_usuario(DNI, CLAVE)

        self.assertFalse(r.ok)
        self.assertEqual(r.motivo, auth_service.MOTIVO_CUENTA_INACTIVA)

    def test_sin_cuenta_crm_o_sin_hash_se_rechaza(self):
        self.cuenta()["PASSWORD_HASH"] = None
        self.assertEqual(auth_service.autenticar_usuario(DNI, CLAVE).motivo, auth_service.MOTIVO_SIN_CLAVE)

        del self.cuentas[DNI]
        self.assertEqual(auth_service.autenticar_usuario(DNI, CLAVE).motivo, auth_service.MOTIVO_SIN_CUENTA_CRM)

    def test_bloqueo_al_quinto_intento(self):
        for intento in range(1, 5):
            auth_service.autenticar_usuario(DNI, "mala")
            self.assertEqual(self.cuenta()["INTENTOS_FALLIDOS"], intento)
            self.assertIsNone(self.cuenta()["BLOQUEADO_HASTA"])

        auth_service.autenticar_usuario(DNI, "mala")

        self.assertEqual(self.cuenta()["INTENTOS_FALLIDOS"], 5)
        self.assertEqual(self.cuenta()["BLOQUEADO_HASTA"], AHORA + timedelta(minutes=15))

    def test_login_rechazado_durante_bloqueo_aun_con_clave_correcta(self):
        self.cuenta()["INTENTOS_FALLIDOS"] = 5
        self.cuenta()["BLOQUEADO_HASTA"] = AHORA + timedelta(minutes=10)

        r = auth_service.autenticar_usuario(DNI, CLAVE)

        self.assertFalse(r.ok)
        self.assertEqual(r.motivo, auth_service.MOTIVO_BLOQUEADO)
        # Durante el bloqueo no se cuentan intentos ni se alarga el bloqueo.
        self.assertEqual(self.cuenta()["INTENTOS_FALLIDOS"], 5)
        self.assertEqual(self.cuenta()["BLOQUEADO_HASTA"], AHORA + timedelta(minutes=10))

    def test_bloqueo_vencido_permite_nuevo_intento_y_reinicia_ciclo(self):
        self.cuenta()["INTENTOS_FALLIDOS"] = 5
        self.cuenta()["BLOQUEADO_HASTA"] = AHORA - timedelta(minutes=1)

        r = auth_service.autenticar_usuario(DNI, "mala")

        self.assertEqual(r.motivo, auth_service.MOTIVO_CLAVE_INCORRECTA)
        self.assertEqual(self.cuenta()["INTENTOS_FALLIDOS"], 1)
        self.assertIsNone(self.cuenta()["BLOQUEADO_HASTA"])

        self.assertTrue(auth_service.autenticar_usuario(DNI, CLAVE).ok)

    def test_login_correcto_reinicia_intentos(self):
        self.cuenta()["INTENTOS_FALLIDOS"] = 3

        r = auth_service.autenticar_usuario(DNI, CLAVE)

        self.assertTrue(r.ok)
        self.assertEqual(self.cuenta()["INTENTOS_FALLIDOS"], 0)
        self.assertIsNone(self.cuenta()["BLOQUEADO_HASTA"])

    def test_cambio_obligatorio_autentica_pero_lo_informa(self):
        self.cuenta()["FLG_CAMBIO_OBLIGATORIO"] = True

        r = auth_service.autenticar_usuario(DNI, CLAVE)

        self.assertTrue(r.ok)
        self.assertTrue(r.requiere_cambio_clave)

    def test_log_no_contiene_clave_ni_hash(self):
        with self.assertLogs("app.services.auth_service", level="INFO") as logs:
            auth_service.autenticar_usuario(DNI, "clave-que-no-debe-aparecer")
            r = auth_service.autenticar_usuario(DNI, CLAVE)

        texto = "\n".join(logs.output)
        self.assertNotIn("clave-que-no-debe-aparecer", texto)
        self.assertNotIn(CLAVE, texto)
        self.assertNotIn(self.hash_clave, texto)
        self.assertNotIn(r.access_token, texto)


class LoginEndpointTests(BaseAuthTest):
    def test_login_correcto_devuelve_token_y_usuario_sin_datos_internos(self):
        resp = routes_auth.login(routes_auth.LoginRequest(dni=DNI, clave=CLAVE))

        self.assertTrue(resp["ok"])
        self.assertEqual(resp["token_type"], "bearer")
        self.assertIn("access_token", resp)
        self.assertEqual(set(resp["user"]), {"dni", "agente", "tipo", "idcartera", "idcarteras"})
        self.assertNotIn(self.hash_clave, str(resp))
        self.assertNotIn(CLAVE, str(resp))

    def test_todos_los_fallos_de_credenciales_dan_el_mismo_mensaje(self):
        respuestas = [routes_auth.login(routes_auth.LoginRequest(dni=DNI, clave="mala"))]

        self.cuenta()["FLG_ACTIVO"] = False
        respuestas.append(routes_auth.login(routes_auth.LoginRequest(dni=DNI, clave=CLAVE)))

        self.usuarios_siscob.clear()
        respuestas.append(routes_auth.login(routes_auth.LoginRequest(dni=DNI, clave=CLAVE)))

        for resp in respuestas:
            self.assertEqual(resp.status_code, 401)
            self.assertEqual(resp.body, respuestas[0].body)

    def test_login_exige_dni_y_clave(self):
        self.assertEqual(routes_auth.login(routes_auth.LoginRequest(dni=DNI)).status_code, 400)
        self.assertEqual(routes_auth.login(routes_auth.LoginRequest(dni="123", clave=CLAVE)).status_code, 400)
        self.assertEqual(routes_auth.login(routes_auth.LoginRequest(clave=CLAVE)).status_code, 400)

    def test_error_tecnico_no_se_expone(self):
        with patch.object(auth_service, "_buscar_usuario_siscob_activo", side_effect=RuntimeError("SQL secreto")), \
             patch.object(routes_auth, "autenticar_usuario", side_effect=RuntimeError("SQL secreto")):
            with self.assertLogs("app.api.routes_auth", level="ERROR"):
                resp = routes_auth.login(routes_auth.LoginRequest(dni=DNI, clave=CLAVE))

        self.assertEqual(resp.status_code, 503)
        self.assertNotIn(b"SQL secreto", resp.body)


class TokenYDependenciaTests(BaseAuthTest):
    def credenciales(self, token):
        return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

    def patch_identidad(self):
        return patch.object(
            auth_dependencies,
            "obtener_identidad_usuario",
            side_effect=lambda dni: auth_service._armar_identidad(self.usuarios_siscob[dni])
            if dni in self.usuarios_siscob else None,
        )

    def test_token_valido_devuelve_usuario_resuelto_en_servidor(self):
        token = security.crear_access_token(DNI)
        # El perfil sale de SISCOB en el momento, no del token ni del navegador.
        self.usuarios_siscob[DNI]["tipo"] = "SUPERVISOR"

        with self.patch_identidad():
            usuario = auth_dependencies.obtener_usuario_actual(self.credenciales(token))

        self.assertEqual(usuario["dni"], DNI)
        self.assertEqual(usuario["tipo"], "SUPERVISOR")

    def test_sin_token_da_401(self):
        with self.assertRaises(HTTPException) as ctx:
            auth_dependencies.obtener_usuario_actual(None)
        self.assertEqual(ctx.exception.status_code, 401)

    def test_token_invalido_da_401(self):
        token = security.crear_access_token(DNI)
        for malo in ["no-es-un-jwt", token[:-2] + ("aa" if not token.endswith("aa") else "bb")]:
            with self.assertRaises(HTTPException) as ctx:
                auth_dependencies.obtener_usuario_actual(self.credenciales(malo))
            self.assertEqual(ctx.exception.status_code, 401)

    def test_token_expirado_da_401(self):
        with patch.object(security, "JWT_EXPIRE_MINUTES", -5):
            token = security.crear_access_token(DNI)

        self.assertIsNone(security.decodificar_access_token(token))
        with self.assertRaises(HTTPException) as ctx:
            auth_dependencies.obtener_usuario_actual(self.credenciales(token))
        self.assertEqual(ctx.exception.status_code, 401)

    def test_cuenta_crm_deshabilitada_con_token_vigente_da_401(self):
        token = security.crear_access_token(DNI)
        self.cuenta()["FLG_ACTIVO"] = False

        with self.patch_identidad():
            with self.assertRaises(HTTPException) as ctx:
                auth_dependencies.obtener_usuario_actual(self.credenciales(token))
        self.assertEqual(ctx.exception.status_code, 401)

    def test_cuenta_crm_inexistente_con_token_vigente_da_401(self):
        token = security.crear_access_token(DNI)
        del self.cuentas[DNI]

        with self.patch_identidad():
            with self.assertRaises(HTTPException) as ctx:
                auth_dependencies.obtener_usuario_actual(self.credenciales(token))
        self.assertEqual(ctx.exception.status_code, 401)

    def test_usuario_que_deja_de_estar_activo_da_401(self):
        token = security.crear_access_token(DNI)
        self.usuarios_siscob.clear()

        with self.patch_identidad():
            with self.assertRaises(HTTPException) as ctx:
                auth_dependencies.obtener_usuario_actual(self.credenciales(token))
        self.assertEqual(ctx.exception.status_code, 401)


try:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    _HAY_TESTCLIENT = True
except Exception:  # httpx no instalado
    _HAY_TESTCLIENT = False


@unittest.skipUnless(_HAY_TESTCLIENT, "TestClient requiere httpx (pip install httpx)")
class AuthMeHttpTests(BaseAuthTest):
    def setUp(self):
        super().setUp()
        app = FastAPI()
        app.include_router(routes_auth.router, prefix="/auth")
        self.client = TestClient(app)

    def test_me_requiere_token(self):
        self.assertEqual(self.client.get("/auth/me").status_code, 401)
        self.assertEqual(
            self.client.get("/auth/me", headers={"Authorization": "Bearer basura"}).status_code, 401
        )

    def test_login_y_me_de_punta_a_punta(self):
        resp = self.client.post("/auth/login", json={"dni": DNI, "clave": CLAVE})
        self.assertEqual(resp.status_code, 200)
        token = resp.json()["access_token"]

        with patch.object(
            auth_dependencies,
            "obtener_identidad_usuario",
            side_effect=lambda dni: auth_service._armar_identidad(self.usuarios_siscob[dni]),
        ):
            me = self.client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})

        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.json()["dni"], DNI)

    def test_login_sin_clave_da_400(self):
        self.assertEqual(self.client.post("/auth/login", json={"dni": DNI}).status_code, 400)


if __name__ == "__main__":
    unittest.main()
