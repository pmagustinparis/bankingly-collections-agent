"""
Estructuras de datos del dominio: el cliente, la propuesta y su estado.

Este módulo no tiene lógica de control ni llama al modelo: solo define las formas.
El control vive en `approval.py`; el razonamiento, en `agent.py`.

Convención de idioma del proyecto: inglés para la mecánica (nombres de funciones y
variables de control), español para los conceptos del dominio de negocio.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
import uuid

# ---------------------------------------------------------------------------
# Configuración del dominio
#
# Estas dos constantes son los parámetros que cambian entre instituciones. Están
# acá, con nombre, en vez de dispersas como números mágicos: es lo que sostiene la
# escalabilidad a decenas de instituciones sin tocar la lógica.
# ---------------------------------------------------------------------------

# Lista CERRADA de acciones. El agente no puede proponer nada fuera de acá.
# La validación por código está en `es_accion_permitida()`, no en el prompt.
ACCIONES_PERMITIDAS = ("recordatorio", "plan_de_pago", "escalar")

# Qué se considera mora temprana. La industria usa 0-30 como corte más común, pero
# algunas instituciones usan 14-60: por eso es configurable y no está hardcodeado.
RANGO_MORA_TEMPRANA_DIAS = (1, 30)


def es_accion_permitida(accion: str) -> bool:
    """Única fuente de verdad sobre qué acciones existen. La usan el harness y el gate."""
    return accion in ACCIONES_PERMITIDAS


def ahora_utc() -> str:
    """Timestamp ISO en UTC, para que la bitácora sea comparable entre corridas."""
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# El cliente
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Cliente:
    """
    El perfil de un cliente en mora temprana, tal como lo ve el agente.

    Ojo con lo que NO está acá: el campo `arquetipo` de `clientes.json` no es un
    campo de esta clase. Eso es deliberado — `arquetipo` es metadata de evaluación
    y mostrárselo al modelo sería darle la respuesta. Al construir el Cliente desde
    el registro crudo, la etiqueta se cae sola. La garantía es estructural, no una
    instrucción en el prompt que alguien pueda olvidar.
    """

    cliente_id: str
    nombre: str
    tipo_de_producto: str
    dias_de_atraso: int
    monto_adeudado: int
    cuota_vencida: int
    antiguedad_meses: int
    canal_preferido: str
    historial_de_pagos: tuple  # meses cerrados, del más antiguo al más reciente

    @classmethod
    def desde_registro(cls, registro: dict) -> "Cliente":
        """Construye un Cliente desde un registro de `clientes.json`, sin la etiqueta."""
        return cls(
            cliente_id=registro["cliente_id"],
            nombre=registro["nombre"],
            tipo_de_producto=registro["tipo_de_producto"],
            dias_de_atraso=registro["dias_de_atraso"],
            monto_adeudado=registro["monto_adeudado"],
            cuota_vencida=registro["cuota_vencida"],
            antiguedad_meses=registro["antiguedad_meses"],
            canal_preferido=registro["canal_preferido"],
            historial_de_pagos=tuple(registro["historial_de_pagos"]),
        )

    def resumen_del_historial(self) -> dict:
        """
        Cuántos meses hay de cada tipo. Aritmética, no juicio.

        Se agregó después de medir (ver ADR-011): en la corrida base el agente contó
        mal el historial de un cliente, se armó un retrato inflado de su conducta y
        sobre esa premisa falsa propuso una gestión demasiado blanda. El error no fue
        cosmético: fue la causa de la única acción equivocada de los 50 casos.

        Lo que esto le saca de encima al agente es SUMAR, que es lo que hace mal y
        no es lo que se le quiere evaluar. Lo que NO le da es la conclusión: el
        historial mes a mes sigue entero en `historial_de_pagos`, y leer el patrón
        —si los atrasos son viejos o recientes, si están dispersos o agrupados, si
        la conducta cambió— sigue siendo trabajo suyo. No hay score de riesgo ni
        tipo de pagador acá adentro; eso sí sería darle la respuesta.
        """
        return {
            "meses_a_tiempo": self.historial_de_pagos.count("a_tiempo"),
            "meses_tardio": self.historial_de_pagos.count("tardio"),
            "meses_no_pago": self.historial_de_pagos.count("no_pago"),
            "total_de_meses_cerrados": len(self.historial_de_pagos),
        }

    def como_dict(self) -> dict:
        """Perfil serializable, que es lo que se le entrega al modelo vía la tool."""
        return {
            "cliente_id": self.cliente_id,
            "nombre": self.nombre,
            "tipo_de_producto": self.tipo_de_producto,
            "dias_de_atraso": self.dias_de_atraso,
            "monto_adeudado": self.monto_adeudado,
            "cuota_vencida": self.cuota_vencida,
            "antiguedad_meses": self.antiguedad_meses,
            "canal_preferido": self.canal_preferido,
            "historial_de_pagos": list(self.historial_de_pagos),
            "resumen_del_historial": self.resumen_del_historial(),
        }


# ---------------------------------------------------------------------------
# El estado de una propuesta
# ---------------------------------------------------------------------------

class EstadoDePropuesta(str, Enum):
    """
    El ciclo de vida completo de una propuesta:

        pendiente_de_aprobacion ──> aprobada ──> ejecutada
                    │
                    └──────────> rechazada

    Estos cuatro estados son todos los que existen. Las transiciones válidas las
    hace cumplir `approval.py`; acá solo se nombran.
    """

    PENDIENTE_DE_APROBACION = "pendiente_de_aprobacion"
    APROBADA = "aprobada"
    RECHAZADA = "rechazada"
    EJECUTADA = "ejecutada"


# ---------------------------------------------------------------------------
# La propuesta
# ---------------------------------------------------------------------------

@dataclass
class Propuesta:
    """
    Lo que el agente propone para un cliente, y todo lo que le pasó después.

    Es el objeto que atraviesa el gate. Guarda las tres cosas que hacen falta para
    que la gestión sea auditable: qué se propuso y por qué, con qué datos se decidió,
    y quién resolvió qué cosa y cuándo.
    """

    cliente_id: str
    accion: str
    razonamiento: str
    tono_sugerido: Optional[str] = None

    # --- Trazabilidad del proceso del agente ---
    # Si el agente no consultó los datos, no debería estar proponiendo nada. Lo
    # registra el harness y lo mide la Dimensión 4 de los evals.
    consulto_datos: bool = False

    # --- Identidad y estado ---
    propuesta_id: str = field(default_factory=lambda: f"PROP-{uuid.uuid4().hex[:8]}")
    estado: EstadoDePropuesta = EstadoDePropuesta.PENDIENTE_DE_APROBACION
    creada_en: str = field(default_factory=ahora_utc)

    # --- La decisión humana (la completa el gate, nadie más) ---
    decidida_por: Optional[str] = None
    decidida_en: Optional[str] = None
    comentario_del_analista: Optional[str] = None

    # Si el analista cambió la acción antes de aprobar, acá queda la original.
    # Esto es materia prima de producto: mide en qué se equivoca el agente según
    # el criterio del humano que lo usa todos los días.
    accion_propuesta_originalmente: Optional[str] = None

    # --- La ejecución (la completa el gate, después de aprobar) ---
    ejecutada_en: Optional[str] = None
    resultado_de_ejecucion: Optional[str] = None

    @property
    def aprobada(self) -> bool:
        """
        El flag que mira la guarda del gate.

        Es una propiedad DERIVADA del estado, no un booleano suelto: así no puede
        existir una propuesta rechazada que además diga `aprobada = True`. Hay un
        solo dato de verdad —`estado`— y esto lo lee.
        """
        return self.estado is EstadoDePropuesta.APROBADA

    @property
    def fue_modificada_por_el_analista(self) -> bool:
        return self.accion_propuesta_originalmente is not None

    def como_dict(self) -> dict:
        """Serialización para la API y el frontend."""
        return {
            "propuesta_id": self.propuesta_id,
            "cliente_id": self.cliente_id,
            "accion": self.accion,
            "razonamiento": self.razonamiento,
            "tono_sugerido": self.tono_sugerido,
            "consulto_datos": self.consulto_datos,
            "estado": self.estado.value,
            "creada_en": self.creada_en,
            "decidida_por": self.decidida_por,
            "decidida_en": self.decidida_en,
            "comentario_del_analista": self.comentario_del_analista,
            "accion_propuesta_originalmente": self.accion_propuesta_originalmente,
            "fue_modificada_por_el_analista": self.fue_modificada_por_el_analista,
            "ejecutada_en": self.ejecutada_en,
            "resultado_de_ejecucion": self.resultado_de_ejecucion,
        }
