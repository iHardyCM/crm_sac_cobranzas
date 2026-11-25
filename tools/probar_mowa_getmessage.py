"""
Prueba (SOLO LECTURA) del endpoint getMessage de Mowa en las 9 cuentas.

Para qué: el diseño de Respuestas SMS (claude/diseno_respuestas_sms.md) guarda solo las
respuestas y completa los datos del SMS de origen (DNI, cartera, texto, fecha de envío)
con getMessage, en vez de guardar todos los mensajes enviados. Antes de construir las
tablas hay que confirmar que getMessage funciona con cada llave y que devuelve los mismos
datos que la búsqueda de campañas que usa hoy la vista.

También mide la latencia real de Mowa, que sirve para validar la estimación de llamadas
diarias de la carga programada.

Qué hace, por cada cuenta con llave en el .env:
  1. Busca campañas día por día hacia atrás, desde la fecha indicada (por defecto ayer),
     hasta encontrar respuestas.
  2. Consulta /campaign/{id}/response y mide cuánto tarda.
  3. Para hasta N respuestas, llama getMessage/{message_id}/{campaign_id} y compara DNI,
     cartera, celular y texto contra el mensaje que trajo la búsqueda.

No envía SMS, no escribe en ninguna base y no imprime DNI, celulares, textos ni llaves:
solo coincidencias (sí/no), conteos y tiempos.

USO (desde la carpeta del CRM)
    python tools/probar_mowa_getmessage.py
    python tools/probar_mowa_getmessage.py 2026-11-19 --dias 7 --muestras 5

Deja el resultado en tools/salidas/mowa_getmessage_<fecha>_<hhmm>.txt
"""
from __future__ import annotations

import argparse
import statistics
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from time import perf_counter
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

from app.services import respuestas_mowa_service as mowa  # noqa: E402

MOWA_GETMESSAGE = "https://api.contactahabilidad.com/app/sms/getMessage"
MAX_CAMPANAS_POR_CUENTA = 40  # Tope de llamadas /response por cuenta para no cargar a Mowa.
RAIZ = Path(__file__).resolve().parents[1]


def _ms(inicio: float) -> int:
    return round((perf_counter() - inicio) * 1000)


def _texto(valor) -> str:
    return str(valor if valor is not None else "").strip()


def _cartera(mensaje: dict) -> str:
    return _texto(mensaje.get("cartera_id", mensaje.get("cartera")))


def _resumen_ms(valores: list[int]) -> str:
    if not valores:
        return "sin datos"
    ordenados = sorted(valores)
    p90 = ordenados[min(len(ordenados) - 1, int(len(ordenados) * 0.9))]
    return (f"n={len(valores)} prom={round(statistics.mean(valores))} ms "
            f"p90={p90} ms máx={ordenados[-1]} ms")


def probar_cuenta(cuenta: str, key: str, desde: date, dias: int, muestras: int) -> dict:
    r = {"cuenta": cuenta, "busqueda_ms": [], "response_ms": [], "getmessage_ms": [],
         "campanas_revisadas": 0, "campanas_con_respuesta": 0, "muestras": [],
         "errores": [], "dia_usado": None}
    for atras in range(dias):
        dia = desde - timedelta(days=atras)
        inicio = perf_counter()
        try:
            campanas = mowa._campanas_con_rescate(cuenta, key, dia, dia)
        except mowa.MowaError as exc:
            r["errores"].append(f"búsqueda {dia}: {exc}")
            continue
        r["busqueda_ms"].append(_ms(inicio))
        for _, _, campana in campanas:
            if r["campanas_revisadas"] >= MAX_CAMPANAS_POR_CUENTA or len(r["muestras"]) >= muestras:
                break
            cid = int(campana["campaign_id"])
            r["campanas_revisadas"] += 1
            inicio = perf_counter()
            try:
                data = mowa._get_json("GET", f"{mowa.MOWA_BASE}/campaign/{cid}/response", key)
            except mowa.MowaError as exc:
                r["errores"].append(f"response campaña {cid}: {exc}")
                continue
            r["response_ms"].append(_ms(inicio))
            respuestas = data.get("responses") if isinstance(data, dict) else None
            if not respuestas:
                continue
            r["campanas_con_respuesta"] += 1
            r["dia_usado"] = r["dia_usado"] or dia.isoformat()
            mensajes = {_texto(m.get("id")): m for m in campana.get("messages", []) if isinstance(m, dict)}
            for resp in respuestas:
                if len(r["muestras"]) >= muestras:
                    break
                if not isinstance(resp, dict) or not _texto(resp.get("message_id")):
                    continue
                r["muestras"].append(_comparar(key, cid, resp, mensajes.get(_texto(resp.get("message_id"))), r))
        if len(r["muestras"]) >= muestras or r["campanas_revisadas"] >= MAX_CAMPANAS_POR_CUENTA:
            break
    return r


def _comparar(key: str, cid: int, resp: dict, origen: dict | None, r: dict) -> dict:
    mid = _texto(resp.get("message_id"))
    muestra = {"campana": cid, "message_id": mid, "ok_http": False,
               "en_busqueda": origen is not None, "campos": [], "coincide": {}}
    inicio = perf_counter()
    try:
        data = mowa._get_json("GET", f"{MOWA_GETMESSAGE}/{mid}/{cid}", key)
    except mowa.MowaError as exc:
        muestra["error"] = str(exc)
        return muestra
    r["getmessage_ms"].append(_ms(inicio))
    if isinstance(data, list):
        data = data[0] if data and isinstance(data[0], dict) else None
    if not isinstance(data, dict):
        muestra["error"] = "Formato inesperado (no es un objeto)."
        return muestra
    muestra["ok_http"] = True
    muestra["campos"] = sorted(data.keys())
    muestra["coincide"]["id"] = _texto(data.get("id")) == mid
    muestra["coincide"]["celular_vs_respuesta"] = _texto(data.get("msisdn")) == _texto(resp.get("msisdn"))
    muestra["trae_dni"] = bool(_texto(data.get("dni"))) and _texto(data.get("dni")) != "0"
    muestra["trae_cartera"] = bool(_cartera(data)) and _cartera(data) != "0"
    muestra["trae_fecha_envio"] = bool(_texto(data.get("send_date")))
    if origen is not None:
        muestra["coincide"]["dni"] = _texto(data.get("dni")) == _texto(origen.get("dni"))
        muestra["coincide"]["cartera"] = _cartera(data) == _cartera(origen)
        muestra["coincide"]["celular"] = _texto(data.get("msisdn")) == _texto(origen.get("msisdn"))
        muestra["coincide"]["texto"] = _texto(data.get("text")) == _texto(origen.get("text"))
    return muestra


def veredicto(r: dict) -> str:
    if not r["muestras"]:
        return "SIN DATOS" if not r["errores"] else "FALLA"
    if not all(m["ok_http"] for m in r["muestras"]):
        return "FALLA" if not any(m["ok_http"] for m in r["muestras"]) else "PARCIAL"
    comparables = [m for m in r["muestras"] if m["en_busqueda"]]
    if comparables and not all(m["coincide"].get("dni") and m["coincide"].get("cartera") for m in comparables):
        return "NO COINCIDE"
    return "OK"


def informe(resultados: list[dict], sin_llave: list[str], desde: date, dias: int, muestras: int) -> list[str]:
    ahora = datetime.now(ZoneInfo("America/Lima")).strftime("%Y-%m-%d %H:%M")
    lineas = [f"Prueba getMessage Mowa · {ahora} · desde {desde} hacia atrás {dias} días · "
              f"hasta {muestras} muestras por cuenta", ""]
    lineas.append("RESUMEN POR CUENTA")
    for r in resultados:
        lineas.append(f"- {r['cuenta']:<16} {veredicto(r):<12} muestras={len(r['muestras'])} "
                      f"campañas revisadas={r['campanas_revisadas']} con respuesta={r['campanas_con_respuesta']} "
                      f"día={r['dia_usado'] or '—'}")
    for cuenta in sin_llave:
        lineas.append(f"- {cuenta:<16} SIN LLAVE    (MOWA_KEY_{cuenta} no está en el .env)")
    lineas += ["", "LECTURA DEL VEREDICTO",
               "  OK          getMessage respondió y DNI/cartera coinciden con la búsqueda de campañas.",
               "  NO COINCIDE respondió, pero DNI o cartera no coinciden: no se puede usar como fuente.",
               "  PARCIAL     algunas llamadas fallaron.  FALLA: ninguna respondió.",
               "  SIN DATOS   no se encontraron respuestas en los días revisados (probar con --dias mayor).",
               "", "LATENCIA (sirve para validar la estimación de la carga programada)"]
    for nombre, campo in (("búsqueda de campañas (1 día)", "busqueda_ms"),
                          ("/campaign/{id}/response", "response_ms"),
                          ("getMessage", "getmessage_ms")):
        valores = [v for r in resultados for v in r[campo]]
        lineas.append(f"- {nombre:<30} {_resumen_ms(valores)}")
    lineas += ["", "DETALLE (sin datos personales)"]
    for r in resultados:
        lineas.append(f"\n## {r['cuenta']}")
        campos = sorted({c for m in r["muestras"] for c in m["campos"]})
        if campos:
            lineas.append(f"   campos que devuelve getMessage: {', '.join(campos)}")
        for m in r["muestras"]:
            if not m["ok_http"]:
                lineas.append(f"   campaña {m['campana']} mensaje {m['message_id']}: ERROR {m.get('error')}")
                continue
            coincide = " ".join(f"{k}={'sí' if v else 'NO'}" for k, v in m["coincide"].items())
            lineas.append(f"   campaña {m['campana']} mensaje {m['message_id']}: "
                          f"trae dni={'sí' if m['trae_dni'] else 'NO'} cartera={'sí' if m['trae_cartera'] else 'NO'} "
                          f"fecha_envío={'sí' if m['trae_fecha_envio'] else 'NO'} | "
                          f"en búsqueda={'sí' if m['en_busqueda'] else 'NO'} | {coincide}")
        for e in r["errores"][:10]:
            lineas.append(f"   aviso: {e}")
        if len(r["errores"]) > 10:
            lineas.append(f"   … {len(r['errores']) - 10} avisos más")
    return lineas


def main() -> None:
    ayer = datetime.now(ZoneInfo("America/Lima")).date() - timedelta(days=1)
    parser = argparse.ArgumentParser(description="Prueba de solo lectura de getMessage en Mowa.")
    parser.add_argument("fecha", nargs="?", default=ayer.isoformat(), help="Día inicial (AAAA-MM-DD). Por defecto ayer.")
    parser.add_argument("--dias", type=int, default=7, help="Días hacia atrás a revisar si no hay respuestas (máx. 31).")
    parser.add_argument("--muestras", type=int, default=5, help="Respuestas a verificar por cuenta (máx. 20).")
    args = parser.parse_args()
    desde = date.fromisoformat(args.fecha)
    dias = max(1, min(args.dias, 31))
    muestras = max(1, min(args.muestras, 20))

    resultados, sin_llave = [], []
    for cuenta, _carteras, key in mowa._cuentas_visibles(None):
        if not key:
            sin_llave.append(cuenta)
            continue
        print(f"Probando {cuenta}…", flush=True)
        resultados.append(probar_cuenta(cuenta, key, desde, dias, muestras))

    lineas = informe(resultados, sin_llave, desde, dias, muestras)
    salidas = RAIZ / "tools" / "salidas"
    salidas.mkdir(parents=True, exist_ok=True)
    archivo = salidas / f"mowa_getmessage_{desde}_{datetime.now().strftime('%H%M')}.txt"
    archivo.write_text("\n".join(lineas), encoding="utf-8")
    print("\n".join(lineas[:16]))
    print(f"\nListo: {archivo}")


if __name__ == "__main__":
    main()
