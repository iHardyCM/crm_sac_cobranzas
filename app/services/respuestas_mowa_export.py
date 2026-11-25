"""Exportación Excel de las conversaciones SMS cargadas y filtradas en la vista."""

from __future__ import annotations

from io import BytesIO
from zoneinfo import ZoneInfo
from datetime import datetime

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter


ENCABEZADOS_CLIENTES = [
    "Estado conversación", "Cartera", "ID cliente", "DNI", "Cliente", "Celulares",
    "Cuentas", "Respuestas", "SMS pendientes", "Primera recepción", "Última recepción",
    "Fecha del SMS enviado", "SMS enviado (al que respondió)",
    "Última respuesta", "Gestión posterior", "Texto de gestión",
]
ENCABEZADOS_RESPUESTAS = [
    "Cartera", "ID cliente", "DNI", "Cliente", "Celular", "Cuenta", "Campaña",
    "ID campaña", "ID respuesta", "Recepción", "Respuesta", "Estado CRM",
    "Estado Mowa", "ID mensaje enviado", "Fecha envío", "Mensaje enviado",
    "Gestión posterior", "ID gestión", "Texto de gestión", "Motivo",
]


def _texto(valor):
    return "" if valor is None else str(valor)


def _fila(hoja, valores, numericas=frozenset()):
    hoja.append([v if i in numericas and isinstance(v, int) else _texto(v)
                 for i, v in enumerate(valores, 1)])
    # Forzar texto evita que Excel interprete una respuesta que empieza con '='
    # como fórmula, y conserva DNI, celulares e identificadores largos.
    for i, celda in enumerate(hoja[hoja.max_row], 1):
        if i not in numericas:
            celda.data_type = "s"
        celda.alignment = Alignment(vertical="top", wrap_text=True)


def _formato(hoja, anchos):
    hoja.freeze_panes = "A2"
    hoja.auto_filter.ref = hoja.dimensions
    for indice, ancho in enumerate(anchos, 1):
        hoja.column_dimensions[get_column_letter(indice)].width = ancho
    for celda in hoja[1]:
        celda.fill = PatternFill("solid", fgColor="173E69")
        celda.font = Font(color="FFFFFF", bold=True)


def generar_excel_respuestas(datos: dict, carteras_permitidas: set[int] | None) -> bytes:
    libro = Workbook()
    clientes = libro.active
    clientes.title = "Clientes"
    respuestas = libro.create_sheet("Respuestas")
    consulta = libro.create_sheet("Consulta")
    _fila(clientes, ENCABEZADOS_CLIENTES)
    _fila(respuestas, ENCABEZADOS_RESPUESTAS)
    total_respuestas = 0
    for grupo in datos["conversaciones"]:
        filas = sorted(grupo["filas"], key=lambda r: _texto(r.get("recibido")))
        if not filas:
            continue
        ultima = filas[-1]
        gestiones = [r for r in filas if r.get("gestion_posterior")]
        gestion = max(gestiones, key=lambda r: _texto(r.get("gestion_posterior"))) if gestiones else {}
        _fila(clientes, [
            grupo.get("estado"), ultima.get("idcartera"), ultima.get("idcliente"),
            ultima.get("dni"), ultima.get("cliente"),
            ", ".join(sorted({_texto(r.get("telefono")) for r in filas if r.get("telefono")})),
            ", ".join(sorted({_texto(r.get("cuenta")) for r in filas if r.get("cuenta")})),
            len(filas), sum(r.get("estado") == "PENDIENTE" for r in filas),
            filas[0].get("recibido"), ultima.get("recibido"),
            # El SMS nuestro al que responde la última respuesta, para entender su contexto.
            ultima.get("mensaje_enviado_fecha"), ultima.get("mensaje_enviado"),
            ultima.get("texto"),
            gestion.get("gestion_posterior"), gestion.get("gestion_posterior_texto"),
        ], numericas={8, 9})
        for r in filas:
            _fila(respuestas, [
                r.get("idcartera"), r.get("idcliente"), r.get("dni"), r.get("cliente"),
                r.get("telefono"), r.get("cuenta"), r.get("campana"), r.get("campana_id"),
                r.get("id"), r.get("recibido"), r.get("texto"), r.get("estado"),
                r.get("estado_mowa_etiqueta"), r.get("mensaje_id"),
                r.get("mensaje_enviado_fecha"), r.get("mensaje_enviado"),
                r.get("gestion_posterior"), r.get("gestion_posterior_id"),
                r.get("gestion_posterior_texto"), r.get("motivo"),
            ])
            total_respuestas += 1
    _fila(consulta, ["Campo", "Valor"])
    alcance = ("Todas las carteras" if carteras_permitidas is None
               else ", ".join(map(str, sorted(carteras_permitidas))))
    rango = datos.get("etiqueta_rango") or "Campañas"
    metadatos = [
        (f"{rango} desde", datos["desde"]), (f"{rango} hasta", datos["hasta"]),
        ("Cuenta seleccionada", datos.get("cuenta") or "Todas las autorizadas"),
        ("Carteras autorizadas", alcance),
        ("Estado filtrado", datos.get("estado_filtro") or "Todos"),
        ("Consulta", "Completa" if datos["completo"] else "Parcial"),
        ("Conversaciones exportadas", len(datos["conversaciones"])),
        ("Respuestas exportadas", total_respuestas),
        ("Generado", datetime.now(ZoneInfo("America/Lima")).strftime("%Y-%m-%d %H:%M:%S")),
        ("Origen", datos.get("origen") or "Datos cargados y filtrados en la vista Respuestas SMS"),
    ]
    metadatos.extend(("Advertencia", aviso) for aviso in datos.get("advertencias", []))
    for campo, valor in metadatos:
        _fila(consulta, [campo, valor], numericas={2} if isinstance(valor, int) else frozenset())
    _formato(clientes, [22, 12, 15, 16, 35, 22, 24, 13, 16, 22, 22, 20, 60, 48, 22, 48])
    _formato(respuestas, [12, 15, 16, 35, 18, 22, 32, 16, 16, 22, 48, 18, 23, 20, 22, 48, 22, 16, 48, 36])
    _formato(consulta, [26, 72])
    salida = BytesIO()
    libro.save(salida)
    return salida.getvalue()
