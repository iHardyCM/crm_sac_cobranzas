import unittest
from decimal import Decimal
from unittest.mock import patch
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from app.services import documentos_service as service
from app.api import routes_documentos as routes
from fastapi import HTTPException


SIP = {
    "TipoDocumento": "D",
    "NumDocumento": "16409720", "Operacion": "4040710002707212",
    "CuentaOrigen": "4040710002707212", "CuentaCastigada": "9202040004089465",
    "NomCliente": "CLIENTE SIP PRUEBA", "Producto": "TARJETA",
    "DeudaTotal": 3022.55, "SdoCapital": 2169.74, "MtoCancelacionCliente": None, "Moneda": "SOLES",
}
INTERBANK = {
    "TipoDocumento": "1 - DNI",
    "NumDocumento": "80026547", "Operacion": "0046465217",
    "CuentaOrigen": "0011344077", "CuentaCastigada": "0046465217",
    "NomCliente": "CLIENTE INTERBANK PRUEBA", "Producto": "06 CRED EFECTIVO",
    "DeudaTotal": 20049.37, "SdoCapital": 3458.68, "MtoCancelacionCliente": 1037.60, "Moneda": "PEN",
}
PAGOS = [{"monto": 100, "fecha": "2026-10-06"}, {"monto": 200, "fecha": "2026-10-16"}]
WORD_NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}


def paragraph_texts(root):
    body = root.find("w:body", WORD_NS)
    return ["".join(node.text or "" for node in paragraph.findall(".//w:t", WORD_NS))
            for paragraph in body.findall("w:p", WORD_NS)]


def table_values(root):
    body = root.find("w:body", WORD_NS)
    return [[["".join(node.text or "" for node in cell.findall(".//w:t", WORD_NS))
              for cell in row.findall("w:tc", WORD_NS)]
             for row in table.findall("w:tr", WORD_NS)]
            for table in body.findall("w:tbl", WORD_NS)]


class DocumentosPropiaTests(unittest.TestCase):
    def test_carteras_y_tipos_separados(self):
        carteras = {item["id"]: item for item in service.listar_carteras_documento()}
        self.assertEqual(carteras[148]["entidad"], "Propia Biznescob")
        self.assertEqual(carteras[137]["entidad"], "Propia Biznescob")
        for origen, cartera_id in (("sip", 148), ("interbank", 137)):
            for modalidad in ("cancelacion", "cuotas"):
                config = service.obtener_config_documento(f"propia_{origen}_{modalidad}")
                self.assertEqual(config["cartera_id"], cartera_id)
                self.assertNotIn("FOH", config["nombre"])

    def test_consultas_usan_tablas_y_cuentas_de_cada_cartera(self):
        class Cursor:
            description = [(name,) for name in ("NumDocumento", "Operacion")]
            def __init__(self): self.sql = ""; self.params = ()
            def execute(self, sql, *params): self.sql, self.params = sql, params
            def fetchall(self): return getattr(self, "rows", [])
            def close(self): pass
        class Connection:
            def __init__(self): self.c = Cursor()
            def cursor(self): return self.c
            def close(self): pass
        for cartera_id, table, fields in (
            (148, "propia_financieraoh", ("NUM_CUENTA_CASTIGADO", "NUM_CUENTA_ORIGEN")),
            (137, "CARTERA_IBK_PROPIA", ("P.CJ", "P.CU")),
        ):
            conn = Connection()
            if cartera_id == 148:
                conn.c.description = [(name,) for name in ("NumDocumento", "Operacion", "SdoCapital")]
                conn.c.rows = [("16409720", SIP["CuentaOrigen"], 2169.74)]
            with patch.object(service, "get_connection", return_value=conn):
                rows = service.consultar_datos_documento_propia(cartera_id, operacion="00123")
            self.assertIn(table, conn.c.sql)
            self.assertTrue(all(field in conn.c.sql for field in fields))
            self.assertEqual(conn.c.params, ("00123", "00123"))
            if cartera_id == 148:
                self.assertIn("CAST(P.NUM_CUENTA_ORIGEN AS VARCHAR(50)) AS Operacion", conn.c.sql)
                self.assertEqual(rows[0]["MontoReferenciaPropia"], 1084.87)
            else:
                self.assertIn("COALESCE(P.INTERES_REGULAR, 0)", conn.c.sql)
                self.assertIn("COALESCE(P.INTERES_COMPENSATORIO, 0)", conn.c.sql)

    def test_modelos_reemplazan_datos_y_cronograma(self):
        for origen, row in (("sip", SIP), ("interbank", INTERBANK)):
            for modalidad in ("cancelacion", "cuotas"):
                tipo = f"propia_{origen}_{modalidad}"
                with patch.object(service, "consultar_datos_documento_propia", return_value=[row]):
                    result = service.generar_documento(
                        tipo, operacion=row["Operacion"], cancelacion=300,
                        fecha_pago="2026-10-06", formato="docx",
                        pagos_mibanco=PAGOS if modalidad == "cuotas" else [],
                        excepcion=origen == "sip",
                    )
                try:
                    with ZipFile(result["path"]) as doc:
                        root = ET.fromstring(doc.read("word/document.xml"))
                        text = "".join(node.text or "" for node in root.findall(".//w:t", WORD_NS))
                        template = service.PROPIA_TEMPLATES[(service.obtener_config_documento(tipo)["cartera_id"], modalidad == "cuotas")]
                        with ZipFile(template) as original:
                            self.assertEqual(doc.read("word/header1.xml"), original.read("word/header1.xml"))
                    self.assertIn(row["NomCliente"], text)
                    self.assertIn(row["NumDocumento"], text)
                    self.assertIn(row["Operacion"], text)
                    if origen == "sip":
                        self.assertNotIn(row["CuentaCastigada"], text)
                    if modalidad == "cuotas":
                        tables = table_values(root)
                        self.assertEqual(len(tables), 2)
                        self.assertEqual(root.find(".//w:tbl/w:tr/w:tc/w:tcPr/w:shd", WORD_NS).get(f"{{{WORD_NS['w']}}}fill"), "2B6FD4")
                        self.assertEqual(root.find(".//w:tbl/w:tr/w:tc/w:p/w:r/w:rPr/w:color", WORD_NS).get(f"{{{WORD_NS['w']}}}val"), "FFFFFF")
                        self.assertEqual(tables[0], [
                            ["Concepto", "Monto"], ["Monto convenio", "300.00"],
                            ["Cuota inicial", "100.00"], ["Número de cuotas", "1"],
                            ["Monto de cuota", "200.00"],
                        ])
                        self.assertEqual(tables[1], [
                            ["NUM CUOTA", "CUOTA", "MES", "AÑO", "DÍA", "MONTO"],
                            ["", "CUOTA INICIAL", "OCTUBRE", "2026", "06", "100.00"],
                            ["1", "CUOTA MENSUAL", "OCTUBRE", "2026", "16", "200.00"],
                        ])
                        with ZipFile(template) as original:
                            original_root = ET.fromstring(original.read("word/document.xml"))
                        original_paragraphs = [(index, text) for index, text in enumerate(paragraph_texts(original_root)) if text]
                        generated_paragraphs = [text for text in paragraph_texts(root) if text]
                        self.assertEqual(len(generated_paragraphs), len(original_paragraphs))
                        for (index, original_text), generated_text in zip(original_paragraphs, generated_paragraphs):
                            if index not in (1, 2, 4, 6, 8, 9):
                                self.assertEqual(generated_text, original_text)
                    else:
                        self.assertEqual(table_values(root)[0], [
                            ["CANCELACIÓN TOTAL", "FECHA DE PAGO"],
                            ["300.00", "06/10/2026"],
                        ])
                        self.assertIn("06/10/2026", text)
                        self.assertEqual(root.find(".//w:tbl/w:tr/w:tc/w:tcPr/w:shd", WORD_NS).get(f"{{{WORD_NS['w']}}}fill"), "2B6FD4")
                        self.assertEqual(root.find(".//w:tbl/w:tr/w:tc//w:rPr/w:color", WORD_NS).get(f"{{{WORD_NS['w']}}}val"), "FFFFFF")
                    self.assertNotIn("ROSSELVET", text)
                    self.assertNotIn("ROJAS LLATAS", text)
                    self.assertNotIn("LITA YESSICA", text)
                finally:
                    result["path"].unlink(missing_ok=True)

    def test_cuotas_rechaza_suma_o_fechas_invalidas(self):
        with patch.object(service, "consultar_datos_documento_propia", return_value=[SIP]):
            with self.assertRaisesRegex(ValueError, "suma"):
                service.generar_documento_propia(
                    service.obtener_config_documento("propia_sip_cuotas"),
                    operacion=SIP["Operacion"], cancelacion=301,
                    fecha_pago="2026-10-06", pagos=PAGOS, excepcion=True,
                )
            with self.assertRaisesRegex(ValueError, "fechas del cronograma"):
                service.generar_documento_propia(
                    service.obtener_config_documento("propia_sip_cuotas"),
                    operacion=SIP["Operacion"], cancelacion=300,
                    fecha_pago="2026-10-06", pagos=list(reversed(PAGOS)), excepcion=True,
                )

    def test_cuotas_variables_y_cuota_inicial_cero(self):
        pagos = [
            {"monto": 0, "fecha": "2026-10-06"},
            {"monto": 33.33, "fecha": "2026-11-06"},
            {"monto": 33.33, "fecha": "2026-12-06"},
            {"monto": 33.34, "fecha": "2027-01-06"},
        ]
        for origen, row in (("sip", SIP), ("interbank", INTERBANK)):
            with patch.object(service, "consultar_datos_documento_propia", return_value=[row]):
                result = service.generar_documento(
                    f"propia_{origen}_cuotas", operacion=row["Operacion"],
                    cancelacion=100, cantidad_cuotas=3, fecha_pago="2026-10-06",
                    pagos_mibanco=pagos, formato="docx", excepcion=origen == "sip",
                )
            try:
                with ZipFile(result["path"]) as doc:
                    root = ET.fromstring(doc.read("word/document.xml"))
                resumen, cronograma = table_values(root)
                self.assertEqual(resumen[3], ["Número de cuotas", "3"])
                self.assertEqual(resumen[2], ["Cuota inicial", "0.00"])
                self.assertEqual(len(cronograma), 5)
                self.assertEqual([item[5] for item in cronograma[1:]], ["0.00", "33.33", "33.33", "33.34"])
                self.assertEqual(result["auditoria_detalle"]["cantidad_cuotas"], 3)
            finally:
                result["path"].unlink(missing_ok=True)

    def test_cuotas_varias_operaciones_suman_deuda_y_generan_un_cronograma(self):
        segundo_sip = dict(SIP, Operacion="4040710009986512", CuentaOrigen="4040710009986512",
                           CuentaCastigada="9202040004090141", DeudaTotal=2095.24, SdoCapital=1319.66)
        primero_ibk = dict(INTERBANK, Operacion="0047255221", CuentaCastigada="0047255221",
                           DeudaTotal=29621.58, MtoCancelacionCliente=10310.75)
        segundo_ibk = dict(INTERBANK, Operacion="0047255222", CuentaCastigada="0047255222",
                           CuentaOrigen="0012308021", Producto="01 VISA", DeudaTotal=15011.71,
                           SdoCapital=5413.10, MtoCancelacionCliente=5246.26)
        for origen, primero, segundo, total, inicial, cuota in (
            ("sip", SIP, segundo_sip, 2000, 200, 900),
            ("interbank", primero_ibk, segundo_ibk, 15557.01, 557.01, 7500),
        ):
            cuentas = {item["Operacion"]: item for item in (primero, segundo)}
            def lookup(_cartera_id, **kwargs):
                item = cuentas.get(kwargs["operacion"])
                return [item] if item else []
            pagos = [{"monto": inicial, "fecha": "2026-10-15"},
                     {"monto": cuota, "fecha": "2026-11-15"},
                     {"monto": cuota, "fecha": "2026-12-15"}]
            solicitudes = [{"operacion": item["Operacion"]} for item in (primero, segundo)]
            with patch.object(service, "consultar_datos_documento_propia", side_effect=lookup):
                result = service.generar_documento(
                    f"propia_{origen}_cuotas", dni=primero["NumDocumento"],
                    cancelacion=total, fecha_pago="2026-10-15", cantidad_cuotas=2,
                    pagos_mibanco=pagos, creditos_propia=solicitudes, formato="docx",
                )
            try:
                with ZipFile(result["path"]) as doc:
                    root = ET.fromstring(doc.read("word/document.xml"))
                text = "".join(node.text or "" for node in root.findall(".//w:t", WORD_NS))
                self.assertIn(primero["Operacion"], text)
                self.assertIn(segundo["Operacion"], text)
                self.assertIn(f"{primero['DeudaTotal'] + segundo['DeudaTotal']:,.2f}", text)
                self.assertEqual(table_values(root)[0][1], ["Monto convenio", f"{total:,.2f}"])
                self.assertEqual(table_values(root)[0][3], ["Número de cuotas", "2"])
                self.assertEqual([fila[5] for fila in table_values(root)[1][1:]],
                                 [f"{inicial:,.2f}", f"{cuota:,.2f}", f"{cuota:,.2f}"])
                self.assertEqual(len(result["auditoria_detalle"]["operaciones"]), 2)
                self.assertTrue(all(item["pago"] is None for item in result["auditoria_detalle"]["operaciones"]))
            finally:
                result["path"].unlink(missing_ok=True)

    def test_cuotas_una_operacion_seleccionada_y_limites_del_total(self):
        segundo = dict(SIP, Operacion="4040710009986512", CuentaOrigen="4040710009986512",
                       CuentaCastigada="9202040004090141", DeudaTotal=2095.24, SdoCapital=1319.66)
        cuentas = {item["Operacion"]: item for item in (SIP, segundo)}
        def lookup(_cartera_id, **kwargs):
            item = cuentas.get(kwargs["operacion"])
            return [item] if item else []
        config = service.obtener_config_documento("propia_sip_cuotas")
        pagos = [{"monto": 0, "fecha": "2026-10-15"}, {"monto": 1200, "fecha": "2026-11-15"}]
        with patch.object(service, "consultar_datos_documento_propia", side_effect=lookup):
            result = service.generar_documento_propia(
                config, dni=SIP["NumDocumento"], cancelacion=1200,
                fecha_pago="2026-10-15", cantidad_cuotas=1,
                pagos=pagos, creditos_propia=[{"operacion": SIP["Operacion"]}],
            )
            try:
                with ZipFile(result["path"]) as doc:
                    root = ET.fromstring(doc.read("word/document.xml"))
                text = "".join(node.text or "" for node in root.findall(".//w:t", WORD_NS))
                self.assertIn(SIP["Operacion"], text)
                self.assertNotIn(segundo["Operacion"], text)
                self.assertIn(f"{SIP['DeudaTotal']:,.2f}", text)
            finally:
                result["path"].unlink(missing_ok=True)
            with self.assertRaisesRegex(ValueError, "50 % del capital total"):
                service.generar_documento_propia(
                    config, dni=SIP["NumDocumento"], cancelacion=1200,
                    fecha_pago="2026-10-15", cantidad_cuotas=1, pagos=pagos,
                    creditos_propia=[{"operacion": SIP["Operacion"]}, {"operacion": segundo["Operacion"]}],
                )
            con_excepcion = service.generar_documento_propia(
                config, dni=SIP["NumDocumento"], cancelacion=1200,
                fecha_pago="2026-10-15", cantidad_cuotas=1, pagos=pagos,
                creditos_propia=[{"operacion": SIP["Operacion"]}, {"operacion": segundo["Operacion"]}],
                excepcion=True,
            )
            try:
                self.assertEqual(len(con_excepcion["auditoria_detalle"]["operaciones"]), 2)
            finally:
                con_excepcion["path"].unlink(missing_ok=True)
            with self.assertRaisesRegex(ValueError, "deuda total"):
                service.generar_documento_propia(
                    config, dni=SIP["NumDocumento"], cancelacion=6000,
                    fecha_pago="2026-10-15", cantidad_cuotas=1,
                    pagos=[{"monto": 0, "fecha": "2026-10-15"}, {"monto": 6000, "fecha": "2026-11-15"}],
                    creditos_propia=[{"operacion": SIP["Operacion"]}, {"operacion": segundo["Operacion"]}],
                )
            cuentas[segundo["Operacion"]] = dict(segundo, SdoCapital=None)
            with self.assertRaisesRegex(ValueError, "capital válido"):
                service.generar_documento_propia(
                    config, dni=SIP["NumDocumento"], cancelacion=1200,
                    fecha_pago="2026-10-15", cantidad_cuotas=1, pagos=pagos,
                    creditos_propia=[{"operacion": SIP["Operacion"]}, {"operacion": segundo["Operacion"]}],
                    excepcion=True,
                )
            cuentas[segundo["Operacion"]] = dict(segundo, NumDocumento="99999999")
            with self.assertRaisesRegex(ValueError, "mismo documento"):
                service.generar_documento_propia(
                    config, dni=SIP["NumDocumento"], cancelacion=1200,
                    fecha_pago="2026-10-15", cantidad_cuotas=1, pagos=pagos,
                    creditos_propia=[{"operacion": SIP["Operacion"]}, {"operacion": segundo["Operacion"]}],
                )

    def test_solicitud_cuotas_acepta_operaciones_sin_montos_individuales(self):
        operaciones = ["0046465217", "0047255222"]
        payload = routes.GenerarDocumentoRequest(
            documento_tipo="propia_interbank_cuotas", dni=INTERBANK["NumDocumento"],
            cancelacion=6283.86,
            creditos_propia=[{"operacion": operacion} for operacion in operaciones],
        )
        enviados = [item.model_dump() for item in payload.creditos_propia]
        self.assertEqual([item["operacion"] for item in enviados], operaciones)
        self.assertTrue(all(item["monto"] is None and item["fecha"] is None for item in enviados))

    def test_cancelacion_no_supera_deuda_total_en_ambas_carteras(self):
        for origen, row in (("sip", SIP), ("interbank", INTERBANK)):
            with patch.object(service, "consultar_datos_documento_propia", return_value=[row]):
                with self.assertRaisesRegex(ValueError, "deuda total"):
                    service.generar_documento_propia(
                        service.obtener_config_documento(f"propia_{origen}_cancelacion"),
                        operacion=row["Operacion"], cancelacion=Decimal(str(row["DeudaTotal"])) + Decimal("0.01"),
                    )

    def test_sip_referencia_50_capital_y_excepcion(self):
        self.assertEqual(str(service.referencia_sip_propia(2169.74)), "1084.87")
        self.assertEqual(str(service.referencia_sip_propia(2169.75)), "1084.88")
        config = service.obtener_config_documento("propia_sip_cancelacion")
        with patch.object(service, "consultar_datos_documento_propia", return_value=[SIP]):
            with self.assertRaisesRegex(ValueError, "Marca Excepción"):
                service.generar_documento_propia(config, operacion=SIP["Operacion"], cancelacion=1084.86)
            for monto, excepcion in ((1084.87, False), (1084.86, True), (2500, False)):
                result = service.generar_documento_propia(
                    config, operacion=SIP["Operacion"], cancelacion=monto, excepcion=excepcion,
                )
                try:
                    self.assertEqual(result["auditoria_detalle"]["referencia_50_capital"], "1,084.87")
                    self.assertEqual(result["auditoria_detalle"]["operaciones"][0]["operacion"], SIP["CuentaOrigen"])
                finally:
                    result["path"].unlink(missing_ok=True)

    def test_interbank_admite_cancelacion_mayor_al_capital_hasta_deuda_total(self):
        config = service.obtener_config_documento("propia_interbank_cancelacion")
        with patch.object(service, "consultar_datos_documento_propia", return_value=[INTERBANK]):
            result = service.generar_documento_propia(config, operacion=INTERBANK["Operacion"], cancelacion=4000)
        result["path"].unlink(missing_ok=True)

    def test_cancelacion_varios_creditos_resume_total_y_fecha_en_cuadro(self):
        segundo_sip = dict(SIP, Operacion="4040710009986512", CuentaOrigen="4040710009986512",
                           CuentaCastigada="9202040004090141", DeudaTotal=2095.24, SdoCapital=1319.66)
        segundo_ibk = dict(INTERBANK, Operacion="0046476510", CuentaCastigada="0046476510",
                           CuentaOrigen="0012308021", DeudaTotal=118185.07, SdoCapital=54131.04)
        for origen, primero, segundo, montos in (
            ("sip", SIP, segundo_sip, (1200, 700)),
            ("interbank", INTERBANK, segundo_ibk, (4000, 17000)),
        ):
            cuentas = {item["Operacion"]: item for item in (primero, segundo)}
            solicitudes = [
                {"operacion": primero["Operacion"], "monto": montos[0], "fecha": "2026-10-06"},
                {"operacion": segundo["Operacion"], "monto": montos[1], "fecha": "2026-10-06"},
            ]
            def lookup(_cartera_id, **kwargs):
                item = cuentas.get(kwargs["operacion"])
                return [item] if item else []
            with patch.object(service, "consultar_datos_documento_propia", side_effect=lookup):
                result = service.generar_documento(
                    f"propia_{origen}_cancelacion", dni=primero["NumDocumento"],
                    cancelacion=sum(montos), fecha_pago="2026-10-06",
                    creditos_propia=solicitudes, formato="docx",
                )
            try:
                with ZipFile(result["path"]) as doc:
                    root = ET.fromstring(doc.read("word/document.xml"))
                text = "".join(node.text or "" for node in root.findall(".//w:t", WORD_NS))
                self.assertIn(primero["Operacion"], text)
                self.assertIn(segundo["Operacion"], text)
                self.assertIn(f"{primero['DeudaTotal'] + segundo['DeudaTotal']:,.2f}", text)
                self.assertEqual(table_values(root)[0], [
                    ["CANCELACIÓN TOTAL", "FECHA DE PAGO"],
                    [f"{sum(montos):,.2f}", "06/10/2026"],
                ])
                self.assertEqual(len(result["auditoria_detalle"]["operaciones"]), 2)
            finally:
                result["path"].unlink(missing_ok=True)

    def test_cancelacion_varios_creditos_valida_cliente_y_umbral_por_credito(self):
        segundo = dict(SIP, Operacion="4040710009986512", CuentaOrigen="4040710009986512",
                       CuentaCastigada="9202040004090141", DeudaTotal=2095.24, SdoCapital=1319.66)
        cuentas = {item["Operacion"]: item for item in (SIP, segundo)}
        def lookup(_cartera_id, **kwargs):
            return [cuentas[kwargs["operacion"]]]
        solicitudes = [
            {"operacion": SIP["Operacion"], "monto": 1500, "fecha": "2026-10-06"},
            {"operacion": segundo["Operacion"], "monto": 500, "fecha": "2026-10-06"},
        ]
        config = service.obtener_config_documento("propia_sip_cancelacion")
        with patch.object(service, "consultar_datos_documento_propia", side_effect=lookup):
            with self.assertRaisesRegex(ValueError, "Marca Excepción"):
                service.generar_documento_propia(config, dni=SIP["NumDocumento"],
                    cancelacion=2000, fecha_pago="2026-10-06", creditos_propia=solicitudes)
            with self.assertRaisesRegex(ValueError, "suma de los créditos"):
                service.generar_documento_propia(config, dni=SIP["NumDocumento"],
                    cancelacion=1900, fecha_pago="2026-10-06", creditos_propia=solicitudes, excepcion=True)
            with self.assertRaisesRegex(ValueError, "deuda total"):
                service.generar_documento_propia(config, dni=SIP["NumDocumento"],
                    cancelacion=3600, fecha_pago="2026-10-06", creditos_propia=[dict(solicitudes[0], monto=3100), solicitudes[1]], excepcion=True)
            with self.assertRaisesRegex(ValueError, "misma fecha de pago"):
                service.generar_documento_propia(config, dni=SIP["NumDocumento"],
                    cancelacion=2000, fecha_pago="2026-10-06", creditos_propia=[solicitudes[0], dict(solicitudes[1], fecha="2026-10-08")], excepcion=True)
            cuentas[segundo["Operacion"]] = dict(segundo, NumDocumento="99999999")
            with self.assertRaisesRegex(ValueError, "mismo documento"):
                service.generar_documento_propia(config, dni=SIP["NumDocumento"],
                    cancelacion=2000, fecha_pago="2026-10-06", creditos_propia=solicitudes, excepcion=True)

    def test_preview_borrador_sin_monto_muestra_pdf(self):
        pagos = [{"monto": 0, "fecha": "2026-10-06"}, {"monto": 0, "fecha": "2026-11-06"}]
        for origen, row in (("sip", SIP), ("interbank", INTERBANK)):
            for modalidad in ("cancelacion", "cuotas"):
                with patch.object(service, "consultar_datos_documento_propia", return_value=[row]):
                    result = service.generar_documento(
                        f"propia_{origen}_{modalidad}", operacion=row["Operacion"],
                        cancelacion=None, cantidad_cuotas=1 if modalidad == "cuotas" else None,
                        pagos_mibanco=pagos if modalidad == "cuotas" else [],
                        fecha_pago="2026-10-06", formato="pdf", permitir_preview=True,
                    )
                try:
                    self.assertTrue(result["path"].read_bytes().startswith(b"%PDF"))
                finally:
                    result["path"].unlink(missing_ok=True)


class DocumentosPropiaRouteTests(unittest.IsolatedAsyncioTestCase):
    async def test_envia_dos_creditos_al_generador_y_auditoria(self):
        creditos = [
            {"operacion": "4040710002707212", "monto": 1200, "fecha": "2026-10-06"},
            {"operacion": "4040710009986512", "monto": 700, "fecha": "2026-10-08"},
        ]
        payload = routes.GenerarDocumentoRequest(
            documento_tipo="propia_sip_cancelacion", dni=SIP["NumDocumento"],
            operacion=SIP["Operacion"], cancelacion=1900, creditos_propia=creditos,
        )
        result = {"path": "acuerdo.docx", "filename": "acuerdo.docx", "formato": "docx",
                  "registro": SIP, "auditoria_detalle": {"operaciones": creditos}}
        with (
            patch.object(routes, "limpiar_documentos_generados"),
            patch.object(routes, "generar_documento", return_value=result) as generar,
            patch.object(routes, "registrar_auditoria_documento") as auditar,
        ):
            await routes.generar_documento_endpoint(payload)
        self.assertEqual(generar.call_args.kwargs["creditos_propia"], creditos)
        self.assertEqual(auditar.call_args.kwargs["operaciones"], [item["operacion"] for item in creditos])

    async def test_no_entrega_acuerdo_sin_traza_de_auditoria(self):
        payload = routes.GenerarDocumentoRequest(
            documento_tipo="propia_sip_cancelacion", dni=SIP["NumDocumento"],
            operacion=SIP["Operacion"], cancelacion=300,
        )
        result = {"path": "acuerdo.docx", "filename": "acuerdo.docx", "formato": "docx", "registro": SIP}
        with (
            patch.object(routes, "limpiar_documentos_generados"),
            patch.object(routes, "generar_documento", return_value=result),
            patch.object(routes, "registrar_auditoria_documento", side_effect=RuntimeError("sin conexión")),
            patch.object(routes.logger, "exception"),
        ):
            with self.assertRaises(HTTPException) as error:
                await routes.generar_documento_endpoint(payload)
        self.assertEqual(error.exception.status_code, 503)


if __name__ == "__main__":
    unittest.main()
