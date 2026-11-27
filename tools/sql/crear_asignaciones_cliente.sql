USE CobAuto;
GO

-- Responsable actual por cliente, cartera y motivo. No modifica Cliente.IdUsuario.
IF OBJECT_ID('dbo.CRM_ASIGNACION_CLIENTE', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.CRM_ASIGNACION_CLIENTE (
        IdAsignacion bigint IDENTITY(1,1) NOT NULL PRIMARY KEY,
        Tipo varchar(40) NOT NULL,
        IdCartera int NOT NULL,
        IdCliente int NOT NULL,
        AgenteUsuario varchar(50) NOT NULL,
        AsignadoPor varchar(50) NOT NULL,
        FechaAsignacion datetime2(0) NOT NULL CONSTRAINT DF_CRM_ASIG_FECHA DEFAULT (SYSDATETIME()),
        CONSTRAINT UQ_CRM_ASIG_CLIENTE_TIPO UNIQUE (Tipo, IdCartera, IdCliente)
    );
    CREATE INDEX IX_CRM_ASIG_BANDEJA
        ON dbo.CRM_ASIGNACION_CLIENTE (Tipo, AgenteUsuario, IdCartera)
        INCLUDE (IdCliente, FechaAsignacion);
END;
GO

IF OBJECT_ID('dbo.CRM_ASIGNACION_CLIENTE_EVENTO', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.CRM_ASIGNACION_CLIENTE_EVENTO (
        IdEvento bigint IDENTITY(1,1) NOT NULL PRIMARY KEY,
        Tipo varchar(40) NOT NULL,
        IdCartera int NOT NULL,
        IdCliente int NOT NULL,
        AgenteAnterior varchar(50) NULL,
        AgenteNuevo varchar(50) NOT NULL,
        UsuarioCambio varchar(50) NOT NULL,
        FechaCambio datetime2(0) NOT NULL CONSTRAINT DF_CRM_ASIG_EVT_FECHA DEFAULT (SYSDATETIME())
    );
    CREATE INDEX IX_CRM_ASIG_EVT_CLIENTE
        ON dbo.CRM_ASIGNACION_CLIENTE_EVENTO (Tipo, IdCartera, IdCliente, FechaCambio);
END;
GO
