from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool

from app.services.importacion_service import (
    analizar_archivo_importacion,
    confirmar_carga_importacion,
    ejecutar_cierre_historico,
    listar_errores_lote_importacion,
    listar_configuraciones_importacion,
    listar_lotes_importacion,
    validar_cierre_historico,
)


router = APIRouter()


@router.get("")
def vista_importacion():
    root = Path(__file__).resolve().parents[2]
    return FileResponse(root / "frontend" / "views" / "importacion.html")


@router.get("/configuraciones")
def configuraciones_importacion():
    try:
        return {"data": listar_configuraciones_importacion()}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error obteniendo configuraciones: {exc}")


@router.post("/analizar")
async def analizar_importacion(
    id_config: int = Form(...),
    periodo: str = Form(...),
    tipo_carga: str = Form(...),
    hoja: Optional[str] = Form(default=None),
    archivo: UploadFile = File(...),
):
    try:
        contenido = await archivo.read()
        return await run_in_threadpool(
            analizar_archivo_importacion,
            id_config=id_config,
            periodo=periodo,
            tipo_carga=tipo_carga,
            hoja=hoja,
            archivo_nombre=archivo.filename or "archivo.xlsx",
            contenido=contenido,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error analizando archivo: {exc}")


@router.get("/lotes")
def lotes_importacion(limit: int = Query(default=100, ge=1, le=500)):
    try:
        return {"data": listar_lotes_importacion(limit=limit)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error listando lotes: {exc}")


@router.get("/lotes/{id_lote}/errores")
def errores_lote_importacion(
    id_lote: int,
    limit: int = Query(default=100, ge=1, le=500),
):
    try:
        return {"data": listar_errores_lote_importacion(id_lote=id_lote, limit=limit)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error listando errores del lote: {exc}")


@router.post("/confirmar")
async def confirmar_importacion(
    id_config: int = Form(...),
    periodo: str = Form(...),
    tipo_carga: str = Form(...),
    usuario: Optional[str] = Form(default=None),
    hoja_usada: Optional[str] = Form(default=None),
    archivo: UploadFile = File(...),
):
    try:
        contenido = await archivo.read()
        return await run_in_threadpool(
            confirmar_carga_importacion,
            id_config=id_config,
            periodo=periodo,
            tipo_carga=tipo_carga,
            usuario=usuario,
            hoja=hoja_usada,
            archivo_nombre=archivo.filename or "archivo.xlsx",
            contenido=contenido,
        )
    except ValueError as exc:
        return {
            "ok": False,
            "id_lote": None,
            "estado": "ERROR",
            "insertados": 0,
            "actualizados": 0,
            "rechazados": 0,
            "observacion": str(exc),
            "errores_preview": [],
        }
    except Exception as exc:
        return {
            "ok": False,
            "id_lote": None,
            "estado": "ERROR",
            "insertados": 0,
            "actualizados": 0,
            "rechazados": 0,
            "observacion": f"Error confirmando carga: {exc}",
            "errores_preview": [],
        }


@router.post("/cierre/validar")
def validar_cierre_importacion(
    id_config: int = Form(...),
    periodo: str = Form(...),
):
    try:
        return validar_cierre_historico(id_config=id_config, periodo=periodo)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error validando cierre historico: {exc}")


@router.post("/cierre/ejecutar")
def ejecutar_cierre_importacion(
    id_config: int = Form(...),
    periodo: str = Form(...),
    usuario: Optional[str] = Form(default=None),
    modo: str = Form(...),
):
    try:
        return ejecutar_cierre_historico(
            id_config=id_config,
            periodo=periodo,
            usuario=usuario,
            modo=modo,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error ejecutando cierre historico: {exc}")
