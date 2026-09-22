"""
Compara la reporteria actual (JSON + guardas en cada lectura) con la nueva
(fuente SQL: tablas) ANTES de cambiar la pagina a la fuente SQL.

QUE COMPARA
  1. Cobertura: llamadas que la fuente SQL entrega sin criterios (no tienen
     filas en CRM_IA_EVALUACION_CRITERIO).
  2. Nota vigente por llamada: debe ser identica (las dos leen las mismas
     columnas de ia_feedback_llamadas).
  3. Resultado por criterio, llamada por llamada: el de la fuente JSON (con las
     guardas re-aplicadas hoy) contra el guardado en la tabla (o el calibrado
     publicado).
  4. % de cumplimiento por criterio en las dos fuentes.
  5. Tiempo de cada fuente.

No escribe nada en la base. Deja un CSV con cada diferencia en tools/salidas/.

USO
    python tools/comparar_reporteria.py
    python tools/comparar_reporteria.py --limit 300
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.ia_audio_service import obtener_reporteria_calidad  # noqa: E402
from app.services.reporteria_sql_service import obtener_reporteria_sql  # noqa: E402

MEDIDOS = {"CUMPLE", "NO_CUMPLE"}


def estado_json(item: dict) -> str:
    """Estado tecnico de un item de la fuente JSON (texto -> codigo)."""
    estado = str(item.get("estado") or item.get("estado_tecnico") or "").strip().upper().replace(" ", "_")
    if estado in {"CUMPLE", "NO_CUMPLE", "NO_APLICA", "NO_EVALUABLE", "REQUIERE_REVISION"}:
        return estado
    texto = str(item.get("calificacion") or item.get("resultado") or "").lower()
    if "no evaluable" in texto:
        return "NO_EVALUABLE"
    if "no aplica" in texto:
        return "NO_APLICA"
    if "revisi" in texto:
        return "REQUIERE_REVISION"
    if "parcial" in texto:
        return "PARCIAL"
    if "no cumple" in texto or "no evidenciado" in texto:
        return "NO_CUMPLE"
    if "cumple" in texto:
        return "CUMPLE"
    return "DESCONOCIDO"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=300)
    args = parser.parse_args()

    t0 = time.perf_counter()
    viejo = obtener_reporteria_calidad(limit=args.limit)
    t_viejo = time.perf_counter() - t0
    t0 = time.perf_counter()
    nuevo = obtener_reporteria_sql(limit=args.limit)
    t_nuevo = time.perf_counter() - t0

    v = {int(r["id_feedback"]): r for r in viejo["detalle"]}
    n = {int(r["id_feedback"]): r for r in nuevo["detalle"]}

    print("=" * 72)
    print(f"Tiempo fuente JSON (actual): {t_viejo:6.2f} s  | llamadas: {len(v)}")
    print(f"Tiempo fuente SQL  (nueva):  {t_nuevo:6.2f} s  | llamadas: {len(n)}  {nuevo.get('tiempos')}")
    print("=" * 72)

    solo_v, solo_n = sorted(set(v) - set(n)), sorted(set(n) - set(v))
    if solo_v or solo_n:
        print(f"IDs solo en JSON: {solo_v[:20]}  | solo en SQL: {solo_n[:20]}")

    sin_criterios = [i for i, r in n.items() if not r["evaluacion_calidad_lista"]]
    print(f"Llamadas SIN criterios en la tabla: {len(sin_criterios)} de {len(n)}")
    if sin_criterios:
        print(f"   ids: {sin_criterios[:40]}{' ...' if len(sin_criterios) > 40 else ''}")

    notas_distintas = [
        (i, v[i]["score_final"], n[i]["score_final"]) for i in sorted(set(v) & set(n))
        if (v[i]["score_final"] is None) != (n[i]["score_final"] is None)
        or (v[i]["score_final"] is not None and abs(float(v[i]["score_final"]) - float(n[i]["score_final"])) > 0.01)
    ]
    print(f"Llamadas con nota vigente distinta: {len(notas_distintas)}")
    for fila in notas_distintas[:10]:
        print(f"   #{fila[0]}: JSON={fila[1]}  SQL={fila[2]}")

    diferencias = []
    agregado = defaultdict(lambda: {"nombre": "", "json_med": 0, "json_cum": 0, "sql_med": 0, "sql_cum": 0, "dif": 0})
    comparadas = 0
    for i in sorted(set(v) & set(n)):
        if i in sin_criterios:
            continue
        items_v = {str(it.get("codigo_criterio") or "").strip(): it for it in v[i].get("evaluacion_calidad_lista") or [] if isinstance(it, dict)}
        for it in n[i]["evaluacion_calidad_lista"]:
            codigo = it["codigo_criterio"]
            e_sql = it["estado"]
            e_json = estado_json(items_v[codigo]) if codigo in items_v else "NO_ESTA_EN_JSON"
            a = agregado[codigo]
            a["nombre"] = it["nombre"]
            if e_sql in MEDIDOS:
                a["sql_med"] += 1
                a["sql_cum"] += e_sql == "CUMPLE"
            if e_json in MEDIDOS:
                a["json_med"] += 1
                a["json_cum"] += e_json == "CUMPLE"
            comparadas += 1
            if e_sql != e_json:
                a["dif"] += 1
                diferencias.append({
                    "id_feedback": i, "cartera": n[i]["cartera"], "codigo": codigo, "criterio": it["nombre"],
                    "estado_json_hoy": e_json, "estado_tabla": e_sql, "resultado_ia_tabla": it["resultado_ia"],
                    "calibrado": "SI" if it["calibrado"] else "NO",
                })

    print(f"Criterios comparados: {comparadas} | con resultado distinto: {len(diferencias)}"
          f" ({(len(diferencias) / comparadas * 100 if comparadas else 0):.1f}%)")
    print("-" * 72)
    print(f"{'Criterio':<44}{'% JSON (N)':>14}{'% SQL (N)':>14}{'difs':>7}")
    for codigo in sorted(agregado, key=lambda c: c):
        a = agregado[codigo]
        pj = f"{a['json_cum'] / a['json_med'] * 100:.0f}% ({a['json_med']})" if a["json_med"] else "—"
        ps = f"{a['sql_cum'] / a['sql_med'] * 100:.0f}% ({a['sql_med']})" if a["sql_med"] else "—"
        print(f"{(codigo + ' ' + a['nombre'])[:43]:<44}{pj:>14}{ps:>14}{a['dif']:>7}")

    salida_dir = Path(__file__).resolve().parent / "salidas"
    salida_dir.mkdir(exist_ok=True)
    archivo = salida_dir / f"comparacion_reporteria_{datetime.now():%Y%m%d_%H%M}.csv"
    with archivo.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["id_feedback", "cartera", "codigo", "criterio", "estado_json_hoy",
                                          "estado_tabla", "resultado_ia_tabla", "calibrado"], delimiter=";")
        w.writeheader()
        w.writerows(diferencias)
    print("-" * 72)
    print(f"Detalle de diferencias: {archivo}")


if __name__ == "__main__":
    main()
