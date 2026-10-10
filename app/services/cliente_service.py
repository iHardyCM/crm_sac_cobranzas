import logging
from time import perf_counter

from app.core.database import get_connection
from app.services.cliente_crm_service import (
    campo,
    construir_respuesta_crm,
    identificador,
    identificador_grupo_valido,
    resolver_tipo_resultado,
)

logger = logging.getLogger(__name__)

def buscar_cliente(valor=None, verificar_acceso=None):
    """verificar_acceso(filas): valida la entidad antes de consultar sus datos.

    Puede devolver las carteras ya verificadas para reutilizarlas al armar
    la respuesta. Sin verificador, el comportamiento es el de siempre.
    """

    # 🚫 seguridad básica
    if not valor:
        return {
            "encontrado": False,
            "error": "Debe enviar un valor de búsqueda"
        }

    inicio = perf_counter()
    conn = get_connection()
    cursor = conn.cursor()

    query = """
        SELECT *
        FROM VW_CLIENTE_CRM_SAC WITH (NOLOCK)
        WHERE 
            DNI = ?
            OR codcliente = ?
            OR CodOperacion= ?
            OR CodigoGrupo = ?
            OR CodCreGrupal = ?
    """

    params = [valor, valor, valor, valor, valor]

    # 🔥 ORDEN INTELIGENTE (basado en coincidencia real)
    query += """
    ORDER BY 
        CASE 
            WHEN CodigoGrupo = ? OR CodCreGrupal = ? THEN DiasAtraso
            ELSE Deuda_Total
        END DESC,
        Deuda_Total DESC
    """

    params.extend([valor, valor])

    try:
        cursor.execute(query, params)
        rows = cursor.fetchall()
        fin_vista = perf_counter()

        if not rows:
            if fin_vista - inicio >= 2:
                logger.warning("Radar búsqueda lenta sin resultados vista_ms=%.0f total_ms=%.0f",
                               (fin_vista - inicio) * 1000, (fin_vista - inicio) * 1000)
            return {"encontrado": False}

        columns = [col[0] for col in cursor.description]
        data = [dict(zip(columns, row)) for row in rows]
        data = resolver_filas_entidad(cursor, data, str(valor).strip())
        fin_entidad = perf_counter()

        carteras_por_dni = verificar_acceso(data) if verificar_acceso is not None else None
        fin_acceso = perf_counter()

        resultado = construir_respuesta_crm(data, str(valor).strip(), carteras_por_dni=carteras_por_dni)
        fin_detalle = perf_counter()
        if fin_detalle - inicio >= 2:
            logger.warning(
                "Radar búsqueda lenta tipo=%s filas=%d vista_ms=%.0f entidad_ms=%.0f "
                "acceso_ms=%.0f detalle_ms=%.0f total_ms=%.0f",
                resultado.get("tipo_resultado"), len(data),
                (fin_vista - inicio) * 1000, (fin_entidad - fin_vista) * 1000,
                (fin_acceso - fin_entidad) * 1000, (fin_detalle - fin_acceso) * 1000,
                (fin_detalle - inicio) * 1000,
            )
        return resultado
    finally:
        cursor.close()
        conn.close()


def resolver_filas_entidad(cursor, coincidencias, valor):
    """Amplia la coincidencia inicial a la entidad completa sin mezclar resultados."""
    if resolver_tipo_resultado(coincidencias, valor) == "GRUPO":
        # La primera consulta ya trae todos los integrantes del grupo y los
        # ordena por mora/deuda. Evita leer la misma vista una segunda vez.
        buscado = identificador(valor)
        return [fila for fila in coincidencias if any(
            identificador_grupo_valido(campo(fila, columna)) and
            identificador(campo(fila, columna)) == buscado
            for columna in ("CodigoGrupo", "CodCreGrupal")
        )]

    principal = coincidencias[0]
    dni = principal.get("DNI")
    codigo_cliente = principal.get("codcliente")
    cursor.execute("""
        SELECT *
        FROM VW_CLIENTE_CRM_SAC WITH(NOLOCK)
        WHERE DNI = ? OR codcliente = ?
        ORDER BY Deuda_Total DESC, DiasAtraso DESC
    """, [dni, codigo_cliente])

    rows = cursor.fetchall()
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in rows]
