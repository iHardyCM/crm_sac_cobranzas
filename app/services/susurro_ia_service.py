from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
import os
import re
from pathlib import Path
from typing import Dict, List, Optional
from uuid import uuid4

from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / ".env")

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover
    OpenAI = None


MAX_FRAGMENTOS = 80
MAX_CONTEXT_CHARS = 1400
SUSURRO_MODEL = os.getenv("SUSURRO_IA_MODEL", os.getenv("IA_FEEDBACK_ANALYSIS_MODEL", "gpt-4o-mini"))
SUSURRO_OPENAI_ENABLED = os.getenv("SUSURRO_IA_OPENAI_ENABLED", "1") != "0"


@dataclass(frozen=True)
class IntentRule:
    intent: str
    title: str
    priority: str
    patterns: tuple[str, ...]
    suggestion: str
    objective: str
    weight: float
    next_step: str


INTENT_RULES: List[IntentRule] = [
    IntentRule(
        intent="SITUACION_CRITICA",
        title="Situacion critica",
        priority="ALTA",
        patterns=(
            "me robaron",
            "me asaltaron",
            "accidente",
            "hospital",
            "enfermo",
            "estuve enfermo",
            "estuve enferma",
            "enfermedad",
            "salud",
            "operacion",
            "me opere",
            "emergencia",
            "fallecio",
            "extorsion",
            "quemaron",
        ),
        suggestion=(
            "Lamento mucho lo que me comenta y entiendo que una situacion asi puede afectar sus pagos. "
            "Para poder ayudarlo mejor, quisiera conocer como esta actualmente: ya se encuentra laborando "
            "o generando algun ingreso? A que se dedica hoy y como viene cubriendo sus gastos principales? "
            "Con esa informacion podemos revisar una planificacion de pagos mensual que sea realista y le "
            "permita regularizar el pendiente sin dejarlo nuevamente descubierto."
        ),
        objective="Contener emocionalmente y llevar la conversacion a una opcion viable.",
        weight=0.95,
        next_step="Validar situacion actual, ingreso y monto mensual posible.",
    ),
    IntentRule(
        intent="OBJECION_ECONOMICA",
        title="Objecion economica",
        priority="ALTA",
        patterns=(
            "no tengo plata",
            "no tengo dinero",
            "no puedo pagar",
            "no puedo cancelar",
            "no me alcanza",
            "sin trabajo",
            "no tengo trabajo",
            "termine contrato",
            "termino mi contrato",
            "se termino mi contrato",
            "me quede sin trabajo",
            "deje de trabajar",
            "dejé de trabajar",
            "no tengo ingresos",
            "no tengo como pagar",
            "se me complico",
        ),
        suggestion=(
            "Entiendo, si termino su contrato o dejo de trabajar, lo mas importante es aterrizar una opcion "
            "que si pueda cumplir. Actualmente esta laborando, buscando empleo o generando algun ingreso "
            "independiente? Como esta cubriendo sus gastos del mes? Con esa base podemos revisar un pago "
            "inicial manejable y luego una planificacion mensual para regularizar el pendiente sin prometer "
            "un monto que despues no pueda sostener."
        ),
        objective="Convertir la objecion en una propuesta parcial o fecha concreta.",
        weight=0.92,
        next_step="Sondear ingreso actual y proponer pago inicial manejable.",
    ),
    IntentRule(
        intent="SOBREENDEUDAMIENTO",
        title="Varias obligaciones",
        priority="ALTA",
        patterns=(
            "tengo otras deudas",
            "tengo otros creditos",
            "otras cajas",
            "otros bancos",
            "varias deudas",
            "debo en varios lados",
            "no solo con ustedes",
        ),
        suggestion=(
            "Comprendo que tenga varias obligaciones. Justamente por eso no quiero ofrecerle algo que no "
            "pueda cumplir. Ayudeme a entender: que pagos son los mas urgentes este mes y con que monto "
            "real podria iniciar para no dejar esta deuda sin atencion? Podemos ordenar una planificacion "
            "mensual y registrar un primer abono que este dentro de su capacidad."
        ),
        objective="Lograr un compromiso pequeno pero verificable.",
        weight=0.9,
        next_step="Proponer abono inicial y confirmar fecha exacta.",
    ),
    IntentRule(
        intent="PIDE_DESCUENTO",
        title="Solicita descuento",
        priority="ALTA",
        patterns=(
            "descuento",
            "rebaja",
            "beneficio",
            "campana",
            "condonacion",
            "quita",
            "cancelar con descuento",
        ),
        suggestion=(
            "Podemos revisar si existe algun beneficio, pero primero necesito entender su capacidad real. "
            "Si se aplicara una facilidad, usted estaria en condicion de cancelar el total o hablamos de "
            "un pago parcial? Digame que monto podria reunir y en que fecha, para orientarlo con una "
            "alternativa viable."
        ),
        objective="Validar capacidad antes de ofrecer beneficio.",
        weight=0.9,
        next_step="Preguntar si puede cancelar total o solo parcial.",
    ),
    IntentRule(
        intent="PROMESA_PAGO",
        title="Promesa de pago",
        priority="ALTA",
        patterns=(
            "voy a pagar",
            "pago hoy",
            "pago manana",
            "me comprometo",
            "lo pago",
            "lo cancelo",
            "si puedo pagar",
        ),
        suggestion=(
            "Perfecto, para dejarlo correctamente registrado confirmemos el compromiso: cuanto va a pagar, "
            "en que fecha exacta y por que canal lo realizara? Entonces registro que usted abonara ese monto "
            "por ese medio y hacemos seguimiento sobre ese acuerdo."
        ),
        objective="Convertir intencion en compromiso completo.",
        weight=0.96,
        next_step="Confirmar monto, canal y forma de pago.",
    ),
    IntentRule(
        intent="PROPONE_FECHA",
        title="Propone fecha",
        priority="MEDIA",
        patterns=(
            "para el dia",
            "para el 10",
            "el lunes",
            "el viernes",
            "fin de mes",
            "quincena",
            "cuando cobre",
            "cuando me paguen",
        ),
        suggestion=(
            "Perfecto, tomamos esa fecha como referencia. Para que no quede solo como una intencion, "
            "confirmeme por favor que monto pagaria ese dia y por que canal lo realizara. Asi lo dejamos "
            "registrado como compromiso claro."
        ),
        objective="Completar la promesa con monto y medio de pago.",
        weight=0.86,
        next_step="Pedir monto exacto y canal.",
    ),
    IntentRule(
        intent="YA_PAGO",
        title="Cliente indica pago",
        priority="MEDIA",
        patterns=(
            "ya pague",
            "ya cancele",
            "ya hice el pago",
            "ya realice el pago",
            "ya deposite",
            "ya abone",
        ),
        suggestion=(
            "Gracias por avisarme. Para ayudarlo a validar correctamente el pago, me confirma por favor "
            "la fecha, el monto y el canal por donde realizo la operacion? Si cuenta con constancia, "
            "tambien podemos usarla para acelerar la verificacion."
        ),
        objective="Obtener datos verificables del pago.",
        weight=0.94,
        next_step="Solicitar comprobante o datos de validacion.",
    ),
    IntentRule(
        intent="NO_RECONOCE_DEUDA",
        title="No reconoce deuda",
        priority="MEDIA",
        patterns=(
            "no reconozco",
            "no es mi deuda",
            "yo no saque",
            "no debo",
            "no firme",
            "no tengo deuda",
        ),
        suggestion=(
            "Entiendo su preocupacion. No vamos a discutirlo por telefono; primero validemos la informacion. "
            "Me confirma sus datos para revisar el detalle del credito y explicarle de donde proviene el "
            "pendiente? Si corresponde, dejamos constancia para validacion."
        ),
        objective="Bajar resistencia y ordenar la verificacion.",
        weight=0.9,
        next_step="Validar identidad y explicar detalle.",
    ),
    IntentRule(
        intent="SOLICITA_INFORMACION",
        title="Solicita informacion",
        priority="MEDIA",
        patterns=(
            "cuanto debo",
            "cual es el monto",
            "donde pago",
            "como pago",
            "numero de cuenta",
            "en que banco",
            "mandame la informacion",
        ),
        suggestion=(
            "Claro, le brindo la informacion. Luego de confirmarle monto y canales de pago, quisiera validar "
            "si podria regularizar hoy o separar una fecha concreta. La idea es que tenga claridad y podamos "
            "dejar una accion registrada."
        ),
        objective="Informar sin perder orientacion a compromiso.",
        weight=0.78,
        next_step="Dar dato y pedir decision de pago.",
    ),
    IntentRule(
        intent="LLAMAR_LUEGO",
        title="Pide llamada posterior",
        priority="MEDIA",
        patterns=(
            "llamame luego",
            "llamame mas tarde",
            "estoy trabajando",
            "estoy ocupado",
            "no puedo hablar",
            "despues hablamos",
        ),
        suggestion=(
            "Comprendo que ahora no pueda conversar. Para no incomodarlo y darle seguimiento correcto, "
            "indiqueme por favor un horario especifico en el que si pueda atendernos hoy o manana."
        ),
        objective="Obtener hora concreta de rellamada.",
        weight=0.84,
        next_step="Pedir horario exacto de contacto.",
    ),
    IntentRule(
        intent="RECHAZO_CONTACTO",
        title="Rechaza continuar",
        priority="ALTA",
        patterns=(
            "no me llames",
            "no quiero hablar",
            "dejame de llamar",
            "no insistan",
            "voy a colgar",
            "corta la llamada",
        ),
        suggestion=(
            "Entiendo, no deseo incomodarlo. Solo quiero dejarle la informacion necesaria para que pueda "
            "regularizar y evitar mayores inconvenientes. Si ahora no desea continuar, indiqueme si existe "
            "un horario o canal por el que podamos contactarlo de manera adecuada."
        ),
        objective="Evitar escalamiento negativo y cuidar experiencia.",
        weight=0.9,
        next_step="Ofrecer contacto en otro horario o canal.",
    ),
]


AGENT_CHECKS = {
    "saludo": ("buenos dias", "buenas tardes", "buenas noches", "le saluda", "mi nombre"),
    "monto": ("soles", "monto", "deuda", "capital", "total"),
    "fecha": ("hoy", "manana", "dia", "fecha", "quincena", "fin de mes"),
    "canal": ("banco", "agente", "yape", "transferencia", "app", "aplicativo", "ventanilla"),
    "cierre_3c": ("cuanto", "donde", "como", "monto", "canal"),
}

RISK_TERMS = (
    "carcel",
    "preso",
    "presa",
    "embargo",
    "amenaza",
    "insulto",
    "conch",
    "fastidia",
)

LOW_QUALITY_TERMS = (
    "suscribete",
    "gracias por ver",
    "subtitulos",
    "no no no no",
)

AGENT_LIKE_TERMS = (
    "dias de morosidad",
    "liquidar toda la deuda",
    "importe minimo",
    "puede realizar hoy",
    "numero de su dni",
    "medio de yape",
    "yapear servicios",
    "carta no adeudo",
    "plataforma de mi banco",
    "va a realizar el pago",
    "cuando va a realizar el pago",
    "lo llamo manana",
    "confirme la ejecucion del pago",
    "buenas tardes hasta luego",
    "deuda pendiente",
)


sessions: Dict[str, Dict] = {}


def crear_sesion(
    agente: Optional[str] = None,
    cartera: Optional[str] = None,
    modo: Optional[str] = None,
) -> Dict:
    session_id = uuid4().hex
    now = datetime.now().isoformat()
    sessions[session_id] = {
        "session_id": session_id,
        "agente": clean_value(agente) or "SIN_AGENTE",
        "cartera": clean_value(cartera),
        "modo": clean_value(modo) or "demo",
        "estado": "ACTIVA",
        "created_at": now,
        "updated_at": now,
        "fragments": [],
        "current": None,
        "metrics": empty_metrics(),
        "detected_intents": [],
        "alerts": [],
    }
    return preparar_sesion(sessions[session_id])


def obtener_sesion(session_id: str) -> Dict:
    session = sessions.get(session_id)
    if not session:
        raise ValueError("Sesion de susurro no encontrada.")
    return preparar_sesion(session)


def cerrar_sesion(session_id: str) -> Dict:
    session = sessions.get(session_id)
    if not session:
        raise ValueError("Sesion de susurro no encontrada.")
    session["estado"] = "CERRADA"
    session["updated_at"] = datetime.now().isoformat()
    return preparar_sesion(session)


def limpiar_sesion(session_id: str) -> Dict:
    session = sessions.get(session_id)
    if not session:
        raise ValueError("Sesion de susurro no encontrada.")
    session["fragments"] = []
    session["current"] = None
    session["metrics"] = empty_metrics()
    session["detected_intents"] = []
    session["alerts"] = []
    session["updated_at"] = datetime.now().isoformat()
    return preparar_sesion(session)


def recibir_fragmento(
    session_id: str,
    texto: str,
    speaker: Optional[str] = None,
    source: Optional[str] = None,
) -> Dict:
    session = sessions.get(session_id)
    if not session:
        raise ValueError("Sesion de susurro no encontrada.")

    speaker_norm = normalize_speaker(speaker)
    raw_text = clean_value(texto) or ""
    normalized = normalize_text(raw_text)
    timestamp = datetime.now().isoformat()

    if not raw_text:
        raise ValueError("El fragmento esta vacio.")

    quality = evaluate_quality(normalized)
    if speaker_norm == "cliente" and looks_like_agent_pitch(normalized):
        quality["discard"] = True
        quality["label"] = "POSIBLE_AGENTE"

    context = build_context(session["fragments"], normalized, speaker_norm)
    analysis = analyze_context(context, speaker_norm, normalized)
    analysis.setdefault("ai_mode", "rules")
    analysis = enhance_with_ai(session, speaker_norm, raw_text, context, analysis)
    update_metrics(session, speaker_norm, normalized, analysis)

    fragment = {
        "id": uuid4().hex[:12],
        "timestamp": timestamp,
        "speaker": speaker_norm,
        "source": clean_value(source) or "manual",
        "text": raw_text,
        "normalized_text": normalized,
        "context": context,
        "quality": quality,
        "analysis": analysis,
    }

    session["fragments"].append(fragment)
    if len(session["fragments"]) > MAX_FRAGMENTOS:
        session["fragments"] = session["fragments"][-MAX_FRAGMENTOS:]

    if is_actionable(analysis, quality):
        session["current"] = {
            **analysis,
            "text": raw_text,
            "speaker": speaker_norm,
            "timestamp": timestamp,
        }
        add_detected_intent(session, analysis.get("intent"))

    session["alerts"] = build_alerts(session)
    session["updated_at"] = timestamp

    return {
        "ok": True,
        "fragment": fragment,
        "session": preparar_sesion(session),
    }


def preparar_sesion(session: Dict) -> Dict:
    fragments = session.get("fragments") or []
    return {
        "session_id": session.get("session_id"),
        "agente": session.get("agente"),
        "cartera": session.get("cartera"),
        "modo": session.get("modo"),
        "estado": session.get("estado"),
        "created_at": session.get("created_at"),
        "updated_at": session.get("updated_at"),
        "current": session.get("current"),
        "metrics": session.get("metrics") or empty_metrics(),
        "detected_intents": session.get("detected_intents") or [],
        "alerts": session.get("alerts") or [],
        "fragments": fragments[-MAX_FRAGMENTOS:],
        "total_fragments": len(fragments),
    }


def analyze_context(context: str, speaker: str, current_text: str) -> Dict:
    if speaker == "agente":
        return analyze_agent_text(context, current_text)
    current_analysis = analyze_client_text(current_text)
    if is_clear_client_intent(current_analysis):
        current_analysis["reason"] = f"{current_analysis.get('reason', '')} Analisis basado en el ultimo fragmento claro.".strip()
        return current_analysis
    return analyze_client_text(context)


def analyze_client_text(context: str) -> Dict:
    if not context:
        return low_confidence("Sin contexto suficiente.")

    if has_low_quality_signal(context):
        return {
            **low_confidence("Texto probablemente ruidoso o repetitivo."),
            "quality_flag": "RUIDO",
        }

    priority_match = priority_overrides(context)
    if priority_match:
        return priority_match

    matches = []
    for rule in INTENT_RULES:
        score = count_matches(context, rule.patterns)
        if score:
            confidence = min(0.99, rule.weight + min(score * 0.03, 0.09))
            matches.append((confidence, score, rule))

    if not matches:
        return low_confidence("No se detecto intencion clara del cliente.")

    confidence, score, rule = sorted(matches, key=lambda item: (item[0], item[1]), reverse=True)[0]
    return {
        "intent": rule.intent,
        "title": rule.title,
        "priority": rule.priority,
        "confidence": round(confidence, 2),
        "suggestion": rule.suggestion,
        "objective": rule.objective,
        "next_step": rule.next_step,
        "reason": f"Coincidencias detectadas: {score}.",
        "checklist": build_checklist(rule.intent),
        "ai_mode": "rules",
    }


def analyze_agent_text(context: str, current_text: str) -> Dict:
    checks = {key: any(term in context for term in terms) for key, terms in AGENT_CHECKS.items()}
    risk = any(term in context for term in RISK_TERMS)

    if risk:
        return {
            "intent": "RIESGO_DISCURSO_AGENTE",
            "title": "Riesgo en discurso",
            "priority": "ALTA",
            "confidence": 0.92,
            "suggestion": "Corrige el tono de inmediato. Evita amenazas, presion indebida o frases que deterioren la experiencia.",
            "objective": "Cuidar trato, cumplimiento y calidad de llamada.",
            "next_step": "Retomar con lenguaje neutral y empatico.",
            "reason": "Se detectaron terminos sensibles en el discurso del agente.",
            "checklist": checks,
            "ai_mode": "rules",
        }

    missing_3c = not (checks["monto"] and checks["fecha"] and checks["canal"])
    if missing_3c:
        return {
            "intent": "CIERRE_INCOMPLETO",
            "title": "Cierre incompleto",
            "priority": "MEDIA",
            "confidence": 0.78,
            "suggestion": "Antes de cerrar, confirma las 3C: cuanto paga, cuando/fecha y por que canal o medio lo hara.",
            "objective": "Evitar compromisos ambiguos.",
            "next_step": "Pedir monto, fecha y canal en una sola confirmacion.",
            "reason": "Aun no se evidencian todas las 3C en el discurso del agente.",
            "checklist": checks,
            "ai_mode": "rules",
        }

    return {
        "intent": "AGENTE_EN_RUTA",
        "title": "Gestion encaminada",
        "priority": "BAJA",
        "confidence": 0.72,
        "suggestion": "Mantiene direccion correcta. Refuerza el resumen del acuerdo y valida conformidad del cliente.",
        "objective": "Cerrar con claridad y trazabilidad.",
        "next_step": "Repetir acuerdo y despedir cordialmente.",
        "reason": "El discurso contiene senales de cierre suficientes.",
        "checklist": checks,
        "ai_mode": "rules",
    }


def priority_overrides(context: str) -> Optional[Dict]:
    illness_terms = ("enfermo", "enferma", "enfermedad", "estuve enfermo", "estuve enferma", "salud", "hospital")
    job_loss_terms = (
        "sin trabajo",
        "no tengo trabajo",
        "termine contrato",
        "termino mi contrato",
        "se termino mi contrato",
        "deje de trabajar",
        "me quede sin trabajo",
    )
    if any(item in context for item in illness_terms) and any(item in context for item in job_loss_terms):
        return {
            "intent": "ENFERMEDAD_Y_PERDIDA_INGRESO",
            "title": "Salud y perdida de ingreso",
            "priority": "ALTA",
            "confidence": 0.98,
            "suggestion": (
                "Lamento mucho lo que me comenta y lo entiendo. Si estuvo enfermo y ademas dejo de trabajar "
                "por el termino de contrato, lo primero es conocer su situacion actual para proponer algo que "
                "si pueda cumplir. Actualmente ya se encuentra laborando o generando algun ingreso? A que se "
                "dedica en este momento y como viene sustentando sus gastos? Con esa informacion podemos "
                "acordar una planificacion de pagos mensual y evaluar un primer abono manejable para empezar "
                "a regularizar el pendiente."
            ),
            "objective": "Mostrar empatia, diagnosticar capacidad actual y proponer plan mensual realista.",
            "next_step": "Preguntar situacion laboral actual, fuente de ingresos y monto mensual posible.",
            "reason": "El cliente combina problema de salud con perdida o pausa de ingresos.",
            "checklist": build_checklist("OBJECION_ECONOMICA"),
        }

    negative_payment = (
        "no puedo pagar",
        "no puedo cancelar",
        "no tengo para pagar",
        "no voy a pagar",
        "ahorita no puedo pagar",
    )
    if any(item in context for item in negative_payment):
        rule = next(item for item in INTENT_RULES if item.intent == "OBJECION_ECONOMICA")
        return rule_to_analysis(rule, 0.97, "Negacion o imposibilidad de pago detectada.")

    if "no me comprometo" in context or "no puedo confirmar" in context:
        return {
            "intent": "CLIENTE_DUDA",
            "title": "No confirma compromiso",
            "priority": "MEDIA",
            "confidence": 0.86,
            "suggestion": "No fuerces el compromiso. Pregunta que condicion falta para confirmar monto o fecha.",
            "objective": "Convertir duda en siguiente accion concreta.",
            "next_step": "Preguntar que necesita para confirmar.",
            "reason": "Cliente evita confirmar compromiso.",
            "checklist": build_checklist("CLIENTE_DUDA"),
        }
    return None


def rule_to_analysis(rule: IntentRule, confidence: float, reason: str) -> Dict:
    return {
        "intent": rule.intent,
        "title": rule.title,
        "priority": rule.priority,
        "confidence": confidence,
        "suggestion": rule.suggestion,
        "objective": rule.objective,
        "next_step": rule.next_step,
        "reason": reason,
        "checklist": build_checklist(rule.intent),
        "ai_mode": "rules",
    }


def low_confidence(reason: str) -> Dict:
    return {
        "intent": "NO_CLARO",
        "title": "Esperando contexto",
        "priority": "BAJA",
        "confidence": 0.3,
        "suggestion": "Espera mas contexto o repregunta de forma simple: el inconveniente es monto, fecha o medio de pago?",
        "objective": "Recuperar claridad antes de orientar al agente.",
        "next_step": "Escuchar un fragmento adicional.",
        "reason": reason,
        "checklist": build_checklist("NO_CLARO"),
        "ai_mode": "rules",
    }


def enhance_with_ai(session: Dict, speaker: str, raw_text: str, context: str, analysis: Dict) -> Dict:
    if speaker != "cliente":
        return analysis
    if analysis.get("intent") == "NO_CLARO":
        return analysis
    if not ia_susurro_configurada():
        return analysis

    recent = build_recent_transcript(session.get("fragments") or [], raw_text)
    prompt = build_ai_prompt(session, raw_text, context, recent, analysis)

    try:
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.chat.completions.create(
            model=SUSURRO_MODEL,
            temperature=0.35,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Eres un copiloto silencioso para agentes de cobranza telefonica. "
                        "Tu unica tarea es sugerir la siguiente frase que el agente podria decir. "
                        "Debe sonar humana, empatica, breve y orientada a diagnosticar capacidad de pago. "
                        "No amenaces, no presiones indebidamente, no inventes politicas ni descuentos. "
                        "Responde solo JSON valido."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        )
        content = response.choices[0].message.content or "{}"
        data = json.loads(content)
        return apply_ai_suggestion(analysis, data)
    except Exception as exc:
        enriched = dict(analysis)
        enriched["ai_mode"] = "rules_fallback"
        enriched["ai_error"] = str(exc)[:180]
        return enriched


def ia_susurro_configurada() -> bool:
    return SUSURRO_OPENAI_ENABLED and OpenAI is not None and bool(os.getenv("OPENAI_API_KEY"))


def build_recent_transcript(fragments: List[Dict], raw_text: str) -> str:
    rows = []
    for fragment in fragments[-8:]:
        speaker = fragment.get("speaker") or "cliente"
        text = fragment.get("text") or ""
        if text:
            rows.append(f"{speaker}: {text}")
    rows.append(f"cliente: {raw_text}")
    return "\n".join(rows)[-2500:]


def build_ai_prompt(session: Dict, raw_text: str, context: str, recent: str, analysis: Dict) -> str:
    return f"""
Contexto de negocio:
- Empresa: Biznescob, gestion de cobranza telefonica.
- El agente necesita una frase siguiente para decir con su propia voz.
- La frase debe ayudar a entender la situacion actual del cliente y llevar a una alternativa de pago realista.
- Evita prometer descuentos, castigos, amenazas o informacion no confirmada.
- Si corresponde, pide datos de capacidad: si labora, a que se dedica, como cubre gastos, monto posible, fecha y canal.

Sesion:
- Agente: {session.get("agente") or "-"}
- Cartera: {session.get("cartera") or "-"}

Ultimo fragmento del cliente:
{raw_text}

Contexto reciente normalizado:
{context}

Transcripcion reciente:
{recent}

Analisis base:
- Intencion: {analysis.get("intent")}
- Titulo: {analysis.get("title")}
- Prioridad: {analysis.get("priority")}
- Objetivo: {analysis.get("objective")}

Devuelve este JSON:
{{
  "title": "titulo corto",
  "next_phrase": "frase exacta que el agente puede decir ahora",
  "objective": "objetivo operativo de la frase",
  "next_step": "siguiente accion concreta",
  "priority": "ALTA | MEDIA | BAJA"
}}
""".strip()


def apply_ai_suggestion(analysis: Dict, data: Dict) -> Dict:
    enriched = dict(analysis)
    next_phrase = clean_value(data.get("next_phrase"))
    title = clean_value(data.get("title"))
    objective = clean_value(data.get("objective"))
    next_step = clean_value(data.get("next_step"))
    priority = clean_value(data.get("priority"))

    if title:
        enriched["title"] = title[:120]
    if next_phrase:
        enriched["suggestion"] = next_phrase[:1200]
    if objective:
        enriched["objective"] = objective[:400]
    if next_step:
        enriched["next_step"] = next_step[:300]
    if priority and priority.upper() in {"ALTA", "MEDIA", "BAJA"}:
        enriched["priority"] = priority.upper()

    enriched["ai_mode"] = "openai"
    return enriched


def build_checklist(intent: str) -> Dict:
    base = {
        "sondear_motivo": intent in {"OBJECION_ECONOMICA", "SOBREENDEUDAMIENTO", "SITUACION_CRITICA"},
        "validar_capacidad": intent in {"OBJECION_ECONOMICA", "PIDE_DESCUENTO", "SOBREENDEUDAMIENTO"},
        "confirmar_3c": intent in {"PROMESA_PAGO", "PROPONE_FECHA"},
        "pedir_comprobante": intent == "YA_PAGO",
        "bajar_friccion": intent in {"RECHAZO_CONTACTO", "SITUACION_CRITICA"},
    }
    return base


def update_metrics(session: Dict, speaker: str, text: str, analysis: Dict):
    metrics = session.setdefault("metrics", empty_metrics())
    metrics["fragmentos"] += 1
    metrics["cliente"] += 1 if speaker == "cliente" else 0
    metrics["agente"] += 1 if speaker == "agente" else 0
    metrics["alta"] += 1 if analysis.get("priority") == "ALTA" else 0
    metrics["media"] += 1 if analysis.get("priority") == "MEDIA" else 0
    metrics["baja"] += 1 if analysis.get("priority") == "BAJA" else 0

    if speaker == "agente":
        normalized_context = normalize_text(text)
        for key, terms in AGENT_CHECKS.items():
            if any(term in normalized_context for term in terms):
                metrics["checks"][key] = True


def empty_metrics() -> Dict:
    return {
        "fragmentos": 0,
        "cliente": 0,
        "agente": 0,
        "alta": 0,
        "media": 0,
        "baja": 0,
        "checks": {
            "saludo": False,
            "monto": False,
            "fecha": False,
            "canal": False,
            "cierre_3c": False,
        },
    }


def build_alerts(session: Dict) -> List[Dict]:
    alerts = []
    current = session.get("current") or {}
    metrics = session.get("metrics") or empty_metrics()

    if current.get("priority") == "ALTA":
        alerts.append({
            "type": "priority",
            "title": "Atencion alta",
            "message": current.get("title") or "Intencion sensible detectada.",
        })

    checks = metrics.get("checks") or {}
    if metrics.get("agente", 0) >= 2 and not (checks.get("monto") and checks.get("fecha") and checks.get("canal")):
        alerts.append({
            "type": "closing",
            "title": "Faltan 3C",
            "message": "Aun no se evidencia monto, fecha y canal completos.",
        })

    if current.get("intent") == "RIESGO_DISCURSO_AGENTE":
        alerts.append({
            "type": "risk",
            "title": "Riesgo de calidad",
            "message": "Revisar tono o frase sensible del agente.",
        })

    return alerts[:4]


def build_context(fragments: List[Dict], current_text: str, speaker: str) -> str:
    relevant = [
        fragment.get("normalized_text") or ""
        for fragment in fragments[-8:]
        if fragment.get("speaker") == speaker
    ]
    relevant.append(current_text)
    context = " ".join(item for item in relevant if item).strip()
    if len(context) > MAX_CONTEXT_CHARS:
        context = context[-MAX_CONTEXT_CHARS:]
    return context


def is_actionable(analysis: Dict, quality: Dict) -> bool:
    if quality.get("discard"):
        return False
    if analysis.get("intent") == "NO_CLARO" and float(analysis.get("confidence") or 0) < 0.5:
        return False
    return float(analysis.get("confidence") or 0) >= 0.65


def is_clear_client_intent(analysis: Dict) -> bool:
    if analysis.get("intent") == "NO_CLARO":
        return False
    return float(analysis.get("confidence") or 0) >= 0.65


def add_detected_intent(session: Dict, intent: Optional[str]):
    if not intent or intent == "NO_CLARO":
        return
    detected = session.setdefault("detected_intents", [])
    if intent in detected:
        detected.remove(intent)
    detected.insert(0, intent)
    del detected[6:]


def evaluate_quality(text: str) -> Dict:
    words = text.split()
    repeated = has_repeated_words(words)
    low_quality = has_low_quality_signal(text) or repeated
    return {
        "words": len(words),
        "repeated": repeated,
        "discard": low_quality or len(words) < 2,
        "label": "RUIDO" if low_quality else "OK",
    }


def looks_like_agent_pitch(text: str) -> bool:
    if any(term in text for term in AGENT_LIKE_TERMS):
        client_signals = (
            "no puedo",
            "no tengo",
            "ya pague",
            "descuento",
            "me enferme",
            "estuve enfermo",
            "sin trabajo",
            "no reconozco",
        )
        return not any(signal in text for signal in client_signals)
    return False


def has_repeated_words(words: List[str]) -> bool:
    if len(words) < 8:
        return False
    most_common = max(words.count(word) for word in set(words))
    return most_common / max(len(words), 1) >= 0.45


def has_low_quality_signal(text: str) -> bool:
    return any(term in text for term in LOW_QUALITY_TERMS)


def count_matches(text: str, patterns: tuple[str, ...]) -> int:
    return sum(1 for pattern in patterns if pattern in text)


def normalize_speaker(value: Optional[str]) -> str:
    normalized = normalize_text(value or "cliente")
    if normalized in {"agente", "asesor", "agent"}:
        return "agente"
    return "cliente"


def clean_value(value) -> Optional[str]:
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def normalize_text(value: str) -> str:
    text = str(value or "").lower()
    replacements = {
        "á": "a",
        "é": "e",
        "í": "i",
        "ó": "o",
        "ú": "u",
        "ü": "u",
        "ñ": "n",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    filler = {"eh", "ehh", "mmm", "este", "osea", "pues", "aja"}
    return " ".join(word for word in text.split() if word not in filler)
