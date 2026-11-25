/* =====================================================================================
   SCORE TELEFÓNICO · DIAGNÓSTICO 5 — revisión de la calibración v1 (solo lectura)
   Fecha: 14/11/2026

   Revisa dos señales raras del informe score_calibracion_20261114_1553.md:
     A. Unos ~230 teléfonos de entrenamiento sin validar (OSIPTEL "SV", WhatsApp "SV", timbrado sin dato)
        tienen 50 % de CEF contra 4,7 % del total. Sospecha: son números que se registraron DURANTE o
        DESPUÉS del corte (por ejemplo, el cliente dio un número nuevo en la llamada). Si es así, el modelo
        está aprendiendo algo que ocurre después del corte, y premiaría a todo teléfono nuevo sin validar.
     B. Los teléfonos marcados como equivocado para el DNI (360) o "no existe" (647) tienen más CEF
        (7,2 % y 9,0 %) que el promedio. Sospecha: una sola marca no es confiable.

   No modifica nada. Guardar el resultado en tools\salidas\resultados_diagnostico_score_5.txt
   ===================================================================================== */
USE CobAuto;
SET NOCOUNT ON;

/* ---------- A.1 Entrenamiento: fecha de alta y de actualización del teléfono contra el corte ---------- */
SELECT
    CASE WHEN a.FechaAltaSiscob IS NULL THEN '3 SIN_FECHA_ALTA'
         WHEN CAST(a.FechaAltaSiscob AS DATE) >= c.FechaCorte THEN '2 ALTA_EN_O_DESPUES_DEL_CORTE'
         ELSE '1 ALTA_ANTES_DEL_CORTE' END AS alta,
    CASE WHEN a.FechaActSiscob IS NULL THEN '3 SIN_FECHA_ACT'
         WHEN CAST(a.FechaActSiscob AS DATE) >= c.FechaCorte THEN '2 ACT_EN_O_DESPUES_DEL_CORTE'
         ELSE '1 ACT_ANTES_DEL_CORTE' END AS actualizacion,
    CASE WHEN c.S_OSIPTEL = 'SV' OR c.S_WHATSAPP = 'SV' OR c.S_TIMBRA = 'SIN_DATO' THEN 'SIN_VALIDAR'
         ELSE 'VALIDADO' END AS validacion,
    COUNT(*) AS telefonos,
    SUM(CAST(c.EXITO AS INT)) AS exitos,
    CAST(100.0 * AVG(CAST(c.EXITO AS FLOAT)) AS DECIMAL(6, 2)) AS tasa_cef_pct
FROM score.Caracteristicas AS c WITH (NOLOCK)
OUTER APPLY (
    SELECT TOP 1 u.FechaAltaSiscob, u.FechaActSiscob
    FROM score.TelefonoUniverso AS u WITH (NOLOCK)
    WHERE u.Telefono = c.Telefono AND u.DNI = c.DNI
    ORDER BY CASE WHEN u.IdCartera = c.IdCartera THEN 0 ELSE 1 END
) AS a
WHERE c.Poblacion = 'MARCADOS'
GROUP BY
    CASE WHEN a.FechaAltaSiscob IS NULL THEN '3 SIN_FECHA_ALTA'
         WHEN CAST(a.FechaAltaSiscob AS DATE) >= c.FechaCorte THEN '2 ALTA_EN_O_DESPUES_DEL_CORTE'
         ELSE '1 ALTA_ANTES_DEL_CORTE' END,
    CASE WHEN a.FechaActSiscob IS NULL THEN '3 SIN_FECHA_ACT'
         WHEN CAST(a.FechaActSiscob AS DATE) >= c.FechaCorte THEN '2 ACT_EN_O_DESPUES_DEL_CORTE'
         ELSE '1 ACT_ANTES_DEL_CORTE' END,
    CASE WHEN c.S_OSIPTEL = 'SV' OR c.S_WHATSAPP = 'SV' OR c.S_TIMBRA = 'SIN_DATO' THEN 'SIN_VALIDAR'
         ELSE 'VALIDADO' END
ORDER BY alta, actualizacion, validacion;

/* ---------- A.2 Universo de hoy: cuántos teléfonos marcables están sin validar (impacto en producción) ---------- */
SELECT
    CASE WHEN u.Osiptel = 'SV' OR u.Whatsapp = 'SV' OR u.Timbra IS NULL THEN 'SIN_VALIDAR' ELSE 'VALIDADO' END AS validacion,
    CASE WHEN u.FechaAltaSiscob IS NULL THEN 'SIN_FECHA'
         WHEN u.FechaAltaSiscob >= DATEADD(DAY, -30, CAST(GETDATE() AS DATE)) THEN 'ALTA_ULTIMOS_30_DIAS'
         ELSE 'ALTA_ANTERIOR' END AS alta,
    COUNT(*) AS filas,
    SUM(CASE WHEN u.Osiptel = 'SV' THEN 1 ELSE 0 END) AS osiptel_sv,
    SUM(CASE WHEN u.Whatsapp = 'SV' THEN 1 ELSE 0 END) AS whatsapp_sv,
    SUM(CASE WHEN u.Timbra IS NULL THEN 1 ELSE 0 END) AS timbra_sin_dato
FROM score.TelefonoUniverso AS u WITH (NOLOCK)
WHERE u.ExcluidoListaNegra = 0
GROUP BY
    CASE WHEN u.Osiptel = 'SV' OR u.Whatsapp = 'SV' OR u.Timbra IS NULL THEN 'SIN_VALIDAR' ELSE 'VALIDADO' END,
    CASE WHEN u.FechaAltaSiscob IS NULL THEN 'SIN_FECHA'
         WHEN u.FechaAltaSiscob >= DATEADD(DAY, -30, CAST(GETDATE() AS DATE)) THEN 'ALTA_ULTIMOS_30_DIAS'
         ELSE 'ALTA_ANTERIOR' END
ORDER BY validacion, alta;

/* ---------- B. Equivocado / no existe: cuántas marcas tenían y qué pasó la semana siguiente ---------- */
SELECT
    m.Marca,
    CASE WHEN m.Eventos90 = 1 THEN '1 evento' WHEN m.Eventos90 = 2 THEN '2 eventos' ELSE '3+ eventos' END AS eventos_en_90_dias,
    COUNT(*) AS telefonos,
    SUM(CAST(c.EXITO AS INT)) AS con_cef_semana_siguiente,
    CAST(100.0 * AVG(CAST(c.EXITO AS FLOAT)) AS DECIMAL(6, 2)) AS tasa_cef_pct,
    SUM(f.Titular) AS cef_titular, SUM(f.TerceroAcuerdo) AS cef_tercero_acuerdo,
    SUM(f.Equivocado) AS equivocados_semana_siguiente, SUM(f.NoExiste) AS no_existe_semana_siguiente
FROM score.Caracteristicas AS c WITH (NOLOCK)
CROSS APPLY (
    SELECT 'EQUIVOCADO_DNI' AS Marca,
           (SELECT SUM(d.N_EQUIVOCADO) FROM score.TelefonoDia AS d WITH (NOLOCK)
            WHERE d.IdCartera = c.IdCartera AND d.DNI = c.DNI AND d.Telefono = c.Telefono
              AND d.Fecha >= DATEADD(DAY, -90, c.FechaCorte) AND d.Fecha < c.FechaCorte) AS Eventos90
    WHERE c.F_EQUIVOCADO_DNI = 'SI'
    UNION ALL
    SELECT 'NO_EXISTE',
           (SELECT SUM(d.N_NO_EXISTE) FROM score.TelefonoDia AS d WITH (NOLOCK)
            WHERE d.Telefono = c.Telefono
              AND d.Fecha >= DATEADD(DAY, -90, c.FechaCorte) AND d.Fecha < c.FechaCorte)
    WHERE c.F_NO_EXISTE = 'SI'
) AS m
CROSS APPLY (
    SELECT SUM(d.N_TITULAR) AS Titular, SUM(d.N_TERCERO_ACUERDO) AS TerceroAcuerdo,
           SUM(d.N_EQUIVOCADO) AS Equivocado, SUM(d.N_NO_EXISTE) AS NoExiste
    FROM score.TelefonoDia AS d WITH (NOLOCK)
    WHERE d.IdCartera = c.IdCartera AND d.DNI = c.DNI AND d.Telefono = c.Telefono
      AND d.Fecha >= c.FechaCorte AND d.Fecha < DATEADD(DAY, 7, c.FechaCorte)
) AS f
WHERE c.Poblacion = 'MARCADOS'
GROUP BY m.Marca, CASE WHEN m.Eventos90 = 1 THEN '1 evento' WHEN m.Eventos90 = 2 THEN '2 eventos' ELSE '3+ eventos' END
ORDER BY m.Marca, eventos_en_90_dias;
