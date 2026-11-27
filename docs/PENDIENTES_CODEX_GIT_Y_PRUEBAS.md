# Pendientes para Codex · Datos de clientes fuera de git y pruebas de IA

Escrito por Claude el 27/11/2026. Lee también la sección 0 de `docs/PENDIENTES_CODEX_ZONAS_Y_ALERTAS.md`: esas reglas valen aquí (no inventar, no leer `.env`, CRLF, pruebas).
Haz **solo** las tareas que Hardy te pida, en orden. Anota todo en la sección "Notas de Codex" al final.

---

## T6 · Sacar de git las carpetas con datos de clientes

**Por qué:** varias carpetas del repositorio guardan archivos con DNI, montos o resultados de consultas a la base, y el `.gitignore` no las excluye. Por ejemplo, `tools/salidas/` tiene el convenio generado de un cliente. Si se suben a un remoto, esos datos salen de la empresa.

**Qué hacer:**
1. Agrega al `.gitignore`, en la sección "Archivos cargados / datos de clientes", con un comentario breve:
   - `tools/entradas/`
   - `tools/salidas/`
   - `output/`
   - `Claude outputs/`
   - `/tmp*/` (las carpetas temporales de la raíz, como `tmphoy_0wnc/` y `tmpu5pf4d7o/`; ya existe `tmp/`)
   - `.pytest_cache/`
2. Revisa qué archivos de esas rutas **ya están en el índice**: `git ls-files -- <ruta>`.
3. Sácalos del seguimiento **sin borrarlos del disco**: `git rm -r --cached -- <ruta>`. Nunca uses `git rm` sin `--cached`.
4. Revisa si alguno de esos archivos **ya estuvo en commits anteriores**: `git log --all --oneline -- <ruta>`. Solo informa el resultado.

**Prohibido en esta tarea:**
- reescribir la historia (`git filter-repo`, BFG, `rebase` o `commit --amend` sobre commits ya hechos);
- `push`, y menos `push --force`;
- borrar archivos del disco;
- abrir, copiar o mostrar el contenido de los archivos con datos de clientes. Basta con sus nombres.

**Terminado cuando:**
- `git status` muestra el `.gitignore` modificado y los archivos que salieron del índice;
- `git ls-files` ya no devuelve nada en esas rutas;
- en las notas está la lista de rutas sacadas del índice y si aparecen en commits anteriores. Limpiar la historia lo decide Hardy.

---

## T7 · Diagnosticar las 2 pruebas de IA que fallan (sin arreglarlas todavía)

Fallan desde antes de T1 y no tienen relación con zonas:
- `tests/test_ia_feedback_stability.py::IaFeedbackStabilityTests::test_coercion_and_humiliation_are_not_accepted_as_negotiation`: no encuentra la evidencia «manejando».
- `tests/test_ia_reporteria_cache.py::CacheReporteriaIaTests::test_recarga_reusa_respuesta_y_cambio_en_sql_la_invalida`: espera `_REPORTERIA_CACHE`, que ya no existe en `ia_audio_service`.

**Qué hacer, para cada una:**
1. Con `git log` y `git blame`, encuentra cuándo cambió el código que prueba y cuándo cambió la prueba por última vez.
2. Determina cuál quedó desactualizado:
   - **la prueba**: el código cambió a propósito (un refactor, otra regla) y la prueba no se actualizó;
   - **el código**: se perdió un comportamiento que la prueba protegía. Por ejemplo, la caché de reportería ya no existe o ya no se invalida cuando cambia el SQL, o la evaluación de IA ahora acepta coerción o humillación como negociación.
3. Si es el código, describe el impacto para el usuario. Ejemplos: "la reportería de IA ya no usa caché y cada recarga vuelve a consultar"; "una llamada con amenazas al cliente se califica como negociación".

**No modifiques código ni pruebas en esta tarea.** Escribe en las notas el diagnóstico de cada una, con la evidencia (commits y líneas) y la corrección que propones. Hardy decide si se aplica.

**Terminado cuando:** las notas tienen, para cada prueba, qué lado quedó desactualizado, la evidencia y la propuesta.

---

## Notas de Codex

### T6 · Índice y antecedentes (27/11/2026)

- Añadí a `.gitignore`, bajo "Archivos cargados / datos de clientes", las seis exclusiones pedidas: `tools/entradas/`, `tools/salidas/`, `output/`, `Claude outputs/`, `/tmp*/` y `.pytest_cache/`.
- `git ls-files` identificó 87 archivos ya seguidos. Los retiré **solo del índice** con `git rm -r --cached`: `tools/entradas/` (3), `tools/salidas/` (57), `output/` (7) y `Claude outputs/` (20). No había archivos seguidos bajo `/tmp*/` ni `.pytest_cache/`. Los 87 archivos siguen en disco; `git ls-files` ya no devuelve archivos en ninguna de las seis rutas. `git status` muestra `.gitignore` modificado y las 87 bajas del índice.
- `git log --all --oneline -- <ruta>` confirma antecedentes: `tools/entradas/` en `5e7a681`; `tools/salidas/` en `2c43d21`, `5e7a681`, `0eb9d63`; `output/` en `0eb9d63`; `Claude outputs/` en `191d37d`, `0eb9d63`, `debccc4`, `df21e52`, `b53072a`. No hay antecedentes para `/tmp*/` ni `.pytest_cache/` con ese patrón. La limpieza del historial, si se decide, queda para Hardy. No reescribí historia ni hice push.

### T7 · Diagnóstico de pruebas de IA (27/11/2026)

1. **Negociación Mibanco: prueba desactualizada en su expectativa de evidencia.** La prueba y la exigencia de citar «manejando» (líneas 274-297 de `tests/test_ia_feedback_stability.py`) son de `d75d11c` (31/08/2026; `git blame`); el último cambio del archivo de pruebas fue `ac16123` (09/09/2026). Luego `db6f8a7` (18/09/2026) cambió `app/services/ia_analysis_service.py`: en `PECN.4`, líneas 3859-3869 actuales, el incumplimiento por ausencia de promesa o siguiente acción pasa `[]` como evidencia, con un comentario explícito que evita citar una frase final que no demuestra esa ausencia. Antes se llamaba `evidencia_ausencia_cierre_mibanco_v3(...)`. La prueba actual sí confirma `NO_CUMPLE` para `PECUF.1`, `PECN.2`, `PECN.3` y `PECN.4`; falla solo al exigir la cita del cliente. No hay evidencia aquí de que coerción o humillación se acepten como negociación. **Propuesta:** actualizar únicamente la aserción de evidencia de `PECN.4` para comprobar la ausencia declarada y conservar las aserciones de calificación y la evidencia directa de la descalificación en `PECUF.1`.
2. **Caché de reportería: código desactualizado respecto del comportamiento protegido.** `debccc4` (22/09/2026, 08:34) añadió `tests/test_ia_reporteria_cache.py` y la caché con firma SQL, reutilización e invalidación; `git blame` atribuye la prueba completa (líneas 57-79) a ese commit y `git log` no muestra cambios posteriores en ella. `4ccfd79` (22/09/2026, 08:57) retiró `_REPORTERIA_CACHE`, `_firma_reporteria` y `_enriquecer_fila_reporteria` de `app/services/ia_audio_service.py`, además de la comprobación de firma y la reutilización; la función actual (líneas 689-714) hace una lectura completa en cada llamada. La ruta `app/api/routes_ia_feedback.py:420-440` usa esa función con `fuente=json`, su valor predeterminado; `fuente=sql` es una alternativa explícita. **Impacto:** cada recarga predeterminada vuelve a consultar y enriquecer todas las filas solicitadas, perdiendo la aceleración que `debccc4` había medido (17,8 s en frío frente a 1,46 s con caché, según su mensaje de commit). La lectura directa refleja cambios de SQL, pero ya no hay reutilización ni invalidación de caché que probar. **Propuesta:** restaurar una caché acotada con verificación de cambios de las columnas efectivamente consultadas y copia defensiva de la respuesta, adaptar la prueba al esquema y contrato actuales, y medir la recarga y la equivalencia antes de adoptarla. Requiere decisión de Hardy; no la implementé.

Verificación dirigida: `python -m pytest -q` con los dos identificadores anteriores dio **2 fallidas** (la aserción «manejando» y `AttributeError` por `_REPORTERIA_CACHE`). `python -m pytest -q tests`, ejecutado fuera del sandbox porque las pruebas de FastAPI se bloqueaban allí, terminó con **538 aprobadas, 2 fallidas y 145 subpruebas aprobadas**. La ejecución literal de `python -m pytest -q` se detuvo en recolección: `app/api/test_openia.py` intenta llamar a OpenAI al importarse y falló por resolución de red (`getaddrinfo failed`); no alcanzó a ejecutar la suite. No modifiqué servicios ni pruebas.

