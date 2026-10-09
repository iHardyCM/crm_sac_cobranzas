#!/usr/bin/env python3
"""Actualiza el ?v= de los CSS/JS referenciados en frontend/views/*.html.

La version es un hash del contenido de cada archivo: solo cambia cuando el
archivo cambia, asi el navegador nunca usa una copia vieja ni descarga de mas.

Uso (desde la raiz del proyecto):
    python tools/version_assets.py            # reescribe los HTML que lo necesiten
    python tools/version_assets.py --check    # solo informa; sale con 1 si hay pendientes

Solo toca referencias locales (../css/, ../js/, ../core/). No modifica CSS ni JS.
"""
import hashlib
import re
import sys
from pathlib import Path

FRONTEND = Path(__file__).resolve().parent.parent / "frontend"
VIEWS = FRONTEND / "views"
LARGO_HASH = 10

# src="../js/app.js?v=xxx"  |  href="../css/app.css"
REFERENCIA = re.compile(r'((?:src|href)=")(\.\./(?:css|js|core)/[^"?#]+\.(?:css|js))(\?v=[^"]*)?(")')


def version_de(ruta: Path) -> str:
    return hashlib.sha1(ruta.read_bytes()).hexdigest()[:LARGO_HASH]


def procesar(html: Path, escribir: bool):
    # newline="" conserva los saltos de linea originales (CRLF/LF) del archivo.
    with open(html, encoding="utf-8", newline="") as f:
        original = f.read()
    avisos = []
    cambios = []

    def reemplazar(m):
        destino = (VIEWS / m.group(2)).resolve()
        if not destino.is_file():
            avisos.append(f"no existe {m.group(2)}")
            return m.group(0)
        nueva = f"?v={version_de(destino)}"
        if (m.group(3) or "") != nueva:
            cambios.append(m.group(2))
        return f"{m.group(1)}{m.group(2)}{nueva}{m.group(4)}"

    nuevo = REFERENCIA.sub(reemplazar, original)
    if escribir and nuevo != original:
        with open(html, "w", encoding="utf-8", newline="") as f:
            f.write(nuevo)
    return cambios, avisos


def main():
    solo_revisar = "--check" in sys.argv[1:]
    if not VIEWS.is_dir():
        print(f"No encuentro {VIEWS}")
        return 2
    pendientes = 0
    for html in sorted(VIEWS.glob("*.html")):
        cambios, avisos = procesar(html, escribir=not solo_revisar)
        for a in avisos:
            print(f"[AVISO] {html.name}: {a}")
        if cambios:
            pendientes += 1
            print(f"{'[PENDIENTE]' if solo_revisar else '[ACTUALIZADO]'} {html.name}: {', '.join(cambios)}")
    if pendientes == 0:
        print("Todo al dia: no hay versiones por actualizar.")
    elif solo_revisar:
        print(f"{pendientes} pagina(s) con versiones desactualizadas.")
        return 1
    else:
        print(f"{pendientes} pagina(s) actualizadas.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
