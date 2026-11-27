"""Límites de la bandeja SMS y asignación, sin conexión a SQL ni a Mowa."""

import asyncio
import unittest
from contextlib import contextmanager
from datetime import date, datetime
from unittest.mock import patch

from fastapi import HTTPException

from app.api import routes_respuestas_mowa as rutas
from app.services import respuestas_mowa_service as mowa
from app.services import asignaciones_cliente_service as asignaciones


SUPERVISOR = {"dni": "sup", "tipo": "SUPERVISOR", "idcartera": 124,
              "permisos_vistas": {"respuestas_mowa": True}}
AGENTE = {"dni": "agente1", "tipo": "GESTOR", "idcartera": 124,
          "permisos_vistas": {"respuestas_mowa": True}}


async def directo(funcion, *args):
    return funcion(*args)


def resolver_sin_event_loop(corutina):
    """Estas rutas y los dobles de SQL completan sin suspenderse."""
    try:
        corutina.send(None)
    except StopIteration as terminado:
        return terminado.value
    raise AssertionError("La ruta se suspendió inesperadamente")


def pendientes():
    return {"completo": True, "clientes": 3, "respuestas": 3, "desde": "2026-11-01",
            "advertencias": [], "sincronizacion": None,
            "grupos": [{"filas": [{"idcartera": 124, "idcliente": n, "estado": "PENDIENTE"}]}
                       for n in (1, 2, 3)]}


class AsignacionesSmsTests(unittest.TestCase):
    def test_control_cuenta_clientes_unicos_y_separa_asignados(self):
        datos = {"desde": "2026-11-01", "completo": True, "advertencias": [],
                 "sincronizacion": {"fin": "2026-11-25T10:00:00"}, "grupos": [
                     {"filas": [
                         {"idcartera": 124, "idcliente": 1, "recibido": "2026-11-18T10:00:00"},
                         {"idcartera": 124, "idcliente": 1, "recibido": "2026-11-18T10:01:00"}]},
                     {"filas": [{"idcartera": 124, "idcliente": 2,
                                  "recibido": "2026-11-25T09:00:00"}]},
                     {"filas": [{"idcartera": 132, "idcliente": 3,
                                  "recibido": "2026-11-20T09:00:00"}]},
                 ]}
        actuales = [{"idcartera": 124, "idcliente": 1, "agente_usuario": "agente1",
                    "agente_nombre": "Agente Uno"}]
        agentes = [{"idcartera": 124, "usuario": "agente1", "nombre": "Agente Uno"}]
        with patch.object(rutas, "ahora_lima", return_value=datetime(2026, 11, 25, 12)):
            resumen = rutas._control_asignaciones(datos, actuales, agentes, 124, None)
            detalle = rutas._control_asignaciones(datos, actuales, agentes, 124, "SIN_ASIGNAR")
        self.assertEqual((resumen["clientes"], resumen["respuestas"], resumen["asignados"],
                          resumen["sin_asignar"], resumen["antiguos"]), (2, 3, 1, 1, 1))
        self.assertEqual(resumen["agentes"][0]["respuestas"], 2)
        self.assertEqual(detalle["clientes_detalle"], 1)
        self.assertEqual(detalle["grupos"][0]["filas"][0]["idcliente"], 2)

    def test_control_respeta_perfil_y_cartera(self):
        with self.assertRaises(HTTPException) as error:
            resolver_sin_event_loop(rutas.control_asignaciones_sms(None, None, AGENTE))
        self.assertEqual(error.exception.status_code, 403)
        with self.assertRaises(HTTPException) as error:
            resolver_sin_event_loop(rutas.control_asignaciones_sms(132, None, SUPERVISOR))
        self.assertEqual(error.exception.status_code, 403)
        with patch.object(rutas, "run_in_threadpool", side_effect=directo), \
             patch.object(rutas.tabla, "sin_atender", return_value=pendientes()) as leer, \
             patch.object(rutas.asignaciones, "listar", return_value=[]), \
             patch.object(rutas.asignaciones, "listar_agentes", return_value=[]):
            resultado = resolver_sin_event_loop(rutas.control_asignaciones_sms(None, "SIN_ASIGNAR", SUPERVISOR))
        self.assertEqual(resultado["clientes_detalle"], 3)
        self.assertEqual(leer.call_args.args[0], {124})

    def test_excel_control_conserva_el_filtro_y_la_cartera(self):
        actuales = [{"idcartera": 124, "idcliente": 1,
                    "agente_usuario": "agente1", "agente_nombre": "Agente Uno"}]
        with patch.object(rutas, "run_in_threadpool", side_effect=directo), \
             patch.object(rutas.tabla, "sin_atender", return_value=pendientes()), \
             patch.object(rutas.asignaciones, "listar", return_value=actuales), \
             patch.object(rutas.asignaciones, "listar_agentes", return_value=[]), \
             patch.object(rutas, "generar_excel_respuestas", return_value=b"PK") as generar:
            archivo = resolver_sin_event_loop(
                rutas.excel_control_asignaciones_sms(124, "SIN_ASIGNAR", SUPERVISOR))
        self.assertEqual(archivo.body, b"PK")
        self.assertEqual(generar.call_args.args[1], {124})
        self.assertEqual(len(generar.call_args.args[0]["conversaciones"]), 2)

    def test_agente_no_consulta_general_ni_asigna(self):
        with self.assertRaises(HTTPException) as error:
            asyncio.run(rutas.respuestas_recibidas(date(2026, 11, 24), date(2026, 11, 25),
                                                    None, AGENTE))
        self.assertEqual(error.exception.status_code, 403)
        with self.assertRaises(HTTPException) as error:
            asyncio.run(rutas.asignar_clientes_sms(rutas.AsignacionLote(
                clientes=[rutas.ClienteAsignable(idcartera=124, idcliente=1)],
                agente_usuario="agente1"), AGENTE))
        self.assertEqual(error.exception.status_code, 403)
        with self.assertRaises(HTTPException) as error:
            asyncio.run(rutas.asignar_cliente_sms(
                rutas.AsignacionCliente(idcartera=124, idcliente=1, agente_usuario="agente1"),
                AGENTE))
        self.assertEqual(error.exception.status_code, 403)

    def test_bandeja_filtra_por_asignacion_del_usuario(self):
        with patch.object(rutas, "run_in_threadpool", side_effect=directo), \
             patch.object(rutas.asignaciones, "listar", return_value=[
                 {"idcartera": 124, "idcliente": 1},
                 {"idcartera": 124, "idcliente": 3}]), \
             patch.object(rutas.tabla, "sin_atender", return_value=pendientes()):
            resultado = asyncio.run(rutas.bandeja_sms(AGENTE))
        self.assertEqual(resultado["clientes"], 2)
        self.assertEqual([g["filas"][0]["idcliente"] for g in resultado["grupos"]], [1, 3])

    def test_supervisor_no_asigna_cartera_ajena_y_revalida_pendiente(self):
        payload = rutas.AsignacionCliente(idcartera=126, idcliente=1, agente_usuario="agente1")
        with self.assertRaises(HTTPException) as error:
            asyncio.run(rutas.asignar_cliente_sms(payload, SUPERVISOR))
        self.assertEqual(error.exception.status_code, 403)
        payload.idcartera = 124
        payload.idcliente = 99
        with patch.object(rutas, "run_in_threadpool", side_effect=directo), \
             patch.object(rutas.tabla, "sin_atender", return_value=pendientes()), \
             patch.object(rutas.asignaciones, "asignar") as guardar:
            with self.assertRaises(HTTPException) as error:
                asyncio.run(rutas.asignar_cliente_sms(payload, SUPERVISOR))
        self.assertEqual(error.exception.status_code, 409)
        guardar.assert_not_called()

    def test_envio_agente_rechaza_asignacion_revocada_antes_de_mowa(self):
        fila = {"idcartera": 124, "idcliente": 1, "dni": "12345678"}
        with patch.object(mowa, "_verificar_ancla", return_value=("key", fila, "999111222")), \
             patch.object(mowa, "_get_json") as proveedor:
            with self.assertRaises(PermissionError):
                mowa.enviar_respuesta("COMPARCARTIGO", 1, 2, 3, date(2026, 11, 24),
                                     "Hola", {124},
                                     lambda _cartera, _cliente: (_ for _ in ()).throw(PermissionError()))
        proveedor.assert_not_called()

    def test_reasignacion_actualiza_responsable_y_registra_evento(self):
        sentencias = []
        class Conn:
            def execute(self, sql, params=None):
                texto = str(sql)
                sentencias.append((texto, params))
                class Resultado:
                    def scalar(self):
                        if "SELECT 1 FROM SISCOB.dbo.Usuario" in texto: return 1
                        if "SELECT @r" in texto: return 0
                        if "SELECT AgenteUsuario" in texto: return "agente_anterior"
                        return None
                return Resultado()
        class Motor:
            @contextmanager
            def begin(self): yield Conn()
        with patch.object(asignaciones, "engine_siscob", Motor()):
            resultado = asignaciones.asignar(asignaciones.TIPO_RESPUESTA_SMS,
                                            124, 42, "agente_nuevo", "supervisor")
        self.assertEqual(resultado["agente_anterior"], "agente_anterior")
        self.assertTrue(resultado["cambio"])
        self.assertTrue(any("UPDATE CobAuto.dbo.CRM_ASIGNACION_CLIENTE" in sql
                            for sql, _ in sentencias))
        self.assertTrue(any("INSERT INTO CobAuto.dbo.CRM_ASIGNACION_CLIENTE_EVENTO" in sql
                            and params["anterior"] == "agente_anterior" for sql, params in sentencias))

    def test_lote_valida_todos_los_pendientes_antes_de_guardar(self):
        payload = rutas.AsignacionLote(clientes=[
            rutas.ClienteAsignable(idcartera=124, idcliente=1),
            rutas.ClienteAsignable(idcartera=124, idcliente=99)], agente_usuario="12345678")
        with patch.object(rutas, "run_in_threadpool", side_effect=directo), \
             patch.object(rutas.tabla, "sin_atender", return_value=pendientes()), \
             patch.object(rutas.asignaciones, "asignar_lote") as guardar:
            with self.assertRaises(HTTPException) as error:
                asyncio.run(rutas.asignar_clientes_sms(payload, SUPERVISOR))
        self.assertEqual(error.exception.status_code, 409)
        guardar.assert_not_called()

    def test_lote_guarda_dos_clientes_en_una_operacion(self):
        payload = rutas.AsignacionLote(clientes=[
            rutas.ClienteAsignable(idcartera=124, idcliente=1),
            rutas.ClienteAsignable(idcartera=124, idcliente=2)], agente_usuario="12345678")
        guardadas = [{"idcartera": 124, "idcliente": n, "agente_usuario": "12345678",
                     "cambio": True} for n in (1, 2)]
        with patch.object(rutas, "run_in_threadpool", side_effect=directo), \
             patch.object(rutas.tabla, "sin_atender", return_value=pendientes()), \
             patch.object(rutas.asignaciones, "asignar_lote", return_value=guardadas) as guardar:
            resultado = asyncio.run(rutas.asignar_clientes_sms(payload, SUPERVISOR))
        self.assertEqual(resultado["total"], 2)
        self.assertEqual(resultado["cambios"], 2)
        self.assertEqual(guardar.call_count, 1)
        self.assertEqual(guardar.call_args.args[1], [(124, 1), (124, 2)])

    def test_lote_no_acepta_cartera_fuera_del_supervisor(self):
        payload = rutas.AsignacionLote(clientes=[
            rutas.ClienteAsignable(idcartera=124, idcliente=1),
            rutas.ClienteAsignable(idcartera=132, idcliente=2)], agente_usuario="12345678")
        with patch.object(rutas.tabla, "sin_atender") as consultar:
            with self.assertRaises(HTTPException) as error:
                asyncio.run(rutas.asignar_clientes_sms(payload, SUPERVISOR))
        self.assertEqual(error.exception.status_code, 403)
        consultar.assert_not_called()

    def test_lote_verifica_cobertura_de_todas_las_carteras_antes_de_escribir(self):
        sentencias = []
        class Conn:
            def execute(self, sql, params=None):
                texto = str(sql)
                sentencias.append(texto)
                class Resultado:
                    def scalar(self):
                        if "SELECT 1 FROM SISCOB.dbo.Usuario" in texto:
                            return 1 if params["cartera"] == 124 else None
                        return None
                return Resultado()
        class Motor:
            @contextmanager
            def begin(self): yield Conn()
        with patch.object(asignaciones, "engine_siscob", Motor()):
            with self.assertRaisesRegex(ValueError, "cartera 132"):
                asignaciones.asignar_lote(asignaciones.TIPO_RESPUESTA_SMS,
                                         [(124, 1), (132, 2)], "12345678", "supervisor")
        self.assertFalse(any("INSERT INTO CobAuto.dbo.CRM_ASIGNACION_CLIENTE" in sql
                             or "UPDATE CobAuto.dbo.CRM_ASIGNACION_CLIENTE" in sql
                             for sql in sentencias))


if __name__ == "__main__":
    unittest.main()
