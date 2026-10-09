"""Permisos por usuario: herencia, cambio y restablecimiento sin SQL real."""

import os
import unittest
from contextlib import contextmanager
from unittest.mock import patch

os.environ.setdefault("CRM_JWT_SECRET", "secreto-solo-para-tests-no-productivo-0123456789")

from app.core import permisos_vistas  # noqa: E402
from app.services import admin_accesos_service as servicio  # noqa: E402


class Resultado:
    def __init__(self, filas):
        self.filas = filas

    def mappings(self):
        return self

    def all(self):
        return self.filas

    def fetchone(self):
        return self.filas[0] if self.filas else None


class Conexion:
    def __init__(self, tabla):
        self.tabla = tabla

    def execute(self, query, params=None):
        sql = str(query).upper()
        params = params or {}
        dni = params.get("dni")
        clave = params.get("clave")
        if "SELECT VISTA, PERMITIDO" in sql:
            return Resultado([{"VISTA": k[1], "PERMITIDO": v}
                              for k, v in self.tabla.items() if k[0] == dni])
        if "SELECT PERMITIDO" in sql:
            valor = self.tabla.get((dni, clave))
            return Resultado([{"PERMITIDO": valor}] if valor is not None else [])
        if "DELETE FROM" in sql:
            for llave in list(self.tabla):
                if llave[0] == dni and (clave is None or llave[1] == clave):
                    del self.tabla[llave]
        if "INSERT INTO" in sql:
            self.tabla[(dni, clave)] = bool(params["permitido"])
        return Resultado([])


class Motor:
    def __init__(self):
        self.tabla = {}
        self.conn = Conexion(self.tabla)

    @contextmanager
    def connect(self):
        yield self.conn

    @contextmanager
    def begin(self):
        yield self.conn


class PermisosVistasTests(unittest.TestCase):
    def setUp(self):
        self.motor = Motor()
        usuario = {"usuario": "12345678", "tipo": "GESTOR", "idcartera": 126}
        self.parches = [
            patch.object(servicio.engine_siscob, "begin", side_effect=self.motor.begin),
            patch.object(permisos_vistas, "engine_siscob", self.motor),
            patch.object(servicio.auth_service, "_buscar_usuario_siscob_activo", return_value=usuario),
            patch.object(servicio.auth_service, "obtener_carteras_usuario", return_value=[126]),
        ]
        for parche in self.parches:
            parche.start()

    def tearDown(self):
        for parche in self.parches:
            parche.stop()

    def test_gestor_recibe_vista_de_equipo_y_luego_vuelve_al_perfil(self):
        dni = "12345678"
        antes = {v["clave"]: v for v in servicio.listar_vistas(dni)["vistas"]}
        self.assertFalse(antes["gestiones"]["permitido"])
        self.assertFalse(antes["gestiones"]["personalizado"])

        servicio.guardar_vista(dni, "gestiones", True, "11111111")
        concedido = {v["clave"]: v for v in servicio.listar_vistas(dni)["vistas"]}
        self.assertTrue(concedido["gestiones"]["permitido"])
        self.assertTrue(concedido["gestiones"]["personalizado"])
        self.assertTrue(permisos_vistas.permisos_efectivos({"dni": dni, "tipo": "GESTOR", "idcartera": 126})["gestiones"])

        servicio.guardar_vista(dni, "gestiones", False, "11111111")
        self.assertNotIn((dni, "gestiones"), self.motor.tabla)

    def test_quitar_vista_base_y_restablecer_todas(self):
        dni = "12345678"
        servicio.guardar_vista(dni, "telefonos", False, "11111111")
        self.assertFalse(permisos_vistas.permisos_efectivos({"dni": dni, "tipo": "GESTOR", "idcartera": 126})["telefonos"])
        servicio.restablecer_vistas(dni, "11111111")
        self.assertTrue(permisos_vistas.permisos_efectivos({"dni": dni, "tipo": "GESTOR", "idcartera": 126})["telefonos"])

    def test_catalogo_cerrado(self):
        with self.assertRaises(servicio.ErrorAccesos):
            servicio.guardar_vista("12345678", "accesos_admin", True, "11111111")


if __name__ == "__main__":
    unittest.main()
