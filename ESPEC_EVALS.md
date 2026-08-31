# Especificación de evals — Agente de cobranza temprana

> Insumo de construcción para Claude Code (Paso 6 del build). Define cómo se evalúa el agente: qué se mide, con qué umbrales (definidos ANTES de medir), sobre qué casos, y cómo se reporta. Estas decisiones son de producto y están tomadas. La métrica y los umbrales NO se ajustan después de ver los resultados.

---

## 1. Qué es esto y qué NO es

Un eval mide si el agente **decide bien**. No reemplaza al agente: es el instrumento que valida que el agente funciona. El agente sigue siendo el protagonista del proyecto (banca agéntica).

Este es un eval **de agente**, no de un chatbot: mide la calidad de las **decisiones y acciones** que propone el agente, no la fluidez de un texto. El agente de cobranza es de **trayectoria corta** (consulta datos → razona → propone acción → gate), por eso se evalúan output, razonamiento y uso de datos. Un agente más complejo requeriría evaluación de trayectoria completa y eficiencia de tokens; acá no aplica (mencionarlo en el PRD como evolución futura, no construirlo).

**Principio de proporción:** el eval debe ser proporcionado. El núcleo es **determinístico** (barato, reproducible). El LLM-as-judge se usa con moderación y honestidad. No sobre-construir el eval a costa del agente.

---

## 2. Las 4 dimensiones de medición

Se puntúa por **componentes separados** (no un número agregado único) y **por categoría** (arquetipo). Cada dimensión responde una pregunta distinta.

### Dimensión 1 — Acción apropiada (determinística)
**Pregunta:** ¿el agente propuso una acción dentro del conjunto aceptable para ese caso?
- Se verifica por código: la acción propuesta (`recordatorio` / `plan_de_pago` / `escalar`) se compara contra el conjunto de acciones aceptables definido para cada caso en el eval set.
- **No** se mide coincidencia exacta con una única "respuesta correcta" — se mide pertenencia al conjunto aceptable (puede haber más de una acción válida).
- **Umbral: ≥ 85%** sobre los casos NO ambiguos.
- **Se excluyen del denominador los casos del arquetipo "ambiguo genuino"** (ver Dimensión 3): ahí, por diseño, no hay una acción única correcta.
- **Fundamento del 85%** (para defender en la sesión): un agente que asiste a un analista debe acertar la amplia mayoría de los casos donde la respuesta es claramente correcta. Fallar más de ~1 de cada 7 casos claros lo haría poco confiable como asistente. No es un número de gusto: sale de la lógica de confiabilidad para asistir a un humano.

### Dimensión 2 — Ausencia de errores peligrosos (determinística) — LA QUE MANDA
**Pregunta:** ¿el agente propuso alguna acción que NUNCA debería para ese perfil?
- Errores peligrosos definidos: proponer una acción agresiva (`escalar`) con un buen pagador de atraso leve; proponer una acción blanda (`recordatorio` suave) con un moroso recurrente claro. Se verifica por código contra la marca del caso.
- **Umbral: ≤ 1 error peligroso sobre 50 (idealmente 0).**
- **Esta métrica bloquea el Go aunque la Dimensión 1 pase.** Si hay más de 1 error peligroso, la recomendación es No-Go independientemente del resto.
- **Fundamento** (para la sesión): costo asimétrico. Ser agresivo con un buen cliente daña la relación (cara de recuperar); ser blando con un moroso pierde recupero. A escala de decenas de instituciones, un error peligroso erosiona la confianza en todo el sistema agéntico. Por eso la tolerancia es casi cero. **Preferimos un agente a veces tibio antes que uno a veces peligroso** — es una postura de producto sobre apetito de riesgo.

### Dimensión 3 — Calidad del razonamiento (LLM-as-judge, sin calibrar)
**Pregunta:** ¿el razonamiento del agente es coherente, usa los datos reales del cliente (no inventa), y la acción se sigue del argumento?
- Se evalúa con un LLM-as-judge: un modelo lee el caso + el razonamiento del agente + una rúbrica, y emite un veredicto (coherente / parcial / incoherente).
- **Especialmente relevante para los casos ambiguos** (arquetipo C), que se evalúan por esta dimensión y NO por acción apropiada: en un ambiguo, tanto un recordatorio cuidadoso como un plan preventivo son defendibles — lo que importa es si el razonamiento reconoce la ambigüedad y es sólido.
- **Sin umbral numérico duro.** Evaluación cualitativa. Expectativa: en los ambiguos, el razonamiento debe ser coherente y defendible en la mayoría.
- **LÍMITE A DOCUMENTAR HONESTAMENTE** (esto suma, no resta): el LLM-as-judge NO está calibrado contra anotación humana. Un juez sin calibrar es una opinión disfrazada de medición. En una PoC de 8h no se calibra; se declara como límite conocido y como próximo paso en producción. Reconocer esto demuestra madurez, no debilidad.

### Dimensión 4 — Uso correcto de datos / tools (determinística, liviana)
**Pregunta:** ¿el agente consultó los datos del cliente (vía tools) antes de proponer una acción?
- Se verifica por código: que la trayectoria del agente incluya la consulta de datos antes de la propuesta. El agente no debe proponer "a ciegas".
- **Umbral: 100%.** Proponer sin consultar datos es un fallo de proceso inaceptable. Si no es 100%, es un bug a corregir.
- Este es el toque de "evaluación de agente" (no solo de output) que eleva el trabajo: mide un pedazo de la trayectoria, no solo el resultado final.

---

## 3. Distinción crítica: métricas de eval ≠ métricas de negocio

**No confundir.** Existen datos de industria sobre recuperación de cobranza (ej: la mora temprana recupera hasta el 80% de los casos con buena gestión; la digitalización da hasta +25% de recupero y −30% de costos). **Esos números son del BUSINESS CASE del PRD, NO son el umbral del eval.**

- Tasa de recuperación (hasta 80%) = KPI de negocio → va al business case.
- Precisión del agente (85% acción apropiada) = KPI del eval → mide si el agente decide bien.

Son cosas distintas y no tienen relación directa. Mezclarlas es un error conceptual. El agente en la PoC no "recupera plata"; propone acciones sobre datos sintéticos.

---

## 4. El eval set (estructura)

- Archivo: `evals/eval_set.json`.
- Cada caso del eval referencia un cliente (de `data/`) e incluye:
  - `caso_id`
  - `categoria` (el arquetipo: `buen_pagador_olvidadizo`, `moroso_recurrente`, `ambiguo_genuino`, `monto_atipico`, `cliente_nuevo`, `normal`)
  - `acciones_aceptables`: lista de acciones válidas para ese caso (para Dimensión 1). Para casos ambiguos, puede incluir más de una.
  - `accion_peligrosa`: la acción que NUNCA debería proponerse para ese caso, si aplica (para Dimensión 2). Puede ser null.
  - `es_ambiguo`: booleano; si true, se excluye de la Dimensión 1 y se evalúa por Dimensión 3.
- **La categoría y las acciones esperadas son metadata de evaluación: NUNCA se le pasan al agente en el prompt.** El agente decide a ciegas de la etiqueta; el eval las usa solo para puntuar.

---

## 5. El script de evaluación

- Archivo: `evals/run_evals.py`.
- Corre el agente sobre cada caso del eval set, captura la propuesta + el razonamiento + si consultó datos, y puntúa las 4 dimensiones.
- **Reproducibilidad:** temperatura del modelo fija y baja (ya definido en el stack). Los resultados deben ser estables entre corridas.
- Genera el reporte de resultados (ver sección 6).

---

## 6. El reporte de resultados

- Archivo: `evals/results.md`.
- **Reportar POR CATEGORÍA, no solo global.** Para cada arquetipo: cuántos casos, cuántos acertó (Dimensión 1), errores peligrosos (Dimensión 2), notas de razonamiento (Dimensión 3), uso de datos (Dimensión 4).
- Incluir una tabla resumen y el desglose por categoría.
- **Análisis de errores estilo "taxonomía de fallos":** no listar "falló el caso X". Agrupar los errores por TIPO (ej: "tiende a ignorar la magnitud del monto", "sobre-reacciona con clientes nuevos por falta de historial"). Cada tipo de error es un modo de falla accionable. El análisis de errores vale más que un 100% en casos fáciles.
- **Contraste contra umbrales:** para cada dimensión, indicar si se cumplió el umbral (85% / ≤1 / cualitativo / 100%) y qué implica para el Go/No-Go.

### Nota sobre el set chico
Con 50 casos y ~2 curados por arquetipo, los porcentajes por categoría son gruesos (un fallo mueve mucho el %). Declararlo honestamente: el set prioriza **diseño de dificultad sobre volumen**; los números por categoría son indicativos y el valor está en el análisis cualitativo del error. Esto es una decisión de producto defendible, no una limitación a esconder.

---

## 7. Umbrales: provisionales de PoC (declararlo)

Todos los umbrales (85% / ≤1 / 100%) son **provisionales de PoC**, con fundamento sólido pero sujetos a recalibración en producción contra:
1. El **baseline real de la institución** — cuán bien acierta hoy su gestión por tramos de días de atraso. El agente debe superar ese baseline con margen; hoy se estima el umbral por lógica de producto porque el baseline real requiere medirse con el cliente.
2. **Datos reales** en vez de 50 casos sintéticos.

Declarar esto en el PRD y en la sesión: número concreto + fundamento + honestidad sobre sus límites = criterio de PM senior.

---

## 8. Resumen de umbrales (tabla de referencia)

| Dimensión | Tipo | Umbral | Manda / Notas |
|---|---|---|---|
| 1. Acción apropiada | Determinística | ≥ 85% (casos no ambiguos) | Excluye ambiguos del denominador |
| 2. Errores peligrosos | Determinística | ≤ 1 sobre 50 (ideal 0) | **Bloquea el Go si no se cumple** |
| 3. Calidad razonamiento | LLM-as-judge sin calibrar | Cualitativo (sin número) | Límite documentado honestamente |
| 4. Uso de datos/tools | Determinística | 100% | Fallo de proceso si no |

---

*Fin de la especificación de evals. Recordar: umbrales definidos ANTES de medir y no se ajustan después; la categoría nunca se le pasa al agente; el análisis de errores por taxonomía de fallos es lo más valioso del entregable de medición.*
