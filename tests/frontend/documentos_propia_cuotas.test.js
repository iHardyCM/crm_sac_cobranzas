"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const raiz = path.resolve(__dirname, "..", "..");
const codigo = fs.readFileSync(path.join(raiz, "frontend", "js", "documentos.js"), "utf8");
const elementos = {
    documentoTipo: {value: "propia_interbank_cuotas"},
    cancelacion: {value: ""},
    montoMinimo: {textContent: ""},
    deudaTotal: {textContent: ""},
    condonacionEstimada: {textContent: ""},
    operacionSeleccionada: {textContent: ""},
    fechaPagoMibanco: {value: "2026-10-15"},
    propiaCantidadCuotas: {value: "1"},
    propiaPrimerPago: {value: "0.00"},
    propiaFechaInicial: {value: "2026-10-15"},
    propiaMontoCuota: {value: ""},
    propiaCronograma: {innerHTML: "", querySelectorAll() { return []; }},
    excepcionDocumento: {checked: false},
};
let checks = [{dataset: {index: "0"}}, {dataset: {index: "1"}}];
let todosControles = [];
let cuota = "16.00";
const pagos = [
    {querySelector(selector) { return selector === ".monto-propia" ? {dataset: {monto: "0.00"}} : {value: "2026-10-15"}; }},
    {querySelector(selector) { return selector === ".monto-propia" ? {dataset: {monto: cuota}} : {value: "2026-11-15"}; }},
];
const contexto = vm.createContext({
    window: {location: {protocol: "http:", hostname: "localhost"}},
    document: {
        addEventListener() {},
        getElementById(id) { return elementos[id] || null; },
        querySelectorAll(selector) {
            if (selector === ".credito-propia-check:checked") return checks.filter(item => item.checked !== false);
            if (selector === ".credito-propia-check") return todosControles;
            if (selector === "#propiaCronograma tbody tr") return pagos;
            return [];
        },
    },
});
vm.runInContext(codigo, contexto);
contexto.registrosPrueba = [
    {NumDocumento: "10771235", Operacion: "0047255221", DeudaTotal: 30, MtoCancelacionCliente: 10.25},
    {NumDocumento: "10771235", Operacion: "0047255222", DeudaTotal: 20, MtoCancelacionCliente: 5.75},
];
vm.runInContext("documentosResultados = registrosPrueba; documentoSeleccionado = registrosPrueba[0]", contexto);

vm.runInContext("actualizarResumenCreditosPropia()", contexto);
vm.runInContext("sincronizarCronogramaPropia(false)", contexto);
assert.equal(elementos.montoMinimo.textContent, "S/ 16.00");
assert.equal(elementos.deudaTotal.textContent, "S/ 50.00");
assert.equal(elementos.cancelacion.value, "16.00");
assert.equal(elementos.propiaMontoCuota.value, "16.00");
assert.equal(vm.runInContext("datosAcuerdoPropia().error", contexto), null);
let payload = vm.runInContext('construirPayloadGeneracion("pdf", true)', contexto);
assert.deepEqual(Array.from(payload.creditos_propia, item => item.operacion), ["0047255221", "0047255222"]);
assert.ok(payload.creditos_propia.every(item => Object.keys(item).length === 1));
assert.equal(payload.cancelacion, 16);
assert.equal(payload.pagos_mibanco.reduce((sum, pago) => sum + pago.monto, 0), 16);

checks = [{dataset: {index: "1"}}];
cuota = "5.75";
vm.runInContext("actualizarResumenCreditosPropia()", contexto);
vm.runInContext("sincronizarCronogramaPropia(false)", contexto);
assert.equal(elementos.montoMinimo.textContent, "S/ 5.75");
assert.equal(elementos.deudaTotal.textContent, "S/ 20.00");
assert.equal(elementos.cancelacion.value, "5.75");
assert.equal(elementos.propiaMontoCuota.value, "5.75");
payload = vm.runInContext('construirPayloadGeneracion("pdf", true)', contexto);
assert.deepEqual(Array.from(payload.creditos_propia, item => item.operacion), ["0047255222"]);
assert.equal(payload.cancelacion, 5.75);

elementos.documentoTipo.value = "propia_sip_cuotas";
contexto.registrosPrueba = [
    {NumDocumento: "10771235", Operacion: "4040710002707212", DeudaTotal: 200, MontoReferenciaPropia: 80},
    {NumDocumento: "10771235", Operacion: "4040710009986512", DeudaTotal: 300, MontoReferenciaPropia: 100},
];
checks = [{dataset: {index: "0"}}, {dataset: {index: "1"}}];
cuota = "180.00";
vm.runInContext("documentosResultados = registrosPrueba; documentoSeleccionado = registrosPrueba[0]; actualizarResumenCreditosPropia()", contexto);
assert.equal(elementos.cancelacion.value, "180.00");
assert.equal(vm.runInContext("datosAcuerdoPropia().error", contexto), null);
elementos.cancelacion.value = "179.00";
assert.match(vm.runInContext("datosAcuerdoPropia().error", contexto), /Excepción/);

const botones = [{dataset: {index: "0"}}, {dataset: {index: "1"}}];
const casillas = [{dataset: {index: "0"}}, {dataset: {index: "1"}}];
for (const control of [...botones, ...casillas]) {
    control.addEventListener = (evento, handler) => { control[evento] = handler; };
}
elementos.panelResultados = {classList: {remove() {}, add() {}}};
elementos.contadorResultados = {textContent: ""};
elementos.tbodyResultados = {
    innerHTML: "",
    appendChild() {},
    querySelectorAll(selector) { return selector === "button[data-index]" ? botones : [...botones, ...casillas]; },
};
contexto.document.createElement = () => ({innerHTML: ""});
vm.runInContext("pintarResultados(documentosResultados)", contexto);
assert.ok(botones.every(boton => typeof boton.click === "function"));
assert.ok(casillas.every(casilla => casilla.click === undefined));

contexto.registrosPrueba = [
    {NumDocumento: "10771235", Operacion: "4040710002707212", DeudaTotal: 200, MontoReferenciaPropia: 80},
    {NumDocumento: "10771235", Operacion: "4040710009986512", DeudaTotal: 300, MontoReferenciaPropia: 100},
    {NumDocumento: "99999999", Operacion: "4040710000000000", DeudaTotal: 400, MontoReferenciaPropia: 150},
];
todosControles = contexto.registrosPrueba.map((_, index) => ({dataset: {index: String(index)}, checked: false}));
checks = todosControles;
elementos.panelGeneracion = {classList: {remove() {}}};
elementos.panelOperacionesMibanco = {classList: {add() {}}};
elementos.clienteSeleccionado = {textContent: ""};
vm.runInContext("documentosResultados = registrosPrueba; actualizarModoDocumento = () => {}; pintarPreviewDocumento = () => {}; seleccionarDocumento(1)", contexto);
assert.deepEqual(todosControles.map(control => control.checked), [true, true, false]);
assert.equal(todosControles[2].disabled, true);
assert.equal(elementos.cancelacion.value, "180.00");
todosControles[0].checked = false;
vm.runInContext("actualizarResumenCreditosPropia(); sincronizarCronogramaPropia(false)", contexto);
assert.equal(elementos.cancelacion.value, "100.00");
assert.equal(elementos.propiaMontoCuota.value, "100.00");

console.log("Cuotas de Propia: selección múltiple, suma y cronograma correctos.");
