USE CobAuto;
GO

IF COL_LENGTH('dbo.canales_carga', 'fecha_lanzamiento') IS NULL
BEGIN
    ALTER TABLE dbo.canales_carga
    ADD fecha_lanzamiento date NULL;
END;
GO

UPDATE dbo.canales_carga
SET fecha_lanzamiento = CAST(fecha_carga AS date)
WHERE fecha_lanzamiento IS NULL
  AND fecha_carga IS NOT NULL;
GO

IF NOT EXISTS (
    SELECT 1
    FROM sys.default_constraints dc
    INNER JOIN sys.columns c
        ON c.object_id = dc.parent_object_id
       AND c.column_id = dc.parent_column_id
    WHERE dc.parent_object_id = OBJECT_ID('dbo.canales_carga')
      AND c.name = 'fecha_lanzamiento'
)
BEGIN
    ALTER TABLE dbo.canales_carga
    ADD CONSTRAINT DF_canales_carga_fecha_lanzamiento
        DEFAULT (CONVERT(date, GETDATE())) FOR fecha_lanzamiento;
END;
GO

SELECT
    COUNT(*) AS total_cargas,
    SUM(CASE WHEN fecha_lanzamiento IS NULL THEN 1 ELSE 0 END) AS cargas_sin_fecha_lanzamiento,
    MIN(fecha_lanzamiento) AS primera_fecha_lanzamiento,
    MAX(fecha_lanzamiento) AS ultima_fecha_lanzamiento
FROM dbo.canales_carga;
GO
