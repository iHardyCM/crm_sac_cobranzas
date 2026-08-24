from __future__ import annotations

from copy import deepcopy
from typing import Dict, List, Optional


PENC = "PENC"
PECUF = "PECUF"
PECN = "PECN"
PECC = "PECC"

FUENTE_AUDIO = "AUDIO"
FUENTE_TRANSCRIPCION = "TRANSCRIPCION"
FUENTE_CRM = "CRM"
FUENTE_TIPIFICACION = "TIPIFICACION"
FUENTE_CAMPANIA = "CAMPANIA"
FUENTE_SISTEMA = "SISTEMA"
FUENTE_MULTIFUENTE = "MULTIFUENTE"

# Fuente funcional: PAUTA_MONITOREO_MIBANCO_CORREGIDA 2.xlsx
# Hoja "PAUTA MONITOREO". Los pesos del archivo vienen como proporciones
# (0.20, 0.05, etc.); aquí se conservan sobre escala 100.
MIBANCO_PESOS_ESPERADOS = {
    PECUF: 30.0,
    PECN: 40.0,
    PECC: 20.0,
    PENC: 10.0,
}


MIBANCO_PAUTA: List[Dict] = [
    {
        "codigo_criterio": "PECUF.1",
        "bloque": PECUF,
        "categoria": "PEC",
        "subcategoria": "Precisión de Error Crítico Usuario Final",
        "nombre": "Falta de respeto",
        "peso": 20,
        "detalle": "Mantiene respeto durante toda la llamada",
        "regla_evaluacion": "No agrede, ridiculiza, descalifica ni utiliza expresiones ofensivas. Una agresión grave se considera causal de descalificación según la regla crítica transversal.",
        "criticidad": "ERROR_CRITICO_USUARIO_FINAL",
        "fuente_evidencia": FUENTE_AUDIO,
        "regla_aplicabilidad": "Aplica a toda interacción audible del asesor.",
        "puede_descalificar": True,
        "requiere_evidencia": True,
    },
    {
        "codigo_criterio": "PECUF.2",
        "bloque": PECUF,
        "categoria": "PEC",
        "subcategoria": "Precisión de Error Crítico Usuario Final",
        "nombre": "Escucha activa",
        "peso": 2,
        "detalle": "Escucha, comprende y confirma",
        "regla_evaluacion": "Evita interrupciones inoportunas, comprende lo expresado por el cliente y realiza preguntas de confirmación cuando la información no es clara.",
        "criticidad": "ERROR_CRITICO_USUARIO_FINAL",
        "fuente_evidencia": FUENTE_AUDIO,
        "regla_aplicabilidad": "Aplica cuando el cliente entrega información, objeta, consulta o requiere comprensión del asesor.",
        "puede_descalificar": False,
        "requiere_evidencia": True,
    },
    {
        "codigo_criterio": "PECUF.3",
        "bloque": PECUF,
        "categoria": "PEC",
        "subcategoria": "Precisión de Error Crítico Usuario Final",
        "nombre": "Precisión de la información de la deuda",
        "peso": 5,
        "detalle": "Comunica información financiera exacta",
        "regla_evaluacion": "Brinda únicamente datos vigentes y verificables: deuda, días de mora, producto, cuota u otros conceptos que correspondan al caso.",
        "criticidad": "ERROR_CRITICO_USUARIO_FINAL",
        "fuente_evidencia": FUENTE_MULTIFUENTE,
        "regla_aplicabilidad": "Aplica cuando el asesor comunica deuda, mora, producto, cuota, monto u otros datos financieros.",
        "puede_descalificar": False,
        "requiere_evidencia": True,
    },
    {
        "codigo_criterio": "PECUF.4",
        "bloque": PECUF,
        "categoria": "PEC",
        "subcategoria": "Precisión de Error Crítico Usuario Final",
        "nombre": "Claridad con la información",
        "peso": 3,
        "detalle": "Explicación clara y coherente",
        "regla_evaluacion": "Se expresa con orden, no se contradice, responde de forma comprensible y transmite seguridad sin generar confusión.",
        "criticidad": "ERROR_CRITICO_USUARIO_FINAL",
        "fuente_evidencia": FUENTE_TRANSCRIPCION,
        "regla_aplicabilidad": "Aplica cuando el asesor entrega información o explica condiciones durante la llamada.",
        "puede_descalificar": False,
        "requiere_evidencia": True,
    },
    {
        "codigo_criterio": "PECN.1",
        "bloque": PECN,
        "categoria": "PEC",
        "subcategoria": "Precisión de Error Crítico del Negocio",
        "nombre": "Sondeo y diagnóstico",
        "peso": 5,
        "detalle": "Identifica causa y capacidad de pago",
        "regla_evaluacion": "Realiza preguntas de diagnóstico y seguimiento para comprender la causa del no pago, intención y capacidad, sin convertir el sondeo en un interrogatorio.",
        "criticidad": "ERROR_CRITICO_NEGOCIO",
        "fuente_evidencia": FUENTE_TRANSCRIPCION,
        "regla_aplicabilidad": "Aplica cuando existe contacto con el titular o interlocutor autorizado y objetivo de cobranza.",
        "puede_descalificar": False,
        "requiere_evidencia": True,
    },
    {
        "codigo_criterio": "PECN.2",
        "bloque": PECN,
        "categoria": "PEC",
        "subcategoria": "Precisión de Error Crítico del Negocio",
        "nombre": "Negociación escalonada",
        "peso": 10,
        "detalle": "Propone alternativas orientadas al pago",
        "regla_evaluacion": "Construye una propuesta acorde con el diagnóstico, presenta alternativas válidas y busca una acción concreta de pago dentro de las opciones autorizadas.",
        "criticidad": "ERROR_CRITICO_NEGOCIO",
        "fuente_evidencia": FUENTE_TRANSCRIPCION,
        "regla_aplicabilidad": "Aplica cuando la llamada genera oportunidad real de gestionar pago, abono, convenio o alternativa autorizada.",
        "puede_descalificar": False,
        "requiere_evidencia": True,
    },
    {
        "codigo_criterio": "PECN.3",
        "bloque": PECN,
        "categoria": "PEC",
        "subcategoria": "Precisión de Error Crítico del Negocio",
        "nombre": "Manejo de objeciones",
        "peso": 15,
        "detalle": "Argumenta según la objeción",
        "regla_evaluacion": "Es una respuesta ante la negativa del cliente utilizando argumentos sólidos y válidos alineados a la objeción expuesta por el cliente.",
        "criticidad": "ERROR_CRITICO_NEGOCIO",
        "fuente_evidencia": FUENTE_TRANSCRIPCION,
        "regla_aplicabilidad": "Aplica únicamente si el cliente presenta objeción, rechazo, imposibilidad, duda relevante o restricción económica.",
        "puede_descalificar": False,
        "requiere_evidencia": True,
    },
    {
        "codigo_criterio": "PECN.4",
        "bloque": PECN,
        "categoria": "PEC",
        "subcategoria": "Precisión de Error Crítico del Negocio",
        "nombre": "Cierre de negociación",
        "peso": 10,
        "detalle": "Inducir a cierre para una promesa de pago",
        "regla_evaluacion": "Luego de haber informado la deuda y haber hecho frente a sus objeciones, el agente debe cerrar la promesa de pago de forma efectiva y oportuna.",
        "criticidad": "ERROR_CRITICO_NEGOCIO",
        "fuente_evidencia": FUENTE_TRANSCRIPCION,
        "regla_aplicabilidad": "Aplica cuando la conversación permite concretar promesa, abono, convenio o siguiente acción de pago.",
        "puede_descalificar": False,
        "requiere_evidencia": True,
    },
    {
        "codigo_criterio": "PECC.1",
        "bloque": PECC,
        "categoria": "PEC",
        "subcategoria": "Precisión de Error Crítico de Cumplimiento",
        "nombre": "Filosofía Biznescob",
        "peso": 5,
        "detalle": "Protege la imagen de Mibanco",
        "regla_evaluacion": "No desacredita a Mibanco, a sus colaboradores, áreas, procesos o canales; tampoco responsabiliza a terceros para justificar una mala gestión.",
        "criticidad": "ERROR_CRITICO_CUMPLIMIENTO",
        "fuente_evidencia": FUENTE_TRANSCRIPCION,
        "regla_aplicabilidad": "Aplica a toda referencia del asesor sobre Mibanco, sus canales, colaboradores o procesos.",
        "puede_descalificar": False,
        "requiere_evidencia": True,
    },
    {
        "codigo_criterio": "PECC.2",
        "bloque": PECC,
        "categoria": "PEC",
        "subcategoria": "Precisión de Error Crítico de Cumplimiento",
        "nombre": "Confirmación del acuerdo",
        "peso": 5,
        "detalle": "Lectura de speech",
        "regla_evaluacion": "Evalúa el speech de confirmación de promesa de pago verbal al cliente. Debe quedar claro el compromiso y sus condiciones principales.",
        "criticidad": "ERROR_CRITICO_CUMPLIMIENTO",
        "fuente_evidencia": FUENTE_TRANSCRIPCION,
        "regla_aplicabilidad": "Aplica cuando existe promesa, compromiso, abono, convenio o acuerdo verbal.",
        "puede_descalificar": False,
        "requiere_evidencia": True,
    },
    {
        "codigo_criterio": "PECC.3",
        "bloque": PECC,
        "categoria": "PEC",
        "subcategoria": "Precisión de Error Crítico de Cumplimiento",
        "nombre": "Tipificación de la gestión",
        "peso": 10,
        "detalle": "Registra el motivo de llamada de acuerdo al escenario.",
        "regla_evaluacion": "Tipifica de manera correcta el motivo o submotivo de la llamada y en el campo de observaciones deja un detalle completo.",
        "criticidad": "ERROR_CRITICO_CUMPLIMIENTO",
        "fuente_evidencia": FUENTE_TIPIFICACION,
        "regla_aplicabilidad": "Aplica cuando existe tipificación o resultado de gestión registrado para la llamada.",
        "puede_descalificar": False,
        "requiere_evidencia": True,
    },
    {
        "codigo_criterio": "PENC.1",
        "bloque": PENC,
        "categoria": "PENC",
        "subcategoria": "Precisión de Error No Crítico - Protocolos de Atención",
        "nombre": "Saludo de bienvenida",
        "peso": 2,
        "detalle": "Saluda oportunamente",
        "regla_evaluacion": "Saluda al inicio de la interacción, indicando nombre y apellidos del ejecutivo, sin omitir que actúa en representación de Mibanco.",
        "criticidad": "ERROR_NO_CRITICO",
        "fuente_evidencia": FUENTE_AUDIO,
        "regla_aplicabilidad": "Aplica a llamadas con contacto efectivo o intento de apertura audible.",
        "puede_descalificar": False,
        "requiere_evidencia": False,
    },
    {
        "codigo_criterio": "PENC.2",
        "bloque": PENC,
        "categoria": "PENC",
        "subcategoria": "Precisión de Error No Crítico - Protocolos de Atención",
        "nombre": "Tono de voz",
        "peso": 3,
        "detalle": "Fluidez, modulación y dicción",
        "regla_evaluacion": "Mantiene tono, velocidad, vocalización y fluidez adecuadas; evita muletillas repetitivas y tecnicismos innecesarios.",
        "criticidad": "ERROR_NO_CRITICO",
        "fuente_evidencia": FUENTE_AUDIO,
        "regla_aplicabilidad": "Aplica cuando el audio permite evaluar locución de forma suficiente.",
        "puede_descalificar": False,
        "requiere_evidencia": False,
    },
    {
        "codigo_criterio": "PENC.3",
        "bloque": PENC,
        "categoria": "PENC",
        "subcategoria": "Precisión de Error No Crítico - Protocolos de Atención",
        "nombre": "Claridad del lenguaje oral",
        "peso": 3,
        "detalle": "Explicación clara y coherente",
        "regla_evaluacion": "Se expresa con orden, no se contradice, responde de forma comprensible y transmite seguridad sin generar confusión.",
        "criticidad": "ERROR_NO_CRITICO",
        "fuente_evidencia": FUENTE_TRANSCRIPCION,
        "regla_aplicabilidad": "Aplica cuando el asesor entrega información o explica condiciones durante la llamada.",
        "puede_descalificar": False,
        "requiere_evidencia": False,
    },
    {
        "codigo_criterio": "PENC.4",
        "bloque": PENC,
        "categoria": "PENC",
        "subcategoria": "Precisión de Error No Crítico - Protocolos de Atención",
        "nombre": "Despedida adecuada",
        "peso": 2,
        "detalle": "Cierre cordial",
        "regla_evaluacion": "Finaliza la llamada de forma educada y profesional, una vez concluida la gestión.",
        "criticidad": "ERROR_NO_CRITICO",
        "fuente_evidencia": FUENTE_AUDIO,
        "regla_aplicabilidad": "Aplica cuando existe cierre audible de la llamada y no se corta por falla técnica o abandono del cliente.",
        "puede_descalificar": False,
        "requiere_evidencia": False,
    },
]


MIBANCO_REGLAS_DESCALIFICACION = [
    {
        "codigo": "DESC_AGRESION_INSULTO",
        "nombre": "Insulto, agresión o humillación grave",
        "criterios_relacionados": ["PECUF.1"],
        "requiere_rol": "AGENTE",
        "requiere_evidencia": True,
    },
    {
        "codigo": "DESC_AMENAZA_COACCION",
        "nombre": "Amenaza o coacción grave",
        "criterios_relacionados": ["PECC.1"],
        "requiere_rol": "AGENTE",
        "requiere_evidencia": True,
    },
    {
        "codigo": "DESC_DATOS_TERCERO",
        "nombre": "Divulgación de deuda o información sensible a terceros no autorizados",
        "criterios_relacionados": ["PECUF.3"],
        "requiere_rol": "AGENTE",
        "requiere_evidencia": True,
    },
]


def es_cartera_mibanco(cartera: Optional[str]) -> bool:
    texto = str(cartera or "").strip().lower()
    return "mibanco" in texto or "mi banco" in texto


def obtener_pauta_mibanco() -> List[Dict]:
    validar_pauta_mibanco()
    return deepcopy(MIBANCO_PAUTA)


def obtener_criterio_mibanco(codigo: str) -> Optional[Dict]:
    codigo_norm = str(codigo or "").strip().upper()
    for item in MIBANCO_PAUTA:
        if item["codigo_criterio"].upper() == codigo_norm:
            return deepcopy(item)
    return None


def validar_pauta_mibanco() -> None:
    totales = {bloque: 0.0 for bloque in MIBANCO_PESOS_ESPERADOS}
    codigos = set()
    for item in MIBANCO_PAUTA:
        codigo = item.get("codigo_criterio")
        if not codigo:
            raise ValueError("Pauta Mibanco inválida: criterio sin codigo_criterio.")
        if codigo in codigos:
            raise ValueError(f"Pauta Mibanco inválida: código duplicado {codigo}.")
        codigos.add(codigo)
        bloque = item.get("bloque")
        if bloque not in totales:
            raise ValueError(f"Pauta Mibanco inválida: bloque no reconocido {bloque}.")
        totales[bloque] += float(item.get("peso") or 0)
        for campo in (
            "categoria",
            "subcategoria",
            "nombre",
            "detalle",
            "regla_evaluacion",
            "criticidad",
            "fuente_evidencia",
            "regla_aplicabilidad",
        ):
            if not str(item.get(campo) or "").strip():
                raise ValueError(f"Pauta Mibanco inválida: {codigo} sin {campo}.")
    for bloque, esperado in MIBANCO_PESOS_ESPERADOS.items():
        obtenido = round(totales.get(bloque, 0.0), 2)
        if obtenido != esperado:
            raise ValueError(f"Pauta Mibanco inválida: {bloque} suma {obtenido}, esperado {esperado}.")
    total = round(sum(totales.values()), 2)
    if total != 100.0:
        raise ValueError(f"Pauta Mibanco inválida: total {total}, esperado 100.")


def resumen_pesos_mibanco() -> Dict[str, float]:
    validar_pauta_mibanco()
    totales = {bloque: 0.0 for bloque in MIBANCO_PESOS_ESPERADOS}
    for item in MIBANCO_PAUTA:
        totales[item["bloque"]] += float(item["peso"])
    totales["TOTAL"] = round(sum(totales.values()), 2)
    return {key: round(value, 2) for key, value in totales.items()}
