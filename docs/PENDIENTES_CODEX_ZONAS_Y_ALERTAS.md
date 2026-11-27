# Pendientes para Codex · Zonas restringidas y alertas del CRM

Escrito por Claude el 27/11/2026, al cerrar la primera versión de **Zonas restringidas**. Hardy la validó y se la mostró a gerencia.
Lee este documento completo antes de tocar código. Cada tarea dice qué hacer, en qué archivos y cuándo se da por terminada.

---

## 0. Reglas del proyecto (obligatorias)

1. **No inventes datos, columnas ni tablas.** Usa solo estructuras que ya existen en el código o en `tools/sql`. Si falta un dato, deja la tarea marcada como bloqueada y escribe qué necesitas. No asumas.
2. **No leas ni imprimas `.env`, claves ni credenciales.** Nada de secretos en logs, respuestas ni commits.
3. **Archivos con fin de línea CRLF** (Windows), igual que el resto del repositorio. No cambies los finales de línea de archivos que no tocas.
4. **Versión de los assets:** en las vistas (`frontend/views/*.html`), cada `?v=` de un `.js`/`.css` son los **primeros 10 caracteres del SHA-1 del archivo tal como queda guardado** (CRLF). Si cambias un JS/CSS, actualiza su `?v=` en todas las vistas que lo cargan.
5. **SQL:** el script es completo y autocontenido (`USE CobAuto; GO` …) y se puede correr más de una vez.
   - `CREATE OR ALTER VIEW/PROCEDURE` va solo en su bloque, con `GO` antes y después.
   - CobAuto **no** admite `STRING_SPLIT` ni `STRING_AGG` por su nivel de compatibilidad: usa `VALUES` y `STUFF(... FOR XML PATH(''))`.
   - Antes de un `UPDATE`/`DELETE`, deja una consulta para revisar qué filas cambian.
   - Los scripts los corre Hardy; tú no tienes acceso a la base.
6. **Pruebas:** `python -m pytest -q` desde la raíz debe pasar completo (523 pruebas al 27/11; 2 de IA fallaban antes de T1, ver sección 4). Cada cambio de lógica en Python lleva su prueba en `tests/`.
7. **Permisos:** todo endpoint nuevo exige sesión (`requiere_clave_definitiva`) y valida el perfil en el backend con `app/core/autorizacion_carteras.py` (`tiene_vision_global`, `es_supervisor`, `carteras_permitidas`, `prohibido`). El frontend solo oculta botones; la seguridad está en el backend.
8. **Versión para probar vs. producción:** no agregues validaciones, bloqueos ni capas que no se pidieron. Si ves algo necesario para producción, anótalo al final de este documento.
9. **Idioma:** textos de la interfaz, mensajes y comentarios en español, directos y sin tecnicismos para el usuario final.

---

## 1. Contexto: qué existe hoy

**Objetivo:** dejar de gestionar los departamentos que un banco ordena (Interbank pidió detener Piura el 27/11/2026) o que Biznescob decide (lluvias, El Niño). El generador de bases quita a esos clientes.

**Base de datos (CobAuto, esquema `score`):**
- `tools/sql/score_telefonico_fase19_zonas.sql` crea las tablas y la vista:
  - `score.ZonaRestringida`: IdZona, Nivel, Valor, Motivo, Origen BANCO/INTERNO, Desde, Hasta, Activo, AplicaTodas, traza de registro y de baja;
  - `score.ZonaRestringidaCartera`: IdZona, IdCartera;
  - `score.vw_ClienteZonaRestringida`: clientes que hoy caen en una restricción vigente, por cartera.
- `tools/sql/score_telefonico_fase20_zonas_mapa.sql`: la vista compara sin tildes (`COLLATE Latin1_General_CI_AI`), y el script trae un diagnóstico de valores no reconocidos.
- La ubicación del cliente sale de `score.vw_DatoCliente` (Campo = 'DEPARTAMENTO') según `score.CampoCartera`.
- Restricción activa: IdZona 1, PIURA, BANCO, todas las carteras.

**Generador:** `app/services/generador_bases_reglas.py` (`construir_consulta(..., zonas=True)`) y `generador_bases_service.hay_zonas` agregan el paso forzado "Sin zona restringida".

**Pantalla:** `frontend/views/zonas.html` + `frontend/js/zonas.js` + `frontend/js/zonas_mapa_peru.js` (contornos SVG) + `frontend/css/zonas.css`.

**API:** `app/api/routes_zonas_restringidas.py` (prefijo `/zonas-restringidas`), con la lógica en `app/services/zonas_restringidas_service.py`:
- `GET /estado`, `GET /excluidos`, `GET /cobertura`, `GET /excel`;
- `POST /simular`, `POST ""` (registrar), `POST /levantar`;
- ver: jefes y supervisores; registrar y levantar: visión global.

**Definiciones** (no cambiarlas sin hablar con Hardy):
- **PDP vigente:** `siscob.dbo.COMPROMISO`, FechaCompromiso ≥ hoy, Monto > 0 y PAGADO distinto de SI/S. Es la misma regla del filtro "PDP vigente" del generador.
- **Cobertura:** sobre la base de trabajo (`score.vw_BaseTrabajo`, DNI distintos).
  - "Con departamento": al menos un valor que es uno de los 25 departamentos.
  - "No reconocido": tiene valor, pero ninguno es un departamento.
  - "Sin valor": no trae el dato.

---

## 2. Tareas para Codex (independientes; hazlas en este orden)

### T1 · Actualizar el `?v=` de `app_layout.js` y `home.js` en todas las vistas
El 27/11 se agregó "Zonas restringidas" al menú (`frontend/js/app_layout.js`) y a Home (`frontend/js/home.js`). Solo se actualizó el `?v=` en `zonas.html`, `segmentos.html`, `score_telefonico.html`, `score_rendimiento.html`, `respuestas_mowa.html` y `home.html`. Las demás vistas pueden mostrar el menú viejo por caché del navegador.
- **Qué hacer:** calcular el SHA-1 actual de `frontend/js/app_layout.js` (y de `home.js`) y dejar ese `?v=` en **todas** las vistas que los cargan. No tocar nada más de esas vistas.
- **Terminado cuando:** `grep "app_layout.js?v="` muestra un único valor en todas las vistas.

### T2 · Pruebas de permisos de las rutas de zonas
- **Qué hacer:** pruebas en `tests/test_zonas_restringidas_rutas.py` con `TestClient`, siguiendo el patrón de `tests/test_sesion_api.py` y `tests/test_admin_accesos.py` (revisa ahí cómo simulan la sesión y el perfil del usuario). Deben cubrir:
  - un SUPERVISOR puede `GET /estado`, pero `POST /zonas-restringidas` y `POST /levantar` responden 403;
  - un AGENTE recibe 403 en `GET /estado`;
  - `GET /excel?idcartera=X` responde 403 si X no está en `carteras_permitidas` del usuario.
- Simula la base: no abras conexiones reales. Sustituye `engine_siscob` o las funciones del servicio con `unittest.mock.patch`.
- **Terminado cuando:** las pruebas nuevas pasan junto con las 70 existentes.

### T3 · Caché corto para `/cobertura` y medición de tiempos
`/cobertura` y `/excel` recorren toda la base de trabajo y pueden tardar varios segundos.
- **Qué hacer:**
  - caché en memoria del resultado de `zonas_restringidas_service.cobertura` por **10 minutos**, una sola entrada global con su hora de cálculo;
  - el endpoint devuelve también `calculado_en` (hora) y la pantalla lo muestra junto al título de la tabla de carteras: "calculado 10:42";
  - parámetro `?refrescar=1` para forzar el recálculo, y un botón "Recalcular" en la tabla de carteras que lo use;
  - registrar en el log cuánto tardó cada cálculo de `/cobertura` y de `/excel`.
- No caches `/estado` ni `/excluidos`: deben reflejar al instante una restricción nueva.
- **Terminado cuando:** hay una prueba de la caché (segunda llamada sin consultar la base; `refrescar=1` sí consulta) y la pantalla muestra la hora.

### T4 · Burbuja de alertas global del CRM (versión 1)
Hardy la pidió el 27/11: una burbuja abajo a la derecha, en todas las pantallas, que al cargar o actualizar muestre las alertas.
- **Backend:** `GET /alertas/resumen`, en un router nuevo `app/api/routes_alertas.py` registrado en `app/main.py`. Devuelve una lista de `{id, tipo, nivel: "rojo"|"ambar"|"info", titulo, detalle, enlace}`. Fuentes de la v1:
  1. **Zonas restringidas vigentes:** una alerta por restricción vigente o programada. Lee `score.ZonaRestringida` (Activo = 1, con la misma lógica de "Estado" que `zonas_restringidas_service.zonas`; reutiliza esa función). Enlace: `zonas.html`. Visible para todos los perfiles, porque los agentes también deben saber que no se gestiona Piura.
  2. **Respuestas SMS sin atender**, solo si ya hay en `app/services/respuestas_mowa_service.py` o `respuestas_sms_tabla.py` una función que cuente las pendientes, respetando las carteras del usuario. **No inventes la regla de "sin atender":** si no existe, deja esta fuente fuera y anótalo al final de este documento.
  3. **La asignación de clientes queda fuera de la v1**: espera a la bandeja del agente.
- **Frontend** (`frontend/js/app_layout.js` + `frontend/css/app_layout.css`):
  - botón flotante abajo a la derecha con un contador;
  - al hacer clic, se abre un panel con la lista (color según nivel, enlace a la pantalla);
  - se consulta al cargar cada página y cada 5 minutos;
  - "Marcar como vista" por alerta, guardado en `localStorage` por id y fecha. Si la alerta cambia de contenido, vuelve a aparecer;
  - no aparece en `login.html` ni en `cambiar_clave.html`;
  - si el endpoint falla, la burbuja se oculta en silencio, sin mensajes de error al agente.
- **Terminado cuando:** hay pruebas del endpoint (perfiles y forma de la respuesta), y T1 se repite para el nuevo `?v=` de `app_layout.js`/`app_layout.css`.

### T5 · Mecanismo de equivalencias de departamento (sin datos)
Algunas carteras traen valores que no son ninguno de los 25 departamentos. MiBanco (112) tiene 342 clientes así.
- **Qué hacer:** `tools/sql/score_telefonico_fase21_equivalencias.sql`:
  - tabla `score.DepartamentoEquivalencia (Valor NVARCHAR(100) PK, Departamento VARCHAR(40) NOT NULL, UsuarioRegistro, FechaRegistro)`, con un CHECK de que Departamento sea uno de los 25 (la lista está en `DEPARTAMENTOS` de `zonas_restringidas_service.py`);
  - `score.vw_ClienteZonaRestringida` traduce el valor con esa tabla antes de comparar;
  - `cobertura()` y `simular()` aplican la misma traducción.
- **No cargues filas:** las equivalencias las define Hardy. Deja en el script un bloque comentado de ejemplo para insertarlas.
- **Terminado cuando:** las pruebas cubren que un valor equivalente cuenta como "Con departamento".

### T4.1 · Ajustes a la burbuja (revisión de Claude, 27/11)
T4 quedó bien. Faltan cinco ajustes; ninguno cambia reglas de negocio:
1. **Que una falla de SMS no apague las zonas.** Hoy, si `sms.sin_atender` lanza un error, `/alertas/resumen` responde 503 y la burbuja se oculta, también para la alerta de Piura, que es la crítica. Encierra la parte SMS en su propio `try/except`: registra el error en el log y devuelve igual las alertas de zonas.
2. **Caché de 3 minutos para el conteo SMS**, con clave por las carteras permitidas (`None` = todas). El CRM recarga la página en cada navegación, así que sin caché `sin_atender` corre cada vez que un supervisor cambia de pantalla. Sigue el patrón de la caché de `/cobertura` (lock y hora de cálculo). Las zonas no se cachean: dos consultas livianas, y deben verse al instante.
3. **Enlace solo si el usuario puede abrir la pantalla.** Para quien no tiene acceso a `zonas.html` (el agente), `enlace` = `null` y la burbuja no muestra "Abrir pantalla": el aviso basta. Usa la misma regla de acceso que la ruta (visión global o supervisor). Lo mismo para `respuestas_mowa.html`.
4. **Fechas en formato dd/mm/aaaa** en el detalle de la zona (hoy sale 2026-11-27).
5. **Que la alerta SMS no reaparezca por cada cambio del conteo.** Hoy la firma incluye el detalle, así que vuelve a salir cada vez que cambia el número. Debe volver a salir solo si el número **sube** respecto del que estaba al marcarla como vista, o si cambia el día. Las alertas de zona siguen como están: reaparecen si cambia su contenido.

- **Terminado cuando:** hay pruebas de (1), (2) y (3), la suite pasa (salvo los 2 fallos de IA ya conocidos) y el `?v=` de `app_layout.js` está actualizado en todas las vistas.

---

## 3. Bloqueadas: necesitan a Hardy (no las resuelvas por tu cuenta)

| Tema | Qué falta |
|---|---|
| Valores no reconocidos (2) | Hardy debe pasar los 2 valores (pantalla → "Valores de departamento que no se reconocen" o fase20, sección 2). Con ellos se cargan las equivalencias de T5. |
| 126 Vigente IND (2.7 %) y 128 CCM (3 %) con departamento | La fuente (`Compartamos_Vigente_Cobranzas.dbo.VW_COMPARTAMOS_VIGENTE_CLIENTE_BI_ANALITICO`) casi no cruza con la base de trabajo. Hay que revisar con qué llave se une en `score.CampoCartera`. Codex puede escribir un **diagnóstico de solo lectura**, pero el arreglo depende del resultado. |
| Departamento de 124, 132, 133 y 144 | Hardy lo está armando. Fuentes candidatas: FOH 132 → `MASTER_ASIGNACION_FOH` (DEPARTAMENTO_DOMICILIARIA, UBIGEO); grupal 133 → `Distrito_Principal` + `Desarrollo.dbo.Zona_Region`; castigo grupal → `compartamos_grupal_castigo.NomDepartamento`. Confirmar llaves antes de cargar. |
| Macrozonas y semáforo | Las propuso Claude: constante `ZONAS` y umbrales `UMBRAL_OK = 0.98`, `UMBRAL_REVISAR = 0.90` en `zonas.js`. Cambiarlos solo si Hardy lo pide. |
| Qué hacer con los clientes con PDP en zona | Es una decisión de negocio (si se les recuerda la PDP o no). La pantalla solo informa. |
| Alertas SENAMHI (lluvias, calor) | Fase 2. Falta definir la fuente. |

---

## 4. Notas de Codex
(Anota aquí lo que dejaste pendiente, lo que necesitas de Hardy y lo que sería necesario para producción.)

- **T1 a T3 (27/11/2026):** terminadas. Las 26 vistas que cargan `app_layout.js` usan el SHA-1 `57154c8936`; `home.js` usa `a4ddd1539f`. Se añadieron pruebas de permisos y de caché sin conexión real. `/cobertura` guarda una entrada global durante 10 minutos, expone `calculado_en` y acepta `?refrescar=1`; la pantalla muestra la hora y permite recalcular. Los cálculos de cobertura y Excel registran su duración en el log.
- **Pruebas:** las 4 pruebas nuevas pasan. `python -m pytest -q` terminó con **521 aprobadas y 2 fallidas** (145 subpruebas aprobadas); los dos fallos se repiten al ejecutarlos aislados: `test_ia_feedback_stability.py::IaFeedbackStabilityTests::test_coercion_and_humiliation_are_not_accepted_as_negotiation` no encuentra la evidencia «manejando», y `test_ia_reporteria_cache.py::CacheReporteriaIaTests::test_recarga_reusa_respuesta_y_cambio_en_sql_la_invalida` espera `_REPORTERIA_CACHE`, ausente en `ia_audio_service`. Estos archivos no se tocaron en T1 a T3. Queda pendiente resolverlos para que pase la suite completa.
- **Verificación pendiente:** no hubo conexión a CobAuto ni medición con datos reales. La duración aparecerá en el log cuando se consulten `/cobertura` y `/excel` en un entorno con base. La caché es por proceso; si producción usa varios procesos, cada uno tendrá su propia entrada y hora de cálculo. Conviene revisar ese comportamiento antes de desplegar.
- **T4 (27/11/2026):** terminada. `/alertas/resumen` reutiliza `zonas_restringidas_service.zonas` para restricciones vigentes y programadas, visibles para todos los perfiles con sesión. La fuente SMS sí existe: `respuestas_sms_tabla.sin_atender(carteras_permitidas)` cuenta clientes con respuestas pendientes según la regla ya usada por `/respuestas-mowa/sin-atender`. Su alerta se muestra a jefes y supervisores con acceso a Respuestas SMS; el agente recibe solo las alertas de zonas. La burbuja se consulta al cargar y cada 5 minutos, permite marcar cada alerta como vista por usuario, id y fecha, y vuelve a mostrarla si cambia su contenido. Está en las 28 vistas que cargan `app_layout.js`, incluida Inicio y la vista antigua del score; `generador_bases.html` solo redirige al generador actual. No aparece en login ni en cambio de clave.
- **Pruebas de T4:** 6 pruebas del endpoint con fuentes simuladas y 1 prueba del flujo de la burbuja pasan. La ejecución final de `python -m pytest -q` terminó con **528 aprobadas y 2 fallidas** (145 subpruebas aprobadas). Son los mismos dos fallos de IA anotados arriba; no se cambiaron esos módulos.
- **Verificación pendiente para producción:** no se probó contra CobAuto ni en navegador real. Hay que comprobar los tiempos de `sin_atender` al consultar alertas desde cada pantalla y cada 5 minutos, y verificar el panel en móvil. Si la consulta SMS es parcial, la alerta dice «Al menos» y «Consulta parcial» cuando ya encontró clientes; con cero clientes y consulta parcial no puede confirmar que no haya pendientes. Los agentes ven el aviso de zona, pero el enlace `zonas.html` conserva el acceso restringido de su pantalla; decidir si también deben poder abrir el detalle.
- **Fuera del alcance solicitado:** T5 (equivalencias de departamento) sigue pendiente. Para cargar sus equivalencias se necesitan los dos valores no reconocidos de la sección 3; Codex no los dedujo ni cargó.
