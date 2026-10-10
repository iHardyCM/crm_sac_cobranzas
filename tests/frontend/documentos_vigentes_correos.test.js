"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const source = fs.readFileSync(path.resolve(__dirname, "..", "..", "frontend", "js", "documentos.js"), "utf8");
let cartera = "133";
let tipo = "compromiso_cuota_individual";
const elementos = {cancelacion: {value: "450"}, cuotasIndividual: {value: "1"}};
const context = vm.createContext({
    window: {location: {protocol: "http:", hostname: "localhost"}},
    document: {
        addEventListener() {},
        getElementById(id) {
            if (id === "documentoCartera") return {value: cartera};
            if (id === "documentoTipo") return {value: tipo};
            return elementos[id] || null;
        },
    },
});
vm.runInContext(source, context);
vm.runInContext(`
    documentoSeleccionado = {
        NomCliente: "CLIENTE PRUEBA", Operacion: "21201555", CodigoGrupo: "341738",
        CodCreGrupal: "21201544", NomGrupo: "GRUPO PRUEBA", UltCuotaAtrasada: 8,
    };
    agenciaDestinoCastigo = () => ({nombre: "PUENTE PIEDRA", gerente: "", correoGa: "agencia@compartamos.pe", correoAgencia: ""});
    ccAgenciaOrigenCastigo = () => "";
    textoDesdeHtml = () => "";
    obtenerEncargadoPreview = () => ({nombre: "ENCARGADO"});
    totalPagoGrupo = () => 450;
    tablaDetalleGrupoCorreo = () => "";
`, context);

const correo = funcion => vm.runInContext(`${funcion}()`, context);
const supervisorCastigo = "supervisor.compartamos@biznescob.pe";
const supervisorGrupal = "supervisor2.compartamos@biznescob.pe";
const supervisorIndividual = "supervisor3.compartamos@biznescob.pe";

let resultado = correo("correoCuotaIndividual");
assert.match(resultado.asunto, /^CSM_VIGENTE_CAMPAÑA_CUOTAS_/);
assert.match(resultado.destinatarios, new RegExp(supervisorGrupal));
assert.doesNotMatch(resultado.destinatarios, new RegExp(supervisorCastigo));

tipo = "transaccion_cancelacion";
resultado = correo("correoCancelacionIndividual");
assert.match(resultado.asunto, /^MITIGACION_CSM_CANCELACION_/);
assert.match(resultado.destinatarios, new RegExp(supervisorGrupal));

tipo = "cancelacion_grupal";
resultado = correo("correoCancelacionGrupal");
assert.match(resultado.asunto, /_CSM_/);
assert.match(resultado.destinatarios, new RegExp(supervisorGrupal));

tipo = "compromiso_cuota_grupal";
resultado = correo("correoCuotaGrupal");
assert.match(resultado.asunto, /_CSM_/);
assert.match(resultado.destinatarios, new RegExp(supervisorGrupal));

for (const id of ["126", "128"]) {
    cartera = id;
    tipo = "vigente_individual_cuota";
    resultado = correo("correoCuotaIndividual");
    assert.match(resultado.asunto, /^IND_VIGENTE_CAMPAÑA_CUOTAS_/);
    assert.match(resultado.destinatarios, new RegExp(supervisorIndividual));
    assert.doesNotMatch(resultado.destinatarios, new RegExp(supervisorCastigo));
    tipo = "vigente_individual_cancelacion";
    resultado = correo("correoCancelacionIndividual");
    assert.match(resultado.destinatarios, new RegExp(supervisorIndividual));
}

assert.match(vm.runInContext("destinatariosCastigo({correoGa: '', correoAgencia: ''})", context), new RegExp(supervisorCastigo));
console.log("Correos de carteras vigentes y asuntos CSM/IND: OK");
