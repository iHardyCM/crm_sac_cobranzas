from fastapi import APIRouter
from app.services.auth_service import validar_usuario

router = APIRouter()

@router.post("/login")
def login(payload: dict):
    dni = (payload.get("dni") or "").strip()
    if not dni or len(dni) != 8:
        return {"ok": False, "msg": "DNI inválido"}

    user = validar_usuario(dni)
    if not user:
        return {"ok": False, "msg": "Usuario no encontrado"}

    return {"ok": True, "user": user}