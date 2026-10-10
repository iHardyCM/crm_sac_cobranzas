import logging
from typing import Callable, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core import autorizacion_carteras as autorizacion
from app.core.auth_dependencies import requiere_clave_definitiva
from app.core.permisos_vistas import exigir_vista
from app.services.cliente_crm_service import COMPARTAMOS_CARTERAS, campo, identificador
from app.services.cliente_service import buscar_cliente

logger = logging.getLogger(__name__)

router = APIRouter()

MENSAJE_ERROR_TECNICO = "No se pudo completar la consulta del cliente. Intenta nuevamente."
MENSAJE_CLIENTE_NO_PERMITIDO = (
    "No tienes acceso a la información de este cliente: tiene operaciones en una cartera "
    "que no tienes asignada o no se pudo confirmar su cartera."
)


def _denegar(usuario: Dict, motivo: str, carteras: Optional[List[int]] = None) -> None:
    # No se registra el DNI del cliente: solo el usuario, el motivo y las carteras.
    logger.info(
        "Consulta de cliente denegada usuario=%s motivo=%s carteras=%s",
        usuario.get("dni"), motivo, carteras,
    )
    raise autorizacion.prohibido(MENSAJE_CLIENTE_NO_PERMITIDO)


def _verificador_de_acceso(usuario: Dict, contexto: Optional[Dict] = None) -> Optional[Callable[[List[Dict]], Dict[str, set[int]]]]:
    """Regla fail closed para usuarios sin vision global.

    VW_CLIENTE_CRM_SAC no expone la cartera de cada operacion, asi que no se
    puede filtrar operacion por operacion. La unica relacion confiable es
    SISCOB.CLIENTE (Dni -> IdCartera). Por eso se decide sobre la entidad
    completa (todas las filas que se devolverian):
      - todas las filas deben tener DNI;
      - cada DNI debe tener al menos una cartera Compartamos en SISCOB;
      - un usuario asignado a Compartamos puede consultar cualquiera de sus
        carteras en Radar; las otras carteras siguen fuera de su alcance.
    Si algo no se cumple o no se puede determinar: 403 y no se devuelve nada.
    """
    if autorizacion.tiene_vision_global(usuario):
        return None
    asignadas = autorizacion.carteras_usuario(usuario)
    permitidas = set(asignadas)
    if asignadas & autorizacion.CARTERAS_COMPARTAMOS:
        permitidas.update(autorizacion.CARTERAS_COMPARTAMOS)

    def verificar(filas: List[Dict]) -> Dict[str, set[int]]:
        dnis = {identificador(campo(fila, "DNI")) for fila in filas}
        if not filas or "" in dnis:
            _denegar(usuario, "filas_sin_dni")

        carteras_por_dni = autorizacion.carteras_compartamos_por_dni(dnis)
        if any(not carteras_por_dni.get(dni) for dni in dnis):
            _denegar(usuario, "cartera_no_determinable")

        carteras_cliente = set().union(*carteras_por_dni.values())
        ajenas = carteras_cliente - permitidas
        if ajenas:
            _denegar(usuario, "cartera_no_asignada", sorted(ajenas))

        if contexto is not None:
            contexto["otras_carteras"] = sorted(carteras_cliente - asignadas)

        return carteras_por_dni

    return verificar


@router.get("/buscar")
def buscar(valor: str = Query(None), usuario: Dict = Depends(requiere_clave_definitiva)):
    exigir_vista(usuario, "clientes")
    # Parametros como idcartera, idcarteras o perfil del navegador no se leen:
    # el acceso se decide con la sesion del servidor.
    # El permiso individual permite al monitor usar la vista, con la misma
    # verificación de cartera por cliente que se aplica a cualquier otro perfil.
    cartera_compartamos = bool(autorizacion.carteras_usuario(usuario) & autorizacion.CARTERAS_COMPARTAMOS)
    if not (autorizacion.puede_consultar_compartamos(usuario) or cartera_compartamos):
        raise autorizacion.prohibido(autorizacion.MENSAJE_SIN_ACCESO_MODULO)

    try:
        contexto = {}
        resultado = buscar_cliente(valor=valor, verificar_acceso=_verificador_de_acceso(usuario, contexto))
        if resultado.get("encontrado") and contexto.get("otras_carteras"):
            resultado["otras_carteras_compartamos"] = [
                {"id": cartera, "nombre": COMPARTAMOS_CARTERAS[cartera]}
                for cartera in contexto["otras_carteras"]
            ]
        return resultado
    except HTTPException:
        raise
    except Exception:
        # Incluye un fallo al consultar la cartera en SISCOB: no se devuelve nada.
        logger.exception("Error en busqueda de cliente usuario=%s", usuario.get("dni"))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=MENSAJE_ERROR_TECNICO)
