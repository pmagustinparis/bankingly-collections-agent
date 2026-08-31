#!/usr/bin/env bash
#
# Demuestra que el control vive en el BACKEND y no en la interfaz.
#
# Todo lo que sigue se hace con curl contra la API. No hay frontend corriendo, y no
# hace falta: si el control estuviera en la UI, saltearla alcanzaría para ejecutar
# una acción sin aprobación. Vamos a ver que no alcanza.
#
# Uso:  bash backend/probar_api.sh          (con la API ya levantada)
#       API=http://localhost:8000 bash backend/probar_api.sh

set -u
API="${API:-http://localhost:8000}"
VERDE=$'\033[32m'; ROJO=$'\033[31m'; GRIS=$'\033[90m'; RESET=$'\033[0m'

# Ejecuta un curl y verifica el código HTTP. Imprime el cuerpo de la respuesta.
pedir() {  # pedir <esperado> <descripcion> <metodo> <ruta> [json]
  local esperado="$1" descripcion="$2" metodo="$3" ruta="$4" cuerpo="${5:-}"
  local respuesta codigo salida
  if [ -n "$cuerpo" ]; then
    respuesta=$(curl -s -w '\n%{http_code}' -X "$metodo" "$API$ruta" \
                     -H 'Content-Type: application/json' -d "$cuerpo")
  else
    respuesta=$(curl -s -w '\n%{http_code}' -X "$metodo" "$API$ruta")
  fi
  codigo=$(printf '%s' "$respuesta" | tail -n1)
  salida=$(printf '%s' "$respuesta" | sed '$d')

  printf '\n  %s %s %s\n' "$metodo" "$ruta" "${GRIS}${cuerpo}${RESET}"
  if [ "$codigo" = "$esperado" ]; then
    printf '  %sHTTP %s%s  %s\n' "$VERDE" "$codigo" "$RESET" "$descripcion"
  else
    printf '  %sHTTP %s%s  %s  (se esperaba %s)\n' "$ROJO" "$codigo" "$RESET" "$descripcion" "$esperado"
    FALLAS=$((FALLAS + 1))
  fi
  printf '%s\n' "$salida" | head -c 700 | sed 's/^/    /'
  printf '\n'
  ULTIMA="$salida"
}

FALLAS=0

echo "================================================================"
echo " 1. El agente propone. La propuesta nace RETENIDA."
echo "================================================================"
pedir 201 "propuesta creada" POST /casos/evaluar '{"cliente_id":"CLI-003"}'
ID=$(printf '%s' "$ULTIMA" | sed -n 's/.*"propuesta_id":"\([^"]*\)".*/\1/p')
echo "  ${GRIS}propuesta: $ID${RESET}"

echo
echo "================================================================"
echo " 2. LA PRUEBA: pedir la ejecución SIN aprobación, salteando el frontend"
echo "================================================================"
pedir 403 "BLOQUEADO por el gate" POST "/propuestas/$ID/ejecutar"

echo "================================================================"
echo " 3. Tampoco alcanza con inventar el estado en el pedido"
echo "================================================================"
pedir 403 "BLOQUEADO: el cuerpo del pedido no cambia el estado" \
      POST "/propuestas/$ID/ejecutar" '{"aprobada":true,"estado":"aprobada"}'

echo "================================================================"
echo " 4. Ni con una propuesta que no existe"
echo "================================================================"
pedir 404 "no existe" POST "/propuestas/PROP-inventado/ejecutar"

echo "================================================================"
echo " 5. Con aprobación humana, recién ahí se ejecuta"
echo "================================================================"
pedir 200 "un analista aprueba (aprobar NO ejecuta)" \
      POST "/propuestas/$ID/aprobar" '{"analista":"ana.perez"}'
pedir 200 "ahora sí, la ejecución prospera" POST "/propuestas/$ID/ejecutar"

echo "================================================================"
echo " 6. Y no se puede ejecutar dos veces"
echo "================================================================"
pedir 409 "BLOQUEADO: ya fue ejecutada" POST "/propuestas/$ID/ejecutar"

echo "================================================================"
echo " 7. Lo rechazado no se ejecuta nunca"
echo "================================================================"
pedir 201 "otra propuesta" POST /casos/evaluar '{"cliente_id":"CLI-001"}'
ID2=$(printf '%s' "$ULTIMA" | sed -n 's/.*"propuesta_id":"\([^"]*\)".*/\1/p')
pedir 200 "el analista la rechaza" \
      POST "/propuestas/$ID2/rechazar" '{"analista":"ana.perez","motivo":"el cliente ya pago"}'
pedir 403 "BLOQUEADO: rechazada" POST "/propuestas/$ID2/ejecutar"

echo "================================================================"
echo " 8. El analista tampoco puede inventar una acción"
echo "================================================================"
pedir 201 "otra propuesta" POST /casos/evaluar '{"cliente_id":"CLI-009"}'
ID3=$(printf '%s' "$ULTIMA" | sed -n 's/.*"propuesta_id":"\([^"]*\)".*/\1/p')
pedir 422 "BLOQUEADO: fuera de la lista cerrada" \
      POST "/propuestas/$ID3/modificar" \
      '{"analista":"ana.perez","nueva_accion":"condonar_deuda"}'

echo "================================================================"
echo " 9. La bitácora registra los intentos bloqueados"
echo "================================================================"
curl -s "$API/bitacora" | tr ',' '\n' | grep -E '"evento"|"detalle"' | sed 's/^/  /' | head -40

echo
if [ "$FALLAS" -eq 0 ]; then
  printf '%sTodas las comprobaciones pasaron. Sin aprobación humana, la API no ejecuta.%s\n\n' "$VERDE" "$RESET"
else
  printf '%s%s comprobaciones fallaron.%s\n\n' "$ROJO" "$FALLAS" "$RESET"
  exit 1
fi
