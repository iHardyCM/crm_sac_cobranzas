from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Dict, List, Optional
from uuid import uuid4

from sqlalchemy import text

from app.core.db_siscob import engine_siscob
from app.services.ia_analysis_service import (
    analizar_transcripcion_mock,
    analizar_transcripcion_real,
    aplicar_guardas_deterministicas_criterios,
    calcular_pesos_detalle_evaluacion,
    calcular_score_normalizado,
    completar_evidencias_desde_segmentos_v3,
    consolidar_puntos_sgc,
    construir_resumen_sgc,
    deduplicar_puntos_criticos,
    enriquecer_evaluacion_sgc,
    generar_transcripcion_mock,
    ia_real_configurada,
    normalizar_hallazgos_no_criticos_v2,
    normalizar_interlocutores_v2,
    reparar_evaluacion_contextual_v2,
    transcribir_audio_real,
)


logger = logging.getLogger(__name__)

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

        IF COL_LENGTH('CobAuto.dbo.ia_feedback_llamadas', 'peso_total') IS NULL
            ALTER TABLE CobAuto.dbo.ia_feedback_llamadas
            ADD peso_total DECIMAL(5,2) NULL;

        IF COL_LENGTH('CobAuto.dbo.ia_feedback_llamadas', 'peso_aplicable') IS NULL
            ALTER TABLE CobAuto.dbo.ia_feedback_llamadas
            ADD peso_aplicable DECIMAL(5,2) NULL;

        IF COL_LENGTH('CobAuto.dbo.ia_feedback_llamadas', 'peso_no_aplica') IS NULL
            ALTER TABLE CobAuto.dbo.ia_feedback_llamadas
            ADD peso_no_aplica DECIMAL(5,2) NULL;

        IF COL_LENGTH('CobAuto.dbo.ia_feedback_llamadas', 'peso_no_evaluable') IS NULL
            ALTER TABLE CobAuto.dbo.ia_feedback_llamadas
            ADD peso_no_evaluable DECIMAL(5,2) NULL;

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
        "modelo_transcripcion": os.getenv("IA_FEEDBACK_DIARIZATION_MODEL")
        or (
            os.getenv("IA_FEEDBACK_TRANSCRIPTION_MODEL")
            if "diarize" in str(os.getenv("IA_FEEDBACK_TRANSCRIPTION_MODEL") or "").lower()
            else "gpt-4o-transcribe-diarize"
        ),
        "modelo_transcripcion_fallback": os.getenv("IA_FEEDBACK_TRANSCRIPTION_FALLBACK_MODEL")
        or (
            os.getenv("IA_FEEDBACK_TRANSCRIPTION_MODEL")
            if "diarize" not in str(os.getenv("IA_FEEDBACK_TRANSCRIPTION_MODEL") or "").lower()
            else "gpt-4o-mini-transcribe"
        ),
        "modelo_analisis": os.getenv("IA_FEEDBACK_ANALYSIS_MODEL", "gpt-4o-mini"),
    }


def transcripcion_diarizada_valida(transcripcion: Optional[str]) -> bool:
    texto = str(transcripcion or "").strip()
    if not texto.startswith("#TRANSCRIPCION_DIARIZADA_V1"):
        return False
    try:
        interlocutores = normalizar_interlocutores_v2({}, texto)
    except Exception:
        return False
    segmentos = interlocutores.get("segmentos") if isinstance(interlocutores, dict) else []
    if not isinstance(segmentos, list) or not segmentos:
        return False
    roles = {
        str(item.get("hablante") or item.get("rol") or "").upper()
        for item in segmentos
        if isinstance(item, dict)
    }
    return bool(roles & {"AGENTE", "CLIENTE"})


def obtener_transcripcion_para_analisis(registro: Dict, *, forzar_transcripcion: bool = False) -> tuple[str, bool]:
    """
    Devuelve la transcripción que debe usar el análisis.

    La transcripción diarizada guardada es la fuente canónica. Solo se llama al
    transcriptor cuando no existe, cuando se fuerza explícitamente o cuando la
    guardada es antigua/no canónica y la IA real está disponible.
    """
    transcripcion_guardada = str(registro.get("transcripcion") or "").strip()
    if not forzar_transcripcion and transcripcion_diarizada_valida(transcripcion_guardada):
        return transcripcion_guardada, False

    if ia_real_configurada():
        # FIX: se deja rastro del preproceso de audio (recorte de timbrado) para
        # poder correlacionarlo despues con los casos de diarizacion dudosa.
        info_preproceso: Dict = {}
        transcripcion = transcribir_audio_real(
            registro.get("ruta_archivo") or "", info_preproceso
        )
        if info_preproceso.get("recortado"):
            logger.info(
                "IA feedback %s: se descartaron %.2fs de timbrado antes de transcribir (%s)",
                registro.get("id_feedback"),
                info_preproceso.get("segundos_descartados") or 0.0,
                info_preproceso.get("motivo") or "",
            )
        return transcripcion, True

    if transcripcion_guardada:
        return transcripcion_guardada, False

    return generar_transcripcion_mock(registro), True


def analizar_feedback(id_feedback: int, forzar_transcripcion: bool = False) -> Dict:
    ensure_tabla_feedback()
    # Cronometro por fase. Sin esto, "el analisis tarda cinco minutos" no se
    # puede atacar: no se sabe si el tiempo se va en transcribir, en el modelo
    # o en guardar, y cualquier optimizacion seria a ciegas.
    t_inicio = time.perf_counter()
    tiempos: Dict[str, float] = {}
    registro = obtener_feedback(id_feedback)
    tiempos["leer_registro"] = time.perf_counter() - t_inicio

    try:
        aviso_ia = None
        transcripcion_guardada = str(registro.get("transcripcion") or "").strip()
        reutiliza_transcripcion = (
            not forzar_transcripcion
            and transcripcion_diarizada_valida(transcripcion_guardada)
        )
        if not reutiliza_transcripcion:
            actualizar_estado(id_feedback, "TRANSCRIBIENDO")
        t_fase = time.perf_counter()
        transcripcion, transcripcion_generada = obtener_transcripcion_para_analisis(
            registro,
            forzar_transcripcion=forzar_transcripcion,
        )
        tiempos["transcripcion"] = time.perf_counter() - t_fase
        if transcripcion_generada:
            t_fase = time.perf_counter()
            actualizar_transcripcion(id_feedback, transcripcion)
            tiempos["guardar_transcripcion"] = time.perf_counter() - t_fase
        if not ia_real_configurada():
            aviso_ia = "IA real no configurada, usando analisis simulado"

        actualizar_estado(id_feedback, "ANALIZANDO")
        t_fase = time.perf_counter()
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
        tiempos["analisis_ia"] = time.perf_counter() - t_fase

        t_fase = time.perf_counter()
        guardar_analisis(id_feedback, analisis)
        tiempos["guardar_analisis"] = time.perf_counter() - t_fase

        t_fase = time.perf_counter()
        resultado = obtener_feedback(id_feedback)
        tiempos["releer_ficha"] = time.perf_counter() - t_fase

        total = time.perf_counter() - t_inicio
        detalle = " | ".join(f"{nombre}={valor:.1f}s" for nombre, valor in tiempos.items())
        logger.info(
            "[TIEMPOS] feedback=%s total=%.1fs | %s | transcripcion_%s",
            id_feedback, total, detalle,
            "nueva" if transcripcion_generada else "reutilizada",
        )
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


ESTADOS_EN_PROCESO = ("PENDIENTE", "EN_COLA", "TRANSCRIBIENDO", "ANALIZANDO")


def obtener_bandeja_supervisor(
    supervisor: Optional[str] = None,
    ver_todo: bool = False,
    limite: int = 150,
) -> Dict:
    """La bandeja de trabajo del supervisor: que esta en proceso y que falta revisar.

    Responde "y ahora que hago": cada llamada cargada termina aqui hasta que el
    supervisor la revisa. Vive en el servidor, asi que sobrevive a recargar la
    pagina o cambiar de equipo, a diferencia de una lista en el navegador.

    Incluye:
      - en proceso: cargadas que todavia se estan transcribiendo o evaluando.
      - con error:  el analisis fallo y hay que reintentarlo.
      - por revisar: analizadas, sin revision del supervisor.
    Cada una lleva las senales que definen el siguiente paso: si falta el
    agente, si la IA pidio revision humana, si hay calibraciones en curso.
    """
    ensure_tabla_feedback()
    # La bandeja es el trabajo DEL DIA: lo cargado hoy. Lo pendiente de dias
    # anteriores no se lista aqui (se cuenta aparte y se trabaja desde
    # Evaluaciones > Por revisar). Lo que sigue en proceso o con error se mira
    # desde ayer, para no perder una carga que cruzo la medianoche.
    filtros = [
        f"""(
            (L.estado IN ({", ".join(f"'{e}'" for e in ESTADOS_EN_PROCESO)}, 'ERROR')
             AND L.fecha_creacion >= DATEADD(DAY, -1, CAST(GETDATE() AS DATE)))
            OR (L.estado = 'FINALIZADO' AND ISNULL(L.estado_revision, 'PENDIENTE') = 'PENDIENTE'
                AND L.fecha_creacion >= CAST(GETDATE() AS DATE))
        )""",
    ]
    params: Dict = {"limite": int(limite)}
    filtro_supervisor = ""
    if not ver_todo and limpiar_texto(supervisor):
        filtro_supervisor = " AND LTRIM(RTRIM(ISNULL(L.supervisor, ''))) = :supervisor"
        filtros.append(filtro_supervisor.replace(" AND ", "", 1))
        params["supervisor"] = limpiar_texto(supervisor)

    query = text(f"""
        SELECT TOP (:limite)
            L.id_feedback, L.archivo_nombre, L.agente, L.cartera, L.supervisor,
            L.fecha_llamada, L.fecha_creacion, L.fecha_analisis,
            L.estado, L.estado_revision, L.mensaje_error, L.requiere_revision_humana,
            L.score_final, L.score_calibrado, L.origen_score,
            cal_borrador = (SELECT COUNT(1) FROM CobAuto.dbo.CRM_IA_CALIBRACION_CRITERIO C
                            WHERE C.id_feedback = L.id_feedback AND C.estado = 'BORRADOR'),
            cal_en_revision = (SELECT COUNT(1) FROM CobAuto.dbo.CRM_IA_CALIBRACION_CRITERIO C
                               WHERE C.id_feedback = L.id_feedback AND C.estado = 'EN_REVISION')
        FROM CobAuto.dbo.ia_feedback_llamadas L WITH(NOLOCK)
        WHERE {" AND ".join(filtros)}
        ORDER BY L.fecha_creacion DESC, L.id_feedback DESC
    """)
    query_anteriores = text(f"""
        SELECT total = COUNT(1),
               sin_agente = SUM(CASE WHEN LTRIM(RTRIM(ISNULL(L.agente, ''))) = '' THEN 1 ELSE 0 END)
        FROM CobAuto.dbo.ia_feedback_llamadas L WITH(NOLOCK)
        WHERE L.estado = 'FINALIZADO'
          AND ISNULL(L.estado_revision, 'PENDIENTE') = 'PENDIENTE'
          AND L.fecha_creacion < CAST(GETDATE() AS DATE)
          {filtro_supervisor}
    """)
    with engine_siscob.connect() as conn:
        filas = conn.execute(query, params).mappings().all()
        anteriores = conn.execute(query_anteriores, {k: v for k, v in params.items() if k == "supervisor"}).mappings().first() or {}

    en_proceso, con_error, por_revisar = [], [], []
    for fila in filas:
        item = serializar(dict(fila))
        item["score_vigente"] = score_vigente_llamada(item)
        item["sin_agente"] = not limpiar_texto(item.get("agente"))
        estado = str(item.get("estado") or "").upper()
        if estado in ESTADOS_EN_PROCESO:
            en_proceso.append(item)
        elif estado == "ERROR":
            con_error.append(item)
        else:
            por_revisar.append(item)
    # Lo que acaba de terminar va arriba: es lo que el supervisor esta
    # esperando para abrir (antes iba al final y habia que bajar a buscarlo).
    por_revisar.sort(key=lambda i: (i.get("fecha_analisis") or i.get("fecha_creacion") or ""), reverse=True)
    return {
        "en_proceso": en_proceso,
        "con_error": con_error,
        "por_revisar": por_revisar,
        "resumen": {
            "en_proceso": len(en_proceso),
            "con_error": len(con_error),
            "por_revisar": len(por_revisar),
            "sin_agente": sum(1 for i in por_revisar if i["sin_agente"]),
            "anteriores_por_revisar": int(anteriores.get("total") or 0),
            "anteriores_sin_agente": int(anteriores.get("sin_agente") or 0),
        },
    }


def score_vigente_llamada(row: Dict) -> Optional[float]:
    """La nota que vale para una llamada.

    Regla del modulo de calibracion: solo una calibracion PUBLICADA mueve la
    nota. Si existe, manda; si no, vale la de la IA. Centralizarlo aqui evita
    que la ficha muestre una nota y los reportes promedien otra.
    """
    calibrado = row.get("score_calibrado")
    if calibrado is not None and str(row.get("origen_score") or "").upper() == "CALIBRACION":
        return float(calibrado)
    for campo in ("score_final", "score_calidad"):
        valor = row.get(campo)
        if valor is not None:
            return float(valor)
    return None


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
            requiere_feedback, requiere_coaching, fecha_coaching,
            score_calibrado, origen_score
        FROM CobAuto.dbo.ia_feedback_llamadas WITH(NOLOCK)
        WHERE {where_sql}
        ORDER BY fecha_creacion DESC, id_feedback DESC
    """.format(where_sql=" AND ".join(filtros)))

    with engine_siscob.connect() as conn:
        rows = conn.execute(query, params).mappings().all()

    total = len(rows)
    # Promedio sobre la nota VIGENTE: la calibrada si Calidad la publico.
    scores = [valor for valor in (score_vigente_llamada(row) for row in rows) if valor is not None]
    segmentos = {}
    items = {}
    carteras = {}
    agentes = {}
    semanas = {}
    sgc_grupos = {}
    sgc_factores = {}
    detalle = []
    total_ceros = 0

    # Una llamada sin score NO se pudo medir. Antes caia en float(... or 0) y
    # entraba a los promedios como un cero, hundiendo la media del asesor, de
    # la cartera y de la semana con una nota que nadie calculo. Ahora queda
    # fuera de los agregados y se cuenta aparte, para que el reporte pueda
    # decir sobre cuantas llamadas se calculo realmente el promedio.
    no_evaluables = 0
    for row in rows:
        score = score_vigente_llamada(row)
        cartera = str(row.get("cartera") or "Sin cartera")
        agente = str(row.get("agente") or "Sin agente asociado")
        supervisor_row = str(row.get("supervisor") or "Sin supervisor")
        semana = clave_semana(row.get("fecha_creacion"))
        if score is None:
            no_evaluables += 1
        else:
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
            "score_calidad_ia": float(row["score_calidad_ia"]) if row.get("score_calidad_ia") is not None else score,
            "score_supervisor": float(row.get("score_supervisor")) if row.get("score_supervisor") is not None else None,
            "score_final": score,
            "score_normalizado": float(row["score_normalizado"]) if row.get("score_normalizado") is not None else score,
            "evaluable": score is not None,
            # La nota de la IA se conserva aparte: es contra lo que se mide la
            # calibracion. score_final ya refleja la vigente.
            "score_ia": float(row["score_final"]) if row.get("score_final") is not None else None,
            "score_calibrado": float(row["score_calibrado"]) if row.get("score_calibrado") is not None else None,
            "origen_score": str(row.get("origen_score") or "IA"),
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

        # La llamada aparece en el detalle -es real y hay que poder verla- pero
        # NO alimenta las estadisticas agregadas. En una llamada no evaluable
        # todos los criterios tienen nota 0 porque no se midieron, no porque
        # fallaran: contarlos como "items en cero" inflaria las brechas por
        # segmento y por item con incumplimientos que nunca se observaron.
        # (Ademas, sus cubos de cartera/agente/semana no existen, porque
        # acumular_score solo se llama para las medibles.)
        if score is None:
            continue

        for item in evaluacion:
            if not isinstance(item, dict):
                continue
            # Misma regla que el score: un criterio que no se midio (No aplica,
            # No evaluable, Requiere revision) no entra al cumplimiento por
            # segmento/item ni se cuenta como brecha. Antes su nota 0 se sumaba
            # como "cero" y su peso al denominador, y Tipificacion y Tono de voz
            # -No evaluables por diseno- salian como brecha en el 100% de las
            # llamadas.
            if _estado_criterio_para_agregado(item) in ESTADOS_FUERA_DEL_AGREGADO:
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
        # Sobre cuantas llamadas se calculo realmente el promedio. Un promedio
        # sin este dato no dice si se midio el 100% o el 60% de lo evaluado.
        "audios_con_score": len(scores),
        "audios_sin_score": no_evaluables,
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
            peso_total, peso_aplicable, peso_no_aplica, peso_no_evaluable,
            score_normalizado, estado_calidad, nivel_riesgo,
            error_critico, calidad_transcripcion, confianza_evaluacion,
            requiere_revision_humana, motivo_revision,
            evaluacion_calidad, habilidades_blandas, fortalezas, puntos_criticos, recomendaciones, guion_sugerido, alertas,
            evidencias_clave, nivel_oportunidad_mejora, comentario_supervisor, estado_revision,
            comentario_feedback, revisado_por, mensaje_error, nivel_ia,
            falta_anulante, frase_anulante, momento_falta_anulante, estado_recalibracion,
            estado_coaching, fecha_coaching, responsable_coaching, compromiso_agente, resultado_coaching,
            resumen_sgc, estado_feedback, requiere_feedback, requiere_coaching,
            fecha_creacion, fecha_analisis, fecha_revision,
            score_calibrado, origen_score
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
    # Despues de enriquecer: esa funcion puede recalcular score_final, y la
    # nota vigente debe salir de los valores definitivos.
    data["score_vigente"] = score_vigente_llamada(data)
    return data


def obtener_estado_feedback(id_feedback: int) -> Dict:
    """Estado del procesamiento, sin cargar la ficha completa.

    La pantalla lo consulta cada pocos segundos mientras la llamada se procesa.
    obtener_feedback es pesada -relee JSON y re-ejecuta las guardas-; hacerla
    cada 4 segundos por cada llamada en curso cargaria al servidor sin motivo.
    """
    with engine_siscob.connect() as conn:
        fila = conn.execute(text("""
            SELECT id_feedback, estado, mensaje_error, agente, cartera,
                   score_final, score_calibrado, origen_score, fecha_analisis
            FROM CobAuto.dbo.ia_feedback_llamadas WITH(NOLOCK)
            WHERE id_feedback = :id_feedback
        """), {"id_feedback": id_feedback}).mappings().first()
    if not fila:
        raise ValueError("Analisis IA no encontrado.")
    data = serializar(dict(fila))
    data["score_vigente"] = score_vigente_llamada(data)
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
                peso_total = :peso_total,
                peso_aplicable = :peso_aplicable,
                peso_no_aplica = :peso_no_aplica,
                peso_no_evaluable = :peso_no_evaluable,
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
            "peso_total": analisis.get("peso_total"),
            "peso_aplicable": analisis.get("peso_aplicable"),
            "peso_no_aplica": analisis.get("peso_no_aplica"),
            "peso_no_evaluable": analisis.get("peso_no_evaluable"),
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
    # La evaluacion por criterio se persiste aqui, al cerrar el analisis. Si la
    # llamada ya tenia sus criterios escritos, esto NO los pisa (inmutabilidad).
    # Un fallo aqui no puede tumbar el analisis, que ya quedo guardado arriba:
    # se registra y se sigue.
    try:
        escritas = persistir_evaluacion_criterios(id_feedback, analisis)
        if escritas:
            logger.info("[CRITERIOS] feedback=%s filas=%s", id_feedback, escritas)
    except Exception:
        logger.exception("[CRITERIOS] no se pudo persistir la evaluacion por criterio (feedback=%s)", id_feedback)

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


RESULTADOS_IA_VALIDOS = {"CUMPLE", "NO_CUMPLE", "NO_APLICA", "NO_EVALUABLE", "REQUIERE_REVISION"}


def _resultado_ia_normalizado(item: Dict) -> str:
    """Devuelve el estado tecnico del criterio, no el texto de pantalla."""
    estado = str(item.get("estado") or item.get("estado_tecnico") or "").strip().upper().replace(" ", "_")
    if estado in RESULTADOS_IA_VALIDOS:
        return estado
    texto = str(item.get("resultado") or item.get("calificacion") or "").strip().lower()
    if "no evaluable" in texto:
        return "NO_EVALUABLE"
    if "no aplica" in texto:
        return "NO_APLICA"
    if "revisi" in texto:
        return "REQUIERE_REVISION"
    if "no cumple" in texto or "no evidenciado" in texto:
        return "NO_CUMPLE"
    if "cumple" in texto:
        return "CUMPLE"
    return "REQUIERE_REVISION"


def _hablante_evidencia(item: Dict) -> Optional[str]:
    """Solo se declara el hablante cuando la evidencia viene de un segmento."""
    valor = str(item.get("evidencia_hablante") or item.get("hablante") or "").strip().upper()
    if valor in {"AGENTE", "CLIENTE"}:
        return valor
    if not item.get("segmentos_evidencia"):
        return None
    return "INDETERMINADO"


def _texto_evidencia(item: Dict) -> Optional[str]:
    """Une las citas del criterio con el mismo separador que usa la ficha.

    Un criterio puede sustentarse en mas de un segmento. Guardar solo el
    primero perderia parte del sustento justo en la tabla con la que despues
    se mide la precision, asi que se guardan todas. Cuando la conclusion es
    por ausencia no hay nada que citar y la columna queda NULL, que es lo
    correcto: NULL significa "no hay cita", no "no se reviso".
    """
    textual = item.get("evidencia_textual")
    if isinstance(textual, list) and textual:
        partes = [str(x).strip() for x in textual if str(x or "").strip()]
        if partes:
            return " | ".join(partes)
    evidencia = str(item.get("evidencia") or "").strip()
    return evidencia if evidencia and evidencia != "-" else None


def _numero_o_none(value):
    try:
        return float(value) if value is not None and str(value).strip() != "" else None
    except (TypeError, ValueError):
        return None


def _entero_o_none(value):
    """int() directo revienta con "2.0", que es como quedo guardada la version
    en varias evaluaciones. Se pasa por float para no perder el dato en silencio."""
    if value is None or str(value).strip() == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        pass
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return None


def _resolver_id_pauta(conn, nombre, version) -> Optional[int]:
    """Busca la pauta real por (nombre, version), que es UNIQUE en CRM_IA_PAUTA.

    POR QUE HACE FALTA
    "pauta" y "pauta_version" tambien se llenan con los valores de respaldo de
    las matrices fijas -COPC_SGC v2.0, MIBANCO v1.0-, que NO son pautas de la
    tabla. Si esas versiones se guardaran como pauta_version, el reporte de
    precision agruparia la matriz fija COPC v2.0 junto a la pauta publicada v2,
    que son cosas distintas.

    Por eso la unica fuente valida es la tabla: si (nombre, version) existe,
    hay pauta; si no existe, no hay pauta y no se inventa ninguna.
    """
    nombre_limpio = str(nombre or "").strip()
    version_num = _entero_o_none(version)
    if not nombre_limpio or version_num is None:
        return None
    fila = conn.execute(text("""
        SELECT id_pauta
        FROM CobAuto.dbo.CRM_IA_PAUTA
        WHERE nombre = :nombre AND version = :version
    """), {"nombre": nombre_limpio, "version": version_num}).scalar()
    return int(fila) if fila is not None else None


def persistir_evaluacion_criterios(id_feedback: int, analisis: Dict, rehacer: bool = False) -> int:
    """Escribe el resultado de la IA por criterio en CRM_IA_EVALUACION_CRITERIO.

    POR QUE EXISTE
    Esa tabla es contra la que se mide la precision de la IA: una fila por
    (id_feedback, codigo_criterio), con la definicion del criterio congelada al
    momento del analisis. calibracion_service la lee en cinco consultas.

    REGLA DE INMUTABILIDAD
    El DDL la declara INMUTABLE y esa regla se respeta: si la evaluacion ya
    tiene filas, NO se reescriben. Medir precision contra un resultado que
    cambia despues de que el supervisor lo califico no mide nada.

    La unica excepcion es rehacer=True, pensada para iterar durante el
    desarrollo, y ni siquiera esa toca una evaluacion que ya tenga
    calibraciones humanas: en ese caso se rechaza y no se escribe nada.

    Devuelve la cantidad de filas escritas (0 si ya existian y no se rehace).
    """
    criterios = analisis.get("evaluacion_calidad") or []
    if not isinstance(criterios, list) or not criterios:
        return 0

    filas = []
    vistos = set()
    for item in criterios:
        if not isinstance(item, dict):
            continue
        codigo = str(item.get("codigo_criterio") or item.get("codigo") or "").strip()
        if not codigo or codigo in vistos:
            # La tabla tiene UNIQUE (id_feedback, codigo_criterio): un duplicado
            # reventaria el INSERT completo. Se queda la primera aparicion.
            continue
        vistos.add(codigo)
        filas.append({
            "id_feedback": id_feedback,
            "id_pauta": None,   # se resuelve abajo, con conexion
            "pauta_version": None,
            "codigo_bloque": limpiar_texto(item.get("bloque")),
            "nombre_bloque": limpiar_texto(item.get("bloque_nombre") or item.get("subcategoria")),
            "codigo_criterio": codigo[:80],
            "nombre_criterio": limpiar_texto(item.get("nombre") or item.get("item")),
            "tipo_criterio": limpiar_texto(item.get("tipo_criterio") or "PUNTUABLE"),
            "peso": _numero_o_none(item.get("peso")),
            "fuente_evidencia": limpiar_texto(item.get("fuente_evidencia")),
            "resultado_ia": _resultado_ia_normalizado(item),
            "puntaje_obtenido": _numero_o_none(item.get("nota") if item.get("nota") is not None else item.get("puntaje_obtenido")),
            "bloque_anulado": 1 if item.get("bloque_anulado") else 0,
            "confianza_ia": limpiar_texto(item.get("confianza")),
            "motivo_ia": limpiar_texto(item.get("motivo") or item.get("hallazgo")),
            "recomendacion_ia": limpiar_texto(item.get("recomendacion") or item.get("recomendacion_entrenable")),
            "evidencia_texto": _texto_evidencia(item),
            "evidencia_hablante": _hablante_evidencia(item),
            "momento_llamada": limpiar_texto(item.get("momento")),
        })

    if not filas:
        return 0

    with engine_siscob.begin() as conn:
        # id_pauta manda: si el analisis no lo trae -las evaluaciones viejas no
        # lo guardaban-, se resuelve por (nombre, version) contra CRM_IA_PAUTA.
        # Y si no hay pauta identificable, la VERSION tampoco se guarda: un
        # numero de version sin pauta no es agrupable y solo confundiria el
        # reporte de precision.
        id_pauta = _entero_o_none(analisis.get("id_pauta"))
        if id_pauta is None:
            id_pauta = _resolver_id_pauta(conn, analisis.get("pauta"), analisis.get("pauta_version"))
        pauta_version = _entero_o_none(analisis.get("pauta_version")) if id_pauta is not None else None
        for fila in filas:
            fila["id_pauta"] = id_pauta
            fila["pauta_version"] = pauta_version

        existentes = int(conn.execute(text("""
            SELECT COUNT(1)
            FROM CobAuto.dbo.CRM_IA_EVALUACION_CRITERIO
            WHERE id_feedback = :id_feedback
        """), {"id_feedback": id_feedback}).scalar() or 0)

        if existentes and not rehacer:
            return 0

        if existentes:
            calibradas = int(conn.execute(text("""
                SELECT COUNT(1)
                FROM CobAuto.dbo.CRM_IA_CALIBRACION_CRITERIO
                WHERE id_feedback = :id_feedback
            """), {"id_feedback": id_feedback}).scalar() or 0)
            if calibradas:
                raise ValueError(
                    f"La evaluacion {id_feedback} ya tiene {calibradas} calibracion(es) humana(s): "
                    "su evaluacion IA no se puede rehacer sin invalidar esa medicion."
                )
            conn.execute(text("""
                DELETE FROM CobAuto.dbo.CRM_IA_EVALUACION_CRITERIO
                WHERE id_feedback = :id_feedback
            """), {"id_feedback": id_feedback})

        conn.execute(text("""
            INSERT INTO CobAuto.dbo.CRM_IA_EVALUACION_CRITERIO
                (id_feedback, id_pauta, pauta_version, codigo_bloque, nombre_bloque,
                 codigo_criterio, nombre_criterio, tipo_criterio, peso, fuente_evidencia,
                 resultado_ia, puntaje_obtenido, bloque_anulado, confianza_ia,
                 motivo_ia, recomendacion_ia,
                 evidencia_texto, evidencia_hablante, momento_llamada)
            VALUES
                (:id_feedback, :id_pauta, :pauta_version, :codigo_bloque, :nombre_bloque,
                 :codigo_criterio, :nombre_criterio, :tipo_criterio, :peso, :fuente_evidencia,
                 :resultado_ia, :puntaje_obtenido, :bloque_anulado, :confianza_ia,
                 :motivo_ia, :recomendacion_ia,
                 :evidencia_texto, :evidencia_hablante, :momento_llamada)
        """), filas)

    return len(filas)


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
            -- COALESCE: una revision que no trae agente NO lo borra. Antes
            -- era SET agente = :agente, y como la pantalla envia ese campo
            -- vacio, guardar cualquier revision dejaba el agente en NULL.
            SET agente = COALESCE(:agente, agente),
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


def asignar_agente_feedback(id_feedback: int, agente: Optional[str], usuario: Optional[str] = None) -> Dict:
    """Asigna o corrige el agente evaluado en una llamada.

    El agente es la unidad de todo lo que viene despues -desempeno, planes de
    mejora, reportes por asesor-. Sin el, cada evaluacion queda suelta. Por eso
    tiene su propia operacion, con traza en el historial, en vez de viajar
    escondido dentro de la revision del supervisor.

    Formato: "USUARIO - Nombres Apellidos", la misma convencion que ya usa el
    campo supervisor, para que agrupar por agente sea estable.
    """
    ensure_tabla_feedback()
    anterior = obtener_feedback(id_feedback)
    agente_limpio = limpiar_texto(agente)
    if not agente_limpio:
        raise ValueError("Indica el agente a asignar.")

    with engine_siscob.begin() as conn:
        conn.execute(text("""
            UPDATE CobAuto.dbo.ia_feedback_llamadas
            SET agente = :agente
            WHERE id_feedback = :id_feedback
        """), {"id_feedback": id_feedback, "agente": agente_limpio})

    agente_previo = limpiar_texto(anterior.get("agente"))
    registrar_historial_feedback(
        id_feedback,
        "ASIGNACION_AGENTE",
        "Agente asignado." if not agente_previo else "Agente corregido.",
        usuario=limpiar_texto(usuario),
        valor_anterior=agente_previo,
        valor_nuevo=agente_limpio,
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
        pesos_ctx = calcular_pesos_detalle_evaluacion(evaluacion)
        data["score_bruto"] = score_bruto_ctx
        data["peso_total"] = pesos_ctx.get("peso_total")
        data["peso_aplicable"] = peso_ctx
        data["peso_no_aplica"] = pesos_ctx.get("peso_no_aplica")
        data["peso_no_evaluable"] = pesos_ctx.get("peso_no_evaluable")
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
    puntos_visibles = data.get("puntos_criticos_lista")
    if puntos_visibles is None:
        puntos_visibles = cargar_json_lista(data.get("puntos_criticos"))
    if not puntos_visibles:
        puntos_visibles = consolidar_puntos_sgc(
            deduplicar_puntos_criticos(normalizar_hallazgos_no_criticos_v2(None, evaluacion))
        )
        data["puntos_criticos_lista"] = puntos_visibles
        data["puntos_criticos"] = json.dumps(puntos_visibles, ensure_ascii=False)
        data["total_puntos_criticos"] = len(puntos_visibles)
    data["version_evaluacion"] = resumen_sgc.get("version_evaluacion")
    data["estado_tecnico"] = resumen_sgc.get("estado_tecnico")
    data["tipificaciones_sugeridas"] = resumen_sgc.get("tipificaciones_sugeridas") or []
    data["feedback_asesor"] = resumen_sgc.get("feedback_asesor") or {}
    if isinstance(json_copc_v2, dict):
        data["pauta"] = json_copc_v2.get("pauta") or data.get("pauta")
        data["pauta_version"] = json_copc_v2.get("pauta_version") or data.get("pauta_version")
        data["pauta_pesos"] = json_copc_v2.get("pauta_pesos") or data.get("pauta_pesos")
        data["pauta_snapshot"] = json_copc_v2.get("pauta_snapshot") if isinstance(json_copc_v2.get("pauta_snapshot"), list) else []
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
    segmentos_actuales = data.get("segmentos_interlocutores") if isinstance(data.get("segmentos_interlocutores"), list) else []
    if segmentos_actuales:
        data["evaluacion_calidad_lista"] = completar_evidencias_desde_segmentos_v3(
            data.get("evaluacion_calidad_lista") or [],
            segmentos_actuales,
        )
        # La cartera decide contra que entidad se verifican PENC.1 y PECC.1, y
        # la fila SI la tiene. No pasarla aqui hacia que cada relectura de la
        # ficha ejecutara las guardas con cartera=None: sin tokens de entidad,
        # PENC.1 se abstenia y PECC.1 no podia nombrar a la entidad correcta,
        # pese a que el analisis original si la habia usado. Ese era el
        # cartera=None que veniamos arrastrando en los logs.
        evaluacion = aplicar_guardas_deterministicas_criterios(
            segmentos_actuales,
            data.get("evaluacion_calidad_lista") or [],
            data.get("cartera"),
        )
        evaluacion = enriquecer_evaluacion_sgc(
            evaluacion,
            score_final=score_final_num,
            nivel_riesgo=data.get("nivel_riesgo") or data.get("nivel_oportunidad_mejora"),
            falta_anulante=bool(data.get("falta_anulante")),
        )
        score_bruto_guardas, peso_guardas, score_guardas = calcular_score_normalizado(evaluacion)
        pesos_guardas = calcular_pesos_detalle_evaluacion(evaluacion)
        data["score_bruto"] = score_bruto_guardas
        data["peso_total"] = pesos_guardas.get("peso_total")
        data["peso_aplicable"] = peso_guardas
        data["peso_no_aplica"] = pesos_guardas.get("peso_no_aplica")
        data["peso_no_evaluable"] = pesos_guardas.get("peso_no_evaluable")
        data["score_normalizado"] = score_guardas
        if not data.get("score_final") or str(data.get("estado_revision") or "").upper() == "PENDIENTE":
            data["score_final"] = score_guardas
            data["score_calidad"] = score_guardas
        score_final_num = score_guardas
        resumen_sgc = construir_resumen_sgc(
            evaluacion,
            resumen_sgc,
            score_final=score_final_num,
            nivel_riesgo=data.get("nivel_riesgo") or data.get("nivel_oportunidad_mejora"),
            falta_anulante=bool(data.get("falta_anulante")),
        )
        puntos_visibles = consolidar_puntos_sgc(
            deduplicar_puntos_criticos(normalizar_hallazgos_no_criticos_v2(None, evaluacion))
        )
        data["evaluacion_calidad_lista"] = evaluacion
        data["resumen_sgc"] = resumen_sgc
        data["puntos_criticos_lista"] = puntos_visibles
        data["puntos_criticos"] = json.dumps(puntos_visibles, ensure_ascii=False)
        data["total_puntos_criticos"] = len(puntos_visibles)
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


# Estados que no se midieron: fuera del denominador del score y de la
# reporteria por segmento/item/SGC (misma regla en todo el modulo).
ESTADOS_FUERA_DEL_AGREGADO = {"NO_APLICA", "NO_EVALUABLE", "REQUIERE_REVISION"}


def _estado_criterio_para_agregado(item: Dict) -> Optional[str]:
    """Estado tecnico del criterio, o None si no se puede saber.

    A diferencia de _resultado_ia_normalizado, lo desconocido NO se vuelve
    REQUIERE_REVISION: un item antiguo sin estado sigue contando como antes
    (por nota vs peso) en vez de desaparecer del reporte.
    """
    estado = str(item.get("estado") or item.get("estado_tecnico") or "").strip().upper().replace(" ", "_")
    if estado:
        return estado
    texto = str(item.get("calificacion") or item.get("resultado") or "").strip().lower()
    if "no evaluable" in texto:
        return "NO_EVALUABLE"
    if "no aplica" in texto:
        return "NO_APLICA"
    if "revisi" in texto:
        return "REQUIERE_REVISION"
    return None
