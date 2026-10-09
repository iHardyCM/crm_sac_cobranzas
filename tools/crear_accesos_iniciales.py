#!/usr/bin/env python3
"""Carga inicial de accesos CRM: clave inicial = DNI, con cambio obligatorio.

Que hace
    Para cada usuario activo de SISCOB (Estado = 'A') con DNI de 8 digitos que
    todavia NO tiene cuenta en CobAuto.dbo.CRM_USUARIO_ACCESO, crea la cuenta con
    la clave inicial igual a su DNI (guardada como hash Argon2, igual que el resto
    del CRM), FLG_ACTIVO = 1 y FLG_CAMBIO_OBLIGATORIO = 1. En su primer ingreso el
    CRM obliga a cambiarla antes de usar cualquier modulo; la politica de claves
    ya rechaza usar el DNI como clave nueva.

Que NO hace
    - No toca cuentas que ya tienen una clave definitiva.
    - No toca cuentas deshabilitadas a proposito (FLG_ACTIVO = 0).
    - No modifica SISCOB.dbo.USUARIO.
    - Sin --ejecutar solo muestra el plan (no escribe nada en la BD).

Modos
    python tools/crear_accesos_iniciales.py                   # plan (dry-run)
    python tools/crear_accesos_iniciales.py --ejecutar        # crea las cuentas
    python tools/crear_accesos_iniciales.py --incluir-pendientes
        # ademas, cuentas con clave temporal aleatoria que NUNCA se usaron para
        # definir clave propia: pasan a clave = DNI (con --ejecutar)
    python tools/crear_accesos_iniciales.py --excluir-tipos ADMINISTRADOR
        # deja fuera del lote a esos perfiles (se habilitan luego, uno a uno,
        # desde Administracion de accesos, que entrega una clave aleatoria)
    python tools/crear_accesos_iniciales.py --reporte
        # quienes siguen sin cambiar la clave inicial (solo lectura)
    python tools/crear_accesos_iniciales.py --cerrar-ventana [--ejecutar]
        # deshabilita las cuentas del lote que no cambiaron la clave (ver riesgo)

Riesgo conocido (leer antes de ejecutar)
    El DNI no es un secreto. Mientras una cuenta conserve la clave inicial,
    cualquiera que conozca el DNI puede entrar como esa persona y fijar su propia
    clave. El bloqueo por intentos no lo evita (el atacante usa la clave correcta).
    Conviene: ejecutar el lote el mismo dia que se comunica el lanzamiento, pedir
    el cambio de inmediato, revisar --reporte a las 24-48 h y usar --cerrar-ventana
    para las cuentas que sigan sin cambiar (se reactivan con "Habilitar acceso",
    que entrega una clave aleatoria nueva).
"""

import argparse
import csv
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

# Debe caber en USUARIO_CREACION / USUARIO_ACTUALIZACION: esas columnas ya guardan
# un DNI (8 caracteres) en el alta normal, por eso la etiqueta mide exactamente 8.
ETIQUETA_LOTE = "LOTE_DNI"
assert len(ETIQUETA_LOTE) <= 8
TAMANO_LOTE = 200

CREAR = "CREAR"
REEMPLAZAR_TEMPORAL = "REEMPLAZAR_TEMPORAL"
OMITIR_DEFINITIVA = "OMITIR_YA_TIENE_CLAVE"
OMITIR_DESHABILITADA = "OMITIR_DESHABILITADA"
OMITIR_PENDIENTE = "OMITIR_PENDIENTE (usa --incluir-pendientes)"
OMITIR_DNI_INVALIDO = "OMITIR_USUARIO_NO_ES_DNI_DE_8_DIGITOS"
OMITIR_EXCLUIDO = "OMITIR_PERFIL_EXCLUIDO"


def normalizar_tipo(tipo) -> str:
    import unicodedata
    texto = unicodedata.normalize("NFD", str(tipo or "").strip())
    return "".join(c for c in texto if unicodedata.category(c) != "Mn").upper()


def clasificar(fila: Dict, incluir_pendientes: bool = False,
               excluir_tipos: Optional[Iterable[str]] = None) -> str:
    """Decide que hacer con un usuario SISCOB (fila ya unida con su cuenta CRM).

    Es una funcion pura para poder probarla sin base de datos.
    """
    usuario = str(fila.get("USUARIO") or "").strip()
    if not (len(usuario) == 8 and usuario.isdigit()):
        return OMITIR_DNI_INVALIDO

    excluidos = {normalizar_tipo(t) for t in (excluir_tipos or [])}
    if excluidos and normalizar_tipo(fila.get("TipoUsuario")) in excluidos:
        return OMITIR_EXCLUIDO

    if fila.get("USUARIO_ACCESO") is None:
        return CREAR

    if not fila.get("FLG_ACTIVO"):
        return OMITIR_DESHABILITADA

    # Cuenta con clave temporal aleatoria que nunca llego a definir clave propia.
    if fila.get("FLG_CAMBIO_OBLIGATORIO") and fila.get("FECHA_CAMBIO_CLAVE") is None:
        return REEMPLAZAR_TEMPORAL if incluir_pendientes else OMITIR_PENDIENTE

    return OMITIR_DEFINITIVA


# ---------------------------------------------------------------------------
# Acceso a datos (SQL Server)
# ---------------------------------------------------------------------------

def leer_usuarios(conn) -> List[Dict]:
    from sqlalchemy import text
    rows = conn.execute(text("""
        SELECT
            LTRIM(RTRIM(U.USUARIO)) AS USUARIO,
            U.Nombres, U.Apellidos, U.TipoUsuario, U.IDCARTERA,
            A.USUARIO AS USUARIO_ACCESO,
            A.FLG_ACTIVO, A.FLG_CAMBIO_OBLIGATORIO,
            A.FECHA_CAMBIO_CLAVE, A.FECHA_ULTIMO_LOGIN, A.USUARIO_CREACION
        FROM SISCOB.dbo.USUARIO U WITH (NOLOCK)
        LEFT JOIN CobAuto.dbo.CRM_USUARIO_ACCESO A
            ON A.USUARIO COLLATE DATABASE_DEFAULT = LTRIM(RTRIM(U.USUARIO)) COLLATE DATABASE_DEFAULT
        WHERE LTRIM(RTRIM(ISNULL(U.Estado, ''))) = 'A'
        ORDER BY U.TipoUsuario, U.Apellidos, U.Nombres
    """)).mappings().all()
    return [dict(r) for r in rows]


def crear_cuenta(conn, dni: str, password_hash: str) -> int:
    """INSERT protegido contra carreras: si otra sesion creo la cuenta, no hace nada."""
    from sqlalchemy import text
    res = conn.execute(text("""
        INSERT INTO CobAuto.dbo.CRM_USUARIO_ACCESO
            (USUARIO, PASSWORD_HASH, FLG_ACTIVO, FLG_CAMBIO_OBLIGATORIO,
             INTENTOS_FALLIDOS, BLOQUEADO_HASTA, FECHA_CAMBIO_CLAVE, USUARIO_CREACION)
        SELECT :dni, :hash, 1, 1, 0, NULL, NULL, :lote
        WHERE NOT EXISTS (
            SELECT 1 FROM CobAuto.dbo.CRM_USUARIO_ACCESO WITH (UPDLOCK, HOLDLOCK)
            WHERE USUARIO = :dni)
    """), {"dni": dni, "hash": password_hash, "lote": ETIQUETA_LOTE})
    return res.rowcount or 0


def reemplazar_temporal(conn, dni: str, password_hash: str) -> int:
    """Solo si la cuenta SIGUE con clave temporal sin definir (evita pisar un cambio reciente)."""
    from sqlalchemy import text
    res = conn.execute(text("""
        UPDATE CobAuto.dbo.CRM_USUARIO_ACCESO
        SET PASSWORD_HASH = :hash,
            FLG_CAMBIO_OBLIGATORIO = 1,
            INTENTOS_FALLIDOS = 0,
            BLOQUEADO_HASTA = NULL,
            USUARIO_ACTUALIZACION = :lote,
            FECHA_ACTUALIZACION = SYSDATETIME()
        WHERE USUARIO = :dni
          AND FLG_ACTIVO = 1
          AND FLG_CAMBIO_OBLIGATORIO = 1
          AND FECHA_CAMBIO_CLAVE IS NULL
    """), {"dni": dni, "hash": password_hash, "lote": ETIQUETA_LOTE})
    return res.rowcount or 0


def leer_pendientes_del_lote(conn) -> List[Dict]:
    from sqlalchemy import text
    rows = conn.execute(text("""
        SELECT A.USUARIO, U.Nombres, U.Apellidos, U.TipoUsuario,
               A.FLG_ACTIVO, A.FECHA_ULTIMO_LOGIN
        FROM CobAuto.dbo.CRM_USUARIO_ACCESO A
        LEFT JOIN SISCOB.dbo.USUARIO U WITH (NOLOCK)
            ON LTRIM(RTRIM(U.USUARIO)) COLLATE DATABASE_DEFAULT = A.USUARIO COLLATE DATABASE_DEFAULT
        WHERE (A.USUARIO_CREACION = :lote OR A.USUARIO_ACTUALIZACION = :lote)
          AND A.FLG_ACTIVO = 1
          AND A.FLG_CAMBIO_OBLIGATORIO = 1
          AND A.FECHA_CAMBIO_CLAVE IS NULL
        ORDER BY U.TipoUsuario, U.Apellidos, U.Nombres
    """), {"lote": ETIQUETA_LOTE}).mappings().all()
    return [dict(r) for r in rows]


def deshabilitar_pendientes(conn) -> int:
    from sqlalchemy import text
    res = conn.execute(text("""
        UPDATE CobAuto.dbo.CRM_USUARIO_ACCESO
        SET FLG_ACTIVO = 0,
            USUARIO_ACTUALIZACION = :lote,
            FECHA_ACTUALIZACION = SYSDATETIME()
        WHERE (USUARIO_CREACION = :lote OR USUARIO_ACTUALIZACION = :lote)
          AND FLG_ACTIVO = 1
          AND FLG_CAMBIO_OBLIGATORIO = 1
          AND FECHA_CAMBIO_CLAVE IS NULL
    """), {"lote": ETIQUETA_LOTE})
    return res.rowcount or 0


# ---------------------------------------------------------------------------
# Presentacion
# ---------------------------------------------------------------------------

def _nombre(f: Dict) -> str:
    return f"{(f.get('Apellidos') or '').strip()} {(f.get('Nombres') or '').strip()}".strip()


def resumir(plan: List[Dict]) -> None:
    por_accion = Counter(f["_accion"] for f in plan)
    print("\nResumen del plan")
    for accion, n in sorted(por_accion.items()):
        print(f"  {n:6d}  {accion}")
    afectados = [f for f in plan if f["_accion"] in (CREAR, REEMPLAZAR_TEMPORAL)]
    if afectados:
        print("\nCuentas que quedarian con clave inicial = DNI, por perfil")
        for tipo, n in sorted(Counter(normalizar_tipo(f.get("TipoUsuario")) or "(SIN PERFIL)" for f in afectados).items()):
            print(f"  {n:6d}  {tipo}")


def guardar_csv(plan: List[Dict], nombre: str) -> Path:
    carpeta = RAIZ / "logs"
    carpeta.mkdir(exist_ok=True)
    ruta = carpeta / f"{nombre}_{datetime.now():%Y%m%d_%H%M%S}.csv"
    with open(ruta, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["usuario", "nombre", "perfil", "idcartera", "accion"])
        for fila in plan:
            w.writerow([fila.get("USUARIO"), _nombre(fila), fila.get("TipoUsuario"),
                        fila.get("IDCARTERA"), fila["_accion"]])
    return ruta


def confirmar(mensaje: str) -> bool:
    return input(f"{mensaje}\nEscribe CONFIRMAR para continuar: ").strip() == "CONFIRMAR"


# ---------------------------------------------------------------------------
# Modos
# ---------------------------------------------------------------------------

def modo_carga(args) -> int:
    from app.core.db_siscob import engine_siscob
    from app.core.security import generar_hash_clave

    with engine_siscob.connect() as conn:
        usuarios = leer_usuarios(conn)

    plan = []
    for f in usuarios:
        f["_accion"] = clasificar(f, args.incluir_pendientes, args.excluir_tipos)
        plan.append(f)

    resumir(plan)
    ruta = guardar_csv(plan, "accesos_iniciales_plan" if not args.ejecutar else "accesos_iniciales_ejecutado")
    print(f"\nDetalle por usuario: {ruta}")

    a_procesar = [f for f in plan if f["_accion"] in (CREAR, REEMPLAZAR_TEMPORAL)]
    if not args.ejecutar:
        print("\nDRY-RUN: no se escribio nada. Revisa el detalle y vuelve a ejecutar con --ejecutar.")
        return 0
    if not a_procesar:
        print("\nNada que procesar.")
        return 0
    if not confirmar(f"\nSe aplicara clave inicial = DNI (cambio obligatorio) a {len(a_procesar)} cuenta(s)."):
        print("Cancelado.")
        return 1

    hechos = Counter()
    for i in range(0, len(a_procesar), TAMANO_LOTE):
        bloque = a_procesar[i:i + TAMANO_LOTE]
        with engine_siscob.begin() as conn:  # una transaccion por bloque
            for f in bloque:
                dni = f["USUARIO"]
                password_hash = generar_hash_clave(dni)
                if f["_accion"] == CREAR:
                    hechos[CREAR] += crear_cuenta(conn, dni, password_hash)
                else:
                    hechos[REEMPLAZAR_TEMPORAL] += reemplazar_temporal(conn, dni, password_hash)
        print(f"  procesados {min(i + TAMANO_LOTE, len(a_procesar))}/{len(a_procesar)}")

    print(f"\nListo. Creadas: {hechos[CREAR]} | temporales reemplazadas: {hechos[REEMPLAZAR_TEMPORAL]} "
          f"| omitidas por cambios concurrentes: {len(a_procesar) - sum(hechos.values())}")
    print("Recuerda: revisa --reporte a las 24-48 h y usa --cerrar-ventana para las que sigan sin cambiar.")
    return 0


def modo_reporte(args) -> int:
    from app.core.db_siscob import engine_siscob
    with engine_siscob.connect() as conn:
        pendientes = leer_pendientes_del_lote(conn)
    print(f"Cuentas del lote que siguen con la clave inicial (DNI): {len(pendientes)}")
    for tipo, n in sorted(Counter(normalizar_tipo(f.get("TipoUsuario")) or "(SIN PERFIL)" for f in pendientes).items()):
        print(f"  {n:6d}  {tipo}")
    ruta = RAIZ / "logs"
    ruta.mkdir(exist_ok=True)
    destino = ruta / f"accesos_pendientes_{datetime.now():%Y%m%d_%H%M%S}.csv"
    with open(destino, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["usuario", "nombre", "perfil", "ultimo_login"])
        for p in pendientes:
            w.writerow([p["USUARIO"], _nombre(p), p.get("TipoUsuario"), p.get("FECHA_ULTIMO_LOGIN")])
    print(f"Detalle: {destino}")
    return 0


def modo_cerrar_ventana(args) -> int:
    from app.core.db_siscob import engine_siscob
    with engine_siscob.connect() as conn:
        pendientes = leer_pendientes_del_lote(conn)
    print(f"Cuentas del lote sin cambiar la clave inicial: {len(pendientes)}")
    if not args.ejecutar:
        print("DRY-RUN: no se deshabilito nada. Usa --ejecutar para deshabilitarlas.")
        return 0
    if not pendientes:
        return 0
    if not confirmar(f"Se deshabilitaran {len(pendientes)} cuenta(s) (se reactivan con 'Habilitar acceso')."):
        print("Cancelado.")
        return 1
    with engine_siscob.begin() as conn:
        n = deshabilitar_pendientes(conn)
    print(f"Deshabilitadas: {n}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Carga inicial de accesos CRM con clave inicial = DNI.")
    ap.add_argument("--ejecutar", action="store_true", help="Aplica los cambios (sin esto es dry-run).")
    ap.add_argument("--incluir-pendientes", action="store_true",
                    help="Tambien pasa a clave = DNI las cuentas con clave temporal que nunca definieron clave propia.")
    ap.add_argument("--excluir-tipos", nargs="*", default=[],
                    help="Perfiles (TipoUsuario) que quedan fuera del lote, p. ej. ADMINISTRADOR.")
    ap.add_argument("--reporte", action="store_true", help="Lista las cuentas del lote que no cambiaron la clave.")
    ap.add_argument("--cerrar-ventana", action="store_true",
                    help="Deshabilita las cuentas del lote que no cambiaron la clave inicial.")
    args = ap.parse_args(argv)

    if args.reporte:
        return modo_reporte(args)
    if args.cerrar_ventana:
        return modo_cerrar_ventana(args)
    return modo_carga(args)


if __name__ == "__main__":
    sys.exit(main())
