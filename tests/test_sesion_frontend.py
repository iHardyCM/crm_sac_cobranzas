"""Tests de la validacion de sesion del frontend (session.js y fetchIa).

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
