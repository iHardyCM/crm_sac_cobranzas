const MOWA_API = `${window.location.protocol}//${window.location.hostname}:8000/respuestas-mowa/consultar`;
// La vista lee CobAuto.dbo.CRM_SMS_*; la carga de Mowa se inicia por separado.
const MOWA_RAIZ = MOWA_API.replace(/\/consultar$/, "");
const MOWA_SYNC_API = `${MOWA_RAIZ}/sincronizacion`;
let mowaFilas = [];
let mowaAlcanceCarteras = null;
let mowaConsultaAbort = null;
let mowaDetener = false;
let mowaPagina = 1;
let mowaConsultaCompleta = false;
let mowaAdvertenciasConsulta = [];
let mowaConversacionesVisibles = [];
let mowaChatClave = null;
let mowaGruposCache = null;
let mowaExcluidasInactivas = 0;
let mowaSinAtenderResumen = null;
let mowaResumenSolicitud = 0;
let mowaModoAcumulado = false;
let mowaCarteraAcumulada = null;
let mowaSyncTimer = null;
let mowaSyncObservando = false;
let mowaSyncEsperadoId = null;
let mowaSyncInicio = 0;
const mowaChatEnvios = new Map();
const mowaChatHistorico = new Map();
let mowaModoBandeja = false;
let mowaPuedeAsignar = false;
let mowaAsignaciones = new Map();
let mowaAgentes = [];
let mowaSeleccionados = new Map();
let mowaClientesAsignando = [];
let mowaAgentesModal = [];
let mowaModoControl = false;
let mowaControlFiltro = null;
let mowaControlCartera = null;
let mowaControlSolicitud = 0;
let mowaControlCargado = false;
const MOWA_MAX_LOTE = 500;

document.addEventListener("DOMContentLoaded", async () => {
    if (typeof asegurarSesionBackend !== "function" || !(await asegurarSesionBackend())) return;
    const hoy = new Date();
    // Por defecto: respuestas recibidas ayer y hoy (día calendario anterior, incluye domingos).
    document.getElementById("mowaDesde").value = fechaLocal(new Date(hoy.getFullYear(), hoy.getMonth(), hoy.getDate() - 1));
    document.getElementById("mowaHasta").value = fechaLocal(hoy);
    document.getElementById("mowaFiltros").addEventListener("submit", consultarMowa);
    document.getElementById("mowaBandejaActualizar").addEventListener("click", cargarBandejaMowa);
    document.getElementById("mowaAsignacionFiltro").addEventListener("change", () => { mowaPagina = 1; pintarMowa(); });
    document.getElementById("mowaAsignarCerrar").addEventListener("click", () => document.getElementById("mowaAsignarModal").close());
    document.getElementById("mowaAsignarModal").addEventListener("click", event => {
        const modal = event.currentTarget;
        if (event.target !== modal) return;
        const r = modal.getBoundingClientRect();
        if (event.clientX < r.left || event.clientX > r.right || event.clientY < r.top || event.clientY > r.bottom) modal.close();
    });
    document.getElementById("mowaAsignarForm").addEventListener("submit", guardarAsignacionMowa);
    document.getElementById("mowaAsignarBuscar").addEventListener("input", pintarAgentesAsignacionMowa);
    document.getElementById("mowaAsignarLista").addEventListener("click", event => {
        const opcion = event.target.closest("[data-agente]");
        if (!opcion) return;
        document.getElementById("mowaAsignarAgente").value = opcion.dataset.agente;
        pintarAgentesAsignacionMowa();
    });
    document.getElementById("mowaSeleccionPagina").addEventListener("change", event => seleccionarPaginaMowa(event.target.checked));
    document.getElementById("mowaSeleccionFiltrados").addEventListener("click", seleccionarFiltradosMowa);
    document.getElementById("mowaSeleccionLimpiar").addEventListener("click", limpiarSeleccionMowa);
    document.getElementById("mowaAsignarSeleccion").addEventListener("click", abrirAsignacionMultipleMowa);
    document.getElementById("mowaSyncBoton").addEventListener("click", iniciarActualizacionMowa);
    document.getElementById("mowaCuenta").addEventListener("change", () => {
        ++mowaResumenSolicitud;
        mowaSinAtenderResumen = null;
        mowaModoAcumulado = false;
        mowaCarteraAcumulada = null;
        mowaModoControl = false;
        mowaControlFiltro = null;
        mowaFilas = [];
        mowaGruposCache = null;
        limpiarSeleccionMowa();
        mowaConsultaCompleta = false;
        document.getElementById("mowaSinAtenderTotal").textContent = "—";
        document.getElementById("mowaSinAtenderDetalle").textContent = "Pulsa Consultar para actualizar esta cuenta.";
        document.getElementById("mowaSinAtender").disabled = true;
        document.getElementById("mowaVerCarteras").disabled = true;
        document.getElementById("mowaExportar").textContent = "Exportar Excel";
        document.getElementById("mowaExportar").removeAttribute("title");
        document.getElementById("mowaCardPendientesTitulo").textContent = "Sin gestión posterior (rango)";
        actualizarResumenMowa(false, false);
        pintarMowa();
        document.getElementById("mowaAlcance").textContent = "Pulsa Consultar para cargar la cuenta seleccionada.";
    });
    for (const id of ["mowaEstado", "mowaCartera", "mowaOrden", "mowaTamano", "mowaBuscar"]) {
        document.getElementById(id).addEventListener(id === "mowaBuscar" ? "input" : "change", () => {
            mowaPagina = 1;
            pintarMowa();
        });
    }
    document.getElementById("mowaMas").addEventListener("click", () => {
        cambiarPaginaMowa(1);
    });
    document.getElementById("mowaAnterior").addEventListener("click", () => {
        cambiarPaginaMowa(-1);
    });
    document.getElementById("mowaExportar").addEventListener("click", exportarMowa);
    document.getElementById("mowaSinAtender").addEventListener("click", () => descargarSinAtenderMowa());
    document.getElementById("mowaVerCarteras").addEventListener("click", abrirCarterasMowa);
    document.getElementById("mowaControlAbrir").addEventListener("click", abrirControlMowa);
    document.getElementById("mowaControlCerrar").addEventListener("click", () => document.getElementById("mowaControlModal").close());
    document.getElementById("mowaControlActualizar").addEventListener("click", cargarControlMowa);
    document.getElementById("mowaControlCartera").addEventListener("change", cargarControlMowa);
    document.getElementById("mowaControlModal").addEventListener("click", clickControlMowa);
    document.getElementById("mowaCarterasCerrar").addEventListener("click", () => document.getElementById("mowaCarterasModal").close());
    document.getElementById("mowaCarterasModal").addEventListener("click", clickCarterasMowa);
    document.getElementById("mowaCarterasModal").addEventListener("keydown", teclaCarterasMowa);
    document.getElementById("mowaCancelar").addEventListener("click", () => {
        mowaDetener = true;
        mowaConsultaAbort?.abort();
    });
    document.getElementById("mowaCardPendientes").addEventListener("click", () => {
        document.getElementById("mowaEstado").value = "PENDIENTE";
        document.getElementById("mowaCartera").value = "";
        document.getElementById("mowaBuscar").value = "";
        document.getElementById("mowaOrden").value = "antiguo";
        mowaPagina = 1;
        pintarMowa();
        document.getElementById("mowaDetalle").scrollIntoView({behavior: "smooth", block: "start"});
    });
    document.getElementById("mowaTabla").addEventListener("click", async event => {
        const asignar = event.target.closest("[data-asignar]");
        if (asignar) { abrirAsignacionMowa(mowaConversacionesVisibles[Number(asignar.dataset.asignar)]); return; }
        const abrir = event.target.closest("[data-chat]");
        if (abrir) { abrirChatMowa(mowaConversacionesVisibles[Number(abrir.dataset.chat)]); return; }
        const boton = event.target.closest("[data-copiar]");
        if (!boton) return;
        try {
            await navigator.clipboard.writeText(boton.dataset.copiar);
            boton.textContent = "Copiado";
            setTimeout(() => { boton.textContent = "Copiar DNI"; }, 1500);
        } catch (_) {
            avisoMowa("No se pudo copiar el DNI. Puedes seleccionarlo en la tabla.", true);
        }
    });
    document.getElementById("mowaTabla").addEventListener("change", event => {
        const check = event.target.closest("[data-seleccionar]");
        if (!check) return;
        const grupo = mowaConversacionesVisibles[Number(check.dataset.seleccionar)];
        if (!grupo) return;
        seleccionarGrupoMowa(grupo, check.checked);
    });
    document.getElementById("mowaChatCerrar").addEventListener("click", () => document.getElementById("mowaChat").close());
    document.getElementById("mowaChat").addEventListener("click", cerrarChatFueraMowa);
    document.getElementById("mowaChatTexto").addEventListener("input", () => {
        document.getElementById("mowaChatCaracteres").textContent = `${document.getElementById("mowaChatTexto").value.length}/160`;
    });
    document.getElementById("mowaChatForm").addEventListener("submit", enviarChatMowa);
    document.getElementById("mowaEstado").value = "PENDIENTE";
    document.getElementById("mowaOrden").value = "antiguo";
    if (await cargarOpcionesMowa()) {
        document.getElementById("mowaCuenta").value = "";
        if (mowaModoBandeja) await cargarBandejaMowa();
        else await consultarMowa();
        if (!document.getElementById("mowaSyncAcciones").hidden) consultarEstadoActualizacionMowa();
    }
});

function fechaLocal(fecha) {
    return `${fecha.getFullYear()}-${String(fecha.getMonth()+1).padStart(2,"0")}-${String(fecha.getDate()).padStart(2,"0")}`;
}

async function cargarOpcionesMowa() {
    try {
        const response = await fetchConSesion(MOWA_API.replace(/\/consultar$/, "/opciones"));
        const result = await response.json();
        if (!response.ok) throw new Error(result.detail || "No se pudieron cargar las cuentas autorizadas.");
        mowaAlcanceCarteras = result.alcance_carteras;
        mowaModoBandeja = result.modo === "BANDEJA";
        mowaPuedeAsignar = result.puede_asignar === true;
        document.getElementById("mowaBandejaBar").hidden = !mowaModoBandeja;
        document.querySelector(".mowa-top").hidden = mowaModoBandeja;
        document.querySelector(".mowa-resumen").hidden = mowaModoBandeja;
        document.querySelector(".mowa-nota").hidden = mowaModoBandeja;
        document.getElementById("mowaAsignacionControl").hidden = !mowaPuedeAsignar;
        document.getElementById("mowaControlAbrir").hidden = !mowaPuedeAsignar;
        document.getElementById("mowaSeleccionCol").hidden = !mowaPuedeAsignar;
        if (mowaModoBandeja) {
            document.title = "Mis asignaciones | CRM Cobranzas";
            document.querySelector(".mowa-heading h2").textContent = "Mis asignaciones";
            document.querySelector(".mowa-heading p").textContent = "Clientes que te asignaron y aún tienen respuestas sin gestión posterior.";
            document.getElementById("mowaExportar").hidden = true;
            document.getElementById("mowaEstado").closest("label").hidden = true;
        }
        document.getElementById("mowaSyncAcciones").hidden = !result.puede_actualizar;
        const select = document.getElementById("mowaCuenta");
        select.innerHTML = `<option value="">${mowaAlcanceCarteras === null ? "Todas las cuentas" : "Todas mis cuentas"}</option>`;
        for (const cuenta of result.cuentas || []) {
            const option = document.createElement("option");
            option.value = cuenta.id;
            option.textContent = cuenta.nombre;
            select.appendChild(option);
        }
        const carteras = [...new Set((result.cuentas || []).flatMap(c => c.carteras || []))].sort((a, b) => a - b);
        document.getElementById("mowaControlCartera").innerHTML = '<option value="">Todas mis carteras</option>' +
            carteras.map(id => `<option value="${id}">Cartera ${id}</option>`).join("");
        document.getElementById("mowaCardAlcance").textContent = textoAlcanceMowa();
        return true;
    } catch (error) {
        avisoMowa(error.message || "No se pudieron cargar las cuentas.", true);
        return false;
    }
}

function claveAsignacionMowa(cartera, cliente) {
    return `${cartera}:${cliente}`;
}

async function cargarAsignacionesMowa() {
    if (!mowaPuedeAsignar) return;
    try {
        const response = await fetchConSesion(`${MOWA_RAIZ}/asignaciones`);
        const result = await response.json();
        if (!response.ok) throw new Error(result.detail || "No se pudieron cargar las asignaciones.");
        mowaAgentes = result.agentes || [];
        mowaAsignaciones = new Map((result.asignaciones || []).map(a =>
            [claveAsignacionMowa(a.idcartera, a.idcliente), a]));
        pintarMowa();
    } catch (error) {
        avisoMowa(error.message || "No se pudieron cargar las asignaciones.", true);
    }
}

async function cargarBandejaMowa() {
    if (!mowaModoBandeja) return;
    const boton = document.getElementById("mowaBandejaActualizar");
    boton.disabled = true;
    document.getElementById("mowaBandejaResumen").textContent = "Actualizando clientes asignados…";
    document.getElementById("mowaTabla").innerHTML = '<tr><td colspan="6" class="mowa-vacio">Cargando tu bandeja…</td></tr>';
    try {
        const response = await fetchConSesion(`${MOWA_RAIZ}/bandeja`);
        const result = await response.json();
        if (!response.ok) throw new Error(result.detail || "No se pudo cargar tu bandeja.");
        mowaFilas = (result.grupos || []).flatMap(g => g.filas || []);
        mowaGruposCache = null;
        mowaPagina = 1;
        mowaConsultaCompleta = result.completo !== false;
        mowaAdvertenciasConsulta = result.advertencias || [];
        document.getElementById("mowaEstado").value = "PENDIENTE";
        actualizarCarterasMowa();
        pintarMowa();
        pintarSincronizacionMowa(result.sincronizacion);
        const alcance = `${result.clientes} ${result.clientes === 1 ? "cliente" : "clientes"} · ${result.respuestas} respuestas pendientes${result.completo === false ? " · datos parciales" : ""}`;
        document.getElementById("mowaBandejaResumen").textContent = alcance;
        document.getElementById("mowaAlcance").textContent = alcance;
        avisoMowa(resumirAdvertenciasMowa(mowaAdvertenciasConsulta));
    } catch (error) {
        document.getElementById("mowaBandejaResumen").textContent = "No se pudo actualizar";
        avisoMowa(error.message || "No se pudo cargar tu bandeja.", true);
    } finally { boton.disabled = false; }
}

function clienteAsignableMowa(grupo) {
    const r = grupo?.ultimo;
    return r && grupo.estado === "PENDIENTE" && r.idcartera && r.idcliente
        ? {idcartera: Number(r.idcartera), idcliente: Number(r.idcliente),
            nombre: r.cliente || r.dni || `Cliente ${r.idcliente}`}
        : null;
}

function seleccionarGrupoMowa(grupo, seleccionado) {
    if (!mowaPuedeAsignar) return;
    const cliente = clienteAsignableMowa(grupo);
    if (!cliente) return;
    const clave = claveAsignacionMowa(cliente.idcartera, cliente.idcliente);
    if (seleccionado && !mowaSeleccionados.has(clave) && mowaSeleccionados.size >= MOWA_MAX_LOTE) {
        avisoMowa(`Selecciona hasta ${MOWA_MAX_LOTE} clientes por lote.`, true);
        pintarMowa();
        return;
    }
    if (seleccionado) mowaSeleccionados.set(clave, cliente);
    else mowaSeleccionados.delete(clave);
    pintarMowa();
}

function seleccionarPaginaMowa(seleccionado) {
    const elegibles = mowaConversacionesVisibles.map(clienteAsignableMowa).filter(Boolean);
    if (seleccionado && new Set([...mowaSeleccionados.keys(), ...elegibles.map(c => claveAsignacionMowa(c.idcartera, c.idcliente))]).size > MOWA_MAX_LOTE) {
        avisoMowa(`El lote admite hasta ${MOWA_MAX_LOTE} clientes. Filtra la tabla para dividirlo.`, true);
        pintarMowa();
        return;
    }
    for (const cliente of elegibles) {
        const clave = claveAsignacionMowa(cliente.idcartera, cliente.idcliente);
        if (seleccionado) mowaSeleccionados.set(clave, cliente);
        else mowaSeleccionados.delete(clave);
    }
    pintarMowa();
}

function seleccionarFiltradosMowa() {
    const elegibles = filtrarOrdenarMowa().map(clienteAsignableMowa).filter(Boolean);
    if (new Set([...mowaSeleccionados.keys(), ...elegibles.map(c => claveAsignacionMowa(c.idcartera, c.idcliente))]).size > MOWA_MAX_LOTE) {
        avisoMowa(`Hay más de ${MOWA_MAX_LOTE} clientes. Filtra por cartera o fecha y vuelve a seleccionar.`, true);
        return;
    }
    for (const cliente of elegibles) mowaSeleccionados.set(
        claveAsignacionMowa(cliente.idcartera, cliente.idcliente), cliente);
    pintarMowa();
}

function limpiarSeleccionMowa() {
    mowaSeleccionados.clear();
    const barra = document.getElementById("mowaSeleccionBar");
    if (barra) barra.hidden = true;
    const check = document.getElementById("mowaSeleccionPagina");
    if (check) { check.checked = false; check.indeterminate = false; }
    if (mowaPuedeAsignar) pintarMowa();
}

function agentesComunesMowa(carteras) {
    const porUsuario = new Map();
    for (const agente of mowaAgentes) {
        if (!carteras.includes(Number(agente.idcartera))) continue;
        const actual = porUsuario.get(agente.usuario) || {usuario: agente.usuario,
            nombre: agente.nombre, carteras: new Set()};
        actual.carteras.add(Number(agente.idcartera));
        porUsuario.set(agente.usuario, actual);
    }
    return [...porUsuario.values()].filter(a => carteras.every(c => a.carteras.has(c)))
        .sort((a, b) => String(a.nombre).localeCompare(String(b.nombre), "es"));
}

function abrirAsignacionMowa(grupo) {
    if (!mowaPuedeAsignar) return;
    const cliente = clienteAsignableMowa(grupo);
    if (cliente) abrirModalAsignacionMowa([cliente]);
}

function abrirAsignacionMultipleMowa() {
    if (!mowaPuedeAsignar || !mowaSeleccionados.size) return;
    abrirModalAsignacionMowa([...mowaSeleccionados.values()]);
}

function abrirModalAsignacionMowa(clientes) {
    mowaClientesAsignando = clientes;
    const carteras = [...new Set(clientes.map(c => c.idcartera))].sort((a, b) => a - b);
    mowaAgentesModal = agentesComunesMowa(carteras);
    const individual = clientes.length === 1;
    const actual = individual ? mowaAsignaciones.get(claveAsignacionMowa(clientes[0].idcartera, clientes[0].idcliente)) : null;
    document.getElementById("mowaAsignarTitulo").textContent = individual
        ? (actual ? "Cambiar agente" : "Asignar cliente") : `Asignar ${clientes.length} clientes`;
    document.getElementById("mowaAsignarCliente").textContent = individual
        ? `${clientes[0].nombre} · cartera ${clientes[0].idcartera}`
        : `${carteras.length === 1 ? "Cartera" : "Carteras"} ${carteras.join(", ")} · el agente debe tener acceso a todas`;
    document.getElementById("mowaAsignarBuscar").value = "";
    document.getElementById("mowaAsignarAgente").value = actual?.agente_usuario || "";
    document.getElementById("mowaAsignarAviso").textContent = mowaAgentesModal.length
        ? (actual ? `Responsable actual: ${actual.agente_nombre || actual.agente_usuario}` : "")
        : "No hay agentes con acceso a todas estas carteras. Filtra y selecciona una cartera por vez.";
    document.getElementById("mowaAsignarGuardar").textContent = individual ? "Guardar asignación" : `Asignar ${clientes.length} clientes`;
    document.getElementById("mowaAsignarGuardar").disabled = !mowaAgentesModal.length;
    pintarAgentesAsignacionMowa();
    document.getElementById("mowaAsignarModal").showModal();
    document.getElementById("mowaAsignarBuscar").focus();
}

function pintarAgentesAsignacionMowa() {
    const termino = document.getElementById("mowaAsignarBuscar").value.trim()
        .normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
    const elegido = document.getElementById("mowaAsignarAgente").value;
    const visibles = mowaAgentesModal.filter(a => `${a.nombre} ${a.usuario}`
        .normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().includes(termino));
    document.getElementById("mowaAsignarLista").innerHTML = visibles.length
        ? visibles.map(a => `<button type="button" role="option" data-agente="${escMowa(a.usuario)}" aria-selected="${a.usuario === elegido}"><strong>${escMowa(a.nombre || a.usuario)}</strong><small>${escMowa(a.usuario)}</small></button>`).join("")
        : `<div class="mowa-agentes-vacio">${mowaAgentesModal.length ? "No hay agentes con ese nombre o DNI." : "No hay agentes disponibles para esta selección."}</div>`;
    const agente = mowaAgentesModal.find(a => a.usuario === elegido);
    document.getElementById("mowaAsignarSeleccionado").textContent = agente
        ? `Seleccionado: ${agente.nombre} · ${agente.usuario}` : "Selecciona un agente";
}

async function guardarAsignacionMowa(event) {
    event.preventDefault();
    const clientes = mowaClientesAsignando;
    const agente = document.getElementById("mowaAsignarAgente").value;
    if (!clientes.length || !agente || !mowaAgentesModal.some(a => a.usuario === agente)) return;
    const boton = document.getElementById("mowaAsignarGuardar");
    const aviso = document.getElementById("mowaAsignarAviso");
    boton.disabled = true;
    aviso.textContent = "Guardando asignación…";
    try {
        const individual = clientes.length === 1;
        const ruta = `${MOWA_RAIZ}/asignaciones${individual ? "" : "/lote"}`;
        const payload = individual
            ? {idcartera: clientes[0].idcartera, idcliente: clientes[0].idcliente,
                agente_usuario: agente}
            : {clientes: clientes.map(c => ({idcartera: c.idcartera, idcliente: c.idcliente})), agente_usuario: agente};
        const response = await fetchConSesion(ruta, {
            method: "PUT", headers: {"Content-Type": "application/json"}, body: JSON.stringify(payload),
        });
        const result = await response.json();
        if (!response.ok) throw new Error(result.detail || "No se pudo guardar la asignación.");
        const guardadas = individual ? [result] : result.asignaciones;
        const nombre = mowaAgentesModal.find(a => a.usuario === agente)?.nombre || agente;
        for (const item of guardadas) mowaAsignaciones.set(
            claveAsignacionMowa(item.idcartera, item.idcliente), {...item, agente_nombre: nombre});
        mowaSeleccionados.clear();
        document.getElementById("mowaAsignarModal").close();
        pintarMowa();
        if (mowaModoControl && mowaControlFiltro) await abrirDetalleControlMowa(mowaControlFiltro, false);
        const cambios = individual ? Number(result.cambio) : result.cambios;
        avisoMowa(cambios ? `${cambios} ${cambios === 1 ? "cliente asignado" : "clientes asignados"} a ${nombre}.` : "Estos clientes ya estaban asignados a ese agente.");
    } catch (error) {
        aviso.textContent = error.message || "No se pudo guardar la asignación.";
    } finally { boton.disabled = false; }
}

function abrirControlMowa() {
    if (!mowaPuedeAsignar) return;
    document.getElementById("mowaControlModal").showModal();
    cargarControlMowa();
}

async function cargarControlMowa() {
    if (!mowaPuedeAsignar) return;
    const solicitud = ++mowaControlSolicitud;
    mowaControlCargado = false;
    const boton = document.getElementById("mowaControlActualizar");
    const aviso = document.getElementById("mowaControlAviso");
    const cartera = document.getElementById("mowaControlCartera").value;
    const params = new URLSearchParams();
    if (cartera) params.set("cartera", cartera);
    boton.disabled = true;
    aviso.textContent = "Calculando clientes pendientes y responsables…";
    aviso.className = "mowa-control-aviso";
    for (const id of ["mowaControlTotal", "mowaControlSinAsignar", "mowaControlAsignados", "mowaControlAntiguos"])
        document.getElementById(id).textContent = "…";
    document.getElementById("mowaControlAgentes").innerHTML = "";
    try {
        const response = await fetchConSesion(`${MOWA_RAIZ}/control-asignaciones${params.size ? `?${params}` : ""}`);
        const result = await response.json();
        if (solicitud !== mowaControlSolicitud) return;
        if (!response.ok) throw new Error(result.detail || "No se pudo cargar el control.");
        mowaControlCargado = true;
        document.getElementById("mowaControlTotal").textContent = result.completo ? String(result.clientes) : `${result.clientes}+`;
        document.getElementById("mowaControlSinAsignar").textContent = result.completo ? String(result.sin_asignar) : `${result.sin_asignar}+`;
        document.getElementById("mowaControlAsignados").textContent = result.completo ? String(result.asignados) : `${result.asignados}+`;
        document.getElementById("mowaControlAntiguos").textContent = result.completo ? String(result.antiguos) : `${result.antiguos}+`;
        document.getElementById("mowaControlAlcance").textContent = `${result.respuestas} respuestas · desde ${formatoFechaSoloMowa(result.desde)}`;
        document.getElementById("mowaControlAgentes").innerHTML = (result.agentes || []).length
            ? result.agentes.map(a => `<div class="mowa-control-agente"><div><strong>${escMowa(a.nombre)}</strong><small>${escMowa(a.usuario)}${a.primera_recepcion ? ` · primera espera ${escMowa(formatoFechaSoloMowa(a.primera_recepcion))}` : ""}</small></div><div><b>${a.clientes}</b><small>clientes</small></div><div class="mowa-control-respuestas"><b>${a.respuestas}</b><small>respuestas</small></div><div class="mowa-control-antiguo"><b>${a.antiguos}</b><small>antiguos</small></div><button type="button" data-control-agente="${escMowa(a.usuario)}" ${a.clientes ? "" : "disabled"}>Ver pendientes</button></div>`).join("")
            : '<p class="mowa-small">No hay agentes en las carteras seleccionadas.</p>';
        const sync = result.sincronizacion;
        const ultimo = sync?.ultimo_intento;
        const atrasada = !sync?.fin || sync.desactualizada || sync.resultado === "CON_AVISOS" || ultimo?.resultado === "ERROR";
        const texto = !sync?.fin ? "Aún no hay una sincronización completada."
            : `Última carga ${formatoFechaMowa(sync.fin)}${sync.resultado === "CON_AVISOS" ? ` · ${ultimo?.fin === sync.fin && ultimo.avisos != null ? `${ultimo.avisos} avisos` : "con avisos"}` : ""}${sync.desactualizada ? " · sin actualización reciente" : ""}.`;
        const intento = ultimo?.resultado === "ERROR" ? ` Último intento fallido: ${formatoFechaMowa(ultimo.fin || ultimo.inicio)}.` : "";
        document.getElementById("mowaControlSync").textContent = `${texto}${intento}${atrasada ? " Los conteos pueden omitir respuestas recientes. Revisa la actualización SMS en la parte superior." : ""}`;
        document.getElementById("mowaControlSync").classList.toggle("alerta", atrasada);
        aviso.textContent = result.completo === false
            ? `Conteo parcial: ${resumirAdvertenciasMowa(result.advertencias) || "no se verificaron todas las gestiones."}`
            : "Selecciona un número o un agente para abrir sus clientes pendientes acumulados.";
        aviso.classList.toggle("error", result.completo === false);
    } catch (error) {
        if (solicitud !== mowaControlSolicitud) return;
        aviso.textContent = error.message || "No se pudo cargar el control de asignaciones.";
        aviso.classList.add("error");
    } finally { if (solicitud === mowaControlSolicitud) boton.disabled = false; }
}

function clickControlMowa(event) {
    const dialogo = document.getElementById("mowaControlModal");
    const accion = event.target.closest?.("[data-control-agente]");
    if (accion) { if (mowaControlCargado) abrirDetalleControlMowa(accion.dataset.controlAgente); return; }
    if (event.target !== dialogo) return;
    const r = dialogo.getBoundingClientRect();
    if (event.clientX < r.left || event.clientX > r.right || event.clientY < r.top || event.clientY > r.bottom) dialogo.close();
}

async function abrirDetalleControlMowa(agente, desplazar = true) {
    if (!mowaPuedeAsignar) return;
    const cartera = document.getElementById("mowaControlCartera").value;
    const params = new URLSearchParams({agente});
    if (cartera) params.set("cartera", cartera);
    const cargando = document.getElementById("mowaCargando");
    cargando.hidden = false;
    document.getElementById("mowaProgreso").textContent = "Abriendo clientes pendientes del control de asignaciones.";
    try {
        const response = await fetchConSesion(`${MOWA_RAIZ}/control-asignaciones?${params}`);
        const result = await response.json();
        if (!response.ok) throw new Error(result.detail || "No se pudieron abrir los pendientes.");
        mowaModoControl = true;
        mowaControlFiltro = agente;
        mowaControlCartera = cartera || null;
        mowaModoAcumulado = false;
        mowaCarteraAcumulada = null;
        mowaFilas = (result.grupos || []).flatMap(g => g.filas || []);
        mowaAsignaciones = new Map((result.asignaciones || []).map(a =>
            [claveAsignacionMowa(a.idcartera, a.idcliente), a]));
        mowaGruposCache = null;
        mowaSeleccionados.clear();
        mowaPagina = 1;
        mowaConsultaCompleta = result.completo !== false;
        mowaAdvertenciasConsulta = result.advertencias || [];
        mowaExcluidasInactivas = 0;
        document.getElementById("mowaEstado").value = "PENDIENTE";
        document.getElementById("mowaAsignacionFiltro").value = "";
        document.getElementById("mowaOrden").value = "antiguo";
        document.getElementById("mowaBuscar").value = "";
        document.getElementById("mowaCardPendientesTitulo").textContent = "Sin gestión posterior (acumulado)";
        document.getElementById("mowaExportar").textContent = "Excel de asignaciones";
        document.getElementById("mowaExportar").title = "Incluye todos los pendientes del grupo abierto, aunque uses Buscar o cambies de página.";
        actualizarCarterasMowa();
        if (cartera) document.getElementById("mowaCartera").value = cartera;
        pintarSincronizacionMowa(result.sincronizacion);
        actualizarResumenMowa(mowaConsultaCompleta, true);
        pintarMowa();
        const agenteNombre = agente === "TODOS" ? "todos" : agente === "SIN_ASIGNAR" ? "sin asignar"
            : result.agentes.find(a => a.usuario === agente)?.nombre || agente;
        document.getElementById("mowaAlcance").textContent = `${result.clientes_detalle} clientes · ${result.respuestas_detalle} respuestas pendientes · ${agenteNombre}${cartera ? ` · cartera ${cartera}` : ""} · acumuladas desde ${formatoFechaSoloMowa(result.desde)}${result.completo === false ? " · parcial" : ""}`;
        avisoMowa(resumirAdvertenciasMowa(mowaAdvertenciasConsulta));
        if (dialogoAbiertoMowa("mowaControlModal")) document.getElementById("mowaControlModal").close();
        if (desplazar) document.getElementById("mowaDetalle").scrollIntoView({behavior: "smooth", block: "start"});
    } catch (error) {
        avisoMowa(error.message || "No se pudieron abrir los clientes.", true);
    } finally { cargando.hidden = true; }
}

function dialogoAbiertoMowa(id) { return document.getElementById(id).open === true; }

function mostrarEstadoActualizacionMowa(texto, resultado = "") {
    const el = document.getElementById("mowaSyncEstado");
    el.textContent = texto;
    el.hidden = !texto;
    el.dataset.resultado = resultado;
}

function programarEstadoActualizacionMowa() {
    clearTimeout(mowaSyncTimer);
    mowaSyncTimer = setTimeout(consultarEstadoActualizacionMowa, 5000);
}

async function iniciarActualizacionMowa() {
    const boton = document.getElementById("mowaSyncBoton");
    boton.disabled = true;
    boton.textContent = "Iniciando…";
    mostrarEstadoActualizacionMowa("Solicitando actualización a Mowa…");
    try {
        const dias = Number(document.getElementById("mowaSyncDias").value);
        const response = await fetchConSesion(MOWA_SYNC_API, {
            method: "POST", headers: {"Content-Type": "application/json"},
            body: JSON.stringify({dias}),
        });
        const result = await response.json();
        if (!response.ok) throw new Error(result.detail || "No se pudo iniciar la actualización.");
        mowaSyncEsperadoId = Number(result.id_anterior) + 1;
        mowaSyncInicio = Date.now();
        mowaSyncObservando = true;
        mostrarEstadoActualizacionMowa(`Buscando campañas desde ${formatoFechaSoloMowa(result.desde)}. Puedes seguir usando la vista.`);
        await consultarEstadoActualizacionMowa();
    } catch (error) {
        if (error?.constructor?.name === "SesionInvalidaError") return;
        boton.disabled = false;
        boton.textContent = "Actualizar SMS";
        mostrarEstadoActualizacionMowa(error.message || "No se pudo iniciar la actualización.", "ERROR");
    }
}

async function consultarEstadoActualizacionMowa() {
    if (document.getElementById("mowaSyncAcciones").hidden) return;
    const boton = document.getElementById("mowaSyncBoton");
    try {
        const response = await fetchConSesion(MOWA_SYNC_API);
        const estado = await response.json();
        if (!response.ok) throw new Error(estado.detail || "No se pudo leer el avance.");
        if (estado.en_curso) {
            mowaSyncObservando = true;
            mowaSyncEsperadoId = estado.id;
            boton.disabled = true;
            boton.textContent = "Actualizando…";
            mostrarEstadoActualizacionMowa(`Actualización iniciada el ${formatoFechaMowa(estado.inicio)}. Puedes seguir usando la vista.`);
            programarEstadoActualizacionMowa();
            return;
        }
        if (mowaSyncEsperadoId && estado.id < mowaSyncEsperadoId) {
            if (Date.now() - mowaSyncInicio < 30000) {
                programarEstadoActualizacionMowa();
                return;
            }
            mostrarEstadoActualizacionMowa("La carga no llegó a iniciarse. Revisa el servidor antes de reintentar.", "ERROR");
        } else if (mowaSyncObservando) {
            const detalle = estado.resultado === "ERROR" || estado.interrumpida
                ? "La actualización se interrumpió. Revisa el servidor antes de reintentar."
                : `Actualización terminada: ${estado.respuestas_nuevas ?? 0} respuestas nuevas, ${estado.origenes_completados ?? 0} respuestas con origen completado, ${estado.campanas_nuevas ?? 0} campañas nuevas${estado.avisos ? ` y ${estado.avisos} avisos de Mowa; pueden faltar datos y puedes reintentar` : ""}.`;
            mostrarEstadoActualizacionMowa(detalle, estado.interrumpida ? "ERROR" : estado.resultado);
            if (estado.fin) await consultarMowa();
        }
        mowaSyncObservando = false;
        mowaSyncEsperadoId = null;
        clearTimeout(mowaSyncTimer);
        boton.disabled = false;
        boton.textContent = "Actualizar SMS";
    } catch (error) {
        if (error?.constructor?.name === "SesionInvalidaError") return;
        mostrarEstadoActualizacionMowa(error.message || "No se pudo leer el avance.", "ERROR");
        if (mowaSyncObservando) programarEstadoActualizacionMowa();
        else { boton.disabled = false; boton.textContent = "Actualizar SMS"; }
    }
}

function textoAlcanceMowa() {
    const carteras = mowaAlcanceCarteras;
    if (carteras === null) return "Todas las carteras";
    if (!Array.isArray(carteras) || !carteras.length) return "Sin carteras asignadas";
    return `${carteras.length === 1 ? "Cartera" : "Carteras"} ${carteras.join(", ")}`;
}

async function consultarMowa(event) {
    event?.preventDefault();
    const desde = document.getElementById("mowaDesde").value;
    const hasta = document.getElementById("mowaHasta").value;
    const cuenta = document.getElementById("mowaCuenta").value;
    const boton = document.getElementById("mowaConsultar");
    const controles = ["mowaDesde", "mowaHasta", "mowaCuenta"].map(id => document.getElementById(id));
    if (!desde || !hasta || desde > hasta || (Date.parse(hasta) - Date.parse(desde)) / 86400000 > 30) {
        avisoMowa("Selecciona un rango de hasta 31 días.", true); return;
    }
    mowaDetener = false;
    mowaModoAcumulado = false;
    mowaCarteraAcumulada = null;
    mowaModoControl = false;
    mowaControlFiltro = null;
    document.getElementById("mowaCardPendientesTitulo").textContent = "Sin gestión posterior (rango)";
    document.getElementById("mowaExportar").textContent = "Exportar Excel";
    document.getElementById("mowaExportar").removeAttribute("title");
    mowaFilas = [];
    mowaGruposCache = null;
    mowaSeleccionados.clear();
    mowaExcluidasInactivas = 0;
    mowaPagina = 1;
    mowaConsultaCompleta = false;
    mowaAdvertenciasConsulta = [];
    boton.disabled = true; boton.textContent = "Consultando…";
    controles.forEach(control => { control.disabled = true; });
    avisoMowa("");
    document.getElementById("mowaCargando").hidden = false;
    document.getElementById("mowaProgreso").textContent = "Leyendo las respuestas guardadas y verificando las gestiones en SISCOB.";
    document.getElementById("mowaMas").disabled = true;
    document.getElementById("mowaAnterior").disabled = true;
    document.getElementById("mowaExportar").disabled = true;
    document.getElementById("mowaVerCarteras").disabled = true;
    document.getElementById("mowaPaginacion").textContent = "Cargando…";
    document.getElementById("mowaCartera").innerHTML = '<option value="">Todas</option>';
    document.getElementById("mowaTabla").innerHTML = `<tr><td colspan="${mowaPuedeAsignar ? 7 : 6}" class="mowa-vacio">Consultando respuestas y verificando gestiones…</td></tr>`;
    document.getElementById("mowaAlcance").textContent = "Consulta en curso";
    actualizarResumenMowa(false, false);
    const tarjeta = cargarSinAtenderMowa(cuenta);
    const inicioConsulta = Date.now();
    const reloj = setInterval(() => {
        document.getElementById("mowaSegundos").textContent = `${Math.floor((Date.now() - inicioConsulta) / 1000)} s`;
    }, 1000);
    const controller = new AbortController();
    mowaConsultaAbort = controller;
    const temporizador = setTimeout(() => controller.abort(), 65000);
    let hayDatos = false;
    try {
        const params = new URLSearchParams({desde, hasta});
        if (cuenta) params.set("cuenta", cuenta);
        const response = await fetchConSesion(`${MOWA_RAIZ}/recibidas?${params}`, {signal: controller.signal});
        const result = await response.json();
        if (!response.ok) throw new Error(result.detail || "No se pudo consultar las respuestas.");
        hayDatos = true;
        agregarFilasMowa(result.data || []);
        mowaExcluidasInactivas = Number(result.excluidas_inactivas) || 0;
        if (Object.prototype.hasOwnProperty.call(result, "alcance_carteras")) mowaAlcanceCarteras = result.alcance_carteras;
        mowaConsultaCompleta = result.completo !== false;
        mowaAdvertenciasConsulta = [...(result.advertencias || [])];
        pintarSincronizacionMowa(result.sincronizacion);
        actualizarCarterasMowa();
        avisoMowa(resumirAdvertenciasMowa(mowaAdvertenciasConsulta));
    } catch (error) {
        if (error?.constructor?.name === "SesionInvalidaError") return;
        avisoMowa(error.name === "AbortError"
            ? (mowaDetener ? "Consulta detenida." : "La consulta superó 65 segundos. Intenta un rango menor.")
            : (error.message || "No se pudo consultar las respuestas."), true);
    } finally {
        clearTimeout(temporizador);
        clearInterval(reloj);
        mowaConsultaAbort = null;
        document.getElementById("mowaVerCarteras").disabled = !mowaSinAtenderResumen;
        actualizarResumenMowa(mowaConsultaCompleta, hayDatos);
        pintarMowa();
        document.getElementById("mowaAlcance").textContent = hayDatos
            ? `${agruparMowa().length} conversaciones · ${mowaFilas.length} respuestas${textoInactivasMowa()} · recibidas del ${formatoFechaSoloMowa(desde)} al ${formatoFechaSoloMowa(hasta)}${cuenta ? ` · ${cuenta}` : ""}${mowaConsultaCompleta ? "" : " · consulta parcial"}`
            : "Sin datos";
        document.getElementById("mowaCargando").hidden = true;
        document.getElementById("mowaSegundos").textContent = "0 s";
        boton.disabled = false; boton.textContent = "Consultar";
        controles.forEach(control => { control.disabled = false; });
    }
    await tarjeta;
    if (mowaPuedeAsignar) await cargarAsignacionesMowa();
}

async function cargarSinAtenderMowa(cuenta) {
    const solicitud = ++mowaResumenSolicitud;
    const total = document.getElementById("mowaSinAtenderTotal");
    const detalle = document.getElementById("mowaSinAtenderDetalle");
    const tarjeta = document.getElementById("mowaSinAtender");
    mowaSinAtenderResumen = null;
    document.getElementById("mowaVerCarteras").disabled = true;
    total.textContent = "…";
    detalle.textContent = "Calculando clientes sin atender…";
    tarjeta.disabled = true;
    try {
        const params = new URLSearchParams();
        if (cuenta) params.set("cuenta", cuenta);
        const response = await fetchConSesion(`${MOWA_RAIZ}/sin-atender${params.toString() ? `?${params}` : ""}`);
        const result = await response.json();
        if (solicitud !== mowaResumenSolicitud) return;
        if (!response.ok) throw new Error(result.detail || "No se pudo calcular.");
        mowaSinAtenderResumen = result;
        total.textContent = String(result.clientes);
        detalle.textContent = `${result.respuestas} ${result.respuestas === 1 ? "respuesta" : "respuestas"} · ${result.clientes_ayer_hoy} de ayer y hoy · desde ${formatoFechaSoloMowa(result.desde)}${result.completo === false ? " · parcial" : ""}${result.sincronizacion?.desactualizada ? " · carga desactualizada" : ""}`;
        tarjeta.disabled = !result.clientes;
        document.getElementById("mowaVerCarteras").disabled = Boolean(mowaConsultaAbort);
        tarjeta.classList?.toggle("mowa-pulsante", result.clientes > 0);
        pintarSincronizacionMowa(result.sincronizacion);
    } catch (error) {
        if (solicitud !== mowaResumenSolicitud) return;
        if (error?.constructor?.name === "SesionInvalidaError") return;
        total.textContent = "—";
        detalle.textContent = error.message || "No se pudo calcular.";
        document.getElementById("mowaVerCarteras").disabled = true;
    }
}

function abrirCarterasMowa() {
    const resumen = mowaSinAtenderResumen;
    if (!resumen) return;
    const colores = ["#155ca8", "#e38b2c", "#18877b", "#9b61b5", "#cf5a57", "#6d83b8", "#8c9b40", "#b16d40", "#607d8b"];
    const carteras = (resumen.por_cartera || [])
        .map(r => ({id: Number(r.idcartera), clientes: Number(r.clientes) || 0}))
        .filter(r => Number.isInteger(r.id) && r.id > 0 && r.clientes > 0)
        .sort((a, b) => b.clientes - a.clientes || a.id - b.id);
    const total = carteras.reduce((suma, r) => suma + r.clientes, 0);
    const circunferencia = 2 * Math.PI * 74;
    let inicio = 0;
    const segmentos = carteras.map((r, indice) => {
        const largo = circunferencia * r.clientes / total;
        const segmento = `<circle cx="110" cy="110" r="74" fill="none" stroke="${colores[indice % colores.length]}" stroke-width="28" stroke-dasharray="${Math.max(0, largo - 2)} ${circunferencia}" stroke-dashoffset="-${inicio}" transform="rotate(-90 110 110)" data-cartera="${r.id}" tabindex="0" role="button" aria-label="Cartera ${r.id}: ${r.clientes} ${r.clientes === 1 ? "cliente pendiente" : "clientes pendientes"}. Ver detalle"></circle>`;
        inicio += largo;
        return segmento;
    }).join("");
    document.getElementById("mowaDona").innerHTML = `<svg viewBox="0 0 220 220" aria-label="${total} clientes pendientes distribuidos por cartera"><circle cx="110" cy="110" r="74" fill="none" stroke="#e7edf3" stroke-width="28"></circle>${segmentos}<text x="110" y="109" class="mowa-dona-total">${total}</text><text x="110" y="130" class="mowa-dona-leyenda">clientes</text></svg>`;
    document.getElementById("mowaCarterasLista").innerHTML = carteras.length
        ? carteras.map((r, indice) => {
            const porcentaje = r.clientes / total * 100;
            return `<button type="button" data-cartera="${r.id}"><span class="mowa-carteras-color" style="background:${colores[indice % colores.length]}"></span><span>Cartera ${r.id}<small>${porcentaje < 1 ? "&lt;1" : Math.round(porcentaje)}% del total</small></span><strong>${r.clientes}</strong></button>`;
        }).join("")
        : '<p class="mowa-small">No hay clientes pendientes en las carteras autorizadas.</p>';
    const cuenta = document.getElementById("mowaCuenta").selectedOptions[0]?.textContent || "Todas las cuentas";
    document.getElementById("mowaCarterasSubtitulo").textContent = `${total} clientes · ${cuenta} · respuestas desde ${formatoFechaSoloMowa(resumen.desde)}`;
    document.getElementById("mowaCarterasNota").textContent = `${resumen.sincronizacion?.desactualizada ? "La carga SMS está desactualizada; pueden faltar respuestas recientes. " : ""}${resumen.completo === false ? "El conteo es parcial porque no se verificaron todas las gestiones. " : ""}Selecciona una cartera para abrir todos sus pendientes acumulados, aunque estén fuera del rango de fechas visible.`;
    document.getElementById("mowaCarterasModal").showModal();
}

function clickCarterasMowa(event) {
    const dialogo = document.getElementById("mowaCarterasModal");
    const destino = event.target.closest?.("[data-cartera]");
    if (destino) { verPendientesCarteraMowa(Number(destino.dataset.cartera)); return; }
    if (event.target !== dialogo) return;
    const r = dialogo.getBoundingClientRect();
    if (event.clientX < r.left || event.clientX > r.right || event.clientY < r.top || event.clientY > r.bottom) dialogo.close();
}

function teclaCarterasMowa(event) {
    if (!["Enter", " "].includes(event.key) || !event.target.matches?.("circle[data-cartera]")) return;
    event.preventDefault();
    verPendientesCarteraMowa(Number(event.target.dataset.cartera));
}

async function verPendientesCarteraMowa(cartera) {
    if (!mowaSinAtenderResumen?.por_cartera?.some(r => Number(r.idcartera) === cartera)) return;
    document.getElementById("mowaCarterasModal").close();
    const cuenta = document.getElementById("mowaCuenta").value;
    const params = new URLSearchParams({cartera: String(cartera)});
    if (cuenta) params.set("cuenta", cuenta);
    const cargando = document.getElementById("mowaCargando");
    const controller = new AbortController();
    const temporizador = setTimeout(() => controller.abort(), 65000);
    cargando.hidden = false;
    document.getElementById("mowaProgreso").textContent = `Abriendo pendientes acumulados de la cartera ${cartera}.`;
    document.getElementById("mowaVerCarteras").disabled = true;
    try {
        const response = await fetchConSesion(`${MOWA_RAIZ}/sin-atender/detalle?${params}`, {signal: controller.signal});
        const result = await response.json();
        if (!response.ok) throw new Error(result.detail || "No se pudieron abrir los pendientes.");
        mowaModoAcumulado = true;
        mowaCarteraAcumulada = cartera;
        mowaModoControl = false;
        mowaControlFiltro = null;
        mowaFilas = (result.grupos || []).flatMap(g => g.filas || []);
        mowaSeleccionados.clear();
        mowaGruposCache = null;
        mowaPagina = 1;
        mowaConsultaCompleta = result.completo !== false;
        mowaAdvertenciasConsulta = result.advertencias || [];
        mowaExcluidasInactivas = 0;
        document.getElementById("mowaEstado").value = "PENDIENTE";
        document.getElementById("mowaOrden").value = "antiguo";
        document.getElementById("mowaBuscar").value = "";
        document.getElementById("mowaCardPendientesTitulo").textContent = "Sin gestión posterior (acumulado)";
        document.getElementById("mowaExportar").textContent = "Excel de cartera";
        document.getElementById("mowaExportar").title = "Incluye todos los pendientes de esta cartera, aunque uses Buscar en la tabla.";
        actualizarCarterasMowa();
        document.getElementById("mowaCartera").value = String(cartera);
        pintarSincronizacionMowa(result.sincronizacion);
        actualizarResumenMowa(mowaConsultaCompleta, true);
        pintarMowa();
        document.getElementById("mowaAlcance").textContent = `${result.clientes} clientes · ${result.respuestas} respuestas pendientes · cartera ${cartera} · acumuladas desde ${formatoFechaSoloMowa(result.desde)}${result.sincronizacion?.desactualizada ? " · carga desactualizada" : ""}`;
        avisoMowa(resumirAdvertenciasMowa(mowaAdvertenciasConsulta));
        if (mowaPuedeAsignar) await cargarAsignacionesMowa();
        document.getElementById("mowaDetalle").scrollIntoView({behavior: "smooth", block: "start"});
    } catch (error) {
        if (error?.constructor?.name !== "SesionInvalidaError") avisoMowa(error.name === "AbortError" ? "La consulta de pendientes superó 65 segundos." : (error.message || "No se pudieron abrir los pendientes."), true);
    } finally {
        clearTimeout(temporizador);
        cargando.hidden = true;
        document.getElementById("mowaVerCarteras").disabled = !mowaSinAtenderResumen;
    }
}

async function descargarSinAtenderMowa(cartera = null, desdeTabla = false) {
    const tarjeta = document.getElementById("mowaSinAtender");
    const accion = document.getElementById("mowaSinAtenderAccion");
    const botonTabla = document.getElementById("mowaExportar");
    const cuenta = document.getElementById("mowaCuenta").value;
    if (desdeTabla) { botonTabla.disabled = true; botonTabla.textContent = "Generando Excel…"; }
    else { tarjeta.disabled = true; accion.textContent = "Generando Excel…"; }
    try {
        const params = new URLSearchParams();
        if (cuenta) params.set("cuenta", cuenta);
        if (cartera) params.set("cartera", String(cartera));
        const response = await fetchConSesion(`${MOWA_RAIZ}/sin-atender/excel${params.toString() ? `?${params}` : ""}`);
        if (!response.ok) {
            const error = await response.json().catch(() => ({}));
            throw new Error(error.detail || "No se pudo generar el Excel.");
        }
        const nombre = nombreDescargaMowa(response, `SMS_sin_atender${cartera ? `_C${cartera}` : ""}_${fechaLocal(new Date())}.xlsx`);
        const objeto = URL.createObjectURL(await response.blob());
        const enlace = document.createElement("a");
        enlace.href = objeto;
        enlace.download = nombre;
        document.body.appendChild(enlace);
        enlace.click();
        enlace.remove();
        setTimeout(() => URL.revokeObjectURL(objeto), 1000);
    } catch (error) {
        avisoMowa(error.message || "No se pudo generar el Excel.", true);
    } finally {
        accion.textContent = "Descargar Excel de pendientes";
        tarjeta.disabled = document.getElementById("mowaSinAtenderTotal").textContent === "0";
        if (desdeTabla) {
            botonTabla.textContent = "Excel de cartera";
            botonTabla.disabled = filtrarOrdenarMowa().length === 0;
        }
    }
}

function nombreDescargaMowa(response, respaldo) {
    const disposicion = response.headers?.get?.("Content-Disposition") || "";
    return (disposicion.match(/filename="([^"]+)"/) || [])[1] || respaldo;
}

function pintarSincronizacionMowa(sync) {
    const el = document.getElementById("mowaConsultaHora");
    if (!sync) return;
    if (!sync.fin) {
        const intento = sync.ultimo_intento;
        el.textContent = `No hay una sincronización completada${intento ? ` · último intento ${intento.resultado || "sin cierre"}: ${formatoFechaMowa(intento.fin || intento.inicio)}` : ""}`;
        el.className = "mowa-small mowa-sync-alerta";
        return;
    }
    const intento = sync.ultimo_intento;
    const avisoIntento = intento?.resultado === "ERROR"
        ? ` · último intento falló: ${formatoFechaMowa(intento.fin || intento.inicio)}`
        : intento && !intento.fin ? ` · hay una corrida sin cierre desde ${formatoFechaMowa(intento.inicio)}` : "";
    const sinIntentos = sync.desactualizada && (!intento || intento.fin === sync.fin)
        ? " · sin corridas posteriores registradas" : "";
    el.textContent = `Última sincronización ${sync.resultado === "CON_AVISOS" ? "con avisos" : "completada"}: ${formatoFechaMowa(sync.fin)}${sync.desactualizada ? " · sin actualización reciente" : ""}${avisoIntento}${sinIntentos}`;
    el.className = `mowa-small${sync.desactualizada || sync.resultado === "CON_AVISOS" || avisoIntento ? " mowa-sync-alerta" : ""}`;
}

function agregarFilasMowa(nuevas) {
    const porId = new Map(mowaFilas.map(r => [`${r.cuenta}:${r.campana_id}:${r.id}`, r]));
    for (const fila of nuevas) porId.set(`${fila.cuenta}:${fila.campana_id}:${fila.id}`, fila);
    mowaFilas = [...porId.values()];
    mowaGruposCache = null;
}

function textoInactivasMowa() {
    if (!mowaExcluidasInactivas) return "";
    return ` · ${mowaExcluidasInactivas} ${mowaExcluidasInactivas === 1 ? "respuesta oculta" : "respuestas ocultas"} por cliente inactivo en SISCOB`;
}

// La agrupación solo cambia cuando llegan filas nuevas; filtros, búsqueda y
// paginación reutilizan el resultado en lugar de reagrupar en cada tecla.
function agruparMowa() {
    if (mowaGruposCache) return mowaGruposCache;
    mowaGruposCache = construirGruposMowa();
    return mowaGruposCache;
}

function construirGruposMowa() {
    const grupos = new Map();
    for (const fila of mowaFilas) {
        const clave = fila.idcliente && fila.idcartera
            ? `cliente:${fila.idcartera}:${fila.idcliente}`
            : `respuesta:${fila.cuenta}:${fila.campana_id}:${fila.id}`;
        if (!grupos.has(clave)) grupos.set(clave, {clave, filas: []});
        grupos.get(clave).filas.push(fila);
    }
    return [...grupos.values()].map(grupo => {
        grupo.filas.sort((a, b) => String(a.recibido || "").localeCompare(String(b.recibido || "")));
        const ultimo = grupo.filas.at(-1);
        const estados = grupo.filas.map(r => r.estado);
        grupo.ultimo = ultimo;
        grupo.recibido = ultimo.recibido;
        grupo.primeraPendiente = grupo.filas.find(r => r.estado === "PENDIENTE")?.recibido || grupo.filas[0].recibido;
        grupo.estado = ["PENDIENTE", "SIN_VERIFICAR", "SIN_VINCULAR", "ATENDIDA"].find(estado => estados.includes(estado));
        grupo.cuentas = [...new Set(grupo.filas.map(r => r.cuenta))];
        grupo.telefonos = [...new Set(grupo.filas.map(r => r.telefono).filter(Boolean))];
        grupo.gestion = [...grupo.filas].reverse().find(r => r.gestion_posterior) || null;
        return grupo;
    });
}

function actualizarResumenMowa(completo, hayDatos) {
    const grupos = agruparMowa();
    const contar = estado => grupos.filter(r => r.estado === estado).length;
    for (const [id, estado] of [
        ["mowaPendientes", "PENDIENTE"], ["mowaAtendidas", "ATENDIDA"],
        ["mowaSinVincular", "SIN_VINCULAR"], ["mowaSinVerificar", "SIN_VERIFICAR"],
    ]) {
        const cantidad = contar(estado);
        document.getElementById(id).textContent = !hayDatos ? "—" : (completo ? String(cantidad) : `${cantidad}+`);
    }
    const card = document.getElementById("mowaCardPendientes");
    card.classList?.toggle("mowa-pulsante", contar("PENDIENTE") > 0);
    const cuenta = document.getElementById("mowaCuenta").value;
    document.getElementById("mowaCardAlcance").textContent =
        mowaModoControl
            ? `${mowaControlCartera ? `Cartera ${mowaControlCartera}` : textoAlcanceMowa()} · control de asignaciones${completo ? "" : " · conteo parcial"}`
            : mowaModoAcumulado
            ? `Cartera ${mowaCarteraAcumulada} · pendientes acumulados${completo ? "" : " · conteo parcial"}`
            : `${textoAlcanceMowa()}${cuenta ? ` · ${cuenta}` : ""}${completo ? " · recibidas en el rango" : " · conteo parcial"}`;
}

function actualizarCarterasMowa() {
    const select = document.getElementById("mowaCartera");
    const seleccion = select.value;
    const carteras = [...new Set(mowaFilas.map(r => r.idcartera).filter(Number.isInteger))].sort((a, b) => a - b);
    select.innerHTML = '<option value="">Todas</option>' +
        carteras.map(id => `<option value="${id}">Cartera ${id}</option>`).join("");
    if (carteras.includes(Number(seleccion))) select.value = seleccion;
}

function cambiarPaginaMowa(delta) {
    mowaPagina = Math.max(1, mowaPagina + delta);
    pintarMowa();
}

function filtrarOrdenarMowa() {
    const estado = document.getElementById("mowaEstado").value;
    const cartera = document.getElementById("mowaCartera").value;
    const orden = document.getElementById("mowaOrden").value;
    const buscar = document.getElementById("mowaBuscar").value.trim().toLowerCase();
    const grupos = agruparMowa().filter(g => (!estado || g.estado === estado) &&
        (!cartera || String(g.ultimo.idcartera) === cartera) &&
        (!mowaPuedeAsignar || !document.getElementById("mowaAsignacionFiltro").value ||
            (document.getElementById("mowaAsignacionFiltro").value === "ASIGNADAS") ===
            mowaAsignaciones.has(claveAsignacionMowa(g.ultimo.idcartera, g.ultimo.idcliente))) &&
        g.filas.some(r => `${r.dni} ${r.cliente} ${r.telefono} ${r.texto} ${r.mensaje_enviado} ${r.gestion_posterior_texto} ${r.campana} ${r.cuenta}`.toLowerCase().includes(buscar)));
    grupos.sort((a, b) => {
        if (orden === "cliente") return String(a.ultimo.cliente || "").localeCompare(String(b.ultimo.cliente || ""), "es");
        if (orden === "pendiente") {
            const prioridad = Number(b.estado === "PENDIENTE") - Number(a.estado === "PENDIENTE");
            if (prioridad) return prioridad;
        }
        return orden === "antiguo"
            ? String(a.primeraPendiente || "").localeCompare(String(b.primeraPendiente || ""))
            : String(b.recibido || "").localeCompare(String(a.recibido || ""));
    });
    return grupos;
}

function pintarMowa() {
    const grupos = filtrarOrdenarMowa();
    const tamano = Number(document.getElementById("mowaTamano").value) || 20;
    const paginas = Math.max(1, Math.ceil(grupos.length / tamano));
    mowaPagina = Math.min(mowaPagina, paginas);
    const inicio = (mowaPagina - 1) * tamano;
    const visibles = grupos.slice(inicio, inicio + tamano);
    mowaConversacionesVisibles = visibles;
    if (mowaPuedeAsignar) {
        const seleccionables = visibles.map(clienteAsignableMowa).filter(Boolean);
        const seleccionadasPagina = seleccionables.filter(c => mowaSeleccionados.has(claveAsignacionMowa(c.idcartera, c.idcliente))).length;
        const checkPagina = document.getElementById("mowaSeleccionPagina");
        checkPagina.disabled = !seleccionables.length;
        checkPagina.checked = seleccionables.length > 0 && seleccionadasPagina === seleccionables.length;
        checkPagina.indeterminate = seleccionadasPagina > 0 && seleccionadasPagina < seleccionables.length;
        document.getElementById("mowaSeleccionBar").hidden = false;
        document.getElementById("mowaSeleccionConteo").textContent = `${mowaSeleccionados.size} ${mowaSeleccionados.size === 1 ? "cliente seleccionado" : "clientes seleccionados"} · máximo ${MOWA_MAX_LOTE}`;
        document.getElementById("mowaSeleccionLimpiar").disabled = !mowaSeleccionados.size;
        document.getElementById("mowaAsignarSeleccion").disabled = !mowaSeleccionados.size;
        document.getElementById("mowaSeleccionFiltrados").disabled = !grupos.some(clienteAsignableMowa);
    }
    document.getElementById("mowaAnterior").disabled = mowaPagina <= 1;
    document.getElementById("mowaMas").disabled = mowaPagina >= paginas;
    document.getElementById("mowaExportar").disabled = grupos.length === 0;
    document.getElementById("mowaPaginacion").textContent = grupos.length
        ? `${inicio + 1}–${inicio + visibles.length} de ${grupos.length} conversaciones`
        : "0 conversaciones";
    document.getElementById("mowaTabla").innerHTML = grupos.length ? visibles.map((g, indice) => {
        const r = g.ultimo;
        const pendientes = g.filas.filter(f => f.estado === "PENDIENTE").length;
        const asignacion = mowaAsignaciones.get(claveAsignacionMowa(r.idcartera, r.idcliente));
        const asignable = clienteAsignableMowa(g);
        const seleccionada = asignable && mowaSeleccionados.has(claveAsignacionMowa(asignable.idcartera, asignable.idcliente));
        const celdaSeleccion = mowaPuedeAsignar ? `<td class="mowa-seleccion-celda">${asignable
            ? `<input type="checkbox" data-seleccionar="${indice}" aria-label="Seleccionar ${escMowa(asignable.nombre)}" ${seleccionada ? "checked" : ""}>` : ""}</td>` : "";
        const controlAsignacion = mowaPuedeAsignar && g.estado === "PENDIENTE" && r.idcliente
            ? `<div class="mowa-asignacion"><small>${asignacion ? `Asignado a ${escMowa(asignacion.agente_nombre || asignacion.agente_usuario)}` : "Sin asignar"}</small><button type="button" data-asignar="${indice}">${asignacion ? "Cambiar agente" : "Asignar agente"}</button></div>` : "";
        return `
        <tr${seleccionada ? ' class="mowa-seleccionada"' : ""}>
            ${celdaSeleccion}
            <td><strong>${escMowa(formatoFechaMowa(r.recibido))}</strong><small>${g.filas.length} ${g.filas.length === 1 ? "respuesta" : "respuestas"} de esta conversación</small></td>
            <td><span class="mowa-badge ${escMowa(g.estado)}">${escMowa(rotuloMowa(g.estado))}</span>${pendientes ? `<small>${pendientes} ${pendientes === 1 ? "SMS pendiente" : "SMS pendientes"}</small>` : ""}${r.motivo ? `<small class="mowa-motivo" title="${escMowa(r.motivo)}">${escMowa(r.motivo)}</small>` : ""}<small class="mowa-proveedor">Mowa (último SMS): ${escMowa(r.estado_mowa_etiqueta || "No informado")}${r.estado_mowa_codigo != null ? ` · ${escMowa(r.estado_mowa_codigo)}` : ""}</small></td>
            <td><strong>${escMowa(r.cliente || "—")}</strong><small>DNI: ${escMowa(r.dni || "—")} · ID: ${escMowa(r.idcliente || "—")} · Cartera: ${escMowa(r.idcartera || r.cartera_mowa || "—")}</small><small>Tel: ${escMowa(g.telefonos.join(", ") || "—")}</small>${r.dni ? `<button class="mowa-copiar" type="button" data-copiar="${escMowa(r.dni)}">Copiar DNI</button>` : ""}${controlAsignacion}</td>
            <td><div class="mowa-conversacion"><div class="mowa-recibido"><span>Última respuesta</span><p>${escMowa(r.texto || "—")}</p></div><button class="mowa-abrir" type="button" data-chat="${indice}">Ver conversación (${g.filas.length})</button></div></td>
            <td>${escMowa(g.cuentas.join(", "))}<small>${escMowa(r.campana || "Campaña sin nombre")} #${escMowa(r.campana_id)}</small></td>
            <td>${renderGestionMowa(g.estado === "ATENDIDA" ? (g.gestion || r) : {...r, estado: g.estado, gestion_posterior: null})}</td>
        </tr>`;
    }).join("") : `<tr><td colspan="${mowaPuedeAsignar ? 7 : 6}" class="mowa-vacio">Sin conversaciones para estos filtros.</td></tr>`;
}

function datosExportMowa() {
    const campos = ["cuenta", "campana_id", "campana", "id", "mensaje_id", "idcartera",
        "idcliente", "dni", "cliente", "telefono", "recibido", "texto", "estado",
        "estado_mowa_etiqueta", "mensaje_enviado_fecha", "mensaje_enviado",
        "gestion_posterior", "gestion_posterior_id", "gestion_posterior_texto", "motivo"];
    return {
        desde: document.getElementById("mowaDesde").value,
        hasta: document.getElementById("mowaHasta").value,
        cuenta: document.getElementById("mowaCuenta").value || null,
        estado_filtro: document.getElementById("mowaEstado").value || null,
        etiqueta_rango: "Respuestas recibidas",
        completo: mowaConsultaCompleta,
        advertencias: mowaAdvertenciasConsulta,
        conversaciones: filtrarOrdenarMowa().map(g => ({
            estado: g.estado,
            filas: g.filas.map(r => Object.fromEntries(campos.map(campo => [campo, r[campo] ?? null]))),
        })),
    };
}

async function exportarMowa() {
    if (mowaModoAcumulado) return descargarSinAtenderMowa(mowaCarteraAcumulada, true);
    if (mowaModoControl) return exportarControlMowa();
    const datos = datosExportMowa();
    if (!datos.conversaciones.length) return;
    const boton = document.getElementById("mowaExportar");
    boton.disabled = true;
    boton.textContent = "Generando Excel…";
    try {
        const response = await fetchConSesion(MOWA_API.replace(/\/consultar$/, "/exportar"), {
            method: "POST", headers: {"Content-Type": "application/json"},
            body: JSON.stringify(datos),
        });
        if (!response.ok) {
            const error = await response.json().catch(() => ({}));
            throw new Error(error.detail || "No se pudo generar el Excel.");
        }
        const objeto = URL.createObjectURL(await response.blob());
        const enlace = document.createElement("a");
        enlace.href = objeto;
        // El servidor arma el nombre con carteras y hora de generación; este es solo el respaldo.
        enlace.download = nombreDescargaMowa(response,
            `Respuestas_SMS_${datos.desde}_a_${datos.hasta}${datos.completo ? "" : "_PARCIAL"}.xlsx`);
        document.body.appendChild(enlace);
        enlace.click();
        enlace.remove();
        setTimeout(() => URL.revokeObjectURL(objeto), 1000);
    } catch (error) {
        avisoMowa(error.message || "No se pudo generar el Excel.", true);
    } finally {
        boton.textContent = "Exportar Excel";
        boton.disabled = filtrarOrdenarMowa().length === 0;
    }
}

async function exportarControlMowa() {
    if (!mowaControlFiltro) return;
    const boton = document.getElementById("mowaExportar");
    const params = new URLSearchParams({agente: mowaControlFiltro});
    if (mowaControlCartera) params.set("cartera", mowaControlCartera);
    boton.disabled = true;
    boton.textContent = "Generando Excel…";
    try {
        const response = await fetchConSesion(`${MOWA_RAIZ}/control-asignaciones/excel?${params}`);
        if (!response.ok) {
            const error = await response.json().catch(() => ({}));
            throw new Error(error.detail || "No se pudo generar el Excel.");
        }
        const objeto = URL.createObjectURL(await response.blob());
        const enlace = document.createElement("a");
        enlace.href = objeto;
        enlace.download = nombreDescargaMowa(response, `Asignaciones_SMS_${fechaLocal(new Date())}.xlsx`);
        document.body.appendChild(enlace);
        enlace.click();
        enlace.remove();
        setTimeout(() => URL.revokeObjectURL(objeto), 1000);
    } catch (error) {
        avisoMowa(error.message || "No se pudo generar el Excel.", true);
    } finally {
        boton.textContent = "Excel de asignaciones";
        boton.disabled = !filtrarOrdenarMowa().length;
    }
}

function renderGestionMowa(r) {
    if (r.gestion_posterior) return `<div class="mowa-gestion-detalle"><strong>${escMowa(formatoFechaMowa(r.gestion_posterior))}</strong><p>${escMowa(r.gestion_posterior_texto || "Gestión registrada sin descripción")}</p>${r.gestion_posterior_id ? `<small>Gestión #${escMowa(r.gestion_posterior_id)}</small>` : ""}</div>`;
    if (r.estado === "PENDIENTE") return '<span class="mowa-alerta">● Sin gestión posterior</span>';
    if (r.estado === "SIN_VERIFICAR") return '<span class="mowa-alerta">● Gestión sin confirmar</span>';
    return '<span class="mowa-alerta-neutral">Cliente sin vincular</span>';
}

function eventosChatMowa(grupo) {
    const eventos = [];
    const enviados = new Set();
    for (const r of grupo.filas) {
        const claveEnviado = `${r.cuenta}:${r.mensaje_id}`;
        if (r.mensaje_enviado && !enviados.has(claveEnviado)) {
            enviados.add(claveEnviado);
            eventos.push({lado: "nosotros", texto: r.mensaje_enviado,
                fecha: r.mensaje_enviado_fecha, orden: r.mensaje_enviado_fecha || r.recibido,
                cuenta: r.cuenta, telefono: r.telefono, id: r.mensaje_id,
                campana_id: r.campana_id, estado: r.mensaje_enviado_estado});
        }
        eventos.push({lado: "cliente", texto: r.texto, fecha: r.recibido,
            orden: r.recibido, cuenta: r.cuenta, telefono: r.telefono, id: r.id,
            campana_id: r.campana_id, estado: r.estado_mowa_etiqueta});
    }
    eventos.push(...(mowaChatEnvios.get(grupo.clave) || []));
    const rango = `${document.getElementById("mowaDesde").value}:${document.getElementById("mowaHasta").value}`;
    const historico = mowaChatHistorico.get(grupo.clave);
    if (historico?.rango === rango) eventos.push(...historico.eventos);
    const unicos = new Map(eventos.map(e => [`${e.cuenta}:${e.campana_id}:${e.lado}:${e.id}`, e]));
    return [...unicos.values()].sort((a, b) => String(a.orden || "").localeCompare(String(b.orden || "")) ||
        Number(a.lado === "cliente") - Number(b.lado === "cliente"));
}

function cerrarChatFueraMowa(event) {
    const dialogo = document.getElementById("mowaChat");
    if (event.target !== dialogo) return;
    const rect = dialogo.getBoundingClientRect();
    if (event.clientX < rect.left || event.clientX > rect.right ||
        event.clientY < rect.top || event.clientY > rect.bottom) dialogo.close();
}

async function abrirChatMowa(grupo) {
    if (!grupo) return;
    mowaChatClave = grupo.clave;
    document.getElementById("mowaChatTexto").value = "";
    document.getElementById("mowaChatCaracteres").textContent = "0/160";
    document.getElementById("mowaChatAviso").textContent = "";
    const destinos = [...new Set(grupo.filas.map(r => r.telefono).filter(n => /^9\d{8}$/.test(String(n))))]
        .filter(numero => grupo.filas.some(r => r.telefono === numero && r.idcliente &&
            r.campana_creacion && /^\d+$/.test(String(r.id)) && /^\d+$/.test(String(r.mensaje_id))));
    const select = document.getElementById("mowaChatDestino");
    select.innerHTML = destinos.map(n => `<option value="${escMowa(n)}">${escMowa(n)}</option>`).join("");
    if (destinos.includes(grupo.ultimo.telefono)) select.value = grupo.ultimo.telefono;
    select.disabled = !destinos.length;
    document.getElementById("mowaChatEnviar").disabled = select.disabled;
    if (select.disabled) document.getElementById("mowaChatAviso").textContent =
        "El envío requiere un cliente vinculado y un celular peruano verificado.";
    document.getElementById("mowaChatTitulo").textContent = grupo.ultimo.cliente || "Contacto sin vincular";
    document.getElementById("mowaChatSubtitulo").textContent =
        `DNI ${grupo.ultimo.dni || "—"} · Cartera ${grupo.ultimo.idcartera || "—"} · ${grupo.filas.length} ${grupo.filas.length === 1 ? "respuesta" : "respuestas"}`;
    pintarChatMowa(grupo);
    document.getElementById("mowaChat").showModal();
    if (!select.disabled) await cargarHistorialMowa(grupo);
}

async function cargarHistorialMowa(grupo) {
    const desde = document.getElementById("mowaDesde").value;
    const hasta = document.getElementById("mowaHasta").value;
    const rango = `${desde}:${hasta}`;
    const cache = mowaChatHistorico.get(grupo.clave);
    if (cache?.rango === rango && cache.completo) return;
    const anclas = [...new Set(grupo.filas.map(r => `${r.cuenta}:${r.telefono}`))].map(clave =>
        [...grupo.filas].reverse().find(r => `${r.cuenta}:${r.telefono}` === clave && r.idcliente &&
            r.campana_creacion && /^\d+$/.test(String(r.id)) && /^\d+$/.test(String(r.mensaje_id)))).filter(Boolean);
    if (!anclas.length) return;
    const aviso = document.getElementById("mowaChatAviso");
    aviso.textContent = "Cargando los SMS de este cliente en el rango consultado…";
    const eventos = [];
    const advertencias = [];
    for (const ancla of anclas) {
        // El rango de la vista es de recepción; la campaña puede ser anterior. El historial
        // debe incluir la fecha de la campaña y el backend acepta hasta 31 días.
        const rangoHistorial = rangoHistorialMowa(ancla.campana_creacion, desde, hasta);
        const params = new URLSearchParams({cuenta: ancla.cuenta,
            campana_id: ancla.campana_id, respuesta_id: ancla.id,
            mensaje_id: ancla.mensaje_id, fecha_campana: ancla.campana_creacion, ...rangoHistorial});
        try {
            const response = await fetchConSesion(`${MOWA_API.replace(/\/consultar$/, "/historial")}?${params}`);
            const result = await response.json();
            if (!response.ok) throw new Error(result.detail || "No se pudo cargar el historial.");
            eventos.push(...(result.eventos || []).map(e => ({...e, orden: e.fecha})));
            advertencias.push(...(result.advertencias || []));
        } catch (error) {
            advertencias.push(`${ancla.cuenta} · ${ancla.telefono}: ${error.message || "historial no disponible"}`);
        }
    }
    mowaChatHistorico.set(grupo.clave, {rango, eventos, completo: advertencias.length === 0});
    if (mowaChatClave === grupo.clave && document.getElementById("mowaChat").open) {
        pintarChatMowa(grupo);
        if (!aviso.textContent.startsWith("Mowa aceptó")) {
            aviso.textContent = advertencias.length
                ? `${eventos.length ? "Historial parcial" : "No se pudo ampliar el historial"}: ${advertencias.join(" ")} Los mensajes ya cargados siguen visibles.`
                : "Historial del rango cargado. Los mensajes nuevos pueden aparecer al actualizar la consulta.";
        }
    }
}

function rangoHistorialMowa(fechaCampana, desde, hasta) {
    const inicio = fechaCampana && fechaCampana < desde ? fechaCampana : desde;
    const limite = new Date(`${inicio}T00:00:00Z`);
    limite.setUTCDate(limite.getUTCDate() + 30);
    const tope = limite.toISOString().slice(0, 10);
    return {desde: inicio, hasta: hasta > tope ? tope : hasta};
}

function pintarChatMowa(grupo) {
    const contenedor = document.getElementById("mowaChatMensajes");
    contenedor.innerHTML = eventosChatMowa(grupo).map(e => `
        <div class="mowa-burbuja ${e.lado === "cliente" ? "mowa-burbuja-cliente" : "mowa-burbuja-nosotros"}">
            <span>${e.lado === "cliente" ? "Cliente" : "Nuestro SMS"}</span>
            <p>${escMowa(e.texto || "—")}</p>
            <small>${escMowa(e.fecha ? formatoFechaMowa(e.fecha, true) : "Hora no informada")} · ${escMowa(e.telefono || "—")} · ${escMowa(e.cuenta || "")}${e.id ? ` · #${escMowa(e.id)}` : ""}${e.estado ? ` · ${escMowa(e.estado)}` : ""}</small>
        </div>`).join("");
    contenedor.scrollTop = contenedor.scrollHeight;
}

async function enviarChatMowa(event) {
    event.preventDefault();
    const grupo = agruparMowa().find(g => g.clave === mowaChatClave);
    if (!grupo) return;
    const numero = document.getElementById("mowaChatDestino").value;
    const texto = document.getElementById("mowaChatTexto").value.trim();
    const ancla = [...grupo.filas].reverse().find(r => r.telefono === numero &&
        r.idcliente && r.campana_creacion && /^\d+$/.test(String(r.id)) && /^\d+$/.test(String(r.mensaje_id)));
    const aviso = document.getElementById("mowaChatAviso");
    if (!ancla || !texto || texto.length > 160 || /[\r\n]/.test(texto)) {
        aviso.textContent = "Elige un celular verificado y escribe un SMS de hasta 160 caracteres en una línea.";
        return;
    }
    const boton = document.getElementById("mowaChatEnviar");
    boton.disabled = true;
    boton.textContent = "Enviando…";
    aviso.textContent = "Enviando por Mowa…";
    try {
        const response = await fetchConSesion(MOWA_API.replace(/\/consultar$/, "/enviar"), {
            method: "POST", headers: {"Content-Type": "application/json"},
            body: JSON.stringify({cuenta: ancla.cuenta, campana_id: Number(ancla.campana_id),
                respuesta_id: Number(ancla.id), mensaje_id: Number(ancla.mensaje_id),
                fecha_campana: ancla.campana_creacion, texto}),
        });
        const result = await response.json();
        if (!response.ok) throw new Error(result.detail || "Mowa no confirmó el envío. Verifica antes de reintentar.");
        const envios = mowaChatEnvios.get(grupo.clave) || [];
        envios.push({lado: "nosotros", texto: result.texto, fecha: result.fecha,
            orden: result.fecha || new Date().toISOString(), cuenta: result.cuenta,
            telefono: result.telefono, id: result.mensaje_id, campana_id: result.campana_id,
            estado: result.estado_etiqueta || "Aceptado por Mowa"});
        mowaChatEnvios.set(grupo.clave, envios);
        document.getElementById("mowaChatTexto").value = "";
        document.getElementById("mowaChatCaracteres").textContent = "0/160";
        aviso.textContent = `Mowa aceptó el SMS #${result.mensaje_id}. Aún no confirma su entrega. La gestión SISCOB sigue pendiente.`;
        pintarChatMowa(grupo);
    } catch (error) {
        aviso.textContent = error.message || "No se confirmó el envío. Verifica Mowa antes de reintentar.";
    } finally {
        boton.disabled = false;
        boton.textContent = "Enviar SMS";
    }
}

function formatoFechaMowa(valor, conSegundos=false) {
    const texto = String(valor || "");
    const m = texto.match(/^(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2})(?::(\d{2}))?)?/);
    if (!m) return valor || "—";
    return `${m[3]}/${m[2]}/${m[1]}${m[4] ? ` ${m[4]}:${m[5]}${conSegundos && m[6] ? `:${m[6]}` : ""}` : " · hora no registrada"}`;
}

function formatoFechaSoloMowa(valor) {
    return formatoFechaMowa(valor).replace(" · hora no registrada", "");
}

function rotuloMowa(estado) {
    return ({PENDIENTE:"Pendiente",ATENDIDA:"Atendida",SIN_VINCULAR:"Sin vincular",SIN_VERIFICAR:"Sin verificar"})[estado] || estado;
}

function avisoMowa(texto, error=false) {
    const el = document.getElementById("mowaAviso");
    el.textContent = texto || "";
    el.className = `mowa-aviso${texto ? " visible" : ""}${error ? " error" : ""}`;
}

function resumirAdvertenciasMowa(advertencias) {
    const conteos = new Map();
    for (const aviso of advertencias) {
        const legible = aviso.replace("Consulta Mowa fallida (ReadTimeout).",
            "Mowa excedió el tiempo de lectura.");
        conteos.set(legible, (conteos.get(legible) || 0) + 1);
    }
    return [...conteos].map(([aviso, veces]) =>
        veces > 1 ? `${aviso} (${veces} veces)` : aviso).join("\n");
}

function escMowa(valor) {
    return String(valor ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"})[c]);
}
