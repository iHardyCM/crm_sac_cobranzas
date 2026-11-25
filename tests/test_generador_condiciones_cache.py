"""Caché de las condiciones del día (fase 12), con una base simulada."""
from contextlib import contextmanager
from datetime import date

from app.services import generador_bases_reglas as r
from app.services import generador_bases_service as svc

CAT = {}


class _Res:
    def __init__(self, scalar=None, filas=(), rowcount=0):
        self._scalar, self._filas, self.rowcount = scalar, list(filas), rowcount

    def scalar(self):
        return self._scalar

    def fetchall(self):
        return self._filas


class _Motor:
    def __init__(self, existe=True, frescas=()):
        self.existe, self.frescas, self.sql = existe, set(frescas), []

    @contextmanager
    def _conn(self):
        motor = self

        class C:
            def execute(self, sql, params=None):
                texto = str(sql)
                motor.sql.append(texto)
                if "OBJECT_ID('score.CondicionDiaEstado')" in texto:
                    return _Res(scalar=1 if motor.existe else None)
                if "FROM score.CondicionDiaEstado" in texto:
                    return _Res(filas=list(motor.frescas))
                if "sp_getapplock" in texto:
                    return _Res(scalar=0)
                if texto.startswith("INSERT INTO score.CondicionDia"):
                    return _Res(rowcount=37)
                if texto.strip().startswith("MERGE"):
                    motor.frescas.add((params["codigo"], params["idcartera"]))
                return _Res()
        yield C()

    def connect(self):
        return self._conn()

    def begin(self):
        return self._conn()


def _consulta(condiciones, carteras=(112,)):
    return r.construir_consulta(carteras[0], {"canal": "PRED", "condiciones": condiciones}, CAT,
                                hoy=date(2026, 11, 20), carteras=list(carteras))


def test_refresca_solo_lo_vencido(monkeypatch):
    motor = _Motor(frescas={("CEF_HOY", 112)})
    monkeypatch.setattr(svc, "engine_siscob", motor)
    tiempos = {}
    usa = svc.asegurar_condiciones(_consulta({"CEF_HOY": "QUITAR", "PDP_VIGENTE": "QUITAR", "ENVIADO_HOY": "QUITAR"}),
                                   tiempos)
    assert usa is True
    lecturas = [s for s in motor.sql if s.startswith("INSERT INTO score.CondicionDia")]
    assert len(lecturas) == 1 and "N'PDP_VIGENTE'" in lecturas[0]      # CEF_HOY estaba fresca; ENVIADO es en vivo
    assert list(tiempos) == ["cond_PDP_VIGENTE_112"]
    # Segunda consulta inmediata: no vuelve a leer SISCOB
    motor.sql.clear()
    svc.asegurar_condiciones(_consulta({"CEF_HOY": "QUITAR", "PDP_VIGENTE": "SOLO"}), {})
    assert not [s for s in motor.sql if s.startswith("INSERT INTO score.CondicionDia")]


def test_combinada_refresca_cada_cartera(monkeypatch):
    motor = _Motor()
    monkeypatch.setattr(svc, "engine_siscob", motor)
    tiempos = {}
    svc.asegurar_condiciones(_consulta({"PAGO_HOY": "QUITAR"}, carteras=(126, 128)), tiempos)
    assert sorted(tiempos) == ["cond_PAGO_HOY_126", "cond_PAGO_HOY_128"]


def test_sin_tablas_de_la_fase_12_sigue_en_vivo(monkeypatch):
    motor = _Motor(existe=False)
    monkeypatch.setattr(svc, "engine_siscob", motor)
    assert svc.asegurar_condiciones(_consulta({"CEF_HOY": "QUITAR"}), {}) is False
    assert not [s for s in motor.sql if "CondicionDia (" in s]


def test_sin_condiciones_no_consulta_nada(monkeypatch):
    motor = _Motor()
    monkeypatch.setattr(svc, "engine_siscob", motor)
    assert svc.asegurar_condiciones(_consulta({"ENVIADO_HOY": "QUITAR"}), {}) is True
    assert motor.sql == []
