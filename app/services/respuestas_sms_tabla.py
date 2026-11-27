"""Respuestas SMS leídas desde CobAuto.dbo.CRM_SMS_* (fase 1b del diseño).

La carga programada (respuestas_sms_sync) guarda las respuestas de Mowa. Aquí solo se
leen y se cruzan con SISCOB usando las mismas reglas que la consulta en vivo
(respuestas_mowa_service.clasificar_respuestas): vínculo por DNI y cartera del SMS,
cliente activo (ESTADO A o N) y gestión posterior a la recepción.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import text

from app.core.db_siscob import engine_siscob
from app.services import respuestas_mowa_service as mowa
from app.services.respuestas_sms_sync import FECHA_CORTE_RESPUESTAS, ahora_lima

MINUTOS_CARGA_DESACTUALIZADA = 30

_SQL_RESPUESTAS = """
    SELECT R.Cuenta, R.CampaignId, R.RespuestaId, R.MessageId, R.Msisdn, R.Texto,
           R.FechaRecepcion, R.RecepcionConHora, R.EstadoMowa, R.EtiquetaMowa,
           R.Dni, R.CarteraMowa, R.MensajeTexto, R.MensajeFechaEnvio, R.OrigenEstado,
           C.Descripcion, C.FechaCreacion
    FROM CobAuto.dbo.CRM_SMS_RESPUESTA R WITH (NOLOCK)
    LEFT JOIN CobAuto.dbo.CRM_SMS_CAMPANA C WITH (NOLOCK)
      ON C.Cuenta = R.Cuenta AND C.CampaignId = R.CampaignId
    WHERE R.Cuenta IN ({cuentas}) {filtro_fecha}
"""


def _iso(valor: Any, con_hora: bool = True) -> str | None:
    if not valor:
        return None
    if isinstance(valor, datetime):
        return valor.isoformat(timespec="seconds") if con_hora else valor.date().isoformat()
    return str(valor)


def fila_desde_tabla(r: dict) -> dict:
    """Convierte una fila de CRM_SMS_RESPUESTA al formato que ya usa la vista."""
    dni = str(r.get("Dni") or "").strip()
    origen = r.get("OrigenEstado")
    if origen == "PENDIENTE":
        motivo = "Los datos del SMS de origen aún se están cargando."
    elif origen == "NO_ENCONTRADO":
        motivo = "Mowa no devolvió el SMS de origen de esta respuesta."
    elif not dni:
        motivo = "El envío no trae un identificador de cliente verificable."
    else:
        motivo = None
    creacion = r.get("FechaCreacion")
    return {
        "id": str(r["RespuestaId"]), "cuenta": r["Cuenta"],
        "campana_id": int(r["CampaignId"]), "campana": r.get("Descripcion") or "",
        "campana_creacion": creacion.date().isoformat() if isinstance(creacion, datetime) else None,
        "mensaje_id": str(r["MessageId"]),
        "mensaje_enviado": r.get("MensajeTexto"),
        "mensaje_enviado_fecha": _iso(r.get("MensajeFechaEnvio")),
        "mensaje_enviado_estado": None,
        "telefono": r.get("Msisdn") or "",
        "texto": r.get("Texto") or "",
        "recibido": _iso(r.get("FechaRecepcion"), bool(r.get("RecepcionConHora"))),
        "estado_mowa_codigo": r.get("EstadoMowa"),
        "estado_mowa_etiqueta": r.get("EtiquetaMowa"),
        "dni": dni, "cartera_mowa": int(r.get("CarteraMowa") or 0),
        "cliente": None, "idcliente": None, "idcartera": None,
        "gestion_posterior": None, "gestion_posterior_texto": None,
        "gestion_posterior_id": None, "estado": "SIN_VINCULAR", "motivo": motivo,
    }


def _cuentas(carteras_permitidas: set[int] | None, cuenta: str | None) -> list[str]:
    nombres = [n for n, _, _ in mowa._cuentas_reportables(carteras_permitidas)]
    return [n for n in nombres if not cuenta or n == cuenta]


def _leer(cuentas: list[str], desde: date | None, hasta: date | None, engine=None) -> list[dict]:
    if not cuentas:
        return []
    params: dict[str, Any] = {f"c{i}": c for i, c in enumerate(cuentas)}
    filtro = ""
    if desde is not None:
        filtro += " AND R.FechaRecepcion >= :desde"
        params["desde"] = datetime.combine(desde, datetime.min.time())
    if hasta is not None:
        filtro += " AND R.FechaRecepcion < :hasta"
        params["hasta"] = datetime.combine(hasta + timedelta(days=1), datetime.min.time())
    sql = text(_SQL_RESPUESTAS.format(cuentas=", ".join(f":c{i}" for i in range(len(cuentas))),
                                      filtro_fecha=filtro))
    with (engine or engine_siscob).connect() as conn:
        return [dict(r) for r in conn.execute(sql, params).mappings()]


def ultima_sincronizacion(engine=None) -> dict:
    with (engine or engine_siscob).connect() as conn:
        fila = conn.execute(text("""
            SELECT TOP (1) Fin, Resultado FROM CobAuto.dbo.CRM_SMS_SINCRONIZACION WITH (NOLOCK)
            WHERE Fin IS NOT NULL AND Resultado IN ('OK', 'CON_AVISOS')
            ORDER BY IdSincronizacion DESC""")).mappings().first()
        intento = conn.execute(text("""
            SELECT TOP (1) Inicio, Fin, Resultado, Avisos
            FROM CobAuto.dbo.CRM_SMS_SINCRONIZACION WITH (NOLOCK)
            ORDER BY IdSincronizacion DESC""")).mappings().first()
    ultimo_intento = ({"inicio": _iso(intento["Inicio"]), "fin": _iso(intento["Fin"]),
                       "resultado": intento["Resultado"], "avisos": intento.get("Avisos")}
                      if intento else None)
    if not fila:
        return {"fin": None, "resultado": None, "desactualizada": True,
                "ultimo_intento": ultimo_intento}
    fin = fila["Fin"]
    return {"fin": _iso(fin), "resultado": fila["Resultado"],
            "desactualizada": ahora_lima() - fin > timedelta(minutes=MINUTOS_CARGA_DESACTUALIZADA),
            "ultimo_intento": ultimo_intento}


def estado_carga(engine=None) -> dict:
    """Última corrida global para el control manual; no devuelve datos de clientes."""
    with (engine or engine_siscob).connect() as conn:
        fila = conn.execute(text("""
            SELECT TOP (1) IdSincronizacion, Tipo, Inicio, Fin, Resultado,
                   CampanasNuevas, CampanasRevisadas, RespuestasNuevas,
                   OrigenesCompletados, Avisos
            FROM CobAuto.dbo.CRM_SMS_SINCRONIZACION WITH (NOLOCK)
            ORDER BY IdSincronizacion DESC""")).mappings().first()
    if not fila:
        return {"id": 0, "en_curso": False, "interrumpida": False}
    datos = dict(fila)
    sin_cierre = datos["Fin"] is None
    # Un proceso interrumpido deja Fin nulo. Pasadas dos horas permite reintentar.
    en_curso = sin_cierre and ahora_lima() - datos["Inicio"] < timedelta(hours=2)
    return {
        "id": datos["IdSincronizacion"], "tipo": datos["Tipo"],
        "inicio": _iso(datos["Inicio"]), "fin": _iso(datos["Fin"]),
        "resultado": datos["Resultado"], "en_curso": en_curso,
        "interrumpida": sin_cierre and not en_curso,
        "campanas_nuevas": datos["CampanasNuevas"],
        "campanas_revisadas": datos["CampanasRevisadas"],
        "respuestas_nuevas": datos["RespuestasNuevas"],
        "origenes_completados": datos["OrigenesCompletados"],
        "avisos": datos["Avisos"],
    }


def consultar_recibidas(desde: date, hasta: date, carteras_permitidas: set[int] | None,
                        cuenta: str | None = None) -> dict:
    """Respuestas recibidas en el rango (por fecha de recepción), ya clasificadas."""
    advertencias: list[str] = []
    filas = [fila_desde_tabla(r) for r in _leer(_cuentas(carteras_permitidas, cuenta), desde, hasta)]
    filas, excluidas, _ = mowa.clasificar_respuestas(filas, carteras_permitidas, advertencias)
    return {"data": filas, "advertencias": advertencias, "excluidas_inactivas": excluidas,
            "completo": not advertencias, "desde": desde.isoformat(), "hasta": hasta.isoformat(),
            "sincronizacion": ultima_sincronizacion(),
            "alcance_carteras": None if carteras_permitidas is None else sorted(carteras_permitidas)}


def agrupar_sin_atender(filas: list[dict]) -> list[dict]:
    """Clientes (cartera + ID) con al menos una respuesta PENDIENTE; solo sus pendientes."""
    grupos: dict[tuple, list[dict]] = {}
    for fila in filas:
        if fila.get("estado") == "PENDIENTE" and fila.get("idcliente") and fila.get("idcartera"):
            grupos.setdefault((fila["idcartera"], fila["idcliente"]), []).append(fila)
    salida = [{"estado": "PENDIENTE", "filas": sorted(g, key=lambda r: r.get("recibido") or "")}
              for g in grupos.values()]
    # Primero los que llevan más tiempo esperando.
    salida.sort(key=lambda g: g["filas"][0].get("recibido") or "")
    return salida


def sin_atender(carteras_permitidas: set[int] | None, cuenta: str | None = None,
                idcartera: int | None = None) -> dict:
    """Todos los clientes activos con respuestas sin gestión posterior (desde el corte)."""
    advertencias: list[str] = []
    filas = [fila_desde_tabla(r) for r in _leer(_cuentas(carteras_permitidas, cuenta), None, None)]
    filas, _, _ = mowa.clasificar_respuestas(filas, carteras_permitidas, advertencias)
    if idcartera is not None:
        filas = [fila for fila in filas if fila.get("idcartera") == idcartera]
    grupos = agrupar_sin_atender(filas)
    por_cartera: dict[int, int] = {}
    for g in grupos:
        cartera = g["filas"][0]["idcartera"]
        por_cartera[cartera] = por_cartera.get(cartera, 0) + 1
    hoy = ahora_lima().date()
    ayer = hoy - timedelta(days=1)
    recientes = sum(1 for g in grupos if (g["filas"][-1].get("recibido") or "")[:10] >= ayer.isoformat())
    return {"clientes": len(grupos), "respuestas": sum(len(g["filas"]) for g in grupos),
            "clientes_ayer_hoy": recientes,
            "por_cartera": [{"idcartera": c, "clientes": n} for c, n in sorted(por_cartera.items())],
            "desde": FECHA_CORTE_RESPUESTAS.isoformat(), "advertencias": advertencias,
            "completo": not advertencias, "grupos": grupos,
            "sincronizacion": ultima_sincronizacion()}
