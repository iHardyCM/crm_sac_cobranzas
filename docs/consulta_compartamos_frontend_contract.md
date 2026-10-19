# Contrato Mini CRM de Consulta Compartamos

## Endpoint

- Ruta conservada: `GET /cliente/buscar?valor=...`.
- Servicio de búsqueda: `app/services/cliente_service.py`.
- Normalización CRM: `app/services/cliente_crm_service.py`.
- El backend determina `tipo_resultado` (`CLIENTE` o `GRUPO`). El frontend no infiere el modo.
- Una búsqueda por DNI, código de cliente u operación devuelve la entidad cliente completa. Una búsqueda por `CodigoGrupo` o `CodCreGrupal` devuelve el grupo completo.

## Estructura normalizada

```json
{
  "encontrado": true,
  "tipo_resultado": "CLIENTE | GRUPO",
  "criterio_busqueda": "DNI | CODIGO_CLIENTE | OPERACION | CODIGO_GRUPO | CREDITO_GRUPAL",
  "cliente": {},
  "situacion": {},
  "cobranza": {},
  "campanas": {},
  "contencion": {},
  "gestion": {},
  "pagos_pdp": { "pagos": {}, "pdp": {} },
  "contacto": {},
  "grupo": {},
  "operaciones": [],
  "integrantes": [],
  "cronograma_cuotas": {},
  "informacion_adicional": {},
  "fuentes": {},
  "advertencias": [],
  "total": 0
}
```

Los bloques mantienen `null` o `disponible: false` cuando la fuente no entrega un dato. No se convierte ausencia en cero ni se completa con otra fuente silenciosamente.

## Fuentes y autoridad

### Asignación

`VW_CLIENTE_CRM_SAC` es la fuente autoritativa para identidad, operación, producto, línea, oficina, segmento, condición, calificación, score, mora, cuotas y saldos.

`Calificacion` se expone exactamente como llega de la asignación. No se recalcula, renombra ni reemplaza con datos de SISCOB. Excepción: en la tabla de integrantes de un `GRUPO` la calificación sale de `compartamos_grupal.Cal_PROV` (ver más abajo), por lo que puede diferir de la que muestra la vista individual del cliente.

Los KPIs se consolidan después de deduplicar por `CodOperacion`: cantidad, suma de deuda, capital, capital vencido y desembolso, máxima mora y último pago de asignación.

### SISCOB

- `CLIENTE`, `GESTION`, `INDICADOR` y `USUARIO`: actividad e historial de cobranza. Las consultas se limitan a las carteras Compartamos `124`, `126`, `128`, `133` y `144` para no mezclar gestiones de otras carteras del mismo DNI.
- `COMPROMISO`: PDP, asociada a gestión, cliente y agente.
- SISCOB no sustituye los atributos financieros de la asignación.
- `gestion.carteras_siscob` conserva el diagnóstico de cartera operativa, incluso cuando el cliente no tiene gestiones. Por ejemplo, permite verificar CCM (`128`) sin cambiar `Linea_Negocio`, `Producto`, `Calificacion` u otros valores de asignación.

### Pagos

`PAGOS_BI_NORMALIZADO` aporta último pago real, monto, acumulado mensual y capital contenido únicamente cuando existen filas reales con `tipo_medicion = CONTENCION`.

## Regla de lectura SQL

Todas las lecturas directas a tablas y vistas usadas por este módulo incluyen `WITH(NOLOCK)`:

- `VW_CLIENTE_CRM_SAC WITH(NOLOCK)`
- `SISCOB.DBO.CLIENTE WITH(NOLOCK)`
- `SISCOB.DBO.GESTION WITH(NOLOCK)`
- `SISCOB.DBO.INDICADOR WITH(NOLOCK)`
- `SISCOB.DBO.USUARIO WITH(NOLOCK)`
- `SISCOB.DBO.COMPROMISO WITH(NOLOCK)`
- `dbo.PAGOS_BI_NORMALIZADO WITH(NOLOCK)`

No se modificaron vistas, tablas, procedimientos almacenados ni lógica SQL persistida.

## Cálculos visuales permitidos

- Cuota 1 = `CT1 + CT11 + CT12 + CT13 + CT14 + CT15`.
- Cuota 2 = `CT2 + CT21 + CT22 + CT23 + CT24 + CT25`.
- Cuota 3 = `CT3 + CT31 + CT32 + CT33 + CT34 + CT35`.

Los componentes nulos suman cero solo dentro de estas tres fórmulas solicitadas. Cada resultado informa disponibilidad y cantidad de componentes presentes. No se usa deuda, capital o monto cuota como reemplazo.

## Identificadores numéricos

`VW_CLIENTE_CRM_SAC` entrega `CodigoGrupo` y `CodCreGrupal` como `float`. El servicio representa un código entero sin `.0` (`362951.0` → `362951`) antes de compararlo con el valor buscado y de mostrarlo. Sin esa normalización una búsqueda por código de grupo se clasifica como `CLIENTE`.

## Datos de `compartamos_grupal` en la vista de grupo

Fuente: `Desarrollo.dbo.compartamos_grupal WITH(NOLOCK)`, por `CodigoGrupo`, cruzada por DNI (`NumDocumento`, sin ceros a la izquierda). Se leen con `SELECT *` y las columnas se buscan por nombre normalizado; las que no existan se informan en `advertencias` y el campo queda vacío (no se inventa).

| Campo en integrantes | Columna | Regla |
|---|---|---|
| `rol` | `COMITÉ` | En blanco = "Integrante" |
| `ultimo_pago_asignacion` | `FecUltPago` | Tal cual |
| `calificacion` | `Cal_PROV` | 0 Normal · 1 CPP · 2 Deficiente · 3 Dudoso 1 · 4 Dudoso 2 · 5 Pérdida (se muestra "N-Etiqueta") |

Si el DNI no tiene registro en `compartamos_grupal`, los tres campos quedan vacíos (sin respaldo de otra fuente). Si un DNI trae valores distintos para un campo, no se elige uno y se informa.

Parámetros de campaña (`cronograma_cuotas.parametros`, solo si todo el grupo comparte el mismo valor): `ProductoCamp`, `% Campaña Cliente`, `% Campaña Cliente 100%`, `% Cancelación Cliente`.

## Cronograma de cuotas atrasadas (solo `GRUPO`)

Bloque `cronograma_cuotas`, visible en un modal abierto con el botón "Cronograma de cuotas atrasadas" (pestañas: Cronograma · Cuotas a pagar · Cuadros). El resultado principal de la búsqueda por grupo sigue siendo la vista de grupo.

- Fuente de montos: `Desarrollo.dbo.SAC_CAR_BIZNESCOB WITH(NOLOCK)`, filtrada por `CodigoGrupo`.
- `[CT 1]`, `[CT 2]` y `[CT 3]` son solo cuota capital (`cuotas`, interruptor "Solo capital"). El **total de la cuota** (`cuotas_total`) suma capital + cargos: `CT1+CT11..CT15`, `CT2+CT21..CT25`, `CT3+CT31..CT35`. Componentes NULL no suman; los totales por cuota están en `totales` y `totales_total`.
- Ubicación: `CT 1` va en la cuota `Ult_CuotaAtrasada` (la más antigua pendiente), `CT 2` en la siguiente y `CT 3` en la subsiguiente. Solo se ubican montos mayores a cero; una celda sin monto queda vacía, no en cero.
- Redondeo solo visual y siempre hacia arriba al sol; los totales de pantalla suman lo mostrado. El valor exacto está en el tooltip y en el payload.
- `dias_atraso_inicio` = `compartamos_grupal.DiasAtraso`. `dias_atraso_hoy` = `SAC_CAR_BIZNESCOB.DiasAtraso`. `dias_atraso_proyectado` = `dias_atraso_inicio + 31` (`DIAS_PROYECCION_ATRASO`).
- Solo se muestran integrantes devueltos por la consulta principal del grupo (misma autorización por cartera). Los registros de SAC fuera de ese conjunto se cuentan en `advertencias`.
- Un integrante que no llegó en la carga SAC no aparece en el cronograma.

### Plan de pago (`cronograma_cuotas.plan`)

`ProductoCamp` con "28" → 1 cuota; con "14" → 2 cuotas; siempre las más atrasadas **del grupo**. Si el producto falta, es ambiguo dentro del grupo o no indica 14/28, `plan.disponible = false` con `plan.motivo`.

**Regla por fecha de vencimiento (Hardy, 2026-10-13; misma regla que Biznescob Analytics).** Antes se tomaban los N *números* de cuota más bajos del grupo. Falla cuando los integrantes tienen distinto desembolso: grupo 44011, una integrante debía su N.° 2 y cinco su N.° 3, todas con vencimiento 12/08/2026; por número solo se exigía la N.° 2 (1 de 6) aunque, si las otras cinco no pagan, el grupo sigue en atraso. Ahora:
1. Vencimiento de `CT 1` = `UltFecVen` (AAAAMMDD); `CT 2` = + 1 periodo; `CT 3` = + 2 periodos (14 o 28 días según producto).
2. D1 = vencimiento más antiguo del grupo entre integrantes con `CT 1` > 0.
3. Posición de cada CT = 1 + ROUND((vencimiento − D1) / periodo) (redondeo como SQL Server).
4. Cuotas exigidas = las N posiciones más antiguas con capital.
5. Cada integrante paga sus CT en esas posiciones, aunque su número de cuota sea otro.

La **matriz del cronograma sigue por número de cuota** (decisión de Hardy); solo cambia lo que se paga. Campos:
- `plan.vencimientos[]`: `fecha_vencimiento`, `cuota` (número más frecuente en esa fecha, solo para mostrar), `numeros` (todos los números que vencen ese día), `integrantes`, `capital`, `total`. `plan.cuotas` = los `cuota` de cada vencimiento (compatibilidad). `plan.alineado = false` si en alguna fecha vencen números distintos.
- Por integrante: `a_pagar` / `a_pagar_total` (por número de cuota; marcan la celda "a pagar" en la matriz), `a_pagar_detalle[]` (fecha, número, capital, total) y `fecha_vencimiento_ct1`.
- Pestaña "Por pagar": una columna por vencimiento; bajo cada monto, el número de cuota de ese integrante. Cuadro "Cuota grupo" y "Preparar compromiso grupal": capital por vencimiento y aporte de cada integrante según `a_pagar`.
- Integrante sin `UltFecVen`: no se le asigna cuota y se avisa en `advertencias`; si nadie tiene fecha, `plan.disponible = false`.

### Cuadros (pestaña "Cuadros")

Reproducen los tres cuadros del correo de campaña. Los porcentajes vienen de `compartamos_grupal` como texto (p. ej. `45% Capital`); se toma el primer número.

| Cuadro | Columna de campaña |
|---|---|
| Detalle por cliente | `% Campaña Cliente` (Campaña) y `% Cancelación Cliente` (Campaña cancelación), por integrante |
| Cuota grupo | `% Campaña Cliente 100%` |
| Cancelación grupo | `% Cancelación Cliente` |

Reglas (definidas por negocio, solo capital sin intereses ni cargos):
- **Cuadros sin redondeo (decisión temporal):** se muestran con 2 decimales, sin subir al sol; el cronograma/matriz sigue redondeando hacia arriba.
- **Campaña cuota** (por cada cuota a pagar) = Σ capital exacto de la cuota de todos los integrantes × (100 − % campaña) ÷ 100. Ejemplo: 1273 × 55% = 700.15; 2678 × 55% = 1472.90; total 2173.05 sobre capital 3951.
- **Excepción:** el gestor/supervisor escribe el monto que ofrece el grupo (en memoria; no se guarda). **% propuesta** = monto ÷ capital total × 100 (1800 ÷ 3951 = 45.56%). Monto por cuota = capital de la cuota × % propuesta exacto, de modo que la suma es el monto ofrecido (579.95 + 1220.05 = 1800.00). Subir el % al entero (46%) quedó desactivado por ahora.
- **Cancelación grupo** usa `% Cancelación Cliente` y, **mientras se confirma la base**, se calcula sobre el capital del grupo (suma de capital de integrantes): base = capital × (100 − % cancelación) ÷ 100. Alternativa en evaluación: capital vencido. Excepción igual que en la cuota. El detalle por cliente no tiene propuesta.
- **Rango atraso** sale de `compartamos_grupal.Rang_AtrasoCtaGru` (por integrante en el detalle; en los cuadros de grupo, solo si coincide en todo el grupo).
- Sin porcentaje legible no se calcula (se avisa en el modal). No se bloquea una propuesta menor a la campaña; solo se señala como excepción.
- Rango atraso, Top_NroGru, Prioridad y la propuesta por cliente quedan en "—" hasta definir reglas.

## Campos no conectados

La inspección real de `VW_CLIENTE_CRM_SAC` confirmó que actualmente no entrega:

- `Empresa`, `Tramo` y `UltFecVen`.
- `Direccion_Negocio`, `Direccion_Vivienda`, `Rubro`, `Vivienda`, `Conyuge`, `Avales`, `RCC` y `FechaCarga`.
- Campos de campañas/cancelación como `Camp_1_Cuota`, `Camp_2_Cuota`, `Camp_3_Cuota`, `Cancelacion`, `Porcent_Camp`, `Monto_Pagar`, `Camp_Canc_Integrantes` y `Camp_Canc_Grupo`.
- Una regla identificada para cliente u operación contenedora.
- Monto requerido o capital contenido por PDP.
- Un campo inequívoco de rol por integrante. `CargoComite1`, `CargoComite2` y `CargoComite3` existen, pero no se reinterpretan como rol individual sin una regla confirmada.

Estos campos permanecen ausentes o no disponibles. No se inventan ni se derivan hasta definir y validar su fuente/regla de negocio.

## Presentación

- `CLIENTE`: cabecera individual, KPIs, operaciones compactas, detalle integrado, actividad, pagos/PDP, contacto e información adicional colapsable. No muestra semántica grupal salvo un contexto secundario cuando el cliente pertenece realmente a un grupo.
- `GRUPO`: cabecera, métricas, integrantes, operaciones y actividad con arquitectura específica del grupo.
- La tabla individual mantiene ocho columnas visibles y desplaza los campos restantes al detalle de la operación seleccionada.
- Una sola operación usa la misma arquitectura; no vuelve a tarjetas ni abre un modal.
