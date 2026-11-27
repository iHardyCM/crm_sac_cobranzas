# routes_zonas_restringidas.py
"""Zonas restringidas (mapa del Perú): departamentos donde no se gestiona.

Seguridad: sesión válida con clave definitiva en cada endpoint.
- Ver (mapa, restricciones, clientes excluidos): administración, jefes y supervisores.
- Registrar y levantar: administración y jefes de cartera (visión global).
Las restricciones afectan a todas las carteras que alcancen, por eso no se filtra por la cartera del usuario.
"""
import logging
import time
from datetime import datetime
from pathlib import Path
from datetime import date
from threading import Lock
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse, Response
from starlette.concurrency import run_in_threadpool

from app.core import autorizacion_carteras as autorizacion
from app.core.auth_dependencies import requiere_clave_definitiva
from app.core.db_siscob import engine_siscob
from app.services import zonas_restringidas_service as zonas

router = APIRouter()
logger = logging.getLogger(__name__)

Usuario = Depends(requiere_clave_definitiva)
MENSAJE_ERROR = "No se pudo completar la operación de zonas restringidas. Intenta nuevamente."
MENSAJE_SIN_INSTALAR = "Falta instalar score_telefonico_fase19_zonas.sql en CobAuto."
_COBERTURA_VIGENCIA_SEGUNDOS = 600
_cobertura_cache = None
_cobertura_lock = Lock()


def _puede_editar(usuario: Dict) -> bool:
    return autorizacion.tiene_vision_global(usuario)


def _exigir_ver(usuario: Dict) -> None:
    if not (autorizacion.tiene_vision_global(usuario) or autorizacion.es_supervisor(usuario)):
        raise autorizacion.prohibido("Tu perfil no tiene acceso a zonas restringidas.")


def _exigir_editar(usuario: Dict) -> None:
    if not _puede_editar(usuario):
        raise autorizacion.prohibido("Solo administración y jefes de cartera registran o levantan zonas.")


def _error(contexto: str, usuario: Dict) -> HTTPException:
    logger.exception("Error en zonas restringidas (%s) usuario=%s", contexto, usuario.get("dni"))
    return HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=MENSAJE_ERROR)


def _exigir_instalado(conn) -> None:
    if not zonas.disponible(conn):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=MENSAJE_SIN_INSTALAR)


@router.get("")
def vista_zonas():
    """Pantalla (solo HTML; los datos se piden a los endpoints protegidos)."""
    root = Path(__file__).resolve().parents[2]
    return FileResponse(root / "frontend" / "views" / "zonas.html")


@router.get("/estado")
async def estado(usuario: Dict = Usuario):
    _exigir_ver(usuario)

    def _tarea():
        with engine_siscob.connect() as conn:
            _exigir_instalado(conn)
            return {"zonas": zonas.zonas(conn), "carteras": zonas.carteras(conn),
                    "puede_editar": _puede_editar(usuario)}
    try:
        return await run_in_threadpool(_tarea)
    except HTTPException:
        raise
    except Exception:
        raise _error("estado", usuario)


@router.get("/excluidos")
async def excluidos(usuario: Dict = Usuario):
    """Clientes que hoy salen de las bases, por zona y cartera (puede tardar unos segundos)."""
    _exigir_ver(usuario)

    def _tarea():
        with engine_siscob.connect() as conn:
            _exigir_instalado(conn)
            return zonas.excluidos(conn)
    try:
        return await run_in_threadpool(_tarea)
    except HTTPException:
        raise
    except Exception:
        raise _error("excluidos", usuario)


@router.get("/cobertura")
async def cobertura(refrescar: bool = Query(False), usuario: Dict = Usuario):
    """Qué tan completo está el departamento en la base de trabajo de cada cartera (puede tardar unos segundos)."""
    _exigir_ver(usuario)

    def _tarea():
        global _cobertura_cache
        with _cobertura_lock:
            ahora = time.monotonic()
            if not refrescar and _cobertura_cache is not None:
                calculado, resultado = _cobertura_cache
                if ahora - calculado < _COBERTURA_VIGENCIA_SEGUNDOS:
                    return resultado
            inicio = time.perf_counter()
            try:
                with engine_siscob.connect() as conn:
                    datos = zonas.cobertura(conn)
                resultado = {**datos, "calculado_en": datetime.now().astimezone().isoformat(timespec="seconds")}
                _cobertura_cache = (time.monotonic(), resultado)
                return resultado
            finally:
                logger.info("Cálculo de cobertura de zonas: %.3f s", time.perf_counter() - inicio)
    try:
        return await run_in_threadpool(_tarea)
    except Exception:
        raise _error("cobertura", usuario)


@router.get("/excel")
async def excel(idcartera: Optional[int] = Query(None, gt=0), usuario: Dict = Usuario):
    """Libro para corroborar. Trae DNI: cada usuario solo descarga las carteras que tiene asignadas."""
    _exigir_ver(usuario)
    permitidas = autorizacion.carteras_permitidas(usuario)
    if idcartera is not None:
        if permitidas is not None and idcartera not in permitidas:
            raise autorizacion.prohibido()
        permitidas = {idcartera}
    lista = None if permitidas is None else sorted(permitidas)

    def _tarea():
        inicio = time.perf_counter()
        try:
            with engine_siscob.connect() as conn:
                _exigir_instalado(conn)
                return zonas.excel(conn, lista)
        finally:
            logger.info("Cálculo de Excel de zonas: %.3f s", time.perf_counter() - inicio)
    try:
        contenido = await run_in_threadpool(_tarea)
    except HTTPException:
        raise
    except Exception:
        raise _error("excel", usuario)
    nombre = f"zonas_restringidas_{date.today():%Y%m%d}{f'_{idcartera}' if idcartera else ''}.xlsx"
    return Response(content=contenido,
                    media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f'attachment; filename="{nombre}"'})


@router.post("/simular")
async def simular(cuerpo: Dict[str, Any] = Body(...), usuario: Dict = Usuario):
    _exigir_ver(usuario)

    def _tarea():
        with engine_siscob.connect() as conn:
            return zonas.simular(conn, cuerpo.get("departamentos") or [], bool(cuerpo.get("todas")),
                                 cuerpo.get("carteras") or [])
    try:
        return {"data": await run_in_threadpool(_tarea)}
    except zonas.ZonaInvalida as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        raise _error("simular", usuario)


@router.post("")
async def registrar(cuerpo: Dict[str, Any] = Body(...), usuario: Dict = Usuario):
    _exigir_editar(usuario)
    try:
        datos = zonas.validar_registro(cuerpo)
    except zonas.ZonaInvalida as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    def _tarea():
        with engine_siscob.begin() as conn:
            _exigir_instalado(conn)
            return zonas.registrar(conn, datos, str(usuario["dni"]))
    try:
        resultado = await run_in_threadpool(_tarea)
        logger.info("Zonas restringidas registradas por %s: %s", usuario.get("dni"), resultado)
        return {"data": resultado}
    except HTTPException:
        raise
    except Exception:
        raise _error("registrar", usuario)


@router.post("/levantar")
async def levantar(cuerpo: Dict[str, Any] = Body(...), usuario: Dict = Usuario):
    """Levanta una o varias restricciones (quedan en el historial como LEVANTADA)."""
    _exigir_editar(usuario)

    def _tarea():
        with engine_siscob.begin() as conn:
            _exigir_instalado(conn)
            return zonas.levantar(conn, cuerpo.get("ids") or [], cuerpo.get("motivo") or "", str(usuario["dni"]))
    try:
        n = await run_in_threadpool(_tarea)
        if not n:
            raise HTTPException(status_code=404, detail="Las restricciones ya no están activas.")
        logger.info("Zonas restringidas %s levantadas por %s", cuerpo.get("ids"), usuario.get("dni"))
        return {"levantadas": n}
    except zonas.ZonaInvalida as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except HTTPException:
        raise
    except Exception:
        raise _error("levantar", usuario)
