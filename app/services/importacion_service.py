from datetime import date, datetime
from decimal import Decimal
from io import BytesIO
import math
import re
import time
import unicodedata
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.core.db_siscob import engine_siscob


CONFIG_COLUMNS = [
    "id_config",
    "cartera",
    "producto",
    "idcartera",
    "tabla_destino",
    "tabla_historica",
    "clave_cruce",
    "metodo_lectura",
    "permite_columnas_nuevas",
    "requiere_orden_columnas",
    "frecuencia",
    "campo_periodo_actual",
    "campo_periodo_historico",
    "tipo_periodo",
    "formato_periodo",
    "requiere_transformacion_historico",
    "tipo_estructura_historico",
    "tabla_actual_es_mensual",
]

VALORES_FILA_TECNICA = {
    "",
    "-",
    "0",
    "0.0",
    "0.00",
    "NA",
    "N/A",
    "NN",
    "NULL",
    "NONE",
}


def listar_configuraciones_importacion() -> List[Dict[str, Any]]:
    asegurar_configuracion_importacion()
    query = text(f"""
        SELECT {", ".join(CONFIG_COLUMNS)}
        FROM CobAuto.dbo.importacion_config_cartera WITH(NOLOCK)
        WHERE ISNULL(activo, 1) = 1
        ORDER BY cartera, producto, id_config
    """)
    with engine_siscob.connect() as conn:
        rows = conn.execute(query).mappings().all()
    return [serializar_dict(dict(row)) for row in rows]


def analizar_archivo_importacion(
    id_config: int,
    periodo: str,
    tipo_carga: str,
    archivo_nombre: str,
    contenido: bytes,
    hoja: Optional[str] = None,
) -> Dict[str, Any]:
    validar_periodo(periodo)
    if not contenido:
        raise ValueError("Archivo obligatorio.")

    config = obtener_configuracion(id_config)
    if not config:
        raise ValueError("La configuracion no existe o no esta activa.")

    tabla_destino = (config.get("tabla_destino") or "").strip()
    if not tabla_destino:
        raise ValueError("La configuracion no tiene tabla_destino.")

    columnas_destino = obtener_columnas_tabla(tabla_destino)
    if not columnas_destino:
        raise ValueError(f"La tabla destino no existe o no tiene columnas: {tabla_destino}")

    excel = abrir_excel(contenido, archivo_nombre)
    hojas_disponibles = list(excel.sheet_names)
    hoja_usada = hoja if hoja in hojas_disponibles else hojas_disponibles[0]
    df = pd.read_excel(excel, sheet_name=hoja_usada, dtype=str)
    df = df.where(pd.notna(df), None)
    df, filas_ignoradas = limpiar_filas_tecnicas_importacion(df)

    columnas_archivo = [str(col) for col in df.columns]
    mapa_archivo = mapa_normalizado(columnas_archivo)
    mapa_destino = mapa_normalizado([col["column_name"] for col in columnas_destino])

    columnas_coincidentes = [
        mapa_destino[norm]
        for norm in mapa_destino
        if norm in mapa_archivo
    ]
    columnas_faltantes = [
        original
        for norm, original in mapa_destino.items()
        if norm not in mapa_archivo
    ]
    columnas_nuevas = [
        original
        for norm, original in mapa_archivo.items()
        if norm not in mapa_destino
    ]

    claves = parsear_claves(config.get("clave_cruce"))
    claves_norm = [normalizar_columna(clave) for clave in claves]
    claves_destino_faltantes = [
        claves[i]
        for i, norm in enumerate(claves_norm)
        if norm not in mapa_destino
    ]
    if claves_destino_faltantes:
        raise ValueError(
            "La clave_cruce configurada no existe en la tabla destino: "
            + ", ".join(claves_destino_faltantes)
        )

    columnas_clave_encontradas = [
        claves[i]
        for i, norm in enumerate(claves_norm)
        if norm in mapa_archivo
    ]
    columnas_clave_faltantes_raw = [
        claves[i]
        for i, norm in enumerate(claves_norm)
        if norm not in mapa_archivo
    ]
    campo_periodo_actual = config.get("campo_periodo_actual")
    campo_periodo_norm = normalizar_columna(campo_periodo_actual) if campo_periodo_actual else ""
    columnas_generadas = []
    columnas_clave_faltantes = []

    for columna in columnas_clave_faltantes_raw:
        if campo_periodo_norm and normalizar_columna(columna) == campo_periodo_norm:
            columnas_generadas.append({
                "columna": columna,
                "estado": "GENERADA",
                "tipo": "info",
                "observacion": f"Se completara con el periodo seleccionado: {periodo}",
                "visible_default": True,
            })
        else:
            columnas_clave_faltantes.append(columna)

    faltantes_no_generadas = [
        columna
        for columna in columnas_faltantes
        if not campo_periodo_norm or normalizar_columna(columna) != campo_periodo_norm
    ]

    for columna in columnas_faltantes:
        if campo_periodo_norm and normalizar_columna(columna) == campo_periodo_norm:
            if not any(normalizar_columna(item["columna"]) == campo_periodo_norm for item in columnas_generadas):
                columnas_generadas.append({
                    "columna": columna,
                    "estado": "GENERADA",
                    "tipo": "info",
                    "observacion": f"Se completara con el periodo seleccionado: {periodo}",
                    "visible_default": True,
                })

    alertas = construir_alertas(
        config=config,
        columnas_nuevas=columnas_nuevas,
        columnas_faltantes=faltantes_no_generadas,
        columnas_clave_faltantes=columnas_clave_faltantes,
        columnas_generadas=columnas_generadas,
        mapa_destino=mapa_destino,
    )
    columnas_problema, errores_bloqueantes, advertencias, infos = construir_columnas_problema(
        columnas_clave_faltantes=columnas_clave_faltantes,
        columnas_faltantes=faltantes_no_generadas,
        columnas_nuevas=columnas_nuevas,
        columnas_generadas=columnas_generadas,
        alertas=alertas,
    )
    impacto = analizar_impacto_tabla_destino(
        df=df,
        config=config,
        tabla_destino=tabla_destino,
        periodo=periodo,
        tipo_carga=tipo_carga,
        claves=claves,
        mapa_archivo=mapa_archivo,
        mapa_destino=mapa_destino,
    )
    alertas.extend(impacto["alertas"])
    if filas_ignoradas:
        alertas.append({
            "tipo": "info",
            "mensaje": f"Se omitieron {filas_ignoradas} fila(s) tecnica(s) del archivo.",
        })
    advertencias = [item for item in alertas if item.get("tipo") == "advertencia"]
    infos = [item for item in alertas if item.get("tipo") in ("info", "ok")]

    preview = [
        {**serializar_dict(row), "estado_carga": impacto["estados_carga"][idx]}
        for idx, row in enumerate(df.head(20).to_dict(orient="records"))
    ]

    return {
        "id_config": config["id_config"],
        "cartera": config.get("cartera"),
        "producto": config.get("producto"),
        "tabla_destino": tabla_destino,
        "tabla_historica": config.get("tabla_historica"),
        "periodo": periodo,
        "tipo_carga": tipo_carga,
        "archivo_nombre": archivo_nombre,
        "hojas_disponibles": hojas_disponibles,
        "hoja_usada": hoja_usada,
        "total_filas": int(len(df)),
        "filas_ignoradas": filas_ignoradas,
        "total_columnas_archivo": int(len(columnas_archivo)),
        "columnas_archivo": columnas_archivo,
        "columnas_destino": [col["column_name"] for col in columnas_destino],
        "columnas_coincidentes": [
            {
                "columna": columna,
                "estado": "COINCIDENTE",
                "observacion": "Existe en el archivo y en la tabla destino.",
                "visible_default": False,
            }
            for columna in columnas_coincidentes
        ],
        "columnas_faltantes_en_archivo": faltantes_no_generadas,
        "columnas_nuevas_en_archivo": columnas_nuevas,
        "columnas_generadas": columnas_generadas,
        "columnas_problema": columnas_problema,
        "errores_bloqueantes": errores_bloqueantes,
        "advertencias": advertencias,
        "infos": infos,
        "impacto": impacto["resumen"],
        "diagnostico_cruce": impacto["diagnostico_cruce"],
        "duplicados_archivo": impacto["resumen"]["duplicados_archivo"],
        "filas_duplicadas_preview": impacto["filas_duplicadas_preview"],
        "columnas_clave_cruce": claves,
        "columnas_clave_encontradas": columnas_clave_encontradas,
        "columnas_clave_faltantes": columnas_clave_faltantes,
        "preview": preview,
        "alertas": alertas,
    }


def listar_lotes_importacion(limit: int = 100) -> List[Dict[str, Any]]:
    asegurar_tablas_carga_importacion()
    query = text("""
        SELECT TOP (:limit)
            id_lote, cartera, producto, periodo, tipo_proceso, archivo_nombre,
            total_filas, insertados, actualizados, rechazados, estado,
            observacion, fecha_inicio, fecha_fin
        FROM CobAuto.dbo.importacion_lotes WITH(NOLOCK)
        ORDER BY fecha_inicio DESC, id_lote DESC
    """)
    try:
        with engine_siscob.connect() as conn:
            rows = conn.execute(query, {"limit": limit}).mappings().all()
        return [serializar_dict(dict(row)) for row in rows]
    except DBAPIError as exc:
        mensaje = str(exc).lower()
        if "importacion_lotes" in mensaje and ("invalid object" in mensaje or "no existe" in mensaje):
            return []
        raise


def listar_errores_lote_importacion(id_lote: int, limit: int = 100) -> List[Dict[str, Any]]:
    asegurar_tablas_carga_importacion()
    query = text("""
        SELECT TOP (:limit)
            fila_excel, columna, valor, error, fecha_registro
        FROM CobAuto.dbo.importacion_errores WITH(NOLOCK)
        WHERE id_lote = :id_lote
        ORDER BY id_error
    """)
    with engine_siscob.connect() as conn:
        rows = conn.execute(query, {"id_lote": id_lote, "limit": limit}).mappings().all()
    return [serializar_dict(dict(row)) for row in rows]


def confirmar_carga_importacion(
    id_config: int,
    periodo: str,
    tipo_carga: str,
    usuario: Optional[str],
    archivo_nombre: str,
    contenido: bytes,
    hoja: Optional[str] = None,
) -> Dict[str, Any]:
    tiempo_inicio = time.perf_counter()
    tiempos: Dict[str, float] = {}

    def marcar_tiempo(nombre: str, inicio: float) -> None:
        tiempos[nombre] = round(time.perf_counter() - inicio, 3)

    validar_periodo(periodo)
    tipo_normalizado = normalizar_tipo_carga_confirmacion(tipo_carga)
    if tipo_normalizado not in ("AGREGAR_ACTUALIZAR", "CARGA_INICIAL_MENSUAL"):
        raise ValueError("Este tipo de carga aun no esta implementado de forma segura.")
    es_carga_inicial = tipo_normalizado == "CARGA_INICIAL_MENSUAL"
    if not contenido:
        raise ValueError("Archivo obligatorio.")

    asegurar_tablas_carga_importacion()

    config = obtener_configuracion(id_config)
    if not config:
        raise ValueError("La configuracion no existe o no esta activa.")

    tabla_destino = (config.get("tabla_destino") or "").strip()
    if not tabla_destino:
        raise ValueError("La configuracion no tiene tabla_destino.")

    columnas_destino = obtener_columnas_tabla(tabla_destino)
    if not columnas_destino:
        raise ValueError(f"La tabla destino no existe o no tiene columnas: {tabla_destino}")

    inicio_lectura = time.perf_counter()
    if es_carga_inicial:
        df, hoja_usada = leer_dataframe_importacion(contenido, archivo_nombre, hoja)
    else:
        analisis = analizar_archivo_importacion(
            id_config=id_config,
            periodo=periodo,
            tipo_carga=tipo_normalizado,
            archivo_nombre=archivo_nombre,
            contenido=contenido,
            hoja=hoja,
        )
        if analisis.get("errores_bloqueantes"):
            return {
                "ok": False,
                "estado": "ERROR",
                "mensaje": "La carga no puede confirmarse porque existen errores bloqueantes.",
                "detalle": "; ".join(item.get("observacion") or item.get("mensaje") or "-" for item in analisis["errores_bloqueantes"]),
            }

        df, hoja_usada = leer_dataframe_importacion(contenido, archivo_nombre, hoja)
    marcar_tiempo("lectura_excel", inicio_lectura)
    columnas_archivo = [str(col) for col in df.columns]
    mapa_archivo = mapa_normalizado(columnas_archivo)
    mapa_destino = mapa_normalizado([col["column_name"] for col in columnas_destino])
    columnas_destino_por_nombre = {col["column_name"]: col for col in columnas_destino}
    columnas_destino_por_norm = {
        normalizar_columna(col["column_name"]): col
        for col in columnas_destino
    }
    columnas_identity = {
        normalizar_columna(col["column_name"])
        for col in columnas_destino
        if col.get("is_identity")
    }

    claves = parsear_claves(config.get("clave_cruce"))
    if not claves:
        raise ValueError("No existe clave_cruce configurada para confirmar la carga.")

    claves_destino = []
    for clave in claves:
        clave_destino = mapa_destino.get(normalizar_columna(clave))
        if not clave_destino:
            raise ValueError(f"La clave_cruce '{clave}' no existe en la tabla destino.")
        claves_destino.append(clave_destino)

    inicio_impacto = time.perf_counter()
    if es_carga_inicial:
        impacto = analizar_impacto_solo_archivo(
            df=df,
            config=config,
            periodo=periodo,
            tipo_carga=tipo_normalizado,
            claves=claves,
            mapa_archivo=mapa_archivo,
            mapa_destino=mapa_destino,
        )
    else:
        impacto = analizar_impacto_tabla_destino(
            df=df,
            config=config,
            tabla_destino=tabla_destino,
            periodo=periodo,
            tipo_carga=tipo_normalizado,
            claves=claves,
            mapa_archivo=mapa_archivo,
            mapa_destino=mapa_destino,
        )
    marcar_tiempo("clasificacion", inicio_impacto)
    estados = impacto["estados_carga"]
    total_nuevo = estados.count("NUEVO")
    total_existente = estados.count("EXISTENTE")
    total_duplicado = estados.count("DUPLICADO_ARCHIVO")
    total_incompleta = estados.count("CLAVE_INCOMPLETA")

    campo_periodo = config.get("campo_periodo_actual")
    campo_periodo_norm = normalizar_columna(campo_periodo) if campo_periodo else ""
    valor_periodo = valor_periodo_configurado(config, periodo)
    columnas_generadas: List[str] = []

    columnas_archivo_validas: List[Tuple[str, str, Dict[str, Any]]] = []
    columnas_omitidas: List[str] = []
    for columna_archivo in columnas_archivo:
        norm = normalizar_columna(columna_archivo)
        destino_col = mapa_destino.get(norm)
        if destino_col and norm not in columnas_identity:
            columnas_archivo_validas.append((columna_archivo, destino_col, columnas_destino_por_nombre[destino_col]))
        elif not destino_col:
            columnas_omitidas.append(columna_archivo)

    if campo_periodo_norm and campo_periodo_norm in columnas_destino_por_norm and campo_periodo_norm not in mapa_archivo:
        columnas_generadas.append(columnas_destino_por_norm[campo_periodo_norm]["column_name"])

    columnas_insert_usadas = sorted({
        destino_col
        for _, destino_col, _ in columnas_archivo_validas
    } | set(columnas_generadas))
    columnas_update_usadas = sorted({
        destino_col
        for _, destino_col, _ in columnas_archivo_validas
        if destino_col not in claves_destino
    } | {col for col in columnas_generadas if col not in claves_destino})

    print("CONFIRMAR total filas", len(df))
    print("CONFIRMAR existentes", total_existente)
    print("CONFIRMAR nuevos", total_nuevo)
    print("CONFIRMAR columnas update", columnas_update_usadas)
    print("UPDATE columnas:", columnas_update_usadas)

    if total_existente > 0 and not columnas_update_usadas and not es_carga_inicial:
        raise ValueError("No hay columnas validas para actualizar.")
    if (total_nuevo > 0 or es_carga_inicial) and not columnas_insert_usadas:
        raise ValueError("No hay columnas validas para insertar.")
    if es_carga_inicial and total_nuevo + total_existente <= 0:
        raise ValueError("No hay filas validas para reemplazar la cartera activa.")

    lote_id = None
    insertados = 0
    actualizados = 0
    rechazados = 0
    total_updates_ejecutados = 0
    total_updates_sin_afectar_filas = 0
    total_inserts_ejecutados = 0
    total_registros_reemplazados = 0
    motivos_rechazo: List[Dict[str, Any]] = []
    debug_updates: List[Dict[str, Any]] = []
    usuario_limpio = str(usuario or "SIN_USUARIO").strip()[:50]
    destino_sql = nombre_tabla_sql(tabla_destino)

    inicio_lote = time.perf_counter()
    with engine_siscob.begin() as conn_lote:
        lote_id = crear_lote_importacion(
            conn=conn_lote,
            config=config,
            periodo=periodo,
            tipo_proceso=tipo_normalizado,
            archivo_nombre=archivo_nombre,
            usuario=usuario_limpio,
            total_filas=len(df),
        )
    marcar_tiempo("crear_lote", inicio_lote)

    try:
        with engine_siscob.begin() as conn:
            if es_carga_inicial:
                inicio_delete = time.perf_counter()
                delete_result = conn.execute(text(f"DELETE FROM {destino_sql}"))
                total_registros_reemplazados = int(delete_result.rowcount or 0)
                marcar_tiempo("limpiar_destino", inicio_delete)

                inicio_staging_setup = time.perf_counter()
                columnas_insert_ordenadas = list(columnas_insert_usadas)
                staging_sql = asegurar_staging_importacion(
                    conn=conn,
                    id_config=int(config["id_config"]),
                    columnas=columnas_insert_ordenadas,
                    columnas_destino_por_nombre=columnas_destino_por_nombre,
                )
                conn.execute(
                    text(f"DELETE FROM {staging_sql} WHERE [__id_lote] = :id_lote"),
                    {"id_lote": lote_id},
                )
                marcar_tiempo("preparar_staging", inicio_staging_setup)

                filas_staging_batch = []
                inicio_staging = time.perf_counter()

                for idx, row in df.iterrows():
                    estado = estados[idx] if idx < len(estados) else "CLAVE_INCOMPLETA"
                    fila_excel = idx + 2
                    if estado in ("DUPLICADO_ARCHIVO", "CLAVE_INCOMPLETA"):
                        rechazados += 1
                        agregar_motivo_rechazo(
                            motivos_rechazo, fila_excel, "clave_cruce", estado
                        )
                        registrar_error_importacion(
                            conn=conn,
                            id_lote=lote_id,
                            fila_excel=fila_excel,
                            columna="clave_cruce",
                            valor=clave_fila_texto(row, claves, mapa_archivo, config, periodo),
                            error=estado,
                        )
                        continue

                    valores_insert = valores_insert_importacion(
                        row=row,
                        columnas_archivo_validas=columnas_archivo_validas,
                        columnas_generadas=columnas_generadas,
                        valor_periodo=valor_periodo,
                    )
                    if not valores_insert:
                        rechazados += 1
                        agregar_motivo_rechazo(
                            motivos_rechazo, fila_excel, "INSERT", "No hay columnas compatibles para insertar."
                        )
                        registrar_error_importacion(
                            conn, lote_id, fila_excel, "-", None,
                            "No hay columnas compatibles para insertar."
                        )
                        continue
                    filas_staging_batch.append({
                        "fila_excel": fila_excel,
                        "valores": valores_insert,
                    })
                    if len(filas_staging_batch) >= 1000:
                        insertar_filas_staging_importacion(
                            conn=conn,
                            staging_sql=staging_sql,
                            id_lote=lote_id,
                            filas=filas_staging_batch,
                            columnas=columnas_insert_ordenadas,
                        )
                        insertados += len(filas_staging_batch)
                        filas_staging_batch = []

                if filas_staging_batch:
                    insertar_filas_staging_importacion(
                        conn=conn,
                        staging_sql=staging_sql,
                        id_lote=lote_id,
                        filas=filas_staging_batch,
                        columnas=columnas_insert_ordenadas,
                    )
                    insertados += len(filas_staging_batch)

                marcar_tiempo("cargar_staging", inicio_staging)

                if insertados:
                    inicio_insert_final = time.perf_counter()
                    columnas_sql = ", ".join(quote_identificador(col) for col in columnas_insert_ordenadas)
                    select_sql = ", ".join(quote_identificador(col) for col in columnas_insert_ordenadas)
                    conn.execute(text(f"""
                        INSERT INTO {destino_sql} ({columnas_sql})
                        SELECT {select_sql}
                        FROM {staging_sql}
                        WHERE [__id_lote] = :id_lote
                          AND [__estado_fila] = 'VALIDO'
                    """), {"id_lote": lote_id})
                    total_inserts_ejecutados = insertados
                    marcar_tiempo("insertar_destino", inicio_insert_final)

            inicio_proceso_fila = time.perf_counter()
            for idx, row in (() if es_carga_inicial else df.iterrows()):
                estado = estados[idx] if idx < len(estados) else "CLAVE_INCOMPLETA"
                fila_excel = idx + 2

                if estado in ("DUPLICADO_ARCHIVO", "CLAVE_INCOMPLETA"):
                    rechazados += 1
                    agregar_motivo_rechazo(
                        motivos_rechazo, fila_excel, "clave_cruce", estado
                    )
                    registrar_error_importacion(
                        conn=conn,
                        id_lote=lote_id,
                        fila_excel=fila_excel,
                        columna="clave_cruce",
                        valor=clave_fila_texto(row, claves, mapa_archivo, config, periodo),
                        error=estado,
                    )
                    continue

                valores_insert = valores_insert_importacion(
                    row=row,
                    columnas_archivo_validas=columnas_archivo_validas,
                    columnas_generadas=columnas_generadas,
                    valor_periodo=valor_periodo,
                )
                where_sql, where_params = construir_where_clave_importacion(
                    row=row,
                    claves_destino=claves_destino,
                    mapa_archivo=mapa_archivo,
                    config=config,
                    periodo=periodo,
                    columnas_destino_por_nombre=columnas_destino_por_nombre,
                )

                print("UPDATE where:", ",".join(claves_destino))
                print("Fila estado:", estado)

                if estado == "NUEVO":
                    if not valores_insert:
                        rechazados += 1
                        agregar_motivo_rechazo(
                            motivos_rechazo, fila_excel, "INSERT", "No hay columnas compatibles para insertar."
                        )
                        registrar_error_importacion(
                            conn, lote_id, fila_excel, "-", None,
                            "No hay columnas compatibles para insertar."
                        )
                        continue
                    columnas_sql = ", ".join(quote_identificador(col) for col in valores_insert)
                    params_sql = {f"v{i}": valor for i, valor in enumerate(valores_insert.values())}
                    values_sql = ", ".join(f":v{i}" for i in range(len(valores_insert)))
                    conn.execute(text(f"""
                        INSERT INTO {destino_sql} ({columnas_sql})
                        VALUES ({values_sql})
                    """), params_sql)
                    insertados += 1
                    total_inserts_ejecutados += 1
                elif estado == "EXISTENTE":
                    valores_update = valores_update_importacion(
                        row=row,
                        columnas_archivo_validas=columnas_archivo_validas,
                        columnas_generadas=columnas_generadas,
                        valor_periodo=valor_periodo,
                        claves_destino=claves_destino,
                    )
                    if not valores_update:
                        raise ValueError("No hay columnas validas para actualizar.")
                    count_previo = int(conn.execute(
                        text(f"SELECT COUNT(1) FROM {destino_sql} WHERE {where_sql}"),
                        where_params,
                    ).scalar() or 0)
                    set_parts = []
                    params_sql = dict(where_params)
                    for i, (columna, valor) in enumerate(valores_update.items()):
                        param_name = f"u{i}"
                        set_parts.append(f"{quote_identificador(columna)} = :{param_name}")
                        params_sql[param_name] = valor
                    update_sql = f"""
                            UPDATE {destino_sql}
                            SET {", ".join(set_parts)}
                            WHERE {where_sql}
                        """
                    try:
                        result = conn.execute(text(update_sql), params_sql)
                    except Exception as update_exc:
                        print("Error update:", update_exc)
                        raise
                    rowcount = int(result.rowcount or 0)
                    if len(debug_updates) < 5:
                        debug_updates.append({
                            "fila_excel": fila_excel,
                            "where_sql_usado": where_sql,
                            "params_where_usados": dict(where_params),
                            "select_count_previo_update": count_previo,
                            "update_sql_usado": " ".join(update_sql.split()),
                            "columnas_set_usadas": list(valores_update.keys()),
                            "rowcount_update": rowcount,
                        })
                    if count_previo <= 0:
                        rechazados += 1
                        total_updates_sin_afectar_filas += 1
                        agregar_motivo_rechazo(
                            motivos_rechazo,
                            fila_excel,
                            "clave_cruce",
                            "UPDATE no afecto filas. Revisar clave de cruce.",
                        )
                        registrar_error_importacion(
                            conn=conn,
                            id_lote=lote_id,
                            fila_excel=fila_excel,
                            columna="clave_cruce",
                            valor=clave_fila_texto(row, claves, mapa_archivo, config, periodo),
                            error=(
                                "UPDATE no afecto filas. Revisar clave de cruce. "
                                f"COUNT={count_previo}; WHERE={where_sql}; PARAMS={where_params}"
                            ),
                        )
                        continue
                    if rowcount == 0:
                        total_updates_sin_afectar_filas += 1
                    filas_sql_afectadas = rowcount if rowcount > 0 else count_previo
                    actualizados += 1
                    total_updates_ejecutados += filas_sql_afectadas
                else:
                    rechazados += 1
                    agregar_motivo_rechazo(
                        motivos_rechazo, fila_excel, "estado_carga", f"Estado no cargable: {estado}"
                    )
                    registrar_error_importacion(
                        conn, lote_id, fila_excel, "estado_carga", estado, f"Estado no cargable: {estado}"
                    )
            if not es_carga_inicial:
                marcar_tiempo("procesar_filas", inicio_proceso_fila)

            total_procesado = insertados + actualizados + rechazados
            if len(df) > 0 and total_procesado == 0:
                raise ValueError("No se proceso ningun registro. Revisar clasificacion o ejecucion SQL.")
            if total_procesado != len(df):
                raise ValueError(
                    f"Conteo inconsistente: total_filas={len(df)}, procesado={total_procesado}."
                )

            print("CONFIRMAR updates ejecutados", total_updates_ejecutados)
            estado_lote = "CARGADO"
            observacion_lote = "Carga completada correctamente"
            if es_carga_inicial:
                observacion_lote = (
                    "Carga inicial mensual completada. "
                    f"Se reemplazaron {total_registros_reemplazados} registros activos previos."
                )
            if len(df) > 0 and rechazados == len(df):
                estado_lote = "ERROR"
                observacion_lote = "Todas las filas fueron rechazadas. No se marca lote como CARGADO."
            elif insertados + actualizados <= 0:
                estado_lote = "ERROR"
                observacion_lote = "No se procesó ningún registro. Revisar clasificación o ejecución SQL."

            if rechazados > 0 and insertados + actualizados > 0:
                estado_lote = "OBSERVADO"
                observacion_lote = "Carga procesada con rechazos parciales."
            if len(df) > 0 and rechazados == len(df):
                estado_lote = "ERROR"
                observacion_lote = "Todas las filas fueron rechazadas. No se marcara como CARGADO."

            actualizar_lote_importacion(
                conn=conn,
                id_lote=lote_id,
                estado=estado_lote,
                insertados=insertados,
                actualizados=actualizados,
                rechazados=rechazados,
                observacion=observacion_lote,
            )
            tiempos["total"] = round(time.perf_counter() - tiempo_inicio, 3)
    except Exception as exc:
        if lote_id:
            marcar_lote_error(
                id_lote=lote_id,
                observacion=str(exc),
            )
        return {
            "ok": False,
            "id_lote": lote_id,
            "estado": "ERROR",
            "cartera": config.get("cartera"),
            "producto": config.get("producto"),
            "periodo": periodo,
            "tabla_destino": tabla_destino,
            "total_filas": int(len(df)),
            "insertados": insertados,
            "actualizados": actualizados,
            "rechazados": rechazados or int(len(df)),
            "observacion": str(exc),
            "errores_preview": listar_errores_lote_importacion(lote_id, limit=10) if lote_id else [],
            "motivo_rechazo_primeras_10": motivos_rechazo[:10],
            "columnas_update_usadas": columnas_update_usadas,
            "columnas_insert_usadas": columnas_insert_usadas,
            "total_updates_ejecutados": total_updates_ejecutados,
            "total_updates_sin_afectar_filas": total_updates_sin_afectar_filas,
            "total_registros_reemplazados": total_registros_reemplazados,
            "tiempos": tiempos,
            "debug_updates_primeras_5": debug_updates,
        }

    estado_final = estado_lote
    tiempos["total"] = round(time.perf_counter() - tiempo_inicio, 3)
    return {
        "ok": insertados + actualizados > 0,
        "id_lote": lote_id,
        "estado": estado_final,
        "cartera": config.get("cartera"),
        "producto": config.get("producto"),
        "periodo": periodo,
        "tabla_destino": tabla_destino,
        "total_filas": int(len(df)),
        "insertados": insertados,
        "actualizados": actualizados,
        "rechazados": rechazados,
        "columnas_omitidas": columnas_omitidas,
        "columnas_generadas": columnas_generadas,
        "errores_preview": listar_errores_lote_importacion(lote_id, limit=10) if lote_id else [],
        "motivo_rechazo_primeras_10": motivos_rechazo[:10],
        "columnas_update_usadas": columnas_update_usadas,
        "columnas_insert_usadas": columnas_insert_usadas,
        "total_updates_ejecutados": total_updates_ejecutados,
        "total_updates_sin_afectar_filas": total_updates_sin_afectar_filas,
        "total_registros_reemplazados": total_registros_reemplazados,
        "tiempos": tiempos,
        "debug": {
            "total_filas_excel_leidas": int(len(df)),
            "total_clasificadas_nuevo": total_nuevo,
            "total_clasificadas_existente": total_existente,
            "total_duplicado_archivo": total_duplicado,
            "total_clave_incompleta": total_incompleta,
            "columnas_update_usadas": columnas_update_usadas,
            "columnas_insert_usadas": columnas_insert_usadas,
            "total_updates_ejecutados": total_updates_ejecutados,
            "total_inserts_ejecutados": total_inserts_ejecutados,
            "total_updates_sin_afectar_filas": total_updates_sin_afectar_filas,
            "total_registros_reemplazados": total_registros_reemplazados,
            "tiempos": tiempos,
            "total_rechazados_registrados": rechazados,
            "motivo_rechazo_primeras_10": motivos_rechazo[:10],
            "debug_updates_primeras_5": debug_updates,
        },
        "hoja_usada": hoja_usada,
        "observacion": observacion_lote,
    }


def validar_cierre_historico(id_config: int, periodo: str) -> Dict[str, Any]:
    validar_periodo(periodo)
    asegurar_tabla_cierres_historicos()

    config = obtener_configuracion(id_config)
    if not config:
        raise ValueError("La configuracion no existe o no esta activa.")

    tabla_origen = (config.get("tabla_destino") or "").strip()
    tabla_historica = (config.get("tabla_historica") or "").strip()
    tipo_estructura = str(config.get("tipo_estructura_historico") or "").upper().strip()
    campo_periodo = (config.get("campo_periodo_historico") or "").strip()
    campo_periodo = campo_periodo_historico_efectivo(config, tabla_historica, campo_periodo)
    alertas: List[Dict[str, str]] = []

    if es_configuracion_saldos(config):
        return {
            "id_config": id_config,
            "cartera": config.get("cartera"),
            "producto": config.get("producto"),
            "periodo": periodo,
            "tabla_origen": tabla_origen,
            "tabla_historica": tabla_historica or None,
            "tipo_estructura_historico": tipo_estructura or None,
            "campo_periodo_historico": campo_periodo or None,
            "periodo_convertido": None,
            "total_origen": 0,
            "total_existente_previo": 0,
            "puede_cerrar": False,
            "alertas": [{
                "tipo": "info",
                "mensaje": "Las configuraciones de SALDOS no ejecutan cierre historico desde este modulo.",
            }],
        }

    if tipo_estructura == "SIN_HISTORICO":
        return {
            "id_config": id_config,
            "cartera": config.get("cartera"),
            "producto": config.get("producto"),
            "periodo": periodo,
            "tabla_origen": tabla_origen,
            "tabla_historica": tabla_historica or None,
            "tipo_estructura_historico": tipo_estructura,
            "campo_periodo_historico": campo_periodo or None,
            "periodo_convertido": None,
            "total_origen": 0,
            "total_existente_previo": 0,
            "puede_cerrar": False,
            "alertas": [{
                "tipo": "info",
                "mensaje": "Esta configuracion esta marcada como SIN_HISTORICO. No aplica cierre mensual.",
            }],
        }

    if tipo_estructura not in ("MISMA_ESTRUCTURA", "MAPEO_HISTORICO"):
        alertas.append({
            "tipo": "error",
            "mensaje": "Tipo de estructura historica no valido o no configurado.",
        })

    if not tabla_origen:
        alertas.append({"tipo": "error", "mensaje": "La configuracion no tiene tabla origen/tabla_destino."})
    if not tabla_historica:
        alertas.append({"tipo": "error", "mensaje": "La configuracion no tiene tabla_historica."})
    if not campo_periodo:
        alertas.append({"tipo": "error", "mensaje": "La configuracion no tiene campo_periodo_historico."})

    columnas_origen = obtener_columnas_tabla(tabla_origen) if tabla_origen else []
    columnas_historico = obtener_columnas_tabla(tabla_historica) if tabla_historica else []

    if tabla_origen and not columnas_origen:
        alertas.append({"tipo": "error", "mensaje": f"La tabla origen no existe o no tiene columnas: {tabla_origen}"})
    if tabla_historica and not columnas_historico:
        alertas.append({"tipo": "error", "mensaje": f"La tabla historica no existe o no tiene columnas: {tabla_historica}"})
    validar_ruta_historica_compartamos(
        tabla_origen=tabla_origen,
        tabla_historica=tabla_historica,
        alertas=alertas,
    )

    mapa_historico = mapa_normalizado([col["column_name"] for col in columnas_historico])
    campo_periodo_historico = mapa_historico.get(normalizar_columna(campo_periodo)) if campo_periodo else None
    if campo_periodo and columnas_historico and not campo_periodo_historico:
        if permite_historico_sin_periodo(config, tabla_historica):
            alertas.append({
                "tipo": "advertencia",
                "mensaje": (
                    f"El historico no tiene campo periodo '{campo_periodo}'. "
                    "El cierre se controlara por importacion_cierres_historicos y no permitira reemplazo automatico por periodo."
                ),
            })
            campo_periodo_historico = None
        else:
            alertas.append({
                "tipo": "error",
                "mensaje": f"El campo_periodo_historico '{campo_periodo}' no existe en la tabla historica.",
            })

    total_origen = contar_tabla(tabla_origen) if columnas_origen else 0
    periodo_convertido = valor_periodo_configurado(config, periodo) if campo_periodo_historico else periodo
    total_existente = 0
    if columnas_historico and campo_periodo_historico:
        total_existente = contar_periodo_historico(
            tabla_historica=tabla_historica,
            campo_periodo=campo_periodo_historico,
            periodo=periodo,
            config=config,
        )
    elif columnas_historico:
        total_existente = contar_cierre_control_previo(id_config, periodo)

    if total_origen == 0 and not any(a.get("tipo") == "error" for a in alertas):
        alertas.append({"tipo": "advertencia", "mensaje": "La tabla origen no tiene registros para cerrar."})

    if total_existente > 0:
        mensaje_existente = (
            f"Ya existe un cierre registrado para el periodo {periodo}."
            if not campo_periodo_historico
            else f"Ya existen {total_existente} registros en el historico para el periodo {periodo}."
        )
        alertas.append({"tipo": "advertencia", "mensaje": mensaje_existente})

    if not any(a.get("tipo") in ("error", "advertencia") for a in alertas):
        alertas.append({"tipo": "ok", "mensaje": "Validacion correcta. El cierre puede ejecutarse."})

    return {
        "id_config": id_config,
        "cartera": config.get("cartera"),
        "producto": config.get("producto"),
        "periodo": periodo,
        "tabla_origen": tabla_origen,
        "tabla_historica": tabla_historica,
        "tipo_estructura_historico": tipo_estructura,
        "campo_periodo_historico": campo_periodo_historico or None,
        "periodo_convertido": serializar_valor(periodo_convertido),
        "total_origen": total_origen,
        "total_existente_previo": total_existente,
        "puede_cerrar": total_origen > 0 and not any(a.get("tipo") == "error" for a in alertas),
        "alertas": alertas,
    }


def ejecutar_cierre_historico(id_config: int, periodo: str, usuario: Optional[str], modo: str) -> Dict[str, Any]:
    modo = str(modo or "").upper().strip()
    if modo not in ("INSERTAR_SI_NO_EXISTE", "REEMPLAZAR_PERIODO"):
        raise ValueError("Modo de cierre no valido.")

    validacion = validar_cierre_historico(id_config=id_config, periodo=periodo)
    if not validacion.get("puede_cerrar"):
        raise ValueError("El cierre no puede ejecutarse. Revisa las alertas de validacion.")
    if validacion.get("tipo_estructura_historico") == "SIN_HISTORICO":
        raise ValueError("No se ejecuta cierre para configuraciones SIN_HISTORICO.")
    if validacion.get("total_existente_previo", 0) > 0 and modo == "INSERTAR_SI_NO_EXISTE":
        raise ValueError("Ya existe data historica del periodo. Usa REEMPLAZAR_PERIODO si corresponde.")

    config = obtener_configuracion(id_config)
    if not config:
        raise ValueError("La configuracion no existe o no esta activa.")

    tabla_origen = validacion["tabla_origen"]
    tabla_historica = validacion["tabla_historica"]
    campo_periodo = validacion["campo_periodo_historico"]
    columnas_origen = obtener_columnas_tabla(tabla_origen)
    columnas_historico = obtener_columnas_tabla(tabla_historica)
    insert_columns, select_expressions, params, faltantes_obligatorias = preparar_columnas_cierre(
        columnas_origen=columnas_origen,
        columnas_historico=columnas_historico,
        campo_periodo=campo_periodo,
        config=config,
        periodo=periodo,
    )

    if faltantes_obligatorias:
        raise ValueError(
            "La tabla historica tiene columnas obligatorias que no existen en origen ni se pueden generar: "
            + ", ".join(faltantes_obligatorias)
        )
    if not insert_columns:
        raise ValueError("No hay columnas compatibles para insertar en la tabla historica.")

    origen_sql = nombre_tabla_sql(tabla_origen)
    historico_sql = nombre_tabla_sql(tabla_historica)
    where_periodo = None
    where_params: Dict[str, Any] = {}
    if campo_periodo:
        where_periodo, where_params = condicion_periodo_historico(campo_periodo, periodo, config)
    params.update(where_params)

    usuario_limpio = str(usuario or "SIN_USUARIO").strip()[:50]
    cierre_id = None
    total_insertado = 0

    try:
        with engine_siscob.begin() as conn:
            cierre_id = conn.execute(text("""
                INSERT INTO CobAuto.dbo.importacion_cierres_historicos
                    (id_config, cartera, producto, periodo, tabla_origen, tabla_historica,
                     total_origen, total_existente_previo, usuario, estado, observacion)
                OUTPUT INSERTED.id_cierre
                VALUES
                    (:id_config, :cartera, :producto, :periodo, :tabla_origen, :tabla_historica,
                     :total_origen, :total_existente_previo, :usuario, 'PROCESANDO', :observacion);
            """), {
                "id_config": id_config,
                "cartera": config.get("cartera") or "SIN_CARTERA",
                "producto": config.get("producto"),
                "periodo": periodo,
                "tabla_origen": tabla_origen,
                "tabla_historica": tabla_historica,
                "total_origen": validacion["total_origen"],
                "total_existente_previo": validacion["total_existente_previo"],
                "usuario": usuario_limpio,
                "observacion": f"Modo: {modo}",
            }).scalar()

            if modo == "REEMPLAZAR_PERIODO":
                if not where_periodo:
                    raise ValueError("Este historico no tiene campo periodo. No se puede reemplazar automaticamente por periodo.")
                conn.execute(text(f"DELETE FROM {historico_sql} WHERE {where_periodo}"), params)
            else:
                if where_periodo:
                    existente_en_transaccion = int(conn.execute(text(f"""
                        SELECT COUNT(1)
                        FROM {historico_sql} WITH(UPDLOCK, HOLDLOCK)
                        WHERE {where_periodo}
                    """), params).scalar() or 0)
                else:
                    existente_en_transaccion = contar_cierre_control_previo(id_config, periodo)
                if existente_en_transaccion > 0:
                    raise ValueError(
                        "El periodo historico ya tiene registros. Valida nuevamente y usa REEMPLAZAR_PERIODO si corresponde."
                    )

            insert_sql = text(f"""
                INSERT INTO {historico_sql}
                    ({", ".join(insert_columns)})
                SELECT
                    {", ".join(select_expressions)}
                FROM {origen_sql} WITH(NOLOCK)
            """)
            conn.execute(insert_sql, params)
            total_insertado = validacion["total_origen"]

            conn.execute(text("""
                UPDATE CobAuto.dbo.importacion_cierres_historicos
                SET total_insertado = :total_insertado,
                    estado = 'CERRADO',
                    observacion = :observacion,
                    fecha_fin = GETDATE()
                WHERE id_cierre = :id_cierre
            """), {
                "id_cierre": cierre_id,
                "total_insertado": total_insertado,
                "observacion": f"Cierre ejecutado correctamente. Modo: {modo}",
            })
    except Exception as exc:
        registrar_cierre_fallido(
            id_config=id_config,
            config=config,
            periodo=periodo,
            tabla_origen=tabla_origen,
            tabla_historica=tabla_historica,
            total_origen=validacion["total_origen"],
            total_existente=validacion["total_existente_previo"],
            usuario=usuario_limpio,
            observacion=str(exc),
            cierre_id=cierre_id,
        )
        raise

    return {
        "id_cierre": cierre_id,
        "id_config": id_config,
        "periodo": periodo,
        "tabla_origen": tabla_origen,
        "tabla_historica": tabla_historica,
        "insertados": total_insertado,
        "estado": "CERRADO",
        "fecha": datetime.now().isoformat(timespec="seconds"),
        "mensaje": "Cierre historico ejecutado correctamente.",
    }


def obtener_configuracion(id_config: int) -> Optional[Dict[str, Any]]:
    asegurar_configuracion_importacion()
    query = text(f"""
        SELECT {", ".join(CONFIG_COLUMNS)}
        FROM CobAuto.dbo.importacion_config_cartera WITH(NOLOCK)
        WHERE id_config = :id_config
          AND ISNULL(activo, 1) = 1
    """)
    with engine_siscob.connect() as conn:
        row = conn.execute(query, {"id_config": id_config}).mappings().first()
    return serializar_dict(dict(row)) if row else None


def obtener_columnas_tabla(tabla: str) -> List[Dict[str, Any]]:
    database, schema, table_name = parsear_nombre_tabla(tabla)
    query = text(f"""
        SELECT
            c.name AS column_name,
            t.name AS data_type,
            c.max_length AS max_length,
            c.precision AS precision,
            c.scale AS scale,
            c.column_id AS ordinal_position,
            c.is_nullable AS is_nullable,
            c.is_identity AS is_identity,
            CASE WHEN dc.object_id IS NULL THEN 0 ELSE 1 END AS has_default
        FROM [{database}].sys.columns c
        INNER JOIN [{database}].sys.tables tb
            ON c.object_id = tb.object_id
        INNER JOIN [{database}].sys.schemas s
            ON tb.schema_id = s.schema_id
        INNER JOIN [{database}].sys.types t
            ON c.user_type_id = t.user_type_id
        LEFT JOIN [{database}].sys.default_constraints dc
            ON c.default_object_id = dc.object_id
        WHERE s.name = :schema
          AND tb.name = :table_name
        ORDER BY c.column_id
    """)
    with engine_siscob.connect() as conn:
        rows = conn.execute(query, {"schema": schema, "table_name": table_name}).mappings().all()
    return [serializar_dict(dict(row)) for row in rows]


def analizar_impacto_tabla_destino(
    df: pd.DataFrame,
    config: Dict[str, Any],
    tabla_destino: str,
    periodo: str,
    tipo_carga: str,
    claves: List[str],
    mapa_archivo: Dict[str, str],
    mapa_destino: Dict[str, str],
) -> Dict[str, Any]:
    if not claves:
        estados = ["CLAVE_INCOMPLETA"] * len(df)
        return {
            "resumen": resumen_impacto(estados),
            "estados_carga": estados,
            "filas_duplicadas_preview": [],
            "alertas": [{
                "tipo": "error",
                "mensaje": "No existe clave_cruce configurada para comparar contra la tabla destino.",
            }],
        }

    claves_destino = [mapa_destino[normalizar_columna(clave)] for clave in claves]
    claves_norm = [normalizar_columna(clave) for clave in claves]
    campo_periodo = config.get("campo_periodo_actual")
    campo_periodo_norm = normalizar_columna(campo_periodo) if campo_periodo else ""
    valor_periodo = valor_periodo_configurado(config, periodo)

    claves_archivo: List[Tuple[Any, ...]] = []
    claves_incompletas: List[bool] = []
    for _, row in df.iterrows():
        valores = []
        incompleta = False
        for indice, clave_norm in enumerate(claves_norm):
            if clave_norm in mapa_archivo:
                valor_cruce = row.get(mapa_archivo[clave_norm])
            elif campo_periodo_norm and clave_norm == campo_periodo_norm:
                valor_cruce = valor_periodo
            else:
                valor_cruce = None

            normalizado = normalizar_valor_cruce(valor_cruce, es_fecha=clave_norm == campo_periodo_norm and es_periodo_fecha(config))
            if normalizado in ("", None):
                incompleta = True
            valores.append(normalizado)

        claves_archivo.append(tuple(valores))
        claves_incompletas.append(incompleta)

    conteo_claves: Dict[Tuple[Any, ...], int] = {}
    for clave, incompleta in zip(claves_archivo, claves_incompletas):
        if incompleta:
            continue
        conteo_claves[clave] = conteo_claves.get(clave, 0) + 1

    destino = obtener_claves_existentes_destino(
        tabla_destino=tabla_destino,
        claves_destino=claves_destino,
        campo_periodo=campo_periodo,
        periodo=periodo,
        config=config,
        mapa_destino=mapa_destino,
    )
    claves_existentes = destino["claves"]

    estados: List[str] = []
    for clave, incompleta in zip(claves_archivo, claves_incompletas):
        if incompleta:
            estados.append("CLAVE_INCOMPLETA")
        elif conteo_claves.get(clave, 0) > 1:
            estados.append("DUPLICADO_ARCHIVO")
        elif clave in claves_existentes:
            estados.append("EXISTENTE")
        else:
            estados.append("NUEVO")

    duplicados_preview = construir_preview_duplicados(df, estados, claves_destino, claves_archivo)
    resumen = resumen_impacto(estados)
    alertas = alertas_impacto(tipo_carga, resumen)
    total_coincidencias = sum(1 for estado in estados if estado == "EXISTENTE")
    diagnostico = {
        "id_config_usado": config.get("id_config"),
        "tabla_destino_usada": tabla_destino,
        "clave_cruce_usada": ",".join(claves),
        "tabla_actual_es_mensual": es_tabla_actual_mensual(config),
        "campo_periodo_actual": campo_periodo,
        "filtro_periodo_aplicado": "si" if destino["filtro_periodo_aplicado"] else "no",
        "total_claves_archivo": len([clave for clave, incompleta in zip(claves_archivo, claves_incompletas) if not incompleta]),
        "total_claves_destino_leidas": len(claves_existentes),
        "total_coincidencias": total_coincidencias,
        "preview_claves_archivo": [
            clave_debug(claves_destino, clave)
            for clave, incompleta in list(zip(claves_archivo, claves_incompletas))[:10]
            if not incompleta
        ],
        "preview_claves_destino": [
            clave_debug(claves_destino, clave)
            for clave in list(claves_existentes)[:10]
        ],
        "query_destino_debug": destino["query_debug"],
    }

    return {
        "resumen": resumen,
        "estados_carga": estados,
        "filas_duplicadas_preview": duplicados_preview,
        "alertas": alertas,
        "diagnostico_cruce": diagnostico,
    }


def analizar_impacto_solo_archivo(
    df: pd.DataFrame,
    config: Dict[str, Any],
    periodo: str,
    tipo_carga: str,
    claves: List[str],
    mapa_archivo: Dict[str, str],
    mapa_destino: Dict[str, str],
) -> Dict[str, Any]:
    if not claves:
        estados = ["CLAVE_INCOMPLETA"] * len(df)
        return {
            "resumen": resumen_impacto(estados),
            "estados_carga": estados,
            "filas_duplicadas_preview": [],
            "alertas": [{
                "tipo": "error",
                "mensaje": "No existe clave_cruce configurada para validar el archivo.",
            }],
            "diagnostico_cruce": {},
        }

    claves_destino = [mapa_destino[normalizar_columna(clave)] for clave in claves]
    claves_norm = [normalizar_columna(clave) for clave in claves]
    campo_periodo = config.get("campo_periodo_actual")
    campo_periodo_norm = normalizar_columna(campo_periodo) if campo_periodo else ""
    valor_periodo = valor_periodo_configurado(config, periodo)

    claves_archivo: List[Tuple[Any, ...]] = []
    claves_incompletas: List[bool] = []
    for _, row in df.iterrows():
        valores = []
        incompleta = False
        for clave_norm in claves_norm:
            if clave_norm in mapa_archivo:
                valor_cruce = row.get(mapa_archivo[clave_norm])
            elif campo_periodo_norm and clave_norm == campo_periodo_norm:
                valor_cruce = valor_periodo
            else:
                valor_cruce = None

            normalizado = normalizar_valor_cruce(
                valor_cruce,
                es_fecha=clave_norm == campo_periodo_norm and es_periodo_fecha(config),
            )
            if normalizado in ("", None):
                incompleta = True
            valores.append(normalizado)

        claves_archivo.append(tuple(valores))
        claves_incompletas.append(incompleta)

    conteo_claves: Dict[Tuple[Any, ...], int] = {}
    for clave, incompleta in zip(claves_archivo, claves_incompletas):
        if incompleta:
            continue
        conteo_claves[clave] = conteo_claves.get(clave, 0) + 1

    estados: List[str] = []
    for clave, incompleta in zip(claves_archivo, claves_incompletas):
        if incompleta:
            estados.append("CLAVE_INCOMPLETA")
        elif conteo_claves.get(clave, 0) > 1:
            estados.append("DUPLICADO_ARCHIVO")
        else:
            estados.append("NUEVO")

    duplicados_preview = construir_preview_duplicados(df, estados, claves_destino, claves_archivo)
    resumen = resumen_impacto(estados)
    alertas = alertas_impacto(tipo_carga, resumen)
    diagnostico = {
        "id_config_usado": config.get("id_config"),
        "tabla_destino_usada": config.get("tabla_destino"),
        "clave_cruce_usada": ",".join(claves),
        "tabla_actual_es_mensual": es_tabla_actual_mensual(config),
        "campo_periodo_actual": campo_periodo,
        "filtro_periodo_aplicado": "no",
        "total_claves_archivo": len([clave for clave, incompleta in zip(claves_archivo, claves_incompletas) if not incompleta]),
        "total_claves_destino_leidas": 0,
        "total_coincidencias": 0,
        "query_destino_debug": "No aplica para reemplazo de cartera activa del mes.",
    }

    return {
        "resumen": resumen,
        "estados_carga": estados,
        "filas_duplicadas_preview": duplicados_preview,
        "alertas": alertas,
        "diagnostico_cruce": diagnostico,
    }


def obtener_claves_existentes_destino(
    tabla_destino: str,
    claves_destino: List[str],
    campo_periodo: Optional[str],
    periodo: str,
    config: Dict[str, Any],
    mapa_destino: Dict[str, str],
) -> Dict[str, Any]:
    database, schema, table_name = parsear_nombre_tabla(tabla_destino)
    tabla_sql = f"[{database}].[{schema}].[{table_name}]"
    columnas_sql = ", ".join(quote_identificador(columna) for columna in claves_destino)
    condiciones = []
    params: Dict[str, Any] = {}
    campo_periodo_destino = None
    if campo_periodo:
        periodo_norm = normalizar_columna(campo_periodo)
        campo_periodo_destino = next(
            (col for col in claves_destino if normalizar_columna(col) == periodo_norm),
            mapa_destino.get(periodo_norm),
        )

    filtro_periodo_aplicado = False
    if campo_periodo_destino and not es_tabla_actual_mensual(config):
        filtro_periodo_aplicado = True
        if es_periodo_fecha(config):
            condiciones.append(f"CAST({quote_identificador(campo_periodo_destino)} AS DATE) = :periodo_fecha")
            params["periodo_fecha"] = valor_periodo_configurado(config, periodo)
        else:
            condiciones.append(f"CAST({quote_identificador(campo_periodo_destino)} AS VARCHAR(30)) = :periodo")
            params["periodo"] = periodo

    where = f" WHERE {' AND '.join(condiciones)}" if condiciones else ""
    query = text(f"""
        SELECT {columnas_sql}
        FROM {tabla_sql} WITH(NOLOCK)
        {where}
    """)
    query_debug = f"SELECT {columnas_sql} FROM {tabla_sql} WITH(NOLOCK){where}"

    with engine_siscob.connect() as conn:
        rows = conn.execute(query, params).mappings().all()

    existentes = set()
    campo_periodo_norm = normalizar_columna(campo_periodo) if campo_periodo else ""
    for row in rows:
        existentes.add(tuple(
            normalizar_valor_cruce(
                row.get(col),
                es_fecha=normalizar_columna(col) == campo_periodo_norm and es_periodo_fecha(config),
            )
            for col in claves_destino
        ))
    return {
        "claves": existentes,
        "filtro_periodo_aplicado": filtro_periodo_aplicado,
        "query_debug": query_debug,
    }


def contar_tabla(tabla: str) -> int:
    query = text(f"SELECT COUNT(1) AS total FROM {nombre_tabla_sql(tabla)} WITH(NOLOCK)")
    with engine_siscob.connect() as conn:
        return int(conn.execute(query).scalar() or 0)


def contar_periodo_historico(
    tabla_historica: str,
    campo_periodo: str,
    periodo: str,
    config: Dict[str, Any],
) -> int:
    where_periodo, params = condicion_periodo_historico(campo_periodo, periodo, config)
    query = text(f"""
        SELECT COUNT(1) AS total
        FROM {nombre_tabla_sql(tabla_historica)} WITH(NOLOCK)
        WHERE {where_periodo}
    """)
    with engine_siscob.connect() as conn:
        return int(conn.execute(query, params).scalar() or 0)


def contar_cierre_control_previo(id_config: int, periodo: str) -> int:
    asegurar_tabla_cierres_historicos()
    query = text("""
        SELECT COUNT(1)
        FROM CobAuto.dbo.importacion_cierres_historicos WITH(NOLOCK)
        WHERE id_config = :id_config
          AND periodo = :periodo
          AND estado = 'CERRADO'
    """)
    with engine_siscob.connect() as conn:
        return int(conn.execute(query, {"id_config": id_config, "periodo": periodo}).scalar() or 0)


def campo_periodo_historico_efectivo(
    config: Dict[str, Any],
    tabla_historica: str,
    campo_configurado: str,
) -> str:
    texto = normalizar_columna(
        f"{config.get('cartera') or ''} {config.get('producto') or ''} "
        f"{config.get('tabla_destino') or ''} {tabla_historica or ''}"
    )
    if "compartamos" in texto and "vigente" in texto and "grupal" in texto:
        return "Mes Asignacion"
    return campo_configurado


def permite_historico_sin_periodo(config: Dict[str, Any], tabla_historica: str) -> bool:
    texto = normalizar_columna(
        f"{config.get('cartera') or ''} {config.get('producto') or ''} "
        f"{config.get('tabla_destino') or ''} {tabla_historica or ''}"
    )
    return "compartamos" in texto and "vigente" in texto and "grupal" in texto


def condicion_periodo_historico(
    campo_periodo: str,
    periodo: str,
    config: Dict[str, Any],
) -> Tuple[str, Dict[str, Any]]:
    campo_sql = quote_identificador(campo_periodo)
    if es_periodo_fecha(config):
        return f"CAST({campo_sql} AS DATE) = :periodo_historico_fecha", {
            "periodo_historico_fecha": valor_periodo_configurado(config, periodo)
        }
    return f"CAST({campo_sql} AS VARCHAR(30)) = :periodo_historico", {
        "periodo_historico": periodo
    }


def preparar_columnas_cierre(
    columnas_origen: List[Dict[str, Any]],
    columnas_historico: List[Dict[str, Any]],
    campo_periodo: str,
    config: Dict[str, Any],
    periodo: str,
) -> Tuple[List[str], List[str], Dict[str, Any], List[str]]:
    origen_por_norm = {
        normalizar_columna(col["column_name"]): col["column_name"]
        for col in columnas_origen
    }
    campo_periodo_norm = normalizar_columna(campo_periodo)
    insert_columns: List[str] = []
    select_expressions: List[str] = []
    faltantes_obligatorias: List[str] = []
    params: Dict[str, Any] = {
        "periodo_insert": valor_periodo_configurado(config, periodo)
    }

    for col in columnas_historico:
        nombre_hist = col["column_name"]
        if col.get("is_identity"):
            continue

        norm = normalizar_columna(nombre_hist)
        if campo_periodo_norm and norm == campo_periodo_norm:
            insert_columns.append(quote_identificador(nombre_hist))
            select_expressions.append(":periodo_insert")
            continue

        if norm in origen_por_norm:
            insert_columns.append(quote_identificador(nombre_hist))
            select_expressions.append(expresion_select_cierre(origen_por_norm[norm], col))
            continue

        if not es_columna_nullable(col) and not col.get("has_default"):
            faltantes_obligatorias.append(nombre_hist)

    return insert_columns, select_expressions, params, faltantes_obligatorias


def expresion_select_cierre(columna_origen: str, columna_historica: Dict[str, Any]) -> str:
    origen_sql = quote_identificador(columna_origen)
    tipo_destino = str(columna_historica.get("data_type") or "").lower()

    if tipo_destino in ("date", "datetime", "datetime2", "smalldatetime"):
        texto_origen = f"NULLIF(LTRIM(RTRIM(CONVERT(VARCHAR(50), {origen_sql}))), '')"
        return (
            "COALESCE("
            f"TRY_CONVERT({tipo_destino}, {origen_sql}), "
            f"TRY_CONVERT({tipo_destino}, {texto_origen}, 103), "
            f"TRY_CONVERT({tipo_destino}, {texto_origen}, 120), "
            f"TRY_CONVERT({tipo_destino}, {texto_origen}, 23), "
            f"TRY_CONVERT({tipo_destino}, {texto_origen}, 112)"
            ")"
        )

    return origen_sql


def es_columna_nullable(columna: Dict[str, Any]) -> bool:
    value = columna.get("is_nullable", True)
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return int(value) == 1
    return str(value or "").upper() in ("YES", "TRUE", "1", "SI", "SÍ")


def nombre_tabla_sql(tabla: str) -> str:
    database, schema, table_name = parsear_nombre_tabla(tabla)
    return f"[{database}].[{schema}].[{table_name}]"


def asegurar_tabla_cierres_historicos() -> None:
    ddl = text("""
        IF OBJECT_ID('CobAuto.dbo.importacion_cierres_historicos', 'U') IS NULL
        BEGIN
            CREATE TABLE CobAuto.dbo.importacion_cierres_historicos (
                id_cierre INT IDENTITY(1,1) PRIMARY KEY,
                id_config INT NOT NULL,
                cartera VARCHAR(100) NOT NULL,
                producto VARCHAR(100) NULL,
                periodo VARCHAR(6) NOT NULL,
                tabla_origen VARCHAR(300) NOT NULL,
                tabla_historica VARCHAR(300) NOT NULL,
                total_origen INT DEFAULT 0,
                total_insertado INT DEFAULT 0,
                total_existente_previo INT DEFAULT 0,
                usuario VARCHAR(50) NULL,
                estado VARCHAR(50) DEFAULT 'PENDIENTE',
                observacion VARCHAR(MAX) NULL,
                fecha_inicio DATETIME DEFAULT GETDATE(),
                fecha_fin DATETIME NULL
            )
        END
    """)
    with engine_siscob.begin() as conn:
        conn.execute(ddl)


def registrar_cierre_fallido(
    id_config: int,
    config: Dict[str, Any],
    periodo: str,
    tabla_origen: str,
    tabla_historica: str,
    total_origen: int,
    total_existente: int,
    usuario: str,
    observacion: str,
    cierre_id: Optional[int],
) -> None:
    asegurar_tabla_cierres_historicos()
    with engine_siscob.begin() as conn:
        if cierre_id:
            conn.execute(text("""
                UPDATE CobAuto.dbo.importacion_cierres_historicos
                SET estado = 'ERROR',
                    observacion = :observacion,
                    fecha_fin = GETDATE()
                WHERE id_cierre = :id_cierre
            """), {"id_cierre": cierre_id, "observacion": observacion[:4000]})
        else:
            conn.execute(text("""
                INSERT INTO CobAuto.dbo.importacion_cierres_historicos
                    (id_config, cartera, producto, periodo, tabla_origen, tabla_historica,
                     total_origen, total_existente_previo, usuario, estado, observacion, fecha_fin)
                VALUES
                    (:id_config, :cartera, :producto, :periodo, :tabla_origen, :tabla_historica,
                     :total_origen, :total_existente_previo, :usuario, 'ERROR', :observacion, GETDATE())
            """), {
                "id_config": id_config,
                "cartera": config.get("cartera") or "SIN_CARTERA",
                "producto": config.get("producto"),
                "periodo": periodo,
                "tabla_origen": tabla_origen,
                "tabla_historica": tabla_historica,
                "total_origen": total_origen,
                "total_existente_previo": total_existente,
                "usuario": usuario,
                "observacion": observacion[:4000],
            })


def normalizar_tipo_carga_confirmacion(tipo_carga: str) -> str:
    texto = normalizar_columna(tipo_carga).upper()
    if texto in (
        "CARGA_INICIAL_MENSUAL",
        "CARGA_INICIAL",
        "REEMPLAZAR_CARTERA_ACTIVA_MES",
        "REEMPLAZAR_CARTERA_ACTIVA_DEL_MES",
    ):
        return "CARGA_INICIAL_MENSUAL"
    if texto in (
        "AGREGAR_ACTUALIZAR",
        "AGREGAR_Y_ACTUALIZAR",
        "AGREGAR_MAS_ACTUALIZAR",
        "AGREGAR_ACTUALIZACION",
    ):
        return "AGREGAR_ACTUALIZAR"
    if texto.replace("_", " ") == "AGREGAR ACTUALIZAR":
        return "AGREGAR_ACTUALIZAR"
    return str(tipo_carga or "").upper().strip()


def leer_dataframe_importacion(
    contenido: bytes,
    archivo_nombre: str,
    hoja: Optional[str] = None,
) -> Tuple[pd.DataFrame, str]:
    excel = abrir_excel(contenido, archivo_nombre)
    hojas_disponibles = list(excel.sheet_names)
    hoja_usada = hoja if hoja in hojas_disponibles else hojas_disponibles[0]
    df = pd.read_excel(excel, sheet_name=hoja_usada, dtype=str)
    df = df.where(pd.notna(df), None)
    df, _ = limpiar_filas_tecnicas_importacion(df)
    return df, hoja_usada


def limpiar_filas_tecnicas_importacion(df: pd.DataFrame) -> Tuple[pd.DataFrame, int]:
    if df.empty:
        return df, 0

    filas_tecnicas = df.apply(es_fila_tecnica_importacion, axis=1)
    total_ignoradas = int(filas_tecnicas.sum())
    if total_ignoradas == 0:
        return df, 0

    return df.loc[~filas_tecnicas].reset_index(drop=True), total_ignoradas


def es_fila_tecnica_importacion(row: pd.Series) -> bool:
    valores = []
    tiene_nn = False

    for value in row.tolist():
        if value is None or pd.isna(value):
            continue

        texto = str(value).replace("\u00a0", " ").strip()
        if not texto:
            continue

        texto_normalizado = texto.upper()
        if texto_normalizado == "NN":
            tiene_nn = True

        valores.append(texto_normalizado)

    if not valores:
        return True

    return tiene_nn and all(valor in VALORES_FILA_TECNICA for valor in valores)


def asegurar_tablas_carga_importacion() -> None:
    ddl = text("""
        IF OBJECT_ID('CobAuto.dbo.importacion_lotes', 'U') IS NULL
        BEGIN
            CREATE TABLE CobAuto.dbo.importacion_lotes (
                id_lote INT IDENTITY(1,1) PRIMARY KEY,
                id_config INT NOT NULL,
                cartera VARCHAR(100) NULL,
                producto VARCHAR(100) NULL,
                periodo VARCHAR(6) NOT NULL,
                tipo_proceso VARCHAR(80) NOT NULL,
                archivo_nombre VARCHAR(255) NULL,
                usuario VARCHAR(50) NULL,
                total_filas INT DEFAULT 0,
                insertados INT DEFAULT 0,
                actualizados INT DEFAULT 0,
                rechazados INT DEFAULT 0,
                estado VARCHAR(50) DEFAULT 'EN_PROCESO',
                observacion VARCHAR(MAX) NULL,
                fecha_inicio DATETIME DEFAULT GETDATE(),
                fecha_fin DATETIME NULL
            )
        END

        IF OBJECT_ID('CobAuto.dbo.importacion_errores', 'U') IS NULL
        BEGIN
            CREATE TABLE CobAuto.dbo.importacion_errores (
                id_error INT IDENTITY(1,1) PRIMARY KEY,
                id_lote INT NOT NULL,
                fila_excel INT NULL,
                columna VARCHAR(255) NULL,
                valor VARCHAR(MAX) NULL,
                error VARCHAR(500) NULL,
                fecha_registro DATETIME DEFAULT GETDATE()
            )
        END

        IF COL_LENGTH('CobAuto.dbo.importacion_lotes', 'usuario') IS NULL
            ALTER TABLE CobAuto.dbo.importacion_lotes ADD usuario VARCHAR(50) NULL

        IF COL_LENGTH('CobAuto.dbo.importacion_lotes', 'observacion') IS NULL
            ALTER TABLE CobAuto.dbo.importacion_lotes ADD observacion VARCHAR(MAX) NULL

        IF COL_LENGTH('CobAuto.dbo.importacion_lotes', 'fecha_fin') IS NULL
            ALTER TABLE CobAuto.dbo.importacion_lotes ADD fecha_fin DATETIME NULL
    """)
    with engine_siscob.begin() as conn:
        conn.execute(ddl)


def crear_lote_importacion(
    conn,
    config: Dict[str, Any],
    periodo: str,
    tipo_proceso: str,
    archivo_nombre: str,
    usuario: str,
    total_filas: int,
) -> int:
    return int(conn.execute(text("""
        INSERT INTO CobAuto.dbo.importacion_lotes
            (id_config, cartera, producto, periodo, tipo_proceso, archivo_nombre,
             usuario, total_filas, insertados, actualizados, rechazados, estado,
             observacion)
        OUTPUT INSERTED.id_lote
        VALUES
            (:id_config, :cartera, :producto, :periodo, :tipo_proceso, :archivo_nombre,
             :usuario, :total_filas, 0, 0, 0, 'EN_PROCESO', :observacion)
    """), {
        "id_config": config.get("id_config"),
        "cartera": config.get("cartera"),
        "producto": config.get("producto"),
        "periodo": periodo,
        "tipo_proceso": tipo_proceso,
        "archivo_nombre": archivo_nombre[:255],
        "usuario": usuario,
        "total_filas": int(total_filas),
        "observacion": "Carga iniciada.",
    }).scalar())


def actualizar_lote_importacion(
    conn,
    id_lote: int,
    estado: str,
    insertados: int,
    actualizados: int,
    rechazados: int,
    observacion: str,
) -> None:
    conn.execute(text("""
        UPDATE CobAuto.dbo.importacion_lotes
        SET insertados = :insertados,
            actualizados = :actualizados,
            rechazados = :rechazados,
            estado = :estado,
            observacion = :observacion,
            fecha_fin = GETDATE()
        WHERE id_lote = :id_lote
    """), {
        "id_lote": id_lote,
        "estado": estado,
        "insertados": insertados,
        "actualizados": actualizados,
        "rechazados": rechazados,
        "observacion": observacion[:4000],
    })


def nombre_staging_importacion(id_config: int) -> str:
    return f"CobAuto.dbo.importacion_staging_{int(id_config)}_fast"


def asegurar_staging_importacion(
    conn,
    id_config: int,
    columnas: List[str],
    columnas_destino_por_nombre: Dict[str, Dict[str, Any]],
) -> str:
    tabla = nombre_staging_importacion(id_config)
    tabla_sql = nombre_tabla_sql(tabla)
    tabla_literal = tabla.replace("'", "''")
    conn.execute(text(f"""
        IF OBJECT_ID('{tabla_literal}', 'U') IS NULL
        BEGIN
            CREATE TABLE {tabla_sql} (
                [__id_lote] INT NOT NULL,
                [__fila_excel] INT NULL,
                [__estado_fila] VARCHAR(30) NULL
            )
        END
    """))

    for columna in columnas:
        columna_literal = str(columna).replace("'", "''")
        tipo_sql = tipo_sql_staging_importacion(columnas_destino_por_nombre.get(columna, {}))
        conn.execute(text(f"""
            IF COL_LENGTH('{tabla_literal}', '{columna_literal}') IS NULL
            BEGIN
                ALTER TABLE {tabla_sql}
                ADD {quote_identificador(columna)} {tipo_sql} NULL
            END
        """))

    return tabla_sql


def tipo_sql_staging_importacion(columna: Dict[str, Any]) -> str:
    tipo = str(columna.get("data_type") or "").lower()
    max_length = int(columna.get("max_length") or 0)
    precision = int(columna.get("precision") or 0)
    scale = int(columna.get("scale") or 0)

    if tipo in ("varchar", "char", "varbinary", "binary"):
        if max_length == -1:
            return f"{tipo}(MAX)"
        return f"{tipo}({max(max_length, 1)})"
    if tipo in ("nvarchar", "nchar"):
        if max_length == -1:
            return f"{tipo}(MAX)"
        return f"{tipo}({max(max_length // 2, 1)})"
    if tipo in ("decimal", "numeric"):
        return f"{tipo}({precision or 18},{scale})"
    if tipo in (
        "int", "bigint", "smallint", "tinyint", "bit", "float", "real",
        "money", "smallmoney", "date", "datetime", "datetime2", "smalldatetime",
        "time", "uniqueidentifier",
    ):
        return tipo
    return "NVARCHAR(4000)"


def insertar_filas_staging_importacion(
    conn,
    staging_sql: str,
    id_lote: int,
    filas: List[Dict[str, Any]],
    columnas: List[str],
) -> None:
    if not filas:
        return

    columnas_sql = ["[__id_lote]", "[__fila_excel]", "[__estado_fila]"] + [
        quote_identificador(columna) for columna in columnas
    ]
    placeholders = ", ".join("?" for _ in columnas_sql)
    insert_sql = f"""
        INSERT INTO {staging_sql} ({", ".join(columnas_sql)})
        VALUES ({placeholders})
    """
    payload = []
    for fila in filas:
        valores = fila["valores"]
        payload.append((
            id_lote,
            fila["fila_excel"],
            "VALIDO",
            *(valores.get(columna) for columna in columnas),
        ))

    raw_connection = getattr(conn.connection, "driver_connection", None)
    if raw_connection is None:
        raw_connection = conn.connection.connection

    cursor = raw_connection.cursor()
    try:
        try:
            cursor.fast_executemany = True
        except Exception:
            pass
        cursor.executemany(insert_sql, payload)
    finally:
        cursor.close()


def marcar_lote_error(id_lote: int, observacion: str) -> None:
    with engine_siscob.begin() as conn:
        conn.execute(text("""
            UPDATE CobAuto.dbo.importacion_lotes
            SET estado = 'ERROR',
                observacion = :observacion,
                fecha_fin = GETDATE()
            WHERE id_lote = :id_lote
        """), {
            "id_lote": id_lote,
            "observacion": str(observacion or "")[:4000],
        })


def registrar_error_importacion(
    conn,
    id_lote: int,
    fila_excel: int,
    columna: str,
    valor: Any,
    error: str,
) -> None:
    conn.execute(text("""
        INSERT INTO CobAuto.dbo.importacion_errores
            (id_lote, fila_excel, columna, valor, error)
        VALUES
            (:id_lote, :fila_excel, :columna, :valor, :error)
    """), {
        "id_lote": id_lote,
        "fila_excel": fila_excel,
        "columna": str(columna or "-")[:255],
        "valor": None if valor is None else str(valor)[:4000],
        "error": str(error or "-")[:500],
    })


def agregar_motivo_rechazo(
    motivos: List[Dict[str, Any]],
    fila_excel: int,
    columna: str,
    error: str,
) -> None:
    if len(motivos) >= 10:
        return
    motivos.append({
        "fila_excel": fila_excel,
        "columna": columna,
        "error": error,
    })


def valor_celda_importacion(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if pd.isna(value):
        return None
    if isinstance(value, pd.Timestamp):
        return value.to_pydatetime()
    texto = str(value).replace("\u00a0", "").strip()
    if texto.lower() in ("", "nan", "none", "nat"):
        return None
    if re.fullmatch(r"\d+\.0+", texto):
        return texto.split(".", 1)[0]
    return texto


def valores_insert_importacion(
    row: pd.Series,
    columnas_archivo_validas: List[Tuple[str, str, Dict[str, Any]]],
    columnas_generadas: List[str],
    valor_periodo: Any,
) -> Dict[str, Any]:
    valores: Dict[str, Any] = {}
    for columna_archivo, columna_destino, _ in columnas_archivo_validas:
        valores[columna_destino] = valor_celda_importacion(row.get(columna_archivo))
    for columna in columnas_generadas:
        valores[columna] = valor_periodo
    return valores


def valores_update_importacion(
    row: pd.Series,
    columnas_archivo_validas: List[Tuple[str, str, Dict[str, Any]]],
    columnas_generadas: List[str],
    valor_periodo: Any,
    claves_destino: List[str],
) -> Dict[str, Any]:
    claves_norm = {normalizar_columna(col) for col in claves_destino}
    valores: Dict[str, Any] = {}
    for columna_archivo, columna_destino, _ in columnas_archivo_validas:
        if normalizar_columna(columna_destino) in claves_norm:
            continue
        valor = valor_celda_importacion(row.get(columna_archivo))
        if valor is not None:
            valores[columna_destino] = valor
    for columna in columnas_generadas:
        if normalizar_columna(columna) not in claves_norm:
            valores[columna] = valor_periodo
    return valores


def construir_where_clave_importacion(
    row: pd.Series,
    claves_destino: List[str],
    mapa_archivo: Dict[str, str],
    config: Dict[str, Any],
    periodo: str,
    columnas_destino_por_nombre: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Tuple[str, Dict[str, Any]]:
    campo_periodo = config.get("campo_periodo_actual")
    campo_periodo_norm = normalizar_columna(campo_periodo) if campo_periodo else ""
    valor_periodo = valor_periodo_configurado(config, periodo)
    partes = []
    params: Dict[str, Any] = {}
    for indice, clave_destino in enumerate(claves_destino):
        clave_norm = normalizar_columna(clave_destino)
        param = f"k{indice}"
        if clave_norm in mapa_archivo:
            valor = normalizar_valor_cruce(
                row.get(mapa_archivo[clave_norm]),
                es_fecha=clave_norm == campo_periodo_norm and es_periodo_fecha(config),
            )
        elif campo_periodo_norm and clave_norm == campo_periodo_norm:
            valor = valor_periodo
        else:
            valor = None

        if campo_periodo_norm and clave_norm == campo_periodo_norm and es_periodo_fecha(config):
            partes.append(f"CAST({quote_identificador(clave_destino)} AS DATE) = :{param}")
            params[param] = valor_periodo
        else:
            tipo_columna = ""
            if columnas_destino_por_nombre and clave_destino in columnas_destino_por_nombre:
                tipo_columna = str(columnas_destino_por_nombre[clave_destino].get("data_type") or "").lower()
            expresion = expresion_clave_normalizada_sql(clave_destino, tipo_columna)
            if clave_norm in ("cod_pre", "codcli", "cod_cli", "operacion", "num_operacion"):
                partes.append(
                    f"({expresion} = :{param} OR TRY_CONVERT(DECIMAL(38, 0), {expresion}) = TRY_CONVERT(DECIMAL(38, 0), :{param}))"
                )
            else:
                partes.append(
                    f"{expresion} = :{param}"
                )
            params[param] = normalizar_valor_cruce_parametro_sql(valor, tipo_columna)
    return " AND ".join(partes), params


def expresion_clave_normalizada_sql(columna: str, tipo_columna: str = "") -> str:
    if tipo_columna in ("int", "bigint", "smallint", "tinyint", "numeric", "decimal", "float", "real", "money", "smallmoney"):
        return (
            f"REPLACE(LTRIM(RTRIM(CONVERT(VARCHAR(100), "
            f"CONVERT(DECIMAL(38, 0), {quote_identificador(columna)})))), CHAR(160), '')"
        )
    return f"REPLACE(LTRIM(RTRIM(CAST({quote_identificador(columna)} AS VARCHAR(100)))), CHAR(160), '')"


def normalizar_valor_cruce_parametro_sql(value: Any, tipo_columna: str = "") -> Any:
    texto = normalizar_valor_cruce(value)
    return texto


def clave_fila_texto(
    row: pd.Series,
    claves: List[str],
    mapa_archivo: Dict[str, str],
    config: Dict[str, Any],
    periodo: str,
) -> str:
    campo_periodo = config.get("campo_periodo_actual")
    campo_periodo_norm = normalizar_columna(campo_periodo) if campo_periodo else ""
    partes = []
    for clave in claves:
        clave_norm = normalizar_columna(clave)
        if clave_norm in mapa_archivo:
            valor = normalizar_valor_cruce(row.get(mapa_archivo[clave_norm]))
        elif campo_periodo_norm and clave_norm == campo_periodo_norm:
            valor = valor_periodo_configurado(config, periodo)
        else:
            valor = None
        partes.append(f"{clave}={valor or ''}")
    return " | ".join(partes)


def resumen_impacto(estados: List[str]) -> Dict[str, int]:
    nuevos = estados.count("NUEVO")
    existentes = estados.count("EXISTENTE")
    duplicados = estados.count("DUPLICADO_ARCHIVO")
    incompletas = estados.count("CLAVE_INCOMPLETA")
    return {
        "registros_archivo": len(estados),
        "registros_nuevos": nuevos,
        "registros_existentes": existentes,
        "duplicados_archivo": duplicados,
        "clave_incompleta": incompletas,
        "registros_a_insertar": nuevos,
        "registros_a_actualizar": existentes,
        "registros_actuales_periodo": existentes,
    }


def alertas_impacto(tipo_carga: str, resumen: Dict[str, int]) -> List[Dict[str, str]]:
    alertas: List[Dict[str, str]] = []
    tipo = str(tipo_carga or "").upper()
    existentes = resumen.get("registros_existentes", 0)

    if tipo == "CARGA_INICIAL_MENSUAL" and existentes > 0:
        alertas.append({
            "tipo": "advertencia",
            "mensaje": "Ya existen registros en la tabla destino para estas claves activas.",
        })

    if tipo == "REEMPLAZAR_ACTIVA" and existentes > 0:
        alertas.append({
            "tipo": "info",
            "mensaje": f"{existentes} registros actuales serian reemplazados en una fase posterior.",
        })

    if resumen.get("duplicados_archivo", 0) > 0:
        alertas.append({
            "tipo": "advertencia",
            "mensaje": f"{resumen['duplicados_archivo']} filas tienen clave duplicada dentro del archivo.",
        })

    if resumen.get("clave_incompleta", 0) > 0:
        alertas.append({
            "tipo": "error",
            "mensaje": f"{resumen['clave_incompleta']} filas tienen clave de cruce incompleta.",
        })

    return alertas


def construir_preview_duplicados(
    df: pd.DataFrame,
    estados: List[str],
    claves_destino: List[str],
    claves_archivo: List[Tuple[Any, ...]],
) -> List[Dict[str, Any]]:
    preview = []
    for idx, estado in enumerate(estados):
        if estado != "DUPLICADO_ARCHIVO":
            continue
        item = {
            "fila": idx + 2,
            "estado_carga": estado,
            "clave": " | ".join(f"{col}={valor}" for col, valor in zip(claves_destino, claves_archivo[idx])),
        }
        preview.append(item)
        if len(preview) >= 20:
            break
    return preview


def valor_periodo_configurado(config: Dict[str, Any], periodo: str) -> Any:
    if es_periodo_fecha(config):
        return date(int(periodo[:4]), int(periodo[4:6]), 1)
    return periodo


def es_tabla_actual_mensual(config: Dict[str, Any]) -> bool:
    value = config.get("tabla_actual_es_mensual", 1)
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return int(value) == 1
    return str(value or "1").strip().lower() in ("1", "true", "si", "sí", "yes")


def es_periodo_fecha(config: Dict[str, Any]) -> bool:
    tipo = str(config.get("tipo_periodo") or "").upper()
    formato = str(config.get("formato_periodo") or "").upper()
    return tipo == "DATE" and formato == "YYYY-MM-01"


def normalizar_valor_cruce(value: Any, es_fecha: bool = False) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if pd.isna(value):
        return None
    if es_fecha:
        fecha = pd.to_datetime(value, errors="coerce")
        if pd.isna(fecha):
            return None
        return fecha.date().isoformat()
    texto = str(value).replace("\u00a0", "").strip()
    texto = re.sub(r"\s+", " ", texto)
    if re.fullmatch(r"\d+\.0+", texto):
        texto = texto.split(".", 1)[0]
    if texto.lower() in ("nan", "none", "nat"):
        return None
    return texto


def clave_debug(columnas: List[str], clave: Tuple[Any, ...]) -> Dict[str, Any]:
    return {columna: valor for columna, valor in zip(columnas, clave)}


def quote_identificador(columna: str) -> str:
    texto = str(columna or "").strip()
    if not texto or any(char in texto for char in ("\x00", "\r", "\n", ";")):
        raise ValueError(f"Nombre de columna no valido para consulta: {columna}")
    return f"[{texto.replace(']', ']]')}]"


def asegurar_configuracion_importacion() -> None:
    ddl = text("""
        IF COL_LENGTH('CobAuto.dbo.importacion_config_cartera', 'tabla_actual_es_mensual') IS NULL
        BEGIN
            ALTER TABLE CobAuto.dbo.importacion_config_cartera
            ADD tabla_actual_es_mensual BIT NOT NULL
                CONSTRAINT DF_importacion_config_cartera_tabla_actual_es_mensual DEFAULT(1)
        END
    """)
    update_mibanco = text("""
        UPDATE CobAuto.dbo.importacion_config_cartera
        SET clave_cruce = 'NRO_DOC,COD_PRE',
            tabla_actual_es_mensual = 1
        WHERE ISNULL(activo, 1) = 1
          AND UPPER(LTRIM(RTRIM(ISNULL(cartera, '')))) LIKE '%MIBANCO%'
          AND (
                UPPER(LTRIM(RTRIM(ISNULL(producto, '')))) = 'GENERAL'
                OR UPPER(LTRIM(RTRIM(ISNULL(producto, '')))) LIKE '%GENERAL%'
              )
    """)
    update_compartamos_castigo_individual = text("""
        UPDATE CobAuto.dbo.importacion_config_cartera
        SET tabla_historica = 'Compartamos_Castigo_Cobranzas.dbo.compartamos_castigo'
        WHERE ISNULL(activo, 1) = 1
          AND UPPER(LTRIM(RTRIM(ISNULL(cartera, '')))) LIKE '%COMPARTAMOS%'
          AND (
                UPPER(LTRIM(RTRIM(ISNULL(producto, '')))) LIKE '%CASTIGO INDIVIDUAL%'
                OR (
                    UPPER(LTRIM(RTRIM(ISNULL(producto, '')))) LIKE '%CASTIGO%'
                    AND UPPER(LTRIM(RTRIM(ISNULL(producto, '')))) NOT LIKE '%GRUPAL%'
                    AND UPPER(LTRIM(RTRIM(ISNULL(tabla_destino, '')))) NOT LIKE '%GRUPAL%'
                )
              )
    """)
    update_compartamos_castigo_grupal = text("""
        UPDATE CobAuto.dbo.importacion_config_cartera
        SET tabla_historica = 'Compartamos_Castigo_Cobranzas.dbo.HIST_GRUPAL_CASTIGO'
        WHERE ISNULL(activo, 1) = 1
          AND UPPER(LTRIM(RTRIM(ISNULL(cartera, '')))) LIKE '%COMPARTAMOS%'
          AND (
                UPPER(LTRIM(RTRIM(ISNULL(producto, '')))) LIKE '%CASTIGO GRUPAL%'
                OR UPPER(LTRIM(RTRIM(ISNULL(tabla_destino, '')))) LIKE '%GRUPAL_CASTIGO%'
              )
    """)
    update_compartamos_vigente_grupal = text("""
        UPDATE CobAuto.dbo.importacion_config_cartera
        SET tabla_historica = 'Compartamos_Vigente_Cobranzas.dbo.HIST_COMPARTAMOS_GRUPAL',
            campo_periodo_historico = 'Mes Asignacion',
            tipo_estructura_historico = 'MAPEO_HISTORICO'
        WHERE ISNULL(activo, 1) = 1
          AND UPPER(LTRIM(RTRIM(ISNULL(cartera, '')))) LIKE '%COMPARTAMOS%'
          AND (
                UPPER(LTRIM(RTRIM(ISNULL(producto, '')))) LIKE '%VIGENTE GRUPAL%'
                OR UPPER(LTRIM(RTRIM(ISNULL(tabla_destino, '')))) LIKE '%COMPARTAMOS_GRUPAL%'
              )
    """)
    with engine_siscob.begin() as conn:
        conn.execute(ddl)
        conn.execute(update_mibanco)
        conn.execute(update_compartamos_castigo_individual)
        conn.execute(update_compartamos_castigo_grupal)
        conn.execute(update_compartamos_vigente_grupal)


def parsear_nombre_tabla(tabla: str) -> Tuple[str, str, str]:
    limpio = tabla.replace("[", "").replace("]", "").strip()
    partes = [parte.strip() for parte in limpio.split(".") if parte.strip()]
    if len(partes) == 1:
        database, schema, table_name = "CobAuto", "dbo", partes[0]
    elif len(partes) == 2:
        database, schema, table_name = "CobAuto", partes[0], partes[1]
    elif len(partes) == 3:
        database, schema, table_name = partes
    else:
        raise ValueError(f"Nombre de tabla destino no valido: {tabla}")

    for nombre in (database, schema, table_name):
        if not re.fullmatch(r"[A-Za-z0-9_]+", nombre):
            raise ValueError(f"Nombre de tabla destino no valido: {tabla}")

    return database, schema, table_name


def abrir_excel(contenido: bytes, archivo_nombre: str) -> pd.ExcelFile:
    extension = archivo_nombre.lower().rsplit(".", 1)[-1] if "." in archivo_nombre else ""
    stream = BytesIO(contenido)
    if extension == "xls":
        return pd.ExcelFile(stream, engine="xlrd")
    return pd.ExcelFile(stream, engine="openpyxl")


def validar_periodo(periodo: str) -> None:
    if not periodo or not re.fullmatch(r"\d{6}", str(periodo).strip()):
        raise ValueError("Periodo obligatorio con formato YYYYMM.")


def normalizar_columna(value: Any) -> str:
    texto = str(value or "").strip().lower()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(char for char in texto if not unicodedata.combining(char))
    texto = re.sub(r"[^a-z0-9]+", "_", texto)
    return re.sub(r"_+", "_", texto).strip("_")


def mapa_normalizado(columnas: List[str]) -> Dict[str, str]:
    mapa: Dict[str, str] = {}
    for columna in columnas:
        normalizada = normalizar_columna(columna)
        if normalizada and normalizada not in mapa:
            mapa[normalizada] = columna
    return mapa


def parsear_claves(clave_cruce: Any) -> List[str]:
    if not clave_cruce:
        return []
    return [
        item.strip()
        for item in re.split(r"[,;|]", str(clave_cruce))
        if item.strip()
    ]


def construir_alertas(
    config: Dict[str, Any],
    columnas_nuevas: List[str],
    columnas_faltantes: List[str],
    columnas_clave_faltantes: List[str],
    columnas_generadas: List[Dict[str, str]],
    mapa_destino: Dict[str, str],
) -> List[Dict[str, str]]:
    alertas: List[Dict[str, str]] = []

    if columnas_clave_faltantes:
        alertas.append({
            "tipo": "error",
            "mensaje": "Faltan columnas clave en el archivo: " + ", ".join(columnas_clave_faltantes),
        })

    if columnas_faltantes:
        faltantes_meta = [col for col in columnas_faltantes if es_columna_meta(col)]
        faltantes_reales = [col for col in columnas_faltantes if not es_columna_meta(col)]
        if faltantes_meta:
            alertas.append({
                "tipo": "advertencia",
                "mensaje": "Columnas de meta no vienen en el archivo; se actualizaran desde el modulo de metas: "
                + ", ".join(faltantes_meta),
            })
        if faltantes_reales:
            alertas.append({
                "tipo": "advertencia",
                "mensaje": f"{len(faltantes_reales)} columnas de la tabla destino no vienen en el archivo.",
            })

    if columnas_generadas:
        alertas.append({
            "tipo": "info",
            "mensaje": "Columnas que se generaran desde pantalla: "
            + ", ".join(item["columna"] for item in columnas_generadas),
        })

    if columnas_nuevas:
        alertas.append({
            "tipo": "info",
            "mensaje": f"{len(columnas_nuevas)} columnas nuevas fueron detectadas en el archivo.",
        })

    campo_periodo = config.get("campo_periodo_actual")
    if campo_periodo and normalizar_columna(campo_periodo) not in mapa_destino:
        alertas.append({
            "tipo": "advertencia",
            "mensaje": f"El campo_periodo_actual '{campo_periodo}' no existe en la tabla destino.",
        })

    tipo_periodo = str(config.get("tipo_periodo") or "").upper()
    formato_periodo = str(config.get("formato_periodo") or "").upper()
    if tipo_periodo == "DATE" and formato_periodo == "YYYY-MM-01":
        alertas.append({
            "tipo": "info",
            "mensaje": "El periodo se convertira a fecha de corte en una fase posterior. En este analisis no se ejecuta cierre.",
        })

    if str(config.get("tipo_estructura_historico") or "").upper() == "SIN_HISTORICO":
        alertas.append({
            "tipo": "info",
            "mensaje": "La configuracion no exige tabla historica para esta estructura.",
        })

    if not alertas:
        alertas.append({
            "tipo": "ok",
            "mensaje": "Analisis completado sin alertas criticas.",
        })

    return alertas


def construir_columnas_problema(
    columnas_clave_faltantes: List[str],
    columnas_faltantes: List[str],
    columnas_nuevas: List[str],
    columnas_generadas: List[Dict[str, str]],
    alertas: List[Dict[str, str]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, str]], List[Dict[str, str]], List[Dict[str, str]]]:
    problemas: List[Dict[str, Any]] = []

    for columna in columnas_clave_faltantes:
        problemas.append({
            "columna": columna,
            "estado": "CLAVE FALTANTE",
            "tipo": "error",
            "observacion": "Clave de cruce requerida y no encontrada en el archivo.",
            "visible_default": True,
        })

    for columna in columnas_faltantes:
        if es_columna_meta(columna):
            problemas.append({
                "columna": columna,
                "estado": "FALTANTE",
                "tipo": "advertencia",
                "observacion": "Se actualizara desde el modulo de metas.",
                "visible_default": True,
            })
        else:
            problemas.append({
                "columna": columna,
                "estado": "FALTANTE",
                "tipo": "advertencia",
                "observacion": "Existe en la tabla destino, pero no viene en el archivo.",
                "visible_default": True,
            })

    for columna in columnas_nuevas:
        problemas.append({
            "columna": columna,
            "estado": "NUEVA",
            "tipo": "info",
            "observacion": "Viene en el archivo, pero no existe en la tabla destino. Revisar si requiere mapeo.",
            "visible_default": True,
        })

    problemas.extend(columnas_generadas)

    errores = [item for item in problemas if item.get("tipo") == "error"]
    advertencias = [item for item in alertas if item.get("tipo") == "advertencia"]
    infos = [item for item in alertas if item.get("tipo") in ("info", "ok")]
    return problemas, errores, advertencias, infos


def es_columna_meta(columna: Any) -> bool:
    return "meta" in normalizar_columna(columna)


def es_configuracion_saldos(config: Dict[str, Any]) -> bool:
    texto = f"{config.get('cartera') or ''} {config.get('producto') or ''} {config.get('tabla_destino') or ''}"
    return "saldo" in normalizar_columna(texto)


def validar_ruta_historica_compartamos(
    tabla_origen: str,
    tabla_historica: str,
    alertas: List[Dict[str, str]],
) -> None:
    origen_norm = normalizar_columna(tabla_origen)
    historico_norm = normalizar_columna(tabla_historica)

    if "compartamos_grupal_castigo" in origen_norm and "hist_grupal_castigo" not in historico_norm:
        alertas.append({
            "tipo": "error",
            "mensaje": "Compartamos Castigo Grupal debe cerrar en Compartamos_Castigo_Cobranzas.dbo.HIST_GRUPAL_CASTIGO.",
        })

    if (
        "compartamos_castigo" in origen_norm
        and "grupal" not in origen_norm
        and "hist_grupal_castigo" in historico_norm
    ):
        alertas.append({
            "tipo": "error",
            "mensaje": "Compartamos Castigo Individual debe cerrar en Compartamos_Castigo_Cobranzas.dbo.compartamos_castigo.",
        })


def serializar_valor(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if pd.isna(value):
        return None
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def serializar_dict(row: Dict[str, Any]) -> Dict[str, Any]:
    return {key: serializar_valor(value) for key, value in row.items()}
