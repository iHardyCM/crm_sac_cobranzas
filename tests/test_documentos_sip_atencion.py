import json
import unittest
from unittest.mock import patch
from xml.etree import ElementTree

from fastapi import HTTPException

from app.api import routes_documentos as routes
from app.services import documentos_service as service


REGISTRO_SIP = {
    "TipoDocumento": "DNI",
    "NumDocumento": "45006821",
    "NomCliente": "MARY GARCIA OLAYA",
    "Nombres": "MARY",
    "Apellidos": "GARCIA OLAYA",
    "Operacion": "4040719023523664",
}


class DocumentosSipAtencionTests(unittest.TestCase):
    def test_tipo_esta_disponible_para_financiera_oh(self):
        config = service.obtener_config_documento("sip_constancia_atencion")

        self.assertEqual(config["cartera_id"], 132)
        self.assertEqual(config["document_kind"], "sip_atencion")

    def test_usa_campos_separados_fecha_lima_y_canal_fijo(self):
        capturado = {}
        with patch.object(service, "consultar_datos_documento_sip", return_value=[REGISTRO_SIP.copy()]):
            def pdf_falso(path, context):
                capturado.update(context)

            with patch.object(service, "generar_pdf_sip_atencion", side_effect=pdf_falso):
                result = service.generar_constancia_atencion_sip(
                    service.obtener_config_documento("sip_constancia_atencion"),
                    dni="45006821",
                    operacion="4040719023523664",
                    fecha_pago="2026-08-18",
                    formato="pdf",
                )

        self.assertEqual(capturado["nombres"], "MARY")
        self.assertEqual(capturado["apellidos"], "GARCIA OLAYA")
        self.assertEqual(capturado["tarjeta"], "4040719023523664")
        self.assertEqual(capturado["tarjeta_titular"], "4040719023523664")
        self.assertEqual(capturado["canal"], "CALL CENTER")
        self.assertEqual(capturado["fecha_solicitud"], "18/08/2026")
        detalle = result["auditoria_detalle"]
        self.assertEqual(detalle["modalidad"], "constancia_atencion")
        self.assertEqual(detalle["fecha_solicitud"], "18/08/2026")
        self.assertEqual(detalle["canal"], "CALL CENTER")
        self.assertEqual(detalle["tipo_documento_cliente"], "DNI")
        self.assertEqual(detalle["numero_documento_cliente"], "45006821")
        self.assertEqual(detalle["nombres"], "MARY")
        self.assertEqual(detalle["apellidos"], "GARCIA OLAYA")
        self.assertEqual(detalle["tarjeta"], "4040719023523664")
        self.assertEqual(detalle["tarjeta_titular"], "4040719023523664")

    def test_fecha_solicitud_invalida_se_rechaza(self):
        with patch.object(service, "consultar_datos_documento_sip", return_value=[REGISTRO_SIP.copy()]):
            with self.assertRaisesRegex(ValueError, "AAAA-MM-DD"):
                service.generar_constancia_atencion_sip(
                    service.obtener_config_documento("sip_constancia_atencion"),
                    dni="45006821",
                    operacion="4040719023523664",
                    fecha_pago="18/08/2026",
                    formato="pdf",
                )

    def test_auditoria_persiste_detalle_de_la_constancia(self):
        class CursorFalso:
            def __init__(self):
                self.calls = []

            def execute(self, sql, *params):
                self.calls.append((sql, params))

            def close(self):
                pass

        class ConexionFalsa:
            def __init__(self):
                self.cursor_obj = CursorFalso()

            def cursor(self):
                return self.cursor_obj

            def commit(self):
                pass

            def close(self):
                pass

        conexion = ConexionFalsa()
        detalle = {
            "modalidad": "constancia_atencion",
            "fecha_solicitud": "18/08/2026",
            "canal": "CALL CENTER",
            "tipo_documento_cliente": "DNI",
            "numero_documento_cliente": "45006821",
            "nombres": "MARY",
            "apellidos": "GARCIA OLAYA",
            "tarjeta": "4040719023523664",
            "tarjeta_titular": "4040719023523664",
            "operaciones": [{"operacion": "4040719023523664"}],
        }
        result = {
            "formato": "pdf",
            "filename": "constancia.pdf",
            "registro": REGISTRO_SIP.copy(),
        }
        with patch.object(service, "get_connection", return_value=conexion):
            service.registrar_auditoria_documento(
                result=result,
                documento_tipo="sip_constancia_atencion",
                usuario="12345678",
                nombre_usuario="USUARIO QA",
                perfil_usuario="ADMINISTRADOR",
                detalle_operaciones=detalle,
            )

        insert_params = conexion.cursor_obj.calls[-1][1][0]
        detalle_guardado = json.loads(insert_params[-1])
        self.assertEqual(detalle_guardado["fecha_solicitud"], "18/08/2026")
        self.assertEqual(detalle_guardado["canal"], "CALL CENTER")
        self.assertEqual(detalle_guardado["numero_documento_cliente"], "45006821")
        self.assertEqual(detalle_guardado["tarjeta"], "4040719023523664")

    def test_no_inventa_nombres_ausentes(self):
        registro = REGISTRO_SIP.copy()
        registro["Nombres"] = ""
        with patch.object(service, "consultar_datos_documento_sip", return_value=[registro]):
            with self.assertRaisesRegex(ValueError, "nombres"):
                service.generar_constancia_atencion_sip(
                    service.obtener_config_documento("sip_constancia_atencion"),
                    dni=registro["NumDocumento"],
                    operacion=registro["Operacion"],
                    formato="pdf",
                )

    def test_documento_xml_contiene_datos_y_texto_legal(self):
        context = {
            "cliente": REGISTRO_SIP["NomCliente"],
            "tipo_documento": REGISTRO_SIP["TipoDocumento"],
            "dni": REGISTRO_SIP["NumDocumento"],
            "nombres": REGISTRO_SIP["Nombres"],
            "apellidos": REGISTRO_SIP["Apellidos"],
            "fecha_solicitud": "20/09/2026",
            "canal": "CALL CENTER",
            "tarjeta": REGISTRO_SIP["Operacion"],
            "tarjeta_titular": REGISTRO_SIP["Operacion"],
        }
        document_xml = service.document_sip_atencion_xml(context)
        ElementTree.fromstring(document_xml)

        self.assertIn("Constancia de Atención", document_xml)
        self.assertIn("MARY", document_xml)
        self.assertIn("GARCIA OLAYA", document_xml)
        self.assertIn("CALL CENTER", document_xml)
        self.assertIn(REGISTRO_SIP["Operacion"], document_xml)
        self.assertIn("protección de datos personales", document_xml)
        self.assertIn("rIdLogoSip", document_xml)


class DocumentosSipAtencionRouteTests(unittest.IsolatedAsyncioTestCase):
    async def test_no_entrega_documento_si_falla_su_auditoria(self):
        payload = routes.GenerarDocumentoRequest(
            documento_tipo="sip_constancia_atencion",
            dni="45006821",
            operacion="4040719023523664",
            fecha_pago="2026-08-18",
            formato="pdf",
        )
        result = {
            "path": "constancia.pdf",
            "filename": "constancia.pdf",
            "formato": "pdf",
            "registro": REGISTRO_SIP.copy(),
            "auditoria_detalle": {"fecha_solicitud": "18/08/2026"},
        }
        with (
            patch.object(routes, "limpiar_documentos_generados"),
            patch.object(routes, "generar_documento", return_value=result),
            patch.object(routes, "registrar_auditoria_documento", side_effect=RuntimeError("auditoría no disponible")),
        ):
            with self.assertRaises(HTTPException) as error:
                await routes.generar_documento_endpoint(payload)

        self.assertEqual(error.exception.status_code, 503)
        self.assertIn("traza de auditoría", error.exception.detail)


if __name__ == "__main__":
    unittest.main()
