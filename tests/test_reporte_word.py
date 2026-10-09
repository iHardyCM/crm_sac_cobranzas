"""Informes Word (.docx): se generan, abren y muestran los mismos numeros que el PDF.

Datos SIMULADOS solo para probar el formato.
"""
import pytest

docx = pytest.importorskip("docx")

from io import BytesIO

from app.services.reporte_calidad_word import (
    construir_informe_cartera_docx,
    construir_informe_individual_docx,
)


def _texto(blob: bytes) -> str:
    d = docx.Document(BytesIO(blob))
    partes = [p.text for p in d.paragraphs]

    def _tabla(t):
        for fila in t.rows:
            for c in fila.cells:
                partes.extend(p.text for p in c.paragraphs)
                for sub in c.tables:
                    _tabla(sub)
    for t in d.tables:
        _tabla(t)
    return "\n".join(partes)


def _ind(nota):
    return {
        "score_vigente": nota,
        "meta": {"agente": "1 - AGENTE PRUEBA", "cartera": "132 - CARTERA PRUEBA", "fecha": "2026-10-07T12:11:00"},
        "resumen": "Resumen de prueba.",
        "criterios": [
            {"bloque_nombre": "PECUF", "criterio": "Falta de respeto", "peso": 20, "nota": 20, "resultado": "Cumple"},
            {"bloque_nombre": "PECN", "criterio": "Cierre", "peso": 10, "nota": 0, "resultado": "No cumple", "brecha": True, "evidencia": "frase"},
        ],
        "fortalezas": ["Respeto.", "Respeto."], "brechas": [], "feedback": "", "compromiso": "",
    }


def test_individual_con_nota():
    t = _texto(construir_informe_individual_docx(_ind(51.4)))
    assert "51.4" in t and "Falta de respeto" in t and "No cumple" in t and "Cierre" in t
    assert t.count("Respeto.") == 1  # fortalezas repetidas se muestran una vez


def test_individual_sin_nota_no_es_cero():
    t = _texto(construir_informe_individual_docx(_ind(None)))
    assert "No evaluable" in t and "No es un 0" in t


def test_individual_sin_criterios_no_falla():
    p = _ind(None); p["criterios"] = []
    assert "no tiene criterios" in _texto(construir_informe_individual_docx(p))


def test_cartera_vacia_y_con_datos():
    assert construir_informe_cartera_docx({})
    p = {"meta": 85, "periodo": "p", "evaluaciones": [
        {"fecha": "2026-10-01", "cartera": "A", "agente": "X", "nota": 90},
        {"fecha": "2026-10-02", "cartera": "A", "agente": "Y", "nota": 70}]}
    t = _texto(construir_informe_cartera_docx(p))
    assert "80.0" in t and "1 de 2" in t and "50%" in t
