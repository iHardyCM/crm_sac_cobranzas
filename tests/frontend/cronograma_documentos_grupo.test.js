"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const raiz = path.resolve(__dirname, "..", "..");
const leer = archivo => fs.readFileSync(path.join(raiz, "frontend", "js", archivo), "utf8");
const sesion = {dni: "71335556", tipo: "SUPERVISOR"};
const almacen = new Map();
const localStorage = {
    getItem: clave => sesion[clave] || almacen.get(clave) || null,
    setItem: (clave, valor) => almacen.set(clave, valor),
    removeItem: clave => almacen.delete(clave),
};
let pestañaAbierta = null;
const ventanaRadar = {
    addEventListener() {}, location: {href: "compartamos.html"},
    crypto: {getRandomValues(bytes) { bytes.fill(7); return bytes; }},
    open(url, destino, opciones) { pestañaAbierta = {url, destino, opciones}; },
};

const radar = vm.createContext({
    window: ventanaRadar,
    document: {}, localStorage, sessionStorage: {setItem() {}},
    esSupervisor: tipo => tipo === "SUPERVISOR",
    Intl, Date,
});
vm.runInContext(leer("compartamos.js"), radar);

const datos = {grupo: {codigo_grupo: "341738", credito_grupal: "21201544"}};
const cronograma = {
    plan: {disponible: true, cuotas: [8, 9]},
    totales: {8: 400, 9: 200},
    integrantes: [
        {dni: "06902885", operacion: "00021201555", cuotas: {8: 100}},
        {dni: "06873820", operacion: "21201546", cuotas: {9: 200}},
        {dni: "77565158", operacion: "21201551", cuotas: {8: 300, 10: 500}},
        {dni: "77909811", operacion: "21201547", cuotas: {10: 250}},
    ],
};
radar.datosPrueba = datos;
radar.cronogramaPrueba = cronograma;
const preparar = monto => vm.runInContext(`prepararDocumentoCuotasCRM(datosPrueba, cronogramaPrueba, ${monto})`, radar);
const propuesta = preparar(299.99);
assert.equal(propuesta.pagos.length, 3);
assert.equal(propuesta.cuotas.join(","), "8,9");
assert.equal(propuesta.pagos.reduce((suma, pago) => suma + Math.round(Number(pago.monto) * 100), 0), 29999);
assert.equal(propuesta.pagos.some(pago => pago.operacion === "21201547"), false);
assert.equal(preparar(0), null);
assert.equal(preparar(1.001), null);
cronograma.plan.cuotas = [8];
assert.equal(preparar(100).pagos.length, 2);
cronograma.plan.cuotas = [8, 9];
assert.equal(vm.runInContext("puedePrepararDocumentoGrupoCRM()", radar), true);
sesion.tipo = "GESTOR";
assert.equal(vm.runInContext("puedePrepararDocumentoGrupoCRM()", radar), false);
sesion.tipo = "SUPERVISOR";
ventanaRadar._consultaCompartamosCRM = {...datos, cronograma_cuotas: cronograma};
ventanaRadar._cronogramaEstado = {propuestas: {cuota: 299.99}};
vm.runInContext("abrirDocumentosGrupoCRM()", radar);
assert.equal(pestañaAbierta.destino, "_blank");
assert.equal(pestañaAbierta.opciones, "noopener");
assert.equal(ventanaRadar.location.href, "compartamos.html");
assert.match(pestañaAbierta.url, /^documentos\.html#radar_cuotas=[a-f0-9]{32}$/);
const claveTransferencia = `crm_documento_cuotas_grupo:${pestañaAbierta.url.split("=")[1]}`;
assert.equal(JSON.parse(almacen.get(claveTransferencia)).propuesta, "299.99");

const checks = [];
const montos = [];
const encargado = {value: ""};
const rutaDocumentos = {protocol: "http:", hostname: "localhost", pathname: "/frontend/views/documentos.html", search: "", hash: `#radar_cuotas=${pestañaAbierta.url.split("=")[1]}`};
const documentos = vm.createContext({
    window: {location: rutaDocumentos}, localStorage,
    history: {replaceState(_, __, ruta) { assert.equal(ruta, rutaDocumentos.pathname); rutaDocumentos.hash = ""; }},
    document: {
        addEventListener() {},
        querySelectorAll(selector) {
            if (selector === ".integrante-activo-input") return checks;
            if (selector === ".monto-grupal-input") return montos;
            return [];
        },
        getElementById(id) { return id === "encargadoParticipante" ? encargado : null; },
    },
});
vm.runInContext(leer("documentos.js"), documentos);
assert.equal(vm.runInContext("extraerPreparacionCuotasGrupo()?.propuesta", documentos), "299.99");
assert.equal(almacen.has(claveTransferencia), false);
assert.equal(rutaDocumentos.hash, "");
assert.equal(vm.runInContext("extraerPreparacionCuotasGrupo()", documentos), null);
const resultados = [
    {CodigoGrupo: "341738", CodCreGrupal: "21201544", NumDocumento: "06902885", Operacion: "21201555"},
    {CodigoGrupo: "341738", CodCreGrupal: "21201544", NumDocumento: "06873820", Operacion: "21201546"},
    {CodigoGrupo: "341738", CodCreGrupal: "21201544", NumDocumento: "77565158", Operacion: "21201551"},
    {CodigoGrupo: "341738", CodCreGrupal: "21201544", NumDocumento: "77909811", Operacion: "21201547"},
];
documentos.preparacionPrueba = JSON.parse(JSON.stringify(propuesta));
documentos.resultadosPrueba = resultados;
assert.equal(vm.runInContext("validarPreparacionCuotasGrupo(preparacionPrueba, resultadosPrueba)", documentos), "");
documentos.resultadosPrueba = resultados.slice(0, 2);
assert.match(vm.runInContext("validarPreparacionCuotasGrupo(preparacionPrueba, resultadosPrueba)", documentos), /No se pudieron verificar/);
documentos.resultadosPrueba = resultados.map(item => ({...item, CodigoGrupo: "otro"}));
assert.match(vm.runInContext("validarPreparacionCuotasGrupo(preparacionPrueba, resultadosPrueba)", documentos), /no coincide/);

resultados.forEach(item => {
    checks.push({dataset: {operacion: item.Operacion}, checked: true});
    montos.push({dataset: {operacion: item.Operacion}, value: ""});
});
documentos.resultadosPrueba = resultados;
vm.runInContext("documentosResultados = resultadosPrueba; actualizarCondonacion = () => {}; pintarPreviewDocumento = () => {}; aplicarPreparacionCuotasGrupo(preparacionPrueba)", documentos);
assert.deepEqual(checks.map(item => item.checked), [true, true, true, false]);
assert.equal(montos[3].value, "");
assert.equal(montos.slice(0, 3).reduce((suma, item) => suma + Math.round(Number(item.value) * 100), 0), 29999);
assert.equal(encargado.value, "21201555");

console.log("Cronograma a compromiso grupal: OK");
