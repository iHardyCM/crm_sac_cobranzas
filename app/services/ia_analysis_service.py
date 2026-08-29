from __future__ import annotations

import json
import logging
import os
import re
import unicodedata
from pathlib import Path
from typing import Dict, List, Optional

from dotenv import load_dotenv
from sqlalchemy import text

from app.core.db_siscob import engine_siscob
from app.services.mibanco_quality_pauta import (
    FUENTE_AUDIO,
    FUENTE_TRANSCRIPCION,
    MIBANCO_REGLAS_DESCALIFICACION,
    es_cartera_mibanco,
    obtener_criterio_mibanco,
    obtener_pauta_mibanco,
    resumen_pesos_mibanco,
)
from app.services.pautas_evaluacion_service import (
    aplicar_anulantes_bloque,
    criterios_pauta_publicada_para_cartera,
)

ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / ".env")

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover - depende del entorno del servidor
    OpenAI = None


TRANSCRIPTION_MODEL_CONFIG = os.getenv("IA_FEEDBACK_TRANSCRIPTION_MODEL", "").strip()
TRANSCRIPTION_MODEL = (
    os.getenv("IA_FEEDBACK_DIARIZATION_MODEL")
    or (TRANSCRIPTION_MODEL_CONFIG if "diarize" in TRANSCRIPTION_MODEL_CONFIG.lower() else "")
    or "gpt-4o-transcribe-diarize"
)
TRANSCRIPTION_FALLBACK_MODEL = (
    os.getenv("IA_FEEDBACK_TRANSCRIPTION_FALLBACK_MODEL")
    or (TRANSCRIPTION_MODEL_CONFIG if TRANSCRIPTION_MODEL_CONFIG and "diarize" not in TRANSCRIPTION_MODEL_CONFIG.lower() else "")
    or "gpt-4o-mini-transcribe"
)
ANALYSIS_MODEL = os.getenv("IA_FEEDBACK_ANALYSIS_MODEL", "gpt-4o-mini")
PROMPT_CONFIG_TABLE = "CobAuto.dbo.ia_feedback_prompt_config"
logger = logging.getLogger(__name__)

SGC_GRUPO_NEGOCIO = "Errores críticos del negocio"
SGC_GRUPO_USUARIO = "Errores críticos del usuario final"
SGC_GRUPO_CUMPLIMIENTO = "Errores críticos de cumplimiento"
SGC_GRUPO_NO_CRITICO = "Errores no críticos"
SGC_GRUPO_NO_APLICA = "No aplica"
SGC_GRUPOS_VALIDOS = {
    SGC_GRUPO_NEGOCIO,
    SGC_GRUPO_USUARIO,
    SGC_GRUPO_CUMPLIMIENTO,
    SGC_GRUPO_NO_CRITICO,
    SGC_GRUPO_NO_APLICA,
}

SGC_FACTORES = [
    (SGC_GRUPO_NEGOCIO, "Razón de no pago y explicar motivo", ("2.1", "motivo de atraso", "causa raiz", "causa raíz", "razon de no pago", "razón de no pago")),
    (SGC_GRUPO_NEGOCIO, "Urgencia y persistencia en el pago", ("3.5", "orientacion a resultado", "orientación a resultado", "urgencia", "persistencia")),
    (SGC_GRUPO_NEGOCIO, "Gestión de objeciones del cliente", ("3.2", "objeciones")),
    (SGC_GRUPO_NEGOCIO, "Uso de aplicativo si aplica", ("aplicativo", "uso de aplicativo")),
    (SGC_GRUPO_NEGOCIO, "Asesorar", ("asesorar", "asesoria", "asesoría")),
    (SGC_GRUPO_NEGOCIO, "Dominio de la llamada", ("dominio", "control de conversacion", "control de conversación")),
    (SGC_GRUPO_NEGOCIO, "Parafraseo / reafirmar acuerdo de pagos", ("4.3", "recapitulacion", "recapitulación", "parafraseo", "reafirmar")),
    (SGC_GRUPO_NEGOCIO, "Tipificación correcta", ("tipificacion", "tipificación", "registro", "trazabilidad")),
    (SGC_GRUPO_NEGOCIO, "Falta grave para el negocio", ("falta grave para el negocio",)),
    (SGC_GRUPO_NEGOCIO, "Cierre verificable 3C/4C", ("4.1", "cierre 3c", "cierre verificable", "cuanto paga", "cuánto paga")),
    (SGC_GRUPO_NEGOCIO, "Negociación escalonada", ("3.1", "negociacion escalonada", "negociación escalonada")),
    (SGC_GRUPO_NEGOCIO, "Propuesta de alternativas", ("3.3", "alternativas")),
    (SGC_GRUPO_NEGOCIO, "Orientación a resultado", ("3.5", "compromiso concreto", "resultado")),
    (SGC_GRUPO_USUARIO, "Información de la deuda", ("1.3", "informacion correcta", "información correcta", "deuda")),
    (SGC_GRUPO_USUARIO, "Agilidad / escucha activa", ("2.3", "escucha activa", "agilidad", "interrup")),
    (SGC_GRUPO_USUARIO, "Falta grave para el usuario final", ("falta grave para el usuario",)),
    (SGC_GRUPO_USUARIO, "Claridad de la explicación", ("5.2", "claridad", "explicacion", "explicación")),
    (SGC_GRUPO_USUARIO, "Confusión generada al cliente", ("confusion", "confusión")),
    (SGC_GRUPO_CUMPLIMIENTO, "Ley de protección y defensa del consumidor", ("proteccion", "protección", "defensa del consumidor")),
    (SGC_GRUPO_CUMPLIMIENTO, "Validación de titularidad", ("1.2", "validacion de titularidad", "validación de titularidad", "titularidad")),
    (SGC_GRUPO_CUMPLIMIENTO, "Exposición de deuda a tercero", ("tercero", "exponer deuda", "exposicion de deuda", "exposición de deuda")),
    (SGC_GRUPO_CUMPLIMIENTO, "Información falsa o riesgosa", ("informacion falsa", "información falsa", "riesgosa", "legal")),
    (SGC_GRUPO_CUMPLIMIENTO, "Amenazas, presión indebida o trato abusivo", ("amenaza", "presion indebida", "presión indebida", "trato abusivo", "insulto", "humilla", "carcel", "cárcel")),
    (SGC_GRUPO_CUMPLIMIENTO, "Conducta ética y no abuso", ("5.4", "conducta etica", "conducta ética", "cumplimiento etico", "cumplimiento ético", "no abuso")),
    (SGC_GRUPO_NO_CRITICO, "Identificación del cliente", ("identificacion del cliente", "identificación del cliente")),
    (SGC_GRUPO_NO_CRITICO, "Identificación del gestor", ("1.1", "apertura", "identificacion", "identificación", "gestor")),
    (SGC_GRUPO_NO_CRITICO, "Entonación, dicción y empatía", ("5.1", "5.2", "empatia", "empatía", "diccion", "dicción", "entonacion", "entonación")),
    (SGC_GRUPO_NO_CRITICO, "TMO / ACW", ("tmo", "acw")),
    (SGC_GRUPO_NO_CRITICO, "Lenguaje formal", ("lenguaje formal",)),
    (SGC_GRUPO_NO_CRITICO, "Despedida profesional", ("4.5", "despedida")),
    (SGC_GRUPO_NO_CRITICO, "Actualización de números telefónicos si aplica", ("telefono", "teléfono", "numeros telefonicos", "números telefónicos")),
]

COPC_ITEMS_CANONICOS = [
    ("Cumplimiento", "1.1 Saludo e identificación del agente", 3),
    ("Cumplimiento", "1.2 Identificación de la entidad", 3),
    ("Cumplimiento", "1.3 Validación de titularidad", 4),
    ("Cumplimiento", "1.4 Motivo de llamada y control de información", 5),
    ("Diagnóstico", "2.1 Identificación de la causa", 5),
    ("Diagnóstico", "2.2 Capacidad actual de pago", 4),
    ("Diagnóstico", "2.3 Fecha probable de ingreso", 2),
    ("Diagnóstico", "2.4 Monto disponible", 2),
    ("Diagnóstico", "2.5 Fuente del dinero o situación económica", 2),
    ("Gestión de solución", "3.1 Presentación clara de la propuesta", 6),
    ("Gestión de solución", "3.2 Claridad del beneficio", 4),
    ("Gestión de solución", "3.3 Exploración de capacidad durante la negociación", 5),
    ("Gestión de solución", "3.4 Negociación escalonada", 8),
    ("Gestión de solución", "3.5 Manejo de objeciones", 7),
    ("Gestión de solución", "3.6 Inducción a pago o abono", 5),
    ("Cierre verificable", "4.1 Cantidad", 7),
    ("Cierre verificable", "4.2 Fecha exacta", 7),
    ("Cierre verificable", "4.3 Canal de pago", 5),
    ("Cierre verificable", "4.4 Confirmación expresa", 7),
    ("Cierre verificable", "4.5 Resumen y siguiente acción", 4),
    ("Experiencia y ética", "5.1 Respeto y ausencia de juicio", 2),
    ("Experiencia y ética", "5.2 Empatía y escucha activa", 1),
    ("Experiencia y ética", "5.3 Lenguaje claro y presión profesional", 1),
    ("Experiencia y ética", "5.4 Despedida y cierre profesional", 1),
]


SGC_CODIGO_NEGOCIO = "ERROR_CRITICO_NEGOCIO"
SGC_CODIGO_USUARIO = "ERROR_CRITICO_USUARIO_FINAL"
SGC_CODIGO_CUMPLIMIENTO = "ERROR_CRITICO_CUMPLIMIENTO"
SGC_CODIGO_NO_CRITICO = "ERROR_NO_CRITICO"

SGC_GRUPO_DESDE_CRITICIDAD_PAUTA = {
    "ERROR_CRITICO_NEGOCIO": (SGC_GRUPO_NEGOCIO, SGC_CODIGO_NEGOCIO),
    "ERROR_CRITICO_USUARIO_FINAL": (SGC_GRUPO_USUARIO, SGC_CODIGO_USUARIO),
    "ERROR_CRITICO_CUMPLIMIENTO": (SGC_GRUPO_CUMPLIMIENTO, SGC_CODIGO_CUMPLIMIENTO),
    "ERROR_NO_CRITICO": (SGC_GRUPO_NO_CRITICO, SGC_CODIGO_NO_CRITICO),
}


def catalogo_sgc_desde_pauta(item: Dict) -> Dict:
    """La pauta publicada manda para criterios que no pertenecen al catálogo COPC histórico."""
    criticidad = str((item or {}).get("criticidad") or "").strip().upper()
    grupo, codigo = SGC_GRUPO_DESDE_CRITICIDAD_PAUTA.get(
        criticidad,
        (SGC_GRUPO_NO_CRITICO, SGC_CODIGO_NO_CRITICO),
    )
    return {
        "grupo_error_sgc": grupo,
        "grupo_sgc_codigo": codigo,
        "factor_sgc": str((item or {}).get("nombre") or "Criterio técnico"),
        "severidad_base": "CRITICA" if codigo != SGC_CODIGO_NO_CRITICO else "MEDIA",
        "bloque": (item or {}).get("bloque"),
        "fuente_evidencia": (item or {}).get("fuente_evidencia"),
    }

SGC_CATALOGO = {
    "1.1": {"grupo_sgc_codigo": SGC_CODIGO_NO_CRITICO, "grupo_error_sgc": SGC_GRUPO_NO_CRITICO, "factor_sgc": "Identificación del gestor", "severidad_base": "LEVE"},
    "1.2": {"grupo_sgc_codigo": SGC_CODIGO_NO_CRITICO, "grupo_error_sgc": SGC_GRUPO_NO_CRITICO, "factor_sgc": "Identificación de la entidad", "severidad_base": "LEVE"},
    "1.3": {"grupo_sgc_codigo": SGC_CODIGO_CUMPLIMIENTO, "grupo_error_sgc": SGC_GRUPO_CUMPLIMIENTO, "factor_sgc": "Validación de titularidad", "severidad_base": "CRITICA"},
    "1.4": {"grupo_sgc_codigo": SGC_CODIGO_USUARIO, "grupo_error_sgc": SGC_GRUPO_USUARIO, "factor_sgc": "Información y claridad de la gestión", "severidad_base": "MEDIA"},

    "2.1": {"grupo_sgc_codigo": SGC_CODIGO_NEGOCIO, "grupo_error_sgc": SGC_GRUPO_NEGOCIO, "factor_sgc": "Razón de no pago", "severidad_base": "CRITICA"},
    "2.2": {"grupo_sgc_codigo": SGC_CODIGO_NEGOCIO, "grupo_error_sgc": SGC_GRUPO_NEGOCIO, "factor_sgc": "Capacidad actual de pago", "severidad_base": "CRITICA"},
    "2.3": {"grupo_sgc_codigo": SGC_CODIGO_NEGOCIO, "grupo_error_sgc": SGC_GRUPO_NEGOCIO, "factor_sgc": "Fecha probable de disponibilidad", "severidad_base": "MEDIA"},
    "2.4": {"grupo_sgc_codigo": SGC_CODIGO_NEGOCIO, "grupo_error_sgc": SGC_GRUPO_NEGOCIO, "factor_sgc": "Monto disponible", "severidad_base": "CRITICA"},
    "2.5": {"grupo_sgc_codigo": SGC_CODIGO_NEGOCIO, "grupo_error_sgc": SGC_GRUPO_NEGOCIO, "factor_sgc": "Situación económica", "severidad_base": "MEDIA"},

    "3.1": {"grupo_sgc_codigo": SGC_CODIGO_NO_CRITICO, "grupo_error_sgc": SGC_GRUPO_NO_CRITICO, "factor_sgc": "Presentación y adaptación de la propuesta", "severidad_base": "MEDIA"},
    "3.2": {"grupo_sgc_codigo": SGC_CODIGO_USUARIO, "grupo_error_sgc": SGC_GRUPO_USUARIO, "factor_sgc": "Claridad de montos y condiciones", "severidad_base": "MEDIA"},
    "3.3": {"grupo_sgc_codigo": SGC_CODIGO_NEGOCIO, "grupo_error_sgc": SGC_GRUPO_NEGOCIO, "factor_sgc": "Adaptación a capacidad de pago", "severidad_base": "CRITICA"},
    "3.4": {"grupo_sgc_codigo": SGC_CODIGO_NEGOCIO, "grupo_error_sgc": SGC_GRUPO_NEGOCIO, "factor_sgc": "Negociación escalonada", "severidad_base": "CRITICA"},
    "3.5": {"grupo_sgc_codigo": SGC_CODIGO_NEGOCIO, "grupo_error_sgc": SGC_GRUPO_NEGOCIO, "factor_sgc": "Manejo de objeciones", "severidad_base": "CRITICA"},
    "3.6": {"grupo_sgc_codigo": SGC_CODIGO_NEGOCIO, "grupo_error_sgc": SGC_GRUPO_NEGOCIO, "factor_sgc": "Inducción a pago o abono", "severidad_base": "CRITICA"},

    "4.1": {"grupo_sgc_codigo": SGC_CODIGO_NEGOCIO, "grupo_error_sgc": SGC_GRUPO_NEGOCIO, "factor_sgc": "Cierre verificable 3C/4C", "severidad_base": "CRITICA"},
    "4.2": {"grupo_sgc_codigo": SGC_CODIGO_NEGOCIO, "grupo_error_sgc": SGC_GRUPO_NEGOCIO, "factor_sgc": "Cierre verificable 3C/4C", "severidad_base": "CRITICA"},
    "4.3": {"grupo_sgc_codigo": SGC_CODIGO_NEGOCIO, "grupo_error_sgc": SGC_GRUPO_NEGOCIO, "factor_sgc": "Cierre verificable 3C/4C", "severidad_base": "CRITICA"},
    "4.4": {"grupo_sgc_codigo": SGC_CODIGO_NEGOCIO, "grupo_error_sgc": SGC_GRUPO_NEGOCIO, "factor_sgc": "Cierre verificable 3C/4C", "severidad_base": "CRITICA"},
    "4.5": {"grupo_sgc_codigo": SGC_CODIGO_NEGOCIO, "grupo_error_sgc": SGC_GRUPO_NEGOCIO, "factor_sgc": "Cierre verificable 3C/4C", "severidad_base": "MEDIA"},

    "5.1": {"grupo_sgc_codigo": SGC_CODIGO_USUARIO, "grupo_error_sgc": SGC_GRUPO_USUARIO, "factor_sgc": "Respeto y trato al cliente", "severidad_base": "CRITICA"},
    "5.2": {"grupo_sgc_codigo": SGC_CODIGO_NO_CRITICO, "grupo_error_sgc": SGC_GRUPO_NO_CRITICO, "factor_sgc": "Empatía y escucha activa", "severidad_base": "MEDIA"},
    "5.3": {"grupo_sgc_codigo": SGC_CODIGO_CUMPLIMIENTO, "grupo_error_sgc": SGC_GRUPO_CUMPLIMIENTO, "factor_sgc": "Lenguaje claro y presión profesional", "severidad_base": "CRITICA"},
    "5.4": {"grupo_sgc_codigo": SGC_CODIGO_CUMPLIMIENTO, "grupo_error_sgc": SGC_GRUPO_CUMPLIMIENTO, "factor_sgc": "Conducta ética y no abuso", "severidad_base": "CRITICA"},
}

SGC_MAPEO_CRITERIOS = {
    codigo: (meta["grupo_error_sgc"], meta["factor_sgc"])
    for codigo, meta in SGC_CATALOGO.items()
}

ESTADOS_COPC_V2 = {
    "CUMPLE",
    "PARCIAL_ALTO",
    "PARCIAL_MEDIO",
    "PARCIAL_BAJO",
    "NO_CUMPLE",
    "NO_APLICA",
    "NO_EVALUABLE",
    "REQUIERE_REVISION",
}

ESTADOS_MIBANCO = {
    "CUMPLE",
    "NO_CUMPLE",
    "NO_APLICA",
    "NO_EVALUABLE",
    "REQUIERE_REVISION",
}

FUENTES_OBSERVABLES_AUDIO = {FUENTE_AUDIO, FUENTE_TRANSCRIPCION}


def perfil_puede_editar_prompt(perfil: Optional[str]) -> bool:
    normalizado = str(perfil or "").strip().upper()
    return normalizado in {
        "ADMINISTRADOR",
        "JEFE DE CARTERA",
        "JEFE DE CARTERAS",
        "JEFE DE COBRANZA",
        "JEFE CARTERA",
    }


def obtener_pauta_evaluacion(cartera: Optional[str] = None) -> Optional[List[Dict]]:
    pauta_publicada = criterios_pauta_publicada_para_cartera(cartera)
    if pauta_publicada:
        return pauta_publicada
    if es_cartera_mibanco(cartera):
        return obtener_pauta_mibanco()
    return None


def codigo_criterio_pauta(item: Dict) -> str:
    return str(item.get("codigo_criterio") or item.get("codigo") or "").strip()


def matriz_desde_pauta_mibanco(pauta: List[Dict]) -> List[Dict]:
    matriz = []
    for item in pauta:
        matriz.append({
            "codigo": codigo_criterio_pauta(item),
            "bloque": item.get("bloque"),
            "categoria": item.get("categoria"),
            "subcategoria": item.get("subcategoria"),
            "nombre": item.get("nombre"),
            "peso": item.get("peso"),
            "detalle": item.get("detalle"),
            "regla_evaluacion": item.get("regla_evaluacion"),
            "criticidad": item.get("criticidad"),
            "fuente_evidencia": item.get("fuente_evidencia"),
            "regla_aplicabilidad": item.get("regla_aplicabilidad"),
            "regla_cumple": item.get("regla_cumple"),
            "regla_no_cumple": item.get("regla_no_cumple"),
            "puede_descalificar": bool(item.get("puede_descalificar")),
            "requiere_evidencia": bool(item.get("requiere_evidencia")),
            "tipo_criterio": item.get("tipo_criterio") or "PUNTUABLE",
            "recomendacion": item.get("recomendacion"),
        })
    return matriz


def matriz_tecnica_para_pauta(pauta: Optional[List[Dict]] = None) -> List[Dict]:
    if pauta:
        return matriz_desde_pauta_mibanco(pauta)
    return matriz_tecnica_pipeline_v3()


def fuente_observable_en_audio(fuente: str) -> bool:
    return str(fuente or "").strip().upper() in FUENTES_OBSERVABLES_AUDIO


def ensure_tabla_prompt_config():
    query = text("""
        IF OBJECT_ID('CobAuto.dbo.ia_feedback_prompt_config', 'U') IS NULL
        BEGIN
            CREATE TABLE CobAuto.dbo.ia_feedback_prompt_config (
                id_prompt INT IDENTITY(1,1) PRIMARY KEY,
                clave VARCHAR(50) NOT NULL UNIQUE,
                prompt_base NVARCHAR(MAX) NOT NULL,
                actualizado_por VARCHAR(150) NULL,
                fecha_actualizacion DATETIME DEFAULT GETDATE()
            );
        END
    """)
    with engine_siscob.begin() as conn:
        conn.execute(query)


def clave_prompt(cartera: Optional[str] = None) -> str:
    cartera_limpia = str(cartera or "").strip()
    if cartera_limpia:
        return f"CARTERA::{cartera_limpia[:41]}"
    return "GENERAL"


def obtener_prompt_configuracion(cartera: Optional[str] = None) -> Dict:
    ensure_tabla_prompt_config()
    query = text("""
        SELECT TOP 1 clave, prompt_base, actualizado_por, fecha_actualizacion
        FROM CobAuto.dbo.ia_feedback_prompt_config WITH(NOLOCK)
        WHERE clave IN (:clave_cartera, 'GENERAL')
        ORDER BY CASE WHEN clave = :clave_cartera THEN 0 ELSE 1 END
    """)
    with engine_siscob.connect() as conn:
        row = conn.execute(query, {"clave_cartera": clave_prompt(cartera)}).mappings().first()

    if not row:
        return {
            "cartera": cartera,
            "clave": clave_prompt(cartera),
            "prompt_base": prompt_base_sistema(),
            "prompt_personalizado": None,
            "usa_prompt_personalizado": False,
            "origen_prompt": "SISTEMA",
            "actualizado_por": None,
            "fecha_actualizacion": None,
        }

    return {
        "cartera": cartera,
        "clave": row.get("clave"),
        "prompt_base": row.get("prompt_base") or prompt_base_sistema(),
        "prompt_personalizado": row.get("prompt_base"),
        "usa_prompt_personalizado": True,
        "origen_prompt": "CARTERA" if row.get("clave") == clave_prompt(cartera) and cartera else "GENERAL",
        "actualizado_por": row.get("actualizado_por"),
        "fecha_actualizacion": row.get("fecha_actualizacion").isoformat() if row.get("fecha_actualizacion") else None,
    }


def guardar_prompt_configuracion(
    prompt_base: str,
    actualizado_por: Optional[str],
    perfil: Optional[str],
    cartera: Optional[str] = None,
) -> Dict:
    if not perfil_puede_editar_prompt(perfil):
        raise PermissionError("Solo jefes o administradores pueden modificar el prompt.")

    prompt = str(prompt_base or "").strip()
    if len(prompt) < 500:
        raise ValueError("El prompt debe tener al menos 500 caracteres para conservar la estructura de evaluacion.")

    ensure_tabla_prompt_config()
    query = text("""
        MERGE CobAuto.dbo.ia_feedback_prompt_config AS target
        USING (SELECT :clave AS clave) AS source
        ON target.clave = source.clave
        WHEN MATCHED THEN
            UPDATE SET prompt_base = :prompt_base,
                       actualizado_por = :actualizado_por,
                       fecha_actualizacion = GETDATE()
        WHEN NOT MATCHED THEN
            INSERT (clave, prompt_base, actualizado_por, fecha_actualizacion)
            VALUES (:clave, :prompt_base, :actualizado_por, GETDATE());
    """)
    with engine_siscob.begin() as conn:
        conn.execute(query, {
            "clave": clave_prompt(cartera),
            "prompt_base": prompt,
            "actualizado_por": actualizado_por,
        })
    return obtener_prompt_configuracion(cartera)


def ia_real_configurada() -> bool:
    return bool(os.getenv("OPENAI_API_KEY"))


def prompt_base_sistema() -> str:
    """Contexto mínimo de compatibilidad; la pauta publicada define la evaluación real."""
    return """
Analiza exclusivamente la llamada entregada y responde con JSON válido.

La pauta de monitoreo publicada para la cartera define los criterios, pesos,
aplicabilidad, criticidad y reglas de evidencia. No sustituyas esa pauta por
marcos genéricos, no inventes evidencia y no atribuyas al agente frases del
cliente. Si la fuente requerida no está disponible, indica NO_EVALUABLE; si
la evidencia o el rol es ambiguo para una falta sensible, indica
REQUIERE_REVISION.
""".strip()


def prompt_copc_cobranza_v2() -> str:
    return """
Analiza esta transcripción de llamada de cobranza y devuelve exclusivamente JSON válido.

Marco: COPC adaptado a cobranza telefónica v2. No es una matriz COPC oficial universal.
Evalúa solo conductas observables o razonablemente inferibles. No inventes hechos, citas ni timestamps.
AISLAMIENTO OBLIGATORIO ENTRE EVALUACIONES:
- Analiza exclusivamente la transcripción incluida en este prompt.
- Ignora cualquier llamada, ejemplo, evidencia, fecha, monto, frase, hallazgo o conclusión de evaluaciones anteriores.
- Toda evidencia textual debe existir literalmente o de forma claramente equivalente en esta transcripción.
- Si un dato no aparece en esta llamada, devuelve null, lista vacía, NO_EVALUABLE o REQUIERE_REVISION según corresponda.
- Está prohibido completar información faltante usando patrones de llamadas anteriores.
- Antes de devolver un hallazgo, valida que la evidencia pertenece a esta transcripción y no a otro caso.

REGLA FUNDAMENTAL DE EVALUACION:
- No marques automáticamente NO_CUMPLE porque una frase exacta no aparezca.
- CUMPLE: la conducta requerida se observa suficientemente.
- PARCIAL: la conducta se realiza, pero queda incompleta.
- NO_CUMPLE: existía una oportunidad clara de ejecutar la conducta y el agente no lo hizo o lo hizo incorrectamente.
- NO_EVALUABLE: el desarrollo de la llamada no generó una oportunidad razonable para ejecutar el criterio.
- REQUIERE_REVISION: existe evidencia ambigua o insuficiente para decidir responsablemente.
- No uses NO_CUMPLE como sustituto de "no encontré evidencia".
- No confundas contexto del cliente con error del agente: evalúa lo que hace el agente después de la objeción.
- Evalúa independientemente los cinco componentes del cierre verificable; no agrupes automáticamente cantidad, fecha, canal, confirmación y resumen como cero.
- No generes hallazgos artificiales para llenar grupos SGC vacíos.

Estados permitidos por criterio:
CUMPLE, PARCIAL_ALTO, PARCIAL_MEDIO, PARCIAL_BAJO, NO_CUMPLE, NO_EVALUABLE, REQUIERE_REVISION.

Reglas centrales:
- La ausencia de evidencia no significa automáticamente NO_CUMPLE. Usa NO_EVALUABLE o REQUIERE_REVISION y explica motivo.
- Si no hay diarización, infiere AGENTE, CLIENTE o NO_DETERMINADO por fragmento con confianza. No fuerces una asignación ambigua.
- Devuelve interlocutores.segmentos siempre que la transcripción permita separar turnos de habla. Cada segmento debe traer:
  hablante AGENTE, CLIENTE o NO_DETERMINADO; texto literal; timestamp null si no existe; confianza ALTA, MEDIA o BAJA;
  fundamento breve de por qué asignaste ese hablante. Si la separación es demasiado ambigua, usa NO_DETERMINADO.
- No dejes interlocutores.segmentos vacío cuando hay turnos evidentes por preguntas/respuestas, saludos del gestor,
  frases de cobranza del agente o respuestas del cliente. Divide en fragmentos cortos y conserva toda la llamada.
- La nota mínima aprobatoria es 85.
- Conserva score_tecnico sobre 100 aunque exista descalificación.
- Nunca conviertas automáticamente el score_tecnico a cero por error crítico.
- La descalificación es independiente del score técnico.
- No evalúes "Tipificación correcta"; devuelve dos tipificaciones sugeridas sin impacto en score.
- Si no hay timestamps, usa null. No inventes timestamps.
- La evidencia de una falta anulante debe ser una cita textual exacta de la transcripción, no una categoría.
- Si detectas humillación o maltrato psicológico explícito, crea un error crítico automático en el grupo
  "Errores críticos del usuario final" con factor "Falta grave al usuario final / Maltrato psicológico".

- La validación de titularidad CUMPLE si el agente pregunta por la persona y el interlocutor confirma directa
  o indirectamente ser ella. No exijas DNI ni validación adicional.
- Gestión de solución y Cierre verificable aplican cuando hubo contacto y oportunidad real de negociar, aunque no
  haya acuerdo. No los marques NO_EVALUABLE por falta de compromiso; puntúa bajo, cero o REQUIERE_REVISION.
- Si no tienes cita textual exacta para sustentar un incumplimiento, usa REQUIERE_REVISION, no inventes evidencia.
- Separa presión legal ambigua como error crítico de cumplimiento sujeto a calibración: REQUIERE_REVISION,
  no falta anulante automática.

Reglas de calidad analitica para hallazgos:
- Cada hallazgo debe ser especifico, equilibrado y accionable. No devuelvas etiquetas sueltas como
  "No cumple cierre", "Falta de empatia" o "No presento propuesta".
- Para cada criterio con PARCIAL, NO_CUMPLE o REQUIERE_REVISION explica:
  1) que si hizo el agente, 2) donde perdio la oportunidad, 3) cita textual exacta,
  4) lectura de negocio, 5) impacto en recupero/cierre, 6) impacto en cliente,
  7) conducta concreta esperada y 8) frase alternativa sugerida.
- Diferencia ausencia total de conducta vs conducta parcial. Si el agente ofrecio fraccionamiento,
  no digas "No presento propuesta"; di que presento una alternativa pero no la desarrollo ni la adapto.
- Reconoce fortalezas relacionadas cuando existan. Las fortalezas no eliminan la brecha, pero deben aparecer
  en resumen ejecutivo, feedback supervisor y feedback asesor.
- Todo NO_CUMPLE debe tener evidencia_textual literal. Si no hay cita, usa REQUIERE_REVISION.
- No uses textos genericos como "No evidenciado en la respuesta IA" o "Revisar transcripcion" como evidencia.
- No conviertas ambiguedad en incumplimiento confirmado.
- Si existe objecion economica, evalua si el agente reconoce, indaga, adapta, busca monto, busca fecha e intenta cerrar.
- Si existe una advertencia o escalamiento ambiguo, clasificalo como REQUIERE_REVISION por dependencia de discurso autorizado, no como descalificacion automatica.

Matriz COPC v2, total 100:

D1. Cumplimiento y control de contacto, 15 puntos:
1.1 Saludo e identificación del agente, 3. Saluda e indica su nombre. Cumple 3, parcial 1.5, no cumple 0.
1.2 Identificación de la entidad, 3. Menciona banco o entidad. Cumple 3, parcial 1.5, no cumple 0.
1.3 Validación de titularidad, 4. Basta que pregunte por la persona y el interlocutor confirme directa o indirectamente:
"sí", "soy yo", "ella habla", "con ella", "dígame", "sí señor" o respuesta contextual inequívoca.
No exige DNI, fecha de nacimiento ni validación adicional. Cumple 4, parcial/ambiguo 2, no cumple 0, requiere revisión si no se puede inferir.
No validar no descalifica automáticamente; descalifica solo si se revela deuda a tercero confirmado.
1.4 Motivo de llamada y control de información, 5. Explica motivo y evita información falsa, contradictoria o revelada antes de validar.
Cumple 5, parcial alto 3.75, parcial medio 2.5, parcial bajo 1.25, no cumple 0.

D2. Diagnóstico, 15 puntos:
2.1 Identificación de la causa, 5. Identifica por qué dejó de pagar. Si cliente lo explica espontáneamente, puntúa si agente escucha y usa la información.
2.2 Capacidad actual de pago, 4. Determina si puede pagar o abonar ahora o en fecha cercana.
2.3 Fecha probable de ingreso, 2. Determina cuándo podría disponer de dinero. "El otro mes", "después" o "cuando pueda" no son suficientes.
2.4 Monto disponible, 2. Busca cuánto podría pagar o abonar. No hay monto mínimo obligatorio.
2.5 Fuente del dinero o situación económica, 2. Identifica fuente posible o ausencia de ingresos sin interrogatorio invasivo.

D3. Gestión de solución y negociación, 35 puntos:
3.1 Presentación clara de la propuesta, 6. Diferencia deuda total, campaña, cuota, abono, fraccionamiento, fecha límite cuando corresponda.
3.2 Claridad del beneficio, 4. Explica por qué conviene pagar/abonar: reducir deuda, evitar incremento, campaña, regularización o avance real a otra instancia.
3.3 Exploración de capacidad durante la negociación, 5. Usa diagnóstico para adaptar propuesta. No dupliques automáticamente el diagnóstico.
3.4 Negociación escalonada, 8. Escalera: cancelación total, campaña, abono/fraccionamiento, fecha próxima con monto concreto. No exige todas si cliente acepta una inicial.
3.5 Manejo de objeciones, 7. Escucha, responde profesionalmente y reconduce a solución.
3.6 Inducción a pago o abono, 5. Intenta obtener pago, abono, monto concreto o fecha concreta.
Regla mes vigente: si cliente dice próximo mes, el agente debe intentar primero orientar pago/abono dentro del mes vigente y explicar que condiciones pueden cambiar.

D4. Cierre verificable, 30 puntos. Cierre 4C: Cantidad, Cuándo, Canal, Confirmación.
4.1 Cantidad, 7. Monto exacto confirmado 7; mencionado sin reconfirmar 5.25; rango 3.5; "un abono" 1.75; sin monto 0.
4.2 Fecha exacta, 7. Fecha exacta 7; referencia cercana clara 5.25; fecha amplia 3.5; "el otro mes" 1.75; sin fecha 0.
4.3 Canal de pago, 5. Canal definido y confirmado 5; mencionado 3.75; canales generales 2.5; ambiguo 1.25; sin canal 0.
4.4 Confirmación expresa, 7. Aceptación clara 7; reserva menor 5.25; ambigua 3.5; intención general 1.75; rechazo/silencio 0.
4.5 Resumen y siguiente acción, 4. Resume monto, fecha, canal y siguiente acción 4; omite menor 3; solo monto/fecha 2; general 1; sin resumen 0.
Tipos de cierre permitidos: PAGO_INMEDIATO_CONFIRMADO, PROMESA_VERIFICABLE, PROMESA_PARCIAL, INTENCION_NO_VERIFICABLE, SEGUIMIENTO_ACORDADO, SIN_COMPROMISO, LLAMADA_INTERRUMPIDA.

D5. Experiencia y ética, 5 puntos:
5.1 Respeto y ausencia de juicio, 2. Cumple 2, parcial 1, no cumple 0.
5.2 Empatía y escucha activa, 1. Cumple 1, parcial 0.5, no cumple 0.
5.3 Lenguaje claro y presión profesional, 1. Cumple 1, parcial 0.5, no cumple 0.
5.4 Despedida y cierre profesional, 1. Cumple 1, parcial 0.5, no cumple 0.

Errores críticos automáticos, descalifican manteniendo score técnico:
insulto directo, humillación, maltrato psicológico explícito, discriminación, amenaza falsa grave,
revelación de deuda a tercero confirmado, suplantación o identificación falsa, burla sobre salud/desempleo/problema familiar,
manipulación deliberada con información falsa.
Ejemplo: "Todo lo que dice son pretextos" puede ser maltrato psicológico descalificante si el contexto confirma desacreditación.

Errores críticos sujetos a calibración:
presión excesiva, interrupciones constantes, sarcasmo dudoso, advertencia legal ambigua, comentario poco empático,
tono confrontacional, corte abrupto, frase culpabilizante moderada, información imprecisa posiblemente involuntaria.
Clasifícalos como CRITICO_CONDICIONADO y REQUIERE_REVISION; no descalifiques automáticamente.

Tipificación sugerida:
Devuelve dos tipificaciones sugeridas, principal y alternativa, sin código y sin impacto en score.
Ejemplos: dificultad de pago - problema financiero, problema personal, salud, desempleo, dificultad de negocio,
renuente, reclamo, niega deuda, rechazo de pago, posposición sin fecha, promesa total, promesa parcial,
pago realizado, seguimiento de solución de pago.

JSON mínimo obligatorio:
{
  "version_evaluacion": "2.0",
  "resultado_evaluacion": {
    "score_tecnico": 0,
    "score_maximo": 100,
    "nota_minima_aprobatoria": 85,
    "estado_tecnico": "",
    "estado_calidad": "",
    "descalificada": false,
    "motivo_descalificacion": null,
    "confianza_global": "",
    "evaluacion_provisional": false,
    "requiere_revision_humana": false,
    "motivos_revision": []
  },
  "resultado_gestion": {
    "tipo_contacto": "",
    "resultado_principal": "",
    "tipo_cierre": "",
    "monto_acordado": null,
    "fecha_acordada": null,
    "canal_acordado": null,
    "confirmacion_cliente": false,
    "resumen": ""
  },
  "tipificaciones_sugeridas": [
    {"orden": 1, "categoria": "", "tipificacion": "", "descripcion": "", "confianza_porcentaje": 0, "justificacion": "", "impacta_score": false},
    {"orden": 2, "categoria": "", "tipificacion": "", "descripcion": "", "confianza_porcentaje": 0, "justificacion": "", "impacta_score": false}
  ],
  "resumen_ejecutivo": {
    "texto": "",
    "fortaleza_principal": "",
    "debilidad_principal": "",
    "riesgo_principal": "",
    "oportunidad_principal": "",
    "conclusion": ""
  },
  "interlocutores": {
    "confianza_global": "",
    "metodo": "INFERIDO_DESDE_TRANSCRIPCION | DIARIZACION_ORIGINAL | NO_DISPONIBLE",
    "segmentos": [
      {
        "orden": 1,
        "timestamp": null,
        "inicio_segundos": null,
        "fin_segundos": null,
        "hablante": "AGENTE | CLIENTE | NO_DETERMINADO",
        "texto": "",
        "confianza": "ALTA | MEDIA | BAJA",
        "fundamento": ""
      }
    ]
  },
  "dimensiones": [],
  "errores_criticos": [],
  "hallazgos_no_criticos": [],
  "frases_detectadas": {"adecuadas": [], "mejorables": [], "riesgo": []},
  "coaching": {
    "feedback_supervisor": {
      "resumen_tecnico": "",
      "fortalezas": [],
      "brechas_principales": [],
      "conducta_prioritaria": "",
      "accion_entrenable": "",
      "objetivo_siguiente_llamada": ""
    },
    "feedback_asesor": {
      "mensaje": "",
      "lo_que_hiciste_bien": "",
      "mejora_prioritaria": "",
      "frase_a_evitar": "",
      "frase_recomendada": "",
      "ejemplo_mejorado": "",
      "compromiso_sugerido": ""
    }
  },
  "validaciones": {"suma_dimensiones_correcta": true, "score_dentro_de_rango": true, "observaciones": []}
}

Cada criterio dentro de dimensiones debe incluir:
codigo, nombre, puntaje_maximo, puntaje_obtenido, estado, conducta_esperada, evidencias,
hallazgo, impacto, recomendacion, gravedad, puede_descalificar, confianza, requiere_revision, motivo_no_evaluable.
Ademas, cada criterio debe incluir estos campos enriquecidos:
codigo_criterio, factor, grupo_sgc, calificacion, evidencia_textual, conducta_observada, lectura_ia,
impacto_negocio, impacto_cliente, recomendacion_entrenable, frase_sugerida, fortaleza_relacionada.
Reglas:
- evidencia_textual es una lista de citas literales de la transcripcion.
- conducta_observada describe que ocurrio, incluyendo fortalezas parciales.
- lectura_ia explica que significa la conducta para cobranza.
- hallazgo resume la brecha sin negar lo que el agente si hizo.
- impacto_negocio conecta con pago, abono, compromiso, recupero o cierre.
- impacto_cliente conecta con claridad, confianza o experiencia.
- recomendacion_entrenable debe ser una accion concreta para la siguiente llamada.
- frase_sugerida debe ser una frase lista para usar o entrenar.
- fortaleza_relacionada reconoce algo bien ejecutado cuando exista.
Incluye siempre los 24 criterios de la matriz. Si un criterio no puede evaluarse, inclúyelo con estado
NO_EVALUABLE o REQUIERE_REVISION, puntaje_obtenido null, motivo_no_evaluable claro y evidencia vacía.

No asignes grupo_error_sgc, grupo_sgc, factor_sgc ni severidad_base. El sistema los resuelve
de forma determinística desde el catálogo interno por codigo_criterio.
""".strip()


def prompt_copc_cobranza() -> str:
    return """
Analiza esta transcripcion de llamada de cobranza y devuelve exclusivamente un JSON valido.

Marco de evaluacion: COPC adaptado a cobranza telefonica, homologado con el modelo SGC/PEC interno.
El objetivo es evaluar calidad de gestion, cumplimiento del proceso, experiencia del cliente
y efectividad de cobranza. La calidad no debe verse como "hablar bonito"; debe relacionarse
con contacto efectivo, diagnostico, negociacion, cierre verificable y trato adecuado.
No presentes los items como matriz COPC oficial universal. Evalua bajo un marco COPC adaptado
al proceso de cobranza telefonica.

Principios COPC aplicados:
- Evaluar solo conductas observables en la llamada.
- Diferenciar errores criticos de oportunidades de mejora.
- Conectar calidad con resultado de negocio: contacto, promesa, cierre 3C y recupero.
- Usar criterios consistentes para calibracion entre supervisores.
- El feedback debe ser accionable, especifico y entrenable.

Matriz operativa COPC Cobranza 100 puntos:

1. Cumplimiento y control de contacto 15 puntos:
  - 1.1 Apertura e identificacion: 4 puntos. Saluda, se identifica y comunica empresa/motivo.
  - 1.2 Validacion de titularidad y datos: 5 puntos. Verifica identidad antes de exponer deuda.
    Cuenta como validacion si el asesor pregunta por titularidad o identidad con frases naturales como
    "hablo con la titular", "usted es la titular", "es la tt/titular" y el cliente confirma afirmativamente.
    Evalua siempre la secuencia antes/despues:
    * Cumple: la persona confirma ser titular o autorizada antes de que el asesor exponga monto, deuda,
      mora, descuento, producto o consecuencia de cobranza.
    * Parcial: la confirmacion es contextual o debil, por ejemplo el asesor pregunta por una segunda persona
      y la interlocutora confirma ser ella, pero no hay validacion reforzada de dato adicional. No lo marques
      como "No cumple" si no se expuso deuda antes de esa confirmacion.
    * No cumple: el asesor expone deuda antes de confirmar titularidad, la persona niega ser titular,
      indica que el titular no esta, o se entrega informacion de deuda a conyuge/tercero no autorizado.
    * No aplica: la llamada no expone deuda ni datos sensibles y solo deja mensaje general o contacto.
    Si existe duda entre titular, conyuge o tercero, conserva el resultado mas prudente y marca
    revision_humana=true con evidencia textual y momento.
  - 1.3 Informacion correcta de deuda/gestion: 4 puntos. Explica deuda, producto, PDP o situacion sin confundir.
  - 1.4 Registro y trazabilidad verbal: 2 puntos. Deja claro el motivo o siguiente paso.

2. Diagnostico y escucha 15 puntos:
  - 2.1 Identificacion de causa raiz / motivo de atraso: 5 puntos.
  - 2.2 Diagnostico de capacidad de pago: 5 puntos.
  - 2.3 Escucha activa y control de la interaccion: 3 puntos.
  - 2.4 Confirmacion de comprension del cliente: 2 puntos.

3. Negociacion de cobranza 30 puntos:
  - 3.1 Negociacion escalonada: 10 puntos. Inicia por deuda total o importe alto, luego capital,
    y deja descuento/campana como ultima alternativa. No debe partir por el monto mas bajo.
  - 3.2 Gestion de objeciones del cliente: 7 puntos. Reconoce la objecion, indaga causa y responde sin confrontar.
  - 3.3 Propuesta de alternativas viables: 5 puntos. Ofrece opciones segun capacidad y politica.
  - 3.4 Argumentacion de beneficios y consecuencias: 4 puntos. Explica beneficios de pagar y consecuencias reales
    sin amenazas ni informacion falsa.
  - 3.5 Orientacion a resultado: 4 puntos. Busca compromiso concreto, no solo informar.

4. Cierre y compromiso 25 puntos:
  - 4.1 Cierre verificable 3C/4C: 10 puntos. Confirma cuanto paga, donde paga y como pagara.
  - 4.2 Fecha/hora o plazo verificable: 5 puntos. El compromiso debe tener fecha clara.
  - 4.3 Confirmacion y recapitulacion: 5 puntos. Repite acuerdo y valida aceptacion del cliente.
  - 4.4 Plan de seguimiento ante incumplimiento: 3 puntos. Define seguimiento o alternativa.
  - 4.5 Despedida profesional: 2 puntos.

5. Experiencia, conducta y riesgo critico (Filosofia Biznescob) 15 puntos:
  - 5.1 Tono profesional y empatico: 4 puntos.
  - 5.2 Lenguaje claro, diccion y orden: 3 puntos.
  - 5.3 Manejo emocional de la llamada: 3 puntos. No interrumpe, no ridiculiza, no escala conflicto.
  - 5.4 Conducta etica y no abuso: 5 puntos. No usa insultos, sarcasmo, humillacion, amenazas,
    presion indebida, informacion falsa ni frases fuera de lugar.
  Este segmento representa la Filosofia Biznescob: cobranza firme, responsable, respetuosa y orientada
  a solucionar sin maltrato ni presion indebida.

Errores criticos COPC Cobranza:
- Amenazas o intimidacion: "te vas a ir a la carcel", "debes ir presa", similares.
- Insultos, lenguaje ofensivo o despectivo: "conchuda" u otros agravios.
- Exponer deuda a tercero sin validacion de titularidad.
- Dar informacion falsa, legalmente riesgosa o no verificable.
- Presion indebida, humillacion, burla o sarcasmo.
- Compromiso inventado o cierre no aceptado por el cliente.

Capa SGC/PEC para reportería gerencial:
- Mantén la matriz operativa COPC Cobranza como base de evaluación de la llamada.
- No clasifiques grupo_error_sgc, factor_sgc ni severidad_base. El sistema traduce cada código
  técnico a SGC/PEC mediante catálogo interno determinístico.

Faltas anulantes automaticas:
- Si el asesor insulta, amenaza, humilla, discrimina, expone deuda a un tercero sin validar,
  inventa una consecuencia legal grave o usa presion abusiva, la llamada debe calificarse con
  score_calidad = 0 aunque otros items parezcan correctos.
- En una falta anulante debes indicar la frase textual exacta o lo mas literal posible, y el minuto/segundo
  donde se detecto si la transcripcion trae marcas de tiempo. Si no hay marca de tiempo, usa "No disponible".
- Otras faltas pueden ser "GRAVE", "MEDIA" o "LEVE" segun impacto, siempre con evidencia.

Reglas de scoring:
- Si la transcripcion no evidencia un punto, usa resultado "No evidenciado" y nota 0.
- La nota de cada item debe estar entre 0 y su peso maximo.
- La evaluacion_calidad debe incluir obligatoriamente los 22 items de la matriz COPC Cobranza.
- La suma de notas es el score_calidad final sobre 100.
- Si hay error critico, el item 5.4 debe ser 0, nivel_oportunidad_mejora debe ser "ALTA",
  debe existir una alerta explicita y debe aparecer en puntos_criticos.
- Si hay falta anulante, todo score_calidad debe ser 0, falta_anulante debe ser true y
  nivel_oportunidad_mejora debe ser "ALTA".
- Una llamada cordial sin negociacion ni cierre verificable no puede tener nota alta.
- Una llamada con promesa de pago sin 3C completa no debe calificarse como cierre robusto.
- Primero identifica el objetivo de la llamada. Si la llamada es de confirmacion o seguimiento de PDP/pago
  ya pactado, no castigues al agente por no explicar toda la deuda ni por no hacer negociacion escalonada
  desde cero. En esos casos evalua si confirma el acuerdo previo, monto, fecha, canal, estado del pago,
  motivo de incumplimiento si aplica y siguiente accion.
- Para llamadas de confirmacion de PDP, el item 1.3 puede cumplir con una explicacion breve del contexto
  de pago/promesa, y los items de negociacion deben evaluarse segun pertinencia del seguimiento, no como
  una venta inicial de alternativas.
- Basa cada hallazgo en evidencia breve de la llamada; no inventes hechos.
- Para validacion de titularidad, cita la frase exacta o aproximada donde el cliente confirma o niega identidad.
  Si marcas "No cumple", explica si la deuda fue expuesta antes de validar o si la persona era tercero/no autorizada.
- El resumen debe mencionar objetivo, cliente/contexto si existe, resultado y riesgo principal.
- La recomendacion debe servir para coaching del agente.
- Incluye maximo 4 fortalezas, maximo 5 puntos criticos y maximo 4 alertas.
- Reglas feedback/coaching:
  * Si hay error crítico de cumplimiento, requiere_feedback=true y requiere_coaching=true.
  * Si hay falta anulante, requiere_coaching=true.
  * Si score_final < 80, requiere_feedback=true.
  * Si score_final < 70 o nivel_riesgo=ALTO, requiere_coaching=true.
  * Si el error es no crítico aislado, requiere_feedback=true y requiere_coaching puede ser false.
  * No marques todos los factores como coaching. El coaching es un plan estructurado para falta anulante,
    error crítico de cumplimiento, score_final < 70, nivel_riesgo=ALTO, reincidencia o definicion manual del supervisor.

Segmentos permitidos para puntos criticos:
- Cumplimiento
- Diagnostico
- Negociacion
- Cierre
- Experiencia y riesgo

Estructura exacta requerida:
{
  "resumen": "texto breve",
  "clasificacion_copc": {
    "tipo_llamada": "Cobranza inicial | Seguimiento PDP | Confirmacion de pago | Recordatorio | Informativa | No evaluable | Otro",
    "evaluabilidad": "EVALUABLE | PARCIALMENTE_EVALUABLE | NO_EVALUABLE",
    "motivo_no_evaluable": "texto o No aplica",
    "objetivo_principal": "objetivo operativo de la llamada"
  },
  "tipo_contacto": "Contacto efectivo | Contacto no efectivo | Tercero | Buzon | Cortada | Otro",
  "resultado_gestion": "Compromiso confirmado | Compromiso pendiente | Sin compromiso | Informativo | Otro",
  "objecion_principal": "texto o No evidenciada",
  "resultado_final": {
    "score_bruto": 0,
    "peso_aplicable": 100,
    "score_normalizado": 0,
    "score_final": 0,
    "estado": "Excelente | Aprobado | Con observacion | No aprobado",
    "nivel_riesgo": "BAJO | MEDIO | ALTO"
  },
  "calidad_transcripcion": {
    "nivel": "ALTA | MEDIA | BAJA",
    "confianza": "ALTA | MEDIA | BAJA",
    "requiere_revision_humana": false,
    "motivo": "texto o No aplica"
  },
  "calibracion": {
    "confianza_evaluacion": "ALTA | MEDIA | BAJA",
    "requiere_revision_humana": false,
    "motivo_revision": "texto o No aplica"
  },
  "evaluacion_calidad": [
    {
      "segmento": "Cumplimiento | Diagnostico | Negociacion | Cierre | Experiencia y riesgo",
      "item": "1.1 Apertura e identificacion",
      "peso": 4,
      "nota": 0,
      "nota_ia": 0,
      "nota_supervisor": null,
      "nota_final": 0,
      "aplica": true,
      "motivo_no_aplica": "texto o No aplica",
      "resultado": "Cumple | Parcial | No cumple | No evidenciado",
      "segmento_copc": "Cumplimiento | Diagnostico | Negociacion | Cierre | Experiencia y riesgo",
      "calificacion": "Cumple | No cumple | No aplica | Parcial",
      "motivo": "motivo para feedback o coaching",
      "hallazgo": "texto",
      "evidencia": "referencia breve de la llamada",
      "momento": "mm:ss o No disponible",
      "recomendacion": "texto",
      "requiere_feedback": false,
      "requiere_coaching": false,
      "motivo_feedback_coaching": "texto o No aplica"
    }
  ],
  "resumen_sgc": {
    "errores_criticos_negocio": 0,
    "errores_criticos_usuario_final": 0,
    "errores_criticos_cumplimiento": 0,
    "errores_no_criticos": 0,
    "requiere_feedback": true,
    "requiere_coaching": false,
    "motivo": "texto"
  },
  "habilidades_blandas": [
    {
      "habilidad": "Actitud conciliadora | Empatia | Escucha activa | Vocalizacion y claridad | Manejo emocional",
      "nivel": "Alto | Medio | Bajo",
      "evidencia": "referencia breve",
      "recomendacion": "texto"
    }
  ],
  "fortalezas_agente": ["texto"],
  "puntos_criticos": [
    {
      "segmento": "Cumplimiento | Diagnostico | Negociacion | Cierre | Experiencia y riesgo",
      "categoria": "texto",
      "severidad": "ANULANTE | GRAVE | MEDIA | LEVE",
      "hallazgo": "texto",
      "frase_textual": "frase del asesor o No disponible",
      "momento": "mm:ss o No disponible",
      "evidencia": "referencia breve de la llamada",
      "impacto": "texto",
      "recomendacion": "texto"
    }
  ],
  "evidencias_clave": [
    {
      "tipo": "Validacion | Negociacion | Cierre | Riesgo | Fortaleza",
      "momento": "mm:ss o No disponible",
      "frase_textual": "frase breve o No disponible",
      "interpretacion": "por que importa para la evaluacion"
    }
  ],
  "recomendacion_feedback_supervisor": "texto accionable",
  "guion_sugerido": "texto breve que el agente podria usar",
  "alertas": ["texto"],
  "falta_anulante": false,
  "frase_anulante": "frase textual o No aplica",
  "momento_falta_anulante": "mm:ss o No aplica",
  "nivel_oportunidad_mejora": "BAJA | MEDIA | ALTA"
}
""".strip()


def transcribir_audio_real(ruta_audio: str) -> str:
    if not ia_real_configurada():
        raise RuntimeError("OPENAI_API_KEY no configurada.")
    if OpenAI is None:
        raise RuntimeError("La libreria openai no esta instalada en el entorno.")

    ruta = Path(ruta_audio)
    if not ruta.exists():
        raise RuntimeError("No se encontro el archivo de audio para transcribir.")

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    with ruta.open("rb") as audio_file:
        try:
            result = client.audio.transcriptions.create(
                model=TRANSCRIPTION_MODEL,
                file=audio_file,
                response_format="diarized_json",
                chunking_strategy="auto",
            )
            diarizada = normalizar_transcripcion_diarizada(result)
            if diarizada.get("segmentos"):
                diarizada["speaker_role_mapping"] = asignar_roles_speakers(client, diarizada["segmentos"])
                return construir_texto_diarizado_canonico(diarizada)
        except Exception:
            audio_file.seek(0)
            try:
                result = client.audio.transcriptions.create(
                    model=TRANSCRIPTION_FALLBACK_MODEL,
                    file=audio_file,
                    response_format="verbose_json",
                    timestamp_granularities=["segment"],
                )
            except Exception:
                audio_file.seek(0)
                result = client.audio.transcriptions.create(
                    model=TRANSCRIPTION_FALLBACK_MODEL,
                    file=audio_file,
                )

    text = getattr(result, "text", None)
    if not text and isinstance(result, dict):
        text = result.get("text")

    segments = getattr(result, "segments", None)
    if segments is None and isinstance(result, dict):
        segments = result.get("segments")
    texto_segmentado = construir_texto_con_timestamps(segments)
    if texto_segmentado:
        return texto_segmentado

    if not text:
        raise RuntimeError("La transcripcion no devolvio texto.")
    return text.strip()


def normalizar_transcripcion_diarizada(result) -> Dict:
    data = result
    if not isinstance(data, dict):
        try:
            data = result.model_dump()
        except Exception:
            data = {k: getattr(result, k, None) for k in ("text", "segments", "words")}

    texto = str(data.get("text") or data.get("texto") or "").strip()
    raw_segments = (
        data.get("segments")
        or data.get("segmentos")
        or data.get("speaker_segments")
        or data.get("utterances")
        or []
    )
    segmentos = []
    for raw in raw_segments if isinstance(raw_segments, list) else []:
        if not isinstance(raw, dict):
            try:
                raw = raw.model_dump()
            except Exception:
                raw = {
                    "text": getattr(raw, "text", None),
                    "start": getattr(raw, "start", None),
                    "end": getattr(raw, "end", None),
                    "speaker": getattr(raw, "speaker", None),
                }
        texto_segmento = str(
            raw.get("text")
            or raw.get("texto")
            or raw.get("transcript")
            or raw.get("content")
            or ""
        ).strip()
        if not texto_segmento:
            continue
        inicio = raw.get("start", raw.get("inicio_segundos", raw.get("start_time")))
        fin = raw.get("end", raw.get("fin_segundos", raw.get("end_time")))
        speaker = str(
            raw.get("speaker")
            or raw.get("speaker_id")
            or raw.get("speaker_label")
            or raw.get("speaker_original")
            or ""
        ).strip()
        segmentos.append({
            "segmento_id": len(segmentos) + 1,
            "speaker_original": speaker or "speaker_unknown",
            "rol": None,
            "inicio_segundos": normalizar_segundos_v2(inicio),
            "fin_segundos": normalizar_segundos_v2(fin),
            "timestamp": formatear_timestamp(inicio),
            "texto_original": texto_segmento,
            "texto_limpio": None,
            "texto": texto_segmento,
        })
    segmentos.sort(key=lambda item: (item.get("inicio_segundos") is None, item.get("inicio_segundos") or 0, item.get("segmento_id") or 0))
    for idx, segmento in enumerate(segmentos, start=1):
        segmento["segmento_id"] = idx
    if not texto and segmentos:
        texto = " ".join(item["texto_original"] for item in segmentos).strip()
    return {"texto_completo": texto, "segmentos": segmentos}


def construir_texto_diarizado_canonico(diarizada: Dict) -> str:
    lineas = ["#TRANSCRIPCION_DIARIZADA_V1"]
    texto_completo = str(diarizada.get("texto_completo") or "").strip()
    if texto_completo:
        lineas.append(f"#TEXTO_COMPLETO {texto_completo}")
    segmentos = sorted(
        [item for item in (diarizada.get("segmentos") or []) if isinstance(item, dict)],
        key=lambda item: (item.get("inicio_segundos") is None, item.get("inicio_segundos") or 0, item.get("segmento_id") or 0),
    )
    speakers = {
        str(item.get("speaker_original")): normalizar_hablante_v2(item.get("rol"))
        for item in segmentos
        if item.get("speaker_original")
    }
    if speakers:
        lineas.append(f"#SPEAKERS {json.dumps(speakers, ensure_ascii=False, sort_keys=True)}")
    if isinstance(diarizada.get("speaker_role_mapping"), dict):
        lineas.append(f"#SPEAKER_ROLE_MAPPING {json.dumps(diarizada.get('speaker_role_mapping'), ensure_ascii=False, sort_keys=True)}")
    integridad = validar_integridad_diarizacion(segmentos, len(segmentos))
    lineas.append(f"#INTEGRIDAD {json.dumps(integridad, ensure_ascii=False, sort_keys=True)}")
    for segmento in segmentos:
        texto = str(segmento.get("texto_original") or segmento.get("texto") or "").replace("\n", " ").strip()
        if not texto:
            continue
        speaker = str(segmento.get("speaker_original") or "speaker_unknown").strip()
        rol = normalizar_hablante_v2(segmento.get("rol")) if segmento.get("rol") else "NO_DETERMINADO"
        timestamp = segmento.get("timestamp") or formatear_timestamp(segmento.get("inicio_segundos"))
        inicio = segmento.get("inicio_segundos")
        fin = segmento.get("fin_segundos")
        inicio_txt = "" if inicio is None else str(round(float(inicio), 3))
        fin_txt = "" if fin is None else str(round(float(fin), 3))
        lineas.append(f"[{timestamp}] {{{speaker}}} <{rol}> ({inicio_txt}-{fin_txt}) {texto}")
    return "\n".join(lineas).strip()


def validar_integridad_diarizacion(segmentos: List[Dict], cantidad_original: Optional[int] = None) -> Dict:
    ids = []
    segmentos_reordenados = 0
    speaker_modificados = 0
    prev_inicio = None
    segmentos_invalidos = 0
    speakers_originales = {}
    roles_por_speaker = {}
    for idx, segmento in enumerate(segmentos):
        ids.append(segmento.get("segmento_id"))
        inicio = segmento.get("inicio_segundos")
        fin = segmento.get("fin_segundos")
        if prev_inicio is not None and inicio is not None and inicio < prev_inicio:
            segmentos_reordenados += 1
        if inicio is not None:
            prev_inicio = inicio
        if inicio is not None and fin is not None and inicio > fin:
            segmentos_invalidos += 1
        if not str(segmento.get("texto_original") or segmento.get("texto") or "").strip():
            segmentos_invalidos += 1
        speaker = segmento.get("speaker_original")
        if not speaker:
            segmentos_invalidos += 1
        elif speaker in speakers_originales and speakers_originales[speaker] != speaker:
            speaker_modificados += 1
        else:
            speakers_originales[speaker] = speaker
        if speaker:
            roles_por_speaker.setdefault(str(speaker), normalizar_hablante_v2(segmento.get("rol") or segmento.get("hablante")))
    total_original = cantidad_original if cantidad_original is not None else len(segmentos)
    roles_dos_speakers = set(roles_por_speaker.values()) if len(roles_por_speaker) == 2 else set()
    mapping_valido = len(roles_por_speaker) != 2 or roles_dos_speakers == {"AGENTE", "CLIENTE"}
    return {
        "segmentos_originales": total_original,
        "segmentos_renderizados": len(segmentos),
        "segmentos_perdidos": max(0, total_original - len(segmentos)),
        "segmentos_nuevos": max(0, len(segmentos) - total_original),
        "segmentos_reordenados": segmentos_reordenados,
        "segmentos_invalidos": segmentos_invalidos,
        "speaker_modificados": speaker_modificados,
        "speaker_mapping_valido": mapping_valido,
        "requiere_revision_humana": not mapping_valido,
        "segmento_id_unicos": len(ids) == len(set(ids)),
        "orden_temporal_valido": segmentos_reordenados == 0,
    }


def asignar_roles_speakers(client, segmentos: List[Dict]) -> Dict:
    speakers = {}
    for segmento in segmentos:
        speaker = str(segmento.get("speaker_original") or "").strip()
        if not speaker:
            continue
        speakers.setdefault(speaker, []).append(segmento)

    if not speakers:
        return {}

    muestras = {}
    for speaker, items in speakers.items():
        seleccion = muestra_distribuida_speaker_v3(items)
        vistos = set()
        muestras[speaker] = []
        for item in seleccion:
            texto = str(item.get("texto") or "").strip()
            if not texto or texto in vistos:
                continue
            vistos.add(texto)
            muestras[speaker].append({
                "segmento_id": item.get("segmento_id"),
                "timestamp": item.get("timestamp"),
                "texto": texto,
            })
    logger.info(
        "Diarizacion speakers antes de roles: %s",
        json.dumps({
            "speakers_detectados": sorted(speakers.keys()),
            "cantidad_segmentos_por_speaker": {speaker: len(items) for speaker, items in speakers.items()},
            "primeros_5_segmentos_por_speaker": {
                speaker: [
                    {
                        "segmento_id": item.get("segmento_id"),
                        "timestamp": item.get("timestamp"),
                        "texto": str(item.get("texto") or item.get("texto_original") or "")[:180],
                    }
                    for item in items[:5]
                ]
                for speaker, items in speakers.items()
            },
        }, ensure_ascii=False),
    )

    prompt = f"""
Asigna rol a speakers completos de una llamada de cobranza. No clasifiques frases individualmente.
Decide una sola vez el rol predominante de cada speaker usando la muestra global.

Roles permitidos: AGENTE, CLIENTE, NO_DETERMINADO.

Señales AGENTE: saludo profesional, identificacion, menciona entidad, explica motivo, pregunta capacidad, propone pago, negocia, cierra.
Señales CLIENTE: confirma identidad, responde preguntas, explica situacion, objeta, habla de ingresos, acepta o rechaza propuestas.

Muestras por speaker:
{json.dumps(muestras, ensure_ascii=False)}

Devuelve JSON:
{{"speakers": {{"speaker_0": {{"rol": "AGENTE|CLIENTE|NO_DETERMINADO", "confianza": "ALTA|MEDIA|BAJA", "fundamento": ""}}}}}}
""".strip()

    mapping = {}
    try:
        data = llamar_json_modelo_pipeline_v3(client, prompt, "Asigna rol global por speaker diarizado.")
        raw_mapping = data.get("speakers") if isinstance(data.get("speakers"), dict) else {}
    except Exception:
        raw_mapping = {}

    mapping_ia = {}
    for speaker in speakers:
        raw = raw_mapping.get(speaker) if isinstance(raw_mapping.get(speaker), dict) else {}
        rol = normalizar_hablante_v2(raw.get("rol"))
        confianza = normalizar_confianza(raw.get("confianza"))
        fundamento = str(raw.get("fundamento") or "Rol asignado desde muestra global del speaker.").strip()
        mapping_ia[speaker] = {"rol": rol, "confianza": confianza, "fundamento": fundamento}

    mapping = validar_mapping_speakers_estandar_v3(speakers, mapping_ia)
    if not mapping:
        mapping = mapping_ia
        for speaker, asignacion in list(mapping.items()):
            if asignacion.get("rol") == "NO_DETERMINADO":
                rol, confianza, fundamento = inferir_rol_speaker_operativo_v3(speakers[speaker])
                mapping[speaker] = {"rol": rol, "confianza": confianza, "fundamento": fundamento}

    for segmento in segmentos:
        speaker = str(segmento.get("speaker_original") or "").strip()
        asignacion = mapping.get(speaker, {})
        segmento["rol"] = asignacion.get("rol") or "NO_DETERMINADO"
        segmento["hablante"] = segmento["rol"]
        segmento["confianza"] = asignacion.get("confianza") or "BAJA"
        segmento["fundamento"] = asignacion.get("fundamento") or "Rol no determinado desde diarizacion."

    logger.info(
        "Diarizacion mapping_resultante: %s",
        json.dumps({
            "mapping_resultante": mapping,
            "conteo_roles": conteo_roles_segmentos_v3(segmentos),
        }, ensure_ascii=False),
    )
    return mapping


def validar_mapping_speakers_estandar_v3(speakers: Dict[str, List[Dict]], mapping_ia: Dict[str, Dict]) -> Dict:
    if len(speakers) < 2:
        return {}
    if len(speakers) == 2:
        return validar_mapping_dos_speakers_v3(speakers, mapping_ia)

    speaker_ids = list(speakers.keys())
    roles = {
        speaker: normalizar_hablante_v2((mapping_ia.get(speaker) or {}).get("rol"))
        for speaker in speaker_ids
    }
    roles_utiles = {rol for rol in roles.values() if rol in {"AGENTE", "CLIENTE"}}
    conteo_roles_utiles = {
        rol: list(roles.values()).count(rol)
        for rol in {"AGENTE", "CLIENTE"}
    }
    if roles_utiles == {"AGENTE", "CLIENTE"} and conteo_roles_utiles.get("AGENTE") == 1 and conteo_roles_utiles.get("CLIENTE") == 1:
        return {
            speaker: {
                "rol": roles[speaker],
                "confianza": normalizar_confianza((mapping_ia.get(speaker) or {}).get("confianza")),
                "fundamento": (mapping_ia.get(speaker) or {}).get("fundamento") or "Rol asignado por IA a nivel speaker.",
            }
            for speaker in speaker_ids
        }

    puntajes = {
        speaker: puntuar_speaker_roles_operativo_v3(items)
        for speaker, items in speakers.items()
    }
    agente = max(
        speaker_ids,
        key=lambda speaker: (
            int(puntajes[speaker].get("score_agente") or 0) - int(puntajes[speaker].get("score_cliente") or 0),
            int(puntajes[speaker].get("score_agente") or 0),
            len(speakers[speaker]),
        ),
    )
    candidatos_cliente = [speaker for speaker in speaker_ids if speaker != agente]
    cliente = max(
        candidatos_cliente,
        key=lambda speaker: (
            int(puntajes[speaker].get("score_cliente") or 0) - int(puntajes[speaker].get("score_agente") or 0),
            int(puntajes[speaker].get("score_cliente") or 0),
            len(speakers[speaker]),
        ),
    )
    if int(puntajes[agente].get("score_agente") or 0) < 2 or int(puntajes[cliente].get("score_cliente") or 0) < 1:
        logger.warning(
            "Mapping speaker->rol multiparte ambiguo; no se fuerza exclusividad. puntajes=%s mapping_ia=%s",
            json.dumps(puntajes, ensure_ascii=False),
            json.dumps(mapping_ia, ensure_ascii=False),
        )
        return {}

    salida = {}
    for speaker in speaker_ids:
        if speaker == agente:
            salida[speaker] = {
                "rol": "AGENTE",
                "confianza": "MEDIA",
                "fundamento": "Mapping corregido por señales globales de gestión del speaker.",
            }
        elif speaker == cliente:
            salida[speaker] = {
                "rol": "CLIENTE",
                "confianza": "MEDIA",
                "fundamento": "Mapping corregido por señales globales de respuesta/objeción del speaker.",
            }
        else:
            if es_speaker_confirmacion_cliente_v3(speakers[speaker], puntajes.get(speaker, {})):
                rol, confianza, fundamento = (
                    "CLIENTE",
                    "MEDIA",
                    "Speaker breve de confirmación o respuesta del cliente dentro de la apertura.",
                )
            else:
                rol, confianza, fundamento = inferir_rol_speaker_operativo_v3(speakers[speaker])
            if rol in {"AGENTE", "CLIENTE"}:
                salida[speaker] = {"rol": rol, "confianza": confianza, "fundamento": fundamento}
            else:
                salida[speaker] = {
                    "rol": "NO_DETERMINADO",
                    "confianza": "BAJA",
                    "fundamento": "Speaker adicional sin señales suficientes para rol operativo.",
                }
    return salida


def muestra_distribuida_speaker_v3(items: List[Dict]) -> List[Dict]:
    if not items:
        return []
    total = len(items)
    indices = []
    ventanas = [
        range(0, min(total, 5)),
        range(max(0, total // 3 - 2), min(total, total // 3 + 3)),
        range(max(0, total // 2 - 2), min(total, total // 2 + 3)),
        range(max(0, (total * 2) // 3 - 2), min(total, (total * 2) // 3 + 3)),
        range(max(0, total - 5), total),
    ]
    for ventana in ventanas:
        for idx in ventana:
            if idx not in indices:
                indices.append(idx)
    return [items[idx] for idx in indices]


def validar_mapping_dos_speakers_v3(speakers: Dict[str, List[Dict]], mapping_ia: Dict[str, Dict]) -> Dict:
    if len(speakers) != 2:
        return {}

    speaker_ids = list(speakers.keys())
    roles = {speaker: normalizar_hablante_v2((mapping_ia.get(speaker) or {}).get("rol")) for speaker in speaker_ids}
    confianzas = {speaker: normalizar_confianza((mapping_ia.get(speaker) or {}).get("confianza")) for speaker in speaker_ids}

    if set(roles.values()) == {"AGENTE", "CLIENTE"}:
        return {
            speaker: {
                "rol": roles[speaker],
                "confianza": confianzas[speaker],
                "fundamento": (mapping_ia.get(speaker) or {}).get("fundamento") or "Rol asignado por IA a nivel speaker.",
            }
            for speaker in speaker_ids
        }

    # Regla de exclusividad: si un solo speaker fue clasificado con confianza
    # suficiente, el otro queda como el rol complementario.
    seguros = [
        speaker for speaker in speaker_ids
        if roles[speaker] in {"AGENTE", "CLIENTE"} and confianzas[speaker] in {"ALTA", "MEDIA"}
    ]
    if len(seguros) == 1:
        seguro = seguros[0]
        otro = speaker_ids[1] if speaker_ids[0] == seguro else speaker_ids[0]
        rol_seguro = roles[seguro]
        rol_otro = "CLIENTE" if rol_seguro == "AGENTE" else "AGENTE"
        return {
            seguro: {
                "rol": rol_seguro,
                "confianza": confianzas[seguro],
                "fundamento": (mapping_ia.get(seguro) or {}).get("fundamento") or "Rol asignado por IA a nivel speaker.",
            },
            otro: {
                "rol": rol_otro,
                "confianza": "MEDIA",
                "fundamento": "Regla de exclusividad en llamada de dos speakers.",
            },
        }

    # Si la IA devolvió ambos iguales o ambos indeterminados, no lo aceptamos:
    # intentamos fallback global por speaker.
    fallback = asignar_dos_speakers_por_fallback_v3(speakers)
    if fallback and set(item.get("rol") for item in fallback.values()) == {"AGENTE", "CLIENTE"}:
        return fallback

    rol_unico = next(iter(set(roles.values())), None) if len(set(roles.values())) == 1 else None
    if rol_unico in {"AGENTE", "CLIENTE"}:
        puntajes = {
            speaker: puntuar_speaker_roles_operativo_v3(items)
            for speaker, items in speakers.items()
        }
        clave_rol = "score_agente" if rol_unico == "AGENTE" else "score_cliente"
        ordenados = sorted(
            puntajes.items(),
            key=lambda item: (
                int(item[1].get(clave_rol) or 0),
                int(item[1].get("score_agente") or 0) + int(item[1].get("score_cliente") or 0),
            ),
            reverse=True,
        )
        principal = ordenados[0][0]
        secundario = ordenados[1][0]
        score_principal = int(puntajes[principal].get(clave_rol) or 0)
        score_secundario = int(puntajes[secundario].get(clave_rol) or 0)
        if score_principal >= 2 and score_principal > score_secundario:
            rol_secundario = "CLIENTE" if rol_unico == "AGENTE" else "AGENTE"
            return {
                principal: {
                    "rol": rol_unico,
                    "confianza": "MEDIA",
                    "fundamento": "Mapping corregido por exclusividad en llamada de dos speakers.",
                },
                secundario: {
                    "rol": rol_secundario,
                    "confianza": "MEDIA",
                    "fundamento": "Rol complementario por exclusividad en llamada de dos speakers.",
                },
            }

    logger.warning(
        "Mapping speaker->rol ambiguo en llamada de dos speakers; se conserva mapping parcial util. mapping_ia=%s fallback=%s",
        json.dumps(mapping_ia, ensure_ascii=False),
        json.dumps(fallback, ensure_ascii=False),
    )
    parcial = {}
    for speaker in speaker_ids:
        rol = roles[speaker]
        if rol in {"AGENTE", "CLIENTE"} and confianzas[speaker] in {"ALTA", "MEDIA"} and list(roles.values()).count(rol) == 1:
            parcial[speaker] = {
                "rol": rol,
                "confianza": confianzas[speaker],
                "fundamento": (mapping_ia.get(speaker) or {}).get("fundamento") or "Mapping parcial conservado por confianza suficiente.",
            }
        else:
            parcial[speaker] = {
                "rol": "NO_DETERMINADO",
                "confianza": "BAJA",
                "fundamento": "Mapping ambiguo: no se pudo asignar rol con evidencia suficiente.",
            }
    return parcial


def puntuar_speaker_roles_operativo_v3(segmentos: List[Dict]) -> Dict[str, object]:
    texto = limpiar_key_texto(" ".join(
        str(item.get("texto") or item.get("texto_original") or item.get("transcripcion") or item.get("frase") or "")
        for item in muestra_distribuida_speaker_v3(segmentos)
    ))
    senales_agente = [
        "le habla", "te saluda", "le saluda", "mi nombre", "soy",
        "se comunica", "mi banco", "mibanco",
        "banco", "entidad", "por encargo", "cuenta", "deuda", "credito",
        "prestamo", "cuotas", "cuota", "campana", "descuento", "beneficio",
        "puedes", "puede", "podria", "podria", "abonar", "cancelar", "pagar",
        "cuanto", "fecha", "cuando", "capacidad", "ha podido recaudar",
        "pago total", "acuerdo", "programar", "compromiso", "voucher",
        "constancia", "fraccionamiento",
    ]
    senales_cliente = [
        "no puedo", "no me encuentro", "no tengo", "no cuento", "estoy pagando",
        "tengo problemas", "problemas", "trabajo", "ingreso", "cosecha",
        "agricultura", "enfermedad", "operar", "esposo", "familia",
        "bancos", "otro banco", "mis bancos", "debo", "debiendo",
        "puedo pagar", "podria pagar", "voy a cancelar", "me interesa",
        "no se ha podido", "no se puede", "para el", "la semana",
        "el miercoles", "manana", "plazo", "reprogramar", "parte",
        "abono", "duda", "cuanto es", "si con ella", "sí con ella",
        "con ella", "digame", "dígame", "no uso whatsapp",
    ]
    hallazgos_agente = senales_presentes_operativas_v3(texto, senales_agente)
    hallazgos_cliente = senales_presentes_operativas_v3(texto, senales_cliente)
    return {
        "score_agente": len(hallazgos_agente),
        "score_cliente": len(hallazgos_cliente),
        "senales_agente": hallazgos_agente[:12],
        "senales_cliente": hallazgos_cliente[:12],
    }


def es_speaker_confirmacion_cliente_v3(segmentos: List[Dict], puntaje: Optional[Dict] = None) -> bool:
    if not segmentos or len(segmentos) > 8:
        return False
    puntaje = puntaje or puntuar_speaker_roles_operativo_v3(segmentos)
    if int(puntaje.get("score_agente") or 0) >= 2:
        return False
    texto = limpiar_key_texto(" ".join(
        str(item.get("texto") or item.get("texto_original") or "")
        for item in segmentos
    ))
    tokens_cliente = {
        "si", "sí", "si con ella", "sí con ella", "con ella",
        "digame", "dígame", "buenos dias", "buenas tardes",
        "no uso whatsapp", "ok", "esta bien", "está bien",
    }
    return any(limpiar_key_texto(token) in texto for token in tokens_cliente)


def inferir_rol_speaker_operativo_v3(segmentos: List[Dict]) -> tuple[str, str, str]:
    puntaje = puntuar_speaker_roles_operativo_v3(segmentos)
    score_agente = int(puntaje["score_agente"])
    score_cliente = int(puntaje["score_cliente"])
    if score_agente > score_cliente:
        return "AGENTE", "MEDIA", f"Fallback por señales globales de gestión del speaker: {', '.join(puntaje['senales_agente'][:5])}."
    if score_cliente > score_agente:
        return "CLIENTE", "MEDIA", f"Fallback por señales globales de respuesta/objeción del speaker: {', '.join(puntaje['senales_cliente'][:5])}."
    return "NO_DETERMINADO", "BAJA", "Fallback sin señales suficientes por speaker."


def senales_presentes_operativas_v3(texto: str, senales: List[str]) -> List[str]:
    encontradas = []
    for senal in senales:
        key = limpiar_key_texto(senal)
        if not key:
            continue
        if re.search(rf"(?<!\w){re.escape(key)}(?!\w)", texto):
            encontradas.append(senal)
    return encontradas


def inferir_rol_speaker_fallback_v3(segmentos: List[Dict]) -> tuple[str, str, str]:
    texto = limpiar_key_texto(" ".join(str(item.get("texto") or "") for item in muestra_distribuida_speaker_v3(segmentos)))
    senales_agente = [
        "le habla", "te saluda", "le saluda", "mi banco", "mibanco", "por encargo",
        "deuda", "credito", "cuotas", "puedes", "puede", "abonar", "cancelar",
        "fecha", "pago total", "acuerdo", "voucher",
    ]
    senales_cliente = [
        "no puedo", "no me encuentro", "estoy pagando", "tengo", "trabajo", "ingreso",
        "bancos", "no tengo", "puedo pagar", "voy a cancelar", "me interesa",
    ]
    score_agente = sum(1 for item in senales_agente if item in texto)
    score_cliente = sum(1 for item in senales_cliente if item in texto)
    if score_agente > score_cliente:
        return "AGENTE", "MEDIA", "Fallback por señales globales de gestion del speaker."
    if score_cliente > score_agente:
        return "CLIENTE", "MEDIA", "Fallback por señales globales de respuesta/objecion del speaker."
    return "NO_DETERMINADO", "BAJA", "Fallback sin señales suficientes por speaker."


def asignar_dos_speakers_por_fallback_v3(speakers: Dict[str, List[Dict]]) -> Dict:
    scores = {}
    for speaker, items in speakers.items():
        rol, confianza, fundamento = inferir_rol_speaker_operativo_v3(items)
        puntaje = puntuar_speaker_roles_operativo_v3(items)
        scores[speaker] = (
            int(puntaje["score_agente"]),
            int(puntaje["score_cliente"]),
            rol,
            confianza,
            fundamento,
            puntaje,
        )
    ordenados = sorted(scores.items(), key=lambda item: (item[1][0] - item[1][1], item[1][0]), reverse=True)
    if len(ordenados) != 2:
        return {}
    agente = ordenados[0][0]
    cliente = ordenados[1][0]
    agente_score, agente_cliente_score = scores[agente][0], scores[agente][1]
    cliente_score_agente, cliente_score = scores[cliente][0], scores[cliente][1]

    if agente_score < 2 and cliente_score < 2:
        return {}

    if agente_score <= agente_cliente_score or agente_score <= cliente_score_agente:
        por_cliente = sorted(scores.items(), key=lambda item: (item[1][1] - item[1][0], item[1][1]), reverse=True)
        cliente = por_cliente[0][0]
        agente = [speaker for speaker in speakers.keys() if speaker != cliente][0]
        if scores[cliente][1] < 2:
            return {}

    return {
        agente: {
            "rol": "AGENTE",
            "confianza": "MEDIA",
            "fundamento": "Fallback: speaker con mayor perfil operativo de gestión.",
        },
        cliente: {
            "rol": "CLIENTE",
            "confianza": "MEDIA",
            "fundamento": "Fallback: rol complementario en llamada de dos participantes.",
        },
    }


def conteo_roles_segmentos_v3(segmentos: List[Dict]) -> Dict[str, int]:
    conteo = {"AGENTE": 0, "CLIENTE": 0, "NO_DETERMINADO": 0}
    for segmento in segmentos:
        rol = normalizar_hablante_v2(segmento.get("rol") or segmento.get("hablante"))
        conteo[rol if rol in conteo else "NO_DETERMINADO"] += 1
    return conteo


def metricas_cobertura_roles_v3(segmentos: List[Dict], mapping: Optional[Dict] = None) -> Dict:
    conteo = conteo_roles_segmentos_v3(segmentos)
    total = len(segmentos)
    conocidos = conteo["AGENTE"] + conteo["CLIENTE"]
    speakers = sorted({
        str(item.get("speaker_original"))
        for item in segmentos
        if item.get("speaker_original")
    })
    mapping_speakers = mapping if isinstance(mapping, dict) and mapping else {
        speaker: next(
            (
                normalizar_hablante_v2(item.get("rol") or item.get("hablante"))
                for item in segmentos
                if str(item.get("speaker_original")) == speaker
            ),
            "NO_DETERMINADO",
        )
        for speaker in speakers
    }
    confianzas = [
        str(item.get("confianza") or "").upper()
        for item in segmentos
        if normalizar_hablante_v2(item.get("rol") or item.get("hablante")) in {"AGENTE", "CLIENTE"}
    ]
    confianza_mapping = "ALTA" if confianzas and confianzas.count("ALTA") / len(confianzas) >= 0.6 else "MEDIA" if conocidos else "BAJA"
    cobertura = round((conocidos / total) * 100, 2) if total else 0.0
    return {
        "total_segmentos": total,
        "segmentos_agente": conteo["AGENTE"],
        "segmentos_cliente": conteo["CLIENTE"],
        "segmentos_no_determinado": conteo["NO_DETERMINADO"],
        "cobertura_roles_pct": cobertura,
        "speakers_detectados": speakers,
        "mapping_speakers": mapping_speakers,
        "confianza_mapping": confianza_mapping,
        "requiere_revision_humana": cobertura < 70,
    }


def evaluar_calidad_transcripcion_v3(segmentos: List[Dict]) -> Dict:
    """Determina si la fuente permite automatizar la evaluación sin alterar segmentos.

    Es una compuerta de confianza: no corrige, fusiona ni reasigna texto. Solo
    deja trazabilidad para que los criterios sensibles no se interpreten como
    conclusiones definitivas cuando la diarización o el tiempo son insuficientes.
    """
    segmentos = [item for item in segmentos if isinstance(item, dict)]
    integridad = validar_integridad_diarizacion(segmentos, len(segmentos)) if any(
        item.get("speaker_original") for item in segmentos
    ) else {}
    roles = metricas_cobertura_roles_v3(segmentos)
    total = len(segmentos)
    con_tiempo = [
        item for item in segmentos
        if item.get("inicio_segundos") is not None and item.get("fin_segundos") is not None
    ]
    cobertura_tiempo = round((len(con_tiempo) / total) * 100, 2) if total else 0.0
    fragmentos_cortos = sum(
        1 for item in segmentos
        if len(re.findall(r"\w+", str(item.get("texto_original") or item.get("texto") or ""))) <= 2
    )
    fragmentacion_pct = round((fragmentos_cortos / total) * 100, 2) if total else 0.0
    motivos_criticos = []
    motivos_advertencia = []

    if not total:
        motivos_criticos.append("No se generaron segmentos de transcripción.")
    if roles.get("cobertura_roles_pct", 0) < 70:
        motivos_criticos.append("La cobertura de roles AGENTE/CLIENTE es menor al 70%.")
    if total and cobertura_tiempo < 70:
        motivos_criticos.append("Menos del 70% de los segmentos tiene inicio y fin sincronizados.")
    if integridad and (
        not integridad.get("segmento_id_unicos")
        or not integridad.get("orden_temporal_valido")
        or integridad.get("segmentos_invalidos", 0) > 0
        or integridad.get("segmentos_perdidos", 0) > 0
    ):
        motivos_criticos.append("La integridad de segmentos diarizados requiere revisión.")

    if total and cobertura_tiempo < 95 and not motivos_criticos:
        motivos_advertencia.append("Hay segmentos sin sincronización temporal completa.")
    if total >= 12 and fragmentacion_pct >= 40:
        motivos_advertencia.append("La transcripción está muy fragmentada; conviene revisar frases sensibles contra el audio.")
    if len(roles.get("speakers_detectados") or []) > 2:
        motivos_advertencia.append("La diarización detectó más de dos speakers; puede existir tercero o superposición.")

    requiere_revision = bool(motivos_criticos)
    nivel = "BAJA" if motivos_criticos else ("MEDIA" if motivos_advertencia else "ALTA")
    confianza = "BAJA" if motivos_criticos else ("MEDIA" if motivos_advertencia or roles.get("confianza_mapping") == "MEDIA" else "ALTA")
    return {
        "nivel": nivel,
        "confianza": confianza,
        "requiere_revision_humana": requiere_revision,
        "motivo": "; ".join([*motivos_criticos, *motivos_advertencia]) or "Fuente transcrita y diarizada con cobertura suficiente.",
        "motivos_criticos": motivos_criticos,
        "advertencias": motivos_advertencia,
        "metricas": {
            "total_segmentos": total,
            "segmentos_con_tiempo": len(con_tiempo),
            "cobertura_tiempo_pct": cobertura_tiempo,
            "fragmentos_cortos": fragmentos_cortos,
            "fragmentacion_pct": fragmentacion_pct,
            "roles": roles,
            "integridad": integridad,
        },
    }


def construir_texto_con_timestamps(segments) -> Optional[str]:
    if not isinstance(segments, list) or not segments:
        return None

    lineas = []
    for segment in segments:
        if not isinstance(segment, dict):
            continue
        texto = str(segment.get("text") or "").strip()
        if not texto:
            continue
        inicio = segment.get("start")
        lineas.append(f"[{formatear_timestamp(inicio)}] {texto}")
    return "\n".join(lineas).strip() or None


def formatear_timestamp(value) -> str:
    try:
        segundos = max(0, int(float(value)))
    except (TypeError, ValueError):
        return "No disponible"
    minutos, segundos = divmod(segundos, 60)
    return f"{minutos:02d}:{segundos:02d}"


def analizar_transcripcion_real(
    transcripcion: str,
    comentario_supervisor: Optional[str] = None,
    cartera: Optional[str] = None,
) -> Dict:
    if not ia_real_configurada():
        raise RuntimeError("OPENAI_API_KEY no configurada.")
    if OpenAI is None:
        raise RuntimeError("La libreria openai no esta instalada en el entorno.")

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    return analizar_transcripcion_pipeline_v3(
        client=client,
        transcripcion=transcripcion,
        comentario_supervisor=comentario_supervisor,
        cartera=cartera,
    )


def analizar_transcripcion_pipeline_v3(
    *,
    client,
    transcripcion: str,
    comentario_supervisor: Optional[str] = None,
    cartera: Optional[str] = None,
) -> Dict:
    pauta = obtener_pauta_evaluacion(cartera)
    segmentos = identificar_interlocutores(transcripcion, client=client)
    hechos = extraer_hechos_llamada(client, segmentos, comentario_supervisor=comentario_supervisor)
    criterios = evaluar_criterios_desde_hechos(client, segmentos, hechos, pauta=pauta)
    criterios = normalizar_criterios_pipeline_v3(criterios, segmentos, pauta=pauta)
    criterios = aplicar_anulantes_bloque(criterios)
    criterios = aplicar_guardas_deterministicas_criterios(segmentos, criterios)
    score_antes = score_desde_criterios_pipeline_v3(criterios)
    auditoria = auditar_evaluacion(client, segmentos, hechos, criterios)
    criterios, criterios_corregidos = corregir_criterios_inconsistentes(client, segmentos, hechos, criterios, auditoria, pauta=pauta)
    criterios = normalizar_criterios_pipeline_v3(criterios, segmentos, pauta=pauta)
    criterios = aplicar_anulantes_bloque(criterios)
    criterios = aplicar_guardas_deterministicas_criterios(segmentos, criterios)
    score_despues = score_desde_criterios_pipeline_v3(criterios)
    feedback = generar_feedback_desde_evaluacion(client, segmentos, hechos, criterios, score_despues)
    data = construir_respuesta_pipeline_v3(
        segmentos=segmentos,
        hechos=hechos,
        criterios=criterios,
        auditoria=auditoria,
        feedback=feedback,
        score_antes=score_antes,
        score_despues=score_despues,
        criterios_corregidos=criterios_corregidos,
        cartera=cartera,
        pauta=pauta,
    )
    return normalizar_analisis_copc_v2(data, transcripcion=transcripcion)


def construir_prompt_analisis_calidad(
    transcripcion: str,
    comentario_supervisor: Optional[str],
    cartera: Optional[str] = None,
) -> str:
    try:
        config = obtener_prompt_configuracion(cartera)
    except Exception:
        config = {}
    base = prompt_base_sistema()
    prompt_personalizado = config.get("prompt_personalizado") or ""
    if limpiar_key_texto(prompt_personalizado) == limpiar_key_texto(base):
        prompt_personalizado = ""
    ajustes = f"""

Ajustes adicionales por cartera o configuracion interna:
{prompt_personalizado}

Estos ajustes pueden complementar el análisis, pero nunca reemplazan la pauta publicada de la cartera.
""" if prompt_personalizado else ""

    return f"""
{base}
{ajustes}

Comentario del supervisor:
{comentario_supervisor or "-"}

Transcripcion:
{transcripcion}
""".strip()


def identificar_interlocutores(transcripcion: str, client=None) -> List[Dict]:
    segmentos = segmentar_transcripcion_etiquetada_v2(transcripcion)
    tiene_diarizacion_original = any(item.get("speaker_original") for item in segmentos)
    if not segmentos:
        segmentos = segmentar_transcripcion_inferida_v2(transcripcion)
    normalizados = []
    ultimo = "NO_DETERMINADO"
    for idx, segmento in enumerate(segmentos, start=1):
        texto = str(segmento.get("texto_limpio") or segmento.get("texto_original") or segmento.get("texto") or "").strip()
        if not texto:
            continue
        hablante = normalizar_hablante_v2(segmento.get("hablante"))
        confianza = normalizar_confianza(segmento.get("confianza"))
        fundamento = str(segmento.get("fundamento") or "").strip()
        if hablante == "NO_DETERMINADO" and not tiene_diarizacion_original:
            hablante, confianza, fundamento = inferir_hablante_fragmento_v2(texto, ultimo)
        if hablante in {"AGENTE", "CLIENTE"}:
            ultimo = hablante
        normalizados.append({
            "segmento_id": normalizar_orden_segmento_v2(segmento.get("segmento_id"), idx),
            "orden": normalizar_orden_segmento_v2(segmento.get("orden"), idx),
            "timestamp": normalizar_timestamp_v2(segmento.get("timestamp")),
            "inicio_segundos": normalizar_segundos_v2(segmento.get("inicio_segundos")),
            "fin_segundos": normalizar_segundos_v2(segmento.get("fin_segundos")),
            "hablante": hablante,
            "texto_original": str(segmento.get("texto_original") or texto).strip(),
            "texto_limpio": segmento.get("texto_limpio"),
            "texto": texto,
            "confianza": confianza,
            "fundamento": fundamento,
            "speaker_original": segmento.get("speaker_original"),
            "rol": hablante,
        })
    if tiene_diarizacion_original:
        if diarizacion_tiene_roles_operativos_v3(normalizados):
            return normalizados
        if client is not None and normalizados:
            reasignados = identificar_interlocutores_ia(client, normalizados)
            if cobertura_roles_suficiente_v3(reasignados):
                for original, reasignado in zip(normalizados, reasignados):
                    original["hablante"] = reasignado.get("hablante") or "NO_DETERMINADO"
                    original["rol"] = original["hablante"]
                    original["confianza"] = reasignado.get("confianza") or original.get("confianza")
                    original["fundamento"] = reasignado.get("fundamento") or "Rol reasignado por fallback secuencial sobre diarización insuficiente."
                return normalizados
        return completar_interlocutores_por_secuencia_v3(normalizados)
    if client is None or not normalizados:
        return completar_interlocutores_por_secuencia_v3(normalizados)
    return identificar_interlocutores_ia(client, normalizados)


def diarizacion_tiene_roles_operativos_v3(segmentos: List[Dict]) -> bool:
    if not segmentos:
        return False
    speakers = {str(item.get("speaker_original") or "").strip() for item in segmentos if item.get("speaker_original")}
    roles = [normalizar_hablante_v2(item.get("hablante") or item.get("rol")) for item in segmentos]
    roles_claros = {rol for rol in roles if rol in {"AGENTE", "CLIENTE"}}
    if len(speakers) >= 2 and roles_claros == {"AGENTE", "CLIENTE"}:
        return True
    return False


def cobertura_roles_suficiente_v3(segmentos: List[Dict]) -> bool:
    if not segmentos:
        return False
    total = len(segmentos)
    agente = sum(1 for item in segmentos if normalizar_hablante_v2(item.get("hablante") or item.get("rol")) == "AGENTE")
    cliente = sum(1 for item in segmentos if normalizar_hablante_v2(item.get("hablante") or item.get("rol")) == "CLIENTE")
    return agente > 0 and cliente > 0 and ((agente + cliente) / total) >= 0.7


def identificar_interlocutores_ia(client, segmentos: List[Dict]) -> List[Dict]:
    """
    Segunda capa de identificación de hablantes.

    La segmentación conserva texto/timestamps del sistema. La IA solo asigna
    hablante, confianza y fundamento usando la secuencia conversacional.
    """
    salida = [dict(item) for item in segmentos]
    por_id = {int(item.get("segmento_id") or 0): item for item in salida}
    bloques = bloques_segmentos_pipeline_v3(salida, 120)
    ultimo_hablante = "NO_DETERMINADO"

    for indice, bloque in enumerate(bloques, start=1):
        contexto_previo = []
        if bloque and int(bloque[0].get("segmento_id") or 0) > 1:
            inicio = max(0, salida.index(bloque[0]) - 6)
            contexto_previo = salida[inicio:salida.index(bloque[0])]

        prompt = f"""
Identifica hablantes de esta llamada de cobranza usando la secuencia conversacional completa del bloque.
No modifiques textos ni timestamps. No evalues calidad ni score.

Reglas:
- AGENTE suele saludar, identificarse, preguntar, explicar deuda/propuesta, negociar, inducir pago, cerrar.
- CLIENTE suele responder, confirmar identidad, explicar situacion, objetar, aceptar o rechazar.
- Usa turnos de pregunta/respuesta. No analices frases aisladas.
- Si una frase es ambigua, usa NO_DETERMINADO.
- No fuerces asignaciones por palabras sueltas como deuda, pago o banco.

Bloque {indice} de {len(bloques)}.
Ultimo hablante claro antes del bloque: {ultimo_hablante}

Contexto previo:
{json.dumps(contexto_previo, ensure_ascii=False)}

Segmentos:
{json.dumps(bloque, ensure_ascii=False)}

Devuelve JSON:
{{"segmentos": [
  {{"segmento_id": 1, "hablante": "AGENTE|CLIENTE|NO_DETERMINADO", "confianza": "ALTA|MEDIA|BAJA", "fundamento": ""}}
]}}
""".strip()
        try:
            data = llamar_json_modelo_pipeline_v3(client, prompt, "Identifica hablantes por secuencia; no cambies el texto.")
        except Exception:
            continue

        asignaciones = data.get("segmentos") if isinstance(data.get("segmentos"), list) else []
        for raw in asignaciones:
            if not isinstance(raw, dict):
                continue
            try:
                segmento_id = int(raw.get("segmento_id"))
            except (TypeError, ValueError):
                continue
            segmento = por_id.get(segmento_id)
            if not segmento:
                continue
            hablante = normalizar_hablante_v2(raw.get("hablante"))
            confianza = normalizar_confianza(raw.get("confianza"))
            if hablante not in {"AGENTE", "CLIENTE", "NO_DETERMINADO"}:
                hablante = "NO_DETERMINADO"
            segmento["hablante"] = hablante
            segmento["confianza"] = confianza
            segmento["fundamento"] = str(raw.get("fundamento") or "Identificado por secuencia conversacional.").strip()
            if hablante in {"AGENTE", "CLIENTE"}:
                ultimo_hablante = hablante

    return completar_interlocutores_por_secuencia_v3(salida)


def completar_interlocutores_por_secuencia_v3(segmentos: List[Dict]) -> List[Dict]:
    salida = [dict(item) for item in segmentos]
    ultimo_claro = "NO_DETERMINADO"
    pendiente_agente = False

    for idx, segmento in enumerate(salida):
        texto = str(segmento.get("texto") or "").strip()
        key = limpiar_key_texto(texto)
        hablante = normalizar_hablante_v2(segmento.get("hablante"))
        confianza = normalizar_confianza(segmento.get("confianza"))
        sugerido = hablante
        fundamento = str(segmento.get("fundamento") or "").strip()

        if hablante == "NO_DETERMINADO" or confianza == "BAJA":
            sugerido, confianza_sugerida, fundamento_sugerido = inferir_hablante_secuencia_v3(
                key,
                texto,
                ultimo_claro,
                pendiente_agente,
                idx,
                salida,
            )
            if sugerido != "NO_DETERMINADO":
                hablante = sugerido
                confianza = confianza_sugerida
                fundamento = fundamento_sugerido

        segmento["hablante"] = hablante
        segmento["confianza"] = confianza
        segmento["fundamento"] = fundamento or "Hablante inferido por secuencia conversacional."

        if hablante in {"AGENTE", "CLIENTE"}:
            ultimo_claro = hablante
        pendiente_agente = texto.endswith("?") and hablante == "AGENTE"

    return salida


def inferir_hablante_secuencia_v3(
    key: str,
    texto: str,
    ultimo_claro: str,
    pendiente_agente: bool,
    idx: int,
    segmentos: List[Dict],
) -> tuple[str, str, str]:
    if not key:
        return "NO_DETERMINADO", "BAJA", "Sin texto suficiente para inferir hablante."

    agente_fuerte = [
        "le habla", "te saluda", "le saluda", "por encargo", "mi banco", "mibanco",
        "credito", "cuotas", "cuota", "deuda", "debes cancelar", "puedes cancelar", "puede cancelar", "abonar",
        "abonando", "pago total", "fecha de", "estamos estableciendo", "puedes ir",
        "se puede", "efectuas el pago", "te corresponde", "acuerdo", "campana",
        "por referencia", "te he traido", "le traigo", "impulsa",
    ]
    cliente_fuerte = [
        "no me encuentro", "estoy pagando", "he tenido", "perdida", "mi agricultura",
        "yo trabajo", "yo consulte", "no podia", "no puedo", "no podria", "yo podria",
        "me quedo", "tengo dinero", "vuelvo a juntar", "acabo de pagar", "mis bancos",
        "mi banco", "me han permitido", "me interesa", "voy a cancelar",
        "no me alcanza", "no tengo", "no cuento", "otros bancos", "todos los bancos",
    ]
    respuestas_cortas_cliente = {
        "si", "si senor", "si senorita", "ya", "ya senorita", "claro", "correcto",
        "aja", "ok", "bueno", "no", "no senorita", "que senorita", "cuanto",
    }

    score_agente = sum(1 for item in agente_fuerte if item in key)
    score_cliente = sum(1 for item in cliente_fuerte if item in key)

    if key in respuestas_cortas_cliente and (pendiente_agente or ultimo_claro == "AGENTE"):
        return "CLIENTE", "MEDIA", "Respuesta breve posterior a pregunta o gestion del agente."

    if idx <= 2 and key in {"alo", "si"}:
        return "CLIENTE", "MEDIA", "Apertura/respuesta inicial probable del cliente en llamada saliente."

    if idx <= 3 and key.startswith("hola") and ultimo_claro == "CLIENTE":
        return "AGENTE", "MEDIA", "Saludo del agente posterior a apertura del cliente."

    if "como estas" in key or "como esta" in key:
        return "AGENTE", "MEDIA", "Pregunta de apertura y control del agente."

    if texto.endswith("?") and idx <= 5 and ultimo_claro == "AGENTE" and len(key.split()) <= 4:
        return "AGENTE", "MEDIA", "Pregunta inicial de validacion o contacto del agente."

    if key in {"que", "que senorita"} or "que senorita" in key:
        return "CLIENTE", "MEDIA", "Pregunta breve del cliente ante la gestion."

    if key in {"ya entiendo", "entiendo", "ya"} and ultimo_claro == "CLIENTE":
        return "AGENTE", "MEDIA", "Reconocimiento posterior a explicacion del cliente."

    if key.startswith("mira ") or key.startswith("mire "):
        return "AGENTE", "MEDIA", "Transicion del agente para explicar propuesta o informacion de gestion."

    if texto.endswith("?"):
        if score_agente > score_cliente:
            return "AGENTE", "MEDIA", "Pregunta de control o gestion dentro de la llamada."
        if score_cliente > score_agente:
            return "CLIENTE", "MEDIA", "Objecion o consulta del cliente en forma interrogativa."
        if ultimo_claro == "AGENTE":
            return "CLIENTE", "MEDIA", "Pregunta/respuesta del cliente dentro de la objecion."

    if score_agente > score_cliente:
        return "AGENTE", "MEDIA" if score_agente == 1 else "ALTA", "Inferido por gestion, propuesta o informacion de cobranza."
    if score_cliente > score_agente:
        return "CLIENTE", "MEDIA" if score_cliente == 1 else "ALTA", "Inferido por explicacion, objecion o situacion economica del cliente."

    if ultimo_claro == "AGENTE" and len(key.split()) <= 4:
        return "CLIENTE", "BAJA", "Respuesta corta posterior a intervencion del agente."

    if ultimo_claro == "CLIENTE" and len(key.split()) <= 6:
        return "CLIENTE", "BAJA", "Continuacion breve de explicacion del cliente."

    return "NO_DETERMINADO", "BAJA", "No hay suficientes marcas secuenciales para asignar hablante."


def extraer_hechos_llamada(client, segmentos: List[Dict], comentario_supervisor: Optional[str] = None) -> Dict:
    categorias = categorias_hechos_pipeline_v3()
    hechos = {categoria: [] for categoria in categorias}
    inventario = inventario_vacio_pipeline_v3()
    bloques = bloques_segmentos_pipeline_v3(segmentos, 120)
    for indice, bloque in enumerate(bloques, start=1):
        prompt = f"""
Analiza exclusivamente estos segmentos de la llamada actual. No asignes score ni errores.
Extrae hechos observables de forma exhaustiva y referencia siempre segmento_id.
No inventes datos. Si no aparece, deja la lista vacia.

Bloque {indice} de {len(bloques)}.
Comentario supervisor auxiliar: {comentario_supervisor or "-"}

Categorias obligatorias:
{json.dumps(categorias, ensure_ascii=False)}

Segmentos:
{json.dumps(bloque, ensure_ascii=False)}

Devuelve JSON:
{{
  "hechos": {{"categoria": [{{"segmento_id": 1, "hablante": "AGENTE|CLIENTE|NO_DETERMINADO", "texto": "", "tipo": "", "interpretacion": "", "confianza": "ALTA|MEDIA|BAJA"}}]}},
  "inventario": {{"apertura.saludo": {{"encontrado": true, "segmentos": [1]}}}}
}}
""".strip()
        data = llamar_json_modelo_pipeline_v3(client, prompt, "Extrae hechos de cobranza; no evalues ni puntues.")
        for categoria, items in (data.get("hechos") or {}).items():
            if categoria not in hechos or not isinstance(items, list):
                continue
            hechos[categoria].extend(normalizar_hechos_pipeline_v3(items, segmentos))
        fusionar_inventario_pipeline_v3(inventario, data.get("inventario") or {})
    deduplicar_hechos_pipeline_v3(hechos)
    completar_inventario_desde_hechos_pipeline_v3(inventario, hechos)
    return {
        "hechos": hechos,
        "inventario": inventario,
        "cobertura": {
            "cantidad_segmentos_entrada": len(segmentos),
            "cantidad_segmentos_considerados": sum(len(bloque) for bloque in bloques),
            "cantidad_bloques": len(bloques),
        },
    }


def evaluar_criterios_desde_hechos(client, segmentos: List[Dict], hechos: Dict, pauta: Optional[List[Dict]] = None) -> List[Dict]:
    matriz = matriz_tecnica_para_pauta(pauta)
    if pauta:
        instrucciones_estado = """
Estados permitidos para esta pauta:
- CUMPLE: la conducta se observa suficientemente.
- NO_CUMPLE: existe incumplimiento observable y evidencia verificable.
- NO_APLICA: el criterio legítimamente no corresponde a esta llamada.
- NO_EVALUABLE: el criterio corresponde, pero la fuente necesaria no está disponible en audio/transcripción.
- REQUIERE_REVISION: existe evidencia ambigua, roles dudosos o posible falta crítica que requiere validación humana.

No uses NO_APLICA por falta de información. Usa NO_EVALUABLE cuando la fuente sea CRM, TIPIFICACION, CAMPANIA o SISTEMA y no esté disponible.
No uses REQUIERE_REVISION como salida genérica por falta de IDs. Para criterios observables ordinarios decide CUMPLE o NO_CUMPLE según hechos y segmentos.
Para CUMPLE, segmentos_evidencia es recomendable pero no obligatorio si conducta_observada y hallazgo explican el cumplimiento.
Para NO_CUMPLE observable, segmentos_evidencia o segmentos_contexto es obligatorio. Para faltas críticas o posibles descalificaciones, la evidencia debe ser de AGENTE con confianza suficiente.
Usa REQUIERE_REVISION solo si la evidencia existe pero es ambigua, el rol AGENTE/CLIENTE es dudoso, hay contradicción real o la falta crítica necesita validación humana.
"""
        contrato_estado = "CUMPLE|NO_CUMPLE|NO_APLICA|NO_EVALUABLE|REQUIERE_REVISION"
    else:
        instrucciones_estado = """
Estados permitidos:
- CUMPLE
- PARCIAL_ALTO
- PARCIAL_MEDIO
- PARCIAL_BAJO
- NO_CUMPLE
- NO_EVALUABLE
- REQUIERE_REVISION
"""
        contrato_estado = "CUMPLE|PARCIAL_ALTO|PARCIAL_MEDIO|PARCIAL_BAJO|NO_CUMPLE|NO_EVALUABLE|REQUIERE_REVISION"
    prompt = f"""
Evalua exclusivamente la llamada actual usando segmentos y hechos extraidos.
Devuelve exactamente {len(matriz)} criterios tecnicos. No decidas grupo SGC ni criticidad; usa los codigos entregados.
Usa segmentos_evidencia como fuente principal. No inventes citas.
NO_CUMPLE solo si hubo oportunidad clara y la conducta fallo. Si falta evidencia usa NO_EVALUABLE o REQUIERE_REVISION.
{instrucciones_estado}

Matriz:
{json.dumps(matriz, ensure_ascii=False)}

Segmentos completos:
{json.dumps(segmentos, ensure_ascii=False)}

Hechos:
{json.dumps(hechos, ensure_ascii=False)}

Devuelve JSON:
{{"criterios": [
  {{"codigo": "", "nombre": "", "peso": 0, "estado": "{contrato_estado}", "puntaje_obtenido": 0, "segmentos_evidencia": [], "segmentos_contexto": [], "tipo_evidencia": "DIRECTA|CONTEXTUAL|AUSENCIA_EN_SECUENCIA|REVISION_HUMANA", "conducta_observada": "", "hallazgo": "", "impacto_negocio": "", "impacto_cliente": "", "recomendacion_entrenable": "", "frase_sugerida": "", "fortaleza_relacionada": null, "confianza": "ALTA|MEDIA|BAJA", "posible_descalificacion": false, "justificacion_descalificacion": null}}
]}}
""".strip()
    data = llamar_json_modelo_pipeline_v3(client, prompt, "Evalua criterios tecnicos desde hechos; no generes score global ni SGC.")
    return data.get("criterios") if isinstance(data.get("criterios"), list) else []


def auditar_evaluacion(client, segmentos: List[Dict], hechos: Dict, criterios: List[Dict]) -> Dict:
    prompt = f"""
Audita consistencia de una evaluacion ya generada. No evalues desde cero.
Busca contradicciones entre hechos, segmentos y criterios.
Ejemplos generales: si hechos contienen monto/fecha/confirmacion y el criterio correspondiente esta NO_CUMPLE sin justificacion, marcar contradiccion.
Si un criterio de respeto esta NO_CUMPLE sin evidencia negativa, marcar contradiccion.

Segmentos:
{json.dumps(segmentos, ensure_ascii=False)}

Hechos:
{json.dumps(hechos, ensure_ascii=False)}

Criterios:
{json.dumps(criterios, ensure_ascii=False)}

Devuelve JSON:
{{"inconsistencias": [{{"criterio": "4.1", "tipo": "CONTRADICCION|EVIDENCIA_INSUFICIENTE|COBERTURA", "descripcion": "", "segmentos": [], "accion": "REVISAR_CRITERIO|SIN_CAMBIO"}}]}}
""".strip()
    data = llamar_json_modelo_pipeline_v3(client, prompt, "Audita contradicciones sin reevaluar toda la llamada.")
    inconsistencias = data.get("inconsistencias") if isinstance(data.get("inconsistencias"), list) else []
    return {"inconsistencias": inconsistencias}


def corregir_criterios_inconsistentes(
    client,
    segmentos: List[Dict],
    hechos: Dict,
    criterios: List[Dict],
    auditoria: Dict,
    pauta: Optional[List[Dict]] = None,
) -> tuple[List[Dict], List[str]]:
    inconsistencias = [
        item for item in auditoria.get("inconsistencias", [])
        if isinstance(item, dict) and item.get("criterio") and item.get("accion") == "REVISAR_CRITERIO"
    ]
    if not inconsistencias:
        return criterios, []
    criterios_por_codigo = {str(item.get("codigo") or ""): item for item in criterios if isinstance(item, dict)}
    cuestionados = [criterios_por_codigo.get(str(item.get("criterio"))) for item in inconsistencias]
    cuestionados = [item for item in cuestionados if item]
    estados = "CUMPLE|NO_CUMPLE|NO_APLICA|NO_EVALUABLE|REQUIERE_REVISION" if pauta else "CUMPLE|PARCIAL_ALTO|PARCIAL_MEDIO|PARCIAL_BAJO|NO_CUMPLE|NO_EVALUABLE|REQUIERE_REVISION"
    prompt = f"""
Corrige solo los criterios cuestionados. No analices criterios no listados.
Usa segmentos_evidencia por ID y no inventes citas.
Respeta estos estados permitidos: {estados}.

Segmentos relacionados y completos:
{json.dumps(segmentos, ensure_ascii=False)}

Hechos:
{json.dumps(hechos, ensure_ascii=False)}

Criterios cuestionados:
{json.dumps(cuestionados, ensure_ascii=False)}

Observaciones auditor:
{json.dumps(inconsistencias, ensure_ascii=False)}

Devuelve JSON:
{{"criterios": [{{"codigo": "", "nombre": "", "peso": 0, "estado": "{estados}", "puntaje_obtenido": 0, "segmentos_evidencia": [], "segmentos_contexto": [], "tipo_evidencia": "DIRECTA|CONTEXTUAL|AUSENCIA_EN_SECUENCIA|REVISION_HUMANA", "conducta_observada": "", "hallazgo": "", "impacto_negocio": "", "impacto_cliente": "", "recomendacion_entrenable": "", "frase_sugerida": "", "fortaleza_relacionada": null, "confianza": "ALTA|MEDIA|BAJA", "posible_descalificacion": false, "justificacion_descalificacion": null}}]}}
""".strip()
    data = llamar_json_modelo_pipeline_v3(client, prompt, "Corrige criterios puntuales observados por auditoria.")
    corregidos = normalizar_criterios_pipeline_v3(data.get("criterios") if isinstance(data.get("criterios"), list) else [], segmentos, pauta=pauta)
    codigos_cuestionados = {
        str(item.get("criterio") or "").strip()
        for item in inconsistencias
        if str(item.get("criterio") or "").strip()
    }
    if codigos_cuestionados:
        corregidos = [
            item for item in corregidos
            if str(item.get("codigo") or item.get("codigo_criterio") or "").strip() in codigos_cuestionados
        ]
    salida = list(criterios)
    indices = {str(item.get("codigo") or ""): idx for idx, item in enumerate(salida)}
    codigos = []
    for item in corregidos:
        codigo = str(item.get("codigo") or "")
        if codigo in indices:
            salida[indices[codigo]] = item
            codigos.append(codigo)
    return salida, codigos


def generar_feedback_desde_evaluacion(client, segmentos: List[Dict], hechos: Dict, criterios: List[Dict], score: Dict) -> Dict:
    prompt = f"""
Genera feedback y coaching solo desde la evaluacion final validada.
No cambies score ni criterios. No reinterpretes la llamada desde cero.
El feedback debe reconocer fortalezas observables y priorizar la brecha de mayor impacto.

Segmentos:
{json.dumps(segmentos, ensure_ascii=False)}

Hechos:
{json.dumps(hechos, ensure_ascii=False)}

Criterios finales:
{json.dumps(criterios, ensure_ascii=False)}

Score Python:
{json.dumps(score, ensure_ascii=False)}

Devuelve JSON:
{{"resumen_ejecutivo": {{"texto": "", "fortaleza_principal": "", "debilidad_principal": "", "riesgo_principal": "", "oportunidad_principal": "", "conclusion": ""}}, "resultado_gestion": {{"tipo_contacto": "", "resultado_principal": "", "tipo_cierre": "", "monto_acordado": null, "fecha_acordada": null, "canal_acordado": null, "confirmacion_cliente": false, "resumen": ""}}, "tipificaciones_sugeridas": [], "coaching": {{"feedback_supervisor": {{"resumen_tecnico": "", "fortalezas": [], "brechas_principales": [], "conducta_prioritaria": "", "accion_entrenable": "", "objetivo_siguiente_llamada": ""}}, "feedback_asesor": {{"mensaje": "", "lo_que_hiciste_bien": "", "mejora_prioritaria": "", "frase_a_evitar": "", "frase_recomendada": "", "ejemplo_mejorado": "", "compromiso_sugerido": ""}}}}}}
""".strip()
    return llamar_json_modelo_pipeline_v3(client, prompt, "Genera feedback final desde matriz validada.")


def llamar_json_modelo_pipeline_v3(client, prompt: str, system: str) -> Dict:
    response = client.chat.completions.create(
        model=ANALYSIS_MODEL,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": f"{system} Responde exclusivamente JSON valido y trabaja solo con la llamada actual."},
            {"role": "user", "content": prompt},
        ],
    )
    return cargar_json_analisis(response.choices[0].message.content or "{}", client=client)


def bloques_segmentos_pipeline_v3(segmentos: List[Dict], size: int = 120) -> List[List[Dict]]:
    if not segmentos:
        return []
    return [segmentos[i:i + size] for i in range(0, len(segmentos), size)]


def categorias_hechos_pipeline_v3() -> List[str]:
    return [
        "identificacion_agente", "identificacion_entidad", "validacion_titularidad",
        "causas_no_pago", "capacidad_pago", "situacion_economica", "fuente_dinero",
        "montos_mencionados", "fechas_mencionadas", "objeciones_cliente", "respuestas_objeciones",
        "propuestas_agente", "alternativas_pago", "inducciones_pago", "aceptaciones_cliente",
        "rechazos_cliente", "canales_pago", "compromisos", "recapitulaciones",
        "siguientes_acciones", "frases_riesgo", "empatia", "faltas_empatia", "despedida",
    ]


def inventario_vacio_pipeline_v3() -> Dict:
    claves = [
        "apertura.saludo", "apertura.identificacion_agente", "apertura.identificacion_entidad", "apertura.titularidad", "apertura.motivo",
        "diagnostico.causa", "diagnostico.capacidad", "diagnostico.fecha_probable", "diagnostico.monto_disponible", "diagnostico.situacion_economica",
        "negociacion.propuesta", "negociacion.objecion", "negociacion.respuesta_objecion", "negociacion.adaptacion", "negociacion.alternativas", "negociacion.induccion",
        "cierre.cantidad", "cierre.fecha", "cierre.canal", "cierre.confirmacion", "cierre.recapitulacion", "cierre.siguiente_accion",
        "experiencia.respeto", "experiencia.empatia", "experiencia.presion", "experiencia.lenguaje_riesgoso", "experiencia.despedida",
    ]
    return {clave: {"encontrado": False, "segmentos": []} for clave in claves}


def normalizar_hechos_pipeline_v3(items: List[Dict], segmentos: List[Dict]) -> List[Dict]:
    segmentos_por_id = {int(item.get("segmento_id") or 0): item for item in segmentos}
    salida = []
    for raw in items:
        if not isinstance(raw, dict):
            continue
        segmento_id = normalizar_segmento_id_pipeline_v3(raw.get("segmento_id"), segmentos_por_id)
        segmento = segmentos_por_id.get(segmento_id, {})
        texto = str(segmento.get("texto") or raw.get("texto") or "").strip()
        if not texto:
            continue
        salida.append({
            "segmento_id": segmento_id,
            "hablante": normalizar_hablante_v2(raw.get("hablante") or segmento.get("hablante")),
            "texto": texto,
            "tipo": str(raw.get("tipo") or "").strip(),
            "interpretacion": str(raw.get("interpretacion") or "").strip(),
            "confianza": normalizar_confianza(raw.get("confianza") or segmento.get("confianza")),
        })
    return salida


def normalizar_segmento_id_pipeline_v3(value, segmentos_por_id: Dict[int, Dict]) -> int:
    try:
        segmento_id = int(value)
    except (TypeError, ValueError):
        return 0
    return segmento_id if segmento_id in segmentos_por_id else 0


def fusionar_inventario_pipeline_v3(inventario: Dict, parcial: Dict) -> None:
    if not isinstance(parcial, dict):
        return
    for clave, value in parcial.items():
        if not isinstance(value, dict):
            continue
        actual = inventario.setdefault(clave, {"encontrado": False, "segmentos": []})
        segmentos = [int(x) for x in value.get("segmentos", []) if str(x).isdigit()]
        actual["encontrado"] = bool(actual.get("encontrado") or value.get("encontrado") or segmentos)
        actual["segmentos"] = sorted(set([*actual.get("segmentos", []), *segmentos]))


def deduplicar_hechos_pipeline_v3(hechos: Dict) -> None:
    for categoria, items in list(hechos.items()):
        vistos = set()
        salida = []
        for item in items:
            clave = (item.get("segmento_id"), limpiar_key_texto(item.get("tipo")), limpiar_key_texto(item.get("texto")))
            if clave in vistos:
                continue
            vistos.add(clave)
            salida.append(item)
        hechos[categoria] = salida


def completar_inventario_desde_hechos_pipeline_v3(inventario: Dict, hechos: Dict) -> None:
    mapa = {
        "apertura.saludo": ["identificacion_agente"],
        "apertura.identificacion_agente": ["identificacion_agente"],
        "apertura.identificacion_entidad": ["identificacion_entidad"],
        "apertura.titularidad": ["validacion_titularidad"],
        "diagnostico.causa": ["causas_no_pago"],
        "diagnostico.capacidad": ["capacidad_pago"],
        "diagnostico.fecha_probable": ["fechas_mencionadas"],
        "diagnostico.monto_disponible": ["montos_mencionados"],
        "diagnostico.situacion_economica": ["situacion_economica", "fuente_dinero"],
        "negociacion.propuesta": ["propuestas_agente", "alternativas_pago"],
        "negociacion.objecion": ["objeciones_cliente"],
        "negociacion.respuesta_objecion": ["respuestas_objeciones"],
        "negociacion.induccion": ["inducciones_pago"],
        "cierre.cantidad": ["compromisos", "montos_mencionados"],
        "cierre.fecha": ["compromisos", "fechas_mencionadas"],
        "cierre.canal": ["canales_pago"],
        "cierre.confirmacion": ["aceptaciones_cliente"],
        "cierre.recapitulacion": ["recapitulaciones"],
        "cierre.siguiente_accion": ["siguientes_acciones"],
        "experiencia.empatia": ["empatia"],
        "experiencia.presion": ["frases_riesgo"],
        "experiencia.lenguaje_riesgoso": ["frases_riesgo"],
        "experiencia.despedida": ["despedida"],
    }
    for clave, categorias in mapa.items():
        segmentos = []
        for categoria in categorias:
            segmentos.extend([item.get("segmento_id") for item in hechos.get(categoria, []) if item.get("segmento_id")])
        if segmentos:
            actual = inventario.setdefault(clave, {"encontrado": False, "segmentos": []})
            actual["encontrado"] = True
            actual["segmentos"] = sorted(set([*actual.get("segmentos", []), *segmentos]))


def matriz_tecnica_pipeline_v3() -> List[Dict]:
    return [
        {
            "codigo": codigo_item_canonico(item),
            "nombre": nombre_item_sin_codigo(item),
            "dimension": segmento,
            "peso": peso,
        }
        for segmento, item, peso in COPC_ITEMS_CANONICOS
    ]


def codigo_item_canonico(item: str) -> str:
    match = re.match(r"^\s*(\d+\.\d+)", str(item or ""))
    return match.group(1) if match else ""


def nombre_item_sin_codigo(item: str) -> str:
    return re.sub(r"^\s*\d+\.\d+\s*", "", str(item or "")).strip()


def normalizar_criterios_pipeline_v3(
    criterios: List[Dict],
    segmentos: List[Dict],
    pauta: Optional[List[Dict]] = None,
) -> List[Dict]:
    if pauta:
        por_codigo = {
            codigo_criterio_pauta(item): (
                str(item.get("subcategoria") or item.get("bloque") or ""),
                str(item.get("nombre") or ""),
                float(item.get("peso") or 0),
                item,
            )
            for item in pauta
        }
    else:
        por_codigo = {
            codigo_item_canonico(item): (segmento, nombre_item_sin_codigo(item), peso, {})
            for segmento, item, peso in COPC_ITEMS_CANONICOS
        }
    segmentos_por_id = {int(item.get("segmento_id") or 0): item for item in segmentos}
    salida = []
    entrada = {
        str(item.get("codigo") or item.get("codigo_criterio") or "").strip().upper(): item
        for item in criterios
        if isinstance(item, dict)
    }
    for codigo, (segmento, nombre_criterio, peso, meta) in por_codigo.items():
        raw = entrada.get(codigo) or {}
        raw = entrada.get(str(codigo).upper()) or {}
        estado = normalizar_estado_criterio_v2(raw.get("estado") or raw.get("resultado"))
        evidencia_ids = normalizar_ids_segmentos_pipeline_v3(raw.get("segmentos_evidencia"), segmentos_por_id)
        contexto_ids = normalizar_ids_segmentos_pipeline_v3(raw.get("segmentos_contexto"), segmentos_por_id)
        evidencia_textual = [segmentos_por_id[item]["texto"] for item in evidencia_ids if item in segmentos_por_id]
        if pauta:
            estado = normalizar_estado_mibanco_pipeline_v3(estado)
            estado = aplicar_reglas_fuente_mibanco_v3(estado, meta, evidencia_ids, contexto_ids, segmentos_por_id)
            nota = puntaje_mibanco_pipeline_v3(estado, peso)
        else:
            nota = puntaje_pipeline_v3(raw.get("puntaje_obtenido"), estado, peso)
        salida.append({
            "codigo": codigo,
            "codigo_criterio": codigo,
            "nombre": nombre_criterio,
            "dimension": segmento,
            "segmento_copc": segmento,
            "bloque": meta.get("bloque"),
            "categoria": meta.get("categoria"),
            "subcategoria": meta.get("subcategoria"),
            "peso": peso,
            "puntaje_maximo": peso,
            "estado": estado,
            "resultado": resultado_legacy_desde_estado_v2(estado),
            "puntaje_obtenido": nota,
            "nota": nota,
            "nota_ia": nota,
            "nota_final": nota,
            "segmentos_evidencia": evidencia_ids,
            "segmentos_contexto": contexto_ids,
            "tipo_evidencia": normalizar_tipo_evidencia_pipeline_v3(raw.get("tipo_evidencia")),
            "conducta_observada": str(raw.get("conducta_observada") or "").strip(),
            "hallazgo": str(raw.get("hallazgo") or "").strip(),
            "impacto_negocio": str(raw.get("impacto_negocio") or "").strip(),
            "impacto_cliente": str(raw.get("impacto_cliente") or "").strip(),
            "recomendacion_entrenable": str(raw.get("recomendacion_entrenable") or "").strip(),
            "frase_sugerida": str(raw.get("frase_sugerida") or "").strip(),
            "fortaleza_relacionada": raw.get("fortaleza_relacionada"),
            "confianza": normalizar_confianza(raw.get("confianza")),
            "detalle": meta.get("detalle"),
            "regla_evaluacion": meta.get("regla_evaluacion"),
            "criticidad": meta.get("criticidad"),
            "fuente_evidencia": meta.get("fuente_evidencia"),
            "regla_aplicabilidad": meta.get("regla_aplicabilidad"),
            "regla_cumple": meta.get("regla_cumple"),
            "regla_no_cumple": meta.get("regla_no_cumple"),
            "puede_descalificar": bool(meta.get("puede_descalificar")),
            "requiere_evidencia": bool(meta.get("requiere_evidencia")),
            "tipo_criterio": meta.get("tipo_criterio") or "PUNTUABLE",
            "anula_bloque": str(meta.get("tipo_criterio") or "").upper() == "ANULANTE_BLOQUE",
            "recomendacion_configurada": meta.get("recomendacion"),
            "posible_descalificacion": bool(raw.get("posible_descalificacion")),
            "justificacion_descalificacion": raw.get("justificacion_descalificacion"),
            "evidencia_textual": evidencia_textual,
        })
    return salida


def normalizar_estado_mibanco_pipeline_v3(estado: str) -> str:
    estado = normalizar_estado_criterio_v2(estado)
    if estado in ESTADOS_MIBANCO:
        return estado
    if estado.startswith("PARCIAL"):
        return "REQUIERE_REVISION"
    return "REQUIERE_REVISION"


def aplicar_reglas_fuente_mibanco_v3(
    estado: str,
    meta: Dict,
    evidencia_ids: List[int],
    contexto_ids: List[int],
    segmentos_por_id: Dict[int, Dict],
) -> str:
    fuente = str(meta.get("fuente_evidencia") or "").strip().upper()
    requiere_evidencia = bool(meta.get("requiere_evidencia"))
    puede_descalificar = bool(meta.get("puede_descalificar"))
    criticidad = str(meta.get("criticidad") or "").strip().upper()

    if fuente and not fuente_observable_en_audio(fuente):
        return "NO_EVALUABLE"

    if estado == "NO_CUMPLE" and requiere_evidencia and not (evidencia_ids or contexto_ids):
        return "REQUIERE_REVISION"

    if estado == "NO_CUMPLE" and (puede_descalificar or criticidad == "ERROR_CRITICO_CUMPLIMIENTO"):
        ids = evidencia_ids or contexto_ids
        if not ids:
            return "REQUIERE_REVISION"
        roles = {
            normalizar_hablante_v2((segmentos_por_id.get(segmento_id) or {}).get("hablante") or (segmentos_por_id.get(segmento_id) or {}).get("rol"))
            for segmento_id in ids
        }
        if "AGENTE" not in roles:
            return "REQUIERE_REVISION"
        if "NO_DETERMINADO" in roles and puede_descalificar:
            return "REQUIERE_REVISION"

    return estado


def puntaje_mibanco_pipeline_v3(estado: str, peso: float) -> float:
    return float(peso) if estado == "CUMPLE" else 0.0


def normalizar_ids_segmentos_pipeline_v3(value, segmentos_por_id: Dict[int, Dict]) -> List[int]:
    if not isinstance(value, list):
        value = []
    salida = []
    for item in value:
        try:
            segmento_id = int(item)
        except (TypeError, ValueError):
            continue
        if segmento_id in segmentos_por_id and segmento_id not in salida:
            salida.append(segmento_id)
    return salida


def normalizar_tipo_evidencia_pipeline_v3(value) -> str:
    texto = limpiar_key_texto(value)
    if "ausencia" in texto:
        return "AUSENCIA_EN_SECUENCIA"
    if "revision" in texto or "humana" in texto:
        return "REVISION_HUMANA"
    if "context" in texto:
        return "CONTEXTUAL"
    return "DIRECTA"


def puntaje_pipeline_v3(value, estado: str, peso: float) -> float:
    if value not in (None, ""):
        return numero_en_rango(value, 0, peso)
    if estado == "CUMPLE":
        return float(peso)
    if estado == "PARCIAL_ALTO":
        return round(float(peso) * 0.75, 2)
    if estado == "PARCIAL_MEDIO":
        return round(float(peso) * 0.5, 2)
    if estado == "PARCIAL_BAJO":
        return round(float(peso) * 0.25, 2)
    return 0.0


def aplicar_guardas_deterministicas_criterios(segmentos: List[Dict], criterios: List[Dict]) -> List[Dict]:
    """
    Corrige contradicciones evidentes entre segmentos canónicos y criterios.

    No intenta reevaluar toda la llamada ni reemplaza a la IA. Solo impide que
    conductas observables simples queden como NO_CUMPLE cuando la propia
    transcripción demuestra lo contrario.
    """
    salida = [dict(item) for item in criterios]
    por_codigo = {str(item.get("codigo") or item.get("codigo_criterio") or ""): item for item in salida}
    segmentos_ordenados = sorted(
        [item for item in segmentos if isinstance(item, dict)],
        key=lambda item: (
            item.get("inicio_segundos") is None,
            item.get("inicio_segundos") or 0,
            item.get("segmento_id") or 0,
        ),
    )
    texto_agente = limpiar_key_texto(" ".join(
        str(item.get("texto") or item.get("texto_original") or "")
        for item in segmentos_ordenados
        if normalizar_hablante_v2(item.get("hablante") or item.get("rol")) == "AGENTE"
    ))
    texto_cliente = limpiar_key_texto(" ".join(
        str(item.get("texto") or item.get("texto_original") or "")
        for item in segmentos_ordenados
        if normalizar_hablante_v2(item.get("hablante") or item.get("rol")) == "CLIENTE"
    ))

    # 1.1: saludo + identificación del agente.
    saludo_agente = buscar_segmentos_por_tokens_v3(segmentos_ordenados, "AGENTE", {"hola", "buenos dias", "buenas tardes", "buenas noches"})
    identidad_agente = buscar_segmentos_por_tokens_v3(segmentos_ordenados, "AGENTE", {"le habla", "habla", "te saluda", "le saluda", "mi nombre", "soy", "se comunica"})
    if saludo_agente and identidad_agente:
        aplicar_resultado_guardado_v3(
            por_codigo.get("1.1"),
            "CUMPLE",
            [saludo_agente[0], identidad_agente[0]],
            "El agente saluda y comunica su identidad durante la apertura.",
            "Mantener una apertura clara con saludo e identificación.",
        )
    elif saludo_agente or identidad_agente:
        aplicar_resultado_guardado_v3(
            por_codigo.get("1.1"),
            "PARCIAL_MEDIO",
            [(saludo_agente or identidad_agente)[0]],
            "La apertura contiene saludo o identificación, pero queda incompleta.",
            "Completar saludo e identificación del gestor en la apertura.",
        )

    # 1.2: entidad/cartera mencionada. "mi banco" evidencia referencia a entidad,
    # aunque puede quedar parcial si no se nombra de forma específica.
    entidad_nominal = buscar_segmentos_por_tokens_v3(segmentos_ordenados, "AGENTE", {"mibanco", "mi banco", "banco", "entidad", "cartera"})
    if entidad_nominal:
        estado = "CUMPLE" if any("mibanco" in limpiar_key_texto(seg.get("texto") or "") for seg in entidad_nominal) else "PARCIAL_MEDIO"
        aplicar_resultado_guardado_v3(
            por_codigo.get("1.2"),
            estado,
            [entidad_nominal[0]],
            "El agente menciona la entidad o cartera en cuyo nombre realiza la gestión.",
            "Nombrar la entidad de forma explícita para evitar ambigüedad.",
        )

    # 1.3: validación de titularidad por pregunta al titular y respuesta afirmativa/contextual.
    titularidad = detectar_titularidad_contextual_v3(segmentos_ordenados)
    if titularidad:
        aplicar_resultado_guardado_v3(
            por_codigo.get("1.3"),
            "CUMPLE",
            titularidad,
            "Se valida de forma suficiente que la conversación es con la persona consultada.",
            "Mantener validación de titularidad antes de exponer información sensible.",
        )

    # 2.2: capacidad actual de pago. Si se pregunta por capacidad/monto recaudado
    # o el cliente explica capacidad actual, no puede quedar como falta total de indagación.
    pregunta_capacidad = buscar_segmentos_por_tokens_v3(
        segmentos_ordenados,
        "AGENTE",
        {"cuanto", "cuánto", "ha podido recaudar", "puede pagar", "podria pagar", "podría pagar", "capacidad", "abonar"},
    )
    respuesta_capacidad = buscar_segmentos_por_tokens_v3(
        segmentos_ordenados,
        "CLIENTE",
        {"no puedo", "no me encuentro", "problemas", "estoy pagando", "he podido", "puedo", "juntando", "recaudar", "dinero"},
    )
    if pregunta_capacidad and respuesta_capacidad:
        aplicar_resultado_guardado_v3(
            por_codigo.get("2.2"),
            "CUMPLE",
            [pregunta_capacidad[0], respuesta_capacidad[0]],
            "Se explora y se obtiene información sobre la capacidad actual de pago.",
            "Profundizar monto exacto disponible cuando el cliente describe su capacidad.",
        )
    elif pregunta_capacidad or respuesta_capacidad:
        aplicar_resultado_guardado_v3(
            por_codigo.get("2.2"),
            "PARCIAL_ALTO",
            [(pregunta_capacidad or respuesta_capacidad)[0]],
            "Existe información o indagación sobre capacidad, pero faltó precisar mejor el monto disponible.",
            "Preguntar el monto exacto que el cliente puede asumir.",
        )

    # 5.1: respeto y ausencia de juicio. No convertir una despedida cordial o
    # lenguaje neutro en falta de respeto si no existe evidencia negativa.
    lenguaje_negativo = any(token in texto_agente for token in {
        "mentiroso", "irresponsable", "no quiere pagar", "usted nunca paga",
        "amenaza", "judicial", "embargo", "denuncia", "mal cliente",
        "tiene que pagar porque si", "no le importa",
    })
    despedida_cordial = buscar_segmentos_por_tokens_v3(
        segmentos_ordenados,
        "AGENTE",
        {"buen dia", "buen día", "hasta luego", "gracias", "que tenga"},
    )
    criterio_respeto = por_codigo.get("5.1")
    if criterio_respeto and not lenguaje_negativo and texto_agente:
        evidencia = despedida_cordial[:1] or buscar_segmentos_por_tokens_v3(segmentos_ordenados, "AGENTE", {"señora", "senora", "señor", "senor"})[:1]
        aplicar_resultado_guardado_v3(
            criterio_respeto,
            "CUMPLE",
            evidencia,
            "No se evidencia juicio, maltrato ni lenguaje ofensivo del agente.",
            "Mantener trato respetuoso y lenguaje profesional.",
        )

    aplicar_guardas_mibanco_v3(segmentos_ordenados, por_codigo)
    return salida


def aplicar_guardas_mibanco_v3(segmentos: List[Dict], por_codigo: Dict[str, Dict]) -> None:
    """
    Reglas determinísticas para la pauta Mibanco vigente.

    La IA aporta evaluación contextual. Python estabiliza aplicabilidad y evita
    que criterios observables desde otras fuentes se castiguen desde audio.
    """
    texto_agente = limpiar_key_texto(" ".join(
        str(item.get("texto") or item.get("texto_original") or "")
        for item in segmentos
        if normalizar_hablante_v2(item.get("hablante") or item.get("rol")) == "AGENTE"
    ))
    texto_cliente = limpiar_key_texto(" ".join(
        str(item.get("texto") or item.get("texto_original") or "")
        for item in segmentos
        if normalizar_hablante_v2(item.get("hablante") or item.get("rol")) == "CLIENTE"
    ))
    segmentos_agente = [
        item for item in segmentos
        if normalizar_hablante_v2(item.get("hablante") or item.get("rol")) == "AGENTE"
    ]
    segmentos_cliente = [
        item for item in segmentos
        if normalizar_hablante_v2(item.get("hablante") or item.get("rol")) == "CLIENTE"
    ]
    evidencia_neutra = segmentos_agente[:1]
    dificultades_cliente = buscar_segmentos_dificultad_cliente_v3(segmentos)
    objeciones_cliente = buscar_segmentos_objecion_cliente_v3(segmentos)
    respuestas_gestion = buscar_segmentos_respuesta_gestion_agente_v3(segmentos)
    tercero_confirmado = buscar_segmentos_tercero_confirmado_mibanco_v3(segmentos)
    corte_abrupto = buscar_segmentos_corte_abrupto_mibanco_v3(segmentos)
    sin_oportunidad_por_tercero_o_corte = bool(tercero_confirmado or corte_abrupto)
    preguntas_causa = buscar_segmentos_sondeo_causa_agente_v3(segmentos)
    causas_cliente = buscar_segmentos_causa_cliente_v3(segmentos)
    preguntas_capacidad = buscar_segmentos_diagnostico_agente_v3(segmentos)
    respuestas_capacidad = buscar_segmentos_capacidad_cliente_v3(segmentos)
    tiene_causa = bool(preguntas_causa or causas_cliente)
    tiene_capacidad = bool(preguntas_capacidad and respuestas_capacidad)

    # PECUF.1: Falta de respeto.
    if por_codigo.get("PECUF.1") and estado_sgc_normalizado(por_codigo["PECUF.1"]) == "REQUIERE_REVISION":
        if not contiene_riesgo_trato_agente_v3(texto_agente):
            aplicar_resultado_guardado_v3(
                por_codigo["PECUF.1"],
                "CUMPLE",
                evidencia_neutra,
                "No se evidencia agresión, ridiculización, descalificación ni expresión ofensiva del agente.",
                "Mantener trato respetuoso durante toda la llamada.",
            )

    # PECUF.2: Escucha activa.
    if por_codigo.get("PECUF.2"):
        if dificultades_cliente or objeciones_cliente:
            base = (dificultades_cliente or objeciones_cliente)[0]
            respuesta = buscar_respuesta_posterior_v3(segmentos, base, "AGENTE", set(), ventana=5)
            aplicar_resultado_guardado_v3(
                por_codigo["PECUF.2"],
                "CUMPLE" if respuesta else "REQUIERE_REVISION",
                [base, *(respuesta[:1] if respuesta else [])],
                "El agente permite la exposición del cliente y continúa la gestión con respuesta posterior." if respuesta else "No queda claro si el agente confirmó o comprendió la información del cliente.",
                "Confirmar comprensión antes de pasar a propuesta o cierre.",
            )
        else:
            estado = "CUMPLE" if segmentos_cliente else "NO_APLICA"
            aplicar_resultado_guardado_v3(
                por_codigo["PECUF.2"],
                estado,
                segmentos_cliente[:1] or evidencia_neutra,
                "La interacción no presenta información adicional que exija confirmación específica." if segmentos_cliente else "No hubo interacción suficiente con el cliente para evaluar escucha activa.",
                "Mantener escucha y confirmar comprensión cuando el cliente entregue información relevante.",
            )

    # PECUF.3: Precisión de la información de la deuda.
    if por_codigo.get("PECUF.3"):
        comunica_deuda = buscar_segmentos_por_tokens_v3(
            segmentos,
            "AGENTE",
            {"deuda", "cuota", "mora", "saldo", "capital", "interes", "interés", "monto", "pagar"},
        )
        if not comunica_deuda:
            aplicar_resultado_guardado_v3(
                por_codigo["PECUF.3"],
                "NO_APLICA",
                [],
                "No se identifica comunicación de deuda, mora, cuota o monto financiero evaluable.",
                "Comunicar información financiera solo cuando corresponda y con datos verificables.",
            )

    # PECUF.4 / PENC.3: Claridad de la información/lenguaje.
    for codigo_claridad in ("PECUF.4", "PENC.3"):
        if por_codigo.get(codigo_claridad) and not contiene_confusion_material_agente_v3(texto_agente):
            aplicar_resultado_guardado_v3(
                por_codigo[codigo_claridad],
                "CUMPLE",
                evidencia_neutra,
                "No se evidencia contradicción, confusión material ni lenguaje incomprensible del agente.",
                "Mantener explicaciones claras, ordenadas y sin contradicciones.",
            )

    # PECN.1: Sondeo y diagnóstico.
    if por_codigo.get("PECN.1"):
        if tiene_causa and tiene_capacidad:
            aplicar_resultado_guardado_v3(
                por_codigo["PECN.1"],
                "CUMPLE",
                [(preguntas_causa or causas_cliente)[0], (preguntas_capacidad or respuestas_capacidad)[0]],
                "El agente obtiene información sobre la causa del atraso y la capacidad actual del cliente.",
                "Profundizar causa, capacidad, monto y fecha para sostener la negociación.",
            )
        elif segmentos_agente or segmentos_cliente:
            aplicar_resultado_guardado_v3(
                por_codigo["PECN.1"],
                "NO_CUMPLE",
                [(preguntas_capacidad or respuestas_capacidad or preguntas_causa or causas_cliente or evidencia_neutra)[0]],
                "El diagnóstico no cubre de forma suficiente la causa del atraso y la capacidad actual de pago.",
                "Completar el diagnóstico con causa, capacidad, monto disponible y fecha.",
            )
        else:
            aplicar_resultado_guardado_v3(
                por_codigo["PECN.1"],
                "NO_CUMPLE",
                evidencia_neutra,
                "No se observa sondeo sobre vínculo, causa, intención o capacidad de pago.",
                "Indagar vínculo con el titular y, cuando corresponda, causa, capacidad, monto y fecha.",
            )

    # PECN.2: Negociación escalonada.
    if por_codigo.get("PECN.2"):
        oportunidad = objeciones_cliente or dificultades_cliente
        if sin_oportunidad_por_tercero_o_corte:
            aplicar_resultado_guardado_v3(
                por_codigo["PECN.2"],
                "NO_APLICA",
                (tercero_confirmado or corte_abrupto)[:1],
                "La llamada no permitió gestionar una alternativa: se confirmó tercero o se produjo corte abrupto antes de responder.",
                "Retomar la gestión con el titular cuando exista una oportunidad válida de negociación.",
            )
        elif oportunidad:
            respuesta_negociacion = buscar_respuesta_posterior_v3(
                segmentos,
                oportunidad[0],
                "AGENTE",
                {"puede", "podemos", "abonar", "pagar", "cuota", "fecha", "alternativa", "opcion", "opción", "solucion", "solución", "fraccionamiento", "convenio", "monto", "recaudar", "descuento", "campana", "campaña", "rebaja", "reajuste", "vigencia"},
                ventana=24,
            )
            negociacion_sustentada = bool(respuesta_negociacion and tiene_causa and tiene_capacidad)
            aplicar_resultado_guardado_v3(
                por_codigo["PECN.2"],
                "CUMPLE" if negociacion_sustentada else "NO_CUMPLE",
                [oportunidad[0], *(respuesta_negociacion[:1] if respuesta_negociacion else [])],
                "Ante la situación del cliente, el agente conduce la gestión con alternativa posterior y basada en el diagnóstico." if negociacion_sustentada else "La gestión no desarrolla una alternativa escalonada sustentada en causa y capacidad de pago.",
                "Mantener negociación escalonada vinculada a capacidad y fecha.",
            )
        else:
            aplicar_resultado_guardado_v3(
                por_codigo["PECN.2"],
                "NO_CUMPLE",
                oportunidad[:1] or evidencia_neutra,
                "No se observa una alternativa concreta y adaptada que conduzca la gestión hacia pago o siguiente acción.",
                "Ofrecer alternativa viable o abono acorde a la capacidad del cliente.",
            )

    # PECN.3: Manejo de objeciones.
    if por_codigo.get("PECN.3"):
        if sin_oportunidad_por_tercero_o_corte:
            aplicar_resultado_guardado_v3(
                por_codigo["PECN.3"],
                "NO_APLICA",
                (tercero_confirmado or corte_abrupto)[:1],
                "La llamada no permitió abordar una objeción: se confirmó tercero o se produjo corte abrupto antes de responder.",
                "Retomar la gestión con el titular cuando exista una oportunidad válida de negociación.",
            )
        elif not objeciones_cliente:
            estado = "CUMPLE" if respuestas_gestion else "NO_CUMPLE"
            aplicar_resultado_guardado_v3(
                por_codigo["PECN.3"],
                estado,
                respuestas_gestion[:1] or evidencia_neutra,
                "No surge una objeción explícita; la gestión continúa con una conducción orientada a solución." if respuestas_gestion else "No se identifica objeción explícita ni conducción posterior suficiente de la gestión.",
                "Ante dudas, postergaciones o restricciones, explorar la condición y orientar una alternativa concreta.",
            )
        else:
            respuesta_objecion = buscar_respuesta_posterior_v3(
                segmentos,
                objeciones_cliente[0],
                "AGENTE",
                {"puede", "puedes", "abonar", "pagar", "cuanto", "cuánto", "fecha", "alternativa", "opcion", "opción", "solucion", "solución", "recaudar", "monto", "descuento", "campana", "campaña", "rebaja", "reajuste", "vigencia"},
                ventana=24,
            )
            aplicar_resultado_guardado_v3(
                por_codigo["PECN.3"],
                "CUMPLE" if respuesta_objecion else "NO_CUMPLE",
                [objeciones_cliente[0], *(respuesta_objecion[:1] if respuesta_objecion else [])],
                "El agente aborda la objeción del cliente con una respuesta orientada a solución." if respuesta_objecion else "El cliente presenta una objeción y no se observa abordaje posterior suficiente.",
                "Explorar alternativa, monto o fecha frente a cada objeción relevante.",
            )

    # PECN.4: Cierre de negociación.
    if por_codigo.get("PECN.4"):
        compromiso = buscar_segmentos_compromiso_confirmado_mibanco_v3(segmentos)
        siguiente_accion = buscar_segmentos_siguiente_accion_confirmada_mibanco_v3(segmentos)
        if sin_oportunidad_por_tercero_o_corte:
            aplicar_resultado_guardado_v3(
                por_codigo["PECN.4"],
                "NO_APLICA",
                (tercero_confirmado or corte_abrupto)[:1],
                "La llamada no permitió inducir cierre: se confirmó tercero o se produjo corte abrupto antes de gestionar.",
                "Retomar el contacto con el titular para conducir una acción verificable.",
            )
        elif not compromiso and not siguiente_accion:
            aplicar_resultado_guardado_v3(
                por_codigo["PECN.4"],
                "NO_CUMPLE",
                respuestas_gestion[:1] or evidencia_neutra,
                "No se identifica promesa de pago ni siguiente acción verificable acordada con el cliente.",
                "Inducir a promesa de pago cuando la conversación permita concretar un compromiso.",
            )
        else:
            aplicar_resultado_guardado_v3(
                por_codigo["PECN.4"],
                "CUMPLE",
                compromiso[:1] or siguiente_accion,
                "Se identifica una promesa de pago o una siguiente acción verificable acordada con el cliente.",
                "Cerrar con promesa o siguiente acción verificable cuando exista disposición de gestión.",
            )

    # PECC.1: Filosofía Biznescob / imagen de Mibanco.
    if por_codigo.get("PECC.1"):
        if not contiene_descredito_mibanco_v3(texto_agente):
            aplicar_resultado_guardado_v3(
                por_codigo["PECC.1"],
                "CUMPLE",
                evidencia_neutra,
                "No se evidencia descrédito a Mibanco, sus colaboradores, áreas, procesos o canales.",
                "Proteger la imagen de Mibanco y explicar procesos sin responsabilizar a terceros.",
            )

    # PECC.2: Confirmación del acuerdo.
    if por_codigo.get("PECC.2"):
        compromiso = buscar_segmentos_compromiso_confirmado_mibanco_v3(segmentos)
        if not compromiso:
            aplicar_resultado_guardado_v3(
                por_codigo["PECC.2"],
                "NO_APLICA",
                [],
                "No se identifica un acuerdo verbal cerrado que requiera speech de confirmación.",
                "Aplicar speech de confirmación cuando exista promesa de pago.",
            )
        else:
            validacion = buscar_segmentos_validacion_acuerdo_agente_v3(segmentos)
            aplicar_resultado_guardado_v3(
                por_codigo["PECC.2"],
                "CUMPLE" if validacion else "REQUIERE_REVISION",
                [compromiso[0], *(validacion[:1] if validacion else [])],
                "El agente confirma verbalmente condiciones del acuerdo." if validacion else "Existe posible compromiso, pero no queda plenamente confirmado mediante speech.",
                "Confirmar verbalmente monto, fecha y condiciones principales del compromiso.",
            )

    # PECC.3: Tipificación de gestión requiere fuente de sistema/tipificación.
    if por_codigo.get("PECC.3"):
        aplicar_resultado_guardado_v3(
            por_codigo["PECC.3"],
            "NO_EVALUABLE",
            [],
            "La tipificación de la gestión requiere fuente de sistema no disponible en el audio.",
            "Contrastar tipificación y observación registrada contra la llamada.",
        )

    # PENC.1: Saludo de bienvenida.
    if por_codigo.get("PENC.1"):
        saludo = buscar_segmentos_por_tokens_v3(segmentos[:8], "AGENTE", {"hola", "aló", "alo", "buen dia", "buen día", "buenos dias", "buenos días", "buenas tardes", "buenas noches", "le saluda", "te saluda", "saludo", "habla"})
        entidad = buscar_segmentos_por_tokens_v3(segmentos[:12], "AGENTE", {"mibanco", "mi banco"})
        estado_saludo = "CUMPLE" if saludo and entidad else ("NO_CUMPLE" if segmentos_agente else "NO_APLICA")
        aplicar_resultado_guardado_v3(
            por_codigo["PENC.1"],
            estado_saludo,
            (saludo[:1] + entidad[:1]) or evidencia_neutra,
            "El agente saluda e identifica representación de Mibanco." if saludo and entidad else ("La llamada se interrumpe antes de una apertura atribuible al agente." if not segmentos_agente else "La apertura no incluye saludo e identificación completa en representación de Mibanco."),
            "Saludar indicando nombre/apellidos y representación de Mibanco.",
        )

    # PENC.2: Tono de voz. Sin análisis acústico avanzado, no castigar desde texto.
    if por_codigo.get("PENC.2") and estado_sgc_normalizado(por_codigo["PENC.2"]) == "REQUIERE_REVISION":
        aplicar_resultado_guardado_v3(
            por_codigo["PENC.2"],
            "CUMPLE",
            evidencia_neutra,
            "No se identifica evidencia textual suficiente de tono inadecuado en la transcripción disponible.",
            "Mantener tono, velocidad y dicción adecuados.",
        )

    # PENC.4: Despedida adecuada.
    if por_codigo.get("PENC.4"):
        despedida = buscar_segmentos_por_tokens_v3(segmentos[-8:], "AGENTE", {"gracias", "hasta luego", "buen dia", "buen día", "buenas tardes", "que tenga"})
        if despedida:
            aplicar_resultado_guardado_v3(
                por_codigo["PENC.4"],
                "CUMPLE",
                despedida[:1],
                "El agente cierra la llamada con despedida cordial.",
                "Mantener despedida profesional al finalizar la gestión.",
            )


def contiene_riesgo_trato_agente_v3(texto_agente: str) -> bool:
    tokens = {
        "mentiroso", "irresponsable", "sinverguenza", "sinvergüenza",
        "usted nunca paga", "no quiere pagar", "mal cliente", "burla",
        "ridiculiza", "humilla", "callese", "cállese", "no entiende nada",
    }
    texto = limpiar_key_texto(texto_agente)
    return any(limpiar_key_texto(token) in texto for token in tokens)


def contiene_corte_deliberado_v3(texto_agente: str) -> bool:
    tokens = {
        "le voy a cortar", "voy a cortar", "corto la llamada",
        "ya no la atiendo", "no tengo tiempo para atender",
    }
    texto = limpiar_key_texto(texto_agente)
    return any(limpiar_key_texto(token) in texto for token in tokens)


def contiene_confusion_material_agente_v3(texto_agente: str) -> bool:
    tokens = {
        "me equivoque", "me equivoqué", "no era", "corrijo",
        "disculpe no es", "no se entiende", "no le puedo explicar",
        "no se como", "no sé como", "no sé cómo", "no tengo claro",
        "confundi", "confundí", "confusion", "confusión",
    }
    texto = limpiar_key_texto(texto_agente)
    return any(limpiar_key_texto(token) in texto for token in tokens)


def contiene_descredito_mibanco_v3(texto_agente: str) -> bool:
    tokens = {
        "culpa de mibanco", "culpa del banco", "mibanco se equivoco",
        "mibanco se equivocó", "el banco se equivoco", "el banco se equivocó",
        "mibanco no sabe", "mi banco no sabe", "mibanco no funciona",
        "mi banco no funciona", "problema de mibanco", "problema del banco",
        "ellos se equivocaron", "el area se equivoco", "el área se equivocó",
        "no hacen bien su trabajo", "no registraron bien", "le informaron mal",
    }
    texto = limpiar_key_texto(texto_agente)
    return any(limpiar_key_texto(token) in texto for token in tokens)


def buscar_segmentos_objecion_cliente_v3(segmentos: List[Dict]) -> List[Dict]:
    tokens = {
        "no puedo", "no tengo", "no cuento", "no me alcanza",
        "no voy a poder", "no podria", "no podría", "no acepto",
        "muy alto", "mucho monto", "no estoy en capacidad",
        "ahorita no", "ahora no", "no puedo ahora", "no cuento con",
        "no tengo el monto", "llamar mas tarde", "llamar más tarde",
        "no uso whatsapp", "no tengo whatsapp",
        "estoy pagando", "problemas", "enfermedad", "operar",
        "me pagan", "cosecha", "otros bancos", "otro banco",
    }
    return buscar_segmentos_por_tokens_v3(segmentos, "CLIENTE", tokens)


def buscar_segmentos_dificultad_cliente_v3(segmentos: List[Dict]) -> List[Dict]:
    tokens = {
        "problemas", "no puedo", "no me encuentro", "no tengo", "no cuento",
        "estoy pagando", "enfermedad", "operar", "agricultura", "cosecha",
        "trabajo", "debo", "debiendo", "otros bancos", "otro banco",
        "familia", "esposo", "esposa", "perdida", "pérdida",
    }
    return buscar_segmentos_por_tokens_v3(segmentos, "CLIENTE", tokens)


def buscar_segmentos_respuesta_gestion_agente_v3(segmentos: List[Dict]) -> List[Dict]:
    tokens = {
        "puede", "puedes", "podria", "podría", "abonar", "cancelar",
        "pagar", "pago", "monto", "cuanto", "cuánto", "fecha",
        "acuerdo", "compromiso", "opcion", "opción", "alternativa",
        "solucion", "solución", "recaudar", "programar", "voucher",
    }
    return buscar_segmentos_por_tokens_v3(segmentos, "AGENTE", tokens)


def buscar_segmentos_diagnostico_agente_v3(segmentos: List[Dict]) -> List[Dict]:
    tokens = {
        "por que", "por qué", "motivo", "causa", "que paso", "qué pasó",
        "cuanto", "cuánto", "ha podido recaudar", "puede pagar",
        "capacidad", "fecha", "cuando", "cuándo", "ingreso",
        "que es lo que", "qué es lo que", "situacion", "situación",
    }
    return buscar_segmentos_por_tokens_v3(segmentos, "AGENTE", tokens)


def buscar_segmentos_sondeo_causa_agente_v3(segmentos: List[Dict]) -> List[Dict]:
    tokens = {
        "por que", "por qué", "motivo", "causa", "que paso", "qué pasó",
        "que ocurrio", "qué ocurrió", "a que se debe", "a qué se debe",
        "desde cuando", "desde cuándo", "que sucedio", "qué sucedió",
    }
    return buscar_segmentos_por_tokens_v3(segmentos, "AGENTE", tokens)


def buscar_segmentos_causa_cliente_v3(segmentos: List[Dict]) -> List[Dict]:
    tokens = {
        "debido", "desde que", "me quede", "me quedé",
        "perdi", "perdí", "desemple", "enfermedad", "operar", "cosecha",
        "problema", "otros bancos", "otro banco", "familia", "trabajo",
    }
    return buscar_segmentos_por_tokens_v3(segmentos, "CLIENTE", tokens)


def buscar_segmentos_capacidad_cliente_v3(segmentos: List[Dict]) -> List[Dict]:
    tokens = {
        "puedo", "podria", "podría", "voy a", "tengo", "no tengo",
        "no puedo", "no cuento", "he podido", "recaudar", "juntar",
        "dinero", "monto", "soles", "fecha", "semana", "mañana", "manana",
    }
    return buscar_segmentos_por_tokens_v3(segmentos, "CLIENTE", tokens)


def buscar_segmentos_personalizacion_v3(segmentos: List[Dict]) -> List[Dict]:
    encontrados = []
    for segmento in segmentos[:15]:
        if normalizar_hablante_v2(segmento.get("hablante") or segmento.get("rol")) != "AGENTE":
            continue
        texto_original = str(segmento.get("texto") or segmento.get("texto_original") or "").strip()
        texto = limpiar_key_texto(texto_original)
        if any(token in texto for token in {"senora", "senor", "señora", "señor", "don ", "dona ", "doña "}):
            encontrados.append(segmento)
            continue
        # Nombre propio probable: palabra capitalizada que no sea inicio genérico.
        palabras = re.findall(r"\b[A-ZÁÉÍÓÚÑ][a-záéíóúñ]{2,}\b", texto_original)
        palabras_genericas = {"Buenos", "Buenas", "Hola", "Mibanco", "Banco"}
        if any(palabra not in palabras_genericas for palabra in palabras):
            encontrados.append(segmento)
    return encontrados


def buscar_segmentos_consulta_cliente_v3(segmentos: List[Dict]) -> List[Dict]:
    tokens = {
        "cuanto", "cuánto", "como", "cómo", "cuando", "cuándo",
        "donde", "dónde", "que", "qué", "por que", "por qué",
        "consulta", "me puede explicar", "no entiendo", "cual", "cuál",
    }
    encontrados = []
    for segmento in segmentos:
        if normalizar_hablante_v2(segmento.get("hablante") or segmento.get("rol")) != "CLIENTE":
            continue
        texto_original = str(segmento.get("texto") or segmento.get("texto_original") or "")
        texto = limpiar_key_texto(texto_original)
        if "?" in texto_original or any(token and token in texto for token in {limpiar_key_texto(item) for item in tokens}):
            encontrados.append(segmento)
    return encontrados


def buscar_segmentos_compromiso_pago_v3(segmentos: List[Dict]) -> List[Dict]:
    tokens = {
        "voy a pagar", "voy a cancelar", "puedo pagar", "podria pagar",
        "podría pagar", "me comprometo", "para el", "mañana", "manana",
        "el miercoles", "el miércoles", "pago", "abono", "voucher",
    }
    cliente = buscar_segmentos_por_tokens_v3(segmentos, "CLIENTE", tokens)
    agente = buscar_segmentos_por_tokens_v3(segmentos, "AGENTE", {"programar", "compromiso", "queda", "entonces", "confirmamos", "monto", "fecha", "pago"})
    return cliente or agente


def buscar_segmentos_compromiso_confirmado_mibanco_v3(segmentos: List[Dict]) -> List[Dict]:
    """Detecta aceptación del cliente, no una propuesta aislada del agente."""
    ordenados = sorted(
        [item for item in segmentos if isinstance(item, dict)],
        key=lambda item: int(item.get("segmento_id") or 0),
    )
    aceptaciones_breves = {"si", "sí", "correcto", "de acuerdo", "conforme", "esta bien", "está bien"}
    compromisos = {
        "me comprometo", "voy a pagar", "voy a cancelar", "voy a abonar",
        "lo pago", "lo cancelo", "lo abono", "si voy a pagar", "sí voy a pagar",
    }
    condiciones_pago = {
        "pago", "abono", "cancelar", "monto", "soles", "cuota", "fecha",
        "hoy", "manana", "mañana", "lunes", "martes", "miercoles", "miércoles",
        "jueves", "viernes", "sabado", "sábado", "domingo", "voucher",
    }
    encontrados = []
    for indice, segmento in enumerate(ordenados):
        if normalizar_hablante_v2(segmento.get("hablante") or segmento.get("rol")) != "CLIENTE":
            continue
        texto_original = str(segmento.get("texto") or segmento.get("texto_original") or "")
        texto = limpiar_key_texto(texto_original)
        if any(token in texto for token in compromisos) and _compromiso_cliente_especifico_v3(texto_original):
            encontrados.append(segmento)
            continue
        if texto in {limpiar_key_texto(item) for item in aceptaciones_breves}:
            previos_agente = ordenados[max(0, indice - 3):indice]
            if any(
                normalizar_hablante_v2(previo.get("hablante") or previo.get("rol")) == "AGENTE"
                and _propuesta_pago_completa_v3(previo, condiciones_pago)
                for previo in previos_agente
            ):
                encontrados.append(segmento)
    return encontrados


def _propuesta_pago_completa_v3(segmento: Dict, condiciones_pago: set[str]) -> bool:
    texto_original = str(segmento.get("texto") or segmento.get("texto_original") or "")
    texto = limpiar_key_texto(texto_original)
    acciones_pago = {"pago", "abono", "cancelar", "monto", "soles", "cuota", "voucher"}
    tiene_accion = any(token in texto for token in acciones_pago)
    tiene_monto = bool(re.search(r"\b\d{2,6}(?:[.,]\d{1,2})?\b", texto_original))
    tiene_fecha = any(token in texto for token in {
        "hoy", "manana", "mañana", "lunes", "martes", "miercoles", "miércoles",
        "jueves", "viernes", "sabado", "sábado", "domingo", "fecha",
    })
    return tiene_accion and tiene_monto and tiene_fecha


def _compromiso_cliente_especifico_v3(texto_original: str) -> bool:
    texto = limpiar_key_texto(texto_original)
    tiene_monto = bool(re.search(r"\b\d{2,6}(?:[.,]\d{1,2})?\b", texto_original))
    tiene_fecha = any(token in texto for token in {
        "hoy", "manana", "mañana", "lunes", "martes", "miercoles", "miércoles",
        "jueves", "viernes", "sabado", "sábado", "domingo", "fecha",
    })
    return tiene_monto or tiene_fecha


def buscar_segmentos_siguiente_accion_confirmada_mibanco_v3(segmentos: List[Dict]) -> List[Dict]:
    """Reconoce un agendamiento confirmado; no lo confunde con una promesa de pago."""
    ordenados = sorted(
        [item for item in segmentos if isinstance(item, dict)],
        key=lambda item: int(item.get("segmento_id") or 0),
    )
    aceptaciones = {"si", "sí", "correcto", "de acuerdo", "conforme", "esta bien", "está bien"}
    acciones = {"llamo", "llamar", "devolver la llamada", "me comunico", "comunicar", "contacto", "agendar", "agendamos"}
    referencias_tiempo = {"hoy", "manana", "mañana", "tarde", "fecha", "hora"}
    for indice, segmento in enumerate(ordenados):
        if normalizar_hablante_v2(segmento.get("hablante") or segmento.get("rol")) != "AGENTE":
            continue
        texto_original = str(segmento.get("texto") or segmento.get("texto_original") or "")
        texto = limpiar_key_texto(texto_original)
        tiene_accion = any(limpiar_key_texto(token) in texto for token in acciones)
        tiene_tiempo = any(limpiar_key_texto(token) in texto for token in referencias_tiempo) or bool(re.search(r"\b\d{1,2}(?::\d{2})?\b", texto_original))
        if not (tiene_accion and tiene_tiempo):
            continue
        for siguiente in ordenados[indice + 1:indice + 4]:
            if normalizar_hablante_v2(siguiente.get("hablante") or siguiente.get("rol")) != "CLIENTE":
                continue
            respuesta = limpiar_key_texto(siguiente.get("texto") or siguiente.get("texto_original") or "")
            if respuesta in {limpiar_key_texto(item) for item in aceptaciones}:
                return [segmento, siguiente]
    return []


def buscar_segmentos_validacion_acuerdo_agente_v3(segmentos: List[Dict]) -> List[Dict]:
    encontrados = []
    for segmento in segmentos:
        if normalizar_hablante_v2(segmento.get("hablante") or segmento.get("rol")) != "AGENTE":
            continue
        texto = limpiar_key_texto(segmento.get("texto") or segmento.get("texto_original") or "")
        tiene_monto = bool(re.search(r"\b\d{2,6}\b", texto)) or any(token in texto for token in {"soles", "monto", "cuota"})
        tiene_fecha = any(token in texto for token in {"hoy", "manana", "mañana", "lunes", "martes", "miercoles", "miércoles", "jueves", "viernes", "sabado", "sábado", "domingo", "fecha"})
        tiene_medio = any(token in texto for token in {"voucher", "agente", "banco", "canal", "ventanilla", "transferencia", "aplicativo"})
        if tiene_monto and tiene_fecha and tiene_medio:
            encontrados.append(segmento)
    return encontrados


def buscar_segmentos_riesgo_intimidacion_v3(segmentos: List[Dict]) -> List[Dict]:
    tokens = {
        "embargo", "demanda", "denuncia", "judicial", "legal",
        "coactivo", "coactiva", "amenaza", "central de riesgo",
        "lo van a reportar", "se va a perjudicar", "otra instancia",
    }
    return buscar_segmentos_por_tokens_v3(segmentos, "AGENTE", tokens)


def buscar_respuesta_posterior_v3(segmentos: List[Dict], referencia: Dict, rol: str, tokens: set[str], ventana: int = 5) -> List[Dict]:
    ref_id = int(referencia.get("segmento_id") or 0)
    encontrados = []
    tokens_norm = {limpiar_key_texto(token) for token in tokens}
    for segmento in segmentos:
        sid = int(segmento.get("segmento_id") or 0)
        if sid <= ref_id or sid > ref_id + ventana:
            continue
        if normalizar_hablante_v2(segmento.get("hablante") or segmento.get("rol")) != normalizar_hablante_v2(rol):
            continue
        texto = limpiar_key_texto(segmento.get("texto") or segmento.get("texto_original") or "")
        if not tokens_norm or any(token and token in texto for token in tokens_norm):
            encontrados.append(segmento)
    return encontrados


def buscar_respuesta_previa_v3(segmentos: List[Dict], referencia: Dict, rol: str, tokens: set[str], ventana: int = 3) -> List[Dict]:
    ref_id = int(referencia.get("segmento_id") or 0)
    encontrados = []
    tokens_norm = {limpiar_key_texto(token) for token in tokens}
    for segmento in segmentos:
        sid = int(segmento.get("segmento_id") or 0)
        if sid >= ref_id or sid < ref_id - ventana:
            continue
        if normalizar_hablante_v2(segmento.get("hablante") or segmento.get("rol")) != normalizar_hablante_v2(rol):
            continue
        texto = limpiar_key_texto(segmento.get("texto") or segmento.get("texto_original") or "")
        if any(token and token in texto for token in tokens_norm):
            encontrados.append(segmento)
    return encontrados


def detectar_espera_relevante_v3(segmentos: List[Dict]) -> Optional[Dict]:
    ordenados = sorted(
        [item for item in segmentos if isinstance(item, dict)],
        key=lambda item: (item.get("inicio_segundos") is None, item.get("inicio_segundos") or 0, item.get("segmento_id") or 0),
    )
    previo = None
    for segmento in ordenados:
        inicio = segmento.get("inicio_segundos")
        if previo is not None and inicio is not None:
            fin_previo = previo.get("fin_segundos")
            if fin_previo is not None and float(inicio) - float(fin_previo) >= 20:
                return segmento
        previo = segmento
    return None


def buscar_segmentos_identificacion_asesor_entidad_v3(segmentos: List[Dict]) -> List[Dict]:
    encontrados = []
    for segmento in segmentos[:12]:
        if normalizar_hablante_v2(segmento.get("hablante") or segmento.get("rol")) != "AGENTE":
            continue
        texto = limpiar_key_texto(segmento.get("texto") or segmento.get("texto_original") or "")
        tiene_asesor = any(token in texto for token in {"habla", "le habla", "me llamo", "mi nombre", "soy", "te saluda", "le saluda"})
        tiene_entidad = any(token in texto for token in {"mibanco", "mi banco", "banco", "cuenta", "credito", "crédito"})
        if tiene_asesor and tiene_entidad:
            encontrados.append(segmento)
    if encontrados:
        return encontrados
    asesor = buscar_segmentos_por_tokens_v3(segmentos[:12], "AGENTE", {"habla", "le habla", "mi nombre", "soy", "te saluda", "le saluda"})
    entidad = buscar_segmentos_por_tokens_v3(segmentos[:12], "AGENTE", {"mibanco", "mi banco", "banco"})
    return (asesor[:1] + entidad[:1]) if asesor and entidad else []


def contiene_indicio_tercero_v3(texto_cliente: str) -> bool:
    tokens = {
        "no soy", "soy su", "es mi", "no se encuentra", "no esta",
        "no está", "llame luego", "es mi esposo", "es mi esposa",
        "es mi hijo", "es mi hija", "es mi hermano", "es mi hermana",
    }
    texto = limpiar_key_texto(texto_cliente)
    return any(limpiar_key_texto(token) in texto for token in tokens)


def buscar_segmentos_tercero_confirmado_mibanco_v3(segmentos: List[Dict]) -> List[Dict]:
    """Solo confirma tercero con expresiones explícitas; no infiere por silencio o duda."""
    tokens = {
        "no soy", "se equivoco de numero", "se equivocó de número", "no la conozco",
        "no lo conozco", "soy su esposo", "soy su esposa", "soy su hijo", "soy su hija",
        "soy su hermano", "soy su hermana", "no vive aqui", "no vive aquí",
    }
    return buscar_segmentos_por_tokens_v3(segmentos, "CLIENTE", tokens)


def buscar_segmentos_corte_abrupto_mibanco_v3(segmentos: List[Dict]) -> List[Dict]:
    """Reconoce cortes explícitos al final de la secuencia; evita inferirlos por falta de evidencia."""
    ordenados = sorted(
        [item for item in segmentos if isinstance(item, dict)],
        key=lambda item: int(item.get("segmento_id") or 0),
    )
    if not ordenados:
        return []
    finales = ordenados[-3:]
    tokens = {"voy a colgar", "voy a cortar", "cuelgo", "corto la llamada", "se corto", "se cortó"}
    encontrados = []
    for segmento in finales:
        texto = limpiar_key_texto(segmento.get("texto") or segmento.get("texto_original") or "")
        if any(limpiar_key_texto(token) in texto for token in tokens):
            encontrados.append(segmento)
    return encontrados


def buscar_segmentos_por_tokens_v3(segmentos: List[Dict], rol: str, tokens: set[str]) -> List[Dict]:
    encontrados = []
    rol_objetivo = normalizar_hablante_v2(rol)
    tokens_norm = {limpiar_key_texto(token) for token in tokens}
    for segmento in segmentos:
        if normalizar_hablante_v2(segmento.get("hablante") or segmento.get("rol")) != rol_objetivo:
            continue
        texto = limpiar_key_texto(segmento.get("texto") or segmento.get("texto_original") or "")
        if any(token and token in texto for token in tokens_norm):
            encontrados.append(segmento)
    return encontrados


def detectar_titularidad_contextual_v3(segmentos: List[Dict]) -> List[Dict]:
    respuestas_validas = {"si", "sí", "digame", "dígame", "que digame", "qué dígame", "soy yo", "ella habla", "el habla"}
    for idx, segmento in enumerate(segmentos[:12]):
        if normalizar_hablante_v2(segmento.get("hablante") or segmento.get("rol")) != "AGENTE":
            continue
        texto = limpiar_key_texto(segmento.get("texto") or segmento.get("texto_original") or "")
        if not texto:
            continue
        pregunta_titular = (
            texto.endswith("por favor")
            or "me podria comunicar" in texto
            or "me podría comunicar" in texto
            or "con la senora" in texto
            or "con la señora" in texto
            or "con el senor" in texto
            or "con el señor" in texto
        )
        if not pregunta_titular:
            continue
        for siguiente in segmentos[idx + 1:idx + 4]:
            if normalizar_hablante_v2(siguiente.get("hablante") or siguiente.get("rol")) != "CLIENTE":
                continue
            respuesta = limpiar_key_texto(siguiente.get("texto") or siguiente.get("texto_original") or "")
            respuestas_norm = {limpiar_key_texto(item) for item in respuestas_validas}
            palabras = set(respuesta.split())
            if respuesta in respuestas_norm or "digame" in respuesta or "si" in palabras:
                return [segmento, siguiente]
    return []


def aplicar_resultado_guardado_v3(
    criterio: Optional[Dict],
    estado: str,
    segmentos: List[Dict],
    hallazgo: str,
    recomendacion: str,
) -> None:
    if not isinstance(criterio, dict):
        return
    peso = float(criterio.get("peso") or 0)
    criterio["estado"] = estado
    criterio["puntaje_obtenido"] = puntaje_pipeline_v3(None, estado, peso)
    criterio["resultado"] = resultado_legacy_desde_estado_v2(estado)
    criterio["calificacion"] = criterio["resultado"]
    criterio["nota"] = criterio["puntaje_obtenido"]
    criterio["nota_ia"] = criterio["puntaje_obtenido"]
    criterio["nota_final"] = criterio["puntaje_obtenido"]
    criterio["segmentos_evidencia"] = [
        int(item.get("segmento_id"))
        for item in segmentos
        if item.get("segmento_id") is not None
    ]
    criterio["evidencia_textual"] = [
        str(item.get("texto") or item.get("texto_original") or "").strip()
        for item in segmentos
        if str(item.get("texto") or item.get("texto_original") or "").strip()
    ]
    criterio["tipo_evidencia"] = "DIRECTA" if criterio["segmentos_evidencia"] else "CONTEXTUAL"
    criterio["hallazgo"] = hallazgo
    criterio["conducta_observada"] = hallazgo
    criterio["recomendacion_entrenable"] = recomendacion
    if estado == "CUMPLE":
        criterio["impacto_negocio"] = ""
        criterio["impacto_cliente"] = ""


def score_desde_criterios_pipeline_v3(criterios: List[Dict]) -> Dict:
    bruto = 0.0
    peso_aplicable = 0.0
    peso_total = 0.0
    peso_no_aplica = 0.0
    peso_no_evaluable = 0.0
    for item in criterios:
        peso_item = float(item.get("peso") or 0)
        estado = str(item.get("estado") or "")
        peso_total += peso_item
        if estado == "NO_APLICA":
            peso_no_aplica += peso_item
            continue
        if estado == "NO_EVALUABLE":
            peso_no_evaluable += peso_item
            continue
        bruto += float(item.get("puntaje_obtenido") or 0)
        peso_aplicable += peso_item
    score = round((bruto / peso_aplicable) * 100, 2) if peso_aplicable else 0.0
    return {
        "score_bruto": round(bruto, 2),
        "peso_total": round(peso_total, 2),
        "peso_aplicable": round(peso_aplicable, 2),
        "peso_no_aplica": round(peso_no_aplica, 2),
        "peso_no_evaluable": round(peso_no_evaluable, 2),
        "score_tecnico": score,
    }


def metadatos_pauta_pipeline_v3(pauta: Optional[List[Dict]]) -> Dict:
    if not pauta:
        return {"nombre": "COPC_SGC", "version": "2.0", "pesos": None, "snapshot": None}
    bloques: Dict[str, float] = {}
    for criterio in pauta:
        bloque = str(criterio.get("bloque") or criterio.get("subcategoria") or "Sin bloque")
        if str(criterio.get("tipo_criterio") or "PUNTUABLE").upper() != "PUNTUABLE":
            bloques.setdefault(bloque, 0.0)
            continue
        bloques[bloque] = round(bloques.get(bloque, 0.0) + float(criterio.get("peso") or 0), 2)
    primero = pauta[0] if pauta else {}
    nombre = str(primero.get("pauta_nombre") or "MIBANCO").strip()
    version = primero.get("pauta_version") or "1.0"
    snapshot = [{
        "codigo_criterio": item.get("codigo_criterio") or item.get("codigo"),
        "bloque": item.get("bloque"),
        "nombre": item.get("nombre"),
        "peso": item.get("peso"),
        "tipo_criterio": item.get("tipo_criterio") or "PUNTUABLE",
        "criticidad": item.get("criticidad"),
        "fuente_evidencia": item.get("fuente_evidencia"),
    } for item in pauta]
    return {
        "nombre": nombre,
        "version": version,
        "pesos": {**bloques, "TOTAL": round(sum(bloques.values()), 2)},
        "snapshot": snapshot,
    }


def construir_respuesta_pipeline_v3(
    *,
    segmentos: List[Dict],
    hechos: Dict,
    criterios: List[Dict],
    auditoria: Dict,
    feedback: Dict,
    score_antes: Dict,
    score_despues: Dict,
    criterios_corregidos: List[str],
    cartera: Optional[str] = None,
    pauta: Optional[List[Dict]] = None,
) -> Dict:
    dimensiones = []
    criterios_por_codigo = {
        str(item.get("codigo") or item.get("codigo_criterio") or "").strip(): item
        for item in criterios
        if isinstance(item, dict) and str(item.get("codigo") or item.get("codigo_criterio") or "").strip()
    }
    if pauta:
        bloques = list(dict.fromkeys(str(item.get("bloque") or item.get("subcategoria") or "") for item in pauta))
        for segmento in bloques:
            codigos_segmento = [
                codigo_criterio_pauta(item)
                for item in pauta
                if str(item.get("bloque") or item.get("subcategoria") or "") == segmento
            ]
            criterios_segmento = [
                criterio_pipeline_a_v2(criterios_por_codigo[codigo])
                for codigo in codigos_segmento
                if codigo in criterios_por_codigo
            ]
            peso = sum(float(item.get("puntaje_maximo") or 0) for item in criterios_segmento)
            nota = sum(float(item.get("puntaje_obtenido") or 0) for item in criterios_segmento)
            dimensiones.append({"codigo": segmento, "nombre": nombre_bloque_mibanco(segmento), "puntaje_maximo": peso, "puntaje_obtenido": round(nota, 2), "criterios": criterios_segmento})
    else:
        for segmento in dict.fromkeys(seg for seg, _, _ in COPC_ITEMS_CANONICOS):
            codigos_segmento = [
                codigo_item_canonico(nombre)
                for segmento_canon, nombre, _peso in COPC_ITEMS_CANONICOS
                if segmento_canon == segmento
            ]
            criterios_segmento = [
                criterio_pipeline_a_v2(criterios_por_codigo[codigo])
                for codigo in codigos_segmento
                if codigo in criterios_por_codigo
            ]
            peso = sum(float(item.get("puntaje_maximo") or 0) for item in criterios_segmento)
            nota = sum(float(item.get("puntaje_obtenido") or 0) for item in criterios_segmento)
            dimensiones.append({"codigo": segmento, "nombre": segmento, "puntaje_maximo": peso, "puntaje_obtenido": round(nota, 2), "criterios": criterios_segmento})
    resumen = feedback.get("resumen_ejecutivo") if isinstance(feedback.get("resumen_ejecutivo"), dict) else {}
    gestion = feedback.get("resultado_gestion") if isinstance(feedback.get("resultado_gestion"), dict) else {}
    coaching = feedback.get("coaching") if isinstance(feedback.get("coaching"), dict) else {}
    requiere_revision = any(item.get("estado") == "REQUIERE_REVISION" for item in criterios)
    codigos_revision = [item.get("codigo") for item in criterios if item.get("estado") == "REQUIERE_REVISION"]
    if len(codigos_revision) >= max(8, int(len(criterios) * 0.5)):
        motivos_revision = ["Revisión humana requerida por cobertura o confianza insuficiente del análisis."]
    else:
        motivos_revision = codigos_revision
    score = score_despues.get("score_tecnico", 0)
    cobertura = hechos.get("cobertura") if isinstance(hechos.get("cobertura"), dict) else {}
    metricas_roles = metricas_cobertura_roles_v3(segmentos)
    calidad_transcripcion = evaluar_calidad_transcripcion_v3(segmentos)
    if metricas_roles.get("requiere_revision_humana") and "Cobertura de roles menor al 70%." not in motivos_revision:
        motivos_revision = [*motivos_revision, "Cobertura de roles menor al 70%."]
    if calidad_transcripcion.get("requiere_revision_humana"):
        for motivo in calidad_transcripcion.get("motivos_criticos") or []:
            if motivo not in motivos_revision:
                motivos_revision.append(motivo)
    requiere_revision = bool(
        requiere_revision
        or metricas_roles.get("requiere_revision_humana")
        or calidad_transcripcion.get("requiere_revision_humana")
    )
    hallazgos_estimados = sum(
        1
        for item in criterios
        if item.get("estado") not in {"CUMPLE", "NO_APLICA", "NO_EVALUABLE", "REQUIERE_REVISION"}
    )
    metadatos_pauta = metadatos_pauta_pipeline_v3(pauta)
    descalificacion = detectar_descalificacion_mibanco_v3(criterios, segmentos) if pauta else {"descalificada": False}
    if descalificacion.get("requiere_revision"):
        requiere_revision = True
        motivos_revision = [*motivos_revision, descalificacion.get("motivo") or "Posible falta descalificante requiere revisión humana."]
    return {
        "version_evaluacion": f"{metadatos_pauta['nombre']}_{metadatos_pauta['version']}" if pauta else "2.0",
        "motor_evaluacion": "PIPELINE_MULTIPASO_V3",
        "pauta": metadatos_pauta["nombre"],
        "pauta_version": metadatos_pauta["version"],
        "pauta_pesos": metadatos_pauta["pesos"],
        "pauta_snapshot": metadatos_pauta["snapshot"],
        "resultado_evaluacion": {
            "score_tecnico": score,
            "score_maximo": 100,
            "nota_minima_aprobatoria": 85,
            "estado_tecnico": "DESCALIFICADO" if descalificacion.get("descalificada") else ("APROBADA" if score >= 85 else "NO_APROBADA"),
            "estado_calidad": "PENDIENTE_REVISION" if requiere_revision else ("APROBADA" if score >= 85 else "NO_APROBADA"),
            "descalificada": bool(descalificacion.get("descalificada")),
            "motivo_descalificacion": descalificacion.get("motivo"),
            "evidencia_descalificacion": descalificacion.get("evidencia"),
            "confianza_global": confianza_global_segmentos_v2(segmentos),
            "evaluacion_provisional": requiere_revision,
            "requiere_revision_humana": requiere_revision,
            "motivos_revision": motivos_revision,
            "metricas_roles": metricas_roles,
            "calidad_transcripcion": calidad_transcripcion,
        },
        "resultado_gestion": gestion,
        "calidad_transcripcion": calidad_transcripcion,
        "tipificaciones_sugeridas": feedback.get("tipificaciones_sugeridas") if isinstance(feedback.get("tipificaciones_sugeridas"), list) else [],
        "resumen_ejecutivo": resumen,
        "interlocutores": {
            "confianza_global": confianza_global_segmentos_v2(segmentos),
            "metodo": "DIARIZACION_ORIGINAL" if any(item.get("speaker_original") for item in segmentos) else "PIPELINE_SECUENCIAL",
            "speakers": {
                str(item.get("speaker_original")): item.get("hablante")
                for item in segmentos
                if item.get("speaker_original") and item.get("hablante")
            },
            "integridad": validar_integridad_diarizacion(segmentos, len(segmentos)) if any(item.get("speaker_original") for item in segmentos) else {},
            "metricas_roles": metricas_roles,
            "segmentos": segmentos,
        },
        "dimensiones": dimensiones,
        "errores_criticos": [],
        "hallazgos_no_criticos": [],
        "frases_detectadas": {"adecuadas": [], "mejorables": [], "riesgo": []},
        "coaching": coaching,
        "hechos_llamada": hechos,
        "auditoria_consistencia": auditoria,
        "log_calidad_motor": {
            "cantidad_segmentos_entrada": len(segmentos),
            "cantidad_segmentos_analizados": len(segmentos),
            "hechos_encontrados": sum(len(v) for v in hechos.get("hechos", {}).values() if isinstance(v, list)),
            "criterios_evaluados": len(criterios),
            "cantidad_hallazgos_estimados": hallazgos_estimados,
            "cobertura_roles": metricas_roles,
            "calidad_transcripcion": calidad_transcripcion,
            "inconsistencias_encontradas": len(auditoria.get("inconsistencias", [])),
            "criterios_corregidos": criterios_corregidos,
            "score_antes_auditoria": score_antes,
            "score_despues_auditoria": score_despues,
            "cartera": cartera,
            "pauta": metadatos_pauta["nombre"],
            "pauta_version": metadatos_pauta["version"],
        },
        "validaciones": {
            "suma_dimensiones_correcta": True,
            "score_dentro_de_rango": 0 <= score <= 100,
            "cobertura_completa": cobertura.get("cantidad_segmentos_considerados") == len(segmentos),
            "observaciones": [],
        },
    }


def criterio_pipeline_a_v2(item: Dict) -> Dict:
    codigo = str(item.get("codigo") or "")
    catalogo_sgc = obtener_catalogo_sgc(codigo) or catalogo_sgc_desde_pauta(item)
    grupo_sgc = catalogo_sgc.get("grupo_error_sgc") or SGC_GRUPO_NO_CRITICO
    factor_sgc = catalogo_sgc.get("factor_sgc") or item.get("nombre") or "Criterio tecnico"
    evidencia_textual = item.get("evidencia_textual") if isinstance(item.get("evidencia_textual"), list) else []
    evidencias = []
    for segmento_id, texto in zip(item.get("segmentos_evidencia") or [], evidencia_textual):
        evidencias.append({
            "segmento_id": segmento_id,
            "texto": texto,
            "tipo": item.get("tipo_evidencia") or "DIRECTA",
        })
    return {
        "codigo": codigo,
        "codigo_criterio": codigo,
        "nombre": item.get("nombre") or "",
        "puntaje_maximo": item.get("peso") or 0,
        "puntaje_obtenido": item.get("puntaje_obtenido") or 0,
        "estado": item.get("estado") or "REQUIERE_REVISION",
        "conducta_esperada": "",
        "evidencias": evidencias,
        "evidencia_textual": evidencia_textual,
        "segmentos_evidencia": item.get("segmentos_evidencia") or [],
        "segmentos_contexto": item.get("segmentos_contexto") or [],
        "tipo_evidencia": item.get("tipo_evidencia") or "DIRECTA",
        "hallazgo": item.get("hallazgo") or item.get("conducta_observada") or "",
        "impacto": combinar_textos_v2(item.get("impacto_negocio"), item.get("impacto_cliente"), separador=" | "),
        "recomendacion": item.get("recomendacion_entrenable") or "",
        "gravedad": "",
        "puede_descalificar": bool(item.get("puede_descalificar") or catalogo_sgc.get("puede_descalificar")),
        "confianza": item.get("confianza") or "",
        "requiere_revision": item.get("estado") == "REQUIERE_REVISION",
        "motivo_no_evaluable": item.get("hallazgo") if item.get("estado") in {"NO_EVALUABLE", "REQUIERE_REVISION"} else "",
        "bloque": item.get("bloque"),
        "categoria": item.get("categoria"),
        "subcategoria": item.get("subcategoria"),
        "detalle": item.get("detalle"),
        "regla_evaluacion": item.get("regla_evaluacion"),
        "criticidad": item.get("criticidad"),
        "fuente_evidencia": item.get("fuente_evidencia") or catalogo_sgc.get("fuente_evidencia"),
        "regla_aplicabilidad": item.get("regla_aplicabilidad"),
        "requiere_evidencia": bool(item.get("requiere_evidencia")),
        "tipo_criterio": item.get("tipo_criterio") or "PUNTUABLE",
        "bloque_anulado": bool(item.get("bloque_anulado")),
        "motivo_bloque_anulado": item.get("motivo_bloque_anulado") or "",
        "posible_descalificacion": bool(item.get("posible_descalificacion")),
        "justificacion_descalificacion": item.get("justificacion_descalificacion"),
        "factor": factor_sgc,
        "grupo_sgc": grupo_sgc,
        "grupo_error_sgc": grupo_sgc,
        "grupo_sgc_codigo": catalogo_sgc.get("grupo_sgc_codigo"),
        "factor_sgc": factor_sgc,
        "severidad_base": catalogo_sgc.get("severidad_base"),
        "calificacion": resultado_legacy_desde_estado_v2(item.get("estado")),
        "conducta_observada": item.get("conducta_observada") or "",
        "lectura_ia": item.get("hallazgo") or "",
        "impacto_negocio": item.get("impacto_negocio") or "",
        "impacto_cliente": item.get("impacto_cliente") or "",
        "recomendacion_entrenable": item.get("recomendacion_entrenable") or "",
        "frase_sugerida": item.get("frase_sugerida") or "",
        "fortaleza_relacionada": item.get("fortaleza_relacionada"),
    }


def nombre_bloque_mibanco(bloque: str) -> str:
    nombres = {
        "PENC": "PENC - Error no crítico",
        "PECUF": "PECUF - Error crítico usuario final",
        "PECN": "PECN - Error crítico negocio",
        "PECC": "PECC - Error crítico cumplimiento",
    }
    return nombres.get(str(bloque or ""), str(bloque or "Mibanco"))


def detectar_descalificacion_mibanco_v3(criterios: List[Dict], segmentos: List[Dict]) -> Dict:
    segmentos_por_id = {int(item.get("segmento_id") or 0): item for item in segmentos if item.get("segmento_id") is not None}
    for criterio in criterios:
        if not criterio.get("puede_descalificar"):
            continue
        if not criterio.get("posible_descalificacion"):
            continue
        ids = criterio.get("segmentos_evidencia") or criterio.get("segmentos_contexto") or []
        if not ids:
            return {
                "descalificada": False,
                "requiere_revision": True,
                "motivo": f"Posible falta descalificante sin segmento verificable en {criterio.get('codigo_criterio')}.",
            }
        evidencias = [segmentos_por_id.get(int(segmento_id)) for segmento_id in ids if int(segmento_id) in segmentos_por_id]
        roles = {normalizar_hablante_v2((item or {}).get("hablante") or (item or {}).get("rol")) for item in evidencias}
        confianzas = {normalizar_confianza((item or {}).get("confianza")) for item in evidencias}
        if "AGENTE" not in roles or "NO_DETERMINADO" in roles or "BAJA" in confianzas:
            return {
                "descalificada": False,
                "requiere_revision": True,
                "motivo": f"Posible falta descalificante con interlocutor o confianza insuficiente en {criterio.get('codigo_criterio')}.",
                "evidencia": " | ".join(str((item or {}).get("texto") or (item or {}).get("texto_original") or "").strip() for item in evidencias if item),
            }
        if criterio.get("estado") == "NO_CUMPLE":
            return {
                "descalificada": True,
                "requiere_revision": False,
                "motivo": criterio.get("justificacion_descalificacion") or criterio.get("hallazgo") or f"Falta descalificante en {criterio.get('nombre')}.",
                "criterio": criterio.get("codigo_criterio"),
                "evidencia": " | ".join(str((item or {}).get("texto") or (item or {}).get("texto_original") or "").strip() for item in evidencias if item),
            }
    return {"descalificada": False, "requiere_revision": False}


def cargar_json_analisis(content: str, *, client=None) -> Dict:
    try:
        data = json.loads(content or "{}")
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass

    if client is None:
        raise ValueError("La IA devolvió un JSON inválido y no se pudo reparar.")

    reparacion = client.chat.completions.create(
        model=ANALYSIS_MODEL,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": "Repara el contenido para que sea exclusivamente JSON válido. No agregues datos nuevos.",
            },
            {"role": "user", "content": content or "{}"},
        ],
    )
    reparado = reparacion.choices[0].message.content or "{}"
    data = json.loads(reparado)
    if not isinstance(data, dict):
        raise ValueError("La reparación de JSON no devolvió un objeto válido.")
    return data


def asegurar_respuesta_copc_v2(client, prompt: str, data: Dict) -> Dict:
    if es_copc_v2(data) and respuesta_copc_v2_tiene_criterios(data):
        return data
    response = client.chat.completions.create(
        model=ANALYSIS_MODEL,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": (
                    "La respuesta previa no cumplió el contrato COPC v2. "
                    "Devuelve exclusivamente JSON válido con version_evaluacion '2.0' "
                    "y las 5 dimensiones con los criterios de la matriz COPC v2 definida. "
                    "Incluye interlocutores.segmentos con hablante, texto, timestamp, confianza y fundamento "
                    "cuando la transcripción permita separar turnos de habla. "
                    "No uses el formato antiguo."
                ),
            },
            {"role": "user", "content": prompt},
        ],
    )
    content = response.choices[0].message.content or "{}"
    reparada = cargar_json_analisis(content, client=client)
    if not (es_copc_v2(reparada) and respuesta_copc_v2_tiene_criterios(reparada)):
        if es_copc_v2(reparada):
            return reparada
        if es_copc_v2(data):
            return data
        raise ValueError("La IA no devolvió una evaluación COPC v2 válida con criterios completos.")
    return reparada


def respuesta_copc_v2_tiene_criterios(data: Dict) -> bool:
    dimensiones = data.get("dimensiones")
    if not isinstance(dimensiones, list):
        return False
    total = 0
    for dimension in dimensiones:
        if not isinstance(dimension, dict):
            continue
        items = dimension.get("criterios") or dimension.get("items") or []
        if isinstance(items, list):
            total += len([item for item in items if isinstance(item, dict)])
    return total >= 20


def es_copc_v2(data: Dict) -> bool:
    return str(data.get("version_evaluacion") or "").startswith("2") or isinstance(data.get("resultado_evaluacion"), dict)


def normalizar_analisis_copc_v2(data: Dict, transcripcion: str = "") -> Dict:
    es_pipeline_v3 = (
        str(data.get("motor_evaluacion") or "").upper() == "PIPELINE_MULTIPASO_V3"
        or str(data.get("pauta") or "").upper() == "MIBANCO"
    )
    resultado = data.get("resultado_evaluacion") if isinstance(data.get("resultado_evaluacion"), dict) else {}
    gestion = data.get("resultado_gestion") if isinstance(data.get("resultado_gestion"), dict) else {}
    resumen = data.get("resumen_ejecutivo") if isinstance(data.get("resumen_ejecutivo"), dict) else {}
    coaching = data.get("coaching") if isinstance(data.get("coaching"), dict) else {}
    feedback_supervisor = coaching.get("feedback_supervisor") if isinstance(coaching.get("feedback_supervisor"), dict) else {}
    feedback_asesor = coaching.get("feedback_asesor") if isinstance(coaching.get("feedback_asesor"), dict) else {}
    interlocutores = normalizar_interlocutores_v2(data, transcripcion)
    data["interlocutores"] = interlocutores
    calidad_transcripcion = data.get("calidad_transcripcion") if isinstance(data.get("calidad_transcripcion"), dict) else {}
    if not calidad_transcripcion:
        calidad_transcripcion = resultado.get("calidad_transcripcion") if isinstance(resultado.get("calidad_transcripcion"), dict) else {}
    if not calidad_transcripcion:
        calidad_transcripcion = evaluar_calidad_transcripcion_v3(interlocutores.get("segmentos") or [])

    evaluacion = normalizar_dimensiones_copc_v2(data.get("dimensiones"))
    if not es_pipeline_v3:
        evaluacion = reparar_evaluacion_contextual_v2(evaluacion, data, transcripcion)
    evaluacion = completar_evidencias_desde_segmentos_v3(evaluacion, interlocutores.get("segmentos", []))
    score_bruto, peso_aplicable, score_tecnico = calcular_score_normalizado(evaluacion)
    score_tecnico = round(min(score_tecnico, 100), 2)
    pesos_detalle = calcular_pesos_detalle_evaluacion(evaluacion)

    descalificada_ia = bool(resultado.get("descalificada"))
    descalificada = False
    errores_crudos = None if es_pipeline_v3 else data.get("errores_criticos")
    errores_criticos = normalizar_errores_criticos_v2(errores_crudos, evaluacion)
    if not es_pipeline_v3:
        errores_criticos = reparar_errores_criticos_contextuales_v2(errores_criticos, evaluacion, data, transcripcion)
    frase_anulante = (
        str(resultado.get("evidencia_descalificacion") or resultado.get("motivo_descalificacion") or "No aplica")
        if es_pipeline_v3
        else frase_anulante_contextual_v2(resultado, errores_criticos, transcripcion, descalificada_ia)
    )
    if es_pipeline_v3 and descalificada_ia:
        descalificada = bool(frase_anulante and frase_anulante != "No aplica")
    else:
        descalificada = (descalificada_ia or any(item.get("automatico") for item in errores_criticos)) and cita_anulante_valida_v2(frase_anulante)
    estado_tecnico = "APROBADA" if score_tecnico >= 85 else "NO_APROBADA"
    if any(item.get("requiere_revision") for item in evaluacion):
        estado_tecnico = "PROVISIONAL" if estado_tecnico == "APROBADA" else estado_tecnico

    estado_calidad = str(resultado.get("estado_calidad") or "").strip().upper()
    if estado_calidad not in {"APROBADA", "APROBADA_CON_MEJORAS", "NO_APROBADA", "DESCALIFICADA", "PENDIENTE_REVISION"}:
        if descalificada:
            estado_calidad = "DESCALIFICADA"
        elif resultado.get("requiere_revision_humana") or calidad_transcripcion.get("requiere_revision_humana") or any(item.get("requiere_revision") for item in evaluacion):
            estado_calidad = "PENDIENTE_REVISION"
        elif score_tecnico >= 85:
            estado_calidad = "APROBADA"
        elif score_tecnico >= 70:
            estado_calidad = "APROBADA_CON_MEJORAS"
        else:
            estado_calidad = "NO_APROBADA"

    nivel_riesgo = "ALTO" if estado_calidad in {"DESCALIFICADA", "PENDIENTE_REVISION"} or score_tecnico < 70 else "MEDIO" if score_tecnico < 85 else "BAJO"
    evaluacion = enriquecer_evaluacion_sgc(
        evaluacion,
        score_final=score_tecnico,
        nivel_riesgo=nivel_riesgo,
        falta_anulante=descalificada,
    )
    motivos_revision = resultado.get("motivos_revision") if isinstance(resultado.get("motivos_revision"), list) else []
    motivo_calidad = str(calidad_transcripcion.get("motivo") or "").strip()
    if calidad_transcripcion.get("requiere_revision_humana") and motivo_calidad and motivo_calidad not in motivos_revision:
        motivos_revision = [*motivos_revision, motivo_calidad]
    requiere_revision = bool(
        resultado.get("requiere_revision_humana")
        or calidad_transcripcion.get("requiere_revision_humana")
        or motivos_revision
        or any(item.get("requiere_revision") for item in evaluacion)
    )

    hallazgos_no_criticos_crudos = None if es_pipeline_v3 else data.get("hallazgos_no_criticos")
    puntos_criticos = errores_criticos + normalizar_hallazgos_no_criticos_v2(hallazgos_no_criticos_crudos, evaluacion)
    puntos_criticos = consolidar_puntos_sgc(deduplicar_puntos_criticos(puntos_criticos))
    error_critico = bool(descalificada) or any(
        bool(item.get("error_sgc_confirmado"))
        and str(item.get("grupo_error_sgc") or "") in {
            SGC_GRUPO_NEGOCIO,
            SGC_GRUPO_USUARIO,
            SGC_GRUPO_CUMPLIMIENTO,
        }
        for item in puntos_criticos
    )

    fortalezas = feedback_supervisor.get("fortalezas") if isinstance(feedback_supervisor.get("fortalezas"), list) else []
    if resumen.get("fortaleza_principal"):
        fortalezas = [resumen.get("fortaleza_principal"), *fortalezas]

    tipificaciones = data.get("tipificaciones_sugeridas") if isinstance(data.get("tipificaciones_sugeridas"), list) else []
    alertas = []
    if estado_calidad == "DESCALIFICADA":
        alertas.append(f"Descalificación: {resultado.get('motivo_descalificacion') or 'error crítico automático'}")
    if requiere_revision:
        alertas.append("Requiere revisión humana por criterios no concluyentes o confianza baja.")
    for item in puntos_criticos[:4]:
        if item.get("hallazgo"):
            alertas.append(str(item.get("hallazgo")))

    return {
        "version_evaluacion": data.get("version_evaluacion") or "2.0",
        "pauta": data.get("pauta") or "COPC_SGC",
        "pauta_pesos": data.get("pauta_pesos"),
        "json_copc_v2": data,
        "hechos_llamada": data.get("hechos_llamada") if isinstance(data.get("hechos_llamada"), dict) else {},
        "auditoria_consistencia": data.get("auditoria_consistencia") if isinstance(data.get("auditoria_consistencia"), dict) else {},
        "log_calidad_motor": data.get("log_calidad_motor") if isinstance(data.get("log_calidad_motor"), dict) else {},
        "interlocutores": interlocutores,
        "segmentos_interlocutores": interlocutores.get("segmentos", []),
        "resumen": str(resumen.get("texto") or gestion.get("resumen") or "-"),
        "tipo_contacto": str(gestion.get("tipo_contacto") or "-"),
        "tipo_llamada": str(gestion.get("tipo_cierre") or "Por clasificar"),
        "evaluabilidad": "PARCIALMENTE_EVALUABLE" if requiere_revision else "EVALUABLE",
        "motivo_no_evaluable": "; ".join(str(x) for x in motivos_revision) if motivos_revision else "",
        "objetivo_principal": str(resumen.get("conclusion") or gestion.get("resumen") or "-"),
        "resultado_gestion": str(gestion.get("resultado_principal") or gestion.get("tipo_cierre") or "-"),
        "objecion_principal": str(resumen.get("debilidad_principal") or "-"),
        "score_calidad": score_tecnico,
        "score_final": score_tecnico,
        "score_bruto": score_bruto,
        "peso_total": pesos_detalle["peso_total"],
        "peso_aplicable": peso_aplicable,
        "peso_no_aplica": pesos_detalle["peso_no_aplica"],
        "peso_no_evaluable": pesos_detalle["peso_no_evaluable"],
        "score_normalizado": score_tecnico,
        "estado_calidad": estado_calidad,
        "estado_tecnico": estado_tecnico,
        "nivel_riesgo": nivel_riesgo,
        "error_critico": error_critico,
        "calidad_transcripcion": normalizar_confianza(calidad_transcripcion.get("nivel") or resultado.get("confianza_global")),
        "calidad_transcripcion_detalle": calidad_transcripcion,
        "confianza_evaluacion": normalizar_confianza(calidad_transcripcion.get("confianza") or resultado.get("confianza_global")),
        "requiere_revision_humana": requiere_revision,
        "motivo_revision": "; ".join(str(x) for x in motivos_revision) or (resultado.get("motivo_descalificacion") if requiere_revision else ""),
        "evaluacion_calidad": evaluacion,
        "resumen_sgc": construir_resumen_sgc(
            evaluacion,
            data.get("resumen_sgc") if isinstance(data.get("resumen_sgc"), dict) else {},
            score_final=score_tecnico,
            nivel_riesgo=nivel_riesgo,
            falta_anulante=descalificada,
        ),
        "habilidades_blandas": habilidades_desde_evaluacion(evaluacion),
        "fortalezas_agente": [str(x) for x in fortalezas if x][:4],
        "puntos_criticos": puntos_criticos,
        "evidencias_clave": evidencias_desde_v2(data, puntos_criticos),
        "recomendacion_feedback_supervisor": str(feedback_supervisor.get("resumen_tecnico") or feedback_supervisor.get("accion_entrenable") or "-"),
        "guion_sugerido": str(feedback_asesor.get("ejemplo_mejorado") or feedback_asesor.get("frase_recomendada") or "-"),
        "feedback_asesor": feedback_asesor,
        "tipificaciones_sugeridas": tipificaciones[:2],
        "alertas": deduplicar_textos(alertas)[:4],
        "falta_anulante": descalificada,
        "frase_anulante": frase_anulante if descalificada else "No aplica",
        "momento_falta_anulante": None,
        "nivel_oportunidad_mejora": "ALTA" if nivel_riesgo == "ALTO" else "MEDIA" if nivel_riesgo == "MEDIO" else "BAJA",
    }


def normalizar_interlocutores_v2(data: Dict, transcripcion: str = "") -> Dict:
    interlocutores = data.get("interlocutores") if isinstance(data.get("interlocutores"), dict) else {}
    segmentos_raw = primer_lista_segmentos_v2(data, interlocutores)
    segmentos = []
    for idx, raw in enumerate(segmentos_raw, start=1):
        if not isinstance(raw, dict):
            continue
        texto = str(
            raw.get("texto_limpio")
            or raw.get("texto_original")
            or raw.get("texto")
            or raw.get("text")
            or raw.get("transcripcion")
            or raw.get("frase")
            or raw.get("contenido")
            or ""
        ).strip()
        if not texto:
            continue
        hablante = normalizar_hablante_v2(
            raw.get("hablante")
            or raw.get("rol")
            or raw.get("role")
            or raw.get("interlocutor")
        )
        segmentos.append({
            "segmento_id": normalizar_orden_segmento_v2(raw.get("segmento_id") or raw.get("id"), idx),
            "orden": normalizar_orden_segmento_v2(raw.get("orden") or raw.get("index"), idx),
            "timestamp": normalizar_timestamp_v2(raw.get("timestamp") or raw.get("momento") or raw.get("time")),
            "inicio_segundos": normalizar_segundos_v2(raw.get("inicio_segundos") or raw.get("inicio") or raw.get("start")),
            "fin_segundos": normalizar_segundos_v2(raw.get("fin_segundos") or raw.get("fin") or raw.get("end")),
            "speaker_original": raw.get("speaker_original") or raw.get("speaker"),
            "rol": hablante,
            "hablante": hablante,
            "texto_original": str(raw.get("texto_original") or texto).strip(),
            "texto_limpio": raw.get("texto_limpio"),
            "texto": texto,
            "confianza": normalizar_confianza(raw.get("confianza") or raw.get("confidence")),
            "fundamento": str(raw.get("fundamento") or raw.get("justificacion") or raw.get("motivo") or "").strip(),
        })

    if not segmentos:
        segmentos = segmentar_transcripcion_etiquetada_v2(transcripcion)
    if not segmentos:
        segmentos = segmentar_transcripcion_inferida_v2(transcripcion)

    metodo = str(interlocutores.get("metodo") or "").strip().upper()
    if not metodo:
        metodo = "DIARIZACION_ORIGINAL" if any(item.get("speaker_original") for item in segmentos) else ("INFERIDO_DESDE_TRANSCRIPCION" if segmentos else "NO_DISPONIBLE")
    confianza_global = normalizar_confianza(interlocutores.get("confianza_global") or confianza_global_segmentos_v2(segmentos))
    speakers = interlocutores.get("speakers") if isinstance(interlocutores.get("speakers"), dict) else {}
    if not speakers:
        speakers = {
            str(item.get("speaker_original")): item.get("hablante")
            for item in segmentos
            if item.get("speaker_original") and item.get("hablante")
        }
    speakers_normalizados = {
        str(speaker): normalizar_hablante_v2(rol)
        for speaker, rol in speakers.items()
        if normalizar_hablante_v2(rol) in {"AGENTE", "CLIENTE"}
    }
    if speakers_normalizados:
        for segmento in segmentos:
            speaker = str(segmento.get("speaker_original") or "").strip()
            rol_global = speakers_normalizados.get(speaker)
            if not rol_global:
                continue
            segmento["rol"] = rol_global
            segmento["hablante"] = rol_global
            if normalizar_confianza(segmento.get("confianza")) == "BAJA":
                segmento["confianza"] = "MEDIA"
            if not segmento.get("fundamento"):
                segmento["fundamento"] = "Rol aplicado desde mapping global speaker -> rol."
        speakers = speakers_normalizados
    integridad = interlocutores.get("integridad") if isinstance(interlocutores.get("integridad"), dict) else {}
    if not integridad and any(item.get("speaker_original") for item in segmentos):
        integridad = validar_integridad_diarizacion(segmentos, len(segmentos))
    metricas_roles = interlocutores.get("metricas_roles") if isinstance(interlocutores.get("metricas_roles"), dict) else {}
    if not metricas_roles:
        metricas_roles = metricas_cobertura_roles_v3(segmentos)
    return {
        "confianza_global": confianza_global if segmentos else "BAJA",
        "metodo": metodo,
        "speakers": speakers,
        "integridad": integridad,
        "metricas_roles": metricas_roles,
        "segmentos": segmentos,
    }


def primer_lista_segmentos_v2(data: Dict, interlocutores: Dict) -> List[Dict]:
    candidatos = [
        interlocutores.get("segmentos"),
        data.get("segmentos_interlocutores"),
        data.get("transcripcion_segmentos"),
        data.get("transcripcion_diarizada"),
        data.get("diarizacion"),
    ]
    for candidato in candidatos:
        if isinstance(candidato, list):
            return candidato
    return []


def normalizar_orden_segmento_v2(value, default: int) -> int:
    try:
        numero = int(value)
        return numero if numero > 0 else default
    except (TypeError, ValueError):
        return default


def normalizar_hablante_v2(value) -> str:
    texto = limpiar_key_texto(value)
    if any(token in texto for token in ("agente", "asesor", "gestor", "operador", "cobrador")):
        return "AGENTE"
    if any(token in texto for token in ("cliente", "titular", "deudor", "interlocutor", "usuario")):
        return "CLIENTE"
    return "NO_DETERMINADO"


def normalizar_timestamp_v2(value) -> Optional[str]:
    if value is None:
        return None
    texto = str(value).strip()
    if not texto or texto.lower() in {"null", "none", "no disponible", "-"}:
        return None
    match = re.search(r"\b(\d{1,2}:\d{2}(?::\d{2})?)\b", texto)
    return match.group(1) if match else None


def normalizar_segundos_v2(value) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        numero = float(value)
        return numero if numero >= 0 else None
    except (TypeError, ValueError):
        timestamp = normalizar_timestamp_v2(value)
        if not timestamp:
            return None
        partes = [int(x) for x in timestamp.split(":")]
        if len(partes) == 2:
            return float(partes[0] * 60 + partes[1])
        return float(partes[0] * 3600 + partes[1] * 60 + partes[2])


def segmentar_transcripcion_etiquetada_v2(transcripcion: str = "") -> List[Dict]:
    segmentos = []
    lineas = [linea.strip() for linea in str(transcripcion or "").splitlines() if linea.strip()]
    patron_diarizado = re.compile(
        r"^\[([^\]]+)\]\s+\{([^}]+)\}\s+<([^>]+)>\s+\(([^-)]*)-([^)]*)\)\s+(.+)$",
        re.I,
    )
    for idx, linea in enumerate(lineas, start=1):
        match = patron_diarizado.match(linea)
        if not match:
            continue
        timestamp, speaker, rol_raw, inicio, fin, texto = match.groups()
        hablante = normalizar_hablante_v2(rol_raw)
        segmentos.append({
            "segmento_id": len(segmentos) + 1,
            "orden": len(segmentos) + 1,
            "timestamp": timestamp,
            "inicio_segundos": normalizar_segundos_v2(inicio),
            "fin_segundos": normalizar_segundos_v2(fin),
            "speaker_original": speaker.strip(),
            "rol": hablante,
            "hablante": hablante,
            "texto_original": texto.strip(),
            "texto_limpio": None,
            "texto": texto.strip(),
            "confianza": "ALTA" if hablante in {"AGENTE", "CLIENTE"} else "BAJA",
            "fundamento": "Diarizacion original del audio con rol asignado por speaker.",
        })
    if segmentos:
        return segmentos

    patron = re.compile(r"^(?:(\d{1,2}:\d{2}(?::\d{2})?)\s+)?(agente|asesor|gestor|cliente|titular|deudor|interlocutor)\s*[:\-]\s*(.+)$", re.I)
    for idx, linea in enumerate(lineas, start=1):
        match = patron.match(linea)
        if not match:
            continue
        timestamp, hablante_raw, texto = match.groups()
        segmentos.append({
            "segmento_id": idx,
            "orden": idx,
            "timestamp": timestamp,
            "inicio_segundos": normalizar_segundos_v2(timestamp),
            "fin_segundos": None,
            "hablante": normalizar_hablante_v2(hablante_raw),
            "texto": texto.strip(),
            "confianza": "ALTA",
            "fundamento": "Etiqueta de hablante presente en la transcripcion.",
        })
    return segmentos


def segmentar_transcripcion_inferida_v2(transcripcion: str = "") -> List[Dict]:
    texto = re.sub(r"\s+", " ", str(transcripcion or "")).strip()
    if not texto:
        return []
    partes = re.split(r"(?<=[?!.])\s+", texto)
    segmentos = []
    ultimo_hablante = "NO_DETERMINADO"
    for parte in partes:
        fragmento = parte.strip()
        if len(fragmento) < 3:
            continue
        hablante, confianza, fundamento = inferir_hablante_fragmento_v2(fragmento, ultimo_hablante)
        if hablante in {"AGENTE", "CLIENTE"}:
            ultimo_hablante = hablante
        segmentos.append({
            "segmento_id": len(segmentos) + 1,
            "orden": len(segmentos) + 1,
            "timestamp": None,
            "inicio_segundos": None,
            "fin_segundos": None,
            "hablante": hablante,
            "texto": fragmento,
            "confianza": confianza,
            "fundamento": fundamento,
        })
    return segmentos


def inferir_hablante_fragmento_v2(fragmento: str, ultimo_hablante: str = "NO_DETERMINADO") -> tuple[str, str, str]:
    key = limpiar_key_texto(fragmento)
    senales_agente = [
        "buenos dias",
        "le habla",
        "le saluda",
        "mi banco",
        "mibanco",
        "deuda",
        "descuento",
        "facilidades",
        "pago",
        "abono",
        "fraccionar",
        "campana",
        "regularizar",
        "se le puede",
        "para que pueda",
        "le indicaron",
        "se acuerda",
        "pase a nuestra instancia",
    ]
    senales_cliente = [
        "si digame",
        "si senor",
        "si senorita",
        "no puedo",
        "no tengo",
        "yo no",
        "yo gano",
        "me podria",
        "estoy en juicio",
        "estoy pagando",
        "me dijo",
        "seria injusto",
        "no le puedo",
        "lo podria hacer",
    ]
    score_agente = sum(1 for item in senales_agente if item in key)
    score_cliente = sum(1 for item in senales_cliente if item in key)
    if score_agente > score_cliente:
        return "AGENTE", "MEDIA" if score_agente == 1 else "ALTA", "Inferido por frases de gestion, entidad o propuesta de cobranza."
    if score_cliente > score_agente:
        return "CLIENTE", "MEDIA" if score_cliente == 1 else "ALTA", "Inferido por respuesta, objecion o explicacion del cliente."
    if fragmento.endswith("?") and ultimo_hablante != "AGENTE":
        return "AGENTE", "BAJA", "Inferido por pregunta dentro de la gestion."
    return "NO_DETERMINADO", "BAJA", "No hay suficientes marcas para asignar hablante con seguridad."


def confianza_global_segmentos_v2(segmentos: List[Dict]) -> str:
    if not segmentos:
        return "BAJA"
    total = len(segmentos)
    altos = sum(1 for item in segmentos if item.get("confianza") == "ALTA")
    determinados = sum(1 for item in segmentos if item.get("hablante") in {"AGENTE", "CLIENTE"})
    if determinados / total >= 0.75 and altos / total >= 0.5:
        return "ALTA"
    if determinados / total >= 0.5:
        return "MEDIA"
    return "BAJA"


def normalizar_dimensiones_copc_v2(dimensiones) -> List[Dict]:
    criterios = []
    if isinstance(dimensiones, list):
        for dimension in dimensiones:
            if not isinstance(dimension, dict):
                continue
            segmento = str(dimension.get("nombre") or dimension.get("dimension") or dimension.get("segmento") or "")
            items = dimension.get("criterios") or dimension.get("items") or []
            if isinstance(items, list):
                for criterio in items:
                    if isinstance(criterio, dict):
                        criterios.append(convertir_criterio_v2(criterio, segmento))
    if any(str(item.get("codigo_criterio") or "").upper().startswith(("PENC.", "PECUF.", "PECN.", "PECC.")) for item in criterios):
        return criterios
    return completar_matriz_copc(criterios)


def convertir_criterio_v2(criterio: Dict, segmento: str) -> Dict:
    codigo = str(criterio.get("codigo") or criterio.get("codigo_criterio") or "").strip()
    nombre = str(criterio.get("nombre") or criterio.get("criterio") or "").strip()
    nombre_item = f"{codigo} {nombre}".strip()
    canon = buscar_item_canonico(codigo, nombre_item)
    segmento_canon, item_canon, peso_canon = canon
    catalogo_sgc = obtener_catalogo_sgc(codigo)
    if catalogo_sgc and str(codigo).upper().startswith(("PENC.", "PECUF.", "PECN.", "PECC.")):
        segmento_canon = str(criterio.get("subcategoria") or criterio.get("bloque") or segmento or "").strip()
        item_canon = nombre or nombre_item
        peso_canon = float(criterio.get("puntaje_maximo") or criterio.get("peso") or 0)
    peso_raw = criterio.get("puntaje_maximo")
    if peso_raw is None:
        peso_raw = criterio.get("peso")
    peso = numero_en_rango(peso_raw, 0, peso_canon or 100) if peso_raw is not None else peso_canon
    peso = peso or peso_canon
    estado = normalizar_estado_criterio_v2(criterio.get("estado") or criterio.get("resultado") or criterio.get("calificacion"))
    aplica = estado not in {"NO_APLICA", "NO_EVALUABLE"}
    if estado in {"NO_APLICA", "NO_EVALUABLE"}:
        aplica = False
    nota_raw = criterio.get("puntaje_obtenido")
    if nota_raw is None:
        nota_raw = criterio.get("nota")
    if nota_raw is None:
        nota_raw = criterio.get("nota_ia")
    nota = numero_en_rango(nota_raw, 0, peso)
    if estado in {"NO_EVALUABLE", "REQUIERE_REVISION"} and nota_raw in (None, ""):
        nota = 0
    resultado = resultado_legacy_desde_estado_v2(estado)
    codigo_final = str(criterio.get("codigo_criterio") or codigo or "").strip()
    catalogo_sgc = obtener_catalogo_sgc(codigo_final)
    if catalogo_sgc:
        grupo_sgc = catalogo_sgc["grupo_error_sgc"]
        factor_sgc = catalogo_sgc["factor_sgc"]
    elif str(criterio.get("criticidad") or "").strip():
        catalogo_sgc = catalogo_sgc_desde_pauta(criterio)
        grupo_sgc = catalogo_sgc["grupo_error_sgc"]
        factor_sgc = catalogo_sgc["factor_sgc"]
    else:
        sgc = clasificar_item_sgc({
            "codigo_criterio": codigo_final,
            "item": item_canon,
            "segmento": segmento_canon,
            "hallazgo": criterio.get("hallazgo"),
            "evidencia": " | ".join(evidencia_texto_v2(criterio.get("evidencias"))),
            "recomendacion": criterio.get("recomendacion"),
        })
        grupo_sgc = normalizar_grupo_sgc(sgc.get("grupo_error_sgc"), criterio)
        factor_sgc = str(sgc.get("factor_sgc") or nombre or item_canon)
        catalogo_sgc = sgc
    evidencia_textual = evidencia_texto_v2(criterio.get("evidencia_textual")) or evidencia_texto_v2(criterio.get("evidencias"))
    evidencia = " | ".join(evidencia_textual) or "-"
    conducta_observada = texto_limpio_criterio_v2(criterio.get("conducta_observada"))
    lectura_ia = texto_limpio_criterio_v2(criterio.get("lectura_ia"))
    hallazgo = texto_limpio_criterio_v2(criterio.get("hallazgo")) or lectura_ia or conducta_observada or "-"
    impacto_negocio = texto_limpio_criterio_v2(criterio.get("impacto_negocio"))
    impacto_cliente = texto_limpio_criterio_v2(criterio.get("impacto_cliente"))
    impacto = texto_limpio_criterio_v2(criterio.get("impacto")) or combinar_textos_v2(
        impacto_negocio,
        impacto_cliente,
        separador=" | ",
    )
    recomendacion_entrenable = texto_limpio_criterio_v2(criterio.get("recomendacion_entrenable"))
    recomendacion = recomendacion_entrenable or texto_limpio_criterio_v2(criterio.get("recomendacion")) or "-"
    frase_sugerida = texto_limpio_criterio_v2(criterio.get("frase_sugerida"))
    fortaleza_relacionada = texto_limpio_criterio_v2(criterio.get("fortaleza_relacionada"))
    motivo = texto_limpio_criterio_v2(criterio.get("motivo_no_evaluable")) or lectura_ia or conducta_observada or hallazgo
    return {
        "segmento": segmento_canon or formatear_segmento_v2(segmento),
        "item": item_canon or nombre_item or "Criterio sin nombre",
        "bloque": criterio.get("bloque") or catalogo_sgc.get("bloque"),
        "categoria": criterio.get("categoria"),
        "subcategoria": criterio.get("subcategoria"),
        "detalle": criterio.get("detalle"),
        "regla_evaluacion": criterio.get("regla_evaluacion"),
        "criticidad": criterio.get("criticidad") or catalogo_sgc.get("grupo_sgc_codigo"),
        "fuente_evidencia": criterio.get("fuente_evidencia") or catalogo_sgc.get("fuente_evidencia"),
        "regla_aplicabilidad": criterio.get("regla_aplicabilidad"),
        "requiere_evidencia": bool(criterio.get("requiere_evidencia")),
        "tipo_criterio": criterio.get("tipo_criterio") or "PUNTUABLE",
        "bloque_anulado": bool(criterio.get("bloque_anulado")),
        "motivo_bloque_anulado": criterio.get("motivo_bloque_anulado") or "",
        "posible_descalificacion": bool(criterio.get("posible_descalificacion")),
        "justificacion_descalificacion": criterio.get("justificacion_descalificacion"),
        "peso": peso,
        "nota": nota,
        "nota_ia": nota,
        "nota_supervisor": None,
        "nota_final": nota,
        "aplica": aplica,
        "motivo_no_aplica": str(criterio.get("motivo_no_evaluable") or ""),
        "resultado": resultado,
        "segmento_copc": segmento_canon or formatear_segmento_v2(segmento),
        "grupo_error_sgc": grupo_sgc,
        "grupo_sgc_codigo": catalogo_sgc.get("grupo_sgc_codigo"),
        "factor_sgc": factor_sgc,
        "severidad_base": catalogo_sgc.get("severidad_base"),
        "calificacion": resultado,
        "motivo": motivo,
        "hallazgo": hallazgo,
        "evidencia": evidencia,
        "momento": primer_timestamp_v2(criterio.get("evidencias")),
        "recomendacion": recomendacion,
        "impacto": impacto or "-",
        "codigo_criterio": str(criterio.get("codigo_criterio") or codigo or ""),
        "segmentos_evidencia": criterio.get("segmentos_evidencia") if isinstance(criterio.get("segmentos_evidencia"), list) else [],
        "segmentos_contexto": criterio.get("segmentos_contexto") if isinstance(criterio.get("segmentos_contexto"), list) else [],
        "tipo_evidencia": str(criterio.get("tipo_evidencia") or ""),
        "factor": str(criterio.get("factor") or factor_sgc),
        "grupo_sgc": grupo_sgc,
        "evidencia_textual": evidencia_textual,
        "conducta_observada": conducta_observada,
        "lectura_ia": lectura_ia,
        "impacto_negocio": impacto_negocio,
        "impacto_cliente": impacto_cliente,
        "recomendacion_entrenable": recomendacion_entrenable,
        "frase_sugerida": frase_sugerida,
        "fortaleza_relacionada": fortaleza_relacionada or None,
        "gravedad": str(criterio.get("gravedad") or ""),
        "puede_descalificar": bool(criterio.get("puede_descalificar")),
        "confianza": normalizar_confianza(criterio.get("confianza")),
        "requiere_revision": bool(criterio.get("requiere_revision") or estado == "REQUIERE_REVISION"),
        "requiere_feedback": resultado not in {"Cumple", "No aplica"},
        "requiere_coaching": bool(criterio.get("puede_descalificar") or grupo_sgc == SGC_GRUPO_CUMPLIMIENTO or estado == "NO_CUMPLE"),
        "motivo_feedback_coaching": hallazgo if resultado not in {"Cumple", "No aplica"} else "",
    }


def completar_evidencias_desde_segmentos_v3(evaluacion: List[Dict], segmentos: List[Dict]) -> List[Dict]:
    if not isinstance(evaluacion, list) or not isinstance(segmentos, list):
        return evaluacion
    segmentos_por_id = {}
    for segmento in segmentos:
        if not isinstance(segmento, dict):
            continue
        try:
            segmento_id = int(segmento.get("segmento_id") or segmento.get("id") or 0)
        except (TypeError, ValueError):
            continue
        if segmento_id > 0:
            segmentos_por_id[segmento_id] = segmento

    for item in evaluacion:
        if not isinstance(item, dict):
            continue
        ids = normalizar_ids_segmentos_pipeline_v3(item.get("segmentos_evidencia"), segmentos_por_id)
        if not ids:
            continue
        textos = []
        timestamps = []
        for segmento_id in ids:
            segmento = segmentos_por_id.get(segmento_id)
            if not segmento:
                continue
            texto = str(segmento.get("texto_limpio") or segmento.get("texto_original") or segmento.get("texto") or "").strip()
            if not texto:
                continue
            hablante = normalizar_hablante_v2(segmento.get("hablante") or segmento.get("rol"))
            prefijo = f"{hablante}: " if hablante in {"AGENTE", "CLIENTE"} else ""
            textos.append(f"{prefijo}{texto}")
            timestamp = segmento.get("timestamp") or formatear_timestamp(segmento.get("inicio_segundos"))
            if timestamp:
                timestamps.append(timestamp)
        if not textos:
            continue
        evidencia_actual = str(item.get("evidencia") or "").strip()
        if evidencia_actual in {"", "-", "No disponible", "No disponible.", "Evidencia textual no validada automáticamente."}:
            item["evidencia"] = " | ".join(textos)
        if not item.get("evidencia_textual"):
            item["evidencia_textual"] = textos
        if timestamps and not item.get("momento"):
            item["momento"] = timestamps[0]
    return evaluacion


def buscar_item_canonico(codigo: str, nombre: str) -> tuple[str, str, float]:
    texto = f"{codigo} {nombre}".strip().lower()
    for segmento, item, peso in COPC_ITEMS_CANONICOS:
        item_codigo = item.split(" ", 1)[0]
        if codigo and codigo == item_codigo:
            return segmento, item, peso
        if item_codigo and texto.startswith(item_codigo.lower()):
            return segmento, item, peso
    return formatear_segmento_v2(""), nombre, numero_en_rango(None, 0, 0)


def formatear_segmento_v2(value: str) -> str:
    texto = str(value or "").lower()
    if "cumpl" in texto:
        return "Cumplimiento"
    if "diagn" in texto:
        return "Diagnóstico"
    if "gestion" in texto or "gestión" in texto or "negoci" in texto:
        return "Gestión de solución"
    if "cierre" in texto:
        return "Cierre verificable"
    if "experiencia" in texto or "etica" in texto or "ética" in texto:
        return "Experiencia y ética"
    return "Sin segmento"


def normalizar_estado_criterio_v2(value) -> str:
    estado = str(value or "REQUIERE_REVISION").strip().upper()
    estado = estado.replace(" ", "_").replace("-", "_")
    aliases = {
        "PARCIAL": "PARCIAL_MEDIO",
        "REVISION_HUMANA": "REQUIERE_REVISION",
        "REQUIERE_REVISION_HUMANA": "REQUIERE_REVISION",
    }
    estado = aliases.get(estado, estado)
    return estado if estado in ESTADOS_COPC_V2 else "REQUIERE_REVISION"


def resultado_legacy_desde_estado_v2(estado: str) -> str:
    if estado == "CUMPLE":
        return "Cumple"
    if estado in {"PARCIAL_ALTO", "PARCIAL_MEDIO", "PARCIAL_BAJO"}:
        return "Parcial"
    if estado == "NO_CUMPLE":
        return "No cumple"
    if estado == "NO_APLICA":
        return "No aplica"
    if estado == "NO_EVALUABLE":
        return "No evaluable"
    return "Requiere revisión"


def codigo_item_v2(item: Dict) -> str:
    return obtener_codigo_item_copc(item)


def buscar_item_por_codigo_v2(evaluacion: List[Dict], codigo: str) -> Optional[Dict]:
    for item in evaluacion:
        if codigo_item_v2(item) == codigo:
            return item
    return None


def cita_textual_contextual_v2(transcripcion: str, patrones: List[str]) -> str:
    texto = str(transcripcion or "")
    for patron in patrones:
        match = re.search(patron, texto, flags=re.IGNORECASE)
        if match:
            return re.sub(r"\s+", " ", match.group(0).strip())
    return ""


def titularidad_confirmada_contextual_v2(transcripcion: str) -> bool:
    texto = re.sub(r"\s+", " ", str(transcripcion or "")).strip()
    texto_key = limpiar_key_texto(texto)
    patrones_key = [
        r"con\s+.{2,80}\?\s*(si|ella habla|soy yo|con ella|digame|si senor|si senorita)",
        r"me comunico con\s+.{2,80}\?\s*(si|ella habla|soy yo|con ella|digame)",
        r"hablo con\s+.{2,80}\?\s*(si|ella habla|soy yo|con ella|digame)",
        r"comunicar con\s+.{2,120}\?\s*(si|digame|si digame|si senor|si senorita)",
        r"se[nñ]or[a]?\s+.{2,120}\?\s*(si|digame|si digame|si senor|si senorita)",
    ]
    if any(re.search(patron, texto_key, flags=re.IGNORECASE) for patron in patrones_key):
        return True
    patrones = [
        r"¿?\s*con\s+[^?]{2,80}\?\s*¿?\s*(s[ií]|ella habla|soy yo|con ella|d[ií]game|s[ií]\s+señor(?:a|ita)?)\b",
        r"me comunico con\s+[^?]{2,80}\?\s*(s[ií]|ella habla|soy yo|con ella|d[ií]game)\b",
        r"hablo con\s+[^?]{2,80}\?\s*(s[ií]|ella habla|soy yo|con ella|d[ií]game)\b",
    ]
    return any(re.search(patron, texto, flags=re.IGNORECASE) for patron in patrones)


def oportunidad_gestion_contextual_v2(transcripcion: str) -> bool:
    texto = limpiar_key_texto(transcripcion)
    senales = ["no tengo", "no puedo", "pagar", "deuda", "descuento", "solucion", "abono", "credito", "agosto", "mes"]
    return sum(1 for senal in senales if senal in texto) >= 3


def cita_generica_gestion_v2(transcripcion: str) -> str:
    return cita_textual_contextual_v2(transcripcion, [
        r"Yo no tengo que proponer nada[^.?!]{0,180}",
        r"Las leyes le van a obligar[^.?!]{0,180}",
        r"No me voy a negar[^.?!]{0,220}",
        r"Si tuviera[^.?!]{0,180}",
        r"ese monto no lo tengo[^.?!]{0,180}",
        r"pagar[eé]?\s*(?:200|300)[^.?!]{0,180}",
        r"estoy en la sierra[^.?!]{0,180}",
    ])


def reparar_evaluacion_contextual_v2(evaluacion: List[Dict], data: Dict, transcripcion: str = "") -> List[Dict]:
    """
    Validación conservadora posterior al análisis IA.

    Esta función NO debe reconstruir la evaluación con reglas específicas de una
    llamada anterior ni sobreescribir criterios completos por coincidencias de
    palabras. La IA ya evaluó los 24 criterios con el prompt vigente.

    Responsabilidades:
    1. validar que las evidencias textuales pertenezcan a la transcripción actual;
    2. evitar contaminación entre evaluaciones;
    3. conservar score, resultado y hallazgo devueltos por IA salvo que la
       evidencia sea claramente inválida;
    4. ante evidencia inválida, pasar a revisión en vez de fabricar un hallazgo.
    """
    transcripcion_key = limpiar_key_texto(transcripcion)

    for item in evaluacion:
        if not isinstance(item, dict):
            continue

        evidencias = item.get("evidencia_textual")
        if not isinstance(evidencias, list):
            evidencias = evidencia_texto_v2(evidencias)

        evidencias_validas = []
        for evidencia in evidencias:
            frase = str(evidencia or "").strip()
            if not frase:
                continue

            frase_key = limpiar_key_texto(frase)
            if not frase_key:
                continue

            # Coincidencia directa normalizada.
            if frase_key in transcripcion_key:
                evidencias_validas.append(frase)
                continue

            # Tolerancia a pequeñas diferencias de puntuación/transcripción.
            tokens = [t for t in frase_key.split() if len(t) >= 4]
            if len(tokens) >= 4:
                ventana = " ".join(tokens[: min(8, len(tokens))])
                if ventana and ventana in transcripcion_key:
                    evidencias_validas.append(frase)

        if evidencias:
            item["evidencia_textual"] = evidencias_validas

            # Si la IA devolvió evidencia, pero ninguna pertenece a esta llamada,
            # no se mantiene el hallazgo como confirmado.
            if not evidencias_validas:
                # No destruimos el resultado ni el score del criterio.
                # Solo marcamos la literalidad de la evidencia como pendiente.
                item["evidencia"] = "Evidencia textual no validada automáticamente."
                item["evidencia_textual"] = []
                item["requiere_revision_evidencia"] = True

        evidencias_finales = item.get("evidencia_textual") or []
        if evidencias_finales:
            item["evidencia"] = " | ".join(str(x) for x in evidencias_finales if str(x).strip())

    return evaluacion

def reparar_errores_criticos_contextuales_v2(errores: List[Dict], evaluacion: List[Dict], data: Dict, transcripcion: str = "") -> List[Dict]:
    return list(errores or [])


def frase_anulante_contextual_v2(resultado: Dict, errores: List[Dict], transcripcion: str, descalificada: bool) -> str:
    for item in errores:
        texto = str(item.get("frase_textual") or item.get("evidencia") or "").strip()
        if texto and texto.lower() not in {"no disponible", "-", "maltrato psicológico explícito y presión excesiva"}:
            return texto
    return str(resultado.get("motivo_descalificacion") or ("No aplica" if not descalificada else "No disponible"))


def cita_anulante_valida_v2(texto: str) -> bool:
    valor = str(texto or "").strip()
    if not valor:
        return False
    key = limpiar_key_texto(valor)
    invalidos = [
        "no disponible",
        "no aplica",
        "maltrato psicologico explicito",
        "presion excesiva",
        "error critico",
        "falta grave",
    ]
    if any(item in key for item in invalidos):
        return False
    return len(valor) >= 12


def texto_limpio_criterio_v2(value) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return " | ".join(str(item).strip() for item in value if str(item).strip())
    texto = str(value).strip()
    if texto.lower() in {"null", "none", "no disponible", "-", "revisar transcripcion", "revisar transcripción"}:
        return ""
    return texto


def combinar_textos_v2(*items: str, separador: str = " ") -> str:
    textos = [str(item).strip() for item in items if str(item or "").strip()]
    return separador.join(textos)


def evidencia_texto_v2(evidencias) -> List[str]:
    salida = []
    if isinstance(evidencias, list):
        for evidencia in evidencias[:3]:
            if isinstance(evidencia, dict):
                texto = (
                    evidencia.get("texto")
                    or evidencia.get("frase")
                    or evidencia.get("frase_textual")
                    or evidencia.get("cita")
                    or evidencia.get("evidencia")
                    or evidencia.get("fragmento")
                )
                if texto:
                    salida.append(str(texto))
            elif evidencia:
                salida.append(str(evidencia))
    elif evidencias:
        salida.append(str(evidencias))
    return salida


def primer_timestamp_v2(evidencias) -> Optional[str]:
    if isinstance(evidencias, list):
        for evidencia in evidencias:
            if isinstance(evidencia, dict):
                timestamp = evidencia.get("timestamp") or evidencia.get("momento")
                if timestamp:
                    return str(timestamp)
    return None


def normalizar_errores_criticos_v2(value, evaluacion: List[Dict]) -> List[Dict]:
    rows = []
    if isinstance(value, list):
        for item in value:
            if not isinstance(item, dict):
                continue
            automatico = str(item.get("tipo") or item.get("clasificacion") or "").upper() in {"AUTOMATICO", "AUTOMÁTICO", "DESCALIFICANTE"}
            evidencia_raw = str(item.get("evidencia") or item.get("frase_textual") or "").strip()
            hallazgo_raw = str(item.get("hallazgo") or item.get("descripcion") or "").strip()
            calificacion_raw = normalizar_calificacion_sgc(item)
            if not evidencia_util_sgc(evidencia_raw):
                continue
            if not hallazgo_sgc_operativo(hallazgo_raw, evidencia_raw):
                continue
            clasificacion = clasificar_item_sgc(item)
            rows.append({
                "segmento": formatear_segmento_v2(item.get("segmento_copc") or item.get("segmento") or "Experiencia y ética"),
                "segmento_copc": formatear_segmento_v2(item.get("segmento_copc") or item.get("segmento") or "Experiencia y ética"),
                "grupo_error_sgc": normalizar_grupo_sgc(item.get("grupo_error_sgc") or SGC_GRUPO_CUMPLIMIENTO, item),
                "grupo_sgc_codigo": clasificacion.get("grupo_sgc_codigo"),
                "factor_sgc": str(clasificacion.get("factor_sgc") or item.get("factor_sgc") or item.get("criterio") or item.get("tipo") or "Conducta ética y no abuso"),
                "severidad_base": clasificacion.get("severidad_base"),
                "categoria": str(item.get("criterio") or item.get("tipo") or "Error crítico"),
                "severidad": "ANULANTE" if automatico else "GRAVE",
                "automatico": automatico,
                "requiere_revision": bool(item.get("requiere_revision") or not automatico),
                "calificacion": calificacion_raw,
                "hallazgo": hallazgo_raw or "-",
                "frase_textual": str(item.get("frase_textual") or item.get("frase") or "No disponible"),
                "momento": item.get("timestamp") or item.get("momento"),
                "evidencia": evidencia_raw or "-",
                "impacto": str(item.get("impacto") or "Riesgo crítico para calidad y cumplimiento."),
                "recomendacion": str(item.get("recomendacion") or "Revisión inmediata por supervisor."),
            })
    for item in evaluacion:
        estado = estado_sgc_normalizado(item)
        debe_mostrar = (
            estado == "NO_CUMPLE"
            or bool(item.get("posible_descalificacion"))
            or (estado == "REQUIERE_REVISION" and revision_sgc_visible(item))
            or item.get("gravedad") in {"ANULANTE", "GRAVE"}
        )
        if not debe_mostrar:
            continue
        if not hallazgo_sgc_operativo(item.get("hallazgo"), item.get("evidencia")):
            continue
        if item.get("puede_descalificar") or item.get("gravedad") in {"ANULANTE", "GRAVE"} or estado in {"NO_CUMPLE", "REQUIERE_REVISION"}:
            calificacion = normalizar_calificacion_sgc(item)
            rows.append({
                "segmento": item.get("segmento"),
                "segmento_copc": item.get("segmento_copc"),
                "grupo_error_sgc": item.get("grupo_error_sgc"),
                "grupo_sgc_codigo": item.get("grupo_sgc_codigo"),
                "factor_sgc": item.get("factor_sgc"),
                "categoria": item.get("factor_sgc"),
                "severidad": "REVISION" if calificacion == "Requiere revisión" else ("ANULANTE" if item.get("puede_descalificar") else "GRAVE"),
                "automatico": bool(item.get("puede_descalificar")),
                "requiere_revision": bool(item.get("requiere_revision")),
                "calificacion": calificacion,
                "hallazgo": item.get("hallazgo"),
                "frase_textual": item.get("evidencia"),
                "momento": item.get("momento"),
                "evidencia": item.get("evidencia"),
                "impacto": item.get("impacto"),
                "recomendacion": item.get("recomendacion"),
                "codigo_criterio": item.get("codigo_criterio"),
                "criterios_relacionados": [item.get("codigo_criterio")] if item.get("codigo_criterio") else [],
                "error_sgc_confirmado": bool(item.get("error_sgc_confirmado")),
            })
    return rows


def normalizar_hallazgos_no_criticos_v2(value, evaluacion: List[Dict]) -> List[Dict]:
    rows = []
    if isinstance(value, list):
        for item in value:
            if not isinstance(item, dict):
                continue
            if not hallazgo_sgc_operativo(item.get("hallazgo") or item.get("descripcion"), item.get("evidencia") or item.get("frase_textual")):
                continue
            clasificacion = clasificar_item_sgc(item)
            rows.append({
                "segmento": formatear_segmento_v2(item.get("segmento_copc") or item.get("segmento") or ""),
                "segmento_copc": formatear_segmento_v2(item.get("segmento_copc") or item.get("segmento") or ""),
                "grupo_error_sgc": normalizar_grupo_sgc(item.get("grupo_error_sgc") or SGC_GRUPO_NO_CRITICO, item),
                "grupo_sgc_codigo": clasificacion.get("grupo_sgc_codigo"),
                "factor_sgc": str(clasificacion.get("factor_sgc") or item.get("factor_sgc") or item.get("criterio") or "Hallazgo no crítico"),
                "severidad_base": clasificacion.get("severidad_base"),
                "categoria": str(item.get("criterio") or "Hallazgo no crítico"),
                "severidad": normalizar_severidad(item.get("severidad") or "MEDIA"),
                "hallazgo": str(item.get("hallazgo") or item.get("descripcion") or "-"),
                "frase_textual": str(item.get("frase_textual") or "No disponible"),
                "momento": item.get("timestamp") or item.get("momento"),
                "evidencia": str(item.get("evidencia") or "-"),
                "impacto": str(item.get("impacto") or "-"),
                "recomendacion": str(item.get("recomendacion") or "-"),
            })
    salida = []
    for item in evaluacion:
        if not isinstance(item, dict):
            continue
        if item.get("aplica", True) is False or item.get("puede_descalificar"):
            continue
        if item.get("mostrar_hallazgo_sgc") is False:
            continue
        calificacion = normalizar_calificacion_sgc(item)
        if calificacion in {"Cumple", "No aplica", "No evaluable"}:
            continue
        if calificacion == "Requiere revisión" and not revision_sgc_visible(item):
            continue
        if not hallazgo_sgc_operativo(item.get("hallazgo"), item.get("evidencia")):
            continue
        salida.append({
            "segmento": item.get("segmento"),
            "segmento_copc": item.get("segmento_copc"),
            "grupo_error_sgc": item.get("grupo_error_sgc"),
            "grupo_sgc_codigo": item.get("grupo_sgc_codigo"),
            "factor_sgc": item.get("factor_sgc"),
            "categoria": item.get("factor_sgc"),
            "severidad": "REVISION" if calificacion == "Requiere revisión" else normalizar_severidad(item.get("severidad_base") or item.get("severidad") or "MEDIA"),
            "calificacion": calificacion,
            "hallazgo": item.get("hallazgo"),
            "frase_textual": item.get("evidencia"),
            "momento": item.get("momento"),
            "evidencia": item.get("evidencia"),
            "impacto": item.get("impacto"),
            "recomendacion": item.get("recomendacion"),
            "codigo_criterio": item.get("codigo_criterio"),
            "criterios_relacionados": [item.get("codigo_criterio")] if item.get("codigo_criterio") else [],
            "error_sgc_confirmado": bool(item.get("error_sgc_confirmado")),
        })
    return rows + salida


def revision_sgc_visible(item: Dict) -> bool:
    if not isinstance(item, dict):
        return False
    evidencia = str(item.get("evidencia") or "").strip()
    hallazgo = str(item.get("hallazgo") or "").strip()
    motivo = str(item.get("motivo") or item.get("motivo_no_evaluable") or "").strip()
    placeholders = {
        "",
        "-",
        "No disponible",
        "No disponible.",
        "No evidenciado",
        "No evidenciado en la respuesta IA",
        "Evidencia textual no validada automáticamente.",
    }
    if not hallazgo_sgc_operativo(hallazgo, evidencia or motivo):
        return False
    if item.get("posible_descalificacion"):
        return True
    return evidencia not in placeholders or hallazgo not in placeholders or motivo not in placeholders


def evidencia_util_sgc(value: str) -> bool:
    texto = str(value or "").strip()
    if not texto:
        return False
    key = limpiar_key_texto(texto)
    invalidos = {
        "",
        "no disponible",
        "no disponible.",
        "no evidenciado",
        "no evidenciado en la respuesta ia",
        "evidencia textual no validada automaticamente",
    }
    return key not in invalidos and texto != "-"


def hallazgo_sgc_operativo(hallazgo, evidencia=None) -> bool:
    texto = limpiar_key_texto(f"{hallazgo or ''} {evidencia or ''}")
    if not texto:
        return False
    positivos = [
        "no divulga",
        "no se divulga",
        "mantiene trato respetuoso",
        "trato respetuoso",
        "sin interrupciones",
        "se desarrolla sin interrupciones",
        "no hay amenaza",
        "sin amenaza",
        "sin coaccion",
        "sin coacción",
        "confirma informacion",
        "confirma información",
        "se indaga",
        "el agente indaga",
        "agente indaga",
        "el agente busca ayudar",
        "busca ayudar",
        "el agente reconoce",
        "agente reconoce",
        "el agente responde",
        "agente responde",
        "permite que el cliente",
        "atiende la consulta",
    ]
    if any(limpiar_key_texto(token) in texto for token in positivos):
        negativos_explicitos = [
            "falta",
            "no confirma",
            "no valido",
            "no validó",
            "no identifica",
            "no indaga",
            "no ofrece",
            "no aborda",
            "no responde",
            "no reconoce",
            "no concreta",
            "incumple",
            "omitio",
            "omitió",
            "descalifica",
            "agrede",
        ]
        return any(limpiar_key_texto(token) in texto for token in negativos_explicitos)
    placeholders = {"", "-", "no disponible", "no aplica"}
    return texto not in placeholders


def consolidar_puntos_sgc(items: List[Dict]) -> List[Dict]:
    """
    Consolida hallazgos del mismo grupo/factor SGC.
    Conserva una sola fila visible y agrega cantidad de criterios relacionados.
    """
    grupos = {}
    orden = []

    for item in items or []:
        if not isinstance(item, dict):
            continue

        grupo = str(item.get("grupo_error_sgc") or "")
        factor = str(item.get("factor_sgc") or item.get("categoria") or "")
        key = (limpiar_key_texto(grupo), limpiar_key_texto(factor))

        if key not in grupos:
            copia = dict(item)
            copia["criterios_relacionados"] = []
            copia["calificacion"] = normalizar_calificacion_sgc(copia)
            copia["error_sgc_confirmado"] = bool(item.get("error_sgc_confirmado"))
            grupos[key] = copia
            orden.append(key)
        else:
            grupos[key]["error_sgc_confirmado"] = bool(grupos[key].get("error_sgc_confirmado") or item.get("error_sgc_confirmado"))
            grupos[key]["severidad"] = severidad_mas_alta_sgc(grupos[key].get("severidad"), item.get("severidad"))
            grupos[key]["calificacion"] = calificacion_mas_severa_sgc(grupos[key].get("calificacion"), item.get("calificacion"))

        codigos = item.get("criterios_relacionados") if isinstance(item.get("criterios_relacionados"), list) else []
        codigo = str(item.get("codigo_criterio") or "").strip()
        if codigo:
            codigos = [*codigos, codigo]
        for codigo_item in codigos:
            codigo_limpio = str(codigo_item or "").strip()
            if codigo_limpio and codigo_limpio not in grupos[key]["criterios_relacionados"]:
                grupos[key]["criterios_relacionados"].append(codigo_limpio)

        # Si el primer registro no tiene evidencia útil, usa otra del grupo.
        evidencia_actual = str(grupos[key].get("evidencia") or "").strip()
        evidencia_nueva = str(item.get("evidencia") or "").strip()
        if evidencia_actual in {"", "-", "No disponible.", "Evidencia textual no validada automáticamente."} and evidencia_nueva:
            grupos[key]["evidencia"] = evidencia_nueva

        if limpiar_key_texto(factor) == limpiar_key_texto("Cierre verificable 3C/4C"):
            grupos[key]["motivo"] = motivo_cierre_consolidado_sgc(grupos[key]["criterios_relacionados"])
            grupos[key]["hallazgo"] = grupos[key]["motivo"]

    return [grupos[key] for key in orden]


def severidad_mas_alta_sgc(actual, nueva) -> str:
    orden = {"": 0, "LEVE": 1, "MEDIA": 2, "REVISION": 2, "GRAVE": 3, "CRITICA": 3, "ANULANTE": 4}
    actual_txt = str(actual or "").upper()
    nueva_txt = str(nueva or "").upper()
    return nueva_txt if orden.get(nueva_txt, 0) > orden.get(actual_txt, 0) else actual_txt


def calificacion_mas_severa_sgc(actual, nueva) -> str:
    orden = {
        "": 0,
        "cumple": 0,
        "no aplica": 0,
        "requiere revision": 1,
        "parcial": 2,
        "no cumple": 3,
    }
    actual_key = limpiar_key_texto(actual)
    nueva_key = limpiar_key_texto(nueva)
    return str(nueva or actual or "") if orden.get(nueva_key, 0) > orden.get(actual_key, 0) else str(actual or nueva or "")


def motivo_cierre_consolidado_sgc(codigos: List[str]) -> str:
    nombres = {
        "4.1": "cantidad",
        "4.2": "fecha exacta",
        "4.3": "canal de pago",
        "4.4": "confirmación expresa",
        "4.5": "resumen y siguiente acción",
    }
    afectados = [nombres[codigo] for codigo in codigos if codigo in nombres]
    if not afectados:
        return "Brecha en cierre verificable."
    return "Brecha en cierre verificable: " + ", ".join(afectados) + "."


def deduplicar_puntos_criticos(items: List[Dict]) -> List[Dict]:
    vistos = set()
    salida = []
    for item in items:
        key = limpiar_key_texto(f"{item.get('hallazgo')} {item.get('frase_textual')} {item.get('factor_sgc')}")
        if key in vistos:
            continue
        vistos.add(key)
        salida.append(item)
    return salida


def deduplicar_textos(items: List[str]) -> List[str]:
    vistos = set()
    salida = []
    for item in items:
        texto = str(item or "").strip()
        key = limpiar_key_texto(texto)
        if not texto or key in vistos:
            continue
        vistos.add(key)
        salida.append(texto)
    return salida


def limpiar_key_texto(value: str) -> str:
    texto = unicodedata.normalize("NFKD", str(value or "").lower())
    texto = "".join(ch for ch in texto if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", texto)).strip()


def normalizar_confianza(value) -> str:
    texto = str(value or "MEDIA").strip().upper()
    if texto in {"ALTA", "HIGH"}:
        return "ALTA"
    if texto in {"BAJA", "LOW"}:
        return "BAJA"
    return "MEDIA"


def evidencias_desde_v2(data: Dict, puntos: List[Dict]) -> List[Dict]:
    frases = data.get("frases_detectadas") if isinstance(data.get("frases_detectadas"), dict) else {}
    evidencias = []
    for tipo, lista in (("Fortaleza", frases.get("adecuadas")), ("Mejora", frases.get("mejorables")), ("Riesgo", frases.get("riesgo"))):
        if isinstance(lista, list):
            for item in lista[:3]:
                texto = item.get("frase") if isinstance(item, dict) else item
                momento = item.get("timestamp") if isinstance(item, dict) else None
                if texto:
                    evidencias.append({
                        "tipo": tipo,
                        "momento": momento,
                        "frase_textual": str(texto),
                        "interpretacion": f"Frase detectada como {tipo.lower()} en COPC v2.",
                    })
    if evidencias:
        return evidencias[:8]
    return normalizar_evidencias_clave([], puntos)


def construir_prompt_analisis(transcripcion: str, comentario_supervisor: Optional[str]) -> str:
    return f"""
Analiza esta transcripcion de llamada de cobranza y devuelve exclusivamente un JSON valido.

La finalidad es ayudar al supervisor a dar feedback operativo al agente.
No es un informe oficial de calidad, auditoria ni scoring.

Evalua con esta rubrica operativa:
- Apertura: saludo, identificacion, motivo de llamada y tono inicial.
- Validacion: confirma cliente, deuda/contexto y comprension del cliente.
- Comunicacion: claridad, orden, lenguaje simple y escucha activa, que el agente no utilice sarcasmos y su tono debe ser atento, empático.
- Manejo de objecion: identifica causa real, explora alternativas y no fuerza respuestas.
- Negociacion: ofrece opciones concretas, valida capacidad de pago, monto, fecha y canal.
- Cierre: confirma acuerdo o siguiente accion, resume compromisos y deja trazabilidad.
- Riesgos: mala informacion, trato inadecuado, presion indebida, promesa debil o confusion.

Segmentos permitidos para puntos criticos:
- Inicio de llamada
- Desarrollo
- Manejo de objecion
- Cierre

Reglas:
- Basa cada hallazgo en algo observable de la transcripcion.
- Si la transcripcion no evidencia un punto, dilo como "No evidenciado" y no lo inventes.
- Diferencia fortalezas de oportunidades de mejora.
- El resumen debe mencionar cliente/contexto, objetivo de la llamada y resultado.
- La recomendacion debe ser concreta, entrenable y aplicable en la siguiente llamada.
- Incluye maximo 4 fortalezas, maximo 4 puntos criticos y maximo 3 alertas.
- El campo evidencia debe ser una referencia breve a lo ocurrido, no una cita extensa.

Estructura exacta requerida:
{{
  "resumen": "texto breve",
  "tipo_contacto": "Contacto efectivo | Contacto no efectivo | Tercero | Buzon | Cortada | Otro",
  "resultado_gestion": "Compromiso confirmado | Compromiso pendiente | Sin compromiso | Informativo | Otro",
  "objecion_principal": "texto o No evidenciada",
  "fortalezas_agente": ["texto"],
  "puntos_criticos": [
    {{
      "segmento": "Inicio de llamada | Desarrollo | Manejo de objecion | Cierre",
      "categoria": "texto",
      "hallazgo": "texto",
      "evidencia": "referencia breve de la llamada",
      "impacto": "texto",
      "recomendacion": "texto"
    }}
  ],
  "recomendacion_feedback_supervisor": "texto accionable",
  "guion_sugerido": "texto breve que el agente podria usar",
  "alertas": ["texto"],
  "nivel_oportunidad_mejora": "BAJA | MEDIA | ALTA"
}}

Comentario del supervisor:
{comentario_supervisor or "-"}

Transcripcion:
{transcripcion}
""".strip()


def texto_normalizado_sgc(value) -> str:
    return str(value or "").lower().strip()


def obtener_catalogo_sgc(codigo: str) -> Dict:
    codigo_limpio = str(codigo or "").strip()
    criterio_mibanco = obtener_criterio_mibanco(codigo_limpio)
    if criterio_mibanco:
        criticidad = str(criterio_mibanco.get("criticidad") or "").upper()
        if criticidad == SGC_CODIGO_NEGOCIO:
            grupo = SGC_GRUPO_NEGOCIO
        elif criticidad == SGC_CODIGO_USUARIO:
            grupo = SGC_GRUPO_USUARIO
        elif criticidad == SGC_CODIGO_CUMPLIMIENTO:
            grupo = SGC_GRUPO_CUMPLIMIENTO
        else:
            grupo = SGC_GRUPO_NO_CRITICO
        return {
            "grupo_sgc_codigo": criticidad or SGC_CODIGO_NO_CRITICO,
            "grupo_error_sgc": grupo,
            "factor_sgc": criterio_mibanco.get("nombre") or codigo_limpio,
            "severidad_base": "CRITICA" if criticidad in {SGC_CODIGO_NEGOCIO, SGC_CODIGO_USUARIO, SGC_CODIGO_CUMPLIMIENTO} else "MEDIA",
            "bloque": criterio_mibanco.get("bloque"),
            "fuente_evidencia": criterio_mibanco.get("fuente_evidencia"),
            "puede_descalificar": criterio_mibanco.get("puede_descalificar"),
        }
    return dict(SGC_CATALOGO.get(codigo_limpio) or {})


def estado_sgc_normalizado(item: Dict) -> str:
    texto = str(item.get("estado") or item.get("resultado") or item.get("calificacion") or "").strip()
    key = limpiar_key_texto(texto)
    if key in {"cumple", "c cumple"}:
        return "CUMPLE"
    if key in {"no cumple", "nc no cumple", "no evidenciado"}:
        return "NO_CUMPLE"
    if key in {"no aplica", "na no aplica"}:
        return "NO_APLICA"
    if key in {"no evaluable"}:
        return "NO_EVALUABLE"
    if key in {"requiere revision", "revision humana"} or "requiere revis" in key:
        return "REQUIERE_REVISION"
    if "parcial" in key:
        if "alto" in key:
            return "PARCIAL_ALTO"
        if "bajo" in key:
            return "PARCIAL_BAJO"
        return "PARCIAL_MEDIO"
    if "no cumple" in key:
        return "NO_CUMPLE"
    if "cumple" in key:
        return "CUMPLE"
    return "REQUIERE_REVISION"


def parcial_compromete_materialmente_sgc(codigo: str, estado: str, item: Optional[Dict] = None) -> bool:
    if not estado.startswith("PARCIAL"):
        return False
    if estado == "PARCIAL_BAJO":
        return True
    return impacto_material_sgc(codigo, item)


def impacto_material_sgc(codigo: str, item: Optional[Dict] = None) -> bool:
    if isinstance(item, dict) and item.get("impacto_material_sgc") is not None:
        return bool(item.get("impacto_material_sgc"))
    catalogo = obtener_catalogo_sgc(codigo)
    grupo = catalogo.get("grupo_sgc_codigo")
    if grupo == SGC_CODIGO_CUMPLIMIENTO:
        return True
    texto_impacto = limpiar_key_texto(
        " ".join([
            str((item or {}).get("impacto") or ""),
            str((item or {}).get("impacto_negocio") or ""),
            str((item or {}).get("impacto_cliente") or ""),
            str((item or {}).get("hallazgo") or ""),
        ])
    )
    claves_materiales = {
        "compromiso",
        "cierre",
        "pago",
        "abono",
        "recupero",
        "confusion",
        "cumplimiento",
        "riesgo",
        "titularidad",
    }
    return any(clave in texto_impacto for clave in claves_materiales)


def resolver_hallazgo_sgc(codigo: str, resultado: str, item: Optional[Dict] = None) -> Dict:
    catalogo = obtener_catalogo_sgc(codigo)
    estado = estado_sgc_normalizado({"estado": resultado}) if not isinstance(item, dict) else estado_sgc_normalizado({**item, "estado": resultado or item.get("estado")})
    severidad = str(catalogo.get("severidad_base") or "MEDIA").upper()
    grupo_catalogo = catalogo.get("grupo_error_sgc") or SGC_GRUPO_NO_CRITICO

    visible = False
    error_confirmado = False
    grupo_visible = grupo_catalogo
    calificacion_visible = "Requiere revisión"

    if estado in {"CUMPLE", "NO_APLICA", "NO_EVALUABLE"}:
        visible = False
        if estado == "CUMPLE":
            calificacion_visible = "Cumple"
        elif estado == "NO_APLICA":
            calificacion_visible = "No aplica"
        else:
            calificacion_visible = "No evaluable"
    elif estado == "REQUIERE_REVISION":
        visible = True
        error_confirmado = False
        calificacion_visible = "Requiere revisión"
    elif estado == "NO_CUMPLE":
        visible = True
        error_confirmado = True
        calificacion_visible = "No cumple"
        impacto_material = impacto_material_sgc(codigo, item)
        if severidad in {"MEDIA", "LEVE"} and str(codigo or "") not in {"4.1", "4.2", "4.3", "4.4", "4.5"} and not impacto_material:
            grupo_visible = SGC_GRUPO_NO_CRITICO
    elif estado.startswith("PARCIAL"):
        visible = True
        error_confirmado = True
        calificacion_visible = "Parcial"
        impacto_material = parcial_compromete_materialmente_sgc(codigo, estado, item)
        if str(codigo or "") in {"4.1", "4.2", "4.3", "4.4", "4.5"}:
            grupo_visible = SGC_GRUPO_NEGOCIO
        elif severidad in {"MEDIA", "LEVE"} or not impacto_material:
            grupo_visible = SGC_GRUPO_NO_CRITICO

    return {
        "estado_sgc": estado,
        "grupo_error_sgc": grupo_visible,
        "grupo_sgc_codigo": catalogo.get("grupo_sgc_codigo"),
        "factor_sgc": catalogo.get("factor_sgc") or str((item or {}).get("item") or "Criterio sin clasificación"),
        "severidad_base": severidad,
        "mostrar_hallazgo_sgc": visible,
        "error_sgc_confirmado": error_confirmado,
        "calificacion_sgc": calificacion_visible,
    }


def clasificar_item_sgc(item: Dict) -> Dict:
    """
    Clasificación SGC determinística.

    La IA evalúa conducta, evidencia, resultado y recomendación.
    El sistema decide grupo/factor SGC según el código técnico para evitar
    duplicidades y clasificaciones inconsistentes entre evaluaciones.
    """
    codigo = str(
        item.get("codigo_criterio")
        or item.get("codigo")
        or obtener_codigo_item_copc(item)
        or ""
    ).strip()

    catalogo = obtener_catalogo_sgc(codigo)
    if catalogo:
        return {
            "grupo_error_sgc": catalogo["grupo_error_sgc"],
            "grupo_sgc_codigo": catalogo["grupo_sgc_codigo"],
            "factor_sgc": catalogo["factor_sgc"],
            "severidad_base": catalogo["severidad_base"],
        }

    # Fallback histórico para registros antiguos que no tengan código.
    texto = " ".join([
        str(item.get("item") or ""),
        str(item.get("segmento") or ""),
        str(item.get("hallazgo") or ""),
        str(item.get("evidencia") or ""),
        str(item.get("recomendacion") or ""),
    ]).lower()

    for grupo, factor, claves in SGC_FACTORES:
        if any(str(clave).lower() in texto for clave in claves):
            if "tipific" in str(factor).lower():
                factor = "Registro y trazabilidad de gestión"
            return {"grupo_error_sgc": grupo, "factor_sgc": factor}

    return {
        "grupo_error_sgc": SGC_GRUPO_NO_CRITICO,
        "factor_sgc": str(item.get("item") or "Criterio sin clasificación"),
    }


def normalizar_grupo_sgc(value, item: Optional[Dict] = None) -> str:
    codigo = str((item or {}).get("codigo_criterio") or (item or {}).get("codigo") or obtener_codigo_item_copc(item or {}) or "").strip()
    catalogo = obtener_catalogo_sgc(codigo)
    if catalogo.get("grupo_error_sgc"):
        return catalogo["grupo_error_sgc"]
    texto = str(value or "").strip()
    if texto in SGC_GRUPOS_VALIDOS and texto != SGC_GRUPO_NO_APLICA:
        return texto
    lower = texto.lower()
    for grupo in SGC_GRUPOS_VALIDOS:
        if lower and lower == grupo.lower() and grupo != SGC_GRUPO_NO_APLICA:
            return grupo
    return clasificar_item_sgc(item or {}).get("grupo_error_sgc", SGC_GRUPO_NO_CRITICO)


def normalizar_calificacion_sgc(item: Dict) -> str:
    texto = str(item.get("calificacion") or item.get("resultado") or "").strip()
    lower = limpiar_key_texto(texto)

    if lower in {"requiere revision", "revision humana"} or "requiere revis" in lower:
        return "Requiere revisión"
    if lower in {"no aplica", "n a", "na"}:
        return "No aplica"
    if lower in {"no evaluable"}:
        return "No evaluable"
    if "parcial" in lower:
        return "Parcial"
    if "no cumple" in lower or "no evidenciado" in lower:
        return "No cumple"
    if "cumple" in lower:
        return "Cumple"

    # Si no hay estado confiable, no fabricar un incumplimiento.
    return "Requiere revisión"


def debe_contar_error_sgc(item: Dict) -> bool:
    """
    Solo cuenta brechas confirmadas.
    Revisión humana / evidencia pendiente NO equivale a NO CUMPLE.
    """
    if item.get("aplica") is False:
        return False

    grupo = item.get("grupo_error_sgc")
    if grupo == SGC_GRUPO_NO_APLICA:
        return False

    if item.get("error_sgc_confirmado") is not None:
        return bool(item.get("error_sgc_confirmado"))

    calificacion = limpiar_key_texto(
        item.get("calificacion") or item.get("resultado") or ""
    )

    if calificacion in {
        "cumple",
        "no aplica",
        "requiere revision",
        "revision humana",
        "no evaluable",
    }:
        return False

    return calificacion in {
        "no cumple",
        "parcial",
    }


def enriquecer_evaluacion_sgc(
    evaluacion: List[Dict],
    *,
    score_final: Optional[float] = None,
    nivel_riesgo: Optional[str] = None,
    falta_anulante: bool = False,
) -> List[Dict]:
    riesgo_alto = str(nivel_riesgo or "").upper() == "ALTO"
    score_bajo_feedback = score_final is not None and score_final < 80
    score_bajo_coaching = score_final is not None and score_final < 70
    for item in evaluacion:
        clasificacion = clasificar_item_sgc(item)
        codigo = str(item.get("codigo_criterio") or item.get("codigo") or obtener_codigo_item_copc(item) or "").strip()
        resolucion = resolver_hallazgo_sgc(codigo, str(item.get("estado") or item.get("resultado") or item.get("calificacion") or ""), item)
        grupo = resolucion.get("grupo_error_sgc") or clasificacion.get("grupo_error_sgc") or SGC_GRUPO_NO_CRITICO
        factor = str(resolucion.get("factor_sgc") or clasificacion.get("factor_sgc") or item.get("item") or "-")
        calificacion = resolucion.get("calificacion_sgc") or normalizar_calificacion_sgc(item)
        nota = float(item.get("nota") or 0)
        peso = float(item.get("peso") or 0)
        no_cumple = bool(item.get("aplica", True)) and bool(resolucion.get("error_sgc_confirmado"))
        cumplimiento_critico = grupo == SGC_GRUPO_CUMPLIMIENTO and no_cumple
        requiere_feedback = item.get("requiere_feedback")
        requiere_coaching = item.get("requiere_coaching")
        if requiere_feedback is None:
            requiere_feedback = bool(no_cumple)
        if requiere_coaching is None:
            requiere_coaching = bool(no_cumple and (cumplimiento_critico or falta_anulante or score_bajo_coaching or riesgo_alto))
        item["segmento_copc"] = str(item.get("segmento_copc") or item.get("segmento") or "-")
        item["grupo_error_sgc"] = grupo
        item["grupo_sgc_codigo"] = resolucion.get("grupo_sgc_codigo") or clasificacion.get("grupo_sgc_codigo")
        item["factor_sgc"] = factor
        item["severidad_base"] = resolucion.get("severidad_base") or clasificacion.get("severidad_base")
        item["estado_sgc"] = resolucion.get("estado_sgc")
        item["mostrar_hallazgo_sgc"] = bool(resolucion.get("mostrar_hallazgo_sgc"))
        item["error_sgc_confirmado"] = bool(resolucion.get("error_sgc_confirmado"))
        item["calificacion"] = calificacion
        item["motivo"] = str(item.get("motivo") or item.get("hallazgo") or "-")
        item["requiere_feedback"] = bool(requiere_feedback)
        item["requiere_coaching"] = bool(requiere_coaching)
        item["motivo_feedback_coaching"] = str(
            item.get("motivo_feedback_coaching")
            or item.get("motivo")
            or item.get("hallazgo")
            or ("Requiere seguimiento por brecha SGC/PEC." if requiere_coaching else "Requiere feedback puntual.")
        )
    return evaluacion


def construir_resumen_sgc(
    evaluacion: List[Dict],
    data_resumen: Optional[Dict] = None,
    *,
    score_final: Optional[float] = None,
    nivel_riesgo: Optional[str] = None,
    falta_anulante: bool = False,
) -> Dict:
    resumen = data_resumen if isinstance(data_resumen, dict) else {}
    conteos = {
        "errores_criticos_negocio": 0,
        "errores_criticos_usuario_final": 0,
        "errores_criticos_cumplimiento": 0,
        "errores_no_criticos": 0,
    }
    factores_contados = set()
    for item in evaluacion:
        if not debe_contar_error_sgc(item):
            continue
        grupo = item.get("grupo_error_sgc")
        factor = item.get("factor_sgc") or item.get("item") or "-"
        key = (limpiar_key_texto(grupo), limpiar_key_texto(factor))
        if key in factores_contados:
            continue
        factores_contados.add(key)
        if grupo == SGC_GRUPO_NEGOCIO:
            conteos["errores_criticos_negocio"] += 1
        elif grupo == SGC_GRUPO_USUARIO:
            conteos["errores_criticos_usuario_final"] += 1
        elif grupo == SGC_GRUPO_CUMPLIMIENTO:
            conteos["errores_criticos_cumplimiento"] += 1
        elif grupo == SGC_GRUPO_NO_CRITICO:
            conteos["errores_no_criticos"] += 1
    requiere_feedback = any(item.get("requiere_feedback") for item in evaluacion) or (score_final is not None and score_final < 80)
    requiere_coaching = (
        any(item.get("requiere_coaching") for item in evaluacion)
        or falta_anulante
        or (score_final is not None and score_final < 70)
        or str(nivel_riesgo or "").upper() == "ALTO"
    )
    motivo = resumen.get("motivo") or "Clasificación SGC/PEC generada desde la matriz COPC."
    return {
        **conteos,
        "requiere_feedback": bool(resumen.get("requiere_feedback", requiere_feedback)),
        "requiere_coaching": bool(resumen.get("requiere_coaching", requiere_coaching)),
        "motivo": str(motivo),
    }


def normalizar_analisis(data: Dict, transcripcion: str = "") -> Dict:
    es_version_v2 = es_copc_v2(data)
    if es_version_v2:
        data = normalizar_analisis_copc_v2(data, transcripcion=transcripcion)

    puntos = data.get("puntos_criticos")
    if not isinstance(puntos, list):
        puntos = []

    fortalezas = data.get("fortalezas_agente")
    if not isinstance(fortalezas, list):
        fortalezas = []

    alertas = data.get("alertas")
    if not isinstance(alertas, list):
        alertas = []
    habilidades = data.get("habilidades_blandas")
    if not isinstance(habilidades, list):
        habilidades = []

    clasificacion = data.get("clasificacion_copc") if isinstance(data.get("clasificacion_copc"), dict) else {}
    resultado_final = data.get("resultado_final") if isinstance(data.get("resultado_final"), dict) else {}
    calibracion = data.get("calibracion") if isinstance(data.get("calibracion"), dict) else {}
    calidad_transcripcion = data.get("calidad_transcripcion")
    if isinstance(calidad_transcripcion, dict):
        calidad_texto = str(calidad_transcripcion.get("nivel") or "MEDIA").upper()
        confianza = str(calidad_transcripcion.get("confianza") or calibracion.get("confianza_evaluacion") or "MEDIA").upper()
        requiere_revision = bool(calidad_transcripcion.get("requiere_revision_humana"))
        motivo_revision = str(calidad_transcripcion.get("motivo") or calibracion.get("motivo_revision") or "")
    else:
        calidad_texto = str(calidad_transcripcion or "MEDIA").upper()
        confianza = str(calibracion.get("confianza_evaluacion") or "MEDIA").upper()
        requiere_revision = bool(calibracion.get("requiere_revision_humana"))
        motivo_revision = str(calibracion.get("motivo_revision") or "")

    evaluacion = normalizar_evaluacion_calidad(data.get("evaluacion_calidad"))
    score_bruto, peso_aplicable, score_normalizado = calcular_score_normalizado(evaluacion)
    score_calidad = numero_en_rango(
        resultado_final.get("score_normalizado") if resultado_final else data.get("score_calidad"),
        0,
        100,
    )
    if score_calidad == 0 and score_bruto > 0 and not data.get("falta_anulante"):
        score_calidad = score_normalizado
    falta_anulante = bool(data.get("falta_anulante"))

    nivel = str(data.get("nivel_oportunidad_mejora") or "MEDIA").upper()
    if nivel not in {"BAJA", "MEDIA", "ALTA"}:
        nivel = "MEDIA"

    puntos_normalizados = [
        {
            "segmento": str(item.get("segmento") or "-"),
            "segmento_copc": str(item.get("segmento_copc") or item.get("segmento") or "-"),
            "grupo_error_sgc": normalizar_grupo_sgc(item.get("grupo_error_sgc"), item),
            "factor_sgc": str(item.get("factor_sgc") or clasificar_item_sgc(item).get("factor_sgc") or item.get("categoria") or "-"),
            "categoria": str(item.get("categoria") or "-"),
            "severidad": normalizar_severidad(item.get("severidad")),
            "hallazgo": str(item.get("hallazgo") or "-"),
            "frase_textual": str(item.get("frase_textual") or "No disponible"),
            "momento": str(item.get("momento") or "No disponible"),
            "evidencia": str(item.get("evidencia") or "-"),
            "impacto": str(item.get("impacto") or "-"),
            "recomendacion": str(item.get("recomendacion") or "-"),
        }
        for item in puntos
        if isinstance(item, dict)
    ]
    falta_anulante = falta_anulante or any(item["severidad"] == "ANULANTE" for item in puntos_normalizados)
    error_critico = falta_anulante or any(item["severidad"] in {"ANULANTE", "GRAVE"} for item in puntos_normalizados)
    if falta_anulante and not es_version_v2:
        score_calidad = 0
        score_normalizado = 0
        nivel = "ALTA"

    score_final = numero_en_rango(resultado_final.get("score_final") if resultado_final else score_calidad, 0, 100)
    if falta_anulante and not es_version_v2:
        score_final = 0
    estado_calidad = str(resultado_final.get("estado") or data.get("estado_calidad") or clasificar_estado_calidad(score_final, falta_anulante and not es_version_v2)).strip()
    nivel_riesgo = str(resultado_final.get("nivel_riesgo") or calcular_nivel_riesgo(score_final, error_critico)).upper()
    evaluacion = enriquecer_evaluacion_sgc(
        evaluacion,
        score_final=score_final,
        nivel_riesgo=nivel_riesgo,
        falta_anulante=falta_anulante,
    )
    resumen_sgc = construir_resumen_sgc(
        evaluacion,
        data.get("resumen_sgc") if isinstance(data.get("resumen_sgc"), dict) else {},
        score_final=score_final,
        nivel_riesgo=nivel_riesgo,
        falta_anulante=falta_anulante,
    )
    evidencias = normalizar_evidencias_clave(data.get("evidencias_clave"), puntos_normalizados)
    interlocutores = data.get("interlocutores") if isinstance(data.get("interlocutores"), dict) else {}
    segmentos_interlocutores = interlocutores.get("segmentos") if isinstance(interlocutores.get("segmentos"), list) else []

    return {
        "version_evaluacion": data.get("version_evaluacion"),
        "json_copc_v2": data.get("json_copc_v2"),
        "interlocutores": interlocutores,
        "segmentos_interlocutores": segmentos_interlocutores,
        "resumen": str(data.get("resumen") or "-"),
        "tipo_contacto": str(data.get("tipo_contacto") or "-"),
        "tipo_llamada": str(clasificacion.get("tipo_llamada") or data.get("tipo_llamada") or "-"),
        "evaluabilidad": str(clasificacion.get("evaluabilidad") or data.get("evaluabilidad") or "EVALUABLE"),
        "motivo_no_evaluable": str(clasificacion.get("motivo_no_evaluable") or data.get("motivo_no_evaluable") or ""),
        "objetivo_principal": str(clasificacion.get("objetivo_principal") or data.get("objetivo_principal") or "-"),
        "resultado_gestion": str(data.get("resultado_gestion") or "-"),
        "objecion_principal": str(data.get("objecion_principal") or "-"),
        "score_calidad": score_calidad,
        "score_final": score_final,
        "score_bruto": score_bruto,
        "peso_aplicable": peso_aplicable,
        "score_normalizado": score_normalizado,
        "estado_tecnico": data.get("estado_tecnico"),
        "estado_calidad": estado_calidad,
        "nivel_riesgo": nivel_riesgo,
        "error_critico": error_critico,
        "calidad_transcripcion": calidad_texto if calidad_texto in {"ALTA", "MEDIA", "BAJA"} else "MEDIA",
        "confianza_evaluacion": confianza if confianza in {"ALTA", "MEDIA", "BAJA"} else "MEDIA",
        "requiere_revision_humana": requiere_revision,
        "motivo_revision": motivo_revision,
        "evaluacion_calidad": evaluacion,
        "resumen_sgc": resumen_sgc,
        "habilidades_blandas": normalizar_habilidades_blandas(habilidades, evaluacion),
        "fortalezas_agente": [str(x) for x in fortalezas],
        "puntos_criticos": puntos_normalizados,
        "evidencias_clave": evidencias,
        "recomendacion_feedback_supervisor": str(data.get("recomendacion_feedback_supervisor") or "-"),
        "guion_sugerido": str(data.get("guion_sugerido") or "-"),
        "feedback_asesor": data.get("feedback_asesor") if isinstance(data.get("feedback_asesor"), dict) else {},
        "tipificaciones_sugeridas": data.get("tipificaciones_sugeridas") if isinstance(data.get("tipificaciones_sugeridas"), list) else [],
        "alertas": [str(x) for x in alertas],
        "falta_anulante": falta_anulante,
        "frase_anulante": str(data.get("frase_anulante") or ("No aplica" if not falta_anulante else "No disponible")),
        "momento_falta_anulante": str(data.get("momento_falta_anulante") or ("No aplica" if not falta_anulante else "No disponible")),
        "nivel_oportunidad_mejora": nivel,
    }


def obtener_codigo_item_copc(item: Dict) -> str:
    codigo_directo = str(item.get("codigo_criterio") or item.get("codigo") or "").strip()
    if codigo_directo:
        return codigo_directo
    texto = f"{item.get('item') or ''} {item.get('factor_sgc') or ''} {item.get('motivo') or ''}".strip()
    for segmento, nombre, _peso in COPC_ITEMS_CANONICOS:
        codigo = nombre.split(" ", 1)[0]
        if texto.startswith(codigo) or f" {codigo} " in f" {texto} ":
            return codigo
    return ""


def completar_matriz_copc(evaluacion: List[Dict]) -> List[Dict]:
    por_codigo = {obtener_codigo_item_copc(item): item for item in evaluacion if obtener_codigo_item_copc(item)}
    completa = []
    for segmento, nombre, peso in COPC_ITEMS_CANONICOS:
        codigo = nombre.split(" ", 1)[0]
        if codigo in por_codigo:
            item = por_codigo[codigo]
            item["segmento"] = item.get("segmento") or segmento
            item["segmento_copc"] = item.get("segmento_copc") or segmento
            item["item"] = nombre
            item["peso"] = peso
            item["nota"] = numero_en_rango(item.get("nota"), 0, peso)
            item["nota_ia"] = numero_en_rango(item.get("nota_ia"), 0, peso)
            item["nota_final"] = numero_en_rango(item.get("nota_final"), 0, peso)
            completa.append(item)
            continue
        completa.append({
            "segmento": segmento,
            "item": nombre,
            "peso": peso,
            "nota": 0,
            "nota_ia": 0,
            "nota_supervisor": None,
            "nota_final": 0,
            "aplica": False,
            "motivo_no_aplica": "Criterio no devuelto por IA; requiere revisión si era aplicable.",
            "resultado": "Requiere revisión",
            "segmento_copc": segmento,
            "grupo_error_sgc": "",
            "factor_sgc": "",
            "calificacion": "Requiere revisión",
            "motivo": "Criterio pendiente de validacion por respuesta incompleta de IA.",
            "hallazgo": "Criterio pendiente de validacion; no se debe concluir incumplimiento sin evidencia.",
            "evidencia": "No disponible.",
            "momento": "No disponible",
            "recomendacion": "Validar este criterio con la transcripcion antes de usarlo para feedback.",
            "codigo_criterio": codigo,
            "factor": "",
            "grupo_sgc": "",
            "evidencia_textual": [],
            "conducta_observada": "",
            "lectura_ia": "",
            "impacto_negocio": "",
            "impacto_cliente": "",
            "recomendacion_entrenable": "",
            "frase_sugerida": "",
            "fortaleza_relacionada": None,
            "requiere_feedback": False,
            "requiere_coaching": False,
            "motivo_feedback_coaching": "",
            "requiere_revision": True,
        })
    return completa


def normalizar_evaluacion_calidad(value) -> List[Dict]:
    if not isinstance(value, list):
        value = []

    normalizada = []
    for item in value:
        if not isinstance(item, dict):
            continue

        peso = numero_en_rango(item.get("peso"), 0, 100)
        aplica = item.get("aplica")
        resultado = str(item.get("resultado") or "-")
        if aplica is None:
            aplica = resultado.strip().lower() not in {"no aplica", "n/a", "na"}
        if "requiere revis" in resultado.strip().lower():
            aplica = True
        nota_ia = numero_en_rango(item.get("nota_ia", item.get("nota")), 0, peso)
        nota_supervisor = item.get("nota_supervisor")
        nota_supervisor = numero_en_rango(nota_supervisor, 0, peso) if nota_supervisor not in (None, "") else None
        nota_final = item.get("nota_final")
        nota_final = numero_en_rango(nota_final, 0, peso) if nota_final not in (None, "") else nota_ia
        nota = 0 if not aplica else nota_final
        evidencia_textual = evidencia_texto_v2(item.get("evidencia_textual")) or evidencia_texto_v2(item.get("evidencia"))
        conducta_observada = texto_limpio_criterio_v2(item.get("conducta_observada"))
        lectura_ia = texto_limpio_criterio_v2(item.get("lectura_ia"))
        hallazgo = texto_limpio_criterio_v2(item.get("hallazgo")) or lectura_ia or conducta_observada or "-"
        recomendacion_entrenable = texto_limpio_criterio_v2(item.get("recomendacion_entrenable"))
        normalizada.append({
            "segmento": str(item.get("segmento") or "-"),
            "item": str(item.get("item") or "-"),
            "peso": peso,
            "nota": nota,
            "nota_ia": nota_ia,
            "nota_supervisor": nota_supervisor,
            "nota_final": nota,
            "aplica": bool(aplica),
            "motivo_no_aplica": str(item.get("motivo_no_aplica") or ""),
            "resultado": resultado,
            "segmento_copc": str(item.get("segmento_copc") or item.get("segmento") or "-"),
            "grupo_error_sgc": str(item.get("grupo_error_sgc") or ""),
            "factor_sgc": str(item.get("factor_sgc") or ""),
            "calificacion": str(item.get("calificacion") or resultado),
            "motivo": str(item.get("motivo") or lectura_ia or conducta_observada or hallazgo or "-"),
            "hallazgo": hallazgo,
            "evidencia": " | ".join(evidencia_textual) or str(item.get("evidencia") or "-"),
            "momento": str(item.get("momento") or "No disponible"),
            "recomendacion": recomendacion_entrenable or str(item.get("recomendacion") or "-"),
            "codigo_criterio": str(item.get("codigo_criterio") or obtener_codigo_item_copc(item) or ""),
            "factor": str(item.get("factor") or item.get("factor_sgc") or ""),
            "grupo_sgc": str(item.get("grupo_sgc") or item.get("grupo_error_sgc") or ""),
            "evidencia_textual": evidencia_textual,
            "conducta_observada": conducta_observada,
            "lectura_ia": lectura_ia,
            "impacto_negocio": texto_limpio_criterio_v2(item.get("impacto_negocio")),
            "impacto_cliente": texto_limpio_criterio_v2(item.get("impacto_cliente")),
            "recomendacion_entrenable": recomendacion_entrenable,
            "frase_sugerida": texto_limpio_criterio_v2(item.get("frase_sugerida")),
            "fortaleza_relacionada": texto_limpio_criterio_v2(item.get("fortaleza_relacionada")) or None,
            "requiere_feedback": item.get("requiere_feedback"),
            "requiere_coaching": item.get("requiere_coaching"),
            "motivo_feedback_coaching": str(item.get("motivo_feedback_coaching") or ""),
            "requiere_revision": bool(item.get("requiere_revision")),
        })

    return completar_matriz_copc(normalizada)


def calcular_score_normalizado(evaluacion: List[Dict]) -> tuple[float, float, float]:
    score_bruto = 0.0
    peso_aplicable = 0.0
    for item in evaluacion:
        resultado = limpiar_key_texto(item.get("estado") or item.get("resultado") or item.get("calificacion") or "")
        motivo_no_aplica = str(item.get("motivo_no_aplica") or "").strip().lower()
        no_puntua = (
            resultado in {"no aplica", "no evaluable", "no aplicable"}
            or item.get("estado") in {"NO_APLICA", "NO_EVALUABLE"}
            or (item.get("aplica") is False and ("no aplica" in resultado or "no evaluable" in resultado or "no_evaluable" in motivo_no_aplica))
        )
        if no_puntua:
            continue
        score_bruto += float(item.get("nota") or 0)
        peso_aplicable += float(item.get("peso") or 0)
    score_bruto = round(score_bruto, 2)
    peso_aplicable = round(peso_aplicable, 2)
    score_normalizado = round((score_bruto / peso_aplicable) * 100, 2) if peso_aplicable else 0.0
    return score_bruto, peso_aplicable, score_normalizado


def calcular_pesos_detalle_evaluacion(evaluacion: List[Dict]) -> Dict[str, float]:
    detalle = {
        "peso_total": 0.0,
        "peso_no_aplica": 0.0,
        "peso_no_evaluable": 0.0,
    }
    for item in evaluacion or []:
        peso = float(item.get("peso") or item.get("puntaje_maximo") or 0)
        estado = estado_sgc_normalizado(item)
        detalle["peso_total"] += peso
        if estado == "NO_APLICA":
            detalle["peso_no_aplica"] += peso
        elif estado == "NO_EVALUABLE":
            detalle["peso_no_evaluable"] += peso
    return {key: round(value, 2) for key, value in detalle.items()}


def clasificar_estado_calidad(score: float, falta_anulante: bool = False) -> str:
    if falta_anulante:
        return "No aprobado"
    if score >= 85:
        return "Excelente"
    if score >= 75:
        return "Aprobado"
    if score >= 60:
        return "Con observacion"
    return "No aprobado"


def calcular_nivel_riesgo(score: float, error_critico: bool = False) -> str:
    if error_critico or score < 60:
        return "ALTO"
    if score < 80:
        return "MEDIO"
    return "BAJO"


def normalizar_evidencias_clave(value, puntos: List[Dict]) -> List[Dict]:
    evidencias = []
    if isinstance(value, list):
        for item in value[:8]:
            if not isinstance(item, dict):
                continue
            evidencias.append({
                "tipo": str(item.get("tipo") or item.get("categoria") or "Evidencia"),
                "segmento_copc": str(item.get("segmento_copc") or item.get("segmento") or "-"),
                "grupo_error_sgc": normalizar_grupo_sgc(item.get("grupo_error_sgc"), item),
                "factor_sgc": str(item.get("factor_sgc") or clasificar_item_sgc(item).get("factor_sgc") or "-"),
                "severidad": normalizar_severidad(item.get("severidad")),
                "momento": str(item.get("momento") or "No disponible"),
                "frase_textual": str(item.get("frase_textual") or item.get("frase") or "No disponible"),
                "interpretacion": str(item.get("interpretacion") or item.get("hallazgo") or item.get("evidencia") or "-"),
                "impacto": str(item.get("impacto") or "-"),
                "recomendacion": str(item.get("recomendacion") or "-"),
            })
    if evidencias:
        return evidencias
    return [
        {
            "tipo": item.get("categoria") or item.get("segmento") or "Punto critico",
            "segmento_copc": item.get("segmento") or "-",
            "grupo_error_sgc": normalizar_grupo_sgc(item.get("grupo_error_sgc"), item),
            "factor_sgc": str(item.get("factor_sgc") or clasificar_item_sgc(item).get("factor_sgc") or item.get("categoria") or "-"),
            "severidad": item.get("severidad") or "MEDIA",
            "momento": item.get("momento") or "No disponible",
            "frase_textual": item.get("frase_textual") or "No disponible",
            "interpretacion": item.get("hallazgo") or item.get("evidencia") or "-",
            "impacto": item.get("impacto") or "-",
            "recomendacion": item.get("recomendacion") or "-",
        }
        for item in puntos[:5]
    ]


def normalizar_severidad(value) -> str:
    severidad = str(value or "MEDIA").strip().upper()
    return severidad if severidad in {"ANULANTE", "GRAVE", "MEDIA", "LEVE"} else "MEDIA"


def normalizar_habilidades_blandas(value, evaluacion: List[Dict]) -> List[Dict]:
    if value:
        habilidades = []
        for item in value[:6]:
            if not isinstance(item, dict):
                continue
            habilidades.append({
                "habilidad": str(item.get("habilidad") or "-"),
                "nivel": normalizar_nivel_habilidad(item.get("nivel")),
                "evidencia": str(item.get("evidencia") or "-"),
                "recomendacion": str(item.get("recomendacion") or "-"),
            })
        if habilidades:
            return habilidades

    return habilidades_desde_evaluacion(evaluacion)


def normalizar_nivel_habilidad(value) -> str:
    nivel = str(value or "Medio").strip().capitalize()
    return nivel if nivel in {"Alto", "Medio", "Bajo"} else "Medio"


def habilidades_desde_evaluacion(evaluacion: List[Dict]) -> List[Dict]:
    referencias = [
        ("Actitud conciliadora", ("3.2", "5.1"), "Refuerza una postura colaborativa ante objeciones."),
        ("Empatia", ("5.1", "5.3"), "Validar la situacion del cliente antes de insistir."),
        ("Escucha activa", ("2.3", "2.4"), "Evitar interrupciones y confirmar entendimiento."),
        ("Vocalizacion y claridad", ("5.2",), "Mantener lenguaje claro, ordenado y facil de seguir."),
        ("Manejo emocional", ("5.3", "5.4"), "Sostener calma, respeto y control durante toda la llamada."),
    ]
    salida = []
    for habilidad, prefijos, recomendacion in referencias:
        relacionados = [
            item for item in evaluacion
            if any(str(item.get("item") or "").startswith(prefijo) for prefijo in prefijos)
        ]
        if not relacionados:
            nivel = "Medio"
            evidencia = "No hay evidencia suficiente para calificar con precision."
        else:
            peso = sum(float(item.get("peso") or 0) for item in relacionados)
            nota = sum(float(item.get("nota") or 0) for item in relacionados)
            porcentaje = (nota / peso) * 100 if peso else 0
            nivel = "Alto" if porcentaje >= 80 else "Medio" if porcentaje >= 55 else "Bajo"
            evidencia = "; ".join(str(item.get("hallazgo") or "-") for item in relacionados[:2])
        salida.append({
            "habilidad": habilidad,
            "nivel": nivel,
            "evidencia": evidencia,
            "recomendacion": recomendacion,
        })
    return salida


def numero_en_rango(value, minimo: float, maximo: float) -> float:
    try:
        numero = float(value)
    except (TypeError, ValueError):
        numero = minimo
    return round(min(max(numero, minimo), maximo), 2)


def generar_transcripcion_mock(metadata: Optional[Dict] = None) -> str:
    """Genera una transcripcion simulada para la primera etapa del modulo."""
    metadata = metadata or {}
    agente = metadata.get("agente") or "el agente"
    dni = metadata.get("dni") or "cliente"
    telefono = metadata.get("telefono") or "telefono registrado"

    return (
        f"Transcripcion simulada. {agente} saluda al cliente identificado como {dni}, "
        f"valida el telefono {telefono} y explica el motivo de contacto por una deuda "
        "pendiente. El cliente manifiesta dificultad de pago por falta de liquidez y pide "
        "una alternativa. El agente escucha la objecion, propone una fecha tentativa y "
        "refuerza la importancia de cumplir el compromiso. La llamada termina con un "
        "acuerdo preliminar sujeto a confirmacion del cliente."
    )


def item_copc(segmento: str, item: str, peso: float, nota: float, resultado: str, hallazgo: str) -> Dict:
    return {
        "segmento": segmento,
        "item": item,
        "peso": peso,
        "nota": nota,
        "resultado": resultado,
        "hallazgo": hallazgo,
        "evidencia": "Transcripcion simulada de cobranza.",
        "recomendacion": "Reforzar este criterio en coaching operativo bajo matriz COPC Cobranza.",
    }


def analizar_transcripcion_mock(
    transcripcion: str,
    comentario_supervisor: Optional[str] = None,
) -> Dict:
    """Devuelve una estructura de analisis compatible con una futura respuesta IA."""
    puntos_criticos: List[Dict] = [
        {
            "segmento": "Diagnostico",
            "categoria": "Capacidad de pago",
            "hallazgo": "El agente identifica la objecion, pero no profundiza en monto disponible ni fecha exacta.",
            "evidencia": "La llamada queda en una alternativa preliminar sin validar capacidad real.",
            "impacto": "Puede generar compromisos poco firmes o de baja probabilidad de cumplimiento.",
            "recomendacion": "Preguntar por ingreso esperado, fecha de disponibilidad y monto realista antes de cerrar.",
        },
        {
            "segmento": "Cierre",
            "categoria": "Cierre",
            "hallazgo": "El cierre queda como acuerdo preliminar y no como compromiso confirmado.",
            "evidencia": "No se confirma monto, fecha y canal como compromiso final.",
            "impacto": "Reduce claridad para seguimiento y recupero.",
            "recomendacion": "Repetir monto, fecha y consecuencia de incumplimiento antes de despedirse.",
        },
    ]

    if comentario_supervisor:
        puntos_criticos.append({
            "segmento": "Experiencia y riesgo",
            "categoria": "Contexto",
            "hallazgo": comentario_supervisor.strip(),
            "evidencia": "Comentario ingresado por el supervisor.",
            "impacto": "Debe considerarse en el feedback operativo del agente.",
            "recomendacion": "Contrastar la observacion con nuevas llamadas del mismo agente.",
        })

    return {
        "resumen": (
            "Llamada orientada a recuperar contacto y obtener compromiso. El agente mantiene "
            "tono correcto y explica el motivo, pero necesita fortalecer preguntas de capacidad "
            "de pago y cierre verificable."
        ),
        "tipo_contacto": "Contacto efectivo con objecion de pago",
        "resultado_gestion": "Compromiso preliminar",
        "objecion_principal": "Falta de liquidez inmediata",
        "evaluacion_calidad": [
            item_copc("Cumplimiento", "1.1 Apertura e identificacion", 4, 3, "Parcial", "Saluda y explica el motivo, pero puede ordenar mejor la apertura."),
            item_copc("Cumplimiento", "1.2 Validacion de titularidad y datos", 5, 3, "Parcial", "La validacion queda basica y debe reforzarse antes de exponer informacion."),
            item_copc("Cumplimiento", "1.3 Informacion correcta de deuda/gestion", 4, 3, "Parcial", "Explica motivo de contacto sin suficiente detalle verificable."),
            item_copc("Cumplimiento", "1.4 Registro y trazabilidad verbal", 2, 1, "Parcial", "No deja totalmente claro el siguiente paso registrado."),
            item_copc("Diagnostico", "2.1 Identificacion del motivo de atraso", 5, 3, "Parcial", "Identifica falta de liquidez, pero no profundiza la causa."),
            item_copc("Diagnostico", "2.2 Situacion economica actual/capacidad de pago", 5, 2, "Parcial", "No valida monto disponible ni fecha exacta."),
            item_copc("Diagnostico", "2.3 Escucha activa y control de conversacion", 3, 2, "Parcial", "Escucha la objecion y mantiene control general."),
            item_copc("Diagnostico", "2.4 Confirmacion de entendimiento", 2, 1, "Parcial", "No confirma claramente que entendio la situacion del cliente."),
            item_copc("Negociacion", "3.1 Negociacion escalonada", 10, 4, "Parcial", "Propone alternativa sin escalar desde deuda total o importe alto."),
            item_copc("Negociacion", "3.2 Manejo de objeciones", 7, 4, "Parcial", "Reconoce la objecion, pero necesita indagar mejor."),
            item_copc("Negociacion", "3.3 Propuesta de alternativas viables", 5, 3, "Parcial", "Ofrece una alternativa preliminar."),
            item_copc("Negociacion", "3.4 Argumentacion de beneficios y consecuencias", 4, 2, "Parcial", "Refuerza importancia de pagar, pero con poca argumentacion."),
            item_copc("Negociacion", "3.5 Orientacion a resultado", 4, 2, "Parcial", "Busca compromiso, aunque queda sujeto a confirmacion."),
            item_copc("Cierre", "4.1 Cierre 3C", 10, 3, "Parcial", "No confirma cuanto paga, donde paga y como pagara."),
            item_copc("Cierre", "4.2 Fecha/hora o plazo verificable", 5, 2, "Parcial", "La fecha queda tentativa."),
            item_copc("Cierre", "4.3 Confirmacion y recapitulacion", 5, 2, "Parcial", "No recapitula el acuerdo de forma verificable."),
            item_copc("Cierre", "4.4 Siguiente accion si no hay pago", 3, 1, "Parcial", "El seguimiento no queda claramente definido."),
            item_copc("Cierre", "4.5 Despedida profesional", 2, 2, "Cumple", "Cierra sin trato inadecuado."),
            item_copc("Experiencia y riesgo", "5.1 Tono profesional y empatico", 4, 3, "Parcial", "Mantiene tono correcto."),
            item_copc("Experiencia y riesgo", "5.2 Lenguaje claro, diccion y orden", 3, 2, "Parcial", "La gestion es comprensible, con oportunidad de ordenar mejor."),
            item_copc("Experiencia y riesgo", "5.3 Manejo emocional de la llamada", 3, 3, "Cumple", "No se evidencian interrupciones agresivas."),
            item_copc("Experiencia y riesgo", "5.4 Cumplimiento etico/no abuso", 5, 5, "Cumple", "No se evidencian insultos, amenazas ni presion indebida."),
        ],
        "fortalezas_agente": [
            "Mantiene trato cordial y ordenado.",
            "Explica el motivo de contacto sin confrontar.",
            "Reconoce la objecion del cliente antes de proponer alternativa.",
        ],
        "habilidades_blandas": [
            {
                "habilidad": "Actitud conciliadora",
                "nivel": "Alto",
                "evidencia": "El agente reconoce la objecion sin confrontar.",
                "recomendacion": "Mantener lenguaje colaborativo al negociar alternativas.",
            },
            {
                "habilidad": "Vocalizacion y claridad",
                "nivel": "Medio",
                "evidencia": "La explicacion es comprensible, pero puede ordenar mejor el cierre.",
                "recomendacion": "Cerrar con una frase breve que repita monto, fecha y canal.",
            },
            {
                "habilidad": "Escucha activa",
                "nivel": "Medio",
                "evidencia": "Escucha la falta de liquidez, pero no confirma capacidad exacta.",
                "recomendacion": "Parafrasear la objecion y validar entendimiento antes de proponer.",
            },
        ],
        "puntos_criticos": puntos_criticos,
        "recomendacion_feedback_supervisor": (
            "Dar feedback breve enfocado en dos conductas: sondear capacidad de pago con "
            "preguntas concretas y cerrar repitiendo monto, fecha y canal de pago."
        ),
        "guion_sugerido": (
            "Entiendo la dificultad. Para dejar un compromiso realista, indiqueme: "
            "que monto podria abonar, que dia exacto lo tendria disponible y por que canal "
            "realizaria el pago. Entonces registramos el acuerdo por ese monto y fecha."
        ),
        "alertas": [
            "Compromiso no totalmente confirmado.",
            "Objecion economica requiere seguimiento cercano.",
        ],
        "nivel_oportunidad_mejora": "MEDIA",
    }
