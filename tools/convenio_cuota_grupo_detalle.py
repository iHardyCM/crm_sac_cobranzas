"""Convenio de cancelación cuota grupo con detalle por cuota (5, 6, 7...) de cada integrante.

El documento del CRM pone una sola fila por integrante (su cuota más atrasada). Este script usa la
misma plantilla y los mismos datos (compartamos_grupal + SAC), pero pone una fila por integrante y
por cada cuota acordada, con lo que paga por esa cuota.

Regla (26/11/2026):
  · Cuota de cada integrante: CT 1 es su cuota Ult_CuotaAtrasada, CT 2 la siguiente y CT 3 la
    subsiguiente (solo capital, la misma regla del cronograma del Radar).
  · Propuesta de la cuota N (monto que paga el grupo por esa cuota) se reparte en proporción al
    capital de la cuota N de cada integrante:  paga_i = propuesta_N × capital_i ÷ capital_N.
    Equivale a pagar (100 % − % propuesta) de su cuota capital.
  · Redondeo a céntimos; la diferencia de redondeo va al integrante con más capital en esa cuota,
    para que la suma sea exactamente la propuesta.
  · Nota de abono: igual que el documento del CRM, por operación (deuda total − lo que paga).

Uso (desde la carpeta del CRM, con el mismo entorno de Python):
  python tools/convenio_cuota_grupo_detalle.py --grupo 454785 --propuesta 5=608 6=1702 7=1890 ^
         --capital 5=1106 6=3734 7=4132 --fiador-dni 12345678 --provincia LIMA

  --capital es opcional: si se indica, el script se detiene cuando el capital del SAC no cuadra.
  Sin --fiador-dni toma al primer integrante, como el CRM (modo participante).
  Salida: tools/salidas/Convenio_cuota_grupo_<grupo>.docx
"""
import argparse
import sys
from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
CENT = Decimal("0.01")


def entero(valor):
    try:
        return int(Decimal(str(valor).strip()))
    except Exception:
        return None


def dec(valor):
    try:
        return Decimal(str(valor).strip()) if valor not in (None, "") else Decimal("0")
    except Exception:
        return Decimal("0")


def pares(textos, nombre):
    salida = {}
    for t in textos or []:
        if "=" not in t:
            raise SystemExit(f"{nombre}: usa el formato cuota=monto, por ejemplo 5=608")
        n, m = t.split("=", 1)
        salida[int(n)] = Decimal(m.replace(",", ""))
    return salida


def cuotas_integrante(row):
    """[(numero_cuota, k, capital)] de las CT 1..3 con capital > 0."""
    inicio = entero(row.get("UltCuotaAtrasada"))
    if inicio is None:
        return []
    return [(inicio + k - 1, k, dec(row.get(f"CT{k}"))) for k in (1, 2, 3) if dec(row.get(f"CT{k}")) > 0]


def total_cuota(row, k):
    return dec(row.get(f"CT{k}")) + sum(dec(row.get(f"CT{k}{i}")) for i in range(1, 6))


def repartir(rows, propuestas):
    """Una fila por integrante y cuota acordada. Devuelve (filas, capital_por_cuota)."""
    capital = {n: Decimal("0") for n in propuestas}
    detalle = []
    for row in rows:
        for n, k, cap in cuotas_integrante(row):
            if n in propuestas:
                capital[n] += cap
                detalle.append({"row": row, "n": n, "k": k, "capital": cap})
    faltan = [n for n, c in capital.items() if c <= 0]
    if faltan:
        raise SystemExit(f"Ningún integrante tiene capital en la(s) cuota(s) {faltan} según el SAC.")
    for n, prop in propuestas.items():
        filas_n = [d for d in detalle if d["n"] == n]
        for d in filas_n:
            d["paga"] = (prop * d["capital"] / capital[n]).quantize(CENT, rounding=ROUND_HALF_UP)
        diferencia = prop - sum(d["paga"] for d in filas_n)
        if diferencia:
            max(filas_n, key=lambda d: d["capital"])["paga"] += diferencia
    detalle.sort(key=lambda d: (str(d["row"].get("NomCliente") or ""), d["n"]))
    return detalle, capital


def xml_con_abono_por_operacion(original):
    """La plantilla del CRM arma las dos tablas con context['filas']; aquí la de pago va por cuota y la
    nota de abono por operación (context['filas_abono'])."""
    def construir(context):
        pago = original(context)
        abono = original({**context, "filas": context["filas_abono"]})
        corte_pago = pago.rfind("<w:p>", 0, pago.find("NOTA DE ABONO"))
        corte_abono = abono.rfind("<w:p>", 0, abono.find("NOTA DE ABONO"))
        if corte_pago < 0 or corte_abono < 0:
            corte_pago = pago.rfind("<w:p ", 0, pago.find("NOTA DE ABONO"))
            corte_abono = abono.rfind("<w:p ", 0, abono.find("NOTA DE ABONO"))
        if corte_pago < 0 or corte_abono < 0:
            raise SystemExit("No se encontró la sección NOTA DE ABONO en la plantilla del CRM.")
        return pago[:corte_pago] + abono[corte_abono:]
    return construir


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--grupo", required=True, help="Código de grupo (CodigoGrupo) o crédito grupal (CodCreGrupal)")
    ap.add_argument("--propuesta", nargs="+", required=True, help="cuota=monto que paga el grupo, ej. 5=608 6=1702 7=1890")
    ap.add_argument("--capital", nargs="*", help="cuota=capital esperado (control), ej. 5=1106 6=3734 7=4132")
    ap.add_argument("--fiador-dni", default="", help="DNI del integrante que firma (modo participante)")
    ap.add_argument("--provincia", default="", help="Provincia del fiador")
    ap.add_argument("--distrito", default="", help="Distrito del fiador (si se quiere reemplazar el del SAC)")
    args = ap.parse_args()

    sys.path.insert(0, str(RAIZ))
    from app.services import documentos_service as ds

    propuestas = pares(args.propuesta, "--propuesta")
    esperado = pares(args.capital, "--capital")

    rows = ds.consultar_datos_documento(codigo_grupo=args.grupo, limit=200) or \
        ds.consultar_datos_documento(cod_cre_grupal=args.grupo, limit=200)
    if not rows:
        raise SystemExit(f"No se encontró el grupo {args.grupo} en compartamos_grupal.")

    detalle, capital = repartir(rows, propuestas)

    print(f"\nGrupo {rows[0].get('NomGrupo')} · crédito {ds.clave_operacion(rows[0].get('CodCreGrupal'))} · {len(rows)} operaciones")
    print(f"{'Cuota':>5} {'Capital SAC':>12} {'Esperado':>10} {'Propuesta':>10} {'% propuesta':>11} {'Integrantes':>11}")
    cuadra = True
    for n in sorted(propuestas):
        esp = esperado.get(n)
        # El cuadro de campaña del Radar redondea el capital hacia arriba al sol entero (1,105.40 → 1,106)
        ok = esp is None or abs(esp - capital[n]) <= Decimal("0.05") or esp == capital[n].to_integral_value(rounding=ROUND_CEILING)
        cuadra &= ok
        pct = (1 - propuestas[n] / capital[n]) * 100
        print(f"{n:>5} {capital[n]:>12,.2f} {('' if esp is None else f'{esp:,.2f}'):>10} {propuestas[n]:>10,.2f} "
              f"{pct:>10.2f}% {sum(1 for d in detalle if d['n'] == n):>11}{'' if ok else '  <-- NO CUADRA'}")
    if not cuadra:
        raise SystemExit("\nEl capital del SAC no cuadra con el esperado: no se genera el documento.")

    # Contexto base del CRM (fiador, grupo, deuda, condonación por operación)
    pago_op = {}
    for d in detalle:
        op = ds.limpiar_texto(d["row"].get("Operacion"))
        pago_op[op] = pago_op.get(op, Decimal("0")) + d["paga"]
    fiador = {"modo": "participante", "dni": args.fiador_dni, "provincia": args.provincia}
    if args.distrito:
        fiador["distrito"] = args.distrito
    pagos = [{"operacion": op, "monto": str(m), "activo": True} for op, m in pago_op.items()]
    context = ds.preparar_contexto_cuota_grupal(rows, fiador=fiador, pagos_grupales=pagos, excepcion=True)
    context["credito_grupal"] = ds.clave_operacion(context["credito_grupal"])   # 21806276.0 → 21806276

    nros = {}
    for d in detalle:
        nros.setdefault(ds.limpiar_texto(d["row"].get("Operacion")), []).append(str(d["n"]))
    context["filas_abono"] = [{**f, "nro_cuota": ", ".join(nros.get(f["operacion"], [f["nro_cuota"]]))}
                              for f in context["filas"]]
    context["filas"] = [{
        "cuenta": ds.limpiar_texto(d["row"].get("CtaCliente") or d["row"].get("CodigoGrupo")),
        "operacion": ds.limpiar_texto(d["row"].get("Operacion")),
        "nro_cuota": str(d["n"]),
        "cliente": ds.limpiar_texto(d["row"].get("NomCliente")),
        "cuota": ds.format_money(total_cuota(d["row"], d["k"])),
        "monto_pago": ds.format_money(d["paga"]),
        "monto_condonacion": "",
    } for d in detalle]
    context["total_cuota"] = ds.format_money(sum(total_cuota(d["row"], d["k"]) for d in detalle))
    context["total_pago"] = ds.format_money(sum(d["paga"] for d in detalle))

    ds.document_cuota_grupal_xml = xml_con_abono_por_operacion(ds.document_cuota_grupal_xml)
    salida = RAIZ / "tools" / "salidas" / f"Convenio_cuota_grupo_{ds.safe_filename(args.grupo)}.docx"
    ds.generar_docx_limpio(salida, context, document_kind="compromiso_cuota_grupal")

    print(f"\nFiador: {context['fiador_nombre']} (DNI {context['fiador_dni']})")
    print(f"{'Cuota':>5}  {'Operación':<12} {'Integrante':<42} {'Capital':>10} {'Paga':>10}")
    for d in detalle:
        print(f"{d['n']:>5}  {ds.limpiar_texto(d['row'].get('Operacion')):<12} "
              f"{ds.limpiar_texto(d['row'].get('NomCliente'))[:42]:<42} {d['capital']:>10,.2f} {d['paga']:>10,.2f}")
    for n in sorted(propuestas):
        print(f"Total cuota {n}: {sum(d['paga'] for d in detalle if d['n'] == n):,.2f}")
    print(f"MONTO TOTAL A PAGAR: {context['total_pago']}")
    print(f"\nDocumento: {salida}")


if __name__ == "__main__":
    main()
