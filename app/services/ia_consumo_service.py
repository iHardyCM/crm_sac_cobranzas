"""
Consumo de la API de IA por evaluación (CRM_IA_CONSUMO_API).

QUE HACE
Guarda una fila por cada llamada a la API con lo que la propia respuesta
informa: modelo, tokens de entrada (y cuántos vinieron del cache), tokens de
salida, tokens de audio y cuánto tardó. La fila queda ligada al id_feedback de
la evaluación en curso y al paso del pipeline que la originó.

POR QUE ASI
- Los tokens NO se estiman: si la respuesta no trae 'usage', se guarda 0 y la
  fila queda marcada; inventar un consumo haria inutil el reporte.
- El COSTO no se guarda: se calcula al leer, multiplicando tokens por la tarifa
  vigente en CRM_IA_TARIFA_MODELO. Si un modelo no tiene tarifa cargada, el
  reporte muestra tokens y deja el costo vacio.
- Registrar nunca puede romper un analisis: todo va en try/except y, si falla la
  escritura, solo queda una advertencia en el log.

COMO SE USA
    with contexto_consumo(id_feedback):
        ...  # todo lo que llame a la API dentro queda atribuido a esa evaluacion

    registrar_consumo("CRITERIOS", modelo, respuesta, duracion_ms=123)
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Dict, List, Optional

from sqlalchemy import text

from app.core.db_siscob import engine_siscob

logger = logging.getLogger(__name__)

_ID_FEEDBACK: ContextVar[Optional[int]] = ContextVar("ia_consumo_id_feedback", default=None)


def fijar_contexto_consumo(id_feedback: Optional[int]):
    """Marca a que evaluacion pertenece todo lo que se llame a partir de aqui."""
    return _ID_FEEDBACK.set(int(id_feedback) if id_feedback else None)


def liberar_contexto_consumo(token) -> None:
    try:
        _ID_FEEDBACK.reset(token)
    except (ValueError, LookupError):
        _ID_FEEDBACK.set(None)


@contextmanager
def contexto_consumo(id_feedback: Optional[int]):
    token = _ID_FEEDBACK.set(int(id_feedback) if id_feedback else None)
    try:
        yield
    finally:
        _ID_FEEDBACK.reset(token)


def _entero(valor) -> int:
    try:
        return int(valor or 0)
    except (TypeError, ValueError):
        return 0


def _uso_de_respuesta(respuesta) -> Dict[str, int]:
    """Lee 'usage' de la respuesta, sea objeto del SDK o dict.

    Los nombres cambian entre endpoints (prompt_tokens / input_tokens), asi que
    se aceptan ambos. Lo que no venga queda en 0, no se estima.
    """
    uso = getattr(respuesta, "usage", None)
    if uso is None and isinstance(respuesta, dict):
        uso = respuesta.get("usage")
    if uso is None:
        return {}
    if not isinstance(uso, dict):
        try:
            uso = uso.model_dump()
        except Exception:
            uso = {k: getattr(uso, k, None) for k in
                   ("prompt_tokens", "completion_tokens", "total_tokens",
                    "input_tokens", "output_tokens", "input_token_details", "prompt_tokens_details")}

    detalles = uso.get("prompt_tokens_details") or uso.get("input_token_details") or {}
    if detalles and not isinstance(detalles, dict):
        try:
            detalles = detalles.model_dump()
        except Exception:
            detalles = {k: getattr(detalles, k, None) for k in ("cached_tokens", "audio_tokens", "text_tokens")}

    return {
        "tokens_input": _entero(uso.get("prompt_tokens") or uso.get("input_tokens")),
        "tokens_output": _entero(uso.get("completion_tokens") or uso.get("output_tokens")),
        "tokens_cacheados": _entero((detalles or {}).get("cached_tokens")),
        "tokens_audio": _entero((detalles or {}).get("audio_tokens")),
    }


def registrar_consumo(
    paso: str,
    modelo: str,
    respuesta=None,
    *,
    id_feedback: Optional[int] = None,
    duracion_ms: Optional[int] = None,
    segundos_audio: Optional[float] = None,
    exito: bool = True,
    detalle_error: Optional[str] = None,
) -> None:
    uso = _uso_de_respuesta(respuesta) if respuesta is not None else {}
    fila = {
        "id_feedback": id_feedback if id_feedback is not None else _ID_FEEDBACK.get(),
        "paso": str(paso or "DESCONOCIDO")[:40],
        "modelo": str(modelo or "")[:100],
        "tokens_input": uso.get("tokens_input", 0),
        "tokens_cacheados": uso.get("tokens_cacheados", 0),
        "tokens_output": uso.get("tokens_output", 0),
        "tokens_audio": uso.get("tokens_audio", 0),
        "segundos_audio": float(segundos_audio) if segundos_audio else None,
        "duracion_ms": int(duracion_ms) if duracion_ms is not None else None,
        "exito": 1 if exito else 0,
        "detalle_error": (detalle_error or None) and str(detalle_error)[:400],
    }
    try:
        with engine_siscob.begin() as conn:
            conn.execute(text("""
                INSERT INTO CobAuto.dbo.CRM_IA_CONSUMO_API
                    (id_feedback, paso, modelo, tokens_input, tokens_cacheados, tokens_output,
                     tokens_audio, segundos_audio, duracion_ms, exito, detalle_error)
                VALUES
                    (:id_feedback, :paso, :modelo, :tokens_input, :tokens_cacheados, :tokens_output,
                     :tokens_audio, :segundos_audio, :duracion_ms, :exito, :detalle_error)
            """), fila)
    except Exception as exc:  # nunca debe tumbar un analisis
        logger.warning("[CONSUMO] no se pudo registrar (%s/%s): %s", paso, modelo, exc)


# ---------------------------------------------------------------- reporte

SQL_COSTO = """
    costo = SUM(
        ISNULL(C.tokens_input - C.tokens_cacheados, 0) * ISNULL(T_IN.precio_unitario, 0)
      + ISNULL(C.tokens_cacheados, 0) * ISNULL(COALESCE(T_CA.precio_unitario, T_IN.precio_unitario), 0)
      + ISNULL(C.tokens_output, 0)    * ISNULL(T_OUT.precio_unitario, 0)
      + ISNULL(C.tokens_audio, 0)     * ISNULL(T_AU.precio_unitario, 0)
    )
"""

# Una tarifa por modelo y concepto: la ultima vigente.
SQL_TARIFAS = """
    (SELECT modelo, concepto, precio_unitario = precio / NULLIF(unidad, 0),
            rn = ROW_NUMBER() OVER (PARTITION BY modelo, concepto ORDER BY vigente_desde DESC)
     FROM CobAuto.dbo.CRM_IA_TARIFA_MODELO)
"""


def _joins_tarifa(alias: str = "C") -> str:
    partes = []
    for sufijo, concepto in (("IN", "INPUT"), ("CA", "CACHEADO"), ("OUT", "OUTPUT"), ("AU", "AUDIO")):
        partes.append(f"""
        LEFT JOIN {SQL_TARIFAS} T_{sufijo}
               ON T_{sufijo}.modelo = {alias}.modelo AND T_{sufijo}.concepto = '{concepto}' AND T_{sufijo}.rn = 1""")
    return "".join(partes)


def hay_tarifas() -> bool:
    try:
        with engine_siscob.connect() as conn:
            return bool(conn.execute(text("SELECT TOP 1 1 FROM CobAuto.dbo.CRM_IA_TARIFA_MODELO")).scalar())
    except Exception:
        return False


def obtener_consumo(dias: int = 30, limite: int = 200) -> Dict:
    """Consumo por evaluación y por día, con el costo cuando hay tarifas."""
    params = {"dias": -abs(int(dias)), "limite": int(limite)}
    con_tarifas = hay_tarifas()

    sql_evaluaciones = text(f"""
        SELECT TOP (:limite)
               C.id_feedback,
               L.archivo_nombre, L.cartera, L.agente,
               L.duracion_segundos, L.fecha_creacion, L.score_final,
               llamadas_api = COUNT(*),
               tokens_input = SUM(C.tokens_input),
               tokens_cacheados = SUM(C.tokens_cacheados),
               tokens_output = SUM(C.tokens_output),
               tokens_audio = SUM(C.tokens_audio),
               segundos_api = SUM(ISNULL(C.duracion_ms, 0)) / 1000.0,
               {SQL_COSTO},
               primera = MIN(C.fecha), ultima = MAX(C.fecha)
        FROM CobAuto.dbo.CRM_IA_CONSUMO_API C WITH(NOLOCK)
        LEFT JOIN CobAuto.dbo.ia_feedback_llamadas L WITH(NOLOCK) ON L.id_feedback = C.id_feedback
        {_joins_tarifa()}
        WHERE C.fecha >= DATEADD(DAY, :dias, GETDATE())
        GROUP BY C.id_feedback, L.archivo_nombre, L.cartera, L.agente,
                 L.duracion_segundos, L.fecha_creacion, L.score_final
        ORDER BY MAX(C.fecha) DESC
    """)

    sql_pasos = text(f"""
        SELECT C.paso, C.modelo,
               llamadas = COUNT(*),
               evaluaciones = COUNT(DISTINCT C.id_feedback),
               tokens_input = SUM(C.tokens_input),
               tokens_cacheados = SUM(C.tokens_cacheados),
               tokens_output = SUM(C.tokens_output),
               tokens_audio = SUM(C.tokens_audio),
               {SQL_COSTO}
        FROM CobAuto.dbo.CRM_IA_CONSUMO_API C WITH(NOLOCK)
        {_joins_tarifa()}
        WHERE C.fecha >= DATEADD(DAY, :dias, GETDATE())
        GROUP BY C.paso, C.modelo
        ORDER BY SUM(C.tokens_input + C.tokens_output + C.tokens_audio) DESC
    """)

    sql_dias = text(f"""
        SELECT dia = CAST(C.fecha AS DATE),
               evaluaciones = COUNT(DISTINCT C.id_feedback),
               llamadas = COUNT(*),
               tokens = SUM(C.tokens_input + C.tokens_output + C.tokens_audio),
               {SQL_COSTO}
        FROM CobAuto.dbo.CRM_IA_CONSUMO_API C WITH(NOLOCK)
        {_joins_tarifa()}
        WHERE C.fecha >= DATEADD(DAY, :dias, GETDATE())
        GROUP BY CAST(C.fecha AS DATE)
        ORDER BY dia
    """)

    with engine_siscob.connect() as conn:
        evaluaciones = [dict(r) for r in conn.execute(sql_evaluaciones, params).mappings()]
        pasos = [dict(r) for r in conn.execute(sql_pasos, params).mappings()]
        dias_lista = [dict(r) for r in conn.execute(sql_dias, params).mappings()]

    def limpiar(filas: List[Dict]) -> List[Dict]:
        salida = []
        for fila in filas:
            item = {}
            for k, v in fila.items():
                if hasattr(v, "isoformat"):
                    item[k] = v.isoformat()
                elif hasattr(v, "__float__") and not isinstance(v, (int, bool)):
                    item[k] = float(v)
                else:
                    item[k] = v
            if not con_tarifas:
                item["costo"] = None
            salida.append(item)
        return salida

    evaluaciones = limpiar(evaluaciones)
    pasos = limpiar(pasos)
    dias_lista = limpiar(dias_lista)

    total_costo = sum(e.get("costo") or 0 for e in evaluaciones) if con_tarifas else None
    medibles = [e for e in evaluaciones if e.get("id_feedback")]
    return {
        "con_tarifas": con_tarifas,
        "dias": abs(int(dias)),
        "resumen": {
            "evaluaciones": len(medibles),
            "llamadas_api": sum(e.get("llamadas_api") or 0 for e in evaluaciones),
            "tokens": sum((e.get("tokens_input") or 0) + (e.get("tokens_output") or 0) + (e.get("tokens_audio") or 0) for e in evaluaciones),
            "costo_total": round(total_costo, 4) if total_costo is not None else None,
            "costo_promedio": round(total_costo / len(medibles), 4) if total_costo is not None and medibles else None,
        },
        "evaluaciones": evaluaciones,
        "pasos": pasos,
        "dias_detalle": dias_lista,
    }
