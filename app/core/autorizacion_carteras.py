"""Reglas de perfil y cartera para autorizar el acceso a datos de cobranza.

El usuario siempre viene de la sesion validada en el servidor
(requiere_clave_definitiva): tipo, idcartera e idcarteras salen de SISCOB y
CRM_SUPERVISOR_CARTERA, nunca del navegador.

Solo se usan reglas que YA existen en el CRM:
- Vision global: el mismo conjunto de perfiles de puedeVerCorporativo()
  (session.js / app_layout.js) y de perfil_puede_editar_prompt()
  (ia_analysis_service).
- Supervisor: TipoUsuario que contiene "SUPERVISOR" (esSupervisor() en session.js).
- Monitor de calidad: solo accede a Analisis IA (puedeAccederModulo en app_layout.js).
- Carteras Compartamos: las de COMPARTAMOS_CARTERAS en cliente_crm_service
  (se reutiliza esa constante; no hay una segunda lista en el backend).
"""

import logging
from typing import Dict, Iterable, List, Optional, Set

from fastapi import HTTPException, status
from sqlalchemy import text

from app.core.auth_dependencies import (
    CODIGO_ACCESO_DENEGADO,
    cabeceras_codigo_error,
    normalizar_tipo_usuario,
)
from app.core.db_siscob import engine_siscob
from app.services.cliente_crm_service import COMPARTAMOS_CARTERAS


logger = logging.getLogger(__name__)

PERFILES_VISION_GLOBAL = {
    "ADMINISTRADOR",
    "JEFE DE CARTERA",
    "JEFE DE CARTERAS",
    "JEFE DE COBRANZA",
    "JEFE CARTERA",
}

CARTERAS_COMPARTAMOS = frozenset(COMPARTAMOS_CARTERAS)

MENSAJE_SIN_ACCESO_MODULO = "Tu perfil no tiene acceso a este módulo."
MENSAJE_CARTERA_NO_PERMITIDA = "No tienes asignada la cartera de esta información."


def _entero(valor) -> Optional[int]:
    try:
        return int(str(valor).strip())
    except (TypeError, ValueError):
        return None


def perfil(usuario: Dict) -> str:
    return normalizar_tipo_usuario(usuario.get("tipo"))


def tiene_vision_global(usuario: Dict) -> bool:
    return perfil(usuario) in PERFILES_VISION_GLOBAL


def es_supervisor(usuario: Dict) -> bool:
    return "SUPERVISOR" in perfil(usuario)


def es_monitor_calidad(usuario: Dict) -> bool:
    tipo = perfil(usuario)
    return "MONITOR" in tipo and "CALIDAD" in tipo


def carteras_usuario(usuario: Dict) -> Set[int]:
    """Cartera principal + adicionales, tal como las resolvio el servidor."""
    carteras = {_entero(c) for c in (usuario.get("idcarteras") or [])}
    carteras.add(_entero(usuario.get("idcartera")))
    return {c for c in carteras if c is not None}


def carteras_permitidas(usuario: Dict) -> Optional[Set[int]]:
    """None = sin restriccion (vision global). Un set (posiblemente vacio) = restringir a esas."""
    if tiene_vision_global(usuario):
        return None
    return carteras_usuario(usuario)


def cartera_permitida(usuario: Dict, idcartera) -> bool:
    permitidas = carteras_permitidas(usuario)
    if permitidas is None:
        return True
    cartera = _entero(idcartera)
    return cartera is not None and cartera in permitidas


def alguna_cartera_permitida(usuario: Dict, carteras: Iterable) -> bool:
    permitidas = carteras_permitidas(usuario)
    if permitidas is None:
        return True
    return any(_entero(c) in permitidas for c in carteras)


def prohibido(mensaje: str = MENSAJE_CARTERA_NO_PERMITIDA) -> HTTPException:
    """403 por perfil/cartera: lleva el codigo ACCESO_DENEGADO (no es cambio de clave)."""
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=mensaje,
        headers=cabeceras_codigo_error(CODIGO_ACCESO_DENEGADO),
    )


def exigir_no_monitor_calidad(usuario: Dict) -> None:
    """El monitor de calidad solo usa Analisis IA (regla existente de app_layout)."""
    if es_monitor_calidad(usuario) and not tiene_vision_global(usuario):
        raise prohibido(MENSAJE_SIN_ACCESO_MODULO)


def puede_consultar_compartamos(usuario: Dict) -> bool:
    """Regla existente del modulo "clientes": vision global o alguna cartera Compartamos."""
    if tiene_vision_global(usuario):
        return True
    if es_monitor_calidad(usuario):
        return False
    return bool(carteras_usuario(usuario) & CARTERAS_COMPARTAMOS)


def cartera_principal_de_usuario(dni: str) -> Optional[int]:
    """IDCARTERA principal de un usuario de SISCOB (agente), sin filtrar Estado.

    Es la misma cartera que ya usan las consultas de compromisos del supervisor.
    """
    with engine_siscob.connect() as conn:
        row = conn.execute(text("""
            SELECT TOP 1 IDCARTERA
            FROM SISCOB.DBO.USUARIO WITH(NOLOCK)
            WHERE LTRIM(RTRIM(USUARIO)) = LTRIM(RTRIM(:dni))
        """), {"dni": str(dni or "").strip()}).fetchone()
    return _entero(row.IDCARTERA) if row else None


_TAMANO_LOTE_DNI = 500  # SQL Server admite ~2100 parametros por consulta


def carteras_compartamos_por_dni(dnis: Iterable[str]) -> Dict[str, Set[int]]:
    """Carteras Compartamos en que SISCOB.CLIENTE registra cada DNI.

    Es la misma relacion (CLIENTE.Dni -> CLIENTE.IdCartera) que ya usa
    cliente_crm_service para "carteras_siscob". Un DNI ausente del resultado
    significa que su cartera no se puede determinar.
    """
    dnis_limpios: List[str] = sorted({str(d).strip() for d in dnis if str(d or "").strip()})
    resultado: Dict[str, Set[int]] = {}
    if not dnis_limpios:
        return resultado

    carteras = sorted(CARTERAS_COMPARTAMOS)
    params_carteras = {f"c{i}": c for i, c in enumerate(carteras)}
    filtro_carteras = ", ".join(f":c{i}" for i in range(len(carteras)))

    with engine_siscob.connect() as conn:
        for inicio in range(0, len(dnis_limpios), _TAMANO_LOTE_DNI):
            lote = dnis_limpios[inicio:inicio + _TAMANO_LOTE_DNI]
            params = dict(params_carteras)
            params.update({f"d{i}": d for i, d in enumerate(lote)})
            filtro_dnis = ", ".join(f":d{i}" for i in range(len(lote)))
            filas = conn.execute(text(f"""
                SELECT DISTINCT
                    LTRIM(RTRIM(ISNULL(CL.Dni, ''))) AS DNI,
                    CL.IdCartera AS IDCARTERA
                FROM SISCOB.DBO.CLIENTE CL WITH(NOLOCK)
                WHERE CL.IdCartera IN ({filtro_carteras})
                  AND LTRIM(RTRIM(ISNULL(CL.Dni, ''))) IN ({filtro_dnis})
            """), params).fetchall()
            for fila in filas:
                cartera = _entero(fila.IDCARTERA)
                if cartera is not None:
                    resultado.setdefault(str(fila.DNI).strip(), set()).add(cartera)
    return resultado
