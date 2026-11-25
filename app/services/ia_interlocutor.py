# ia_interlocutor.py
"""Interlocutor de una llamada analizada: TITULAR o TERCERO (pedido de Calidad, 16/11/2026).

Se decide con lo que ya quedó guardado del análisis (los segmentos de la transcripción con su rol y el tipo de
contacto que devolvió la IA). No se vuelve a leer el audio ni se llama a la API: sirve igual para las
llamadas nuevas y para las ya evaluadas. No cambia la nota: es una etiqueta descriptiva.

Reglas, en orden:
  1. Si la separación de voces (agente / cliente) no es confiable, no se adivina: SIN_IDENTIFICAR.
  2. El cliente dice que no es el titular o cuál es su vínculo ("soy su esposa", "no se encuentra",
     "no vive aquí", "yo le aviso"...) -> TERCERO. Si después el agente pregunta por el titular y alguien
     confirma ("¿la señora Ana?" - "sí, dígame"), le pasaron la llamada al titular -> TITULAR.
  3. El agente pregunta por el titular y el cliente confirma ("sí", "dígame", "soy yo") -> TITULAR.
  4. Sin frase clara: el tipo de contacto de la IA ("Tercero" -> TERCERO; "Contacto efectivo" -> TITULAR).
  5. Si nada de lo anterior: SIN_IDENTIFICAR.
Cada resultado guarda su evidencia (la frase o el tipo de contacto) y su origen (REGLA o IA).
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from app.core.db_siscob import engine_siscob
from app.services.ia_analysis_service import (
    cobertura_roles_suficiente_v3,
    limpiar_key_texto,
    normalizar_hablante_v2,
    normalizar_interlocutores_v2,
)

logger = logging.getLogger(__name__)

TITULAR, TERCERO, SIN_IDENTIFICAR = "TITULAR", "TERCERO", "SIN_IDENTIFICAR"
ETIQUETAS = {TITULAR: "Titular", TERCERO: "Tercero", SIN_IDENTIFICAR: "Sin identificar"}

FRASES_TERCERO = (
    "soy su esposa", "soy su esposo", "soy su pareja", "soy su conviviente", "soy su mama", "soy su papa",
    "soy su madre", "soy su padre", "soy su hijo", "soy su hija", "soy su hermano", "soy su hermana",
    "soy su sobrino", "soy su sobrina", "soy su nuera", "soy su yerno", "soy su cunado", "soy su cunada",
    "soy su tio", "soy su tia", "soy su abuela", "soy su abuelo", "soy su nieto", "soy su nieta",
    "soy su vecino", "soy su vecina", "soy familiar", "soy su familiar", "soy su amiga", "soy su amigo",
    "no soy el titular", "no soy la titular", "no soy el senor", "no soy la senora", "no soy yo",
    "no soy esa persona", "no se encuentra", "no esta en casa", "no esta aqui", "ya no vive", "no vive aqui",
    "no la conozco", "no lo conozco", "le doy el mensaje", "le dejo el mensaje", "le paso el recado",
    "le paso el mensaje", "numero equivocado", "se equivoco de numero",
)
RESPUESTAS_TITULAR = {"si", "digame", "que digame", "soy yo", "ella habla", "el habla", "con ella", "con el",
                      "si soy yo", "si digame", "si con ella", "si con el", "aja", "si ella habla", "si el habla"}


def _rol(segmento: Dict) -> str:
    return normalizar_hablante_v2(segmento.get("hablante") or segmento.get("rol"))


def _texto(segmento: Dict) -> str:
    return limpiar_key_texto(segmento.get("texto") or segmento.get("texto_original") or "")


def _cita(segmento: Dict) -> str:
    original = str(segmento.get("texto_original") or segmento.get("texto") or "").strip()
    return f"{'Cliente' if _rol(segmento) == 'CLIENTE' else 'Agente'}: \"{original[:300]}\""


def _pregunta_por_titular(texto: str) -> bool:
    return (texto.endswith("por favor") or "me podria comunicar" in texto or "con la senora" in texto
            or "con el senor" in texto or "con la senorita" in texto or "hablo con" in texto
            or "se encuentra el senor" in texto or "se encuentra la senora" in texto)


def _confirma(texto: str) -> bool:
    if texto in RESPUESTAS_TITULAR:
        return True
    palabras = texto.split()
    return bool(palabras) and (palabras[0] in {"si", "digame", "aja"} or "soy yo" in texto) and "no soy" not in texto


def clasificar_interlocutor(segmentos: List[Dict], tipo_contacto_ia: Optional[str] = None) -> Dict[str, str]:
    segmentos = [s for s in (segmentos or []) if isinstance(s, dict)]
    if not segmentos or not cobertura_roles_suficiente_v3(segmentos):
        return {"interlocutor": SIN_IDENTIFICAR, "origen": "REGLA",
                "evidencia": "La separación de voces de la llamada no es confiable: no se identifica al interlocutor."}

    frases = [limpiar_key_texto(f) for f in FRASES_TERCERO]
    idx_tercero, seg_tercero = None, None
    for i, s in enumerate(segmentos):
        if _rol(s) == "CLIENTE" and any(f and f in _texto(s) for f in frases):
            idx_tercero, seg_tercero = i, s
            break

    confirmaciones = []   # (índice de la respuesta, segmento de la respuesta)
    for i, s in enumerate(segmentos):
        if _rol(s) != "AGENTE" or not _pregunta_por_titular(_texto(s)):
            continue
        for j in range(i + 1, min(i + 4, len(segmentos))):
            sig = segmentos[j]
            if _rol(sig) == "CLIENTE":
                if _confirma(_texto(sig)):
                    confirmaciones.append((j, sig))
                break

    if seg_tercero is not None:
        despues = [c for c in confirmaciones if c[0] > idx_tercero]
        if despues:
            return {"interlocutor": TITULAR, "origen": "REGLA",
                    "evidencia": f"Contestó un tercero y luego el titular: {_cita(seg_tercero)} → {_cita(despues[0][1])}"}
        return {"interlocutor": TERCERO, "origen": "REGLA", "evidencia": _cita(seg_tercero)}
    if confirmaciones:
        return {"interlocutor": TITULAR, "origen": "REGLA", "evidencia": _cita(confirmaciones[0][1])}

    tipo = limpiar_key_texto(tipo_contacto_ia or "")
    if "tercero" in tipo:
        return {"interlocutor": TERCERO, "origen": "IA", "evidencia": f"Tipo de contacto según la IA: {tipo_contacto_ia}"}
    if "efectivo" in tipo and "no efectivo" not in tipo:
        return {"interlocutor": TITULAR, "origen": "IA", "evidencia": f"Tipo de contacto según la IA: {tipo_contacto_ia}"}
    return {"interlocutor": SIN_IDENTIFICAR, "origen": "REGLA",
            "evidencia": "No hay una frase que confirme quién contestó."}


def segmentos_de_registro(resumen_sgc: Any, transcripcion: Optional[str]) -> List[Dict]:
    """Segmentos guardados de una llamada ya analizada (los mismos que muestra la ficha)."""
    datos = resumen_sgc
    if isinstance(datos, str):
        try:
            datos = json.loads(datos)
        except (TypeError, ValueError):
            datos = {}
    copc = datos.get("json_copc_v2") if isinstance(datos, dict) else None
    if isinstance(copc, dict):
        inter = copc.get("interlocutores") if isinstance(copc.get("interlocutores"), dict) else {}
        segmentos = inter.get("segmentos") if isinstance(inter.get("segmentos"), list) else []
        if segmentos:
            return segmentos
        inter = normalizar_interlocutores_v2(copc, transcripcion or "")
        return inter.get("segmentos") if isinstance(inter, dict) else []
    inter = normalizar_interlocutores_v2({}, transcripcion or "")
    return inter.get("segmentos") if isinstance(inter, dict) else []


def guardar_interlocutor(conn, id_feedback: int, resultado: Dict[str, str]) -> None:
    conn.execute(text("""
        UPDATE CobAuto.dbo.ia_feedback_llamadas
        SET interlocutor = :i, interlocutor_origen = :o, interlocutor_evidencia = :e
        WHERE id_feedback = :id"""),
        {"i": resultado["interlocutor"], "o": resultado["origen"], "e": (resultado.get("evidencia") or "")[:500],
         "id": int(id_feedback)})


def rellenar_interlocutores(solo_faltantes: bool = True, limite: int = 5000) -> Dict[str, int]:
    """Etiqueta las llamadas ya analizadas con lo guardado (sin volver a leer el audio ni llamar a la IA)."""
    condicion = "AND interlocutor IS NULL" if solo_faltantes else ""
    with engine_siscob.connect() as conn:
        filas = conn.execute(text(f"""
            SELECT TOP (:n) id_feedback, resumen_sgc, transcripcion, tipo_contacto
            FROM CobAuto.dbo.ia_feedback_llamadas WITH (NOLOCK)
            WHERE estado = 'FINALIZADO' {condicion}
            ORDER BY id_feedback"""), {"n": int(limite)}).mappings().all()
    cuenta = {TITULAR: 0, TERCERO: 0, SIN_IDENTIFICAR: 0, "errores": 0}
    for f in filas:
        try:
            r = clasificar_interlocutor(segmentos_de_registro(f["resumen_sgc"], f["transcripcion"]), f["tipo_contacto"])
            with engine_siscob.begin() as conn:
                guardar_interlocutor(conn, f["id_feedback"], r)
            cuenta[r["interlocutor"]] += 1
        except Exception:
            cuenta["errores"] += 1
            logger.exception("[INTERLOCUTOR] no se pudo etiquetar la llamada %s", f["id_feedback"])
    return cuenta
