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

SGC_GRUPO_NEGOCIO = "Errores crÃ­ticos del negocio"
SGC_GRUPO_USUARIO = "Errores crÃ­ticos del usuario final"
SGC_GRUPO_CUMPLIMIENTO = "Errores crÃ­ticos de cumplimiento"
SGC_GRUPO_NO_CRITICO = "Errores no crÃ­ticos"
SGC_GRUPO_NO_APLICA = "No aplica"
SGC_GRUPOS_VALIDOS = {
    SGC_GRUPO_NEGOCIO,
    SGC_GRUPO_USUARIO,
    SGC_GRUPO_CUMPLIMIENTO,
    SGC_GRUPO_NO_CRITICO,
    SGC_GRUPO_NO_APLICA,
}

SGC_FACTORES = [
    (SGC_GRUPO_NEGOCIO, "RazÃ³n de no pago y explicar motivo", ("2.1", "motivo de atraso", "causa raiz", "causa raÃ­z", "razon de no pago", "razÃ³n de no pago")),
    (SGC_GRUPO_NEGOCIO, "Urgencia y persistencia en el pago", ("3.5", "orientacion a resultado", "orientaciÃ³n a resultado", "urgencia", "persistencia")),
    (SGC_GRUPO_NEGOCIO, "GestiÃ³n de objeciones del cliente", ("3.2", "objeciones")),
    (SGC_GRUPO_NEGOCIO, "Uso de aplicativo si aplica", ("aplicativo", "uso de aplicativo")),
    (SGC_GRUPO_NEGOCIO, "Asesorar", ("asesorar", "asesoria", "asesorÃ­a")),
    (SGC_GRUPO_NEGOCIO, "Dominio de la llamada", ("dominio", "control de conversacion", "control de conversaciÃ³n")),
    (SGC_GRUPO_NEGOCIO, "Parafraseo / reafirmar acuerdo de pagos", ("4.3", "recapitulacion", "recapitulaciÃ³n", "parafraseo", "reafirmar")),
    (SGC_GRUPO_NEGOCIO, "TipificaciÃ³n correcta", ("tipificacion", "tipificaciÃ³n", "registro", "trazabilidad")),
    (SGC_GRUPO_NEGOCIO, "Falta grave para el negocio", ("falta grave para el negocio",)),
    (SGC_GRUPO_NEGOCIO, "Cierre verificable 3C/4C", ("4.1", "cierre 3c", "cierre verificable", "cuanto paga", "cuÃ¡nto paga")),
    (SGC_GRUPO_NEGOCIO, "NegociaciÃ³n escalonada", ("3.1", "negociacion escalonada", "negociaciÃ³n escalonada")),
    (SGC_GRUPO_NEGOCIO, "Propuesta de alternativas", ("3.3", "alternativas")),
    (SGC_GRUPO_NEGOCIO, "OrientaciÃ³n a resultado", ("3.5", "compromiso concreto", "resultado")),
    (SGC_GRUPO_USUARIO, "InformaciÃ³n de la deuda", ("1.3", "informacion correcta", "informaciÃ³n correcta", "deuda")),
    (SGC_GRUPO_USUARIO, "Agilidad / escucha activa", ("2.3", "escucha activa", "agilidad", "interrup")),
    (SGC_GRUPO_USUARIO, "Falta grave para el usuario final", ("falta grave para el usuario",)),
    (SGC_GRUPO_USUARIO, "Claridad de la explicaciÃ³n", ("5.2", "claridad", "explicacion", "explicaciÃ³n")),
    (SGC_GRUPO_USUARIO, "ConfusiÃ³n generada al cliente", ("confusion", "confusiÃ³n")),
    (SGC_GRUPO_CUMPLIMIENTO, "Ley de protecciÃ³n y defensa del consumidor", ("proteccion", "protecciÃ³n", "defensa del consumidor")),
    (SGC_GRUPO_CUMPLIMIENTO, "ValidaciÃ³n de titularidad", ("1.2", "validacion de titularidad", "validaciÃ³n de titularidad", "titularidad")),
    (SGC_GRUPO_CUMPLIMIENTO, "ExposiciÃ³n de deuda a tercero", ("tercero", "exponer deuda", "exposicion de deuda", "exposiciÃ³n de deuda")),
    (SGC_GRUPO_CUMPLIMIENTO, "InformaciÃ³n falsa o riesgosa", ("informacion falsa", "informaciÃ³n falsa", "riesgosa", "legal")),
    (SGC_GRUPO_CUMPLIMIENTO, "Amenazas, presiÃ³n indebida o trato abusivo", ("amenaza", "presion indebida", "presiÃ³n indebida", "trato abusivo", "insulto", "humilla", "carcel", "cÃ¡rcel")),
    (SGC_GRUPO_CUMPLIMIENTO, "Conducta Ã©tica y no abuso", ("5.4", "conducta etica", "conducta Ã©tica", "cumplimiento etico", "cumplimiento Ã©tico", "no abuso")),
    (SGC_GRUPO_NO_CRITICO, "IdentificaciÃ³n del cliente", ("identificacion del cliente", "identificaciÃ³n del cliente")),
    (SGC_GRUPO_NO_CRITICO, "IdentificaciÃ³n del gestor", ("1.1", "apertura", "identificacion", "identificaciÃ³n", "gestor")),
    (SGC_GRUPO_NO_CRITICO, "EntonaciÃ³n, dicciÃ³n y empatÃ­a", ("5.1", "5.2", "empatia", "empatÃ­a", "diccion", "dicciÃ³n", "entonacion", "entonaciÃ³n")),
    (SGC_GRUPO_NO_CRITICO, "TMO / ACW", ("tmo", "acw")),
    (SGC_GRUPO_NO_CRITICO, "Lenguaje formal", ("lenguaje formal",)),
    (SGC_GRUPO_NO_CRITICO, "Despedida profesional", ("4.5", "despedida")),
    (SGC_GRUPO_NO_CRITICO, "ActualizaciÃ³n de nÃºmeros telefÃ³nicos si aplica", ("telefono", "telÃ©fono", "numeros telefonicos", "nÃºmeros telefÃ³nicos")),
]

COPC_ITEMS_CANONICOS = [
    ("Cumplimiento", "1.1 Saludo e identificaciÃ³n del agente", 3),
    ("Cumplimiento", "1.2 IdentificaciÃ³n de la entidad", 3),
    ("Cumplimiento", "1.3 ValidaciÃ³n de titularidad", 4),
    ("Cumplimiento", "1.4 Motivo de llamada y control de informaciÃ³n", 5),
    ("DiagnÃ³stico", "2.1 IdentificaciÃ³n de la causa", 5),
    ("DiagnÃ³stico", "2.2 Capacidad actual de pago", 4),
    ("DiagnÃ³stico", "2.3 Fecha probable de ingreso", 2),
    ("DiagnÃ³stico", "2.4 Monto disponible", 2),
    ("DiagnÃ³stico", "2.5 Fuente del dinero o situaciÃ³n econÃ³mica", 2),
    ("GestiÃ³n de soluciÃ³n", "3.1 PresentaciÃ³n clara de la propuesta", 6),
    ("GestiÃ³n de soluciÃ³n", "3.2 Claridad del beneficio", 4),
    ("GestiÃ³n de soluciÃ³n", "3.3 ExploraciÃ³n de capacidad durante la negociaciÃ³n", 5),
    ("GestiÃ³n de soluciÃ³n", "3.4 NegociaciÃ³n escalonada", 8),
    ("GestiÃ³n de soluciÃ³n", "3.5 Manejo de objeciones", 7),
    ("GestiÃ³n de soluciÃ³n", "3.6 InducciÃ³n a pago o abono", 5),
    ("Cierre verificable", "4.1 Cantidad", 7),
    ("Cierre verificable", "4.2 Fecha exacta", 7),
    ("Cierre verificable", "4.3 Canal de pago", 5),
    ("Cierre verificable", "4.4 ConfirmaciÃ³n expresa", 7),
    ("Cierre verificable", "4.5 Resumen y siguiente acciÃ³n", 4),
    ("Experiencia y Ã©tica", "5.1 Respeto y ausencia de juicio", 2),
    ("Experiencia y Ã©tica", "5.2 EmpatÃ­a y escucha activa", 1),
    ("Experiencia y Ã©tica", "5.3 Lenguaje claro y presiÃ³n profesional", 1),
    ("Experiencia y Ã©tica", "5.4 Despedida y cierre profesional", 1),
]


SGC_MAPEO_CRITERIOS = {
    "1.1": (SGC_GRUPO_NO_CRITICO, "IdentificaciÃ³n del gestor"),
    "1.2": (SGC_GRUPO_NO_CRITICO, "IdentificaciÃ³n de la entidad"),
    "1.3": (SGC_GRUPO_CUMPLIMIENTO, "ValidaciÃ³n de titularidad"),
    "1.4": (SGC_GRUPO_USUARIO, "InformaciÃ³n de la deuda"),

    "2.1": (SGC_GRUPO_NEGOCIO, "RazÃ³n de no pago y explicar motivo"),
    "2.2": (SGC_GRUPO_NEGOCIO, "Capacidad actual de pago"),
    "2.3": (SGC_GRUPO_NEGOCIO, "Fecha probable de ingreso"),
    "2.4": (SGC_GRUPO_NEGOCIO, "Monto disponible"),
    "2.5": (SGC_GRUPO_NEGOCIO, "SituaciÃ³n econÃ³mica"),

    "3.1": (SGC_GRUPO_NO_CRITICO, "PresentaciÃ³n y adaptaciÃ³n de la propuesta"),
    "3.2": (SGC_GRUPO_NO_CRITICO, "Claridad de montos y condiciones"),
    "3.3": (SGC_GRUPO_NEGOCIO, "ExploraciÃ³n de capacidad"),
    "3.4": (SGC_GRUPO_NEGOCIO, "NegociaciÃ³n escalonada"),
    "3.5": (SGC_GRUPO_NEGOCIO, "Manejo de objeciones"),
    "3.6": (SGC_GRUPO_NEGOCIO, "InducciÃ³n a pago o abono"),

    "4.1": (SGC_GRUPO_NEGOCIO, "Cierre verificable 3C/4C"),
    "4.2": (SGC_GRUPO_NEGOCIO, "Cierre verificable 3C/4C"),
    "4.3": (SGC_GRUPO_NEGOCIO, "Cierre verificable 3C/4C"),
    "4.4": (SGC_GRUPO_NEGOCIO, "Cierre verificable 3C/4C"),
    "4.5": (SGC_GRUPO_NEGOCIO, "Cierre verificable 3C/4C"),

    "5.1": (SGC_GRUPO_NO_CRITICO, "Respeto y ausencia de juicio"),
    "5.2": (SGC_GRUPO_NO_CRITICO, "EmpatÃ­a aplicada a la negociaciÃ³n"),
    "5.3": (SGC_GRUPO_CUMPLIMIENTO, "Lenguaje claro y presiÃ³n profesional"),
    "5.4": (SGC_GRUPO_CUMPLIMIENTO, "Conducta Ã©tica y no abuso"),
}

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
Analiza esta transcripciÃ³n de llamada de cobranza y devuelve exclusivamente JSON vÃ¡lido.

Marco: COPC adaptado a cobranza telefÃ³nica v2. No es una matriz COPC oficial universal.
EvalÃºa solo conductas observables o razonablemente inferibles. No inventes hechos, citas ni timestamps.
AISLAMIENTO OBLIGATORIO ENTRE EVALUACIONES:
- Analiza exclusivamente la transcripciÃ³n incluida en este prompt.
- Ignora cualquier llamada, ejemplo, evidencia, fecha, monto, frase, hallazgo o conclusiÃ³n de evaluaciones anteriores.
- Toda evidencia textual debe existir literalmente o de forma claramente equivalente en esta transcripciÃ³n.
- Si un dato no aparece en esta llamada, devuelve null, lista vacÃ­a, NO_EVALUABLE o REQUIERE_REVISION segÃºn corresponda.
- EstÃ¡ prohibido completar informaciÃ³n faltante usando patrones de llamadas anteriores.
- Antes de devolver un hallazgo, valida que la evidencia pertenece a esta transcripciÃ³n y no a otro caso.

REGLA FUNDAMENTAL DE EVALUACION:
- No marques automÃ¡ticamente NO_CUMPLE porque una frase exacta no aparezca.
- CUMPLE: la conducta requerida se observa suficientemente.
- PARCIAL: la conducta se realiza, pero queda incompleta.
- NO_CUMPLE: existÃ­a una oportunidad clara de ejecutar la conducta y el agente no lo hizo o lo hizo incorrectamente.
- NO_EVALUABLE: el desarrollo de la llamada no generÃ³ una oportunidad razonable para ejecutar el criterio.
- REQUIERE_REVISION: existe evidencia ambigua o insuficiente para decidir responsablemente.
- No uses NO_CUMPLE como sustituto de "no encontrÃ© evidencia".
- No confundas contexto del cliente con error del agente: evalÃºa lo que hace el agente despuÃ©s de la objeciÃ³n.
- EvalÃºa independientemente los cinco componentes del cierre verificable; no agrupes automÃ¡ticamente cantidad, fecha, canal, confirmaciÃ³n y resumen como cero.
- No generes hallazgos artificiales para llenar grupos SGC vacÃ­os.

Estados permitidos por criterio:
CUMPLE, PARCIAL_ALTO, PARCIAL_MEDIO, PARCIAL_BAJO, NO_CUMPLE, NO_EVALUABLE, REQUIERE_REVISION.

Reglas centrales:
- La ausencia de evidencia no significa automÃ¡ticamente NO_CUMPLE. Usa NO_EVALUABLE o REQUIERE_REVISION y explica motivo.
- Si no hay diarizaciÃ³n, infiere AGENTE, CLIENTE o NO_DETERMINADO por fragmento con confianza. No fuerces una asignaciÃ³n ambigua.
- Devuelve interlocutores.segmentos siempre que la transcripciÃ³n permita separar turnos de habla. Cada segmento debe traer:
  hablante AGENTE, CLIENTE o NO_DETERMINADO; texto literal; timestamp null si no existe; confianza ALTA, MEDIA o BAJA;
  fundamento breve de por quÃ© asignaste ese hablante. Si la separaciÃ³n es demasiado ambigua, usa NO_DETERMINADO.
- No dejes interlocutores.segmentos vacÃ­o cuando hay turnos evidentes por preguntas/respuestas, saludos del gestor,
  frases de cobranza del agente o respuestas del cliente. Divide en fragmentos cortos y conserva toda la llamada.
- La nota mÃ­nima aprobatoria es 85.
- Conserva score_tecnico sobre 100 aunque exista descalificaciÃ³n.
- Nunca conviertas automÃ¡ticamente el score_tecnico a cero por error crÃ­tico.
- La descalificaciÃ³n es independiente del score tÃ©cnico.
- No evalÃºes "TipificaciÃ³n correcta"; devuelve dos tipificaciones sugeridas sin impacto en score.
- Si no hay timestamps, usa null. No inventes timestamps.
- La evidencia de una falta anulante debe ser una cita textual exacta de la transcripciÃ³n, no una categorÃ­a.
- Si detectas humillaciÃ³n o maltrato psicolÃ³gico explÃ­cito, crea un error crÃ­tico automÃ¡tico en el grupo
  "Errores crÃ­ticos del usuario final" con factor "Falta grave al usuario final / Maltrato psicolÃ³gico".

- La validaciÃ³n de titularidad CUMPLE si el agente pregunta por la persona y el interlocutor confirma directa
  o indirectamente ser ella. No exijas DNI ni validaciÃ³n adicional.
- GestiÃ³n de soluciÃ³n y Cierre verificable aplican cuando hubo contacto y oportunidad real de negociar, aunque no
  haya acuerdo. No los marques NO_EVALUABLE por falta de compromiso; puntÃºa bajo, cero o REQUIERE_REVISION.
- Si no tienes cita textual exacta para sustentar un incumplimiento, usa REQUIERE_REVISION, no inventes evidencia.
- Separa presiÃ³n legal ambigua como error crÃ­tico de cumplimiento sujeto a calibraciÃ³n: REQUIERE_REVISION,
  no falta anulante automÃ¡tica.

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
1.1 Saludo e identificaciÃ³n del agente, 3. Saluda e indica su nombre. Cumple 3, parcial 1.5, no cumple 0.
1.2 IdentificaciÃ³n de la entidad, 3. Menciona banco o entidad. Cumple 3, parcial 1.5, no cumple 0.
1.3 ValidaciÃ³n de titularidad, 4. Basta que pregunte por la persona y el interlocutor confirme directa o indirectamente:
"sÃ­", "soy yo", "ella habla", "con ella", "dÃ­game", "sÃ­ seÃ±or" o respuesta contextual inequÃ­voca.
No exige DNI, fecha de nacimiento ni validaciÃ³n adicional. Cumple 4, parcial/ambiguo 2, no cumple 0, requiere revisiÃ³n si no se puede inferir.
No validar no descalifica automÃ¡ticamente; descalifica solo si se revela deuda a tercero confirmado.
1.4 Motivo de llamada y control de informaciÃ³n, 5. Explica motivo y evita informaciÃ³n falsa, contradictoria o revelada antes de validar.
Cumple 5, parcial alto 3.75, parcial medio 2.5, parcial bajo 1.25, no cumple 0.

D2. DiagnÃ³stico, 15 puntos:
2.1 IdentificaciÃ³n de la causa, 5. Identifica por quÃ© dejÃ³ de pagar. Si cliente lo explica espontÃ¡neamente, puntÃºa si agente escucha y usa la informaciÃ³n.
2.2 Capacidad actual de pago, 4. Determina si puede pagar o abonar ahora o en fecha cercana.
2.3 Fecha probable de ingreso, 2. Determina cuÃ¡ndo podrÃ­a disponer de dinero. "El otro mes", "despuÃ©s" o "cuando pueda" no son suficientes.
2.4 Monto disponible, 2. Busca cuÃ¡nto podrÃ­a pagar o abonar. No hay monto mÃ­nimo obligatorio.
2.5 Fuente del dinero o situaciÃ³n econÃ³mica, 2. Identifica fuente posible o ausencia de ingresos sin interrogatorio invasivo.

D3. GestiÃ³n de soluciÃ³n y negociaciÃ³n, 35 puntos:
3.1 PresentaciÃ³n clara de la propuesta, 6. Diferencia deuda total, campaÃ±a, cuota, abono, fraccionamiento, fecha lÃ­mite cuando corresponda.
3.2 Claridad del beneficio, 4. Explica por quÃ© conviene pagar/abonar: reducir deuda, evitar incremento, campaÃ±a, regularizaciÃ³n o avance real a otra instancia.
3.3 ExploraciÃ³n de capacidad durante la negociaciÃ³n, 5. Usa diagnÃ³stico para adaptar propuesta. No dupliques automÃ¡ticamente el diagnÃ³stico.
3.4 NegociaciÃ³n escalonada, 8. Escalera: cancelaciÃ³n total, campaÃ±a, abono/fraccionamiento, fecha prÃ³xima con monto concreto. No exige todas si cliente acepta una inicial.
3.5 Manejo de objeciones, 7. Escucha, responde profesionalmente y reconduce a soluciÃ³n.
3.6 InducciÃ³n a pago o abono, 5. Intenta obtener pago, abono, monto concreto o fecha concreta.
Regla mes vigente: si cliente dice prÃ³ximo mes, el agente debe intentar primero orientar pago/abono dentro del mes vigente y explicar que condiciones pueden cambiar.

D4. Cierre verificable, 30 puntos. Cierre 4C: Cantidad, CuÃ¡ndo, Canal, ConfirmaciÃ³n.
4.1 Cantidad, 7. Monto exacto confirmado 7; mencionado sin reconfirmar 5.25; rango 3.5; "un abono" 1.75; sin monto 0.
4.2 Fecha exacta, 7. Fecha exacta 7; referencia cercana clara 5.25; fecha amplia 3.5; "el otro mes" 1.75; sin fecha 0.
4.3 Canal de pago, 5. Canal definido y confirmado 5; mencionado 3.75; canales generales 2.5; ambiguo 1.25; sin canal 0.
4.4 ConfirmaciÃ³n expresa, 7. AceptaciÃ³n clara 7; reserva menor 5.25; ambigua 3.5; intenciÃ³n general 1.75; rechazo/silencio 0.
4.5 Resumen y siguiente acciÃ³n, 4. Resume monto, fecha, canal y siguiente acciÃ³n 4; omite menor 3; solo monto/fecha 2; general 1; sin resumen 0.
Tipos de cierre permitidos: PAGO_INMEDIATO_CONFIRMADO, PROMESA_VERIFICABLE, PROMESA_PARCIAL, INTENCION_NO_VERIFICABLE, SEGUIMIENTO_ACORDADO, SIN_COMPROMISO, LLAMADA_INTERRUMPIDA.

D5. Experiencia y Ã©tica, 5 puntos:
5.1 Respeto y ausencia de juicio, 2. Cumple 2, parcial 1, no cumple 0.
5.2 EmpatÃ­a y escucha activa, 1. Cumple 1, parcial 0.5, no cumple 0.
5.3 Lenguaje claro y presiÃ³n profesional, 1. Cumple 1, parcial 0.5, no cumple 0.
5.4 Despedida y cierre profesional, 1. Cumple 1, parcial 0.5, no cumple 0.

Errores crÃ­ticos automÃ¡ticos, descalifican manteniendo score tÃ©cnico:
insulto directo, humillaciÃ³n, maltrato psicolÃ³gico explÃ­cito, discriminaciÃ³n, amenaza falsa grave,
revelaciÃ³n de deuda a tercero confirmado, suplantaciÃ³n o identificaciÃ³n falsa, burla sobre salud/desempleo/problema familiar,
manipulaciÃ³n deliberada con informaciÃ³n falsa.
Ejemplo: "Todo lo que dice son pretextos" puede ser maltrato psicolÃ³gico descalificante si el contexto confirma desacreditaciÃ³n.

Errores crÃ­ticos sujetos a calibraciÃ³n:
presiÃ³n excesiva, interrupciones constantes, sarcasmo dudoso, advertencia legal ambigua, comentario poco empÃ¡tico,
tono confrontacional, corte abrupto, frase culpabilizante moderada, informaciÃ³n imprecisa posiblemente involuntaria.
ClasifÃ­calos como CRITICO_CONDICIONADO y REQUIERE_REVISION; no descalifiques automÃ¡ticamente.

TipificaciÃ³n sugerida:
Devuelve dos tipificaciones sugeridas, principal y alternativa, sin cÃ³digo y sin impacto en score.
Ejemplos: dificultad de pago - problema financiero, problema personal, salud, desempleo, dificultad de negocio,
renuente, reclamo, niega deuda, rechazo de pago, posposiciÃ³n sin fecha, promesa total, promesa parcial,
pago realizado, seguimiento de soluciÃ³n de pago.

JSON mÃ­nimo obligatorio:
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
Incluye siempre los 24 criterios de la matriz. Si un criterio no puede evaluarse, inclÃºyelo con estado
NO_EVALUABLE o REQUIERE_REVISION, puntaje_obtenido null, motivo_no_evaluable claro y evidencia vacÃ­a.

Para compatibilidad gerencial, cada criterio puede incluir grupo_error_sgc y factor_sgc. Si no lo incluyes,
el sistema lo inferirÃ¡ por criterio.
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

Capa SGC/PEC para reporterÃ­a gerencial:
- MantÃ©n la matriz operativa COPC Cobranza como base de evaluaciÃ³n de la llamada.
- SGC/PEC no reemplaza a COPC: traduce los hallazgos a una clasificaciÃ³n interna para Pareto, feedback y coaching.
- Clasifica cada item tambiÃ©n en grupo_error_sgc y factor_sgc.
- Grupos permitidos:
  * Errores crÃ­ticos del negocio
  * Errores crÃ­ticos del usuario final
  * Errores crÃ­ticos de cumplimiento
  * Errores no crÃ­ticos
  * No aplica
- Factores SGC/PEC de negocio: RazÃ³n de no pago y explicar motivo, Urgencia y persistencia en el pago,
  GestiÃ³n de objeciones del cliente, Uso de aplicativo si aplica, Asesorar, Dominio de la llamada,
  Parafraseo / reafirmar acuerdo de pagos, TipificaciÃ³n correcta, Falta grave para el negocio,
  Cierre verificable 3C/4C, NegociaciÃ³n escalonada, Propuesta de alternativas, OrientaciÃ³n a resultado.
- Factores SGC/PEC de usuario final: InformaciÃ³n de la deuda, Agilidad / escucha activa,
  Falta grave para el usuario final, Claridad de la explicaciÃ³n, ConfusiÃ³n generada al cliente.
- Factores SGC/PEC de cumplimiento: Ley de protecciÃ³n y defensa del consumidor,
  ValidaciÃ³n de titularidad, ExposiciÃ³n de deuda a tercero, InformaciÃ³n falsa o riesgosa,
  Amenazas, presiÃ³n indebida o trato abusivo, Conducta Ã©tica y no abuso.
- Factores SGC/PEC no crÃ­ticos: IdentificaciÃ³n del cliente, IdentificaciÃ³n del gestor,
  EntonaciÃ³n, dicciÃ³n y empatÃ­a, TMO / ACW, Lenguaje formal, Despedida profesional,
  ActualizaciÃ³n de nÃºmeros telefÃ³nicos si aplica.

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
  * Si hay error crÃ­tico de cumplimiento, requiere_feedback=true y requiere_coaching=true.
  * Si hay falta anulante, requiere_coaching=true.
  * Si score_final < 80, requiere_feedback=true.
  * Si score_final < 70 o nivel_riesgo=ALTO, requiere_coaching=true.
  * Si el error es no crÃ­tico aislado, requiere_feedback=true y requiere_coaching puede ser false.
  * No marques todos los factores como coaching. El coaching es un plan estructurado para falta anulante,
    error crÃ­tico de cumplimiento, score_final < 70, nivel_riesgo=ALTO, reincidencia o definicion manual del supervisor.

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
      "grupo_error_sgc": "Errores crÃ­ticos del negocio | Errores crÃ­ticos del usuario final | Errores crÃ­ticos de cumplimiento | Errores no crÃ­ticos | No aplica",
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
    segmentos = identificar_interlocutores(transcripcion)
    hechos = extraer_hechos_llamada(client, segmentos, comentario_supervisor=comentario_supervisor)
    criterios = evaluar_criterios_desde_hechos(client, segmentos, hechos)
    criterios = normalizar_criterios_pipeline_v3(criterios, segmentos)
    score_antes = score_desde_criterios_pipeline_v3(criterios)
    auditoria = auditar_evaluacion(client, segmentos, hechos, criterios)
    criterios, criterios_corregidos = corregir_criterios_inconsistentes(client, segmentos, hechos, criterios, auditoria)
    criterios = normalizar_criterios_pipeline_v3(criterios, segmentos)
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


def identificar_interlocutores(transcripcion: str) -> List[Dict]:
    segmentos = segmentar_transcripcion_etiquetada_v2(transcripcion)
    if not segmentos:
        segmentos = segmentar_transcripcion_inferida_v2(transcripcion)
    normalizados = []
    ultimo = "NO_DETERMINADO"
    for idx, segmento in enumerate(segmentos, start=1):
        texto = str(segmento.get("texto") or "").strip()
        if not texto:
            continue
        hablante = normalizar_hablante_v2(segmento.get("hablante"))
        confianza = normalizar_confianza(segmento.get("confianza"))
        fundamento = str(segmento.get("fundamento") or "").strip()
        if hablante == "NO_DETERMINADO":
            hablante, confianza, fundamento = inferir_hablante_fragmento_v2(texto, ultimo)
        if hablante in {"AGENTE", "CLIENTE"}:
            ultimo = hablante
        normalizados.append({
            "segmento_id": idx,
            "orden": idx,
            "timestamp": normalizar_timestamp_v2(segmento.get("timestamp")),
            "inicio_segundos": normalizar_segundos_v2(segmento.get("inicio_segundos")),
            "fin_segundos": normalizar_segundos_v2(segmento.get("fin_segundos")),
            "hablante": hablante,
            "texto": texto,
            "confianza": confianza,
            "fundamento": fundamento,
        })
    return normalizados


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


def evaluar_criterios_desde_hechos(client, segmentos: List[Dict], hechos: Dict) -> List[Dict]:
    prompt = f"""
Evalua exclusivamente la llamada actual usando segmentos y hechos extraidos.
Devuelve exactamente los 24 criterios tecnicos. No decidas grupo SGC.
Usa segmentos_evidencia como fuente principal. No inventes citas.
NO_CUMPLE solo si hubo oportunidad clara y la conducta fallo. Si falta evidencia usa NO_EVALUABLE o REQUIERE_REVISION.
Evalua cierre 4C criterio por criterio: cantidad, fecha, canal, confirmacion y resumen.

Matriz:
{json.dumps(matriz_tecnica_pipeline_v3(), ensure_ascii=False)}

Segmentos completos:
{json.dumps(segmentos, ensure_ascii=False)}

Hechos:
{json.dumps(hechos, ensure_ascii=False)}

Devuelve JSON:
{{"criterios": [
  {{"codigo": "1.1", "nombre": "", "peso": 3, "estado": "CUMPLE|PARCIAL_ALTO|PARCIAL_MEDIO|PARCIAL_BAJO|NO_CUMPLE|NO_EVALUABLE|REQUIERE_REVISION", "puntaje_obtenido": 0, "segmentos_evidencia": [], "segmentos_contexto": [], "tipo_evidencia": "DIRECTA|CONTEXTUAL|AUSENCIA_EN_SECUENCIA|REVISION_HUMANA", "conducta_observada": "", "hallazgo": "", "impacto_negocio": "", "impacto_cliente": "", "recomendacion_entrenable": "", "frase_sugerida": "", "fortaleza_relacionada": null}}
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


def corregir_criterios_inconsistentes(client, segmentos: List[Dict], hechos: Dict, criterios: List[Dict], auditoria: Dict) -> tuple[List[Dict], List[str]]:
    inconsistencias = [
        item for item in auditoria.get("inconsistencias", [])
        if isinstance(item, dict) and item.get("criterio") and item.get("accion") == "REVISAR_CRITERIO"
    ]
    if not inconsistencias:
        return criterios, []
    criterios_por_codigo = {str(item.get("codigo") or ""): item for item in criterios if isinstance(item, dict)}
    cuestionados = [criterios_por_codigo.get(str(item.get("criterio"))) for item in inconsistencias]
    cuestionados = [item for item in cuestionados if item]
    prompt = f"""
Corrige solo los criterios cuestionados. No analices criterios no listados.
Usa segmentos_evidencia por ID y no inventes citas.

Segmentos relacionados y completos:
{json.dumps(segmentos, ensure_ascii=False)}

Hechos:
{json.dumps(hechos, ensure_ascii=False)}

Criterios cuestionados:
{json.dumps(cuestionados, ensure_ascii=False)}

Observaciones auditor:
{json.dumps(inconsistencias, ensure_ascii=False)}

Devuelve JSON:
{{"criterios": [{{"codigo": "", "nombre": "", "peso": 0, "estado": "CUMPLE|PARCIAL_ALTO|PARCIAL_MEDIO|PARCIAL_BAJO|NO_CUMPLE|NO_EVALUABLE|REQUIERE_REVISION", "puntaje_obtenido": 0, "segmentos_evidencia": [], "segmentos_contexto": [], "tipo_evidencia": "DIRECTA|CONTEXTUAL|AUSENCIA_EN_SECUENCIA|REVISION_HUMANA", "conducta_observada": "", "hallazgo": "", "impacto_negocio": "", "impacto_cliente": "", "recomendacion_entrenable": "", "frase_sugerida": "", "fortaleza_relacionada": null}}]}}
""".strip()
    data = llamar_json_modelo_pipeline_v3(client, prompt, "Corrige criterios puntuales observados por auditoria.")
    corregidos = normalizar_criterios_pipeline_v3(data.get("criterios") if isinstance(data.get("criterios"), list) else [], segmentos)
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


def normalizar_criterios_pipeline_v3(criterios: List[Dict], segmentos: List[Dict]) -> List[Dict]:
    por_codigo = {codigo_item_canonico(item): (segmento, item, peso) for segmento, item, peso in COPC_ITEMS_CANONICOS}
    segmentos_por_id = {int(item.get("segmento_id") or 0): item for item in segmentos}
    salida = []
    entrada = {str(item.get("codigo") or item.get("codigo_criterio") or "").strip(): item for item in criterios if isinstance(item, dict)}
    for codigo, (segmento, item_canonico, peso) in por_codigo.items():
        raw = entrada.get(codigo) or {}
        estado = normalizar_estado_criterio_v2(raw.get("estado") or raw.get("resultado"))
        nota = puntaje_pipeline_v3(raw.get("puntaje_obtenido"), estado, peso)
        evidencia_ids = normalizar_ids_segmentos_pipeline_v3(raw.get("segmentos_evidencia"), segmentos_por_id)
        contexto_ids = normalizar_ids_segmentos_pipeline_v3(raw.get("segmentos_contexto"), segmentos_por_id)
        evidencia_textual = [segmentos_por_id[item]["texto"] for item in evidencia_ids if item in segmentos_por_id]
        salida.append({
            "codigo": codigo,
            "codigo_criterio": codigo,
            "nombre": nombre_item_sin_codigo(item_canonico),
            "dimension": segmento,
            "peso": peso,
            "estado": estado,
            "puntaje_obtenido": nota,
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
            "evidencia_textual": evidencia_textual,
        })
    return salida


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


def score_desde_criterios_pipeline_v3(criterios: List[Dict]) -> Dict:
    bruto = 0.0
    peso = 0.0
    for item in criterios:
        if item.get("estado") == "NO_EVALUABLE":
            continue
        bruto += float(item.get("puntaje_obtenido") or 0)
        peso += float(item.get("peso") or 0)
    score = round((bruto / peso) * 100, 2) if peso else 0.0
    return {"score_bruto": round(bruto, 2), "peso_aplicable": round(peso, 2), "score_tecnico": score}


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
) -> Dict:
    dimensiones = []
    for segmento in dict.fromkeys(seg for seg, _, _ in COPC_ITEMS_CANONICOS):
        criterios_segmento = [criterio_pipeline_a_v2(item) for item in criterios if item.get("dimension") == segmento]
        peso = sum(float(item.get("puntaje_maximo") or 0) for item in criterios_segmento)
        nota = sum(float(item.get("puntaje_obtenido") or 0) for item in criterios_segmento)
        dimensiones.append({"codigo": segmento, "nombre": segmento, "puntaje_maximo": peso, "puntaje_obtenido": round(nota, 2), "criterios": criterios_segmento})
    resumen = feedback.get("resumen_ejecutivo") if isinstance(feedback.get("resumen_ejecutivo"), dict) else {}
    gestion = feedback.get("resultado_gestion") if isinstance(feedback.get("resultado_gestion"), dict) else {}
    coaching = feedback.get("coaching") if isinstance(feedback.get("coaching"), dict) else {}
    requiere_revision = any(item.get("estado") == "REQUIERE_REVISION" for item in criterios)
    score = score_despues.get("score_tecnico", 0)
    cobertura = hechos.get("cobertura") if isinstance(hechos.get("cobertura"), dict) else {}
    return {
        "version_evaluacion": "2.0",
        "motor_evaluacion": "PIPELINE_MULTIPASO_V3",
        "resultado_evaluacion": {
            "score_tecnico": score,
            "score_maximo": 100,
            "nota_minima_aprobatoria": 85,
            "estado_tecnico": "APROBADA" if score >= 85 else "NO_APROBADA",
            "estado_calidad": "PENDIENTE_REVISION" if requiere_revision else ("APROBADA" if score >= 85 else "NO_APROBADA"),
            "descalificada": False,
            "motivo_descalificacion": None,
            "confianza_global": confianza_global_segmentos_v2(segmentos),
            "evaluacion_provisional": requiere_revision,
            "requiere_revision_humana": requiere_revision,
            "motivos_revision": [item.get("codigo") for item in criterios if item.get("estado") == "REQUIERE_REVISION"],
        },
        "resultado_gestion": gestion,
        "tipificaciones_sugeridas": feedback.get("tipificaciones_sugeridas") if isinstance(feedback.get("tipificaciones_sugeridas"), list) else [],
        "resumen_ejecutivo": resumen,
        "interlocutores": {"confianza_global": confianza_global_segmentos_v2(segmentos), "metodo": "PIPELINE_SECUENCIAL", "segmentos": segmentos},
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
            "inconsistencias_encontradas": len(auditoria.get("inconsistencias", [])),
            "criterios_corregidos": criterios_corregidos,
            "score_antes_auditoria": score_antes,
            "score_despues_auditoria": score_despues,
            "cartera": cartera,
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
    grupo_sgc, factor_sgc = SGC_MAPEO_CRITERIOS.get(codigo, (SGC_GRUPO_NO_CRITICO, item.get("nombre") or "Criterio tecnico"))
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
        "puede_descalificar": False,
        "confianza": "",
        "requiere_revision": item.get("estado") == "REQUIERE_REVISION",
        "motivo_no_evaluable": item.get("hallazgo") if item.get("estado") in {"NO_EVALUABLE", "REQUIERE_REVISION"} else "",
        "factor": factor_sgc,
        "grupo_sgc": grupo_sgc,
        "grupo_error_sgc": grupo_sgc,
        "factor_sgc": factor_sgc,
        "calificacion": resultado_legacy_desde_estado_v2(item.get("estado")),
        "conducta_observada": item.get("conducta_observada") or "",
        "lectura_ia": item.get("hallazgo") or "",
        "impacto_negocio": item.get("impacto_negocio") or "",
        "impacto_cliente": item.get("impacto_cliente") or "",
        "recomendacion_entrenable": item.get("recomendacion_entrenable") or "",
        "frase_sugerida": item.get("frase_sugerida") or "",
        "fortaleza_relacionada": item.get("fortaleza_relacionada"),
    }


def cargar_json_analisis(content: str, *, client=None) -> Dict:
    try:
        data = json.loads(content or "{}")
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass

    if client is None:
        raise ValueError("La IA devolviÃ³ un JSON invÃ¡lido y no se pudo reparar.")

    reparacion = client.chat.completions.create(
        model=ANALYSIS_MODEL,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": "Repara el contenido para que sea exclusivamente JSON vÃ¡lido. No agregues datos nuevos.",
            },
            {"role": "user", "content": content or "{}"},
        ],
    )
    reparado = reparacion.choices[0].message.content or "{}"
    data = json.loads(reparado)
    if not isinstance(data, dict):
        raise ValueError("La reparaciÃ³n de JSON no devolviÃ³ un objeto vÃ¡lido.")
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
                    "La respuesta previa no cumpliÃ³ el contrato COPC v2. "
                    "Devuelve exclusivamente JSON vÃ¡lido con version_evaluacion '2.0' "
                    "y las 5 dimensiones con los criterios de la matriz COPC v2 definida. "
                    "Incluye interlocutores.segmentos con hablante, texto, timestamp, confianza y fundamento "
                    "cuando la transcripciÃ³n permita separar turnos de habla. "
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
        raise ValueError("La IA no devolviÃ³ una evaluaciÃ³n COPC v2 vÃ¡lida con criterios completos.")
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
    es_pipeline_v3 = data.get("motor_evaluacion") == "PIPELINE_MULTIPASO_V3"
    resultado = data.get("resultado_evaluacion") if isinstance(data.get("resultado_evaluacion"), dict) else {}
    gestion = data.get("resultado_gestion") if isinstance(data.get("resultado_gestion"), dict) else {}
    resumen = data.get("resumen_ejecutivo") if isinstance(data.get("resumen_ejecutivo"), dict) else {}
    coaching = data.get("coaching") if isinstance(data.get("coaching"), dict) else {}
    feedback_supervisor = coaching.get("feedback_supervisor") if isinstance(coaching.get("feedback_supervisor"), dict) else {}
    feedback_asesor = coaching.get("feedback_asesor") if isinstance(coaching.get("feedback_asesor"), dict) else {}
    interlocutores = normalizar_interlocutores_v2(data, transcripcion)
    data["interlocutores"] = interlocutores

    evaluacion = normalizar_dimensiones_copc_v2(data.get("dimensiones"))
    if not es_pipeline_v3:
        evaluacion = reparar_evaluacion_contextual_v2(evaluacion, data, transcripcion)
    score_bruto, peso_aplicable, score_tecnico = calcular_score_normalizado(evaluacion)
    score_tecnico = round(min(score_tecnico, 100), 2)

    descalificada_ia = bool(resultado.get("descalificada"))
    descalificada = False
    errores_criticos = normalizar_errores_criticos_v2(data.get("errores_criticos"), evaluacion)
    if not es_pipeline_v3:
        errores_criticos = reparar_errores_criticos_contextuales_v2(errores_criticos, evaluacion, data, transcripcion)
    frase_anulante = (
        str(resultado.get("motivo_descalificacion") or "No aplica")
        if es_pipeline_v3
        else frase_anulante_contextual_v2(resultado, errores_criticos, transcripcion, descalificada_ia)
    )
    descalificada = (descalificada_ia or any(item.get("automatico") for item in errores_criticos)) and cita_anulante_valida_v2(frase_anulante)
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
    puntos_criticos = consolidar_puntos_sgc(deduplicar_puntos_criticos(puntos_criticos))
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
        alertas.append(f"DescalificaciÃ³n: {resultado.get('motivo_descalificacion') or 'error crÃ­tico automÃ¡tico'}")
    if requiere_revision:
        alertas.append("Requiere revisiÃ³n humana por criterios no concluyentes o confianza baja.")
    for item in puntos_criticos[:4]:
        if item.get("hallazgo"):
            alertas.append(str(item.get("hallazgo")))

    return {
        "version_evaluacion": "2.0",
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
            raw.get("texto")
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
            or raw.get("speaker")
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
            "hablante": hablante,
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
        metodo = "INFERIDO_DESDE_TRANSCRIPCION" if segmentos else "NO_DISPONIBLE"
    confianza_global = normalizar_confianza(interlocutores.get("confianza_global") or confianza_global_segmentos_v2(segmentos))
    return {
        "confianza_global": confianza_global if segmentos else "BAJA",
        "metodo": metodo,
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
    aplica = estado != "NO_EVALUABLE"
    if estado == "NO_EVALUABLE":
        aplica = False
    nota = numero_en_rango(criterio.get("puntaje_obtenido"), 0, peso)
    if estado in {"NO_EVALUABLE", "REQUIERE_REVISION"} and criterio.get("puntaje_obtenido") in (None, ""):
        nota = 0
    resultado = resultado_legacy_desde_estado_v2(estado)
    codigo_final = str(criterio.get("codigo_criterio") or codigo or "").strip()
    if codigo_final in SGC_MAPEO_CRITERIOS:
        grupo_sgc, factor_sgc = SGC_MAPEO_CRITERIOS[codigo_final]
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
        "grupo_sgc": str(criterio.get("grupo_sgc") or grupo_sgc),
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
        return "DiagnÃ³stico"
    if "gestion" in texto or "gestiÃ³n" in texto or "negoci" in texto:
        return "GestiÃ³n de soluciÃ³n"
    if "cierre" in texto:
        return "Cierre verificable"
    if "experiencia" in texto or "etica" in texto or "Ã©tica" in texto:
        return "Experiencia y Ã©tica"
    return "Sin segmento"


def normalizar_estado_criterio_v2(value) -> str:
    estado = str(value or "REQUIERE_REVISION").strip().upper()
    estado = estado.replace(" ", "_").replace("-", "_")
    aliases = {
        "PARCIAL": "PARCIAL_MEDIO",
        "REVISION_HUMANA": "REQUIERE_REVISION",
        "REQUIERE_REVISION_HUMANA": "REQUIERE_REVISION",
        "NO_APLICA": "NO_EVALUABLE",
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
    if estado == "NO_EVALUABLE":
        return "No aplica"
    return "Requiere revisiÃ³n"


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
        r"se[nÃ±]or[a]?\s+.{2,120}\?\s*(si|digame|si digame|si senor|si senorita)",
    ]
    if any(re.search(patron, texto_key, flags=re.IGNORECASE) for patron in patrones_key):
        return True
    patrones = [
        r"Â¿?\s*con\s+[^?]{2,80}\?\s*Â¿?\s*(s[iÃ­]|ella habla|soy yo|con ella|d[iÃ­]game|s[iÃ­]\s+seÃ±or(?:a|ita)?)\b",
        r"me comunico con\s+[^?]{2,80}\?\s*(s[iÃ­]|ella habla|soy yo|con ella|d[iÃ­]game)\b",
        r"hablo con\s+[^?]{2,80}\?\s*(s[iÃ­]|ella habla|soy yo|con ella|d[iÃ­]game)\b",
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
        r"pagar[eÃ©]?\s*(?:200|300)[^.?!]{0,180}",
        r"estoy en la sierra[^.?!]{0,180}",
    ])


def reparar_evaluacion_contextual_v2(evaluacion: List[Dict], data: Dict, transcripcion: str = "") -> List[Dict]:
    """
    ValidaciÃ³n conservadora posterior al anÃ¡lisis IA.

    Esta funciÃ³n NO debe reconstruir la evaluaciÃ³n con reglas especÃ­ficas de una
    llamada anterior ni sobreescribir criterios completos por coincidencias de
    palabras. La IA ya evaluÃ³ los 24 criterios con el prompt vigente.

    Responsabilidades:
    1. validar que las evidencias textuales pertenezcan a la transcripciÃ³n actual;
    2. evitar contaminaciÃ³n entre evaluaciones;
    3. conservar score, resultado y hallazgo devueltos por IA salvo que la
       evidencia sea claramente invÃ¡lida;
    4. ante evidencia invÃ¡lida, pasar a revisiÃ³n en vez de fabricar un hallazgo.
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

            # Tolerancia a pequeÃ±as diferencias de puntuaciÃ³n/transcripciÃ³n.
            tokens = [t for t in frase_key.split() if len(t) >= 4]
            if len(tokens) >= 4:
                ventana = " ".join(tokens[: min(8, len(tokens))])
                if ventana and ventana in transcripcion_key:
                    evidencias_validas.append(frase)

        if evidencias:
            item["evidencia_textual"] = evidencias_validas

            # Si la IA devolviÃ³ evidencia, pero ninguna pertenece a esta llamada,
            # no se mantiene el hallazgo como confirmado.
            if not evidencias_validas:
                # No destruimos el resultado ni el score del criterio.
                # Solo marcamos la literalidad de la evidencia como pendiente.
                item["evidencia"] = "Evidencia textual no validada automÃ¡ticamente."
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
        if texto and texto.lower() not in {"no disponible", "-", "maltrato psicolÃ³gico explÃ­cito y presiÃ³n excesiva"}:
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
    if texto.lower() in {"null", "none", "no disponible", "-", "revisar transcripcion", "revisar transcripciÃ³n"}:
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
            automatico = str(item.get("tipo") or item.get("clasificacion") or "").upper() in {"AUTOMATICO", "AUTOMÃTICO", "DESCALIFICANTE"}
            rows.append({
                "segmento": formatear_segmento_v2(item.get("segmento_copc") or item.get("segmento") or "Experiencia y Ã©tica"),
                "segmento_copc": formatear_segmento_v2(item.get("segmento_copc") or item.get("segmento") or "Experiencia y Ã©tica"),
                "grupo_error_sgc": normalizar_grupo_sgc(item.get("grupo_error_sgc") or SGC_GRUPO_CUMPLIMIENTO, item),
                "factor_sgc": str(item.get("factor_sgc") or item.get("criterio") or item.get("tipo") or "Conducta Ã©tica y no abuso"),
                "categoria": str(item.get("criterio") or item.get("tipo") or "Error crÃ­tico"),
                "severidad": "ANULANTE" if automatico else "GRAVE",
                "automatico": automatico,
                "requiere_revision": bool(item.get("requiere_revision") or not automatico),
                "hallazgo": str(item.get("hallazgo") or item.get("descripcion") or "-"),
                "frase_textual": str(item.get("frase_textual") or item.get("frase") or "No disponible"),
                "momento": item.get("timestamp") or item.get("momento"),
                "evidencia": str(item.get("evidencia") or item.get("frase_textual") or "-"),
                "impacto": str(item.get("impacto") or "Riesgo crÃ­tico para calidad y cumplimiento."),
                "recomendacion": str(item.get("recomendacion") or "RevisiÃ³n inmediata por supervisor."),
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
                "factor_sgc": str(item.get("factor_sgc") or item.get("criterio") or "Hallazgo no crÃ­tico"),
                "categoria": str(item.get("criterio") or "Hallazgo no crÃ­tico"),
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
        and item.get("resultado") not in {"Cumple", "No aplica", "Requiere revisiÃ³n", "Requiere revision"}
        and not item.get("puede_descalificar")
    ][:8]


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
            grupos[key] = copia
            orden.append(key)

        codigo = str(item.get("codigo_criterio") or "").strip()
        if codigo and codigo not in grupos[key]["criterios_relacionados"]:
            grupos[key]["criterios_relacionados"].append(codigo)

        # Si el primer registro no tiene evidencia Ãºtil, usa otra del grupo.
        evidencia_actual = str(grupos[key].get("evidencia") or "").strip()
        evidencia_nueva = str(item.get("evidencia") or "").strip()
        if evidencia_actual in {"", "-", "No disponible.", "Evidencia textual no validada automÃ¡ticamente."} and evidencia_nueva:
            grupos[key]["evidencia"] = evidencia_nueva

    return [grupos[key] for key in orden]


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
- Comunicacion: claridad, orden, lenguaje simple y escucha activa, que el agente no utilice sarcasmos y su tono debe ser atento, empÃ¡tico.
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
    """
    ClasificaciÃ³n SGC determinÃ­stica.

    La IA evalÃºa conducta, evidencia, resultado y recomendaciÃ³n.
    El sistema decide grupo/factor SGC segÃºn el cÃ³digo tÃ©cnico para evitar
    duplicidades y clasificaciones inconsistentes entre evaluaciones.
    """
    codigo = str(
        item.get("codigo_criterio")
        or item.get("codigo")
        or obtener_codigo_item_copc(item)
        or ""
    ).strip()

    if codigo in SGC_MAPEO_CRITERIOS:
        grupo, factor = SGC_MAPEO_CRITERIOS[codigo]
        return {
            "grupo_error_sgc": grupo,
            "factor_sgc": factor,
        }

    # Fallback histÃ³rico para registros antiguos que no tengan cÃ³digo.
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
                factor = "Registro y trazabilidad de gestiÃ³n"
            return {"grupo_error_sgc": grupo, "factor_sgc": factor}

    return {
        "grupo_error_sgc": SGC_GRUPO_NO_CRITICO,
        "factor_sgc": str(item.get("item") or "Criterio sin clasificaciÃ³n"),
    }


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
    lower = limpiar_key_texto(texto)

    if lower in {"requiere revision", "revision humana"} or "requiere revis" in lower:
        return "Requiere revisiÃ³n"
    if lower in {"no evaluable", "no aplica", "n a", "na"}:
        return "No aplica"
    if "parcial" in lower:
        return "Parcial"
    if "no cumple" in lower or "no evidenciado" in lower:
        return "No cumple"
    if "cumple" in lower:
        return "Cumple"

    # Si no hay estado confiable, no fabricar un incumplimiento.
    return "Requiere revisiÃ³n"


def debe_contar_error_sgc(item: Dict) -> bool:
    """
    Solo cuenta brechas confirmadas.
    RevisiÃ³n humana / evidencia pendiente NO equivale a NO CUMPLE.
    """
    if item.get("aplica") is False:
        return False

    grupo = item.get("grupo_error_sgc")
    if grupo == SGC_GRUPO_NO_APLICA:
        return False

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
    motivo = resumen.get("motivo") or "ClasificaciÃ³n SGC/PEC generada desde la matriz COPC."
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
            "motivo_no_aplica": "Criterio no devuelto por IA; requiere revisiÃ³n si era aplicable.",
            "resultado": "Requiere revisiÃ³n",
            "segmento_copc": segmento,
            "grupo_error_sgc": "",
            "factor_sgc": "",
            "calificacion": "Requiere revisiÃ³n",
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
        resultado = str(item.get("resultado") or item.get("calificacion") or "").strip().lower()
        motivo_no_aplica = str(item.get("motivo_no_aplica") or "").strip().lower()
        no_aplica_real = item.get("aplica") is False and (
            "no aplica" in resultado
            or "no evaluable" in resultado
            or "no_evaluable" in motivo_no_aplica
        )
        if no_aplica_real:
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
