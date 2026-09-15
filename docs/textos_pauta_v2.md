# Textos para la pauta v2 — copiar y pegar

Solo se tocan **dos criterios**. Todo lo demás queda igual: no cambies pesos,
códigos, bloques ni criticidades. Los pesos deben seguir sumando 100 o el botón
Publicar no se habilita.

---

## Criterio 1 de 2 — PECUF.3

Búscalo en el bloque **PECUF** (Precisión de Error Crítico Usuario Final).

### Campo: Nombre

```
Declaración escalonada de montos
```

### Campo: Fuente evidencia

Cambiar de `MULTIFUENTE` a:

```
TRANSCRIPCION
```

### Campo: Cuándo cumple

```
Cumple cuando declara la deuda total con su importe y el cliente no la rechaza; o cuando, ante rechazo explícito, ofrece el capital con su importe; o cuando, ante un segundo rechazo, ofrece el monto de campaña.
```

### Campo: Cuándo no cumple

```
No cumple cuando omite declarar la deuda total, cuando ante un rechazo explícito no ofrece el siguiente nivel, o cuando salta un nivel de la escalera (por ejemplo, pasa de la deuda total a la campaña sin ofrecer el capital).
```

### Campo: Aplicabilidad / No aplica

```
Aplica en toda conversación con el titular. Solo es NO_APLICA ante tercero confirmado o corte que impida negociar. Evadir o cambiar de tema no equivale a rechazo: sin negativa o imposibilidad explícita del cliente, no se exige bajar de nivel.
```

### Dentro de "Más reglas y recomendaciones"

Ese bloque viene **plegado**. Hay que abrirlo para ver estos tres campos.

#### Campo: Detalle

```
Declara los montos de la deuda y escala solo ante rechazo
```

#### Campo: Regla de evaluación

```
El asesor debe declarar el monto de la deuda total. Si el cliente rechaza de forma explícita, debe ofrecer el capital con su monto y, ante un nuevo rechazo, el monto de campaña. El orden es estricto. No se verifica que la cifra sea correcta: se evalúa que el monto haya sido comunicado.
```

#### Campo: Recomendación sugerida

```
Decir el importe de la deuda total apenas se valida al titular y bajar de nivel solo cuando el cliente se niega o declara no poder.
```

### Lo que NO se toca en PECUF.3

- Peso: sigue en **5**
- Código: sigue siendo **PECUF.3**
- Criticidad: sigue **ERROR_CRITICO_USUARIO_FINAL**
- Evidencia obligatoria: sigue **marcada**
- Puede descalificar: sigue **desmarcada**

---

## Criterio 2 de 2 — PECN.2

Búscalo en el bloque **PECN**. Se acota para que no mida lo mismo que PECUF.3.

### Campo: Cuándo cumple

```
Cumple cuando propone o ajusta la forma de pago según el diagnóstico -cuotas, plazos, fechas o canal- buscando una opción concreta y viable.
```

### Campo: Cuándo no cumple

```
No cumple cuando existe oportunidad de negociar y el agente no desarrolla ninguna alternativa de forma de pago, o la propuesta ignora la situación que el cliente planteó.
```

### Campo: Aplicabilidad / No aplica

```
Aplica en toda conversación con el titular. Solo puede ser NO_APLICA ante tercero confirmado o corte abrupto que impida responder; una propuesta sola no equivale a compromiso. No se evalúa aquí la declaración de montos.
```

### Dentro de "Más reglas y recomendaciones"

#### Campo: Regla de evaluación

```
Construye una propuesta de pago acorde con lo que el cliente expuso: forma de pago, fraccionamiento, fechas, canal y viabilidad. La escalera de montos (deuda total, capital, campaña) NO se evalúa aquí: corresponde a PECUF.3.
```

### Lo que NO se toca en PECN.2

Nombre, peso (10), código, criticidad y los checkboxes quedan igual.

---

## Antes de publicar

En el pie del editor debe decir:

```
Peso puntuable: 100.00 / 100
```

Si no dice 100, algo se movió sin querer: revisa los pesos antes de publicar.

---

## Descripción de la versión

En "Datos generales", campo Descripción:

```
Pauta general de evaluacion. v2: PECUF.3 mide la declaracion escalonada de montos (deuda total, capital, campania) en lugar de contrastar contra una base de deudas.
```
