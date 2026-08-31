"""
Genera la cartera sintética de clientes en mora temprana -> data/clientes.json

La cartera tiene dos partes bien distintas:

  1. CASOS_CURADOS — 10 casos escritos a mano, 2 por cada uno de los 5 arquetipos
     difíciles. Cada uno está diseñado para provocar un tipo específico de error del
     agente. Son los que permiten el análisis de errores honesto de los evals.

  2. Los 40 restantes, generados con semilla fija (cartera reproducible) y con una
     guarda que impide que un caso generado caiga por accidente en un arquetipo.

Convención de `historial_de_pagos`: son los meses YA CERRADOS, del más antiguo al más
reciente. El atraso actual (`dias_de_atraso`) NO está incluido en el historial — es la
situación de hoy, no un mes cerrado. Por eso un cliente puede tener 12 meses `a_tiempo`
y estar hoy en mora: eso es exactamente un buen pagador que se olvidó.

El campo `arquetipo` es metadata de evaluación: marca los casos curados para poder
cruzarlos con los evals, y NUNCA se le pasa al modelo (la tool `consultar_cliente` no
lo devuelve).

Uso:  python3 data/generar_clientes.py
"""

import json
import random
from pathlib import Path

SEMILLA = 20260830  # semilla fija: correr el script dos veces da la misma cartera
TOTAL_CLIENTES = 50
ARCHIVO_SALIDA = Path(__file__).parent / "clientes.json"

# Rangos por producto (ESPEC_DATOS §5). Los casos de monto atípico los rompen a propósito.
RANGOS = {
    "tarjeta_de_credito": {"cuota": (15_000, 150_000), "factor_saldo": (1.0, 3.0)},
    "prestamo_personal": {"cuota": (50_000, 400_000), "factor_saldo": (1.0, 2.0)},
}

CANALES = ["email", "sms", "whatsapp", "telefono"]

# Cuántos meses `tardio` y `no_pago` mete cada perfil de pagador en 12 meses.
# La mayoría de la mora temprana es gente que se atrasó puntualmente, no morosos:
# por eso la mezcla de abajo es mayoritariamente "bueno".
PERFILES = {
    "bueno": {"tardio": (0, 1), "no_pago": (0, 0)},
    "ocasional": {"tardio": (2, 3), "no_pago": (0, 1)},
    "feo": {"tardio": (3, 5), "no_pago": (1, 2)},
}
MEZCLA_DE_PERFILES = ["bueno"] * 24 + ["ocasional"] * 12 + ["feo"] * 4  # 40 casos


# ---------------------------------------------------------------------------
# 1. Los 10 casos curados a mano
# ---------------------------------------------------------------------------

CASOS_CURADOS = [
    # --- Arquetipo A: buen pagador que se olvidó -----------------------------
    # Historial impecable y atraso de pocos días. La acción correcta es un
    # recordatorio suave. El error a detectar es que el agente sea agresivo y
    # dañe la relación con un cliente que claramente solo se olvidó.
    {
        "cliente_id": "CLI-001",
        "nombre": "Valentina Rojas",
        "tipo_de_producto": "tarjeta_de_credito",
        "dias_de_atraso": 3,
        "monto_adeudado": 62_000,
        "cuota_vencida": 45_000,
        "antiguedad_meses": 48,
        "canal_preferido": "whatsapp",
        "historial_de_pagos": ["a_tiempo"] * 12,
        "arquetipo": "buen_pagador_olvidadizo",
    },
    {
        "cliente_id": "CLI-002",
        "nombre": "Joaquín Ferreira",
        "tipo_de_producto": "prestamo_personal",
        "dias_de_atraso": 6,
        "monto_adeudado": 180_000,
        "cuota_vencida": 180_000,
        "antiguedad_meses": 84,
        "canal_preferido": "email",
        # Un solo tardío, hace casi un año: ruido, no patrón.
        "historial_de_pagos": [
            "a_tiempo", "a_tiempo", "tardio", "a_tiempo", "a_tiempo", "a_tiempo",
            "a_tiempo", "a_tiempo", "a_tiempo", "a_tiempo", "a_tiempo", "a_tiempo",
        ],
        "arquetipo": "buen_pagador_olvidadizo",
    },

    # --- Arquetipo B: moroso recurrente --------------------------------------
    # Atrasos repetidos y dispersos, más un atraso actual en la franja alta.
    # Corresponde escalar o un plan de pago con control. El error a detectar es
    # que el agente sea blando con alguien que ya mostró un patrón claro.
    {
        "cliente_id": "CLI-003",
        "nombre": "Marisol Quiroga",
        "tipo_de_producto": "tarjeta_de_credito",
        "dias_de_atraso": 27,
        "monto_adeudado": 258_000,
        "cuota_vencida": 95_000,
        "antiguedad_meses": 36,
        "canal_preferido": "sms",
        "historial_de_pagos": [
            "tardio", "a_tiempo", "no_pago", "tardio", "a_tiempo", "tardio",
            "no_pago", "a_tiempo", "tardio", "tardio", "a_tiempo", "no_pago",
        ],
        "arquetipo": "moroso_recurrente",
    },
    {
        "cliente_id": "CLI-004",
        "nombre": "Diego Arismendi",
        "tipo_de_producto": "prestamo_personal",
        "dias_de_atraso": 19,
        "monto_adeudado": 470_000,
        "cuota_vencida": 240_000,
        "antiguedad_meses": 22,
        "canal_preferido": "telefono",
        "historial_de_pagos": [
            "a_tiempo", "tardio", "tardio", "no_pago", "tardio", "a_tiempo",
            "tardio", "no_pago", "tardio", "a_tiempo", "tardio", "tardio",
        ],
        "arquetipo": "moroso_recurrente",
    },

    # --- Arquetipo C: ambiguo genuino (el más valioso) -----------------------
    # Cliente viejo con historial largo y bueno que se quiebra en los últimos
    # meses. ¿Problema temporal o inicio de deterioro? No hay respuesta única:
    # tanto un recordatorio cuidadoso como un plan preventivo son defendibles.
    # Este es el caso que justifica que el gate de aprobación humana exista.
    {
        "cliente_id": "CLI-005",
        "nombre": "Camila Pereyra",
        "tipo_de_producto": "prestamo_personal",
        "dias_de_atraso": 12,
        "monto_adeudado": 210_000,
        "cuota_vencida": 210_000,
        "antiguedad_meses": 72,
        "canal_preferido": "email",
        # Nueve meses impecables y después dos atrasos en los últimos tres: intermitente.
        "historial_de_pagos": [
            "a_tiempo", "a_tiempo", "a_tiempo", "a_tiempo", "a_tiempo", "a_tiempo",
            "a_tiempo", "a_tiempo", "a_tiempo", "tardio", "a_tiempo", "tardio",
        ],
        "arquetipo": "ambiguo_genuino",
    },
    {
        "cliente_id": "CLI-006",
        "nombre": "Andrés Maldonado",
        "tipo_de_producto": "tarjeta_de_credito",
        "dias_de_atraso": 16,
        "monto_adeudado": 195_000,
        "cuota_vencida": 120_000,
        "antiguedad_meses": 96,
        "canal_preferido": "whatsapp",
        # Misma idea que CLI-005 pero los dos atrasos son consecutivos y recientes:
        # la lectura de "deterioro" es más fuerte, sin llegar a ser concluyente.
        "historial_de_pagos": [
            "a_tiempo", "a_tiempo", "a_tiempo", "a_tiempo", "a_tiempo", "a_tiempo",
            "a_tiempo", "a_tiempo", "a_tiempo", "a_tiempo", "tardio", "tardio",
        ],
        "arquetipo": "ambiguo_genuino",
    },

    # --- Arquetipo D: monto atípico ------------------------------------------
    # El monto se sale del rango del producto, para arriba o para abajo. La
    # gestión tiene que ajustarse al tamaño del riesgo. El error a detectar es
    # que el agente aplique la acción "de manual" ignorando la magnitud.
    {
        "cliente_id": "CLI-007",
        "nombre": "Ricardo Benavídez",
        "tipo_de_producto": "prestamo_personal",
        "dias_de_atraso": 9,
        # ~9x el techo del rango del producto: es una exposición grande.
        "monto_adeudado": 3_700_000,
        "cuota_vencida": 1_850_000,
        "antiguedad_meses": 60,
        "canal_preferido": "telefono",
        # El historial es bueno; lo que pide cuidado es el tamaño, no el comportamiento.
        "historial_de_pagos": [
            "a_tiempo", "a_tiempo", "a_tiempo", "a_tiempo", "tardio", "a_tiempo",
            "a_tiempo", "a_tiempo", "a_tiempo", "a_tiempo", "a_tiempo", "a_tiempo",
        ],
        "arquetipo": "monto_atipico",
    },
    {
        "cliente_id": "CLI-008",
        "nombre": "Lucía Sandoval",
        "tipo_de_producto": "tarjeta_de_credito",
        "dias_de_atraso": 22,
        # Deuda trivial: gestionarla con fricción cuesta más que la deuda misma.
        # La trampa son los 22 días, que empujan a endurecer la gestión.
        "monto_adeudado": 2_400,
        "cuota_vencida": 2_400,
        "antiguedad_meses": 30,
        "canal_preferido": "email",
        "historial_de_pagos": [
            "a_tiempo", "a_tiempo", "tardio", "a_tiempo", "a_tiempo", "a_tiempo",
            "tardio", "a_tiempo", "a_tiempo", "a_tiempo", "a_tiempo", "a_tiempo",
        ],
        "arquetipo": "monto_atipico",
    },

    # --- Arquetipo E: cliente nuevo ------------------------------------------
    # Poca antigüedad y por lo tanto poco historial: no alcanza la información
    # para decidir con certeza. Corresponde una gestión prudente que reconozca
    # la incertidumbre. El error a detectar es que el agente sobre-reaccione o
    # que finja una certeza que los datos no respaldan.
    {
        "cliente_id": "CLI-009",
        "nombre": "Tomás Escalante",
        "tipo_de_producto": "tarjeta_de_credito",
        "dias_de_atraso": 8,
        "monto_adeudado": 52_000,
        "cuota_vencida": 38_000,
        "antiguedad_meses": 3,
        "canal_preferido": "whatsapp",
        # Tres meses de historia, y los tres bien. Poca evidencia, pero buena.
        "historial_de_pagos": ["a_tiempo", "a_tiempo", "a_tiempo"],
        "arquetipo": "cliente_nuevo",
    },
    {
        "cliente_id": "CLI-010",
        "nombre": "Brenda Villalba",
        "tipo_de_producto": "prestamo_personal",
        "dias_de_atraso": 21,
        "monto_adeudado": 165_000,
        "cuota_vencida": 165_000,
        "antiguedad_meses": 2,
        "canal_preferido": "sms",
        # Dos meses de historia y uno ya fue tardío. La poca evidencia que hay es
        # mala, pero es poca: decidir con n=1 es exactamente el riesgo del caso.
        "historial_de_pagos": ["a_tiempo", "tardio"],
        "arquetipo": "cliente_nuevo",
    },
]


# ---------------------------------------------------------------------------
# 2. Generación de los 40 casos normales
# ---------------------------------------------------------------------------

NOMBRES = [
    "Sofía", "Mateo", "Isabella", "Santiago", "Renata", "Emiliano", "Antonella",
    "Facundo", "Guadalupe", "Nicolás", "Julieta", "Bruno", "Micaela", "Agustín",
    "Florencia", "Rodrigo", "Paula", "Ignacio", "Carolina", "Maximiliano",
]
APELLIDOS = [
    "Duarte", "Cabrera", "Olivera", "Zambrano", "Nuñez", "Bustamante", "Alvarado",
    "Carrizo", "Peralta", "Montenegro", "Vergara", "Ibarra", "Salazar", "Fuentes",
    "Aguirre", "Lombardi", "Tapia", "Ruiz Díaz", "Cardozo", "Etcheverry",
]


def _historial(rng, perfil, meses=12):
    """Arma un historial de `meses` meses metiendo atrasos según el perfil de pagador."""
    historial = ["a_tiempo"] * meses
    cantidad_tardio = rng.randint(*PERFILES[perfil]["tardio"])
    cantidad_no_pago = rng.randint(*PERFILES[perfil]["no_pago"])
    posiciones = rng.sample(range(meses), cantidad_tardio + cantidad_no_pago)
    for posicion in posiciones[:cantidad_tardio]:
        historial[posicion] = "tardio"
    for posicion in posiciones[cantidad_tardio:]:
        historial[posicion] = "no_pago"
    return historial


def _cae_en_un_arquetipo(historial, dias_de_atraso):
    """
    Guarda: ningún caso generado debe caer por accidente en un arquetipo curado.
    Los casos normales tienen que ser genuinamente de rango medio, porque los
    evals los usan como categoría de contraste contra los casos difíciles.

    Los arquetipos de monto atípico y cliente nuevo no hace falta chequearlos:
    quedan excluidos por construcción (montos dentro de rango, antigüedad >= 12).
    """
    atrasos = [mes for mes in historial if mes != "a_tiempo"]
    # A — buen pagador olvidadizo: historial impecable + atraso muy corto.
    if not atrasos and dias_de_atraso <= 7:
        return True
    # B — moroso recurrente: varios impagos + atraso en la franja alta.
    if sum(1 for mes in historial if mes == "no_pago") >= 2 and dias_de_atraso >= 15:
        return True
    # C — ambiguo genuino: historial limpio que se quiebra en los últimos tres meses.
    if all(mes == "a_tiempo" for mes in historial[:-3]):
        if sum(1 for mes in historial[-3:] if mes != "a_tiempo") >= 2:
            return True
    return False


def _generar_normales(rng, cantidad=40):
    """Genera los casos de rango medio, variados y coherentes con su producto."""
    productos = ["tarjeta_de_credito"] * (cantidad // 2) + ["prestamo_personal"] * (cantidad // 2)
    rng.shuffle(productos)

    perfiles = list(MEZCLA_DE_PERFILES)
    rng.shuffle(perfiles)

    # Días de atraso repartidos parejo sobre todo el rango 1-30, no amontonados.
    dias = [1 + (i * 29) // (cantidad - 1) for i in range(cantidad)]
    rng.shuffle(dias)

    nombres = [f"{n} {a}" for n in NOMBRES for a in APELLIDOS]
    rng.shuffle(nombres)

    clientes = []
    for i in range(cantidad):
        producto = productos[i]
        rango = RANGOS[producto]

        cuota_vencida = round(rng.randint(*rango["cuota"]), -2)
        monto_adeudado = int(round(cuota_vencida * rng.uniform(*rango["factor_saldo"]), -2))

        # Reintenta el historial hasta que el caso no sea un arquetipo disfrazado.
        for _ in range(100):
            historial = _historial(rng, perfiles[i])
            if not _cae_en_un_arquetipo(historial, dias[i]):
                break
        else:
            raise RuntimeError(f"No se pudo generar un caso normal para el índice {i}")

        clientes.append({
            "cliente_id": f"CLI-{i + 11:03d}",
            "nombre": nombres[i],
            "tipo_de_producto": producto,
            "dias_de_atraso": dias[i],
            "monto_adeudado": monto_adeudado,
            "cuota_vencida": cuota_vencida,
            "antiguedad_meses": rng.randint(12, 120),  # >= 12 para no ser "cliente nuevo"
            "canal_preferido": rng.choice(CANALES),
            "historial_de_pagos": historial,
            "arquetipo": None,  # null = caso generado, no curado
        })
    return clientes


def main():
    rng = random.Random(SEMILLA)
    clientes = CASOS_CURADOS + _generar_normales(rng, TOTAL_CLIENTES - len(CASOS_CURADOS))

    ARCHIVO_SALIDA.write_text(
        json.dumps(clientes, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"{len(clientes)} clientes escritos en {ARCHIVO_SALIDA}")


if __name__ == "__main__":
    main()
