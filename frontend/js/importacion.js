const BASE_URL_IMPORTACION = `${window.location.protocol}//${window.location.hostname}:8000`;

let configuracionesImportacion = [];
let ultimoAnalisis = null;
let ultimaValidacionCierre = null;
let cierreEnEjecucion = false;
let cargaEnEjecucion = false;
let mostrarCoincidentes = false;
let filtroPreviewEstado = "TODOS";
let previewVisible = false;
let analisisConfirmado = false;
let progresoConfirmacionTimer = null;

document.addEventListener("DOMContentLoaded", () => {
    if (!exigirSesion()) return;

    const periodo = document.getElementById("periodoImportacion");
    if (periodo && !periodo.value) periodo.value = codmesActual();
    const periodoCierre = document.getElementById("periodoCierreImportacion");
    if (periodoCierre && !periodoCierre.value) periodoCierre.value = codmesActual();

    document.getElementById("formImportacion")?.addEventListener("submit", analizarImportacion);
    document.getElementById("formCierreHistorico")?.addEventListener("submit", validarCierreHistorico);
    document.getElementById("archivoImportacion")?.addEventListener("change", actualizarNombreArchivoImportacion);

    cargarConfiguracionesImportacion();
    cargarLotesImportacion(false);
});

function cambiarTabImportacion(tab) {
    document.querySelectorAll(".import-tabs button").forEach(btn => {
        btn.classList.toggle("active", btn.dataset.tab === tab);
    });
    document.querySelectorAll(".tab-panel").forEach(panel => {
        panel.classList.toggle("active", panel.id === `tab-${tab}`);
    });
    if (tab === "historial") cargarLotesImportacion(false);
}

async function cargarConfiguracionesImportacion() {
    const select = document.getElementById("configImportacion");
    const selectCierre = document.getElementById("configCierreImportacion");
    try {
        const res = await fetch(`${BASE_URL_IMPORTACION}/importacion/configuraciones`, { cache: "no-store" });
        const json = await res.json();
        if (!res.ok) throw new Error(json.detail || "No se pudieron cargar configuraciones.");

        configuracionesImportacion = json.data || [];
        const opciones = `<option value="">Seleccionar configuracion</option>` + configuracionesImportacion.map(item => `
            <option value="${item.id_config}">
                ${h(item.cartera || "Cartera")} - ${h(item.producto || "Producto")} | ${h(item.tabla_destino || "-")}
            </option>
        `).join("");
        if (select) select.innerHTML = opciones;
        if (selectCierre) selectCierre.innerHTML = opciones;
    } catch (error) {
        if (select) select.innerHTML = `<option value="">Error cargando configuraciones</option>`;
        if (selectCierre) selectCierre.innerHTML = `<option value="">Error cargando configuraciones</option>`;
        toastImportacion(error.message, "error");
    }
}

async function analizarImportacion(event) {
    event.preventDefault();

    const idConfig = document.getElementById("configImportacion").value;
    const periodo = document.getElementById("periodoImportacion").value.trim();
    const tipoCarga = document.getElementById("tipoCargaImportacion").value;
    const archivo = document.getElementById("archivoImportacion").files[0];

    if (!idConfig || !periodo || !tipoCarga || !archivo) {
        toastImportacion("Selecciona configuracion, periodo, tipo de carga y archivo.", "error");
        return;
    }
    if (!/^\d{6}$/.test(periodo)) {
        toastImportacion("El periodo debe tener formato YYYYMM.", "error");
        return;
    }

    const formData = new FormData();
    formData.set("id_config", idConfig);
    formData.set("periodo", periodo);
    formData.set("tipo_carga", tipoCarga);
    formData.set("archivo", archivo);

    const btn = document.getElementById("btnAnalizarImportacion");
    try {
        btn.disabled = true;
        btn.textContent = "Analizando...";

        const res = await fetch(`${BASE_URL_IMPORTACION}/importacion/analizar`, {
            method: "POST",
            body: formData
        });
        const json = await res.json();
        if (!res.ok) throw new Error(json.detail || "No se pudo analizar el archivo.");

        ultimoAnalisis = json;
        mostrarCoincidentes = false;
        filtroPreviewEstado = "TODOS";
        previewVisible = false;
        analisisConfirmado = false;
        renderAnalisisImportacion(json);
        toastImportacion("Archivo analizado correctamente.", "ok");
    } catch (error) {
        toastImportacion(error.message, "error");
    } finally {
        btn.disabled = false;
        btn.textContent = "Analizar archivo";
    }
}

function renderAnalisisImportacion(data) {
    document.getElementById("resultadoAnalisis").classList.remove("hidden");

    const kpis = [
        ["Total filas", numero(data.total_filas)],
        ["Columnas archivo", numero(data.total_columnas_archivo)],
        ["Coincidentes", numero(data.columnas_coincidentes?.length || 0), "ok"],
        ["Generadas", numero(data.columnas_generadas?.length || 0), "info"],
        ["Nuevas", numero(data.columnas_nuevas_en_archivo?.length || 0), "info"],
        ["Faltantes", numero(data.columnas_faltantes_en_archivo?.length || 0), "warn"],
        ["Errores bloqueantes", numero(data.errores_bloqueantes?.length || 0), (data.errores_bloqueantes || []).length ? "bad" : "ok"]
    ];

    document.getElementById("kpisAnalisis").innerHTML = kpis.map(([label, value, tone]) => `
        <article class="kpi-card ${tone || ""}">
            <span>${label}</span>
            <strong>${value}</strong>
        </article>
    `).join("");

    renderColumnasAnalisis(data);
    renderAlertasAnalisis(data.alertas || []);
    renderImpactoImportacion(data.impacto || {});
    renderDiagnosticoCruce(data.diagnostico_cruce || {});
    actualizarEstadoPreview();
    renderAccionesConfirmacionCarga(data);
}

function renderImpactoImportacion(impacto) {
    const kpis = [
        ["Nuevos", impacto.registros_nuevos || 0, "ok"],
        ["Existentes", impacto.registros_existentes || 0, "info"],
        ["Duplicados archivo", impacto.duplicados_archivo || 0, impacto.duplicados_archivo ? "warn" : "ok"],
        ["Clave incompleta", impacto.clave_incompleta || 0, impacto.clave_incompleta ? "bad" : "ok"],
        ["A insertar", impacto.registros_a_insertar || 0, "ok"],
        ["A actualizar", impacto.registros_a_actualizar || 0, "info"]
    ];

    document.getElementById("kpisImpacto").innerHTML = kpis.map(([label, value, tone]) => `
        <article class="impact-kpi ${tone}">
            <span>${label}</span>
            <strong>${numero(value)}</strong>
        </article>
    `).join("");
}

function renderDiagnosticoCruce(debug) {
    const panel = document.getElementById("diagnosticoCruce");
    if (!panel) return;

    if (!debug || !Object.keys(debug).length) {
        panel.innerHTML = "";
        return;
    }

    console.group("Diagnostico cruce importacion");
    console.table({
        id_config_usado: debug.id_config_usado,
        tabla_destino_usada: debug.tabla_destino_usada,
        clave_cruce_usada: debug.clave_cruce_usada,
        tabla_actual_es_mensual: debug.tabla_actual_es_mensual,
        campo_periodo_actual: debug.campo_periodo_actual,
        filtro_periodo_aplicado: debug.filtro_periodo_aplicado,
        total_claves_archivo: debug.total_claves_archivo,
        total_claves_destino_leidas: debug.total_claves_destino_leidas,
        total_coincidencias: debug.total_coincidencias
    });
    console.log("Query destino:", debug.query_destino_debug);
    console.table(debug.preview_claves_archivo || []);
    console.table(debug.preview_claves_destino || []);
    console.groupEnd();

    panel.innerHTML = `
        <details>
            <summary>Diagnostico de cruce</summary>
            <div class="debug-grid">
                ${debugItem("ID config", debug.id_config_usado)}
                ${debugItem("Tabla destino", debug.tabla_destino_usada)}
                ${debugItem("Clave cruce", debug.clave_cruce_usada)}
                ${debugItem("Tabla mensual activa", debug.tabla_actual_es_mensual ? "si" : "no")}
                ${debugItem("Campo periodo", debug.campo_periodo_actual || "-")}
                ${debugItem("Filtro periodo", debug.filtro_periodo_aplicado)}
                ${debugItem("Claves archivo", numero(debug.total_claves_archivo))}
                ${debugItem("Claves destino", numero(debug.total_claves_destino_leidas))}
                ${debugItem("Coincidencias", numero(debug.total_coincidencias))}
            </div>
            <pre>${h(debug.query_destino_debug || "-")}</pre>
            <div class="debug-preview">
                <div>
                    <h4>Archivo</h4>
                    <pre>${h(JSON.stringify(debug.preview_claves_archivo || [], null, 2))}</pre>
                </div>
                <div>
                    <h4>Destino</h4>
                    <pre>${h(JSON.stringify(debug.preview_claves_destino || [], null, 2))}</pre>
                </div>
            </div>
        </details>
    `;
}

function debugItem(label, value) {
    return `<div><span>${h(label)}</span><strong>${h(valorVacio(value))}</strong></div>`;
}

function renderColumnasAnalisis(data) {
    const problemas = normalizarFilasColumnas(data.columnas_problema || []);
    const coincidentes = normalizarFilasColumnas(data.columnas_coincidentes || []);
    const filas = mostrarCoincidentes ? [...problemas, ...coincidentes] : problemas;

    const btn = document.getElementById("btnCoincidentes");
    if (btn) {
        btn.textContent = mostrarCoincidentes ? "Ocultar columnas coincidentes" : "Ver columnas coincidentes";
    }

    document.getElementById("tablaColumnasAnalisis").innerHTML = filas.length
        ? filas.map(row => `
            <tr>
                <td>${h(row.columna)}</td>
                <td><span class="badge ${tipoBadge(row.tipo, row.estado)}">${h(row.estado)}</span></td>
                <td>${h(row.observacion)}</td>
            </tr>
        `).join("")
        : `<tr><td colspan="3" class="empty-row">No hay columnas con problemas. Usa "Ver columnas coincidentes" para revisar las correctas.</td></tr>`;
}

function renderAlertasAnalisis(alertas) {
    const grupos = [
        ["error", "Errores", alertas.filter(a => ["error", "bad"].includes(a.tipo))],
        ["advertencia", "Advertencias", alertas.filter(a => a.tipo === "advertencia" || a.tipo === "warn")],
        ["info", "Info", alertas.filter(a => ["info", "ok"].includes(a.tipo))]
    ];

    document.getElementById("alertasAnalisis").innerHTML = grupos.map(([tipo, titulo, items]) => `
        <section class="alert-group">
            <h4>${titulo}</h4>
            ${items.length ? items.map(alerta => `
                <div class="alert-item ${h(alerta.tipo || tipo)}">
                    <span>${h(alerta.mensaje || "-")}</span>
                </div>
            `).join("") : `<div class="alert-item muted"><span>Sin ${titulo.toLowerCase()}.</span></div>`}
        </section>
    `).join("");
}

function toggleCoincidentesImportacion() {
    mostrarCoincidentes = !mostrarCoincidentes;
    if (ultimoAnalisis) renderColumnasAnalisis(ultimoAnalisis);
}

function normalizarFilasColumnas(rows) {
    return rows.map(row => {
        if (typeof row === "string") {
            return {
                columna: row,
                estado: "COINCIDENTE",
                tipo: "ok",
                observacion: "Existe en el archivo y en la tabla destino."
            };
        }
        return {
            columna: row.columna || row.column_name || "-",
            estado: row.estado || "-",
            tipo: row.tipo || tipoPorEstado(row.estado),
            observacion: row.observacion || row.obs || "-"
        };
    });
}

function tipoBadge(tipo, estado) {
    const normalizado = String(tipo || tipoPorEstado(estado)).toLowerCase();
    if (normalizado === "error") return "bad";
    if (normalizado === "advertencia") return "warn";
    return normalizado;
}

function tipoPorEstado(estado) {
    const texto = String(estado || "").toUpperCase();
    if (texto.includes("CLAVE")) return "error";
    if (texto.includes("FALTANTE")) return "advertencia";
    if (texto.includes("GENERADA")) return "info";
    if (texto.includes("NUEVA")) return "info";
    return "ok";
}

function renderPreviewAnalisis(rows) {
    const table = document.getElementById("tablaPreviewAnalisis");
    const filtradasBase = filtroPreviewEstado === "TODOS"
        ? rows
        : rows.filter(row => row.estado_carga === filtroPreviewEstado);
    const filtradas = filtradasBase.slice(0, 20);

    document.querySelectorAll("#filtrosPreview button").forEach(btn => {
        btn.classList.toggle("active", btn.dataset.estado === filtroPreviewEstado);
    });

    if (!filtradas.length) {
        table.innerHTML = `<tbody><tr><td class="empty-row">El archivo no contiene filas para previsualizar.</td></tr></tbody>`;
        return;
    }

    const columnas = Object.keys(filtradas[0]).filter(col => col !== "estado_carga");
    table.innerHTML = `
        <thead>
            <tr>
                <th>Estado carga</th>
                ${columnas.map(col => `<th>${h(col)}</th>`).join("")}
            </tr>
        </thead>
        <tbody>
            ${filtradas.map(row => `
                <tr>
                    <td><span class="badge ${badgeEstadoCarga(row.estado_carga)}">${h(row.estado_carga || "-")}</span></td>
                    ${columnas.map(col => `<td>${h(valorVacio(row[col]))}</td>`).join("")}
                </tr>
            `).join("")}
        </tbody>
    `;
}

function filtrarPreviewImportacion(estado) {
    filtroPreviewEstado = estado;
    if (ultimoAnalisis && previewVisible) renderPreviewAnalisis(ultimoAnalisis.preview || []);
    actualizarEstadoPreview();
}

function togglePreviewImportacion() {
    previewVisible = !previewVisible;
    if (previewVisible && ultimoAnalisis) {
        renderPreviewAnalisis(ultimoAnalisis.preview || []);
    }
    actualizarEstadoPreview();
}

function actualizarEstadoPreview() {
    const card = document.getElementById("previewAnalisisCard");
    const btn = document.getElementById("btnTogglePreview");
    const table = document.getElementById("tablaPreviewAnalisis");

    if (card) card.classList.toggle("hidden", !previewVisible);
    if (btn) btn.textContent = previewVisible ? "Ocultar preview" : "Ver preview de datos";
    if (!previewVisible && table) table.innerHTML = "";
}

function badgeEstadoCarga(estado) {
    switch (estado) {
        case "NUEVO": return "ok";
        case "EXISTENTE": return "info";
        case "DUPLICADO_ARCHIVO": return "warn";
        case "CLAVE_INCOMPLETA": return "bad";
        default: return "info";
    }
}

async function cargarLotesImportacion(mostrarMensaje = true) {
    try {
        const res = await fetch(`${BASE_URL_IMPORTACION}/importacion/lotes`, { cache: "no-store" });
        const json = await res.json();
        if (!res.ok) throw new Error(json.detail || "No se pudo cargar historial.");
        renderLotesImportacion(json.data || []);
        if (mostrarMensaje) toastImportacion("Historial actualizado.", "ok");
    } catch (error) {
        toastImportacion(error.message, "error");
    }
}

function renderLotesImportacion(lotes) {
    document.getElementById("tablaLotesImportacion").innerHTML = lotes.length
        ? lotes.map(item => `
            <tr>
                <td>${h(item.id_lote)}</td>
                <td>${h(item.cartera || "-")}</td>
                <td>${h(item.producto || "-")}</td>
                <td>${h(item.periodo || "-")}</td>
                <td>${h(item.tipo_proceso || "-")}</td>
                <td class="archivo">${h(item.archivo_nombre || "-")}</td>
                <td>${numero(item.total_filas)}</td>
                <td class="ok-text">${numero(item.insertados)}</td>
                <td>${numero(item.actualizados)}</td>
                <td class="bad-text">${numero(item.rechazados)}</td>
                <td><span class="badge info">${h(item.estado || "-")}</span></td>
                <td>${fechaHora(item.fecha_inicio)}</td>
                <td>${fechaHora(item.fecha_fin)}</td>
                <td class="archivo">${h(item.observacion || "-")}</td>
            </tr>
        `).join("")
        : `<tr><td colspan="14" class="empty-row">No hay lotes registrados.</td></tr>`;
}

function renderAccionesConfirmacionCarga(data) {
    const panel = document.getElementById("panelConfirmarCarga");
    const mensaje = document.getElementById("mensajeConfirmarCarga");
    const btn = document.getElementById("btnConfirmarCarga");
    if (!panel || !mensaje || !btn) return;

    const errores = data.errores_bloqueantes || [];
    const tipoCarga = document.getElementById("tipoCargaImportacion")?.value || data.tipo_carga || "";
    const tipoNormalizado = normalizarTipoCargaImportacion(tipoCarga);
    const tipoPermitido = ["AGREGAR_ACTUALIZAR", "CARGA_INICIAL_MENSUAL"].includes(tipoNormalizado);
    panel.classList.remove("hidden");
    document.getElementById("resultadoConfirmacionCarga")?.classList.add("hidden");

    if (analisisConfirmado) {
        panel.classList.add("hidden");
        btn.disabled = true;
        mensaje.innerHTML = `<div class="load-message info">Para volver a cargar, analiza nuevamente el archivo.</div>`;
        return;
    }

    if (errores.length) {
        btn.disabled = true;
        mensaje.innerHTML = `<div class="load-message bad">Corrige los errores bloqueantes antes de confirmar la carga.</div>`;
        return;
    }
    if (!tipoPermitido) {
        btn.disabled = true;
        mensaje.innerHTML = `<div class="load-message warn">Por seguridad, este tipo de carga aun no esta implementado.</div>`;
        return;
    }

    btn.disabled = false;
    if (tipoNormalizado === "CARGA_INICIAL_MENSUAL") {
        mensaje.innerHTML = `
            <div class="load-message warn">
                Se reemplazara la cartera activa actual de esta configuracion y se insertaran ${numero(data.total_filas || 0)} filas del archivo.
            </div>
        `;
    } else {
        mensaje.innerHTML = `
            <div class="load-message info">
                Se preparan ${numero(data.impacto?.registros_a_insertar || 0)} registros para insertar y
                ${numero(data.impacto?.registros_a_actualizar || 0)} para actualizar.
            </div>
        `;
    }
}

function abrirConfirmacionCarga() {
    if (analisisConfirmado) {
        toastImportacion("Para volver a cargar, analiza nuevamente el archivo.", "info");
        return;
    }
    if (!ultimoAnalisis) {
        toastImportacion("Primero analiza el archivo.", "error");
        return;
    }
    if ((ultimoAnalisis.errores_bloqueantes || []).length) {
        toastImportacion("Existen errores bloqueantes.", "error");
        return;
    }
    const archivo = document.getElementById("archivoImportacion")?.files?.[0];
    if (!archivo) {
        toastImportacion("El archivo ya no esta seleccionado. Vuelve a seleccionarlo.", "error");
        return;
    }

    const modal = document.getElementById("modalConfirmacionCarga");
    const detalle = document.getElementById("detalleModalConfirmacionCarga");
    const aceptar = document.getElementById("btnAceptarConfirmacionCarga");
    const cancelar = document.getElementById("btnCancelarConfirmacionCarga");
    if (!modal || !detalle || !aceptar || !cancelar) {
        toastImportacion("No se pudo abrir la confirmacion visual.", "error");
        return;
    }

    const impacto = ultimoAnalisis.impacto || {};
    const tipoCarga = normalizarTipoCargaImportacion(document.getElementById("tipoCargaImportacion")?.value || ultimoAnalisis.tipo_carga);
    const esCargaInicial = tipoCarga === "CARGA_INICIAL_MENSUAL";
    detalle.innerHTML = `
        <div><span>Cartera</span><strong>${h(ultimoAnalisis.cartera || "-")}</strong></div>
        <div><span>Producto</span><strong>${h(ultimoAnalisis.producto || "-")}</strong></div>
        <div><span>Periodo</span><strong>${h(ultimoAnalisis.periodo || "-")}</strong></div>
        <div><span>Tipo carga</span><strong>${esCargaInicial ? "Reemplazar cartera activa del mes" : "Agregar + actualizar"}</strong></div>
        <div><span>Tabla destino</span><strong>${h(ultimoAnalisis.tabla_destino || "-")}</strong></div>
        <div><span>A insertar</span><strong>${numero(esCargaInicial ? ultimoAnalisis.total_filas : impacto.registros_a_insertar)}</strong></div>
        <div><span>A actualizar</span><strong>${numero(esCargaInicial ? 0 : impacto.registros_a_actualizar)}</strong></div>
        <div><span>Rechazados previos</span><strong>${numero((impacto.duplicados_archivo || 0) + (impacto.clave_incompleta || 0))}</strong></div>
        <div><span>Generadas</span><strong>${h((ultimoAnalisis.columnas_generadas || []).map(x => x.columna || x).join(", ") || "-")}</strong></div>
        <div><span>Omitidas</span><strong>${numero(ultimoAnalisis.columnas_nuevas_en_archivo?.length || 0)} columnas nuevas</strong></div>
        <div><span>Faltantes no criticas</span><strong>${numero(ultimoAnalisis.columnas_faltantes_en_archivo?.length || 0)}</strong></div>
        ${esCargaInicial ? `<div class="danger-note"><span>Accion</span><strong>Se eliminara la tabla activa actual antes de insertar el archivo.</strong></div>` : ""}
    `;

    const cerrar = () => {
        modal.classList.add("hidden");
        modal.setAttribute("aria-hidden", "true");
        aceptar.onclick = null;
        cancelar.onclick = null;
        modal.onclick = null;
        document.removeEventListener("keydown", onKeydown);
    };
    const onKeydown = event => {
        if (event.key === "Escape") cerrar();
    };
    aceptar.onclick = async () => {
        cerrar();
        await confirmarCargaImportacion();
    };
    cancelar.onclick = cerrar;
    modal.onclick = event => {
        if (event.target === modal) cerrar();
    };
    document.addEventListener("keydown", onKeydown);
    modal.classList.remove("hidden");
    modal.setAttribute("aria-hidden", "false");
    cancelar.focus();
}

async function confirmarCargaImportacion() {
    if (cargaEnEjecucion) return;
    const archivo = document.getElementById("archivoImportacion")?.files?.[0];
    if (!ultimoAnalisis || !archivo) {
        toastImportacion("Primero analiza y conserva seleccionado el archivo.", "error");
        return;
    }

    const formData = new FormData();
    formData.set("id_config", ultimoAnalisis.id_config);
    formData.set("periodo", ultimoAnalisis.periodo);
    formData.set("tipo_carga", normalizarTipoCargaImportacion(ultimoAnalisis.tipo_carga || document.getElementById("tipoCargaImportacion")?.value));
    formData.set("usuario", usuarioActualImportacion());
    formData.set("hoja_usada", ultimoAnalisis.hoja_usada || "");
    formData.set("archivo", archivo);

    const btn = document.getElementById("btnConfirmarCarga");
    const mensaje = document.getElementById("mensajeConfirmarCarga");
    const totalInsertar = ultimoAnalisis.impacto?.registros_a_insertar || 0;
    const totalActualizar = ultimoAnalisis.impacto?.registros_a_actualizar || 0;
    const inicioConfirmacion = Date.now();
    try {
        cargaEnEjecucion = true;
        if (btn) {
            btn.disabled = true;
            btn.textContent = "Confirmando...";
        }
        iniciarProgresoConfirmacion({
            mensaje,
            inicio: inicioConfirmacion,
            totalInsertar,
            totalActualizar,
            periodo: ultimoAnalisis.periodo,
            cartera: ultimoAnalisis.cartera,
        });
        const res = await fetch(`${BASE_URL_IMPORTACION}/importacion/confirmar`, {
            method: "POST",
            body: formData
        });
        const json = await res.json();
        console.log("Resultado confirmar", json);

        analisisConfirmado = true;
        ultimoAnalisis = null;
        renderResultadoConfirmacionCarga(json);
        await cargarLotesImportacion(false);
        toastImportacion(
            json.ok === false ? "La carga termino con observaciones o error." : "Carga confirmada correctamente.",
            json.ok === false ? "error" : "ok"
        );
    } catch (error) {
        analisisConfirmado = true;
        ultimoAnalisis = null;
        renderResultadoConfirmacionCarga({
            ok: false,
            id_lote: "-",
            estado: "ERROR",
            insertados: 0,
            actualizados: 0,
            rechazados: 0,
            periodo: ultimoAnalisis?.periodo || "-",
            tabla_destino: ultimoAnalisis?.tabla_destino || "-",
            observacion: error.message || "No se pudo confirmar la carga."
        });
        toastImportacion(error.message, "error");
    } finally {
        detenerProgresoConfirmacion();
        cargaEnEjecucion = false;
        if (btn) {
            btn.disabled = true;
            btn.textContent = "Confirmar carga";
        }
    }
}

function iniciarProgresoConfirmacion({ mensaje, inicio, totalInsertar, totalActualizar, periodo, cartera }) {
    detenerProgresoConfirmacion();
    const render = async () => {
        const segundos = Math.max(1, Math.round((Date.now() - inicio) / 1000));
        const textoTiempo = segundos < 60
            ? `${segundos}s`
            : `${Math.floor(segundos / 60)}m ${String(segundos % 60).padStart(2, "0")}s`;
        let detalleLote = "";

        try {
            const res = await fetch(`${BASE_URL_IMPORTACION}/importacion/lotes?limit=5`, { cache: "no-store" });
            const json = await res.json();
            const lote = (json.data || []).find(item =>
                String(item.periodo || "") === String(periodo || "") &&
                (!cartera || String(item.cartera || "").toUpperCase() === String(cartera || "").toUpperCase()) &&
                ["EN_PROCESO", "PROCESANDO"].includes(String(item.estado || "").toUpperCase())
            );
            if (lote) {
                detalleLote = ` Lote ${h(lote.id_lote)} en proceso desde ${h(fechaHora(lote.fecha_inicio))}.`;
            }
        } catch (_) {
            detalleLote = "";
        }

        if (mensaje) {
            mensaje.innerHTML = `
                <div class="load-message info">
                    Confirmando carga... tiempo transcurrido ${h(textoTiempo)}.
                    Se procesan ${numero(totalInsertar)} registros para insertar y ${numero(totalActualizar)} para actualizar.
                    ${detalleLote || "La carga sigue ejecutandose en segundo plano."}
                </div>
            `;
        }
    };

    render();
    progresoConfirmacionTimer = setInterval(render, 5000);
}

function detenerProgresoConfirmacion() {
    if (progresoConfirmacionTimer) {
        clearInterval(progresoConfirmacionTimer);
        progresoConfirmacionTimer = null;
    }
}

function renderResultadoConfirmacionCarga(data) {
    const panelConfirmar = document.getElementById("panelConfirmarCarga");
    panelConfirmar?.classList.add("hidden", "confirmacion-finalizada");
    const panel = document.getElementById("resultadoConfirmacionCarga");
    const detalle = document.getElementById("detalleConfirmacionCarga");
    panel?.classList.remove("hidden");
    panel?.classList.remove("load-ok", "load-warn", "load-bad");
    panel?.classList.add(claseResultadoCarga(data.estado));
    if (!detalle) return;

    const filas = [
        ["ID lote", data.id_lote || "-"],
        ["Estado", data.estado || "-"],
        ["Insertados", numero(data.insertados)],
        ["Actualizados", numero(data.actualizados)],
        ["Rechazados", numero(data.rechazados)],
        ["Activos reemplazados", numero(data.total_registros_reemplazados || 0)],
        ["Periodo", data.periodo || "-"],
        ["Tabla destino", data.tabla_destino || "-"],
        ["Omitidas", numero(data.columnas_omitidas?.length || 0)],
        ["Generadas", (data.columnas_generadas || []).join(", ") || "-"]
    ];
    const tiempos = data.tiempos || data.debug?.tiempos || {};
    const tiemposHtml = Object.keys(tiempos).length ? `
        <div class="load-timings">
            <h4>Tiempos del proceso</h4>
            ${Object.entries(tiempos).map(([label, value]) => `
                <div>
                    <span>${h(etiquetaTiempoCarga(label))}</span>
                    <strong>${h(formatoSegundos(value))}</strong>
                </div>
            `).join("")}
        </div>
    ` : "";
    const errores = data.errores_preview || data.motivo_rechazo_primeras_10 || [];
    const erroresHtml = errores.length ? `
        <div class="load-errors">
            <h4>Primeras causas de error</h4>
            ${errores.slice(0, 10).map(item => `
                <div>
                    <strong>Fila ${h(item.fila_excel || "-")} - ${h(item.columna || "-")}</strong>
                    <span>${h(item.valor || "")}</span>
                    <p>${h(item.error || "-")}</p>
                </div>
            `).join("")}
        </div>
    ` : "";

    detalle.innerHTML = filas.map(([label, value]) => `
        <div class="cierre-item ${claseItemResultadoCarga(data.estado)}">
            <span>${h(label)}</span>
            <strong>${h(value)}</strong>
        </div>
    `).join("") + `
        <div class="load-final-message">
            <strong>${h(data.observacion || "Resultado final del lote.")}</strong>
            <span>Para volver a cargar, analiza nuevamente el archivo.</span>
            <button class="btn-secondary" type="button" onclick="nuevoAnalisisImportacion()">Nuevo analisis</button>
        </div>
        ${tiemposHtml}
        ${erroresHtml}
    `;

    const btn = document.getElementById("btnConfirmarCarga");
    if (btn) btn.disabled = true;
    const mensaje = document.getElementById("mensajeConfirmarCarga");
    if (mensaje) {
        mensaje.innerHTML = `<div class="load-message info">Para volver a cargar, analiza nuevamente el archivo.</div>`;
    }
    const archivo = document.getElementById("archivoImportacion");
    if (archivo) archivo.value = "";
    actualizarNombreArchivoImportacion();
    panel?.scrollIntoView({ behavior: "smooth", block: "start" });
}

function etiquetaTiempoCarga(label) {
    const etiquetas = {
        lectura_excel: "Lectura Excel",
        clasificacion: "Clasificacion",
        crear_lote: "Crear lote",
        limpiar_destino: "Limpiar destino",
        preparar_staging: "Preparar staging",
        cargar_staging: "Cargar staging",
        insertar_destino: "Insertar destino",
        procesar_filas: "Procesar filas",
        total: "Total"
    };
    return etiquetas[label] || label.replaceAll("_", " ");
}

function formatoSegundos(value) {
    const numeroValor = Number(value || 0);
    if (!Number.isFinite(numeroValor)) return "-";
    if (numeroValor >= 60) {
        const minutos = Math.floor(numeroValor / 60);
        const segundos = Math.round(numeroValor % 60);
        return `${minutos}m ${segundos}s`;
    }
    return `${numeroValor.toFixed(2)}s`;
}

function claseResultadoCarga(estado) {
    const value = String(estado || "").toUpperCase();
    if (value === "CARGADO") return "load-ok";
    if (value === "OBSERVADO") return "load-warn";
    return "load-bad";
}

function claseItemResultadoCarga(estado) {
    const value = String(estado || "").toUpperCase();
    if (value === "CARGADO") return "ok";
    if (value === "OBSERVADO") return "warn";
    return "bad";
}

function nuevoAnalisisImportacion() {
    limpiarAnalisisImportacion();
    document.getElementById("configImportacion")?.focus();
}

async function validarCierreHistorico(event) {
    event.preventDefault();

    const idConfig = document.getElementById("configCierreImportacion").value;
    const periodo = document.getElementById("periodoCierreImportacion").value.trim();
    if (!idConfig || !periodo) {
        toastImportacion("Selecciona configuracion y periodo de cierre.", "error");
        return;
    }
    if (!/^\d{6}$/.test(periodo)) {
        toastImportacion("El periodo debe tener formato YYYYMM.", "error");
        return;
    }

    const formData = new FormData();
    formData.set("id_config", idConfig);
    formData.set("periodo", periodo);

    const btn = document.getElementById("btnValidarCierre");
    try {
        btn.disabled = true;
        btn.textContent = "Validando...";
        const res = await fetch(`${BASE_URL_IMPORTACION}/importacion/cierre/validar`, {
            method: "POST",
            body: formData
        });
        const json = await res.json();
        if (!res.ok) throw new Error(json.detail || "No se pudo validar el cierre.");

        ultimaValidacionCierre = json;
        renderValidacionCierre(json);
        document.getElementById("resultadoEjecucionCierre")?.classList.add("hidden");
        toastImportacion("Cierre validado.", json.puede_cerrar ? "ok" : "info");
    } catch (error) {
        toastImportacion(error.message, "error");
    } finally {
        btn.disabled = false;
        btn.textContent = "Validar cierre";
    }
}

function renderValidacionCierre(data) {
    document.getElementById("resultadoCierre").classList.remove("hidden");
    const resumen = [
        ["Cartera", data.cartera || "-"],
        ["Producto", data.producto || "-"],
        ["Periodo", data.periodo || "-"],
        ["Periodo historico", data.periodo_convertido || "-"],
        ["Tabla origen", data.tabla_origen || "-"],
        ["Tabla historica", data.tabla_historica || "-"],
        ["Tipo cierre", data.tipo_estructura_historico || "-"],
        ["Campo periodo historico", data.campo_periodo_historico || "-"],
        ["Total origen", numero(data.total_origen)],
        ["Existente previo", numero(data.total_existente_previo)],
        ["Puede cerrar", data.puede_cerrar ? "Si" : "No"]
    ];

    document.getElementById("resumenCierre").innerHTML = resumen.map(([label, value]) => `
        <div class="cierre-item">
            <span>${h(label)}</span>
            <strong>${h(value)}</strong>
        </div>
    `).join("");

    document.getElementById("alertasCierre").innerHTML = (data.alertas || []).map(alerta => `
        <div class="alert-item ${h(alerta.tipo || "info")}">
            <span>${h(alerta.mensaje || "-")}</span>
        </div>
    `).join("");

    renderAccionesCierre(data);
}

function renderAccionesCierre(data) {
    const contenedor = document.getElementById("accionesCierre");
    if (!contenedor) return;

    if (!data.puede_cerrar) {
        contenedor.innerHTML = `<button class="btn-secondary" type="button" onclick="limpiarCierreHistorico()">Cancelar</button>`;
        return;
    }

    const hayPrevio = Number(data.total_existente_previo || 0) > 0;
    contenedor.innerHTML = `
        <button class="btn-secondary" type="button" onclick="limpiarCierreHistorico()">Cancelar</button>
        ${hayPrevio ? `
            <div class="replace-warning">
                Ya existe data del periodo. Solo se reemplazara ese periodo historico, no la tabla activa.
            </div>
            <button class="btn-danger" type="button" onclick="ejecutarCierreHistorico('REEMPLAZAR_PERIODO')">
                Reemplazar periodo historico
            </button>
        ` : `
            <button class="btn-primary" type="button" onclick="ejecutarCierreHistorico('INSERTAR_SI_NO_EXISTE')">
                Ejecutar cierre
            </button>
        `}
    `;
}

async function ejecutarCierreHistorico(modo) {
    if (cierreEnEjecucion) return;
    if (!ultimaValidacionCierre) {
        toastImportacion("Primero valida el cierre.", "error");
        return;
    }

    const confirmado = await confirmarCierreHistorico(modo, ultimaValidacionCierre);
    if (!confirmado) return;

    const formData = new FormData();
    formData.set("id_config", ultimaValidacionCierre.id_config);
    formData.set("periodo", ultimaValidacionCierre.periodo);
    formData.set("usuario", usuarioActualImportacion());
    formData.set("modo", modo);

    try {
        cierreEnEjecucion = true;
        bloquearAccionesCierre(true);
        const res = await fetch(`${BASE_URL_IMPORTACION}/importacion/cierre/ejecutar`, {
            method: "POST",
            body: formData
        });
        const json = await res.json();
        if (!res.ok) throw new Error(json.detail || "No se pudo ejecutar el cierre.");

        renderEjecucionCierre(json);
        marcarCierreEjecutado();
        toastImportacion("Cierre historico ejecutado correctamente.", "ok");
    } catch (error) {
        toastImportacion(error.message, "error");
        bloquearAccionesCierre(false);
    } finally {
        cierreEnEjecucion = false;
    }
}

function renderEjecucionCierre(data) {
    document.getElementById("resultadoEjecucionCierre").classList.remove("hidden");
    const filas = [
        ["ID cierre", data.id_cierre || "-"],
        ["Estado", data.estado || "-"],
        ["Insertados", numero(data.insertados)],
        ["Periodo", data.periodo || "-"],
        ["Tabla historica", data.tabla_historica || "-"],
        ["Fecha", fechaHora(data.fecha)]
    ];
    document.getElementById("detalleEjecucionCierre").innerHTML = filas.map(([label, value]) => `
        <div class="cierre-item ok">
            <span>${h(label)}</span>
            <strong>${h(value)}</strong>
        </div>
    `).join("");
}

function bloquearAccionesCierre(bloqueado) {
    document.querySelectorAll("#accionesCierre button").forEach(btn => {
        btn.disabled = bloqueado;
        if (bloqueado && btn.classList.contains("btn-primary")) btn.textContent = "Ejecutando...";
        if (bloqueado && btn.classList.contains("btn-danger")) btn.textContent = "Reemplazando...";
    });
}

function marcarCierreEjecutado() {
    const acciones = document.getElementById("accionesCierre");
    if (acciones) {
        acciones.innerHTML = `
            <div class="closure-done">
                Cierre ejecutado. Para repetir el proceso, valida nuevamente el periodo.
            </div>
            <button class="btn-secondary" type="button" onclick="reiniciarValidacionCierre()">Validar nuevamente</button>
        `;
    }
    ultimaValidacionCierre = null;
}

function reiniciarValidacionCierre() {
    limpiarCierreHistorico();
    document.getElementById("formCierreHistorico")?.requestSubmit();
}

function limpiarCierreHistorico() {
    ultimaValidacionCierre = null;
    cierreEnEjecucion = false;
    document.getElementById("resultadoCierre")?.classList.add("hidden");
    document.getElementById("resultadoEjecucionCierre")?.classList.add("hidden");
}

function usuarioActualImportacion() {
    return localStorage.getItem("dni")
        || localStorage.getItem("agente")
        || localStorage.getItem("usuario")
        || "SIN_USUARIO";
}

function normalizarTipoCargaImportacion(value) {
    const texto = String(value || "").trim().toUpperCase().replace(/\s+/g, "_");
    if (texto.includes("CARGA_INICIAL") || texto.includes("REEMPLAZAR_CARTERA_ACTIVA")) {
        return "CARGA_INICIAL_MENSUAL";
    }
    if (texto.includes("AGREGAR") && texto.includes("ACTUALIZAR")) {
        return "AGREGAR_ACTUALIZAR";
    }
    return texto;
}

function confirmarCierreHistorico(modo, data) {
    return new Promise(resolve => {
        const modal = document.getElementById("modalConfirmacionCierre");
        const titulo = document.getElementById("tituloConfirmacionCierre");
        const mensaje = document.getElementById("mensajeConfirmacionCierre");
        const detalle = document.getElementById("detalleConfirmacionCierre");
        const icono = document.getElementById("iconoConfirmacionCierre");
        const aceptar = document.getElementById("btnAceptarConfirmacionCierre");
        const cancelar = document.getElementById("btnCancelarConfirmacionCierre");

        if (!modal || !titulo || !mensaje || !detalle || !aceptar || !cancelar) {
            toastImportacion("No se pudo abrir la confirmacion visual. Recarga la pagina.", "error");
            resolve(false);
            return;
        }

        const reemplaza = modo === "REEMPLAZAR_PERIODO";
        titulo.textContent = reemplaza ? "Reemplazar periodo historico" : "Ejecutar cierre historico";
        mensaje.textContent = reemplaza
            ? "Se eliminara solo el periodo historico seleccionado y se insertara nuevamente la tabla activa consolidada."
            : "Se copiara la tabla activa consolidada hacia el historico oficial del periodo.";
        icono.textContent = reemplaza ? "!" : "i";
        icono.className = `confirm-icon ${reemplaza ? "warn" : "info"}`;
        aceptar.textContent = reemplaza ? "Reemplazar periodo" : "Ejecutar cierre";
        aceptar.className = reemplaza ? "btn-danger" : "btn-primary";
        detalle.innerHTML = `
            <div><span>Periodo</span><strong>${h(data.periodo || "-")}</strong></div>
            <div><span>Origen</span><strong>${h(data.tabla_origen || "-")}</strong></div>
            <div><span>Historico</span><strong>${h(data.tabla_historica || "-")}</strong></div>
            <div><span>Total origen</span><strong>${numero(data.total_origen)}</strong></div>
            <div><span>Existente previo</span><strong>${numero(data.total_existente_previo)}</strong></div>
        `;

        const cerrar = value => {
            modal.classList.add("hidden");
            modal.setAttribute("aria-hidden", "true");
            aceptar.onclick = null;
            cancelar.onclick = null;
            modal.onclick = null;
            document.removeEventListener("keydown", onKeydown);
            resolve(value);
        };
        const onKeydown = event => {
            if (event.key === "Escape") cerrar(false);
        };

        aceptar.onclick = () => cerrar(true);
        cancelar.onclick = () => cerrar(false);
        modal.onclick = event => {
            if (event.target === modal) cerrar(false);
        };
        document.addEventListener("keydown", onKeydown);
        modal.classList.remove("hidden");
        modal.setAttribute("aria-hidden", "false");
        cancelar.focus();
    });
}

function limpiarAnalisisImportacion() {
    ultimoAnalisis = null;
    cargaEnEjecucion = false;
    analisisConfirmado = false;
    mostrarCoincidentes = false;
    filtroPreviewEstado = "TODOS";
    previewVisible = false;
    document.getElementById("formImportacion")?.reset();
    document.getElementById("periodoImportacion").value = codmesActual();
    document.getElementById("nombreArchivoImportacion").textContent = "Ningun archivo seleccionado";
    document.getElementById("resultadoAnalisis").classList.add("hidden");
    document.getElementById("panelConfirmarCarga")?.classList.add("hidden");
    document.getElementById("resultadoConfirmacionCarga")?.classList.add("hidden");
    const detalleConfirmacion = document.getElementById("detalleConfirmacionCarga");
    if (detalleConfirmacion) detalleConfirmacion.innerHTML = "";
    const mensajeConfirmacion = document.getElementById("mensajeConfirmarCarga");
    if (mensajeConfirmacion) mensajeConfirmacion.innerHTML = "";
    actualizarEstadoPreview();
}

function actualizarNombreArchivoImportacion() {
    const archivo = document.getElementById("archivoImportacion").files[0];
    document.getElementById("nombreArchivoImportacion").textContent = archivo?.name || "Ningun archivo seleccionado";
}

function codmesActual() {
    const hoy = new Date();
    return `${hoy.getFullYear()}${String(hoy.getMonth() + 1).padStart(2, "0")}`;
}

function toastImportacion(mensaje, tipo = "info") {
    const toast = document.getElementById("toastImportacion");
    if (!toast) return;
    toast.textContent = mensaje;
    toast.className = `import-toast visible ${tipo}`;
    window.clearTimeout(toast._timer);
    toast._timer = window.setTimeout(() => {
        toast.className = "import-toast";
    }, 3500);
}

function numero(value) {
    return Number(value || 0).toLocaleString("es-PE");
}

function fechaHora(value) {
    if (!value) return "-";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return String(value);
    return date.toLocaleString("es-PE", { dateStyle: "short", timeStyle: "short" });
}

function valorVacio(value) {
    return value === null || value === undefined || value === "" ? "-" : value;
}

function h(value) {
    return String(value ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}
