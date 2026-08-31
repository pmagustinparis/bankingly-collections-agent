"""
EL HARNESS: el loop, el llamado al modelo, y la propuesta que sale hacia el gate.

Escrito a mano y no con un framework de agentes, a propósito. En un sistema donde lo
que hay que demostrar es dónde vive el control, el loop tiene que poder leerse entero
y señalarse con el dedo. Un framework escondería justamente lo que hay que mostrar.

Dónde aparece el modelo en todo esto: en dos momentos, y sólo dos.
  - pide los datos (decide consultar);
  - razona y propone una acción.
Todo lo demás —cargar el caso, ejecutar la tool, validar la acción contra la lista
cerrada, registrar la propuesta en el gate— es código.

Lo que el modelo NO puede hacer, por construcción: aprobar, ejecutar, inventar una
acción fuera de la lista, o ver la etiqueta de evaluación del caso.
"""

import json
import os
from typing import Optional

import anthropic
from dotenv import load_dotenv

import approval
import tools
from models import ACCIONES_PERMITIDAS, Propuesta, es_accion_permitida

load_dotenv()

# ---------------------------------------------------------------------------
# Configuración del modelo
# ---------------------------------------------------------------------------

MODELO = os.getenv("ANTHROPIC_MODEL", "claude-opus-5")

# Palanca de reproducibilidad de los evals (ver ADR-002 del README): los modelos
# actuales ya no aceptan `temperature`, así que la estabilidad se busca con un
# esfuerzo de razonamiento bajo y constante, prompt fijo y datos fijos.
ESFUERZO = os.getenv("ANTHROPIC_EFFORT", "low")

MAX_TOKENS = 8000  # el razonamiento del modelo también consume de acá
MAX_TURNOS = 6  # tope de seguridad: la trayectoria real son 2 turnos


# ---------------------------------------------------------------------------
# EL PROMPT DEL SISTEMA
#
# Le damos al agente el MARCO DE NEGOCIO —principios de juicio— y no un árbol de
# decisión. Nada de "si el atraso es menor a 7 días, recordatorio": eso sería un
# if disfrazado de agente, y no haría falta un modelo para ejecutarlo.
#
# La contracara, asumida: con principios el agente es menos predecible que una
# regla. Eso no es un defecto del diseño, es el motivo por el cual existe el gate.
# Si el agente fuera perfectamente predecible, la aprobación humana sobraría.
#
# Lo que este prompt deliberadamente NO dice: la categoría del caso, umbrales
# numéricos, y cualquier pista sobre qué espera el eval.
# ---------------------------------------------------------------------------

PROMPT_DEL_SISTEMA = f"""\
Sos un asistente de cobranza temprana en una institución financiera de LATAM.
Trabajás para un analista de cobranzas de la institución, no para el cliente final.

Tu tarea es analizar la situación de un cliente con atraso reciente y PROPONER la
mejor acción de gestión. Tu propuesta no se ejecuta sola: un analista humano la
revisa y decide si aprobarla, corregirla o descartarla. Proponé con criterio y
explicá por qué, para que esa persona pueda evaluarlo rápido.

El objetivo del negocio es recuperar el pago sin dañar la relación con el cliente.
Las dos cosas importan: cobrar hoy a costa de perder al cliente es un mal negocio.

# Principios para decidir

No son reglas mecánicas. Son el criterio del oficio; el caso concreto manda.

- No todos los atrasos son iguales. La acción correcta depende del contexto
  individual del cliente, no de los días de atraso mirados por separado.
- Un historial de pagos sólido sugiere un olvido puntual y amerita un trato suave.
  Tratar con dureza a un buen cliente por un descuido daña una relación que costó
  años construir y que es cara de recuperar.
- Un patrón de atrasos repetidos sugiere más firmeza. Quien ya mostró
  incumplimiento sostenido necesita una gestión distinta de quien falló una vez.
- La firmeza sube con el nivel de riesgo, pero el respeto al cliente no baja nunca.
- El monto modula la gestión. Una exposición grande amerita más cuidado aunque el
  comportamiento sea bueno; una deuda menor no justifica una gestión costosa ni
  fricción con el cliente, porque gestionarla puede salir más caro que la deuda.
- La antigüedad también modula. Con un cliente nuevo hay poca historia sobre la
  cual concluir: ante poca evidencia corresponde prudencia, sin dureza infundada
  y sin aparentar una certeza que los datos no respaldan.
- Estás en mora TEMPRANA. Se trata de actuar a tiempo para que el atraso no se
  agrave, cuando todavía es barato y la relación está intacta.

# Acciones disponibles

Podés proponer una y sólo una de estas tres. No existen otras acciones y no debés
inventar ninguna:

- `recordatorio`: contactar al cliente para recordarle el pago, con un tono
  determinado que vos sugerís.
- `plan_de_pago`: ofrecerle refinanciar la deuda en cuotas.
- `escalar`: derivar la gestión a un nivel superior de cobranza.

# Cómo trabajar

1. SIEMPRE consultá los datos del cliente con la tool `consultar_cliente` antes de
   proponer nada. Nunca propongas sin haber mirado los datos.
2. Leé el historial de pagos como un patrón, no como una cuenta de incidentes:
   importa cuántos son, pero también si son viejos o recientes, si están dispersos
   o agrupados, y si la conducta cambió en los últimos meses.
3. Proponé UNA sola acción, la que mejor resuelva este caso.
4. Justificá con los datos concretos del cliente. Un razonamiento que serviría
   igual para cualquier otro cliente no le sirve al analista para decidir.
5. Si el caso es genuinamente dudoso, decilo en el razonamiento en lugar de fingir
   seguridad. El analista necesita saber cuándo mirar con más atención.

Respondé con la acción propuesta, tu razonamiento, y el tono sugerido para la
gestión (en `escalar`, el tono con el que conviene encuadrar la derivación).
"""


# La forma exacta de la respuesta, impuesta por la API y no pedida por favor en el
# prompt. El enum sale de ACCIONES_PERMITIDAS: una sola fuente de verdad para la
# lista cerrada, la misma que valida el gate.
FORMATO_DE_LA_PROPUESTA = {
    "type": "json_schema",
    "schema": {
        "type": "object",
        "properties": {
            "accion": {
                "type": "string",
                "enum": list(ACCIONES_PERMITIDAS),
                "description": "La acción propuesta.",
            },
            "razonamiento": {
                "type": "string",
                "description": (
                    "Por qué esta acción para este cliente, apoyado en sus datos concretos."
                ),
            },
            "tono_sugerido": {
                "type": "string",
                "description": "Con qué tono conviene hacer la gestión.",
            },
        },
        "required": ["accion", "razonamiento", "tono_sugerido"],
        "additionalProperties": False,
    },
}


class ExcepcionDelAgente(Exception):
    """El agente no pudo producir una propuesta utilizable."""


def _anotar(traza: Optional[list], paso: str) -> None:
    """Registra un paso de la trayectoria, si quien llama pidió seguirla."""
    if traza is not None:
        traza.append(paso)


def evaluar_caso(cliente_id: str, traza: Optional[list] = None) -> Propuesta:
    """
    Evalúa un caso de punta a punta y deja la propuesta RETENIDA en el gate.

    Devuelve la propuesta en estado `pendiente_de_aprobacion`. Nunca ejecuta nada:
    para que algo pase hace falta que una persona apruebe, y eso vive en approval.py.
    """
    cliente = anthropic.Anthropic()  # lee ANTHROPIC_API_KEY del entorno

    # Paso 1 (código): se arma el caso. Fijate que NO se le pasan los datos del
    # cliente al modelo: se le pasa el id y los datos los tiene que ir a buscar.
    # Eso es lo que hace que la trayectoria sea real y medible.
    mensajes = [{
        "role": "user",
        "content": f"Evaluá el caso del cliente {cliente_id} y proponé una acción de gestión.",
    }]
    _anotar(traza, f"caso creado para {cliente_id} (sin datos servidos)")

    consulto_datos = False
    respuesta = None

    for turno in range(MAX_TURNOS):
        respuesta = cliente.messages.create(
            model=MODELO,
            max_tokens=MAX_TOKENS,
            system=PROMPT_DEL_SISTEMA,
            tools=tools.ESQUEMA_DE_TOOLS,
            output_config={"effort": ESFUERZO, "format": FORMATO_DE_LA_PROPUESTA},
            messages=mensajes,
        )

        if respuesta.stop_reason != "tool_use":
            break

        # Paso 3 (código): el harness ejecuta la tool. El modelo pide; no accede
        # a los datos por su cuenta.
        bloques_de_tool = [b for b in respuesta.content if b.type == "tool_use"]
        mensajes.append({"role": "assistant", "content": respuesta.content})

        resultados = []
        for bloque in bloques_de_tool:
            contenido, es_error = tools.ejecutar_tool(bloque.name, dict(bloque.input))
            if bloque.name == "consultar_cliente" and not es_error:
                consulto_datos = True
            _anotar(traza, f"turno {turno + 1}: el modelo pidió {bloque.name}"
                           f"({dict(bloque.input)}){' -> ERROR' if es_error else ''}")
            resultados.append({
                "type": "tool_result",
                "tool_use_id": bloque.id,
                "content": contenido,
                "is_error": es_error,
            })
        mensajes.append({"role": "user", "content": resultados})
    else:
        raise ExcepcionDelAgente(
            f"El agente no cerró una propuesta para {cliente_id} en {MAX_TURNOS} turnos."
        )

    # Paso 4 (modelo): la propuesta viene en el bloque de texto final, con la forma
    # que impuso el schema.
    propuesta_cruda = _leer_propuesta(respuesta, cliente_id)
    _anotar(traza, f"turno final: el modelo propuso '{propuesta_cruda['accion']}'")

    # Paso 5 (código): EL GUARDRAIL. Aunque el schema ya restringe el enum, se
    # revalida acá: la lista cerrada la hace cumplir el código, no la confianza
    # en que la API haya respetado el formato.
    if not es_accion_permitida(propuesta_cruda["accion"]):
        raise ExcepcionDelAgente(
            f"El agente propuso '{propuesta_cruda['accion']}', que no está en la "
            f"lista cerrada {ACCIONES_PERMITIDAS}."
        )

    propuesta = Propuesta(
        cliente_id=cliente_id,
        accion=propuesta_cruda["accion"],
        razonamiento=propuesta_cruda["razonamiento"],
        tono_sugerido=propuesta_cruda["tono_sugerido"],
        # Se registra tal cual pasó. Si el agente propuso sin consultar, queda
        # asentado y el analista lo ve: no se corrige por atrás. Si el harness lo
        # tapara, la Dimensión 4 del eval mediría al harness y no al agente.
        consulto_datos=consulto_datos,
    )

    # Paso 6 (código): EL GATE. La propuesta queda retenida esperando a un humano.
    return approval.registrar_propuesta(propuesta)


def _leer_propuesta(respuesta, cliente_id: str) -> dict:
    """Extrae el JSON de la propuesta del último mensaje del modelo."""
    if respuesta.stop_reason == "refusal":
        raise ExcepcionDelAgente(f"El modelo declinó evaluar el caso {cliente_id}.")

    if respuesta.stop_reason == "max_tokens":
        raise ExcepcionDelAgente(
            f"La respuesta para {cliente_id} se cortó por MAX_TOKENS ({MAX_TOKENS}): "
            f"el JSON llegaría incompleto. Subí MAX_TOKENS."
        )

    texto = next((b.text for b in respuesta.content if b.type == "text"), None)
    if texto is None:
        raise ExcepcionDelAgente(f"El modelo no devolvió una propuesta para {cliente_id}.")

    try:
        return json.loads(texto)
    except json.JSONDecodeError as e:
        raise ExcepcionDelAgente(
            f"La propuesta para {cliente_id} no vino en JSON válido: {e}"
        ) from e
