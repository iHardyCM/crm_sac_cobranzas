from datetime import date
from datetime import datetime
from io import BytesIO
from typing import Optional

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
import pandas as pd
from app.services.corporativo_service import (
    obtener_carteras_corporativo,
    obtener_matriz_compromisos_corporativo,
    obtener_resumen_corporativo
)

router = APIRouter()


def calcular_estado_semaforo(calidad, tasa_caida):
    """
    Regla gerencial simple basada en montos caidos:
    - Saludable: calidad >= 70 y caida <= 30
    - Seguimiento: calidad >= 55 y caida <= 45
    - Critico: calidad baja o caida alta
    """

    calidad = calidad or 0
    tasa_caida = tasa_caida or 0

    if calidad >= 70 and tasa_caida <= 30:
        return "SALUDABLE"

    if calidad >= 55 and tasa_caida <= 45:
        return "SEGUIMIENTO"

    return "CRITICO"


@router.get("/resumen")
def resumen_corporativo(
    fecha_desde: Optional[date] = Query(default=None),
    fecha_hasta: Optional[date] = Query(default=None),
    idcartera: Optional[int] = Query(default=None)
):
    data = obtener_resumen_corporativo(
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        idcartera=idcartera
    )

    detalle = []

    for x in data:
        total_promesas = x.get("total_promesas", 0) or 0
        monto_pdp = x.get("monto_pdp", 0) or 0
        monto_pagado = x.get("monto_pagado", 0) or 0
        monto_hoy = x.get("monto_hoy", 0) or 0
        monto_proyectado = x.get("monto_proyectado", 0) or 0

        monto_caido = max(monto_proyectado, 0)

        calidad = (
            round((monto_pagado / monto_hoy) * 100, 2)
            if monto_hoy > 0
            else 0
        )

        tasa_caida = (
            round((monto_caido / monto_hoy) * 100, 2)
            if monto_hoy > 0
            else 0
        )

        estado_semaforo = calcular_estado_semaforo(
            calidad=calidad,
            tasa_caida=tasa_caida
        )

        fila = {
            **x,
            "monto_caido": monto_caido,
            "monto_pendiente": monto_caido,
            "calidad": calidad,
            "tasa_caida": tasa_caida,
            "estado_semaforo": estado_semaforo
        }

        detalle.append(fila)

    total_promesas = sum(x.get("total_promesas", 0) or 0 for x in detalle)
    monto_pdp = sum(x.get("monto_pdp", 0) or 0 for x in detalle)
    monto_pagado = sum(x.get("monto_pagado", 0) or 0 for x in detalle)
    monto_hoy = sum(x.get("monto_hoy", 0) or 0 for x in detalle)
    monto_proyectado = sum(x.get("monto_proyectado", 0) or 0 for x in detalle)
    monto_caido = sum(x.get("monto_caido", 0) or 0 for x in detalle)

    eficacia = (
        round((monto_pagado / monto_hoy) * 100, 2)
        if monto_hoy > 0
        else 0
    )

    tasa_caida = (
        round((monto_caido / monto_hoy) * 100, 2)
        if monto_hoy > 0
        else 0
    )

    calidad = eficacia

    mayor_caida = max(
        detalle,
        key=lambda x: x.get("tasa_caida", 0) or 0,
        default=None
    )

    menor_cumplimiento = min(
        detalle,
        key=lambda x: x.get("calidad", 0) or 0,
        default=None
    )

    mayor_caido = max(
        detalle,
        key=lambda x: x.get("monto_caido", 0) or 0,
        default=None
    )

    mejor_cartera = max(
        detalle,
        key=lambda x: x.get("calidad", 0) or 0,
        default=None
    )

    return {
        "resumen": {
            "total_promesas": total_promesas,
            "monto_pdp": monto_pdp,
            "monto_pagado": monto_pagado,
            "monto_hoy": monto_hoy,
            "monto_proyectado": monto_proyectado,
            "monto_caido": monto_caido,
            "monto_pendiente": monto_caido,
            "eficacia": eficacia,
            "tasa_caida": tasa_caida,
            "calidad": calidad
        },
        "alertas": {
            "mayor_caida": mayor_caida,
            "menor_cumplimiento": menor_cumplimiento,
            "mayor_caido": mayor_caido,
            "mayor_pendiente": mayor_caido,
            "mejor_cartera": mejor_cartera
        },
        "detalle": detalle
    }


@router.get("/filtros")
def filtros_corporativo():
    return {
        "carteras": obtener_carteras_corporativo()
    }


@router.get("/pdp-hoy")
def pdp_hoy_corporativo(
    idcartera: Optional[int] = Query(default=None)
):
    data = obtener_matriz_compromisos_corporativo(
        idcartera=idcartera,
        solo_hoy=True
    )

    return {
        "ok": True,
        "total": len(data),
        "data": data
    }


@router.get("/exportar")
def exportar_corporativo(
    fecha_desde: Optional[date] = Query(default=None),
    fecha_hasta: Optional[date] = Query(default=None),
    idcartera: Optional[int] = Query(default=None)
):
    data = resumen_corporativo(
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        idcartera=idcartera
    )

    resumen = data.get("resumen", {})
    alertas = data.get("alertas", {})
    detalle = data.get("detalle", [])
    matriz = obtener_matriz_compromisos_corporativo(
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        idcartera=idcartera
    )

    df_resumen = pd.DataFrame([{
        "total_promesas": resumen.get("total_promesas", 0),
        "monto_pdp": resumen.get("monto_pdp", 0),
        "monto_pagado": resumen.get("monto_pagado", 0),
        "monto_hoy": resumen.get("monto_hoy", 0),
        "monto_proyectado": resumen.get("monto_proyectado", 0),
        "pendiente_hoy": resumen.get("monto_proyectado", 0),
        "monto_caido": resumen.get("monto_caido", 0),
        "eficacia": resumen.get("eficacia", 0),
        "tasa_caida": resumen.get("tasa_caida", 0),
        "calidad": resumen.get("calidad", 0)
    }])

    filas_alertas = []
    for nombre, item in alertas.items():
        if not item:
            continue

        filas_alertas.append({
            "alerta": nombre,
            "idcartera": item.get("idcartera"),
            "cartera": item.get("cartera"),
            "total_promesas": item.get("total_promesas"),
            "monto_pdp": item.get("monto_pdp"),
            "monto_pagado": item.get("monto_pagado"),
            "monto_hoy": item.get("monto_hoy"),
            "monto_proyectado": item.get("monto_proyectado"),
            "pendiente_hoy": item.get("monto_proyectado"),
            "monto_caido": item.get("monto_caido"),
            "calidad": item.get("calidad"),
            "tasa_caida": item.get("tasa_caida"),
            "estado_semaforo": item.get("estado_semaforo")
        })

    df_detalle = pd.DataFrame(detalle)
    df_matriz = pd.DataFrame(matriz)

    output = BytesIO()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df_matriz.to_excel(writer, index=False, sheet_name="Matriz_Compromisos")
        df_resumen.to_excel(writer, index=False, sheet_name="Resumen")
        df_detalle.to_excel(writer, index=False, sheet_name="Detalle_KPI")

        for sheet in writer.sheets.values():
            sheet.freeze_panes = "A2"
            for column_cells in sheet.columns:
                max_length = max(
                    len(str(cell.value)) if cell.value is not None else 0
                    for cell in column_cells
                )
                sheet.column_dimensions[column_cells[0].column_letter].width = min(max_length + 2, 38)

    output.seek(0)

    fecha_descarga = datetime.now().strftime("%Y%m%d_%H%M")
    nombre_archivo = f"Reporte_Corporativo_{fecha_descarga}.xlsx"

    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f"attachment; filename={nombre_archivo}"
        }
    )
