"""Zonas restringidas: validación del formulario del mapa y escritura en score.ZonaRestringida."""
from datetime import date

import pytest

from app.services import zonas_restringidas_service as z

HOY = date(2026, 11, 27)


def _cuerpo(**kw):
    base = {"departamentos": ["Piura"], "todas": True, "origen": "BANCO",
            "motivo": "Interbank 27/11: detener gestión", "desde": "2026-11-27"}
    base.update(kw)
    return base


def test_normaliza_tildes_y_espacios():
    assert z.normalizar(" San  Martín ") == "SAN MARTIN"
    assert z.normalizar("apurímac") == "APURIMAC"


def test_los_25_departamentos_coinciden_con_el_mapa():
    assert len(z.DEPARTAMENTOS) == 25 and len(set(z.DEPARTAMENTOS)) == 25


def test_validar_todas_las_carteras():
    d = z.validar_registro(_cuerpo(departamentos=["Piura", "TUMBES", "piura"]), hoy=HOY)
    assert d["departamentos"] == ["PIURA", "TUMBES"]
    assert d["todas"] is True and d["carteras"] == []
    assert d["desde"] == HOY and d["hasta"] is None


def test_validar_carteras_elegidas():
    d = z.validar_registro(_cuerpo(todas=False, carteras=["137", 117, 117]), hoy=HOY)
    assert d["carteras"] == [117, 137]


@pytest.mark.parametrize("cambio, mensaje", [
    ({"departamentos": []}, "al menos un departamento"),
    ({"departamentos": ["LIMA METROPOLITANA"]}, "no es un departamento"),
    ({"todas": False, "carteras": []}, "Elige las carteras"),
    ({"motivo": "  "}, "motivo"),
    ({"origen": "OTRO"}, "origen"),
    ({"hasta": "2026-11-20", "desde": "2026-11-01"}, "ya pasó"),
    ({"desde": "2026-12-10", "hasta": "2026-12-01"}, "anterior"),
    ({"desde": "27/11/2026"}, "no es válida"),
])
def test_validar_rechaza(cambio, mensaje):
    with pytest.raises(z.ZonaInvalida, match=mensaje):
        z.validar_registro(_cuerpo(**cambio), hoy=HOY)


class _Res:
    def __init__(self, filas=None, escalar=None, rowcount=1):
        self._filas, self._escalar, self.rowcount = filas or [], escalar, rowcount

    def mappings(self):
        return self

    def first(self):
        return self._filas[0] if self._filas else None

    def all(self):
        return self._filas

    def scalar(self):
        return self._escalar


class _Conn:
    """Responde según el texto del SQL; guarda cada sentencia con sus parámetros."""
    def __init__(self, existente=None, rowcount_cartera=1):
        self.existente, self.rowcount_cartera, self.sql = existente, rowcount_cartera, []

    def execute(self, sql, params=None):
        s = str(sql)
        self.sql.append((s, params))
        if "SELECT TOP (1) IdZona" in s:
            return _Res([self.existente] if self.existente else [])
        if "INSERT INTO score.ZonaRestringida (" in s:
            return _Res(escalar=50)
        if "INSERT INTO score.ZonaRestringidaCartera" in s:
            return _Res(rowcount=self.rowcount_cartera)
        return _Res()


def test_registrar_nueva_para_todas():
    conn = _Conn()
    datos = z.validar_registro(_cuerpo(departamentos=["Tumbes"]), hoy=HOY)
    r = z.registrar(conn, datos, "71234567")
    assert r == [{"IdZona": 50, "Departamento": "TUMBES", "Accion": "NUEVA"}]
    insert = next(p for s, p in conn.sql if "INSERT INTO score.ZonaRestringida (" in s)
    assert insert["valor"] == "TUMBES" and insert["todas"] == 1 and insert["nivel"] == "DEPARTAMENTO"
    assert not any("ZonaRestringidaCartera" in s for s, _ in conn.sql)


def test_registrar_existente_pasa_a_todas():
    conn = _Conn(existente={"IdZona": 1, "AplicaTodas": False})
    datos = z.validar_registro(_cuerpo(), hoy=HOY)
    r = z.registrar(conn, datos, "71234567")
    assert r[0]["Accion"] == "AMPLIADA" and r[0]["IdZona"] == 1
    assert any("SET AplicaTodas = 1" in s for s, _ in conn.sql)
    assert not any("INSERT INTO score.ZonaRestringida (" in s for s, _ in conn.sql)


def test_registrar_existente_con_las_mismas_carteras_no_cambia():
    conn = _Conn(existente={"IdZona": 1, "AplicaTodas": False}, rowcount_cartera=0)
    datos = z.validar_registro(_cuerpo(todas=False, carteras=[117]), hoy=HOY)
    assert z.registrar(conn, datos, "71234567")[0]["Accion"] == "SIN CAMBIO"


def test_registrar_existente_para_todas_no_cambia():
    conn = _Conn(existente={"IdZona": 1, "AplicaTodas": True})
    datos = z.validar_registro(_cuerpo(), hoy=HOY)
    assert z.registrar(conn, datos, "71234567")[0]["Accion"] == "SIN CAMBIO"


def test_levantar_exige_motivo():
    with pytest.raises(z.ZonaInvalida, match="por qué"):
        z.levantar(_Conn(), [1], "", "71234567")
    with pytest.raises(z.ZonaInvalida, match="No hay restricciones"):
        z.levantar(_Conn(), [], "Banco autorizó retomar", "71234567")


class _Fila(dict):
    __getattr__ = dict.get


class _ResExcel:
    def __init__(self, filas):
        self.filas = [_Fila(f) for f in filas]

    def mappings(self):
        return self

    def all(self):
        return self.filas

    def __iter__(self):
        return iter(self.filas)


class _ConnExcel:
    """Responde a las consultas del Excel según su texto."""
    def __init__(self):
        self.sql = []

    def execute(self, sql, params=None):
        s = str(sql)
        self.sql.append(s)
        if "FROM score.BaseTrabajoEstado" in s:
            return _ResExcel([{"IdCartera": 117, "TieneDepartamento": 1}, {"IdCartera": 132, "TieneDepartamento": 0}])
        if "TOP (100)" in s:
            return _ResExcel([{"IdCartera": 117, "Valor": "PROV. CONST. DEL CALLAO", "Clientes": 3}])
        if "AS SinDepartamento" in s:
            return _ResExcel([{"IdCartera": 117, "Clientes": 100, "ConDepartamento": 90, "NoReconocido": 3,
                               "SinDepartamento": 7}])
        if "ClientesPdp7Dias" in s:
            return _ResExcel([{"IdCartera": 117, "Clientes": 10, "ClientesPdp": 2, "Pdps": 2, "MontoPdp": 350.5,
                               "ClientesPdpHoy": 1, "ClientesPdp7Dias": 2}])
        if "AS EnBaseTrabajo" in s:
            return _ResExcel([{"IdCartera": 117, "DNI": "12345678", "IdCliente": 9, "Valor": "Piura", "IdZona": 1,
                               "Origen": "BANCO", "EnBaseTrabajo": "SI", "Pdps": 1, "MontoPdp": 350.5,
                               "ProximaPdp": date(2026, 11, 28)}])
        if "Fecha registro" in s or "p.FechaGenero" in s:
            return _ResExcel([{"IdCartera": 117, "DNI": "12345678", "IdCliente": 9, "Valor": "PIURA",
                               "FechaCompromiso": date(2026, 11, 28), "Monto": 350.5, "FechaGenero": date(2026, 11, 20)}])
        if "AS Situacion" in s:
            return _ResExcel([{"IdCartera": 117, "DNI": "87654321", "IdCliente": 5, "Situacion": "SIN VALOR", "Valor": None}])
        return _ResExcel([])


def test_cobertura_cuenta_y_lista_no_reconocidos():
    r = z.cobertura(_ConnExcel())
    assert r["carteras"][0]["ConDepartamento"] == 90 and r["carteras"][0]["SinDepartamento"] == 7
    assert r["no_reconocidos"][0]["Valor"] == "PROV. CONST. DEL CALLAO"


def test_excel_trae_las_cinco_hojas():
    from io import BytesIO
    from openpyxl import load_workbook
    conn = _ConnExcel()
    libro = load_workbook(BytesIO(z.excel(conn, [117])))
    assert libro.sheetnames == ["Resumen", "Clientes fuera", "PDP vigentes en zona", "Sin departamento", "Notas"]
    resumen = list(libro["Resumen"].values)
    assert resumen[1][0] == 117 and resumen[1][7] == 0.9 and resumen[1][10] == 350.5
    assert list(libro["Clientes fuera"].values)[1][4] == "PIURA"
    assert list(libro["Sin departamento"].values)[1][4] == "SIN VALOR"
    # Solo la cartera pedida: 132 no aparece y la consulta filtra por 117.
    assert all(f[0] != 132 for f in resumen[1:])
    assert any("IdCartera IN (117)" in s for s in conn.sql)
