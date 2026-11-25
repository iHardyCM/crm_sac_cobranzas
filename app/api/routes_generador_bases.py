# routes_generador_bases.py
"""Generador de bases (score telefónico nuevo).

Seguridad (mismas reglas del CRM):
- Sesión válida y clave definitiva en todos los endpoints de datos (requiere_clave_definitiva).
- Perfil: visión global (administrador, jefes) o supervisor. El monitor de calidad no entra.
- Cartera: el usuario solo consulta, actualiza y genera sobre sus carteras (SISCOB.USUARIO +
  CRM_SUPERVISOR_CARTERA); la visión global puede elegir cualquiera. Nada de esto viene del navegador.
"""
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse, Response
from starlette.concurrency import run_in_threadpool

from app.core import autorizacion_carteras as autorizacion
from app.core.auth_dependencies import requiere_clave_definitiva
from app.services import generador_bases_service as servicio
from app.services import generador_rendimiento_service as rendimiento_servicio
from app.services.generador_bases_reglas import RecetaInvalida

router = APIRouter()
logger = logging.getLogger(__name__)

Usuario = Depends(requiere_clave_definitiva)
MENSAJE_ERROR_TECNICO = "No se pudo completar la operación del generador de bases. Intenta nuevamente."
MENSAJE_SIN_MODULO = "Tu perfil no tiene acceso al generador de bases."


def _exigir_modulo(usuario: Dict) -> None:
    autorizacion.exigir_no_monitor_calidad(usuario)
    if not (autorizacion.tiene_vision_global(usuario) or autorizacion.es_supervisor(usuario)):
        raise autorizacion.prohibido(MENSAJE_SIN_MODULO)


async def _permitida(usuario: Dict, idcartera: int) -> bool:
    """Una cartera combinada (p. ej. 901 = 126 + 128) exige permiso sobre todas sus carteras reales."""
    carteras = await run_in_threadpool(servicio.carteras_reales, int(idcartera))
    return all(autorizacion.cartera_permitida(usuario, c) for c in carteras)


async def _exigir_cartera(usuario: Dict, idcartera: int) -> None:
    _exigir_modulo(usuario)
    try:
        ok = await _permitida(usuario, idcartera)
    except Exception:
        raise _error("permiso de cartera", usuario)
    if not ok:
        raise autorizacion.prohibido()


def _error(contexto: str, usuario: Dict) -> HTTPException:
    logger.exception("Error en generador de bases (%s) usuario=%s", contexto, usuario.get("dni"))
    return HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=MENSAJE_ERROR_TECNICO)


@router.get("")
def vista_generador_bases():
    """Pantalla del generador (solo HTML; los datos se piden a los endpoints protegidos)."""
    root = Path(__file__).resolve().parents[2]
    return FileResponse(root / "frontend" / "views" / "score_telefonico.html")


@router.get("/carteras")
async def carteras(usuario: Dict = Usuario):
    _exigir_modulo(usuario)
    try:
        return {"data": await run_in_threadpool(servicio.listar_carteras, autorizacion.carteras_permitidas(usuario))}
    except Exception:
        raise _error("carteras", usuario)


@router.get("/catalogo")
async def catalogo(idcartera: int = Query(...), usuario: Dict = Usuario):
    await _exigir_cartera(usuario, idcartera)
    try:
        return await run_in_threadpool(servicio.obtener_catalogo, idcartera)
    except Exception:
        raise _error("catalogo", usuario)


@router.post("/consulta")
async def consulta(cuerpo: Dict[str, Any] = Body(...), usuario: Dict = Usuario):
    """cuerpo: {idcartera, canal?, filtros: [...], condiciones: {CODIGO: QUITAR|SOLO|INDIFERENTE},
    telefonos_por_cliente?, pagina?, tamano?}"""
    idcartera = _idcartera(cuerpo)
    await _exigir_cartera(usuario, idcartera)
    try:
        return await run_in_threadpool(servicio.consultar, idcartera, cuerpo,
                                       cuerpo.get("pagina") or 1, cuerpo.get("tamano") or 50)
    except RecetaInvalida as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        raise _error("consulta", usuario)


@router.post("/actualizar/{idcartera}")
async def actualizar(idcartera: int, usuario: Dict = Usuario):
    """Botón Actualizar: historial, alineación, universo, score y tabla de trabajo de la cartera."""
    await _exigir_cartera(usuario, idcartera)
    try:
        resultado = await run_in_threadpool(servicio.actualizar_cartera, idcartera, usuario["dni"])
    except Exception:
        raise _error("actualizar", usuario)
    if resultado.get("Resultado") == "OCUPADA":
        return {"ok": False, "ocupada": True, "detalle": resultado,
                "mensaje": "La cartera ya se está actualizando. Espera a que termine."}
    return {"ok": resultado.get("Estado") == "OK", "ocupada": False, "detalle": resultado}


@router.post("/nombre")
async def nombre_propuesto(cuerpo: Dict[str, Any] = Body(...), usuario: Dict = Usuario):
    """Nombre legible propuesto para la base con la receta actual (el usuario lo puede corregir antes de generar)."""
    idcartera = _idcartera(cuerpo)
    await _exigir_cartera(usuario, idcartera)
    try:
        return await run_in_threadpool(servicio.proponer_nombre, idcartera, cuerpo)
    except RecetaInvalida as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception:
        raise _error("nombre de la base", usuario)


@router.post("/generar")
async def generar(cuerpo: Dict[str, Any] = Body(...), usuario: Dict = Usuario):
    """Registra la base (receta + teléfonos) y devuelve su código y nombre. El archivo se baja con /bases/{id}/archivo."""
    idcartera = _idcartera(cuerpo)
    await _exigir_cartera(usuario, idcartera)
    try:
        return await run_in_threadpool(servicio.generar_base, idcartera, cuerpo, usuario["dni"])
    except RecetaInvalida as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        raise _error("generar", usuario)


@router.get("/bases")
async def bases(idcartera: Optional[int] = Query(None), dias: int = Query(30), usuario: Dict = Usuario):
    _exigir_modulo(usuario)
    if idcartera is not None and not await _permitida(usuario, idcartera):
        raise autorizacion.prohibido()
    try:
        return {"data": await run_in_threadpool(servicio.listar_bases, autorizacion.carteras_permitidas(usuario),
                                                idcartera, dias)}
    except Exception:
        raise _error("bases", usuario)


@router.get("/bases/{id_base}/archivo")
async def archivo_base(id_base: int, formato: str = Query("xlsx", pattern="^(xlsx|csv)$"), usuario: Dict = Usuario):
    """Archivo de la base: Excel (xlsx) o CSV delimitado por comas (csv), con IdCliente de SISCOB."""
    _exigir_modulo(usuario)
    try:
        cabecera = await run_in_threadpool(servicio.obtener_base, id_base)
    except Exception:
        raise _error("archivo", usuario)
    if not cabecera or not cabecera.get("Codigo"):
        raise HTTPException(status_code=404, detail="La base no existe.")
    if not await _permitida(usuario, cabecera["IdCartera"]):
        raise autorizacion.prohibido()
    try:
        contenido = await run_in_threadpool(servicio.exportar_base, id_base, formato)
    except Exception:
        raise _error("archivo", usuario)
    tipo, extension = servicio.FORMATOS_ARCHIVO[formato]
    nombre = f"{cabecera['NombreArchivo']}{extension}"
    return Response(content=contenido, media_type=tipo,
                    headers={"Content-Disposition": f'attachment; filename="{nombre}"'})


@router.post("/rendimiento")
async def rendimiento(cuerpo: Dict[str, Any] = Body(...), usuario: Dict = Usuario):
    """Rendimiento del score (fase 13): cuerpo {idcartera, dias: 7|14|30, universo: CARTERA|BASES,
    filtros?: {Tramo|Orden|Canal|Osiptel|Timbra|Whatsapp|Origen|Fuente|Color: [valores]}}."""
    idcartera = _idcartera(cuerpo)
    await _exigir_cartera(usuario, idcartera)
    try:
        dias = int(cuerpo.get("dias") or 7)
        return await run_in_threadpool(rendimiento_servicio.rendimiento, idcartera, dias,
                                       str(cuerpo.get("universo") or "CARTERA"), cuerpo.get("filtros"))
    except (rendimiento_servicio.ConsultaInvalida, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception:
        raise _error("rendimiento del score", usuario)


@router.post("/rendimiento/cobertura")
async def rendimiento_cobertura(cuerpo: Dict[str, Any] = Body(...), usuario: Dict = Usuario):
    """Cobertura del periodo por tramo: teléfonos distintos y cuántos recibieron al menos una llamada.
    Mismo cuerpo que /rendimiento. Va aparte porque cuenta teléfono por teléfono y tarda más."""
    idcartera = _idcartera(cuerpo)
    await _exigir_cartera(usuario, idcartera)
    try:
        dias = int(cuerpo.get("dias") or 7)
        return await run_in_threadpool(rendimiento_servicio.cobertura, idcartera, dias,
                                       str(cuerpo.get("universo") or "CARTERA"), cuerpo.get("filtros"))
    except (rendimiento_servicio.ConsultaInvalida, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception:
        raise _error("cobertura del score", usuario)


@router.get("/score/version")
async def score_version(idcartera: int = Query(...), usuario: Dict = Usuario):
    """Qué significa el score de la cartera: tramos, tasa de CEF por tramo en la prueba, puntos por característica."""
    await _exigir_cartera(usuario, idcartera)
    try:
        return await run_in_threadpool(servicio.score_version, idcartera)
    except Exception:
        raise _error("score_version", usuario)


@router.get("/score/telefono")
async def score_telefono(idcartera: int = Query(...), dni: str = Query(..., max_length=20),
                         telefono: str = Query(..., max_length=12), usuario: Dict = Usuario):
    """Por qué un teléfono tiene su score: puntos de cada característica."""
    await _exigir_cartera(usuario, idcartera)
    try:
        detalle = await run_in_threadpool(servicio.score_telefono, idcartera, dni.strip(), telefono.strip())
    except Exception:
        raise _error("score_telefono", usuario)
    if detalle is None:
        raise HTTPException(status_code=404, detail="El teléfono no está en el score vigente de la cartera.")
    return detalle


def _idcartera(cuerpo: Dict[str, Any]) -> int:
    try:
        return int(cuerpo.get("idcartera"))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Indica la cartera.")
