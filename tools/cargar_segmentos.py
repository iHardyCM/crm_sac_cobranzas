"""Carga de segmentos de MiBanco (y otros) al generador de bases.

Uso (desde la carpeta del CRM, con el mismo .env del backend):
    python tools/cargar_segmentos.py SEGMENTACION_COBEX tools/entradas/segmentos_mibanco_202611/Clientes_Segmentacion_Nov26_Cobex_Castigo_Biznescob.xlsx
    python tools/cargar_segmentos.py SEGMENTACION_COBEX <mismo archivo> --cargar --usuario 12345678

Sin --cargar solo muestra la vista previa (no escribe). Con --cargar escribe en una sola transacción:
reemplaza la carga vigente con el mismo nombre (queda en el historial como REEMPLAZADA).

Requisito: tools/sql/score_telefonico_fase8_segmentos.sql ejecutado.
Las definiciones de abajo son las de noviembre de 2026 (archivos revisados el 14/11 y el 16/11). Si el banco
cambia columnas, se ajusta aquí; más adelante esto lo hará la carga desde el CRM.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from app.services.segmentos_service import (  # noqa: E402
    CargaInvalida, ColumnaSegmento, DefinicionCarga, cargar, leer_archivo, previsualizar,
)

DEFINICIONES = {
    # Clientes_Segmentacion_Nov26_Cobex_Castigo_Biznescob.xlsx · 4.906 clientes, uno por fila
    "SEGMENTACION_COBEX": DefinicionCarga(
        entidad="MIBANCO", segmento="Segmentación COBEX castigo", columna_clave="CO_CLIENTE",
        tipo_clave="CODIGO_BANCO", columna_periodo="PERIODO", filtros={"FUNCIONARIO": ["BIZNESCOB"]},
        columnas=[
            ColumnaSegmento("SEG_FINAL_COBEX_CAST", "SEG_COBEX_CAST", "Segmento COBEX castigo (MiBanco)", "SEGC",
                            "Segmento final que envía MiBanco (SEG_FINAL_COBEX_CAST).", orden_valores="G1|G2|G3|T.A|T.B"),
            ColumnaSegmento("SUB_SEG_FINAL_COBEX_CAST", "SUBSEG_COBEX_CAST", "Subsegmento COBEX castigo (MiBanco)", "SSEGC",
                            "Subsegmento final que envía MiBanco (SUB_SEG_FINAL_COBEX_CAST).", orden_valores="G1|G2|G3"),
        ]),
    # Base_Preferia_Nov26_Final.xlsx · hoja DATA; trae clientes de otras agencias: se quedan los de BIZNESCOB
    "PREFIERA": DefinicionCarga(
        entidad="MIBANCO", segmento="Campaña Prefiera", columna_clave="CO_CLIENTE", tipo_clave="CODIGO_BANCO",
        hoja="DATA", columna_periodo="PERIODO", filtros={"FUNCIONARIO": ["BIZNESCOB"]},
        columnas=[
            ColumnaSegmento("DSCTO_PREFIERA", "DSCTO_PREFIERA", "Descuento campaña Prefiera (MiBanco)", "DPRF",
                            "Descuento de la campaña Prefiera. Sin dato = el cliente no está en la campaña.",
                            formato="PORCENTAJE"),
        ]),
    # Gestion_Prioritaria_Biznescob.xlsx · por préstamo (COD_PRE); el valor es único por cliente salvo el
    # préstamo "Activa" del cliente 1337785, que no es castigo: se cargan solo las filas "Castigo Rp".
    "GESTION_PRIORITARIA": DefinicionCarga(
        entidad="MIBANCO", segmento="Gestión prioritaria", columna_clave="COD_CLI", tipo_clave="CODIGO_BANCO",
        periodo="202611", filtros={"Marca Control": ["Castigo Rp"], "USU_FIN 2": ["BIZNESCOB"]},
        columnas=[
            ColumnaSegmento("Gestion Prio", "GESTION_PRIO_MB", "Gestión prioritaria (MiBanco)", "GPRIO",
                            "Prioridad de gestión que envía MiBanco (Gestion Prio).", orden_valores="P. Alta|P. Media|P. Baja"),
            ColumnaSegmento("RANGO MES_CLASIFICADO", "RANGO_MES_CLASIF_MB", "Rango de meses clasificado (MiBanco)", "RMCL",
                            "Rango de meses de castigo clasificado por MiBanco; \"6. IRRE\" = irrecuperable.",
                            orden_valores="1.[2-12]|2.[13-24]|3.[25-48]|4.[49>|6. IRRE"),
        ]),
}


def main() -> int:
    ap = argparse.ArgumentParser(description="Carga de segmentos al generador de bases")
    ap.add_argument("definicion", choices=sorted(DEFINICIONES))
    ap.add_argument("archivo")
    ap.add_argument("--cargar", action="store_true", help="escribe la carga (sin esto, solo vista previa)")
    ap.add_argument("--usuario", default="CARGA_MANUAL", help="DNI de quien carga (queda en la bitácora)")
    args = ap.parse_args()

    from app.core.db_siscob import engine_siscob   # misma conexión del CRM (base CobAuto)

    d = DEFINICIONES[args.definicion]
    ruta = Path(args.archivo)
    if not ruta.is_absolute() and not ruta.exists():
        ruta = RAIZ / ruta
    if not ruta.exists():
        print(f"NO SE ENCONTRÓ EL ARCHIVO: {args.archivo}\n"
              f"Pon la ruta completa entre comillas o deja el archivo en tools/entradas/ y usa esa ruta.")
        return 1
    df = leer_archivo(ruta.read_bytes(), ruta.name, d.hoja)
    try:
        if args.cargar:
            with engine_siscob.begin() as conn:
                r = cargar(conn, d, df, ruta.name, args.usuario)
            print("CARGA HECHA")
        else:
            with engine_siscob.connect() as conn:
                r = previsualizar(conn, d, df)
            r.pop("filas", None)
            print("VISTA PREVIA (no se escribió nada; repite con --cargar)")
    except CargaInvalida as exc:
        print(f"NO SE CARGÓ: {exc}")
        return 1
    print(json.dumps(r, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
