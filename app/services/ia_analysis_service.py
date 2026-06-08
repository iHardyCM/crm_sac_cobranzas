from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, List, Optional

from dotenv import load_dotenv
from sqlalchemy import text

from app.core.db_siscob import engine_siscob

ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / ".env")

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover - depende del entorno del servidor
    OpenAI = None


TRANSCRIPTION_MODEL = os.getenv("IA_FEEDBACK_TRANSCRIPTION_MODEL", "gpt-4o-mini-transcribe")
ANALYSIS_MODEL = os.getenv("IA_FEEDBACK_ANALYSIS_MODEL", "gpt-4o-mini")
PROMPT_CONFIG_TABLE = "CobAuto.dbo.ia_feedback_prompt_config"


def perfil_puede_editar_prompt(perfil: Optional[str]) -> bool:
    normalizado = str(perfil or "").strip().upper()
    return normalizado in {
        "ADMINISTRADOR",
        "JEFE DE CARTERA",
        "JEFE DE CARTERAS",
        "JEFE DE COBRANZA",
        "JEFE CARTERA",
    }


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
    return """
Analiza esta transcripcion de llamada de cobranza y devuelve exclusivamente un JSON valido.

La finalidad es ayudar al supervisor a dar feedback operativo al agente.
No es un informe oficial de auditoria ni scoring legal, pero si debe servir como evaluacion
operativa consistente.

Evalua con esta matriz ponderada:
- Presentacion 10%:
  - 1.1 Saludo: 4 puntos.
  - 1.2 Informacion de la deuda: 6 puntos.
- Sondeo 10%:
  - 2.1 Motivo de atraso: 5 puntos.
  - 2.2 Situacion actual: 5 puntos.
- Negociacion 35%:
  - 3.1 Negociacion escalonada: 15 puntos. Debe iniciar desde deuda total o importe alto,
    luego capital y finalmente campana/descuento; no debe iniciar por el monto mas bajo.
  - 3.2 Manejo de objeciones: 12 puntos.
  - 3.3 Beneficios: 8 puntos.
- Cierre 30%:
  - 4.1 Uso de las 3C: 15 puntos. Las 3C son cuanto paga, donde paga y como pagara.
  - 4.2 Consecuencias: 10 puntos.
  - 4.3 Despedida: 5 puntos.
- Filosofia Biznescob 15%:
  - 5.1 El personaje: 3 puntos.
  - 5.2 Tono de voz: 4 puntos.
  - 5.3 Diccion: 3 puntos.
  - 5.4 Manejo de la llamada: 5 puntos. Penaliza insultos, sarcasmos, presion indebida,
    trato despectivo, ironias o cualquier frase que deteriore la experiencia del cliente.

Reglas:
- Basa cada hallazgo en algo observable de la transcripcion.
- Si la transcripcion no evidencia un punto, usa resultado "No evidenciado" y nota 0.
- La nota de cada item debe estar entre 0 y su peso maximo.
- La evaluacion_calidad debe incluir obligatoriamente los 12 items de la matriz.
- La suma de notas debe reflejar la calidad general. Buen tono sin negociacion ni cierre
  no debe producir una nota alta.
- Diferencia fortalezas de oportunidades de mejora.
- El resumen debe mencionar cliente/contexto, objetivo de la llamada y resultado.
- La recomendacion debe ser concreta, entrenable y aplicable en la siguiente llamada.
- Incluye maximo 4 fortalezas, maximo 4 puntos criticos y maximo 3 alertas.
- El campo evidencia debe ser una referencia breve a lo ocurrido, no una cita extensa.

Segmentos permitidos para puntos criticos:
- Inicio de llamada
- Desarrollo
- Manejo de objecion
- Cierre

Estructura exacta requerida:
{
  "resumen": "texto breve",
  "tipo_contacto": "Contacto efectivo | Contacto no efectivo | Tercero | Buzon | Cortada | Otro",
  "resultado_gestion": "Compromiso confirmado | Compromiso pendiente | Sin compromiso | Informativo | Otro",
  "objecion_principal": "texto o No evidenciada",
  "evaluacion_calidad": [
    {
      "segmento": "Presentacion | Sondeo | Negociacion | Cierre | Filosofia Biznescob",
      "item": "1.1 Saludo",
      "peso": 4,
      "nota": 0,
      "resultado": "Cumple | Parcial | No cumple | No evidenciado",
      "hallazgo": "texto",
      "evidencia": "referencia breve de la llamada",
      "recomendacion": "texto"
    }
  ],
  "fortalezas_agente": ["texto"],
  "puntos_criticos": [
    {
      "segmento": "Inicio de llamada | Desarrollo | Manejo de objecion | Cierre",
      "categoria": "texto",
      "hallazgo": "texto",
      "evidencia": "referencia breve de la llamada",
      "impacto": "texto",
      "recomendacion": "texto"
    }
  ],
  "recomendacion_feedback_supervisor": "texto accionable",
  "guion_sugerido": "texto breve que el agente podria usar",
  "alertas": ["texto"],
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
        result = client.audio.transcriptions.create(
            model=TRANSCRIPTION_MODEL,
            file=audio_file,
        )

    text = getattr(result, "text", None)
    if not text and isinstance(result, dict):
        text = result.get("text")

    if not text:
        raise RuntimeError("La transcripcion no devolvio texto.")
    return text.strip()


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
    prompt = construir_prompt_analisis_calidad(transcripcion, comentario_supervisor, cartera=cartera)

    response = client.chat.completions.create(
        model=ANALYSIS_MODEL,
        temperature=0.2,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": (
                    "Eres un analista senior de calidad operativa en cobranzas telefonicas. "
                    "Tu trabajo es evaluar la llamada con criterio de supervision, detectar "
                    "conductas observables y generar feedback accionable para mejorar al agente. "
                    "No inventes hechos no presentes en la transcripcion. Responde solo JSON valido."
                ),
            },
            {"role": "user", "content": prompt},
        ],
    )

    content = response.choices[0].message.content or "{}"
    data = json.loads(content)
    return normalizar_analisis(data)


def construir_prompt_analisis_calidad(
    transcripcion: str,
    comentario_supervisor: Optional[str],
    cartera: Optional[str] = None,
) -> str:
    try:
        config = obtener_prompt_configuracion(cartera)
    except Exception:
        config = {}
    if config.get("prompt_base"):
        return f"""
{config["prompt_base"]}

Comentario del supervisor:
{comentario_supervisor or "-"}

Transcripcion:
{transcripcion}
""".strip()

    return f"""
Analiza esta transcripcion de llamada de cobranza y devuelve exclusivamente un JSON valido.

La finalidad es ayudar al supervisor a dar feedback operativo al agente.
No es un informe oficial de auditoria ni scoring legal, pero si debe servir como evaluacion
operativa consistente.

Evalua con esta matriz ponderada:
- Presentacion 10%:
  - 1.1 Saludo: 4 puntos.
  - 1.2 Informacion de la deuda: 6 puntos.
- Sondeo 10%:
  - 2.1 Motivo de atraso: 5 puntos.
  - 2.2 Situacion actual: 5 puntos.
- Negociacion 35%:
  - 3.1 Negociacion escalonada: 15 puntos. Debe iniciar desde deuda total o importe alto,
    luego capital y finalmente campana/descuento; no debe iniciar por el monto mas bajo.
  - 3.2 Manejo de objeciones: 12 puntos.
  - 3.3 Beneficios: 8 puntos.
- Cierre 30%:
  - 4.1 Uso de las 3C: 15 puntos. Las 3C son cuanto paga, donde paga y como pagara.
  - 4.2 Consecuencias: 10 puntos.
  - 4.3 Despedida: 5 puntos.
- Filosofia Biznescob 15%:
  - 5.1 El personaje: 3 puntos.
  - 5.2 Tono de voz: 4 puntos.
  - 5.3 Diccion: 3 puntos.
  - 5.4 Manejo de la llamada: 5 puntos. Penaliza insultos, sarcasmos, presion indebida,
    trato despectivo, ironias o cualquier frase que deteriore la experiencia del cliente.

Reglas:
- Basa cada hallazgo en algo observable de la transcripcion.
- Si la transcripcion no evidencia un punto, usa resultado "No evidenciado" y nota 0.
- La nota de cada item debe estar entre 0 y su peso maximo.
- La evaluacion_calidad debe incluir obligatoriamente los 12 items de la matriz.
- La suma de notas debe reflejar la calidad general. Buen tono sin negociacion ni cierre
  no debe producir una nota alta.
- Diferencia fortalezas de oportunidades de mejora.
- El resumen debe mencionar cliente/contexto, objetivo de la llamada y resultado.
- La recomendacion debe ser concreta, entrenable y aplicable en la siguiente llamada.
- Incluye maximo 4 fortalezas, maximo 4 puntos criticos y maximo 3 alertas.
- El campo evidencia debe ser una referencia breve a lo ocurrido, no una cita extensa.

Segmentos permitidos para puntos criticos:
- Inicio de llamada
- Desarrollo
- Manejo de objecion
- Cierre

Estructura exacta requerida:
{{
  "resumen": "texto breve",
  "tipo_contacto": "Contacto efectivo | Contacto no efectivo | Tercero | Buzon | Cortada | Otro",
  "resultado_gestion": "Compromiso confirmado | Compromiso pendiente | Sin compromiso | Informativo | Otro",
  "objecion_principal": "texto o No evidenciada",
  "evaluacion_calidad": [
    {{
      "segmento": "Presentacion | Sondeo | Negociacion | Cierre | Filosofia Biznescob",
      "item": "1.1 Saludo",
      "peso": 4,
      "nota": 0,
      "resultado": "Cumple | Parcial | No cumple | No evidenciado",
      "hallazgo": "texto",
      "evidencia": "referencia breve de la llamada",
      "recomendacion": "texto"
    }}
  ],
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


def normalizar_analisis(data: Dict) -> Dict:
    puntos = data.get("puntos_criticos")
    if not isinstance(puntos, list):
        puntos = []

    fortalezas = data.get("fortalezas_agente")
    if not isinstance(fortalezas, list):
        fortalezas = []

    alertas = data.get("alertas")
    if not isinstance(alertas, list):
        alertas = []

    evaluacion = normalizar_evaluacion_calidad(data.get("evaluacion_calidad"))
    score_calidad = round(sum(item["nota"] for item in evaluacion), 2)

    nivel = str(data.get("nivel_oportunidad_mejora") or "MEDIA").upper()
    if nivel not in {"BAJA", "MEDIA", "ALTA"}:
        nivel = "MEDIA"

    return {
        "resumen": str(data.get("resumen") or "-"),
        "tipo_contacto": str(data.get("tipo_contacto") or "-"),
        "resultado_gestion": str(data.get("resultado_gestion") or "-"),
        "objecion_principal": str(data.get("objecion_principal") or "-"),
        "score_calidad": score_calidad,
        "evaluacion_calidad": evaluacion,
        "fortalezas_agente": [str(x) for x in fortalezas],
        "puntos_criticos": [
            {
                "segmento": str(item.get("segmento") or "-"),
                "categoria": str(item.get("categoria") or "-"),
                "hallazgo": str(item.get("hallazgo") or "-"),
                "evidencia": str(item.get("evidencia") or "-"),
                "impacto": str(item.get("impacto") or "-"),
                "recomendacion": str(item.get("recomendacion") or "-"),
            }
            for item in puntos
            if isinstance(item, dict)
        ],
        "recomendacion_feedback_supervisor": str(data.get("recomendacion_feedback_supervisor") or "-"),
        "guion_sugerido": str(data.get("guion_sugerido") or "-"),
        "alertas": [str(x) for x in alertas],
        "nivel_oportunidad_mejora": nivel,
    }


def normalizar_evaluacion_calidad(value) -> List[Dict]:
    if not isinstance(value, list):
        value = []

    normalizada = []
    for item in value:
        if not isinstance(item, dict):
            continue

        peso = numero_en_rango(item.get("peso"), 0, 100)
        nota = numero_en_rango(item.get("nota"), 0, peso)
        normalizada.append({
            "segmento": str(item.get("segmento") or "-"),
            "item": str(item.get("item") or "-"),
            "peso": peso,
            "nota": nota,
            "resultado": str(item.get("resultado") or "-"),
            "hallazgo": str(item.get("hallazgo") or "-"),
            "evidencia": str(item.get("evidencia") or "-"),
            "recomendacion": str(item.get("recomendacion") or "-"),
        })

    return normalizada


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


def analizar_transcripcion_mock(
    transcripcion: str,
    comentario_supervisor: Optional[str] = None,
) -> Dict:
    """Devuelve una estructura de analisis compatible con una futura respuesta IA."""
    puntos_criticos: List[Dict] = [
        {
            "segmento": "Validacion de capacidad de pago",
            "categoria": "Sondeo",
            "hallazgo": "El agente identifica la objecion, pero no profundiza en monto disponible ni fecha exacta.",
            "evidencia": "La llamada queda en una alternativa preliminar sin validar capacidad real.",
            "impacto": "Puede generar compromisos poco firmes o de baja probabilidad de cumplimiento.",
            "recomendacion": "Preguntar por ingreso esperado, fecha de disponibilidad y monto realista antes de cerrar.",
        },
        {
            "segmento": "Cierre de compromiso",
            "categoria": "Cierre",
            "hallazgo": "El cierre queda como acuerdo preliminar y no como compromiso confirmado.",
            "evidencia": "No se confirma monto, fecha y canal como compromiso final.",
            "impacto": "Reduce claridad para seguimiento y recupero.",
            "recomendacion": "Repetir monto, fecha y consecuencia de incumplimiento antes de despedirse.",
        },
    ]

    if comentario_supervisor:
        puntos_criticos.append({
            "segmento": "Observacion del supervisor",
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
            {
                "segmento": "Presentacion",
                "item": "1.1 Saludo",
                "peso": 4,
                "nota": 3,
                "resultado": "Parcial",
                "hallazgo": "Saludo correcto, aunque podria reforzar identificacion y motivo.",
                "evidencia": "Transcripcion simulada con saludo inicial.",
                "recomendacion": "Abrir con saludo, nombre, empresa y motivo en una frase clara.",
            },
            {
                "segmento": "Negociacion",
                "item": "3.1 Negociacion escalonada",
                "peso": 15,
                "nota": 6,
                "resultado": "Parcial",
                "hallazgo": "Propone alternativa, pero no escala desde deuda total a opciones menores.",
                "evidencia": "La llamada queda en una fecha tentativa.",
                "recomendacion": "Partir por deuda total o monto alto y reducir solo ante negativa del cliente.",
            },
            {
                "segmento": "Cierre",
                "item": "4.1 Uso de las 3C",
                "peso": 15,
                "nota": 5,
                "resultado": "Parcial",
                "hallazgo": "No confirma claramente cuanto paga, donde paga y como pagara.",
                "evidencia": "El acuerdo queda preliminar.",
                "recomendacion": "Cerrar confirmando monto, lugar/canal y forma de pago.",
            },
            {
                "segmento": "Filosofia Biznescob",
                "item": "5.4 Manejo de la llamada",
                "peso": 5,
                "nota": 4,
                "resultado": "Parcial",
                "hallazgo": "Mantiene trato adecuado, sin evidencias de sarcasmo o agresion.",
                "evidencia": "La transcripcion simulada mantiene tono cordial.",
                "recomendacion": "Sostener tono profesional y evitar cualquier expresion ironica o despectiva.",
            },
        ],
        "fortalezas_agente": [
            "Mantiene trato cordial y ordenado.",
            "Explica el motivo de contacto sin confrontar.",
            "Reconoce la objecion del cliente antes de proponer alternativa.",
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
