from pathlib import Path
from typing import List

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.services.admin_supervisores_service import (
    guardar_asignaciones,
    listar_asignaciones,
    listar_carteras,
    listar_supervisores,
)


router = APIRouter()


class AsignacionPayload(BaseModel):
    usuario: str
    idcarteras: List[int]
    usuario_actualizacion: str | None = None


@router.get("")
def vista_admin_supervisores():
    root = Path(__file__).resolve().parents[2]
    return FileResponse(root / "frontend" / "views" / "admin_supervisores.html")


@router.get("/supervisores")
def obtener_supervisores():
    try:
        return {"data": listar_supervisores()}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error listando supervisores: {exc}")


@router.get("/carteras")
def obtener_carteras():
    try:
        return {"data": listar_carteras()}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error listando carteras: {exc}")


@router.get("/asignaciones")
def obtener_asignaciones(usuario: str | None = None):
    try:
        return {"data": listar_asignaciones(usuario)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error listando asignaciones: {exc}")


@router.post("/asignaciones")
def actualizar_asignaciones(payload: AsignacionPayload):
    try:
        return guardar_asignaciones(
            usuario=payload.usuario,
            idcarteras=payload.idcarteras,
            usuario_actualizacion=payload.usuario_actualizacion or "",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error guardando asignaciones: {exc}")
