from app.core.database import get_connection
from app.services.cliente_crm_service import construir_respuesta_crm, resolver_tipo_resultado

def buscar_cliente(valor=None):

    # 🚫 seguridad básica
    if not valor:
        return {
            "encontrado": False,
            "error": "Debe enviar un valor de búsqueda"
        }

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
        END DESC
    """

    params.extend([valor, valor])

    try:
        cursor.execute(query, params)
        rows = cursor.fetchall()

        if not rows:
            return {"encontrado": False}

        columns = [col[0] for col in cursor.description]
        data = [dict(zip(columns, row)) for row in rows]
        data = resolver_filas_entidad(cursor, data, str(valor).strip())

        return construir_respuesta_crm(data, str(valor).strip())
    finally:
        cursor.close()
        conn.close()


def resolver_filas_entidad(cursor, coincidencias, valor):
    """Amplia la coincidencia inicial a la entidad completa sin mezclar resultados."""
    if resolver_tipo_resultado(coincidencias, valor) == "GRUPO":
        cursor.execute("""
            SELECT *
            FROM VW_CLIENTE_CRM_SAC WITH(NOLOCK)
            WHERE CodigoGrupo = ? OR CodCreGrupal = ?
            ORDER BY DiasAtraso DESC, Deuda_Total DESC
        """, [valor, valor])
    else:
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
