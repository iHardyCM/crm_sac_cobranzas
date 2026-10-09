from datetime import date
from io import BytesIO
import unittest
from unittest.mock import patch

from openpyxl import Workbook
import pandas as pd

from app.services.pagos_service import (
    FORMATS,
    aplicar_filtros_formato,
    clasificar_cambios_compartamos,
    construir_resumen_previo,
    leer_archivo,
    normalizar_documento_compartamos,
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

    def test_compartamos_vigente_filtra_usuario_y_saldo_positivo(self):
        df = pd.DataFrame([
            {
                "Usuario_MesAsig": "EXTERNO - BIZNESCOB",
                "Sdo_CON_REC": 100,
            },
            {
                "Usuario_MesAsig": "EXTERNO - BIZNESCOB",
                "Sdo_CON_REC": 0,
            },
            {
                "Usuario_MesAsig": "OTRO USUARIO",
                "Sdo_CON_REC": 100,
            },
        ])

        filtrado = aplicar_filtros_formato(
            df,
            "COMPARTAMOS_VIGENTE",
            FORMATS["COMPARTAMOS_VIGENTE"],
        )

        self.assertEqual(len(filtrado), 1)
        self.assertEqual(filtrado.iloc[0]["Sdo_CON_REC"], 100)

    def test_compartamos_vigente_mapea_llaves_y_fechas(self):
        df = pd.DataFrame([{
            "Usuario_MesAsig": "EXTERNO - BIZNESCOB",
            "MesAsig": date(2026, 9, 29),
            "LinNeg": "IND",
            "Recaudo": 250.50,
            "Sdo_CON_REC": 800,
            "Operacion": "9202040001",
            "CtaCliente": "0000012345",
            "CodCliente": "123456745573053",
        }])

        with patch(
            "app.services.pagos_service.fecha_actual_lima",
            return_value=date(2026, 9, 30),
        ):
            registro = normalizar_registros(
                df,
                "COMPARTAMOS_VIGENTE",
                "20260929 Reporte Cobex Vigente.xlsx",
            )[0]

        self.assertEqual(registro["idcartera"], 126)
        self.assertEqual(registro["num_operacion"], "9202040001")
        self.assertEqual(registro["num_cuenta"], "0000012345")
        self.assertEqual(registro["cod_cliente"], "123456745573053")
        self.assertEqual(registro["documento"], "45573053")
        self.assertEqual(registro["monto_pago_soles"], 250.50)
        self.assertEqual(registro["capital_contenido"], 800)
        self.assertEqual(registro["fecha_proceso"], date(2026, 9, 29))
        self.assertEqual(registro["fecha_pago"], date(2026, 9, 30))
        self.assertEqual(registro["fecha_corte"], date(2026, 9, 30))
        self.assertEqual(registro["codmes"], "202609")

    def test_lectura_compartamos_preserva_identificadores_como_texto(self):
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "base"
        sheet.append([
            "Usuario_MesAsig",
            "MesAsig",
            "LinNeg",
            "Recaudo",
            "Sdo_CON_REC",
            "Operacion",
            "CtaCliente",
            "CodCliente",
        ])
        sheet.append([
            "EXTERNO - BIZNESCOB",
            date(2026, 9, 29),
            "IND",
            250,
            800,
            "00009202040001",
            "0000012345",
            "000000045573053",
        ])
        stream = BytesIO()
        workbook.save(stream)

        df = leer_archivo(
            "COMPARTAMOS_VIGENTE",
            "20260929 Reporte Cobex Vigente.xlsx",
            stream.getvalue(),
        )

        self.assertEqual(df.iloc[0]["Operacion"], "00009202040001")
        self.assertEqual(df.iloc[0]["CtaCliente"], "0000012345")
        self.assertEqual(df.iloc[0]["CodCliente"], "000000045573053")

    def test_compartamos_normaliza_documento_segun_longitud(self):
        self.assertEqual(normalizar_documento_compartamos("123456745573053"), "45573053")
        self.assertEqual(normalizar_documento_compartamos("1234567123456789"), "123456789")
        self.assertEqual(normalizar_documento_compartamos("123456712345678901"), "12345678901")

    def test_compartamos_clasifica_merge_incremental(self):
        base = {
            "formato": "COMPARTAMOS_VIGENTE",
            "codmes": "202609",
            "idcartera": 126,
            "cod_cliente": "123456745573053",
            "documento": "45573053",
            "num_cuenta": "CTA-1",
            "tipo_producto": "TRADICIONAL",
            "clasificacion_sbs": "NORMAL",
            "segmentacion": "IND",
            "usuario_asignado": "EXTERNO - BIZNESCOB",
            "monto_pago_soles": 100,
            "capital_contenido": 500,
        }
        activos = [
            {**base, "num_operacion": "SIN_CAMBIO"},
            {**base, "num_operacion": "ACTUALIZADA"},
            {**base, "num_operacion": "RETIRADA"},
        ]
        staging = [
            {**base, "num_operacion": "SIN_CAMBIO"},
            {**base, "num_operacion": "ACTUALIZADA", "monto_pago_soles": 125},
            {**base, "num_operacion": "NUEVA"},
        ]

        cambios = clasificar_cambios_compartamos(staging, activos)

        self.assertEqual(len(cambios["filas_nuevas"]), 1)
        self.assertEqual(len(cambios["filas_actualizadas"]), 1)
        self.assertEqual(len(cambios["filas_sin_cambio"]), 1)
        self.assertEqual(len(cambios["filas_retiradas"]), 1)

    def test_resumen_compartamos_muestra_idcartera_por_segmento(self):
        registros = [
            {
                "segmentacion": segmento,
                "idcartera": idcartera,
                "estado_fila": "VALIDO",
                "monto_pago_soles": 100,
                "capital_contenido": 200,
                "codmes": "202610",
                "fecha_corte": date(2026, 10, 5),
            }
            for segmento, idcartera in (("GRU", 133), ("CCM", 128), ("IND", 126))
        ]

        resumen = construir_resumen_previo(
            "COMPARTAMOS_VIGENTE",
            "20261005 Reporte Cobex Vigente.xlsx",
            registros,
        )
        ids = {
            item["cartera"]: item["idcartera"]
            for item in resumen["resumen_por_cartera"]
        }

        self.assertEqual(ids, {"GRU": 133, "CCM": 128, "IND": 126})


if __name__ == "__main__":
    unittest.main()
