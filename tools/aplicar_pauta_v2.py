"""
Aplica la pauta v2 (declaracion escalonada de montos) sobre la base del CRM.

QUE HACE
Ejecuta app/scripts/seed_pauta_general_v2.sql: clona la pauta PUBLICADA en una
version nueva en estado BORRADOR y aplica sobre la copia los dos cambios de la
regla del 16/09/2026 (PECUF.3 y PECN.2). Despues corre las verificaciones y
muestra el resultado.

POR QUE ESTE SCRIPT Y NO EL .SQL A MANO
Usa la misma conexion que el CRM (engine_siscob), asi que no hay credenciales
sueltas ni que abrir SSMS. Y deja el resultado de las verificaciones impreso en
pantalla, que es lo que hay que mirar antes de publicar.

GARANTIAS
- La pauta vigente NO se modifica. Se crea una copia nueva en BORRADOR.
- Todo el bloque de cambios va en una transaccion: o entra completo o no entra.
- Por defecto NO escribe: hay que pasar --ejecutar.
- Es seguro correrlo dos veces por error: avisa si ya existe una version en
  BORRADOR con estos cambios y no crea otra, salvo que se fuerce.

USO
    python tools/aplicar_pauta_v2.py                # verifica y simula
    python tools/aplicar_pauta_v2.py --ejecutar     # crea la v2 en BORRADOR
    python tools/aplicar_pauta_v2.py --solo-verificar

Despues de crearla, la pauta se revisa y se PUBLICA desde la pantalla de
Pautas de evaluacion. Este script no publica nada: publicar cambia como se
evalua, y esa es una decision, no un paso tecnico.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from sqlalchemy import text  # noqa: E402

from app.core.db_siscob import engine_siscob  # noqa: E402

RUTA_SQL = RAIZ / "app" / "scripts" / "seed_pauta_general_v2.sql"


def separar_lotes(sql: str):
    """Divide el script por GO, que es separador de lote y no una sentencia."""
    partes = re.split(r"^\s*GO\s*$", sql, flags=re.MULTILINE | re.IGNORECASE)
    return [p.strip() for p in partes if p.strip()]


def mostrar(titulo, filas, columnas):
    print(f"\n--- {titulo} ---")
    if not filas:
        print("    (sin filas)")
        return
    anchos = [max(len(str(c)), *(len(str(f[i])) for f in filas)) for i, c in enumerate(columnas)]
    print("    " + "  ".join(str(c).ljust(anchos[i]) for i, c in enumerate(columnas)))
    for f in filas:
        print("    " + "  ".join(str(f[i]).ljust(anchos[i]) for i in range(len(columnas))))


def estado_actual(conn):
    filas = conn.execute(text("""
        SELECT id_pauta, nombre, version, estado, aplica_todas
        FROM CobAuto.dbo.CRM_IA_PAUTA
        ORDER BY version
    """)).fetchall()
    mostrar("Pautas existentes", filas, ["id_pauta", "nombre", "version", "estado", "aplica_todas"])
    return filas


def verificar(conn):
    mostrar(
        "Pesos por version (deben sumar 100)",
        conn.execute(text("""
            SELECT P.version, COUNT(*) AS criterios, SUM(C.peso) AS suma_pesos
            FROM CobAuto.dbo.CRM_IA_PAUTA_CRITERIO AS C
            JOIN CobAuto.dbo.CRM_IA_PAUTA AS P ON P.id_pauta = C.id_pauta
            GROUP BY P.version ORDER BY P.version
        """)).fetchall(),
        ["version", "criterios", "suma_pesos"],
    )
    mostrar(
        "Criterios modificados, v1 contra v2",
        conn.execute(text("""
            SELECT P.version, C.codigo_criterio, C.nombre, C.peso, C.fuente_evidencia
            FROM CobAuto.dbo.CRM_IA_PAUTA_CRITERIO AS C
            JOIN CobAuto.dbo.CRM_IA_PAUTA AS P ON P.id_pauta = C.id_pauta
            WHERE C.codigo_criterio IN (N'PECUF.3', N'PECN.2')
            ORDER BY C.codigo_criterio, P.version
        """)).fetchall(),
        ["version", "codigo", "nombre", "peso", "fuente"],
    )
    mostrar(
        "Criterios por bloque y version (no debe perderse ninguno)",
        conn.execute(text("""
            SELECT P.version, B.codigo, COUNT(C.id_criterio) AS criterios
            FROM CobAuto.dbo.CRM_IA_PAUTA AS P
            JOIN CobAuto.dbo.CRM_IA_PAUTA_BLOQUE AS B ON B.id_pauta = P.id_pauta
            LEFT JOIN CobAuto.dbo.CRM_IA_PAUTA_CRITERIO AS C ON C.id_bloque = B.id_bloque
            GROUP BY P.version, B.codigo ORDER BY P.version, B.codigo
        """)).fetchall(),
        ["version", "bloque", "criterios"],
    )


def main():
    parser = argparse.ArgumentParser(description="Crea la pauta v2 en BORRADOR.")
    parser.add_argument("--ejecutar", action="store_true", help="Escribe. Sin esto solo verifica.")
    parser.add_argument("--solo-verificar", action="store_true", help="No escribe, solo muestra el estado.")
    parser.add_argument("--forzar", action="store_true", help="Crea otra version aunque ya exista un BORRADOR.")
    args = parser.parse_args()

    if not RUTA_SQL.exists():
        print(f"No se encontro {RUTA_SQL}")
        return 1

    with engine_siscob.connect() as conn:
        filas = estado_actual(conn)
        if args.solo_verificar:
            verificar(conn)
            return 0

        publicadas = [f for f in filas if str(f[3]).upper() == "PUBLICADA"]
        borradores = [f for f in filas if str(f[3]).upper() == "BORRADOR"]

        if not publicadas:
            print("\nNo hay ninguna pauta PUBLICADA para clonar. No se hace nada.")
            return 1
        if borradores and not args.forzar:
            print(f"\nYa existe una pauta en BORRADOR (version {borradores[-1][2]}).")
            print("Revisala o publicala antes de crear otra. Para crear otra igual: --forzar")
            return 1

    if not args.ejecutar:
        print("\nSIMULACION. Se clonaria la pauta publicada en una version nueva en BORRADOR,")
        print("con PECUF.3 redefinido como declaracion escalonada de montos y PECN.2 acotado")
        print("a la forma de pago. La pauta vigente no se modifica.")
        print("\nVuelve a ejecutar con --ejecutar para aplicarlo.")
        return 0

    sql = RUTA_SQL.read_text(encoding="utf-8")
    lotes = separar_lotes(sql)
    # El ultimo lote del archivo son las consultas de verificacion: se omite
    # aqui y se corre aparte, formateado.
    lotes_cambio = lotes[:1] if len(lotes) > 1 else lotes

    print("\nAplicando...")
    with engine_siscob.begin() as conn:
        for lote in lotes_cambio:
            conn.exec_driver_sql(lote)
    print("Listo.")

    with engine_siscob.connect() as conn:
        estado_actual(conn)
        verificar(conn)

    print("\nLa v2 quedo en BORRADOR. Revisa las tablas de arriba y publicala desde")
    print("la pantalla de Pautas de evaluacion cuando estes conforme.")
    print("Mientras no se publique, PECUF.3 sigue evaluandose como NO_EVALUABLE.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
