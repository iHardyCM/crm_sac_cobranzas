"""
Compara (SOLO LECTURA) cuántas campañas devuelve Mowa al buscar por semana vs. día por día.

Para qué: la carga inicial (backfill) descubrió unas 140 campañas por semana buscando día
por día, pero la vista en vivo, que busca por semana, llegó a más de 360 campañas en la
semana del 08 al 14/11. Si la búsqueda por día pierde campañas, la carga programada también
perdería respuestas. Este script lo mide.

Por cada cuenta compara tres formas de buscar el mismo rango:
  A. semana completa (como la vista actual)
  B. día por día con fromDate = toDate (como la carga)
  C. día por día con toDate = día siguiente (por si toDate fuera exclusivo)
Y cuántas campañas de A ya están en CobAuto.dbo.CRM_SMS_CAMPANA.

Solo imprime IDs de campaña, fechas y conteos (sin DNI, celulares ni textos).

USO (desde la carpeta del CRM)
    python tools/comparar_busqueda_mowa.py                      # 2026-11-08 a 2026-11-14
    python tools/comparar_busqueda_mowa.py 2026-11-08 2026-11-14

Deja el resultado en tools/salidas/comparar_busqueda_mowa_<desde>_<hasta>.txt
"""
from __future__ import annotations

import sys
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

from sqlalchemy import text  # noqa: E402

from app.core.db_siscob import engine_siscob  # noqa: E402
from app.services import respuestas_mowa_service as mowa  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]


def _ids(resultado) -> dict[int, dict]:
    return {int(c["campaign_id"]): c for _, _, c in resultado}


def _buscar(cuenta, key, desde, hasta, avisos, etiqueta):
    try:
        return _ids(mowa._campanas_con_rescate(cuenta, key, desde, hasta))
    except mowa.MowaError as exc:
        avisos.append(f"{cuenta} {etiqueta} {desde}..{hasta}: {exc}")
        return {}


def _fecha(c, campo):
    f = mowa._parse_fecha(c.get(campo))
    return f.date().isoformat() if f else "sin fecha"


def main() -> None:
    desde = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else date(2026, 11, 8)
    hasta = date.fromisoformat(sys.argv[2]) if len(sys.argv) > 2 else date(2026, 11, 14)
    dias = [desde + timedelta(days=i) for i in range((hasta - desde).days + 1)]
    lineas = [f"Comparación de búsqueda de campañas Mowa · {desde} a {hasta}", "",
              "cuenta            A_semana  B_dia(=)  C_dia(+1)  A-B  B-A  A_en_tabla"]
    detalle, avisos = [], []
    totales = Counter()
    for cuenta, _carteras, key in mowa._cuentas_visibles(None):
        if not key:
            continue
        print(f"Comparando {cuenta}…", flush=True)
        a = _buscar(cuenta, key, desde, hasta, avisos, "semana")
        b, c = {}, {}
        for d in dias:
            b.update(_buscar(cuenta, key, d, d, avisos, "día="))
            c.update(_buscar(cuenta, key, d, d + timedelta(days=1), avisos, "día+1"))
        en_tabla = set()
        if a:
            with engine_siscob.connect() as conn:
                ids = list(a)
                for i in range(0, len(ids), 500):
                    lote = ids[i:i + 500]
                    params = {"cuenta": cuenta, **{f"i{n}": v for n, v in enumerate(lote)}}
                    marcas = ", ".join(f":i{n}" for n in range(len(lote)))
                    en_tabla.update(r[0] for r in conn.execute(text(
                        f"SELECT CampaignId FROM CobAuto.dbo.CRM_SMS_CAMPANA WITH (NOLOCK) "
                        f"WHERE Cuenta = :cuenta AND CampaignId IN ({marcas})"), params))
        solo_a = sorted(set(a) - set(b))
        solo_b = sorted(set(b) - set(a))
        lineas.append(f"{cuenta:<16} {len(a):>9} {len(b):>9} {len(c):>10} {len(solo_a):>4} "
                      f"{len(solo_b):>4} {len(en_tabla):>11}")
        totales.update({"A": len(a), "B": len(b), "C": len(c), "A-B": len(solo_a),
                        "B-A": len(solo_b), "tabla": len(en_tabla)})
        if solo_a:
            creacion = Counter(_fecha(a[i], "creation_date") for i in solo_a)
            envio = Counter(_fecha(a[i], "send_date") for i in solo_a)
            con_mensajes = sum(1 for i in solo_a if a[i].get("messages"))
            detalle += [f"\n## {cuenta}: {len(solo_a)} campañas solo en la búsqueda semanal",
                        f"   fecha de creación: {dict(sorted(creacion.items()))}",
                        f"   fecha de envío:    {dict(sorted(envio.items()))}",
                        f"   con mensajes en la respuesta: {con_mensajes}",
                        f"   ejemplos de ID: {solo_a[:10]}"]
    lineas.append(f"{'TOTAL':<16} {totales['A']:>9} {totales['B']:>9} {totales['C']:>10} "
                  f"{totales['A-B']:>4} {totales['B-A']:>4} {totales['tabla']:>11}")
    lineas += ["", "LECTURA",
               "  A-B > 0: la búsqueda por día pierde campañas que la semanal sí trae.",
               "  C > B:   toDate se comporta como exclusivo (hay que buscar con el día siguiente).",
               "  A_en_tabla < A: campañas de la semana que la carga no tiene registradas."]
    lineas += detalle
    if avisos:
        lineas += ["", "AVISOS"] + [f"  {a}" for a in avisos]
    salidas = RAIZ / "tools" / "salidas"
    salidas.mkdir(parents=True, exist_ok=True)
    archivo = salidas / f"comparar_busqueda_mowa_{desde}_{hasta}.txt"
    archivo.write_text("\n".join(lineas), encoding="utf-8")
    print("\n".join(lineas[:14]))
    print(f"\nListo: {archivo}")


if __name__ == "__main__":
    main()
