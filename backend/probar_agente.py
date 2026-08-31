"""
Corre el agente sobre algunos clientes y muestra qué propone y cómo razona.

Verificable del Paso 3: el agente evalúa un caso y la propuesta queda RETENIDA en
estado `pendiente_de_aprobacion`. Nada se ejecuta.

Uso:  python3 backend/probar_agente.py [CLI-001 CLI-003 ...]
"""

import sys
import textwrap

import agent
import approval
import tools

VERDE, AMARILLO, GRIS, RESET = "\033[32m", "\033[33m", "\033[90m", "\033[0m"

CASOS_POR_DEFECTO = ["CLI-001", "CLI-003", "CLI-006"]


def mostrar_cliente(perfil: dict) -> None:
    print(f"  {GRIS}producto {perfil['tipo_de_producto']} | "
          f"{perfil['dias_de_atraso']} días de atraso | "
          f"debe {perfil['monto_adeudado']:,} (cuota {perfil['cuota_vencida']:,}) | "
          f"cliente hace {perfil['antiguedad_meses']} meses | "
          f"canal {perfil['canal_preferido']}{RESET}")
    print(f"  {GRIS}historial: {' '.join(perfil['historial_de_pagos'])}{RESET}")


def main():
    ids = sys.argv[1:] or CASOS_POR_DEFECTO
    approval.limpiar_repositorio()

    for cliente_id in ids:
        perfil = tools.consultar_cliente(cliente_id)
        print(f"\n{'=' * 78}")
        print(f"{cliente_id} — {perfil['nombre']}")
        print("=" * 78)
        mostrar_cliente(perfil)

        traza = []
        propuesta = agent.evaluar_caso(cliente_id, traza=traza)

        print(f"\n  {GRIS}trayectoria:{RESET}")
        for paso in traza:
            print(f"    {GRIS}· {paso}{RESET}")

        print(f"\n  ACCIÓN PROPUESTA: {VERDE}{propuesta.accion}{RESET}"
              f"   {GRIS}(tono: {propuesta.tono_sugerido}){RESET}")
        print("\n  RAZONAMIENTO:")
        for linea in textwrap.wrap(propuesta.razonamiento, width=72):
            print(f"    {linea}")

        print(f"\n  {AMARILLO}estado: {propuesta.estado.value}{RESET}"
              f"   {GRIS}consultó datos: {propuesta.consulto_datos}{RESET}")

    print(f"\n{'=' * 78}")
    print("Todas las propuestas quedaron retenidas en el gate. No se ejecutó ninguna:")
    for p in approval.listar_propuestas():
        print(f"  {p.propuesta_id}  {p.cliente_id}  {p.accion:14s} -> {p.estado.value}")
    print()


if __name__ == "__main__":
    main()
