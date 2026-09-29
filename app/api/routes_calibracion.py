"""Endpoints de calibracion humana de la evaluacion IA.

Seguridad: todos los endpoints exigen sesion valida (requiere_clave_definitiva).
El perfil y el usuario que se auditan salen de la sesion; los campos "perfil"
y "usuario" del payload o la query se aceptan por compatibilidad y se ignoran.
"""

from typing import Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.core.auth_dependencies import normalizar_tipo_usuario, requiere_clave_definitiva

from app.services.calibracion_service import (
    enviar_llamada_a_revision,
    guardar_calibracion,
    listar_cola_revision,
    listar_motivos,
    obtener_calibracion,
    obtener_precision,
    perfil_puede_proponer_calibracion,
    perfil_puede_publicar_calibracion,
    recalcular_score_calibrado,
    resolver_calibracion,
    resolver_llamada,
)
from app.services.ia_analysis_service import perfil_puede_ver_historial_global_ia


router = APIRouter()

UsuarioCalibracion = Depends(requiere_clave_definitiva)


def _perfil_sesion(usuario: Dict) -> str:
    return normalizar_tipo_usuario(usuario.get("tipo"))


def _usuario_sesion(usuario: Dict) -> str:
    # La pantalla enviaba el DNI como "usuario" de la calibracion.
    return usuario.get("dni")


class CalibracionPayload(BaseModel):
    id_evaluacion_criterio: int
    accion: str = "CONFIRMAR"
    resultado_esperado: Optional[str] = None
    evidencia_valida: str = "SI"
    id_motivo: Optional[int] = None
    evidencia_revisor: Optional[str] = None
    comentario: Optional[str] = None
    usuario: Optional[str] = None
    perfil: Optional[str] = None
    enviar_a_revision: bool = False


class ResolucionPayload(BaseModel):
    estado: str = "PUBLICADA"
    usuario: Optional[str] = None
    motivo_rechazo: Optional[str] = None
    perfil: Optional[str] = None


class EnvioPayload(BaseModel):
    usuario: Optional[str] = None
    perfil: Optional[str] = None


@router.get("/motivos")
def motivos_calibracion(usuario: Dict = UsuarioCalibracion):
    try:
        return {"data": listar_motivos()}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error listando motivos: {exc}")


@router.get("/cola")
def cola_revision(usuario: Dict = UsuarioCalibracion):
    """Bandeja de Calidad: llamadas con calibraciones esperando decision."""
    try:
        return {"data": listar_cola_revision()}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error listando la cola de revision: {exc}")


@router.get("/permisos")
def permisos_calibracion(usuario: Dict = UsuarioCalibracion):
    """La pantalla pregunta que puede hacer el perfil, en vez de decidirlo ella.
    El perfil sale de la sesion; un "perfil" en la query se ignora."""
    perfil = _perfil_sesion(usuario)
    return {
        "puede_publicar": perfil_puede_publicar_calibracion(perfil),
        "puede_proponer": perfil_puede_proponer_calibracion(perfil),
    }


@router.post("/llamada/{id_feedback}/enviar")
def enviar_llamada(id_feedback: int, payload: EnvioPayload, usuario: Dict = UsuarioCalibracion):
    """Calidad o el supervisor entregan a jefatura lo que corrigieron."""
    try:
        return enviar_llamada_a_revision(
            id_feedback, _usuario_sesion(usuario), perfil=_perfil_sesion(usuario)
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error enviando a revision: {exc}")


@router.post("/llamada/{id_feedback}/resolver")
def resolver_llamada_completa(id_feedback: int, payload: ResolucionPayload,
                              usuario: Dict = UsuarioCalibracion):
    """Jefatura aprueba o rechaza todo lo que esta en revision en la llamada."""
    try:
        return resolver_llamada(
            id_feedback,
            estado=payload.estado,
            usuario=_usuario_sesion(usuario),
            motivo_rechazo=payload.motivo_rechazo,
            perfil=_perfil_sesion(usuario),
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error resolviendo la llamada: {exc}")


@router.get("/{id_feedback}")
def calibracion_de_llamada(id_feedback: int, usuario: Dict = UsuarioCalibracion):
    try:
        return obtener_calibracion(id_feedback)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error obteniendo calibracion: {exc}")


@router.post("/criterio")
def guardar_criterio(payload: CalibracionPayload, usuario: Dict = UsuarioCalibracion):
    try:
        return guardar_calibracion(
            payload.id_evaluacion_criterio,
            accion=payload.accion,
            resultado_esperado=payload.resultado_esperado,
            evidencia_valida=payload.evidencia_valida,
            id_motivo=payload.id_motivo,
            evidencia_revisor=payload.evidencia_revisor,
            comentario=payload.comentario,
            usuario=_usuario_sesion(usuario),
            perfil=_perfil_sesion(usuario),
            enviar_a_revision=payload.enviar_a_revision,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error guardando calibracion: {exc}")


@router.post("/{id_calibracion}/resolver")
def resolver(id_calibracion: int, payload: ResolucionPayload, usuario: Dict = UsuarioCalibracion):
    """Publicar o rechazar. Publicar es lo unico que mueve la nota de la llamada."""
    try:
        return resolver_calibracion(
            id_calibracion,
            estado=payload.estado,
            usuario=_usuario_sesion(usuario),
            motivo_rechazo=payload.motivo_rechazo,
            perfil=_perfil_sesion(usuario),
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error resolviendo calibracion: {exc}")


@router.post("/{id_feedback}/recalcular")
def recalcular(id_feedback: int, usuario: Dict = UsuarioCalibracion):
    try:
        return recalcular_score_calibrado(id_feedback)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error recalculando score: {exc}")


@router.get("/reporte/precision")
def reporte_precision(
    cartera: Optional[str] = Query(default=None),
    id_pauta: Optional[int] = Query(default=None),
    usuario: Dict = UsuarioCalibracion,
):
    """Precision de la IA. Solo perfiles con vision global la consultan: es una
    metrica del modulo, no del desempeno de un agente."""
    if not perfil_puede_ver_historial_global_ia(_perfil_sesion(usuario)):
        raise HTTPException(status_code=403, detail="Perfil sin acceso a la metrica de precision.")
    try:
        return obtener_precision(cartera=cartera, id_pauta=id_pauta)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error obteniendo precision: {exc}")
