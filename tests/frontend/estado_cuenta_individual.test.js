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

// Campañas (regla 11/11/2026). Payload generado por construir_estado_cuenta con los montos del caso
// verificado contra el cronograma del banco (cuotas 10 y 11; 5% Capital; cancelación 20% Capital).
radar.ecBanco = {"aplica": true, "disponible": true, "motivo": null, "fuente": "SAC_CAR_BIZNESCOB", "cartera": "Individual", "tabla_asignacion": "compartamos_individual", "cuotas_aprobadas_asignacion": 12, "cuotas_pagadas_asignacion": 9, "campanas": {"disponible": true, "cuotas": [{"cuotas": 1, "porcentaje": "5% Capital", "tipo": "CAPITAL", "descuento": 5.0, "regla": "Capital − 5%", "aplica": true, "motivo": null, "monto_asignacion": 193.9235, "monto_calculado": 193.9235, "coincide": true, "monto": 193.9235}, {"cuotas": 2, "porcentaje": "5% Capital", "tipo": "CAPITAL", "descuento": 5.0, "regla": "Capital − 5%", "aplica": true, "motivo": null, "monto_asignacion": 399.9215, "monto_calculado": 399.9215, "coincide": true, "monto": 399.9215}, {"cuotas": 3, "porcentaje": "Sin Campania", "tipo": "SIN_CAMPANA", "descuento": null, "regla": "Cuota completa", "aplica": false, "motivo": "El cliente tiene 2 cuotas vencidas.", "monto_asignacion": null, "monto_calculado": null, "coincide": null, "monto": null}, {"cuotas": 4, "porcentaje": "Sin Campania", "tipo": "SIN_CAMPANA", "descuento": null, "regla": "Cuota completa", "aplica": false, "motivo": "El cliente tiene 2 cuotas vencidas.", "monto_asignacion": null, "monto_calculado": null, "coincide": null, "monto": null}], "cancelacion": {"porcentaje": "20% Capital", "tipo": "CAPITAL", "descuento": 20.0, "regla": "Saldo capital − 20%", "base_capital": 660.64, "monto_asignacion": 528.512, "monto_calculado": 528.512, "coincide": true, "monto": 528.512}}, "meses_entre_cuotas_estimado": 1, "cuotas": [{"numero": 10, "posicion_ct": 1, "fecha_vencimiento": "2026-09-21", "fecha_estimada": false, "dias_vencida": 51, "por_vencer": false, "capital": 204.13, "cargos": 59.22, "total": 263.35, "componentes_cargos": {"CT 11": 1.0, "CT 12": 0.0, "CT 13": 33.87, "CT 14": 19.82, "CT 15": 4.53}, "queda_con_dias": 21, "queda_con_estimado": true, "cobro": {"cuotas": 1, "porcentaje": "5% Capital", "tipo": "CAPITAL", "regla": "Capital − 5%", "monto": 193.9235, "coincide": true}}, {"numero": 11, "posicion_ct": 2, "fecha_vencimiento": "2026-10-21", "fecha_estimada": true, "dias_vencida": 21, "por_vencer": false, "capital": 216.84, "cargos": 32.6, "total": 249.44, "componentes_cargos": {"CT 21": 1.0, "CT 22": 0.0, "CT 23": 21.16, "CT 24": 8.36, "CT 25": 2.08}, "queda_con_dias": 0, "queda_con_estimado": false, "cobro": {"cuotas": 2, "porcentaje": "5% Capital", "tipo": "CAPITAL", "regla": "Capital − 5%", "monto": 399.9215, "coincide": true}}], "advertencias": [], "cuota_mas_atrasada": 10, "dias_atraso_hoy": 51, "fecha_carga": null, "fecha_corte": "2026-11-11", "fecha_corte_fuente": "UltFecVen + DiasAtraso", "totales": {"capital": 420.97, "cargos": 91.82, "total": 512.79}, "conciliacion": {"cuotas_en_sac": 2, "cuotas_vencidas": 2, "completo": true, "capital_vencido": 420.97, "suma_capital_cuotas": 420.97, "diferencia_capital": 0.0, "cuadra_capital": true}, "simulacion_disponible": true, "simulacion_motivo": null};
const campanas = vm.runInContext(`renderEstadoCuentaCampanasCRM({capital: 660.64}, ecBanco)`, radar);
assert.match(campanas, /Capital − 5%/);
assert.match(campanas, /S\/ 194/);          // 193.9235 -> 194
assert.match(campanas, /S\/ 400/);          // 399.9215 -> 400
assert.match(campanas, /S\/ 529/);          // cancelación 528.512 -> 529
assert.equal((campanas.match(/✓ Coincide/g) || []).length, 3);
assert.equal((campanas.match(/El cliente tiene 2 cuotas vencidas/g) || []).length, 2);

// Tabla de cuotas: columna "Con campaña" y cifra "A cobrar hasta la N.° 11".
const cuotasBanco = vm.runInContext(`renderEstadoCuentaCuotasCRM({cuotas_aprobadas: 12}, ecBanco, "total", 1)`, radar);
assert.match(cuotasBanco, /A cobrar hasta la N\.° 11 · 5% Capital/);
assert.match(cuotasBanco, /S\/ 400/);
assert.match(cuotasBanco, /sin campaña S\/ 515/);   // (205 + 60) + (217 + 33): capital y cargos suben al sol por separado
assert.match(cuotasBanco, /<b>S\/ 194<\/b><small>5% Capital<\/small>/);

// Sin campaña: la cifra vuelve al acumulado de la cuota completa.
const cobroSin = vm.runInContext(`celdaCobroCampanaCRM({tipo: "SIN_CAMPANA", monto: 263.35, porcentaje: "Sin Campania"})`, radar);
assert.match(cobroSin, /S\/ 264.*Sin campaña/);
assert.equal(vm.runInContext(`celdaCobroCampanaCRM(null)`, radar), "—");

// Asignación y cálculo distintos: se cobra el mayor y se muestra el otro como referencia.
const mayorAsig = vm.runInContext(`verificacionCampanaCRM({coincide: false, monto_fuente: "ASIGNACION", monto_asignacion: 127.28, monto_calculado: 119.27})`, radar);
assert.match(mayorAsig, /Se cobra el mayor \(asignación\)/);
assert.match(mayorAsig, /Cálculo hoy: S\/ 119\.27/);
const mayorCalc = vm.runInContext(`verificacionCampanaCRM({coincide: false, monto_fuente: "CALCULO", monto_asignacion: 190, monto_calculado: 193.92})`, radar);
assert.match(mayorCalc, /Se cobra el mayor \(cálculo de hoy\)/);

console.log("estado_cuenta_individual.test.js OK");
