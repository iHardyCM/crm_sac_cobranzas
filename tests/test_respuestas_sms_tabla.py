"""Vista de respuestas SMS leída desde CRM_SMS_*, sin SQL real."""

import unittest
import asyncio
from contextlib import contextmanager
from datetime import date, datetime
from io import BytesIO
from unittest.mock import patch

from fastapi import HTTPException
from openpyxl import load_workbook

from app.api import routes_respuestas_mowa as rutas
from app.services import respuestas_mowa_service as mowa
from app.services import respuestas_sms_tabla as tabla


def fila_tabla(rid, dni="12345678", cuenta="INTERBANK_BC", recibido=datetime(2026, 11, 19, 10, 0),
               origen="OK", cartera=117):
    return {"Cuenta": cuenta, "CampaignId": 100, "RespuestaId": rid, "MessageId": 500 + rid,
            "Msisdn": "999111222", "Texto": f"Respuesta {rid}", "FechaRecepcion": recibido,
            "RecepcionConHora": 1, "EstadoMowa": 2, "EtiquetaMowa": "ASESORAMIENTO",
            "Dni": dni, "CarteraMowa": cartera, "MensajeTexto": "Aviso",
            "MensajeFechaEnvio": datetime(2026, 11, 19, 9, 0), "OrigenEstado": origen,
            "Descripcion": "Campaña", "FechaCreacion": datetime(2026, 11, 18, 8, 0)}


class _Resultado:
    def __init__(self, filas): self.filas = filas
    def mappings(self): return self.filas


class _Motor:
    def __init__(self, clientes): self.clientes = clientes
    @contextmanager
    def connect(self):
        clientes = self.clientes
        class C:
            def execute(self, _sql, _params): return _Resultado(clientes)
        yield C()


class _MotorSincronizacion:
    def __init__(self, filas): self.filas = iter(filas)
    @contextmanager
    def connect(self):
        filas = self.filas
        class C:
            def execute(self, _sql):
                fila = next(filas)
                class Resultado:
                    def mappings(self): return self
                    def first(self): return fila
                return Resultado()
        yield C()


SYNC = {"fin": "2026-11-20T10:00:00", "resultado": "OK", "desactualizada": False}


class TablaTests(unittest.TestCase):
    def test_estado_carga_distingue_ejecucion_e_interrupcion(self):
        fila = {"IdSincronizacion": 4, "Tipo": "BACKFILL",
                "Inicio": datetime(2026, 11, 24, 10), "Fin": None,
                "Resultado": None, "CampanasNuevas": None, "CampanasRevisadas": None,
                "RespuestasNuevas": None, "OrigenesCompletados": None, "Avisos": None}
        with patch.object(tabla, "ahora_lima", return_value=datetime(2026, 11, 24, 10, 5)):
            estado = tabla.estado_carga(_MotorSincronizacion([fila]))
        self.assertTrue(estado["en_curso"])
        with patch.object(tabla, "ahora_lima", return_value=datetime(2026, 11, 24, 12, 5)):
            estado = tabla.estado_carga(_MotorSincronizacion([fila]))
        self.assertTrue(estado["interrumpida"])

    def test_actualizacion_manual_solo_global_y_sin_duplicados(self):
        supervisor = {"dni": "s", "tipo": "SUPERVISOR", "idcartera": 124,
                      "permisos_vistas": {"respuestas_mowa": True}}
        admin = {"dni": "a", "tipo": "ADMINISTRADOR",
                 "permisos_vistas": {"respuestas_mowa": True}}
        class Tareas:
            def __init__(self): self.tareas = []
            def add_task(self, funcion, *args): self.tareas.append((funcion, args))
        tareas = Tareas()
        with self.assertRaises(HTTPException) as error:
            asyncio.run(rutas.iniciar_actualizacion_sms(rutas.ActualizacionSms(dias=7), tareas, supervisor))
        self.assertEqual(error.exception.status_code, 403)
        with patch.object(rutas.tabla, "estado_carga", return_value={"id": 3, "en_curso": False}), \
             patch.object(rutas, "ahora_lima", return_value=datetime(2026, 11, 24, 16)):
            try:
                respuesta = asyncio.run(rutas.iniciar_actualizacion_sms(
                    rutas.ActualizacionSms(dias=7), tareas, admin))
                self.assertEqual(respuesta["desde"], "2026-11-18")
                self.assertEqual(respuesta["id_anterior"], 3)
                self.assertEqual(len(tareas.tareas), 1)
                with self.assertRaises(HTTPException) as duplicada:
                    asyncio.run(rutas.iniciar_actualizacion_sms(
                        rutas.ActualizacionSms(dias=7), tareas, admin))
                self.assertEqual(duplicada.exception.status_code, 409)
            finally:
                if rutas._carga_manual_local.locked():
                    rutas._carga_manual_local.release()

    def test_ultima_carga_distingue_intento_fallido(self):
        motor = _MotorSincronizacion([
            {"Fin": datetime(2026, 11, 20, 9, 26), "Resultado": "OK"},
            {"Inicio": datetime(2026, 11, 24, 9, 0), "Fin": datetime(2026, 11, 24, 9, 1),
             "Resultado": "ERROR"},
        ])
        with patch.object(tabla, "ahora_lima", return_value=datetime(2026, 11, 24, 10, 0)):
            resultado = tabla.ultima_sincronizacion(motor)
        self.assertEqual(resultado["fin"], "2026-11-20T09:26:00")
        self.assertTrue(resultado["desactualizada"])
        self.assertEqual(resultado["ultimo_intento"]["resultado"], "ERROR")

    def test_fila_desde_tabla_conserva_formato_de_la_vista(self):
        fila = tabla.fila_desde_tabla(fila_tabla(1))
        self.assertEqual((fila["id"], fila["mensaje_id"], fila["campana_creacion"], fila["recibido"]),
                         ("1", "501", "2026-11-18", "2026-11-19T10:00:00"))
        self.assertEqual((fila["dni"], fila["cartera_mowa"], fila["estado"]), ("12345678", 117, "SIN_VINCULAR"))
        pendiente = tabla.fila_desde_tabla(fila_tabla(2, dni=None, origen="PENDIENTE"))
        self.assertIn("aún se están cargando", pendiente["motivo"])
        sin_hora = tabla.fila_desde_tabla({**fila_tabla(3), "RecepcionConHora": 0})
        self.assertEqual(sin_hora["recibido"], "2026-11-19")

    def test_sin_atender_cuenta_clientes_activos_pendientes(self):
        filas = [fila_tabla(1, "11111111"), fila_tabla(2, "11111111", recibido=datetime(2026, 11, 3, 9)),
                 fila_tabla(3, "22222222"), fila_tabla(4, "33333333")]
        clientes = [
            # 1111: pendiente (sin gestión). 2222: atendido. 3333: inactivo (se oculta).
            {"dni": "11111111", "idcliente": 1, "idcartera": 117, "cliente": "A", "estado_cliente": "A",
             "gestion_fecha": None, "gestion_hora": None},
            {"dni": "22222222", "idcliente": 2, "idcartera": 117, "cliente": "B", "estado_cliente": "N",
             "gestion_fecha": datetime(2026, 11, 19), "gestion_hora": "11:00:00", "gestion_id": 9},
            {"dni": "33333333", "idcliente": 3, "idcartera": 117, "cliente": "C", "estado_cliente": "R",
             "gestion_fecha": None, "gestion_hora": None},
        ]
        with patch.object(tabla, "_leer", return_value=filas), \
             patch.object(mowa, "engine_siscob", _Motor(clientes)), \
             patch.object(tabla, "ultima_sincronizacion", return_value=SYNC), \
             patch.object(tabla, "ahora_lima", return_value=datetime(2026, 11, 20, 9, 0)):
            resultado = tabla.sin_atender(None)
        self.assertEqual((resultado["clientes"], resultado["respuestas"], resultado["clientes_ayer_hoy"]), (1, 2, 1))
        self.assertEqual(resultado["por_cartera"], [{"idcartera": 117, "clientes": 1}])
        self.assertEqual([r["id"] for r in resultado["grupos"][0]["filas"]], ["2", "1"])  # más antigua primero

    def test_recibidas_filtra_por_cartera_del_supervisor(self):
        filas = [fila_tabla(1, "11111111", cuenta="COMPARVIGENTE", cartera=126),
                 fila_tabla(2, "22222222", cuenta="COMPARVIGENTE", cartera=128)]
        clientes = [
            {"dni": "11111111", "idcliente": 1, "idcartera": 126, "cliente": "A", "estado_cliente": "A",
             "gestion_fecha": None, "gestion_hora": None},
            {"dni": "22222222", "idcliente": 2, "idcartera": 128, "cliente": "B", "estado_cliente": "A",
             "gestion_fecha": None, "gestion_hora": None},
        ]
        with patch.object(tabla, "_leer", return_value=filas) as leer, \
             patch.object(mowa, "engine_siscob", _Motor(clientes)), \
             patch.object(tabla, "ultima_sincronizacion", return_value=SYNC):
            resultado = tabla.consultar_recibidas(date(2026, 11, 19), date(2026, 11, 20), {126})
        self.assertEqual([r["idcartera"] for r in resultado["data"]], [126])
        self.assertEqual(leer.call_args.args[0], ["COMPARVIGENTE"])  # Solo cuentas visibles.

    def test_cuentas_visibles_por_permiso(self):
        self.assertEqual(tabla._cuentas({124}, None), ["COMPARCARTIGO"])
        self.assertEqual(tabla._cuentas(None, "INTERBANK_BC"), ["INTERBANK_BC"])

    def test_pendientes_acumulados_se_acotan_a_cartera(self):
        filas = [fila_tabla(1, "11111111", cuenta="COMPARVIGENTE", cartera=126),
                 fila_tabla(2, "22222222", cuenta="COMPARVIGENTE", cartera=128)]
        clientes = [
            {"dni": "11111111", "idcliente": 1, "idcartera": 126, "cliente": "A", "estado_cliente": "A",
             "gestion_fecha": None, "gestion_hora": None},
            {"dni": "22222222", "idcliente": 2, "idcartera": 128, "cliente": "B", "estado_cliente": "A",
             "gestion_fecha": None, "gestion_hora": None},
        ]
        with patch.object(tabla, "_leer", return_value=filas), \
             patch.object(mowa, "engine_siscob", _Motor(clientes)), \
             patch.object(tabla, "ultima_sincronizacion", return_value=SYNC):
            resultado = tabla.sin_atender(None, "COMPARVIGENTE", 126)
        self.assertEqual((resultado["clientes"], resultado["respuestas"]), (1, 1))
        self.assertEqual(resultado["grupos"][0]["filas"][0]["idcartera"], 126)


class RutasTablaTests(unittest.TestCase):
    supervisor = {"dni": "s", "tipo": "SUPERVISOR", "idcartera": 124,
                  "permisos_vistas": {"respuestas_mowa": True}}

    def test_excel_sin_atender_rechaza_cuenta_ajena(self):
        with patch.object(rutas.tabla, "sin_atender") as calcular:
            with self.assertRaises(HTTPException) as error:
                rutas.excel_sin_atender(cuenta="INTERBANK_BC", cartera=None, usuario=self.supervisor).send(None)
        self.assertEqual(error.exception.status_code, 403)
        calcular.assert_not_called()

    def test_detalle_sin_atender_rechaza_cartera_ajena(self):
        with patch.object(rutas.tabla, "sin_atender") as calcular:
            with self.assertRaises(HTTPException) as error:
                rutas.detalle_sin_atender(cartera=126, cuenta=None, usuario=self.supervisor).send(None)
        self.assertEqual(error.exception.status_code, 403)
        calcular.assert_not_called()

    def test_excel_sin_atender_genera_hojas(self):
        grupo = {"estado": "PENDIENTE", "filas": [{
            "cuenta": "COMPARCARTIGO", "campana_id": 1, "campana": "C", "id": "1", "mensaje_id": "5",
            "idcartera": 124, "idcliente": 9, "dni": "1", "cliente": "X", "telefono": "999",
            "recibido": "2026-11-19T10:00:00", "texto": "Hola", "estado": "PENDIENTE"}]}
        resultado = {"clientes": 1, "respuestas": 1, "desde": "2026-11-01", "completo": True,
                     "advertencias": [], "grupos": [grupo]}
        import asyncio

        async def correr():
            return await rutas.excel_sin_atender(cuenta=None, cartera=None, usuario=self.supervisor)
        with patch.object(rutas.tabla, "sin_atender", return_value=resultado):
            respuesta = asyncio.run(correr())
        libro = load_workbook(BytesIO(respuesta.body))
        self.assertEqual(libro["Clientes"].max_row, 2)
        metadatos = {a: b for a, b in libro["Consulta"].iter_rows(min_row=2, values_only=True)}
        self.assertEqual(metadatos["Respuestas recibidas desde"], "2026-11-01")
        self.assertRegex(respuesta.headers["content-disposition"],
                         r'filename="SMS_sin_atender_C124_\d{8}_\d{6}\.xlsx"')

    def test_nombre_excel_sms(self):
        ahora = datetime(2026, 11, 20, 10, 5, 12)
        self.assertEqual(rutas.nombre_excel_sms("SMS_sin_atender", [124, 124], False, ahora=ahora),
                         "SMS_sin_atender_C124_20261120_100512.xlsx")
        self.assertEqual(rutas.nombre_excel_sms("Respuestas_SMS", [128, 126, None], True,
                                                "2026-11-19_a_2026-11-20", ahora=ahora),
                         "Respuestas_SMS_C126-128_2026-11-19_a_2026-11-20_20261120_100512_PARCIAL.xlsx")
        self.assertEqual(rutas.nombre_excel_sms("SMS_sin_atender", range(110, 117), False, ahora=ahora),
                         "SMS_sin_atender_Varias_carteras_20261120_100512.xlsx")
        self.assertEqual(rutas.nombre_excel_sms("SMS_sin_atender", [], False, ahora=ahora),
                         "SMS_sin_atender_20261120_100512.xlsx")

    def test_recibidas_rechaza_rango_largo(self):
        admin = {"dni": "a", "tipo": "ADMINISTRADOR", "permisos_vistas": {"respuestas_mowa": True}}
        with self.assertRaises(HTTPException) as error:
            rutas.respuestas_recibidas(desde=date(2026, 10, 1), hasta=date(2026, 11, 19),
                                       cuenta=None, usuario=admin).send(None)
        self.assertEqual(error.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()
