"""CSV del marcador (24/11/2026): solo IDCLIENTE y TELEFONO, con encabezado. El Excel conserva todas las columnas."""
from app.services import generador_bases_service as s


def test_csv_solo_idcliente_y_telefono(monkeypatch):
    monkeypatch.setattr(s, "obtener_base", lambda _id: {"Codigo": "B50"})
    monkeypatch.setattr(s, "_filas_archivo", lambda _id, _c: [["B50", 126, 1, "01234567", 555, "987654321", 1, 80, "A"],
                                                              ["B50", 126, 2, "07654321", None, "912345678", 1, 70, "A"]])
    texto = s.exportar_base(50, "csv").decode("utf-8")
    assert texto == "IDCLIENTE,TELEFONO\r\n555,987654321\r\n,912345678\r\n"
