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
function crearEntorno({ storage = {}, rutas = {} } = {}) {
    const llamadas = [];
    const listeners = {};
    const location = { protocol: "http:", hostname: "localhost", href: "http://localhost:5500/views/ia_feedback.html" };
    const elementos = [];
    const documentStub = {
        body: {
            appendChild: el => elementos.push(el),
            contains: () => true,
        },
        addEventListener: (tipo, fn) => { (listeners[tipo] = listeners[tipo] || []).push(fn); },
        getElementById: () => null,
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
    vm.createContext(contexto);
    return { contexto, llamadas, listeners, location, elementos };
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
