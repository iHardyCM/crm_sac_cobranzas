from datetime import date, datetime

import pytest

from app.services import generador_bases_reglas as r
from app.services.generador_bases_reglas import CampoMeta, RecetaInvalida

CAT = {
    "TRAMO": CampoMeta("TRAMO", "Tramo del score", "T", "SCORE", "LISTA", "TRABAJO", "Tramo"),
    "COLOR": CampoMeta("COLOR", "Semáforo", "COL", "TELEFONO", "LISTA", "TRABAJO", "PrioridadColor"),
    "CAPITAL": CampoMeta("CAPITAL", "Capital", "CAP", "CLIENTE", "RANGO", "TRABAJO", "Capital"),
    "CONTACTO_DIRECTO_MES": CampoMeta("CONTACTO_DIRECTO_MES", "Contacto directo en el mes", "CD",
                                      "GESTION_CLIENTE", "SINO", "TRABAJO", "ContactoDirectoMes"),
    "PRODUCTO": CampoMeta("PRODUCTO", "Producto", "PROD", "CLIENTE", "LISTA", "DATO", None),
    "MESES_CASTIGO": CampoMeta("MESES_CASTIGO", "Meses de castigo", "MCAS", "CLIENTE", "RANGO", "DATO", None),
    "FOGAPI": CampoMeta("FOGAPI", "FOGAPI", "FOG", "CLIENTE", "LISTA", "DATO", None, disponible=False),
    "MALO": CampoMeta("MALO", "Columna inventada", "X", "CLIENTE", "LISTA", "TRABAJO", "DNI; DROP TABLE x"),
}


def test_filtro_lista_y_color_plomo():
    c = r.construir_consulta(112, {"filtros": [{"campo": "TRAMO", "valores": ["A", "B"]},
                                               {"campo": "COLOR", "valores": ["PQ", "V"]}]}, CAT, hoy=date(2026, 11, 14))
    assert c.pasos[0] == ("Sin descartados", "t.Descartado = 0")
    assert "t.[Tramo] IN (:p0, :p1)" in c.pasos[1][1]
    assert sorted(v for k, v in c.params.items() if k in ("p2", "p3", "p4")) == ["P", "Q", "V"]
    assert c.params["idcartera"] == 112 and c.ctes == []


def test_filtro_dato_cuenta_es_exists():
    c = r.construir_consulta(112, {"filtros": [{"campo": "PRODUCTO", "valores": ["A1", "SIN_DATO"]}]}, CAT)
    cond = c.pasos[1][1]
    assert "EXISTS (SELECT 1 FROM score.vw_DatoCliente AS d" in cond and "NOT EXISTS" in cond
    assert c.params["p0"] == "PRODUCTO"


def test_rango_y_sino_bit():
    c = r.construir_consulta(112, {"filtros": [{"campo": "CAPITAL", "min": 1000},
                                               {"campo": "MESES_CASTIGO", "max": 24},
                                               {"campo": "CONTACTO_DIRECTO_MES", "valores": ["NO"]}]}, CAT)
    assert "t.[Capital] >=" in c.pasos[1][1] and "<=" not in c.pasos[1][1]
    assert "d.ValorNum <=" in c.pasos[2][1]
    assert "t.[ContactoDirectoMes] IN (:" in c.pasos[3][1]
    assert 0 in c.params.values()


def test_excluir_deja_pasar_sin_dato():
    c = r.construir_consulta(112, {"filtros": [{"campo": "TRAMO", "valores": ["E"], "excluir": True}]}, CAT)
    assert c.pasos[1][0] == "Sin Tramo del score"
    assert c.pasos[1][1].startswith("(CASE WHEN") and c.pasos[1][1].endswith("= 0")


def test_campos_no_disponibles_o_fuera_de_lista_blanca():
    with pytest.raises(RecetaInvalida):
        r.construir_consulta(112, {"filtros": [{"campo": "FOGAPI", "valores": ["SI"]}]}, CAT)
    with pytest.raises(RecetaInvalida):
        r.construir_consulta(112, {"filtros": [{"campo": "NO_EXISTE", "valores": ["x"]}]}, CAT)
    with pytest.raises(RecetaInvalida):
        r.construir_consulta(112, {"filtros": [{"campo": "MALO", "valores": ["x"]}]}, CAT)
    with pytest.raises(RecetaInvalida):
        r.construir_consulta(112, {"filtros": [{"campo": "TRAMO", "valores": []}]}, CAT)


def test_condiciones_del_dia():
    c = r.construir_consulta(112, {"canal": "PRED", "condiciones": {"CEF_HOY": "QUITAR", "PDP_CREADA_HOY": "SOLO",
                                                                    "EQUIVOCADO_HOY": "INDIFERENTE",
                                                                    "ENVIADO_HOY": "QUITAR"}}, CAT,
                             hoy=date(2026, 11, 14))
    etiquetas = [p[0] for p in c.pasos]
    assert etiquetas[1:] == ["Sin contacto directo hoy", "Solo pdp creada hoy", "Sin ya enviado hoy (mismo canal)"]
    assert len(c.ctes) == 3 and c.params["manana"] == date(2026, 11, 15) and c.params["canal"] == "PRED"
    assert "x.Telefono = t.Telefono" in c.pasos[3][1]
    with pytest.raises(RecetaInvalida):
        r.construir_consulta(112, {"condiciones": {"ENVIADO_HOY": "QUITAR"}}, CAT)   # sin canal
    with pytest.raises(RecetaInvalida):
        r.construir_consulta(112, {"condiciones": {"CEF_HOY": "BORRAR"}}, CAT)


def test_pdp_y_pago_reconocen_s_y_si():
    c = r.construir_consulta(112, {"condiciones": {"PDP_VIGENTE": "QUITAR", "PAGO_HOY": "SOLO"}}, CAT)
    sql = "\n".join(c.ctes)
    assert "NOT IN ('SI', 'S')" in sql and "IN ('SI', 'S')" in sql and "cp.FechaPago >= :hoy" in sql
    assert [p[0] for p in c.pasos[1:]] == ["Sin pdp vigente", "Solo pago registrado hoy"]


def test_embudo_acumulado():
    pasos = [("a", "1"), ("b", "1"), ("c", "1")]
    # teléfonos: 5 pasan todo, 2 fallan en a, 3 en b, 1 en c ; clientes: 2 pasan, 1 llega hasta b, 1 falla en a
    filas = [("T", 0, 5), ("T", 1, 2), ("T", 2, 3), ("T", 3, 1), ("C", 0, 2), ("C", 2, 1), ("C", 1, 1)]
    e = r.acumular_embudo(filas, pasos)
    assert [x["telefonos"] for x in e] == [11, 9, 6, 5]
    assert [x["clientes"] for x in e] == [4, 3, 2, 2]


def test_sql_embudo_y_seleccion_usan_los_pasos():
    c = r.construir_consulta(112, {"filtros": [{"campo": "TRAMO", "valores": ["A"]}],
                                   "condiciones": {"CEF_HOY": "QUITAR"}}, CAT)
    e = r.sql_embudo(c)
    assert e.startswith("WITH c_CEF_HOY AS (") and "THEN 3" in e
    s = r.sql_seleccion(c, 2)
    assert "WHERE f.rn <= 2" in s and "sel AS (" in s
    usados = r.solo_parametros_usados(e, dict(c.params, sobra=1))
    assert "sobra" not in usados and "canal" not in usados and "t.IdCartera IN (112)" in e
    assert "g.idCartera IN (112)" in e and "t.IdCartera IN (112)" in s and "1 AS u" in s and "PARTITION BY t.DNI, t.Telefono" not in s


def test_telefonos_por_cliente():
    assert r.telefonos_por_cliente({}) is None
    assert r.telefonos_por_cliente({"telefonos_por_cliente": "3"}) == 3
    with pytest.raises(RecetaInvalida):
        r.telefonos_por_cliente({"telefonos_por_cliente": 0.5 + 100})


def test_nombre_archivo():
    receta = {"filtros": [{"campo": "TRAMO", "valores": ["B", "A"]},
                          {"campo": "CONTACTO_DIRECTO_MES", "valores": ["SI"]},
                          {"campo": "PRODUCTO", "valores": ["A1 PLUS", "OTRO"]}],
              "condiciones": {"PDP_VIGENTE": "QUITAR", "CEF_HOY": "INDIFERENTE"}}
    piezas = r.resumen_receta(receta, CAT)
    assert piezas == ["A-B", "CD", "PROD", "SINPDPV"]
    nombre = r.nombre_archivo(112, datetime(2026, 11, 14, 9, 42), "PRED", piezas, "B124")
    # 43 caracteres no caben en 40: se quita la última pieza del resumen, nunca el código
    assert nombre == "112_1411-0942_PRED_A-B_CD_PROD_B124"
    assert r.nombre_archivo(112, datetime(2026, 11, 14, 9, 42), "PRED", piezas, "B124", largo=60).endswith("_SINPDPV_B124")
    assert len(nombre) <= 40


def test_nombre_recorta_resumen_nunca_el_codigo():
    piezas = ["UNOLARGO", "DOSLARGO", "TRESLARGO", "CUATROLARGO"]
    nombre = r.nombre_archivo(7, datetime(2026, 1, 2, 3, 4), "SMS", piezas, "B123456")
    assert nombre.startswith("007_0201-0304_SMS_") and nombre.endswith("_B123456") and len(nombre) <= 40


def test_segmentadores_cuentan_sin_el_filtro_propio():
    c = r.construir_consulta(112, {"filtros": [{"campo": "TRAMO", "valores": ["A"]},
                                               {"campo": "PRODUCTO", "valores": ["A1"]}],
                                   "condiciones": {"CEF_HOY": "QUITAR"}}, CAT, hoy=date(2026, 11, 14))
    assert c.campos_paso == [None, "TRAMO", "PRODUCTO", None]
    donde_sin_tramo = r.sql_donde(c, sin_campo="TRAMO")
    assert "t.[Tramo]" not in donde_sin_tramo and "vw_DatoCliente" in donde_sin_tramo and "c_CEF_HOY" in donde_sin_tramo
    cat = {k: v for k, v in CAT.items() if k != "MALO"}
    plan = r.plan_conteos(c, cat)
    # Todo sale de la temporal #gb_a: TRAMO (paso 1) se cuenta sin su propio paso; COLOR con todos los pasos
    assert "N'TRAMO'" in plan["trabajo"] and "a.Fallo IN (0, 2)" in plan["trabajo"]
    # Los campos sin filtro propio se cuentan en UNA pasada por nivel (CROSS APPLY VALUES): teléfonos y clientes
    assert "N'PQ'" in plan["trabajo"] and "CROSS APPLY (VALUES" in plan["trabajo"] and "GROUPING SETS" not in plan["trabajo"]
    assert "SELECT DISTINCT a.DNI" in plan["trabajo"]   # CONTACTO_DIRECTO_MES: una fila por cliente
    assert plan["trabajo"].count("FROM #gb_a AS a WHERE a.Fallo = 0") == 2
    assert "vw_BaseTrabajo" not in plan["trabajo"]
    # PRODUCTO (paso 2): clientes que cumplen todo menos su paso, con "Sin dato"
    prod = [x for x in plan["dato"] if "N'PRODUCTO'" in x][0]
    assert "a.Fallo IN (0, 4)" in prod and "SIN_DATO" in prod
    assert plan["dato_comun"] == ["MESES_CASTIGO"]   # FOGAPI no disponible, PRODUCTO filtrado
    assert any("N'MESES_CASTIGO'" in x and "d.ValorNum < 7.0" in x for x in plan["dato"])
    assert "N'CAPITAL'" in plan["trabajo"] and "N'20,000+'" in plan["trabajo"]
    assert ":" not in plan["preparar"]


def test_lectura_unica_con_mascara():
    c = r.construir_consulta(112, {"filtros": [{"campo": "TRAMO", "valores": ["A"]}],
                                   "condiciones": {"CEF_HOY": "QUITAR"}}, CAT, hoy=date(2026, 11, 14))
    tmp = r.sql_materializar(c)
    # Las temporales se crean sin parámetros (pyodbc + sp_prepexec las borraría) y luego se llenan
    assert tmp[1].startswith("CREATE TABLE #c_CEF_HOY (DNI VARCHAR(50)") and ":" not in tmp[1]
    assert tmp[2].startswith("INSERT INTO #c_CEF_HOY (DNI) SELECT DISTINCT") and ":hoy" in tmp[2]
    assert "TOP 0 t.*, CAST(0 AS BIGINT) AS Fallo INTO #gb_a" in tmp[4] and ":" not in tmp[4]
    lectura = tmp[5]
    assert lectura.startswith("INSERT INTO #gb_a") and "WHERE t.IdCartera IN (112)" in lectura and "WITH" not in lectura
    assert not any("DELETE" in x for x in tmp)          # una sola cartera: no se quitan repetidos
    assert "FROM #c_CEF_HOY AS x" in lectura and "FROM c_CEF_HOY" not in lectura
    assert "CAST(1 AS BIGINT)" in lectura and "CAST(2 AS BIGINT)" in lectura and "CAST(4 AS BIGINT)" in lectura
    assert "DROP TABLE #c_ENVIADO_HOY" in tmp[0]
    emb = r.sql_embudo_temp(c)
    assert "Fallo % 2 = 0" in emb and "Fallo % 8 = 0" in emb
    salida = r.embudo_desde_fila([100, 50, 90, 45, 30, 20, 25, 18], c.pasos)
    assert salida[0] == {"paso": "Teléfonos de la cartera", "telefonos": 100, "clientes": 50}
    assert salida[-1]["paso"] == "Sin contacto directo hoy" and salida[-1]["telefonos"] == 25
    sel = r.sql_seleccion_temp(2)
    assert "FROM #gb_a AS a WHERE a.Fallo = 0" in sel and "WHERE f.rn <= 2" in sel


def test_campo_repetido_en_la_receta():
    with pytest.raises(RecetaInvalida):
        r.construir_consulta(112, {"filtros": [{"campo": "TRAMO", "valores": ["A"]},
                                               {"campo": "TRAMO", "valores": ["B"]}]}, CAT)


def test_rangos_y_fechas_se_filtran_por_tramos_marcados():
    c = r.construir_consulta(112, {"filtros": [{"campo": "CAPITAL", "valores": ["0 – 499.99", "20,000+", "SIN_DATO"]},
                                               {"campo": "MESES_CASTIGO", "valores": ["13–24"]}]}, CAT)
    cap, mcas = c.pasos[1][1], c.pasos[2][1]
    assert "CASE WHEN t.[Capital] IS NULL THEN NULL WHEN t.[Capital] < 500.0 THEN N'0 – 499.99'" in cap
    assert "IN (:p0, :p1)" in cap and "t.[Capital] IS NULL" in cap
    assert "EXISTS (SELECT 1 FROM score.vw_DatoCliente" in mcas and "d.ValorNum < 13.0 THEN N'7–12'" in mcas
    assert r.tramos_de(CAT["CAPITAL"])[-1] == "20,000+"
    assert r.tramos_de(CampoMeta("SCORE", "Score", "SC", "SCORE", "RANGO", "TRABAJO", "Score"))[0] == "90–100"
    assert r._enteros(0, 1, 4, 11, 31) == [("0", 1.0), ("1–3", 4.0), ("4–10", 11.0), ("11–30", 31.0), ("31+", None)]
    nombre = r.resumen_receta({"filtros": [{"campo": "MESES_CASTIGO", "valores": ["13–24"]}]}, CAT)
    assert nombre == ["MCAS1324"]


def test_sql_grupos_una_lectura_por_nivel():
    cat = {
        "MG_CONTACTO_MES": r.CampoMeta("MG_CONTACTO_MES", "Mejor contacto", "MGC", "GESTION_CLIENTE", "LISTA", "TRABAJO", "MgContacto"),
        "COBERTURA_MES": r.CampoMeta("COBERTURA_MES", "Cobertura", "COB", "GESTION_CLIENTE", "SINO", "TRABAJO", "Cobertura"),
        "FRECUENCIA_MES": r.CampoMeta("FRECUENCIA_MES", "Frecuencia", "FRE", "GESTION_CLIENTE", "RANGO", "TRABAJO", "Frecuencia"),
        "MG_TEL_6M": r.CampoMeta("MG_TEL_6M", "Mejor 6m", "MGT6", "GESTION_TELEFONO", "LISTA", "TRABAJO", "MgTel6m"),
        "GESTIONES_TEL_MES": r.CampoMeta("GESTIONES_TEL_MES", "Gestiones mes", "GTM", "GESTION_TELEFONO", "RANGO", "TRABAJO", "GestionesTelMes"),
    }
    assert r.cuenta_telefonos(cat["MG_TEL_6M"]) and not r.cuenta_telefonos(cat["MG_CONTACTO_MES"])
    assert r.tramos_de(cat["FRECUENCIA_MES"]) == ["0", "1", "2–3", "4–7", "8–15", "16+"]
    c = r.construir_consulta(112, {"filtros": [{"campo": "MG_TEL_6M", "valores": ["TITULAR"]},
                                               {"campo": "COBERTURA_MES", "valores": ["0"]}]}, cat, hoy=date(2026, 11, 16))
    donde = r.sql_donde(c)
    assert "t.[MgTel6m] IN" in donde and "t.[Cobertura] IN" in donde
    plan = r.plan_conteos(c, cat)
    t = plan["trabajo"]
    # Libres: GESTIONES_TEL_MES (teléfonos) y MG_CONTACTO_MES + FRECUENCIA_MES (clientes), una lectura cada nivel
    assert t.count("CROSS APPLY (VALUES") == 2 and "N'GESTIONES_TEL_MES'" in t and "N'FRECUENCIA_MES'" in t
    assert "(N'MG_CONTACTO_MES', CONVERT(NVARCHAR(200), x.v0)), (N'FRECUENCIA_MES', CONVERT(NVARCHAR(200), x.v1))" in t
    # Con filtro propio: aparte, sin su paso
    assert "N'MG_TEL_6M' AS Campo" in t and "COUNT(DISTINCT a.DNI)" in t   # COBERTURA_MES: clientes sin su paso
    sql = r.sql_grupos([cat["MG_CONTACTO_MES"]], "score.vw_BaseTrabajo AS a WHERE a.IdCartera = :id", por_cliente=False)
    assert sql == ("SELECT u.Campo, u.Valor, COUNT(*) AS N FROM (SELECT CONVERT(NVARCHAR(200), a.[MgContacto]) AS v0 FROM "
                   "score.vw_BaseTrabajo AS a WHERE a.IdCartera = :id) AS x CROSS APPLY (VALUES "
                   "(N'MG_CONTACTO_MES', CONVERT(NVARCHAR(200), x.v0))) AS u (Campo, Valor) GROUP BY u.Campo, u.Valor")
    assert r.sql_grupos([], "x", True) == ""


def test_cartera_combinada_lee_ambas_y_deja_un_telefono():
    c = r.construir_consulta(901, {"filtros": [{"campo": "PRODUCTO", "valores": ["A1"]}], "canal": "PRED",
                                   "condiciones": {"CEF_HOY": "QUITAR", "ENVIADO_HOY": "QUITAR"}},
                             CAT, hoy=date(2026, 11, 16), carteras=[126, 128])
    assert c.combinada and c.carteras == [126, 128]
    tmp = r.sql_materializar(c)
    assert "WHERE t.IdCartera IN (126, 128)" in tmp[-3]
    assert tmp[-2].startswith("WITH x AS") and "PARTITION BY DNI, Telefono" in tmp[-2] and "Fallo = 0" in tmp[-2]
    assert any("g.idCartera IN (126, 128)" in x for x in tmp)
    assert any("d.IdCartera IN (126, 128)" in x for x in tmp)       # enviado hoy: por la cartera de cada fila
    # el dato se cruza por la cartera de la fila, no por la cartera elegida
    assert "d.IdCartera = t.IdCartera" in c.pasos[1][1]
    plan = r.plan_conteos(c, CAT)
    assert "IdCartera, DNI INTO #gb_c" in plan["preparar"]
    assert all("u.IdCartera = d.IdCartera" in x for x in plan["dato"] + plan["con_dato"])
    assert ":idcartera" not in " ".join(plan["dato"] + plan["con_dato"] + [plan["trabajo"]])
    s = r.sql_seleccion(c, None)
    assert "PARTITION BY t.DNI, t.Telefono ORDER BY t.Score DESC, t.IdCartera" in s and "WHERE t.u = 1" in s
    with pytest.raises(RecetaInvalida):
        r.lista_carteras([])


# ---- Fase 12 (20/11/2026): condiciones del día desde la foto score.CondicionDia ----

def test_refrescar_condicion_por_cartera():
    pdp = r.sql_refrescar_condicion("PDP_VIGENTE", 112)
    assert pdp[0] == "DELETE FROM score.CondicionDia WHERE Codigo = N'PDP_VIGENTE' AND IdCartera = 112;"
    assert pdp[1].startswith("INSERT INTO score.CondicionDia (Codigo, IdCartera, Fecha, DNI, Telefono) "
                             "SELECT N'PDP_VIGENTE', 112, :hoy, x.DNI, NULL FROM (SELECT DISTINCT")
    assert "cl.IdCartera IN (112)" in pdp[1] and pdp[1].endswith(") AS x;")
    equivocado = r.sql_refrescar_condicion("EQUIVOCADO_HOY", 126)
    assert "x.DNI, x.Telefono FROM" in equivocado[1] and "g.idCartera IN (126)" in equivocado[1]
    with pytest.raises(RecetaInvalida):
        r.sql_refrescar_condicion("ENVIADO_HOY", 112)   # depende del canal: sigue en vivo


def test_vista_previa_lee_condiciones_de_la_foto():
    c = r.construir_consulta(126, {"canal": "PRED", "condiciones": {"PDP_VIGENTE": "QUITAR", "ENVIADO_HOY": "QUITAR"}},
                             CAT, hoy=date(2026, 11, 20), carteras=[126, 128])
    assert r.condiciones_usadas(c) == ["PDP_VIGENTE", "ENVIADO_HOY"]
    tmp = r.sql_materializar(c, condiciones_cache=True)
    pdp = [x for x in tmp if x.startswith("INSERT INTO #c_PDP_VIGENTE")][0]
    assert ("SELECT DISTINCT DNI FROM score.CondicionDia WHERE Codigo = N'PDP_VIGENTE' "
            "AND IdCartera IN (126, 128) AND Fecha = :hoy") in pdp
    assert "COMPROMISO" not in pdp
    enviado = [x for x in tmp if x.startswith("INSERT INTO #c_ENVIADO_HOY")][0]
    assert "score.BaseDetalle" in enviado          # en vivo
    # Sin caché (antes de ejecutar la fase 12) todo sigue igual que antes
    assert "COMPROMISO" in [x for x in r.sql_materializar(c) if x.startswith("INSERT INTO #c_PDP_VIGENTE")][0]


# ---------------------------------------------------------------- nombre de la base (24/11/2026)
M = datetime(2026, 11, 24, 12, 49)


def _n(filtros, cartera="112", canal=None):
    return r.nombre_legible(cartera, canal, {"filtros": filtros}, {}, M)


def test_nombre_ejemplo_de_hardy():
    filtros = [
        {"campo": "RANGO_CAPITAL", "valores": ["1. [0 - 499.99]", "2. [500 - 999.99]", "0. SIN INFORMACION"], "excluir": True},
        {"campo": "MG_CONTACTO_MES", "valores": ["CEF"], "excluir": True},
        {"campo": "TRAMO", "valores": ["A", "B"]},
        {"campo": "TIMBRA", "valores": ["2", "4"]},
        {"campo": "OSIPTEL", "valores": ["NO"], "excluir": True},
        {"campo": "SEGMENTO", "valores": ["X"]},                          # lo propio de la cartera no va
    ]
    assert _n(filtros) == "112 2411 1249 K MAYOR 1K NOC SCORE AB TIM 24 OSIPTEL"
    assert _n(filtros, canal="PRED") == "112 2411 1249 PRD K MAYOR 1K NOC SCORE AB TIM 24 OSIPTEL"


def test_nombre_tipo_de_base_corto():
    assert _n([], canal="PREVIEW") == "112 2411 1249 PRV MIX CONTACTO MIX SCORE"
    assert _n([], canal="IVR").startswith("112 2411 1249 TTS ")
    assert _n([], canal="SMS").startswith("112 2411 1249 SMS ")


def test_nombre_capital():
    assert _n([{"campo": "RANGO_CAPITAL", "valores": ["1. [0 - 499.99]"], "excluir": True}]).startswith("112 2411 1249 K MAYOR 500 ")
    menor = [{"campo": "RANGO_CAPITAL", "valores": ["7. [20,000+]"], "excluir": True}]
    assert "K MENOR 20K" in _n(menor)
    medio = [{"campo": "RANGO_CAPITAL", "valores": ["3. [1,000 - 2,499.99]", "4. [2,500 - 4,999.99]"]}]
    assert "K 1K-5K" in _n(medio)
    assert "K MIX" in _n([{"campo": "RANGO_CAPITAL", "valores": ["1. [0 - 499.99]", "7. [20,000+]"]}])
    assert " K " not in _n([])


def test_nombre_capital_sac():
    sac = [{"campo": "RANGO_CAPITAL_SAC", "valores": ["1. [0 - 499.99]", "NO ESTÁ EN SAC", "0. SIN INFORMACION"], "excluir": True}]
    assert _n(sac).startswith("112 2411 1249 K MAYOR 500 ")


def test_nombre_contacto_y_score():
    assert _n([]) == "112 2411 1249 MIX CONTACTO MIX SCORE"
    assert "CEF MES" in _n([{"campo": "MG_CONTACTO_MES", "valores": ["CEF"]}])
    assert "MIX CONTACTO" in _n([{"campo": "MG_CONTACTO_MES", "valores": ["SG"], "excluir": True}])
    hist = [{"campo": "MG_CONTACTO_MES", "valores": ["CEF"], "excluir": True},
            {"campo": "MG_TEL_6M", "valores": ["TITULAR", "TERCERO_ACUERDO"]}]
    assert "CEF HIST" in _n(hist)
    assert "SCORE ABC" in _n([{"campo": "TRAMO", "valores": ["D", "E"], "excluir": True}])
    assert "MIX SCORE" in _n([{"campo": "TRAMO", "valores": ["A", "B", "C", "D", "E"]}])


def test_nombre_pdp_y_seguimiento_caidos():
    assert _n([{"campo": "ESTADO_PDP", "valores": ["CAÍDA"]}, {"campo": "TRAMO", "valores": ["A"]}]) == "112 2411 1249 PDP CAIDA MES SCORE A"
    hist = [{"campo": "ESTADO_PDP", "valores": ["SIN PDP"]}, {"campo": "PDP_ANTERIOR", "valores": ["CAÍDA"]}]
    assert "PDP CAIDA HIST" in _n(hist)
    caido = {"campo": "SEGUIMIENTO_ACTUAL", "valores": ["CAÍDO"]}
    assert "SEG CAIDO MES" in _n([caido, {"campo": "SEGUIMIENTO_MES", "valores": ["Este mes"]}])
    assert "SEG CAIDO HIST" in _n([caido, {"campo": "SEGUIMIENTO_MES", "valores": ["Este mes"], "excluir": True}])
    assert _n([caido]).endswith("SEG CAIDO MIX SCORE")
    # quitar PAGADA y VIGENTE no es "PDP caída": sigue el contacto
    assert "MIX CONTACTO" in _n([{"campo": "ESTADO_PDP", "valores": ["PAGADA", "VIGENTE"], "excluir": True}])


def test_nombre_osiptel_timbrado_semaforo():
    assert _n([{"campo": "OSIPTEL", "valores": ["SI", "SV"]}]).endswith("OSIPTEL")
    assert _n([{"campo": "OSIPTEL", "valores": ["NO"]}]).endswith("OSP NO")
    assert _n([{"campo": "TIMBRA", "valores": ["0", "1"], "excluir": True}]).endswith("TIM 234")
    assert _n([{"campo": "COLOR", "valores": ["A", "PQ", "V"]}]).endswith("SEM APV")
    assert _n([{"campo": "COLOR", "valores": ["R", "F"], "excluir": True}]).endswith("SEM VTAP")


def test_nombre_combinada_abreviatura_tras_la_fecha():
    propuesta = r.nombre_legible("126 VIGMIX", "PRED", {"filtros": []}, {}, M)
    assert propuesta == "126 2411 1249 PRD VIGMIX MIX CONTACTO MIX SCORE"
    assert r.nombre_final(propuesta, "126", "B60", datetime(2026, 11, 24, 13, 0)) == "126 2411 1300 PRD VIGMIX MIX CONTACTO MIX SCORE B60"


def test_nombre_final_fecha_de_generacion_y_codigo():
    g = datetime(2026, 11, 24, 12, 53)
    assert r.nombre_final("112 2411 1249 K MAYOR 1K NOC SCORE AB", "112", "B51", g) == "112 2411 1253 K MAYOR 1K NOC SCORE AB B51"
    assert r.nombre_final("noc score a", "112", "B52", g) == "112 2411 1253 NOC SCORE A B52"
    assert r.nombre_final("112 2411 1249 SCORE A B99", "112", "B53", g) == "112 2411 1253 SCORE A B53"
    assert r.nombre_final("112 pred déf/perd, cap | x", "112", "B54", g) == "112 2411 1253 PRED DEF PERD CAP X B54"
    largo = r.nombre_final("112 " + "X" * 300, "112", "B999", g)
    assert len(largo) <= 120 and largo.endswith(" B999")


def test_enviado_hoy_agrupa_predictivo_y_preview():
    assert "b.Canal IN ('PRED', 'PREVIEW')" in r._SQL_CONDICION["ENVIADO_HOY"]
    assert "PREVIEW" in r.CANALES and r.CANALES_MARCADOR == ("PRED", "PREVIEW")


def test_zonas_restringidas_paso_forzado():
    """Zonas (27/11/2026): con zonas vigentes, «Sin zona restringida» va justo después de los descartados."""
    catalogo = {}
    sin = r.construir_consulta(117, {"filtros": []}, catalogo)
    con = r.construir_consulta(117, {"filtros": []}, catalogo, zonas=True)
    assert [p[0] for p in sin.pasos] == ["Sin descartados"]
    assert [p[0] for p in con.pasos] == ["Sin descartados", "Sin zona restringida"]
    assert "score.vw_ClienteZonaRestringida" in r.sql_donde(con)
    assert len(con.campos_paso) == len(con.pasos)
