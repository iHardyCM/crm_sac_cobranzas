# zonas_restringidas_service.py
"""Zonas restringidas: departamentos donde no se gestiona (orden del banco o decisión interna).

Lee y escribe en CobAuto (esquema score, fase19 + fase20) con la conexión del CRM (engine_siscob).
- score.ZonaRestringida          una fila por departamento restringido (nunca se borra: se levanta).
- score.ZonaRestringidaCartera   carteras a las que aplica, cuando no es AplicaTodas.
- score.vw_ClienteZonaRestringida clientes que hoy caen en una restricción vigente; el generador de bases
                                   los quita con el paso forzado «Sin zona restringida».

La pantalla trabaja por DEPARTAMENTO. El valor se guarda en mayúsculas y sin tildes (SAN MARTIN), y la vista
compara sin distinguir tildes (fase20), así que cruza con «San Martín» de la asignación.
"""
import io
import unicodedata
from datetime import date, datetime
from typing import Any, Dict, Iterable, List, Optional

from openpyxl import Workbook
from openpyxl.cell import WriteOnlyCell
from openpyxl.utils import get_column_letter
from openpyxl.styles import Font, PatternFill
from sqlalchemy import bindparam, text

from app.services.generador_bases_service import NOMBRES_CARTERA

NIVEL = "DEPARTAMENTO"
ORIGENES = ("BANCO", "INTERNO")
DEPARTAMENTOS = (
    "AMAZONAS", "ANCASH", "APURIMAC", "AREQUIPA", "AYACUCHO", "CAJAMARCA", "CALLAO", "CUSCO",
    "HUANCAVELICA", "HUANUCO", "ICA", "JUNIN", "LA LIBERTAD", "LAMBAYEQUE", "LIMA", "LORETO",
    "MADRE DE DIOS", "MOQUEGUA", "PASCO", "PIURA", "PUNO", "SAN MARTIN", "TACNA", "TUMBES", "UCAYALI",
)
MAX_MOTIVO = 400
CI_AI = "Latin1_General_CI_AI"
# Los 25 nombres como tabla en línea (constantes del código: no vienen del usuario).
VALORES_DEPS = ", ".join(f"(N'{d}')" for d in DEPARTAMENTOS)

# PDP vigente: misma regla que el filtro «PDP vigente» del generador (generador_bases_reglas, 14/11/2026):
# compromiso de hoy en adelante, monto > 0 y no pagado (PAGADO distinto de SI / S).
SQL_PDP_VIGENTE = """
    SELECT cl.IdCartera, LTRIM(RTRIM(cl.Dni)) COLLATE DATABASE_DEFAULT AS DNI, cp.IdCliente,
           CAST(cp.FechaCompromiso AS DATE) AS FechaCompromiso, cp.Monto, cp.FechaGenero
    FROM siscob.dbo.COMPROMISO AS cp WITH (NOLOCK)
    INNER JOIN siscob.dbo.Cliente AS cl WITH (NOLOCK) ON cl.IdCliente = cp.IdCliente
    WHERE cp.FechaCompromiso >= CAST(GETDATE() AS DATE) AND cp.Monto > 0
      AND ISNULL(UPPER(LTRIM(RTRIM(cp.Pagado))), '') NOT IN ('SI', 'S')"""
# Por cliente: cuántas PDP vigentes, cuánto suman y la más próxima.
SQL_PDP_CLIENTE = f"""
    SELECT IdCartera, DNI, COUNT(*) AS Pdps, SUM(Monto) AS MontoPdp, MIN(FechaCompromiso) AS ProximaPdp
    FROM ({SQL_PDP_VIGENTE}) AS x
    GROUP BY IdCartera, DNI"""


class ZonaInvalida(ValueError):
    """Datos del formulario que no se pueden registrar (mensaje apto para el usuario)."""


def normalizar(valor: Any) -> str:
    """Mayúsculas, sin tildes y con un solo espacio: «San Martín » -> «SAN MARTIN»."""
    t = unicodedata.normalize("NFD", str(valor or ""))
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return " ".join(t.upper().split())


def _fecha(valor: Any, campo: str) -> Optional[date]:
    if valor in (None, ""):
        return None
    if isinstance(valor, date):
        return valor
    try:
        return datetime.strptime(str(valor)[:10], "%Y-%m-%d").date()
    except ValueError:
        raise ZonaInvalida(f"La fecha «{campo}» no es válida.")


def _carteras(valores: Iterable[Any]) -> List[int]:
    salida = set()
    for v in valores or []:
        try:
            n = int(str(v).strip())
        except (TypeError, ValueError):
            raise ZonaInvalida("Hay una cartera que no es válida.")
        if n <= 0:
            raise ZonaInvalida("Hay una cartera que no es válida.")
        salida.add(n)
    return sorted(salida)


def departamentos_validos(valores: Iterable[Any]) -> List[str]:
    deps = []
    for v in valores or []:
        d = normalizar(v)
        if d not in DEPARTAMENTOS:
            raise ZonaInvalida(f"«{v}» no es un departamento del Perú.")
        if d not in deps:
            deps.append(d)
    if not deps:
        raise ZonaInvalida("Selecciona al menos un departamento en el mapa.")
    return deps


def validar_registro(cuerpo: Dict[str, Any], hoy: Optional[date] = None) -> Dict[str, Any]:
    hoy = hoy or date.today()
    deps = departamentos_validos(cuerpo.get("departamentos"))
    todas = bool(cuerpo.get("todas"))
    carteras = [] if todas else _carteras(cuerpo.get("carteras"))
    if not todas and not carteras:
        raise ZonaInvalida("Elige las carteras o marca «Todas las carteras».")
    origen = normalizar(cuerpo.get("origen") or "BANCO")
    if origen not in ORIGENES:
        raise ZonaInvalida("El origen debe ser Banco o Interno.")
    motivo = " ".join(str(cuerpo.get("motivo") or "").split())
    if len(motivo) < 5:
        raise ZonaInvalida("Escribe el motivo (por ejemplo, la orden del banco y su fecha).")
    if len(motivo) > MAX_MOTIVO:
        raise ZonaInvalida(f"El motivo pasa de {MAX_MOTIVO} caracteres.")
    desde = _fecha(cuerpo.get("desde"), "Desde") or hoy
    hasta = _fecha(cuerpo.get("hasta"), "Hasta")
    if hasta is not None and hasta < desde:
        raise ZonaInvalida("«Hasta» no puede ser anterior a «Desde».")
    if hasta is not None and hasta < hoy:
        raise ZonaInvalida("«Hasta» ya pasó: la restricción no regiría.")
    return {"departamentos": deps, "todas": todas, "carteras": carteras, "origen": origen,
            "motivo": motivo, "desde": desde, "hasta": hasta}


def _filas(resultado) -> List[Dict[str, Any]]:
    return [dict(r) for r in resultado.mappings().all()]


def disponible(conn) -> bool:
    """fase19 instalada con la columna AplicaTodas."""
    return conn.execute(text(
        "SELECT CASE WHEN OBJECT_ID('score.vw_ClienteZonaRestringida') IS NULL "
        "OR COL_LENGTH('score.ZonaRestringida', 'AplicaTodas') IS NULL THEN 0 ELSE 1 END"
    )).scalar() == 1


# ------------------------------------------------------------------ lectura
def carteras(conn) -> List[Dict[str, Any]]:
    """Carteras del generador y si ya tienen DEPARTAMENTO (sin él, la restricción no las alcanza todavía)."""
    filas = _filas(conn.execute(text("""
        SELECT e.IdCartera,
               CASE WHEN EXISTS (SELECT 1 FROM score.CampoCartera AS c
                                 WHERE c.IdCartera = e.IdCartera AND c.Campo = 'DEPARTAMENTO') THEN 1 ELSE 0 END AS TieneDepartamento
        FROM score.BaseTrabajoEstado AS e
        ORDER BY e.IdCartera
    """)))
    for f in filas:
        f["IdCartera"] = int(f["IdCartera"])
        f["Nombre"] = NOMBRES_CARTERA.get(f["IdCartera"], f"CARTERA {f['IdCartera']}")
        f["TieneDepartamento"] = bool(f["TieneDepartamento"])
    return filas


def zonas(conn, dias_historial: int = 120) -> List[Dict[str, Any]]:
    """Restricciones activas y las levantadas en los últimos días, con sus carteras."""
    filas = _filas(conn.execute(text("""
        SELECT z.IdZona, z.Nivel, z.Valor, z.Motivo, z.Origen, z.Desde, z.Hasta, z.Activo, z.AplicaTodas,
               z.UsuarioRegistro, z.FechaRegistro, z.UsuarioBaja, z.FechaBaja, z.MotivoBaja,
               CASE WHEN z.Activo = 1 AND z.Desde <= CAST(GETDATE() AS DATE)
                         AND (z.Hasta IS NULL OR z.Hasta >= CAST(GETDATE() AS DATE)) THEN 'VIGENTE'
                    WHEN z.Activo = 1 AND z.Desde > CAST(GETDATE() AS DATE) THEN 'PROGRAMADA'
                    WHEN z.Activo = 1 THEN 'VENCIDA'
                    ELSE 'LEVANTADA' END AS Estado
        FROM score.ZonaRestringida AS z
        WHERE z.Activo = 1 OR z.FechaBaja >= DATEADD(DAY, -:dias, GETDATE())
        ORDER BY z.Activo DESC, z.Valor, z.IdZona DESC
    """), {"dias": int(dias_historial)}))
    por_zona: Dict[int, List[int]] = {}
    for r in conn.execute(text("SELECT IdZona, IdCartera FROM score.ZonaRestringidaCartera")).all():
        por_zona.setdefault(int(r[0]), []).append(int(r[1]))
    for f in filas:
        f["IdZona"] = int(f["IdZona"])
        f["Activo"] = bool(f["Activo"])
        f["AplicaTodas"] = bool(f["AplicaTodas"])
        f["Departamento"] = normalizar(f["Valor"])
        f["Carteras"] = sorted(por_zona.get(f["IdZona"], []))
    return filas


def excluidos(conn) -> Dict[str, Any]:
    """Clientes que hoy quedan fuera, por zona y cartera (y sin duplicar por cartera), con sus PDP vigentes."""
    def _consulta(claves: str) -> List[Dict[str, Any]]:
        return _filas(conn.execute(text(f"""
            WITH z AS (SELECT DISTINCT {claves}, DNI FROM score.vw_ClienteZonaRestringida),
                 p AS ({SQL_PDP_CLIENTE})
            SELECT {", ".join("z." + c.strip() for c in claves.split(","))},
                   COUNT(*) AS Clientes,
                   COUNT(p.DNI) AS ClientesPdp,
                   SUM(p.Pdps) AS Pdps,
                   SUM(p.MontoPdp) AS MontoPdp,
                   SUM(CASE WHEN p.ProximaPdp = CAST(GETDATE() AS DATE) THEN 1 ELSE 0 END) AS ClientesPdpHoy,
                   SUM(CASE WHEN p.ProximaPdp <= DATEADD(DAY, 7, CAST(GETDATE() AS DATE)) THEN 1 ELSE 0 END) AS ClientesPdp7Dias
            FROM z LEFT JOIN p ON p.IdCartera = z.IdCartera AND p.DNI = z.DNI
            GROUP BY {", ".join("z." + c.strip() for c in claves.split(","))}
        """)))
    return {"por_zona": _numeros(_consulta("IdZona, IdCartera")), "por_cartera": _numeros(_consulta("IdCartera"))}


def _numeros(filas: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Decimal -> float y None -> 0 en las métricas, para el JSON."""
    for f in filas:
        for k, v in list(f.items()):
            if k in ("IdZona", "IdCartera"):
                f[k] = int(v)
            elif k.startswith(("Clientes", "Pdps", "Monto", "Con", "Sin", "No")):
                f[k] = float(v or 0) if k.startswith("Monto") else int(v or 0)
    return filas


def cobertura(conn) -> Dict[str, Any]:
    """Qué tan completo está el DEPARTAMENTO en la base de trabajo de cada cartera.
    ConDepartamento: el cliente tiene al menos un valor que es uno de los 25 departamentos.
    NoReconocido: tiene valor, pero ninguno es un departamento (ej. «PROV. CONST. DEL CALLAO»).
    SinDepartamento: la asignación no trae el dato (o la cartera no tiene el campo en el generador)."""
    filas = _numeros(_filas(conn.execute(text(f"""
        WITH dep AS (
            SELECT d.IdCartera, d.DNI,
                   MIN(CASE WHEN x.Departamento IS NULL THEN 1 ELSE 0 END) AS NoReconocido
            FROM score.vw_DatoCliente AS d
            LEFT JOIN (VALUES {VALORES_DEPS}) AS x (Departamento)
                   ON x.Departamento COLLATE {CI_AI} = LTRIM(RTRIM(d.Valor)) COLLATE {CI_AI}
            WHERE d.Campo = 'DEPARTAMENTO' AND NULLIF(LTRIM(RTRIM(d.Valor)), '') IS NOT NULL
            GROUP BY d.IdCartera, d.DNI),
        base AS (SELECT DISTINCT IdCartera, DNI FROM score.vw_BaseTrabajo)
        SELECT b.IdCartera,
               COUNT(*) AS Clientes,
               SUM(CASE WHEN dep.DNI IS NOT NULL AND dep.NoReconocido = 0 THEN 1 ELSE 0 END) AS ConDepartamento,
               SUM(CASE WHEN dep.NoReconocido = 1 THEN 1 ELSE 0 END) AS NoReconocido,
               SUM(CASE WHEN dep.DNI IS NULL THEN 1 ELSE 0 END) AS SinDepartamento
        FROM base AS b
        LEFT JOIN dep ON dep.IdCartera = b.IdCartera AND dep.DNI = b.DNI
        GROUP BY b.IdCartera
        ORDER BY b.IdCartera
    """))))
    valores = _filas(conn.execute(text(f"""
        SELECT TOP (100) d.IdCartera, LTRIM(RTRIM(d.Valor)) AS Valor, COUNT(DISTINCT d.DNI) AS Clientes
        FROM score.vw_DatoCliente AS d
        WHERE d.Campo = 'DEPARTAMENTO' AND NULLIF(LTRIM(RTRIM(d.Valor)), '') IS NOT NULL
          AND NOT EXISTS (SELECT 1 FROM (VALUES {VALORES_DEPS}) AS x (Departamento)
                          WHERE x.Departamento COLLATE {CI_AI} = LTRIM(RTRIM(d.Valor)) COLLATE {CI_AI})
        GROUP BY d.IdCartera, LTRIM(RTRIM(d.Valor))
        ORDER BY Clientes DESC
    """)))
    for v in valores:
        v["IdCartera"], v["Clientes"] = int(v["IdCartera"]), int(v["Clientes"])
    return {"carteras": filas, "no_reconocidos": valores}


def simular(conn, departamentos: List[str], todas: bool, ids_carteras: List[int]) -> List[Dict[str, Any]]:
    """Clientes que saldrían por cartera y departamento (misma comparación que la vista) y cuántos de ellos
    tienen PDP vigente."""
    deps = departamentos_validos(departamentos)
    filtro_cartera = "" if todas else "AND d.IdCartera IN :carteras"
    sql = text(f"""
        WITH d AS (
            SELECT DISTINCT d.IdCartera, d.DNI, UPPER(LTRIM(RTRIM(d.Valor))) COLLATE {CI_AI} AS Valor
            FROM score.vw_DatoCliente AS d
            WHERE d.Campo = 'DEPARTAMENTO'
              AND LTRIM(RTRIM(d.Valor)) COLLATE {CI_AI} IN :deps
              {filtro_cartera}),
        p AS ({SQL_PDP_CLIENTE})
        SELECT d.IdCartera, d.Valor, COUNT(*) AS Clientes, COUNT(p.DNI) AS ClientesPdp, SUM(p.MontoPdp) AS MontoPdp
        FROM d LEFT JOIN p ON p.IdCartera = d.IdCartera AND p.DNI = d.DNI
        GROUP BY d.IdCartera, d.Valor
    """).bindparams(bindparam("deps", expanding=True))
    params: Dict[str, Any] = {"deps": deps}
    if not todas:
        ids = _carteras(ids_carteras)
        if not ids:
            raise ZonaInvalida("Elige las carteras o marca «Todas las carteras».")
        sql = sql.bindparams(bindparam("carteras", expanding=True))
        params["carteras"] = ids
    salida: Dict[tuple, Dict[str, Any]] = {}
    for f in _filas(conn.execute(sql, params)):
        clave = (int(f["IdCartera"]), normalizar(f["Valor"]))
        acc = salida.setdefault(clave, {"Clientes": 0, "ClientesPdp": 0, "MontoPdp": 0.0})
        acc["Clientes"] += int(f["Clientes"] or 0)
        acc["ClientesPdp"] += int(f["ClientesPdp"] or 0)
        acc["MontoPdp"] += float(f["MontoPdp"] or 0)
    return [{"IdCartera": c, "Departamento": d, **v} for (c, d), v in sorted(salida.items())]


# ------------------------------------------------------------------ escritura
def registrar(conn, datos: Dict[str, Any], usuario: str) -> List[Dict[str, Any]]:
    """Un departamento = una restricción. Si ya hay una vigente o programada, se amplía su alcance
    (todas las carteras o las que falten) y conserva sus fechas y motivo."""
    resultado = []
    for dep in datos["departamentos"]:
        existente = conn.execute(text(f"""
            SELECT TOP (1) IdZona, AplicaTodas
            FROM score.ZonaRestringida WITH (UPDLOCK, HOLDLOCK)
            WHERE Activo = 1 AND Nivel = :nivel
              AND Valor COLLATE {CI_AI} = :valor COLLATE {CI_AI}
              AND (Hasta IS NULL OR Hasta >= CAST(GETDATE() AS DATE))
            ORDER BY IdZona DESC
        """), {"nivel": NIVEL, "valor": dep}).mappings().first()
        if existente is None:
            id_zona = int(conn.execute(text("""
                INSERT INTO score.ZonaRestringida (Nivel, Valor, Motivo, Origen, Desde, Hasta, UsuarioRegistro, AplicaTodas)
                OUTPUT INSERTED.IdZona
                VALUES (:nivel, :valor, :motivo, :origen, :desde, :hasta, :usuario, :todas)
            """), {"nivel": NIVEL, "valor": dep, "motivo": datos["motivo"], "origen": datos["origen"],
                   "desde": datos["desde"], "hasta": datos["hasta"], "usuario": usuario[:50],
                   "todas": 1 if datos["todas"] else 0}).scalar())
            accion = "NUEVA"
        else:
            id_zona = int(existente["IdZona"])
            accion = "SIN CAMBIO" if existente["AplicaTodas"] else "AMPLIADA"
            if datos["todas"] and not existente["AplicaTodas"]:
                conn.execute(text("UPDATE score.ZonaRestringida SET AplicaTodas = 1 WHERE IdZona = :id"), {"id": id_zona})
        if not datos["todas"]:
            agregadas = 0
            for c in datos["carteras"]:
                r = conn.execute(text("""
                    INSERT INTO score.ZonaRestringidaCartera (IdZona, IdCartera)
                    SELECT :id, :c
                    WHERE NOT EXISTS (SELECT 1 FROM score.ZonaRestringidaCartera AS x
                                      WHERE x.IdZona = :id AND x.IdCartera = :c)
                """), {"id": id_zona, "c": c})
                agregadas += max(int(r.rowcount or 0), 0)
            if existente is not None and not existente["AplicaTodas"]:
                accion = "AMPLIADA" if agregadas else "SIN CAMBIO"
        resultado.append({"IdZona": id_zona, "Departamento": dep, "Accion": accion})
    return resultado


def levantar(conn, ids_zona: List[int], motivo: str, usuario: str) -> int:
    """Da de baja las restricciones (quedan en el historial). Devuelve cuántas se levantaron."""
    motivo = " ".join(str(motivo or "").split())
    if len(motivo) < 5:
        raise ZonaInvalida("Escribe por qué se levanta la restricción.")
    if len(motivo) > MAX_MOTIVO:
        raise ZonaInvalida(f"El motivo pasa de {MAX_MOTIVO} caracteres.")
    ids = sorted({int(i) for i in ids_zona or [] if str(i).strip().isdigit()})
    if not ids:
        raise ZonaInvalida("No hay restricciones para levantar.")
    r = conn.execute(text("""
        UPDATE score.ZonaRestringida
        SET Activo = 0, UsuarioBaja = :usuario, FechaBaja = SYSDATETIME(), MotivoBaja = :motivo
        WHERE IdZona IN :ids AND Activo = 1
    """).bindparams(bindparam("ids", expanding=True)), {"usuario": usuario[:50], "motivo": motivo, "ids": ids})
    return int(r.rowcount or 0)


# ------------------------------------------------------------------ Excel para revisar
def _filtro_carteras(carteras: Optional[List[int]], alias: str) -> str:
    """None = todas. Los ids son enteros validados: se pueden poner en el texto."""
    if carteras is None:
        return ""
    ids = ",".join(str(int(c)) for c in carteras) or "NULL"
    return f"AND {alias}.IdCartera IN ({ids})"


def _hoja(libro, nombre: str, columnas: List[str], filas: Iterable[Iterable[Any]]) -> int:
    """Hoja en modo de solo escritura (aguanta cientos de miles de filas) con cabecera resaltada."""
    hoja = libro.create_sheet(nombre)
    hoja.freeze_panes = "A2"
    for i, col in enumerate(columnas, start=1):
        hoja.column_dimensions[get_column_letter(i)].width = max(12, min(45, len(col) + 4))
    negrita, fondo = Font(bold=True, color="FFFFFF"), PatternFill("solid", fgColor="12243A")
    cabecera = []
    for col in columnas:
        celda = WriteOnlyCell(hoja, value=col)
        celda.font, celda.fill = negrita, fondo
        cabecera.append(celda)
    hoja.append(cabecera)
    n = 0
    for fila in filas:
        hoja.append(list(fila))
        n += 1
    return n


def excel(conn, permitidas: Optional[List[int]]) -> bytes:
    """Libro para corroborar: resumen por cartera, clientes fuera, sus PDP vigentes y los clientes de la base
    de trabajo sin departamento reconocido. permitidas = None -> todas (visión global)."""
    nombres_cartera = {c["IdCartera"]: c for c in carteras(conn)}
    cob = {f["IdCartera"]: f for f in cobertura(conn)["carteras"]}
    exc = {f["IdCartera"]: f for f in excluidos(conn)["por_cartera"]}
    ids = sorted(set(nombres_cartera) | set(cob) | set(exc))
    if permitidas is not None:
        ids = [i for i in ids if i in set(permitidas)]

    libro = Workbook(write_only=True)
    resumen = []
    for i in ids:
        c, e, k = nombres_cartera.get(i, {}), exc.get(i, {}), cob.get(i, {})
        clientes = k.get("Clientes", 0)
        resumen.append([i, c.get("Nombre", ""), "SI" if c.get("TieneDepartamento") else "NO", clientes,
                        k.get("ConDepartamento", 0), k.get("SinDepartamento", 0), k.get("NoReconocido", 0),
                        round(k.get("ConDepartamento", 0) / clientes, 4) if clientes else None,
                        e.get("Clientes", 0), e.get("ClientesPdp", 0), e.get("MontoPdp", 0.0)])
    _hoja(libro, "Resumen", ["IdCartera", "Cartera", "Campo DEPARTAMENTO", "Clientes base trabajo",
                             "Con departamento", "Sin departamento", "Valor no reconocido", "% con departamento",
                             "Clientes fuera hoy", "Clientes fuera con PDP vigente", "Monto PDP vigente"], resumen)

    filtro_z = _filtro_carteras(None if permitidas is None else ids, "z")
    fuera = conn.execute(text(f"""
        WITH b AS (SELECT IdCartera, DNI, MIN(IdCliente) AS IdCliente FROM score.vw_BaseTrabajo GROUP BY IdCartera, DNI),
             p AS ({SQL_PDP_CLIENTE})
        SELECT z.IdCartera, z.DNI, b.IdCliente, z.Valor, z.IdZona, z.Origen,
               CASE WHEN b.DNI IS NULL THEN 'NO' ELSE 'SI' END AS EnBaseTrabajo,
               ISNULL(p.Pdps, 0) AS Pdps, ISNULL(p.MontoPdp, 0) AS MontoPdp, p.ProximaPdp
        FROM (SELECT DISTINCT IdCartera, DNI, IdZona, Valor, Origen FROM score.vw_ClienteZonaRestringida) AS z
        LEFT JOIN b ON b.IdCartera = z.IdCartera AND b.DNI = z.DNI
        LEFT JOIN p ON p.IdCartera = z.IdCartera AND p.DNI = z.DNI
        WHERE 1 = 1 {filtro_z}
        ORDER BY z.IdCartera, z.Valor, z.DNI
    """))
    _hoja(libro, "Clientes fuera", ["IdCartera", "Cartera", "DNI", "IdCliente", "Departamento", "IdZona", "Origen",
                                    "En base de trabajo", "PDP vigentes", "Monto PDP vigente", "Próxima PDP"],
          ([r.IdCartera, nombres_cartera.get(int(r.IdCartera), {}).get("Nombre", ""), r.DNI, r.IdCliente,
            normalizar(r.Valor), r.IdZona, r.Origen, r.EnBaseTrabajo, r.Pdps, float(r.MontoPdp or 0), r.ProximaPdp]
           for r in fuera))

    pdps = conn.execute(text(f"""
        SELECT p.IdCartera, p.DNI, p.IdCliente, z.Valor, p.FechaCompromiso, p.Monto, p.FechaGenero
        FROM ({SQL_PDP_VIGENTE}) AS p
        INNER JOIN (SELECT DISTINCT IdCartera, DNI, Valor FROM score.vw_ClienteZonaRestringida) AS z
                ON z.IdCartera = p.IdCartera AND z.DNI = p.DNI
        WHERE 1 = 1 {filtro_z}
        ORDER BY p.FechaCompromiso, p.IdCartera, p.DNI
    """))
    _hoja(libro, "PDP vigentes en zona", ["IdCartera", "Cartera", "DNI", "IdCliente", "Departamento",
                                          "Fecha compromiso", "Monto", "Fecha registro PDP"],
          ([r.IdCartera, nombres_cartera.get(int(r.IdCartera), {}).get("Nombre", ""), r.DNI, r.IdCliente,
            normalizar(r.Valor), r.FechaCompromiso, float(r.Monto or 0), r.FechaGenero] for r in pdps))

    con_campo = [i for i in ids if nombres_cartera.get(i, {}).get("TieneDepartamento")]
    sin = conn.execute(text(f"""
        WITH dep AS (
            SELECT d.IdCartera, d.DNI, MIN(CASE WHEN x.Departamento IS NULL THEN 1 ELSE 0 END) AS NoReconocido,
                   MAX(LTRIM(RTRIM(d.Valor))) AS Valor
            FROM score.vw_DatoCliente AS d
            LEFT JOIN (VALUES {VALORES_DEPS}) AS x (Departamento)
                   ON x.Departamento COLLATE {CI_AI} = LTRIM(RTRIM(d.Valor)) COLLATE {CI_AI}
            WHERE d.Campo = 'DEPARTAMENTO' AND NULLIF(LTRIM(RTRIM(d.Valor)), '') IS NOT NULL
            GROUP BY d.IdCartera, d.DNI),
        b AS (SELECT IdCartera, DNI, MIN(IdCliente) AS IdCliente FROM score.vw_BaseTrabajo GROUP BY IdCartera, DNI)
        SELECT b.IdCartera, b.DNI, b.IdCliente,
               CASE WHEN dep.DNI IS NULL THEN 'SIN VALOR' ELSE 'NO RECONOCIDO' END AS Situacion, dep.Valor
        FROM b LEFT JOIN dep ON dep.IdCartera = b.IdCartera AND dep.DNI = b.DNI
        WHERE (dep.DNI IS NULL OR dep.NoReconocido = 1) {_filtro_carteras(con_campo, "b")}
        ORDER BY b.IdCartera, b.DNI
    """))
    _hoja(libro, "Sin departamento", ["IdCartera", "Cartera", "DNI", "IdCliente", "Situación", "Valor en asignación"],
          ([r.IdCartera, nombres_cartera.get(int(r.IdCartera), {}).get("Nombre", ""), r.DNI, r.IdCliente,
            r.Situacion, r.Valor] for r in sin))

    notas = [
        ["Generado", datetime.now().strftime("%d/%m/%Y %H:%M")],
        ["Clientes fuera hoy", "Clientes de la asignación (score.vw_DatoCliente) cuyo DEPARTAMENTO está en una "
                               "restricción vigente para su cartera. El generador de bases los quita."],
        ["En base de trabajo", "SI = el cliente está en la base de trabajo del score (es a quien el generador "
                               "habría llamado)."],
        ["PDP vigente", "Misma regla del generador: compromiso de hoy en adelante, monto > 0 y PAGADO distinto de "
                        "SI / S (SISCOB.COMPROMISO)."],
        ["Sin departamento", "Clientes de la base de trabajo, en carteras que ya tienen el campo DEPARTAMENTO, "
                             "sin valor o con un valor que no es ninguno de los 25 departamentos: una restricción "
                             "no los alcanza. Las carteras sin el campo figuran en Resumen (Campo DEPARTAMENTO = NO)."],
    ]
    _hoja(libro, "Notas", ["Concepto", "Definición"], notas)
    salida = io.BytesIO()
    libro.save(salida)
    return salida.getvalue()

