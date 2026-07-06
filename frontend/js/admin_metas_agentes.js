const BASE_URL_ADMIN_METAS = `${window.location.protocol}//${window.location.hostname}:8000`;

let carterasMeta = [];
let agentesMeta = [];
let metasAgentes = [];

document.addEventListener("DOMContentLoaded", () => {
    if (!exigirSesion()) return;
    if (!puedeVerCorporativo()) {
        alert("No tienes acceso a configuracion.");
        irInicio();
        return;
    }

    prepararMesesMeta();
    cargarAdminMetas();
});

async function cargarAdminMetas() {
    try {
        mostrarAdminMetasToast("Cargando metas...", "info");
        const codmes = document.getElementById("codmesMeta").value;
        const filtroCartera = document.getElementById("filtroCarteraTabla")?.value || "";
        const params = new URLSearchParams({ codmes });
        if (filtroCartera) params.set("idcartera", filtroCartera);

        const [carteras, metas] = await Promise.all([
            fetchJsonMetas("/admin-metas-agentes/carteras"),
            fetchJsonMetas(`/admin-metas-agentes/metas?${params.toString()}`),
        ]);

        carterasMeta = carteras.data || [];
        metasAgentes = metas.data || [];

        pintarCarterasMeta();
        await cargarAgentesMeta();
        pintarTablaMetasAgentes();
        mostrarAdminMetasToast("Metas actualizadas.", "ok");
    } catch (error) {
        console.error(error);
        mostrarAdminMetasToast(`No se pudo cargar. ${error.message || ""}`, "error");
    }
}

async function cargarAgentesMeta() {
    const idcartera = document.getElementById("carteraMetaSelect").value;
    const params = new URLSearchParams();
    if (idcartera) params.set("idcartera", idcartera);
    const agentes = await fetchJsonMetas(`/admin-metas-agentes/agentes?${params.toString()}`);
    agentesMeta = agentes.data || [];
    pintarAgentesMeta();
}

async function seleccionarCarteraMeta() {
    await cargarAgentesMeta();
}

async function fetchJsonMetas(path, options = {}) {
    const response = await fetch(`${BASE_URL_ADMIN_METAS}${path}`, {
        cache: "no-store",
        ...options,
        headers: {
            "Content-Type": "application/json",
            ...(options.headers || {}),
        },
    });
    if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error(error.detail || `HTTP ${response.status}`);
    }
    return response.json();
}

function prepararMesesMeta() {
    const select = document.getElementById("codmesMeta");
    const hoy = new Date();
    const opciones = [];

    for (let offset = -3; offset <= 2; offset++) {
        const fecha = new Date(hoy.getFullYear(), hoy.getMonth() + offset, 1);
        const codmes = `${fecha.getFullYear()}${String(fecha.getMonth() + 1).padStart(2, "0")}`;
        opciones.push(`<option value="${codmes}">${codmes} - ${fecha.toLocaleDateString("es-PE", { month: "long", year: "numeric" })}</option>`);
    }

    select.innerHTML = opciones.join("");
    select.value = `${hoy.getFullYear()}${String(hoy.getMonth() + 1).padStart(2, "0")}`;
}

function pintarCarterasMeta() {
    const selects = [
        document.getElementById("carteraMetaSelect"),
        document.getElementById("filtroCarteraTabla"),
    ].filter(Boolean);

    selects.forEach(select => {
        const actual = select.value;
        const placeholder = select.id === "filtroCarteraTabla" ? "Todas las carteras" : "Seleccionar cartera";
        select.innerHTML = `<option value="">${placeholder}</option>` + carterasMeta.map(item => `
            <option value="${h(item.idcartera)}">${h(item.idcartera)} - ${h(item.cartera)}</option>
        `).join("");
        select.value = carterasMeta.some(item => String(item.idcartera) === String(actual)) ? actual : "";
    });
}

function pintarAgentesMeta() {
    const select = document.getElementById("agenteMetaSelect");
    const actual = select.value;

    select.innerHTML = `<option value="">Aplicar a toda la cartera</option>` + agentesMeta.map(item => `
        <option value="${h(item.usuario)}">${h(item.agente)} (${h(item.cartera)})</option>
    `).join("");

    select.value = agentesMeta.some(item => String(item.usuario) === String(actual)) ? actual : "";
}

function pintarTablaMetasAgentes() {
    const tbody = document.getElementById("tablaMetasAgentes");

    if (!metasAgentes.length) {
        tbody.innerHTML = `<tr><td colspan="6" class="empty-table">Sin metas registradas para el filtro seleccionado.</td></tr>`;
        return;
    }

    tbody.innerHTML = metasAgentes.map(item => `
        <tr>
            <td>${h(item.codmes)}</td>
            <td><span class="badge-cartera">${h(item.idcartera)} - ${h(item.cartera)}</span></td>
            <td class="left">
                <strong>${h(item.agente || item.usuario)}</strong>
                <small>${h(item.usuario)}</small>
            </td>
            <td class="money">${solesMeta(item.meta_mensual)}</td>
            <td>${h(item.usuario_actualizacion || "-")}</td>
            <td>${formatDateMeta(item.fecha_actualizacion)}</td>
        </tr>
    `).join("");
}

async function guardarMetaAgente() {
    const codmes = document.getElementById("codmesMeta").value;
    const idcartera = document.getElementById("carteraMetaSelect").value;
    const usuario = document.getElementById("agenteMetaSelect").value;
    const meta = Number(document.getElementById("montoMetaAgente").value || 0);

    if (!idcartera) {
        mostrarAdminMetasToast("Selecciona una cartera.", "error");
        return;
    }

    try {
        const endpoint = usuario
            ? "/admin-metas-agentes/metas"
            : "/admin-metas-agentes/metas-cartera";
        const payload = {
            codmes,
            idcartera: Number(idcartera),
            meta_mensual: meta,
            usuario_actualizacion: localStorage.getItem("dni") || "SIN_USUARIO",
        };

        if (usuario) {
            payload.usuario = usuario;
        }

        const resultado = await fetchJsonMetas(endpoint, {
            method: "POST",
            body: JSON.stringify(payload),
        });

        document.getElementById("montoMetaAgente").value = "";
        await cargarAdminMetas();
        const total = resultado.agentes_actualizados;
        mostrarAdminMetasToast(
            total ? `Meta general guardada para ${total} agentes activos.` : "Meta guardada correctamente.",
            "ok"
        );
    } catch (error) {
        console.error(error);
        mostrarAdminMetasToast(`No se pudo guardar. ${error.message || ""}`, "error");
    }
}

function limpiarMetaAgente() {
    document.getElementById("carteraMetaSelect").value = "";
    document.getElementById("agenteMetaSelect").value = "";
    document.getElementById("montoMetaAgente").value = "";
    cargarAgentesMeta();
}

function mostrarAdminMetasToast(texto, tipo = "info") {
    const toast = document.getElementById("adminMetasToast");
    toast.textContent = texto;
    toast.className = `admin-toast activo ${tipo}`;
    clearTimeout(window._adminMetasToastTimer);
    window._adminMetasToastTimer = setTimeout(() => toast.classList.remove("activo"), 2600);
}

function solesMeta(value) {
    return Number(value || 0).toLocaleString("es-PE", {
        style: "currency",
        currency: "PEN",
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
    });
}

function formatDateMeta(value) {
    if (!value) return "-";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return value;
    return date.toLocaleString("es-PE", {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
    });
}

function h(value) {
    return String(value ?? "-")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}
