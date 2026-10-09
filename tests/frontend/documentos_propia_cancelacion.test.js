"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const raiz = path.resolve(__dirname, "..", "..");
const source = fs.readFileSync(path.join(raiz, "frontend", "js", "documentos.js"), "utf8");
let tipo = "propia_sip_cancelacion";
const elementos = {
    cancelacion: {value: "350.00"},
    fechaPagoMibanco: {value: "2026-10-06"},
    excepcionDocumento: {checked: false},
};
let checks = [];
const context = vm.createContext({
    window: {location: {protocol: "http:", hostname: "localhost"}},
    document: {
        addEventListener() {},
        getElementById(id) { return id === "documentoTipo" ? {value: tipo} : elementos[id] || null; },
        querySelectorAll(selector) { return selector === ".credito-propia-check:checked" ? checks : []; },
    },
});
vm.runInContext(source, context);

function distribuir(creditos, monto) {
    context.creditosPrueba = creditos;
    return vm.runInContext(`distribuirCancelacionPropia(creditosPrueba, ${monto})`, context);
}

const sip = [
    {DeudaTotal: 200, MontoReferenciaPropia: 80},
    {DeudaTotal: 300, MontoReferenciaPropia: 100},
];
const sipMontos = distribuir(sip, 35000);
assert.equal(sipMontos.reduce((total, monto) => total + monto, 0), 35000);
assert.ok(sipMontos[0] >= 8000 && sipMontos[1] >= 10000);
assert.ok(sipMontos[0] <= 20000 && sipMontos[1] <= 30000);
assert.deepEqual(Array.from(distribuir(sip, 50000)), [20000, 30000]);
assert.equal(distribuir(sip, 50001), null);
assert.equal(distribuir(sip, 1), null);

const sipExcepcion = distribuir(sip, 12000);
assert.equal(sipExcepcion.reduce((total, monto) => total + monto, 0), 12000);
assert.ok(sipExcepcion.every(monto => monto > 0));
assert.ok(sipExcepcion.some((monto, index) => monto < [8000, 10000][index]));

context.creditosPrueba = sip.map((item, index) => ({...item, Operacion: String(index + 1)}));
checks = [{dataset: {index: "0"}}, {dataset: {index: "1"}}];
vm.runInContext("documentosResultados = creditosPrueba; documentoSeleccionado = creditosPrueba[0]", context);
const acuerdo = vm.runInContext("datosAcuerdoPropia()", context);
assert.equal(acuerdo.error, null);
assert.equal(acuerdo.creditos.length, 2);
assert.equal(acuerdo.creditos.reduce((total, item) => total + Math.round(item.monto * 100), 0), 35000);
assert.ok(acuerdo.creditos.every(item => item.fecha === "2026-10-06"));

elementos.cancelacion.value = "120.00";
assert.match(vm.runInContext("datosAcuerdoPropia().error", context), /Excepción/);
elementos.excepcionDocumento.checked = true;
assert.equal(vm.runInContext("datosAcuerdoPropia().error", context), null);
elementos.cancelacion.value = "120.001";
assert.match(vm.runInContext("datosAcuerdoPropia().error", context), /dos decimales/);
elementos.cancelacion.value = "350.00";
elementos.excepcionDocumento.checked = false;

tipo = "propia_interbank_cancelacion";
const interbank = [
    {DeudaTotal: 100, MtoCancelacionCliente: 50},
    {DeudaTotal: 250, MtoCancelacionCliente: 100},
];
const interbankMontos = distribuir(interbank, 33333);
assert.equal(interbankMontos.reduce((total, monto) => total + monto, 0), 33333);
assert.ok(interbankMontos[0] <= 10000 && interbankMontos[1] <= 25000);
assert.deepEqual(Array.from(distribuir(interbank, 35000)), [10000, 25000]);

const html = fs.readFileSync(path.join(raiz, "frontend", "views", "documentos.html"), "utf8");
assert.ok(!html.includes('id="propiaCreditosBox"'));
assert.ok(html.includes('id="cancelacion"') && html.includes('id="fechaPagoMibanco"'));

console.log("Cancelación total de Propia: distribución y formulario correctos.");
