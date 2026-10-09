from app.services.nombres_descarga import nombre_descarga

IND = {"tipo": "INDIVIDUAL", "meta": {"agente": "19805651 - FANNY VASQUEZ",
       "cartera": "132 - FINANCIERA OH", "fecha": "2026-10-07T12:11:00"}}


def test_individual():
    assert nombre_descarga(IND, "INDIVIDUAL", "pdf") == "Informe_Llamada_FANNY_VASQUEZ_FINANCIERA_OH_20261007.pdf"


def test_individual_tildes_y_simbolos():
    p = {"meta": {"agente": "1 - Ñandú / Pérez", "cartera": "x", "fecha": "07/10/2026"}}
    assert nombre_descarga(p, "INDIVIDUAL", "rtf") == "Informe_Llamada_Nandu_Perez_x_20261007.rtf"


def test_individual_sin_datos_no_inventa():
    assert nombre_descarga({"meta": {}}, "INDIVIDUAL", "pdf") == "Informe_Llamada.pdf"


def test_cartera_una_cartera_rango():
    p = {"evaluaciones": [{"cartera": "132 - FINANCIERA OH", "fecha": "2026-10-01"},
                          {"cartera": "132 - FINANCIERA OH", "fecha": "2026-10-08 10:00"}]}
    assert nombre_descarga(p, "CARTERA", "pdf") == "Informe_Calidad_FINANCIERA_OH_20261001_a_20261008.pdf"
    assert nombre_descarga(p, "CARTERA", "xlsx", excel=True) == "Reporte_Calidad_FINANCIERA_OH_20261001_a_20261008.xlsx"


def test_cartera_varias_y_un_dia():
    p = {"evaluaciones": [{"cartera": "A", "fecha": "2026-10-01"}, {"cartera": "B", "fecha": "2026-10-01"}]}
    assert nombre_descarga(p, "CARTERA", "pdf") == "Informe_Calidad_Varias_carteras_20261001.pdf"
