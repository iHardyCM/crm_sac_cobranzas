"""Consulta de respuestas SMS Mowa y verificación de gestión posterior en SISCOB.

Mowa identifica la respuesta por message_id. El DNI y la cartera proceden del
mensaje enviado; no se atribuye un cliente por compartir un teléfono.
"""

from __future__ import annotations

import logging
import os
import re
import secrets
import threading
import time as reloj
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor, wait
from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import requests
from sqlalchemy import text

from app.core.db_siscob import engine_siscob


MOWA_BASE = "https://api.contactahabilidad.com/app/sms/v1"
MOWA_SIMPLE = "https://api.contactahabilidad.com/app/sms/simple"
CUENTAS = {
    "INTERBANK_BC": (117,),
    "COMPARVIGENTE": (126, 128, 133),
    "COMPARCARTIGO": (124,),  # Nombre de variable entregado por el proveedor.
    "FINANCIERA_OH": (132,),
    "PROPIA_BIZNES": (137, 148),
    "COMPGRUPAL": (133,),
    "COMPARCAST_CSM": (144,),
    "MIBANCO_VIG": (135,),
    "MI_BANCO_CAS": (112, 143),
}
# La cuenta sigue sincronizándose y conserva su histórico; solo se excluye de
# las vistas y exportaciones operativas de Respuestas SMS.
CUENTAS_OCULTAS_REPORTES = frozenset({"MIBANCO_VIG"})
NOMBRES_CUENTAS = {
    "INTERBANK_BC": "Interbank BC",
    "COMPARVIGENTE": "Compartamos vigente",
    "COMPARCARTIGO": "Compartamos castigo",
    "FINANCIERA_OH": "Financiera OH",
    "PROPIA_BIZNES": "Propia Biznes",
    "COMPGRUPAL": "Compartamos grupal",
    "COMPARCAST_CSM": "Compartamos castigo CSM",
    "MIBANCO_VIG": "MiBanco vigente",
    "MI_BANCO_CAS": "MiBanco castigo",
}
MAX_CAMPANAS = 36
MAX_CAMPANAS_HISTORIAL = 60
PRESUPUESTO_BUSQUEDA_SEGUNDOS = 24
PRESUPUESTO_RESPUESTAS_SEGUNDOS = 24
SNAPSHOT_SEGUNDOS = 15 * 60
SNAPSHOT_MAX_ENTRADAS = 8
_snapshots: OrderedDict[str, dict] = OrderedDict()
_snapshots_lock = threading.Lock()

# Mismo criterio de "cliente activo" que usan compromisos y control horario (confirmado 20/11).
ESTADOS_CLIENTE_ACTIVO = ("A", "N")
LOTE_SISCOB = 400

# Caché compartida (todos los usuarios) de las respuestas por campaña. Solo
# guarda la lista de respuestas de Mowa, no el resultado filtrado por usuario;
# la autorización y SISCOB se evalúan en cada consulta. Campañas recientes se
# refrescan antes porque siguen recibiendo respuestas con más frecuencia.
CACHE_RESPUESTAS_RECIENTE_SEGUNDOS = 2 * 60
CACHE_RESPUESTAS_ANTIGUA_SEGUNDOS = 10 * 60
CACHE_RESPUESTAS_DIAS_RECIENTE = 1
CACHE_RESPUESTAS_MAX_ENTRADAS = 6000
_cache_respuestas: OrderedDict[tuple, tuple[float, Any]] = OrderedDict()
_cache_respuestas_lock = threading.Lock()

logger = logging.getLogger(__name__)


class MowaError(Exception):
    def __init__(self, mensaje: str, status_code: int | None = None):
        super().__init__(mensaje)
        self.status_code = status_code


class SnapshotNoDisponible(Exception):
    pass


def _criterio_snapshot(desde: date, hasta: date, cuenta: str | None,
                       carteras: set[int] | None, usuario_id: str) -> tuple:
    return (desde, hasta, cuenta or "", None if carteras is None else tuple(sorted(carteras)),
            str(usuario_id))


def _limpiar_snapshots(ahora: float) -> None:
    for token in list(_snapshots):
        if ahora - _snapshots[token]["creado"] > SNAPSHOT_SEGUNDOS:
            del _snapshots[token]
    while len(_snapshots) > SNAPSHOT_MAX_ENTRADAS:
        _snapshots.popitem(last=False)


def _guardar_snapshot(criterio: tuple, campanas: list, advertencias: list[str]) -> str:
    token = secrets.token_urlsafe(24)
    with _snapshots_lock:
        _snapshots[token] = {"creado": reloj.monotonic(), "criterio": criterio,
                             "campanas": campanas, "advertencias": advertencias}
        _limpiar_snapshots(reloj.monotonic())
    return token


def _leer_snapshot(token: str, criterio: tuple) -> dict:
    with _snapshots_lock:
        _limpiar_snapshots(reloj.monotonic())
        snapshot = _snapshots.get(token)
        if snapshot is None or snapshot["criterio"] != criterio:
            raise SnapshotNoDisponible("La consulta de campañas venció. Inicia una nueva consulta.")
        _snapshots.move_to_end(token)
        return snapshot


def _get_json(method: str, url: str, key: str, **kwargs):
    try:
        response = requests.request(
            method, url, headers={"Authorization": key, "Accept": "application/json"},
            timeout=(3, 7), **kwargs,
        )
        response.raise_for_status()
        return response.json()
    except requests.HTTPError as exc:
        # Solo se muestra el código HTTP; el cuerpo puede contener datos del proveedor.
        codigo = exc.response.status_code if exc.response is not None else "desconocido"
        raise MowaError(f"Mowa devolvió HTTP {codigo}.", codigo if isinstance(codigo, int) else None) from exc
    except (requests.RequestException, ValueError) as exc:
        # Nunca incluir la URL con parámetros sensibles, el cuerpo ni la llave.
        raise MowaError(f"Consulta Mowa fallida ({type(exc).__name__}).") from exc


def _cuentas_visibles(carteras_permitidas: set[int] | None):
    return [
        (nombre, candidatas, os.getenv(f"MOWA_KEY_{nombre}", "").strip())
        for nombre, candidatas in CUENTAS.items()
        if carteras_permitidas is None or set(candidatas) & carteras_permitidas
    ]


def cuenta_reportable(nombre: str) -> bool:
    return nombre in CUENTAS and nombre not in CUENTAS_OCULTAS_REPORTES


def _cuentas_reportables(carteras_permitidas: set[int] | None):
    return [cuenta for cuenta in _cuentas_visibles(carteras_permitidas)
            if cuenta_reportable(cuenta[0])]


def _campanas(nombre: str, key: str, desde: date, hasta: date, telefono: str | None = None):
    filtros = {"fromDate": desde.isoformat(), "toDate": hasta.isoformat()}
    if telefono:
        filtros["msisdn"] = telefono
    data = _get_json("POST", f"{MOWA_BASE}/campaigns/search", key, json=filtros)
    if not isinstance(data, list):
        raise MowaError("La lista de campañas Mowa tiene un formato inesperado.")
    return [(nombre, key, c) for c in data if isinstance(c, dict) and str(c.get("campaign_id", "")).isdigit()]


def _campanas_con_rescate(nombre: str, key: str, desde: date, hasta: date):
    try:
        return _campanas(nombre, key, desde, hasta)
    except MowaError as exc:
        if not isinstance(exc.__cause__, requests.Timeout) or desde >= hasta:
            raise
        mitad = desde + timedelta(days=(hasta - desde).days // 2)
        # Un rango corto reduce el tamaño de respuesta cuando Mowa agota los
        # siete segundos de lectura del bloque semanal.
        return (_campanas(nombre, key, desde, mitad)
                + _campanas(nombre, key, mitad + timedelta(days=1), hasta))


def _buscar_campanas(cuentas: list, desde: date, hasta: date):
    campanas = []
    advertencias = []
    pool = ThreadPoolExecutor(max_workers=9)
    try:
        trabajos = {pool.submit(_campanas_con_rescate, nombre, key, desde, hasta): nombre
                    for nombre, _, key in cuentas if key}
        terminados, pendientes = wait(trabajos, timeout=PRESUPUESTO_BUSQUEDA_SEGUNDOS)
        for trabajo in terminados:
            try:
                campanas.extend(trabajo.result())
            except MowaError as exc:
                advertencias.append(f"{trabajos[trabajo]}: {exc}")
        for trabajo in pendientes:
            advertencias.append(f"{trabajos[trabajo]}: búsqueda excedió el tiempo de espera.")
            trabajo.cancel()
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
    for nombre, _, key in cuentas:
        if not key:
            advertencias.append(f"{nombre}: llave Mowa no configurada.")
    campanas = list({(nombre, int(c["campaign_id"])): (nombre, key, c)
                     for nombre, key, c in campanas}.values())
    campanas.sort(key=lambda x: (str(x[2].get("creation_date") or ""),
                                  x[0], int(x[2]["campaign_id"])), reverse=True)
    return campanas, advertencias


def limpiar_cache_respuestas() -> None:
    with _cache_respuestas_lock:
        _cache_respuestas.clear()


def _ttl_respuestas(creacion: Any) -> int:
    fecha = _parse_fecha(creacion)
    hoy = datetime.now(ZoneInfo("America/Lima")).date()
    if fecha is None or (hoy - fecha.date()).days <= CACHE_RESPUESTAS_DIAS_RECIENTE:
        return CACHE_RESPUESTAS_RECIENTE_SEGUNDOS
    return CACHE_RESPUESTAS_ANTIGUA_SEGUNDOS


def _respuestas_mowa_cache(nombre: str, key: str, cid: int, creacion: Any = None):
    """Respuestas crudas de una campaña; devuelve (data, vino_de_cache)."""
    clave = (nombre, cid)
    ahora = reloj.monotonic()
    with _cache_respuestas_lock:
        guardado = _cache_respuestas.get(clave)
        if guardado and guardado[0] > ahora:
            _cache_respuestas.move_to_end(clave)
            return guardado[1], True
    data = _get_json("GET", f"{MOWA_BASE}/campaign/{cid}/response", key)
    if isinstance(data, dict) and isinstance(data.get("responses"), list):
        with _cache_respuestas_lock:
            _cache_respuestas[clave] = (reloj.monotonic() + _ttl_respuestas(creacion), data)
            _cache_respuestas.move_to_end(clave)
            while len(_cache_respuestas) > CACHE_RESPUESTAS_MAX_ENTRADAS:
                _cache_respuestas.popitem(last=False)
    return data, False


def _en_cache_respuestas(nombre: str, cid: int) -> bool:
    with _cache_respuestas_lock:
        guardado = _cache_respuestas.get((nombre, cid))
        return bool(guardado and guardado[0] > reloj.monotonic())


def _respuestas_de_campana(nombre: str, key: str, campana: dict):
    cid = int(campana["campaign_id"])
    data, _ = _respuestas_mowa_cache(nombre, key, cid, campana.get("creation_date"))
    if not isinstance(data, dict) or not isinstance(data.get("responses"), list):
        raise MowaError("Las respuestas Mowa tienen un formato inesperado.")
    mensajes = {str(m.get("id")): m for m in campana.get("messages", []) if isinstance(m, dict)}
    salida = []
    for r in data["responses"]:
        if not isinstance(r, dict):
            continue
        envio = mensajes.get(str(r.get("message_id")), {})
        dni = str(envio.get("dni") or "").strip()
        if dni == "0":
            dni = ""
        try:
            cartera_mowa = int(envio.get("cartera_id") or envio.get("cartera") or 0)
        except (TypeError, ValueError):
            cartera_mowa = 0
        recibido_valor = r.get("received_date")
        recibido = _parse_fecha(recibido_valor) if _tiene_hora(recibido_valor) else None
        enviado_valor = envio.get("send_date") or campana.get("send_date")
        enviado_fecha = _parse_fecha(enviado_valor)
        if enviado_fecha is None:
            enviado_valor = envio.get("creation_date") or campana.get("creation_date")
            enviado_fecha = _parse_fecha(enviado_valor)
        if recibido is None:
            # Se muestra la respuesta, pero nunca se marca atendida sin hora.
            fecha_sin_hora = _parse_fecha(recibido_valor)
            fecha_texto = fecha_sin_hora.date().isoformat() if fecha_sin_hora else None
        else:
            fecha_texto = recibido.isoformat(timespec="seconds")
        salida.append({
            "id": str(r.get("id") or ""), "cuenta": nombre,
            "campana_id": cid, "campana": str(campana.get("description") or ""),
            "campana_creacion": str(campana.get("creation_date") or "")[:10] or None,
            "mensaje_id": str(r.get("message_id") or ""),
            "mensaje_enviado": str(envio.get("text") or "") or None,
            "mensaje_enviado_fecha": (enviado_fecha.isoformat(timespec="seconds")
                                      if _tiene_hora(enviado_valor) else enviado_fecha.date().isoformat())
                                      if enviado_fecha else None,
            "mensaje_enviado_estado": str(envio.get("label_status") or "") or None,
            "telefono": str(r.get("msisdn") or envio.get("msisdn") or ""),
            "texto": str(r.get("text") or ""), "recibido": fecha_texto,
            "estado_mowa_codigo": r.get("status"),
            "estado_mowa_etiqueta": str(r.get("label_status") or "") or None,
            "dni": dni, "cartera_mowa": cartera_mowa,
            "cliente": None, "idcliente": None, "idcartera": None,
            "gestion_posterior": None, "gestion_posterior_texto": None,
            "gestion_posterior_id": None, "estado": "SIN_VINCULAR",
            "motivo": "El envío no trae un identificador de cliente verificable." if not dni else None,
        })
    return salida


def _parse_fecha(valor: Any) -> datetime | None:
    if isinstance(valor, datetime):
        return valor.replace(tzinfo=None)
    if isinstance(valor, date):
        return datetime.combine(valor, time.min)
    if not valor:
        return None
    try:
        fecha = datetime.fromisoformat(str(valor).strip().replace("Z", "+00:00"))
        return fecha.astimezone(ZoneInfo("America/Lima")).replace(tzinfo=None) if fecha.tzinfo else fecha
    except ValueError:
        return None


def _tiene_hora(valor: Any) -> bool:
    return isinstance(valor, datetime) or bool(re.search(r"[T ]\d{2}:\d{2}", str(valor or "")))


def _fecha_gestion(fecha: Any, hora: Any) -> datetime | None:
    base = _parse_fecha(fecha)
    if base is None:
        return None
    if isinstance(hora, datetime):
        return datetime.combine(base.date(), hora.time())
    if isinstance(hora, time):
        return datetime.combine(base.date(), hora)
    if hora is not None:
        try:
            hora_valor = time.fromisoformat(str(hora).strip())
            return datetime.combine(base.date(), hora_valor)
        except ValueError:
            pass
    return base if base.time() != time.min else None


def _cliente_activo(cliente: dict) -> bool:
    return str(cliente.get("estado_cliente") or "").strip().upper() in ESTADOS_CLIENTE_ACTIVO


def _enriquecer_clientes(filas: list[dict], carteras_permitidas: set[int] | None):
    # Consultas acotadas por DNI y carteras posibles de cada cuenta. 400 filas por lote
    # dejan los parámetros muy por debajo del límite de 2 100 de SQL Server.
    for inicio in range(0, len(filas), LOTE_SISCOB):
        lote = filas[inicio:inicio + LOTE_SISCOB]
        dnis = sorted({r["dni"] for r in lote if r["dni"]})
        # Consultar todas las carteras candidatas antes de decidir si el DNI
        # identifica a un único cliente. La restricción del usuario se aplica
        # antes de devolver filas, nunca para fabricar una coincidencia única.
        carteras = sorted({c for r in lote for c in CUENTAS[r["cuenta"]]})
        if not dnis or not carteras:
            continue
        params = {f"d{i}": d for i, d in enumerate(dnis)}
        params.update({f"c{i}": c for i, c in enumerate(carteras)})
        dni_sql = ", ".join(f":d{i}" for i in range(len(dnis)))
        cartera_sql = ", ".join(f":c{i}" for i in range(len(carteras)))
        # Se traen también los clientes inactivos para poder distinguir
        # "inactivo en SISCOB" (se oculta) de "no existe en la cartera" (sin
        # vincular). La última gestión solo se busca para clientes activos.
        activo_sql = ", ".join(f"'{e}'" for e in ESTADOS_CLIENTE_ACTIVO)
        sql = text(f"""
            SELECT CL.Dni AS dni, CL.IdCliente AS idcliente,
                   CL.IdCartera AS idcartera, CL.NombreCliente AS cliente,
                   UPPER(LTRIM(RTRIM(ISNULL(CL.Estado, '')))) AS estado_cliente,
                   G.IdGestion AS gestion_id, G.Fecha AS gestion_fecha,
                   G.Hora AS gestion_hora, G.Gestion AS gestion_texto
            FROM SISCOB.dbo.CLIENTE CL WITH(NOLOCK)
            OUTER APPLY (
                SELECT TOP 1 G.IdGestion, G.Fecha, G.Hora, G.Gestion
                FROM SISCOB.dbo.GESTION G WITH(NOLOCK)
                WHERE G.IdCliente = CL.IdCliente AND G.IdCartera = CL.IdCartera
                  AND UPPER(LTRIM(RTRIM(ISNULL(CL.Estado, '')))) IN ({activo_sql})
                ORDER BY G.Fecha DESC, G.Hora DESC, G.IdGestion DESC
            ) G
            WHERE CL.Dni IN ({dni_sql}) AND CL.IdCartera IN ({cartera_sql})
        """)
        with engine_siscob.connect() as conn:
            # Evita que una consulta SISCOB lenta mantenga la vista esperando
            # indefinidamente después de terminar la parte de Mowa.
            driver = getattr(getattr(conn, "connection", None), "driver_connection", None)
            timeout_anterior = getattr(driver, "timeout", None)
            try:
                if driver is not None:
                    driver.timeout = 12
                clientes = [dict(row) for row in conn.execute(sql, params).mappings()]
            finally:
                if driver is not None and timeout_anterior is not None:
                    driver.timeout = timeout_anterior
        por_dni: dict[str, list[dict]] = {}
        for cliente in clientes:
            por_dni.setdefault(str(cliente["dni"]).strip(), []).append(cliente)
        for fila in lote:
            if not fila["dni"]:
                continue
            opciones = [c for c in por_dni.get(fila["dni"], [])
                        if int(c["idcartera"]) in CUENTAS[fila["cuenta"]]
                        if not fila["cartera_mowa"] or int(c["idcartera"]) == fila["cartera_mowa"]]
            activas = [c for c in opciones if _cliente_activo(c)]
            if opciones and not activas:
                # Todos los candidatos están inactivos: sea cual sea el cliente
                # real, ya no se gestiona. Se excluye de la vista.
                fila.update(estado="INACTIVO", motivo="Cliente inactivo en SISCOB.",
                            carteras_inactivas=sorted({int(c["idcartera"]) for c in opciones}))
                continue
            # Un mismo DNI puede tener un registro inactivo anterior y uno
            # activo en la MISMA cartera; ahí el activo es el vigente. Si los
            # candidatos están en carteras distintas no se elige por estado.
            if (len(activas) == 1 and len(opciones) > 1
                    and {int(c["idcartera"]) for c in opciones} == {int(activas[0]["idcartera"])}):
                opciones = activas
            if len(opciones) != 1:
                fila["motivo"] = ("Cliente no encontrado en la cartera de esta cuenta."
                                  if not opciones else "Identificador asociado a varios clientes; requiere revisión.")
                continue
            cliente = opciones[0]
            fila.update(cliente=str(cliente["cliente"] or ""), idcliente=cliente["idcliente"],
                        idcartera=int(cliente["idcartera"]))
            fila["vinculo"] = ("Cartera Mowa y DNI" if fila["cartera_mowa"]
                               else "Cuenta Mowa y DNI únicos en SISCOB")
            recibida = _parse_fecha(fila["recibido"]) if _tiene_hora(fila["recibido"]) else None
            gestion = _fecha_gestion(cliente["gestion_fecha"], cliente["gestion_hora"])
            fecha_gestion = _parse_fecha(cliente["gestion_fecha"])
            if recibida is None:
                fila.update(estado="SIN_VERIFICAR", motivo="Mowa no entregó una hora de recepción válida.")
            elif gestion is None and fecha_gestion and fecha_gestion.date() > recibida.date():
                fila.update(estado="ATENDIDA", gestion_posterior=fecha_gestion.date().isoformat(),
                            gestion_posterior_texto=cliente.get("gestion_texto"),
                            gestion_posterior_id=cliente.get("gestion_id"), motivo=None)
            elif gestion is None and fecha_gestion and fecha_gestion.date() < recibida.date():
                fila.update(estado="PENDIENTE", motivo=None)
            elif gestion is None and fecha_gestion:
                fila.update(estado="SIN_VERIFICAR", motivo="La última gestión no tiene hora verificable.")
            elif gestion is not None and gestion > recibida:
                fila.update(estado="ATENDIDA", gestion_posterior=gestion.isoformat(timespec="seconds"),
                            gestion_posterior_texto=cliente.get("gestion_texto"),
                            gestion_posterior_id=cliente.get("gestion_id"), motivo=None)
            else:
                fila.update(estado="PENDIENTE", motivo=None)


def consultar_respuestas(desde: date, hasta: date, carteras_permitidas: set[int] | None,
                        cuenta: str | None = None, offset: int = 0,
                        snapshot_token: str | None = None, usuario_id: str = ""):
    cuentas = _cuentas_reportables(carteras_permitidas)
    if cuenta:
        cuentas = [item for item in cuentas if item[0] == cuenta]
    criterio = _criterio_snapshot(desde, hasta, cuenta, carteras_permitidas, usuario_id)
    ms_busqueda = 0
    if snapshot_token:
        snapshot = _leer_snapshot(snapshot_token, criterio)
    else:
        if offset:
            raise SnapshotNoDisponible("La siguiente página requiere la consulta inicial.")
        t_busqueda = reloj.perf_counter()
        campanas, busqueda_advertencias = _buscar_campanas(cuentas, desde, hasta)
        ms_busqueda = round((reloj.perf_counter() - t_busqueda) * 1000)
        snapshot_token = _guardar_snapshot(criterio, campanas, busqueda_advertencias)
        snapshot = {"campanas": campanas, "advertencias": busqueda_advertencias}
    total_campanas = len(snapshot["campanas"])
    campanas = snapshot["campanas"][offset:offset + MAX_CAMPANAS]
    siguiente_offset = offset + len(campanas) if offset + len(campanas) < total_campanas else None
    advertencias = list(snapshot["advertencias"]) if offset == 0 else []
    filas = []
    t_inicio = reloj.perf_counter()
    en_cache = sum(1 for nombre, _, c in campanas if _en_cache_respuestas(nombre, int(c["campaign_id"])))
    pool = ThreadPoolExecutor(max_workers=12)
    try:
        trabajos = {pool.submit(_respuestas_de_campana, *item): (item[0], item[2]["campaign_id"])
                    for item in campanas}
        terminados, pendientes = wait(trabajos, timeout=PRESUPUESTO_RESPUESTAS_SEGUNDOS)
        for trabajo in terminados:
            try:
                filas.extend(trabajo.result())
            except MowaError as exc:
                cuenta_error, cid = trabajos[trabajo]
                advertencias.append(f"{cuenta_error}, campaña {cid}: {exc}")
        if pendientes:
            advertencias.append(f"{len(pendientes)} campañas no respondieron a tiempo. Consulta un rango menor o una cuenta.")
            for trabajo in pendientes:
                trabajo.cancel()
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
    t_mowa = reloj.perf_counter()
    campanas_con_respuesta = len({(r["cuenta"], r["campana_id"]) for r in filas})
    # Cada respuesta es única dentro de una cuenta. No colapsar respuestas
    # diferentes del mismo teléfono o cliente.
    filas = list({(r["cuenta"], r["campana_id"], r["id"] or
                   (r["mensaje_id"], r["recibido"], r["texto"])): r for r in filas}.values())
    filas, excluidas_inactivas, total_inactivas = clasificar_respuestas(
        filas, carteras_permitidas, advertencias)
    t_siscob = reloj.perf_counter()
    diagnostico = {
        "ms_busqueda_campanas": ms_busqueda,
        "campanas_pagina": len(campanas), "campanas_en_cache": en_cache,
        "campanas_con_respuesta": campanas_con_respuesta,
        "ms_mowa": round((t_mowa - t_inicio) * 1000),
        "ms_siscob": round((t_siscob - t_mowa) * 1000),
    }
    logger.info("Respuestas SMS usuario=%s rango=%s..%s cuenta=%s offset=%s/%s %s respuestas=%s inactivas=%s",
                usuario_id, desde, hasta, cuenta or "todas", offset, total_campanas,
                diagnostico, len(filas), total_inactivas)
    return {"data": filas, "advertencias": advertencias, "excluidas_inactivas": excluidas_inactivas,
            "diagnostico": diagnostico,
            "completo": not snapshot["advertencias"] and not advertencias and siguiente_offset is None,
            "total_campanas": total_campanas, "siguiente_offset": siguiente_offset,
            "snapshot_token": snapshot_token,
            "desde": desde.isoformat(), "hasta": hasta.isoformat(),
            "alcance_carteras": None if carteras_permitidas is None else sorted(carteras_permitidas)}


def clasificar_respuestas(filas: list[dict], carteras_permitidas: set[int] | None,
                          advertencias: list[str]) -> tuple[list[dict], int, int]:
    """Cruza con SISCOB (vínculo, cliente activo, gestión posterior) y filtra por permiso.

    Devuelve (filas visibles ordenadas de la más reciente a la más antigua,
    respuestas ocultas por cliente inactivo en carteras visibles, total de inactivas).
    """
    if filas:
        try:
            _enriquecer_clientes(filas, carteras_permitidas)
        except Exception:
            logger.exception("Respuestas SMS: falló la verificación en SISCOB")
            advertencias.append("No se pudo verificar clientes y gestiones en SISCOB.")
            for fila in filas:
                if fila["dni"]:
                    fila.update(estado="SIN_VERIFICAR", motivo="Sin consulta SISCOB disponible.")
    # Clientes inactivos en SISCOB: no se muestran. Solo se cuentan los de
    # carteras visibles para el usuario.
    inactivas = [r for r in filas if r.get("estado") == "INACTIVO"]
    excluidas = sum(
        1 for r in inactivas
        if carteras_permitidas is None or set(r.get("carteras_inactivas") or ()) & carteras_permitidas)
    filas = [r for r in filas if r.get("estado") != "INACTIVO"]
    if carteras_permitidas is not None:
        # Una cuenta Mowa puede contener varias carteras. Sin vínculo confirmado
        # no hay forma de demostrar que la respuesta pertenece al usuario.
        filas = [r for r in filas if r["idcartera"] in carteras_permitidas]
    filas.sort(key=lambda r: r["recibido"] or "", reverse=True)
    return filas, excluidas, len(inactivas)


def _verificar_ancla(cuenta: str, campana_id: int, respuesta_id: int, mensaje_id: int,
                    fecha_campana: date,
                    carteras_permitidas: set[int] | None):
    """Valida en las fuentes la respuesta elegida, sin confiar en DNI o celular del navegador."""
    if cuenta not in CUENTAS or (carteras_permitidas is not None
                                 and not set(CUENTAS[cuenta]) & carteras_permitidas):
        raise ValueError("Cuenta SMS no autorizada.")
    key = os.getenv(f"MOWA_KEY_{cuenta}", "").strip()
    if not key:
        raise MowaError("La llave de esta cuenta no está configurada.")
    # Reutiliza la búsqueda de campañas que alimenta la pantalla. El endpoint
    # legacy getMessage no está validado para todas las cuentas del proveedor.
    try:
        candidatas = _campanas(cuenta, key, fecha_campana, fecha_campana)
    except MowaError as exc:
        raise MowaError(f"Verificación de la campaña original: {exc}") from exc
    campana = next((c for _, _, c in candidatas if int(c["campaign_id"]) == campana_id), None)
    if campana is None:
        raise MowaError("La campaña original no apareció en la fecha consultada.")
    origen = next((m for m in campana.get("messages", []) if isinstance(m, dict)
                   and str(m.get("id") or "") == str(mensaje_id)), None)
    if origen is None:
        raise MowaError("El mensaje original no apareció en su campaña.")
    filas = _respuestas_de_campana(cuenta, key, campana)
    fila = next((r for r in filas if r["id"] == str(respuesta_id)
                 and r["mensaje_id"] == str(mensaje_id)), None)
    if fila is None:
        raise ValueError("La respuesta no corresponde al mensaje seleccionado.")
    numero = str(origen.get("msisdn") or "").strip()
    if fila["telefono"] != numero or len(numero) != 9 or not numero.startswith("9") or not numero.isdigit():
        raise ValueError("No se pudo verificar un celular peruano válido para esta respuesta.")
    _enriquecer_clientes([fila], carteras_permitidas)
    if fila["estado"] == "INACTIVO":
        raise ValueError("El cliente está inactivo en SISCOB; ya no se le puede responder desde aquí.")
    if not fila["idcliente"] or (carteras_permitidas is not None
                                  and fila["idcartera"] not in carteras_permitidas):
        raise ValueError("No se pudo vincular la respuesta a un cliente de tu cartera.")
    return key, fila, numero


def enviar_respuesta(cuenta: str, campana_id: int, respuesta_id: int, mensaje_id: int,
                    fecha_campana: date, texto_sms: str,
                    carteras_permitidas: set[int] | None, autorizar_cliente=None) -> dict:
    """Revalida la respuesta y su destinatario en Mowa y SISCOB antes del envío."""
    texto_sms = texto_sms.strip()
    if not texto_sms or len(texto_sms) > 160 or any(ord(c) < 32 for c in texto_sms):
        raise ValueError("Escribe un SMS de 1 a 160 caracteres, en una sola línea.")
    key, fila, numero = _verificar_ancla(
        cuenta, campana_id, respuesta_id, mensaje_id, fecha_campana, carteras_permitidas)
    if autorizar_cliente is not None:
        autorizar_cliente(fila["idcartera"], fila["idcliente"])
    try:
        enviado = _get_json("POST", MOWA_SIMPLE, key,
                            json={"msisdn": numero, "text": texto_sms, "type": 1,
                                  "dni": fila["dni"], "cartera": fila["idcartera"]})
    except MowaError as exc:
        raise MowaError("Mowa no confirmó el envío. Verifica el historial del proveedor antes de reintentar.") from exc
    if not isinstance(enviado, dict) or not enviado.get("id") or not enviado.get("campaign_id"):
        raise MowaError("Mowa no confirmó el envío. Verifica el historial del proveedor antes de reintentar.")
    fecha_envio = _parse_fecha(enviado.get("creation_date"))
    return {"mensaje_id": str(enviado["id"]), "campana_id": str(enviado["campaign_id"]),
            "fecha": fecha_envio.isoformat(timespec="seconds") if fecha_envio else None,
            "estado_codigo": enviado.get("status"), "estado_etiqueta": enviado.get("label_status"),
            "texto": texto_sms, "telefono": numero, "idcliente": fila["idcliente"],
            "idcartera": fila["idcartera"], "cuenta": cuenta}


def _fecha_evento_mowa(valor: Any) -> str | None:
    fecha = _parse_fecha(valor)
    if not fecha:
        return None
    return fecha.isoformat(timespec="seconds") if _tiene_hora(valor) else fecha.date().isoformat()


def consultar_historial(cuenta: str, campana_id: int, respuesta_id: int, mensaje_id: int,
                       fecha_campana: date, desde: date, hasta: date,
                       carteras_permitidas: set[int] | None, autorizar_cliente=None) -> dict:
    """Historial de la cuenta y el celular verificados, limitado al rango de campañas."""
    key, fila, numero = _verificar_ancla(
        cuenta, campana_id, respuesta_id, mensaje_id, fecha_campana, carteras_permitidas)
    if autorizar_cliente is not None:
        autorizar_cliente(fila["idcartera"], fila["idcliente"])
    try:
        campanas = _campanas(cuenta, key, desde, hasta, telefono=numero)
    except MowaError as exc:
        if exc.status_code not in (400, 404, 422):
            raise MowaError(f"Búsqueda del historial por celular: {exc}", exc.status_code) from exc
        # Algunas cuentas rechazan filtros combinados. Reutilizar la búsqueda
        # por semanas que ya usa la vista, y filtrar DNI/cartera/celular aquí.
        campanas = []
        bloque_desde = desde
        try:
            while bloque_desde <= hasta:
                bloque_hasta = min(bloque_desde + timedelta(days=6), hasta)
                campanas.extend(_campanas(cuenta, key, bloque_desde, bloque_hasta))
                bloque_desde = bloque_hasta + timedelta(days=1)
        except MowaError as fallback_exc:
            raise MowaError(f"Búsqueda del historial por fechas: {fallback_exc}",
                            fallback_exc.status_code) from fallback_exc
    campanas.sort(key=lambda item: (str(item[2].get("creation_date") or ""),
                                    int(item[2]["campaign_id"])), reverse=True)
    advertencias = []
    if len(campanas) > MAX_CAMPANAS_HISTORIAL:
        advertencias.append("Hay más campañas de este celular que las mostradas. Acota el rango.")
        campanas = campanas[:MAX_CAMPANAS_HISTORIAL]
    eventos = []
    consultas = []
    for _, _, campana in campanas:
        mensajes = {}
        for m in campana.get("messages", []):
            if not isinstance(m, dict) or str(m.get("dni") or "").strip() != fila["dni"]:
                continue
            if str(m.get("msisdn") or "").strip() != numero:
                continue
            try:
                cartera_mensaje = int(m.get("cartera_id") or m.get("cartera") or 0)
            except (TypeError, ValueError):
                continue
            if cartera_mensaje != fila["idcartera"] and not (
                cartera_mensaje == 0 and len(CUENTAS[cuenta]) == 1):
                continue
            mid = str(m.get("id") or "")
            if not mid:
                continue
            mensajes[mid] = m
            eventos.append({"lado": "nosotros", "id": mid, "campana_id": campana["campaign_id"],
                            "texto": str(m.get("text") or ""), "fecha": _fecha_evento_mowa(
                                m.get("send_date") or m.get("creation_date")
                                or campana.get("send_date") or campana.get("creation_date")),
                            "estado": m.get("label_status"), "telefono": numero, "cuenta": cuenta})
        if mensajes:
            consultas.append((int(campana["campaign_id"]), campana.get("creation_date"), mensajes))
    pool = ThreadPoolExecutor(max_workers=8)
    try:
        trabajos = {pool.submit(_respuestas_mowa_cache, cuenta, key, cid, creacion):
                    (cid, mensajes) for cid, creacion, mensajes in consultas}
        terminados, pendientes = wait(trabajos, timeout=PRESUPUESTO_RESPUESTAS_SEGUNDOS)
        for trabajo in terminados:
            cid, mensajes = trabajos[trabajo]
            try:
                data, _ = trabajo.result()
                if not isinstance(data, dict) or not isinstance(data.get("responses"), list):
                    raise MowaError("Formato de respuestas inesperado.")
                for r in data["responses"]:
                    if not isinstance(r, dict) or str(r.get("message_id") or "") not in mensajes:
                        continue
                    if str(r.get("msisdn") or "").strip() != numero:
                        continue
                    eventos.append({"lado": "cliente", "id": str(r.get("id") or ""),
                                    "campana_id": cid, "texto": str(r.get("text") or ""),
                                    "fecha": _fecha_evento_mowa(r.get("received_date")),
                                    "estado": r.get("label_status"), "telefono": numero,
                                    "cuenta": cuenta})
            except MowaError:
                advertencias.append(f"No se pudo leer la campaña {cid}.")
        if pendientes:
            advertencias.append(f"{len(pendientes)} campañas excedieron el tiempo de espera.")
            for trabajo in pendientes:
                trabajo.cancel()
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
    eventos = list({(e["cuenta"], e["campana_id"], e["lado"], e["id"]): e for e in eventos}.values())
    return {"eventos": eventos, "advertencias": advertencias, "completo": not advertencias,
            "idcliente": fila["idcliente"], "idcartera": fila["idcartera"]}
