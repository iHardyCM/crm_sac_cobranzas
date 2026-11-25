"""Carga programada de respuestas SMS de Mowa hacia CobAuto.

Diseño: claude/diseno_respuestas_sms.md (proyecto crm_cobranzas).

Qué hace cada corrida:
  1. Descubre campañas nuevas (búsqueda por día) y las registra en CRM_SMS_CAMPANA.
  2. Revisa las campañas cuya ProximaRevision ya venció (GET /campaign/{id}/response),
     guarda las respuestas nuevas recibidas desde FECHA_CORTE_RESPUESTAS y reprograma
     la siguiente revisión según la antigüedad de la campaña.
  3. Completa los datos del SMS de origen (DNI, cartera, texto, fecha de envío) con la
     búsqueda de campañas filtrada por CampaignId. getMessage devolvió HTTP 400 en las
     9 cuentas (prueba del 20/11/2026), por eso no se usa.
  4. Deja una fila en CRM_SMS_SINCRONIZACION con lo que hizo y los avisos.

No guarda el estado atendida/pendiente: eso se calcula al consultar contra SISCOB.
No escribe en SISCOB. Un candado (sp_getapplock) impide dos corridas a la vez.
"""
from __future__ import annotations

import json
import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, Iterable
from zoneinfo import ZoneInfo

from sqlalchemy import text

from app.services import respuestas_mowa_service as mowa

logger = logging.getLogger(__name__)

FECHA_CORTE_RESPUESTAS = date(2026, 11, 1)   # Respuestas recibidas desde esta fecha.
DIAS_CAMPANAS = 60                            # Campañas que se siguen revisando.
# (antigüedad máxima en días, intervalo entre revisiones)
TRAMOS = (
    (2, timedelta(minutes=10)),
    (7, timedelta(minutes=30)),
    (30, timedelta(hours=3)),
    (DIAS_CAMPANAS, timedelta(hours=24)),
)
HORA_LIMITE_DESCUBRIR_AYER = 9      # Antes de esta hora también se descubren las de ayer.
MAX_CAMPANAS_POR_CORRIDA = 800      # Corrida programada; el resto queda para la siguiente.
MAX_CAMPANAS_ORIGEN_POR_CORRIDA = 150
MAX_INTENTOS_ORIGEN = 5
HILOS = 12
CANDADO = "CRM_SMS_SYNC"
TZ = ZoneInfo("America/Lima")


# --------------------------------------------------------------------------- lógica pura

def ahora_lima() -> datetime:
    return datetime.now(TZ).replace(tzinfo=None, microsecond=0)


def intervalo_revision(fecha_creacion: date | None, hoy: date) -> timedelta | None:
    """Intervalo hasta la siguiente revisión; None si la campaña salió de los 60 días."""
    if fecha_creacion is None:
        return TRAMOS[0][1]
    antiguedad = (hoy - fecha_creacion).days
    for maximo, intervalo in TRAMOS:
        if antiguedad <= maximo:
            return intervalo
    return None


def proxima_revision(fecha_creacion: date | None, ahora: datetime) -> datetime | None:
    intervalo = intervalo_revision(fecha_creacion, ahora.date())
    return None if intervalo is None else ahora + intervalo


def dias_a_descubrir(tipo: str, ahora: datetime, desde: date | None = None) -> list[date]:
    hoy = ahora.date()
    if tipo == "BACKFILL" or (tipo == "MANUAL" and desde is not None):
        inicio = desde or (hoy - timedelta(days=DIAS_CAMPANAS))
        return [inicio + timedelta(days=i) for i in range((hoy - inicio).days + 1)]
    dias = [hoy]
    if ahora.hour < HORA_LIMITE_DESCUBRIR_AYER:
        dias.insert(0, hoy - timedelta(days=1))
    return dias


def _texto(valor: Any, largo: int | None = None) -> str | None:
    s = str(valor if valor is not None else "").strip()
    if not s:
        return None
    return s[:largo] if largo else s


def _entero(valor: Any) -> int | None:
    try:
        return int(str(valor).strip())
    except (TypeError, ValueError):
        return None


def datos_campana(cuenta: str, campana: dict, dia: date, ahora: datetime) -> dict | None:
    cid = _entero(campana.get("campaign_id"))
    if cid is None:
        return None
    creacion = mowa._parse_fecha(campana.get("creation_date"))
    envio = mowa._parse_fecha(campana.get("send_date"))
    fecha_base = (creacion or envio).date() if (creacion or envio) else dia
    total = _entero(campana.get("total_messages"))
    if total is None and isinstance(campana.get("messages"), list):
        total = len(campana["messages"])
    return {
        "cuenta": cuenta, "cid": cid,
        "descripcion": _texto(campana.get("description"), 200),
        "creacion": creacion, "envio": envio, "total_mensajes": total,
        # Una campaña nueva se revisa en la misma corrida; fuera de los 60 días no se revisa.
        "proxima": ahora if intervalo_revision(fecha_base, ahora.date()) is not None else None,
    }


def filas_respuesta(cuenta: str, cid: int, data: Any, fecha_creacion: date | None,
                    corte: date = FECHA_CORTE_RESPUESTAS) -> list[dict]:
    """Convierte la respuesta de /campaign/{id}/response en filas, aplicando el corte."""
    if not isinstance(data, dict) or not isinstance(data.get("responses"), list):
        raise mowa.MowaError("Las respuestas Mowa tienen un formato inesperado.")
    filas = []
    for r in data["responses"]:
        if not isinstance(r, dict):
            continue
        rid, mid = _entero(r.get("id")), _entero(r.get("message_id"))
        if rid is None or mid is None:
            continue
        valor = r.get("received_date")
        recibido = mowa._parse_fecha(valor)
        if recibido is not None and recibido.date() < corte:
            continue
        if recibido is None and (fecha_creacion is None or fecha_creacion < corte):
            continue
        filas.append({
            "cuenta": cuenta, "cid": cid, "rid": rid, "mid": mid,
            "msisdn": _texto(r.get("msisdn"), 15), "texto": _texto(r.get("text"), 1000),
            "recibido": recibido, "con_hora": 1 if mowa._tiene_hora(valor) else 0,
            "estado": _entero(r.get("status")), "etiqueta": _texto(r.get("label_status"), 100),
        })
    return filas


def total_respuestas(data: Any) -> int:
    if isinstance(data, dict):
        total = _entero(data.get("total_incoming"))
        if total is not None:
            return total
        if isinstance(data.get("responses"), list):
            return len(data["responses"])
    return 0


def origen_por_mensaje(campana: dict) -> dict[int, dict]:
    """message_id -> datos del SMS de origen, tomados de la búsqueda de campañas."""
    salida = {}
    for m in campana.get("messages") or []:
        if not isinstance(m, dict):
            continue
        mid = _entero(m.get("id"))
        if mid is None:
            continue
        dni = _texto(m.get("dni"), 20)
        valor_envio = m.get("send_date") or m.get("creation_date") or campana.get("send_date")
        salida[mid] = {
            "dni": None if dni in (None, "0") else dni,
            "cartera": _entero(m.get("cartera_id") if m.get("cartera_id") is not None else m.get("cartera")) or None,
            "texto": _texto(m.get("text"), 400),
            "envio": mowa._parse_fecha(valor_envio),
        }
    return salida


# --------------------------------------------------------------------------- Mowa

def _buscar_campana_por_id(cuenta: str, key: str, cid: int, dias: Iterable[date]) -> dict | None:
    """Busca una campaña puntual. Si Mowa ignora el filtro campaignId, se filtra aquí."""
    for dia in dict.fromkeys(d for d in dias if d):
        data = mowa._get_json("POST", f"{mowa.MOWA_BASE}/campaigns/search", key,
                              json={"fromDate": dia.isoformat(), "toDate": dia.isoformat(),
                                    "campaignId": cid})
        if not isinstance(data, list):
            raise mowa.MowaError("La búsqueda de campañas tiene un formato inesperado.")
        encontrada = next((c for c in data if isinstance(c, dict) and _entero(c.get("campaign_id")) == cid), None)
        if encontrada is not None:
            return encontrada
    return None


# --------------------------------------------------------------------------- base de datos

class Repositorio:
    """Acceso a las tablas CRM_SMS_* de CobAuto."""

    def __init__(self, engine):
        self.engine = engine
        self._conn_candado = None

    def adquirir_candado(self) -> bool:
        self._conn_candado = self.engine.connect()
        resultado = self._conn_candado.exec_driver_sql(
            "SET NOCOUNT ON; DECLARE @r int; "
            f"EXEC @r = sp_getapplock @Resource = N'{CANDADO}', @LockMode = 'Exclusive', "
            "@LockOwner = 'Session', @LockTimeout = 0; SELECT @r AS r;").scalar()
        if resultado is None or int(resultado) < 0:
            self._conn_candado.close()
            self._conn_candado = None
            return False
        return True

    def liberar_candado(self) -> None:
        if self._conn_candado is None:
            return
        try:
            self._conn_candado.exec_driver_sql(
                f"EXEC sp_releaseapplock @Resource = N'{CANDADO}', @LockOwner = 'Session';")
        finally:
            self._conn_candado.close()
            self._conn_candado = None

    def iniciar_registro(self, tipo: str, inicio: datetime) -> int:
        with self.engine.begin() as conn:
            return int(conn.execute(text("""
                SET NOCOUNT ON;
                INSERT INTO CobAuto.dbo.CRM_SMS_SINCRONIZACION (Inicio, Tipo) VALUES (:inicio, :tipo);
                SELECT CAST(SCOPE_IDENTITY() AS bigint);"""), {"inicio": inicio, "tipo": tipo}).scalar())

    def cerrar_registro(self, id_sync: int, resumen: "Resumen", fin: datetime) -> None:
        with self.engine.begin() as conn:
            conn.execute(text("""
                UPDATE CobAuto.dbo.CRM_SMS_SINCRONIZACION
                SET Fin = :fin, Resultado = :resultado, CampanasNuevas = :nuevas,
                    CampanasRevisadas = :revisadas, RespuestasNuevas = :respuestas,
                    OrigenesCompletados = :origenes, Avisos = :avisos, Detalle = :detalle
                WHERE IdSincronizacion = :id"""), {
                "fin": fin, "resultado": resumen.resultado, "nuevas": resumen.campanas_nuevas,
                "revisadas": resumen.campanas_revisadas, "respuestas": resumen.respuestas_nuevas,
                "origenes": resumen.origenes_completados, "avisos": len(resumen.avisos),
                "detalle": json.dumps(resumen.avisos[:200], ensure_ascii=False) if resumen.avisos else None,
                "id": id_sync})

    def campanas_existentes(self, cuenta: str, ids: list[int]) -> set[int]:
        existentes: set[int] = set()
        with self.engine.connect() as conn:
            for i in range(0, len(ids), 500):
                lote = ids[i:i + 500]
                params = {"cuenta": cuenta, **{f"i{n}": v for n, v in enumerate(lote)}}
                marcas = ", ".join(f":i{n}" for n in range(len(lote)))
                existentes.update(r[0] for r in conn.execute(text(
                    f"SELECT CampaignId FROM CobAuto.dbo.CRM_SMS_CAMPANA WITH (NOLOCK) "
                    f"WHERE Cuenta = :cuenta AND CampaignId IN ({marcas})"), params))
        return existentes

    def insertar_campanas(self, filas: list[dict]) -> None:
        if not filas:
            return
        sql = text("""
            INSERT INTO CobAuto.dbo.CRM_SMS_CAMPANA
                (Cuenta, CampaignId, Descripcion, FechaCreacion, FechaEnvio, TotalMensajes, ProximaRevision)
            VALUES (:cuenta, :cid, :descripcion, :creacion, :envio, :total_mensajes, :proxima)""")
        # Fila por fila: con fast_executemany, pyodbc puede truncar textos de largo variable.
        with self.engine.begin() as conn:
            for fila in filas:
                conn.execute(sql, fila)

    def retirar_campanas_antiguas(self, hoy: date) -> None:
        with self.engine.begin() as conn:
            conn.execute(text("""
                UPDATE CobAuto.dbo.CRM_SMS_CAMPANA SET ProximaRevision = NULL
                WHERE ProximaRevision IS NOT NULL
                  AND CAST(COALESCE(FechaCreacion, FechaEnvio, FechaDescubierta) AS date) < :limite"""),
                {"limite": hoy - timedelta(days=DIAS_CAMPANAS)})

    def campanas_a_revisar(self, ahora: datetime, limite: int | None,
                          forzar: bool = False) -> list[dict]:
        top = f"TOP ({int(limite)})" if limite else ""
        with self.engine.connect() as conn:
            return [dict(r) for r in conn.execute(text(f"""
                SELECT {top} Cuenta AS cuenta, CampaignId AS cid,
                       CAST(COALESCE(FechaCreacion, FechaEnvio, FechaDescubierta) AS date) AS fecha_base,
                       TotalRespuestas AS total
                FROM CobAuto.dbo.CRM_SMS_CAMPANA WITH (NOLOCK)
                WHERE ProximaRevision IS NOT NULL
                  AND (ProximaRevision <= :ahora OR :forzar = 1)
                ORDER BY ProximaRevision"""), {"ahora": ahora, "forzar": int(forzar)}).mappings()]

    def respuestas_existentes(self, cuenta: str, cid: int) -> set[int]:
        with self.engine.connect() as conn:
            return {r[0] for r in conn.execute(text(
                "SELECT RespuestaId FROM CobAuto.dbo.CRM_SMS_RESPUESTA WITH (NOLOCK) "
                "WHERE Cuenta = :cuenta AND CampaignId = :cid"), {"cuenta": cuenta, "cid": cid})}

    def guardar_revision(self, cuenta: str, cid: int, nuevas: list[dict], total: int,
                         ahora: datetime, proxima: datetime | None) -> None:
        with self.engine.begin() as conn:
            sql = text("""
                INSERT INTO CobAuto.dbo.CRM_SMS_RESPUESTA
                    (Cuenta, CampaignId, RespuestaId, MessageId, Msisdn, Texto, FechaRecepcion,
                     RecepcionConHora, EstadoMowa, EtiquetaMowa)
                VALUES (:cuenta, :cid, :rid, :mid, :msisdn, :texto, :recibido,
                        :con_hora, :estado, :etiqueta)""")
            for fila in nuevas:
                conn.execute(sql, fila)
            conn.execute(text("""
                UPDATE CobAuto.dbo.CRM_SMS_CAMPANA
                SET TotalRespuestas = :total, UltimaRevision = :ahora, ProximaRevision = :proxima
                WHERE Cuenta = :cuenta AND CampaignId = :cid"""),
                {"total": total, "ahora": ahora, "proxima": proxima, "cuenta": cuenta, "cid": cid})

    def reprogramar(self, cuenta: str, cid: int, proxima: datetime) -> None:
        with self.engine.begin() as conn:
            conn.execute(text("UPDATE CobAuto.dbo.CRM_SMS_CAMPANA SET ProximaRevision = :p "
                              "WHERE Cuenta = :cuenta AND CampaignId = :cid"),
                         {"p": proxima, "cuenta": cuenta, "cid": cid})

    def campanas_con_origen_pendiente(self, limite: int | None) -> list[dict]:
        top = f"TOP ({int(limite)})" if limite else ""
        with self.engine.connect() as conn:
            return [dict(r) for r in conn.execute(text(f"""
                SELECT {top} R.Cuenta AS cuenta, R.CampaignId AS cid,
                       CAST(C.FechaCreacion AS date) AS creacion, CAST(C.FechaEnvio AS date) AS envio
                FROM (SELECT DISTINCT Cuenta, CampaignId FROM CobAuto.dbo.CRM_SMS_RESPUESTA WITH (NOLOCK)
                      WHERE OrigenEstado = 'PENDIENTE') R
                JOIN CobAuto.dbo.CRM_SMS_CAMPANA C WITH (NOLOCK)
                  ON C.Cuenta = R.Cuenta AND C.CampaignId = R.CampaignId
                ORDER BY R.CampaignId DESC""")).mappings()]

    def completar_origen(self, cuenta: str, cid: int, origen: dict[int, dict] | None) -> int:
        """Completa las respuestas pendientes de una campaña. origen=None: campaña no hallada."""
        with self.engine.begin() as conn:
            pendientes = [r[0] for r in conn.execute(text(
                "SELECT DISTINCT MessageId FROM CobAuto.dbo.CRM_SMS_RESPUESTA "
                "WHERE Cuenta = :cuenta AND CampaignId = :cid AND OrigenEstado = 'PENDIENTE'"),
                {"cuenta": cuenta, "cid": cid})]
            completados = 0
            for mid in pendientes:
                datos = (origen or {}).get(int(mid))
                if datos:
                    conn.execute(text("""
                        UPDATE CobAuto.dbo.CRM_SMS_RESPUESTA
                        SET Dni = :dni, CarteraMowa = :cartera, MensajeTexto = :texto,
                            MensajeFechaEnvio = :envio, OrigenEstado = 'OK'
                        WHERE Cuenta = :cuenta AND CampaignId = :cid AND MessageId = :mid
                          AND OrigenEstado = 'PENDIENTE'"""),
                        {**datos, "cuenta": cuenta, "cid": cid, "mid": mid})
                    completados += 1
                else:
                    conn.execute(text("""
                        UPDATE CobAuto.dbo.CRM_SMS_RESPUESTA
                        SET OrigenIntentos = OrigenIntentos + 1,
                            OrigenEstado = CASE WHEN OrigenIntentos + 1 >= :maximo
                                                THEN 'NO_ENCONTRADO' ELSE 'PENDIENTE' END
                        WHERE Cuenta = :cuenta AND CampaignId = :cid AND MessageId = :mid
                          AND OrigenEstado = 'PENDIENTE'"""),
                        {"maximo": MAX_INTENTOS_ORIGEN, "cuenta": cuenta, "cid": cid, "mid": mid})
            return completados


# --------------------------------------------------------------------------- orquestación

@dataclass
class Resumen:
    tipo: str
    campanas_nuevas: int = 0
    campanas_revisadas: int = 0
    respuestas_nuevas: int = 0
    origenes_completados: int = 0
    avisos: list[str] = field(default_factory=list)
    omitida: bool = False

    @property
    def resultado(self) -> str:
        return "CON_AVISOS" if self.avisos else "OK"


def _llaves() -> dict[str, str]:
    return {nombre: key for nombre, _, key in mowa._cuentas_visibles(None) if key}


def _descubrir(repo: Repositorio, llaves: dict[str, str], dias: list[date],
               ahora: datetime, resumen: Resumen) -> None:
    trabajos = [(cuenta, key, dia) for cuenta, key in llaves.items() for dia in dias]
    with ThreadPoolExecutor(max_workers=min(HILOS, len(trabajos) or 1)) as pool:
        futuros = {pool.submit(mowa._campanas_con_rescate, c, k, d, d): (c, d) for c, k, d in trabajos}
        por_cuenta: dict[str, dict[int, dict]] = {}
        for futuro, (cuenta, dia) in futuros.items():
            try:
                encontradas = futuro.result()
            except mowa.MowaError as exc:
                resumen.avisos.append(f"{cuenta} búsqueda {dia}: {exc}")
                continue
            for _, _, campana in encontradas:
                fila = datos_campana(cuenta, campana, dia, ahora)
                if fila:
                    por_cuenta.setdefault(cuenta, {})[fila["cid"]] = fila
    for cuenta, filas in por_cuenta.items():
        existentes = repo.campanas_existentes(cuenta, list(filas))
        nuevas = [f for cid, f in filas.items() if cid not in existentes]
        repo.insertar_campanas(nuevas)
        resumen.campanas_nuevas += len(nuevas)


def _revisar(repo: Repositorio, llaves: dict[str, str], ahora: datetime,
             limite: int | None, resumen: Resumen, forzar: bool = False) -> None:
    pendientes = [c for c in repo.campanas_a_revisar(ahora, limite, forzar) if c["cuenta"] in llaves]

    def consultar(c):
        return mowa._get_json("GET", f"{mowa.MOWA_BASE}/campaign/{c['cid']}/response", llaves[c["cuenta"]])

    with ThreadPoolExecutor(max_workers=HILOS) as pool:
        futuros = [(c, pool.submit(consultar, c)) for c in pendientes]
        for campana, futuro in futuros:
            cuenta, cid = campana["cuenta"], int(campana["cid"])
            try:
                data = futuro.result()
                filas = filas_respuesta(cuenta, cid, data, campana["fecha_base"])
            except mowa.MowaError as exc:
                resumen.avisos.append(f"{cuenta} campaña {cid}: {exc}")
                # Reintento pronto, sin perder el tramo: 10 minutos.
                repo.reprogramar(cuenta, cid, ahora + TRAMOS[0][1])
                continue
            existentes = repo.respuestas_existentes(cuenta, cid) if filas else set()
            nuevas = [f for f in filas if f["rid"] not in existentes]
            repo.guardar_revision(cuenta, cid, nuevas, total_respuestas(data), ahora,
                                  proxima_revision(campana["fecha_base"], ahora))
            resumen.campanas_revisadas += 1
            resumen.respuestas_nuevas += len(nuevas)


def _completar_origenes(repo: Repositorio, llaves: dict[str, str], limite: int | None,
                        resumen: Resumen) -> None:
    pendientes = [c for c in repo.campanas_con_origen_pendiente(limite) if c["cuenta"] in llaves]

    def buscar(c):
        return _buscar_campana_por_id(c["cuenta"], llaves[c["cuenta"]], int(c["cid"]),
                                      (c["creacion"], c["envio"]))

    with ThreadPoolExecutor(max_workers=HILOS) as pool:
        futuros = [(c, pool.submit(buscar, c)) for c in pendientes]
        for campana, futuro in futuros:
            try:
                encontrada = futuro.result()
            except mowa.MowaError as exc:
                # Falla de Mowa: no consume intentos; se reintenta en la siguiente corrida.
                resumen.avisos.append(f"{campana['cuenta']} origen campaña {campana['cid']}: {exc}")
                continue
            origen = origen_por_mensaje(encontrada) if encontrada else None
            resumen.origenes_completados += repo.completar_origen(
                campana["cuenta"], int(campana["cid"]), origen)


def ejecutar(engine, tipo: str = "PROGRAMADA", desde: date | None = None,
             ahora: datetime | None = None) -> Resumen:
    """Corre una sincronización completa. tipo: PROGRAMADA, MANUAL o BACKFILL."""
    tipo = tipo.upper()
    ahora = ahora or ahora_lima()
    resumen = Resumen(tipo=tipo)
    repo = Repositorio(engine)
    if not repo.adquirir_candado():
        resumen.omitida = True
        logger.info("Sincronización SMS omitida: hay otra corrida en curso.")
        return resumen
    id_sync = None
    try:
        id_sync = repo.iniciar_registro(tipo, ahora)
        llaves = _llaves()
        for nombre, _, key in mowa._cuentas_visibles(None):
            if not key:
                resumen.avisos.append(f"{nombre}: llave Mowa no configurada.")
        es_backfill = tipo == "BACKFILL" or (tipo == "MANUAL" and desde is not None)
        _descubrir(repo, llaves, dias_a_descubrir(tipo, ahora, desde), ahora, resumen)
        repo.retirar_campanas_antiguas(ahora.date())
        _revisar(repo, llaves, ahora, None if es_backfill else MAX_CAMPANAS_POR_CORRIDA,
                resumen, forzar=tipo == "MANUAL" and desde is not None)
        _completar_origenes(repo, llaves, None if es_backfill else MAX_CAMPANAS_ORIGEN_POR_CORRIDA, resumen)
        repo.cerrar_registro(id_sync, resumen, ahora_lima())
        logger.info("Sincronización SMS %s: campañas nuevas=%s revisadas=%s respuestas nuevas=%s "
                    "orígenes=%s avisos=%s", tipo, resumen.campanas_nuevas, resumen.campanas_revisadas,
                    resumen.respuestas_nuevas, resumen.origenes_completados, len(resumen.avisos))
        return resumen
    except Exception as exc:
        logger.exception("Sincronización SMS %s falló", tipo)
        if id_sync is not None:
            resumen.avisos.append(f"ERROR: {type(exc).__name__}")
            try:
                with engine.begin() as conn:
                    conn.execute(text("UPDATE CobAuto.dbo.CRM_SMS_SINCRONIZACION SET Fin = :fin, "
                                      "Resultado = 'ERROR', Detalle = :d WHERE IdSincronizacion = :id"),
                                 {"fin": ahora_lima(), "d": json.dumps(resumen.avisos[:200], ensure_ascii=False),
                                  "id": id_sync})
            except Exception:
                logger.exception("No se pudo registrar el error de la sincronización SMS")
        raise
    finally:
        repo.liberar_candado()
