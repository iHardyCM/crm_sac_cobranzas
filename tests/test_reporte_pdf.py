"""Informes PDF del Centro de Calidad: se generan y respetan las reglas de lectura.

Usa datos SIMULADOS solo para probar el formato; no representan ninguna evaluacion real.
"""
import re
from io import BytesIO

from app.services.reporte_calidad_pdf import (
    construir_informe_cartera_pdf,
    construir_informe_individual_pdf,
)

try:
    from pypdf import PdfReader
except ImportError:  # pragma: no cover
    PdfReader = None


def _texto(pdf: bytes) -> str:
    assert pdf.startswith(b"%PDF")
    if PdfReader is None:
        return ""
    return " ".join(p.extract_text() or "" for p in PdfReader(BytesIO(pdf)).pages)


def _individual(score):
    return {
        "score_vigente": score,
        "meta": {"agente": "1 - AGENTE PRUEBA", "cartera": "132 - CARTERA PRUEBA", "fecha": "2026-10-07T12:11:00"},
        "resumen": "Resumen de prueba.",
        "criterios": [
            {"bloque_nombre": "PECUF", "criterio": "Falta de respeto", "peso": 20, "nota": 20, "resultado": "Cumple"},
            {"bloque_nombre": "PECN", "criterio": "Cierre", "peso": 10, "nota": 0, "resultado": "No cumple", "brecha": True, "evidencia": "-"},
            {"bloque_nombre": "PENC", "criterio": "Tono de voz", "peso": 3, "nota": 0, "resultado": "No evaluable"},
        ],
        "fortalezas": ["Respeto.", "Respeto.", "Escucha."],
        "brechas": [], "feedback": "", "compromiso": "",
    }


def test_individual_con_nota():
    texto = _texto(construir_informe_individual_pdf(_individual(51.4)))
    if texto:
        assert "51.4" in texto
        assert texto.count("Respeto.") == 1  # fortalezas repetidas se muestran una vez


def test_individual_sin_nota_no_es_cero():
    texto = _texto(construir_informe_individual_pdf(_individual(None)))
    if texto:
        assert "No evaluable" in texto
        assert "No es un 0" in texto


def test_individual_sin_criterios_no_falla():
    datos = _individual(None)
    datos["criterios"] = []
    assert construir_informe_individual_pdf(datos).startswith(b"%PDF")


def test_cartera_sin_datos_no_falla():
    assert construir_informe_cartera_pdf({}).startswith(b"%PDF")


def test_cartera_numeros_salen_del_payload():
    payload = {
        "periodo": "Octubre", "meta": 85,
        "evaluaciones": [
            {"fecha": "2026-10-01", "cartera": "C1", "agente": "A", "nota": 90, "error_critico": "No"},
            {"fecha": "2026-10-02", "cartera": "C1", "agente": "A", "nota": 70, "error_critico": "Sí"},
            {"fecha": "2026-10-03", "cartera": "C1", "agente": "B", "nota": None, "error_critico": "No"},
        ],
        "criterios": [
            {"criterio": "Cierre", "medido": 1, "brecha": 1},
            {"criterio": "Cierre", "medido": 1, "brecha": 0},
            {"criterio": "Cierre", "medido": 0, "brecha": 0},
        ],
        "agentes": [{"agente": "A", "tendencia": None, "brecha_repite": ""}],
    }
    texto = _texto(construir_informe_cartera_pdf(payload))
    if texto:
        assert "80.0" in texto           # promedio de 90 y 70; la llamada sin nota no cuenta como 0
        assert "1 de 2" in texto         # 1 de 2 evaluaciones con nota en meta
        assert "50%" in texto            # Cierre falla en 1 de 2 mediciones medidas


def test_individual_siempre_una_sola_hoja_aun_con_mucho_texto():
    if PdfReader is None:
        return
    p = _individual(51.4)
    largo = "Texto de prueba muy largo para forzar la compactacion del informe. " * 12
    p["resumen"] = largo
    p["feedback"] = largo
    p["fortalezas"] = [f"Fortaleza {i}: {largo[:120]}" for i in range(8)]
    p["criterios"] = [
        {"bloque_nombre": f"B{i % 4}", "criterio": f"Criterio {i}", "peso": 5, "nota": 0,
         "resultado": "No cumple", "brecha": True, "evidencia": largo[:200]}
        for i in range(20)
    ]
    p["brechas"] = [{"criterio": f"Criterio {i}", "resultado": "No cumple", "evidencia": largo[:200]} for i in range(10)]
    pdf = construir_informe_individual_pdf(p)
    assert len(PdfReader(BytesIO(pdf)).pages) == 1
    assert len(PdfReader(BytesIO(construir_informe_individual_pdf(_individual(80)))).pages) == 1
