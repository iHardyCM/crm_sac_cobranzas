# segmentos_service.py
"""Carga de segmentos por cliente que envía el banco aparte (o que arma Biznescob) al generador de bases.

Reglas (diseño del generador, sección 8, aprobadas por Hardy el 14/11/2026):
  - Un dato único por cliente. Si un cliente trae dos valores distintos en una columna, la carga no se hace
    y se muestra el conflicto: no se elige un valor en silencio.
  - La carga es por entidad: el segmento se pega al cliente en todas las carteras de la entidad.
  - La clave del archivo es el código del banco (se traduce a DNI con la asignación vigente, según
    score.EntidadClaveCliente) o el DNI.
  - Una carga nueva con el mismo nombre de segmento reemplaza a la vigente; la anterior queda en el historial.
  - Cada columna queda en el catálogo (score.Campo, origen DATO, grupo Segmentos del banco/propios) y el
    generador la lee por score.vw_DatoCliente, igual que los datos del corte.

Este módulo no depende de la pantalla: lo usa tools/cargar_segmentos.py y lo usará la carga desde el CRM.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from io import BytesIO
import re
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from sqlalchemy import text

FORMATOS = ("TEXTO", "PORCENTAJE")
MAX_EJEMPLOS = 20


@dataclass
class ColumnaSegmento:
    columna: str                 # nombre en el archivo
    campo: str                   # código en score.Campo
    etiqueta: str
    abreviatura: str             # para el nombre del archivo exportado (máx. 12)
    descripcion: str
    formato: str = "TEXTO"       # TEXTO tal cual · PORCENTAJE (0.97 → "97%")
    orden_valores: Optional[str] = None


@dataclass
class DefinicionCarga:
    entidad: str                 # código de ControlCobranza.bl.Entidad (p. ej. MIBANCO)
    segmento: str                # nombre de la carga: la nueva con el mismo nombre reemplaza a la vigente
    columna_clave: str
    tipo_clave: str              # CODIGO_BANCO · DNI
    columnas: List[ColumnaSegmento]
    fuente: str = "BANCO"        # BANCO · BIZNESCOB
    hoja: Optional[str] = None   # None = primera hoja
    filtros: Dict[str, List[str]] = field(default_factory=dict)   # columna → valores que se quedan
    columna_periodo: Optional[str] = None
    periodo: Optional[str] = None                                 # AAAAMM si el archivo no lo trae


class CargaInvalida(ValueError):
    pass


# ---------------------------------------------------------------- lectura y preparación (sin base de datos)
def _norm(nombre: Any) -> str:
    return re.sub(r"\s+", " ", str(nombre or "")).strip().upper()


def _columna_real(df: pd.DataFrame, nombre: str) -> str:
    reales = {_norm(c): c for c in df.columns}
    if _norm(nombre) not in reales:
        raise CargaInvalida(f"El archivo no tiene la columna '{nombre}'. Columnas: {', '.join(map(str, df.columns))}")
    return reales[_norm(nombre)]


def leer_archivo(contenido: bytes, archivo: str, hoja: Optional[str] = None) -> pd.DataFrame:
    motor = "pyxlsb" if archivo.lower().endswith(".xlsb") else None
    if archivo.lower().endswith(".csv"):
        df = pd.read_csv(BytesIO(contenido), dtype=str, encoding="utf-8-sig", sep=None, engine="python")
    else:
        df = pd.read_excel(BytesIO(contenido), sheet_name=hoja or 0, dtype=str, engine=motor)
    df.columns = [str(c).strip() for c in df.columns]
    return df.where(pd.notna(df), None)


VACIOS = {"NAN", "NONE", "NAT", "NULL", "<NA>"}


def _texto(valor: Any) -> Optional[str]:
    """Texto limpio; vacío → None. pandas puede dejar las celdas vacías como "nan" al leer como texto."""
    if valor is None:
        return None
    t = re.sub(r"\s+", " ", str(valor)).strip()
    return None if not t or t.upper() in VACIOS else t


def periodo_aaaamm(valor: Any) -> Optional[str]:
    """AAAAMM desde 202611, 202611.0, 2026-11-15, 2026-11-15 00:00:00, 15/11/2026 o 2026/11."""
    t = _texto(valor)
    if t is None:
        return None
    m = re.fullmatch(r"(20\d{2})(0[1-9]|1[0-2])(\.0+)?", t)
    if m:
        return m.group(1) + m.group(2)
    m = re.match(r"^(20\d{2})[-/](\d{1,2})(?:[-/]\d{1,2})?(?:[ T].*)?$", t)
    if m and 1 <= int(m.group(2)) <= 12:
        return f"{m.group(1)}{int(m.group(2)):02d}"
    m = re.match(r"^\d{1,2}[-/](\d{1,2})[-/](20\d{2})(?:[ T].*)?$", t)
    if m and 1 <= int(m.group(1)) <= 12:
        return f"{m.group(2)}{int(m.group(1)):02d}"
    return None


def clave_codigo_banco(valor: Any) -> Optional[str]:
    """Código de cliente del banco como entero en texto (MiBanco lo guarda como float: 10342994.0 → 10342994)."""
    t = _texto(valor)
    if t is None:
        return None
    try:
        return str(int(float(t)))
    except ValueError:
        return None


def clave_dni(valor: Any) -> Optional[str]:
    """DNI como texto de 8 dígitos. Excel guarda el DNI como número y pierde el cero de la izquierda
    (01234567 → 1234567 o 1234567.0): se completa a 8. Otros documentos (CE, RUC, con letras) quedan tal cual."""
    t = _texto(valor)
    if t is None:
        return None
    m = re.fullmatch(r"(\d+)(\.0+)?", t)
    if m:
        return m.group(1).zfill(8)
    return t.upper()


def formatear(valor: Any, formato: str) -> Optional[str]:
    t = _texto(valor)
    if t is None or formato == "TEXTO":
        return t
    if formato == "PORCENTAJE":
        try:
            n = float(t.replace("%", ""))
        except ValueError:
            return t
        if "%" in t:          # ya viene como "97%"
            n = n / 100
        pct = round(n * 100, 2)
        return f"{int(pct)}%" if pct == int(pct) else f"{pct}%"
    raise CargaInvalida(f"Formato no soportado: {formato}")


def preparar(df: pd.DataFrame, d: DefinicionCarga) -> Dict[str, Any]:
    """Filtra, normaliza la clave y arma un valor por cliente y columna. Devuelve también los conflictos."""
    if d.tipo_clave not in ("CODIGO_BANCO", "DNI"):
        raise CargaInvalida("tipo_clave debe ser CODIGO_BANCO o DNI.")
    for c in d.columnas:
        if c.formato not in FORMATOS:
            raise CargaInvalida(f"Formato no soportado en {c.columna}: {c.formato}")
        if len(c.abreviatura) > 12:
            raise CargaInvalida(f"La abreviatura de {c.campo} pasa de 12 caracteres.")
    filas_archivo = int(len(df))
    for col, valores in d.filtros.items():
        real = _columna_real(df, col)
        permitidos = {_norm(v) for v in valores}
        df = df[df[real].map(_norm).isin(permitidos)]
    filas_filtradas = int(len(df))

    clave_real = _columna_real(df, d.columna_clave)
    reales = {c.campo: _columna_real(df, c.columna) for c in d.columnas}
    normalizar_clave = clave_codigo_banco if d.tipo_clave == "CODIGO_BANCO" else clave_dni

    periodo = d.periodo
    if d.columna_periodo:
        crudos = [v for v in df[_columna_real(df, d.columna_periodo)] if _texto(v) is not None]
        malos = sorted({str(v) for v in crudos if periodo_aaaamm(v) is None})[:5]
        if malos:
            raise CargaInvalida(f"No se reconoce el periodo en {d.columna_periodo}: {malos}. Usa AAAAMM o una fecha.")
        periodos = {periodo_aaaamm(v) for v in crudos}
        if len(periodos) != 1:
            raise CargaInvalida(f"El archivo trae más de un periodo en {d.columna_periodo}: {sorted(periodos)}. "
                                "Filtra las filas o escribe el periodo.")
        periodo = periodos.pop()
    if not periodo or not re.fullmatch(r"20\d{2}(0[1-9]|1[0-2])", str(periodo)):
        raise CargaInvalida(f"Periodo inválido o faltante: {periodo!r} (AAAAMM).")

    valores: Dict[str, Dict[str, Optional[str]]] = {}
    conflictos: List[Dict[str, Any]] = []
    sin_clave = 0
    for _, fila in df.iterrows():
        clave = normalizar_clave(fila[clave_real])
        if not clave:
            sin_clave += 1
            continue
        actual = valores.setdefault(clave, {})
        for c in d.columnas:
            v = formatear(fila[reales[c.campo]], c.formato)
            if c.campo in actual and actual[c.campo] != v:
                conflictos.append({"clave": clave, "campo": c.campo, "valores": sorted({str(actual[c.campo]), str(v)})})
            else:
                actual[c.campo] = v

    distintos = {}
    for c in d.columnas:
        cuenta: Dict[str, int] = {}
        for vals in valores.values():
            v = vals.get(c.campo)
            if v is not None:
                cuenta[v] = cuenta.get(v, 0) + 1
        distintos[c.campo] = dict(sorted(cuenta.items(), key=lambda x: -x[1]))
    return {"periodo": str(periodo), "filas_archivo": filas_archivo, "filas_filtradas": filas_filtradas,
            "sin_clave": sin_clave, "valores": valores, "conflictos": conflictos, "distintos": distintos}


# ---------------------------------------------------------------- base de datos
_OBJETO = re.compile(r"^[A-Za-z0-9_]+\.[A-Za-z0-9_]+\.[A-Za-z0-9_]+$")
_COLUMNA = re.compile(r"^[A-Za-z0-9_]+$")


def _entidad(conn, codigo: str) -> Tuple[int, List[int]]:
    fila = conn.execute(text("SELECT IdEntidad FROM ControlCobranza.bl.Entidad WHERE Codigo = :c"), {"c": codigo}).first()
    if not fila:
        raise CargaInvalida(f"No existe la entidad {codigo} en ControlCobranza.bl.Entidad.")
    carteras = [int(r[0]) for r in conn.execute(text(
        "SELECT IdCartera FROM ControlCobranza.bl.EntidadCartera WHERE IdEntidad = :e ORDER BY IdCartera"),
        {"e": int(fila[0])})]
    return int(fila[0]), carteras


def _traduccion(conn, id_entidad: int) -> Dict[str, set]:
    """Código del banco → DNI(s), con las asignaciones registradas en score.EntidadClaveCliente."""
    mapa: Dict[str, set] = {}
    objetos = conn.execute(text("""
        SELECT Objeto, ColumnaCodigo, ColumnaDNI FROM score.EntidadClaveCliente
        WHERE IdEntidad = :e AND Activo = 1"""), {"e": id_entidad}).fetchall()
    if not objetos:
        raise CargaInvalida("La entidad no tiene asignación registrada en score.EntidadClaveCliente.")
    for objeto, col_cod, col_dni in objetos:
        if not (_OBJETO.match(objeto) and _COLUMNA.match(col_cod) and _COLUMNA.match(col_dni)):
            raise CargaInvalida(f"Nombre de objeto o columna no válido en score.EntidadClaveCliente: {objeto}")
        partes = ".".join(f"[{p}]" for p in objeto.split("."))
        filas = conn.execute(text(f"""
            SELECT DISTINCT CONVERT(VARCHAR(30), TRY_CONVERT(BIGINT, TRY_CONVERT(FLOAT, [{col_cod}]))) AS Codigo,
                   LTRIM(RTRIM(CONVERT(VARCHAR(20), [{col_dni}]))) AS DNI
            FROM {partes} WITH (NOLOCK)
            WHERE [{col_cod}] IS NOT NULL AND [{col_dni}] IS NOT NULL""")).fetchall()
        for cod, dni in filas:
            if cod and dni:
                mapa.setdefault(str(cod), set()).add(str(dni))
    return mapa


def _cruce_score(conn, carteras: List[int], dnis: set) -> tuple:
    """Cuántos clientes del archivo están en la base del score de cada cartera de la entidad
    (score.BaseTrabajoCliente). El generador solo muestra el segmento a esos clientes."""
    if not carteras or not dnis:
        return 0, {}
    marcas = ", ".join(f":c{i}" for i in range(len(carteras)))
    filas = conn.execute(text(f"""
        SELECT DISTINCT IdCartera, LTRIM(RTRIM(CONVERT(VARCHAR(20), DNI))) AS DNI
        FROM score.BaseTrabajoCliente WHERE IdCartera IN ({marcas})"""),
        {f"c{i}": c for i, c in enumerate(carteras)}).fetchall()
    por_cartera: Dict[int, int] = {}
    vistos = set()
    for idcartera, dni in filas:
        if dni in dnis:
            por_cartera[int(idcartera)] = por_cartera.get(int(idcartera), 0) + 1
            vistos.add(dni)
    return len(vistos), dict(sorted(por_cartera.items()))


def previsualizar(conn, d: DefinicionCarga, df: pd.DataFrame) -> Dict[str, Any]:
    prep = preparar(df, d)
    id_entidad, carteras = _entidad(conn, d.entidad)
    filas: List[Dict[str, Any]] = []
    sin_cruce: List[str] = []
    conflictos = list(prep["conflictos"])
    if d.tipo_clave == "CODIGO_BANCO":
        mapa = _traduccion(conn, id_entidad)
        por_dni: Dict[str, str] = {}
        for codigo, vals in prep["valores"].items():
            dnis = mapa.get(codigo)
            if not dnis:
                sin_cruce.append(codigo)
                continue
            if len(dnis) > 1:
                conflictos.append({"clave": codigo, "campo": "DNI", "valores": sorted(dnis)})
                continue
            dni = next(iter(dnis))
            if dni in por_dni and por_dni[dni] != codigo:
                # Dos códigos del banco con el mismo DNI: válido solo si traen los mismos valores
                otro = prep["valores"][por_dni[dni]]
                if otro != vals:
                    conflictos.append({"clave": f"{por_dni[dni]} / {codigo}", "campo": "DNI " + dni,
                                       "valores": ["valores distintos para el mismo DNI"]})
                continue
            por_dni[dni] = codigo
            for c in d.columnas:
                if vals.get(c.campo) is not None:
                    filas.append({"Campo": c.campo, "CodigoBanco": codigo, "DNI": dni, "Valor": vals[c.campo]})
    else:
        for dni, vals in prep["valores"].items():
            for c in d.columnas:
                if vals.get(c.campo) is not None:
                    filas.append({"Campo": c.campo, "CodigoBanco": None, "DNI": dni, "Valor": vals[c.campo]})
    dnis = {f["DNI"] for f in filas}
    clientes = len(dnis)
    en_score, por_cartera = _cruce_score(conn, carteras, dnis)
    errores_catalogo = validar_catalogo(conn, d, id_entidad)
    return {
        "errores_catalogo": errores_catalogo,
        "entidad": d.entidad, "id_entidad": id_entidad, "carteras": carteras, "segmento": d.segmento,
        "periodo": prep["periodo"], "filas_archivo": prep["filas_archivo"], "filas_filtradas": prep["filas_filtradas"],
        "claves": len(prep["valores"]), "sin_clave": prep["sin_clave"], "clientes": clientes,
        "codigos_sin_cruce": len(sin_cruce), "ejemplos_sin_cruce": sin_cruce[:MAX_EJEMPLOS],
        "conflictos": len(conflictos), "ejemplos_conflicto": conflictos[:MAX_EJEMPLOS],
        "distintos": prep["distintos"], "filas": filas,
        "en_score": en_score, "por_cartera": por_cartera,
    }


def cargar(conn, d: DefinicionCarga, df: pd.DataFrame, archivo: str, usuario: str) -> Dict[str, Any]:
    """Escribe la carga dentro de la transacción de conn (usar engine.begin()). Falla si hay conflictos."""
    p = previsualizar(conn, d, df)
    if p["errores_catalogo"]:
        raise CargaInvalida(" ".join(p["errores_catalogo"]))
    if p["conflictos"]:
        raise CargaInvalida(f"Hay {p['conflictos']} conflicto(s): corrige el archivo antes de cargar. "
                            f"Ejemplos: {p['ejemplos_conflicto'][:5]}")
    if not p["filas"]:
        raise CargaInvalida("No quedó ningún cliente para cargar.")
    grupo = "SEGMENTO_BANCO" if d.fuente == "BANCO" else "SEGMENTO_PROPIO"
    fuente_txt = (f"score.SegmentoCliente ← carga \"{d.segmento}\" de {d.entidad} "
                  f"({'archivo del banco' if d.fuente == 'BANCO' else 'Biznescob'})")
    for c in d.columnas:
        conn.execute(text("""
            MERGE score.Campo AS t
            USING (SELECT :codigo AS Codigo) AS s ON t.Codigo = s.Codigo
            WHEN MATCHED THEN UPDATE SET Etiqueta = :etiqueta, Abreviatura = :abrev, Grupo = :grupo, TipoFiltro = 'LISTA',
                 Origen = 'DATO', ColumnaOrigen = NULL, OrdenValores = :orden, Descripcion = :descr, Fuente = :fuente,
                 Actualizacion = N'Cuando llega el archivo (carga de segmentos)', Activo = 1
            WHEN NOT MATCHED THEN INSERT (Codigo, Etiqueta, Abreviatura, Grupo, TipoFiltro, Origen, ColumnaOrigen,
                 OrdenValores, Descripcion, Fuente, Actualizacion)
                 VALUES (:codigo, :etiqueta, :abrev, :grupo, 'LISTA', 'DATO', NULL, :orden, :descr, :fuente,
                         N'Cuando llega el archivo (carga de segmentos)');"""),
            {"codigo": c.campo, "etiqueta": c.etiqueta, "abrev": c.abreviatura, "grupo": grupo,
             "orden": c.orden_valores, "descr": c.descripcion, "fuente": fuente_txt})
        for idcartera in p["carteras"]:
            conn.execute(text("""
                MERGE score.CampoCartera AS t
                USING (SELECT :campo AS Campo, :idcartera AS IdCartera) AS s
                ON t.Campo = s.Campo AND t.IdCartera = s.IdCartera
                WHEN MATCHED THEN UPDATE SET Nivel = 'CLIENTE', Tabla = N'score.SegmentoCliente', Columna = :columna
                WHEN NOT MATCHED THEN INSERT (Campo, IdCartera, Nivel, Tabla, Columna)
                     VALUES (:campo, :idcartera, 'CLIENTE', N'score.SegmentoCliente', :columna);"""),
                {"campo": c.campo, "idcartera": idcartera, "columna": f"{d.segmento} · {c.columna}"[:128]})

    conn.execute(text("""
        UPDATE score.SegmentoCarga SET Estado = 'REEMPLAZADA'
        WHERE IdEntidad = :e AND Segmento = :s AND Estado = 'VIGENTE'"""), {"e": p["id_entidad"], "s": d.segmento})
    id_carga = int(conn.execute(text("""
        INSERT INTO score.SegmentoCarga (IdEntidad, Fuente, Segmento, Periodo, Archivo, ColumnaClave, TipoClave,
               FilasArchivo, ClientesCargados, CodigosSinCruce, Estado, Usuario)
        OUTPUT INSERTED.IdCarga
        VALUES (:e, :f, :s, :p, :a, :cc, :tc, :fa, :cl, :sc, 'VIGENTE', :u)"""),
        {"e": p["id_entidad"], "f": d.fuente, "s": d.segmento, "p": p["periodo"], "a": archivo[:260],
         "cc": d.columna_clave, "tc": d.tipo_clave, "fa": p["filas_archivo"], "cl": p["clientes"],
         "sc": p["codigos_sin_cruce"], "u": usuario}).scalar())
    filas = [{"IdCarga": id_carga, **f} for f in p["filas"]]
    conn.execute(text("""INSERT INTO score.SegmentoCliente (IdCarga, Campo, CodigoBanco, DNI, Valor)
                         VALUES (:IdCarga, :Campo, :CodigoBanco, :DNI, :Valor)"""), filas)
    resultado = {k: v for k, v in p.items() if k != "filas"}
    resultado.update({"id_carga": id_carga, "filas_insertadas": len(filas)})
    return resultado


# ---------------------------------------------------------------- pantalla de carga (CRM)
CODIGO_CAMPO = re.compile(r"^[A-Z][A-Z0-9_]{2,59}$")
PERIODO = re.compile(r"^20\d{2}(0[1-9]|1[0-2])$")
MAX_VALORES_ANALISIS = 12
MAX_VALORES_FILTRO = 200


def hojas_archivo(contenido: bytes, archivo: str) -> List[str]:
    if archivo.lower().endswith(".csv"):
        return []
    motor = "pyxlsb" if archivo.lower().endswith(".xlsb") else None
    return [str(h) for h in pd.ExcelFile(BytesIO(contenido), engine=motor).sheet_names]


def codigo_sugerido(columna: str) -> str:
    t = re.sub(r"[^A-Z0-9]+", "_", _norm(columna).encode("ascii", "ignore").decode()).strip("_")
    if not t or not t[0].isalpha():
        t = "SEG_" + t
    return t[:60]


def analizar_archivo(contenido: bytes, archivo: str, hoja: Optional[str] = None) -> Dict[str, Any]:
    """Columnas del archivo con sus valores más frecuentes, para configurar la carga en pantalla."""
    hojas = hojas_archivo(contenido, archivo)
    if hoja and hojas and hoja not in hojas:
        raise CargaInvalida(f"El archivo no tiene la hoja {hoja}.")
    df = leer_archivo(contenido, archivo, hoja)
    columnas = []
    for col in df.columns:
        serie = df[col].map(_texto)
        conteo = serie.dropna().value_counts()
        columnas.append({
            "nombre": col,
            "distintos": int(conteo.shape[0]),
            "vacios": int(serie.isna().sum()),
            "valores": [{"valor": str(v), "filas": int(n)} for v, n in conteo.head(MAX_VALORES_ANALISIS).items()],
            "valores_filtro": [str(v) for v in conteo.head(MAX_VALORES_FILTRO).index] if conteo.shape[0] <= MAX_VALORES_FILTRO else [],
            "codigo_sugerido": codigo_sugerido(col),
        })
    return {"archivo": archivo, "hojas": hojas, "hoja": hoja or (hojas[0] if hojas else None),
            "filas": int(len(df)), "columnas": columnas}


def definicion_desde_dict(datos: Dict[str, Any]) -> DefinicionCarga:
    """Valida la configuración que manda la pantalla (no se confía en el navegador)."""
    def texto(clave, largo, obligatorio=True):
        v = _texto(datos.get(clave))
        if obligatorio and not v:
            raise CargaInvalida(f"Falta {clave}.")
        if v and len(v) > largo:
            raise CargaInvalida(f"{clave} pasa de {largo} caracteres.")
        return v

    columnas = []
    vistos = set()
    for c in datos.get("columnas") or []:
        campo = (_texto(c.get("campo")) or "").upper()
        if not CODIGO_CAMPO.match(campo):
            raise CargaInvalida(f"Código inválido: {campo!r}. Usa mayúsculas, números y _ (3 a 60, empieza con letra).")
        if campo in vistos:
            raise CargaInvalida(f"El código {campo} está repetido.")
        vistos.add(campo)
        abrev = (_texto(c.get("abreviatura")) or "").upper()
        if not re.fullmatch(r"[A-Z0-9]{2,12}", abrev):
            raise CargaInvalida(f"Abreviatura inválida en {campo}: 2 a 12 letras o números.")
        etiqueta = _texto(c.get("etiqueta")) or campo
        descripcion = _texto(c.get("descripcion")) or etiqueta
        formato = (_texto(c.get("formato")) or "TEXTO").upper()
        orden = _texto(c.get("orden_valores"))
        columnas.append(ColumnaSegmento(
            columna=texto_c(c, "columna"), campo=campo, etiqueta=etiqueta[:100], abreviatura=abrev,
            descripcion=descripcion[:500], formato=formato, orden_valores=orden[:1000] if orden else None))
    if not columnas:
        raise CargaInvalida("Marca al menos una columna para cargar.")
    filtros = {}
    for f in datos.get("filtros") or []:
        col = _texto(f.get("columna"))
        valores = [str(v) for v in (f.get("valores") or []) if _texto(v)]
        if col and valores:
            filtros[col] = valores
    tipo_clave = (_texto(datos.get("tipo_clave")) or "").upper()
    fuente = (_texto(datos.get("fuente")) or "BANCO").upper()
    if fuente not in ("BANCO", "BIZNESCOB"):
        raise CargaInvalida("La fuente debe ser BANCO o BIZNESCOB.")
    periodo = _texto(datos.get("periodo"))
    columna_periodo = _texto(datos.get("columna_periodo"))
    if not columna_periodo and not (periodo and PERIODO.match(periodo)):
        raise CargaInvalida("Indica el periodo (AAAAMM) o la columna del archivo que lo trae.")
    return DefinicionCarga(
        entidad=texto("entidad", 30).upper(), segmento=texto("segmento", 100), columna_clave=texto("columna_clave", 128),
        tipo_clave=tipo_clave, columnas=columnas, fuente=fuente, hoja=_texto(datos.get("hoja")),
        filtros=filtros, columna_periodo=columna_periodo, periodo=None if columna_periodo else periodo)


def texto_c(c: Dict[str, Any], clave: str) -> str:
    v = _texto(c.get(clave))
    if not v:
        raise CargaInvalida(f"Falta {clave} en una columna.")
    return v


def validar_catalogo(conn, d: DefinicionCarga, id_entidad: int) -> List[str]:
    """Errores que impiden cargar: un código que ya es de otro dato del generador, una abreviatura de otro campo,
    o un código que ya llena otro segmento vigente de la misma entidad (el cliente tendría dos valores)."""
    errores = []
    for c in d.columnas:
        existe = conn.execute(text("SELECT Origen, Fuente FROM score.Campo WHERE Codigo = :c"), {"c": c.campo}).first()
        if existe and not str(existe[1] or "").startswith("score.SegmentoCliente"):
            errores.append(f"{c.campo} ya existe en el generador con otro origen ({existe[1]}): usa otro código.")
        otra = conn.execute(text("""
            SELECT TOP 1 Codigo FROM score.Campo WHERE Abreviatura = :a AND Codigo <> :c"""),
            {"a": c.abreviatura, "c": c.campo}).scalar()
        if otra:
            errores.append(f"La abreviatura {c.abreviatura} ya la usa {otra}: elige otra (va en el nombre del archivo).")
        otro_segmento = conn.execute(text("""
            SELECT TOP 1 k.Segmento FROM score.SegmentoCarga AS k
            INNER JOIN score.SegmentoCliente AS s ON s.IdCarga = k.IdCarga
            WHERE k.Estado = 'VIGENTE' AND k.IdEntidad = :e AND s.Campo = :c AND k.Segmento <> :s"""),
            {"e": id_entidad, "c": c.campo, "s": d.segmento}).scalar()
        if otro_segmento:
            errores.append(f"{c.campo} ya lo llena el segmento vigente \"{otro_segmento}\": usa otro código o el mismo nombre de segmento.")
    return errores


def listar_entidades(conn) -> List[Dict[str, Any]]:
    filas = conn.execute(text("""
        SELECT e.IdEntidad, e.Codigo, ec.IdCartera,
               CASE WHEN EXISTS (SELECT 1 FROM score.EntidadClaveCliente AS k
                                 WHERE k.IdEntidad = e.IdEntidad AND k.Activo = 1) THEN 1 ELSE 0 END AS ConTraduccion
        FROM ControlCobranza.bl.Entidad AS e
        LEFT JOIN ControlCobranza.bl.EntidadCartera AS ec ON ec.IdEntidad = e.IdEntidad
        ORDER BY e.Codigo, ec.IdCartera""")).fetchall()
    salida: Dict[int, Dict[str, Any]] = {}
    for id_e, codigo, idcartera, traduccion in filas:
        e = salida.setdefault(int(id_e), {"id": int(id_e), "codigo": str(codigo), "carteras": [],
                                          "codigo_banco": bool(traduccion)})
        if idcartera is not None:
            e["carteras"].append(int(idcartera))
    return list(salida.values())


def listar_cargas(conn, limite: int = 100) -> List[Dict[str, Any]]:
    filas = conn.execute(text("""
        SELECT TOP (:n) k.IdCarga, e.Codigo AS Entidad, k.Fuente, k.Segmento, k.Periodo, k.Archivo, k.ColumnaClave,
               k.TipoClave, k.FilasArchivo, k.ClientesCargados, k.CodigosSinCruce, k.Estado, k.Usuario, k.FechaCarga,
               (SELECT COUNT(DISTINCT s.Campo) FROM score.SegmentoCliente AS s WHERE s.IdCarga = k.IdCarga) AS Campos
        FROM score.SegmentoCarga AS k
        LEFT JOIN ControlCobranza.bl.Entidad AS e ON e.IdEntidad = k.IdEntidad
        ORDER BY k.IdCarga DESC"""), {"n": max(1, min(int(limite), 500))}).mappings().all()
    return [{k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in f.items()} for f in filas]


def anular_carga(conn, id_carga: int) -> bool:
    r = conn.execute(text("UPDATE score.SegmentoCarga SET Estado = 'ANULADA' WHERE IdCarga = :id AND Estado = 'VIGENTE'"),
                     {"id": int(id_carga)})
    return bool(r.rowcount)
