from typing import Optional
from pathlib import Path

from fastapi import APIRouter, Query
from fastapi.responses import FileResponse

from app.services.control_horario_service import obtener_resumen_control_horario


router = APIRouter()


@router.get("")
def vista_control_horario():
    root = Path(__file__).resolve().parents[2]
    return FileResponse(root / "frontend" / "views" / "control_horario.html")


@router.get("/resumen")
def resumen_control_horario(
    fecha: Optional[str] = Query(default=None),
    idcartera: Optional[int] = Query(default=None),
    idusuario: Optional[int] = Query(default=None)
):
    return obtener_resumen_control_horario(
        fecha=fecha,
        idcartera=idcartera,
        idusuario=idusuario
    )
