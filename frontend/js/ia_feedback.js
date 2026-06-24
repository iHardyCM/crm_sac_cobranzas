const IA_FEEDBACK_BASE = obtenerBaseUrlIaFeedback();

let historialIa = [];
let resultadoActualIa = null;
let reporteriaActualIa = null;
let detalleReporteIa = [];
let detalleReportePaginaIa = 1;
let detalleReportePageSizeIa = 10;
let agenteSemanaPaginaIa = 1;
let agenteSemanaPageSizeIa = 8;
let agenteSemanaCarteraIa = "";
let agenteSemanaItemsIa = [];
let mensajeIaTimeout = null;
let iaAudioConfig = {
    formatos: ["MP3", "WAV", "M4A", "OGG"],
    extensiones: [".mp3", ".wav", ".m4a", ".ogg"],
    maxMb: 25,
};

document.addEventListener("DOMContentLoaded", () => {
    if (typeof exigirSesion === "function" && !exigirSesion()) return;

    prepararFormularioIa();
    prepararFiltrosReporteIa();
    prepararAccionesReporteIa();
    prepararAccionesAgenteSemanaIa();
    cargarConfigIa();
    cargarCarterasIa();
    cargarHistorialIa();
    activarVistaReporteriaIa({ scroll: false });
    cargarReporteriaIa();
    cargarPromptIa();
    inicializarCabeceraReporteIa();
});

function obtenerBaseUrlIaFeedback() {
    const host = window.location.hostname || "127.0.0.1";
    return `http://${host}:8000/ia-feedback`;
}

function prepararFormularioIa() {
    const form = document.getElementById("formIaFeedback");
    const audioInput = document.getElementById("audioIa");
    const nombreAudio = document.getElementById("nombreAudioIa");

    document.getElementById("supervisorIa")?.remove();
    setValue("fechaIa", fechaLocalActualIa());

    const comentario = document.getElementById("comentarioIa");
    if (comentario) {
        comentario.placeholder = "Ejemplo: revisar bajo COPC cobranza si hubo diagnostico, negociacion escalonada, cierre 3C y algun riesgo critico.";
    }

    audioInput.addEventListener("change", () => {
        const archivo = audioInput.files?.[0];
        nombreAudio.textContent = archivo?.name || "Ningun archivo seleccionado";
        if (archivo) validarArchivoAudioIa(archivo, { mostrarOk: true });
    });

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        await subirYAnalizarIa();
    });

    document.getElementById("formRevisionIa")?.addEventListener("submit", async (event) => {
        event.preventDefault();
        await guardarRevisionIa();
    });

    document.getElementById("formRecalibracionIa")?.addEventListener("submit", async (event) => {
        event.preventDefault();
        await enviarRecalibracionIa();
    });
}

async function subirYAnalizarIa() {
    const archivo = document.getElementById("audioIa").files?.[0];
    if (!archivo) {
        mostrarMensajeIa("Selecciona un audio para analizar.", "error");
        return;
    }

    if (!validarArchivoAudioIa(archivo)) return;

    if (!valorCarteraIa()) {
        mostrarMensajeIa("Selecciona una cartera para mantener la trazabilidad del analisis.", "error");
        return;
    }

    const btn = document.getElementById("btnAnalizarIa");
    btn.disabled = true;
    btn.textContent = "Procesando...";
    cambiarEstadoProceso("PENDIENTE");
    mostrarMensajeIa("Registrando audio para analisis...", "ok");

    try {
        const formData = new FormData();
        formData.append("archivo", archivo);
        formData.append("cartera", valorCarteraIa());
        formData.append("dni", valor("dniIa"));
        formData.append("telefono", valor("telefonoIa"));
        formData.append("fecha_llamada", valor("fechaIa"));
        formData.append("comentario_supervisor", valor("comentarioIa"));
        formData.append("supervisor", localStorage.getItem("agente") || localStorage.getItem("dni") || "SIN_USUARIO");

        const upload = await fetchIa(`${IA_FEEDBACK_BASE}/upload`, {
            method: "POST",
            body: formData,
        }, 120000);
        const uploadData = await leerJsonSeguro(upload);
        if (!upload.ok) throw new Error(uploadData.detail || uploadData.error || "No se pudo cargar el audio.");

        cambiarEstadoProceso("TRANSCRIBIENDO");
        mostrarMensajeIa("Audio registrado. Generando analisis con IA...", "ok");

        const analizar = await fetchIa(`${IA_FEEDBACK_BASE}/${uploadData.id_feedback}/analizar`, {
            method: "POST",
        }, 180000);
        const data = await leerJsonSeguro(analizar);
        if (!analizar.ok) throw new Error(data.detail || data.error || "No se pudo analizar la llamada.");

        cambiarEstadoProceso(data.estado || "FINALIZADO");
        renderResultadoIa(data);
        if (data.aviso_ia) {
            mostrarMensajeIa(`${data.aviso_ia}. Analisis generado correctamente.`, "ok");
        } else {
            mostrarMensajeIa("Analisis generado correctamente.", "ok");
        }
        limpiarFormularioBasicoIa({ limpiarCartera: true });
        await cargarHistorialIa();
    } catch (error) {
        cambiarEstadoProceso("ERROR");
        mostrarMensajeIa(error.message || "Error analizando llamada.", "error");
    } finally {
        btn.disabled = false;
        btn.textContent = "Analizar llamada con IA";
    }
}

async function cargarCarterasIa() {
    const select = document.getElementById("carteraIa");
    if (!select) return;

    const fallback = [
        { idcartera: 112, cartera: "Mibanco" },
        { idcartera: 117, cartera: "Interbank" },
        { idcartera: 132, cartera: "Financiera OH" },
        { idcartera: 148, cartera: "Financiera OH Propia" },
        { idcartera: 126, cartera: "Compartamos" },
        { idcartera: 128, cartera: "Compartamos" },
        { idcartera: 133, cartera: "Compartamos" },
        { idcartera: 124, cartera: "Compartamos Castigo" },
        { idcartera: 144, cartera: "Compartamos Castigo" },
    ];

    try {
        const response = await fetchIa(`${IA_FEEDBACK_BASE}/carteras`, {}, 12000);
        const data = await leerJsonSeguro(response);
        const carteras = response.ok && Array.isArray(data.data) ? data.data : fallback;
        pintarCarterasIa(carteras.length ? carteras : fallback);
    } catch {
        pintarCarterasIa(fallback);
    }
}

function pintarCarterasIa(carteras) {
    const select = document.getElementById("carteraIa");
    const carterasFiltradas = filtrarCarterasPorPerfil(carteras);
    const options = `<option value="">Seleccionar cartera</option>` + carterasFiltradas.map(item => {
        const nombre = item.cartera || item.nombre || "Cartera";
        const label = item.idcartera ? `${item.idcartera} - ${nombre}` : nombre;
        return `<option value="${escapeHtml(label)}">${escapeHtml(label)}</option>`;
    }).join("");
    if (select) select.innerHTML = options;

    if (select && carterasFiltradas.length === 1) {
        select.value = select.options[1]?.value || "";
    }

    const filtroCartera = document.getElementById("filtroCarteraIa");
    if (filtroCartera) {
        const valorActual = filtroCartera.value;
        filtroCartera.innerHTML = `<option value="">Todas</option>` + carterasFiltradas.map(item => {
            const nombre = item.cartera || item.nombre || "Cartera";
            const label = item.idcartera ? `${item.idcartera} - ${nombre}` : nombre;
            return `<option value="${escapeHtml(label)}">${escapeHtml(label)}</option>`;
        }).join("");
        filtroCartera.value = [...filtroCartera.options].some(option => option.value === valorActual) ? valorActual : "";
    }

    if (tipoUsuarioIa() === "SUPERVISOR" && !carterasFiltradas.length) {
        mostrarMensajeIa("No se encontraron carteras asignadas para tu usuario supervisor.", "error");
    }

    const promptSelect = document.getElementById("promptCarteraIa");
    if (promptSelect) {
        const valorActual = promptSelect.value;
        promptSelect.innerHTML = `<option value="">Prompt general</option>` + options.replace(`<option value="">Seleccionar cartera</option>`, "");
        promptSelect.value = [...promptSelect.options].some(option => option.value === valorActual) ? valorActual : "";
    }
}

async function cargarConfigIa() {
    try {
        const response = await fetchIa(`${IA_FEEDBACK_BASE}/config`, {}, 12000);
        const data = await leerJsonSeguro(response);
        if (!response.ok) return;

        iaAudioConfig.formatos = data.formatos_permitidos || iaAudioConfig.formatos;
        iaAudioConfig.extensiones = iaAudioConfig.formatos.map(x => `.${String(x).toLowerCase()}`);
        iaAudioConfig.maxMb = Number(data.max_audio_mb || iaAudioConfig.maxMb);

        const ayuda = document.getElementById("ayudaAudioIa");
        if (ayuda) {
            ayuda.textContent = `Formatos permitidos: ${iaAudioConfig.formatos.join(", ")}. Maximo ${iaAudioConfig.maxMb} MB.`;
        }
        actualizarModoIa(data);
    } catch {
        // La validacion backend sigue siendo la fuente final si no carga la configuracion.
    }
}

function actualizarModoIa(data) {
    const titulo = document.getElementById("modoIaTitulo");
    const detalle = document.getElementById("modoIaDetalle");
    if (!titulo || !detalle) return;

    if (data.ia_real_configurada) {
        titulo.textContent = "IA real activa";
        detalle.textContent = `${data.modelo_transcripcion || "Transcripcion"} + ${data.modelo_analisis || "Analisis"}`;
    } else {
        titulo.textContent = "Modo simulado";
        detalle.textContent = "Configura OPENAI_API_KEY para analizar audio real";
    }
}

function validarArchivoAudioIa(archivo, options = {}) {
    const extension = obtenerExtension(archivo.name);
    const maxBytes = iaAudioConfig.maxMb * 1024 * 1024;

    if (!iaAudioConfig.extensiones.includes(extension)) {
        mostrarMensajeIa(`Formato no permitido. Usa ${iaAudioConfig.formatos.join(", ")}.`, "error");
        return false;
    }

    if (archivo.size > maxBytes) {
        mostrarMensajeIa(`El archivo supera el tamano maximo permitido de ${iaAudioConfig.maxMb} MB.`, "error");
        return false;
    }

    if (options.mostrarOk) {
        const mb = (archivo.size / 1024 / 1024).toFixed(2);
        mostrarMensajeIa(`Audio listo para cargar (${extension.replace(".", "").toUpperCase()}, ${mb} MB).`, "ok");
    }

    return true;
}

function obtenerExtension(nombre) {
    const index = String(nombre || "").lastIndexOf(".");
    return index >= 0 ? String(nombre).slice(index).toLowerCase() : "";
}

function fechaLocalActualIa() {
    const ahora = new Date();
    ahora.setMinutes(ahora.getMinutes() - ahora.getTimezoneOffset());
    return ahora.toISOString().slice(0, 16);
}

function tipoUsuarioIa() {
    if (typeof normalizarTipoUsuario === "function") {
        return normalizarTipoUsuario(localStorage.getItem("tipo"));
    }
    return String(localStorage.getItem("tipo") || "").trim().toUpperCase();
}

function esPerfilGerencialIa() {
    if (typeof puedeVerCorporativo === "function") {
        return puedeVerCorporativo(localStorage.getItem("tipo"));
    }
    return ["ADMINISTRADOR", "JEFE DE CARTERA", "JEFE DE CARTERAS", "JEFE DE COBRANZA", "JEFE CARTERA"].includes(tipoUsuarioIa());
}

function idsCarterasSesionIa() {
    return [
        ...(localStorage.getItem("idcarteras") || "").split(","),
        localStorage.getItem("idcartera")
    ]
        .map(x => String(x || "").trim())
        .filter(Boolean)
        .filter((value, index, array) => array.indexOf(value) === index);
}

function filtrarCarterasPorPerfil(carteras) {
    if (esPerfilGerencialIa()) return carteras;
    if (tipoUsuarioIa() !== "SUPERVISOR") return carteras;

    const ids = idsCarterasSesionIa();
    if (!ids.length) return [];

    return carteras.filter(item => {
        const id = String(item.idcartera || "").trim();
        if (id) return ids.includes(id);
        const texto = String(item.cartera || item.nombre || "");
        return ids.some(idPermitido => texto.includes(idPermitido));
    });
}

async function cargarHistorialIa() {
    try {
        const params = new URLSearchParams({
            limit: "100",
            perfil: tipoUsuarioIa(),
            supervisor: localStorage.getItem("agente") || localStorage.getItem("dni") || ""
        });
        const response = await fetchIa(`${IA_FEEDBACK_BASE}/listar?${params.toString()}`, {}, 15000);
        const data = await leerJsonSeguro(response);
        if (!response.ok) throw new Error(data.detail || "No se pudo cargar el historial.");
        historialIa = data.data || [];
        renderHistorialIa();
        renderKpisIa();
    } catch (error) {
        mostrarMensajeIa(error.message || "Error cargando historial.", "error");
    }
}

async function verAnalisisIa(idFeedback) {
    try {
        const response = await fetchIa(`${IA_FEEDBACK_BASE}/${idFeedback}`, {}, 15000);
        const data = await leerJsonSeguro(response);
        if (!response.ok) throw new Error(data.detail || "No se pudo obtener el analisis.");
        cambiarEstadoProceso(data.estado || "PENDIENTE");
        renderResultadoIa(data);
        window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (error) {
        mostrarMensajeIa(error.message || "Error obteniendo detalle.", "error");
    }
}

function renderKpisIa() {
    const analizados = historialIa.filter(x => x.estado === "FINALIZADO").length;
    const pendientes = historialIa.filter(x => ["PENDIENTE", "TRANSCRIBIENDO", "ANALIZANDO"].includes(x.estado)).length;
    const criticos = historialIa.filter(x => Number(x.total_puntos_criticos || 0) > 0).length;
    const alta = historialIa.filter(x => String(x.nivel_oportunidad_mejora || "").toUpperCase() === "ALTA").length;

    setText("kpiAnalizados", formatoNumero(analizados));
    setText("kpiPendientes", formatoNumero(pendientes));
    setText("kpiCriticos", formatoNumero(criticos));
    setText("kpiAlta", formatoNumero(alta));
}

function renderHistorialIa() {
    const tbody = document.getElementById("historialIaBody");
    if (!historialIa.length) {
        tbody.innerHTML = `<tr><td colspan="10" class="empty-row">No hay audios registrados.</td></tr>`;
        return;
    }

    tbody.innerHTML = historialIa.map(row => `
        <tr>
            <td>${formatoFecha(row.fecha_creacion)}</td>
            <td>${escapeHtml(row.archivo_nombre || "-")}</td>
            <td>${escapeHtml(row.agente || "-")}</td>
            <td>${escapeHtml(row.cartera || "-")}</td>
            <td>${escapeHtml(row.resultado_gestion || "-")}</td>
            <td>${formatoNumero(row.total_puntos_criticos || 0)}</td>
            <td>${row.score_calidad != null ? `${Number(row.score_calidad).toFixed(1)}%` : escapeHtml(row.nivel_oportunidad_mejora || "-")}</td>
            <td>${badgeRevision(row.estado_revision)}</td>
            <td>${badgeEstado(row.estado)}</td>
            <td><button class="historial-action" type="button" onclick="verAnalisisIa(${row.id_feedback})">Ver analisis</button></td>
        </tr>
    `).join("");
}

function renderResultadoIa(data) {
    resultadoActualIa = data;
    activarVistaResultadoIa(true);
    document.getElementById("resultadoVacioIa").classList.add("oculto");
    document.getElementById("resultadoContenidoIa").classList.remove("oculto");

    setText("trazaAudioIa", data.archivo_nombre || "-");
    setText("trazaSupervisorIa", data.supervisor || "-");
    setText("trazaRevisionIa", data.estado_revision || "PENDIENTE");
    setText("resultadoNivelIa", data.nivel_oportunidad_mejora || "-");
    setText("resumenIa", data.resumen || "-");
    setText("tipoContactoIa", data.tipo_contacto || "-");
    setText("resultadoGestionIa", data.resultado_gestion || "-");
    setText("objecionIa", data.objecion_principal || "-");
    setText("scoreCalidadIa", data.score_calidad != null ? `${Number(data.score_calidad).toFixed(1)} / 100` : "-");
    setText("estadoRecalibracionIa", (data.estado_recalibracion || "SIN_APELACION").replace("_", " "));
    setText("recomendacionIa", data.recomendaciones || "-");
    setText("guionIa", data.guion_sugerido || "-");

    pintarEvaluacionCalidad(data.evaluacion_calidad_lista || []);
    pintarResumenSegmentos(data.evaluacion_calidad_lista || []);
    pintarHabilidadesBlandas(data.habilidades_blandas_lista || habilidadesBlandasDesdeEvaluacionIa(data.evaluacion_calidad_lista || []));
    pintarLista("fortalezasIa", data.fortalezas_lista || []);
    pintarLista("alertasIa", data.alertas_lista || []);
    pintarPuntosCriticos(data.puntos_criticos_lista || []);
    cargarRevisionEnFormulario(data);
}

function activarVistaResultadoIa(activa) {
    ocultarMensajeIa();
    setVistaActivaIa("evaluaciones");
    document.getElementById("filtrosReporteIa")?.classList.add("oculto");
    document.getElementById("kpisIa")?.classList.toggle("oculto", activa);
    document.getElementById("panelCargaIa")?.classList.toggle("oculto", activa);
    document.getElementById("historialPanelIa")?.classList.toggle("oculto", activa);
    document.getElementById("reporteriaPanelIa")?.classList.add("oculto");
    document.getElementById("panelResultadoIa")?.classList.remove("oculto");
    document.getElementById("panelResultadoIa")?.classList.toggle("result-focus", activa);
    document.getElementById("btnNuevaLlamadaIa")?.classList.toggle("oculto", !activa);
    document.querySelector(".ia-grid")?.classList.toggle("result-mode", activa);
}

function nuevaLlamadaIa() {
    ocultarMensajeIa();
    resultadoActualIa = null;
    setVistaActivaIa("evaluaciones");
    document.getElementById("filtrosReporteIa")?.classList.add("oculto");
    document.getElementById("kpisIa")?.classList.add("oculto");
    document.getElementById("panelCargaIa")?.classList.remove("oculto");
    document.getElementById("panelResultadoIa")?.classList.add("oculto");
    document.getElementById("historialPanelIa")?.classList.add("oculto");
    document.getElementById("reporteriaPanelIa")?.classList.add("oculto");
    document.querySelector(".ia-grid")?.classList.add("result-mode");
    document.getElementById("resultadoVacioIa")?.classList.remove("oculto");
    document.getElementById("resultadoContenidoIa")?.classList.add("oculto");
    document.getElementById("btnVolverResultadoIa")?.classList.add("oculto");
    cambiarEstadoProceso("PENDIENTE");
    setText("resultadoNivelIa", "-");
    setValue("fechaIa", fechaLocalActualIa());
    window.scrollTo({ top: 0, behavior: "smooth" });
}

function toggleHistorialIa() {
    ocultarMensajeIa();
    setVistaActivaIa("evaluaciones");
    const panel = document.getElementById("historialPanelIa");
    document.getElementById("filtrosReporteIa")?.classList.add("oculto");
    document.getElementById("reporteriaPanelIa")?.classList.add("oculto");
    document.getElementById("kpisIa")?.classList.add("oculto");
    document.getElementById("panelCargaIa")?.classList.add("oculto");
    document.getElementById("panelResultadoIa")?.classList.add("oculto");
    panel?.classList.remove("oculto");
    document.querySelector(".ia-grid")?.classList.add("result-mode");
    cargarHistorialIa();
}

function toggleReporteriaIa() {
    activarVistaReporteriaIa();
    cargarReporteriaIa();
}

function activarVistaReporteriaIa(options = {}) {
    ocultarMensajeIa();
    setVistaActivaIa("reporte");
    document.getElementById("filtrosReporteIa")?.classList.remove("oculto");
    document.getElementById("kpisIa")?.classList.add("oculto");
    document.getElementById("panelCargaIa")?.classList.add("oculto");
    document.getElementById("panelResultadoIa")?.classList.add("oculto");
    document.getElementById("historialPanelIa")?.classList.add("oculto");
    document.getElementById("reporteriaPanelIa")?.classList.remove("oculto");
    document.getElementById("btnVolverResultadoIa")?.classList.toggle("oculto", !resultadoActualIa);
    document.querySelector(".ia-grid")?.classList.add("result-mode");
    if (options.scroll !== false) window.scrollTo({ top: 0, behavior: "smooth" });
}

function volverResultadoIa() {
    if (!resultadoActualIa) {
        nuevaLlamadaIa();
        return;
    }
    activarVistaResultadoIa(true);
    document.getElementById("resultadoVacioIa")?.classList.add("oculto");
    document.getElementById("resultadoContenidoIa")?.classList.remove("oculto");
    window.scrollTo({ top: 0, behavior: "smooth" });
}

async function cargarReporteriaIa() {
    try {
        const params = new URLSearchParams({
            limit: "300",
            perfil: tipoUsuarioIa(),
            supervisor: localStorage.getItem("agente") || localStorage.getItem("dni") || ""
        });
        const response = await fetchIa(`${IA_FEEDBACK_BASE}/reporteria?${params.toString()}`, {}, 20000);
        const data = await leerJsonSeguro(response);
        if (!response.ok) throw new Error(data.detail || "No se pudo cargar la reporteria.");
        renderReporteriaIa(data);
    } catch (error) {
        mostrarMensajeIa(error.message || "Error cargando reporteria.", "error");
    }
}

function renderReporteriaIa(data) {
    reporteriaActualIa = data || {};
    detalleReporteIa = aplicarFiltrosDetalleIa(reporteriaActualIa.detalle || []);
    const paginas = totalPaginasDetalleIa();
    if (detalleReportePaginaIa > paginas) detalleReportePaginaIa = paginas;
    poblarFiltroSupervisoresIa(reporteriaActualIa.detalle || []);
    const dataFiltrada = construirReporteFiltradoIa(reporteriaActualIa, detalleReporteIa);
    const brechas = dataFiltrada.brechas || [];
    const carteras = dataFiltrada.carteras || [];
    const agentes = dataFiltrada.agentes || [];
    const score = Number(dataFiltrada.score_promedio || 0);
    const brechaPrincipal = brechas[0]
        ? `${brechas[0].item || "-"} (${formatoNumero(brechas[0].ceros || 0)} ceros)`
        : "-";
    setText("repTotalIa", formatoNumero(dataFiltrada.total_audios || 0));
    setText("repPromedioIa", dataFiltrada.score_promedio == null ? "-" : `${Number(dataFiltrada.score_promedio).toFixed(1)}%`);
    setText("repCerosIa", formatoNumero(dataFiltrada.items_nota_cero || 0));
    setText("repObservadasIa", porcentajeObservadasIa(dataFiltrada));
    setText("repAgentesEvaluadosIa", formatoNumero(agentes.filter(x => etiquetaReporte(x, "agente") !== "Sin agente asociado").length));
    setText("repPendienteCoachingIa", formatoNumero(agentes.filter(x => porcentajeReporte(x) < 75 || Number(x.ceros || 0) > 0).length));
    setText("repTotalCentroIa", formatoNumero(dataFiltrada.total_audios || 0));
    setText("repRiesgoIa", score >= 85 && !Number(dataFiltrada.items_nota_cero || 0) ? "BAJO" : score < 70 || Number(dataFiltrada.items_nota_cero || 0) > 8 ? "ALTO" : "MEDIO");
    setText("repCarteraSensibleIa", carteras[0]?.cartera || "-");
    setText("repAgenteRiesgoIa", agentes[0]?.agente || "-");
    setText("repFallaRepetidaIa", brechaPrincipal);
    setText("ultimaActualizacionIa", formatoFecha(new Date().toISOString()));
    pintarDistribucionIa(dataFiltrada);
    pintarAlertasTablaIa(brechas);
    pintarTopAgentesIa(agentes);
    pintarAgentesPrioridadIa(agentes);
    pintarReincidenciasIa(brechas);
    pintarBarrasReporte("repCarterasIa", carteras, "cartera");
    pintarBarrasReporte("repSegmentosIa", dataFiltrada.segmentos || [], "segmento");
    pintarBarrasReporte("repBrechasIa", brechas, "item");
    pintarComparativoCarterasIa(carteras);
    pintarSemanasReporte(dataFiltrada.semanas || []);
    pintarCarteraSemanaIa(detalleReporteIa);
    pintarResumenCopcIa(dataFiltrada);
    poblarFiltroAgenteSemanaIa(detalleReporteIa);
    pintarAgenteSemanaIa(detalleReporteIa);
    pintarPrecisionCarteraIa(carteras);
    pintarTendenciaSemanalIa(detalleReporteIa);
    pintarParetoIa(brechas);
    pintarDetalleReporteIa(detalleReporteIa);
}

function porcentajeObservadasIa(data) {
    const total = Number(data.total_audios || 0);
    if (!total) return "-";
    const observadas = Math.min(total, Number(data.items_nota_cero || 0));
    return `${((observadas / total) * 100).toFixed(1)}%`;
}

function prepararFiltrosReporteIa() {
    ["filtroFechaIa", "filtroCarteraIa", "filtroSupervisorIa", "filtroAgenteIa", "filtroRiesgoIa", "filtroResultadoIa"].forEach(id => {
        const el = document.getElementById(id);
        if (!el) return;
        const evento = el.tagName === "INPUT" ? "input" : "change";
        el.addEventListener(evento, () => {
            detalleReportePaginaIa = 1;
            if (reporteriaActualIa) renderReporteriaIa(reporteriaActualIa);
        });
    });
    setValue("filtroFechaIa", rangoMesActualIa());
}

function prepararAccionesReporteIa() {
    document.querySelectorAll("[onclick='exportarReporteIa()']").forEach(btn => {
        btn.addEventListener("click", event => {
            event.preventDefault();
            exportarReporteIa();
        });
        btn.removeAttribute("onclick");
    });
    document.querySelectorAll("[onclick='limpiarFiltrosReporteIa()']").forEach(btn => {
        btn.addEventListener("click", event => {
            event.preventDefault();
            limpiarFiltrosReporteIa();
        });
        btn.removeAttribute("onclick");
    });
    document.querySelectorAll("[onclick='cargarReporteriaIa()']").forEach(btn => {
        btn.addEventListener("click", event => {
            event.preventDefault();
            cargarReporteriaIa();
        });
        btn.removeAttribute("onclick");
    });
    document.getElementById("pageSizeDetalleIa")?.addEventListener("change", event => {
        detalleReportePageSizeIa = Number(event.target.value || 10);
        detalleReportePaginaIa = 1;
        pintarDetalleReporteIa(detalleReporteIa);
    });
    document.getElementById("prevDetalleIa")?.addEventListener("click", () => {
        if (detalleReportePaginaIa <= 1) return;
        detalleReportePaginaIa -= 1;
        pintarDetalleReporteIa(detalleReporteIa);
    });
    document.getElementById("nextDetalleIa")?.addEventListener("click", () => {
        if (detalleReportePaginaIa >= totalPaginasDetalleIa()) return;
        detalleReportePaginaIa += 1;
        pintarDetalleReporteIa(detalleReporteIa);
    });
}

function aplicarFiltrosDetalleIa(items) {
    const cartera = valor("filtroCarteraIa").toLowerCase();
    const supervisor = valor("filtroSupervisorIa").toLowerCase();
    const agente = valor("filtroAgenteIa").toLowerCase();
    const riesgo = valor("filtroRiesgoIa").toLowerCase();
    const resultado = valor("filtroResultadoIa").toLowerCase();
    const rango = parseRangoFechasIa(valor("filtroFechaIa"));

    return items.filter(item => {
        const fecha = parseFechaIa(item.fecha_llamada || item.fecha_creacion);
        if (rango.desde && (!fecha || fecha < rango.desde)) return false;
        if (rango.hasta && (!fecha || fecha > rango.hasta)) return false;
        if (cartera && !String(item.cartera || "").toLowerCase().includes(cartera)) return false;
        if (supervisor && !String(item.supervisor || "").toLowerCase().includes(supervisor)) return false;
        if (agente && !String(item.agente || "").toLowerCase().includes(agente)) return false;
        if (riesgo && nivelRiesgoDetalleIa(item).toLowerCase() !== riesgo) return false;
        if (resultado && resultadoIaDetalle(item).toLowerCase() !== resultado) return false;
        return true;
    });
}

function construirReporteFiltradoIa(data, detalle) {
    const scores = detalle.map(x => Number(x.score_calidad || 0)).filter(x => !Number.isNaN(x));
    const carteras = agruparScoreDetalleIa(detalle, "cartera");
    const agentes = agruparScoreDetalleIa(detalle, "agente");
    const semanas = agruparScoreDetalleIa(detalle, "semana");
    const segmentos = {};
    let ceros = 0;

    detalle.forEach(row => {
        Object.entries(row.notas_segmento || {}).forEach(([segmento, dataSegmento]) => {
            const actual = segmentos[segmento] || { segmento, peso: 0, nota: 0, total_items: 0, ceros: 0 };
            actual.peso += Number(dataSegmento.peso || 0);
            actual.nota += Number(dataSegmento.nota || 0);
            actual.total_items += 1;
            if (Number(dataSegmento.nota || 0) === 0) {
                actual.ceros += 1;
                ceros += 1;
            }
            segmentos[segmento] = actual;
        });
    });

    const segmentosLista = Object.values(segmentos).map(item => {
        item.porcentaje = item.peso ? (item.nota / item.peso) * 100 : 0;
        return item;
    }).sort((a, b) => a.porcentaje - b.porcentaje);

    return {
        ...data,
        total_audios: detalle.length,
        score_promedio: scores.length ? scores.reduce((sum, value) => sum + value, 0) / scores.length : null,
        items_nota_cero: ceros || detalle.reduce((sum, row) => sum + Number(row.total_puntos_criticos || 0), 0),
        carteras,
        agentes,
        semanas,
        segmentos: segmentosLista,
    };
}

function pintarCarteraSemanaIa(items) {
    const table = document.getElementById("repCarteraSemanaIa");
    if (!table) return;
    if (!items.length) {
        table.innerHTML = `<tbody><tr><td class="empty-row">No hay evaluaciones para los filtros seleccionados.</td></tr></tbody>`;
        return;
    }

    const semanas = [...new Set(items.map(item => claveSemanaClienteIa(item.fecha_llamada || item.fecha_creacion)))].sort();
    const carteras = {};
    items.forEach(item => {
        const cartera = item.cartera || "Sin cartera";
        const semana = claveSemanaClienteIa(item.fecha_llamada || item.fecha_creacion);
        const actual = carteras[cartera] || { cartera, total: 0, scoreTotal: 0, criticos: 0, semanas: {} };
        actual.total += 1;
        actual.scoreTotal += Number(item.score_calidad || 0);
        actual.criticos += Number(item.total_puntos_criticos || 0);
        const sem = actual.semanas[semana] || { total: 0, scoreTotal: 0 };
        sem.total += 1;
        sem.scoreTotal += Number(item.score_calidad || 0);
        actual.semanas[semana] = sem;
        carteras[cartera] = actual;
    });

    const rows = Object.values(carteras).sort((a, b) => b.total - a.total);
    table.innerHTML = `
        <thead>
            <tr>
                <th>Cartera</th>
                <th>Evaluaciones mes</th>
                <th>Promedio</th>
                <th>Alertas</th>
                ${semanas.map(semana => `<th>${escapeHtml(semana)}</th>`).join("")}
            </tr>
        </thead>
        <tbody>
            ${rows.map(row => `
                <tr class="cartera-week-row" data-cartera="${encodeURIComponent(row.cartera)}" title="Ver agentes evaluados de esta cartera">
                    <td><strong>${escapeHtml(row.cartera)}</strong></td>
                    <td>${formatoNumero(row.total)}</td>
                    <td>${(row.scoreTotal / row.total).toFixed(1)}%</td>
                    <td>${formatoNumero(row.criticos)}</td>
                    ${semanas.map(semana => {
                        const sem = row.semanas[semana];
                        return `<td>${sem ? `${formatoNumero(sem.total)} | ${(sem.scoreTotal / sem.total).toFixed(1)}%` : "-"}</td>`;
                    }).join("")}
                </tr>
            `).join("")}
        </tbody>
    `;
}

function prepararAccionesAgenteSemanaIa() {
    document.getElementById("repAgenteCarteraIa")?.addEventListener("change", event => {
        agenteSemanaCarteraIa = event.target.value || "";
        agenteSemanaPaginaIa = 1;
        pintarAgenteSemanaIa(detalleReporteIa);
    });
    document.getElementById("repAgenteBusquedaIa")?.addEventListener("input", () => {
        agenteSemanaPaginaIa = 1;
        pintarAgenteSemanaIa(detalleReporteIa);
    });
    document.getElementById("repAgenteOrdenIa")?.addEventListener("change", () => {
        agenteSemanaPaginaIa = 1;
        pintarAgenteSemanaIa(detalleReporteIa);
    });
    document.getElementById("repAgentePageSizeIa")?.addEventListener("change", event => {
        agenteSemanaPageSizeIa = Number(event.target.value || 8);
        agenteSemanaPaginaIa = 1;
        pintarAgenteSemanaIa(detalleReporteIa);
    });
    document.getElementById("repAgentePrevIa")?.addEventListener("click", () => {
        if (agenteSemanaPaginaIa <= 1) return;
        agenteSemanaPaginaIa -= 1;
        pintarAgenteSemanaIa(detalleReporteIa);
    });
    document.getElementById("repAgenteNextIa")?.addEventListener("click", () => {
        const totalPaginas = Math.max(1, Math.ceil((agenteSemanaItemsIa.length || 0) / agenteSemanaPageSizeIa));
        if (agenteSemanaPaginaIa >= totalPaginas) return;
        agenteSemanaPaginaIa += 1;
        pintarAgenteSemanaIa(detalleReporteIa);
    });
    document.addEventListener("click", event => {
        const scrollTarget = event.target.closest("[data-quality-scroll]");
        if (scrollTarget) {
            event.preventDefault();
            document.getElementById(scrollTarget.dataset.qualityScroll)?.scrollIntoView({ behavior: "smooth", block: "start" });
        }
        const row = event.target.closest(".cartera-week-row");
        if (!row) return;
        agenteSemanaCarteraIa = decodeURIComponent(row.dataset.cartera || "");
        setValue("repAgenteCarteraIa", agenteSemanaCarteraIa);
        agenteSemanaPaginaIa = 1;
        pintarAgenteSemanaIa(detalleReporteIa);
        document.getElementById("repAgenteSemanaCardIa")?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
}

function pintarResumenCopcIa(data) {
    const total = Number(data.total_audios || 0);
    const score = data.score_promedio == null ? 0 : Number(data.score_promedio || 0);
    const ceros = Number(data.items_nota_cero || 0);
    const agentes = data.agentes || [];
    const carteras = data.carteras || [];
    const coaching = agentes.filter(x => porcentajeReporte(x) < 75 || Number(x.ceros || 0) > 0).length;
    setText("copcMonitorResumenIa", `${formatoNumero(total)} evaluaciones, ${formatoNumero(ceros)} alertas y score promedio ${score ? score.toFixed(1) : "0.0"}%.`);
    setText("copcSupervisorResumenIa", `${formatoNumero(agentes.length)} agentes evaluados; ${formatoNumero(coaching)} requieren seguimiento o coaching.`);
    setText("copcFichaResumenIa", total ? `Ultima muestra lista para ficha: ${formatoNumero(total)} evaluaciones del periodo filtrado.` : "Sin evaluaciones para preparar ficha en el filtro actual.");
    setText("copcCalibracionResumenIa", `${formatoNumero(carteras.length)} carteras comparables para calibrar criterio y brechas.`);
}

function poblarFiltroAgenteSemanaIa(items) {
    const select = document.getElementById("repAgenteCarteraIa");
    if (!select) return;
    const actual = agenteSemanaCarteraIa || select.value || "";
    const carteras = [...new Set(items.map(item => item.cartera || "Sin cartera").filter(Boolean))].sort();
    select.innerHTML = `<option value="">Todas las carteras</option>` + carteras.map(item => `<option value="${escapeHtml(item)}">${escapeHtml(item)}</option>`).join("");
    select.value = carteras.includes(actual) ? actual : "";
    agenteSemanaCarteraIa = select.value;
}

function pintarAgenteSemanaIa(items) {
    const table = document.getElementById("repAgenteSemanaIa");
    if (!table) return;
    const semanas = [...new Set(items.map(item => claveSemanaClienteIa(item.fecha_llamada || item.fecha_creacion)))].sort();
    const cartera = agenteSemanaCarteraIa || valor("repAgenteCarteraIa");
    const busqueda = valor("repAgenteBusquedaIa").toLowerCase();
    const orden = valor("repAgenteOrdenIa") || "riesgo";
    const filtrados = items.filter(item => {
        if (cartera && String(item.cartera || "Sin cartera") !== cartera) return false;
        if (busqueda && !String(item.agente || "Sin agente asociado").toLowerCase().includes(busqueda)) return false;
        return true;
    });
    const grupos = {};
    filtrados.forEach(item => {
        const agente = item.agente || "Sin agente asociado";
        const itemCartera = item.cartera || "Sin cartera";
        const semana = claveSemanaClienteIa(item.fecha_llamada || item.fecha_creacion);
        const key = `${itemCartera}||${agente}`;
        const actual = grupos[key] || { cartera: itemCartera, agente, total: 0, scoreTotal: 0, criticos: 0, semanas: {} };
        actual.total += 1;
        actual.scoreTotal += Number(item.score_calidad || 0);
        actual.criticos += Number(item.total_puntos_criticos || 0);
        const sem = actual.semanas[semana] || { total: 0, scoreTotal: 0 };
        sem.total += 1;
        sem.scoreTotal += Number(item.score_calidad || 0);
        actual.semanas[semana] = sem;
        grupos[key] = actual;
    });
    agenteSemanaItemsIa = Object.values(grupos).map(item => ({
        ...item,
        promedio: item.total ? item.scoreTotal / item.total : 0,
    }));
    ordenarAgentesSemanaIa(agenteSemanaItemsIa, orden);
    const total = agenteSemanaItemsIa.length;
    const totalPaginas = Math.max(1, Math.ceil(total / agenteSemanaPageSizeIa));
    if (agenteSemanaPaginaIa > totalPaginas) agenteSemanaPaginaIa = totalPaginas;
    const inicio = total ? (agenteSemanaPaginaIa - 1) * agenteSemanaPageSizeIa : 0;
    const pagina = agenteSemanaItemsIa.slice(inicio, inicio + agenteSemanaPageSizeIa);
    setText("repAgenteSemanaSubIa", cartera ? `Agentes evaluados en ${cartera}.` : "Agentes evaluados por cartera, mes y semana.");
    setText("repAgenteCarteraActivaIa", cartera ? `Cartera seleccionada: ${cartera}` : "Vista consolidada de agentes evaluados.");
    setText("repAgenteConteoIa", total ? `Mostrando ${formatoNumero(inicio + 1)} a ${formatoNumero(Math.min(inicio + agenteSemanaPageSizeIa, total))} de ${formatoNumero(total)} agentes` : "Mostrando 0 agentes");
    setText("repAgentePaginaIa", `Pagina ${formatoNumero(agenteSemanaPaginaIa)} de ${formatoNumero(totalPaginas)}`);
    const prev = document.getElementById("repAgentePrevIa");
    const next = document.getElementById("repAgenteNextIa");
    if (prev) prev.disabled = agenteSemanaPaginaIa <= 1;
    if (next) next.disabled = agenteSemanaPaginaIa >= totalPaginas;
    if (!pagina.length) {
        table.innerHTML = `<tbody><tr><td class="empty-row">No hay agentes evaluados para esta seleccion.</td></tr></tbody>`;
        return;
    }
    table.innerHTML = `
        <thead>
            <tr>
                <th>Agente</th>
                <th>Cartera</th>
                <th>Evaluaciones mes</th>
                <th>Promedio</th>
                <th>Alertas</th>
                ${semanas.map(semana => `<th>${escapeHtml(semana)}</th>`).join("")}
            </tr>
        </thead>
        <tbody>
            ${pagina.map(row => `
                <tr class="${row.promedio < 70 || row.criticos > 0 ? "warning-row" : ""}">
                    <td><strong>${escapeHtml(row.agente)}</strong></td>
                    <td>${escapeHtml(row.cartera)}</td>
                    <td>${formatoNumero(row.total)}</td>
                    <td><span class="quality-score ${claseScoreAgenteIa(row.promedio)}">${row.promedio.toFixed(1)}%</span></td>
                    <td>${formatoNumero(row.criticos)}</td>
                    ${semanas.map(semana => {
                        const sem = row.semanas[semana];
                        return `<td>${sem ? `${formatoNumero(sem.total)} | ${(sem.scoreTotal / sem.total).toFixed(1)}%` : "-"}</td>`;
                    }).join("")}
                </tr>
            `).join("")}
        </tbody>
    `;
}

function ordenarAgentesSemanaIa(items, orden) {
    const sorters = {
        total: (a, b) => b.total - a.total || a.promedio - b.promedio,
        score_desc: (a, b) => b.promedio - a.promedio || b.total - a.total,
        score_asc: (a, b) => a.promedio - b.promedio || b.criticos - a.criticos,
        riesgo: (a, b) => b.criticos - a.criticos || a.promedio - b.promedio || b.total - a.total,
    };
    items.sort(sorters[orden] || sorters.riesgo);
}

function claseScoreAgenteIa(score) {
    if (score >= 85) return "score-ok";
    if (score >= 70) return "score-mid";
    return "score-low";
}

function pintarPrecisionCarteraIa(items) {
    const el = document.getElementById("repPrecisionCarteraIa");
    if (!el) return;
    if (!items.length) {
        el.innerHTML = `<div class="empty-segment">Sin datos suficientes.</div>`;
        return;
    }
    const max = Math.max(...items.map(item => porcentajeReporte(item)), 100);
    el.innerHTML = [...items]
        .sort((a, b) => porcentajeReporte(b) - porcentajeReporte(a))
        .slice(0, 12)
        .map(item => {
            const value = porcentajeReporte(item);
            return `
                <article>
                    <span>${escapeHtml(item.cartera || "-")}</span>
                    <div class="vertical-bar"><i style="height:${Math.max(6, (value / max) * 100)}%"></i></div>
                    <strong>${value.toFixed(1)}%</strong>
                </article>
            `;
        }).join("");
}

function pintarTendenciaSemanalIa(items) {
    const el = document.getElementById("repTendenciaSemanalIa");
    if (!el) return;
    const semanas = agruparScoreDetalleIa(items, "semana").sort((a, b) => String(a.semana).localeCompare(String(b.semana)));
    if (!semanas.length) {
        el.innerHTML = `<div class="empty-segment">Sin datos suficientes.</div>`;
        return;
    }
    el.innerHTML = semanas.map(item => {
        const score = porcentajeReporte(item);
        return `
            <article>
                <span>${escapeHtml(item.semana || "-")}</span>
                <div class="trend-point" style="--score:${score}"></div>
                <strong>${score.toFixed(1)}%</strong>
                <small>${formatoNumero(item.total_audios || 0)} eval.</small>
            </article>
        `;
    }).join("");
}

function pintarParetoIa(items) {
    const el = document.getElementById("repParetoIa");
    if (!el) return;
    const rows = [...items].slice(0, 10);
    const total = rows.reduce((sum, item) => sum + Number(item.ceros || item.total || 0), 0);
    let acumulado = 0;
    if (!rows.length || !total) {
        el.innerHTML = `<div class="empty-segment">Sin datos suficientes.</div>`;
        return;
    }
    el.innerHTML = rows.map(item => {
        const count = Number(item.ceros || item.total || 0);
        acumulado += count;
        const pct = (count / total) * 100;
        const acumPct = (acumulado / total) * 100;
        return `
            <article>
                <div>
                    <strong>${escapeHtml(item.item || "-")}</strong>
                    <span>${formatoNumero(count)} casos | acum. ${acumPct.toFixed(1)}%</span>
                </div>
                <div class="pareto-line">
                    <i style="width:${pct}%"></i>
                    <b style="left:${Math.min(100, acumPct)}%"></b>
                </div>
            </article>
        `;
    }).join("");
}

function agruparScoreDetalleIa(items, campo) {
    const grupos = {};
    items.forEach(item => {
        const clave = campo === "semana" ? claveSemanaClienteIa(item.fecha_llamada || item.fecha_creacion) : (item[campo] || `Sin ${campo}`);
        const actual = grupos[clave] || { [campo]: clave, total_audios: 0, score_total: 0, ceros: 0 };
        actual.total_audios += 1;
        actual.score_total += Number(item.score_calidad || 0);
        actual.ceros += Number(item.total_puntos_criticos || 0);
        grupos[clave] = actual;
    });
    return Object.values(grupos).map(item => ({
        ...item,
        score_promedio: item.total_audios ? item.score_total / item.total_audios : 0,
    })).sort((a, b) => Number(a.score_promedio || 0) - Number(b.score_promedio || 0));
}

function pintarDetalleReporteIa(items) {
    const tbody = document.getElementById("repDetalleBodyIa");
    if (!tbody) return;
    const total = items.length;
    const totalPaginas = totalPaginasDetalleIa();
    const inicio = total ? (detalleReportePaginaIa - 1) * detalleReportePageSizeIa : 0;
    const fin = Math.min(inicio + detalleReportePageSizeIa, total);
    const pagina = items.slice(inicio, fin);
    setText("repConteoDetalleIa", total ? `Mostrando ${formatoNumero(inicio + 1)} a ${formatoNumero(fin)} de ${formatoNumero(total)} evaluaciones` : "Mostrando 0 evaluaciones");
    setText("detallePaginaIa", `Pagina ${formatoNumero(detalleReportePaginaIa)} de ${formatoNumero(totalPaginas)}`);
    const prev = document.getElementById("prevDetalleIa");
    const next = document.getElementById("nextDetalleIa");
    if (prev) prev.disabled = detalleReportePaginaIa <= 1;
    if (next) next.disabled = detalleReportePaginaIa >= totalPaginas;
    if (!items.length) {
        tbody.innerHTML = `<tr><td colspan="9" class="empty-row">No hay evaluaciones para los filtros seleccionados.</td></tr>`;
        return;
    }
    tbody.innerHTML = pagina.map(item => `
        <tr>
            <td>${escapeHtml(item.id_feedback || "-")}</td>
            <td>${escapeHtml(item.archivo_nombre || "-")}</td>
            <td>${escapeHtml(item.agente || "-")}</td>
            <td>${escapeHtml(item.supervisor || "-")}</td>
            <td>${escapeHtml(item.cartera || "-")}</td>
            <td>${escapeHtml(formatearNotasSegmentoIa(item.notas_segmento))}</td>
            <td><strong>${Number(item.score_calidad || 0).toFixed(1)}%</strong></td>
            <td>${escapeHtml(item.observacion_supervisor || "-")}</td>
            <td><button class="historial-action" type="button" onclick="verAnalisisIa(${Number(item.id_feedback || 0)})">Ver</button></td>
        </tr>
    `).join("");
}

function totalPaginasDetalleIa() {
    return Math.max(1, Math.ceil((detalleReporteIa?.length || 0) / detalleReportePageSizeIa));
}

function formatearNotasSegmentoIa(notas) {
    const entries = Object.entries(notas || {});
    if (!entries.length) return "-";
    return entries.map(([segmento, item]) => `${formatearSegmentoIa(segmento)}: ${Number(item.nota || 0).toFixed(1)}/${Number(item.peso || 0).toFixed(1)}`).join(" | ");
}

function formatearSegmentoIa(segmento) {
    const value = String(segmento || "-");
    return value.toLowerCase() === "experiencia y riesgo" ? "Filosofia Biznescob" : value;
}

function poblarFiltroSupervisoresIa(items) {
    const select = document.getElementById("filtroSupervisorIa");
    if (!select || select.dataset.ready === "1") return;
    const supervisores = [...new Set(items.map(x => x.supervisor).filter(Boolean))].sort();
    select.innerHTML = `<option value="">Todos</option>` + supervisores.map(item => `<option value="${escapeHtml(item)}">${escapeHtml(item)}</option>`).join("");
    select.dataset.ready = "1";
}

function limpiarFiltrosReporteIa() {
    detalleReportePaginaIa = 1;
    agenteSemanaPaginaIa = 1;
    agenteSemanaCarteraIa = "";
    setValue("filtroFechaIa", "");
    setValue("filtroCarteraIa", "");
    setValue("filtroSupervisorIa", "");
    setValue("filtroAgenteIa", "");
    setValue("filtroRiesgoIa", "");
    setValue("filtroResultadoIa", "");
    setValue("repAgenteCarteraIa", "");
    setValue("repAgenteBusquedaIa", "");
    setValue("repAgenteOrdenIa", "riesgo");
    if (reporteriaActualIa) renderReporteriaIa(reporteriaActualIa);
}

function resultadoIaDetalle(item) {
    const score = Number(item.score_calidad || 0);
    if (score >= 85) return "Excelente";
    if (score >= 70) return "Aceptable";
    if (score >= 50) return "Con observacion";
    return "Deficiente";
}

function nivelRiesgoDetalleIa(item) {
    const score = Number(item.score_calidad || 0);
    const criticos = Number(item.total_puntos_criticos || 0);
    if (score < 70 || criticos >= 3) return "Alto";
    if (score < 85 || criticos > 0) return "Medio";
    return "Bajo";
}

function parseRangoFechasIa(value) {
    const partes = String(value || "").split("-").map(x => x.trim()).filter(Boolean);
    const desde = parseFechaManualIa(partes[0]);
    const hasta = parseFechaManualIa(partes[1]);
    if (hasta) hasta.setHours(23, 59, 59, 999);
    return { desde, hasta };
}

function parseFechaManualIa(value) {
    if (!value) return null;
    const match = String(value).match(/^(\d{2})\/(\d{2})\/(\d{4})$/);
    if (!match) return null;
    return new Date(Number(match[3]), Number(match[2]) - 1, Number(match[1]));
}

function parseFechaIa(value) {
    if (!value) return null;
    const fecha = new Date(value);
    return Number.isNaN(fecha.getTime()) ? null : fecha;
}

function rangoSemanaActualIa() {
    const hoy = new Date();
    const desde = new Date(hoy);
    desde.setDate(hoy.getDate() - 7);
    return `${formatoFechaCortaIa(desde)} - ${formatoFechaCortaIa(hoy)}`;
}

function rangoMesActualIa() {
    const hoy = new Date();
    const desde = new Date(hoy.getFullYear(), hoy.getMonth(), 1);
    return `${formatoFechaCortaIa(desde)} - ${formatoFechaCortaIa(hoy)}`;
}

function formatoFechaCortaIa(fecha) {
    return fecha.toLocaleDateString("es-PE", { day: "2-digit", month: "2-digit", year: "numeric" });
}

function claveSemanaClienteIa(value) {
    const fecha = parseFechaIa(value) || new Date();
    const semanaMes = Math.ceil(fecha.getDate() / 7);
    return `${fecha.getFullYear()}-${String(fecha.getMonth() + 1).padStart(2, "0")} S${semanaMes}`;
}

function pintarDistribucionIa(data) {
    const total = Number(data.total_audios || 0);
    const score = Number(data.score_promedio || 0);
    const ceros = Math.min(total, Number(data.items_nota_cero || 0));
    const excelente = score >= 85 ? Math.round(total * 0.34) : 0;
    const aceptable = score >= 70 ? Math.max(0, total - excelente - ceros) : Math.round(total * 0.35);
    const observado = Math.max(0, total - excelente - aceptable - ceros);
    const items = [
        ["Excelente", excelente, "#22c55e"],
        ["Aceptable", aceptable, "#3b82f6"],
        ["Con observacion", observado, "#f59e0b"],
        ["Deficiente", ceros, "#ef4444"],
    ];
    const legend = document.getElementById("repDistribucionIa");
    if (legend) {
        legend.innerHTML = items.map(([label, value, color]) => `
            <p><i style="background:${color}"></i><span>${escapeHtml(label)}</span><strong>${total ? Math.round((value / total) * 100) : 0}% (${formatoNumero(value)})</strong></p>
        `).join("");
    }
    setText("repInsightIa", total
        ? `El score promedio IA es ${score.toFixed(1)}. Priorizar ${data.brechas?.[0]?.item || "las brechas principales"} para mejorar cierre y negociacion.`
        : "Sin datos suficientes para generar insight.");
}

function pintarAlertasTablaIa(items) {
    const tbody = document.getElementById("repAlertasTablaIa");
    if (!tbody) return;
    if (!items.length) {
        tbody.innerHTML = `<tr><td colspan="4">Sin alertas registradas.</td></tr>`;
        return;
    }
    tbody.innerHTML = items.slice(0, 5).map(item => {
        const ceros = Number(item.ceros || 0);
        const severidad = ceros >= 5 ? "Critica" : ceros >= 2 ? "Alta" : "Media";
        return `
            <tr>
                <td>${escapeHtml(item.item || "-")}</td>
                <td>${formatoNumero(ceros || item.total || 0)}</td>
                <td><span class="severity ${severidad.toLowerCase()}">${severidad}</span></td>
                <td>${escapeHtml(accionSugeridaIa(item.item))}</td>
            </tr>
        `;
    }).join("");
}

function accionSugeridaIa(item) {
    const texto = String(item || "").toLowerCase();
    if (texto.includes("cierre") || texto.includes("3c")) return "Capacitacion en cierre";
    if (texto.includes("objec")) return "Coaching comercial";
    if (texto.includes("identidad") || texto.includes("datos")) return "Reforzar protocolo";
    if (texto.includes("tono") || texto.includes("manejo")) return "Escucha conjunta";
    return "Revision supervisor";
}

function pintarTopAgentesIa(items) {
    const mejores = [...items].filter(x => x.agente && x.agente !== "Sin agente asociado").sort((a, b) => porcentajeReporte(b) - porcentajeReporte(a)).slice(0, 3);
    pintarMiniTablaIa("repTopAgentesIa", mejores, ["Agente", "Evaluaciones", "Score IA"], item => [
        item.agente || "-",
        formatoNumero(item.total_audios || 0),
        `${porcentajeReporte(item).toFixed(0)}`
    ]);
}

function pintarAgentesPrioridadIa(items) {
    const prioridad = [...items].filter(x => x.agente).sort((a, b) => (Number(b.ceros || 0) - Number(a.ceros || 0)) || porcentajeReporte(a) - porcentajeReporte(b)).slice(0, 3);
    pintarMiniTablaIa("repAgentesPrioridadIa", prioridad, ["Agente", "Score IA", "Estado"], item => [
        item.agente || "-",
        `${porcentajeReporte(item).toFixed(0)}`,
        porcentajeReporte(item) < 70 || Number(item.ceros || 0) > 0 ? "Pendiente" : "Revisado"
    ]);
}

function pintarReincidenciasIa(items) {
    pintarMiniTablaIa("repReincidenciasIa", items.slice(0, 3), ["Falla recurrente", "Veces", "Accion"], item => [
        item.item || "-",
        formatoNumero(item.ceros || item.total || 0),
        accionSugeridaIa(item.item)
    ]);
}

function pintarComparativoCarterasIa(items) {
    pintarMiniTablaIa("repComparativoCarterasIa", items.slice(0, 5), ["Cartera", "Evaluaciones", "Score", "Alertas"], item => [
        item.cartera || "-",
        formatoNumero(item.total_audios || 0),
        `${porcentajeReporte(item).toFixed(0)}`,
        formatoNumero(item.ceros || 0)
    ]);
}

function pintarMiniTablaIa(id, items, headers, rowMapper) {
    const el = document.getElementById(id);
    if (!el) return;
    if (!items.length) {
        el.innerHTML = `<div class="empty-segment">Sin datos suficientes.</div>`;
        return;
    }
    el.innerHTML = `
        <table>
            <thead><tr>${headers.map(header => `<th>${escapeHtml(header)}</th>`).join("")}</tr></thead>
            <tbody>${items.map(item => `<tr>${rowMapper(item).map(value => `<td>${escapeHtml(value)}</td>`).join("")}</tr>`).join("")}</tbody>
        </table>
    `;
}

function pintarBarrasReporte(id, items, labelField) {
    const el = document.getElementById(id);
    if (!el) return;

    if (!items.length) {
        el.innerHTML = `<div class="empty-segment">Sin datos suficientes.</div>`;
        return;
    }

    el.innerHTML = items.map(item => {
        const porcentaje = porcentajeReporte(item);
        const totalBase = item.total ?? item.total_audios ?? 0;
        const label = etiquetaReporte(item, labelField);
        return `
            <article class="${porcentaje < 60 || Number(item.ceros || 0) > 0 ? "critical-report" : ""}">
                <div>
                    <strong>${escapeHtml(label)}</strong>
                    <span>${porcentaje.toFixed(1)}% | ceros: ${formatoNumero(item.ceros || 0)} | base: ${formatoNumero(totalBase)}</span>
                </div>
                <div class="report-bar"><i style="width:${porcentaje}%"></i></div>
            </article>
        `;
    }).join("");
}

function porcentajeReporte(item) {
    return Math.max(0, Math.min(100, Number(item.porcentaje ?? item.score_promedio ?? 0)));
}

function etiquetaReporte(item, labelField) {
    if (labelField === "item") return `${item.item || "-"} (${item.segmento || "-"})`;
    if (labelField === "cartera") return item.cartera || "-";
    if (labelField === "agente") return item.agente || "-";
    if (labelField === "semana") return item.semana || "-";
    return formatearSegmentoIa(item.segmento);
}

function pintarSemanasReporte(items) {
    const el = document.getElementById("repSemanasIa");
    if (!el) return;

    if (!items.length) {
        el.innerHTML = `<div class="empty-segment">Sin datos suficientes.</div>`;
        return;
    }

    el.innerHTML = items.map(item => {
        const porcentaje = porcentajeReporte(item);
        return `
            <article class="${porcentaje < 70 || Number(item.ceros || 0) > 0 ? "critical-report" : ""}">
                <span>${escapeHtml(item.semana || "-")}</span>
                <strong>${porcentaje.toFixed(1)}%</strong>
                <div class="report-bar"><i style="width:${porcentaje}%"></i></div>
                <small>${formatoNumero(item.total_audios || 0)} evaluaciones | ${formatoNumero(item.ceros || 0)} ceros</small>
            </article>
        `;
    }).join("");
}

async function guardarRevisionIa() {
    const idFeedback = valor("feedbackIdActualIa");
    if (!idFeedback) {
        mostrarMensajeIa("Primero abre o genera un analisis para guardar la revision.", "error");
        return;
    }

    const btn = document.getElementById("btnGuardarRevisionIa");
    btn.disabled = true;
    btn.textContent = "Guardando...";

    try {
        const formData = new FormData();
        formData.append("agente", valor("agenteRevisionIa"));
        formData.append("estado_revision", valor("estadoRevisionIa") || "REVISADO");
        formData.append("comentario_feedback", valor("comentarioFeedbackIa"));
        formData.append("revisado_por", localStorage.getItem("agente") || localStorage.getItem("dni") || "SIN_USUARIO");

        const response = await fetchIa(`${IA_FEEDBACK_BASE}/${idFeedback}/revision`, {
            method: "POST",
            body: formData,
        }, 30000);
        const data = await leerJsonSeguro(response);
        if (!response.ok) throw new Error(data.detail || "No se pudo guardar la revision.");

        resultadoActualIa = null;
        document.getElementById("resultadoContenidoIa")?.classList.add("oculto");
        document.getElementById("resultadoVacioIa")?.classList.remove("oculto");
        activarVistaReporteriaIa();
        await cargarHistorialIa();
        await cargarReporteriaIa();
        mostrarMensajeIa("Revision guardada correctamente.", "ok");
    } catch (error) {
        mostrarMensajeIa(error.message || "Error guardando revision.", "error");
    } finally {
        btn.disabled = false;
        btn.textContent = "Guardar revision";
    }
}

function abrirRecalibracionIa() {
    if (!resultadoActualIa?.id_feedback) {
        mostrarMensajeIa("Primero abre o genera un analisis para solicitar recalibracion.", "error");
        return;
    }
    setText("recalibracionIdIa", resultadoActualIa.id_feedback || "-");
    setText("recalibracionNotaIa", resultadoActualIa.score_calidad != null ? `${Number(resultadoActualIa.score_calidad).toFixed(1)} / 100` : "-");
    setText("recalibracionNivelIa", resultadoActualIa.nivel_oportunidad_mejora || "-");
    setValue("itemRecalibracionIa", "");
    setValue("scoreSugeridoIa", "");
    setValue("nivelSugeridoIa", "");
    setValue("motivoRecalibracionIa", "");
    setValue("evidenciaRecalibracionIa", "");
    document.getElementById("modalRecalibracionIa")?.classList.remove("oculto");
}

function cerrarRecalibracionIa() {
    document.getElementById("modalRecalibracionIa")?.classList.add("oculto");
}

async function enviarRecalibracionIa() {
    const idFeedback = resultadoActualIa?.id_feedback || valor("feedbackIdActualIa");
    if (!idFeedback) {
        mostrarMensajeIa("Primero abre o genera un analisis para solicitar recalibracion.", "error");
        return;
    }

    if (!valor("motivoRecalibracionIa")) {
        mostrarMensajeIa("Ingresa el motivo de discrepancia para dejar trazabilidad.", "error");
        return;
    }

    const btn = document.getElementById("btnEnviarRecalibracionIa");
    btn.disabled = true;
    btn.textContent = "Enviando...";

    try {
        const formData = new FormData();
        formData.append("item_cuestionado", valor("itemRecalibracionIa"));
        if (valor("scoreSugeridoIa")) formData.append("score_sugerido", valor("scoreSugeridoIa"));
        formData.append("nivel_sugerido", valor("nivelSugeridoIa"));
        formData.append("motivo", valor("motivoRecalibracionIa"));
        formData.append("evidencia_supervisor", valor("evidenciaRecalibracionIa"));
        formData.append("solicitado_por", localStorage.getItem("agente") || localStorage.getItem("dni") || "SIN_USUARIO");

        const response = await fetchIa(`${IA_FEEDBACK_BASE}/${idFeedback}/recalibracion`, {
            method: "POST",
            body: formData,
        }, 30000);
        const data = await leerJsonSeguro(response);
        if (!response.ok) throw new Error(data.detail || "No se pudo solicitar la recalibracion.");

        resultadoActualIa = data.feedback || resultadoActualIa;
        setText("estadoRecalibracionIa", "PENDIENTE");
        setText("trazaRevisionIa", resultadoActualIa.estado_revision || "PENDIENTE");
        cerrarRecalibracionIa();
        await cargarHistorialIa();
        mostrarMensajeIa("Solicitud de recalibracion registrada con trazabilidad.", "ok");
    } catch (error) {
        mostrarMensajeIa(error.message || "Error solicitando recalibracion.", "error");
    } finally {
        btn.disabled = false;
        btn.textContent = "Enviar solicitud";
    }
}

function cargarRevisionEnFormulario(data) {
    setValue("feedbackIdActualIa", data.id_feedback || "");
    setValue("agenteRevisionIa", data.agente || "");
    setValue("estadoRevisionIa", data.estado_revision || "REVISADO");
    setValue("comentarioFeedbackIa", data.comentario_feedback || data.recomendaciones || "");
}

function pintarLista(id, items) {
    const el = document.getElementById(id);
    el.innerHTML = items.length
        ? items.map(item => `<li class="${esAlertaCritica(item) ? "critical-alert" : ""}">${escapeHtml(item)}</li>`).join("")
        : `<li>-</li>`;
}

function esAlertaCritica(texto) {
    const value = String(texto || "").toLowerCase();
    return [
        "insulto",
        "amenaza",
        "carcel",
        "presa",
        "ofensiv",
        "sarcasmo",
        "presion indebida",
        "trato despectivo",
        "conchuda"
    ].some(term => value.includes(term));
}

function pintarEvaluacionCalidad(items) {
    const tbody = document.getElementById("evaluacionCalidadIa");
    if (!tbody) return;

    if (!items.length) {
        tbody.innerHTML = `<tr><td colspan="9">Sin evaluacion de calidad registrada.</td></tr>`;
        return;
    }

    tbody.innerHTML = items.map(item => `
        <tr class="${claseFilaEvaluacion(item)}">
            <td>${escapeHtml(formatearSegmentoIa(item.segmento))}</td>
            <td>${escapeHtml(item.item || "-")}</td>
            <td>${formatoPeso(item.peso)}</td>
            <td><strong class="${Number(item.nota || 0) === 0 ? "critical-score" : ""}">${formatoPeso(item.nota)}</strong></td>
            <td>${escapeHtml(item.resultado || "-")}</td>
            <td>${escapeHtml(item.hallazgo || "-")}</td>
            <td>${escapeHtml(item.momento || "No disponible")}</td>
            <td>${escapeHtml(item.evidencia || "-")}</td>
            <td>${escapeHtml(item.recomendacion || "-")}</td>
        </tr>
    `).join("");
}

function pintarHabilidadesBlandas(items) {
    const contenedor = document.getElementById("habilidadesBlandasIa");
    if (!contenedor) return;
    if (!items.length) {
        contenedor.innerHTML = `<div class="empty-segment">Sin habilidades blandas registradas.</div>`;
        return;
    }
    contenedor.innerHTML = items.map(item => {
        const nivel = String(item.nivel || "Medio");
        return `
            <article class="soft-skill-card ${claseNivelHabilidadIa(nivel)}">
                <div>
                    <span>${escapeHtml(item.habilidad || "-")}</span>
                    <strong>${escapeHtml(nivel)}</strong>
                </div>
                <p>${escapeHtml(item.evidencia || "-")}</p>
                <small>${escapeHtml(item.recomendacion || "-")}</small>
            </article>
        `;
    }).join("");
}

function habilidadesBlandasDesdeEvaluacionIa(items) {
    const config = [
        ["Actitud conciliadora", ["3.2", "5.1"], "Refuerza una postura colaborativa ante objeciones."],
        ["Empatia", ["5.1", "5.3"], "Validar la situacion del cliente antes de insistir."],
        ["Escucha activa", ["2.3", "2.4"], "Evitar interrupciones y confirmar entendimiento."],
        ["Vocalizacion y claridad", ["5.2"], "Mantener lenguaje claro, ordenado y facil de seguir."],
        ["Manejo emocional", ["5.3", "5.4"], "Sostener calma, respeto y control durante toda la llamada."],
    ];
    return config.map(([habilidad, prefijos, recomendacion]) => {
        const relacionados = items.filter(item => prefijos.some(prefijo => String(item.item || "").startsWith(prefijo)));
        const peso = relacionados.reduce((sum, item) => sum + Number(item.peso || 0), 0);
        const nota = relacionados.reduce((sum, item) => sum + Number(item.nota || 0), 0);
        const porcentaje = peso ? (nota / peso) * 100 : 0;
        const nivel = porcentaje >= 80 ? "Alto" : porcentaje >= 55 ? "Medio" : "Bajo";
        return {
            habilidad,
            nivel,
            evidencia: relacionados.map(item => item.hallazgo).filter(Boolean).slice(0, 2).join(" | ") || "No hay evidencia suficiente.",
            recomendacion,
        };
    });
}

function claseNivelHabilidadIa(nivel) {
    const value = String(nivel || "").toLowerCase();
    if (value.includes("alto")) return "skill-high";
    if (value.includes("bajo")) return "skill-low";
    return "skill-mid";
}

function claseFilaEvaluacion(item) {
    const nota = Number(item.nota || 0);
    const resultado = String(item.resultado || "").toUpperCase();
    const texto = `${item.hallazgo || ""} ${item.evidencia || ""} ${item.recomendacion || ""}`;
    if (nota === 0 || resultado.includes("NO CUMPLE") || resultado.includes("NO EVIDENCIADO") || esAlertaCritica(texto)) {
        return "critical-row";
    }
    if (resultado.includes("PARCIAL")) return "warning-row";
    return "";
}

function pintarResumenSegmentos(items) {
    const contenedor = document.getElementById("resumenSegmentosIa");
    if (!contenedor) return;

    if (!items.length) {
        contenedor.innerHTML = `<div class="empty-segment">Sin resumen por segmento registrado.</div>`;
        return;
    }

    const segmentos = new Map();
    items.forEach(item => {
        const key = item.segmento || "Sin segmento";
        const actual = segmentos.get(key) || { segmento: key, peso: 0, nota: 0, observaciones: [] };
        actual.peso += Number(item.peso || 0);
        actual.nota += Number(item.nota || 0);
        if (item.resultado && item.resultado !== "Cumple") {
            actual.observaciones.push(`${item.item}: ${item.resultado}`);
        }
        segmentos.set(key, actual);
    });

    contenedor.innerHTML = [...segmentos.values()].map(item => {
        const porcentaje = item.peso ? Math.round((item.nota / item.peso) * 100) : 0;
        return `
            <article class="segment-card ${porcentaje < 60 ? "critical-segment" : porcentaje < 80 ? "warning-segment" : ""}">
                <div>
                    <span>${escapeHtml(formatearSegmentoIa(item.segmento))}</span>
                    <strong>${formatoPeso(item.nota)} / ${formatoPeso(item.peso)}</strong>
                </div>
                <div class="segment-bar"><i style="width:${Math.max(0, Math.min(100, porcentaje))}%"></i></div>
                <small>${escapeHtml(item.observaciones.slice(0, 2).join(" | ") || "Sin observaciones criticas.")}</small>
            </article>
        `;
    }).join("");
}

function toggleDetalleCalidadIa() {
    const detalle = document.getElementById("detalleCalidadIa");
    const btn = document.getElementById("btnDetalleCalidadIa");
    if (!detalle) return;
    const visible = detalle.classList.toggle("oculto") === false;
    if (btn) btn.textContent = visible ? "Ocultar detalle de evaluacion" : "Ver detalle de evaluacion";
}

async function cargarPromptIa() {
    const panel = document.getElementById("panelPromptIa");
    if (!panel) return;

    try {
        const perfil = localStorage.getItem("tipo") || "";
        const cartera = valor("promptCarteraIa");
        const params = new URLSearchParams({ perfil });
        if (cartera) params.set("cartera", cartera);
        const response = await fetchIa(`${IA_FEEDBACK_BASE}/prompt?${params.toString()}`, {}, 12000);
        const data = await leerJsonSeguro(response);
        if (!response.ok || !data.puede_editar) return;

        panel.classList.remove("oculto");
        setValue("promptBaseIa", data.prompt_base || "");
        setText("promptOrigenIa", obtenerTextoOrigenPrompt(data));
        setText(
            "promptMetaIa",
            data.usa_prompt_personalizado
                ? `Origen: ${obtenerTextoOrigenPrompt(data)}. Ultima actualizacion: ${formatoFecha(data.fecha_actualizacion)} por ${data.actualizado_por || "-"}`
                : "Prompt base del sistema. Guardalo para crear una version general o especifica de cartera."
        );
    } catch {
        // Si no carga la configuracion, el analisis sigue usando el prompt general.
    }
}

function obtenerTextoOrigenPrompt(data) {
    if (data.origen_prompt === "CARTERA") return "Prompt propio de cartera";
    if (data.origen_prompt === "GENERAL") return "Prompt general";
    return "Prompt base del sistema";
}

function abrirPromptIa() {
    document.getElementById("modalPromptIa")?.classList.remove("oculto");
    mostrarSeccionPromptIa("promptContextIa");
    cargarPromptIa();
}

function cerrarPromptIa() {
    document.getElementById("modalPromptIa")?.classList.add("oculto");
}

function mostrarSeccionPromptIa(id) {
    document.querySelectorAll(".prompt-section").forEach(section => {
        section.classList.toggle("oculto", section.id !== id);
    });
    document.querySelectorAll(".prompt-tab").forEach(tab => {
        tab.classList.toggle("active", tab.dataset.section === id);
    });
}

async function guardarPromptIa() {
    const prompt = valor("promptBaseIa");
    if (!prompt) {
        mostrarMensajeIa("Ingresa el prompt base antes de guardar.", "error");
        return;
    }

    const btn = document.getElementById("btnGuardarPromptIa");
    btn.disabled = true;
    btn.textContent = "Guardando...";

    try {
        const formData = new FormData();
        formData.append("prompt_base", prompt);
        formData.append("actualizado_por", localStorage.getItem("agente") || localStorage.getItem("dni") || "SIN_USUARIO");
        formData.append("perfil", localStorage.getItem("tipo") || "");
        formData.append("cartera", valor("promptCarteraIa"));

        const response = await fetchIa(`${IA_FEEDBACK_BASE}/prompt`, {
            method: "POST",
            body: formData,
        }, 30000);
        const data = await leerJsonSeguro(response);
        if (!response.ok) throw new Error(data.detail || "No se pudo guardar el prompt.");

        setText("promptOrigenIa", obtenerTextoOrigenPrompt(data));
        setText("promptMetaIa", `Origen: ${obtenerTextoOrigenPrompt(data)}. Ultima actualizacion: ${formatoFecha(data.fecha_actualizacion)} por ${data.actualizado_por || "-"}`);
        mostrarMensajeIa("Prompt guardado correctamente. Se aplicara en los proximos analisis.", "ok");
    } catch (error) {
        mostrarMensajeIa(error.message || "Error guardando prompt.", "error");
    } finally {
        btn.disabled = false;
        btn.textContent = "Guardar prompt";
    }
}

function pintarPuntosCriticos(items) {
    const tbody = document.getElementById("puntosCriticosIa");
    if (!items.length) {
        tbody.innerHTML = `<tr><td colspan="9">Sin puntos criticos registrados.</td></tr>`;
        return;
    }

    tbody.innerHTML = items.map(item => `
        <tr class="${claseFilaPuntoCriticoIa(item)}">
            <td>${escapeHtml(formatearSegmentoIa(item.segmento))}</td>
            <td>${escapeHtml(item.categoria || "-")}</td>
            <td><span class="severity ${claseSeveridadIa(item.severidad)}">${escapeHtml(item.severidad || "MEDIA")}</span></td>
            <td>${escapeHtml(item.momento || "No disponible")}</td>
            <td>${escapeHtml(item.frase_textual || "No disponible")}</td>
            <td>${escapeHtml(item.hallazgo || "-")}</td>
            <td>${escapeHtml(item.evidencia || "-")}</td>
            <td>${escapeHtml(item.impacto || "-")}</td>
            <td>${escapeHtml(item.recomendacion || "-")}</td>
        </tr>
    `).join("");
}

function claseFilaPuntoCriticoIa(item) {
    const severidad = String(item.severidad || "").toUpperCase();
    const texto = `${item.hallazgo} ${item.impacto} ${item.recomendacion} ${item.frase_textual}`;
    if (severidad === "ANULANTE" || severidad === "GRAVE" || esAlertaCritica(texto)) return "critical-row";
    if (severidad === "MEDIA") return "warning-row";
    return "";
}

function claseSeveridadIa(severidad) {
    const value = String(severidad || "MEDIA").toLowerCase();
    if (value === "anulante" || value === "grave") return "critica";
    if (value === "media") return "alta";
    return "media";
}

function cambiarEstadoProceso(estado) {
    const badge = document.getElementById("estadoProceso");
    const estadoNormalizado = String(estado || "PENDIENTE").toUpperCase();
    badge.textContent = estadoNormalizado;
    badge.className = `status-badge ${claseEstado(estadoNormalizado)}`;
}

function badgeEstado(estado) {
    const estadoNormalizado = String(estado || "PENDIENTE").toUpperCase();
    return `<span class="table-badge ${claseEstado(estadoNormalizado)}">${escapeHtml(estadoNormalizado)}</span>`;
}

function badgeRevision(estado) {
    const estadoNormalizado = String(estado || "PENDIENTE").toUpperCase();
    const clase = estadoNormalizado === "PENDIENTE" ? "badge-pendiente" : "badge-finalizado";
    return `<span class="table-badge ${clase}">${escapeHtml(estadoNormalizado.replace("_", " "))}</span>`;
}

function claseEstado(estado) {
    const key = String(estado || "").toLowerCase();
    if (key === "finalizado") return "badge-finalizado";
    if (key === "transcribiendo") return "badge-transcribiendo";
    if (key === "analizando") return "badge-analizando";
    if (key === "error") return "badge-error";
    return "badge-pendiente";
}

function limpiarFormularioBasicoIa(options = {}) {
    document.getElementById("audioIa").value = "";
    document.getElementById("nombreAudioIa").textContent = "Ningun archivo seleccionado";
    setValue("dniIa", "");
    setValue("telefonoIa", "");
    setValue("comentarioIa", "");
    setValue("fechaIa", fechaLocalActualIa());
    if (options.limpiarCartera) {
        const cartera = document.getElementById("carteraIa");
        if (cartera && cartera.options.length > 2) cartera.value = "";
    }
}

function mostrarMensajeIa(texto, tipo = "ok") {
    const box = document.getElementById("mensajeIa");
    if (!box) return;
    clearTimeout(mensajeIaTimeout);
    box.className = `ia-message ${tipo}`;
    box.textContent = texto;
    box.classList.remove("oculto");
    if (document.getElementById("panelCargaIa")?.classList.contains("oculto")) {
        box.classList.add("floating-message");
        document.querySelector(".ia-workspace")?.prepend(box);
    } else {
        box.classList.remove("floating-message");
        document.getElementById("panelCargaIa")?.appendChild(box);
    }
    mensajeIaTimeout = setTimeout(ocultarMensajeIa, tipo === "error" ? 9000 : 5000);
}

function ocultarMensajeIa() {
    const box = document.getElementById("mensajeIa");
    if (!box) return;
    clearTimeout(mensajeIaTimeout);
    box.classList.add("oculto");
    box.classList.remove("floating-message");
}

async function leerJsonSeguro(response) {
    try {
        return await response.json();
    } catch {
        return {};
    }
}

async function fetchIa(url, options = {}, timeoutMs = 30000) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), timeoutMs);
    try {
        return await fetch(url, {
            ...options,
            signal: controller.signal,
        });
    } catch (error) {
        if (error.name === "AbortError") {
            throw new Error("La solicitud demoro demasiado. Revisa la conexion con la base o intenta nuevamente.");
        }
        throw error;
    } finally {
        clearTimeout(timeout);
    }
}

function valor(id) {
    return document.getElementById(id)?.value?.trim() || "";
}

function valorCarteraIa() {
    const select = document.getElementById("carteraIa");
    return select?.value?.trim() || "";
}

function setText(id, value) {
    const el = document.getElementById(id);
    if (el) el.textContent = value;
}

function setValue(id, value) {
    const el = document.getElementById(id);
    if (el) el.value = value;
}

function formatoNumero(value) {
    return Number(value || 0).toLocaleString("es-PE");
}

function formatoPeso(value) {
    const numero = Number(value || 0);
    return Number.isInteger(numero) ? String(numero) : numero.toFixed(1);
}

function formatoFecha(value) {
    if (!value) return "-";
    const fecha = new Date(value);
    if (Number.isNaN(fecha.getTime())) return value;
    return fecha.toLocaleString("es-PE", {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
    });
}

function inicializarCabeceraReporteIa() {
    setText("usuarioSidebarIa", localStorage.getItem("agente") || localStorage.getItem("nombre") || "Supervisor");
    setText("perfilSidebarIa", localStorage.getItem("tipo") || "Calidad operativa");
    setText("ultimaActualizacionIa", formatoFecha(new Date().toISOString()));
}

function setVistaActivaIa(view) {
    document.querySelectorAll(".ia-sidebar-nav button").forEach(button => {
        button.classList.toggle("active", button.dataset.view === view);
    });
}

function exportarReporteIa() {
    const rows = detalleReporteIa || [];
    if (!rows.length) {
        mostrarMensajeIa("No hay evaluaciones para exportar con los filtros seleccionados.", "error");
        return;
    }
    const csvRows = [
        ["RESUMEN POR CARTERA Y SEMANA"],
        ...filasResumenCarteraSemanaCsv(rows),
        [],
        ["DETALLE DE EVALUACIONES"],
        ["id_llamada", "audio", "agente", "supervisor", "cartera", "notas_por_segmento", "score_final", "observacion_supervisor"],
        ...rows.map(item => [
            item.id_feedback || "",
            item.archivo_nombre || "",
            item.agente || "",
            item.supervisor || "",
            item.cartera || "",
            formatearNotasSegmentoIa(item.notas_segmento),
            Number(item.score_calidad || 0).toFixed(1),
            item.observacion_supervisor || "",
        ])
    ];
    const csv = csvRows.map(row => row.map(valorCsvIa).join(";")).join("\r\n");
    const blob = new Blob([`\uFEFF${csv}`], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `reporte_calidad_ia_${new Date().toISOString().slice(0, 10)}.csv`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
    mostrarMensajeIa("Reporte exportado correctamente.", "ok");
}

function filasResumenCarteraSemanaCsv(items) {
    const semanas = [...new Set(items.map(item => claveSemanaClienteIa(item.fecha_llamada || item.fecha_creacion)))].sort();
    const grupos = {};
    items.forEach(item => {
        const cartera = item.cartera || "Sin cartera";
        const semana = claveSemanaClienteIa(item.fecha_llamada || item.fecha_creacion);
        const actual = grupos[cartera] || { cartera, total: 0, scoreTotal: 0, criticos: 0, semanas: {} };
        actual.total += 1;
        actual.scoreTotal += Number(item.score_calidad || 0);
        actual.criticos += Number(item.total_puntos_criticos || 0);
        const sem = actual.semanas[semana] || { total: 0, scoreTotal: 0 };
        sem.total += 1;
        sem.scoreTotal += Number(item.score_calidad || 0);
        actual.semanas[semana] = sem;
        grupos[cartera] = actual;
    });
    const header = ["cartera", "evaluaciones_mes", "promedio", "alertas", ...semanas];
    const rows = Object.values(grupos).sort((a, b) => b.total - a.total).map(item => [
        item.cartera,
        item.total,
        (item.scoreTotal / item.total).toFixed(1),
        item.criticos,
        ...semanas.map(semana => {
            const sem = item.semanas[semana];
            return sem ? `${sem.total} eval | ${(sem.scoreTotal / sem.total).toFixed(1)}%` : "-";
        })
    ]);
    return [header, ...rows];
}

function valorCsvIa(value) {
    const texto = String(value ?? "").replace(/"/g, '""');
    return `"${texto}"`;
}

function mostrarPendienteCalidadIa(nombre) {
    mostrarMensajeIa(`${nombre}: base visual creada. El siguiente paso es construir la vista completa y PDF.`, "ok");
}

function escapeHtml(value) {
    return String(value ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

window.cargarHistorialIa = cargarHistorialIa;
window.verAnalisisIa = verAnalisisIa;
window.toggleDetalleCalidadIa = toggleDetalleCalidadIa;
window.nuevaLlamadaIa = nuevaLlamadaIa;
window.toggleHistorialIa = toggleHistorialIa;
window.toggleReporteriaIa = toggleReporteriaIa;
window.volverResultadoIa = volverResultadoIa;
window.cargarReporteriaIa = cargarReporteriaIa;
window.exportarReporteIa = exportarReporteIa;
window.limpiarFiltrosReporteIa = limpiarFiltrosReporteIa;
window.abrirPromptIa = abrirPromptIa;
window.cerrarPromptIa = cerrarPromptIa;
window.mostrarSeccionPromptIa = mostrarSeccionPromptIa;
window.guardarPromptIa = guardarPromptIa;
window.cargarPromptIa = cargarPromptIa;
window.abrirRecalibracionIa = abrirRecalibracionIa;
window.cerrarRecalibracionIa = cerrarRecalibracionIa;
window.mostrarPendienteCalidadIa = mostrarPendienteCalidadIa;
