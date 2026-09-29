from pathlib import Path
from urllib.parse import quote

import logging
import os
import time
from datetime import datetime
import threading

from typing import Dict

from fastapi import APIRouter, BackgroundTasks, Body, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, Response
from starlette.concurrency import run_in_threadpool

import re

from app.core.auth_dependencies import normalizar_tipo_usuario, requiere_clave_definitiva
from app.services.admin_metas_agentes_service import listar_agentes
from app.services.admin_supervisores_service import listar_carteras
from app.services.reporte_calidad_export import construir_reporte_calidad_excel
from app.services.ia_consumo_service import obtener_consumo
from app.services.reporteria_sql_service import obtener_reporteria_sql
from app.services.ia_analysis_service import (
    guardar_prompt_configuracion,
    obtener_prompt_configuracion,
    perfil_puede_editar_prompt,
    perfil_puede_ver_historial_global_ia,
)
from app.services.ia_audio_service import (
    actualizar_estado,
    analizar_feedback,
    asignar_agente_feedback,
    guardar_coaching_feedback,
    guardar_revision_feedback,
    listar_recalibraciones_feedback,
    listar_feedback,
    obtener_bandeja_supervisor,
    obtener_estado_feedback,
    obtener_configuracion_audio,
    obtener_feedback,
    obtener_reporteria_calidad,
    registrar_audio_feedback,
    resolver_recalibracion_feedback,
    solicitar_recalibracion_feedback,
)


router = APIRouter()
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Seguridad (hardening fase 3)
# Todos los endpoints de datos o mutacion exigen sesion valida:
# requiere_clave_definitiva = JWT + cuenta CRM activa + usuario activo en
# SISCOB + clave definitiva (sin cambio obligatorio pendiente).
# Perfil e identidad salen SIEMPRE del usuario autenticado, nunca de
# parametros "perfil", "supervisor", "usuario" o "actualizado_por" del
# navegador. Esos parametros se siguen aceptando por compatibilidad con la
# pantalla, pero se ignoran.
# Pendiente: filtrar por idcarteras del usuario (ver docs/autenticacion_fase1.md).
# ---------------------------------------------------------------------------
UsuarioIa = Depends(requiere_clave_definitiva)


def _perfil_sesion(usuario: Dict) -> str:
    return normalizar_tipo_usuario(usuario.get("tipo"))


def _identidad_sesion(usuario: Dict) -> str:
    """Mismo formato que la pantalla usaba ("DNI - Nombres Apellidos")."""
    return usuario.get("agente") or usuario.get("dni")

# Llamadas que se estan procesando en este proceso del servidor. Evita lanzar
# dos analisis a la vez sobre la misma llamada -doble clic, dos pestañas-, que
# gastarian API dos veces y se pisarian al guardar.
# Limitacion conocida: vive en memoria. Si el servidor corre con varios workers
# cada uno tiene su propio conjunto, y si se reinicia a mitad de un analisis el
# registro se pierde (la llamada queda en TRANSCRIBIENDO o ANALIZANDO y se
# puede relanzar desde la ficha).
_EN_PROCESO: set[int] = set()
_EN_PROCESO_LOCK = threading.Lock()


@router.get("")
def vista_ia_feedback():
    root = Path(__file__).resolve().parents[2]
    return FileResponse(
        root / "frontend" / "views" / "ia_feedback.html",
        headers={"Cache-Control": "no-store"},
    )


@router.get("/config")
def config_ia_feedback(usuario: Dict = UsuarioIa):
    return obtener_configuracion_audio()


@router.get("/carteras")
def carteras_ia_feedback(usuario: Dict = UsuarioIa):
    try:
        return {"data": listar_carteras()}
    except Exception:
        return {
            "data": [
                {"idcartera": None, "cartera": "Mibanco"},
                {"idcartera": None, "cartera": "Interbank"},
                {"idcartera": None, "cartera": "Financiera OH"},
                {"idcartera": None, "cartera": "Financiera OH Propia"},
                {"idcartera": None, "cartera": "Compartamos"},
                {"idcartera": None, "cartera": "Efectiva"},
            ]
        }


@router.get("/prompt")
def obtener_prompt_ia_feedback(
    cartera: str | None = Query(default=None),
    usuario: Dict = UsuarioIa,
):
    # "perfil" en la query se ignora: el permiso sale de la sesion.
    puede_editar = perfil_puede_editar_prompt(_perfil_sesion(usuario))
    if not puede_editar:
        return {
            "prompt_base": None,
            "usa_prompt_personalizado": False,
            "actualizado_por": None,
            "fecha_actualizacion": None,
            "puede_editar": False,
        }

    data = obtener_prompt_configuracion(cartera)
    data["puede_editar"] = puede_editar
    return data


@router.post("/prompt")
def guardar_prompt_ia_feedback(
    prompt_base: str = Form(...),
    cartera: str | None = Form(default=None),
    usuario: Dict = UsuarioIa,
):
    # "perfil" y "actualizado_por" del formulario se ignoran: salen de la sesion.
    try:
        return guardar_prompt_configuracion(
            prompt_base=prompt_base,
            actualizado_por=_identidad_sesion(usuario),
            perfil=_perfil_sesion(usuario),
            cartera=cartera,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error guardando prompt IA: {exc}")


@router.get("/bandeja")
def bandeja_ia_feedback(usuario: Dict = UsuarioIa):
    """Lo que el supervisor tiene en curso y pendiente de revisar.
    Los perfiles con vision global ven la de todos.
    Supervisor y perfil salen de la sesion; los de la query se ignoran."""
    try:
        return obtener_bandeja_supervisor(
            supervisor=_identidad_sesion(usuario),
            ver_todo=perfil_puede_ver_historial_global_ia(_perfil_sesion(usuario)),
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error cargando la bandeja: {exc}")


@router.get("/agentes")
def agentes_ia_feedback(
    cartera: str | None = Query(default=None),
    idcartera: int | None = Query(default=None),
    usuario: Dict = UsuarioIa,
):
    """Gestores activos, filtrados por cartera.

    Reusa listar_agentes -la misma fuente que el modulo de metas: SISCOB.USUARIO
    con TipoUsuario GESTOR y Estado A-, para no tener dos maestros de agentes.
    Acepta el id numerico o la etiqueta "124 - COMPARTAMOS ...", que es como
    viaja la cartera en este modulo.
    """
    if idcartera is None and cartera:
        coincide = re.match(r"\s*(\d{2,4})\b", cartera)
        if coincide:
            idcartera = int(coincide.group(1))
    try:
        return {"data": listar_agentes(idcartera), "idcartera": idcartera}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error listando agentes: {exc}")


@router.post("/upload")
async def upload_ia_feedback(
    archivo: UploadFile = File(...),
    agente: str | None = Form(default=None),
    cartera: str | None = Form(default=None),
    dni: str | None = Form(default=None),
    telefono: str | None = Form(default=None),
    fecha_llamada: str | None = Form(default=None),
    comentario_supervisor: str | None = Form(default=None),
    usuario: Dict = UsuarioIa,
):
    # El supervisor que carga el audio es el usuario autenticado (no el formulario).
    try:
        contenido = await archivo.read()
        return await run_in_threadpool(
            registrar_audio_feedback,
            archivo_nombre=archivo.filename or "audio",
            contenido=contenido,
            agente=agente,
            supervisor=_identidad_sesion(usuario),
            cartera=cartera,
            dni=dni,
            telefono=telefono,
            fecha_llamada=fecha_llamada,
            comentario_supervisor=comentario_supervisor,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error registrando audio: {exc}")


def _procesar_en_segundo_plano(id_feedback: int, forzar_transcripcion: bool) -> None:
    try:
        analizar_feedback(id_feedback, forzar_transcripcion)
    except Exception:
        # analizar_feedback ya deja la llamada en ERROR con el mensaje; aqui
        # solo se registra, porque ya no hay una peticion a la que responder.
        logger.exception("[SEGUNDO PLANO] fallo el analisis de feedback=%s", id_feedback)
    finally:
        with _EN_PROCESO_LOCK:
            _EN_PROCESO.discard(id_feedback)


@router.post("/{id_feedback}/analizar/iniciar")
def iniciar_analisis_ia_feedback(
    id_feedback: int,
    background_tasks: BackgroundTasks,
    forzar_transcripcion: bool = Query(default=False),
    usuario: Dict = UsuarioIa,
):
    """Lanza el analisis y responde al instante.

    El analisis tarda ~4 minutos -casi todo en OpenAI- y antes la pantalla
    esperaba bloqueada todo ese tiempo. Ahora corre en segundo plano y la
    pantalla consulta /estado; el supervisor puede seguir trabajando.
    """
    with _EN_PROCESO_LOCK:
        if id_feedback in _EN_PROCESO:
            raise HTTPException(status_code=409, detail="Esta llamada ya se está procesando.")
        _EN_PROCESO.add(id_feedback)
    try:
        actualizar_estado(id_feedback, "EN_COLA")
    except Exception as exc:
        with _EN_PROCESO_LOCK:
            _EN_PROCESO.discard(id_feedback)
        raise HTTPException(status_code=500, detail=f"No se pudo encolar la llamada: {exc}")
    background_tasks.add_task(_procesar_en_segundo_plano, id_feedback, forzar_transcripcion)
    return {"id_feedback": id_feedback, "estado": "EN_COLA"}


@router.get("/{id_feedback}/estado")
def estado_ia_feedback(id_feedback: int, usuario: Dict = UsuarioIa):
    try:
        data = obtener_estado_feedback(id_feedback)
        with _EN_PROCESO_LOCK:
            data["en_proceso"] = id_feedback in _EN_PROCESO
        return data
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error consultando estado: {exc}")


@router.post("/{id_feedback}/analizar")
async def analizar_ia_feedback(
    id_feedback: int,
    forzar_transcripcion: bool = Query(default=False),
    usuario: Dict = UsuarioIa,
):
    # Mismo guardia que la version en segundo plano: si la llamada ya se esta
    # procesando, un reanalisis simultaneo gastaria API dos veces y se pisaria.
    with _EN_PROCESO_LOCK:
        if id_feedback in _EN_PROCESO:
            raise HTTPException(status_code=409, detail="Esta llamada ya se está procesando.")
        _EN_PROCESO.add(id_feedback)
    try:
        return await run_in_threadpool(analizar_feedback, id_feedback, forzar_transcripcion)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error analizando llamada: {exc}")
    finally:
        with _EN_PROCESO_LOCK:
            _EN_PROCESO.discard(id_feedback)


@router.post("/{id_feedback}/revision")
def guardar_revision_ia_feedback(
    id_feedback: int,
    agente: str | None = Form(default=None),
    comentario_feedback: str | None = Form(default=None),
    estado_revision: str | None = Form(default="REVISADO"),
    usuario: Dict = UsuarioIa,
):
    # "revisado_por" del formulario se ignora: es el usuario autenticado.
    try:
        return guardar_revision_feedback(
            id_feedback,
            agente=agente,
            comentario_feedback=comentario_feedback,
            estado_revision=estado_revision,
            revisado_por=_identidad_sesion(usuario),
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error guardando revision IA: {exc}")


# Formulario antiguo de recalibracion: RETIRADO el 28/09/2026.
# Escribia la nota a mano en score_final, por fuera de la pauta y en paralelo a
# la calibracion por criterio, asi que dos correcciones podian contradecirse.
# Toda correccion pasa ahora por /calibracion: se corrige el criterio y la nota
# se recalcula sola. El historial anterior se mantiene visible (GET de abajo).
@router.post("/{id_feedback}/recalibracion")
def solicitar_recalibracion_ia_feedback(id_feedback: int, usuario: Dict = UsuarioIa):
    raise HTTPException(
        status_code=410,
        detail="La recalibracion por nota sugerida fue retirada. Corrige el criterio en Calibracion: la nota se recalcula sola.",
    )


@router.get("/{id_feedback}/recalibraciones")
def recalibraciones_ia_feedback(id_feedback: int, usuario: Dict = UsuarioIa):
    try:
        return {"data": listar_recalibraciones_feedback(id_feedback)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error listando recalibraciones IA: {exc}")


@router.post("/recalibracion/{id_recalibracion}/resolver")
def resolver_recalibracion_ia_feedback(id_recalibracion: int, usuario: Dict = UsuarioIa):
    raise HTTPException(
        status_code=410,
        detail="La resolucion de recalibraciones fue retirada. Jefatura aprueba las correcciones desde Calibracion.",
    )


@router.post("/{id_feedback}/coaching")
def guardar_coaching_ia_feedback(
    id_feedback: int,
    estado: str | None = Form(default="PROGRAMADO"),
    feedback_supervisor: str | None = Form(default=None),
    compromiso_agente: str | None = Form(default=None),
    fecha_programada: str | None = Form(default=None),
    resultado: str | None = Form(default=None),
    responsable: str | None = Form(default=None),
    usuario: Dict = UsuarioIa,
):
    try:
        return guardar_coaching_feedback(
            id_feedback,
            estado=estado,
            feedback_supervisor=feedback_supervisor,
            compromiso_agente=compromiso_agente,
            fecha_programada=fecha_programada,
            resultado=resultado,
            responsable=responsable,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error guardando coaching IA: {exc}")


@router.get("/listar")
def listar_ia_feedback(
    limit: int = Query(default=100, ge=1, le=300),
    usuario: Dict = UsuarioIa,
):
    # Vision global o solo lo propio: se decide con el perfil de la sesion.
    # "perfil" y "supervisor" de la query se ignoran.
    try:
        if perfil_puede_ver_historial_global_ia(_perfil_sesion(usuario)):
            supervisor_filtro = None
        else:
            supervisor_filtro = _identidad_sesion(usuario)
        inicio = time.perf_counter()
        data = listar_feedback(limit=limit, supervisor=supervisor_filtro)
        logger.info("[TIEMPOS] listar filas=%s segundos=%.2f", len(data), time.perf_counter() - inicio)
        return {"data": data}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error listando analisis IA: {exc}")


@router.get("/reporteria")
def reporteria_ia_feedback(
    limit: int = Query(default=300, ge=1, le=1000),
    fuente: str = Query(default="json", pattern="^(json|sql)$"),
    usuario: Dict = UsuarioIa,
):
    # Vision global o solo lo propio: se decide con el perfil de la sesion.
    # "perfil" y "supervisor" de la query se ignoran.
    try:
        if perfil_puede_ver_historial_global_ia(_perfil_sesion(usuario)):
            supervisor_filtro = None
        else:
            supervisor_filtro = _identidad_sesion(usuario)
        # [TIEMPOS] Medir antes de optimizar: la pagina queda en blanco mientras
        # esto responde. Si el tiempo crece con el numero de filas, el costo
        # esta en re-enriquecer cada evaluacion (guardas) dentro del servicio.
        inicio = time.perf_counter()
        # fuente=sql lee las tablas (sin re-aplicar guardas). Queda como opcion
        # hasta validar con tools/comparar_reporteria.py que las cifras cuadran.
        if fuente == "sql":
            data = obtener_reporteria_sql(limit=limit, supervisor=supervisor_filtro)
        else:
            data = obtener_reporteria_calidad(limit=limit, supervisor=supervisor_filtro)
        logger.info(
            "[TIEMPOS] reporteria fuente=%s filas=%s segundos=%.2f",
            fuente, len(data.get("detalle") or []), time.perf_counter() - inicio,
        )
        return data
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error obteniendo reporteria IA: {exc}")


# Quien ve el costo de la API. Por defecto solo ADMINISTRADOR; se puede ampliar
# sin tocar codigo con IA_FEEDBACK_CONSUMO_PERFILES="ADMINISTRADOR,JEFE DE CARTERA".
# El perfil sale de la sesion validada en el servidor (no del navegador).
def _perfil_ve_consumo_ia(perfil: str | None) -> bool:
    permitidos = {
        p.strip().upper()
        for p in os.getenv("IA_FEEDBACK_CONSUMO_PERFILES", "ADMINISTRADOR").split(",")
        if p.strip()
    }
    return normalizar_tipo_usuario(perfil) in permitidos


@router.get("/consumo")
def consumo_ia_feedback(
    dias: int = Query(default=30, ge=1, le=180),
    limite: int = Query(default=200, ge=1, le=1000),
    usuario: Dict = UsuarioIa,
):
    """Cuanto consumio la API por evaluacion. Solo perfiles con vision global:
    es informacion de costo del modulo, no de una cartera."""
    if not _perfil_ve_consumo_ia(_perfil_sesion(usuario)):
        raise HTTPException(status_code=403, detail="Perfil sin acceso al consumo de la API.")
    try:
        return obtener_consumo(dias=dias, limite=limite)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error obteniendo el consumo de la IA: {exc}")


@router.post("/reporteria/exportar-excel")
def exportar_reporteria_excel(payload: dict = Body(...), usuario: Dict = UsuarioIa):
    """Arma el Excel con lo que la pagina ya filtro. No recalcula reglas."""
    try:
        contenido = construir_reporte_calidad_excel(payload)
    except Exception as exc:
        logger.exception("Error exportando reporte de calidad")
        raise HTTPException(status_code=500, detail=f"No se pudo generar el Excel: {exc}")
    nombre = f"reporte_calidad_{datetime.now():%Y%m%d_%H%M}.xlsx"
    return Response(
        content=contenido,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{nombre}"'},
    )


@router.get("/{id_feedback}/audio")
def audio_ia_feedback(id_feedback: int, usuario: Dict = UsuarioIa):
    try:
        data = obtener_feedback(id_feedback)
        ruta = data.get("ruta_archivo")
        if not ruta:
            raise HTTPException(status_code=404, detail="Audio no registrado para esta evaluacion.")
        root = Path(__file__).resolve().parents[2]
        archivo = Path(ruta)
        if not archivo.is_absolute():
            archivo = root / archivo
        archivo = archivo.resolve()
        uploads_root = (root / "uploads" / "ia_feedback").resolve()
        if uploads_root not in [archivo, *archivo.parents]:
            raise HTTPException(status_code=403, detail="Ruta de audio no permitida.")
        if not archivo.exists():
            raise HTTPException(status_code=404, detail="Archivo de audio no encontrado.")
        media_type = {
            ".mp3": "audio/mpeg",
            ".wav": "audio/wav",
            ".m4a": "audio/mp4",
            ".ogg": "audio/ogg",
        }.get(archivo.suffix.lower(), "application/octet-stream")
        nombre = data.get("archivo_nombre") or archivo.name
        headers = {
            "Content-Disposition": f"inline; filename*=UTF-8''{quote(str(nombre))}",
            "Cache-Control": "private, max-age=3600",
        }
        return FileResponse(archivo, media_type=media_type, headers=headers)
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error obteniendo audio IA: {exc}")


@router.get("/{id_feedback}")
def detalle_ia_feedback(id_feedback: int, usuario: Dict = UsuarioIa):
    try:
        return obtener_feedback(id_feedback)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error obteniendo analisis IA: {exc}")



@router.post("/{id_feedback}/agente")
def asignar_agente_ia_feedback(
    id_feedback: int,
    agente: str = Form(...),
    usuario: Dict = UsuarioIa,
):
    # Quien asigna es el usuario autenticado; un "usuario" en el formulario se ignora.
    try:
        return asignar_agente_feedback(id_feedback, agente, _identidad_sesion(usuario))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error asignando agente: {exc}")
