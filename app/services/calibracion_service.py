"""Calibracion humana de la evaluacion IA, criterio por criterio.

Reglas de negocio que este modulo sostiene:

1. La evaluacion de la IA es inmutable. Nunca se modifica CRM_IA_EVALUACION_CRITERIO:
   es el registro contra el que se mide la precision del modulo.

2. Solo los criterios con un acto humano explicito -confirmar o corregir- entran al
   denominador de la metrica de precision. Un criterio que nadie reviso es un
   no-dato, no una coincidencia.

3. La accion se refiere al RESULTADO del criterio; la validez de la evidencia es
   independiente. Un criterio puede estar bien resuelto y mal sustentado, y ese
   caso -acertar citando una evidencia que no existe- es justamente el que
   interesa detectar.

4. Solo una calibracion PUBLICADA afecta el score de la llamada. En BORRADOR y
   EN_REVISION el acto se registra pero la nota mostrada sigue siendo la de la IA.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from sqlalchemy import text

from app.core.db_siscob import engine_siscob


ESTADO_BORRADOR = "BORRADOR"
ESTADO_EN_REVISION = "EN_REVISION"
ESTADO_PUBLICADA = "PUBLICADA"
ESTADO_RECHAZADA = "RECHAZADA"

ACCION_CONFIRMAR = "CONFIRMAR"
ACCION_CORREGIR = "CORREGIR"

RESULTADOS_VALIDOS = {"CUMPLE", "NO_CUMPLE", "NO_APLICA", "NO_EVALUABLE"}
EVIDENCIA_VALIDA = {"SI", "NO", "PARCIAL"}

# Estados que suman puntaje. Se mantiene alineado con puntaje_mibanco_pipeline_v3:
# solo CUMPLE otorga el peso del criterio.
ESTADOS_QUE_PUNTUAN = {"CUMPLE"}


def _texto(value, limite: Optional[int] = None) -> Optional[str]:
    texto = str(value or "").strip()
    if not texto:
        return None
    return texto[:limite] if limite else texto


def listar_motivos() -> List[Dict]:
    """Catalogo de motivos activo, con la prueba de decision de cada uno.

    La prueba de decision es lo que mantiene la clasificacion consistente entre
    analistas; la ficha deberia mostrarla al elegir el motivo.
    """
    with engine_siscob.begin() as conn:
        filas = conn.execute(text("""
            SELECT id_motivo, codigo, nombre, descripcion, prueba_decision,
                   categoria, aplica_resultado, aplica_evidencia
            FROM CobAuto.dbo.CRM_IA_CALIBRACION_MOTIVO
            WHERE activo = 1
            ORDER BY orden, id_motivo
        """)).mappings().all()
    salida = []
    for fila in filas:
        item = dict(fila)
        item["aplica_resultado"] = bool(item.get("aplica_resultado"))
        item["aplica_evidencia"] = bool(item.get("aplica_evidencia"))
        salida.append(item)
    return salida


def obtener_calibracion(id_feedback: int) -> Dict:
    """Criterios evaluados de una llamada, con su calibracion vigente si existe."""
    with engine_siscob.begin() as conn:
        criterios = conn.execute(text("""
            SELECT E.id_evaluacion_criterio, E.codigo_bloque, E.nombre_bloque,
                   E.codigo_criterio, E.nombre_criterio, E.peso, E.fuente_evidencia,
                   E.resultado_ia, E.puntaje_obtenido, E.confianza_ia,
                   E.motivo_ia, E.evidencia_texto, E.momento_llamada,
                   C.id_calibracion, C.accion, C.resultado_esperado, C.evidencia_valida,
                   C.id_motivo, M.codigo AS motivo_codigo, M.nombre AS motivo_nombre,
                   C.evidencia_revisor, C.comentario, C.estado AS estado_calibracion,
                   C.creado_por, C.fecha_creacion AS fecha_calibracion
            FROM CobAuto.dbo.CRM_IA_EVALUACION_CRITERIO E
            LEFT JOIN CobAuto.dbo.CRM_IA_CALIBRACION_CRITERIO C
                   ON C.id_evaluacion_criterio = E.id_evaluacion_criterio
                  AND C.estado <> 'RECHAZADA'
            LEFT JOIN CobAuto.dbo.CRM_IA_CALIBRACION_MOTIVO M
                   ON M.id_motivo = C.id_motivo
            WHERE E.id_feedback = :id_feedback
            ORDER BY E.codigo_bloque, E.codigo_criterio
        """), {"id_feedback": id_feedback}).mappings().all()

    data = []
    for fila in criterios:
        item = dict(fila)
        for campo in ("fecha_calibracion",):
            if item.get(campo) is not None:
                item[campo] = item[campo].isoformat()
        item["calibrado"] = item.get("id_calibracion") is not None
        data.append(item)

    revisados = sum(1 for item in data if item["calibrado"])
    return {
        "id_feedback": id_feedback,
        "criterios": data,
        "resumen": {
            "total_criterios": len(data),
            "revisados": revisados,
            "pendientes": len(data) - revisados,
            # El avance es sobre criterios revisados, no sobre criterios corregidos:
            # confirmar tambien es revisar.
            "avance_pct": round((revisados / len(data)) * 100, 1) if data else 0.0,
        },
    }


def guardar_calibracion(
    id_evaluacion_criterio: int,
    *,
    accion: str,
    resultado_esperado: Optional[str] = None,
    evidencia_valida: str = "SI",
    id_motivo: Optional[int] = None,
    evidencia_revisor: Optional[str] = None,
    comentario: Optional[str] = None,
    usuario: Optional[str] = None,
    enviar_a_revision: bool = False,
) -> Dict:
    """Registra el acto humano sobre un criterio. Crea o actualiza el borrador.

    No se permite editar una calibracion ya PUBLICADA: para cambiarla hay que
    rechazarla y calibrar de nuevo, de modo que quede rastro de ambas decisiones.
    """
    accion = str(accion or "").strip().upper()
    if accion not in {ACCION_CONFIRMAR, ACCION_CORREGIR}:
        raise ValueError("La accion debe ser CONFIRMAR o CORREGIR.")

    evidencia_valida = str(evidencia_valida or "").strip().upper()
    if evidencia_valida not in EVIDENCIA_VALIDA:
        raise ValueError("La validez de la evidencia debe ser SI, NO o PARCIAL.")

    if accion == ACCION_CORREGIR:
        resultado_esperado = str(resultado_esperado or "").strip().upper()
        if resultado_esperado not in RESULTADOS_VALIDOS:
            raise ValueError("Una correccion requiere indicar el resultado esperado.")
    else:
        resultado_esperado = None

    # Motivo obligatorio salvo confirmacion limpia: resultado correcto y evidencia
    # que lo sustenta. Cualquier otra combinacion describe una falla y necesita
    # decir cual, o la metrica por motivo no sirve para nada.
    confirmacion_limpia = accion == ACCION_CONFIRMAR and evidencia_valida == "SI"
    if confirmacion_limpia:
        id_motivo = None
    elif not id_motivo:
        raise ValueError("Indica el motivo de la calibracion.")

    estado = ESTADO_EN_REVISION if enviar_a_revision else ESTADO_BORRADOR

    with engine_siscob.begin() as conn:
        evaluacion = conn.execute(text("""
            SELECT id_evaluacion_criterio, id_feedback, codigo_criterio, resultado_ia
            FROM CobAuto.dbo.CRM_IA_EVALUACION_CRITERIO
            WHERE id_evaluacion_criterio = :id_evaluacion_criterio
        """), {"id_evaluacion_criterio": id_evaluacion_criterio}).mappings().first()
        if not evaluacion:
            raise ValueError("El criterio evaluado no existe.")

        vigente = conn.execute(text("""
            SELECT id_calibracion, estado
            FROM CobAuto.dbo.CRM_IA_CALIBRACION_CRITERIO
            WHERE id_evaluacion_criterio = :id_evaluacion_criterio
              AND estado <> 'RECHAZADA'
        """), {"id_evaluacion_criterio": id_evaluacion_criterio}).mappings().first()

        params = {
            "id_evaluacion_criterio": id_evaluacion_criterio,
            "id_feedback": int(evaluacion["id_feedback"]),
            "codigo_criterio": evaluacion["codigo_criterio"],
            "accion": accion,
            "resultado_esperado": resultado_esperado,
            "evidencia_valida": evidencia_valida,
            "id_motivo": id_motivo,
            "evidencia_revisor": _texto(evidencia_revisor),
            "comentario": _texto(comentario),
            "estado": estado,
            "usuario": _texto(usuario, 150),
        }

        if vigente:
            if vigente["estado"] == ESTADO_PUBLICADA:
                raise ValueError(
                    "Esta calibracion ya fue publicada. Rechazala si necesitas corregirla."
                )
            conn.execute(text("""
                UPDATE CobAuto.dbo.CRM_IA_CALIBRACION_CRITERIO
                SET accion = :accion,
                    resultado_esperado = :resultado_esperado,
                    evidencia_valida = :evidencia_valida,
                    id_motivo = :id_motivo,
                    evidencia_revisor = :evidencia_revisor,
                    comentario = :comentario,
                    estado = :estado,
                    actualizado_por = :usuario,
                    fecha_actualizacion = GETDATE()
                WHERE id_calibracion = :id_calibracion
            """), {**params, "id_calibracion": int(vigente["id_calibracion"])})
            id_calibracion = int(vigente["id_calibracion"])
        else:
            resultado = conn.execute(text("""
                INSERT INTO CobAuto.dbo.CRM_IA_CALIBRACION_CRITERIO
                    (id_evaluacion_criterio, id_feedback, codigo_criterio, accion,
                     resultado_esperado, evidencia_valida, id_motivo,
                     evidencia_revisor, comentario, estado, creado_por, actualizado_por)
                OUTPUT INSERTED.id_calibracion
                VALUES
                    (:id_evaluacion_criterio, :id_feedback, :codigo_criterio, :accion,
                     :resultado_esperado, :evidencia_valida, :id_motivo,
                     :evidencia_revisor, :comentario, :estado, :usuario, :usuario)
            """), params)
            id_calibracion = int(resultado.scalar_one())

    return {"ok": True, "id_calibracion": id_calibracion, "estado": estado}


def resolver_calibracion(
    id_calibracion: int,
    *,
    estado: str,
    usuario: Optional[str] = None,
    motivo_rechazo: Optional[str] = None,
) -> Dict:
    """Publica o rechaza una calibracion en revision.

    Publicar es el unico acto que mueve la nota de la llamada.
    """
    estado = str(estado or "").strip().upper()
    if estado not in {ESTADO_PUBLICADA, ESTADO_RECHAZADA}:
        raise ValueError("El estado debe ser PUBLICADA o RECHAZADA.")
    if estado == ESTADO_RECHAZADA and not _texto(motivo_rechazo):
        raise ValueError("Un rechazo necesita motivo.")

    with engine_siscob.begin() as conn:
        actual = conn.execute(text("""
            SELECT id_calibracion, id_feedback, estado
            FROM CobAuto.dbo.CRM_IA_CALIBRACION_CRITERIO
            WHERE id_calibracion = :id_calibracion
        """), {"id_calibracion": id_calibracion}).mappings().first()
        if not actual:
            raise ValueError("La calibracion no existe.")
        if actual["estado"] == ESTADO_PUBLICADA:
            raise ValueError("Esta calibracion ya esta publicada.")

        conn.execute(text("""
            UPDATE CobAuto.dbo.CRM_IA_CALIBRACION_CRITERIO
            SET estado = :estado,
                motivo_rechazo = :motivo_rechazo,
                revisado_por = :usuario,
                fecha_revision = GETDATE(),
                publicado_por = CASE WHEN :estado = 'PUBLICADA' THEN :usuario ELSE publicado_por END,
                fecha_publicacion = CASE WHEN :estado = 'PUBLICADA' THEN GETDATE() ELSE fecha_publicacion END,
                actualizado_por = :usuario,
                fecha_actualizacion = GETDATE()
            WHERE id_calibracion = :id_calibracion
        """), {
            "id_calibracion": id_calibracion,
            "estado": estado,
            "motivo_rechazo": _texto(motivo_rechazo),
            "usuario": _texto(usuario, 150),
        })

    id_feedback = int(actual["id_feedback"])
    recalculo = recalcular_score_calibrado(id_feedback)
    return {"ok": True, "estado": estado, "id_feedback": id_feedback, **recalculo}


def recalcular_score_calibrado(id_feedback: int) -> Dict:
    """Recalcula la nota de la llamada aplicando solo calibraciones PUBLICADAS.

    El score de la IA (score_calidad_ia) no se toca nunca. Si no hay ninguna
    calibracion publicada, score_calibrado queda NULL y la nota vigente sigue
    siendo la de la IA.
    """
    with engine_siscob.begin() as conn:
        filas = conn.execute(text("""
            SELECT E.codigo_criterio, E.peso, E.resultado_ia,
                   C.resultado_esperado, C.accion, C.estado
            FROM CobAuto.dbo.CRM_IA_EVALUACION_CRITERIO E
            LEFT JOIN CobAuto.dbo.CRM_IA_CALIBRACION_CRITERIO C
                   ON C.id_evaluacion_criterio = E.id_evaluacion_criterio
                  AND C.estado = 'PUBLICADA'
            WHERE E.id_feedback = :id_feedback
        """), {"id_feedback": id_feedback}).mappings().all()

        if not filas:
            return {"score_calibrado": None, "publicadas": 0}

        publicadas = sum(1 for fila in filas if fila.get("estado") == ESTADO_PUBLICADA)
        if not publicadas:
            conn.execute(text("""
                UPDATE CobAuto.dbo.ia_feedback_llamadas
                SET score_calibrado = NULL,
                    origen_score = 'IA'
                WHERE id_feedback = :id_feedback
            """), {"id_feedback": id_feedback})
            return {"score_calibrado": None, "publicadas": 0}

        obtenido = 0.0
        peso_aplicable = 0.0
        for fila in filas:
            peso = float(fila.get("peso") or 0)
            # Resultado vigente: el corregido si la correccion esta publicada,
            # el de la IA en cualquier otro caso.
            resultado = fila.get("resultado_ia")
            if fila.get("estado") == ESTADO_PUBLICADA and fila.get("accion") == ACCION_CORREGIR:
                resultado = fila.get("resultado_esperado") or resultado
            resultado = str(resultado or "").upper()

            # NO_APLICA y NO_EVALUABLE salen del denominador: no son incumplimientos.
            if resultado in {"NO_APLICA", "NO_EVALUABLE"}:
                continue
            peso_aplicable += peso
            if resultado in ESTADOS_QUE_PUNTUAN:
                obtenido += peso

        score = round((obtenido / peso_aplicable) * 100, 2) if peso_aplicable else None

        conn.execute(text("""
            UPDATE CobAuto.dbo.ia_feedback_llamadas
            SET score_calibrado = :score,
                origen_score = 'CALIBRACION'
            WHERE id_feedback = :id_feedback
        """), {"id_feedback": id_feedback, "score": score})

    return {
        "score_calibrado": score,
        "publicadas": publicadas,
        "peso_aplicable": round(peso_aplicable, 2),
        "puntaje_obtenido": round(obtenido, 2),
    }


def obtener_precision(
    *,
    cartera: Optional[str] = None,
    id_pauta: Optional[int] = None,
) -> Dict:
    """Precision de la IA por criterio, solo sobre criterios efectivamente revisados.

    Se reportan dos metricas separadas a proposito:
      - precision de resultado: la IA concluyo lo mismo que Calidad.
      - precision de evidencia: ademas lo sustento con una cita valida.
    Fundirlas en un solo porcentaje esconde el caso peligroso, que es acertar el
    resultado citando una evidencia que no existe.
    """
    filtros = ["C.estado IN ('EN_REVISION', 'PUBLICADA')"]
    params: Dict = {}
    if cartera:
        filtros.append("L.cartera = :cartera")
        params["cartera"] = cartera
    if id_pauta:
        filtros.append("E.id_pauta = :id_pauta")
        params["id_pauta"] = id_pauta

    with engine_siscob.begin() as conn:
        filas = conn.execute(text(f"""
            SELECT E.codigo_criterio, E.nombre_criterio, L.cartera,
                   revisados = COUNT(*),
                   acierto_resultado = SUM(CASE WHEN C.accion = 'CONFIRMAR' THEN 1 ELSE 0 END),
                   acierto_evidencia = SUM(CASE WHEN C.evidencia_valida = 'SI' THEN 1 ELSE 0 END),
                   coincidencia_plena = SUM(CASE WHEN C.accion = 'CONFIRMAR'
                                                  AND C.evidencia_valida = 'SI'
                                            THEN 1 ELSE 0 END)
            FROM CobAuto.dbo.CRM_IA_CALIBRACION_CRITERIO C
            INNER JOIN CobAuto.dbo.CRM_IA_EVALUACION_CRITERIO E
                    ON E.id_evaluacion_criterio = C.id_evaluacion_criterio
            INNER JOIN CobAuto.dbo.ia_feedback_llamadas L
                    ON L.id_feedback = C.id_feedback
            WHERE {' AND '.join(filtros)}
            GROUP BY E.codigo_criterio, E.nombre_criterio, L.cartera
            ORDER BY E.codigo_criterio
        """), params).mappings().all()

        motivos = conn.execute(text(f"""
            SELECT M.codigo, M.nombre, M.categoria, veces = COUNT(*)
            FROM CobAuto.dbo.CRM_IA_CALIBRACION_CRITERIO C
            INNER JOIN CobAuto.dbo.CRM_IA_CALIBRACION_MOTIVO M ON M.id_motivo = C.id_motivo
            INNER JOIN CobAuto.dbo.CRM_IA_EVALUACION_CRITERIO E
                    ON E.id_evaluacion_criterio = C.id_evaluacion_criterio
            INNER JOIN CobAuto.dbo.ia_feedback_llamadas L ON L.id_feedback = C.id_feedback
            WHERE {' AND '.join(filtros)}
            GROUP BY M.codigo, M.nombre, M.categoria
            ORDER BY COUNT(*) DESC
        """), params).mappings().all()

    detalle = []
    for fila in filas:
        item = dict(fila)
        revisados = int(item["revisados"]) or 1
        item["precision_resultado_pct"] = round(int(item["acierto_resultado"]) / revisados * 100, 1)
        item["precision_evidencia_pct"] = round(int(item["acierto_evidencia"]) / revisados * 100, 1)
        item["coincidencia_plena_pct"] = round(int(item["coincidencia_plena"]) / revisados * 100, 1)
        detalle.append(item)

    total = sum(int(item["revisados"]) for item in detalle)
    return {
        "criterios_revisados": total,
        # Con pocos actos de calibracion los porcentajes no son interpretables.
        # Se marca explicitamente en vez de dejar que alguien lea un 100% sobre 2 casos.
        "muestra_suficiente": total >= 30,
        "detalle": detalle,
        "motivos": [dict(item) for item in motivos],
    }
