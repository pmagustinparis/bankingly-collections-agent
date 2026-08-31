# CLAUDE.md — Guía de construcción del proyecto

> Este archivo es el briefing permanente para Claude Code. Leelo al inicio y respetá estas decisiones durante todo el build. **No re-decidas lo que ya está decidido acá.** Si algo es ambiguo, elegí la opción más simple y legible, dejá registrada la decisión como ADR breve en el README, y seguí.

---

## 0. Documentos de este proyecto (qué leer y cuándo)

Además de este archivo, existen tres documentos de especificación detallada. Consultá cada uno en su paso correspondiente:

- **`ESPEC_DATOS.md`** → leer antes del **Paso 1** (datos simulados). Define el esquema del cliente, los rangos, y los 10 casos difíciles a curar.
- **`ESPEC_AGENTE.md`** → leer antes de los **Pasos 2 y 3** (el gate y el agente/harness). Define el loop, el comportamiento del gate, las tools y el diseño del prompt. Es el corazón del sistema.
- **`ESPEC_EVALS.md`** → leer antes del **Paso 6** (evals). Define las 4 dimensiones de medición, los umbrales (definidos antes de medir) y cómo reportar.

También está disponible el PDF del desafío técnico original como fuente de referencia. Este `CLAUDE.md` es el índice general y las reglas; los `ESPEC_*` son el detalle de cada parte densa. Ante conflicto, prevalece lo más específico (el ESPEC correspondiente), y si persiste la duda, preguntá antes de improvisar sobre el gate o los evals.

---

## 1. Contexto del proyecto

Prototipo (PoC) de un **agente interno de cobranza temprana** para instituciones financieras de LATAM, en el marco de "banca agéntica": un agente con IA que hace trabajo bancario real, siempre con **aprobación humana** antes de ejecutar cualquier acción con efectos.

- **Usuario del agente:** un analista de cobranzas de la institución (no el cliente final).
- **Qué hace el agente:** dado un cliente con atraso temprano, analiza su situación y **propone** una acción de gestión (contactar con cierto mensaje/tono, ofrecer un plan de pago, o escalar la gestión).
- **Qué NO hace el agente:** ejecutar nada por su cuenta. Toda acción con efectos la aprueba un humano primero.
- **Es una PoC con datos simulados.** Sin integraciones reales. Corre localmente.

---

## 2. Criterio rector (lo más importante de este archivo)

Este proyecto se evalúa como trabajo de **Product Manager**, no de desarrollo. El código es evidencia de ejecución, pero el valor está en las decisiones de producto.

- **Producto → código, siempre.** Cada pieza técnica sirve a una decisión de producto explícita.
- **El gate de aprobación humana es el corazón del proyecto.** Es la pieza más importante. Tratala como tal.
- **Código mínimo, legible y reproducible.** Este código es un handoff a un equipo de Tecnología que lo va a productizar. Lo tienen que poder leer y entender rápido. **No sobre-ingenierices.** Nada de abstracciones innecesarias, patrones rebuscados, ni dependencias que no aporten.
- **Legibilidad > astucia.** Preferí código obvio sobre código clever. Si una solución simple y una sofisticada resuelven lo mismo, va la simple.
- **Cada paso deja algo verificable.** No construyas varias piezas a ciegas. Cada etapa produce algo que se puede correr y comprobar.

---

## 3. El caso de uso: cobranza temprana

El agente trabaja sobre clientes con **atraso temprano** (primeros días de mora), donde todavía se puede recuperar el crédito de forma barata y sin dañar la relación.

**Acciones que el agente puede proponer** (lista cerrada — el agente no inventa acciones fuera de esta lista):
- `recordatorio` — contactar al cliente con un mensaje/tono determinado.
- `plan_de_pago` — ofrecer refinanciar la deuda en cuotas.
- `escalar` — derivar la gestión a un nivel superior de cobranza.

**Lógica de producto:** no todos los atrasos son iguales. Un buen pagador con atraso leve necesita un recordatorio suave; un deudor recurrente necesita otra gestión. El valor del agente está en **segmentar por contexto individual** (historial, monto, días de atraso) en vez de tratar a todos igual.

---

## 4. Decisiones de arquitectura (ya tomadas — respetar)

- **Lenguaje:** Python.
- **Arquitectura:** backend Python + frontend web mínimo, **físicamente separados**. El backend es un servicio con API; el frontend es un cliente que consume esa API.
- **El control por código vive en el backend**, nunca en el frontend ni en el prompt. Se debe poder apagar el frontend entero y el gate sigue funcionando.
- **Harness artesanal (a mano), no framework de agentes.** El loop, las tools, el llamado al modelo y el gate se escriben explícitamente para que el control sea visible y auditable.
- **Modelo:** Claude vía API de Anthropic. **Temperatura fija y baja** (para que los evals sean estables y reproducibles).
- **API key por variable de entorno.** NUNCA hardcodeada. Se lee de `ANTHROPIC_API_KEY`.
- **Datos:** 100% sintéticos. El grueso generado, pero con **casos difíciles curados a mano**.

---

## 5. Estructura del repo (respetar exactamente)

```
bankingly-collections-agent/
├── README.md                 # Técnico: setup + arquitectura del agente + ADRs
├── PRD.md                    # Producto: lo redacta el PM por fuera del build (NO lo genera Claude Code)
├── .env.example              # Variables necesarias (sin valores reales)
├── .gitignore                # Excluye .env y secretos
├── requirements.txt          # Dependencias Python
├── backend/
│   ├── agent.py              # El harness: loop, razonamiento, propuesta
│   ├── tools.py              # Tools que el modelo puede pedir usar
│   ├── approval.py           # EL GATE. Control por código, aislado acá
│   ├── api.py                # Endpoints (evaluar caso / aprobar acción)
│   └── models.py             # Estructuras de datos (caso, propuesta, estado)
├── frontend/                 # Cliente mínimo: muestra y dispara, nada más
├── data/
│   ├── clientes.json         # Grueso sintético
│   └── casos_dificiles.json  # Curados a mano (o marcados dentro de clientes)
├── evals/
│   ├── eval_set.json         # Casos de prueba con categoría y resultado esperado
│   ├── run_evals.py          # Script que corre la evaluación
│   └── results.md            # Resultados por categoría + análisis de errores
└── ai_interactions/
    └── interactions.md       # Intercambios con la IA (curados al final)
```

**Regla sobre `approval.py`:** el gate va aislado en su propio archivo, con nombres explícitos. Debe poder señalarse en una sola pantalla y explicarse solo. No lo distribuyas ni lo escondas dentro de otros archivos.

---

## 6. Convención de idioma

- **Inglés** para la mecánica del código: nombres de archivos, funciones, variables de control, endpoints. Ej: `evaluate_case()`, `require_approval()`, `pending_actions`.
- **Español** para los conceptos del dominio de negocio, incluso dentro del código. Ej: `dias_de_atraso`, `monto_adeudado`, `historial_de_pagos`, `plan_de_pago`, `escalar`, `recordatorio`.
- **Español** para todos los documentos: README, PRD, ADRs, comentarios explicativos, `results.md`, `interactions.md`.

Ejemplo del balance esperado:
```python
def evaluate_case(cliente):
    propuesta = agent.propose_action(cliente)  # el agente propone
    return require_approval(propuesta)          # el gate retiene hasta aprobación humana
```

---

## 7. Orden de construcción (seguir esta secuencia)

**Paso 0 — Andamiaje.** Crear estructura de carpetas, `requirements.txt`, `.env.example`, `.gitignore`, README embrionario. Fijar la estructura antes de escribir lógica.

**Paso 1 — Datos simulados.** Generar clientes sintéticos con los campos del dominio. Curar a mano los casos difíciles (buen pagador con atraso leve, moroso recurrente, ambiguo genuino). Verificable: abrir el JSON y ver datos realistas.

**Paso 2 — `models.py` + `approval.py` (EL GATE), juntos y ANTES del agente.** Definir las estructuras de datos y construir el gate primero, para que todo lo demás se construya alrededor del control. Probar el gate en soledad con una propuesta falsa: debe bloquear la ejecución si no hay aprobación. Verificable: el gate rechaza una acción no aprobada.

**Paso 3 — `agent.py` (harness).** El loop, las tools, el llamado al modelo. El agente propone; su propuesta pasa por el gate que ya existe. Verificable: el agente evalúa un caso y produce una propuesta que queda en estado pendiente.

**Paso 4 — `api.py`.** Endpoints que exponen el backend como servicio. Verificable —y crítico para la demo— se le puede pegar a la API sin frontend y comprobar que **pedir ejecución sin aprobación es rechazado**.

**Paso 5 — Frontend mínimo.** Último a propósito. Una pantalla: lista de casos pendientes, razonamiento + datos + acción propuesta del agente, botones aprobar/rechazar/modificar. Sin lógica de control, sin login, sin routing complejo. Si el tiempo aprieta, este paso se recorta sin tocar el backend.

**Paso 6 — Evals.** Set de evaluación con casos etiquetados por categoría, script que corre, y `results.md` con resultados **por categoría** + análisis de errores. La métrica y el umbral se definen ANTES de correr (no se ajustan después de ver el resultado). Incluir casos difíciles donde el agente falle: el análisis de por qué falla vale más que un 100% en casos fáciles.

**Paso 7 — Documentación técnica curada.** Al cierre del build, producir/completar únicamente:
- **README técnico completo:** setup reproducible (cómo instalar, configurar la `ANTHROPIC_API_KEY`, y correr), la sección "Arquitectura del agente" (qué decide el modelo vs. qué garantiza el código), y los ADRs de las decisiones tomadas durante el build.
- **Dejar el material en crudo listo para curar:** los intercambios de IA capturados durante el trabajo, ordenados en `ai_interactions/interactions.md` (los 3 momentos: prompt de pieza central, error detectado, cambio de enfoque). Ordenar y limpiar, sin inventar.
- **`evals/results.md`:** resultados por categoría + análisis de errores (esto sale del Paso 6).

**NO produzcas el `PRD.md` ni el pitch de producto.** Ver la regla 11. El PRD lo redacta el PM por fuera del build.

---

## 8. Reglas de trabajo (innegociables)

1. **El control de aprobación va en código, nunca en el prompt.** No confíes en instrucciones al modelo para garantizar el gate. La garantía es una condición en código (`if not aprobado: bloquear`) que el modelo no puede sortear.
2. **La ejecución de una acción con efectos SIEMPRE pasa por el gate.** No debe existir ningún camino en el código que ejecute una acción sin verificar la aprobación humana.
3. **El frontend no tiene lógica de control.** Solo muestra propuestas y dispara señales (aprobar/rechazar) que el backend valida. Si aparece la tentación de validar algo en el front, va en el backend.
4. **El agente solo propone acciones de la lista cerrada** (`recordatorio`, `plan_de_pago`, `escalar`). No inventa acciones nuevas.
5. **API key y secretos por variable de entorno.** Nunca en el código. `.env` va en `.gitignore`; `.env.example` muestra las variables sin valores.
6. **Temperatura del modelo fija y baja**, para reproducibilidad de los evals.
7. **Registrá decisiones ante ambigüedad como ADR breve** en el README: qué decidiste, qué alternativas consideraste, qué tradeoff aceptaste. Formato corto.
8. **No sobre-ingenierices.** Ante la duda, la solución más simple y legible. Menos código bien pensado > más código sofisticado.
9. **Cada archivo hace una cosa clara.** No mezcles responsabilidades. El gate en `approval.py`, el agente en `agent.py`, los endpoints en `api.py`.
10. **Datos y ejemplos siempre sintéticos y ficticios.** Nunca datos reales de personas.
11. **División de trabajo: qué documentás vos (Claude Code) y qué redacta el PM.**
    - **Claude Code produce:** el código, el README técnico (setup + arquitectura del agente + ADRs), los `results.md` de evals, y deja ordenados los intercambios de IA en crudo.
    - **El PM redacta por fuera del build (NO Claude Code):** el `PRD.md` completo (elección del caso, usuarios, alcance, requisitos priorizados, criterios de aceptación, visión a 12 meses, roadmap, business case, Go/No-Go con criterios de reversión) y el pitch de producto. Son entregables de producto y de negocio que dependen de criterio de PM y de los resultados finales; no se generan automáticamente.
    - Si durante el build surge contenido útil para el PRD (un dato, una decisión, un número), **anotalo en el README o como ADR** para que el PM lo tome — pero no escribas el PRD.

---

*Fin del briefing. Ante cualquier decisión no cubierta acá: elegí lo más simple y legible, registrala como ADR, y seguí. Y recordá: el PRD y el pitch de producto los hace el PM, no vos.*
