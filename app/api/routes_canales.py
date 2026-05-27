from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, JSONResponse

from app.services.canales_service import (
    CanalesColumnError,
    importar_canales,
    listar_carteras_canales,
    listar_importaciones_canales,
    obtener_importacion_canales,
)


router = APIRouter()


@router.get("")
def vista_canales():
    root = Path(__file__).resolve().parents[2]
    return FileResponse(root / "frontend" / "views" / "canales.html")


@router.get("/carteras")
def carteras_canales():
    try:
        return {"data": listar_carteras_canales()}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error obteniendo carteras: {exc}")


@router.post("/importar")
async def importar_archivo_canales(
    canal: str = Form(...),
    idcartera: int = Form(...),
    cartera: str = Form(...),
    usuario_carga: str = Form(default="SIN_USUARIO"),
    archivo: UploadFile = File(...),
):
    try:
        contenido = await archivo.read()
        return importar_canales(
            canal=canal,
            idcartera=idcartera,
            cartera=cartera,
            usuario_carga=usuario_carga,
            archivo_nombre=archivo.filename or "archivo.xlsx",
            contenido=contenido,
        )
    except CanalesColumnError as exc:
        return JSONResponse(status_code=400, content=exc.payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error importando archivo: {exc}")


@router.get("/importaciones")
def importaciones_canales(limit: int = Query(default=100, ge=1, le=500)):
    try:
        return {"data": listar_importaciones_canales(limit=limit)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error listando importaciones: {exc}")


@router.get("/importaciones/{id_carga}")
def detalle_importacion_canales(id_carga: int):
    try:
        return obtener_importacion_canales(id_carga)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error obteniendo detalle: {exc}")
