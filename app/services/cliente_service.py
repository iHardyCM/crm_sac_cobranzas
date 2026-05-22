from app.core.database import get_connection

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

    cursor.execute(query, params)
    rows = cursor.fetchall()

    if not rows:
        return {"encontrado": False}

    columns = [col[0] for col in cursor.description]
    data = [dict(zip(columns, row)) for row in rows]

    return {
        "encontrado": True,
        "total": len(data),
        "data": data
    }