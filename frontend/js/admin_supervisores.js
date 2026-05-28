const BASE_URL_ADMIN_SUPER = `${window.location.protocol}//${window.location.hostname}:8000`;

let supervisoresAdmin = [];
let carterasAdmin = [];
let asignacionesAdmin = [];

document.addEventListener("DOMContentLoaded", () => {
    if (!exigirSesion()) return;
    if (!puedeVerCorporativo()) {
        alert("No tienes acceso a configuracion.");
        irInicio();
        return;
    }
    cargarAdminSupervisores();
});

async function cargarAdminSupervisores() {
    try {
        mostrarAdminToast("Cargando mantenimiento...", "info");
        const [supervisores, carteras, asignaciones] = await Promise.all([
            fetchJson("/admin-supervisores/supervisores"),
            fetchJson("/admin-supervisores/carteras"),
            fetchJson("/admin-supervisores/asignaciones"),
        ]);

        supervisoresAdmin = supervisores.data || [];
        carterasAdmin = carteras.data || [];
        asignacionesAdmin = asignaciones.data || [];

        pintarSupervisores();
        pintarCarteras();
        pintarAsignaciones();
        mostrarAdminToast("Mantenimiento actualizado.", "ok");
    } catch (error) {
        console.error(error);
        mostrarAdminToast(`No se pudo cargar. ${error.message || ""}`, "error");
    }
}

async function fetchJson(path, options = {}) {
    const response = await fetch(`${BASE_URL_ADMIN_SUPER}${path}`, {
        cache: "no-store",
        ...options,
        headers: {
            "Content-Type": "application/json",
            ...(options.headers || {}),
        },
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
}

function pintarSupervisores() {
    const select = document.getElementById("supervisorSelect");
    const actual = select.value;

    select.innerHTML = `<option value="">Seleccionar supervisor</option>` + supervisoresAdmin.map(item => `
        <option value="${h(item.usuario)}">${h(item.supervisor)}</option>
    `).join("");

    select.value = supervisoresAdmin.some(item => String(item.usuario) === String(actual)) ? actual : "";
}

function pintarCarteras() {
    const contenedor = document.getElementById("carterasChecklist");
    const usuario = document.getElementById("supervisorSelect").value;
    const asignadas = new Set(
        asignacionesAdmin
            .filter(item => String(item.usuario) === String(usuario))
            .map(item => String(item.idcartera))
    );

    contenedor.innerHTML = carterasAdmin.map(item => `
        <label class="cartera-check">
            <input type="checkbox" value="${h(item.idcartera)}" ${asignadas.has(String(item.idcartera)) ? "checked" : ""}>
            <span>${h(item.idcartera)} - ${h(item.cartera)}</span>
        </label>
    `).join("");
}

function pintarAsignaciones() {
    const tbody = document.getElementById("tablaAsignacionesSupervisor");

    if (!asignacionesAdmin.length) {
        tbody.innerHTML = `<tr><td colspan="4" class="empty-table">Sin asignaciones adicionales registradas.</td></tr>`;
        return;
    }

    tbody.innerHTML = asignacionesAdmin.map(item => `
        <tr>
            <td class="left">
                <strong>${h(item.supervisor || item.usuario)}</strong>
                <small>${h(item.usuario)}</small>
            </td>
            <td><span class="badge-cartera">${h(item.idcartera)} - ${h(item.cartera)}</span></td>
            <td>${h(item.usuario_actualizacion || "-")}</td>
            <td>${formatDate(item.fecha_actualizacion)}</td>
        </tr>
    `).join("");
}

function seleccionarSupervisorAdmin() {
    pintarCarteras();
}

function limpiarAdminSupervisores() {
    document.getElementById("supervisorSelect").value = "";
    pintarCarteras();
}

async function guardarAdminSupervisores() {
    const usuario = document.getElementById("supervisorSelect").value;
    if (!usuario) {
        mostrarAdminToast("Selecciona un supervisor.", "error");
        return;
    }

    const idcarteras = [...document.querySelectorAll("#carterasChecklist input:checked")]
        .map(input => Number(input.value));

    try {
        const payload = {
            usuario,
            idcarteras,
            usuario_actualizacion: localStorage.getItem("dni") || "SIN_USUARIO",
        };

        await fetchJson("/admin-supervisores/asignaciones", {
            method: "POST",
            body: JSON.stringify(payload),
        });

        const asignaciones = await fetchJson("/admin-supervisores/asignaciones");
        asignacionesAdmin = asignaciones.data || [];
        pintarAsignaciones();
        pintarCarteras();
        mostrarAdminToast("Asignaciones guardadas correctamente.", "ok");
    } catch (error) {
        console.error(error);
        mostrarAdminToast(`No se pudo guardar. ${error.message || ""}`, "error");
    }
}

function mostrarAdminToast(texto, tipo = "info") {
    const toast = document.getElementById("adminSuperToast");
    toast.textContent = texto;
    toast.className = `admin-toast activo ${tipo}`;
    clearTimeout(window._adminSuperToastTimer);
    window._adminSuperToastTimer = setTimeout(() => toast.classList.remove("activo"), 2600);
}

function formatDate(value) {
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
