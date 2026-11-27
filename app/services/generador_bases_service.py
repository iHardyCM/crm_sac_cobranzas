"""Generador de bases: catálogo, consulta con embudo, actualización por cartera, generación y traza.

Lee y escribe en CobAuto (esquema score) con la conexión del CRM (engine_siscob, base por defecto CobAuto).
Las reglas de armado del SQL y del nombre del archivo están en generador_bases_reglas (sin base de datos).
"""
from __future__ import annotations

import csv
import io
import json
import logging
import threading
import time
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional

from openpyxl import Workbook
from sqlalchemy import text

from app.core.db_siscob import engine_siscob
from app.services import generador_bases_reglas as reglas
from app.services.generador_bases_reglas import CampoMeta, RecetaInvalida

logger = logging.getLogger(__name__)

NOMBRES_CARTERA = {
    112: "MIBANCO CASTIGO", 117: "INTERBANK", 124: "COMPARTAMOS CASTIGO IND",
    126: "COMPARTAMOS VIGENTE IND", 128: "COMPARTAMOS VIGENTE CCM", 132: "SIP (FINANCIERA OH)",
    133: "COMPARTAMOS GRUPAL VIGENTE", 137: "PROPIA INTERBANK", 144: "COMPARTAMOS GRUPAL CASTIGO",
    148: "PROPIA SIP",
}
MAX_VALORES_CATALOGO = 300
TAMANO_PAGINA_MAX = 200
# Tope por sentencia de la consulta de la pantalla (15/11/2026: una consulta con 16 filtros quedó corriendo y
# bloqueó el backend). Si se pasa, se corta en SQL Server y la pantalla avisa.
SEGUNDOS_MAX_CONSULTA = 120


def _json(valor):
    if isinstance(valor, Decimal):
        return float(valor)
    if isinstance(valor, (datetime, date)):
        return valor.isoformat()
    return valor


def _filas(resultado) -> List[Dict[str, Any]]:
    return [{k: _json(v) for k, v in fila.items()} for fila in resultado.mappings().all()]


# ---------------------------------------------------------------- carteras combinadas
# Una cartera combinada (score.CarteraCombinada, fase 10) junta varias carteras reales en una sola opción del
# generador, p. ej. 901 = Vigente IND (126) + Vigente CCM (128). Cada fila conserva su cartera real; un mismo
# cliente + teléfono va una vez (la fila de mejor score). Las carteras reales siguen disponibles por separado.
def _combinadas(conn) -> Dict[int, Dict[str, Any]]:
    if conn.execute(text("SELECT OBJECT_ID('score.CarteraCombinadaMiembro')")).scalar() is None:
        return {}      # fase 10 sin ejecutar: no hay combinadas
    salida: Dict[int, Dict[str, Any]] = {}
    for f in conn.execute(text("""
            SELECT c.IdCartera, c.Nombre, c.Abreviatura, c.CarteraArchivo, m.IdCarteraMiembro
            FROM score.CarteraCombinada AS c
            INNER JOIN score.CarteraCombinadaMiembro AS m ON m.IdCartera = c.IdCartera
            WHERE c.Activo = 1 ORDER BY c.IdCartera, m.IdCarteraMiembro""")).mappings():
        c = salida.setdefault(int(f["IdCartera"]), {"nombre": f["Nombre"], "archivo": int(f["CarteraArchivo"]),
                                                    "abreviatura": reglas._pieza(f["Abreviatura"]) or "MIX",
                                                    "miembros": []})
        c["miembros"].append(int(f["IdCarteraMiembro"]))
    return salida


def carteras_de(conn, idcartera: int) -> List[int]:
    """Carteras reales detrás de la cartera elegida: sus miembros si es combinada; si no, ella misma."""
    c = _combinadas(conn).get(int(idcartera))
    return list(c["miembros"]) if c else [int(idcartera)]


def carteras_reales(idcartera: int) -> List[int]:
    """Para la autorización: el usuario debe tener permiso sobre todas las carteras reales."""
    with engine_siscob.connect() as conn:
        return carteras_de(conn, idcartera)


def _en(carteras: List[int]) -> str:
    return reglas.lista_carteras(carteras)


# ---------------------------------------------------------------- carteras
def listar_carteras(permitidas: Optional[set]) -> List[Dict[str, Any]]:
    """Carteras con tabla de trabajo armada, con su última actualización. None = todas.
    Al final, las combinadas cuyas carteras estén todas armadas y permitidas."""
    with engine_siscob.connect() as conn:
        combinadas = _combinadas(conn)
        filas = _filas(conn.execute(text("""
            SELECT e.IdCartera, e.FechaCorteFuente, e.ClientesUniverso, e.FechaArmado,
                   a.UltimaActualizacion, a.Usuario AS UsuarioActualizacion, a.Origen AS OrigenActualizacion,
                   a.HistorialHasta, a.Version, a.Telefonos, a.Aviso, a.Segundos, a.EnCurso
            FROM score.BaseTrabajoEstado AS e
            LEFT JOIN score.vw_ActualizacionCarteraEstado AS a ON a.IdCartera = e.IdCartera
            ORDER BY e.IdCartera
        """)))
    entidades = _entidades()
    salida = []
    por_id = {}
    for f in filas:
        f["Nombre"] = NOMBRES_CARTERA.get(int(f["IdCartera"]), f"CARTERA {f['IdCartera']}")
        f["Entidad"] = entidades.get(int(f["IdCartera"]))
        por_id[int(f["IdCartera"])] = f
        if permitidas is not None and int(f["IdCartera"]) not in permitidas:
            continue
        salida.append(f)
    for idc, c in combinadas.items():
        miembros = [por_id.get(m) for m in c["miembros"]]
        if not all(miembros) or (permitidas is not None and not set(c["miembros"]) <= set(permitidas)):
            continue
        salida.append(_fila_combinada(idc, c, miembros))
    return salida


def _fila_combinada(idc: int, c: Dict[str, Any], miembros: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Estado de la combinada a partir de sus carteras: la actualización y el corte más antiguos (lo que manda),
    clientes y teléfonos sumados (un cliente en ambas cuenta dos veces aquí; la base lo deja una vez)."""
    def menor(k):
        valores = [m[k] for m in miembros if m.get(k)]
        return min(valores) if valores else None

    def suma(k):
        return sum(int(m[k] or 0) for m in miembros)

    avisos = [f"{m['IdCartera']}: {m['Aviso']}" for m in miembros if m.get("Aviso")]
    return {
        "IdCartera": idc, "Nombre": c["nombre"], "Entidad": miembros[0].get("Entidad"), "Miembros": c["miembros"],
        "FechaCorteFuente": menor("FechaCorteFuente"), "ClientesUniverso": suma("ClientesUniverso"),
        "FechaArmado": menor("FechaArmado"), "UltimaActualizacion": menor("UltimaActualizacion"),
        "UsuarioActualizacion": None, "OrigenActualizacion": " + ".join(str(m) for m in c["miembros"]),
        "HistorialHasta": menor("HistorialHasta"), "Version": miembros[0].get("Version"),
        "Telefonos": suma("Telefonos"), "Aviso": " · ".join(avisos) or None, "Segundos": None,
        "EnCurso": any(m.get("EnCurso") for m in miembros),
    }


def _entidades() -> Dict[int, str]:
    """Entidad de cada cartera (la misma tabla que usa la calibración del score). Si no se puede leer, vacío."""
    try:
        with engine_siscob.connect() as conn:
            filas = conn.execute(text("""
                SELECT ec.IdCartera, e.Codigo
                FROM ControlCobranza.bl.EntidadCartera AS ec
                INNER JOIN ControlCobranza.bl.Entidad AS e ON e.IdEntidad = ec.IdEntidad
            """)).fetchall()
        return {int(f[0]): str(f[1]) for f in filas}
    except Exception:
        logger.warning("No se pudo leer la entidad de las carteras (ControlCobranza.bl.EntidadCartera)", exc_info=True)
        return {}


# ---------------------------------------------------------------- catálogo
def _leer_catalogo(conn, carteras: List[int]) -> Dict[str, CampoMeta]:
    """En una combinada, un campo está disponible si lo tiene alguna de sus carteras."""
    filas = conn.execute(text(f"""
        SELECT c.Codigo, c.Etiqueta, c.Abreviatura, c.Grupo, c.TipoFiltro, c.Origen, c.ColumnaOrigen,
               CASE WHEN c.Grupo IN ('SCORE', 'TELEFONO') OR c.TodasLasCarteras = 1
                         OR EXISTS (SELECT 1 FROM score.CampoCartera AS cc
                                    WHERE cc.Campo = c.Codigo AND cc.IdCartera IN ({_en(carteras)}))
                    THEN 1 ELSE 0 END AS Disponible
        FROM score.Campo AS c
        WHERE c.Activo = 1
    """)).mappings().all()
    return {f["Codigo"]: CampoMeta(f["Codigo"], f["Etiqueta"], f["Abreviatura"], f["Grupo"], f["TipoFiltro"],
                                   f["Origen"], f["ColumnaOrigen"], bool(f["Disponible"])) for f in filas}


# ---------------------------------------------------------------- SAC del día (fase 17, 25/11/2026)
# Compartamos vigente: la foto del SAC (score.SacClienteDia) se toma sola cuando el SAC tiene una carga nueva.
# Como máximo una revisión por minuto en este proceso; si falla, la vista marca SAC DESACTUALIZADO al pasar el día.
_SAC_REVISADO = 0.0
_SAC_CANDADO = threading.Lock()


def asegurar_sac() -> None:
    global _SAC_REVISADO
    if time.monotonic() - _SAC_REVISADO < 60:
        return
    with _SAC_CANDADO:
        if time.monotonic() - _SAC_REVISADO < 60:
            return
        _SAC_REVISADO = time.monotonic()
        try:
            with engine_siscob.begin() as conn:
                if conn.execute(text("SELECT OBJECT_ID('score.sp_CargarSac')")).scalar() is not None:
                    conn.execute(text("EXEC score.sp_CargarSac @Simular = 0"))
        except Exception:
            logger.exception("No se pudo tomar la foto del SAC del día")


def hay_zonas(conn, carteras: List[int]) -> bool:
    """¿Hay zonas restringidas vigentes para estas carteras? (fase 19; sin la fase instalada, no)."""
    if conn.execute(text("SELECT CASE WHEN OBJECT_ID('score.vw_ClienteZonaRestringida') IS NULL "
                         "OR COL_LENGTH('score.ZonaRestringida', 'AplicaTodas') IS NULL THEN 0 ELSE 1 END")).scalar() == 0:
        return False
    en = reglas.lista_carteras(carteras)
    return bool(conn.execute(text(f"""
        SELECT COUNT(*) FROM score.ZonaRestringida AS z
        WHERE z.Activo = 1 AND z.Desde <= CAST(GETDATE() AS DATE)
          AND (z.Hasta IS NULL OR z.Hasta >= CAST(GETDATE() AS DATE))
          AND (z.AplicaTodas = 1 OR EXISTS (SELECT 1 FROM score.ZonaRestringidaCartera AS zc
                                            WHERE zc.IdZona = z.IdZona AND zc.IdCartera IN ({en})))""")).scalar())


def obtener_catalogo(idcartera: int) -> Dict[str, Any]:
    asegurar_sac()
    with engine_siscob.connect() as conn:
        carteras = carteras_de(conn, idcartera)
        en = _en(carteras)
        # Nivel, tabla y columna: los de la primera cartera que tiene el campo
        campos = _filas(conn.execute(text(f"""
            SELECT c.Codigo, c.Etiqueta, c.Abreviatura, c.Grupo, c.TipoFiltro, c.Origen, c.ColumnaOrigen, c.OrdenValores,
                   c.Descripcion, c.Fuente, c.Actualizacion, cc.Nivel, cc.Tabla, cc.Columna
            FROM score.Campo AS c
            OUTER APPLY (SELECT TOP 1 x.Nivel, x.Tabla, x.Columna FROM score.CampoCartera AS x
                         WHERE x.Campo = c.Codigo AND x.IdCartera IN ({en}) ORDER BY x.IdCartera) AS cc
            WHERE c.Activo = 1 AND (cc.Nivel IS NOT NULL OR c.Grupo IN ('SCORE', 'TELEFONO') OR c.TodasLasCarteras = 1
                                    OR EXISTS (SELECT 1 FROM score.CampoCartera AS y
                                               WHERE y.Campo = c.Codigo AND y.IdCartera IN ({en})))
            ORDER BY c.Grupo, c.Etiqueta
        """)))

        # Valores de los campos guardados como filas (listas y sí/no), con clientes por valor
        valores_dato = conn.execute(text(f"""
            SELECT d.Campo, d.Valor, COUNT(DISTINCT d.DNI) AS Clientes, MIN(d.FechaFuente) AS FechaFuente
            FROM {reglas.FUENTE_DATO} AS d
            INNER JOIN score.Campo AS c ON c.Codigo = d.Campo AND c.TipoFiltro IN ('LISTA', 'SINO')
            WHERE d.IdCartera IN ({en}) AND d.Valor IS NOT NULL
            GROUP BY d.Campo, d.Valor
        """)).mappings().all()

        fechas_dato = {f["Campo"]: _json(f["FechaFuente"]) for f in conn.execute(text(f"""
            SELECT Campo, MIN(FechaFuente) AS FechaFuente FROM {reglas.FUENTE_DATO}
            WHERE IdCartera IN ({en}) GROUP BY Campo
        """)).mappings().all()}

        # Valores de las columnas de lista de la vista (teléfono y cliente), en una sola lectura
        listas = [reglas.CampoMeta(c["Codigo"], c["Etiqueta"], c["Abreviatura"], c["Grupo"], c["TipoFiltro"],
                                   c["Origen"], c.get("ColumnaOrigen"))
                  for c in campos if c["Origen"] == "TRABAJO" and c["TipoFiltro"] == "LISTA"
                  and c.get("ColumnaOrigen") in reglas.COLUMNAS_VISTA]
        sql_listas = reglas.sql_grupos(listas, f"score.vw_BaseTrabajo AS a WHERE a.IdCartera IN ({en})", por_cliente=False)
        valores_vista = conn.execute(text(sql_listas)).mappings().all() if sql_listas else []

    por_campo: Dict[str, List[Dict[str, Any]]] = {}
    for v in valores_dato:
        por_campo.setdefault(v["Campo"], []).append({"valor": v["Valor"], "clientes": int(v["Clientes"])})
    for v in valores_vista:
        valor = v["Valor"] if v["Valor"] is not None else reglas.SIN_DATO
        por_campo.setdefault(v["Campo"], []).append({"valor": valor, "telefonos": int(v["N"])})

    for campo in campos:
        lista = por_campo.get(campo["Codigo"], [])
        orden = [x for x in (campo.get("OrdenValores") or "").split("|") if x]
        posicion = {valor: i for i, valor in enumerate(orden)}
        lista.sort(key=lambda x: (posicion.get(x["valor"], len(orden)), -(x.get("clientes") or x.get("telefonos") or 0)))
        tramos = reglas.tramos_de(reglas.CampoMeta(campo["Codigo"], campo["Etiqueta"], campo["Abreviatura"],
                                                   campo["Grupo"], campo["TipoFiltro"], campo["Origen"], campo.get("Columna")))
        if tramos:   # campo numérico: se elige por tramos fijos (el conteo llega con la consulta)
            lista = [{"valor": t} for t in tramos]
        campo["Tramos"] = bool(tramos)
        campo["Valores"] = lista[:MAX_VALORES_CATALOGO]
        campo["ValoresTruncados"] = len(lista) > MAX_VALORES_CATALOGO
        campo["FechaFuente"] = fechas_dato.get(campo["Codigo"])

    condiciones = [{"Codigo": k, **v, "Modos": list(reglas.MODOS_CONDICION)} for k, v in reglas.CONDICIONES.items()]
    return {"idcartera": idcartera, "carteras": carteras, "campos": campos, "condiciones": condiciones,
            "canales": reglas.CANALES}


# ---------------------------------------------------------------- consulta
def _ejecutar(conn, sql: str, params: Dict[str, Any]):
    """Ejecuta con solo los parámetros que el SQL usa."""
    return conn.execute(text(sql), reglas.solo_parametros_usados(sql, params))


SQL_TOTALES = """
SELECT COUNT(*) AS Telefonos, COUNT(DISTINCT DNI) AS Clientes,
       SUM(CASE WHEN rn = 1 THEN Capital END) AS Capital,
       AVG(CAST(Score AS DECIMAL(9, 2))) AS ScorePromedio,
       SUM(CASE WHEN Tramo = 'A' THEN 1 ELSE 0 END) AS TramoA,
       SUM(CASE WHEN Tramo = 'B' THEN 1 ELSE 0 END) AS TramoB,
       SUM(CASE WHEN Tramo = 'C' THEN 1 ELSE 0 END) AS TramoC,
       SUM(CASE WHEN Tramo = 'D' THEN 1 ELSE 0 END) AS TramoD,
       SUM(CASE WHEN Tramo = 'E' THEN 1 ELSE 0 END) AS TramoE,
       SUM(CASE WHEN UPPER(CONVERT(VARCHAR(5), Whatsapp)) = 'SI' THEN 1 ELSE 0 END) AS WhatsappSi,
       SUM(CASE WHEN CONVERT(VARCHAR(5), Timbra) IN ('3', '4') THEN 1 ELSE 0 END) AS Timbrado34,
       MIN(FechaScore) AS FechaScore, MIN(Version) AS Version, MIN(FechaCorteFuente) AS FechaCorteCliente
FROM sel"""

# Mejor resultado del teléfono y del cliente en la ventana del historial (score.TelefonoDia: un registro por
# teléfono y día con su mejor resultado; score.ResultadoTelefono.Orden: menor = mejor). Último resultado del
# teléfono y datos de score.Caracteristicas del mismo corte del score. Solo para las filas de la página.
DIAS_HISTORIAL_PANTALLA = 90

SQL_PAGINA = """,
pg AS (
    SELECT Posicion, IdCartera, DNI, IdCliente, Telefono, rn AS OrdenEnBase, Score, Tramo, OrdenScore, PrioridadColor,
           Whatsapp, Osiptel, Timbra, Operador, Capital, RangoCapital, ContactoDirectoMes,
           Razon1, Razon2, Razon3, Razon_Resta, FechaScore
    FROM sel WHERE Posicion BETWEEN :desde AND :hasta
)
SELECT pg.Posicion, pg.IdCartera, pg.DNI, pg.IdCliente, pg.Telefono, pg.OrdenEnBase, pg.Score, pg.Tramo, pg.OrdenScore,
       pg.PrioridadColor, pg.Whatsapp, pg.Osiptel, pg.Timbra, pg.Operador, pg.Capital, pg.RangoCapital,
       pg.ContactoDirectoMes, pg.Razon1, pg.Razon2, pg.Razon3, pg.Razon_Resta,
       mt.MejorResultado AS MejorResultadoTel, mt.Fecha AS FechaMejorTel,
       mc.MejorResultado AS MejorResultadoCli, mc.Fecha AS FechaMejorCli,
       ut.UltimoResultado AS UltimoResultadoTel, ut.UltimoEvento AS UltimoEventoTel,
       ca.DiasUltCef, ca.FranjaContacto
FROM pg
OUTER APPLY (SELECT TOP 1 d.MejorResultado, d.Fecha
             FROM score.TelefonoDia AS d INNER JOIN score.ResultadoTelefono AS r ON r.Codigo = d.MejorResultado
             WHERE d.IdCartera = pg.IdCartera AND d.DNI = pg.DNI AND d.Telefono = pg.Telefono AND d.Fecha >= :desde_hist
             ORDER BY r.Orden, d.Fecha DESC) AS mt
OUTER APPLY (SELECT TOP 1 d.MejorResultado, d.Fecha
             FROM score.TelefonoDia AS d INNER JOIN score.ResultadoTelefono AS r ON r.Codigo = d.MejorResultado
             WHERE d.IdCartera = pg.IdCartera AND d.DNI = pg.DNI AND d.Fecha >= :desde_hist
             ORDER BY r.Orden, d.Fecha DESC) AS mc
OUTER APPLY (SELECT TOP 1 d.UltimoResultado, d.UltimoEvento
             FROM score.TelefonoDia AS d
             WHERE d.IdCartera = pg.IdCartera AND d.DNI = pg.DNI AND d.Telefono = pg.Telefono AND d.Fecha >= :desde_hist
               AND d.UltimoEvento IS NOT NULL
             ORDER BY d.UltimoEvento DESC) AS ut
LEFT JOIN score.Caracteristicas AS ca
       ON ca.FechaCorte = pg.FechaScore AND ca.Poblacion = 'UNIVERSO' AND ca.IdCartera = pg.IdCartera
      AND ca.DNI = pg.DNI AND ca.Telefono = pg.Telefono
ORDER BY pg.Posicion"""


def _condiciones_frescas(conn, hoy) -> set:
    filas = conn.execute(text(reglas.SQL_CONDICIONES_FRESCAS),
                         {"hoy": hoy, "segundos": reglas.SEGUNDOS_CACHE_CONDICIONES}).fetchall()
    return {(str(f[0]), int(f[1])) for f in filas}


def asegurar_condiciones(consulta, tiempos: Dict[str, int]) -> bool:
    """Deja al día (máximo SEGUNDOS_CACHE_CONDICIONES de antigüedad) la foto de cada condición del día que usa la
    receta, por cartera. Devuelve False si las tablas de la fase 12 no existen: la consulta sigue en vivo."""
    codigos = [x for x in reglas.condiciones_usadas(consulta) if x in reglas.CONDICIONES_CACHE]
    if not codigos:
        return True
    hoy = consulta.params["hoy"]
    with engine_siscob.connect() as conn:
        if conn.execute(text("SELECT OBJECT_ID('score.CondicionDiaEstado')")).scalar() is None:
            logger.warning("Generador: falta ejecutar score_telefonico_fase12_condiciones.sql; condiciones en vivo")
            return False
        frescas = _condiciones_frescas(conn, hoy)
    for codigo in codigos:
        for idc in consulta.carteras:
            if (codigo, int(idc)) in frescas:
                continue
            inicio = time.perf_counter()
            with engine_siscob.begin() as conn:
                # Un candado por condición y cartera: si dos usuarios llegan a la vez, el segundo espera y
                # reutiliza la foto del primero en lugar de volver a leer SISCOB.
                bloqueo = conn.execute(text(
                    "SET NOCOUNT ON; DECLARE @r INT; EXEC @r = sp_getapplock @Resource = :recurso, "
                    "@LockMode = 'Exclusive', @LockOwner = 'Transaction', @LockTimeout = 60000; SELECT @r;"),
                    {"recurso": f"GB_COND_{codigo}_{int(idc)}"}).scalar()
                if bloqueo is None or int(bloqueo) < 0:
                    raise RecetaInvalida("Otra consulta está actualizando las condiciones del día de esta cartera. "
                                         "Intenta de nuevo en unos segundos.")
                if (codigo, int(idc)) in _condiciones_frescas(conn, hoy):
                    continue
                filas = 0
                for sql in reglas.sql_refrescar_condicion(codigo, idc):
                    resultado = _ejecutar(conn, sql, consulta.params)
                    if sql.startswith("INSERT"):
                        filas = max(int(resultado.rowcount or 0), 0)
                ms = int((time.perf_counter() - inicio) * 1000)
                conn.execute(text(reglas.SQL_ESTADO_CONDICION),
                             {"codigo": codigo, "idcartera": int(idc), "hoy": hoy, "filas": filas, "ms": ms})
            tiempos[f"cond_{codigo}_{int(idc)}"] = ms
    return True


def consultar(idcartera: int, receta: Dict, pagina: int = 1, tamano: int = 50) -> Dict[str, Any]:
    """Embudo, totales, página y (si se piden) conteos de cada filtro, leyendo la vista una sola vez."""
    tamano = max(1, min(int(tamano or 50), TAMANO_PAGINA_MAX))
    pagina = max(1, int(pagina or 1))
    tiempos: Dict[str, int] = {}
    reloj = time.perf_counter()

    def marca(nombre):
        nonlocal reloj
        ahora = time.perf_counter()
        tiempos[nombre] = int((ahora - reloj) * 1000)
        reloj = ahora

    asegurar_sac()
    with engine_siscob.connect() as conn:
        dbapi = getattr(conn.connection, "dbapi_connection", None)
        timeout_previo = getattr(dbapi, "timeout", 0) if dbapi is not None else 0
        carteras = carteras_de(conn, idcartera)
        catalogo = _leer_catalogo(conn, carteras)
        consulta = reglas.construir_consulta(idcartera, receta, catalogo, carteras=carteras,
                                               zonas=hay_zonas(conn, carteras))
        por_cliente = reglas.telefonos_por_cliente(receta)
        marca("catalogo")
        try:
            if dbapi is not None:
                dbapi.timeout = SEGUNDOS_MAX_CONSULTA
            # Condiciones del día desde la foto compartida (se refresca en otra conexión si está vencida)
            condiciones_cache = asegurar_condiciones(consulta, tiempos)
            marca("condiciones")
            for sql in reglas.sql_materializar(consulta, condiciones_cache):
                _ejecutar(conn, sql, consulta.params)
            marca("lectura")
            fila = _ejecutar(conn, reglas.sql_embudo_temp(consulta), consulta.params).fetchone()
            embudo = reglas.embudo_desde_fila(fila, consulta.pasos)
            base = reglas.sql_seleccion_temp(por_cliente)
            totales = _ejecutar(conn, base + SQL_TOTALES, {}).mappings().first()
            marca("totales")
            params = dict(desde=(pagina - 1) * tamano + 1, hasta=pagina * tamano,
                          desde_hist=date.today() - timedelta(days=DIAS_HISTORIAL_PANTALLA))
            filas = _filas(_ejecutar(conn, base + SQL_PAGINA, params))
            marca("pagina")
            segmentadores = None
            if receta.get("conteos"):
                # Si fallan los conteos, la consulta sigue: la pantalla avisa en el modal de filtros
                # Tiempos por parte: conteos_preparar (clientes de la base), conteos_vista (campos de la vista),
                # conteos_datos (campos por cuenta del cliente)
                try:
                    segmentadores = _conteos(conn, consulta, catalogo, marca)
                except Exception:
                    logger.exception("No se pudieron calcular los conteos de los filtros (cartera %s)", idcartera)
                    segmentadores = {"error": "No se pudieron calcular los conteos de los filtros."}
                    marca("conteos_error")
        except Exception as exc:
            if _es_timeout(exc):
                raise RecetaInvalida(f"La consulta pasó de {SEGUNDOS_MAX_CONSULTA} segundos y se detuvo. "
                                     "Prueba con menos filtros a la vez o avísame qué filtros usaste.")
            raise
        finally:
            try:
                if dbapi is not None:
                    dbapi.timeout = 0
                conn.execute(text(reglas.sql_borrar_temporales()))
            finally:
                if dbapi is not None:
                    dbapi.timeout = timeout_previo or 0

    # Medición (20/11/2026): cuánto cuesta cada etapa por clic, para decidir la optimización con datos reales.
    logger.info("Generador consulta cartera=%s filtros=%s condiciones=%s conteos=%s pagina=%s telefonos=%s tiempos_ms=%s",
                idcartera, len(receta.get("filtros") or []),
                sum(1 for m in (receta.get("condiciones") or {}).values() if str(m).upper() != "INDIFERENTE"),
                bool(receta.get("conteos")), pagina, int(totales["Telefonos"] or 0), tiempos)
    if por_cliente:
        embudo.append({"paso": f"Hasta {por_cliente} teléfono(s) por cliente",
                       "telefonos": int(totales["Telefonos"] or 0), "clientes": int(totales["Clientes"] or 0)})
    salida = {"idcartera": idcartera, "totales": {k: _json(v) for k, v in totales.items()},
              "embudo": embudo, "pagina": pagina, "tamano": tamano, "filas": filas,
              "dias_historial": DIAS_HISTORIAL_PANTALLA, "tiempos_ms": tiempos}
    if segmentadores is not None:
        salida["segmentadores"] = segmentadores
    return salida


def _es_timeout(exc: Exception) -> bool:
    texto = str(exc).lower()
    return "hyt00" in texto or "timeout expired" in texto or "tiempo de espera" in texto


def _conteos(conn, consulta, catalogo, marca=lambda _nombre: None) -> Dict[str, Any]:
    """Conteos por valor de cada filtro con la receta aplicada (cada campo con filtro propio se cuenta sin
    ese filtro, como los segmentadores de Excel). Usa la temporal que dejó consultar()."""
    plan = reglas.plan_conteos(consulta, catalogo)
    conteos: Dict[str, Dict[str, int]] = {}

    def sumar(filas):
        for f in filas:
            campo, valor = str(f[0]), (str(f[1]) if f[1] is not None else reglas.SIN_DATO)
            conteos.setdefault(campo, {})[valor] = conteos.get(campo, {}).get(valor, 0) + int(f[2] or 0)

    conn.execute(text(plan["preparar"]))
    clientes = int(conn.execute(text(f"SELECT COUNT(DISTINCT DNI) FROM {reglas.TEMP_CLIENTES}")).scalar() or 0)
    marca("conteos_preparar")
    if plan["trabajo"]:
        sumar(_ejecutar(conn, plan["trabajo"], consulta.params).fetchall())
    marca("conteos_vista")
    for codigo in plan["dato_comun"]:
        conteos.setdefault(codigo, {})
    for sql in plan["dato"]:
        sumar(_ejecutar(conn, sql, consulta.params).fetchall())
    for sql in plan["con_dato"]:
        con_dato = {str(f[0]): int(f[1] or 0) for f in _ejecutar(conn, sql, consulta.params).fetchall()}
        for codigo in plan["dato_comun"]:
            sin = clientes - con_dato.get(codigo, 0)
            if sin > 0:
                conteos[codigo][reglas.SIN_DATO] = sin
    marca("conteos_datos")
    return {"conteos": conteos, "clientes": clientes}


# ---------------------------------------------------------------- actualizar cartera
def actualizar_cartera(idcartera: int, usuario_dni: str) -> Dict[str, Any]:
    """Actualiza la cartera; una combinada actualiza sus carteras una tras otra. Si una está ocupada o falla,
    se detiene ahí y lo dice (las anteriores ya quedaron actualizadas)."""
    carteras = carteras_reales(idcartera)
    if len(carteras) == 1:
        return _actualizar_una(carteras[0], usuario_dni)
    segundos, avisos, ultimo = 0, [], {}
    for c in carteras:
        ultimo = _actualizar_una(c, usuario_dni)
        if ultimo.get("Resultado") == "OCUPADA" or ultimo.get("Estado") != "OK":
            ultimo = dict(ultimo, Cartera=c, Error=f"Cartera {c}: {ultimo.get('Error') or ultimo.get('Aviso') or ''}".strip())
            return ultimo
        segundos += int(ultimo.get("Segundos") or 0)
        if ultimo.get("Aviso"):
            avisos.append(f"{c}: {ultimo['Aviso']}")
    return dict(ultimo, Segundos=segundos, Aviso=" · ".join(avisos) or None, Carteras=carteras)


def _actualizar_una(idcartera: int, usuario_dni: str) -> Dict[str, Any]:
    """Ejecuta score.sp_ActualizarCartera (modo real). Devuelve la fila de la bitácora o OCUPADA."""
    conexion = engine_siscob.raw_connection()
    dbapi = getattr(conexion, "driver_connection", None) or conexion.connection
    try:
        dbapi.autocommit = True   # el procedimiento maneja sus transacciones y su candado de sesión
        cursor = dbapi.cursor()
        cursor.execute(
            "EXEC score.sp_ActualizarCartera @IdCartera = ?, @Usuario = ?, @Origen = 'MANUAL', @Alinear = 1, @Simular = 0",
            int(idcartera), str(usuario_dni))
        ultimo = None
        while True:
            if cursor.description:
                columnas = [c[0] for c in cursor.description]
                filas = cursor.fetchall()
                if filas and columnas and columnas[0] == "Resultado":
                    ultimo = {k: _json(v) for k, v in zip(columnas, filas[-1])}
            if not cursor.nextset():
                break
        cursor.close()
    finally:
        try:
            dbapi.autocommit = False
        finally:
            conexion.close()
    if ultimo is None:
        raise RuntimeError("La actualización no devolvió resultado.")
    return ultimo


# ---------------------------------------------------------------- generar base
def _prefijo_nombre(idcartera: int, combinada: Optional[Dict[str, Any]]) -> tuple:
    """('126', '126') o, en una combinada, ('126', '126 VIGMIX'): código de 3 dígitos y comienzo del nombre."""
    cartera_txt = f"{int(combinada['archivo'] if combinada else idcartera):03d}"
    return cartera_txt, (f"{cartera_txt} {combinada['abreviatura']}" if combinada else cartera_txt)


def proponer_nombre(idcartera: int, receta: Dict) -> Dict[str, Any]:
    """Nombre propuesto para la base (sin el código, que se agrega al generar). El usuario lo puede corregir."""
    canal = str(receta.get("canal") or "").upper()
    with engine_siscob.connect() as conn:
        combinada = _combinadas(conn).get(int(idcartera))
        carteras = list(combinada["miembros"]) if combinada else [int(idcartera)]
        catalogo = _leer_catalogo(conn, carteras)
        # Código que probablemente tendrá la base (el definitivo se asigna al generar)
        siguiente = conn.execute(text("SELECT IDENT_CURRENT('score.Base') + IDENT_INCR('score.Base')")).scalar()
    cartera_txt, prefijo = _prefijo_nombre(idcartera, combinada)
    return {"nombre": reglas.nombre_legible(prefijo, canal, receta, catalogo, datetime.now()),
            "cartera": cartera_txt, "codigo_probable": f"B{int(siguiente)}" if siguiente is not None else None,
            "largo_maximo": 110}


def generar_base(idcartera: int, receta: Dict, usuario_dni: str) -> Dict[str, Any]:
    canal = str(receta.get("canal") or "").upper()
    if canal not in reglas.CANALES:
        raise RecetaInvalida("Elige el canal de la base: predictivo, preview, IVR/TTS, SMS u otro.")
    descripcion = str(receta.get("descripcion") or "").strip()[:200] or None
    momento = datetime.now().replace(microsecond=0)
    asegurar_sac()

    with engine_siscob.begin() as conn:
        combinada = _combinadas(conn).get(int(idcartera))
        carteras = list(combinada["miembros"]) if combinada else [int(idcartera)]
        catalogo = _leer_catalogo(conn, carteras)
        consulta = reglas.construir_consulta(idcartera, receta, catalogo, carteras=carteras,
                                               zonas=hay_zonas(conn, carteras))
        por_cliente = reglas.telefonos_por_cliente(receta)
        base = reglas.sql_seleccion(consulta, por_cliente)

        # Última actualización buena; en una combinada, la más antigua de sus carteras
        ultima = conn.execute(text(f"""
            SELECT MIN(Fin) FROM (
                SELECT IdCartera, MAX(Fin) AS Fin FROM score.ActualizacionCartera
                WHERE IdCartera IN ({_en(carteras)}) AND Estado = 'OK' AND Modo = 'REAL' GROUP BY IdCartera
            ) AS x
        """)).scalar()

        id_base = conn.execute(text("""
            INSERT INTO score.Base (IdCartera, Canal, Descripcion, Receta, Usuario, FechaGeneracion, UltimaActualizacion)
            OUTPUT inserted.IdBase
            VALUES (:id, :canal, :descripcion, :receta, :usuario, :momento, :ultima)
        """), {"id": idcartera, "canal": canal, "descripcion": descripcion,
               "receta": json.dumps(receta, ensure_ascii=False, default=str), "usuario": usuario_dni,
               "momento": momento, "ultima": ultima}).scalar()

        _ejecutar(conn, base + """
            INSERT INTO score.BaseDetalle (IdBase, Posicion, IdCartera, DNI, IdCliente, Telefono, Score, Tramo, OrdenCliente)
            SELECT :idbase, Posicion, IdCartera, DNI, IdCliente, Telefono, Score, Tramo, rn FROM sel""",
                  dict(consulta.params, idbase=id_base))

        resumen = _ejecutar(conn, base + SQL_TOTALES, consulta.params).mappings().first()

        if not resumen["Telefonos"]:
            raise RecetaInvalida("La base no tiene teléfonos con estos filtros: no se generó.")

        codigo = f"B{id_base}"
        # Nombre legible (24/11/2026): el que el usuario dejó en la pantalla o, si no mandó, la propuesta.
        # Empieza por la cartera (LunaTel la toma de los 3 primeros dígitos; la combinada usa su CarteraArchivo).
        cartera_txt, prefijo = _prefijo_nombre(idcartera, combinada)
        editado = str(receta.get("nombre") or "").strip()
        nombre = reglas.nombre_final(editado or reglas.nombre_legible(prefijo, canal, receta, catalogo, momento),
                                     cartera_txt, codigo, momento)
        conn.execute(text("""
            UPDATE score.Base SET Codigo = :codigo, NombreArchivo = :nombre, Clientes = :clientes, Telefonos = :telefonos,
                   Capital = :capital, ScorePromedio = :promedio, FechaScore = :fscore, VersionScore = :version,
                   FechaCorteCliente = :fcorte
            WHERE IdBase = :idbase
        """), {"codigo": codigo, "nombre": nombre, "clientes": resumen["Clientes"], "telefonos": resumen["Telefonos"],
               "capital": resumen["Capital"], "promedio": resumen["ScorePromedio"], "fscore": resumen["FechaScore"],
               "version": resumen["Version"], "fcorte": resumen["FechaCorteCliente"], "idbase": id_base})

    return {"IdBase": id_base, "Codigo": codigo, "NombreArchivo": nombre, "Canal": canal,
            "Clientes": int(resumen["Clientes"]), "Telefonos": int(resumen["Telefonos"]),
            "Capital": _json(resumen["Capital"]), "FechaGeneracion": momento.isoformat()}


def obtener_base(id_base: int) -> Optional[Dict[str, Any]]:
    with engine_siscob.connect() as conn:
        fila = conn.execute(text("SELECT * FROM score.Base WHERE IdBase = :id"), {"id": id_base}).mappings().first()
    return {k: _json(v) for k, v in fila.items()} if fila else None


FORMATOS_ARCHIVO = {
    "xlsx": ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", ".xlsx"),
    "csv": ("text/csv; charset=utf-8", ".csv"),
}
COLUMNAS_ARCHIVO = ["CODIGO_BASE", "IDCARTERA", "POSICION", "DNI", "IDCLIENTE", "TELEFONO", "ORDEN_CLIENTE", "SCORE", "TRAMO"]
# CSV para el marcador (24/11/2026, Hardy): solo IdCliente y teléfono, con encabezado
COLUMNAS_CSV = ["IDCLIENTE", "TELEFONO"]


def _filas_archivo(id_base: int, codigo: str) -> List[List[Any]]:
    """Filas del archivo en el orden de la base. IdCliente: el guardado al generar (siscob.dbo.Cliente); en bases
    anteriores al 16/11/2026, el del universo actual de la cartera."""
    with engine_siscob.connect() as conn:
        filas = conn.execute(text("""
            SELECT d.Posicion, d.IdCartera, d.DNI, COALESCE(d.IdCliente, u.IdCliente) AS IdCliente, d.Telefono,
                   d.OrdenCliente, d.Score, d.Tramo
            FROM score.BaseDetalle AS d
            LEFT JOIN score.TelefonoUniverso AS u
                   ON u.IdCartera = d.IdCartera AND u.DNI = d.DNI AND u.Telefono = d.Telefono
            WHERE d.IdBase = :id ORDER BY d.Posicion
        """), {"id": id_base}).fetchall()
    return [[codigo, f.IdCartera, f.Posicion, f.DNI, f.IdCliente, f.Telefono, f.OrdenCliente, f.Score, f.Tramo]
            for f in filas]


def exportar_base(id_base: int, formato: str = "xlsx") -> bytes:
    """Archivo de la base. Excel: todas las columnas (para revisar). CSV para el marcador: solo IDCLIENTE y TELEFONO,
    delimitado por comas (UTF-8, sin BOM, fin de línea Windows)."""
    if formato not in FORMATOS_ARCHIVO:
        raise RecetaInvalida("Formato de archivo no soportado: usa xlsx o csv.")
    cabecera = obtener_base(id_base)
    filas = _filas_archivo(id_base, cabecera["Codigo"])
    if formato == "csv":
        salida_txt = io.StringIO()
        escritor = csv.writer(salida_txt, delimiter=",", lineterminator="\r\n")
        escritor.writerow(COLUMNAS_CSV)
        pos = [COLUMNAS_ARCHIVO.index(c) for c in COLUMNAS_CSV]
        escritor.writerows(["" if fila[i] is None else fila[i] for i in pos] for fila in filas)
        return salida_txt.getvalue().encode("utf-8")
    libro = Workbook(write_only=True)
    hoja = libro.create_sheet("BASE")
    hoja.append(COLUMNAS_ARCHIVO)
    for fila in filas:
        hoja.append(fila)
    salida = io.BytesIO()
    libro.save(salida)
    return salida.getvalue()


def exportar_base_xlsx(id_base: int) -> bytes:
    return exportar_base(id_base, "xlsx")


# ---------------------------------------------------------------- histórico
def listar_bases(permitidas: Optional[set], idcartera: Optional[int] = None, dias: int = 30) -> List[Dict[str, Any]]:
    dias = max(1, min(int(dias or 30), 365))
    with engine_siscob.connect() as conn:
        filas = _filas(conn.execute(text("""
            SELECT IdBase, Codigo, NombreArchivo, IdCartera, Canal, Descripcion, Usuario, FechaGeneracion,
                   FechaScore, VersionScore, FechaCorteCliente, Clientes, Telefonos, Capital, ScorePromedio, IdBaseOrigen
            FROM score.Base
            WHERE FechaGeneracion >= DATEADD(DAY, -:dias, CAST(GETDATE() AS DATE))
              AND (:id IS NULL OR IdCartera = :id)
              AND Codigo IS NOT NULL
            ORDER BY FechaGeneracion DESC
        """), {"dias": dias, "id": idcartera}))
    if permitidas is not None:
        with engine_siscob.connect() as conn:
            combinadas = _combinadas(conn)
        def permitida(idc):
            miembros = combinadas.get(idc, {}).get("miembros") or [idc]
            return set(miembros) <= set(permitidas)
        filas = [f for f in filas if permitida(int(f["IdCartera"]))]
    return filas


# ---------------------------------------------------------------- detalle del score
def score_version(idcartera: int) -> Dict[str, Any]:
    """Qué significa el score de la cartera: versión usada, cortes de tramo, métricas de la calibración
    (tasa de CEF por tramo en prueba, AUC), puntos por característica y cómo se reparte hoy la cartera."""
    with engine_siscob.connect() as conn:
        carteras = carteras_de(conn, idcartera)
        ultimo = conn.execute(text(f"""
            SELECT TOP 1 Version, FechaCorte FROM score.TelefonoScore
            WHERE IdCartera IN ({_en(carteras)}) ORDER BY FechaCorte DESC
        """)).mappings().first()
        if not ultimo:
            return {"idcartera": idcartera, "version": None}
        version = int(ultimo["Version"])
        pv = conn.execute(text("""
            SELECT Version, Estado, Descripcion, CorteDesde, CorteHasta, PuntosMaximos,
                   Tramo_A, Tramo_B, Tramo_C, Tramo_D, Metricas, FechaPublicacion
            FROM score.PesoVersion WHERE Version = :v
        """), {"v": version}).mappings().first()
        pesos = _filas(conn.execute(text("""
            SELECT Caracteristica, Tramo, Puntos, N, TasaExito FROM score.Peso
            WHERE Version = :v AND Tramo <> '*' ORDER BY Caracteristica, Puntos DESC
        """), {"v": version}))
        reparto = _filas(conn.execute(text(f"""
            SELECT Tramo, COUNT(*) AS Telefonos, MIN(Score) AS ScoreMin, MAX(Score) AS ScoreMax
            FROM score.vw_BaseTrabajo WHERE IdCartera IN ({_en(carteras)}) AND Descartado = 0 GROUP BY Tramo ORDER BY Tramo
        """)))
    metricas = {}
    if pv and pv["Metricas"]:
        try:
            metricas = json.loads(pv["Metricas"])
        except ValueError:
            metricas = {}
    cabecera = {k: _json(v) for k, v in pv.items() if k != "Metricas"} if pv else {}
    return {"idcartera": idcartera, "version": version, "fecha_score": _json(ultimo["FechaCorte"]),
            "entidad": _entidades().get(int(carteras[0])), "cabecera": cabecera, "metricas": metricas,
            "pesos": pesos, "reparto": reparto}


def score_telefono(idcartera: int, dni: str, telefono: str) -> Optional[Dict[str, Any]]:
    """Por qué un teléfono tiene su score: el tramo de cada característica y los puntos que suma."""
    with engine_siscob.connect() as conn:
        carteras = carteras_de(conn, idcartera)
        # En una combinada: la fila de mejor score (la que queda en la base)
        fila = conn.execute(text(f"""
            SELECT TOP 1 IdCartera, FechaScore, Version, Score, Tramo, OrdenCliente, Descartado, MotivoDescarte,
                   Razon1, Razon2, Razon3, Razon_Resta
            FROM score.vw_BaseTrabajo WHERE IdCartera IN ({_en(carteras)}) AND DNI = :dni AND Telefono = :tel
            ORDER BY Score DESC, IdCartera
        """), {"dni": dni, "tel": telefono}).mappings().first()
        if not fila:
            return None
        idcartera = int(fila["IdCartera"])
        version = int(fila["Version"])
        caract = conn.execute(text("""
            SELECT * FROM score.Caracteristicas
            WHERE FechaCorte = :f AND Poblacion = 'UNIVERSO' AND IdCartera = :id AND DNI = :dni AND Telefono = :tel
        """), {"f": fila["FechaScore"], "id": idcartera, "dni": dni, "tel": telefono}).mappings().first()
        pesos = conn.execute(text("""
            SELECT Caracteristica, Tramo, Puntos, N, TasaExito FROM score.Peso WHERE Version = :v
        """), {"v": version}).mappings().all()
        maximos = conn.execute(text("SELECT PuntosMaximos FROM score.PesoVersion WHERE Version = :v"),
                               {"v": version}).scalar()

    por_car: Dict[str, Dict[str, Any]] = {}
    for p in pesos:
        por_car.setdefault(p["Caracteristica"], {})[p["Tramo"]] = p
    detalle, total = [], 0.0
    for car in sorted(por_car):
        tramos = por_car[car]
        valor = None
        if caract is not None and car in caract:
            valor = caract[car] if caract[car] is not None else "SIN_DATO"
        peso = tramos.get(str(valor)) if valor is not None else None
        conocido = peso is not None
        peso = peso or tramos.get("*")
        puntos = float(peso["Puntos"]) if peso is not None else 0.0
        total += puntos
        detalle.append({
            "Caracteristica": car, "Tramo": valor, "Puntos": puntos, "TramoConocido": conocido,
            "Maximo": max(float(x["Puntos"]) for x in tramos.values()),
            "TasaExito": _json(peso["TasaExito"]) if conocido and peso["TasaExito"] is not None else None,
            "N": int(peso["N"]) if conocido and peso["N"] is not None else None,
            "Tramos": sorted(({"Tramo": t, "Puntos": float(x["Puntos"]),
                               "TasaExito": _json(x["TasaExito"]) if x["TasaExito"] is not None else None}
                              for t, x in tramos.items() if t != "*"), key=lambda x: -x["Puntos"]),
        })
    maximos = float(maximos) if maximos else None
    extra = {}
    if caract is not None:
        for k in ("DiasUltCef", "UltimoIntento", "FranjaContacto"):
            if k in caract:
                extra[k] = _json(caract[k])
    return {"idcartera": idcartera, "dni": dni, "telefono": telefono,
            "score": {k: _json(v) for k, v in fila.items()},
            "puntos": round(total, 2), "puntos_maximos": maximos,
            "score_calculado": round(total / maximos * 100) if maximos else None,
            "con_caracteristicas": caract is not None, "detalle": detalle, "datos": extra}
