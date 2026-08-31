"""
Las tools que el modelo puede pedir usar.

Hay una sola: `consultar_cliente`. Alcanza para la trayectoria de este agente y no
hay motivo para inventar más — una tool decorativa sería ruido en el harness.

Regla que este módulo hace cumplir: el agente razona sobre DATOS CRUDOS. No se le
entrega un score de riesgo ni un "tipo de pagador" masticado; se le da el historial
mes a mes y el contexto, y el patrón lo tiene que leer él. Darle la conclusión
servida invalidaría lo que se quiere demostrar.
"""

import json
from pathlib import Path

from models import Cliente

CARPETA_DE_DATOS = Path(__file__).resolve().parent.parent / "data"
ARCHIVO_DE_CLIENTES = CARPETA_DE_DATOS / "clientes.json"

# Los casos de escalamiento son la iteración 2 del eval, nacida de un hallazgo de la
# corrida base. Viven en su propio archivo y no dentro de `clientes.json` a propósito:
# la cartera base quedó congelada antes de la primera medición, y mezclarlos ahí
# rompería la comparación entre la corrida base y la mitigada.
ARCHIVO_DE_CASOS_DE_ESCALAMIENTO = CARPETA_DE_DATOS / "casos_escalamiento.json"


def _cargar_cartera() -> dict[str, dict]:
    """Levanta la cartera una vez y la indexa por id."""
    registros = json.loads(ARCHIVO_DE_CLIENTES.read_text(encoding="utf-8"))
    if ARCHIVO_DE_CASOS_DE_ESCALAMIENTO.exists():
        registros += json.loads(
            ARCHIVO_DE_CASOS_DE_ESCALAMIENTO.read_text(encoding="utf-8")
        )
    return {registro["cliente_id"]: registro for registro in registros}


_CARTERA = _cargar_cartera()


def consultar_cliente(cliente_id: str) -> dict:
    """
    Devuelve el perfil completo de un cliente de la cartera.

    Lo que NO devuelve: el campo `arquetipo`. Esa etiqueta es metadata de evaluación
    y mostrársela al modelo sería darle la respuesta. No hace falta acordarse de
    filtrarla: `Cliente.desde_registro()` sólo copia los campos del dominio, así que
    la etiqueta se cae por construcción.
    """
    if cliente_id not in _CARTERA:
        raise ClienteInexistente(f"No existe el cliente {cliente_id} en la cartera")
    return Cliente.desde_registro(_CARTERA[cliente_id]).como_dict()


def listar_clientes() -> list[dict]:
    """Cartera completa, sin etiquetas. La usa la API para poblar la pantalla."""
    return [Cliente.desde_registro(r).como_dict() for r in _CARTERA.values()]


class ClienteInexistente(Exception):
    """El id pedido no está en la cartera."""


# ---------------------------------------------------------------------------
# La definición que viaja a la API del modelo
# ---------------------------------------------------------------------------

# La descripción explica la SEMÁNTICA de los datos, no cómo decidir. Que el historial
# sean meses cerrados y que el atraso de hoy no esté ahí adentro es información que el
# modelo necesita para no contar dos veces la misma mora; no es una regla de decisión.
ESQUEMA_DE_TOOLS = [
    {
        "name": "consultar_cliente",
        "description": (
            "Devuelve el perfil de un cliente de la cartera de cobranza.\n\n"
            "Campos que devuelve:\n"
            "- tipo_de_producto: 'prestamo_personal' o 'tarjeta_de_credito'.\n"
            "- dias_de_atraso: días transcurridos desde el vencimiento impago (situación de hoy).\n"
            "- monto_adeudado: total adeudado.\n"
            "- cuota_vencida: valor de la cuota impaga puntual.\n"
            "- antiguedad_meses: hace cuántos meses es cliente de la institución.\n"
            "- canal_preferido: 'email', 'sms', 'whatsapp' o 'telefono'.\n"
            "- historial_de_pagos: los meses YA CERRADOS, del más antiguo al más reciente. "
            "Cada mes es 'a_tiempo', 'tardio' o 'no_pago'. El atraso actual NO está incluido "
            "acá: es la situación de hoy y viene en dias_de_atraso. Por eso un cliente puede "
            "tener un historial impecable y estar en mora ahora mismo. Un cliente con poca "
            "antigüedad tiene un historial más corto, simplemente porque hay menos historia.\n"
            "- resumen_del_historial: cuántos meses hay de cada tipo, ya contados. Usá estos "
            "números si vas a mencionar cantidades, en lugar de contarlos vos. Es sólo la "
            "suma: la lectura del patrón —si los atrasos son viejos o recientes, si están "
            "agrupados o dispersos, si la conducta cambió— la tenés que hacer vos sobre "
            "historial_de_pagos."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "cliente_id": {
                    "type": "string",
                    "description": "Identificador del cliente, con el formato 'CLI-001'.",
                }
            },
            "required": ["cliente_id"],
            "additionalProperties": False,
        },
    }
]


def ejecutar_tool(nombre: str, argumentos: dict) -> tuple[str, bool]:
    """
    Despacha una tool pedida por el modelo. Devuelve (contenido, es_error).

    Todo error es controlado y vuelve al modelo como texto: si le pide un cliente que
    no existe, se entera y puede corregir, en vez de que se caiga el harness.
    """
    if nombre != "consultar_cliente":
        return f"La tool '{nombre}' no existe.", True

    try:
        perfil = consultar_cliente(argumentos["cliente_id"])
    except ClienteInexistente as e:
        return str(e), True
    except KeyError:
        return "Falta el parámetro obligatorio 'cliente_id'.", True

    return json.dumps(perfil, ensure_ascii=False), False
