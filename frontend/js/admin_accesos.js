// admin_accesos.js
// Administración de accesos al CRM. Todas las llamadas llevan el access_token;
// el backend decide si el usuario es ADMINISTRADOR (403 si no lo es).
// Ocultar botones aquí es solo comodidad visual, no seguridad.

const BASE_URL_ACCESOS = `${window.location.protocol}//${window.location.hostname}:8000`;

const ETIQUETAS_ESTADO_ACCESO = {
    SIN_ACCESO: "Sin acceso",
    ACTIVO: "Activo",
    CAMBIO_OBLIGATORIO: "Cambio obligatorio",
    BLOQUEADO: "Bloqueado",
    DESHABILITADO: "Deshabilitado",
    SIN_CLAVE: "Sin clave"
};

let usuariosAccesos = [];

document.addEventListener("DOMContentLoaded", () => {
    if (!exigirSesion()) return;
    if (!localStorage.getItem("access_token")) {
        irALoginAccesos("Inicia sesion nuevamente para administrar accesos.");
        return;
    }

    document.getElementById("accesosBuscarForm").addEventListener("submit", event => {
        event.preventDefault();
        cargarUsuariosAccesos();
    });
    document.getElementById("accesosActualizar").addEventListener("click", cargarUsuariosAccesos);
    document.getElementById("tablaAccesos").addEventListener("click", manejarAccionTabla);
    document.getElementById("claveTemporalCopiar").addEventListener("click", copiarClaveTemporal);
    document.getElementById("claveTemporalCerrar").addEventListener("click", ocultarClaveTemporal);

    cargarUsuariosAccesos();
});

async function fetchAccesos(path, options = {}) {
    const response = await fetch(`${BASE_URL_ACCESOS}${path}`, {
        cache: "no-store",
        ...options,
        headers: {
            "Content-Type": "application/json",
            "Authorization": `Bearer ${localStorage.getItem("access_token") || ""}`,
            ...(options.headers || {}),
        },
    });

    if (response.status === 401) {
        irALoginAccesos("Sesion vencida o invalida. Inicia sesion nuevamente.");
        throw new Error("Sesion no valida.");
    }

    let data = null;
    try {
        data = await response.json();
    } catch (error) {
        data = null;
    }

    if (!response.ok) {
        const mensaje = response.status === 403
            ? "Tu perfil no tiene permiso para administrar accesos."
            : (data?.detail || `No se pudo completar la operación (HTTP ${response.status}).`);
        throw new Error(mensaje);
    }
    return data;
}

async function cargarUsuariosAccesos() {
    const q = document.getElementById("accesosBusqueda").value.trim();
    const params = new URLSearchParams({ limite: "150" });
    if (q) params.set("q", q);

    try {
        mostrarAccesosToast("Cargando usuarios...", "info");
        const respuesta = await fetchAccesos(`/admin-accesos/usuarios?${params.toString()}`);
        usuariosAccesos = respuesta?.data || [];
        pintarTablaAccesos();
        mostrarAccesosToast(`${usuariosAccesos.length} usuario(s) encontrados.`, "ok");
    } catch (error) {
        console.error(error);
        usuariosAccesos = [];
        pintarTablaAccesos(error.message);
        mostrarAccesosToast(error.message, "error");
    }
}

function pintarTablaAccesos(mensajeError = "") {
    const tbody = document.getElementById("tablaAccesos");

    if (!usuariosAccesos.length) {
        tbody.innerHTML = `<tr><td colspan="8" class="empty-table">${h(mensajeError || "Sin usuarios para la búsqueda.")}</td></tr>`;
        return;
    }

    tbody.innerHTML = usuariosAccesos.map(u => `
        <tr>
            <td class="left">
                <strong>${h(`${u.nombres || ""} ${u.apellidos || ""}`.trim() || u.dni)}</strong>
                <small>${h(u.dni)}</small>
            </td>
            <td>${h(u.tipo)}</td>
            <td>${h(u.idcartera)}</td>
            <td><span class="estado-acceso ${h(String(u.estado_acceso || "").toLowerCase())}">${h(ETIQUETAS_ESTADO_ACCESO[u.estado_acceso] || u.estado_acceso)}</span></td>
            <td>${formatDateAccesos(u.fecha_ultimo_login)}</td>
            <td>${u.tiene_acceso ? h(u.intentos_fallidos) : "-"}</td>
            <td>${formatDateAccesos(u.bloqueado_hasta)}</td>
            <td><div class="acciones-acceso">${botonesAcciones(u)}</div></td>
        </tr>
    `).join("");
}

function botonesAcciones(u) {
    const dni = h(u.dni);
    const boton = (accion, texto, clase = "btn-secondary") =>
        `<button type="button" class="${clase}" data-accion="${accion}" data-dni="${dni}">${texto}</button>`;

    if (!u.tiene_acceso) return boton("habilitar", "Habilitar acceso", "btn-primary");
    if (u.estado_acceso === "DESHABILITADO") return boton("habilitar", "Rehabilitar", "btn-primary");

    const botones = [];
    if (u.estado_acceso === "BLOQUEADO" || Number(u.intentos_fallidos) > 0) {
        botones.push(boton("desbloquear", "Desbloquear"));
    }
    botones.push(boton("reset-clave", "Resetear clave"));
    botones.push(boton("deshabilitar", "Deshabilitar", "btn-peligro"));
    return botones.join("");
}

const CONFIRMACIONES = {
    "habilitar": u => ({
        title: u.tiene_acceso ? "Rehabilitar acceso" : "Habilitar acceso",
        message: `Se generará una clave temporal para ${nombreUsuario(u)}. Deberá cambiarla en su primer ingreso.`,
        acceptText: "Generar clave",
        tone: "primary"
    }),
    "reset-clave": u => ({
        title: "Resetear clave",
        message: `La clave actual de ${nombreUsuario(u)} dejará de funcionar y se generará una temporal nueva.`,
        acceptText: "Resetear",
        tone: "danger"
    }),
    "desbloquear": u => ({
        title: "Desbloquear cuenta",
        message: `Se reiniciarán los intentos fallidos de ${nombreUsuario(u)}.`,
        acceptText: "Desbloquear",
        tone: "primary"
    }),
    "deshabilitar": u => ({
        title: "Deshabilitar acceso",
        message: `${nombreUsuario(u)} no podrá volver a iniciar sesión y los módulos ya protegidos dejarán de responderle de inmediato, incluso con una sesión abierta.`,
        acceptText: "Deshabilitar",
        tone: "danger"
    }),
};

async function manejarAccionTabla(event) {
    const boton = event.target.closest("button[data-accion]");
    if (!boton) return;

    const accion = boton.dataset.accion;
    const dni = boton.dataset.dni;
    const usuario = usuariosAccesos.find(u => String(u.dni) === String(dni));
    if (!usuario || !CONFIRMACIONES[accion]) return;

    const confirmado = typeof window.crmConfirm === "function"
        ? await window.crmConfirm(CONFIRMACIONES[accion](usuario))
        : window.confirm(CONFIRMACIONES[accion](usuario).message);
    if (!confirmado) return;

    boton.disabled = true;
    try {
        const respuesta = await fetchAccesos(`/admin-accesos/${encodeURIComponent(dni)}/${accion}`, { method: "POST" });

        if (respuesta?.clave_temporal) {
            mostrarClaveTemporal(usuario, respuesta.clave_temporal);
        }
        await cargarUsuariosAccesos();
        mostrarAccesosToast(mensajeExito(accion, respuesta), "ok");
    } catch (error) {
        console.error(error);
        mostrarAccesosToast(error.message, "error");
        boton.disabled = false;
    }
}

function mensajeExito(accion, respuesta) {
    if (accion === "habilitar") return respuesta?.accion === "REHABILITAR" ? "Acceso rehabilitado." : "Acceso habilitado.";
    if (accion === "reset-clave") return "Clave reseteada.";
    if (accion === "desbloquear") return "Cuenta desbloqueada.";
    if (accion === "deshabilitar") return respuesta?.sin_cambios ? "La cuenta ya estaba deshabilitada." : "Acceso deshabilitado.";
    return "Operación completada.";
}

// La clave temporal solo vive en el DOM mientras se muestra: no se guarda en
// variables globales, localStorage ni sessionStorage, y se borra al ocultarla.
function mostrarClaveTemporal(usuario, clave) {
    document.getElementById("claveTemporalUsuario").textContent = `${nombreUsuario(usuario)} · DNI ${usuario.dni}`;
    document.getElementById("claveTemporalValor").textContent = clave;
    const card = document.getElementById("claveTemporalCard");
    card.classList.remove("oculto");
    card.scrollIntoView({ behavior: "smooth", block: "start" });
}

function ocultarClaveTemporal() {
    document.getElementById("claveTemporalValor").textContent = "";
    document.getElementById("claveTemporalUsuario").textContent = "-";
    document.getElementById("claveTemporalCard").classList.add("oculto");
}

async function copiarClaveTemporal() {
    const valor = document.getElementById("claveTemporalValor").textContent;
    if (!valor) return;
    try {
        await navigator.clipboard.writeText(valor);
        mostrarAccesosToast("Clave copiada al portapapeles.", "ok");
    } catch (error) {
        mostrarAccesosToast("No se pudo copiar. Selecciona la clave y cópiala manualmente.", "error");
    }
}

function nombreUsuario(u) {
    return `${u.nombres || ""} ${u.apellidos || ""}`.trim() || u.dni;
}

function irALoginAccesos(mensaje) {
    localStorage.clear();
    sessionStorage.clear();
    sessionStorage.setItem("loginMensaje", mensaje);
    window.location.href = "login.html";
}

function mostrarAccesosToast(texto, tipo = "info") {
    const toast = document.getElementById("adminAccesosToast");
    toast.textContent = texto;
    toast.className = `admin-toast activo ${tipo}`;
    clearTimeout(window._adminAccesosToastTimer);
    window._adminAccesosToastTimer = setTimeout(() => toast.classList.remove("activo"), 3200);
}

function formatDateAccesos(value) {
    if (!value) return "-";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return h(value);
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
