"use strict";

// Estado de cuenta individual / CCM: redondeo de pantalla, acumulado y estados del modal.
// Uso: node tests/frontend/estado_cuenta_individual.test.js
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const raiz = path.resolve(__dirname, "..", "..");
const codigo = fs.readFileSync(path.join(raiz, "frontend", "js", "compartamos.js"), "utf8");
const radar = vm.createContext({
    window: { addEventListener() {}, matchMedia: () => ({ matches: false }) },
    document: {}, localStorage: { getItem: () => null }, sessionStorage: {}, Intl, Date,
});
vm.runInContext(codigo, radar);

const ec = {
    aplica: true, disponible: true, cartera: "Individual", tabla_asignacion: "compartamos_individual",
    dias_atraso_hoy: 85, simulacion_disponible: true, meses_entre_cuotas_estimado: 1,
    cuotas: [
        { numero: 7, fecha_vencimiento: "2026-08-15", fecha_estimada: false, dias_vencida: 85, capital: 410.35, cargos: 80.08, total: 490.43, queda_con_dias: 54, queda_con_estimado: true, componentes_cargos: { "CT 11": 52.18 } },
        { numero: 8, fecha_vencimiento: "2026-09-15", fecha_estimada: true, dias_vencida: 54, capital: 418.92, cargos: 52.30, total: 471.22, queda_con_dias: 24, queda_con_estimado: true, componentes_cargos: {} },
        { numero: 9, fecha_vencimiento: "2026-10-15", fecha_estimada: true, dias_vencida: 24, capital: 427.63, cargos: null, total: 427.63, queda_con_dias: 0, queda_con_estimado: false, componentes_cargos: {} },
    ],
    conciliacion: { cuotas_en_sac: 3, cuotas_vencidas: 3, completo: true, capital_vencido: 1256.90, suma_capital_cuotas: 1256.90, diferencia_capital: 0, cuadra_capital: true },
    campanas: { disponible: true, cuotas: [{ cuotas: 1, porcentaje: "20%", monto: 328.28 }, { cuotas: 2, porcentaje: null, monto: null }, { cuotas: 3, porcentaje: null, monto: null }, { cuotas: 4, porcentaje: "35%", monto: 900 }], cancelacion: { porcentaje: "45%", monto: 2189.22 } },
    advertencias: [],
};
radar.ecPrueba = ec;
// Los objetos vienen de otro contexto vm: se comparan como JSON.
const plano = valor => JSON.parse(JSON.stringify(valor));
const calcular = modo => plano(vm.runInContext(`calcularEstadoCuentaCRM(ecPrueba, "${modo}")`, radar));

// Capital y cargos se suben al sol por separado; el total mostrado es su suma (la fila cuadra).
const total = calcular("total");
assert.deepEqual(total.filas.map(f => [f.capitalMostrado, f.cargosMostrado, f.totalMostrado]), [[411, 81, 492], [419, 53, 472], [428, null, 428]]);
assert.deepEqual(total.filas.map(f => f.acumulado), [492, 964, 1392]);
assert.deepEqual(total.totales, { capital: 1258, cargos: 134, total: 1392 });

// Solo capital: el acumulado suma capital mostrado.
assert.deepEqual(calcular("capital").filas.map(f => f.acumulado), [411, 830, 1258]);

// Sin cuotas: totales nulos, no cero.
radar.ecVacio = { cuotas: [] };
assert.deepEqual(plano(vm.runInContext(`calcularEstadoCuentaCRM(ecVacio, "total").totales`, radar)), { capital: null, cargos: null, total: null });

// Texto de días resultantes.
assert.equal(vm.runInContext(`textoQuedaConCRM({queda_con_dias: 0})`, radar), "Queda al día");
assert.equal(vm.runInContext(`textoQuedaConCRM({queda_con_dias: 54, queda_con_estimado: true})`, radar), "Queda con 54 días de atraso (aprox.)");
assert.equal(vm.runInContext(`textoQuedaConCRM({queda_con_dias: null})`, radar), null);

// Botón solo cuando aplica.
assert.equal(vm.runInContext(`renderBotonEstadoCuentaCRM({operacion: "1", estado_cuenta: {aplica: false}})`, radar), "");
assert.match(vm.runInContext(`renderBotonEstadoCuentaCRM({operacion: "3021004587", estado_cuenta: {aplica: true}})`, radar), /data-abrir-estado-cuenta="3021004587"/);

// Pestaña de cuotas: selección "hasta la N.° 8" muestra el acumulado y los días resultantes.
const cuotasHtml = vm.runInContext(`renderEstadoCuentaCuotasCRM({cuotas_aprobadas: 12}, ecPrueba, "total", 1)`, radar);
assert.match(cuotasHtml, /Si paga hasta la N\.° 8/);
assert.match(cuotasHtml, /S\/ 964/);
assert.match(cuotasHtml, /Queda con 24 días de atraso \(aprox\.\)/);
assert.equal((cuotasHtml.match(/class="is-incluida"/g) || []).length, 2);

// Carga incompleta: aviso, filas faltantes y sin simulación.
radar.ecIncompleto = { ...ec, simulacion_disponible: false, simulacion_motivo: "Faltan cuotas vencidas en la carga.",
    conciliacion: { ...ec.conciliacion, cuotas_vencidas: 5, completo: false, cuadra_capital: false, capital_vencido: 1689.09, diferencia_capital: 432.19 } };
const incompleto = vm.runInContext(`renderEstadoCuentaCuotasCRM({}, ecIncompleto, "total", 0)`, radar);
assert.match(incompleto, /La carga trae 3 de 5 cuotas vencidas/);
assert.equal((incompleto.match(/crm-ec-falta/g) || []).length, 2);
assert.match(incompleto, /Días resultantes: no se pueden calcular/);

// No disponible: muestra el motivo del backend.
radar.ecNoDisponible = { aplica: true, disponible: false, motivo: "La operación no figura en la carga SAC del día." };
assert.match(vm.runInContext(`renderEstadoCuentaCuotasCRM({}, ecNoDisponible, "total", 0)`, radar), /no figura en la carga SAC/);

// Campañas: tal cual, con referencia de capital; 4 cuotas sin referencia (SAC trae 3).
const campanas = vm.runInContext(`renderEstadoCuentaCampanasCRM({capital: 3980.40}, ecPrueba)`, radar);
assert.match(campanas, /S\/ 329/);         // 328.28 -> 329
assert.match(campanas, /S\/ 411/);         // capital de la cuota 1
assert.match(campanas, /S\/ 1,258/);       // no aplica a la fila 3 (sin campaña) pero sí la referencia
assert.match(campanas, /crm-ec-sin-ref/);  // campaña de 4 cuotas
assert.match(campanas, /S\/ 3,981/);       // saldo capital de referencia para cancelación

console.log("estado_cuenta_individual.test.js OK");
