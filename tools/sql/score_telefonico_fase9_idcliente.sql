/* =====================================================================================
   Generador de bases · fase 9 · IdCliente en el detalle de cada base             (16/11/2026)
   Base: CobAuto. Se puede volver a ejecutar.

   El archivo exportado lleva el IdCliente de siscob.dbo.Cliente (lo piden el predictivo y el preview).
   Se guarda al generar, junto con el teléfono, para que el archivo de una base no cambie después.
   Es el IdCliente del universo del score: cliente activo (A/N) de la cartera; si el DNI tiene varios,
   el mayor (misma regla de score.sp_ArmarUniversoCartera).

   ORDEN: ejecutar ANTES de reiniciar el backend (el código nuevo inserta esta columna al generar).
   Bases generadas antes de este cambio: el archivo toma el IdCliente del universo actual.
   ===================================================================================== */
USE CobAuto;
GO

IF COL_LENGTH('score.BaseDetalle', 'IdCliente') IS NULL
    ALTER TABLE score.BaseDetalle ADD IdCliente INT NULL;
GO
