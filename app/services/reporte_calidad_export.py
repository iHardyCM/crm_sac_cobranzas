"""
Exportacion del reporte de calidad (Centro de Calidad IA) a Excel.

PARA QUE SIRVE
Llevar a gerencia, a la entidad o a una reunion de calibracion lo mismo que se
ve en pantalla, con el mismo filtro aplicado, en un archivo que se puede
auditar: cada numero del resumen se puede rastrear hasta sus filas.

DE DONDE SALEN LOS DATOS
Del navegador, ya filtrados. La pagina aplica los filtros (periodo, cartera,
supervisor...) sobre la reporteria y envia aqui las evaluaciones y los
criterios resultantes. Este modulo NO recalcula reglas de negocio: solo arma
el libro. Asi el Excel y la pantalla no pueden contar historias distintas.

COMO ESTA ORGANIZADO
  Resumen              periodo, filtros, meta y KPIs (formulas).
  Por cartera          nota, % en meta, error critico (formulas) y donde falla mas.
  Por supervisor       idem.
  Por agente           idem + tendencia y brecha que repite.
  Criterio x Cartera   % de cumplimiento por criterio (formulas) y N medidas.
  Criterio x Agente    idem por agente.
  Pareto               brechas por criterio con % acumulado (formulas).
  Evaluaciones         una fila por llamada (la base de todo lo anterior).
  Criterios            una fila por criterio evaluado en cada llamada.
  Definiciones         como se calcula cada indicador.

Los agregados son FORMULAS sobre las hojas de detalle, no numeros calculados
en Python: si alguien corrige una fila o cambia la meta en Resumen, todo se
recalcula. Lo que no es agregable con una formula simple (tendencia, brecha que
repite, "donde falla mas") viaja como valor ya calculado por la pagina y se
rotula como tal.

No inventa datos: lo que no viene en el payload queda vacio.
"""

from __future__ import annotations

from datetime import datetime
from io import BytesIO
from typing import Dict, List, Optional

from openpyxl import Workbook
from openpyxl.formatting.rule import CellIsRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

FUENTE = "Arial"
AZUL_TITULO = "0D355B"
AZUL_CABECERA = "1F4E79"
GRIS_BORDE = "D5DEE8"
VERDE_FONDO, VERDE_TEXTO = "E3F4E9", "17633A"
AMBAR_FONDO, AMBAR_TEXTO = "FDF0D9", "8A5A0B"
ROJO_FONDO, ROJO_TEXTO = "FBE2E2", "A8323C"

BORDE = Border(bottom=Side(style="thin", color=GRIS_BORDE))
CABECERA_FILL = PatternFill("solid", fgColor=AZUL_CABECERA)
CABECERA_FONT = Font(name=FUENTE, bold=True, color="FFFFFF", size=10)
TEXTO = Font(name=FUENTE, size=10)
NEGRITA = Font(name=FUENTE, size=10, bold=True)
NOTA = Font(name=FUENTE, size=9, italic=True, color="5F7488")
INPUT_FONT = Font(name=FUENTE, size=11, bold=True, color="0000FF")
INPUT_FILL = PatternFill("solid", fgColor="FFFF00")

# Celda de la meta en Resumen: todas las formulas de "en meta" la referencian.
META_REF = "Resumen!$C$6"

COLS_EVAL = [
    ("id_feedback", "ID", 9),
    ("fecha", "Fecha llamada", 17),
    ("cartera", "Cartera", 26),
    ("agente", "Agente", 32),
    ("supervisor", "Supervisor", 28),
    ("tipo_llamada", "Tipo de llamada", 20),
    ("nota", "Nota vigente", 12),
    ("origen", "Origen de la nota", 14),
    ("nota_ia", "Nota IA", 10),
    ("evaluable", "Evaluable", 10),
    (None, "En meta", 9),  # formula
    ("error_critico", "Error crítico", 12),
    ("estado_revision", "Revisión supervisor", 16),
    ("ia_pide_revision", "IA pide revisión", 14),
    ("brechas", "Brechas (No cumple / Parcial)", 50),
    ("observacion", "Observación supervisor", 40),
]
COLS_CRIT = [
    ("id_feedback", "ID", 9),
    ("fecha", "Fecha llamada", 17),
    ("cartera", "Cartera", 26),
    ("agente", "Agente", 32),
    ("supervisor", "Supervisor", 28),
    ("tipo_llamada", "Tipo de llamada", 20),
    ("bloque", "Bloque", 9),
    ("bloque_nombre", "Nombre del bloque", 34),
    ("codigo", "Código", 10),
    ("criterio", "Criterio", 34),
    ("peso", "Peso", 7),
    ("nota", "Puntos", 8),
    ("resultado", "Resultado", 16),
    ("medido", "Medido (1/0)", 11),
    ("cumple", "Cumple (1/0)", 11),
    ("brecha", "Brecha (1/0)", 11),
]


def _col(cols, key: str) -> str:
    for i, (k, _h, _w) in enumerate(cols, start=1):
        if k == key:
            return get_column_letter(i)
    raise KeyError(key)


def _cabecera(ws: Worksheet, fila: int, titulos: List[str], anchos: Optional[List[int]] = None) -> None:
    for i, titulo in enumerate(titulos, start=1):
        c = ws.cell(row=fila, column=i, value=titulo)
        c.font = CABECERA_FONT
        c.fill = CABECERA_FILL
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        if anchos:
            ws.column_dimensions[get_column_letter(i)].width = anchos[i - 1]
    ws.row_dimensions[fila].height = 30


def _titulo(ws: Worksheet, texto: str, subtitulo: str = "") -> None:
    ws["A1"] = texto
    ws["A1"].font = Font(name=FUENTE, size=14, bold=True, color=AZUL_TITULO)
    if subtitulo:
        ws["A2"] = subtitulo
        ws["A2"].font = NOTA


def _colores_pct(ws: Worksheet, rango: str) -> None:
    """Semaforo contra la meta de Resumen (verde >= meta, ambar >= 70, rojo)."""
    ws.conditional_formatting.add(rango, CellIsRule(operator="greaterThanOrEqual", formula=[f"{META_REF}/100"],
                                                    fill=PatternFill("solid", fgColor=VERDE_FONDO), font=Font(name=FUENTE, color=VERDE_TEXTO, bold=True)))
    ws.conditional_formatting.add(rango, CellIsRule(operator="between", formula=["0.7", f"{META_REF}/100-0.0001"],
                                                    fill=PatternFill("solid", fgColor=AMBAR_FONDO), font=Font(name=FUENTE, color=AMBAR_TEXTO, bold=True)))
    ws.conditional_formatting.add(rango, CellIsRule(operator="lessThan", formula=["0.7"],
                                                    fill=PatternFill("solid", fgColor=ROJO_FONDO), font=Font(name=FUENTE, color=ROJO_TEXTO, bold=True)))


def _escribir_detalle(ws: Worksheet, cols, filas: List[Dict], titulo: str, subtitulo: str) -> int:
    _titulo(ws, titulo, subtitulo)
    _cabecera(ws, 4, [h for _k, h, _w in cols], [w for _k, _h, w in cols])
    for r, fila in enumerate(filas, start=5):
        for c, (k, _h, _w) in enumerate(cols, start=1):
            if k is None:
                continue
            valor = fila.get(k)
            if k == "fecha" and isinstance(valor, str) and valor:
                try:
                    valor = datetime.fromisoformat(valor.replace("Z", "+00:00")).replace(tzinfo=None)
                except ValueError:
                    pass
            celda = ws.cell(row=r, column=c, value=valor if valor != "" else None)
            celda.font = TEXTO
            if k == "fecha" and isinstance(valor, datetime):
                celda.number_format = "dd/mm/yyyy hh:mm"
    ultima = max(5, 4 + len(filas))
    ws.freeze_panes = "B5"
    ws.auto_filter.ref = f"A4:{get_column_letter(len(cols))}{ultima}"
    return ultima


def _rango(hoja: str, col: str, ultima: int) -> str:
    return f"'{hoja}'!${col}$5:${col}${ultima}"


def construir_reporte_calidad_excel(payload: Dict) -> bytes:
    evaluaciones: List[Dict] = payload.get("evaluaciones") or []
    criterios: List[Dict] = payload.get("criterios") or []
    meta = float(payload.get("meta") or 85)

    wb = Workbook()
    ws_res = wb.active
    ws_res.title = "Resumen"
    hojas = {n: wb.create_sheet(n) for n in ["Por cartera", "Por supervisor", "Por agente", "Criterio x Cartera",
                                             "Criterio x Agente", "Pareto", "Evaluaciones", "Criterios", "Definiciones"]}

    # --- detalle primero: todo lo demas lo referencia
    ult_e = _escribir_detalle(hojas["Evaluaciones"], COLS_EVAL, evaluaciones, "Evaluaciones",
                              "Una fila por llamada del periodo filtrado. Nota vacía = No evaluable.")
    ws_e = hojas["Evaluaciones"]
    c_nota, c_meta = _col(COLS_EVAL, "nota"), get_column_letter(11)
    for r in range(5, 5 + len(evaluaciones)):
        ws_e[f"{c_meta}{r}"] = f'=IF({c_nota}{r}="","",IF({c_nota}{r}>={META_REF},"Sí","No"))'
        ws_e[f"{c_meta}{r}"].font = TEXTO
        ws_e[f"{c_nota}{r}"].number_format = "0.0"
        ws_e[f"{_col(COLS_EVAL, 'nota_ia')}{r}"].number_format = "0.0"
        ws_e[f"{_col(COLS_EVAL, 'brechas')}{r}"].alignment = Alignment(wrap_text=True, vertical="top")

    ult_c = _escribir_detalle(hojas["Criterios"], COLS_CRIT, criterios, "Criterios por evaluación",
                              "Medido = Cumple, No cumple o Parcial. No aplica, No evaluable y Requiere revisión quedan con Medido = 0.")

    E = lambda key: _rango("Evaluaciones", _col(COLS_EVAL, key), ult_e)  # noqa: E731
    E_META = _rango("Evaluaciones", c_meta, ult_e)
    C = lambda key: _rango("Criterios", _col(COLS_CRIT, key), ult_c)  # noqa: E731

    # --- Resumen
    _titulo(ws_res, "Reporte de calidad — Centro de Calidad IA", f"Generado el {datetime.now():%d/%m/%Y %H:%M}"
            + (f" por {payload.get('generado_por')}" if payload.get("generado_por") else ""))
    ws_res.column_dimensions["A"].width = 3
    ws_res.column_dimensions["B"].width = 38
    ws_res.column_dimensions["C"].width = 26
    ws_res.column_dimensions["D"].width = 60
    ws_res["B4"], ws_res["C4"] = "Periodo", payload.get("periodo") or "Sin filtro de fecha"
    ws_res["B5"], ws_res["C5"] = "Filtros", "; ".join(f"{a}: {b}" for a, b in (payload.get("filtros") or [])) or "Ninguno"
    ws_res["B6"], ws_res["C6"] = "Meta de calidad (%)", meta
    ws_res["C6"].font, ws_res["C6"].fill = INPUT_FONT, INPUT_FILL
    ws_res["D6"] = "Editable: todas las columnas «en meta» y los colores usan esta celda."
    ws_res["D6"].font = NOTA
    for celda in ("B4", "B5", "B6"):
        ws_res[celda].font = NEGRITA
    _cabecera(ws_res, 8, ["", "Indicador", "Valor", "Cómo se calcula"])
    kpis = [
        ("Evaluaciones", f"=COUNTA({E('id_feedback')})", "0", "Llamadas del periodo filtrado."),
        ("Con nota", f"=COUNT({E('nota')})", "0", "Excluye las No evaluables."),
        ("No evaluables", "=C9-C10", "0", "Sin ningún criterio medible: fuera de los promedios."),
        ("Nota promedio", f"=IFERROR(AVERAGE({E('nota')}),\"\")", "0.0", "Promedio de la nota vigente (calibrada si Calidad la publicó)."),
        ("% en meta", f"=IFERROR(COUNTIF({E_META},\"Sí\")/C10,\"\")", "0.0%", "Evaluaciones con nota ≥ meta, sobre las que tienen nota."),
        ("Con error crítico", f"=COUNTIF({E('error_critico')},\"Sí\")", "0", "Error crítico, falta anulante o punto crítico."),
        ("Por revisar", f"=COUNTIF({E('estado_revision')},\"Por revisar\")", "0", "Sin cierre del supervisor."),
        ("Sin agente", f"=COUNTIF({E('agente')},\"Sin agente\")", "0", "No cuentan para ningún agente."),
        ("Criterios medidos (actos)", f"=SUM({C('medido')})", "0", "Criterio × llamada con resultado Cumple/No cumple/Parcial."),
        ("% de cumplimiento de criterios", f"=IFERROR(SUM({C('cumple')})/C17,\"\")", "0.0%", "Cumple / medidos."),
    ]
    for i, (nombre, formula, fmt, como) in enumerate(kpis, start=9):
        ws_res[f"B{i}"], ws_res[f"C{i}"], ws_res[f"D{i}"] = nombre, formula, como
        ws_res[f"B{i}"].font, ws_res[f"C{i}"].font, ws_res[f"D{i}"].font = NEGRITA, TEXTO, NOTA
        ws_res[f"C{i}"].number_format = fmt
        for col in "BCD":
            ws_res[f"{col}{i}"].border = BORDE
    ws_res["B21"] = "Las hojas «Por …» y «Criterio x …» se calculan con fórmulas sobre las hojas Evaluaciones y Criterios."
    ws_res["B21"].font = NOTA

    # --- Por cartera / supervisor / agente
    foco = payload.get("foco") or {}

    def hoja_grupo(ws: Worksheet, clave: str, etiqueta: str, extras: Optional[Dict[str, Dict]] = None) -> None:
        grupos = foco.get(clave) or []
        _titulo(ws, f"Por {etiqueta.lower()}", "Nota, % en meta y error crítico con fórmulas; «Dónde falla más» es el cálculo de la página (criterios con mayor % de falla).")
        titulos = [etiqueta, "Evaluaciones", "Con nota", "Nota promedio", "vs meta (pp)", "% en meta", "Con error crítico"]
        anchos = [34, 12, 10, 13, 12, 11, 13]
        if extras is not None:
            titulos += ["Tendencia (pp)", "Brecha que repite"]
            anchos += [13, 34]
        titulos += ["Dónde falla más (1)", "Dónde falla más (2)", "Dónde falla más (3)"]
        anchos += [36, 36, 36]
        _cabecera(ws, 4, titulos, anchos)
        col_e = _col(COLS_EVAL, clave)
        for r, g in enumerate(grupos, start=5):
            ws.cell(row=r, column=1, value=g.get("grupo")).font = NEGRITA
            ref = f"$A{r}"
            ws.cell(row=r, column=2, value=f"=COUNTIF({_rango('Evaluaciones', col_e, ult_e)},{ref})")
            ws.cell(row=r, column=3, value=f"=COUNTIFS({_rango('Evaluaciones', col_e, ult_e)},{ref},{E('nota')},\"<>\")")
            ws.cell(row=r, column=4, value=f"=IFERROR(AVERAGEIFS({E('nota')},{_rango('Evaluaciones', col_e, ult_e)},{ref}),\"\")").number_format = "0.0"
            ws.cell(row=r, column=5, value=f"=IF(D{r}=\"\",\"\",D{r}-{META_REF})").number_format = "+0.0;-0.0;0.0"
            ws.cell(row=r, column=6, value=f"=IFERROR(COUNTIFS({_rango('Evaluaciones', col_e, ult_e)},{ref},{E_META},\"Sí\")/C{r},\"\")").number_format = "0%"
            ws.cell(row=r, column=7, value=f"=COUNTIFS({_rango('Evaluaciones', col_e, ult_e)},{ref},{E('error_critico')},\"Sí\")")
            c = 8
            if extras is not None:
                ex = extras.get(g.get("grupo")) or {}
                t = ex.get("tendencia")
                ws.cell(row=r, column=c, value=t if t is not None else "sin base").number_format = "+0.0;-0.0;0.0"
                ws.cell(row=r, column=c + 1, value=ex.get("brecha_repite") or "")
                c += 2
            for j, txt in enumerate((g.get("top") or [])[:3]):
                ws.cell(row=r, column=c + j, value=txt).alignment = Alignment(wrap_text=True, vertical="top")
            for col in range(1, len(titulos) + 1):
                ws.cell(row=r, column=col).border = BORDE
                ws.cell(row=r, column=col).font = NEGRITA if col == 1 else TEXTO
        if grupos:
            ult = 4 + len(grupos)
            ws.conditional_formatting.add(f"D5:D{ult}", CellIsRule(operator="lessThan", formula=[META_REF], font=Font(name=FUENTE, color=ROJO_TEXTO, bold=True)))
            ws.auto_filter.ref = f"A4:{get_column_letter(len(titulos))}{ult}"
        ws.freeze_panes = "B5"

    hoja_grupo(hojas["Por cartera"], "cartera", "Cartera")
    hoja_grupo(hojas["Por supervisor"], "supervisor", "Supervisor")
    extras_ag = {a.get("agente"): a for a in (payload.get("agentes") or [])}
    hoja_grupo(hojas["Por agente"], "agente", "Agente", extras_ag)

    # --- matrices criterio x grupo
    criterios_catalogo = payload.get("catalogo_criterios") or []

    def matriz(ws: Worksheet, clave: str, etiqueta: str) -> None:
        grupos = [g.get("grupo") for g in (foco.get(clave) or [])]
        _titulo(ws, f"Cumplimiento por criterio y {etiqueta.lower()}",
                "% = llamadas que cumplen / llamadas donde el criterio se midió. Vacío = no se midió. Debajo, el N de medidas de cada celda.")
        _cabecera(ws, 4, ["Código", "Criterio"] + grupos + ["Total"], [10, 36] + [16] * len(grupos) + [12])
        col_g = _col(COLS_CRIT, clave)
        n = len(criterios_catalogo)
        fila_n = 4 + n + 3
        ws.cell(row=fila_n - 1, column=1, value="N de medidas por celda").font = NEGRITA
        _cabecera(ws, fila_n, ["Código", "Criterio"] + grupos + ["Total"])
        for i, crit in enumerate(criterios_catalogo):
            r, rn = 5 + i, fila_n + 1 + i
            for fila in (r, rn):
                ws.cell(row=fila, column=1, value=crit.get("codigo")).font = NEGRITA
                ws.cell(row=fila, column=2, value=crit.get("criterio")).font = TEXTO
            cond_cod = f"{C('codigo')},$A{r}"
            for j in range(len(grupos) + 1):
                col = get_column_letter(3 + j)
                if j < len(grupos):
                    cond = f"{cond_cod},{_rango('Criterios', col_g, ult_c)},{col}$4"
                else:
                    cond = cond_cod
                ws[f"{col}{r}"] = f"=IFERROR(COUNTIFS({cond},{C('cumple')},1)/COUNTIFS({cond},{C('medido')},1),\"\")"
                ws[f"{col}{r}"].number_format = "0%"
                ws[f"{col}{r}"].alignment = Alignment(horizontal="center")
                cond_n = cond.replace(f"$A{r}", f"$A{rn}").replace(f"{col}$4", f"{col}${fila_n}")
                ws[f"{col}{rn}"] = f"=COUNTIFS({cond_n},{C('medido')},1)"
                ws[f"{col}{rn}"].alignment = Alignment(horizontal="center")
                ws[f"{col}{rn}"].font = TEXTO
        if n:
            _colores_pct(ws, f"C5:{get_column_letter(3 + len(grupos))}{4 + n}")
        ws.freeze_panes = "C5"

    matriz(hojas["Criterio x Cartera"], "cartera", "Cartera")
    matriz(hojas["Criterio x Agente"], "agente", "Agente")

    # --- Pareto
    ws_p = hojas["Pareto"]
    _titulo(ws_p, "Pareto de brechas", "Brecha = No cumple o Parcial. Ordenado por número de brechas al momento de exportar.")
    _cabecera(ws_p, 4, ["Código", "Criterio", "Medidas", "Brechas", "% de falla", "% del total de brechas", "% acumulado"], [10, 36, 10, 10, 11, 16, 13])
    orden = payload.get("pareto") or []
    for i, crit in enumerate(orden):
        r = 5 + i
        ws_p[f"A{r}"], ws_p[f"B{r}"] = crit.get("codigo"), crit.get("criterio")
        ws_p[f"A{r}"].font = NEGRITA
        ws_p[f"C{r}"] = f"=COUNTIFS({C('codigo')},$A{r},{C('medido')},1)"
        ws_p[f"D{r}"] = f"=COUNTIFS({C('codigo')},$A{r},{C('brecha')},1)"
        ws_p[f"E{r}"] = f"=IFERROR(D{r}/C{r},\"\")"
        ws_p[f"F{r}"] = f"=IFERROR(D{r}/SUM($D$5:$D${4 + len(orden)}),\"\")"
        ws_p[f"G{r}"] = f"=IFERROR(SUM($D$5:D{r})/SUM($D$5:$D${4 + len(orden)}),\"\")"
        for col in "EFG":
            ws_p[f"{col}{r}"].number_format = "0.0%"
    ws_p.freeze_panes = "C5"

    # --- Definiciones
    ws_d = hojas["Definiciones"]
    _titulo(ws_d, "Definiciones")
    ws_d.column_dimensions["A"].width = 30
    ws_d.column_dimensions["B"].width = 110
    defs = [
        ("Nota vigente", "La nota de la llamada que cuenta: la calibrada si Calidad la publicó; si no, la de la IA."),
        ("No evaluable", "Llamada sin ningún criterio medible. Queda fuera de promedios y porcentajes y se cuenta aparte."),
        ("Criterio medido", "Resultado Cumple, No cumple o Parcial. No aplica, No evaluable y Requiere revisión no entran a ningún %."),
        ("Brecha", "Criterio medido con resultado No cumple o Parcial."),
        ("% de cumplimiento", "Llamadas donde el criterio cumple / llamadas donde se midió."),
        ("% en meta", "Evaluaciones con nota ≥ meta (Resumen!C6) / evaluaciones con nota."),
        ("Dónde falla más", "Los 3 criterios con mayor % de falla del grupo, con falla/medidas y la diferencia contra el % de falla de todo el periodo."),
        ("Tendencia", "Promedio de las 3 últimas notas del agente menos el de las 3 anteriores. «sin base» si no hay al menos 2 y 2."),
        ("Brecha que repite", "Regla acordada: el agente falla el mismo criterio 2+ veces en sus últimas 5 mediciones de ese criterio, con al menos 3 mediciones."),
        ("Base chica", "Menos de 3 medidas: el % existe pero no es concluyente."),
    ]
    for i, (a, b) in enumerate(defs, start=3):
        ws_d[f"A{i}"], ws_d[f"B{i}"] = a, b
        ws_d[f"A{i}"].font, ws_d[f"B{i}"].font = NEGRITA, TEXTO
        ws_d[f"B{i}"].alignment = Alignment(wrap_text=True, vertical="top")

    for ws in wb.worksheets:
        ws.sheet_view.showGridLines = False
    wb.calculation.fullCalcOnLoad = True
    salida = BytesIO()
    wb.save(salida)
    return salida.getvalue()
