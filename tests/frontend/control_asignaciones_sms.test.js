const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

async function probarControl() {
    const elementos = new Map();
    function elemento(id) {
        if (!elementos.has(id)) elementos.set(id, {
            value: '', textContent: '', innerHTML: '', hidden: false, disabled: false,
            classList: {toggle() {}, add() {}}, removeAttribute() {},
            scrollIntoView() {}, close() { this.open = false; },
        });
        return elementos.get(id);
    }
    elemento('mowaControlCartera').value = '124';
    elemento('mowaTamano').value = '20';
    elemento('mowaOrden').value = 'antiguo';
    elemento('mowaEstado').value = 'PENDIENTE';
    elemento('mowaControlModal').open = true;
    const llamadas = [];
    const datos = {clientes: 2, respuestas: 3, sin_asignar: 1, asignados: 1,
        antiguos: 1, desde: '2026-11-01', completo: true, advertencias: [],
        agentes: [{usuario: '12345678', nombre: 'Agente de prueba', clientes: 1,
            respuestas: 2, antiguos: 1, primera_recepcion: '2026-11-18T10:00:00'}],
        sincronizacion: {fin: '2026-11-20T09:26:00', resultado: 'CON_AVISOS',
            desactualizada: true, ultimo_intento: {fin: '2026-11-25T08:00:00', resultado: 'ERROR'}},
    };
    const contexto = vm.createContext({
        window: {location: {protocol: 'http:', hostname: 'localhost'}},
        document: {addEventListener() {}, getElementById: elemento},
        fetchConSesion: async ruta => {
            llamadas.push(ruta);
            return {ok: true, json: async () => ruta.includes('agente=')
                ? {...datos, clientes_detalle: 1, respuestas_detalle: 1,
                    asignaciones: [], grupos: [{filas: [{idcartera: 124, idcliente: 2,
                        cliente: 'Cliente pendiente', dni: '12345678', telefono: '999999999',
                        cuenta: 'COMPARCARTIGO', campana_id: 10, id: '20',
                        recibido: '2026-11-25T09:00:00', estado: 'PENDIENTE', texto: 'Sí'}]}]}
                : datos};
        },
        URLSearchParams, Date,
    });
    vm.runInContext(fs.readFileSync(path.join(__dirname,
        '../../frontend/js/respuestas_mowa.js'), 'utf8'), contexto);
    vm.runInContext('mowaPuedeAsignar = true; mowaAlcanceCarteras = [124]', contexto);
    await contexto.cargarControlMowa();
    assert.match(llamadas[0], /control-asignaciones\?cartera=124$/);
    assert.equal(elemento('mowaControlTotal').textContent, '2');
    assert.equal(elemento('mowaControlSinAsignar').textContent, '1');
    assert.match(elemento('mowaControlAgentes').innerHTML, /Agente de prueba/);
    assert.match(elemento('mowaControlSync').textContent, /sin actualización reciente.*Último intento fallido/);
    await contexto.abrirDetalleControlMowa('SIN_ASIGNAR', false);
    assert.match(llamadas[1], /agente=SIN_ASIGNAR&cartera=124$/);
    assert.match(elemento('mowaTabla').innerHTML, /Cliente pendiente/);
    assert.equal(elemento('mowaControlModal').open, false);
    assert.match(elemento('mowaAlcance').textContent, /1 clientes/);
}

probarControl().then(() => console.log('Control de asignaciones SMS: OK'))
    .catch(error => { console.error(error); process.exitCode = 1; });
