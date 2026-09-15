# Contrato frontend de Consulta Compartamos

## Endpoint actual

- Ruta: `GET /cliente/buscar?valor=...`.
- Servicio: `app/services/cliente_service.py`.
- Fuente: `VW_CLIENTE_CRM_SAC` mediante `SELECT *`.
- El endpoint no renombra, agrega ni completa columnas; serializa cada fila de la vista como un objeto.
- No se modifico SQL, la ruta ni la logica de negocio para este rediseño.

## Campos usados directamente

El frontend lee los nombres entregados por la vista. Se conservan los nombres de negocio y, solo para tolerar diferencias de mayusculas o variantes ya usadas en el repositorio, se admiten alias de lectura.

- Identidad: `NomCliente`, `DNI`, `codcliente`, `Edad`, `SexoCliente`, `NomOficina`, `Territorio`, `SEGMENTO`, `Linea_Negocio`, `Calificacion`.
- Operacion: `CodOperacion`, `Producto`, `Condicion`, `Deuda_Total`, `SdoCapital`, `SdoCapitalVencido`, `DiasAtraso`, `NroCuotas_Aprobadas`, `Nro_CuotasAtrasadas`, `Nro_CuotasVencidas`, `ULT_CUOTAATRASADA`, `MTOCUOTA`, `FecDesemb`, `FecUltPago`, `UltFecVen`, `MtoCapDesembolso`.
- Cliente complementario: `Direccion_Principal`, `Distrito_Principal`, `Direccion_Negocio`, `Telef_01` a `Telef_04`, `FecNacimiento`, `ActividadEconomica`.
- Grupo: `CodigoGrupo`, `CodCreGrupal`, `NombreGrupo`.
- Cuotas visuales: `CT1`, `CT11` a `CT15`; `CT2`, `CT21` a `CT25`; `CT3`, `CT31` a `CT35`.

## Disponibilidad no confirmada en vivo

La inspeccion directa del esquema de `VW_CLIENTE_CRM_SAC` no pudo completarse en este entorno por un error local de negociacion SSL del controlador ODBC. Por ello no se afirma que todas las columnas solicitadas existan actualmente en la vista.

Los campos que no estaban consumidos por la version anterior y requieren confirmacion con una respuesta real son principalmente `Territorio`, `Direccion_Negocio`, `ActividadEconomica` y `UltFecVen`. Si cualquiera no llega en el JSON, la interfaz muestra `—`; no inventa valores ni modifica el endpoint.

## Reglas de presentacion

- Con una busqueda activa, el modo grupal solo se habilita si el valor buscado coincide exactamente con un `CodigoGrupo` o `CodCreGrupal` real. Asi, buscar por DNI, codigo de cliente u operacion conserva el contexto individual aunque esa persona pertenezca a un grupo.
- En renderizados sin valor de busqueda, se usa como respaldo la presencia de `CodigoGrupo`, `CodCreGrupal` o `NombreGrupo`. `0`, `00`, valores vacios y nulos nunca activan el modo grupal.
- `Calificacion` se muestra tal como llega; no se recalcula ni se sustituye por un tramo de mora.
- Los KPIs usan las filas recibidas para el cliente: cantidad, sumas, maxima mora y fecha maxima de ultimo pago.
- Cuota 1, 2 y 3 son calculos exclusivamente visuales. Si falta cualquier componente de una formula, el resultado se presenta como `—`.
