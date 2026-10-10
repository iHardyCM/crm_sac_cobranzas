"""
Explora (SOLO LECTURA) de donde sale la calificacion en las tablas de asignacion de Compartamos.

Regla de negocio acordada: la calificacion NO se toma de SAC (VW_CLIENTE_CRM_SAC) sino de la asignacion:
    grupal     -> Desarrollo.dbo.compartamos_grupal          (hoy: columna Cal_PROV)
    individual -> Desarrollo.dbo.compartamos_individual
    ccm        -> Desarrollo.dbo.compartamos_ccm
    castigo    -> Desarrollo.dbo.compartamos_castigo          (individual)
                  Desarrollo.dbo.compartamos_grupal_castigo   (grupal)
                  y alli no hay calificacion sino segmentacion verde/ambar/rojo.

Este script NO adivina nombres de columna: lista las columnas candidatas de cada tabla
(que contengan cal / segm / prov / semaf / color / riesgo) y muestra sus valores para el
cliente que indiques, para confirmar con datos reales cual es la correcta.

USO
    python tools/explorar_calificacion.py 74922215        # DNI, operacion, codigo cliente o grupo
Prueba con: un cliente individual, uno CCM, un castigo individual, un grupo y un castigo grupal.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.database import get_connection  # noqa: E402
from app.services import cliente_crm_service as crm  # noqa: E402
from app.services.cliente_service import resolver_filas_entidad  # noqa: E402

TABLAS = ["compartamos_individual", "compartamos_ccm", "compartamos_grupal",
          "compartamos_castigo", "compartamos_grupal_castigo"]
PATRONES = ("cal", "segm", "prov", "semaf", "color", "riesgo", "categ", "clasif")
LLAVES = ("NumDoc", "DNI", "Operacion", "CodOperacion", "LinNeg", "CodigoGrupo", "CodCreGrupal")


def entidad(cur, valor):
    cur.execute("""SELECT * FROM VW_CLIENTE_CRM_SAC WITH (NOLOCK)
                   WHERE DNI = ? OR codcliente = ? OR CodOperacion = ? OR CodigoGrupo = ? OR CodCreGrupal = ?""", [valor] * 5)
    filas = cur.fetchall()
    if not filas:
        return [], []
    cols = [c[0] for c in cur.description]
    data = resolver_filas_entidad(cur, [dict(zip(cols, f)) for f in filas], valor)
    dnis, ops = [], []
    for f in data:
        d = crm.identificador(crm.campo(f, "DNI"))
        if d and d not in dnis:
            dnis.append(d)
    for o in crm.deduplicar_operaciones(data):
        op = crm.normalizar_operacion(o).get("operacion")
        if op and op not in ops:
            ops.append(op)
    return dnis, ops


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    valor = sys.argv[1].strip()
    conn = get_connection()
    cur = conn.cursor()
    try:
        dnis, ops = entidad(cur, valor)
        print(f"\n=== «{valor}» -> {len(dnis)} DNI(s), {len(ops)} operacion(es) segun la vista ===")
        if not dnis:
            print("La vista no devolvio filas; prueba con otro valor.")
            return
        for tabla in TABLAS:
            print(f"\n--- Desarrollo.dbo.{tabla} ---")
            cur.execute("""SELECT COLUMN_NAME, DATA_TYPE FROM Desarrollo.INFORMATION_SCHEMA.COLUMNS
                           WHERE TABLE_NAME = ? ORDER BY ORDINAL_POSITION""", [tabla])
            columnas = [(r[0], r[1]) for r in cur.fetchall()]
            if not columnas:
                print("   (no existe o no hay permiso para verla)")
                continue
            nombres = [c for c, _ in columnas]
            candidatas = [c for c in nombres if any(p in c.lower() for p in PATRONES)]
            llaves = [k for k in LLAVES if any(k.lower() == c.strip().lower() for c in nombres)]
            print(f"   {len(nombres)} columnas. Candidatas a calificacion/segmentacion: {candidatas or 'NINGUNA'}")
            print(f"   Columnas llave encontradas: {llaves or 'NINGUNA'}")
            reales = {k: next(c for c in nombres if c.strip().lower() == k.lower()) for k in llaves}
            filtros, params = [], []
            for k in ("NumDoc", "DNI"):
                if k in reales:
                    filtros.append(f"LTRIM(RTRIM(CONVERT(VARCHAR(40), [{reales[k]}]))) IN ({','.join('?' * len(dnis))})")
                    params += dnis
            for k in ("Operacion", "CodOperacion"):
                if k in reales and ops:
                    filtros.append(f"LTRIM(RTRIM(CONVERT(VARCHAR(60), [{reales[k]}]))) IN ({','.join('?' * len(ops))})")
                    params += ops
            if not filtros:
                print("   Sin columna llave conocida: no se puede buscar al cliente aqui.")
                continue
            mostrar = list(dict.fromkeys([reales[k] for k in llaves] + candidatas))
            sel = ", ".join(f"[{c}]" for c in mostrar)
            cur.execute(f"SELECT TOP 8 {sel} FROM Desarrollo.dbo.{tabla} WITH (NOLOCK) WHERE " + " OR ".join(filtros), params)
            filas = cur.fetchall()
            print(f"   Filas del cliente en esta tabla: {len(filas)}" + (" (se muestran hasta 8)" if len(filas) == 8 else ""))
            for f in filas:
                print("     " + " | ".join(f"{c}={str(v).strip() if v is not None else 'NULL'}" for c, v in zip(mostrar, f)))
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
