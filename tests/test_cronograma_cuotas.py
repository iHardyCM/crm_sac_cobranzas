"""Cronograma de cuotas atrasadas, plan de pago y datos de compartamos_grupal.

Solo prueba las reglas de armado; no consulta la base de datos.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.cliente_crm_service import (  # noqa: E402
    DIAS_PROYECCION_ATRASO,
    aplicar_calificacion_integrantes,
    aplicar_datos_grupal,
    construir_cronograma_cuotas,
    construir_datos_grupal,
    construir_plan_pago,
    etiqueta_calificacion,
    fecha_sac,
    formatear_rol,
    redondear_sql,
    texto,
)


def sac(dni, nombre, ult, ct=None, cargos=None, hoy=None, operacion=None, grupo=380168, venc=None):
    """Fila con los nombres reales (espacios finales incluidos) de SAC_CAR_BIZNESCOB.

    venc: UltFecVen (vencimiento de la cuota Ult_CuotaAtrasada) como float AAAAMMDD, igual que SAC."""
    ct = ct or {}
    cargos = cargos or {}
    fila = {
        "DNI": dni, "[NomCliente ]": nombre, "NomCliente ": nombre, "CodigoGrupo ": float(grupo),
        "Cod Operación": operacion or f"op-{dni}", "Ult_CuotaAtrasada ": ult, "DiasAtraso ": hoy,
        "UltFecVen": float(venc) if venc else None,
    }
    for clave in ("CT 1", "CT 2", "CT 3"):
        fila[clave] = ct.get(clave)
    for clave, valor in cargos.items():
        fila[clave] = valor
    return fila


def grupal(dni, **campos):
    base = {"NumDocumento": dni, "CodigoGrupo": 380168.0, "COMITÉ": "", "FecUltPago": None, "Cal_PROV": 0,
            "ProductoCamp": "14 días", "DiasAtraso": 40, "NroCuotas_Aprobadas": 8, "NroCuotasPagadas": 3}
    base.update(campos)
    return base


class DatosGrupalTest(unittest.TestCase):
    def test_rol_en_blanco_es_integrante(self):
        self.assertEqual(formatear_rol(""), "Integrante")
        self.assertEqual(formatear_rol(None), "Integrante")
        self.assertEqual(formatear_rol("PRESIDENTA"), "Presidenta")

    def test_calificacion_por_codigo(self):
        esperado = {0: "Normal", 1: "CPP", 2: "Deficiente", 3: "Dudoso 1", 4: "Dudoso 2", 5: "Pérdida"}
        for codigo, nombre in esperado.items():
            self.assertEqual(etiqueta_calificacion(codigo), f"{codigo}-{nombre}")
            self.assertEqual(etiqueta_calificacion(float(codigo)), f"{codigo}-{nombre}")

    def test_dni_con_ceros_y_aplicacion(self):
        datos = construir_datos_grupal([grupal("0070859388", **{"COMITÉ": "TESORERA", "Cal_PROV": 2, "FecUltPago": "2026-09-21"})])
        integrantes = [{"dni": "70859388", "rol": None, "ultimo_pago_asignacion": None, "calificacion": "x"},
                       {"dni": "11111111", "rol": "x", "ultimo_pago_asignacion": "x", "calificacion": "x"}]
        aplicar_datos_grupal(integrantes, datos)
        self.assertEqual(integrantes[0]["rol"], "Tesorera")
        self.assertEqual(integrantes[0]["ultimo_pago_asignacion"][:10], "2026-09-21")
        # Sin registro en compartamos_grupal no se inventa un valor.
        self.assertIsNone(integrantes[1]["rol"])
        # La calificacion ya no la fija aplicar_datos_grupal: sale de la asignacion (Cal_PROV para grupal).
        for integrante in integrantes:
            integrante["operaciones"] = [{"operacion": None}]
        aplicar_calificacion_integrantes(integrantes, {"por_dni": {}}, datos)
        self.assertEqual(integrantes[0]["calificacion"], "2-Deficiente")
        self.assertEqual(integrantes[0]["tipo_calificacion"], "Calificación")
        self.assertEqual(integrantes[0]["cartera_calificacion"], "Grupal")
        self.assertIsNone(integrantes[1]["calificacion"])

    def test_valores_en_conflicto_no_se_eligen(self):
        datos = construir_datos_grupal([grupal("70859388", Cal_PROV=1), grupal("70859388", Cal_PROV=2)])
        self.assertIsNone(datos["por_dni"]["70859388"]["cal_prov"])
        self.assertTrue(any("distintos" in a for a in datos["advertencias"]))

    def test_columnas_inexistentes_se_reportan(self):
        datos = construir_datos_grupal([{"NumDocumento": "70859388", "CodigoGrupo": 1.0}])
        self.assertTrue(any("No se encontró" in a for a in datos["advertencias"]))
        self.assertNotIn("pct_campana", datos["columnas"])

    def test_rango_atraso_desde_rang_atrasoctagru(self):
        datos = construir_datos_grupal([grupal("70859388", Rang_AtrasoCtaGru="[46 - 60]")])
        self.assertEqual(datos["por_dni"]["70859388"]["rango_atraso"], "[46 - 60]")

    def test_codigo_flotante_se_normaliza(self):
        self.assertEqual(texto(380168.0), "380168")


class CronogramaTest(unittest.TestCase):
    def setUp(self):
        self.filas = [
            # Cronogramas alineados (14 dias): la N.o 4 de Aaron y la N.o 5 de Rocio no coinciden en fecha.
            sac("70859388", "AARON", 4, {"CT 1": 100.10, "CT 2": 110.20, "CT 3": 120.30},
                {"CT 11": 5, "CT 12": 1, "CT 21": 6, "CT 31": 7}, hoy=49, venc=20260801),
            sac("44634806", "ROCIO", 5, {"CT 1": 200, "CT 2": 210}, hoy=49, venc=20260815),
            sac("99999999", "AJENA", 4, {"CT 1": 999}, hoy=10, venc=20260801),
        ]
        self.por_dni = {"70859388": {"comite": "PRESIDENTA", "producto_camp": "14 días", "dias_atraso_inicio": 18, "cuotas_aprobadas": 8, "cuotas_pagadas": 3},
                        "44634806": {"comite": "", "producto_camp": "14 días", "dias_atraso_inicio": 20}}

    def construir(self):
        return construir_cronograma_cuotas(self.filas, ["70859388", "0044634806"], self.por_dni)

    def test_ct1_pertenece_a_ult_cuota_atrasada(self):
        crono = self.construir()
        aaron = next(i for i in crono["integrantes"] if i["dni"] == "70859388")
        self.assertEqual(aaron["cuotas"], {"4": 100.10, "5": 110.20, "6": 120.30})
        rocio = next(i for i in crono["integrantes"] if i["dni"] == "44634806")
        self.assertEqual(rocio["cuotas"], {"5": 200.0, "6": 210.0})

    def test_total_de_cuota_suma_cargos(self):
        aaron = next(i for i in self.construir()["integrantes"] if i["dni"] == "70859388")
        self.assertEqual(aaron["cuotas_total"]["4"], 106.10)   # 100.10 + 5 + 1
        self.assertEqual(aaron["cuotas_total"]["5"], 116.20)   # 110.20 + 6
        self.assertEqual(aaron["cuotas_total"]["6"], 127.30)   # 120.30 + 7

    def test_no_incluye_dni_no_autorizado(self):
        crono = self.construir()
        self.assertEqual({i["dni"] for i in crono["integrantes"]}, {"70859388", "44634806"})
        self.assertTrue(any("no figuran" in a for a in crono["advertencias"]))

    def test_cuotas_ordenadas_y_totales(self):
        crono = self.construir()
        self.assertEqual(crono["cuotas"], [4, 5, 6])
        self.assertEqual(crono["totales"]["5"], 310.2)
        self.assertEqual(crono["totales"]["6"], 330.3)

    def test_atraso_proyectado(self):
        aaron = next(i for i in self.construir()["integrantes"] if i["dni"] == "70859388")
        self.assertEqual(aaron["dias_atraso_inicio"], 18)
        self.assertEqual(aaron["dias_atraso_hoy"], 49)
        self.assertEqual(aaron["dias_atraso_proyectado"], 18 + DIAS_PROYECCION_ATRASO)

    def test_plan_14_dias_son_dos_cuotas_mas_atrasadas(self):
        plan = self.construir()["plan"]
        self.assertTrue(plan["disponible"])
        self.assertEqual(plan["cuotas"], [4, 5])

    def test_rol_en_cronograma(self):
        integrantes = {i["dni"]: i for i in self.construir()["integrantes"]}
        self.assertEqual(integrantes["70859388"]["rol"], "Presidenta")
        self.assertEqual(integrantes["44634806"]["rol"], "Integrante")


    def test_plan_alineado_por_vencimiento_marca_celdas(self):
        crono = self.construir()
        plan = crono["plan"]
        self.assertEqual([v["fecha_vencimiento"] for v in plan["vencimientos"]], ["2026-08-01", "2026-08-15"])
        self.assertTrue(plan["alineado"])
        integrantes = {i["dni"]: i for i in crono["integrantes"]}
        self.assertEqual(integrantes["70859388"]["a_pagar"], {"4": 100.10, "5": 110.20})
        self.assertEqual(integrantes["44634806"]["a_pagar"], {"5": 200.0})
        self.assertEqual(integrantes["44634806"]["a_pagar_detalle"],
                         [{"fecha_vencimiento": "2026-08-15", "cuota": 5, "capital": 200.0, "total": 200.0}])
        self.assertEqual(plan["vencimientos"][1]["capital"], 310.2)
        self.assertNotIn("_ubicacion", integrantes["70859388"])


class PlanPorVencimientoTest(unittest.TestCase):
    """Grupo 44011 (13/10): Felicita (desembolso 17/06) debe su N.o 2; las otras cinco (20/05) su N.o 3.
    Todas vencen el 12/08/2026. Por numero solo se exigia la N.o 2 (1 de 6); deben pagar las seis.
    Montos ilustrativos, no son los del SAC."""

    def setUp(self):
        self.filas = [sac("10000001", "FELICITA", 2, {"CT 1": 48.65, "CT 2": 48.65}, hoy=61, venc=20260812)]
        self.filas += [sac(f"2000000{n}", f"SOCIA {n}", 3, {"CT 1": 100 + n, "CT 2": 100 + n}, hoy=61, venc=20260812)
                       for n in range(1, 6)]
        dnis = [fila["DNI"] for fila in self.filas]
        self.crono = construir_cronograma_cuotas(self.filas, dnis, {dni: {"producto_camp": "Crédito Grupal 28 Días S/."} for dni in dnis})

    def test_todas_pagan_la_cuota_que_vence_el_mismo_dia(self):
        plan = self.crono["plan"]
        self.assertTrue(plan["disponible"])
        self.assertEqual(plan["cuotas_por_pagar"], 1)
        venc = plan["vencimientos"][0]
        self.assertEqual((venc["fecha_vencimiento"], venc["numeros"], venc["integrantes"]), ("2026-08-12", [2, 3], 6))
        self.assertEqual(venc["cuota"], 3)          # numero mas frecuente en esa fecha (solo para mostrar)
        self.assertEqual(plan["cuotas"], [3])
        self.assertFalse(plan["alineado"])
        self.assertEqual(venc["capital"], round(48.65 + sum(100 + n for n in range(1, 6)), 2))

    def test_cada_integrante_paga_su_cuota_de_esa_fecha(self):
        integrantes = {i["dni"]: i for i in self.crono["integrantes"]}
        # Felicita paga su N.o 2; su N.o 3 vence un periodo despues y no se exige.
        self.assertEqual(integrantes["10000001"]["a_pagar"], {"2": 48.65})
        self.assertEqual(integrantes["20000001"]["a_pagar"], {"3": 101.0})
        self.assertTrue(all(len(i["a_pagar_detalle"]) == 1 for i in integrantes.values()))
        self.assertEqual(integrantes["10000001"]["a_pagar_detalle"][0]["fecha_vencimiento"], "2026-08-12")

    def test_matriz_sigue_por_numero(self):
        self.assertEqual(self.crono["cuotas"], [2, 3, 4])
        felicita = next(i for i in self.crono["integrantes"] if i["dni"] == "10000001")
        self.assertEqual(felicita["cuotas"], {"2": 48.65, "3": 48.65})

    def test_sin_fecha_de_vencimiento_no_se_inventa(self):
        filas = [sac("10000001", "SIN FECHA", 2, {"CT 1": 48.65})]
        crono = construir_cronograma_cuotas(filas, ["10000001"], {"10000001": {"producto_camp": "28 días"}})
        self.assertFalse(crono["plan"]["disponible"])
        self.assertIn("UltFecVen", crono["plan"]["motivo"])
        self.assertTrue(any("UltFecVen" in a for a in crono["advertencias"]))

    def test_redondeo_igual_a_sql_server(self):
        self.assertEqual([redondear_sql(x) for x in (0.5, 1.5, 2.5, -0.5, 0.49)], [1, 2, 3, -1, 0])
        self.assertEqual(fecha_sac(20260812.0).isoformat(), "2026-08-12")
        self.assertIsNone(fecha_sac(0))


class PlanPagoTest(unittest.TestCase):
    def test_28_dias_una_cuota(self):
        plan = construir_plan_pago([4, 5, 6], "28 días", False)
        self.assertEqual((plan["disponible"], plan["cuotas"]), (True, [4]))

    def test_14_dias_dos_cuotas(self):
        self.assertEqual(construir_plan_pago([4, 5, 6], "Crédito Grupal 14 Días", False)["cuotas"], [4, 5])

    def test_una_sola_cuota_presente_con_producto_14(self):
        self.assertEqual(construir_plan_pago([5], "14 días", False)["cuotas"], [5])

    def test_producto_desconocido_no_inventa(self):
        plan = construir_plan_pago([4, 5], "7 días", False)
        self.assertFalse(plan["disponible"])
        self.assertIn("motivo", plan)

    def test_sin_producto_o_ambiguo(self):
        self.assertFalse(construir_plan_pago([4, 5], None, False)["disponible"])
        self.assertFalse(construir_plan_pago([4, 5], "14 días", True)["disponible"])

    def test_sin_cuotas(self):
        self.assertFalse(construir_plan_pago([], "14 días", False)["disponible"])


if __name__ == "__main__":
    unittest.main()
