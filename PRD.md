# PRD — Agente de cobranza temprana

---

## 1. Elección del caso de uso

### El problema

Un cliente se atrasa en una cuota. En los primeros días de mora la institución todavía puede recuperar barato y sin dañar la relación, si contacta a la persona correcta con el tono correcto. Hoy la gestión es por tramos genéricos de días de atraso, sin mirar el contexto individual. Un buen pagador que se olvidó recibe el mismo trato que un deudor recurrente. Se pierde recupero y se erosionan relaciones valiosas.

El error más costoso de la cobranza no es ser firme con un moroso, sino ser agresivo con un buen cliente. El primero es gestión legítima; el segundo destruye una relación que costó años construir.

### La elección: cobranza temprana

Un agente interno analiza el contexto individual de cada cliente en mora temprana (1 a 30 días) y propone la acción de gestión más adecuada (recordatorio, plan de pago, o escalar). Un analista humano revisa y aprueba antes de que se ejecute.

Evaluamos los cinco casos sugeridos contra seis criterios (impacto de negocio, esfuerzo de build, riesgo regulatorio, demostración del control por código, escalabilidad a decenas de instituciones, riqueza para el análisis de errores).

**Por qué cobranza temprana primero:** argumento de negocio directo y cuantificable (la mora temprana bien gestionada recupera hasta el 80% de los casos; la digitalización mejora el recupero hasta 25% y reduce costos hasta 30%). Riesgo regulatorio bajo comparado con las alternativas. El control por código se demuestra con naturalidad (proponer y esperar aprobación). Escala a toda institución que preste.

### Qué se descartó

**Aprobación de crédito** (runner-up): mayor potencia de negocio, pero exige dominio de scoring y expone a terreno regulatorio denso (fair lending, derecho a explicación) que varía sustancialmente entre jurisdicciones de LATAM. Descartarlo pese a su mayor impacto es una decisión de priorización: cobranza demuestra el mismo mecanismo de control con menor superficie de riesgo y con regulación más homogénea entre países, lo que facilita escalar a decenas de instituciones en distintas jurisdicciones sin rehacer el análisis regulatorio en cada una.

**Alertas AML:** el más exigente en expertise regulatorio, con marcos normativos (GAFI, UIF local) que difieren significativamente por país. **Verificación KYC:** su valor real es multimodal (documento, biometría); con datos simulados queda empobrecido. **Monitoreo de cartera:** produce diagnóstico, no acciones ejecutables; el gate quedaría forzado.

En los cuatro casos descartados, además del esfuerzo y el riesgo, pesa un factor de escalabilidad: las regulaciones de crédito, AML y KYC son más específicas por jurisdicción, lo que complica ofrecer la solución a decenas de instituciones en distintos países sin una adaptación regulatoria caso a caso. La cobranza temprana tiene prácticas más transversales y regulación menos fragmentada entre mercados de LATAM.

---

## 2. Usuarios

**Usuario primario:** analista de cobranzas de la institución financiera. Recibe una propuesta razonada por caso y decide aprobar, rechazar o corregir.

**No es usuario de esta versión:** el cliente final del banco.

---

## 3. Alcance de esta versión

**Hace:** analiza clientes en mora temprana y propone acciones con razonamiento; retiene toda propuesta hasta aprobación humana garantizada por código; permite aprobar, rechazar o modificar; mide su desempeño con 54 casos y reporta por categoría.

**No hace (deliberadamente):** no ejecuta acciones reales (gestión simulada); no prioriza cartera (ver Roadmap, Etapa 2); no tiene login, persistencia ni integración con sistemas reales.

---

## 4. Requisitos priorizados

### Etapa 1 — Esta PoC (construido)

| # | Requisito | Estado |
|---|---|---|
| 1 | El agente propone una acción de lista cerrada (recordatorio / plan de pago / escalar) con razonamiento | ✅ Hecho |
| 2 | Ninguna acción se ejecuta sin aprobación humana, garantizado por código | ✅ Hecho |
| 3 | El analista puede aprobar, rechazar (con motivo) o modificar la acción | ✅ Hecho |
| 4 | Registro auditable de toda propuesta, decisión e intento bloqueado | ✅ Hecho |
| 5 | Medición con métrica y umbral definidos antes de medir, por categoría | ✅ Hecho |
| 6 | Casos difíciles curados para análisis de errores | ✅ Hecho |
| 7 | Interfaz mínima de aprobación para el analista | ✅ Hecho |

### Etapa 2 — Piloto (próximo paso)

| # | Requisito | Por qué en esta etapa y no antes |
|---|---|---|
| 8 | Priorización de cartera antes de la evaluación caso por caso | Identificado en la validación (OP-01); requiere datos reales para tener sentido |
| 9 | Conexión con datos reales de una institución | La PoC demuestra el mecanismo; el piloto demuestra el valor |
| 10 | Etiquetado de casos de eval por analistas reales | Condición del Go: no se puede hacer sin acceso a analistas de la institución |
| 11 | Calibración del juez de razonamiento contra anotación humana | Requiere las etiquetas del punto anterior como insumo |
| 12 | Flujo de aprobación en un solo paso para el analista | Mejora de UX (OP-02); la garantía de código ya funciona, solo cambia la experiencia |

### Etapa 3 — Multi-institución (escalar)

| # | Requisito | Por qué en esta etapa y no antes |
|---|---|---|
| 13 | Parametrización por institución (rango de mora, acciones, umbral de escalamiento) | Solo tiene sentido cuando hay más de una institución usando el producto |
| 14 | Integración real con al menos un canal de contacto | Requiere acuerdos con proveedores de canal por mercado |
| 15 | Panel de métricas de adopción y negocio para la institución | Depende de datos de uso real a escala |
| 16 | Monitoreo continuo del agente en producción | Requiere volumen de producción real para detectar regresiones |

---

## 5. Criterios de aceptación (esta versión)

- Ninguna acción se ejecuta si `aprobada != true` en el registro del sistema, verificado incluso salteando la interfaz y pegándole directo a la API.
- El agente consulta los datos del cliente antes de proponer en el 100% de los casos.
- No se proponen ni aprueban acciones fuera de la lista cerrada.
- Corre localmente con instrucciones reproducibles, sin credenciales en el código.
- Resultados de evaluación reportados por categoría con análisis de errores.

---

## 6. Visión a 12 meses

Un asistente de cobranza temprana que las instituciones clientes de Bankingly activan sobre su propia cartera, con rango de mora y catálogo de acciones parametrizable. El analista recibe una cola de trabajo ya priorizada y para cada caso una propuesta razonada que aprueba en segundos. Auditable de punta a punta, con el umbral de escalamiento calibrado junto con cada institución.

---

## 7. Roadmap

| Etapa | Foco | Entregable clave | Criterio de éxito |
|---|---|---|---|
| **1. Validación (esta PoC)** | Demostrar el mecanismo de control y que el agente decide con criterio razonable | Gate funcionando, 54 casos medidos, análisis de errores con taxonomía de fallos | 0 errores peligrosos; acción apropiada ≥85%; análisis que revele límites con honestidad |
| **2. Priorización + piloto** | Agregar priorización de cartera (OP-01); piloto con datos reales y un analista real | Cola de trabajo priorizada + agente integrado; eval recalibrado con etiquetas de analistas | Tasa de aprobación directa >70%; recupero del segmento piloto mejora el baseline de la institución |
| **3. Multi-institución** | Escalar a las 100+ instituciones de Bankingly | Parametrización por institución; integración con canal real; panel de métricas | Adopción sostenida; costo por gestión menor al manual; monitoreo continuo sin regresiones |

**Etapa 1 completada.** Los resultados completos, incluida la taxonomía de fallos (fallos del agente y del propio instrumento de medición), están en `evals/results.md`.

La **Etapa 2** incorpora la oportunidad de priorización de cartera (OP-01) identificada usando el prototipo: el problema del analista no es solo "qué acción tomar" sino "a quién atender primero entre miles". También resuelve la fricción de UX de la aprobación en dos pasos (OP-02), integrando las dos llamadas en un solo botón sin tocar la garantía de código.

---

## 8. Métricas de éxito

### Métricas de adopción

| Métrica | Qué mide | Meta |
|---|---|---|
| Tasa de aprobación directa | % de propuestas aprobadas sin modificar | >70% en piloto |
| Tasa de modificación por tipo de acción | En qué dirección corrige el analista | Decreciente mes a mes (señal de calibración) |
| Tasa de rechazo con motivo | Frecuencia y razones de rechazo | Decreciente; si sube, investigar |
| Tiempo promedio de gestión por caso | Segundos que el analista tarda en resolver un caso con el agente vs. sin él | Reducción ≥40% vs. gestión manual |

### Métricas de negocio

| Métrica | Qué mide | Meta |
|---|---|---|
| Tasa de recuperación de mora temprana | % de casos recuperados en el segmento piloto | Mejora vs. baseline medido de la institución (meta: +15-25%) |
| Costo por gestión | Costo operativo por caso (horas-analista + costo de API) | Menor al costo de gestión manual por caso |
| Volumen de cartera gestionada | Casos gestionados por analista por día | Aumento vs. capacidad actual sin el agente |

### Métrica de seguridad (bloquea si falla)

| Métrica | Qué mide | Meta |
|---|---|---|
| Errores peligrosos en producción | Gestión agresiva con buen cliente o blanda con moroso claro | 0 — monitoreo continuo; si sube, se frena |

---

## 9. Riesgos

| Riesgo | Mitigación |
|---|---|
| El agente propone una gestión inadecuada (agresiva con buen cliente / blanda con moroso) | Métrica de errores peligrosos con tolerancia casi cero; bloquea el Go si se supera |
| Las etiquetas de "acción correcta" del eval no reflejan el criterio de analistas reales | Condición del Go: recalibrar con analistas reales antes del piloto |
| El juez de calidad de razonamiento no está calibrado | Declarado como límite; calibrar contra anotación humana antes de producción |
| Fricción de UX en la aprobación en dos pasos | Identificado en la validación (OP-02); se resuelve en Etapa 2 sin tocar la garantía |

---

## 10. Go / No-Go

**Recomendación: Go.**

En 54 casos medidos, la dimensión que bloquea (errores peligrosos) dio **0**. El agente no fue agresivo con ningún buen pagador ni blando con ningún moroso en ninguna de las tres corridas. La acción apropiada superó el umbral con margen (98% vs. 85%) y el uso de datos fue 100%. El agente demostró ser prudente por diseño: cuando se lo forzó con casos extremos de escalamiento (iteración 2), escaló correctamente en 4 de 4.

**Mejoras identificadas para resolver antes del piloto:**
1. Corregir los puntos ciegos detectados en el instrumento de evaluación (la rúbrica no distinguía entre dos acciones válidas en un tramo de casos y no ponderaba recencia de atrasos) y volver a medir.
2. Etiquetar con analistas de cobranza reales.
3. Calibrar el juez de razonamiento contra anotación humana.
4. Acordar con la institución el umbral de escalamiento deseado (el agente hoy es prudente; ese apetito de riesgo debe definirse explícitamente, no asumirse).

**Criterios de reversión:**
- Si al medir con etiquetas de analistas la tasa de errores peligrosos supera 1/50, el Go se revierte.
- Si en el piloto la tasa de aprobación directa cae por debajo del 50% sostenido, el agente no está agregando valor y se revalúa.
- Si el costo por gestión con el agente supera el costo manual, no cierra el business case.

---

## 11. Aprendizajes de la validación

Dos oportunidades que surgieron *usando el prototipo* (detalle en el README):

- **OP-01 — Priorización de cartera.** Con 50 clientes el analista elige a mano; con miles, el problema es "a quién atender primero". Va a la Etapa 2.
- **OP-02 — Fricción de la aprobación en dos pasos.** Dejada así en la PoC para demostrar el control visible. En producción: un solo botón, misma garantía por código.

---

*Detalle técnico completo en `README.md`. Resultados de evaluación y análisis de errores en `evals/results.md`.*
