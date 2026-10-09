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

// Codigo estable que el backend envia en los 403 (cabecera X-CRM-Codigo-Error).
const HEADER_CODIGO_ERROR = "X-CRM-Codigo-Error";
const CODIGOS_ERROR_BACKEND = Object.freeze({
    CAMBIO_CLAVE_OBLIGATORIO: "CAMBIO_CLAVE_OBLIGATORIO",
    ACCESO_DENEGADO: "ACCESO_DENEGADO",
});

let _promesaSesionBackend = null;
let _redireccionSesionEnCurso = false;
window.crmPermisosVistas = null;

function puedeUsarVista(clave) {
    const permisos = window.crmPermisosVistas;
    return permisos && Object.prototype.hasOwnProperty.call(permisos, clave)
        ? permisos[clave] === true
        : null;
}

// Resultado de la ultima validacion (para que las paginas distingan los casos).
const ESTADOS_SESION_BACKEND = Object.freeze({
    VALIDA: "VALIDA",
    SIN_TOKEN: "SIN_TOKEN",
    REVOCADA: "REVOCADA",
    CAMBIO_OBLIGATORIO: "CAMBIO_OBLIGATORIO",
    ERROR_TECNICO: "ERROR_TECNICO",
});
let _estadoSesionBackend = null;

function obtenerEstadoSesionBackend() {
    return _estadoSesionBackend;
}

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

// Redirige una sola vez aunque varias llamadas fallen al mismo tiempo.
function redirigirSesionUnaVez(destino) {
    if (_redireccionSesionEnCurso) return false;
    _redireccionSesionEnCurso = true;
    window.location.href = destino;
    return true;
}

// Sesion invalida (401, sin token, cuenta deshabilitada): limpia todo el
// estado del navegador, conserva solo el mensaje para el login y redirige.
function cerrarSesionPorInvalidez(mensaje = MENSAJE_SESION_REVOCADA) {
    if (_redireccionSesionEnCurso) return;
    localStorage.clear();
    sessionStorage.clear();
    sessionStorage.setItem("loginMensaje", mensaje);
    redirigirSesionUnaVez("login.html");
}

// Nombre anterior, usado por IA y Consumo de IA: mismo comportamiento.
function cerrarSesionPorBackend(mensaje = MENSAJE_SESION_REVOCADA) {
    cerrarSesionPorInvalidez(mensaje);
}

function irACambioClaveObligatorio() {
    try {
        localStorage.setItem("requiere_cambio_clave", "true");
    } catch (error) {
        // sin almacenamiento disponible: igual se redirige
    }
    redirigirSesionUnaVez("cambiar_clave.html");
}

// Codigo de error del backend ("" si la respuesta no lo trae).
function codigoErrorRespuesta(response) {
    try {
        return (response && response.headers && response.headers.get(HEADER_CODIGO_ERROR)) || "";
    } catch (error) {
        return "";
    }
}

// true solo para el 403 de cambio de clave obligatorio. Si la respuesta trae
// codigo, decide el codigo (un 403 ACCESO_DENEGADO nunca manda a cambiar la
// clave). Sin codigo (endpoints aun no migrados) se compara el detail exacto.
function esRespuestaCambioClave(status, data, codigo = "") {
    if (status !== 403) return false;
    if (codigo) return codigo === CODIGOS_ERROR_BACKEND.CAMBIO_CLAVE_OBLIGATORIO;
    return !!data && data.detail === MENSAJE_CAMBIO_CLAVE_BACKEND;
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
    const resultado = await _consultarSesionBackend();
    _estadoSesionBackend = resultado.estado;
    return resultado.estado === ESTADOS_SESION_BACKEND.VALIDA ? resultado.usuario : null;
}

async function _consultarSesionBackend() {
    const token = obtenerAccessToken();
    if (!token) {
        cerrarSesionPorInvalidez("Inicia sesión para continuar.");
        return { estado: ESTADOS_SESION_BACKEND.SIN_TOKEN };
    }

    let response;
    try {
        response = await fetch(`${SESION_API_BASE}/auth/me`, {
            cache: "no-store",
            headers: { "Authorization": `Bearer ${token}` }
        });
    } catch (error) {
        mostrarErrorSesionBackend("El servidor no respondió. Revisa tu conexión e intenta nuevamente.");
        return { estado: ESTADOS_SESION_BACKEND.ERROR_TECNICO };
    }

    let data = null;
    try {
        data = await response.json();
    } catch (error) {
        data = null;
    }

    if (response.status === 401) {
        cerrarSesionPorInvalidez(MENSAJE_SESION_REVOCADA);
        return { estado: ESTADOS_SESION_BACKEND.REVOCADA };
    }
    if (esRespuestaCambioClave(response.status, data, codigoErrorRespuesta(response))) {
        irACambioClaveObligatorio();
        return { estado: ESTADOS_SESION_BACKEND.CAMBIO_OBLIGATORIO };
    }
    if (!response.ok || !data || !data.dni) {
        mostrarErrorSesionBackend("Ocurrió un problema técnico al validar tu sesión. Intenta nuevamente en un momento.");
        return { estado: ESTADOS_SESION_BACKEND.ERROR_TECNICO };
    }

    // La identidad sale del backend; lo que hubiera en localStorage se reemplaza.
    // localStorage queda solo como estado de UI / compatibilidad.
    const idcarteras = Array.isArray(data.idcarteras) ? data.idcarteras.filter(Boolean) : [];
    localStorage.setItem("dni", data.dni);
    localStorage.setItem("agente", data.agente || data.dni);
    localStorage.setItem("tipo", data.tipo || "");
    localStorage.setItem("idcartera", data.idcartera || idcarteras[0] || "");
    localStorage.setItem("idcarteras", idcarteras.join(","));
    window.crmPermisosVistas = data.permisos_vistas || null;

    // El backend informa el cambio obligatorio; si no lo informa (version
    // anterior), se usa el indicador que guardo el login.
    const requiereCambio = typeof data.requiere_cambio_clave === "boolean"
        ? data.requiere_cambio_clave
        : localStorage.getItem("requiere_cambio_clave") === "true";
    localStorage.setItem("requiere_cambio_clave", requiereCambio ? "true" : "false");
    if (requiereCambio) {
        irACambioClaveObligatorio();
        return { estado: ESTADOS_SESION_BACKEND.CAMBIO_OBLIGATORIO };
    }

    return { estado: ESTADOS_SESION_BACKEND.VALIDA, usuario: data };
}

// Bootstrap unico por pagina: todas las cargas esperan la misma validacion.
function asegurarSesionBackend() {
    if (!_promesaSesionBackend) {
        _promesaSesionBackend = validarSesionBackend();
    }
    return _promesaSesionBackend;
}

// ---------------------------------------------------------------------------
// fetch autenticado para los modulos migrados (Cliente, Compromisos, Telefonos).
// Agrega Authorization: Bearer (sin pisar headers existentes ni el Content-Type
// de FormData).
//   401                          -> limpia la sesion y va a login.html
//   403 CAMBIO_CLAVE_OBLIGATORIO -> va a cambiar_clave.html
//   (en ambos lanza SesionInvalidaError para que la pagina no siga)
//   403 ACCESO_DENEGADO u otro   -> se devuelve la respuesta: la pagina se queda,
//                                   muestra el mensaje y la sesion no se toca.
// ---------------------------------------------------------------------------
class SesionInvalidaError extends Error {}

async function fetchConSesion(url, opciones = {}) {
    const response = await fetch(url, {
        cache: "no-store",
        ...opciones,
        headers: agregarAuthorizationHeader(opciones.headers),
    });

    if (response.status === 401) {
        cerrarSesionPorInvalidez(MENSAJE_SESION_REVOCADA);
        throw new SesionInvalidaError(MENSAJE_SESION_REVOCADA);
    }
    if (response.status === 403) {
        let data = null;
        try {
            data = await response.clone().json();
        } catch (error) {
            data = null;
        }
        if (esRespuestaCambioClave(403, data, codigoErrorRespuesta(response))) {
            irACambioClaveObligatorio();
            throw new SesionInvalidaError(MENSAJE_CAMBIO_CLAVE_BACKEND);
        }
    }
    return response;
}

// true si la respuesta es un 403 de permisos (perfil/cartera): la sesion sigue valida.
function esAccesoDenegado(response) {
    return !!response && response.status === 403
        && codigoErrorRespuesta(response) !== CODIGOS_ERROR_BACKEND.CAMBIO_CLAVE_OBLIGATORIO;
}

// Mensaje del backend (detail/msg) o uno por defecto, para mostrar al usuario.
async function mensajeErrorRespuesta(response, porDefecto) {
    try {
        const data = await response.clone().json();
        return data?.detail || data?.msg || porDefecto;
    } catch (error) {
        return porDefecto;
    }
}

// ---------------------------------------------------------------------------
// Descarga de archivos protegidos. window.open / location.href / <a href> no
// pueden enviar Authorization: se baja con fetchConSesion y se guarda el blob.
// El backend debe exponer Content-Disposition (Access-Control-Expose-Headers)
// para que se conserve el nombre; si no, se usa nombrePorDefecto.
// Lanza Error con el mensaje del backend si la respuesta no es correcta
// (SesionInvalidaError si la sesion no es valida: la pagina ya redirige).
// ---------------------------------------------------------------------------
async function descargarArchivoConSesion(url, nombrePorDefecto = "descarga") {
    const response = await fetchConSesion(url);
    if (!response.ok) {
        throw new Error(await mensajeErrorRespuesta(response, "No se pudo descargar el archivo."));
    }

    const disposicion = response.headers.get("Content-Disposition") || "";
    const codificado = disposicion.match(/filename\*=UTF-8''([^;]+)/i);
    const simple = disposicion.match(/filename="?([^";]+)"?/i);
    let nombre = nombrePorDefecto;
    try {
        if (codificado) nombre = decodeURIComponent(codificado[1].trim());
        else if (simple) nombre = simple[1].trim();
    } catch (error) {
        nombre = nombrePorDefecto;
    }

    const urlBlob = URL.createObjectURL(await response.blob());
    const enlace = document.createElement("a");
    enlace.href = urlBlob;
    enlace.download = nombre;
    document.body.appendChild(enlace);
    enlace.click();
    enlace.remove();
    setTimeout(() => URL.revokeObjectURL(urlBlob), 1000);
    return nombre;
}
