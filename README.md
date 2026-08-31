# Agente de cobranza temprana — PoC

PoC de un **agente interno de cobranza temprana** para instituciones financieras de LATAM,
en el marco de "banca agéntica": un agente con IA que hace trabajo bancario real, siempre
con **aprobación humana** antes de ejecutar cualquier acción con efectos.

El usuario del agente es un **analista de cobranzas** de la institución, no el cliente final.
Dado un cliente con atraso temprano (1 a 30 días), el agente analiza su situación y **propone**
una acción de gestión. **No ejecuta nada por su cuenta:** toda acción con efectos pasa por un
gate de aprobación humana garantizado **por código**, no por el prompt.

| Acción (lista cerrada) | Qué es |
|---|---|
| `recordatorio` | Contactar al cliente con un mensaje y un tono determinados. |
| `plan_de_pago` | Ofrecer refinanciar la deuda en cuotas. |
| `escalar` | Derivar la gestión a un nivel superior de cobranza. |

**Estado: construido, corriendo y medido.** Backend, gate, agente, API, frontend y evaluación
completos. Datos 100% sintéticos, sin integraciones reales, corre localmente.

- **Medición:** [`evals/results.md`](evals/results.md) — 54 casos, tres corridas, con el
  análisis de errores y el Go/No-Go fundado.
- **Cómo funciona por dentro:** la sección [Arquitectura del agente](#arquitectura-del-agente).
- **Por qué está hecho así:** el [registro de decisiones](#registro-de-decisiones-adrs), 12 ADRs.

---

## Setup

Requiere **Python 3.10 o superior** (el SDK `anthropic` 1.x lo exige). Probado con 3.12.
No hace falta Node ni ningún paso de build: el frontend es HTML y JavaScript planos.

```bash
# 1. Entorno virtual
python3 -m venv .venv
source .venv/bin/activate          # en Windows: .venv\Scripts\activate

# 2. Dependencias
pip install -r requirements.txt

# 3. Credenciales
cp .env.example .env
# editar .env y completar ANTHROPIC_API_KEY
```

La API key se lee **sólo** de la variable de entorno. Nunca está en el código, y `.env`
está en `.gitignore`.

### Correr la aplicación

Dos procesos, cada uno en su terminal, los dos desde la raíz del repo.

```bash
# Terminal 1 — el backend (la API)
.venv/bin/uvicorn api:app --app-dir backend --port 8000 --reload

# Terminal 2 — el frontend (archivos estáticos)
.venv/bin/python -m http.server 5173 --directory frontend
```

Después, abrir **http://localhost:5173**. La documentación interactiva de la API queda en
http://localhost:8000/docs.

> El frontend se sirve por HTTP y no abriendo el archivo con doble clic: desde `file://`
> el navegador bloquea las llamadas a la API.

> La bandeja de propuestas vive **en memoria**. Al reiniciar el backend se vacía.

### Verificaciones

Las que **no** consumen API de Anthropic:

```bash
# El gate, en soledad: sin agente, sin modelo, sin API, sin frontend.
# 12 comprobaciones, incluido el intento de saltearlo con una propuesta falsificada.
.venv/bin/python backend/probar_gate.py

# Regenerar los datos sintéticos y la rúbrica de evaluación
# (reproducible: misma semilla, mismo archivo — ver eval_set.json)
python3 data/generar_clientes.py
python3 data/generar_casos_escalamiento.py
python3 evals/generar_eval_set.py
```

Las que **sí** consumen API de Anthropic:

```bash
# El agente sobre algunos casos, mostrando su trayectoria y razonamiento
.venv/bin/python backend/probar_agente.py CLI-001 CLI-003 CLI-006

# El control desde afuera: pegarle a la API con curl, sin frontend.
# Requiere el backend levantado en otra terminal.
bash backend/probar_api.sh

# La evaluación completa (50 casos, ~20 min, ~100 llamadas al modelo).
# Los datos crudos de las tres corridas originales no van en el repo (no son
# el entregable); el análisis completo sobre ellos está en evals/results.md.
.venv/bin/python evals/run_evals.py --crudo evals/mi_corrida.json

# La iteración 2 del eval (4 casos de escalamiento)
.venv/bin/python evals/run_evals.py \
    --eval-set evals/eval_set_escalamiento.json \
    --crudo evals/mi_corrida_escalamiento.json
```

---

## Estructura del repo

```
bankingly-collections-agent/
├── README.md                       Este archivo: setup + arquitectura + ADRs
├── PRD.md                          Elección del caso, alcance, roadmap, Go/No-Go
├── .env.example                    Variables necesarias, sin valores
├── .gitignore                      Excluye .env y secretos
├── requirements.txt                4 dependencias, cada una justificada
│
├── backend/
│   ├── models.py                   Estructuras: Cliente, Propuesta, EstadoDePropuesta
│   ├── approval.py                 EL GATE. El control por código, aislado acá
│   ├── tools.py                    La tool que el modelo puede pedir usar
│   ├── agent.py                    El harness: loop, prompt, llamado al modelo
│   ├── api.py                      Endpoints HTTP
│   ├── probar_gate.py              Prueba el gate en soledad (sin modelo ni API)
│   ├── probar_agente.py            Corre el agente sobre casos sueltos
│   └── probar_api.sh               Demuestra el control con curl, sin frontend
│
├── frontend/                       Cliente mínimo, sin build ni dependencias
│   ├── index.html                  Una pantalla: la bandeja del analista
│   ├── app.js                      Llama a la API y muestra. Sin lógica de control
│   └── estilos.css
│
├── data/
│   ├── generar_clientes.py         Genera la cartera (semilla fija) + los 10 curados
│   ├── clientes.json               50 clientes sintéticos
│   ├── generar_casos_escalamiento.py   Iteración 2, nacida de un hallazgo del eval
│   └── casos_escalamiento.json     4 casos donde sólo cabe escalar
│
├── evals/
│   ├── generar_eval_set.py         La rúbrica, como código auditable y reproducible
│   ├── eval_set.json               50 casos etiquetados (congelado antes de medir)
│   ├── eval_set_escalamiento.json  Los 4 de la iteración 2
│   ├── run_evals.py                Corre agente + juez y puntúa las 4 dimensiones
│   └── results.md                  EL REPORTE: las tres corridas y el análisis de errores
│
└── ai_interactions/
    ├── exportar_sesion.py          Exportador mecánico de la sesión
    ├── sesion_completa.md          La sesión entera, legible
    ├── sesion_completa.jsonl       El volcado crudo, sin tocar
    ├── candidatos.md               Los tres momentos, pre-localizados
    └── interactions.md             Los tres momentos curados
```

## Arquitectura del agente

La pregunta que responde esta sección: **qué decide el modelo y qué garantiza el código.**

### La regla

**El modelo propone; el código dispone.** El modelo nunca ejecuta una acción con efectos.
Toda acción pasa por un gate que es código, no una instrucción en el prompt.

### El reparto de responsabilidades

| Lo decide el **modelo** (cognitivo, difuso) | Lo garantiza el **código** (determinístico, innegociable) |
|---|---|
| Qué datos pedir y cuándo pedirlos | Que sólo se propongan acciones de la lista cerrada |
| Cómo interpretar el historial y el contexto | Que **nada** se ejecute sin aprobación humana |
| Qué acción proponer, entre las tres | Que quede registrado si consultó datos antes de proponer |
| Con qué tono hacer la gestión | Que las transiciones de estado sean válidas (no ejecutar dos veces, no aprobar lo rechazado) |
| Cómo explicar su razonamiento | Que el modelo nunca vea la etiqueta de evaluación del caso |
| Cuándo declarar que el caso es dudoso | El registro auditable de todo, incluidos los intentos bloqueados |

### El loop, paso a paso

El modelo aparece en **2 de 9 pasos**. Todo lo demás es código.

```
  ┌─ 1. CÓDIGO   Se recibe un cliente_id. Se arma el caso.
  │              Al modelo se le pasa el ID, NO los datos.
  │
  │  2. MODELO   Pide usar la tool consultar_cliente.
  │
  │  3. CÓDIGO   El harness ejecuta la tool y devuelve el perfil.
  │              Error controlado si el cliente no existe.
  │
  │  4. MODELO   Razona y propone UNA acción + razonamiento + tono.
  │              La forma la impone el schema de la API, no el prompt.
  │
  │  5. CÓDIGO   GUARDRAIL: ¿la acción está en la lista cerrada?
  │              Si no, se rechaza acá.
  │
  │  6. CÓDIGO   EL GATE. La propuesta queda RETENIDA.
  ▼              Estado: pendiente_de_aprobacion. Nada se ejecuta.
     ─────────────────── espera a una persona ───────────────────
  ┌  7. HUMANO   Aprobar / rechazar / modificar (vía API).
  │              Sólo la aprobación humana habilita la ejecución.
  │
  │  8. CÓDIGO   LA GUARDA DURA. Sólo si está aprobada, se ejecuta.
  │              Si no: ExcepcionAprobacionRequerida.
  │
  └─ 9. CÓDIGO   Estado final + registro auditable.
```

Que al modelo se le pase el ID y no los datos no es un detalle: hace que la trayectoria sea
**real y medible**. Si se le sirvieran los datos, no habría forma de saber si consultó — que
es lo que mide la Dimensión 4 del eval (dio 100%).

### Dónde vive el control

En **[`backend/approval.py`](backend/approval.py)**, aislado, y en una sola condición:

```python
def ejecutar_accion(propuesta_id: str) -> Propuesta:
    propuesta = obtener_propuesta(propuesta_id)
    ...
    # ─── LA GUARDA DURA ─────────────────────────────────────────
    if not propuesta.aprobada:
        _registrar_en_bitacora("ejecucion_bloqueada", propuesta, ...)
        raise ExcepcionAprobacionRequerida(
            f"No se puede ejecutar la propuesta {propuesta_id}: "
            f"su estado es '{propuesta.estado.value}' y se requiere aprobación humana."
        )
    # ────────────────────────────────────────────────────────────
    resultado = _ejecutar_efecto_simulado(propuesta)
```

Tres decisiones hacen que esa guarda sea el **único** portón y no un cartel que se puede
rodear (detalle y límites en el ADR-006):

1. **Recibe un `propuesta_id`, no un objeto `Propuesta`.** Busca el estado en el repositorio.
   Si recibiera el objeto, cualquiera podría fabricar uno con `estado=APROBADA` y pasárselo.
2. **El efecto con consecuencias es una función privada del mismo módulo**
   (`_ejecutar_efecto_simulado`), que sólo llama el portón. No hay un módulo de "ejecución"
   importable que alguien pueda invocar de costado.
3. **`aprobada` es una propiedad derivada de `estado`**, no un booleano suelto: no puede
   existir una propuesta rechazada que además diga que está aprobada.

Y `aprobar()` es **la única función del sistema** que lleva una propuesta a `aprobada`.

### Qué NO puede hacer el modelo, por construcción

- **Aprobar nada.** El modelo devuelve texto; no hace llamadas a funciones de Python.
- **Ejecutar nada.** El efecto está detrás de la guarda, siempre.
- **Inventar una acción.** El enum del schema sale de `ACCIONES_PERMITIDAS`, la misma
  constante que valida el gate, y además se revalida en código al parsear la respuesta.
- **Ver la etiqueta del caso.** El campo `arquetipo` no existe en la clase `Cliente`: al
  construirla desde el registro crudo, la etiqueta se cae sola. Es una garantía estructural,
  no una instrucción del prompt que alguien pueda olvidar.

**El límite honesto:** en Python nada impide que otro código mute `propuesta.estado` a mano.
El guion bajo es convención, no candado. La garantía fuerte no es contra un programador
hostil: es contra **el modelo**, y ahí es total. Ese es el riesgo que este proyecto controla.

### Por qué principios y no reglas

El prompt le da al agente el **marco de negocio** —criterio del oficio— y no un árbol de
decisión. Nada de "si el atraso es menor a 7 días, recordatorio": eso sería un `if` disfrazado
de agente. El prompt no contiene un solo umbral numérico.

La contracara está asumida: con principios el agente es **menos predecible** que una regla.
Eso no es un defecto del diseño, es el motivo por el cual el gate existe. Si el agente fuera
perfectamente predecible, la aprobación humana sobraría.

### Cómo demostrarlo en 30 segundos

```bash
# Sin modelo, sin API, sin frontend: el gate solo.
.venv/bin/python backend/probar_gate.py
```

Doce comprobaciones. La más importante es el escenario 7: se fabrica un objeto `Propuesta`
que se auto-declara `estado=APROBADA` y usurpa el id de una propuesta real — y el gate lo
bloquea igual, porque consulta el repositorio en vez de creerle al objeto.

```bash
# Con el backend levantado: el control desde afuera, salteando el frontend.
bash backend/probar_api.sh
```

Pide la ejecución de una propuesta pendiente con `curl` y el backend responde **403**.
También prueba que mandar `{"aprobada": true}` en el cuerpo del pedido no cambia nada: el
endpoint ni siquiera lee el cuerpo, el estado sale del repositorio del gate.

---

## Alcance de esta PoC

**Lo que hace:** propone una acción por cliente con su razonamiento, la retiene hasta que un
humano decida, y mide la calidad de esas propuestas con un set de evaluación de 54 casos.

**Lo que no hace:** no ejecuta acciones reales (el envío es simulado), no prioriza la cartera
(ver OP-01), no tiene login ni usuarios, no persiste en base de datos, no se integra con
ningún core bancario.

---

## Registro de decisiones (ADRs)

Estilo breve: qué se decidió, qué alternativa se consideró, qué tradeoff se aceptó.

| | Decisión | Paso |
|---|---|---|
| ADR-001 | Frontend estático, sin framework ni build | 0 |
| ADR-002 | Reproducibilidad: `effort`, no `temperature` | 0 |
| ADR-003 | Un solo `clientes.json` con los curados marcados | 0-1 |
| ADR-004 | El historial son meses cerrados, sin el atraso de hoy | 1 |
| ADR-005 | Categoría de contraste en los evals | 1 |
| ADR-006 | **Cómo se garantiza que la guarda es el único portón** | 2 |
| ADR-007 | El analista puede modificar la acción, y queda registrado | 2 |
| ADR-008 | Aprobar y ejecutar son endpoints separados | 4 |
| ADR-009 | Excepciones del gate → HTTP en un solo lugar | 4 |
| ADR-010 | Conteo agregado en la tool: decidir después de medir | 4-6 |
| ADR-011 | **La mitigación que refutó su propia hipótesis** | 6 |
| ADR-012 | Los casos de escalamiento van en archivos separados | 6 |

**ADR-001 — Frontend estático, sin framework ni build.** Decisión: HTML + CSS + JS plano
por `fetch`, sin React ni build. Alternativa: un framework de UI. Tradeoff: se resigna
comodidad de desarrollo a cambio de que la separación física backend/frontend sea evidente
— se puede apagar el frontend entero y el gate sigue funcionando.

**ADR-002 — Reproducibilidad: `effort`, no `temperature`.** Los modelos actuales de
Anthropic eliminaron `temperature` (HTTP 400 si se envía), así que la instrucción literal
de "temperatura fija y baja" es inejecutable. Decisión: `claude-opus-5` sin `temperature`,
con `output_config.effort` bajo y constante como palanca de estabilidad. Tradeoff: se
conserva la intención de la especificación (evals reproducibles) por encima de su letra;
la reproducibilidad es alta pero no bit-exacta, y se declara así en `results.md`.

**ADR-003 — Un solo `clientes.json` con los curados marcados.** Decisión: los 10 casos
curados llevan un campo `arquetipo`; los 40 generados lo llevan en `null`. Alternativa:
un archivo separado para los curados. Tradeoff: se resigna separación visual a cambio de
una sola fuente de verdad para la cartera.

**ADR-004 — El historial son meses cerrados.** La especificación no aclaraba si el mes en
curso entra en el historial; incluirlo volvía imposible el arquetipo "buen pagador
olvidadizo" (no podía tener 12 meses impecables y estar en mora a la vez). Decisión: el
historial son sólo los meses ya cerrados; el atraso de hoy vive en `dias_de_atraso`.

**ADR-005 — Categoría de contraste en los evals.** Quedaron 5 casos normales con historial
impecable y atraso alto (25-28 días). Decisión: usar los 2 más extremos (CLI-025, CLI-046)
como categoría de contraste, para medir si el agente calibra la firmeza por magnitud de
mora y no sólo por historial. Sin fabricar datos nuevos.

**ADR-006 — Cómo se garantiza que la guarda es el único portón.** Tres medidas en
`approval.py`: (1) `ejecutar_accion()` recibe un `propuesta_id`, no un objeto, y busca el
estado en el repositorio — así nadie puede fabricar una propuesta que "diga" estar
aprobada; (2) el efecto con consecuencias vive en una función privada del módulo, sólo
invocable desde el portón; (3) `aprobada` es una propiedad derivada de `estado`, no un
booleano suelto. **Límite honesto:** la garantía es total contra el modelo (que sólo
devuelve texto), no un candado contra código con acceso directo al proceso.

**ADR-007 — El analista puede modificar la acción, y queda registrado.**
`aprobar_con_modificacion()` guarda qué había propuesto el agente originalmente en
`accion_propuesta_originalmente`. Tradeoff: un campo más, a cambio de una señal barata de
en qué se corrige al agente el analista que lo usa todos los días.

**ADR-008 — Aprobar y ejecutar son endpoints separados.** Decisión: `POST /aprobar` y
`POST /ejecutar` son llamadas distintas; aprobar no dispara la gestión. Alternativa: que
aprobar ejecute en el mismo paso (más cómodo). Tradeoff: se resigna comodidad para poder
demostrar el bloqueo del gate pidiendo `/ejecutar` sobre algo pendiente (ver OP-02).

**ADR-009 — Excepciones del gate → HTTP en un solo lugar.** Un mapa único de excepción a
código de estado: el bloqueo del gate es siempre 403, sin importar la ruta. Tradeoff: una
indirección más para leer, a cambio de que ninguna ruta pueda olvidarse de traducir un
rechazo y de que las rutas queden sin lógica de control propia.

**ADR-010 — Conteo agregado en la tool: decidir después de medir.** En el Paso 3 el agente
contó mal un historial ("3 no_pago y 4 tardío" cuando eran 3 y 5). Decisión: no implementar
la mitigación todavía, para no borrar evidencia del modo de falla antes de medirlo. Cerrado
en el Paso 6 tras medir su frecuencia real (ver ADR-011).

**ADR-011 — La mitigación que refutó su propia hipótesis.** Se implementó: `consultar_cliente`
devuelve el conteo del historial ya calculado, además del historial crudo. Hipótesis: ese
error de conteo *causaba* la única acción equivocada de la corrida base. Resultado al medir
de nuevo: el conteo se corrigió, pero la acción no cambió en ninguno de los 50 casos — el
error *acompañaba*, no causaba. Se dejó implementada igual (elimina una clase real de error
factual) y el hallazgo real terminó siendo otro: la rúbrica del eval no ponderaba recencia,
mientras el prompt sí se lo pedía al agente.

**ADR-012 — Los casos de escalamiento van en archivos separados.** Nacieron después de
medir, del hallazgo de que el agente nunca proponía `escalar` en los 50 casos base.
Decisión: 4 casos nuevos en `data/casos_escalamiento.json` y `eval_set_escalamiento.json`,
sin mezclarlos con la cartera base, para no romper la comparación antes/después de la
mitigación. Resultado: escaló 4 de 4 — prudente, no incapaz.

---

## Oportunidades identificadas durante la validación

Dos cosas que se vieron **usando el prototipo**, no ideas de escritorio. Ambas están
desarrolladas en el roadmap del [`PRD.md`](PRD.md) (Etapa 2).

**OP-01 — Falta una etapa previa de priorización de cartera.** Con 50 clientes el
analista elige a mano de una lista; con una cartera real de miles, el problema no es sólo
"qué acción tomar" sino "a quién atender primero". Decisión deliberada de alcance: no se
construyó en esta PoC para no diluir el foco del gate, que es el corazón del proyecto.

**OP-02 — La aprobación en dos pasos es fricción para el analista.** Aprobar y después
ejecutar se siente como doble tarea. Se dejó así a propósito (ver ADR-008): es lo que
permite demostrar el bloqueo del gate pidiendo la ejecución de algo pendiente. En
producción se resuelve con un botón único que encadena las dos llamadas por código, sin
tocar la garantía — `ejecutar_accion()` sigue verificando la aprobación igual.

---

## Producto

El [`PRD.md`](PRD.md) —caso de uso y alternativas descartadas, usuarios, alcance,
requisitos priorizados en 3 etapas, visión a 12 meses, roadmap, métricas, riesgos y
Go/No-Go con criterios de reversión— está redactado y completo. Se apoya en los 12 ADRs
de arriba y en la medición completa de [`evals/results.md`](evals/results.md).

---

## Intercambios con la IA

En [`ai_interactions/`](ai_interactions/): los tres momentos curados en `interactions.md`,
la sesión completa (`sesion_completa.md`, legible, y `sesion_completa.jsonl`, sin editar),
y `candidatos.md` con los momentos pre-localizados antes de elegir.
