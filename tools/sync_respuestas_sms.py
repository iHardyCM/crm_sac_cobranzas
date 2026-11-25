"""
Carga programada de respuestas SMS de Mowa hacia CobAuto (tablas CRM_SMS_*).

Requiere haber ejecutado antes tools/sql/crear_respuestas_sms.sql.

USO (desde la carpeta del CRM)
    python tools/sync_respuestas_sms.py                  # corrida programada (cada 10 min)
    python tools/sync_respuestas_sms.py --backfill       # carga inicial: campañas de 60 días
    python tools/sync_respuestas_sms.py --backfill --desde 2026-09-21

Corridas programadas: tools/sync_respuestas_sms.bat desde el Programador de tareas de
Windows, cada 10 minutos de 07:00 a 22:00, todos los días.

Código de salida: 0 = OK u omitida (otra corrida en curso), 1 = error.
El detalle de cada corrida queda en CobAuto.dbo.CRM_SMS_SINCRONIZACION.
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

from app.core.db_siscob import engine_siscob  # noqa: E402
from app.services import respuestas_sms_sync as sync  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Carga de respuestas SMS de Mowa a CobAuto.")
    parser.add_argument("--backfill", action="store_true",
                        help="Carga inicial: descubre campañas día por día y revisa todas.")
    parser.add_argument("--desde", type=date.fromisoformat, default=None,
                        help="Solo con --backfill: primer día de campañas (por defecto, hace 60 días).")
    parser.add_argument("--manual", action="store_true", help="Marca la corrida como MANUAL en la bitácora.")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    tipo = "BACKFILL" if args.backfill else ("MANUAL" if args.manual else "PROGRAMADA")
    try:
        resumen = sync.ejecutar(engine_siscob, tipo=tipo, desde=args.desde)
    except Exception:
        return 1
    if resumen.omitida:
        print("Omitida: hay otra corrida en curso.")
        return 0
    print(f"{tipo}: campañas nuevas={resumen.campanas_nuevas} revisadas={resumen.campanas_revisadas} "
          f"respuestas nuevas={resumen.respuestas_nuevas} orígenes completados={resumen.origenes_completados} "
          f"avisos={len(resumen.avisos)}")
    for aviso in resumen.avisos[:20]:
        print(f"  aviso: {aviso}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
