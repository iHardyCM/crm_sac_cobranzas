"""Flujo de la burbuja de alertas sin navegador ni base de datos."""
import shutil
import subprocess
from pathlib import Path

import pytest


RAIZ = Path(__file__).resolve().parents[1]
SCRIPT = RAIZ / "tests" / "frontend" / "alertas_layout.test.js"


@pytest.mark.skipif(shutil.which("node") is None, reason="Requiere Node.js")
def test_burbuja_vista_cambio_error_y_paginas_sin_alertas():
    proceso = subprocess.run(["node", str(SCRIPT)], cwd=RAIZ, capture_output=True, text=True, timeout=30)
    assert proceso.returncode == 0, proceso.stderr or proceso.stdout
    assert proceso.stdout.strip() == "OK"
