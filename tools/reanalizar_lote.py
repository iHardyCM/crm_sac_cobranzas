"""
Reanalisis por lote de evaluaciones ya registradas.

QUE HACE
Llama a app.services.ia_audio_service.analizar_feedback para cada id indicado.
Es la MISMA funcion del boton Reanalizar de la ficha: no hay una segunda ruta
de analisis que pueda comportarse distinto.

POR QUE REUSA LA TRANSCRIPCION POR DEFECTO
Volver a transcribir cuesta una llamada de API mas por audio y, sobre todo,
introduce variacion: el mismo audio no produce exactamente la misma
transcripcion dos veces. Si lo que quieres es ver el efecto de la PAUTA sobre
llamadas ya transcritas, conviene dejar la transcripcion fija: asi la unica
variable que cambia son las reglas. Con --forzar-transcripcion se vuelve a
transcribir desde el audio.

OJO CON LA CARTERA
Varios criterios dependen de la cartera para saber contra que entidad
verificar -PENC.1 saludo con identificacion, PECC.1 respeto por la entidad-.
Si la cartera registrada no corresponde al audio real, esos criterios saldran
mal de forma consistente. El script muestra la cartera de cada evaluacion
ANTES de analizar, justamente para que se vea si hay que corregirla primero.

USO
    python tools/reanalizar_lote.py --ids 1 2 3           # simulacion
    python tools/reanalizar_lote.py --ids 1 2 3 --ejecutar
    python tools/reanalizar_lote.py --rango 1 28 --ejecutar
    python tools/reanalizar_lote.py --rango 1 28 --ejecutar --forzar-transcripcion
    python tools/reanalizar_lote.py --rango 1 28 --ejecutar --pausa 3
"""

from __future__ import annotations

import argparse
import sys
import time
import traceback
from pathlib import Path

# La raiz del proyecto es el PADRE de tools/, no tools/ mismo.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text  # noqa: E402

from app.core.db_siscob import engine_siscob  # noqa: E402
from app.services.ia_audio_service import analizar_feedback  # noqa: E402


def evaluaciones(ids):
    if not ids:
        return []
    marcas = ", ".join(f":id{i}" for i in range(len(ids)))
    params = {f"id{i}": valor for i, valor in enumerate(ids)}
    consulta = text(f"""
        SELECT id_feedback, cartera, agente, archivo_nombre, ruta_archivo,
               estado, score_final
        FROM CobAuto.dbo.ia_feedback_llamadas WITH (NOLOCK)
        WHERE id_feedback IN ({marcas})
        ORDER BY id_feedback
    """)
    with engine_siscob.connect() as conn:
        return [dict(f) for f in conn.execute(consulta, params).mappings().all()]


def existe_audio(ruta) -> bool:
    """Sin archivo no hay nada que reanalizar, y conviene saberlo antes de
    gastar la primera llamada de API."""
    if not ruta:
        return False
    try:
        return Path(str(ruta)).is_file()
    except OSError:
        return False


def main():
    parser = argparse.ArgumentParser(description="Reanalisis por lote de evaluaciones.")
    parser.add_argument("--ids", nargs="*", type=int, default=None, help="Ids concretos.")
    parser.add_argument("--rango", nargs=2, type=int, metavar=("DESDE", "HASTA"), default=None)
    parser.add_argument("--ejecutar", action="store_true", help="Analiza. Sin esto solo lista.")
    parser.add_argument("--forzar-transcripcion", action="store_true",
                        help="Vuelve a transcribir el audio. Por defecto reusa la transcripcion guardada.")
    parser.add_argument("--pausa", type=float, default=2.0,
                        help="Segundos entre llamadas, para no saturar la API. Default 2.")
    args = parser.parse_args()

    ids = list(args.ids or [])
    if args.rango:
        desde, hasta = args.rango
        ids.extend(range(desde, hasta + 1))
    ids = sorted(set(ids))
    if not ids:
        print("Indica --ids o --rango.")
        return 1

    filas = evaluaciones(ids)
    if not filas:
        print("Ninguno de esos id_feedback existe.")
        return 1

    faltantes = sorted(set(ids) - {f["id_feedback"] for f in filas})
    if faltantes:
        print(f"AVISO: no existen en la tabla: {faltantes}\n")

    print(f"{'id':>5}  {'cartera':<32}  {'audio':<8}  {'score':>6}  estado")
    sin_audio = []
    for fila in filas:
        hay_audio = existe_audio(fila.get("ruta_archivo"))
        if not hay_audio:
            sin_audio.append(fila["id_feedback"])
        score = fila.get("score_final")
        print(f"{fila['id_feedback']:>5}  {str(fila.get('cartera') or '- SIN CARTERA -')[:32]:<32}  "
              f"{'ok' if hay_audio else 'FALTA':<8}  "
              f"{(f'{float(score):.1f}' if score is not None else '-'):>6}  "
              f"{fila.get('estado') or '-'}")

    if sin_audio:
        print(f"\nSin archivo de audio en disco ({len(sin_audio)}): {sin_audio}")
        print("Esas se omiten: no hay nada que reanalizar.")

    # La cartera decide contra que entidad se verifican PENC.1 y PECC.1. Si no
    # esta, esos criterios no tienen con que compararse.
    sin_cartera = [f["id_feedback"] for f in filas if not str(f.get("cartera") or "").strip()]
    if sin_cartera:
        print(f"\nAVISO: sin cartera registrada ({len(sin_cartera)}): {sin_cartera}")
        print("Los criterios que dependen de la entidad quedaran sin poder verificarse.")

    procesables = [f for f in filas if existe_audio(f.get("ruta_archivo"))]

    if not args.ejecutar:
        print(f"\nSIMULACION. Se reanalizarian {len(procesables)} evaluaciones.")
        print("Revisa las carteras de arriba. Si alguna no corresponde al audio real,")
        print("corrigela ANTES: los criterios de entidad saldran mal de forma consistente.")
        print("\nVuelve a ejecutar con --ejecutar cuando estes conforme.")
        return 0

    modo = "re-transcribiendo" if args.forzar_transcripcion else "reusando la transcripcion guardada"
    print(f"\nAnalizando {len(procesables)} evaluaciones, {modo}.\n")

    ok = 0
    errores = []
    for indice, fila in enumerate(procesables, start=1):
        id_feedback = fila["id_feedback"]
        inicio = time.time()
        try:
            # Un fallo en una llamada no debe tumbar el lote entero: se anota
            # y se sigue con la siguiente.
            resultado = analizar_feedback(id_feedback, forzar_transcripcion=args.forzar_transcripcion)
            score = (resultado or {}).get("score_final") or (resultado or {}).get("score_calidad")
            ok += 1
            print(f"[{indice}/{len(procesables)}] id={id_feedback}  score={score}  "
                  f"({time.time() - inicio:.1f}s)")
        except Exception as exc:
            errores.append((id_feedback, f"{type(exc).__name__}: {exc}"))
            print(f"[{indice}/{len(procesables)}] id={id_feedback}  ERROR: {type(exc).__name__}: {exc}")
            traceback.print_exc(limit=2)
        if indice < len(procesables) and args.pausa > 0:
            time.sleep(args.pausa)

    print(f"\nAnalizadas: {ok} de {len(procesables)}")
    if errores:
        print(f"Con error ({len(errores)}):")
        for id_feedback, detalle in errores:
            print(f"  {id_feedback}: {detalle}")

    print("\nLa evaluacion por criterio se persiste sola al cerrar cada analisis,")
    print("salvo que la evaluacion ya tuviera filas. Para reescribir esas:")
    print("  python tools/backfill_evaluacion_criterios.py --ejecutar --rehacer --ids <ids>")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
