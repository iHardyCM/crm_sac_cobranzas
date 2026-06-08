from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse

from app.services.admin_supervisores_service import listar_carteras
from app.services.ia_analysis_service import (
    guardar_prompt_configuracion,
    obtener_prompt_configuracion,
    perfil_puede_editar_prompt,
)
from app.services.ia_audio_service import (
    analizar_feedback,
    guardar_revision_feedback,
    listar_feedback,
    obtener_configuracion_audio,
    obtener_feedback,
    registrar_audio_feedback,
)


router = APIRouter()


@router.get("")
def vista_ia_feedback():
    root = Path(__file__).resolve().parents[2]
    return FileResponse(root / "frontend" / "views" / "ia_feedback.html")


@router.get("/config")
def config_ia_feedback():
    return obtener_configuracion_audio()


@router.get("/carteras")
def carteras_ia_feedback():
    try:
        return {"data": listar_carteras()}
    except Exception:
        return {
            "data": [
                {"idcartera": None, "cartera": "Mibanco"},
                {"idcartera": None, "cartera": "Interbank"},
                {"idcartera": None, "cartera": "Financiera OH"},
                {"idcartera": None, "cartera": "Compartamos"},
                {"idcartera": None, "cartera": "Crediscotia"},
                {"idcartera": None, "cartera": "Efectiva"},
            ]
        }


@router.get("/prompt")
def obtener_prompt_ia_feedback(
    perfil: str | None = Query(default=None),
    cartera: str | None = Query(default=None),
):
    puede_editar = perfil_puede_editar_prompt(perfil)
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
    actualizado_por: str | None = Form(default=None),
    perfil: str | None = Form(default=None),
    cartera: str | None = Form(default=None),
):
    try:
        return guardar_prompt_configuracion(
            prompt_base=prompt_base,
            actualizado_por=actualizado_por,
            perfil=perfil,
            cartera=cartera,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error guardando prompt IA: {exc}")


@router.post("/upload")
async def upload_ia_feedback(
    archivo: UploadFile = File(...),
    agente: str | None = Form(default=None),
    supervisor: str | None = Form(default=None),
    cartera: str | None = Form(default=None),
    dni: str | None = Form(default=None),
    telefono: str | None = Form(default=None),
    fecha_llamada: str | None = Form(default=None),
    comentario_supervisor: str | None = Form(default=None),
):
    try:
        contenido = await archivo.read()
        return registrar_audio_feedback(
            archivo_nombre=archivo.filename or "audio",
            contenido=contenido,
            agente=agente,
            supervisor=supervisor,
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


@router.post("/{id_feedback}/analizar")
def analizar_ia_feedback(id_feedback: int):
    try:
        return analizar_feedback(id_feedback)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error analizando llamada: {exc}")


@router.post("/{id_feedback}/revision")
def guardar_revision_ia_feedback(
    id_feedback: int,
    agente: str | None = Form(default=None),
    comentario_feedback: str | None = Form(default=None),
    estado_revision: str | None = Form(default="REVISADO"),
    revisado_por: str | None = Form(default=None),
):
    try:
        return guardar_revision_feedback(
            id_feedback,
            agente=agente,
            comentario_feedback=comentario_feedback,
            estado_revision=estado_revision,
            revisado_por=revisado_por,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error guardando revision IA: {exc}")


@router.get("/listar")
def listar_ia_feedback(
    limit: int = Query(default=100, ge=1, le=300),
    supervisor: str | None = Query(default=None),
    perfil: str | None = Query(default=None),
):
    try:
        if perfil_puede_editar_prompt(perfil):
            supervisor_filtro = None
        else:
            if not supervisor:
                return {"data": []}
            supervisor_filtro = supervisor
        return {"data": listar_feedback(limit=limit, supervisor=supervisor_filtro)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error listando analisis IA: {exc}")


@router.get("/{id_feedback}")
def detalle_ia_feedback(id_feedback: int):
    try:
        return obtener_feedback(id_feedback)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error obteniendo analisis IA: {exc}")
