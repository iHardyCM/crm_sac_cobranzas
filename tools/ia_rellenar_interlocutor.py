"""Etiqueta quién contestó (Titular / Tercero) en las llamadas ya analizadas del módulo Análisis IA.

No vuelve a leer el audio ni llama a la IA: usa lo que quedó guardado (segmentos de la transcripción y el
tipo de contacto del análisis). Las llamadas nuevas se etiquetan solas al terminar su análisis.

Uso (desde la carpeta del CRM, con el mismo .env del backend):
    python tools/ia_rellenar_interlocutor.py            # solo las que no tienen etiqueta
    python tools/ia_rellenar_interlocutor.py --todas    # vuelve a etiquetar todas (si cambian las reglas)
"""
import argparse
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from app.services.ia_audio_service import ensure_tabla_feedback  # noqa: E402
from app.services.ia_interlocutor import rellenar_interlocutores  # noqa: E402

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--todas", action="store_true")
    args = ap.parse_args()
    ensure_tabla_feedback()   # crea las columnas si faltan
    r = rellenar_interlocutores(solo_faltantes=not args.todas)
    print(f"Titular: {r['TITULAR']} · Tercero: {r['TERCERO']} · Sin identificar: {r['SIN_IDENTIFICAR']} · Errores: {r['errores']}")
