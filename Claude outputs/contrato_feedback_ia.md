# Feedback_IA — qué mide y qué no

**Módulo:** evaluación de calidad de llamadas de cobranza con IA, dentro del CRM `crm_sac_cobranzas`
**Pauta vigente:** Pauta general de evaluación, id_pauta 1, versión 1, aplicable a todas las carteras
**Pauta en borrador:** versión 2 — redefine PECUF.3 como declaración escalonada de montos (sección 3.1)
**Estado:** previo a producción
**Última revisión:** 16/09/2026

Este documento existe para que, cuando alguien pregunte "¿este número es confiable?", la respuesta esté escrita de antemano y no dependa de quién conteste.

---

## 1. Qué hace el módulo

Recibe la grabación de una llamada, la transcribe separando quién habla, evalúa la gestión del asesor contra los criterios de la pauta y entrega: un score, el detalle criterio por criterio con su evidencia, un relato de lo que pasó en la llamada y material de coaching.

El resultado **no es una nota final**. Es una preevaluación que Calidad revisa. La corrección humana se registra aparte y solo mueve la nota cuando se publica.

---

## 2. La regla de fondo

> Un criterio solo suma puntos si se pudo observar y se cumplió.
> Lo que no se puede observar no se aprueba por defecto ni se castiga: sale del cálculo y se declara.

De ahí salen cinco estados posibles por criterio:

| Estado | Suma puntos | Cuenta en el denominador | Significa |
|---|---|---|---|
| CUMPLE | Sí | Sí | Se observó y se cumplió |
| NO_CUMPLE | No | Sí | Se observó y no se cumplió |
| NO_APLICA | No | **No** | La situación que evalúa no ocurrió en esta llamada |
| NO_EVALUABLE | No | **No** | No hay fuente para verificarlo |
| REQUIERE_REVISION | No | **Sí** ⚠️ | Hay indicio pero no evidencia suficiente: decide una persona |

La fila marcada es un problema abierto. Ver sección 6.

---

## 3. Qué se mide hoy: 82 de 100 puntos

> Con la pauta v2 publicada pasan a ser **87 de 100**: PECUF.3 vuelve a medirse. Ver 3.1.

La pauta tiene 15 criterios en 4 bloques que suman 100 puntos. Tres criterios no se pueden medir con lo que hay disponible y quedan declarados como no evaluables.

### Se mide (82 puntos)

| Bloque | Criterio | Peso | Fuente |
|---|---|---|---|
| PECUF | PECUF.1 Falta de respeto | 20 | Audio |
| PECUF | PECUF.2 Escucha activa | 2 | Audio |
| PECUF | PECUF.4 Claridad con la información | 3 | Transcripción |
| PECN | PECN.1 Sondeo y diagnóstico | 5 | Transcripción |
| PECN | PECN.2 Negociación escalonada | 10 | Transcripción |
| PECN | PECN.3 Manejo de objeciones | 15 | Transcripción |
| PECC | PECN.4 Cierre de negociación | 10 | Transcripción |
| PECC | PECC.1 Respeto por la entidad y sus canales | 5 | Transcripción |
| PECC | PECC.2 Confirmación del acuerdo | 5 | Transcripción |
| PENC | PENC.1 Saludo de bienvenida | 2 | Audio |
| PENC | PENC.3 Claridad del lenguaje oral | 3 | Transcripción |
| PENC | PENC.4 Despedida adecuada | 2 | Audio |

### No se mide (18 puntos)

| Criterio | Peso | Por qué | Qué haría falta |
|---|---|---|---|
| PECUF.3 Precisión de la información de la deuda | 5 | Su fuente es MULTIFUENTE. **Queda así solo mientras la v1 siga publicada**: con la v2 este criterio vuelve a medirse (3.1) | Publicar la pauta v2 |
| PECC.3 Tipificación de la gestión | 10 | Su fuente es TIPIFICACION: lo que el asesor registró en el sistema no está en el audio | Cruce contra la tipificación registrada |
| PENC.2 Tono de voz | 3 | Requiere análisis acústico. Juzgar el tono leyendo texto sería inventar | Análisis acústico del audio |

Estos tres criterios **no se aprueban por defecto**. Antes ponían CUMPLE, es decir regalaban el punto; hoy quedan en NO_EVALUABLE y salen del denominador.

**El score se calcula sobre los criterios realmente observados**, no sobre 100. Una llamada donde además no aplicó algún criterio se evalúa sobre menos todavía, y eso es correcto: comparar contra lo que no ocurrió es lo que produce números falsos.

---

## 3.1 PECUF.3 con la pauta v2: declaración escalonada de montos

**Decisión de negocio del 16/09/2026:** no se usará una base de deudas, capitales y campañas. Se deja de verificar que la cifra sea correcta y se pasa a medir el **fraseo**: que el asesor haya declarado los montos en la llamada.

El criterio se renombra a *Declaración escalonada de montos*, su fuente cambia de MULTIFUENTE a TRANSCRIPCIÓN y conserva sus 5 puntos.

### La escalera

```
deuda total  --rechazo explícito-->  capital  --rechazo explícito-->  campaña
```

- Declarar la **deuda total con su monto** es obligatorio y no depende de lo que haga el cliente.
- Solo se baja de nivel ante **rechazo o imposibilidad explícita** ("no puedo", "no tengo", "es mucho"). Que el cliente evada, pregunte otra cosa o cambie de tema **no es rechazo**: si no se niega, no se le exige al asesor bajar de nivel.
- Si acepta en cualquier nivel, la escalera se detiene ahí. No hace falta mencionar los niveles siguientes.
- El orden es **estricto**: saltar de la deuda total a la campaña sin pasar por el capital es incumplimiento.

### Cómo se resuelve el estado

| Situación | Estado |
|---|---|
| No hay intervenciones del asesor | NO_APLICA |
| No declaró la deuda total | NO_CUMPLE |
| Declaró la deuda total y el cliente no la rechazó | CUMPLE |
| Rechazo del total, no ofreció capital | NO_CUMPLE |
| Rechazo del total, saltó a campaña sin capital | NO_CUMPLE |
| Rechazo del total, ofreció capital y no fue rechazado | CUMPLE |
| Rechazo del total y del capital, ofreció campaña | CUMPLE |
| Rechazo del total y del capital, no llegó a campaña | NO_CUMPLE |
| Mencionó el concepto pero no se reconoce el monto | REQUIERE_REVISION |

Esa última fila es deliberada. El transcriptor devuelve los números tanto en dígitos como en palabras y a veces los deforma; si el concepto aparece pero la cifra no se reconoce, la llamada va a revisión humana en lugar de marcarse como incumplimiento. Un error de transcripción no puede convertirse en una falta del asesor.

### Qué ya no se mide

Que el monto sea **correcto**. Un importe equivocado pero declarado cumple este criterio. La exactitud de la cifra dejó de estar en el alcance del módulo por decisión de negocio, y no hay forma de verificarla sin la base de deudas.

### Separación con PECN.2

Para no descontar dos veces la misma conducta, la v2 acota los dos criterios:

- **PECUF.3** evalúa los **montos**: cuáles se declararon y en qué orden.
- **PECN.2** evalúa la **forma de pago**: cuotas, plazos, fechas, canal y viabilidad según lo que el cliente expuso.

---

## 4. Cómo se calcula el score

```
score = puntos obtenidos / peso de los criterios evaluables × 100
```

Solo CUMPLE otorga puntos, y otorga el peso completo del criterio. No hay cumplimiento parcial en esta pauta.

Descalificación: solo **PECUF.1 (falta de respeto)** puede descalificar la llamada. Ningún otro criterio lo hace. La cobertura de operaciones del cliente es informativa, no descalificante, por decisión de negocio.

---

## 5. De qué depende la confiabilidad

### Separación de interlocutores
Toda la evaluación afirma cosas sobre lo que hizo **el asesor**. Si no se puede confiar en quién dijo cada frase, esas afirmaciones no se sostienen.

El módulo verifica que ambos roles estén presentes, que al menos el 70% de los segmentos tengan rol asignado y que el rol minoritario tenga al menos 15% de participación. Si no se cumple, **todos los criterios pasan a REQUIERE_REVISION** en vez de producir un resultado.

Esto pasa de verdad: en una muestra de audios productivos hay casos donde la transcripción atribuyó casi todo a un solo interlocutor.

### Timbrado previo a la conexión
Cuando la grabación incluye el timbrado, ese tramo puede consumir uno de los dos cupos de hablante del transcriptor y dejar toda la conversación en el cupo restante. El módulo detecta el tono de timbrado y lo descarta antes de transcribir, corrigiendo los tiempos para que la evidencia siga apuntando al minuto real del audio.

Medido sobre 15 llamadas reales: 3 traían timbrado (14,1 s / 15,4 s / 5,1 s). No se recorta nada cuando no hay evidencia de tono.

**Limitación:** los audios en formato GSM 6.10 no pasan por este preproceso. En la muestra fueron 2 de 15.

### Evidencia
Un criterio marcado NO_CUMPLE que requiere evidencia y no la tiene no se castiga: pasa a REQUIERE_REVISION. Cuando la conclusión es por ausencia de una conducta, se declara como tal (`AUSENCIA_EN_SECUENCIA`) en vez de citar una frase cualquiera de relleno, y la confianza no puede quedar en ALTA.

---

## 6. Problemas abiertos

### 6.1 REQUIERE_REVISION penaliza el score — decisión pendiente
Un criterio en REQUIERE_REVISION aporta 0 puntos pero **mantiene su peso en el denominador**. Consecuencia: una llamada donde la separación de interlocutores falla manda los 15 criterios a REQUIERE_REVISION y produce **score 0**, que se guarda como nota de la llamada.

Un 0 que en realidad significa "no pudimos atribuir quién habló" es un número falso presentado como resultado.

Opciones:
- **(a)** Excluir REQUIERE_REVISION del denominador, igual que NO_EVALUABLE, y mostrar en la ficha cuánto peso está pendiente de juicio humano.
- **(b)** No publicar score cuando el peso en revisión supera un umbral, y dejar la llamada en estado pendiente.

Cambia la definición del indicador, así que es decisión de negocio, no técnica.

### 6.2 El indicador de error crítico no discrimina
Se marca error crítico si **algún** criterio queda NO_CUMPLE dentro de un grupo crítico. Como 11 de los 15 criterios están clasificados como críticos, casi cualquier llamada con un incumplimiento queda marcada. Por eso el tablero muestra 100%.

Está correctamente programado; el problema es la definición. Necesita severidad o restringirse a conducta descalificante.

### 6.3 PECN.4 está en el bloque equivocado
"Cierre de negociación" tiene código PECN.4 pero está cargado en el bloque PECC. Los pesos cierran en 100 gracias a eso, así que moverlo obliga a rebalancear. Mientras tanto, el reporte de precisión por bloque lo atribuye a Cumplimiento en vez de Negociación.

### 6.4 El mecanismo de bloque anulante está inactivo
Los 15 criterios de la pauta son PUNTUABLE. Ninguno es ANULANTE_BLOQUE, así que la anulación por bloque nunca se dispara. No es un error, pero conviene saber que hoy la única descalificación posible viene de PECUF.1.

---

## 7. Cómo se mide si la IA acierta

Cada evaluación se congela criterio por criterio en `CRM_IA_EVALUACION_CRITERIO`. Esa fila no se modifica nunca: si Calidad corrige, la corrección va a una tabla aparte.

Se considera **coincidencia** cuando Calidad confirma el mismo resultado **y** valida la evidencia citada como suficiente. Un acierto con evidencia inventada no cuenta como acierto.

Solo entran al cálculo los criterios donde hubo un acto humano explícito — confirmar también cuenta. Lo que nadie revisó no suma ni a favor ni en contra. La precisión se reporta con la muestra a la vista, y por debajo de 30 actos se marca como muestra insuficiente.

---

## 8. Qué se puede afirmar y qué no

**Se puede afirmar:**
- "El score se calcula solo sobre los criterios que la IA pudo observar en esta llamada."
- "Los criterios que no se pueden verificar están declarados, no aprobados."
- "Cuando no se puede confiar en quién habló, la llamada no recibe un resultado automático."
- "La evaluación original queda congelada y es auditable contra la corrección humana."

**No se puede afirmar todavía:**
- Que el score sea comparable entre llamadas con distinta cantidad de criterios evaluables, sin mostrar el peso evaluado.
- Que la IA acierte en un porcentaje determinado: no hay muestra calibrada suficiente.
- Que la información de deuda que comunicó el asesor sea correcta: se mide que la haya declarado, no que la cifra cuadre.
- Que un score bajo signifique mala gestión, mientras 6.1 siga abierto.
