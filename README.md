## Módulo de Importación de Pagos

El CRM cuenta con un módulo centralizado de importación de pagos para reemplazar el flujo anterior en PHP.  
Este módulo permite cargar archivos de pagos de diferentes carteras, validar su contenido, publicar cortes oficiales y alimentar reportes BI, dashboards y futuras vistas de metas.

### Objetivo del módulo

Centralizar la carga de pagos del negocio mediante un flujo controlado:

1. Carga de archivo.
2. Validación del formato.
3. Normalización en staging.
4. Previsualización de resultados.
5. Confirmación de publicación.
6. Actualización de corte activo.
7. Conservación de auditoría histórica.

El módulo evita duplicidades considerando que varios archivos de pagos vienen acumulados por mes.  
Por ello, cuando se publica una nueva carga del mismo formato, período y cartera, el corte anterior queda reemplazado y solo el último corte queda activo para BI.

---

### Flujo funcional

```text
Archivo de pagos
    ↓
Validación
    ↓
PAGOS_STAGING_NORMALIZADO
    ↓
Confirmación del usuario
    ↓
PAGOS_BI_NORMALIZADO
    ↓
VW_PAGOS_BI_ACTIVO
    ↓
BI / dashboards / vista de metas


Tablas principales
| Tabla / Vista               | Descripción                                                                        |
| --------------------------- | ---------------------------------------------------------------------------------- |
| `PAGOS_IMPORTACION`         | Registra cada archivo importado, su estado, usuario, período, totales y auditoría. |
| `PAGOS_STAGING_NORMALIZADO` | Guarda temporalmente las filas validadas antes de publicarlas.                     |
| `PAGOS_BI_NORMALIZADO`      | Tabla final normalizada que contiene pagos publicados para BI y dashboards.        |
| `VW_PAGOS_BI_ACTIVO`        | Vista oficial que expone solo los registros activos vigentes.                      |
| `VW_PAGOS_RESUMEN_CARTERA`  | Vista resumen por cartera, período y tipo de medición.                             |
| `PAGOS_CONFIG_CARTERA`      | Configuración de formatos, carteras, IDs y tipo de medición.                       |


Estados de importación
| Estado             | Descripción                                            |
| ------------------ | ------------------------------------------------------ |
| `RECIBIDO`         | Archivo recibido, pendiente de procesamiento.          |
| `VALIDADO`         | Archivo validado y cargado en staging.                 |
| `PUBLICADO`        | Archivo confirmado y publicado como corte activo.      |
| `REEMPLAZADO`      | Corte anterior reemplazado por una carga más reciente. |
| `ERROR_VALIDACION` | Archivo con errores de validación.                     |


Regla de cortes activos
formato + codmes + idcartera


Reglas por formato
MiBanco
Formato: MIBANCO
Hoja: DATOS
Filtro: USU_FIN = BIZNESCOB
Fecha de pago: FEC_ULT_PAG
Formato de fecha: yyyymmdd
Monto principal: PAG_REA_SOL
ID cartera operativo: 112
Cartera: MIBANCO
Tipo de medición: RECUPERO
COD_CLI se guarda como cod_cliente.
COD_PRE se guarda como num_operacion.
TIP_CAR se guarda como segmentacion.

Nota:
El módulo no separa MiBanco en 112, 143 y 135 porque dicha clasificación depende de cruces externos no disponibles en este importador.

Interbank
Formato: INTERBANK
Hoja: PAGOS
Filtro: ESTUDIO = BIZNESCOB
Excluir PERIODOCAMPAÑA = 0
Período: PERIODOCAMPAÑA
Fecha de pago: FECHA_AMORT
Monto principal: TOTAL_PAGADOMN
ID cartera: 117
Tipo de medición: RECUPERO
Financiera OH
Formato: FINANCIERA_OH
El archivo puede llegar como .xls, pero internamente comportarse como CSV.
Filtro: GESTOR = BIZNESCOB
Importar solo registros con SUMA_PAGOS_MES > 0
Monto principal: SUMA_PAGOS_MES
Período: FECHA_PROCESO
ID cartera: 132
Tipo de medición: RECUPERO
Compartamos Castigo
Formato: COMPARTAMOS_CASTIGO
Hoja: Caja
Filtro: USUARIO_2 = EXTERNO - BIZNESCOB
Fecha de pago: FECHA_DE_MOVIMIENTO
Monto principal: Monto
Tipo de medición: RECUPERO

Mapeo:

LinNeg	ID cartera	Cartera
IND	124	Compartamos Castigo Individual
GRU	144	Compartamos Castigo Grupal
CCM	144	Compartamos Castigo Grupal

Nota:
En Compartamos Castigo, GRU y CCM se consolidan como Castigo Grupal.

Compartamos Vigente
Formato: COMPARTAMOS_VIGENTE
Hoja: base
Filtro: Usuario_MesAsig = EXTERNO - BIZNESCOB
Período: MesAsig
Monto pago: Recaudo
Capital contenido: Sdo_CON_REC
Tipo producto: TipCartera
Clasificación SBS: Calif_Provisiones
Tipo de medición: CONTENCION


| LinNeg | ID cartera | Cartera                        |
| ------ | ---------: | ------------------------------ |
| `IND`  |        126 | Compartamos Vigente Individual |
| `CCM`  |        128 | Compartamos Vigente CCM        |
| `GRU`  |        133 | Compartamos Vigente Grupal     |


python -m http.server 5500
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload                                                               
