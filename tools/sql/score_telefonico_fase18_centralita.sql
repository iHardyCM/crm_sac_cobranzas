/* =====================================================================================
   score_telefonico_fase18_centralita.sql
   Problema (diagnóstico 2611c, 20/11): el 99.7 % de las llamadas de centralita que no llegan a un
   asesor son las mismas llamadas de pgestion (máquina). Los filtros "Gestiones del teléfono en el mes"
   y "en 6 meses" sumaban humana + máquina + centralita: contaban doble los días con centralita.

   Regla nueva, por teléfono y día:
       gestiones = humana + el MAYOR entre máquina (pgestion) y centralita
   · Día con ambas fuentes: cuenta la llamada una vez.
   · Día sin pgestion (ej. 23/11): toma la centralita, no se pierde el día.
   · Día sin centralita (ej. 24 y 25/11): toma pgestion.

   No toca el score: sus intentos ya son humana + máquina (fase 3).
   Cambia solo score.sp_ArmarGestion (GestionesTelMes, GestionesTel6m) y la descripción de los 2 campos.

   Paso 1: correr con @Aplicar = 0 (simula: muestra cuántas veces está la expresión).
   Paso 2: @Aplicar = 1. Toma efecto en la próxima actualización (05:20) o con "Actualizar" por cartera.
   ===================================================================================== */
SET NOCOUNT ON;
DECLARE @Aplicar BIT = 0;

DECLARE @def NVARCHAR(MAX) = OBJECT_DEFINITION(OBJECT_ID('score.sp_ArmarGestion'));
DECLARE @viejo NVARCHAR(200) = N'td.IntentosHumano + td.IntentosMaquina + td.LlamadasCentralita';
DECLARE @nuevo NVARCHAR(300) = N'td.IntentosHumano + CASE WHEN td.IntentosMaquina >= td.LlamadasCentralita THEN td.IntentosMaquina ELSE td.LlamadasCentralita END';

IF @def IS NULL THROW 50001, 'No existe score.sp_ArmarGestion en esta base. Ejecuta el script en la base del score.', 1;

DECLARE @veces INT = (LEN(@def) - LEN(REPLACE(@def, @viejo, N''))) / LEN(@viejo);
DECLARE @yaParchado BIT = CASE WHEN CHARINDEX(N'CASE WHEN td.IntentosMaquina >= td.LlamadasCentralita', @def) > 0 THEN 1 ELSE 0 END;

SELECT @veces AS VecesExpresionAntigua, @yaParchado AS YaParchado,
       CASE WHEN @yaParchado = 1 AND @veces = 0 THEN 'Ya estaba aplicado: no hay nada que hacer'
            WHEN @veces = 2 THEN 'OK: se reemplazan las 2 (GestionesMes y Gestiones6m)'
            ELSE 'REVISAR: se esperaban 2 apariciones' END AS Diagnostico;

IF @Aplicar = 1
BEGIN
    IF @yaParchado = 1 AND @veces = 0
        PRINT 'score.sp_ArmarGestion ya tiene la regla nueva.';
    ELSE
    BEGIN
        IF @veces <> 2 THROW 50002, 'La expresión no aparece 2 veces en score.sp_ArmarGestion: no se modifica nada.', 1;
        SET @def = REPLACE(@def, @viejo, @nuevo);
        -- La definición guardada puede empezar con CREATE PROCEDURE o CREATE OR ALTER PROCEDURE
        DECLARE @p INT = PATINDEX(N'%CREATE%PROCEDURE%', @def);
        IF @p = 0 THROW 50003, 'No se encontró CREATE PROCEDURE en la definición.', 1;
        DECLARE @q INT = CHARINDEX(N'PROCEDURE', @def, @p);
        SET @def = STUFF(@def, @p, @q - @p, N'CREATE OR ALTER ');
        EXEC sys.sp_executesql @def;

        UPDATE score.Campo
        SET Descripcion = N'Intentos del mes al número: humanos + máquina. La centralita registra las mismas llamadas de máquina: se usa solo el día que falta pgestion (cuenta el mayor de los dos, nunca la suma).',
            Fuente = N'score.GestionTelefono ← score.TelefonoDia (humana, máquina y centralita; 6 meses)'
        WHERE Codigo = N'GESTIONES_TEL_MES';
        UPDATE score.Campo
        SET Descripcion = N'Intentos al número en 6 meses: humanos + máquina. La centralita registra las mismas llamadas de máquina: se usa solo el día que falta pgestion (cuenta el mayor de los dos, nunca la suma).',
            Fuente = N'score.GestionTelefono ← score.TelefonoDia (humana, máquina y centralita; 6 meses)'
        WHERE Codigo = N'GESTIONES_TEL_6M';

        PRINT 'Aplicado. Toma efecto en la próxima actualización de cada cartera.';
    END;

    -- Control
    SET @def = OBJECT_DEFINITION(OBJECT_ID('score.sp_ArmarGestion'));
    SELECT (LEN(@def) - LEN(REPLACE(@def, @viejo, N''))) / LEN(@viejo) AS VecesExpresionAntigua_Debe0,
           (LEN(@def) - LEN(REPLACE(@def, N'CASE WHEN td.IntentosMaquina >= td.LlamadasCentralita', N'')))
             / LEN(N'CASE WHEN td.IntentosMaquina >= td.LlamadasCentralita') AS VecesReglaNueva_Debe2;
END;
GO
