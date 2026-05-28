from sqlalchemy import text
from app.core.db_siscob import engine_siscob


def obtener_carteras_usuario(dni, idcartera):
    carteras = []

    if idcartera is not None:
        carteras.append(int(idcartera))

    carteras.extend(obtener_carteras_adicionales(dni))

    return sorted(set(carteras))


def asegurar_tabla_supervisor_cartera(conn):
    conn.execute(text("""
        IF OBJECT_ID('CobAuto.dbo.CRM_SUPERVISOR_CARTERA', 'U') IS NULL
        BEGIN
            CREATE TABLE CobAuto.dbo.CRM_SUPERVISOR_CARTERA (
                id INT IDENTITY(1,1) PRIMARY KEY,
                usuario VARCHAR(50) NOT NULL,
                idcartera INT NOT NULL,
                activo BIT NOT NULL DEFAULT 1,
                usuario_actualizacion VARCHAR(50) NULL,
                fecha_actualizacion DATETIME NOT NULL DEFAULT GETDATE()
            );

            CREATE INDEX IX_CRM_SUPERVISOR_CARTERA_USUARIO
            ON CobAuto.dbo.CRM_SUPERVISOR_CARTERA(usuario, activo);
        END
    """))


def obtener_carteras_adicionales(dni):
    try:
        query = text("""
            SELECT idcartera
            FROM CobAuto.dbo.CRM_SUPERVISOR_CARTERA WITH(NOLOCK)
            WHERE LTRIM(RTRIM(usuario)) = LTRIM(RTRIM(:dni))
              AND activo = 1
        """)

        with engine_siscob.begin() as conn:
            asegurar_tabla_supervisor_cartera(conn)
            rows = conn.execute(query, {"dni": str(dni).strip()}).fetchall()

        return [int(row.idcartera) for row in rows if row.idcartera is not None]
    except Exception as exc:
        print(f"Error obteniendo carteras adicionales: {exc}")
        return []


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
                idcarteras = obtener_carteras_usuario(r.USUARIO, r.IDCARTERA)

                return {
                    "dni": r.USUARIO,
                    "agente": f"{r.USUARIO} - {r.Nombres} {r.Apellidos}",
                    "tipo": r.TipoUsuario,
                    "idcartera": r.IDCARTERA,
                    "idcarteras": idcarteras
                }

    except Exception as e:
        print(f"Error validando usuario: {e}")

    return None
