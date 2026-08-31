# Especificación del agente y el gate — Cobranza temprana

> Insumo de construcción para Claude Code (Pasos 2 y 3 del build — el corazón del sistema). Define la arquitectura del harness, el comportamiento del gate, las tools y el diseño del prompt del agente. Es la pieza más importante del proyecto: el control por código vive acá. Implementar estas decisiones, no re-decidirlas.

---

## 1. Qué es el agente y qué es el harness

- **El agente** = el modelo (Claude vía API) razonando sobre un caso y proponiendo una acción.
- **El harness** = todo el código alrededor del modelo que lo convierte en un sistema controlado: el loop, las tools, el estado, las validaciones y el gate.
- **Regla de oro:** el modelo PROPONE; el código DISPONE. El modelo nunca ejecuta una acción con efectos. Toda acción pasa por el gate, que es código.

La línea que hay que trazar con claridad (esto se documenta en el README como "Arquitectura del agente"):
- **El modelo decide:** qué datos pedir, cómo interpretar el caso, qué acción proponer, cómo explicar su razonamiento. Lo cognitivo/difuso.
- **El código garantiza:** que solo se propongan acciones de la lista cerrada, que la ejecución nunca ocurra sin aprobación humana, que el agente haya consultado datos antes de proponer, y el registro auditable. Lo determinístico/innegociable.

---

## 2. El loop del agente (trayectoria paso a paso)

Trayectoria corta: consulta datos → razona → propone → gate → (humano) → ejecuta o no.

1. **Inicio (código):** el harness recibe un `cliente_id` a evaluar. Crea el estado del caso: `{cliente_id, paso: "inicio", propuesta: null, aprobado: false}`.
2. **El agente pide datos (modelo):** el agente, siguiendo su prompt, pide usar la tool `consultar_cliente` para obtener el perfil. NO se le pasan los datos servidos; los debe pedir. (Esto hace la trayectoria real y evaluable — Dimensión 4 del eval.)
3. **El harness ejecuta la tool (código):** valida que el cliente exista, ejecuta `consultar_cliente`, devuelve el perfil al agente. Si el cliente no existe, error controlado.
4. **El agente razona y propone (modelo):** con los datos, el agente razona sobre el contexto y propone UNA acción de la lista cerrada + su justificación. Devuelve algo estructurado (acción + razonamiento).
5. **El harness valida la propuesta (código):** verifica que la acción propuesta sea una de la lista cerrada (`recordatorio`/`plan_de_pago`/`escalar`). Si el modelo propuso algo fuera de la lista, se rechaza acá (guardrail). La propuesta pasa a estado `pendiente_de_aprobacion`.
6. **EL GATE (código):** la propuesta queda retenida. NADA se ejecuta. Espera decisión humana. (Ver sección 4.)
7. **El humano decide (persona + código):** aprobar / rechazar / modificar. Solo la aprobación humana setea `aprobado = true`.
8. **Ejecución (código):** SOLO si `aprobado == true`, el harness ejecuta la acción (simulada) y registra todo. Si no, no se ejecuta.
9. **Cierre (código):** estado final `resuelto`, con registro auditable de qué se propuso, quién aprobó, con qué datos, cuándo.

Fijate: el modelo aparece solo en pasos 2 y 4. Todo lo demás es código.

---

## 3. Las tools

**Principio:** mínimas. No inventar tools que no aportan.

- **`consultar_cliente(cliente_id)`** — tool principal. Devuelve el perfil completo del cliente desde `data/`: `tipo_de_producto`, `dias_de_atraso`, `monto_adeudado`, `cuota_vencida`, `antiguedad_meses`, `canal_preferido`, `historial_de_pagos`. Es la tool que el agente DEBE usar antes de proponer.

Una sola tool alcanza para la trayectoria de este agente. Si durante el build aparece una necesidad real de separar (ej. historial detallado aparte), evaluarlo y registrar ADR — pero por defecto, una tool. No agregar tools decorativas.

**Importante:** el `arquetipo`/categoría del cliente (metadata de evals) NO se devuelve en esta tool. El agente nunca ve la etiqueta.

---

## 4. El gate (approval.py) — el corazón

Aislado en `backend/approval.py`, con nombres explícitos. Debe poder señalarse en una pantalla y explicarse solo.

**Comportamiento:**
- Una propuesta tiene un estado: `pendiente_de_aprobacion` → `aprobada` | `rechazada` → (si aprobada) `ejecutada`.
- La función que ejecuta la acción con efectos tiene, en código, una guarda dura:
  ```
  def ejecutar_accion(propuesta):
      if not propuesta.aprobada:
          raise ExcepcionAprobacionRequerida("No se puede ejecutar sin aprobación humana")
      # ... ejecuta la acción simulada
  ```
- **No existe ningún otro camino en el código que ejecute una acción con efectos.** La guarda es el único portón, y siempre está.
- El flag `aprobada` SOLO lo puede setear la acción humana de aprobación (vía API, ver abajo). El modelo no tiene acceso a setearlo. El prompt no puede sortearlo.

**La demostración clave (para la sesión, criterio 2):**
- Debe poder mostrarse que si se llama a `ejecutar_accion` sobre una propuesta no aprobada —incluso salteando el frontend, pegándole directo al backend— se rechaza con la excepción. Eso PRUEBA que el control es de código, no de prompt ni de UI.

---

## 5. El prompt del agente: principios, no reglas

**Decisión de producto (confirmada):** el prompt le da al agente el MARCO DE NEGOCIO (principios de juicio), NO reglas rígidas tipo "si atraso < 7 → recordatorio". Le damos la sabiduría del dominio y lo dejamos razonar. Un árbol de decisión disfrazado invalidaría el sentido de usar un agente.

**El prompt del sistema incluye:**

- **Rol y objetivo:** sos un asistente de cobranza temprana para un analista de una institución financiera. Tu objetivo es proponer la mejor acción para recuperar el pago sin dañar la relación con el cliente.

- **Principios de negocio (reemplazan a las reglas):**
  - No todos los atrasos son iguales; la mejor acción depende del contexto individual.
  - Un historial de pagos sólido sugiere un olvido puntual y amerita un trato suave.
  - Un patrón de atrasos repetidos sugiere más firmeza en la gestión.
  - La firmeza sube con el nivel de riesgo, pero el respeto al cliente nunca baja.
  - El monto adeudado y la antigüedad del cliente modulan la gestión (más monto = más cuidado; cliente nuevo con poca historia = más prudencia ante la incertidumbre).
  - Estás en mora TEMPRANA (1-30 días): el objetivo es actuar a tiempo para evitar que el atraso se agrave.

- **Acciones disponibles (lista cerrada — no inventar otras):**
  - `recordatorio` — contactar al cliente con un mensaje/tono determinado (especificar el tono sugerido).
  - `plan_de_pago` — ofrecer refinanciar la deuda en cuotas.
  - `escalar` — derivar la gestión a un nivel superior de cobranza.

- **Mandato de proceso:**
  - SIEMPRE consultá los datos del cliente (vía tool) antes de proponer. Nunca propongas sin datos.
  - Explicá tu razonamiento: por qué esta acción para este cliente, con base en los datos.
  - Proponé UNA sola acción.

**Lo que el prompt NO incluye (importante):**
- La categoría/arquetipo del caso (sería darle la respuesta).
- Umbrales numéricos rígidos que lo conviertan en árbol de decisión.
- Cualquier pista sobre qué espera el eval.

**Formato de salida del agente:** estructurado y parseable — acción propuesta (de la lista cerrada) + razonamiento + tono/mensaje sugerido si aplica. Definir el formato exacto (JSON u otro) al construir; que sea fácil de validar por código.

---

## 6. Consecuencia de diseño a tener presente

Con principios en vez de reglas, el agente es algo menos predecible que un árbol de decisión. **Esto es correcto y esperable** — y es precisamente por eso que existe el gate de aprobación humana. El agente propone con criterio; el humano valida. Si el agente fuera perfectamente predecible, el gate sobraría. La imperfección controlada es parte del diseño, no un defecto. (Este es un buen argumento para la sesión.)

---

## 7. Reproducibilidad y configuración

- Modelo: Claude vía API de Anthropic. Temperatura fija y baja (evals estables).
- API key por variable de entorno `ANTHROPIC_API_KEY`. Nunca hardcodeada.
- El rango de mora temprana (1-30 días) y la lista de acciones deben ser fácilmente configurables (constantes claras, no números mágicos dispersos) — sostiene la escalabilidad a decenas de instituciones.

---

*Fin de la especificación del agente. Recordar: el modelo propone y el código dispone; el gate es el único portón a la ejecución y siempre está; el agente razona sobre principios, no sigue reglas; nunca ve la categoría del caso.*
