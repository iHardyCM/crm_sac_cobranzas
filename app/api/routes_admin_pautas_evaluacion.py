from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.services.pautas_evaluacion_service import (
    archivar_pauta,
    duplicar_pauta,
    guardar_borrador,
    listar_pautas,
    obtener_carteras_pauta,
    obtener_pauta,
    plantilla_general_evaluacion,
    publicar_pauta,
    validar_pauta,
)


router = APIRouter()


class PautaPayload(BaseModel):
    id_pauta: Optional[int] = None
    nombre: str = ""
    version: Optional[int] = None
    descripcion: str = ""
    aplica_todas: bool = False
    idcarteras: List[int] = Field(default_factory=list)
    grupo_nombre: str = ""
    vigencia_desde: Optional[str] = None
    vigencia_hasta: Optional[str] = None
    bloques: List[Dict[str, Any]] = Field(default_factory=list)
    usuario_actualizacion: str = ""


class AccionPayload(BaseModel):
    usuario_actualizacion: str = ""


@router.get("")
def vista_admin_pautas_evaluacion():
    root = Path(__file__).resolve().parents[2]
    return FileResponse(root / "frontend" / "views" / "admin_pautas_evaluacion.html")


@router.get("/pautas")
def obtener_pautas():
    try:
        return {"data": listar_pautas()}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error listando pautas: {exc}")


@router.get("/pautas/{id_pauta}")
def detalle_pauta(id_pauta: int):
    try:
        pauta = obtener_pauta(id_pauta)
        if not pauta:
            raise HTTPException(status_code=404, detail="La pauta no existe.")
        return {"data": pauta}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error obteniendo pauta: {exc}")


@router.get("/carteras")
def obtener_carteras():
    try:
        return {"data": obtener_carteras_pauta()}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error listando carteras: {exc}")


@router.get("/plantillas/general")
def plantilla_general():
    """Solo entrega un borrador de partida; el usuario decide cuándo guardarlo o publicarlo."""
    return {"data": plantilla_general_evaluacion()}


@router.post("/validar")
def validar(payload: PautaPayload):
    data = validar_pauta(payload.model_dump(), requiere_total=False)
    return {
        "ok": data["valida"],
        "errores": data["errores"],
        "peso_total": data["peso_total"],
        "puede_publicar": validar_pauta(payload.model_dump(), requiere_total=True)["valida"],
    }


@router.post("/pautas")
def guardar(payload: PautaPayload):
    try:
        return guardar_borrador(payload.model_dump(), payload.usuario_actualizacion)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error guardando pauta: {exc}")


@router.post("/pautas/{id_pauta}/duplicar")
def duplicar(id_pauta: int, payload: AccionPayload):
    try:
        return duplicar_pauta(id_pauta, payload.usuario_actualizacion)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error duplicando pauta: {exc}")


@router.post("/pautas/{id_pauta}/publicar")
def publicar(id_pauta: int, payload: AccionPayload):
    try:
        return publicar_pauta(id_pauta, payload.usuario_actualizacion)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error publicando pauta: {exc}")


@router.post("/pautas/{id_pauta}/archivar")
def archivar(id_pauta: int, payload: AccionPayload):
    try:
        return archivar_pauta(id_pauta, payload.usuario_actualizacion)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error archivando pauta: {exc}")
