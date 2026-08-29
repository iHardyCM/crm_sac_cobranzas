import unittest
import json

from app.services.pautas_evaluacion_service import (
    TIPO_ANULANTE_BLOQUE,
    TIPO_PUNTUABLE,
    aplicar_anulantes_bloque,
    plantilla_general_evaluacion,
    validar_pauta,
)


def criterio(codigo, peso, tipo=TIPO_PUNTUABLE, estado="CUMPLE"):
    return {
        "codigo_criterio": codigo,
        "nombre": codigo,
        "tipo_criterio": tipo,
        "peso": peso,
        "regla_evaluacion": "Regla verificable.",
        "fuente_evidencia": "TRANSCRIPCION",
        "activo": True,
        "estado": estado,
        "puntaje_obtenido": peso,
        "nota": peso,
    }


class PautasEvaluacionTests(unittest.TestCase):
    def test_plantilla_mibanco_es_un_borrador_publicable_en_peso(self):
        plantilla = plantilla_general_evaluacion()
        plantilla["aplica_todas"] = True

        validacion = validar_pauta(plantilla, requiere_total=True)

        self.assertTrue(validacion["valida"], validacion["errores"])
        self.assertEqual(validacion["peso_total"], 100.0)
        self.assertEqual(plantilla["estado"], "BORRADOR")

    def test_plantilla_mibanco_incluye_reglas_de_cumplimiento_e_incumplimiento(self):
        plantilla = plantilla_general_evaluacion()
        criterios = [
            criterio
            for bloque in plantilla["bloques"]
            for criterio in bloque["criterios"]
        ]

        self.assertTrue(criterios)
        self.assertTrue(all(item["regla_cumple"].strip() for item in criterios))
        self.assertTrue(all(item["regla_no_cumple"].strip() for item in criterios))
        self.assertNotIn("mibanco", json.dumps(plantilla, ensure_ascii=False).lower())

    def test_no_permte_publicar_si_los_puntos_no_suman_cien(self):
        pauta = {
            "nombre": "Pauta incompleta",
            "aplica_todas": True,
            "bloques": [{
                "codigo": "B1", "nombre": "Bloque 1", "criterios": [criterio("B1.1", 99)],
            }],
        }

        validacion = validar_pauta(pauta, requiere_total=True)

        self.assertFalse(validacion["valida"])
        self.assertIn("suman 99.00", " ".join(validacion["errores"]))

    def test_anulante_confirmado_anula_solo_su_bloque(self):
        criterios = [
            {**criterio("B1.1", 50), "bloque": "B1"},
            {**criterio("B1.A", 0, TIPO_ANULANTE_BLOQUE, "NO_CUMPLE"), "bloque": "B1"},
            {**criterio("B2.1", 50), "bloque": "B2"},
        ]

        resultado = aplicar_anulantes_bloque(criterios)

        self.assertTrue(resultado[0]["bloque_anulado"])
        self.assertEqual(resultado[0]["puntaje_obtenido"], 0.0)
        self.assertEqual(resultado[1]["estado"], "NO_CUMPLE")
        self.assertNotIn("bloque_anulado", resultado[2])
        self.assertEqual(resultado[2]["puntaje_obtenido"], 50)


if __name__ == "__main__":
    unittest.main()
