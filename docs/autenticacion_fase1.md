# Autenticación CRM — Fase 1 (rama `hardening/security-phase1`)

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

- Los otros endpoints siguen sin proteger.
- CORS, `NOLOCK` y las conexiones SQL siguen como estaban.
- El frontend sigue guardando `dni`, `agente`, `tipo`, `idcartera` e `idcarteras` en `localStorage` para no romper las pantallas. **Esos datos no son seguridad.** La credencial real es `access_token`.

## Pendientes

1. **Alta inicial de acceso por administrador.** Hoy no existe pantalla ni endpoint. Mientras tanto se hace a mano (ver abajo). No se permite autorregistro con solo el DNI.
2. **Reset de contraseña por administrador.**
3. **Cambio obligatorio de contraseña.** El login devuelve `requiere_cambio_clave = true` y el frontend lo guarda en `localStorage.requiere_cambio_clave`, pero todavía deja entrar. Falta un endpoint de cambio de clave del propio usuario autenticado y su pantalla. Hay que acordarlo antes de construirlo.
4. **Migración progresiva:** que el frontend envíe el token en cada `fetch` desde un solo helper, y proteger los routers con `Depends(obtener_usuario_actual)`.
5. **Sesiones antiguas:** `exigirSesion()` (en `session.js`) aún valida solo `dni` y `agente`. Quien ya tenía sesión abierta antes del cambio sigue entrando a las pantallas hasta cerrar sesión. Se corrige al exigir `access_token` en la fase de migración del frontend.

## Alta manual de una cuenta (solo para probar, hasta que exista la pantalla)

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
    ('12345678', '<hash generado en el paso 1>', 1, 1, 0, SYSDATETIME(), '<DNI del administrador>');
```

Desbloquear a mano a un usuario:

```sql
UPDATE CobAuto.dbo.CRM_USUARIO_ACCESO
SET INTENTOS_FALLIDOS = 0, BLOQUEADO_HASTA = NULL,
    USUARIO_ACTUALIZACION = '<DNI del administrador>', FECHA_ACTUALIZACION = SYSDATETIME()
WHERE USUARIO = '12345678';
```

## Tests

```
python -m unittest tests.test_auth -v
```

No usan la base de datos. Los tests HTTP (`/auth/me`) requieren `httpx`; si no está instalado, se saltan.
