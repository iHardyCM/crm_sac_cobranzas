const BASE_URL_PAUTAS = `${window.location.protocol}//${window.location.hostname}:8000`;

let pautasEvaluacion = [];
let carterasPauta = [];
let pautaActual = null;
let bloqueSeleccionadoPauta = 0;
let criterioSeleccionadoPauta = 0;

document.addEventListener("DOMContentLoaded", () => {
    if (!exigirSesion()) return;
    if (!puedeVerCorporativo()) {
        alert("No tienes acceso a configuración de pautas.");
        irInicio();
        return;
    }
    cargarPautasEvaluacion();
});

async function fetchPautas(path, options = {}) {
    const response = await fetch(`${BASE_URL_PAUTAS}${path}`, {
        cache: "no-store",
        ...options,
        headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || `HTTP ${response.status}`);
    return data;
}

async function cargarPautasEvaluacion() {
    try {
        mostrarToastPauta("Cargando pautas...", "info");
        const [pautas, carteras] = await Promise.all([
            fetchPautas("/admin-pautas-evaluacion/pautas"),
            fetchPautas("/admin-pautas-evaluacion/carteras"),
        ]);
        pautasEvaluacion = pautas.data || [];
        carterasPauta = carteras.data || [];
        pintarListaPautas();
        mostrarToastPauta("Pautas actualizadas.", "ok");
    } catch (error) {
        console.error(error);
        mostrarToastPauta(`No se pudo cargar la configuración. ${error.message || ""}`, "error");
    }
}

function pintarListaPautas() {
    const el = document.getElementById("listaPautas");
    if (!pautasEvaluacion.length) {
        el.innerHTML = `<div class="pauta-empty"><strong>Aún no hay pautas guardadas.</strong><span>Crea una pauta y publícala cuando esté validada.</span></div>`;
        return;
    }
    const actual = Number(document.getElementById("idPauta")?.value || 0);
    el.innerHTML = pautasEvaluacion.map(item => `
        <button class="pauta-list-item ${Number(item.id_pauta) === actual ? "active" : ""}" type="button" onclick="abrirPautaEvaluacion(${Number(item.id_pauta)})">
            <strong>${esc(item.nombre)}</strong>
            <small>Versión ${esc(item.version)} · ${esc(item.cantidad_criterios)} criterios · ${formatoPeso(item.peso_total)} pts</small>
            <span class="status ${esc(item.estado)}">${esc(textoEstadoPauta(item.estado))}</span>
        </button>
    `).join("");
}

async function abrirPautaEvaluacion(idPauta) {
    try {
        const respuesta = await fetchPautas(`/admin-pautas-evaluacion/pautas/${idPauta}`);
        cargarEditorPauta(respuesta.data);
    } catch (error) {
        mostrarToastPauta(`No se pudo abrir la pauta. ${error.message || ""}`, "error");
    }
}

function nuevaPautaEvaluacion() {
    cargarEditorPauta({
        estado: "BORRADOR", aplica_todas: false, bloques: [], idcarteras: [], version: null,
        nombre: "", descripcion: "", vigencia_desde: null, vigencia_hasta: null,
    });
}

async function usarPlantillaGeneral() {
    try {
        const respuesta = await fetchPautas("/admin-pautas-evaluacion/plantillas/general");
        cargarEditorPauta(respuesta.data);
        mostrarToastPauta("Plantilla general cargada como borrador. Define el alcance antes de guardarla.", "info");
    } catch (error) {
        mostrarToastPauta(error.message || "No se pudo cargar la plantilla general.", "error");
    }
}

function cargarEditorPauta(pauta) {
    pautaActual = normalizarPautaCliente(pauta);
    bloqueSeleccionadoPauta = 0;
    criterioSeleccionadoPauta = 0;
    document.getElementById("pautaEmpty").classList.add("oculto");
    document.getElementById("formPauta").classList.remove("oculto");
    document.getElementById("idPauta").value = pautaActual.id_pauta || "";
    document.getElementById("pautaNombre").value = pautaActual.nombre || "";
    document.getElementById("pautaDescripcion").value = pautaActual.descripcion || "";
    document.getElementById("pautaVigenciaDesde").value = fechaInput(pautaActual.vigencia_desde);
    document.getElementById("pautaVigenciaHasta").value = fechaInput(pautaActual.vigencia_hasta);
    document.getElementById("pautaTodasCarteras").checked = Boolean(pautaActual.aplica_todas);
    document.getElementById("pautaGrupoNombre").value = pautaActual.grupo_nombre || "";
    document.getElementById("pautaEditorTitulo").textContent = pautaActual.nombre || "Nueva pauta";
    document.getElementById("pautaVersionLabel").textContent = pautaActual.id_pauta
        ? `${textoEstadoPauta(pautaActual.estado)} · VERSIÓN ${pautaActual.version}`
        : "BORRADOR NUEVO";
    pintarCarterasPauta();
    pintarBloquesPauta();
    aplicarEstadoEditorPauta();
    actualizarResumenPauta();
    pintarListaPautas();
}

function normalizarPautaCliente(pauta) {
    return {
        ...pauta,
        estado: pauta.estado || "BORRADOR",
        idcarteras: (pauta.idcarteras || []).map(Number),
        bloques: (pauta.bloques || []).map((bloque, indice) => ({
            ...bloque,
            activo: bloque.activo !== false,
            orden: bloque.orden || indice + 1,
            criterios: (bloque.criterios || []).map((criterio, orden) => ({
                ...criterio,
                activo: criterio.activo !== false,
                orden: criterio.orden || orden + 1,
                tipo_criterio: criterio.tipo_criterio || "PUNTUABLE",
            })),
        })),
    };
}

function pautaEsEditable() {
    return String(pautaActual?.estado || "BORRADOR") === "BORRADOR";
}

function aplicarEstadoEditorPauta() {
    const editable = pautaEsEditable();
    document.querySelectorAll("#formPauta input, #formPauta textarea, #formPauta select").forEach(el => {
        if (el.id !== "idPauta") el.disabled = !editable;
    });
    document.getElementById("btnGuardarPauta").disabled = !editable;
    document.getElementById("btnPublicarPauta").disabled = !editable;
    document.getElementById("btnDuplicarPauta").disabled = !pautaActual?.id_pauta;
    document.getElementById("btnArchivarPauta").disabled = !pautaActual?.id_pauta || pautaActual?.estado === "ARCHIVADA";
}

function pintarCarterasPauta() {
    const seleccionadas = new Set((pautaActual.idcarteras || []).map(String));
    const contenedor = document.getElementById("pautaCarteras");
    contenedor.innerHTML = carterasPauta.map(item => `
        <label class="cartera-check">
            <input type="checkbox" value="${esc(item.idcartera)}" ${seleccionadas.has(String(item.idcartera)) ? "checked" : ""}>
            <span>${esc(item.idcartera)} - ${esc(item.cartera)}</span>
        </label>
    `).join("");
    alternarAlcancePauta();
}

function alternarAlcancePauta() {
    const todas = document.getElementById("pautaTodasCarteras").checked;
    document.querySelectorAll("#pautaCarteras input").forEach(input => { input.disabled = todas || !pautaEsEditable(); });
    document.getElementById("pautaGrupoNombre").disabled = todas || !pautaEsEditable();
}

function pintarBloquesPauta() {
    const contenedor = document.getElementById("bloquesPauta");
    if (!pautaActual.bloques.length) {
        contenedor.innerHTML = `<div class="pauta-empty"><strong>Sin bloques.</strong><span>Agrega el primer bloque de evaluación.</span></div>`;
        return;
    }
    if (bloqueSeleccionadoPauta >= pautaActual.bloques.length) bloqueSeleccionadoPauta = pautaActual.bloques.length - 1;
    const bloque = pautaActual.bloques[bloqueSeleccionadoPauta];
    const bloqueIndex = bloqueSeleccionadoPauta;
    if (criterioSeleccionadoPauta >= bloque.criterios.length) criterioSeleccionadoPauta = Math.max(0, bloque.criterios.length - 1);
    const criterio = bloque.criterios[criterioSeleccionadoPauta];
    contenedor.innerHTML = `
        <div class="bloques-selector" role="tablist" aria-label="Bloques de la pauta">
            ${pautaActual.bloques.map((item, indice) => {
                const peso = pesoBloquePauta(item);
                return `<button class="bloque-selector-item ${indice === bloqueSeleccionadoPauta ? "active" : ""}" type="button" role="tab" aria-selected="${indice === bloqueSeleccionadoPauta}" onclick="seleccionarBloquePauta(${indice})">
                    <strong>${esc(item.codigo || `B${indice + 1}`)}</strong>
                    <span>${esc(item.nombre || "Bloque sin nombre")}</span>
                    <small>${item.criterios?.length || 0} criterios · ${formatoPeso(peso)} pts</small>
                </button>`;
            }).join("")}
        </div>
        <div class="bloque-contexto">
            <div>
                <strong>${esc(bloque.codigo || "Bloque")} · ${esc(bloque.nombre || "Sin nombre")}</strong>
                <span>Bloque seleccionado para edición</span>
            </div>
            <div class="bloque-metricas" aria-label="Resumen del bloque seleccionado">
                <span>${bloque.criterios?.length || 0} criterios</span>
                <span>${formatoPeso(pesoBloquePauta(bloque))} pts</span>
                <span>${(bloque.criterios || []).filter(item => item.activo !== false).length} activos</span>
                <span>${esc(textoEstadoPauta(pautaActual.estado))}</span>
            </div>
        </div>
        <article class="bloque-pauta" data-bloque-index="${bloqueIndex}">
            <div class="bloque-head">
                <input data-field="codigo" value="${esc(bloque.codigo || "")}" placeholder="Código bloque">
                <input data-field="nombre" value="${esc(bloque.nombre || "")}" placeholder="Nombre del bloque">
                <input data-field="categoria" value="${esc(bloque.categoria || "")}" placeholder="Categoría">
                <button class="mini-btn danger" type="button" onclick="eliminarBloquePauta(${bloqueIndex})">Quitar bloque</button>
            </div>
            <label class="bloque-descripcion-field">
                <span>Propósito del bloque</span>
                <textarea class="bloque-descripcion" data-field="descripcion" rows="2" placeholder="Describe qué comportamiento o riesgo evalúa este bloque.">${esc(bloque.descripcion || "")}</textarea>
                <small>Esta descripción orienta la configuración y la lectura de los criterios del bloque.</small>
            </label>
            <div class="criterios-workbench">
                <section class="criterios-tabla-wrap">
                    <div class="criterios-tabla-head"><strong>Criterios del bloque ${esc(bloque.codigo || "")}</strong><button class="mini-btn add-criterion" type="button" onclick="agregarCriterioPauta(${bloqueIndex})">Agregar criterio</button></div>
                    <div class="criterios-tabla-scroll">
                        <table class="criterios-tabla"><thead><tr><th></th><th>Código y nombre</th><th>Tipo</th><th>Peso</th><th>Fuente</th><th>Criticidad</th><th>Estado</th><th></th></tr></thead>
                        <tbody>${(bloque.criterios || []).map((item, indice) => pintarFilaCriterioPauta(item, bloqueIndex, indice)).join("") || '<tr><td colspan="8" class="criterio-vacio">Aún no hay criterios en este bloque.</td></tr>'}</tbody></table>
                    </div>
                </section>
                <aside class="criterio-editor-panel">
                    ${criterio ? pintarCriterioPauta(criterio, bloqueIndex, criterioSeleccionadoPauta) : '<div class="criterio-vacio">Selecciona o agrega un criterio para editarlo.</div>'}
                </aside>
            </div>
        </article>`;
    aplicarEstadoEditorPauta();
}

function seleccionarBloquePauta(indice) {
    sincronizarBloquesDesdeDom();
    bloqueSeleccionadoPauta = Number(indice) || 0;
    criterioSeleccionadoPauta = 0;
    pintarBloquesPauta();
    actualizarResumenPauta();
}

function pesoBloquePauta(bloque = {}) {
    return (bloque.criterios || []).reduce((total, criterio) => (
        total + (criterio.activo !== false && criterio.tipo_criterio === "PUNTUABLE" ? Number(criterio.peso || 0) : 0)
    ), 0);
}

function pintarCriterioPauta(criterio, bloqueIndex, criterioIndex) {
    const anulante = String(criterio.tipo_criterio || "") === "ANULANTE_BLOQUE";
    return `
        <section class="criterio-editor" data-criterio-index="${criterioIndex}">
            <div class="criterio-editor-title"><strong>Editar criterio seleccionado</strong><span>${esc(criterio.codigo_criterio || "Nuevo criterio")}</span></div>
            <div class="criterio-grid">
                <div class="criterio-field"><label>Código</label><input data-field="codigo_criterio" value="${esc(criterio.codigo_criterio || "")}" placeholder="Ej.: EC-UF.1"></div>
                <div class="criterio-field"><label>Nombre</label><input data-field="nombre" value="${esc(criterio.nombre || "")}" placeholder="Nombre del criterio"></div>
                <div class="criterio-field"><label>Tipo</label><select data-field="tipo_criterio" onchange="refrescarTipoCriterioPauta()"><option value="PUNTUABLE" ${!anulante ? "selected" : ""}>Puntuable</option><option value="ANULANTE_BLOQUE" ${anulante ? "selected" : ""}>Anulante de bloque</option></select></div>
                <div class="criterio-field"><label>Peso</label><input data-field="peso" type="number" min="0" step="0.01" value="${esc(criterio.peso ?? 0)}" ${anulante ? "disabled" : ""}></div>
                <div class="criterio-field"><label>Fuente evidencia</label><select data-field="fuente_evidencia">${opcionesFuente(criterio.fuente_evidencia)}</select></div>
            </div>
            <div class="criterio-grid-detail criterio-principal">
                <div class="criterio-field"><label>Cuándo cumple</label><textarea data-field="regla_cumple" rows="2">${esc(criterio.regla_cumple || "")}</textarea></div>
                <div class="criterio-field"><label>Cuándo no cumple</label><textarea data-field="regla_no_cumple" rows="2">${esc(criterio.regla_no_cumple || "")}</textarea></div>
                <div class="criterio-field"><label>Aplicabilidad / No aplica</label><textarea data-field="regla_aplicabilidad" rows="2">${esc(criterio.regla_aplicabilidad || "")}</textarea></div>
                <div class="criterio-field"><label>Criticidad</label><select data-field="criticidad">${opcionesCriticidad(criterio.criticidad)}</select></div>
            </div>
            <details class="criterio-avanzado"><summary>Más reglas y recomendaciones</summary><div class="criterio-grid-detail"><div class="criterio-field"><label>Detalle</label><textarea data-field="detalle" rows="2">${esc(criterio.detalle || "")}</textarea></div><div class="criterio-field"><label>Regla de evaluación</label><textarea data-field="regla_evaluacion" rows="2" placeholder="Qué debe analizar la IA">${esc(criterio.regla_evaluacion || "")}</textarea></div><div class="criterio-field"><label>Recomendación sugerida</label><textarea data-field="recomendacion" rows="2">${esc(criterio.recomendacion || "")}</textarea></div></div></details>
            <div class="criterio-checks">
                <label><input data-field="requiere_evidencia" type="checkbox" ${criterio.requiere_evidencia ? "checked" : ""}> Evidencia obligatoria</label>
                <label><input data-field="puede_descalificar" type="checkbox" ${criterio.puede_descalificar ? "checked" : ""}> Puede descalificar</label>
                <label><input data-field="activo" type="checkbox" ${criterio.activo !== false ? "checked" : ""}> Activo</label>
            </div>
            <div class="criterio-actions"><button class="mini-btn danger" type="button" onclick="eliminarCriterioPauta(${bloqueIndex}, ${criterioIndex})">Quitar criterio</button></div>
        </section>`;
}

function pintarFilaCriterioPauta(criterio, bloqueIndex, criterioIndex) {
    const seleccionado = criterioIndex === criterioSeleccionadoPauta;
    const tipo = criterio.tipo_criterio === "ANULANTE_BLOQUE" ? "Anulante" : "Puntuable";
    return `<tr class="${seleccionado ? "selected" : ""}">
        <td><input type="radio" name="criterioSeleccionado" ${seleccionado ? "checked" : ""} onchange="seleccionarCriterioPauta(${criterioIndex})" aria-label="Seleccionar ${esc(criterio.codigo_criterio || "criterio")}"></td>
        <td><strong>${esc(criterio.codigo_criterio || "-")}</strong><span>${esc(criterio.nombre || "Sin nombre")}</span></td>
        <td><span class="tag-table">${tipo}</span></td><td>${formatoPeso(criterio.peso)} pts</td><td>${esc(criterio.fuente_evidencia || "-")}</td><td><span class="tag-table ${String(criterio.criticidad || "").includes("NO_CRITICO") ? "neutral" : "critical"}">${esc(textoCriticidadPauta(criterio.criticidad))}</span></td><td><span class="tag-table ${criterio.activo !== false ? "active" : "inactive"}">${criterio.activo !== false ? "Activo" : "Inactivo"}</span></td>
        <td><button class="mini-btn" type="button" onclick="seleccionarCriterioPauta(${criterioIndex})">Editar</button></td>
    </tr>`;
}

function seleccionarCriterioPauta(indice) {
    sincronizarBloquesDesdeDom();
    criterioSeleccionadoPauta = Number(indice) || 0;
    pintarBloquesPauta();
}

function opcionesFuente(actual) {
    const fuentes = ["AUDIO", "TRANSCRIPCION", "CRM", "TIPIFICACION", "CAMPANIA", "SISTEMA", "MULTIFUENTE"];
    return fuentes.map(valor => `<option value="${valor}" ${valor === (actual || "TRANSCRIPCION") ? "selected" : ""}>${valor}</option>`).join("");
}

function opcionesCriticidad(actual) {
    const opciones = ["ERROR_NO_CRITICO", "ERROR_CRITICO_NEGOCIO", "ERROR_CRITICO_USUARIO_FINAL", "ERROR_CRITICO_CUMPLIMIENTO"];
    return opciones.map(valor => `<option value="${valor}" ${valor === actual ? "selected" : ""}>${valor.replaceAll("_", " ")}</option>`).join("");
}

function textoCriticidadPauta(valor) {
    return String(valor || "Sin definir").replace("ERROR_CRITICO_", "Crítico ").replace("ERROR_", "").replaceAll("_", " ");
}

function sincronizarBloquesDesdeDom() {
    if (!pautaActual) return [];
    document.querySelectorAll("#bloquesPauta .bloque-pauta").forEach(bloqueEl => {
        const indiceBloque = Number(bloqueEl.dataset.bloqueIndex || 0);
        const valor = campo => bloqueEl.querySelector(`:scope > .bloque-head [data-field="${campo}"], :scope > [data-field="${campo}"]`)?.value?.trim() || "";
        const bloque = { ...pautaActual.bloques[indiceBloque], codigo: valor("codigo"), nombre: valor("nombre"), categoria: valor("categoria"), descripcion: valor("descripcion"), orden: indiceBloque + 1, activo: true, criterios: [...(pautaActual.bloques[indiceBloque].criterios || [])] };
        const criterioEl = bloqueEl.querySelector(".criterio-editor");
        if (criterioEl) {
            const indiceCriterio = Number(criterioEl.dataset.criterioIndex || 0);
            const obtener = campo => criterioEl.querySelector(`[data-field="${campo}"]`);
            const tipo = obtener("tipo_criterio")?.value || "PUNTUABLE";
            bloque.criterios[indiceCriterio] = {
                codigo_criterio: obtener("codigo_criterio")?.value?.trim() || "",
                nombre: obtener("nombre")?.value?.trim() || "",
                tipo_criterio: tipo,
                peso: tipo === "ANULANTE_BLOQUE" ? 0 : Number(obtener("peso")?.value || 0),
                detalle: obtener("detalle")?.value?.trim() || "",
                regla_evaluacion: obtener("regla_evaluacion")?.value?.trim() || "",
                regla_cumple: obtener("regla_cumple")?.value?.trim() || "",
                regla_no_cumple: obtener("regla_no_cumple")?.value?.trim() || "",
                regla_aplicabilidad: obtener("regla_aplicabilidad")?.value?.trim() || "",
                criticidad: obtener("criticidad")?.value || "",
                fuente_evidencia: obtener("fuente_evidencia")?.value || "TRANSCRIPCION",
                requiere_evidencia: Boolean(obtener("requiere_evidencia")?.checked),
                puede_descalificar: Boolean(obtener("puede_descalificar")?.checked),
                recomendacion: obtener("recomendacion")?.value?.trim() || "",
                activo: Boolean(obtener("activo")?.checked), orden: indiceCriterio + 1,
            };
        }
        pautaActual.bloques[indiceBloque] = bloque;
    });
    return pautaActual.bloques;
}

function agregarBloquePauta() {
    sincronizarBloquesDesdeDom();
    pautaActual.bloques.push({ codigo: "", nombre: "", categoria: "", descripcion: "", activo: true, criterios: [] });
    bloqueSeleccionadoPauta = pautaActual.bloques.length - 1;
    criterioSeleccionadoPauta = 0;
    pintarBloquesPauta();
}

function eliminarBloquePauta(indice) {
    sincronizarBloquesDesdeDom();
    pautaActual.bloques.splice(indice, 1);
    bloqueSeleccionadoPauta = Math.max(0, Math.min(bloqueSeleccionadoPauta, pautaActual.bloques.length - 1));
    pintarBloquesPauta();
    actualizarResumenPauta();
}

function agregarCriterioPauta(indiceBloque) {
    sincronizarBloquesDesdeDom();
    pautaActual.bloques[indiceBloque].criterios.push({ tipo_criterio: "PUNTUABLE", fuente_evidencia: "TRANSCRIPCION", activo: true, peso: 0, requiere_evidencia: false, puede_descalificar: false });
    criterioSeleccionadoPauta = pautaActual.bloques[indiceBloque].criterios.length - 1;
    pintarBloquesPauta();
}

function eliminarCriterioPauta(indiceBloque, indiceCriterio) {
    sincronizarBloquesDesdeDom();
    pautaActual.bloques[indiceBloque].criterios.splice(indiceCriterio, 1);
    criterioSeleccionadoPauta = Math.max(0, Math.min(criterioSeleccionadoPauta, pautaActual.bloques[indiceBloque].criterios.length - 1));
    pintarBloquesPauta();
    actualizarResumenPauta();
}

function refrescarTipoCriterioPauta() {
    sincronizarBloquesDesdeDom();
    pintarBloquesPauta();
    actualizarResumenPauta();
}

function leerPautaFormulario() {
    sincronizarBloquesDesdeDom();
    return {
        id_pauta: Number(document.getElementById("idPauta").value) || null,
        nombre: document.getElementById("pautaNombre").value.trim(),
        descripcion: document.getElementById("pautaDescripcion").value.trim(),
        aplica_todas: document.getElementById("pautaTodasCarteras").checked,
        idcarteras: [...document.querySelectorAll("#pautaCarteras input:checked")].map(input => Number(input.value)),
        grupo_nombre: document.getElementById("pautaGrupoNombre").value.trim(),
        vigencia_desde: document.getElementById("pautaVigenciaDesde").value || null,
        vigencia_hasta: document.getElementById("pautaVigenciaHasta").value || null,
        bloques: pautaActual.bloques,
        usuario_actualizacion: localStorage.getItem("dni") || localStorage.getItem("usuario") || "SIN_USUARIO",
    };
}

function actualizarResumenPauta() {
    if (!pautaActual) return;
    sincronizarBloquesDesdeDom();
    const peso = pautaActual.bloques.flatMap(b => b.criterios || []).reduce((suma, criterio) => (
        suma + (criterio.activo !== false && criterio.tipo_criterio === "PUNTUABLE" ? Number(criterio.peso || 0) : 0)
    ), 0);
    document.getElementById("pesoPauta").textContent = `Peso puntuable: ${formatoPeso(peso)} / 100`;
    document.getElementById("estadoValidacionPauta").textContent = Number(peso.toFixed(2)) === 100
        ? "Peso completo. Valida las reglas antes de publicar."
        : "El peso puntuable debe sumar 100 para publicar.";
}

async function validarPautaActual() {
    try {
        const respuesta = await fetchPautas("/admin-pautas-evaluacion/validar", { method: "POST", body: JSON.stringify(leerPautaFormulario()) });
        actualizarResumenPauta();
        mostrarToastPauta(respuesta.ok ? "Borrador válido. Ya puedes guardar o publicar." : respuesta.errores.join(" "), respuesta.ok ? "ok" : "error");
    } catch (error) { mostrarToastPauta(error.message || "No se pudo validar.", "error"); }
}

async function guardarPautaActual() {
    try {
        const respuesta = await fetchPautas("/admin-pautas-evaluacion/pautas", { method: "POST", body: JSON.stringify(leerPautaFormulario()) });
        cargarEditorPauta(respuesta.pauta);
        await cargarPautasEvaluacion();
        mostrarToastPauta("Borrador guardado.", "ok");
    } catch (error) { mostrarToastPauta(error.message || "No se pudo guardar.", "error"); }
}

async function publicarPautaActual() {
    if (!pautaActual?.id_pauta) { mostrarToastPauta("Guarda el borrador antes de publicarlo.", "error"); return; }
    try {
        const respuesta = await fetchPautas(`/admin-pautas-evaluacion/pautas/${pautaActual.id_pauta}/publicar`, {
            method: "POST", body: JSON.stringify({ usuario_actualizacion: localStorage.getItem("dni") || "SIN_USUARIO" }),
        });
        cargarEditorPauta(respuesta.pauta);
        await cargarPautasEvaluacion();
        mostrarToastPauta("Pauta publicada para el alcance seleccionado.", "ok");
    } catch (error) { mostrarToastPauta(error.message || "No se pudo publicar.", "error"); }
}

async function duplicarPautaActual() {
    if (!pautaActual?.id_pauta) return;
    try {
        const respuesta = await fetchPautas(`/admin-pautas-evaluacion/pautas/${pautaActual.id_pauta}/duplicar`, {
            method: "POST", body: JSON.stringify({ usuario_actualizacion: localStorage.getItem("dni") || "SIN_USUARIO" }),
        });
        cargarEditorPauta(respuesta.pauta);
        await cargarPautasEvaluacion();
        mostrarToastPauta("Nueva versión creada como borrador.", "ok");
    } catch (error) { mostrarToastPauta(error.message || "No se pudo duplicar.", "error"); }
}

async function archivarPautaActual() {
    if (!pautaActual?.id_pauta) return;
    if (!await crmConfirm({ title: "Archivar pauta", message: "La pauta dejará de usarse en nuevas evaluaciones. Las evaluaciones históricas no cambian.", acceptText: "Archivar", tone: "danger" })) return;
    try {
        await fetchPautas(`/admin-pautas-evaluacion/pautas/${pautaActual.id_pauta}/archivar`, { method: "POST", body: JSON.stringify({ usuario_actualizacion: localStorage.getItem("dni") || "SIN_USUARIO" }) });
        await abrirPautaEvaluacion(pautaActual.id_pauta);
        await cargarPautasEvaluacion();
        mostrarToastPauta("Pauta archivada.", "ok");
    } catch (error) { mostrarToastPauta(error.message || "No se pudo archivar.", "error"); }
}

function textoEstadoPauta(estado) { return ({ BORRADOR: "Borrador", PUBLICADA: "Publicada", ARCHIVADA: "Archivada" })[estado] || estado || "Borrador"; }
function formatoPeso(valor) { return Number(valor || 0).toFixed(2).replace(/\.00$/, ""); }
function fechaInput(valor) { return valor ? String(valor).slice(0, 10) : ""; }
function esc(valor) { return String(valor ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/\"/g, "&quot;").replace(/'/g, "&#039;"); }
function mostrarToastPauta(texto, tipo = "info") { const el = document.getElementById("pautasToast"); el.textContent = texto; el.className = `pautas-toast activo ${tipo}`; clearTimeout(window._pautasToastTimer); window._pautasToastTimer = setTimeout(() => el.classList.remove("activo"), 3800); }
