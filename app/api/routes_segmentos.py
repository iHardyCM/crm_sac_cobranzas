# routes_segmentos.py
"""Carga de segmentos del banco (o propios) para el generador de bases.

Seguridad: sesión válida con clave definitiva y perfil de visión global (administrador y jefes), como
pide el diseño ("lo cargan administrador y jefe de cartera"). La carga es por entidad, no por cartera.
El archivo se manda en cada paso (analizar, vista previa, cargar): no queda guardado en el servidor.
"""
import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool

from app.core import autorizacion_carteras as autorizacion
from app.core.auth_dependencies import requiere_clave_definitiva
from app.core.db_siscob import engine_siscob
from app.services import segmentos_service as seg

router = APIRouter()
logger = logging.getLogger(__name__)

Usuario = Depends(requiere_clave_definitiva)
MAX_BYTES = 40 * 1024 * 1024
EXTENSIONES = (".xlsx", ".xlsm", ".xlsb", ".csv")
MENSAJE_ERROR = "No se pudo completar la carga de segmentos. Intenta nuevamente."


def _exigir_perfil(usuario: Dict) -> None:
    if not autorizacion.tiene_vision_global(usuario):
        raise autorizacion.prohibido("Solo administración y jefes de cartera cargan segmentos.")


def _error(contexto: str, usuario: Dict) -> HTTPException:
    logger.exception("Error en carga de segmentos (%s) usuario=%s", contexto, usuario.get("dni"))
    return HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=MENSAJE_ERROR)


async def _leer(archivo: UploadFile) -> bytes:
    nombre = (archivo.filename or "").lower()
    if not nombre.endswith(EXTENSIONES):
        raise HTTPException(status_code=400, detail="Sube un archivo .xlsx, .xlsb o .csv.")
    contenido = await archivo.read()
    if not contenido:
        raise HTTPException(status_code=400, detail="El archivo está vacío.")
    if len(contenido) > MAX_BYTES:
        raise HTTPException(status_code=400, detail="El archivo pasa de 40 MB.")
    return contenido


def _definicion(texto: str) -> seg.DefinicionCarga:
    try:
        datos = json.loads(texto or "{}")
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Configuración inválida.")
    try:
        return seg.definicion_desde_dict(datos)
    except seg.CargaInvalida as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("")
def vista_segmentos():
    root = Path(__file__).resolve().parents[2]
    return FileResponse(root / "frontend" / "views" / "segmentos.html")


@router.get("/entidades")
async def entidades(usuario: Dict = Usuario):
    _exigir_perfil(usuario)

    def _tarea():
        with engine_siscob.connect() as conn:
            return seg.listar_entidades(conn)
    try:
        return {"data": await run_in_threadpool(_tarea)}
    except Exception:
        raise _error("entidades", usuario)


@router.post("/analizar")
async def analizar(archivo: UploadFile = File(...), hoja: Optional[str] = Form(None), usuario: Dict = Usuario):
    _exigir_perfil(usuario)
    contenido = await _leer(archivo)
    try:
        return await run_in_threadpool(seg.analizar_archivo, contenido, archivo.filename, hoja or None)
    except seg.CargaInvalida as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        raise _error("analizar", usuario)


@router.post("/previsualizar")
async def previsualizar(archivo: UploadFile = File(...), definicion: str = Form(...), usuario: Dict = Usuario):
    _exigir_perfil(usuario)
    contenido = await _leer(archivo)
    d = _definicion(definicion)

    def _tarea():
        df = seg.leer_archivo(contenido, archivo.filename, d.hoja)
        with engine_siscob.connect() as conn:
            r = seg.previsualizar(conn, d, df)
        r.pop("filas", None)
        return r
    try:
        return await run_in_threadpool(_tarea)
    except seg.CargaInvalida as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        raise _error("previsualizar", usuario)


@router.post("/cargar")
async def cargar(archivo: UploadFile = File(...), definicion: str = Form(...), usuario: Dict = Usuario):
    _exigir_perfil(usuario)
    contenido = await _leer(archivo)
    d = _definicion(definicion)

    def _tarea():
        df = seg.leer_archivo(contenido, archivo.filename, d.hoja)
        with engine_siscob.begin() as conn:
            return seg.cargar(conn, d, df, archivo.filename, str(usuario["dni"]))
    try:
        return await run_in_threadpool(_tarea)
    except seg.CargaInvalida as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        raise _error("cargar", usuario)


@router.get("/cargas")
async def cargas(limite: int = Query(100), usuario: Dict = Usuario):
    _exigir_perfil(usuario)

    def _tarea():
        with engine_siscob.connect() as conn:
            return seg.listar_cargas(conn, limite)
    try:
        return {"data": await run_in_threadpool(_tarea)}
    except Exception:
        raise _error("cargas", usuario)


@router.post("/cargas/{id_carga}/anular")
async def anular(id_carga: int, usuario: Dict = Usuario):
    """La carga deja de usarse en el generador (queda en el historial como ANULADA)."""
    _exigir_perfil(usuario)

    def _tarea():
        with engine_siscob.begin() as conn:
            return seg.anular_carga(conn, id_carga)
    try:
        if not await run_in_threadpool(_tarea):
            raise HTTPException(status_code=404, detail="La carga no existe o ya no está vigente.")
        logger.info("Carga de segmentos %s anulada por %s", id_carga, usuario.get("dni"))
        return {"ok": True}
    except HTTPException:
        raise
    except Exception:
        raise _error("anular", usuario)
