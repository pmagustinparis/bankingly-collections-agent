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

# Regenerar los datos sintéticos (reproducible: misma semilla, mismo archivo)
python3 data/generar_clientes.py
python3 data/generar_casos_escalamiento.py
python3 evals/generar_eval_set.py

# Rehacer el reporte cuantitativo de una corrida ya hecha, sin volver a medir
.venv/bin/python evals/run_evals.py --reporte --crudo evals/resultados_base.json
```

Las que **sí** consumen API de Anthropic:

```bash
# El agente sobre algunos casos, mostrando su trayectoria y razonamiento
.venv/bin/python backend/probar_agente.py CLI-001 CLI-003 CLI-006

# El control desde afuera: pegarle a la API con curl, sin frontend.
# Requiere el backend levantado en otra terminal.
bash backend/probar_api.sh

# La evaluación completa (50 casos, ~20 min, ~100 llamadas al modelo)
.venv/bin/python evals/run_evals.py --crudo evals/resultados_mitigado.json

# La iteración 2 del eval (4 casos de escalamiento)
.venv/bin/python evals/run_evals.py \
    --eval-set evals/eval_set_escalamiento.json \
    --crudo evals/resultados_escalamiento.json
```

---

## Estructura del repo

```
bankingly-collections-agent/
├── README.md                       Este archivo: setup + arquitectura + ADRs
├── PRD.md                          Stub: el PRD lo redacta el PM aparte
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
│   ├── generar_eval_set.py         La rúbrica, como código auditable
│   ├── eval_set.json               50 casos etiquetados (congelado antes de medir)
│   ├── eval_set_escalamiento.json  Los 4 de la iteración 2
│   ├── run_evals.py                Corre agente + juez y puntúa las 4 dimensiones
│   ├── resultados_base.json        Corrida base, datos crudos
│   ├── resultados_mitigado.json    Corrida con la mitigación aplicada
│   ├── resultados_escalamiento.json  Iteración 2
│   └── results.md                  EL REPORTE: resultados y análisis de errores
│
└── ai_interactions/
    ├── exportar_sesion.py          Exportador mecánico de la sesión
    ├── sesion_completa.md          La sesión entera, legible
    ├── sesion_completa.jsonl       El volcado crudo, sin tocar
    ├── candidatos.md               Los tres momentos, pre-localizados
    └── interactions.md             Esqueleto para curar (lo completa el PM)
```

---

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

Formato corto: qué se decidió, qué alternativas se consideraron, qué tradeoff se aceptó.

| | Decisión | Paso |
|---|---|---|
| [ADR-001](#adr-001--frontend-estático-sin-framework-ni-build) | Frontend estático, sin framework ni build | 0 |
| [ADR-002](#adr-002--reproducibilidad-de-los-evals-effort-no-temperature) | Reproducibilidad: `effort`, no `temperature` | 0 |
| [ADR-003](#adr-003--un-solo-clientesjson-con-los-casos-curados-marcados-adentro) | Un solo `clientes.json` con los curados marcados | 0-1 |
| [ADR-004](#adr-004--historial_de_pagos-son-meses-cerrados-el-atraso-actual-no-está-adentro) | El historial son meses cerrados | 1 |
| [ADR-005](#adr-005--categoría-de-contraste-en-los-evals-buen-pagador-con-atraso-largo) | Categoría de contraste en los evals | 1 |
| [ADR-006](#adr-006--cómo-se-garantiza-que-la-guarda-del-gate-es-el-único-portón) | **Cómo se garantiza que la guarda es el único portón** | 2 |
| [ADR-007](#adr-007--el-analista-puede-modificar-la-acción-y-eso-queda-registrado) | El analista puede modificar, y queda registrado | 2 |
| [ADR-008](#adr-008--aprobar-y-ejecutar-son-dos-endpoints-separados) | Aprobar y ejecutar son endpoints separados | 4 |
| [ADR-009](#adr-009--las-excepciones-del-gate-se-traducen-a-http-en-un-solo-lugar) | Excepciones del gate → HTTP en un solo lugar | 4 |
| [ADR-010](#adr-010--conteo-agregado-en-la-tool-la-decisión-que-se-difirió-hasta-medir) | Conteo agregado en la tool: decidir después de medir | 4-6 |
| [ADR-011](#adr-011--mitigación-del-error-de-conteo-se-implementó-y-no-arregló-lo-que-se-esperaba) | **La mitigación que refutó su propia hipótesis** | 6 |
| [ADR-012](#adr-012--los-casos-de-escalamiento-van-en-archivos-separados) | Los casos de escalamiento van en archivos separados | 6 |

### ADR-001 — Frontend estático, sin framework ni build

- **Decisión:** el frontend es HTML + CSS + JavaScript plano, servido como archivos estáticos,
  consumiendo la API del backend por `fetch`.
- **Alternativas:** React/Vite, o un template server-side renderizado por FastAPI.
- **Tradeoff:** se resigna comodidad de desarrollo y componentes reutilizables. A cambio:
  cero dependencias de front, cero paso de build, y —lo que importa— la **separación física**
  entre backend y frontend queda evidente. Se puede apagar el frontend entero y el gate sigue
  funcionando, que es exactamente lo que hay que poder demostrar. Como el frontend es el paso
  que se recorta si aprieta el tiempo, conviene que no arrastre infraestructura propia.

### ADR-002 — Reproducibilidad de los evals: `effort`, no `temperature`

- **Contexto:** la especificación pedía "temperatura fija y baja" para que los evals sean estables.
- **Problema:** los modelos actuales de Anthropic (familia Claude 5 y Opus 4.7/4.8) **eliminaron
  el parámetro `temperature`**: enviarlo devuelve HTTP 400. La instrucción literal es
  inejecutable con un modelo actual.
- **Decisión:** usar `claude-opus-5` sin `temperature`, y fijar la palanca de reproducibilidad
  disponible: `output_config.effort` en un valor bajo y constante, prompt fijo y datos fijos.
- **Alternativas:** (a) bajar a `claude-sonnet-4-6`, que todavía acepta `temperature=0`, y cumplir
  la instrucción al pie de la letra; (b) lo decidido.
- **Tradeoff:** se resigna la letra de la especificación para conservar su **intención**
  (evals estables y reproducibles) sobre un modelo vigente. A cambio, se asume que la
  reproducibilidad es *alta pero no bit-exacta*: ni siquiera `temperature=0` garantizaba
  determinismo, así que la pérdida real es menor que la aparente. **Se declara en `results.md`**
  que las corridas pueden variar levemente, en vez de prometer un determinismo que no existe.
- **Nota para el PRD:** este es un ejemplo concreto de decisión ante ambigüedad — la
  especificación envejeció respecto de la API, se detectó al construir, y se resolvió
  conservando la intención por encima de la letra.

### ADR-003 — Un solo `clientes.json`, con los casos curados marcados adentro

- **Decisión:** los 50 clientes viven en `data/clientes.json`. Los 10 casos curados a mano se
  distinguen por un campo `arquetipo`; los 40 generados lo llevan en `null`.
- **Alternativas:** un `data/casos_dificiles.json` separado (contemplado en la especificación).
- **Tradeoff:** se resigna la separación visual entre curados y generados. A cambio, hay **una
  sola fuente de verdad** para la cartera: la tool `consultar_cliente` lee un único archivo y no
  hay riesgo de que un cliente exista en un archivo y no en el otro. El campo `arquetipo` es
  metadata de evaluación y **nunca se le pasa al modelo**.
- **Estado:** confirmada al construir los datos (Paso 1).

### ADR-004 — `historial_de_pagos` son meses cerrados; el atraso actual no está adentro

- **Contexto:** la especificación de datos no aclaraba si el mes en curso —el que está
  impago hoy— forma parte del historial. Había una contradicción latente: un buen pagador
  que se olvidó no podría tener 12 meses `a_tiempo` y estar en mora al mismo tiempo.
- **Decisión:** el historial son los meses **ya cerrados**, del más antiguo al más reciente.
  El atraso de hoy vive únicamente en `dias_de_atraso`. Son dos señales distintas: el
  track record y la situación actual.
- **Alternativas:** incluir el mes en curso como último elemento del historial.
- **Tradeoff:** la alternativa haría redundante parte de `dias_de_atraso` y volvería
  imposible el arquetipo "buen pagador olvidadizo", que es justamente el caso que mide si
  el agente daña la relación con buenos clientes. Se resigna literalidad respecto de la
  frase "últimos 12 meses" a cambio de que los datos sean internamente coherentes.

### ADR-005 — Categoría de contraste en los evals: buen pagador con atraso largo

- **Contexto:** al generar la cartera quedaron 5 casos normales con historial impecable y
  atraso alto (CLI-014, CLI-015, CLI-025, CLI-030, CLI-046; dos de ellos con 25 y 28 días).
  No son ningún arquetipo curado, pero son una situación genuinamente interesante.
- **Decisión:** usarlos en el Paso 6 como **categoría de contraste**, para responder una
  pregunta que ningún arquetipo cubre por sí solo: *¿el agente gestiona distinto a un buen
  pagador con 3 días de atraso que a uno con 28?* Si trata igual a los dos, no está
  calibrando la firmeza por nivel de riesgo — que es un principio explícito del dominio.
- **Tradeoff:** suma una categoría al reporte de evals sin fabricar datos nuevos: son casos
  que ya existían en la cartera. El costo es un poco más de superficie de medición.

### ADR-006 — Cómo se garantiza que la guarda del gate es el único portón

- **Contexto:** que exista un `if not propuesta.aprobada: raise ...` no alcanza si hay
  formas de rodearlo. Había que cerrar los caminos alternativos.
- **Decisión:** tres medidas, todas en `backend/approval.py`:
  1. **`ejecutar_accion()` recibe un `propuesta_id`, no un objeto `Propuesta`.** Busca el
     estado en el repositorio. Si recibiera el objeto, cualquiera podría construir uno con
     `estado=APROBADA` y pasarlo. Está demostrado en el escenario 7 de `probar_gate.py`.
  2. **El efecto con consecuencias vive en una función privada del propio módulo**
     (`_ejecutar_efecto_simulado`), que sólo llama el portón. No hay un módulo de
     "ejecución" importable que alguien pueda invocar de costado.
  3. **`aprobada` es una propiedad derivada de `estado`**, no un booleano suelto: no puede
     existir una propuesta rechazada que además diga que está aprobada.
- **Alternativa:** la firma literal de la especificación, `ejecutar_accion(propuesta)`.
- **Tradeoff:** se resigna la firma exacta de la especificación a cambio de que la garantía
  sea real y no de buena fe. **Límite que hay que decir en voz alta:** en Python nada impide
  que otro código mute `propuesta.estado` a mano — el guion bajo es convención, no candado.
  La garantía fuerte no es contra un programador hostil, es contra **el modelo**: el modelo
  devuelve texto, no llamadas a funciones de Python, así que no tiene ninguna vía para
  aprobar nada. Ese es exactamente el riesgo que este proyecto tiene que controlar.

### ADR-007 — El analista puede modificar la acción, y eso queda registrado

- **Decisión:** además de aprobar y rechazar, el gate expone `aprobar_con_modificacion()`.
  Guarda qué había propuesto el agente en `accion_propuesta_originalmente`.
- **Tradeoff:** agrega una función y un campo. A cambio deja un dato que en producción vale
  mucho: **en qué se corrige al agente**. La tasa de modificación por acción y por perfil es
  la señal más barata para saber dónde el criterio del agente se aparta del criterio del
  analista que lo usa todos los días. **Nota para el PRD:** sirve como métrica de adopción y
  como insumo de mejora continua.
- **Nota de control:** la acción que elige el humano también se valida contra la lista
  cerrada. El gate no le cree al modelo, pero tampoco le cree a la UI.

### ADR-008 — Aprobar y ejecutar son dos endpoints separados

- **Decisión:** `POST /propuestas/{id}/aprobar` y `POST /propuestas/{id}/ejecutar` son
  llamadas distintas. Aprobar no dispara la gestión.
- **Alternativa:** que aprobar ejecute en el mismo movimiento, que es más cómodo para el
  analista (un clic en vez de dos).
- **Tradeoff:** se resigna comodidad. A cambio se gana lo que hay que poder demostrar: con
  los dos pasos separados, cualquiera puede pedir la ejecución de una propuesta pendiente
  y ver que el backend la rechaza con 403. Si aprobar ejecutara, ese pedido no existiría
  como operación y la garantía sería indemostrable desde afuera. **Además separa dos
  decisiones que son distintas en el negocio:** "esta acción es correcta" y "hacela ahora".
- **Nota para el PRD:** en producción la UI puede encadenar las dos llamadas en un solo
  botón sin tocar el backend. La separación es del contrato, no necesariamente de la
  experiencia.

### ADR-009 — Las excepciones del gate se traducen a HTTP en un solo lugar

- **Decisión:** un mapa de excepción a código de estado, registrado como manejadores de
  FastAPI. El bloqueo del gate es **403 Forbidden**; una transición imposible es 409; una
  acción fuera de la lista cerrada es 422; un id inexistente, 404; una falla del modelo, 502.
- **Alternativa:** que cada ruta atrape sus excepciones y arme su respuesta.
- **Tradeoff:** el mapa central es una indirección más para leer. A cambio, ninguna ruta
  puede olvidarse de traducir un bloqueo, y el rechazo del gate se ve idéntico venga del
  endpoint que venga. Se eligió 403 y no 409 porque describe exactamente lo que pasó: el
  pedido se entendió perfectamente y está **prohibido**.
- **Consecuencia buscada:** las rutas quedan sin lógica de control. `ejecutar()` es una
  línea que delega en `approval.ejecutar_accion()`. Si se borrara la ruta, el gate seguiría
  intacto.

### ADR-010 — Conteo agregado en la tool: la decisión que se difirió hasta medir

- **Hallazgo (Paso 3):** evaluando CLI-003, el agente escribió "3 no_pago y 4 tardío"
  cuando el historial tiene 3 `no_pago` y **5** `tardio`. La acción propuesta igual fue
  correcta, pero el razonamiento —que es lo que el analista lee para decidir— tenía un
  número mal.
- **Dato importante (Paso 4):** al volver a evaluar el mismo cliente desde la API, el
  agente contó bien ("3 no_pago y 5 tardio, con sólo 4 pagos a tiempo"). **El error es
  intermitente, no sistemático.** Esto confirma en la práctica lo dicho en ADR-002: la
  reproducibilidad es alta pero no bit-exacta, y una corrida sola no alcanza para
  caracterizar un modo de falla.
- **Mitigación candidata:** que `consultar_cliente` devuelva, además del historial mes a
  mes, el conteo agregado por estado. No le quita al agente la lectura del patrón —que es
  lo que se quiere evaluar— y le saca de encima una aritmética en la que se equivoca.
- **Estado en su momento: NO implementada a propósito.** Se decide en el Paso 6, con la medición sobre
  los 50 casos a la vista. Implementarla ahora borraría la evidencia del modo de falla
  antes de haberlo medido; el error también es material valioso de análisis.
- **CERRADO en el Paso 6.** Se midió: 1 error de conteo sobre 50 casos (2%), de baja
  frecuencia pero acompañando la única acción equivocada de la corrida. Se decidió
  implementarla. **Qué pasó al hacerlo: ver ADR-011** — funcionó para lo que apuntaba
  y refutó la hipótesis que la motivaba.

### ADR-011 — Mitigación del error de conteo: se implementó, y no arregló lo que se esperaba

- **Decisión:** `consultar_cliente` devuelve `resumen_del_historial` (los conteos por
  estado) **además** del historial mes a mes, que sigue entero. Se le saca de encima la
  aritmética, no la lectura del patrón. No hay score de riesgo ni tipo de pagador: eso
  sí sería darle la respuesta.
- **Qué se esperaba:** en la corrida base, el agente contó mal el historial de CLI-040 y
  sobre ese retrato inflado propuso una gestión demasiado blanda — el único fallo de la
  Dimensión 1. La hipótesis era que el error de conteo **causaba** la decisión equivocada.
- **Qué pasó al medir de nuevo los 50 casos:** los errores de conteo del historial
  desaparecieron (2 → 0), pero **la acción no cambió en ninguno de los 50 casos** y
  CLI-040 volvió a fallar, esta vez leyendo el historial correctamente. **La hipótesis
  era falsa.** Corregida la aritmética, la decisión no se movió.
- **Se deja implementada igual:** elimina una clase real de error factual en el
  razonamiento que el analista lee para decidir, aunque en este set no cambiara ninguna
  acción. El costo es una línea de datos más en la tool.
- **Hallazgo lateral, más valioso que la mitigación:** al leer el razonamiento ya
  correcto de CLI-040 se ve que el cliente tiene atrasos **antiguos** y seis meses
  recientes casi limpios. La rúbrica del eval lo clasifica como perfil "feo" contando
  atrasos totales **sin ponderar recencia**, mientras que el prompt le pide al agente
  exactamente lo contrario. Es probable que CLI-040 no sea un fallo del agente sino de
  la etiqueta. No se corrigió la rúbrica después de medir —eso invalidaría la
  medición— y queda anotado para la próxima iteración.
- **Nota para el PRD:** este ciclo —hipótesis, intervención, refutación— es el ejemplo
  más limpio del build de una decisión tomada con evidencia y no con intuición.

### ADR-012 — Los casos de escalamiento van en archivos separados

- **Decisión:** los 4 casos de la iteración 2 viven en `data/casos_escalamiento.json` y
  `evals/eval_set_escalamiento.json`, no dentro de `clientes.json` ni de `eval_set.json`.
  `tools.py` carga los dos archivos y los une.
- **Por qué:** nacieron **después** de medir, a partir del hallazgo de que el agente
  nunca escalaba. Meterlos en la cartera base cambiaría el eval base y rompería la
  comparación entre la corrida base y la mitigada, que se apoya en que los 50 casos sean
  exactamente los mismos.
- **Tensión con el ADR-003** (una sola fuente de verdad para la cartera): se acepta a
  conciencia. La separación acá no es desprolijidad sino trazabilidad — hace visible qué
  se midió antes y qué se agregó después. La estructura del repo ya preveía un segundo
  archivo de datos para casos curados.
- **Resultado:** el agente escaló en **4 de 4**. La respuesta a "¿prudente o incapaz?"
  es prudente. El defecto estaba en el eval, que durante 50 casos no supo distinguir
  una cosa de la otra.

---

## Oportunidades identificadas durante la validación

> Esta sección no documenta lo construido: junta material para que el PM lo tome en el
> PRD. Son cosas que se vieron **usando el prototipo**, no ideas de escritorio.

### OP-01 — Falta una etapa previa de priorización de cartera

- **Qué se vio:** en la PoC, el analista elige a mano de una lista qué cliente evaluar.
  Con 50 clientes se puede; con una cartera real de miles, no. Usando el prototipo quedó
  claro que **el problema del analista no es sólo "qué acción tomar con este cliente",
  sino "a quién atender primero"**. Hoy esa decisión es implícita y queda a criterio de
  quien mira la lista.
- **Qué faltaría:** una etapa de **priorización o pre-clasificación de la cartera**,
  anterior a la que resuelve este agente: ordenar o segmentar los casos por urgencia,
  recuperabilidad esperada o riesgo, y recién ahí entregarle al analista una cola de
  trabajo. El agente actual resolvería el "qué hacer" de cada caso que esa etapa priorice.
- **Por qué NO se construyó ahora — decisión deliberada de alcance, no un olvido:**
  el corazón de esta PoC es el gate de aprobación humana y la calidad de la propuesta por
  caso. Construir la priorización habría agregado una segunda pieza que compite por el
  foco y por el tiempo, y habría diluido lo que hay que demostrar. Se prefiere una pieza
  terminada y medida antes que dos a medias.
- **Adónde va:** al roadmap, como etapa siguiente natural del producto. Encaja como una
  fase previa en el mismo flujo, sin rehacer nada de lo construido: la priorización
  produce la cola, y este agente la procesa caso por caso.
- **Detectada:** Paso 5, probando el prototipo.

### OP-02 — La aprobación en dos pasos es fricción para el analista

- **Qué se vio:** usando la pantalla, aprobar y después ejecutar se siente como doble
  tarea. El analista ya decidió que la acción es correcta; tener que confirmar una
  segunda vez que además quiere que ocurra se percibe como un trámite, no como una
  decisión nueva. Sobre una cola de muchos casos por día, esa fricción se multiplica.
- **Decisión tomada — consciente y a favor de mostrar el mecanismo:** en la PoC los dos
  pasos quedan separados. Que aprobar y ejecutar sean operaciones distintas es
  exactamente el control que hay que demostrar: con `POST /aprobar` y `POST /ejecutar`
  como llamadas independientes, se puede pedir la ejecución de una propuesta pendiente y
  ver que el backend responde 403. Si aprobar ejecutara, ese pedido no existiría como
  operación y la garantía sería indemostrable desde afuera. **La PoC prioriza hacer
  visible el mecanismo por encima de pulir la experiencia.**
- **Cómo se resuelve en producción, sin tocar la garantía:** un solo botón de cara al
  analista, con las dos llamadas encadenadas por código por debajo. La separación es del
  **contrato de la API**, no necesariamente de la experiencia. `ejecutar_accion()` sigue
  verificando la aprobación igual que hoy: lo que cambia es cuántos clics hace el
  humano, no qué verifica el código. La garantía es idéntica en los dos casos.
- **Detectada:** Paso 5, probando el prototipo. Ver también el ADR-008, que registra la
  decisión técnica de separar los endpoints.

---

## Producto

El **`PRD.md`** y el pitch de producto **los redacta el PM por fuera de este build**: la
elección del caso, el alcance, los requisitos priorizados, el business case, el roadmap y el
Go/No-Go dependen de criterio de producto y de los resultados finales.

Lo que este build deja como insumo: los 12 ADRs y las dos oportunidades de arriba, y la
medición completa con su análisis de errores en [`evals/results.md`](evals/results.md).

---

## Intercambios con la IA

En [`ai_interactions/`](ai_interactions/):

- **`sesion_completa.md`** — la sesión entera, en orden, con los mensajes íntegros y cada
  llamada a herramienta resumida en una línea.
- **`sesion_completa.jsonl`** — el volcado crudo de Claude Code, copiado sin editar.
- **`exportar_sesion.py`** — el exportador, para que se vea que el volcado es mecánico y no
  una selección editorial.
- **`candidatos.md`** — los tres momentos que pide el ejercicio, pre-localizados con cita y
  número de línea.
- **`interactions.md`** — el entregable final, que cura el PM.
