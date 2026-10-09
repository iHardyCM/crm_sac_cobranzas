CREATE OR ALTER PROCEDURE dbo.SP_CRM_CONTROL_HORARIO_GESTION_RECUPERO_V2
    @Fecha DATE = NULL,
    @IdCartera INT = NULL,
    @IdUsuario INT = NULL
AS
BEGIN
    SET NOCOUNT ON;

    IF @Fecha IS NULL
        SET @Fecha = CAST(GETDATE() AS DATE);

    DECLARE @FechaInicio DATETIME = CAST(@Fecha AS DATETIME);
    DECLARE @FechaFin DATETIME = DATEADD(DAY, 1, @FechaInicio);

    DECLARE @MesInicio DATE = DATEFROMPARTS(YEAR(@Fecha), MONTH(@Fecha), 1);
    DECLARE @MesFin DATE = DATEADD(MONTH, 1, @MesInicio);

    /* ============================================================
       V2 - OPTIMIZACION (mismo resultado que la version original)

       La version original cruzaba COMPROMISO con GESTION (14 millones de
       filas) en 5 consultas distintas y SQL Server elegia un HASH JOIN que
       leia toda la tabla GESTION y derramaba a tempdb. Aqui se materializa
       una sola vez lo del dia (pocas filas) y el resto de consultas lee
       esas tablas temporales:

         #GEST_DIA   gestiones del dia (busqueda por FECHA)
         #COMP_DIA   compromisos generados o a pagar hoy (pocas filas)
         #COMP_GEST  esos compromisos con su gestion (busqueda por IDGESTION)

       Filtros, formulas y columnas de salida NO cambian.
       ============================================================ */

    SELECT
        G.IDGESTION,
        G.IDCARTERA,
        G.IDUSUARIO,
        G.HORA,
        G.TIPOCONTACTO,
        G.DNI,
        G.IDCLIENTE
    INTO #GEST_DIA
    FROM SISCOB.DBO.GESTION G WITH (NOLOCK)
    WHERE
        G.FECHA >= @FechaInicio
        AND G.FECHA < @FechaFin
        AND G.IDUSUARIO IS NOT NULL
        AND (@IdCartera IS NULL OR G.IDCARTERA = @IdCartera)
        AND (@IdUsuario IS NULL OR G.IDUSUARIO = @IdUsuario)
    OPTION (RECOMPILE);

    SELECT
        C.IDGESTION,
        C.FECHAGENERO,
        C.FECHACOMPROMISO,
        C.MONTO,
        C.PAGADO,
        C.MONTOPAGADO
    INTO #COMP_DIA
    FROM SISCOB.DBO.COMPROMISO C WITH (NOLOCK)
    WHERE
        (C.FECHAGENERO >= @FechaInicio AND C.FECHAGENERO < @FechaFin)
        OR (C.FECHACOMPROMISO >= @FechaInicio AND C.FECHACOMPROMISO < @FechaFin)
    OPTION (RECOMPILE);

    SELECT
        G.IDCARTERA,
        G.IDUSUARIO,
        CD.FECHAGENERO,
        CD.FECHACOMPROMISO,
        CD.MONTO,
        CD.PAGADO,
        CD.MONTOPAGADO
    INTO #COMP_GEST
    FROM #COMP_DIA CD
    INNER JOIN SISCOB.DBO.GESTION G WITH (NOLOCK)
        ON CD.IDGESTION = G.IDGESTION
    WHERE
        G.IDUSUARIO IS NOT NULL
        AND (@IdCartera IS NULL OR G.IDCARTERA = @IdCartera)
        AND (@IdUsuario IS NULL OR G.IDUSUARIO = @IdUsuario)
    OPTION (RECOMPILE);

    /* ============================================================
       CONTROL HORARIO DE GESTIÓN Y RECUPERO

       Reglas:
       - GESTION cruza con USUARIO por IDUSUARIO
       - GESTION cruza con COMPROMISO por IDGESTION
       - TIPOCONTACTO: 1 = CEF, 2 = CNE, 3 = NOC
       - Clientes únicos: DNI + IDCLIENTE + IDCARTERA del mes actual
       - PDP generado: FECHAGENERO del día + MONTO > 0
       - Proyectado: FECHACOMPROMISO del día + MONTO > 0
       - Pagado: FECHACOMPROMISO del día + MONTOPAGADO > 0 + PAGADO = 'SI'
       ============================================================ */

    ;WITH GESTIONES_DIA AS (
        SELECT
            G.IDCARTERA,
            G.IDUSUARIO,

            USUARIO_AGENTE =
                MAX(U.USUARIO),

            AGENTE =
                CONCAT(
                    MAX(U.USUARIO),
                    ' - ',
                    MAX(ISNULL(U.NOMBRES, '')),
                    ' ',
                    MAX(ISNULL(U.APELLIDOS, ''))
                ),

            GESTIONES =
                COUNT(1),

            CEF =
                SUM(CASE WHEN G.TIPOCONTACTO = 1 THEN 1 ELSE 0 END),

            CNE =
                SUM(CASE WHEN G.TIPOCONTACTO = 2 THEN 1 ELSE 0 END),

            NOC =
                SUM(CASE WHEN G.TIPOCONTACTO = 3 THEN 1 ELSE 0 END),

            ULTIMA_GESTION =
                MAX(G.HORA)
        FROM #GEST_DIA G
        LEFT JOIN SISCOB.DBO.USUARIO U WITH (NOLOCK)
            ON G.IDUSUARIO = U.IDUSUARIO
        GROUP BY
            G.IDCARTERA,
            G.IDUSUARIO
    ),

    CLIENTES_UNICOS_MES AS (
        SELECT
            G.IDCARTERA,
            G.IDUSUARIO,

            CLIENTES_GESTIONADOS =
                COUNT(DISTINCT
                    CONCAT(
                        ISNULL(CAST(G.DNI AS VARCHAR(30)), ''),
                        '|',
                        ISNULL(CAST(G.IDCLIENTE AS VARCHAR(30)), ''),
                        '|',
                        ISNULL(CAST(G.IDCARTERA AS VARCHAR(30)), '')
                    )
                )
        FROM SISCOB.DBO.GESTION G WITH (NOLOCK)
        WHERE
            G.FECHA >= @MesInicio
            AND G.FECHA < @MesFin
            AND G.IDUSUARIO IS NOT NULL
            AND ISNULL(G.DNI, '') <> ''
            AND G.IDCLIENTE IS NOT NULL
            AND G.IDCARTERA IS NOT NULL
            AND (@IdCartera IS NULL OR G.IDCARTERA = @IdCartera)
            AND (@IdUsuario IS NULL OR G.IDUSUARIO = @IdUsuario)
        GROUP BY
            G.IDCARTERA,
            G.IDUSUARIO
    ),

    PDP_GENERADO_DIA AS (
        SELECT
            C.IDCARTERA,
            C.IDUSUARIO,

            Q_PDP_GEN =
                COUNT(1),

            PDP_GEN =
                SUM(ISNULL(C.MONTO, 0))
        FROM #COMP_GEST C
        WHERE
            C.FECHAGENERO >= @FechaInicio
            AND C.FECHAGENERO < @FechaFin
            AND ISNULL(C.MONTO, 0) > 0
        GROUP BY
            C.IDCARTERA,
            C.IDUSUARIO
    ),

    PROYECTADO_DIA AS (
        SELECT
            C.IDCARTERA,
            C.IDUSUARIO,

            Q_PROYECTADO =
                COUNT(1),

            PROYECTADO =
                SUM(ISNULL(C.MONTO, 0)),

            Q_PAGADOS =
                SUM(
                    CASE
                        WHEN UPPER(LTRIM(RTRIM(ISNULL(C.PAGADO, '')))) IN ('SI', 'SÍ')
                             AND ISNULL(C.MONTOPAGADO, 0) > 0
                        THEN 1
                        ELSE 0
                    END
                ),

            PAGO =
                SUM(
                    CASE
                        WHEN UPPER(LTRIM(RTRIM(ISNULL(C.PAGADO, '')))) IN ('SI', 'SÍ')
                             AND ISNULL(C.MONTOPAGADO, 0) > 0
                        THEN ISNULL(C.MONTOPAGADO, 0)
                        ELSE 0
                    END
                ),

            Q_PENDIENTES =
                SUM(
                    CASE
                        WHEN NOT (
                            UPPER(LTRIM(RTRIM(ISNULL(C.PAGADO, '')))) IN ('SI', 'SÍ')
                            AND ISNULL(C.MONTOPAGADO, 0) > 0
                        )
                        THEN 1
                        ELSE 0
                    END
                )
        FROM #COMP_GEST C
        WHERE
            C.FECHACOMPROMISO >= @FechaInicio
            AND C.FECHACOMPROMISO < @FechaFin
            AND ISNULL(C.MONTO, 0) > 0
        GROUP BY
            C.IDCARTERA,
            C.IDUSUARIO
    ),

    BASE_AGENTES AS (
        SELECT IDCARTERA, IDUSUARIO FROM GESTIONES_DIA
        UNION
        SELECT IDCARTERA, IDUSUARIO FROM CLIENTES_UNICOS_MES
        UNION
        SELECT IDCARTERA, IDUSUARIO FROM PDP_GENERADO_DIA
        UNION
        SELECT IDCARTERA, IDUSUARIO FROM PROYECTADO_DIA
    ),

    CONSOLIDADO AS (
        SELECT
            B.IDCARTERA,
            B.IDUSUARIO,

            USUARIO_AGENTE =
                COALESCE(GD.USUARIO_AGENTE, U.USUARIO),

            AGENTE =
                COALESCE(
                    GD.AGENTE,
                    CONCAT(
                        ISNULL(U.USUARIO, ''),
                        ' - ',
                        ISNULL(U.NOMBRES, ''),
                        ' ',
                        ISNULL(U.APELLIDOS, '')
                    )
                ),

            GESTIONES =
                ISNULL(GD.GESTIONES, 0),

            CLIENTES_GESTIONADOS_MES =
                ISNULL(CUM.CLIENTES_GESTIONADOS, 0),

            CEF =
                ISNULL(GD.CEF, 0),

            CNE =
                ISNULL(GD.CNE, 0),

            NOC =
                ISNULL(GD.NOC, 0),

            PORC_CEF =
                CAST(
                    CASE
                        WHEN ISNULL(GD.GESTIONES, 0) = 0 THEN 0
                        ELSE ISNULL(GD.CEF, 0) * 100.0 / GD.GESTIONES
                    END
                AS DECIMAL(10,2)),

            Q_PDP_GEN =
                ISNULL(PG.Q_PDP_GEN, 0),

            PDP_GEN =
                ISNULL(PG.PDP_GEN, 0),

            TC =
                CAST(
                    CASE
                        WHEN ISNULL(GD.CEF, 0) = 0 THEN 0
                        ELSE ISNULL(PG.Q_PDP_GEN, 0) * 100.0 / GD.CEF
                    END
                AS DECIMAL(10,2)),

            Q_PROYECTADO =
                ISNULL(PD.Q_PROYECTADO, 0),

    PROYECTADO =
                ISNULL(PD.PROYECTADO, 0),

            Q_PAGADOS =
                ISNULL(PD.Q_PAGADOS, 0),

            PAGO =
                ISNULL(PD.PAGO, 0),

            Q_PENDIENTES =
                ISNULL(PD.Q_PENDIENTES, 0),

            AVANCE =
                CAST(
                    CASE
                        WHEN ISNULL(PD.PROYECTADO, 0) = 0 THEN 0
                        ELSE ISNULL(PD.PAGO, 0) * 100.0 / PD.PROYECTADO
                    END
                AS DECIMAL(10,2)),

            PENDIENTE =
                CASE
                    WHEN ISNULL(PD.PROYECTADO, 0) - ISNULL(PD.PAGO, 0) < 0 THEN 0
                    ELSE ISNULL(PD.PROYECTADO, 0) - ISNULL(PD.PAGO, 0)
                END,

            ULTIMA_GESTION =
                GD.ULTIMA_GESTION
        FROM BASE_AGENTES B
        LEFT JOIN GESTIONES_DIA GD
            ON B.IDCARTERA = GD.IDCARTERA
            AND B.IDUSUARIO = GD.IDUSUARIO
        LEFT JOIN CLIENTES_UNICOS_MES CUM
            ON B.IDCARTERA = CUM.IDCARTERA
            AND B.IDUSUARIO = CUM.IDUSUARIO
        LEFT JOIN PDP_GENERADO_DIA PG
            ON B.IDCARTERA = PG.IDCARTERA
            AND B.IDUSUARIO = PG.IDUSUARIO
        LEFT JOIN PROYECTADO_DIA PD
            ON B.IDCARTERA = PD.IDCARTERA
            AND B.IDUSUARIO = PD.IDUSUARIO
        LEFT JOIN SISCOB.DBO.USUARIO U WITH (NOLOCK)
            ON B.IDUSUARIO = U.IDUSUARIO
    )

    SELECT
        IDCARTERA,
        IDUSUARIO,
        USUARIO_AGENTE,
        AGENTE,
        GESTIONES,
        CLIENTES_GESTIONADOS_MES,
        CEF,
        CNE,
        NOC,
        PORC_CEF,
        Q_PDP_GEN,
        PDP_GEN,
        TC,
        Q_PROYECTADO,
        PROYECTADO,
        Q_PAGADOS,
        PAGO,
        Q_PENDIENTES,
        AVANCE,
        PENDIENTE,
        ULTIMA_GESTION,

        ACCION =
            CASE
                WHEN ISNULL(GESTIONES, 0) = 0
                    THEN 'SIN GESTIÓN'

                WHEN ISNULL(PROYECTADO, 0) > 0
                     AND ISNULL(PAGO, 0) >= ISNULL(PROYECTADO, 0)
                    THEN 'CUMPLIÓ PROYECTADO'

                WHEN ISNULL(PROYECTADO, 0) > 0
                     AND ISNULL(PAGO, 0) = 0
                    THEN 'PRIORIZAR PDP DE HOY'

                WHEN ISNULL(PROYECTADO, 0) > ISNULL(PAGO, 0)
                    THEN 'DAR SEGUIMIENTO'

                WHEN ISNULL(CEF, 0) = 0
                     AND ISNULL(GESTIONES, 0) > 0
                    THEN 'SIN CONTACTO EFECTIVO'

                WHEN ISNULL(Q_PDP_GEN, 0) = 0
                     AND ISNULL(CEF, 0) > 0
                    THEN 'CONTACTA PERO NO CIERRA'

                WHEN ISNULL(PDP_GEN, 0) > 0
                    THEN 'BUEN CIERRE'

                ELSE 'EN GESTIÓN'
            END,

        COLOR_ACCION =
            CASE
                WHEN ISNULL(GESTIONES, 0) = 0
                    THEN 'GRIS'

                WHEN ISNULL(PROYECTADO, 0) > 0
                     AND ISNULL(PAGO, 0) >= ISNULL(PROYECTADO, 0)
                    THEN 'VERDE'

                WHEN ISNULL(PROYECTADO, 0) > 0
                     AND ISNULL(PAGO, 0) = 0
                    THEN 'ROJO'

                WHEN ISNULL(PROYECTADO, 0) > ISNULL(PAGO, 0)
                    THEN 'AMBAR'

                WHEN ISNULL(CEF, 0) = 0
                     AND ISNULL(GESTIONES, 0) > 0
                    THEN 'ROJO'

                WHEN ISNULL(Q_PDP_GEN, 0) = 0
                     AND ISNULL(CEF, 0) > 0
                    THEN 'AMBAR'

                WHEN ISNULL(PDP_GEN, 0) > 0
                    THEN 'VERDE'

                ELSE 'AZUL'
            END
    INTO #CONTROL_HORARIO
    FROM CONSOLIDADO
    OPTION (RECOMPILE);

    /* ============================================================
       RESULTADO 1: DETALLE POR AGENTE
       ============================================================ */

    SELECT          IDCARTERA,
        IDUSUARIO,
        USUARIO_AGENTE,
        AGENTE,
        GESTIONES,
        CLIENTES_GESTIONADOS_MES,
        CEF,
        CNE,
        NOC,
        PORC_CEF,
        Q_PDP_GEN,
        PDP_GEN,
        TC,
        Q_PROYECTADO,
        PROYECTADO,
        Q_PAGADOS,
        PAGO,
        Q_PENDIENTES,
        AVANCE,
        PENDIENTE,
        ULTIMA_GESTION,
        ACCION,
        COLOR_ACCION
    FROM #CONTROL_HORARIO
    ORDER BY
        CEF DESC,
        GESTIONES DESC;

    /* ============================================================
       RESULTADO 2: KPIS SUPERIORES
       ============================================================ */

    SELECT
        FECHA =
            @Fecha,

        MES_INICIO =
            @MesInicio,

        ULTIMO_CORTE =
            CONVERT(VARCHAR(8), GETDATE(), 108),

        GESTIONES_ACUMULADAS =
            ISNULL(SUM(GESTIONES), 0),

        CLIENTES_GESTIONADOS_MES =
            ISNULL(SUM(CLIENTES_GESTIONADOS_MES), 0),

        CEF_ACUMULADOS =
            ISNULL(SUM(CEF), 0),

        CNE_ACUMULADOS =
            ISNULL(SUM(CNE), 0),

        NOC_ACUMULADOS =
            ISNULL(SUM(NOC), 0),

        PORC_CEF_GENERAL =
            CAST(
                CASE
                    WHEN ISNULL(SUM(GESTIONES), 0) = 0 THEN 0
                    ELSE ISNULL(SUM(CEF), 0) * 100.0 / SUM(GESTIONES)
                END
            AS DECIMAL(10,2)),

        Q_PDP_GENERADAS =
            ISNULL(SUM(Q_PDP_GEN), 0),

        PDP_GENERADO =
            ISNULL(SUM(PDP_GEN), 0),

        TC_GENERAL =
            CAST(
                CASE
                    WHEN ISNULL(SUM(CEF), 0) = 0 THEN 0
                    ELSE ISNULL(SUM(Q_PDP_GEN), 0) * 100.0 / SUM(CEF)
                END
            AS DECIMAL(10,2)),

        Q_PROYECTADO_HOY =
            ISNULL(SUM(Q_PROYECTADO), 0),

        PROYECTADO_HOY =
            ISNULL(SUM(PROYECTADO), 0),

        Q_PAGADOS_HOY =
            ISNULL(SUM(Q_PAGADOS), 0),

        PAGO_HOY =
            ISNULL(SUM(PAGO), 0),

        AVANCE_DIA =
            CAST(
                CASE
                    WHEN ISNULL(SUM(PROYECTADO), 0) = 0 THEN 0
                    ELSE ISNULL(SUM(PAGO), 0) * 100.0 / SUM(PROYECTADO)
                END
            AS DECIMAL(10,2)),

        PENDIENTE_HOY =
            ISNULL(SUM(PENDIENTE), 0),

        AGENTES_TOTAL =
            COUNT(1),

        AGENTES_CRITICOS =
            ISNULL(SUM(
                CASE
                    WHEN COLOR_ACCION IN ('ROJO', 'AMBAR') THEN 1
                    ELSE 0
                END
            ), 0),

        AGENTES_SIN_GESTION =
            ISNULL(SUM(
                CASE
                    WHEN ACCION = 'SIN GESTIÓN' THEN 1
                    ELSE 0
                END
            ), 0),

        AGENTES_SIN_PDP =
            ISNULL(SUM(
                CASE
                    WHEN Q_PDP_GEN = 0 AND CEF > 0 THEN 1
                    ELSE 0
                END
            ), 0)
    FROM #CONTROL_HORARIO;

    /* ============================================================
       RESULTADO 3: TOP 5 MEJORES AVANCES
       ============================================================ */

    SELECT TOP 5
        TIPO_RANKING = 'TOP_AVANCE',
        IDUSUARIO,
        USUARIO_AGENTE,
        AGENTE,
        PROYECTADO,
        PAGO,
        AVANCE,
        PENDIENTE
    FROM #CONTROL_HORARIO
    WHERE PROYECTADO > 0
    ORDER BY
        AVANCE DESC,
        PAGO DESC;

    /* ============================================================
       RESULTADO 4: TOP 5 PENDIENTES CRÍTICOS
       ============================================================ */

    SELECT TOP 5
        TIPO_RANKING = 'PENDIENTES_CRITICOS',
        IDUSUARIO,
        USUARIO_AGENTE,
        AGENTE,
        PROYECTADO,
       PAGO,
        AVANCE,
        PENDIENTE
    FROM #CONTROL_HORARIO
    WHERE PENDIENTE > 0
    ORDER BY
        PENDIENTE DESC,
        PROYECTADO DESC;

    /* ============================================================
       RESULTADO 5: ALERTAS DEL CORTE
       ============================================================ */

    SELECT
        ALERTA = 'Agentes sin PDP con contacto efectivo',
        CANTIDAD = COUNT(1),
        PRIORIDAD = 'MEDIA',
        COLOR = 'AMBAR'
    FROM #CONTROL_HORARIO
    WHERE Q_PDP_GEN = 0
      AND CEF > 0

    UNION ALL

    SELECT
        ALERTA = 'Agentes con proyectado de hoy sin pago',
        CANTIDAD = COUNT(1),
        PRIORIDAD = 'ALTA',
        COLOR = 'ROJO'
    FROM #CONTROL_HORARIO
    WHERE PROYECTADO > 0
      AND PAGO = 0

    UNION ALL

    SELECT
        ALERTA = 'Agentes con avance menor al 20%',
        CANTIDAD = COUNT(1),
        PRIORIDAD = 'ALTA',
        COLOR = 'ROJO'
    FROM #CONTROL_HORARIO
    WHERE PROYECTADO > 0
      AND AVANCE < 20

    UNION ALL

    SELECT
        ALERTA = 'Agentes sin contacto efectivo',
        CANTIDAD = COUNT(1),
        PRIORIDAD = 'MEDIA',
        COLOR = 'AMBAR'
    FROM #CONTROL_HORARIO
    WHERE GESTIONES > 0
      AND CEF = 0

    UNION ALL

    SELECT
        ALERTA = 'Proyectado pendiente',
        CANTIDAD = CAST(ISNULL(SUM(PENDIENTE), 0) AS INT),
        PRIORIDAD = 'INFO',
        COLOR = 'AZUL'
    FROM #CONTROL_HORARIO
    WHERE PENDIENTE > 0;

    DROP TABLE #CONTROL_HORARIO;


 /* ============================================================
    RESULTADO 6: CORTE POR HORA
    Mide actividad operativa por hora:
    - Gestiones por hora según G.HORA
    - CEF/CNE/NOC por hora según TIPOCONTACTO
    - PDP generadas por hora según C.FECHAGENERO
    - Monto generado por hora según C.MONTO
    No incluye proyectado/pago por hora.
    ============================================================ */

 ;WITH HORAS AS (
  SELECT 6 AS HORA_CORTE
  UNION ALL SELECT 7
  UNION ALL SELECT 8
  UNION ALL SELECT 9
  UNION ALL SELECT 10
  UNION ALL SELECT 11
  UNION ALL SELECT 12
  UNION ALL SELECT 13
  UNION ALL SELECT 14
  UNION ALL SELECT 15
  UNION ALL SELECT 16
  UNION ALL SELECT 17
  UNION ALL SELECT 18
  UNION ALL SELECT 19
  UNION ALL SELECT 20
 ),

 GESTIONES_HORA AS (
  SELECT
   HORA_CORTE = DATEPART(HOUR, G.HORA),

   GESTIONES = COUNT(1),

   CLIENTES_GESTIONADOS_HORA =
    COUNT(DISTINCT
     CONCAT(
      ISNULL(CAST(G.DNI AS VARCHAR(30)), ''),
      '|',
      ISNULL(CAST(G.IDCLIENTE AS VARCHAR(30)), ''),
      '|',
      ISNULL(CAST(G.IDCARTERA AS VARCHAR(30)), '')
     )
    ),

   CEF = SUM(CASE WHEN G.TIPOCONTACTO = 1 THEN 1 ELSE 0 END),
   CNE = SUM(CASE WHEN G.TIPOCONTACTO = 2 THEN 1 ELSE 0 END),
   NOC = SUM(CASE WHEN G.TIPOCONTACTO = 3 THEN 1 ELSE 0 END)
  FROM #GEST_DIA G
  WHERE
   DATEPART(HOUR, G.HORA) BETWEEN 6 AND 20
  GROUP BY
   DATEPART(HOUR, G.HORA)
 ),

 PDP_HORA AS (
  SELECT
   HORA_CORTE = DATEPART(HOUR, C.FECHAGENERO),

   Q_PDP_GEN = COUNT(1),

   PDP_GEN = SUM(ISNULL(C.MONTO, 0))
  FROM #COMP_GEST C
  WHERE
   C.FECHAGENERO >= @FechaInicio
   AND C.FECHAGENERO < @FechaFin
   AND ISNULL(C.MONTO, 0) > 0
   AND DATEPART(HOUR, C.FECHAGENERO) BETWEEN 6 AND 20
  GROUP BY
   DATEPART(HOUR, C.FECHAGENERO)
 )

 SELECT
  HORA_CORTE = H.HORA_CORTE,

  RANGO_HORA =
   CONCAT(
    RIGHT('00' + CAST(H.HORA_CORTE AS VARCHAR(2)), 2),
    ':00 - ',
    RIGHT('00' + CAST(H.HORA_CORTE + 1 AS VARCHAR(2)), 2),
    ':00'
   ),

  GESTIONES = ISNULL(GH.GESTIONES, 0),

  CLIENTES_GESTIONADOS_HORA =
   ISNULL(GH.CLIENTES_GESTIONADOS_HORA, 0),

  CEF = ISNULL(GH.CEF, 0),

  CNE = ISNULL(GH.CNE, 0),

  NOC = ISNULL(GH.NOC, 0),

  PORC_CEF =
   CAST(
    CASE
     WHEN ISNULL(GH.GESTIONES, 0) = 0 THEN 0
     ELSE ISNULL(GH.CEF, 0) * 100.0 / GH.GESTIONES
    END
   AS DECIMAL(10,2)),

  Q_PDP_GEN =
   ISNULL(PH.Q_PDP_GEN, 0),

  PDP_GEN =
   ISNULL(PH.PDP_GEN, 0),

  TC =
   CAST(
    CASE
     WHEN ISNULL(GH.CEF, 0) = 0 THEN 0
     ELSE ISNULL(PH.Q_PDP_GEN, 0) * 100.0 / GH.CEF
    END
   AS DECIMAL(10,2))
 FROM HORAS H
 LEFT JOIN GESTIONES_HORA GH
  ON H.HORA_CORTE = GH.HORA_CORTE
 LEFT JOIN PDP_HORA PH
  ON H.HORA_CORTE = PH.HORA_CORTE
 ORDER BY
  H.HORA_CORTE;


 /* ============================================================
    RESULTADO 7: CORTE POR AGENTE Y HORA
    Opcional para drilldown.
    ============================================================ */

 ;WITH GESTIONES_AGENTE_HORA AS (
  SELECT
   G.IDCARTERA,
   G.IDUSUARIO,

   USUARIO_AGENTE = MAX(U.USUARIO),

   AGENTE =
    CONCAT(
     MAX(U.USUARIO),
     ' - ',
     MAX(ISNULL(U.NOMBRES, '')),
     ' ',
     MAX(ISNULL(U.APELLIDOS, ''))
    ),

   HORA_CORTE = DATEPART(HOUR, G.HORA),

   GESTIONES = COUNT(1),

   CEF = SUM(CASE WHEN G.TIPOCONTACTO = 1 THEN 1 ELSE 0 END),

   CNE = SUM(CASE WHEN G.TIPOCONTACTO = 2 THEN 1 ELSE 0 END),

   NOC = SUM(CASE WHEN G.TIPOCONTACTO = 3 THEN 1 ELSE 0 END)
  FROM #GEST_DIA G
  LEFT JOIN SISCOB.DBO.USUARIO U WITH (NOLOCK)
   ON G.IDUSUARIO = U.IDUSUARIO
  WHERE
   DATEPART(HOUR, G.HORA) BETWEEN 6 AND 20
  GROUP BY
   G.IDCARTERA,
   G.IDUSUARIO,
   DATEPART(HOUR, G.HORA)
 ),

 PDP_AGENTE_HORA AS (
  SELECT
   C.IDCARTERA,
   C.IDUSUARIO,

   HORA_CORTE = DATEPART(HOUR, C.FECHAGENERO),

   Q_PDP_GEN = COUNT(1),

   PDP_GEN = SUM(ISNULL(C.MONTO, 0))
  FROM #COMP_GEST C
  WHERE
   C.FECHAGENERO >= @FechaInicio
   AND C.FECHAGENERO < @FechaFin
   AND ISNULL(C.MONTO, 0) > 0
   AND DATEPART(HOUR, C.FECHAGENERO) BETWEEN 6 AND 20
  GROUP BY
   C.IDCARTERA,
   C.IDUSUARIO,
   DATEPART(HOUR, C.FECHAGENERO)
 ),

 BASE_AGENTE_HORA AS (
  SELECT IDCARTERA, IDUSUARIO, HORA_CORTE FROM GESTIONES_AGENTE_HORA
  UNION
  SELECT IDCARTERA, IDUSUARIO, HORA_CORTE FROM PDP_AGENTE_HORA
 )

 SELECT
  B.IDCARTERA,
  B.IDUSUARIO,

  USUARIO_AGENTE =
   COALESCE(GH.USUARIO_AGENTE, U.USUARIO),

  AGENTE =
   COALESCE(
    GH.AGENTE,
    CONCAT(
     ISNULL(U.USUARIO, ''),
     ' - ',
     ISNULL(U.NOMBRES, ''),
     ' ',
     ISNULL(U.APELLIDOS, '')
    )
   ),

  B.HORA_CORTE,

  RANGO_HORA =
   CONCAT(
    RIGHT('00' + CAST(B.HORA_CORTE AS VARCHAR(2)), 2),
    ':00 - ',
    RIGHT('00' + CAST(B.HORA_CORTE + 1 AS VARCHAR(2)), 2),
    ':00'
   ),

  GESTIONES = ISNULL(GH.GESTIONES, 0),

  CEF = ISNULL(GH.CEF, 0),

  CNE = ISNULL(GH.CNE, 0),

  NOC = ISNULL(GH.NOC, 0),

  PORC_CEF =
   CAST(
    CASE
     WHEN ISNULL(GH.GESTIONES, 0) = 0 THEN 0
     ELSE ISNULL(GH.CEF, 0) * 100.0 / GH.GESTIONES
    END
   AS DECIMAL(10,2)),

  Q_PDP_GEN =
   ISNULL(PH.Q_PDP_GEN, 0),

  PDP_GEN =
   ISNULL(PH.PDP_GEN, 0),

  TC =
   CAST(
    CASE
     WHEN ISNULL(GH.CEF, 0) = 0 THEN 0
     ELSE ISNULL(PH.Q_PDP_GEN, 0) * 100.0 / GH.CEF
    END
   AS DECIMAL(10,2))
 FROM BASE_AGENTE_HORA B
 LEFT JOIN GESTIONES_AGENTE_HORA GH
  ON B.IDCARTERA = GH.IDCARTERA
  AND B.IDUSUARIO = GH.IDUSUARIO
  AND B.HORA_CORTE = GH.HORA_CORTE
 LEFT JOIN PDP_AGENTE_HORA PH
  ON B.IDCARTERA = PH.IDCARTERA
  AND B.IDUSUARIO = PH.IDUSUARIO
  AND B.HORA_CORTE = PH.HORA_CORTE
 LEFT JOIN SISCOB.DBO.USUARIO U WITH (NOLOCK)
  ON B.IDUSUARIO = U.IDUSUARIO
 ORDER BY
  B.HORA_CORTE,
  GESTIONES DESC,
  CEF DESC;
END;
