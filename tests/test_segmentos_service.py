import pandas as pd
import pytest

from app.services.segmentos_service import (
    CargaInvalida, ColumnaSegmento, DefinicionCarga, clave_codigo_banco, clave_dni, formatear, preparar,
)


def _def(**extra):
    base = dict(entidad="MIBANCO", segmento="Prueba", columna_clave="CO_CLIENTE", tipo_clave="CODIGO_BANCO",
                columna_periodo="PERIODO", filtros={"FUNCIONARIO": ["BIZNESCOB"]},
                columnas=[ColumnaSegmento("SEG", "SEG_X", "Segmento", "SGX", "Prueba")])
    base.update(extra)
    return DefinicionCarga(**base)


def test_clave_y_formato():
    assert clave_codigo_banco("10342994.0") == "10342994" and clave_codigo_banco("abc") is None
    assert formatear("0.97", "PORCENTAJE") == "97%" and formatear("97%", "PORCENTAJE") == "97%"
    assert formatear("0.925", "PORCENTAJE") == "92.5%" and formatear("  T.A ", "TEXTO") == "T.A"


def test_preparar_filtra_y_detecta_conflictos():
    df = pd.DataFrame({"PERIODO": ["202611"] * 4, "CO_CLIENTE": ["1.0", "1", "2", "3"],
                       "FUNCIONARIO": ["BIZNESCOB", "BIZNESCOB", "IBR", "BIZNESCOB"], "SEG": ["G1", "G2", "G1", "T.A"]})
    p = preparar(df, _def())
    assert p["filas_filtradas"] == 3 and set(p["valores"]) == {"1", "3"}
    assert p["conflictos"] == [{"clave": "1", "campo": "SEG_X", "valores": ["G1", "G2"]}]


def test_mismo_valor_repetido_no_es_conflicto_y_periodo_unico():
    df = pd.DataFrame({"PERIODO": ["202611", "202611"], "CO_CLIENTE": ["5", "5"], "FUNCIONARIO": ["BIZNESCOB"] * 2,
                       "SEG": ["G1", "G1"]})
    assert preparar(df, _def())["conflictos"] == []
    df.loc[1, "PERIODO"] = "202610"
    with pytest.raises(CargaInvalida):
        preparar(df, _def())


def test_definicion_desde_dict_valida_lo_que_manda_la_pantalla():
    from app.services.segmentos_service import definicion_desde_dict
    base = {"entidad": "mibanco", "segmento": "Prueba", "columna_clave": "CO_CLIENTE", "tipo_clave": "CODIGO_BANCO",
            "periodo": "202611", "filtros": [{"columna": "FUNCIONARIO", "valores": ["BIZNESCOB"]}, {"columna": "X", "valores": []}],
            "columnas": [{"columna": "SEG", "campo": "seg_x", "abreviatura": "sgx", "formato": "texto"}]}
    d = definicion_desde_dict(base)
    assert d.entidad == "MIBANCO" and d.columnas[0].campo == "SEG_X" and d.columnas[0].abreviatura == "SGX"
    assert d.filtros == {"FUNCIONARIO": ["BIZNESCOB"]} and d.periodo == "202611"
    for malo in ({"campo": "1ABC"}, {"abreviatura": "MUY_LARGA_ABREV"}):
        datos = dict(base, columnas=[dict(base["columnas"][0], **malo)])
        with pytest.raises(CargaInvalida):
            definicion_desde_dict(datos)
    with pytest.raises(CargaInvalida):
        definicion_desde_dict(dict(base, periodo="2026-11"))


def test_analizar_archivo_y_codigo_sugerido():
    import io
    from app.services.segmentos_service import analizar_archivo, codigo_sugerido
    assert codigo_sugerido("Gestion Prio") == "GESTION_PRIO" and codigo_sugerido("% META") == "META"
    buf = io.BytesIO()
    pd.DataFrame({"CO_CLIENTE": [1, 2, 3], "SEG": ["G1", "G1", "T.A"]}).to_excel(buf, index=False, sheet_name="DATA")
    r = analizar_archivo(buf.getvalue(), "x.xlsx")
    assert r["hojas"] == ["DATA"] and r["filas"] == 3
    seg = next(c for c in r["columnas"] if c["nombre"] == "SEG")
    assert seg["distintos"] == 2 and seg["valores"][0] == {"valor": "G1", "filas": 2}


def test_periodo_desde_fecha_y_vacios_nan():
    from app.services.segmentos_service import periodo_aaaamm, _texto
    assert periodo_aaaamm("2026-11-15 00:00:00") == "202611" and periodo_aaaamm("202611.0") == "202611"
    assert periodo_aaaamm("15/11/2026") == "202611" and periodo_aaaamm("2026/11") == "202611"
    assert periodo_aaaamm("noviembre") is None and _texto("nan") is None and _texto(" NaN ") is None
    df = pd.DataFrame({"PERIODO": ["2026-11-15 00:00:00", "2026-11-01"], "CO_CLIENTE": ["1", "2"],
                       "FUNCIONARIO": ["BIZNESCOB"] * 2, "SEG": ["G1", "nan"]})
    p = preparar(df, _def())
    assert p["periodo"] == "202611" and p["valores"]["2"]["SEG_X"] is None


def test_clave_dni_recupera_cero_de_excel():
    assert clave_dni(1234567) == "01234567"
    assert clave_dni("1234567.0") == "01234567"
    assert clave_dni(" 45678901 ") == "45678901"
    assert clave_dni("001234567") == "001234567"     # CE de 9 dígitos: no se recorta
    assert clave_dni("ce12345") == "CE12345"
    assert clave_dni("nan") is None
