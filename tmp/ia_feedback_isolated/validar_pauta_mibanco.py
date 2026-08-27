"""Ejecutor aislado para validar la pauta Mibanco sin persistencia."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.ia_analysis_service import analizar_transcripcion_real


BASE = Path(__file__).resolve().parent
TRANSCRIPCION = BASE / "audio_20260820_185331_transcripcion_mapping_fix.txt"
SALIDA = BASE / "audio_20260820_185331_resultado_end_to_end.json"


def main() -> None:
    transcripcion = TRANSCRIPCION.read_text(encoding="utf-8")
    resultado = analizar_transcripcion_real(transcripcion, cartera="112 - MIBANCO 1")
    SALIDA.write_text(
        json.dumps(resultado, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    evaluacion = resultado.get("evaluacion_calidad") or []
    resumen = {
        "score": resultado.get("score_calidad"),
        "estado": resultado.get("estado_calidad"),
        "requiere_revision": resultado.get("requiere_revision_humana"),
        "calidad_transcripcion": resultado.get("calidad_transcripcion"),
        "motivo_revision": resultado.get("motivo_revision"),
        "criterios": [
            {
                "codigo": item.get("codigo") or item.get("codigo_criterio"),
                "nombre": item.get("item") or item.get("criterio") or item.get("nombre"),
                "estado": item.get("estado") or item.get("estado_sgc") or item.get("resultado"),
                "puntaje": item.get("puntaje_obtenido") or item.get("nota"),
                "evidencia": item.get("evidencia") or item.get("evidencia_textual"),
            }
            for item in evaluacion
        ],
        "hallazgos": resultado.get("resumen_sgc", {}).get("hallazgos") or resultado.get("puntos_criticos") or [],
    }
    print(json.dumps(resumen, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
