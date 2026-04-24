from sqlalchemy import text
from app.core.db_siscob import engine_siscob


def validar_usuario(dni: str):

    try:
        query = text("""
            SELECT TOP 1
                G.DNI,
                CONCAT(U.USUARIO,' - ',U.Nombres,' ',U.Apellidos) AS AGENTE
            FROM SISCOB.DBO.GESTION G WITH(NOLOCK)
            LEFT JOIN SISCOB.DBO.USUARIO U WITH(NOLOCK)
                ON U.IDUSUARIO = G.IDUSUARIO
            WHERE LEFT(U.USUARIO, 8) = :dni
        """)

        with engine_siscob.connect() as conn:
            r = conn.execute(query, {"dni": dni}).fetchone()

            if r:
                return {
                    "dni": r.DNI,
                    "agente": r.AGENTE
                }

    except Exception as e:
        print(f"Error validando usuario: {e}")

    return None