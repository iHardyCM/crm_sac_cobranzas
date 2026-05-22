from sqlalchemy import text
from app.core.db_siscob import engine_siscob


def validar_usuario(dni: str):
    try:
        query = text("""
            SELECT TOP 1
                U.USUARIO,
                U.Nombres,
                U.Apellidos,
                U.TipoUsuario,
                U.IDCARTERA
            FROM SISCOB.DBO.USUARIO U WITH(NOLOCK)
            WHERE LTRIM(RTRIM(U.USUARIO)) = LTRIM(RTRIM(:dni))
        """)

        with engine_siscob.connect() as conn:
            r = conn.execute(query, {"dni": dni}).fetchone()

            if r:
                return {
                    "dni": r.USUARIO,
                    "agente": f"{r.USUARIO} - {r.Nombres} {r.Apellidos}",
                    "tipo": r.TipoUsuario,
                    "idcartera": r.IDCARTERA
                }

    except Exception as e:
        print(f"Error validando usuario: {e}")

    return None
