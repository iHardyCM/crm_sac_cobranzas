from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.services.admin_metas_agentes_service import (
    guardar_meta_cartera,
    guardar_meta_agente,
    listar_agentes,
    listar_carteras_metas,
    listar_metas_agentes,
    obtener_ritmo_meta_agente,
    obtener_resumen_meta_agente,
)


router = APIRouter()


class MetaAgentePayload(BaseModel):
    codmes: str
    idcartera: int
    usuario: str
    meta_mensual: float
    usuario_actualizacion: Optional[str] = None


class MetaCarteraPayload(BaseModel):
    codmes: str
    idcartera: int
    meta_mensual: float
    usuario_actualizacion: Optional[str] = None


@router.get("")
def vista_admin_metas_agentes():
    root = Path(__file__).resolve().parents[2]
    return FileResponse(root / "frontend" / "views" / "admin_metas_agentes.html")


@router.get("/ritmo")
def vista_ritmo_meta():
    root = Path(__file__).resolve().parents[2]
    return FileResponse(root / "frontend" / "views" / "ritmo_meta.html")


@router.get("/carteras")
def obtener_carteras():
    try:
        return {"data": listar_carteras_metas()}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error listando carteras: {exc}")


@router.get("/agentes")
def obtener_agentes(idcartera: Optional[int] = Query(default=None)):
    try:
        return {"data": listar_agentes(idcartera=idcartera)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error listando agentes: {exc}")


@router.get("/metas")
def obtener_metas(
    codmes: Optional[str] = Query(default=None),
    idcartera: Optional[int] = Query(default=None),
):
    try:
        return {"data": listar_metas_agentes(codmes=codmes, idcartera=idcartera)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error listando metas: {exc}")


@router.post("/metas")
def actualizar_meta(payload: MetaAgentePayload):
    try:
        return guardar_meta_agente(
            codmes=payload.codmes,
            idcartera=payload.idcartera,
            usuario=payload.usuario,
            meta_mensual=payload.meta_mensual,
            usuario_actualizacion=payload.usuario_actualizacion or "",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error guardando meta: {exc}")


@router.post("/metas-cartera")
def actualizar_meta_cartera(payload: MetaCarteraPayload):
    try:
        return guardar_meta_cartera(
            codmes=payload.codmes,
            idcartera=payload.idcartera,
            meta_mensual=payload.meta_mensual,
            usuario_actualizacion=payload.usuario_actualizacion or "",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error guardando metas por cartera: {exc}")


@router.get("/resumen-agente")
def resumen_agente(usuario: str, codmes: Optional[str] = Query(default=None)):
    try:
        return obtener_resumen_meta_agente(usuario=usuario, codmes=codmes)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error obteniendo resumen del agente: {exc}")


@router.get("/ritmo-agente")
def ritmo_agente(usuario: str, codmes: Optional[str] = Query(default=None)):
    try:
        return obtener_ritmo_meta_agente(usuario=usuario, codmes=codmes)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error obteniendo ritmo del agente: {exc}")
