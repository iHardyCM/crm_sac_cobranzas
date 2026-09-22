import unittest
from datetime import datetime
from unittest.mock import patch

from app.services import ia_audio_service as svc


class _ResultadoFalso:
    def __init__(self, filas):
        self.filas = filas

    def __iter__(self):
        return iter(self.filas)

    def mappings(self):
        return self

    def all(self):
        return [dict(fila) for fila in self.filas]


class _ConexionFalsa:
    def __init__(self):
        self.nota = 85.0
        self.firma = b"a" * 32
        self.lecturas_completas = 0

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        pass

    def execute(self, query, _params):
        if "HASHBYTES" in str(query):
            return _ResultadoFalso([(1, self.firma)])
        self.lecturas_completas += 1
        return _ResultadoFalso([{
            "id_feedback": 1,
            "fecha_creacion": datetime(2026, 9, 21),
            "score_final": self.nota,
            "score_calidad": self.nota,
            "evaluacion_calidad": "[]",
            "puntos_criticos": "[]",
            "resumen_sgc": "{}",
        }])


class _MotorFalso:
    def __init__(self, conexion):
        self.conexion = conexion

    def connect(self):
        return self.conexion


class CacheReporteriaIaTests(unittest.TestCase):
    def test_recarga_reusa_respuesta_y_cambio_en_sql_la_invalida(self):
        conexion = _ConexionFalsa()

        def enriquecer(data):
            return {**data, "evaluacion_calidad_lista": [], "resumen_sgc": {}}

        svc._REPORTERIA_CACHE.clear()
        with patch.object(svc, "engine_siscob", _MotorFalso(conexion)), \
             patch.object(svc, "ensure_tabla_feedback", lambda: None), \
             patch.object(svc, "_enriquecer_fila_reporteria", enriquecer):
            primera = svc.obtener_reporteria_calidad()
            primera["detalle"][0]["score_final"] = 0
            segunda = svc.obtener_reporteria_calidad()
            self.assertEqual(segunda["detalle"][0]["score_final"], 85.0)
            self.assertEqual(conexion.lecturas_completas, 1)

            conexion.nota = 90.0
            conexion.firma = b"b" * 32
            tercera = svc.obtener_reporteria_calidad()
            self.assertEqual(tercera["detalle"][0]["score_final"], 90.0)
            self.assertEqual(conexion.lecturas_completas, 2)
        svc._REPORTERIA_CACHE.clear()


if __name__ == "__main__":
    unittest.main()
