from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.services.susurro_ia_service import (
    cerrar_sesion,
    crear_sesion,
    limpiar_sesion,
    obtener_sesion,
    recibir_fragmento,
)


router = APIRouter()


class CrearSesionRequest(BaseModel):
    agente: str | None = None
    cartera: str | None = None
    modo: str | None = "demo"


class FragmentoRequest(BaseModel):
    session_id: str
    texto: str
    speaker: str | None = "cliente"
    source: str | None = "manual"


@router.get("")
def vista_susurro_ia():
    root = Path(__file__).resolve().parents[2]
    return FileResponse(root / "frontend" / "views" / "susurro_ia.html")


@router.post("/sesiones")
def crear_sesion_susurro(data: CrearSesionRequest):
    return crear_sesion(
        agente=data.agente,
        cartera=data.cartera,
        modo=data.modo,
    )


@router.get("/sesiones/{session_id}")
def estado_sesion_susurro(session_id: str):
    try:
        return obtener_sesion(session_id)
    except ValueError as exc:
        return {
            "session_id": None,
            "estado": "EXPIRADA",
            "mensaje": str(exc),
            "current": None,
            "metrics": {},
            "detected_intents": [],
            "alerts": [],
            "fragments": [],
            "total_fragments": 0,
        }


@router.post("/fragmentos")
def fragmento_susurro(data: FragmentoRequest):
    try:
        return recibir_fragmento(
            session_id=data.session_id,
            texto=data.texto,
            speaker=data.speaker,
            source=data.source,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/sesiones/{session_id}/limpiar")
def limpiar_sesion_susurro(session_id: str):
    try:
        return limpiar_sesion(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/sesiones/{session_id}/cerrar")
def cerrar_sesion_susurro(session_id: str):
    try:
        return cerrar_sesion(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
