// Cliente de la API. Muestra lo que el backend devuelve y dispara las llamadas
// que el analista pide. Nada más.
//
// REGLA DE ESTE ARCHIVO: acá no hay lógica de control.
//   - No decide si algo se puede aprobar, rechazar o ejecutar. Manda el pedido y
//     muestra lo que el backend conteste, incluido el rechazo.
//   - No conoce la lista de acciones: se la pregunta al backend (GET /acciones).
//   - No calcula estados: los estados llegan en la respuesta y se muestran.
// Si algo de esto hiciera falta validarlo, va al backend, no acá.

const API = "http://localhost:8000";

let clientesPorId = {};
let accionesPermitidas = [];

// ---------------------------------------------------------------------------
// Llamadas a la API
// ---------------------------------------------------------------------------

// Hace la llamada y, si es una acción del analista, deja el resultado FIJO en el
// panel de abajo. Devuelve el cuerpo tanto si salió bien como si el backend
// rechazó: el rechazo es información que el analista tiene que ver, no un error
// a esconder.
//
// `mostrar: false` es para las recargas internas (traer la cartera, refrescar la
// bandeja). Sin eso, el GET que viene después de cada acción escribe encima del
// resultado que el analista acaba de provocar y lo hace parpadear. El panel
// muestra lo que hiciste, no las tareas domésticas del front.
async function llamar(metodo, ruta, cuerpo, { mostrar = true } = {}) {
  const opciones = { method: metodo, headers: { "Content-Type": "application/json" } };
  if (cuerpo !== undefined) opciones.body = JSON.stringify(cuerpo);

  let respuesta, datos;
  try {
    respuesta = await fetch(API + ruta, opciones);
    datos = await respuesta.json();
  } catch (e) {
    if (mostrar) {
      fijarResultado({
        titulo: "SIN CONEXIÓN", ok: false, metodo, ruta,
        mensaje: `No se pudo contactar al backend en ${API}. ¿Está corriendo?`,
        detalle: String(e.message),
      });
    }
    return { ok: false, datos: null };
  }

  if (mostrar) {
    fijarResultado({
      titulo: `HTTP ${respuesta.status}`,
      ok: respuesta.ok,
      metodo, ruta, cuerpo,
      mensaje: respuesta.ok ? null : (datos && datos.detalle) || "El backend rechazó el pedido.",
      detalle: JSON.stringify(datos, null, 2),
    });
  }
  return { ok: respuesta.ok, datos };
}

// Deja el resultado a la vista hasta la próxima acción del analista. No se borra
// solo ni se vence: para la demo del gate hace falta poder leerlo con calma.
function fijarResultado({ titulo, ok, metodo, ruta, cuerpo, mensaje, detalle }) {
  const consola = document.getElementById("consola");
  const estado = document.getElementById("consola-estado");
  const linea = document.getElementById("consola-mensaje");
  const cuerpoEl = document.getElementById("consola-cuerpo");

  consola.classList.remove("oculta");
  consola.classList.toggle("hay-error", !ok);

  const hora = new Date().toLocaleTimeString("es-AR");
  estado.textContent =
    `${titulo} · ${metodo} ${ruta}${cuerpo ? " " + JSON.stringify(cuerpo) : ""} · ${hora}`;

  linea.textContent = mensaje || "";
  linea.hidden = !mensaje;

  cuerpoEl.className = ok ? "ok" : "error";
  cuerpoEl.textContent = detalle;
}

// ---------------------------------------------------------------------------
// Carga y dibujado
// ---------------------------------------------------------------------------

async function iniciar() {
  const clientes = await llamar("GET", "/clientes", undefined, { mostrar: false });
  if (!clientes.ok) return;
  clientesPorId = Object.fromEntries(clientes.datos.map((c) => [c.cliente_id, c]));

  const acciones = await llamar("GET", "/acciones", undefined, { mostrar: false });
  accionesPermitidas = acciones.ok ? acciones.datos : [];

  const selector = document.getElementById("cliente");
  selector.innerHTML = clientes.datos
    .map((c) => `<option value="${c.cliente_id}">${c.cliente_id} — ${c.nombre} ` +
                `(${c.dias_de_atraso} días)</option>`)
    .join("");

  await refrescarPropuestas();
}

async function refrescarPropuestas() {
  const { ok, datos } = await llamar("GET", "/propuestas", undefined, { mostrar: false });
  if (!ok) return;

  // Sólo separa para mostrar. El estado lo decidió el backend.
  const pendientes = datos.filter((p) => p.estado === "pendiente_de_aprobacion");
  const resueltas = datos.filter((p) => p.estado !== "pendiente_de_aprobacion");

  document.getElementById("contador-pendientes").textContent =
    pendientes.length ? `(${pendientes.length})` : "";

  document.getElementById("pendientes").innerHTML =
    pendientes.length
      ? pendientes.map(dibujarPendiente).join("")
      : `<p class="vacio">No hay propuestas esperando decisión. Evaluá un caso para empezar.</p>`;

  document.getElementById("resueltas").innerHTML =
    resueltas.length
      ? resueltas.map(dibujarResuelta).join("")
      : `<p class="vacio">Todavía no resolviste ninguna.</p>`;
}

function datosDelCliente(cliente_id) {
  const c = clientesPorId[cliente_id];
  if (!c) return "";
  const meses = c.historial_de_pagos
    .map((m) => `<span class="mes ${m}" title="${m}"></span>`)
    .join("");
  return `
    <div class="datos">
      <dl>
        <div><dt>Producto</dt><dd>${c.tipo_de_producto}</dd></div>
        <div><dt>Días de atraso</dt><dd>${c.dias_de_atraso}</dd></div>
        <div><dt>Monto adeudado</dt><dd>${c.monto_adeudado.toLocaleString("es-AR")}</dd></div>
        <div><dt>Cuota vencida</dt><dd>${c.cuota_vencida.toLocaleString("es-AR")}</dd></div>
        <div><dt>Antigüedad</dt><dd>${c.antiguedad_meses} meses</dd></div>
        <div><dt>Canal preferido</dt><dd>${c.canal_preferido}</dd></div>
      </dl>
      <div class="historial">${meses}
        <span class="leyenda">historial de pagos, del mes más viejo al más reciente</span>
      </div>
    </div>`;
}

function dibujarPendiente(p) {
  const c = clientesPorId[p.cliente_id] || {};
  const opciones = accionesPermitidas
    .map((a) => `<option value="${a}" ${a === p.accion ? "selected" : ""}>${a}</option>`)
    .join("");

  const avisoSinDatos = p.consulto_datos ? "" :
    `<div class="aviso">El agente propuso sin consultar los datos del cliente.
      Revisá esta propuesta con especial atención.</div>`;

  return `
  <article class="tarjeta" data-id="${p.propuesta_id}">
    <div class="tarjeta-encabezado">
      <div>
        <span class="cliente-nombre">${c.nombre || p.cliente_id}</span>
        <span class="cliente-id">${p.cliente_id} · ${p.propuesta_id}</span>
      </div>
      <span class="accion">${p.accion}</span>
    </div>

    ${datosDelCliente(p.cliente_id)}

    <p class="razonamiento">${escapar(p.razonamiento)}</p>
    <p class="tono"><strong>Tono sugerido:</strong> ${escapar(p.tono_sugerido || "—")}</p>
    ${avisoSinDatos}

    <div class="acciones">
      <button class="aprobar" data-hacer="aprobar">Aprobar</button>
      <button class="rechazar" data-hacer="rechazar">Rechazar</button>
      <input type="text" data-campo="comentario"
             placeholder="Comentario (obligatorio para rechazar)">
    </div>
    <div class="acciones acciones-fila-2">
      <select data-campo="nueva_accion">${opciones}</select>
      <button data-hacer="modificar">Cambiar la acción y aprobar</button>
      <button class="enlace" data-hacer="intentar-ejecutar"
              title="Llama a POST /propuestas/{id}/ejecutar sin aprobar. El backend responde 403.">
        intentar ejecutar sin aprobar (demo)
      </button>
    </div>
  </article>`;
}

function dibujarResuelta(p) {
  const c = clientesPorId[p.cliente_id] || {};
  const modificada = p.fue_modificada_por_el_analista
    ? `<span class="cliente-id">el agente había propuesto ${p.accion_propuesta_originalmente}</span>`
    : "";
  const ejecutar = p.estado === "aprobada"
    ? `<button class="primario" data-hacer="ejecutar">Ejecutar la acción</button>`
    : "";
  const resultado = p.resultado_de_ejecucion
    ? `<div class="datos">${escapar(p.resultado_de_ejecucion)}</div>` : "";

  return `
  <article class="tarjeta" data-id="${p.propuesta_id}">
    <div class="tarjeta-encabezado">
      <div>
        <span class="cliente-nombre">${c.nombre || p.cliente_id}</span>
        <span class="cliente-id">${p.cliente_id} · ${p.propuesta_id}</span>
      </div>
      <span class="accion">${p.accion}</span>
    </div>
    <p class="tono">
      <span class="estado ${p.estado}">${p.estado}</span>
      ${p.decidida_por ? ` · por ${escapar(p.decidida_por)}` : ""}
      ${p.comentario_del_analista ? ` · "${escapar(p.comentario_del_analista)}"` : ""}
      ${modificada}
    </p>
    ${resultado}
    ${ejecutar ? `<div class="acciones">${ejecutar}</div>` : ""}
  </article>`;
}

function escapar(texto) {
  const d = document.createElement("div");
  d.textContent = texto == null ? "" : texto;
  return d.innerHTML;
}

// ---------------------------------------------------------------------------
// Qué hace cada botón
//
// Cada uno arma un pedido y lo manda. Ninguno decide si la operación corresponde:
// eso lo resuelve el backend y la respuesta se muestra tal cual.
// ---------------------------------------------------------------------------

document.addEventListener("click", async (evento) => {
  const boton = evento.target.closest("[data-hacer]");
  if (!boton) return;

  const tarjeta = boton.closest(".tarjeta");
  const id = tarjeta.dataset.id;
  const analista = document.getElementById("analista").value.trim();
  const campo = (nombre) => tarjeta.querySelector(`[data-campo="${nombre}"]`);
  const comentario = campo("comentario") ? campo("comentario").value.trim() : "";

  boton.disabled = true;
  switch (boton.dataset.hacer) {
    case "aprobar":
      await llamar("POST", `/propuestas/${id}/aprobar`, { analista, comentario: comentario || null });
      break;
    case "rechazar":
      // El motivo se manda como lo escribió el analista. Si está vacío, el backend
      // lo rechaza: la obligatoriedad la define el contrato de la API, no el front.
      await llamar("POST", `/propuestas/${id}/rechazar`, { analista, motivo: comentario });
      break;
    case "modificar":
      await llamar("POST", `/propuestas/${id}/modificar`, {
        analista, nueva_accion: campo("nueva_accion").value, comentario: comentario || null,
      });
      break;
    case "ejecutar":
    case "intentar-ejecutar":
      // Es exactamente la misma llamada en los dos casos. La única diferencia es
      // el estado en que está la propuesta, y eso lo evalúa el gate en el backend.
      await llamar("POST", `/propuestas/${id}/ejecutar`);
      break;
  }
  boton.disabled = false;
  await refrescarPropuestas();
});

document.getElementById("evaluar").addEventListener("click", async (evento) => {
  const boton = evento.currentTarget;
  const cliente_id = document.getElementById("cliente").value;
  boton.disabled = true;
  boton.textContent = "El agente está analizando…";
  await llamar("POST", "/casos/evaluar", { cliente_id });
  boton.disabled = false;
  boton.textContent = "Evaluar con el agente";
  await refrescarPropuestas();
});

document.getElementById("cerrar-consola").addEventListener("click", () => {
  document.getElementById("consola").classList.toggle("oculta");
});

iniciar();
