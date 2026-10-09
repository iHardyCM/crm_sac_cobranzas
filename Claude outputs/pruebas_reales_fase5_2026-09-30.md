# Pruebas reales — Fase 5 (CRM SAC Cobranzas)

- **Fecha:** 2026-09-30
- **Entorno:** backend local (`http://localhost:8000`) con la BD real, rama `hardening/security-phase1`, sin commit.
- **Cómo se probó:** llamadas a la API con el token de cada cuenta y comprobaciones en pantalla en el navegador de la app.
- **Cuentas:** se usaron cuentas de prueba habilitadas desde Accesos CRM. Se identifican por los 3 últimos dígitos del DNI.

| Cuenta | Perfil | Carteras (según `/auth/me`) |
|---|---|---|
| Gestor A …787 | GESTOR | 126 |
| Gestor B …234 | GESTOR | 126 |
| Supervisor …800 | SUPERVISOR | 126 |
| Supervisor …409 | SUPERVISOR | 124 (+112, 143 adicionales) |
| Monitor …650 | MONITOR DE CALIDAD | — |
| Gestor …981 | GESTOR | 112 (Mibanco) |

Datos usados, elegidos con el administrador:

- Clientes: uno solo de la cartera 126, uno solo de la 124 y uno multicartera (124+126).
- Compromisos: uno de cada gestor y uno de un agente de la 124.

**Resultado: pasaron los 71 casos** (65 por API y 6 en pantalla).

## Alta y primer ingreso

| Caso | Esperado | Obtenido |
|---|---|---|
| Habilitar una cuenta ya activa | 409 | 409 ✔ |
| Login con clave temporal | 200 + cambio obligatorio | 200, `requiere_cambio_clave=true` ✔ |
| `/auth/me` con clave temporal | 200 + cambio obligatorio | ✔ |
| Endpoint de datos con clave temporal | 403 `CAMBIO_CLAVE_OBLIGATORIO` | ✔ |
| Cambio de clave con la clave actual incorrecta | rechazado | 400 ✔ |
| Nueva clave igual al DNI | rechazado | 400 ✔ |
| Cambio de clave válido | 200 | ✔ |
| Login con la clave temporal ya usada | 401 genérico | ✔ |
| Login con la clave definitiva | 200, sin cambio obligatorio | ✔ |
| Alta completa de las otras 5 cuentas | 200 / 200 | ✔ |

## Cliente (Consulta Compartamos)

| Caso | Esperado | Obtenido |
|---|---|---|
| Gestor 126 → cliente de la 126 | 200 con datos | ✔ |
| Gestor 126 → cliente de la 124 | 403 `ACCESO_DENEGADO`, sin datos | ✔ |
| Gestor 126 → cliente multicartera 124+126 | 403, sin datos | ✔ |
| Supervisor 126 → cliente de la 126 / multicartera | 200 / 403 | ✔ |
| Supervisor 124 → cliente de la 124 / de la 126 / multicartera | 200 / 403 / 403 | ✔ |
| Monitor de calidad | 403 (módulo) | ✔ |
| Gestor Mibanco | 403 (módulo) | ✔ |
| Administrador → multicartera | 200 | ✔ |
| Gestor con `idcartera`, `idcarteras`, `perfil` o `tipo` en la URL | igual 403 | ✔ |
| Valor inexistente | 200, `encontrado=false` | ✔ |

## Compromisos

| Caso | Esperado | Obtenido |
|---|---|---|
| Gestor A ve sus compromisos | 200 | 119 filas ✔ |
| Gestor A → lista de gestor B, misma cartera (`/{dni}` y `/agente/compromisos`) | 403 | ✔ |
| Supervisor 126 → agente de la 126 / de la 124 | 200 / 403 | ✔ |
| Supervisor 124 → agente de la 124 / de la 126 | 200 / 403 | ✔ |
| Detalle: gestor A abre su propio compromiso | 200 | ✔ |
| **IDOR:** gestor A abre el detalle de gestor B, misma cartera | 403 | ✔ |
| **IDOR:** gestor A abre el detalle de un agente de la 124 | 403 | ✔ |
| **IDOR:** gestor A con `agente` y `perfil` en la URL | 403 | ✔ |
| Detalle: supervisor 126 → gestor A / agente de la 124 | 200 / 403 | ✔ |
| Detalle: supervisor 124 → agente de la 124 / gestor A | 200 / 403 | ✔ |
| Detalle: administrador / monitor | 200 / 403 | ✔ |
| Resumen supervisor: gestor | 403 | ✔ |
| Resumen supervisor: supervisor con DNI ajeno en la URL | 200 con sus propios datos | ✔ |
| Exportar cartera: gestor | 403 | ✔ |
| Exportar cartera: supervisor con DNI ajeno en la URL | archivo con su propio DNI | ✔ |

## Teléfonos

| Caso | Esperado | Obtenido |
|---|---|---|
| Filtros del gestor 126 | solo la cartera 126 | ✔ |
| Filtros del supervisor 124 | subconjunto de 112/124/143 | solo 124 ✔ |
| Filtros del administrador | todas | 9 carteras ✔ |
| Gestor 126 busca un cliente de la 124 | sin teléfonos (el administrador ve 6) | ✔ |
| Gestor 126 busca un cliente de la 126 | con teléfonos | ✔ |
| Gestor 126 fuerza `idcartera=124` | 403 | ✔ |
| Monitor | 403 | ✔ |
| Detalle de un número de cliente de la 124 | administrador 200 / gestor 126 no lo ve | 200 / 404 ✔ |

## Accesos y revocación

| Caso | Esperado | Obtenido |
|---|---|---|
| Deshabilitar con el JWT vigente | 401 en cliente, `/auth/me`, compromisos, teléfonos y login | ✔ |
| Rehabilitar | clave temporal nueva; la anterior 401; cambio obligatorio | ✔ |
| 5 intentos fallidos | bloqueo; la clave correcta también da 401; mensaje genérico | ✔ |
| El administrador ve el bloqueo | `BLOQUEADO`, 5 intentos | ✔ |
| Desbloquear | la clave correcta vuelve a entrar | ✔ |
| Reset de clave | la anterior 401; temporal con cambio; el JWT anterior recibe 403 `CAMBIO_CLAVE_OBLIGATORIO` | ✔ |
| El administrador intenta deshabilitarse | 409 | ✔ |
| Gestor o supervisor usan Accesos | 403 `ACCESO_DENEGADO` | ✔ |

## En pantalla (gestor A)

| Caso | Esperado | Obtenido |
|---|---|---|
| Consulta Compartamos, cliente de la 124 | se queda en el módulo con el mensaje y conserva la sesión | ✔ |
| Consulta Compartamos, cliente de la 126 | muestra la ficha | ✔ |
| Compromisos: detalle de otro gestor | aviso "No tienes acceso a este compromiso.", se queda | ✔ |
| Compromisos: detalle propio | abre el modal | ✔ |
| Teléfonos: filtro de carteras | solo la 126 | ✔ |
| Página abierta y el administrador deshabilita la cuenta | la siguiente acción lleva al login, borra el almacenamiento y muestra "Tu sesión ya no está habilitada" | ✔ |

## Hallazgos (no son fallos de la Fase 5)

1. **JWT anterior tras rehabilitar o resetear.** Si una cuenta se deshabilita y luego se rehabilita, o se le resetea la clave, un JWT emitido antes vuelve a responder `/auth/me`. Mientras no se cambie la clave, los datos le dan 403 por cambio obligatorio. Después de ese cambio, ese token vuelve a servir hasta que vence. **Propuesta para otra fase:** versión de token o fecha de emisión mínima en `CRM_USUARIO_ACCESO`.
2. **Clientes multicartera.** En una muestra de 36 clientes encontrados, tomados de compromisos de los gestores …787 (126) y …699 (124), 4 eran multicartera y quedan bloqueados para los usuarios sin visión global. La muestra es chica y no representa al total.
3. **Incidente durante la prueba.** Al abrir una pestaña, la herramienta navegó la pestaña del administrador y se perdió su sesión en el navegador. La cuenta del administrador no cambió. Se repitió el ingreso y la prueba siguió en una dirección separada (127.0.0.1).

## Estado final

- Las 6 cuentas de prueba quedaron **DESHABILITADAS**.
- La cuenta del administrador sigue **ACTIVA**, y el monitor …220, que ya estaba deshabilitado, no se tocó.
- Las filas de las cuentas de prueba siguen en `CRM_USUARIO_ACCESO`, porque el sistema no borra cuentas.
- Ninguna contraseña ni clave temporal queda registrada en este documento.
