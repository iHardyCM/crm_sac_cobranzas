"""Seguridad del modulo IA (routes_ia_feedback y routes_calibracion).

No usan la base de datos: las validaciones de sesion y los servicios de IA se
simulan. Ejecutar desde la raiz del proyecto:

    python -m unittest tests.test_ia_seguridad -v

Los tests HTTP requieren httpx (TestClient); si no esta instalado se saltan.
"""

import os
import unittest
from unittest.mock import MagicMock, patch

os.environ.setdefault("CRM_JWT_SECRET", "secreto-solo-para-tests-no-productivo-0123456789")

from app.core import auth_dependencies, security  # noqa: E402
from app.services import auth_service  # noqa: E402
from app.api import routes_calibracion, routes_ia_feedback  # noqa: E402

try:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    _HAY_TESTCLIENT = True
except Exception:  # httpx no instalado
    _HAY_TESTCLIENT = False


ADMIN = "11111111"
GESTOR = "22222222"
SUPERVISOR = "33333333"
MENSAJE_CAMBIO = "Debes cambiar tu contraseña antes de continuar."


@unittest.skipUnless(_HAY_TESTCLIENT, "TestClient requiere httpx (pip install httpx)")
class BaseIaSeguridadTest(unittest.TestCase):
    def setUp(self):
        self.usuarios = {
            ADMIN: {"usuario": ADMIN, "nombres": "ANA", "apellidos": "ADMIN", "tipo": "ADMINISTRADOR", "idcartera": 124},
            GESTOR: {"usuario": GESTOR, "nombres": "GINO", "apellidos": "GESTOR", "tipo": "GESTOR", "idcartera": 112},
            SUPERVISOR: {"usuario": SUPERVISOR, "nombres": "SARA", "apellidos": "SUPER", "tipo": "Supervisor", "idcartera": 117},
        }
        self.cuentas = {dni: {"FLG_ACTIVO": True, "FLG_CAMBIO_OBLIGATORIO": False} for dni in self.usuarios}

        def identidad(dni):
            return auth_service._armar_identidad(self.usuarios[dni]) if dni in self.usuarios else None

        self.parches = [
            patch.object(auth_service, "obtener_carteras_usuario", side_effect=lambda d, i: [int(i)]),
            patch.object(auth_dependencies, "obtener_identidad_usuario", side_effect=identidad),
            patch.object(auth_dependencies, "cuenta_crm_activa",
                         side_effect=lambda d: bool(self.cuentas.get(d, {}).get("FLG_ACTIVO"))),
            patch.object(auth_dependencies, "cuenta_requiere_cambio_clave",
                         side_effect=lambda d: bool(self.cuentas.get(d, {}).get("FLG_CAMBIO_OBLIGATORIO", True))),
        ]
        for p in self.parches:
            p.start()

        app = FastAPI()
        app.include_router(routes_ia_feedback.router, prefix="/ia-feedback")
        app.include_router(routes_calibracion.router, prefix="/calibracion")
        self.client = TestClient(app)

    def tearDown(self):
        for p in self.parches:
            p.stop()

    def auth(self, dni):
        return {"Authorization": f"Bearer {security.crear_access_token(dni)}"}

    def agente(self, dni):
        u = self.usuarios[dni]
        return f"{dni} - {u['nombres']} {u['apellidos']}"


def _rutas_con_datos(router, prefijo):
    """Todas las rutas del router salvo la que solo sirve el HTML (path vacio)."""
    rutas = []
    for ruta in router.routes:
        if ruta.path == "":
            continue
        path = (prefijo + ruta.path).replace("{id_feedback}", "1").replace(
            "{id_recalibracion}", "1").replace("{id_calibracion}", "1")
        for metodo in sorted(ruta.methods):
            rutas.append((metodo.lower(), path))
    return rutas


class SinSesionTests(BaseIaSeguridadTest):
    def test_todos_los_endpoints_ia_sin_token_dan_401(self):
        rutas = _rutas_con_datos(routes_ia_feedback.router, "/ia-feedback")
        self.assertGreaterEqual(len(rutas), 22)
        for metodo, path in rutas:
            with self.subTest(ruta=f"{metodo.upper()} {path}"):
                self.assertEqual(getattr(self.client, metodo)(path).status_code, 401)

    def test_todos_los_endpoints_calibracion_sin_token_dan_401(self):
        for metodo, path in _rutas_con_datos(routes_calibracion.router, "/calibracion"):
            with self.subTest(ruta=f"{metodo.upper()} {path}"):
                self.assertEqual(getattr(self.client, metodo)(path).status_code, 401)

    def test_token_invalido_da_401(self):
        resp = self.client.get("/ia-feedback/config", headers={"Authorization": "Bearer no-es-un-jwt"})
        self.assertEqual(resp.status_code, 401)

    def test_audio_sin_token_da_401(self):
        self.assertEqual(self.client.get("/ia-feedback/1/audio").status_code, 401)


class ConSesionTests(BaseIaSeguridadTest):
    def test_token_valido_entra(self):
        with patch.object(routes_ia_feedback, "obtener_configuracion_audio", return_value={"max_audio_mb": 25}):
            resp = self.client.get("/ia-feedback/config", headers=self.auth(GESTOR))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"max_audio_mb": 25})

    def test_cuenta_deshabilitada_da_401_con_el_mismo_token(self):
        headers = self.auth(GESTOR)
        with patch.object(routes_ia_feedback, "obtener_configuracion_audio", return_value={}), \
             patch.object(routes_ia_feedback, "obtener_bandeja_supervisor", return_value={}):
            self.assertEqual(self.client.get("/ia-feedback/config", headers=headers).status_code, 200)

            self.cuentas[GESTOR]["FLG_ACTIVO"] = False   # el admin la deshabilita

            for path in ("/ia-feedback/config", "/ia-feedback/bandeja", "/ia-feedback/1/audio"):
                with self.subTest(path=path):
                    self.assertEqual(self.client.get(path, headers=headers).status_code, 401)

    def test_cambio_obligatorio_da_403_estable(self):
        self.cuentas[GESTOR]["FLG_CAMBIO_OBLIGATORIO"] = True
        resp = self.client.get("/ia-feedback/config", headers=self.auth(GESTOR))
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.json()["detail"], MENSAJE_CAMBIO)


class PerfilDelNavegadorNoDaPermisosTests(BaseIaSeguridadTest):
    def test_get_prompt_ignora_perfil_de_la_query(self):
        with patch.object(routes_ia_feedback, "obtener_prompt_configuracion") as obtener:
            resp = self.client.get("/ia-feedback/prompt?perfil=ADMINISTRADOR", headers=self.auth(GESTOR))
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.json()["puede_editar"])
        self.assertIsNone(resp.json()["prompt_base"])
        obtener.assert_not_called()

    def test_post_prompt_no_confia_en_perfil_administrador_del_navegador(self):
        form = {"prompt_base": "x" * 600, "perfil": "ADMINISTRADOR", "actualizado_por": "99999999 - OTRO"}
        with patch("app.services.ia_analysis_service.ensure_tabla_prompt_config") as ddl:
            resp = self.client.post("/ia-feedback/prompt", data=form, headers=self.auth(GESTOR))
        self.assertEqual(resp.status_code, 403)
        ddl.assert_not_called()   # no llego a tocar la BD

    def test_post_prompt_usa_identidad_y_perfil_de_la_sesion(self):
        with patch.object(routes_ia_feedback, "guardar_prompt_configuracion", return_value={"ok": True}) as guardar:
            resp = self.client.post(
                "/ia-feedback/prompt",
                data={"prompt_base": "x" * 600, "perfil": "GESTOR", "actualizado_por": "99999999 - OTRO"},
                headers=self.auth(ADMIN),
            )
        self.assertEqual(resp.status_code, 200)
        kwargs = guardar.call_args.kwargs
        self.assertEqual(kwargs["perfil"], "ADMINISTRADOR")
        self.assertEqual(kwargs["actualizado_por"], self.agente(ADMIN))

    def test_listar_y_reporteria_no_se_amplian_con_perfil_ni_supervisor_de_la_query(self):
        query = "?perfil=ADMINISTRADOR&supervisor=99999999%20-%20OTRO"
        with patch.object(routes_ia_feedback, "listar_feedback", return_value=[]) as listar, \
             patch.object(routes_ia_feedback, "obtener_reporteria_calidad", return_value={"detalle": []}) as rep:
            self.assertEqual(self.client.get(f"/ia-feedback/listar{query}", headers=self.auth(GESTOR)).status_code, 200)
            self.assertEqual(self.client.get(f"/ia-feedback/reporteria{query}", headers=self.auth(GESTOR)).status_code, 200)
        self.assertEqual(listar.call_args.kwargs["supervisor"], self.agente(GESTOR))
        self.assertEqual(rep.call_args.kwargs["supervisor"], self.agente(GESTOR))

    def test_vision_global_sale_del_perfil_de_la_sesion(self):
        with patch.object(routes_ia_feedback, "listar_feedback", return_value=[]) as listar:
            self.client.get("/ia-feedback/listar", headers=self.auth(ADMIN))
        self.assertIsNone(listar.call_args.kwargs["supervisor"])

    def test_bandeja_usa_supervisor_de_la_sesion(self):
        with patch.object(routes_ia_feedback, "obtener_bandeja_supervisor", return_value={}) as bandeja:
            self.client.get("/ia-feedback/bandeja?perfil=ADMINISTRADOR&supervisor=otro", headers=self.auth(GESTOR))
        self.assertEqual(bandeja.call_args.kwargs, {"supervisor": self.agente(GESTOR), "ver_todo": False})

    def test_consumo_ignora_perfil_de_la_query(self):
        with patch.object(routes_ia_feedback, "obtener_consumo") as consumo:
            resp = self.client.get("/ia-feedback/consumo?perfil=ADMINISTRADOR", headers=self.auth(GESTOR))
        self.assertEqual(resp.status_code, 403)
        consumo.assert_not_called()

    def test_upload_revision_y_agente_registran_al_usuario_de_la_sesion(self):
        with patch.object(routes_ia_feedback, "registrar_audio_feedback", return_value={"ok": True}) as registrar, \
             patch.object(routes_ia_feedback, "guardar_revision_feedback", return_value={"ok": True}) as revision, \
             patch.object(routes_ia_feedback, "asignar_agente_feedback", return_value={"ok": True}) as asignar:
            h = self.auth(SUPERVISOR)
            self.client.post("/ia-feedback/upload", headers=h,
                             files={"archivo": ("a.mp3", b"123", "audio/mpeg")},
                             data={"supervisor": "99999999 - OTRO"})
            self.client.post("/ia-feedback/1/revision", headers=h, data={"revisado_por": "99999999 - OTRO"})
            self.client.post("/ia-feedback/1/agente", headers=h, data={"agente": "X", "usuario": "99999999"})
        self.assertEqual(registrar.call_args.kwargs["supervisor"], self.agente(SUPERVISOR))
        self.assertEqual(revision.call_args.kwargs["revisado_por"], self.agente(SUPERVISOR))
        self.assertEqual(asignar.call_args.args[2], self.agente(SUPERVISOR))

    def test_calibracion_permisos_ignoran_perfil_de_la_query(self):
        resp = self.client.get("/calibracion/permisos?perfil=ADMINISTRADOR", headers=self.auth(GESTOR))
        self.assertEqual(resp.json(), {"puede_publicar": False, "puede_proponer": False})

    def test_calibracion_resolver_usa_perfil_y_usuario_de_la_sesion(self):
        with patch.object(routes_calibracion, "resolver_llamada", return_value={"ok": True}) as resolver:
            self.client.post("/calibracion/llamada/1/resolver", headers=self.auth(SUPERVISOR),
                             json={"estado": "PUBLICADA", "usuario": ADMIN, "perfil": "ADMINISTRADOR"})
        kwargs = resolver.call_args.kwargs
        self.assertEqual(kwargs["perfil"], "SUPERVISOR")
        self.assertEqual(kwargs["usuario"], SUPERVISOR)

    def test_calibracion_publicar_con_perfil_falso_es_rechazada_por_el_servicio(self):
        # El servicio real decide con el perfil de la sesion: un GESTOR no publica.
        # (resolver_llamada valida el permiso antes de tocar la BD; el engine se
        # reemplaza igual para garantizar que ningun test llegue a SQL Server).
        with patch("app.services.calibracion_service.engine_siscob", MagicMock()) as engine:
            resp = self.client.post("/calibracion/llamada/1/resolver", headers=self.auth(GESTOR),
                                    json={"estado": "PUBLICADA", "perfil": "ADMINISTRADOR"})
        self.assertEqual(resp.status_code, 403)
        engine.begin.assert_not_called()


from tests.test_admin_accesos import BaseAccesosTest, OBJETIVO as OBJETIVO_ADMIN  # noqa: E402
from app.api import routes_admin_accesos, routes_auth  # noqa: E402


@unittest.skipUnless(_HAY_TESTCLIENT, "TestClient requiere httpx (pip install httpx)")
class AceptacionRevocacionTest(BaseAccesosTest):
    """Prueba de aceptacion: alta -> login -> IA -> deshabilitar -> 401 con el JWT anterior."""

    def test_flujo_completo_de_revocacion(self):
        app = FastAPI()
        app.include_router(routes_auth.router, prefix="/auth")
        app.include_router(routes_admin_accesos.router, prefix="/admin-accesos")
        app.include_router(routes_ia_feedback.router, prefix="/ia-feedback")
        client = TestClient(app)
        admin = {"Authorization": f"Bearer {security.crear_access_token('11111111')}"}

        # 1. El administrador habilita al usuario.
        alta = client.post(f"/admin-accesos/{OBJETIVO_ADMIN}/habilitar", headers=admin)
        self.assertEqual(alta.status_code, 200)
        temporal = alta.json()["clave_temporal"]

        # 2. El usuario inicia sesion y cambia la clave temporal.
        login = client.post("/auth/login", json={"dni": OBJETIVO_ADMIN, "clave": temporal}).json()
        token = {"Authorization": f"Bearer {login['access_token']}"}
        self.assertEqual(client.post("/auth/cambiar-clave", headers=token, json={
            "clave_actual": temporal, "clave_nueva": "ClaveDefinitiva2026", "confirmacion": "ClaveDefinitiva2026",
        }).status_code, 200)

        # 3. Abre IA y ve informacion.
        with patch.object(routes_ia_feedback, "obtener_bandeja_supervisor", return_value={"en_proceso": []}):
            self.assertEqual(client.get("/ia-feedback/bandeja", headers=token).status_code, 200)

            # 4. El administrador lo deshabilita.
            self.assertEqual(client.post(f"/admin-accesos/{OBJETIVO_ADMIN}/deshabilitar", headers=admin).status_code, 200)

            # 5-6. Al recargar la pagina, /auth/me responde 401 (el frontend lo manda al login).
            self.assertEqual(client.get("/auth/me", headers=token).status_code, 401)
            # 7. Y cualquier endpoint IA con el JWT anterior tambien responde 401.
            self.assertEqual(client.get("/ia-feedback/bandeja", headers=token).status_code, 401)
            self.assertEqual(client.get("/ia-feedback/1/audio", headers=token).status_code, 401)


if __name__ == "__main__":
    unittest.main()
