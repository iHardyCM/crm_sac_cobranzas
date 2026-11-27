"""Responsables actuales y cambios auditados por tipo, cartera y cliente."""

from sqlalchemy import text

from app.core.db_siscob import engine_siscob

TIPO_RESPUESTA_SMS = "RESPUESTA_SMS"


def listar_agentes(carteras: set[int] | None) -> list[dict]:
    """Solo gestores activos con acceso vigente al CRM."""
    params = {}
    filtro = ""
    if carteras is not None:
        if not carteras:
            return []
        params = {f"c{i}": c for i, c in enumerate(sorted(carteras))}
        filtro = "AND C.IdCartera IN (" + ", ".join(f":c{i}" for i in range(len(params))) + ")"
    with engine_siscob.connect() as conn:
        filas = conn.execute(text(f"""
            SELECT LTRIM(RTRIM(U.Usuario)) AS usuario, C.IdCartera AS idcartera,
                   LTRIM(RTRIM(CONCAT(ISNULL(U.Nombres,''), ' ', ISNULL(U.Apellidos,'')))) AS nombre
            FROM SISCOB.dbo.Usuario U
            JOIN CobAuto.dbo.CRM_USUARIO_ACCESO A
              ON A.USUARIO COLLATE DATABASE_DEFAULT = U.Usuario COLLATE DATABASE_DEFAULT
            LEFT JOIN CobAuto.dbo.CRM_USUARIO_VISTA V
              ON V.USUARIO COLLATE DATABASE_DEFAULT = U.Usuario COLLATE DATABASE_DEFAULT
             AND V.VISTA = 'respuestas_mowa'
            CROSS APPLY (
                SELECT U.IdCartera AS IdCartera WHERE U.IdCartera IS NOT NULL
                UNION
                SELECT SC.idcartera FROM CobAuto.dbo.CRM_SUPERVISOR_CARTERA SC
                WHERE SC.usuario COLLATE DATABASE_DEFAULT = U.Usuario COLLATE DATABASE_DEFAULT
                  AND SC.activo = 1
            ) C
            WHERE U.TipoUsuario = 'GESTOR' AND U.Estado = 'A'
              AND A.FLG_ACTIVO = 1 AND A.PASSWORD_HASH IS NOT NULL
              AND ISNULL(V.PERMITIDO, 1) = 1 {filtro}
            ORDER BY C.IdCartera, U.Apellidos, U.Nombres
        """), params).mappings().all()
    return [dict(f) for f in filas]


def listar(tipo: str, carteras: set[int] | None = None,
           agente: str | None = None) -> list[dict]:
    params = {"tipo": tipo}
    filtro = ""
    if carteras is not None:
        if not carteras:
            return []
        params.update({f"c{i}": c for i, c in enumerate(sorted(carteras))})
        filtro += " AND A.IdCartera IN (" + ", ".join(f":c{i}" for i in range(len(carteras))) + ")"
    if agente is not None:
        params["agente"] = agente.strip()
        filtro += " AND A.AgenteUsuario = :agente"
    with engine_siscob.connect() as conn:
        filas = conn.execute(text(f"""
            SELECT A.IdCartera AS idcartera, A.IdCliente AS idcliente,
                   A.AgenteUsuario AS agente_usuario,
                   LTRIM(RTRIM(CONCAT(ISNULL(U.Nombres,''), ' ', ISNULL(U.Apellidos,'')))) AS agente_nombre,
                   A.AsignadoPor AS asignado_por, A.FechaAsignacion AS fecha_asignacion
            FROM CobAuto.dbo.CRM_ASIGNACION_CLIENTE A
            LEFT JOIN SISCOB.dbo.Usuario U ON U.Usuario COLLATE DATABASE_DEFAULT = A.AgenteUsuario COLLATE DATABASE_DEFAULT
            WHERE A.Tipo = :tipo {filtro}
        """), params).mappings().all()
    return [{**dict(f), "fecha_asignacion": f["fecha_asignacion"].isoformat(timespec="seconds")}
            for f in filas]


def pertenece(tipo: str, idcartera: int, idcliente: int, agente: str) -> bool:
    with engine_siscob.connect() as conn:
        valor = conn.execute(text("""
            SELECT 1 FROM CobAuto.dbo.CRM_ASIGNACION_CLIENTE
            WHERE Tipo=:tipo AND IdCartera=:cartera AND IdCliente=:cliente
              AND AgenteUsuario=:agente
        """), {"tipo": tipo, "cartera": idcartera, "cliente": idcliente,
               "agente": agente.strip()}).scalar()
    return bool(valor)


def asignar_lote(tipo: str, clientes: list[tuple[int, int]], agente: str, actor: str) -> list[dict]:
    """Guarda todo el lote o revierte todo; conserva un evento por cambio."""
    agente, actor = agente.strip(), actor.strip()
    claves = sorted(set(clientes))
    if (not agente or not actor or not claves or len(claves) != len(clientes)
            or any(cartera <= 0 or cliente <= 0 for cartera, cliente in claves)):
        raise ValueError("Selecciona un cliente y un agente válidos.")
    resultados = []
    with engine_siscob.begin() as conn:
        for idcartera in sorted({cartera for cartera, _ in claves}):
            habilitado = conn.execute(text("""
                SELECT 1 FROM SISCOB.dbo.Usuario U
                JOIN CobAuto.dbo.CRM_USUARIO_ACCESO A
                  ON A.USUARIO COLLATE DATABASE_DEFAULT = U.Usuario COLLATE DATABASE_DEFAULT
                LEFT JOIN CobAuto.dbo.CRM_USUARIO_VISTA V
                  ON V.USUARIO COLLATE DATABASE_DEFAULT = U.Usuario COLLATE DATABASE_DEFAULT
                 AND V.VISTA = 'respuestas_mowa'
                WHERE U.Usuario=:agente AND U.TipoUsuario='GESTOR'
                  AND U.Estado='A' AND A.FLG_ACTIVO=1 AND A.PASSWORD_HASH IS NOT NULL
                  AND ISNULL(V.PERMITIDO, 1) = 1
                  AND (U.IdCartera=:cartera OR EXISTS (
                      SELECT 1 FROM CobAuto.dbo.CRM_SUPERVISOR_CARTERA SC
                      WHERE SC.usuario COLLATE DATABASE_DEFAULT = U.Usuario COLLATE DATABASE_DEFAULT
                        AND SC.idcartera=:cartera AND SC.activo=1))
            """), {"agente": agente, "cartera": idcartera}).scalar()
            if not habilitado:
                raise ValueError(f"El agente no tiene acceso activo al CRM y a la cartera {idcartera}.")
        for idcartera, idcliente in claves:
            recurso = f"CRM_ASIGNACION_CLIENTE:{tipo}:{idcartera}:{idcliente}"
            bloqueo = conn.execute(text("""
                SET NOCOUNT ON;
                DECLARE @r int;
                EXEC @r = sp_getapplock @Resource=:recurso, @LockMode='Exclusive',
                    @LockOwner='Transaction', @LockTimeout=5000;
                SELECT @r
            """), {"recurso": recurso}).scalar()
            if bloqueo is None or bloqueo < 0:
                raise RuntimeError("No se pudo reservar la asignación. Intenta nuevamente.")
            params = {"tipo": tipo, "cartera": idcartera, "cliente": idcliente,
                      "agente": agente, "actor": actor}
            anterior = conn.execute(text("""
                SELECT AgenteUsuario FROM CobAuto.dbo.CRM_ASIGNACION_CLIENTE WITH (UPDLOCK, HOLDLOCK)
                WHERE Tipo=:tipo AND IdCartera=:cartera AND IdCliente=:cliente
            """), params).scalar()
            if anterior != agente:
                if anterior:
                    conn.execute(text("""
                        UPDATE CobAuto.dbo.CRM_ASIGNACION_CLIENTE
                        SET AgenteUsuario=:agente, AsignadoPor=:actor, FechaAsignacion=SYSDATETIME()
                        WHERE Tipo=:tipo AND IdCartera=:cartera AND IdCliente=:cliente
                    """), params)
                else:
                    conn.execute(text("""
                        INSERT INTO CobAuto.dbo.CRM_ASIGNACION_CLIENTE
                            (Tipo,IdCartera,IdCliente,AgenteUsuario,AsignadoPor)
                        VALUES (:tipo,:cartera,:cliente,:agente,:actor)
                    """), params)
                conn.execute(text("""
                    INSERT INTO CobAuto.dbo.CRM_ASIGNACION_CLIENTE_EVENTO
                        (Tipo,IdCartera,IdCliente,AgenteAnterior,AgenteNuevo,UsuarioCambio)
                    VALUES (:tipo,:cartera,:cliente,:anterior,:agente,:actor)
                """), {**params, "anterior": anterior})
            resultados.append({"tipo": tipo, "idcartera": idcartera, "idcliente": idcliente,
                               "agente_usuario": agente, "agente_anterior": anterior,
                               "cambio": anterior != agente})
    return resultados


def asignar(tipo: str, idcartera: int, idcliente: int, agente: str, actor: str) -> dict:
    return asignar_lote(tipo, [(idcartera, idcliente)], agente, actor)[0]
