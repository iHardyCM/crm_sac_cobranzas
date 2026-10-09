"""Informes de calidad en Word (.docx editable), con el mismo diseno que los PDF.

  construir_informe_individual_docx(payload) -> bytes
  construir_informe_cartera_docx(payload)    -> bytes

Reutiliza del PDF las reglas de lectura (estados, colores de nota, modelo de cartera),
asi que ambos formatos muestran exactamente los mismos numeros. Requiere python-docx.
"""
from __future__ import annotations

from datetime import datetime
from io import BytesIO
from typing import Dict, List, Optional

from docx import Document
from docx.enum.section import WD_ORIENT
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

from app.services.reporte_calidad_pdf import (
    BASE_CHICA, ESTADOS, META_POR_DEFECTO, _bloques, _clave_estado, _color_nota, _estado_agente,
    _fecha_hora, _modelo_cartera, _num, _recortar, _sin_repetidos, _txt,
)

NAVY, BLUE, INK, MUTED, LINE = "0E3159", "1265B1", "1B3047", "5F7488", "D5DEE8"
SOFT, PALE = "F3F6FA", "E6EEF7"
VERDE, ROJO, AMBAR, GRIS = "17633A", "A8323C", "8A5A0B", "4A5B6D"
FUENTE = "Segoe UI"


def _hex(color) -> str:
    return color.hexval().replace("0x", "").upper()


# ------------------------------------------------------------------ utilidades
def _nuevo_documento(titulo: str, pie: str) -> Document:
    d = Document()
    s = d.sections[0]
    s.orientation = WD_ORIENT.LANDSCAPE
    s.page_width, s.page_height = Cm(29.7), Cm(21.0)
    s.left_margin = s.right_margin = Cm(1.2)
    s.top_margin, s.bottom_margin = Cm(0.7), Cm(1.1)
    s.footer_distance = Cm(0.4)
    st = d.styles["Normal"]
    st.font.name, st.font.size = FUENTE, Pt(9)
    st.element.rPr.rFonts.set(qn("w:eastAsia"), FUENTE)
    st.paragraph_format.space_after = Pt(0)
    st.paragraph_format.space_before = Pt(0)
    d.core_properties.title, d.core_properties.author = titulo, "Biznescob · Centro de Calidad"
    # pie con numero de pagina
    p = s.footer.paragraphs[0]
    p.style.font.size = Pt(7)
    _run(p, f"Biznescob · Centro de Calidad · {pie}    Emitido {datetime.now():%d/%m/%Y %H:%M} · Página ", 7, MUTED)
    r = p.add_run()
    r.font.size, r.font.color.rgb = Pt(7), RGBColor.from_string(MUTED)
    for tipo, texto in (("begin", None), (None, "PAGE"), ("end", None)):
        if tipo:
            e = OxmlElement("w:fldChar"); e.set(qn("w:fldCharType"), tipo)
        else:
            e = OxmlElement("w:instrText"); e.set(qn("xml:space"), "preserve"); e.text = texto
        r._r.append(e)
    return d


def _ancho_util(d: Document) -> float:
    s = d.sections[0]
    return (s.page_width - s.left_margin - s.right_margin) / 360000  # cm


def _run(p, texto, size=9, color=INK, bold=False, italic=False):
    r = p.add_run(str(texto))
    r.font.size, r.font.bold, r.font.italic = Pt(size), bold, italic
    r.font.color.rgb = RGBColor.from_string(color)
    r.font.name = FUENTE
    return r


def _par(contenedor, texto="", size=9, color=INK, bold=False, italic=False, align=None,
         antes=0, despues=0, primero=False):
    """Parrafo en un documento o celda. primero=True reutiliza el parrafo vacio de la celda."""
    p = contenedor.paragraphs[0] if primero and contenedor.paragraphs and not contenedor.paragraphs[0].text else contenedor.add_paragraph()
    p.paragraph_format.space_before, p.paragraph_format.space_after = Pt(antes), Pt(despues)
    if align == "c":
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    elif align == "r":
        p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    if texto != "":
        _run(p, texto, size, color, bold, italic)
    return p


def _fondo(celda, hexcolor):
    pr = celda._tc.get_or_add_tcPr()
    for e in pr.findall(qn("w:shd")):
        pr.remove(e)
    sh = OxmlElement("w:shd")
    sh.set(qn("w:val"), "clear"); sh.set(qn("w:color"), "auto"); sh.set(qn("w:fill"), hexcolor)
    pr.append(sh)


def _bordes(celda, **lados):
    """lados: top/bottom/left/right = (grosor_en_octavos_de_pt, color) o None para sin borde."""
    pr = celda._tc.get_or_add_tcPr()
    b = pr.find(qn("w:tcBorders"))
    if b is None:
        b = OxmlElement("w:tcBorders"); pr.append(b)
    for lado, v in lados.items():
        e = OxmlElement(f"w:{lado}")
        if v is None:
            e.set(qn("w:val"), "nil")
        else:
            e.set(qn("w:val"), "single"); e.set(qn("w:sz"), str(v[0])); e.set(qn("w:space"), "0"); e.set(qn("w:color"), v[1])
        b.append(e)


def _margenes(celda, arriba=60, abajo=60, izq=110, der=110):
    pr = celda._tc.get_or_add_tcPr()
    m = OxmlElement("w:tcMar")
    for lado, v in (("top", arriba), ("left", izq), ("bottom", abajo), ("right", der)):
        e = OxmlElement(f"w:{lado}"); e.set(qn("w:w"), str(v)); e.set(qn("w:type"), "dxa"); m.append(e)
    pr.append(m)


def _valign(celda, v="center"):
    pr = celda._tc.get_or_add_tcPr()
    e = OxmlElement("w:vAlign"); e.set(qn("w:val"), v); pr.append(e)


def _fijar(t, anchos):
    """Ancho exacto (cm): tblW + tblGrid + ancho de cada celda. Sin esto Word/LibreOffice reparten a su criterio."""
    pr = t._tbl.tblPr
    for e in pr.findall(qn("w:tblW")):
        pr.remove(e)
    w = OxmlElement("w:tblW"); w.set(qn("w:w"), str(int(sum(anchos) * 567))); w.set(qn("w:type"), "dxa"); pr.append(w)
    if not pr.findall(qn("w:tblLayout")):
        lay = OxmlElement("w:tblLayout"); lay.set(qn("w:type"), "fixed"); pr.append(lay)
    grid = t._tbl.tblGrid
    for g, a in zip(grid.findall(qn("w:gridCol")), anchos):
        g.set(qn("w:w"), str(int(a * 567)))
    for fila in t.rows:
        for i, c in enumerate(fila.cells):
            if i < len(anchos) and len(fila.cells) == len(anchos):
                c.width = Cm(anchos[i])


def _tabla(contenedor, filas, anchos, sin_bordes=True):
    """Tabla de ancho fijo (cm). Sin bordes por defecto; cada celda se decora a mano."""
    t = contenedor.add_table(rows=filas, cols=len(anchos))
    t.alignment = WD_TABLE_ALIGNMENT.LEFT
    t.autofit = False
    pr = t._tbl.tblPr
    lay = OxmlElement("w:tblLayout"); lay.set(qn("w:type"), "fixed"); pr.append(lay)
    m = OxmlElement("w:tblCellMar")
    for lado in ("top", "left", "bottom", "right"):
        e = OxmlElement(f"w:{lado}"); e.set(qn("w:w"), "0"); e.set(qn("w:type"), "dxa"); m.append(e)
    pr.append(m)
    _fijar(t, anchos)
    return t


def _cola_minima(celda):
    """Word exige un parrafo despues de una tabla anidada: se deja casi sin altura."""
    ps = celda.paragraphs
    p = ps[-1] if ps and not ps[-1].text else celda.add_paragraph()
    p.paragraph_format.space_before = p.paragraph_format.space_after = Pt(0)
    p.paragraph_format.line_spacing = Pt(2)
    r = p.add_run(""); r.font.size = Pt(1)


def _espacio(d, pts=6):
    p = d.add_paragraph()
    p.paragraph_format.space_after = Pt(0)
    p.paragraph_format.line_spacing = Pt(max(pts, 1))
    for r in p.runs:
        r.font.size = Pt(1)
    return p


def _caja(celda, titulo, color_barra=BLUE, fondo=None):
    """Estilo comun de tarjeta: borde fino + barra de color a la izquierda."""
    _fondo(celda, fondo) if fondo else None
    _bordes(celda, top=(4, LINE), bottom=(4, LINE), right=(4, LINE), left=(24, color_barra))
    _margenes(celda, 70, 80, 150, 130)
    if titulo:
        _par(celda, titulo, 6.5, MUTED, True, primero=True, despues=2)


def _pildora(celda, texto, fondo, color, size=7.5):
    _fondo(celda, fondo)
    _bordes(celda, top=(12, "FFFFFF"), bottom=(12, "FFFFFF"), left=(12, "FFFFFF"), right=(12, "FFFFFF"))
    _margenes(celda, 20, 20, 40, 40)
    _valign(celda)
    _par(celda, texto, size, color, True, align="c", primero=True)


def _encabezado(d, eyebrow, titulo, sub):
    _par(d, eyebrow, 7.5, BLUE, True)
    _par(d, titulo, 22, NAVY, True, antes=1)
    if sub:
        _par(d, sub, 8.5, MUTED, antes=1)


# ------------------------------------------------------------------ INDIVIDUAL
def construir_informe_individual_docx(payload: Dict) -> bytes:
    d = _nuevo_documento("Informe de evaluación de llamada", "Informe de evaluación de llamada")
    W = _ancho_util(d)
    criterios = payload.get("criterios") or []
    meta_llamada = payload.get("meta") or {}
    nota = _num(payload.get("score_vigente"))
    meta_cal = _num(payload.get("meta_calidad")) or META_POR_DEFECTO

    # --- cabecera: titulo a la izquierda, nota a la derecha
    cab = _tabla(d, 1, [W - 7.8, 7.8])
    izq, der = cab.rows[0].cells
    _par(izq, "CENTRO DE CALIDAD", 7.5, BLUE, True, primero=True)
    _par(izq, "Informe de evaluación de llamada", 22, NAVY, True, antes=1)
    _par(izq, "Resultado vigente de la llamada · pauta aplicada a la cartera", 8.5, MUTED, antes=1)
    _fondo(der, "FFFFFF"); _bordes(der, top=(4, LINE), bottom=(4, LINE), left=(4, LINE), right=(4, LINE)); _margenes(der, 60, 80, 150, 150)
    _par(der, "NOTA FINAL DE LA LLAMADA", 7, NAVY, True, primero=True)
    if nota is None:
        _par(der, "No evaluable", 20, GRIS, True, align="c", antes=4)
        _par(der, "Sin nota en esta llamada", 7.5, MUTED, align="c")
    else:
        p = _par(der, "", antes=2)
        _run(p, f"{nota:.1f}", 30, _hex(_color_nota(nota, meta_cal)), True)
        _run(p, " / 100", 11, MUTED)
        dif = nota - meta_cal
        p2 = _par(der, "")
        _run(p2, f"Meta {meta_cal:g}  ·  ", 8, MUTED)
        _run(p2, f"{dif:+.1f} pts vs meta", 8, _hex(_color_nota(nota, meta_cal)), True)
    _espacio(d, 4)

    # --- datos
    chips = _tabla(d, 1, [W * .44, W * .28, W * .28])
    for c, (et, val) in zip(chips.rows[0].cells, (("AGENTE", meta_llamada.get("agente")), ("CARTERA", meta_llamada.get("cartera")),
                                                  ("FECHA Y HORA", _fecha_hora(meta_llamada.get("fecha"))))):
        _fondo(c, SOFT); _bordes(c, top=(4, LINE), bottom=(4, LINE), left=(4, LINE), right=(4, LINE)); _margenes(c, 50, 60, 130, 100)
        _par(c, et, 6.5, MUTED, True, primero=True)
        _par(c, _txt(val), 10, NAVY, True)
    _espacio(d, 6)

    # --- aviso sin nota
    if nota is None:
        cuenta: Dict[str, int] = {}
        for c in criterios:
            k = _clave_estado(c.get("resultado")); cuenta[k] = cuenta.get(k, 0) + 1
        partes = [f"{cuenta[k]} {n}" for k, n in (("requiere revision", "requieren revisión"), ("no evaluable", "no evaluables"),
                                                  ("no aplica", "no aplican")) if cuenta.get(k)]
        detalle = "Ningún criterio pudo medirse" + (f" ({', '.join(partes)})" if partes else "") if criterios else "No hay criterios medidos"
        av = _tabla(d, 1, [W]).rows[0].cells[0]
        _fondo(av, "FDF0D9"); _bordes(av, left=(24, "D9901A")); _margenes(av, 60, 60, 150, 100)
        p = _par(av, "", primero=True)
        _run(p, "Esta llamada no tiene nota. ", 8.5, INK, True)
        _run(p, f"{detalle}. No es un 0: queda fuera de los promedios.", 8.5)
        _espacio(d, 5)

    # --- resumen
    rs = _tabla(d, 1, [W]).rows[0].cells[0]
    _caja(rs, "RESUMEN DE LA LLAMADA", BLUE)
    _par(rs, _txt(payload.get("resumen"), "Sin resumen registrado."), 9)
    _espacio(d, 4)

    _par(d, "Criterios de evaluación", 11, NAVY, True, despues=2)

    # --- criterios por bloque, 2 por fila
    gap = 0.4
    wc = (W - gap) / 2
    tarjetas = []
    for nombre, filas in _bloques(criterios):
        puntos = sum(float(f.get("nota") or 0) for f in filas if f.get("nota") is not None)
        peso = sum(float(f.get("peso") or 0) for f in filas)
        tarjetas.append((nombre, filas, puntos, peso))
    if not tarjetas:
        _par(d, "Esta evaluación no tiene criterios registrados.", 9, MUTED)
    for i in range(0, len(tarjetas), 2):
        fila = _tabla(d, 1, [wc, gap, wc])
        for celda, tarj in zip((fila.rows[0].cells[0], fila.rows[0].cells[2]), tarjetas[i:i + 2]):
            nombre, filas, puntos, peso = tarj
            wn, wp, wd = wc - 2.2 - 3.0, 2.2, 3.0
            inner = celda.add_table(rows=1 + len(filas), cols=3)
            inner.autofit = False
            _fijar(inner, (wn, wp, wd))
            h = inner.rows[0].cells
            a = h[0].merge(h[1])
            _fondo(a, NAVY); _margenes(a, 50, 50, 130, 60); _par(a, nombre, 8.5, "FFFFFF", True, primero=True)
            _fondo(h[2], NAVY); _margenes(h[2], 50, 50, 60, 130)
            _par(h[2], f"{puntos:g} de {peso:g} pts", 7.5, "FFFFFF", align="r", primero=True)
            for r, f in zip(inner.rows[1:], filas):
                n, p_ = _num(f.get("nota")), _num(f.get("peso"))
                pts = "—" if n is None else f"{n:g} / {p_:g}" if p_ is not None else f"{n:g}"
                c0, c1, c2 = r.cells
                for c in (c0, c1):
                    _bordes(c, bottom=(4, PALE)); _valign(c); _margenes(c, 35, 35, 130, 60)
                _par(c0, _txt(f.get("criterio")), 8.3, primero=True)
                _par(c1, pts, 8.3, INK, True, align="r", primero=True)
                _bordes(c2, bottom=(4, PALE))
                _, fondo, tcol = ESTADOS[_clave_estado(f.get("resultado"))]
                _pildora(c2, ESTADOS[_clave_estado(f.get("resultado"))][0], fondo.lstrip("#"), tcol.lstrip("#"))
            # el parrafo vacio inicial de la celda externa va antes de la tabla: se quita
            if len(celda.paragraphs) > 1 and not celda.paragraphs[0].text:
                celda._tc.remove(celda.paragraphs[0]._p)
            _cola_minima(celda)
        _espacio(d, 3)

    # --- fortalezas | brechas | feedback
    g = 0.35
    w3 = (W - 2 * g) / 3
    tres = _tabla(d, 2, [w3, g, w3, g, w3])
    for col, (titulo, color) in zip((0, 2, 4), (("FORTALEZAS OBSERVADAS", VERDE), ("BRECHAS Y RECOMENDACIÓN", ROJO), ("FEEDBACK DEL EVALUADOR", BLUE))):
        c = tres.rows[0].cells[col]
        _fondo(c, color); _margenes(c, 60, 60, 130, 100)
        _par(c, titulo, 8, "FFFFFF", True, primero=True)
    cuerpo = tres.rows[1].cells
    for col in (0, 2, 4):
        _bordes(cuerpo[col], bottom=(4, LINE), left=(4, LINE), right=(4, LINE)); _margenes(cuerpo[col], 70, 80, 130, 120)
    fort = _sin_repetidos(payload.get("fortalezas"))
    if fort:
        for i, f in enumerate(fort):
            _par(cuerpo[0], "• " + f, 8.3, primero=(i == 0), despues=1)
    else:
        _par(cuerpo[0], "Sin fortaleza registrada.", 8.3, MUTED, primero=True)
    brechas = [x for x in criterios if x.get("brecha")]
    primero = True
    for c in brechas:
        p = _par(cuerpo[2], "", primero=primero, despues=1); primero = False
        _run(p, "• ", 8.3); _run(p, _txt(c.get("criterio")), 8.3, INK, True); _run(p, f" · {_txt(c.get('resultado'))}", 8.3)
        ev = _txt(c.get("evidencia"), "")
        if ev:
            q = _par(cuerpo[2], "“" + _recortar(ev, 220) + "”", 7.5, MUTED, italic=True, despues=2)
            q.paragraph_format.left_indent = Cm(0.3)
    if not brechas:
        previas = _sin_repetidos(payload.get("brechas"))
        for i, b in enumerate(previas):
            _par(cuerpo[2], "• " + _recortar(b, 240), 8.3, primero=(i == 0), despues=1)
        if not previas:
            _par(cuerpo[2], "Sin brecha registrada.", 8.3, MUTED, primero=True)
    _par(cuerpo[4], _txt(payload.get("feedback"), "Sin feedback registrado."), 8.3, primero=True)
    _espacio(d, 4)

    # --- compromiso + firmas
    fr = _tabla(d, 1, [W * .30, W * .233, W * .233, W * .234])
    c0 = fr.rows[0].cells[0]
    _fondo(c0, SOFT); _bordes(c0, left=(24, BLUE), top=(4, LINE), bottom=(4, LINE)); _margenes(c0, 70, 70, 150, 100)
    _par(c0, "COMPROMISO DEL AGENTE", 6.5, MUTED, True, primero=True, despues=2)
    _par(c0, _txt(payload.get("compromiso"), "Pendiente de registrar con el agente."), 8.3)
    for col, rotulo in zip((1, 2, 3), ("Calidad", "Jefatura de cartera (Lourdes)", "Agente")):
        c = fr.rows[0].cells[col]
        _fondo(c, SOFT); _bordes(c, top=(4, LINE), bottom=(4, LINE), right=(4, LINE) if col == 3 else None)
        _margenes(c, 70, 70, 200, 200); _valign(c, "bottom")
        _par(c, "", 14, primero=True, antes=14)
        q = _par(c, f"{rotulo} · Firma y fecha", 6.8, MUTED)
        pb = OxmlElement("w:pBdr"); top = OxmlElement("w:top")
        for k, v in (("val", "single"), ("sz", "6"), ("space", "2"), ("color", "7A8CA0")):
            top.set(qn(f"w:{k}"), v)
        pb.append(top); q._p.get_or_add_pPr().append(pb)

    buf = BytesIO()
    d.save(buf)
    return buf.getvalue()


# ------------------------------------------------------------------ CARTERA
def _tabla_simple(d, W, cabeceras, filas, anchos_rel, alinea=None, colores=None):
    """Tabla con cabecera clara. colores[(fila, col)] = (fondo, texto) para pildoras."""
    anchos = [W * r for r in anchos_rel]
    t = _tabla(d, 1 + len(filas), anchos)
    alinea = alinea or ["l"] * len(cabeceras)
    for j, h in enumerate(cabeceras):
        c = t.rows[0].cells[j]
        _fondo(c, PALE); _bordes(c, bottom=(8, NAVY)); _margenes(c, 55, 55, 120, 120); _valign(c)
        _par(c, h, 8, NAVY, True, align=alinea[j], primero=True)
    for i, fila in enumerate(filas, start=1):
        for j, v in enumerate(fila):
            c = t.rows[i].cells[j]
            _bordes(c, bottom=(4, LINE)); _margenes(c, 55, 55, 120, 120); _valign(c)
            if i % 2 == 0:
                _fondo(c, "F8FAFC")
            if colores and (i - 1, j) in colores:
                f, tx = colores[(i - 1, j)]
                _pildora(c, v, f, tx)
            else:
                est = v if isinstance(v, tuple) else (v, 8.5, INK, False)
                _par(c, est[0], est[1], est[2], est[3], align=alinea[j], primero=True)
    return t


def construir_informe_cartera_docx(payload: Dict) -> bytes:
    m = _modelo_cartera(payload)
    d = _nuevo_documento("Informe ejecutivo de calidad", "Informe ejecutivo de calidad")
    W = _ancho_util(d)
    meta = m["meta"]
    prom = m["promedio"]

    _encabezado(d, "CENTRO DE CALIDAD", "Informe ejecutivo de calidad", "")
    _espacio(d, 4)
    datos = [("CARTERA", m["cartera"]), ("PERIODO", m["periodo"]), ("MUESTRA", f"{m['n']} evaluaciones"),
             ("EMISIÓN", datetime.now().strftime("%d/%m/%Y") + (f" · {m['emite']}" if m["emite"] else ""))]
    chips = _tabla(d, 1, [W * p for p in (.26, .30, .18, .26)])
    for c, (t, v) in zip(chips.rows[0].cells, datos):
        _fondo(c, SOFT); _bordes(c, top=(4, LINE), bottom=(4, LINE), left=(4, LINE), right=(4, LINE)); _margenes(c, 60, 60, 140, 100)
        _par(c, t, 6.5, MUTED, True, primero=True)
        _par(c, _txt(v), 10, NAVY, True)
    if m["filtros"]:
        txt = " · ".join(f"{a}: {b}" for a, b in m["filtros"] if a)
        if txt:
            p = _par(d, "", antes=4)
            _run(p, "Filtros aplicados: ", 8.5, MUTED, True); _run(p, txt, 8.5, MUTED)
    _espacio(d, 8)

    # --- KPIs
    pct_meta = None if (meta is None or not m["con_nota"]) else 100 * m["en_meta"] / m["con_nota"]
    kpis = [
        (str(m["n"]), "Evaluaciones", f"de {len(m['agentes'])} agentes", BLUE),
        ("—" if prom is None else f"{prom:.1f}", "Nota promedio",
         "Sin meta configurada" if meta is None or prom is None else f"{prom - meta:+.1f} pts vs meta {meta:g}", _hex(_color_nota(prom, meta))),
        ("—" if pct_meta is None else f"{pct_meta:.0f}%", "En meta",
         "Sin meta configurada" if pct_meta is None else f"{m['en_meta']} de {m['con_nota']} con nota", VERDE),
        (str(m["sin_nota"]), "Sin nota", "No evaluables · fuera de promedios", AMBAR),
        (str(m["criticos"]), "Con error crítico", "Indicador en revisión (no distingue gravedad)", ROJO),
    ]
    gk = 0.3
    wk = (W - gk * 4) / 5
    tk = _tabla(d, 1, [wk, gk, wk, gk, wk, gk, wk, gk, wk])
    for idx, (valor, etiqueta, detalle, color) in enumerate(kpis):
        c = tk.rows[0].cells[idx * 2]
        _fondo(c, "FFFFFF"); _bordes(c, top=(24, color), bottom=(4, LINE), left=(4, LINE), right=(4, LINE)); _margenes(c, 80, 90, 140, 100)
        _par(c, etiqueta.upper(), 6.8, MUTED, True, primero=True)
        _par(c, valor, 22, color, True, antes=1)
        _par(c, detalle, 7.2, MUTED)
    _espacio(d, 10)

    # --- evolucion + criterios que requieren atencion (lado a lado)
    gg = 0.7
    wi = W * .50
    wd = W - wi - gg
    lado = _tabla(d, 1, [wi, gg, wd])
    li, _, ld = lado.rows[0].cells
    _par(li, "Evolución de la nota promedio", 11, NAVY, True, primero=True)
    _par(li, "Semanas de domingo a sábado, acotadas al mes.", 7.8, MUTED, despues=4)
    filas_sem = [[s["etiqueta"], s["rango"], "—" if s["prom"] is None else f"{s['prom']:.1f}", str(s["n"])] for s in m["semanas"]]
    if filas_sem:
        ti = li.add_table(rows=1 + len(filas_sem), cols=4)
        ti.autofit = False
        _fijar(ti, (wi * .30, wi * .28, wi * .22, wi * .20))
        for k, h in enumerate(("Semana", "Fechas", "Promedio", "Eval.")):
            c = ti.rows[0].cells[k]; _fondo(c, PALE); _bordes(c, bottom=(8, NAVY)); _margenes(c, 45, 45, 100, 100)
            _par(c, h, 8, NAVY, True, align="l" if k < 2 else "r", primero=True)
        for i, f in enumerate(filas_sem, start=1):
            for k, v in enumerate(f):
                c = ti.rows[i].cells[k]; _bordes(c, bottom=(4, LINE)); _margenes(c, 45, 45, 100, 100)
                color = INK
                if k == 2 and v != "—":
                    color = _hex(_color_nota(float(v), meta))
                _par(c, v, 8.5, color, k == 2, align="l" if k < 2 else "r", primero=True)
    else:
        _par(li, "Sin semanas con fecha en el periodo.", 8.5, MUTED)
    _par(ld, "Criterios que requieren atención", 11, NAVY, True, primero=True)
    _par(ld, "Mayor % de incumplimiento sobre lo medido.", 7.8, MUTED, despues=4)
    top = m["ranking"][:5]
    if top:
        td = ld.add_table(rows=1 + len(top), cols=3)
        td.autofit = False
        _fijar(td, (wd * .62, wd * .22, wd * .16))
        for k, h in enumerate(("Criterio", "Brechas", "% falla")):
            c = td.rows[0].cells[k]; _fondo(c, PALE); _bordes(c, bottom=(8, NAVY)); _margenes(c, 45, 45, 100, 100)
            _par(c, h, 8, NAVY, True, align="l" if k == 0 else "r", primero=True)
        for i, r_ in enumerate(top, start=1):
            vals = (r_["nombre"], f"{r_['brechas']} de {r_['medidas']}", f"{r_['tasa']:.0f}%")
            for k, v in enumerate(vals):
                c = td.rows[i].cells[k]; _bordes(c, bottom=(4, LINE)); _margenes(c, 45, 45, 100, 100)
                _par(c, v, 8.5, ROJO if k == 2 else INK, k == 2, align="l" if k == 0 else "r", primero=True)
    else:
        _par(ld, "Sin brechas medidas en el periodo.", 8.5, MUTED)
    for c in (li, ld):  # quita el parrafo vacio final que Word exige tras una tabla anidada
        pass
    _espacio(d, 10)

    # --- lectura del periodo + plan de accion
    lineas: List[List] = []
    if prom is not None:
        t = [("La nota promedio fue ", False), (f"{prom:.1f}", True), (" de 100", False)]
        if meta is not None:
            t.append((f", {abs(prom - meta):.1f} puntos {'sobre' if prom >= meta else 'bajo'} la meta de {meta:g}.", False))
        else:
            t.append((".", False))
        lineas.append(t)
    validas = [s for s in m["semanas"] if s["prom"] is not None]
    if len(validas) >= 2:
        dif = validas[-1]["prom"] - validas[-2]["prom"]
        lineas.append([(f"La última semana {'mejoró' if dif >= 0 else 'bajó'} ", False), (f"{abs(dif):.1f} puntos", True), (" frente a la anterior.", False)])
    if m["ranking"]:
        r = m["ranking"][0]
        lineas.append([(r["nombre"], True), (f" es el principal foco: {r['brechas']} de {r['medidas']} mediciones con brecha ({r['tasa']:.0f}%).", False)])
    if m["sin_nota"]:
        lineas.append([(f"{m['sin_nota']} evaluaciones no tienen nota (no evaluables) y no entran en el promedio.", False)])
    if not lineas:
        lineas = [[("No hay notas evaluables en el periodo.", False)]]
    gl = 0.5
    wl = W * .58
    lp = _tabla(d, 1, [wl, gl, W - wl - gl])
    cl, _, cp = lp.rows[0].cells
    _par(cl, "LECTURA DEL PERIODO", 7.5, BLUE, True, primero=True, despues=3)
    for i, partes in enumerate(lineas[:4], start=1):
        p = _par(cl, "", despues=2)
        _run(p, f"{i}  ", 9, BLUE, True)
        for texto, neg in partes:
            _run(p, texto, 9, INK, neg)
    _caja(cp, "PLAN DE ACCIÓN", BLUE, SOFT)
    foco = m["ranking"][0]["nombre"] if m["ranking"] else "Sin brechas medidas"
    p = _par(cp, "", despues=2); _run(p, "Foco: ", 9, INK, True); _run(p, foco, 9)
    p = _par(cp, ""); _run(p, "Acción sugerida: ", 9, INK, True); _run(p, m["recomendacion"] or "Coaching y seguimiento semanal.", 9)

    # --- anexo: rendimiento por agente
    d.add_paragraph().add_run().add_break(WD_BREAK.PAGE)
    _par(d, "CENTRO DE CALIDAD · ANEXO", 7.5, BLUE, True)
    _par(d, "Rendimiento por agente", 18, NAVY, True, antes=1)
    _par(d, f"{m['cartera']} · {m['periodo']}", 8.5, MUTED, antes=1, despues=6)
    filas, colores = [], {}
    for i, a in enumerate(m["agentes"]):
        tend = "Sin base" if a["tendencia"] is None else f"{a['tendencia']:+.1f} pts"
        t_col = MUTED if a["tendencia"] is None else (VERDE if a["tendencia"] >= 0 else ROJO)
        clave, texto_estado = _estado_agente(a["prom"], meta)
        _, fondo, tcol = ESTADOS[clave]
        colores[(i, 5)] = (fondo.lstrip("#"), tcol.lstrip("#"))
        filas.append([
            (a["nombre"], 8.5, INK, True),
            str(a["n"]) + ("" if a["con_nota"] == a["n"] else f" ({a['con_nota']} con nota)"),
            ("—" if a["prom"] is None else f"{a['prom']:.1f}", 9, _hex(_color_nota(a["prom"], meta)), True),
            (tend, 8.5, t_col, False),
            a["criterio"], texto_estado,
        ])
    if filas:
        _tabla_simple(d, W, ["Agente", "Evaluaciones", "Promedio", "Tendencia", "Principal criterio a reforzar", "Estado"], filas,
                      [.24, .11, .10, .13, .30, .12], ["l", "c", "c", "c", "l", "c"], colores)
    else:
        _par(d, "Sin agentes con evaluaciones en el periodo.", 9, MUTED)

    # --- donde falla mas
    foco_dim = [(t, m["foco"].get(k) or []) for t, k in (("Por cartera", "cartera"), ("Por supervisor", "supervisor"))]
    foco_dim = [(t, v) for t, v in foco_dim if v]
    if foco_dim:
        _espacio(d, 10)
        _par(d, "Dónde falla más", 11, NAVY, True)
        _par(d, "Los 3 criterios con mayor % de falla de cada grupo y su diferencia contra el total del periodo.", 7.8, MUTED, despues=4)
        anchos = [W / len(foco_dim)] * len(foco_dim)
        tf = _tabla(d, 1, anchos)
        for c, (titulo, grupos) in zip(tf.rows[0].cells, foco_dim):
            _margenes(c, 0, 0, 0, 200)
            _par(c, titulo.upper(), 7.5, BLUE, True, primero=True, despues=3)
            for g_ in grupos[:6]:
                _par(c, _txt(g_.get("grupo")), 8.5, INK, True, antes=2)
                for linea in (g_.get("top") or [])[:3]:
                    q = _par(c, "– " + str(linea), 7.8, MUTED)
                    q.paragraph_format.left_indent = Cm(0.25)

    # --- como leer
    _espacio(d, 12)
    nota_c = _tabla(d, 1, [W]).rows[0].cells[0]
    _fondo(nota_c, SOFT); _bordes(nota_c, top=(4, LINE), bottom=(4, LINE), left=(4, LINE), right=(4, LINE)); _margenes(nota_c, 90, 90, 160, 160)
    cobertura = "" if m["cobertura"] is None else f" De los registros de criterio, el {m['cobertura']:.0f}% fue medible (Cumple o No cumple)."
    p = _par(nota_c, "", primero=True)
    _run(p, "Cómo leer este informe. ", 7.8, MUTED, True)
    _run(p, ("Un criterio cuenta como medido solo si resultó Cumple o No cumple; No aplica, No evaluable y Requiere revisión no entran en ningún porcentaje. "
             "Una evaluación sin nota no es un 0: queda fuera de promedios. En meta = evaluaciones con nota ≥ meta sobre las que tienen nota. "
             "Tendencia = promedio de las 3 últimas notas del agente menos el de las 3 anteriores (sin base si no hay al menos 2 y 2). "
             f"Con menos de {BASE_CHICA} mediciones se marca «base chica».{cobertura}"), 7.8, MUTED)

    buf = BytesIO()
    d.save(buf)
    return buf.getvalue()
