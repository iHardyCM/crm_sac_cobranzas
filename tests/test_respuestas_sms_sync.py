"""Lógica de la carga programada de respuestas SMS, sin red ni SQL real."""

import unittest
from datetime import date, datetime, timedelta
from unittest.mock import patch

from app.services import respuestas_mowa_service as mowa
from app.services import respuestas_sms_sync as sync


AHORA = datetime(2026, 11, 20, 10, 0, 0)


class TramosTests(unittest.TestCase):
    def test_intervalos_por_antiguedad(self):
        hoy = AHORA.date()
        casos = [(0, timedelta(minutes=10)), (2, timedelta(minutes=10)), (3, timedelta(minutes=30)),
                 (7, timedelta(minutes=30)), (8, timedelta(hours=3)), (30, timedelta(hours=3)),
                 (31, timedelta(hours=24)), (60, timedelta(hours=24)), (61, None)]
        for dias, esperado in casos:
            self.assertEqual(sync.intervalo_revision(hoy - timedelta(days=dias), hoy), esperado, dias)

    def test_dias_a_descubrir(self):
        self.assertEqual(sync.dias_a_descubrir("PROGRAMADA", AHORA), [date(2026, 11, 20)])
        temprano = AHORA.replace(hour=7, minute=10)
        self.assertEqual(sync.dias_a_descubrir("PROGRAMADA", temprano),
                         [date(2026, 11, 19), date(2026, 11, 20)])
        backfill = sync.dias_a_descubrir("BACKFILL", AHORA)
        self.assertEqual((backfill[0], backfill[-1], len(backfill)),
                         (date(2026, 9, 21), date(2026, 11, 20), 61))
        self.assertEqual(sync.dias_a_descubrir("MANUAL", AHORA, date(2026, 11, 18)),
                         [date(2026, 11, 18), date(2026, 11, 19), date(2026, 11, 20)])

    def test_campana_nueva_se_revisa_en_la_misma_corrida(self):
        fila = sync.datos_campana("INTERBANK_BC", {"campaign_id": "77", "creation_date": "2026-11-20 08:00:00",
                                                   "messages": [{}, {}]}, AHORA.date(), AHORA)
        self.assertEqual((fila["cid"], fila["proxima"], fila["total_mensajes"]), (77, AHORA, 2))
        vieja = sync.datos_campana("INTERBANK_BC", {"campaign_id": 78, "creation_date": "2026-09-01 08:00:00"},
                                   date(2026, 9, 1), AHORA)
        self.assertIsNone(vieja["proxima"])


class RespuestasTests(unittest.TestCase):
    def test_corte_de_fecha_y_campos(self):
        data = {"total_incoming": 3, "responses": [
            {"id": 1, "message_id": 10, "msisdn": "999111222", "text": "Ya pagué",
             "received_date": "2026-11-19 10:15:00", "status": 2, "label_status": "ASESORAMIENTO"},
            {"id": 2, "message_id": 11, "received_date": "2026-10-31 23:59:00", "text": "Antes del corte"},
            {"id": 3, "message_id": 12, "received_date": "2026-11-02", "text": "Sin hora"},
            {"id": None, "message_id": 13, "received_date": "2026-11-19 10:15:00"},
        ]}
        filas = sync.filas_respuesta("INTERBANK_BC", 100, data, date(2026, 10, 30))
        self.assertEqual([f["rid"] for f in filas], [1, 3])
        self.assertEqual((filas[0]["con_hora"], filas[1]["con_hora"]), (1, 0))
        self.assertEqual(filas[0]["recibido"], datetime(2026, 11, 19, 10, 15))
        self.assertEqual(sync.total_respuestas(data), 3)

    def test_formato_inesperado_es_error_de_mowa(self):
        with self.assertRaises(mowa.MowaError):
            sync.filas_respuesta("INTERBANK_BC", 100, {"responses": None}, AHORA.date())

    def test_origen_desde_busqueda(self):
        campana = {"campaign_id": 100, "send_date": "2026-11-19 09:00:00", "messages": [
            {"id": 10, "dni": "12345678", "cartera_id": 117, "text": "Aviso", "send_date": "2026-11-19 09:01:00"},
            {"id": 11, "dni": "0", "cartera": 0, "text": "Sin DNI"},
        ]}
        origen = sync.origen_por_mensaje(campana)
        self.assertEqual(origen[10], {"dni": "12345678", "cartera": 117, "texto": "Aviso",
                                      "envio": datetime(2026, 11, 19, 9, 1)})
        self.assertEqual((origen[11]["dni"], origen[11]["cartera"]), (None, None))

    def test_busqueda_por_id_filtra_aunque_mowa_ignore_el_filtro(self):
        llamadas = []
        def proveedor(metodo, url, key, **kw):
            llamadas.append(kw["json"])
            if kw["json"]["fromDate"] == "2026-11-18":
                return [{"campaign_id": 5}, {"campaign_id": 100, "messages": []}]
            return [{"campaign_id": 5}]
        with patch.object(mowa, "_get_json", side_effect=proveedor):
            encontrada = sync._buscar_campana_por_id("INTERBANK_BC", "k", 100,
                                                     (date(2026, 11, 17), date(2026, 11, 18)))
        self.assertEqual(encontrada["campaign_id"], 100)
        self.assertEqual([l["campaignId"] for l in llamadas], [100, 100])


class RepoFalso:
    """Repositorio en memoria para probar la orquestación."""
    def __init__(self):
        self.campanas, self.respuestas, self.registros = {}, {}, []
    def adquirir_candado(self): return True
    def liberar_candado(self): pass
    def iniciar_registro(self, tipo, inicio): self.registros.append(tipo); return 1
    def cerrar_registro(self, *a): pass
    def campanas_existentes(self, cuenta, ids): return {c for (cu, c) in self.campanas if cu == cuenta}
    def insertar_campanas(self, filas):
        for f in filas: self.campanas[(f["cuenta"], f["cid"])] = dict(f, total=0)
    def retirar_campanas_antiguas(self, hoy): pass
    def campanas_a_revisar(self, ahora, limite, forzar=False):
        return [{"cuenta": cu, "cid": c, "fecha_base": (f["creacion"] or ahora).date(), "total": f["total"]}
                for (cu, c), f in self.campanas.items() if f["proxima"] and (forzar or f["proxima"] <= ahora)]
    def respuestas_existentes(self, cuenta, cid):
        return {r for (cu, c, r) in self.respuestas if (cu, c) == (cuenta, cid)}
    def guardar_revision(self, cuenta, cid, nuevas, total, ahora, proxima):
        for f in nuevas: self.respuestas[(cuenta, cid, f["rid"])] = dict(f, origen="PENDIENTE")
        self.campanas[(cuenta, cid)].update(total=total, proxima=proxima)
    def reprogramar(self, cuenta, cid, proxima): self.campanas[(cuenta, cid)]["proxima"] = proxima
    def campanas_con_origen_pendiente(self, limite):
        claves = {(cu, c) for (cu, c, _), f in self.respuestas.items() if f["origen"] == "PENDIENTE"}
        return [{"cuenta": cu, "cid": c, "creacion": self.campanas[(cu, c)]["creacion"].date(), "envio": None}
                for cu, c in claves]
    def completar_origen(self, cuenta, cid, origen):
        n = 0
        for (cu, c, r), f in self.respuestas.items():
            if (cu, c) == (cuenta, cid) and origen and f["mid"] in origen:
                f.update(origen="OK", **origen[f["mid"]]); n += 1
        return n


class OrquestacionTests(unittest.TestCase):
    def test_actualizacion_manual_revisa_aunque_aun_no_venza(self):
        repo = RepoFalso()
        repo.insertar_campanas([{"cuenta": "INTERBANK_BC", "cid": 1,
                                 "creacion": AHORA, "proxima": AHORA + timedelta(hours=1)}])
        with patch.object(sync, "Repositorio", return_value=repo), \
             patch.object(mowa, "_get_json", return_value={"responses": []}), \
             patch.object(sync, "_llaves", return_value={"INTERBANK_BC": "k"}), \
             patch.object(sync, "_descubrir"), patch.object(sync, "_completar_origenes"), \
             patch.object(mowa, "_cuentas_visibles", return_value=[("INTERBANK_BC", (117,), "k")]):
            resultado = sync.ejecutar(None, "MANUAL", desde=AHORA.date(), ahora=AHORA)
        self.assertEqual(resultado.campanas_revisadas, 1)

    def test_corrida_descubre_revisa_y_completa_origen(self):
        campana = {"campaign_id": 100, "creation_date": "2026-11-20 08:00:00", "messages": [
            {"id": 10, "dni": "12345678", "cartera_id": 117, "text": "Aviso"}]}
        def proveedor(metodo, url, key, **kw):
            if url.endswith("/response"):
                return {"total_incoming": 1, "responses": [
                    {"id": 1, "message_id": 10, "received_date": "2026-11-20 09:00:00", "text": "Ok"}]}
            if "campaigns/search" in url:
                return [campana]
            raise AssertionError(url)
        repo = RepoFalso()
        with patch.object(sync, "Repositorio", return_value=repo), \
             patch.object(mowa, "_get_json", side_effect=proveedor), \
             patch.object(sync, "_llaves", return_value={"INTERBANK_BC": "k"}), \
             patch.object(mowa, "_cuentas_visibles", return_value=[("INTERBANK_BC", (117,), "k")]):
            primera = sync.ejecutar(None, "PROGRAMADA", ahora=AHORA)
            proxima_tras_primera = repo.campanas[("INTERBANK_BC", 100)]["proxima"]
            segunda = sync.ejecutar(None, "PROGRAMADA", ahora=AHORA + timedelta(minutes=10))
        self.assertEqual((primera.campanas_nuevas, primera.respuestas_nuevas, primera.origenes_completados),
                         (1, 1, 1))
        self.assertEqual(repo.respuestas[("INTERBANK_BC", 100, 1)]["dni"], "12345678")
        self.assertEqual(proxima_tras_primera, AHORA + timedelta(minutes=10))
        # La segunda corrida revisa de nuevo (tramo de 10 minutos) pero no duplica nada.
        self.assertEqual((segunda.campanas_nuevas, segunda.campanas_revisadas, segunda.respuestas_nuevas),
                         (0, 1, 0))

    def test_error_de_mowa_reprograma_y_no_detiene_la_corrida(self):
        repo = RepoFalso()
        repo.insertar_campanas([{"cuenta": "INTERBANK_BC", "cid": 1, "creacion": AHORA - timedelta(days=20),
                                 "proxima": AHORA}])
        def proveedor(metodo, url, key, **kw):
            if url.endswith("/response"):
                raise mowa.MowaError("Mowa devolvió HTTP 500.", 500)
            return []
        with patch.object(sync, "Repositorio", return_value=repo), \
             patch.object(mowa, "_get_json", side_effect=proveedor), \
             patch.object(sync, "_llaves", return_value={"INTERBANK_BC": "k"}), \
             patch.object(mowa, "_cuentas_visibles", return_value=[("INTERBANK_BC", (117,), "k")]):
            resumen = sync.ejecutar(None, "PROGRAMADA", ahora=AHORA)
        self.assertEqual(resumen.resultado, "CON_AVISOS")
        self.assertEqual(repo.campanas[("INTERBANK_BC", 1)]["proxima"], AHORA + timedelta(minutes=10))

    def test_otra_corrida_en_curso_se_omite(self):
        repo = RepoFalso()
        repo.adquirir_candado = lambda: False
        with patch.object(sync, "Repositorio", return_value=repo):
            self.assertTrue(sync.ejecutar(None, "PROGRAMADA", ahora=AHORA).omitida)
        self.assertEqual(repo.registros, [])


if __name__ == "__main__":
    unittest.main()
