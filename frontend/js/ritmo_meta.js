const BASE_URL_RITMO = `${window.location.protocol}//${window.location.hostname}:8000`;

let ritmoActual = null;
let agenteRitmo = "";

document.addEventListener("DOMContentLoaded", () => {
    if (!exigirSesion()) return;
    activarTooltips();
    prepararMesesRitmo();
    agenteRitmo = obtenerAgenteRitmo();
    document.getElementById("ritmoAgente").innerText = agenteRitmo || "-";
    cargarRitmoMeta();
});

function activarTooltips() {
    document.querySelectorAll(".has-tip").forEach(item => {
        item.setAttribute("tabindex", "0");
    });
}

async function cargarRitmoMeta() {
    try {
        const usuario = (agenteRitmo || "").split(" - ")[0];
        const codmes = document.getElementById("ritmoCodmes").value;
        const params = new URLSearchParams({ usuario, codmes });
        const res = await fetch(`${BASE_URL_RITMO}/admin-metas-agentes/ritmo-agente?${params.toString()}`, {
            cache: "no-store",
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "No se pudo cargar ritmo.");

        ritmoActual = data;
        renderRitmo(data);
        renderCalculadora();
    } catch (error) {
        console.error("ERROR RITMO:", error);
        ritmoActual = null;
        renderRitmo(null);
    }
}

function obtenerAgenteRitmo() {
    const params = new URLSearchParams(window.location.search);
    return params.get("agente")
        || localStorage.getItem("agente_filtro")
        || localStorage.getItem("agente")
        || localStorage.getItem("dni")
        || "";
}

function prepararMesesRitmo() {
    const select = document.getElementById("ritmoCodmes");
    const hoy = new Date();
    const opciones = [];

    for (let offset = -2; offset <= 1; offset++) {
        const fecha = new Date(hoy.getFullYear(), hoy.getMonth() + offset, 1);
        const codmes = `${fecha.getFullYear()}${String(fecha.getMonth() + 1).padStart(2, "0")}`;
        opciones.push(`<option value="${codmes}">${codmes} - ${fecha.toLocaleDateString("es-PE", { month: "long", year: "numeric" })}</option>`);
    }

    select.innerHTML = opciones.join("");
    select.value = `${hoy.getFullYear()}${String(hoy.getMonth() + 1).padStart(2, "0")}`;
}

function renderRitmo(data) {
    const safe = data || {};
    const meta = Number(safe.meta_mensual || 0);
    const cumplido = Number(safe.monto_cumplido || 0);
    const esperado = Number(safe.esperado_a_hoy || 0);
    const cumplimientoPct = Number(safe.cumplimiento_pct || 0);
    const esperadoPct = Number(safe.avance_esperado_pct || 0);
    const proyectadoPct = Number(safe.cumplimiento_proyectado_pct || 0);
    const estado = safe.estado_ritmo || "sin-ritmo";

    document.getElementById("ritmoNecesarioDia").innerText = soles(safe.necesario_diario);
    document.getElementById("ritmoDiasRestantes").innerText = `${numero(safe.dias_habiles_restantes)} dias habiles restantes`;
    document.getElementById("ritmoBrecha").innerText = soles(safe.brecha);
    document.getElementById("ritmoMeta").innerText = `Meta ${soles(meta)}`;
    document.getElementById("ritmoTickets").innerText = Number(safe.tickets_necesarios_dia || 0).toFixed(1);
    document.getElementById("ritmoTicketPromedio").innerText = `Para ponerte al dia con ticket prom. ${soles(safe.ticket_promedio)}`;
    document.getElementById("ritmoProyeccion").innerText = soles(safe.proyeccion_cierre);
    document.getElementById("ritmoProyeccionPct").innerText = `${porcentaje(proyectadoPct)} de la meta`;
    document.getElementById("ritmoEstadoLabel").innerText = etiquetaEstado(estado);
    document.getElementById("ritmoEstadoTitulo").innerText = safe.estado_titulo || "-";
    document.getElementById("ritmoEstadoDetalle").innerText = safe.estado_detalle || "-";
    document.getElementById("ritmoCumplimiento").innerText = porcentaje(cumplimientoPct);
    document.getElementById("ritmoFecha").innerText = `Al ${formatearFecha(safe.fecha_referencia)} | ${numero(safe.dias_habiles_transcurridos)} de ${numero(safe.dias_habiles_mes)} dias habiles`;
    document.getElementById("ritmoEsperado").innerText = soles(esperado);
    document.getElementById("ritmoCumplido").innerText = soles(cumplido);
    document.getElementById("ritmoDesvio").innerText = solesConSigno(safe.desvio_monto);
    document.getElementById("barEsperado").style.width = limitarPct(esperadoPct);
    document.getElementById("barReal").style.width = limitarPct(cumplimientoPct);

    document.getElementById("ritmoStatus").className = `ritmo-status ${estado}`;
    document.body.classList.toggle("sin-meta", !safe.meta_configurada);
}

function renderCalculadora() {
    const data = ritmoActual || {};
    const pago = Number(document.getElementById("calcPago").value || 0);
    const brecha = Math.max(Number(data.brecha || 0) - pago, 0);
    const dias = Number(data.dias_habiles_restantes || 0);
    const nuevoDiario = dias > 0 ? brecha / dias : brecha;
    const actualDiario = Number(data.necesario_diario || 0);

    document.getElementById("calcBrecha").innerText = soles(brecha);
    document.getElementById("calcDiario").innerText = soles(nuevoDiario);
    document.getElementById("calcAlivio").innerText = soles(Math.max(actualDiario - nuevoDiario, 0));
}

function etiquetaEstado(estado) {
    return {
        "verde": "Verde",
        "amarillo": "Amarillo",
        "rojo": "Rojo",
        "sin-ritmo": "Sin ritmo",
    }[estado] || "Sin ritmo";
}

function soles(value) {
    return Number(value || 0).toLocaleString("es-PE", {
        style: "currency",
        currency: "PEN",
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
    });
}

function solesConSigno(value) {
    const numeroValor = Number(value || 0);
    return `${numeroValor < 0 ? "-" : ""}${soles(Math.abs(numeroValor))}`;
}

function porcentaje(value) {
    return `${(Number(value || 0) * 100).toFixed(1)}%`;
}

function numero(value) {
    return Number(value || 0).toLocaleString("es-PE");
}

function limitarPct(value) {
    return `${Math.min(Math.max(Number(value || 0) * 100, 0), 100)}%`;
}

function formatearFecha(value) {
    if (!value) return "-";
    const partes = String(value).slice(0, 10).split("-");
    if (partes.length === 3) return `${partes[2]}/${partes[1]}/${partes[0]}`;
    return value;
}
