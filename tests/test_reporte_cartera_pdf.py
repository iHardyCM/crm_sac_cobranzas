"""Pruebas del modelo y la exportacion del informe ejecutivo por cartera."""

import unittest
from datetime import date

from app.services.reporte_cartera_pdf import _model, _month_week, construir_informe_cartera_pdf


class InformeCarteraPdfTest(unittest.TestCase):
    def test_semanas_de_octubre_domingo_a_sabado(self):
        payload = {"evaluaciones": [
            {"agente": "Agente A", "fecha": "2026-10-02", "nota": 50},
            {"agente": "Agente A", "fecha": "2026-10-03", "nota": 70},
            {"agente": "Agente A", "fecha": "2026-10-04", "nota": 80},
            {"agente": "Agente A", "fecha": "2026-10-07", "nota": 90},
        ]}
        model = _model(payload)
        self.assertEqual([(week["label"], week["date_label"], week["average"])
                          for week in model["weeks"]], [
            ("Sem. 1", "01/10-03/10", 60),
            ("Sem. 2", "04/10-10/10", 85),
        ])
        self.assertEqual(model["agents"][0]["trend"], 25)
        self.assertEqual(_month_week(date(2026, 10, 31))[0], (2026, 10, 5))
        self.assertEqual(_month_week(date(2026, 11, 1))[0], (2026, 11, 1))
        self.assertEqual(_month_week(date(2026, 11, 7))[0], (2026, 11, 1))
        self.assertEqual(_month_week(date(2026, 11, 8))[0], (2026, 11, 2))
        self.assertEqual(_month_week(date(2026, 8, 30))[0], (2026, 8, 6))

    def test_metrica_y_tendencia_usan_solo_datos_medidos(self):
        payload = {
            "meta": 80,
            "evaluaciones": [
                {"cartera": "Cartera A", "agente": "Agente A", "fecha": "2026-10-01", "nota": 60,
                 "error_critico": "Sí"},
                {"cartera": "Cartera A", "agente": "Agente A", "fecha": "2026-10-08", "nota": 70,
                 "error_critico": "No"},
                {"cartera": "Cartera A", "agente": "Agente A", "fecha": "2026-10-15", "nota": 65,
                 "error_critico": "No"},
            ],
            "criterios": [
                {"criterio": "Criterio original", "medido": 1, "brecha": 1},
                {"criterio": "Criterio original", "medido": 0, "brecha": 1},
            ],
        }
        model = _model(payload)
        self.assertEqual(model["portfolio"], "Cartera A")
        self.assertEqual(model["critical"], 1)
        self.assertEqual(model["coverage"], 50)
        self.assertEqual(model["ranking"][0]["name"], "Criterio original")
        self.assertEqual(model["ranking"][0]["breaches"], 1)
        self.assertEqual(model["agents"][0]["trend"], -5)

    def test_textos_largos_y_varios_agentes_no_impiden_exportar(self):
        criterion = "Informacion completa de alternativas de pago y acuerdos disponibles para el titular"
        payload = {
            "periodo": "01/10/2026 - 31/10/2026",
            "meta": 85,
            "evaluaciones": [
                {"cartera": "Cartera A", "agente": f"{index:08d} - AGENTE CON NOMBRE Y APELLIDOS EXTENSOS",
                 "fecha": f"2026-10-{index % 28 + 1:02d}", "nota": 60 + index,
                 "error_critico": "No"}
                for index in range(25)
            ],
            "criterios": [{"criterio": criterion, "medido": 1, "brecha": 1} for _ in range(25)],
            "recomendacion": (
                "Priorizar la revision del criterio con mayor incidencia, documentar las causas "
                "observadas, acordar acciones de entrenamiento y verificar la evolucion semanal."
            ),
        }
        result = construir_informe_cartera_pdf(payload)
        self.assertTrue(result.startswith(b"%PDF-"))
        self.assertGreater(len(result), 10000)


if __name__ == "__main__":
    unittest.main()
