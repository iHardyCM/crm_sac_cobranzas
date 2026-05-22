from fastapi import APIRouter, Query
from app.services.cliente_service import buscar_cliente

router = APIRouter()

@router.get("/buscar")
def buscar(valor: str = Query(None)):
    return buscar_cliente(valor=valor)