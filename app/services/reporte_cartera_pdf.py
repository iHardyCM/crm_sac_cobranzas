"""Informe ejecutivo de cartera con una reticula estable para A4 horizontal."""

from collections import defaultdict
from calendar import monthrange
from datetime import datetime, timedelta
from html import escape
from io import BytesIO
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A3, A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph


PAGE_W, PAGE_H = landscape(A4)
OUTPUT_W, OUTPUT_H = landscape(A3)
PAGE_SCALE = 1.25
LEFT, RIGHT = 24, PAGE_W - 24
WIDTH = RIGHT - LEFT
NAVY = colors.HexColor("#0E3159")
BLUE = colors.HexColor("#1265B1")
INK = colors.HexColor("#183552")
MUTED = colors.HexColor("#58708B")
LINE = colors.HexColor("#C8D6E4")
PALE = colors.HexColor("#EAF0F6")
BAR_BG = colors.HexColor("#DDE5ED")


def _fonts():
    fonts = Path("C:/Windows/Fonts")
    regular = fonts / "segoeui.ttf"
    bold = fonts / "segoeuib.ttf"
    if regular.exists() and bold.exists():
        if "QualitySegoe" not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont("QualitySegoe", str(regular)))
            pdfmetrics.registerFont(TTFont("QualitySegoe-Bold", str(bold)))
        return "QualitySegoe", "QualitySegoe-Bold"
    return "Helvetica", "Helvetica-Bold"


def _date(value):
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        try:
            return datetime.strptime(text[:10], "%d/%m/%Y")
        except ValueError:
            return None


def _number(value):
    try:
        return float(value) if value is not None and value != "" else None
    except (TypeError, ValueError):
        return None


def _yes(value):
    return str(value or "").strip().casefold() in {"sí", "si", "true", "1"}


def _month_week(day):
    first = day.replace(day=1)
    sunday = day - timedelta(days=(day.weekday() + 1) % 7)
    last = day.replace(day=monthrange(day.year, day.month)[1])
    number = 1 + (day.day + (first.weekday() + 1) % 7 - 1) // 7
    return (day.year, day.month, number), max(first, sunday), min(last, sunday + timedelta(days=6))


def _paragraph(pdf, text, x, top, width, max_height, font, size=8, color=INK, bold=None):
    """Dibuja texto dentro de su celda y reduce la fuente si es necesario."""
    safe = escape(str(text or "—"))
    current = size
    while True:
        style = ParagraphStyle("cell", fontName=bold or font, fontSize=current,
                               leading=current * 1.24, textColor=color)
        item = Paragraph(safe, style)
        _, height = item.wrap(width, max_height)
        if height <= max_height or current <= 5.6:
            break
        current -= .35
    if height > max_height:
        raise ValueError(f"Texto demasiado largo para el informe: {str(text)[:60]}")
    item.drawOn(pdf, x, top - height)
    return height


def _line(pdf, x1, y1, x2, y2, color=LINE, width=.55):
    pdf.setStrokeColor(color)
    pdf.setLineWidth(width)
    pdf.line(x1, y1, x2, y2)


def _start_page(pdf):
    """Centra la reticula en A3 con margenes amplios sin deformar el texto."""
    pdf.translate((OUTPUT_W - PAGE_W * PAGE_SCALE) / 2,
                  (OUTPUT_H - PAGE_H * PAGE_SCALE) / 2)
    pdf.scale(PAGE_SCALE, PAGE_SCALE)


def _section(pdf, title, subtitle, x, top, font, bold):
    pdf.setFillColor(NAVY)
    pdf.setFont(bold, 11)
    pdf.drawString(x, top, title)
    pdf.setFillColor(MUTED)
    pdf.setFont(font, 7.2)
    pdf.drawString(x, top - 11, subtitle)


def _model(payload):
    evaluations = payload.get("evaluaciones") or []
    criteria = payload.get("criterios") or []
    grades = [_number(row.get("nota")) for row in evaluations]
    grades = [value for value in grades if value is not None]
    average = sum(grades) / len(grades) if grades else None
    target = _number(payload.get("meta"))
    portfolios = sorted({str(row.get("cartera")).strip() for row in evaluations if row.get("cartera")})
    portfolio = portfolios[0] if len(portfolios) == 1 else "Carteras seleccionadas"
    critical_count = sum(_yes(row.get("error_critico")) for row in evaluations)

    per_week = defaultdict(list)
    per_agent = defaultdict(list)
    for row in evaluations:
        name = str(row.get("agente") or "Sin agente").strip()
        per_agent[name].append(row)
        date = _date(row.get("fecha"))
        if date:
            per_week[_month_week(date.date())[0]].append(row)

    weeks = []
    multiple_months = len({key[:2] for key in per_week}) > 1
    for key, rows in sorted(per_week.items()):
        notes = [_number(row.get("nota")) for row in rows]
        notes = [n for n in notes if n is not None]
        _, start, end = _month_week(_date(rows[0].get("fecha")).date())
        label = f"{key[1]:02d} · S{key[2]}" if multiple_months else f"Sem. {key[2]}"
        weeks.append({"start": start, "end": end, "label": label,
                      "date_label": f"{start:%d/%m}-{end:%d/%m}",
                      "average": sum(notes) / len(notes) if notes else None, "count": len(rows)})

    repeated_by_agent = {}
    for entry in payload.get("agentes") or []:
        name = str(entry.get("agente") or "").strip()
        repeated_by_agent[name] = str(entry.get("brecha_repite") or "").strip()

    agents = []
    for name, rows in per_agent.items():
        notes = [_number(row.get("nota")) for row in rows]
        notes = [n for n in notes if n is not None]
        score = sum(notes) / len(notes) if notes else None
        by_week = defaultdict(list)
        for row in rows:
            date = _date(row.get("fecha"))
            note = _number(row.get("nota"))
            if date and note is not None:
                by_week[_month_week(date.date())[0]].append(note)
        points = [sum(values) / len(values) for _, values in sorted(by_week.items())]
        trend = points[-1] - points[-2] if len(points) >= 2 else None
        agents.append({"name": name, "count": len(rows), "score": score, "trend": trend,
                       "week_count": len(points),
                       "criterion": repeated_by_agent.get(name) or "Sin recurrencia identificada"})
    agents.sort(key=lambda row: (row["score"] is None, row["score"] or 0, row["name"]))

    by_criterion = defaultdict(lambda: {"measured": 0, "breaches": 0})
    measured = 0
    for row in criteria:
        name = str(row.get("criterio") or "").strip()
        if not name:
            continue
        entry = by_criterion[name]
        if _yes(row.get("medido")):
            entry["measured"] += 1
            measured += 1
            if _yes(row.get("brecha")):
                entry["breaches"] += 1
    ranking = []
    for name, counts in by_criterion.items():
        if counts["measured"]:
            ranking.append({"name": name, **counts,
                            "rate": 100 * counts["breaches"] / counts["measured"]})
    ranking.sort(key=lambda row: (-row["rate"], -row["breaches"], row["name"]))

    return {"portfolio": portfolio, "period": str(payload.get("periodo") or "Periodo no indicado"),
            "evaluations": evaluations, "criteria": criteria, "average": average, "target": target,
            "critical": critical_count, "coverage": 100 * measured / len(criteria) if criteria else None,
            "weeks": weeks, "agents": agents, "ranking": ranking,
            "recommendation": str(payload.get("recomendacion") or "").strip()}


def _header(pdf, model, font, bold):
    pdf.setFillColor(NAVY)
    pdf.setFont(bold, 22)
    pdf.drawString(LEFT + 7, 562, "Informe ejecutivo de calidad por cartera")
    pdf.setFont(font, 7.8)
    y = 539
    fields = [("Cartera", model["portfolio"], 186),
              ("Periodo", model["period"], 233),
              ("Muestra", f"{len(model['evaluations'])} evaluaciones", 169),
              ("Fecha de emisión", datetime.now().strftime("%d/%m/%Y"), 194)]
    x = LEFT + 7
    for label, value, width in fields:
        pdf.setFont(bold, 7.7)
        pdf.drawString(x, y, label + ":")
        label_width = pdfmetrics.stringWidth(label + ":", bold, 7.7)
        _paragraph(pdf, value, x + label_width + 4, y + 7, width - label_width - 12,
                   17, font, 7.5)
        x += width
        if x < RIGHT - 5:
            _line(pdf, x - 8, y - 3, x - 8, y + 10)
    _line(pdf, LEFT, 525, RIGHT, 525, NAVY, .7)


def _kpis(pdf, model, font, bold):
    count = len(model["evaluations"])
    avg = model["average"]
    target = model["target"]
    coverage = model["coverage"]
    items = [
        (str(count), "evaluaciones", f"de {len(model['agents'])} agentes"),
        ("—" if avg is None else f"{avg:.1f}", "nota promedio",
         "Sin meta configurada" if target is None or avg is None else f"{avg - target:+.1f} pts vs. meta"),
        (str(model["critical"]), "riesgos críticos", "evaluaciones con error crítico"),
        ("—" if coverage is None else f"{coverage:.0f}%", "criterios medidos", "de los registros de criterio"),
    ]
    col_width = WIDTH / 4
    for index, (number, label, detail) in enumerate(items):
        x = LEFT + index * col_width
        if index:
            _line(pdf, x, 465, x, 516)
        pdf.setFillColor(NAVY)
        pdf.setFont(bold, 22)
        pdf.drawString(x + 25, 487, number)
        pdf.setFont(bold, 9)
        pdf.drawString(x + 25, 476, label)
        pdf.setFillColor(MUTED)
        pdf.setFont(font, 7.1)
        pdf.drawString(x + 25, 467, detail)
    _line(pdf, LEFT, 460, RIGHT, 460, NAVY, .7)


def _chart(pdf, weeks, x, top, width, height, font, bold):
    _section(pdf, "Evolución de la nota promedio", "Semanas de domingo a sábado, acotadas al mes.", x, top, font, bold)
    axis_left, axis_right = x + 31, x + width - 18
    data_left, data_right = axis_left + 45, axis_right - 30
    bottom, upper = top - height + 20, top - 31
    scores = [week["average"] for week in weeks if week["average"] is not None]
    lower = max(0, min(60, (int(min(scores) // 10) - 1) * 10)) if scores else 60
    for tick in range(lower, 101, 10):
        y = bottom + (upper - bottom) * (tick - lower) / (100 - lower)
        _line(pdf, axis_left, y, axis_right, y, PALE, .4)
        pdf.setFillColor(MUTED)
        pdf.setFont(font, 6.2)
        pdf.drawRightString(axis_left - 7, y - 2, str(tick))
    if not scores:
        _paragraph(pdf, "Sin notas semanales para graficar.", data_left, upper - 20,
                   data_right - data_left, 20, font, 8)
        return
    positions = []
    for index, week in enumerate(weeks):
        score = week["average"]
        if score is None:
            continue
        pos_x = data_left + (data_right - data_left) * index / max(1, len(weeks) - 1)
        pos_y = bottom + (upper - bottom) * (score - lower) / (100 - lower)
        positions.append((pos_x, pos_y, score))
        pdf.setFillColor(MUTED)
        pdf.setFont(font, 6.2)
        pdf.drawCentredString(pos_x, bottom - 10, week["label"])
        pdf.drawCentredString(pos_x, bottom - 18, week["date_label"])
    pdf.setStrokeColor(BLUE)
    pdf.setLineWidth(1.7)
    for first, second in zip(positions, positions[1:]):
        pdf.line(first[0], first[1], second[0], second[1])
    for pos_x, pos_y, score in positions:
        pdf.setFillColor(BLUE)
        pdf.circle(pos_x, pos_y, 2.4, stroke=0, fill=1)
        pdf.setFont(bold, 7.0)
        pdf.drawCentredString(pos_x, pos_y + 7, f"{score:.1f}")


def _highlights(pdf, model, x, top, width, height, font, bold):
    _section(pdf, "Hitos del periodo", "Principales resultados y oportunidades identificadas.", x, top, font, bold)
    weeks = [week for week in model["weeks"] if week["average"] is not None]
    if len(weeks) >= 2:
        delta = weeks[-1]["average"] - weeks[-2]["average"]
        lead = f"La última semana {'mejoró' if delta >= 0 else 'bajó'} {abs(delta):.1f} puntos frente a la anterior."
    elif model["average"] is not None:
        lead = f"Promedio del periodo: {model['average']:.1f} de 100."
    else:
        lead = "No hay notas evaluables en el periodo."
    pdf.setFillColor(NAVY)
    pdf.setFont(bold, 9)
    pdf.drawString(x + 10, top - 33, "Resultado del periodo")
    _paragraph(pdf, lead, x + 10, top - 38, width - 20, 25, font, 7.9)
    _line(pdf, x + 7, top - 68, x + width - 7, top - 68)
    pdf.setFillColor(NAVY)
    pdf.setFont(bold, 9)
    pdf.drawString(x + 10, top - 82, "Criterio más afectado")
    criterion = model["ranking"][0] if model["ranking"] else None
    detail = (f"{criterion['name']}: {criterion['breaches']} de {criterion['measured']} mediciones "
              f"con brecha ({criterion['rate']:.0f}%).") if criterion else "Sin brechas medidas."
    _paragraph(pdf, detail, x + 10, top - 87, width - 20, 26, font, 7.9)


def _agent_table(pdf, model, top, font, bold, first=True, offset=0, limit=7):
    title = "Rendimiento por agente" if first else "Rendimiento por agente (continuación)"
    _section(pdf, title, "Cantidad de evaluaciones, nota y principal oportunidad de mejora.", LEFT, top, font, bold)
    head_top = top - 28
    head_h, row_h = 17, 20
    columns = [LEFT, LEFT + 174, LEFT + 244, LEFT + 335, LEFT + 437, LEFT + 696, RIGHT]
    pdf.setFillColor(PALE)
    pdf.rect(LEFT, head_top - head_h, WIDTH, head_h, stroke=0, fill=1)
    labels = ["Agente", "Evaluaciones", "Promedio", "Tendencia semanal", "Principal criterio a reforzar", "Estado"]
    for i, label in enumerate(labels):
        pdf.setFillColor(NAVY)
        pdf.setFont(bold, 7.3)
        pdf.drawString(columns[i] + 6, head_top - 12, label)
    rows = model["agents"][offset:offset + limit]
    for index, row in enumerate(rows):
        y_top = head_top - head_h - index * row_h
        if index % 2:
            pdf.setFillColor(colors.HexColor("#F8FAFC"))
            pdf.rect(LEFT, y_top - row_h, WIDTH, row_h, stroke=0, fill=1)
        _line(pdf, LEFT, y_top - row_h, RIGHT, y_top - row_h)
        _paragraph(pdf, row["name"], columns[0] + 6, y_top - 3, columns[1] - columns[0] - 12,
                   row_h - 5, font, 7.1)
        pdf.setFillColor(INK)
        pdf.setFont(font, 7.4)
        pdf.drawCentredString((columns[1] + columns[2]) / 2, y_top - 13, str(row["count"]))
        score = row["score"]
        pdf.drawCentredString((columns[2] + columns[3]) / 2, y_top - 13, "—" if score is None else f"{score:.1f}")
        trend = row["trend"]
        if trend is not None:
            pdf.setFillColor(BLUE if trend >= 0 else colors.HexColor("#9E3D43"))
            pdf.drawCentredString((columns[3] + columns[4]) / 2, y_top - 13, f"{trend:+.1f} pts")
        else:
            message = "1 semana" if row["week_count"] == 1 else "Sin nota"
            pdf.drawCentredString((columns[3] + columns[4]) / 2, y_top - 13, message)
        _paragraph(pdf, row["criterion"], columns[4] + 6, y_top - 3, columns[5] - columns[4] - 12,
                   row_h - 5, font, 7.1)
        status = ("Sin nota" if score is None else "Sin meta" if model["target"] is None
                  else "En rango" if score >= model["target"] else "En seguimiento")
        _paragraph(pdf, status, columns[5] + 6, y_top - 4, columns[6] - columns[5] - 12,
                   row_h - 5, font, 7.0)
    return head_top - head_h - len(rows) * row_h


def _bottom(pdf, model, top, font, bold):
    middle = LEFT + WIDTH * .53
    _section(pdf, "Criterios que requieren atención", "Mayor porcentaje de incumplimiento en lo medido.", LEFT, top, font, bold)
    _section(pdf, "Análisis y recomendaciones", "Conclusiones del periodo y acciones sugeridas.", middle + 12, top, font, bold)
    _line(pdf, middle, top + 6, middle, top - 96)
    header_y = top - 29
    pdf.setFont(bold, 6.9)
    pdf.setFillColor(NAVY)
    pdf.drawString(LEFT + 4, header_y, "Criterio")
    pdf.drawString(LEFT + 255, header_y, "Afectadas")
    pdf.drawString(LEFT + 334, header_y, "%")
    _line(pdf, LEFT, header_y - 3, middle - 9, header_y - 3)
    for index, row in enumerate(model["ranking"][:5]):
        y_top = header_y - 5 - index * 14
        _paragraph(pdf, row["name"], LEFT + 4, y_top, 172, 14, font, 6.8)
        bar_x, bar_y, bar_w = LEFT + 180, y_top - 8, 66
        pdf.setFillColor(BAR_BG)
        pdf.rect(bar_x, bar_y, bar_w, 5, stroke=0, fill=1)
        pdf.setFillColor(BLUE)
        pdf.rect(bar_x, bar_y, bar_w * min(row["rate"], 100) / 100, 5, stroke=0, fill=1)
        pdf.setFillColor(INK)
        pdf.setFont(font, 6.7)
        pdf.drawString(LEFT + 259, y_top - 8, f"{row['breaches']}/{row['measured']}")
        pdf.drawString(LEFT + 335, y_top - 8, f"{row['rate']:.0f}%")
        _line(pdf, LEFT, y_top - 12, middle - 9, y_top - 12, PALE, .4)
    if not model["ranking"]:
        _paragraph(pdf, "Sin criterios medidos con brechas.", LEFT + 4, header_y - 10, 380, 20, font, 7.2)

    notes = []
    avg, target = model["average"], model["target"]
    if avg is not None:
        notes.append(f"La nota promedio del periodo fue {avg:.1f} de 100" +
                     (f", {abs(avg - target):.1f} puntos {'sobre' if avg >= target else 'bajo'} la meta." if target is not None else "."))
    if model["ranking"]:
        top_row = model["ranking"][0]
        notes.append(f"{top_row['name']} es el principal foco: {top_row['breaches']} de {top_row['measured']} mediciones presentan brecha.")
    if model["agents"]:
        agent = model["agents"][0]
        notes.append(f"Seguimiento inicial a {agent['name']}" +
                     (f" ({agent['score']:.1f} de promedio)." if agent["score"] is not None else " (sin nota evaluable)."))
    for index, note in enumerate(notes[:3]):
        y_top = header_y - 3 - index * 19
        pdf.setFillColor(NAVY)
        pdf.setFont(bold, 9)
        pdf.drawString(middle + 14, y_top - 9, str(index + 1))
        _paragraph(pdf, note, middle + 32, y_top - 1, RIGHT - middle - 40, 18, font, 6.9)


def _action_footer(pdf, model, font, bold, page=1):
    y = 19
    pdf.setFillColor(PALE)
    pdf.rect(LEFT, y - 12, WIDTH, 30, stroke=0, fill=1)
    pdf.setFillColor(NAVY)
    pdf.setFont(bold, 8.6)
    pdf.drawString(LEFT + 7, y + 7, "Plan de acción")
    focus = model["ranking"][0]["name"] if model["ranking"] else "Sin brechas medidas"
    _paragraph(pdf, f"Foco: {focus}", LEFT + 105, y + 13, 210, 22, font, 6.8)
    action = model["recommendation"] or "Coaching y seguimiento semanal."
    _paragraph(pdf, f"Acción sugerida: {action}", LEFT + 330, y + 13, WIDTH - 340, 22, font, 6.8)
    pdf.setFont(font, 6.5)
    pdf.setFillColor(MUTED)
    pdf.drawRightString(RIGHT - 6, y - 8, f"Página {page}")


def construir_informe_cartera_pdf(payload: dict) -> bytes:
    model = _model(payload)
    font, bold = _fonts()
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=(OUTPUT_W, OUTPUT_H), pageCompression=1)
    pdf.setTitle("Informe ejecutivo de calidad por cartera")

    _start_page(pdf)
    _header(pdf, model, font, bold)
    _kpis(pdf, model, font, bold)
    _chart(pdf, model["weeks"], LEFT + 2, 443, 420, 110, font, bold)
    _line(pdf, LEFT + 436, 441, LEFT + 436, 338)
    _highlights(pdf, model, LEFT + 448, 443, WIDTH - 448, 110, font, bold)
    _line(pdf, LEFT, 329, RIGHT, 329, NAVY, .65)
    agent_bottom = _agent_table(pdf, model, 314, font, bold, limit=5)
    _line(pdf, LEFT, agent_bottom - 7, RIGHT, agent_bottom - 7, NAVY, .65)
    _bottom(pdf, model, agent_bottom - 22, font, bold)
    _action_footer(pdf, model, font, bold)
    pdf.showPage()

    for page, offset in enumerate(range(5, len(model["agents"]), 20), start=2):
        _start_page(pdf)
        pdf.setFillColor(NAVY)
        pdf.setFont(bold, 18)
        pdf.drawString(LEFT, 555, "Informe ejecutivo de calidad · anexo de agentes")
        pdf.setFont(font, 8)
        pdf.drawString(LEFT, 535, f"{model['portfolio']} | {model['period']}")
        _line(pdf, LEFT, 524, RIGHT, 524, NAVY, .7)
        _agent_table(pdf, model, 507, font, bold, first=False, offset=offset, limit=20)
        _action_footer(pdf, model, font, bold, page=page)
        pdf.showPage()

    pdf.save()
    return buffer.getvalue()
