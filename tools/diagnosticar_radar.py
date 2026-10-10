"""
Diagnostico de lentitud del Radar Compartamos (busqueda de cliente / grupo).

SOLO LEE: no escribe ni modifica nada en la base.

QUE HACE
  1. Mide cada etapa de una busqueda real por separado:
       vista (VW_CLIENTE_CRM_SAC) -> entidad -> acceso por cartera (SISCOB.CLIENTE)
       -> gestiones -> pagos -> compromisos (PDP) -> [grupo] compartamos_grupal -> cronograma
  2. Compara la consulta de cartera tal como esta hoy (LTRIM/RTRIM sobre Dni, que
     impide usar un indice) contra la misma consulta sin funciones sobre la columna.
  3. Lista los indices que existen hoy en las tablas que usa el Radar y su cantidad de filas.
  4. Ejecuta la busqueda completa 2 veces (la 2.a ya con datos en cache del servidor SQL).

USO (desde la carpeta del proyecto, con el mismo .env del backend)
    python tools/diagnosticar_radar.py 12345678            # un DNI / operacion / cliente
    python tools/diagnosticar_radar.py 20527102            # un credito grupal o codigo de grupo
Prueba con 1 DNI y 1 grupo: asi se ven las dos rutas.
"""
from __future__ import annotations

import sys
from pathlib import Path
from time import perf_counter

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from sqlalchemy import text  # noqa: E402

from app.core.database import get_connection  # noqa: E402
from app.core.db_siscob import engine_siscob  # noqa: E402
from app.core import autorizacion_carteras as aut  # noqa: E402
from app.services import cliente_crm_service as crm  # noqa: E402
from app.services.cliente_service import buscar_cliente, resolver_filas_entidad  # noqa: E402

RESULTADOS = []


def medir(etiqueta, fn):
    t = perf_counter()
    try:
        valor = fn()
        ms = (perf_counter() - t) * 1000
        RESULTADOS.append((etiqueta, ms, "ok"))
        return valor
    except Exception as exc:  # el diagnostico sigue aunque una etapa falle
        ms = (perf_counter() - t) * 1000
        RESULTADOS.append((etiqueta, ms, f"ERROR: {type(exc).__name__}: {str(exc)[:120]}"))
        return None


def etapas(valor):
    conn = get_connection()
    cur = conn.cursor()
    try:
        def vista():
            cur.execute("""
                SELECT * FROM VW_CLIENTE_CRM_SAC WITH (NOLOCK)
                WHERE DNI = ? OR codcliente = ? OR CodOperacion = ? OR CodigoGrupo = ? OR CodCreGrupal = ?
            """, [valor] * 5)
            filas = cur.fetchall()
            cols = [c[0] for c in cur.description]
            return [dict(zip(cols, f)) for f in filas]

        datos = medir("1. vista VW_CLIENTE_CRM_SAC (consulta inicial, 5 OR)", vista)
        if not datos:
            print("La vista no devolvio filas para ese valor; prueba con otro.")
            return
        print(f"   filas devueltas por la vista: {len(datos)}")
        entidad = medir("2. ampliar a la entidad completa", lambda: resolver_filas_entidad(cur, datos, str(valor).strip()))
        entidad = entidad or datos
        print(f"   filas de la entidad: {len(entidad)}")
    finally:
        cur.close()
        conn.close()

    dnis = []
    for f in entidad:
        d = crm.texto(crm.campo(f, "DNI"))
        if d and d not in dnis:
            dnis.append(d)
    principal = crm.deduplicar_operaciones(entidad)[0]
    dni = crm.texto(crm.campo(principal, "DNI"))
    codcliente = crm.texto(crm.campo(principal, "codcliente", "CodCliente"))
    ops = [o["operacion"] for o in (crm.normalizar_operacion(r) for r in crm.deduplicar_operaciones(entidad)) if o.get("operacion")]
    print(f"   DNIs distintos: {len(dnis)} · operaciones: {len(ops)}")

    por_dni = medir("3. acceso por cartera (SISCOB.CLIENTE)", lambda: aut.carteras_compartamos_por_dni(dnis))
    medir("4. gestiones (SISCOB: CLIENTE+GESTION+INDICADOR+USUARIO)", lambda: crm.consultar_gestiones(dnis, carteras_por_dni=por_dni))
    medir("5. pagos (PAGOS_BI_NORMALIZADO)", lambda: crm.consultar_pagos(dni, codcliente, ops))
    medir("6. compromisos / PDP (SISCOB.COMPROMISO)", lambda: crm.consultar_pdp(dni, ops))
    if crm.resolver_tipo_resultado(entidad, str(valor).strip()) == "GRUPO":
        codigos = crm.codigos_grupo(entidad)
        medir("7. compartamos_grupal (Desarrollo)", lambda: crm.consultar_datos_grupal(codigos))
        medir("8. cronograma SAC_CAR_BIZNESCOB (Desarrollo)", lambda: crm.consultar_cronograma_grupo(codigos))
    else:
        print("   (no es grupo: se omiten compartamos_grupal y cronograma; prueba tambien con un grupo)")
    medir("9. calificacion/segmentacion (4 tablas de asignacion, en paralelo)", lambda: crm.consultar_calificacion_asignacion(dnis))
    for tabla, cols_dni, cols_op, col_valor, tipo in crm.FUENTES_ASIGNACION:
        medir(f"   9.x solo {tabla}", lambda t=tabla, a=cols_dni, b=cols_op, c=col_valor, d=tipo:
              crm.consultar_tabla_asignacion(t, a, b, c, d, crm.variantes_documento(dnis)))
    return dnis


def sargabilidad(dnis):
    if not dnis:
        return
    carteras = sorted(aut.CARTERAS_COMPARTAMOS)
    base = {f"c{i}": c for i, c in enumerate(carteras)}
    filtro_c = ", ".join(f":c{i}" for i in range(len(carteras)))
    muestra = dnis[:50]
    pd = {f"d{i}": d for i, d in enumerate(muestra)}
    filtro_d = ", ".join(f":d{i}" for i in range(len(muestra)))
    params = {**base, **pd}
    hoy = text(f"""SELECT DISTINCT LTRIM(RTRIM(ISNULL(CL.Dni,''))) AS DNI, CL.IdCartera
                   FROM SISCOB.DBO.CLIENTE CL WITH(NOLOCK)
                   WHERE CL.IdCartera IN ({filtro_c}) AND LTRIM(RTRIM(ISNULL(CL.Dni,''))) IN ({filtro_d})""")
    directo = text(f"""SELECT DISTINCT LTRIM(RTRIM(ISNULL(CL.Dni,''))) AS DNI, CL.IdCartera
                       FROM SISCOB.DBO.CLIENTE CL WITH(NOLOCK)
                       WHERE CL.IdCartera IN ({filtro_c}) AND CL.Dni IN ({filtro_d})""")
    res = {}
    for nombre, q in (("como esta hoy (LTRIM/RTRIM sobre la columna)", hoy), ("sin funciones sobre la columna", directo)):
        with engine_siscob.connect() as conn:
            t = perf_counter()
            filas = conn.execute(q, params).fetchall()
            res[nombre] = ((perf_counter() - t) * 1000, {(str(f[0]).strip(), int(f[1])) for f in filas})
    (n1, (t1, r1)), (n2, (t2, r2)) = list(res.items())
    print(f"   {n1}: {t1:.0f} ms, {len(r1)} filas")
    print(f"   {n2}: {t2:.0f} ms, {len(r2)} filas")
    print("   ¿mismo resultado? " + ("SI" if r1 == r2 else f"NO (difieren {len(r1 ^ r2)} filas: hay DNIs con espacios; no se puede quitar el TRIM sin limpiar el dato)"))


TABLAS = [("SISCOB", "CLIENTE"), ("SISCOB", "GESTION"), ("SISCOB", "COMPROMISO"), ("SISCOB", "INDICADOR"),
          ("SISCOB", "USUARIO"), ("Desarrollo", "compartamos_grupal"), ("Desarrollo", "compartamos_individual"), ("Desarrollo", "compartamos_ccm"), ("Desarrollo", "compartamos_castigo"), ("Desarrollo", "compartamos_grupal_castigo"), ("Desarrollo", "SAC_CAR_BIZNESCOB"), (None, "PAGOS_BI_NORMALIZADO")]


def indices():
    for bd, tabla in TABLAS:
        prefijo = f"{bd}." if bd else ""
        q = text(f"""
            SELECT i.name AS indice, i.type_desc AS tipo,
                   STUFF((SELECT ', ' + c.name + CASE WHEN ic2.is_descending_key = 1 THEN ' DESC' ELSE '' END
                          FROM {prefijo}sys.index_columns ic2 JOIN {prefijo}sys.columns c ON c.object_id = ic2.object_id AND c.column_id = ic2.column_id
                          WHERE ic2.object_id = i.object_id AND ic2.index_id = i.index_id AND ic2.is_included_column = 0
                          ORDER BY ic2.key_ordinal FOR XML PATH('')), 1, 2, '') AS columnas_clave,
                   (SELECT SUM(p.rows) FROM {prefijo}sys.partitions p WHERE p.object_id = i.object_id AND p.index_id IN (0, 1)) AS filas
            FROM {prefijo}sys.indexes i JOIN {prefijo}sys.objects o ON o.object_id = i.object_id
            WHERE o.name = :t AND o.type = 'U' AND i.type > 0 ORDER BY i.index_id
        """)
        try:
            with engine_siscob.connect() as conn:
                filas = conn.execute(q, {"t": tabla}).fetchall()
        except Exception as exc:
            print(f"   {prefijo}{tabla}: no se pudo leer ({type(exc).__name__})")
            continue
        if not filas:
            print(f"   {prefijo}{tabla}: sin indices (o sin permiso para verlos / es una vista)")
            continue
        print(f"   {prefijo}{tabla}  (~{int(filas[0].filas or 0):,} filas)")
        for f in filas:
            print(f"      - {f.indice or '(heap)'} [{f.tipo}]  clave: {f.columnas_clave or '—'}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    valor = sys.argv[1].strip()
    print(f"\n=== Radar: diagnostico para «{valor}» ===")
    print("\n[A] Etapas por separado")
    dnis = etapas(valor)
    print("\n[B] Consulta de cartera: hoy vs sin funciones sobre la columna")
    sargabilidad(dnis)
    print("\n[C] Indices existentes")
    indices()
    print("\n[D] Busqueda completa, 2 veces")
    for i in (1, 2):
        medir(f"busqueda completa #{i}", lambda: buscar_cliente(valor=valor, verificar_acceso=None))
    print("\n=== RESUMEN (ms) ===")
    total_etapas = 0.0
    for etiqueta, ms, estado in RESULTADOS:
        print(f"{ms:9.0f}  {etiqueta}  {'' if estado == 'ok' else estado}")
        if etiqueta[0].isdigit() and not etiqueta.startswith("9.x"):
            total_etapas += ms
    print(f"{total_etapas:9.0f}  suma de etapas 1 a 9 (sin las lineas 9.x) (la busqueda real las ejecuta una tras otra)")


if __name__ == "__main__":
    main()
