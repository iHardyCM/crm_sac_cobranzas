from calendar import monthrange
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

from sqlalchemy import text

from app.core.db_siscob import engine_siscob
from app.services.admin_supervisores_service import CARTERAS, listar_carteras


def asegurar_tabla_meta_agente(conn):
    conn.execute(text("""
        IF OBJECT_ID('CobAuto.dbo.CRM_META_AGENTE', 'U') IS NULL
        BEGIN
            CREATE TABLE CobAuto.dbo.CRM_META_AGENTE (
                id INT IDENTITY(1,1) PRIMARY KEY,
                codmes CHAR(6) NOT NULL,
                idcartera INT NOT NULL,
                usuario VARCHAR(50) NOT NULL,
                meta_mensual DECIMAL(18,2) NOT NULL DEFAULT 0,
                activo BIT NOT NULL DEFAULT 1,
                usuario_actualizacion VARCHAR(50) NULL,
                fecha_actualizacion DATETIME NOT NULL DEFAULT GETDATE()
            );

            CREATE INDEX IX_CRM_META_AGENTE_BUSQUEDA
            ON CobAuto.dbo.CRM_META_AGENTE(codmes, idcartera, usuario, activo);
        END
    """))


def normalizar_codmes(codmes: Optional[str]) -> str:
    valor = "".join(ch for ch in str(codmes or "") if ch.isdigit())
    if len(valor) == 6:
        return valor
    hoy = date.today()
    return f"{hoy.year}{hoy.month:02d}"


def listar_agentes(idcartera: Optional[int] = None) -> List[Dict]:
    filtros = [
        "UPPER(LTRIM(RTRIM(ISNULL(TipoUsuario, '')))) = 'GESTOR'",
        "UPPER(LTRIM(RTRIM(ISNULL(Estado, '')))) = 'A'",
    ]
    params = {}

    if idcartera:
        filtros.append("IDCARTERA = :idcartera")
        params["idcartera"] = int(idcartera)

    query = text(f"""
        SELECT
            LTRIM(RTRIM(USUARIO)) AS usuario,
            CONCAT(LTRIM(RTRIM(USUARIO)), ' - ', ISNULL(Nombres, ''), ' ', ISNULL(Apellidos, '')) AS agente,
            IDCARTERA AS idcartera
        FROM SISCOB.dbo.USUARIO WITH(NOLOCK)
        WHERE {' AND '.join(filtros)}
        ORDER BY IDCARTERA, agente
    """)

    with engine_siscob.connect() as conn:
        rows = conn.execute(query, params).mappings().all()

    return [
        {
            **dict(row),
            "cartera": CARTERAS.get(int(row["idcartera"]), f"Cartera {row['idcartera']}") if row["idcartera"] else "-",
        }
        for row in rows
    ]


def listar_metas_agentes(codmes: Optional[str] = None, idcartera: Optional[int] = None) -> List[Dict]:
    codmes_limpio = normalizar_codmes(codmes)
    filtros = ["M.codmes = :codmes", "M.activo = 1"]
    params = {"codmes": codmes_limpio}

    if idcartera:
        filtros.append("M.idcartera = :idcartera")
        params["idcartera"] = int(idcartera)

    query = text(f"""
        SELECT
            M.id,
            M.codmes,
            M.idcartera,
            M.usuario,
            M.meta_mensual,
            M.usuario_actualizacion,
            M.fecha_actualizacion,
            CONCAT(LTRIM(RTRIM(U.USUARIO)), ' - ', ISNULL(U.Nombres, ''), ' ', ISNULL(U.Apellidos, '')) AS agente
        FROM CobAuto.dbo.CRM_META_AGENTE M WITH(NOLOCK)
        LEFT JOIN SISCOB.dbo.USUARIO U WITH(NOLOCK)
            ON LTRIM(RTRIM(U.USUARIO)) = LTRIM(RTRIM(M.usuario))
        WHERE {' AND '.join(filtros)}
          AND U.IDCARTERA = M.idcartera
          AND UPPER(LTRIM(RTRIM(ISNULL(U.Estado, '')))) = 'A'
        ORDER BY M.idcartera, agente
    """)

    with engine_siscob.begin() as conn:
        asegurar_tabla_meta_agente(conn)
        rows = conn.execute(query, params).mappings().all()

    return [
        {
            **dict(row),
            "meta_mensual": float(row["meta_mensual"] or 0),
            "cartera": CARTERAS.get(int(row["idcartera"]), f"Cartera {row['idcartera']}"),
            "fecha_actualizacion": row["fecha_actualizacion"].isoformat() if row["fecha_actualizacion"] else None,
        }
        for row in rows
    ]


def guardar_meta_agente(
    codmes: str,
    idcartera: int,
    usuario: str,
    meta_mensual: float,
    usuario_actualizacion: str = "",
) -> Dict:
    codmes_limpio = normalizar_codmes(codmes)
    usuario_limpio = str(usuario or "").strip()
    meta = float(meta_mensual or 0)

    if not usuario_limpio:
        raise ValueError("Debe seleccionar un agente.")
    if int(idcartera or 0) <= 0:
        raise ValueError("Debe seleccionar una cartera.")
    if meta < 0:
        raise ValueError("La meta mensual no puede ser negativa.")

    with engine_siscob.begin() as conn:
        asegurar_tabla_meta_agente(conn)
        agente_activo = conn.execute(text("""
            SELECT TOP 1 1
            FROM SISCOB.dbo.USUARIO WITH(NOLOCK)
            WHERE LTRIM(RTRIM(USUARIO)) = LTRIM(RTRIM(:usuario))
              AND IDCARTERA = :idcartera
              AND UPPER(LTRIM(RTRIM(ISNULL(TipoUsuario, '')))) = 'GESTOR'
              AND UPPER(LTRIM(RTRIM(ISNULL(Estado, '')))) = 'A'
        """), {
            "usuario": usuario_limpio,
            "idcartera": int(idcartera),
        }).scalar()

        if not agente_activo:
            raise ValueError("El agente no esta activo o no pertenece a la cartera seleccionada.")

        conn.execute(text("""
            UPDATE CobAuto.dbo.CRM_META_AGENTE
            SET activo = 0,
                usuario_actualizacion = :usuario_actualizacion,
                fecha_actualizacion = GETDATE()
            WHERE codmes = :codmes
              AND idcartera = :idcartera
              AND LTRIM(RTRIM(usuario)) = LTRIM(RTRIM(:usuario))
              AND activo = 1
        """), {
            "codmes": codmes_limpio,
            "idcartera": int(idcartera),
            "usuario": usuario_limpio,
            "usuario_actualizacion": usuario_actualizacion or None,
        })

        conn.execute(text("""
            INSERT INTO CobAuto.dbo.CRM_META_AGENTE
                (codmes, idcartera, usuario, meta_mensual, activo, usuario_actualizacion, fecha_actualizacion)
            VALUES
                (:codmes, :idcartera, :usuario, :meta_mensual, 1, :usuario_actualizacion, GETDATE())
        """), {
            "codmes": codmes_limpio,
            "idcartera": int(idcartera),
            "usuario": usuario_limpio,
            "meta_mensual": meta,
            "usuario_actualizacion": usuario_actualizacion or None,
        })

    return {
        "ok": True,
        "codmes": codmes_limpio,
        "idcartera": int(idcartera),
        "usuario": usuario_limpio,
        "meta_mensual": round(meta, 2),
    }


def guardar_meta_cartera(
    codmes: str,
    idcartera: int,
    meta_mensual: float,
    usuario_actualizacion: str = "",
) -> Dict:
    codmes_limpio = normalizar_codmes(codmes)
    idcartera_limpia = int(idcartera or 0)
    meta = float(meta_mensual or 0)

    if idcartera_limpia <= 0:
        raise ValueError("Debe seleccionar una cartera.")
    if meta < 0:
        raise ValueError("La meta mensual no puede ser negativa.")

    with engine_siscob.begin() as conn:
        asegurar_tabla_meta_agente(conn)

        agentes = conn.execute(text("""
            SELECT LTRIM(RTRIM(USUARIO)) AS usuario
            FROM SISCOB.dbo.USUARIO WITH(NOLOCK)
            WHERE IDCARTERA = :idcartera
              AND UPPER(LTRIM(RTRIM(ISNULL(TipoUsuario, '')))) = 'GESTOR'
              AND UPPER(LTRIM(RTRIM(ISNULL(Estado, '')))) = 'A'
        """), {"idcartera": idcartera_limpia}).mappings().all()

        usuarios = [row["usuario"] for row in agentes if row["usuario"]]
        if not usuarios:
            raise ValueError("No hay agentes activos para la cartera seleccionada.")

        conn.execute(text("""
            UPDATE M
            SET activo = 0,
                usuario_actualizacion = :usuario_actualizacion,
                fecha_actualizacion = GETDATE()
            FROM CobAuto.dbo.CRM_META_AGENTE M
            INNER JOIN SISCOB.dbo.USUARIO U
                ON LTRIM(RTRIM(U.USUARIO)) = LTRIM(RTRIM(M.usuario))
               AND U.IDCARTERA = M.idcartera
            WHERE M.codmes = :codmes
              AND M.idcartera = :idcartera
              AND M.activo = 1
              AND UPPER(LTRIM(RTRIM(ISNULL(U.TipoUsuario, '')))) = 'GESTOR'
              AND UPPER(LTRIM(RTRIM(ISNULL(U.Estado, '')))) = 'A'
        """), {
            "codmes": codmes_limpio,
            "idcartera": idcartera_limpia,
            "usuario_actualizacion": usuario_actualizacion or None,
        })

        conn.execute(text("""
            INSERT INTO CobAuto.dbo.CRM_META_AGENTE
                (codmes, idcartera, usuario, meta_mensual, activo, usuario_actualizacion, fecha_actualizacion)
            VALUES
                (:codmes, :idcartera, :usuario, :meta_mensual, 1, :usuario_actualizacion, GETDATE())
        """), [
            {
                "codmes": codmes_limpio,
                "idcartera": idcartera_limpia,
                "usuario": usuario,
                "meta_mensual": meta,
                "usuario_actualizacion": usuario_actualizacion or None,
            }
            for usuario in usuarios
        ])

    return {
        "ok": True,
        "codmes": codmes_limpio,
        "idcartera": idcartera_limpia,
        "meta_mensual": round(meta, 2),
        "agentes_actualizados": len(usuarios),
    }


def obtener_resumen_meta_agente(usuario: str, codmes: Optional[str] = None) -> Dict:
    codmes_limpio = normalizar_codmes(codmes)
    usuario_limpio = str(usuario or "").strip()
    inicio = datetime.strptime(codmes_limpio + "01", "%Y%m%d").date()
    if inicio.month == 12:
        fin = date(inicio.year + 1, 1, 1)
    else:
        fin = date(inicio.year, inicio.month + 1, 1)

    query = text("""
        SELECT TOP 1
            U.IDCARTERA AS idcartera,
            ISNULL(M.meta_mensual, 0) AS meta_mensual
        FROM SISCOB.dbo.USUARIO U WITH(NOLOCK)
        LEFT JOIN CobAuto.dbo.CRM_META_AGENTE M WITH(NOLOCK)
            ON M.codmes = :codmes
           AND M.activo = 1
           AND M.idcartera = U.IDCARTERA
           AND LTRIM(RTRIM(M.usuario)) = LTRIM(RTRIM(U.USUARIO))
        WHERE LTRIM(RTRIM(U.USUARIO)) = LTRIM(RTRIM(:usuario))
    """)

    query_compromisos = text("""
        SELECT
            SUM(CASE WHEN C.PAGADO = 'SI' OR ISNULL(C.MONTOPAGADO, 0) > 0
                THEN ISNULL(C.MONTOPAGADO, 0) ELSE 0 END) AS monto_cumplido,
            SUM(CASE WHEN (C.PAGADO <> 'SI' OR C.PAGADO IS NULL)
                      AND CAST(C.FECHACOMPROMISO AS DATE) >= CAST(GETDATE() AS DATE)
                THEN ISNULL(C.MONTO, 0) - ISNULL(C.MONTOPAGADO, 0) ELSE 0 END) AS monto_vigente,
            SUM(CASE WHEN (C.PAGADO <> 'SI' OR C.PAGADO IS NULL)
                      AND CAST(C.FECHACOMPROMISO AS DATE) < CAST(GETDATE() AS DATE)
                THEN ISNULL(C.MONTO, 0) - ISNULL(C.MONTOPAGADO, 0) ELSE 0 END) AS monto_caido,
            COUNT(CASE WHEN C.PAGADO = 'SI' OR ISNULL(C.MONTOPAGADO, 0) > 0 THEN 1 END) AS pagos_count,
            AVG(CASE WHEN C.PAGADO = 'SI' OR ISNULL(C.MONTOPAGADO, 0) > 0
                THEN NULLIF(ISNULL(C.MONTOPAGADO, 0), 0) END) AS ticket_promedio
        FROM SISCOB.dbo.COMPROMISO C WITH(NOLOCK)
        LEFT JOIN SISCOB.dbo.GESTION G WITH(NOLOCK)
            ON G.IDGESTION = C.IDGESTION
        LEFT JOIN SISCOB.dbo.USUARIO U WITH(NOLOCK)
            ON U.IDUSUARIO = G.IDUSUARIO
        WHERE LTRIM(RTRIM(U.USUARIO)) = LTRIM(RTRIM(:usuario))
          AND C.MONTO > 0
          AND CAST(C.FECHACOMPROMISO AS DATE) >= :inicio
          AND CAST(C.FECHACOMPROMISO AS DATE) < :fin
    """)

    with engine_siscob.begin() as conn:
        asegurar_tabla_meta_agente(conn)
        meta_row = conn.execute(query, {"codmes": codmes_limpio, "usuario": usuario_limpio}).mappings().first()
        resumen_row = conn.execute(query_compromisos, {
            "usuario": usuario_limpio,
            "inicio": inicio,
            "fin": fin,
        }).mappings().first()

    meta_mensual = float((meta_row or {}).get("meta_mensual") or 0)
    monto_cumplido = float((resumen_row or {}).get("monto_cumplido") or 0)
    monto_vigente = float((resumen_row or {}).get("monto_vigente") or 0)
    monto_caido = float((resumen_row or {}).get("monto_caido") or 0)
    ticket_promedio = float((resumen_row or {}).get("ticket_promedio") or 0)
    brecha = max(meta_mensual - monto_cumplido, 0)

    return {
        "codmes": codmes_limpio,
        "usuario": usuario_limpio,
        "idcartera": (meta_row or {}).get("idcartera"),
        "cartera": CARTERAS.get(int((meta_row or {}).get("idcartera") or 0), "-"),
        "meta_mensual": round(meta_mensual, 2),
        "monto_cumplido": round(monto_cumplido, 2),
        "monto_vigente": round(max(monto_vigente, 0), 2),
        "monto_caido": round(max(monto_caido, 0), 2),
        "brecha": round(brecha, 2),
        "cumplimiento_pct": round(monto_cumplido / meta_mensual, 6) if meta_mensual else 0,
        "ticket_promedio": round(ticket_promedio, 2),
        "pagos_count": int((resumen_row or {}).get("pagos_count") or 0),
        "meta_configurada": meta_mensual > 0,
    }


def obtener_ritmo_meta_agente(usuario: str, codmes: Optional[str] = None) -> Dict:
    codmes_limpio = normalizar_codmes(codmes)
    resumen = obtener_resumen_meta_agente(usuario=usuario, codmes=codmes_limpio)
    timing = calcular_timing_mes(codmes_limpio)

    meta = float(resumen.get("meta_mensual") or 0)
    cumplido = float(resumen.get("monto_cumplido") or 0)
    brecha = max(meta - cumplido, 0)
    dias_restantes = float(timing["dias_habiles_restantes"])
    dias_transcurridos = float(timing["dias_habiles_transcurridos"])
    dias_mes = float(timing["dias_habiles_mes"])

    avance_esperado_pct = dividir(dias_transcurridos, dias_mes)
    esperado_a_hoy = meta * avance_esperado_pct
    cumplimiento_pct = dividir(cumplido, meta)
    desvio_monto = cumplido - esperado_a_hoy
    necesario_diario = dividir(brecha, dias_restantes) if brecha > 0 and dias_restantes > 0 else brecha
    promedio_diario_actual = dividir(cumplido, dias_transcurridos)
    proyeccion_cierre = promedio_diario_actual * dias_mes if promedio_diario_actual > 0 else 0
    cumplimiento_proyectado_pct = dividir(proyeccion_cierre, meta)
    tickets_necesarios_dia = dividir(necesario_diario, float(resumen.get("ticket_promedio") or 0))
    estado = calcular_estado_ritmo(cumplimiento_pct, avance_esperado_pct)

    return {
        **resumen,
        "fecha_referencia": timing["fecha_referencia"].isoformat(),
        "dias_habiles_mes": timing["dias_habiles_mes"],
        "dias_habiles_transcurridos": timing["dias_habiles_transcurridos"],
        "dias_habiles_restantes": timing["dias_habiles_restantes"],
        "avance_esperado_pct": round(avance_esperado_pct, 6),
        "esperado_a_hoy": round(esperado_a_hoy, 2),
        "desvio_monto": round(desvio_monto, 2),
        "necesario_diario": round(necesario_diario, 2),
        "promedio_diario_actual": round(promedio_diario_actual, 2),
        "proyeccion_cierre": round(proyeccion_cierre, 2),
        "cumplimiento_proyectado_pct": round(cumplimiento_proyectado_pct, 6),
        "tickets_necesarios_dia": round(tickets_necesarios_dia, 2),
        "estado_ritmo": estado["estado"],
        "estado_titulo": estado["titulo"],
        "estado_detalle": estado["detalle"],
    }


def calcular_timing_mes(codmes: str) -> Dict:
    hoy = date.today()
    year = int(codmes[:4])
    month = int(codmes[4:6])
    inicio = date(year, month, 1)
    fin = date(year, month, monthrange(year, month)[1])
    dias_mes = contar_dias_habiles(inicio, fin)

    if hoy < inicio:
        return {
            "fecha_referencia": inicio,
            "dias_habiles_mes": dias_mes,
            "dias_habiles_transcurridos": 0,
            "dias_habiles_restantes": dias_mes,
        }
    elif hoy > fin:
        return {
            "fecha_referencia": fin,
            "dias_habiles_mes": dias_mes,
            "dias_habiles_transcurridos": dias_mes,
            "dias_habiles_restantes": 0,
        }

    return {
        "fecha_referencia": hoy,
        "dias_habiles_mes": dias_mes,
        "dias_habiles_transcurridos": contar_dias_habiles(inicio, hoy),
        "dias_habiles_restantes": contar_dias_habiles(hoy, fin),
    }


def contar_dias_habiles(inicio: date, fin: date) -> int:
    if fin < inicio:
        return 0

    total = 0
    cursor = inicio
    while cursor <= fin:
        if cursor.weekday() < 5:
            total += 1
        cursor += timedelta(days=1)
    return total


def calcular_estado_ritmo(cumplimiento_pct: float, esperado_pct: float) -> Dict:
    if esperado_pct <= 0:
        return {
            "estado": "sin-ritmo",
            "titulo": "Mes por iniciar",
            "detalle": "Aun no hay ritmo esperado acumulado.",
        }

    ratio = dividir(cumplimiento_pct, esperado_pct)
    if ratio >= 1:
        return {
            "estado": "verde",
            "titulo": "Vas sobre el ritmo",
            "detalle": "Tu avance esta igual o por encima de lo esperado para hoy.",
        }
    if ratio >= 0.9:
        return {
            "estado": "amarillo",
            "titulo": "Estas cerca del ritmo",
            "detalle": "Un empuje corto te vuelve a poner en linea con la meta.",
        }
    return {
        "estado": "rojo",
        "titulo": "Necesitas recuperar ritmo",
        "detalle": "La brecha diaria sube si no compensas en los proximos dias habiles.",
    }


def dividir(numerador: float, denominador: float) -> float:
    return numerador / denominador if denominador else 0.0


def listar_carteras_metas() -> List[Dict]:
    return listar_carteras()
