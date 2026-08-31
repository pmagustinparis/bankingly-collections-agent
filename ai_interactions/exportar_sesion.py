"""
Exporta la sesión de Claude Code a un markdown legible.

Existe para que quede claro que la exportación es MECÁNICA y no una selección
editorial: este script vuelca todos los turnos en orden, sin elegir cuáles. La
curaduría de los tres momentos que pide el ejercicio se hace aparte, a mano y de
forma declarada, en `candidatos.md` e `interactions.md`.

Qué conserva y qué resume:
  - Los mensajes del usuario y las respuestas del asistente van ÍNTEGROS, textuales.
  - Cada llamada a una herramienta se reduce a una línea (qué herramienta, sobre qué).
    Volcar las salidas completas de comandos haría el archivo ilegible y enterraría
    justamente lo que hay que poder leer: los intercambios textuales.

Para quien quiera la prueba sin ningún filtro, al lado está `sesion_completa.jsonl`:
el volcado original de Claude Code, copiado sin tocar.

Uso:  python3 ai_interactions/exportar_sesion.py <ruta-al-.jsonl>
"""

import json
import re
import sys
from pathlib import Path

SALIDA = Path(__file__).resolve().parent / "sesion_completa.md"

# Bloques que el runtime inyecta en el turno del usuario y que no escribió una persona.
RUIDO = re.compile(
    r"<system-reminder>.*?</system-reminder>|<ide_opened_file>.*?</ide_opened_file>|"
    r"<ide_selection>.*?</ide_selection>",
    re.DOTALL,
)


def _texto_de(contenido) -> str:
    """Junta los bloques de texto de un mensaje, venga como string o como lista."""
    if isinstance(contenido, str):
        return contenido
    if not isinstance(contenido, list):
        return ""
    return "".join(
        bloque.get("text", "")
        for bloque in contenido
        if isinstance(bloque, dict) and bloque.get("type") == "text"
    )


def _resumir_herramienta(bloque: dict) -> str:
    """Una línea por llamada: qué herramienta y sobre qué actuó."""
    nombre = bloque.get("name", "?")
    entrada = bloque.get("input", {}) or {}
    detalle = (
        entrada.get("description")
        or entrada.get("file_path")
        or entrada.get("skill")
        or entrada.get("query")
        or (entrada.get("command", "")[:80] if entrada.get("command") else "")
        or ""
    )
    return f"`{nombre}`" + (f" — {detalle}" if detalle else "")


def _es_turno_humano(texto: str) -> bool:
    """Distingue lo que escribió una persona de lo que inyectó el sistema."""
    if not texto.strip():
        return False
    marcas = ("<task-notification>", "<system-reminder>", "Base directory for this skill:",
              "<command-name>", "tool_use_error")
    return not any(marca in texto for marca in marcas)


def exportar(ruta_jsonl: Path) -> None:
    lineas = [
        "# Sesión completa de Claude Code — agente de cobranza temprana\n",
        "Exportación mecánica de la sesión, en orden cronológico, generada por ",
        "`exportar_sesion.py`.\n",
        "Los mensajes del usuario y las respuestas del asistente están **íntegros y sin ",
        "editar**. Cada llamada a una herramienta se resume en una línea; el volcado sin ",
        "ningún filtro está en `sesion_completa.jsonl`.\n",
        "\n---\n",
    ]

    turnos_humanos = 0
    turnos_asistente = 0
    llamadas = 0

    with ruta_jsonl.open(encoding="utf-8") as archivo:
        for linea in archivo:
            try:
                entrada = json.loads(linea)
            except json.JSONDecodeError:
                continue

            tipo = entrada.get("type")
            momento = (entrada.get("timestamp") or "")[:19].replace("T", " ")
            contenido = entrada.get("message", {}).get("content")

            if tipo == "user":
                texto = RUIDO.sub("", _texto_de(contenido)).strip()
                if not _es_turno_humano(texto):
                    continue
                turnos_humanos += 1
                lineas.append(f"\n## USUARIO · {momento}\n\n{texto}\n")

            elif tipo == "assistant":
                if not isinstance(contenido, list):
                    continue
                texto = _texto_de(contenido).strip()
                herramientas = [
                    _resumir_herramienta(b) for b in contenido
                    if isinstance(b, dict) and b.get("type") == "tool_use"
                ]
                if not texto and not herramientas:
                    continue
                turnos_asistente += 1
                llamadas += len(herramientas)
                lineas.append(f"\n### CLAUDE · {momento}\n")
                if texto:
                    lineas.append(f"\n{texto}\n")
                for herramienta in herramientas:
                    lineas.append(f"\n> herramienta: {herramienta}\n")

    SALIDA.write_text("".join(lineas), encoding="utf-8")
    print(f"Exportado a {SALIDA}")
    print(f"  turnos del usuario  : {turnos_humanos}")
    print(f"  turnos del asistente: {turnos_asistente}")
    print(f"  llamadas a herramientas resumidas: {llamadas}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("Falta la ruta al .jsonl de la sesión.\n"
                         "Suele estar en ~/.claude/projects/<proyecto>/<id>.jsonl")
    exportar(Path(sys.argv[1]).expanduser())
