/* =====================================================================================
   crm_cierre_turno_fase3.sql  ·  Cierre de turno: Vigente Individual + CCM como un solo cuadro
   Hardy (26/11/2026): «vigente individual debe ir junto a CCM … tratado como uno solo».
   · Une la 128 al grupo 126 y quita el cuadro aparte de la 128.
   · Vigente (126 y 133): los agentes de otra cartera salen con su nombre (así los reportan los supervisores de
     vigente, p. ej. José Aarón de la 144), para que la PDP en soles y la contención caigan en la misma fila.
   Solo toca la tabla de grupos. Se puede correr más de una vez.
   ===================================================================================== */
USE CobAuto;
GO
SET NOCOUNT ON;

IF NOT EXISTS (SELECT 1 FROM dbo.CRM_CIERRE_TURNO_GRUPO WHERE IdGrupo = 126 AND IdCartera = 128)
    INSERT INTO dbo.CRM_CIERRE_TURNO_GRUPO (IdGrupo, Nombre, IdCartera) VALUES (126, N'Compartamos vigente individual + CCM', 128);
UPDATE dbo.CRM_CIERRE_TURNO_GRUPO SET Nombre = N'Compartamos vigente individual + CCM' WHERE IdGrupo = 126;
DELETE FROM dbo.CRM_CIERRE_TURNO_GRUPO WHERE IdGrupo = 128;
UPDATE dbo.CRM_CIERRE_TURNO_GRUPO SET ExternosEnBolsa = 0 WHERE IdGrupo IN (126, 133);
GO

SELECT IdGrupo, Nombre, IdCartera, ExternosEnBolsa FROM dbo.CRM_CIERRE_TURNO_GRUPO ORDER BY IdGrupo, IdCartera;
EXEC dbo.sp_CRM_CierreTurnoAgentes @IdGrupo = 126, @Fecha = NULL;
GO
