"""Endpoints de calibracion humana de la evaluacion IA."""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.services.calibracion_service import (
    guardar_calibracion,
    listar_motivos,
    obtener_calibracion,
    obtener_precision,
    recalcular_score_calibrado,
    resolver_calibracion,
)
from app.services.ia_analysis_service import perfil_puede_ver_historial_global_ia


router = APIRouter()


class CalibracionPayload(BaseModel):
    id_evaluacion_criterio: int
    accion: str = "CONFIRMAR"
    resultado_esperado: Optional[str] = None
    evidencia_valida: str = "SI"
    id_motivo: Optional[int] = None
    evidencia_revisor: Optional[str] = None
    comentario: Optional[str] = None
    usuario: Optional[str] = None
    enviar_a_revision: bool = False


class ResolucionPayload(BaseModel):
    estado: str = "PUBLICADA"
    usuario: Optional[str] = None
    motivo_rechazo: Optional[str] = None


@router.get("/motivos")
def motivos_calibracion():
    try:
        return {"data": listar_motivos()}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error listando motivos: {exc}")


@router.get("/{id_feedback}")
def calibracion_de_llamada(id_feedback: int):
    try:
        return obtener_calibracion(id_feedback)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error obteniendo calibracion: {exc}")


@router.post("/criterio")
def guardar_criterio(payload: CalibracionPayload):
    try:
        return guardar_calibracion(
            payload.id_evaluacion_criterio,
            accion=payload.accion,
            resultado_esperado=payload.resultado_esperado,
            evidencia_valida=payload.evidencia_valida,
            id_motivo=payload.id_motivo,
            evidencia_revisor=payload.evidencia_revisor,
            comentario=payload.comentario,
            usuario=payload.usuario,
            enviar_a_revision=payload.enviar_a_revision,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error guardando calibracion: {exc}")


@router.post("/{id_calibracion}/resolver")
def resolver(id_calibracion: int, payload: ResolucionPayload):
    """Publicar o rechazar. Publicar es lo unico que mueve la nota de la llamada."""
    try:
        return resolver_calibracion(
            id_calibracion,
            estado=payload.estado,
            usuario=payload.usuario,
            motivo_rechazo=payload.motivo_rechazo,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error resolviendo calibracion: {exc}")


@router.post("/{id_feedback}/recalcular")
def recalcular(id_feedback: int):
    try:
        return recalcular_score_calibrado(id_feedback)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error recalculando score: {exc}")


@router.get("/reporte/precision")
def reporte_precision(
    cartera: Optional[str] = Query(default=None),
    id_pauta: Optional[int] = Query(default=None),
    perfil: Optional[str] = Query(default=None),
):
    """Precision de la IA. Solo perfiles con vision global la consultan: es una
    metrica del modulo, no del desempeno de un agente."""
    if not perfil_puede_ver_historial_global_ia(perfil):
        raise HTTPException(status_code=403, detail="Perfil sin acceso a la metrica de precision.")
    try:
        return obtener_precision(cartera=cartera, id_pauta=id_pauta)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error obteniendo precision: {exc}")
