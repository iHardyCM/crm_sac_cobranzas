from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool

from app.services.metas_service import (
    importar_metas_mibanco,
    obtener_detalle_metas,
    obtener_resumen_metas,
)


router = APIRouter()


@router.get("")
def vista_metas():
    root = Path(__file__).resolve().parents[2]
    return FileResponse(root / "frontend" / "views" / "metas.html")


@router.post("/importar/mibanco")
async def importar_metas_mibanco_endpoint(
    codmes: str = Form(...),
    usuario: Optional[str] = Form(default=None),
    archivo: UploadFile = File(...),
):
    try:
        contenido = await archivo.read()
        return await run_in_threadpool(
            importar_metas_mibanco,
            codmes=codmes,
            archivo_nombre=archivo.filename or "metas_mibanco.xlsx",
            contenido=contenido,
            usuario=usuario,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error importando metas MiBanco: {exc}")


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
