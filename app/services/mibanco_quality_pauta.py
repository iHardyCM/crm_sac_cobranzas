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

MIBANCO_PESOS_ESPERADOS = {
    PENC: 20.0,
    PECUF: 40.0,
    PECN: 25.0,
    PECC: 15.0,
}


MIBANCO_PAUTA: List[Dict] = [
    {
        "codigo_criterio": "PENC.1",
        "bloque": PENC,
        "categoria": "PENC",
        "subcategoria": "Protocolos de Atención",
        "nombre": "Saludo de bienvenida",
        "peso": 1,
        "detalle": "Saluda oportunamente",
        "regla_evaluacion": "Saluda al inicio de la interacción y menciona su nombre de forma clara. La identificación de la entidad se evalúa en Cumplimiento para evitar doble penalización.",
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
        "subcategoria": "Protocolos de Atención",
        "nombre": "Personalización",
        "peso": 1,
        "detalle": "Personaliza de forma adecuada",
        "regla_evaluacion": "Utiliza el nombre o apellido del cliente de manera natural, sin diminutivos, sobrenombres ni excesos de repetición.",
        "criticidad": "ERROR_NO_CRITICO",
        "fuente_evidencia": FUENTE_AUDIO,
        "regla_aplicabilidad": "Aplica cuando el asesor conoce o consulta el nombre del cliente durante la interacción.",
        "puede_descalificar": False,
        "requiere_evidencia": False,
    },
    {
        "codigo_criterio": "PENC.3",
        "bloque": PENC,
        "categoria": "PENC",
        "subcategoria": "Protocolos de Atención",
        "nombre": "Uso correcto de la locución",
        "peso": 1,
        "detalle": "Fluidez, modulación y dicción",
        "regla_evaluacion": "Mantiene tono, velocidad, vocalización y fluidez adecuadas; evita muletillas repetitivas y tecnicismos innecesarios.",
        "criticidad": "ERROR_NO_CRITICO",
        "fuente_evidencia": FUENTE_AUDIO,
        "regla_aplicabilidad": "Aplica cuando el audio permite evaluar locución de forma suficiente.",
        "puede_descalificar": False,
        "requiere_evidencia": False,
    },
    {
        "codigo_criterio": "PENC.4",
        "bloque": PENC,
        "categoria": "PENC",
        "subcategoria": "Protocolos de Atención",
        "nombre": "Claridad del lenguaje oral",
        "peso": 2,
        "detalle": "Explicación clara y coherente",
        "regla_evaluacion": "Se expresa con orden, no se contradice, responde de forma comprensible y transmite seguridad sin generar confusión.",
        "criticidad": "ERROR_NO_CRITICO",
        "fuente_evidencia": FUENTE_TRANSCRIPCION,
        "regla_aplicabilidad": "Aplica cuando el asesor entrega información o explica condiciones durante la llamada.",
        "puede_descalificar": False,
        "requiere_evidencia": False,
    },
    {
        "codigo_criterio": "PENC.5",
        "bloque": PENC,
        "categoria": "PENC",
        "subcategoria": "Protocolos de Atención",
        "nombre": "Lenguaje formal y profesional",
        "peso": 2,
        "detalle": "Uso profesional del lenguaje",
        "regla_evaluacion": "Evita jergas, expresiones coloquiales inapropiadas y términos que resten profesionalismo a la comunicación.",
        "criticidad": "ERROR_NO_CRITICO",
        "fuente_evidencia": FUENTE_TRANSCRIPCION,
        "regla_aplicabilidad": "Aplica a toda interacción audible del asesor.",
        "puede_descalificar": False,
        "requiere_evidencia": False,
    },
    {
        "codigo_criterio": "PENC.6",
        "bloque": PENC,
        "categoria": "PENC",
        "subcategoria": "Protocolos de Atención",
        "nombre": "Despedida adecuada",
        "peso": 1,
        "detalle": "Cierre cordial",
        "regla_evaluacion": "Finaliza la llamada de forma educada y profesional, una vez concluida la gestión.",
        "criticidad": "ERROR_NO_CRITICO",
        "fuente_evidencia": FUENTE_AUDIO,
        "regla_aplicabilidad": "Aplica cuando existe cierre audible de la llamada y no se corta por falla técnica o abandono del cliente.",
        "puede_descalificar": False,
        "requiere_evidencia": False,
    },
    {
        "codigo_criterio": "PENC.7",
        "bloque": PENC,
        "categoria": "PENC",
        "subcategoria": "Gestión de la Llamada",
        "nombre": "Empatía",
        "peso": 6,
        "detalle": "Reconoce la situación del cliente",
        "regla_evaluacion": "Demuestra comprensión de la situación expuesta por el cliente sin asumir, juzgar ni minimizar su dificultad.",
        "criticidad": "ERROR_NO_CRITICO",
        "fuente_evidencia": FUENTE_TRANSCRIPCION,
        "regla_aplicabilidad": "Aplica cuando el cliente expone una situación, dificultad u objeción que amerita reconocimiento.",
        "puede_descalificar": False,
        "requiere_evidencia": False,
    },
    {
        "codigo_criterio": "PENC.8",
        "bloque": PENC,
        "categoria": "PENC",
        "subcategoria": "Gestión de la Llamada",
        "nombre": "Actitud de servicio",
        "peso": 6,
        "detalle": "Disposición y conducción de la atención",
        "regla_evaluacion": "Mantiene cordialidad, disposición para ayudar y evita respuestas que hagan sentir al cliente ignorado, subestimado o tratado de forma mecánica.",
        "criticidad": "ERROR_NO_CRITICO",
        "fuente_evidencia": FUENTE_AUDIO,
        "regla_aplicabilidad": "Aplica a llamadas donde existe interacción suficiente entre asesor y cliente.",
        "puede_descalificar": False,
        "requiere_evidencia": False,
    },
    {
        "codigo_criterio": "PECUF.1",
        "bloque": PECUF,
        "categoria": "PEC",
        "subcategoria": "Precisión de Error Crítico Usuario Final",
        "nombre": "Trato respetuoso",
        "peso": 6,
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
        "nombre": "Continuidad de la llamada",
        "peso": 4,
        "detalle": "No corta ni induce el corte",
        "regla_evaluacion": "No finaliza deliberadamente la llamada ni deja al cliente sin atención para provocar el corte. Se exceptúan fallas evidentes de conectividad.",
        "criticidad": "ERROR_CRITICO_USUARIO_FINAL",
        "fuente_evidencia": FUENTE_AUDIO,
        "regla_aplicabilidad": "Aplica cuando la llamada tiene desarrollo suficiente para evaluar continuidad.",
        "puede_descalificar": False,
        "requiere_evidencia": True,
    },
    {
        "codigo_criterio": "PECUF.3",
        "bloque": PECUF,
        "categoria": "PEC",
        "subcategoria": "Precisión de Error Crítico Usuario Final",
        "nombre": "Validación del cliente y de la información",
        "peso": 4,
        "detalle": "Confirma los datos necesarios",
        "regla_evaluacion": "Valida la información requerida antes de brindar datos sensibles o ejecutar acciones, evitando solicitar información innecesaria.",
        "criticidad": "ERROR_CRITICO_USUARIO_FINAL",
        "fuente_evidencia": FUENTE_TRANSCRIPCION,
        "regla_aplicabilidad": "Aplica cuando el asesor expone datos sensibles, confirma identidad o ejecuta acciones que requieren validación.",
        "puede_descalificar": True,
        "requiere_evidencia": True,
    },
    {
        "codigo_criterio": "PECUF.4",
        "bloque": PECUF,
        "categoria": "PEC",
        "subcategoria": "Precisión de Error Crítico Usuario Final",
        "nombre": "Sondeo y diagnóstico",
        "peso": 6,
        "detalle": "Identifica causa y capacidad de pago",
        "regla_evaluacion": "Realiza preguntas de diagnóstico y seguimiento para comprender la causa del no pago, intención y capacidad, sin convertir el sondeo en un interrogatorio.",
        "criticidad": "ERROR_CRITICO_USUARIO_FINAL",
        "fuente_evidencia": FUENTE_TRANSCRIPCION,
        "regla_aplicabilidad": "Aplica cuando existe contacto con el titular o interlocutor autorizado y objetivo de cobranza.",
        "puede_descalificar": False,
        "requiere_evidencia": True,
    },
    {
        "codigo_criterio": "PECUF.5",
        "bloque": PECUF,
        "categoria": "PEC",
        "subcategoria": "Precisión de Error Crítico Usuario Final",
        "nombre": "Negociación escalonada",
        "peso": 8,
        "detalle": "Propone alternativas orientadas al pago",
        "regla_evaluacion": "Construye una propuesta acorde con el diagnóstico, presenta alternativas válidas y busca una acción concreta de pago dentro de las opciones autorizadas.",
        "criticidad": "ERROR_CRITICO_USUARIO_FINAL",
        "fuente_evidencia": FUENTE_TRANSCRIPCION,
        "regla_aplicabilidad": "Aplica cuando la llamada genera oportunidad real de gestionar pago, abono, convenio o alternativa autorizada.",
        "puede_descalificar": False,
        "requiere_evidencia": True,
    },
    {
        "codigo_criterio": "PECUF.6",
        "bloque": PECUF,
        "categoria": "PEC",
        "subcategoria": "Precisión de Error Crítico Usuario Final",
        "nombre": "Manejo de objeciones",
        "peso": 4,
        "detalle": "Argumenta según la objeción",
        "regla_evaluacion": "Responde con argumentos pertinentes y veraces. Solo aplica cuando el cliente presenta una objeción; si no ocurre, debe marcarse como No Aplica.",
        "criticidad": "ERROR_CRITICO_USUARIO_FINAL",
        "fuente_evidencia": FUENTE_TRANSCRIPCION,
        "regla_aplicabilidad": "Aplica únicamente si el cliente presenta objeción, rechazo, imposibilidad, duda relevante o restricción económica.",
        "puede_descalificar": False,
        "requiere_evidencia": True,
    },
    {
        "codigo_criterio": "PECUF.7",
        "bloque": PECUF,
        "categoria": "PEC",
        "subcategoria": "Precisión de Error Crítico Usuario Final",
        "nombre": "Resolución de consultas",
        "peso": 3,
        "detalle": "Aclara dudas relacionadas con la gestión",
        "regla_evaluacion": "Responde correctamente las consultas del cliente o indica el canal/proceso correspondiente cuando la solución no depende del asesor.",
        "criticidad": "ERROR_CRITICO_USUARIO_FINAL",
        "fuente_evidencia": FUENTE_TRANSCRIPCION,
        "regla_aplicabilidad": "Aplica cuando el cliente formula una consulta o duda relacionada con la gestión.",
        "puede_descalificar": False,
        "requiere_evidencia": True,
    },
    {
        "codigo_criterio": "PECUF.8",
        "bloque": PECUF,
        "categoria": "PEC",
        "subcategoria": "Precisión de Error Crítico Usuario Final",
        "nombre": "Tiempo de espera",
        "peso": 1,
        "detalle": "Gestiona pausas justificadas",
        "regla_evaluacion": "Evita esperas innecesarias. Si requiere más tiempo para consultar información, informa al cliente y retoma la interacción oportunamente.",
        "criticidad": "ERROR_CRITICO_USUARIO_FINAL",
        "fuente_evidencia": FUENTE_AUDIO,
        "regla_aplicabilidad": "Aplica cuando existen pausas, silencios o esperas atribuibles al asesor.",
        "puede_descalificar": False,
        "requiere_evidencia": True,
    },
    {
        "codigo_criterio": "PECUF.9",
        "bloque": PECUF,
        "categoria": "PEC",
        "subcategoria": "Precisión de Error Crítico Usuario Final",
        "nombre": "Uso correcto del aplicativo",
        "peso": 1,
        "detalle": "Consulta y utiliza la información disponible",
        "regla_evaluacion": "Emplea correctamente la información de los aplicativos autorizados y no interpreta ni comunica datos del sistema de manera errónea.",
        "criticidad": "ERROR_CRITICO_USUARIO_FINAL",
        "fuente_evidencia": FUENTE_MULTIFUENTE,
        "regla_aplicabilidad": "Aplica cuando se requiere contrastar información comunicada con aplicativos autorizados.",
        "puede_descalificar": False,
        "requiere_evidencia": True,
    },
    {
        "codigo_criterio": "PECUF.10",
        "bloque": PECUF,
        "categoria": "PEC",
        "subcategoria": "Precisión de Error Crítico Usuario Final",
        "nombre": "Escucha activa",
        "peso": 3,
        "detalle": "Escucha, comprende y confirma",
        "regla_evaluacion": "Evita interrupciones inoportunas, comprende lo expresado por el cliente y realiza preguntas de confirmación cuando la información no es clara.",
        "criticidad": "ERROR_CRITICO_USUARIO_FINAL",
        "fuente_evidencia": FUENTE_AUDIO,
        "regla_aplicabilidad": "Aplica cuando el cliente entrega información, objeta, consulta o requiere comprensión del asesor.",
        "puede_descalificar": False,
        "requiere_evidencia": True,
    },
    {
        "codigo_criterio": "PECN.1",
        "bloque": PECN,
        "categoria": "PEC",
        "subcategoria": "Precisión de Error Crítico del Negocio",
        "nombre": "Imagen de la empresa",
        "peso": 2,
        "detalle": "Protege la imagen de Mibanco",
        "regla_evaluacion": "No desacredita a Mibanco, a sus colaboradores, áreas, procesos o canales; tampoco responsabiliza a terceros para justificar una mala gestión.",
        "criticidad": "ERROR_CRITICO_NEGOCIO",
        "fuente_evidencia": FUENTE_TRANSCRIPCION,
        "regla_aplicabilidad": "Aplica a toda referencia del asesor sobre Mibanco, sus canales, colaboradores o procesos.",
        "puede_descalificar": False,
        "requiere_evidencia": True,
    },
    {
        "codigo_criterio": "PECN.2",
        "bloque": PECN,
        "categoria": "PEC",
        "subcategoria": "Precisión de Error Crítico del Negocio",
        "nombre": "Precisión de la información de la deuda",
        "peso": 5,
        "detalle": "Comunica información financiera exacta",
        "regla_evaluacion": "Brinda únicamente datos vigentes y verificables: deuda, días de mora, producto, cuota u otros conceptos que correspondan al caso.",
        "criticidad": "ERROR_CRITICO_NEGOCIO",
        "fuente_evidencia": FUENTE_MULTIFUENTE,
        "regla_aplicabilidad": "Aplica cuando el asesor comunica deuda, mora, producto, cuota, monto u otros datos financieros.",
        "puede_descalificar": False,
        "requiere_evidencia": True,
    },
    {
        "codigo_criterio": "PECN.3",
        "bloque": PECN,
        "categoria": "PEC",
        "subcategoria": "Precisión de Error Crítico del Negocio",
        "nombre": "Aplicación correcta de campañas o convenios",
        "peso": 5,
        "detalle": "Ofrece condiciones autorizadas",
        "regla_evaluacion": "Informa campañas, descuentos, convenios o alternativas exactamente según las condiciones vigentes y sin crear beneficios no autorizados.",
        "criticidad": "ERROR_CRITICO_NEGOCIO",
        "fuente_evidencia": FUENTE_CAMPANIA,
        "regla_aplicabilidad": "Aplica cuando el asesor comunica campañas, descuentos, convenios o beneficios condicionados.",
        "puede_descalificar": False,
        "requiere_evidencia": True,
    },
    {
        "codigo_criterio": "PECN.4",
        "bloque": PECN,
        "categoria": "PEC",
        "subcategoria": "Precisión de Error Crítico del Negocio",
        "nombre": "Formalización del acuerdo en sistema",
        "peso": 4,
        "detalle": "Registra correctamente la promesa o acuerdo",
        "regla_evaluacion": "Registra monto, fecha, cuota/condición y demás datos exigidos. Este criterio evalúa el registro; la confirmación verbal al cliente se evalúa en PECC.",
        "criticidad": "ERROR_CRITICO_NEGOCIO",
        "fuente_evidencia": FUENTE_SISTEMA,
        "regla_aplicabilidad": "Aplica cuando existe promesa, compromiso, convenio o acuerdo que debe registrarse.",
        "puede_descalificar": False,
        "requiere_evidencia": True,
    },
    {
        "codigo_criterio": "PECN.5",
        "bloque": PECN,
        "categoria": "PEC",
        "subcategoria": "Precisión de Error Crítico del Negocio",
        "nombre": "Tipificación de la gestión",
        "peso": 3,
        "detalle": "Registra el resultado real de la llamada",
        "regla_evaluacion": "La tipificación debe reflejar lo que realmente ocurrió. No convierte intención, consulta o posibilidad en una promesa de pago inexistente.",
        "criticidad": "ERROR_CRITICO_NEGOCIO",
        "fuente_evidencia": FUENTE_TIPIFICACION,
        "regla_aplicabilidad": "Aplica cuando existe tipificación o resultado de gestión registrado para la llamada.",
        "puede_descalificar": False,
        "requiere_evidencia": True,
    },
    {
        "codigo_criterio": "PECN.6",
        "bloque": PECN,
        "categoria": "PEC",
        "subcategoria": "Precisión de Error Crítico del Negocio",
        "nombre": "Actualización de datos en CRM",
        "peso": 3,
        "detalle": "Actualiza datos solo cuando corresponde",
        "regla_evaluacion": "Actualiza teléfonos, datos de contacto o estatus únicamente con información válida y confirmada, evitando modificaciones erróneas.",
        "criticidad": "ERROR_CRITICO_NEGOCIO",
        "fuente_evidencia": FUENTE_CRM,
        "regla_aplicabilidad": "Aplica cuando el asesor recibe, confirma o modifica datos de contacto, estado o información del cliente.",
        "puede_descalificar": False,
        "requiere_evidencia": True,
    },
    {
        "codigo_criterio": "PECN.7",
        "bloque": PECN,
        "categoria": "PEC",
        "subcategoria": "Precisión de Error Crítico del Negocio",
        "nombre": "Trazabilidad y evidencia de la gestión",
        "peso": 3,
        "detalle": "Deja registro suficiente y consistente",
        "regla_evaluacion": "Los comentarios, registros y evidencias deben permitir reconstruir la gestión y ser consistentes con lo conversado y con la tipificación seleccionada.",
        "criticidad": "ERROR_CRITICO_NEGOCIO",
        "fuente_evidencia": FUENTE_MULTIFUENTE,
        "regla_aplicabilidad": "Aplica cuando existe registro de gestión disponible para contrastar con la llamada.",
        "puede_descalificar": False,
        "requiere_evidencia": True,
    },
    {
        "codigo_criterio": "PECC.1",
        "bloque": PECC,
        "categoria": "PEC",
        "subcategoria": "Precisión de Error Crítico de Cumplimiento",
        "nombre": "Identificación del asesor y de la entidad",
        "peso": 3,
        "detalle": "Se identifica correctamente",
        "regla_evaluacion": "Menciona su nombre y la entidad/cartera que representa. No brinda una identidad, cargo o representación falsa.",
        "criticidad": "ERROR_CRITICO_CUMPLIMIENTO",
        "fuente_evidencia": FUENTE_AUDIO,
        "regla_aplicabilidad": "Aplica a llamadas donde existe apertura audible del asesor.",
        "puede_descalificar": False,
        "requiere_evidencia": True,
    },
    {
        "codigo_criterio": "PECC.2",
        "bloque": PECC,
        "categoria": "PEC",
        "subcategoria": "Precisión de Error Crítico de Cumplimiento",
        "nombre": "Información veraz y no intimidatoria",
        "peso": 4,
        "detalle": "No amenaza ni exagera consecuencias",
        "regla_evaluacion": "No comunica acciones inexistentes, no utiliza coerción y no presenta consecuencias legales, judiciales o crediticias de forma falsa o exagerada. Amenazas graves pueden activar descalificación.",
        "criticidad": "ERROR_CRITICO_CUMPLIMIENTO",
        "fuente_evidencia": FUENTE_TRANSCRIPCION,
        "regla_aplicabilidad": "Aplica cuando el asesor comunica consecuencias, condiciones, restricciones, gestiones posteriores o información normativa.",
        "puede_descalificar": True,
        "requiere_evidencia": True,
    },
    {
        "codigo_criterio": "PECC.3",
        "bloque": PECC,
        "categoria": "PEC",
        "subcategoria": "Precisión de Error Crítico de Cumplimiento",
        "nombre": "Protección de datos y confidencialidad",
        "peso": 4,
        "detalle": "Protege la información del cliente",
        "regla_evaluacion": "No divulga la condición de deuda ni información financiera a terceros no autorizados y utiliza los datos únicamente para la finalidad permitida. Una vulneración grave puede activar descalificación.",
        "criticidad": "ERROR_CRITICO_CUMPLIMIENTO",
        "fuente_evidencia": FUENTE_AUDIO,
        "regla_aplicabilidad": "Aplica cuando se conversa con titular, tercero, familiar, referencia, aval o interlocutor no plenamente validado.",
        "puede_descalificar": True,
        "requiere_evidencia": True,
    },
    {
        "codigo_criterio": "PECC.4",
        "bloque": PECC,
        "categoria": "PEC",
        "subcategoria": "Precisión de Error Crítico de Cumplimiento",
        "nombre": "Validación verbal del acuerdo",
        "peso": 4,
        "detalle": "Confirma las condiciones antes del cierre",
        "regla_evaluacion": "Resume como mínimo monto, fecha y medio/forma de pago, además de las condiciones relevantes. No mezcla este criterio con el registro en sistema para evitar doble penalización.",
        "criticidad": "ERROR_CRITICO_CUMPLIMIENTO",
        "fuente_evidencia": FUENTE_TRANSCRIPCION,
        "regla_aplicabilidad": "Aplica cuando existe promesa, compromiso, abono, convenio o acuerdo verbal.",
        "puede_descalificar": False,
        "requiere_evidencia": True,
    },
]


MIBANCO_REGLAS_DESCALIFICACION = [
    {
        "codigo": "DESC_AMENAZA_COACCION",
        "nombre": "Amenaza o coacción grave",
        "criterios_relacionados": ["PECC.2"],
        "requiere_rol": "AGENTE",
        "requiere_evidencia": True,
    },
    {
        "codigo": "DESC_DATOS_TERCERO",
        "nombre": "Divulgación de deuda o información sensible a terceros no autorizados",
        "criterios_relacionados": ["PECC.3", "PECUF.3"],
        "requiere_rol": "AGENTE",
        "requiere_evidencia": True,
    },
    {
        "codigo": "DESC_AGRESION_INSULTO",
        "nombre": "Insulto, agresión o humillación grave",
        "criterios_relacionados": ["PECUF.1"],
        "requiere_rol": "AGENTE",
        "requiere_evidencia": True,
    },
    {
        "codigo": "DESC_FALSIFICACION",
        "nombre": "Falsificación deliberada de información",
        "criterios_relacionados": ["PECC.2", "PECN.2", "PECN.3"],
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
