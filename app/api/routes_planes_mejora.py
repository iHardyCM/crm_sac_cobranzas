from fastapi import APIRouter, Body, HTTPException, Query

from app.services.planes_mejora_service import REGLA, cerrar_plan, crear_plan, listar_planes

router = APIRouter()


@router.get("")
def planes_listar(estado: str | None = Query(default=None), agente: str | None = Query(default=None)):
    try:
        return {"regla": REGLA, "data": listar_planes(estado=estado, agente=agente)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error listando planes de mejora: {exc}")


@router.post("")
def planes_crear(payload: dict = Body(...)):
    try:
        return crear_plan(
            agente=payload.get("agente"),
            codigo_criterio=payload.get("codigo_criterio"),
            accion_acordada=payload.get("accion_acordada"),
            responsable=payload.get("responsable"),
            usuario=payload.get("usuario"),
        )
    except LookupError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error creando plan de mejora: {exc}")


@router.post("/{id_plan}/cerrar")
def planes_cerrar(id_plan: int, payload: dict = Body(...)):
    try:
        return cerrar_plan(id_plan, estado=payload.get("estado"), comentario=payload.get("comentario"), usuario=payload.get("usuario"))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error cerrando plan de mejora: {exc}")
