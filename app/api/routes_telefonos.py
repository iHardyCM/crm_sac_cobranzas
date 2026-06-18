# routes_telefonos.py
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool

from app.services.telefonos_service import (
    buscar_telefonos_cliente,
    listar_filtros_telefonos,
    obtener_detalle_telefono,
)


router = APIRouter()


@router.get("")
def vista_telefonos():
    root = Path(__file__).resolve().parents[2]
    return FileResponse(root / "frontend" / "views" / "telefonos.html")


@router.get("/buscar")
async def buscar_telefonos(
    q: str = Query(..., description="DNI, ID Cliente o teléfono"),
    idcartera: str | None = Query(default=None),
    whatsapp: str | None = Query(default=None),
    timbra: str | None = Query(default=None),
    tipo: str | None = Query(default=None),
    origen: str | None = Query(default=None),
):
    try:
        return await run_in_threadpool(
            buscar_telefonos_cliente,
            q=q,
            idcartera=idcartera,
            whatsapp=whatsapp,
            timbra=timbra,
            tipo=tipo,
            origen=origen,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error consultando teléfonos: {exc}")


@router.get("/filtros")
async def filtros_telefonos():
    try:
        return await run_in_threadpool(listar_filtros_telefonos)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error obteniendo filtros: {exc}")


@router.get("/detalle/{telefono}")
async def detalle_telefono(telefono: str):
    try:
        return await run_in_threadpool(obtener_detalle_telefono, telefono)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error obteniendo detalle del teléfono: {exc}")