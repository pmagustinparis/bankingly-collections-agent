# Especificación de datos simulados — Agente de cobranza temprana

> Insumo de construcción para Claude Code (Paso 1 del build). Define la forma exacta de los datos sintéticos y los casos difíciles a curar. Estas decisiones son de producto y están tomadas: implementarlas, no re-decidirlas. Ante un detalle no cubierto, elegir lo más simple y realista, registrar ADR breve, y seguir.

---

## 1. Propósito de los datos

Simular una cartera de clientes en **mora temprana** (atraso reciente) para que el agente analice cada caso y proponga una acción de cobranza. Los datos son la materia prima sobre la que el agente razona: deben ser realistas y contener casos de dificultad variada, incluyendo casos donde el agente pueda fallar.

**Principio rector:** el agente razona sobre **datos crudos**, no sobre etiquetas pre-calculadas. No se le entrega el "perfil de riesgo" ni el "tipo de pagador" masticado; eso lo debe inferir del historial y el contexto. Darle la conclusión servida invalidaría lo que se quiere demostrar.

---

## 2. Alcance y marco (verificado con research de industria)

- **Mora temprana = 1 a 30 días de atraso.** Es el corte más estándar de la industria (mora temprana 0-30, media 31-90, tardía +90). Todos los clientes del dataset caen en este rango.
- **Nota de producto (documentar como ADR):** los cortes varían entre instituciones (algunas usan 14-60 días para "temprana"). Se adopta 1-30 por ser el más común, y el sistema se diseña para que el rango sea **configurable** — esto sostiene la escalabilidad a decenas de instituciones.
- **La segmentación es la práctica central de la cobranza moderna.** El error clásico del negocio es tratar a todos los deudores igual. El agente existe para segmentar por contexto individual (días de atraso, monto, historial, tipo de producto) y proponer la acción adecuada a cada perfil.
- **Principio de tono (para la lógica del agente):** la firmeza sube a medida que avanza la mora, pero el respeto no baja nunca. Aplica a cómo el agente calibra la acción propuesta.

---

## 3. Volumen y composición

- **Total: 50 clientes.**
- **10 casos curados a mano (20%)** — los casos difíciles, 2 por cada uno de los 5 arquetipos (ver sección 6).
- **40 casos generados** con variedad realista dentro de los rangos definidos.
- Fundamento de producto (para el PRD/sesión): se prioriza **diseño de dificultad sobre volumen**. Un set chico y curado demuestra más criterio que uno grande y aleatorio. Los casos curados son los que permiten el análisis de errores honesto.

---

## 4. Esquema del cliente (campos)

Cada cliente es un registro con estos campos. Nombres de dominio en español (convención del proyecto).

| Campo | Tipo | Descripción | Rango / valores |
|---|---|---|---|
| `cliente_id` | string | Identificador único | ej. "CLI-001" |
| `nombre` | string | Nombre ficticio (para legibilidad de la demo) | nombres LATAM genéricos |
| `tipo_de_producto` | enum | Producto en mora | `prestamo_personal`, `tarjeta_de_credito` |
| `dias_de_atraso` | int | Días desde el vencimiento impago | 1 a 30 |
| `monto_adeudado` | number | Total adeudado (ARS/genérico LATAM) | ver sección 5 |
| `cuota_vencida` | number | Valor de la cuota impaga puntual | ver sección 5 |
| `antiguedad_meses` | int | Hace cuánto es cliente | 1 a 120 |
| `canal_preferido` | enum | Canal de contacto preferido | `email`, `sms`, `whatsapp`, `telefono` |
| `historial_de_pagos` | array | Últimos 12 meses, mes a mes (ver 4.1) | lista de 12 estados |

### 4.1 Estructura de `historial_de_pagos`

Lista de **12 elementos** (los últimos 12 meses, del más antiguo al más reciente). Cada elemento es uno de tres estados:

- `a_tiempo` — pagó dentro del plazo.
- `tardio` — pagó pero con atraso.
- `no_pago` — no pagó ese mes.

Ejemplo: `["a_tiempo","a_tiempo","a_tiempo","tardio","a_tiempo","a_tiempo","a_tiempo","a_tiempo","a_tiempo","a_tiempo","a_tiempo","tardio"]`

Este historial es la señal más rica del dataset: es lo que permite al agente distinguir un buen pagador que se olvidó de un moroso recurrente. **No resumir en un score; el agente debe leer el patrón.**

> Para clientes con `antiguedad_meses` < 12, el historial tiene solo tantos meses como antigüedad (un cliente nuevo tiene historia corta). Esto es deliberado: alimenta el arquetipo "cliente nuevo".

---

## 5. Rangos de montos (realismo LATAM)

Moneda genérica LATAM (pensada como ARS, pero sin símbolo forzado). Coherencia interna importa más que el valor absoluto.

- **Tarjeta de crédito:** cuotas/saldos más chicos y frecuentes. `cuota_vencida` ~ 15.000 a 150.000. `monto_adeudado` puede ser 1 a 3 veces la cuota (saldo acumulado).
- **Préstamo personal:** cuotas más grandes. `cuota_vencida` ~ 50.000 a 400.000. `monto_adeudado` normalmente ≈ cuota vencida (1 cuota) o hasta 2 cuotas.
- Los **casos de monto atípico** (arquetipo 4) rompen estos rangos a propósito (muy alto o muy bajo).

---

## 6. Los 10 casos curados (2 por arquetipo)

Cada arquetipo está diseñado para provocar un tipo específico de error o dificultad. Estos casos son la base de las categorías de evaluación. Curar 2 de cada uno, variando detalles (producto, monto, canal) para que no sean clones.

### Arquetipo A — Buen pagador que se olvidó
- **Perfil:** historial impecable o casi (0-1 `tardio` en 12 meses), atraso corto (1-7 días), monto normal, antigüedad media-alta.
- **Acción correcta esperada:** `recordatorio` suave.
- **Error a detectar:** que el agente sea agresivo (proponga `escalar` o trato duro) con un cliente que claramente solo se olvidó. Testea que el agente **no daña la relación con buenos clientes**.

### Arquetipo B — Moroso recurrente
- **Perfil:** historial con atrasos repetidos (varios `tardio`/`no_pago` dispersos), atraso actual en la franja alta (15-30 días), antigüedad variable.
- **Acción correcta esperada:** `escalar` o `plan_de_pago` con control.
- **Error a detectar:** que el agente sea blando (proponga solo `recordatorio`) con alguien que ya mostró un patrón de incumplimiento. Testea que el agente **reconoce patrones de riesgo**.

### Arquetipo C — Ambiguo genuino (el más valioso)
- **Perfil:** historial largo y bueno (2+ años impecables) con un **cambio reciente de patrón** (ej. 2 atrasos en los últimos 3 meses). ¿Problema temporal o inicio de deterioro? No hay respuesta única correcta.
- **Acción correcta esperada:** no hay una sola; tanto `recordatorio` cuidadoso como `plan_de_pago` preventivo son defendibles.
- **Valor:** este caso **justifica la existencia del gate de aprobación humana**. Para el análisis de errores, permite mostrar madurez: el agente propone algo defendible, pero un humano razonable podría elegir otra cosa — por eso el control humano es necesario, no opcional.

### Arquetipo D — Monto atípico
- **Perfil:** un `monto_adeudado` muy por fuera del rango típico (muy alto o muy bajo) respecto del resto de su perfil.
- **Acción correcta esperada:** la gestión debe ajustarse al tamaño del riesgo (un monto muy alto amerita más cuidado/escalamiento aunque el historial sea ok; uno trivial no amerita fricción).
- **Error a detectar:** que el agente ignore la magnitud y aplique la acción "de manual" sin ajustar por monto.

### Arquetipo E — Cliente nuevo
- **Perfil:** `antiguedad_meses` baja (1-5), historial corto (pocos meses), poca información para decidir.
- **Acción correcta esperada:** una gestión prudente que reconoce la incertidumbre por falta de historia.
- **Error a detectar:** que el agente sobre-reaccione (trato duro sin evidencia) o que finja certeza que los datos no respaldan. Testea el comportamiento con **información insuficiente**.

---

## 7. Formato de salida

- Archivo principal: `data/clientes.json` — array con los 50 clientes.
- Los 10 casos curados se marcan con un campo extra `arquetipo` (ej. `"arquetipo": "ambiguo_genuino"`) para poder cruzarlos con los evals. Los 40 generados llevan `"arquetipo": null` o `"normal"`.
- Alternativa aceptable: un `data/casos_dificiles.json` separado, si resulta más limpio. Decidir al construir y registrar como ADR.
- El campo `arquetipo` es metadata de evaluación: **no se le pasa al agente en el prompt** (sería darle la respuesta). Solo lo usa el sistema de evals para categorizar.

---

## 8. Reglas de generación (para los 40 casos normales)

- Distribuir con variedad en los dos `tipo_de_producto` (aprox. mitad y mitad).
- `dias_de_atraso` distribuidos en todo el rango 1-30, no amontonados.
- Historiales variados: mayoría buenos pagadores (realista: la mayoría de la mora temprana es gente que se atrasó puntualmente), algunos con atrasos ocasionales, pocos con patrón feo.
- Nombres, canales y montos variados y coherentes con el tipo de producto.
- Ningún caso normal debe caer accidentalmente en un arquetipo extremo sin estar marcado — mantener los casos normales genuinamente "de rango medio".

---

*Fin de la especificación de datos. Recordá: el agente razona sobre datos crudos; el `arquetipo` es solo para evals y nunca se le muestra al modelo.*
