from __future__ import annotations

import logging
import math
import re
from collections import Counter
import unicodedata
from datetime import date, datetime
from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor
from time import perf_counter
from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy import text

from app.core.db_siscob import engine_siscob

logger = logging.getLogger(__name__)

# Prefiltro por indice en gestiones/compromisos. El filtro exacto original (LTRIM/RTRIM) se conserva en la
# consulta; el prefiltro solo reduce las filas que SQL Server debe revisar. Poner False para volver al comportamiento anterior.
RADAR_PREFILTRO_SARGABLE = True

CT_FORMULAS = {
    "cuota_1": ["CT1", "CT11", "CT12", "CT13", "CT14", "CT15"],
    "cuota_2": ["CT2", "CT21", "CT22", "CT23", "CT24", "CT25"],
    "cuota_3": ["CT3", "CT31", "CT32", "CT33", "CT34", "CT35"],
}

# Atraso proyectado = dias de atraso al inicio (compartamos_grupal) + este valor.
DIAS_PROYECCION_ATRASO = 31

# Calificacion de provision (compartamos_grupal.Cal_PROV). Definicion dada por negocio.
CALIFICACION_PROVISION = {
    0: "Normal",
    1: "CPP",
    2: "Deficiente",
    3: "Dudoso 1",
    4: "Dudoso 2",
    5: "Pérdida",
}

# Dias de producto -> cuotas que debe pagar el grupo (siempre las mas atrasadas).
CUOTAS_A_PAGAR_POR_PRODUCTO = {14: 2, 28: 1}

# Columnas de compartamos_grupal que usa el modulo. Los nombres alternativos cubren
# diferencias de acentos, espacios o simbolos; si ninguno existe se informa.
CAMPOS_GRUPAL = {
    "comite": ("COMITÉ", "COMITE"),
    "fec_ult_pago": ("FecUltPago",),
    "cal_prov": ("Cal_PROV", "CalPROV"),
    "producto_camp": ("ProductoCamp",),
    "pct_campana": ("% Campaña Cliente",),
    "pct_campana_100": ("% Campaña Cliente 100%",),
    "pct_cancelacion": ("% Cancelación Cliente", "% Cancelacion Cliente"),
    "rango_atraso": ("Rang_AtrasoCtaGru",),
    "dias_atraso_inicio": ("DiasAtraso",),
    "cuotas_aprobadas": ("NroCuotas_Aprobadas",),
    "cuotas_pagadas": ("NroCuotasPagadas",),
}

COMPARTAMOS_CARTERAS = {
    124: "CASTIGO INDIVIDUAL",
    126: "VIGENTE INDIVIDUAL",
    128: "VIGENTE CCM",
    133: "VIGENTE GRUPAL",
    144: "CASTIGO GRUPAL",
}


def construir_respuesta_crm(rows: List[Dict[str, Any]], valor_buscado: str,
                           carteras_por_dni: Optional[Dict[str, set[int]]] = None) -> Dict[str, Any]:
    inicio = perf_counter()
    tiempos_fuentes: Dict[str, float] = {}
    tipo_resultado = resolver_tipo_resultado(rows, valor_buscado)
    operaciones_rows = deduplicar_operaciones(rows)
    operaciones = [normalizar_operacion(row) for row in operaciones_rows]
    principal = operaciones_rows[0]
    advertencias: List[str] = []

    if operaciones_grupo_por_asignacion(rows):
        advertencias.append(
            "Una o más operaciones se tratan como grupales porque figuran en compartamos_grupal, "
            "aunque SAC las trae con código de grupo 0 o vacío."
        )

    dni = texto(campo(principal, "DNI"))
    dnis = []
    for row in rows:
        value = texto(campo(row, "DNI"))
        if value and value not in dnis:
            dnis.append(value)
    codcliente = texto(campo(principal, "codcliente", "CodCliente"))
    codigos_operacion = [item["operacion"] for item in operaciones if item.get("operacion")]

    gestion = estructura_gestion_vacia()
    pagos = estructura_pagos_vacia()
    pdp = estructura_pdp_vacia()
    cronograma = estructura_cronograma_vacia()
    grupal: Dict[str, Any] = {"disponible": False, "por_dni": {}, "columnas": set(), "advertencias": []}

    # Las fuentes son independientes entre si: se consultan a la vez (cada una con su conexion).
    def medir_fuente(clave: str, funcion):
        inicio_f = perf_counter()
        try:
            return funcion()
        finally:
            tiempos_fuentes[clave] = (perf_counter() - inicio_f) * 1000

    def fuente_grupal():
        codigos = codigos_grupo(rows)
        operaciones_grupo = operaciones_grupo_por_asignacion(rows)
        avisos: List[str] = []
        datos = grupal
        try:
            datos = medir_fuente("grupal_ms", lambda: construir_datos_grupal(consultar_datos_grupal(codigos)))
            avisos.extend(datos.get("advertencias", []))
        except Exception:
            avisos.append("No se pudo consultar compartamos_grupal (rol, último pago, calificación y campañas).")
        crono = cronograma
        try:
            crono = medir_fuente("cronograma_ms", lambda: construir_cronograma_cuotas(consultar_cronograma_grupo(codigos, operaciones_grupo), dnis, datos.get("por_dni", {})))
            avisos.extend(crono.pop("advertencias", []))
        except Exception:
            avisos.append("No se pudo consultar el cronograma de cuotas atrasadas del grupo.")
        return datos, crono, avisos

    tareas: Dict[str, Any] = {
        "gestion": lambda: medir_fuente("gestion_ms", lambda: consultar_gestiones(dnis, carteras_por_dni=carteras_por_dni)),
        "pagos": lambda: medir_fuente("pagos_ms", lambda: consultar_pagos(dni, codcliente, codigos_operacion)),
        "pdp": lambda: medir_fuente("pdp_ms", lambda: consultar_pdp(dni, codigos_operacion)),
        "cal": lambda: medir_fuente("calificacion_ms", lambda: consultar_calificacion_asignacion(dnis)),
    }
    if tipo_resultado == "GRUPO":
        tareas["grupal"] = fuente_grupal
    with ThreadPoolExecutor(max_workers=len(tareas)) as pool:
        futuros = {nombre: pool.submit(tarea) for nombre, tarea in tareas.items()}
        resultados: Dict[str, Any] = {}
        for nombre, futuro in futuros.items():
            try:
                resultados[nombre] = futuro.result()
            except Exception:
                resultados[nombre] = None
    if resultados.get("gestion") is not None:
        gestion = resultados["gestion"]
    else:
        advertencias.append("No se pudo consultar la actividad de cobranza en SISCOB.")
    if resultados.get("pagos") is not None:
        pagos = resultados["pagos"]
    else:
        advertencias.append("No se pudo consultar la fuente operativa de pagos.")
    if resultados.get("pdp") is not None:
        pdp = resultados["pdp"]
    else:
        advertencias.append("No se pudo consultar la fuente operativa de compromisos.")
    if tipo_resultado == "GRUPO" and resultados.get("grupal") is not None:
        grupal, cronograma, avisos_grupo = resultados["grupal"]
        advertencias.extend(avisos_grupo)
    if resultados.get("cal") is not None:
        asignacion_cal = resultados["cal"]
        advertencias.extend(asignacion_cal.pop("advertencias", []))
    else:
        asignacion_cal = {"por_dni": {}}
        advertencias.append("No se pudo consultar la calificación/segmentación en las tablas de asignación.")
    for fila_op, operacion_item in zip(operaciones_rows, operaciones):
        aplicar_calificacion(operacion_item, clave_documento(campo(fila_op, "DNI")), operacion_item.get("operacion"),
                             asignacion_cal, grupal)

    situacion = construir_situacion(operaciones)
    contacto = construir_contacto(rows)
    grupo = construir_contexto_grupo(rows)
    campanas = construir_campanas(operaciones)
    contencion = construir_contencion(pagos)
    cliente = construir_cliente(rows, operaciones)
    if operaciones:
        # Cada operacion trae su propia calificacion/cartera. En la cabecera solo se muestra un valor
        # si todas las operaciones coinciden; si no, se remite al detalle por operacion.
        claves = {(o.get("tipo_calificacion"), o.get("calificacion"), o.get("cartera_calificacion")) for o in operaciones}
        if len(claves) == 1:
            for campo_cal in ("calificacion", "tipo_calificacion", "fuente_calificacion", "cartera_calificacion"):
                cliente[campo_cal] = operaciones[0].get(campo_cal)
        else:
            cliente["calificacion"] = "Según operación"
            cliente["tipo_calificacion"] = "Calificación"
            cliente["cartera_calificacion"] = None
    informacion_adicional = construir_informacion_adicional(rows)

    respuesta = {
        "encontrado": True,
        "tipo_resultado": tipo_resultado,
        "criterio_busqueda": resolver_criterio_busqueda(rows, valor_buscado),
        "cliente": cliente,
        "situacion": situacion,
        "cobranza": {
            "gestionado_hoy": gestion.get("gestionado_hoy"),
            "gestionado_mes": gestion.get("gestionado_mes"),
            "ultima_gestion": gestion.get("ultima_gestion"),
            "resultado": gestion.get("resultado"),
            "contacto": gestion.get("contacto"),
            "agente": gestion.get("agente"),
            "canal": gestion.get("canal"),
            "mejor_gestion": None,
            "mejor_gestion_disponible": False,
        },
        "campanas": campanas,
        "contencion": contencion,
        "gestion": gestion,
        "pagos_pdp": {"pagos": pagos, "pdp": pdp},
        "contacto": contacto,
        "grupo": grupo,
        "operaciones": operaciones,
        "integrantes": aplicar_calificacion_integrantes(
            aplicar_datos_grupal(construir_integrantes(operaciones_rows, gestion.get("por_dni", {})), grupal),
            asignacion_cal, grupal) if tipo_resultado == "GRUPO" else [],
        "cronograma_cuotas": cronograma,
        "informacion_adicional": informacion_adicional,
        "fuentes": {
            "asignacion": {"disponible": True, "fuente": "VW_CLIENTE_CRM_SAC"},
            "gestion": {"disponible": gestion.get("disponible", False), "fuente": "SISCOB"},
            "pagos": {"disponible": pagos.get("disponible", False), "fuente": "PAGOS_BI_NORMALIZADO"},
            "pdp": {"disponible": pdp.get("disponible", False), "fuente": "SISCOB.COMPROMISO"},
        },
        "advertencias": advertencias,
        "total": len(operaciones),
    }
    resultado = serializar(respuesta)
    total_ms = (perf_counter() - inicio) * 1000
    if total_ms >= 2000:
        logger.warning("Radar detalle lento tipo=%s integrantes=%d fuentes_ms=%s total_ms=%.0f",
                       tipo_resultado, len(dnis),
                       {nombre: round(ms) for nombre, ms in tiempos_fuentes.items()}, total_ms)
    return resultado


def resolver_tipo_resultado(rows: List[Dict[str, Any]], valor_buscado: str) -> str:
    buscado = identificador(valor_buscado)
    for row in rows:
        for key in ("CodigoGrupo", "CodCreGrupal"):
            value = campo(row, key)
            if identificador_grupo_valido(value) and identificador(value) == buscado:
                return "GRUPO"
    return "CLIENTE"


def resolver_criterio_busqueda(rows: List[Dict[str, Any]], valor_buscado: str) -> str:
    buscado = identificador(valor_buscado)
    criterios = [
        ("DNI", ("DNI",)),
        ("CODIGO_CLIENTE", ("codcliente", "CodCliente")),
        ("OPERACION", ("CodOperacion", "Operacion")),
        ("CODIGO_GRUPO", ("CodigoGrupo",)),
        ("CREDITO_GRUPAL", ("CodCreGrupal",)),
    ]
    for nombre, keys in criterios:
        if any(identificador(campo(row, *keys)) == buscado for row in rows):
            return nombre
    return "OTRO"


def deduplicar_operaciones(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    resultado: List[Dict[str, Any]] = []
    indices: Dict[str, int] = {}
    for index, row in enumerate(rows):
        operacion = identificador(campo(row, "CodOperacion", "Operacion"))
        key = operacion or f"sin-operacion-{index}"
        if key not in indices:
            indices[key] = len(resultado)
            resultado.append(dict(row))
            continue
        actual = resultado[indices[key]]
        for nombre, value in row.items():
            if vacio(actual.get(nombre)) and not vacio(value):
                actual[nombre] = value
    return resultado


def normalizar_operacion(row: Dict[str, Any]) -> Dict[str, Any]:
    cuotas = {nombre: calcular_cuota_visual(row, campos) for nombre, campos in CT_FORMULAS.items()}
    alternativas = []
    agregar_alternativa(alternativas, "Monto cuota", numero(campo(row, "MtoCuota", "MTOCUOTA")), "ASIGNACION")
    for nombre, etiqueta in (("cuota_1", "Cuota 1"), ("cuota_2", "Cuota 2"), ("cuota_3", "Cuota 3")):
        if cuotas[nombre]["disponible"]:
            agregar_alternativa(alternativas, etiqueta, cuotas[nombre]["valor"], "CALCULO_VISUAL")

    campos_campana = {
        "Camp 1 cuota": ("Camp_1_Cuota", "Camp1Cuota"),
        "Camp 2 cuota": ("Camp_2_Cuota", "Camp2Cuota"),
        "Camp 3 cuota": ("Camp_3_Cuota", "Camp3Cuota"),
        "Cancelacion": ("Cancelacion", "CANCELACION"),
        "Monto pagar": ("Monto_Pagar", "MontoPagar"),
        "Camp cancelacion integrantes": ("Camp_Canc_Integrantes",),
        "Camp cancelacion grupo": ("Camp_Canc_Grupo",),
    }
    for etiqueta, keys in campos_campana.items():
        agregar_alternativa(alternativas, etiqueta, numero(campo(row, *keys)), "ASIGNACION")

    return {
        "operacion": texto(campo(row, "CodOperacion", "Operacion")),
        "producto": texto(campo(row, "Producto")),
        "linea_negocio": texto(campo(row, "Linea_Negocio", "LineaNegocio")),
        "oficina": texto(campo(row, "NomOficina")),
        "territorio": texto(campo(row, "Territorio")),
        "segmento": texto(campo(row, "SEGMENTO", "Segmento")),
        "condicion": texto(campo(row, "Condicion")),
        "calificacion": None,
        "tipo_calificacion": None,
        "score": numero(campo(row, "SCORE", "Score")),
        "tramo": texto(campo(row, "Tramo")),
        "dias_atraso": numero(campo(row, "DiasAtraso")),
        "deuda_total": numero(campo(row, "Deuda_Total")),
        "capital": numero(campo(row, "SdoCapital")),
        "capital_vencido": numero(campo(row, "SdoCapitalVencido")),
        "monto_desembolso": numero(campo(row, "MtoCapDesembolso")),
        "fecha_desembolso": fecha_iso(campo(row, "FecDesemb")),
        "cuotas_aprobadas": entero(campo(row, "NroCuotas_Aprobadas")),
        "cuotas_atrasadas": entero(campo(row, "Nro_CuotasAtrasadas")),
        "cuotas_vencidas": entero(campo(row, "Nro_CuotasVencidas")),
        "ultima_cuota_atrasada": texto(campo(row, "Ult_CuotaAtrasada", "ULT_CUOTAATRASADA")),
        "monto_cuota": numero(campo(row, "MtoCuota", "MTOCUOTA")),
        "monto_capital_vencido_cuota": numero(campo(row, "MontoCapVenCuot")),
        "fecha_ultimo_pago_asignacion": fecha_iso(campo(row, "FecUltPago")),
        "ultimo_vencimiento": fecha_iso(campo(row, "UltFecVen")),
        "fecha_castigo": fecha_iso(campo(row, "FecCastigo")),
        "convenio_vigente": texto(campo(row, "Convenio_Vigente")),
        "pagos_no_contabilizados": numero(campo(row, "Pagos_no_Contabilizados")),
        "cuotas_calculadas": cuotas,
        "alternativas_cobro": alternativas,
        "contencion": {"disponible": False},
    }


def calcular_cuota_visual(row: Dict[str, Any], campos: Iterable[str]) -> Dict[str, Any]:
    valores_originales = [campo(row, nombre) for nombre in campos]
    disponibles = [value for value in valores_originales if not vacio(value)]
    total = sum(numero(value) or 0 for value in valores_originales)
    return {
        "valor": round(total, 2),
        "disponible": bool(disponibles),
        "componentes_disponibles": len(disponibles),
        "componentes_totales": len(valores_originales),
    }


def agregar_alternativa(items: List[Dict[str, Any]], nombre: str, monto: Optional[float], fuente: str) -> None:
    if monto is None or monto <= 0:
        return
    items.append({"nombre": nombre, "monto": round(monto, 2), "fuente": fuente})


def construir_cliente(rows: List[Dict[str, Any]], operaciones: List[Dict[str, Any]]) -> Dict[str, Any]:
    principal = rows[0]
    return {
        "nombre": texto(campo(principal, "NomCliente")),
        "dni": texto(campo(principal, "DNI")),
        "codigo_cliente": texto(campo(principal, "codcliente", "CodCliente")),
        "edad": entero(campo(principal, "Edad")),
        "sexo": texto(campo(principal, "SexoCliente")),
        "oficina": texto(campo(principal, "NomOficina")),
        "territorio": texto(campo(principal, "Territorio")),
        "segmento": texto(campo(principal, "SEGMENTO", "Segmento")),
        "linea_negocio": texto(campo(principal, "Linea_Negocio", "LineaNegocio")),
        "producto_principal": texto(campo(principal, "Producto")),
        "calificacion": None,
        "tipo_calificacion": None,
        "condicion": texto(campo(principal, "Condicion")),
        "score": numero(campo(principal, "SCORE", "Score")),
        "tiene_grupo": construir_contexto_grupo(rows).get("disponible", False),
        "cantidad_operaciones": len(operaciones),
    }


def construir_situacion(operaciones: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "cantidad_operaciones": len(operaciones),
        "deuda_actual": sumar_conocidos(item.get("deuda_total") for item in operaciones),
        "capital": sumar_conocidos(item.get("capital") for item in operaciones),
        "capital_vencido": sumar_conocidos(item.get("capital_vencido") for item in operaciones),
        "monto_desembolso": sumar_conocidos(item.get("monto_desembolso") for item in operaciones),
        "mora_maxima": maximo_conocido(item.get("dias_atraso") for item in operaciones),
        "ultimo_pago_asignacion": max_fecha(item.get("fecha_ultimo_pago_asignacion") for item in operaciones),
    }


def construir_contacto(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    principal = rows[0]
    telefonos = []
    for row in rows:
        for key in ("Telef_01", "Telef_02", "Telef_03", "Telef_04"):
            value = texto(campo(row, key))
            if value and value != "0" and value not in telefonos:
                telefonos.append(value)
    return {
        "telefono_principal": telefonos[0] if telefonos else None,
        "telefonos_adicionales": telefonos[1:],
        "direccion_principal": texto(campo(principal, "Direccion_Principal")),
        "distrito": texto(campo(principal, "Distrito_Principal")),
        "direccion_vivienda": texto(campo(principal, "Direccion_Vivienda")),
        "direccion_negocio": texto(campo(principal, "Direccion_Negocio")),
    }


def construir_contexto_grupo(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    principal = next((row for row in rows if any(identificador_grupo_valido(campo(row, key)) for key in ("CodigoGrupo", "CodCreGrupal", "NombreGrupo"))), rows[0])
    codigo = texto(campo(principal, "CodigoGrupo"))
    credito = texto(campo(principal, "CodCreGrupal"))
    nombre = texto(campo(principal, "NombreGrupo"))
    disponible = any(identificador_grupo_valido(value) for value in (codigo, credito, nombre))
    return {
        "disponible": disponible,
        "nombre": nombre if identificador_grupo_valido(nombre) else None,
        "codigo_grupo": codigo if identificador_grupo_valido(codigo) else None,
        "credito_grupal": credito if identificador_grupo_valido(credito) else None,
        "oficina": texto(campo(principal, "NomOficina")),
        "territorio": texto(campo(principal, "Territorio")),
        "producto": texto(campo(principal, "Producto")),
        "linea_negocio": texto(campo(principal, "Linea_Negocio")),
    }


def construir_campanas(operaciones: List[Dict[str, Any]]) -> Dict[str, Any]:
    items = []
    for operacion in operaciones:
        alternativas_asignacion = [item for item in operacion.get("alternativas_cobro", []) if item.get("fuente") == "ASIGNACION" and item.get("nombre") != "Monto cuota"]
        if alternativas_asignacion:
            items.append({"operacion": operacion.get("operacion"), "alternativas": alternativas_asignacion})
    return {"disponible": bool(items), "items": items, "fuente": "ASIGNACION"}


def construir_contencion(pagos: Dict[str, Any]) -> Dict[str, Any]:
    capital_pago = pagos.get("capital_contenido_pago") if pagos.get("disponible") else None
    return {
        "disponible": capital_pago is not None,
        "capital_evaluado": None,
        "monto_requerido": None,
        "capital_contenido_pago": capital_pago,
        "capital_contenido_pdp": None,
        "cumple_pago": None,
        "cumple_pdp": None,
        "operacion_contenedora": None,
        "cliente_contenedor": None,
        "regla_contenedor_disponible": False,
        "fuente": "PAGOS_BI_NORMALIZADO" if capital_pago is not None else None,
    }


def construir_informacion_adicional(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    principal = rows[0]
    return limpiar_vacios({
        "fecha_nacimiento": fecha_iso(campo(principal, "FecNacimiento")),
        "edad": entero(campo(principal, "Edad")),
        "sexo": texto(campo(principal, "SexoCliente")),
        "actividad_economica": texto(campo(principal, "Actividad_Economica", "ActividadEconomica")),
        "rubro": texto(campo(principal, "Rubro")),
        "vivienda": texto(campo(principal, "Vivienda")),
        "direccion_negocio": texto(campo(principal, "Direccion_Negocio")),
        "conyuge": texto(campo(principal, "Conyuge")),
        "avales": texto(campo(principal, "Avales")),
        "rcc": texto(campo(principal, "RCC")),
        "score": numero(campo(principal, "SCORE")),
        "fecha_carga": fecha_iso(campo(principal, "FechaCarga")),
        "mes_asignacion": texto(campo(principal, "Mes_Asignacion")),
    })


def construir_integrantes(rows: List[Dict[str, Any]], gestion_por_dni: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    gestion_por_dni = gestion_por_dni or {}
    grupos: Dict[str, List[Dict[str, Any]]] = {}
    for index, row in enumerate(rows):
        key = identificador(campo(row, "DNI")) or identificador(campo(row, "codcliente")) or f"integrante-{index}"
        grupos.setdefault(key, []).append(row)

    integrantes = []
    for filas in grupos.values():
        operaciones = [normalizar_operacion(item) for item in deduplicar_operaciones(filas)]
        principal = filas[0]
        dni = texto(campo(principal, "DNI"))
        integrantes.append({
            "nombre": texto(campo(principal, "NomCliente")),
            "dni": dni,
            "codigo_cliente": texto(campo(principal, "codcliente")),
            "rol": texto(campo(principal, "Rol", "CargoIntegrante")),
            "operaciones": operaciones,
            "deuda": sumar_conocidos(item.get("deuda_total") for item in operaciones),
            "capital": sumar_conocidos(item.get("capital") for item in operaciones),
            "capital_vencido": sumar_conocidos(item.get("capital_vencido") for item in operaciones),
            "mora": maximo_conocido(item.get("dias_atraso") for item in operaciones),
            "cuotas_vencidas": maximo_conocido(item.get("cuotas_vencidas") for item in operaciones),
            "ultimo_pago_asignacion": max_fecha(item.get("fecha_ultimo_pago_asignacion") for item in operaciones),
            "calificacion": None,
        "tipo_calificacion": None,
            "contencion": {"disponible": False},
            "gestion": gestion_por_dni.get(identificador(dni), {"gestionado_hoy": False, "gestionado_mes": 0}),
        })
    return integrantes


MARCA_GRUPO_ASIGNACION = "_grupo_asignacion"


def operaciones_grupo_por_asignacion(rows: List[Dict[str, Any]]) -> List[str]:
    """Codigos de operacion (tal como los trae SAC) cuyo grupo se tomo de compartamos_grupal."""
    ops: List[str] = []
    for row in rows:
        if row.get(MARCA_GRUPO_ASIGNACION):
            op = identificador(campo(row, "CodOperacion", "Operacion"))
            if op and op not in ops:
                ops.append(op)
    return ops


def clave_dni_operacion(row: Dict[str, Any]) -> tuple:
    return (clave_documento(campo(row, "DNI", "NumDocumento")), clave_documento(campo(row, "CodOperacion", "Operacion")))


def consultar_asignacion_grupal(dnis: List[str], grupo: Optional[str]) -> List[Dict[str, Any]]:
    """Filas de compartamos_grupal de los DNI dados y/o del grupo (CodigoGrupo o CodCreGrupal) buscado."""
    dnis = [identificador(value) for value in dnis if identificador(value)]
    if not dnis and not grupo:
        return []
    with engine_siscob.connect() as conn:
        reales = columnas_reales_tabla(conn, "compartamos_grupal")

        def col(*nombres: str) -> Optional[str]:
            return next((reales[clave_columna(n)] for n in nombres if clave_columna(n) in reales), None)

        c_dni, c_op = col("NumDocumento", "DNI"), col("Operacion", "CodOperacion")
        c_grupo, c_cred, c_nombre = col("CodigoGrupo"), col("CodCreGrupal"), col("NomGrupo", "NombreGrupo")
        if not c_dni or not c_op:
            raise RuntimeError("compartamos_grupal no tiene las columnas de documento u operación esperadas")
        sel = lambda c: f"[{c}]" if c else "NULL"  # noqa: E731
        params: Dict[str, Any] = {}
        condiciones: List[str] = []
        if dnis:
            variantes = variantes_documento(dnis)
            params.update({f"d{i}": v for i, v in enumerate(variantes)})
            condiciones.append(f"[{c_dni}] IN (" + ", ".join(f"CAST(:d{i} AS VARCHAR(40))" for i in range(len(variantes))) + ")")
        if grupo and (c_grupo or c_cred):
            params["g"] = grupo
            for c in (c_grupo, c_cred):
                if c:
                    condiciones.append(f"[{c}] = CAST(:g AS VARCHAR(40))")
        if not condiciones:
            return []
        query = text(f"""
            SELECT {sel(c_dni)} AS dni, {sel(c_op)} AS operacion, {sel(c_grupo)} AS codigo_grupo,
                   {sel(c_cred)} AS credito_grupal, {sel(c_nombre)} AS nombre_grupo
            FROM Desarrollo.dbo.compartamos_grupal WITH(NOLOCK)
            WHERE {" OR ".join(condiciones)}
        """)
        return [dict(row) for row in conn.execute(query, params).mappings().all()]


def aplicar_grupo_asignacion(fila: Dict[str, Any], asignacion: Dict[str, Any]) -> None:
    """Completa el grupo de la fila con el de compartamos_grupal cuando SAC lo trae en 0 o vacio.
    Nunca pisa un codigo de grupo valido de SAC."""
    completo = False
    for destino, origen in (("CodigoGrupo", "codigo_grupo"), ("CodCreGrupal", "credito_grupal"), ("NombreGrupo", "nombre_grupo")):
        nuevo = asignacion.get(origen)
        if not identificador_grupo_valido(nuevo):
            continue
        clave = next((k for k in fila if clave_columna(k) == clave_columna(destino)), destino)
        if not identificador_grupo_valido(fila.get(clave)):
            fila[clave] = texto(nuevo)
            completo = True
    if completo:
        fila[MARCA_GRUPO_ASIGNACION] = True


def consultar_filas_vista_por_operacion(cursor, faltantes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Filas de VW_CLIENTE_CRM_SAC de operaciones concretas (se busca por DNI y se filtra por operacion)."""
    dnis = []
    for item in faltantes:
        dni = identificador(item.get("dni"))
        if dni and dni not in dnis:
            dnis.append(dni)
    if not dnis:
        return []
    variantes = variantes_documento(dnis)
    cursor.execute(
        "SELECT * FROM VW_CLIENTE_CRM_SAC WITH(NOLOCK) WHERE DNI IN (" + ", ".join("?" for _ in variantes) + ")",
        variantes,
    )
    columnas = [c[0] for c in cursor.description]
    quiero = {clave_dni_operacion(item) for item in faltantes}
    return [fila for fila in (dict(zip(columnas, r)) for r in cursor.fetchall()) if clave_dni_operacion(fila) in quiero]


def incorporar_asignacion_grupal(cursor, filas: List[Dict[str, Any]], valor: Any) -> List[Dict[str, Any]]:
    """Regla de negocio: si la operacion esta en la asignacion grupal (compartamos_grupal), es grupal,
    aunque SAC la traiga con CodigoGrupo 0.
      1) a las filas que ya trae la vista se les completa el grupo desde compartamos_grupal;
      2) si se busca un grupo, se agregan los integrantes que SAC no asocia a ese grupo."""
    buscado = identificador(valor)
    dnis = []
    for fila in filas:
        dni = identificador(campo(fila, "DNI"))
        if dni and dni not in dnis:
            dnis.append(dni)
    grupo = buscado if buscado.isdigit() else None
    try:
        asignaciones = consultar_asignacion_grupal(dnis, grupo)
    except Exception:
        logger.exception("No se pudo leer compartamos_grupal para completar el grupo del Radar")
        return filas
    por_clave: Dict[tuple, Dict[str, Any]] = {}
    for item in asignaciones:
        por_clave.setdefault(clave_dni_operacion(item), item)
    for fila in filas:
        item = por_clave.get(clave_dni_operacion(fila))
        if item:
            aplicar_grupo_asignacion(fila, item)
    if not grupo:
        return filas
    presentes = {clave_dni_operacion(fila) for fila in filas}
    faltantes = [
        item for clave, item in por_clave.items()
        if clave not in presentes and grupo in (identificador(item.get("codigo_grupo")), identificador(item.get("credito_grupal")))
    ]
    if not faltantes:
        return filas
    try:
        nuevas = consultar_filas_vista_por_operacion(cursor, faltantes)
    except Exception:
        logger.exception("No se pudieron leer de la vista los integrantes de compartamos_grupal")
        return filas
    asignacion_de = {clave_dni_operacion(item): item for item in faltantes}
    for fila in nuevas:
        aplicar_grupo_asignacion(fila, asignacion_de[clave_dni_operacion(fila)])
    combinadas = filas + nuevas
    combinadas.sort(key=lambda f: (-(numero(campo(f, "DiasAtraso")) or 0), -(numero(campo(f, "Deuda_Total")) or 0)))
    return combinadas


def codigos_grupo(rows: List[Dict[str, Any]]) -> List[str]:
    codigos: List[str] = []
    for row in rows:
        value = campo(row, "CodigoGrupo")
        if identificador_grupo_valido(value) and identificador(value) not in codigos:
            codigos.append(identificador(value))
    return codigos


def clave_columna(nombre: Any) -> str:
    """Nombre de columna comparable: sin acentos, espacios ni signos (conserva %)."""
    base = unicodedata.normalize("NFKD", str(nombre))
    base = "".join(char for char in base if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9%]", "", base.lower())


def indexar_fila(fila: Dict[str, Any]) -> Dict[str, Any]:
    return {clave_columna(clave): valor for clave, valor in fila.items()}


def valor_columna(indice: Dict[str, Any], *nombres: str) -> Any:
    for nombre in nombres:
        valor = indice.get(clave_columna(nombre))
        if not vacio(valor):
            return valor
    return None


def existe_columna(indice: Dict[str, Any], *nombres: str) -> bool:
    return any(clave_columna(nombre) in indice for nombre in nombres)


def etiqueta_calificacion(valor: Any) -> Optional[str]:
    numero_cal = entero(valor)
    if numero_cal in CALIFICACION_PROVISION:
        return f"{numero_cal}-{CALIFICACION_PROVISION[numero_cal]}"
    return texto(valor)


def consultar_datos_grupal(codigos: List[str]) -> List[Dict[str, Any]]:
    """Filas de Desarrollo.dbo.compartamos_grupal del grupo (asignacion inicial)."""
    if not codigos:
        return []
    params = {f"grupo_{index}": codigo for index, codigo in enumerate(codigos)}
    marcadores = ", ".join(f":{key}" for key in params)
    query = text(f"""
        SELECT *
        FROM Desarrollo.DBO.compartamos_grupal C WITH(NOLOCK)
        WHERE C.CodigoGrupo IN ({marcadores})
    """)
    with engine_siscob.connect() as conn:
        return [dict(row) for row in conn.execute(query, params).mappings().all()]


def columna_parecida(indice: Dict[str, Any], campo_id: str) -> Optional[str]:
    """Respaldo para los % de campana si el nombre real de la columna difiere del esperado."""
    for clave in indice:
        if campo_id == "pct_campana_100" and "campana" in clave and "100" in clave:
            return clave
        if campo_id == "pct_campana" and "campana" in clave and "cliente" in clave and "100" not in clave:
            return clave
        if campo_id == "pct_cancelacion" and "cancelacion" in clave and "cliente" in clave:
            return clave
        if campo_id == "rango_atraso" and "rang" in clave and "atraso" in clave:
            return clave
    return None


def construir_datos_grupal(filas: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Un registro por DNI. Si un DNI trae valores distintos para un campo, no se elige uno."""
    advertencias: List[str] = []
    if not filas:
        return {"disponible": False, "por_dni": {}, "columnas": set(), "advertencias": ["compartamos_grupal no devolvió registros para este grupo."]}

    indices = [indexar_fila(fila) for fila in filas]
    campos = {campo_id: tuple(nombres) for campo_id, nombres in CAMPOS_GRUPAL.items()}
    for campo_id, nombres in list(campos.items()):
        if not existe_columna(indices[0], *nombres):
            parecida = columna_parecida(indices[0], campo_id)
            if parecida:
                campos[campo_id] = nombres + (parecida,)
                advertencias.append(f"compartamos_grupal: {nombres[0]} se leyó desde la columna '{parecida}'.")
    columnas = {campo_id for campo_id, nombres in campos.items() if existe_columna(indices[0], *nombres)}
    faltantes = [campos[campo_id][0] for campo_id in campos if campo_id not in columnas]
    if faltantes:
        advertencias.append("No se encontró en compartamos_grupal: " + ", ".join(faltantes) + ".")

    por_dni_filas: Dict[str, List[Dict[str, Any]]] = {}
    for indice in indices:
        dni = clave_documento(valor_columna(indice, "NumDocumento", "DNI"))
        if dni:
            por_dni_filas.setdefault(dni, []).append(indice)

    por_dni: Dict[str, Dict[str, Any]] = {}
    conflictos = 0
    for dni, grupo_filas in por_dni_filas.items():
        registro: Dict[str, Any] = {}
        for campo_id, nombres in campos.items():
            if campo_id not in columnas:
                continue
            valores = []
            for indice in grupo_filas:
                valor = valor_columna(indice, *nombres)
                if not vacio(valor) and not any(texto(valor) == texto(previo) for previo in valores):
                    valores.append(valor)
            if len(valores) == 1:
                registro[campo_id] = valores[0]
            elif len(valores) == 0:
                registro[campo_id] = None
            else:
                registro[campo_id] = None
                conflictos += 1
        por_dni[dni] = registro
    if conflictos:
        advertencias.append(f"compartamos_grupal: {conflictos} dato(s) con valores distintos para un mismo DNI; no se muestran.")
    return {"disponible": True, "por_dni": por_dni, "columnas": columnas, "advertencias": advertencias}


def formatear_rol(comite: Any) -> str:
    valor = texto(comite)
    return valor.capitalize() if valor else "Integrante"


def aplicar_datos_grupal(integrantes: List[Dict[str, Any]], grupal: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Rol (COMITÉ), ultimo pago (FecUltPago) y calificacion (Cal_PROV) salen de compartamos_grupal."""
    if not grupal.get("disponible"):
        return integrantes
    columnas = grupal.get("columnas", set())
    por_dni = grupal.get("por_dni", {})
    for integrante in integrantes:
        datos = por_dni.get(clave_documento(integrante.get("dni")))
        if "comite" in columnas:
            integrante["rol"] = formatear_rol(datos.get("comite")) if datos is not None else None
        if "fec_ult_pago" in columnas:
            integrante["ultimo_pago_asignacion"] = fecha_iso(datos.get("fec_ult_pago")) if datos is not None else None
    return integrantes


# Calificacion / segmentacion: salen de las tablas de asignacion, NO de SAC.
#   (tabla, columnas DNI posibles, columnas operacion posibles, columna valor, tipo)
#   grupal -> compartamos_grupal (Cal_PROV, via construir_datos_grupal)
FUENTES_ASIGNACION = (
    ("compartamos_individual", ("NumDoc", "DNI"), ("Operacion", "CodOperacion"), "Calif_Provisiones", "CALIFICACION"),
    ("compartamos_ccm", ("NumDoc", "DNI"), ("Operacion", "CodOperacion"), "Calif_Provisiones", "CALIFICACION"),
    ("compartamos_castigo", ("NumDoc", "DNI"), ("Operacion", "CodOperacion"), "Segmentacion", "SEGMENTACION"),
    ("compartamos_grupal_castigo", ("NumDoc", "DNI"), ("Operacion", "CodOperacion"), "Segmentacion", "SEGMENTACION"),
)
CARTERA_ASIGNACION = {
    "compartamos_individual": "Individual", "compartamos_ccm": "CCM", "compartamos_grupal": "Grupal",
    "compartamos_castigo": "Castigo individual", "compartamos_grupal_castigo": "Castigo grupal",
}
SEGMENTACION_ETIQUETA = {"verde": "Verde", "ambar": "Ámbar", "rojo": "Rojo"}
_columnas_asignacion_cache: Dict[str, Dict[str, str]] = {}


def etiqueta_segmentacion(valor: Any) -> Optional[str]:
    base = texto(valor)
    if base is None:
        return None
    clave = clave_columna(base)
    return SEGMENTACION_ETIQUETA.get(clave, base)


def columnas_reales_tabla(conn, tabla: str) -> Dict[str, str]:
    """Nombre real (con su capitalizacion/espacios) de cada columna, indexado por clave_columna."""
    if tabla not in _columnas_asignacion_cache:
        filas = conn.execute(text(
            "SELECT COLUMN_NAME FROM Desarrollo.INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = :t"), {"t": tabla}).all()
        _columnas_asignacion_cache[tabla] = {clave_columna(f[0]): f[0] for f in filas}
    return _columnas_asignacion_cache[tabla]


def variantes_documento(dnis: List[str]) -> List[str]:
    """Formas en que un DNI puede estar guardado (con/sin ceros a la izquierda) para comparar sin funciones sobre la columna."""
    variantes: List[str] = []
    for dni in dnis:
        for valor in (dni, dni.lstrip("0"), dni.lstrip("0").zfill(8)):
            if valor and valor not in variantes:
                variantes.append(valor)
    return variantes


def consultar_tabla_asignacion(tabla: str, cols_dni: tuple, cols_op: tuple, col_valor: str, tipo: str,
                               variantes: List[str]) -> Dict[str, Any]:
    """Una tabla de asignacion, en su propia conexion (se ejecuta en paralelo con las demas)."""
    salida: Dict[str, Any] = {"filas": [], "advertencia": None}
    params = {f"d{i}": valor for i, valor in enumerate(variantes)}
    # CAST del lado del parametro: asi la columna no se convierte y el filtro puede usar indice.
    marcadores = ", ".join(f"CAST(:{key} AS VARCHAR(40))" for key in params)
    try:
        with engine_siscob.connect() as conn:
            reales = columnas_reales_tabla(conn, tabla)
            col_dni = next((reales[clave_columna(c)] for c in cols_dni if clave_columna(c) in reales), None)
            col_op = next((reales[clave_columna(c)] for c in cols_op if clave_columna(c) in reales), None)
            col_val = reales.get(clave_columna(col_valor))
            if not col_dni or not col_val:
                salida["advertencia"] = f"{tabla}: no se encontró la columna de documento o de {col_valor}."
                return salida
            sel_op = f"[{col_op}]" if col_op else "NULL"
            query = text(f"""
                SELECT [{col_dni}] AS dni, {sel_op} AS operacion, [{col_val}] AS valor
                FROM Desarrollo.dbo.{tabla} WITH(NOLOCK)
                WHERE [{col_dni}] IN ({marcadores})
            """)
            for fila in conn.execute(query, params).mappings().all():
                valor = etiqueta_segmentacion(fila["valor"]) if tipo == "SEGMENTACION" else etiqueta_calificacion(fila["valor"])
                if valor is None:
                    continue
                salida["filas"].append({
                    "dni": clave_documento(fila["dni"]), "tabla": tabla,
                    "tipo": "Segmentación" if tipo == "SEGMENTACION" else "Calificación",
                    "valor": valor, "operacion": clave_documento(fila["operacion"]),
                })
    except Exception:
        logger.exception("No se pudo leer %s para calificación/segmentación", tabla)
        salida["advertencia"] = f"No se pudo consultar {tabla} (calificación/segmentación)."
    return salida


def consultar_calificacion_asignacion(dnis: List[str]) -> Dict[str, Any]:
    """{'por_dni': {dni_sin_ceros: [{tabla, tipo, valor, operacion}]}, 'advertencias': [...]}
    Las 4 tablas se consultan en paralelo."""
    dnis = [identificador(value) for value in dnis if identificador(value)]
    resultado: Dict[str, Any] = {"por_dni": {}, "advertencias": []}
    if not dnis:
        return resultado
    variantes = variantes_documento(dnis)
    with ThreadPoolExecutor(max_workers=len(FUENTES_ASIGNACION)) as pool:
        futuros = [pool.submit(consultar_tabla_asignacion, *fuente, variantes) for fuente in FUENTES_ASIGNACION]
        for futuro in futuros:
            salida = futuro.result()
            if salida["advertencia"]:
                resultado["advertencias"].append(salida["advertencia"])
            for fila in salida["filas"]:
                dni = fila.pop("dni")
                resultado["por_dni"].setdefault(dni, []).append(fila)
    return resultado


def resolver_calificacion(dni: str, operacion: Any, asignacion: Dict[str, Any], grupal: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Prioridad: 1) misma operacion en una tabla de asignacion; 2) compartamos_grupal (Cal_PROV) si es integrante;
    3) unico registro del DNI en las tablas de asignacion. Si no hay dato, None (no se inventa)."""
    candidatos = asignacion.get("por_dni", {}).get(dni, [])
    clave_op = clave_documento(operacion)
    if clave_op:
        for item in candidatos:
            if item["operacion"] == clave_op:
                return {**item, "fuente": item["tabla"]}
    datos = grupal.get("por_dni", {}).get(dni) if grupal.get("disponible") else None
    if datos is not None and not vacio(datos.get("cal_prov")):
        return {"tipo": "Calificación", "valor": etiqueta_calificacion(datos.get("cal_prov")), "fuente": "compartamos_grupal"}
    distintos = {(item["tabla"], item["tipo"], item["valor"]) for item in candidatos}
    if len(distintos) == 1:
        item = candidatos[0]
        return {**item, "fuente": item["tabla"]}
    return None


def aplicar_calificacion(destino: Dict[str, Any], dni: str, operacion: Any, asignacion: Dict[str, Any], grupal: Dict[str, Any]) -> None:
    encontrado = resolver_calificacion(dni, operacion, asignacion, grupal)
    destino["calificacion"] = encontrado["valor"] if encontrado else None
    destino["tipo_calificacion"] = encontrado["tipo"] if encontrado else None
    destino["fuente_calificacion"] = encontrado["fuente"] if encontrado else None
    destino["cartera_calificacion"] = CARTERA_ASIGNACION.get(encontrado["fuente"]) if encontrado else None


def aplicar_calificacion_integrantes(integrantes: List[Dict[str, Any]], asignacion: Dict[str, Any], grupal: Dict[str, Any]) -> List[Dict[str, Any]]:
    for integrante in integrantes:
        operaciones = integrante.get("operaciones") or [{}]
        aplicar_calificacion(integrante, clave_documento(integrante.get("dni")), operaciones[0].get("operacion"), asignacion, grupal)
    return integrantes


def consultar_cronograma_grupo(codigos: List[str], operaciones: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """Filas de la carga diaria SAC del grupo (cuotas CT por integrante).

    `operaciones`: operaciones que la asignacion grupal (compartamos_grupal) reconoce como del grupo pero que
    SAC trae con CodigoGrupo 0; se buscan por su codigo de operacion para que entren en el cronograma."""
    operaciones = [op for op in (operaciones or []) if op]
    if not codigos and not operaciones:
        return []
    params: Dict[str, Any] = {}
    condiciones: List[str] = []
    if codigos:
        params.update({f"grupo_{index}": codigo for index, codigo in enumerate(codigos)})
        condiciones.append("S.[CodigoGrupo ] IN (" + ", ".join(f":grupo_{index}" for index in range(len(codigos))) + ")")
    if operaciones:
        params.update({f"op_{index}": op for index, op in enumerate(operaciones)})
        condiciones.append("S.[Cod Operación] IN (" + ", ".join(f":op_{index}" for index in range(len(operaciones))) + ")")
    query = text(f"""
        SELECT S.*
        FROM Desarrollo.DBO.SAC_CAR_BIZNESCOB S WITH(NOLOCK)
        WHERE {" OR ".join(condiciones)}
    """)
    with engine_siscob.connect() as conn:
        return [dict(row) for row in conn.execute(query, params).mappings().all()]


COLUMNAS_CT_CAPITAL = ("CT 1", "CT 2", "CT 3")
COLUMNAS_CT_CARGOS = {
    1: ("CT 11", "CT 12", "CT 13", "CT 14", "CT 15"),
    2: ("CT 21", "CT 22", "CT 23", "CT 24", "CT 25"),
    3: ("CT 31", "CT 32", "CT 33", "CT 34", "CT 35"),
}


def valor_unanime(valores: Iterable[Any]) -> tuple:
    """(valor, ambiguo): el valor si todos los no vacios coinciden."""
    distintos: List[Any] = []
    for valor in valores:
        if not vacio(valor) and not any(texto(valor) == texto(previo) for previo in distintos):
            distintos.append(valor)
    if len(distintos) == 1:
        return distintos[0], False
    return None, len(distintos) > 1


def dias_producto(producto: Optional[str]) -> Optional[int]:
    """Periodo entre cuotas segun ProductoCamp: 14 o 28 dias. Cualquier otro texto: no determinado."""
    if not producto:
        return None
    coincidencia = re.search(r"(?<!\d)(14|28)(?!\d)\s*d[ií]as", producto, re.IGNORECASE)
    return int(coincidencia.group(1)) if coincidencia else None


def cuotas_por_producto(producto: Optional[str]) -> Optional[int]:
    """14 dias -> 2 cuotas; 28 dias -> 1 cuota. Cualquier otro texto: no determinado."""
    dias = dias_producto(producto)
    return CUOTAS_A_PAGAR_POR_PRODUCTO.get(dias) if dias else None


def fecha_sac(value: Any) -> Optional[date]:
    """UltFecVen de SAC llega como float AAAAMMDD (20260812.0); tambien acepta date/datetime."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    entero_fecha = entero(value)
    if entero_fecha is None or not 19000101 <= entero_fecha <= 99991231:
        return None
    try:
        return date(entero_fecha // 10000, entero_fecha // 100 % 100, entero_fecha % 100)
    except ValueError:
        return None


def redondear_sql(valor: float) -> int:
    """ROUND(x, 0) de SQL Server (mitades lejos de cero); round() de Python redondea al par."""
    return int(math.copysign(math.floor(abs(valor) + 0.5), valor))


def construir_cronograma_cuotas(
    filas: List[Dict[str, Any]],
    dnis_autorizados: Iterable[str],
    grupal_por_dni: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Matriz integrante x numero de cuota.

    Regla: CT 1 corresponde a la cuota Ult_CuotaAtrasada (la mas antigua pendiente),
    CT 2 a la siguiente y CT 3 a la subsiguiente. Se entregan dos lecturas:
      - cuotas: solo capital (CT 1, CT 2, CT 3), tal cual llegan;
      - cuotas_total: total de la cuota con cargos por atraso
        (CT 1 + CT 11..CT 15, CT 2 + CT 21..CT 25, CT 3 + CT 31..CT 35).
    Solo se incluyen integrantes ya devueltos (y autorizados) por la consulta principal.

    La matriz se muestra por NUMERO de cuota. Lo que el grupo debe pagar (plan) se decide
    por FECHA DE VENCIMIENTO (2026-10-13, misma regla que Biznescob Analytics V1):
    integrantes con distinto desembolso pueden deber cuotas de distinto numero que vencen
    el mismo dia, y todos deben pagar para que el grupo contenga. Ver plan_pago_por_vencimiento.
    """
    grupal_por_dni = grupal_por_dni or {}
    advertencias: List[str] = []
    autorizados = {clave_documento(dni) for dni in dnis_autorizados if clave_documento(dni)}

    por_operacion: Dict[str, Dict[str, Any]] = {}
    excluidos = 0
    columnas_ct_faltantes: set = set()
    for index, fila in enumerate(filas):
        indice = indexar_fila(fila)
        dni = clave_documento(valor_columna(indice, "DNI"))
        if dni not in autorizados:
            excluidos += 1
            continue
        for nombre in list(COLUMNAS_CT_CAPITAL) + [c for grupo in COLUMNAS_CT_CARGOS.values() for c in grupo]:
            if not existe_columna(indice, nombre):
                columnas_ct_faltantes.add(nombre)
        operacion = identificador(valor_columna(indice, "Cod Operación", "CodOperacion"))
        key = f"{dni}|{operacion or index}"
        por_operacion.setdefault(key, indice)
    if excluidos:
        advertencias.append(
            f"Cronograma: {excluidos} registro(s) de la carga SAC no figuran entre los integrantes consultados y no se muestran."
        )
    if columnas_ct_faltantes:
        advertencias.append("Cronograma: no se encontraron en la carga SAC las columnas " + ", ".join(sorted(columnas_ct_faltantes)) + "; el total de cuota puede estar incompleto.")

    integrantes = []
    ubicacion: List[Dict[str, Any]] = []
    numeros_cuota = set()
    sin_ubicacion = 0
    for key, indice in por_operacion.items():
        dni = clave_documento(valor_columna(indice, "DNI"))
        grupal = grupal_por_dni.get(dni) or {}
        cuota_inicial = entero(valor_columna(indice, "Ult_CuotaAtrasada"))
        capital = [numero(valor_columna(indice, nombre)) for nombre in COLUMNAS_CT_CAPITAL]
        total = []
        for posicion in (1, 2, 3):
            componentes = [capital[posicion - 1]] + [numero(valor_columna(indice, nombre)) for nombre in COLUMNAS_CT_CARGOS[posicion]]
            presentes = [valor for valor in componentes if valor is not None]
            total.append(sum(presentes) if presentes else None)
        cuotas: Dict[str, float] = {}
        cuotas_total: Dict[str, float] = {}
        if cuota_inicial is not None:
            for posicion in range(3):
                if capital[posicion] is not None and capital[posicion] > 0:
                    cuotas[str(cuota_inicial + posicion)] = round(capital[posicion], 2)
                    numeros_cuota.add(cuota_inicial + posicion)
                if total[posicion] is not None and total[posicion] > 0:
                    cuotas_total[str(cuota_inicial + posicion)] = round(total[posicion], 2)
                    numeros_cuota.add(cuota_inicial + posicion)
        elif any((valor or 0) > 0 for valor in capital + total):
            sin_ubicacion += 1
        atraso_inicio = entero(grupal.get("dias_atraso_inicio"))
        ubicacion.append({"cuota_inicial": cuota_inicial, "capital": capital, "total": total,
                          "fecha_ct1": fecha_sac(valor_columna(indice, "UltFecVen"))})
        integrantes.append({
            "nombre": texto(valor_columna(indice, "NomCliente")),
            "dni": texto(valor_columna(indice, "DNI")),
            "operacion": texto(valor_columna(indice, "Cod Operación", "CodOperacion")),
            "rol": formatear_rol(grupal.get("comite")) if grupal and "comite" in grupal else None,
            "producto_camp": texto(grupal.get("producto_camp")),
            "pct_campana": texto(grupal.get("pct_campana")),
            "pct_campana_100": texto(grupal.get("pct_campana_100")),
            "pct_cancelacion": texto(grupal.get("pct_cancelacion")),
            "rango_atraso": texto(grupal.get("rango_atraso")),
            "cuota_mas_atrasada": cuota_inicial,
            "cuotas": cuotas,
            "cuotas_total": cuotas_total,
            "dias_atraso_inicio": atraso_inicio,
            "dias_atraso_hoy": entero(valor_columna(indice, "DiasAtraso")),
            "dias_atraso_proyectado": atraso_inicio + DIAS_PROYECCION_ATRASO if atraso_inicio is not None else None,
            "cuotas_aprobadas": entero(grupal.get("cuotas_aprobadas")),
            "cuotas_pagadas": entero(grupal.get("cuotas_pagadas")),
            "fecha_vencimiento_ct1": fecha_iso(ubicacion[-1]["fecha_ct1"]),
        })
        integrantes[-1]["_ubicacion"] = ubicacion[-1]
    if sin_ubicacion:
        advertencias.append(
            f"Cronograma: {sin_ubicacion} integrante(s) con montos CT pero sin Ult_CuotaAtrasada; sus montos no se ubican en ninguna cuota."
        )

    integrantes.sort(key=lambda item: (
        item["cuota_mas_atrasada"] if item["cuota_mas_atrasada"] is not None else float("inf"),
        -(item["dias_atraso_hoy"] or 0),
        item["nombre"] or "",
    ))
    columnas = sorted(numeros_cuota)
    totales = {str(n): round(sum(item["cuotas"].get(str(n), 0) for item in integrantes), 2) for n in columnas}
    totales_total = {str(n): round(sum(item["cuotas_total"].get(str(n), 0) for item in integrantes), 2) for n in columnas}

    # Parametros de campana del grupo (compartamos_grupal): solo si todos coinciden.
    parametros: Dict[str, Any] = {}
    ambiguos = []
    for campo_id in ("producto_camp", "pct_campana", "pct_campana_100", "pct_cancelacion", "rango_atraso"):
        valor, ambiguo = valor_unanime(grupal_por_dni.get(clave_documento(item["dni"]), {}).get(campo_id) for item in integrantes)
        parametros[campo_id] = texto(valor)
        if ambiguo:
            ambiguos.append(campo_id)
    if ambiguos:
        advertencias.append("Cronograma: el grupo tiene valores distintos en " + ", ".join(ambiguos) + "; ese dato no se muestra.")

    plan = plan_pago_por_vencimiento(integrantes, parametros.get("producto_camp"), "producto_camp" in ambiguos, advertencias)
    return {
        "disponible": bool(integrantes),
        "fuente": "SAC_CAR_BIZNESCOB + compartamos_grupal",
        "dias_proyeccion": DIAS_PROYECCION_ATRASO,
        "cuotas": columnas,
        "integrantes": integrantes,
        "totales": totales,
        "totales_total": totales_total,
        "parametros": parametros,
        "plan": plan,
        "advertencias": advertencias,
    }


def plan_pago_por_vencimiento(integrantes: List[Dict[str, Any]], producto: Optional[str], producto_ambiguo: bool,
                              advertencias: List[str]) -> Dict[str, Any]:
    """Cuotas que debe pagar el grupo, alineadas por FECHA DE VENCIMIENTO (2026-10-13).

    Misma regla que Biznescob Analytics (V1 y obligacion en cuotas):
      1. Vencimiento de CT 1 = UltFecVen; CT 2 = + 1 periodo; CT 3 = + 2 (14 o 28 dias segun producto).
      2. D1 = vencimiento mas antiguo del grupo entre integrantes con CT 1 > 0.
      3. Posicion de cada CT = 1 + ROUND((vencimiento - D1) / periodo).
      4. Cuotas exigidas = las 1 (28 dias) o 2 (14 dias) posiciones mas antiguas con capital.
      5. Cada integrante debe sus CT en esas posiciones, aunque su numero de cuota sea otro.
    Ejemplo real: grupo 44011, una integrante debe su N.o 2 y cinco su N.o 3, todas vencen el
    12/08/2026: deben pagar las seis. Por numero solo se exigia la N.o 2 (1 de 6).

    Agrega a cada integrante: a_pagar / a_pagar_total (por numero de cuota, para marcar la matriz)
    y a_pagar_detalle (una fila por cuota exigida: fecha, numero, capital y total con cargos).
    Quita el campo interno _ubicacion.
    """
    periodo = dias_producto(producto)
    datos = [item.pop("_ubicacion", None) or {} for item in integrantes]
    for item in integrantes:
        item.update(a_pagar={}, a_pagar_total={}, a_pagar_detalle=[])

    def positivo(valor: Optional[float]) -> bool:
        return valor is not None and valor > 0

    candidatos = [d["fecha_ct1"] for d in datos
                  if d.get("fecha_ct1") and (d.get("cuota_inicial") or 0) > 0 and positivo((d.get("capital") or [None])[0])]
    d1 = min(candidatos) if candidatos else None

    posiciones: Dict[int, Dict[str, Any]] = {}
    sin_fecha = 0
    for d in datos:
        d["pos1"] = None
        con_capital = any(positivo(v) for v in d.get("capital") or [])
        if d.get("cuota_inicial") is None or not con_capital:
            continue
        if not d.get("fecha_ct1") or d1 is None or periodo is None:
            if d.get("fecha_ct1") is None:
                sin_fecha += 1
            continue
        d["pos1"] = 1 + redondear_sql((d["fecha_ct1"] - d1).days / periodo)
        for k in range(3):
            capital_k = d["capital"][k]
            if not positivo(capital_k):
                continue
            pos = d["pos1"] + k
            info = posiciones.setdefault(pos, {"capital": 0.0, "total": 0.0, "fecha": None, "numeros": Counter()})
            info["capital"] += capital_k
            if positivo(d["total"][k]):
                info["total"] += d["total"][k]
            vence = date.fromordinal(d["fecha_ct1"].toordinal() + k * periodo)
            info["fecha"] = vence if info["fecha"] is None or vence < info["fecha"] else info["fecha"]
            info["numeros"][d["cuota_inicial"] + k] += 1
    if sin_fecha:
        advertencias.append(
            f"Cuotas a pagar: {sin_fecha} integrante(s) sin fecha de vencimiento (UltFecVen) en la carga SAC; "
            "no se puede saber qué cuota les corresponde y no se incluyen en lo que debe pagar el grupo."
        )

    plan = construir_plan_pago(sorted(posiciones), producto, producto_ambiguo)
    if not plan.get("disponible"):
        if not posiciones and sin_fecha and plan.get("motivo") == "El grupo no tiene cuotas atrasadas con monto.":
            plan["motivo"] = "La carga SAC no trae la fecha de vencimiento (UltFecVen); no se puede determinar qué cuotas debe pagar el grupo."
        return plan

    seleccion = plan["cuotas"]
    vencimientos = []
    for pos in seleccion:
        info = posiciones[pos]
        # Numero que se muestra: el mas frecuente en esa fecha (empate: el menor). Solo informativo.
        numero_mostrado = sorted(info["numeros"].items(), key=lambda par: (-par[1], par[0]))[0][0]
        vencimientos.append({
            "posicion": pos,
            "fecha_vencimiento": info["fecha"].isoformat(),
            "cuota": numero_mostrado,
            "numeros": sorted(info["numeros"]),
            "integrantes": sum(info["numeros"].values()),
            "capital": round(info["capital"], 2),
            "total": round(info["total"], 2),
        })
    fecha_por_pos = {v["posicion"]: v["fecha_vencimiento"] for v in vencimientos}
    for item, d in zip(integrantes, datos):
        if d.get("pos1") is None:
            continue
        for k in range(3):
            pos = d["pos1"] + k
            if pos not in fecha_por_pos:
                continue
            if not positivo(d["capital"][k]):
                continue  # misma condicion que la seleccion: una cuota sin capital no se exige
            numero_k = d["cuota_inicial"] + k
            capital_k = round(d["capital"][k], 2)
            total_k = round(d["total"][k], 2) if positivo(d["total"][k]) else None
            item["a_pagar"][str(numero_k)] = capital_k
            if total_k is not None:
                item["a_pagar_total"][str(numero_k)] = total_k
            item["a_pagar_detalle"].append({"fecha_vencimiento": fecha_por_pos[pos], "cuota": numero_k,
                                            "capital": capital_k, "total": total_k})
    plan.update(
        cuotas=[v["cuota"] for v in vencimientos],
        vencimientos=vencimientos,
        alineado=all(len(v["numeros"]) == 1 for v in vencimientos),
        regla=("14 días: 2 cuotas · 28 días: 1 cuota · las más atrasadas del grupo por fecha de vencimiento: "
               "pagan todos los integrantes con cuota en esa fecha, aunque el número de su cuota sea otro"),
    )
    return plan


def construir_plan_pago(cuotas_presentes: List[int], producto: Optional[str], producto_ambiguo: bool) -> Dict[str, Any]:
    """Cuotas que debe pagar el grupo: las N mas atrasadas, N segun el producto (14 -> 2, 28 -> 1)."""
    if producto_ambiguo:
        return {"disponible": False, "motivo": "El grupo tiene más de un ProductoCamp; no se puede determinar cuántas cuotas debe pagar."}
    if not producto:
        return {"disponible": False, "motivo": "compartamos_grupal no trae ProductoCamp para este grupo."}
    cantidad = cuotas_por_producto(producto)
    if cantidad is None:
        return {"disponible": False, "producto": producto, "motivo": "ProductoCamp no indica 14 ni 28 días; no se puede determinar cuántas cuotas debe pagar."}
    if not cuotas_presentes:
        return {"disponible": False, "producto": producto, "cuotas_por_pagar": cantidad, "motivo": "El grupo no tiene cuotas atrasadas con monto."}
    return {
        "disponible": True,
        "producto": producto,
        "cuotas_por_pagar": cantidad,
        "cuotas": cuotas_presentes[:cantidad],
        "regla": "14 días: 2 cuotas · 28 días: 1 cuota · siempre las más atrasadas del grupo",
    }


def estructura_cronograma_vacia() -> Dict[str, Any]:
    return {"disponible": False, "fuente": None, "dias_proyeccion": DIAS_PROYECCION_ATRASO, "cuotas": [], "integrantes": [], "totales": {}, "totales_total": {}, "parametros": {}, "plan": {"disponible": False}}


def clave_documento(value: Any) -> str:
    """DNI comparable entre fuentes con tipos distintos (texto con ceros a la izquierda vs numerico)."""
    return identificador(value).lstrip("0")


def prefiltro_gestiones(cantidad_dnis: int) -> str:
    """Gestiones candidatas por DNI usando IX_gestion_dni_* (GESTION.DNI) e IX_Cliente (CLIENTE.Dni).
    El CAST va del lado del parametro para no convertir la columna (y asi poder usar el indice)."""
    if not RADAR_PREFILTRO_SARGABLE or cantidad_dnis <= 0:
        return ""
    lista = ", ".join(f"CAST(:dni_{i} AS VARCHAR(40))" for i in range(cantidad_dnis))
    return f"""AND G.IdGestion IN (
              SELECT G1.IdGestion FROM SISCOB.DBO.GESTION G1 WITH(NOLOCK) WHERE G1.DNI IN ({lista})
              UNION
              SELECT G2.IdGestion FROM SISCOB.DBO.CLIENTE C2 WITH(NOLOCK)
              INNER JOIN SISCOB.DBO.GESTION G2 WITH(NOLOCK) ON G2.IdCliente = C2.IdCliente
              WHERE C2.Dni IN ({lista}))"""


def consultar_gestiones(dnis: List[str], carteras_por_dni: Optional[Dict[str, set[int]]] = None) -> Dict[str, Any]:
    dnis = [identificador(value) for value in dnis if identificador(value)]
    if not dnis:
        return estructura_gestion_vacia()
    condiciones = []
    params = {}
    for index, dni in enumerate(dnis):
        key = f"dni_{index}"
        condiciones.append(f"LTRIM(RTRIM(ISNULL(CL.Dni, ''))) = :{key}")
        condiciones.append(f"LTRIM(RTRIM(ISNULL(G.DNI, ''))) = :{key}")
        params[key] = dni
    query = text("""
        SELECT TOP 100
            G.IdGestion AS id_gestion,
            G.Fecha AS fecha,
            G.Hora AS hora,
            G.Gestion AS gestion,
            G.Contacto AS contacto,
            G.Telefono AS telefono,
            G.TipoContacto AS canal,
            G.TipoOperador AS operador,
            G.campana AS campana,
            CL.Dni AS dni_cliente,
            CL.IdCartera AS id_cartera,
            G.DNI AS dni_gestion,
            I.CodIndicador AS codigo_indicador,
            I.DescripcionIndicador AS resultado,
            U.Usuario AS usuario,
            LTRIM(RTRIM(CONCAT(ISNULL(U.Nombres, ''), ' ', ISNULL(U.Apellidos, '')))) AS agente
        FROM SISCOB.DBO.CLIENTE CL WITH(NOLOCK)
        INNER JOIN SISCOB.DBO.GESTION G WITH(NOLOCK) ON G.IdCliente = CL.IdCliente
        LEFT JOIN SISCOB.DBO.INDICADOR I WITH(NOLOCK) ON I.IdIndicador = G.IdIndicador
        LEFT JOIN SISCOB.DBO.USUARIO U WITH(NOLOCK) ON U.IdUsuario = G.IdUsuario
        WHERE CL.IdCartera IN (124, 126, 128, 133, 144)
          AND ({condiciones})
          {prefiltro}
        ORDER BY G.Fecha DESC, G.Hora DESC, G.IdGestion DESC
    """.format(condiciones=" OR ".join(condiciones), prefiltro=prefiltro_gestiones(len(dnis))))
    query_carteras = None
    if carteras_por_dni is None:
        query_carteras = text("""
            SELECT DISTINCT CL.IdCartera AS id_cartera
            FROM SISCOB.DBO.CLIENTE CL WITH(NOLOCK)
            WHERE CL.IdCartera IN (124, 126, 128, 133, 144)
              AND ({condiciones})
        """.format(condiciones=" OR ".join(
            f"LTRIM(RTRIM(ISNULL(CL.Dni, ''))) = :dni_{index}"
            for index in range(len(dnis))
        )))
    with engine_siscob.connect() as conn:
        rows = [dict(row) for row in conn.execute(query, params).mappings().all()]
        if query_carteras is not None:
            carteras_rows = [dict(row) for row in conn.execute(query_carteras, params).mappings().all()]
        else:
            carteras_rows = [
                {"id_cartera": cartera}
                for carteras in carteras_por_dni.values()
                for cartera in carteras
            ]

    hoy = date.today()
    inicio_mes = hoy.replace(day=1)
    historia = []
    for row in rows:
        fecha = a_fecha(row.get("fecha"))
        historia.append(limpiar_vacios({
            "id": row.get("id_gestion"),
            "fecha": fecha_iso(row.get("fecha")),
            "hora": texto(row.get("hora")),
            "gestion": texto(row.get("gestion")),
            "resultado": texto(row.get("resultado")) or texto(row.get("codigo_indicador")),
            "contacto": texto(row.get("contacto")),
            "telefono": texto(row.get("telefono")),
            "agente": texto(row.get("agente")) or texto(row.get("usuario")),
            "canal": texto(row.get("canal")) or texto(row.get("operador")),
            "campana": texto(row.get("campana")),
        }))
    ultima = historia[0] if historia else None
    carteras_siscob = []
    for row in carteras_rows:
        id_cartera = entero(row.get("id_cartera"))
        if id_cartera in COMPARTAMOS_CARTERAS and not any(item["id"] == id_cartera for item in carteras_siscob):
            carteras_siscob.append({"id": id_cartera, "nombre": COMPARTAMOS_CARTERAS[id_cartera]})
    por_dni = {}
    for dni in dnis:
        filas_dni = [row for row in rows if identificador(row.get("dni_cliente") or row.get("dni_gestion")) == dni]
        ultima_dni = next((item for item, row in zip(historia, rows) if identificador(row.get("dni_cliente") or row.get("dni_gestion")) == dni), None)
        por_dni[dni] = {
            "gestionado_hoy": any(a_fecha(row.get("fecha")) == hoy for row in filas_dni),
            "gestionado_mes": sum(1 for row in filas_dni if (a_fecha(row.get("fecha")) or date.min) >= inicio_mes),
            "ultima_gestion": ultima_dni,
        }
    return {
        "disponible": True,
        "gestionado_hoy": any(a_fecha(row.get("fecha")) == hoy for row in rows),
        "gestionado_mes": sum(1 for row in rows if (a_fecha(row.get("fecha")) or date.min) >= inicio_mes),
        "cantidad_gestiones": len(rows),
        "ultima_gestion": ultima,
        "resultado": ultima.get("resultado") if ultima else None,
        "contacto": ultima.get("contacto") if ultima else None,
        "agente": ultima.get("agente") if ultima else None,
        "canal": ultima.get("canal") if ultima else None,
        "historial": historia,
        "por_dni": por_dni,
        "carteras_siscob": carteras_siscob,
    }


def consultar_pagos(dni: Optional[str], codcliente: Optional[str], operaciones: List[str]) -> Dict[str, Any]:
    condiciones = ["1 = 0"]
    params: Dict[str, Any] = {}
    if dni:
        condiciones.extend(["LTRIM(RTRIM(ISNULL(documento, ''))) = :dni", "LTRIM(RTRIM(ISNULL(dni, ''))) = :dni"])
        params["dni"] = dni
    if codcliente:
        condiciones.append("LTRIM(RTRIM(ISNULL(cod_cliente, ''))) = :codcliente")
        params["codcliente"] = codcliente
    for index, operacion in enumerate(operaciones):
        key = f"op_{index}"
        condiciones.append(f"LTRIM(RTRIM(ISNULL(num_operacion, ''))) = :{key}")
        params[key] = operacion

    query = text(f"""
        SELECT TOP 200
            id_pago, formato, tipo_medicion, fecha_pago, fecha_movimiento, fecha_proceso, fecha_corte,
            documento, cod_cliente, num_operacion, monto_pago_soles, capital_contenido, activo
        FROM dbo.PAGOS_BI_NORMALIZADO WITH(NOLOCK)
        WHERE ISNULL(activo, 0) = 1
          AND UPPER(ISNULL(formato, '')) LIKE 'COMPARTAMOS%'
          AND ({' OR '.join(condiciones)})
        ORDER BY COALESCE(fecha_pago, fecha_movimiento, fecha_proceso, fecha_corte) DESC, id_pago DESC
    """)
    with engine_siscob.connect() as conn:
        rows = [dict(row) for row in conn.execute(query, params).mappings().all()]

    hoy = date.today()
    inicio_mes = hoy.replace(day=1)
    pagos = []
    for row in rows:
        fecha = row.get("fecha_pago") or row.get("fecha_movimiento") or row.get("fecha_proceso") or row.get("fecha_corte")
        pagos.append({
            "fecha": fecha_iso(fecha),
            "monto": numero(row.get("monto_pago_soles")),
            "capital_contenido": numero(row.get("capital_contenido")),
            "operacion": texto(row.get("num_operacion")),
            "tipo_medicion": texto(row.get("tipo_medicion")),
        })
    ultimo = pagos[0] if pagos else None
    acumulado_mes = sum((item.get("monto") or 0) for item in pagos if (a_fecha(item.get("fecha")) or date.min) >= inicio_mes)
    pagos_contencion = [
        item for item in pagos
        if (texto(item.get("tipo_medicion")) or "").upper() == "CONTENCION"
    ]
    capital_contenido = (
        sum((item.get("capital_contenido") or 0) for item in pagos_contencion)
        if pagos_contencion
        else None
    )
    return {
        "disponible": True,
        "tiene_datos": bool(pagos),
        "ultimo_pago_real": ultimo.get("fecha") if ultimo else None,
        "monto_ultimo_pago": ultimo.get("monto") if ultimo else None,
        "pago_acumulado_mes": round(acumulado_mes, 2) if pagos else None,
        "capital_contenido_pago": round(capital_contenido, 2) if capital_contenido is not None else None,
        "historial": pagos,
    }


def prefiltro_pdp(dni: Optional[str], operaciones: List[str]) -> str:
    """Compromisos candidatos: por operacion (COMPROMISO es chica), por GESTION.DNI -> idxcp1(idGestion)
    y por CLIENTE.Dni (directo o via gestion). El filtro exacto original sigue aplicandose despues."""
    if not RADAR_PREFILTRO_SARGABLE or not (dni or operaciones):
        return ""
    ramas: List[str] = []
    if operaciones:
        lista_op = ", ".join(f":pdp_op_{i}" for i in range(len(operaciones)))
        ramas.append(f"SELECT C1.IdCompromiso FROM SISCOB.DBO.COMPROMISO C1 WITH(NOLOCK) WHERE LTRIM(RTRIM(ISNULL(C1.NumOperacion, ''))) IN ({lista_op})")
    if dni:
        ramas.append("""SELECT C2.IdCompromiso FROM SISCOB.DBO.GESTION G2 WITH(NOLOCK)
              INNER JOIN SISCOB.DBO.COMPROMISO C2 WITH(NOLOCK) ON C2.IdGestion = G2.IdGestion
              WHERE G2.DNI = CAST(:dni AS VARCHAR(40))""")
        ramas.append("""SELECT C3.IdCompromiso FROM SISCOB.DBO.CLIENTE L3 WITH(NOLOCK)
              INNER JOIN SISCOB.DBO.COMPROMISO C3 WITH(NOLOCK) ON C3.IdCliente = L3.IdCliente
              WHERE L3.Dni = CAST(:dni AS VARCHAR(40))""")
        ramas.append("""SELECT C4.IdCompromiso FROM SISCOB.DBO.CLIENTE L4 WITH(NOLOCK)
              INNER JOIN SISCOB.DBO.GESTION G4 WITH(NOLOCK) ON G4.IdCliente = L4.IdCliente
              INNER JOIN SISCOB.DBO.COMPROMISO C4 WITH(NOLOCK) ON C4.IdGestion = G4.IdGestion
              WHERE L4.Dni = CAST(:dni AS VARCHAR(40))""")
    return "AND C.IdCompromiso IN (" + " UNION ".join(ramas) + ")"


def consultar_pdp(dni: Optional[str], operaciones: List[str]) -> Dict[str, Any]:
    condiciones = ["1 = 0"]
    params: Dict[str, Any] = {}
    if dni:
        condiciones.extend(["LTRIM(RTRIM(ISNULL(CL.Dni, ''))) = :dni", "LTRIM(RTRIM(ISNULL(G.DNI, ''))) = :dni"])
        params["dni"] = dni
    for index, operacion in enumerate(operaciones):
        key = f"pdp_op_{index}"
        condiciones.append(f"LTRIM(RTRIM(ISNULL(C.NumOperacion, ''))) = :{key}")
        params[key] = operacion
    query = text(f"""
        SELECT TOP 100
            C.IdCompromiso AS id_compromiso,
            C.FechaGenero AS fecha_genero,
            C.FechaCompromiso AS fecha_compromiso,
            C.Monto AS monto,
            C.Pagado AS pagado,
            C.FechaPago AS fecha_pago,
            C.MontoPagado AS monto_pagado,
            C.NumOperacion AS operacion,
            U.Usuario AS usuario,
            LTRIM(RTRIM(CONCAT(ISNULL(U.Nombres, ''), ' ', ISNULL(U.Apellidos, '')))) AS agente
        FROM SISCOB.DBO.COMPROMISO C WITH(NOLOCK)
        LEFT JOIN SISCOB.DBO.GESTION G WITH(NOLOCK) ON G.IdGestion = C.IdGestion
        LEFT JOIN SISCOB.DBO.CLIENTE CL WITH(NOLOCK) ON CL.IdCliente = COALESCE(C.IdCliente, G.IdCliente)
        LEFT JOIN SISCOB.DBO.USUARIO U WITH(NOLOCK) ON U.IdUsuario = G.IdUsuario
        WHERE CL.IdCartera IN (124, 126, 128, 133, 144)
          AND ({' OR '.join(condiciones)})
          {prefiltro_pdp(dni, operaciones)}
        ORDER BY C.FechaCompromiso DESC, C.IdCompromiso DESC
    """)
    with engine_siscob.connect() as conn:
        rows = [dict(row) for row in conn.execute(query, params).mappings().all()]

    items = []
    for row in rows:
        fecha = a_fecha(row.get("fecha_compromiso"))
        pagado = (texto(row.get("pagado")) or "").upper()
        if pagado == "SI":
            estado = "CUMPLIDA"
        elif fecha == date.today():
            estado = "HOY"
        elif fecha and fecha < date.today():
            estado = "CAIDA"
        else:
            estado = "VIGENTE"
        items.append(limpiar_vacios({
            "id": row.get("id_compromiso"),
            "fecha_genero": fecha_iso(row.get("fecha_genero")),
            "fecha_compromiso": fecha_iso(row.get("fecha_compromiso")),
            "monto": numero(row.get("monto")),
            "estado": estado,
            "pagado": texto(row.get("pagado")),
            "fecha_pago": fecha_iso(row.get("fecha_pago")),
            "monto_pagado": numero(row.get("monto_pagado")),
            "operacion": texto(row.get("operacion")),
            "agente": texto(row.get("agente")) or texto(row.get("usuario")),
        }))
    vigente = next((item for item in items if item.get("estado") in {"HOY", "VIGENTE"}), None)
    ultima = items[0] if items else None
    principal = vigente or ultima
    return {
        "disponible": True,
        "tiene_datos": bool(items),
        "pdp_vigente": bool(vigente),
        "monto_pdp": principal.get("monto") if principal else None,
        "fecha_compromiso": principal.get("fecha_compromiso") if principal else None,
        "estado_pdp": principal.get("estado") if principal else None,
        "agente_pdp": principal.get("agente") if principal else None,
        "historial": items,
    }


def estructura_gestion_vacia() -> Dict[str, Any]:
    return {"disponible": False, "gestionado_hoy": None, "gestionado_mes": None, "cantidad_gestiones": None, "historial": [], "por_dni": {}, "carteras_siscob": []}


def estructura_pagos_vacia() -> Dict[str, Any]:
    return {"disponible": False, "tiene_datos": False, "ultimo_pago_real": None, "monto_ultimo_pago": None, "pago_acumulado_mes": None, "capital_contenido_pago": None, "historial": []}


def estructura_pdp_vacia() -> Dict[str, Any]:
    return {"disponible": False, "tiene_datos": False, "pdp_vigente": None, "monto_pdp": None, "fecha_compromiso": None, "estado_pdp": None, "agente_pdp": None, "historial": []}


def campo(row: Dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in row and not vacio(row.get(key)):
            return row.get(key)
    lower = {str(key).lower(): value for key, value in row.items()}
    for key in keys:
        value = lower.get(key.lower())
        if not vacio(value):
            return value
    return None


def vacio(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def texto(value: Any) -> Optional[str]:
    if vacio(value):
        return None
    # VW_CLIENTE_CRM_SAC entrega algunos codigos (CodigoGrupo, CodCreGrupal) como
    # float: 362951 llega como 362951.0. Un codigo entero se representa sin ".0"
    # para que se compare y se muestre igual que el valor que escribe el usuario.
    if isinstance(value, (float, Decimal)) and not isinstance(value, bool):
        if value == value and value not in (float("inf"), float("-inf")) and value == int(value):
            return str(int(value))
    return str(value).strip()


def identificador(value: Any) -> str:
    return texto(value) or ""


def identificador_grupo_valido(value: Any) -> bool:
    value = identificador(value)
    if not value:
        return False
    try:
        return float(value.replace(",", ".")) != 0
    except ValueError:
        return True


def numero(value: Any) -> Optional[float]:
    if vacio(value):
        return None
    if isinstance(value, Decimal):
        return float(value)
    try:
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def entero(value: Any) -> Optional[int]:
    value = numero(value)
    return int(value) if value is not None else None


def fecha_iso(value: Any) -> Optional[str]:
    if vacio(value):
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    raw = str(value).strip()
    if len(raw) == 8 and raw.isdigit():
        return f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}"
    return raw


def a_fecha(value: Any) -> Optional[date]:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if vacio(value):
        return None
    raw = str(value).strip()[:10]
    for formato in ("%Y-%m-%d", "%d/%m/%Y", "%Y%m%d"):
        try:
            return datetime.strptime(raw, formato).date()
        except ValueError:
            continue
    return None


def sumar_conocidos(values: Iterable[Optional[float]]) -> Optional[float]:
    conocidos = [value for value in values if value is not None]
    return round(sum(conocidos), 2) if conocidos else None


def maximo_conocido(values: Iterable[Optional[float]]) -> Optional[float]:
    conocidos = [value for value in values if value is not None]
    return max(conocidos) if conocidos else None


def max_fecha(values: Iterable[Optional[str]]) -> Optional[str]:
    conocidos = [(a_fecha(value), value) for value in values if value]
    validos = [(parsed, original) for parsed, original in conocidos if parsed]
    return max(validos, key=lambda item: item[0])[1] if validos else None


def limpiar_vacios(data: Dict[str, Any]) -> Dict[str, Any]:
    return {key: value for key, value in data.items() if value is not None and value != ""}


def serializar(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: serializar(item) for key, item in value.items()}
    if isinstance(value, list):
        return [serializar(item) for item in value]
    if isinstance(value, tuple):
        return [serializar(item) for item in value]
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value
