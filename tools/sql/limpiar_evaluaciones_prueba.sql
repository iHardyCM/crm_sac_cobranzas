/* ===========================================================================
   Limpieza de evaluaciones de prueba del modulo Feedback_IA
   ---------------------------------------------------------------------------
   POR QUE NO ES UN TRUNCATE
   1. CRM_IA_EVALUACION_CRITERIO esta referenciada por el FK
      FK_CRM_IA_CALIB_EVALUACION desde CRM_IA_CALIBRACION_CRITERIO. SQL Server
      rechaza TRUNCATE sobre una tabla referenciada por un FK aunque la tabla
      que la referencia este vacia (error 4712).
   2. TRUNCATE es todo o nada. Aqui se conservan las evaluaciones hechas con
      la pauta publicada, que son las unicas utiles para calibrar.

   COMO SE USA
   Ejecuta el PASO 1 solo. Revisa los conteos. Si cuadran, ejecuta el PASO 2.
   El PASO 2 esta dentro de una transaccion con ROLLBACK por defecto: hay que
   cambiar la ultima linea a COMMIT a proposito para que escriba.

   ORDEN DE BORRADO
   De hijas a madre, respetando los FK.
   =========================================================================== */

USE CobAuto;
GO

/* ---------------------------------------------------------------------------
   Evaluaciones que SE CONSERVAN.
   Son las evaluadas con la pauta publicada (id_pauta 1 y 2). Ajusta esta lista
   si quieres conservar alguna mas: todo lo que NO este aqui se borra.
   --------------------------------------------------------------------------- */
IF OBJECT_ID('tempdb..#conservar') IS NOT NULL DROP TABLE #conservar;
CREATE TABLE #conservar (id_feedback INT PRIMARY KEY);
INSERT INTO #conservar (id_feedback) VALUES (29),(30),(31),(34),(35),(36),(37);

IF OBJECT_ID('tempdb..#borrar') IS NOT NULL DROP TABLE #borrar;
SELECT F.id_feedback, F.archivo_nombre, F.ruta_archivo, F.estado, F.fecha_creacion
INTO #borrar
FROM CobAuto.dbo.ia_feedback_llamadas AS F
WHERE NOT EXISTS (SELECT 1 FROM #conservar C WHERE C.id_feedback = F.id_feedback);


/* ===========================================================================
   PASO 1 - SOLO LECTURA. Ejecuta esto primero y revisa.
   =========================================================================== */

-- 1.a Que evaluaciones se borrarian
SELECT 'A borrar' AS lista, id_feedback, archivo_nombre, estado, fecha_creacion
FROM #borrar
ORDER BY id_feedback;

-- 1.b Que se conserva
SELECT 'Se conserva' AS lista, F.id_feedback, F.archivo_nombre, F.estado
FROM CobAuto.dbo.ia_feedback_llamadas F
INNER JOIN #conservar C ON C.id_feedback = F.id_feedback
ORDER BY F.id_feedback;

-- 1.c Filas afectadas por tabla
SELECT 'ia_feedback_llamadas'          AS tabla, COUNT(*) AS filas FROM #borrar
UNION ALL SELECT 'ia_feedback_historial',        COUNT(*) FROM CobAuto.dbo.ia_feedback_historial       H INNER JOIN #borrar B ON B.id_feedback = H.id_feedback
UNION ALL SELECT 'ia_feedback_coaching',         COUNT(*) FROM CobAuto.dbo.ia_feedback_coaching        G INNER JOIN #borrar B ON B.id_feedback = G.id_feedback
UNION ALL SELECT 'ia_feedback_recalibraciones',  COUNT(*) FROM CobAuto.dbo.ia_feedback_recalibraciones R INNER JOIN #borrar B ON B.id_feedback = R.id_feedback
UNION ALL SELECT 'CRM_IA_EVALUACION_CRITERIO',   COUNT(*) FROM CobAuto.dbo.CRM_IA_EVALUACION_CRITERIO  E INNER JOIN #borrar B ON B.id_feedback = E.id_feedback
UNION ALL SELECT 'CRM_IA_CALIBRACION_CRITERIO',  COUNT(*) FROM CobAuto.dbo.CRM_IA_CALIBRACION_CRITERIO K INNER JOIN #borrar B ON B.id_feedback = K.id_feedback;

/* 1.d FRENO DE SEGURIDAD
   Si esto devuelve filas, hay trabajo humano -calibraciones- en evaluaciones
   que ibas a borrar. Revisa antes de continuar: eso no se recupera. */
SELECT 'OJO: calibracion humana en una evaluacion marcada para borrar' AS aviso,
       K.id_feedback, K.codigo_criterio, K.accion, K.estado, K.creado_por, K.fecha_creacion
FROM CobAuto.dbo.CRM_IA_CALIBRACION_CRITERIO K
INNER JOIN #borrar B ON B.id_feedback = K.id_feedback;

/* 1.e Archivos de audio que quedarian huerfanos en disco.
   El DELETE no borra archivos: copia esta lista si vas a limpiar la carpeta. */
SELECT 'Audio huerfano' AS nota, id_feedback, ruta_archivo
FROM #borrar
WHERE ruta_archivo IS NOT NULL
ORDER BY id_feedback;


/* ===========================================================================
   PASO 2 - ESCRITURA. Ejecuta esto SOLO si el paso 1 cuadra.
   Termina en ROLLBACK a proposito. Cambia la ultima linea a COMMIT cuando
   hayas visto los conteos del propio bloque y estes conforme.
   =========================================================================== */

BEGIN TRANSACTION;

    DELETE K
    FROM CobAuto.dbo.CRM_IA_CALIBRACION_CRITERIO K
    INNER JOIN #borrar B ON B.id_feedback = K.id_feedback;
    PRINT CONCAT('CRM_IA_CALIBRACION_CRITERIO: ', @@ROWCOUNT);

    DELETE E
    FROM CobAuto.dbo.CRM_IA_EVALUACION_CRITERIO E
    INNER JOIN #borrar B ON B.id_feedback = E.id_feedback;
    PRINT CONCAT('CRM_IA_EVALUACION_CRITERIO: ', @@ROWCOUNT);

    DELETE H
    FROM CobAuto.dbo.ia_feedback_historial H
    INNER JOIN #borrar B ON B.id_feedback = H.id_feedback;
    PRINT CONCAT('ia_feedback_historial: ', @@ROWCOUNT);

    DELETE G
    FROM CobAuto.dbo.ia_feedback_coaching G
    INNER JOIN #borrar B ON B.id_feedback = G.id_feedback;
    PRINT CONCAT('ia_feedback_coaching: ', @@ROWCOUNT);

    DELETE R
    FROM CobAuto.dbo.ia_feedback_recalibraciones R
    INNER JOIN #borrar B ON B.id_feedback = R.id_feedback;
    PRINT CONCAT('ia_feedback_recalibraciones: ', @@ROWCOUNT);

    DELETE F
    FROM CobAuto.dbo.ia_feedback_llamadas F
    INNER JOIN #borrar B ON B.id_feedback = F.id_feedback;
    PRINT CONCAT('ia_feedback_llamadas: ', @@ROWCOUNT);

    -- Verificacion dentro de la misma transaccion, antes de decidir.
    SELECT COUNT(*) AS quedan_llamadas FROM CobAuto.dbo.ia_feedback_llamadas;
    SELECT COUNT(*) AS quedan_criterios FROM CobAuto.dbo.CRM_IA_EVALUACION_CRITERIO;

ROLLBACK TRANSACTION;   -- <<< cambia a COMMIT TRANSACTION para escribir de verdad
GO


/* ===========================================================================
   OPCIONAL - reiniciar el contador de id_feedback
   ---------------------------------------------------------------------------
   Solo tiene sentido si borras TODO, incluidas las 29-37. Si conservas esas,
   NO ejecutes esto: reiniciar el IDENTITY por debajo de un id existente hace
   que el siguiente INSERT choque con la clave primaria.
   =========================================================================== */
-- DBCC CHECKIDENT ('CobAuto.dbo.ia_feedback_llamadas', RESEED, 0);
