"""
Backfill de CRM_IA_EVALUACION_CRITERIO desde las evaluaciones ya guardadas.

POR QUE ES UN SCRIPT PYTHON Y NO SQL
La evaluacion por criterio vive como JSON en ia_feedback_llamadas.evaluacion_calidad,
y la traza de la pauta vive dentro de resumen_sgc. CobAuto esta en nivel de
compatibilidad 120, donde OPENJSON no existe y solo hay JSON_VALUE, que no
recorre un arreglo. Por eso el JSON se parsea aqui y no en SQL.

QUE HACE
Para cada evaluacion FINALIZADA escribe una fila por criterio llamando a
app.services.ia_audio_service.persistir_evaluacion_criterios, que es la MISMA
funcion que usa el flujo normal al cerrar un analisis. No hay una segunda
implementacion del INSERT que pueda quedar desalineada.

GARANTIAS
- Por defecto NO escribe nada: hay que pasar --ejecutar.
- Es idempotente: una evaluacion que ya tiene filas se omite.
- --rehacer reescribe evaluaciones que ya tienen filas, y la propia funcion
  rechaza las que tengan calibraciones humanas registradas.
- No modifica ia_feedback_llamadas ni ninguna evaluacion existente.

USO
    python tools/backfill_evaluacion_criterios.py                # simulacion
    python tools/backfill_evaluacion_criterios.py --ejecutar     # escribe
    python tools/backfill_evaluacion_criterios.py --ids 28 29 30 # solo esas
    python tools/backfill_evaluacion_criterios.py --ejecutar --rehacer --ids 36
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# La raiz del proyecto es el PADRE de tools/, no tools/ mismo. Python agrega al
# path la carpeta del script, no el directorio desde el que se lanza, asi que
# sin esto "import app" falla aunque estes parado en la raiz.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text  # noqa: E402

from app.core.db_siscob import engine_siscob  # noqa: E402
from app.services.ia_audio_service import persistir_evaluacion_criterios  # noqa: E402


def cargar_json(value):
    """La columna puede venir como texto JSON, como estructura ya parseada o vacia."""
    if not value:
        return None
    if isinstance(value, (list, dict)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return None


def cargar_lista(value):
    data = cargar_json(value)
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for clave in ("evaluacion_calidad", "criterios", "items"):
            if isinstance(data.get(clave), list):
                return data[clave]
    return []


def traza_pauta(resumen_sgc_raw):
    """Nombre, id y version de la pauta con la que se evaluo.

    NO estan como columnas en ia_feedback_llamadas: viven dentro del JSON de
    resumen_sgc, y en las evaluaciones mas nuevas tambien dentro de su
    json_copc_v2. Se busca en los dos sitios, sin inventar un valor cuando no
    esta.

    Ojo con "nombre": tambien se llena con los respaldos de las matrices fijas
    (COPC_SGC, MIBANCO), que no son pautas de CRM_IA_PAUTA. Quien decide si hay
    pauta de verdad es persistir_evaluacion_criterios, buscando el par
    (nombre, version) en la tabla. Aqui solo se transporta lo que quedo escrito.
    """
    resumen = cargar_json(resumen_sgc_raw)
    if not isinstance(resumen, dict):
        return None, None, None
    fuentes = [resumen]
    interno = resumen.get("json_copc_v2")
    if isinstance(interno, dict):
        fuentes.append(interno)
    nombre = None
    id_pauta = None
    version = None
    for fuente in fuentes:
        if nombre is None and fuente.get("pauta"):
            nombre = fuente.get("pauta")
        if id_pauta is None and fuente.get("id_pauta") is not None:
            id_pauta = fuente.get("id_pauta")
        if version is None and fuente.get("pauta_version") is not None:
            version = fuente.get("pauta_version")
    return nombre, id_pauta, version


def pautas_registradas():
    """(nombre, version) -> id_pauta. Solo para MOSTRAR en la simulacion lo
    mismo que va a decidir persistir_evaluacion_criterios al escribir."""
    with engine_siscob.connect() as conn:
        filas = conn.execute(text("""
            SELECT id_pauta, nombre, version FROM CobAuto.dbo.CRM_IA_PAUTA
        """)).mappings().all()
    return {(str(f["nombre"]).strip(), int(f["version"])): int(f["id_pauta"]) for f in filas}


def version_entera(value):
    if value is None or str(value).strip() == "":
        return None
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return None


def candidatos(ids=None, incluir_existentes=False):
    """Evaluaciones finalizadas con evaluacion por criterio guardada."""
    condiciones = ["F.estado = 'FINALIZADO'", "F.evaluacion_calidad IS NOT NULL"]
    params = {}
    if not incluir_existentes:
        condiciones.append("""NOT EXISTS (
              SELECT 1 FROM CobAuto.dbo.CRM_IA_EVALUACION_CRITERIO AS C
              WHERE C.id_feedback = F.id_feedback
          )""")
    if ids:
        marcas = ", ".join(f":id{i}" for i in range(len(ids)))
        condiciones.append(f"F.id_feedback IN ({marcas})")
        params = {f"id{i}": valor for i, valor in enumerate(ids)}

    consulta = text(f"""
        SELECT F.id_feedback,
               F.evaluacion_calidad,
               F.resumen_sgc
        FROM CobAuto.dbo.ia_feedback_llamadas AS F WITH (NOLOCK)
        WHERE {" AND ".join(condiciones)}
        ORDER BY F.id_feedback
    """)
    with engine_siscob.connect() as conn:
        filas = conn.execute(consulta, params).mappings().all()
    return [dict(fila) for fila in filas]


def main():
    parser = argparse.ArgumentParser(description="Backfill de evaluacion por criterio.")
    parser.add_argument("--ejecutar", action="store_true", help="Escribe. Sin esto solo simula.")
    parser.add_argument("--ids", nargs="*", type=int, default=None, help="Limita a estos id_feedback.")
    parser.add_argument(
        "--rehacer",
        action="store_true",
        help="Reescribe evaluaciones que ya tienen filas. Las que tengan calibracion humana se rechazan.",
    )
    args = parser.parse_args()

    with engine_siscob.connect() as conn:
        existe = conn.execute(
            text("SELECT OBJECT_ID('CobAuto.dbo.CRM_IA_EVALUACION_CRITERIO', 'U')")
        ).scalar()
    if not existe:
        print("La tabla CRM_IA_EVALUACION_CRITERIO no existe. Ejecuta antes app/scripts/ddl_calibracion_ia.sql.")
        return 1

    pendientes = candidatos(args.ids, incluir_existentes=args.rehacer)
    if not pendientes:
        print("No hay evaluaciones que procesar con estos filtros.")
        return 0

    if args.rehacer and args.ejecutar:
        print("MODO REHACER: se borran y reescriben las filas de estas evaluaciones.")
        print("Las que tengan calibraciones humanas se rechazan sin tocar nada.\n")

    catalogo = pautas_registradas()

    print(f"{'id':>5}  {'criterios':>9}  {'pauta declarada':>30}  {'ver':>4}  {'id':>4}  estado")
    total_filas = 0
    escritas = 0
    sin_criterios = []
    sin_pauta = []

    for fila in pendientes:
        id_feedback = fila["id_feedback"]
        criterios = cargar_lista(fila.get("evaluacion_calidad"))
        nombre_pauta, id_pauta, pauta_version = traza_pauta(fila.get("resumen_sgc"))
        if id_pauta is None:
            id_pauta = catalogo.get((str(nombre_pauta or "").strip(), version_entera(pauta_version)))
        col_nombre = (str(nombre_pauta or "-"))[:30]
        col_version = str(pauta_version if pauta_version is not None else "-")
        col_pauta = str(id_pauta if id_pauta is not None else "-")
        if id_pauta is None:
            sin_pauta.append(id_feedback)

        if not criterios:
            sin_criterios.append(id_feedback)
            print(f"{id_feedback:>5}  {0:>9}  {col_nombre:>30}  {col_version:>4}  {col_pauta:>4}  sin criterios: se omite")
            continue

        analisis = {
            "evaluacion_calidad": criterios,
            "pauta": nombre_pauta,
            "id_pauta": id_pauta,
            "pauta_version": pauta_version,
        }

        if not args.ejecutar:
            total_filas += len(criterios)
            print(f"{id_feedback:>5}  {len(criterios):>9}  {col_nombre:>30}  {col_version:>4}  {col_pauta:>4}  simulacion")
            continue

        try:
            insertadas = persistir_evaluacion_criterios(id_feedback, analisis, rehacer=args.rehacer)
        except Exception as exc:
            print(f"{id_feedback:>5}  {len(criterios):>9}  {col_nombre:>30}  {col_version:>4}  {col_pauta:>4}  ERROR: {exc}")
            continue

        total_filas += insertadas
        escritas += 1 if insertadas else 0
        detalle = f"{insertadas} filas" if insertadas else "omitida (ya tenia filas)"
        print(f"{id_feedback:>5}  {len(criterios):>9}  {col_nombre:>30}  {col_version:>4}  {col_pauta:>4}  {detalle}")

    print()
    if args.ejecutar:
        print(f"Evaluaciones escritas: {escritas} de {len(pendientes)} | filas insertadas: {total_filas}")
    else:
        print(f"SIMULACION. Se insertarian hasta {total_filas} filas en {len(pendientes)} evaluaciones.")
        print("Vuelve a ejecutar con --ejecutar para escribir.")

    if sin_criterios:
        print(f"\nSin criterios guardados (revisar a mano): {sin_criterios}")

    # Una evaluacion cuyo par (nombre, version) no esta en CRM_IA_PAUTA se
    # evaluo con una matriz fija, no con una pauta. Su fila se guarda igual y
    # queda trazable por id_feedback, pero con id_pauta y pauta_version en NULL
    # a proposito: no es comparable en el reporte de precision por pauta.
    if sin_pauta:
        print(f"\nAVISO: {len(sin_pauta)} evaluacion(es) sin pauta identificable en CRM_IA_PAUTA:")
        print(f"  {sin_pauta}")
        print("  Se guardan con id_pauta y pauta_version en NULL. Son trazables por")
        print("  id_feedback, pero quedan fuera del reporte de precision por pauta.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
