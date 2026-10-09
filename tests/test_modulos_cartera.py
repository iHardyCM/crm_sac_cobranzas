"""Seguridad de Cliente (Consulta Compartamos), Compromisos y Telefonos.

Sesion obligatoria, identidad desde el JWT y restriccion por cartera.
No usan la base de datos: sesion, SISCOB y servicios se simulan.

    python -m unittest tests.test_modulos_cartera -v

Los tests HTTP requieren httpx (TestClient); si no esta instalado se saltan.
"""

import os
import unittest
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

os.environ.setdefault("CRM_JWT_SECRET", "secreto-solo-para-tests-no-productivo-0123456789")

from app.core import auth_dependencies, autorizacion_carteras, permisos_vistas, security  # noqa: E402
from app.api import routes_cliente, routes_compromisos, routes_telefonos  # noqa: E402
from app.services import telefonos_service  # noqa: E402

try:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    _HAY_TESTCLIENT = True
except Exception:  # httpx no instalado
    _HAY_TESTCLIENT = False


GESTOR_126 = "10000126"
GESTOR_B_126 = "10000226"
SUPER_126_128 = "20000126"
ADMIN = "30000000"
MONITOR = "40000000"
GESTOR_MIBANCO = "50000112"
AGENTE_128 = "60000128"
AGENTE_124 = "70000124"

USUARIOS = {
    GESTOR_126: {"tipo": "GESTOR", "idcartera": 126, "idcarteras": [126]},
    GESTOR_B_126: {"tipo": "GESTOR", "idcartera": 126, "idcarteras": [126]},
    SUPER_126_128: {"tipo": "SUPERVISOR", "idcartera": 126, "idcarteras": [126, 128]},
    ADMIN: {"tipo": "ADMINISTRADOR", "idcartera": 124, "idcarteras": [124]},
    MONITOR: {"tipo": "MONITOR DE CALIDAD", "idcartera": 126, "idcarteras": [126]},
    GESTOR_MIBANCO: {"tipo": "GESTOR", "idcartera": 112, "idcarteras": [112]},
}

CARTERA_DE_AGENTE = {GESTOR_126: 126, GESTOR_B_126: 126, AGENTE_128: 128, AGENTE_124: 124, SUPER_126_128: 126}


def cliente_en(*carteras):
    """Respuesta de buscar_cliente con la cartera SISCOB informada."""
    return {
        "encontrado": True,
        "cliente": {"nombre": "CLIENTE PRUEBA"},
        "gestion": {"carteras_siscob": [{"id": c, "nombre": "X"} for c in carteras]},
    }


@contextmanager
def engine_falso(filas_por_consulta):
    """Engine de SQLAlchemy simulado: registra (sql, params) de cada execute."""
    llamadas = []
    filas = list(filas_por_consulta)

    class Conn:
        def execute(self, query, params=None):
            llamadas.append((str(query), dict(params or {})))
            valor = filas.pop(0) if filas else None
            resultado = MagicMock()
            resultado.fetchone.return_value = valor
            resultado.fetchall.return_value = valor or []
            return resultado

    @contextmanager
    def connect():
        yield Conn()

    engine = MagicMock()
    engine.connect.side_effect = connect
    yield engine, llamadas


@unittest.skipUnless(_HAY_TESTCLIENT, "TestClient requiere httpx (pip install httpx)")
class BaseModulosTest(unittest.TestCase):
    def setUp(self):
        self.activas = {dni: True for dni in USUARIOS}
        self.vistas_individuales = {}

        def identidad(dni):
            u = USUARIOS.get(dni)
            if not u:
                return None
            return {"dni": dni, "agente": f"{dni} - USUARIO PRUEBA", **u}

        self.parches = [
            patch.object(auth_dependencies, "obtener_identidad_usuario", side_effect=identidad),
            patch.object(auth_dependencies, "cuenta_crm_activa", side_effect=lambda d: self.activas.get(d, False)),
            patch.object(auth_dependencies, "cuenta_requiere_cambio_clave", return_value=False),
            patch.object(permisos_vistas, "leer_sobrescrituras",
                         side_effect=lambda d: self.vistas_individuales.get(d, {})),
            patch.object(autorizacion_carteras, "cartera_principal_de_usuario",
                         side_effect=lambda d: CARTERA_DE_AGENTE.get(d)),
        ]
        for p in self.parches:
            p.start()

        app = FastAPI()
        app.include_router(routes_cliente.router, prefix="/cliente")
        app.include_router(routes_compromisos.router, prefix="/compromisos")
        app.include_router(routes_telefonos.router, prefix="/telefonos")
        self.client = TestClient(app)

    def tearDown(self):
        for p in self.parches:
            p.stop()

    def auth(self, dni):
        return {"Authorization": f"Bearer {security.crear_access_token(dni)}"}


# ---------------------------------------------------------------- sesion
class SesionTests(BaseModulosTest):
    RUTAS = [
        "/cliente/buscar?valor=12345678",
        f"/compromisos/{GESTOR_126}",
        "/compromisos/detalle/1",
        "/compromisos/supervisor/resumen",
        f"/compromisos/agente/compromisos?agente={GESTOR_126}",
        "/compromisos/supervisor/exportar-cartera",
        "/telefonos/buscar?q=12345678",
        "/telefonos/filtros",
        "/telefonos/detalle/999999999",
    ]

    def test_sin_token_401_en_todos_los_endpoints(self):
        for ruta in self.RUTAS:
            with self.subTest(ruta=ruta):
                self.assertEqual(self.client.get(ruta).status_code, 401)

    def test_token_invalido_401(self):
        for ruta in self.RUTAS:
            with self.subTest(ruta=ruta):
                resp = self.client.get(ruta, headers={"Authorization": "Bearer no-es-jwt"})
                self.assertEqual(resp.status_code, 401)

    def test_cuenta_deshabilitada_401_con_el_mismo_jwt(self):
        headers = self.auth(SUPER_126_128)
        with patch.object(routes_cliente, "buscar_cliente", return_value=cliente_en(126)), \
             patch.object(routes_compromisos, "obtener_compromisos", return_value=[]), \
             patch.object(routes_telefonos, "buscar_telefonos_cliente", return_value={"ok": True}):
            self.assertEqual(self.client.get("/cliente/buscar?valor=1", headers=headers).status_code, 200)
            self.assertEqual(self.client.get(f"/compromisos/{SUPER_126_128}", headers=headers).status_code, 200)
            self.assertEqual(self.client.get("/telefonos/buscar?q=1", headers=headers).status_code, 200)

            self.activas[SUPER_126_128] = False   # el administrador la deshabilita

            for ruta in self.RUTAS:
                with self.subTest(ruta=ruta):
                    self.assertEqual(self.client.get(ruta, headers=headers).status_code, 401)

    def test_monitor_de_calidad_no_usa_estos_modulos(self):
        h = self.auth(MONITOR)
        with patch.object(routes_cliente, "buscar_cliente") as buscar, \
             patch.object(routes_telefonos, "buscar_telefonos_cliente") as telefonos:
            self.assertEqual(self.client.get("/cliente/buscar?valor=1", headers=h).status_code, 403)
            self.assertEqual(self.client.get(f"/compromisos/{MONITOR}", headers=h).status_code, 403)
            self.assertEqual(self.client.get("/telefonos/buscar?q=1", headers=h).status_code, 403)
        buscar.assert_not_called()
        telefonos.assert_not_called()


# ---------------------------------------------------------------- cliente
DNI_CLIENTE_A = "41000001"
DNI_CLIENTE_B = "41000002"


def fila(dni, operacion="OP1"):
    """Fila de VW_CLIENTE_CRM_SAC (la vista no trae cartera)."""
    return {"DNI": dni, "codcliente": "C1", "CodOperacion": operacion}


class ClienteCarteraTests(BaseModulosTest):
    """Fail closed: sin vision global, TODAS las carteras del cliente (segun
    SISCOB.CLIENTE) deben estar asignadas; si no se pueden determinar, 403."""

    def buscar(self, dni, filas, carteras_por_dni, query="?valor=12345678", error_siscob=None):
        def buscar_falso(valor=None, verificar_acceso=None):
            if not filas:
                return {"encontrado": False}
            if verificar_acceso is not None:
                verificar_acceso([dict(f) for f in filas])
            return {"encontrado": True, "cliente": {"nombre": "CLIENTE PRUEBA"},
                    "operaciones": [{"operacion": f["CodOperacion"]} for f in filas]}

        def carteras_falsas(dnis):
            if error_siscob:
                raise error_siscob
            return {d: set(carteras_por_dni[d]) for d in dnis if carteras_por_dni.get(d)}

        with patch.object(routes_cliente, "buscar_cliente", side_effect=buscar_falso) as buscar, \
             patch.object(autorizacion_carteras, "carteras_compartamos_por_dni",
                          side_effect=carteras_falsas) as carteras:
            resp = self.client.get(f"/cliente/buscar{query}", headers=self.auth(dni))
        return resp, buscar, carteras

    def assert_denegado(self, resp):
        self.assertEqual(resp.status_code, 403)
        self.assertNotIn("CLIENTE PRUEBA", resp.text)
        self.assertNotIn("OP1", resp.text)
        self.assertEqual(resp.headers.get("X-CRM-Codigo-Error"), "ACCESO_DENEGADO")

    def test_cliente_de_su_cartera_se_ve(self):
        resp, _, _ = self.buscar(GESTOR_126, [fila(DNI_CLIENTE_A)], {DNI_CLIENTE_A: {126}})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["encontrado"])

    def test_permiso_individual_habilita_monitor_solo_en_su_cartera(self):
        self.vistas_individuales[MONITOR] = {"clientes": True}
        propia, _, _ = self.buscar(MONITOR, [fila(DNI_CLIENTE_A)], {DNI_CLIENTE_A: {126}})
        ajena, _, _ = self.buscar(MONITOR, [fila(DNI_CLIENTE_A)], {DNI_CLIENTE_A: {124}})
        self.assertEqual(propia.status_code, 200)
        self.assert_denegado(ajena)

    def test_quitar_vista_cliente_bloquea_antes_de_consultar(self):
        self.vistas_individuales[GESTOR_126] = {"clientes": False}
        resp, buscar, _ = self.buscar(GESTOR_126, [fila(DNI_CLIENTE_A)], {DNI_CLIENTE_A: {126}})
        self.assert_denegado(resp)
        buscar.assert_not_called()

    def test_cliente_de_otra_cartera_403(self):
        resp, _, _ = self.buscar(GESTOR_126, [fila(DNI_CLIENTE_A)], {DNI_CLIENTE_A: {124}})
        self.assert_denegado(resp)

    def test_multicartera_con_una_cartera_no_asignada_403(self):
        # Antes se devolvian todas las operaciones si una cartera coincidia.
        filas = [fila(DNI_CLIENTE_A, "OP1"), fila(DNI_CLIENTE_A, "OP2")]
        resp, _, _ = self.buscar(GESTOR_126, filas, {DNI_CLIENTE_A: {124, 126}})
        self.assert_denegado(resp)
        self.assertNotIn("OP2", resp.text)

    def test_multicartera_con_todas_asignadas_se_ve(self):
        resp, _, _ = self.buscar(SUPER_126_128, [fila(DNI_CLIENTE_A)], {DNI_CLIENTE_A: {126, 128}})
        self.assertEqual(resp.status_code, 200)

    def test_grupo_con_un_integrante_de_otra_cartera_403(self):
        filas = [fila(DNI_CLIENTE_A, "OP1"), fila(DNI_CLIENTE_B, "OP2")]
        resp, _, _ = self.buscar(GESTOR_126, filas, {DNI_CLIENTE_A: {126}, DNI_CLIENTE_B: {124}})
        self.assert_denegado(resp)

    def test_grupo_con_todos_en_su_cartera_se_ve(self):
        filas = [fila(DNI_CLIENTE_A, "OP1"), fila(DNI_CLIENTE_B, "OP2")]
        resp, _, _ = self.buscar(GESTOR_126, filas, {DNI_CLIENTE_A: {126}, DNI_CLIENTE_B: {126}})
        self.assertEqual(resp.status_code, 200)

    def test_cartera_no_determinable_403(self):
        # SISCOB no registra el DNI en ninguna cartera Compartamos.
        resp, _, _ = self.buscar(GESTOR_126, [fila(DNI_CLIENTE_A)], {})
        self.assert_denegado(resp)

    def test_un_integrante_sin_cartera_determinable_403(self):
        filas = [fila(DNI_CLIENTE_A, "OP1"), fila(DNI_CLIENTE_B, "OP2")]
        resp, _, _ = self.buscar(GESTOR_126, filas, {DNI_CLIENTE_A: {126}})
        self.assert_denegado(resp)

    def test_fila_sin_dni_403(self):
        resp, _, carteras = self.buscar(GESTOR_126, [fila(None)], {})
        self.assert_denegado(resp)
        carteras.assert_not_called()

    def test_error_consultando_cartera_no_devuelve_datos(self):
        resp, _, _ = self.buscar(GESTOR_126, [fila(DNI_CLIENTE_A)], {},
                                 error_siscob=RuntimeError("timeout SISCOB"))
        self.assertEqual(resp.status_code, 500)
        self.assertNotIn("CLIENTE PRUEBA", resp.text)
        self.assertNotIn("SISCOB", resp.text)

    def test_idcartera_idcarteras_o_perfil_del_navegador_no_amplian(self):
        query = "?valor=12345678&idcartera=124&idcarteras=124,128&perfil=ADMINISTRADOR&tipo=ADMINISTRADOR"
        resp, buscar, _ = self.buscar(GESTOR_126, [fila(DNI_CLIENTE_A)], {DNI_CLIENTE_A: {124}}, query)
        self.assert_denegado(resp)
        self.assertEqual(buscar.call_args.kwargs["valor"], "12345678")
        self.assertIsNotNone(buscar.call_args.kwargs["verificar_acceso"])

    def test_supervisor_con_carteras_adicionales_opera_en_ambas(self):
        for cartera, esperado in ((126, 200), (128, 200), (124, 403)):
            with self.subTest(cartera=cartera):
                resp, _, _ = self.buscar(SUPER_126_128, [fila(DNI_CLIENTE_A)], {DNI_CLIENTE_A: {cartera}})
                self.assertEqual(resp.status_code, esperado)

    def test_vision_global_ve_cualquier_cartera_sin_filtro(self):
        resp, buscar, carteras = self.buscar(ADMIN, [fila(DNI_CLIENTE_A)], {})
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(buscar.call_args.kwargs["verificar_acceso"])
        carteras.assert_not_called()

    def test_usuario_sin_cartera_compartamos_no_accede_al_modulo(self):
        resp, buscar, _ = self.buscar(GESTOR_MIBANCO, [fila(DNI_CLIENTE_A)], {DNI_CLIENTE_A: {126}})
        self.assertEqual(resp.status_code, 403)
        buscar.assert_not_called()

    def test_no_encontrado_responde_normal(self):
        resp, _, _ = self.buscar(GESTOR_126, [], {})
        self.assertEqual(resp.json(), {"encontrado": False})

    def test_error_tecnico_no_se_expone(self):
        with patch.object(routes_cliente, "buscar_cliente", side_effect=RuntimeError("SQL interno")):
            resp = self.client.get("/cliente/buscar?valor=1", headers=self.auth(GESTOR_126))
        self.assertEqual(resp.status_code, 500)
        self.assertNotIn("SQL interno", resp.text)


class ClienteServicioTests(unittest.TestCase):
    """buscar_cliente verifica el acceso con TODAS las filas y antes de
    consultar gestion, pagos y PDP."""

    def test_verificacion_antes_de_armar_la_respuesta(self):
        from app.services import cliente_service

        cursor = MagicMock()
        cursor.description = [("DNI",), ("codcliente",), ("CodOperacion",)]
        cursor.fetchall.side_effect = [
            [("41000001", "C1", "OP1")],                           # coincidencia inicial
            [("41000001", "C1", "OP1"), ("41000001", "C1", "OP2")],  # entidad completa
        ]
        conn = MagicMock()
        conn.cursor.return_value = cursor

        def denegar(filas):
            self.assertEqual([f["CodOperacion"] for f in filas], ["OP1", "OP2"])
            raise autorizacion_carteras.prohibido()

        with patch.object(cliente_service, "get_connection", return_value=conn), \
             patch.object(cliente_service, "construir_respuesta_crm") as construir:
            with self.assertRaises(Exception):
                cliente_service.buscar_cliente(valor="41000001", verificar_acceso=denegar)
        construir.assert_not_called()
        conn.close.assert_called_once()

    def test_sin_verificador_el_comportamiento_no_cambia(self):
        from app.services import cliente_service

        cursor = MagicMock()
        cursor.description = [("DNI",), ("codcliente",), ("CodOperacion",)]
        cursor.fetchall.side_effect = [[("41000001", "C1", "OP1")], [("41000001", "C1", "OP1")]]
        conn = MagicMock()
        conn.cursor.return_value = cursor
        with patch.object(cliente_service, "get_connection", return_value=conn), \
             patch.object(cliente_service, "construir_respuesta_crm", return_value={"encontrado": True}) as construir:
            self.assertEqual(cliente_service.buscar_cliente(valor="41000001"), {"encontrado": True})
        construir.assert_called_once()


class CarterasPorDniTests(unittest.TestCase):
    def test_lee_siscob_cliente_solo_carteras_compartamos(self):
        filas = [SimpleNamespace(DNI="41000001 ", IDCARTERA=126), SimpleNamespace(DNI="41000001", IDCARTERA=124),
                 SimpleNamespace(DNI="41000002", IDCARTERA=128)]
        with engine_falso([filas]) as (engine, llamadas), \
             patch.object(autorizacion_carteras, "engine_siscob", engine):
            mapa = autorizacion_carteras.carteras_compartamos_por_dni(["41000001", " 41000002", "", None])
        self.assertEqual(mapa, {"41000001": {124, 126}, "41000002": {128}})
        sql, params = llamadas[0]
        self.assertIn("SISCOB.DBO.CLIENTE", sql)
        self.assertEqual({v for k, v in params.items() if k.startswith("c")}, set(autorizacion_carteras.CARTERAS_COMPARTAMOS))
        self.assertEqual({v for k, v in params.items() if k.startswith("d")}, {"41000001", "41000002"})

    def test_sin_dnis_no_consulta(self):
        with patch.object(autorizacion_carteras, "engine_siscob") as engine:
            self.assertEqual(autorizacion_carteras.carteras_compartamos_por_dni([]), {})
        engine.connect.assert_not_called()

    def test_una_sola_lista_de_carteras_compartamos_en_el_backend(self):
        from app.services.cliente_crm_service import COMPARTAMOS_CARTERAS
        self.assertEqual(set(autorizacion_carteras.CARTERAS_COMPARTAMOS), set(COMPARTAMOS_CARTERAS))


# ---------------------------------------------------------------- compromisos
class CompromisosTests(BaseModulosTest):
    def test_gestor_con_permiso_individual_ve_equipo_solo_de_su_cartera(self):
        self.vistas_individuales[GESTOR_126] = {"gestiones": True}
        with patch.object(routes_compromisos, "obtener_compromisos", return_value=[]) as obtener:
            propia = self.client.get(f"/compromisos/agente/compromisos?agente={GESTOR_B_126}",
                                     headers=self.auth(GESTOR_126))
            ajena = self.client.get(f"/compromisos/agente/compromisos?agente={AGENTE_128}",
                                   headers=self.auth(GESTOR_126))
        self.assertEqual(propia.status_code, 200)
        self.assertEqual(ajena.status_code, 403)
        obtener.assert_called_once_with(GESTOR_B_126)

    def test_quitar_vista_equipo_revoca_al_supervisor(self):
        self.vistas_individuales[SUPER_126_128] = {"gestiones": False}
        r = self.client.get("/compromisos/supervisor/resumen", headers=self.auth(SUPER_126_128))
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.headers.get("X-CRM-Codigo-Error"), "ACCESO_DENEGADO")
        otro = self.client.get(f"/compromisos/agente/compromisos?agente={AGENTE_128}",
                              headers=self.auth(SUPER_126_128))
        self.assertEqual(otro.status_code, 403)

    def test_quitar_mis_compromisos_bloquea_consulta_propia(self):
        self.vistas_individuales[GESTOR_126] = {"compromisos": False}
        with patch.object(routes_compromisos, "obtener_compromisos") as obtener:
            r = self.client.get(f"/compromisos/{GESTOR_126}", headers=self.auth(GESTOR_126))
        self.assertEqual(r.status_code, 403)
        obtener.assert_not_called()

    def test_agente_ve_sus_compromisos_con_su_dni(self):
        with patch.object(routes_compromisos, "obtener_compromisos", return_value=[{"id": 1}]) as obtener:
            resp = self.client.get(f"/compromisos/{GESTOR_126}", headers=self.auth(GESTOR_126))
        self.assertEqual(resp.status_code, 200)
        obtener.assert_called_once_with(GESTOR_126)

    def test_gestor_no_ve_compromisos_de_otro_agente(self):
        with patch.object(routes_compromisos, "obtener_compromisos") as obtener:
            r1 = self.client.get(f"/compromisos/{AGENTE_128}", headers=self.auth(GESTOR_126))
            r2 = self.client.get(f"/compromisos/agente/compromisos?agente={AGENTE_128}", headers=self.auth(GESTOR_126))
        self.assertEqual((r1.status_code, r2.status_code), (403, 403))
        obtener.assert_not_called()

    def test_supervisor_ve_agentes_de_sus_carteras_y_no_de_otras(self):
        with patch.object(routes_compromisos, "obtener_compromisos", return_value=[]) as obtener:
            ok = self.client.get(f"/compromisos/agente/compromisos?agente={AGENTE_128}", headers=self.auth(SUPER_126_128))
            no = self.client.get(f"/compromisos/agente/compromisos?agente={AGENTE_124}", headers=self.auth(SUPER_126_128))
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(no.status_code, 403)
        obtener.assert_called_once_with(AGENTE_128)

    def test_perfil_en_query_no_da_permiso(self):
        with patch.object(routes_compromisos, "obtener_compromisos") as obtener:
            resp = self.client.get(
                f"/compromisos/agente/compromisos?agente={AGENTE_124}&perfil=ADMINISTRADOR&idcarteras=124",
                headers=self.auth(SUPER_126_128),
            )
        self.assertEqual(resp.status_code, 403)
        obtener.assert_not_called()

    def test_vision_global_ve_cualquier_agente(self):
        with patch.object(routes_compromisos, "obtener_compromisos", return_value=[]):
            resp = self.client.get(f"/compromisos/agente/compromisos?agente={AGENTE_124}", headers=self.auth(ADMIN))
        self.assertEqual(resp.status_code, 200)

    def test_resumen_supervisor_usa_el_dni_del_jwt(self):
        with engine_falso([SimpleNamespace(IDCARTERA=126, TipoUsuario="SUPERVISOR"), []]) as (engine, llamadas), \
             patch("app.core.db_siscob.engine_siscob", engine):
            resp = self.client.get("/compromisos/supervisor/resumen?dni=99999999", headers=self.auth(SUPER_126_128))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(llamadas[0][1], {"dni": SUPER_126_128})

    def test_resumen_supervisor_solo_supervision(self):
        resp = self.client.get("/compromisos/supervisor/resumen", headers=self.auth(GESTOR_126))
        self.assertEqual(resp.status_code, 403)

    def test_exportar_cartera_usa_el_dni_del_jwt(self):
        with engine_falso([[]]) as (engine, llamadas), patch.object(routes_compromisos, "engine_siscob", engine):
            resp = self.client.get("/compromisos/supervisor/exportar-cartera?dni=99999999",
                                   headers=self.auth(SUPER_126_128))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(llamadas[0][1], {"dni": SUPER_126_128})
        self.assertIn(SUPER_126_128, resp.headers["content-disposition"])

    def test_exportar_cartera_solo_supervision(self):
        self.assertEqual(
            self.client.get("/compromisos/supervisor/exportar-cartera", headers=self.auth(GESTOR_126)).status_code, 403)

    def _detalle(self, dni, dni_agente, cartera_agente, cartera_compromiso, query=""):
        fila = SimpleNamespace(
            IDCOMPROMISO=1, TipoContacto="CD", DescripcionIndicador="PDP", NOMBRECLIENTE="CLIENTE PRUEBA",
            DNI="12345678", TELEFONO="999", MONTO=100, MONEDA="PEN", FECHACOMPROMISO="2026-09-30",
            FECHAGENERO="2026-09-01", MONTOPAGADO=0, TIPOPAGO="T", NUMOPERACION="OP1", GESTION="G",
            AGENTE="A", ULT_GESTION=None, ULT_FECHA=None, ULT_AGENTE=None, ULT_CONTACTO=None,
            ULT_INDICADOR=None, IDCARTERA_GESTION=cartera_compromiso,
            DNI_AGENTE=dni_agente, IDCARTERA_AGENTE=cartera_agente,
        )
        with engine_falso([fila]) as (engine, llamadas), patch("app.core.db_siscob.engine_siscob", engine):
            resp = self.client.get(f"/compromisos/detalle/1{query}", headers=self.auth(dni))
        self._sql_detalle = llamadas[0][0] if llamadas else ""
        return resp

    def assert_denegado(self, resp):
        self.assertEqual(resp.status_code, 403)
        self.assertNotIn("CLIENTE PRUEBA", resp.text)
        self.assertEqual(resp.headers.get("X-CRM-Codigo-Error"), "ACCESO_DENEGADO")

    # --- intento de IDOR por id
    def test_idor_gestor_abre_compromiso_de_otro_gestor_de_su_cartera_403(self):
        self.assert_denegado(self._detalle(GESTOR_126, GESTOR_B_126, 126, 126))

    def test_gestor_abre_su_propio_compromiso(self):
        resp = self._detalle(GESTOR_126, GESTOR_126, 126, 126)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["cliente"], "CLIENTE PRUEBA")

    def test_propietario_sale_de_siscob(self):
        self._detalle(GESTOR_126, GESTOR_126, 126, 126)
        self.assertIn("U.USUARIO", self._sql_detalle)
        self.assertIn("U.IDCARTERA AS IDCARTERA_AGENTE", self._sql_detalle)

    def test_supervisor_autorizado(self):
        self.assertEqual(self._detalle(SUPER_126_128, AGENTE_128, 128, 128).status_code, 200)
        self.assertEqual(self._detalle(SUPER_126_128, GESTOR_B_126, 126, 126).status_code, 200)

    def test_supervisor_de_otra_cartera_403(self):
        self.assert_denegado(self._detalle(SUPER_126_128, AGENTE_124, 124, 124))

    def test_supervisor_agente_suyo_pero_compromiso_de_cartera_ajena_403(self):
        self.assert_denegado(self._detalle(SUPER_126_128, AGENTE_128, 128, 124))

    def test_vision_global_ve_cualquier_compromiso(self):
        self.assertEqual(self._detalle(ADMIN, AGENTE_124, 124, 124).status_code, 200)
        self.assertEqual(self._detalle(ADMIN, None, None, None).status_code, 200)

    def test_sin_propietario_determinable_403(self):
        self.assert_denegado(self._detalle(GESTOR_126, None, None, 126))
        self.assert_denegado(self._detalle(SUPER_126_128, None, None, 126))

    def test_parametros_del_navegador_no_cambian_el_propietario(self):
        query = f"?agente={GESTOR_126}&dni={GESTOR_126}&perfil=ADMINISTRADOR&idcartera=126"
        self.assert_denegado(self._detalle(GESTOR_126, GESTOR_B_126, 126, 126, query))

    def test_monitor_de_calidad_no_abre_detalle(self):
        self.assertEqual(self._detalle(MONITOR, MONITOR, 126, 126).status_code, 403)


# ---------------------------------------------------------------- telefonos (router)
class TelefonosRouterTests(BaseModulosTest):
    def test_quitar_vista_impide_llamar_servicio(self):
        self.vistas_individuales[GESTOR_126] = {"telefonos": False}
        with patch.object(routes_telefonos, "buscar_telefonos_cliente") as buscar:
            r = self.client.get("/telefonos/buscar?q=12345678", headers=self.auth(GESTOR_126))
        self.assertEqual(r.status_code, 403)
        buscar.assert_not_called()

    def test_busqueda_restringida_a_las_carteras_del_usuario(self):
        with patch.object(routes_telefonos, "buscar_telefonos_cliente", return_value={"ok": True}) as buscar:
            resp = self.client.get("/telefonos/buscar?q=12345678&perfil=ADMINISTRADOR", headers=self.auth(SUPER_126_128))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(buscar.call_args.kwargs["carteras_permitidas"], [126, 128])

    def test_idcartera_ajena_403(self):
        with patch.object(routes_telefonos, "buscar_telefonos_cliente") as buscar:
            resp = self.client.get("/telefonos/buscar?q=1&idcartera=128", headers=self.auth(GESTOR_126))
        self.assertEqual(resp.status_code, 403)
        buscar.assert_not_called()

    def test_idcartera_propia_acota(self):
        with patch.object(routes_telefonos, "buscar_telefonos_cliente", return_value={"ok": True}) as buscar:
            resp = self.client.get("/telefonos/buscar?q=1&idcartera=126", headers=self.auth(GESTOR_126))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(buscar.call_args.kwargs["idcartera"], "126")
        self.assertEqual(buscar.call_args.kwargs["carteras_permitidas"], [126])

    def test_vision_global_sin_restriccion(self):
        with patch.object(routes_telefonos, "buscar_telefonos_cliente", return_value={"ok": True}) as buscar:
            self.client.get("/telefonos/buscar?q=1", headers=self.auth(ADMIN))
        self.assertIsNone(buscar.call_args.kwargs["carteras_permitidas"])

    def test_filtros_y_detalle_reciben_las_carteras(self):
        with patch.object(routes_telefonos, "listar_filtros_telefonos", return_value={"data": {}}) as filtros, \
             patch.object(routes_telefonos, "obtener_detalle_telefono", return_value={"ok": True}) as detalle:
            self.client.get("/telefonos/filtros", headers=self.auth(GESTOR_126))
            self.client.get("/telefonos/detalle/999", headers=self.auth(GESTOR_126))
        self.assertEqual(filtros.call_args.args, ([126],))
        self.assertEqual(detalle.call_args.args, ("999", [126]))

    def test_error_tecnico_no_se_expone(self):
        with patch.object(routes_telefonos, "buscar_telefonos_cliente", side_effect=RuntimeError("ODBC secreto")):
            resp = self.client.get("/telefonos/buscar?q=1", headers=self.auth(GESTOR_126))
        self.assertEqual(resp.status_code, 500)
        self.assertNotIn("ODBC secreto", resp.text)


# ---------------------------------------------------------------- telefonos (servicio)
class CursorFalso:
    def __init__(self, resultados):
        self.resultados = list(resultados)
        self.consultas = []
        self.description = None
        self._actual = []

    def execute(self, sql, *params):
        self.consultas.append((sql, params))
        columnas, filas = self.resultados.pop(0) if self.resultados else ([], [])
        self.description = [(c,) for c in columnas]
        self._actual = filas

    def fetchall(self):
        return self._actual

    def close(self):
        pass


class TelefonosServicioTests(unittest.TestCase):
    def conexion(self, cursor):
        conn = MagicMock()
        conn.cursor.return_value = cursor
        return patch.object(telefonos_service, "get_connection", return_value=conn)

    def test_busqueda_agrega_in_de_carteras_permitidas(self):
        cursor = CursorFalso([])
        with self.conexion(cursor):
            telefonos_service.buscar_telefonos_cliente(q="12345678", carteras_permitidas=[128, 126])
        sql, params = cursor.consultas[0]
        self.assertIn("AND IDCARTERA IN (?,?)", sql)
        self.assertEqual(list(params[-2:]), [126, 128])

    def test_sin_carteras_no_devuelve_nada(self):
        cursor = CursorFalso([])
        with self.conexion(cursor):
            telefonos_service.buscar_telefonos_cliente(q="12345678", carteras_permitidas=[])
        self.assertIn("AND 1 = 0", cursor.consultas[0][0])

    def test_vision_global_no_agrega_filtro(self):
        cursor = CursorFalso([])
        with self.conexion(cursor):
            telefonos_service.buscar_telefonos_cliente(q="12345678", carteras_permitidas=None)
        self.assertNotIn("IDCARTERA IN", cursor.consultas[0][0])

    def test_relacionados_y_detalle_solo_de_carteras_permitidas(self):
        columnas = ["DNI", "IDCLIENTE", "NOMBRE_CLIENTE", "IDCARTERA", "ORIGEN", "TIPO_BASE", "T_EMP"]
        filas = [("111", 1, "PROPIO", 126, "E", "B", "T"), ("222", 2, "AJENO", 124, "E", "B", "T")]
        cursor = CursorFalso([(columnas, filas)])
        with self.conexion(cursor):
            resultado = telefonos_service.obtener_detalle_telefono("999", [126])
        self.assertEqual([r["NOMBRE_CLIENTE"] for r in resultado["data"]], ["PROPIO"])

    def test_detalle_de_telefono_solo_ajeno_da_no_encontrado(self):
        columnas = ["DNI", "IDCLIENTE", "NOMBRE_CLIENTE", "IDCARTERA", "ORIGEN", "TIPO_BASE", "T_EMP"]
        cursor = CursorFalso([(columnas, [("222", 2, "AJENO", 124, "E", "B", "T")])])
        with self.conexion(cursor):
            with self.assertRaises(ValueError):
                telefonos_service.obtener_detalle_telefono("999", [126])

    def test_filtros_solo_carteras_permitidas(self):
        resultados = [(["IDCARTERA"], [(124,), (126,), (128,)])] + [(["X"], [])] * 5
        cursor = CursorFalso(resultados)
        with self.conexion(cursor):
            data = telefonos_service.listar_filtros_telefonos([126, 128])["data"]
        self.assertEqual([c["idcartera"] for c in data["carteras"]], [126, 128])


# ---------------------------------------------------------------- codigos 403
class CodigosError403Tests(BaseModulosTest):
    """El frontend distingue los 403 por la cabecera X-CRM-Codigo-Error."""

    def test_401_sin_codigo_de_403(self):
        resp = self.client.get("/cliente/buscar?valor=1")
        self.assertEqual(resp.status_code, 401)
        self.assertIsNone(resp.headers.get("X-CRM-Codigo-Error"))

    def test_cambio_obligatorio_lleva_su_codigo_y_mantiene_el_detail(self):
        with patch.object(auth_dependencies, "cuenta_requiere_cambio_clave", return_value=True):
            for ruta in SesionTests.RUTAS:
                with self.subTest(ruta=ruta):
                    resp = self.client.get(ruta, headers=self.auth(GESTOR_126))
                    self.assertEqual(resp.status_code, 403)
                    self.assertEqual(resp.headers.get("X-CRM-Codigo-Error"), "CAMBIO_CLAVE_OBLIGATORIO")
                    self.assertEqual(resp.json()["detail"], auth_dependencies.MENSAJE_CAMBIO_CLAVE)

    def test_acceso_denegado_lleva_otro_codigo(self):
        casos = [
            (GESTOR_126, "/compromisos/supervisor/resumen"),
            (GESTOR_126, f"/compromisos/{AGENTE_128}"),
            (MONITOR, "/cliente/buscar?valor=1"),
            (GESTOR_MIBANCO, "/cliente/buscar?valor=1"),
            (GESTOR_126, "/telefonos/buscar?q=1&idcartera=124"),
        ]
        for dni, ruta in casos:
            with self.subTest(ruta=ruta, dni=dni):
                resp = self.client.get(ruta, headers=self.auth(dni))
                self.assertEqual(resp.status_code, 403)
                self.assertEqual(resp.headers.get("X-CRM-Codigo-Error"), "ACCESO_DENEGADO")
                self.assertNotEqual(resp.json()["detail"], auth_dependencies.MENSAJE_CAMBIO_CLAVE)

    def test_requiere_administrador_usa_acceso_denegado(self):
        from fastapi import HTTPException
        with self.assertRaises(HTTPException) as ctx:
            auth_dependencies.requiere_administrador({"dni": GESTOR_126, "tipo": "GESTOR"})
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertEqual(ctx.exception.headers["X-CRM-Codigo-Error"], "ACCESO_DENEGADO")

    def test_codigo_legible_desde_otro_origen_con_el_cors_actual(self):
        # Misma configuracion CORS que app/main.py (no se modifica).
        from fastapi.middleware.cors import CORSMiddleware
        app = FastAPI()
        app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                           allow_methods=["*"], allow_headers=["*"])
        app.include_router(routes_cliente.router, prefix="/cliente")
        cliente = TestClient(app)
        origen = {"Origin": "http://localhost:5500"}

        denegado = cliente.get("/cliente/buscar?valor=1", headers={**self.auth(MONITOR), **origen})
        with patch.object(auth_dependencies, "cuenta_requiere_cambio_clave", return_value=True):
            cambio = cliente.get("/cliente/buscar?valor=1", headers={**self.auth(GESTOR_126), **origen})

        for resp, codigo in ((denegado, "ACCESO_DENEGADO"), (cambio, "CAMBIO_CLAVE_OBLIGATORIO")):
            with self.subTest(codigo=codigo):
                self.assertEqual(resp.status_code, 403)
                self.assertEqual(resp.headers.get("X-CRM-Codigo-Error"), codigo)
                self.assertIn("X-CRM-Codigo-Error", resp.headers.get("access-control-expose-headers", ""))
                self.assertTrue(resp.headers.get("access-control-allow-origin"))


# ---------------------------------------------------------------- reglas
class ReglasCarteraTests(unittest.TestCase):
    def test_carteras_usuario_combina_principal_y_adicionales(self):
        u = {"tipo": "SUPERVISOR", "idcartera": "126", "idcarteras": [128, "133"]}
        self.assertEqual(autorizacion_carteras.carteras_usuario(u), {126, 128, 133})

    def test_vision_global_solo_perfiles_existentes(self):
        for tipo in ("ADMINISTRADOR", "Jefe de Cartera", "JEFE DE COBRANZA"):
            self.assertTrue(autorizacion_carteras.tiene_vision_global({"tipo": tipo}))
        for tipo in ("SUPERVISOR", "GESTOR", "MONITOR DE CALIDAD", ""):
            self.assertFalse(autorizacion_carteras.tiene_vision_global({"tipo": tipo}))

    def test_cartera_invalida_no_se_permite(self):
        u = {"tipo": "GESTOR", "idcartera": 126, "idcarteras": [126]}
        self.assertFalse(autorizacion_carteras.cartera_permitida(u, None))
        self.assertFalse(autorizacion_carteras.cartera_permitida(u, "abc"))
        self.assertTrue(autorizacion_carteras.cartera_permitida(u, "126"))


if __name__ == "__main__":
    unittest.main()
