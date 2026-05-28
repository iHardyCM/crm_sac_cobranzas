from typing import Dict, List

from sqlalchemy import text

from app.core.db_siscob import engine_siscob


CARTERAS = {
    112: "MIBANCO 1",
    143: "MIBANCO 2",
    135: "MIBANCO VIGENTE",
    124: "COMPARTAMOS CASTIGO INDIVIDUAL",
    144: "COMPARTAMOS CASTIGO GRUPAL",
    126: "COMPARTAMOS VIGENTE INDIVIDUAL",
    128: "COMPARTAMOS VIGENTE CCM",
    133: "COMPARTAMOS VIGENTE GRUPAL / CSM",
    132: "FINANCIERA OH",
    117: "INTERBANK",
    137: "INTERBANK CEDIDA",
}


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


def listar_supervisores() -> List[Dict]:
    query = text("""
        SELECT
            LTRIM(RTRIM(USUARIO)) AS usuario,
            CONCAT(LTRIM(RTRIM(USUARIO)), ' - ', ISNULL(Nombres, ''), ' ', ISNULL(Apellidos, '')) AS supervisor,
            IDCARTERA AS idcartera_base
        FROM SISCOB.dbo.USUARIO WITH(NOLOCK)
        WHERE UPPER(LTRIM(RTRIM(ISNULL(TipoUsuario, '')))) = 'SUPERVISOR'
        ORDER BY supervisor
    """)
    with engine_siscob.connect() as conn:
        rows = conn.execute(query).mappings().all()
    return [dict(row) for row in rows]


def listar_carteras() -> List[Dict]:
    query = text("""
        SELECT DISTINCT IDCARTERA AS idcartera
        FROM SISCOB.dbo.USUARIO WITH(NOLOCK)
        WHERE IDCARTERA IS NOT NULL
        ORDER BY IDCARTERA
    """)
    carteras = {}
    with engine_siscob.connect() as conn:
        rows = conn.execute(query).mappings().all()

    for row in rows:
        idcartera = int(row["idcartera"])
        carteras[idcartera] = CARTERAS.get(idcartera, f"Cartera {idcartera}")

    for idcartera, cartera in CARTERAS.items():
        carteras.setdefault(idcartera, cartera)

    return [
        {"idcartera": idcartera, "cartera": cartera}
        for idcartera, cartera in sorted(carteras.items(), key=lambda item: item[1])
    ]


def listar_asignaciones(usuario: str | None = None) -> List[Dict]:
    where = "WHERE A.activo = 1"
    params = {}
    if usuario:
        where += " AND LTRIM(RTRIM(A.usuario)) = LTRIM(RTRIM(:usuario))"
        params["usuario"] = usuario

    query = text(f"""
        SELECT
            A.id,
            LTRIM(RTRIM(A.usuario)) AS usuario,
            A.idcartera,
            A.activo,
            A.usuario_actualizacion,
            A.fecha_actualizacion,
            CONCAT(LTRIM(RTRIM(U.USUARIO)), ' - ', ISNULL(U.Nombres, ''), ' ', ISNULL(U.Apellidos, '')) AS supervisor
        FROM CobAuto.dbo.CRM_SUPERVISOR_CARTERA A WITH(NOLOCK)
        LEFT JOIN SISCOB.dbo.USUARIO U WITH(NOLOCK)
            ON LTRIM(RTRIM(U.USUARIO)) = LTRIM(RTRIM(A.usuario))
        {where}
        ORDER BY A.usuario, A.idcartera
    """)

    with engine_siscob.begin() as conn:
        asegurar_tabla_supervisor_cartera(conn)
        rows = conn.execute(query, params).mappings().all()

    return [
        {
            **dict(row),
            "cartera": CARTERAS.get(int(row["idcartera"]), f"Cartera {row['idcartera']}"),
            "fecha_actualizacion": row["fecha_actualizacion"].isoformat() if row["fecha_actualizacion"] else None,
        }
        for row in rows
    ]


def guardar_asignaciones(usuario: str, idcarteras: List[int], usuario_actualizacion: str = "") -> Dict:
    usuario = (usuario or "").strip()
    if not usuario:
        raise ValueError("Debe seleccionar un supervisor.")

    idcarteras_limpias = sorted({int(x) for x in idcarteras if str(x).strip()})

    with engine_siscob.begin() as conn:
        asegurar_tabla_supervisor_cartera(conn)

        conn.execute(text("""
            UPDATE CobAuto.dbo.CRM_SUPERVISOR_CARTERA
            SET activo = 0,
                usuario_actualizacion = :usuario_actualizacion,
                fecha_actualizacion = GETDATE()
            WHERE LTRIM(RTRIM(usuario)) = LTRIM(RTRIM(:usuario))
              AND activo = 1
        """), {
            "usuario": usuario,
            "usuario_actualizacion": usuario_actualizacion or None,
        })

        for idcartera in idcarteras_limpias:
            conn.execute(text("""
                INSERT INTO CobAuto.dbo.CRM_SUPERVISOR_CARTERA
                    (usuario, idcartera, activo, usuario_actualizacion, fecha_actualizacion)
                VALUES
                    (:usuario, :idcartera, 1, :usuario_actualizacion, GETDATE())
            """), {
                "usuario": usuario,
                "idcartera": idcartera,
                "usuario_actualizacion": usuario_actualizacion or None,
            })

    return {
        "ok": True,
        "usuario": usuario,
        "idcarteras": idcarteras_limpias,
        "mensaje": "Asignaciones actualizadas correctamente.",
    }
