const SUSURRO_BASE = obtenerBaseUrlSusurro();

let sesionSusurro = null;
let speakerSusurro = "cliente";
let pollingSusurro = null;
let pollingSuspendidoSusurro = false;

document.addEventListener("DOMContentLoaded", async () => {
    if (typeof exigirSesion === "function" && !exigirSesion()) return;
    setSpeakerSusurro("cliente");
    const sessionIdUrl = new URLSearchParams(window.location.search).get("session_id");
    if (sessionIdUrl) {
        await cargarSesionSusurro(sessionIdUrl);
    } else {
        await crearSesionSusurro();
    }

    document.getElementById("fragmentoSusurro")?.addEventListener("keydown", event => {
        if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
            enviarFragmentoSusurro();
        }
    });
    iniciarPollingSusurro();
    document.addEventListener("visibilitychange", manejarVisibilidadSusurro);
    window.addEventListener("beforeunload", detenerPollingSusurro);
});

function obtenerBaseUrlSusurro() {
    const host = window.location.hostname || "127.0.0.1";
    return `http://${host}:8000/susurro-ia`;
}

async function crearSesionSusurro() {
    try {
        const response = await fetch(`${SUSURRO_BASE}/sesiones`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                agente: localStorage.getItem("agente") || localStorage.getItem("dni") || "SIN_USUARIO",
                cartera: localStorage.getItem("idcartera") || "",
                modo: "demo"
            })
        });
        const data = await leerJsonSeguroSusurro(response);
        if (!response.ok) throw new Error(data.detail || "No se pudo crear la sesion.");
        sesionSusurro = data;
        pollingSuspendidoSusurro = false;
        renderSesionSusurro(data);
        if (!pollingSusurro) iniciarPollingSusurro();
    } catch (error) {
        mostrarErrorSusurro(error.message || "Error creando sesion.");
    }
}

async function cargarSesionSusurro(sessionId) {
    try {
        const response = await fetch(`${SUSURRO_BASE}/sesiones/${encodeURIComponent(sessionId)}`);
        const data = await leerJsonSeguroSusurro(response);
        if (response.status === 404) {
            marcarSesionExpiradaSusurro();
            return;
        }
        if (!response.ok) throw new Error(data.detail || "No se pudo cargar la sesion.");
        sesionSusurro = data;
        pollingSuspendidoSusurro = false;
        renderSesionSusurro(data);
        if (!pollingSusurro) iniciarPollingSusurro();
    } catch (error) {
        mostrarErrorSusurro(error.message || "Error cargando sesion.");
        await crearSesionSusurro();
    }
}

function iniciarPollingSusurro() {
    if (pollingSusurro) clearInterval(pollingSusurro);
    pollingSusurro = setInterval(async () => {
        if (!sesionSusurro?.session_id || pollingSuspendidoSusurro || document.hidden) return;
        try {
            const response = await fetch(`${SUSURRO_BASE}/sesiones/${encodeURIComponent(sesionSusurro.session_id)}`);
            const data = await leerJsonSeguroSusurro(response);
            if (response.ok) {
                sesionSusurro = data;
                renderSesionSusurro(data);
                return;
            }
            if (response.status === 404) {
                marcarSesionExpiradaSusurro();
            }
        } catch {
            // Mantiene la ultima vista si la sesion aun no responde.
        }
    }, 2000);
}

function detenerPollingSusurro() {
    if (pollingSusurro) {
        clearInterval(pollingSusurro);
        pollingSusurro = null;
    }
}

function manejarVisibilidadSusurro() {
    pollingSuspendidoSusurro = document.hidden;
}

function marcarSesionExpiradaSusurro() {
    detenerPollingSusurro();
    pollingSuspendidoSusurro = true;
    sesionSusurro = null;
    setTextSusurro("estadoSesionSusurro", "SESION EXPIRADA");
    setTextSusurro("detalleSesionSusurro", "La sesion ya no existe en el servidor. Crea una nueva sesion para continuar.");
}

async function enviarFragmentoSusurro() {
    if (!sesionSusurro?.session_id) {
        await crearSesionSusurro();
    }

    const textarea = document.getElementById("fragmentoSusurro");
    const texto = textarea.value.trim();
    if (!texto) return;

    try {
        const response = await fetch(`${SUSURRO_BASE}/fragmentos`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                session_id: sesionSusurro.session_id,
                texto,
                speaker: speakerSusurro,
                source: "manual"
            })
        });
        const data = await leerJsonSeguroSusurro(response);
        if (!response.ok) throw new Error(data.detail || "No se pudo analizar el fragmento.");
        sesionSusurro = data.session;
        textarea.value = "";
        renderSesionSusurro(sesionSusurro);
    } catch (error) {
        mostrarErrorSusurro(error.message || "Error enviando fragmento.");
    }
}

async function limpiarSusurro() {
    if (!sesionSusurro?.session_id) {
        await crearSesionSusurro();
        return;
    }

    try {
        const response = await fetch(`${SUSURRO_BASE}/sesiones/${sesionSusurro.session_id}/limpiar`, {
            method: "POST"
        });
        const data = await leerJsonSeguroSusurro(response);
        if (!response.ok) throw new Error(data.detail || "No se pudo limpiar la sesion.");
        sesionSusurro = data;
        renderSesionSusurro(data);
    } catch (error) {
        mostrarErrorSusurro(error.message || "Error limpiando sesion.");
    }
}

function renderSesionSusurro(data) {
    setTextSusurro("estadoSesionSusurro", data.estado || "ACTIVA");
    setTextSusurro(
        "detalleSesionSusurro",
        `${data.agente || "Agente"} | ${data.modo || "demo"} | ${formatoHoraSusurro(data.updated_at)} | ${data.session_id || ""}`
    );
    renderActualSusurro(data.current);
    renderMetricasSusurro(data.metrics || {});
    renderAlertasSusurro(data.alerts || []);
    renderHistorialSusurro(data.fragments || []);
}

function renderActualSusurro(current) {
    const empty = document.getElementById("sugerenciaVaciaSusurro");
    const content = document.getElementById("sugerenciaActivaSusurro");
    const priority = current?.priority || "BAJA";

    document.getElementById("prioridadSusurro").className = `priority-badge ${priority.toLowerCase()}`;
    setTextSusurro("prioridadSusurro", priority);

    if (!current) {
        empty?.classList.remove("oculto");
        content?.classList.add("oculto");
        return;
    }

    empty?.classList.add("oculto");
    content?.classList.remove("oculto");
    setTextSusurro("intencionSusurro", current.intent || "-");
    setTextSusurro("tituloSusurro", current.title || "-");
    setTextSusurro("textoSugerenciaSusurro", current.suggestion || "-");
    setTextSusurro("objetivoSusurro", current.objective || "-");
    setTextSusurro("siguientePasoSusurro", current.next_step || "-");
}

function renderMetricasSusurro(metrics) {
    const checks = metrics.checks || {};
    toggleCheckSusurro("checkSaludo", checks.saludo);
    toggleCheckSusurro("checkMonto", checks.monto);
    toggleCheckSusurro("checkFecha", checks.fecha);
    toggleCheckSusurro("checkCanal", checks.canal);
    toggleCheckSusurro("check3c", checks.monto && checks.fecha && checks.canal);

    setTextSusurro("metClienteSusurro", metrics.cliente || 0);
    setTextSusurro("metAgenteSusurro", metrics.agente || 0);
    setTextSusurro("metAltaSusurro", metrics.alta || 0);
}

function renderAlertasSusurro(alerts) {
    const box = document.getElementById("alertasSusurro");
    if (!alerts.length) {
        box.innerHTML = `<div class="empty-row">Sin alertas activas.</div>`;
        return;
    }

    box.innerHTML = alerts.map(alert => `
        <article class="alert-item ${escapeHtmlSusurro(alert.type || "")}">
            <strong>${escapeHtmlSusurro(alert.title || "Alerta")}</strong>
            <span>${escapeHtmlSusurro(alert.message || "")}</span>
        </article>
    `).join("");
}

function renderHistorialSusurro(items) {
    const box = document.getElementById("historialSusurro");
    setTextSusurro("totalFragmentosSusurro", `${items.length} fragmentos`);
    if (!items.length) {
        box.innerHTML = `<div class="empty-row">Aun no hay fragmentos.</div>`;
        return;
    }

    box.innerHTML = items.slice().reverse().map(item => {
        const analysis = item.analysis || {};
        return `
            <article class="timeline-item ${escapeHtmlSusurro(item.speaker || "cliente")}">
                <div class="timeline-meta">
                    <strong>${escapeHtmlSusurro(item.speaker || "-")}</strong>
                    <span>${formatoHoraSusurro(item.timestamp)}</span>
                    <em>${escapeHtmlSusurro(analysis.priority || "BAJA")}</em>
                </div>
                <p>${escapeHtmlSusurro(item.text || "")}</p>
                <div class="timeline-analysis">
                    <span>${escapeHtmlSusurro(analysis.intent || "NO_CLARO")}</span>
                    <small>${escapeHtmlSusurro(analysis.reason || "")}</small>
                </div>
            </article>
        `;
    }).join("");
}

function setSpeakerSusurro(value) {
    speakerSusurro = value === "agente" ? "agente" : "cliente";
    document.getElementById("btnClienteSusurro")?.classList.toggle("active", speakerSusurro === "cliente");
    document.getElementById("btnAgenteSusurro")?.classList.toggle("active", speakerSusurro === "agente");
    const textarea = document.getElementById("fragmentoSusurro");
    if (textarea) {
        textarea.placeholder = speakerSusurro === "cliente"
            ? "Ejemplo cliente: no puedo pagar hoy porque estoy sin trabajo"
            : "Ejemplo agente: le confirmo que pagara 200 soles hoy por agente autorizado";
    }
}

function cargarEjemploSusurro() {
    const ejemplos = {
        cliente: [
            "no puedo pagar hoy porque estoy sin trabajo",
            "me puede hacer un descuento para cancelar la deuda",
            "ya pague en la manana por agente autorizado",
            "llameme mas tarde porque estoy trabajando"
        ],
        agente: [
            "le confirmo que pagara 200 soles hoy por agente autorizado",
            "buenos dias le saluda Carlos, lo llamo por su deuda pendiente",
            "me confirma cuanto pagara, donde pagara y como realizara el pago"
        ]
    };
    const lista = ejemplos[speakerSusurro] || ejemplos.cliente;
    document.getElementById("fragmentoSusurro").value = lista[Math.floor(Math.random() * lista.length)];
}

function toggleCheckSusurro(id, active) {
    document.getElementById(id)?.classList.toggle("done", Boolean(active));
}

function setTextSusurro(id, value) {
    const el = document.getElementById(id);
    if (el) el.textContent = value;
}

function mostrarErrorSusurro(message) {
    if (typeof crmAlert === "function") {
        crmAlert({ title: "Susurro IA", message, tone: "danger" });
        return;
    }
    alert(message);
}

async function leerJsonSeguroSusurro(response) {
    try {
        return await response.json();
    } catch {
        return {};
    }
}

function formatoHoraSusurro(value) {
    if (!value) return "-";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return value;
    return date.toLocaleTimeString("es-PE", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function escapeHtmlSusurro(value) {
    return String(value ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

window.crearSesionSusurro = crearSesionSusurro;
window.enviarFragmentoSusurro = enviarFragmentoSusurro;
window.limpiarSusurro = limpiarSusurro;
window.setSpeakerSusurro = setSpeakerSusurro;
window.cargarEjemploSusurro = cargarEjemploSusurro;
