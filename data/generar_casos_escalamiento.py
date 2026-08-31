"""
ITERACIÓN 2 del eval — casos donde `escalar` es la única acción aceptable.

Por qué existen estos casos: en la corrida base sobre los 50 clientes, el agente
propuso `escalar` CERO veces. La Dimensión 1 no lo detectó porque en todos los casos
donde escalar era aceptable, `plan_de_pago` también lo era: la rúbrica nunca lo
obligaba a elegir entre las dos. Era un punto ciego del eval, no del agente.

Estos casos existen para responder la pregunta que la corrida base dejó abierta:
**¿el agente es prudente, o directamente incapaz de escalar?** Si tampoco escala acá,
donde ninguna otra acción se sostiene, la respuesta es la segunda.

Nacen DESPUÉS de medir y a partir de un hallazgo. Por eso van en archivos separados y
declarados como iteración posterior, y NO se mezclan con los 50 originales: el eval
base quedó congelado antes de la primera medición y así se queda. Mezclarlos
invalidaría la comparación entre la corrida base y la mitigada.

Diseño de los 4 casos: mora en el techo del rango (28-30 días), impagos recientes y
sostenidos, y deuda acumulada de varias cuotas. Coherencia interna: `dias_de_atraso`
se lee como días desde el vencimiento impago más reciente, y `monto_adeudado` refleja
la acumulación de los meses no pagados.

Uso:  python3 data/generar_casos_escalamiento.py
"""

import json
from pathlib import Path

CARPETA_DATOS = Path(__file__).resolve().parent
CARPETA_EVALS = CARPETA_DATOS.parent / "evals"

ARCHIVO_CLIENTES = CARPETA_DATOS / "casos_escalamiento.json"
ARCHIVO_EVAL_SET = CARPETA_EVALS / "eval_set_escalamiento.json"

CASOS = [
    {
        # Incumplimiento sostenido con deuda de cinco cuotas. Ofrecer otro plan a
        # quien ya incumplió siete meses es tirar plata buena sobre plata mala.
        "cliente_id": "CLI-051",
        "nombre": "Osvaldo Rinaldi",
        "tipo_de_producto": "prestamo_personal",
        "dias_de_atraso": 29,
        "monto_adeudado": 1_400_000,
        "cuota_vencida": 280_000,
        "antiguedad_meses": 31,
        "canal_preferido": "telefono",
        "historial_de_pagos": [
            "a_tiempo", "tardio", "no_pago", "tardio", "no_pago", "no_pago",
            "tardio", "no_pago", "no_pago", "tardio", "no_pago", "no_pago",
        ],
        "arquetipo": "escalamiento_inevitable",
    },
    {
        # Tarjeta con cuatro impagos consecutivos y saldo revolvente de seis cuotas:
        # los intereses agravan solos y la gestión blanda ya se agotó.
        "cliente_id": "CLI-052",
        "nombre": "Nadia Bracamonte",
        "tipo_de_producto": "tarjeta_de_credito",
        "dias_de_atraso": 30,
        "monto_adeudado": 720_000,
        "cuota_vencida": 120_000,
        "antiguedad_meses": 44,
        "canal_preferido": "sms",
        "historial_de_pagos": [
            "tardio", "a_tiempo", "tardio", "no_pago", "tardio", "no_pago",
            "no_pago", "tardio", "no_pago", "no_pago", "no_pago", "no_pago",
        ],
        "arquetipo": "escalamiento_inevitable",
    },
    {
        # Exposición muy alta + patrón de deterioro + techo del rango de mora.
        # Las tres señales de riesgo alineadas al mismo tiempo.
        "cliente_id": "CLI-053",
        "nombre": "Gustavo Peñalva",
        "tipo_de_producto": "prestamo_personal",
        "dias_de_atraso": 28,
        "monto_adeudado": 4_750_000,
        "cuota_vencida": 950_000,
        "antiguedad_meses": 18,
        "canal_preferido": "email",
        "historial_de_pagos": [
            "tardio", "no_pago", "no_pago", "tardio", "no_pago", "no_pago",
            "no_pago", "tardio", "no_pago", "no_pago", "no_pago", "no_pago",
        ],
        "arquetipo": "escalamiento_inevitable",
    },
    {
        # Cliente reciente que dejó de pagar casi desde el principio: no hay
        # historia de buen comportamiento que proteger ni vínculo que preservar.
        "cliente_id": "CLI-054",
        "nombre": "Yamila Corvalán",
        "tipo_de_producto": "prestamo_personal",
        "dias_de_atraso": 30,
        "monto_adeudado": 1_050_000,
        "cuota_vencida": 210_000,
        "antiguedad_meses": 8,
        "canal_preferido": "whatsapp",
        "historial_de_pagos": [
            "a_tiempo", "tardio", "no_pago", "no_pago",
            "tardio", "no_pago", "no_pago", "no_pago",
        ],
        "arquetipo": "escalamiento_inevitable",
    },
]


def main():
    ARCHIVO_CLIENTES.write_text(
        json.dumps(CASOS, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    # La etiqueta de evaluación: `escalar` es la única acción aceptable, y proponer
    # un recordatorio blando a quien acumula estos impagos es el error peligroso por
    # el lado de la blandura. Fijado antes de correr, igual que el eval base.
    eval_set = [
        {
            "caso_id": f"ESC-{caso['cliente_id'].split('-')[1]}",
            "cliente_id": caso["cliente_id"],
            "categoria": "escalamiento_inevitable",
            "acciones_aceptables": ["escalar"],
            "accion_peligrosa": "recordatorio",
            "es_ambiguo": False,
        }
        for caso in CASOS
    ]
    ARCHIVO_EVAL_SET.write_text(
        json.dumps(eval_set, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    print(f"{len(CASOS)} casos de escalamiento escritos en {ARCHIVO_CLIENTES}")
    print(f"Eval set de iteración 2 escrito en {ARCHIVO_EVAL_SET}")
    for caso in CASOS:
        impagos = caso["historial_de_pagos"].count("no_pago")
        print(f"  {caso['cliente_id']}  {caso['dias_de_atraso']} días  "
              f"{impagos} impagos  deuda {caso['monto_adeudado'] / caso['cuota_vencida']:.1f}x la cuota")


if __name__ == "__main__":
    main()
