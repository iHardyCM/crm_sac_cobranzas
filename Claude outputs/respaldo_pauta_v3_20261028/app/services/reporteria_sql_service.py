"""
Reporteria del Centro de Calidad leida desde las tablas (fuente SQL).

POR QUE EXISTE
La reporteria anterior (ia_audio_service.obtener_reporteria_calidad) toma el
JSON de cada evaluacion y le vuelve a aplicar las guardas de la pauta en CADA
lectura. Con 96 evaluaciones tarda 10-21 s y crece con cada una nueva. Ademas,
si una regla cambia, las notas por criterio de llamadas antiguas cambian en
silencio al volver a leerlas.

Esta version lee lo que ya quedo guardado:
  - ia_feedback_llamadas            la llamada, su nota IA y su nota calibrada.
  - CRM_IA_EVALUACION_CRITERIO      el resultado de la IA por criterio, escrito
                                    una sola vez al terminar el analisis
                                    (inmutable).
  - CRM_IA_CALIBRACION_CRITERIO     las correcciones de Calidad, solo PUBLICADAS.

REGLA DEL RESULTADO VIGENTE POR CRITERIO (la misma de recalcular_score_calibrado)
  Si hay una calibracion PUBLICADA con accion CORREGIR -> resultado_esperado.
  En cualquier otro caso                              -> resultado_ia.
  Puntos: el peso si el resultado vigente es CUMPLE; 0 en otro caso.
  (Para lo no calibrado se respeta puntaje_obtenido tal como lo guardo la IA.)

La forma de la respuesta es la misma que la de la reporteria anterior, para que
la pagina no cambie. Las listas agregadas (segmentos, brechas, carteras...) van
vacias: la pagina v2 calcula todo desde "detalle".

No recalcula guardas ni reglas de negocio: si una llamada no tiene filas en
CRM_IA_EVALUACION_CRITERIO, se entrega sin criterios y se cuenta en
"llamadas_sin_criterios". No se completa con el JSON: mezclar dos fuentes es
justo lo que esta version quiere evitar.
"""

from __future__ import annotations

import json
import time
from typing import Dict, List, Optional

from sqlalchemy import bindparam, text

from app.core.db_siscob import engine_siscob
from app.services.ia_audio_service import limpiar_texto, score_vigente_llamada, serializar

ESTADOS_TEXTO = {
    "CUMPLE": "Cumple",
    "NO_CUMPLE": "No cumple",
    "NO_APLICA": "No aplica",
    "NO_EVALUABLE": "No evaluable",
    "REQUIERE_REVISION": "Requiere revisión",
}


def _contar_lista_json(valor) -> int:
    if not valor:
        return 0
    if isinstance(valor, list):
        return len(valor)
    try:
        dato = json.loads(valor)
        return len(dato) if isinstance(dato, list) else 0
    except (TypeError, ValueError):
        return 0


def obtener_reporteria_sql(limit: int = 300, supervisor: Optional[str] = None) -> Dict:
    t0 = time.perf_counter()
    filtros = ["estado = 'FINALIZADO'"]
    params: Dict = {"limit": int(limit)}
    if limpiar_texto(supervisor):
        filtros.append("LTRIM(RTRIM(ISNULL(supervisor, ''))) = :supervisor")
        params["supervisor"] = limpiar_texto(supervisor)

    sql_llamadas = text("""
        SELECT TOP (:limit)
            id_feedback, archivo_nombre, cartera, supervisor, agente,
            score_calidad, score_calidad_ia, score_supervisor, score_final, score_normalizado,
            score_calibrado, origen_score,
            nivel_riesgo, tipo_llamada, requiere_revision_humana,
            fecha_creacion, fecha_llamada, comentario_supervisor, comentario_feedback,
            resultado_gestion, nivel_oportunidad_mejora, puntos_criticos,
            estado_revision, falta_anulante, error_critico,
            estado_recalibracion, estado_coaching, estado_feedback,
            requiere_feedback, requiere_coaching, fecha_coaching
        FROM CobAuto.dbo.ia_feedback_llamadas WITH(NOLOCK)
        WHERE {where_sql}
        ORDER BY fecha_creacion DESC, id_feedback DESC
    """.format(where_sql=" AND ".join(filtros)))

    sql_criterios = text("""
        SELECT E.id_feedback, E.codigo_bloque, E.nombre_bloque, E.codigo_criterio,
               E.nombre_criterio, E.tipo_criterio, E.peso, E.resultado_ia, E.puntaje_obtenido,
               C.accion AS accion_calibracion, C.resultado_esperado
        FROM CobAuto.dbo.CRM_IA_EVALUACION_CRITERIO E WITH(NOLOCK)
        LEFT JOIN CobAuto.dbo.CRM_IA_CALIBRACION_CRITERIO C WITH(NOLOCK)
               ON C.id_evaluacion_criterio = E.id_evaluacion_criterio
              AND C.estado = 'PUBLICADA'
        WHERE E.id_feedback IN :ids
        ORDER BY E.id_feedback, E.codigo_criterio
    """).bindparams(bindparam("ids", expanding=True))

    with engine_siscob.connect() as conn:
        llamadas = conn.execute(sql_llamadas, params).mappings().all()
        t_llamadas = time.perf_counter()
        ids = [int(r["id_feedback"]) for r in llamadas]
        criterios_por_id: Dict[int, List[Dict]] = {i: [] for i in ids}
        if ids:
            # SQL Server admite ~2100 parametros por consulta: se parte en bloques.
            for inicio in range(0, len(ids), 900):
                for fila in conn.execute(sql_criterios, {"ids": ids[inicio:inicio + 900]}).mappings():
                    criterios_por_id[int(fila["id_feedback"])].append(dict(fila))
    t_criterios = time.perf_counter()

    detalle = []
    scores = []
    sin_criterios = 0
    for row in llamadas:
        row = dict(row)
        score = score_vigente_llamada(row)
        if score is not None:
            scores.append(score)
        items = []
        for fila in criterios_por_id.get(int(row["id_feedback"]), []):
            peso = float(fila["peso"] or 0)
            resultado_ia = str(fila["resultado_ia"] or "").upper()
            corregido = str(fila.get("accion_calibracion") or "").upper() == "CORREGIR" and fila.get("resultado_esperado")
            vigente = str(fila["resultado_esperado"]).upper() if corregido else resultado_ia
            if corregido:
                puntos = peso if vigente == "CUMPLE" else 0.0
            else:
                puntos = float(fila["puntaje_obtenido"] or 0)
            texto = ESTADOS_TEXTO.get(vigente, "Requiere revisión")
            items.append({
                "codigo_criterio": fila["codigo_criterio"],
                "item": fila["nombre_criterio"],
                "nombre": fila["nombre_criterio"],
                "factor_sgc": fila["nombre_criterio"],
                "bloque": fila["codigo_bloque"],
                "bloque_nombre": fila["nombre_bloque"],
                "segmento": fila["nombre_bloque"],
                "tipo_criterio": fila["tipo_criterio"],
                "peso": peso,
                "nota": puntos,
                "estado": vigente,
                "resultado": texto,
                "calificacion": texto,
                "resultado_ia": resultado_ia,
                "calibrado": bool(corregido),
            })
        if not items:
            sin_criterios += 1
        detalle.append({
            "id_feedback": row["id_feedback"],
            "fecha_creacion": serializar({"f": row.get("fecha_creacion")})["f"],
            "fecha_llamada": serializar({"f": row.get("fecha_llamada")})["f"],
            "archivo_nombre": row.get("archivo_nombre"),
            "cartera": str(row.get("cartera") or "Sin cartera"),
            "agente": str(row.get("agente") or "Sin agente asociado"),
            "supervisor": str(row.get("supervisor") or "Sin supervisor"),
            "evaluacion_calidad_lista": items,
            "fuente_criterios": "TABLA" if items else "SIN_DETALLE",
            "score_calidad": score,
            "score_final": score,
            "score_normalizado": score,
            "evaluable": score is not None,
            "score_ia": float(row["score_final"]) if row.get("score_final") is not None else None,
            "score_calidad_ia": float(row["score_calidad_ia"]) if row.get("score_calidad_ia") is not None else None,
            "score_supervisor": float(row["score_supervisor"]) if row.get("score_supervisor") is not None else None,
            "score_calibrado": float(row["score_calibrado"]) if row.get("score_calibrado") is not None else None,
            "origen_score": str(row.get("origen_score") or "IA"),
            "nivel_riesgo": row.get("nivel_riesgo") or row.get("nivel_oportunidad_mejora"),
            "nivel_oportunidad_mejora": row.get("nivel_oportunidad_mejora"),
            "tipo_llamada": row.get("tipo_llamada"),
            "requiere_revision_humana": bool(row.get("requiere_revision_humana")),
            "resultado_gestion": row.get("resultado_gestion"),
            "total_puntos_criticos": _contar_lista_json(row.get("puntos_criticos")),
            "observacion_supervisor": row.get("comentario_feedback") or row.get("comentario_supervisor"),
            "estado_revision": row.get("estado_revision"),
            "falta_anulante": bool(row.get("falta_anulante")),
            "error_critico": bool(row.get("error_critico")),
            "estado_recalibracion": row.get("estado_recalibracion") or "SIN_APELACION",
            "estado_coaching": row.get("estado_coaching") or "PENDIENTE",
            "estado_feedback": row.get("estado_feedback"),
            "requiere_feedback": bool(row.get("requiere_feedback")),
            "requiere_coaching": bool(row.get("requiere_coaching")),
            "fecha_coaching": serializar({"f": row.get("fecha_coaching")})["f"],
            "brechas_items": [],
            "notas_segmento": {},
            "resumen_sgc": {},
        })

    return {
        "fuente": "SQL",
        "total_audios": len(detalle),
        "score_promedio": round(sum(scores) / len(scores), 2) if scores else None,
        "audios_con_score": len(scores),
        "audios_sin_score": len(detalle) - len(scores),
        "llamadas_sin_criterios": sin_criterios,
        "items_nota_cero": 0,
        "segmentos": [], "brechas": [], "sgc_grupos": [], "sgc_factores": [],
        "carteras": [], "agentes": [], "semanas": [],
        "detalle": detalle,
        "tiempos": {
            "llamadas_s": round(t_llamadas - t0, 3),
            "criterios_s": round(t_criterios - t_llamadas, 3),
            "total_s": round(time.perf_counter() - t0, 3),
        },
    }
