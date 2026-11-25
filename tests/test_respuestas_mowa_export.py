"""Excel de respuestas, sin conexión a Mowa ni SQL."""

import unittest
from datetime import date
from io import BytesIO
from unittest.mock import patch

from fastapi import HTTPException
from openpyxl import load_workbook

from app.api.routes_respuestas_mowa import ExportacionSms, exportar_sms_mowa
from app.services.respuestas_mowa_export import generar_excel_respuestas


class ExportacionMowaTests(unittest.TestCase):
    def setUp(self):
        self.fila = {
            "cuenta": "INTERBANK_BC", "campana_id": 100, "campana": "Aviso",
            "id": "1", "mensaje_id": "501", "idcartera": 117, "idcliente": 11,
            "dni": "04066636", "cliente": "Cliente A", "telefono": "956300337",
            "recibido": "2026-11-18T17:59:34", "texto": "=SUM(1,1)",
            "estado": "PENDIENTE", "estado_mowa_etiqueta": "ASESORAMIENTO",
            "mensaje_enviado_fecha": "2026-11-18", "mensaje_enviado": "Aviso SMS",
            "gestion_posterior": None, "gestion_posterior_id": None,
            "gestion_posterior_texto": None, "motivo": None,
        }
        self.datos = {
            "desde": "2026-11-01", "hasta": "2026-11-19", "cuenta": None,
            "estado_filtro": "PENDIENTE", "completo": False,
            "advertencias": ["PROPIA_BIZNES: lectura incompleta"],
            "conversaciones": [{"estado": "PENDIENTE", "filas": [
                self.fila, {**self.fila, "id": "2", "texto": "Segunda respuesta",
                            "recibido": "2026-11-18T17:59:35"},
                {**self.fila, "id": "3", "texto": "Tercera respuesta",
                 "recibido": "2026-11-18T17:59:36"},
            ]}],
        }

    def test_excel_una_fila_cliente_tres_respuestas_y_parcial(self):
        archivo = generar_excel_respuestas(self.datos, {117})
        libro = load_workbook(BytesIO(archivo), read_only=False)
        self.assertEqual(libro.sheetnames, ["Clientes", "Respuestas", "Consulta"])
        self.assertEqual(libro["Clientes"].max_row, 2)
        self.assertEqual(libro["Clientes"]["H2"].value, 3)
        encabezados = [c.value for c in libro["Clientes"][1]]
        sms = encabezados.index("SMS enviado (al que respondió)") + 1
        self.assertEqual(libro["Clientes"].cell(2, sms).value, "Aviso SMS")
        self.assertEqual(libro["Clientes"].cell(2, sms + 1).value, "Tercera respuesta")  # Última respuesta al lado.
        self.assertEqual(libro["Respuestas"].max_row, 4)
        self.assertEqual(libro["Respuestas"]["K2"].value, "=SUM(1,1)")
        self.assertEqual(libro["Respuestas"]["K2"].data_type, "s")
        metadatos = {a: b for a, b in libro["Consulta"].iter_rows(min_row=2, values_only=True)}
        self.assertEqual(metadatos["Consulta"], "Parcial")
        self.assertEqual(metadatos["Carteras autorizadas"], "117")
        self.assertEqual(metadatos["Respuestas exportadas"], 3)

    def test_supervisor_no_exporta_cartera_ajena(self):
        payload = ExportacionSms(**self.datos)
        supervisor = {"dni": "s", "tipo": "SUPERVISOR", "idcartera": 124,
                      "permisos_vistas": {"respuestas_mowa": True}}
        with patch("app.api.routes_respuestas_mowa.generar_excel_respuestas") as generar:
            with self.assertRaises(HTTPException) as error:
                exportar_sms_mowa(payload, usuario=supervisor).send(None)
        self.assertEqual(error.exception.status_code, 403)
        generar.assert_not_called()


if __name__ == "__main__":
    unittest.main()
