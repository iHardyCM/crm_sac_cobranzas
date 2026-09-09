from datetime import date
from io import BytesIO
import unittest

from openpyxl import Workbook
import pandas as pd

from app.services.pagos_service import leer_archivo, normalizar_registros


class PagosServiceTests(unittest.TestCase):
    def test_financiera_oh_mapea_cuenta_original_y_cliente(self):
        df = pd.DataFrame([{
            "FECHA_PROCESO": date(2026, 8, 31),
            "GESTOR": "BIZNESCOB",
            "SUMA_PAGOS_MES": 450,
            "NUM_CUENTA_ORI": 1234567890123456,
            "NOMBRE_CLIENTE": "CLIENTE DE PRUEBA",
        }])

        registro = normalizar_registros(
            df,
            "FINANCIERA_OH",
            "Cartera_BIZNESCOB_2026-08-31.xls",
        )[0]

        self.assertEqual(registro["num_operacion"], "1234567890123456")
        self.assertEqual(registro["cliente"], "CLIENTE DE PRUEBA")

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
