"""
Backfill de CRM_IA_EVALUACION_CRITERIO desde las evaluaciones ya guardadas.

POR QUE ES UN SCRIPT PYTHON Y NO SQL
La evaluacion por criterio vive como JSON en ia_feedback_llamadas.evaluacion_calidad.
CobAuto esta en nivel de compatibilidad 120, donde OPENJSON no existe y solo hay
JSON_VALUE, que no recorre un arreglo. Por eso el JSON se parsea aqui y no en SQL.

QUE HACE
Para cada evaluacion FINALIZADA que todavia no tiene filas en
CRM_IA_EVALUACION_CRITERIO, escribe una fila por criterio reutilizando
exactamente la misma funcion que usa el flujo normal
(ia_audio_service.persistir_evaluacion_criterios). No hay una segunda
implementacion que pueda quedar desalineada.

GARANTIAS
- Es idempotente: una evaluacion que ya tiene filas no se vuelve a escribir.
- No toca evaluaciones que ya tienen calibraciones humanas: esa comprobacion
  vive dentro de persistir_evaluacion_criterios y aqui no se elude.
- No modifica ia_feedback_llamadas ni ninguna evaluacion existente.
- Por defecto NO escribe nada: hay que pasar --ejecutar.

USO
    python backfill_evaluacion_criterios.py                 # simulacion
    python backfill_evaluacion_criterios.py --ejecutar      # escribe
    python backfill_evaluacion_criterios.py --ids 28 29 30  # solo esas
    python backfill_evaluacion_criterios.py --ejecutar --ids 33

Se ejecuta desde la raiz del proyecto, con el mismo entorno del CRM.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sqlalchemy import text  # noqa: E402

from app.core.db_siscob import engine_siscob  # noqa: E402
from app.services.ia_audio_service import persistir_evaluacion_criterios  # noqa: E402


def cargar_lista(value):
    """La columna puede venir como JSON de lista, como dict o vacia."""
    if not value:
        return []
    if isinstance(value, list):
        return value
    try:
        data = json.loads(value)
    except (TypeError, ValueError):
        return []
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for clave in ("evaluacion_calidad", "criterios", "items"):
            if isinstance(data.get(clave), list):
                return data[clave]
    return []


def candidatos(ids=None):
    """Evaluaciones finalizadas sin filas en la tabla de criterios."""
    filtro = ""
    params = {}
    if ids:
        marcas = ", ".join(f":id{i}" for i in range(len(ids)))
        filtro = f" AND F.id_feedback IN ({marcas})"
        params = {f"id{i}": valor for i, valor in enumerate(ids)}

    consulta = text(f"""
        SELECT F.id_feedback,
               F.evaluacion_calidad,
               F.id_pauta,
               F.pauta_version
        FROM CobAuto.dbo.ia_feedback_llamadas AS F WITH (NOLOCK)
        WHERE F.estado = 'FINALIZADO'
          AND F.evaluacion_calidad IS NOT NULL
          AND NOT EXISTS (
              SELECT 1 FROM CobAuto.dbo.CRM_IA_EVALUACION_CRITERIO AS C
              WHERE C.id_feedback = F.id_feedback
          )
          {filtro}
        ORDER BY F.id_feedback
    """)
    with engine_siscob.connect() as conn:
        filas = conn.execute(consulta, params).mappings().all()
    return [dict(fila) for fila in filas]


def main():
    parser = argparse.ArgumentParser(description="Backfill de evaluacion por criterio.")
    parser.add_argument("--ejecutar", action="store_true", help="Escribe. Sin esto solo simula.")
    parser.add_argument("--ids", nargs="*", type=int, default=None, help="Limita a estos id_feedback.")
    args = parser.parse_args()

    with engine_siscob.connect() as conn:
        existe = conn.execute(
            text("SELECT OBJECT_ID('CobAuto.dbo.CRM_IA_EVALUACION_CRITERIO', 'U')")
        ).scalar()
    if not existe:
        print("La tabla CRM_IA_EVALUACION_CRITERIO no existe. Ejecuta antes ddl_calibracion_ia.sql.")
        return 1

    pendientes = candidatos(args.ids)
    if not pendientes:
        print("No hay evaluaciones pendientes de backfill.")
        return 0

    print(f"{'id':>5}  {'criterios':>9}  {'pauta':>6}  {'ver':>4}  estado")
    total_filas = 0
    escritas = 0
    sin_criterios = []

    for fila in pendientes:
        id_feedback = fila["id_feedback"]
        criterios = cargar_lista(fila.get("evaluacion_calidad"))
        if not criterios:
            sin_criterios.append(id_feedback)
            print(f"{id_feedback:>5}  {'0':>9}  {'-':>6}  {'-':>4}  sin criterios: se omite")
            continue

        # persistir_evaluacion_criterios lee pauta_id / pauta_version del analisis;
        # aqui vienen de la columna, que es lo que quedo guardado en su momento.
        analisis = {
            "evaluacion_calidad": criterios,
            "pauta_id": fila.get("id_pauta"),
            "pauta_version": fila.get("pauta_version"),
        }

        if not args.ejecutar:
            total_filas += len(criterios)
            print(f"{id_feedback:>5}  {len(criterios):>9}  {str(fila.get('id_pauta') or '-'):>6}  "
                  f"{str(fila.get('pauta_version') or '-'):>4}  simulacion")
            continue

        try:
            insertadas = persistir_evaluacion_criterios(id_feedback, analisis)
        except Exception as exc:
            print(f"{id_feedback:>5}  {'-':>9}  {'-':>6}  {'-':>4}  ERROR: {exc}")
            continue

        total_filas += insertadas
        escritas += 1 if insertadas else 0
        detalle = f"{insertadas} filas" if insertadas else "omitida (ya calibrada o sin datos)"
        print(f"{id_feedback:>5}  {len(criterios):>9}  {str(fila.get('id_pauta') or '-'):>6}  "
              f"{str(fila.get('pauta_version') or '-'):>4}  {detalle}")

    print()
    if args.ejecutar:
        print(f"Evaluaciones escritas: {escritas} de {len(pendientes)} | filas insertadas: {total_filas}")
    else:
        print(f"SIMULACION. Se insertarian {total_filas} filas en {len(pendientes)} evaluaciones.")
        print("Vuelve a ejecutar con --ejecutar para escribir.")

    if sin_criterios:
        print(f"\nSin criterios guardados (revisar a mano): {sin_criterios}")

    # Las evaluaciones anteriores a la pauta publicada no tienen id_pauta. Sus
    # filas quedan con id_pauta NULL y NO deben entrar al reporte de precision
    # por pauta: se midieron con las matrices fijas, no con la pauta vigente.
    sin_pauta = [f["id_feedback"] for f in pendientes if not f.get("id_pauta")]
    if sin_pauta:
        print(f"\nAVISO: sin id_pauta (evaluadas antes de publicar la pauta): {sin_pauta}")
        print("Quedan trazables pero no son comparables contra la pauta vigente.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
