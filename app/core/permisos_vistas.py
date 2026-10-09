"""Permisos individuales de las vistas operativas con API autenticada.

La ausencia de una fila conserva el permiso derivado del perfil y cartera.
Un permiso de vista no amplía las carteras asignadas al usuario.
"""

import unicodedata
from typing import Dict

from fastapi import HTTPException, status
from sqlalchemy import text

from app.core.db_siscob import engine_siscob
from app.services.cliente_crm_service import COMPARTAMOS_CARTERAS


CATALOGO = (
    ("clientes", "Radar Compartamos"),
    ("compromisos", "Mis compromisos"),
    ("gestiones", "Compromisos del equipo"),
    ("telefonos", "Validación de teléfonos"),
    ("ia_feedback", "Análisis IA"),
)
CLAVES = frozenset(clave for clave, _ in CATALOGO)
PERFILES_GLOBALES = frozenset({
    "ADMINISTRADOR", "JEFE DE CARTERA", "JEFE DE CARTERAS",
    "JEFE DE COBRANZA", "JEFE CARTERA",
})


def _tipo(usuario: Dict) -> str:
    valor = unicodedata.normalize("NFD", str(usuario.get("tipo") or "").strip())
    return "".join(c for c in valor if unicodedata.category(c) != "Mn").upper()


def permisos_base(usuario: Dict) -> Dict[str, bool]:
    tipo = _tipo(usuario)
    global_ = tipo in PERFILES_GLOBALES
    supervisor = "SUPERVISOR" in tipo
    monitor = "MONITOR" in tipo and "CALIDAD" in tipo
    compartamos = puede_habilitar_clientes(usuario)
    return {
        "clientes": global_ or (not monitor and compartamos),
        "compromisos": not monitor,
        "gestiones": global_ or supervisor,
        "telefonos": not monitor,
        "ia_feedback": global_ or supervisor or monitor,
    }


def puede_habilitar_clientes(usuario: Dict) -> bool:
    if _tipo(usuario) in PERFILES_GLOBALES:
        return True
    carteras = list(usuario.get("idcarteras") or []) + [usuario.get("idcartera")]
    return any(
        str(c).strip().isdigit() and int(str(c).strip()) in COMPARTAMOS_CARTERAS
        for c in carteras if c is not None
    )


def leer_sobrescrituras(dni: str) -> Dict[str, bool]:
    with engine_siscob.connect() as conn:
        rows = conn.execute(text("""
            SELECT VISTA, PERMITIDO
            FROM CobAuto.dbo.CRM_USUARIO_VISTA
            WHERE USUARIO = :dni
        """), {"dni": dni}).mappings().all()
    return {r["VISTA"]: bool(r["PERMITIDO"]) for r in rows if r["VISTA"] in CLAVES}


def permisos_efectivos(usuario: Dict, sobrescrituras: Dict[str, bool] | None = None) -> Dict[str, bool]:
    permisos = permisos_base(usuario)
    cambios = sobrescrituras if sobrescrituras is not None else leer_sobrescrituras(usuario["dni"])
    permisos.update({clave: bool(valor) for clave, valor in cambios.items() if clave in CLAVES})
    permisos["clientes"] = permisos["clientes"] and puede_habilitar_clientes(usuario)
    return permisos


def tiene_vista(usuario: Dict, clave: str) -> bool:
    permisos = usuario.get("permisos_vistas")
    if permisos is None:
        # Compatibilidad con llamadas directas en los tests; en HTTP la
        # dependencia de sesión siempre consulta la tabla antes de llegar aquí.
        permisos = permisos_base(usuario)
    return bool(permisos.get(clave))


def exigir_vista(usuario: Dict, clave: str) -> None:
    if not tiene_vista(usuario, clave):
        from app.core.auth_dependencies import CODIGO_ACCESO_DENEGADO, cabeceras_codigo_error
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes acceso a esta vista.",
            headers=cabeceras_codigo_error(CODIGO_ACCESO_DENEGADO),
        )
