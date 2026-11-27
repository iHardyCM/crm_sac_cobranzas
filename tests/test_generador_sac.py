"""Exportación de clientes fuera del SAC (fase 17, 25/11/2026)."""
import io
from datetime import date

from openpyxl import load_workbook

from app.services import generador_sac_service as s


def test_mapear_columnas_por_nombre_parecido():
    assert s.mapear_columnas(["Saldo Capital por Cuenta", "Saldo Total x Cliente"])["capital"] == "Saldo Capital por Cuenta"
    m = s.mapear_columnas(["NumDocumento", "Operacion", "NomCliente", "CtaCliente", "SdoCapital ", "Cal_PROV",
                           "CodigoGrupo", "CodCreGrupal", "FecUltPago"])
    assert m["dni"] == "NumDocumento" and m["capital"] == "SdoCapital " and m["calificacion"] == "Cal_PROV"
    assert m["codigo_grupo"] == "CodigoGrupo" and m["cod_cre_grupal"] == "CodCreGrupal"
    assert m["dias_atraso"] is None


def test_normalizaciones():
    assert s.sin_ceros("00000000000019362539") == "19362539"
    assert s.sin_ceros(1234567.0) == "1234567"
    assert s.calificacion(2.0) == "2-Deficiente" and s.calificacion("X") == "X"
    assert s.fecha_aaaammdd(20261103.0) == date(2026, 11, 3) and s.fecha_aaaammdd(None) is None


def test_excel_una_fila_por_operacion_y_sin_asignacion(monkeypatch):
    mapa = s.mapear_columnas(["DNI", "Operacion", "NomCliente", "CtaCliente", "SdoCapital", "Cal_PROV", "CodigoGrupo", "CodCreGrupal"])
    datos = {
        "ultima": {"FechaSac": date(2026, 11, 25), "FechaCarga": "2026-11-25 09:47"},
        "clientes": [
            {"IdCartera": 133, "DNI": "01234567", "Condicion": "CANCELADO", "CondicionCodigo": "CA", "MgContacto": "CEF", "UgIndicador": "x",
             "EstadoPdp": "PAGADA", "UltCefTramo": "Día 20", "CapitalAnalytics": 500, "UltimoDiaEnSac": date(2026, 11, 24),
             "SaldoUltimoDiaEnSac": 480},
            {"IdCartera": 133, "DNI": "07654321", "Condicion": "NUEVO"},
        ],
        "asignaciones": {133: ({"1234567": [
            {"DNI": "1234567", "Operacion": "00019362539", "NomCliente": "ANA", "CtaCliente": "77", "SdoCapital": 300.5,
             "Cal_PROV": 0, "CodigoGrupo": 123456789012.0, "CodCreGrupal": 5.0},
            {"DNI": "1234567", "Operacion": "00019362540", "NomCliente": "ANA", "CtaCliente": "77", "SdoCapital": 199.5,
             "Cal_PROV": 1, "CodigoGrupo": 123456789012.0, "CodCreGrupal": 5.0}]}, mapa, "compartamos_grupal")},
        "grupal": True,
    }
    monkeypatch.setattr(s, "fuera_del_sac", lambda _id: datos)
    contenido, nombre = s.exportar_fuera_del_sac(133)
    assert nombre == "133_fuera_del_SAC_20261125.xlsx"
    hoja = load_workbook(io.BytesIO(contenido))["Fuera del SAC"]
    filas = list(hoja.iter_rows(values_only=True))
    cab = filas[0]
    assert "Código grupo" in cab and "Cod. créd. grupal" in cab and "Condición SISCOB (hoy)" in cab
    assert len(filas) == 4                                 # 2 operaciones + 1 cliente sin asignación
    f1 = dict(zip(cab, filas[1]))
    assert f1["DNI"] == "01234567" and f1["Operación"] == "00019362539" and f1["Calificación"] == "0-Normal"
    assert f1["Código grupo"] == "123456789012" and f1["Cód. condición"] == "CA"
    f3 = dict(zip(cab, filas[3]))
    assert f3["Observación"] == "Sin fila en la asignación de la cartera"


def test_quita_caracteres_que_excel_no_acepta():
    assert s._celda("ANA\x02 PEREZ\x1f") == "ANA PEREZ"
    assert s._codigo("77\x00") == "77"
