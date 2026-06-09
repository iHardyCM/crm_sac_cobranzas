from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
import json
import os
import re
from pathlib import Path
from typing import Dict, List, Optional
from uuid import uuid4

from sqlalchemy import text

from app.core.db_siscob import engine_siscob
from app.services.ia_analysis_service import (
    analizar_transcripcion_mock,
    analizar_transcripcion_real,
    generar_transcripcion_mock,
    ia_real_configurada,
    transcribir_audio_real,
)


TABLA_FEEDBACK = "CobAuto.dbo.ia_feedback_llamadas"
UPLOAD_DIR = Path(os.getenv("IA_FEEDBACK_UPLOAD_DIR", str(Path("uploads") / "ia_feedback")))
EXTENSIONES_PERMITIDAS = {".mp3", ".wav", ".m4a", ".ogg"}
try:
    MAX_AUDIO_MB = int(os.getenv("IA_FEEDBACK_MAX_AUDIO_MB", "25"))
except ValueError:
    MAX_AUDIO_MB = 25
MAX_AUDIO_BYTES = MAX_AUDIO_MB * 1024 * 1024
FORMATOS_PERMITIDOS_TEXTO = "MP3, WAV, M4A, OGG"


def ensure_tabla_feedback():
    query = text("""
        IF OBJECT_ID('CobAuto.dbo.ia_feedback_llamadas', 'U') IS NULL
        BEGIN
            CREATE TABLE CobAuto.dbo.ia_feedback_llamadas (
                id_feedback INT IDENTITY(1,1) PRIMARY KEY,
                archivo_nombre VARCHAR(255) NOT NULL,
                ruta_archivo VARCHAR(500) NOT NULL,
                agente VARCHAR(150) NULL,
                supervisor VARCHAR(150) NULL,
                cartera VARCHAR(100) NULL,
                dni VARCHAR(20) NULL,
                telefono VARCHAR(20) NULL,
                fecha_llamada DATETIME NULL,
                duracion_segundos INT NULL,
                estado VARCHAR(30) DEFAULT 'PENDIENTE',
                transcripcion NVARCHAR(MAX) NULL,
                resumen NVARCHAR(MAX) NULL,
                tipo_contacto VARCHAR(100) NULL,
                resultado_gestion VARCHAR(150) NULL,
                objecion_principal VARCHAR(250) NULL,
                score_calidad DECIMAL(5,2) NULL,
                evaluacion_calidad NVARCHAR(MAX) NULL,
                fortalezas NVARCHAR(MAX) NULL,
                puntos_criticos NVARCHAR(MAX) NULL,
                recomendaciones NVARCHAR(MAX) NULL,
                guion_sugerido NVARCHAR(MAX) NULL,
                alertas NVARCHAR(MAX) NULL,
                nivel_oportunidad_mejora VARCHAR(50) NULL,
                comentario_supervisor NVARCHAR(MAX) NULL,
                estado_revision VARCHAR(30) DEFAULT 'PENDIENTE',
                comentario_feedback NVARCHAR(MAX) NULL,
                fecha_revision DATETIME NULL,
                revisado_por VARCHAR(150) NULL,
                mensaje_error NVARCHAR(MAX) NULL,
                fecha_creacion DATETIME DEFAULT GETDATE(),
                fecha_analisis DATETIME NULL
            );
        END
    """)
    columnas_query = text("""
        IF COL_LENGTH('CobAuto.dbo.ia_feedback_llamadas', 'estado_revision') IS NULL
            ALTER TABLE CobAuto.dbo.ia_feedback_llamadas
            ADD estado_revision VARCHAR(30) DEFAULT 'PENDIENTE';

        IF COL_LENGTH('CobAuto.dbo.ia_feedback_llamadas', 'comentario_feedback') IS NULL
            ALTER TABLE CobAuto.dbo.ia_feedback_llamadas
            ADD comentario_feedback NVARCHAR(MAX) NULL;

        IF COL_LENGTH('CobAuto.dbo.ia_feedback_llamadas', 'fecha_revision') IS NULL
            ALTER TABLE CobAuto.dbo.ia_feedback_llamadas
            ADD fecha_revision DATETIME NULL;

        IF COL_LENGTH('CobAuto.dbo.ia_feedback_llamadas', 'revisado_por') IS NULL
            ALTER TABLE CobAuto.dbo.ia_feedback_llamadas
            ADD revisado_por VARCHAR(150) NULL;

        IF COL_LENGTH('CobAuto.dbo.ia_feedback_llamadas', 'score_calidad') IS NULL
            ALTER TABLE CobAuto.dbo.ia_feedback_llamadas
            ADD score_calidad DECIMAL(5,2) NULL;

        IF COL_LENGTH('CobAuto.dbo.ia_feedback_llamadas', 'evaluacion_calidad') IS NULL
            ALTER TABLE CobAuto.dbo.ia_feedback_llamadas
            ADD evaluacion_calidad NVARCHAR(MAX) NULL;
    """)
    with engine_siscob.begin() as conn:
        conn.execute(query)
        conn.execute(columnas_query)


def registrar_audio_feedback(
    *,
    archivo_nombre: str,
    contenido: bytes,
    agente: Optional[str] = None,
    supervisor: Optional[str] = None,
    cartera: Optional[str] = None,
    dni: Optional[str] = None,
    telefono: Optional[str] = None,
    fecha_llamada: Optional[str] = None,
    comentario_supervisor: Optional[str] = None,
) -> Dict:
    ensure_tabla_feedback()

    if not contenido:
        raise ValueError("El archivo de audio esta vacio.")

    if len(contenido) > MAX_AUDIO_BYTES:
        raise ValueError(f"El archivo supera el tamano maximo permitido de {MAX_AUDIO_MB} MB.")

    extension = Path(archivo_nombre or "").suffix.lower()
    if extension not in EXTENSIONES_PERMITIDAS:
        raise ValueError(f"Formato no permitido. Usa {FORMATOS_PERMITIDOS_TEXTO}.")
    archivo_nombre = limpiar_nombre_archivo(archivo_nombre)

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    nombre_guardado = f"feedback_{datetime.now():%Y%m%d_%H%M%S}_{uuid4().hex}{extension}"
    ruta = UPLOAD_DIR / nombre_guardado
    ruta.write_bytes(contenido)

    query = text("""
        INSERT INTO CobAuto.dbo.ia_feedback_llamadas
            (archivo_nombre, ruta_archivo, agente, supervisor, cartera, dni, telefono,
             fecha_llamada, estado, comentario_supervisor, fecha_creacion)
        OUTPUT INSERTED.id_feedback
        VALUES
            (:archivo_nombre, :ruta_archivo, :agente, :supervisor, :cartera, :dni, :telefono,
             :fecha_llamada, 'PENDIENTE', :comentario_supervisor, GETDATE())
    """)

    with engine_siscob.begin() as conn:
        id_feedback = int(conn.execute(query, {
            "archivo_nombre": archivo_nombre,
            "ruta_archivo": str(ruta),
            "agente": limpiar_texto(agente),
            "supervisor": limpiar_texto(supervisor),
            "cartera": limpiar_texto(cartera),
            "dni": limpiar_texto(dni),
            "telefono": limpiar_texto(telefono),
            "fecha_llamada": normalizar_fecha_llamada(fecha_llamada),
            "comentario_supervisor": limpiar_texto(comentario_supervisor),
        }).scalar())

    return obtener_feedback(id_feedback)


def obtener_configuracion_audio() -> Dict:
    return {
        "formatos_permitidos": sorted(ext.replace(".", "").upper() for ext in EXTENSIONES_PERMITIDAS),
        "formatos_texto": FORMATOS_PERMITIDOS_TEXTO,
        "max_audio_mb": MAX_AUDIO_MB,
        "ia_real_configurada": ia_real_configurada(),
        "modelo_transcripcion": os.getenv("IA_FEEDBACK_TRANSCRIPTION_MODEL", "gpt-4o-mini-transcribe"),
        "modelo_analisis": os.getenv("IA_FEEDBACK_ANALYSIS_MODEL", "gpt-4o-mini"),
    }


def analizar_feedback(id_feedback: int) -> Dict:
    ensure_tabla_feedback()
    registro = obtener_feedback(id_feedback)

    try:
        actualizar_estado(id_feedback, "TRANSCRIBIENDO")
        aviso_ia = None
        if ia_real_configurada():
            transcripcion = transcribir_audio_real(registro.get("ruta_archivo") or "")
        else:
            aviso_ia = "IA real no configurada, usando analisis simulado"
            transcripcion = generar_transcripcion_mock(registro)
        actualizar_transcripcion(id_feedback, transcripcion)

        actualizar_estado(id_feedback, "ANALIZANDO")
        if ia_real_configurada():
            analisis = analizar_transcripcion_real(
                transcripcion,
                comentario_supervisor=registro.get("comentario_supervisor"),
                cartera=registro.get("cartera"),
            )
        else:
            analisis = analizar_transcripcion_mock(
                transcripcion,
                comentario_supervisor=registro.get("comentario_supervisor"),
            )
        guardar_analisis(id_feedback, analisis)
        resultado = obtener_feedback(id_feedback)
        if aviso_ia:
            resultado["aviso_ia"] = aviso_ia
        return resultado
    except Exception as exc:
        actualizar_estado(id_feedback, "ERROR", str(exc))
        raise


def listar_feedback(limit: int = 100, supervisor: Optional[str] = None) -> List[Dict]:
    ensure_tabla_feedback()
    filtros = []
    params = {"limit": limit}
    if limpiar_texto(supervisor):
        filtros.append("LTRIM(RTRIM(ISNULL(supervisor, ''))) = :supervisor")
        params["supervisor"] = limpiar_texto(supervisor)

    where_sql = f"WHERE {' AND '.join(filtros)}" if filtros else ""
    query = text("""
        SELECT TOP (:limit)
            id_feedback, archivo_nombre, agente, supervisor, cartera, dni, telefono,
            fecha_llamada, duracion_segundos, estado, resultado_gestion,
            score_calidad, puntos_criticos, nivel_oportunidad_mejora, estado_revision,
            comentario_feedback, revisado_por, mensaje_error,
            fecha_creacion, fecha_analisis, fecha_revision
        FROM CobAuto.dbo.ia_feedback_llamadas WITH(NOLOCK)
        {where_sql}
        ORDER BY fecha_creacion DESC, id_feedback DESC
    """.format(where_sql=where_sql))

    with engine_siscob.connect() as conn:
        rows = conn.execute(query, params).mappings().all()

    return [preparar_resumen(dict(row)) for row in rows]


def obtener_reporteria_calidad(limit: int = 300, supervisor: Optional[str] = None) -> Dict:
    ensure_tabla_feedback()
    filtros = ["estado = 'FINALIZADO'"]
    params = {"limit": limit}
    if limpiar_texto(supervisor):
        filtros.append("LTRIM(RTRIM(ISNULL(supervisor, ''))) = :supervisor")
        params["supervisor"] = limpiar_texto(supervisor)

    query = text("""
        SELECT TOP (:limit)
            id_feedback, archivo_nombre, cartera, supervisor, agente, score_calidad,
            evaluacion_calidad, fecha_creacion, fecha_llamada, comentario_supervisor,
            comentario_feedback, resultado_gestion, nivel_oportunidad_mejora,
            puntos_criticos, estado_revision
        FROM CobAuto.dbo.ia_feedback_llamadas WITH(NOLOCK)
        WHERE {where_sql}
        ORDER BY fecha_creacion DESC, id_feedback DESC
    """.format(where_sql=" AND ".join(filtros)))

    with engine_siscob.connect() as conn:
        rows = conn.execute(query, params).mappings().all()

    total = len(rows)
    scores = [float(row.get("score_calidad") or 0) for row in rows if row.get("score_calidad") is not None]
    segmentos = {}
    items = {}
    carteras = {}
    agentes = {}
    semanas = {}
    detalle = []
    total_ceros = 0

    for row in rows:
        score = float(row.get("score_calidad") or 0)
        cartera = str(row.get("cartera") or "Sin cartera")
        agente = str(row.get("agente") or "Sin agente asociado")
        supervisor_row = str(row.get("supervisor") or "Sin supervisor")
        semana = clave_semana(row.get("fecha_creacion"))
        acumular_score(carteras, cartera, "cartera", score)
        acumular_score(agentes, agente, "agente", score)
        acumular_score(semanas, semana, "semana", score)
        evaluacion = cargar_json_lista(row.get("evaluacion_calidad"))
        notas_segmento = resumir_notas_segmento(evaluacion)
        puntos_criticos = cargar_json_lista(row.get("puntos_criticos"))
        detalle.append({
            "id_feedback": row.get("id_feedback"),
            "fecha_creacion": serializar({"fecha": row.get("fecha_creacion")}).get("fecha"),
            "fecha_llamada": serializar({"fecha": row.get("fecha_llamada")}).get("fecha"),
            "archivo_nombre": row.get("archivo_nombre"),
            "cartera": cartera,
            "agente": agente,
            "supervisor": supervisor_row,
            "notas_segmento": notas_segmento,
            "score_calidad": score,
            "resultado_gestion": row.get("resultado_gestion"),
            "nivel_oportunidad_mejora": row.get("nivel_oportunidad_mejora"),
            "total_puntos_criticos": len(puntos_criticos),
            "observacion_supervisor": row.get("comentario_feedback") or row.get("comentario_supervisor"),
            "estado_revision": row.get("estado_revision"),
        })

        for item in evaluacion:
            if not isinstance(item, dict):
                continue
            segmento = str(item.get("segmento") or "Sin segmento")
            nombre_item = str(item.get("item") or "Sin item")
            peso = float(item.get("peso") or 0)
            nota = float(item.get("nota") or 0)

            seg = segmentos.setdefault(segmento, {"segmento": segmento, "peso": 0.0, "nota": 0.0, "total_items": 0, "ceros": 0})
            seg["peso"] += peso
            seg["nota"] += nota
            seg["total_items"] += 1

            key = f"{segmento}::{nombre_item}"
            actual = items.setdefault(key, {"segmento": segmento, "item": nombre_item, "peso": 0.0, "nota": 0.0, "total": 0, "ceros": 0})
            actual["peso"] += peso
            actual["nota"] += nota
            actual["total"] += 1

            if nota == 0:
                seg["ceros"] += 1
                actual["ceros"] += 1
                total_ceros += 1
                carteras[cartera]["ceros"] += 1
                agentes[agente]["ceros"] += 1
                semanas[semana]["ceros"] += 1

    segmentos_lista = [agregar_porcentaje(item) for item in segmentos.values()]
    brechas_lista = [agregar_porcentaje(item) for item in items.values()]
    carteras_lista = [finalizar_score(item) for item in carteras.values()]
    agentes_lista = [finalizar_score(item) for item in agentes.values()]
    semanas_lista = [finalizar_score(item) for item in semanas.values()]
    brechas_lista.sort(key=lambda item: (item.get("ceros", 0), 100 - item.get("porcentaje", 0)), reverse=True)
    segmentos_lista.sort(key=lambda item: item.get("porcentaje", 0))
    carteras_lista.sort(key=lambda item: (item.get("score_promedio") or 0))
    agentes_lista.sort(key=lambda item: (item.get("score_promedio") or 0))
    semanas_lista.sort(key=lambda item: item.get("semana") or "")

    return {
        "total_audios": total,
        "score_promedio": round(sum(scores) / len(scores), 2) if scores else None,
        "items_nota_cero": total_ceros,
        "segmentos": segmentos_lista,
        "brechas": brechas_lista[:12],
        "carteras": carteras_lista,
        "agentes": agentes_lista[:20],
        "semanas": semanas_lista,
        "detalle": detalle,
    }


def agregar_porcentaje(item: Dict) -> Dict:
    peso = float(item.get("peso") or 0)
    nota = float(item.get("nota") or 0)
    item["porcentaje"] = round((nota / peso) * 100, 2) if peso else 0
    item["peso"] = round(peso, 2)
    item["nota"] = round(nota, 2)
    return item


def acumular_score(destino: Dict, clave: str, campo: str, score: float):
    item = destino.setdefault(clave, {
        campo: clave,
        "total_audios": 0,
        "score_total": 0.0,
        "ceros": 0,
    })
    item["total_audios"] += 1
    item["score_total"] += score


def finalizar_score(item: Dict) -> Dict:
    total = int(item.get("total_audios") or 0)
    score_total = float(item.pop("score_total", 0) or 0)
    item["score_promedio"] = round(score_total / total, 2) if total else None
    return item


def resumir_notas_segmento(items: List) -> Dict:
    segmentos: Dict[str, Dict] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        segmento = str(item.get("segmento") or "Sin segmento")
        actual = segmentos.setdefault(segmento, {"nota": 0.0, "peso": 0.0})
        actual["nota"] += float(item.get("nota") or 0)
        actual["peso"] += float(item.get("peso") or 0)
    return {
        segmento: {
            "nota": round(data["nota"], 2),
            "peso": round(data["peso"], 2),
            "porcentaje": round((data["nota"] / data["peso"]) * 100, 2) if data["peso"] else 0,
        }
        for segmento, data in segmentos.items()
    }


def clave_semana(value) -> str:
    if isinstance(value, datetime):
        fecha = value
    else:
        try:
            fecha = datetime.fromisoformat(str(value))
        except Exception:
            fecha = datetime.now()
    iso = fecha.isocalendar()
    return f"{iso.year}-S{iso.week:02d}"


def obtener_feedback(id_feedback: int) -> Dict:
    ensure_tabla_feedback()
    query = text("""
        SELECT
            id_feedback, archivo_nombre, ruta_archivo, agente, supervisor, cartera, dni,
            telefono, fecha_llamada, duracion_segundos, estado, transcripcion, resumen,
            tipo_contacto, resultado_gestion, objecion_principal, score_calidad,
            evaluacion_calidad, fortalezas, puntos_criticos, recomendaciones, guion_sugerido, alertas,
            nivel_oportunidad_mejora, comentario_supervisor, estado_revision,
            comentario_feedback, revisado_por, mensaje_error,
            fecha_creacion, fecha_analisis, fecha_revision
        FROM CobAuto.dbo.ia_feedback_llamadas WITH(NOLOCK)
        WHERE id_feedback = :id_feedback
    """)

    with engine_siscob.connect() as conn:
        row = conn.execute(query, {"id_feedback": id_feedback}).mappings().first()

    if not row:
        raise ValueError("Analisis IA no encontrado.")

    data = serializar(dict(row))
    data["evaluacion_calidad_lista"] = cargar_json_lista(data.get("evaluacion_calidad"))
    data["fortalezas_lista"] = cargar_json_lista(data.get("fortalezas"))
    data["puntos_criticos_lista"] = cargar_json_lista(data.get("puntos_criticos"))
    data["alertas_lista"] = cargar_json_lista(data.get("alertas"))
    data["total_puntos_criticos"] = len(data["puntos_criticos_lista"])
    return data


def actualizar_estado(id_feedback: int, estado: str, mensaje_error: Optional[str] = None):
    with engine_siscob.begin() as conn:
        conn.execute(text("""
            UPDATE CobAuto.dbo.ia_feedback_llamadas
            SET estado = :estado,
                mensaje_error = :mensaje_error
            WHERE id_feedback = :id_feedback
        """), {
            "id_feedback": id_feedback,
            "estado": estado,
            "mensaje_error": mensaje_error,
        })


def actualizar_transcripcion(id_feedback: int, transcripcion: str):
    with engine_siscob.begin() as conn:
        conn.execute(text("""
            UPDATE CobAuto.dbo.ia_feedback_llamadas
            SET transcripcion = :transcripcion
            WHERE id_feedback = :id_feedback
        """), {
            "id_feedback": id_feedback,
            "transcripcion": transcripcion,
        })


def guardar_analisis(id_feedback: int, analisis: Dict):
    with engine_siscob.begin() as conn:
        conn.execute(text("""
            UPDATE CobAuto.dbo.ia_feedback_llamadas
            SET estado = 'FINALIZADO',
                resumen = :resumen,
                tipo_contacto = :tipo_contacto,
                resultado_gestion = :resultado_gestion,
                objecion_principal = :objecion_principal,
                score_calidad = :score_calidad,
                evaluacion_calidad = :evaluacion_calidad,
                fortalezas = :fortalezas,
                puntos_criticos = :puntos_criticos,
                recomendaciones = :recomendaciones,
                guion_sugerido = :guion_sugerido,
                alertas = :alertas,
                nivel_oportunidad_mejora = :nivel_oportunidad_mejora,
                mensaje_error = NULL,
                fecha_analisis = GETDATE()
            WHERE id_feedback = :id_feedback
        """), {
            "id_feedback": id_feedback,
            "resumen": analisis.get("resumen"),
            "tipo_contacto": analisis.get("tipo_contacto"),
            "resultado_gestion": analisis.get("resultado_gestion"),
            "objecion_principal": analisis.get("objecion_principal"),
            "score_calidad": analisis.get("score_calidad"),
            "evaluacion_calidad": json.dumps(analisis.get("evaluacion_calidad") or [], ensure_ascii=False),
            "fortalezas": json.dumps(analisis.get("fortalezas_agente") or [], ensure_ascii=False),
            "puntos_criticos": json.dumps(analisis.get("puntos_criticos") or [], ensure_ascii=False),
            "recomendaciones": analisis.get("recomendacion_feedback_supervisor"),
            "guion_sugerido": analisis.get("guion_sugerido"),
            "alertas": json.dumps(analisis.get("alertas") or [], ensure_ascii=False),
            "nivel_oportunidad_mejora": analisis.get("nivel_oportunidad_mejora"),
        })


def guardar_revision_feedback(
    id_feedback: int,
    *,
    agente: Optional[str] = None,
    comentario_feedback: Optional[str] = None,
    estado_revision: Optional[str] = None,
    revisado_por: Optional[str] = None,
) -> Dict:
    ensure_tabla_feedback()
    obtener_feedback(id_feedback)

    estado = normalizar_estado_revision(estado_revision)
    with engine_siscob.begin() as conn:
        conn.execute(text("""
            UPDATE CobAuto.dbo.ia_feedback_llamadas
            SET agente = :agente,
                comentario_feedback = :comentario_feedback,
                estado_revision = :estado_revision,
                revisado_por = :revisado_por,
                fecha_revision = GETDATE()
            WHERE id_feedback = :id_feedback
        """), {
            "id_feedback": id_feedback,
            "agente": limpiar_texto(agente),
            "comentario_feedback": limpiar_texto(comentario_feedback),
            "estado_revision": estado,
            "revisado_por": limpiar_texto(revisado_por),
        })

    return obtener_feedback(id_feedback)


def preparar_resumen(row: Dict) -> Dict:
    data = serializar(row)
    data["total_puntos_criticos"] = len(cargar_json_lista(data.get("puntos_criticos")))
    return data


def cargar_json_lista(value) -> List:
    if not value:
        return []
    if isinstance(value, list):
        return value
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, list) else []
    except Exception:
        return []


def limpiar_nombre_archivo(nombre: str) -> str:
    nombre = Path(nombre or "audio").name
    nombre = re.sub(r"[^A-Za-z0-9_. -]", "_", nombre).strip()
    return nombre[:180] or "audio"


def limpiar_texto(value) -> Optional[str]:
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def normalizar_fecha_llamada(value) -> Optional[datetime]:
    texto = limpiar_texto(value)
    if not texto:
        return None

    formatos = (
        "%Y-%m-%dT%H:%M",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
    )
    for formato in formatos:
        try:
            return datetime.strptime(texto, formato)
        except ValueError:
            pass

    try:
        return datetime.fromisoformat(texto)
    except ValueError as exc:
        raise ValueError("La fecha de llamada no tiene un formato valido.") from exc


def normalizar_estado_revision(value: Optional[str]) -> str:
    estado = str(value or "REVISADO").strip().upper()
    permitidos = {"PENDIENTE", "REVISADO", "FEEDBACK_ENVIADO", "CERRADO"}
    return estado if estado in permitidos else "REVISADO"


def serializar(row: Dict) -> Dict:
    serializado = {}
    for key, value in row.items():
        if isinstance(value, Decimal):
            serializado[key] = float(value)
        elif isinstance(value, (datetime, date)):
            serializado[key] = value.isoformat()
        else:
            serializado[key] = value
    return serializado
