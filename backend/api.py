"""
La API: el backend expuesto como servicio.

Acá se hace real la separación backend/frontend. Todo lo que el frontend puede
hacer, se puede hacer con `curl`: el frontend no tiene ningún poder especial ni
ninguna lógica de control propia. Es un cliente más.

El endpoint que importa para la demo es `POST /propuestas/{id}/ejecutar`. Está
separado a propósito de `/aprobar`: si aprobar ejecutara automáticamente, no se
podría demostrar qué pasa cuando alguien pide ejecutar sin aprobación. Con los dos
endpoints separados, cualquiera puede saltear el frontend, pedir la ejecución de
una propuesta pendiente, y ver que el backend la rechaza.

Ningún endpoint toca el estado de una propuesta por su cuenta: todos delegan en las
funciones de `approval.py`. La API traduce HTTP a llamadas al gate y traduce las
excepciones del gate a códigos de estado. No decide nada.

Uso:  uvicorn api:app --app-dir backend --reload
"""

from typing import Optional

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

import agent
import approval
import tools
from models import ACCIONES_PERMITIDAS, EstadoDePropuesta

app = FastAPI(
    title="Agente de cobranza temprana",
    description="Backend del agente. Toda acción con efectos pasa por el gate de "
                "aprobación humana, que vive en approval.py.",
    version="0.1.0",
)

# El frontend es un archivo estático que corre en otro origen. En una PoC local esto
# alcanza; en producción se restringe al dominio de la institución.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Traducción de excepciones del dominio a códigos HTTP
#
# En un solo lugar, para que ninguna ruta tenga que acordarse de hacerlo y para que
# el bloqueo del gate se vea igual venga del endpoint que venga.
# ---------------------------------------------------------------------------

_CODIGOS = {
    # 403: la petición se entiende, pero está prohibida. Es EL bloqueo del gate.
    approval.ExcepcionAprobacionRequerida: 403,
    # 409: el pedido choca con el estado actual (aprobar algo ya rechazado, etc.).
    approval.ExcepcionTransicionInvalida: 409,
    # 422: la acción pedida no existe en la lista cerrada.
    approval.ExcepcionAccionNoPermitida: 422,
    approval.ExcepcionPropuestaInexistente: 404,
    tools.ClienteInexistente: 404,
    # 502: el problema fue del modelo, no de quien llamó.
    agent.ExcepcionDelAgente: 502,
}


def _registrar_manejadores() -> None:
    for excepcion, codigo in _CODIGOS.items():
        app.add_exception_handler(excepcion, _manejar_excepcion_del_dominio)


async def _manejar_excepcion_del_dominio(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=_CODIGOS[type(exc)],
        content={"error": type(exc).__name__, "detalle": str(exc)},
    )


_registrar_manejadores()


# ---------------------------------------------------------------------------
# Cuerpos de las peticiones
# ---------------------------------------------------------------------------

# `min_length=1` no es decoración: una bitácora que dice "aprobada por ''" o un
# rechazo sin motivo no sirven para auditar nada. Que la obligatoriedad viva acá y
# no en el JavaScript es justamente la regla del proyecto — si el frontend fuera el
# que exige el motivo, alcanzaría un `curl` para saltearlo.
NoVacio = Field(min_length=1)


class PedidoDeEvaluacion(BaseModel):
    cliente_id: str = NoVacio


class PedidoDeAprobacion(BaseModel):
    analista: str = NoVacio
    comentario: Optional[str] = None


class PedidoDeRechazo(BaseModel):
    analista: str = NoVacio
    motivo: str = NoVacio


class PedidoDeModificacion(BaseModel):
    analista: str = NoVacio
    nueva_accion: str = NoVacio
    comentario: Optional[str] = None


# ---------------------------------------------------------------------------
# Consulta
# ---------------------------------------------------------------------------

@app.get("/acciones")
def listar_acciones():
    """
    La lista cerrada de acciones.

    Existe para que el frontend no tenga que saberla. Si la lista viviera hardcodeada
    en el JavaScript, habría dos fuentes de verdad y el front estaría afirmando una
    regla de negocio. Así el front pregunta y el backend contesta.
    """
    return list(ACCIONES_PERMITIDAS)


@app.get("/clientes")
def listar_clientes():
    """La cartera en mora temprana. Sin la etiqueta de arquetipo."""
    return tools.listar_clientes()


@app.get("/clientes/{cliente_id}")
def obtener_cliente(cliente_id: str):
    return tools.consultar_cliente(cliente_id)


@app.get("/propuestas")
def listar_propuestas(estado: Optional[EstadoDePropuesta] = None):
    """Las propuestas del agente. Con `?estado=pendiente_de_aprobacion` para la bandeja."""
    return [p.como_dict() for p in approval.listar_propuestas(estado)]


@app.get("/propuestas/{propuesta_id}")
def obtener_propuesta(propuesta_id: str):
    return approval.obtener_propuesta(propuesta_id).como_dict()


@app.get("/bitacora")
def obtener_bitacora():
    """El registro auditable, incluidos los intentos de ejecución bloqueados."""
    return approval.obtener_bitacora()


# ---------------------------------------------------------------------------
# El agente propone
# ---------------------------------------------------------------------------

@app.post("/casos/evaluar", status_code=201)
def evaluar_caso(pedido: PedidoDeEvaluacion):
    """
    Corre el agente sobre un cliente y deja la propuesta RETENIDA en el gate.

    Devuelve siempre una propuesta en `pendiente_de_aprobacion`. Este endpoint no
    ejecuta nada: no hay forma de pedirle que además haga la gestión.
    """
    tools.consultar_cliente(pedido.cliente_id)  # 404 temprano si el cliente no existe
    return agent.evaluar_caso(pedido.cliente_id).como_dict()


# ---------------------------------------------------------------------------
# El humano decide
# ---------------------------------------------------------------------------

@app.post("/propuestas/{propuesta_id}/aprobar")
def aprobar(propuesta_id: str, pedido: PedidoDeAprobacion):
    """Aprueba, y nada más. Aprobar NO ejecuta: son dos decisiones distintas."""
    return approval.aprobar(propuesta_id, pedido.analista, pedido.comentario).como_dict()


@app.post("/propuestas/{propuesta_id}/rechazar")
def rechazar(propuesta_id: str, pedido: PedidoDeRechazo):
    return approval.rechazar(propuesta_id, pedido.analista, pedido.motivo).como_dict()


@app.post("/propuestas/{propuesta_id}/modificar")
def modificar(propuesta_id: str, pedido: PedidoDeModificacion):
    """El analista corrige la acción del agente y la aprueba con la corrección."""
    return approval.aprobar_con_modificacion(
        propuesta_id, pedido.analista, pedido.nueva_accion, pedido.comentario
    ).como_dict()


# ---------------------------------------------------------------------------
# LA EJECUCIÓN — el endpoint que demuestra dónde vive el control
# ---------------------------------------------------------------------------

@app.post("/propuestas/{propuesta_id}/ejecutar")
def ejecutar(propuesta_id: str):
    """
    Pide ejecutar la acción. Sólo prospera si un humano la aprobó antes.

    No hay ninguna validación de control acá adentro: esta función delega en
    `approval.ejecutar_accion()`, que es donde está la guarda. Si esta ruta se
    borrara, el gate seguiría siendo el gate; si el frontend desapareciera, también.
    Pedirle esto a una propuesta pendiente devuelve 403 y queda asentado en la
    bitácora como intento bloqueado.
    """
    return approval.ejecutar_accion(propuesta_id).como_dict()
