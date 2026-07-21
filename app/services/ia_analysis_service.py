from __future__ import annotations

import json
import os
import re
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

ESTADOS_COPC_V2 = {
    "CUMPLE",
    "PARCIAL_ALTO",
    "PARCIAL_MEDIO",
    "PARCIAL_BAJO",
    "NO_CUMPLE",
    "NO_EVALUABLE",
    "REQUIERE_REVISION",
}


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
    return prompt_copc_cobranza_v2()


def prompt_copc_cobranza_v2() -> str:
    return """
Analiza esta transcripción de llamada de cobranza y devuelve exclusivamente JSON válido.

Marco: COPC adaptado a cobranza telefónica v2. No es una matriz COPC oficial universal.
Evalúa solo conductas observables o razonablemente inferibles. No inventes hechos, citas ni timestamps.

Estados permitidos por criterio:
CUMPLE, PARCIAL_ALTO, PARCIAL_MEDIO, PARCIAL_BAJO, NO_CUMPLE, NO_EVALUABLE, REQUIERE_REVISION.

Reglas centrales:
- La ausencia de evidencia no significa automáticamente NO_CUMPLE. Usa NO_EVALUABLE o REQUIERE_REVISION y explica motivo.
- Si no hay diarización, infiere AGENTE, CLIENTE o NO_DETERMINADO por fragmento con confianza. No fuerces una asignación ambigua.
- La nota mínima aprobatoria es 85.
- Conserva score_tecnico sobre 100 aunque exista descalificación.
- Nunca conviertas automáticamente el score_tecnico a cero por error crítico.
- La descalificación es independiente del score técnico.
- No evalúes "Tipificación correcta"; devuelve dos tipificaciones sugeridas sin impacto en score.
- Si no hay timestamps, usa null. No inventes timestamps.

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
  "interlocutores": {"confianza_global": "", "segmentos": []},
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
Incluye siempre los 24 criterios de la matriz. Si un criterio no puede evaluarse, inclúyelo con estado
NO_EVALUABLE o REQUIERE_REVISION, puntaje_obtenido null, motivo_no_evaluable claro y evidencia vacía.

Para compatibilidad gerencial, cada criterio puede incluir grupo_error_sgc y factor_sgc. Si no lo incluyes,
el sistema lo inferirá por criterio.
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
- SGC/PEC no reemplaza a COPC: traduce los hallazgos a una clasificación interna para Pareto, feedback y coaching.
- Clasifica cada item también en grupo_error_sgc y factor_sgc.
- Grupos permitidos:
  * Errores críticos del negocio
  * Errores críticos del usuario final
  * Errores críticos de cumplimiento
  * Errores no críticos
  * No aplica
- Factores SGC/PEC de negocio: Razón de no pago y explicar motivo, Urgencia y persistencia en el pago,
  Gestión de objeciones del cliente, Uso de aplicativo si aplica, Asesorar, Dominio de la llamada,
  Parafraseo / reafirmar acuerdo de pagos, Tipificación correcta, Falta grave para el negocio,
  Cierre verificable 3C/4C, Negociación escalonada, Propuesta de alternativas, Orientación a resultado.
- Factores SGC/PEC de usuario final: Información de la deuda, Agilidad / escucha activa,
  Falta grave para el usuario final, Claridad de la explicación, Confusión generada al cliente.
- Factores SGC/PEC de cumplimiento: Ley de protección y defensa del consumidor,
  Validación de titularidad, Exposición de deuda a tercero, Información falsa o riesgosa,
  Amenazas, presión indebida o trato abusivo, Conducta ética y no abuso.
- Factores SGC/PEC no críticos: Identificación del cliente, Identificación del gestor,
  Entonación, dicción y empatía, TMO / ACW, Lenguaje formal, Despedida profesional,
  Actualización de números telefónicos si aplica.

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
      "grupo_error_sgc": "Errores críticos del negocio | Errores críticos del usuario final | Errores críticos de cumplimiento | Errores no críticos | No aplica",
      "factor_sgc": "factor SGC/PEC aplicable",
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
    data = cargar_json_analisis(content, client=client)
    data = asegurar_respuesta_copc_v2(client, prompt, data)
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
    base = prompt_base_sistema()
    prompt_personalizado = config.get("prompt_personalizado") or ""
    if limpiar_key_texto(prompt_personalizado) == limpiar_key_texto(base):
        prompt_personalizado = ""
    ajustes = f"""

Ajustes adicionales por cartera o configuracion interna:
{prompt_personalizado}

Estos ajustes pueden complementar el analisis, pero no reemplazan ni reducen la matriz COPC Cobranza.
""" if prompt_personalizado else ""

    return f"""
{base}
{ajustes}

Comentario del supervisor:
{comentario_supervisor or "-"}

Transcripcion:
{transcripcion}
""".strip()


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
                    "y las 5 dimensiones con sus 24 criterios completos. "
                    "No uses el formato antiguo."
                ),
            },
            {"role": "user", "content": prompt},
        ],
    )
    content = response.choices[0].message.content or "{}"
    reparada = cargar_json_analisis(content, client=client)
    if not (es_copc_v2(reparada) and respuesta_copc_v2_tiene_criterios(reparada)):
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


def normalizar_analisis_copc_v2(data: Dict) -> Dict:
    resultado = data.get("resultado_evaluacion") if isinstance(data.get("resultado_evaluacion"), dict) else {}
    gestion = data.get("resultado_gestion") if isinstance(data.get("resultado_gestion"), dict) else {}
    resumen = data.get("resumen_ejecutivo") if isinstance(data.get("resumen_ejecutivo"), dict) else {}
    coaching = data.get("coaching") if isinstance(data.get("coaching"), dict) else {}
    feedback_supervisor = coaching.get("feedback_supervisor") if isinstance(coaching.get("feedback_supervisor"), dict) else {}
    feedback_asesor = coaching.get("feedback_asesor") if isinstance(coaching.get("feedback_asesor"), dict) else {}

    evaluacion = normalizar_dimensiones_copc_v2(data.get("dimensiones"))
    score_bruto, peso_aplicable, score_tecnico = calcular_score_normalizado(evaluacion)
    score_tecnico = round(min(score_tecnico, 100), 2)

    descalificada = bool(resultado.get("descalificada"))
    errores_criticos = normalizar_errores_criticos_v2(data.get("errores_criticos"), evaluacion)
    descalificada = descalificada or any(item.get("automatico") for item in errores_criticos)
    estado_tecnico = "APROBADA" if score_tecnico >= 85 else "NO_APROBADA"
    if any(item.get("requiere_revision") for item in evaluacion):
        estado_tecnico = "PROVISIONAL" if estado_tecnico == "APROBADA" else estado_tecnico

    estado_calidad = str(resultado.get("estado_calidad") or "").strip().upper()
    if estado_calidad not in {"APROBADA", "APROBADA_CON_MEJORAS", "NO_APROBADA", "DESCALIFICADA", "PENDIENTE_REVISION"}:
        if descalificada:
            estado_calidad = "DESCALIFICADA"
        elif resultado.get("requiere_revision_humana") or any(item.get("requiere_revision") for item in evaluacion):
            estado_calidad = "PENDIENTE_REVISION"
        elif score_tecnico >= 85:
            estado_calidad = "APROBADA"
        elif score_tecnico >= 70:
            estado_calidad = "APROBADA_CON_MEJORAS"
        else:
            estado_calidad = "NO_APROBADA"

    nivel_riesgo = "ALTO" if estado_calidad in {"DESCALIFICADA", "PENDIENTE_REVISION"} or score_tecnico < 70 else "MEDIO" if score_tecnico < 85 else "BAJO"
    motivos_revision = resultado.get("motivos_revision") if isinstance(resultado.get("motivos_revision"), list) else []
    requiere_revision = bool(resultado.get("requiere_revision_humana") or motivos_revision or any(item.get("requiere_revision") for item in evaluacion))

    puntos_criticos = errores_criticos + normalizar_hallazgos_no_criticos_v2(data.get("hallazgos_no_criticos"), evaluacion)
    puntos_criticos = deduplicar_puntos_criticos(puntos_criticos)
    error_critico = bool(errores_criticos) or any(
        str(item.get("severidad") or "").upper() in {"ANULANTE", "GRAVE"}
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
        "version_evaluacion": "2.0",
        "json_copc_v2": data,
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
        "peso_aplicable": peso_aplicable,
        "score_normalizado": score_tecnico,
        "estado_calidad": estado_calidad,
        "estado_tecnico": estado_tecnico,
        "nivel_riesgo": nivel_riesgo,
        "error_critico": error_critico,
        "calidad_transcripcion": normalizar_confianza(resultado.get("confianza_global")),
        "confianza_evaluacion": normalizar_confianza(resultado.get("confianza_global")),
        "requiere_revision_humana": requiere_revision,
        "motivo_revision": "; ".join(str(x) for x in motivos_revision) or (resultado.get("motivo_descalificacion") if requiere_revision else ""),
        "evaluacion_calidad": evaluacion,
        "resumen_sgc": {},
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
        "frase_anulante": str(resultado.get("motivo_descalificacion") or ("No aplica" if not descalificada else "No disponible")),
        "momento_falta_anulante": None,
        "nivel_oportunidad_mejora": "ALTA" if nivel_riesgo == "ALTO" else "MEDIA" if nivel_riesgo == "MEDIO" else "BAJA",
    }


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
    return completar_matriz_copc(criterios)


def convertir_criterio_v2(criterio: Dict, segmento: str) -> Dict:
    codigo = str(criterio.get("codigo") or "").strip()
    nombre = str(criterio.get("nombre") or criterio.get("criterio") or "").strip()
    nombre_item = f"{codigo} {nombre}".strip()
    canon = buscar_item_canonico(codigo, nombre_item)
    segmento_canon, item_canon, peso_canon = canon
    peso = numero_en_rango(criterio.get("puntaje_maximo"), 0, peso_canon or 100) if criterio.get("puntaje_maximo") is not None else peso_canon
    peso = peso or peso_canon
    estado = normalizar_estado_criterio_v2(criterio.get("estado"))
    aplica = estado not in {"NO_EVALUABLE", "REQUIERE_REVISION"}
    if estado in {"NO_EVALUABLE", "REQUIERE_REVISION"}:
        aplica = False
    nota = numero_en_rango(criterio.get("puntaje_obtenido"), 0, peso)
    if estado in {"NO_EVALUABLE", "REQUIERE_REVISION"} and criterio.get("puntaje_obtenido") in (None, ""):
        nota = 0
    resultado = resultado_legacy_desde_estado_v2(estado)
    sgc = clasificar_item_sgc({
        "item": item_canon,
        "segmento": segmento_canon,
        "hallazgo": criterio.get("hallazgo"),
        "evidencia": " | ".join(evidencia_texto_v2(criterio.get("evidencias"))),
        "recomendacion": criterio.get("recomendacion"),
    })
    grupo_sgc = normalizar_grupo_sgc(criterio.get("grupo_error_sgc") or sgc.get("grupo_error_sgc"), criterio)
    factor_sgc = str(criterio.get("factor_sgc") or sgc.get("factor_sgc") or nombre or item_canon)
    return {
        "segmento": segmento_canon or formatear_segmento_v2(segmento),
        "item": item_canon or nombre_item or "Criterio sin nombre",
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
        "factor_sgc": factor_sgc,
        "calificacion": resultado,
        "motivo": str(criterio.get("motivo_no_evaluable") or criterio.get("hallazgo") or "-"),
        "hallazgo": str(criterio.get("hallazgo") or "-"),
        "evidencia": " | ".join(evidencia_texto_v2(criterio.get("evidencias"))) or "-",
        "momento": primer_timestamp_v2(criterio.get("evidencias")),
        "recomendacion": str(criterio.get("recomendacion") or "-"),
        "impacto": str(criterio.get("impacto") or "-"),
        "gravedad": str(criterio.get("gravedad") or ""),
        "puede_descalificar": bool(criterio.get("puede_descalificar")),
        "confianza": normalizar_confianza(criterio.get("confianza")),
        "requiere_revision": bool(criterio.get("requiere_revision") or estado == "REQUIERE_REVISION"),
        "requiere_feedback": resultado not in {"Cumple", "No aplica"},
        "requiere_coaching": bool(criterio.get("puede_descalificar") or grupo_sgc == SGC_GRUPO_CUMPLIMIENTO or estado == "NO_CUMPLE"),
        "motivo_feedback_coaching": str(criterio.get("hallazgo") or criterio.get("motivo_no_evaluable") or ""),
    }


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
    return estado if estado in ESTADOS_COPC_V2 else "REQUIERE_REVISION"


def resultado_legacy_desde_estado_v2(estado: str) -> str:
    if estado == "CUMPLE":
        return "Cumple"
    if estado in {"PARCIAL_ALTO", "PARCIAL_MEDIO", "PARCIAL_BAJO"}:
        return "Parcial"
    if estado == "NO_CUMPLE":
        return "No cumple"
    if estado == "NO_EVALUABLE":
        return "No aplica"
    return "Requiere revisión"


def evidencia_texto_v2(evidencias) -> List[str]:
    salida = []
    if isinstance(evidencias, list):
        for evidencia in evidencias[:3]:
            if isinstance(evidencia, dict):
                texto = evidencia.get("texto") or evidencia.get("frase") or evidencia.get("evidencia") or evidencia.get("fragmento")
                if texto:
                    salida.append(str(texto))
            elif evidencia:
                salida.append(str(evidencia))
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
            rows.append({
                "segmento": formatear_segmento_v2(item.get("segmento_copc") or item.get("segmento") or "Experiencia y ética"),
                "segmento_copc": formatear_segmento_v2(item.get("segmento_copc") or item.get("segmento") or "Experiencia y ética"),
                "grupo_error_sgc": normalizar_grupo_sgc(item.get("grupo_error_sgc") or SGC_GRUPO_CUMPLIMIENTO, item),
                "factor_sgc": str(item.get("factor_sgc") or item.get("criterio") or item.get("tipo") or "Conducta ética y no abuso"),
                "categoria": str(item.get("criterio") or item.get("tipo") or "Error crítico"),
                "severidad": "ANULANTE" if automatico else "GRAVE",
                "automatico": automatico,
                "requiere_revision": bool(item.get("requiere_revision") or not automatico),
                "hallazgo": str(item.get("hallazgo") or item.get("descripcion") or "-"),
                "frase_textual": str(item.get("frase_textual") or item.get("frase") or "No disponible"),
                "momento": item.get("timestamp") or item.get("momento"),
                "evidencia": str(item.get("evidencia") or item.get("frase_textual") or "-"),
                "impacto": str(item.get("impacto") or "Riesgo crítico para calidad y cumplimiento."),
                "recomendacion": str(item.get("recomendacion") or "Revisión inmediata por supervisor."),
            })
    if rows:
        return rows
    for item in evaluacion:
        if item.get("puede_descalificar") or item.get("gravedad") in {"ANULANTE", "GRAVE"}:
            rows.append({
                "segmento": item.get("segmento"),
                "segmento_copc": item.get("segmento_copc"),
                "grupo_error_sgc": item.get("grupo_error_sgc"),
                "factor_sgc": item.get("factor_sgc"),
                "categoria": item.get("factor_sgc"),
                "severidad": "ANULANTE" if item.get("puede_descalificar") else "GRAVE",
                "automatico": bool(item.get("puede_descalificar")),
                "requiere_revision": bool(item.get("requiere_revision")),
                "hallazgo": item.get("hallazgo"),
                "frase_textual": item.get("evidencia"),
                "momento": item.get("momento"),
                "evidencia": item.get("evidencia"),
                "impacto": item.get("impacto"),
                "recomendacion": item.get("recomendacion"),
            })
    return rows


def normalizar_hallazgos_no_criticos_v2(value, evaluacion: List[Dict]) -> List[Dict]:
    rows = []
    if isinstance(value, list):
        for item in value:
            if not isinstance(item, dict):
                continue
            rows.append({
                "segmento": formatear_segmento_v2(item.get("segmento_copc") or item.get("segmento") or ""),
                "segmento_copc": formatear_segmento_v2(item.get("segmento_copc") or item.get("segmento") or ""),
                "grupo_error_sgc": normalizar_grupo_sgc(item.get("grupo_error_sgc") or SGC_GRUPO_NO_CRITICO, item),
                "factor_sgc": str(item.get("factor_sgc") or item.get("criterio") or "Hallazgo no crítico"),
                "categoria": str(item.get("criterio") or "Hallazgo no crítico"),
                "severidad": normalizar_severidad(item.get("severidad") or "MEDIA"),
                "hallazgo": str(item.get("hallazgo") or item.get("descripcion") or "-"),
                "frase_textual": str(item.get("frase_textual") or "No disponible"),
                "momento": item.get("timestamp") or item.get("momento"),
                "evidencia": str(item.get("evidencia") or "-"),
                "impacto": str(item.get("impacto") or "-"),
                "recomendacion": str(item.get("recomendacion") or "-"),
            })
    if rows:
        return rows
    return [
        {
            "segmento": item.get("segmento"),
            "segmento_copc": item.get("segmento_copc"),
            "grupo_error_sgc": item.get("grupo_error_sgc"),
            "factor_sgc": item.get("factor_sgc"),
            "categoria": item.get("factor_sgc"),
            "severidad": "MEDIA",
            "hallazgo": item.get("hallazgo"),
            "frase_textual": item.get("evidencia"),
            "momento": item.get("momento"),
            "evidencia": item.get("evidencia"),
            "impacto": item.get("impacto"),
            "recomendacion": item.get("recomendacion"),
        }
        for item in evaluacion
        if item.get("aplica", True) is not False
        and item.get("resultado") not in {"Cumple", "No aplica", "Requiere revisión", "Requiere revision"}
        and not item.get("puede_descalificar")
    ][:8]


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
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", str(value or "").lower())).strip()


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


def clasificar_item_sgc(item: Dict) -> Dict:
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
    segmento = texto_normalizado_sgc(item.get("segmento"))
    if "cumpl" in segmento:
        return {"grupo_error_sgc": SGC_GRUPO_CUMPLIMIENTO, "factor_sgc": "Validación de titularidad"}
    if "negoci" in segmento or "cierre" in segmento:
        return {"grupo_error_sgc": SGC_GRUPO_NEGOCIO, "factor_sgc": "Orientación a resultado"}
    if "diagn" in segmento:
        return {"grupo_error_sgc": SGC_GRUPO_NEGOCIO, "factor_sgc": "Razón de no pago y explicar motivo"}
    if "experiencia" in segmento or "riesgo" in segmento:
        return {"grupo_error_sgc": SGC_GRUPO_CUMPLIMIENTO, "factor_sgc": "Conducta ética y no abuso"}
    return {"grupo_error_sgc": SGC_GRUPO_NO_CRITICO, "factor_sgc": str(item.get("item") or "Error no crítico")}


def normalizar_grupo_sgc(value, item: Optional[Dict] = None) -> str:
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
    lower = texto.lower()
    if "requiere revis" in lower or "revision" in lower or "revisión" in lower or "no evaluable" in lower:
        return "Requiere revisión"
    if "no aplica" in lower or lower in {"n/a", "na"}:
        return "No aplica"
    if "parcial" in lower:
        return "Parcial"
    if "no cumple" in lower or "no evidenciado" in lower:
        return "No cumple"
    if "cumple" in lower:
        return "Cumple"
    return "No cumple" if float(item.get("nota") or 0) == 0 else "Parcial"


def debe_contar_error_sgc(item: Dict) -> bool:
    grupo = item.get("grupo_error_sgc")
    calificacion = str(item.get("calificacion") or "").lower()
    if item.get("aplica") is False:
        return False
    return grupo != SGC_GRUPO_NO_APLICA and calificacion not in {"cumple", "no aplica", "requiere revisión", "requiere revision"}


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
        grupo = normalizar_grupo_sgc(item.get("grupo_error_sgc"), item)
        factor = str(item.get("factor_sgc") or clasificacion.get("factor_sgc") or item.get("item") or "-")
        calificacion = normalizar_calificacion_sgc(item)
        nota = float(item.get("nota") or 0)
        peso = float(item.get("peso") or 0)
        no_cumple = bool(item.get("aplica", True)) and (calificacion in {"No cumple", "Parcial"} or (peso > 0 and nota < peso))
        cumplimiento_critico = grupo == SGC_GRUPO_CUMPLIMIENTO and no_cumple
        requiere_feedback = item.get("requiere_feedback")
        requiere_coaching = item.get("requiere_coaching")
        if requiere_feedback is None:
            requiere_feedback = bool(no_cumple)
        if requiere_coaching is None:
            requiere_coaching = bool(no_cumple and (cumplimiento_critico or falta_anulante or score_bajo_coaching or riesgo_alto))
        item["segmento_copc"] = str(item.get("segmento_copc") or item.get("segmento") or "-")
        item["grupo_error_sgc"] = grupo
        item["factor_sgc"] = factor
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
    for item in evaluacion:
        if not debe_contar_error_sgc(item):
            continue
        grupo = item.get("grupo_error_sgc")
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


def normalizar_analisis(data: Dict) -> Dict:
    es_version_v2 = es_copc_v2(data)
    if es_version_v2:
        data = normalizar_analisis_copc_v2(data)

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

    return {
        "version_evaluacion": data.get("version_evaluacion"),
        "json_copc_v2": data.get("json_copc_v2"),
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
            "motivo": "La IA no devolvio evidencia para este item en la matriz original.",
            "hallazgo": "No evidenciado en la respuesta IA.",
            "evidencia": "No disponible.",
            "momento": "No disponible",
            "recomendacion": "Revisar la transcripcion o solicitar recalibracion si el item si fue cubierto.",
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
        nota_ia = numero_en_rango(item.get("nota_ia", item.get("nota")), 0, peso)
        nota_supervisor = item.get("nota_supervisor")
        nota_supervisor = numero_en_rango(nota_supervisor, 0, peso) if nota_supervisor not in (None, "") else None
        nota_final = item.get("nota_final")
        nota_final = numero_en_rango(nota_final, 0, peso) if nota_final not in (None, "") else nota_ia
        nota = 0 if not aplica else nota_final
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
            "motivo": str(item.get("motivo") or item.get("hallazgo") or "-"),
            "hallazgo": str(item.get("hallazgo") or "-"),
            "evidencia": str(item.get("evidencia") or "-"),
            "momento": str(item.get("momento") or "No disponible"),
            "recomendacion": str(item.get("recomendacion") or "-"),
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
        if item.get("aplica") is False:
            continue
        score_bruto += float(item.get("nota") or 0)
        peso_aplicable += float(item.get("peso") or 0)
    score_bruto = round(score_bruto, 2)
    peso_aplicable = round(peso_aplicable, 2)
    score_normalizado = round((score_bruto / peso_aplicable) * 100, 2) if peso_aplicable else 0.0
    return score_bruto, peso_aplicable, score_normalizado


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
