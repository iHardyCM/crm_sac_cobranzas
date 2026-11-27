"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const codigo = fs.readFileSync(path.resolve(__dirname, "../../frontend/js/app_layout.js"), "utf8");

function entorno(pagina) {
    const elementos = new Map();
    const guardado = new Map([["dni", "12345678"]]);
    let respuesta = [{ id: "zona:1", tipo: "zona_restringida", nivel: "rojo",
        titulo: "Gestión detenida: Piura", detalle: "Banco & lluvia", enlace: "zonas.html" }];
    let fallar = false;
    let consultas = 0;
    let intervalo = null;
    let intervaloMs = null;
    const elemento = id => {
        if (!elementos.has(id)) elementos.set(id, {
            hidden: id === "crmAlertas" || id === "crmAlertasPanel",
            textContent: "", innerHTML: "", dataset: {}, atributos: {}, eventos: {},
            setAttribute(nombre, valor) { this.atributos[nombre] = valor; },
            addEventListener(nombre, fn) { this.eventos[nombre] = fn; },
        });
        return elementos.get(id);
    };
    const contexto = {
        console, Date, JSON,
        location: { pathname: `/views/${pagina}` },
        document: {
            body: {
                insertAdjacentHTML(_posicion, html) {
                    for (const match of html.matchAll(/id="([^"]+)"/g)) elemento(match[1]);
                },
            },
            documentElement: { classList: { remove() {} } },
            getElementById: id => elementos.get(id) || null,
            addEventListener() {},
        },
        localStorage: {
            getItem: clave => guardado.get(clave) ?? null,
            setItem: (clave, valor) => guardado.set(clave, String(valor)),
        },
        asegurarSesionBackend: async () => true,
        fetchConSesion: async () => {
            consultas++;
            if (fallar) throw new Error("Servicio no disponible");
            return { ok: true, json: async () => respuesta };
        },
        SESION_API_BASE: "http://localhost:8000",
        setInterval: (fn, ms) => { intervalo = fn; intervaloMs = ms; },
    };
    contexto.window = contexto;
    vm.runInNewContext(codigo, contexto, { filename: "app_layout.js" });
    return {
        elemento, guardado,
        get consultas() { return consultas; },
        get intervalo() { return intervalo; },
        get intervaloMs() { return intervaloMs; },
        cambiarRespuesta: valor => { respuesta = valor; },
        fallar: () => { fallar = true; },
    };
}

const esperar = () => new Promise(resolve => setImmediate(resolve));

async function probar() {
    const e = entorno("home.html");
    await esperar();
    await esperar();
    assert.equal(e.consultas, 1);
    assert.equal(e.intervaloMs, 300000);
    assert.equal(e.elemento("crmAlertas").hidden, false);
    assert.equal(e.elemento("crmAlertasCuenta").textContent, "1");
    assert.match(e.elemento("crmAlertasLista").innerHTML, /Banco &amp; lluvia/);

    e.elemento("crmAlertasBoton").eventos.click();
    assert.equal(e.elemento("crmAlertasPanel").hidden, false);
    e.elemento("crmAlertasLista").eventos.click({ target: {
        closest: () => ({ dataset: { alertaId: "zona:1" } }),
    } });
    assert.equal(e.elemento("crmAlertasCuenta").textContent, "0");
    assert.equal(JSON.parse(e.guardado.get("crmAlertaVista:12345678:zona:1")).fecha, new Date().toDateString());

    await e.intervalo();
    assert.equal(e.elemento("crmAlertasCuenta").textContent, "0");
    e.cambiarRespuesta([{ id: "zona:1", tipo: "zona_restringida", nivel: "rojo",
        titulo: "Gestión detenida: Piura", detalle: "Banco cambió el motivo", enlace: "zonas.html" }]);
    await e.intervalo();
    assert.equal(e.elemento("crmAlertasCuenta").textContent, "1");

    e.fallar();
    await e.intervalo();
    assert.equal(e.elemento("crmAlertas").hidden, true);

    const login = entorno("login.html");
    await esperar();
    assert.equal(login.consultas, 0);
    assert.equal(login.intervalo, null);
    const cambio = entorno("cambiar_clave.html");
    await esperar();
    assert.equal(cambio.consultas, 0);
    assert.equal(cambio.intervalo, null);
    const anterior = entorno("score_telefonico_v0.html");
    await esperar();
    await esperar();
    assert.equal(anterior.consultas, 1);
}

probar().then(() => console.log("OK"), error => { console.error(error); process.exitCode = 1; });
