"""Pauta v3 (calibración de Calidad, 28/10/2026).

Cubre lo que cambia con la v3 y, sobre todo, que las evaluaciones hechas con
pautas anteriores (sin admite_parcial) se sigan resolviendo igual al releerse.
"""
import unittest

from app.services.ia_analysis_service import (
    aplicar_guardas_deterministicas_criterios,
    normalizar_estado_mibanco_pipeline_v3,
    puntaje_mibanco_pipeline_v3,
)
from app.services.pautas_evaluacion_service import (
    TIPO_ANULANTE_BLOQUE,
    TIPO_PUNTUABLE,
    bloques_anulados,
    puntaje_por_estado,
    validar_pauta,
)

CARTERA = "COMPARTAMOS CASTIGO INDIVIDUAL"

# Pesos v3 tal como los carga seed_pauta_general_v3.sql.
PAUTA_V3 = [
    ("PECUF", "PECUF.1", 20, TIPO_PUNTUABLE, False),
    ("PECUF", "PECUF.2", 7, TIPO_PUNTUABLE, False),
    ("PECUF", "PECUF.3", 9, TIPO_PUNTUABLE, True),
    ("PECUF", "PECUF.4", 7, TIPO_PUNTUABLE, False),
    ("PECN", "PECN.1", 6, TIPO_PUNTUABLE, True),
    ("PECN", "PECN.2", 6, TIPO_PUNTUABLE, True),
    ("PECN", "PECN.3", 6, TIPO_PUNTUABLE, True),
    ("PECN", "PECN.4", 4, TIPO_PUNTUABLE, True),
    ("PECC", "PECC.1", 0, TIPO_ANULANTE_BLOQUE, False),
    ("PECC", "PECC.2", 6, TIPO_PUNTUABLE, False),
    ("PECC", "PECC.3", 4, TIPO_PUNTUABLE, False),
    ("PECC", "PECC.4", 5, TIPO_PUNTUABLE, False),
    ("PENC", "PENC.1", 2, TIPO_PUNTUABLE, False),
    ("PENC", "PENC.2", 4, TIPO_PUNTUABLE, False),
    ("PENC", "PENC.3", 4, TIPO_PUNTUABLE, False),
    ("PENC", "PENC.4", 2, TIPO_PUNTUABLE, False),
    ("PENC", "PENC.5", 8, TIPO_PUNTUABLE, True),
]


def seg(i, rol, texto):
    return {"segmento_id": i, "hablante": rol, "rol": rol, "texto": texto, "inicio_segundos": i * 4}


def criterio(codigo, peso, bloque, tipo=TIPO_PUNTUABLE, admite=False, estado="REQUIERE_REVISION"):
    item = {
        "codigo": codigo,
        "codigo_criterio": codigo,
        "bloque": bloque,
        "peso": float(peso),
        "tipo_criterio": tipo,
        "estado": estado,
        "fuente_evidencia": "TRANSCRIPCION",
        "puntaje_obtenido": puntaje_por_estado(estado, peso),
        "nota": puntaje_por_estado(estado, peso),
    }
    if admite:
        item["admite_parcial"] = True
        item["regla_parcial"] = "Regla parcial de prueba."
    return item


def pauta_v3(estado="CUMPLE"):
    return [criterio(c, p, b, t, a, estado) for b, c, p, t, a in PAUTA_V3]


def pauta_v2(estado="CUMPLE"):
    """Mismos códigos, sin admite_parcial: así llegan las evaluaciones viejas."""
    return [criterio(c, p, b, TIPO_PUNTUABLE, False, estado) for b, c, p, t, a in PAUTA_V3 if c not in {"PECC.4", "PENC.5"}]


def por_codigo(criterios):
    return {item["codigo"]: item for item in criterios}


def llamada(*turnos):
    return [seg(i, rol, texto) for i, (rol, texto) in enumerate(turnos, start=1)]


APERTURA_COMPLETA = [
    ("AGENTE", "Buenos días, le saluda Ana Pérez en representación de Compartamos Banco."),
    ("CLIENTE", "Sí, buenos días."),
    ("AGENTE", "¿Me podría comunicar con la señora Rosa Quispe, por favor?"),
    ("CLIENTE", "Sí, soy yo."),
]


class PautaV3ValidacionTests(unittest.TestCase):
    def _payload(self, **cambios):
        bloques = {}
        for b, c, p, t, a in PAUTA_V3:
            bloques.setdefault(b, {"codigo": b, "nombre": b, "criterios": []})["criterios"].append({
                "codigo_criterio": c, "nombre": c, "tipo_criterio": t, "peso": p,
                "regla_evaluacion": "Regla verificable.", "fuente_evidencia": "TRANSCRIPCION",
                "admite_parcial": a, "regla_parcial": "Condición parcial." if a else "",
                **cambios.get(c, {}),
            })
        return {"nombre": "Pauta general de evaluacion", "aplica_todas": True, "bloques": list(bloques.values())}

    def test_v3_suma_100_y_es_publicable(self):
        validacion = validar_pauta(self._payload(), requiere_total=True)
        self.assertTrue(validacion["valida"], validacion["errores"])
        self.assertEqual(validacion["peso_total"], 100.0)

    def test_parcial_sin_regla_no_se_puede_guardar(self):
        validacion = validar_pauta(self._payload(**{"PECN.1": {"regla_parcial": ""}}))
        self.assertFalse(validacion["valida"])
        self.assertTrue(any("PECN.1" in error and "parcial" in error for error in validacion["errores"]))

    def test_anulante_nunca_admite_parcial(self):
        validacion = validar_pauta(self._payload(**{"PECC.1": {"admite_parcial": True}}))
        pecc1 = next(c for b in validacion["pauta"]["bloques"] for c in b["criterios"] if c["codigo_criterio"] == "PECC.1")
        self.assertFalse(pecc1["admite_parcial"])


class PuntajeParcialTests(unittest.TestCase):
    def test_parcial_vale_la_mitad(self):
        self.assertEqual(puntaje_por_estado("PARCIAL_MEDIO", 9), 4.5)
        self.assertEqual(puntaje_mibanco_pipeline_v3("PARCIAL_MEDIO", 6), 3.0)
        self.assertEqual(puntaje_por_estado("NO_CUMPLE", 9), 0.0)
        self.assertEqual(puntaje_por_estado("CUMPLE", 9), 9.0)

    def test_parcial_del_modelo_solo_se_acepta_si_el_criterio_lo_admite(self):
        self.assertEqual(normalizar_estado_mibanco_pipeline_v3("PARCIAL", admite_parcial=True), "PARCIAL_MEDIO")
        self.assertEqual(normalizar_estado_mibanco_pipeline_v3("PARCIAL_ALTO", admite_parcial=True), "PARCIAL_MEDIO")
        self.assertEqual(normalizar_estado_mibanco_pipeline_v3("PARCIAL_MEDIO", admite_parcial=False), "REQUIERE_REVISION")

    def test_bloques_anulados_sobre_filas_de_tabla(self):
        filas = [
            {"codigo_bloque": "PECC", "tipo_criterio": "ANULANTE_BLOQUE", "resultado_ia": "NO_CUMPLE"},
            {"codigo_bloque": "PECC", "tipo_criterio": "PUNTUABLE", "resultado_ia": "CUMPLE"},
            {"codigo_bloque": "PECN", "tipo_criterio": "PUNTUABLE", "resultado_ia": "CUMPLE"},
        ]
        anulados = bloques_anulados(filas, estado_de=lambda f: f["resultado_ia"], bloque_de=lambda f: f["codigo_bloque"])
        self.assertEqual(anulados, {"PECC"})


class GuardasV3Tests(unittest.TestCase):
    def evaluar(self, segmentos, criterios):
        return por_codigo(aplicar_guardas_deterministicas_criterios(segmentos, criterios, CARTERA))

    # --- PECN.3 -------------------------------------------------------------
    def test_pecn3_sin_objecion_es_no_aplica_en_v3(self):
        segmentos = llamada(*APERTURA_COMPLETA,
                            ("AGENTE", "Su deuda total es de 1500 soles, ¿puede pagar el viernes?"),
                            ("CLIENTE", "Sí, el viernes pago."),
                            ("AGENTE", "Perfecto, gracias, que tenga buen día."))
        v3 = self.evaluar(segmentos, pauta_v3())
        self.assertEqual(v3["PECN.3"]["estado"], "NO_APLICA")

    def test_pecn3_sin_objecion_conserva_regla_anterior_en_v2(self):
        segmentos = llamada(*APERTURA_COMPLETA,
                            ("AGENTE", "Su deuda total es de 1500 soles, ¿puede pagar el viernes?"),
                            ("CLIENTE", "Sí, el viernes pago."),
                            ("AGENTE", "Perfecto, gracias, que tenga buen día."))
        v2 = self.evaluar(segmentos, pauta_v2())
        self.assertIn(v2["PECN.3"]["estado"], {"CUMPLE", "NO_CUMPLE"})

    # --- PECUF.3 ------------------------------------------------------------
    def _escalera_saltada(self):
        return llamada(*APERTURA_COMPLETA,
                       ("AGENTE", "Su deuda total es de 2690 soles."),
                       ("CLIENTE", "No puedo, es mucho."),
                       ("AGENTE", "Le ofrecemos un descuento de campaña, quedaría en 900 soles."),
                       ("CLIENTE", "Lo voy a pensar."),
                       ("AGENTE", "Gracias, que tenga buen día."))

    def test_pecuf3_salto_de_nivel_es_parcial_en_v3(self):
        v3 = self.evaluar(self._escalera_saltada(), pauta_v3())
        self.assertEqual(v3["PECUF.3"]["estado"], "PARCIAL_MEDIO")
        self.assertEqual(v3["PECUF.3"]["nota"], 4.5)

    def test_pecuf3_salto_de_nivel_sigue_siendo_no_cumple_en_v2(self):
        v2 = self.evaluar(self._escalera_saltada(), pauta_v2())
        self.assertEqual(v2["PECUF.3"]["estado"], "NO_CUMPLE")

    def test_pecuf3_sin_deuda_total_sigue_siendo_no_cumple_en_v3(self):
        segmentos = llamada(*APERTURA_COMPLETA,
                            ("AGENTE", "Tenemos un descuento de campaña de 900 soles."),
                            ("CLIENTE", "Ya, gracias."))
        v3 = self.evaluar(segmentos, pauta_v3())
        self.assertEqual(v3["PECUF.3"]["estado"], "NO_CUMPLE")

    # --- PECN.1 -------------------------------------------------------------
    def test_pecn1_solo_causa_es_parcial_en_v3_y_no_cumple_en_v2(self):
        segmentos = llamada(*APERTURA_COMPLETA,
                            ("AGENTE", "¿A qué se debe el atraso?"),
                            ("CLIENTE", "Me quedé sin trabajo desde que cerró la empresa."),
                            ("AGENTE", "Entiendo. Gracias por contarme."))
        self.assertEqual(self.evaluar(segmentos, pauta_v3())["PECN.1"]["estado"], "PARCIAL_MEDIO")
        self.assertEqual(self.evaluar(segmentos, pauta_v2())["PECN.1"]["estado"], "NO_CUMPLE")

    # --- PECN.4 -------------------------------------------------------------
    def test_pecn4_intento_de_cierre_sin_compromiso_es_parcial_en_v3(self):
        segmentos = llamada(*APERTURA_COMPLETA,
                            ("AGENTE", "Su deuda total es de 1500 soles. ¿Para qué fecha podría realizar el pago?"),
                            ("CLIENTE", "No sé todavía, lo tengo que ver."),
                            ("AGENTE", "Gracias, que tenga buen día."))
        self.assertEqual(self.evaluar(segmentos, pauta_v3())["PECN.4"]["estado"], "PARCIAL_MEDIO")
        self.assertEqual(self.evaluar(segmentos, pauta_v2())["PECN.4"]["estado"], "NO_CUMPLE")

    # --- PECC.1 anulante ----------------------------------------------------
    def test_sin_identificacion_anula_el_bloque_pecc(self):
        segmentos = llamada(("AGENTE", "Buenos días."),
                            ("CLIENTE", "Buenos días."),
                            ("AGENTE", "¿Me podría comunicar con la señora Rosa Quispe, por favor?"),
                            ("CLIENTE", "Sí, soy yo."),
                            ("AGENTE", "Su deuda total es de 1500 soles, ¿puede pagar el viernes?"),
                            ("CLIENTE", "Sí, el viernes pago 1500 soles."),
                            ("AGENTE", "Confirmamos entonces el pago de 1500 soles el viernes por agente. Gracias, buen día."))
        criterios = pauta_v3()
        resultado = self.evaluar(segmentos, criterios)
        self.assertEqual(resultado["PECC.1"]["estado"], "NO_CUMPLE")
        for codigo in ("PECC.2", "PECC.3", "PECC.4"):
            self.assertTrue(resultado[codigo]["bloque_anulado"], codigo)
            self.assertEqual(resultado[codigo]["nota"], 0.0, codigo)
        # El saludo no se castiga dos veces: en v3 PENC.1 es solo saludo.
        self.assertEqual(resultado["PENC.1"]["estado"], "CUMPLE")
        # Otros bloques no se tocan.
        self.assertFalse(resultado["PECUF.1"].get("bloque_anulado"))

    def test_identificacion_completa_cumple_y_el_bloque_se_recupera(self):
        segmentos = llamada(*APERTURA_COMPLETA,
                            ("AGENTE", "Su deuda total es de 1500 soles."),
                            ("CLIENTE", "Ya."))
        criterios = pauta_v3()
        # Simula una relectura de una ficha que había quedado anulada.
        for item in criterios:
            if item["bloque"] == "PECC":
                item["bloque_anulado"] = True
                item["nota"] = 0.0
        resultado = self.evaluar(segmentos, criterios)
        self.assertEqual(resultado["PECC.1"]["estado"], "CUMPLE")
        self.assertFalse(resultado["PECC.2"]["bloque_anulado"])

    def test_solo_nombre_sin_entidad_va_a_revision_y_no_anula(self):
        segmentos = llamada(("AGENTE", "Buenos días, le saluda Ana Pérez."),
                            ("CLIENTE", "Buenos días."),
                            ("AGENTE", "¿Me podría comunicar con la señora Rosa Quispe, por favor?"),
                            ("CLIENTE", "Sí, soy yo."))
        resultado = self.evaluar(segmentos, pauta_v3())
        self.assertEqual(resultado["PECC.1"]["estado"], "REQUIERE_REVISION")
        self.assertFalse(resultado["PECC.2"].get("bloque_anulado"))

    def test_pecc1_en_v2_sigue_siendo_respeto_por_la_entidad(self):
        segmentos = llamada(("AGENTE", "Buenos días."), ("CLIENTE", "Buenos días."),
                            ("AGENTE", "Le llamo por su deuda."), ("CLIENTE", "Ya."))
        resultado = self.evaluar(segmentos, pauta_v2())
        self.assertEqual(resultado["PECC.1"]["estado"], "CUMPLE")
        self.assertFalse(resultado["PECC.2"].get("bloque_anulado"))

    # --- PECC.4 -------------------------------------------------------------
    def test_pecc4_titularidad_antes_del_monto_cumple(self):
        segmentos = llamada(*APERTURA_COMPLETA,
                            ("AGENTE", "Su deuda total es de 1500 soles."),
                            ("CLIENTE", "Ya."))
        self.assertEqual(self.evaluar(segmentos, pauta_v3())["PECC.4"]["estado"], "CUMPLE")

    def test_pecc4_sin_montos_no_aplica(self):
        segmentos = llamada(*APERTURA_COMPLETA,
                            ("AGENTE", "Le llamaba para coordinar, ¿lo puedo llamar mañana?"),
                            ("CLIENTE", "Sí, mañana."))
        self.assertEqual(self.evaluar(segmentos, pauta_v3())["PECC.4"]["estado"], "NO_APLICA")


if __name__ == "__main__":
    unittest.main()
