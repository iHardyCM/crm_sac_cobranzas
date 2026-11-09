# Estado de cuenta individual — Radar Compartamos

**Para:** Codex (construcción) · **Auditoría:** Claude · **Dueño de las reglas:** Hardy Cruz
**Estado:** especificación v1, 09/11/2026. Fase A lista para construir **cuando el paso 0 confirme el cruce de operaciones** (sección 9); la regla de "monto a cobrar" sigue pendiente (D1).
**Propuesta visual aprobada para revisar con la cliente:** `docs/prototipos/estado_cuenta_individual.html` (datos de ejemplo). Codex debe reproducirla con los datos reales.
**Antecedente:** el cronograma de cuotas atrasadas del grupal (`docs/consulta_compartamos_frontend_contract.md`, sección "Cronograma de cuotas atrasadas"). Este módulo replica esa lógica para **una operación individual**, sin tocar lo grupal.

Etiquetas de evidencia usadas abajo:

| Etiqueta | Significado |
|---|---|
| **[CÓDIGO]** | Verificado en el código actual del repositorio |
| **[REGLA]** | Regla ya definida por Hardy y en uso en el grupal |
| **[POR VALIDAR]** | Se confirma con `tools/sql/validar_estado_cuenta_individual.sql` (paso 0) |
| **[PENDIENTE]** | Decisión de negocio abierta (sección 8). Codex no la implementa por su cuenta |

---

## 1. Problema de negocio

Compartamos pidió (correo de supervisión, 31/10/2026) *"una réplica del estado de cuenta similar al de CB, que permita visualizar rápidamente las cuotas del cliente y el número a cobrar"*, porque los agentes **no tienen acceso a WSAC**.

Lo que el agente necesita resolver en la llamada:

1. ¿Qué cuotas debe el cliente, de qué monto y desde cuándo vence cada una?
2. ¿Cuánto se le cobra? (Fase B: depende de una regla que hoy no existe en el CRM)
3. Si paga hasta cierta cuota, ¿con cuántos días de atraso queda? (contención)

**Unidad de análisis:** una operación individual vigente. No el cliente: un cliente puede tener a la vez una operación grupal y una individual o CCM [CÓDIGO: `incorporar_asignacion_grupal`].

---

## 2. Alcance

### Entra (Fase A)
- Operaciones que figuran **por número de operación** en `Desarrollo.dbo.compartamos_individual` (Vigente Individual, cartera 126) o en `Desarrollo.dbo.compartamos_ccm` (CCM, 128) — **CCM confirmado por Hardy, 09/11/2026**.
- Pestaña "Campañas": los montos de campaña de la asignación, mostrados tal cual (sección 3.5).
- Vista `CLIENTE` del Radar (búsqueda por DNI, código de cliente u operación).
- Cuotas atrasadas que trae la carga SAC (`CT 1..3`), con fecha de vencimiento, capital, cargos, total y acumulado.
- Conciliación contra la asignación y simulación de atraso resultante (si el paso 0 la valida).

### No entra
- Operaciones grupales: siguen con el cronograma grupal.
- Castigo individual (124) y castigo grupal (144): no tienen cuotas, tienen saldo; es otro producto.
- Cuotas pagadas y cuotas por vencer (el cronograma completo del préstamo): la carga SAC no las trae. Ver 3.4.
- Una regla de "monto a cobrar" (D1). La pantalla muestra el acumulado por cuota y las campañas de la asignación; no recomienda un monto.
- Generar documentos (acuerdo de cuotas). Se evalúa después.

---

## 3. Fuentes

### 3.1 Qué operación califica
Una operación recibe estado de cuenta **solo si** su número aparece en `compartamos_individual` o `compartamos_ccm` (columna `[Operacion]`, nvarchar). No se decide por el texto de `Producto` ni de `Linea_Negocio`.

**Cruce sin ceros a la izquierda.** La primera corrida del paso 0 (09/11/2026) cruzó `[Operacion]` contra `[Cod Operación]` de SAC y contra `CodOperacion` de la vista **comparando el texto tal cual: 0 de 2000 coincidencias**. El CRM ya compara estas tablas con `clave_documento()` (quita ceros a la izquierda) y el script se corrigió igual. Hasta que la segunda corrida confirme el cruce, ese es el primer bloqueo de la construcción: si tampoco cruza sin ceros, la columna correcta puede ser otra (`codcuenta`, `ctacliente`), y el bloque 1b del script lo muestra.

Hoy `resolver_calificacion` [CÓDIGO] marca la cartera con tres niveles de prioridad; el tercero ("único registro del DNI") **no** cruza por operación. Ese nivel no sirve para decidir el estado de cuenta: Codex debe exponer explícitamente si la coincidencia fue por operación (por ejemplo `cartera_por_operacion: true`) y usar solo ese caso. Si la cartera no se puede determinar, no se muestra el estado de cuenta (cerrado por defecto, igual que la autorización).

### 3.2 Montos y fechas: `Desarrollo.dbo.SAC_CAR_BIZNESCOB`
Misma fuente y mismas columnas que el grupal [CÓDIGO: `consultar_cronograma_grupo`, `construir_cronograma_cuotas`]:

| Columna SAC | Uso |
|---|---|
| `[Cod Operación]` | Cruce con la operación de la vista (normalizar con `identificador()`) |
| `Ult_CuotaAtrasada` | Número de la cuota donde va `CT 1` |
| `CT 1`, `CT 2`, `CT 3` | Capital de las cuotas `Ult`, `Ult+1`, `Ult+2` [REGLA] |
| `CT 11..15`, `CT 21..25`, `CT 31..35` | Otros cargos por atraso de cada cuota [REGLA]. Su significado individual (interés, mora, gastos, seguro) no está documentado: se muestran sumados como "Otros cargos" **[PENDIENTE D7]** |
| `UltFecVen` | Vencimiento de la cuota `CT 1` (llega como float AAAAMMDD; usar `fecha_sac()`) [REGLA del grupal; **POR VALIDAR** en individual] |
| `DiasAtraso` | Atraso del día |
| `FechaCarga` (datetime) | Fecha de corte de la carga. Se valida contra `UltFecVen + DiasAtraso` (bloque 5) |

SAC también trae `Interes_AlDia`, `Interes_Pactado`, `MtoPenalidad_Dia` y `Gasto`, pero **por operación**, no por cuota. No se usan para repartir los cargos entre cuotas.

Los nombres reales traen espacios finales y tildes. Se leen con `indexar_fila` / `valor_columna` [CÓDIGO], nunca con el nombre escrito a mano en Python.

### 3.3 Asignación: `VW_CLIENTE_CRM_SAC` (ya viene en la respuesta)
`NroCuotas_Aprobadas`, `Nro_CuotasVencidas`, `Nro_CuotasAtrasadas`, `SdoCapital`, `SdoCapitalVencido`, `Deuda_Total`, `MtoCuota`, `FecDesemb`, `FecUltPago`, `DiasAtraso`. Se usan para cabecera y conciliación. **La vista no trae `UltFecVen`** [CÓDIGO: contrato actual, "Campos no conectados"].

### 3.4 Lo que no existe en ninguna fuente conectada
- Fecha de vencimiento de `CT 2` y `CT 3`: hay que derivarla con la frecuencia de pago, que no está conectada **[PENDIENTE D2]**.
- Cuotas pagadas con su fecha y monto, cuotas futuras y su desglose: sin fuente. No se rellenan con `MtoCuota` ni se "suponen pagadas" las cuotas menores a `Ult_CuotaAtrasada`.
- Más de 3 cuotas vencidas: SAC solo trae 3. Si `Nro_CuotasVencidas` > cuotas con capital en SAC, el estado de cuenta está **incompleto** y lo dice (ver R6).

### 3.5 Campañas de la asignación (pestaña "Campañas")
Columnas reales (bloque 1 del paso 0), iguales en las dos tablas:

| Concepto | Columna | Tipo |
|---|---|---|
| % campaña k cuotas (k = 1..4) | `[Camp1Cuota%]` … `[Camp4Cuota%]` | texto |
| Monto campaña k cuotas | `[Campaña Final 1 Cuota]` … `[Campaña Final 4 Cuota]` | float |
| % cancelación | `[Cancelación%]` | texto |
| Monto cancelación | `[Cancelacion]` | float |

Se muestran **tal cual llegan**, sin recalcular. Al lado va una referencia calculada: el total mostrado de las primeras k cuotas del estado de cuenta (y la deuda total para la cancelación). La campaña de 4 cuotas no tiene referencia, porque SAC trae como máximo 3. Si el monto de campaña es sobre capital o sobre total, y sus condiciones, está **por confirmar con Compartamos**.

Otras columnas de la asignación útiles para la cabecera: `NROCUOTAS`, `NROCUOTASPAGADAS`, `FECULTPAGO`, `Calif_Provisiones` (individual); en CCM no hay `NROCUOTASPAGADAS`. Si un dato no existe en la tabla de la cartera, la cabecera muestra "—".

---

## 4. Reglas de cálculo (Fase A)

**R1. Ubicación.** `CT k` va en la cuota `Ult_CuotaAtrasada + (k − 1)`. Solo se lista una cuota si su capital `CT k` > 0. Idéntico al grupal [REGLA].

**R2. Cargos sin capital.** En pantalla, los cargos `CT k1..k5` se llaman **"Intereses, moras y gastos"** (Hardy, 09/11: no se sabe qué es cada uno por separado); el desglose CT k1…k5 va en el tooltip. Si `CT k` es 0 o NULL pero sus cargos `CT k1..k5` suman > 0, la fila se muestra con capital vacío y cargos, y se agrega una advertencia. No se descarta en silencio un monto que el cliente debe.

**R3. Total de la cuota.** `total_k = CT k + CT k1 + … + CT k5`; los componentes NULL no suman. Si todos son NULL, `total_k = null` (no 0) [REGLA].

**R4. Acumulado.** `acumulado_k = Σ total` desde la cuota más antigua hasta la k, en orden. Es dato, no recomendación: responde "si paga hasta esta cuota, son S/ X".

**R5. Fecha y días vencidos.**
- `vencimiento_1 = UltFecVen`.
- `vencimiento_2`, `vencimiento_3`: solo si D2 está resuelto; si no, `null` y la columna dice "—". Nunca se suman 30 o 31 días por defecto.
- `fecha_corte` = `FechaCarga` de SAC, si el bloque 5 confirma que `FechaCarga − UltFecVen = DiasAtraso` (con un desfase constante). `dias_vencida_k = fecha_corte − vencimiento_k`. Nunca se usa la fecha del servidor. Si no se confirma, `dias_vencida` solo se informa para la cuota 1 (= `DiasAtraso`).
- Si D2 produce fechas estimadas (frecuencia mensual sin calendario del banco), cada fecha derivada lleva `fecha_estimada: true` y la pantalla lo marca.

**R6. Conciliación (siempre visible, nunca "corrige").**
- `cuotas_en_sac` = cuotas con capital > 0 en SAC.
- `completo = (cuotas_en_sac == Nro_CuotasVencidas)`. Si es `false` o `Nro_CuotasVencidas` es NULL: advertencia "El estado de cuenta muestra N de M cuotas vencidas".
- `diferencia_capital = SdoCapitalVencido − Σ CT capital`. Se muestra si |diferencia| > 0.05. No se reparte ni se ajusta.

**R7. Simulación de atraso** (solo si R5 tiene fechas y `completo = true`).
Para cada cuota k listada: `atraso_si_paga_hasta_k = fecha_corte − vencimiento_(k+1)` si existe una cuota k+1 vencida; si no, 0. Es aritmética sobre fechas, no una regla de contención. Qué umbral de días evita la migración de calificación es de Compartamos y queda en Fase B.

**R8. Duplicados.** Si SAC trae más de una fila para la misma operación con valores distintos, no se elige una: `disponible = false` con motivo. (El grupal hoy toma la primera con `setdefault`; ver hallazgo H1.)

**R9. Redondeo (Hardy, 09/11: también se redondea).** En pantalla, capital y cargos de cada cuota se suben al sol **hacia arriba** por separado, y el total mostrado de la cuota es la suma de esos dos valores; así la fila cuadra a la vista y nunca queda por debajo del exacto. Acumulado y totales suman lo mostrado. El payload lleva los exactos a 2 decimales y la pantalla los muestra en el tooltip. Ejemplo: capital 410.35 → 411; cargos 80.08 → 81; total mostrado 492 (exacto 490.43). Los montos de campaña se suben al sol de la misma forma.

**R10. Ausencia.** Sin fila en SAC → `disponible = false`, motivo "La operación no figura en la carga SAC del día". Nada se completa con la vista ni con otra fuente.

---

## 5. Contrato del payload

Dentro de cada elemento de `operaciones[]` de `GET /cliente/buscar` (sin endpoint nuevo: hereda la autorización por cartera y el `exigir_vista("clientes")` actuales).

```json
"estado_cuenta": {
  "aplica": true,
  "disponible": true,
  "motivo": null,
  "fuente": "SAC_CAR_BIZNESCOB",
  "cartera": "Individual",
  "cuota_mas_atrasada": 4,
  "dias_atraso_hoy": 47,
  "fecha_corte": "2026-11-08",
  "fecha_corte_fuente": "UltFecVen + DiasAtraso | null",
  "periodicidad": {"dias": null, "fuente": null},
  "cuotas": [
    {"numero": 4, "fecha_vencimiento": "2026-09-22", "fecha_estimada": false, "dias_vencida": 47,
     "capital": 312.40, "cargos": 58.11, "total": 370.51, "acumulado": 370.51,
     "componentes_cargos": {"CT 11": 40.10, "CT 12": 18.01, "CT 13": null, "CT 14": null, "CT 15": null}}
  ],
  "totales": {"capital": 0.0, "cargos": 0.0, "total": 0.0},
  "conciliacion": {
    "cuotas_en_sac": 2, "cuotas_vencidas_asignacion": 2, "completo": true,
    "capital_vencido_asignacion": 0.0, "suma_capital_cuotas": 0.0, "diferencia_capital": 0.0
  },
  "simulacion": [{"paga_hasta_cuota": 4, "monto": 370.51, "dias_atraso_resultante": 16}],
  "campanas": {
    "fuente": "compartamos_individual | compartamos_ccm",
    "cuotas": [{"cuotas": 1, "porcentaje": "20%", "monto": 392.34}],
    "cancelacion": {"porcentaje": "45%", "monto": 2189.22}
  },
  "advertencias": []
}
```

Los números del ejemplo son ilustrativos de formato, no datos reales.

- `aplica = false` (operación grupal, castigo, CCM mientras D3 siga abierto, o sin coincidencia por operación en `compartamos_individual`): el resto del bloque no se envía.
- `simulacion = null` cuando R7 no se cumple; la pantalla dice por qué.
- Las advertencias del bloque también se agregan a `advertencias` de la respuesta, como hace el grupal.

---

## 6. Implementación esperada

### Backend (`app/services/cliente_crm_service.py`)
1. **Extraer** de `construir_cronograma_cuotas` la lectura de una fila SAC a una función pura (p. ej. `leer_cuotas_sac(indice) -> {cuota_inicial, capital[3], cargos[3][5], total[3], fecha_ct1, dias_atraso}`) y usarla en el grupal y en el individual. Condición: `tests/test_cronograma_cuotas.py` y `tests/test_grupo_desde_asignacion.py` pasan **sin modificarse**.
2. Nueva consulta `consultar_sac_por_operacion(operaciones)`: `SELECT S.* FROM Desarrollo.DBO.SAC_CAR_BIZNESCOB S WITH(NOLOCK) WHERE S.[Cod Operación] IN (:op_0, …)`, parametrizada, con `engine_siscob` como el grupal. Solo para respuestas `CLIENTE`, en el mismo `ThreadPoolExecutor` y medida con `medir_fuente("estado_cuenta_ms", …)`.
3. Nueva función pura `construir_estado_cuenta(fila_operacion, filas_sac, cartera_por_operacion) -> dict` que aplique R1–R10. Sin acceso a BD dentro: se prueba con diccionarios.
4. El bloque se arma **después** de `aplicar_calificacion`, porque depende de la cartera por operación.
5. Constantes nuevas arriba del archivo con comentario de origen. Nada de números mágicos en las funciones.

### Frontend (`frontend/js/compartamos.js`, `frontend/css/compartamos.css`)
**Referencia visual:** `docs/prototipos/estado_cuenta_individual.html`. Abrirla en el navegador; tiene tres escenarios (completo, CCM con carga incompleta, una cuota). Se reproduce con los componentes y clases del Radar (`crm-modal*`, `crm-chip`, `crm-segmento`, colores `rango-0/1/2`), no copiando el CSS del prototipo.

1. Botón "Estado de cuenta" en la fila de la operación (columna Acción) y en el detalle, solo si `estado_cuenta.aplica`.
2. Modal propio `estadoCuentaModalCRM` reutilizando las clases `crm-modal*`. **No** reutilizar los ids ni el estado global del cronograma grupal (`cronogramaModalCRM`, `window._cronogramaEstado`).
3. Contenido, como en el prototipo:
   - Pestaña **Cuotas vencidas**: chips (producto, cartera, calificación, desembolso, pagadas, fecha de carga) y selector "Total de la cuota / Solo capital"; cuatro cifras (vencido en la carga, días de atraso hoy, cuotas vencidas de aprobadas, "Si paga hasta la N.° X"); aviso si la carga está incompleta; tabla (Cuota, Vence, Días vencida, Capital, Intereses moras y gastos, Total cuota, Acumulado, Si paga hasta aquí → queda con N días); filas faltantes rayadas cuando la carga trae menos cuotas que las vencidas; conciliación con ✓/!; leyenda.
   - Tocar una fila selecciona "pagar hasta esta cuota": se marcan las filas incluidas y la cifra de la derecha muestra el acumulado y los días resultantes. Es estado de pantalla, no se guarda.
   - Pestaña **Campañas** (etiqueta "por validar"): tabla de la sección 3.5.
4. `null` se muestra "—", nunca "S/ 0.00". Fecha estimada con marca visible.
5. Responsive con el patrón `data-label` que ya usan las tablas.
6. Si se cambia un asset, versionar con `tools/version_assets.py` como el resto.

### Documentación
Agregar al contrato `docs/consulta_compartamos_frontend_contract.md` una sección "Estado de cuenta individual" con lo construido.

---

## 7. Pruebas obligatorias (`tests/test_estado_cuenta_individual.py`)

Sin base de datos, con filas armadas como en `test_cronograma_cuotas.py` (nombres reales con espacios y tildes).

| # | Caso | Esperado |
|---|---|---|
| 1 | `Ult=4`, CT1..3 > 0, `UltFecVen` | Cuotas 4, 5, 6; vencimiento de la 4 = `UltFecVen` |
| 2 | Sin periodicidad (D2 abierto) | Vencimientos 5 y 6 = `null`; simulación `null` |
| 3 | CT2 = 0, CT3 > 0 | Se listan 4 y 6; advertencia de hueco |
| 4 | CT1 NULL, CT11 > 0 | Fila 4 con capital `null`, cargos > 0, advertencia (R2) |
| 5 | Todos los cargos NULL | `total = capital`; `cargos = null` |
| 6 | `Nro_CuotasVencidas = 5`, 3 CT | `completo = false`, advertencia, simulación `null` |
| 7 | Σ CT ≠ `SdoCapitalVencido` | `diferencia_capital` informada, montos sin ajustar |
| 8 | Dos filas SAC distintas de la misma operación | `disponible = false` con motivo (R8) |
| 9 | Operación ausente en SAC | `disponible = false`, motivo R10 |
| 10 | Operación grupal, castigo o solo coincidencia por DNI | `aplica = false` |
| 11 | `UltFecVen` NULL | Vencimientos `null`, advertencia, simulación `null` |
| 12 | Acumulado con decimales | Suma exacta a 2 decimales, sin redondeo al sol |
| 13 | Regresión | Pruebas del grupal pasan sin cambios |
| 14 | Redondeo R9 | capital 410.35 y cargos 80.08 → 411 + 81 = 492 mostrado; exacto 490.43 en el payload |
| 15 | Operación en `compartamos_ccm` | `aplica = true`, `cartera = "CCM"`, campañas desde `compartamos_ccm` |
| 16 | Operación con ceros a la izquierda distintos entre asignación y SAC | Cruza igual (`clave_documento`) |
| 17 | Campaña con % pero sin monto, o al revés | Se muestra lo que hay; lo demás "—" |

---

## 8. Decisiones pendientes (Hardy / Compartamos)

| # | Decisión | Por qué importa | Propuesta |
|---|---|---|---|
| D1 | **Qué es "el número a cobrar"** en individual | Es lo que pidió el banco y cambia toda la pantalla | Fase A muestra acumulado y simulación (datos). La regla (cuota más antigua, poner al día, o campaña) se define con Compartamos y entra en Fase B |
| D2 | Fecha de vencimiento de CT 2 y CT 3 | Sin ella no hay días vencidos ni simulación | Usar una columna de frecuencia si el paso 0 la encuentra. Si no hay, mostrar solo la fecha de CT 1. No suponer +30 días |
| D3 | ~~¿Incluye CCM?~~ | — | **Resuelto 09/11:** sí, individual y CCM |
| D4 | ~~Formato de CB/WSAC~~ | — | **Resuelto 09/11:** no hay modelo; se usa la propuesta `docs/prototipos/estado_cuenta_individual.html` y Hardy la afina con la cliente |
| D5 | ~~Redondeo~~ | — | **Resuelto 09/11:** hacia arriba al sol (R9) |
| D6 | Campañas | Las columnas existen (3.5) | Mostrarlas tal cual; falta confirmar con Compartamos sobre qué base se calculan |
| D7 | ~~Significado de CT k1..k5~~ | — | **Resuelto 09/11:** no se conoce por separado; se muestran sumados como "Intereses, moras y gastos" |

---

## 9. Paso 0 — validación de datos antes de construir

Ejecutar `tools/sql/validar_estado_cuenta_individual.sql` (solo lectura) y guardar la salida.

**Corrida 1 (09/11/2026):** columnas encontradas en las tres fuentes; **0 de 2000** operaciones cruzaron con SAC y con la vista. Causa probable: ceros a la izquierda. El script ya se corrigió y se agregó el bloque 1b (diagnóstico del cruce). Falta la corrida 2.

Qué decide cada bloque:

| Bloque | Pregunta | Si sale mal |
|---|---|---|
| 1 | Columnas reales de SAC, `compartamos_individual`, `compartamos_ccm` | **Hecho (corrida 1).** No hay columna de frecuencia de pago: D2 sigue abierto |
| 1b | Qué columna de la asignación cruza con `[Cod Operación]`; si SAC trae operaciones individuales | Si no cruza, la construcción no empieza |
| 2 | Cobertura: % de operaciones individuales con fila SAC, `UltFecVen`, `CT 1` | Si la cobertura es baja, el botón aparecería en pocos casos: revisar antes de construir |
| 3 | ¿CT 1..3 cubre todas las cuotas vencidas? Huecos y cargos sin capital | Dimensiona R2, R6 |
| 4 | Σ CT vs `SdoCapitalVencido` | Si no cuadra en la mayoría, entender por qué antes de mostrar la conciliación |
| 5 | ¿`DiasAtraso` = fecha de corte − `UltFecVen`? | Si no es constante, R5/R7 no aplican |
| 6 | Días promedio por cuota (orientativo) | Informa D2; no es una regla |
| 7 | Muestra de 20 operaciones | Contrastar 5 a mano contra WSAC |

---

## 10. Criterios de auditoría (lo que revisaré en la entrega de Codex)

**Datos y reglas**
- [ ] Ningún monto, fecha o cuota sale de una fuente distinta a las de la sección 3.
- [ ] No hay valores por defecto que oculten ausencia (`or 0`, `?? 0`, 30/31 días, `MtoCuota` como reemplazo).
- [ ] R1–R10 implementadas tal cual; cada desviación, explicada.
- [ ] La cartera se decide por operación, no por DNI ni por texto de producto.
- [ ] Duplicados en SAC no se resuelven eligiendo una fila.

**No romper lo validado**
- [ ] El diff del grupal se limita a la extracción de la función común.
- [ ] `test_cronograma_cuotas.py` y `test_grupo_desde_asignacion.py` sin cambios y en verde.
- [ ] El modal grupal sigue funcionando (ids y estado global separados).

**Seguridad y rendimiento**
- [ ] Sin endpoint nuevo, o si lo hay, con `requiere_clave_definitiva`, `exigir_vista` y el verificador de cartera.
- [ ] SQL parametrizado, `WITH(NOLOCK)`, una sola consulta SAC por búsqueda, en paralelo.
- [ ] Tiempo agregado medido en `tiempos_fuentes`.

**Pantalla**
- [ ] `null` → "—"; fechas estimadas marcadas; advertencias visibles.
- [ ] Totales de la tabla = suma de las filas mostradas.
- [ ] 5 operaciones del bloque 7 coinciden con WSAC cuota por cuota (prueba manual con Hardy).

---

## 11. Hallazgos en el código existente (no bloquean, conviene saberlos)

- **H1.** `construir_cronograma_cuotas` usa `por_operacion.setdefault(key, indice)`: si SAC trae dos filas de la misma operación, toma la primera sin avisar. En el individual se exige R8; en el grupal queda como mejora aparte.
- **H2.** `resolver_calificacion` cae a "único registro del DNI" cuando no cruza por operación. Para la calificación está bien; para decidir qué módulo aplica a una operación, no (ver 3.1).
- **H3.** `normalizar_operacion` ya calcula "Cuotas calculadas" (`CT1+CT11..`) desde la vista sin número de cuota ni fecha. Cuando el estado de cuenta esté disponible, ese bloque del detalle queda redundante; retirarlo es decisión de Hardy, no de Codex.
