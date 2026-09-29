function normalizarTipoUsuario(tipo) {
    return String(tipo || "")
        .trim()
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "")
        .toUpperCase();
}

function puedeVerCorporativo(tipo) {
    const tipoNormalizado = normalizarTipoUsuario(tipo || localStorage.getItem("tipo"));
    return [
        "JEFE DE CARTERA",
        "JEFE DE CARTERAS",
        "JEFE DE COBRANZA",
        "JEFE CARTERA",
        "ADMINISTRADOR"
    ].includes(tipoNormalizado);
}

function esSupervisor(tipo) {
    const tipoNormalizado = normalizarTipoUsuario(tipo || localStorage.getItem("tipo"));
    return tipoNormalizado === "SUPERVISOR"
        || tipoNormalizado === "SUPERVISORA"
        || tipoNormalizado.includes("SUPERVISOR");
}

function obtenerIdCarterasSesion() {
    const ids = [
        ...(localStorage.getItem("idcarteras") || "").split(","),
        localStorage.getItem("idcartera")
    ]
        .map(x => String(x || "").trim())
        .filter(Boolean);

    return [...new Set(ids)];
}

function obtenerQueryCarterasSesion() {
    const ids = obtenerIdCarterasSesion();

    if (ids.length > 1) {
        return `idcarteras=${encodeURIComponent(ids.join(","))}`;
    }

    if (ids.length === 1) {
        return `idcartera=${encodeURIComponent(ids[0])}`;
    }

    return "";
}

function esCarteraCompartamos(idcartera) {
    const carteras = idcartera
        ? [String(idcartera).trim()]
        : obtenerIdCarterasSesion();

    return carteras.some(cartera => ["124", "126", "128", "133", "139", "144"].includes(cartera));
}

function puedeVerPdpHoy(tipo) {
    return puedeVerCorporativo(tipo) || esSupervisor(tipo);
}

function obtenerRutaPorTipo(tipo) {
    const tipoNormalizado = normalizarTipoUsuario(tipo);

    if (puedeVerCorporativo(tipoNormalizado)) {
        return "corporativo.html";
    }

    if (esSupervisor(tipoNormalizado)) {
        return "supervisor.html";
    }

    return "compromisos.html";
}

function irInicio() {
    window.location.href = "home.html";
}

function exigirSesion() {
    const dni = localStorage.getItem("dni");
    const agente = localStorage.getItem("agente");

    if (!dni || !agente) {
        sessionStorage.setItem("loginMensaje", "Sesion vencida o invalida. Inicia sesion nuevamente.");
        window.location.href = "login.html";
        return false;
    }

    return true;
}

function exigirAccesoCorporativo() {
    if (!exigirSesion()) return false;

    if (!puedeVerCorporativo()) {
        sessionStorage.setItem("homeMensaje", "Tu perfil no tiene acceso al panel corporativo.");
        irInicio();
        return false;
    }

    return true;
}

function exigirAccesoPdpHoy() {
    if (!exigirSesion()) return false;

    if (!puedeVerPdpHoy()) {
        sessionStorage.setItem("homeMensaje", "Tu perfil no tiene acceso a promesas con vencimiento hoy.");
        irInicio();
        return false;
    }

    return true;
}

function cerrarSesion() {
    localStorage.clear();
    sessionStorage.clear();
    window.location.href = "login.html";
}

// ---------------------------------------------------------------------------
// Validacion real de la sesion contra el backend (GET /auth/me).
//
// exigirSesion() solo mira localStorage y se mantiene por compatibilidad, pero
// NO es seguridad. Las paginas migradas esperan asegurarSesionBackend() antes
// de cargar cualquier dato: si la cuenta fue deshabilitada, /auth/me responde
// 401 y el usuario vuelve al login aunque tenga datos viejos en localStorage.
// ---------------------------------------------------------------------------

const SESION_API_BASE = `${window.location.protocol}//${window.location.hostname}:8000`;
const MENSAJE_SESION_REVOCADA = "Tu sesión ya no está habilitada. Inicia sesión nuevamente.";
const MENSAJE_CAMBIO_CLAVE_BACKEND = "Debes cambiar tu contraseña antes de continuar.";

let _promesaSesionBackend = null;

function obtenerAccessToken() {
    try {
        return localStorage.getItem("access_token") || "";
    } catch (error) {
        return "";
    }
}

// Agrega Authorization: Bearer al objeto de headers recibido (sin pisar uno existente).
function agregarAuthorizationHeader(headers) {
    const resultado = new Headers(headers || {});
    const token = obtenerAccessToken();
    if (token && !resultado.has("Authorization")) {
        resultado.set("Authorization", `Bearer ${token}`);
    }
    return resultado;
}

function cerrarSesionPorBackend(mensaje = MENSAJE_SESION_REVOCADA) {
    localStorage.clear();
    sessionStorage.clear();
    sessionStorage.setItem("loginMensaje", mensaje);
    window.location.href = "login.html";
}

function irACambioClaveObligatorio() {
    window.location.href = "cambiar_clave.html";
}

// true si la respuesta es el 403 estable del cambio de clave obligatorio.
function esRespuestaCambioClave(status, data) {
    return status === 403 && data && data.detail === MENSAJE_CAMBIO_CLAVE_BACKEND;
}

// Error tecnico: no se asume sesion valida, pero tampoco se borran credenciales.
function mostrarErrorSesionBackend(mensaje) {
    if (!document.body) return;
    let aviso = document.getElementById("crmSesionErrorBackend");
    if (!aviso) {
        aviso = document.createElement("div");
        aviso.id = "crmSesionErrorBackend";
        aviso.setAttribute("role", "alert");
        aviso.style.cssText = "position:fixed;inset:0;z-index:99999;display:flex;align-items:center;justify-content:center;"
            + "background:rgba(7,26,49,.72);padding:20px;font-family:Inter,system-ui,sans-serif;";
        aviso.innerHTML = `
            <div style="max-width:440px;background:#fff;color:#12243a;border-radius:16px;padding:24px;box-shadow:0 20px 50px rgba(0,0,0,.3)">
                <strong style="display:block;font-size:17px;margin-bottom:8px">No se pudo verificar tu sesión</strong>
                <p data-sesion-mensaje style="margin:0 0 16px;color:#5f7083;line-height:1.5"></p>
                <button type="button" style="border:0;border-radius:10px;background:#075fc8;color:#fff;font-weight:800;padding:10px 16px;cursor:pointer"
                    onclick="window.location.reload()">Reintentar</button>
            </div>`;
        document.body.appendChild(aviso);
    }
    aviso.querySelector("[data-sesion-mensaje]").textContent = mensaje;
}

async function validarSesionBackend() {
    const token = obtenerAccessToken();
    if (!token) {
        cerrarSesionPorBackend("Inicia sesión para continuar.");
        return null;
    }

    let response;
    try {
        response = await fetch(`${SESION_API_BASE}/auth/me`, {
            cache: "no-store",
            headers: { "Authorization": `Bearer ${token}` }
        });
    } catch (error) {
        mostrarErrorSesionBackend("El servidor no respondió. Revisa tu conexión e intenta nuevamente.");
        return null;
    }

    let data = null;
    try {
        data = await response.json();
    } catch (error) {
        data = null;
    }

    if (response.status === 401) {
        cerrarSesionPorBackend(MENSAJE_SESION_REVOCADA);
        return null;
    }
    if (esRespuestaCambioClave(response.status, data)) {
        irACambioClaveObligatorio();
        return null;
    }
    if (!response.ok || !data || !data.dni) {
        mostrarErrorSesionBackend("Ocurrió un problema técnico al validar tu sesión. Intenta nuevamente en un momento.");
        return null;
    }

    // La identidad sale del backend; lo que hubiera en localStorage se reemplaza.
    const idcarteras = Array.isArray(data.idcarteras) ? data.idcarteras.filter(Boolean) : [];
    localStorage.setItem("dni", data.dni);
    localStorage.setItem("agente", data.agente || data.dni);
    localStorage.setItem("tipo", data.tipo || "");
    localStorage.setItem("idcartera", data.idcartera || idcarteras[0] || "");
    localStorage.setItem("idcarteras", idcarteras.join(","));

    if (localStorage.getItem("requiere_cambio_clave") === "true") {
        irACambioClaveObligatorio();
        return null;
    }

    return data;
}

// Bootstrap unico por pagina: todas las cargas esperan la misma validacion.
function asegurarSesionBackend() {
    if (!_promesaSesionBackend) {
        _promesaSesionBackend = validarSesionBackend();
    }
    return _promesaSesionBackend;
}
