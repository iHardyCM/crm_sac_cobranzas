from __future__ import annotations

import re
from collections import defaultdict
from copy import deepcopy
from datetime import date
from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy import text

from app.core.db_siscob import engine_siscob
from app.services.admin_supervisores_service import listar_carteras


ESTADO_BORRADOR = "BORRADOR"
ESTADO_PUBLICADA = "PUBLICADA"
ESTADO_ARCHIVADA = "ARCHIVADA"

TIPO_PUNTUABLE = "PUNTUABLE"
TIPO_ANULANTE_BLOQUE = "ANULANTE_BLOQUE"
TIPOS_CRITERIO = {TIPO_PUNTUABLE, TIPO_ANULANTE_BLOQUE}

FUENTES_EVIDENCIA = {
    "AUDIO", "TRANSCRIPCION", "CRM", "TIPIFICACION", "CAMPANIA", "SISTEMA", "MULTIFUENTE",
}


def asegurar_tablas_pautas(conn) -> None:
    """Crea el catálogo versionado sin tocar evaluaciones ya persistidas."""
    conn.execute(text("""
        IF OBJECT_ID('CobAuto.dbo.CRM_IA_PAUTA', 'U') IS NULL
        BEGIN
            CREATE TABLE CobAuto.dbo.CRM_IA_PAUTA (
                id_pauta INT IDENTITY(1,1) PRIMARY KEY,
                nombre NVARCHAR(160) NOT NULL,
                version INT NOT NULL,
                descripcion NVARCHAR(MAX) NULL,
                estado VARCHAR(20) NOT NULL DEFAULT 'BORRADOR',
                aplica_todas BIT NOT NULL DEFAULT 0,
                vigencia_desde DATE NULL,
                vigencia_hasta DATE NULL,
                creado_por VARCHAR(80) NULL,
                fecha_creacion DATETIME NOT NULL DEFAULT GETDATE(),
                actualizado_por VARCHAR(80) NULL,
                fecha_actualizacion DATETIME NOT NULL DEFAULT GETDATE(),
                CONSTRAINT UQ_CRM_IA_PAUTA_NOMBRE_VERSION UNIQUE(nombre, version)
            );
        END;

        IF OBJECT_ID('CobAuto.dbo.CRM_IA_PAUTA_BLOQUE', 'U') IS NULL
        BEGIN
            CREATE TABLE CobAuto.dbo.CRM_IA_PAUTA_BLOQUE (
                id_bloque INT IDENTITY(1,1) PRIMARY KEY,
                id_pauta INT NOT NULL,
                codigo VARCHAR(50) NOT NULL,
                nombre NVARCHAR(180) NOT NULL,
                categoria NVARCHAR(100) NULL,
                descripcion NVARCHAR(MAX) NULL,
                orden INT NOT NULL DEFAULT 1,
                activo BIT NOT NULL DEFAULT 1,
                CONSTRAINT UQ_CRM_IA_PAUTA_BLOQUE UNIQUE(id_pauta, codigo)
            );
        END;

        IF OBJECT_ID('CobAuto.dbo.CRM_IA_PAUTA_CRITERIO', 'U') IS NULL
        BEGIN
            CREATE TABLE CobAuto.dbo.CRM_IA_PAUTA_CRITERIO (
                id_criterio INT IDENTITY(1,1) PRIMARY KEY,
                id_pauta INT NOT NULL,
                id_bloque INT NOT NULL,
                codigo_criterio VARCHAR(80) NOT NULL,
                nombre NVARCHAR(220) NOT NULL,
                tipo_criterio VARCHAR(30) NOT NULL DEFAULT 'PUNTUABLE',
                peso DECIMAL(10,2) NOT NULL DEFAULT 0,
                detalle NVARCHAR(MAX) NULL,
                regla_evaluacion NVARCHAR(MAX) NULL,
                regla_cumple NVARCHAR(MAX) NULL,
                regla_no_cumple NVARCHAR(MAX) NULL,
                regla_aplicabilidad NVARCHAR(MAX) NULL,
                criticidad VARCHAR(80) NULL,
                fuente_evidencia VARCHAR(30) NULL,
                requiere_evidencia BIT NOT NULL DEFAULT 0,
                puede_descalificar BIT NOT NULL DEFAULT 0,
                recomendacion NVARCHAR(MAX) NULL,
                orden INT NOT NULL DEFAULT 1,
                activo BIT NOT NULL DEFAULT 1,
                CONSTRAINT UQ_CRM_IA_PAUTA_CRITERIO UNIQUE(id_pauta, codigo_criterio)
            );
        END;

        IF OBJECT_ID('CobAuto.dbo.CRM_IA_PAUTA_CARTERA', 'U') IS NULL
        BEGIN
            CREATE TABLE CobAuto.dbo.CRM_IA_PAUTA_CARTERA (
                id_asignacion INT IDENTITY(1,1) PRIMARY KEY,
                id_pauta INT NOT NULL,
                idcartera INT NOT NULL,
                grupo_nombre NVARCHAR(120) NULL,
                CONSTRAINT UQ_CRM_IA_PAUTA_CARTERA UNIQUE(id_pauta, idcartera)
            );
        END;
    """))


def _limpiar_texto(value: Any, limite: Optional[int] = None) -> str:
    texto = str(value or "").strip()
    return texto[:limite] if limite else texto


def _normalizar_bool(value: Any) -> bool:
    return value is True or str(value).strip().lower() in {"1", "true", "si", "sí", "on"}


def _numero(value: Any) -> float:
    try:
        return round(float(value or 0), 2)
    except (TypeError, ValueError):
        return 0.0


def _normalizar_fecha(value: Any) -> Optional[str]:
    texto = _limpiar_texto(value, 10)
    return texto or None


def _normalizar_carteras(values: Iterable[Any]) -> List[int]:
    ids = []
    for value in values or []:
        try:
            cartera = int(value)
        except (TypeError, ValueError):
            continue
        if cartera > 0 and cartera not in ids:
            ids.append(cartera)
    return sorted(ids)


def _normalizar_criterio(item: Dict, orden: int) -> Dict:
    tipo = _limpiar_texto(item.get("tipo_criterio") or TIPO_PUNTUABLE, 30).upper()
    if tipo not in TIPOS_CRITERIO:
        tipo = TIPO_PUNTUABLE
    fuente = _limpiar_texto(item.get("fuente_evidencia") or "TRANSCRIPCION", 30).upper()
    return {
        "codigo_criterio": _limpiar_texto(item.get("codigo_criterio") or item.get("codigo"), 80).upper(),
        "nombre": _limpiar_texto(item.get("nombre"), 220),
        "tipo_criterio": tipo,
        "peso": 0.0 if tipo == TIPO_ANULANTE_BLOQUE else _numero(item.get("peso")),
        "detalle": _limpiar_texto(item.get("detalle")),
        "regla_evaluacion": _limpiar_texto(item.get("regla_evaluacion")),
        "regla_cumple": _limpiar_texto(item.get("regla_cumple")),
        "regla_no_cumple": _limpiar_texto(item.get("regla_no_cumple")),
        "regla_aplicabilidad": _limpiar_texto(item.get("regla_aplicabilidad")),
        "criticidad": _limpiar_texto(item.get("criticidad"), 80),
        "fuente_evidencia": fuente,
        "requiere_evidencia": _normalizar_bool(item.get("requiere_evidencia")),
        "puede_descalificar": _normalizar_bool(item.get("puede_descalificar")),
        "recomendacion": _limpiar_texto(item.get("recomendacion") or item.get("recomendacion_entrenable")),
        "orden": int(item.get("orden") or orden),
        "activo": _normalizar_bool(item.get("activo", True)),
    }


def normalizar_payload_pauta(payload: Dict) -> Dict:
    bloques = []
    for indice, raw_bloque in enumerate(payload.get("bloques") or [], start=1):
        if not isinstance(raw_bloque, dict):
            continue
        criterios = [
            _normalizar_criterio(raw, orden)
            for orden, raw in enumerate(raw_bloque.get("criterios") or [], start=1)
            if isinstance(raw, dict)
        ]
        bloques.append({
            "codigo": _limpiar_texto(raw_bloque.get("codigo"), 50).upper(),
            "nombre": _limpiar_texto(raw_bloque.get("nombre"), 180),
            "categoria": _limpiar_texto(raw_bloque.get("categoria"), 100),
            "descripcion": _limpiar_texto(raw_bloque.get("descripcion")),
            "orden": int(raw_bloque.get("orden") or indice),
            "activo": _normalizar_bool(raw_bloque.get("activo", True)),
            "criterios": criterios,
        })
    return {
        "id_pauta": payload.get("id_pauta"),
        "nombre": _limpiar_texto(payload.get("nombre"), 160),
        "version": int(payload.get("version") or 0),
        "descripcion": _limpiar_texto(payload.get("descripcion")),
        "aplica_todas": _normalizar_bool(payload.get("aplica_todas")),
        "idcarteras": _normalizar_carteras(payload.get("idcarteras") or payload.get("carteras")),
        "grupo_nombre": _limpiar_texto(payload.get("grupo_nombre"), 120),
        "vigencia_desde": _normalizar_fecha(payload.get("vigencia_desde")),
        "vigencia_hasta": _normalizar_fecha(payload.get("vigencia_hasta")),
        "bloques": bloques,
    }


def validar_pauta(payload: Dict, requiere_total: bool = False) -> Dict:
    pauta = normalizar_payload_pauta(payload)
    errores: List[str] = []
    if not pauta["nombre"]:
        errores.append("La pauta debe tener nombre.")
    if not pauta["aplica_todas"] and not pauta["idcarteras"]:
        errores.append("Selecciona todas las carteras o al menos una cartera de alcance.")
    codigos_bloque = set()
    codigos_criterio = set()
    total = 0.0
    for bloque in pauta["bloques"]:
        if not bloque["codigo"] or not bloque["nombre"]:
            errores.append("Cada bloque debe tener código y nombre.")
        if bloque["codigo"] in codigos_bloque:
            errores.append(f"Código de bloque duplicado: {bloque['codigo']}.")
        codigos_bloque.add(bloque["codigo"])
        for criterio in bloque["criterios"]:
            codigo = criterio["codigo_criterio"]
            if not codigo or not criterio["nombre"]:
                errores.append("Cada criterio debe tener código y nombre.")
            if codigo in codigos_criterio:
                errores.append(f"Código de criterio duplicado: {codigo}.")
            codigos_criterio.add(codigo)
            if criterio["tipo_criterio"] == TIPO_PUNTUABLE and criterio["activo"]:
                if criterio["peso"] <= 0:
                    errores.append(f"{codigo or 'Criterio'} debe tener un peso mayor a cero.")
                total += criterio["peso"]
            if criterio["tipo_criterio"] == TIPO_ANULANTE_BLOQUE and criterio["peso"]:
                errores.append(f"{codigo or 'Criterio'} es anulante y no debe tener peso.")
            if criterio["fuente_evidencia"] not in FUENTES_EVIDENCIA:
                errores.append(f"{codigo or 'Criterio'} tiene una fuente de evidencia no válida.")
            if not criterio["regla_evaluacion"]:
                errores.append(f"{codigo or 'Criterio'} requiere una regla de evaluación.")
    if not pauta["bloques"]:
        errores.append("La pauta debe incluir al menos un bloque.")
    if requiere_total and round(total, 2) != 100.0:
        errores.append(f"Los criterios puntuables activos suman {total:.2f}; para publicar deben sumar 100.00.")
    return {"pauta": pauta, "errores": errores, "peso_total": round(total, 2), "valida": not errores}


def _obtener_pauta_conn(conn, id_pauta: int) -> Optional[Dict]:
    pauta = conn.execute(text("""
        SELECT id_pauta, nombre, version, descripcion, estado, aplica_todas,
               vigencia_desde, vigencia_hasta, creado_por, fecha_creacion,
               actualizado_por, fecha_actualizacion
        FROM CobAuto.dbo.CRM_IA_PAUTA
        WHERE id_pauta = :id_pauta
    """), {"id_pauta": id_pauta}).mappings().first()
    if not pauta:
        return None
    data = dict(pauta)
    bloques = conn.execute(text("""
        SELECT id_bloque, codigo, nombre, categoria, descripcion, orden, activo
        FROM CobAuto.dbo.CRM_IA_PAUTA_BLOQUE
        WHERE id_pauta = :id_pauta
        ORDER BY orden, id_bloque
    """), {"id_pauta": id_pauta}).mappings().all()
    criterios = conn.execute(text("""
        SELECT id_bloque, codigo_criterio, nombre, tipo_criterio, peso, detalle,
               regla_evaluacion, regla_cumple, regla_no_cumple, regla_aplicabilidad,
               criticidad, fuente_evidencia, requiere_evidencia, puede_descalificar,
               recomendacion, orden, activo
        FROM CobAuto.dbo.CRM_IA_PAUTA_CRITERIO
        WHERE id_pauta = :id_pauta
        ORDER BY orden, id_criterio
    """), {"id_pauta": id_pauta}).mappings().all()
    criterios_por_bloque: Dict[int, List[Dict]] = defaultdict(list)
    for criterio in criterios:
        item = dict(criterio)
        item["peso"] = float(item.get("peso") or 0)
        item["requiere_evidencia"] = bool(item.get("requiere_evidencia"))
        item["puede_descalificar"] = bool(item.get("puede_descalificar"))
        item["activo"] = bool(item.get("activo"))
        criterios_por_bloque[item.pop("id_bloque")].append(item)
    data["bloques"] = []
    for bloque in bloques:
        item = dict(bloque)
        item["activo"] = bool(item.get("activo"))
        item["criterios"] = criterios_por_bloque.get(item["id_bloque"], [])
        data["bloques"].append(item)
    asignaciones = conn.execute(text("""
        SELECT idcartera, grupo_nombre
        FROM CobAuto.dbo.CRM_IA_PAUTA_CARTERA
        WHERE id_pauta = :id_pauta
        ORDER BY idcartera
    """), {"id_pauta": id_pauta}).mappings().all()
    data["idcarteras"] = [int(row["idcartera"]) for row in asignaciones]
    data["grupo_nombre"] = next((row["grupo_nombre"] for row in asignaciones if row["grupo_nombre"]), None)
    data["aplica_todas"] = bool(data.get("aplica_todas"))
    for campo in ("vigencia_desde", "vigencia_hasta", "fecha_creacion", "fecha_actualizacion"):
        if data.get(campo) is not None:
            data[campo] = data[campo].isoformat()
    return data


def listar_pautas() -> List[Dict]:
    with engine_siscob.begin() as conn:
        asegurar_tablas_pautas(conn)
        rows = conn.execute(text("""
            SELECT P.id_pauta, P.nombre, P.version, P.estado, P.aplica_todas,
                   P.vigencia_desde, P.vigencia_hasta, P.fecha_actualizacion,
                   COUNT(C.id_criterio) AS cantidad_criterios,
                   COALESCE(SUM(CASE WHEN C.activo = 1 AND C.tipo_criterio = 'PUNTUABLE' THEN C.peso ELSE 0 END), 0) AS peso_total
            FROM CobAuto.dbo.CRM_IA_PAUTA P
            LEFT JOIN CobAuto.dbo.CRM_IA_PAUTA_CRITERIO C ON C.id_pauta = P.id_pauta
            GROUP BY P.id_pauta, P.nombre, P.version, P.estado, P.aplica_todas,
                     P.vigencia_desde, P.vigencia_hasta, P.fecha_actualizacion
            ORDER BY P.nombre, P.version DESC
        """)).mappings().all()
        alcances = conn.execute(text("""
            SELECT id_pauta, idcartera FROM CobAuto.dbo.CRM_IA_PAUTA_CARTERA
        """)).mappings().all()
    por_pauta: Dict[int, List[int]] = defaultdict(list)
    for alcance in alcances:
        por_pauta[int(alcance["id_pauta"])].append(int(alcance["idcartera"]))
    salida = []
    for row in rows:
        item = dict(row)
        item["peso_total"] = float(item.get("peso_total") or 0)
        item["cantidad_criterios"] = int(item.get("cantidad_criterios") or 0)
        item["aplica_todas"] = bool(item.get("aplica_todas"))
        item["idcarteras"] = por_pauta.get(int(item["id_pauta"]), [])
        for campo in ("vigencia_desde", "vigencia_hasta", "fecha_actualizacion"):
            if item.get(campo) is not None:
                item[campo] = item[campo].isoformat()
        salida.append(item)
    return salida


def obtener_pauta(id_pauta: int) -> Optional[Dict]:
    with engine_siscob.begin() as conn:
        asegurar_tablas_pautas(conn)
        return _obtener_pauta_conn(conn, int(id_pauta))


def guardar_borrador(payload: Dict, usuario_actualizacion: str = "") -> Dict:
    validacion = validar_pauta(payload, requiere_total=False)
    if validacion["errores"]:
        raise ValueError(" ".join(validacion["errores"]))
    pauta = validacion["pauta"]
    with engine_siscob.begin() as conn:
        asegurar_tablas_pautas(conn)
        id_pauta = pauta.get("id_pauta")
        if id_pauta:
            existente = _obtener_pauta_conn(conn, int(id_pauta))
            if not existente:
                raise ValueError("La pauta no existe.")
            if existente["estado"] != ESTADO_BORRADOR:
                raise ValueError("Solo las pautas en borrador pueden editarse. Duplica la versión publicada.")
            conn.execute(text("""
                UPDATE CobAuto.dbo.CRM_IA_PAUTA
                SET nombre = :nombre, descripcion = :descripcion, aplica_todas = :aplica_todas,
                    vigencia_desde = :vigencia_desde, vigencia_hasta = :vigencia_hasta,
                    actualizado_por = :usuario, fecha_actualizacion = GETDATE()
                WHERE id_pauta = :id_pauta
            """), {**pauta, "usuario": usuario_actualizacion or None})
            conn.execute(text("DELETE FROM CobAuto.dbo.CRM_IA_PAUTA_CARTERA WHERE id_pauta = :id_pauta"), {"id_pauta": id_pauta})
            conn.execute(text("DELETE FROM CobAuto.dbo.CRM_IA_PAUTA_CRITERIO WHERE id_pauta = :id_pauta"), {"id_pauta": id_pauta})
            conn.execute(text("DELETE FROM CobAuto.dbo.CRM_IA_PAUTA_BLOQUE WHERE id_pauta = :id_pauta"), {"id_pauta": id_pauta})
        else:
            siguiente = conn.execute(text("""
                SELECT ISNULL(MAX(version), 0) + 1 AS version
                FROM CobAuto.dbo.CRM_IA_PAUTA WHERE nombre = :nombre
            """), {"nombre": pauta["nombre"]}).scalar_one()
            result = conn.execute(text("""
                INSERT INTO CobAuto.dbo.CRM_IA_PAUTA
                    (nombre, version, descripcion, estado, aplica_todas, vigencia_desde, vigencia_hasta, creado_por, actualizado_por)
                OUTPUT INSERTED.id_pauta
                VALUES (:nombre, :version, :descripcion, 'BORRADOR', :aplica_todas, :vigencia_desde, :vigencia_hasta, :usuario, :usuario)
            """), {**pauta, "version": siguiente, "usuario": usuario_actualizacion or None})
            id_pauta = int(result.scalar_one())
        for idcartera in pauta["idcarteras"]:
            conn.execute(text("""
                INSERT INTO CobAuto.dbo.CRM_IA_PAUTA_CARTERA (id_pauta, idcartera, grupo_nombre)
                VALUES (:id_pauta, :idcartera, :grupo_nombre)
            """), {"id_pauta": id_pauta, "idcartera": idcartera, "grupo_nombre": pauta["grupo_nombre"] or None})
        for bloque in pauta["bloques"]:
            result = conn.execute(text("""
                INSERT INTO CobAuto.dbo.CRM_IA_PAUTA_BLOQUE
                    (id_pauta, codigo, nombre, categoria, descripcion, orden, activo)
                OUTPUT INSERTED.id_bloque
                VALUES (:id_pauta, :codigo, :nombre, :categoria, :descripcion, :orden, :activo)
            """), {**bloque, "id_pauta": id_pauta})
            id_bloque = int(result.scalar_one())
            for criterio in bloque["criterios"]:
                conn.execute(text("""
                    INSERT INTO CobAuto.dbo.CRM_IA_PAUTA_CRITERIO
                        (id_pauta, id_bloque, codigo_criterio, nombre, tipo_criterio, peso, detalle,
                         regla_evaluacion, regla_cumple, regla_no_cumple, regla_aplicabilidad,
                         criticidad, fuente_evidencia, requiere_evidencia, puede_descalificar,
                         recomendacion, orden, activo)
                    VALUES
                        (:id_pauta, :id_bloque, :codigo_criterio, :nombre, :tipo_criterio, :peso, :detalle,
                         :regla_evaluacion, :regla_cumple, :regla_no_cumple, :regla_aplicabilidad,
                         :criticidad, :fuente_evidencia, :requiere_evidencia, :puede_descalificar,
                         :recomendacion, :orden, :activo)
                """), {**criterio, "id_pauta": id_pauta, "id_bloque": id_bloque})
        guardada = _obtener_pauta_conn(conn, int(id_pauta))
    return {"ok": True, "pauta": guardada, "validacion": validar_pauta(guardada, requiere_total=False)}


def duplicar_pauta(id_pauta: int, usuario_actualizacion: str = "") -> Dict:
    origen = obtener_pauta(id_pauta)
    if not origen:
        raise ValueError("La pauta no existe.")
    copia = deepcopy(origen)
    copia.pop("id_pauta", None)
    copia["nombre"] = origen["nombre"]
    copia["version"] = 0
    return guardar_borrador(copia, usuario_actualizacion)


def publicar_pauta(id_pauta: int, usuario_actualizacion: str = "") -> Dict:
    with engine_siscob.begin() as conn:
        asegurar_tablas_pautas(conn)
        pauta = _obtener_pauta_conn(conn, id_pauta)
        if not pauta:
            raise ValueError("La pauta no existe.")
        if pauta["estado"] != ESTADO_BORRADOR:
            raise ValueError("Solo un borrador puede publicarse.")
        validacion = validar_pauta(pauta, requiere_total=True)
        if validacion["errores"]:
            raise ValueError(" ".join(validacion["errores"]))
        conn.execute(text("""
            UPDATE P SET estado = 'ARCHIVADA', actualizado_por = :usuario, fecha_actualizacion = GETDATE()
            FROM CobAuto.dbo.CRM_IA_PAUTA P
            WHERE P.estado = 'PUBLICADA' AND P.id_pauta <> :id_pauta
              AND (
                :aplica_todas = 1 OR P.aplica_todas = 1
                OR EXISTS (
                    SELECT 1 FROM CobAuto.dbo.CRM_IA_PAUTA_CARTERA A
                    INNER JOIN CobAuto.dbo.CRM_IA_PAUTA_CARTERA B
                        ON A.idcartera = B.idcartera
                    WHERE A.id_pauta = P.id_pauta AND B.id_pauta = :id_pauta
                )
              )
        """), {"id_pauta": id_pauta, "aplica_todas": pauta["aplica_todas"], "usuario": usuario_actualizacion or None})
        conn.execute(text("""
            UPDATE CobAuto.dbo.CRM_IA_PAUTA
            SET estado = 'PUBLICADA', actualizado_por = :usuario, fecha_actualizacion = GETDATE()
            WHERE id_pauta = :id_pauta
        """), {"id_pauta": id_pauta, "usuario": usuario_actualizacion or None})
        publicada = _obtener_pauta_conn(conn, id_pauta)
    return {"ok": True, "pauta": publicada, "mensaje": "Pauta publicada y aplicada al alcance seleccionado."}


def archivar_pauta(id_pauta: int, usuario_actualizacion: str = "") -> Dict:
    with engine_siscob.begin() as conn:
        asegurar_tablas_pautas(conn)
        conn.execute(text("""
            UPDATE CobAuto.dbo.CRM_IA_PAUTA
            SET estado = 'ARCHIVADA', actualizado_por = :usuario, fecha_actualizacion = GETDATE()
            WHERE id_pauta = :id_pauta
        """), {"id_pauta": id_pauta, "usuario": usuario_actualizacion or None})
    return {"ok": True, "mensaje": "Pauta archivada."}


def obtener_carteras_pauta() -> List[Dict]:
    return listar_carteras()


def plantilla_general_evaluacion() -> Dict:
    """Convierte la pauta base vigente en un borrador general editable, sin publicarlo."""
    from app.services.mibanco_quality_pauta import obtener_pauta_mibanco

    descripciones_bloque = {
        "PECUF": "Evalúa conductas y comunicaciones del agente que pueden afectar directamente al usuario final, incluyendo el trato, la escucha y la claridad de la información entregada.",
        "PECN": "Evalúa la calidad de la gestión de cobranza: diagnóstico de la situación, desarrollo de alternativas, manejo de objeciones y conducción hacia una solución o compromiso.",
        "PECC": "Evalúa el cumplimiento operativo y la comunicación de acuerdos, así como la correcta relación del agente con la entidad, sus procesos y sus canales.",
        "PENC": "Evalúa protocolos de atención que sostienen una interacción profesional, clara y adecuada desde el saludo hasta la despedida.",
    }
    bloques: Dict[str, Dict] = {}
    for orden, criterio in enumerate(obtener_pauta_mibanco(), start=1):
        codigo_criterio = str(criterio.get("codigo_criterio") or "").strip()
        nombre = str(criterio.get("nombre") or "").strip()
        detalle = str(criterio.get("detalle") or "")
        regla_evaluacion = str(criterio.get("regla_evaluacion") or "")
        regla_cumple = str(criterio.get("regla_cumple") or "")
        regla_no_cumple = str(criterio.get("regla_no_cumple") or "")
        aplicabilidad = str(criterio.get("regla_aplicabilidad") or "")
        if codigo_criterio == "PECC.1":
            nombre = "Respeto por la entidad y sus canales"
            detalle = "Protege la imagen de la entidad financiera"
        reemplazos_generales = {
            "Mibanco": "la entidad financiera",
            "Biznescob": "la entidad financiera",
        }
        for origen, destino in reemplazos_generales.items():
            detalle = detalle.replace(origen, destino)
            regla_evaluacion = regla_evaluacion.replace(origen, destino)
            regla_cumple = regla_cumple.replace(origen, destino)
            regla_no_cumple = regla_no_cumple.replace(origen, destino)
            aplicabilidad = aplicabilidad.replace(origen, destino)
        codigo_bloque = str(criterio.get("bloque") or "PEC").strip().upper()
        bloque = bloques.setdefault(codigo_bloque, {
            "codigo": codigo_bloque,
            "nombre": str(criterio.get("subcategoria") or codigo_bloque).strip(),
            "categoria": str(criterio.get("categoria") or "").strip(),
            "descripcion": descripciones_bloque.get(codigo_bloque, "Describe el propósito, alcance y riesgo que evalúa este bloque."),
            "orden": len(bloques) + 1,
            "activo": True,
            "criterios": [],
        })
        bloque["criterios"].append({
            "codigo_criterio": codigo_criterio,
            "nombre": nombre,
            "tipo_criterio": TIPO_PUNTUABLE,
            "peso": _numero(criterio.get("peso")),
            "detalle": detalle,
            "regla_evaluacion": regla_evaluacion,
            "regla_cumple": regla_cumple,
            "regla_no_cumple": regla_no_cumple,
            "regla_aplicabilidad": aplicabilidad,
            "criticidad": criterio.get("criticidad") or "",
            "fuente_evidencia": criterio.get("fuente_evidencia") or "TRANSCRIPCION",
            "requiere_evidencia": _normalizar_bool(criterio.get("requiere_evidencia")),
            "puede_descalificar": _normalizar_bool(criterio.get("puede_descalificar")),
            "recomendacion": "",
            "orden": orden,
            "activo": True,
        })
    return {
        "nombre": "Plantilla general de evaluación",
        "descripcion": "Plantilla editable de bloques y criterios. Ajuste reglas y alcance antes de guardarla o publicarla.",
        "estado": ESTADO_BORRADOR,
        "aplica_todas": False,
        "idcarteras": [],
        "grupo_nombre": "",
        "vigencia_desde": None,
        "vigencia_hasta": None,
        "bloques": list(bloques.values()),
    }


def plantilla_pauta_mibanco_actual() -> Dict:
    """Alias temporal de compatibilidad para llamadas internas anteriores."""
    return plantilla_general_evaluacion()


def _id_cartera_desde_texto(cartera: Optional[str]) -> Optional[int]:
    texto_cartera = _limpiar_texto(cartera)
    match = re.search(r"\b(\d{2,4})\b", texto_cartera)
    if match:
        return int(match.group(1))
    nombre = texto_cartera.upper()
    for item in obtener_carteras_pauta():
        if _limpiar_texto(item.get("cartera")).upper() == nombre:
            return int(item["idcartera"])
    return None


def obtener_pauta_publicada_para_cartera(cartera: Optional[str]) -> Optional[Dict]:
    """Devuelve definición completa. Si BBDD no está disponible, el motor conserva su fallback histórico."""
    idcartera = _id_cartera_desde_texto(cartera)
    try:
        with engine_siscob.begin() as conn:
            asegurar_tablas_pautas(conn)
            row = conn.execute(text("""
                SELECT TOP 1 P.id_pauta
                FROM CobAuto.dbo.CRM_IA_PAUTA P
                WHERE P.estado = 'PUBLICADA'
                  AND (P.vigencia_desde IS NULL OR P.vigencia_desde <= CAST(GETDATE() AS DATE))
                  AND (P.vigencia_hasta IS NULL OR P.vigencia_hasta >= CAST(GETDATE() AS DATE))
                  AND (
                    P.aplica_todas = 1
                    OR (:idcartera IS NOT NULL AND EXISTS (
                        SELECT 1 FROM CobAuto.dbo.CRM_IA_PAUTA_CARTERA A
                        WHERE A.id_pauta = P.id_pauta AND A.idcartera = :idcartera
                    ))
                  )
                ORDER BY CASE WHEN P.aplica_todas = 0 THEN 0 ELSE 1 END,
                         P.fecha_actualizacion DESC, P.id_pauta DESC
            """), {"idcartera": idcartera}).scalar()
            return _obtener_pauta_conn(conn, int(row)) if row else None
    except Exception:
        return None


def criterios_pauta_publicada_para_cartera(cartera: Optional[str]) -> Optional[List[Dict]]:
    pauta = obtener_pauta_publicada_para_cartera(cartera)
    if not pauta:
        return None
    criterios = []
    for bloque in pauta.get("bloques") or []:
        if not bloque.get("activo", True):
            continue
        for criterio in bloque.get("criterios") or []:
            if not criterio.get("activo", True):
                continue
            criterios.append({
                **criterio,
                "bloque": bloque.get("codigo"),
                "bloque_nombre": bloque.get("nombre"),
                "categoria": bloque.get("categoria"),
                "subcategoria": bloque.get("nombre"),
                "pauta_id": pauta.get("id_pauta"),
                "pauta_nombre": pauta.get("nombre"),
                "pauta_version": pauta.get("version"),
                "pauta_estado": pauta.get("estado"),
            })
    return criterios


def aplicar_anulantes_bloque(criterios: List[Dict]) -> List[Dict]:
    """Un anulante confirmado pone a cero el bloque, sin falsear estados individuales."""
    anulantes = {
        str(item.get("bloque") or item.get("subcategoria") or "")
        for item in criterios
        if str(item.get("tipo_criterio") or "").upper() == TIPO_ANULANTE_BLOQUE
        and str(item.get("estado") or "").upper() == "NO_CUMPLE"
    }
    if not anulantes:
        return criterios
    for item in criterios:
        bloque = str(item.get("bloque") or item.get("subcategoria") or "")
        if bloque not in anulantes:
            continue
        item["bloque_anulado"] = True
        item["puntaje_obtenido"] = 0.0
        item["nota"] = 0.0
        item["nota_ia"] = 0.0
        item["nota_final"] = 0.0
        if str(item.get("tipo_criterio") or "").upper() != TIPO_ANULANTE_BLOQUE:
            item["motivo_bloque_anulado"] = "El bloque fue anulado por un criterio anulante incumplido."
    return criterios
