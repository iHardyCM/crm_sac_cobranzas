// cambiar_clave.js
// Cambio de contraseña del propio usuario. Se identifica SOLO por el access_token:
// no se envía DNI ni perfil. Tras el cambio, los datos de sesión se leen de /auth/me.

const BASE_URL_CAMBIO_CLAVE = `${window.location.protocol}//${window.location.hostname}:8000`;
let cambioEnProceso = false;

document.addEventListener("DOMContentLoaded", () => {
    if (!localStorage.getItem("access_token")) {
        sessionStorage.setItem("loginMensaje", "Inicia sesion para cambiar tu contraseña.");
        window.location.href = "login.html";
        return;
    }

    const obligatorio = localStorage.getItem("requiere_cambio_clave") === "true";
    if (!obligatorio) {
        // Cambio voluntario: se permite volver al CRM.
        document.getElementById("cambioEtiqueta").textContent = "Cambio de contraseña";
        document.getElementById("cambioDescripcion").textContent =
            "Ingresa tu contraseña actual y la nueva que quieres usar.";
        if (localStorage.getItem("dni") && localStorage.getItem("agente")) {
            document.getElementById("cambioVolver").classList.remove("oculto");
        }
    }

    document.getElementById("claveActual")?.focus();
});

function authHeadersCambioClave() {
    return {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${localStorage.getItem("access_token") || ""}`
    };
}

async function cambiarClave() {
    if (cambioEnProceso) return;

    const actual = document.getElementById("claveActual").value;
    const nueva = document.getElementById("claveNueva").value;
    const confirmacion = document.getElementById("claveConfirmacion").value;

    if (!actual || !nueva || !confirmacion) {
        mostrarCambioMensaje("Completa los tres campos.");
        return;
    }
    if (nueva.length < 8) {
        mostrarCambioMensaje("La nueva contraseña debe tener al menos 8 caracteres.");
        return;
    }
    if (nueva !== confirmacion) {
        mostrarCambioMensaje("La nueva contraseña y su confirmación no coinciden.");
        return;
    }

    try {
        cambioEnProceso = true;
        setCambioLoading(true);
        mostrarCambioMensaje("Guardando...", "info");

        const res = await fetch(`${BASE_URL_CAMBIO_CLAVE}/auth/cambiar-clave`, {
            method: "POST",
            headers: authHeadersCambioClave(),
            body: JSON.stringify({ clave_actual: actual, clave_nueva: nueva, confirmacion })
        });

        if (res.status === 401) {
            sesionVencidaCambioClave();
            return;
        }

        const data = await leerJsonSeguro(res);
        if (!res.ok || !data?.ok) {
            mostrarCambioMensaje(data?.detail || "No se pudo cambiar la contraseña.");
            return;
        }

        limpiarCamposCambioClave();
        localStorage.setItem("requiere_cambio_clave", "false");
        try {
            await cargarSesionDesdeServidor();
        } catch (errorSesion) {
            // La clave ya se cambió; si no se pudo leer la sesión, se pide ingresar de nuevo.
            console.error("ERROR /auth/me tras cambio de clave:", errorSesion);
            localStorage.clear();
            sessionStorage.clear();
            sessionStorage.setItem("loginMensaje", "Tu contraseña se cambió. Inicia sesión con la nueva.");
            window.location.href = "login.html";
            return;
        }
        window.location.href = "home.html";
    } catch (error) {
        console.error("ERROR CAMBIO CLAVE:", error);
        mostrarCambioMensaje("No se pudo conectar con el servidor.");
    } finally {
        cambioEnProceso = false;
        setCambioLoading(false);
    }
}

// Datos de compatibilidad para las pantallas actuales (no son seguridad):
// se toman de lo que el backend reconoce para el token.
async function cargarSesionDesdeServidor() {
    const res = await fetch(`${BASE_URL_CAMBIO_CLAVE}/auth/me`, { headers: authHeadersCambioClave() });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);

    const user = await res.json();
    const idcarteras = Array.isArray(user.idcarteras) ? user.idcarteras.filter(Boolean) : [];

    localStorage.setItem("dni", user.dni);
    localStorage.setItem("agente", user.agente);
    localStorage.setItem("tipo", user.tipo);
    localStorage.setItem("idcartera", user.idcartera || idcarteras[0] || "");
    localStorage.setItem("idcarteras", idcarteras.join(","));
    if (!localStorage.getItem("session_started_at")) {
        localStorage.setItem("session_started_at", new Date().toISOString());
    }
}

function sesionVencidaCambioClave() {
    localStorage.clear();
    sessionStorage.clear();
    sessionStorage.setItem("loginMensaje", "Sesion vencida o invalida. Inicia sesion nuevamente.");
    window.location.href = "login.html";
}

async function leerJsonSeguro(res) {
    try {
        return await res.json();
    } catch (error) {
        return null;
    }
}

function limpiarCamposCambioClave() {
    ["claveActual", "claveNueva", "claveConfirmacion"].forEach(id => {
        const campo = document.getElementById(id);
        if (campo) campo.value = "";
    });
}

function setCambioLoading(loading) {
    const boton = document.getElementById("cambioBtn");
    if (boton) {
        boton.disabled = loading;
        boton.textContent = loading ? "Guardando..." : "Guardar nueva contraseña";
    }
    ["claveActual", "claveNueva", "claveConfirmacion"].forEach(id => {
        const campo = document.getElementById(id);
        if (campo) campo.disabled = loading;
    });
}

function mostrarCambioMensaje(texto, tipo = "error") {
    const mensaje = document.getElementById("cambioMensaje");
    if (!mensaje) return;
    mensaje.textContent = texto;
    mensaje.className = `login-message ${tipo}`;
}
