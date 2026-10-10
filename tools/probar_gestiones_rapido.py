"""
Prueba (SOLO LECTURA) de una forma mas rapida de consultar las gestiones del Radar.

Por que: en el diagnostico, 'gestiones' fue la etapa mas lenta (1.4 a 4.6 s). Su filtro es
    LTRIM(RTRIM(ISNULL(CL.Dni,''))) = x  OR  LTRIM(RTRIM(ISNULL(G.DNI,''))) = x
Con funciones sobre la columna y un OR entre dos tablas, SQL Server no puede usar los indices
IX_Cliente(Dni) ni IX_gestion_dni_cartera_fecha(DNI, idCartera, Fecha): une CLIENTE con los
14 millones de GESTION y recien filtra.

La alternativa parte cada rama por separado (cada una usa su indice) y las une:
    rama 1: GESTION por G.DNI           rama 2: CLIENTE por CL.Dni -> GESTION por IdCliente
Debe devolver EXACTAMENTE las mismas gestiones, en el mismo orden. Este script lo comprueba
contra la consulta actual con datos reales ANTES de tocar el sistema.

USO
    python tools/probar_gestiones_rapido.py 74922215 20527102 <otro dni o grupo> ...
Cada valor puede ser DNI, operacion, codigo de cliente o grupo (se resuelve igual que el Radar).
"""
from __future__ import annotations

import sys
from pathlib import Path
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text  # noqa: E402

from app.core import autorizacion_carteras as aut  # noqa: E402
from app.core.database import get_connection  # noqa: E402
from app.core.db_siscob import engine_siscob  # noqa: E402
from app.services import cliente_crm_service as crm  # noqa: E402
from app.services.cliente_service import resolver_filas_entidad  # noqa: E402


def dnis_de(valor):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""SELECT * FROM VW_CLIENTE_CRM_SAC WITH (NOLOCK)
                       WHERE DNI = ? OR codcliente = ? OR CodOperacion = ? OR CodigoGrupo = ? OR CodCreGrupal = ?""", [valor] * 5)
        filas = cur.fetchall()
        if not filas:
            return []
        cols = [c[0] for c in cur.description]
        data = resolver_filas_entidad(cur, [dict(zip(cols, f)) for f in filas], valor)
    finally:
        cur.close()
        conn.close()
    dnis = []
    for f in data:
        d = crm.identificador(crm.campo(f, "DNI"))
        if d and d not in dnis:
            dnis.append(d)
    return dnis


def gestiones_nuevas(dnis):
    carteras = sorted(aut.CARTERAS_COMPARTAMOS)
    params = {f"c{i}": c for i, c in enumerate(carteras)}
    fc = ", ".join(f":c{i}" for i in range(len(carteras)))
    params.update({f"d{i}": d for i, d in enumerate(dnis)})
    fd = ", ".join(f":d{i}" for i in range(len(dnis)))
    q = text(f"""
        SELECT TOP 100 G.IdGestion AS id_gestion
        FROM (
            SELECT G1.IdGestion
            FROM SISCOB.DBO.GESTION G1 WITH(NOLOCK)
            INNER JOIN SISCOB.DBO.CLIENTE C1 WITH(NOLOCK) ON C1.IdCliente = G1.IdCliente
            WHERE C1.IdCartera IN ({fc}) AND G1.DNI IN ({fd})
            UNION
            SELECT G2.IdGestion
            FROM SISCOB.DBO.CLIENTE C2 WITH(NOLOCK)
            INNER JOIN SISCOB.DBO.GESTION G2 WITH(NOLOCK) ON G2.IdCliente = C2.IdCliente
            WHERE C2.IdCartera IN ({fc}) AND C2.Dni IN ({fd})
        ) X
        INNER JOIN SISCOB.DBO.GESTION G WITH(NOLOCK) ON G.IdGestion = X.IdGestion
        ORDER BY G.Fecha DESC, G.Hora DESC, G.IdGestion DESC
    """)
    with engine_siscob.connect() as conn:
        return [r[0] for r in conn.execute(q, params).fetchall()]


def operaciones_de(valor):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""SELECT * FROM VW_CLIENTE_CRM_SAC WITH (NOLOCK)
                       WHERE DNI = ? OR codcliente = ? OR CodOperacion = ? OR CodigoGrupo = ? OR CodCreGrupal = ?""", [valor] * 5)
        filas = cur.fetchall()
        cols = [c[0] for c in cur.description]
        data = resolver_filas_entidad(cur, [dict(zip(cols, f)) for f in filas], valor) if filas else []
    finally:
        cur.close()
        conn.close()
    principal = crm.deduplicar_operaciones(data)[0] if data else {}
    ops = [o["operacion"] for o in (crm.normalizar_operacion(r) for r in crm.deduplicar_operaciones(data)) if o.get("operacion")]
    return crm.texto(crm.campo(principal, "DNI")), ops


def comparar(nombre, funcion, extraer):
    """Ejecuta la funcion real del Radar con el prefiltro apagado (comportamiento anterior) y encendido."""
    crm.RADAR_PREFILTRO_SARGABLE = False
    t = perf_counter(); antes = extraer(funcion()); ms_a = (perf_counter() - t) * 1000
    crm.RADAR_PREFILTRO_SARGABLE = True
    t = perf_counter(); despues = extraer(funcion()); ms_n = (perf_counter() - t) * 1000
    return antes == despues, ms_a, ms_n, len(antes), antes, despues


def main():
    valores = sys.argv[1:]
    if not valores:
        print(__doc__)
        sys.exit(1)
    todo_igual = True
    print(f"{'valor':<14}{'fuente':<10}{'antes ms':>10}{'ahora ms':>10}{'filas':>7}  resultado")
    for v in valores:
        dnis = dnis_de(v)
        if not dnis:
            print(f"{v:<14}  sin filas en la vista")
            continue
        dni, ops = operaciones_de(v)
        pruebas = (
            ("gestiones", lambda: crm.consultar_gestiones(dnis), lambda r: [int(h.get("id")) for h in r.get("historial", [])]),
            ("pdp", lambda: crm.consultar_pdp(dni, ops), lambda r: [int(i.get("id")) for i in r.get("historial", r.get("items", r.get("compromisos", [])))]),
        )
        for nombre, fn, ext in pruebas:
            try:
                igual, ms_a, ms_n, n, antes, despues = comparar(nombre, fn, ext)
            except Exception as exc:
                todo_igual = False
                print(f"{v:<14}{nombre:<10}  ERROR {type(exc).__name__}: {str(exc)[:150]}")
                continue
            if not igual:
                todo_igual = False
                res = f"DIFERENTE (solo antes: {len(set(antes) - set(despues))}, solo ahora: {len(set(despues) - set(antes))}; mismo conjunto: {set(antes) == set(despues)})"
            else:
                res = "IGUAL"
            print(f"{v:<14}{nombre:<10}{ms_a:>10.0f}{ms_n:>10.0f}{n:>7}  {res}")
    crm.RADAR_PREFILTRO_SARGABLE = True
    print("\nConclusion:", "todas las pruebas dan el mismo resultado" if todo_igual else "HAY DIFERENCIAS: revisar antes de dejar el prefiltro activo")


if __name__ == "__main__":
    main()
