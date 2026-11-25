"""
Inspecciona la respuesta de la API de gestiones de UCM/Omnitel (solo lectura).

Para qué: saber qué campos trae cada llamada y en cuál viene el nombre de la base que se pone al
cargarla en UCM. No se conecta a ninguna base de datos ni escribe en SISCOB.

Uso (desde la carpeta del CRM):
    python tools/ucm_inspeccionar_api.py 2026-11-13

Deja en tools/salidas/ucm_api_columnas_<fecha>.txt:
    - cada columna con su tipo, cuántos valores distintos tiene y 3 ejemplos;
    - para las columnas de texto con pocos valores distintos (candidatas a "nombre de base",
      campaña o lista), los 20 valores más frecuentes con su cantidad.
"""

import sys
from pathlib import Path

import pandas as pd
import requests

URL = "https://bzncob.omnitel.pe/api/v1.3.1/gestiones"
RAIZ = Path(__file__).resolve().parents[1]


def main() -> None:
    fecha = sys.argv[1] if len(sys.argv) > 1 else pd.Timestamp.today().strftime("%Y-%m-%d")
    respuesta = requests.post(URL, json={"fecha": fecha}, headers={"Content-Type": "application/json"}, timeout=300)
    respuesta.raise_for_status()
    df = pd.DataFrame(respuesta.json())

    lineas = [f"API {URL} · fecha {fecha} · {len(df):,} llamadas · {len(df.columns)} columnas", ""]
    lineas.append("COLUMNAS")
    for c in df.columns:
        ejemplos = df[c].dropna().astype(str).head(3).tolist()
        lineas.append(f"- {c} | tipo {df[c].dtype} | distintos {df[c].nunique(dropna=True):,} | vacíos {df[c].isna().sum():,} | ej. {ejemplos}")

    lineas += ["", "COLUMNAS DE TEXTO CON POCOS VALORES (candidatas a nombre de base, campaña o lista)"]
    for c in df.columns:
        n = df[c].nunique(dropna=True)
        if df[c].dtype == object and 1 < n <= 2000:
            lineas.append(f"\n## {c} ({n:,} valores distintos)")
            for valor, cantidad in df[c].astype(str).value_counts().head(20).items():
                lineas.append(f"   {cantidad:>8,}  {valor}")

    salidas = RAIZ / "tools" / "salidas"
    salidas.mkdir(parents=True, exist_ok=True)
    archivo = salidas / f"ucm_api_columnas_{fecha}.txt"
    archivo.write_text("\n".join(lineas), encoding="utf-8")
    print(f"Listo: {archivo}")


if __name__ == "__main__":
    main()
