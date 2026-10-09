"""Pruebas de tools/crear_accesos_iniciales.py (sin base de datos).

    python -m unittest tests.test_accesos_iniciales -v
"""

import contextlib
import io
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

os.environ.setdefault("CRM_JWT_SECRET", "secreto-solo-para-tests-no-productivo-0123456789")

try:
    import pyodbc  # noqa: F401
except Exception:  # pragma: no cover
    sys.modules["pyodbc"] = MagicMock()

with patch("sqlalchemy.create_engine", MagicMock()):
    from tools import crear_accesos_iniciales as ini  # noqa: E402
    from app.core import security  # noqa: E402
    from app.services import auth_service  # noqa: E402


def fila(usuario="12345678", tipo="GESTOR", acceso=None, activo=1, cambio=1, fecha_cambio=None):
    return {"USUARIO": usuario, "TipoUsuario": tipo, "USUARIO_ACCESO": acceso,
            "FLG_ACTIVO": activo, "FLG_CAMBIO_OBLIGATORIO": cambio, "FECHA_CAMBIO_CLAVE": fecha_cambio}


class ClasificarTests(unittest.TestCase):
    def test_sin_cuenta_se_crea(self):
        self.assertEqual(ini.clasificar(fila()), ini.CREAR)

    def test_usuario_que_no_es_dni_se_omite(self):
        for u in ("ABC", "1234567", "123456789", "12 34567", ""):
            self.assertEqual(ini.clasificar(fila(usuario=u)), ini.OMITIR_DNI_INVALIDO, u)

    def test_cuenta_con_clave_definitiva_no_se_toca(self):
        f = fila(acceso="12345678", cambio=0, fecha_cambio="2026-10-01")
        self.assertEqual(ini.clasificar(f, incluir_pendientes=True), ini.OMITIR_DEFINITIVA)

    def test_cuenta_deshabilitada_no_se_toca(self):
        f = fila(acceso="12345678", activo=0)
        self.assertEqual(ini.clasificar(f, incluir_pendientes=True), ini.OMITIR_DESHABILITADA)

    def test_temporal_sin_usar_solo_con_flag(self):
        f = fila(acceso="12345678", cambio=1, fecha_cambio=None)
        self.assertEqual(ini.clasificar(f), ini.OMITIR_PENDIENTE)
        self.assertEqual(ini.clasificar(f, incluir_pendientes=True), ini.REEMPLAZAR_TEMPORAL)

    def test_excluir_tipos_ignora_tildes_y_mayusculas(self):
        self.assertEqual(ini.clasificar(fila(tipo="Administrador "), excluir_tipos=["ADMINISTRADOR"]), ini.OMITIR_EXCLUIDO)
        self.assertEqual(ini.clasificar(fila(tipo="GESTOR"), excluir_tipos=["ADMINISTRADOR"]), ini.CREAR)


class ClaveInicialTests(unittest.TestCase):
    def test_hash_del_dni_valida_con_el_login_y_el_dni_no_sirve_como_clave_nueva(self):
        dni = "12345678"
        h = security.generar_hash_clave(dni)
        self.assertTrue(security.verificar_clave(dni, h))
        self.assertFalse(security.verificar_clave("87654321", h))
        with self.assertRaises(auth_service.ErrorCambioClave):
            auth_service.validar_politica_clave(dni, dni)


class DryRunTests(unittest.TestCase):
    def test_sin_ejecutar_no_escribe(self):
        usuarios = [fila("11111111"), fila("22222222", acceso="22222222", cambio=0, fecha_cambio="x")]
        engine = MagicMock()
        with patch("app.core.db_siscob.engine_siscob", engine), \
             patch.object(ini, "leer_usuarios", return_value=usuarios), \
             patch.object(ini, "crear_cuenta") as crear, \
             patch.object(ini, "reemplazar_temporal") as reemplazar, \
             patch.object(ini, "guardar_csv", return_value="x.csv"), \
             contextlib.redirect_stdout(io.StringIO()) as salida:
            rc = ini.main([])
        self.assertEqual(rc, 0)
        crear.assert_not_called()
        reemplazar.assert_not_called()
        engine.begin.assert_not_called()
        self.assertIn("DRY-RUN", salida.getvalue())

    def test_ejecutar_sin_confirmar_no_escribe(self):
        engine = MagicMock()
        with patch("app.core.db_siscob.engine_siscob", engine), \
             patch.object(ini, "leer_usuarios", return_value=[fila("11111111")]), \
             patch.object(ini, "crear_cuenta") as crear, \
             patch.object(ini, "guardar_csv", return_value="x.csv"), \
             patch("builtins.input", return_value="no"), \
             contextlib.redirect_stdout(io.StringIO()):
            rc = ini.main(["--ejecutar"])
        self.assertEqual(rc, 1)
        crear.assert_not_called()

    def test_ejecutar_confirmado_crea_con_hash_del_dni(self):
        engine = MagicMock()
        creadas = []
        def fake_crear(conn, dni, h):
            creadas.append((dni, h)); return 1
        with patch("app.core.db_siscob.engine_siscob", engine), \
             patch.object(ini, "leer_usuarios", return_value=[fila("11111111"), fila("22222222")]), \
             patch.object(ini, "crear_cuenta", side_effect=fake_crear), \
             patch.object(ini, "guardar_csv", return_value="x.csv"), \
             patch("builtins.input", return_value="CONFIRMAR"), \
             contextlib.redirect_stdout(io.StringIO()):
            rc = ini.main(["--ejecutar"])
        self.assertEqual(rc, 0)
        self.assertEqual([d for d, _ in creadas], ["11111111", "22222222"])
        for dni, h in creadas:
            self.assertTrue(security.verificar_clave(dni, h))
            self.assertNotIn(dni, h)


if __name__ == "__main__":
    unittest.main()
