"""
Compara el SP original de Control Horario contra la version V2 (optimizada).

Ejecuta ambos con los mismos parametros y revisa, resultset por resultset,
que las columnas y las filas sean exactamente iguales. Mide el tiempo de cada uno.
No modifica nada en la base de datos (solo ejecuta los SP, que solo leen).

Uso (desde la carpeta del proyecto, con el entorno virtual activado):
    python tools/comparar_sp_control_horario.py                      # ayer, todas las carteras
    python tools/comparar_sp_control_horario.py --fecha 2026-10-07
    python tools/comparar_sp_control_horario.py --fecha 2026-10-07 --idcartera 117 --idcartera 133

Recomendacion: comparar primero con una fecha cerrada (ayer). Con la fecha de hoy
pueden entrar gestiones nuevas entre una ejecucion y otra y aparecer diferencias
que no son del SP.
"""
import argparse
import sys
import time
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import get_connection  # noqa: E402

SP_ORIGINAL = "dbo.SP_CRM_CONTROL_HORARIO_GESTION_RECUPERO"
SP_V2 = "dbo.SP_CRM_CONTROL_HORARIO_GESTION_RECUPERO_V2"

# Columnas que dependen del reloj y no del dato (se ignoran al comparar).
COLUMNAS_IGNORADAS = {"ULTIMO_CORTE"}


def ejecutar(nombre, fecha, idcartera, idusuario):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        inicio = time.perf_counter()
        cursor.execute(
            f"EXEC {nombre} @Fecha = ?, @IdCartera = ?, @IdUsuario = ?",
            fecha, idcartera, idusuario,
        )
        resultados = []
        while True:
            if cursor.description is not None:
                columnas = [c[0] for c in cursor.description]
                filas = [tuple(f) for f in cursor.fetchall()]
                resultados.append((columnas, filas))
            if not cursor.nextset():
                break
        return resultados, time.perf_counter() - inicio
    finally:
        cursor.close()
        conn.close()


def normalizar(columnas, filas):
    indices = [i for i, c in enumerate(columnas) if c not in COLUMNAS_IGNORADAS]
    return Counter(tuple(repr(f[i]) for i in indices) for f in filas)


def comparar(original, v2):
    todo_igual = len(original) == len(v2)
    if not todo_igual:
        print(f"  DIFERENTE: cantidad de resultsets original={len(original)} v2={len(v2)}")
    for n, ((cols_a, filas_a), (cols_b, filas_b)) in enumerate(zip(original, v2), start=1):
        if cols_a != cols_b:
            todo_igual = False
            print(f"  Resultset {n}: DIFERENTE (columnas)\n    original={cols_a}\n    v2      ={cols_b}")
            continue
        a = normalizar(cols_a, filas_a)
        b = normalizar(cols_b, filas_b)
        if a == b:
            print(f"  Resultset {n}: igual ({len(filas_a)} filas)")
            continue
        todo_igual = False
        print(f"  Resultset {n}: DIFERENTE (original {len(filas_a)} filas, v2 {len(filas_b)} filas)")
        solo_a = list((a - b).elements())[:5]
        solo_b = list((b - a).elements())[:5]
        for fila in solo_a:
            print("    solo en ORIGINAL:", fila)
        for fila in solo_b:
            print("    solo en V2      :", fila)
    return todo_igual


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--fecha", default=(date.today() - timedelta(days=1)).isoformat())
    parser.add_argument("--idcartera", type=int, action="append", default=[])
    parser.add_argument("--idusuario", type=int, default=None)
    args = parser.parse_args()

    casos = [None] + args.idcartera
    resumen = []
    for idcartera in casos:
        etiqueta = f"fecha={args.fecha} idcartera={idcartera if idcartera is not None else 'TODAS'}"
        print(f"\n=== {etiqueta} ===")
        original, t_original = ejecutar(SP_ORIGINAL, args.fecha, idcartera, args.idusuario)
        v2, t_v2 = ejecutar(SP_V2, args.fecha, idcartera, args.idusuario)
        print(f"  Tiempo original: {t_original:.1f} s | V2: {t_v2:.1f} s")
        igual = comparar(original, v2)
        resumen.append((etiqueta, igual))

    print("\n=== RESUMEN ===")
    for etiqueta, igual in resumen:
        print(("OK        " if igual else "DIFERENTE ") + etiqueta)
    return 0 if all(i for _, i in resumen) else 1


if __name__ == "__main__":
    sys.exit(main())
