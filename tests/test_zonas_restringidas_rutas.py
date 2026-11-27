"""Permisos de zonas restringidas con sesión y base simuladas."""
import os
import sys
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

os.environ.setdefault("CRM_JWT_SECRET", "secreto-solo-para-tests-no-productivo-0123456789")

try:
    import pyodbc  # noqa: F401
except Exception:  # pragma: no cover
    sys.modules["pyodbc"] = MagicMock()

from fastapi.testclient import TestClient  # noqa: E402

with patch("sqlalchemy.create_engine", MagicMock()):
    from app.main import app  # noqa: E402

from app.api import routes_zonas_restringidas as rutas  # noqa: E402
from app.core import auth_dependencies, permisos_vistas, security  # noqa: E402


@contextmanager
def sesion(tipo, carteras):
    usuario = {"dni": "12345678", "usuario": "12345678", "tipo": tipo,
               "idcartera": carteras[0], "idcarteras": carteras}
    headers = {"Authorization": f"Bearer {security.crear_access_token(usuario['dni'])}"}
    with patch.object(auth_dependencies, "cuenta_crm_activa", return_value=True), \
         patch.object(auth_dependencies, "obtener_identidad_usuario", return_value=usuario), \
         patch.object(auth_dependencies, "cuenta_requiere_cambio_clave", return_value=False), \
         patch.object(permisos_vistas, "permisos_efectivos", return_value={}), \
         patch.object(rutas.engine_siscob, "connect") as conectar, \
         patch.object(rutas.zonas, "disponible", return_value=True), \
         patch.object(rutas.zonas, "zonas", return_value=[]), \
         patch.object(rutas.zonas, "carteras", return_value=[]):
        with TestClient(app, raise_server_exceptions=False) as cliente:
            yield cliente, headers, conectar


def test_supervisor_ve_estado_pero_no_modifica():
    with sesion("SUPERVISOR", [117]) as (cliente, headers, conectar):
        respuesta = cliente.get("/zonas-restringidas/estado", headers=headers)
        assert respuesta.status_code == 200
        assert respuesta.json() == {"zonas": [], "carteras": [], "puede_editar": False}
        assert conectar.call_count == 1
        for ruta, cuerpo in [
            ("/zonas-restringidas", {"departamentos": ["PIURA"]}),
            ("/zonas-restringidas/levantar", {"ids": [1], "motivo": "Banco autorizó"}),
        ]:
            respuesta = cliente.post(ruta, headers=headers, json=cuerpo)
            assert respuesta.status_code == 403
            assert respuesta.headers["X-CRM-Codigo-Error"] == "ACCESO_DENEGADO"
        assert conectar.call_count == 1


def test_agente_no_ve_estado():
    with sesion("AGENTE", [117]) as (cliente, headers, conectar):
        respuesta = cliente.get("/zonas-restringidas/estado", headers=headers)
        assert respuesta.status_code == 403
        assert respuesta.headers["X-CRM-Codigo-Error"] == "ACCESO_DENEGADO"
        conectar.assert_not_called()


def test_excel_rechaza_cartera_no_asignada():
    with sesion("SUPERVISOR", [117, 124]) as (cliente, headers, conectar):
        respuesta = cliente.get("/zonas-restringidas/excel?idcartera=128", headers=headers)
        assert respuesta.status_code == 403
        assert respuesta.headers["X-CRM-Codigo-Error"] == "ACCESO_DENEGADO"
        conectar.assert_not_called()


def test_cobertura_usa_cache_y_refrescar_recalcula():
    rutas._cobertura_cache = None
    try:
        with sesion("SUPERVISOR", [117]) as (cliente, headers, conectar), \
             patch.object(rutas.zonas, "cobertura", return_value={"carteras": [], "no_reconocidos": []}) as calcular:
            primera = cliente.get("/zonas-restringidas/cobertura", headers=headers)
            segunda = cliente.get("/zonas-restringidas/cobertura", headers=headers)
            for respuesta in (primera, segunda):
                assert respuesta.status_code == 200
                assert respuesta.json()["calculado_en"]
            assert segunda.json() == primera.json()
            assert calcular.call_count == 1
            assert conectar.call_count == 1

            tercera = cliente.get("/zonas-restringidas/cobertura?refrescar=1", headers=headers)
            assert tercera.status_code == 200
            assert calcular.call_count == 2
            assert conectar.call_count == 2
    finally:
        rutas._cobertura_cache = None
