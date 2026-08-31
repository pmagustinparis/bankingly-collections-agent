"""
EL GATE DE APROBACIÓN HUMANA. El corazón de este proyecto.

Regla que gobierna todo el sistema: el modelo PROPONE, el código DISPONE.

Ninguna acción con efectos se ejecuta sin que un humano la haya aprobado. Esa
garantía no está en el prompt —donde sería una sugerencia que el modelo puede
ignorar— sino acá, en una condición de código que nadie puede sortear:

        if not propuesta.aprobada:
            raise ExcepcionAprobacionRequerida(...)

Tres decisiones de diseño hacen que esa guarda sea de verdad el único portón:

  1. El efecto con consecuencias vive en `_ejecutar_efecto_simulado()`, una función
     privada de este módulo. No es importable desde ningún otro archivo sin violar
     la convención del guion bajo, y nadie más la llama. Para provocar el efecto hay
     que pasar por `ejecutar_accion()`, y `ejecutar_accion()` siempre chequea.

  2. `ejecutar_accion()` recibe un `propuesta_id`, no un objeto Propuesta, y busca
     el estado en el repositorio. Si recibiera un objeto, cualquiera podría fabricar
     uno con `estado=APROBADA` y saltearse la aprobación. Al buscarlo, la única
     verdad sobre si algo está aprobado es la que guarda este módulo.

  3. El estado sólo cambia por las funciones de este archivo, y `aprobar()` es la
     única que lleva a APROBADA. El modelo no puede llamarla: el modelo devuelve
     texto, y el harness lo convierte en una Propuesta que nace PENDIENTE.
"""

from typing import Optional

from models import (
    EstadoDePropuesta,
    Propuesta,
    ahora_utc,
    es_accion_permitida,
)


# ---------------------------------------------------------------------------
# Excepciones
# ---------------------------------------------------------------------------

class ExcepcionAprobacionRequerida(Exception):
    """Se intentó ejecutar una acción que ningún humano aprobó."""


class ExcepcionTransicionInvalida(Exception):
    """Se intentó un cambio de estado que el ciclo de vida no permite."""


class ExcepcionAccionNoPermitida(Exception):
    """Se intentó usar una acción fuera de la lista cerrada."""


class ExcepcionPropuestaInexistente(Exception):
    """No hay ninguna propuesta registrada con ese id."""


# ---------------------------------------------------------------------------
# Repositorio de propuestas y bitácora
#
# En memoria, a propósito: es una PoC y persistir no agrega nada a lo que hay que
# demostrar. Para productizar esto se reemplaza por una base de datos sin tocar la
# lógica del gate, porque todo el acceso pasa por las funciones de abajo.
# ---------------------------------------------------------------------------

_PROPUESTAS: dict[str, Propuesta] = {}
_BITACORA: list[dict] = []


def _registrar_en_bitacora(evento: str, propuesta: Propuesta, detalle: str = "") -> None:
    """Deja rastro auditable de cada paso: qué pasó, con qué propuesta y cuándo."""
    _BITACORA.append({
        "momento": ahora_utc(),
        "evento": evento,
        "propuesta_id": propuesta.propuesta_id,
        "cliente_id": propuesta.cliente_id,
        "accion": propuesta.accion,
        "estado": propuesta.estado.value,
        "detalle": detalle,
    })


def obtener_bitacora() -> list[dict]:
    """El registro auditable completo, en orden cronológico."""
    return list(_BITACORA)


def obtener_propuesta(propuesta_id: str) -> Propuesta:
    if propuesta_id not in _PROPUESTAS:
        raise ExcepcionPropuestaInexistente(f"No existe la propuesta {propuesta_id}")
    return _PROPUESTAS[propuesta_id]


def listar_propuestas(estado: Optional[EstadoDePropuesta] = None) -> list[Propuesta]:
    """Todas las propuestas, o sólo las de un estado. Es lo que consume el frontend."""
    propuestas = list(_PROPUESTAS.values())
    if estado is not None:
        propuestas = [p for p in propuestas if p.estado is estado]
    return propuestas


def limpiar_repositorio() -> None:
    """Vacía el estado. Sólo para pruebas y para correr los evals desde cero."""
    _PROPUESTAS.clear()
    _BITACORA.clear()


# ---------------------------------------------------------------------------
# El ciclo de vida de una propuesta
# ---------------------------------------------------------------------------

def registrar_propuesta(propuesta: Propuesta) -> Propuesta:
    """
    Entrada al gate. Toda propuesta del agente pasa por acá y queda RETENIDA.

    Nace `pendiente_de_aprobacion` sí o sí: este es el único modo de meter una
    propuesta al sistema, y no acepta un estado inicial distinto.
    """
    if not es_accion_permitida(propuesta.accion):
        raise ExcepcionAccionNoPermitida(
            f"'{propuesta.accion}' no está en la lista cerrada de acciones"
        )

    propuesta.estado = EstadoDePropuesta.PENDIENTE_DE_APROBACION
    _PROPUESTAS[propuesta.propuesta_id] = propuesta
    _registrar_en_bitacora("propuesta_registrada", propuesta,
                           f"el agente propuso '{propuesta.accion}'")
    return propuesta


def aprobar(propuesta_id: str, analista: str,
            comentario: Optional[str] = None) -> Propuesta:
    """
    LA ÚNICA FUNCIÓN DEL SISTEMA QUE LLEVA UNA PROPUESTA A `aprobada`.

    La dispara una persona desde la API. El modelo no tiene forma de llegar acá:
    el modelo produce texto, no llamadas a funciones de Python.
    """
    propuesta = obtener_propuesta(propuesta_id)
    _exigir_estado(propuesta, EstadoDePropuesta.PENDIENTE_DE_APROBACION, "aprobar")

    propuesta.estado = EstadoDePropuesta.APROBADA
    propuesta.decidida_por = analista
    propuesta.decidida_en = ahora_utc()
    propuesta.comentario_del_analista = comentario
    _registrar_en_bitacora("aprobada", propuesta, f"aprobada por {analista}")
    return propuesta


def aprobar_con_modificacion(propuesta_id: str, analista: str, nueva_accion: str,
                             comentario: Optional[str] = None) -> Propuesta:
    """
    El analista cambia la acción propuesta y recién ahí la aprueba.

    La acción del humano también se valida contra la lista cerrada: el gate no
    confía en el modelo, pero tampoco deja que la UI mande cualquier cosa.
    Se conserva qué había propuesto el agente, para poder medir después en qué
    difiere el criterio del agente del criterio del analista.
    """
    if not es_accion_permitida(nueva_accion):
        raise ExcepcionAccionNoPermitida(
            f"'{nueva_accion}' no está en la lista cerrada de acciones"
        )

    propuesta = obtener_propuesta(propuesta_id)
    _exigir_estado(propuesta, EstadoDePropuesta.PENDIENTE_DE_APROBACION, "modificar")

    propuesta.accion_propuesta_originalmente = propuesta.accion
    propuesta.accion = nueva_accion
    propuesta.estado = EstadoDePropuesta.APROBADA
    propuesta.decidida_por = analista
    propuesta.decidida_en = ahora_utc()
    propuesta.comentario_del_analista = comentario
    _registrar_en_bitacora(
        "aprobada_con_modificacion", propuesta,
        f"{analista} cambió '{propuesta.accion_propuesta_originalmente}' por '{nueva_accion}'",
    )
    return propuesta


def rechazar(propuesta_id: str, analista: str, motivo: str) -> Propuesta:
    """El analista descarta la propuesta. Estado terminal: de acá no se ejecuta nada."""
    propuesta = obtener_propuesta(propuesta_id)
    _exigir_estado(propuesta, EstadoDePropuesta.PENDIENTE_DE_APROBACION, "rechazar")

    propuesta.estado = EstadoDePropuesta.RECHAZADA
    propuesta.decidida_por = analista
    propuesta.decidida_en = ahora_utc()
    propuesta.comentario_del_analista = motivo
    _registrar_en_bitacora("rechazada", propuesta, f"rechazada por {analista}: {motivo}")
    return propuesta


# ---------------------------------------------------------------------------
# EL PORTÓN
# ---------------------------------------------------------------------------

def ejecutar_accion(propuesta_id: str) -> Propuesta:
    """
    El único camino del sistema hacia una acción con efectos.

    Recibe un id y busca el estado real en el repositorio, en vez de creerle a un
    objeto que le pasen: así nadie puede fabricar una propuesta que "diga" estar
    aprobada. Si no está aprobada, no se ejecuta y se levanta la excepción.
    """
    propuesta = obtener_propuesta(propuesta_id)

    # Una acción aprobada se ejecuta UNA vez. Sin esto, repetir el llamado volvería
    # a disparar el efecto: en cobranza, molestar al mismo cliente dos veces.
    if propuesta.estado is EstadoDePropuesta.EJECUTADA:
        _registrar_en_bitacora("ejecucion_bloqueada", propuesta, "ya había sido ejecutada")
        raise ExcepcionTransicionInvalida(
            f"La propuesta {propuesta_id} ya fue ejecutada el {propuesta.ejecutada_en}."
        )

    # ─── LA GUARDA DURA ─────────────────────────────────────────────────────
    if not propuesta.aprobada:
        _registrar_en_bitacora("ejecucion_bloqueada", propuesta,
                               f"se intentó ejecutar en estado '{propuesta.estado.value}'")
        raise ExcepcionAprobacionRequerida(
            f"No se puede ejecutar la propuesta {propuesta_id}: "
            f"su estado es '{propuesta.estado.value}' y se requiere aprobación humana."
        )
    # ────────────────────────────────────────────────────────────────────────

    resultado = _ejecutar_efecto_simulado(propuesta)

    propuesta.estado = EstadoDePropuesta.EJECUTADA
    propuesta.ejecutada_en = ahora_utc()
    propuesta.resultado_de_ejecucion = resultado
    _registrar_en_bitacora("ejecutada", propuesta, resultado)
    return propuesta


def _ejecutar_efecto_simulado(propuesta: Propuesta) -> str:
    """
    La acción con efectos. Privada a propósito: nadie la llama salvo el portón.

    En la PoC el efecto es simulado (devuelve una descripción). En producción, acá
    adentro es donde se dispararía el envío real, el alta del plan de pago o el
    ticket de escalamiento — y seguiría estando detrás de la misma guarda.
    """
    efectos = {
        "recordatorio": "Recordatorio enviado al cliente",
        "plan_de_pago": "Oferta de plan de pago cursada al cliente",
        "escalar": "Caso derivado a gestión de cobranza avanzada",
    }
    return f"[SIMULADO] {efectos[propuesta.accion]} ({propuesta.cliente_id})"


def _exigir_estado(propuesta: Propuesta, estado_esperado: EstadoDePropuesta,
                   operacion: str) -> None:
    """
    Hace cumplir el ciclo de vida: pendiente → aprobada|rechazada → ejecutada.

    Sin esto se podría aprobar algo ya rechazado, o ejecutar dos veces la misma
    acción — que en cobranza significa molestar al cliente dos veces.
    """
    if propuesta.estado is not estado_esperado:
        raise ExcepcionTransicionInvalida(
            f"No se puede {operacion} la propuesta {propuesta.propuesta_id}: "
            f"su estado es '{propuesta.estado.value}' y se esperaba "
            f"'{estado_esperado.value}'."
        )
