"""Casos de atribución y de gestión posteriores sin red ni SQL real."""

import unittest
import time
from copy import deepcopy
from contextlib import contextmanager
from datetime import datetime
from datetime import date
from unittest.mock import patch

from app.services import respuestas_mowa_service as mowa
from app.api.routes_respuestas_mowa import opciones_respuestas_mowa
from app.api.routes_respuestas_mowa import EnvioSms, enviar_sms_mowa, historial_sms_mowa
from fastapi import HTTPException
import requests


class _Resultado:
    def __init__(self, filas): self.filas = filas
    def mappings(self): return self.filas


class _Conexion:
    def __init__(self, filas): self.filas = filas
    def execute(self, _sql, _params):
        assert "SELECT TOP 1 G.IdGestion, G.Fecha, G.Hora, G.Gestion" in str(_sql)
        return _Resultado(self.filas)


class _Motor:
    # SISCOB devuelve siempre estado_cliente; por defecto los casos usan activos.
    def __init__(self, filas): self.filas = [{"estado_cliente": "A", **f} for f in filas]
    @contextmanager
    def connect(self): yield _Conexion(self.filas)


class RespuestasMowaTests(unittest.TestCase):
    def setUp(self):
        mowa.limpiar_cache_respuestas()
        self.campana = {
            "campaign_id": 100, "description": "Prueba",
            "messages": [
                {"id": 501, "dni": "12345678", "cartera_id": 126, "msisdn": "999111222",
                 "text": "Mensaje enviado A", "send_date": "2026-11-19 10:00:30"},
                {"id": 502, "dni": "87654321", "cartera_id": 126, "msisdn": "999333444"},
                {"id": 503, "dni": "0", "cartera_id": 126, "msisdn": "999555666"},
            ],
        }
        self.respuestas = {"responses": [
            {"id": 1, "message_id": 501, "msisdn": "999111222", "text": "Llámame", "received_date": "2026-11-19 10:15:00", "status": 2, "label_status": "ASESORAMIENTO"},
            {"id": 2, "message_id": 502, "msisdn": "999333444", "text": "Consulta", "received_date": "2026-11-19 10:15:00"},
            {"id": 3, "message_id": 503, "msisdn": "999555666", "text": "Hola", "received_date": "2026-11-19 10:15:00"},
        ]}

    def test_clasificacion_respeta_hora_y_no_atribuye_telefono(self):
        clientes = [
            {"dni": "12345678", "idcliente": 11, "idcartera": 126, "cliente": "Cliente A", "gestion_id": 41, "gestion_texto": "Se llamó al cliente", "gestion_fecha": datetime(2026,11,19), "gestion_hora": "10:16:00"},
            {"dni": "87654321", "idcliente": 12, "idcartera": 126, "cliente": "Cliente B", "gestion_fecha": datetime(2026,11,19), "gestion_hora": "10:14:00"},
        ]
        with patch.object(mowa, "_get_json", return_value=self.respuestas), patch.object(mowa, "engine_siscob", _Motor(clientes)):
            filas = mowa._respuestas_de_campana("COMPARVIGENTE", "dummy", self.campana)
            mowa._enriquecer_clientes(filas, {126})
        self.assertEqual([r["estado"] for r in filas], ["ATENDIDA", "PENDIENTE", "SIN_VINCULAR"])
        self.assertEqual(filas[0]["idcliente"], 11)
        self.assertEqual(filas[0]["mensaje_enviado"], "Mensaje enviado A")
        self.assertEqual(filas[0]["mensaje_enviado_fecha"], "2026-11-19T10:00:30")
        self.assertEqual(filas[0]["estado_mowa_codigo"], 2)
        self.assertEqual(filas[0]["estado_mowa_etiqueta"], "ASESORAMIENTO")
        self.assertEqual(filas[0]["gestion_posterior_texto"], "Se llamó al cliente")
        self.assertEqual(filas[0]["gestion_posterior_id"], 41)
        self.assertIsNone(filas[2]["idcliente"])

    def test_sin_cartera_mowa_y_sin_gestion_es_pendiente_si_dni_es_unico(self):
        campana = {"campaign_id": 100, "messages": [
            {"id": 501, "dni": "12345678", "cartera_id": 0, "msisdn": "999111222"},
        ]}
        respuesta = {"responses": [
            {"id": 1, "message_id": 501, "received_date": "2026-11-19 10:15:00", "text": "Sí"},
        ]}
        cliente = [{"dni": "12345678", "idcliente": 11, "idcartera": 126,
                    "cliente": "Cliente A", "gestion_fecha": None, "gestion_hora": None}]
        with patch.object(mowa, "_get_json", return_value=respuesta), patch.object(mowa, "engine_siscob", _Motor(cliente)):
            filas = mowa._respuestas_de_campana("COMPARVIGENTE", "dummy", campana)
            mowa._enriquecer_clientes(filas, {126})
        self.assertEqual(filas[0]["estado"], "PENDIENTE")
        self.assertEqual(filas[0]["idcartera"], 126)
        self.assertIn("Cuenta Mowa y DNI", filas[0]["vinculo"])

    def test_cuenta_compartida_no_fabrica_coincidencia_unica_por_permiso(self):
        fila = {"cuenta": "COMPARVIGENTE", "dni": "12345678", "cartera_mowa": 0,
                "recibido": "2026-11-19T10:15:00", "estado": "SIN_VINCULAR", "idcartera": None}
        clientes = [
            {"dni": "12345678", "idcliente": 11, "idcartera": 126, "cliente": "A", "gestion_fecha": None, "gestion_hora": None},
            {"dni": "12345678", "idcliente": 12, "idcartera": 128, "cliente": "B", "gestion_fecha": None, "gestion_hora": None},
        ]
        with patch.object(mowa, "engine_siscob", _Motor(clientes)):
            mowa._enriquecer_clientes([fila], {126})
        self.assertIsNone(fila["idcartera"])
        self.assertEqual(fila["estado"], "SIN_VINCULAR")

    def test_opciones_supervisor_124_y_administrador(self):
        supervisor = {"dni": "s", "tipo": "SUPERVISOR", "idcartera": 124,
                      "permisos_vistas": {"respuestas_mowa": True}}
        admin = {"dni": "a", "tipo": "ADMINISTRADOR",
                 "permisos_vistas": {"respuestas_mowa": True}}
        opciones = opciones_respuestas_mowa(usuario=supervisor)
        self.assertEqual(opciones["alcance_carteras"], [124])
        self.assertFalse(opciones["puede_actualizar"])
        self.assertEqual([c["id"] for c in opciones["cuentas"]], ["COMPARCARTIGO"])
        opciones_admin = opciones_respuestas_mowa(usuario=admin)
        self.assertIsNone(opciones_admin["alcance_carteras"])
        self.assertTrue(opciones_admin["puede_actualizar"])

    def test_sin_hora_mismo_dia_queda_sin_verificar(self):
        self.assertIsNone(mowa._fecha_gestion(datetime(2026, 11, 19), None))
        self.assertEqual(mowa._fecha_gestion(datetime(2026, 11, 19), "11:00:00"), datetime(2026, 11, 19, 11))

    def test_mowa_fecha_sin_hora_no_inventa_medianoche(self):
        campana = {"campaign_id": 100, "send_date": "2026-11-19", "messages": [
            {"id": 501, "dni": "12345678", "cartera_id": 126, "msisdn": "999111222",
             "text": "Aviso", "send_date": "2026-11-19"}]}
        respuesta = {"responses": [{"id": 1, "message_id": 501, "received_date": "2026-11-19",
                                     "msisdn": "999111222", "text": "Sí"}]}
        cliente = [{"dni": "12345678", "idcliente": 11, "idcartera": 126,
                    "cliente": "A", "gestion_fecha": None, "gestion_hora": None}]
        with patch.object(mowa, "_get_json", return_value=respuesta), \
             patch.object(mowa, "engine_siscob", _Motor(cliente)):
            filas = mowa._respuestas_de_campana("COMPARVIGENTE", "dummy", campana)
            mowa._enriquecer_clientes(filas, {126})
        self.assertEqual(filas[0]["recibido"], "2026-11-19")
        self.assertEqual(filas[0]["mensaje_enviado_fecha"], "2026-11-19")
        self.assertEqual(filas[0]["estado"], "SIN_VERIFICAR")

    def test_cuenta_fuera_de_cartera_no_se_consulta(self):
        visibles = [nombre for nombre, _, _ in mowa._cuentas_visibles({117})]
        self.assertEqual(visibles, ["INTERBANK_BC"])

    def test_cuenta_compartida_filtra_respuestas_de_otra_cartera(self):
        filas = [
            {"cuenta":"COMPARVIGENTE", "campana_id":1, "id":"1", "mensaje_id":"1", "recibido":"2026-11-19T10:00:00", "texto":"A", "dni":"1", "idcartera":126},
            {"cuenta":"COMPARVIGENTE", "campana_id":1, "id":"2", "mensaje_id":"2", "recibido":"2026-11-19T10:00:00", "texto":"B", "dni":"2", "idcartera":128},
        ]
        with patch.object(mowa, "_cuentas_visibles", return_value=[("COMPARVIGENTE", (126,128), "dummy")]), \
             patch.object(mowa, "_campanas", return_value=[("COMPARVIGENTE", "dummy", {"campaign_id":1})]), \
             patch.object(mowa, "_respuestas_de_campana", return_value=filas), \
             patch.object(mowa, "_enriquecer_clientes"):
            resultado = mowa.consultar_respuestas(date(2026,11,19), date(2026,11,19), {126})
        self.assertEqual([r["id"] for r in resultado["data"]], ["1"])

    def test_supervisor_124_solo_recibe_su_cartera_y_jefe_recibe_ambas(self):
        filas = [
            {"cuenta":"COMPARCARTIGO", "campana_id":1, "id":"1", "mensaje_id":"1",
             "recibido":"2026-11-19T10:00:00", "texto":"A", "dni":"1", "idcartera":124},
            {"cuenta":"COMPARCARTIGO", "campana_id":1, "id":"2", "mensaje_id":"2",
             "recibido":"2026-11-19T10:00:00", "texto":"B", "dni":"2", "idcartera":126},
        ]
        with patch.object(mowa, "_cuentas_visibles", return_value=[("COMPARCARTIGO", (124,), "dummy")]), \
             patch.object(mowa, "_campanas", return_value=[("COMPARCARTIGO", "dummy", {"campaign_id":1})]), \
             patch.object(mowa, "_respuestas_de_campana", return_value=filas), \
             patch.object(mowa, "_enriquecer_clientes"):
            supervisor = mowa.consultar_respuestas(date(2026,11,19), date(2026,11,19), {124})
            jefe = mowa.consultar_respuestas(date(2026,11,19), date(2026,11,19), None)
        self.assertEqual([r["idcartera"] for r in supervisor["data"]], [124])
        self.assertEqual({r["idcartera"] for r in jefe["data"]}, {124, 126})

    def test_seleccion_de_cuenta_evitaria_consultar_las_otras(self):
        cuentas = [("INTERBANK_BC", (117,), "a"), ("COMPARVIGENTE", (126,), "b")]
        with patch.object(mowa, "_cuentas_visibles", return_value=cuentas), \
             patch.object(mowa, "_campanas", return_value=[]) as buscar:
            resultado = mowa.consultar_respuestas(date(2026,11,19), date(2026,11,19), None, "INTERBANK_BC")
        self.assertEqual(buscar.call_count, 1)
        self.assertEqual(buscar.call_args.args[0], "INTERBANK_BC")
        self.assertTrue(resultado["completo"])

    def test_campanas_adicionales_se_consultan_en_otra_pagina(self):
        campanas = [("INTERBANK_BC", "a", {"campaign_id": i, "creation_date": f"2026-11-19 10:{i:02d}"}) for i in range(4)]
        def respuesta(_nombre, _key, campana):
            cid = campana["campaign_id"]
            return [{"cuenta": "INTERBANK_BC", "campana_id": cid, "id": str(cid),
                     "mensaje_id": str(cid), "recibido": "2026-11-19T10:00:00",
                     "texto": f"Respuesta {cid}", "dni": "", "idcartera": None}]
        with patch.object(mowa, "_cuentas_visibles", return_value=[("INTERBANK_BC", (117,), "a")]), \
             patch.object(mowa, "_campanas", return_value=campanas) as buscar, \
             patch.object(mowa, "_respuestas_de_campana", side_effect=respuesta) as respuestas, \
             patch.object(mowa, "MAX_CAMPANAS", 2):
            primera = mowa.consultar_respuestas(date(2026,11,19), date(2026,11,19), None,
                                                usuario_id="admin")
            segunda = mowa.consultar_respuestas(date(2026,11,19), date(2026,11,19), None,
                                                offset=2, snapshot_token=primera["snapshot_token"],
                                                usuario_id="admin")
        self.assertEqual(respuestas.call_count, 4)
        self.assertEqual({r["texto"] for r in primera["data"] + segunda["data"]},
                         {f"Respuesta {i}" for i in range(4)})
        self.assertEqual(buscar.call_count, 1)  # La segunda página no repite Mowa.
        self.assertEqual(primera["total_campanas"], segunda["total_campanas"])
        self.assertEqual(primera["siguiente_offset"], 2)
        self.assertFalse(primera["completo"])
        self.assertIsNone(segunda["siguiente_offset"])
        self.assertTrue(segunda["completo"])
        with self.assertRaises(mowa.SnapshotNoDisponible):
            mowa.consultar_respuestas(date(2026,11,19), date(2026,11,19), None,
                                     offset=2, snapshot_token=primera["snapshot_token"],
                                     usuario_id="otro_usuario")

    def test_timeout_semanal_reintenta_en_dos_rangos(self):
        llamadas = []
        def buscar(nombre, key, desde, hasta):
            llamadas.append((desde, hasta))
            if desde == date(2026, 11, 1) and hasta == date(2026, 11, 7):
                raise mowa.MowaError("Consulta Mowa fallida (ReadTimeout).") from requests.ReadTimeout()
            return [(nombre, key, {"campaign_id": len(llamadas)})]
        with patch.object(mowa, "_campanas", side_effect=buscar):
            resultado = mowa._campanas_con_rescate("PROPIA_BIZNES", "dummy",
                                                    date(2026, 11, 1), date(2026, 11, 7))
        self.assertEqual(llamadas, [(date(2026,11,1), date(2026,11,7)),
                                    (date(2026,11,1), date(2026,11,4)),
                                    (date(2026,11,5), date(2026,11,7))])
        self.assertEqual(len(resultado), 2)

    def test_cuenta_fallida_queda_parcial_sin_repetir_busqueda_por_pagina(self):
        campanas = [("INTERBANK_BC", "a", {"campaign_id": i}) for i in range(4)]
        def buscar(nombre, *_args):
            if nombre == "PROPIA_BIZNES":
                raise mowa.MowaError("Consulta Mowa fallida (ReadTimeout).")
            return campanas
        with patch.object(mowa, "_cuentas_visibles", return_value=[
                ("INTERBANK_BC", (117,), "a"), ("PROPIA_BIZNES", (137,), "b")]), \
             patch.object(mowa, "_campanas", side_effect=buscar) as llamadas, \
             patch.object(mowa, "_respuestas_de_campana", return_value=[]), \
             patch.object(mowa, "MAX_CAMPANAS", 2):
            primera = mowa.consultar_respuestas(date(2026,11,19), date(2026,11,19), None,
                                                usuario_id="admin")
            segunda = mowa.consultar_respuestas(date(2026,11,19), date(2026,11,19), None,
                                                offset=2, snapshot_token=primera["snapshot_token"],
                                                usuario_id="admin")
        self.assertEqual(llamadas.call_count, 2)
        self.assertEqual(len(primera["advertencias"]), 1)
        self.assertEqual(segunda["advertencias"], [])
        self.assertFalse(segunda["completo"])

    def test_campana_lenta_no_bloquea_el_resultado(self):
        campana = [("INTERBANK_BC", "a", {"campaign_id": 1})]
        def respuesta_lenta(*_args):
            time.sleep(0.08)
            return []
        with patch.object(mowa, "_cuentas_visibles", return_value=[("INTERBANK_BC", (117,), "a")]), \
             patch.object(mowa, "_campanas", return_value=campana), \
             patch.object(mowa, "_respuestas_de_campana", side_effect=respuesta_lenta), \
             patch.object(mowa, "PRESUPUESTO_RESPUESTAS_SEGUNDOS", 0.01):
            resultado = mowa.consultar_respuestas(date(2026,11,19), date(2026,11,19), None)
        self.assertFalse(resultado["completo"])
        self.assertIn("no respondieron a tiempo", " ".join(resultado["advertencias"]))

    def test_envio_revalida_respuesta_cliente_cartera_y_destino(self):
        origen = {"id": 501, "dni": "12345678", "cartera_id": 126,
                  "msisdn": "999111222", "text": "Mensaje original", "send_date": "2026-11-19 10:00:00"}
        cliente = [{"dni": "12345678", "idcliente": 11, "idcartera": 126,
                    "cliente": "Cliente A", "gestion_fecha": None, "gestion_hora": None}]
        llamadas = []
        def proveedor(metodo, url, _key, **kwargs):
            llamadas.append((metodo, url, kwargs))
            if "campaigns/search" in url:
                return [{"campaign_id": 100, "messages": [origen]}]
            if "/response" in url: return self.respuestas
            if url == mowa.MOWA_SIMPLE:
                return {"id": 700, "campaign_id": 800, "status": 1,
                        "label_status": "Pendiente de Envío", "creation_date": "2026-11-19 10:20:00"}
            raise AssertionError(url)
        with patch.object(mowa, "_get_json", side_effect=proveedor), \
             patch.object(mowa, "engine_siscob", _Motor(cliente)), \
             patch.dict(mowa.os.environ, {"MOWA_KEY_COMPARVIGENTE": "dummy"}):
            resultado = mowa.enviar_respuesta("COMPARVIGENTE", 100, 1, 501,
                                              date(2026, 11, 19), "Respuesta de prueba", {126})
        self.assertEqual(resultado["mensaje_id"], "700")
        self.assertEqual(resultado["idcliente"], 11)
        self.assertIn("/campaigns/search", llamadas[0][1])
        self.assertEqual(llamadas[0][2]["json"], {"fromDate": "2026-11-19", "toDate": "2026-11-19"})
        self.assertEqual(llamadas[-1][2]["json"], {"msisdn": "999111222", "text": "Respuesta de prueba",
                                                  "type": 1, "dni": "12345678", "cartera": 126})

    def test_envio_no_usa_numero_del_navegador_ni_otra_cartera(self):
        origen = {"id": 501, "dni": "12345678", "cartera_id": 126, "msisdn": "999111222"}
        with patch.object(mowa, "_get_json", return_value=origen) as proveedor, \
             patch.dict(mowa.os.environ, {"MOWA_KEY_COMPARVIGENTE": "dummy"}):
            with self.assertRaises(ValueError):
                mowa.enviar_respuesta("COMPARVIGENTE", 100, 1, 501,
                                     date(2026, 11, 19), "Hola", {124})
        proveedor.assert_not_called()
        respuestas = deepcopy(self.respuestas)
        respuestas["responses"][0]["msisdn"] = "999000000"
        with patch.object(mowa, "_get_json", side_effect=[[{"campaign_id": 100, "messages": [origen]}], respuestas]) as proveedor, \
             patch.dict(mowa.os.environ, {"MOWA_KEY_COMPARVIGENTE": "dummy"}):
            with self.assertRaises(ValueError):
                mowa.enviar_respuesta("COMPARVIGENTE", 100, 1, 501,
                                     date(2026, 11, 19), "Hola", {126})
        self.assertEqual(proveedor.call_count, 2)

    def test_envio_rechaza_cuenta_ajena_al_supervisor_124(self):
        supervisor = {"dni": "s", "tipo": "SUPERVISOR", "idcartera": 124,
                      "permisos_vistas": {"respuestas_mowa": True}}
        payload = EnvioSms(cuenta="INTERBANK_BC", campana_id=1, respuesta_id=2,
                           mensaje_id=3, fecha_campana=date(2026, 11, 19), texto="Hola")
        with patch("app.api.routes_respuestas_mowa.enviar_respuesta") as enviar:
            with self.assertRaises(HTTPException) as error:
                enviar_sms_mowa(payload, usuario=supervisor).send(None)
        self.assertEqual(error.exception.status_code, 403)
        enviar.assert_not_called()

    def test_historial_incluye_sms_sin_respuesta_y_filtra_otro_cliente(self):
        origen = {"id": 501, "dni": "12345678", "cartera_id": 126,
                  "msisdn": "999111222", "text": "Aviso"}
        campanas = [
            {"campaign_id": 100, "creation_date": "2026-11-19 09:00:00", "messages": [
                {**origen, "send_date": "2026-11-19 09:10:00"}]},
            {"campaign_id": 200, "creation_date": "2026-11-19 11:00:00", "messages": [
                {"id": 601, "dni": "12345678", "cartera_id": 126, "msisdn": "999111222",
                 "text": "Seguimiento", "send_date": "2026-11-19 11:01:00"},
                {"id": 602, "dni": "87654321", "cartera_id": 126, "msisdn": "999111222",
                 "text": "Otro cliente"}]},
        ]
        cliente = [{"dni": "12345678", "idcliente": 11, "idcartera": 126,
                    "cliente": "A", "gestion_fecha": None, "gestion_hora": None}]
        filtros = []
        def proveedor(metodo, url, _key, **kwargs):
            if "campaigns/search" in url:
                filtros.append(kwargs["json"])
                return campanas
            if "/response" in url:
                return self.respuestas if "/100/" in url else {"responses": []}
            raise AssertionError(url)
        with patch.object(mowa, "_get_json", side_effect=proveedor), \
             patch.object(mowa, "engine_siscob", _Motor(cliente)), \
             patch.dict(mowa.os.environ, {"MOWA_KEY_COMPARVIGENTE": "dummy"}):
            resultado = mowa.consultar_historial("COMPARVIGENTE", 100, 1, 501,
                                                  date(2026, 11, 19), date(2026, 11, 1),
                                                  date(2026, 11, 19), {126})
        self.assertTrue(resultado["completo"])
        self.assertEqual(filtros[0], {"fromDate": "2026-11-19", "toDate": "2026-11-19"})
        self.assertEqual(filtros[1]["msisdn"], "999111222")
        self.assertEqual({e["texto"] for e in resultado["eventos"]},
                         {"Aviso", "Seguimiento", "Llámame"})

    def test_historial_rechaza_cuenta_ajena_al_supervisor_124(self):
        supervisor = {"dni": "s", "tipo": "SUPERVISOR", "idcartera": 124,
                      "permisos_vistas": {"respuestas_mowa": True}}
        with patch("app.api.routes_respuestas_mowa.consultar_historial") as consultar:
            with self.assertRaises(HTTPException) as error:
                historial_sms_mowa(cuenta="INTERBANK_BC", campana_id=1,
                                  respuesta_id=2, mensaje_id=3, fecha_campana=date(2026, 11, 19),
                                  desde=date(2026, 11, 1),
                                  hasta=date(2026, 11, 19), usuario=supervisor).send(None)
        self.assertEqual(error.exception.status_code, 403)
        consultar.assert_not_called()

    def test_historial_reintenta_por_semanas_si_filtro_celular_falla(self):
        cliente = {"dni": "12345678", "idcliente": 11, "idcartera": 126}
        with patch.object(mowa, "_verificar_ancla", return_value=("dummy", cliente, "999111222")), \
             patch.object(mowa, "_campanas", side_effect=[mowa.MowaError("HTTP 400", 400), [], [], []]) as buscar:
            resultado = mowa.consultar_historial("COMPARVIGENTE", 100, 1, 501,
                                                  date(2026, 11, 19), date(2026, 11, 1),
                                                  date(2026, 11, 19), {126})
        self.assertTrue(resultado["completo"])
        self.assertEqual(buscar.call_count, 4)
        self.assertEqual(buscar.call_args_list[0].kwargs["telefono"], "999111222")
        self.assertEqual(buscar.call_args_list[1].args[2:4], (date(2026, 11, 1), date(2026, 11, 7)))

    def test_cliente_inactivo_se_excluye_y_se_cuenta(self):
        campana = {"campaign_id": 100, "messages": [
            {"id": 501, "dni": "12345678", "cartera_id": 126, "msisdn": "999111222"},
            {"id": 502, "dni": "87654321", "cartera_id": 126, "msisdn": "999333444"},
        ]}
        respuestas = {"responses": [
            {"id": 1, "message_id": 501, "received_date": "2026-11-19 10:15:00", "text": "A"},
            {"id": 2, "message_id": 502, "received_date": "2026-11-19 10:15:00", "text": "B"},
        ]}
        clientes = [
            {"dni": "12345678", "idcliente": 11, "idcartera": 126, "cliente": "Activo",
             "estado_cliente": "A", "gestion_fecha": None, "gestion_hora": None},
            {"dni": "87654321", "idcliente": 12, "idcartera": 126, "cliente": "Retirado",
             "estado_cliente": "R", "gestion_fecha": None, "gestion_hora": None},
        ]
        with patch.object(mowa, "_cuentas_visibles", return_value=[("COMPARVIGENTE", (126, 128, 133), "k")]), \
             patch.object(mowa, "_campanas", return_value=[("COMPARVIGENTE", "k", campana)]), \
             patch.object(mowa, "_get_json", return_value=respuestas), \
             patch.object(mowa, "engine_siscob", _Motor(clientes)):
            admin = mowa.consultar_respuestas(date(2026,11,19), date(2026,11,19), None)
            otra = mowa.consultar_respuestas(date(2026,11,19), date(2026,11,19), {124})
        self.assertEqual([r["cliente"] for r in admin["data"]], ["Activo"])
        self.assertEqual(admin["excluidas_inactivas"], 1)
        self.assertEqual(otra["excluidas_inactivas"], 0)  # No revela conteos de otra cartera.

    def test_registro_inactivo_anterior_en_misma_cartera_no_vuelve_ambiguo(self):
        fila = {"cuenta": "COMPARVIGENTE", "dni": "12345678", "cartera_mowa": 0,
                "recibido": "2026-11-19T10:15:00", "estado": "SIN_VINCULAR", "idcartera": None}
        clientes = [
            {"dni": "12345678", "idcliente": 10, "idcartera": 126, "cliente": "Viejo",
             "estado_cliente": "R", "gestion_fecha": None, "gestion_hora": None},
            {"dni": "12345678", "idcliente": 11, "idcartera": 126, "cliente": "Vigente",
             "estado_cliente": "N", "gestion_fecha": None, "gestion_hora": None},
        ]
        with patch.object(mowa, "engine_siscob", _Motor(clientes)):
            mowa._enriquecer_clientes([fila], None)
        self.assertEqual((fila["idcliente"], fila["estado"]), (11, "PENDIENTE"))

    def test_inactivo_en_otra_cartera_sigue_siendo_ambiguo(self):
        fila = {"cuenta": "COMPARVIGENTE", "dni": "12345678", "cartera_mowa": 0,
                "recibido": "2026-11-19T10:15:00", "estado": "SIN_VINCULAR", "idcartera": None}
        clientes = [
            {"dni": "12345678", "idcliente": 10, "idcartera": 126, "cliente": "A",
             "estado_cliente": "R", "gestion_fecha": None, "gestion_hora": None},
            {"dni": "12345678", "idcliente": 11, "idcartera": 128, "cliente": "B",
             "estado_cliente": "A", "gestion_fecha": None, "gestion_hora": None},
        ]
        with patch.object(mowa, "engine_siscob", _Motor(clientes)):
            mowa._enriquecer_clientes([fila], None)
        self.assertIsNone(fila.get("idcliente"))
        self.assertEqual(fila["estado"], "SIN_VINCULAR")

    def test_respuestas_por_campana_se_reutilizan_desde_cache(self):
        with patch.object(mowa, "_get_json", return_value=self.respuestas) as proveedor:
            mowa._respuestas_de_campana("COMPARVIGENTE", "k", self.campana)
            mowa._respuestas_de_campana("COMPARVIGENTE", "k", self.campana)
        self.assertEqual(proveedor.call_count, 1)
        mowa.limpiar_cache_respuestas()
        with patch.object(mowa, "_get_json", return_value=self.respuestas) as proveedor:
            mowa._respuestas_de_campana("COMPARVIGENTE", "k", self.campana)
        self.assertEqual(proveedor.call_count, 1)

    def test_respuesta_con_error_no_queda_en_cache(self):
        with patch.object(mowa, "_get_json", side_effect=mowa.MowaError("HTTP 500", 500)):
            with self.assertRaises(mowa.MowaError):
                mowa._respuestas_de_campana("COMPARVIGENTE", "k", self.campana)
        with patch.object(mowa, "_get_json", return_value=self.respuestas) as proveedor:
            mowa._respuestas_de_campana("COMPARVIGENTE", "k", self.campana)
        self.assertEqual(proveedor.call_count, 1)

    def test_envio_rechaza_cliente_inactivo(self):
        origen = {"id": 501, "dni": "12345678", "cartera_id": 126,
                  "msisdn": "999111222", "send_date": "2026-11-19 10:00:00"}
        cliente = [{"dni": "12345678", "idcliente": 11, "idcartera": 126, "cliente": "A",
                    "estado_cliente": "R", "gestion_fecha": None, "gestion_hora": None}]
        def proveedor(metodo, url, _key, **kwargs):
            if "campaigns/search" in url: return [{"campaign_id": 100, "messages": [origen]}]
            if "/response" in url: return self.respuestas
            raise AssertionError("No debe enviar SMS a un cliente inactivo")
        with patch.object(mowa, "_get_json", side_effect=proveedor), \
             patch.object(mowa, "engine_siscob", _Motor(cliente)), \
             patch.dict(mowa.os.environ, {"MOWA_KEY_COMPARVIGENTE": "dummy"}):
            with self.assertRaises(ValueError) as error:
                mowa.enviar_respuesta("COMPARVIGENTE", 100, 1, 501, date(2026, 11, 19), "Hola", {126})
        self.assertIn("inactivo", str(error.exception))

    def test_error_http_mowa_muestra_codigo_sin_cuerpo(self):
        respuesta = requests.Response()
        respuesta.status_code = 404
        respuesta._content = b"datos privados del proveedor"
        with patch.object(mowa.requests, "request", return_value=respuesta):
            with self.assertRaises(mowa.MowaError) as error:
                mowa._get_json("GET", "https://api.contactahabilidad.com/prueba", "llave")
        self.assertEqual(error.exception.status_code, 404)
        self.assertEqual(str(error.exception), "Mowa devolvió HTTP 404.")


if __name__ == "__main__": unittest.main()
