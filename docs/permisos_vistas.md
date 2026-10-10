# Usuarios y permisos de vistas

El administrador entra a **Configuración → Usuarios**, filtra por cartera principal o busca a una persona y pulsa **Vistas** o **Carteras**. Cada interruptor guarda el cambio de inmediato. **Restablecer permisos del perfil** elimina las excepciones de vistas del usuario.

La primera versión administra estas vistas, que ya cuentan con sesión validada en la API: Radar Compartamos, Mis compromisos, Compromisos del equipo, Validación de teléfonos y Análisis IA. Configuración y las pantallas gerenciales siguen reservadas a sus perfiles actuales. Una concesión de vista no amplía las carteras asignadas por SISCOB; Radar Compartamos solo puede habilitarse si existe una cartera Compartamos asignada.

El botón **Carteras** del mismo usuario administra las carteras adicionales mediante la tabla existente `CobAuto.dbo.CRM_SUPERVISOR_CARTERA`, que el backend incorpora a la identidad en cada petición. La cartera principal de SISCOB aparece marcada y no se puede quitar aquí. Los cambios se guardan por interruptor y afectan a los módulos que hacen cumplir el alcance de cartera, como Compromisos del equipo y Validación de teléfonos. El permiso de vista y el alcance de cartera son controles distintos: para consultar un módulo protegido se necesitan ambos. No se crea una segunda tabla de asignaciones.

El mantenimiento anterior de supervisores utiliza esa misma tabla y ahora exige perfil administrador en todas sus APIs; el DNI de auditoría procede del token validado.

Para revisar a todos los usuarios Compartamos con su cartera principal, cuenta CRM, excepción de Radar y carteras adicionales, ejecutar la consulta de solo lectura [diagnostico_usuarios_radar_compartamos.sql](../tools/sql/diagnostico_usuarios_radar_compartamos.sql) en el servidor SQL autorizado. El filtro de la pantalla permite revisar una cartera principal, por ejemplo 126, y abrir **Carteras** en cada usuario.

Radar Compartamos aplica una regla de consulta propia: quien tiene una cartera Compartamos y la vista habilitada puede consultar cualquiera de las carteras Compartamos definidas en `COMPARTAMOS_CARTERAS`. Cuando el resultado pertenece a una cartera fuera de su asignación, se muestra un aviso con sus nombres e identificadores. Esto no agrega una asignación operativa ni cambia el alcance de los otros módulos.

## Instalación

Antes de publicar este código, ejecutar [crear_crm_usuario_vista.sql](../tools/sql/crear_crm_usuario_vista.sql) en `CobAuto`. El código consulta la tabla en `/auth/me` y en las APIs autenticadas, por lo que la migración debe estar aplicada primero. No se han aplicado cambios en una base real desde este desarrollo local.

La tabla guarda únicamente las excepciones al perfil (`PERMITIDO = 1` o `0`), el administrador que hizo el último cambio y la fecha. Si no hay fila, se aplica el permiso base. Cada petición vuelve a leer las excepciones, por lo que una revocación se aplica a la siguiente llamada aunque el usuario conserve su sesión abierta.

Las vistas restantes del CRM aún no se ofrecen en este mantenedor porque sus endpoints o su alcance de datos no tienen un contrato de autorización por usuario y cartera completo. Incorporarlas exige proteger esas APIs y verificar sus acciones antes de mostrar un interruptor que prometa revocación efectiva. La lista de carteras adicionales no convierte automáticamente todos los módulos del CRM en vistas restringidas por cartera.
