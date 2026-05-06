from sqlalchemy import text
from app.core.db_siscob import engine_siscob
from datetime import datetime


def calcular_estado(fecha, pagado, fecha_pago):
    hoy = datetime.now().date()

    if pagado == "SI":
        return "Cumplida"
    elif fecha == hoy:
        return "Hoy"
    elif fecha < hoy:
        return "Caída"
    else:
        return "Vigente"

def obtener_compromisos(dni):

    hoy = datetime.now().date()
    inicio_mes = hoy.replace(day=1)

    data = []

    try:
        with engine_siscob.connect() as conn:

            query = text("""
                SELECT
                    C.IDCOMPROMISO,
                    C.FECHACOMPROMISO,
                    C.NUMOPERACION,
                    C.MONTO,
                    C.MONEDA,
                    C.MONTOPAGADO,
                    C.TIPOPAGO,

                    G.DNI,
                    G.IDCLIENTE,
                    G.TELEFONO,
                    G.GESTION,

                    CL.NOMBRECLIENTE,

                    CASE 
                        WHEN C.MONTOPAGADO > 0 THEN 'SI'
                        ELSE 'NO'
                    END AS PAGADO

                FROM SISCOB.DBO.COMPROMISO C WITH(NOLOCK)

                LEFT JOIN SISCOB.DBO.GESTION G WITH(NOLOCK)
                    ON G.IDGESTION = C.IDGESTION

                LEFT JOIN SISCOB.DBO.CLIENTE CL WITH(NOLOCK)
                    ON CL.IDCLIENTE = G.IDCLIENTE

                LEFT JOIN SISCOB.DBO.USUARIO U WITH(NOLOCK)
                    ON U.IDUSUARIO = G.IDUSUARIO
                WHERE
                    U.USUARIO = :dni
                    AND C.FECHACOMPROMISO >= :inicio_mes
                    AND C.MONTO > 0
            """)

            rows = conn.execute(query, {
                "dni": dni,
                "inicio_mes": inicio_mes
            }).fetchall()

            # 🔥 traer intentos del día
            query_intentos = text("""
                SELECT
                    G.IDCLIENTE,
                    COUNT(1) AS intentos_hoy
                FROM SISCOB.DBO.GESTION G WITH(NOLOCK)

                LEFT JOIN SISCOB.DBO.USUARIO U WITH(NOLOCK)
                    ON U.IDUSUARIO = G.IDUSUARIO

                WHERE 
                    CAST(G.FECHA AS DATE) = CAST(GETDATE() AS DATE)
                    AND U.USUARIO = :dni

                GROUP BY G.IDCLIENTE
            """)

            intentos_rows = conn.execute(query_intentos, {
                "dni": dni
            }).fetchall()

            # 🔥 mapear
            map_intentos = {r.IDCLIENTE: r.intentos_hoy for r in intentos_rows}

            for r in rows:

                fecha = r.FECHACOMPROMISO.date() if r.FECHACOMPROMISO else hoy

                estado = calcular_estado(
                    fecha,
                    r.PAGADO,
                    None
                )

                data.append({
                    "id": r.IDCOMPROMISO,
                    "cliente": r.NOMBRECLIENTE or "-",
                    "operacion": r.NUMOPERACION,
                    "dni": r.DNI,
                    "idcliente": r.IDCLIENTE,
                    "telefono": r.TELEFONO or "-",
                    "monto": float(r.MONTO or 0),
                    "fecha": str(fecha),
                    "estado": estado,

                    "intentos_hoy": map_intentos.get(r.IDCLIENTE, 0)
                })

    except Exception as e:
        print("ERROR REAL BACKEND:", e)  # 🔥 esto es clave
        raise

    return data