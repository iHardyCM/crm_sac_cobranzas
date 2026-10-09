"""
Informes en PDF del Centro de Calidad (diseno 2026-10).

  construir_informe_individual_pdf(payload)  -> una llamada evaluada
  construir_informe_cartera_pdf(payload)     -> exportable del Centro de Calidad

NO CALCULA REGLAS DE NEGOCIO NUEVAS
Reciben el mismo payload que ya armaba la pagina (ia_feedback_vistas.js) y solo
lo presentan. Los numeros salen de ahi: nota vigente, resultado por criterio,
puntos, meta, tendencia por agente (la que calcula la pagina), brechas.
Lo unico que este modulo calcula son agregados simples sobre lo recibido
(promedios, conteos, % en meta), con las mismas definiciones del contrato:

  - nota vigente None  -> "No evaluable": sin nota, fuera de promedios (no es 0).
  - criterio medido    -> CUMPLE o NO_CUMPLE (columna "medido" del payload).
  - cumplimiento       -> siempre con N; con menos de 3 medidas, "base chica".
  - % en meta          -> evaluaciones con nota >= meta, sobre las que tienen nota.

Los PDF anteriores siguen en reporte_calidad_export.py y reporte_cartera_pdf.py
(no se tocaron) por si hay que volver atras.
"""

from __future__ import annotations

from calendar import monthrange
from collections import defaultdict
from datetime import datetime, timedelta
from html import escape
from io import BytesIO
from pathlib import Path
from typing import Dict, List, Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, Flowable, Frame, KeepTogether, PageTemplate,
                                Paragraph, Spacer, Table, TableStyle)

# ----------------------------------------------------------------- diseno
NAVY = colors.HexColor("#0E3159")
BLUE = colors.HexColor("#1265B1")
INK = colors.HexColor("#1B3047")
MUTED = colors.HexColor("#5F7488")
LINE = colors.HexColor("#D5DEE8")
SOFT = colors.HexColor("#F3F6FA")
PALE = colors.HexColor("#E6EEF7")
WHITE = colors.white

ESTADOS = {  # clave -> (texto, fondo, texto)
    "cumple": ("Cumple", "#E3F4E9", "#17633A"),
    "no cumple": ("No cumple", "#FBE2E2", "#A8323C"),
    "parcial": ("Parcial", "#FDF0D9", "#8A5A0B"),
    "requiere revision": ("Requiere revisión", "#FDF0D9", "#8A5A0B"),
    "no evaluable": ("No evaluable", "#ECEFF3", "#4A5B6D"),
    "no aplica": ("No aplica", "#E6EEF7", "#35557A"),
}
META_POR_DEFECTO = 85.0  # contrato Feedback_IA, seccion 8
BASE_CHICA = 3


def _fuentes():
    """Segoe UI si esta (servidor Windows); si no, Helvetica. Siempre 3 variantes."""
    carpeta = Path("C:/Windows/Fonts")
    reg, neg, ita = carpeta / "segoeui.ttf", carpeta / "segoeuib.ttf", carpeta / "segoeuii.ttf"
    if reg.exists() and neg.exists():
        if "CalSegoe" not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont("CalSegoe", str(reg)))
            pdfmetrics.registerFont(TTFont("CalSegoe-Bold", str(neg)))
            pdfmetrics.registerFont(TTFont("CalSegoe-Italic", str(ita if ita.exists() else reg)))
        return "CalSegoe", "CalSegoe-Bold", "CalSegoe-Italic"
    return "Helvetica", "Helvetica-Bold", "Helvetica-Oblique"


def _estilo(nombre, fuente, size, color=INK, leading=None, align=0, **kw):
    return ParagraphStyle(nombre, fontName=fuente, fontSize=size, leading=leading or size * 1.28,
                          textColor=color, alignment=align, **kw)


def _txt(valor, vacio="—") -> str:
    t = str(valor if valor is not None else "").strip()
    return t if t and t not in {"-", "—"} else vacio


def _p(valor, estilo, vacio="—"):
    return Paragraph(escape(_txt(valor, vacio)), estilo)


def _num(valor) -> Optional[float]:
    try:
        return float(valor) if valor is not None and valor != "" else None
    except (TypeError, ValueError):
        return None


def _si(valor) -> bool:
    return str(valor or "").strip().casefold() in {"sí", "si", "true", "1"}


def _fecha(valor) -> Optional[datetime]:
    t = str(valor or "").strip()
    if not t:
        return None
    try:
        return datetime.fromisoformat(t.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        pass
    for fmt in ("%d/%m/%Y %I:%M %p", "%d/%m/%Y"):
        try:
            return datetime.strptime(t[:len(datetime.now().strftime(fmt))], fmt)
        except ValueError:
            continue
    try:
        return datetime.strptime(t[:10], "%Y-%m-%d")
    except ValueError:
        return None


def _fecha_hora(valor) -> str:
    f = _fecha(valor)
    if f is None:
        return _txt(valor)
    return f.strftime("%d/%m/%Y %I:%M %p") if (f.hour or f.minute) else f.strftime("%d/%m/%Y")


def _clave_estado(resultado) -> str:
    t = str(resultado or "").strip().casefold().replace("ó", "o")
    if "no evaluable" in t:
        return "no evaluable"
    if "no aplica" in t:
        return "no aplica"
    if "revisi" in t:
        return "requiere revision"
    if "no cumple" in t:
        return "no cumple"
    if "parcial" in t:
        return "parcial"
    if "cumple" in t:
        return "cumple"
    return "requiere revision"


def _color_nota(nota: Optional[float], meta: Optional[float]):
    """Mismo criterio de colores que el Excel: >= meta verde, 70..meta ambar, resto rojo."""
    if nota is None:
        return colors.HexColor("#4A5B6D")
    if meta is None:
        return NAVY
    if nota >= meta:
        return colors.HexColor("#17633A")
    if nota >= 70:
        return colors.HexColor("#8A5A0B")
    return colors.HexColor("#A8323C")


def _recortar(texto: str, limite: int) -> str:
    t = " ".join(str(texto or "").split())
    if len(t) <= limite:
        return t
    corte = t[:limite].rsplit(" ", 1)[0].rstrip(" ,.;:")
    return corte + "…"


def _sin_repetidos(valores) -> List[str]:
    vistos, salida = set(), []
    for v in valores or []:
        t = " ".join(str(v or "").split())
        if t and t.casefold() not in vistos:
            vistos.add(t.casefold())
            salida.append(t)
    return salida


# --------------------------------------------------------------- flowables
class Pill(Flowable):
    """Etiqueta de resultado con fondo de color."""

    def __init__(self, resultado, fuente, ancho=96, alto=13.5, size=7.2):
        super().__init__()
        clave = _clave_estado(resultado)
        self.texto, self.fondo, self.color = ESTADOS[clave]
        if clave == "parcial" and str(resultado or "").strip():
            self.texto = str(resultado).strip()
        self.fuente, self.size = fuente, size
        self.width, self.height = ancho, alto

    def wrap(self, *_):
        return self.width, self.height

    def draw(self):
        c = self.canv
        c.setFillColor(colors.HexColor(self.fondo))
        c.roundRect(0, 0, self.width, self.height, self.height / 2, stroke=0, fill=1)
        c.setFillColor(colors.HexColor(self.color))
        c.setFont(self.fuente, self.size)
        c.drawCentredString(self.width / 2, self.height / 2 - self.size * 0.35, self.texto)


class Barra(Flowable):
    """Barra de progreso fina (0..1) con marca opcional de meta."""

    def __init__(self, ancho, proporcion, color=BLUE, alto=4, marca=None):
        super().__init__()
        self.width, self.height = ancho, alto
        self.prop = max(0.0, min(1.0, proporcion or 0.0))
        self.color, self.marca = color, marca

    def wrap(self, *_):
        return self.width, self.height

    def draw(self):
        c = self.canv
        c.setFillColor(colors.HexColor("#DDE5ED"))
        c.roundRect(0, 0, self.width, self.height, self.height / 2, stroke=0, fill=1)
        if self.prop > 0:
            c.setFillColor(self.color)
            c.roundRect(0, 0, max(self.height, self.width * self.prop), self.height, self.height / 2, stroke=0, fill=1)
        if self.marca is not None:
            x = self.width * self.marca
            c.setStrokeColor(NAVY)
            c.setLineWidth(1)
            c.line(x, -1.5, x, self.height + 1.5)


class TarjetaNota(Flowable):
    """Nota final de la llamada, grande, con barra y marca de meta."""

    def __init__(self, nota, meta, fuentes, ancho=210, alto=84, detalle=""):
        super().__init__()
        self.nota, self.meta, self.detalle = nota, meta, detalle
        self.font, self.bold, self.ital = fuentes
        self.width, self.height = ancho, alto

    def wrap(self, *_):
        return self.width, self.height

    def draw(self):
        c, w, h = self.canv, self.width, self.height
        c.setFillColor(WHITE)
        c.setStrokeColor(LINE)
        c.setLineWidth(.8)
        c.roundRect(0, 0, w, h, 8, stroke=1, fill=1)
        c.setFillColor(NAVY)
        c.roundRect(0, h - 19, w, 19, 8, stroke=0, fill=1)
        c.rect(0, h - 19, w, 9, stroke=0, fill=1)
        c.setFillColor(WHITE)
        c.setFont(self.bold, 7.2)
        c.drawString(12, h - 13, "NOTA FINAL DE LA LLAMADA")
        c.setFont(self.font, 6.6)
        c.drawRightString(w - 12, h - 13, "Resultado vigente")
        color = _color_nota(self.nota, self.meta)
        c.setFillColor(color)
        if self.nota is None:
            c.setFont(self.bold, 21)
            c.drawCentredString(w / 2, h - 50, "No evaluable")
            c.setFillColor(MUTED)
            c.setFont(self.font, 6.8)
            c.drawCentredString(w / 2, h - 63, self.detalle or "Sin nota: no entra en promedios")
            return
        c.setFont(self.bold, 32)
        txt = f"{self.nota:.1f}"
        c.drawString(14, h - 56, txt)
        ancho_txt = pdfmetrics.stringWidth(txt, self.bold, 32)
        c.setFillColor(MUTED)
        c.setFont(self.font, 12)
        c.drawString(14 + ancho_txt + 4, h - 56, "/ 100")
        if self.meta is not None:
            c.setFillColor(MUTED)
            c.setFont(self.font, 6.8)
            delta = self.nota - self.meta
            c.drawRightString(w - 12, h - 40, f"Meta {self.meta:g}")
            c.setFillColor(color)
            c.setFont(self.bold, 7.4)
            c.drawRightString(w - 12, h - 51, f"{delta:+.1f} pts vs meta")
        c.saveState()
        c.translate(12, 11)
        b = Barra(w - 24, self.nota / 100, color, 5, None if self.meta is None else self.meta / 100)
        b.canv = c
        b.draw()
        c.restoreState()


class Firma(Flowable):
    """Linea de firma y de fecha dibujadas (no guiones bajos de texto)."""

    def __init__(self, etiqueta, ancho, fuentes):
        super().__init__()
        self.etiqueta, self.font = etiqueta, fuentes[0]
        self.width, self.height = ancho, 30

    def wrap(self, *_):
        return self.width, self.height

    def draw(self):
        c, w = self.canv, self.width
        c.setStrokeColor(MUTED)
        c.setLineWidth(.6)
        corte = w * .64
        c.line(0, 14, corte - 8, 14)
        c.line(corte, 14, w, 14)
        c.setFillColor(MUTED)
        c.setFont(self.font, 6.6)
        c.drawString(0, 5, f"{self.etiqueta} · Firma")
        c.drawString(corte, 5, "Fecha")


def _tarjeta(titulo, cuerpo, ancho, fuentes, acento=NAVY, detalle=""):
    """Tarjeta con cabecera de color. 'cuerpo' es una lista de flowables."""
    font, bold, _ = fuentes
    st = _estilo("tj-h", bold, 7.4, WHITE)
    st_d = _estilo("tj-d", font, 7, WHITE, align=2)
    cab = [Paragraph(escape(titulo.upper()), st), Paragraph(escape(detalle), st_d) if detalle else ""]
    t = Table([cab, [cuerpo, ""]], colWidths=[ancho * .68, ancho * .32])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), acento),
        ("SPAN", (0, 1), (-1, 1)),
        ("BOX", (0, 0), (-1, -1), .7, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, 0), 4.5), ("BOTTOMPADDING", (0, 0), (-1, 0), 4.5),
        ("TOPPADDING", (0, 1), (-1, 1), 5), ("BOTTOMPADDING", (0, 1), (-1, 1), 5),
    ]))
    return t


def _pie(canvas, doc, fuentes, titulo):
    font = fuentes[0]
    w, h = doc.pagesize
    canvas.saveState()
    canvas.setFillColor(NAVY)
    canvas.rect(0, h - 6, w, 6, stroke=0, fill=1)
    canvas.setFillColor(BLUE)
    canvas.rect(0, h - 6, 90, 6, stroke=0, fill=1)
    canvas.setStrokeColor(LINE)
    canvas.setLineWidth(.5)
    canvas.line(26, 24, w - 26, 24)
    canvas.setFont(font, 6.8)
    canvas.setFillColor(MUTED)
    canvas.drawString(26, 13, f"Biznescob · Centro de Calidad · {titulo}")
    canvas.drawRightString(w - 26, 13, f"Emitido {datetime.now():%d/%m/%Y %H:%M} · Página {doc.page}")
    canvas.restoreState()


def _documento(titulo_pdf, fuentes, titulo_pie):
    salida = BytesIO()
    W, H = landscape(A4)
    doc = BaseDocTemplate(salida, pagesize=(W, H), leftMargin=26, rightMargin=26, topMargin=24,
                          bottomMargin=32, title=titulo_pdf, author="Biznescob · Centro de Calidad")
    marco = Frame(26, 32, W - 52, H - 24 - 32, leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    doc.addPageTemplates([PageTemplate(id="p", frames=[marco], pagesize=(W, H),
                                       onPage=lambda c, d: _pie(c, d, fuentes, titulo_pie))])
    return doc, salida, W - 52


# ============================================================ INDIVIDUAL
def _bloques(criterios):
    bloques: Dict[str, List[Dict]] = {}
    for c in criterios or []:
        nombre = _txt(c.get("bloque_nombre") or c.get("bloque"), "Criterios evaluados")
        bloques.setdefault(nombre, []).append(c)
    return list(bloques.items())


def _armar_individual(payload: Dict, nivel: int):
    """Arma el informe. nivel 0 = comodo; 1 y 2 = mas compacto (todo en UNA hoja)."""
    fuentes = _fuentes()
    font, bold, ital = fuentes
    doc, salida, CW = _documento("Informe de evaluación de llamada", fuentes, "Informe de evaluación de llamada")

    criterios = payload.get("criterios") or []
    meta_llamada = payload.get("meta") or {}
    nota = _num(payload.get("score_vigente"))
    meta_cal = _num(payload.get("meta_calidad")) or META_POR_DEFECTO
    pad = (2.4, 1.8, 1.3)[nivel]            # relleno vertical de cada fila de criterio
    tam = (8.0, 7.7, 7.4)[nivel]            # tamano de texto de tablas
    max_ev = (150, 100, 70)[nivel]          # largo de la cita de evidencia

    s_eyebrow = _estilo("eb", bold, 7.4, BLUE, 9)
    s_titulo = _estilo("ti", bold, 21, NAVY, 24)
    s_sub = _estilo("su", font, 8.6, MUTED, 11)
    s_label = _estilo("lb", bold, 6.4, MUTED, 8)
    s_valor = _estilo("vl", bold, 9.6, NAVY, 12)
    s_cuerpo = _estilo("cu", font, tam + .6, INK, (tam + .6) * 1.3)
    s_peq = _estilo("pq", font, tam, INK, tam * 1.3)
    s_pts = _estilo("pt", bold, tam, INK, tam * 1.25, align=2)
    s_ev = _estilo("ev", ital, tam - .8, MUTED, (tam - .8) * 1.28)
    s_sec = _estilo("se", bold, 10.5, NAVY, 13)

    cuenta = defaultdict(int)
    for c in criterios:
        cuenta[_clave_estado(c.get("resultado"))] += 1
    detalle_sin_nota = ""
    if nota is None and criterios:
        partes = [f"{cuenta[k]} {n}" for k, n in (("requiere revision", "requieren revisión"),
                                                 ("no evaluable", "no evaluables"), ("no aplica", "no aplican")) if cuenta[k]]
        detalle_sin_nota = "Ningún criterio pudo medirse" + (f" ({', '.join(partes)})" if partes else "")

    # --- cabecera: titulo + datos a la izquierda, nota a la derecha
    ancho_izq = CW - 222
    chips = Table([[
        [Paragraph("AGENTE", s_label), Paragraph(escape(_txt(meta_llamada.get("agente"))), s_valor)],
        [Paragraph("CARTERA", s_label), Paragraph(escape(_txt(meta_llamada.get("cartera"))), s_valor)],
        [Paragraph("FECHA Y HORA", s_label), Paragraph(escape(_fecha_hora(meta_llamada.get("fecha"))), s_valor)],
    ]], colWidths=[ancho_izq * .44, ancho_izq * .28, ancho_izq * .28])
    chips.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), SOFT), ("BOX", (0, 0), (-1, -1), .6, LINE),
                               ("LINEAFTER", (0, 0), (-2, -1), .6, LINE), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                               ("LEFTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 4),
                               ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
    izquierda = [Paragraph("CENTRO DE CALIDAD", s_eyebrow), Spacer(1, 1),
                 Paragraph("Informe de evaluación de llamada", s_titulo), Spacer(1, 1),
                 Paragraph("Resultado vigente de la llamada · pauta aplicada a la cartera", s_sub), Spacer(1, 6), chips]
    cab = Table([[izquierda, TarjetaNota(nota, meta_cal, fuentes, 214, 84, "Sin nota en esta llamada")]],
                colWidths=[ancho_izq + 0, 222])
    cab.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                             ("RIGHTPADDING", (0, 0), (0, 0), 8), ("RIGHTPADDING", (1, 0), (1, 0), 0),
                             ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                             ("ALIGN", (1, 0), (1, 0), "RIGHT")]))
    historia: List[Flowable] = [cab, Spacer(1, 7)]

    if nota is None:
        aviso = Table([[Paragraph(
            "<b>Esta llamada no tiene nota.</b> " + escape(detalle_sin_nota or "No hay criterios medidos") +
            ". No es un 0: queda fuera de los promedios.", s_peq)]], colWidths=[CW])
        aviso.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FDF0D9")),
                                   ("LINEBEFORE", (0, 0), (0, -1), 3, colors.HexColor("#D9901A")),
                                   ("LEFTPADDING", (0, 0), (-1, -1), 10), ("TOPPADDING", (0, 0), (-1, -1), 4),
                                   ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
        historia += [aviso, Spacer(1, 6)]

    resumen = Table([[[Paragraph("RESUMEN DE LA LLAMADA", s_label), Spacer(1, 2),
                       _p(payload.get("resumen"), s_cuerpo, "Sin resumen registrado.")]]], colWidths=[CW])
    resumen.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), WHITE), ("BOX", (0, 0), (-1, -1), .6, LINE),
                                 ("LINEBEFORE", (0, 0), (0, -1), 3, BLUE), ("LEFTPADDING", (0, 0), (-1, -1), 10),
                                 ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    historia += [resumen, Spacer(1, 7), Paragraph("Criterios de evaluación", s_sec), Spacer(1, 3)]

    # --- bloques de criterios (2 por fila)
    ancho_card = (CW - 12) / 2
    w_pts, w_pill = 46, 92
    w_nom = ancho_card - w_pts - w_pill - 16
    tarjetas = []
    for nombre, filas in _bloques(criterios):
        puntos = sum(float(f.get("nota") or 0) for f in filas if f.get("nota") is not None)
        peso = sum(float(f.get("peso") or 0) for f in filas)
        filas_tabla = []
        for f in filas:
            n, p = _num(f.get("nota")), _num(f.get("peso"))
            pts = "—" if n is None else f"{n:g} / {p:g}" if p is not None else f"{n:g}"
            filas_tabla.append([_p(f.get("criterio"), s_peq), Paragraph(escape(pts), s_pts), Pill(f.get("resultado"), bold, w_pill - 2)])
        cuerpo = Table(filas_tabla, colWidths=[w_nom, w_pts, w_pill])
        cuerpo.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LINEBELOW", (0, 0), (-1, -2), .4, PALE),
                                    ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                                    ("TOPPADDING", (0, 0), (-1, -1), pad), ("BOTTOMPADDING", (0, 0), (-1, -1), pad)]))
        prop = (puntos / peso) if peso else 0
        barra = Barra(ancho_card - 16, prop, _color_nota(prop * 100, meta_cal), 3.2)
        tarjetas.append(_tarjeta(nombre, [barra, Spacer(1, 3), cuerpo], ancho_card, fuentes,
                                 detalle=f"{puntos:g} de {peso:g} pts"))
    if not tarjetas:
        historia.append(Table([[Paragraph("Esta evaluación no tiene criterios registrados.", s_peq)]], colWidths=[CW],
                              style=[("BOX", (0, 0), (-1, -1), .6, LINE), ("TOPPADDING", (0, 0), (-1, -1), 8),
                                     ("BOTTOMPADDING", (0, 0), (-1, -1), 8), ("LEFTPADDING", (0, 0), (-1, -1), 10)]))
    for i in range(0, len(tarjetas), 2):
        par = tarjetas[i:i + 2]
        while len(par) < 2:
            par.append("")
        fila = Table([[par[0], "", par[1]]], colWidths=[ancho_card, 12, ancho_card])
        fila.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                                  ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 0),
                                  ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
        historia += [fila, Spacer(1, 6)]

    # --- fortalezas | brechas | feedback (tres columnas)
    ancho3 = (CW - 24) / 3
    fortalezas = _sin_repetidos(payload.get("fortalezas"))
    fort_flow = [Paragraph("• " + escape(f), s_peq) for f in fortalezas] or [Paragraph("Sin fortaleza registrada.", s_peq)]
    brechas_flow: List[Flowable] = []
    for c in [x for x in criterios if x.get("brecha")]:
        brechas_flow.append(Paragraph(f"• <b>{escape(_txt(c.get('criterio')))}</b> · {escape(_txt(c.get('resultado')))}", s_peq))
        ev = _txt(c.get("evidencia"), "")
        if ev:
            brechas_flow.append(Paragraph("“" + escape(_recortar(ev, max_ev)) + "”", ParagraphStyle("ev2", parent=s_ev, leftIndent=8)))
    if not brechas_flow:
        previas = _sin_repetidos(payload.get("brechas"))
        brechas_flow = [Paragraph("• " + escape(_recortar(b, 200)), s_peq) for b in previas] or [Paragraph("Sin brecha registrada.", s_peq)]
    fb_flow = [_p(payload.get("feedback"), s_peq, "Sin feedback registrado.")]
    fila3 = Table([[_tarjeta("Fortalezas observadas", fort_flow, ancho3, fuentes, colors.HexColor("#17633A")), "",
                    _tarjeta("Brechas y recomendación", brechas_flow, ancho3, fuentes, colors.HexColor("#A8323C")), "",
                    _tarjeta("Feedback del evaluador", fb_flow, ancho3, fuentes, BLUE)]],
                  colWidths=[ancho3, 12, ancho3, 12, ancho3])
    fila3.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                               ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 0),
                               ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
    historia += [fila3, Spacer(1, 6)]

    # --- compromiso del agente + firmas, en una franja
    ancho_texto = CW * .27
    ancho_firma = (CW - ancho_texto - 20 - 30) / 3
    franja = Table([[[Paragraph("COMPROMISO DEL AGENTE", s_label), Spacer(1, 2),
                      _p(payload.get("compromiso"), s_peq, "Pendiente de registrar con el agente.")],
                     Firma("Calidad", ancho_firma, fuentes),
                     Firma("Jefatura de cartera (Lourdes)", ancho_firma, fuentes),
                     Firma("Agente", ancho_firma, fuentes)]],
                   colWidths=[ancho_texto + 20, ancho_firma + 10, ancho_firma + 10, ancho_firma + 10])
    franja.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), .6, LINE), ("LINEBEFORE", (0, 0), (0, -1), 3, BLUE),
                                ("BACKGROUND", (0, 0), (-1, -1), SOFT), ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
                                ("LEFTPADDING", (0, 0), (0, -1), 10), ("LEFTPADDING", (1, 0), (-1, -1), 6),
                                ("RIGHTPADDING", (0, 0), (-1, -1), 4), ("TOPPADDING", (0, 0), (-1, -1), 6),
                                ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
    historia.append(franja)
    return doc, salida, historia, CW


def construir_informe_individual_pdf(payload: Dict) -> bytes:
    """Informe de UNA llamada, siempre en UNA hoja.

    Intenta primero con espaciado comodo y, si no cabe, lo va compactando. Si aun
    asi no cabe (muchas brechas con textos largos), reduce la escala del contenido
    en vez de pasar a una segunda hoja.
    """
    from reportlab.platypus import KeepInFrame
    from reportlab.platypus.doctemplate import LayoutError
    for nivel in (0, 1, 2):
        doc, salida, historia, CW = _armar_individual(payload, nivel)
        try:
            doc.build(historia)
        except LayoutError:
            continue  # un bloque no cabe ni solo en la hoja: probar mas compacto / reducir
        if doc.page == 1:
            return salida.getvalue()
    doc, salida, historia, CW = _armar_individual(payload, 2)
    alto = doc.pagesize[1] - 24 - 32
    doc.build([KeepInFrame(CW, alto, historia, mode="shrink")])
    return salida.getvalue()


# ============================================================== CARTERA
def _semana_del_mes(dia):
    """Semanas de domingo a sabado acotadas al mes (misma regla que el PDF anterior)."""
    primero = dia.replace(day=1)
    domingo = dia - timedelta(days=(dia.weekday() + 1) % 7)
    ultimo = dia.replace(day=monthrange(dia.year, dia.month)[1])
    numero = 1 + (dia.day + (primero.weekday() + 1) % 7 - 1) // 7
    return (dia.year, dia.month, numero), max(primero, domingo), min(ultimo, domingo + timedelta(days=6))


def _modelo_cartera(payload: Dict) -> Dict:
    evals = payload.get("evaluaciones") or []
    crits = payload.get("criterios") or []
    notas = [n for n in (_num(e.get("nota")) for e in evals) if n is not None]
    meta = _num(payload.get("meta"))
    carteras = sorted({str(e.get("cartera")).strip() for e in evals if e.get("cartera")})
    promedio = sum(notas) / len(notas) if notas else None

    por_semana, por_agente = defaultdict(list), defaultdict(list)
    for e in evals:
        por_agente[str(e.get("agente") or "Sin agente").strip()].append(e)
        f = _fecha(e.get("fecha"))
        if f:
            por_semana[_semana_del_mes(f.date())[0]].append(e)
    varios_meses = len({k[:2] for k in por_semana}) > 1
    semanas = []
    for k, filas in sorted(por_semana.items()):
        ns = [n for n in (_num(r.get("nota")) for r in filas) if n is not None]
        _, ini, fin = _semana_del_mes(_fecha(filas[0].get("fecha")).date())
        semanas.append({"etiqueta": f"{k[1]:02d} · S{k[2]}" if varios_meses else f"Sem. {k[2]}",
                        "rango": f"{ini:%d/%m}–{fin:%d/%m}", "prom": sum(ns) / len(ns) if ns else None, "n": len(filas)})

    info_agente = {str(a.get("agente") or "").strip(): a for a in (payload.get("agentes") or [])}
    agentes = []
    for nombre, filas in por_agente.items():
        ns = [n for n in (_num(r.get("nota")) for r in filas) if n is not None]
        info = info_agente.get(nombre, {})
        agentes.append({"nombre": nombre, "n": len(filas), "con_nota": len(ns),
                        "prom": sum(ns) / len(ns) if ns else None,
                        "tendencia": _num(info.get("tendencia")),
                        "criterio": str(info.get("brecha_repite") or "").strip() or "Sin recurrencia identificada"})
    agentes.sort(key=lambda a: (a["prom"] is None, a["prom"] if a["prom"] is not None else 0, a["nombre"]))

    por_crit = defaultdict(lambda: {"medidas": 0, "brechas": 0})
    medidos = 0
    for r in crits:
        nombre = str(r.get("criterio") or "").strip()
        if not nombre:
            continue
        if _si(r.get("medido")):
            por_crit[nombre]["medidas"] += 1
            medidos += 1
            if _si(r.get("brecha")):
                por_crit[nombre]["brechas"] += 1
    ranking = [{"nombre": n, **v, "tasa": 100 * v["brechas"] / v["medidas"]} for n, v in por_crit.items() if v["medidas"]]
    ranking.sort(key=lambda r: (-r["tasa"], -r["brechas"], r["nombre"]))

    return {
        "cartera": carteras[0] if len(carteras) == 1 else "Carteras seleccionadas" if carteras else "—",
        "periodo": str(payload.get("periodo") or "Periodo no indicado"),
        "emite": str(payload.get("generado_por") or "").strip(),
        "filtros": payload.get("filtros") or [],
        "n": len(evals), "con_nota": len(notas), "sin_nota": len(evals) - len(notas),
        "promedio": promedio, "meta": meta,
        "en_meta": sum(1 for n in notas if meta is not None and n >= meta),
        "criticos": sum(_si(e.get("error_critico")) for e in evals),
        "cobertura": 100 * medidos / len(crits) if crits else None,
        "semanas": semanas, "agentes": agentes, "ranking": ranking,
        "foco": payload.get("foco") or {},
        "recomendacion": str(payload.get("recomendacion") or "").strip(),
    }


class Kpis(Flowable):
    def __init__(self, items, ancho, fuentes, alto=62):
        super().__init__()
        self.items, self.font, self.bold = items, fuentes[0], fuentes[1]
        self.width, self.height = ancho, alto

    def wrap(self, *_):
        return self.width, self.height

    def draw(self):
        c = self.canv
        n = len(self.items)
        gap = 8
        w = (self.width - gap * (n - 1)) / n
        for i, (valor, etiqueta, detalle, color) in enumerate(self.items):
            x = i * (w + gap)
            c.setFillColor(SOFT)
            c.setStrokeColor(LINE)
            c.setLineWidth(.6)
            c.roundRect(x, 0, w, self.height, 7, stroke=1, fill=1)
            c.setFillColor(color)
            c.roundRect(x, 10, 3, self.height - 20, 1.5, stroke=0, fill=1)
            c.setFont(self.bold, 22)
            c.drawString(x + 14, self.height - 29, valor)
            c.setFillColor(NAVY)
            c.setFont(self.bold, 8.2)
            c.drawString(x + 14, self.height - 41, etiqueta)
            c.setFillColor(MUTED)
            c.setFont(self.font, 6.6)
            c.drawString(x + 14, self.height - 52, _recortar(detalle, int(w / 3.1)))


class Evolucion(Flowable):
    """Linea de nota promedio por semana, con la meta como referencia."""

    def __init__(self, semanas, meta, ancho, alto, fuentes):
        super().__init__()
        self.semanas, self.meta = semanas, meta
        self.font, self.bold = fuentes[0], fuentes[1]
        self.width, self.height = ancho, alto

    def wrap(self, *_):
        return self.width, self.height

    def draw(self):
        c, W, H = self.canv, self.width, self.height
        con = [s["prom"] for s in self.semanas if s["prom"] is not None]
        if not con:
            c.setFillColor(MUTED)
            c.setFont(self.font, 8.5)
            c.drawString(0, H / 2, "Sin notas semanales para graficar.")
            return
        izq, der, abajo, arriba = 28, W - 14, 26, H - 8
        bajo = max(0, min(60, (int(min(con + ([self.meta] if self.meta else [])) // 10) - 1) * 10))
        def y(v):
            return abajo + (arriba - abajo) * (v - bajo) / (100 - bajo)
        for tick in range(bajo, 101, 10):
            c.setStrokeColor(PALE)
            c.setLineWidth(.5)
            c.line(izq, y(tick), der, y(tick))
            c.setFillColor(MUTED)
            c.setFont(self.font, 6.4)
            c.drawRightString(izq - 5, y(tick) - 2, str(tick))
        if self.meta is not None and bajo <= self.meta <= 100:
            c.setStrokeColor(colors.HexColor("#17633A"))
            c.setLineWidth(.9)
            c.setDash(3, 3)
            c.line(izq, y(self.meta), der, y(self.meta))
            c.setDash()
            c.setFillColor(colors.HexColor("#17633A"))
            c.setFont(self.bold, 6.6)
            c.drawRightString(der, y(self.meta) + 3, f"Meta {self.meta:g}")
        n = len(self.semanas)
        margen = 22
        pts = []
        for i, s in enumerate(self.semanas):
            x = izq + margen + (der - izq - 2 * margen) * (i / (n - 1) if n > 1 else .5)
            c.setFillColor(MUTED)
            c.setFont(self.font, 6.4)
            c.drawCentredString(x, abajo - 11, s["etiqueta"])
            c.drawCentredString(x, abajo - 19, s["rango"])
            if s["prom"] is not None:
                pts.append((x, y(s["prom"]), s["prom"], s["n"]))
        if len(pts) > 1:
            path = c.beginPath()
            path.moveTo(pts[0][0], abajo)
            for x, yy, *_ in pts:
                path.lineTo(x, yy)
            path.lineTo(pts[-1][0], abajo)
            path.close()
            c.setFillColor(colors.Color(0.07, 0.40, 0.69, alpha=.10))
            c.drawPath(path, stroke=0, fill=1)
        c.setStrokeColor(BLUE)
        c.setLineWidth(2)
        for a, b in zip(pts, pts[1:]):
            c.line(a[0], a[1], b[0], b[1])
        for x, yy, v, cnt in pts:
            c.setFillColor(WHITE)
            c.setStrokeColor(BLUE)
            c.setLineWidth(1.6)
            c.circle(x, yy, 3, stroke=1, fill=1)
            c.setFillColor(NAVY)
            c.setFont(self.bold, 7.6)
            c.drawCentredString(x, yy + 8, f"{v:.1f}")


class Brechas(Flowable):
    """Ranking de criterios por % de falla, con N siempre visible."""

    def __init__(self, ranking, ancho, fuentes, maximo=5, fila=27):
        super().__init__()
        self.rank, self.font, self.bold = ranking[:maximo], fuentes[0], fuentes[1]
        self.fila = fila
        self.width, self.height = ancho, max(fila * max(len(self.rank), 1), fila)

    def wrap(self, *_):
        return self.width, self.height

    def draw(self):
        c = self.canv
        if not self.rank:
            c.setFillColor(MUTED)
            c.setFont(self.font, 8.5)
            c.drawString(0, self.height - 14, "Sin brechas en los criterios medidos.")
            return
        for i, r in enumerate(self.rank):
            top = self.height - i * self.fila
            c.setFillColor(INK)
            c.setFont(self.bold, 7.8)
            nombre = r["nombre"]
            while pdfmetrics.stringWidth(nombre, self.bold, 7.8) > self.width - 58 and len(nombre) > 8:
                nombre = nombre[:-2]
            c.drawString(0, top - 9, nombre + ("…" if nombre != r["nombre"] else ""))
            c.setFont(self.bold, 8.6)
            c.setFillColor(colors.HexColor("#A8323C") if r["tasa"] >= 50 else NAVY)
            c.drawRightString(self.width, top - 9, f"{r['tasa']:.0f}%")
            c.setFillColor(colors.HexColor("#DDE5ED"))
            c.roundRect(0, top - 17, self.width, 4, 2, stroke=0, fill=1)
            c.setFillColor(colors.HexColor("#A8323C") if r["tasa"] >= 50 else BLUE)
            c.roundRect(0, top - 17, max(4, self.width * min(r["tasa"], 100) / 100), 4, 2, stroke=0, fill=1)
            c.setFillColor(MUTED)
            c.setFont(self.font, 6.5)
            base = "  ·  base chica" if r["medidas"] < BASE_CHICA else ""
            c.drawString(0, top - 25, f"falla en {r['brechas']} de {r['medidas']} mediciones{base}")


def _estado_agente(prom, meta):
    if prom is None:
        return "no evaluable", "Sin nota"
    if meta is None:
        return "no aplica", "Sin meta"
    return ("cumple", "En rango") if prom >= meta else ("parcial", "En seguimiento")


def construir_informe_cartera_pdf(payload: Dict) -> bytes:
    fuentes = _fuentes()
    font, bold, ital = fuentes
    m = _modelo_cartera(payload)
    doc, salida, CW = _documento("Informe ejecutivo de calidad", fuentes, "Informe ejecutivo de calidad")
    meta = m["meta"]

    s_eb = _estilo("eb", bold, 7.4, BLUE, 9)
    s_ti = _estilo("ti", bold, 24, NAVY, 28)
    s_lb = _estilo("lb", bold, 6.6, MUTED, 8)
    s_vl = _estilo("vl", bold, 9.6, NAVY, 12)
    s_sec = _estilo("se", bold, 11.5, NAVY, 14)
    s_sub = _estilo("su", font, 7.6, MUTED, 10)
    s_cu = _estilo("cu", font, 8.8, INK, 12.2)
    s_pq = _estilo("pq", font, 7.8, INK, 10)
    s_th = _estilo("th", bold, 7.2, NAVY, 9)
    s_thc = _estilo("thc", bold, 7.2, NAVY, 9, align=1)
    s_td = _estilo("td", font, 8, INK, 10.2)
    s_tdc = _estilo("tdc", font, 8, INK, 10.2, align=1)

    def sec(titulo, sub):
        return [Paragraph(escape(titulo), s_sec), Paragraph(escape(sub), s_sub), Spacer(1, 5)]

    # ---------- pagina 1: lectura ejecutiva
    cab = Table([[[Paragraph("CENTRO DE CALIDAD", s_eb), Spacer(1, 2),
                   Paragraph("Informe ejecutivo de calidad", s_ti)]]], colWidths=[CW])
    cab.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 0),
                             ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
    datos = [("CARTERA", m["cartera"]), ("PERIODO", m["periodo"]), ("MUESTRA", f"{m['n']} evaluaciones"),
             ("EMISIÓN", datetime.now().strftime("%d/%m/%Y") + (f" · {m['emite']}" if m["emite"] else ""))]
    pesos = [.31, .27, .17, .25]
    chips = Table([[[Paragraph(t, s_lb), Paragraph(escape(_txt(v)), s_vl)] for t, v in datos]], colWidths=[CW * p for p in pesos])
    chips.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), SOFT), ("BOX", (0, 0), (-1, -1), .6, LINE),
                               ("LINEAFTER", (0, 0), (-2, -1), .6, LINE), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                               ("LEFTPADDING", (0, 0), (-1, -1), 10), ("TOPPADDING", (0, 0), (-1, -1), 6),
                               ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    historia: List[Flowable] = [cab, Spacer(1, 7), chips, Spacer(1, 9)]
    if m["filtros"]:
        txt = " · ".join(f"{escape(str(a))}: {escape(str(b))}" for a, b in m["filtros"] if a)
        historia += [Paragraph("<b>Filtros aplicados:</b> " + txt, s_sub), Spacer(1, 6)]

    prom = m["promedio"]
    pct_meta = None if (meta is None or not m["con_nota"]) else 100 * m["en_meta"] / m["con_nota"]
    kpis = [
        (str(m["n"]), "Evaluaciones", f"de {len(m['agentes'])} agentes", BLUE),
        ("—" if prom is None else f"{prom:.1f}", "Nota promedio",
         "Sin meta configurada" if meta is None or prom is None else f"{prom - meta:+.1f} pts vs meta {meta:g}", _color_nota(prom, meta)),
        ("—" if pct_meta is None else f"{pct_meta:.0f}%", "En meta",
         "Sin meta configurada" if pct_meta is None else f"{m['en_meta']} de {m['con_nota']} con nota", colors.HexColor("#17633A")),
        (str(m["sin_nota"]), "Sin nota", "No evaluables · fuera de promedios", colors.HexColor("#8A5A0B")),
        (str(m["criticos"]), "Con error crítico", "Indicador en revisión (no distingue gravedad)", colors.HexColor("#A8323C")),
    ]
    historia += [Kpis(kpis, CW, fuentes, 62), Spacer(1, 12)]

    mitad_izq, mitad_der = CW * .56, CW * .44 - 22
    izq = sec("Evolución de la nota promedio", "Semanas de domingo a sábado, acotadas al mes.") + \
        [Evolucion(m["semanas"], meta, mitad_izq, 178, fuentes)]
    der = sec("Criterios que requieren atención", "Mayor % de incumplimiento sobre lo medido.") + [Brechas(m["ranking"], mitad_der, fuentes, 5, 33)]
    cuerpo = Table([[izq, "", der]], colWidths=[mitad_izq, 22, mitad_der])
    cuerpo.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                                ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 0),
                                ("BOTTOMPADDING", (0, 0), (-1, -1), 0), ("LINEAFTER", (0, 0), (0, 0), .5, LINE)]))
    historia += [cuerpo, Spacer(1, 12)]

    # lectura del periodo + plan de accion
    notas = []
    if prom is not None:
        notas.append(f"La nota promedio fue <b>{prom:.1f}</b> de 100" +
                     (f", {abs(prom - meta):.1f} puntos {'sobre' if prom >= meta else 'bajo'} la meta de {meta:g}." if meta is not None else "."))
    validas = [s for s in m["semanas"] if s["prom"] is not None]
    if len(validas) >= 2:
        d = validas[-1]["prom"] - validas[-2]["prom"]
        notas.append(f"La última semana {'mejoró' if d >= 0 else 'bajó'} <b>{abs(d):.1f} puntos</b> frente a la anterior.")
    if m["ranking"]:
        r = m["ranking"][0]
        notas.append(f"<b>{escape(r['nombre'])}</b> es el principal foco: {r['brechas']} de {r['medidas']} mediciones con brecha ({r['tasa']:.0f}%).")
    if m["sin_nota"]:
        notas.append(f"{m['sin_nota']} evaluaciones no tienen nota (no evaluables) y no entran en el promedio.")
    if not notas:
        notas = ["No hay notas evaluables en el periodo."]
    lectura = [Paragraph(f"<font color='#1265B1'><b>{i + 1}</b></font>&nbsp;&nbsp;{t}", s_cu) for i, t in enumerate(notas[:4])]
    lectura = [x for p in lectura for x in (p, Spacer(1, 3))]
    foco = m["ranking"][0]["nombre"] if m["ranking"] else "Sin brechas medidas"
    plan = [Paragraph("PLAN DE ACCIÓN", _estilo("pa", bold, 7.4, BLUE, 9)), Spacer(1, 3),
            Paragraph(f"<b>Foco:</b> {escape(foco)}", s_cu), Spacer(1, 2),
            Paragraph("<b>Acción sugerida:</b> " + escape(m["recomendacion"] or "Coaching y seguimiento semanal."), s_cu)]
    ancho_l = CW * .58
    fila = Table([[[Paragraph("LECTURA DEL PERIODO", _estilo("lp", bold, 7.4, BLUE, 9)), Spacer(1, 3)] + lectura, "", plan]],
                 colWidths=[ancho_l, 14, CW - ancho_l - 14])
    fila.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("BACKGROUND", (2, 0), (2, 0), SOFT),
                              ("BOX", (2, 0), (2, 0), .6, LINE), ("LINEBEFORE", (2, 0), (2, 0), 3, BLUE),
                              ("LEFTPADDING", (0, 0), (0, 0), 0), ("LEFTPADDING", (2, 0), (2, 0), 12),
                              ("RIGHTPADDING", (2, 0), (2, 0), 12), ("TOPPADDING", (0, 0), (-1, -1), 6),
                              ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    historia.append(KeepTogether([fila]))

    # ---------- anexo: agentes, donde falla mas, definiciones
    from reportlab.platypus import PageBreak
    historia += [PageBreak(), Paragraph("CENTRO DE CALIDAD · ANEXO", s_eb), Spacer(1, 2),
                 Paragraph("Rendimiento por agente", _estilo("t2", bold, 18, NAVY, 22)),
                 Paragraph(escape(f"{m['cartera']} · {m['periodo']}"), s_sub), Spacer(1, 8)]
    cols = [CW * .24, CW * .09, CW * .10, CW * .14, CW * .31, CW * .12]
    filas = [[Paragraph("Agente", s_th), Paragraph("Evaluaciones", s_thc), Paragraph("Promedio", s_thc),
              Paragraph("Tendencia", s_thc), Paragraph("Principal criterio a reforzar", s_th), Paragraph("Estado", s_thc)]]
    estilos_celdas = []
    for i, a in enumerate(m["agentes"], start=1):
        tendencia = "Sin base" if a["tendencia"] is None else f"{a['tendencia']:+.1f} pts"
        t_color = MUTED if a["tendencia"] is None else (colors.HexColor("#17633A") if a["tendencia"] >= 0 else colors.HexColor("#A8323C"))
        clave, texto_estado = _estado_agente(a["prom"], meta)
        _, fondo, tcol = ESTADOS[clave]
        filas.append([
            _p(a["nombre"], s_td),
            Paragraph(str(a["n"]) + ("" if a["con_nota"] == a["n"] else f" <font size='6.4' color='#5F7488'>({a['con_nota']} con nota)</font>"), s_tdc),
            Paragraph(f"<font color='{_color_nota(a['prom'], meta).hexval().replace('0x', '#')}'><b>{'—' if a['prom'] is None else format(a['prom'], '.1f')}</b></font>", s_tdc),
            Paragraph(f"<font color='{t_color.hexval().replace('0x', '#')}'>{tendencia}</font>", s_tdc),
            _p(a["criterio"], s_td),
            Pill(texto_estado if clave != "cumple" else "Cumple", bold, 70, 12.5, 6.8),
        ])
        # El estado se muestra con su propio texto, no con el del resultado de criterio.
        filas[-1][5].texto = texto_estado
        filas[-1][5].fondo, filas[-1][5].color = fondo, tcol
    tabla = Table(filas, colWidths=cols, repeatRows=1)
    tabla.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), PALE), ("LINEBELOW", (0, 0), (-1, 0), .8, NAVY),
        ("LINEBELOW", (0, 1), (-1, -1), .4, LINE), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, colors.HexColor("#F8FAFC")]),
        ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 4.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 4.5),
        ("ALIGN", (5, 1), (5, -1), "CENTER"),
    ] + estilos_celdas))
    historia.append(tabla if len(filas) > 1 else Paragraph("Sin agentes con evaluaciones en el periodo.", s_cu))

    foco_dim = [(t, m["foco"].get(k) or []) for t, k in (("Por cartera", "cartera"), ("Por supervisor", "supervisor"))]
    foco_dim = [(t, v) for t, v in foco_dim if v]
    if foco_dim:
        historia += [Spacer(1, 14)] + sec("Dónde falla más", "Los 3 criterios con mayor % de falla de cada grupo y su diferencia contra el total del periodo.")
        bloques = []
        for titulo, grupos in foco_dim:
            flow = [Paragraph(escape(titulo.upper()), _estilo("fd", bold, 7.4, BLUE, 9)), Spacer(1, 3)]
            for g in grupos[:6]:
                flow.append(Paragraph(f"<b>{escape(_txt(g.get('grupo')))}</b>", s_pq))
                for linea in (g.get("top") or [])[:3]:
                    flow.append(Paragraph("– " + escape(str(linea)), _estilo("fl", font, 7.2, MUTED, 9.2, leftIndent=6)))
                flow.append(Spacer(1, 4))
            bloques.append(flow)
        medio = (CW - 18) / len(bloques)
        grid = Table([bloques[0:1] + [""] + bloques[1:2]] if len(bloques) == 2 else [bloques],
                     colWidths=[medio, 18, medio] if len(bloques) == 2 else [CW])
        grid.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                                  ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 0),
                                  ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
        historia.append(grid)

    cobertura = "" if m["cobertura"] is None else f" De los registros de criterio, el {m['cobertura']:.0f}% fue medible (Cumple o No cumple)."
    historia += [Spacer(1, 14), Table([[Paragraph(
        "<b>Cómo leer este informe.</b> Un criterio cuenta como <b>medido</b> solo si resultó Cumple o No cumple; "
        "No aplica, No evaluable y Requiere revisión no entran en ningún porcentaje. Una evaluación sin nota no es un 0: queda fuera de promedios. "
        f"<b>En meta</b> = evaluaciones con nota ≥ meta sobre las que tienen nota. <b>Tendencia</b> = promedio de las 3 últimas notas del agente "
        f"menos el de las 3 anteriores (sin base si no hay al menos 2 y 2). Con menos de {BASE_CHICA} mediciones se marca «base chica».{cobertura}",
        _estilo("nt", font, 7.3, MUTED, 9.6))]], colWidths=[CW],
        style=[("BACKGROUND", (0, 0), (-1, -1), SOFT), ("BOX", (0, 0), (-1, -1), .6, LINE),
               ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
               ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7)])]
    doc.build(historia)
    return salida.getvalue()
