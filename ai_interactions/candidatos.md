# Candidatos para los tres momentos — material para curar

El ejercicio pide **tres momentos copiados tal cual**: (a) el prompt que produjo la
pieza más importante del prototipo, (b) el intercambio donde el modelo devolvió algo
incorrecto y cómo se detectó, y (c) el momento en que se cambió de enfoque.

Este archivo **no es el entregable**: es el índice para armarlo. Cada candidato apunta
a la línea exacta de `sesion_completa.md`, con una cita corta para reconocerlo. El
archivo final se cura en `interactions.md`.

Hay más de un candidato por categoría a propósito: son de naturaleza distinta y la
elección cambia qué historia se cuenta.

---

## (a) El prompt que produjo la pieza más importante

### A1 — El pedido del gate ⭐ *el más fuerte*

`sesion_completa.md`, **línea 377** · turno del usuario del 2026-08-30 22:30:30

> Avancemos al Paso 2: models.py + approval.py (el gate), juntos y antes del agente.
> Releé ESPEC_AGENTE.md antes de arrancar, sobre todo la sección del gate. Recordá que
> este es el corazón del proyecto: el gate va aislado en approval.py, con la guarda
> dura (si no está aprobada, no se ejecuta y se levanta una excepción), y tiene que
> poder señalarse en una pantalla y explicarse solo.
>
> Cuando termines, quiero que hagas dos cosas: (1) mostrame el código de models.py y
> approval.py para revisarlo, y (2) probá el gate en soledad con una propuesta falsa
> (sin agente todavía) y mostrame que rechaza la ejecución si no hay aprobación.

**Por qué es el más fuerte:** es el prompt de la pieza central del proyecto y muestra
tres cosas de cómo se dirigió la herramienta — *orden de construcción* (el gate antes
del agente, para que todo se construya alrededor del control), *criterio de calidad*
("señalable en una pantalla y explicarse solo") y *verificación exigida por
adelantado* ("probá el gate en soledad… mostrame que rechaza"). No pide código: pide
código **más su demostración**.

La respuesta produjo `approval.py` con la guarda dura y `probar_gate.py`, y de ahí
salió el escenario 7 (la propuesta impostora que se auto-declara aprobada y el gate
igual la bloquea porque consulta el repositorio). Ese escenario es el que se muestra
en la sesión.

### A2 — El pedido del harness

`sesion_completa.md`, **línea 529** · turno del 2026-08-30 22:46:11

> Vamos al Paso 3, el agent.py. […] el agente pide los datos con la tool
> consultar_cliente, razona sobre principios de negocio y no sobre reglas rígidas,
> propone una sola acción de la lista cerrada con su justificación, y la propuesta
> queda retenida en el gate. El modelo propone, el código dispone.

Alternativa válida si se prefiere mostrar el prompt que produjo el agente en sí. Más
débil que A1 para el criterio 2 de la sesión, más fuerte para el criterio 3.

---

## (b) El modelo devolvió algo incorrecto y cómo se detectó

Tres candidatos, y **son de tres tipos distintos**. Vale elegir según qué se quiera
mostrar.

### B1 — El error de conteo del agente, detectado verificando contra los datos

`sesion_completa.md`, **líneas 801-805 y 835** · Paso 3, 2026-08-30 23:13

Lo que el agente escribió sobre CLI-003:

> en los últimos 12 meses cerrados hay 3 'no_pago' y 4 'tardío'

La detección:

> **Pero cometió un error factual.** Dice "3 'no_pago' y 4 'tardío'". Lo verifiqué
> contra los datos: son **3 no_pago y 5 tardío** (4 es la cantidad de `a_tiempo` —
> parece haber cruzado las cuentas). El caso es aún peor de lo que el agente describió,
> así que no cambia la acción, pero importa: el razonamiento es lo que el analista lee
> para decidir, y tiene un número mal.

**Qué muestra:** que la verificación fue *contra la fuente*, no a ojo. El error no
cambiaba la acción propuesta, así que era fácil dejarlo pasar. Tiene continuación: en
el Paso 4 el mismo caso se contó bien (**línea 959**), lo que probó que el error era
**intermitente** y que una sola corrida no alcanza para caracterizar un modo de falla.

### B2 — El 403 que parpadeaba: lo detectó el usuario, no el modelo ⭐ *el más honesto*

`sesion_completa.md`, **línea 1132** (reporte del usuario) y **línea 1222** (el
diagnóstico) · Paso 5, 2026-08-31 00:19

El reporte:

> Cuando aprieto "intentar ejecutar sin aprobar (demo)", el mensaje del 403 aparece un
> microsegundo en la franja negra y desaparece. […] Necesito que ese 403 quede fijo y
> visible en pantalla, no que parpadee: es la demostración central del control por
> código.

El diagnóstico:

> `refrescarPropuestas()` usaba el mismo `llamar()`, que **escribía su propio
> `HTTP 200` encima del 403**. Por eso lo veías un microsegundo: el 403 llegaba a
> pintarse y el refresco de la bandeja lo tapaba de inmediato.

**Por qué es el más honesto de los tres:** este bug **no lo detectó el modelo**. En el
turno anterior se había afirmado que el frontend estaba verificado, sin haberlo abierto
en un navegador. Lo encontró el humano usándolo. La respuesta incluye reconocerlo
("la vez pasada afirmé algo del front sin probarlo y se me escapó justo este bug") y
construir una verificación real —un DOM simulado en Node para correr el `app.js`
verdadero— en vez de volver a afirmar sin probar. Si se quiere mostrar el límite de
confiar en lo que la herramienta dice de sí misma, es este.

### B3 — La validación que existía sólo en el placeholder de un input

`sesion_completa.md`, **líneas 1019 y 1108** · Paso 5

> Probando el flujo descubrí que **rechazar con motivo vacío devolvía HTTP 200**. El
> backend no lo validaba, y mi comentario en el front afirmaba que sí — o sea, la
> obligatoriedad del motivo existía sólo en el placeholder de un input.

**Qué muestra:** un caso donde el código generado **se contradecía con su propio
comentario**. El comentario afirmaba una garantía que no existía. Se detectó probando
el endpoint con `curl`, no leyendo el código — que es la lección: los comentarios no
son evidencia.

---

## (c) El momento en que se cambió de enfoque

### C1 — La mitigación que se implementó y no funcionó ⭐ *el más fuerte*

`sesion_completa.md`, **líneas 1661 (la hipótesis) → 1700 (la decisión) → 1897-1903
(la refutación)** · Pasos 6, 2026-08-31 02:48 en adelante

La hipótesis, en la corrida base:

> ## Hallazgo 2 — Un error de conteo causó la única acción equivocada
> […] **El error factual no fue cosmético: fue la causa de la decisión equivocada.**

La intervención pedida:

> Implementá la mitigación del error de conteo […] Es barata y ataca la causa directa
> del único fallo real de la corrida.

El resultado, después de volver a correr los 50 casos:

> **Pero mi hipótesis era falsa.** CLI-040 volvió a fallar. Con los conteos servidos
> leyó el historial **correctamente** […] y aun así propuso `recordatorio`. Cero
> cambios de acción en 50 casos.
>
> En la corrida base afirmé que el error de conteo **causaba** la decisión equivocada.
> Corregida la aritmética, la decisión no se movió. **Acompañaba, no causaba.**

Y el hallazgo lateral que apareció al mirar el razonamiento ya correcto:

> Mi rúbrica lo clasifica como perfil "feo" contando atrasos totales, **sin ponderar
> recencia** — mientras el prompt le pide al agente exactamente lo contrario […] **el
> agente hizo lo que el prompt le pidió, y la rúbrica lo penalizó por hacerlo.**

**Por qué es el más fuerte:** es un ciclo completo de hipótesis → intervención →
refutación → reencuadre, con la conclusión reportada en contra de lo que convenía. El
cambio de enfoque no es de herramienta sino **de explicación**: se abandonó una causa
cómoda que la evidencia no sostenía, y el defecto terminó estando en el instrumento de
medición y no en el agente.

### C2 — La especificación que envejeció: de `temperature` a `effort`

`sesion_completa.md`, **líneas 225-227** · Paso 0, 2026-08-30 22:22

> **1. La especificación pide "temperatura fija y baja" — y eso ya no se puede hacer.**
>
> Los modelos actuales de Anthropic (familia Claude 5, y Opus 4.7/4.8) **eliminaron el
> parámetro `temperature`**: mandarlo devuelve un HTTP 400. La instrucción de
> `CLAUDE.md` y `ESPEC_AGENTE.md` envejeció respecto de la API.

**Qué muestra:** una instrucción del briefing que era literalmente inejecutable, y la
decisión de conservar su **intención** (evals reproducibles) por encima de su letra,
registrada como ADR-002 con el tradeoff explícito. Es un cambio de enfoque temprano y
de otra naturaleza que C1: acá el problema estaba en la especificación, no en el
razonamiento.

### C3 — El eval que se corrigió a sí mismo

`sesion_completa.md`, **línea 1694 en adelante** · Paso 6

El punto ciego de la rúbrica (que ningún caso obligaba a elegir entre `plan_de_pago` y
`escalar`, con lo cual un agente que jamás escala puntuaba igual que uno que calibra
bien), y la iteración 2 que nació de ahí para responder si el agente era **prudente o
incapaz**. Resultado: 4 de 4 escaló, o sea prudente — y el defecto era del eval.

Sirve si se prefiere mostrar el cambio de enfoque **sobre el instrumento de medición**
en vez de sobre una hipótesis causal.

---

## Sugerencia de combinación

Si se eligen **A1 + B2 + C1**, los tres momentos cuentan una historia coherente y sin
autoindulgencia: se dirigió bien la pieza central pidiendo demostración además de
código; la herramienta afirmó estar verificada cuando no lo estaba y lo encontró el
humano; y una hipótesis propia se cayó al probarla y se reportó igual.

Si se prefiere mostrar más verificación técnica y menos error propio, **A1 + B1 + C2**
es la combinación más conservadora.
