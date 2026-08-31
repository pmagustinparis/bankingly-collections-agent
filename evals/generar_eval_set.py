"""
Genera el eval set -> evals/eval_set.json

Este archivo es la RÚBRICA del proyecto. Define, para cada uno de los 50 clientes,
qué acciones se consideran aceptables y cuál sería un error peligroso. Está escrito
como código y no como un JSON tipeado a mano para que el criterio sea auditable: se
puede discutir la regla, no solo el resultado caso por caso.

REGLA METODOLÓGICA: este archivo se genera y se congela ANTES de correr el agente.
Las etiquetas y los umbrales no se ajustan después de ver los resultados. Si algo de
acá se cambiara después de medir, la medición dejaría de valer.

LÍMITE QUE HAY QUE DECLARAR: estas etiquetas reflejan el criterio de quien construyó
la PoC, no el de un analista de cobranzas real. La rúbrica está razonada y fijada de
antemano, que es lo correcto metodológicamente, pero en producción las tendría que
poner gente que hace el trabajo todos los días. Va declarado en results.md.

Uso:  python3 evals/generar_eval_set.py
"""

import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ARCHIVO_DE_CLIENTES = RAIZ / "data" / "clientes.json"
ARCHIVO_DE_SALIDA = RAIZ / "evals" / "eval_set.json"

# Los dos impecables de la franja alta de atraso. Categoría de contraste (ADR-005):
# sirven para responder si el agente gestiona distinto a un buen pagador con 3 días
# que a uno con 28. CLI-030 (15 días) queda como normal: 15 días es un limbo que
# diluiría el contraste.
CONTRASTE = {"CLI-025", "CLI-046"}


# ---------------------------------------------------------------------------
# Lectura del historial (los mismos hechos que después ve el juez)
# ---------------------------------------------------------------------------

def _atrasos(cliente) -> tuple[int, int]:
    """Devuelve (atrasos totales, impagos) de los meses cerrados."""
    historial = cliente["historial_de_pagos"]
    return (
        sum(1 for mes in historial if mes != "a_tiempo"),
        sum(1 for mes in historial if mes == "no_pago"),
    )


def _perfil_de_historial(cliente) -> str:
    total, _ = _atrasos(cliente)
    if total <= 1:
        return "solido"
    if total <= 4:
        return "ocasional"
    return "feo"


def _franja_de_atraso(cliente) -> str:
    dias = cliente["dias_de_atraso"]
    if dias <= 10:
        return "bajo"
    if dias <= 20:
        return "medio"
    return "alto"


# ---------------------------------------------------------------------------
# La rúbrica de los casos normales
#
# Cruce de perfil de historial contra franja de atraso. Donde las tres acciones son
# genuinamente defendibles, el caso NO se marca con las tres aceptables —eso lo
# volvería imposible de fallar y sumaría relleno al porcentaje— sino que se declara
# ambiguo y sale del denominador de la Dimensión 1, midiéndose por razonamiento.
# ---------------------------------------------------------------------------

AMBIGUO = "AMBIGUO"

RUBRICA_NORMALES = {
    ("solido", "bajo"):     ["recordatorio"],
    ("solido", "medio"):    ["recordatorio"],
    ("solido", "alto"):     ["recordatorio", "plan_de_pago"],
    ("ocasional", "bajo"):  ["recordatorio"],
    ("ocasional", "medio"): ["recordatorio", "plan_de_pago"],
    ("ocasional", "alto"):  AMBIGUO,   # las tres son defendibles: se mide por D3
    ("feo", "bajo"):        ["recordatorio", "plan_de_pago"],
    ("feo", "medio"):       ["plan_de_pago", "escalar"],
    ("feo", "alto"):        ["plan_de_pago", "escalar"],
}


# ---------------------------------------------------------------------------
# Los casos curados: cada arquetipo tiene su propio criterio
# ---------------------------------------------------------------------------

ACEPTABLES_POR_ARQUETIPO = {
    # Historial impecable y atraso corto: un recordatorio suave y nada más.
    "buen_pagador_olvidadizo": ["recordatorio"],
    # Patrón de incumplimiento sostenido: hace falta gestión con control.
    "moroso_recurrente": ["plan_de_pago", "escalar"],
    # Sin respuesta única por diseño: se evalúa por razonamiento, no por acción.
    "ambiguo_genuino": ["recordatorio", "plan_de_pago"],
    # Poca historia: prudencia. Ni dureza infundada ni certezas sin respaldo.
    "cliente_nuevo": ["recordatorio", "plan_de_pago"],
}


def _aceptables_monto_atipico(cliente) -> list[str]:
    """
    El monto atípico no se etiqueta por regla general sino por dirección.

    - Monto muy alto: la exposición pide una gestión más cuidadosa. Ofrecer
      refinanciación a un buen pagador con nueve días de atraso es prematuro, así
      que el plan de pago queda afuera.
    - Monto trivial: gestionar con fricción cuesta más que la deuda. Sólo el
      recordatorio es proporcionado.

    Nota para el reporte: este arquetipo se mide mejor por razonamiento que por
    acción, porque la lista cerrada no codifica INTENSIDAD de gestión —eso vive en
    el tono— y el error que busca provocar es ignorar la magnitud del monto.
    """
    if cliente["monto_adeudado"] >= 1_000_000:
        return ["recordatorio", "escalar"]
    return ["recordatorio"]


# ---------------------------------------------------------------------------
# Errores peligrosos (Dimensión 2) — sólo donde el error es inequívoco
#
# Esta dimensión bloquea el Go, así que se define con la mano corta: marcar como
# peligroso algo discutible vaciaría de sentido el umbral. Cubre los dos costos
# asimétricos del negocio: agresividad con un buen cliente (relación cara de
# recuperar) y blandura con un moroso claro (recupero perdido).
# ---------------------------------------------------------------------------

def _accion_peligrosa(cliente, categoria) -> str | None:
    total_atrasos, impagos = _atrasos(cliente)
    dias = cliente["dias_de_atraso"]

    if categoria == "buen_pagador_olvidadizo":
        return "escalar"
    if categoria == "moroso_recurrente":
        return "recordatorio"

    # Los casos normales que tienen la MISMA FORMA que esos dos arquetipos se
    # miden con la misma vara: la regla es del perfil, no de la etiqueta.
    if categoria == "normal":
        if total_atrasos <= 1 and dias <= 7:
            return "escalar"
        if impagos >= 2 and dias >= 21:
            return "recordatorio"

    # Contraste, ambiguo, monto atípico y cliente nuevo: sin acción peligrosa.
    # Escalar a un buen pagador con 28 días de mora es discutible, no peligroso.
    return None


# ---------------------------------------------------------------------------

def construir_caso(cliente) -> dict:
    cliente_id = cliente["cliente_id"]
    arquetipo = cliente["arquetipo"]

    if arquetipo:
        categoria = arquetipo
    elif cliente_id in CONTRASTE:
        categoria = "buen_pagador_atraso_largo"
    else:
        categoria = "normal"

    if categoria == "monto_atipico":
        aceptables = _aceptables_monto_atipico(cliente)
    elif categoria in ACEPTABLES_POR_ARQUETIPO:
        aceptables = ACEPTABLES_POR_ARQUETIPO[categoria]
    elif categoria == "buen_pagador_atraso_largo":
        # Historial impecable pero la mora ya es larga: recordatorio firme o plan
        # preventivo. Es el mismo criterio que un normal sólido de franja alta.
        aceptables = ["recordatorio", "plan_de_pago"]
    else:
        aceptables = RUBRICA_NORMALES[(_perfil_de_historial(cliente), _franja_de_atraso(cliente))]

    # El arquetipo C es ambiguo por diseño; los normales lo son cuando las tres
    # acciones se defienden. En los dos casos salen del denominador de la D1.
    es_ambiguo = (categoria == "ambiguo_genuino") or (aceptables is AMBIGUO)
    if aceptables is AMBIGUO:
        aceptables = ["recordatorio", "plan_de_pago", "escalar"]

    return {
        "caso_id": f"EVAL-{cliente_id.split('-')[1]}",
        "cliente_id": cliente_id,
        "categoria": categoria,
        "acciones_aceptables": aceptables,
        "accion_peligrosa": _accion_peligrosa(cliente, categoria),
        "es_ambiguo": es_ambiguo,
    }


def main():
    clientes = json.loads(ARCHIVO_DE_CLIENTES.read_text(encoding="utf-8"))
    casos = [construir_caso(c) for c in clientes]

    ARCHIVO_DE_SALIDA.write_text(
        json.dumps(casos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    import collections
    print(f"{len(casos)} casos escritos en {ARCHIVO_DE_SALIDA}\n")
    print("Por categoría:")
    for categoria, cantidad in collections.Counter(c["categoria"] for c in casos).most_common():
        print(f"  {categoria:28s} {cantidad}")
    ambiguos = sum(1 for c in casos if c["es_ambiguo"])
    peligrosas = sum(1 for c in casos if c["accion_peligrosa"])
    print(f"\nAmbiguos (fuera del denominador de la D1): {ambiguos}")
    print(f"Denominador real de la Dimensión 1: {len(casos) - ambiguos}")
    print(f"Casos con acción peligrosa definida: {peligrosas}")


if __name__ == "__main__":
    main()
