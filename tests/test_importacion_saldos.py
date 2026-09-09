import unittest
from unittest.mock import patch

from app.services.importacion_service import (
    columnas_insertables_saldos,
    detectar_total_columnas_saldos,
    iterar_filas_saldos_sin_cabecera,
    periodo_saldos_desde_archivo,
    preparar_archivo_saldos,
)


class ImportacionSaldosTests(unittest.TestCase):
    def test_lee_archivo_tabulado_sin_cabecera(self):
        contenido = "1\tDOS\t3\r\n4\tCINCO\t6\r\n".encode("cp850")
        estadisticas = {}

        filas = list(iterar_filas_saldos_sin_cabecera(contenido, 3, estadisticas))

        self.assertEqual(filas, [["1", "DOS", "3"], ["4", "CINCO", "6"]])
        self.assertEqual(estadisticas["filas_fisicas"], 2)
        self.assertEqual(estadisticas["filas_reconstruidas"], 0)

    def test_reconstruye_saltos_de_linea_y_limpia_nulos(self):
        contenido = "CALLE 1\r\nMZ A\tPIURA\t\x00ACTIVO\r\n".encode("cp850")
        estadisticas = {}

        filas = list(iterar_filas_saldos_sin_cabecera(contenido, 3, estadisticas))

        self.assertEqual(filas, [["CALLE 1 MZ A", "PIURA", "ACTIVO"]])
        self.assertEqual(estadisticas["filas_reconstruidas"], 1)
        self.assertEqual(estadisticas["caracteres_nulos"], 1)

    def test_rechaza_una_fila_con_mas_columnas_que_el_destino(self):
        contenido = "1\t2\t3\t4\r\n".encode("cp850")

        with self.assertRaisesRegex(ValueError, "supera las 3 columnas"):
            list(iterar_filas_saldos_sin_cabecera(contenido, 3, {}))

    def test_excluye_columnas_no_insertables(self):
        columnas = [
            {"column_name": "dato", "data_type": "varchar", "is_identity": 0, "is_computed": 0},
            {"column_name": "id", "data_type": "int", "is_identity": 1, "is_computed": 0},
            {"column_name": "total", "data_type": "decimal", "is_identity": 0, "is_computed": 1},
            {"column_name": "version", "data_type": "timestamp", "is_identity": 0, "is_computed": 0},
        ]

        resultado = columnas_insertables_saldos(columnas)

        self.assertEqual([columna["column_name"] for columna in resultado], ["dato"])

    def test_detecta_columnas_desde_filas_fisicas_completas(self):
        contenido = "DIRECCION\r\nCONTINUA\tPIURA\tACTIVO\r\n1\t2\t3\r\n".encode("cp850")

        self.assertEqual(detectar_total_columnas_saldos(contenido), 3)

    @patch("app.services.importacion_service.obtener_columnas_tabla")
    @patch("app.services.importacion_service.obtener_configuracion")
    def test_omite_solo_columna_final_con_default(self, obtener_configuracion, obtener_columnas):
        obtener_configuracion.return_value = {
            "id_config": 9,
            "cartera": "COMPARTAMOS",
            "producto": "SALDOS",
            "tabla_destino": "Desarrollo.dbo.SAC_CAR_BIZNESCOB",
        }
        obtener_columnas.return_value = [
            {"column_name": "A", "data_type": "varchar", "has_default": 0},
            {"column_name": "B", "data_type": "varchar", "has_default": 0},
            {"column_name": "C", "data_type": "varchar", "has_default": 0},
            {"column_name": "FechaCarga", "data_type": "datetime", "has_default": 1},
        ]

        contexto = preparar_archivo_saldos(
            id_config=9,
            archivo_nombre="SAC_CAR_BIZNESCOB_20260907.csv",
            contenido="1\t2\t3\r\n".encode("cp850"),
            incluir_preview=True,
        )

        self.assertEqual(contexto["total_columnas_archivo"], 3)
        self.assertEqual([col["column_name"] for col in contexto["columnas_destino"]], ["A", "B", "C"])
        self.assertEqual(contexto["columnas_default_omitidas"][0]["column_name"], "FechaCarga")

    def test_toma_periodo_del_nombre_del_archivo(self):
        self.assertEqual(
            periodo_saldos_desde_archivo("SAC_CAR_BIZNESCOB_20260907.csv"),
            "202609",
        )


if __name__ == "__main__":
    unittest.main()
