"""
Prueba del gate EN SOLEDAD: sin agente, sin modelo, sin API y sin frontend.

Fabrica propuestas a mano y comprueba que el gate se comporta como debe. Que esto
corra sin la API ni el modelo es justamente el punto: demuestra que el control es
del código y no depende de nada más.

Uso:  python3 backend/probar_gate.py
"""

import approval
from models import EstadoDePropuesta, Propuesta

VERDE, ROJO, GRIS, RESET = "\033[32m", "\033[31m", "\033[90m", "\033[0m"

_resultados = []


def esperar_excepcion(descripcion, excepcion_esperada, funcion, *args, **kwargs):
    """Corre algo que DEBE fallar y verifica que falle con la excepción correcta."""
    try:
        funcion(*args, **kwargs)
    except excepcion_esperada as e:
        print(f"  {VERDE}BLOQUEADO{RESET}  {descripcion}")
        print(f"             {GRIS}{excepcion_esperada.__name__}: {e}{RESET}")
        _resultados.append(True)
    except Exception as e:  # falló, pero por el motivo equivocado
        print(f"  {ROJO}MAL{RESET}        {descripcion}")
        print(f"             {ROJO}esperaba {excepcion_esperada.__name__}, "
              f"vino {type(e).__name__}: {e}{RESET}")
        _resultados.append(False)
    else:
        print(f"  {ROJO}NO BLOQUEÓ{RESET} {descripcion}  <-- EL GATE FALLÓ")
        _resultados.append(False)


def esperar_exito(descripcion, funcion, *args, **kwargs):
    """Corre algo que DEBE funcionar."""
    try:
        resultado = funcion(*args, **kwargs)
    except Exception as e:
        print(f"  {ROJO}FALLÓ{RESET}      {descripcion}  ({type(e).__name__}: {e})")
        _resultados.append(False)
        return None
    print(f"  {VERDE}OK{RESET}         {descripcion}")
    _resultados.append(True)
    return resultado


def propuesta_falsa(accion="recordatorio", cliente_id="CLI-001"):
    """Una propuesta inventada a mano. Ningún modelo participó de esto."""
    return Propuesta(
        cliente_id=cliente_id,
        accion=accion,
        razonamiento="Propuesta de prueba escrita a mano para ejercitar el gate.",
        tono_sugerido="cordial",
        consulto_datos=True,
    )


def main():
    approval.limpiar_repositorio()

    print("\n=== 1. Lo esencial: sin aprobación humana, no se ejecuta ===\n")
    pendiente = approval.registrar_propuesta(propuesta_falsa())
    print(f"  {GRIS}propuesta {pendiente.propuesta_id} registrada, "
          f"estado '{pendiente.estado.value}', aprobada={pendiente.aprobada}{RESET}")
    esperar_excepcion(
        "ejecutar una propuesta recién creada (pendiente)",
        approval.ExcepcionAprobacionRequerida,
        approval.ejecutar_accion, pendiente.propuesta_id,
    )

    print("\n=== 2. Con aprobación humana, sí se ejecuta ===\n")
    esperar_exito("un analista aprueba la propuesta",
                  approval.aprobar, pendiente.propuesta_id, "ana.perez")
    ejecutada = esperar_exito("ahora sí, ejecutar la acción",
                              approval.ejecutar_accion, pendiente.propuesta_id)
    if ejecutada:
        print(f"             {GRIS}{ejecutada.resultado_de_ejecucion}{RESET}")

    print("\n=== 3. Una acción aprobada se ejecuta una sola vez ===\n")
    esperar_excepcion(
        "volver a ejecutar la misma propuesta",
        approval.ExcepcionTransicionInvalida,
        approval.ejecutar_accion, pendiente.propuesta_id,
    )

    print("\n=== 4. Lo rechazado no se ejecuta nunca ===\n")
    rechazada = approval.registrar_propuesta(propuesta_falsa("escalar", "CLI-003"))
    approval.rechazar(rechazada.propuesta_id, "ana.perez", "el cliente ya pagó")
    esperar_excepcion(
        "ejecutar una propuesta rechazada",
        approval.ExcepcionAprobacionRequerida,
        approval.ejecutar_accion, rechazada.propuesta_id,
    )
    esperar_excepcion(
        "aprobar algo que ya fue rechazado",
        approval.ExcepcionTransicionInvalida,
        approval.aprobar, rechazada.propuesta_id, "otro.analista",
    )

    print("\n=== 5. La lista cerrada de acciones se valida por código ===\n")
    esperar_excepcion(
        "el agente propone una acción inventada ('condonar_deuda')",
        approval.ExcepcionAccionNoPermitida,
        approval.registrar_propuesta, propuesta_falsa("condonar_deuda"),
    )
    a_modificar = approval.registrar_propuesta(propuesta_falsa("recordatorio", "CLI-005"))
    esperar_excepcion(
        "el analista intenta aprobar con una acción inventada",
        approval.ExcepcionAccionNoPermitida,
        approval.aprobar_con_modificacion,
        a_modificar.propuesta_id, "ana.perez", "mandar_carta_documento",
    )

    print("\n=== 6. El analista puede corregir al agente antes de aprobar ===\n")
    modificada = esperar_exito(
        "cambiar 'recordatorio' por 'plan_de_pago' y aprobar",
        approval.aprobar_con_modificacion,
        a_modificar.propuesta_id, "ana.perez", "plan_de_pago",
        "el historial reciente sugiere anticiparse",
    )
    if modificada:
        print(f"             {GRIS}el agente había propuesto "
              f"'{modificada.accion_propuesta_originalmente}', se ejecuta "
              f"'{modificada.accion}'{RESET}")
    esperar_exito("ejecutar la acción ya corregida por el humano",
                  approval.ejecutar_accion, modificada.propuesta_id)

    print("\n=== 7. Saltear el gate fabricando una propuesta 'ya aprobada' ===\n")
    colada = approval.registrar_propuesta(propuesta_falsa("escalar", "CLI-004"))
    impostora = propuesta_falsa("escalar", "CLI-004")
    impostora.propuesta_id = colada.propuesta_id          # se hace pasar por la real
    impostora.estado = EstadoDePropuesta.APROBADA         # y se auto-declara aprobada
    print(f"  {GRIS}objeto impostor: id={impostora.propuesta_id}, "
          f"estado='{impostora.estado.value}', aprobada={impostora.aprobada}{RESET}")
    esperar_excepcion(
        "ejecutar usando el id de la impostora (el gate mira el repositorio, no el objeto)",
        approval.ExcepcionAprobacionRequerida,
        approval.ejecutar_accion, impostora.propuesta_id,
    )
    esperar_excepcion(
        "ejecutar una propuesta que nunca se registró",
        approval.ExcepcionPropuestaInexistente,
        approval.ejecutar_accion, "PROP-inventado",
    )

    print("\n=== Bitácora auditable ===\n")
    for entrada in approval.obtener_bitacora():
        print(f"  {entrada['momento'][11:19]}  {entrada['evento']:26s} "
              f"{entrada['propuesta_id']}  {entrada['cliente_id']}  "
              f"{GRIS}{entrada['detalle']}{RESET}")

    print("\n=== Estado final de las propuestas ===\n")
    for p in approval.listar_propuestas():
        print(f"  {p.propuesta_id}  {p.cliente_id}  {p.accion:14s} -> {p.estado.value}")

    ok = sum(_resultados)
    total = len(_resultados)
    color = VERDE if ok == total else ROJO
    print(f"\n{color}{ok}/{total} comprobaciones pasaron.{RESET}")
    if ok != total:
        raise SystemExit(1)
    print("El gate retiene todo lo que no aprobó un humano.\n")


if __name__ == "__main__":
    main()
