"""
Planes de mejora por agente y criterio (CRM_IA_PLAN_MEJORA).

REGLAS ACORDADAS (21/09/2026)
  Candidato   falla el criterio en >= 2 de sus ultimas 5 mediciones, con >= 3
              mediciones de ese criterio. (La pantalla lo sugiere; abrir un plan
              igual queda a criterio del supervisor.)
  Linea base  cumplimiento en esas ultimas mediciones, al crear el plan.
  Meta        80% de cumplimiento en las 5 mediciones siguientes al inicio.
  Cierre      CUMPLIDO / NO_CUMPLIDO al completar las 5 mediciones;
              VENCIDO si a los 30 dias no se completaron. Lo confirma una persona.

MEDICION
  Resultado VIGENTE del criterio en una llamada FINALIZADA del agente: el
  corregido si Calidad publico una correccion, si no el de la IA. Solo cuenta si
  es CUMPLE o NO_CUMPLE (lo no medido no suma ni resta). La fecha es la de la
  llamada (si falta, la de carga): el plan mide llamadas posteriores a su inicio.

El avance no se guarda: se calcula al leer, para que nunca contradiga a las
evaluaciones. Al cerrar se guarda una foto (cierre_mediciones / cierre_cumple).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.core.db_siscob import engine_siscob

REGLA = {"ultimas": 5, "fallas": 2, "minimo": 3, "meta_pct": 80.0, "mediciones_objetivo": 5, "dias": 30}
MEDIDOS = {"CUMPLE", "NO_CUMPLE"}
ESTADOS_CIERRE = {"CUMPLIDO", "NO_CUMPLIDO", "VENCIDO", "ANULADO"}

SQL_MEDICIONES = text("""
    SELECT L.id_feedback,
           fecha = COALESCE(L.fecha_llamada, L.fecha_creacion),
           L.cartera, E.nombre_criterio, E.id_pauta,
           E.resultado_ia, C.accion, C.resultado_esperado
    FROM CobAuto.dbo.CRM_IA_EVALUACION_CRITERIO E WITH(NOLOCK)
    INNER JOIN CobAuto.dbo.ia_feedback_llamadas L WITH(NOLOCK)
            ON L.id_feedback = E.id_feedback
    LEFT JOIN CobAuto.dbo.CRM_IA_CALIBRACION_CRITERIO C WITH(NOLOCK)
           ON C.id_evaluacion_criterio = E.id_evaluacion_criterio
          AND C.estado = 'PUBLICADA'
    WHERE LTRIM(RTRIM(L.agente)) = :agente
      AND E.codigo_criterio = :codigo
      AND L.estado = 'FINALIZADO'
    ORDER BY COALESCE(L.fecha_llamada, L.fecha_creacion), L.id_feedback
""")


def _mediciones(conn, agente: str, codigo: str) -> List[Dict]:
    """Mediciones del criterio para el agente, de la mas antigua a la mas reciente."""
    salida = []
    for fila in conn.execute(SQL_MEDICIONES, {"agente": agente.strip(), "codigo": codigo}).mappings():
        vigente = fila["resultado_ia"]
        if str(fila["accion"] or "").upper() == "CORREGIR" and fila["resultado_esperado"]:
            vigente = fila["resultado_esperado"]
        vigente = str(vigente or "").upper()
        fecha = fila["fecha"]
        if isinstance(fecha, date) and not isinstance(fecha, datetime):
            fecha = datetime.combine(fecha, datetime.min.time())
        salida.append({**dict(fila), "fecha": fecha, "vigente": vigente, "medido": vigente in MEDIDOS})
    return salida


def _avance(plan: Dict, mediciones: List[Dict], ahora: datetime) -> Dict:
    posteriores = [m for m in mediciones if m["medido"] and m["fecha"] and m["fecha"] >= plan["fecha_inicio"]]
    objetivo = int(plan["mediciones_objetivo"])
    tramo = posteriores[:objetivo]
    cumple = sum(1 for m in tramo if m["vigente"] == "CUMPLE")
    pct = round(cumple / len(tramo) * 100, 1) if tramo else None
    if len(tramo) >= objetivo:
        sugerido = "CUMPLIDO" if pct >= float(plan["meta_pct"]) else "NO_CUMPLIDO"
    elif ahora > plan["fecha_vencimiento"]:
        sugerido = "VENCIDO"
    else:
        sugerido = "ACTIVO"
    return {
        "mediciones": len(tramo),
        "cumple": cumple,
        "pct": pct,
        "estado_sugerido": sugerido,
        "dias_restantes": max(0, (plan["fecha_vencimiento"] - ahora).days),
        "detalle": [{"id_feedback": m["id_feedback"], "fecha": m["fecha"].isoformat(), "resultado": m["vigente"]} for m in tramo],
    }


def _serializar(plan: Dict) -> Dict:
    out = {}
    for k, v in plan.items():
        if isinstance(v, datetime):
            out[k] = v.isoformat()
        elif hasattr(v, "__float__") and not isinstance(v, (int, float, bool)):
            out[k] = float(v)
        else:
            out[k] = v
    return out


def listar_planes(estado: Optional[str] = None, agente: Optional[str] = None) -> List[Dict]:
    filtros, params = [], {}
    if estado:
        filtros.append("estado = :estado")
        params["estado"] = estado.upper()
    if agente:
        filtros.append("agente = :agente")
        params["agente"] = agente.strip()
    where = f"WHERE {' AND '.join(filtros)}" if filtros else ""
    ahora = datetime.now()
    with engine_siscob.connect() as conn:
        planes = [dict(p) for p in conn.execute(text(f"""
            SELECT * FROM CobAuto.dbo.CRM_IA_PLAN_MEJORA WITH(NOLOCK)
            {where}
            ORDER BY CASE WHEN estado = 'ACTIVO' THEN 0 ELSE 1 END, fecha_inicio DESC
        """), params).mappings()]
        for plan in planes:
            if plan["estado"] == "ACTIVO":
                plan["avance"] = _avance(plan, _mediciones(conn, plan["agente"], plan["codigo_criterio"]), ahora)
            else:
                plan["avance"] = None
    return [_serializar(p) for p in planes]


def crear_plan(
    *,
    agente: str,
    codigo_criterio: str,
    accion_acordada: Optional[str] = None,
    responsable: Optional[str] = None,
    usuario: Optional[str] = None,
) -> Dict:
    agente = (agente or "").strip()
    codigo = (codigo_criterio or "").strip()
    if not agente or agente.lower().startswith("sin agente"):
        raise ValueError("El plan necesita un agente asignado.")
    if not codigo:
        raise ValueError("El plan necesita un criterio.")

    inicio = datetime.now()
    with engine_siscob.begin() as conn:
        mediciones = _mediciones(conn, agente, codigo)
        medidas = [m for m in mediciones if m["medido"]]
        ultimas = medidas[-REGLA["ultimas"]:]
        fallas = sum(1 for m in ultimas if m["vigente"] == "NO_CUMPLE")
        cumple = len(ultimas) - fallas
        ref = mediciones[-1] if mediciones else {}
        candidato = len(ultimas) >= REGLA["minimo"] and fallas >= REGLA["fallas"]
        motivo = (f"Falla {fallas} de sus últimas {len(ultimas)} mediciones"
                  + ("" if candidato else " (no cumple la regla de candidato; abierto por decisión del supervisor)"))
        try:
            id_plan = conn.execute(text("""
                INSERT INTO CobAuto.dbo.CRM_IA_PLAN_MEJORA
                    (agente, cartera, codigo_criterio, nombre_criterio, id_pauta,
                     base_mediciones, base_cumple, motivo, accion_acordada, responsable,
                     meta_pct, mediciones_objetivo, fecha_inicio, fecha_vencimiento, estado, creado_por)
                OUTPUT INSERTED.id_plan
                VALUES
                    (:agente, :cartera, :codigo, :nombre, :id_pauta,
                     :base_med, :base_cum, :motivo, :accion, :responsable,
                     :meta, :objetivo, :inicio, :vence, 'ACTIVO', :usuario)
            """), {
                "agente": agente, "cartera": ref.get("cartera"), "codigo": codigo,
                "nombre": ref.get("nombre_criterio"), "id_pauta": ref.get("id_pauta"),
                "base_med": len(ultimas), "base_cum": cumple, "motivo": motivo,
                "accion": (accion_acordada or "").strip() or None, "responsable": (responsable or "").strip() or None,
                "meta": REGLA["meta_pct"], "objetivo": REGLA["mediciones_objetivo"],
                "inicio": inicio, "vence": inicio + timedelta(days=REGLA["dias"]),
                "usuario": (usuario or "").strip() or None,
            }).scalar()
        except IntegrityError as exc:
            raise LookupError("Ese agente ya tiene un plan ACTIVO para este criterio.") from exc
    return {"ok": True, "id_plan": int(id_plan), "candidato": candidato, "motivo": motivo}


def cerrar_plan(id_plan: int, *, estado: str, comentario: Optional[str] = None, usuario: Optional[str] = None) -> Dict:
    estado = (estado or "").upper()
    if estado not in ESTADOS_CIERRE:
        raise ValueError(f"Estado de cierre inválido: {estado}")
    ahora = datetime.now()
    with engine_siscob.begin() as conn:
        plan = conn.execute(text("SELECT * FROM CobAuto.dbo.CRM_IA_PLAN_MEJORA WHERE id_plan = :id"), {"id": id_plan}).mappings().first()
        if not plan:
            raise LookupError("El plan no existe.")
        plan = dict(plan)
        if plan["estado"] != "ACTIVO":
            raise ValueError(f"El plan ya está cerrado ({plan['estado']}).")
        avance = _avance(plan, _mediciones(conn, plan["agente"], plan["codigo_criterio"]), ahora)
        conn.execute(text("""
            UPDATE CobAuto.dbo.CRM_IA_PLAN_MEJORA
            SET estado = :estado, cierre_mediciones = :med, cierre_cumple = :cum,
                comentario_cierre = :comentario, cerrado_por = :usuario, fecha_cierre = :ahora
            WHERE id_plan = :id AND estado = 'ACTIVO'
        """), {"estado": estado, "med": avance["mediciones"], "cum": avance["cumple"],
               "comentario": (comentario or "").strip() or None, "usuario": (usuario or "").strip() or None,
               "ahora": ahora, "id": id_plan})
    return {"ok": True, "id_plan": id_plan, "estado": estado, "estado_sugerido": avance["estado_sugerido"], "avance": avance}
