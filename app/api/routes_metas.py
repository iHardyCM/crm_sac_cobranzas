from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from app.services.metas_service import obtener_detalle_metas, obtener_resumen_metas


router = APIRouter()


@router.get("")
def vista_metas():
    root = Path(__file__).resolve().parents[2]
    return FileResponse(root / "frontend" / "views" / "metas.html")


@router.get("/resumen")
def resumen_metas(
    codmes: Optional[str] = Query(default=None),
    tipo_medicion: Optional[str] = Query(default=None),
    grupo_cartera: Optional[str] = Query(default=None),
):
    try:
        return obtener_resumen_metas(
            codmes=codmes,
            tipo_medicion=tipo_medicion,
            grupo_cartera=grupo_cartera,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error obteniendo resumen de metas: {exc}")


@router.get("/detalle")
def detalle_metas(
    codmes: Optional[str] = Query(default=None),
    tipo_medicion: Optional[str] = Query(default=None),
    grupo_cartera: Optional[str] = Query(default=None),
):
    try:
        return {
            "data": obtener_detalle_metas(
                codmes=codmes,
                tipo_medicion=tipo_medicion,
                grupo_cartera=grupo_cartera,
            )
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error obteniendo detalle de metas: {exc}")
