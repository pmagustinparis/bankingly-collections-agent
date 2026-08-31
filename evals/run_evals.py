"""
Corre el agente sobre los 50 casos del eval set y puntúa las 4 dimensiones.

  D1 — Acción apropiada        determinística   >= 85% (excluye ambiguos)
  D2 — Errores peligrosos      determinística   <= 1 sobre 50   [BLOQUEA EL GO]
  D3 — Calidad del razonamiento LLM-as-judge    cualitativa, sin umbral
  D4 — Uso de datos / tools    determinística   100%

El núcleo es determinístico y barato. El juez LLM se usa con moderación: una sola
llamada por caso, y con una precaución de diseño importante — el juez NO hace
aritmética. Los conteos del historial los calcula el código y se los entrega ya
verificados, así el juez sólo compara el texto del agente contra hechos ciertos.
Un juez que cuenta mal taparía el error del agente en vez de medirlo.

El juez tampoco ve el arquetipo ni las acciones aceptables: si supiera cuál era la
respuesta esperada, premiaría el acuerdo con la D1 y la D3 sería una copia ruidosa
de la D1 en lugar de una medición independiente.

Uso:
  python3 evals/run_evals.py                       corre el eval base (50 casos)
  python3 evals/run_evals.py --reporte             rehace el reporte sin volver a medir
  python3 evals/run_evals.py --eval-set X --crudo Y --reporte-out Z

`results.md` es un documento CURADO que cuenta la historia de las tres corridas
(base, mitigada e iteración de escalamiento). Este script genera el reporte
cuantitativo de UNA corrida; el ensamblado narrativo se escribe a mano sobre esa
base, porque el análisis de errores es interpretación y no sale de una plantilla.
"""

import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "backend"))

import anthropic  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

import agent  # noqa: E402
import approval  # noqa: E402
import tools  # noqa: E402

load_dotenv()

def _argumento(bandera: str, por_defecto: str) -> Path:
    """Lee `--bandera valor` de la línea de comandos, o usa el valor por defecto."""
    if bandera in sys.argv:
        return Path(sys.argv[sys.argv.index(bandera) + 1])
    return RAIZ / "evals" / por_defecto


ARCHIVO_EVAL_SET = _argumento("--eval-set", "eval_set.json")
ARCHIVO_CRUDO = _argumento("--crudo", "resultados_crudos.json")
ARCHIVO_REPORTE = _argumento("--reporte-out", "results.md")

# Umbrales FIJADOS ANTES DE MEDIR. No se tocan después de ver los resultados.
UMBRAL_D1 = 0.85
UMBRAL_D2 = 1        # cantidad máxima de errores peligrosos tolerada
UMBRAL_D4 = 1.0

# Para clasificar un fallo por dirección: ¿se pasó de blando o de duro?
FIRMEZA = {"recordatorio": 0, "plan_de_pago": 1, "escalar": 2}


# ---------------------------------------------------------------------------
# Los hechos del caso, calculados por código
# ---------------------------------------------------------------------------

def hechos_verificados(perfil: dict) -> dict:
    """
    Lo que es objetivamente cierto del historial de este cliente.

    Se le entrega al juez para que no tenga que contar. Es la pieza que convierte
    la verificación factual en algo confiable en vez de en otra opinión de modelo.
    """
    historial = perfil["historial_de_pagos"]
    conteo = Counter(historial)
    return {
        "meses_cerrados_en_el_historial": len(historial),
        "meses_a_tiempo": conteo.get("a_tiempo", 0),
        "meses_tardio": conteo.get("tardio", 0),
        "meses_no_pago": conteo.get("no_pago", 0),
        "ultimo_mes_cerrado": historial[-1] if historial else None,
        "atrasos_en_los_ultimos_3_meses": sum(
            1 for mes in historial[-3:] if mes != "a_tiempo"
        ),
        "veces_la_cuota_que_representa_la_deuda": round(
            perfil["monto_adeudado"] / perfil["cuota_vencida"], 2
        ),
    }


# ---------------------------------------------------------------------------
# El juez
# ---------------------------------------------------------------------------

PROMPT_DEL_JUEZ = """\
Sos un evaluador de la calidad del razonamiento de un asistente de cobranza.

Te doy los datos de un cliente, un bloque de HECHOS VERIFICADOS calculados
programáticamente sobre esos datos, y la acción que el asistente propuso con su
razonamiento. Tu tarea es juzgar la calidad del RAZONAMIENTO, no si te gusta la
acción elegida.

Importante: puede haber más de una acción defendible para el mismo caso. No penalices
una acción con la que no coincidirías si el argumento que la sostiene es sólido.

# Qué mirar

1. VERACIDAD. ¿Todo lo que el razonamiento afirma sobre los datos es cierto?
   Compará cada afirmación numérica o factual contra el bloque de HECHOS VERIFICADOS
   y contra los datos del cliente. Los hechos verificados son correctos por
   construcción: si el razonamiento los contradice, el equivocado es el razonamiento.
   Prestá atención a los conteos del historial de pagos, que es donde es fácil errar.

2. CONSECUENCIA. ¿La acción propuesta se sigue del argumento? ¿O el razonamiento
   apunta en una dirección y la acción va en otra?

3. INCERTIDUMBRE. Cuando los datos no alcanzan para concluir con seguridad —poca
   historia, señales contradictorias, un cambio de patrón reciente— ¿el razonamiento
   lo reconoce, o finge una certeza que los datos no respaldan?

4. ESPECIFICIDAD. ¿El razonamiento se apoya en los datos concretos de ESTE cliente,
   o serviría igual copiado para cualquier otro?

# El veredicto

- `coherente`: sin afirmaciones falsas, la acción se sigue del argumento, y el
  razonamiento es específico de este cliente.
- `parcial`: el núcleo del argumento se sostiene, pero hay una imprecisión, un salto
  lógico, o generalidad de más.
- `incoherente`: hay afirmaciones falsas que importan para la conclusión, o la acción
  no se sigue de lo que el propio razonamiento argumenta.

En `afirmaciones_incorrectas` listá, textualmente y una por una, las afirmaciones del
razonamiento que contradicen los datos. Si no hay ninguna, devolvé una lista vacía.
"""

FORMATO_DEL_VEREDICTO = {
    "type": "json_schema",
    "schema": {
        "type": "object",
        "properties": {
            "veredicto": {
                "type": "string",
                "enum": ["coherente", "parcial", "incoherente"],
            },
            "afirmaciones_incorrectas": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Afirmaciones del razonamiento que contradicen los datos.",
            },
            "la_accion_se_sigue_del_argumento": {"type": "boolean"},
            "reconoce_la_incertidumbre": {"type": "boolean"},
            "justificacion": {"type": "string"},
        },
        "required": [
            "veredicto",
            "afirmaciones_incorrectas",
            "la_accion_se_sigue_del_argumento",
            "reconoce_la_incertidumbre",
            "justificacion",
        ],
        "additionalProperties": False,
    },
}


def juzgar(cliente_api, perfil: dict, propuesta: dict) -> dict:
    """Una llamada al juez por caso. Sin arquetipo y sin acciones aceptables."""
    entrada = {
        "datos_del_cliente": perfil,
        "hechos_verificados": hechos_verificados(perfil),
        "accion_propuesta": propuesta["accion"],
        "razonamiento_del_asistente": propuesta["razonamiento"],
        "tono_sugerido": propuesta["tono_sugerido"],
    }
    respuesta = cliente_api.messages.create(
        model=agent.MODELO,
        max_tokens=agent.MAX_TOKENS,
        system=PROMPT_DEL_JUEZ,
        output_config={"effort": agent.ESFUERZO, "format": FORMATO_DEL_VEREDICTO},
        messages=[{"role": "user", "content": json.dumps(entrada, ensure_ascii=False, indent=2)}],
    )
    texto = next(b.text for b in respuesta.content if b.type == "text")
    return json.loads(texto)


# ---------------------------------------------------------------------------
# La corrida
# ---------------------------------------------------------------------------

def correr() -> list[dict]:
    casos = json.loads(ARCHIVO_EVAL_SET.read_text(encoding="utf-8"))
    cliente_api = anthropic.Anthropic()
    approval.limpiar_repositorio()

    resultados = []
    for i, caso in enumerate(casos, 1):
        cliente_id = caso["cliente_id"]
        print(f"[{i:2d}/{len(casos)}] {cliente_id} ({caso['categoria']})…", flush=True)

        registro = {"caso": caso, "error": None, "propuesta": None, "veredicto": None}
        try:
            perfil = tools.consultar_cliente(cliente_id)
            propuesta = agent.evaluar_caso(cliente_id).como_dict()
            registro["propuesta"] = propuesta
            registro["veredicto"] = juzgar(cliente_api, perfil, propuesta)
            print(f"          -> {propuesta['accion']} / {registro['veredicto']['veredicto']}",
                  flush=True)
        except Exception as e:  # un caso que falla no debe tirar abajo la corrida
            registro["error"] = f"{type(e).__name__}: {e}"
            print(f"          -> ERROR: {registro['error']}", flush=True)

        resultados.append(registro)
        # Se guarda incrementalmente: si algo se cae a mitad de camino, no se
        # pierden las llamadas ya pagadas.
        ARCHIVO_CRUDO.write_text(
            json.dumps(resultados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    return resultados


# ---------------------------------------------------------------------------
# Puntuación
# ---------------------------------------------------------------------------

def clasificar_fallo(accion: str, aceptables: list[str]) -> str:
    """Por qué falló: ¿se pasó de blando, de duro, o eligió algo intermedio?"""
    firmeza_propuesta = FIRMEZA[accion]
    firmezas_aceptables = [FIRMEZA[a] for a in aceptables]
    if firmeza_propuesta < min(firmezas_aceptables):
        return "mas_blando_de_lo_aceptable"
    if firmeza_propuesta > max(firmezas_aceptables):
        return "mas_duro_de_lo_aceptable"
    return "intensidad_intermedia_no_aceptable"


def puntuar(resultados: list[dict]) -> dict:
    por_categoria = defaultdict(lambda: {
        "total": 0, "d1_evaluados": 0, "d1_aciertos": 0,
        "d2_errores": 0, "d4_consultaron": 0,
        "veredictos": Counter(), "casos": [],
    })
    fallos_d1, errores_d2, fallos_d4, factuales = [], [], [], []
    errores_de_corrida = []

    for registro in resultados:
        caso = registro["caso"]
        categoria = caso["categoria"]
        acumulador = por_categoria[categoria]
        acumulador["total"] += 1

        if registro["error"]:
            errores_de_corrida.append((caso["cliente_id"], registro["error"]))
            continue

        propuesta = registro["propuesta"]
        veredicto = registro["veredicto"] or {}
        accion = propuesta["accion"]

        # D4 — uso de datos
        if propuesta["consulto_datos"]:
            acumulador["d4_consultaron"] += 1
        else:
            fallos_d4.append(caso["cliente_id"])

        # D1 — acción apropiada (los ambiguos no entran al denominador)
        acierto = accion in caso["acciones_aceptables"]
        if not caso["es_ambiguo"]:
            acumulador["d1_evaluados"] += 1
            if acierto:
                acumulador["d1_aciertos"] += 1
            else:
                fallos_d1.append({
                    "cliente_id": caso["cliente_id"], "categoria": categoria,
                    "propuso": accion, "aceptables": caso["acciones_aceptables"],
                    "tipo": clasificar_fallo(accion, caso["acciones_aceptables"]),
                })

        # D2 — errores peligrosos
        if caso["accion_peligrosa"] and accion == caso["accion_peligrosa"]:
            acumulador["d2_errores"] += 1
            errores_d2.append({
                "cliente_id": caso["cliente_id"], "categoria": categoria, "propuso": accion,
            })

        # D3 — razonamiento
        acumulador["veredictos"][veredicto.get("veredicto", "sin_veredicto")] += 1
        for afirmacion in veredicto.get("afirmaciones_incorrectas", []):
            factuales.append({"cliente_id": caso["cliente_id"], "categoria": categoria,
                              "afirmacion": afirmacion})

        acumulador["casos"].append({
            "cliente_id": caso["cliente_id"], "accion": accion, "acierto": acierto,
            "veredicto": veredicto.get("veredicto"),
            "reconoce_incertidumbre": veredicto.get("reconoce_la_incertidumbre"),
            "afirmaciones_incorrectas": veredicto.get("afirmaciones_incorrectas", []),
            "razonamiento": propuesta["razonamiento"],
            "tono": propuesta["tono_sugerido"],
        })

    evaluados = sum(a["d1_evaluados"] for a in por_categoria.values())
    aciertos = sum(a["d1_aciertos"] for a in por_categoria.values())
    con_datos = sum(a["d4_consultaron"] for a in por_categoria.values())
    medidos = len(resultados) - len(errores_de_corrida)

    return {
        "por_categoria": dict(por_categoria),
        "d1": {"evaluados": evaluados, "aciertos": aciertos,
               "tasa": aciertos / evaluados if evaluados else 0.0},
        "d2": {"errores": len(errores_d2), "detalle": errores_d2},
        "d3": {"veredictos": Counter(
                   c["veredicto"] for a in por_categoria.values() for c in a["casos"]),
               "casos_con_afirmaciones_falsas": len({f["cliente_id"] for f in factuales}),
               "afirmaciones": factuales},
        "d4": {"con_datos": con_datos, "medidos": medidos,
               "tasa": con_datos / medidos if medidos else 0.0, "fallos": fallos_d4},
        "fallos_d1": fallos_d1,
        "errores_de_corrida": errores_de_corrida,
        "medidos": medidos,
    }


# ---------------------------------------------------------------------------
# El reporte
# ---------------------------------------------------------------------------

ORDEN_DE_CATEGORIAS = [
    "buen_pagador_olvidadizo", "moroso_recurrente", "ambiguo_genuino",
    "monto_atipico", "cliente_nuevo", "buen_pagador_atraso_largo", "normal",
]


def escribir_reporte(p: dict, resultados: list[dict]) -> None:
    d1, d2, d3, d4 = p["d1"], p["d2"], p["d3"], p["d4"]
    marca = lambda ok: "CUMPLE" if ok else "NO CUMPLE"  # noqa: E731
    d1_ok = d1["tasa"] >= UMBRAL_D1
    d2_ok = d2["errores"] <= UMBRAL_D2
    d4_ok = d4["tasa"] >= UMBRAL_D4

    L = []
    L.append("# Resultados de evaluación — agente de cobranza temprana\n")
    L.append(f"Corrida: {datetime.now(timezone.utc).isoformat(timespec='seconds')}  ")
    L.append(f"Modelo: `{agent.MODELO}` · esfuerzo `{agent.ESFUERZO}`  ")
    L.append(f"Casos: {p['medidos']} de {len(resultados)} medidos  ")
    L.append(f"Eval set: `{ARCHIVO_EVAL_SET.name}` · datos crudos: `{ARCHIVO_CRUDO.name}`\n")
    L.append("> Los umbrales de este reporte se fijaron **antes** de medir, en el plan del")
    L.append("> Paso 6, y no se tocaron después de ver los resultados. El eval set se generó")
    L.append("> y se congeló antes de la primera llamada al agente.\n")

    # --- Resumen ---
    L.append("## Resumen contra umbrales\n")
    L.append("| Dimensión | Tipo | Umbral | Resultado | |")
    L.append("|---|---|---|---|---|")
    L.append(f"| 1. Acción apropiada | determinística | ≥ 85% | "
             f"**{d1['tasa']:.0%}** ({d1['aciertos']}/{d1['evaluados']}) | {marca(d1_ok)} |")
    L.append(f"| 2. Errores peligrosos | determinística | ≤ 1 sobre 50 | "
             f"**{d2['errores']}** | {marca(d2_ok)} |")
    veredictos = " · ".join(f"{k}: {v}" for k, v in d3["veredictos"].most_common())
    L.append(f"| 3. Calidad del razonamiento | juez LLM sin calibrar | cualitativo | "
             f"{veredictos} | — |")
    L.append(f"| 4. Uso de datos / tools | determinística | 100% | "
             f"**{d4['tasa']:.0%}** ({d4['con_datos']}/{d4['medidos']}) | {marca(d4_ok)} |")
    L.append("")
    L.append(f"La Dimensión 1 se mide sobre **{d1['evaluados']} casos**, no sobre 50: los "
             f"{50 - d1['evaluados']} casos ambiguos quedan fuera del denominador porque en "
             "ellos más de una acción es defendible y contarlos sería relleno que no puede "
             "fallar. Se evalúan por Dimensión 3.\n")

    bloqueo = ("La Dimensión 2 **bloquea el Go**: con más de un error peligroso la "
               "recomendación es No-Go aunque el resto pase.")
    L.append(f"{bloqueo}\n")

    # --- Por categoría ---
    L.append("## Resultados por categoría\n")
    L.append("| Categoría | Casos | D1 acción apropiada | D2 peligrosos | D3 razonamiento | D4 datos |")
    L.append("|---|---|---|---|---|---|")
    for categoria in ORDEN_DE_CATEGORIAS:
        a = p["por_categoria"].get(categoria)
        if not a:
            continue
        d1_txt = (f"{a['d1_aciertos']}/{a['d1_evaluados']}" if a["d1_evaluados"]
                  else "— (ambiguos)")
        v = " · ".join(f"{k[:4]}. {n}" for k, n in a["veredictos"].most_common())
        L.append(f"| `{categoria}` | {a['total']} | {d1_txt} | {a['d2_errores']} | {v} | "
                 f"{a['d4_consultaron']}/{a['total']} |")
    L.append("")

    # --- Qué propuso en los casos difíciles ---
    L.append("## Qué propuso el agente en los casos curados\n")
    L.append("| Cliente | Categoría | Propuso | Aceptables | ¿Acertó? | Juez |")
    L.append("|---|---|---|---|---|---|")
    for registro in resultados:
        caso = registro["caso"]
        if caso["categoria"] == "normal" or not registro["propuesta"]:
            continue
        accion = registro["propuesta"]["accion"]
        acierto = accion in caso["acciones_aceptables"]
        marca_acierto = "—" if caso["es_ambiguo"] else ("sí" if acierto else "**NO**")
        L.append(f"| {caso['cliente_id']} | `{caso['categoria']}` | `{accion}` | "
                 f"{', '.join(f'`{a}`' for a in caso['acciones_aceptables'])} | "
                 f"{marca_acierto} | {registro['veredicto']['veredicto']} |")
    L.append("")

    # --- Distribución de acciones ---
    # Va en el reporte automático a propósito: es el número que las métricas de
    # titular esconden. Un agente puede tener 98% de acción apropiada y estar
    # usando dos de las tres acciones que tiene disponibles.
    L.append("## Distribución de las acciones propuestas\n")
    propuestas = Counter(r["propuesta"]["accion"] for r in resultados if r["propuesta"])
    L.append("| Acción | Veces propuesta | Sobre el total |")
    L.append("|---|---|---|")
    for accion in ("recordatorio", "plan_de_pago", "escalar"):
        n = propuestas.get(accion, 0)
        L.append(f"| `{accion}` | {n} | {n / p['medidos']:.0%} |")
    L.append("")
    sin_usar = [a for a in ("recordatorio", "plan_de_pago", "escalar") if not propuestas.get(a)]
    if sin_usar:
        L.append(f"**El agente nunca propuso {', '.join(f'`{a}`' for a in sin_usar)}** "
                 f"en los {p['medidos']} casos.\n")

    # --- Taxonomía de fallos ---
    L.append("## Taxonomía de fallos\n")
    L.append("Agrupados por **tipo de falla**, no por caso: cada tipo es un modo de error "
             "accionable, y saber en qué se equivoca sistemáticamente vale más que la lista "
             "de cuáles falló.\n")

    if p["fallos_d1"]:
        por_tipo = defaultdict(list)
        for f in p["fallos_d1"]:
            por_tipo[f["tipo"]].append(f)
        nombres = {
            "mas_blando_de_lo_aceptable": "Se queda corto: propone una gestión más blanda "
                                          "que la que el perfil pide",
            "mas_duro_de_lo_aceptable": "Se pasa de firme: endurece más de lo que el perfil "
                                        "justifica",
            "intensidad_intermedia_no_aceptable": "Elige una intensidad intermedia que no "
                                                  "corresponde al caso",
        }
        for tipo, fallos in sorted(por_tipo.items(), key=lambda kv: -len(kv[1])):
            L.append(f"### {nombres[tipo]} — {len(fallos)} caso(s)\n")
            for f in fallos:
                L.append(f"- **{f['cliente_id']}** (`{f['categoria']}`): propuso "
                         f"`{f['propuso']}`, aceptables "
                         f"{', '.join(f'`{a}`' for a in f['aceptables'])}.")
            L.append("")
    else:
        L.append("### Sin fallos de acción apropiada\n")
        L.append("Ningún caso quedó fuera de su conjunto aceptable.\n")

    # --- Errores factuales (la pregunta del ADR-010) ---
    L.append("### Errores factuales en el razonamiento\n")
    total_casos_falsos = d3["casos_con_afirmaciones_falsas"]
    L.append(f"El juez encontró afirmaciones que contradicen los datos en "
             f"**{total_casos_falsos} de {p['medidos']} casos** "
             f"({total_casos_falsos / p['medidos']:.0%}).\n")
    if d3["afirmaciones"]:
        L.append("| Cliente | Categoría | Afirmación incorrecta |")
        L.append("|---|---|---|")
        for f in d3["afirmaciones"]:
            texto = f["afirmacion"].replace("|", "/").replace("\n", " ")
            L.append(f"| {f['cliente_id']} | `{f['categoria']}` | {texto} |")
        L.append("")

    if d4["fallos"]:
        L.append("### Propuestas sin consultar datos\n")
        L.append(f"{len(d4['fallos'])} caso(s): {', '.join(d4['fallos'])}. "
                 "Es un fallo de proceso, no de criterio: hay que corregirlo en el harness.\n")

    if p["errores_de_corrida"]:
        L.append("### Casos que no se pudieron medir\n")
        for cliente_id, error in p["errores_de_corrida"]:
            L.append(f"- {cliente_id}: {error}")
        L.append("")

    # --- Contraste ---
    L.append("## Análisis de contraste: ¿calibra la firmeza por nivel de riesgo?\n")
    L.append("Pregunta que ningún arquetipo responde solo: **¿el agente gestiona distinto a "
             "un buen pagador con pocos días de atraso que a uno con muchos?** Si tratara "
             "igual a los dos, no estaría calibrando la firmeza por riesgo, que es un "
             "principio explícito del dominio (ADR-005).\n")
    L.append("| Cliente | Categoría | Días de atraso | Historial | Propuso |")
    L.append("|---|---|---|---|---|")
    for registro in resultados:
        caso = registro["caso"]
        if caso["categoria"] not in ("buen_pagador_olvidadizo", "buen_pagador_atraso_largo"):
            continue
        if not registro["propuesta"]:
            continue
        perfil = tools.consultar_cliente(caso["cliente_id"])
        atrasos = sum(1 for m in perfil["historial_de_pagos"] if m != "a_tiempo")
        L.append(f"| {caso['cliente_id']} | `{caso['categoria']}` | "
                 f"{perfil['dias_de_atraso']} | "
                 f"{'impecable' if not atrasos else f'{atrasos} atraso(s)'} | "
                 f"`{registro['propuesta']['accion']}` |")
    L.append("")

    # --- Límites ---
    L.append("## Límites de esta medición\n")
    L.append("Declarados de entrada, no como descargo posterior.\n")
    L.append("1. **El juez LLM no está calibrado contra anotación humana.** Es una opinión "
             "de modelo con una rúbrica, no una medición validada. Se mitigó en parte lo "
             "más frágil —la verificación factual— entregándole los conteos ya calculados "
             "por código, así el juez compara en vez de contar; pero el veredicto global "
             "sigue sin calibrar. Calibrarlo contra un panel de analistas es el próximo "
             "paso en producción.")
    L.append("2. **Las `acciones_aceptables` reflejan el criterio de quien construyó la "
             "PoC, no el de un analista de cobranzas real.** La rúbrica está razonada y "
             "fijada antes de medir, que es lo correcto metodológicamente, pero en "
             "producción esas etiquetas las tiene que poner gente que hace el trabajo.")
    L.append("3. **El set es chico y por categoría es más chico todavía** (2 casos por "
             "arquetipo). Un solo fallo mueve el porcentaje de una categoría entera. Es una "
             "decisión de producto: se priorizó **diseño de dificultad sobre volumen**, "
             "porque un set curado demuestra más criterio que uno grande y aleatorio. Los "
             "números por categoría son indicativos; el valor está en el análisis "
             "cualitativo del error.")
    L.append("4. **Los umbrales son provisionales de PoC.** Tienen fundamento, pero en "
             "producción se recalibran contra el baseline real de la institución (cuán bien "
             "acierta hoy su gestión por tramo de atraso) y contra datos reales en lugar de "
             "50 casos sintéticos.")
    L.append("5. **La reproducibilidad es alta pero no bit-exacta.** Los modelos actuales no "
             "aceptan `temperature`; la estabilidad se busca con esfuerzo bajo y constante, "
             "prompt fijo y datos fijos (ADR-002). Dos corridas pueden diferir levemente.\n")

    ARCHIVO_REPORTE.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"\nReporte escrito en {ARCHIVO_REPORTE}")


def main():
    if "--reporte" in sys.argv:
        resultados = json.loads(ARCHIVO_CRUDO.read_text(encoding="utf-8"))
        print(f"Rehaciendo el reporte desde {ARCHIVO_CRUDO} ({len(resultados)} casos)")
    else:
        resultados = correr()

    p = puntuar(resultados)
    escribir_reporte(p, resultados)

    print(f"\nD1 acción apropiada : {p['d1']['tasa']:.0%} "
          f"({p['d1']['aciertos']}/{p['d1']['evaluados']})   umbral 85%")
    print(f"D2 errores peligrosos: {p['d2']['errores']}                 umbral <= 1")
    print(f"D3 veredictos        : {dict(p['d3']['veredictos'])}")
    print(f"   casos con afirmaciones falsas: {p['d3']['casos_con_afirmaciones_falsas']}")
    print(f"D4 uso de datos      : {p['d4']['tasa']:.0%} "
          f"({p['d4']['con_datos']}/{p['d4']['medidos']})   umbral 100%")


if __name__ == "__main__":
    main()
