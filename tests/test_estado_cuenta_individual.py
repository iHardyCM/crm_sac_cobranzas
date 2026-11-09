"""Estado de cuenta individual / CCM (docs/estado_cuenta_individual_compartamos.md).

Solo prueba las reglas de armado; no consulta la base de datos.
"""
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services import cliente_crm_service as crm  # noqa: E402
from app.services.cliente_crm_service import (  # noqa: E402
    aplicar_estado_cuenta,
    construir_estado_cuenta,
    indexar_fila,
    sumar_meses,
)


def sac(operacion="0003021004587", ult=7, venc=20260815, hoy=85, ct=None, cargos=None, vencidas=3,
        capital_vencido=None, dni="40000001", fecha_carga=None):
    """Fila con los nombres reales de SAC_CAR_BIZNESCOB (espacios finales y tildes incluidos)."""
    ct = ct if ct is not None else {"CT 1": 410.35, "CT 2": 418.92, "CT 3": 427.63}
    cargos = cargos if cargos is not None else {
        "CT 11": 52.18, "CT 12": 21.40, "CT 14": 6.50,
        "CT 21": 33.70, "CT 22": 12.10, "CT 24": 6.50,
        "CT 31": 14.05, "CT 32": 3.30, "CT 34": 6.50,
    }
    fila = {
        "DNI": dni, "Cod Operación": operacion, "CodigoGrupo ": 0.0,
        "Ult_CuotaAtrasada ": float(ult) if ult is not None else None,
        "UltFecVen ": float(venc) if venc else None, "DiasAtraso ": float(hoy) if hoy is not None else None,
        "Nro_CuotasVencidas ": float(vencidas) if vencidas is not None else None,
        "SdoCapitalVencido ": capital_vencido if capital_vencido is not None else round(sum(v for v in ct.values() if v), 2),
        "FechaCarga": fecha_carga,
    }
    for grupo in (("CT 1", "CT 11", "CT 12", "CT 13", "CT 14", "CT 15"),
                  ("CT 2", "CT 21", "CT 22", "CT 23", "CT 24", "CT 25"),
                  ("CT 3", "CT 31", "CT 32", "CT 33", "CT 34", "CT 35")):
        for nombre in grupo:
            fila[nombre] = ct.get(nombre, cargos.get(nombre))
    return fila


def asignacion(tabla="compartamos_individual", cartera="Individual", **campos):
    fila = {"Operacion": "3021004587", "NumDoc": "40000001", "NROCUOTAS": 12.0, "NROCUOTASPAGADAS": 6.0,
            "Camp1Cuota%": "20%", "Campaña Final 1 Cuota": 328.28, "Cancelación%": "45%", "Cancelacion": 2189.22}
    fila.update(campos)
    return {"tabla": tabla, "cartera": cartera, "indice": indexar_fila(fila)}


OPERACION = {"operacion": "3021004587", "cuotas_vencidas": 3, "capital_vencido": 1256.90}


class EstadoCuentaTest(unittest.TestCase):
    def setUp(self):
        self.meses_original = crm.MESES_ENTRE_CUOTAS_ESTIMADO

    def tearDown(self):
        crm.MESES_ENTRE_CUOTAS_ESTIMADO = self.meses_original

    def test_01_ubicacion_fechas_y_dias(self):
        ec = construir_estado_cuenta(OPERACION, [sac()], asignacion())
        self.assertTrue(ec["disponible"])
        self.assertEqual([c["numero"] for c in ec["cuotas"]], [7, 8, 9])
        primera, segunda, tercera = ec["cuotas"]
        self.assertEqual(primera["fecha_vencimiento"], "2026-08-15")
        self.assertFalse(primera["fecha_estimada"])
        self.assertEqual(primera["dias_vencida"], 85)  # = DiasAtraso por construccion
        self.assertEqual(segunda["fecha_vencimiento"], "2026-09-15")
        self.assertTrue(segunda["fecha_estimada"])
        self.assertEqual((segunda["dias_vencida"], tercera["dias_vencida"]), (54, 24))
        self.assertEqual(ec["fecha_corte"], "2026-11-08")
        self.assertEqual(ec["fecha_corte_fuente"], "UltFecVen + DiasAtraso")

    def test_02_sin_periodicidad_no_proyecta(self):
        crm.MESES_ENTRE_CUOTAS_ESTIMADO = None
        ec = construir_estado_cuenta(OPERACION, [sac()], asignacion())
        self.assertIsNone(ec["cuotas"][1]["fecha_vencimiento"])
        self.assertIsNone(ec["cuotas"][2]["dias_vencida"])
        self.assertFalse(ec["simulacion_disponible"])
        self.assertTrue(all(c["queda_con_dias"] is None for c in ec["cuotas"]))

    def test_03_hueco_entre_cuotas(self):
        fila = sac(ct={"CT 1": 100.0, "CT 2": 0.0, "CT 3": 120.0}, cargos={})
        ec = construir_estado_cuenta({**OPERACION, "cuotas_vencidas": 2}, [fila], asignacion())
        self.assertEqual([c["numero"] for c in ec["cuotas"]], [7, 9])
        self.assertTrue(any("hueco" in a for a in ec["advertencias"]))

    def test_04_cargos_sin_capital(self):
        fila = sac(ct={"CT 1": None, "CT 2": 200.0}, cargos={"CT 11": 15.0}, vencidas=1)
        ec = construir_estado_cuenta(OPERACION, [fila], asignacion())
        primera = ec["cuotas"][0]
        self.assertIsNone(primera["capital"])
        self.assertEqual(primera["cargos"], 15.0)
        self.assertTrue(any("no capital" in a for a in ec["advertencias"]))

    def test_05_sin_cargos(self):
        ec = construir_estado_cuenta(OPERACION, [sac(cargos={})], asignacion())
        primera = ec["cuotas"][0]
        self.assertIsNone(primera["cargos"])
        self.assertEqual(primera["total"], primera["capital"])

    def test_06_carga_incompleta(self):
        ec = construir_estado_cuenta(OPERACION, [sac(vencidas=5, capital_vencido=1689.09)], asignacion())
        self.assertFalse(ec["conciliacion"]["completo"])
        self.assertFalse(ec["simulacion_disponible"])
        self.assertEqual(ec["simulacion_motivo"], "Faltan cuotas vencidas en la carga.")
        self.assertTrue(any("3 de 5" in a for a in ec["advertencias"]))

    def test_07_conciliacion_de_capital_sin_ajustar(self):
        ec = construir_estado_cuenta(OPERACION, [sac(capital_vencido=1300.00)], asignacion())
        self.assertEqual(ec["conciliacion"]["suma_capital_cuotas"], 1256.90)
        self.assertEqual(ec["conciliacion"]["diferencia_capital"], 43.10)
        self.assertFalse(ec["conciliacion"]["cuadra_capital"])
        self.assertEqual(ec["cuotas"][0]["capital"], 410.35)

    def test_08_duplicadas_distintas_no_se_elige(self):
        ec = construir_estado_cuenta(OPERACION, [sac(), sac(ult=8)], asignacion())
        self.assertTrue(ec["aplica"])
        self.assertFalse(ec["disponible"])
        self.assertIn("2 filas distintas", ec["motivo"])

    def test_08b_duplicadas_identicas_se_aceptan(self):
        ec = construir_estado_cuenta(OPERACION, [sac(), sac()], asignacion())
        self.assertTrue(ec["disponible"])

    def test_09_sin_fila_sac(self):
        ec = construir_estado_cuenta(OPERACION, [], asignacion())
        self.assertTrue(ec["aplica"])
        self.assertFalse(ec["disponible"])
        self.assertEqual(ec["motivo"], "La operación no figura en la carga SAC del día.")

    def test_10_sin_asignacion_individual_no_aplica(self):
        self.assertEqual(construir_estado_cuenta(OPERACION, [sac()], None), {"aplica": False})

    def test_11_sin_ultfecven(self):
        ec = construir_estado_cuenta(OPERACION, [sac(venc=None)], asignacion())
        self.assertTrue(ec["disponible"])
        self.assertTrue(all(c["fecha_vencimiento"] is None for c in ec["cuotas"]))
        self.assertFalse(ec["simulacion_disponible"])
        self.assertTrue(any("UltFecVen" in a for a in ec["advertencias"]))

    def test_12_montos_exactos_en_el_payload(self):
        ec = construir_estado_cuenta(OPERACION, [sac()], asignacion())
        primera = ec["cuotas"][0]
        self.assertEqual((primera["capital"], primera["cargos"], primera["total"]), (410.35, 80.08, 490.43))
        self.assertEqual(primera["componentes_cargos"]["CT 11"], 52.18)
        self.assertIsNone(primera["componentes_cargos"]["CT 13"])

    def test_13_simulacion_si_paga_hasta_aqui(self):
        ec = construir_estado_cuenta(OPERACION, [sac()], asignacion())
        self.assertTrue(ec["simulacion_disponible"])
        self.assertEqual([c["queda_con_dias"] for c in ec["cuotas"]], [54, 24, 0])
        self.assertEqual([c["queda_con_estimado"] for c in ec["cuotas"]], [True, True, False])

    def test_14_ccm(self):
        asig = asignacion("compartamos_ccm", "CCM", NROCUOTASPAGADAS=None)
        ec = construir_estado_cuenta(OPERACION, [sac()], asig)
        self.assertEqual(ec["cartera"], "CCM")
        self.assertEqual(ec["tabla_asignacion"], "compartamos_ccm")
        self.assertIsNone(ec["cuotas_pagadas_asignacion"])

    def test_15_campanas_tal_cual(self):
        ec = construir_estado_cuenta(OPERACION, [sac()], asignacion())
        campanas = ec["campanas"]
        self.assertTrue(campanas["disponible"])
        self.assertEqual(campanas["cuotas"][0], {"cuotas": 1, "porcentaje": "20%", "monto": 328.28})
        self.assertEqual(campanas["cuotas"][1], {"cuotas": 2, "porcentaje": None, "monto": None})
        self.assertEqual(campanas["cancelacion"], {"porcentaje": "45%", "monto": 2189.22})

    def test_16_cruce_sin_ceros_a_la_izquierda(self):
        operaciones = [dict(OPERACION)]
        advertencias = []
        asig = {"por_operacion": {"3021004587": asignacion()}, "advertencias": []}
        aplicar_estado_cuenta(operaciones, [sac(operacion="0003021004587")], asig, advertencias)
        self.assertTrue(operaciones[0]["estado_cuenta"]["disponible"])

    def test_17_fallas_de_consulta(self):
        operaciones = [dict(OPERACION)]
        advertencias = []
        aplicar_estado_cuenta(operaciones, [sac()], None, advertencias)
        self.assertEqual(operaciones[0]["estado_cuenta"], {"aplica": False})
        self.assertTrue(advertencias)
        operaciones = [dict(OPERACION)]
        asig = {"por_operacion": {"3021004587": asignacion()}, "advertencias": []}
        aplicar_estado_cuenta(operaciones, None, asig, [])
        self.assertTrue(operaciones[0]["estado_cuenta"]["aplica"])
        self.assertFalse(operaciones[0]["estado_cuenta"]["disponible"])

    def test_18_cuota_que_aun_no_vence(self):
        # Ult 7 vence 15/10 y la carga es del 20/10 (5 dias): la N.o 8 (15/11) todavia no vence.
        ec = construir_estado_cuenta({**OPERACION, "cuotas_vencidas": 1}, [sac(venc=20261015, hoy=5, vencidas=1)], asignacion())
        segunda = ec["cuotas"][1]
        self.assertTrue(segunda["por_vencer"])
        self.assertIsNone(segunda["dias_vencida"])
        self.assertEqual(ec["cuotas"][0]["queda_con_dias"], 0)

    def test_19_sumar_meses_fin_de_mes(self):
        from datetime import date
        self.assertEqual(sumar_meses(date(2026, 1, 31), 1), date(2026, 2, 28))
        self.assertEqual(sumar_meses(date(2026, 11, 15), 2), date(2027, 1, 15))


class RespuestaRadarTest(unittest.TestCase):
    """construir_respuesta_crm: el bloque aparece en CLIENTE y no se consulta en GRUPO."""

    def fuentes(self, sac_filas, asig):
        vacio = {"disponible": False}
        return [
            patch.object(crm, "consultar_gestiones", return_value={**crm.estructura_gestion_vacia(), "por_dni": {}}),
            patch.object(crm, "consultar_pagos", return_value=crm.estructura_pagos_vacia()),
            patch.object(crm, "consultar_pdp", return_value=crm.estructura_pdp_vacia()),
            patch.object(crm, "consultar_calificacion_asignacion", return_value={"por_dni": {}, "advertencias": []}),
            patch.object(crm, "consultar_sac_por_dni", return_value=sac_filas),
            patch.object(crm, "consultar_asignacion_estado_cuenta", return_value=asig),
        ], vacio

    def test_cliente_con_operacion_individual_y_grupal(self):
        filas_vw = [
            {"DNI": "40000001", "CodOperacion": "3021004587", "Producto": "Crédito Individual", "Nro_CuotasVencidas": 3,
             "SdoCapitalVencido": 1256.90, "DiasAtraso": 85, "Deuda_Total": 4136.63, "CodigoGrupo": 0.0},
            {"DNI": "40000001", "CodOperacion": "3021009911", "Producto": "Crédito Grupal 28 Días", "Nro_CuotasVencidas": 0,
             "DiasAtraso": 0, "Deuda_Total": 1150.0, "CodigoGrupo": 0.0},
        ]
        asig = {"por_operacion": {"3021004587": asignacion()}, "advertencias": []}
        parches, _ = self.fuentes([sac()], asig)
        with parches[0], parches[1], parches[2], parches[3], parches[4], parches[5]:
            respuesta = crm.construir_respuesta_crm(filas_vw, "40000001")
        self.assertEqual(respuesta["tipo_resultado"], "CLIENTE")
        individual, grupal = respuesta["operaciones"]
        self.assertTrue(individual["estado_cuenta"]["disponible"])
        self.assertEqual(individual["estado_cuenta"]["cartera"], "Individual")
        self.assertEqual(grupal["estado_cuenta"], {"aplica": False})

    def test_grupo_no_consulta_estado_cuenta(self):
        filas_vw = [{"DNI": "40000001", "CodOperacion": "1", "CodigoGrupo": 380168.0, "DiasAtraso": 10}]
        parches, _ = self.fuentes([], {"por_operacion": {}, "advertencias": []})
        with parches[0], parches[1], parches[2], parches[3], parches[4] as sac_mock, parches[5] as asig_mock, \
                patch.object(crm, "consultar_datos_grupal", return_value=[]), \
                patch.object(crm, "consultar_cronograma_grupo", return_value=[]):
            respuesta = crm.construir_respuesta_crm(filas_vw, "380168")
        self.assertEqual(respuesta["tipo_resultado"], "GRUPO")
        sac_mock.assert_not_called()
        asig_mock.assert_not_called()
        self.assertNotIn("estado_cuenta", respuesta["operaciones"][0])


if __name__ == "__main__":
    unittest.main()
