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
    return prompt_copc_cobranza()


def prompt_copc_cobranza() -> str:
    return """
Analiza esta transcripcion de llamada de cobranza y devuelve exclusivamente un JSON valido.

Marco de evaluacion: COPC adaptado a cobranza telefonica.
El objetivo es evaluar calidad de gestion, cumplimiento del proceso, experiencia del cliente
y efectividad de cobranza. La calidad no debe verse como "hablar bonito"; debe relacionarse
con contacto efectivo, diagnostico, negociacion, cierre verificable y trato adecuado.

Principios COPC aplicados:
- Evaluar solo conductas observables en la llamada.
- Diferenciar errores criticos de oportunidades de mejora.
- Conectar calidad con resultado de negocio: contacto, promesa, cierre 3C y recupero.
- Usar criterios consistentes para calibracion entre supervisores.
- El feedback debe ser accionable, especifico y entrenable.

Matriz COPC Cobranza 100 puntos:

1. Cumplimiento y control de contacto 15 puntos:
  - 1.1 Apertura e identificacion: 4 puntos. Saluda, se identifica y comunica empresa/motivo.
  - 1.2 Validacion de titularidad y datos: 5 puntos. Verifica identidad antes de exponer deuda.
    Cuenta como validacion si el asesor pregunta por titularidad o identidad con frases naturales como
    "hablo con la titular", "usted es la titular", "es la tt/titular" y el cliente confirma afirmativamente.
  - 1.3 Informacion correcta de deuda/gestion: 4 puntos. Explica deuda, producto, PDP o situacion sin confundir.
  - 1.4 Registro y trazabilidad verbal: 2 puntos. Deja claro el motivo o siguiente paso.

2. Diagnostico y escucha 15 puntos:
  - 2.1 Identificacion del motivo de atraso: 5 puntos.
  - 2.2 Situacion economica actual/capacidad de pago: 5 puntos.
  - 2.3 Escucha activa y control de conversacion: 3 puntos.
  - 2.4 Confirmacion de entendimiento: 2 puntos.

3. Negociacion de cobranza 30 puntos:
  - 3.1 Negociacion escalonada: 10 puntos. Inicia por deuda total o importe alto, luego capital,
    y deja descuento/campana como ultima alternativa. No debe partir por el monto mas bajo.
  - 3.2 Manejo de objeciones: 7 puntos. Reconoce la objecion, indaga causa y responde sin confrontar.
  - 3.3 Propuesta de alternativas viables: 5 puntos. Ofrece opciones segun capacidad y politica.
  - 3.4 Argumentacion de beneficios y consecuencias: 4 puntos. Explica beneficios de pagar y consecuencias reales
    sin amenazas ni informacion falsa.
  - 3.5 Orientacion a resultado: 4 puntos. Busca compromiso concreto, no solo informar.

4. Cierre y compromiso 25 puntos:
  - 4.1 Cierre 3C: 10 puntos. Confirma cuanto paga, donde paga y como pagara.
  - 4.2 Fecha/hora o plazo verificable: 5 puntos. El compromiso debe tener fecha clara.
  - 4.3 Confirmacion y recapitulacion: 5 puntos. Repite acuerdo y valida aceptacion del cliente.
  - 4.4 Siguiente accion si no hay pago: 3 puntos. Define seguimiento o alternativa.
  - 4.5 Despedida profesional: 2 puntos.

5. Experiencia, conducta y riesgo critico (Filosofia Biznescob) 15 puntos:
  - 5.1 Tono profesional y empatico: 4 puntos.
  - 5.2 Lenguaje claro, diccion y orden: 3 puntos.
  - 5.3 Manejo emocional de la llamada: 3 puntos. No interrumpe, no ridiculiza, no escala conflicto.
  - 5.4 Cumplimiento etico/no abuso: 5 puntos. No usa insultos, sarcasmo, humillacion, amenazas,
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
- El resumen debe mencionar objetivo, cliente/contexto si existe, resultado y riesgo principal.
- La recomendacion debe servir para coaching del agente.
- Incluye maximo 4 fortalezas, maximo 5 puntos criticos y maximo 4 alertas.

Segmentos permitidos para puntos criticos:
- Cumplimiento
- Diagnostico
- Negociacion
- Cierre
- Experiencia y riesgo

Estructura exacta requerida:
{
  "resumen": "texto breve",
  "tipo_contacto": "Contacto efectivo | Contacto no efectivo | Tercero | Buzon | Cortada | Otro",
  "resultado_gestion": "Compromiso confirmado | Compromiso pendiente | Sin compromiso | Informativo | Otro",
  "objecion_principal": "texto o No evidenciada",
  "evaluacion_calidad": [
    {
      "segmento": "Cumplimiento | Diagnostico | Negociacion | Cierre | Experiencia y riesgo",
      "item": "1.1 Apertura e identificacion",
      "peso": 4,
      "nota": 0,
      "resultado": "Cumple | Parcial | No cumple | No evidenciado",
      "hallazgo": "texto",
      "evidencia": "referencia breve de la llamada",
      "momento": "mm:ss o No disponible",
      "recomendacion": "texto"
    }
  ],
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
                response_format="verbose_json",
                timestamp_granularities=["segment"],
            )
        except Exception:
            audio_file.seek(0)
            result = client.audio.transcriptions.create(
                model=TRANSCRIPTION_MODEL,
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
    prompt_personalizado = config.get("prompt_personalizado") or ""
    ajustes = f"""

Ajustes adicionales por cartera o configuracion interna:
{prompt_personalizado}

Estos ajustes pueden complementar el analisis, pero no reemplazan ni reducen la matriz COPC Cobranza.
""" if prompt_personalizado else ""

    return f"""
{prompt_copc_cobranza()}
{ajustes}

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
    habilidades = data.get("habilidades_blandas")
    if not isinstance(habilidades, list):
        habilidades = []

    evaluacion = normalizar_evaluacion_calidad(data.get("evaluacion_calidad"))
    score_calidad = round(sum(item["nota"] for item in evaluacion), 2)
    falta_anulante = bool(data.get("falta_anulante"))

    nivel = str(data.get("nivel_oportunidad_mejora") or "MEDIA").upper()
    if nivel not in {"BAJA", "MEDIA", "ALTA"}:
        nivel = "MEDIA"

    puntos_normalizados = [
        {
            "segmento": str(item.get("segmento") or "-"),
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
    if falta_anulante:
        score_calidad = 0
        nivel = "ALTA"

    return {
        "resumen": str(data.get("resumen") or "-"),
        "tipo_contacto": str(data.get("tipo_contacto") or "-"),
        "resultado_gestion": str(data.get("resultado_gestion") or "-"),
        "objecion_principal": str(data.get("objecion_principal") or "-"),
        "score_calidad": score_calidad,
        "evaluacion_calidad": evaluacion,
        "habilidades_blandas": normalizar_habilidades_blandas(habilidades, evaluacion),
        "fortalezas_agente": [str(x) for x in fortalezas],
        "puntos_criticos": puntos_normalizados,
        "recomendacion_feedback_supervisor": str(data.get("recomendacion_feedback_supervisor") or "-"),
        "guion_sugerido": str(data.get("guion_sugerido") or "-"),
        "alertas": [str(x) for x in alertas],
        "falta_anulante": falta_anulante,
        "frase_anulante": str(data.get("frase_anulante") or ("No aplica" if not falta_anulante else "No disponible")),
        "momento_falta_anulante": str(data.get("momento_falta_anulante") or ("No aplica" if not falta_anulante else "No disponible")),
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
            "momento": str(item.get("momento") or "No disponible"),
            "recomendacion": str(item.get("recomendacion") or "-"),
        })

    return normalizada


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
