// Tests de la validacion de sesion del frontend (session.js + fetchIa).
// Se ejecutan con Node (sin navegador): node tests/frontend/sesion_frontend.test.js
// Imprime un JSON con los resultados; tests/test_sesion_frontend.py lo invoca.
"use strict";

const fs = require("fs");
const path = require("path");
const vm = require("vm");

const RAIZ = path.resolve(__dirname, "..", "..");
const leer = rel => fs.readFileSync(path.join(RAIZ, rel), "utf8");

function crearStorage(inicial = {}) {
    const datos = { ...inicial };
    return {
        getItem: k => (k in datos ? datos[k] : null),
        setItem: (k, v) => { datos[k] = String(v); },
        removeItem: k => { delete datos[k]; },
        clear: () => { for (const k of Object.keys(datos)) delete datos[k]; },
        _datos: datos,
    };
}

function respuesta(status, body) {
    const texto = body === undefined ? "" : JSON.stringify(body);
    return {
        status,
        ok: status >= 200 && status < 300,
        json: async () => JSON.parse(texto),
        clone() { return respuesta(status, body); },
        blob: async () => ({}),
    };
}

// Crea un "navegador" minimo. rutas: { "/auth/me": respuesta(...) , ... }
function crearEntorno({ storage = {}, rutas = {}, pagina = "http://localhost:5500/views/ia_feedback.html",
                       conElementos = false, clasesIniciales = [] } = {}) {
    const llamadas = [];
    const listeners = {};
    let hrefActual = pagina;
    const redirecciones = [];
    const location = {
        protocol: "http:",
        hostname: "localhost",
        get href() { return hrefActual; },
        set href(valor) { redirecciones.push(valor); hrefActual = valor; },
        reload() {},
    };
    const elementos = [];
    const porId = {};
    const clasesBody = new Set(clasesIniciales);
    const documentStub = {
        body: {
            appendChild: el => elementos.push(el),
            contains: () => true,
            classList: {
                add: c => clasesBody.add(c),
                remove: c => clasesBody.delete(c),
                contains: c => clasesBody.has(c),
            },
        },
        addEventListener: (tipo, fn) => { (listeners[tipo] = listeners[tipo] || []).push(fn); },
        // Los elementos de Home se crean al pedirlos; el aviso tecnico de session.js se crea con createElement.
        getElementById: id => (conElementos && id !== "crmSesionErrorBackend"
            ? (porId[id] = porId[id] || { id, innerText: "", innerHTML: "", textContent: "" })
            : null),
        querySelector: () => null,
        querySelectorAll: () => [],
        createElement: () => ({
            style: {},
            setAttribute() {},
            set innerHTML(v) { this._html = v; },
            get innerHTML() { return this._html; },
            querySelector: () => ({ textContent: "" }),
        }),
    };
    const contexto = {
        // console silencioso: ia_feedback.js imprime su version al cargarse.
        console: { log() {}, info() {}, warn() {}, debug() {}, error() {} },
        URLSearchParams, Headers, AbortController, FormData, Blob, URL,
        setTimeout, clearTimeout, setInterval: () => 0, clearInterval: () => {},
        localStorage: crearStorage(storage),
        sessionStorage: crearStorage(),
        document: documentStub,
        fetch: async (url, opciones = {}) => {
            const headers = new Headers(opciones.headers || {});
            llamadas.push({ url: String(url), authorization: headers.get("Authorization"), headers, opciones });
            const ruta = Object.keys(rutas).find(r => String(url).includes(r));
            if (!ruta) return respuesta(200, {});
            const r = rutas[ruta];
            return typeof r === "function" ? r() : r;
        },
    };
    contexto.window = contexto;
    contexto.window.location = location;
    contexto.addEventListener = (tipo, fn) => { (listeners["window:" + tipo] = listeners["window:" + tipo] || []).push(fn); };
    vm.createContext(contexto);
    return { contexto, llamadas, listeners, location, elementos, porId, clasesBody, redirecciones };
}

function cargar(entorno, ...archivos) {
    for (const archivo of archivos) {
        vm.runInContext(leer(archivo), entorno.contexto, { filename: archivo });
    }
}

const USUARIO_ME = { dni: "22222222", agente: "22222222 - GINO GESTOR", tipo: "GESTOR", idcartera: 112, idcarteras: [112, 144] };

const casos = {
    async sin_token_no_continua() {
        const e = crearEntorno({ storage: { dni: "22222222", agente: "x" } });
        cargar(e, "frontend/js/session.js");
        const r = await e.contexto.validarSesionBackend();
        return r === null
            && e.llamadas.length === 0
            && e.location.href === "login.html"
            && e.contexto.localStorage.getItem("dni") === null;
    },

    async me_401_limpia_sesion_y_va_al_login() {
        const e = crearEntorno({
            storage: { access_token: "tok", dni: "22222222", agente: "x", tipo: "ADMINISTRADOR" },
            rutas: { "/auth/me": respuesta(401, { detail: "Sesion no valida" }) },
        });
        cargar(e, "frontend/js/session.js");
        const r = await e.contexto.validarSesionBackend();
        return r === null
            && e.llamadas[0].authorization === "Bearer tok"
            && e.contexto.localStorage.getItem("access_token") === null
            && e.contexto.localStorage.getItem("tipo") === null
            && e.contexto.sessionStorage.getItem("loginMensaje") === "Tu sesión ya no está habilitada. Inicia sesión nuevamente."
            && e.location.href === "login.html";
    },

    async me_200_actualiza_identidad_desde_backend() {
        const e = crearEntorno({
            storage: { access_token: "tok", dni: "22222222", agente: "viejo", tipo: "ADMINISTRADOR" },
            rutas: { "/auth/me": respuesta(200, USUARIO_ME) },
        });
        cargar(e, "frontend/js/session.js");
        const r = await e.contexto.validarSesionBackend();
        const ls = e.contexto.localStorage;
        return r && r.dni === "22222222"
            && ls.getItem("tipo") === "GESTOR"                 // el perfil viejo del navegador se reemplaza
            && ls.getItem("agente") === "22222222 - GINO GESTOR"
            && ls.getItem("idcarteras") === "112,144"
            && e.location.href.endsWith("ia_feedback.html");
    },

    async me_5xx_no_autoriza_ni_borra_credenciales() {
        const e = crearEntorno({
            storage: { access_token: "tok", dni: "22222222", agente: "x" },
            rutas: { "/auth/me": respuesta(503, { detail: "No se pudo validar" }) },
        });
        cargar(e, "frontend/js/session.js");
        const r = await e.contexto.validarSesionBackend();
        return r === null
            && e.contexto.localStorage.getItem("access_token") === "tok"
            && e.location.href.endsWith("ia_feedback.html")
            && e.elementos.length === 1;                       // aviso tecnico bloqueante
    },

    async me_403_cambio_obligatorio_va_a_cambiar_clave() {
        const e = crearEntorno({
            storage: { access_token: "tok" },
            rutas: { "/auth/me": respuesta(403, { detail: "Debes cambiar tu contraseña antes de continuar." }) },
        });
        cargar(e, "frontend/js/session.js");
        const r = await e.contexto.validarSesionBackend();
        return r === null && e.location.href === "cambiar_clave.html";
    },

    async pagina_ia_no_carga_datos_si_me_falla() {
        const e = crearEntorno({
            storage: { access_token: "tok", dni: "22222222", agente: "x", tipo: "ADMINISTRADOR" },
            rutas: { "/auth/me": respuesta(401, { detail: "Sesion no valida" }) },
        });
        cargar(e, "frontend/js/session.js", "frontend/js/ia_feedback.js");
        for (const fn of e.listeners.DOMContentLoaded || []) await fn();
        const llamadasIa = e.llamadas.filter(l => !l.url.includes("/auth/me"));
        return (e.listeners.DOMContentLoaded || []).length === 1
            && e.llamadas.length === 1
            && llamadasIa.length === 0
            && e.location.href === "login.html";
    },

    async fetch_ia_agrega_bearer_y_respeta_headers_y_formdata() {
        const e = crearEntorno({ storage: { access_token: "tok" } });
        cargar(e, "frontend/js/session.js", "frontend/js/ia_feedback.js");
        const form = new FormData();
        form.append("agente", "X");
        await e.contexto.fetchIa("http://localhost:8000/ia-feedback/upload", { method: "POST", body: form });
        await e.contexto.fetchIa("http://localhost:8000/calibracion/criterio", {
            method: "POST", headers: { "Content-Type": "application/json" }, body: "{}",
        });
        const [a, b] = e.llamadas;
        return a.authorization === "Bearer tok"
            && a.opciones.body === form
            && !a.headers.has("Content-Type")                   // FormData conserva su boundary
            && b.authorization === "Bearer tok"
            && b.headers.get("Content-Type") === "application/json";
    },

    async fetch_ia_401_cierra_sesion() {
        const e = crearEntorno({
            storage: { access_token: "tok", dni: "22222222" },
            rutas: { "/ia-feedback/bandeja": respuesta(401, { detail: "x" }) },
        });
        cargar(e, "frontend/js/session.js", "frontend/js/ia_feedback.js");
        let lanzo = false;
        try {
            await e.contexto.fetchIa("http://localhost:8000/ia-feedback/bandeja");
        } catch (error) {
            lanzo = true;
        }
        return lanzo
            && e.location.href === "login.html"
            && e.contexto.localStorage.getItem("access_token") === null;
    },

    async fetch_ia_403_cambio_obligatorio_redirige() {
        const e = crearEntorno({
            storage: { access_token: "tok" },
            rutas: { "/ia-feedback/config": respuesta(403, { detail: "Debes cambiar tu contraseña antes de continuar." }) },
        });
        cargar(e, "frontend/js/session.js", "frontend/js/ia_feedback.js");
        let lanzo = false;
        try {
            await e.contexto.fetchIa("http://localhost:8000/ia-feedback/config");
        } catch (error) {
            lanzo = true;
        }
        return lanzo && e.location.href === "cambiar_clave.html"
            && e.contexto.localStorage.getItem("access_token") === "tok";
    },

    async fetch_ia_otro_403_no_redirige() {
        const e = crearEntorno({
            storage: { access_token: "tok" },
            rutas: { "/ia-feedback/consumo": respuesta(403, { detail: "Perfil sin acceso al consumo de la API." }) },
        });
        cargar(e, "frontend/js/session.js", "frontend/js/ia_feedback.js");
        const r = await e.contexto.fetchIa("http://localhost:8000/ia-feedback/consumo");
        return r.status === 403 && e.location.href.endsWith("ia_feedback.html");
    },
};

// ---------------------------------------------------------------- Home
const HOME = "http://localhost:5500/views/home.html";

function entornoHome(opciones) {
    const e = crearEntorno({ pagina: HOME, conElementos: true, clasesIniciales: ["home-validando-sesion"], ...opciones });
    cargar(e, "frontend/js/session.js", "frontend/js/home.js");
    return e;
}

async function iniciarPagina(e) {
    for (const fn of e.listeners.DOMContentLoaded || []) await fn();
}

function homeSinPintar(e) {
    return e.porId.homeTitulo === undefined
        && e.porId.modulosHome === undefined
        && e.clasesBody.has("home-validando-sesion");
}

const STORAGE_VIEJO = {
    access_token: "tok", dni: "22222222", agente: "22222222 - NOMBRE VIEJO",
    tipo: "SUPERVISOR", idcartera: "117", idcarteras: "117,133",
};

Object.assign(casos, {
    async home_200_continua() {
        const e = entornoHome({
            storage: STORAGE_VIEJO,
            rutas: { "/auth/me": respuesta(200, { ...USUARIO_ME, requiere_cambio_clave: false }) },
        });
        await iniciarPagina(e);
        return e.porId.homeTitulo.innerText === "Hola, GINO GESTOR"
            && e.porId.homeUsuario.innerText === "22222222 - GINO GESTOR"
            && e.porId.modulosHome.innerHTML.includes("Mis compromisos")
            && !e.clasesBody.has("home-validando-sesion")
            && e.redirecciones.length === 0;
    },

    async home_identidad_backend_reemplaza_localstorage() {
        // SISCOB paso al usuario de SUPERVISOR a GESTOR; el JWT sigue vigente.
        const e = entornoHome({
            storage: STORAGE_VIEJO,
            rutas: { "/auth/me": respuesta(200, { ...USUARIO_ME, requiere_cambio_clave: false }) },
        });
        await iniciarPagina(e);
        const ls = e.contexto.localStorage;
        return e.porId.homePerfil.innerText === "GESTOR"
            && e.porId.homeCarteras.innerText === "112, 144"
            && !e.porId.modulosHome.innerHTML.includes("Compromisos supervisor")
            && ls.getItem("tipo") === "GESTOR"
            && ls.getItem("agente") === "22222222 - GINO GESTOR"
            && ls.getItem("idcarteras") === "112,144";
    },

    async home_401_limpia_sesion() {
        const e = entornoHome({ storage: STORAGE_VIEJO, rutas: { "/auth/me": respuesta(401, { detail: "x" }) } });
        await iniciarPagina(e);
        const ls = e.contexto.localStorage;
        return Object.keys(ls._datos).length === 0
            && Object.keys(e.contexto.sessionStorage._datos).join() === "loginMensaje"
            && e.contexto.sessionStorage.getItem("loginMensaje") === "Tu sesión ya no está habilitada. Inicia sesión nuevamente.";
    },

    async home_401_redirige_login() {
        const e = entornoHome({ storage: STORAGE_VIEJO, rutas: { "/auth/me": respuesta(401, { detail: "x" }) } });
        await iniciarPagina(e);
        return e.redirecciones.length === 1 && e.redirecciones[0] === "login.html";
    },

    async home_401_no_continua() {
        const e = entornoHome({ storage: STORAGE_VIEJO, rutas: { "/auth/me": respuesta(401, { detail: "x" }) } });
        await iniciarPagina(e);
        return homeSinPintar(e) && e.llamadas.length === 1;
    },

    async home_cambio_obligatorio_va_a_cambiar_clave() {
        const e = entornoHome({
            storage: { ...STORAGE_VIEJO, requiere_cambio_clave: "false" },
            rutas: { "/auth/me": respuesta(200, { ...USUARIO_ME, requiere_cambio_clave: true }) },
        });
        await iniciarPagina(e);
        return e.redirecciones.join() === "cambiar_clave.html"
            && homeSinPintar(e)
            && e.contexto.localStorage.getItem("requiere_cambio_clave") === "true"
            && e.contexto.localStorage.getItem("access_token") === "tok";
    },

    async home_5xx_no_usa_sesion_vieja() {
        const e = entornoHome({ storage: STORAGE_VIEJO, rutas: { "/auth/me": respuesta(503, { detail: "x" }) } });
        await iniciarPagina(e);
        return homeSinPintar(e)                                   // no pinta datos viejos
            && e.redirecciones.length === 0
            && e.elementos.length === 1                           // aviso tecnico bloqueante
            && e.contexto.localStorage.getItem("access_token") === "tok"
            && e.contexto.obtenerEstadoSesionBackend() === "ERROR_TECNICO";
    },

    async home_sin_token_va_al_login() {
        const e = entornoHome({ storage: { dni: "22222222", agente: "x", tipo: "SUPERVISOR" } });
        await iniciarPagina(e);
        return e.llamadas.length === 0
            && e.redirecciones.join() === "login.html"
            && homeSinPintar(e)
            && e.contexto.localStorage.getItem("tipo") === null;
    },

    async redireccion_ocurre_una_sola_vez() {
        const e = crearEntorno({
            storage: { access_token: "tok" },
            rutas: { "/ia-feedback/": respuesta(401, { detail: "x" }), "/auth/me": respuesta(401, { detail: "x" }) },
        });
        cargar(e, "frontend/js/session.js", "frontend/js/ia_feedback.js");
        // Varias llamadas fallan a la vez (bandeja, reporteria, config) + /auth/me.
        await Promise.allSettled([
            e.contexto.fetchIa("http://localhost:8000/ia-feedback/bandeja"),
            e.contexto.fetchIa("http://localhost:8000/ia-feedback/reporteria"),
            e.contexto.fetchIa("http://localhost:8000/ia-feedback/config"),
            e.contexto.validarSesionBackend(),
        ]);
        e.contexto.cerrarSesionPorInvalidez("otro mensaje");
        return e.redirecciones.length === 1
            && e.redirecciones[0] === "login.html"
            && e.contexto.sessionStorage.getItem("loginMensaje") === "Tu sesión ya no está habilitada. Inicia sesión nuevamente.";
    },

    async home_recarga_desde_cache_revalida() {
        const e = entornoHome({ storage: STORAGE_VIEJO });
        let recargo = false;
        e.location.reload = () => { recargo = true; };
        for (const fn of e.listeners["window:pageshow"] || []) fn({ persisted: true });
        return recargo;
    },
});

(async () => {
    const resultados = {};
    for (const [nombre, caso] of Object.entries(casos)) {
        try {
            resultados[nombre] = (await caso()) === true ? "OK" : "FALLO";
        } catch (error) {
            resultados[nombre] = `ERROR: ${error && error.stack || error}`;
        }
    }
    console.log(JSON.stringify(resultados));
})();
