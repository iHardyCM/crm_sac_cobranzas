"""Contrato local del mantenedor de carteras adicionales por usuario."""

import os
import unittest
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("CRM_JWT_SECRET", "secreto-solo-para-tests-no-productivo-0123456789")

from app.services import admin_accesos_service as servicio  # noqa: E402
from app.services import admin_supervisores_service, auth_service  # noqa: E402


class ConexionFalsa:
    def __init__(self):
        self.filas = {}
        self.siguiente_id = 1

    def execute(self, query, params=None):
        sql = str(query).upper()
        params = params or {}
        clave = (params.get("dni"), params.get("idcartera"))
        if "SELECT TOP 1 ID" in sql:
            fila = self.filas.get(clave)
            return SimpleNamespace(fetchone=lambda: SimpleNamespace(id=fila[0]) if fila else None)
        if "UPDATE COBAUTO.DBO.CRM_SUPERVISOR_CARTERA" in sql:
            anterior = self.filas[clave]
            self.filas[clave] = (anterior[0], bool(params["activo"]))
            return SimpleNamespace()
        if "INSERT INTO COBAUTO.DBO.CRM_SUPERVISOR_CARTERA" in sql:
            self.filas[clave] = (self.siguiente_id, True)
            self.siguiente_id += 1
            return SimpleNamespace()
        if "SELECT IDCARTERA" in sql:
            filas = [SimpleNamespace(idcartera=cartera) for (dni, cartera), (_, activo) in self.filas.items()
                     if dni == params["dni"] and activo]
            return SimpleNamespace(fetchall=lambda: filas)
        raise AssertionError(f"SQL inesperado: {sql}")


class CarterasUsuarioTests(unittest.TestCase):
    def setUp(self):
        self.conn = ConexionFalsa()

        @contextmanager
        def transaccion():
            yield self.conn

        self.patches = [
            patch.object(servicio.engine_siscob, "begin", transaccion),
            patch.object(servicio, "_exigir_usuario_siscob_activo",
                         return_value={"usuario": "22222222", "idcartera": 126}),
            patch.object(admin_supervisores_service, "listar_carteras", return_value=[
                {"idcartera": 126, "cartera": "COMPARTAMOS VIGENTE INDIVIDUAL"},
                {"idcartera": 128, "cartera": "COMPARTAMOS VIGENTE CCM"},
            ]),
            patch.object(auth_service, "asegurar_tabla_supervisor_cartera"),
        ]
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)

    def test_asignar_y_revocar_128_se_refleja_en_la_identidad(self):
        dni = "22222222"
        antes = servicio.listar_carteras_usuario(dni)
        self.assertEqual([c["idcartera"] for c in antes["carteras"] if c["permitido"]], [126])

        servicio.guardar_cartera_usuario(dni, 128, True, "11111111")
        self.assertEqual(auth_service.obtener_carteras_usuario(dni, 126), [126, 128])
        despues = servicio.listar_carteras_usuario(dni)
        self.assertTrue(next(c for c in despues["carteras"] if c["idcartera"] == 128)["permitido"])

        servicio.guardar_cartera_usuario(dni, 128, False, "11111111")
        self.assertEqual(auth_service.obtener_carteras_usuario(dni, 126), [126])

    def test_no_puede_quitar_principal_ni_asignar_fuera_del_catalogo(self):
        with self.assertRaises(servicio.ErrorAccesos) as principal:
            servicio.guardar_cartera_usuario("22222222", 126, False, "11111111")
        self.assertEqual(principal.exception.status_code, 409)
        with self.assertRaises(servicio.ErrorAccesos) as desconocida:
            servicio.guardar_cartera_usuario("22222222", 999, True, "11111111")
        self.assertEqual(desconocida.exception.status_code, 400)
        self.assertFalse(self.conn.filas)


if __name__ == "__main__":
    unittest.main()
