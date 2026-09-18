from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy import text

from app.core.db_siscob import engine_siscob


CT_FORMULAS = {
    "cuota_1": ["CT1", "CT11", "CT12", "CT13", "CT14", "CT15"],
    "cuota_2": ["CT2", "CT21", "CT22", "CT23", "CT24", "CT25"],
    "cuota_3": ["CT3", "CT31", "CT32", "CT33", "CT34", "CT35"],
}

COMPARTAMOS_CARTERAS = {
    124: "CASTIGO INDIVIDUAL",
    126: "VIGENTE INDIVIDUAL",
    128: "VIGENTE CCM",
    133: "VIGENTE GRUPAL",
    144: "CASTIGO GRUPAL",
}


def construir_respuesta_crm(rows: List[Dict[str, Any]], valor_buscado: str) -> Dict[str, Any]:
    tipo_resultado = resolver_tipo_resultado(rows, valor_buscado)
    operaciones_rows = deduplicar_operaciones(rows)
    operaciones = [normalizar_operacion(row) for row in operaciones_rows]
    principal = operaciones_rows[0]
    advertencias: List[str] = []

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

    try:
        gestion = consultar_gestiones(dnis)
    except Exception:
        advertencias.append("No se pudo consultar la actividad de cobranza en SISCOB.")

    try:
        pagos = consultar_pagos(dni, codcliente, codigos_operacion)
    except Exception:
        advertencias.append("No se pudo consultar la fuente operativa de pagos.")

    try:
        pdp = consultar_pdp(dni, codigos_operacion)
    except Exception:
        advertencias.append("No se pudo consultar la fuente operativa de compromisos.")

    situacion = construir_situacion(operaciones)
    contacto = construir_contacto(rows)
    grupo = construir_contexto_grupo(rows)
    campanas = construir_campanas(operaciones)
    contencion = construir_contencion(pagos)
    cliente = construir_cliente(rows, operaciones)
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
        "integrantes": construir_integrantes(operaciones_rows, gestion.get("por_dni", {})) if tipo_resultado == "GRUPO" else [],
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
    return serializar(respuesta)


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
        "calificacion": texto(campo(row, "Calificacion")),
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
        "calificacion": texto(campo(principal, "Calificacion")),
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
            "calificacion": texto(campo(principal, "Calificacion")),
            "contencion": {"disponible": False},
            "gestion": gestion_por_dni.get(identificador(dni), {"gestionado_hoy": False, "gestionado_mes": 0}),
        })
    return integrantes


def consultar_gestiones(dnis: List[str]) -> Dict[str, Any]:
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
        ORDER BY G.Fecha DESC, G.Hora DESC, G.IdGestion DESC
    """.format(condiciones=" OR ".join(condiciones)))
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
        carteras_rows = [dict(row) for row in conn.execute(query_carteras, params).mappings().all()]

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
