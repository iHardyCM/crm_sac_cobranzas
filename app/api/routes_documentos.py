from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from app.services.documentos_service import (
    generar_documento,
    limpiar_documentos_generados,
    listar_tipos_documento,
    consultar_datos_documento,
)


router = APIRouter()


class GenerarDocumentoRequest(BaseModel):
    documento_tipo: str
    dni: str | None = None
    operacion: str | None = None
    codigo_grupo: str | None = None
    cod_cre_grupal: str | None = None
    cancelacion: float
    fecha_pago: str
    formato: str = "docx"


@router.get("")
def vista_documentos():
    root = Path(__file__).resolve().parents[2]
    return FileResponse(root / "frontend" / "views" / "documentos.html")


@router.get("/tipos")
async def tipos_documento():
    return {"ok": True, "data": listar_tipos_documento()}


@router.get("/buscar")
async def buscar_documentos(
    dni: str | None = Query(default=None),
    operacion: str | None = Query(default=None),
    codigo_grupo: str | None = Query(default=None),
    cod_cre_grupal: str | None = Query(default=None),
):
    try:
        rows = await run_in_threadpool(
            consultar_datos_documento,
            dni=dni,
            operacion=operacion,
            codigo_grupo=codigo_grupo,
            cod_cre_grupal=cod_cre_grupal,
        )
        return {"ok": True, "data": rows}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error consultando datos del documento: {exc}")


@router.post("/generar")
async def generar_documento_endpoint(payload: GenerarDocumentoRequest):
    try:
        limpiar_documentos_generados()
        result = await run_in_threadpool(
            generar_documento,
            documento_tipo=payload.documento_tipo,
            dni=payload.dni,
            operacion=payload.operacion,
            codigo_grupo=payload.codigo_grupo,
            cod_cre_grupal=payload.cod_cre_grupal,
            cancelacion=payload.cancelacion,
            fecha_pago=payload.fecha_pago,
            formato=payload.formato,
        )
        media_type = "application/pdf" if result["formato"] == "pdf" else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        return FileResponse(
            result["path"],
            media_type=media_type,
            filename=result["filename"],
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error generando documento: {exc}")
