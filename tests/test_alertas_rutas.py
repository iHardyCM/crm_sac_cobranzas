"""Alertas por perfil con sesión y fuentes simuladas."""
import os
import sys
from contextlib import contextmanager
from datetime import date
from unittest.mock import MagicMock, patch

os.environ.setdefault("CRM_JWT_SECRET", "secreto-solo-para-tests-no-productivo-0123456789")

try:
    import pyodbc  # noqa: F401
except Exception:  # pragma: no cover
    sys.modules["pyodbc"] = MagicMock()

from fastapi.testclient import TestClient  # noqa: E402

with patch("sqlalchemy.create_engine", MagicMock()):
    from app.main import app  # noqa: E402

from app.api import routes_alertas as rutas  # noqa: E402
from app.core import auth_dependencies, permisos_vistas, security  # noqa: E402


ZONAS = [
    {"IdZona": 1, "Departamento": "PIURA", "Activo": True, "Estado": "VIGENTE",
     "AplicaTodas": True, "Carteras": [], "Origen": "BANCO", "Desde": date(2026, 11, 27),
     "Hasta": None, "Motivo": "Interbank detuvo la gestión"},
    {"IdZona": 2, "Departamento": "TUMBES", "Activo": True, "Estado": "PROGRAMADA",
     "AplicaTodas": False, "Carteras": [117], "Origen": "INTERNO", "Desde": date(2026, 12, 1),
     "Hasta": date(2026, 12, 5), "Motivo": "Aviso por lluvias"},
    {"IdZona": 3, "Activo": True, "Estado": "VENCIDA"},
    {"IdZona": 4, "Activo": False, "Estado": "LEVANTADA"},
]


@contextmanager
def sesion(tipo, carteras=(117,), vista_sms=True):
    usuario = {"dni": "12345678", "usuario": "12345678", "tipo": tipo,
               "idcartera": carteras[0], "idcarteras": list(carteras)}
    headers = {"Authorization": f"Bearer {security.crear_access_token(usuario['dni'])}"}
    sms_resumen = {"clientes": 3, "completo": True}
    with patch.object(auth_dependencies, "cuenta_crm_activa", return_value=True), \
         patch.object(auth_dependencies, "obtener_identidad_usuario", return_value=usuario), \
         patch.object(auth_dependencies, "cuenta_requiere_cambio_clave", return_value=False), \
         patch.object(permisos_vistas, "permisos_efectivos", return_value={"respuestas_mowa": vista_sms}), \
         patch.object(rutas.engine_siscob, "connect") as conectar, \
         patch.object(rutas.zonas, "zonas", return_value=ZONAS) as leer_zonas, \
         patch.object(rutas.sms, "sin_atender", return_value=sms_resumen) as contar_sms:
        with TestClient(app, raise_server_exceptions=False) as cliente:
            yield cliente, headers, conectar, leer_zonas, contar_sms


def test_sin_sesion_rechaza_sin_consultar_fuentes():
    with patch.object(rutas.engine_siscob, "connect") as conectar, \
         patch.object(rutas.sms, "sin_atender") as contar_sms:
        with TestClient(app, raise_server_exceptions=False) as cliente:
            assert cliente.get("/alertas/resumen").status_code == 401
    conectar.assert_not_called()
    contar_sms.assert_not_called()


def test_jefe_recibe_zonas_y_sms_con_forma_y_niveles():
    with sesion("JEFE DE CARTERA") as (cliente, headers, conectar, leer_zonas, contar_sms):
        respuesta = cliente.get("/alertas/resumen", headers=headers)
        assert respuesta.status_code == 200
        alertas = respuesta.json()
        assert [a["id"] for a in alertas] == ["zona:1", "zona:2", "sms:sin-atender"]
        assert [a["nivel"] for a in alertas] == ["rojo", "info", "ambar"]
        assert all(set(a) == {"id", "tipo", "nivel", "titulo", "detalle", "enlace"} for a in alertas)
        assert alertas[0]["enlace"] == "zonas.html"
        assert "Interbank detuvo la gestión" in alertas[0]["detalle"]
        assert alertas[1]["enlace"] == "zonas.html"
        assert alertas[2]["enlace"] == "respuestas_mowa.html"
        assert "3 clientes" in alertas[2]["detalle"]
        conectar.assert_called_once()
        leer_zonas.assert_called_once()
        contar_sms.assert_called_once_with(None)


def test_supervisor_sms_solo_de_sus_carteras():
    with sesion("SUPERVISOR", (117, 124)) as (cliente, headers, _, _, contar_sms):
        respuesta = cliente.get("/alertas/resumen", headers=headers)
        assert respuesta.status_code == 200
        assert len(respuesta.json()) == 3
        contar_sms.assert_called_once_with({117, 124})


def test_agente_y_monitor_ven_zonas_sin_consultar_sms():
    for tipo in ("GESTOR", "MONITOR DE CALIDAD"):
        with sesion(tipo) as (cliente, headers, _, leer_zonas, contar_sms):
            respuesta = cliente.get("/alertas/resumen", headers=headers)
            assert respuesta.status_code == 200
            assert [a["id"] for a in respuesta.json()] == ["zona:1", "zona:2"]
            leer_zonas.assert_called_once()
            contar_sms.assert_not_called()


def test_vista_sms_deshabilitada_no_expone_conteo():
    with sesion("SUPERVISOR", vista_sms=False) as (cliente, headers, _, _, contar_sms):
        respuesta = cliente.get("/alertas/resumen", headers=headers)
        assert respuesta.status_code == 200
        assert [a["id"] for a in respuesta.json()] == ["zona:1", "zona:2"]
        contar_sms.assert_not_called()


def test_sms_parcial_no_presenta_conteo_como_completo():
    with sesion("SUPERVISOR") as (cliente, headers, _, _, contar_sms):
        contar_sms.return_value = {"clientes": 2, "completo": False}
        respuesta = cliente.get("/alertas/resumen", headers=headers)
        assert respuesta.status_code == 200
        assert "Al menos 2" in respuesta.json()[-1]["detalle"]
        assert "parcial" in respuesta.json()[-1]["detalle"]
