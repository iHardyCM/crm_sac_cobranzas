from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse

from app.services.pagos_service import (
    confirmar_importacion,
    listar_importaciones,
    obtener_cortes_activos,
    obtener_resumen_pagos,
    validar_archivo_pago,
)


router = APIRouter()


@router.get("")
def vista_pagos():
    root = Path(__file__).resolve().parents[2]
    return FileResponse(root / "frontend" / "views" / "pagos.html")


@router.post("/validar")
async def validar_pago(
    formato: str = Form(...),
    usuario_carga: Optional[str] = Form(default=None),
    archivo: UploadFile = File(...),
):
    try:
        content = await archivo.read()
        return validar_archivo_pago(
            formato=formato,
            filename=archivo.filename or "archivo",
            content=content,
            usuario_carga=usuario_carga,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error validando archivo: {exc}")


@router.post("/confirmar/{id_importacion}")
def confirmar_pago(id_importacion: int):
    try:
        return confirmar_importacion(id_importacion)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error publicando importacion: {exc}")


@router.get("/importaciones")
def importaciones(
    codmes: Optional[str] = Query(default=None),
    activos: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=500),
):
    return {
        "data": listar_importaciones(
            limit=limit,
            codmes=codmes,
            solo_activos=activos,
        )
    }


@router.get("/resumen")
def resumen():
    return {"data": obtener_resumen_pagos()}


@router.get("/cortes-activos")
def cortes_activos(codmes: Optional[str] = Query(default=None)):
    return {"data": obtener_cortes_activos(codmes=codmes)}
