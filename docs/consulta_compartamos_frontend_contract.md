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

`Calificacion` se expone exactamente como llega de la asignación. No se recalcula, renombra ni reemplaza con datos de SISCOB.

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
