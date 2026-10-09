# Autenticación CRM — Fases 1 a 5 (rama `hardening/security-phase1`)

## Qué hace

`POST /auth/login` recibe `{ "dni", "clave" }` y autentica en este orden:

1. `SISCOB.dbo.USUARIO`: el usuario existe y `Estado = 'A'`. No se usa `USUARIO.Clave` ni `FechaCese`.
2. `CobAuto.dbo.CRM_USUARIO_ACCESO`: la cuenta existe, `FLG_ACTIVO = 1`, tiene `PASSWORD_HASH` y no hay un `BLOQUEADO_HASTA` vigente.
3. La contraseña se valida con Argon2 (`verificar_clave`).
4. Si la contraseña es incorrecta, se suma 1 a `INTENTOS_FALLIDOS` y se registra `FECHA_ULTIMO_FALLO`. Al quinto fallo se fija `BLOQUEADO_HASTA` en ahora + 15 minutos.
5. Si es correcta: `INTENTOS_FALLIDOS = 0`, `BLOQUEADO_HASTA = NULL` y `FECHA_ULTIMO_LOGIN = SYSDATETIME()`. Se emite un JWT con el DNI en `sub`.

Todas las fechas usan el reloj de SQL Server. Cualquier fallo de credenciales responde **401 "Usuario o contraseña incorrectos."**, sin indicar la causa. Un error técnico responde **503** con un mensaje genérico y el detalle queda en `logs/app.log`.

### Decisiones tomadas

- **Bloqueo vencido:** al vencer el bloqueo, el contador vuelve a empezar y el usuario tiene otros 5 intentos. Mientras el bloqueo está vigente, los intentos se rechazan sin contarse y sin alargar el bloqueo.
- **Bloqueo sin aviso:** durante el bloqueo también se responde el mensaje genérico. El usuario no ve que está bloqueado.
- **Mismo tiempo de respuesta:** un DNI inexistente o sin cuenta también pasa por una verificación Argon2 señuelo, para que no se distinga por el tiempo que tarda.
- **Concurrencia:** la fila del usuario se lee con `UPDLOCK, ROWLOCK` dentro de una transacción, para que dos intentos simultáneos no cuenten mal los fallos.

`GET /auth/me` exige `Authorization: Bearer <token>`. Del token solo se toma el DNI.

En cada petición autenticada, el backend vuelve a validar:

1. que la cuenta exista en `CobAuto.dbo.CRM_USUARIO_ACCESO` y tenga `FLG_ACTIVO = 1`;
2. que el usuario siga existiendo en `SISCOB.dbo.USUARIO` con `Estado = 'A'`;
3. el perfil y las carteras actuales desde SISCOB y `CRM_SUPERVISOR_CARTERA`.

Por lo tanto, deshabilitar una cuenta CRM o inactivar al usuario en SISCOB revoca el acceso aunque el JWT todavía no haya vencido.

La dependencia reutilizable es `app.core.auth_dependencies.obtener_usuario_actual`.

## Qué NO cambia todavía

- ~~Los endpoints fuera de `/auth`, `/admin-accesos`, `/ia-feedback`, `/calibracion`, `/cliente`, `/compromisos` y `/telefonos` siguen sin proteger.~~ Resuelto en la Fase 6: ya exigen sesión (ver "Fase 6").
- CORS, `NOLOCK` y las conexiones SQL siguen como estaban.
- El frontend sigue guardando `dni`, `agente`, `tipo`, `idcartera` e `idcarteras` en `localStorage` para no romper las pantallas. **Esos datos no son seguridad.** La credencial real es `access_token`.

## Fase 2 — Administración de accesos y cambio de clave

### Quién puede administrar

Todos los endpoints `/admin-accesos/...` usan la dependencia `requiere_administrador` (en `app/core/auth_dependencies.py`), que parte de `obtener_usuario_actual`:

- Sin token, o con un token inválido o vencido, o con la cuenta deshabilitada: **401**.
- Con sesión válida pero `TipoUsuario` distinto de `ADMINISTRADOR`: **403**. El perfil se lee de SISCOB en cada petición, normalizado (mayúsculas, sin tildes ni espacios).
- Con clave temporal (`FLG_CAMBIO_OBLIGATORIO = 1`): **403 "Debes cambiar tu contraseña antes de continuar."**, aunque sea administrador y el JWT sea válido. `requiere_administrador` depende de `requiere_clave_definitiva`, que lee el indicador en la BD en cada petición y no confía en `localStorage`.
- Nunca se usan como autorización el perfil ni el DNI que manda el navegador (`localStorage`, payload o query string).
- Ocultar el menú o la tarjeta en el frontend es solo comodidad: escribir la URL `admin_accesos.html` a mano no da permisos, porque los endpoints siguen respondiendo 403.
- La auditoría (`USUARIO_CREACION`, `USUARIO_ACTUALIZACION`) toma el DNI del administrador del JWT, nunca del payload.

### Endpoints administrativos

| Método y ruta | Qué hace | Errores de negocio |
| --- | --- | --- |
| `GET /admin-accesos/usuarios?q=&limite=` | Usuarios de SISCOB con `Estado='A'`, cruzados con `CRM_USUARIO_ACCESO`. Busca por DNI, nombres o apellidos. Límite máximo: 200. No devuelve `PASSWORD_HASH`. | — |
| `POST /admin-accesos/{dni}/habilitar` | Si no hay cuenta, la crea. Si está deshabilitada, la **rehabilita**. En ambos casos genera una clave temporal nueva. | 404 si no está activo en SISCOB; 409 si la cuenta ya está activa |
| `POST /admin-accesos/{dni}/reset-clave` | Genera una clave temporal nueva; la anterior deja de servir. | 404 si no tiene cuenta; 409 si está deshabilitada |
| `POST /admin-accesos/{dni}/desbloquear` | `INTENTOS_FALLIDOS = 0`, `BLOQUEADO_HASTA = NULL`. | 404 si no tiene cuenta |
| `POST /admin-accesos/{dni}/deshabilitar` | `FLG_ACTIVO = 0`. No borra la cuenta ni su historial. Si ya estaba deshabilitada, responde ok con `sin_cambios`. | 404 si no tiene cuenta; **409 "No puedes deshabilitar tu propia cuenta."** si el DNI objetivo es el del administrador del JWT |

Un DNI que no tiene 8 dígitos responde 400. Un error técnico responde 500 con un mensaje genérico, y el detalle queda en el log.

**Estados de acceso que devuelve el listado:** `SIN_ACCESO`, `ACTIVO`, `CAMBIO_OBLIGATORIO`, `BLOQUEADO`, `DESHABILITADO` y `SIN_CLAVE` (cuenta activa sin `PASSWORD_HASH`, por ejemplo creada a mano).

### Clave temporal

- Se genera con `secrets`: 12 caracteres, con al menos una mayúscula, una minúscula y un dígito. Se excluyen los caracteres que se confunden (`0/O`, `1/l/I`). No usa el DNI, fechas, claves fijas ni `SISCOB.Clave`. (La única excepción es la carga inicial masiva de la Fase 6, que usa el DNI como clave inicial; ver abajo.)
- Solo se guarda su hash Argon2.
- **Se muestra una sola vez**, en la respuesta del endpoint, que lleva `Cache-Control: no-store`. No se escribe en el log, ni en la BD en texto plano, ni en `localStorage`. En la pantalla vive solo en el DOM hasta que el administrador pulsa "Ya la entregué, ocultar".
- Si se pierde, la única salida es resetear. Nadie puede consultar una clave, ni la temporal ni la definitiva.
- Habilitar, rehabilitar y resetear dejan `FLG_ACTIVO = 1`, `FLG_CAMBIO_OBLIGATORIO = 1`, `INTENTOS_FALLIDOS = 0`, `BLOQUEADO_HASTA = NULL` y `FECHA_CAMBIO_CLAVE = NULL`. Esta última se completa cuando el usuario crea su clave definitiva.

### Flujo de alta

1. El administrador busca al usuario en **Configuración → Accesos CRM** (`admin_accesos.html`) y pulsa **Habilitar acceso**.
2. La pantalla muestra la clave temporal una vez. El administrador se la entrega al usuario por un canal seguro.
3. El usuario entra con su DNI y la clave temporal. El login responde `requiere_cambio_clave = true`.
4. `login.js` guarda solo `access_token` y `requiere_cambio_clave = "true"`, y redirige a `cambiar_clave.html`. Como no guarda `dni` ni `agente`, `exigirSesion()` no deja abrir otras pantallas del CRM.
5. El usuario cambia la clave. `cambiar_clave.js` pide `/auth/me`, guarda los datos de compatibilidad (`dni`, `agente`, `tipo`, `idcartera`, `idcarteras`), fija `requiere_cambio_clave = "false"` y va al inicio.

### Cambio obligatorio protegido por el backend

Una cuenta con `FLG_CAMBIO_OBLIGATORIO = 1` (recién habilitada, rehabilitada o reseteada) tiene un JWT válido, pero solo puede usar:

- `GET /auth/me`
- `POST /auth/cambiar-clave`

Cualquier endpoint que use `requiere_clave_definitiva` o `requiere_administrador` (hoy todo `/admin-accesos/*`) responde **403 "Debes cambiar tu contraseña antes de continuar."**. Por eso **una cuenta con clave temporal no puede administrar accesos**, aunque su perfil sea `ADMINISTRADOR`. En cuanto cambia la clave (`FLG_CAMBIO_OBLIGATORIO = 0`), el mismo token vuelve a servir: no hace falta volver a iniciar sesión.

La redirección del frontend a `cambiar_clave.html` sigue funcionando como comodidad. La regla la hace cumplir el backend.

`requiere_clave_definitiva` está en `app/core/auth_dependencies.py` y se puede reutilizar al proteger otros routers.

### Cambio de clave del propio usuario

`POST /auth/cambiar-clave` con `{ "clave_actual", "clave_nueva", "confirmacion" }` y `Authorization: Bearer`:

- El usuario sale **solo** del JWT. El modelo no tiene campo `dni`, y si se envía uno se ignora.
- Revalida la cuenta activa (la dependencia) y verifica la clave actual contra `PASSWORD_HASH`.
- Política mínima: de 8 a 128 caracteres, no en blanco, distinta del DNI y distinta de la clave actual. No hay más reglas.
- Si todo es válido: nuevo hash Argon2, `FLG_CAMBIO_OBLIGATORIO = 0`, `INTENTOS_FALLIDOS = 0`, `BLOQUEADO_HASTA = NULL`, `FECHA_CAMBIO_CLAVE = SYSDATETIME()`, `USUARIO_ACTUALIZACION = <propio DNI>` y `FECHA_ACTUALIZACION = SYSDATETIME()`.
- Errores de validación: 400 con un mensaje para el usuario. Sin token: 401.

La pantalla `cambiar_clave.html` también sirve para un cambio voluntario. Si no es obligatorio, muestra "Volver al inicio".

### Revocación inmediata

`obtener_usuario_actual` revalida `CRM_USUARIO_ACCESO.FLG_ACTIVO = 1` y `SISCOB.Estado = 'A'` en **cada** petición. Deshabilitar corta el acceso en la siguiente petición, aunque el JWT siga vigente. Esto aplica a los **endpoints protegidos** (ver Fase 3 y "Módulos pendientes de migración").

### Logging

Se registran la acción, el administrador o usuario, el usuario objetivo y el resultado (por ejemplo `Admin accesos accion=RESET_CLAVE admin=... objetivo=... resultado=OK`). Nunca se registran claves temporales ni definitivas, hashes ni tokens.

## Fase 3 — Sesión validada en el frontend y módulo IA protegido

### Validación real de la sesión en el frontend (`session.js`)

`exigirSesion()` se mantiene por compatibilidad, pero **no es seguridad**: solo mira `localStorage`.

Las páginas migradas esperan `asegurarSesionBackend()` (que llama una vez a `validarSesionBackend()`) **antes de cargar cualquier dato**:

| Respuesta de `GET /auth/me` | Qué hace el frontend |
| --- | --- |
| Sin `access_token` en el navegador | Limpia la sesión y va al login |
| 200 | Reemplaza `dni`, `agente`, `tipo`, `idcartera` e `idcarteras` con lo que responde el backend y continúa. Si `requiere_cambio_clave = "true"`, va a `cambiar_clave.html` |
| 401 | `localStorage.clear()`, `sessionStorage.clear()`, mensaje "Tu sesión ya no está habilitada. Inicia sesión nuevamente." y va al login |
| 403 "Debes cambiar tu contraseña antes de continuar." | Va a `cambiar_clave.html` |
| 5xx o sin respuesta | No continúa ni asume sesión válida. Muestra un aviso con "Reintentar" y **no** borra las credenciales |

Helpers disponibles en `session.js` para las próximas migraciones: `agregarAuthorizationHeader()`, `cerrarSesionPorBackend()`, `irACambioClaveObligatorio()` y `esRespuestaCambioClave()`.

**Páginas migradas:** `home.html` (Fase 4), `ia_feedback.html` (Análisis IA, con calibración y reportería) y `consumo_ia.html`. `admin_accesos.html` y `cambiar_clave.html` ya enviaban el token desde la Fase 2.

### Módulo IA en el frontend

- `ia_feedback.js`: `fetchIa()` agrega `Authorization: Bearer` a **todas** las llamadas del módulo (`/ia-feedback` y `/calibracion`), sin pisar los headers existentes y respetando `FormData`. Si la respuesta es 401, cierra la sesión y va al login. Si es 403 por cambio obligatorio, va a `cambiar_clave.html`. Otros 403 (por ejemplo, perfil sin acceso) siguen el manejo de siempre.
- La página no llama a `cargarConfigIa`, `cargarCarterasIa`, `cargarBandejaIa`, `cargarReporteriaIa` ni a nada más hasta que `/auth/me` responde 200.
- **Audio:** un `<audio src>` no puede enviar el header `Authorization`, así que el audio se descarga con `fetchIa` y se reproduce desde un blob local.
- `consumo_ia.js` ya no envía `perfil`: el backend lo toma de la sesión.

### Módulo IA en el backend

Todos los endpoints de datos o de modificación exigen `requiere_clave_definitiva`: JWT, `FLG_ACTIVO = 1`, SISCOB `Estado = 'A'` y sin cambio obligatorio pendiente. Sin sesión válida responden **401**; con clave temporal, **403**. Solo `GET /ia-feedback` (el HTML de la página) queda abierto.

**`/ia-feedback` (22 endpoints protegidos):** `GET /config`, `GET /carteras`, `GET /prompt`, `POST /prompt`, `GET /bandeja`, `GET /agentes`, `POST /upload`, `POST /{id}/analizar/iniciar`, `GET /{id}/estado`, `POST /{id}/analizar`, `POST /{id}/revision`, `POST /{id}/recalibracion` (retirado, responde 410), `GET /{id}/recalibraciones`, `POST /recalibracion/{id}/resolver` (retirado, 410), `POST /{id}/coaching`, `GET /listar`, `GET /reporteria`, `GET /consumo`, `POST /reporteria/exportar-excel`, `GET /{id}/audio`, `GET /{id}` y `POST /{id}/agente`.

**`/calibracion` (10 endpoints protegidos, los usa la misma página):** `GET /motivos`, `GET /cola`, `GET /permisos`, `POST /llamada/{id}/enviar`, `POST /llamada/{id}/resolver`, `GET /{id}`, `POST /criterio`, `POST /{id}/resolver`, `POST /{id}/recalcular` y `GET /reporte/precision`.

**Perfil e identidad salen de la sesión, no del navegador.** Los parámetros `perfil`, `supervisor`, `usuario`, `actualizado_por` y `revisado_por` se siguen aceptando por compatibilidad, pero **se ignoran**:

| Uso | Antes (navegador) | Ahora (servidor) |
| --- | --- | --- |
| Editar o ver el prompt (`/prompt`) | `perfil` | `TipoUsuario` de SISCOB |
| Visión global en bandeja, listar y reportería | `perfil` | `TipoUsuario` de SISCOB |
| Filtro "lo propio" en bandeja, listar y reportería | `supervisor` | `agente` de la sesión ("DNI - Nombres Apellidos") |
| Supervisor al cargar un audio | `supervisor` | `agente` de la sesión |
| `revisado_por`, `actualizado_por`, asignación de agente | Formulario | `agente` de la sesión |
| Ver el consumo de la API | `perfil` | `TipoUsuario` de SISCOB |
| Permisos de calibración (proponer o publicar) | `perfil` del payload | `TipoUsuario` de SISCOB |
| Usuario que audita la calibración | `usuario` del payload | DNI de la sesión |

Antes, si el payload de calibración venía sin `perfil`, el servicio omitía el chequeo de permiso de "proponer". Ahora el perfil siempre llega desde el servidor.

### Revocación en la práctica

Con una cuenta deshabilitada:
1. Al recargar Home o cualquier página migrada, `/auth/me` responde 401 y el usuario vuelve al login. No hace falta entrar a IA.
2. Cualquier llamada a `/ia-feedback/*`, `/calibracion/*` o `/admin-accesos/*` con el JWT anterior responde 401.
3. Si la página IA ya estaba abierta, la siguiente llamada (bandeja, estado, ficha, audio) responde 401 y la envía al login.

Los módulos todavía no migrados (lista abajo) **siguen respondiendo** a esa sesión hasta que se migren. Por eso la pantalla de Accesos CRM ya no dice que el corte es total.

## Fase 4 — Home como puerta de sesión

`home.html` ya **no confía en `localStorage`**. Al cargar (o al volver con "Atrás" desde la caché del navegador), Home espera `asegurarSesionBackend()` antes de pintar nada: nombre, perfil, carteras, módulos, tarjetas y mensajes.

| `GET /auth/me` | Resultado en Home |
| --- | --- |
| Sin `access_token` | Limpia la sesión y va a `login.html` ("Inicia sesión para continuar."). Esto también saca a las sesiones antiguas, anteriores al login con contraseña |
| 200 y `requiere_cambio_clave = false` | Actualiza `dni`, `agente`, `tipo`, `idcartera` e `idcarteras` con la respuesta y construye Home **con esos datos** |
| 200 y `requiere_cambio_clave = true` | Va a `cambiar_clave.html` sin mostrar Home |
| 401 | `localStorage` y `sessionStorage` limpios (solo queda `loginMensaje` = "Tu sesión ya no está habilitada. Inicia sesión nuevamente.") y va a `login.html`. Home no continúa |
| 5xx o sin respuesta | No muestra datos viejos. Home sigue oculto con un aviso técnico y "Reintentar". Las credenciales no se borran |

Detalles:

- **Sin datos viejos en pantalla:** `home.html` arranca con `body.home-validando-sesion` (contenido y usuario ocultos, texto "Validando sesión…"). La clase se quita solo cuando `/auth/me` respondió 200.
- **Perfil actualizado:** si SISCOB cambia al usuario, por ejemplo de SUPERVISOR a GESTOR, con el JWT todavía vigente, al recargar Home se ven el perfil, las carteras y los módulos nuevos.
- **`/auth/me` ahora devuelve `requiere_cambio_clave`,** leído de `CRM_USUARIO_ACCESO`. Así el cambio obligatorio se detecta aunque el administrador resetee la clave de un usuario que ya tenía sesión abierta. JWT y SQL no cambian: se reutiliza `cuenta_requiere_cambio_clave`.
- **Un solo cierre de sesión:** `cerrarSesionPorInvalidez(mensaje)` en `session.js` limpia el almacenamiento, conserva solo `loginMensaje` y redirige **una sola vez**, aunque varias llamadas reciban 401 al mismo tiempo. `cerrarSesionPorBackend()` (usado por IA y Consumo de IA) delega en ella. La redirección a `cambiar_clave.html` usa la misma protección.
- **Estado de la última validación:** `obtenerEstadoSesionBackend()` devuelve `VALIDA`, `SIN_TOKEN`, `REVOCADA`, `CAMBIO_OBLIGATORIO` o `ERROR_TECNICO`.
- **`app_layout.js` no participa:** `home.html` no lo carga (tiene su propia cabecera). En los demás módulos, el menú sigue construyéndose con `localStorage` hasta que se migren.

**`localStorage` queda solo como estado de UI y compatibilidad.** La autoridad es el backend (`/auth/me` y la validación de cada endpoint protegido).

### Límite importante

Home protegido **no significa** que los demás routers estén protegidos. La revocación se detecta al recargar Home o al usar un módulo migrado, pero si alguien llama directamente a un endpoint no migrado (`/pagos`, `/metas`, `/corporativo`, etc.), ese endpoint todavía responde sin validar la sesión. Cliente, Compromisos y Teléfonos se migraron en la Fase 5.

## Fase 5 — Cliente, Compromisos y Teléfonos

### Routers protegidos

Todos los endpoints de datos usan `Depends(requiere_clave_definitiva)`: JWT, `FLG_ACTIVO = 1`, SISCOB `Estado = 'A'` y sin cambio obligatorio pendiente. Sin sesión válida responden **401**; una cuenta deshabilitada recibe 401 aunque conserve su JWT.

| Router | Endpoints protegidos |
| --- | --- |
| `/cliente` | `GET /buscar` |
| `/compromisos` | `GET /{dni}`, `GET /detalle/{id}`, `GET /agente/compromisos`, `GET /supervisor/resumen`, `GET /supervisor/exportar-cartera` |
| `/telefonos` | `GET /buscar`, `GET /filtros`, `GET /detalle/{telefono}` |

Solo `GET /telefonos` (sirve el HTML) queda abierto.

### Páginas protegidas

`compartamos.html` (usa `core/api.js`), `compromisos.html`, `supervisor.html` (Compromisos supervisor) y `telefonos.html`. `telefonos.html` antes no cargaba `session.js`; ahora sí.

Las cuatro esperan `asegurarSesionBackend()` antes de pintar datos del usuario o llamar al backend. Envían el token con `fetchConSesion()`, el nuevo helper de `session.js`:

- Agrega `Authorization: Bearer` a cada llamada.
- Con 401 llama a `cerrarSesionPorInvalidez()`.
- Con el 403 de cambio obligatorio va a `cambiar_clave.html`.
- En ambos casos lanza `SesionInvalidaError` para que la página no siga.
- Cualquier otro 403 (acceso denegado) se devuelve a la página, que muestra el mensaje y se queda. La sesión no se toca. Ver "Códigos de error 403".

El export de supervisor ya no usa `window.open`, que no puede enviar el header: descarga con `fetchConSesion()`.

### Identidad

- El DNI, el perfil y las carteras salen de la sesión (`usuario_actual`), nunca del navegador.
- `/compromisos/supervisor/resumen` y `/exportar-cartera` **ignoran** el `dni` de la query y usan el DNI del JWT.
- Los parámetros `perfil`, `tipo`, `idcartera` o `idcarteras` en la query o el payload **no amplían** permisos. En Teléfonos, `idcartera` solo puede **acotar** dentro de las carteras permitidas; una cartera ajena da 403.
- `compromisos.js` ya no toma el agente de `localStorage` antes de validar. El agente propio sale de `/auth/me`. El `agente` de la URL o `agente_filtro` sigue siendo solo el filtro visual del supervisor, y el backend decide si puede verlo.

### Reglas de perfil y cartera (`app/core/autorizacion_carteras.py`)

Solo reglas que ya existían en el CRM:

| Regla | Origen |
| --- | --- |
| Visión global: ADMINISTRADOR, JEFE DE CARTERA, JEFE DE CARTERAS, JEFE DE COBRANZA, JEFE CARTERA | `puedeVerCorporativo()` (frontend) y `perfil_puede_editar_prompt()` (IA) |
| Supervisor: `TipoUsuario` que contiene SUPERVISOR | `esSupervisor()` |
| Monitor de calidad: solo Análisis IA (403 en estos módulos) | `puedeAccederModulo()` de `app_layout.js` |
| Carteras permitidas = `idcartera` principal + `idcarteras` adicionales (`CRM_SUPERVISOR_CARTERA`) | `obtener_identidad_usuario()` |
| Carteras Compartamos: 124, 126, 128, 133, 144 | `COMPARTAMOS_CARTERAS` de `cliente_crm_service`. `autorizacion_carteras` reutiliza esa constante: en el backend hay una sola lista |

Cómo se aplica en cada módulo:

| Módulo | Regla de cartera | Si no cumple |
| --- | --- | --- |
| **Cliente** | El usuario debe tener visión global o alguna cartera Compartamos (regla existente del módulo "Consulta Compartamos"). Sin visión global se aplica además la regla *fail closed* descrita abajo | 403 |
| **Compromisos: lo propio** | `/{dni}` con el DNI propio siempre se permite | — |
| **Compromisos: otro agente** (`/{dni}` ajeno o `/agente/compromisos`) | Visión global, o supervisor con la cartera principal del agente (`SISCOB.USUARIO.IDCARTERA`) entre sus carteras. Un gestor no ve a otros agentes | 403 |
| **Compromisos: detalle** | Autorización por objeto (ver abajo): propietario y cartera leídos de SISCOB | 403 |
| **Compromisos: supervisor** | `/supervisor/resumen` y `/exportar-cartera`: solo supervisores y visión global (regla existente de `supervisor.html`). La cartera sigue siendo la principal del supervisor, como antes | 403 |
| **Teléfonos** | `TEMP_TELEFONOS.IDCARTERA` debe estar entre las carteras del usuario. Se aplica en SQL (`AND IDCARTERA IN (...)`) en la búsqueda, y en Python en relacionados, detalle y la lista de carteras de los filtros | 403 (`idcartera` ajena) o sin filas |

Score, OSIPTEL, semaforización, prioridad y el conteo de contexto (`TOTAL_DNIS` y `TOTAL_CARTERAS` por teléfono) **no cambian**: siguen calculándose sobre todas las carteras, igual que antes.

### Cliente: regla *fail closed*

`VW_CLIENTE_CRM_SAC` no expone la cartera de cada operación, así que **no se puede filtrar operación por operación**. En la base existente no hay otra relación confiable operación → cartera: `SISCOB.CLIENTE` solo tiene `Dni` → `IdCartera`, y `SISCOB.COMPROMISO.NumOperacion` existe solo para operaciones con compromiso. No se inventó ninguna relación.

Por eso la decisión se toma sobre la **entidad completa**: todas las filas que se devolverían, incluidos todos los integrantes de un grupo. Para usuarios sin visión global:

1. Todas las filas deben tener DNI.
2. Cada DNI debe tener al menos una cartera Compartamos en `SISCOB.CLIENTE`. La consulta está en `carteras_compartamos_por_dni()`.
3. **Todas** esas carteras deben estar asignadas al usuario.

Si algo no se cumple, o no se puede determinar, responde **403** y no se devuelve ningún dato. Eso incluye el caso de SISCOB sin cartera para el DNI y un cliente multicartera con una sola cartera ajena. Si falla la consulta a SISCOB, responde 500 genérico, sin datos.

La verificación ocurre dentro de `buscar_cliente(valor, verificar_acceso=...)`, justo después de leer la vista y **antes** de consultar gestión, pagos y PDP. Sin el parámetro, el servicio se comporta igual que antes. La visión global no pasa por el verificador.

**Impacto operativo:** un gestor ya no puede consultar a un cliente que también tenga operaciones en otra cartera. Tampoco a un cliente que SISCOB no tenga registrado en una cartera Compartamos. Lo verá un perfil con visión global o un usuario con todas esas carteras asignadas.

### Compromisos: autorización por objeto en `/detalle/{id}`

El `SELECT` del detalle ahora trae también el propietario (`U.USUARIO` del agente que registró la gestión, el mismo criterio que usa el listado) y su cartera (`U.IDCARTERA`). Filtros y joins no cambian. Todo sale de SISCOB; nada del navegador.

| Perfil | Puede abrir |
| --- | --- |
| Visión global | Cualquier compromiso |
| Gestor (y cualquier perfil sin visión global) | Solo los suyos (propietario = su DNI) |
| Supervisor | Los suyos, y los de agentes cuya cartera (`USUARIO.IDCARTERA`) esté entre sus carteras, siempre que la cartera del compromiso (`GESTION.IDCARTERA`) también lo esté |
| Monitor de calidad | Nada (403) |

Si no hay propietario o cartera determinable, responde 403. Esto cierra el acceso por ID (IDOR): un gestor ya no abre el compromiso de otro gestor de su misma cartera.

### Códigos de error 403

Un 403 puede significar dos cosas distintas, así que el backend las marca con la cabecera **`X-CRM-Codigo-Error`**:

| Caso | Código | Frontend (`fetchConSesion`) |
| --- | --- | --- |
| 401 | — | Limpia la sesión y va a `login.html` |
| 403 por clave temporal (`requiere_clave_definitiva`) | `CAMBIO_CLAVE_OBLIGATORIO` | Va a `cambiar_clave.html` sin limpiar la sesión |
| 403 por perfil o cartera (`autorizacion_carteras.prohibido()`, `requiere_administrador`) | `ACCESO_DENEGADO` | Se queda en el módulo y muestra el mensaje. No limpia la sesión ni manda a cambiar la clave |

- El `detail` no cambió. Quien ya lo leía sigue funcionando.
- La cabecera va con `Access-Control-Expose-Headers`, así se puede leer desde otro origen sin modificar la configuración CORS.
- Si una respuesta 403 **no trae código** (routers aún no migrados), `esRespuestaCambioClave()` compara el `detail` exacto, como antes. Cualquier otro 403 se trata como acceso denegado.
- `esAccesoDenegado(response)` está disponible para las páginas.

### Cartera 139

Solo aparece en dos lugares del proyecto:

- `session.js`, en `esCarteraCompartamos()`: decide qué módulos muestra Home y el menú.
- `control_horario_service.py`, en `CARTERAS_EXCLUIDAS_CONTROL = {120, 139, 141, 146}` y en los `NOT IN` de SQL, como cartera **excluida** del control horario.

Ningún catálogo del proyecto la nombra: `CARTERAS` de control horario, score telefónico, documentos o `COMPARTAMOS_CARTERAS`. Las consultas Compartamos (`consultar_gestiones`, `consultar_pdp`) usan `IN (124, 126, 128, 133, 144)`. **No hay evidencia de que sea Compartamos**, así que no se agregó al backend.

Tampoco se quitó de `session.js`: en el código no queda registrado por qué se agregó, y la regla no es clara. El efecto es acotado. Un usuario cuya única cartera sea la 139 verá la opción de Consulta Compartamos, pero el backend le responderá 403. Pendiente: confirmar con negocio qué es la 139 y alinear `session.js`. Otra opción es que `/auth/me` informe si el usuario puede usar el módulo.

### Huecos pendientes en estos módulos

1. **Cliente — completitud de SISCOB:** la regla supone que `SISCOB.CLIENTE` registra todas las carteras de cada DNI. Si la vista trae una operación de una cartera en la que SISCOB no tiene al DNI, esa operación no se detecta. Para filtrar operación por operación hay que confirmar si la vista tiene, o puede exponer, un campo de cartera.
2. **Supervisor con carteras adicionales:** `/supervisor/resumen` y `/exportar-cartera` siguen usando solo la cartera principal del supervisor (comportamiento anterior, sin cambios). Las adicionales solo se usan para autorizar ver a un agente.
3. **`/admin-metas-agentes/resumen-agente`**, que usa `compromisos.js`, recibe el Bearer pero su router **sigue sin protección** (pertenece a Metas).
4. **Cartera 139:** ver arriba.
5. **Detalle de compromiso inexistente:** responde `{"msg": "No encontrado"}` (comportamiento anterior). Un usuario puede distinguir "no existe" de "no autorizado", pero no ve datos.

## Filtro por cartera todavía pendiente en IA

La autenticación ya es real, pero **no se aplica todavía `idcarteras` del usuario** en el módulo IA:

- **Acceso por ID (IDOR):** `GET /ia-feedback/{id}`, `/{id}/audio`, `/{id}/estado`, `/{id}/recalibraciones`, `POST /{id}/revision`, `/{id}/coaching`, `/{id}/agente` y `/{id}/analizar*`, más `/calibracion/{id}`, `/criterio`, `/{id}/resolver`, `/llamada/{id}/*` y `/{id}/recalcular`. Cualquier usuario autenticado puede abrir o modificar una evaluación de otra cartera si conoce su ID.
- **Listados:** `bandeja`, `listar` y `reporteria` filtran por supervisor (perfiles sin visión global) o no filtran (perfiles con visión global). No se cruzan con `idcarteras`. Lo mismo `calibracion/cola`.
- **Catálogos:** `GET /carteras` y `GET /agentes` devuelven todas las carteras o los agentes de la cartera pedida, sin validar que pertenezca al usuario.
- **Carga:** `POST /upload` acepta cualquier `cartera` del formulario.
- **Mensajes de error:** varios endpoints IA aún devuelven `detail=f"...{exc}"`. Hay que cambiarlos a un mensaje genérico con el detalle en el log.

Para resolverlo hay que decidir la regla por perfil (por ejemplo: supervisor = sus carteras, monitor de calidad = todas) y aplicarla en `ia_audio_service` y `calibracion_service`. Eso toca la lógica de IA, así que queda para una tarea aparte.

## Fase 6 — Todos los módulos exigen sesión y carga inicial de accesos (clave = DNI)

### Backend: autenticación en los 13 routers que faltaban

`/admin-metas-agentes`, `/admin-pautas-evaluacion`, `/admin-supervisores`, `/canales`, `/corporativo`, `/control-horario`, `/documentos`, `/importacion`, `/metas`, `/pagos`, `/planes-mejora`, `/score-telefonico` y `/susurro-ia` se registran en `app/main.py` con `dependencies=[Depends(requiere_sesion_api)]`.

`requiere_sesion_api` (en `app/core/auth_dependencies.py`) equivale a `requiere_clave_definitiva`: JWT válido, cuenta CRM activa, usuario activo en SISCOB y sin cambio de clave pendiente (401 / 403 `CAMBIO_CLAVE_OBLIGATORIO`). La única excepción es la **página HTML** de cada módulo (`GET /<modulo>`), porque el navegador no puede enviar `Authorization` al navegar y el HTML no contiene datos; la página consulta sus datos con el token. Cualquier ruta de dos o más segmentos (`/<modulo>/<algo>`) siempre exige sesión.

**Es autenticación, no autorización:** cualquier usuario con sesión válida puede llamar a estos endpoints aunque su perfil no vea ese módulo en el menú. Siguen pendientes (recomendado): restringir por perfil/cartera los módulos de administración e importación (`/admin-*`, `/importacion`, `/pagos`, `/metas/importar`, `/canales/importar`) y sustituir `usuario`/`perfil` que el navegador manda en payload/query por los de la sesión.

### Frontend

- Las llamadas de esos módulos usan `fetchConSesion()` (Bearer; 401 → login; 403 de cambio de clave → `cambiar_clave.html`).
- Las descargas que antes eran navegación directa (`location.href`, `window.open`, `<a href>`) usan `descargarArchivoConSesion()` (en `session.js`): control horario, corporativo y score telefónico. Los endpoints exponen `Content-Disposition` para conservar el nombre del archivo.
- `documentos.html` ahora carga `session.js`.
- `tools/susurro_capturador.py` (cliente externo de `/susurro-ia`) ahora necesita sesión: `--dni` (pide la clave), `--token` o `CRM_ACCESS_TOKEN`.
- Cualquier otro cliente externo (n8n, scripts, Postman) que llame a estos endpoints debe enviar `Authorization: Bearer <token>` obtenido en `POST /auth/login`.

### Clave inicial = DNI (`tools/crear_accesos_iniciales.py`)

Para el lanzamiento, los usuarios activos de SISCOB (`Estado = 'A'`, usuario de 8 dígitos) que aún no tienen cuenta CRM reciben una cuenta con **clave inicial = su DNI**, `FLG_ACTIVO = 1` y `FLG_CAMBIO_OBLIGATORIO = 1`. En el primer ingreso el CRM obliga a cambiarla; la política rechaza el DNI como clave nueva.

```
python tools/crear_accesos_iniciales.py                       # plan (dry-run), genera CSV en logs/
python tools/crear_accesos_iniciales.py --ejecutar            # crea las cuentas (pide escribir CONFIRMAR)
python tools/crear_accesos_iniciales.py --incluir-pendientes  # además, cuentas con clave temporal que nunca se usó
python tools/crear_accesos_iniciales.py --excluir-tipos ADMINISTRADOR   # deja perfiles fuera del lote
python tools/crear_accesos_iniciales.py --reporte             # quién sigue sin cambiar la clave
python tools/crear_accesos_iniciales.py --cerrar-ventana --ejecutar     # deshabilita las que no cambiaron
```

No toca cuentas con clave definitiva ni cuentas deshabilitadas a propósito. Las cuentas del lote quedan marcadas con `USUARIO_CREACION = 'LOTE_DNI'`.

**Riesgo:** el DNI no es secreto. Mientras una cuenta conserve la clave inicial, cualquiera que conozca el DNI puede entrar como esa persona y fijar su propia clave (el bloqueo por intentos no lo evita). Mitigación: ejecutar el lote el día del lanzamiento, pedir el cambio de inmediato, revisar `--reporte` a las 24-48 h y usar `--cerrar-ventana` con las que sigan pendientes (se reactivan con "Habilitar acceso", que entrega una clave aleatoria). Para perfiles con más alcance (administrador, jefes) se recomienda `--excluir-tipos` y habilitarlos uno a uno desde Administración de accesos.

### Tests de la fase

`tests.test_sesion_api` recorre todas las rutas reales de la aplicación y exige 401 sin token (salvo `/`, `/auth/login` y las páginas HTML). `tests.test_accesos_iniciales` cubre la clasificación del script y que nunca escribe sin `--ejecutar` y confirmación.

## Módulos pendientes de migración (histórico, resuelto en la Fase 6)

**Routers sin autenticación en el backend:** `/admin-metas-agentes`, `/admin-pautas-evaluacion`, `/admin-supervisores`, `/canales`, `/corporativo`, `/control-horario`, `/documentos`, `/importacion`, `/metas`, `/pagos`, `/planes-mejora`, `/score-telefonico` y `/susurro-ia`.

**Páginas que aún usan solo `exigirSesion()`:** corporativo, promesas hoy, metas, ritmo meta, control horario, matriz, importación, pagos, canales, documentos, susurro IA, score telefónico y las administraciones de supervisores, metas por agente y pautas de evaluación.

Para migrar cada módulo:
1. En el router, agregar `usuario: Dict = Depends(requiere_clave_definitiva)` a cada endpoint. Reemplazar `perfil` y `usuario` del payload por los de la sesión.
2. En la página, esperar `asegurarSesionBackend()` antes de cargar datos y usar `fetchConSesion()` en cada llamada.
3. Si el módulo maneja carteras, aplicar las reglas de `app/core/autorizacion_carteras.py`.

## Pendientes

1. **Migración del resto de módulos** (lista de arriba) y del filtro por cartera en IA.
2. **Otras páginas:** fuera de Home y las páginas migradas, `exigirSesion()` sigue validando solo `dni` y `agente` en `localStorage`. Un usuario deshabilitado que tenga abierta una de esas páginas puede seguir usándola hasta que recargue Home o entre a un módulo migrado.
3. **Fallos de la clave actual en el cambio de clave:** no suman a `INTENTOS_FALLIDOS` (quien lo intenta ya tiene un token válido). Evaluar si deben contar.
4. **Último administrador:** un administrador no puede deshabilitar su propia cuenta, pero sí a otro administrador. No hay una regla que garantice que quede al menos un administrador activo.
5. **Enlace a "Cambiar contraseña"** desde el menú o la barra superior, para el cambio voluntario. La pantalla ya existe.

## Primer administrador (arranque, solo por SQL)

El módulo de accesos exige un administrador autenticado, así que la **primera** cuenta de administrador se crea a mano. Las demás se crean desde la pantalla.

1. Generar el hash en el servidor del CRM. La contraseña se pide por teclado y no queda en el historial:

```
python -c "import getpass; from dotenv import load_dotenv; load_dotenv(); from app.core.security import generar_hash_clave; print(generar_hash_clave(getpass.getpass('Nueva clave: ')))"
```

2. Validar primero que el usuario está activo en SISCOB y que todavía no tiene cuenta:

```sql
SELECT U.USUARIO, U.Nombres, U.Apellidos, U.TipoUsuario, U.Estado
FROM SISCOB.dbo.USUARIO U WITH (NOLOCK)
WHERE LTRIM(RTRIM(U.USUARIO)) = '12345678';

SELECT * FROM CobAuto.dbo.CRM_USUARIO_ACCESO WHERE USUARIO = '12345678';
```

3. Crear la cuenta:

```sql
INSERT INTO CobAuto.dbo.CRM_USUARIO_ACCESO
    (USUARIO, PASSWORD_HASH, FLG_ACTIVO, FLG_CAMBIO_OBLIGATORIO, INTENTOS_FALLIDOS,
     FECHA_CAMBIO_CLAVE, USUARIO_CREACION)
VALUES
    ('12345678', '<hash generado en el paso 1>', 1, 1, 0, NULL, '<DNI del administrador>');
```

Desbloquear a mano (solo si no hay ningún administrador disponible; lo normal es usar la pantalla):

```sql
UPDATE CobAuto.dbo.CRM_USUARIO_ACCESO
SET INTENTOS_FALLIDOS = 0, BLOQUEADO_HASTA = NULL,
    USUARIO_ACTUALIZACION = '<DNI del administrador>', FECHA_ACTUALIZACION = SYSDATETIME()
WHERE USUARIO = '12345678';
```

## Tests

```
python -m unittest tests.test_auth tests.test_admin_accesos tests.test_ia_seguridad tests.test_sesion_frontend tests.test_modulos_cartera tests.test_sesion_api tests.test_accesos_iniciales -v
```

No usan la base de datos.
- Los tests HTTP (TestClient) requieren `httpx`. Si no está instalado, se saltan; en ese caso casi todo `tests.test_ia_seguridad` y `tests.test_modulos_cartera` queda sin ejecutar. Instálalo con `pip install httpx`.
- `tests.test_sesion_frontend` ejecuta `tests/frontend/sesion_frontend.test.js` con Node. Si Node no está en el PATH, se salta.
