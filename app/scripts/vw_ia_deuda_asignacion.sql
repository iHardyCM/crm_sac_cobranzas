/* =====================================================================
   VW_IA_DEUDA_ASIGNACION
   Contrato unico de deuda para la verificacion de Feedback_IA.

   PROPOSITO
   Cada cartera guarda su asignacion con columnas distintas y algunos
   montos se calculan. En lugar de que el modulo conozca la forma de cada
   tabla, todas las carteras se normalizan aqui a un mismo contrato de
   columnas. Agregar una cartera es agregar un bloque al UNION ALL; el
   codigo Python no cambia.

   GRANULARIDAD: una fila por OPERACION.
   El agente comunica el monto de una operacion concreta ("la operacion
   12312312 tiene una campania de 500"), de modo que la verificacion se
   hace contra operaciones, no contra un agregado del cliente.

   CONTRATO DE COLUMNAS
     idcartera          INT        cartera operativa
     periodo            INT        YYYYMM del mes de asignacion
     documento          VARCHAR    documento de identidad del cliente
     operacion          VARCHAR    codigo de la operacion
     nombre_cliente     NVARCHAR
     monto_capital      DECIMAL    saldo capital
     monto_deuda_total  DECIMAL    deuda total; NULL si la cartera no la expone
     monto_campania     DECIMAL    monto de la campania vigente
     monto_cuota        DECIMAL    cuota pendiente; NULL si no aplica
     dias_atraso        INT

   Un monto en NULL significa "esta cartera no maneja ese concepto".
   La verificacion solo contrasta contra los montos NO nulos: nunca marca
   un incumplimiento por un concepto que la cartera no tiene.
   ===================================================================== */

CREATE OR ALTER VIEW dbo.VW_IA_DEUDA_ASIGNACION
AS

/* ---------------------------------------------------------------------
   COMPARTAMOS CASTIGO  (Desarrollo.DBO.compartamos_castigo)

   Reglas confirmadas con negocio:
   - Porcent_Camp es el PORCENTAJE DE DESCUENTO, no lo que paga el cliente.
     El monto de campania es (1 - Porcent_Camp) * SdoCap.
     Ejemplo: SdoCap 2282.92 con Porcent_Camp 0.70 -> campania 684.88.
   - No se filtra por usuario de asignacion: toda la tabla corresponde a
     la cartera gestionada.
   - META es la meta de cobro por cliente, no un monto que el agente
     comunique al cliente. Queda fuera del contrato a proposito.
   - Esta cartera no expone deuda total ni cuota pendiente: van en NULL.
   --------------------------------------------------------------------- */
SELECT
    idcartera = CASE UPPER(LTRIM(RTRIM(A.LinNeg)))
                    WHEN 'IND' THEN 124   -- Compartamos Castigo Individual
                    WHEN 'GRU' THEN 144   -- Compartamos Castigo Grupal
                    WHEN 'CCM' THEN 144   -- CCM se consolida como Castigo Grupal
                END,
    periodo = YEAR(TRY_CONVERT(DATE, A.MesAsig, 103)) * 100
            + MONTH(TRY_CONVERT(DATE, A.MesAsig, 103)),
    documento = LTRIM(RTRIM(CONVERT(VARCHAR(20), A.NumDoc))),
    operacion = LTRIM(RTRIM(CONVERT(VARCHAR(40), A.Operacion))),
    nombre_cliente = CONVERT(NVARCHAR(200), A.NomCliente),

    monto_capital = CONVERT(DECIMAL(18, 2), A.SdoCapSoles),
    monto_deuda_total = CONVERT(DECIMAL(18, 2), NULL),
    monto_campania = CONVERT(DECIMAL(18, 2),
                             ROUND((1 - A.Porcent_Camp) * A.SdoCap, 2)),
    monto_cuota = CONVERT(DECIMAL(18, 2), NULL),

    dias_atraso = CONVERT(INT, A.DiasAtraso)
FROM Desarrollo.DBO.compartamos_castigo AS A WITH (NOLOCK)
WHERE A.NumDoc IS NOT NULL
  AND A.Operacion IS NOT NULL
  AND UPPER(LTRIM(RTRIM(A.LinNeg))) IN ('IND', 'GRU', 'CCM')

/* ---------------------------------------------------------------------
   SIGUIENTES CARTERAS

   Agregar un bloque por cartera respetando el mismo orden y tipo de
   columnas. Los conceptos que la cartera no maneje van como
   CONVERT(DECIMAL(18,2), NULL).

UNION ALL
SELECT
    idcartera         = <id>,
    periodo           = <YYYYMM>,
    documento         = <documento>,
    operacion         = <operacion>,
    nombre_cliente    = <nombre>,
    monto_capital     = <capital>,
    monto_deuda_total = <deuda total o NULL>,
    monto_campania    = <campania o NULL>,
    monto_cuota       = <cuota pendiente o NULL>,
    dias_atraso       = <dias>
FROM <tabla de la cartera> WITH (NOLOCK)

   PENDIENTE: la tabla historica. Cuando cambia el periodo, la asignacion
   vigente se reemplaza y la anterior pasa a una tabla historica. Falta
   agregar ese bloque para poder verificar llamadas de meses anteriores.
   Sin el, una llamada de un periodo cerrado no cruza y su criterio queda
   NO_EVALUABLE, que es el comportamiento correcto mientras tanto.
   --------------------------------------------------------------------- */
GO


/* =====================================================================
   VERIFICACION
   ===================================================================== */

-- 1. Debe devolver filas con periodo 202609 y campania calculada
SELECT TOP 20 idcartera, periodo, documento, operacion, nombre_cliente,
       monto_capital, monto_campania, dias_atraso
FROM dbo.VW_IA_DEUDA_ASIGNACION
ORDER BY documento;

-- 2. Control de la formula sobre el ejemplo conocido:
--    SdoCap 2282.92 con Porcent_Camp 0.70 debe dar campania 684.88
SELECT documento, operacion, monto_capital, monto_campania
FROM dbo.VW_IA_DEUDA_ASIGNACION
WHERE documento = '60564812';

-- 3. Clientes con mas de una operacion en la misma cartera y periodo.
--    Es el caso que obliga a verificar por operacion y no por cliente.
SELECT documento, idcartera, periodo, COUNT(*) AS operaciones
FROM dbo.VW_IA_DEUDA_ASIGNACION
GROUP BY documento, idcartera, periodo
HAVING COUNT(*) > 1
ORDER BY operaciones DESC;

-- 4. Filas que quedarian fuera por no resolver idcartera o periodo
SELECT COUNT(*) AS filas_sin_cartera
FROM dbo.VW_IA_DEUDA_ASIGNACION WHERE idcartera IS NULL;

SELECT COUNT(*) AS filas_sin_periodo
FROM dbo.VW_IA_DEUDA_ASIGNACION WHERE periodo IS NULL;
GO
