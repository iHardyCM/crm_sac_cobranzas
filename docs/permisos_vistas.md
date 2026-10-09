# Usuarios y permisos de vistas

El administrador entra a **Configuración → Usuarios**, busca a una persona y pulsa **Vistas**. Cada interruptor guarda el cambio de inmediato. **Restablecer permisos del perfil** elimina todas las excepciones del usuario.

La primera versión administra estas vistas, que ya cuentan con sesión validada en la API: Consulta Compartamos, Mis compromisos, Compromisos del equipo, Validación de teléfonos y Análisis IA. Configuración y las pantallas gerenciales siguen reservadas a sus perfiles actuales. Una concesión de vista no amplía las carteras asignadas por SISCOB; Consulta Compartamos solo puede habilitarse si existe una cartera Compartamos asignada.

## Instalación

Antes de publicar este código, ejecutar [crear_crm_usuario_vista.sql](../tools/sql/crear_crm_usuario_vista.sql) en `CobAuto`. El código consulta la tabla en `/auth/me` y en las APIs autenticadas, por lo que la migración debe estar aplicada primero. No se han aplicado cambios en una base real desde este desarrollo local.

La tabla guarda únicamente las excepciones al perfil (`PERMITIDO = 1` o `0`), el administrador que hizo el último cambio y la fecha. Si no hay fila, se aplica el permiso base. Cada petición vuelve a leer las excepciones, por lo que una revocación se aplica a la siguiente llamada aunque el usuario conserve su sesión abierta.

Las vistas restantes del CRM aún no se ofrecen en este mantenedor porque sus endpoints o su alcance de datos no tienen un contrato de autorización por usuario y cartera completo. Incorporarlas exige proteger esas APIs y verificar sus acciones antes de mostrar un interruptor que prometa revocación efectiva.
