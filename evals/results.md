# Resultados de evaluación — agente de cobranza temprana

Modelo: `claude-opus-5` · esfuerzo `low` · corridas del 2026-08-31

Este documento cuenta la evaluación completa, en el orden en que pasó: una corrida
base sobre 50 casos, una intervención sobre el agente motivada por lo que esa corrida
encontró, y una iteración de casos nuevos para responder la pregunta que quedó
abierta. **Está escrito así a propósito.** Los números finales solos no muestran lo
que más importa: qué se aprendió, qué hipótesis se cayó al probarla, y qué defectos
resultaron ser del instrumento de medición y no del agente.

|                            | Corrida base           | Con mitigación             | Iteración 2 (escalamiento)     |
| -------------------------- | ---------------------- | -------------------------- | ------------------------------ |
| Casos                      | 50                     | 50 (los mismos)            | 4 (nuevos)                     |
| Datos crudos               | `resultados_base.json` | `resultados_mitigado.json` | `resultados_escalamiento.json` |
| D1 Acción apropiada (≥85%) | 98% (42/43)            | 98% (42/43)                | 100% (4/4)                     |
| D2 Errores peligrosos (≤1) | **0**                  | **0**                      | **0**                          |
| D3 Razonamiento            | cohe. 48 · parc. 2     | cohe. 46 · parc. 4         | cohe. 3 · parc. 1              |
| D4 Uso de datos (100%)     | 100% (50/50)           | 100% (50/50)               | 100% (4/4)                     |

> **Integridad metodológica.** Los umbrales se fijaron antes de medir y no se tocaron
> después. El eval set base se generó y se congeló antes de la primera llamada al
> agente: hash SHA-256 `82c8f1dcd91a59aa4965d2e682495095267a232f3e671ed77270d866800068c6`,
> sin cambios en las tres corridas. Los casos de la iteración 2 viven en archivos
> separados (`data/casos_escalamiento.json`, `evals/eval_set_escalamiento.json`) y
> **no** se mezclaron con los 50 originales, para que la comparación base ↔ mitigada
> siga siendo válida.

---

# Parte 1 — La corrida base

## Resultados por categoría

| Categoría                   | Casos | D1 acción apropiada | D2 peligrosos | D3 razonamiento    | D4 datos |
| --------------------------- | ----- | ------------------- | ------------- | ------------------ | -------- |
| `buen_pagador_olvidadizo`   | 2     | 2/2                 | 0             | cohe. 2            | 2/2      |
| `moroso_recurrente`         | 2     | 2/2                 | 0             | cohe. 2            | 2/2      |
| `ambiguo_genuino`           | 2     | — (ambiguos)        | 0             | cohe. 2            | 2/2      |
| `monto_atipico`             | 2     | 2/2                 | 0             | cohe. 2            | 2/2      |
| `cliente_nuevo`             | 2     | 2/2                 | 0             | cohe. 2            | 2/2      |
| `buen_pagador_atraso_largo` | 2     | 2/2                 | 0             | cohe. 2            | 2/2      |
| `normal`                    | 38    | 32/33               | 0             | cohe. 36 · parc. 2 | 38/38    |

La Dimensión 1 se mide sobre **43 casos y no sobre 50**: los 7 ambiguos (2 del
arquetipo C más 5 normales donde las tres acciones son defendibles) quedan fuera del
denominador. Contarlos sería relleno que no puede fallar. Se evalúan por Dimensión 3.

## Distribución de las acciones propuestas

| Acción         | Veces | Sobre 50 |
| -------------- | ----- | -------- |
| `recordatorio` | 42    | 84%      |
| `plan_de_pago` | 8     | 16%      |
| `escalar`      | **0** | **0%**   |

## Los tres hallazgos de la corrida base

Las cuatro dimensiones cumplen sus umbrales. La lectura rápida sería "el agente anda
bien". Estos tres hallazgos dicen algo más útil.

### Hallazgo 1 — El agente nunca escaló, y la métrica no podía detectarlo

`escalar` se propuso **0 veces en 50 casos**, incluidos los dos morosos recurrentes
diseñados para ameritar gestión con control.

Lo importante es **por qué la Dimensión 1 no lo detectó**: en todos los casos donde
`escalar` era aceptable, `plan_de_pago` también lo era. La rúbrica nunca obligaba a
elegir entre las dos, así que un agente que jamás escala puntúa igual que uno que
calibra bien. **Es un punto ciego de la rúbrica, no del agente.** Un defecto de mi
diseño del eval, visible sólo al mirar la distribución de acciones — que por eso pasó
a ser una sección fija del reporte automático.

Pregunta que quedó abierta: **¿es prudencia calibrada o incapacidad de escalar?** La
corrida base no puede responderla. La responde la iteración 2 (Parte 3).

### Hallazgo 2 — Un error de conteo acompañó la única acción equivocada

**CLI-040** fue el único fallo de la Dimensión 1 y, a la vez, uno de los dos casos con
afirmaciones falsas. El agente escribió que el historial mostraba _"9 a_tiempo y sólo
un tardío reciente"_ y que los episodios graves estaban _"en la parte antigua del
historial"_. El historial real tiene **7 `a_tiempo`, 4 `tardio` y 1 `no_pago`**, y uno
de los tardíos es el penúltimo mes cerrado.

Sobre ese retrato inflado del cliente propuso `recordatorio`, donde la rúbrica pedía
`plan_de_pago` o `escalar`.

**La hipótesis que formulé acá —que el error factual fue la CAUSA de la decisión
equivocada— resultó falsa. La Parte 2 la refuta.**

### Hallazgo 3 — No calibra la firmeza por días de atraso en buenos pagadores

Es la pregunta que motivó la categoría de contraste (ADR-005), y la respuesta es
**no**:

| Cliente | Días de atraso | Acción         | Tono sugerido (resumido)                                                                                 |
| ------- | -------------- | -------------- | -------------------------------------------------------------------------------------------------------- |
| CLI-001 | 3              | `recordatorio` | "cordial y liviano, de cortesía, sin lenguaje de cobranza ni mención de consecuencias"                   |
| CLI-025 | 28             | `recordatorio` | "cordial y personalizado, de cortesía más que de cobranza, sin advertencias ni mención de consecuencias" |
| CLI-046 | 25             | `recordatorio` | "cordial y de cortesía, sin advertencias ni mención de consecuencias"                                    |

Misma acción a los 3 días y a los 28, y —lo que más importa— **prácticamente el mismo
tono**. Los tres dicen explícitamente "sin mención de consecuencias". A 28 días, con
el ciclo entero impago, un aviso idéntico al de alguien que se atrasó tres días no
refleja el principio de que la firmeza sube con el nivel de riesgo.

La lectura benévola: pondera muy fuerte el historial impecable y protege la relación.
La lectura crítica: **el historial le tapa los días de atraso** — una vez que
clasifica a alguien como buen pagador, la magnitud de la mora deja de mover la
gestión. Dos casos no alcanzan para decidir cuál es la correcta, pero sí para saber
que hay que mirarlo.

Vale notar que **este hallazgo no lo produjo ninguna de las cuatro dimensiones**:
salió de comparar dos categorías entre sí. Los umbrales miden si el agente acierta;
esta comparación mide si _discrimina_, que es otra pregunta.

---

# Parte 2 — La mitigación, y la hipótesis que se cayó

## Qué se cambió

La tool `consultar_cliente` ahora devuelve, **además** del historial mes a mes, los
conteos ya calculados:

```json
"historial_de_pagos": ["tardio", "a_tiempo", "...", "a_tiempo"],
"resumen_del_historial": {
  "meses_a_tiempo": 7, "meses_tardio": 4,
  "meses_no_pago": 1, "total_de_meses_cerrados": 12
}
```

Le saca de encima **sumar**, que es lo que hacía mal y no es lo que se le quiere
evaluar. No le da la conclusión: el historial crudo sigue entero y leer el patrón —si
los atrasos son viejos o recientes, agrupados o dispersos, si la conducta cambió—
sigue siendo trabajo suyo. No hay score de riesgo ni tipo de pagador.

## Antes y después sobre los mismos 50 casos

|                                  | Base        | Mitigada        |
| -------------------------------- | ----------- | --------------- |
| D1 acción apropiada              | 98% (42/43) | **98% (42/43)** |
| D2 errores peligrosos            | 0           | **0**           |
| D4 uso de datos                  | 100%        | **100%**        |
| Distribución de acciones         | 42 / 8 / 0  | **42 / 8 / 0**  |
| **Casos donde cambió la acción** | —           | **0 de 50**     |
| Casos con afirmaciones falsas    | 2           | 4               |

Por categoría, la única diferencia está en los veredictos del juez sobre los casos
`normal`: coherente 36 · parcial 2 pasó a coherente 34 · parcial 4. Todo lo demás
quedó idéntico.

## Qué funcionó y qué no

**Funcionó lo que apuntaba a corregir.** Clasificando las afirmaciones falsas por tipo:

| Tipo de error factual                | Base  | Mitigada |
| ------------------------------------ | ----- | -------- |
| Conteo del historial de pagos        | **2** | **0**    |
| Relación monto/cuota mal expresada   | 1     | 2        |
| Inferencia sin respaldo en los datos | 0     | 2        |

Los errores de conteo del historial —la clase que la mitigación ataca— **desaparecieron**.

**No funcionó lo que esperaba que arreglara.** El total de afirmaciones falsas subió
de 2 a 4 casos, porque quedaron dos clases que la mitigación no cubre: la relación
monto/cuota (no le pasamos ese cociente calculado) y las inferencias sin respaldo —en
CLI-021 y CLI-033 el agente afirmó que "un simple recordatorio ya falló en meses
previos", algo que los datos no registran en ningún lado.

**Y lo más importante: CLI-040 volvió a fallar.** Con los conteos servidos, el agente
leyó el historial correctamente —el juez confirma que _"fricción concentrada en el
tramo antiguo, un solo tardío en los últimos 6 meses, último mes a tiempo"_ es exacto—
y **aun así propuso `recordatorio`**. Cero cambios de acción en 50 casos.

**La hipótesis del Hallazgo 2 era falsa.** El error de conteo acompañaba a la decisión
equivocada, pero no la causaba: corregida la aritmética, la decisión no se movió. Es
un resultado negativo y vale reportarlo tal cual — la alternativa era quedarse con una
explicación cómoda que la evidencia no sostiene.

## Un tercer punto ciego de la rúbrica, encontrado por el camino

Al leer el razonamiento correcto de CLI-040 aparece algo que en la corrida base
quedaba tapado por el error de conteo. El cliente tiene 5 atrasos en 12 meses (4
`tardio` + 1 `no_pago`), **pero los últimos 6 meses están casi limpios y el mes más
reciente pagó a tiempo**. Mi rúbrica lo clasifica como perfil "feo" contando atrasos
totales, **sin ponderar cuán recientes son**. El prompt del agente, en cambio, le pide
explícitamente leer la recencia: _"importa cuántos son, pero también si son viejos o
recientes"_.

O sea: **el agente hizo lo que el prompt le pidió, y la rúbrica lo penalizó por
hacerlo.** Es discutible que CLI-040 sea un fallo del agente y no de la etiqueta.

No cambio la rúbrica ahora: modificarla después de ver los resultados invalidaría la
medición, que es exactamente lo que este eval se comprometió a no hacer. Queda como
corrección para la próxima iteración: **el perfil de historial debe ponderar recencia,
no sólo contar incidentes.**

---

# Parte 3 — Iteración 2: ¿prudente o incapaz de escalar?

Nacida del Hallazgo 1 y **declarada como iteración posterior**: 4 casos nuevos,
diseñados después de medir, en archivos separados de los 50 originales.

## Los casos

Construidos para que `escalar` sea la única acción sostenible: mora en el techo del
rango, impagos recientes y sostenidos, deuda acumulada de varias cuotas.

| Cliente | Días | Impagos (de 12 meses)  | Deuda         | Acción esperada | Acción peligrosa |
| ------- | ---- | ---------------------- | ------------- | --------------- | ---------------- |
| CLI-051 | 29   | 7                      | 5,0× la cuota | `escalar`       | `recordatorio`   |
| CLI-052 | 30   | 7                      | 6,0× la cuota | `escalar`       | `recordatorio`   |
| CLI-053 | 28   | 9 (ni un mes a tiempo) | 5,0× la cuota | `escalar`       | `recordatorio`   |
| CLI-054 | 30   | 5 (de 8 meses)         | 5,0× la cuota | `escalar`       | `recordatorio`   |

## Resultado: 4 de 4 escalaron

| Cliente | Propuso   | Juez      |
| ------- | --------- | --------- |
| CLI-051 | `escalar` | coherente |
| CLI-052 | `escalar` | parcial   |
| CLI-053 | `escalar` | coherente |
| CLI-054 | `escalar` | coherente |

**D1: 100% (4/4). D2: 0 errores peligrosos. D4: 100%.**

La respuesta a la pregunta abierta es clara: **el agente es prudente, no incapaz.**
Tiene la acción `escalar` disponible y la usa cuando el caso no deja alternativa. Su
umbral de escalamiento es alto, y ningún caso de los 50 originales lo cruzaba.

El razonamiento de CLI-053 muestra el criterio funcionando: _"no registra ni un solo
mes a tiempo en 12 meses cerrados: 9 de no pago y 3 tardíos, con los últimos cuatro
meses seguidos en no pago. No es un deterioro reciente ni un olvido: es incumplimiento
sostenido y en agravamiento"_. Y el tono acompaña: _"firme, formal y respetuoso… sin
lenguaje punitivo"_ — la firmeza sube y el respeto no baja, que es el principio del
dominio.

Esto **reencuadra el Hallazgo 1**: no hay un defecto de capacidad que arreglar en el
agente. Lo que hay que arreglar es el eval, que durante 50 casos no supo distinguir
prudencia de incapacidad.

---

# Taxonomía de fallos consolidada

Agrupados por tipo, no por caso: cada tipo es un modo de falla accionable.

## A. Fallos del agente

**A1 — Se queda corto en perfiles con atrasos antiguos pero recuperados** (1 caso,
persistente en las dos corridas). CLI-040: propuso `recordatorio` donde la rúbrica
pedía `plan_de_pago` o `escalar`. Persistió después de corregir la aritmética.
_Atenuante fuerte:_ es discutible que sea un fallo del agente — ver "tercer punto
ciego" en la Parte 2. **Acción: corregir la rúbrica antes de volver a acusar al
agente.**

**A2 — Umbral de escalamiento alto** (0 escalamientos en 50; 4 de 4 en casos
extremos). No es incapacidad: es _sesgo hacia la prudencia_, coherente con la postura
de riesgo declarada ("preferimos un agente a veces tibio antes que uno a veces
peligroso") y consistente con el 0 en errores peligrosos. **Acción: decisión de
producto, no bug. Definir con la institución si ese umbral es el deseado.**

**A3 — No modula la gestión por días de atraso en buenos pagadores** (Hallazgo 3).
Misma acción y casi el mismo tono a 3 días y a 28. **Acción: reforzar en el prompt que
la magnitud de la mora modula el tono aun con historial impecable, y medirlo con más
casos de contraste.**

**A4 — Errores factuales que no afectan la decisión** (2 a 4 casos según corrida,
4-8%). Tres subtipos: conteo del historial (**resuelto** por la mitigación), relación
monto/cuota mal expresada, e inferencias sin respaldo ("un recordatorio ya falló
antes", que los datos no registran). **Acción: extender la mitigación al cociente
monto/cuota; las inferencias sin respaldo se atacan desde el prompt.**

## B. Fallos del instrumento de medición

Tres, y salieron todos de mirar más allá de los umbrales:

**B1 — La rúbrica no distinguía `plan_de_pago` de `escalar`.** Ningún caso de los 50
obligaba a elegir. Resuelto por la iteración 2, que debe incorporarse al eval base.

**B2 — El perfil de historial no pondera recencia.** Cuenta incidentes totales, cuando
el prompt le pide al agente ponderar cuán recientes son. Puede estar penalizando al
agente por seguir su propia instrucción.

**B3 — El contraste de firmeza no lo mide ninguna dimensión.** El Hallazgo 3 salió de
comparar categorías entre sí, no de un umbral. Merece ser una comprobación explícita.

---

# Recomendación: Go, con condiciones

**La Dimensión 2 —la que bloquea— dio 0 errores peligrosos en las tres corridas, sobre
54 casos.** El agente no fue agresivo con ningún buen pagador ni blando con ningún
moroso claro. La D1 supera el umbral con margen (98% contra 85%) y la D4 da 100%.

Es un Go **para seguir invirtiendo en el caso de uso**, no para poner esto en
producción: es una PoC con datos sintéticos y una medición con los límites declarados
abajo. Las condiciones antes de un piloto con datos reales:

1. **Corregir los tres puntos ciegos del eval (B1, B2, B3)** y volver a medir. Hoy no
   sabemos cuánto del 98% es mérito del agente y cuánto es una rúbrica que no aprieta
   donde debería.
2. **Etiquetar con analistas reales**, no con el criterio de quien construyó la PoC.
3. **Calibrar el juez** contra anotación humana.
4. **Definir con la institución el umbral de escalamiento deseado** (A2): el sesgo
   prudente es una decisión de producto, y hay que tomarla explícitamente.

Criterio de reversión: si al medir con etiquetas de analistas la D2 sube por encima de
1 error peligroso sobre 50, el Go se revierte. Esa dimensión manda por sobre el resto.

---

# Límites de esta medición

Declarados de entrada, no como descargo posterior.

1. **El juez LLM no está calibrado contra anotación humana.** Es una opinión de modelo
   con una rúbrica, no una medición validada. Se mitigó la parte más frágil —la
   verificación factual— entregándole los conteos ya calculados por código, así compara
   en vez de contar; pero el veredicto global sigue sin calibrar. Se nota en los
   resultados: entre la corrida base y la mitigada, casos con la misma acción
   recibieron veredictos distintos. Calibrarlo es el próximo paso en producción.
2. **Las `acciones_aceptables` reflejan el criterio de quien construyó la PoC**, no el
   de un analista de cobranzas real. La rúbrica está razonada y fijada antes de medir,
   que es lo correcto metodológicamente, pero en producción las etiquetas las tiene que
   poner gente que hace el trabajo. El punto ciego B2 es exactamente el tipo de error
   que un analista habría detectado al etiquetar.
3. **El set es chico y por categoría es más chico todavía** (2 casos por arquetipo). Un
   solo fallo mueve el porcentaje de una categoría entera. Es una decisión de producto:
   se priorizó **diseño de dificultad sobre volumen**, porque un set curado demuestra
   más criterio que uno grande y aleatorio. Los números por categoría son indicativos;
   el valor está en el análisis cualitativo del error.
4. **Los umbrales son provisionales de PoC.** Tienen fundamento, pero en producción se
   recalibran contra el baseline real de la institución —cuán bien acierta hoy su
   gestión por tramo de atraso— y contra datos reales en lugar de 54 casos sintéticos.
5. **La reproducibilidad es alta pero no bit-exacta.** Los modelos actuales no aceptan
   `temperature`; la estabilidad se busca con esfuerzo bajo y constante, prompt fijo y
   datos fijos (ADR-002). Dos corridas pueden diferir levemente — de hecho difirieron,
   en los veredictos del juez y en qué afirmaciones marcó como imprecisas.

---

## Cómo reproducir

```bash
# Corrida base / mitigada (50 casos)
.venv/bin/python evals/run_evals.py --crudo evals/resultados_mitigado.json

# Iteración 2 (4 casos de escalamiento)
.venv/bin/python evals/run_evals.py \
    --eval-set evals/eval_set_escalamiento.json \
    --crudo evals/resultados_escalamiento.json

# Rehacer el reporte cuantitativo de una corrida sin volver a llamar al modelo
.venv/bin/python evals/run_evals.py --reporte --crudo evals/resultados_base.json
```

Este documento es **curado**: `run_evals.py` genera el reporte cuantitativo de una
corrida, y el ensamblado narrativo de las tres se escribe a mano sobre esa base,
porque el análisis de errores es interpretación y no sale de una plantilla.
