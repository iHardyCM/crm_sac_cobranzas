"""Reglas del generador de bases que no dependen de la base de datos.

Arma el SQL de la consulta a partir de la receta (filtros + condiciones del día) y
el nombre del archivo exportado. Todo filtro pasa por el catálogo (score.Campo):
un campo que no está en el catálogo, o que la cartera no tiene, se rechaza. Los
valores siempre viajan como parámetros; los nombres de columna salen del catálogo
y además se validan contra una lista fija de columnas de score.vw_BaseTrabajo.

Diseño: claude/diseno_generador_bases.md y claude/diseno_base_trabajo.md (proyecto crm_cobranzas).
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

# Columnas de score.vw_BaseTrabajo que un campo de origen TRABAJO puede usar.
COLUMNAS_VISTA = frozenset({
    "Score", "Tramo", "OrdenCliente", "Descartado", "PrioridadColor", "Osiptel", "Whatsapp", "Timbra",
    "Operador", "EsEmpresa", "N_DNI_Comparten", "Capital", "RangoCapital", "Cuentas", "Meta",
    "GestionesHumanasMes", "GestionesMaquinaMes", "ContactoDirectoMes", "FechaUltimoCef", "PdpGeneradasMes",
    # fase 7 · gestión del cliente (score.GestionCliente)
    "Condicion", "MgContacto", "MgIndicador", "MgFechaTramo", "UgContacto", "UgIndicador", "UgFechaTramo",
    "Cobertura", "Frecuencia", "FrecuenciaHumana", "GestionesHumanasSiscob", "EstadoPdp", "UltCefTramo",
    "EstadoSeguimiento",
    # fase 7 · gestión del teléfono (score.GestionTelefono) y tramos del score (score.Caracteristicas)
    "MgTelMes", "UgTelMes", "MgTel6m", "UgTel6m", "UltGestionTelTramo", "GestionesTelMes", "GestionesTel6m",
    "EquivocadosTel6m", "OrigenDato", "FuenteDato", "AntiguedadDato", "TipoLinea", "Relacion", "TramoUltCefTel",
    "TramoTasaCef90", "TramoIntentos30", "TramoUltIntento", "TramoNoConecta90",
    # fase 16 · recupero: PDP de meses anteriores y antigüedad del último seguimiento
    "EstadoPdpAnterior", "PdpAnteriorMes", "SeguimientoMes",
    # fase 17 · SAC del día (Compartamos vigente)
    "CapitalSac", "RangoCapitalSac", "EnSac",
})
# Columnas BIT de la vista (filtro SI/NO)
COLUMNAS_BIT = frozenset({"Descartado", "EsEmpresa", "ContactoDirectoMes", "Cobertura"})
# Datos por cliente o cuenta: los del corte (score.BaseTrabajoDato) y los segmentos cargados
# (score.SegmentoCliente, vigentes, pegados a cada cartera de la entidad). Fase 8, 16/11/2026.
FUENTE_DATO = "score.vw_DatoCliente"
# Grupos que se cuentan por teléfono (el resto, por cliente)
GRUPOS_TELEFONO = frozenset({"SCORE", "TELEFONO", "GESTION_TELEFONO"})

CANALES = {"PRED": "Predictivo", "PREVIEW": "Preview", "IVR": "IVR / TTS", "SMS": "SMS", "OTRO": "Otro"}
# Canales del marcador (24/11/2026, Hardy): para "ya enviado hoy" predictivo y preview son el mismo grupo
CANALES_MARCADOR = ("PRED", "PREVIEW")
SIN_DATO = "SIN_DATO"
MAX_VALORES = 500
LARGO_NOMBRE = 40   # largo máximo por defecto del nombre (diseño, sección 7); el código nunca se recorta

# Condiciones del día: se consultan en vivo, no salen del score. Cada una admite QUITAR, SOLO o INDIFERENTE.
CONDICIONES: Dict[str, Dict[str, str]] = {
    "CEF_HOY": {"etiqueta": "Contacto directo hoy", "abrev": "CEF", "nivel": "CLIENTE",
                "descripcion": "Gestión de hoy con titular o tercero con acuerdo (CEF) en esta cartera.",
                "fuente": "siscob.dbo.gestion + score.IndicadorResultado"},
    "PDP_CREADA_HOY": {"etiqueta": "PDP creada hoy", "abrev": "PDPH", "nivel": "CLIENTE",
                       "descripcion": "Promesa de pago registrada hoy en esta cartera.",
                       "fuente": "siscob.dbo.COMPROMISO (FechaGenero)"},
    "PDP_VIGENTE": {"etiqueta": "PDP vigente", "abrev": "PDPV", "nivel": "CLIENTE",
                    "descripcion": "Promesa con fecha de compromiso desde hoy y sin pagar (PAGADO distinto de SI/S).",
                    "fuente": "siscob.dbo.COMPROMISO"},
    "PAGO_HOY": {"etiqueta": "Pago registrado hoy", "abrev": "PAG", "nivel": "CLIENTE",
                 "descripcion": "Promesa marcada como pagada (SI/S) con fecha de pago de hoy en SISCOB.",
                 "fuente": "siscob.dbo.COMPROMISO (Pagado, FechaPago)"},
    "EQUIVOCADO_HOY": {"etiqueta": "Equivocado hoy", "abrev": "EQ", "nivel": "TELEFONO",
                       "descripcion": "El teléfono fue tipificado hoy como equivocado para este cliente.",
                       "fuente": "siscob.dbo.gestion + score.IndicadorResultado"},
    "ENVIADO_HOY": {"etiqueta": "Ya enviado hoy (mismo canal)", "abrev": "ENV", "nivel": "TELEFONO",
                    "descripcion": "El teléfono ya salió hoy en otra base del mismo canal y cartera (predictivo y preview cuentan como el mismo canal: marcador).",
                    "fuente": "score.Base / score.BaseDetalle"},
}
MODOS_CONDICION = ("QUITAR", "SOLO", "INDIFERENTE")

# Fase 12 (20/11/2026): las condiciones del día se leen de SISCOB una vez por cartera y se guardan en
# score.CondicionDia; la vista previa reutiliza esa foto hasta SEGUNDOS_CACHE_CONDICIONES. Medido: leerlas en
# cada clic costaba 8 a 11 s en la 112. La base que se GENERA las sigue leyendo en vivo (sql_seleccion).
# ENVIADO_HOY lee score.Base (local y barato) y depende del canal: sigue en vivo.
SEGUNDOS_CACHE_CONDICIONES = 120
CONDICIONES_CACHE = frozenset(c for c in CONDICIONES if c != "ENVIADO_HOY")


class RecetaInvalida(ValueError):
    """Error de la receta que se muestra al usuario tal cual (400)."""


@dataclass
class CampoMeta:
    codigo: str
    etiqueta: str
    abreviatura: Optional[str]
    grupo: str
    tipo_filtro: str
    origen: str
    columna: Optional[str]
    disponible: bool = True


@dataclass
class ConsultaSql:
    ctes: List[str]
    pasos: List[Tuple[str, str]]   # (etiqueta, condición SQL sobre alias t)
    params: Dict[str, Any] = field(default_factory=dict)
    campos_paso: List[Optional[str]] = field(default_factory=list)   # campo de cada paso (None: no es filtro)
    # Carteras reales que se leen. Una sola en lo normal; varias en una cartera combinada (p. ej. Vigente IND + CCM,
    # score.CarteraCombinada): cada fila conserva su cartera y un mismo cliente + teléfono queda una vez.
    carteras: List[int] = field(default_factory=list)

    @property
    def combinada(self) -> bool:
        return len(self.carteras) > 1


def lista_carteras(carteras: List[int]) -> str:
    """'126, 128' para IN (...). Son enteros que resuelve el backend (nunca texto del navegador)."""
    if not carteras:
        raise RecetaInvalida("Indica la cartera.")
    return ", ".join(str(int(c)) for c in carteras)


class _Params:
    def __init__(self):
        self.valores: Dict[str, Any] = {}
        self._n = 0

    def nuevo(self, valor) -> str:
        nombre = f"p{self._n}"
        self._n += 1
        self.valores[nombre] = valor
        return f":{nombre}"

    def lista(self, valores) -> str:
        return ", ".join(self.nuevo(v) for v in valores)


def _texto_valores(valores) -> List[str]:
    if valores is None:
        return []
    if not isinstance(valores, (list, tuple)):
        raise RecetaInvalida("Los valores de un filtro deben ser una lista.")
    limpios = [str(v).strip() for v in valores if v is not None and str(v).strip() != ""]
    if len(limpios) > MAX_VALORES:
        raise RecetaInvalida(f"Un filtro admite como máximo {MAX_VALORES} valores.")
    return limpios


def _numero(valor, nombre: str) -> Optional[float]:
    if valor is None or valor == "":
        return None
    try:
        return float(valor)
    except (TypeError, ValueError):
        raise RecetaInvalida(f"{nombre} debe ser un número.")


def _fecha(valor, nombre: str) -> Optional[date]:
    if valor is None or valor == "":
        return None
    try:
        return datetime.strptime(str(valor)[:10], "%Y-%m-%d").date()
    except ValueError:
        raise RecetaInvalida(f"{nombre} debe tener el formato AAAA-MM-DD.")


# ---------------------------------------------------------------- tramos para elegir (sin escribir números)
# Todo filtro de la pantalla es una lista para marcar. Los campos numéricos se muestran en tramos fijos;
# los de fecha, por año-mes. Las etiquetas son también el valor del filtro.
# Cada tramo es (etiqueta, tope): incluye desde el tope del tramo anterior (sin tope el primero) hasta
# antes de su tope (sin tope el último). Los cortes de MESES_CASTIGO, DIAS_MORA/ATRASO, PDP, gestiones y
# montos son una PROPUESTA (15/11/2026, pendiente de confirmar con Hardy); los de SCORE, DNI_COMPARTE e
# intentos siguen los tramos del score; CAPITAL/META siguen la escala de RANGO_CAPITAL (26/10/2026).
def _enteros(*cortes: int, ultimo: str = "+") -> List[Tuple[str, Optional[float]]]:
    """Tramos de enteros: _enteros(0, 1, 2, 3) → '0', '1', '2', '3+'; (1, 3) → '1–2', '3+'."""
    tramos = []
    for i, desde in enumerate(cortes):
        if i == len(cortes) - 1:
            tramos.append((f"{desde}{ultimo}", None))
        else:
            hasta = cortes[i + 1] - 1
            tramos.append((str(desde) if hasta == desde else f"{desde}–{hasta}", float(cortes[i + 1])))
    return tramos


_SOLES = [("0 – 499.99", 500.0), ("500 – 999.99", 1000.0), ("1,000 – 2,499.99", 2500.0),
          ("2,500 – 4,999.99", 5000.0), ("5,000 – 9,999.99", 10000.0), ("10,000 – 19,999.99", 20000.0),
          ("20,000+", None)]
_PAGOS = [("0", 0.01), ("0.01 – 99.99", 100.0), ("100 – 499.99", 500.0), ("500 – 999.99", 1000.0),
          ("1,000 – 2,499.99", 2500.0), ("2,500 – 4,999.99", 5000.0), ("5,000+", None)]
_DIAS = [("0 o menos", 1.0), ("1–30", 31.0), ("31–60", 61.0), ("61–90", 91.0), ("91–120", 121.0),
         ("121–180", 181.0), ("181–360", 361.0), ("361+", None)]

TRAMOS_RANGO: Dict[str, List[Tuple[str, Optional[float]]]] = {
    "SCORE": [("0–9", 10.0), ("10–19", 20.0), ("20–29", 30.0), ("30–39", 40.0), ("40–49", 50.0),
              ("50–59", 60.0), ("60–69", 70.0), ("70–79", 80.0), ("80–89", 90.0), ("90–100", None)],
    "ORDEN_CLIENTE": _enteros(1, 2, 3, 4, 5),
    "DNI_COMPARTE": _enteros(1, 2, 5),
    "CUENTAS": _enteros(1, 2, 3, 4, 6),
    "CAPITAL": _SOLES,
    "CAPITAL_SAC": _SOLES,
    "META": _SOLES,
    "GESTIONES_HUMANAS_MES": _enteros(0, 1, 4, 11, 31),
    "GESTIONES_MAQUINA_MES": _enteros(0, 1, 4, 11, 31),
    "PDP_GENERADAS_MES": _enteros(0, 1, 2, 3),
    "PDP_VIGENTES": _enteros(0, 1, 2, 3),
    "PDP_PENDIENTES": _enteros(0, 1, 2, 3),
    "PDP_EXIGIBLES": _enteros(0, 1, 2, 3),
    "MESES_CASTIGO": [("0–6", 7.0), ("7–12", 13.0), ("13–24", 25.0), ("25–48", 49.0), ("49+", None)],
    "DIAS_MORA": _DIAS,
    "DIAS_ATRASO": _DIAS,
    "PAGO_ACUMULADO": _PAGOS, "PAGO_OFICIAL_ACUMULADO": _PAGOS, "PAGO_REGISTRADO_SISCOB": _PAGOS,
    "MONTO_PDP_PAGADO": _PAGOS, "MONTO_PAGADO_ACUM": _PAGOS, "MONTO_PAGADO_MES": _PAGOS, "MONTO_SISCOB": _PAGOS,
    # fase 7 (16/11/2026, propuesta): días con gestión en el mes, gestiones y equivocados del teléfono
    "FRECUENCIA_MES": _enteros(0, 1, 2, 4, 8, 16),
    "FRECUENCIA_HUMANA_MES": _enteros(0, 1, 2, 4, 8, 16),
    "GESTIONES_HUMANAS_SISCOB": _enteros(0, 1, 4, 11, 31),
    "GESTIONES_TEL_MES": _enteros(0, 1, 2, 4, 8, 16),
    "GESTIONES_TEL_6M": _enteros(0, 1, 4, 11, 31, 61),
    "EQUIVOCADOS_TEL_6M": _enteros(0, 1, 2, 3),
}
# Orden en pantalla: el score de mayor a menor; el resto de menor a mayor
TRAMOS_DESCENDENTES = frozenset({"SCORE"})


def tramos_de(meta: CampoMeta) -> Optional[List[str]]:
    """Etiquetas de los tramos de un campo numérico, en el orden de pantalla (None si no tiene tramos fijos)."""
    tramos = TRAMOS_RANGO.get(meta.codigo)
    if meta.tipo_filtro != "RANGO" or not tramos:
        return None
    etiquetas = [t[0] for t in tramos]
    return list(reversed(etiquetas)) if meta.codigo in TRAMOS_DESCENDENTES else etiquetas


def _sql_texto(valor: str) -> str:
    return "N'" + str(valor).replace("'", "''") + "'"


def expr_etiqueta(meta: CampoMeta, ref: str) -> str:
    """Expresión SQL con la etiqueta del valor (la misma para contar y para filtrar). ref: columna o d.Valor/d.ValorNum."""
    tipo = meta.tipo_filtro
    if tipo == "RANGO":
        tramos = TRAMOS_RANGO.get(meta.codigo)
        if tramos:
            casos = " ".join(f"WHEN {ref} < {tope!r} THEN {_sql_texto(etq)}" for etq, tope in tramos if tope is not None)
            return f"CASE WHEN {ref} IS NULL THEN NULL {casos} ELSE {_sql_texto(tramos[-1][0])} END"
        # Sin tramos fijos: cada valor (redondeado a 2 decimales; entero sin decimales)
        return (f"CASE WHEN {ref} IS NULL THEN NULL WHEN {ref} = FLOOR({ref}) "
                f"THEN CONVERT(NVARCHAR(40), CAST({ref} AS BIGINT)) "
                f"ELSE CONVERT(NVARCHAR(40), CAST(ROUND({ref}, 2) AS DECIMAL(18, 2))) END")
    if tipo == "FECHA":
        if ref.startswith("d."):
            return f"LEFT({ref}, 7)"            # BaseTrabajoDato.Valor guarda la fecha como AAAA-MM-DD
        return f"CONVERT(NCHAR(7), {ref}, 126)"  # columna de fecha → AAAA-MM
    if meta.columna == "PrioridadColor" and not ref.startswith("d."):   # plomo: P y Q son un solo valor
        return f"CASE WHEN {ref} IN ('P', 'Q') THEN N'PQ' ELSE CONVERT(NVARCHAR(200), {ref}) END"
    return f"CONVERT(NVARCHAR(200), {ref})"


def _ref_dato(meta: CampoMeta) -> str:
    return "d.ValorNum" if meta.tipo_filtro == "RANGO" else "d.Valor"


def _por_etiquetas(meta: CampoMeta, filtro: Dict) -> bool:
    """Filtro por valores marcados (lista) en un campo que no es LISTA/SINO: rangos, fechas o texto."""
    return meta.tipo_filtro in ("RANGO", "FECHA", "TEXTO") and filtro.get("valores") is not None


def _condicion_trabajo(meta: CampoMeta, filtro: Dict, p: _Params) -> str:
    col = meta.columna
    if col not in COLUMNAS_VISTA:
        raise RecetaInvalida(f"El campo {meta.codigo} no se puede filtrar.")
    ref = f"t.[{col}]"
    tipo = meta.tipo_filtro
    if tipo in ("LISTA", "SINO"):
        valores = _texto_valores(filtro.get("valores"))
        if not valores:
            raise RecetaInvalida(f"Elige al menos un valor para {meta.etiqueta}.")
        partes = []
        con_nulos = SIN_DATO in valores
        valores = [v for v in valores if v != SIN_DATO]
        if col in COLUMNAS_BIT:
            bits = [1 if v.upper() in ("SI", "1", "TRUE") else 0 for v in valores]
            if bits:
                partes.append(f"{ref} IN ({p.lista(sorted(set(bits)))})")
        else:
            if col == "PrioridadColor" and "PQ" in valores:   # plomo: P y Q son el mismo color
                valores = [v for v in valores if v != "PQ"] + ["P", "Q"]
            if valores:
                partes.append(f"{ref} IN ({p.lista(valores)})")
        if con_nulos:
            partes.append(f"{ref} IS NULL")
        return "(" + " OR ".join(partes) + ")"
    if _por_etiquetas(meta, filtro):
        valores = _texto_valores(filtro.get("valores"))
        if not valores:
            raise RecetaInvalida(f"Elige al menos un valor para {meta.etiqueta}.")
        con_nulos = SIN_DATO in valores
        valores = [v for v in valores if v != SIN_DATO]
        partes = [f"{expr_etiqueta(meta, ref)} IN ({p.lista(valores)})"] if valores else []
        if con_nulos:
            partes.append(f"{ref} IS NULL")
        return "(" + " OR ".join(partes) + ")"
    if tipo == "RANGO":
        minimo, maximo = _numero(filtro.get("min"), "El mínimo"), _numero(filtro.get("max"), "El máximo")
        if minimo is None and maximo is None:
            raise RecetaInvalida(f"Indica un mínimo o un máximo para {meta.etiqueta}.")
        partes = []
        if minimo is not None:
            partes.append(f"{ref} >= {p.nuevo(minimo)}")
        if maximo is not None:
            partes.append(f"{ref} <= {p.nuevo(maximo)}")
        return "(" + " AND ".join(partes) + ")"
    if tipo == "FECHA":
        desde, hasta = _fecha(filtro.get("desde"), "Desde"), _fecha(filtro.get("hasta"), "Hasta")
        if desde is None and hasta is None:
            raise RecetaInvalida(f"Indica desde o hasta para {meta.etiqueta}.")
        partes = []
        if desde is not None:
            partes.append(f"{ref} >= {p.nuevo(desde)}")
        if hasta is not None:
            partes.append(f"{ref} < {p.nuevo(hasta + timedelta(days=1))}")
        return "(" + " AND ".join(partes) + ")"
    if tipo == "TEXTO":
        texto = str(filtro.get("texto") or "").strip()
        if not texto:
            raise RecetaInvalida(f"Escribe un texto para {meta.etiqueta}.")
        return f"({ref} LIKE {p.nuevo('%' + texto + '%')})"
    raise RecetaInvalida(f"Tipo de filtro no soportado: {tipo}.")


def _condicion_dato(meta: CampoMeta, filtro: Dict, p: _Params) -> str:
    campo = p.nuevo(meta.codigo)
    base = (f"SELECT 1 FROM {FUENTE_DATO} AS d WHERE d.IdCartera = t.IdCartera "
            f"AND d.DNI = t.DNI AND d.Campo = {campo}")
    tipo = meta.tipo_filtro
    if tipo in ("LISTA", "SINO") or _por_etiquetas(meta, filtro):
        valores = _texto_valores(filtro.get("valores"))
        if not valores:
            raise RecetaInvalida(f"Elige al menos un valor para {meta.etiqueta}.")
        con_nulos = SIN_DATO in valores
        valores = [v for v in valores if v != SIN_DATO]
        expr = "d.Valor" if tipo in ("LISTA", "SINO") else expr_etiqueta(meta, _ref_dato(meta))
        partes = []
        if valores:
            partes.append(f"EXISTS ({base} AND {expr} IN ({p.lista(valores)}))")
        if con_nulos:
            partes.append(f"NOT EXISTS ({base})")
        return "(" + " OR ".join(partes) + ")"
    if tipo == "RANGO":
        minimo, maximo = _numero(filtro.get("min"), "El mínimo"), _numero(filtro.get("max"), "El máximo")
        if minimo is None and maximo is None:
            raise RecetaInvalida(f"Indica un mínimo o un máximo para {meta.etiqueta}.")
        cond = []
        if minimo is not None:
            cond.append(f"d.ValorNum >= {p.nuevo(minimo)}")
        if maximo is not None:
            cond.append(f"d.ValorNum <= {p.nuevo(maximo)}")
        return f"EXISTS ({base} AND " + " AND ".join(cond) + ")"
    if tipo == "FECHA":
        desde, hasta = _fecha(filtro.get("desde"), "Desde"), _fecha(filtro.get("hasta"), "Hasta")
        if desde is None and hasta is None:
            raise RecetaInvalida(f"Indica desde o hasta para {meta.etiqueta}.")
        cond = []
        if desde is not None:
            cond.append(f"d.Valor >= {p.nuevo(desde.isoformat())}")
        if hasta is not None:
            cond.append(f"d.Valor <= {p.nuevo(hasta.isoformat())}")
        return f"EXISTS ({base} AND " + " AND ".join(cond) + ")"
    if tipo == "TEXTO":
        texto = str(filtro.get("texto") or "").strip()
        if not texto:
            raise RecetaInvalida(f"Escribe un texto para {meta.etiqueta}.")
        return f"EXISTS ({base} AND d.Valor LIKE {p.nuevo('%' + texto + '%')})"
    raise RecetaInvalida(f"Tipo de filtro no soportado: {tipo}.")


# CTE de cada condición del día (solo se arma si la receta la usa)
_SQL_CONDICION = {
    "CEF_HOY": """c_CEF_HOY AS (
    SELECT DISTINCT LTRIM(RTRIM(COALESCE(NULLIF(LTRIM(RTRIM(g.DNI)), ''), cl.Dni))) COLLATE DATABASE_DEFAULT AS DNI
    FROM siscob.dbo.gestion AS g WITH (NOLOCK)
    LEFT JOIN siscob.dbo.Cliente AS cl WITH (NOLOCK) ON cl.IdCliente = g.IdCliente
    INNER JOIN score.IndicadorResultado AS r ON r.IdIndicador = g.IdIndicador
    WHERE g.Fecha >= :hoy AND g.Fecha < :manana AND g.idCartera IN ({carteras})
      AND r.Resultado IN ('TITULAR', 'TERCERO_ACUERDO'))""",
    "EQUIVOCADO_HOY": """c_EQUIVOCADO_HOY AS (
    SELECT DISTINCT LTRIM(RTRIM(COALESCE(NULLIF(LTRIM(RTRIM(g.DNI)), ''), cl.Dni))) COLLATE DATABASE_DEFAULT AS DNI,
           CONVERT(CHAR(9), g.telefono) COLLATE DATABASE_DEFAULT AS Telefono
    FROM siscob.dbo.gestion AS g WITH (NOLOCK)
    LEFT JOIN siscob.dbo.Cliente AS cl WITH (NOLOCK) ON cl.IdCliente = g.IdCliente
    INNER JOIN score.IndicadorResultado AS r ON r.IdIndicador = g.IdIndicador
    WHERE g.Fecha >= :hoy AND g.Fecha < :manana AND g.idCartera IN ({carteras})
      AND r.Resultado = 'EQUIVOCADO')""",
    # SISCOB.COMPROMISO: el cliente y su cartera salen de IdCliente. PAGADO trae SI, NO, S y N (14/11/2026):
    # pagado = SI o S. (Ojo: el módulo de compromisos del CRM solo reconoce SI.)
    "PDP_CREADA_HOY": """c_PDP_CREADA_HOY AS (
    SELECT DISTINCT LTRIM(RTRIM(cl.Dni)) COLLATE DATABASE_DEFAULT AS DNI
    FROM siscob.dbo.COMPROMISO AS cp WITH (NOLOCK)
    INNER JOIN siscob.dbo.Cliente AS cl WITH (NOLOCK) ON cl.IdCliente = cp.IdCliente
    WHERE cp.FechaGenero >= :hoy AND cp.FechaGenero < :manana AND cl.IdCartera IN ({carteras}) AND cp.Monto > 0)""",
    "PDP_VIGENTE": """c_PDP_VIGENTE AS (
    SELECT DISTINCT LTRIM(RTRIM(cl.Dni)) COLLATE DATABASE_DEFAULT AS DNI
    FROM siscob.dbo.COMPROMISO AS cp WITH (NOLOCK)
    INNER JOIN siscob.dbo.Cliente AS cl WITH (NOLOCK) ON cl.IdCliente = cp.IdCliente
    WHERE cl.IdCartera IN ({carteras}) AND cp.FechaCompromiso >= :hoy AND cp.Monto > 0
      AND ISNULL(UPPER(LTRIM(RTRIM(cp.Pagado))), '') NOT IN ('SI', 'S'))""",
    "PAGO_HOY": """c_PAGO_HOY AS (
    SELECT DISTINCT LTRIM(RTRIM(cl.Dni)) COLLATE DATABASE_DEFAULT AS DNI
    FROM siscob.dbo.COMPROMISO AS cp WITH (NOLOCK)
    INNER JOIN siscob.dbo.Cliente AS cl WITH (NOLOCK) ON cl.IdCliente = cp.IdCliente
    WHERE cl.IdCartera IN ({carteras}) AND cp.FechaPago >= :hoy AND cp.FechaPago < :manana
      AND UPPER(LTRIM(RTRIM(cp.Pagado))) IN ('SI', 'S'))""",
    # Por la cartera de cada fila enviada (BaseDetalle): cuenta también lo enviado en una base combinada
    "ENVIADO_HOY": """c_ENVIADO_HOY AS (
    SELECT DISTINCT d.DNI, d.Telefono
    FROM score.BaseDetalle AS d
    INNER JOIN score.Base AS b ON b.IdBase = d.IdBase
    WHERE d.IdCartera IN ({carteras}) AND b.FechaGeneracion >= :hoy
      AND (b.Canal = :canal OR (:canal IN ('PRED', 'PREVIEW') AND b.Canal IN ('PRED', 'PREVIEW'))))""",
}


def _existe_condicion(codigo: str) -> str:
    if CONDICIONES[codigo]["nivel"] == "TELEFONO":
        return f"EXISTS (SELECT 1 FROM c_{codigo} AS x WHERE x.DNI = t.DNI AND x.Telefono = t.Telefono)"
    return f"EXISTS (SELECT 1 FROM c_{codigo} AS x WHERE x.DNI = t.DNI)"


# Zonas restringidas (Hardy 27/11/2026: Interbank ordenó detener toda gestión en Piura). Paso forzado, como los
# descartados: no depende de la receta y se ve en el embudo. La vista cruza score.ZonaRestringida (vigente, con sus
# carteras) con la ubicación del cliente en score.vw_DatoCliente (campos DEPARTAMENTO / PROVINCIA / DISTRITO).
VISTA_ZONAS = "score.vw_ClienteZonaRestringida"
PASO_ZONAS = ("Sin zona restringida",
              f"NOT EXISTS (SELECT 1 FROM {VISTA_ZONAS} AS z WHERE z.IdCartera = t.IdCartera AND z.DNI = t.DNI)")


def construir_consulta(idcartera: int, receta: Dict, catalogo: Dict[str, CampoMeta],
                       hoy: Optional[date] = None, carteras: Optional[List[int]] = None,
                       zonas: bool = False) -> ConsultaSql:
    """Traduce la receta a pasos SQL (uno por filtro y por condición) sobre score.vw_BaseTrabajo AS t.
    carteras: las carteras reales que se leen (por defecto, solo idcartera).
    zonas: hay zonas restringidas vigentes para estas carteras → paso forzado «Sin zona restringida»."""
    hoy = hoy or date.today()
    carteras = [int(c) for c in (carteras or [idcartera])]
    en_carteras = lista_carteras(carteras)
    p = _Params()
    pasos: List[Tuple[str, str]] = [("Sin descartados", "t.Descartado = 0")]
    campos_paso: List[Optional[str]] = [None]
    if zonas:
        pasos.append(PASO_ZONAS)
        campos_paso.append(None)
    for i, filtro in enumerate(receta.get("filtros") or []):
        if not isinstance(filtro, dict):
            raise RecetaInvalida("Cada filtro debe ser un objeto.")
        codigo = str(filtro.get("campo") or "").strip().upper()
        meta = catalogo.get(codigo)
        if meta is None or not meta.disponible:
            raise RecetaInvalida(f"El campo {codigo or '(vacío)'} no está disponible para esta cartera.")
        if meta.origen == "TRABAJO":
            cond = _condicion_trabajo(meta, filtro, p)
        elif meta.origen == "DATO":
            cond = _condicion_dato(meta, filtro, p)
        else:
            raise RecetaInvalida(f"El campo {meta.etiqueta} todavía no se puede filtrar en el generador.")
        if filtro.get("excluir"):
            # "Sin X": también deja pasar los que no tienen dato (NOT sobre NULL no sería verdadero)
            cond = f"(CASE WHEN {cond} THEN 1 ELSE 0 END) = 0"
        if codigo in campos_paso:
            raise RecetaInvalida(f"El campo {meta.etiqueta} está dos veces en la receta.")
        pasos.append((("Sin " if filtro.get("excluir") else "") + meta.etiqueta, cond))
        campos_paso.append(codigo)

    ctes: List[str] = []
    condiciones = receta.get("condiciones") or {}
    if not isinstance(condiciones, dict):
        raise RecetaInvalida("Las condiciones del día deben ser un objeto {codigo: modo}.")
    for codigo, modo in condiciones.items():
        codigo = str(codigo).upper()
        modo = str(modo or "INDIFERENTE").upper()
        if codigo not in CONDICIONES:
            raise RecetaInvalida(f"Condición del día desconocida: {codigo}.")
        if modo not in MODOS_CONDICION:
            raise RecetaInvalida(f"Modo no válido para {codigo}: use QUITAR, SOLO o INDIFERENTE.")
        if modo == "INDIFERENTE":
            continue
        if codigo == "ENVIADO_HOY" and not receta.get("canal"):
            raise RecetaInvalida("Para usar 'ya enviado hoy' elige primero el canal.")
        ctes.append(_SQL_CONDICION[codigo].format(carteras=en_carteras))
        existe = _existe_condicion(codigo)
        etiqueta = CONDICIONES[codigo]["etiqueta"]
        pasos.append(("Sin " + etiqueta.lower() if modo == "QUITAR" else "Solo " + etiqueta.lower(),
                      f"NOT {existe}" if modo == "QUITAR" else existe))
        campos_paso.append(None)

    p.valores.update({"idcartera": int(idcartera), "hoy": hoy, "manana": hoy + timedelta(days=1),
                      "canal": str(receta.get("canal") or "").upper() or None})
    return ConsultaSql(ctes=ctes, pasos=pasos, params=p.valores, campos_paso=campos_paso, carteras=carteras)


def solo_parametros_usados(sql: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Deja solo los parámetros que el SQL usa (:nombre)."""
    usados = set(re.findall(r"(?<![:\w]):([A-Za-z_]\w*)", sql))
    return {k: v for k, v in params.items() if k in usados}


def telefonos_por_cliente(receta: Dict) -> Optional[int]:
    valor = receta.get("telefonos_por_cliente")
    if valor in (None, "", 0, "0"):
        return None
    try:
        n = int(valor)
    except (TypeError, ValueError):
        raise RecetaInvalida("Teléfonos por cliente debe ser un número entero.")
    if n < 1 or n > 50:
        raise RecetaInvalida("Teléfonos por cliente debe estar entre 1 y 50.")
    return n


def sql_embudo(c: ConsultaSql) -> str:
    """Una sola pasada: para cada fila, el primer paso que no cumple (0 = ninguno falla → pasa todo)."""
    # (CASE WHEN cond THEN 1 ELSE 0 END) = 0: un paso que da NULL cuenta como no cumplido, igual que en el WHERE
    casos = " ".join(f"WHEN (CASE WHEN ({cond}) THEN 1 ELSE 0 END) = 0 THEN {i + 1}"
                     for i, (_, cond) in enumerate(c.pasos))
    con = ("WITH " + ",\n".join(c.ctes) + ",\n") if c.ctes else "WITH "
    return f"""{con}paso AS (
    SELECT t.DNI, CASE {casos} ELSE 0 END AS falla
    FROM score.vw_BaseTrabajo AS t
    WHERE t.IdCartera IN ({lista_carteras(c.carteras)})
)
SELECT 'T' AS tipo, falla, COUNT(*) AS n FROM paso GROUP BY falla
UNION ALL
SELECT 'C', falla, COUNT(*) FROM (
    SELECT DNI, CASE WHEN MIN(CASE WHEN falla = 0 THEN 0 ELSE 1 END) = 0 THEN 0 ELSE MAX(falla) END AS falla
    FROM paso GROUP BY DNI
) AS cli GROUP BY falla"""


def acumular_embudo(filas, pasos: List[Tuple[str, str]]) -> List[Dict[str, Any]]:
    """Convierte los conteos por "primer paso que falla" en el embudo acumulado.

    Un teléfono pasa el paso k si su primer fallo es posterior a k (o no falla: 0).
    Para clientes se usa el mayor paso alcanzado por alguno de sus teléfonos.
    """
    n = len(pasos)
    tel = {i: 0 for i in range(n + 1)}
    cli = {i: 0 for i in range(n + 1)}
    for tipo, falla, cantidad in filas:
        destino = tel if tipo == "T" else cli
        destino[int(falla)] = destino.get(int(falla), 0) + int(cantidad)

    def pasan(d, k):  # cuántos llegan después del paso k (k = 0: todos)
        return d[0] + sum(v for f, v in d.items() if f > k)

    embudo = [{"paso": "Teléfonos de la cartera", "telefonos": sum(tel.values()), "clientes": sum(cli.values())}]
    for k, (etiqueta, _) in enumerate(pasos, start=1):
        embudo.append({"paso": etiqueta, "telefonos": pasan(tel, k), "clientes": pasan(cli, k)})
    return embudo


def sql_seleccion(c: ConsultaSql, por_cliente: Optional[int]) -> str:
    """CTE 'sel': teléfonos que cumplen todo, con su orden dentro del cliente en la base."""
    donde = " AND ".join(f"({cond})" for _, cond in c.pasos)
    limite = f"WHERE f.rn <= {int(por_cliente)}" if por_cliente else ""
    con = ("WITH " + ",\n".join(c.ctes) + ",\n") if c.ctes else "WITH "
    # Cartera combinada: entre las filas que cumplen, el mismo cliente + teléfono queda una vez (la de mejor score)
    unico = (",\n           ROW_NUMBER() OVER (PARTITION BY t.DNI, t.Telefono ORDER BY t.Score DESC, t.IdCartera) AS u"
             if c.combinada else ", 1 AS u")
    return f"""{con}t0 AS (
    SELECT t.IdCartera, t.DNI, t.IdCliente, t.Telefono, t.Score, t.Tramo, t.OrdenCliente,
           t.PrioridadColor, t.Whatsapp, t.Osiptel, t.Timbra, t.Operador, t.Capital, t.RangoCapital,
           t.ContactoDirectoMes, t.Razon1, t.Razon2, t.Razon3, t.Razon_Resta, t.FechaScore, t.Version,
           t.FechaCorteFuente{unico}
    FROM score.vw_BaseTrabajo AS t
    WHERE t.IdCartera IN ({lista_carteras(c.carteras)}) AND {donde}
),
f AS (
    SELECT t.IdCartera, t.DNI, t.IdCliente, t.Telefono, t.Score, t.Tramo, t.OrdenCliente AS OrdenScore,
           t.PrioridadColor, t.Whatsapp, t.Osiptel, t.Timbra, t.Operador, t.Capital, t.RangoCapital,
           t.ContactoDirectoMes, t.Razon1, t.Razon2, t.Razon3, t.Razon_Resta, t.FechaScore, t.Version,
           t.FechaCorteFuente,
           ROW_NUMBER() OVER (PARTITION BY t.DNI ORDER BY t.OrdenCliente, t.Score DESC, t.Telefono) AS rn
    FROM t0 AS t WHERE t.u = 1
),
sel AS (
    SELECT f.*, ROW_NUMBER() OVER (ORDER BY f.Score DESC, f.DNI, f.rn) AS Posicion
    FROM f {limite}
)"""


# ---------------------------------------------------------------- nombre del archivo
# ---------------------------------------------------------------- consulta en una sola pasada
# La vista (score.vw_BaseTrabajo) se lee UNA vez por consulta: cada teléfono se guarda en #gb_a con una
# máscara "Fallo" (bit i = no cumple el paso i de la receta). De ahí salen, sin volver a la vista:
#   - el embudo (pasa los k primeros pasos: Fallo % 2^k = 0),
#   - la base (Fallo = 0), sus totales y la página,
#   - los conteos de cada filtro (sin su propio paso: Fallo IN (0, 2^paso)), como los segmentadores de Excel.
# Antes cada pieza recorría la vista con todos los filtros (15/11/2026: "a veces demora en recalcularse").
#
# Tablas temporales: se crean SIN parámetros y luego se llenan. Con pyodbc, una sentencia con parámetros
# corre dentro de sp_prepexec y una #tabla creada ahí desaparece al terminar.
TEMP_TODO = "#gb_a"
TEMP_CLIENTES = "#gb_c"
MAX_PASOS = 62                       # la máscara es BIGINT
CAMPOS_SIN_SEGMENTADOR = frozenset({"DESCARTADO"})   # siempre filtrado (los descartados nunca entran)


def _con(c: ConsultaSql) -> str:
    return ("WITH " + ",\n".join(c.ctes) + "\n") if c.ctes else ""


def sql_donde(c: ConsultaSql, sin_campo: Optional[str] = None) -> str:
    """WHERE sobre score.vw_BaseTrabajo AS t con todos los pasos, menos el del campo indicado."""
    conds = [cond for (_, cond), campo in zip(c.pasos, c.campos_paso or [None] * len(c.pasos))
             if sin_campo is None or campo != sin_campo]
    return " AND ".join([f"t.IdCartera IN ({lista_carteras(c.carteras)})"] + [f"({x})" for x in conds])


def es_segmentador(meta: CampoMeta) -> bool:
    """Campo que se muestra como lista para marcar (todos los tipos: lista, sí/no, rango, fecha, texto)."""
    return (meta.disponible and meta.origen in ("TRABAJO", "DATO") and meta.codigo not in CAMPOS_SIN_SEGMENTADOR
            and meta.tipo_filtro in ("LISTA", "SINO", "RANGO", "FECHA", "TEXTO")
            and (meta.origen == "DATO" or meta.columna in COLUMNAS_VISTA))


def cuenta_telefonos(meta: CampoMeta) -> bool:
    return meta.origen == "TRABAJO" and meta.grupo in GRUPOS_TELEFONO


def _codigos_sql(codigos: List[str]) -> str:
    # Los códigos salen del catálogo (no del navegador) y además se validan: solo letras, números y _
    for x in codigos:
        if not re.fullmatch(r"[A-Z0-9_]+", x):
            raise RecetaInvalida(f"Código de campo no válido: {x}.")
    return ", ".join(f"N'{x}'" for x in codigos)


def sql_borrar_temporales() -> str:
    tablas = [TEMP_TODO, TEMP_CLIENTES] + [f"#c_{codigo}" for codigo in CONDICIONES]
    return " ".join(f"IF OBJECT_ID('tempdb..{t}') IS NOT NULL DROP TABLE {t};" for t in tablas)


def _partes_cte(cte: str) -> Tuple[str, str]:
    m = re.match(r"\s*c_([A-Z_]+) AS \((.*)\)\s*$", cte, re.S)
    if not m or m.group(1) not in CONDICIONES:
        raise RecetaInvalida("Condición del día no reconocida.")
    return m.group(1), m.group(2).strip()


def condiciones_usadas(c: ConsultaSql) -> List[str]:
    return [_partes_cte(cte)[0] for cte in c.ctes]


def sql_refrescar_condicion(codigo: str, idcartera: int) -> List[str]:
    """Rehace la foto de una condición del día para UNA cartera en score.CondicionDia (parámetros :hoy,
    :manana). El MERGE del estado lo hace el servicio, con las filas y el tiempo medidos."""
    if codigo not in CONDICIONES_CACHE:
        raise RecetaInvalida(f"La condición {codigo} no se guarda en caché.")
    idc = int(idcartera)
    _, cuerpo = _partes_cte(_SQL_CONDICION[codigo].format(carteras=str(idc)))
    telefono = "x.Telefono" if CONDICIONES[codigo]["nivel"] == "TELEFONO" else "NULL"
    return [
        f"DELETE FROM score.CondicionDia WHERE Codigo = N'{codigo}' AND IdCartera = {idc};",
        f"INSERT INTO score.CondicionDia (Codigo, IdCartera, Fecha, DNI, Telefono) "
        f"SELECT N'{codigo}', {idc}, :hoy, x.DNI, {telefono} FROM ({cuerpo}) AS x;",
    ]


SQL_ESTADO_CONDICION = """
MERGE score.CondicionDiaEstado AS e
USING (SELECT :codigo AS Codigo, :idcartera AS IdCartera) AS s
   ON e.Codigo = s.Codigo AND e.IdCartera = s.IdCartera
WHEN MATCHED THEN UPDATE SET Fecha = :hoy, CalculadoEn = SYSDATETIME(), Filas = :filas, Ms = :ms
WHEN NOT MATCHED THEN INSERT (Codigo, IdCartera, Fecha, CalculadoEn, Filas, Ms)
     VALUES (:codigo, :idcartera, :hoy, SYSDATETIME(), :filas, :ms);"""

SQL_CONDICIONES_FRESCAS = """
SELECT Codigo, IdCartera FROM score.CondicionDiaEstado
WHERE Fecha = :hoy AND CalculadoEn >= DATEADD(SECOND, -:segundos, SYSDATETIME())"""


def _condiciones_temporales(c: ConsultaSql, desde_cache: bool = False) -> List[str]:
    """Cada condición del día se calcula UNA vez en una #tabla (antes iba como CTE dentro de la lectura).
    La tabla se crea sin parámetros y se llena con ellos (ver la nota de pyodbc arriba).
    desde_cache: las condiciones de CONDICIONES_CACHE se copian de score.CondicionDia (foto reciente)."""
    sentencias = []
    for cte in c.ctes:
        codigo, cuerpo = _partes_cte(cte)
        if desde_cache and codigo in CONDICIONES_CACHE:
            telefono = ", Telefono" if CONDICIONES[codigo]["nivel"] == "TELEFONO" else ""
            cuerpo = (f"SELECT DISTINCT DNI{telefono} FROM score.CondicionDia WHERE Codigo = N'{codigo}' "
                      f"AND IdCartera IN ({lista_carteras(c.carteras)}) AND Fecha = :hoy")
        por_telefono = CONDICIONES[codigo]["nivel"] == "TELEFONO"
        columnas = "DNI, Telefono" if por_telefono else "DNI"
        # Sin NOT NULL y con largo holgado: la gestión puede traer DNI vacío o más largo (no debe romper la carga)
        definicion = ("DNI VARCHAR(50) COLLATE DATABASE_DEFAULT NULL"
                      + (", Telefono VARCHAR(20) COLLATE DATABASE_DEFAULT NULL" if por_telefono else ""))
        sentencias.append(f"CREATE TABLE #c_{codigo} ({definicion});")
        sentencias.append(f"INSERT INTO #c_{codigo} ({columnas}) {cuerpo.strip()}")
        sentencias.append(f"CREATE CLUSTERED INDEX IX_c_{codigo} ON #c_{codigo} ({columnas});")
    return sentencias


def sql_materializar(c: ConsultaSql, condiciones_cache: bool = False) -> List[str]:
    """Lee la vista una vez y guarda cada teléfono con su máscara de pasos que no cumple.
    condiciones_cache: las condiciones del día salen de score.CondicionDia (ver SEGUNDOS_CACHE_CONDICIONES)."""
    if len(c.pasos) > MAX_PASOS:
        raise RecetaInvalida(f"Demasiados filtros a la vez (máximo {MAX_PASOS - 8}).")
    # Las condiciones del día leen sus #tablas (c_X → #c_X)
    fallo = " + ".join(f"(CASE WHEN (CASE WHEN ({cond.replace('FROM c_', 'FROM #c_')}) THEN 1 ELSE 0 END) = 0 "
                       f"THEN CAST({2 ** i} AS BIGINT) ELSE 0 END)"
                       for i, (_, cond) in enumerate(c.pasos)) or "CAST(0 AS BIGINT)"
    return [
        sql_borrar_temporales(),
        *_condiciones_temporales(c, condiciones_cache),
        f"SELECT TOP 0 t.*, CAST(0 AS BIGINT) AS Fallo INTO {TEMP_TODO} FROM score.vw_BaseTrabajo AS t;",
        f"INSERT INTO {TEMP_TODO} SELECT t.*, {fallo} FROM score.vw_BaseTrabajo AS t "
        f"WHERE t.IdCartera IN ({lista_carteras(c.carteras)})",
        *([sql_unico_combinada()] if c.combinada else []),
        f"CREATE CLUSTERED INDEX IX_gb_a ON {TEMP_TODO} (Fallo, DNI);",
    ]


def sql_unico_combinada() -> str:
    """Cartera combinada: un cliente + teléfono que está en dos carteras queda una vez. Se queda la fila que cumple
    la receta (Fallo = 0) y, entre esas, la de mejor score; a igual score, la cartera de número menor."""
    return (f"WITH x AS (SELECT ROW_NUMBER() OVER (PARTITION BY DNI, Telefono ORDER BY "
            f"CASE WHEN Fallo = 0 THEN 0 ELSE 1 END, Score DESC, IdCartera) AS n FROM {TEMP_TODO}) "
            f"DELETE FROM x WHERE n > 1;")


def sql_embudo_temp(c: ConsultaSql) -> str:
    """Una fila: total y, por cada paso k, teléfonos y clientes que cumplen los k primeros pasos."""
    cols = ["COUNT(*) AS T0", "COUNT(DISTINCT DNI) AS C0"]
    for k in range(1, len(c.pasos) + 1):
        m = 2 ** k
        cols.append(f"SUM(CASE WHEN Fallo % {m} = 0 THEN 1 ELSE 0 END) AS T{k}")
        cols.append(f"COUNT(DISTINCT CASE WHEN Fallo % {m} = 0 THEN DNI END) AS C{k}")
    return f"SELECT {', '.join(cols)} FROM {TEMP_TODO}"


def embudo_desde_fila(fila, pasos: List[Tuple[str, str]]) -> List[Dict[str, Any]]:
    salida = [{"paso": "Teléfonos de la cartera", "telefonos": int(fila[0] or 0), "clientes": int(fila[1] or 0)}]
    for k, (etiqueta, _) in enumerate(pasos, start=1):
        salida.append({"paso": etiqueta, "telefonos": int(fila[2 * k] or 0), "clientes": int(fila[2 * k + 1] or 0)})
    return salida


def sql_seleccion_temp(por_cliente: Optional[int]) -> str:
    """CTE 'sel' desde la temporal: los teléfonos que cumplen todo, con su orden en el cliente y en la base."""
    limite = f"WHERE f.rn <= {int(por_cliente)}" if por_cliente else ""
    return f"""WITH f AS (
    SELECT a.*, a.OrdenCliente AS OrdenScore,
           ROW_NUMBER() OVER (PARTITION BY a.DNI ORDER BY a.OrdenCliente, a.Score DESC, a.Telefono) AS rn
    FROM {TEMP_TODO} AS a WHERE a.Fallo = 0
),
sel AS (
    SELECT f.*, ROW_NUMBER() OVER (ORDER BY f.Score DESC, f.DNI, f.rn) AS Posicion
    FROM f {limite}
)"""


def _filas_campo(bit: Optional[int]) -> str:
    """Filas que cuentan para un filtro: las que cumplen todo, o todo menos su propio paso."""
    return "a.Fallo = 0" if bit is None else f"a.Fallo IN (0, {2 ** bit})"


def sql_grupos(metas: List[CampoMeta], origen: str, por_cliente: bool) -> str:
    """Cuenta por valor varios campos de la vista en UNA pasada. Filas (Campo, Valor, N).
    origen: tabla o subconsulta con alias a (con las columnas de la vista). por_cliente: los campos son del
    cliente (iguales en todos sus teléfonos): se lee una fila por DNI y se cuentan clientes; si no, teléfonos.

    Cada fila se despliega en (campo, valor) con CROSS APPLY VALUES y se agrupa una sola vez. Antes era
    GROUPING SETS, que SQL Server resuelve recorriendo la lectura una vez por campo: medido el 20/11/2026
    (diagnostico_generador_conteos_2.sql, mismos resultados), 144 por teléfono 15,6 s → 0,6 s; 112 5,5 s → 0,2 s;
    por cliente 3,0 s → 0,6 s."""
    if not metas:
        return ""
    codigos = [m.codigo for m in metas]
    _codigos_sql(codigos)   # valida los códigos (salen del catálogo)
    exprs = [expr_etiqueta(m, f"a.[{m.columna}]") for m in metas]
    columnas = ", ".join(f"{e} AS v{i}" for i, e in enumerate(exprs))
    lectura = f"SELECT DISTINCT a.DNI, {columnas} FROM {origen}" if por_cliente else f"SELECT {columnas} FROM {origen}"
    valores = ", ".join(f"(N'{c}', CONVERT(NVARCHAR(200), x.v{i}))" for i, c in enumerate(codigos))
    return (f"SELECT u.Campo, u.Valor, COUNT(*) AS N FROM ({lectura}) AS x "
            f"CROSS APPLY (VALUES {valores}) AS u (Campo, Valor) GROUP BY u.Campo, u.Valor")


def _grupo_dato(meta: CampoMeta, union_clientes: str, en_carteras: str) -> str:
    """Clientes por valor de un campo guardado como filas (una fila por cuenta: un cliente cuenta una vez por valor)."""
    codigo = _codigos_sql([meta.codigo])
    ref = _ref_dato(meta)
    expr = "d.Valor" if meta.tipo_filtro in ("LISTA", "SINO") else expr_etiqueta(meta, ref)
    return (f"SELECT d.Campo, {expr} AS Valor, COUNT(DISTINCT d.DNI) AS N FROM {FUENTE_DATO} AS d "
            f"{union_clientes} WHERE d.IdCartera IN ({en_carteras}) AND d.Campo = {codigo} AND {ref} IS NOT NULL "
            f"GROUP BY d.Campo, {expr}")


def plan_conteos(c: ConsultaSql, catalogo: Dict[str, CampoMeta]) -> Dict[str, Any]:
    """SQL de los conteos de cada filtro, sobre la temporal de sql_materializar. Devuelve:
    - preparar: llena #gb_c (clientes que cumplen todo), sin parámetros
    - trabajo: UNA consulta con todos los campos de la vista, filas (Campo, Valor, N)
    - dato: consultas de los campos guardados como filas, filas (Campo, Valor, N) (con SIN_DATO en los propios)
    - con_dato: filas (Campo, N) clientes con alguna fila de los campos DATO sin filtro propio (para "Sin dato")
    """
    bits = {campo: i for i, campo in enumerate(c.campos_paso or []) if campo}
    segmentadores = [m for m in catalogo.values() if es_segmentador(m)]

    # Campos de la vista sin filtro propio: todos cuentan sobre las filas que cumplen todo, en una lectura por
    # nivel (teléfonos / clientes). Los que tienen filtro propio se cuentan aparte, sin su paso.
    partes = []
    trabajo_metas = [x for x in segmentadores if x.origen == "TRABAJO"]
    libres = [m for m in trabajo_metas if bits.get(m.codigo) is None]
    origen_libre = f"{TEMP_TODO} AS a WHERE a.Fallo = 0"
    for por_cliente in (False, True):
        grupo = [m for m in libres if cuenta_telefonos(m) != por_cliente]
        if grupo:
            partes.append(sql_grupos(grupo, origen_libre, por_cliente))
    for m in (x for x in trabajo_metas if bits.get(x.codigo) is not None):
        n = "COUNT(*)" if cuenta_telefonos(m) else "COUNT(DISTINCT a.DNI)"
        expr = expr_etiqueta(m, f"a.[{m.columna}]")
        partes.append(f"SELECT N'{m.codigo}' AS Campo, {expr} AS Valor, {n} AS N FROM {TEMP_TODO} AS a "
                      f"WHERE {_filas_campo(bits.get(m.codigo))} GROUP BY {expr}")
    trabajo = "\nUNION ALL\n".join(partes)

    en_carteras = lista_carteras(c.carteras)
    # #gb_c guarda cartera y cliente: el dato se toma de la cartera de la fila (en una combinada, el cliente
    # puede tener datos distintos en cada cartera)
    union_comun = f"INNER JOIN {TEMP_CLIENTES} AS u ON u.DNI = d.DNI AND u.IdCartera = d.IdCartera"
    dato, dato_comun = [], []
    listas_comunes = []
    for m in (x for x in segmentadores if x.origen == "DATO"):
        bit = bits.get(m.codigo)
        if bit is None:
            dato_comun.append(m.codigo)
            if m.tipo_filtro in ("LISTA", "SINO"):
                listas_comunes.append(m.codigo)
            else:
                dato.append(_grupo_dato(m, union_comun, en_carteras))
        else:
            u = f"(SELECT DISTINCT a.IdCartera, a.DNI FROM {TEMP_TODO} AS a WHERE {_filas_campo(bit)})"
            lista = _codigos_sql([m.codigo])
            dato.append(
                f"{_grupo_dato(m, f'INNER JOIN {u} AS u ON u.DNI = d.DNI AND u.IdCartera = d.IdCartera', en_carteras)} "
                f"UNION ALL SELECT {lista}, N'{SIN_DATO}', COUNT(DISTINCT u.DNI) FROM {u} AS u "
                f"WHERE NOT EXISTS (SELECT 1 FROM {FUENTE_DATO} AS d WHERE d.IdCartera = u.IdCartera "
                f"AND d.Campo = {lista} AND d.DNI = u.DNI)")
    if listas_comunes:
        dato.insert(0,
            f"SELECT d.Campo, d.Valor, COUNT(DISTINCT d.DNI) AS N FROM {FUENTE_DATO} AS d {union_comun} "
            f"WHERE d.IdCartera IN ({en_carteras}) AND d.Campo IN ({_codigos_sql(listas_comunes)}) AND d.Valor IS NOT NULL "
            f"GROUP BY d.Campo, d.Valor")
    con_dato = []
    if dato_comun:
        con_dato.append(
            f"SELECT d.Campo, COUNT(DISTINCT d.DNI) AS N FROM {FUENTE_DATO} AS d {union_comun} "
            f"WHERE d.IdCartera IN ({en_carteras}) AND d.Campo IN ({_codigos_sql(dato_comun)}) GROUP BY d.Campo")
    preparar = (f"SELECT TOP 0 IdCartera, DNI INTO {TEMP_CLIENTES} FROM {TEMP_TODO}; "
                f"INSERT INTO {TEMP_CLIENTES} (IdCartera, DNI) SELECT DISTINCT IdCartera, DNI FROM {TEMP_TODO} WHERE Fallo = 0; "
                f"CREATE CLUSTERED INDEX IX_gb_c ON {TEMP_CLIENTES} (DNI, IdCartera);")
    return {"preparar": preparar, "trabajo": trabajo, "dato": dato, "con_dato": con_dato, "dato_comun": dato_comun}


def _pieza(texto: str) -> str:
    s = unicodedata.normalize("NFKD", str(texto or ""))
    s = "".join(ch for ch in s if not unicodedata.combining(ch)).upper()
    return re.sub(r"[^A-Z0-9]+", "", s)


def resumen_receta(receta: Dict, catalogo: Dict[str, CampoMeta]) -> List[str]:
    """Piezas legibles de la receta para el nombre: TRAMO A-B → 'A-B'; un valor → el valor; varios → abreviatura."""
    piezas: List[str] = []
    for filtro in receta.get("filtros") or []:
        codigo = str(filtro.get("campo") or "").upper()
        meta = catalogo.get(codigo)
        abrev = _pieza(meta.abreviatura if meta and meta.abreviatura else codigo)[:6]
        valores = [v for v in _texto_valores(filtro.get("valores")) if v != SIN_DATO]
        if codigo == "TRAMO" and valores:
            pieza = "-".join(sorted(_pieza(v) for v in valores))
        elif meta and meta.tipo_filtro == "SINO" and len(valores) == 1:
            pieza = abrev if valores[0].upper() == "SI" else "NO" + abrev
        elif meta and meta.tipo_filtro in ("RANGO", "FECHA") and len(valores) == 1:
            pieza = abrev + _pieza(valores[0])[:8]          # p. ej. MCAS1324 (meses de castigo 13–24)
        elif len(valores) == 1 and len(_pieza(valores[0])) <= 8:
            pieza = _pieza(valores[0])
        else:
            pieza = abrev
        if filtro.get("excluir"):
            pieza = "SIN" + pieza
        if pieza:
            piezas.append(pieza)
    for codigo, modo in (receta.get("condiciones") or {}).items():
        modo = str(modo or "").upper()
        if str(codigo).upper() in CONDICIONES and modo in ("QUITAR", "SOLO"):
            abrev = CONDICIONES[str(codigo).upper()]["abrev"]
            piezas.append(("SIN" if modo == "QUITAR" else "SOLO") + abrev)
    return piezas


def nombre_archivo(idcartera: int, momento: datetime, canal: str, piezas: List[str], codigo: str,
                   largo: int = LARGO_NOMBRE) -> str:
    """CCC_DDMM-HHMM_TIPO_RESUMEN_CÓDIGO. Empieza por la cartera (el cargador de LunaTel la toma de los
    3 primeros dígitos) y termina en el código, que nunca se recorta: solo se acorta el resumen."""
    inicio = f"{int(idcartera):03d}_{momento:%d%m-%H%M}_{_pieza(canal) or 'OTRO'}"
    fin = f"_{codigo}"
    resumen = ""
    for pieza in piezas:
        candidato = f"{resumen}_{pieza}"
        if len(inicio) + len(candidato) + len(fin) > largo:
            break
        resumen = candidato
    return f"{inicio}{resumen}{fin}"



# ---------------------------------------------------------------------------------------------------------------
# Nombre de la base (24/11/2026, Hardy): corto y con lo que importa en la operación.
#   CCC DDMM HHMM · capital · mejor contacto del mes · tramo del score · timbrado · OSIPTEL · semáforo · código
#   p. ej. "112 2411 1249 K MAYOR 1K NOC SCORE AB TIM 24 OSIPTEL B51"
# El resto de los filtros (segmentos propios de cada cartera, condiciones del día) no va en el nombre: está en la
# receta guardada. El generador lo propone y el usuario lo corrige; fecha-hora y código se ponen al generar.
# Caracteres: letras, números, espacio, guion, guion bajo y + (sin puntos, comas, | ni /).
# ---------------------------------------------------------------------------------------------------------------
_NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")
# Tipo de base en el nombre (24/11/2026, Hardy): corto, el usuario lo puede cambiar
CANAL_NOMBRE = {"PRED": "PRD", "PREVIEW": "PRV", "IVR": "TTS", "SMS": "SMS", "OTRO": "OTRO"}
# Valores posibles de los campos que se nombran por "lo que queda" (los filtros de exclusión mandan lo quitado)
DOMINIO_NOMBRE = {
    "TRAMO": ["A", "B", "C", "D", "E"],
    "MG_CONTACTO_MES": ["CEF", "CNE", "NOC", "SIN_TIPO", "SG"],
    "OSIPTEL": ["SI", "SV", "NO", SIN_DATO],
    "TIMBRA": ["0", "1", "2", "3", "4", SIN_DATO],
    "COLOR": ["V", "T", "A", "PQ", "F", "R", SIN_DATO],
    "ESTADO_PDP": ["VIGENTE", "CAÍDA", "PAGADA", "SIN FECHA", "SIN PDP"],
    "SEGUIMIENTO_ACTUAL": ["VIGENTE", "HOY", "CAÍDO", "PDP VIGENTE", "PDP CAÍDA", "PDP PAGADA", "PDP SIN FECHA",
                           "SIN SEG"],
    "PDP_ANTERIOR": ["CAÍDA", "PAGADA", "VIGENTE", "SIN FECHA", "SIN PDP ANT"],
    "SEGUIMIENTO_MES": ["Este mes", "Mes anterior", "Hace 2-3 meses", "Hace 4-6 meses", "Más de 6 meses", "SIN SEG"],
    "MG_TEL_6M": ["TITULAR", "TERCERO_ACUERDO", "TERCERO", "FALLECIDO", "CONTESTA_SIN_ID", "NO_CONTESTA", "BUZON",
                  "APAGADO", "SIN_INFORMACION", "EQUIVOCADO", "NO_EXISTE", "NO_APLICA", "SIN_CLASIFICAR", "SIN_GESTION"],
}


def _limpio(texto: str) -> str:
    """Mayúsculas sin tildes; solo letras, números, espacio, - _ +. Lo demás pasa a espacio."""
    s = unicodedata.normalize("NFKD", str(texto or ""))
    s = "".join(ch for ch in s if not unicodedata.combining(ch)).upper()
    s = s.replace("–", "-").replace("—", "-")
    s = re.sub(r"[^A-Z0-9 \-_+]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _miles(numero: float) -> str:
    n = int(round(numero))
    return f"{n // 1000}K" if n >= 1000 and n % 1000 == 0 else str(n)


def _seleccion(filtro: Optional[Dict], dominio: Optional[List[str]] = None) -> Optional[List[str]]:
    """Valores que quedan con el filtro (None = sin filtro). En una exclusión: el dominio menos lo quitado."""
    if not filtro:
        return None
    valores = _texto_valores(filtro.get("valores"))
    if filtro.get("excluir"):
        if dominio is None:
            return None
        quitados = {v.upper() for v in valores}
        return [v for v in dominio if v.upper() not in quitados]
    return valores


def _tramos_capital() -> List[Tuple[float, Optional[float], str]]:
    """Tramos de la escala estándar de capital: (desde, hasta_siguiente, etiqueta), del menor al mayor."""
    tramos = []
    for etq, tope in TRAMOS_RANGO.get("CAPITAL") or []:
        m = _NUM.search(etq)
        tramos.append((float(m.group(0).replace(",", "")) if m else 0.0, tope, etq))
    return tramos


def _pieza_capital(filtros: Dict[str, Dict]) -> Optional[str]:
    """'Rango de capital' (escala estándar 1–7): K MAYOR 1K · K MENOR 20K · K 1K-5K · K MIX."""
    # Vigentes de Compartamos (fase 17): manda el capital del SAC del día si se filtró
    f = (filtros.get("RANGO_CAPITAL_SAC") or filtros.get("CAPITAL_SAC")
         or filtros.get("RANGO_CAPITAL") or filtros.get("CAPITAL"))
    if not f:
        return None
    escala = _tramos_capital()
    def indice(valor: str) -> Optional[int]:
        m = re.match(r"\s*(\d+)\.", str(valor))           # "3. [1,000 - 2,499.99]" → tramo 3 (1 = el menor)
        if m and 1 <= int(m.group(1)) <= len(escala):
            return int(m.group(1)) - 1
        n = _NUM.search(str(valor))                        # "1,000 – 2,499.99" (campo CAPITAL por tramos)
        if n:
            desde = float(n.group(0).replace(",", ""))
            for i, (d, _t, _e) in enumerate(escala):
                if abs(d - desde) < 0.5:
                    return i
        return None
    valores = _texto_valores(f.get("valores"))
    elegidos = {i for i in (indice(v) for v in valores) if i is not None}
    if f.get("excluir"):
        elegidos = set(range(len(escala))) - elegidos
    if not elegidos:
        return "K SIN INFO" if not f.get("excluir") and valores else None
    idx = sorted(elegidos)
    if len(idx) == len(escala):
        return None                                        # todos los tramos: el capital no distingue la base
    if idx != list(range(idx[0], idx[-1] + 1)):
        return "K MIX"
    desde, hasta = escala[idx[0]][0], escala[idx[-1]][1]
    if hasta is None:
        return f"K MAYOR {_miles(desde)}"
    if idx[0] == 0:
        return f"K MENOR {_miles(hasta)}"
    return f"K {_miles(desde)}-{_miles(hasta)}"


def _pieza_contacto(filtros: Dict[str, Dict]) -> str:
    """Mejor contacto del mes: CEF MES (solo CEF) · NOC (sin CEF) · CEF HIST (sin CEF del mes pero teléfonos con CEF
    en los últimos 6 meses) · MIX CONTACTO (todo o una mezcla con CEF).
    Las bases de recupero (25/11) se nombran por lo que las define: PDP CAIDA MES / HIST, SEG CAIDO MES / HIST."""
    pdp = _seleccion(filtros.get("ESTADO_PDP"), DOMINIO_NOMBRE["ESTADO_PDP"])
    if pdp is not None and {_limpio(v) for v in pdp} == {"CAIDA"}:
        return "PDP CAIDA MES"
    anterior = _seleccion(filtros.get("PDP_ANTERIOR"), DOMINIO_NOMBRE["PDP_ANTERIOR"])
    if anterior is not None and {_limpio(v) for v in anterior} == {"CAIDA"}:
        return "PDP CAIDA HIST"
    seg = _seleccion(filtros.get("SEGUIMIENTO_ACTUAL"), DOMINIO_NOMBRE["SEGUIMIENTO_ACTUAL"])
    if seg is not None and {_limpio(v) for v in seg} == {"CAIDO"}:
        cuando = _seleccion(filtros.get("SEGUIMIENTO_MES"), DOMINIO_NOMBRE["SEGUIMIENTO_MES"])
        if cuando is None:
            return "SEG CAIDO"
        meses = {_limpio(v) for v in cuando}
        if meses == {"ESTE MES"}:
            return "SEG CAIDO MES"
        return "SEG CAIDO HIST" if "ESTE MES" not in meses else "SEG CAIDO"
    quedan = _seleccion(filtros.get("MG_CONTACTO_MES"), DOMINIO_NOMBRE["MG_CONTACTO_MES"])
    if quedan is None:
        return "MIX CONTACTO"
    tipos = {v.upper() for v in quedan}
    if tipos == {"CEF"}:
        return "CEF MES"
    if "CEF" not in tipos:
        tel = _seleccion(filtros.get("MG_TEL_6M"), DOMINIO_NOMBRE["MG_TEL_6M"])
        if tel and {v.upper() for v in tel} <= {"TITULAR", "TERCERO_ACUERDO"}:
            return "CEF HIST"
        return "NOC"
    return "MIX CONTACTO"


def _pieza_score(filtros: Dict[str, Dict]) -> str:
    quedan = _seleccion(filtros.get("TRAMO"), DOMINIO_NOMBRE["TRAMO"])
    letras = sorted({v.upper() for v in (quedan or []) if v.upper() in DOMINIO_NOMBRE["TRAMO"]})
    if not letras or len(letras) == len(DOMINIO_NOMBRE["TRAMO"]):
        return "MIX SCORE"
    return "SCORE " + "".join(letras)


def _pieza_osiptel(filtros: Dict[str, Dict]) -> Optional[str]:
    quedan = _seleccion(filtros.get("OSIPTEL"), DOMINIO_NOMBRE["OSIPTEL"])
    if quedan is None:
        return None
    q = {v.upper() for v in quedan} - {SIN_DATO}
    if q and "NO" not in q and "SI" in q:
        return "OSIPTEL"                                   # SI o SI + SV
    if q == {"NO"}:
        return "OSP NO"
    return "OSP " + "".join(sorted(q)) if q else "OSP SD"


def _pieza_combinacion(filtros: Dict[str, Dict], codigo: str, etiqueta: str) -> Optional[str]:
    """Timbrado y semáforo: lo que queda, junto (TIM 24, SEM VAP)."""
    quedan = _seleccion(filtros.get(codigo), DOMINIO_NOMBRE[codigo])
    if quedan is None:
        return None
    q = [v.upper() for v in quedan if v.upper() != SIN_DATO]
    if codigo == "COLOR":
        q = ["P" if v in ("PQ", "P", "Q") else v for v in q]
    q = list(dict.fromkeys(q))
    return f"{etiqueta} {''.join(q)}" if q else f"{etiqueta} SD"


def nombre_legible(cartera: str, canal: str, receta: Dict, catalogo: Dict[str, CampoMeta],
                   momento: Optional[datetime] = None) -> str:
    """Propuesta de nombre sin el código: '112 2411 1249 PRD K MAYOR 1K NOC SCORE AB TIM 24 OSIPTEL'.
    catalogo queda en la firma por compatibilidad; el nombre no lo usa."""
    filtros = {str(f.get("campo") or "").upper(): f for f in (receta.get("filtros") or [])}
    codigo, _, resto = str(cartera).partition(" ")      # combinada: "126 VIGMIX" → la abreviatura va tras la fecha
    canal_corto = CANAL_NOMBRE.get(str(canal or "").upper())
    piezas = [f"{codigo} {(momento or datetime.now()):%d%m %H%M}", canal_corto, resto or None,
              _pieza_capital(filtros), _pieza_contacto(filtros), _pieza_score(filtros),
              _pieza_combinacion(filtros, "TIMBRA", "TIM"), _pieza_osiptel(filtros),
              _pieza_combinacion(filtros, "COLOR", "SEM")]
    return _limpio(" ".join(p for p in piezas if p))


def nombre_final(propuesto_o_editado: str, cartera: str, codigo: str, momento: Optional[datetime] = None,
                 largo: int = 120) -> str:
    """Nombre que se guarda: cartera, fecha-hora de generación (DDMM HHMM), lo que dejó el usuario y el código
    (que nunca se recorta). La fecha y el código se ponen solos: si el texto ya los trae, se reemplazan."""
    nombre = _limpio(propuesto_o_editado)
    nombre = re.sub(r"\s*\bB\d+$", "", nombre)                         # un código que el usuario haya escrito
    if nombre.startswith(cartera):
        nombre = nombre[len(cartera):].strip()
    nombre = re.sub(r"^\d{4}[ \-]\d{4}\s*", "", nombre)                # la fecha-hora de la propuesta
    inicio = f"{cartera} {momento:%d%m %H%M}" if momento is not None else cartera
    fin = f" {codigo}"
    cuerpo = f"{inicio} {nombre}".strip()
    return cuerpo[: largo - len(fin)].rstrip(" -_") + fin
