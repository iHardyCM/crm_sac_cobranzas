const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

async function probarConsultaConCuenta() {
    const elementos = Object.fromEntries([
        'mowaDesde', 'mowaHasta', 'mowaCuenta', 'mowaConsultar', 'mowaEstado',
        'mowaBuscar', 'mowaTabla', 'mowaPendientes', 'mowaAtendidas',
        'mowaSinVincular', 'mowaSinVerificar', 'mowaConsultaHora',
        'mowaAlcance', 'mowaAviso', 'mowaCargando', 'mowaSegundos',
        'mowaProgreso', 'mowaCardPendientes', 'mowaCardAlcance',
        'mowaCartera', 'mowaOrden', 'mowaTamano', 'mowaMas', 'mowaAnterior',
        'mowaPaginacion', 'mowaExportar', 'mowaChat', 'mowaChatTexto',
        'mowaChatCaracteres', 'mowaChatAviso', 'mowaChatDestino',
        'mowaChatEnviar', 'mowaChatTitulo', 'mowaChatSubtitulo', 'mowaChatMensajes',
        'mowaSinAtender', 'mowaSinAtenderTotal', 'mowaSinAtenderDetalle', 'mowaSinAtenderAccion',
        'mowaVerCarteras', 'mowaCardPendientesTitulo', 'mowaCarterasModal',
        'mowaDona', 'mowaCarterasLista', 'mowaCarterasSubtitulo', 'mowaCarterasNota', 'mowaCarterasCerrar',
        'mowaDetalle', 'mowaSyncAcciones', 'mowaSyncDias', 'mowaSyncBoton', 'mowaSyncEstado',
        'mowaBandejaBar', 'mowaBandejaActualizar', 'mowaBandejaResumen',
        'mowaAsignacionControl', 'mowaAsignacionFiltro', 'mowaAsignarCerrar',
        'mowaAsignarModal', 'mowaAsignarForm', 'mowaAsignarAgente', 'mowaAsignarAviso',
        'mowaAsignarGuardar', 'mowaAsignarBuscar', 'mowaAsignarLista',
        'mowaAsignarSeleccionado', 'mowaSeleccionCol', 'mowaSeleccionPagina',
        'mowaSeleccionBar', 'mowaSeleccionFiltrados', 'mowaSeleccionLimpiar',
        'mowaAsignarSeleccion', 'mowaSeleccionConteo',
        'mowaControlAbrir', 'mowaControlModal', 'mowaControlCerrar',
        'mowaControlActualizar', 'mowaControlCartera', 'mowaControlAviso',
        'mowaControlTotal', 'mowaControlSinAsignar', 'mowaControlAsignados',
        'mowaControlAntiguos', 'mowaControlAlcance', 'mowaControlAgentes', 'mowaControlSync',
    ].map(id => [id, {value: '', textContent: '', innerHTML: '', disabled: false}]));
    elementos.mowaExportar.removeAttribute = () => {};
    elementos.mowaCuenta.selectedOptions = [{textContent: 'MiBanco castigo'}];
    elementos.mowaCarterasModal.showModal = () => { elementos.mowaCarterasModal.open = true; };
    elementos.mowaCarterasModal.close = () => { elementos.mowaCarterasModal.open = false; };
    elementos.mowaDetalle.scrollIntoView = () => {};
    elementos.mowaCardPendientes.classList = {toggle() {}};
    elementos.mowaSinAtender.classList = {toggle() {}};
    elementos.mowaChat.showModal = () => { elementos.mowaChat.open = true; };
    elementos.mowaDesde.value = '2026-11-16';
    elementos.mowaHasta.value = '2026-11-19';
    elementos.mowaCuenta.value = 'MI_BANCO_CAS';
    elementos.mowaOrden.value = 'reciente';
    elementos.mowaTamano.value = '20';
    elementos.mowaSyncEstado.dataset = {};
    let rutaConsultada;
    let descarga;
    const contexto = {
        window: {location: {protocol: 'http:', hostname: 'localhost'}},
        URL: {createObjectURL: () => 'blob:excel', revokeObjectURL() {}},
        document: {
            addEventListener() {},
            getElementById(id) { return elementos[id]; },
            createElement() { return {click() { descarga = this.download; }, remove() {}}; },
            body: {appendChild() {}},
        },
        fetchConSesion: async ruta => {
            if (ruta.includes('/sin-atender')) return {ok: true, json: async () => ({
                clientes: 2, respuestas: 3, clientes_ayer_hoy: 1, desde: '2026-11-01', completo: true,
                por_cartera: [{idcartera: 112, clientes: 2}],
                sincronizacion: {fin: '2026-11-20T09:50:00', resultado: 'OK', desactualizada: false},
            })};
            rutaConsultada = ruta;
            return {ok: true, json: async () => ({sincronizacion: {fin: '2026-11-20T09:50:00', desactualizada: true}, data: [{
                estado: 'PENDIENTE', dni: '12345678', cliente: 'Cliente',
                telefono: '999999999', texto: 'Hola', mensaje_enviado: 'SMS enviado',
                estado_mowa_codigo: 2, estado_mowa_etiqueta: 'ASESORAMIENTO', campana: 'Campaña',
                cuenta: 'MI_BANCO_CAS', recibido: '2026-11-19T10:00:00',
                mensaje_enviado_fecha: '2026-11-19T09:50:00', mensaje_id: '501',
                id: '1', campana_id: 1, campana_creacion: '2026-11-19', idcliente: 11, idcartera: 112,
            }], completo: true, advertencias: []})};
        },
        URLSearchParams, AbortController, setTimeout, clearTimeout, setInterval, clearInterval, Date,
    };
    const script = fs.readFileSync(path.join(__dirname, '../../frontend/js/respuestas_mowa.js'), 'utf8');
    vm.runInNewContext(script, contexto);
    assert.deepEqual(JSON.parse(JSON.stringify(contexto.rangoHistorialMowa('2026-11-10', '2026-11-19', '2026-11-20'))),
        {desde: '2026-11-10', hasta: '2026-11-20'}); // La campaña anterior al rango se incluye.
    assert.deepEqual(JSON.parse(JSON.stringify(contexto.rangoHistorialMowa('2026-09-01', '2026-11-19', '2026-11-20'))),
        {desde: '2026-09-01', hasta: '2026-10-01'}); // Máximo 31 días.
    assert.match(contexto.resumirAdvertenciasMowa([
        'PROPIA_BIZNES: Consulta Mowa fallida (ReadTimeout).',
        'PROPIA_BIZNES: Consulta Mowa fallida (ReadTimeout).',
    ]), /PROPIA_BIZNES: Mowa excedió el tiempo de lectura\. \(2 veces\)/);
    await contexto.consultarMowa({preventDefault() {}});
    assert.match(rutaConsultada, /\/respuestas-mowa\/recibidas\?desde=2026-11-16&hasta=2026-11-19&cuenta=MI_BANCO_CAS/);
    assert.equal(elementos.mowaSinAtenderTotal.textContent, '2');
    assert.match(elementos.mowaSinAtenderDetalle.textContent, /3 respuestas · 1 de ayer y hoy/);
    assert.equal(elementos.mowaSinAtender.disabled, false);
    assert.match(elementos.mowaConsultaHora.textContent, /sin actualización reciente/);
    assert.equal(elementos.mowaPendientes.textContent, '1');
    assert.match(elementos.mowaAlcance.textContent, /MI_BANCO_CAS/);
    assert.match(elementos.mowaTabla.innerHTML, /Ver conversación \(1\)/);
    assert.match(elementos.mowaTabla.innerHTML, /ASESORAMIENTO/);
    assert.match(elementos.mowaTabla.innerHTML, /Sin gestión posterior/);
    assert.equal(elementos.mowaCargando.hidden, true);
    assert.equal(elementos.mowaConsultar.disabled, false);
    contexto.agregarFilasMowa([
        {estado: 'PENDIENTE', dni: '12345678', cliente: 'Cliente', telefono: '999999999',
            texto: 'Segunda', mensaje_enviado: 'SMS enviado', mensaje_enviado_fecha: '2026-11-19T09:50:00',
            cuenta: 'MI_BANCO_CAS', recibido: '2026-11-19T10:01:00', mensaje_id: '501',
            id: '2', campana_id: 1, campana_creacion: '2026-11-19', idcliente: 11, idcartera: 112},
        {estado: 'PENDIENTE', dni: '12345678', cliente: 'Cliente', telefono: '999999999',
            texto: 'Tercera', mensaje_enviado: 'SMS enviado', mensaje_enviado_fecha: '2026-11-19T09:50:00',
            cuenta: 'MI_BANCO_CAS', recibido: '2026-11-19T10:02:00', mensaje_id: '501',
            id: '3', campana_id: 1, campana_creacion: '2026-11-19', idcliente: 11, idcartera: 112},
    ]);
    const grupos = contexto.agruparMowa();
    assert.equal(grupos.length, 1);
    assert.equal(grupos[0].filas.length, 3);
    assert.equal(contexto.eventosChatMowa(grupos[0]).length, 4); // Un envío y tres respuestas.
    contexto.actualizarResumenMowa(true, true);
    assert.equal(elementos.mowaPendientes.textContent, '1'); // Un cliente, no tres SMS.
    contexto.fetchConSesion = async ruta => {
        assert.match(ruta, /\/respuestas-mowa\/historial\?/);
        return {ok: true, json: async () => ({eventos: [
            {lado: 'nosotros', id: '501', campana_id: 1, cuenta: 'MI_BANCO_CAS',
                telefono: '999999999', texto: 'SMS enviado', fecha: '2026-11-19T09:50:00'},
            {lado: 'nosotros', id: '601', campana_id: 2, cuenta: 'MI_BANCO_CAS',
                telefono: '999999999', texto: 'Seguimiento sin respuesta', fecha: '2026-11-19T10:10:00'},
        ], advertencias: []})};
    };
    await contexto.abrirChatMowa(grupos[0]);
    assert.equal((elementos.mowaChatMensajes.innerHTML.match(/mowa-burbuja-cliente/g) || []).length, 3);
    assert.equal((elementos.mowaChatMensajes.innerHTML.match(/mowa-burbuja-nosotros/g) || []).length, 2);
    assert.match(elementos.mowaChatMensajes.innerHTML, /Seguimiento sin respuesta/);
    assert.match(elementos.mowaChatMensajes.innerHTML, /19\/11\/2026 10:02:00/);
    elementos.mowaChatTexto.value = 'Te contactamos';
    let envio;
    contexto.fetchConSesion = async (ruta, opciones) => {
        envio = {ruta, opciones};
        return {ok: true, json: async () => ({mensaje_id: '700', campana_id: '800',
            texto: 'Te contactamos', telefono: '999999999', cuenta: 'MI_BANCO_CAS',
            fecha: '2026-11-19T10:20:00', estado_etiqueta: 'Pendiente de Envío'})};
    };
    await contexto.enviarChatMowa({preventDefault() {}});
    assert.match(envio.ruta, /\/respuestas-mowa\/enviar$/);
    assert.equal(JSON.parse(envio.opciones.body).mensaje_id, 501);
    assert.equal(JSON.parse(envio.opciones.body).fecha_campana, '2026-11-19');
    assert.equal(JSON.parse(envio.opciones.body).telefono, undefined);
    assert.equal((elementos.mowaChatMensajes.innerHTML.match(/mowa-burbuja-nosotros/g) || []).length, 3);
    assert.equal(elementos.mowaPendientes.textContent, '1'); // Enviar no tipifica SISCOB.
    let cierres = 0;
    elementos.mowaChat.getBoundingClientRect = () => ({left: 100, right: 500, top: 100, bottom: 600});
    elementos.mowaChat.close = () => { cierres++; };
    contexto.cerrarChatFueraMowa({target: elementos.mowaChat, clientX: 250, clientY: 250});
    contexto.cerrarChatFueraMowa({target: elementos.mowaChatTexto, clientX: 50, clientY: 50});
    assert.equal(cierres, 0); // Clic dentro del modal.
    contexto.cerrarChatFueraMowa({target: elementos.mowaChat, clientX: 50, clientY: 250});
    assert.equal(cierres, 1); // Clic en el fondo.

    elementos.mowaDesde.value = '2026-11-01';
    elementos.mowaHasta.value = '2026-11-30';
    elementos.mowaCuenta.value = '';
    const llamadas = [];
    contexto.fetchConSesion = async ruta => {
        if (ruta.includes('/sin-atender')) return {ok: true, json: async () => ({
            clientes: 6, respuestas: 6, clientes_ayer_hoy: 0, desde: '2026-11-01', completo: true,
            por_cartera: [{idcartera: 124, clientes: 6}]})};
        llamadas.push(ruta);
        return {ok: true, json: async () => ({
            data: ['01', '08', '15', '22', '29', '29'].map((dia, i) => ({
                estado: 'PENDIENTE', dni: String(i + 1), cliente: 'Cliente',
                telefono: '999999999', texto: 'Sí', mensaje_enviado: 'Aviso',
                recibido: `2026-11-${dia}T1${i}:00:00`, id: String(i + 1),
                cuenta: 'COMPARCARTIGO', campana_id: i + 1, idcartera: 124})),
            completo: true, alcance_carteras: [124], advertencias: [], excluidas_inactivas: 2,
        })};
    };
    await contexto.consultarMowa({preventDefault() {}});
    assert.equal(llamadas.length, 1); // Una sola lectura de la tabla, sin bloques ni páginas.
    assert.equal(elementos.mowaPendientes.textContent, '6');
    assert.match(elementos.mowaCardAlcance.textContent, /Cartera 124.*recibidas en el rango/);
    assert.match(elementos.mowaAlcance.textContent, /2 respuestas ocultas por cliente inactivo/);
    elementos.mowaOrden.value = 'antiguo';
    contexto.pintarMowa();
    assert.ok(elementos.mowaTabla.innerHTML.indexOf('01/11/2026') < elementos.mowaTabla.innerHTML.indexOf('29/11/2026'));
    contexto.agregarFilasMowa(Array.from({length: 25}, (_, i) => ({
        estado: 'PENDIENTE', dni: String(20000000 + i), cliente: `Extra ${i}`,
        telefono: '999999999', texto: 'Sí', recibido: `2026-11-30T10:${String(i).padStart(2, '0')}:00`,
        id: String(100 + i), campana_id: 100 + i, cuenta: 'COMPARCARTIGO',
        idcliente: 100 + i, idcartera: 124,
    })));
    contexto.pintarMowa();
    assert.match(elementos.mowaPaginacion.textContent, /1–20 de 31 conversaciones/);
    assert.equal(elementos.mowaMas.disabled, false);
    contexto.cambiarPaginaMowa(1);
    assert.match(elementos.mowaPaginacion.textContent, /21–31 de 31 conversaciones/);
    assert.equal(elementos.mowaAnterior.disabled, false);
    assert.equal(contexto.datosExportMowa().conversaciones.length, 31); // Todas las páginas.
    elementos.mowaTamano.value = '50';
    contexto.pintarMowa();
    assert.match(elementos.mowaPaginacion.textContent, /1–31 de 31 conversaciones/);
    let exportados;
    contexto.fetchConSesion = async (ruta, opciones) => {
        assert.match(ruta, /\/respuestas-mowa\/exportar$/);
        exportados = JSON.parse(opciones.body);
        return {ok: true, blob: async () => new Uint8Array([80, 75])};
    };
    await contexto.exportarMowa();
    assert.equal(exportados.conversaciones.length, 31);
    assert.equal(exportados.etiqueta_rango, 'Respuestas recibidas');
    let rutaExcel;
    contexto.fetchConSesion = async ruta => {
        rutaExcel = ruta;
        return {ok: true, headers: {get: () => 'attachment; filename="SMS_sin_atender_2026-11-20.xlsx"'},
            blob: async () => new Uint8Array([80, 75])};
    };
    elementos.mowaSinAtenderTotal.textContent = '6';
    await contexto.descargarSinAtenderMowa();
    assert.match(rutaExcel, /\/respuestas-mowa\/sin-atender\/excel$/);
    assert.match(descarga, /SMS_sin_atender_2026-11-20\.xlsx/);
    contexto.abrirCarterasMowa();
    assert.match(elementos.mowaDona.innerHTML, /data-cartera="124"/);
    assert.match(elementos.mowaCarterasLista.innerHTML, /Cartera 124/);
    assert.equal(elementos.mowaCarterasModal.open, true);
    let rutaDetalle;
    contexto.fetchConSesion = async ruta => {
        rutaDetalle = ruta;
        return {ok: true, json: async () => ({
            clientes: 1, respuestas: 1, desde: '2026-11-01', completo: true,
            grupos: [{estado: 'PENDIENTE', filas: [{
                cuenta: 'COMPARCARTIGO', campana_id: 5, id: '9', mensaje_id: '99',
                idcartera: 124, idcliente: 9, dni: '12345678', cliente: 'Pendiente antiguo',
                telefono: '999999999', texto: 'Responder', estado: 'PENDIENTE',
                recibido: '2026-11-05T10:00:00',
            }]}],
        })};
    };
    await contexto.verPendientesCarteraMowa(124);
    assert.match(rutaDetalle, /\/sin-atender\/detalle\?cartera=124$/);
    assert.match(elementos.mowaTabla.innerHTML, /Pendiente antiguo/);
    assert.match(elementos.mowaAlcance.textContent, /acumuladas desde/);
    assert.equal(elementos.mowaEstado.value, 'PENDIENTE');
    assert.equal(elementos.mowaCartera.value, '124');
    assert.equal(elementos.mowaExportar.textContent, 'Excel de cartera');
    contexto.fetchConSesion = async ruta => {
        rutaExcel = ruta;
        return {ok: true, headers: {get: () => ''}, blob: async () => new Uint8Array([80, 75])};
    };
    await contexto.exportarMowa();
    assert.match(rutaExcel, /\/sin-atender\/excel\?cartera=124$/);
}

async function probarCargaAutomatica(alcance, agente = false) {
    const ids = [
        'mowaDesde', 'mowaHasta', 'mowaCuenta', 'mowaConsultar', 'mowaEstado',
        'mowaBuscar', 'mowaTabla', 'mowaPendientes', 'mowaAtendidas',
        'mowaSinVincular', 'mowaSinVerificar', 'mowaConsultaHora',
        'mowaAlcance', 'mowaAviso', 'mowaCargando', 'mowaSegundos',
        'mowaProgreso', 'mowaCardPendientes', 'mowaCardAlcance',
        'mowaCartera', 'mowaOrden', 'mowaTamano', 'mowaMas', 'mowaAnterior',
        'mowaPaginacion', 'mowaExportar', 'mowaChat', 'mowaChatTexto',
        'mowaChatCaracteres', 'mowaChatAviso', 'mowaChatDestino',
        'mowaChatEnviar', 'mowaChatTitulo', 'mowaChatSubtitulo', 'mowaChatMensajes',
        'mowaFiltros', 'mowaCancelar', 'mowaChatCerrar', 'mowaChatForm',
        'mowaSinAtender', 'mowaSinAtenderTotal', 'mowaSinAtenderDetalle', 'mowaSinAtenderAccion',
        'mowaVerCarteras', 'mowaCardPendientesTitulo', 'mowaCarterasModal',
        'mowaDona', 'mowaCarterasLista', 'mowaCarterasSubtitulo', 'mowaCarterasNota', 'mowaCarterasCerrar',
        'mowaDetalle', 'mowaSyncAcciones', 'mowaSyncDias', 'mowaSyncBoton', 'mowaSyncEstado',
        'mowaBandejaBar', 'mowaBandejaActualizar', 'mowaBandejaResumen',
        'mowaAsignacionControl', 'mowaAsignacionFiltro', 'mowaAsignarCerrar',
        'mowaAsignarModal', 'mowaAsignarForm', 'mowaAsignarAgente', 'mowaAsignarAviso',
        'mowaAsignarGuardar', 'mowaAsignarBuscar', 'mowaAsignarLista',
        'mowaAsignarSeleccionado', 'mowaSeleccionCol', 'mowaSeleccionPagina',
        'mowaSeleccionBar', 'mowaSeleccionFiltrados', 'mowaSeleccionLimpiar',
        'mowaAsignarSeleccion', 'mowaSeleccionConteo',
        'mowaControlAbrir', 'mowaControlModal', 'mowaControlCerrar',
        'mowaControlActualizar', 'mowaControlCartera', 'mowaControlAviso',
        'mowaControlTotal', 'mowaControlSinAsignar', 'mowaControlAsignados',
        'mowaControlAntiguos', 'mowaControlAlcance', 'mowaControlAgentes', 'mowaControlSync',
    ];
    const elementos = Object.fromEntries(ids.map(id => [id, {
        value: '', textContent: '', innerHTML: '', disabled: false, addEventListener() {},
    }]));
    elementos.mowaCardPendientes.classList = {toggle() {}};
    elementos.mowaSinAtender.classList = {toggle() {}};
    elementos.mowaExportar.removeAttribute = () => {};
    elementos.mowaCarterasModal.showModal = () => {};
    elementos.mowaCarterasModal.close = () => {};
    elementos.mowaTamano.value = '20';
    elementos.mowaSyncEstado.dataset = {};
    elementos.mowaCuenta.appendChild = () => {};
    elementos.mowaEstado.closest = () => ({hidden: false});
    elementos.mowaDetalle.scrollIntoView = () => {};
    let iniciar;
    const consultas = [];
    class FechaFija extends Date {
        constructor(...args) { super(...(args.length ? args : ['2026-11-03T12:00:00-05:00'])); }
        static now() { return new Date('2026-11-03T12:00:00-05:00').getTime(); }
    }
    const contexto = {
        window: {location: {protocol: 'http:', hostname: 'localhost'}},
        document: {
            addEventListener(tipo, callback) { if (tipo === 'DOMContentLoaded') iniciar = callback; },
            getElementById(id) { return elementos[id]; },
            querySelector() { return {hidden: false, textContent: ''}; },
            createElement() { return {value: '', textContent: ''}; },
        },
        asegurarSesionBackend: async () => true,
        fetchConSesion: async ruta => {
            if (ruta.endsWith('/opciones')) return {ok: true, json: async () => ({
                alcance_carteras: alcance,
                modo: agente ? 'BANDEJA' : 'GENERAL',
                cuentas: [{id: 'COMPARCARTIGO', nombre: 'Compartamos castigo'}],
            })};
            if (ruta.endsWith('/bandeja')) {
                consultas.push(ruta);
                return {ok: true, json: async () => ({clientes: 1, respuestas: 1,
                    completo: true, grupos: [{filas: [{
                        cuenta: 'COMPARCARTIGO', campana_id: 1, id: '1', idcliente: 11,
                        idcartera: 124, dni: '12345678', cliente: 'Cliente asignado',
                        telefono: '999999999', texto: 'Sí', estado: 'PENDIENTE',
                        recibido: '2026-11-03T10:00:00',
                    }]}]})};
            }
            if (ruta.includes('/sin-atender')) return {ok: true, json: async () => ({
                clientes: 1, respuestas: 1, clientes_ayer_hoy: 1, desde: '2026-11-01', completo: true})};
            consultas.push(ruta);
            return {ok: true, json: async () => ({data: [{
                cuenta: 'COMPARCARTIGO', campana_id: 1, id: '1', idcliente: 11,
                idcartera: 124, dni: '12345678', cliente: 'Cliente', telefono: '999999999',
                texto: 'Sí', estado: 'PENDIENTE', recibido: '2026-11-03T10:00:00',
            }], advertencias: [], siguiente_offset: null, alcance_carteras: alcance, total_campanas: 1})};
        },
        URLSearchParams, AbortController, setTimeout, clearTimeout,
        setInterval: () => 1, clearInterval() {}, Date: FechaFija,
    };
    const script = fs.readFileSync(path.join(__dirname, '../../frontend/js/respuestas_mowa.js'), 'utf8');
    vm.runInNewContext(script, contexto);
    await iniciar();
    assert.equal(elementos.mowaDesde.value, '2026-11-02'); // Ayer.
    assert.equal(elementos.mowaHasta.value, '2026-11-03');
    assert.equal(elementos.mowaEstado.value, 'PENDIENTE');
    assert.equal(elementos.mowaOrden.value, 'antiguo');
    assert.equal(consultas.length, 1);
    if (agente) {
        assert.match(consultas[0], /\/bandeja$/);
        assert.equal(elementos.mowaExportar.hidden, true);
        assert.match(elementos.mowaTabla.innerHTML, /Cliente asignado/);
        return;
    }
    assert.match(consultas[0], /\/recibidas\?desde=2026-11-02&hasta=2026-11-03$/); // Todas las cuentas autorizadas.
    assert.equal(elementos.mowaSinAtenderTotal.textContent, '1');
    assert.equal(elementos.mowaPendientes.textContent, '1');
    assert.match(elementos.mowaTabla.innerHTML, /Cliente/);
    assert.match(elementos.mowaCardAlcance.textContent, alcance === null ? /Todas las carteras/ : /Cartera 124/);
}

async function probarActualizacionManual() {
    const elementos = {
        mowaSyncAcciones: {hidden: false},
        mowaSyncDias: {value: '7'},
        mowaSyncBoton: {disabled: false, textContent: ''},
        mowaSyncEstado: {hidden: true, textContent: '', dataset: {}},
    };
    let lecturas = 0;
    let recargas = 0;
    const contexto = {
        window: {location: {protocol: 'http:', hostname: 'localhost'}},
        document: {addEventListener() {}, getElementById(id) { return elementos[id]; }},
        fetchConSesion: async (ruta, opciones) => {
            assert.match(ruta, /\/respuestas-mowa\/sincronizacion$/);
            if (opciones?.method === 'POST') {
                assert.equal(JSON.parse(opciones.body).dias, 7);
                return {ok: true, json: async () => ({id_anterior: 3, desde: '2026-11-18'})};
            }
            lecturas++;
            return {ok: true, json: async () => lecturas === 1
                ? {id: 4, inicio: '2026-11-24T16:00:00', en_curso: true}
                : {id: 4, fin: '2026-11-24T16:05:00', en_curso: false,
                    resultado: 'CON_AVISOS', respuestas_nuevas: 6, origenes_completados: 4,
                    campanas_nuevas: 17, avisos: 2}};
        },
        setTimeout: () => 1, clearTimeout() {}, Date,
    };
    vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../../frontend/js/respuestas_mowa.js'), 'utf8'), contexto);
    contexto.consultarMowa = async () => { recargas++; };
    await contexto.iniciarActualizacionMowa();
    assert.equal(elementos.mowaSyncBoton.disabled, true);
    assert.match(elementos.mowaSyncEstado.textContent, /Actualización iniciada el/);
    await contexto.consultarEstadoActualizacionMowa();
    assert.equal(elementos.mowaSyncBoton.disabled, false);
    assert.equal(recargas, 1);
    assert.match(elementos.mowaSyncEstado.textContent, /6 respuestas nuevas.*4 respuestas con origen completado.*2 avisos/);
}

Promise.all([probarConsultaConCuenta(), probarCargaAutomatica([124]), probarCargaAutomatica(null),
    probarCargaAutomatica([124], true), probarActualizacionManual()])
    .then(() => console.log('Consulta SMS con cuenta y carga automática: OK'))
    .catch(error => { console.error(error); process.exitCode = 1; });
