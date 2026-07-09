from typing import Optional
from pathlib import Path

from fastapi import APIRouter, Query
from fastapi.responses import FileResponse, StreamingResponse

from app.services.control_horario_service import (
    generar_excel_control_horario,
    obtener_matriz_mensual_control_horario,
    obtener_resumen_control_horario,
)


router = APIRouter()


def parse_ids_cartera(ids: Optional[str]):
    if not ids:
        return []
    resultado = []
    for item in ids.split(","):
        item = item.strip()
        if item.isdigit():
            resultado.append(int(item))
    return resultado


@router.get("")
def vista_control_horario():
    root = Path(__file__).resolve().parents[2]
    return FileResponse(root / "frontend" / "views" / "control_horario.html")


@router.get("/resumen")
def resumen_control_horario(
    fecha: Optional[str] = Query(default=None),
    idcartera: Optional[int] = Query(default=None),
    idusuario: Optional[int] = Query(default=None),
    incluir_apoyo_recupero: bool = Query(default=False)
):
    return obtener_resumen_control_horario(
        fecha=fecha,
        idcartera=idcartera,
        idusuario=idusuario,
        incluir_apoyo_recupero=incluir_apoyo_recupero
    )


@router.get("/matriz-mensual")
def matriz_mensual_control_horario(
    fecha: Optional[str] = Query(default=None),
    idcartera: Optional[int] = Query(default=None),
    idusuario: Optional[int] = Query(default=None),
    incluir_apoyo_recupero: bool = Query(default=False)
):
    return obtener_matriz_mensual_control_horario(
        fecha=fecha,
        idcartera=idcartera,
        idusuario=idusuario,
        incluir_apoyo_recupero=incluir_apoyo_recupero
    )


@router.get("/exportar")
def exportar_control_horario(
    fecha: Optional[str] = Query(default=None),
    idcartera: Optional[int] = Query(default=None),
    ids: Optional[str] = Query(default=None),
    idusuario: Optional[int] = Query(default=None),
    incluir_apoyo_recupero: bool = Query(default=False)
):
    idcarteras = parse_ids_cartera(ids)
    if idcartera is not None and not idcarteras:
        idcarteras = [idcartera]

    output, nombre_archivo = generar_excel_control_horario(
        fecha=fecha,
        idcarteras=idcarteras,
        idusuario=idusuario,
        incluir_apoyo_recupero=incluir_apoyo_recupero
    )

    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f"attachment; filename={nombre_archivo}"
        }
    )
