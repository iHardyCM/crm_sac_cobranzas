"""Tests de la validacion de sesion del frontend (session.js, home.js, fetchIa y
los modulos Cliente, Compromisos y Telefonos).

Ejecuta tests/frontend/sesion_frontend.test.js con Node (sin navegador ni BD).
Si Node no esta instalado, se saltan.

    python -m unittest tests.test_sesion_frontend -v
"""

import json
import shutil
import subprocess
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
SCRIPT = RAIZ / "tests" / "frontend" / "sesion_frontend.test.js"

CASOS_ESPERADOS = {
    "semanas_de_mes_domingo_a_sabado",
    "sin_token_no_continua",
    "me_401_limpia_sesion_y_va_al_login",
    "me_200_actualiza_identidad_desde_backend",
    "me_5xx_no_autoriza_ni_borra_credenciales",
    "me_403_cambio_obligatorio_va_a_cambiar_clave",
    "pagina_ia_no_carga_datos_si_me_falla",
    "fetch_ia_agrega_bearer_y_respeta_headers_y_formdata",
    "fetch_ia_401_cierra_sesion",
    "fetch_ia_403_cambio_obligatorio_redirige",
    "fetch_ia_otro_403_no_redirige",
    # Home como puerta de sesion
    "home_200_continua",
    "home_respeta_permiso_individual_de_equipo_y_revocaciones",
    "home_identidad_backend_reemplaza_localstorage",
    "home_401_limpia_sesion",
    "home_401_redirige_login",
    "home_401_no_continua",
    "home_cambio_obligatorio_va_a_cambiar_clave",
    "home_5xx_no_usa_sesion_vieja",
    "home_sin_token_va_al_login",
    "redireccion_ocurre_una_sola_vez",
    "home_recarga_desde_cache_revalida",
    # Cliente, Compromisos y Telefonos
    "compartamos_no_consulta_si_me_falla",
    "compartamos_consulta_con_bearer_sin_carteras_del_navegador",
    "compartamos_401_en_consulta_cierra_sesion",
    "compromisos_no_carga_si_me_falla",
    "compromisos_no_carga_si_vista_revocada_y_equipo_permitido",
    "compromisos_usa_identidad_del_backend_y_bearer",
    "supervisor_no_carga_si_me_falla",
    "supervisor_resumen_con_bearer_sin_dni_del_navegador",
    "telefonos_no_carga_si_me_falla",
    "telefonos_carga_filtros_con_bearer",
    "fetch_con_sesion_401_y_cambio_obligatorio",
    # 403: cambio de clave (codigo) vs acceso denegado
    "fetch_con_sesion_401_limpia_sesion_y_va_al_login",
    "fetch_con_sesion_403_cambio_clave_por_codigo",
    "fetch_con_sesion_403_acceso_denegado_no_cierra_sesion",
    "fetch_con_sesion_403_sin_codigo_no_es_cambio_de_clave",
    "compartamos_403_acceso_denegado_muestra_mensaje_y_se_queda",
    "compromisos_detalle_403_acceso_denegado_se_queda",
    "compromisos_detalle_403_cambio_clave_va_a_cambiar_clave",
}


@unittest.skipUnless(shutil.which("node"), "Requiere Node.js en el PATH")
class SesionFrontendTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        proceso = subprocess.run(
            ["node", str(SCRIPT)], cwd=RAIZ, capture_output=True, text=True, timeout=120,
        )
        lineas = [l for l in proceso.stdout.strip().splitlines() if l.strip()]
        if proceso.returncode != 0 or not lineas:
            raise AssertionError(f"Node fallo: {proceso.stderr or proceso.stdout}")
        cls.resultados = json.loads(lineas[-1])

    def test_todos_los_casos_se_ejecutaron(self):
        self.assertEqual(set(self.resultados), CASOS_ESPERADOS)

    def test_casos(self):
        for nombre in sorted(CASOS_ESPERADOS):
            with self.subTest(caso=nombre):
                self.assertEqual(self.resultados.get(nombre), "OK")


if __name__ == "__main__":
    unittest.main()
