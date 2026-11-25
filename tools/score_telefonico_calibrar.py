"""
Calibra los pesos del score telefónico con el historial real.

QUÉ HACE
  1. Lee score.Caracteristicas (Poblacion = 'MARCADOS'): por cada lunes de corte D, los teléfonos que se
     marcaron de D a D+6, sus características (calculadas solo con lo ocurrido antes de D) y si hubo
     CEF (titular o tercero con acuerdo) en esa semana. Lee los datos ya agrupados por combinación de
     características, así que pesa poco aunque haya millones de teléfonos.
  2. Separa los últimos cortes como PRUEBA (fuera del tiempo de entrenamiento).
  3. Ajusta una regresión logística con todas las carteras juntas. Además de las características del
     teléfono, el modelo lleva:
        - el nivel base de cada cartera (vigente contacta más que castigo por la cartera, no por el número);
        - los intentos de esa semana (un teléfono marcado 10 veces tiene más oportunidades que uno marcado 1).
     Ninguno de los dos entra al score: solo sirven para que los pesos del teléfono no se contaminen.
  4. Convierte los coeficientes en puntos: +20 puntos = el doble de probabilidad relativa de CEF.
     En cada característica el tramo más bajo vale 0. Score = puntos ÷ máximo posible × 100.
  5. Mide en PRUEBA:
        - AUC dentro de cada cartera (0,5 = azar; 1 = perfecto) del score y de una regla simple
          ("el que tuvo CEF más reciente primero"), para saber si el score aporta algo;
        - tasa de CEF por decil de score y por tramo (A…E), en total y por entidad.
  6. Deja un informe en tools/salidas/ y, con --guardar, escribe la versión en score.PesoVersion /
     score.Peso en estado BORRADOR. Publicarla es una decisión aparte: score.sp_PublicarPeso.

USO (desde la carpeta del CRM)
    python tools/score_telefonico_calibrar.py                 # solo informe
    python tools/score_telefonico_calibrar.py --guardar       # informe + versión BORRADOR
    python tools/score_telefonico_calibrar.py --cortes-prueba 4 --lambda-l2 2.0

Solo usa pandas, numpy y scipy (ya están en requirements.txt).
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import sparse
from scipy.optimize import minimize
from sqlalchemy import text

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from app.core.db_siscob import engine_siscob  # noqa: E402  (misma conexión del CRM, base CobAuto)

# Características del teléfono que entran al score.
#   - S_COLOR queda fuera hasta tener historial del semáforo.
#   - F_EQUIVOCADO_DNI y F_NO_EXISTE quedan fuera (diagnóstico 5): el equivocado repetido es una regla de
#     descarte, no un peso, y "no existe" no anticipa nada (6,8 % a 8,3 % de CEF la semana siguiente).
CARACTERISTICAS = [
    "T_ULT_CEF", "T_ULT_TERCERO", "T_TASA_CEF_90", "T_INTENTOS_30", "T_ULT_INTENTO", "T_MAQUINA_90",
    "S_ORIGEN", "S_FUENTE", "S_ANTIG_DATO", "S_OSIPTEL", "S_WHATSAPP", "S_TIMBRA",
    "S_TIPO_LINEA", "S_RELACION", "S_COMPARTIDO",
]
CONTROLES = ["IdCartera", "C_INTENTOS_FUT"]   # ajustan el modelo, no entran al score
PUNTOS_POR_DOBLE = 20.0                      # +20 puntos = el doble de probabilidad relativa
ORDEN_REGLA_SIMPLE = {"1-7": 3, "8-30": 2, "31-90": 1, "SIN_CEF_90": 0}


def leer_datos(desde: str | None, hasta: str | None) -> pd.DataFrame:
    columnas = ", ".join(CARACTERISTICAS + CONTROLES)
    filtro = "WHERE Poblacion = 'MARCADOS'"
    params = {}
    if desde:
        filtro += " AND FechaCorte >= :desde"
        params["desde"] = desde
    if hasta:
        filtro += " AND FechaCorte <= :hasta"
        params["hasta"] = hasta
    sql = f"""
        SELECT FechaCorte, {columnas},
               COUNT_BIG(*) AS n, SUM(CAST(EXITO AS INT)) AS k
        FROM CobAuto.score.Caracteristicas WITH (NOLOCK)
        {filtro}
        GROUP BY FechaCorte, {columnas}
    """
    with engine_siscob.connect() as cn:
        df = pd.read_sql(text(sql), cn, params=params)
    df["FechaCorte"] = pd.to_datetime(df["FechaCorte"]).dt.date
    df["IdCartera"] = df["IdCartera"].astype(str)
    for c in CARACTERISTICAS + ["C_INTENTOS_FUT"]:
        df[c] = df[c].fillna("SIN_DATO").astype(str)
    df["n"] = df["n"].astype(float)
    df["k"] = df["k"].astype(float)
    return df


def leer_entidades() -> dict[str, str]:
    sql = """SELECT CAST(ec.IdCartera AS VARCHAR(10)) AS IdCartera, e.Codigo
             FROM ControlCobranza.bl.EntidadCartera AS ec
             INNER JOIN ControlCobranza.bl.Entidad AS e ON e.IdEntidad = ec.IdEntidad"""
    with engine_siscob.connect() as cn:
        return dict(pd.read_sql(text(sql), cn).values.tolist())


def construir_matriz(df: pd.DataFrame, columnas: list[str], referencias: dict[str, str]):
    """One-hot de cada columna, sin el nivel de referencia (su coeficiente es 0)."""
    bloques, nombres = [], []
    filas = np.arange(len(df))
    for col in columnas:
        niveles = [v for v in sorted(df[col].unique()) if v != referencias[col]]
        indice = {v: i for i, v in enumerate(niveles)}
        cols = df[col].map(indice)
        mask = cols.notna().to_numpy()
        m = sparse.csr_matrix(
            (np.ones(mask.sum()), (filas[mask], cols[mask].astype(int).to_numpy())),
            shape=(len(df), len(niveles)))
        bloques.append(m)
        nombres += [(col, v) for v in niveles]
    intercepto = sparse.csr_matrix(np.ones((len(df), 1)))
    return sparse.hstack([intercepto] + bloques, format="csr"), [("INTERCEPTO", "")] + nombres


def ajustar(X, n, k, lambda_l2: float):
    """Regresión logística binomial con pesos (k éxitos en n intentos por fila) y penalización L2."""
    pen = np.full(X.shape[1], lambda_l2)
    pen[0] = 0.0                                   # el intercepto no se penaliza

    def f(beta):
        z = X @ beta
        # log(1 + e^z) estable
        log1pez = np.logaddexp(0, z)
        nll = np.sum(n * log1pez - k * z) + 0.5 * np.sum(pen * beta * beta)
        p = 1.0 / (1.0 + np.exp(-z))
        grad = X.T @ (n * p - k) + pen * beta
        return nll, grad

    beta0 = np.zeros(X.shape[1])
    tasa = k.sum() / n.sum()
    beta0[0] = math.log(tasa / (1 - tasa))
    res = minimize(f, beta0, jac=True, method="L-BFGS-B", options={"maxiter": 2000})
    if not res.success:
        print(f"AVISO: la optimización terminó con: {res.message}")
    return res.x


def auc_agrupado(score: np.ndarray, n: np.ndarray, k: np.ndarray) -> float | None:
    """AUC con empates, a partir de filas agrupadas (n teléfonos, k éxitos por fila)."""
    d = pd.DataFrame({"s": score, "pos": k, "neg": n - k}).groupby("s", as_index=False)[["pos", "neg"]].sum()
    d = d.sort_values("s")
    P, N = d["pos"].sum(), d["neg"].sum()
    if P == 0 or N == 0:
        return None
    neg_debajo = d["neg"].cumsum() - d["neg"]
    return float((d["pos"] * neg_debajo + 0.5 * d["pos"] * d["neg"]).sum() / (P * N))


def auc_dentro_de_cartera(df: pd.DataFrame, col_score: str) -> float | None:
    """Promedio de AUC por cartera, ponderado por pares positivo-negativo (el orden se usa dentro de cada cartera)."""
    num, den = 0.0, 0.0
    for _, g in df.groupby("IdCartera"):
        a = auc_agrupado(g[col_score].to_numpy(), g["n"].to_numpy(), g["k"].to_numpy())
        if a is None:
            continue
        pares = g["k"].sum() * (g["n"].sum() - g["k"].sum())
        num += a * pares
        den += pares
    return num / den if den else None


def cuantiles_ponderados(valores: np.ndarray, pesos: np.ndarray, qs: list[float]) -> list[float]:
    orden = np.argsort(valores)
    v, w = valores[orden], pesos[orden]
    acum = np.cumsum(w) / w.sum()
    return [float(v[np.searchsorted(acum, q, side="left").clip(0, len(v) - 1)]) for q in qs]


def a_markdown(t: pd.DataFrame) -> str:
    """Tabla markdown sin depender de tabulate."""
    cab = "| " + " | ".join(str(c) for c in t.columns) + " |"
    sep = "|" + "|".join("---" for _ in t.columns) + "|"
    filas = ["| " + " | ".join("" if pd.isna(v) else str(v) for v in r) + " |" for r in t.itertuples(index=False)]
    return "\n".join([cab, sep] + filas)


def tabla_por_grupo(df: pd.DataFrame, col: str) -> pd.DataFrame:
    t = df.groupby(col, as_index=False)[["n", "k"]].sum()
    t["tasa_cef_pct"] = (100 * t["k"] / t["n"]).round(2)
    t["telefonos"] = t["n"].astype(int)
    t["cef"] = t["k"].astype(int)
    return t[[col, "telefonos", "cef", "tasa_cef_pct"]]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--desde", help="primera fecha de corte (AAAA-MM-DD)")
    ap.add_argument("--hasta", help="última fecha de corte (AAAA-MM-DD)")
    ap.add_argument("--cortes-prueba", type=int, default=3, help="últimos cortes que se reservan para medir (def. 3)")
    ap.add_argument("--lambda-l2", type=float, default=1.0, help="penalización L2 (def. 1.0)")
    ap.add_argument("--min-n", type=int, default=1000,
                    help="tramos con menos teléfonos de entrenamiento reciben los puntos del tramo de referencia (def. 1000)")
    ap.add_argument("--guardar", action="store_true", help="escribe la versión en score.PesoVersion/score.Peso (BORRADOR)")
    ap.add_argument("--descripcion", default="Calibración inicial (fase 2)")
    args = ap.parse_args()

    df = leer_datos(args.desde, args.hasta)
    if df.empty:
        sys.exit("No hay datos en score.Caracteristicas (MARCADOS). Ejecute antes score.sp_ArmarEntrenamiento.")
    entidades = leer_entidades()
    df["Entidad"] = df["IdCartera"].map(entidades).fillna("SIN_ENTIDAD")

    cortes = sorted(df["FechaCorte"].unique())
    if len(cortes) <= args.cortes_prueba:
        sys.exit(f"Hay {len(cortes)} cortes; se necesitan más que los {args.cortes_prueba} de prueba.")
    cortes_prueba = set(cortes[-args.cortes_prueba:])
    df["Prueba"] = df["FechaCorte"].isin(cortes_prueba)
    ent, pru = df[~df["Prueba"]].copy(), df[df["Prueba"]].copy()

    # Referencia de cada columna = el tramo con más teléfonos en entrenamiento
    columnas = CARACTERISTICAS + CONTROLES
    referencias = {c: ent.groupby(c)["n"].sum().idxmax() for c in columnas}

    # Tramos chicos: sin peso propio, se ajustan como si fueran el tramo de referencia
    n_por_tramo = {c: ent.groupby(c)["n"].sum() for c in CARACTERISTICAS}
    agrupados = {c: {v for v, n in n_por_tramo[c].items() if n < args.min_n and v != referencias[c]}
                 for c in CARACTERISTICAS}
    ent_fit = ent.copy()
    for c in CARACTERISTICAS:
        if agrupados[c]:
            ent_fit.loc[ent_fit[c].isin(agrupados[c]), c] = referencias[c]

    X_ent, nombres = construir_matriz(ent_fit, columnas, referencias)
    beta = ajustar(X_ent, ent_fit["n"].to_numpy(), ent_fit["k"].to_numpy(), args.lambda_l2)
    coef = {nom: b for nom, b in zip(nombres, beta)}

    # ---- Puntos por tramo (solo características del teléfono) ----
    factor = PUNTOS_POR_DOBLE / math.log(2)
    filas_peso = []
    for col in CARACTERISTICAS:
        niveles = sorted(set(ent[col].unique()) | set(pru[col].unique()))
        crudos = {v: (0.0 if v == referencias[col] else coef.get((col, v), 0.0)) * factor for v in niveles}
        minimo = min(crudos.values())
        estad = ent.groupby(col)[["n", "k"]].sum()
        for v in niveles:
            n_v = float(estad.loc[v, "n"]) if v in estad.index else 0.0
            k_v = float(estad.loc[v, "k"]) if v in estad.index else 0.0
            filas_peso.append({
                "Caracteristica": col, "Tramo": v,
                "Puntos": round(crudos[v] - minimo, 2),
                "Coeficiente": 0.0 if v == referencias[col] else coef.get((col, v), 0.0),
                "N": int(n_v), "TasaExito": (k_v / n_v) if n_v else None,
                "Agrupado": v in agrupados[col] or n_v < args.min_n and v != referencias[col],
            })
        # Fila por defecto: tramos que aparezcan después y que esta versión no conoce
        filas_peso.append({"Caracteristica": col, "Tramo": "*", "Puntos": round(crudos[referencias[col]] - minimo, 2),
                           "Coeficiente": 0.0, "N": 0, "TasaExito": None, "Agrupado": True})
    pesos = pd.DataFrame(filas_peso)
    puntos_max = float(pesos.groupby("Caracteristica")["Puntos"].max().sum())

    def puntuar(d: pd.DataFrame) -> np.ndarray:
        total = np.zeros(len(d))
        for col in CARACTERISTICAS:
            mapa = pesos[pesos["Caracteristica"] == col].set_index("Tramo")["Puntos"]
            total += d[col].map(mapa).fillna(0.0).to_numpy()
        return np.round(100.0 * total / puntos_max) if puntos_max > 0 else total

    for d in (ent, pru):
        d["Score"] = puntuar(d)
        d["ReglaSimple"] = d["T_ULT_CEF"].map(ORDEN_REGLA_SIMPLE).fillna(0)

    # ---- Tramos A…E por quintiles del score en entrenamiento ----
    q = cuantiles_ponderados(ent["Score"].to_numpy(), ent["n"].to_numpy(), [0.2, 0.4, 0.6, 0.8])
    corte_d, corte_c, corte_b, corte_a = q

    def tramo(s):
        return np.where(s >= corte_a, "A", np.where(s >= corte_b, "B", np.where(s >= corte_c, "C",
                        np.where(s >= corte_d, "D", "E"))))

    pru["Tramo"] = tramo(pru["Score"].to_numpy())

    # ---- Deciles (prueba) ----
    cortes_dec = cuantiles_ponderados(pru["Score"].to_numpy(), pru["n"].to_numpy(), [i / 10 for i in range(1, 10)])
    pru["Decil"] = 10 - np.searchsorted(np.array(cortes_dec), pru["Score"].to_numpy(), side="right")  # 1 = mejor

    # ---- Métricas ----
    tasa_base = float(pru["k"].sum() / pru["n"].sum())
    auc_score = auc_dentro_de_cartera(pru, "Score")
    auc_regla = auc_dentro_de_cartera(pru, "ReglaSimple")
    t_tramo = tabla_por_grupo(pru, "Tramo").sort_values("Tramo")
    t_decil = tabla_por_grupo(pru, "Decil").sort_values("Decil")
    t_tramo_ent = pru.groupby(["Entidad", "Tramo"], as_index=False)[["n", "k"]].sum()
    t_tramo_ent["tasa_cef_pct"] = (100 * t_tramo_ent["k"] / t_tramo_ent["n"]).round(2)
    auc_ent = {e: auc_dentro_de_cartera(g, "Score") for e, g in pru.groupby("Entidad")}
    auc_ent_regla = {e: auc_dentro_de_cartera(g, "ReglaSimple") for e, g in pru.groupby("Entidad")}

    tasa_a = float(t_tramo.loc[t_tramo["Tramo"] == "A", "tasa_cef_pct"].iloc[0]) if (t_tramo["Tramo"] == "A").any() else None
    tasa_e = float(t_tramo.loc[t_tramo["Tramo"] == "E", "tasa_cef_pct"].iloc[0]) if (t_tramo["Tramo"] == "E").any() else None

    metricas = {
        "cortes_entrenamiento": [str(c) for c in cortes if c not in cortes_prueba],
        "cortes_prueba": [str(c) for c in sorted(cortes_prueba)],
        "telefonos_entrenamiento": int(ent["n"].sum()),
        "telefonos_prueba": int(pru["n"].sum()),
        "tasa_cef_prueba_pct": round(100 * tasa_base, 2),
        "auc_score_dentro_cartera": round(auc_score, 4) if auc_score else None,
        "auc_regla_simple_dentro_cartera": round(auc_regla, 4) if auc_regla else None,
        "auc_score_por_entidad": {e: (round(a, 4) if a else None) for e, a in auc_ent.items()},
        "auc_regla_por_entidad": {e: (round(a, 4) if a else None) for e, a in auc_ent_regla.items()},
        "tasa_tramo_A_pct": tasa_a, "tasa_tramo_E_pct": tasa_e,
        # Tablas completas de la prueba (las lee la pantalla del generador: detalle del score)
        "tasa_por_tramo": [{"tramo": str(r.Tramo), "telefonos": int(r.telefonos), "cef": int(r.cef),
                            "tasa_cef_pct": float(r.tasa_cef_pct)} for r in t_tramo.itertuples(index=False)],
        "tasa_por_decil": [{"decil": int(r.Decil), "telefonos": int(r.telefonos), "cef": int(r.cef),
                            "tasa_cef_pct": float(r.tasa_cef_pct)} for r in t_decil.itertuples(index=False)],
        "tasa_por_entidad_tramo": [{"entidad": str(r.Entidad), "tramo": str(r.Tramo), "telefonos": int(r.n),
                                    "cef": int(r.k), "tasa_cef_pct": float(r.tasa_cef_pct)}
                                   for r in t_tramo_ent.itertuples(index=False)],
        "lambda_l2": args.lambda_l2, "puntos_por_doble": PUNTOS_POR_DOBLE, "min_n": args.min_n,
        "tramos_agrupados": {c: sorted(v) for c, v in agrupados.items() if v},
        "referencias": referencias,
        "excluidas": ["S_COLOR (sin historial del semáforo)", "F_EQUIVOCADO_DNI (regla de descarte)",
                      "F_NO_EXISTE (sin poder predictivo, diagnóstico 5)"],
    }

    # ---- Informe ----
    salidas = RAIZ / "tools" / "salidas"
    salidas.mkdir(parents=True, exist_ok=True)
    sello = datetime.now().strftime("%Y%m%d_%H%M")
    pesos.to_csv(salidas / f"score_pesos_{sello}.csv", index=False, encoding="utf-8-sig")

    lineas = [
        f"# Calibración del score telefónico · {datetime.now():%d/%m/%Y %H:%M}",
        "",
        "Éxito = CEF (titular o tercero con acuerdo) en la semana siguiente al corte, entre los teléfonos marcados.",
        f"Entrenamiento: {len(metricas['cortes_entrenamiento'])} cortes · {metricas['telefonos_entrenamiento']:,} teléfonos.",
        f"Prueba (fuera del tiempo de entrenamiento): {', '.join(metricas['cortes_prueba'])} · "
        f"{metricas['telefonos_prueba']:,} teléfonos · tasa de CEF {metricas['tasa_cef_prueba_pct']} %.",
        "",
        "## ¿Ordena mejor que una regla simple?",
        "AUC dentro de cada cartera (0,5 = azar, 1 = perfecto). Regla simple = primero el que tuvo CEF más reciente.",
        "",
        "| | Score | Regla simple |",
        "|---|---:|---:|",
        f"| Total | {metricas['auc_score_dentro_cartera']} | {metricas['auc_regla_simple_dentro_cartera']} |",
    ]
    for e in sorted(auc_ent):
        lineas.append(f"| {e} | {metricas['auc_score_por_entidad'][e]} | {metricas['auc_regla_por_entidad'][e]} |")
    lineas += ["", "## Tasa de CEF por tramo (prueba)", "", a_markdown(t_tramo),
               "", f"Cortes de tramo (score mínimo): A {corte_a:.0f} · B {corte_b:.0f} · C {corte_c:.0f} · D {corte_d:.0f}",
               "", "## Tasa de CEF por decil de score (prueba, 1 = mejor)", "", a_markdown(t_decil),
               "", "## Por entidad y tramo (prueba)", "",
               a_markdown(t_tramo_ent.assign(telefonos=t_tramo_ent["n"].astype(int), cef=t_tramo_ent["k"].astype(int))
                          [["Entidad", "Tramo", "telefonos", "cef", "tasa_cef_pct"]]),
               "", "## Puntos por característica", "",
               a_markdown(pesos.assign(TasaExito=(100 * pesos["TasaExito"].astype(float)).round(2))
                    [["Caracteristica", "Tramo", "Puntos", "N", "TasaExito", "Agrupado"]]
                    .rename(columns={"TasaExito": "tasa_cef_pct_entrenamiento"})),
               "", f"Puntos máximos posibles: {puntos_max:.2f} (= score 100).",
               "", "Notas:",
               "- El semáforo (S_COLOR) no entra: solo existe su valor de hoy y depende de las llamadas.",
               f"- Agrupado = tramo con menos de {args.min_n:,} teléfonos de entrenamiento: recibe los puntos del de referencia.",
               "- Tramo * = puntos para un valor que aparezca después y que esta versión no conoce.",
               "- OSIPTEL, WhatsApp y timbrado se usan con su valor de hoy (vienen de validaciones externas).",
               "- La tasa por tramo en entrenamiento es descriptiva; los puntos salen del modelo, que separa el efecto",
               "  de cada característica del de la cartera y de los intentos de esa semana."]
    informe = salidas / f"score_calibracion_{sello}.md"
    informe.write_text("\n".join(lineas), encoding="utf-8")
    print(f"Informe: {informe}")
    print(f"AUC dentro de cartera · score {metricas['auc_score_dentro_cartera']} · regla simple {metricas['auc_regla_simple_dentro_cartera']}")
    print(t_tramo.to_string(index=False))

    if not args.guardar:
        print("Sin --guardar: no se escribió nada en la base.")
        return

    with engine_siscob.begin() as cn:
        version = cn.execute(text("SELECT ISNULL(MAX(Version), 0) + 1 FROM CobAuto.score.PesoVersion")).scalar()
        cn.execute(text("""
            INSERT INTO CobAuto.score.PesoVersion
                (Version, Estado, Descripcion, CorteDesde, CorteHasta, PuntosMaximos,
                 Tramo_A, Tramo_B, Tramo_C, Tramo_D, Metricas)
            VALUES (:v, 'BORRADOR', :d, :cd, :ch, :pm, :a, :b, :c, :dd, :m)"""),
            {"v": version, "d": args.descripcion, "cd": str(cortes[0]), "ch": str(cortes[-1]),
             "pm": round(puntos_max, 2), "a": round(corte_a, 1), "b": round(corte_b, 1),
             "c": round(corte_c, 1), "dd": round(corte_d, 1), "m": json.dumps(metricas, ensure_ascii=False)})
        cn.execute(text("""
            INSERT INTO CobAuto.score.Peso (Version, Caracteristica, Tramo, Puntos, Coeficiente, N, TasaExito)
            VALUES (:v, :c, :t, :p, :co, :n, :te)"""),
            [{"v": version, "c": r.Caracteristica, "t": r.Tramo, "p": float(r.Puntos), "co": float(r.Coeficiente),
              "n": int(r.N), "te": (None if r.TasaExito is None or pd.isna(r.TasaExito) else float(r.TasaExito))}
             for r in pesos.itertuples()])
    print(f"Versión {version} guardada en BORRADOR. Para usarla: EXEC CobAuto.score.sp_PublicarPeso @Version = {version};")


if __name__ == "__main__":
    main()
