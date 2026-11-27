"""Clientes que ya no están en el SAC del día (Compartamos vigente, fase 17, 25/11/2026).

Clientes del generador (score.BaseTrabajoCliente) de las carteras de score.SacCartera que no figuran en la última foto
del SAC (score.SacClienteDia): pagaron, cancelaron o salieron, con o sin gestión. Se exportan a Excel con sus
operaciones de la asignación (Desarrollo.dbo.compartamos_*), porque en el SAC ya no están.

Las columnas de la asignación se buscan por nombre parecido (sin tildes, espacios ni mayúsculas); la hoja "Resumen"
dice qué columna real se usó para cada dato y cuál no se encontró. Nada se completa con otra fuente.
"""
from __future__ import annotations

import io
import re
import unicodedata
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
from openpyxl.utils import get_column_letter
from sqlalchemy import text

from app.core.db_siscob import engine_siscob
from app.services import generador_bases_service as generador


class ExportacionInvalida(ValueError):
    pass


# Dato → nombres posibles de la columna en la asignación (comparados con clave_columna)
COLUMNAS_ASIGNACION: Dict[str, Tuple[str, ...]] = {
    "dni": ("NumDoc", "DNI", "NumDocumento", "NroDocumento", "Nro_Doc", "NRO_DOC", "Documento"),
    "operacion": ("Operacion", "CodOperacion", "Cod Operación"),
    "nombre": ("NomCliente", "NombreCliente", "Nombre", "Nombres", "Cliente"),
    "cta_cliente": ("CtaCliente", "CodClienteBT", "CodCliente"),
    "capital": ("Saldo Capital por Cuenta", "SdoCapital", "SaldoCapital", "Saldo_Capital", "Saldo Capital", "MtoSaldoCapital", "SaldoCap",
                "CAPITAL_TOTAL", "CapitalTotal", "Capital", "MtoSaldo", "Saldo"),
    "calificacion": ("Cal_PROV", "Calif_Provisiones", "Calificacion", "Calif"),
    "dias_atraso": ("DiasAtraso", "Dias_Atraso"),
    "fec_ult_pago": ("FecUltPago", "FECULTPAGO", "Fec_Ult_Pago"),
    "codigo_grupo": ("CodigoGrupo", "CodGrupo"),
    "cod_cre_grupal": ("CodCreGrupal", "CodCredGrupal"),
}
# Calificación de provisión (Cal_PROV) según negocio (la misma del Radar)
CALIFICACION_PROVISION = {0: "Normal", 1: "CPP", 2: "Deficiente", 3: "Dudoso 1", 4: "Dudoso 2", 5: "Pérdida"}
_SEGURO = re.compile(r"^[0-9A-Za-z]{1,20}$")


def clave_columna(nombre: str) -> str:
    s = unicodedata.normalize("NFKD", str(nombre or ""))
    s = "".join(ch for ch in s if not unicodedata.combining(ch)).lower()
    return re.sub(r"[^a-z0-9%]", "", s)


def mapear_columnas(reales: List[str]) -> Dict[str, Optional[str]]:
    """Dato → nombre real de la columna (o None)."""
    por_clave = {clave_columna(c): c for c in reales}
    salida: Dict[str, Optional[str]] = {}
    for dato, candidatos in COLUMNAS_ASIGNACION.items():
        salida[dato] = next((por_clave[clave_columna(c)] for c in candidatos if clave_columna(c) in por_clave), None)
    return salida


def sin_ceros(valor: Any) -> str:
    """Texto sin ceros a la izquierda (un float entero pierde el .0)."""
    if valor is None:
        return ""
    if isinstance(valor, float) and valor.is_integer():
        valor = int(valor)
    if isinstance(valor, Decimal) and valor == valor.to_integral_value():
        valor = int(valor)
    s = str(valor).strip()
    return s.lstrip("0") or ("0" if s else "")


def calificacion(valor: Any) -> Any:
    try:
        n = int(float(valor))
    except (TypeError, ValueError):
        return valor
    return f"{n}-{CALIFICACION_PROVISION[n]}" if n in CALIFICACION_PROVISION else valor


def fecha_aaaammdd(valor: Any) -> Any:
    """FecUltPago llega como número AAAAMMDD: se muestra como fecha si lo es; si no, tal cual."""
    if valor in (None, ""):
        return None
    if isinstance(valor, (date, datetime)):
        return valor
    try:
        n = int(float(valor))
        return date(n // 10000, (n // 100) % 100, n % 100) if 19000101 <= n <= 21001231 else valor
    except (TypeError, ValueError):
        return valor


def _filas(resultado) -> List[Dict[str, Any]]:
    return [dict(f) for f in resultado.mappings().all()]


def _asignacion(conn, tabla: str, dnis: List[str]) -> Tuple[Dict[str, List[Dict]], Dict[str, Optional[str]]]:
    """Filas de la asignación de los DNI dados, por DNI sin ceros; y el mapeo de columnas usado
    (el mapeo lleva además "_columnas": todas las columnas reales de la tabla, para el Resumen)."""
    reales = [f[0] for f in conn.execute(text(
        "SELECT COLUMN_NAME FROM Desarrollo.INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = :t ORDER BY ORDINAL_POSITION"),
        {"t": tabla}).all()]
    mapa = mapear_columnas(reales)
    mapa["_columnas"] = ", ".join(reales)  # type: ignore[assignment]
    por_dni: Dict[str, List[Dict]] = {}
    if not reales or not mapa["dni"]:
        return por_dni, mapa
    # Variantes del DNI (con y sin ceros) en texto literal: solo dígitos y letras, nunca otra cosa
    variantes: List[str] = []
    for d in dnis:
        for v in (d, d.lstrip("0"), d.lstrip("0").zfill(8)):
            if v and _SEGURO.match(v) and v not in variantes:
                variantes.append(v)
    col = "[" + mapa["dni"].replace("]", "]]") + "]"
    nombre_tabla = "[" + tabla.replace("]", "]]") + "]"
    for i in range(0, len(variantes), 800):
        lista = ", ".join(f"N'{v}'" for v in variantes[i:i + 800])
        sql = (f"SELECT a.* FROM Desarrollo.dbo.{nombre_tabla} AS a WITH (NOLOCK) "
               f"WHERE LTRIM(RTRIM(CONVERT(NVARCHAR(30), a.{col}))) IN ({lista})")
        for fila in _filas(conn.execute(text(sql))):
            por_dni.setdefault(sin_ceros(fila.get(mapa["dni"])), []).append(fila)
    return por_dni, mapa


def fuera_del_sac(idcartera: int) -> Dict[str, Any]:
    """Datos de la exportación (sin armar el Excel), separado para probarlo."""
    with engine_siscob.connect() as conn:
        if conn.execute(text("SELECT OBJECT_ID('score.SacClienteDia')")).scalar() is None:
            raise ExportacionInvalida("Falta ejecutar la fase 17 (SAC del día).")
        carteras = generador.carteras_de(conn, idcartera)
        en = ", ".join(str(int(c)) for c in carteras)
        sac = _filas(conn.execute(text(
            f"SELECT IdCartera, TablaAsignacion FROM score.SacCartera WHERE Activo = 1 AND IdCartera IN ({en})")))
        if not sac:
            raise ExportacionInvalida("Solo para las carteras vigentes que se cruzan con el SAC.")
        ultima = conn.execute(text("SELECT TOP (1) FechaSac, FechaCarga FROM score.SacCarga ORDER BY FechaSac DESC")).mappings().first()
        if not ultima:
            raise ExportacionInvalida("Todavía no hay foto del SAC: se toma sola al abrir el generador cuando el SAC tiene datos.")
        en_sac = ", ".join(str(int(s["IdCartera"])) for s in sac)
        clientes = _filas(conn.execute(text(f"""
            SELECT b.IdCartera, b.DNI, b.Capital AS CapitalAnalytics, b.FechaCorteFuente,
                   gc.Condicion, gc.MgContacto, gc.UgIndicador, gc.EstadoPdp, gc.UltCefTramo,
                   ult.FechaSac AS UltimoDiaEnSac, ult.SdoCapital AS SaldoUltimoDiaEnSac
            FROM score.BaseTrabajoCliente AS b
            LEFT JOIN score.GestionCliente AS gc ON gc.IdCartera = b.IdCartera AND gc.DNI = b.DNI
            OUTER APPLY (SELECT TOP (1) d.FechaSac, d.SdoCapital FROM score.SacClienteDia AS d
                         WHERE d.IdCartera = b.IdCartera AND d.DNI = b.DNI ORDER BY d.FechaSac DESC) AS ult
            WHERE b.IdCartera IN ({en_sac})
              AND NOT EXISTS (SELECT 1 FROM score.SacClienteDia AS s
                              WHERE s.FechaSac = :f AND s.IdCartera = b.IdCartera AND s.DNI = b.DNI)
            ORDER BY b.IdCartera, b.DNI
        """), {"f": ultima["FechaSac"]}))
        # Condición SISCOB de hoy con su código (p. ej. CA = CANCELADO), misma regla que sp_ArmarGestion:
        # por DNI, primero el cliente activo (estado A/N) y luego el IdCliente más reciente
        condicion_hoy: Dict[Tuple[int, str], Tuple[Any, Any]] = {}
        for s_ in sac:
            for f in _filas(conn.execute(text("""
                SELECT LTRIM(RTRIM(cl.Dni)) AS DNI, LTRIM(RTRIM(cn.Codigo)) AS Codigo, LTRIM(RTRIM(cn.Descripcion)) AS Descripcion,
                       ROW_NUMBER() OVER (PARTITION BY LTRIM(RTRIM(cl.Dni))
                                          ORDER BY CASE WHEN UPPER(LTRIM(RTRIM(ISNULL(cl.Estado, '')))) IN ('A', 'N') THEN 0 ELSE 1 END,
                                                   cl.IdCliente DESC) AS rn
                FROM siscob.dbo.Cliente AS cl WITH (NOLOCK)
                LEFT JOIN siscob.dbo.Condicion AS cn WITH (NOLOCK) ON cn.IdCondicion = cl.IdCondicion
                WHERE cl.IdCartera = :c
            """), {"c": int(s_["IdCartera"])})):
                if f["rn"] == 1:
                    condicion_hoy[(int(s_["IdCartera"]), sin_ceros(f["DNI"]))] = (f["Codigo"], f["Descripcion"])
        for c in clientes:
            codigo, descripcion = condicion_hoy.get((int(c["IdCartera"]), sin_ceros(c["DNI"])), (None, None))
            c["CondicionCodigo"] = codigo
            if descripcion:
                c["Condicion"] = descripcion
        asignaciones: Dict[int, Tuple[Dict[str, List[Dict]], Dict[str, Optional[str]], str]] = {}
        for s in sac:
            dnis = [c["DNI"] for c in clientes if c["IdCartera"] == s["IdCartera"]]
            por_dni, mapa = _asignacion(conn, s["TablaAsignacion"], dnis)
            asignaciones[int(s["IdCartera"])] = (por_dni, mapa, s["TablaAsignacion"])
    return {"ultima": dict(ultima), "clientes": clientes, "asignaciones": asignaciones,
            "grupal": any(m["codigo_grupo"] or m["cod_cre_grupal"] for _p, m, _t in asignaciones.values())}


COLUMNAS = [
    # (título, clave, ancho)
    ("Cartera", "cartera", 9), ("DNI", "dni", 12), ("Nombre", "nombre", 34), ("Cta. cliente", "cta_cliente", 14),
    ("Operación", "operacion", 22), ("Código grupo", "codigo_grupo", 14), ("Cod. créd. grupal", "cod_cre_grupal", 16),
    ("Capital (asignación)", "capital", 15), ("Calificación", "calificacion", 15),
    ("Días atraso (asignación)", "dias_atraso", 12), ("Fec. último pago (asignación)", "fec_ult_pago", 14),
    ("Cód. condición", "condicion_codigo", 9), ("Condición SISCOB (hoy)", "condicion", 26), ("Mejor contacto del mes", "mg", 12), ("Última gestión del mes", "ug", 34),
    ("PDP del mes", "pdp", 12), ("Último CEF", "ult_cef", 16), ("Capital cliente (Analytics)", "capital_analytics", 15),
    ("Último día en el SAC", "ultimo_sac", 14), ("Saldo capital ese día (SAC)", "saldo_ultimo_sac", 15),
    ("Observación", "obs", 40),
]


def filas_excel(datos: Dict[str, Any]) -> List[Dict[str, Any]]:
    salida: List[Dict[str, Any]] = []
    for c in datos["clientes"]:
        por_dni, mapa, _tabla = datos["asignaciones"][int(c["IdCartera"])]
        comunes = {
            "cartera": c["IdCartera"], "dni": c["DNI"], "condicion": c.get("Condicion"),
            "condicion_codigo": c.get("CondicionCodigo"), "mg": c.get("MgContacto"),
            "ug": c.get("UgIndicador"), "pdp": c.get("EstadoPdp"), "ult_cef": c.get("UltCefTramo"),
            "capital_analytics": c.get("CapitalAnalytics"), "ultimo_sac": c.get("UltimoDiaEnSac"),
            "saldo_ultimo_sac": c.get("SaldoUltimoDiaEnSac"),
        }
        if c.get("UltimoDiaEnSac") is None:
            comunes["obs"] = "No figuró en ninguna foto del SAC guardada"
        operaciones = por_dni.get(sin_ceros(c["DNI"]), [])
        if not operaciones:
            salida.append({**comunes, "obs": "Sin fila en la asignación de la cartera"})
            continue
        for op in operaciones:
            def v(dato):
                return op.get(mapa[dato]) if mapa.get(dato) else None
            salida.append({**comunes,
                           "nombre": v("nombre"), "cta_cliente": v("cta_cliente"), "operacion": v("operacion"),
                           "codigo_grupo": v("codigo_grupo"), "cod_cre_grupal": v("cod_cre_grupal"),
                           "capital": v("capital"), "calificacion": calificacion(v("calificacion")),
                           "dias_atraso": v("dias_atraso"), "fec_ult_pago": fecha_aaaammdd(v("fec_ult_pago"))})
    return salida


def _texto_excel(valor: Any) -> Any:
    """Excel no acepta caracteres de control (vienen en algunos nombres de la asignación): se quitan."""
    if isinstance(valor, str):
        return ILLEGAL_CHARACTERS_RE.sub("", valor)
    if isinstance(valor, (bytes, bytearray)):
        return None
    return valor


def _codigo(valor: Any) -> Optional[str]:
    """Código como texto (conserva ceros a la izquierda; un float entero sin el .0)."""
    if valor is None:
        return None
    if isinstance(valor, float) and valor.is_integer():
        return str(int(valor))
    if isinstance(valor, Decimal) and valor == valor.to_integral_value():
        return str(int(valor))
    return _texto_excel(str(valor).strip())


def _celda(valor: Any) -> Any:
    valor = _texto_excel(valor)
    if isinstance(valor, Decimal):
        return float(valor)
    if isinstance(valor, float) and valor.is_integer() and abs(valor) >= 1e7:
        return str(int(valor))          # códigos guardados como float (grupo, crédito): sin notación científica
    return valor


def exportar_fuera_del_sac(idcartera: int) -> Tuple[bytes, str]:
    datos = fuera_del_sac(idcartera)
    filas = filas_excel(datos)
    columnas = [c for c in COLUMNAS if datos["grupal"] or c[1] not in ("codigo_grupo", "cod_cre_grupal")]
    libro = Workbook()
    hoja = libro.active
    hoja.title = "Fuera del SAC"
    cab = Font(bold=True, color="FFFFFF")
    relleno = PatternFill("solid", fgColor="24466B")
    hoja.append([c[0] for c in columnas])
    for i, (_t, _k, ancho) in enumerate(columnas, start=1):
        celda = hoja.cell(row=1, column=i)
        celda.font, celda.fill = cab, relleno
        celda.alignment = Alignment(wrap_text=True, vertical="center")
        hoja.column_dimensions[get_column_letter(i)].width = ancho
    texto = {"dni", "cta_cliente", "operacion", "codigo_grupo", "cod_cre_grupal", "condicion_codigo"}
    for f in filas:
        hoja.append([(_codigo(f.get(k)) if k in texto else _celda(f.get(k))) for _t, k, _a in columnas])
    for i, (_t, k, _a) in enumerate(columnas, start=1):
        formato = ("#,##0.00" if k in ("capital", "capital_analytics", "saldo_ultimo_sac")
                   else "dd/mm/yyyy" if k in ("fec_ult_pago", "ultimo_sac") else None)
        if formato:
            for fila in hoja.iter_rows(min_row=2, min_col=i, max_col=i):
                fila[0].number_format = formato
    hoja.freeze_panes = "C2"
    hoja.auto_filter.ref = hoja.dimensions

    r = libro.create_sheet("Resumen")
    u = datos["ultima"]
    r.append(["Clientes del generador que no están en el SAC del día"])
    r["A1"].font = Font(bold=True, size=12)
    r.append(["SAC del", u["FechaSac"], "Carga del SAC", u["FechaCarga"]])
    r.append(["Generado", datetime.now().replace(microsecond=0)])
    r.append([])
    r.append(["Cartera", "Clientes fuera del SAC", "Filas (operaciones)", "Tabla de asignación"])
    for idc, (_por, _mapa, tabla) in datos["asignaciones"].items():
        r.append([idc, sum(1 for c in datos["clientes"] if c["IdCartera"] == idc),
                  sum(1 for f in filas if f["cartera"] == idc), f"Desarrollo.dbo.{tabla}"])
    r.append([])
    r.append(["Columna usada de la asignación", "Dato"] + [f"Cartera {i}" for i in datos["asignaciones"]])
    for dato in COLUMNAS_ASIGNACION:
        r.append(["", dato] + [m.get(dato) or "NO ENCONTRADA" for _p, m, _t in datos["asignaciones"].values()])
    # (las columnas reales de cada tabla van más abajo)
    r.append([])
    r.append(["Columnas de la tabla de asignación"])
    for idc, (_por, mapa, tabla) in datos["asignaciones"].items():
        r.append([f"Cartera {idc} · {tabla}", mapa.get("_columnas") or "No se pudo leer la tabla"])
    r.append([])
    r.append(["Una fila por operación de la asignación. Si el cliente no tiene fila en la asignación, sale una fila sin "
              "operación con la observación. El SAC del día ya no tiene a estos clientes: los montos son de la asignación."])
    r.column_dimensions["A"].width = 30
    for col in "BCDEF":
        r.column_dimensions[col].width = 24

    # Todas las columnas de la asignación de estos clientes, tal cual (para revisar lo que no se mapeó)
    for idc, (por_dni, _mapa, tabla) in datos["asignaciones"].items():
        filas_a = [f for lista in por_dni.values() for f in lista]
        if not filas_a:
            continue
        h = libro.create_sheet(f"Asignación {idc}"[:31])
        cols = list(filas_a[0].keys())
        h.append(cols)
        for c in h[1]:
            c.font, c.fill = cab, relleno
        for f in filas_a:
            h.append([_celda(f.get(c)) for c in cols])
        h.freeze_panes = "A2"

    salida = io.BytesIO()
    libro.save(salida)
    carteras = "-".join(str(i) for i in datos["asignaciones"])
    nombre = f"{carteras}_fuera_del_SAC_{u['FechaSac']:%Y%m%d}.xlsx" if hasattr(u["FechaSac"], "strftime") \
        else f"{carteras}_fuera_del_SAC.xlsx"
    return salida.getvalue(), nombre
