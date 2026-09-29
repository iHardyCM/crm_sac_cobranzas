from datetime import date
from io import BytesIO
import unittest

from openpyxl import Workbook
import pandas as pd

from app.services.pagos_service import (
    leer_archivo,
    normalizar_identity_code,
    normalizar_registros,
)


class PagosServiceTests(unittest.TestCase):
    def test_financiera_oh_conserva_operacion_y_enriquece_llaves(self):
        df = pd.DataFrame([{
            "FECHA_PROCESO": date(2026, 9, 21),
            "FEC_ULT_PAGO": date(2026, 9, 18),
            "GESTOR": "BIZNESCOB",
            "SUMA_PAGOS_MES": 450,
            "IDENTITY_CODE": "D000045573053",
            "NUM_CUENTA_PMCP": "9202040000000001",
            "NUM_CUENTA_ORI": "9202040000000002",
            "NOMBRE_CLIENTE": "CLIENTE DE PRUEBA",
        }])

        registro = normalizar_registros(
            df,
            "FINANCIERA_OH",
            "Cartera_BIZNESCOB_2026-09-21.xls",
        )[0]

        self.assertEqual(registro["idcartera"], 132)
        self.assertEqual(registro["cartera"], "FINANCIERA OH")
        self.assertEqual(registro["tipo_medicion"], "RECUPERO")
        self.assertEqual(registro["dni"], "45573053")
        self.assertEqual(registro["documento"], "D000045573053")
        self.assertEqual(registro["num_operacion"], "9202040000000002")
        self.assertEqual(registro["num_cuenta"], "9202040000000001")
        self.assertEqual(registro["cliente"], "CLIENTE DE PRUEBA")
        self.assertEqual(registro["monto_pago"], 450)
        self.assertEqual(registro["monto_pago_soles"], 450)
        self.assertEqual(registro["fecha_corte"], date(2026, 9, 21))
        self.assertEqual(registro["fecha_movimiento"], date(2026, 9, 18))
        self.assertEqual(registro["fecha_pago"], date(2026, 9, 21))
        self.assertEqual(registro["codmes"], "202609")

    def test_financiera_oh_normaliza_identity_code_como_texto(self):
        self.assertEqual(normalizar_identity_code("D000045573053"), "45573053")
        self.assertEqual(normalizar_identity_code("C000123456789"), "123456789")
        self.assertEqual(normalizar_identity_code("  X0000123  "), "X0000123")
        self.assertEqual(normalizar_identity_code(""), "")

    def test_lectura_interbank_preserva_ceros_iniciales_de_cu(self):
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "PAGOS"
        sheet.append([
            "PERIODOCAMPAÑA",
            "ESTUDIO",
            "FECHA_AMORT",
            "TOTAL_PAGADOMN",
            "CU",
            "CJ",
        ])
        sheet.append([202609, "BIZNESCOB", date(2026, 9, 8), 200, "0012185915", "47669430"])
        stream = BytesIO()
        workbook.save(stream)

        df = leer_archivo("INTERBANK", "pagos.xlsx", stream.getvalue())
        registro = normalizar_registros(df, "INTERBANK", "pagos.xlsx")[0]

        self.assertEqual(registro["cod_cliente"], "0012185915")
        self.assertEqual(registro["num_operacion"], "47669430")

    def test_interbank_mapea_cu_y_cj(self):
        df = pd.DataFrame([{
            "PERIODOCAMPAÑA": 202609,
            "ESTUDIO": "BIZNESCOB",
            "FECHA_AMORT": date(2026, 9, 8),
            "TOTAL_PAGADOMN": 200,
            "CU": "0012185915",
            "CJ": "47669430",
        }])

        registro = normalizar_registros(
            df,
            "INTERBANK",
            "20260908 - BIZNESCOB - PAGOS.XLSX",
        )[0]

        self.assertEqual(registro["cod_cliente"], "0012185915")
        self.assertEqual(registro["num_operacion"], "47669430")

    def test_interbank_conserva_encabezados_anteriores(self):
        df = pd.DataFrame([{
            "PERIODOCAMPAÑA": 202608,
            "ESTUDIO": "BIZNESCOB",
            "FECHA_AMORT": date(2026, 8, 31),
            "TOTAL_PAGADOMN": 300,
            "COD_CLIENTE": "0015266876",
            "NUM_OPERACION": "47696016",
        }])

        registro = normalizar_registros(
            df,
            "INTERBANK",
            "RP BIZNESCOB AGOSTO.xlsx",
        )[0]

        self.assertEqual(registro["cod_cliente"], "0015266876")
        self.assertEqual(registro["num_operacion"], "47696016")


if __name__ == "__main__":
    unittest.main()
