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
    calcular_score_normalizado,
    construir_resumen_sgc,
    enriquecer_evaluacion_sgc,
    generar_transcripcion_mock,
    ia_real_configurada,
    normalizar_interlocutores_v2,
    reparar_evaluacion_contextual_v2,
    transcribir_audio_real,
)


TABLA_FEEDBACK = "CobAuto.dbo.ia_feedback_llamadas"
TABLA_RECALIBRACIONES = "CobAuto.dbo.ia_feedback_recalibraciones"
TABLA_COACHING = "CobAuto.dbo.ia_feedback_coaching"
TABLA_HISTORIAL = "CobAuto.dbo.ia_feedback_historial"
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
                habilidades_blandas NVARCHAR(MAX) NULL,
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

        IF COL_LENGTH('CobAuto.dbo.ia_feedback_llamadas', 'habilidades_blandas') IS NULL
            ALTER TABLE CobAuto.dbo.ia_feedback_llamadas
            ADD habilidades_blandas NVARCHAR(MAX) NULL;

        IF COL_LENGTH('CobAuto.dbo.ia_feedback_llamadas', 'score_calidad_ia') IS NULL
            ALTER TABLE CobAuto.dbo.ia_feedback_llamadas
            ADD score_calidad_ia DECIMAL(5,2) NULL;

        IF COL_LENGTH('CobAuto.dbo.ia_feedback_llamadas', 'nivel_ia') IS NULL
            ALTER TABLE CobAuto.dbo.ia_feedback_llamadas
            ADD nivel_ia VARCHAR(50) NULL;

        IF COL_LENGTH('CobAuto.dbo.ia_feedback_llamadas', 'falta_anulante') IS NULL
            ALTER TABLE CobAuto.dbo.ia_feedback_llamadas
            ADD falta_anulante BIT DEFAULT 0;

        IF COL_LENGTH('CobAuto.dbo.ia_feedback_llamadas', 'frase_anulante') IS NULL
            ALTER TABLE CobAuto.dbo.ia_feedback_llamadas
            ADD frase_anulante NVARCHAR(500) NULL;

        IF COL_LENGTH('CobAuto.dbo.ia_feedback_llamadas', 'momento_falta_anulante') IS NULL
            ALTER TABLE CobAuto.dbo.ia_feedback_llamadas
            ADD momento_falta_anulante VARCHAR(20) NULL;

        IF COL_LENGTH('CobAuto.dbo.ia_feedback_llamadas', 'estado_recalibracion') IS NULL
            ALTER TABLE CobAuto.dbo.ia_feedback_llamadas
            ADD estado_recalibracion VARCHAR(30) DEFAULT 'SIN_APELACION';

        IF COL_LENGTH('CobAuto.dbo.ia_feedback_llamadas', 'tipo_llamada') IS NULL
            ALTER TABLE CobAuto.dbo.ia_feedback_llamadas
            ADD tipo_llamada VARCHAR(100) NULL;

        IF COL_LENGTH('CobAuto.dbo.ia_feedback_llamadas', 'evaluabilidad') IS NULL
            ALTER TABLE CobAuto.dbo.ia_feedback_llamadas
            ADD evaluabilidad VARCHAR(40) NULL;

        IF COL_LENGTH('CobAuto.dbo.ia_feedback_llamadas', 'motivo_no_evaluable') IS NULL
            ALTER TABLE CobAuto.dbo.ia_feedback_llamadas
            ADD motivo_no_evaluable NVARCHAR(500) NULL;

        IF COL_LENGTH('CobAuto.dbo.ia_feedback_llamadas', 'objetivo_principal') IS NULL
            ALTER TABLE CobAuto.dbo.ia_feedback_llamadas
            ADD objetivo_principal NVARCHAR(500) NULL;

        IF COL_LENGTH('CobAuto.dbo.ia_feedback_llamadas', 'score_supervisor') IS NULL
            ALTER TABLE CobAuto.dbo.ia_feedback_llamadas
            ADD score_supervisor DECIMAL(5,2) NULL;

        IF COL_LENGTH('CobAuto.dbo.ia_feedback_llamadas', 'score_final') IS NULL
            ALTER TABLE CobAuto.dbo.ia_feedback_llamadas
            ADD score_final DECIMAL(5,2) NULL;

        IF COL_LENGTH('CobAuto.dbo.ia_feedback_llamadas', 'score_bruto') IS NULL
            ALTER TABLE CobAuto.dbo.ia_feedback_llamadas
            ADD score_bruto DECIMAL(5,2) NULL;

        IF COL_LENGTH('CobAuto.dbo.ia_feedback_llamadas', 'peso_aplicable') IS NULL
            ALTER TABLE CobAuto.dbo.ia_feedback_llamadas
            ADD peso_aplicable DECIMAL(5,2) NULL;

        IF COL_LENGTH('CobAuto.dbo.ia_feedback_llamadas', 'score_normalizado') IS NULL
            ALTER TABLE CobAuto.dbo.ia_feedback_llamadas
            ADD score_normalizado DECIMAL(5,2) NULL;

        IF COL_LENGTH('CobAuto.dbo.ia_feedback_llamadas', 'estado_calidad') IS NULL
            ALTER TABLE CobAuto.dbo.ia_feedback_llamadas
            ADD estado_calidad VARCHAR(60) NULL;

        IF COL_LENGTH('CobAuto.dbo.ia_feedback_llamadas', 'nivel_riesgo') IS NULL
            ALTER TABLE CobAuto.dbo.ia_feedback_llamadas
            ADD nivel_riesgo VARCHAR(40) NULL;

        IF COL_LENGTH('CobAuto.dbo.ia_feedback_llamadas', 'error_critico') IS NULL
            ALTER TABLE CobAuto.dbo.ia_feedback_llamadas
            ADD error_critico BIT DEFAULT 0;

        IF COL_LENGTH('CobAuto.dbo.ia_feedback_llamadas', 'calidad_transcripcion') IS NULL
            ALTER TABLE CobAuto.dbo.ia_feedback_llamadas
            ADD calidad_transcripcion VARCHAR(30) NULL;

        IF COL_LENGTH('CobAuto.dbo.ia_feedback_llamadas', 'confianza_evaluacion') IS NULL
            ALTER TABLE CobAuto.dbo.ia_feedback_llamadas
            ADD confianza_evaluacion VARCHAR(30) NULL;

        IF COL_LENGTH('CobAuto.dbo.ia_feedback_llamadas', 'requiere_revision_humana') IS NULL
            ALTER TABLE CobAuto.dbo.ia_feedback_llamadas
            ADD requiere_revision_humana BIT DEFAULT 0;

        IF COL_LENGTH('CobAuto.dbo.ia_feedback_llamadas', 'motivo_revision') IS NULL
            ALTER TABLE CobAuto.dbo.ia_feedback_llamadas
            ADD motivo_revision NVARCHAR(500) NULL;

        IF COL_LENGTH('CobAuto.dbo.ia_feedback_llamadas', 'evidencias_clave') IS NULL
            ALTER TABLE CobAuto.dbo.ia_feedback_llamadas
            ADD evidencias_clave NVARCHAR(MAX) NULL;

        IF COL_LENGTH('CobAuto.dbo.ia_feedback_llamadas', 'estado_coaching') IS NULL
            ALTER TABLE CobAuto.dbo.ia_feedback_llamadas
            ADD estado_coaching VARCHAR(30) DEFAULT 'PENDIENTE';

        IF COL_LENGTH('CobAuto.dbo.ia_feedback_llamadas', 'fecha_coaching') IS NULL
            ALTER TABLE CobAuto.dbo.ia_feedback_llamadas
            ADD fecha_coaching DATETIME NULL;

        IF COL_LENGTH('CobAuto.dbo.ia_feedback_llamadas', 'responsable_coaching') IS NULL
            ALTER TABLE CobAuto.dbo.ia_feedback_llamadas
            ADD responsable_coaching VARCHAR(150) NULL;

        IF COL_LENGTH('CobAuto.dbo.ia_feedback_llamadas', 'compromiso_agente') IS NULL
            ALTER TABLE CobAuto.dbo.ia_feedback_llamadas
            ADD compromiso_agente NVARCHAR(MAX) NULL;

        IF COL_LENGTH('CobAuto.dbo.ia_feedback_llamadas', 'resultado_coaching') IS NULL
            ALTER TABLE CobAuto.dbo.ia_feedback_llamadas
            ADD resultado_coaching NVARCHAR(MAX) NULL;

        IF COL_LENGTH('CobAuto.dbo.ia_feedback_llamadas', 'resumen_sgc') IS NULL
            ALTER TABLE CobAuto.dbo.ia_feedback_llamadas
            ADD resumen_sgc NVARCHAR(MAX) NULL;

        IF COL_LENGTH('CobAuto.dbo.ia_feedback_llamadas', 'estado_feedback') IS NULL
            ALTER TABLE CobAuto.dbo.ia_feedback_llamadas
            ADD estado_feedback VARCHAR(30) DEFAULT 'PENDIENTE';

        IF COL_LENGTH('CobAuto.dbo.ia_feedback_llamadas', 'requiere_feedback') IS NULL
            ALTER TABLE CobAuto.dbo.ia_feedback_llamadas
            ADD requiere_feedback BIT DEFAULT 0;

        IF COL_LENGTH('CobAuto.dbo.ia_feedback_llamadas', 'requiere_coaching') IS NULL
            ALTER TABLE CobAuto.dbo.ia_feedback_llamadas
            ADD requiere_coaching BIT DEFAULT 0;

        IF OBJECT_ID('CobAuto.dbo.ia_feedback_recalibraciones', 'U') IS NULL
        BEGIN
            CREATE TABLE CobAuto.dbo.ia_feedback_recalibraciones (
                id_recalibracion INT IDENTITY(1,1) PRIMARY KEY,
                id_feedback INT NOT NULL,
                score_ia DECIMAL(5,2) NULL,
                nivel_ia VARCHAR(50) NULL,
                item_cuestionado VARCHAR(250) NULL,
                score_sugerido DECIMAL(5,2) NULL,
                nivel_sugerido VARCHAR(50) NULL,
                motivo NVARCHAR(MAX) NOT NULL,
                evidencia_supervisor NVARCHAR(MAX) NULL,
                solicitado_por VARCHAR(150) NULL,
                fecha_solicitud DATETIME DEFAULT GETDATE(),
                estado VARCHAR(30) DEFAULT 'PENDIENTE',
                resuelto_por VARCHAR(150) NULL,
                fecha_resolucion DATETIME NULL,
                motivo_resolucion NVARCHAR(MAX) NULL,
                score_final DECIMAL(5,2) NULL
            );
        END

        IF OBJECT_ID('CobAuto.dbo.ia_feedback_coaching', 'U') IS NULL
        BEGIN
            CREATE TABLE CobAuto.dbo.ia_feedback_coaching (
                id_coaching INT IDENTITY(1,1) PRIMARY KEY,
                id_feedback INT NOT NULL,
                estado VARCHAR(30) DEFAULT 'PENDIENTE',
                feedback_ia NVARCHAR(MAX) NULL,
                feedback_supervisor NVARCHAR(MAX) NULL,
                compromiso_agente NVARCHAR(MAX) NULL,
                fecha_programada DATETIME NULL,
                fecha_realizada DATETIME NULL,
                responsable VARCHAR(150) NULL,
                resultado NVARCHAR(MAX) NULL,
                usuario_creacion VARCHAR(150) NULL,
                fecha_creacion DATETIME DEFAULT GETDATE(),
                usuario_cierre VARCHAR(150) NULL,
                fecha_cierre DATETIME NULL
            );
        END

        IF OBJECT_ID('CobAuto.dbo.ia_feedback_historial', 'U') IS NULL
        BEGIN
            CREATE TABLE CobAuto.dbo.ia_feedback_historial (
                id_historial INT IDENTITY(1,1) PRIMARY KEY,
                id_feedback INT NOT NULL,
                accion VARCHAR(80) NOT NULL,
                descripcion NVARCHAR(MAX) NULL,
                valor_anterior NVARCHAR(MAX) NULL,
                valor_nuevo NVARCHAR(MAX) NULL,
                usuario VARCHAR(150) NULL,
                fecha DATETIME DEFAULT GETDATE()
            );
        END
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
            score_calidad, score_final, score_normalizado, nivel_riesgo, tipo_llamada,
            puntos_criticos, nivel_oportunidad_mejora, estado_revision,
            comentario_feedback, revisado_por, mensaje_error, falta_anulante,
            error_critico, estado_recalibracion, estado_coaching,
            resumen_sgc, estado_feedback, requiere_feedback, requiere_coaching,
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
            score_calidad_ia, score_supervisor, score_final, score_normalizado,
            nivel_riesgo, tipo_llamada, requiere_revision_humana,
            evaluacion_calidad, fecha_creacion, fecha_llamada, comentario_supervisor,
            comentario_feedback, resultado_gestion, nivel_oportunidad_mejora,
            puntos_criticos, estado_revision, falta_anulante, error_critico,
            estado_recalibracion, estado_coaching, resumen_sgc, estado_feedback,
            requiere_feedback, requiere_coaching, fecha_coaching
        FROM CobAuto.dbo.ia_feedback_llamadas WITH(NOLOCK)
        WHERE {where_sql}
        ORDER BY fecha_creacion DESC, id_feedback DESC
    """.format(where_sql=" AND ".join(filtros)))

    with engine_siscob.connect() as conn:
        rows = conn.execute(query, params).mappings().all()

    total = len(rows)
    scores = [
        float(row.get("score_final") if row.get("score_final") is not None else row.get("score_calidad") or 0)
        for row in rows
        if row.get("score_final") is not None or row.get("score_calidad") is not None
    ]
    segmentos = {}
    items = {}
    carteras = {}
    agentes = {}
    semanas = {}
    sgc_grupos = {}
    sgc_factores = {}
    detalle = []
    total_ceros = 0

    for row in rows:
        score = float(row.get("score_final") if row.get("score_final") is not None else row.get("score_calidad") or 0)
        cartera = str(row.get("cartera") or "Sin cartera")
        agente = str(row.get("agente") or "Sin agente asociado")
        supervisor_row = str(row.get("supervisor") or "Sin supervisor")
        semana = clave_semana(row.get("fecha_creacion"))
        acumular_score(carteras, cartera, "cartera", score)
        acumular_score(agentes, agente, "agente", score)
        acumular_score(semanas, semana, "semana", score)
        row_data = serializar(dict(row))
        evaluacion = cargar_json_lista(row.get("evaluacion_calidad"))
        row_data["evaluacion_calidad_lista"] = evaluacion
        row_data = enriquecer_sgc_registro(row_data)
        evaluacion = row_data["evaluacion_calidad_lista"]
        resumen_sgc = row_data["resumen_sgc"]
        notas_segmento = resumir_notas_segmento(evaluacion)
        brechas_items = [
            {
                "segmento": str(item.get("segmento") or "Sin segmento"),
                "item": str(item.get("item") or "Sin item"),
                "segmento_copc": str(item.get("segmento_copc") or item.get("segmento") or "Sin segmento"),
                "grupo_error_sgc": str(item.get("grupo_error_sgc") or "No aplica"),
                "factor_sgc": str(item.get("factor_sgc") or item.get("item") or "Sin factor"),
                "requiere_feedback": bool(item.get("requiere_feedback")),
                "requiere_coaching": bool(item.get("requiere_coaching")),
                "nota": float(item.get("nota") or 0),
                "peso": float(item.get("peso") or 0),
            }
            for item in evaluacion
            if isinstance(item, dict) and float(item.get("nota") or 0) == 0
        ]
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
            "brechas_items": brechas_items,
            "evaluacion_calidad_lista": evaluacion,
            "resumen_sgc": resumen_sgc,
            "score_calidad": score,
            "score_calidad_ia": float(row.get("score_calidad_ia") or score),
            "score_supervisor": float(row.get("score_supervisor")) if row.get("score_supervisor") is not None else None,
            "score_final": score,
            "score_normalizado": float(row.get("score_normalizado") or score),
            "nivel_riesgo": row.get("nivel_riesgo") or row.get("nivel_oportunidad_mejora"),
            "tipo_llamada": row.get("tipo_llamada"),
            "requiere_revision_humana": bool(row.get("requiere_revision_humana")),
            "resultado_gestion": row.get("resultado_gestion"),
            "nivel_oportunidad_mejora": row.get("nivel_oportunidad_mejora"),
            "total_puntos_criticos": len(puntos_criticos),
            "observacion_supervisor": row.get("comentario_feedback") or row.get("comentario_supervisor"),
            "estado_revision": row.get("estado_revision"),
            "falta_anulante": bool(row.get("falta_anulante")),
            "error_critico": bool(row.get("error_critico")),
            "estado_recalibracion": row.get("estado_recalibracion") or "SIN_APELACION",
            "estado_coaching": row.get("estado_coaching") or "PENDIENTE",
            "estado_feedback": row_data.get("estado_feedback"),
            "requiere_feedback": bool(row_data.get("requiere_feedback")),
            "requiere_coaching": bool(row_data.get("requiere_coaching")),
            "fecha_coaching": serializar({"fecha": row.get("fecha_coaching")}).get("fecha"),
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
            if nota < peso and str(item.get("grupo_error_sgc") or "No aplica") != "No aplica":
                grupo = str(item.get("grupo_error_sgc") or "No aplica")
                factor = str(item.get("factor_sgc") or nombre_item)
                sgc_grupo = sgc_grupos.setdefault(grupo, {"grupo_error_sgc": grupo, "total": 0, "criticos": 0})
                sgc_grupo["total"] += 1
                if "crítico" in grupo.lower() or "critico" in grupo.lower():
                    sgc_grupo["criticos"] += 1
                key_sgc = f"{grupo}::{factor}"
                sgc_factor = sgc_factores.setdefault(key_sgc, {
                    "grupo_error_sgc": grupo,
                    "factor_sgc": factor,
                    "frecuencia": 0,
                    "impacto": "Alto" if "cumplimiento" in grupo.lower() or "negocio" in grupo.lower() else "Medio",
                    "accion_recomendada": "Programar coaching" if "cumplimiento" in grupo.lower() or "negocio" in grupo.lower() else "Feedback puntual",
                })
                sgc_factor["frecuencia"] += 1

    segmentos_lista = [agregar_porcentaje(item) for item in segmentos.values()]
    brechas_lista = [agregar_porcentaje(item) for item in items.values()]
    carteras_lista = [finalizar_score(item) for item in carteras.values()]
    agentes_lista = [finalizar_score(item) for item in agentes.values()]
    semanas_lista = [finalizar_score(item) for item in semanas.values()]
    sgc_grupos_lista = sorted(sgc_grupos.values(), key=lambda item: item.get("total", 0), reverse=True)
    sgc_factores_lista = sorted(sgc_factores.values(), key=lambda item: item.get("frecuencia", 0), reverse=True)
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
        "sgc_grupos": sgc_grupos_lista,
        "sgc_factores": sgc_factores_lista[:20],
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
    semana_mes = ((fecha.day - 1) // 7) + 1
    return f"{fecha.year}-{fecha.month:02d} S{semana_mes}"


def obtener_feedback(id_feedback: int) -> Dict:
    ensure_tabla_feedback()
    query = text("""
        SELECT
            id_feedback, archivo_nombre, ruta_archivo, agente, supervisor, cartera, dni,
            telefono, fecha_llamada, duracion_segundos, estado, transcripcion, resumen,
            tipo_contacto, tipo_llamada, evaluabilidad, motivo_no_evaluable,
            objetivo_principal, resultado_gestion, objecion_principal, score_calidad,
            score_calidad_ia, score_supervisor, score_final, score_bruto,
            peso_aplicable, score_normalizado, estado_calidad, nivel_riesgo,
            error_critico, calidad_transcripcion, confianza_evaluacion,
            requiere_revision_humana, motivo_revision,
            evaluacion_calidad, habilidades_blandas, fortalezas, puntos_criticos, recomendaciones, guion_sugerido, alertas,
            evidencias_clave, nivel_oportunidad_mejora, comentario_supervisor, estado_revision,
            comentario_feedback, revisado_por, mensaje_error, nivel_ia,
            falta_anulante, frase_anulante, momento_falta_anulante, estado_recalibracion,
            estado_coaching, fecha_coaching, responsable_coaching, compromiso_agente, resultado_coaching,
            resumen_sgc, estado_feedback, requiere_feedback, requiere_coaching,
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
    data["habilidades_blandas_lista"] = cargar_json_lista(data.get("habilidades_blandas"))
    data["fortalezas_lista"] = cargar_json_lista(data.get("fortalezas"))
    data["puntos_criticos_lista"] = cargar_json_lista(data.get("puntos_criticos"))
    data["alertas_lista"] = cargar_json_lista(data.get("alertas"))
    data["evidencias_clave_lista"] = cargar_json_lista(data.get("evidencias_clave"))
    data["recalibraciones_lista"] = listar_recalibraciones_feedback(id_feedback)
    data["coaching_lista"] = listar_coaching_feedback(id_feedback)
    data["historial_lista"] = listar_historial_feedback(id_feedback)
    data["total_puntos_criticos"] = len(data["puntos_criticos_lista"])
    data = enriquecer_sgc_registro(data)
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
    score_final = analisis.get("score_final")
    if score_final is None:
        score_final = analisis.get("score_normalizado")
    if score_final is None:
        score_final = analisis.get("score_calidad")
    try:
        score_final_num = float(score_final) if score_final is not None else None
    except Exception:
        score_final_num = None
    resumen_sgc = analisis.get("resumen_sgc") or construir_resumen_sgc(
        analisis.get("evaluacion_calidad") or [],
        {},
        score_final=score_final_num,
        nivel_riesgo=analisis.get("nivel_riesgo") or analisis.get("nivel_oportunidad_mejora"),
        falta_anulante=bool(analisis.get("falta_anulante")),
    )
    if analisis.get("tipificaciones_sugeridas"):
        resumen_sgc["tipificaciones_sugeridas"] = analisis.get("tipificaciones_sugeridas")
    if analisis.get("json_copc_v2"):
        resumen_sgc["version_evaluacion"] = "2.0"
        resumen_sgc["json_copc_v2"] = analisis.get("json_copc_v2")
    if analisis.get("estado_tecnico"):
        resumen_sgc["estado_tecnico"] = analisis.get("estado_tecnico")
    if analisis.get("feedback_asesor"):
        resumen_sgc["feedback_asesor"] = analisis.get("feedback_asesor")
    with engine_siscob.begin() as conn:
        conn.execute(text("""
            UPDATE CobAuto.dbo.ia_feedback_llamadas
            SET estado = 'FINALIZADO',
                resumen = :resumen,
                tipo_contacto = :tipo_contacto,
                tipo_llamada = :tipo_llamada,
                evaluabilidad = :evaluabilidad,
                motivo_no_evaluable = :motivo_no_evaluable,
                objetivo_principal = :objetivo_principal,
                resultado_gestion = :resultado_gestion,
                objecion_principal = :objecion_principal,
                score_calidad = :score_final,
                score_calidad_ia = :score_calidad_ia,
                score_final = :score_final,
                score_bruto = :score_bruto,
                peso_aplicable = :peso_aplicable,
                score_normalizado = :score_normalizado,
                estado_calidad = :estado_calidad,
                nivel_riesgo = :nivel_riesgo,
                error_critico = :error_critico,
                calidad_transcripcion = :calidad_transcripcion,
                confianza_evaluacion = :confianza_evaluacion,
                requiere_revision_humana = :requiere_revision_humana,
                motivo_revision = :motivo_revision,
                evaluacion_calidad = :evaluacion_calidad,
                habilidades_blandas = :habilidades_blandas,
                fortalezas = :fortalezas,
                puntos_criticos = :puntos_criticos,
                recomendaciones = :recomendaciones,
                guion_sugerido = :guion_sugerido,
                alertas = :alertas,
                evidencias_clave = :evidencias_clave,
                nivel_oportunidad_mejora = :nivel_oportunidad_mejora,
                nivel_ia = :nivel_oportunidad_mejora,
                falta_anulante = :falta_anulante,
                frase_anulante = :frase_anulante,
                momento_falta_anulante = :momento_falta_anulante,
                resumen_sgc = :resumen_sgc,
                requiere_feedback = :requiere_feedback,
                requiere_coaching = :requiere_coaching,
                estado_feedback = :estado_feedback,
                estado_recalibracion = ISNULL(estado_recalibracion, 'SIN_APELACION'),
                estado_coaching = CASE WHEN :requiere_coaching = 1 AND ISNULL(estado_coaching, '') = '' THEN 'PENDIENTE' ELSE ISNULL(estado_coaching, 'PENDIENTE') END,
                mensaje_error = NULL,
                fecha_analisis = GETDATE()
            WHERE id_feedback = :id_feedback
        """), {
            "id_feedback": id_feedback,
            "resumen": analisis.get("resumen"),
            "tipo_contacto": analisis.get("tipo_contacto"),
            "tipo_llamada": analisis.get("tipo_llamada"),
            "evaluabilidad": analisis.get("evaluabilidad"),
            "motivo_no_evaluable": analisis.get("motivo_no_evaluable"),
            "objetivo_principal": analisis.get("objetivo_principal"),
            "resultado_gestion": analisis.get("resultado_gestion"),
            "objecion_principal": analisis.get("objecion_principal"),
            "score_calidad_ia": analisis.get("score_calidad"),
            "score_final": score_final,
            "score_bruto": analisis.get("score_bruto"),
            "peso_aplicable": analisis.get("peso_aplicable"),
            "score_normalizado": analisis.get("score_normalizado"),
            "estado_calidad": analisis.get("estado_calidad"),
            "nivel_riesgo": analisis.get("nivel_riesgo"),
            "error_critico": 1 if analisis.get("error_critico") else 0,
            "calidad_transcripcion": analisis.get("calidad_transcripcion"),
            "confianza_evaluacion": analisis.get("confianza_evaluacion"),
            "requiere_revision_humana": 1 if analisis.get("requiere_revision_humana") else 0,
            "motivo_revision": analisis.get("motivo_revision"),
            "evaluacion_calidad": json.dumps(analisis.get("evaluacion_calidad") or [], ensure_ascii=False),
            "habilidades_blandas": json.dumps(analisis.get("habilidades_blandas") or [], ensure_ascii=False),
            "fortalezas": json.dumps(analisis.get("fortalezas_agente") or [], ensure_ascii=False),
            "puntos_criticos": json.dumps(analisis.get("puntos_criticos") or [], ensure_ascii=False),
            "recomendaciones": analisis.get("recomendacion_feedback_supervisor"),
            "guion_sugerido": analisis.get("guion_sugerido"),
            "alertas": json.dumps(analisis.get("alertas") or [], ensure_ascii=False),
            "evidencias_clave": json.dumps(analisis.get("evidencias_clave") or [], ensure_ascii=False),
            "nivel_oportunidad_mejora": analisis.get("nivel_oportunidad_mejora"),
            "falta_anulante": 1 if analisis.get("falta_anulante") else 0,
            "frase_anulante": analisis.get("frase_anulante"),
            "momento_falta_anulante": analisis.get("momento_falta_anulante"),
            "resumen_sgc": json.dumps(resumen_sgc, ensure_ascii=False),
            "requiere_feedback": 1 if resumen_sgc.get("requiere_feedback") else 0,
            "requiere_coaching": 1 if resumen_sgc.get("requiere_coaching") else 0,
            "estado_feedback": "PENDIENTE" if resumen_sgc.get("requiere_feedback") else "NO_REQUIERE",
        })
    registrar_historial_feedback(
        id_feedback,
        "ANALISIS_IA",
        "Preevaluacion IA generada bajo matriz COPC Cobranza.",
        valor_nuevo=json.dumps({
            "score_calidad": analisis.get("score_calidad"),
            "score_final": score_final,
            "nivel_riesgo": analisis.get("nivel_riesgo") or analisis.get("nivel_oportunidad_mejora"),
        }, ensure_ascii=False),
    )


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

    registrar_historial_feedback(
        id_feedback,
        "REVISION_SUPERVISOR",
        f"Revision guardada con estado {estado}.",
        usuario=limpiar_texto(revisado_por),
        valor_nuevo=limpiar_texto(comentario_feedback),
    )
    return obtener_feedback(id_feedback)


def solicitar_recalibracion_feedback(
    id_feedback: int,
    *,
    item_cuestionado: Optional[str] = None,
    score_sugerido: Optional[float] = None,
    nivel_sugerido: Optional[str] = None,
    motivo: Optional[str] = None,
    evidencia_supervisor: Optional[str] = None,
    solicitado_por: Optional[str] = None,
) -> Dict:
    ensure_tabla_feedback()
    feedback = obtener_feedback(id_feedback)
    motivo_limpio = limpiar_texto(motivo)
    if not motivo_limpio:
        raise ValueError("Ingresa el motivo de la solicitud de recalibracion.")

    score_actual = feedback.get("score_calidad_ia")
    if score_actual is None:
        score_actual = feedback.get("score_calidad")

    with engine_siscob.begin() as conn:
        id_recalibracion = int(conn.execute(text("""
            INSERT INTO CobAuto.dbo.ia_feedback_recalibraciones
                (id_feedback, score_ia, nivel_ia, item_cuestionado, score_sugerido,
                 nivel_sugerido, motivo, evidencia_supervisor, solicitado_por, estado)
            OUTPUT INSERTED.id_recalibracion
            VALUES
                (:id_feedback, :score_ia, :nivel_ia, :item_cuestionado, :score_sugerido,
                 :nivel_sugerido, :motivo, :evidencia_supervisor, :solicitado_por, 'PENDIENTE')
        """), {
            "id_feedback": id_feedback,
            "score_ia": score_actual,
            "nivel_ia": feedback.get("nivel_ia") or feedback.get("nivel_oportunidad_mejora"),
            "item_cuestionado": limpiar_texto(item_cuestionado),
            "score_sugerido": normalizar_score_sugerido(score_sugerido),
            "nivel_sugerido": limpiar_texto(nivel_sugerido),
            "motivo": motivo_limpio,
            "evidencia_supervisor": limpiar_texto(evidencia_supervisor),
            "solicitado_por": limpiar_texto(solicitado_por),
        }).scalar())
        conn.execute(text("""
            UPDATE CobAuto.dbo.ia_feedback_llamadas
            SET estado_recalibracion = 'PENDIENTE'
            WHERE id_feedback = :id_feedback
        """), {"id_feedback": id_feedback})

    registrar_historial_feedback(
        id_feedback,
        "RECALIBRACION_SOLICITADA",
        f"Solicitud de recalibracion sobre {limpiar_texto(item_cuestionado) or 'evaluacion general'}.",
        usuario=limpiar_texto(solicitado_por),
        valor_anterior=str(score_actual) if score_actual is not None else None,
        valor_nuevo=str(score_sugerido) if score_sugerido is not None else None,
    )
    return {
        "ok": True,
        "id_recalibracion": id_recalibracion,
        "feedback": obtener_feedback(id_feedback),
    }


def listar_recalibraciones_feedback(id_feedback: int) -> List[Dict]:
    ensure_tabla_feedback()
    query = text("""
        SELECT id_recalibracion, id_feedback, score_ia, nivel_ia, item_cuestionado,
               score_sugerido, nivel_sugerido, motivo, evidencia_supervisor,
               solicitado_por, fecha_solicitud, estado, resuelto_por,
               fecha_resolucion, motivo_resolucion, score_final
        FROM CobAuto.dbo.ia_feedback_recalibraciones WITH(NOLOCK)
        WHERE id_feedback = :id_feedback
        ORDER BY fecha_solicitud DESC, id_recalibracion DESC
    """)
    with engine_siscob.connect() as conn:
        rows = conn.execute(query, {"id_feedback": id_feedback}).mappings().all()
    return [serializar(dict(row)) for row in rows]


def resolver_recalibracion_feedback(
    id_recalibracion: int,
    *,
    estado: Optional[str] = None,
    score_final: Optional[float] = None,
    motivo_resolucion: Optional[str] = None,
    resuelto_por: Optional[str] = None,
) -> Dict:
    ensure_tabla_feedback()
    estado_final = str(estado or "APROBADA").strip().upper()
    if estado_final not in {"APROBADA", "RECHAZADA", "CERRADA"}:
        raise ValueError("Estado de recalibracion no valido.")

    motivo = limpiar_texto(motivo_resolucion)
    if not motivo:
        raise ValueError("Ingresa el motivo de resolucion de la recalibracion.")

    score = normalizar_score_sugerido(score_final)
    with engine_siscob.begin() as conn:
        row = conn.execute(text("""
            SELECT TOP 1 id_recalibracion, id_feedback, score_ia, score_sugerido
            FROM CobAuto.dbo.ia_feedback_recalibraciones WITH(UPDLOCK, ROWLOCK)
            WHERE id_recalibracion = :id_recalibracion
        """), {"id_recalibracion": id_recalibracion}).mappings().first()
        if not row:
            raise ValueError("Solicitud de recalibracion no encontrada.")

        id_feedback = int(row.get("id_feedback"))
        nota_resuelta = score
        if nota_resuelta is None and estado_final == "APROBADA":
            nota_resuelta = normalizar_score_sugerido(row.get("score_sugerido"))

        conn.execute(text("""
            UPDATE CobAuto.dbo.ia_feedback_recalibraciones
            SET estado = :estado,
                score_final = :score_final,
                motivo_resolucion = :motivo_resolucion,
                resuelto_por = :resuelto_por,
                fecha_resolucion = GETDATE()
            WHERE id_recalibracion = :id_recalibracion
        """), {
            "id_recalibracion": id_recalibracion,
            "estado": estado_final,
            "score_final": nota_resuelta,
            "motivo_resolucion": motivo,
            "resuelto_por": limpiar_texto(resuelto_por),
        })
        update_score = ""
        params = {
            "id_feedback": id_feedback,
            "estado_recalibracion": estado_final,
        }
        if nota_resuelta is not None and estado_final == "APROBADA":
            update_score = ", score_supervisor = :score_final, score_final = :score_final, score_calidad = :score_final"
            params["score_final"] = nota_resuelta
        conn.execute(text(f"""
            UPDATE CobAuto.dbo.ia_feedback_llamadas
            SET estado_recalibracion = :estado_recalibracion
                {update_score}
            WHERE id_feedback = :id_feedback
        """), params)

    registrar_historial_feedback(
        id_feedback,
        "RECALIBRACION_RESUELTA",
        f"Recalibracion {estado_final}: {motivo}",
        usuario=limpiar_texto(resuelto_por),
        valor_anterior=str(row.get("score_ia")) if row.get("score_ia") is not None else None,
        valor_nuevo=str(nota_resuelta) if nota_resuelta is not None else None,
    )
    return obtener_feedback(id_feedback)


def guardar_coaching_feedback(
    id_feedback: int,
    *,
    estado: Optional[str] = None,
    feedback_supervisor: Optional[str] = None,
    compromiso_agente: Optional[str] = None,
    fecha_programada: Optional[str] = None,
    resultado: Optional[str] = None,
    responsable: Optional[str] = None,
) -> Dict:
    ensure_tabla_feedback()
    feedback = obtener_feedback(id_feedback)
    estado_norm = str(estado or "PENDIENTE").strip().upper()
    if estado_norm not in {"PENDIENTE", "PROGRAMADO", "EN_PROCESO", "REALIZADO", "CERRADO"}:
        estado_norm = "PENDIENTE"

    fecha_prog = normalizar_fecha_llamada(fecha_programada)
    with engine_siscob.begin() as conn:
        conn.execute(text("""
            INSERT INTO CobAuto.dbo.ia_feedback_coaching
                (id_feedback, estado, feedback_ia, feedback_supervisor, compromiso_agente,
                 fecha_programada, fecha_realizada, responsable, resultado, usuario_creacion)
            VALUES
                (:id_feedback, :estado, :feedback_ia, :feedback_supervisor, :compromiso_agente,
                 :fecha_programada, CASE WHEN :estado IN ('REALIZADO', 'CERRADO') THEN GETDATE() ELSE NULL END,
                 :responsable, :resultado, :responsable)
        """), {
            "id_feedback": id_feedback,
            "estado": estado_norm,
            "feedback_ia": feedback.get("recomendaciones"),
            "feedback_supervisor": limpiar_texto(feedback_supervisor),
            "compromiso_agente": limpiar_texto(compromiso_agente),
            "fecha_programada": fecha_prog,
            "responsable": limpiar_texto(responsable),
            "resultado": limpiar_texto(resultado),
        })
        conn.execute(text("""
            UPDATE CobAuto.dbo.ia_feedback_llamadas
            SET estado_coaching = :estado,
                fecha_coaching = CASE WHEN :estado IN ('REALIZADO', 'CERRADO') THEN GETDATE() ELSE :fecha_programada END,
                responsable_coaching = :responsable,
                compromiso_agente = :compromiso_agente,
                resultado_coaching = :resultado
            WHERE id_feedback = :id_feedback
        """), {
            "id_feedback": id_feedback,
            "estado": estado_norm,
            "fecha_programada": fecha_prog,
            "responsable": limpiar_texto(responsable),
            "compromiso_agente": limpiar_texto(compromiso_agente),
            "resultado": limpiar_texto(resultado),
        })

    registrar_historial_feedback(
        id_feedback,
        "COACHING",
        f"Coaching registrado con estado {estado_norm}.",
        usuario=limpiar_texto(responsable),
        valor_nuevo=limpiar_texto(resultado) or limpiar_texto(feedback_supervisor),
    )
    return obtener_feedback(id_feedback)


def listar_coaching_feedback(id_feedback: int) -> List[Dict]:
    ensure_tabla_feedback()
    query = text("""
        SELECT id_coaching, id_feedback, estado, feedback_ia, feedback_supervisor,
               compromiso_agente, fecha_programada, fecha_realizada, responsable,
               resultado, usuario_creacion, fecha_creacion, usuario_cierre, fecha_cierre
        FROM CobAuto.dbo.ia_feedback_coaching WITH(NOLOCK)
        WHERE id_feedback = :id_feedback
        ORDER BY fecha_creacion DESC, id_coaching DESC
    """)
    with engine_siscob.connect() as conn:
        rows = conn.execute(query, {"id_feedback": id_feedback}).mappings().all()
    return [serializar(dict(row)) for row in rows]


def listar_historial_feedback(id_feedback: int) -> List[Dict]:
    ensure_tabla_feedback()
    query = text("""
        SELECT id_historial, id_feedback, accion, descripcion, valor_anterior,
               valor_nuevo, usuario, fecha
        FROM CobAuto.dbo.ia_feedback_historial WITH(NOLOCK)
        WHERE id_feedback = :id_feedback
        ORDER BY fecha DESC, id_historial DESC
    """)
    with engine_siscob.connect() as conn:
        rows = conn.execute(query, {"id_feedback": id_feedback}).mappings().all()
    return [serializar(dict(row)) for row in rows]


def registrar_historial_feedback(
    id_feedback: int,
    accion: str,
    descripcion: Optional[str] = None,
    *,
    usuario: Optional[str] = None,
    valor_anterior: Optional[str] = None,
    valor_nuevo: Optional[str] = None,
):
    ensure_tabla_feedback()
    with engine_siscob.begin() as conn:
        conn.execute(text("""
            INSERT INTO CobAuto.dbo.ia_feedback_historial
                (id_feedback, accion, descripcion, valor_anterior, valor_nuevo, usuario)
            VALUES
                (:id_feedback, :accion, :descripcion, :valor_anterior, :valor_nuevo, :usuario)
        """), {
            "id_feedback": id_feedback,
            "accion": limpiar_texto(accion) or "EVENTO",
            "descripcion": limpiar_texto(descripcion),
            "valor_anterior": valor_anterior,
            "valor_nuevo": valor_nuevo,
            "usuario": limpiar_texto(usuario),
        })


def preparar_resumen(row: Dict) -> Dict:
    data = serializar(row)
    if data.get("score_final") is not None:
        data["score_calidad"] = data.get("score_final")
    elif data.get("score_normalizado") is not None:
        data["score_calidad"] = data.get("score_normalizado")
    data["nivel_oportunidad_mejora"] = data.get("nivel_riesgo") or data.get("nivel_oportunidad_mejora")
    data["total_puntos_criticos"] = len(cargar_json_lista(data.get("puntos_criticos")))
    data["falta_anulante"] = bool(data.get("falta_anulante"))
    data["error_critico"] = bool(data.get("error_critico"))
    data = enriquecer_sgc_registro(data)
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


def cargar_json_dict(value) -> Dict:
    if not value:
        return {}
    if isinstance(value, dict):
        return value
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def enriquecer_sgc_registro(data: Dict) -> Dict:
    evaluacion = data.get("evaluacion_calidad_lista")
    if evaluacion is None:
        evaluacion = cargar_json_lista(data.get("evaluacion_calidad"))
    score_final = data.get("score_final")
    if score_final is None:
        score_final = data.get("score_normalizado")
    if score_final is None:
        score_final = data.get("score_calidad")
    try:
        score_final_num = float(score_final) if score_final is not None else None
    except Exception:
        score_final_num = None
    evaluacion = enriquecer_evaluacion_sgc(
        evaluacion,
        score_final=score_final_num,
        nivel_riesgo=data.get("nivel_riesgo") or data.get("nivel_oportunidad_mejora"),
        falta_anulante=bool(data.get("falta_anulante")),
    )
    resumen_sgc = cargar_json_dict(data.get("resumen_sgc"))
    json_copc_v2 = resumen_sgc.get("json_copc_v2") if isinstance(resumen_sgc, dict) else {}
    if isinstance(json_copc_v2, dict) and str(resumen_sgc.get("version_evaluacion") or data.get("version_evaluacion") or "").startswith("2"):
        evaluacion = reparar_evaluacion_contextual_v2(evaluacion, json_copc_v2, data.get("transcripcion") or "")
        score_bruto_ctx, peso_ctx, score_ctx = calcular_score_normalizado(evaluacion)
        data["score_bruto"] = score_bruto_ctx
        data["peso_aplicable"] = peso_ctx
        data["score_normalizado"] = score_ctx
        if not data.get("score_final") or str(data.get("estado_revision") or "").upper() == "PENDIENTE":
            data["score_final"] = score_ctx
        score_final_num = score_ctx
    resumen_sgc = construir_resumen_sgc(
        evaluacion,
        resumen_sgc,
        score_final=score_final_num,
        nivel_riesgo=data.get("nivel_riesgo") or data.get("nivel_oportunidad_mejora"),
        falta_anulante=bool(data.get("falta_anulante")),
    )
    data["evaluacion_calidad_lista"] = evaluacion
    data["resumen_sgc"] = resumen_sgc
    data["version_evaluacion"] = resumen_sgc.get("version_evaluacion")
    data["estado_tecnico"] = resumen_sgc.get("estado_tecnico")
    data["tipificaciones_sugeridas"] = resumen_sgc.get("tipificaciones_sugeridas") or []
    data["feedback_asesor"] = resumen_sgc.get("feedback_asesor") or {}
    data["audio_url"] = f"/ia-feedback/{data.get('id_feedback')}/audio" if data.get("id_feedback") and data.get("ruta_archivo") else None
    if isinstance(json_copc_v2, dict):
        interlocutores = json_copc_v2.get("interlocutores") if isinstance(json_copc_v2.get("interlocutores"), dict) else {}
        segmentos = interlocutores.get("segmentos") if isinstance(interlocutores.get("segmentos"), list) else []
        if not segmentos:
            interlocutores = normalizar_interlocutores_v2(json_copc_v2, data.get("transcripcion") or "")
            segmentos = interlocutores.get("segmentos") if isinstance(interlocutores.get("segmentos"), list) else []
        data["interlocutores"] = interlocutores
        data["segmentos_interlocutores"] = segmentos
    else:
        interlocutores = normalizar_interlocutores_v2({}, data.get("transcripcion") or "")
        data["interlocutores"] = interlocutores
        data["segmentos_interlocutores"] = interlocutores.get("segmentos", [])
    data["requiere_feedback"] = bool(data.get("requiere_feedback") or resumen_sgc.get("requiere_feedback"))
    data["requiere_coaching"] = bool(data.get("requiere_coaching") or resumen_sgc.get("requiere_coaching"))
    data["estado_feedback"] = data.get("estado_feedback") or ("PENDIENTE" if data["requiere_feedback"] else "NO_REQUIERE")
    return data


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


def normalizar_score_sugerido(value) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        return round(min(max(float(value), 0), 100), 2)
    except (TypeError, ValueError):
        raise ValueError("La nota sugerida debe ser un numero entre 0 y 100.")


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
