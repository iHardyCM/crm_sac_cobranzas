import pytest

from app.services import generador_rendimiento_service as r


def test_sql_una_lectura_con_grouping_sets_y_filtros_parametrizados():
    sql, params = r.sql_rendimiento([126, 128], "BASES", {"Osiptel": ["1", "LN"], "Tramo": ["D", "E"]})
    assert "IdCartera IN (126, 128)" in sql
    assert "Canal <> 'SIN BASE'" in sql
    assert "GROUPING SETS ((Tramo), (Orden, Tramo)" in sql and "(Fecha, Tramo)" in sql
    assert "Osiptel IN (:f0_0, :f0_1)" in sql and "Tramo IN (:f1_0, :f1_1)" in sql
    assert params == {"f0_0": "1", "f0_1": "LN", "f1_0": "D", "f1_1": "E"}
    assert "'LN'" not in sql          # los valores nunca van pegados al SQL


def test_cartera_no_filtra_canal():
    sql, _ = r.sql_rendimiento([112], "CARTERA", {})
    assert "SIN BASE" not in sql.split("FROM score.RendimientoDia")[1]


def test_filtros_invalidos():
    with pytest.raises(r.ConsultaInvalida):
        r._filtros_validos({"DNI": ["1"]})
    with pytest.raises(r.ConsultaInvalida):
        r._filtros_validos({"Tramo": "A"})
    assert r._filtros_validos({"Tramo": ["A", "", None]}) == {"Tramo": ["A"]}
    assert r._filtros_validos({"Tramo": []}) == {}


def test_cobertura_sin_filtros_no_une_bases_ni_atributos():
    sql, params = r.sql_cobertura([126], "CARTERA", {})
    assert "score.BaseDetalle" not in sql and "score.Caracteristicas" not in sql
    assert "COUNT(*) AS TelefonosDistintos" in sql and params == {}


def test_cobertura_bases_y_atributos_parametrizados():
    sql, params = r.sql_cobertura([126, 128], "BASES", {"Osiptel": ["SI"], "Tramo": ["A"], "Orden": ["1"]})
    assert "IdCartera IN (126, 128)" in sql
    assert "b.Canal IS NOT NULL" in sql and "score.BaseDetalle" in sql
    assert "ISNULL(c.S_OSIPTEL, 'SIN_DATO') IN (:c1_0)" in sql
    assert "p.Tramo IN (:c2_0)" in sql and "p.Orden IN (:c0_0)" in sql
    assert params == {"c0_0": "1", "c1_0": "SI", "c2_0": "A"}


def test_cobertura_clasifica_por_que_no_se_llamo():
    sql, _ = r.sql_cobertura([112], "CARTERA", {})
    assert "gc.EstadoPdp IN (N'VIGENTE', N'PAGADA')" in sql
    assert "SinLlamadaCliente" in sql and "ClientesSinLlamada" in sql
