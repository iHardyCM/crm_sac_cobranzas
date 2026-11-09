"""
Exportacion de una pauta de evaluacion a Excel.

PARA QUE SIRVE
La pauta vive repartida en tres tablas y solo se puede leer completa dentro del
editor, un criterio a la vez. Este export la entrega en un archivo que se puede
revisar de corrido, comentar con Calidad o enviar a la entidad.

COMO ESTA ORGANIZADO
Tres hojas, separadas por como se leen y no por como estan guardadas:

  1. Pauta      cabecera de la version y reparto de peso por bloque.
  2. Criterios  una fila por criterio, con lo que se mira de un vistazo:
                peso, criticidad, fuente de evidencia y marcas.
  3. Reglas     los textos largos -cuando cumple, cuando no cumple,
                aplicabilidad-. Van aparte a proposito: mezclados con la hoja
                anterior la convierten en un muro de texto imposible de barrer.

El total de peso se escribe como formula, no como numero calculado en Python:
si alguien edita un peso en el Excel, el total se recalcula solo en vez de
quedar contradiciendo a sus propias filas.

No inventa datos: lo que no esta en la pauta queda vacio.
"""

from __future__ import annotations

from datetime import datetime
from io import BytesIO
from typing import Dict, List, Optional

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter


FUENTE = "Arial"

AZUL_TITULO = "0D355B"
AZUL_CABECERA = "1F4E79"
GRIS_ETIQUETA = "EEF4FB"
GRIS_BORDE = "D0DCE8"
FILA_ALTERNA = "F7FAFD"

# Etiquetas legibles de los valores que guarda la base. Si aparece un valor no
# contemplado se muestra tal cual, en vez de ocultarlo tras un texto generico.
ETIQUETAS_CRITICIDAD = {
    "ERROR_CRITICO_CUMPLIMIENTO": "Error crítico de cumplimiento",
    "ERROR_CRITICO_NEGOCIO": "Error crítico del negocio",
    "ERROR_CRITICO_USUARIO_FINAL": "Error crítico de usuario final",
    "ERROR_NO_CRITICO": "Error no crítico",
}

ETIQUETAS_FUENTE = {
    "AUDIO": "Audio",
    "TRANSCRIPCION": "Transcripción",
    "CRM": "CRM",
    "TIPIFICACION": "Tipificación",
    "CAMPANIA": "Campaña",
    "SISTEMA": "Sistema",
    "MULTIFUENTE": "Multifuente",
}

ETIQUETAS_TIPO = {
    "PUNTUABLE": "Puntuable",
    "ANULANTE_BLOQUE": "Anulante de bloque",
}

ETIQUETAS_ESTADO = {
    "BORRADOR": "Borrador",
    "PUBLICADA": "Publicada",
    "ARCHIVADA": "Archivada",
}


def _etiqueta(valor, mapa: Dict[str, str]) -> str:
    texto = str(valor or "").strip()
    if not texto:
        return ""
    return mapa.get(texto.upper(), texto)


def _fecha_legible(valor) -> str:
    """Las fechas llegan en ISO desde obtener_pauta; se muestran dd/mm/aaaa."""
    texto = str(valor or "").strip()
    if not texto:
        return ""
    for formato in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(texto[:19] if "T" in texto else texto, formato).strftime("%d/%m/%Y")
        except ValueError:
            continue
    return texto


def _borde_suave() -> Border:
    lado = Side(style="thin", color=GRIS_BORDE)
    return Border(left=lado, right=lado, top=lado, bottom=lado)


def _escribir_cabecera(hoja, fila: int, columnas: List[str]) -> None:
    relleno = PatternFill("solid", fgColor=AZUL_CABECERA)
    for indice, titulo in enumerate(columnas, start=1):
        celda = hoja.cell(row=fila, column=indice, value=titulo)
        celda.font = Font(name=FUENTE, size=10, bold=True, color="FFFFFF")
        celda.fill = relleno
        celda.alignment = Alignment(vertical="center", horizontal="left", wrap_text=True)
        celda.border = _borde_suave()
    hoja.row_dimensions[fila].height = 28


def _aplicar_anchos(hoja, anchos: List[int]) -> None:
    for indice, ancho in enumerate(anchos, start=1):
        hoja.column_dimensions[get_column_letter(indice)].width = ancho


def _hoja_pauta(libro: Workbook, pauta: Dict, carteras: Optional[List[Dict]] = None) -> None:
    hoja = libro.active
    hoja.title = "Pauta"
    hoja.sheet_view.showGridLines = False
    _aplicar_anchos(hoja, [28, 46, 16, 14, 14, 14])

    titulo = hoja.cell(row=1, column=1, value=str(pauta.get("nombre") or "Pauta de evaluación"))
    titulo.font = Font(name=FUENTE, size=16, bold=True, color=AZUL_TITULO)
    hoja.cell(row=2, column=1, value=f"Versión {pauta.get('version') or '-'}").font = Font(
        name=FUENTE, size=11, color="4A6480"
    )
    hoja.cell(
        row=3, column=1,
        value=f"Exportado el {datetime.now():%d/%m/%Y %H:%M}",
    ).font = Font(name=FUENTE, size=9, italic=True, color="8496A8")

    if pauta.get("aplica_todas"):
        alcance = "Todas las carteras"
    else:
        nombres = {int(c["idcartera"]): str(c.get("cartera") or c["idcartera"]) for c in (carteras or []) if c.get("idcartera") is not None}
        ids = pauta.get("idcarteras") or []
        alcance = ", ".join(nombres.get(int(i), str(i)) for i in ids) if ids else "Sin carteras asignadas"
        if pauta.get("grupo_nombre"):
            alcance = f"{pauta['grupo_nombre']}: {alcance}"

    datos = [
        ("Estado", _etiqueta(pauta.get("estado"), ETIQUETAS_ESTADO)),
        ("Vigencia desde", _fecha_legible(pauta.get("vigencia_desde"))),
        ("Vigencia hasta", _fecha_legible(pauta.get("vigencia_hasta"))),
        ("Alcance", alcance),
        ("Descripción", str(pauta.get("descripcion") or "")),
        ("Última actualización", _fecha_legible(pauta.get("fecha_actualizacion"))),
    ]
    fila = 5
    for etiqueta, valor in datos:
        celda_etq = hoja.cell(row=fila, column=1, value=etiqueta)
        celda_etq.font = Font(name=FUENTE, size=10, bold=True, color="23405F")
        celda_etq.fill = PatternFill("solid", fgColor=GRIS_ETIQUETA)
        celda_etq.alignment = Alignment(vertical="top")
        celda_etq.border = _borde_suave()

        celda_val = hoja.cell(row=fila, column=2, value=valor)
        celda_val.font = Font(name=FUENTE, size=10)
        celda_val.alignment = Alignment(vertical="top", wrap_text=True)
        celda_val.border = _borde_suave()
        if etiqueta in {"Descripción", "Alcance"} and len(str(valor)) > 60:
            hoja.row_dimensions[fila].height = 32
        fila += 1

    fila += 1
    encabezado = hoja.cell(row=fila, column=1, value="Reparto de peso por bloque")
    encabezado.font = Font(name=FUENTE, size=12, bold=True, color=AZUL_TITULO)
    fila += 1

    _escribir_cabecera(hoja, fila, ["Código", "Bloque", "Criterios", "Peso", "% del total"])
    primera_fila_datos = fila + 1

    bloques = [b for b in (pauta.get("bloques") or []) if b.get("activo", True)]
    for bloque in bloques:
        fila += 1
        criterios = [c for c in (bloque.get("criterios") or []) if c.get("activo", True)]
        puntuables = [c for c in criterios if str(c.get("tipo_criterio") or "PUNTUABLE").upper() == "PUNTUABLE"]
        peso = sum(float(c.get("peso") or 0) for c in puntuables)
        valores = [
            str(bloque.get("codigo") or ""),
            str(bloque.get("nombre") or ""),
            len(criterios),
            peso,
            None,  # formula, se escribe abajo
        ]
        for indice, valor in enumerate(valores, start=1):
            celda = hoja.cell(row=fila, column=indice, value=valor)
            celda.font = Font(name=FUENTE, size=10)
            celda.border = _borde_suave()
            celda.alignment = Alignment(vertical="center", wrap_text=(indice == 2))
        hoja.cell(row=fila, column=4).number_format = "0.00"

    ultima_fila_datos = fila
    fila_total = fila + 1

    # El % de cada bloque y el total son formulas: si alguien corrige un peso en
    # el Excel, los numeros de abajo siguen cuadrando en vez de contradecirlo.
    for f in range(primera_fila_datos, ultima_fila_datos + 1):
        celda = hoja.cell(row=f, column=5, value=f"=IFERROR(D{f}/$D${fila_total},0)")
        celda.number_format = "0.0%"
        celda.font = Font(name=FUENTE, size=10)
        celda.border = _borde_suave()
        celda.alignment = Alignment(vertical="center")

    etiqueta_total = hoja.cell(row=fila_total, column=1, value="TOTAL")
    etiqueta_total.font = Font(name=FUENTE, size=10, bold=True, color=AZUL_TITULO)
    hoja.cell(row=fila_total, column=2, value="Peso puntuable de la pauta").font = Font(
        name=FUENTE, size=10, bold=True, color=AZUL_TITULO
    )
    celda_criterios = hoja.cell(
        row=fila_total, column=3,
        value=f"=SUM(C{primera_fila_datos}:C{ultima_fila_datos})" if bloques else 0,
    )
    celda_peso = hoja.cell(
        row=fila_total, column=4,
        value=f"=SUM(D{primera_fila_datos}:D{ultima_fila_datos})" if bloques else 0,
    )
    celda_peso.number_format = "0.00"
    for columna in range(1, 6):
        celda = hoja.cell(row=fila_total, column=columna)
        celda.font = Font(name=FUENTE, size=10, bold=True, color=AZUL_TITULO)
        celda.fill = PatternFill("solid", fgColor=GRIS_ETIQUETA)
        celda.border = _borde_suave()
    celda_criterios.alignment = Alignment(vertical="center")

    nota = hoja.cell(
        row=fila_total + 2, column=1,
        value="El peso puntuable debe sumar 100 para que la pauta pueda publicarse. "
              "Los criterios anulantes de bloque no suman peso.",
    )
    nota.font = Font(name=FUENTE, size=9, italic=True, color="6D8399")


def _hoja_criterios(libro: Workbook, pauta: Dict) -> None:
    hoja = libro.create_sheet("Criterios")
    hoja.sheet_view.showGridLines = False
    columnas = [
        "Bloque", "Nombre del bloque", "Código", "Criterio", "Peso", "Tipo",
        "Criticidad", "Fuente de evidencia", "Evidencia obligatoria",
        "Puede descalificar", "Detalle",
    ]
    _aplicar_anchos(hoja, [10, 34, 12, 34, 8, 16, 28, 18, 14, 14, 46])
    _escribir_cabecera(hoja, 1, columnas)

    fila = 1
    for bloque in (pauta.get("bloques") or []):
        if not bloque.get("activo", True):
            continue
        for criterio in (bloque.get("criterios") or []):
            if not criterio.get("activo", True):
                continue
            fila += 1
            valores = [
                str(bloque.get("codigo") or ""),
                str(bloque.get("nombre") or ""),
                str(criterio.get("codigo_criterio") or ""),
                str(criterio.get("nombre") or ""),
                float(criterio.get("peso") or 0),
                _etiqueta(criterio.get("tipo_criterio") or "PUNTUABLE", ETIQUETAS_TIPO),
                _etiqueta(criterio.get("criticidad"), ETIQUETAS_CRITICIDAD),
                _etiqueta(criterio.get("fuente_evidencia"), ETIQUETAS_FUENTE),
                "Sí" if criterio.get("requiere_evidencia") else "No",
                "Sí" if criterio.get("puede_descalificar") else "No",
                str(criterio.get("detalle") or ""),
            ]
            for indice, valor in enumerate(valores, start=1):
                celda = hoja.cell(row=fila, column=indice, value=valor)
                celda.font = Font(name=FUENTE, size=10)
                celda.alignment = Alignment(vertical="top", wrap_text=indice in {2, 4, 11})
                celda.border = _borde_suave()
                if fila % 2 == 0:
                    celda.fill = PatternFill("solid", fgColor=FILA_ALTERNA)
            hoja.cell(row=fila, column=5).number_format = "0.00"
            hoja.row_dimensions[fila].height = 30

    hoja.freeze_panes = "A2"
    if fila > 1:
        hoja.auto_filter.ref = f"A1:{get_column_letter(len(columnas))}{fila}"


def _hoja_reglas(libro: Workbook, pauta: Dict) -> None:
    hoja = libro.create_sheet("Reglas")
    hoja.sheet_view.showGridLines = False
    columnas = [
        "Código", "Criterio", "Cuándo cumple", "Cuándo no cumple",
        "Aplicabilidad / No aplica", "Regla de evaluación", "Recomendación sugerida",
    ]
    _aplicar_anchos(hoja, [12, 30, 52, 52, 52, 52, 44])
    _escribir_cabecera(hoja, 1, columnas)

    fila = 1
    for bloque in (pauta.get("bloques") or []):
        if not bloque.get("activo", True):
            continue
        for criterio in (bloque.get("criterios") or []):
            if not criterio.get("activo", True):
                continue
            fila += 1
            valores = [
                str(criterio.get("codigo_criterio") or ""),
                str(criterio.get("nombre") or ""),
                str(criterio.get("regla_cumple") or ""),
                str(criterio.get("regla_no_cumple") or ""),
                str(criterio.get("regla_aplicabilidad") or ""),
                str(criterio.get("regla_evaluacion") or ""),
                str(criterio.get("recomendacion") or ""),
            ]
            for indice, valor in enumerate(valores, start=1):
                celda = hoja.cell(row=fila, column=indice, value=valor)
                celda.font = Font(name=FUENTE, size=10)
                celda.alignment = Alignment(vertical="top", wrap_text=True)
                celda.border = _borde_suave()
                if fila % 2 == 0:
                    celda.fill = PatternFill("solid", fgColor=FILA_ALTERNA)
            # Alto en funcion del texto mas largo de la fila, acotado para que
            # una regla extensa no deje una fila de media pantalla.
            largo = max((len(str(v)) for v in valores[2:]), default=0)
            hoja.row_dimensions[fila].height = min(140, max(34, (largo // 52 + 1) * 15))

    hoja.freeze_panes = "C2"


def construir_excel_pauta(pauta: Dict, carteras: Optional[List[Dict]] = None) -> bytes:
    """Devuelve el .xlsx de la pauta como bytes, listo para descargar."""
    libro = Workbook()
    _hoja_pauta(libro, pauta, carteras)
    _hoja_criterios(libro, pauta)
    _hoja_reglas(libro, pauta)
    buffer = BytesIO()
    libro.save(buffer)
    return buffer.getvalue()


def nombre_archivo_pauta(pauta: Dict) -> str:
    """Nombre de archivo seguro en Windows, sin acentos raros ni separadores."""
    base = str(pauta.get("nombre") or "pauta").strip() or "pauta"
    limpio = "".join(c if (c.isalnum() or c in " -_") else " " for c in base)
    limpio = "_".join(limpio.split())[:70]
    version = pauta.get("version")
    sufijo = f"_v{version}" if version is not None else ""
    return f"{limpio}{sufijo}_{datetime.now():%Y%m%d}.xlsx"
