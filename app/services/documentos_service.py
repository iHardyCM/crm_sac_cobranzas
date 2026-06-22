# documento_service.py
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
import re
import unicodedata
import zipfile
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo

from app.core.database import get_connection


ROOT_DIR = Path(__file__).resolve().parents[2]
TEMPLATES_DIR = ROOT_DIR / "app" / "templates" / "documentos"
OUTPUT_DIR = ROOT_DIR / "app" / "generated_documents"
FONT_FAMILY = "Calibri"
GERENTE_NOMBRE = "LUIS PORTUGUEZ BERROCAL"
GERENTE_DNI = "10416012"
GERENTE_CARGO = "GERENTE GENERAL"
FIRMA_LUIS_PATH = TEMPLATES_DIR / "firma_luis_portuguez.png"

DOCUMENT_TYPES = {
    "transaccion_cancelacion": {
        "id": "transaccion_cancelacion",
        "nombre": "Transaccion extrajudicial y cancelacion de deuda",
        "descripcion": "Carta de transaccion extrajudicial, cancelacion y nota de abono.",
    }
}

MESES = {
    1: "enero",
    2: "febrero",
    3: "marzo",
    4: "abril",
    5: "mayo",
    6: "junio",
    7: "julio",
    8: "agosto",
    9: "septiembre",
    10: "octubre",
    11: "noviembre",
    12: "diciembre",
}


def listar_tipos_documento():
    return list(DOCUMENT_TYPES.values())


def decimal_value(value, default=None):
    if value is None or value == "":
        return default

    try:
        return Decimal(str(value).replace(",", ""))
    except (InvalidOperation, ValueError):
        return default


def serialize_value(value):
    if isinstance(value, Decimal):
        return float(value)

    if isinstance(value, (datetime, date)):
        return value.isoformat()

    return value


def fetch_resultset(cursor):
    columns = [col[0] for col in cursor.description]
    rows = cursor.fetchall()
    return [
        {columns[i]: serialize_value(value) for i, value in enumerate(row)}
        for row in rows
    ]


def limpiar_texto(value):
    return str(value or "").strip()


def format_money(value):
    amount = decimal_value(value, Decimal("0"))
    return f"{amount:,.2f}"


def format_fecha_pago(value):
    if not value:
        return ""

    try:
        parsed = datetime.strptime(str(value), "%Y-%m-%d").date()
        return parsed.strftime("%d/%m/%Y")
    except ValueError:
        return str(value)


def fecha_larga_hoy():
    today = datetime.now(ZoneInfo("America/Lima")).date()
    return f"{today.day} de {MESES[today.month]} del {today.year}"


def filtros_documento(dni=None, operacion=None, codigo_grupo=None, cod_cre_grupal=None):
    filtros = []
    params = []

    if limpiar_texto(operacion):
        return "CAST(CG.Operacion AS VARCHAR(50)) = ?", [limpiar_texto(operacion)]

    if limpiar_texto(dni):
        filtros.append("RTRIM(LTRIM(CG.NumDocumento)) = ?")
        params.append(limpiar_texto(dni))

    if limpiar_texto(codigo_grupo):
        filtros.append("CAST(CG.CodigoGrupo AS VARCHAR(50)) = ?")
        params.append(limpiar_texto(codigo_grupo))

    if limpiar_texto(cod_cre_grupal):
        filtros.append("CAST(CG.CodCreGrupal AS VARCHAR(50)) = ?")
        params.append(limpiar_texto(cod_cre_grupal))

    if not filtros:
        raise ValueError("Ingresa al menos DNI, operacion, cuenta grupal o codigo grupal.")

    return " AND ".join(filtros), params


def consultar_datos_documento(dni=None, operacion=None, codigo_grupo=None, cod_cre_grupal=None, limit=20):
    where, params = filtros_documento(
        dni=dni,
        operacion=operacion,
        codigo_grupo=codigo_grupo,
        cod_cre_grupal=cod_cre_grupal,
    )

    conn = None
    cursor = None

    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            f"""
            SELECT TOP {int(limit)}
                CG.NumDocumento,
                CG.Operacion,
                CG.NomCliente,
                CG.Direccion_Principal AS DireccionPrincipal,
                CG.Distrito_Principal,
                CG.[Mto CancelacionCliente] AS MtoCancelacionCliente,
                CG.NroCuotas_Aprobadas,
                CG.NroCuotasPagadas,
                CG.NroCuotas,
                CG.DiasAtraso,
                CG.CodigoGrupo,
                CG.CodCreGrupal,
                CG.NomGrupo,
                SB.[SdoCapital ] AS SdoCapital,
                SB.[Deuda_Total ] AS DeudaTotal,
                SB.[CT 1] AS CT1,
                SB.[CT 11] AS CT11,
                SB.[CT 12] AS CT12,
                SB.[CT 13] AS CT13,
                SB.[CT 14] AS CT14,
                SB.[CT 15] AS CT15,
                SB.[CT 2] AS CT2,
                SB.[CT 21] AS CT21,
                SB.[CT 22] AS CT22,
                SB.[CT 23] AS CT23,
                SB.[CT 24] AS CT24,
                SB.[CT 25] AS CT25,
                SB.[Ult_CuotaAtrasada ] AS UltCuotaAtrasada
            FROM Desarrollo.DBO.compartamos_grupal CG WITH(NOLOCK)
            LEFT JOIN Desarrollo.DBO.SAC_CAR_BIZNESCOB SB WITH(NOLOCK)
                ON RIGHT('00000000000000000000' + CAST(CG.Operacion AS NVARCHAR(20)), 20) = SB.[Cod Operación]
            WHERE {where}
            ORDER BY CG.NomCliente, CG.Operacion
            """,
            *params,
        )
        return fetch_resultset(cursor)
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()


def obtener_registro_unico(dni=None, operacion=None, codigo_grupo=None, cod_cre_grupal=None):
    rows = consultar_datos_documento(
        dni=dni,
        operacion=operacion,
        codigo_grupo=codigo_grupo,
        cod_cre_grupal=cod_cre_grupal,
        limit=2,
    )

    if not rows:
        raise ValueError("No se encontro informacion para generar el documento.")

    if len(rows) > 1 and not limpiar_texto(operacion):
        raise ValueError("La busqueda devolvio mas de una operacion. Selecciona una operacion antes de generar.")

    return rows[0]


def validar_cancelacion(cancelacion, minimo):
    monto_cancelacion = decimal_value(cancelacion)
    monto_minimo = decimal_value(minimo, Decimal("0"))

    if monto_cancelacion is None:
        raise ValueError("Ingresa un monto de cancelacion valido.")

    if monto_cancelacion <= monto_minimo:
        raise ValueError(
            f"La cancelacion debe ser mayor a S/ {format_money(monto_minimo)} "
            f"(Mto CancelacionCliente de la consulta SQL)."
        )

    return monto_cancelacion, monto_minimo


def safe_filename(value):
    text = re.sub(r"[^A-Za-z0-9_-]+", "_", limpiar_texto(value))
    return text.strip("_") or "documento"


W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def extract_mergefield_name(instr_text):
    match = re.search(r'MERGEFIELD\s+"?([^"\\\s]+)"?', instr_text, flags=re.IGNORECASE)
    return match.group(1).strip() if match else None


def normalizar_field_name(value):
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(char for char in text if not unicodedata.combining(char))
    return text.strip().upper()


def flatten_mergefields(xml, field_values):
    normalized_values = {
        normalizar_field_name(key): value
        for key, value in field_values.items()
    }

    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        return xml

    def fld_char_type(run):
        fld = run.find(f"{{{W_NS}}}fldChar")
        if fld is None:
            return None
        return fld.attrib.get(f"{{{W_NS}}}fldCharType")

    def field_name_from_runs(runs):
        instr_text = "".join(
            node.text or ""
            for run in runs
            for node in run.iter(f"{{{W_NS}}}instrText")
        )
        return extract_mergefield_name(instr_text)

    def run_text(run):
        return "".join(node.text or "" for node in run.iter(f"{{{W_NS}}}t"))

    for paragraph in root.iter(f"{{{W_NS}}}p"):
        children = list(paragraph)
        index = 0

        while index < len(children):
            child = children[index]

            if child.tag != f"{{{W_NS}}}r" or fld_char_type(child) != "begin":
                index += 1
                continue

            end_index = None
            for candidate in range(index + 1, len(children)):
                if children[candidate].tag == f"{{{W_NS}}}r" and fld_char_type(children[candidate]) == "end":
                    end_index = candidate
                    break

            if end_index is None:
                index += 1
                continue

            field_runs = children[index:end_index + 1]
            field_name = field_name_from_runs(field_runs)
            normalized_name = normalizar_field_name(field_name)

            if normalized_name not in normalized_values:
                index = end_index + 1
                continue

            if (
                normalized_name == "CANCELACION"
                and end_index + 1 < len(children)
                and children[end_index + 1].tag == f"{{{W_NS}}}r"
                and run_text(children[end_index + 1]) == ".00"
            ):
                field_runs = children[index:end_index + 2]

            run = ET.Element(f"{{{W_NS}}}r")
            text = ET.SubElement(run, f"{{{W_NS}}}t")
            text.text = str(normalized_values[normalized_name])

            for old_run in field_runs:
                paragraph.remove(old_run)

            paragraph.insert(index, run)
            children = list(paragraph)
            index += 1

    return ET.tostring(root, encoding="unicode")


def replace_in_xml(xml, replacements, field_values, flatten_fields=False):
    xml = re.sub(r"<w:mailMerge\b.*?</w:mailMerge>", "", xml, flags=re.DOTALL)

    if flatten_fields:
        xml = flatten_mergefields(xml, field_values)

    for source, target in replacements.items():
        xml = xml.replace(source, escape(str(target)))

    xml = re.sub(r"<w:highlight\b[^>]*/>", "", xml)
    return xml


def generar_docx_desde_template(template_path, output_path, replacements):
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(template_path, "r") as zin, zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)

            if item.filename.startswith("word/") and item.filename.endswith(".xml"):
                xml = data.decode("utf-8")
                data = replace_in_xml(
                    xml,
                    replacements,
                    replacements,
                    flatten_fields=item.filename == "word/document.xml",
                ).encode("utf-8")

            if item.filename == "word/_rels/settings.xml.rels":
                data = (
                    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>'
                ).encode("utf-8")

            zout.writestr(item, data)


def xml_text(value):
    return escape(str(value or ""))


def run_xml(text, bold=False, size=19, underline=False):
    bold_xml = "<w:b/>" if bold else ""
    underline_xml = '<w:u w:val="single"/>' if underline else ""
    return (
        "<w:r><w:rPr>"
        f'<w:rFonts w:ascii="{FONT_FAMILY}" w:hAnsi="{FONT_FAMILY}" w:cs="{FONT_FAMILY}"/>'
        f"{bold_xml}{underline_xml}<w:sz w:val=\"{size}\"/><w:szCs w:val=\"{size}\"/>"
        f"</w:rPr><w:t xml:space=\"preserve\">{xml_text(text)}</w:t></w:r>"
    )


def paragraph_xml(text="", bold=False, align="both", before=0, after=72, size=19, keep_next=False):
    keep_xml = "<w:keepNext/>" if keep_next else ""
    return (
        "<w:p><w:pPr>"
        f"{keep_xml}<w:spacing w:before=\"{before}\" w:after=\"{after}\" w:line=\"220\" w:lineRule=\"auto\"/>"
        f"<w:jc w:val=\"{align}\"/>"
        "</w:pPr>"
        f"{run_xml(text, bold=bold, size=size)}"
        "</w:p>"
    )


def paragraph_runs_xml(runs, align="both", before=0, after=72, size=19, keep_next=False):
    keep_xml = "<w:keepNext/>" if keep_next else ""
    runs_body = "".join(
        run_xml(
            item.get("text", ""),
            bold=item.get("bold", False),
            underline=item.get("underline", False),
            size=item.get("size", size),
        )
        for item in runs
    )
    return (
        "<w:p><w:pPr>"
        f"{keep_xml}<w:spacing w:before=\"{before}\" w:after=\"{after}\" w:line=\"220\" w:lineRule=\"auto\"/>"
        f"<w:jc w:val=\"{align}\"/>"
        "</w:pPr>"
        f"{runs_body}"
        "</w:p>"
    )


def title_xml(text):
    return paragraph_xml(text, bold=True, align="center", before=0, after=130, size=22, keep_next=True)


def centered_xml(text="", bold=False, before=0, after=50, size=18):
    return paragraph_xml(text, bold=bold, align="center", before=before, after=after, size=size)


def right_xml(text="", bold=False, before=0, after=70, size=18):
    return paragraph_xml(text, bold=bold, align="right", before=before, after=after, size=size)


def image_xml(rel_id="rIdFirmaLuis", doc_id=1, cx=1500000, cy=760000):
    return (
        "<w:p><w:pPr><w:spacing w:before=\"0\" w:after=\"0\"/><w:jc w:val=\"center\"/></w:pPr><w:r>"
        "<w:drawing>"
        "<wp:inline xmlns:wp=\"http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing\" distT=\"0\" distB=\"0\" distL=\"0\" distR=\"0\">"
        f"<wp:extent cx=\"{cx}\" cy=\"{cy}\"/>"
        "<wp:effectExtent l=\"0\" t=\"0\" r=\"0\" b=\"0\"/>"
        f"<wp:docPr id=\"{doc_id}\" name=\"Firma Luis Portuguez\"/>"
        "<wp:cNvGraphicFramePr><a:graphicFrameLocks xmlns:a=\"http://schemas.openxmlformats.org/drawingml/2006/main\" noChangeAspect=\"1\"/></wp:cNvGraphicFramePr>"
        "<a:graphic xmlns:a=\"http://schemas.openxmlformats.org/drawingml/2006/main\">"
        "<a:graphicData uri=\"http://schemas.openxmlformats.org/drawingml/2006/picture\">"
        "<pic:pic xmlns:pic=\"http://schemas.openxmlformats.org/drawingml/2006/picture\">"
        "<pic:nvPicPr><pic:cNvPr id=\"1\" name=\"firma_luis_portuguez.png\"/><pic:cNvPicPr/></pic:nvPicPr>"
        "<pic:blipFill>"
        f"<a:blip xmlns:r=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships\" r:embed=\"{rel_id}\"/>"
        "<a:stretch><a:fillRect/></a:stretch>"
        "</pic:blipFill>"
        "<pic:spPr><a:xfrm><a:off x=\"0\" y=\"0\"/>"
        f"<a:ext cx=\"{cx}\" cy=\"{cy}\"/>"
        "</a:xfrm><a:prstGeom prst=\"rect\"><a:avLst/></a:prstGeom></pic:spPr>"
        "</pic:pic></a:graphicData></a:graphic>"
        "</wp:inline>"
        "</w:drawing>"
        "</w:r></w:p>"
    )


def table_cell(text, bold=False, width=2400, align="center"):
    return (
        "<w:tc><w:tcPr>"
        f"<w:tcW w:w=\"{width}\" w:type=\"dxa\"/>"
        '<w:vAlign w:val="center"/>'
        '<w:tcMar><w:top w:w="50" w:type="dxa"/><w:left w:w="100" w:type="dxa"/>'
        '<w:bottom w:w="50" w:type="dxa"/><w:right w:w="100" w:type="dxa"/></w:tcMar>'
        "</w:tcPr>"
        f"{paragraph_xml(text, bold=bold, align=align, after=0, size=18)}"
        "</w:tc>"
    )


def payment_table_xml(cancelacion, fecha_pago):
    borders = (
        "<w:tblBorders>"
        '<w:top w:val="single" w:sz="8" w:space="0" w:color="000000"/>'
        '<w:left w:val="single" w:sz="8" w:space="0" w:color="000000"/>'
        '<w:bottom w:val="single" w:sz="8" w:space="0" w:color="000000"/>'
        '<w:right w:val="single" w:sz="8" w:space="0" w:color="000000"/>'
        '<w:insideH w:val="single" w:sz="8" w:space="0" w:color="000000"/>'
        '<w:insideV w:val="single" w:sz="8" w:space="0" w:color="000000"/>'
        "</w:tblBorders>"
    )
    return (
        "<w:tbl><w:tblPr>"
        '<w:tblW w:w="4400" w:type="dxa"/>'
        '<w:jc w:val="center"/>'
        f"{borders}"
        '<w:tblCellMar><w:top w:w="80" w:type="dxa"/><w:left w:w="100" w:type="dxa"/>'
        '<w:bottom w:w="80" w:type="dxa"/><w:right w:w="100" w:type="dxa"/></w:tblCellMar>'
        "</w:tblPr>"
        '<w:tblGrid><w:gridCol w:w="2200"/><w:gridCol w:w="2200"/></w:tblGrid>'
        f"<w:tr>{table_cell('Monto', bold=True)}{table_cell('Fecha de Pago/ Cancelación', bold=True)}</w:tr>"
        f"<w:tr>{table_cell(f'S/ {cancelacion}')}{table_cell(fecha_pago)}</w:tr>"
        "</w:tbl>"
    )


def signature_cell_xml(label, dni="", cargo="", width=3600, firma=False, doc_id=1):
    firma_xml = image_xml(doc_id=doc_id) if firma and FIRMA_LUIS_PATH.exists() else ""
    if firma_xml:
        return (
            "<w:tc><w:tcPr>"
            f"<w:tcW w:w=\"{width}\" w:type=\"dxa\"/>"
            '<w:vAlign w:val="bottom"/>'
            '<w:tcMar><w:top w:w="80" w:type="dxa"/><w:left w:w="120" w:type="dxa"/>'
            '<w:bottom w:w="80" w:type="dxa"/><w:right w:w="120" w:type="dxa"/></w:tcMar>'
            "</w:tcPr>"
            + firma_xml
            + "</w:tc>"
        )

    return (
        "<w:tc><w:tcPr>"
        f"<w:tcW w:w=\"{width}\" w:type=\"dxa\"/>"
        '<w:vAlign w:val="bottom"/>'
        '<w:tcMar><w:top w:w="80" w:type="dxa"/><w:left w:w="120" w:type="dxa"/>'
        '<w:bottom w:w="80" w:type="dxa"/><w:right w:w="120" w:type="dxa"/></w:tcMar>'
        "</w:tcPr>"
        + centered_xml("____________________________", before=0, after=10, size=17)
        + centered_xml(label, bold=True, after=6, size=17)
        + (centered_xml(f"D.N.I. {dni}", bold=True, after=6, size=17) if dni else "")
        + (centered_xml(cargo, bold=True, after=0, size=16) if cargo else "")
        + "</w:tc>"
    )


def signature_table_xml(dni, before=230, after=60, doc_id=1):
    return (
        paragraph_xml("", before=before, after=0)
        + "<w:tbl><w:tblPr>"
        '<w:tblW w:w="7600" w:type="dxa"/>'
        '<w:jc w:val="center"/>'
        "</w:tblPr>"
        '<w:tblGrid><w:gridCol w:w="3800"/><w:gridCol w:w="3800"/></w:tblGrid>'
        f"<w:tr>{signature_cell_xml('EL/LA DEUDOR/A', dni=dni, width=3800)}{signature_cell_xml(GERENTE_NOMBRE, width=3800, firma=True, doc_id=doc_id)}</w:tr>"
        "</w:tbl>"
        + paragraph_xml("", before=0, after=after)
    )


def page_break_xml():
    return '<w:p><w:r><w:br w:type="page"/></w:r></w:p>'


def clause_xml(label, text, after=120):
    return paragraph_runs_xml(
        [
            {"text": f"{label}.- ", "bold": True, "underline": True},
            {"text": text},
        ],
        after=after,
        size=18,
    )


def clause_exact_xml(label, text, after=70):
    return paragraph_runs_xml(
        [
            {"text": label, "bold": True, "underline": True},
            {"text": text},
        ],
        after=after,
        size=18,
    )


def document_xml(context):
    paragraphs = [
        title_xml("Transacción extrajudicial y Cancelación de Deuda"),
        paragraph_xml(
            "Conste por el presente documento una Transacción Extrajudicial y Cancelación de Deuda, que celebran "
            "de una parte la Empresa de cobranza _BIZNESCOB, con RUC_20602593640, con domicilio en Enrique Encinas "
            "284 la victoria y representado por el sr(a) LUIS PORTUGUEZ BERROCAL identificado con DNI 10416012, "
            "por encargo de COMPARTAMOS BANCO S.A.,  en adelante COMPARTAMOS, con domicilio en Av. Paseo de la "
            "Republica N° 5895 – Interior 1301, distrito de Mira flores, provincia y departamento de Lima, inscrita "
            "en la Partida Nro. 13777030 del Registro de Personas Jurídicas de la Zona Registral Nro. IX - Sede Lima "
            f"y de otra parte el/la Sr (a) {context['cliente']} identificado con DNI N°.{context['dni']}, con domicilio "
            f"en {context['direccion']}, distrito de {context['distrito']}, a quien en adelante se le denominara  "
            "EL/LA/DEUDOR/A, en los términos y condiciones siguientes:",
            after=70,
            size=18,
        ),
        clause_exact_xml(
            "PRIMERA.- ",
            f"EL DEUDOR reconoce adeudar a COMPARTAMOS BANCO el crédito {context['operacion']}, cuyo  importe "
            f"asciende  a la suma total de S/  {context['deuda_total']},  según liquidación a la fecha.",
            after=65,
        ),
        clause_exact_xml(
            "SEGUNDA- ",
            "De conformidad con lo señalado en la cláusula anterior EL DEUDOR se obliga a cancelar a   COMPARTAMOS "
            "BANCO la deuda antes descrita de la siguiente manera:",
            after=55,
        ),
        payment_table_xml(context["cancelacion"], context["fecha_corta"]),
        paragraph_xml(
            "La cancelación de la suma antes detallada está sujeta al pago acordado en el párrafo que antecede.",
            before=60,
            after=65,
            size=18,
        ),
        clause_exact_xml(
            "TERCERA .- ",
            "Sin perjuicio de lo señalado, COMPARTAMOS se reserva el derecho de iniciar, interponer o continuar "
            "con las acciones administrativas, legales o judiciales en caso de que el EL/LA/DEUDOR/A incumpla las "
            "obligaciones que por el presente documento asume; COMPARTAMOS quedará expedito para su cobro de "
            "conformidad con lo estipulado por inciso 8 del artículo 688 del Código Proceso Civil.",
        ),
        clause_exact_xml(
            "CUARTA .- ",
            "Las garantías y/o fianzas solidarias constituidas en respaldo de la obligación antes señalada subsisten "
            "en tanto no se cancele totalmente la misma por el monto acordado, por cuanto la suscripción de presente "
            "convenio no constituye una novación de la obligación",
        ),
        clause_exact_xml(
            "QUINTA .- ",
            "El incumplimiento o retraso en el pago del monto señalado en la cláusula segunda, a criterio de "
            "COMPARTAMOS, quedarán sin efecto los beneficios (descuentos u otros) otorgados a EL/LA/DEUDOR/A, "
            "recalculando los intereses y mora que se hayan generado posteriormente.",
        ),
        clause_exact_xml(
            "SÉXTA :  ",
            "EL/LA/DEUDOR/A ratifica su voluntad expresada en el presente instrumento, dejando constancia que no    "
            "ha mediado vicio capaz  de invalidarlo.",
            after=80,
        ),
        right_xml(context["fecha_larga"], after=90, size=18),
        signature_table_xml(context["dni"], before=120, after=35, doc_id=1),
        title_xml("NOTA DE ABONO"),
        paragraph_xml(
            "Por el presente documento COMPARTAMOS, concede condonación sobre la deuda de EL/LA/DEUDOR/A, según "
            "las condiciones ofrecidas en la en el presente documento.",
            after=55,
            size=18,
        ),
        paragraph_xml(
            f"Sr(a):{context['cliente']} con DNI Nº {context['dni']} por la suma de S/ {context['condonacion']}",
            bold=True,
            align="center",
            before=40,
            after=60,
            size=19,
        ),
        paragraph_xml(
            "EL/LA/DEUDOR/A, acepta el descuento indicado, reduciendo la deuda vigente que se detalla en la presente "
            "transacción, la misma que mantiene su validez, si EL/LA/DEUDOR/A cumple todas las condiciones descritas "
            "en el documento.",
            after=55,
            size=18,
        ),
        paragraph_xml(
            f"El descuento está sujeto al cumplimiento del pago de: S/ {context['cancelacion']} en las fechas y "
            "formas acordadas en la cláusula segunda.",
            after=60,
            size=18,
        ),
        signature_table_xml(context["dni"], before=230, after=40, doc_id=2),
    ]

    body = "".join(paragraphs)
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f"<w:body>{body}"
        "<w:sectPr>"
        '<w:pgSz w:w="12240" w:h="15840"/>'
        '<w:pgMar w:top="720" w:right="760" w:bottom="720" w:left="760" w:header="360" w:footer="360" w:gutter="0"/>'
        "</w:sectPr></w:body></w:document>"
    )


def styles_xml():
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        '<w:style w:type="paragraph" w:default="1" w:styleId="Normal">'
        '<w:name w:val="Normal"/>'
        f'<w:rPr><w:rFonts w:ascii="{FONT_FAMILY}" w:hAnsi="{FONT_FAMILY}" w:cs="{FONT_FAMILY}"/><w:sz w:val="19"/><w:szCs w:val="19"/></w:rPr>'
        "</w:style></w:styles>"
    )


def generar_docx_limpio(output_path, context):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    parts = {
        "[Content_Types].xml": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Default Extension="png" ContentType="image/png"/>'
            '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
            '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
            '<Override PartName="/word/settings.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.settings+xml"/>'
            "</Types>"
        ),
        "_rels/.rels": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
            "</Relationships>"
        ),
        "word/_rels/document.xml.rels": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
            '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/settings" Target="settings.xml"/>'
            '<Relationship Id="rIdFirmaLuis" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/firma_luis_portuguez.png"/>'
            "</Relationships>"
        ),
        "word/document.xml": document_xml(context),
        "word/styles.xml": styles_xml(),
        "word/settings.xml": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<w:settings xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            '<w:zoom w:percent="100"/>'
            "</w:settings>"
        ),
    }

    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zout:
        for name, content in parts.items():
            zout.writestr(name, content.encode("utf-8"))
        if FIRMA_LUIS_PATH.exists():
            zout.write(FIRMA_LUIS_PATH, "word/media/firma_luis_portuguez.png")


def generar_pdf_limpio(output_path, context):
    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_RIGHT
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import inch
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except ImportError as exc:
        raise ValueError("Para descargar en PDF instala la dependencia reportlab y reinicia el servidor.") from exc

    calibri = Path("C:/Windows/Fonts/calibri.ttf")
    calibrib = Path("C:/Windows/Fonts/calibrib.ttf")
    font_name = "Calibri"
    bold_font = "Calibri-Bold"

    if calibri.exists():
        pdfmetrics.registerFont(TTFont(font_name, str(calibri)))
    else:
        font_name = "Helvetica"

    if calibrib.exists():
        pdfmetrics.registerFont(TTFont(bold_font, str(calibrib)))
    else:
        bold_font = "Helvetica-Bold"

    styles = getSampleStyleSheet()
    body = ParagraphStyle(
        "body",
        parent=styles["Normal"],
        fontName=font_name,
        fontSize=7.45,
        leading=8.55,
        alignment=TA_JUSTIFY,
        spaceAfter=4,
    )
    title = ParagraphStyle(
        "title",
        parent=body,
        fontName=bold_font,
        fontSize=9.6,
        leading=10.5,
        alignment=TA_CENTER,
        spaceAfter=8,
    )
    center = ParagraphStyle("center", parent=body, alignment=TA_CENTER)
    right = ParagraphStyle("right", parent=body, alignment=TA_RIGHT)
    bold = ParagraphStyle("bold", parent=body, fontName=bold_font)
    bold_center = ParagraphStyle("bold_center", parent=center, fontName=bold_font)

    def p(text, style=body):
        return Paragraph(xml_text(text), style)

    def clause(label, text):
        return Paragraph(f"<b><u>{xml_text(label)}</u></b>{xml_text(text)}", body)

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=letter,
        leftMargin=0.52 * inch,
        rightMargin=0.52 * inch,
        topMargin=0.42 * inch,
        bottomMargin=0.42 * inch,
    )

    payment_table = Table(
        [
            [p("Monto", bold_center), p("Fecha de Pago/ Cancelación", bold_center)],
            [p(f"S/ {context['cancelacion']}", center), p(context["fecha_corta"], center)],
        ],
        colWidths=[1.75 * inch, 1.75 * inch],
    )
    payment_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.6, colors.black),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))

    def signature_table_pdf():
        if FIRMA_LUIS_PATH.exists():
            gerente_firma = [Image(str(FIRMA_LUIS_PATH), width=1.35 * inch, height=0.62 * inch)]
        else:
            gerente_firma = [p("____________________________", center)]
        table = Table(
            [
                [
                    [p("____________________________", center), p("EL/LA DEUDOR/A", bold_center), p(f"D.N.I. {context['dni']}", bold_center)],
                    gerente_firma,
                ],
            ],
            colWidths=[3.0 * inch, 3.0 * inch],
        )
        table.setStyle(TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
            ("FONTSIZE", (0, 0), (-1, -1), 7.4),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ]))
        return table

    story = [
        p("Transacción extrajudicial y Cancelación de Deuda", title),
        p(
            "Conste por el presente documento una Transacción Extrajudicial y Cancelación de Deuda, que celebran "
            "de una parte la Empresa de cobranza _BIZNESCOB, con RUC_20602593640, con domicilio en Enrique Encinas "
            "284 la victoria y representado por el sr(a) LUIS PORTUGUEZ BERROCAL identificado con DNI 10416012, "
            "por encargo de COMPARTAMOS BANCO S.A.,  en adelante COMPARTAMOS, con domicilio en Av. Paseo de la "
            "Republica N° 5895 – Interior 1301, distrito de Mira flores, provincia y departamento de Lima, inscrita "
            "en la Partida Nro. 13777030 del Registro de Personas Jurídicas de la Zona Registral Nro. IX - Sede Lima "
            f"y de otra parte el/la Sr (a) {context['cliente']} identificado con DNI N°.{context['dni']}, con domicilio "
            f"en {context['direccion']}, distrito de {context['distrito']}, a quien en adelante se le denominara  "
            "EL/LA/DEUDOR/A, en los términos y condiciones siguientes:"
        ),
        clause("PRIMERA.- ", f"EL DEUDOR reconoce adeudar a COMPARTAMOS BANCO el crédito {context['operacion']}, cuyo  importe asciende  a la suma total de S/  {context['deuda_total']},  según liquidación a la fecha."),
        clause("SEGUNDA- ", "De conformidad con lo señalado en la cláusula anterior EL DEUDOR se obliga a cancelar a   COMPARTAMOS BANCO la deuda antes descrita de la siguiente manera:"),
        payment_table,
        Spacer(1, 4),
        p("La cancelación de la suma antes detallada está sujeta al pago acordado en el párrafo que antecede."),
        clause("TERCERA .- ", "Sin perjuicio de lo señalado, COMPARTAMOS se reserva el derecho de iniciar, interponer o continuar con las acciones administrativas, legales o judiciales en caso de que el EL/LA/DEUDOR/A incumpla las obligaciones que por el presente documento asume; COMPARTAMOS quedará expedito para su cobro de conformidad con lo estipulado por inciso 8 del artículo 688 del Código Proceso Civil."),
        clause("CUARTA .- ", "Las garantías y/o fianzas solidarias constituidas en respaldo de la obligación antes señalada subsisten en tanto no se cancele totalmente la misma por el monto acordado, por cuanto la suscripción de presente convenio no constituye una novación de la obligación"),
        clause("QUINTA .- ", "El incumplimiento o retraso en el pago del monto señalado en la cláusula segunda, a criterio de COMPARTAMOS, quedarán sin efecto los beneficios (descuentos u otros) otorgados a EL/LA/DEUDOR/A, recalculando los intereses y mora que se hayan generado posteriormente."),
        clause("SÉXTA :  ", "EL/LA/DEUDOR/A ratifica su voluntad expresada en el presente instrumento, dejando constancia que no    ha mediado vicio capaz  de invalidarlo."),
        p(context["fecha_larga"], right),
        Spacer(1, 6),
        signature_table_pdf(),
        Spacer(1, 7),
        p("NOTA DE ABONO", title),
        p("Por el presente documento COMPARTAMOS, concede condonación sobre la deuda de EL/LA/DEUDOR/A, según las condiciones ofrecidas en la en el presente documento."),
        p(f"Sr(a):{context['cliente']} con DNI Nº {context['dni']} por la suma de S/ {context['condonacion']}", bold_center),
        p("EL/LA/DEUDOR/A, acepta el descuento indicado, reduciendo la deuda vigente que se detalla en la presente transacción, la misma que mantiene su validez, si EL/LA/DEUDOR/A cumple todas las condiciones descritas en el documento."),
        p(f"El descuento está sujeto al cumplimiento del pago de: S/ {context['cancelacion']} en las fechas y formas acordadas en la cláusula segunda."),
        Spacer(1, 8),
        signature_table_pdf(),
    ]
    doc.build(story)


def generar_documento(documento_tipo, dni=None, operacion=None, codigo_grupo=None, cod_cre_grupal=None, cancelacion=None, fecha_pago=None, formato="docx"):
    config = DOCUMENT_TYPES.get(documento_tipo)
    if not config:
        raise ValueError("Tipo de documento no soportado.")

    registro = obtener_registro_unico(
        dni=dni,
        operacion=operacion,
        codigo_grupo=codigo_grupo,
        cod_cre_grupal=cod_cre_grupal,
    )

    monto_cancelacion, _ = validar_cancelacion(cancelacion, registro.get("MtoCancelacionCliente"))
    deuda_total = decimal_value(registro.get("DeudaTotal"), Decimal("0"))
    monto_condonacion = max(deuda_total - monto_cancelacion, Decimal("0"))
    hoy = datetime.now(ZoneInfo("America/Lima")).date()
    context = {
        "cliente": limpiar_texto(registro.get("NomCliente")),
        "dni": limpiar_texto(registro.get("NumDocumento")),
        "direccion": limpiar_texto(registro.get("DireccionPrincipal")),
        "distrito": limpiar_texto(registro.get("DistritoPrincipal") or registro.get("Distrito_Principal") or registro.get("Distrito")),
        "operacion": limpiar_texto(registro.get("Operacion")),
        "deuda_total": format_money(deuda_total),
        "cancelacion": format_money(monto_cancelacion),
        "condonacion": format_money(monto_condonacion),
        "fecha_corta": hoy.strftime("%d/%m/%Y"),
        "fecha_larga": fecha_larga_hoy(),
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    formato = str(formato or "docx").lower()
    if formato not in ("docx", "pdf"):
        raise ValueError("Formato no soportado. Selecciona Word o PDF.")

    filename = f"{safe_filename(config['nombre'])}_{safe_filename(context['cliente'])}.{formato}"
    output_path = OUTPUT_DIR / filename

    if formato == "pdf":
        generar_pdf_limpio(output_path, context)
    else:
        generar_docx_limpio(output_path, context)

    return {
        "path": output_path,
        "filename": filename,
        "formato": formato,
        "registro": registro,
    }


def limpiar_documentos_generados(dias=2):
    if not OUTPUT_DIR.exists():
        return

    limite = datetime.now().timestamp() - (dias * 24 * 60 * 60)
    for path in OUTPUT_DIR.glob("*.docx"):
        if path.stat().st_mtime < limite:
            try:
                path.unlink()
            except OSError:
                pass
