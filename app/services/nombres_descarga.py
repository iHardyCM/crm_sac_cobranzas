"""Nombres de archivo para las descargas de calidad (PDF, Word y Excel).

Solo arma el texto del nombre a partir de lo que ya viene en el payload;
no toca ninguna regla ni calculo. Si falta un dato se omite (no se inventa).

  Individual: Informe_Llamada_<Agente>_<Cartera>_<AAAAMMDD>.<ext>
  Cartera:    Informe_Calidad_<Cartera>_<desde>_a_<hasta>.<ext>
  Excel:      Reporte_Calidad_<Cartera>_<desde>_a_<hasta>.xlsx
"""
from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime
from typing import Dict, Optional

_MAX_PIEZA = 40


def _limpiar(texto, maximo: int = _MAX_PIEZA) -> str:
    """Texto seguro para nombre de archivo: sin tildes, sin simbolos, con guion bajo."""
    s = unicodedata.normalize("NFKD", str(texto or ""))
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_")
    return s[:maximo].strip("_")


def _agente_sin_dni(texto) -> str:
    """'19805651 - FANNY VASQUEZ' -> 'FANNY VASQUEZ' (el DNI queda fuera del nombre)."""
    s = str(texto or "").strip()
    s = re.sub(r"^\s*\d+\s*[-–:]\s*", "", s)
    return s


def _cartera_sin_codigo(texto) -> str:
    """'132 - FINANCIERA OH' -> 'FINANCIERA OH'."""
    return re.sub(r"^\s*\d+\s*[-–:]\s*", "", str(texto or "").strip())


def _a_fecha(valor) -> Optional[date]:
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    s = str(valor or "").strip()
    if not s or s == "—":
        return None
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", s)
    try:
        if m:
            return date(int(m[1]), int(m[2]), int(m[3]))
        m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", s)
        if m:
            return date(int(m[3]), int(m[2]), int(m[1]))
    except ValueError:
        return None
    return None


def _union(*piezas) -> str:
    return "_".join(p for p in piezas if p)


def nombre_informe_individual(payload: Dict, extension: str, base: str = "Informe_Llamada") -> str:
    meta = payload.get("meta") or {}
    f = _a_fecha(meta.get("fecha"))
    nombre = _union(
        base,
        _limpiar(_agente_sin_dni(meta.get("agente"))),
        _limpiar(_cartera_sin_codigo(meta.get("cartera"))),
        f"{f:%Y%m%d}" if f else "",
    )
    ev = (payload.get("evaluaciones") or [{}])[0]
    if not meta.get("agente") and ev.get("id_feedback"):
        nombre = _union(nombre, f"id{ev['id_feedback']}")
    return f"{nombre}.{extension}"


def nombre_informe_cartera(payload: Dict, extension: str, base: str = "Informe_Calidad") -> str:
    evals = payload.get("evaluaciones") or []
    carteras = sorted({_cartera_sin_codigo(e.get("cartera")) for e in evals if e.get("cartera")})
    if len(carteras) == 1:
        cartera = _limpiar(carteras[0])
    elif carteras:
        cartera = "Varias_carteras"
    else:
        cartera = ""
    fechas = [f for f in (_a_fecha(e.get("fecha")) for e in evals) if f]
    if fechas:
        d, h = min(fechas), max(fechas)
        rango = f"{d:%Y%m%d}" if d == h else f"{d:%Y%m%d}_a_{h:%Y%m%d}"
    else:
        rango = f"emitido_{datetime.now():%Y%m%d_%H%M}"
    return f"{_union(base, cartera, rango)}.{extension}"


def nombre_descarga(payload: Dict, tipo: str, extension: str, excel: bool = False) -> str:
    """Punto unico de entrada para las rutas."""
    if str(tipo).upper() == "INDIVIDUAL":
        return nombre_informe_individual(payload, extension)
    return nombre_informe_cartera(payload, extension, "Reporte_Calidad" if excel else "Informe_Calidad")
