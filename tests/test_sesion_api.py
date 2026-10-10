"""Todos los endpoints de datos exigen sesion valida (401 sin token).

Recorre las rutas reales de app.main (sin base de datos: se simula create_engine
y pyodbc) y comprueba que, sin Authorization, ninguna responde datos. Tambien
verifica con un token valido, con clave temporal y con cuenta deshabilitada.

    python -m unittest tests.test_sesion_api -v
"""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

os.environ.setdefault("CRM_JWT_SECRET", "secreto-solo-para-tests-no-productivo-0123456789")

try:  # El driver ODBC no es necesario: no se abre ninguna conexion.
    import pyodbc  # noqa: F401
except Exception:  # pragma: no cover
    sys.modules["pyodbc"] = MagicMock()

from fastapi.testclient import TestClient  # noqa: E402

with patch("sqlalchemy.create_engine", MagicMock()):
    from app.main import app  # noqa: E402

from app.core import auth_dependencies, permisos_vistas, security  # noqa: E402

DNI = "12345678"
USUARIO = {"dni": DNI, "usuario": DNI, "agente": "ANA", "tipo": "GESTOR", "idcartera": 124, "idcarteras": [124]}

# Rutas que deben seguir abiertas (login, salud) o que se protegen en otra capa
# (la pagina HTML no contiene datos y el navegador no puede enviar el token).
ABIERTAS = {("GET", "/"), ("POST", "/auth/login")}


def _rutas_api():
    for path, metodos in app.openapi()["paths"].items():
        for metodo in metodos:
            yield metodo.upper(), path


def _es_vista(path):
    return path.rstrip("/").count("/") == 1


class SesionApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app, raise_server_exceptions=False)

    def _llamar(self, metodo, path, headers=None):
        import re
        url = re.sub(r"\{[^}]+\}", "1", path)
        return self.client.request(metodo, url, headers=headers or {})

    def test_ningun_endpoint_de_datos_responde_sin_token(self):
        abiertos = []
        for metodo, path in _rutas_api():
            if (metodo, path) in ABIERTAS:
                continue
            if metodo == "GET" and _es_vista(path):
                continue
            resp = self._llamar(metodo, path)
            if resp.status_code != 401:
                abiertos.append(f"{metodo} {path} -> {resp.status_code}")
        self.assertEqual(abiertos, [], "Endpoints sin proteger:\n" + "\n".join(abiertos))

    def test_token_invalido_es_401(self):
        for metodo, path in [("GET", "/control-horario/resumen"), ("GET", "/corporativo/filtros"),
                             ("POST", "/pagos/validar"), ("GET", "/score-telefonico/contexto")]:
            resp = self._llamar(metodo, path, {"Authorization": "Bearer basura"})
            self.assertEqual(resp.status_code, 401, f"{metodo} {path}")

    def test_paginas_html_siguen_abiertas(self):
        for prefijo in ["/control-horario", "/corporativo", "/documentos", "/importacion", "/metas",
                        "/pagos", "/canales", "/susurro-ia", "/planes-mejora",
                        "/admin-metas-agentes", "/admin-pautas-evaluacion", "/admin-supervisores"]:
            if not any(p == prefijo for _, p in _rutas_api()):
                continue  # el modulo no publica pagina HTML
            resp = self.client.get(prefijo)
            self.assertNotEqual(resp.status_code, 401, prefijo)

    def _headers(self):
        token = security.crear_access_token(DNI)
        return {"Authorization": f"Bearer {token}"}

    def _parches(self, activa=True, cambio=False, identidad=USUARIO):
        return (
            patch.object(auth_dependencies, "cuenta_crm_activa", return_value=activa),
            patch.object(auth_dependencies, "obtener_identidad_usuario", return_value=identidad),
            patch.object(auth_dependencies, "cuenta_requiere_cambio_clave", return_value=cambio),
            patch.object(permisos_vistas, "permisos_efectivos", return_value={}),
        )

    def test_clave_temporal_es_403_con_codigo(self):
        p = self._parches(cambio=True)
        with p[0], p[1], p[2], p[3]:
            resp = self._llamar("GET", "/control-horario/resumen", self._headers())
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.headers.get("X-CRM-Codigo-Error"), "CAMBIO_CLAVE_OBLIGATORIO")

    def test_cuenta_deshabilitada_es_401(self):
        p = self._parches(activa=False)
        with p[0], p[1], p[2], p[3]:
            resp = self._llamar("GET", "/control-horario/resumen", self._headers())
        self.assertEqual(resp.status_code, 401)

    def test_sesion_valida_pasa_la_dependencia(self):
        from app.api import routes_control_horario
        p = self._parches()
        with p[0], p[1], p[2], p[3], \
             patch.object(routes_control_horario, "obtener_resumen_control_horario", return_value={"ok": 1}):
            resp = self._llamar("GET", "/control-horario/resumen", self._headers())
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"ok": 1})

    def test_mantenedor_supervisores_rechaza_a_agente(self):
        p = self._parches()
        with p[0], p[1], p[2], p[3]:
            respuesta = self.client.post(
                "/admin-supervisores/asignaciones", headers=self._headers(),
                json={"usuario": DNI, "idcarteras": [128]},
            )
        self.assertEqual(respuesta.status_code, 403)
        self.assertEqual(respuesta.headers.get("X-CRM-Codigo-Error"), "ACCESO_DENEGADO")


if __name__ == "__main__":
    unittest.main()
