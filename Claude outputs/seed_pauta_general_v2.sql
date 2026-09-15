/* =====================================================================
   PAUTA GENERAL DE EVALUACION - VERSION 2
   Cambio de regla de negocio del 16/09/2026

   QUE CAMBIA Y POR QUE
   Se decidio NO usar una base de deudas, capitales y campanias. La
   verificacion de que el monto sea correcto deja de ser posible y, en su
   lugar, se mide el FRASEO: que el asesor declare los montos en la llamada.

   1. PECUF.3 deja de llamarse "Precision de la informacion de la deuda" y
      pasa a ser "Declaracion escalonada de montos". Su fuente cambia de
      MULTIFUENTE a TRANSCRIPCION, porque ahora si es observable: lo que se
      comprueba es que lo haya dicho, no que la cifra cuadre.

      La escalera, en orden estricto:
          deuda total --rechazo--> capital --rechazo--> campania
      Declarar la deuda total es obligatorio y no depende del cliente. Solo
      se baja de nivel ante un rechazo o imposibilidad EXPLICITA del cliente;
      si acepta, o si evade sin negarse, la escalera se detiene ahi.

   2. PECN.2 "Negociacion escalonada" se acota para que no mida lo mismo.
      Desde v2, PECN.2 evalua la FORMA de pago (cuotas, fechas, canal,
      viabilidad segun lo que el cliente expuso) y PECUF.3 evalua los MONTOS.
      Sin esta separacion, una misma conducta descontaria dos veces.

   LO QUE NO CAMBIA
   Pesos, bloques, criticidades y el resto de criterios quedan identicos a
   la v1. Los pesos siguen sumando 100.

   COMO SE EJECUTA
   El script CLONA la pauta 1 en una version 2 en estado BORRADOR y aplica
   los dos cambios sobre la copia. La pauta vigente no se modifica: si algo
   sale mal, no hay nada que revertir. La v2 se revisa en la pantalla de
   Pautas de evaluacion y se publica desde ahi.

   IMPORTANTE: mientras la v1 siga publicada, PECUF.3 se seguira evaluando
   como NO_EVALUABLE. El codigo respeta la fuente declarada por la pauta, de
   modo que la escalera recien empieza a medir cuando se publique la v2.
   ===================================================================== */

SET NOCOUNT ON;
SET XACT_ABORT ON;

DECLARE @id_pauta_origen INT;
DECLARE @id_pauta_nueva  INT;
DECLARE @version_nueva   INT;
DECLARE @usuario         NVARCHAR(100) = N'hcruz';

/* ---------- 1. Ubicar la pauta de origen ---------- */
SELECT TOP 1 @id_pauta_origen = id_pauta
FROM CobAuto.dbo.CRM_IA_PAUTA
WHERE estado = 'PUBLICADA'
ORDER BY version DESC, id_pauta DESC;

IF @id_pauta_origen IS NULL
BEGIN
    RAISERROR('No hay una pauta PUBLICADA para clonar.', 16, 1);
    RETURN;
END

SELECT @version_nueva = ISNULL(MAX(version), 0) + 1
FROM CobAuto.dbo.CRM_IA_PAUTA;

PRINT CONCAT('Clonando pauta ', @id_pauta_origen, ' como version ', @version_nueva);

BEGIN TRANSACTION;

/* ---------- 2. Cabecera ---------- */
INSERT INTO CobAuto.dbo.CRM_IA_PAUTA
    (nombre, version, descripcion, estado, aplica_todas,
     vigencia_desde, vigencia_hasta, creado_por, actualizado_por)
SELECT
    nombre,
    @version_nueva,
    N'Pauta general de evaluacion. v2: PECUF.3 mide la declaracion escalonada de montos (deuda total, capital, campania) en lugar de contrastar contra una base de deudas.',
    'BORRADOR',
    aplica_todas,
    vigencia_desde,
    vigencia_hasta,
    @usuario,
    @usuario
FROM CobAuto.dbo.CRM_IA_PAUTA
WHERE id_pauta = @id_pauta_origen;

SET @id_pauta_nueva = SCOPE_IDENTITY();

/* ---------- 3. Bloques ---------- */
DECLARE @mapa_bloques TABLE (id_bloque_origen INT, id_bloque_nuevo INT, codigo NVARCHAR(50));

MERGE CobAuto.dbo.CRM_IA_PAUTA_BLOQUE AS destino
USING (
    SELECT id_bloque, codigo, nombre, categoria, descripcion, orden, activo
    FROM CobAuto.dbo.CRM_IA_PAUTA_BLOQUE
    WHERE id_pauta = @id_pauta_origen
) AS origen
ON 1 = 0
WHEN NOT MATCHED THEN
    INSERT (id_pauta, codigo, nombre, categoria, descripcion, orden, activo)
    VALUES (@id_pauta_nueva, origen.codigo, origen.nombre, origen.categoria,
            origen.descripcion, origen.orden, origen.activo)
OUTPUT origen.id_bloque, inserted.id_bloque, inserted.codigo
INTO @mapa_bloques (id_bloque_origen, id_bloque_nuevo, codigo);

/* ---------- 4. Criterios ---------- */
INSERT INTO CobAuto.dbo.CRM_IA_PAUTA_CRITERIO
    (id_pauta, id_bloque, codigo_criterio, nombre, tipo_criterio, peso, detalle,
     regla_evaluacion, regla_cumple, regla_no_cumple, regla_aplicabilidad,
     criticidad, fuente_evidencia, requiere_evidencia, puede_descalificar,
     recomendacion, orden, activo)
SELECT
    @id_pauta_nueva, M.id_bloque_nuevo, C.codigo_criterio, C.nombre, C.tipo_criterio,
    C.peso, C.detalle, C.regla_evaluacion, C.regla_cumple, C.regla_no_cumple,
    C.regla_aplicabilidad, C.criticidad, C.fuente_evidencia, C.requiere_evidencia,
    C.puede_descalificar, C.recomendacion, C.orden, C.activo
FROM CobAuto.dbo.CRM_IA_PAUTA_CRITERIO AS C
JOIN @mapa_bloques AS M ON M.id_bloque_origen = C.id_bloque
WHERE C.id_pauta = @id_pauta_origen;

/* ---------- 5. Carteras de alcance (si la pauta no aplica a todas) ---------- */
IF OBJECT_ID('CobAuto.dbo.CRM_IA_PAUTA_CARTERA', 'U') IS NOT NULL
BEGIN
    INSERT INTO CobAuto.dbo.CRM_IA_PAUTA_CARTERA (id_pauta, idcartera)
    SELECT @id_pauta_nueva, idcartera
    FROM CobAuto.dbo.CRM_IA_PAUTA_CARTERA
    WHERE id_pauta = @id_pauta_origen;
END

/* =====================================================================
   6. CAMBIO 1 - PECUF.3: declaracion escalonada de montos
   ===================================================================== */
UPDATE CobAuto.dbo.CRM_IA_PAUTA_CRITERIO
SET nombre = N'Declaración escalonada de montos',
    detalle = N'Declara los montos de la deuda y escala solo ante rechazo',
    regla_evaluacion = N'El asesor debe declarar el monto de la deuda total. Si el cliente rechaza de forma explícita, debe ofrecer el capital con su monto y, ante un nuevo rechazo, el monto de campaña. El orden es estricto. No se verifica que la cifra sea correcta: se evalúa que el monto haya sido comunicado.',
    regla_cumple = N'Cumple cuando declara la deuda total con su importe y el cliente no la rechaza; o cuando, ante rechazo explícito, ofrece el capital con su importe; o cuando, ante un segundo rechazo, ofrece el monto de campaña.',
    regla_no_cumple = N'No cumple cuando omite declarar la deuda total, cuando ante un rechazo explícito no ofrece el siguiente nivel, o cuando salta un nivel de la escalera (por ejemplo, pasa de la deuda total a la campaña sin ofrecer el capital).',
    regla_aplicabilidad = N'Aplica en toda conversación con el titular. Solo es NO_APLICA ante tercero confirmado o corte que impida negociar. Evadir o cambiar de tema no equivale a rechazo: sin negativa o imposibilidad explícita del cliente, no se exige bajar de nivel.',
    fuente_evidencia = N'TRANSCRIPCION',
    recomendacion = N'Decir el importe de la deuda total apenas se valida al titular y bajar de nivel solo cuando el cliente se niega o declara no poder.'
WHERE id_pauta = @id_pauta_nueva
  AND codigo_criterio = N'PECUF.3';

/* =====================================================================
   7. CAMBIO 2 - PECN.2: se acota a la FORMA de pago, no a los montos
   ===================================================================== */
UPDATE CobAuto.dbo.CRM_IA_PAUTA_CRITERIO
SET regla_evaluacion = N'Construye una propuesta de pago acorde con lo que el cliente expuso: forma de pago, fraccionamiento, fechas, canal y viabilidad. La escalera de montos (deuda total, capital, campaña) NO se evalúa aquí: corresponde a PECUF.3.',
    regla_cumple = N'Cumple cuando propone o ajusta la forma de pago según el diagnóstico -cuotas, plazos, fechas o canal- buscando una opción concreta y viable.',
    regla_no_cumple = N'No cumple cuando existe oportunidad de negociar y el agente no desarrolla ninguna alternativa de forma de pago, o la propuesta ignora la situación que el cliente planteó.',
    regla_aplicabilidad = N'Aplica en toda conversación con el titular. Solo puede ser NO_APLICA ante tercero confirmado o corte abrupto que impida responder; una propuesta sola no equivale a compromiso. No se evalúa aquí la declaración de montos.'
WHERE id_pauta = @id_pauta_nueva
  AND codigo_criterio = N'PECN.2';

COMMIT TRANSACTION;

PRINT CONCAT('Pauta v', @version_nueva, ' creada en BORRADOR con id_pauta = ', @id_pauta_nueva);
GO


/* =====================================================================
   VERIFICACION - ejecutar despues del script
   ===================================================================== */

-- 1. La v2 existe en BORRADOR y la v1 sigue PUBLICADA e intacta
SELECT id_pauta, nombre, version, estado, aplica_todas
FROM CobAuto.dbo.CRM_IA_PAUTA
ORDER BY version;

-- 2. Los pesos de la v2 deben sumar exactamente 100
SELECT P.version,
       total_criterios = COUNT(*),
       suma_pesos = SUM(C.peso)
FROM CobAuto.dbo.CRM_IA_PAUTA_CRITERIO AS C
JOIN CobAuto.dbo.CRM_IA_PAUTA AS P ON P.id_pauta = C.id_pauta
GROUP BY P.version
ORDER BY P.version;

-- 3. Los dos criterios modificados, v1 contra v2
SELECT P.version, C.codigo_criterio, C.nombre, C.peso, C.fuente_evidencia
FROM CobAuto.dbo.CRM_IA_PAUTA_CRITERIO AS C
JOIN CobAuto.dbo.CRM_IA_PAUTA AS P ON P.id_pauta = C.id_pauta
WHERE C.codigo_criterio IN (N'PECUF.3', N'PECN.2')
ORDER BY C.codigo_criterio, P.version;

-- 4. Ningun criterio debe haberse perdido en la clonacion
SELECT P.version, B.codigo AS bloque, COUNT(C.id_criterio) AS criterios
FROM CobAuto.dbo.CRM_IA_PAUTA AS P
JOIN CobAuto.dbo.CRM_IA_PAUTA_BLOQUE AS B ON B.id_pauta = P.id_pauta
LEFT JOIN CobAuto.dbo.CRM_IA_PAUTA_CRITERIO AS C ON C.id_bloque = B.id_bloque
GROUP BY P.version, B.codigo
ORDER BY P.version, B.codigo;
GO
