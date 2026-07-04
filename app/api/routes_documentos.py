from pathlib import Path
import tempfile

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from app.services.documentos_service import (
    generar_documento,
    importar_directorio_agencias,
    limpiar_documentos_generados,
    listar_carteras_documento,
    listar_directorio_agencias,
    listar_tipos_documento,
    consultar_datos_documento,
)


router = APIRouter()


class EncargadoDocumentoRequest(BaseModel):
    modo: str | None = None
    operacion: str | None = None
    dni: str | None = None
    nombre: str | None = None
    direccion: str | None = None
    distrito: str | None = None
    provincia: str | None = None


class PagoGrupalRequest(BaseModel):
    operacion: str
    monto: float
    activo: bool = True


class GenerarDocumentoRequest(BaseModel):
    documento_tipo: str
    dni: str | None = None
    operacion: str | None = None
    codigo_grupo: str | None = None
    cod_cre_grupal: str | None = None
    cancelacion: float | None = None
    fecha_pago: str | None = None
    formato: str = "docx"
    excepcion: bool = False
    encargado: EncargadoDocumentoRequest | None = None
    pagos_grupales: list[PagoGrupalRequest] = Field(default_factory=list)
    cuotas_individual: int | None = None


@router.get("")
def vista_documentos():
    root = Path(__file__).resolve().parents[2]
    return FileResponse(root / "frontend" / "views" / "documentos.html")


@router.get("/tipos")
async def tipos_documento():
    return {"ok": True, "data": listar_tipos_documento()}


@router.get("/carteras")
async def carteras_documento():
    return {"ok": True, "data": listar_carteras_documento()}


@router.get("/buscar")
async def buscar_documentos(
    dni: str | None = Query(default=None),
    operacion: str | None = Query(default=None),
    codigo_grupo: str | None = Query(default=None),
    cod_cre_grupal: str | None = Query(default=None),
    cartera_id: int = Query(default=133),
):
    try:
        rows = await run_in_threadpool(
            consultar_datos_documento,
            dni=dni,
            operacion=operacion,
            codigo_grupo=codigo_grupo,
            cod_cre_grupal=cod_cre_grupal,
            cartera_id=cartera_id,
        )
        return {"ok": True, "data": rows}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error consultando datos del documento: {exc}")


@router.get("/agencias")
async def agencias_directorio(
    q: str | None = Query(default=None),
    limit: int = Query(default=300, ge=1, le=1000),
):
    try:
        rows = await run_in_threadpool(listar_directorio_agencias, q=q, limit=limit)
        return {"ok": True, "data": rows}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error consultando directorio de agencias: {exc}")


@router.post("/agencias/importar")
async def importar_agencias_directorio(file: UploadFile = File(...)):
    nombre = file.filename or "directorio_agencias.xlsx"
    if not nombre.lower().endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="Carga un archivo Excel .xlsx o .xls.")

    suffix = Path(nombre).suffix or ".xlsx"
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(await file.read())
            tmp_path = Path(tmp.name)

        result = await run_in_threadpool(importar_directorio_agencias, tmp_path, nombre)
        return {"ok": True, "data": result}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error importando directorio de agencias: {exc}")
    finally:
        if tmp_path is not None:
            try:
                tmp_path.unlink()
            except Exception:
                pass


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
            excepcion=payload.excepcion,
            encargado=payload.encargado.dict() if payload.encargado else None,
            pagos_grupales=[item.dict() for item in payload.pagos_grupales],
            cuotas_individual=payload.cuotas_individual,
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
