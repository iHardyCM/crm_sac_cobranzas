/* =====================================================================================
   SCORE TELEFÓNICO · DIAGNÓSTICO 9 — VALIDAR EL CAMBIO DE "EQUIVOCADOS" EN CARACTERÍSTICAS
   Fecha: 14/11/2026

   Antes: score_telefonico_fase3.sql (bloque 2) reinstalado con el cálculo en bloque.
   Qué hace:
     1. Copia las características de hoy de 112 y 117 (calculadas con la versión anterior por el job de las 20:23).
     2. Actualiza 112 y 117 con el botón (sp_ActualizarCartera, modo real): escribe universo, características y
        score de esas dos carteras, igual que si un supervisor pulsara "Actualizar".
     3. Compara: la marca F_EQUIVOCADO_DNI debe salir igual teléfono por teléfono.
        Las demás columnas también se comparan; alguna diferencia puede venir de cambios del día en SISCOB
        (atributos), no del cambio de cálculo.
   Ejecutar TODO en la misma ventana (las tablas temporales viven en la sesión).
   Guardar la salida en tools/salidas/resultados_diagnostico_score_9.txt
   ===================================================================================== */

USE CobAuto;
SET NOCOUNT ON;

DECLARE @Hoy DATE = CAST(GETDATE() AS DATE);

IF OBJECT_ID('tempdb..#antes') IS NOT NULL DROP TABLE #antes;
SELECT * INTO #antes
FROM score.Caracteristicas
WHERE FechaCorte = @Hoy AND Poblacion = 'UNIVERSO' AND IdCartera IN (112, 117);

SELECT 'ANTES' AS momento, IdCartera, COUNT(*) AS telefonos,
       SUM(CASE WHEN F_EQUIVOCADO_DNI = 'SI' THEN 1 ELSE 0 END) AS equivocado_dni_si
FROM #antes GROUP BY IdCartera ORDER BY IdCartera;
GO

EXEC CobAuto.score.sp_ActualizarCartera @IdCartera = 112, @Usuario = N'validacion_diag9', @Origen = 'MANUAL', @Alinear = 1, @Simular = 0;
EXEC CobAuto.score.sp_ActualizarCartera @IdCartera = 117, @Usuario = N'validacion_diag9', @Origen = 'MANUAL', @Alinear = 1, @Simular = 0;
GO

DECLARE @Hoy DATE = CAST(GETDATE() AS DATE);

IF OBJECT_ID('tempdb..#despues') IS NOT NULL DROP TABLE #despues;
SELECT * INTO #despues
FROM score.Caracteristicas
WHERE FechaCorte = @Hoy AND Poblacion = 'UNIVERSO' AND IdCartera IN (112, 117);

SELECT 'DESPUES' AS momento, IdCartera, COUNT(*) AS telefonos,
       SUM(CASE WHEN F_EQUIVOCADO_DNI = 'SI' THEN 1 ELSE 0 END) AS equivocado_dni_si
FROM #despues GROUP BY IdCartera ORDER BY IdCartera;

-- 1. La comparación que importa: misma marca de equivocado en los teléfonos de ambas corridas
SELECT a.IdCartera,
       COUNT(*) AS telefonos_en_ambas,
       SUM(CASE WHEN a.F_EQUIVOCADO_DNI <> d.F_EQUIVOCADO_DNI THEN 1 ELSE 0 END) AS difiere_equivocado,   -- debe ser 0
       SUM(CASE WHEN a.T_ULT_CEF <> d.T_ULT_CEF OR a.T_TASA_CEF_90 <> d.T_TASA_CEF_90
                  OR a.T_INTENTOS_30 <> d.T_INTENTOS_30 OR a.T_ULT_INTENTO <> d.T_ULT_INTENTO
                  OR a.T_MAQUINA_90 <> d.T_MAQUINA_90 OR a.T_ULT_TERCERO <> d.T_ULT_TERCERO
                  OR a.F_NO_EXISTE <> d.F_NO_EXISTE THEN 1 ELSE 0 END) AS difiere_historial,       -- debe ser 0
       SUM(CASE WHEN a.S_ORIGEN <> d.S_ORIGEN OR a.S_OSIPTEL <> d.S_OSIPTEL OR a.S_WHATSAPP <> d.S_WHATSAPP
                  OR a.S_TIMBRA <> d.S_TIMBRA OR a.S_COMPARTIDO <> d.S_COMPARTIDO OR a.S_COLOR <> d.S_COLOR
                  THEN 1 ELSE 0 END) AS difiere_atributos   -- puede no ser 0 si SISCOB cambió en el día
FROM #antes AS a
INNER JOIN #despues AS d ON d.IdCartera = a.IdCartera AND d.DNI = a.DNI AND d.Telefono = a.Telefono
GROUP BY a.IdCartera
ORDER BY a.IdCartera;

-- 2. Teléfonos que entraron o salieron del universo entre las dos corridas
SELECT IdCartera, SUM(CASE WHEN lado = 'SOLO_ANTES' THEN 1 ELSE 0 END) AS solo_antes,
       SUM(CASE WHEN lado = 'SOLO_DESPUES' THEN 1 ELSE 0 END) AS solo_despues
FROM (SELECT a.IdCartera, 'SOLO_ANTES' AS lado FROM #antes AS a
      WHERE NOT EXISTS (SELECT 1 FROM #despues AS d WHERE d.IdCartera = a.IdCartera AND d.DNI = a.DNI AND d.Telefono = a.Telefono)
      UNION ALL
      SELECT d.IdCartera, 'SOLO_DESPUES' FROM #despues AS d
      WHERE NOT EXISTS (SELECT 1 FROM #antes AS a WHERE a.IdCartera = d.IdCartera AND a.DNI = d.DNI AND a.Telefono = d.Telefono)) AS x
GROUP BY IdCartera;

-- 3. Tiempos de las dos actualizaciones
SELECT TOP 2 IdActualizacion, IdCartera, Estado, DATEDIFF(SECOND, Inicio, Fin) AS segundos_total,
       SegAlineacion, SegUniverso, SegCaracteristicas, SegScore, Mensaje
FROM score.ActualizacionCartera
WHERE Usuario = N'validacion_diag9'
ORDER BY IdActualizacion DESC;
GO
