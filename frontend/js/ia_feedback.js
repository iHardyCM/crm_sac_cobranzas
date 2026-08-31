const IA_FEEDBACK_BASE = obtenerBaseUrlIaFeedback();

const IA_FEEDBACK_JS_VERSION = "IA_ENGINE_TIMEOUT_CACHE_20260810A";
console.info("[IA Feedback]", IA_FEEDBACK_JS_VERSION);

let historialIa = [];
let resultadoActualIa = null;
let reporteriaActualIa = null;
let detalleReporteIa = [];
let evidenciasDetalleIa = [];
let evidenciasAgrupadasIa = [];
let evidenciasDescartadasIa = 0;
let evidenciaExpandidaIa = null;
let filtroEvidenciasActualIa = "todas";
let mostrarTodasEvidenciasIa = false;
let criteriosEvidenciaExpandidaIa = null;
let criteriosRecalibracionIa = [];
let evidenciasRecalibracionIa = [];
let criterioRecalibracionSeleccionadoIa = null;
let evidenciaRecalibracionSeleccionadaIa = null;
let filtroHistorialDetalleIa = "todos";
let historialDetalleExpandidoIa = "";
let detalleReportePaginaIa = 1;
let detalleReportePageSizeIa = 10;
let evaluacionesPaginaIa = 1;
let evaluacionesPageSizeIa = 10;
let agenteSemanaPaginaIa = 1;
let agenteSemanaPageSizeIa = 8;
let agenteSemanaCarteraIa = "";
let agenteSemanaItemsIa = [];
let mensajeIaTimeout = null;
let periodoAutoAjustadoIa = false;
let auditoriaFichaIa = {
    criterio: "factor_sgc | item",
    resultado: "calificacion | resultado",
    grupo: "grupo_error_sgc",
    grupos: {},
    duplicadosEliminados: 0,
    noAplica: "Excluido de brechas y denominador penalizable",
};
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
        comentario.placeholder = "Ejemplo: revisar diagnóstico, negociación, cierre y posibles riesgos según la pauta de la cartera.";
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
        sincronizarRevisionLegacyIa();
        await guardarRevisionIa();
    });

    document.getElementById("formDecisionSupervisorIa")?.addEventListener("submit", async (event) => {
        event.preventDefault();
        await guardarBorradorRevisionIa();
    });

    document.getElementById("comentarioFeedbackIa")?.addEventListener("input", event => {
        setText("contadorComentarioIa", `${event.target.value.length} / 1000`);
    });

    document.querySelectorAll("input[name='decisionSupervisorIa']").forEach(input => {
        input.addEventListener("change", actualizarDecisionSupervisorIa);
    });
    document.getElementById("comentarioFeedbackIa")?.addEventListener("input", actualizarDecisionSupervisorIa);

    document.getElementById("formRecalibracionIa")?.addEventListener("submit", async (event) => {
        event.preventDefault();
        await enviarRecalibracionIa();
    });

    document.getElementById("formCoachingIa")?.addEventListener("submit", async (event) => {
        event.preventDefault();
        await guardarCoachingIa();
    });

    document.getElementById("estadoCoachingIa")?.addEventListener("change", event => {
        actualizarAyudaCoachingIa(event.target.value);
    });
    ["fechaCoachingIa", "responsableCoachingIa"].forEach(id => {
        document.getElementById(id)?.addEventListener("input", () => actualizarAyudaCoachingIa(valor("estadoCoachingIa")));
    });
    ["estadoCoachingIa", "fechaCoachingIa", "responsableCoachingIa", "tipoIntervencionCoachingIa", "conductaPlanCoachingIa", "objetivoMedibleCoachingIa", "compromisoAgenteIa"].forEach(id => {
        document.getElementById(id)?.addEventListener("input", marcarPlanCoachingPendienteIa);
        document.getElementById(id)?.addEventListener("change", marcarPlanCoachingPendienteIa);
    });

    document.getElementById("btnMarcarCoachingRealizadoIa")?.addEventListener("click", async () => {
        await marcarCoachingRealizadoIa();
    });

    document.getElementById("formSeguimientoCoachingIa")?.addEventListener("submit", async (event) => {
        event.preventDefault();
        await guardarSeguimientoCoachingIa();
    });

    document.getElementById("btnCerrarCoachingIa")?.addEventListener("click", async () => {
        await cerrarCoachingDesdeSeguimientoIa();
    });

    document.getElementById("btnVerEvidenciaCoachingIa")?.addEventListener("click", irEvidenciaCoachingIa);
}

async function subirYAnalizarIa() {
    const archivo = document.getElementById("audioIa").files?.[0];
    if (!archivo) {
        mostrarMensajeIa("Selecciona un audio para analizar.", "error");
        return;
    }

    if (!validarArchivoAudioIa(archivo)) return;

    if (!valorCarteraIa()) {
        mostrarMensajeIa("Selecciona una cartera para mantener la trazabilidad del análisis.", "error");
        return;
    }

    const btn = document.getElementById("btnAnalizarIa");
    btn.disabled = true;
    btn.textContent = "Procesando...";
    cambiarEstadoProceso("PENDIENTE");
    mostrarMensajeIa("Registrando audio para análisis...", "ok");

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
        mostrarMensajeIa("Audio registrado. Generando análisis con IA...", "ok");

        const analizar = await fetchIa(`${IA_FEEDBACK_BASE}/${uploadData.id_feedback}/analizar`, {
            method: "POST",
        }, 900000);
        const data = await leerJsonSeguro(analizar);
        if (!analizar.ok) throw new Error(data.detail || data.error || "No se pudo analizar la llamada.");

        cambiarEstadoProceso(data.estado || "FINALIZADO");
        renderResultadoIa(data);
        if (data.aviso_ia) {
            mostrarMensajeIa(`${data.aviso_ia}. Análisis generado correctamente.`, "ok");
        } else {
            mostrarMensajeIa("Análisis generado correctamente.", "ok");
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
        detalle.textContent = `${data.modelo_transcripcion || "Transcripción"} + ${data.modelo_analisis || "Análisis"}`;
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
        return normalizarTipoUsuario(localStorage.getItem("tipo") || localStorage.getItem("tipoUsuario") || localStorage.getItem("perfil"));
    }
    return String(localStorage.getItem("tipo") || localStorage.getItem("tipoUsuario") || localStorage.getItem("perfil") || "").trim().toUpperCase();
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

async function verAnalisisIa(idFeedback, tabDetalle = "revision") {
    try {
        const response = await fetchIa(`${IA_FEEDBACK_BASE}/${idFeedback}`, {}, 15000);
        const data = await leerJsonSeguro(response);
        if (!response.ok) throw new Error(data.detail || "No se pudo obtener el análisis.");
        cambiarEstadoProceso(data.estado || "PENDIENTE");
        renderResultadoIa(data);
        mostrarTabDetalleIa(tabDetalle);
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
            <td>${(row.score_final ?? row.score_calidad) != null ? `${Number(row.score_final ?? row.score_calidad).toFixed(1)}%` : escapeHtml(row.nivel_oportunidad_mejora || "-")}</td>
            <td>${badgeRevision(row.estado_revision)}</td>
            <td>${badgeEstado(row.estado)}</td>
            <td><button class="historial-action" type="button" onclick="verAnalisisIa(${row.id_feedback})">Ver análisis</button></td>
        </tr>
    `).join("");
}

function renderResultadoIa(data) {
    resultadoActualIa = data;
    activarVistaResultadoIa(true);
    document.getElementById("resultadoVacioIa").classList.add("oculto");
    document.getElementById("resultadoContenidoIa").classList.remove("oculto");
    setDetalleSgcVisibleIa(false);
    actualizarPestanasPorPautaIa(data);

    setText("trazaAudioIa", data.archivo_nombre || "-");
    setText("trazaSupervisorIa", data.supervisor || "-");
    setText("trazaRevisionIa", data.estado_revision || "PENDIENTE");
    setText("resultadoNivelIa", formatearRiesgoVisibleIa(data.nivel_oportunidad_mejora));
    setText("resumenIa", data.resumen || "-");
    setText("tipoContactoIa", data.tipo_contacto || "-");
    setText("resultadoGestionIa", data.resultado_gestion || "-");
    setText("objecionIa", data.objecion_principal || "-");
    const scoreMostrado = data.score_final ?? data.score_normalizado ?? data.score_calidad;
    setText("scoreCalidadIa", scoreMostrado != null ? `${Number(scoreMostrado).toFixed(1)} / 100${detallePesoScoreIa(data)}` : "-");
    setText("scorePreliminarIa", data.score_calidad_ia != null ? `${Number(data.score_calidad_ia).toFixed(1)} / 100` : "-");
    setText("nivelRiesgoDetalleIa", formatearRiesgoVisibleIa(data.nivel_oportunidad_mejora));
    setText("faltaAnulanteIa", data.falta_anulante ? "Si" : "No");
    setText("revisionHumanaIa", data.requiere_revision_humana ? "Sí" : "No");
    aplicarEstadoCardsDetalleIa(data);
    pintarFichaRevisionIa(data);
    setText("estadoRecalibracionIa", formatearEstadoRecalibracionIa(data.estado_recalibracion));
    setText("recomendacionIa", data.recomendaciones || "-");
    setText("guionIa", data.guion_sugerido || "-");

    const evaluacionItems = evaluacionCalidadItemsIa(data);
    const hallazgosSgc = hallazgosSgcItemsIa(data);
    pintarEvaluacionCalidad(evaluacionItems);
    pintarResumenSegmentos(evaluacionItems);
    pintarCabeceraFichaSgcIa(data);
    // La ficha es auditable: muestra todos los criterios de la matriz. Los
    // hallazgos consolidados siguen alimentando el resumen ejecutivo aparte.
    pintarFichaAuditoriaSgcIa(evaluacionItems, data);
    pintarCierreFichaSgcIa(data);
    pintarHabilidadesBlandas(data.habilidades_blandas_lista || habilidadesBlandasDesdeEvaluacionIa(evaluacionItems));
    pintarLista("fortalezasIa", data.fortalezas_lista || []);
    pintarLista("alertasIa", data.alertas_lista || []);
    pintarTopCriticosIa(hallazgosSgc);
    pintarEvidenciasDetalleIa(data);
    pintarEvidenciaDestacadaIa(data.evidencias_clave_lista || [], data);
    pintarCalibracionDetalleIa(data);
    pintarHistorialDetalleIa(data.historial_lista || []);
    cargarRevisionEnFormulario(data);
    cargarCoachingEnFormulario(data);
    mostrarTabDetalleIa("revision");
}

function aplicarEstadoCardsDetalleIa(data) {
    aplicarClaseEstadoCardIa("cardNivelRiesgoIa", claseRiesgoCardIa(data.nivel_oportunidad_mejora));
    aplicarClaseEstadoCardIa("cardFaltaAnulanteIa", data.falta_anulante ? "state-danger" : "state-ok");
    aplicarClaseEstadoCardIa("cardRevisionHumanaIa", data.requiere_revision_humana ? "state-warning" : "state-ok");
    aplicarClaseEstadoCardIa("cardResultadoGestionIa", claseResultadoGestionCardIa(data.resultado_gestion));
}

function pintarFichaRevisionIa(data = {}) {
    const id = data.id_feedback || "-";
    const agente = data.agente || "Sin agente asociado";
    const fecha = data.fecha_llamada || data.fecha_creacion;
    const scoreTecnico = scoreTecnicoFichaIa(data);
    const scoreIa = scoreTecnico ?? scoreIaPreliminarResumenIa(data);
    const scoreFinal = scoreValidadoResumenIa(data);
    const descalificada = esLlamadaDescalificadaFichaIa(data);
    const riesgo = formatearRiesgoVisibleIa(data.nivel_oportunidad_mejora || data.nivel_riesgo);
    const errorCritico = Boolean(data.error_critico || data.falta_anulante || Number(data.total_puntos_criticos || 0) > 0);
    const revision = estadoRevisionEvaluacionIa(data);

    setText("detalleBreadcrumbIa", `Evaluaciones / Evaluación #${id}`);
    setText("detalleTituloIa", "Ficha de evaluación");
    setText("detalleSubtituloIa", `Llamada del ${formatoFecha(fecha)} · ${data.cartera || "Sin cartera"}`);
    setText("resultadoNivelIa", descalificada ? "DESCALIFICADA" : riesgo);
    setText("revisionHumanaBadgeIa", data.requiere_revision_humana ? "Requiere revisión humana" : revision.texto);
    const revisionBadge = document.getElementById("revisionHumanaBadgeIa");
    if (revisionBadge) revisionBadge.className = `evaluation-badge ${data.requiere_revision_humana ? "warn" : revision.clase}`;
    pintarBannerDescalificacionIa(data, { descalificada, scoreTecnico });
    actualizarTextoDecisionConfirmarIa(descalificada);

    const meta = document.getElementById("detalleMetaIa");
    if (meta) {
        meta.innerHTML = [
            ["Tipo de llamada", tipoLlamadaVisibleIa(data)],
            ["Agente", agente],
            ["Score IA", formatoScoreSobre100Ia(scoreIa)],
            ["Score final", scoreFinal == null ? "Pendiente" : formatoScoreSobre100Ia(scoreFinal)],
            ["Error crítico", errorCritico ? "Sí" : "No"],
            ["Revisión", revision.texto],
        ].map(([label, value]) => `
            <article>
                <span>${escapeHtml(label)}</span>
                <strong title="${escapeHtml(value)}">${escapeHtml(value)}</strong>
            </article>
        `).join("");
    }

    setText("resumenEjecutivoFichaIa", data.resumen || "Sin resumen ejecutivo disponible.");
    pintarAudioYTranscripcionFichaIa(data);
    pintarClasificacionFichaIa(data);
    pintarDimensionesFichaIa(evaluacionCalidadItemsIa(data), data);
    pintarHallazgosAcordeonIa(evaluacionCalidadItemsIa(data), data);
    pintarFeedbackObservacionesFichaIa(data);
    limpiarDecisionSupervisorIa(data);
    actualizarDecisionSupervisorIa();
}

function pintarBannerDescalificacionIa(data = {}, contexto = {}) {
    const banner = document.getElementById("descalificacionBannerIa");
    if (!banner) return;
    const descalificada = contexto.descalificada ?? esLlamadaDescalificadaFichaIa(data);
    if (!descalificada) {
        banner.classList.add("oculto");
        banner.innerHTML = "";
        return;
    }
    const hallazgo = hallazgoAnulanteFichaIa(data);
    const scoreTecnico = contexto.scoreTecnico ?? scoreTecnicoFichaIa(data);
    const estadoTecnico = data.estado_tecnico || (scoreTecnico != null && scoreTecnico >= 85 ? "Aprobada" : "No aprobada");
    const motivo = data.motivo_descalificacion || hallazgo.motivo || hallazgo.hallazgo || "Falta anulante detectada";
    const evidencia = evidenciaAnulanteFichaIa(data, hallazgo);
    const desviacion = desviacionGestionFichaIa(data, hallazgo);
    banner.classList.remove("oculto");
    banner.innerHTML = `
        <div class="disqualification-title">
            <strong>LLAMADA DESCALIFICADA — FALTA ANULANTE</strong>
        </div>
        <div class="disqualification-grid">
            <article><span>Motivo principal</span><strong>${escapeHtml(motivo)}</strong></article>
            <article><span>Evidencia anulante</span><strong>${escapeHtml(evidencia)}</strong></article>
            <article><span>Desviación de gestión</span><strong>${escapeHtml(desviacion)}</strong></article>
            <article><span>Score técnico</span><strong>${escapeHtml(formatoScoreSobre100Ia(scoreTecnico))}</strong></article>
            <article><span>Estado técnico</span><strong>${escapeHtml(estadoTecnico)}</strong></article>
            <article><span>Estado de calidad</span><strong>Descalificada</strong></article>
            <article><span>Acción sugerida</span><strong>Coaching inmediato y revisión del supervisor</strong></article>
        </div>
    `;
}

function actualizarTextoDecisionConfirmarIa(descalificada = false) {
    const opcion = document.querySelector("input[name='decisionSupervisorIa'][value='confirmar'] + span");
    if (opcion) opcion.textContent = descalificada ? "Confirmar descalificación IA" : "Confirmar evaluación IA";
}

function pintarAudioYTranscripcionFichaIa(data = {}) {
    const wrap = document.getElementById("audioPlayerWrapIa");
    const audioUrl = data.audio_url || data.url_audio || "";
    const audioSrcBase = resolverAudioUrlIa(audioUrl);
    const audioSrc = audioSrcBase ? `${audioSrcBase}${audioSrcBase.includes("?") ? "&" : "?"}inline=1` : "";
    const duracion = data.duracion_segundos ? formatoDuracionIa(Number(data.duracion_segundos)) : "Duración no disponible";
    setText("audioDetalleMetaIa", `${data.archivo_nombre || "Audio"} · ${duracion}`);
    const diarizacion = tieneDiarizacionRealIa(data);
    setText("confianzaTranscripcionIa", diarizacion
        ? `Transcripción con separación de interlocutores · Confianza: ${formatearConfianzaEvaluacionIa(data.confianza_evaluacion || data.calidad_transcripcion)}`
        : "Separación de interlocutores no disponible.");
    if (wrap) {
        wrap.innerHTML = audioUrl
            ? `<audio id="audioRevisionIa" controls preload="metadata"><source src="${escapeHtml(audioSrc)}" type="${escapeHtml(tipoMimeAudioIa(data.archivo_nombre || audioUrl))}"></audio>`
            : `<div class="audio-unavailable"><strong>Audio pendiente de integración</strong><span>El backend guarda la ruta del archivo, pero aún no expone una URL segura para reproducirlo desde la ficha.</span></div>`;
        const audio = document.getElementById("audioRevisionIa");
        audio?.addEventListener("loadedmetadata", () => {
            const activo = document.querySelector(".transcript-tabs button.active")?.dataset.transcriptTab || "limpia";
            mostrarTranscripcionIa(activo);
        }, { once: true });
    }
    mostrarTranscripcionIa("limpia");
}

function pintarClasificacionFichaIa(data = {}) {
    const el = document.getElementById("clasificacionLlamadaIa");
    if (!el) return;
    const confianzaRaw = data.confianza_evaluacion || data.calidad_transcripcion;
    const confianza = formatearConfianzaEvaluacionIa(confianzaRaw);
    const confianzaBaja = confianzaEsBajaIa(confianzaRaw);
    const tipo = tipoLlamadaVisibleIa(data);
    el.innerHTML = `
        <div>
            <span>Tipo e intención</span>
            <strong>${escapeHtml(confianzaBaja ? `Clasificación preliminar: ${tipo}` : tipo)} · ${escapeHtml(data.objetivo_principal || data.tipo_contacto || "Sin información")}</strong>
        </div>
        <div>
            <span>Tipo de llamada supervisor</span>
            <select id="tipoLlamadaSupervisorIa" class="inline-select">
                ${opcionesTipoLlamadaIa(tipo)}
            </select>
        </div>
        <div><span>Confianza de clasificación</span><strong>${escapeHtml(confianzaBaja ? "BAJA" : confianza)}</strong></div>
        <div><span>Resultado de llamada</span><strong>${escapeHtml(textoHumanoIa(data.resultado_gestion) || "Sin información")}</strong></div>
        <div><span>Contexto previo</span><strong>${escapeHtml(data.contexto_previo || "Contexto no disponible")}</strong></div>
        ${renderTipificacionesSugeridasIa(data.tipificaciones_sugeridas || data.resumen_sgc?.tipificaciones_sugeridas || [])}
    `;

    const alertas = document.getElementById("alertasFichaIa");
    if (!alertas) return;
    const textos = [];
    if (data.requiere_revision_humana || confianzaBaja) textos.push(data.motivo_revision || "Revisión humana requerida por confianza baja o criterios contextuales.");
    if (data.falta_anulante) textos.push(`Falta anulante detectada${data.frase_anulante ? `: ${data.frase_anulante}` : "."}`);
    if (Array.isArray(data.alertas_lista)) textos.push(...data.alertas_lista.slice(0, 2));
    const alertasUnicas = deduplicarTextosAlertaFichaIa(textos);
    alertas.innerHTML = alertasUnicas.length
        ? alertasUnicas.map(item => `<p>${escapeHtml(item.texto)}${item.total > 1 ? ` · ${item.total} criterios relacionados` : ""}</p>`).join("")
        : `<p>Sin alertas o contradicciones registradas.</p>`;
}

function renderTipificacionesSugeridasIa(items = []) {
    if (!Array.isArray(items) || !items.length) return "";
    return items.slice(0, 2).map((item, index) => {
        const label = [item.categoria, item.tipificacion].filter(Boolean).join(" - ") || "Tipificación sugerida";
        const confianza = item.confianza_porcentaje != null ? ` · ${Number(item.confianza_porcentaje).toFixed(0)}%` : "";
        const descripcion = item.descripcion || item.justificacion || "";
        return `
        <div>
            <span>Tipificación sugerida ${index === 0 ? "principal" : "alternativa"}</span>
            <strong>${escapeHtml(label)}${escapeHtml(confianza)}</strong>
            ${descripcion ? `<small>${escapeHtml(descripcion)}</small>` : ""}
        </div>
    `}).join("");
}

function deduplicarTextosAlertaFichaIa(textos = []) {
    const mapa = new Map();
    textos.forEach(textoOriginal => {
        const texto = String(textoOriginal || "").trim();
        if (!texto) return;
        const normalizado = normalizarTextoComparacionIa(texto);
        const key = claveAlertaResumenIa(normalizado);
        const actual = mapa.get(key);
        if (actual) {
            actual.total += 1;
            if (texto.length > actual.texto.length) actual.texto = texto;
            return;
        }
        mapa.set(key, { texto: texto.replace(/\s+/g, " ").trim().replace(/\.+$/, ""), total: 1 });
    });
    return [...mapa.values()];
}

function claveAlertaResumenIa(textoNormalizado = "") {
    const texto = String(textoNormalizado || "");
    if ((texto.includes("exposicion") || texto.includes("expuso") || texto.includes("deuda")) && texto.includes("validacion") && texto.includes("titular")) {
        return "exposicion deuda sin validacion titularidad";
    }
    if (texto.includes("deuda") && texto.includes("antes") && texto.includes("confirm") && (texto.includes("identidad") || texto.includes("titular"))) {
        return "exposicion deuda sin validacion titularidad";
    }
    return texto.replace(/\b(de|la|el|sin|con|antes|del)\b/g, " ").replace(/\s+/g, " ").trim();
}

function pintarDimensionesFichaIa(items = [], data = {}) {
    const el = document.getElementById("dimensionesFichaIa");
    if (!el) return;
    if (tienePautaAplicadaIa(data)) {
        const bloques = new Map();
        items.map(itemSgcIa).forEach(item => {
            const bloque = bloquePautaItemIa(item, data);
            const actual = bloques.get(bloque) || { bloque, nota: 0, peso: 0, total: 0, noAplica: 0, revision: 0 };
            const resultado = String(item.resultado || item.calificacion || "").toLowerCase();
            actual.total += 1;
            if (resultado.includes("no aplica") || resultado.includes("no evaluable")) {
                actual.noAplica += 1;
            } else {
                actual.peso += Number(item.peso ?? item.puntaje_maximo ?? 0);
                actual.nota += Number(item.nota ?? item.puntaje_obtenido ?? 0);
            }
            if (resultado.includes("revision") || resultado.includes("revisión")) actual.revision += 1;
            bloques.set(bloque, actual);
        });
        const cards = [...bloques.values()].map(item => {
            const score = item.peso ? (item.nota / item.peso) * 100 : null;
            const estado = !item.total ? "Sin criterios" : item.total === item.noAplica ? "No evaluable" : item.revision ? "Revisión humana" : score >= 85 ? "Cumple" : score >= 60 ? "Parcial" : "No cumple";
            const clase = estado.includes("Cumple") ? "ok" : estado.includes("Parcial") || estado.includes("Revisión") ? "warn" : estado.includes("No evaluable") ? "info" : "risk";
            return `<article class="${clase}"><span>${escapeHtml(item.bloque)}</span><strong>${score == null ? estado : `${formatoPeso(item.nota)}/${formatoPeso(item.peso)}`}</strong><div class="summary-progress"><i style="width:${score == null ? 0 : Math.max(3, Math.min(100, score))}%"></i></div><small>${escapeHtml(estado)}</small></article>`;
        }).join("");
        el.innerHTML = `${cards}<article class="dimension-total"><span>Total de la pauta</span><strong>${escapeHtml(formatoScoreSobre100Ia(scoreTecnicoFichaIa(data)))}</strong><small>${escapeHtml(data.pauta || "Pauta aplicada")}${data.pauta_version ? ` · v${escapeHtml(data.pauta_version)}` : ""}</small></article>`;
        return;
    }
    const dimensiones = [
        { key: "Cumplimiento", label: "Cumplimiento y control de contacto", max: 15 },
        { key: "Diagnóstico", label: "Diagnóstico", max: 15 },
        { key: "Gestión de solución", label: "Gestión de solución y negociación", max: 35 },
        { key: "Cierre verificable", label: "Cierre verificable", max: 30 },
        { key: "Experiencia y ética", label: "Experiencia y ética", max: 5 },
    ];
    const segmentos = new Map(dimensiones.map(item => [item.key, { nota: 0, peso: 0, total: 0, noAplica: 0, revision: 0 }]));
    items.forEach(raw => {
        const item = itemSgcIa(raw);
        const resultado = String(item.resultado || "").toLowerCase();
        const segmento = formatearSegmentoIa(item.segmento || item.segmento_copc || "Sin segmento");
        const actual = segmentos.get(segmento) || { peso: 0, nota: 0, total: 0, noAplica: 0, revision: 0 };
        actual.total += 1;
        if (resultado.includes("no aplica")) {
            actual.noAplica += 1;
        } else {
            actual.peso += Number(item.peso ?? item.puntaje_maximo ?? 0);
            actual.nota += Number(item.nota ?? item.puntaje_obtenido ?? 0);
        }
        if (String(item.resultado || "").toLowerCase().includes("revision")) actual.revision += 1;
        segmentos.set(segmento, actual);
    });
    const totalTecnico = scoreTecnicoFichaIa(data);
    const cards = dimensiones.map(dimension => {
        const item = segmentos.get(dimension.key);
        const nota = item ? Number(item.nota || 0) : 0;
        const score = item && item.total && item.total !== item.noAplica ? (nota / dimension.max) * 100 : null;
        const estado = !item || !item.total ? "No evidenciado" : item.total === item.noAplica ? "No aplica" : item.revision ? "Revisión humana" : score >= 85 ? "Cumple" : score >= 60 ? "Parcial" : "No cumple";
        const clase = estado.includes("Cumple") ? "ok" : estado.includes("Parcial") ? "warn" : estado.includes("No aplica") || estado.includes("No evidenciado") ? "info" : "risk";
        const avance = score == null ? 0 : Math.max(3, Math.min(100, score));
        return `
            <article class="${clase}">
                <span>${escapeHtml(dimension.label)}</span>
                <strong>${score == null ? estado : `${formatoPeso(nota)}/${formatoPeso(dimension.max)}`}</strong>
                <div class="summary-progress"><i style="width:${avance}%"></i></div>
                <small>${escapeHtml(estado)}</small>
            </article>
        `;
    }).join("");
    el.innerHTML = `
        ${cards}
        <article class="dimension-total">
            <span>Total técnico</span>
            <strong>${escapeHtml(formatoScoreSobre100Ia(totalTecnico))}</strong>
            <small>Modelo SGC · Base técnica COPC adaptada</small>
        </article>
    `;
}

function pintarHallazgosAcordeonIa(items = [], data = {}) {
    const el = document.getElementById("hallazgosAcordeonIa");
    if (!el) return;
    const fuente = hallazgosSgcItemsIa(data).length ? hallazgosSgcItemsIa(data) : items;
    const normalizados = repararHallazgosContextualesFichaIa(
        fuente.map(itemSgcIa).map(normalizarHallazgoFichaIa),
        data,
    );
    const rowsBase = normalizados
        .filter(esHallazgoAccionableFichaIa)
        .filter(item => !esHallazgoGenericoSinEvidenciaIa(item));
    const { rows, duplicados } = deduplicarHallazgosFichaIa(rowsBase);
    const rowsResumen = seleccionarHallazgosResumenSgcIa(rows, 3, 6);
    const grupos = SGC_GRUPOS_IA.map(grupo => ({ grupo, rows: rowsResumen.filter(item => item.grupo_error_sgc === grupo) }));
    const totalCriticos = rows.filter(esHallazgoCriticoFichaIa).length;
    const totalNoCriticos = rows.filter(esHallazgoNoCriticoFichaIa).length;
    const totalCriticosResumen = rowsResumen.filter(esGrupoCriticoSgcFichaIa).length;
    const totalNoCriticosResumen = rowsResumen.filter(esHallazgoNoCriticoFichaIa).length;
    const maxIndex = Math.max(0, grupos.reduce((best, grupo, index) => criticidadGrupoIa(grupo.rows) > criticidadGrupoIa(grupos[best]?.rows || []) ? index : best, 0));
    auditoriaFichaIa = {
        criterio: "factor_sgc válido; fallback item COPC",
        resultado: "calificacion; fallback resultado",
        grupo: "grupo_error_sgc normalizado a los 4 grupos SGC/PEC",
        grupos: Object.fromEntries(SGC_GRUPOS_IA.map(grupo => [grupo, rows.filter(item => item.grupo_error_sgc === grupo).length])),
        alertasAntesDeduplicar: rowsBase.length,
        alertasDespuesDeduplicar: rows.length,
        duplicadosEliminados: duplicados,
        noAplica: "No aplica solo como estado/aplicabilidad; se excluye de hallazgos y del denominador penalizable",
        decisionInicial: "ninguna",
        validarInicial: "deshabilitado",
        gruposAbiertosIniciales: grupos
            .map((grupo, index) => index === maxIndex ? grupo.grupo : null)
            .filter(Boolean),
    };
    window.auditoriaFichaIa = auditoriaFichaIa;
    const filtros = document.getElementById("filtrosHallazgosIa");
    if (filtros) {
        const destinoAuditoria = tienePautaAplicadaIa(data) ? "Ver criterios de la pauta" : "Ver ficha SGC/PEC";
        filtros.innerHTML = `
            <span title="La ficha muestra los hallazgos más relevantes; usa ${escapeHtml(destinoAuditoria)} para auditoría total.">Principales ${formatoNumero(rowsResumen.length)} de ${formatoNumero(rows.length)}</span>
            <button class="active" type="button" data-findings-filter="todos" onclick="filtrarHallazgosFichaIa('todos')">Todos ${formatoNumero(rowsResumen.length)}</button>
            <button type="button" data-findings-filter="criticos" onclick="filtrarHallazgosFichaIa('criticos')">Críticos ${formatoNumero(totalCriticosResumen)}</button>
            <button type="button" data-findings-filter="no-criticos" onclick="filtrarHallazgosFichaIa('no-criticos')">No críticos ${formatoNumero(totalNoCriticosResumen)}</button>
        `;
    }
    el.innerHTML = grupos.map(({ grupo, rows: grupoRows }, index) => `
        <section class="finding-group ${index === maxIndex ? "" : "collapsed"}" data-critical-count="${grupoRows.filter(esGrupoCriticoSgcFichaIa).length}" data-noncritical-count="${grupoRows.filter(esHallazgoNoCriticoFichaIa).length}">
            <button type="button" class="finding-group-head" onclick="toggleHallazgoGrupoIa(this)">
                <span>${index + 1}. ${escapeHtml(grupo.toUpperCase())}</span>
                <b>${formatoNumero(grupoRows.length)}</b>
            </button>
            <div class="finding-group-body">
                ${grupoRows.length ? grupoRows.map(item => renderHallazgoFichaIa(item, data)).join("") : `<div class="empty-segment">Sin hallazgos registrados para este grupo.</div>`}
            </div>
        </section>
    `).join("");
}

function seleccionarHallazgosResumenSgcIa(rows = [], maxPorGrupo = 3, maxTotal = 6) {
    const ordenados = [...rows].sort((a, b) => prioridadHallazgoResumenIa(b) - prioridadHallazgoResumenIa(a));
    const conteo = new Map();
    return ordenados.filter(item => {
        const seleccionados = [...conteo.values()].reduce((sum, count) => sum + count, 0);
        if (seleccionados >= maxTotal) return false;
        const grupo = item.grupo_error_sgc || "Sin grupo";
        const actual = conteo.get(grupo) || 0;
        const maxGrupo = esHallazgoNoCriticoFichaIa(item) ? Math.min(2, maxPorGrupo) : maxPorGrupo;
        if (actual >= maxGrupo) return false;
        conteo.set(grupo, actual + 1);
        return true;
    });
}

function prioridadHallazgoResumenIa(item = {}) {
    const resultado = resultadoHallazgoFichaIa(item).toLowerCase();
    const grupo = String(item.grupo_error_sgc || "").toLowerCase();
    const factor = normalizarTextoComparacionIa(item.factor_sgc || criterioHallazgoIa(item));
    let score = 0;
    if (item.falta_anulante || item.puede_descalificar) score += 100;
    if (grupo.includes("cumplimiento")) score += 35;
    if (grupo.includes("usuario")) score += 30;
    if (grupo.includes("negocio")) score += 25;
    if (resultado.includes("no cumple") || resultado.includes("no evidenciado")) score += 20;
    if (resultado.includes("revision") || resultado.includes("revisión")) score += 14;
    if (resultado.includes("parcial")) score += 8;
    if (evidenciaEsTextualFichaIa(evidenciaHallazgoFichaIa(item, resultadoActualIa || {}))) score += 5;
    if (factor.includes("manejo de objeciones")) score += 18;
    if (factor.includes("induccion a pago") || factor.includes("induccion al pago")) score += 18;
    if (factor.includes("cierre verificable")) score += 18;
    if (factor.includes("lenguaje claro y presion profesional")) score += 18;
    if (factor.includes("presentacion adaptacion") || factor.includes("presentacion y adaptacion")) score += 12;
    if (factor.includes("claridad de montos")) score += 12;
    if (factor.includes("empatia aplicada")) score += 12;
    if (factor.includes("razon de no pago") || factor.includes("fecha probable de ingreso")) score -= 18;
    return score;
}

function renderHallazgoFichaIa(item = {}, data = {}) {
    const resultado = resultadoHallazgoFichaIa(item);
    const calificacion = calificacionSgcVisibleFichaIa(resultado);
    const momento = timestampValidoIa(item.momento || item.timestamp) ? (item.momento || item.timestamp) : "";
    const momentoParam = encodeURIComponent(momento);
    const criterio = criterioHallazgoIa(item);
    const itemParam = encodeURIComponent(criterio);
    const audioDisponible = Boolean(data.audio_url || data.url_audio);
    const evidenciaTemporal = audioDisponible && timestampValidoIa(momento);
    const criteriosRelacionados = item.criterios_relacionados?.length || 1;
    const hallazgoBase = detalleHallazgoEnriquecidoIa(item);
    const hallazgoTexto = criteriosRelacionados > 1
        ? `${hallazgoBase} · ${criteriosRelacionados} criterios relacionados`
        : hallazgoBase;
    const evidencia = evidenciaHallazgoFichaIa(item, data);
    return `
        <article class="finding-row" data-critical="${esHallazgoCriticoFichaIa(item) ? "1" : "0"}">
            <div><span>Factor</span><strong>${escapeHtml(criterio)}</strong>${criteriosRelacionados > 1 ? `<small>${criteriosRelacionados} criterios relacionados</small>` : ""}</div>
            <div><span>Calificación</span>${badgeCalificacionSgcFichaIa(calificacion)}</div>
            <div><span>Motivo</span><p>${escapeHtml(hallazgoTexto)}</p></div>
            <div><span>Evidencia</span><p>${escapeHtml(evidencia)}</p>${momento ? `<small>${escapeHtml(momento)}</small>` : ""}</div>
            <div class="finding-actions">
                <button class="btn-light btn-small" type="button" ${evidenciaTemporal ? `onclick="irAEvidenciaAudioIa('${momentoParam}', true)"` : "disabled title=\"Evidencia temporal no disponible\""}>Ver evidencia</button>
                <button class="btn-light btn-small editable-criteria-action" type="button" onclick="prepararRecalibracionItemIa('${itemParam}', true)" disabled>Editar resultado</button>
            </div>
        </article>
    `;
}

function detalleHallazgoEnriquecidoIa(item = {}) {
    const candidatos = [
        item.motivo,
        item.hallazgo,
        item.lectura_ia,
        item.conducta_observada,
    ];
    const vistos = new Set();
    for (const candidato of candidatos) {
        const texto = String(candidato || "").trim();
        const key = normalizarTextoComparacionIa(texto);
        if (!texto || vistos.has(key) || textoEsGenericoHallazgoIa(texto)) continue;
        vistos.add(key);
        return texto;
    }
    return "Requiere revisión humana.";
}

function normalizarHallazgoFichaIa(item = {}) {
    const base = { ...item };
    base.grupo_error_sgc = normalizarGrupoSgcFichaIa(base.grupo_error_sgc, base);
    base.factor_sgc = criterioHallazgoIa(base);
    base.calificacion = resultadoHallazgoFichaIa(base);
    return base;
}

function detallePesoScoreIa(data = {}) {
    const bruto = Number(data.score_bruto);
    const aplicable = Number(data.peso_aplicable);
    if (!Number.isFinite(bruto) || !Number.isFinite(aplicable) || aplicable <= 0) return "";
    const noAplica = Number(data.peso_no_aplica || 0);
    const noEvaluable = Number(data.peso_no_evaluable || 0);
    const extras = [];
    if (noAplica > 0) extras.push(`${formatoPeso(noAplica)} no aplica`);
    if (noEvaluable > 0) extras.push(`${formatoPeso(noEvaluable)} no evaluable`);
    return ` · ${formatoPeso(bruto)}/${formatoPeso(aplicable)} pts aplicables${extras.length ? ` (${extras.join(", ")})` : ""}`;
}

function repararHallazgosContextualesFichaIa(items = [], data = {}) {
    return items.map(item => {
        const copia = { ...item };
        if (esHallazgoAccionableFichaIa(copia) && !evidenciaEsTextualFichaIa(evidenciaHallazgoFichaIa(copia, data))) {
            copia.resultado = "Requiere revisión";
            copia.calificacion = "Requiere revisión";
            copia.requiere_revision = true;
        }
        copia.grupo_error_sgc = normalizarGrupoSgcFichaIa(copia.grupo_error_sgc, copia);
        copia.factor_sgc = criterioHallazgoIa(copia);
        return copia;
    });
}

function buscarHallazgoPorCodigoIa(items = [], codigo = "") {
    const clave = normalizarTextoComparacionIa(codigo);
    return items.find(item => normalizarTextoComparacionIa(codigoCriterioHallazgoIa(item)) === clave);
}

function extraerCitaFichaIa(texto = "", patrones = []) {
    const fuente = String(texto || "");
    for (const patron of patrones) {
        const match = fuente.match(patron);
        if (match?.[0]) return match[0].replace(/\s+/g, " ").trim();
    }
    return "";
}

function normalizarGrupoSgcFichaIa(grupo, item = {}) {
    const texto = String(grupo || "").trim().toLowerCase();
    const encontrado = SGC_GRUPOS_IA.find(nombre => nombre.toLowerCase() === texto);
    if (encontrado) return encontrado;
    return clasificarSgcItemIa({ ...item, grupo_error_sgc: "" }).grupo;
}

function criterioHallazgoIa(item = {}) {
    const candidatos = [
        item.factor_sgc,
        item.factor,
        item.nombre_criterio,
        item.nombre,
        item.item_copc,
        itemCopcVisibleIa(item),
        item.item,
        item.criterio,
    ];
    for (const candidato of candidatos) {
        const texto = String(candidato || "").trim();
        if (texto && !/^(no aplica|na|n\/a|-|null|undefined)$/i.test(texto)) return texto;
    }
    return "Criterio no identificado";
}

function resultadoHallazgoFichaIa(item = {}) {
    const resultado = String(item.calificacion || item.resultado || "").trim();
    if (/requiere[_\s-]*revision|requiere[_\s-]*revisión|revision humana|revisión humana/i.test(resultado)) return "Requiere revisión";
    if (/no evaluable/i.test(resultado)) return "No evaluable";
    if (/no aplica/i.test(resultado)) return "No aplica";
    if (/no evidenciado/i.test(resultado)) return "No evidenciado";
    if (/no cumple/i.test(resultado)) return "No cumple";
    if (/parcial/i.test(resultado)) return "Parcial";
    if (/cumple/i.test(resultado)) return "Cumple";
    return normalizarCalificacionItemIa(item);
}

function calificacionSgcVisibleFichaIa(resultado = "") {
    const texto = String(resultado || "").toLowerCase();
    if (texto.includes("no evaluable")) return "NO EVALUABLE";
    if (texto.includes("no aplica")) return "NA - NO APLICA";
    if (texto.includes("no cumple") || texto.includes("no evidenciado")) return "NC - NO CUMPLE";
    if (texto.includes("revision") || texto.includes("revisión") || texto.includes("parcial")) return "REVISIÓN HUMANA";
    if (texto.includes("cumple")) return "C - CUMPLE";
    return "REVISIÓN HUMANA";
}

function esHallazgoAccionableFichaIa(item = {}) {
    if (criterioHallazgoIa(item) === "Criterio no identificado") return false;
    const factor = normalizarTextoComparacionIa(item.factor_sgc || criterioHallazgoIa(item));
    const evidenciaValida = evidenciaEsTextualFichaIa(evidenciaHallazgoFichaIa(item, resultadoActualIa || {}));
    if (!evidenciaValida && !item.falta_anulante && !item.puede_descalificar) return false;
    if (factor.includes("conducta etica") && !evidenciaValida) return false;
    if (factor.includes("no abuso") && !evidenciaValida) return false;
    if (esHallazgoGenericoSinEvidenciaIa(item)) return false;
    if (item.falta_anulante || item.puede_descalificar) return true;
    const resultado = resultadoHallazgoFichaIa(item).toLowerCase();
    return resultado.includes("no cumple")
        || resultado.includes("revision")
        || resultado.includes("revisión")
        || resultado.includes("parcial");
}

function evidenciaHallazgoFichaIa(item = {}, data = {}) {
    const candidatos = [
        item.frase_textual,
        item.cita_textual,
        item.cita,
        item.evidencia,
        item.evidencia_textual,
    ];
    for (const candidato of candidatos) {
        const texto = String(candidato || "").trim();
        if (texto && evidenciaEsTextualFichaIa(texto)) return texto;
    }
    return "Sin cita textual registrada; requiere revisión humana.";
}

function evidenciaEsTextualFichaIa(texto = "") {
    const valor = String(texto || "").trim();
    const limpio = normalizarTextoComparacionIa(valor);
    if (!valor) return false;
    if (/^(no disponible|-|sin evidencia|no evidenciada|null|undefined)\.?$/i.test(valor)) return false;
    if (["no disponible", "sin evidencia", "no evidenciada", "null", "undefined"].includes(limpio)) return false;
    if (/revisar transcripci[oó]n/i.test(valor)) return false;
    if (/sin cita textual/i.test(valor)) return false;
    if (/no evidenciado en la respuesta ia/i.test(valor)) return false;
    if (/maltrato psicol[oó]gico expl[ií]cito/i.test(valor)) return false;
    return valor.length >= 8;
}

function textoEsGenericoHallazgoIa(texto = "") {
    const valor = normalizarTextoComparacionIa(texto);
    if (!valor) return true;
    const genericos = [
        "no evidenciado en la respuesta ia",
        "criterio pendiente de validacion",
        "no disponible",
        "revisar transcripcion",
        "sin cita textual registrada",
        "sin evidencia",
        "requiere revision humana",
        "validar este criterio con la transcripcion",
        "no se debe concluir incumplimiento",
    ];
    return genericos.some(item => valor.includes(item));
}

function esHallazgoGenericoSinEvidenciaIa(item = {}) {
    if (item.falta_anulante || item.puede_descalificar) return false;
    const evidenciaValida = evidenciaEsTextualFichaIa(evidenciaHallazgoFichaIa(item, resultadoActualIa || {}));
    if (evidenciaValida) return false;
    const textos = [
        item.motivo,
        item.hallazgo,
        item.evidencia,
        item.recomendacion,
        item.conducta_observada,
        item.lectura_ia,
    ];
    return textos.every(texto => textoEsGenericoHallazgoIa(texto));
}

function badgeCalificacionSgcFichaIa(texto = "") {
    const key = String(texto || "").toLowerCase();
    let clase = "review";
    if (key.startsWith("c -")) clase = "ok";
    if (key.startsWith("nc -")) clase = "bad";
    if (key.startsWith("na -")) clase = "na";
    return `<span class="sgc-rating ${clase}">${escapeHtml(texto || "REVISIÓN HUMANA")}</span>`;
}

function deduplicarHallazgosFichaIa(rows = []) {
    const mapa = new Map();
    let duplicados = 0;
    rows.forEach(item => {
        const key = claveDeduplicacionHallazgoIa(item);
        if (!key) return;
        if (mapa.has(key)) {
            const existente = mapa.get(key);
            existente.criterios_relacionados = [...(existente.criterios_relacionados || [criterioHallazgoIa(existente)]), criterioHallazgoIa(item)];
            existente.requiere_feedback = existente.requiere_feedback || item.requiere_feedback;
            existente.requiere_coaching = existente.requiere_coaching || item.requiere_coaching;
            if (!existente.hallazgo && item.hallazgo) existente.hallazgo = item.hallazgo;
            if (!existente.motivo && item.motivo) existente.motivo = item.motivo;
            if (!existente.evidencia && item.evidencia) existente.evidencia = item.evidencia;
            duplicados += 1;
            return;
        }
        mapa.set(key, { ...item, criterios_relacionados: [criterioHallazgoIa(item)] });
    });
    return { rows: [...mapa.values()], duplicados };
}

function claveDeduplicacionHallazgoIa(item = {}) {
    const codigo = codigoCriterioHallazgoIa(item);
    const factorKey = normalizarTextoComparacionIa(item.factor_sgc || criterioHallazgoIa(item));
    if (factorKey.includes("cierre verificable")) return "factor:cierre verificable";
    if (factorKey.includes("presentacion adaptacion") || factorKey.includes("presentacion y adaptacion")) return "factor:presentacion adaptacion propuesta";
    if (factorKey.includes("claridad de montos")) return "factor:claridad montos condiciones";
    if (codigo) return `codigo:${codigo}`;
    const piezas = [
        item.alerta,
        item.categoria,
        item.hallazgo,
        item.motivo,
        item.evidencia,
        item.recomendacion,
        criterioHallazgoIa(item),
    ].map(normalizarTextoComparacionIa).filter(Boolean);
    const texto = piezas.join(" ");
    if ((texto.includes("exposicion") || texto.includes("expuso") || texto.includes("deuda")) && texto.includes("validacion") && texto.includes("titular")) {
        return "exposicion deuda sin validacion titularidad";
    }
    if (texto.includes("deuda") && texto.includes("antes") && texto.includes("confirm") && texto.includes("identidad")) {
        return "exposicion deuda sin validacion titularidad";
    }
    return normalizarTextoComparacionIa(item.hallazgo || item.motivo || item.evidencia || criterioHallazgoIa(item));
}

function codigoCriterioHallazgoIa(item = {}) {
    const candidatos = [
        item.codigo_criterio,
        item.codigo,
        item.codigo_copc,
        String(item.item || "").match(/^\s*((?:PENC|PECUF|PECN|PECC)[\s._-]*\d+)/i)?.[1],
        String(item.item_copc || "").match(/^\s*((?:PENC|PECUF|PECN|PECC)[\s._-]*\d+)/i)?.[1],
        String(item.criterio || "").match(/^\s*((?:PENC|PECUF|PECN|PECC)[\s._-]*\d+)/i)?.[1],
        String(item.item || "").match(/^\s*(\d+\.\d+)/)?.[1],
        String(item.item_copc || "").match(/^\s*(\d+\.\d+)/)?.[1],
        String(item.criterio || "").match(/^\s*(\d+\.\d+)/)?.[1],
    ];
    const codigo = candidatos.find(valor => String(valor || "").trim());
    if (!codigo) return "";
    const texto = String(codigo).trim().toUpperCase();
    const mibanco = texto.match(/^(PENC|PECUF|PECN|PECC)[\s._-]*(\d+)$/);
    if (mibanco) return `${mibanco[1]}.${mibanco[2]}`;
    const legacy = texto.match(/^(\d+)[\s._-]+(\d+)$/);
    return legacy ? `${legacy[1]}.${legacy[2]}` : texto;
}

function normalizarTextoComparacionIa(value = "") {
    return String(value || "")
        .toLowerCase()
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "")
        .replace(/[^\p{L}\p{N}\s]/gu, " ")
        .replace(/\s+/g, " ")
        .trim();
}

function esHallazgoCriticoFichaIa(item = {}) {
    const resultado = resultadoHallazgoFichaIa(item).toLowerCase();
    const grupo = normalizarTextoComparacionIa(item.grupo_error_sgc || "");
    const esBrecha = resultado.includes("no cumple") || resultado.includes("no evidenciado") || resultado.includes("parcial") || resultado.includes("revision") || resultado.includes("revisión");
    const esGrupoCritico = esGrupoCriticoSgcFichaIa(item);
    return Boolean(item.falta_anulante || item.puede_descalificar || (esGrupoCritico && esBrecha));
}

function esGrupoCriticoSgcFichaIa(item = {}) {
    const grupo = normalizarTextoComparacionIa(item.grupo_error_sgc || "");
    return grupo.includes("errores criticos") && !grupo.includes("errores no criticos");
}

function esHallazgoNoCriticoFichaIa(item = {}) {
    const grupo = normalizarTextoComparacionIa(item.grupo_error_sgc || "");
    return grupo.includes("errores no criticos");
}

function criticidadGrupoIa(rows = []) {
    return rows.reduce((sum, item) => sum + (esHallazgoCriticoFichaIa(item) ? 3 : 1), 0);
}

function timestampValidoIa(value) {
    return /^\d{1,2}:\d{2}(?::\d{2})?$/.test(String(value || "").trim());
}

function filtrarHallazgosFichaIa(tipo = "todos") {
    document.querySelectorAll("[data-findings-filter]").forEach(btn => {
        btn.classList.toggle("active", btn.dataset.findingsFilter === tipo);
    });
    document.querySelectorAll("#hallazgosAcordeonIa .finding-group").forEach(group => {
        const criticos = Number(group.dataset.criticalCount || 0);
        const noCriticos = Number(group.dataset.noncriticalCount || 0);
        const visible = tipo === "todos" || (tipo === "criticos" && criticos > 0) || (tipo === "no-criticos" && noCriticos > 0);
        group.classList.toggle("oculto", !visible);
    });
}

function mostrarTranscripcionIa(tipo = "limpia") {
    const el = document.getElementById("transcripcionDetalleIa");
    if (!el) return;
    document.querySelectorAll(".transcript-tabs button").forEach(btn => {
        btn.classList.toggle("active", btn.dataset.transcriptTab === tipo);
    });
    const texto = resultadoActualIa?.transcripcion || "";
    const intervenciones = parseTranscripcionFichaIa(texto, tipo, resultadoActualIa || {});
    if (!intervenciones.length) {
        el.innerHTML = `<div class="empty-segment">Transcripción no disponible.</div>`;
        return;
    }
    el.innerHTML = intervenciones.map(item => {
        const tieneTimestamp = timestampValidoIa(item.momento);
        const tieneHablante = item.hablante && item.hablante !== "SIN DIARIZACIÓN";
        const labelMomento = item.aproximado ? `≈ ${item.momento}` : item.momento;
        const debugSpeaker = debugDiarizacionIa() && item.speakerOriginal
            ? `<small class="transcript-speaker-debug">${escapeHtml(item.speakerOriginal)}</small>`
            : "";
        return `
        <article class="transcript-line ${!tieneTimestamp ? "no-timestamp" : ""} ${!tieneHablante ? "no-speaker" : ""}">
            ${tieneTimestamp ? `<button type="button" ${item.aproximado ? "title=\"Momento aproximado calculado desde la duración del audio\"" : ""} onclick="irAEvidenciaAudioIa('${encodeURIComponent(item.momento)}', true)">${escapeHtml(labelMomento)}</button>` : ""}
            ${tieneHablante ? `<span class="${item.hablante === "CLIENTE" ? "client" : item.hablante === "AGENTE" ? "agent" : "neutral"}">${escapeHtml(item.hablante)}${debugSpeaker}</span>` : ""}
            <p>${escapeHtml(item.texto)}</p>
        </article>
    `;
    }).join("");
}

function parseTranscripcionFichaIa(texto = "", tipo = "limpia", data = {}) {
    if (tipo === "literal") {
        const segmentos = segmentosTranscripcionV2Ia(data);
        if (segmentos.length && esDiarizacionOriginalIa(data, texto)) {
            const continuoSegmentos = segmentos
                .slice()
                .sort(ordenSegmentosCanonicosIa)
                .map(segmento => segmento.texto_original || segmento.texto || segmento.transcripcion || segmento.frase || "")
                .filter(Boolean)
                .join(" ")
                .replace(/\s+/g, " ")
                .trim();
            return continuoSegmentos ? [{ momento: null, hablante: "", texto: continuoSegmentos, index: 0 }] : [];
        }
        const continuo = String(texto || "").replace(/\s+/g, " ").trim();
        return continuo ? [{ momento: null, hablante: "", texto: continuo, index: 0 }] : [];
    }
    const segmentos = segmentosTranscripcionV2Ia(data);
    if (segmentos.length) {
        const diarizada = esDiarizacionOriginalIa(data, texto);
        const visibles = diarizada
            ? segmentos.slice().sort(ordenSegmentosCanonicosIa)
            : segmentos.slice(0, tipo === "limpia" ? 30 : 120);
        const duracionAudio = duracionAudioRevisionIa();
        return visibles.map((segmento, index) => {
            const momentoReal = segmento.momento || segmento.timestamp || segmento.inicio || formatoTimestampDesdeSegundosIa(segmento.inicio_segundos);
            const momentoEstimado = momentoReal || diarizada ? null : timestampEstimadoSegmentoIa(visibles, index, duracionAudio);
            return {
                momento: momentoReal || momentoEstimado,
                aproximado: !momentoReal && Boolean(momentoEstimado),
                hablante: hablanteTranscripcionIa(segmento.hablante || segmento.rol || segmento.speaker_original || "NO_DETERMINADO"),
                texto: segmento.texto_limpio || segmento.texto_original || segmento.texto || segmento.transcripcion || segmento.frase || "",
                speakerOriginal: segmento.speaker_original || segmento.speakerOriginal || segmento.speaker || "",
                index,
            };
        }).filter(item => item.texto);
    }
    const lineas = String(texto || "").split(/\r?\n+/).map(x => x.trim()).filter(Boolean);
    const continuo = lineas.join(" ") || String(texto || "").trim();
    return continuo ? [{ momento: null, hablante: "", texto: continuo, index: 0 }] : [];
}

function segmentosTranscripcionV2Ia(data = {}) {
    const candidatos = [
        data.interlocutores?.segmentos,
        data.segmentos_interlocutores,
        data.transcripcion_segmentos,
        data.transcripcion_diarizada,
    ];
    const segmentos = candidatos.find(Array.isArray);
    return Array.isArray(segmentos) ? segmentos : [];
}

function esDiarizacionOriginalIa(data = {}, texto = "") {
    const metodo = String(data.interlocutores?.metodo || data.metodo_interlocutores || "").toUpperCase();
    return metodo === "DIARIZACION_ORIGINAL" || String(texto || "").includes("#TRANSCRIPCION_DIARIZADA_V1");
}

function ordenSegmentosCanonicosIa(a = {}, b = {}) {
    const inicioA = Number.isFinite(Number(a.inicio_segundos)) ? Number(a.inicio_segundos) : Number.POSITIVE_INFINITY;
    const inicioB = Number.isFinite(Number(b.inicio_segundos)) ? Number(b.inicio_segundos) : Number.POSITIVE_INFINITY;
    if (inicioA !== inicioB) return inicioA - inicioB;
    return Number(a.segmento_id || a.orden || 0) - Number(b.segmento_id || b.orden || 0);
}

function debugDiarizacionIa() {
    try {
        const params = new URLSearchParams(window.location.search || "");
        return params.get("debug_diarizacion") === "1" || localStorage.getItem("iaFeedbackDebugDiarizacion") === "1";
    } catch (_) {
        return false;
    }
}

function hablanteTranscripcionIa(value = "") {
    const texto = normalizarTextoComparacionIa(value);
    if (texto.includes("agente") || texto.includes("asesor") || texto.includes("gestor")) return "AGENTE";
    if (texto.includes("cliente") || texto.includes("titular") || texto.includes("deudor") || texto.includes("interlocutor")) return "CLIENTE";
    return "NO DETERMINADO";
}

function tieneDiarizacionRealIa(data = {}) {
    return segmentosTranscripcionV2Ia(data).length > 0;
}

function evaluacionCalidadItemsIa(data = {}) {
    if (Array.isArray(data.evaluacion_calidad_lista) && data.evaluacion_calidad_lista.length) {
        return data.evaluacion_calidad_lista;
    }
    if (Array.isArray(data.evaluacion_calidad) && data.evaluacion_calidad.length) {
        return data.evaluacion_calidad;
    }
    return [];
}

function tienePautaAplicadaIa(data = {}) {
    return Array.isArray(data.pauta_snapshot) && data.pauta_snapshot.length > 0;
}

function actualizarPestanasPorPautaIa(data = {}) {
    const esPauta = tienePautaAplicadaIa(data);
    document.querySelectorAll("[data-pauta-tab], [data-pauta-action]").forEach(el => el.classList.toggle("oculto", !esPauta));
    document.querySelectorAll("[data-legacy-tab], [data-legacy-action]").forEach(el => el.classList.toggle("oculto", esPauta));
    setText("subtituloDimensionesIa", esPauta ? "Pauta aplicada" : "Base COPC adaptada");
    setText("tituloFichaPautaIa", esPauta ? "Detalle de la evaluación" : "Ficha de errores SGC/PEC");
    setText("descripcionFichaPautaIa", esPauta
        ? "Detalle completo de los criterios, pesos, resultados y evidencias de la pauta aplicada."
        : "Documento oficial de auditoría agrupado por clasificación gerencial.");
    setText("ayudaFichaPautaIa", esPauta
        ? "La ficha conserva todos los criterios evaluados, incluso los que cumplen, no aplican o no son evaluables."
        : "La matriz técnica sustenta el score; la Ficha SGC/PEC consolida los hallazgos para supervisión, feedback y coaching.");
    setText("btnExportarFichaPautaIa", esPauta ? "Exportar detalle" : "Exportar ficha SGC/PEC");
}

function hallazgosSgcItemsIa(data = {}) {
    if (Array.isArray(data.puntos_criticos_lista) && data.puntos_criticos_lista.length) {
        return data.puntos_criticos_lista;
    }
    if (Array.isArray(data.puntos_criticos) && data.puntos_criticos.length) {
        return data.puntos_criticos;
    }
    return [];
}

function scoreTecnicoFichaIa(data = {}) {
    const scoreCalculado = calcularScoreTecnicoDesdeCriteriosIa(evaluacionCalidadItemsIa(data));
    if (scoreCalculado != null) return scoreCalculado;
    const campos = [
        data.score_tecnico,
        data.resultado_evaluacion?.score_tecnico,
        data.score_calidad_ia,
        data.score_ia,
        data.score_normalizado,
        data.score_calidad,
        data.score_final_validado,
        data.score_final,
    ];
    return primerNumeroIa(campos);
}

function calcularScoreTecnicoDesdeCriteriosIa(items = []) {
    if (!Array.isArray(items) || !items.length) return null;
    let nota = 0;
    let peso = 0;
    items.forEach(raw => {
        const item = itemSgcIa(raw);
        const pesoItem = Number(item.peso ?? item.puntaje_maximo ?? 0);
        const notaItem = Number(item.nota ?? item.puntaje_obtenido ?? 0);
        const resultado = resultadoHallazgoFichaIa(item).toLowerCase();
        if (!Number.isFinite(pesoItem) || pesoItem <= 0) return;
        if (resultado.includes("no aplica") || resultado.includes("no evaluable")) return;
        peso += pesoItem;
        if (Number.isFinite(notaItem)) nota += Math.max(0, Math.min(pesoItem, notaItem));
    });
    if (peso <= 0) return null;
    return peso === 100 ? nota : (nota / peso) * 100;
}

function formatoScoreSobre100Ia(value) {
    if (value === null || value === undefined || value === "") return "Sin score";
    const numero = Number(value);
    if (Number.isNaN(numero)) return "Sin score";
    return `${formatoPeso(numero)}/100`;
}

function esLlamadaDescalificadaFichaIa(data = {}) {
    const estado = `${data.estado_calidad || ""} ${data.resultado_evaluacion?.estado_calidad || ""}`.toLowerCase();
    return Boolean(data.descalificada || data.resultado_evaluacion?.descalificada || data.falta_anulante || estado.includes("descalificada"));
}

function hallazgoAnulanteFichaIa(data = {}) {
    const candidatos = [
        ...(Array.isArray(data.puntos_criticos_lista) ? data.puntos_criticos_lista : []),
        ...(Array.isArray(data.errores_criticos) ? data.errores_criticos : []),
        ...evaluacionCalidadItemsIa(data),
    ];
    return candidatos.find(item => {
        const texto = normalizarTextoComparacionIa(`${item.severidad || ""} ${item.gravedad || ""} ${item.categoria || ""} ${item.motivo || ""} ${item.hallazgo || ""}`);
        return texto.includes("anulante") || texto.includes("maltrato") || texto.includes("insulto") || texto.includes("humillacion") || item.puede_descalificar || item.falta_anulante;
    }) || {};
}

function evidenciaAnulanteFichaIa(data = {}, hallazgo = {}) {
    const citaDirecta = extraerCitaFichaIa(String(data.transcripcion || ""), [
        /Parece que no es empresario[^.?!]{0,180}/i,
        /no tiene plata ni para pagar[^.?!]{0,120}/i,
    ]);
    if (citaDirecta) return citaDirecta;
    const evidencia = evidenciaHallazgoFichaIa({
        frase_textual: data.frase_anulante || hallazgo.frase_textual,
        cita_textual: hallazgo.cita_textual,
        cita: hallazgo.cita,
        evidencia: hallazgo.evidencia,
    }, data);
    if (!/^Revisar transcripción|^Sin evidencia/i.test(evidencia)) return evidencia;
    const transcripcion = String(data.transcripcion || "");
    const frase = transcripcion.match(/["“”'‘’]([^"“”'‘’]{15,220})["“”'‘’]/)?.[1];
    return frase || evidencia;
}

function desviacionGestionFichaIa(data = {}, hallazgo = {}) {
    const texto = String(data.desviacion_gestion || data.resultado_gestion || hallazgo.desviacion_gestion || "").trim();
    if (texto && !/^(no_acuerdo|sin_compromiso|no acuerdo)$/i.test(texto)) return `Sí — ${texto.replaceAll("_", " ").toLowerCase()}`;
    if (esLlamadaDescalificadaFichaIa(data)) return "Sí — abandono del objetivo de cobranza";
    return "Requiere revisión del supervisor";
}

function pintarFeedbackObservacionesFichaIa(data = {}) {
    setText("feedbackUltimoIa", formatoFecha(data.fecha_ultimo_feedback || data.fecha_revision || data.fecha_creacion) || "Sin registro");
    setText("feedbackResumenIa", valorTextoSeguroIa(data.feedback_supervisor?.resumen_tecnico || data.recomendacion_feedback || data.recomendacion_feedback_supervisor || data.resumen_sgc?.motivo, "Sin información"));
    setText("feedbackConductaIa", valorTextoSeguroIa(data.feedback_supervisor?.conducta_prioritaria || data.coaching?.feedback_supervisor?.conducta_prioritaria || brechaPrincipalDetalleIa(data), "Sin información"));
    setText("feedbackAccionIa", valorTextoSeguroIa(data.feedback_supervisor?.accion_entrenable || data.coaching?.feedback_supervisor?.accion_entrenable || data.guion_sugerido, "Sin información"));
    setText("feedbackObjetivoIa", valorTextoSeguroIa(data.feedback_supervisor?.objetivo_siguiente_llamada || data.coaching?.feedback_supervisor?.objetivo_siguiente_llamada || data.feedback_asesor?.compromiso_sugerido, "Sin información"));
    setText("gestorActualizacionIa", formatoFecha(data.fecha_observacion_gestor || data.fecha_revision || data.fecha_creacion) || "Sin registro");
    setText("gestorCompromisoIa", valorTextoSeguroIa(data.compromiso_agente || data.observacion_gestor || data.comentario_agente, "Sin compromiso registrado"));
    setText("gestorEstadoIa", valorTextoSeguroIa(data.estado_compromiso || data.estado_coaching || data.estado_feedback || data.estado_revision, "Sin información"));
}

function formatoDuracionIa(segundos) {
    if (!Number.isFinite(segundos) || segundos <= 0) return "Duración no disponible";
    const min = Math.floor(segundos / 60);
    const sec = Math.floor(segundos % 60);
    return `${String(min).padStart(2, "0")}:${String(sec).padStart(2, "0")}`;
}

function tipoMimeAudioIa(nombre = "") {
    const value = String(nombre || "").toLowerCase();
    if (value.endsWith(".mp3")) return "audio/mpeg";
    if (value.endsWith(".m4a")) return "audio/mp4";
    if (value.endsWith(".ogg")) return "audio/ogg";
    if (value.endsWith(".wav")) return "audio/wav";
    return "audio/wav";
}

function resolverAudioUrlIa(url = "") {
    const value = String(url || "").trim();
    if (!value) return "";
    if (/^https?:\/\//i.test(value)) return value;
    const apiOrigin = IA_FEEDBACK_BASE.replace(/\/ia-feedback\/?$/, "");
    if (value.startsWith("/")) return `${apiOrigin}${value}`;
    return `${IA_FEEDBACK_BASE}/${value.replace(/^\/+/, "")}`;
}

function cambiarVelocidadAudioIa(value) {
    const audio = document.getElementById("audioRevisionIa");
    if (audio) audio.playbackRate = Number(value || 1);
}

function irAEvidenciaAudioIa(momento, encoded = false) {
    const audio = document.getElementById("audioRevisionIa");
    const valorMomento = encoded ? decodeURIComponent(momento || "") : momento;
    const segundos = segundosDesdeMomentoIa(valorMomento);
    if (!audio || segundos == null) {
        mostrarMensajeIa("Timestamp o audio no disponible para esta evidencia.", "error");
        return;
    }
    audio.currentTime = segundos;
    audio.play();
}

function segundosDesdeMomentoIa(momento) {
    const partes = String(momento || "").match(/^(\d{1,2}):(\d{2})(?::(\d{2}))?$/);
    if (!partes) return null;
    const nums = partes.slice(1).map(x => Number(x || 0));
    return partes[3] ? nums[0] * 3600 + nums[1] * 60 + nums[2] : nums[0] * 60 + nums[1];
}

function formatoTimestampDesdeSegundosIa(value) {
    if (value === null || value === undefined || value === "") return null;
    const segundos = Number(value);
    if (!Number.isFinite(segundos) || segundos < 0) return null;
    const total = Math.floor(segundos);
    const min = Math.floor(total / 60);
    const sec = total % 60;
    return `${min}:${String(sec).padStart(2, "0")}`;
}

function duracionAudioRevisionIa() {
    const audio = document.getElementById("audioRevisionIa");
    const duracion = Number(audio?.duration);
    return Number.isFinite(duracion) && duracion > 0 ? duracion : null;
}

function timestampEstimadoSegmentoIa(segmentos = [], index = 0, duracion = null) {
    if (!Number.isFinite(duracion) || duracion <= 0 || !segmentos.length) return null;
    const pesos = segmentos.map(segmento => Math.max(1, String(segmento.texto || segmento.transcripcion || segmento.frase || "").trim().split(/\s+/).filter(Boolean).length));
    const total = pesos.reduce((sum, value) => sum + value, 0);
    if (!total) return null;
    const acumulado = pesos.slice(0, index).reduce((sum, value) => sum + value, 0);
    return formatoTimestampDesdeSegundosIa((acumulado / total) * duracion);
}

function toggleHallazgoGrupoIa(btn) {
    btn?.closest(".finding-group")?.classList.toggle("collapsed");
}

function prepararRecalibracionItemIa(item, encoded = false) {
    abrirRecalibracionIa(encoded ? decodeURIComponent(item || "") : item || "");
}

async function guardarBorradorRevisionIa() {
    setValue("estadoRevisionIa", "PENDIENTE");
    await guardarRevisionIa({ permanecerEnFicha: true });
}

async function validarEvaluacionDesdeFichaIa() {
    const decision = document.querySelector("input[name='decisionSupervisorIa']:checked")?.value || "";
    const estado = estadoDecisionSupervisorIa();
    if (!estado.puedeValidar) {
        mostrarMensajeIa(estado.motivo || "Selecciona una decisión válida antes de continuar.", "error");
        return;
    }
    if (decision === "recalibrar") {
        if (!valor("comentarioFeedbackIa")) {
            mostrarMensajeIa("Ingresa un comentario para solicitar recalibración.", "error");
            return;
        }
        abrirRecalibracionIa();
        setValue("motivoRecalibracionIa", valor("comentarioFeedbackIa"));
        return;
    }
    if (decision === "modificar") {
        mostrarMensajeIa("Edición pendiente de integración con el backend. Guarda como borrador o solicita recalibración.", "error");
        return;
    }
    setBotonesValidarFichaIa(true);
    try {
        setValue("estadoRevisionIa", decision === "modificar" ? "REVISADO" : "REVISADO");
        await guardarRevisionIa();
    } finally {
        setBotonesValidarFichaIa(false);
    }
}

function setBotonesValidarFichaIa(loading = false) {
    document.querySelectorAll(".btn-validar-ficha-ia").forEach(btn => {
        btn.classList.toggle("is-loading", loading);
        btn.dataset.loading = loading ? "1" : "0";
        if (loading) btn.textContent = "Validando...";
        else btn.textContent = "Validar evaluación";
    });
}

function actualizarDecisionSupervisorIa() {
    const decision = document.querySelector("input[name='decisionSupervisorIa']:checked")?.value || "";
    const editable = false;
    document.querySelectorAll(".editable-criteria-action").forEach(btn => {
        btn.disabled = !editable;
        btn.title = decision === "modificar"
            ? "Edición pendiente de integración con el backend"
            : "Selecciona Modificar evaluación para registrar una discrepancia";
    });
    const comentario = document.getElementById("comentarioFeedbackIa");
    if (comentario) {
        comentario.placeholder = decision === "recalibrar"
            ? "Explica el motivo de la recalibración antes de enviarla..."
            : decision === "modificar"
                ? "Describe los criterios discrepantes. La edición por ítem aún no recalcula ni persiste score final..."
                : "Escriba su comentario aquí...";
    }
    pintarAvisoDecisionSupervisorIa(decision);
    const estado = estadoDecisionSupervisorIa();
    document.querySelectorAll(".btn-validar-ficha-ia").forEach(btn => {
        btn.disabled = !estado.puedeValidar;
        btn.title = estado.puedeValidar ? "" : estado.motivo;
    });
}

function limpiarDecisionSupervisorIa(data = {}) {
    const pendiente = !esEvaluacionValidadaIa(data);
    if (!pendiente) return;
    document.querySelectorAll("input[name='decisionSupervisorIa']").forEach(input => {
        input.checked = false;
    });
    setValue("comentarioFeedbackIa", "");
}

function estadoDecisionSupervisorIa() {
    const decision = document.querySelector("input[name='decisionSupervisorIa']:checked")?.value || "";
    const comentario = valor("comentarioFeedbackIa").trim();
    const requiereComentario = fichaRequiereComentarioIa(decision);
    if (!decision) {
        return { puedeValidar: false, motivo: "Selecciona una decisión del supervisor." };
    }
    if (decision === "modificar") {
        return { puedeValidar: false, motivo: "Edición pendiente de integración con el backend. Guarda borrador o solicita recalibración." };
    }
    if (requiereComentario && !comentario) {
        return { puedeValidar: false, motivo: "Ingresa un comentario para dejar trazabilidad de la decisión." };
    }
    return { puedeValidar: true, motivo: "" };
}

function fichaRequiereComentarioIa(decision) {
    if (!decision) return true;
    if (["modificar", "recalibrar"].includes(decision)) return true;
    const data = resultadoActualIa || {};
    return Boolean(data.requiere_revision_humana || confianzaEsBajaIa(data.confianza_evaluacion || data.calidad_transcripcion));
}

function pintarAvisoDecisionSupervisorIa(decision) {
    const form = document.getElementById("decisionSupervisorPanelIa") || document.querySelector(".decision-card");
    if (!form) return;
    let aviso = document.getElementById("avisoDecisionSupervisorIa");
    if (!aviso) {
        aviso = document.createElement("div");
        aviso.id = "avisoDecisionSupervisorIa";
        aviso.className = "decision-warning";
        form.prepend(aviso);
    }
    const data = resultadoActualIa || {};
    const requiereComentario = fichaRequiereComentarioIa(decision);
    if (decision === "modificar") {
        aviso.textContent = "Edición pendiente de integración con el backend. Puedes guardar borrador o solicitar recalibración; no se validará un score modificado sin persistencia.";
        aviso.classList.remove("oculto");
        return;
    }
    if (!decision) {
        aviso.textContent = "Selecciona una decisión explícita para continuar. No hay confirmación automática.";
        aviso.classList.remove("oculto");
        return;
    }
    if (requiereComentario && (data.requiere_revision_humana || confianzaEsBajaIa(data.confianza_evaluacion || data.calidad_transcripcion))) {
        aviso.textContent = "La evaluación tiene confianza baja o requiere revisión humana. Debes registrar comentario antes de confirmar o recalibrar.";
        aviso.classList.remove("oculto");
        return;
    }
    aviso.classList.add("oculto");
}

function opcionesTipoLlamadaIa(tipoActual) {
    const opciones = ["Por clasificar", "Cobranza inicial", "Recordatorio PDP", "Confirmación de pago", "Contacto con tercero", "Reprogramación PDP"];
    const actual = tipoActual && tipoActual !== "Sin información" ? tipoActual : "Por clasificar";
    const lista = opciones.includes(actual) ? opciones : [actual, ...opciones];
    return lista.map(opcion => `<option value="${escapeHtml(opcion)}" ${opcion === actual ? "selected" : ""}>${escapeHtml(opcion)}</option>`).join("");
}

function confianzaEsBajaIa(value) {
    const texto = String(value || "").toLowerCase();
    if (!texto || texto === "-") return true;
    return texto.includes("baja") || texto.includes("low") || Number(texto.replace(/[^\d.]/g, "")) < 70;
}

function aplicarClaseEstadoCardIa(id, clase) {
    const el = document.getElementById(id);
    if (!el) return;
    el.classList.remove("state-ok", "state-info", "state-warning", "state-danger", "state-neutral");
    el.classList.add(clase || "state-neutral");
}

function claseRiesgoCardIa(value) {
    const texto = String(value || "").toLowerCase();
    if (texto.includes("alta") || texto.includes("alto") || texto.includes("crit")) return "state-danger";
    if (texto.includes("media") || texto.includes("medio")) return "state-warning";
    if (texto.includes("baja") || texto.includes("bajo")) return "state-ok";
    return "state-neutral";
}

function formatearRiesgoVisibleIa(value) {
    const texto = String(value || "").trim().toUpperCase();
    if (!texto || texto === "-") return "-";
    if (texto.includes("ALTA") || texto.includes("ALTO")) return "RIESGO ALTO";
    if (texto.includes("MEDIA") || texto.includes("MEDIO")) return "RIESGO MEDIO";
    if (texto.includes("BAJA") || texto.includes("BAJO")) return "RIESGO BAJO";
    if (texto.includes("RIESGO")) return texto;
    return `RIESGO ${texto}`;
}

function formatearConfianzaEvaluacionIa(value) {
    const texto = String(value ?? "").trim();
    if (!texto || texto === "-") return "No disponible";
    return texto;
}

function formatearEstadoRecalibracionIa(value) {
    const texto = String(value || "SIN_APELACION").replace(/_/g, " ").trim();
    if (texto.toUpperCase() === "SIN APELACION") return "SIN APELACIÓN";
    return texto;
}

function claseResultadoGestionCardIa(value) {
    const texto = String(value || "").toLowerCase();
    if (texto.includes("pago") || texto.includes("compromiso") || texto.includes("cancel")) return "state-ok";
    if (texto.includes("pendiente") || texto.includes("seguimiento") || texto.includes("confirm")) return "state-info";
    if (texto.includes("sin") || texto.includes("no")) return "state-warning";
    return "state-info";
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
    const vista = options.view || "reporte";
    setVistaActivaIa(vista);
    document.getElementById("filtrosReporteIa")?.classList.toggle("oculto", vista === "reporte");
    document.getElementById("kpisIa")?.classList.add("oculto");
    document.getElementById("panelCargaIa")?.classList.add("oculto");
    document.getElementById("panelResultadoIa")?.classList.add("oculto");
    document.getElementById("historialPanelIa")?.classList.add("oculto");
    document.getElementById("reporteriaPanelIa")?.classList.remove("oculto");
    const panelReporte = document.getElementById("reporteriaPanelIa");
    if (panelReporte) panelReporte.dataset.activeView = vista;
    actualizarPanelesVistaReporteIa(vista);
    document.getElementById("btnVolverResultadoIa")?.classList.toggle("oculto", !resultadoActualIa);
    document.querySelector(".ia-grid")?.classList.add("result-mode");
    if (options.scroll !== false) window.scrollTo({ top: 0, behavior: "smooth" });
}

function actualizarPanelesVistaReporteIa(vista) {
    const paneles = {
        coaching: "tabCoachingIa",
        calibracion: "tabCalibracionIa",
        reportes: "tabReportesSgcIa",
        alertas: "tabAlertasIa",
        prompt: "tabPromptIa",
    };
    Object.entries(paneles).forEach(([key, id]) => {
        document.getElementById(id)?.classList.toggle("oculto", vista !== key);
    });
}

function mostrarVistaEvaluacionesIa() {
    activarVistaReporteriaIa({ view: "evaluaciones" });
    toggleFiltrosResumenIa(false);
    cargarReporteriaIa();
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
    ajustarPeriodoDefaultIa(reporteriaActualIa.detalle || []);
    detalleReporteIa = ordenarEvaluacionesPorFechaDescIa(aplicarFiltrosDetalleIa(reporteriaActualIa.detalle || []));
    const paginas = totalPaginasDetalleIa();
    if (detalleReportePaginaIa > paginas) detalleReportePaginaIa = paginas;
    poblarFiltroSupervisoresIa(reporteriaActualIa.detalle || []);
    const dataFiltrada = construirReporteFiltradoIa(reporteriaActualIa, detalleReporteIa);
    const brechas = dataFiltrada.brechas || [];
    const carteras = dataFiltrada.carteras || [];
    const agentes = dataFiltrada.agentes || [];
    pintarKpisCopcIa(dataFiltrada, detalleReporteIa);
    pintarResumenEjecutivoV2Ia(dataFiltrada, detalleReporteIa);
    setText("ultimaActualizacionIa", formatoFecha(new Date().toISOString()));
    pintarCarteraSemanaIa(detalleReporteIa);
    pintarResumenGerencialCopcIa(dataFiltrada, detalleReporteIa);
    poblarFiltroAgenteSemanaIa(detalleReporteIa);
    pintarAgenteSemanaIa(detalleReporteIa);
    pintarTendenciaSemanalIa(detalleReporteIa);
    pintarDetalleReporteIa(detalleReporteIa);
    pintarBandejaEvaluacionesIa(detalleReporteIa);
    pintarVistaCoachingIa(detalleReporteIa);
    pintarVistaCalibracionTabIa(detalleReporteIa);
    pintarVistaAlertasIa(detalleReporteIa);
    pintarVistaReportesSgcIa(dataFiltrada, detalleReporteIa);
    pintarVistaPromptIa();
}

function pintarKpisCopcIa(data, detalle) {
    const total = Number(data.total_audios || 0);
    const objetivo = Number(data.muestra_objetivo || Math.max(20, Math.ceil(total / 20) * 20 || 20));
    const cumplimiento = objetivo ? Math.min(100, (total / objetivo) * 100) : 0;
    const scoreValidado = promedioDetalleIa(detalle, item => item.score_final ?? item.score_calidad);
    const scoreIa = promedioDetalleIa(detalle, item => item.score_calidad_ia ?? item.score_calidad);
    const erroresCriticos = detalle.filter(item => item.error_critico || Number(item.total_puntos_criticos || 0) > 0).length;
    const coachingPendiente = detalle.filter(item => requiereCoachingIa(item)).length;
    const recalibraciones = detalle.filter(item => String(item.estado_recalibracion || "").toUpperCase() === "PENDIENTE").length;
    const pctErrores = total ? (erroresCriticos / total) * 100 : null;
    const pctCoaching = total ? (coachingPendiente / total) * 100 : null;

    setText("repTotalIa", formatoNumero(total));
    setText("repCumplimientoMonitoreoIa", total ? `${cumplimiento.toFixed(1)}%` : "-");
    setText("repScoreValidadoIa", scoreValidado == null ? "-" : `${scoreValidado.toFixed(1)}%`);
    setText("repErroresCriticosIa", formatoNumero(erroresCriticos));
    setText("repPendienteCoachingIa", formatoNumero(coachingPendiente));
    setText("repRecalibracionesAbiertasIa", formatoNumero(recalibraciones));
    setText("repTotalObjetivoIa", `Objetivo: ${formatoNumero(objetivo)}`);
    setText("repTotalPctIa", total ? `${cumplimiento.toFixed(0)}%` : "Sin avance");
    setText("repErroresPctIa", pctErrores == null ? "Sin base" : `${pctErrores.toFixed(1)}% del total`);
    setText("repCoachingPctIa", pctCoaching == null ? "Sin base" : `${pctCoaching.toFixed(1)}% de evaluaciones`);
    setText("repScoreDeltaIa", scoreIa == null ? "Score normalizado / 100" : `IA promedio: ${scoreIa.toFixed(1)}%`);
    setText("periodoHeaderIa", valor("filtroFechaIa") || "-");
    setText("periodoResumenIa", valor("filtroFechaIa") || "-");
    setWidthIa("repTotalProgressIa", cumplimiento);
    setWidthIa("repCumplimientoProgressIa", cumplimiento);
}

function pintarResumenEjecutivoV2Ia(data, detalle) {
    actualizarResumenFiltrosIa();
    pintarKpisResumenEjecutivoIa(data, detalle);
    pintarAlertaEjecutivaIa(data, detalle);
    pintarTendenciaCalidadResumenIa(detalle);
    pintarParetoResumenIa(data, detalle);
    pintarDimensionesCopcResumenIa(data, detalle);
    pintarAgentesPriorizadosResumenIa(detalle);
    pintarAccionesMejoraResumenIa(detalle);
}

function pintarKpisResumenEjecutivoIa(data, detalle) {
    const el = document.getElementById("resumenKpisEjecutivosIa");
    if (!el) return;
    const total = detalle.length || Number(data.total_audios || 0);
    const validadas = detalle.filter(esEvaluacionValidadaIa);
    const scoreValidado = promedioDetalleIa(validadas, scoreValidadoResumenIa);
    const scoreIa = promedioDetalleIa(detalle, scoreIaPreliminarResumenIa);
    const errores = detalle.filter(item => item.error_critico || item.falta_anulante || Number(item.total_puntos_criticos || 0) > 0).length;
    const pendientes = detalle.filter(item => !esEvaluacionValidadaIa(item)).length;
    const vencidas = accionesVencidasIa(detalle);
    const pctErrores = total ? (errores / total) * 100 : null;
    const cards = [
        {
            color: scoreValidado == null ? "info" : scoreValidado >= 85 ? "ok" : scoreValidado >= 70 ? "warn" : "risk",
            icon: "CV",
            title: "Calidad validada",
            value: scoreValidado == null ? "-" : `${scoreValidado.toFixed(1)}%`,
            meta: scoreValidado == null ? "Sin evaluaciones validadas" : `${formatoNumero(validadas.length)} evaluaciones validadas`,
            delta: scoreValidado == null && scoreIa != null ? `Score IA preliminar: ${scoreIa.toFixed(1)}%` : "Score final validado",
        },
        {
            color: "info",
            icon: "EV",
            title: "Evaluaciones realizadas",
            value: formatoNumero(total),
            meta: "En el periodo seleccionado",
            delta: "Periodo seleccionado",
        },
        {
            color: errores ? "risk" : "ok",
            icon: "EC",
            title: "Evaluaciones con error crítico",
            value: pctErrores == null ? "-" : `${pctErrores.toFixed(1)}%`,
            meta: `${formatoNumero(errores)} evaluaciones`,
            delta: total ? `${formatoNumero(errores)} evaluaciones afectadas` : "Sin base",
        },
        {
            color: pendientes ? "warn" : "ok",
            icon: "RP",
            title: "Revisión pendiente",
            value: formatoNumero(pendientes),
            meta: pendientes ? "Requieren cierre supervisor" : "Sin pendientes",
            delta: "Estado de revisión",
        },
        {
            color: vencidas ? "risk" : "warn",
            icon: "PM",
            title: "Acciones vencidas",
            value: formatoNumero(vencidas),
            meta: "Coaching o planes de mejora",
            delta: "Según fecha programada",
        },
    ];
    el.innerHTML = cards.map(card => `
        <article class="summary-kpi-card ${card.color}">
            <div class="summary-kpi-top">
                <span class="summary-kpi-icon">${escapeHtml(card.icon)}</span>
                <em>${escapeHtml(card.delta)}</em>
            </div>
            <span>${escapeHtml(card.title)}</span>
            <strong>${escapeHtml(card.value)}</strong>
            <small>${escapeHtml(card.meta)}</small>
        </article>
    `).join("");
}

function pintarAlertaEjecutivaIa(data, detalle) {
    const el = document.getElementById("alertaEjecutivaIa");
    if (!el) return;
    const pareto = construirParetoSgcIa(data, detalle);
    if (!detalle.length) {
        el.innerHTML = `<div><strong>Sin información disponible</strong><span>No hay evaluaciones para los filtros seleccionados.</span></div>`;
        return;
    }
    const principal = pareto[0];
    if (!principal) {
        el.innerHTML = `<div><strong>Sin alerta prioritaria</strong><span>No se detectan brechas SGC/PEC relevantes en el periodo filtrado.</span></div>`;
        return;
    }
    const evaluacionesAfectadas = evaluacionesAfectadasPorFactorIa(detalle, principal.factor_sgc);
    const pct = detalle.length ? (evaluacionesAfectadas / detalle.length) * 100 : 0;
    const textoBase = detalle.some(esEvaluacionValidadaIa) ? "evaluaciones revisadas" : "evaluaciones analizadas";
    el.innerHTML = `
        <div>
            <strong>Atención requerida</strong>
            <span>${escapeHtml(principal.factor_sgc)} concentra la principal brecha del periodo y afecta al ${pct.toFixed(1)}% de las ${textoBase}.</span>
        </div>
        <button class="link-button" type="button" onclick="mostrarVistaCoachingIa()">Revisar casos relacionados →</button>
    `;
}

function pintarTendenciaCalidadResumenIa(detalle) {
    const el = document.getElementById("tendenciaCalidadResumenIa");
    if (!el) return;
    const semanas = {};
    const validadas = detalle.filter(esEvaluacionValidadaIa);
    const usarIaPreliminar = !validadas.length;
    const base = usarIaPreliminar ? detalle : validadas;
    const scoreGetter = usarIaPreliminar ? scoreIaPreliminarResumenIa : scoreValidadoResumenIa;
    setText("tituloTendenciaIa", usarIaPreliminar ? "Evolución del score IA preliminar" : "Evolución de calidad");
    setText("subtituloTendenciaIa", usarIaPreliminar ? "Score IA preliminar frente a la meta mensual" : "Score validado frente a la meta mensual");
    const scorePeriodo = promedioDetalleIa(base, scoreGetter);
    base.forEach(row => {
        const score = scoreGetter(row);
        if (score == null) return;
        const semana = claveSemanaClienteIa(row.fecha_llamada || row.fecha_creacion);
        const actual = semanas[semana] || { semana, total: 0, score: 0 };
        actual.total += 1;
        actual.score += score;
        semanas[semana] = actual;
    });
    const semanasOrdenadas = semanasResumenDesdeFiltroIa(Object.keys(semanas));
    const rows = semanasOrdenadas.map(semana => {
        const row = semanas[semana];
        return row
            ? { label: row.semana, score: row.total ? row.score / row.total : null, total: row.total }
            : { label: semana, score: null, total: 0 };
    }).slice(-6);
    const pointsValidos = rows.filter(row => row.total > 0 && row.score != null);
    if (!pointsValidos.length) {
        el.innerHTML = estadoVacioReporteIa(detalle);
        setText("variacionTendenciaIa", "Sin periodo comparable");
        return;
    }
    const anterior = pointsValidos[pointsValidos.length - 2];
    const ultimo = pointsValidos[pointsValidos.length - 1];
    if (anterior && ultimo) {
        const delta = ultimo.score - anterior.score;
        setText("variacionTendenciaIa", `Vs semana con datos ${delta >= 0 ? "+" : "-"}${Math.abs(delta).toFixed(1)} pp`);
    } else {
        setText("variacionTendenciaIa", "Sin periodo comparable");
    }
    el.innerHTML = renderLineaResumenIa(rows, {
        scorePeriodo,
        evaluacionesValidas: pointsValidos.reduce((sum, item) => sum + item.total, 0),
        usarIaPreliminar,
    });
}

function renderLineaResumenIa(points, options = {}) {
    const width = 760;
    const height = 260;
    const left = 54;
    const right = 76;
    const top = 34;
    const bottom = 58;
    const chartW = width - left - right;
    const chartH = height - top - bottom;
    const meta = 85;
    const coords = points.map((point, index) => {
        const x = left + (chartW * index) / Math.max(1, points.length - 1);
        if (point.score == null || !point.total) return { ...point, x, y: top + chartH, sinDatos: true };
        const y = top + chartH - (Math.max(0, Math.min(100, point.score)) / 100) * chartH;
        return { ...point, x, y };
    });
    const lineasValidas = construirSegmentosLineaResumenIa(coords);
    const areasValidas = construirAreasLineaResumenIa(coords, top + chartH);
    const metaY = top + chartH - (meta / 100) * chartH;
    return `
        <svg class="summary-line-svg" viewBox="0 0 ${width} ${height}" role="img" aria-label="Evolución de calidad">
            <line class="summary-grid-line" x1="${left}" y1="${top + chartH}" x2="${left + chartW}" y2="${top + chartH}"></line>
            <line class="summary-grid-line" x1="${left}" y1="${top + chartH / 2}" x2="${left + chartW}" y2="${top + chartH / 2}"></line>
            <line class="summary-target-line" x1="${left}" y1="${metaY.toFixed(1)}" x2="${left + chartW}" y2="${metaY.toFixed(1)}"></line>
            <text class="summary-target-label" x="${left + chartW - 116}" y="${metaY - 8}">${options.usarIaPreliminar ? "Meta referencial 85%" : "Meta 85%"}</text>
            ${areasValidas.map(area => `<polygon class="summary-line-area" points="${area}"></polygon>`).join("")}
            ${lineasValidas.map(linea => `<polyline class="summary-score-line" points="${linea}"></polyline>`).join("")}
            ${coords.map(p => `
                ${p.sinDatos ? `<text class="summary-no-data-label" x="${p.x.toFixed(1)}" y="${top + chartH + 22}">Sin evaluaciones</text>` : `
                    <circle class="summary-score-dot" cx="${p.x.toFixed(1)}" cy="${p.y.toFixed(1)}" r="5"></circle>
                    <text class="summary-score-label" x="${p.x.toFixed(1)}" y="${p.y - 12}">${p.score.toFixed(1)}%</text>
                `}
                <text class="summary-week-label" x="${p.x.toFixed(1)}" y="${height - 15}">${escapeHtml(p.label)}</text>
            `).join("")}
        </svg>
        <div class="summary-chart-footer">
            <span>Resultado del periodo: <strong>${options.scorePeriodo == null ? "Sin información" : `${options.scorePeriodo.toFixed(1)}%`}</strong></span>
            <span>${formatoNumero(options.evaluacionesValidas || 0)} evaluaciones con ${options.usarIaPreliminar ? "score IA" : "score validado"}</span>
        </div>
    `;
}

function construirSegmentosLineaResumenIa(coords) {
    const validos = coords.filter(point => !point.sinDatos);
    if (validos.length < 2) return [];
    return [validos.map(p => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(" ")];
}

function construirAreasLineaResumenIa(coords, baseY) {
    const validos = coords.filter(point => !point.sinDatos);
    if (validos.length < 2) return [];
    const primero = validos[0];
    const ultimo = validos[validos.length - 1];
    return [`${primero.x.toFixed(1)},${baseY} ${validos.map(p => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(" ")} ${ultimo.x.toFixed(1)},${baseY}`];
}

function semanasResumenDesdeFiltroIa(semanasConDatos) {
    const rango = parseRangoFechasIa(valor("filtroFechaIa"));
    const ordenadas = [...new Set(semanasConDatos)].sort((a, b) => a.localeCompare(b));
    if (!rango.desde || !rango.hasta) return ordenadas;
    const semanas = [];
    const cursor = new Date(rango.desde);
    while (cursor <= rango.hasta) {
        const clave = claveSemanaClienteIa(cursor.toISOString());
        if (!semanas.includes(clave)) semanas.push(clave);
        cursor.setDate(cursor.getDate() + 1);
    }
    return semanas.length ? semanas : ordenadas;
}

function pintarParetoResumenIa(data, detalle) {
    const el = document.getElementById("paretoResumenIa");
    if (!el) return;
    const allRows = construirParetoSgcIa(data, detalle);
    const rows = allRows.slice(0, 5);
    if (!rows.length) {
        el.innerHTML = estadoVacioReporteIa(detalle);
        return;
    }
    const max = Math.max(...rows.map(row => Number(row.frecuencia || 0)), 1);
    let acumulado = 0;
    const totalFrecuencia = allRows.reduce((sum, row) => sum + Number(row.frecuencia || 0), 0);
    const totalEvaluaciones = detalle.length;
    const modo = detalle.some(esEvaluacionValidadaIa) ? "Resultado validado" : "Resultado preliminar IA";
    el.innerHTML = `<div class="pareto-mode-label">${modo}</div>` + rows.map((row, index) => {
        const frecuencia = Number(row.frecuencia || 0);
        acumulado += frecuencia;
        const afectadas = Number(row.evaluaciones_afectadas ?? frecuencia);
        const pctMuestra = totalEvaluaciones ? (afectadas / totalEvaluaciones) * 100 : null;
        const pctAcum = totalFrecuencia ? (acumulado / totalFrecuencia) * 100 : 0;
        return `
            <article class="pareto-summary-row" title="Una evaluación puede presentar brechas en varios factores">
                <span>${index + 1}</span>
                <div>
                    <strong>${escapeHtml(row.factor_sgc || "-")}</strong>
                    <div class="summary-progress"><i style="width:${Math.max(4, (frecuencia / max) * 100)}%"></i></div>
                    <small>${formatoNumero(afectadas)} de ${formatoNumero(totalEvaluaciones)} evaluaciones afectadas · ${pctAcum.toFixed(1)}% acumulado de brechas</small>
                </div>
                <em>${formatoNumero(frecuencia)}</em>
                <b>${pctMuestra == null ? "Sin base" : `${pctMuestra.toFixed(1)}%`}</b>
            </article>
        `;
    }).join("");
}

function pintarDimensionesCopcResumenIa(data, detalle) {
    const el = document.getElementById("dimensionCopcResumenIa");
    if (!el) return;
    const tieneValidadas = detalle.some(esEvaluacionValidadaIa);
    setText("subtituloDimensionCopcIa", tieneValidadas ? "Resultado validado de las cinco etapas evaluadas" : "Resultado preliminar IA de las cinco etapas evaluadas");
    const nombres = ["Cumplimiento", "Diagnóstico", "Gestión de solución", "Cierre verificable", "Experiencia y ética"];
    const segmentos = Object.fromEntries((data.segmentos || []).map(item => [formatearSegmentoIa(item.segmento), item]));
    el.innerHTML = nombres.map(nombre => {
        const item = segmentos[nombre] || {};
        const score = item.porcentaje != null ? Number(item.porcentaje) : null;
        const brecha = score == null ? null : score - 85;
        const clase = score == null ? "info" : score >= 85 ? "ok" : score >= 70 ? "warn" : "risk";
        return `
            <article class="dimension-item ${clase}">
                <div><span>${escapeHtml(nombre)}</span><strong>${score == null ? "-" : `${score.toFixed(0)}%`}</strong></div>
                <div class="summary-progress"><i style="width:${score == null ? 0 : Math.max(3, Math.min(100, score))}%"></i></div>
                <small>${brecha == null ? "Sin información disponible" : `Brecha ${brecha >= 0 ? "+" : ""}${brecha.toFixed(0)} pp`}</small>
            </article>
        `;
    }).join("");
}

function pintarAgentesPriorizadosResumenIa(detalle) {
    const el = document.getElementById("agentesPriorizadosResumenIa");
    if (!el) return;
    const rows = construirAgentesPriorizadosIa(detalle).slice(0, 5);
    if (!rows.length) {
        el.innerHTML = estadoVacioReporteIa(detalle);
        return;
    }
    el.innerHTML = `
        <div class="intervention-list">
            ${rows.map(row => {
                const nivel = row.errorCriticoPct >= 25 || (row.scoreValidado != null && row.scoreValidado < 70) ? "Crítico" : row.scoreValidado != null && row.scoreValidado < 80 ? "Alto" : "Medio";
                const claseNivel = nivel === "Crítico" ? "alto" : nivel === "Alto" ? "medio" : "bajo";
                const accion = String(row.estadoCoaching || "").toUpperCase() === "PENDIENTE" ? "Programar" : "Revisar";
                const agenteVisible = nombreAgenteCortoIa(row.agente);
                const agenteCompleto = nombreAgenteLimpioIa(row.agente);
                const codigoAgente = codigoAgenteIa(row.agente);
                const scoreValidadoTexto = row.scoreValidado == null ? "Pendiente" : `${row.scoreValidado.toFixed(1)}%`;
                const scoreIaTexto = row.scoreNormalizado == null ? "Score IA: -" : `Score IA: ${row.scoreNormalizado.toFixed(1)}%`;
                return `
                    <article class="intervention-item ${nivel === "Crítico" ? "is-critical" : nivel === "Alto" ? "is-high" : ""}">
                        <div class="intervention-agent">
                            <span class="intervention-avatar">${escapeHtml(inicialesAgenteIa(row.agente))}</span>
                            <div>
                                <strong title="${escapeHtml(agenteCompleto)}">${escapeHtml(agenteVisible)}</strong>
                                <small>${escapeHtml(codigoAgente ? `Código: ${codigoAgente}` : "Sin código")}</small>
                                <small>${escapeHtml(row.cartera || "-")}</small>
                            </div>
                        </div>
                        <div class="intervention-metrics">
                            <span>
                                <b class="${row.scoreValidado != null && row.scoreValidado < 70 ? "score-danger" : "score-ok"}">${scoreValidadoTexto}</b>
                                <small>Calidad</small>
                                <small>${scoreIaTexto}</small>
                            </span>
                            <span>
                                <b>${escapeHtml(row.brechaPrincipal || "-")}</b>
                                <small>Brecha principal</small>
                            </span>
                            <span>
                                <b>${formatoNumero(row.criticos)}</b>
                                <small>Reincidencia</small>
                            </span>
                        </div>
                        <div class="intervention-actions">
                            ${badgeGerencialIa(nivel, claseNivel)}
                            <button class="historial-action" type="button" onclick="verAnalisisIa(${Number(row.idFeedback || 0)})">${accion}</button>
                        </div>
                    </article>
                `;
            }).join("")}
        </div>
    `;
}

function pintarAccionesMejoraResumenIa(detalle) {
    const el = document.getElementById("accionesMejoraResumenIa");
    if (!el) return;
    const vencidas = accionesVencidasIa(detalle);
    const enCurso = detalle.filter(item => ["EN_PROCESO"].includes(String(item.estado_coaching || "").toUpperCase())).length;
    const programadas = detalle.filter(item => ["PROGRAMADO"].includes(String(item.estado_coaching || "").toUpperCase())).length;
    const completadas = detalle.filter(item => ["REALIZADO", "CERRADO"].includes(String(item.estado_coaching || "").toUpperCase())).length;
    const total = vencidas + enCurso + programadas + completadas;
    const pctVencidas = total ? (vencidas / total) * 100 : 0;
    const pctCurso = total ? (enCurso / total) * 100 : 0;
    const pctProgramadas = total ? (programadas / total) * 100 : 0;
    const proximo = detalle
        .filter(item => item.fecha_coaching && !["REALIZADO", "CERRADO"].includes(String(item.estado_coaching || "").toUpperCase()))
        .sort((a, b) => new Date(a.fecha_coaching) - new Date(b.fecha_coaching))[0];
    el.innerHTML = `
        <div class="actions-donut-wrap">
            <div class="actions-donut ${total ? "" : "is-empty"}" style="--vencidas:${pctVencidas}; --curso:${pctCurso}; --programadas:${pctProgramadas};">
                <strong>${formatoNumero(total)}</strong>
                <span>acciones</span>
            </div>
            <div class="actions-legend">
                <span><i class="risk"></i>Vencidas <b>${formatoNumero(vencidas)}</b></span>
                <span><i class="info"></i>En curso <b>${formatoNumero(enCurso)}</b></span>
                <span><i class="warn"></i>Programadas <b>${formatoNumero(programadas)}</b></span>
                <span><i class="ok"></i>Completadas <b>${formatoNumero(completadas)}</b></span>
            </div>
        </div>
        <div class="next-action-box">
            <span>Próximo vencimiento</span>
            <strong>${proximo ? `Coaching · ${nombreAgenteCortoIa(proximo.agente || "Sin agente")}` : "Sin información disponible"}</strong>
            <small>${proximo ? formatoFecha(proximo.fecha_coaching) : "Pendiente de integración de fechas de plan."}</small>
        </div>
    `;
}

function pintarResumenGerencialCopcIa(data, detalle) {
    pintarCalidadCarteraGerencialIa(data.carteras || [], detalle);
    pintarBrechasCriticasPeriodoIa(data.brechas || [], detalle, Number(data.total_audios || 0));
    pintarAgentesPriorizadosGerencialIa(detalle);
    pintarCalibracionConsistenciaReporteIa(detalle);
    pintarDistribucionSgcIa(data, detalle);
}

function pintarCalidadCarteraGerencialIa(carteras, detalle) {
    const rows = [...carteras].sort((a, b) => (b.total_audios || 0) - (a.total_audios || 0));
    const el = document.getElementById("repCalidadCarteraGerencialIa");
    if (!el) return;
    if (!rows.length) {
        el.innerHTML = estadoVacioReporteIa(detalle);
        return;
    }
    el.innerHTML = `
        <table class="copc-mini-table">
            <thead><tr><th>Cartera</th><th>Evaluaciones</th><th>Score</th><th>Error critico</th><th>Aprobadas</th><th>Estado</th></tr></thead>
            <tbody>${rows.slice(0, 8).map(row => {
                const score = porcentajeReporte(row);
                const crit = Number(row.ceros || 0);
                const aprobadas = Math.max(0, Math.min(100, score));
                const estado = score >= 85 && crit === 0 ? "Optimo" : score >= 70 ? "Atencion" : "Riesgo";
                const estadoClase = estado === "Optimo" ? "bajo" : estado === "Atencion" ? "medio" : "alto";
                return `
                    <tr>
                        <td><strong>${escapeHtml(row.cartera || "-")}</strong></td>
                        <td>${formatoNumero(row.total_audios || 0)}</td>
                        <td>
                            <div class="copc-table-meter"><span>${score.toFixed(1)}%</span><i style="width:${Math.max(2, Math.min(100, score))}%"></i></div>
                        </td>
                        <td>${formatoNumero(crit)}</td>
                        <td>${aprobadas.toFixed(0)}%</td>
                        <td>${badgeGerencialIa(estado, estadoClase)}</td>
                    </tr>
                `;
            }).join("")}</tbody>
        </table>
    `;
}

const SGC_GRUPOS_IA = [
    "Errores críticos del negocio",
    "Errores críticos del usuario final",
    "Errores críticos de cumplimiento",
    "Errores no críticos",
];

const ITEM_COPC_DISPLAY_IA = [
    ["2.1", "2.1 Identificación de causa raíz / motivo de atraso"],
    ["2.2", "2.2 Diagnóstico de capacidad de pago"],
    ["2.3", "2.3 Escucha activa y control de la interacción"],
    ["2.4", "2.4 Confirmación de comprensión del cliente"],
    ["3.2", "3.2 Gestión de objeciones del cliente"],
    ["4.1", "4.1 Cierre verificable 3C/4C"],
    ["4.4", "4.4 Plan de seguimiento ante incumplimiento"],
    ["5.4", "5.4 Conducta ética y no abuso"],
];

const CRITERIO_TECNICO_DISPLAY_IA = {
    "2.1": "Identificación de la causa",
    "2.2": "Capacidad actual de pago",
    "2.3": "Fecha probable de ingreso",
    "2.4": "Monto disponible",
    "2.5": "Fuente del dinero o situación económica",
    "3.1": "Presentación clara de la propuesta",
    "3.2": "Claridad del beneficio",
    "3.3": "Exploración de capacidad durante la negociación",
    "3.4": "Negociación escalonada",
    "3.5": "Manejo de objeciones",
    "3.6": "Inducción a pago o abono",
    "4.1": "Cantidad",
    "4.2": "Fecha exacta",
    "4.3": "Canal de pago",
    "4.4": "Confirmación expresa",
    "4.5": "Resumen y siguiente acción",
    "5.1": "Respeto y ausencia de juicio",
    "5.2": "Empatía y escucha activa",
    "5.3": "Lenguaje claro y presión profesional",
    "5.4": "Despedida y cierre profesional",
};

const SGC_FACTORES_IA = [
    ["Errores críticos del negocio", "Razón de no pago y explicar motivo", ["2.1", "motivo de atraso", "causa raíz", "causa raiz", "razón de no pago", "razon de no pago"]],
    ["Errores críticos del negocio", "Urgencia y persistencia en el pago", ["3.5", "orientación a resultado", "orientacion a resultado", "urgencia", "persistencia"]],
    ["Errores críticos del negocio", "Gestión de objeciones del cliente", ["3.2", "objeciones"]],
    ["Errores críticos del negocio", "Dominio de la llamada", ["2.3", "control de conversación", "control de conversacion", "dominio"]],
    ["Errores críticos del negocio", "Parafraseo / reafirmar acuerdo de pagos", ["4.3", "recapitulación", "recapitulacion", "parafraseo", "reafirmar"]],
    ["Errores críticos del negocio", "Tipificación correcta", ["1.4", "registro", "trazabilidad", "tipificación", "tipificacion"]],
    ["Errores críticos del negocio", "Cierre verificable 3C/4C", ["4.1", "cierre 3c", "cierre verificable", "cuánto", "cuanto"]],
    ["Errores críticos del negocio", "Negociación escalonada", ["3.1", "negociación escalonada", "negociacion escalonada"]],
    ["Errores críticos del negocio", "Propuesta de alternativas", ["3.3", "alternativas"]],
    ["Errores críticos del negocio", "Orientación a resultado", ["3.5", "compromiso concreto", "resultado"]],
    ["Errores críticos del usuario final", "Información de la deuda", ["1.3", "información correcta", "informacion correcta", "deuda"]],
    ["Errores críticos del usuario final", "Agilidad / escucha activa", ["2.3", "escucha activa", "interrup"]],
    ["Errores críticos del usuario final", "Claridad de la explicación", ["5.2", "claridad", "explicación", "explicacion"]],
    ["Errores críticos del usuario final", "Confusión generada al cliente", ["confusión", "confusion"]],
    ["Errores críticos de cumplimiento", "Validación de titularidad", ["1.2", "titularidad", "validación", "validacion"]],
    ["Errores críticos de cumplimiento", "Exposición de deuda a tercero", ["tercero", "exposición", "exposicion"]],
    ["Errores críticos de cumplimiento", "Información falsa o riesgosa", ["información falsa", "informacion falsa", "riesgosa", "legal"]],
    ["Errores críticos de cumplimiento", "Amenazas, presión indebida o trato abusivo", ["amenaza", "presión indebida", "presion indebida", "abuso", "insulto", "cárcel", "carcel"]],
    ["Errores críticos de cumplimiento", "Conducta ética y no abuso", ["5.4", "conducta ética", "conducta etica", "ético", "etico", "no abuso"]],
    ["Errores no críticos", "Identificación del gestor", ["1.1", "apertura", "identificación", "identificacion"]],
    ["Errores no críticos", "Entonación, dicción y empatía", ["5.1", "5.2", "empatía", "empatia", "dicción", "diccion", "entonación", "entonacion"]],
    ["Errores no críticos", "Despedida profesional", ["4.5", "despedida"]],
];

function clasificarSgcItemIa(item = {}) {
    if (item.grupo_error_sgc && item.factor_sgc && !esValorNoAplicableIa(item.grupo_error_sgc)) {
        return { grupo: item.grupo_error_sgc, factor: item.factor_sgc };
    }
    const texto = `${item.item || ""} ${item.segmento || ""} ${item.hallazgo || ""} ${item.evidencia || ""} ${item.recomendacion || ""}`.toLowerCase();
    const match = SGC_FACTORES_IA.find(([, , claves]) => claves.some(clave => texto.includes(String(clave).toLowerCase())));
    if (match) return { grupo: match[0], factor: match[1] };
    if (texto.includes("cierre") || texto.includes("negoci")) return { grupo: "Errores críticos del negocio", factor: "Orientación a resultado" };
    if (texto.includes("cumpl") || texto.includes("riesgo")) return { grupo: "Errores críticos de cumplimiento", factor: "Conducta ética y no abuso" };
    return { grupo: "Errores no críticos", factor: item.item || "Error no crítico" };
}

function itemCopcVisibleIa(item) {
    const codigo = codigoCriterioHallazgoIa(item || {});
    const nombre = String(item?.nombre || item?.criterio || item?.item || item?.item_copc || "").trim();
    if (/^(PENC|PECUF|PECN|PECC)\.\d+$/i.test(codigo)) {
        return `${codigoCriterioDisplayIa(codigo)} ${nombre || "Criterio Mibanco"}`.trim();
    }
    const texto = String(item?.item || item?.criterio || "-");
    const prefijo = texto.match(/^\s*(\d+\.\d+)/)?.[1];
    const match = ITEM_COPC_DISPLAY_IA.find(([codigo]) => codigo === prefijo);
    return match ? match[1] : texto;
}

function itemSgcIa(item = {}) {
    const clasif = clasificarSgcItemIa(item);
    const grupo = esValorNoAplicableIa(item.grupo_error_sgc) ? clasif.grupo : (item.grupo_error_sgc || clasif.grupo);
    const factorBase = item.factor_sgc || item.factor;
    const factor = esValorNoAplicableIa(factorBase) ? clasif.factor : (factorBase || clasif.factor);
    const calificacion = item.calificacion || normalizarCalificacionItemIa(item);
    return {
        ...item,
        grupo_error_sgc: grupo,
        factor_sgc: factor,
        calificacion,
        motivo: item.motivo || item.hallazgo || "-",
        requiere_feedback: item.requiere_feedback ?? requiereFeedbackItemIa({ ...item, calificacion, grupo_error_sgc: grupo }),
        requiere_coaching: item.requiere_coaching ?? requiereCoachingItemIa({ ...item, calificacion, grupo_error_sgc: grupo }),
    };
}

function esValorNoAplicableIa(value) {
    return /^(no aplica|na|n\/a|-|null|undefined)$/i.test(String(value || "").trim());
}

function clasificarGrupoBaseSgcIa(item = {}) {
    const texto = `${item.item || ""} ${item.segmento || ""} ${item.hallazgo || ""} ${item.evidencia || ""} ${item.recomendacion || ""}`.toLowerCase();
    const match = SGC_FACTORES_IA.find(([, , claves]) => claves.some(clave => texto.includes(String(clave).toLowerCase())));
    if (match) return { grupo: match[0], factor: match[1] };
    if (texto.includes("cierre") || texto.includes("negoci")) return { grupo: "Errores críticos del negocio", factor: "Orientación a resultado" };
    if (texto.includes("cumpl") || texto.includes("riesgo")) return { grupo: "Errores críticos de cumplimiento", factor: "Conducta ética y no abuso" };
    if (texto.includes("deuda") || texto.includes("cliente") || texto.includes("explic")) return { grupo: "Errores críticos del usuario final", factor: "Claridad de la explicación" };
    return { grupo: "Errores no críticos", factor: item.item || "Error no crítico" };
}

function normalizarCalificacionItemIa(item = {}) {
    const resultado = String(item.resultado || "").toLowerCase();
    const estado = String(item.estado || item.estado_tecnico || "").toUpperCase();
    if (resultado.includes("requiere_revision") || resultado.includes("requiere revision") || resultado.includes("requiere revisión") || resultado.includes("revision humana") || resultado.includes("revisión humana")) return "Requiere revisión";
    if (resultado.includes("no evaluable")) return "No evaluable";
    if (resultado.includes("no aplica")) return "No aplica";
    if (resultado.includes("parcial")) return "Parcial";
    if (resultado.includes("no cumple") || resultado.includes("no evidenciado")) return "No cumple";
    if (resultado.includes("cumple")) return "Cumple";
    if (estado === "NO_EVALUABLE") return "No evaluable";
    if (estado === "NO_APLICA") return "No aplica";
    if (estado === "REQUIERE_REVISION") return "Requiere revisión";
    return Number(item.nota || 0) === 0 ? "No cumple" : "Parcial";
}

function requiereFeedbackItemIa(item = {}) {
    const cal = String(item.calificacion || "").toLowerCase();
    return cal && !["cumple", "no aplica", "no evaluable"].includes(cal);
}

function requiereCoachingItemIa(item = {}) {
    const cal = String(item.calificacion || "").toLowerCase();
    const grupo = String(item.grupo_error_sgc || "").toLowerCase();
    return cal !== "cumple" && grupo.includes("cumplimiento");
}

function itemsSgcDetalleIa(row = {}) {
    const items = evaluacionCalidadItemsIa(row);
    if (items.length) return items.map(itemSgcIa);
    return (row.brechas_items || []).map(itemSgcIa);
}

function resumenSgcDesdeItemsIa(items = []) {
    const resumen = Object.fromEntries(SGC_GRUPOS_IA.map(grupo => [grupo, 0]));
    items.forEach(raw => {
        const item = itemSgcIa(raw);
        const cal = String(item.calificacion || "").toLowerCase();
        if (!esValorNoAplicableIa(item.grupo_error_sgc) && !["cumple", "no aplica", "no evaluable"].includes(cal) && !cal.includes("revision") && !cal.includes("revisión")) {
            resumen[item.grupo_error_sgc] = (resumen[item.grupo_error_sgc] || 0) + 1;
        }
    });
    return resumen;
}

function pintarDistribucionSgcIa(data, detalle) {
    const el = document.getElementById("repDistribucionSgcIa");
    if (!el) return;
    const conteos = Object.fromEntries(SGC_GRUPOS_IA.map(grupo => [grupo, 0]));
    (data.sgc_grupos || []).forEach(item => {
        if (conteos[item.grupo_error_sgc] != null) conteos[item.grupo_error_sgc] = Number(item.total || 0);
    });
    if (!(data.sgc_grupos || []).length) {
        detalle.forEach(row => {
            const resumen = resumenSgcDesdeItemsIa(itemsSgcDetalleIa(row));
            Object.entries(resumen).forEach(([grupo, total]) => { conteos[grupo] += total; });
        });
    }
    const total = Object.values(conteos).reduce((sum, value) => sum + Number(value || 0), 0);
    if (!total) {
        el.innerHTML = estadoVacioReporteIa(detalle);
        return;
    }
    el.innerHTML = SGC_GRUPOS_IA.map(grupo => {
        const valor = conteos[grupo] || 0;
        const pct = total ? (valor / total) * 100 : 0;
        return `<article><span>${escapeHtml(grupo)}</span><strong>${formatoNumero(valor)}</strong><div class="copc-progress"><i style="width:${Math.max(3, pct)}%"></i></div><small>${pct.toFixed(1)}%</small></article>`;
    }).join("");
}

function pintarBrechasCriticasPeriodoIa(brechas, detalle, totalEvaluaciones) {
    const el = document.getElementById("repBrechasCriticasPeriodoIa");
    if (!el) return;
    const paretoGeneral = construirParetoSgcIa(reporteriaActualIa || {}, detalle);
    const rows = paretoGeneral.length ? paretoGeneral : brechas.slice(0, 10).map(item => {
        const itemSgc = itemSgcIa(item);
        const frecuencia = Number(item.ceros || item.total || 0);
        return {
            ...item,
            frecuencia,
            factor_sgc: itemSgc.factor_sgc || item.item || "-",
            grupo_error_sgc: itemSgc.grupo_error_sgc || "-",
            impacto: itemSgc.grupo_error_sgc.includes("cumplimiento") || itemSgc.grupo_error_sgc.includes("negocio") ? "Alto" : impactoBrechaIa(item.item, frecuencia),
            accion_recomendada: accionSugeridaSgcIa(itemSgc),
        };
    });
    if (!rows.length) {
        el.innerHTML = estadoVacioReporteIa(detalle);
        return;
    }
    const normalizados = rows.map(item => {
        const frecuencia = Number(item.frecuencia || item.ceros || item.total || 0);
        const itemSgc = itemSgcIa(item);
        const factor = item.factor_sgc || itemSgc.factor_sgc || item.item || "-";
        const cartera = carteraMasAfectadaPorFactorSgcIa(detalle, factor) || carteraMasAfectadaPorBrechaIa(detalle, item.item);
        const impacto = itemSgc.grupo_error_sgc.includes("cumplimiento") || itemSgc.grupo_error_sgc.includes("negocio") ? "Alto" : impactoBrechaIa(item.item, frecuencia);
        return {
            ...item,
            frecuencia,
            factor_sgc: factor,
            grupo_error_sgc: itemSgc.grupo_error_sgc || "-",
            segmento_copc: formatearSegmentoIa(item.segmento || "-"),
            cartera_afectada: cartera,
            impacto: item.impacto || impacto,
            accion_recomendada: item.accion_recomendada || accionSugeridaSgcIa(itemSgc),
        };
    });
    const totalBrechas = normalizados.reduce((sum, item) => sum + item.frecuencia, 0);
    el.innerHTML = `
        ${renderParetoSgcChartIa(normalizados, { totalEvaluaciones: totalBrechas || totalEvaluaciones, maxItems: 10, title: "Pareto general SGC/PEC" })}
        <div class="copc-pareto-table-wrap">
            <table class="copc-mini-table pareto-support-table">
                <thead>
                    <tr><th>Factor SGC</th><th>Grupo</th><th>Frecuencia</th><th>% del Pareto</th><th>Impacto</th><th>Cartera afectada</th><th>Acción recomendada</th></tr>
                </thead>
                <tbody>${normalizados.slice(0, 6).map(item => {
                const pct = totalBrechas ? (item.frecuencia / totalBrechas) * 100 : null;
                return `
                    <tr>
                        <td><strong>${escapeHtml(item.factor_sgc)}</strong></td>
                        <td>${escapeHtml(item.grupo_error_sgc)}</td>
                        <td>${formatoNumero(item.frecuencia)}</td>
                        <td>${pct == null ? "Sin base" : `${pct.toFixed(1)}%`}</td>
                        <td>${badgeGerencialIa(item.impacto, item.impacto === "Alto" ? "alto" : "medio")}</td>
                        <td>${escapeHtml(item.cartera_afectada)}</td>
                        <td>${escapeHtml(item.accion_recomendada)}</td>
                    </tr>
                `;
            }).join("")}</tbody>
            </table>
        </div>
    `;
}

function renderParetoSgcChartIa(rows, options = {}) {
    const items = [...(rows || [])]
        .map(row => ({
            label: row.factor_sgc || row.item || row.brecha || "-",
            grupo: row.grupo_error_sgc || row.grupo || "-",
            frecuencia: Number(row.frecuencia ?? row.ceros ?? row.total ?? 0),
        }))
        .filter(row => row.frecuencia > 0)
        .sort((a, b) => b.frecuencia - a.frecuencia)
        .slice(0, options.maxItems || 12);
    const totalErrores = items.reduce((sum, item) => sum + item.frecuencia, 0);
    if (!items.length || !totalErrores) {
        return `<div class="empty-report-state"><strong>No hay brechas suficientes para construir Pareto.</strong><small>Amplía el rango de fechas o selecciona todas las carteras.</small></div>`;
    }

    const width = 1280;
    const height = 500;
    const left = 42;
    const right = 54;
    const top = 32;
    const bottom = 176;
    const chartW = width - left - right;
    const chartH = height - top - bottom;
    const maxFrecuencia = Math.max(...items.map(item => item.frecuencia), 1);
    const slot = chartW / items.length;
    const barW = Math.max(18, Math.min(42, slot * 0.48));
    let acumulado = 0;
    const points = [];
    const bars = items.map((item, index) => {
        acumulado += item.frecuencia;
        const acumPct = acumulado / totalErrores;
        const barH = (item.frecuencia / maxFrecuencia) * chartH;
        const x = left + index * slot + (slot - barW) / 2;
        const y = top + chartH - barH;
        const lineX = x + barW / 2;
        const lineY = top + chartH - (acumPct * chartH);
        points.push(`${lineX.toFixed(1)},${lineY.toFixed(1)}`);
        const labelLines = partirEtiquetaParetoIa(item.label, options.compactLabels ? 3 : 4);
        return `
            <g>
                <rect class="pareto-bar-rect" x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${barW.toFixed(1)}" height="${barH.toFixed(1)}" rx="3"></rect>
                <text class="pareto-count-label" x="${lineX.toFixed(1)}" y="${Math.max(14, y - 7).toFixed(1)}" text-anchor="middle">${formatoNumero(item.frecuencia)}</text>
                <circle class="pareto-dot" cx="${lineX.toFixed(1)}" cy="${lineY.toFixed(1)}" r="3.5"></circle>
                <text class="pareto-pct-label" x="${lineX.toFixed(1)}" y="${Math.max(14, lineY - 9).toFixed(1)}" text-anchor="middle">${(acumPct * 100).toFixed(1)}%</text>
                <text class="pareto-x-label" x="${lineX.toFixed(1)}" y="${height - bottom + 44}" text-anchor="middle">
                    ${labelLines.map((line, lineIndex) => `<tspan x="${lineX.toFixed(1)}" dy="${lineIndex ? 11 : 0}">${escapeHtml(line)}</tspan>`).join("")}
                </text>
            </g>
        `;
    }).join("");
    const yTicks = [0, 25, 50, 75, 100].map(pct => {
        const y = top + chartH - (pct / 100) * chartH;
        return `<text class="pareto-axis-label" x="${width - right + 10}" y="${(y + 3).toFixed(1)}">${pct}%</text>`;
    }).join("");
    return `
        <div class="pareto-chart-card">
            <div class="pareto-chart-head">
                <div>
                    <strong>${escapeHtml(options.title || "Pareto de errores SGC/PEC")}</strong>
                    <span>Barras: frecuencia. Línea: porcentaje acumulado.</span>
                </div>
                <div class="pareto-legend"><span><i></i>Frecuencia</span><span><i class="line"></i>% acumulado</span></div>
            </div>
            <svg class="pareto-svg-chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="${escapeHtml(options.title || "Pareto de errores")}">
                <line class="pareto-axis" x1="${left}" y1="${top + chartH}" x2="${width - right}" y2="${top + chartH}"></line>
                <line class="pareto-axis" x1="${left}" y1="${top}" x2="${left}" y2="${top + chartH}"></line>
                <line class="pareto-axis right" x1="${width - right}" y1="${top}" x2="${width - right}" y2="${top + chartH}"></line>
                ${[0, .25, .5, .75, 1].map(value => {
                    const y = top + chartH - value * chartH;
                    return `<line class="pareto-grid-line" x1="${left}" y1="${y.toFixed(1)}" x2="${width - right}" y2="${y.toFixed(1)}"></line>`;
                }).join("")}
                ${bars}
                <polyline class="pareto-acum-line" points="${points.join(" ")}"></polyline>
                ${yTicks}
            </svg>
        </div>
    `;
}

function partirEtiquetaParetoIa(texto, maxLineas = 4) {
    const palabras = String(texto || "-").replace(/\s+/g, " ").trim().split(" ");
    const lineas = [];
    let actual = "";
    palabras.forEach(palabra => {
        if ((actual + " " + palabra).trim().length > 12 && actual) {
            lineas.push(actual);
            actual = palabra;
        } else {
            actual = `${actual} ${palabra}`.trim();
        }
    });
    if (actual) lineas.push(actual);
    return lineas.slice(0, maxLineas).map((linea, index) => index === maxLineas - 1 && lineas.length > maxLineas ? `${linea}...` : linea);
}

function pintarAgentesPriorizadosGerencialIa(detalle) {
    const el = document.getElementById("repAgentesPriorizadosGerencialIa");
    if (!el) return;
    const rows = construirAgentesPriorizadosIa(detalle).slice(0, 8);
    if (!rows.length) {
        el.innerHTML = estadoVacioReporteIa(detalle);
        return;
    }
    el.innerHTML = `
        <table class="copc-mini-table">
            <thead>
                <tr><th>Agente</th><th>Supervisor</th><th>Cartera</th><th>Eval.</th><th>Score norm.</th><th>Score val.</th><th>% error crit.</th><th>Brecha principal</th><th>Coaching</th><th>Accion</th></tr>
            </thead>
            <tbody>${rows.map(row => {
                const scoreIa = row.scoreNormalizado == null ? "-" : `${row.scoreNormalizado.toFixed(1)}%`;
                const scoreValidado = row.scoreValidado == null ? "Pendiente" : `${row.scoreValidado.toFixed(1)}%`;
                const claseScoreIa = row.scoreNormalizado != null && row.scoreNormalizado < 70 ? "score-danger" : "score-ok";
                return `
                    <tr>
                        <td><strong>${escapeHtml(row.agente)}</strong></td>
                        <td>${escapeHtml(row.supervisor)}</td>
                        <td>${escapeHtml(row.cartera)}</td>
                        <td>${formatoNumero(row.evaluaciones)}</td>
                        <td><strong class="${claseScoreIa}">${scoreIa}</strong></td>
                        <td>${scoreValidado}</td>
                        <td>${row.errorCriticoPct.toFixed(1)}%</td>
                        <td>${escapeHtml(row.brechaPrincipal)}</td>
                        <td>${badgeGerencialIa(row.estadoCoaching, claseBadgeEstadoIa(row.estadoCoaching))}</td>
                        <td><button class="historial-action" type="button" onclick="verAnalisisIa(${Number(row.idFeedback || 0)}, 'coaching')">${String(row.estadoCoaching || "").toUpperCase() === "PENDIENTE" ? "Programar" : "Ver plan"}</button></td>
                    </tr>
                `;
            }).join("")}</tbody>
        </table>
    `;
}

function pintarCalibracionConsistenciaReporteIa(detalle) {
    const el = document.getElementById("repCalibracionConsistenciaIa");
    if (!el) return;
    if (!detalle.length) {
        el.innerHTML = estadoVacioReporteIa(detalle);
        return;
    }
    const conSupervisor = detalle.filter(item => item.score_supervisor != null || item.score_final != null);
    const diffs = detalle
        .map(item => Math.abs(Number(item.score_final ?? item.score_calidad ?? 0) - Number(item.score_calidad_ia ?? item.score_calidad ?? 0)))
        .filter(value => !Number.isNaN(value));
    const diferencia = diffs.length ? diffs.reduce((sum, value) => sum + value, 0) / diffs.length : 0;
    const coincidencia = diffs.length ? Math.max(0, 100 - diferencia).toFixed(1) : "-";
    const abiertas = detalle.filter(item => String(item.estado_recalibracion || "").toUpperCase() === "PENDIENTE").length;
    const requiereRevision = detalle.filter(item => item.requiere_revision_humana || item.error_critico).length;
    const discrepancias = construirItemsMayorDiscrepanciaIa(detalle).slice(0, 4);
    el.innerHTML = `
        <div class="calibration-kpis">
            <article><span>Coincidencia IA vs supervisor</span><strong>${coincidencia === "-" ? "-" : `${coincidencia}%`}</strong></article>
            <article><span>Diferencia promedio</span><strong>${diferencia.toFixed(1)} pts</strong></article>
            <article><span>Evaluaciones calibradas</span><strong>${formatoNumero(conSupervisor.length)}</strong></article>
            <article><span>Recalibraciones abiertas</span><strong>${formatoNumero(abiertas)}</strong></article>
            <article><span>Requieren revisión humana</span><strong>${formatoNumero(requiereRevision)}</strong></article>
        </div>
        <div class="mini-table">
            <table>
                <thead><tr><th>Item con mayor discrepancia</th><th>Frecuencia</th><th>Diferencia prom.</th></tr></thead>
                <tbody>${discrepancias.length ? discrepancias.map(item => `
                    <tr><td>${escapeHtml(item.item)}</td><td>${formatoNumero(item.frecuencia)}</td><td>${item.diferencia.toFixed(1)} pts</td></tr>
                `).join("") : `<tr><td colspan="3" class="empty-row">Sin discrepancias registradas.</td></tr>`}</tbody>
            </table>
        </div>
    `;
}

function pintarVistaCoachingIa(detalle) {
    const kpis = document.getElementById("coachingKpisIa");
    const tabla = document.getElementById("coachingTablaIa");
    if (!kpis || !tabla) return;
    const rows = detalle.filter(item => requiereFeedbackIa(item) || requiereCoachingIa(item) || item.estado_coaching || item.fecha_coaching);
    const conteos = contarPorEstadoIa(detalle, "estado_coaching", ["PENDIENTE", "PROGRAMADO", "REALIZADO", "CERRADO"]);
    const feedbackPendiente = detalle.filter(item => requiereFeedbackIa(item) && String(item.estado_feedback || "PENDIENTE").toUpperCase() === "PENDIENTE").length;
    const coachingRequerido = detalle.filter(item => requiereCoachingIa(item)).length;
    kpis.innerHTML = [
        cardKpiTabIa("Pendiente de feedback", feedbackPendiente, "Observación puntual"),
        cardKpiTabIa("Coaching requerido", coachingRequerido, "Plan estructurado"),
        cardKpiTabIa("Coaching programado", conteos.PROGRAMADO || 0, "Con fecha o seguimiento"),
        cardKpiTabIa("Coaching realizado", conteos.REALIZADO || 0, "Sesiones ejecutadas"),
        cardKpiTabIa("Coaching cerrado", conteos.CERRADO || 0, "Casos finalizados"),
    ].join("");
    if (!rows.length) {
        tabla.innerHTML = `<div class="empty-report-state"><strong>No hay coaching pendiente para los filtros seleccionados.</strong><small>Amplía filtros o revisa otro periodo.</small></div>`;
        return;
    }
    tabla.innerHTML = `
        <table class="copc-mini-table">
            <thead><tr><th>Agente</th><th>Supervisor</th><th>Cartera</th><th>Grupo SGC</th><th>Factor</th><th>Score</th><th>Feedback</th><th>Coaching</th><th>Fecha</th><th>Acción</th></tr></thead>
            <tbody>${rows.slice(0, 80).map(row => {
                const estado = row.estado_coaching || (requiereCoachingIa(row) ? "PENDIENTE" : "-");
                const sgc = principalSgcDetalleIa(row);
                return `
                    <tr>
                        <td><strong>${escapeHtml(row.agente || "Sin agente asociado")}</strong></td>
                        <td>${escapeHtml(row.supervisor || "-")}</td>
                        <td>${escapeHtml(row.cartera || "-")}</td>
                        <td>${badgeSgcIa(sgc.grupo)}</td>
                        <td>${escapeHtml(sgc.factor)}</td>
                        <td>${formatoScoreIa(scoreCoachingIa(row))}</td>
                        <td>${badgeGerencialIa(row.estado_feedback || (requiereFeedbackIa(row) ? "PENDIENTE" : "NO REQUIERE"), requiereFeedbackIa(row) ? "medio" : "bajo")}</td>
                        <td>${badgeGerencialIa(estado, claseBadgeEstadoIa(estado))}</td>
                        <td>${row.fecha_coaching ? formatoFecha(row.fecha_coaching) : "-"}</td>
                        <td><button class="historial-action" type="button" onclick="verAnalisisIa(${Number(row.id_feedback || 0)}, 'coaching')">${accionCoachingIa(estado)}</button></td>
                    </tr>
                `;
            }).join("")}</tbody>
        </table>
    `;
}

function pintarVistaCalibracionTabIa(detalle) {
    const kpis = document.getElementById("calibracionKpisIa");
    const tabla = document.getElementById("calibracionTablaIa");
    const discrepancias = document.getElementById("calibracionDiscrepanciasIa");
    if (!kpis || !tabla || !discrepancias) return;
    const diffs = detalle.map(item => Math.abs(Number(item.score_final ?? item.score_calidad ?? 0) - Number(item.score_calidad_ia ?? item.score_calidad ?? 0))).filter(value => !Number.isNaN(value));
    const diferencia = diffs.length ? diffs.reduce((sum, value) => sum + value, 0) / diffs.length : 0;
    const coincidencia = diffs.length ? Math.max(0, 100 - diferencia).toFixed(1) : "-";
    const calibradas = detalle.filter(item => item.score_supervisor != null || item.score_final != null).length;
    const abiertas = detalle.filter(item => String(item.estado_recalibracion || "").toUpperCase() === "PENDIENTE").length;
    const revision = detalle.filter(item => item.requiere_revision_humana || item.error_critico).length;
    kpis.innerHTML = [
        cardKpiTabIa("Coincidencia IA vs supervisor", coincidencia === "-" ? "-" : `${coincidencia}%`, "Meta de consistencia"),
        cardKpiTabIa("Diferencia promedio", `${diferencia.toFixed(1)} pts`, "IA vs score validado"),
        cardKpiTabIa("Evaluaciones calibradas", calibradas, "Con revisión validada"),
        cardKpiTabIa("Recalibraciones abiertas", abiertas, "Pendientes"),
        cardKpiTabIa("Requieren revisión humana", revision, "Casos sensibles"),
    ].join("");
    const rows = detalle.filter(item => String(item.estado_recalibracion || "SIN_APELACION").toUpperCase() !== "SIN_APELACION" || item.requiere_revision_humana);
    if (!rows.length) {
        tabla.innerHTML = `<div class="empty-report-state"><strong>No hay recalibraciones pendientes para los filtros seleccionados.</strong><small>Las solicitudes aparecerán aquí cuando se registren.</small></div>`;
    } else {
        tabla.innerHTML = `
            <table class="copc-mini-table">
                <thead><tr><th>Evaluación</th><th>Agente</th><th>Supervisor</th><th>Score IA</th><th>Score supervisor</th><th>Diferencia</th><th>Estado recalibración</th><th>Acción</th></tr></thead>
                <tbody>${rows.slice(0, 80).map(row => {
                    const scoreIa = Number(row.score_calidad_ia ?? row.score_calidad ?? 0);
                    const scoreSup = Number(row.score_supervisor ?? row.score_final ?? row.score_calidad ?? 0);
                    const diff = Math.abs(scoreSup - scoreIa);
                    const estado = formatearEstadoRecalibracionIa(row.estado_recalibracion);
                    return `
                        <tr>
                            <td>${escapeHtml(row.id_feedback || "-")}</td>
                            <td>${escapeHtml(row.agente || "Sin agente asociado")}</td>
                            <td>${escapeHtml(row.supervisor || "-")}</td>
                            <td>${scoreIa.toFixed(1)}</td>
                            <td>${scoreSup.toFixed(1)}</td>
                            <td>${diff.toFixed(1)} pts</td>
                            <td>${badgeGerencialIa(estado, String(row.estado_recalibracion || "").toUpperCase() === "PENDIENTE" ? "alto" : "medio")}</td>
                            <td><button class="historial-action" type="button" onclick="verAnalisisIa(${Number(row.id_feedback || 0)})">${String(row.estado_recalibracion || "").toUpperCase() === "PENDIENTE" ? "Resolver" : "Ver"}</button></td>
                        </tr>
                    `;
                }).join("")}</tbody>
            </table>
        `;
    }
    const items = construirItemsMayorDiscrepanciaIa(detalle).slice(0, 8);
    discrepancias.innerHTML = items.length ? `
        <table><thead><tr><th>Ítem</th><th>Frecuencia</th><th>Diferencia prom.</th></tr></thead>
        <tbody>${items.map(item => `<tr><td>${escapeHtml(item.item)}</td><td>${formatoNumero(item.frecuencia)}</td><td>${item.diferencia.toFixed(1)} pts</td></tr>`).join("")}</tbody></table>
    ` : `<div class="empty-report-state"><strong>No hay discrepancias registradas.</strong></div>`;
}

function pintarVistaReportesSgcIa(data, detalle) {
    pintarPrecisionAsesorSgcIa(detalle);
    pintarDistribucionGrupoSgcReporteIa(data, detalle);
    pintarEvolucionSgcIa(detalle);
}

function pintarPrecisionAsesorSgcIa(detalle) {
    const el = document.getElementById("repPrecisionAsesorSgcIa");
    if (!el) return;
    const grupos = {};
    detalle.forEach(row => {
        const agente = row.agente || "Sin agente asociado";
        const actual = grupos[agente] || { agente, total: 0, score: 0, criticos: 0, noCriticos: 0 };
        actual.total += 1;
        actual.score += Number(row.score_final ?? row.score_calidad ?? 0);
        const resumen = resumenSgcDesdeItemsIa(itemsSgcDetalleIa(row));
        actual.criticos += (resumen["Errores críticos del negocio"] || 0) + (resumen["Errores críticos del usuario final"] || 0) + (resumen["Errores críticos de cumplimiento"] || 0);
        actual.noCriticos += resumen["Errores no críticos"] || 0;
        grupos[agente] = actual;
    });
    const rows = Object.values(grupos).sort((a, b) => (a.score / a.total) - (b.score / b.total)).slice(0, 12);
    el.innerHTML = rows.length ? `
        <table><thead><tr><th>Asesor</th><th>Evaluaciones</th><th>Score promedio</th><th>Meta</th><th>Brecha vs meta</th><th>Críticos</th><th>No críticos</th><th>Estado</th></tr></thead>
        <tbody>${rows.map(row => {
            const score = row.total ? row.score / row.total : 0;
            const brecha = score - 85;
            return `<tr><td>${escapeHtml(row.agente)}</td><td>${formatoNumero(row.total)}</td><td>${score.toFixed(1)}%</td><td>85%</td><td>${brecha.toFixed(1)} pts</td><td>${formatoNumero(row.criticos)}</td><td>${formatoNumero(row.noCriticos)}</td><td>${badgeGerencialIa(score >= 85 ? "En meta" : score >= 70 ? "Atención" : "Crítico", score >= 85 ? "bajo" : score >= 70 ? "medio" : "alto")}</td></tr>`;
        }).join("")}</tbody></table>
    ` : estadoVacioReporteIa(detalle);
}

function construirParetoSgcIa(data, detalle) {
    if (!detalle.length) return [];
    const map = {};
    detalle.forEach((row, rowIndex) => {
        const idEvaluacion = String(row.id_feedback || row.id_llamada || row.archivo_nombre || rowIndex);
        itemsSgcDetalleIa(row).forEach(raw => {
            const item = itemSgcIa(raw);
            const cal = String(item.calificacion || "").toLowerCase();
            if (esValorNoAplicableIa(item.grupo_error_sgc) || ["cumple", "no aplica"].includes(cal)) return;
            const key = `${item.grupo_error_sgc}::${item.factor_sgc}`;
            const actual = map[key] || {
                grupo_error_sgc: item.grupo_error_sgc,
                factor_sgc: item.factor_sgc,
                frecuencia: 0,
                evaluaciones_afectadas: 0,
                hallazgos: 0,
                evaluaciones_set: new Set(),
                impacto: item.grupo_error_sgc.includes("críticos") ? "Alto" : "Medio",
                accion_recomendada: accionSugeridaSgcIa(item),
            };
            actual.hallazgos += 1;
            actual.evaluaciones_set.add(idEvaluacion);
            actual.evaluaciones_afectadas = actual.evaluaciones_set.size;
            actual.frecuencia = actual.evaluaciones_afectadas;
            map[key] = actual;
        });
    });
    return Object.values(map)
        .map(item => {
            const { evaluaciones_set, ...rest } = item;
            return rest;
        })
        .sort((a, b) => b.frecuencia - a.frecuencia || b.hallazgos - a.hallazgos || String(a.factor_sgc).localeCompare(String(b.factor_sgc)));
}

function pintarDistribucionGrupoSgcReporteIa(data, detalle) {
    const el = document.getElementById("repParetoGrupoSgcIa");
    if (!el) return;
    const conteos = resumenSgcDesdeItemsIa(detalle.flatMap(row => itemsSgcDetalleIa(row)));
    const rows = SGC_GRUPOS_IA.map(grupo => ({ grupo, total: conteos[grupo] || 0 })).sort((a, b) => b.total - a.total);
    el.innerHTML = rows.some(row => row.total) ? `
        <table><thead><tr><th>Grupo SGC/PEC</th><th>Frecuencia</th><th>Participación</th></tr></thead>
        <tbody>${rows.map(row => {
            const total = rows.reduce((sum, item) => sum + item.total, 0);
            const pct = total ? (row.total / total) * 100 : 0;
            return `<tr><td><strong>${escapeHtml(row.grupo)}</strong></td><td>${formatoNumero(row.total)}</td><td><div class="copc-table-meter"><span>${pct.toFixed(1)}%</span><i style="width:${Math.max(3, pct)}%"></i></div></td></tr>`;
        }).join("")}</tbody></table>
    ` : estadoVacioReporteIa(detalle);
}

function pintarEvolucionSgcIa(detalle) {
    const el = document.getElementById("repEvolucionSgcIa");
    if (!el) return;
    const semanas = {};
    detalle.forEach(row => {
        const semana = claveSemanaClienteIa(row.fecha_llamada || row.fecha_creacion);
        const actual = semanas[semana] || { semana, total: 0, score: 0, criticos: 0, coaching: 0, feedback: 0 };
        actual.total += 1;
        actual.score += Number(row.score_final ?? row.score_calidad ?? 0);
        const resumen = resumenSgcDesdeItemsIa(itemsSgcDetalleIa(row));
        actual.criticos += (resumen["Errores críticos del negocio"] || 0) + (resumen["Errores críticos del usuario final"] || 0) + (resumen["Errores críticos de cumplimiento"] || 0);
        if (requiereCoachingIa(row)) actual.coaching += 1;
        if (requiereFeedbackIa(row)) actual.feedback += 1;
        semanas[semana] = actual;
    });
    const rows = Object.values(semanas).sort((a, b) => a.semana.localeCompare(b.semana));
    el.innerHTML = rows.length ? `
        <table><thead><tr><th>Semana</th><th>Score promedio</th><th>Errores críticos</th><th>Coaching pendiente</th><th>Feedback pendiente</th></tr></thead>
        <tbody>${rows.map(row => `<tr><td>${escapeHtml(row.semana)}</td><td>${(row.score / row.total).toFixed(1)}%</td><td>${formatoNumero(row.criticos)}</td><td>${formatoNumero(row.coaching)}</td><td>${formatoNumero(row.feedback)}</td></tr>`).join("")}</tbody></table>
    ` : estadoVacioReporteIa(detalle);
}

function pintarVistaAlertasIa(detalle) {
    const kpis = document.getElementById("alertasKpisIa");
    const tabla = document.getElementById("alertasTablaIa");
    if (!kpis || !tabla) return;
    const anulantes = detalle.filter(item => item.falta_anulante).length;
    const criticos = detalle.filter(item => item.error_critico || Number(item.total_puntos_criticos || 0) > 0).length;
    const revision = detalle.filter(item => item.requiere_revision_humana).length;
    const coachingVencido = detalle.filter(item => requiereCoachingIa(item) && item.fecha_coaching && new Date(item.fecha_coaching) < new Date()).length;
    const recal = detalle.filter(item => String(item.estado_recalibracion || "").toUpperCase() === "PENDIENTE").length;
    kpis.innerHTML = [
        cardKpiTabIa("Faltas anulantes", anulantes, "Score automático 0"),
        cardKpiTabIa("Errores críticos", criticos, "Riesgo operativo"),
        cardKpiTabIa("Revisión humana requerida", revision, "Casos sensibles"),
        cardKpiTabIa("Coaching vencido", coachingVencido, "Seguimiento atrasado"),
        cardKpiTabIa("Recalibración pendiente", recal, "Solicitudes abiertas"),
    ].join("");
    const rows = detalle.filter(item => item.falta_anulante || item.error_critico || item.requiere_revision_humana || Number(item.total_puntos_criticos || 0) > 0 || String(item.estado_recalibracion || "").toUpperCase() === "PENDIENTE");
    if (!rows.length) {
        tabla.innerHTML = `<div class="empty-report-state"><strong>No hay alertas críticas para los filtros seleccionados.</strong></div>`;
        return;
    }
    tabla.innerHTML = `
        <table class="copc-mini-table">
            <thead><tr><th>Evaluación</th><th>Agente</th><th>Cartera</th><th>Alerta</th><th>Riesgo</th><th>Acción</th></tr></thead>
            <tbody>${rows.slice(0, 80).map(row => `
                <tr>
                    <td>${escapeHtml(row.id_feedback || "-")}</td>
                    <td>${escapeHtml(row.agente || "Sin agente asociado")}</td>
                    <td>${escapeHtml(row.cartera || "-")}</td>
                    <td>${escapeHtml(alertaPrincipalIa(row))}</td>
                    <td>${badgeGerencialIa(formatearRiesgoVisibleIa(row.nivel_oportunidad_mejora), claseBadgeRiesgoIa(row.nivel_oportunidad_mejora))}</td>
                    <td><button class="historial-action" type="button" onclick="verAnalisisIa(${Number(row.id_feedback || 0)})">Ver</button></td>
                </tr>
            `).join("")}</tbody>
        </table>
    `;
}

function pintarVistaPromptIa() {
    setText("promptOrigenResumenIa", valorTextoSeguroIa(document.getElementById("promptOrigenIa")?.textContent));
    setText("promptCarteraResumenIa", document.getElementById("promptCarteraIa")?.selectedOptions?.[0]?.textContent || "Prompt general");
    setText("promptVersionResumenIa", "No disponible");
    setText("promptFechaResumenIa", extraerPromptMetaIa("fecha") || "No disponible");
    setText("promptUsuarioResumenIa", extraerPromptMetaIa("usuario") || "No disponible");
    setText("promptEstadoResumenIa", "Activo");
}

function cardKpiTabIa(titulo, valor, subtitulo) {
    return `<article class="tab-kpi-card"><span>${escapeHtml(titulo)}</span><strong>${escapeHtml(valor)}</strong><small>${escapeHtml(subtitulo || "")}</small></article>`;
}

function contarPorEstadoIa(items, field, estados) {
    const result = Object.fromEntries(estados.map(estado => [estado, 0]));
    items.forEach(item => {
        const estado = String(item[field] || (field === "estado_coaching" && requiereCoachingIa(item) ? "PENDIENTE" : "")).toUpperCase();
        if (result[estado] != null) result[estado] += 1;
    });
    return result;
}

function formatoScoreIa(value) {
    if (value === null || value === undefined || value === "") return "-";
    const numero = Number(value);
    return Number.isNaN(numero) ? "-" : `${numero.toFixed(1)}%`;
}

function scoreCoachingIa(row) {
    if (row.score_final_validado !== null && row.score_final_validado !== undefined) return row.score_final_validado;
    if (row.score_normalizado !== null && row.score_normalizado !== undefined) return row.score_normalizado;
    if (row.score_ia !== null && row.score_ia !== undefined) return row.score_ia;
    if (row.score_final !== null && row.score_final !== undefined) return row.score_final;
    if (row.score_calidad_ia !== null && row.score_calidad_ia !== undefined) return row.score_calidad_ia;
    return null;
}

function valorTextoSeguroIa(value, fallback = "No disponible") {
    const texto = String(value || "").trim();
    return texto && texto !== "-" ? texto : fallback;
}

function extraerPromptMetaIa(tipo) {
    const meta = document.getElementById("promptMetaIa")?.textContent || "";
    if (!meta || meta === "-") return "";
    if (tipo === "usuario") {
        const match = meta.match(/por\s+(.+)$/i);
        return match?.[1]?.trim() || "";
    }
    const match = meta.match(/actualizaci[oó]n:\s*([^.]*)/i);
    return match?.[1]?.trim() || "";
}

function accionCoachingIa(estado) {
    const value = String(estado || "").toUpperCase();
    if (value === "PENDIENTE") return "Programar";
    if (["PROGRAMADO", "EN_PROCESO"].includes(value)) return "Cerrar";
    return "Ver";
}

function alertaPrincipalIa(row) {
    if (row.falta_anulante) return "Falta anulante";
    if (row.error_critico || Number(row.total_puntos_criticos || 0) > 0) return brechaPrincipalDetalleIa(row);
    if (row.requiere_revision_humana) return "Revisión humana requerida";
    if (String(row.estado_recalibracion || "").toUpperCase() === "PENDIENTE") return "Recalibración pendiente";
    return "-";
}

function claseBadgeRiesgoIa(value) {
    const clase = claseRiesgoCardIa(value);
    if (clase === "state-danger") return "alto";
    if (clase === "state-warning") return "medio";
    if (clase === "state-ok") return "bajo";
    return "medio";
}

function promedioDetalleIa(items, getter) {
    const valores = items
        .map(item => Number(getter(item)))
        .filter(value => !Number.isNaN(value));
    if (!valores.length) return null;
    return valores.reduce((sum, value) => sum + value, 0) / valores.length;
}

function scoreCalidadResumenIa(item) {
    return esEvaluacionValidadaIa(item) ? scoreValidadoResumenIa(item) : undefined;
}

function scoreValidadoResumenIa(item) {
    if (!esEvaluacionValidadaIa(item)) return undefined;
    const campos = [item?.score_supervisor, item?.score_final_validado, item?.score_final];
    return primerNumeroIa(campos);
}

function scoreIaPreliminarResumenIa(item) {
    const campos = [item?.score_calidad_ia, item?.score_ia, item?.score_normalizado, item?.score_calidad];
    return primerNumeroIa(campos);
}

function primerNumeroIa(campos = []) {
    for (const campo of campos) {
        if (campo === null || campo === undefined || campo === "") continue;
        const numero = Number(campo);
        if (!Number.isNaN(numero)) return numero;
    }
    return undefined;
}

function esEvaluacionValidadaIa(item = {}) {
    const estado = String(item.estado_revision || "PENDIENTE").toUpperCase();
    const estadosValidos = ["REVISADO", "FEEDBACK_ENVIADO", "CERRADO"];
    const tieneScoreFinal = [item.score_supervisor, item.score_final_validado, item.score_final].some(valor => valor !== null && valor !== undefined && valor !== "");
    return estadosValidos.includes(estado) && tieneScoreFinal;
}

function requiereCoachingIa(item) {
    const estado = String(item.estado_coaching || "PENDIENTE").toUpperCase();
    const score = Number(item.score_final ?? item.score_calidad ?? 0);
    return !["REALIZADO", "CERRADO"].includes(estado) && (item.requiere_coaching || score < 70 || item.nivel_riesgo === "ALTO" || item.error_critico || item.falta_anulante || Number(item.total_puntos_criticos || 0) > 0);
}

function requiereFeedbackIa(item) {
    const estado = String(item.estado_feedback || "PENDIENTE").toUpperCase();
    const score = Number(item.score_final ?? item.score_calidad ?? 0);
    return !["CERRADO", "NO_REQUIERE"].includes(estado) && (item.requiere_feedback || score < 80 || requiereCoachingIa(item));
}

function principalSgcDetalleIa(row = {}) {
    const items = itemsSgcDetalleIa(row);
    const candidato = items.find(item => item.requiere_coaching || item.requiere_feedback || Number(item.nota || 0) === 0) || items[0] || {};
    const sgc = itemSgcIa(candidato);
    return { grupo: sgc.grupo_error_sgc || "No aplica", factor: sgc.factor_sgc || brechaPrincipalDetalleIa(row) || "-" };
}

function badgeSgcIa(grupo) {
    const value = String(grupo || "No aplica");
    let tipo = "medio";
    if (value.includes("cumplimiento")) tipo = "alto";
    else if (value.includes("negocio")) tipo = "alto";
    else if (value.includes("usuario")) tipo = "medio";
    else if (value.includes("no críticos")) tipo = "bajo";
    return badgeGerencialIa(value, tipo);
}

function accionSugeridaSgcIa(item = {}) {
    const grupo = String(item.grupo_error_sgc || "").toLowerCase();
    if (grupo.includes("cumplimiento")) return "Revisión humana y coaching inmediato";
    if (grupo.includes("negocio")) return "Coaching de cierre y negociación";
    if (grupo.includes("usuario")) return "Feedback sobre claridad y experiencia";
    return "Feedback puntual";
}

function estadoVacioReporteIa(detalle) {
    const ultima = [...(reporteriaActualIa?.detalle || [])].sort((a, b) => String(b.fecha_creacion || "").localeCompare(String(a.fecha_creacion || "")))[0];
    return `
        <div class="empty-report-state">
            <strong>No hay evaluaciones para los filtros seleccionados.</strong>
            <span>Última evaluación registrada: ${ultima ? formatoFecha(ultima.fecha_creacion || ultima.fecha_llamada) : "-"}</span>
            <small>Sugerencia: amplia el rango de fechas o selecciona todas las carteras.</small>
        </div>
    `;
}

function toggleFiltrosResumenIa(force) {
    const panel = document.getElementById("filtrosReporteIa");
    if (!panel) return;
    const mostrar = typeof force === "boolean" ? force : panel.classList.contains("oculto");
    panel.classList.toggle("oculto", !mostrar);
    document.getElementById("btnToggleFiltrosIa")?.classList.toggle("active", mostrar);
}

function aplicarFiltrosResumenIa() {
    toggleFiltrosResumenIa(false);
    cargarReporteriaIa();
}

function actualizarResumenFiltrosIa() {
    const filtros = [
        ["Cartera", textoFiltroSelectIa("filtroCarteraIa")],
        ["Supervisor", textoFiltroSelectIa("filtroSupervisorIa")],
        ["Agente", valor("filtroAgenteIa")],
        ["Búsqueda", valor("filtroBusquedaEvaluacionIa")],
        ["Riesgo", textoFiltroSelectIa("filtroRiesgoIa")],
        ["Resultado", textoFiltroSelectIa("filtroResultadoIa")],
        ["Tipo", textoFiltroSelectIa("filtroTipoLlamadaIa")],
        ["Revisión", textoFiltroSelectIa("filtroRevisionIa")],
        ["Error crítico", textoFiltroSelectIa("filtroErrorCriticoIa")],
        ["Plan", textoFiltroSelectIa("filtroCoachingIa")],
        ["Calibración", textoFiltroSelectIa("filtroCalibracionIa")],
    ].filter(([, value]) => value);
    const chips = document.getElementById("chipsFiltrosIa");
    if (chips) {
        chips.innerHTML = filtros.length
            ? filtros.slice(0, 5).map(([label, value]) => `<span>${escapeHtml(label)}: ${escapeHtml(value)}</span>`).join("") + (filtros.length > 5 ? `<span>+${filtros.length - 5} más</span>` : "")
            : `<span>Todos los filtros</span>`;
    }
    setText("contadorFiltrosIa", filtros.length);
    const estado = document.getElementById("estadoDatosResumenIa");
    if (estado) estado.textContent = `Datos actualizados ${new Date().toLocaleTimeString("es-PE", { hour: "2-digit", minute: "2-digit" })}`;
}

function textoFiltroSelectIa(id) {
    const el = document.getElementById(id);
    if (!el) return "";
    if (!el.value) return "";
    return el.selectedOptions?.[0]?.textContent?.trim() || el.value;
}

function evaluacionesAfectadasPorFactorIa(detalle, factor) {
    const target = String(factor || "").toLowerCase();
    if (!target) return 0;
    return detalle.filter(row => itemsSgcDetalleIa(row).some(raw => {
        const item = itemSgcIa(raw);
        const cal = String(item.calificacion || "").toLowerCase();
        return String(item.factor_sgc || "").toLowerCase() === target && !["cumple", "no aplica"].includes(cal);
    })).length;
}

function accionesVencidasIa(detalle) {
    const ahora = new Date();
    return detalle.filter(item => {
        const estado = String(item.estado_coaching || "").toUpperCase();
        if (!item.fecha_coaching || ["REALIZADO", "CERRADO"].includes(estado)) return false;
        const fecha = new Date(item.fecha_coaching);
        return !Number.isNaN(fecha.getTime()) && fecha < ahora;
    }).length;
}

function nombreAgenteCortoIa(nombre) {
    const limpio = nombreAgenteLimpioIa(nombre);
    return limpio.length > 28 ? `${limpio.slice(0, 25)}...` : limpio;
}

function nombreAgenteLimpioIa(nombre) {
    const texto = String(nombre || "").trim();
    if (!texto) return "Sin agente";
    const partes = texto.split(/\s+-\s+/);
    return partes.length > 1 ? partes[partes.length - 1] : texto;
}

function codigoAgenteIa(nombre) {
    const texto = String(nombre || "").trim();
    const partes = texto.split(/\s+-\s+/);
    return partes.length > 1 ? partes[0] : "";
}

function inicialesAgenteIa(nombre) {
    const texto = nombreAgenteLimpioIa(nombre);
    if (!texto) return "SA";
    const partes = texto.split(/\s+/).filter(Boolean);
    return partes.slice(0, 2).map(parte => parte.charAt(0).toUpperCase()).join("") || "SA";
}

function badgeGerencialIa(texto, tipo = "medio") {
    return `<span class="executive-badge ${escapeHtml(tipo)}">${escapeHtml(texto || "-")}</span>`;
}

function claseBadgeEstadoIa(estado) {
    const value = String(estado || "").toUpperCase();
    if (["CERRADO", "REALIZADO", "REVISADO", "CONTROLADO"].includes(value)) return "bajo";
    if (["PROGRAMADO", "EN_PROCESO", "MEDIA", "MEDIO"].includes(value)) return "medio";
    return "alto";
}

function carteraMasAfectadaPorBrechaIa(detalle, itemNombre) {
    const grupos = {};
    detalle.forEach(row => {
        const tieneBrecha = (row.brechas_items || []).some(item => String(item.item || "").toLowerCase() === String(itemNombre || "").toLowerCase());
        if (!tieneBrecha) return;
        const cartera = row.cartera || "Sin cartera";
        grupos[cartera] = (grupos[cartera] || 0) + 1;
    });
    const top = Object.entries(grupos).sort((a, b) => b[1] - a[1])[0];
    return top ? top[0] : "-";
}

function carteraMasAfectadaPorFactorSgcIa(detalle, factorNombre) {
    const grupos = {};
    detalle.forEach(row => {
        const tieneFactor = itemsSgcDetalleIa(row).some(raw => {
            const item = itemSgcIa(raw);
            const calificacion = String(item.calificacion || "").toLowerCase();
            return !["cumple", "no aplica"].includes(calificacion)
                && String(item.factor_sgc || "").toLowerCase() === String(factorNombre || "").toLowerCase();
        });
        if (!tieneFactor) return;
        const cartera = row.cartera || "Sin cartera";
        grupos[cartera] = (grupos[cartera] || 0) + 1;
    });
    const top = Object.entries(grupos).sort((a, b) => b[1] - a[1])[0];
    return top ? top[0] : "";
}

function impactoBrechaIa(item, frecuencia) {
    const texto = String(item || "").toLowerCase();
    if (texto.includes("etico") || texto.includes("abuso") || texto.includes("identidad") || texto.includes("cierre") || frecuencia >= 5) return "Alto";
    return "Medio";
}

function construirAgentesPriorizadosIa(detalle) {
    const grupos = {};
    detalle.forEach(row => {
        const agente = row.agente || "Sin agente asociado";
        const key = `${agente}||${row.cartera || ""}`;
        const actual = grupos[key] || {
            agente,
            supervisor: row.supervisor || "-",
            cartera: row.cartera || "-",
            evaluaciones: 0,
            scoreTotal: 0,
            scoreValidadoConteo: 0,
            scoreIaTotal: 0,
            scoreIaConteo: 0,
            criticos: 0,
            coaching: {},
            brechas: {},
            idFeedback: row.id_feedback,
        };
        actual.evaluaciones += 1;
        const scoreValidado = scoreValidadoResumenIa(row);
        const scoreIa = scoreIaPreliminarResumenIa(row);
        if (scoreValidado != null) {
            actual.scoreTotal += scoreValidado;
            actual.scoreValidadoConteo += 1;
        }
        if (scoreIa != null) {
            actual.scoreIaTotal += scoreIa;
            actual.scoreIaConteo += 1;
        }
        actual.criticos += row.error_critico || row.falta_anulante || Number(row.total_puntos_criticos || 0) > 0 ? 1 : 0;
        actual.coaching[row.estado_coaching || "PENDIENTE"] = (actual.coaching[row.estado_coaching || "PENDIENTE"] || 0) + 1;
        const principal = brechaPrincipalDetalleIa(row);
        if (principal !== "-") actual.brechas[principal] = (actual.brechas[principal] || 0) + 1;
        actual.idFeedback = row.id_feedback || actual.idFeedback;
        grupos[key] = actual;
    });
    return Object.values(grupos)
        .filter(row => row.agente !== "Sin agente asociado")
        .map(row => {
            const estadoCoaching = Object.entries(row.coaching).sort((a, b) => b[1] - a[1])[0]?.[0] || "PENDIENTE";
            const brechaPrincipal = Object.entries(row.brechas).sort((a, b) => b[1] - a[1])[0]?.[0] || "-";
            return {
                ...row,
                scoreNormalizado: row.scoreIaConteo ? row.scoreIaTotal / row.scoreIaConteo : null,
                scoreValidado: row.scoreValidadoConteo ? row.scoreTotal / row.scoreValidadoConteo : null,
                errorCriticoPct: row.evaluaciones ? (row.criticos / row.evaluaciones) * 100 : 0,
                estadoCoaching,
                brechaPrincipal,
            };
        })
        .sort((a, b) => b.errorCriticoPct - a.errorCriticoPct || (a.scoreValidado ?? 999) - (b.scoreValidado ?? 999) || b.evaluaciones - a.evaluaciones);
}

function brechaPrincipalDetalleIa(row) {
    const notas = Object.entries(row.notas_segmento || {}).sort((a, b) => Number(a[1].porcentaje || 0) - Number(b[1].porcentaje || 0));
    return notas[0]?.[0] ? formatearSegmentoIa(notas[0][0]) : "-";
}

function construirItemsMayorDiscrepanciaIa(detalle) {
    const grupos = {};
    detalle.forEach(row => {
        Object.entries(row.notas_segmento || {}).forEach(([segmento, data]) => {
            const diff = Math.abs(Number(row.score_final ?? row.score_calidad ?? 0) - Number(row.score_calidad_ia ?? row.score_calidad ?? 0));
            const actual = grupos[segmento] || { item: formatearSegmentoIa(segmento), frecuencia: 0, diferenciaTotal: 0 };
            actual.frecuencia += 1;
            actual.diferenciaTotal += diff;
            grupos[segmento] = actual;
        });
    });
    return Object.values(grupos)
        .map(item => ({ ...item, diferencia: item.frecuencia ? item.diferenciaTotal / item.frecuencia : 0 }))
        .sort((a, b) => b.diferencia - a.diferencia);
}

function porcentajeObservadasIa(data) {
    const total = Number(data.total_audios || 0);
    if (!total) return "-";
    const observadas = Math.min(total, Number(data.items_nota_cero || 0));
    return `${((observadas / total) * 100).toFixed(1)}%`;
}

function prepararFiltrosReporteIa() {
    ["filtroCarteraIa", "filtroSupervisorIa", "filtroAgenteIa", "filtroBusquedaEvaluacionIa", "filtroRiesgoIa", "filtroResultadoIa", "filtroTipoLlamadaIa", "filtroRevisionIa", "filtroErrorCriticoIa", "filtroCoachingIa", "filtroCalibracionIa"].forEach(id => {
        const el = document.getElementById(id);
        if (!el) return;
        const evento = el.tagName === "INPUT" ? "input" : "change";
        el.addEventListener(evento, () => {
            detalleReportePaginaIa = 1;
            evaluacionesPaginaIa = 1;
            if (reporteriaActualIa) renderReporteriaIa(reporteriaActualIa);
        });
    });
    ["filtroFechaDesdeIa", "filtroFechaHastaIa"].forEach(id => {
        document.getElementById(id)?.addEventListener("change", () => {
            actualizarRangoFechaDesdeCalendariosIa();
            periodoAutoAjustadoIa = false;
            actualizarAvisoPeriodoIa("");
            detalleReportePaginaIa = 1;
            evaluacionesPaginaIa = 1;
            if (reporteriaActualIa) renderReporteriaIa(reporteriaActualIa);
        });
    });
    setRangoFiltroFechaIa(rangoMesActualIa());
}

function ajustarPeriodoDefaultIa(items) {
    if (periodoAutoAjustadoIa) return;
    if (!Array.isArray(items) || !items.length) {
        actualizarAvisoPeriodoIa("");
        return;
    }
    const filtro = valor("filtroFechaIa");
    if (filtro && filtro !== rangoMesActualIa()) return;

    const filtradosMes = aplicarFiltrosDetalleIa(items);
    if (filtradosMes.length) {
        actualizarAvisoPeriodoIa("");
        return;
    }

    const base = aplicarFiltrosDetalleSinFechaIa(items);
    const fechas = (base.length ? base : items)
        .map(item => parseFechaIa(item.fecha_llamada || item.fecha_creacion))
        .filter(Boolean)
        .sort((a, b) => a - b);
    if (!fechas.length) return;

    const hasta = fechas[fechas.length - 1];
    const desde = new Date(hasta);
    desde.setDate(hasta.getDate() - 29);
    setRangoFiltroFechaIa(`${formatoFechaCortaIa(desde)} - ${formatoFechaCortaIa(hasta)}`);
    periodoAutoAjustadoIa = true;
    actualizarAvisoPeriodoIa(`Mostrando último periodo con evaluaciones disponibles: ${formatoFechaCortaIa(desde)} - ${formatoFechaCortaIa(hasta)}`);
}

function aplicarFiltrosDetalleSinFechaIa(items) {
    const cartera = valor("filtroCarteraIa").toLowerCase();
    const supervisor = valor("filtroSupervisorIa").toLowerCase();
    const agente = valor("filtroAgenteIa").toLowerCase();
    const busqueda = valor("filtroBusquedaEvaluacionIa").toLowerCase();
    const riesgo = valor("filtroRiesgoIa").toLowerCase();
    const resultado = valor("filtroResultadoIa").toLowerCase();
    const tipoLlamada = valor("filtroTipoLlamadaIa").toLowerCase();
    const revision = valor("filtroRevisionIa").toLowerCase();
    const errorCritico = valor("filtroErrorCriticoIa").toLowerCase();
    const coaching = valor("filtroCoachingIa").toLowerCase();
    const calibracion = valor("filtroCalibracionIa").toLowerCase();
    return items.filter(item => {
        if (cartera && !String(item.cartera || "").toLowerCase().includes(cartera)) return false;
        if (supervisor && !String(item.supervisor || "").toLowerCase().includes(supervisor)) return false;
        if (agente && !String(item.agente || "").toLowerCase().includes(agente)) return false;
        if (busqueda && !textoBusquedaEvaluacionIa(item).includes(busqueda)) return false;
        if (riesgo && nivelRiesgoDetalleIa(item).toLowerCase() !== riesgo) return false;
        if (resultado && resultadoIaDetalle(item).toLowerCase() !== resultado) return false;
        if (tipoLlamada && !String(item.tipo_llamada || "").toLowerCase().includes(tipoLlamada)) return false;
        if (revision === "revision_humana") {
            if (!item.requiere_revision_humana) return false;
        } else if (revision && String(item.estado_revision || "PENDIENTE").toLowerCase() !== revision) return false;
        if (errorCritico === "si" && !tieneErrorCriticoEvaluacionIa(item)) return false;
        if (errorCritico === "no" && tieneErrorCriticoEvaluacionIa(item)) return false;
        if (coaching && String(item.estado_coaching || "PENDIENTE").toLowerCase() !== coaching) return false;
        if (calibracion && String(item.estado_recalibracion || "SIN_APELACION").toLowerCase() !== calibracion) return false;
        return true;
    });
}

function actualizarAvisoPeriodoIa(texto) {
    const aviso = document.getElementById("avisoPeriodoIa");
    if (!aviso) return;
    aviso.textContent = texto || "";
    aviso.classList.toggle("oculto", !texto);
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
    document.getElementById("evaluacionesPageSizeIa")?.addEventListener("change", event => {
        evaluacionesPageSizeIa = Number(event.target.value || 10);
        evaluacionesPaginaIa = 1;
        pintarBandejaEvaluacionesIa(detalleReporteIa);
    });
    document.getElementById("evaluacionesPrevIa")?.addEventListener("click", () => {
        if (evaluacionesPaginaIa <= 1) return;
        evaluacionesPaginaIa -= 1;
        pintarBandejaEvaluacionesIa(detalleReporteIa);
    });
    document.getElementById("evaluacionesNextIa")?.addEventListener("click", () => {
        if (evaluacionesPaginaIa >= totalPaginasEvaluacionesIa()) return;
        evaluacionesPaginaIa += 1;
        pintarBandejaEvaluacionesIa(detalleReporteIa);
    });
    document.getElementById("busquedaRapidaEvaluacionesIa")?.addEventListener("input", event => {
        setValue("filtroBusquedaEvaluacionIa", event.target.value);
        evaluacionesPaginaIa = 1;
        detalleReportePaginaIa = 1;
        if (reporteriaActualIa) renderReporteriaIa(reporteriaActualIa);
    });
}

function aplicarFiltrosDetalleIa(items) {
    const cartera = valor("filtroCarteraIa").toLowerCase();
    const supervisor = valor("filtroSupervisorIa").toLowerCase();
    const agente = valor("filtroAgenteIa").toLowerCase();
    const busqueda = valor("filtroBusquedaEvaluacionIa").toLowerCase();
    const riesgo = valor("filtroRiesgoIa").toLowerCase();
    const resultado = valor("filtroResultadoIa").toLowerCase();
    const tipoLlamada = valor("filtroTipoLlamadaIa").toLowerCase();
    const revision = valor("filtroRevisionIa").toLowerCase();
    const errorCritico = valor("filtroErrorCriticoIa").toLowerCase();
    const coaching = valor("filtroCoachingIa").toLowerCase();
    const calibracion = valor("filtroCalibracionIa").toLowerCase();
    const rango = parseRangoFechasIa(valor("filtroFechaIa"));

    return items.filter(item => {
        const fecha = parseFechaIa(item.fecha_llamada || item.fecha_creacion);
        if (rango.desde && (!fecha || fecha < rango.desde)) return false;
        if (rango.hasta && (!fecha || fecha > rango.hasta)) return false;
        if (cartera && !String(item.cartera || "").toLowerCase().includes(cartera)) return false;
        if (supervisor && !String(item.supervisor || "").toLowerCase().includes(supervisor)) return false;
        if (agente && !String(item.agente || "").toLowerCase().includes(agente)) return false;
        if (busqueda && !textoBusquedaEvaluacionIa(item).includes(busqueda)) return false;
        if (riesgo && nivelRiesgoDetalleIa(item).toLowerCase() !== riesgo) return false;
        if (resultado && resultadoIaDetalle(item).toLowerCase() !== resultado) return false;
        if (tipoLlamada && !String(item.tipo_llamada || "").toLowerCase().includes(tipoLlamada)) return false;
        if (revision === "revision_humana") {
            if (!item.requiere_revision_humana) return false;
        } else if (revision && String(item.estado_revision || "PENDIENTE").toLowerCase() !== revision) return false;
        if (errorCritico === "si" && !tieneErrorCriticoEvaluacionIa(item)) return false;
        if (errorCritico === "no" && tieneErrorCriticoEvaluacionIa(item)) return false;
        if (coaching && String(item.estado_coaching || "PENDIENTE").toLowerCase() !== coaching) return false;
        if (calibracion && String(item.estado_recalibracion || "SIN_APELACION").toLowerCase() !== calibracion) return false;
        return true;
    });
}

function construirReporteFiltradoIa(data, detalle) {
    const scores = detalle.map(x => Number(x.score_final ?? x.score_calidad ?? 0)).filter(x => !Number.isNaN(x));
    const carteras = agruparScoreDetalleIa(detalle, "cartera");
    const agentes = agruparScoreDetalleIa(detalle, "agente");
    const semanas = agruparScoreDetalleIa(detalle, "semana");
    const segmentos = {};
    const brechas = {};
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
        (row.brechas_items || []).forEach(item => {
            const sgc = itemSgcIa(item);
            const key = `${sgc.grupo_error_sgc || "No aplica"}::${sgc.factor_sgc || item.item || "Sin item"}`;
            const actual = brechas[key] || {
                segmento: item.segmento || "Sin segmento",
                item: item.item || "Sin item",
                grupo_error_sgc: sgc.grupo_error_sgc,
                factor_sgc: sgc.factor_sgc,
                peso: 0,
                nota: 0,
                total: 0,
                ceros: 0,
            };
            actual.peso += Number(item.peso || 0);
            actual.nota += Number(item.nota || 0);
            actual.total += 1;
            actual.ceros += 1;
            brechas[key] = actual;
        });
    });

    const segmentosLista = Object.values(segmentos).map(item => {
        item.porcentaje = item.peso ? (item.nota / item.peso) * 100 : 0;
        return item;
    }).sort((a, b) => a.porcentaje - b.porcentaje);

    const brechasLista = Object.values(brechas).map(item => ({
        ...item,
        porcentaje: item.peso ? (item.nota / item.peso) * 100 : 0,
    })).sort((a, b) => b.ceros - a.ceros || a.porcentaje - b.porcentaje);

    return {
        ...data,
        total_audios: detalle.length,
        score_promedio: scores.length ? scores.reduce((sum, value) => sum + value, 0) / scores.length : null,
        items_nota_cero: ceros || detalle.reduce((sum, row) => sum + Number(row.total_puntos_criticos || 0), 0),
        carteras,
        agentes,
        semanas,
        segmentos: segmentosLista,
        brechas: brechasLista.length ? brechasLista : (data.brechas || []),
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
        actual.scoreTotal += Number(item.score_final ?? item.score_calidad ?? 0);
        actual.criticos += Number(item.total_puntos_criticos || 0);
        const sem = actual.semanas[semana] || { total: 0, scoreTotal: 0 };
        sem.total += 1;
        sem.scoreTotal += Number(item.score_final ?? item.score_calidad ?? 0);
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
        actual.scoreTotal += Number(item.score_final ?? item.score_calidad ?? 0);
        actual.criticos += Number(item.total_puntos_criticos || 0);
        const sem = actual.semanas[semana] || { total: 0, scoreTotal: 0 };
        sem.total += 1;
        sem.scoreTotal += Number(item.score_final ?? item.score_calidad ?? 0);
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
        el.innerHTML = estadoVacioReporteIa(items);
        return;
    }
    const width = 420;
    const height = 180;
    const padX = 34;
    const padY = 22;
    const target = 85;
    const puntos = semanas.map((item, index) => {
        const score = Math.max(0, Math.min(100, porcentajeReporte(item)));
        const x = semanas.length === 1 ? width / 2 : padX + (index * (width - padX * 2)) / (semanas.length - 1);
        const y = padY + ((100 - score) * (height - padY * 2)) / 100;
        return { ...item, score, x, y };
    });
    const path = puntos.map(point => `${point.x.toFixed(1)},${point.y.toFixed(1)}`).join(" ");
    const targetY = padY + ((100 - target) * (height - padY * 2)) / 100;
    el.innerHTML = `
        <svg class="copc-line-chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="Tendencia semanal del score">
            <line x1="${padX}" y1="${targetY.toFixed(1)}" x2="${width - padX}" y2="${targetY.toFixed(1)}" class="target-line"></line>
            <polyline points="${path}" class="score-line"></polyline>
            ${puntos.map(point => `
                <circle cx="${point.x.toFixed(1)}" cy="${point.y.toFixed(1)}" r="4"></circle>
                <text x="${point.x.toFixed(1)}" y="${height - 7}" text-anchor="middle">${escapeHtml(String(point.semana || "-").replace(/^.*?S/, "S"))}</text>
            `).join("")}
            <text x="${width - padX}" y="${Math.max(12, targetY - 6).toFixed(1)}" text-anchor="end" class="target-label">Meta 85%</text>
        </svg>
        <div class="trend-legend">
            <span><i></i>Score validado</span>
            <span><i class="target"></i>Meta</span>
        </div>
    `;
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
        actual.score_total += Number(item.score_final ?? item.score_calidad ?? 0);
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
            <td><strong>${Number(item.score_final ?? item.score_calidad ?? 0).toFixed(1)}%</strong></td>
            <td>${escapeHtml(item.observacion_supervisor || "-")}</td>
            <td><button class="historial-action" type="button" onclick="verAnalisisIa(${Number(item.id_feedback || 0)})">Ver</button></td>
        </tr>
    `).join("");
}

function pintarBandejaEvaluacionesIa(items) {
    pintarKpisEvaluacionesIa(items);
    const tbody = document.getElementById("evaluacionesBodyIa");
    if (!tbody) return;
    const total = items.length;
    const totalPaginas = totalPaginasEvaluacionesIa(items);
    if (evaluacionesPaginaIa > totalPaginas) evaluacionesPaginaIa = totalPaginas;
    const inicio = total ? (evaluacionesPaginaIa - 1) * evaluacionesPageSizeIa : 0;
    const fin = Math.min(inicio + evaluacionesPageSizeIa, total);
    const pagina = items.slice(inicio, fin);
    setText("evaluacionesConteoIa", total ? `Mostrando ${formatoNumero(inicio + 1)} a ${formatoNumero(fin)} de ${formatoNumero(total)} evaluaciones` : "Mostrando 0 evaluaciones");
    setText("evaluacionesPaginaInfoIa", total ? `Mostrando ${formatoNumero(inicio + 1)}-${formatoNumero(fin)} de ${formatoNumero(total)}` : "Mostrando 0 evaluaciones");
    setText("evaluacionesPaginaIa", `Página ${formatoNumero(evaluacionesPaginaIa)} de ${formatoNumero(totalPaginas)}`);
    const prev = document.getElementById("evaluacionesPrevIa");
    const next = document.getElementById("evaluacionesNextIa");
    if (prev) prev.disabled = evaluacionesPaginaIa <= 1;
    if (next) next.disabled = evaluacionesPaginaIa >= totalPaginas;
    setValue("busquedaRapidaEvaluacionesIa", valor("filtroBusquedaEvaluacionIa"));
    if (!items.length) {
        tbody.innerHTML = `<tr><td colspan="9" class="empty-row">No hay evaluaciones para los filtros seleccionados.</td></tr>`;
        return;
    }
    tbody.innerHTML = pagina.map(item => {
        const agente = item.agente || "Sin agente asociado";
        const archivo = item.archivo_nombre || "";
        const revision = estadoRevisionEvaluacionIa(item);
        const validada = esEvaluacionValidadaIa(item);
        const accion = validada ? "Ver ficha" : "Revisar";
        const idFeedback = Number(item.id_feedback || 0);
        return `
            <tr class="${tieneErrorCriticoEvaluacionIa(item) ? "has-critical" : ""}">
                <td><strong>${escapeHtml(formatoFecha(item.fecha_llamada || item.fecha_creacion))}</strong><small>ID ${escapeHtml(item.id_feedback || "-")}</small></td>
                <td><strong title="${escapeHtml(agente)}">${escapeHtml(nombreAgenteCortoIa(agente))}</strong><small title="${escapeHtml(archivo || "Sin audio disponible")}">${archivo ? "Audio disponible" : "Sin audio disponible"}</small></td>
                <td>${escapeHtml(item.cartera || "Sin información")}</td>
                <td>${escapeHtml(tipoLlamadaVisibleIa(item))}</td>
                <td>${scoreBandejaEvaluacionIa(item)}</td>
                <td>${badgeEvaluacionIa(tieneErrorCriticoEvaluacionIa(item) ? "Sí" : "No", tieneErrorCriticoEvaluacionIa(item) ? "risk" : "ok")}</td>
                <td>${badgeEvaluacionIa(formatearRiesgoVisibleIa(item.nivel_oportunidad_mejora || item.nivel_riesgo), claseBadgeRiesgoIa(item.nivel_oportunidad_mejora || item.nivel_riesgo))}</td>
                <td>${badgeEvaluacionIa(revision.texto, revision.clase)}</td>
                <td><button class="historial-action" type="button" data-id-feedback="${idFeedback}" onclick="verAnalisisIa(${idFeedback})">${accion}</button></td>
            </tr>
        `;
    }).join("");
}

function pintarKpisEvaluacionesIa(items) {
    const el = document.getElementById("evaluacionesKpisIa");
    if (!el) return;
    const total = items.length;
    const pendientes = items.filter(item => !esEvaluacionValidadaIa(item)).length;
    const validadas = items.filter(esEvaluacionValidadaIa).length;
    const criticas = items.filter(tieneErrorCriticoEvaluacionIa).length;
    const revisionHumana = items.filter(item => item.requiere_revision_humana).length;
    const cards = [
        ["Total evaluaciones", total, "En el periodo seleccionado", "info"],
        ["Pendientes de revisión", pendientes, "Requieren atención", pendientes ? "warn" : "ok"],
        ["Evaluaciones validadas", validadas, "Revisión completada", "ok"],
        ["Evaluaciones con error crítico", criticas, "Requieren corrección", criticas ? "risk" : "ok"],
        ["Requieren revisión humana", revisionHumana, "En proceso manual", revisionHumana ? "warn" : "info"],
    ];
    el.innerHTML = cards.map(([title, value, meta, color]) => `
        <article class="evaluation-kpi ${color}">
            <span>${escapeHtml(title)}</span>
            <strong>${formatoNumero(value)}</strong>
            <small>${escapeHtml(meta)}</small>
        </article>
    `).join("");
}

function totalPaginasEvaluacionesIa(items = detalleReporteIa) {
    return Math.max(1, Math.ceil((items?.length || 0) / evaluacionesPageSizeIa));
}

function ordenarEvaluacionesPorFechaDescIa(items = []) {
    return [...items].sort((a, b) => {
        const fechaA = parseFechaIa(a.fecha_llamada || a.fecha_creacion);
        const fechaB = parseFechaIa(b.fecha_llamada || b.fecha_creacion);
        const timeA = fechaA ? fechaA.getTime() : 0;
        const timeB = fechaB ? fechaB.getTime() : 0;
        if (timeB !== timeA) return timeB - timeA;
        return Number(b.id_feedback || 0) - Number(a.id_feedback || 0);
    });
}

function tipoLlamadaVisibleIa(item = {}) {
    const tipo = String(item.tipo_llamada || "").trim();
    return textoHumanoIa(tipo) || "Por clasificar";
}

function textoHumanoIa(value) {
    const texto = String(value || "").trim();
    if (!texto) return "";
    return texto
        .replace(/_/g, " ")
        .replace(/\s+/g, " ")
        .toLowerCase()
        .replace(/(^|\s)(\S)/g, (_, sep, char) => `${sep}${char.toUpperCase()}`);
}

function scoreBandejaEvaluacionIa(item) {
    const scoreValidado = scoreValidadoResumenIa(item);
    const scoreIa = scoreIaPreliminarResumenIa(item);
    if (scoreValidado != null) return `<strong>Score final ${scoreValidado.toFixed(1)}%</strong>`;
    if (scoreIa != null) return `<strong>Score IA ${scoreIa.toFixed(1)}%</strong>`;
    return `<span class="muted-cell">Sin score</span>`;
}

function estadoRevisionEvaluacionIa(item) {
    if (item.requiere_revision_humana && !esEvaluacionValidadaIa(item)) return { texto: "Requiere revisión humana", clase: "info" };
    const estado = String(item.estado_revision || "PENDIENTE").toUpperCase();
    const mapa = {
        PENDIENTE: ["Pendiente", "warn"],
        EN_REVISION: ["En revisión", "info"],
        REVISADO: ["Revisado", "ok"],
        FEEDBACK_ENVIADO: ["Feedback enviado", "ok"],
        CERRADO: ["Cerrado", "ok"],
    };
    const [texto, clase] = mapa[estado] || [estado.replaceAll("_", " "), "info"];
    return { texto, clase };
}

function badgeEvaluacionIa(texto, clase = "info") {
    return `<span class="evaluation-badge ${escapeHtml(clase)}">${escapeHtml(texto || "Sin información")}</span>`;
}

function tieneErrorCriticoEvaluacionIa(item = {}) {
    return Boolean(item.error_critico || item.falta_anulante || Number(item.total_puntos_criticos || 0) > 0);
}

function textoBusquedaEvaluacionIa(item = {}) {
    return [
        item.id_feedback,
        item.archivo_nombre,
        item.agente,
        item.supervisor,
        item.cartera,
    ].map(value => String(value || "").toLowerCase()).join(" ");
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
    const key = value.toLowerCase()
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "")
        .trim();
    if (["cumplimiento", "presentacion", "presentacion y validacion", "cumplimiento y control de contacto"].includes(key)) return "Cumplimiento";
    if (["diagnostico", "sondeo", "diagnostico y escucha"].includes(key)) return "Diagnóstico";
    if (["negociacion", "gestion de solucion", "gestion de solucion y negociacion", "negociacion de cobranza"].includes(key)) return "Gestión de solución";
    if (["cierre", "cierre verificable", "cierre y compromiso"].includes(key)) return "Cierre verificable";
    if (["experiencia y riesgo", "filosofia biznescob", "filosofia", "experiencia", "experiencia del cliente", "experiencia conducta y riesgo critico"].includes(key)) return "Experiencia y ética";
    return value;
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
    periodoAutoAjustadoIa = false;
    actualizarAvisoPeriodoIa("");
    setRangoFiltroFechaIa("");
    setValue("filtroCarteraIa", "");
    setValue("filtroSupervisorIa", "");
    setValue("filtroAgenteIa", "");
    setValue("filtroBusquedaEvaluacionIa", "");
    setValue("busquedaRapidaEvaluacionesIa", "");
    setValue("filtroRiesgoIa", "");
    setValue("filtroResultadoIa", "");
    setValue("filtroTipoLlamadaIa", "");
    setValue("filtroRevisionIa", "");
    setValue("filtroErrorCriticoIa", "");
    setValue("filtroCoachingIa", "");
    setValue("filtroCalibracionIa", "");
    setValue("repAgenteCarteraIa", "");
    setValue("repAgenteBusquedaIa", "");
    setValue("repAgenteOrdenIa", "riesgo");
    if (reporteriaActualIa) renderReporteriaIa(reporteriaActualIa);
}

function resultadoIaDetalle(item) {
    const score = Number(item.score_final ?? item.score_calidad ?? 0);
    if (score >= 85) return "Excelente";
    if (score >= 70) return "Aceptable";
    if (score >= 50) return "Con observacion";
    return "Deficiente";
}

function nivelRiesgoDetalleIa(item) {
    const score = Number(item.score_final ?? item.score_calidad ?? 0);
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

function setRangoFiltroFechaIa(rango) {
    setValue("filtroFechaIa", rango || "");
    const { desde, hasta } = parseRangoFechasIa(rango || "");
    setValue("filtroFechaDesdeIa", desde ? formatoFechaInputIa(desde) : "");
    setValue("filtroFechaHastaIa", hasta ? formatoFechaInputIa(hasta) : "");
}

function actualizarRangoFechaDesdeCalendariosIa() {
    const desde = parseFechaInputIa(valor("filtroFechaDesdeIa"));
    const hasta = parseFechaInputIa(valor("filtroFechaHastaIa"));
    const textoDesde = desde ? formatoFechaCortaIa(desde) : "";
    const textoHasta = hasta ? formatoFechaCortaIa(hasta) : "";
    setValue("filtroFechaIa", textoDesde && textoHasta ? `${textoDesde} - ${textoHasta}` : textoDesde || textoHasta || "");
}

function parseFechaInputIa(value) {
    if (!value) return null;
    const [year, month, day] = String(value).split("-").map(Number);
    if (!year || !month || !day) return null;
    return new Date(year, month - 1, day);
}

function formatoFechaInputIa(fecha) {
    return `${fecha.getFullYear()}-${String(fecha.getMonth() + 1).padStart(2, "0")}-${String(fecha.getDate()).padStart(2, "0")}`;
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
                <td>${escapeHtml(itemCopcVisibleIa(item))}</td>
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
    return "Revisión supervisor";
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

async function guardarRevisionIa(options = {}) {
    const idFeedback = valor("feedbackIdActualIa");
    if (!idFeedback) {
        mostrarMensajeIa("Primero abre o genera un análisis para guardar la revisión.", "error");
        return;
    }

    const btn = document.getElementById("btnGuardarRevisionIa");
    const textoOriginal = btn?.textContent || "Guardar borrador";
    if (btn) {
        btn.disabled = true;
        btn.textContent = "Guardando...";
    }

    try {
        const formData = new FormData();
        formData.append("agente", valor("agenteRevisionIa"));
        formData.append("estado_revision", valor("estadoRevisionIa") || "REVISADO");
        formData.append("comentario_feedback", comentarioRevisionConTrazabilidadIa());
        formData.append("revisado_por", localStorage.getItem("agente") || localStorage.getItem("dni") || "SIN_USUARIO");

        const response = await fetchIa(`${IA_FEEDBACK_BASE}/${idFeedback}/revision`, {
            method: "POST",
            body: formData,
        }, 30000);
        const data = await leerJsonSeguro(response);
        if (!response.ok) throw new Error(data.detail || "No se pudo guardar la revisión.");

        if (options.permanecerEnFicha) {
            renderResultadoIa(data);
            mostrarMensajeIa("Borrador guardado correctamente.", "ok");
        } else {
            resultadoActualIa = null;
            document.getElementById("resultadoContenidoIa")?.classList.add("oculto");
            document.getElementById("resultadoVacioIa")?.classList.remove("oculto");
            activarVistaReporteriaIa();
            await cargarHistorialIa();
            await cargarReporteriaIa();
            mostrarMensajeIa("Revisión guardada correctamente.", "ok");
        }
    } catch (error) {
        mostrarMensajeIa(error.message || "Error guardando revisión.", "error");
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.textContent = textoOriginal;
        }
    }
}

function comentarioRevisionConTrazabilidadIa() {
    const decision = document.querySelector("input[name='decisionSupervisorIa']:checked")?.value || "sin decisión";
    const tipoSupervisor = valor("tipoLlamadaSupervisorIa");
    const comentario = valor("comentarioFeedbackIa");
    const partes = [];
    if (comentario) partes.push(comentario);
    partes.push(`Decisión supervisor: ${decision}`);
    if (tipoSupervisor) partes.push(`Tipo de llamada supervisor: ${tipoSupervisor}`);
    if (decision === "modificar") partes.push("Nota: edición pendiente de integración con el backend; no se recalcula ni persiste score final por ítem.");
    return partes.join("\n");
}

function abrirRecalibracionIa(criterioInicial = "") {
    if (!resultadoActualIa?.id_feedback) {
        mostrarMensajeIa("Primero abre o genera un análisis para solicitar recalibración.", "error");
        return;
    }
    setText("recalibracionIdIa", resultadoActualIa.id_feedback || "-");
    const scoreIa = scoreIaOriginalCalibracionIa(resultadoActualIa);
    const scoreTecnico = scoreTecnicoActualCalibracionIa(resultadoActualIa);
    setText("recalibracionScoreIaOriginalIa", scoreIa !== null ? `${formatoPeso(scoreIa)} / 100` : "-");
    setText("recalibracionScoreTecnicoIa", scoreTecnico !== null ? `${formatoPeso(scoreTecnico)} / 100` : "-");
    setText("recalibracionNivelIa", formatearRiesgoVisibleIa(resultadoActualIa.nivel_oportunidad_mejora));
    criteriosRecalibracionIa = criteriosTecnicosRecalibracionIa(resultadoActualIa);
    evidenciasRecalibracionIa = evidenciasParaRecalibracionIa(resultadoActualIa);
    criterioRecalibracionSeleccionadoIa = null;
    evidenciaRecalibracionSeleccionadaIa = null;
    poblarCriteriosRecalibracionIa(criterioInicial);
    poblarEvidenciasRecalibracionIa();
    setValue("resultadoPropuestoRecalibracionIa", "");
    setValue("motivoRecalibracionIa", "");
    setValue("comentarioEvidenciaRecalibracionIa", "");
    document.getElementById("selectorEvidenciaRecalibracionIaWrap")?.classList.add("oculto");
    actualizarCriterioRecalibracionIa();
    document.getElementById("modalRecalibracionIa")?.classList.remove("oculto");
}

function cerrarRecalibracionIa() {
    document.getElementById("modalRecalibracionIa")?.classList.add("oculto");
}

function cancelarRecalibracionIa() {
    const hayCambios = valor("criterioRecalibracionIa") || valor("resultadoPropuestoRecalibracionIa") || valor("motivoRecalibracionIa") || valor("comentarioEvidenciaRecalibracionIa");
    if (hayCambios && !confirm("Hay cambios sin enviar. ¿Deseas cerrar la solicitud?")) return;
    cerrarRecalibracionIa();
}

async function enviarRecalibracionIa() {
    const idFeedback = resultadoActualIa?.id_feedback || valor("feedbackIdActualIa");
    if (!idFeedback) {
        mostrarMensajeIa("Primero abre o genera un análisis para solicitar recalibración.", "error");
        return;
    }

    const criterio = criterioRecalibracionSeleccionadoIa;
    if (!criterio) {
        mostrarMensajeIa("Selecciona un criterio real de la matriz técnica.", "error");
        return;
    }

    const motivo = valor("motivoRecalibracionIa");
    if (!motivoValidoRecalibracionIa(motivo)) {
        mostrarMensajeIa("Ingresa un motivo específico y trazable para la discrepancia.", "error");
        return;
    }

    const evidenciaTexto = construirEvidenciaSupervisorRecalibracionIa();
    if (!evidenciaTexto && !motivo) {
        mostrarMensajeIa("Vincula una evidencia o agrega una justificación suficiente.", "error");
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
        formData.append("motivo", motivo);
        formData.append("evidencia_supervisor", evidenciaTexto);
        formData.append("solicitado_por", localStorage.getItem("agente") || localStorage.getItem("dni") || "SIN_USUARIO");

        const response = await fetchIa(`${IA_FEEDBACK_BASE}/${idFeedback}/recalibracion`, {
            method: "POST",
            body: formData,
        }, 30000);
        const data = await leerJsonSeguro(response);
        if (!response.ok) throw new Error(data.detail || "No se pudo solicitar la recalibración.");

        resultadoActualIa = data.feedback || resultadoActualIa;
        setText("estadoRecalibracionIa", "PENDIENTE");
        setText("trazaRevisionIa", resultadoActualIa.estado_revision || "PENDIENTE");
        cerrarRecalibracionIa();
        await cargarHistorialIa();
        if (resultadoActualIa?.id_feedback) pintarCalibracionDetalleIa(resultadoActualIa);
        mostrarMensajeIa("Solicitud de recalibración registrada con trazabilidad.", "ok");
    } catch (error) {
        mostrarMensajeIa(error.message || "Error solicitando recalibración.", "error");
    } finally {
        btn.disabled = false;
        btn.textContent = "Enviar solicitud";
    }
}

function criteriosTecnicosRecalibracionIa(data = {}) {
    const recalibracionesActivas = new Set((data.recalibraciones_lista || [])
        .filter(item => /pendiente|enviada|analisis|análisis/i.test(String(item.estado || "")))
        .map(item => normalizarTextoComparacionIa(item.item_cuestionado || "")));
    return evaluacionCalidadItemsIa(data)
        .map(itemSgcIa)
        .map(item => {
            const codigo = codigoCriterioHallazgoIa(item);
            const nombre = nombreEspecificoCriterioRecalibracionIa(item, codigo);
            const peso = Number(item.peso ?? item.puntaje_maximo ?? 0);
            if (!codigo || !nombre || nombre === "Criterio no identificado" || !Number.isFinite(peso) || peso <= 0) return null;
            const clave = normalizarTextoComparacionIa(`${codigo} ${nombre}`);
            const bloqueado = [...recalibracionesActivas].some(actual => actual.includes(normalizarTextoComparacionIa(codigo)) || actual.includes(normalizarTextoComparacionIa(nombre)));
            return {
                raw: item,
                codigo,
                nombre,
                dimension: item.segmento_copc || item.segmento || "-",
                grupo: item.grupo_error_sgc || clasificarSgcItemIa(item).grupo,
                peso,
                nota: Number(item.nota ?? item.puntaje_obtenido ?? 0),
                resultado: resultadoHallazgoFichaIa(item),
                hallazgo: item.hallazgo || item.motivo || "-",
                evidencia: evidenciaHallazgoFichaIa(item, data),
                bloqueado,
                clave,
            };
        })
        .filter(Boolean);
}

function nombreEspecificoCriterioRecalibracionIa(item = {}, codigo = "") {
    const codigoLimpio = String(codigo || codigoCriterioHallazgoIa(item) || "").trim();
    const textoItem = String(item.nombre || item.item || item.item_copc || item.nombre_criterio || item.criterio || "").trim();
    const sinCodigo = textoItem
        .replace(/^\s*(?:PENC|PECUF|PECN|PECC)[\s._-]*\d+\s*/i, "")
        .replace(/^\s*\d+\.\d+\s*/, "")
        .trim();
    const factor = String(item.factor_sgc || "").trim();
    const genericosPorCodigo = [
        factor,
        item.segmento,
        item.segmento_copc,
        "Razón de no pago y explicar motivo",
        "Cierre verificable",
        "Cierre verificable 3C/4C",
    ].map(normalizarTextoComparacionIa).filter(Boolean);
    const candidato = sinCodigo || textoItem;
    if (candidato && !genericosPorCodigo.includes(normalizarTextoComparacionIa(candidato))) return candidato;
    return CRITERIO_TECNICO_DISPLAY_IA[codigoLimpio] || candidato || criterioHallazgoIa(item);
}

function etiquetaOpcionCriterioRecalibracionIa(item = {}) {
    const dimension = dimensionCortaRecalibracionIa(item.dimension);
    const suffix = item.bloqueado ? " · solicitud activa" : "";
    return `${item.codigo} ${item.nombre} · ${dimension} · ${item.resultado}${suffix}`;
}

function dimensionCortaRecalibracionIa(value = "") {
    const texto = String(value || "").trim();
    const normal = normalizarTextoComparacionIa(texto);
    if (normal.includes("cumplimiento")) return "Cumplimiento";
    if (normal.includes("diagnost")) return "Diagnóstico";
    if (normal.includes("gestion")) return "Gestión de solución";
    if (normal.includes("cierre")) return "Cierre verificable";
    if (normal.includes("experiencia")) return "Experiencia y ética";
    return texto || "Dimensión no disponible";
}

function poblarCriteriosRecalibracionIa(criterioInicial = "") {
    const select = document.getElementById("criterioRecalibracionIa");
    if (!select) return;
    const inicial = normalizarTextoComparacionIa(criterioInicial);
    select.innerHTML = `<option value="">Seleccionar criterio de la matriz técnica</option>` + criteriosRecalibracionIa.map((item, index) => {
        const selected = inicial && (normalizarTextoComparacionIa(`${item.codigo} ${item.nombre}`).includes(inicial) || inicial.includes(normalizarTextoComparacionIa(item.codigo))) ? "selected" : "";
        const disabled = item.bloqueado ? "disabled" : "";
        return `<option value="${index}" ${selected} ${disabled}>${escapeHtml(etiquetaOpcionCriterioRecalibracionIa(item))}</option>`;
    }).join("");
}

function actualizarCriterioRecalibracionIa() {
    const index = valor("criterioRecalibracionIa");
    criterioRecalibracionSeleccionadoIa = index !== "" ? criteriosRecalibracionIa[Number(index)] || null : null;
    setValue("resultadoPropuestoRecalibracionIa", "");
    evidenciaRecalibracionSeleccionadaIa = evidenciaPorCriterioRecalibracionIa(criterioRecalibracionSeleccionadoIa);
    seleccionarEvidenciaRecalibracionIa(evidenciaRecalibracionSeleccionadaIa);
    pintarDetalleCriterioRecalibracionIa();
    actualizarPropuestaRecalibracionIa();
}

function pintarDetalleCriterioRecalibracionIa() {
    const el = document.getElementById("detalleCriterioRecalibracionIa");
    const item = criterioRecalibracionSeleccionadoIa;
    if (!el) return;
    if (!item) {
        el.innerHTML = `<div class="empty-segment">Selecciona un criterio técnico para ver resultado, evidencia e impacto estimado.</div>`;
        return;
    }
    el.innerHTML = `
        <div class="recalibration-detail-grid">
            ${detalleDatoRecalibracionIa("Código", item.codigo)}
            ${detalleDatoRecalibracionIa("Nombre específico", item.nombre)}
            ${detalleDatoRecalibracionIa("Dimensión técnica", item.dimension)}
            ${detalleDatoRecalibracionIa("Factor o grupo relacionado", grupoSgcSingularIa(item.grupo))}
            ${detalleDatoRecalibracionIa("Peso", formatoPeso(item.peso))}
            ${detalleDatoRecalibracionIa("Nota actual", `${formatoPeso(item.nota)}/${formatoPeso(item.peso)}`)}
            ${detalleDatoRecalibracionIa("Resultado actual", item.resultado)}
            ${detalleDatoRecalibracionIa("Hallazgo técnico", item.hallazgo, true)}
            ${detalleDatoRecalibracionIa("Evidencia disponible", item.evidencia, true)}
        </div>
        <div class="recalibration-inline-actions">
            <button class="btn-light btn-small" type="button" onclick="irAEvidenciaRecalibracionIa()">Ver evidencia</button>
            <button class="btn-light btn-small" type="button" onclick="verCriterioRecalibracionEnMatrizIa()">Ver en matriz técnica</button>
        </div>
    `;
}

function detalleDatoRecalibracionIa(label, value, wide = false) {
    return `<article class="${wide ? "wide" : ""}"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value || "-")}</strong></article>`;
}

function actualizarPropuestaRecalibracionIa() {
    const item = criterioRecalibracionSeleccionadoIa;
    const resultado = valor("resultadoPropuestoRecalibracionIa");
    const propuesta = notaPropuestaRecalibracionIa(item, resultado);
    const notaActual = item ? Number(item.nota || 0) : null;
    const peso = item ? Number(item.peso || 0) : null;
    const impacto = propuesta !== null && notaActual !== null ? propuesta - notaActual : 0;
    setText("notaActualRecalibracionIa", item ? `${formatoPeso(notaActual)}/${formatoPeso(peso)}` : "-");
    setText("notaPropuestaRecalibracionIa", item ? `${formatoPeso(propuesta)}/${formatoPeso(peso)}` : "-");
    setText("impactoRecalibracionIa", `${impacto >= 0 ? "+" : ""}${formatoPeso(impacto)} ${Math.abs(impacto) === 1 ? "punto" : "puntos"}`);
    setValue("itemRecalibracionIa", item ? `${item.codigo} ${item.nombre}` : "");
    setValue("scoreSugeridoIa", resultado && propuesta !== null ? formatoPeso(propuesta) : "");
    setValue("nivelSugeridoIa", resultado || "SIN_CAMBIO");
    pintarResumenSolicitudRecalibracionIa();
}

function notaPropuestaRecalibracionIa(item, resultado = "") {
    if (!item) return null;
    const peso = Number(item.peso || 0);
    const actual = Number(item.nota || 0);
    if (!resultado) return actual;
    if (resultado === "CUMPLE") return peso;
    if (resultado === "NO_CUMPLE") return 0;
    if (resultado === "NO_APLICA") return actual;
    if (resultado === "REVISION_HUMANA") return actual;
    if (resultado === "PARCIAL") {
        if (actual > 0 && actual < peso) return actual;
        return peso >= 2 ? peso / 2 : Math.min(peso, 0.5);
    }
    return actual;
}

function evidenciasParaRecalibracionIa(data = {}) {
    const base = evidenciasAgrupadasIa.length ? evidenciasAgrupadasIa : agruparEvidenciasVisualesIa(normalizarEvidenciasDetalleIa(data).evidencias);
    return base.filter(item => item.frase && item.criterio);
}

function poblarEvidenciasRecalibracionIa() {
    const select = document.getElementById("selectorEvidenciaRecalibracionIa");
    if (!select) return;
    select.innerHTML = `<option value="">Seleccionar evidencia existente</option>` + evidenciasRecalibracionIa.map((item, index) => {
        const texto = `${item.hablante || "NO DETERMINADO"} · ${item.criterio || "-"} · ${String(item.frase || "").slice(0, 90)}`;
        return `<option value="${index}">${escapeHtml(texto)}</option>`;
    }).join("");
}

function evidenciaPorCriterioRecalibracionIa(criterio = null) {
    if (!criterio) return null;
    const codigo = normalizarTextoComparacionIa(criterio.codigo);
    const nombre = normalizarTextoComparacionIa(criterio.nombre);
    return evidenciasRecalibracionIa.find(item => {
        const rels = Array.isArray(item.criterios_relacionados) ? item.criterios_relacionados : [item];
        return rels.some(rel => normalizarTextoComparacionIa(rel.codigo_criterio || "").includes(codigo) || normalizarTextoComparacionIa(rel.criterio || "").includes(nombre));
    }) || null;
}

function seleccionarEvidenciaRecalibracionIa(item = null) {
    evidenciaRecalibracionSeleccionadaIa = item;
    const select = document.getElementById("selectorEvidenciaRecalibracionIa");
    if (select && item) {
        const index = evidenciasRecalibracionIa.indexOf(item);
        if (index >= 0) select.value = String(index);
    }
    pintarEvidenciaVinculadaRecalibracionIa();
}

function actualizarEvidenciaRecalibracionIa() {
    const index = valor("selectorEvidenciaRecalibracionIa");
    seleccionarEvidenciaRecalibracionIa(index !== "" ? evidenciasRecalibracionIa[Number(index)] || null : null);
}

function alternarSelectorEvidenciaRecalibracionIa() {
    document.getElementById("selectorEvidenciaRecalibracionIaWrap")?.classList.toggle("oculto");
}

function pintarEvidenciaVinculadaRecalibracionIa() {
    const el = document.getElementById("evidenciaVinculadaRecalibracionIa");
    if (!el) return;
    const item = evidenciaRecalibracionSeleccionadaIa;
    if (!item) {
        el.innerHTML = `<span>Sin evidencia vinculada</span><p>El supervisor puede enviar la solicitud si explica el contexto de revisión.</p>`;
        pintarResumenSolicitudRecalibracionIa();
        return;
    }
    const timestamp = timestampValidoIa(item.tiempo) ? item.tiempo : "Audio no sincronizado";
    el.innerHTML = `
        <span>${escapeHtml(item.hablante || "NO DETERMINADO")} · ${escapeHtml(timestamp)} · ${escapeHtml(textoTipoEvidenciaIa(item.tipo || ""))}</span>
        <p>${escapeHtml(item.frase || "-")}</p>
        <small>Confianza: ${escapeHtml(item.confianza || "No disponible")}</small>
    `;
    pintarResumenSolicitudRecalibracionIa();
}

function construirEvidenciaSupervisorRecalibracionIa() {
    const item = evidenciaRecalibracionSeleccionadaIa;
    const comentario = valor("comentarioEvidenciaRecalibracionIa");
    const partes = [];
    if (item?.frase) {
        partes.push(`Hablante: ${item.hablante || "NO DETERMINADO"}`);
        partes.push(`Tiempo: ${timestampValidoIa(item.tiempo) ? item.tiempo : "Audio no sincronizado"}`);
        partes.push(`Frase: "${item.frase}"`);
        if (item.tipo) partes.push(`Tipo de sustento: ${textoTipoEvidenciaIa(item.tipo)}`);
        if (item.confianza) partes.push(`Confianza: ${item.confianza}`);
    }
    if (comentario) partes.push(`Comentario supervisor: ${comentario}`);
    const texto = partes.join("\n");
    setValue("evidenciaRecalibracionIa", texto);
    return texto;
}

function pintarResumenSolicitudRecalibracionIa() {
    const el = document.getElementById("resumenSolicitudRecalibracionIa");
    const item = criterioRecalibracionSeleccionadoIa;
    if (!el) return;
    if (!item) {
        el.innerHTML = `<p>Selecciona un criterio para generar el resumen de solicitud.</p>`;
        return;
    }
    const resultado = valor("resultadoPropuestoRecalibracionIa") || "SIN_CAMBIO";
    const propuesta = notaPropuestaRecalibracionIa(item, resultado);
    const impacto = propuesta - Number(item.nota || 0);
    const evidencia = evidenciaRecalibracionSeleccionadaIa?.frase || "Sin evidencia vinculada";
    el.innerHTML = `
        <div><span>Criterio</span><strong>${escapeHtml(`${item.codigo} ${item.nombre}`)}</strong></div>
        <div><span>Actual</span><strong>${escapeHtml(item.resultado)} · ${escapeHtml(formatoPeso(item.nota))}/${escapeHtml(formatoPeso(item.peso))}</strong></div>
        <div><span>Propuesto</span><strong>${escapeHtml(labelResultadoPropuestoRecalibracionIa(resultado))} · ${escapeHtml(formatoPeso(propuesta))}/${escapeHtml(formatoPeso(item.peso))}</strong></div>
        <div><span>Impacto</span><strong>${impacto >= 0 ? "+" : ""}${escapeHtml(formatoPeso(impacto))} pts</strong></div>
        <div class="wide"><span>Evidencia vinculada</span><strong>${escapeHtml(evidencia)}</strong></div>
    `;
}

function labelResultadoPropuestoRecalibracionIa(value = "") {
    const map = {
        SIN_CAMBIO: "Sin cambio sugerido",
        CUMPLE: "Cumple",
        PARCIAL: "Parcial",
        NO_CUMPLE: "No cumple",
        NO_APLICA: "No aplica",
        REVISION_HUMANA: "Revisión humana",
    };
    return map[value || "SIN_CAMBIO"] || value;
}

function motivoValidoRecalibracionIa(texto = "") {
    const limpio = normalizarTextoComparacionIa(texto);
    if (limpio.length < 25) return false;
    return !["no estoy de acuerdo", "revisar", "cambiar nota", "error ia"].includes(limpio);
}

function irAEvidenciaRecalibracionIa() {
    if (!evidenciaRecalibracionSeleccionadaIa) {
        mostrarMensajeIa("Este criterio no tiene evidencia vinculada automáticamente.", "error");
        return;
    }
    mostrarTabDetalleIa("evidencias");
    evidenciaExpandidaIa = claveAgrupacionEvidenciaIa(evidenciaRecalibracionSeleccionadaIa);
    if (typeof pintarTablaEvidenciasIa === "function") pintarTablaEvidenciasIa(evidenciasAgrupadasIa || [], filtroEvidenciasActualIa);
}

function verCriterioRecalibracionEnMatrizIa() {
    if (!criterioRecalibracionSeleccionadoIa) return;
    verCriterioEvidenciaIa(encodeURIComponent(criterioRecalibracionSeleccionadoIa.codigo));
}

function cargarRevisionEnFormulario(data) {
    setValue("feedbackIdActualIa", data.id_feedback || "");
    setValue("agenteRevisionIa", data.agente || "");
    setValue("estadoRevisionIa", data.estado_revision || "REVISADO");
    setValue("comentarioFeedbackIa", data.comentario_feedback || data.recomendaciones || "");
    setValue("agenteRevisionLegacyIa", data.agente || "");
    setValue("estadoRevisionLegacyIa", data.estado_revision || "REVISADO");
    setValue("comentarioFeedbackLegacyIa", data.comentario_feedback || data.recomendaciones || "");
    setText("contadorComentarioIa", `${valor("comentarioFeedbackIa").length} / 1000`);
}

function sincronizarRevisionLegacyIa() {
    if (valor("agenteRevisionLegacyIa")) setValue("agenteRevisionIa", valor("agenteRevisionLegacyIa"));
    if (valor("estadoRevisionLegacyIa")) setValue("estadoRevisionIa", valor("estadoRevisionLegacyIa"));
    if (valor("comentarioFeedbackLegacyIa")) setValue("comentarioFeedbackIa", valor("comentarioFeedbackLegacyIa"));
}

function pintarLista(id, items) {
    const el = document.getElementById(id);
    if (!el) return;
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
    const contenedor = document.getElementById("evaluacionCalidadIa");
    if (!contenedor) return;

    if (!items.length) {
        contenedor.innerHTML = `<div class="empty-segment">Sin evaluación de calidad registrada.</div>`;
        return;
    }

    const grupos = new Map();
    items.map(itemSgcIa).forEach(item => {
        const segmento = formatearSegmentoIa(item.segmento || "Sin segmento");
        const key = segmento;
        const actual = grupos.get(key) || { segmento, peso: 0, nota: 0, brechas: 0, items: [] };
        actual.peso += Number(item.peso || 0);
        actual.nota += Number(item.nota || 0);
        if (claseFilaEvaluacion(item)) actual.brechas += 1;
        actual.items.push(item);
        grupos.set(key, actual);
    });

    const filas = [...grupos.values()].map(grupo => {
        const porcentaje = grupo.peso ? Math.round((grupo.nota / grupo.peso) * 100) : 0;
        const estado = porcentaje >= 85 ? "Cumple" : porcentaje >= 60 ? "Parcial" : "Crítico";
        return grupo.items.map((item, index) => `
            <tr class="${claseFilaEvaluacion(item)}">
                ${index === 0 ? `
                    <td class="matrix-segment-cell ${porcentaje < 60 ? "is-critical" : porcentaje < 85 ? "is-partial" : "is-ok"}" rowspan="${grupo.items.length}">
                        <strong>${escapeHtml(grupo.segmento)}</strong>
                        <small>${formatoPeso(grupo.nota)} / ${formatoPeso(grupo.peso)} · ${escapeHtml(estado)} · ${formatoNumero(grupo.brechas)} brecha(s)</small>
                    </td>
                ` : ""}
                <td class="matrix-item-cell">
                    <strong>${escapeHtml(item.item || "-")}</strong>
                    <small>${escapeHtml(etiquetaGrupoSgcRelacionadoIa(item.grupo_error_sgc))}</small>
                </td>
                <td class="matrix-score-cell">${formatoPeso(item.peso)}</td>
                <td class="matrix-score-cell"><strong class="${Number(item.nota || 0) === 0 ? "critical-score" : ""}">${formatoPeso(item.nota)}</strong></td>
                <td>${badgeResultadoCalidadIa(item.resultado)}</td>
                <td><b>Evidencia</b><p>${escapeHtml(item.evidencia || "-")}</p></td>
                <td data-criterio="${escapeHtml(codigoCriterioHallazgoIa(item))}"><b>Motivo técnico</b><p>${escapeHtml(item.motivo || item.hallazgo || item.recomendacion || "-")}</p></td>
            </tr>
        `).join("");
    }).join("");

    contenedor.innerHTML = `
        <table class="quality-grouped-table">
            <thead>
                <tr>
                    <th>Dimensión técnica</th>
                    <th>Criterio de evaluación</th>
                    <th>Peso</th>
                    <th>Nota</th>
                    <th>Resultado</th>
                    <th>Evidencia</th>
                    <th>Motivo técnico</th>
                </tr>
            </thead>
            <tbody>${filas}</tbody>
        </table>
    `;
}

function etiquetaGrupoSgcRelacionadoIa(grupo = "") {
    const texto = String(grupo || "").trim();
    const normalizado = normalizarTextoComparacionIa(texto);
    if (normalizado.includes("negocio")) return "Grupo SGC relacionado: Error crítico del negocio";
    if (normalizado.includes("usuario final")) return "Grupo SGC relacionado: Error crítico del usuario final";
    if (normalizado.includes("cumplimiento")) return "Grupo SGC relacionado: Error crítico de cumplimiento";
    if (normalizado.includes("no critico")) return "Grupo SGC relacionado: Error no crítico";
    return "Grupo SGC relacionado: No determinado";
}

function badgeResultadoCalidadIa(resultado) {
    const texto = String(resultado || "-");
    const key = texto.toLowerCase();
    let clase = "neutro";
    if (key.includes("cumple") && !key.includes("no cumple")) clase = "cumple";
    if (key.includes("parcial")) clase = "parcial";
    if (key.includes("revision") || key.includes("revisión")) clase = "parcial";
    if (key.includes("no cumple")) clase = "nocumple";
    if (key.includes("no evidenciado")) clase = "noevidenciado";
    if (key.includes("no aplica") || key.includes("no evaluable")) clase = "noaplica";
    return `<span class="quality-result-badge ${clase}">${escapeHtml(texto)}</span>`;
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
    if (resultado.includes("NO APLICA") || resultado.includes("NO EVALUABLE")) return "";
    if (resultado.includes("REVISION") || resultado.includes("REVISIÓN")) return "warning-row";
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
            actual.observaciones.push(`${itemCopcVisibleIa(item)}: ${item.resultado}`);
        }
        segmentos.set(key, actual);
    });

    contenedor.innerHTML = [...segmentos.values()].map(item => {
        const porcentaje = item.peso ? Math.round((item.nota / item.peso) * 100) : 0;
        const estado = porcentaje >= 85 ? "Cumple" : porcentaje >= 60 ? "Parcial" : "Critico";
        return `
            <article class="segment-card ${porcentaje < 60 ? "critical-segment" : porcentaje < 80 ? "warning-segment" : ""}">
                <div>
                    <span>${escapeHtml(formatearSegmentoIa(item.segmento))}</span>
                    <b class="segment-status">${estado}</b>
                    <strong>${formatoPeso(item.nota)} / ${formatoPeso(item.peso)}</strong>
                </div>
                <div class="segment-bar"><i style="width:${Math.max(0, Math.min(100, porcentaje))}%"></i></div>
                <small>${escapeHtml(item.observaciones.slice(0, 2).join(" | ") || "Sin observaciones criticas.")}</small>
            </article>
        `;
    }).join("");
}

function pintarResumenSgcDetalleIa(data = {}) {
    const el = document.getElementById("resumenSgcIa");
    if (!el) return;
    const items = evaluacionCalidadItemsIa(data).map(itemSgcIa);
    const resumen = data.resumen_sgc && typeof data.resumen_sgc === "object"
        ? {
            "Errores críticos del negocio": data.resumen_sgc.errores_criticos_negocio || 0,
            "Errores críticos del usuario final": data.resumen_sgc.errores_criticos_usuario_final || 0,
            "Errores críticos de cumplimiento": data.resumen_sgc.errores_criticos_cumplimiento || 0,
            "Errores no críticos": data.resumen_sgc.errores_no_criticos || 0,
        }
        : resumenSgcDesdeItemsIa(items);
    el.innerHTML = SGC_GRUPOS_IA.map(grupo => {
        const total = Number(resumen[grupo] || 0);
        return `
            <article class="${total ? "has-gap" : "clean"}">
                <span>${escapeHtml(grupo)}</span>
                <strong>${formatoNumero(total)}</strong>
                <small>${total ? "Requiere revisión operativa" : "Sin hallazgos"}</small>
            </article>
        `;
    }).join("");
}

function pintarTablaSgcDetalleIa(items) {
    const tbody = document.getElementById("tablaSgcIa");
    if (!tbody) return;
    const rows = items
        .map(itemSgcIa)
        .filter(item => {
            const cal = String(item.calificacion || "").toLowerCase();
            return !esValorNoAplicableIa(item.grupo_error_sgc) && !["cumple", "no aplica"].includes(cal);
        });
    if (!rows.length) {
        tbody.innerHTML = `<tr><td colspan="8" class="empty-row">Sin brechas SGC / PEC para mostrar en la vista ejecutiva.</td></tr>`;
        return;
    }
    tbody.innerHTML = rows.map(item => `
        <tr class="${item.requiere_coaching ? "critical-row" : item.requiere_feedback ? "warning-row" : ""}">
            <td><strong>${escapeHtml(item.factor_sgc || "-")}</strong></td>
            <td>${badgeSgcIa(item.grupo_error_sgc)}</td>
            <td>${badgeResultadoCalidadIa(item.calificacion)}</td>
            <td>${escapeHtml(item.motivo || item.hallazgo || "-")}</td>
            <td>${escapeHtml(item.evidencia || "-")}</td>
            <td>${escapeHtml(item.recomendacion || "-")}</td>
            <td>${badgeGerencialIa(item.requiere_feedback ? "Sí" : "No", item.requiere_feedback ? "medio" : "bajo")}</td>
            <td>${badgeGerencialIa(item.requiere_coaching ? "Sí" : "No", item.requiere_coaching ? "alto" : "bajo")}</td>
        </tr>
    `).join("");
}

function pintarCabeceraFichaSgcIa(data = {}) {
    const el = document.getElementById("cabeceraFichaSgcIa");
    if (!el) return;
    const score = data.score_final ?? data.score_normalizado ?? data.score_calidad;
    const esPauta = tienePautaAplicadaIa(data);
    const metricaPauta = esPauta
        ? `<article><span>Pauta aplicada</span><strong>${escapeHtml(data.pauta || "Pauta sin nombre")}${data.pauta_version ? ` v${escapeHtml(data.pauta_version)}` : ""}</strong></article>
           <article><span>Puntos aplicables</span><strong>${formatoPeso(data.peso_aplicable ?? 0)} / ${formatoPeso(data.peso_total ?? 100)}</strong></article>`
        : `<article><span>Riesgo</span><strong>${escapeHtml(formatearRiesgoVisibleIa(data.nivel_oportunidad_mejora || data.nivel_riesgo))}</strong></article>`;
    el.innerHTML = `
        <article><span>Evaluación</span><strong>${escapeHtml(data.id_feedback || "-")}</strong></article>
        <article><span>Cartera</span><strong>${escapeHtml(data.cartera || "-")}</strong></article>
        <article><span>Supervisor</span><strong>${escapeHtml(data.supervisor || "-")}</strong></article>
        <article><span>Fecha llamada</span><strong>${escapeHtml(formatoFecha(data.fecha_llamada || data.fecha_creacion))}</strong></article>
        <article><span>Score técnico</span><strong>${score != null ? `${Number(score).toFixed(1)} / 100` : "-"}</strong></article>
        ${metricaPauta}
        <p>${esPauta ? "Evaluación trazable construida directamente desde la pauta aplicada a la llamada." : "Documento gerencial SGC/PEC sustentado por la matriz técnica. Base metodológica inspirada en buenas prácticas COPC y adaptada a cobranza telefónica."}</p>
    `;
}

function pintarCierreFichaSgcIa(data = {}) {
    const items = hallazgosSgcItemsIa(data).length ? hallazgosSgcItemsIa(data) : evaluacionCalidadItemsIa(data);
    const prioridad = seleccionarFeedbackAlarmanteSgcIa(items, data);
    setText("fichaFeedbackSgcIa", prioridad || data.recomendaciones || data.recomendacion_feedback_supervisor || "Sin feedback crítico sugerido registrado.");
    setText("fichaObservacionSgcIa", data.comentario_feedback || data.comentario_supervisor || "Sin observación del supervisor registrada.");
}

function calificacionCortaSgcIa(value) {
    const key = String(value || "").toLowerCase();
    const normalizada = normalizarTextoComparacionIa(value);
    if (key.includes("revision") || key.includes("revisión") || normalizada.includes("requiere revisi")) return "RH";
    if (key.includes("no aplica")) return "NA";
    if (key.includes("no evaluable")) return "NE";
    if (key.includes("parcial")) return "P";
    if (key.includes("no cumple") || key.includes("no evidenciado")) return "NC";
    if (key.includes("cumple")) return "C";
    return "-";
}

function claseFilaFichaSgcIa(item) {
    const key = String(item.calificacion || "").toLowerCase();
    if (key.includes("no cumple") || key.includes("no evidenciado")) return "is-error";
    if (key.includes("parcial") || key.includes("revision") || key.includes("revisión")) return "is-partial";
    if (key.includes("cumple")) return "is-ok";
    return "is-na";
}

function itemsFichaAuditoriaSgcIa(items = []) {
    return items.map(item => {
        const base = itemSgcIa(item);
        const fallback = clasificarGrupoBaseSgcIa(base);
        const grupo = esValorNoAplicableIa(base.grupo_error_sgc) ? fallback.grupo : base.grupo_error_sgc;
        const factor = !esValorNoAplicableIa(base.factor_sgc) ? base.factor_sgc : fallback.factor;
        return {
            ...base,
            grupo_auditoria_sgc: grupo,
            factor_auditoria_sgc: factor,
            calificacion_corta: calificacionCortaSgcIa(base.calificacion),
        };
    });
}

function badgeFichaCalificacionSgcIa(corta, completa) {
    const key = String(corta || "").toUpperCase();
    const clase = key === "NC" ? "nocumple" : (key === "P" || key === "RH") ? "parcial" : key === "C" ? "cumple" : "noaplica";
    const textos = { C: "C - Cumple", NC: "NC - No cumple", P: "P - Parcial", RH: "Revisión humana", NA: "NA - No aplica", NE: "No evaluable" };
    return `<span class="audit-sgc-badge ${clase}" title="${escapeHtml(completa || "-")}">${escapeHtml(textos[key] || "-")}</span>`;
}

function prioridadFichaSgcIa(item = {}) {
    const cal = String(item.calificacion_corta || "").toUpperCase();
    if (cal === "NC") return 0;
    if (cal === "P") return 1;
    if (cal === "RH") return 2;
    if (cal === "NA") return 3;
    return 4;
}

function claveFactorConsolidadoSgcIa(item = {}) {
    const codigo = String(item.codigo_factor_sgc || item.factor_codigo_sgc || "").trim();
    if (codigo) return `codigo:${normalizarTextoComparacionIa(codigo)}`;
    return `factor:${normalizarTextoComparacionIa(item.factor_auditoria_sgc || item.factor_sgc || item.item || "")}`;
}

function textoUtilFichaSgcIa(texto = "") {
    return evidenciaEsTextualFichaIa(texto) && !textoEsGenericoHallazgoIa(texto);
}

function textoUnicoFichaSgcIa(lista = []) {
    const vistos = new Set();
    return lista
        .map(texto => String(texto || "").replace(/\s+/g, " ").trim())
        .filter(Boolean)
        .filter(texto => {
            const clave = normalizarTextoComparacionIa(texto);
            if (!clave || vistos.has(clave)) return false;
            vistos.add(clave);
            return true;
        });
}

function calificacionMasSeveraSgcIa(items = []) {
    const orden = { NC: 4, P: 3, RH: 2, C: 1, NA: 0, "-": -1 };
    return [...items].sort((a, b) => (orden[b.calificacion_corta] ?? -1) - (orden[a.calificacion_corta] ?? -1))[0] || items[0] || {};
}

function consolidarMotivoFactorSgcIa(factor = "", motivos = [], cantidad = 0) {
    const factorKey = normalizarTextoComparacionIa(factor);
    const motivosUnicos = textoUnicoFichaSgcIa(motivos).slice(0, 3);
    if (factorKey.includes("cierre verificable") && cantidad >= 4) {
        return motivosUnicos.join(" · ") || "Cierre verificable con componentes pendientes de validación.";
    }
    return motivosUnicos.slice(0, 2).join(" · ") || "Hallazgo consolidado para supervisión.";
}

function consolidarItemsFichaAuditoriaSgcIa(items = []) {
    const rows = itemsFichaAuditoriaSgcIa(items);
    const grupos = new Map();
    rows.forEach(item => {
        const key = claveFactorConsolidadoSgcIa(item);
        const actual = grupos.get(key) || [];
        actual.push(item);
        grupos.set(key, actual);
    });
    return [...grupos.values()].map(itemsGrupo => {
        const base = calificacionMasSeveraSgcIa(itemsGrupo);
        const evidencias = textoUnicoFichaSgcIa(itemsGrupo.map(item => item.evidencia).filter(textoUtilFichaSgcIa));
        const motivos = textoUnicoFichaSgcIa(itemsGrupo.map(item => item.motivo || item.hallazgo).filter(textoUtilFichaSgcIa));
        const recomendaciones = textoUnicoFichaSgcIa(itemsGrupo.map(item => item.recomendacion).filter(textoUtilFichaSgcIa));
        const criterios = textoUnicoFichaSgcIa(itemsGrupo.map(item => item.item || item.codigo_criterio || item.codigo));
        const factor = base.factor_auditoria_sgc || base.factor_sgc || "Factor SGC/PEC";
        return {
            ...base,
            factor_auditoria_sgc: factor,
            calificacion: base.calificacion,
            calificacion_corta: base.calificacion_corta,
            motivo: consolidarMotivoFactorSgcIa(factor, motivos, itemsGrupo.length),
            evidencia: evidencias.join(" · ") || "-",
            recomendacion: recomendaciones[0] || "-",
            criterios_relacionados: criterios.length || itemsGrupo.length,
            criterios_detalle: criterios,
        };
    });
}

function seleccionarFeedbackAlarmanteSgcIa(items = [], data = {}) {
    const rows = itemsFichaAuditoriaSgcIa(items);
    const prioridadGrupo = grupo => {
        const value = String(grupo || "").toLowerCase();
        if (value.includes("cumplimiento")) return 1;
        if (value.includes("negocio")) return 2;
        if (value.includes("usuario")) return 3;
        return 4;
    };
    const prioridadCal = item => {
        const cal = String(item.calificacion_corta || "").toUpperCase();
        if (cal === "NC") return 0;
        if (cal === "P") return 1;
        return 9;
    };
    const brecha = rows
        .filter(item => ["NC", "P"].includes(String(item.calificacion_corta || "").toUpperCase()))
        .sort((a, b) =>
            prioridadCal(a) - prioridadCal(b)
            || prioridadGrupo(a.grupo_auditoria_sgc) - prioridadGrupo(b.grupo_auditoria_sgc)
        )[0];
    if (data.falta_anulante && (data.frase_anulante || data.momento_falta_anulante)) {
        return `Prioridad máxima: revisar falta anulante${data.frase_anulante ? ` (${data.frase_anulante})` : ""}. Aplicar feedback formal y coaching inmediato.`;
    }
    if (!brecha) return "";
    const accion = brecha.requiere_coaching ? "Requiere coaching estructurado" : "Requiere feedback puntual";
    return `${accion}: ${brecha.factor_auditoria_sgc || "factor SGC/PEC"} - ${brecha.motivo || brecha.hallazgo || "hallazgo crítico sin detalle"}.`;
}

function codigoPautaItemIa(item = {}) {
    return String(item.codigo_criterio || item.codigo || item.item || "").trim().toUpperCase();
}

function bloquePautaItemIa(item = {}, data = {}) {
    const codigo = codigoPautaItemIa(item);
    const snapshot = Array.isArray(data.pauta_snapshot) ? data.pauta_snapshot : [];
    const definido = snapshot.find(criterio => codigoPautaItemIa(criterio) === codigo) || {};
    return String(item.bloque || definido.bloque || item.subcategoria || "Otros criterios").trim() || "Otros criterios";
}

function pintarFichaPautaIa(items, data = {}) {
    const el = document.getElementById("fichaAuditoriaSgcIa");
    if (!el) return;
    const grupos = new Map();
    items.map(itemSgcIa).forEach(item => {
        const bloque = bloquePautaItemIa(item, data);
        const lista = grupos.get(bloque) || [];
        lista.push(item);
        grupos.set(bloque, lista);
    });
    if (!grupos.size) {
        el.innerHTML = `<div class="empty-report-state"><strong>Sin criterios de pauta disponibles.</strong><small>La evaluación no contiene ítems suficientes para construir la ficha.</small></div>`;
        return;
    }
    el.innerHTML = [...grupos.entries()].map(([bloque, criterios]) => {
        const peso = criterios.reduce((total, item) => total + Number(item.peso ?? item.puntaje_maximo ?? 0), 0);
        const nota = criterios.reduce((total, item) => total + Number(item.nota ?? item.puntaje_obtenido ?? 0), 0);
        const brechas = criterios.filter(item => ["NC", "P", "RH"].includes(calificacionCortaSgcIa(item.calificacion))).length;
        return `
            <section class="audit-sgc-group pauta-criterios-group">
                <header class="audit-sgc-header"><span>${escapeHtml(bloque)}</span><small>${formatoPeso(nota)} / ${formatoPeso(peso)} pts · ${formatoNumero(brechas)} brecha(s)</small></header>
                <div class="audit-sgc-table-wrap">
                    <table class="audit-sgc-table pauta-criterios-table">
                        <thead><tr><th>Criterio</th><th>Peso</th><th>Nota</th><th>Resultado</th><th>Evidencia</th><th>Análisis y siguiente paso</th></tr></thead>
                        <tbody>${criterios.map(item => `
                            <tr class="${claseFilaFichaSgcIa({ ...item, calificacion: item.calificacion })}">
                                <td><strong>${escapeHtml(itemCopcVisibleIa(item))}</strong></td>
                                <td>${formatoPeso(item.peso ?? item.puntaje_maximo ?? 0)}</td>
                                <td><strong>${formatoPeso(item.nota ?? item.puntaje_obtenido ?? 0)}</strong></td>
                                <td>${badgeFichaCalificacionSgcIa(calificacionCortaSgcIa(item.calificacion), item.calificacion)}</td>
                                <td>${escapeHtml(item.evidencia || "-")}</td>
                                <td class="pauta-analisis-cell">
                                    <div class="pauta-analisis-motivo"><span>Motivo</span><strong>${escapeHtml(item.motivo || item.hallazgo || "-")}</strong></div>
                                    ${item.recomendacion ? `<div class="pauta-analisis-recomendacion"><span>Recomendación</span><p>${escapeHtml(item.recomendacion)}</p></div>` : ""}
                                </td>
                            </tr>
                        `).join("")}</tbody>
                    </table>
                </div>
            </section>
        `;
    }).join("");
}

function pintarFichaAuditoriaSgcIa(items, data = {}) {
    if (tienePautaAplicadaIa(data)) {
        pintarFichaPautaIa(items, data);
        return;
    }
    const el = document.getElementById("fichaAuditoriaSgcIa");
    if (!el) return;
    const rows = consolidarItemsFichaAuditoriaSgcIa(items);
    const esBrecha = item => ["NC", "P", "RH"].includes(String(item.calificacion_corta || "").toUpperCase());
    if (!rows.length) {
        el.innerHTML = `<div class="empty-report-state"><strong>Sin ficha SGC/PEC disponible.</strong><small>La evaluación no contiene ítems suficientes para construir la ficha de auditoría.</small></div>`;
        return;
    }
    el.innerHTML = SGC_GRUPOS_IA.map(grupo => {
        const grupoRows = rows.filter(item => item.grupo_auditoria_sgc === grupo);
        const brechas = grupoRows.filter(esBrecha);
        const visibles = grupoRows.sort((a, b) => prioridadFichaSgcIa(a) - prioridadFichaSgcIa(b));
        const estadoGrupo = brechas.length ? `${brechas.length} factor(es) observado(s)` : "Sin errores observados";
        return `
            <section class="audit-sgc-group">
                <header class="audit-sgc-header"><span>${escapeHtml(grupo.toUpperCase())}</span><small>${escapeHtml(estadoGrupo)}</small></header>
                <div class="audit-sgc-table-wrap">
                    <table class="audit-sgc-table">
                        <thead>
                            <tr>
                                <th>Factor</th>
                                <th>Calificación</th>
                                <th>Motivo</th>
                                <th>Evidencia</th>
                                <th>Recomendación</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${visibles.length ? visibles.map(item => `
                                <tr class="${claseFilaFichaSgcIa(item)}">
                                    <td><strong>${escapeHtml(item.factor_auditoria_sgc || "-")}</strong>${item.criterios_relacionados > 1 ? `<small>${formatoNumero(item.criterios_relacionados)} criterios relacionados</small>` : ""}</td>
                                    <td>${badgeFichaCalificacionSgcIa(item.calificacion_corta, item.calificacion)}</td>
                                    <td class="${["NC", "P", "RH"].includes(item.calificacion_corta) ? "audit-sgc-focus" : ""}">${escapeHtml(item.motivo || item.hallazgo || "-")}</td>
                                    <td>${escapeHtml(item.evidencia || "-")}</td>
                                    <td>${escapeHtml(item.recomendacion || "-")}</td>
                                </tr>
                            `).join("") : `<tr><td colspan="5" class="empty-row">Sin factores registrados para este grupo.</td></tr>`}
                        </tbody>
                    </table>
                </div>
            </section>
        `;
    }).join("");
}

function toggleDetalleCalidadIa() {
    mostrarTabDetalleIa("matriz");
}

function setDetalleSgcVisibleIa(visible) {
    const wrap = document.getElementById("detalleSgcWrapIa");
    const btn = document.getElementById("btnToggleDetalleSgcIa");
    if (wrap) wrap.classList.toggle("oculto", !visible);
    if (btn) btn.textContent = visible ? "Ocultar detalle SGC/PEC" : "Ver detalle SGC/PEC";
}

function toggleDetalleSgcIa() {
    const wrap = document.getElementById("detalleSgcWrapIa");
    if (!wrap) return;
    setDetalleSgcVisibleIa(wrap.classList.contains("oculto"));
}

function mostrarTabDetalleIa(tab = "resumen") {
    const contenedor = document.getElementById("resultadoContenidoIa");
    if (!contenedor) return;
    contenedor.dataset.activeTab = tab;
    contenedor.querySelectorAll(".detail-tabs button").forEach(btn => {
        btn.classList.toggle("active", btn.dataset.detailTab === tab);
    });

    const paneles = {
        revision: "detalleRevisionPanelIa",
        resumen: "detalleResumenPanelIa",
        matriz: "detalleMatrizPanelIa",
        ficha_sgc: "detalleFichaSgcPanelIa",
        evidencias: "evidenciasClaveSectionIa",
        coaching: "detalleCoachingPanelIa",
        calibracion: "calibracionDetalleIa",
        historial: "historialDetalleIa",
    };
    Object.entries(paneles).forEach(([key, id]) => {
        document.getElementById(id)?.classList.toggle("oculto", key !== tab);
    });
    if (tab === "matriz") setText("btnDetalleCalidadIa", "Ver matriz técnica");
}

function pintarEvidenciasDetalleIa(data = {}) {
    const tbody = document.getElementById("tablaEvidenciasIa");
    const filtros = document.getElementById("filtrosEvidenciasIa");
    const resumen = document.getElementById("resumenOperativoEvidenciasIa");
    if (!tbody || !filtros || !resumen) return;
    const { evidencias, descartadas } = normalizarEvidenciasDetalleIa(data);
    evidenciasDetalleIa = evidencias;
    evidenciasAgrupadasIa = agruparEvidenciasVisualesIa(evidencias);
    evidenciasDescartadasIa = descartadas;
    evidenciaExpandidaIa = null;
    filtroEvidenciasActualIa = "todas";
    mostrarTodasEvidenciasIa = false;
    criteriosEvidenciaExpandidaIa = null;

    const conteos = conteosEvidenciasIa(evidenciasAgrupadasIa);
    filtros.innerHTML = [
        ["todas", "Todas", conteos.todas],
        ["critica", "Críticas", conteos.critica],
        ["oportunidad", "Oportunidades", conteos.oportunidad],
        ["fortaleza", "Fortalezas", conteos.fortaleza],
        ["contexto", "Contexto del cliente", conteos.contexto],
    ].map(([key, label, total], index) => `
        <button class="${index === 0 ? "active" : ""}" type="button" data-evidence-filter="${key}" onclick="filtrarEvidenciasIa('${key}')">
            ${escapeHtml(label)} <span>${formatoNumero(total)}</span>
        </button>
    `).join("");

    pintarEstadoEvidenciasIa();
    pintarTablaEvidenciasIa(evidenciasAgrupadasIa);
}

function normalizarEvidenciasDetalleIa(data = {}) {
    const criterios = evaluacionCalidadItemsIa(data);
    const evidenciasClave = Array.isArray(data.evidencias_clave_lista) ? data.evidencias_clave_lista : [];
    const segmentos = segmentosTranscripcionV2Ia(data);
    const rows = [];
    let descartadas = 0;

    criterios.map(itemSgcIa).forEach(item => {
        const frase = fraseEvidenciaValidaIa(item.evidencia || item.frase_textual || item.cita_textual || item.cita);
        const criterio = criterioHallazgoIa(item);
        const lectura = lecturaEvidenciaIa(item, frase);
        if (!frase || !criterio || !lectura) {
            descartadas += 1;
            return;
        }
        const segmento = buscarSegmentoPorFraseIa(segmentos, frase);
        rows.push({
            codigo_criterio: codigoCriterioHallazgoIa(item),
            segmento_id: segmento?.id || segmento?.indice || segmento?.index || "",
            tiempo: tiempoEvidenciaIa(item, segmento),
            hablante: hablanteEvidenciaIa(item, segmento),
            frase,
            criterio,
            grupo_sgc: grupoSgcSingularIa(item.grupo_error_sgc || clasificarSgcItemIa(item).grupo),
            tipo: tipoEvidenciaIa(item, frase),
            confianza: confianzaEvidenciaIa(item, segmento, data),
            lectura,
            resultado: resultadoHallazgoFichaIa(item),
            hallazgo: item.hallazgo || "",
            recomendacion: item.recomendacion_entrenable || item.recomendacion || "",
            peso: Number(item.peso ?? item.puntaje_maximo ?? 0),
            falta_anulante: Boolean(item.falta_anulante || item.puede_descalificar),
        });
    });

    evidenciasClave.forEach(item => {
        const frase = fraseEvidenciaValidaIa(item.frase_textual || item.evidencia || item.cita_textual);
        const criterio = criterioHallazgoIa(item);
        const lectura = lecturaEvidenciaIa(item, frase);
        if (!frase || !criterio || !lectura) {
            descartadas += 1;
            return;
        }
        const segmento = buscarSegmentoPorFraseIa(segmentos, frase);
        rows.push({
            codigo_criterio: codigoCriterioHallazgoIa(item),
            segmento_id: segmento?.id || segmento?.indice || segmento?.index || "",
            tiempo: tiempoEvidenciaIa(item, segmento),
            hablante: hablanteEvidenciaIa(item, segmento),
            frase,
            criterio,
            grupo_sgc: grupoSgcSingularIa(item.grupo_error_sgc || clasificarSgcItemIa(item).grupo),
            tipo: tipoEvidenciaIa(item, frase),
            confianza: confianzaEvidenciaIa(item, segmento, data),
            lectura,
            resultado: resultadoHallazgoFichaIa(item),
            hallazgo: item.hallazgo || item.motivo || "",
            recomendacion: item.recomendacion_entrenable || item.recomendacion || "",
            peso: Number(item.peso ?? item.puntaje_maximo ?? 0),
            falta_anulante: Boolean(item.falta_anulante || item.puede_descalificar),
        });
    });

    agregarEvidenciasContextualesIa(rows, data, segmentos);

    const dedupe = new Map();
    rows.forEach(item => {
        const key = [item.codigo_criterio || normalizarTextoComparacionIa(item.criterio), normalizarTextoComparacionIa(item.frase), item.hablante].join("||");
        if (!item.frase || !item.criterio || !item.lectura || dedupe.has(key)) {
            descartadas += 1;
            return;
        }
        dedupe.set(key, item);
    });
    const evidencias = [...dedupe.values()].sort(ordenEvidenciasIa);
    return { evidencias, descartadas };
}

function agruparEvidenciasVisualesIa(items = []) {
    const grupos = new Map();
    items.forEach(item => {
        const key = claveAgrupacionEvidenciaIa(item);
        const actual = grupos.get(key) || {
            ...item,
            criterios_relacionados: [],
            relaciones_tecnicas: 0,
        };
        actual.criterios_relacionados.push({
            codigo_criterio: item.codigo_criterio || "",
            criterio: item.criterio || "Criterio no identificado",
            grupo_sgc: item.grupo_sgc || "No determinado",
            resultado: item.resultado || "",
            lectura: item.lectura || "",
            recomendacion: item.recomendacion || "",
            hallazgo: item.hallazgo || "",
            peso: Number(item.peso || 0),
        });
        actual.relaciones_tecnicas += 1;
        actual.falta_anulante = Boolean(actual.falta_anulante || item.falta_anulante);
        actual.tipo = tipoAgrupadoEvidenciaIa(actual, item);
        actual.grupo_sgc = grupoPrincipalEvidenciaIa(actual.criterios_relacionados);
        actual.criterio = criterioPrincipalEvidenciaIa(actual.criterios_relacionados, actual.criterio);
        actual.confianza = confianzaVisualEvidenciaIa(actual, item);
        actual.lectura = lecturaGeneralEvidenciaIa(actual);
        grupos.set(key, actual);
    });
    return [...grupos.values()]
        .map(item => ({
            ...item,
            criterios_relacionados: deduplicarCriteriosEvidenciaIa(item.criterios_relacionados),
        }))
        .sort(ordenEvidenciasAgrupadasIa);
}

function claveAgrupacionEvidenciaIa(item = {}) {
    const frase = normalizarTextoComparacionIa(item.frase);
    const hablante = normalizarTextoComparacionIa(item.hablante || "NO DETERMINADO");
    const segmento = String(item.segmento_id || "").trim();
    const tiempo = timestampValidoIa(item.tiempo) ? item.tiempo : "";
    return segmento ? `segmento:${segmento}` : [hablante, frase, tiempo].filter(Boolean).join("|");
}

function deduplicarCriteriosEvidenciaIa(items = []) {
    const map = new Map();
    items.forEach(item => {
        const key = item.codigo_criterio || normalizarTextoComparacionIa(item.criterio);
        if (!key) return;
        const existente = map.get(key);
        if (!existente || prioridadRelacionEvidenciaIa(item) < prioridadRelacionEvidenciaIa(existente)) {
            map.set(key, item);
        }
    });
    return [...map.values()].sort((a, b) => prioridadRelacionEvidenciaIa(a) - prioridadRelacionEvidenciaIa(b));
}

function tipoAgrupadoEvidenciaIa(grupo = {}, item = {}) {
    const actual = grupo.tipo || item.tipo || "oportunidad";
    const candidato = tipoVisualEvidenciaIa(item);
    if (candidato === "revision") return "revision";
    return prioridadTipoEvidenciaIa(candidato, item, grupo) < prioridadTipoEvidenciaIa(actual, item, grupo) ? candidato : actual;
}

function tipoVisualEvidenciaIa(item = {}) {
    if (item.falta_anulante) return "anulante";
    const hablante = hablanteTranscripcionIa(item.hablante || "");
    const resultado = normalizarTextoComparacionIa(item.resultado || "");
    const grupo = normalizarTextoComparacionIa(item.grupo_sgc || "");
    if (resultado.includes("revision") || resultado.includes("revisión") || item.tipo === "revision") return "revision";
    if (hablante === "CLIENTE" && item.tipo === "fortaleza") return "contexto";
    if (hablante === "CLIENTE" && item.tipo !== "critica" && item.tipo !== "revision") return "contexto";
    if (item.tipo === "fortaleza" && hablante !== "AGENTE") return "contexto";
    if (item.tipo === "fortaleza") return "fortaleza";
    if (grupo.includes("no critico") || item.tipo === "oportunidad") return "oportunidad";
    if (grupo.includes("critico") || resultado.includes("no cumple")) return "critica";
    return item.tipo || "oportunidad";
}

function prioridadTipoEvidenciaIa(tipo = "", item = {}, grupo = {}) {
    if (tipo === "anulante" || item.falta_anulante || grupo.falta_anulante) return 0;
    const sgc = normalizarTextoComparacionIa(item.grupo_sgc || grupo.grupo_sgc || "");
    if (tipo === "critica" && sgc.includes("usuario")) return 1;
    if (tipo === "critica" && sgc.includes("cumplimiento")) return 2;
    if (tipo === "critica" && sgc.includes("negocio")) return 3;
    if (tipo === "revision") return 4;
    if (tipo === "oportunidad") return 5;
    if (tipo === "fortaleza") return 6;
    if (tipo === "contexto") return 7;
    return 8;
}

function prioridadRelacionEvidenciaIa(item = {}) {
    return prioridadTipoEvidenciaIa(tipoVisualEvidenciaIa(item), item)
        - Math.min(10, Number(item.peso || 0)) / 100;
}

function grupoPrincipalEvidenciaIa(items = []) {
    const principal = [...items].sort((a, b) => prioridadRelacionEvidenciaIa(a) - prioridadRelacionEvidenciaIa(b))[0];
    return principal?.grupo_sgc || "No determinado";
}

function criterioPrincipalEvidenciaIa(items = [], fallback = "") {
    const principal = [...items].sort((a, b) => prioridadRelacionEvidenciaIa(a) - prioridadRelacionEvidenciaIa(b))[0];
    return principal?.criterio || fallback || "Criterio no identificado";
}

function confianzaVisualEvidenciaIa(grupo = {}, item = {}) {
    const explicita = String(item.confianza || grupo.confianza || "").trim().toUpperCase();
    if (["ALTA", "MEDIA", "BAJA"].includes(explicita) && grupo.relaciones_tecnicas <= 1) return explicita;
    if (tipoVisualEvidenciaIa(item) === "revision") return "MEDIA";
    if (!timestampValidoIa(grupo.tiempo) || grupo.relaciones_tecnicas > 1) return "MEDIA";
    if (hablanteTranscripcionIa(grupo.hablante || "") === "NO DETERMINADO") return "BAJA";
    if (String(grupo.frase || "").length < 24) return "MEDIA";
    return explicita && explicita !== "NO DISPONIBLE" ? explicita : "MEDIA";
}

function lecturaGeneralEvidenciaIa(item = {}) {
    const criterios = item.criterios_relacionados || [];
    return criterios.find(item => item.lectura)?.lectura || item.lectura || "";
}

function ordenEvidenciasAgrupadasIa(a, b) {
    return prioridadOperativaEvidenciaIa(a) - prioridadOperativaEvidenciaIa(b)
        || confianzaPesoEvidenciaIa(b.confianza) - confianzaPesoEvidenciaIa(a.confianza)
        || (hablanteTranscripcionIa(b.hablante) === "AGENTE" ? 1 : 0) - (hablanteTranscripcionIa(a.hablante) === "AGENTE" ? 1 : 0)
        || (timestampValidoIa(b.tiempo) ? 1 : 0) - (timestampValidoIa(a.tiempo) ? 1 : 0)
        || String(b.frase || "").length - String(a.frase || "").length
        || Math.max(...(b.criterios_relacionados || []).map(item => Number(item.peso || 0)), 0) - Math.max(...(a.criterios_relacionados || []).map(item => Number(item.peso || 0)), 0);
}

function prioridadOperativaEvidenciaIa(item = {}) {
    const grupo = normalizarTextoComparacionIa(item.grupo_sgc || "");
    const criterio = normalizarTextoComparacionIa(item.criterio || "");
    if (item.falta_anulante || item.tipo === "anulante") return 0;
    if (item.tipo === "critica" && grupo.includes("usuario")) return 10;
    if (item.tipo === "critica" && grupo.includes("cumplimiento")) return 20;
    if (item.tipo === "critica" && criterio.includes("manejo de objeciones")) return 30;
    if (item.tipo === "critica" && criterio.includes("cierre verificable")) return 31;
    if (item.tipo === "critica" && grupo.includes("negocio")) return 35;
    if (item.tipo === "revision") return 40;
    if (item.tipo === "oportunidad" && criterio.includes("presentacion")) return 50;
    if (item.tipo === "oportunidad") return 60;
    if (item.tipo === "fortaleza") return 70;
    if (item.tipo === "contexto") return 80;
    return 90;
}

function confianzaPesoEvidenciaIa(confianza = "") {
    const key = normalizarTextoComparacionIa(confianza);
    if (key.includes("alta")) return 3;
    if (key.includes("media")) return 2;
    if (key.includes("baja")) return 1;
    return 0;
}

function fraseEvidenciaValidaIa(texto = "") {
    const frase = String(texto || "").replace(/\s+/g, " ").trim();
    if (!frase || !evidenciaEsTextualFichaIa(frase) || textoEsGenericoHallazgoIa(frase)) return "";
    if (/^revisar transcripci[oó]n/i.test(frase)) return "";
    return frase.replace(/^["“”]+|["“”]+$/g, "");
}

function buscarSegmentoPorFraseIa(segmentos = [], frase = "") {
    const fraseKey = normalizarTextoComparacionIa(frase);
    if (!fraseKey) return null;
    const palabras = fraseKey.split(" ").filter(Boolean);
    const muestra = palabras.slice(0, Math.min(8, palabras.length)).join(" ");
    return segmentos.find(segmento => {
        const texto = normalizarTextoComparacionIa(segmento.texto || segmento.transcripcion || segmento.frase || "");
        return texto && (texto.includes(fraseKey) || (muestra && texto.includes(muestra)) || fraseKey.includes(texto.slice(0, 80)));
    }) || null;
}

function tiempoEvidenciaIa(item = {}, segmento = null) {
    const candidatos = [
        item.momento,
        item.timestamp,
        item.inicio,
        formatoTimestampDesdeSegundosIa(item.inicio_segundos),
        segmento?.momento,
        segmento?.timestamp,
        segmento?.inicio,
        formatoTimestampDesdeSegundosIa(segmento?.inicio_segundos),
    ];
    return candidatos.find(timestampValidoIa) || "";
}

function hablanteEvidenciaIa(item = {}, segmento = null) {
    const candidato = segmento?.hablante
        || segmento?.rol
        || segmento?.speaker_original
        || segmento?.speakerOriginal
        || item.hablante
        || item.rol
        || item.speaker_original
        || item.speakerOriginal
        || "NO_DETERMINADO";
    return hablanteTranscripcionIa(candidato || "");
}

function confianzaEvidenciaIa(item = {}, segmento = null, data = {}) {
    const valor = item.confianza || segmento?.confianza || data.confianza_evaluacion || data.calidad_transcripcion || "";
    const texto = String(valor || "").trim();
    if (!texto) return "No disponible";
    if (/^\d+(\.\d+)?$/.test(texto)) return `${Number(texto).toFixed(0)}%`;
    return texto.toUpperCase();
}

function tipoEvidenciaIa(item = {}, frase = "") {
    const resultado = resultadoHallazgoFichaIa(item).toLowerCase();
    const grupo = normalizarTextoComparacionIa(item.grupo_error_sgc || "");
    const factor = normalizarTextoComparacionIa(item.factor_sgc || criterioHallazgoIa(item));
    if (resultado.includes("revision") || resultado.includes("revisión")) return "revision";
    if (resultado.includes("cumple") && !resultado.includes("no cumple") && !resultado.includes("parcial")) return "fortaleza";
    if (grupo.includes("errores no criticos") || resultado.includes("parcial") || factor.includes("presentacion") || factor.includes("claridad")) return "oportunidad";
    if (grupo.includes("errores criticos") || resultado.includes("no cumple") || resultado.includes("no evidenciado")) return "critica";
    if (hablanteTranscripcionIa(item.hablante || "") === "CLIENTE") return "contexto";
    return "oportunidad";
}

function lecturaEvidenciaIa(item = {}, frase = "") {
    const factor = normalizarTextoComparacionIa(item.factor_sgc || criterioHallazgoIa(item));
    const lectura = item.lectura_ia || item.interpretacion || item.impacto_negocio || item.hallazgo || item.motivo;
    if (lectura && !textoEsGenericoHallazgoIa(lectura)) return String(lectura).replace(/\s+/g, " ").trim();
    if (factor.includes("manejo de objeciones")) return "La evidencia muestra una objeción o restricción que debe evaluarse según la respuesta del agente.";
    if (factor.includes("induccion")) return "La evidencia sustenta una oportunidad de inducir pago o abono.";
    if (factor.includes("cierre verificable")) {
        return "La evidencia se relaciona con uno o más componentes del cierre verificable.";
    }
    if (factor.includes("presentacion")) return "La evidencia se relaciona con la forma en que el agente presentó o adaptó la propuesta.";
    if (factor.includes("lenguaje claro")) return "La evidencia requiere validar claridad, presión profesional o discurso autorizado.";
    return "";
}

function agregarEvidenciasContextualesIa(rows = [], data = {}, segmentos = []) {
    return rows;
}

function fraseContextualTranscripcionIa(transcripcion = "", claves = []) {
    const frases = String(transcripcion || "")
        .split(/(?<=[.!?])\s+|\n+/)
        .map(texto => texto.replace(/\s+/g, " ").trim())
        .filter(Boolean);
    const match = frases.find(frase => {
        const key = normalizarTextoComparacionIa(frase);
        return claves.every(clave => key.includes(normalizarTextoComparacionIa(clave)));
    });
    return fraseEvidenciaValidaIa(match || "");
}

function grupoSgcSingularIa(grupo = "") {
    const normalizado = normalizarTextoComparacionIa(grupo);
    if (normalizado.includes("negocio")) return "Error crítico del negocio";
    if (normalizado.includes("usuario final")) return "Error crítico del usuario final";
    if (normalizado.includes("cumplimiento")) return "Error crítico de cumplimiento";
    if (normalizado.includes("no critico")) return "Error no crítico";
    return "No determinado";
}

function ordenEvidenciasIa(a, b) {
    const pesoTipo = { critica: 0, revision: 1, oportunidad: 2, fortaleza: 3, contexto: 4 };
    const ta = segundosDesdeMomentoIa(a.tiempo);
    const tb = segundosDesdeMomentoIa(b.tiempo);
    return (pesoTipo[a.tipo] ?? 9) - (pesoTipo[b.tipo] ?? 9)
        || (ta == null ? 99999 : ta) - (tb == null ? 99999 : tb);
}

function conteosEvidenciasIa(items = []) {
    return {
        todas: items.length,
        critica: items.filter(item => item.tipo === "critica" || item.tipo === "anulante").length,
        oportunidad: items.filter(item => item.tipo === "oportunidad").length,
        fortaleza: items.filter(item => item.tipo === "fortaleza").length,
        contexto: items.filter(item => item.tipo === "contexto").length,
        revision: items.filter(item => item.tipo === "revision").length,
    };
}

function pintarEstadoEvidenciasIa() {
    const resumen = document.getElementById("resumenOperativoEvidenciasIa");
    if (!resumen) return;
    const totalAgrupadas = evidenciasAgrupadasIa.length;
    const totalRelaciones = evidenciasDetalleIa.length;
    const texto = mostrarTodasEvidenciasIa
        ? `Mostrando ${formatoNumero(totalAgrupadas)} evidencias agrupadas · ${formatoNumero(evidenciasDescartadasIa)} registros descartados por falta de sustento`
        : `Principales ${formatoNumero(Math.min(5, totalAgrupadas))} de ${formatoNumero(totalAgrupadas)} evidencias · ${formatoNumero(totalRelaciones)} relaciones técnicas · ${formatoNumero(evidenciasDescartadasIa)} registros descartados por falta de sustento`;
    resumen.innerHTML = `
        <p>${escapeHtml(texto)}</p>
        <button type="button" class="btn-light btn-small" onclick="toggleModoEvidenciasIa()">${mostrarTodasEvidenciasIa ? "Ver principales" : "Ver todas las evidencias"}</button>
    `;
}

function pintarTablaEvidenciasIa(items = [], filtro = "todas") {
    const tbody = document.getElementById("tablaEvidenciasIa");
    if (!tbody) return;
    const filtradas = filtro === "todas" ? items : items.filter(item => filtro === "critica" ? ["critica", "anulante"].includes(item.tipo) : item.tipo === filtro);
    const visibles = mostrarTodasEvidenciasIa ? filtradas : filtradas.slice(0, 5);
    if (!visibles.length) {
        tbody.innerHTML = `<tr><td colspan="6" class="empty-row">No hay evidencias con sustento textual para este filtro.</td></tr>`;
        return;
    }
    tbody.innerHTML = visibles.map(item => {
        const key = evidenciaKeyIa(item);
        const expandida = evidenciaExpandidaIa === key;
        const tieneTiempo = timestampValidoIa(item.tiempo);
        const criteriosValidos = criteriosTecnicosValidosEvidenciaIa(item);
        return `
            <tr data-evidence-type="${escapeHtml(item.tipo)}" data-evidence-key="${escapeHtml(key)}">
                <td>${tieneTiempo
                    ? `<button class="evidence-time-pill" type="button" onclick="irAEvidenciaAudioIa('${encodeURIComponent(item.tiempo)}', true)">▶ ${escapeHtml(item.tiempo)}</button>`
                    : `<span class="evidence-no-time">Sin timestamp</span>`}</td>
                <td><span class="speaker-pill ${claseHablanteEvidenciaIa(item.hablante)}">${escapeHtml(item.hablante || "NO DETERMINADO")}</span></td>
                <td>
                    <div class="evidence-main-text">
                        <strong>${escapeHtml(item.frase)}</strong>
                        <small>${escapeHtml(item.criterio)} · ${escapeHtml(grupoSgcCortoEvidenciaIa(item.grupo_sgc))}</small>
                        ${criteriosValidos.length > 1 ? `<em>${formatoNumero(criteriosValidos.length)} criterios relacionados</em>` : ""}
                    </div>
                </td>
                <td><span class="evidence-kind ${claseTipoEvidenciaIa(item.tipo)}">${escapeHtml(textoTipoEvidenciaIa(item.tipo))}</span></td>
                <td><span class="confidence-pill">${escapeHtml(item.confianza || "No disponible")}</span></td>
                <td>
                    <div class="evidence-actions">
                        ${tieneTiempo
                            ? `<button type="button" onclick="irAEvidenciaAudioIa('${encodeURIComponent(item.tiempo)}', true)">Escuchar</button>`
                            : `<span class="evidence-unsynced">Audio no sincronizado</span>`}
                        <button type="button" onclick="toggleAnalisisEvidenciaIa('${encodeURIComponent(key)}')">${expandida ? "Ocultar" : "Ver análisis"}</button>
                        <button type="button" onclick="${criteriosValidos.length > 1 ? `toggleAnalisisEvidenciaIa('${encodeURIComponent(key)}')` : `verCriterioEvidenciaIa('${encodeURIComponent(criteriosValidos[0]?.codigo_criterio || item.codigo_criterio || item.criterio)}')`}">Ver criterio</button>
                    </div>
                </td>
            </tr>
            ${expandida ? filaAnalisisEvidenciaIa(item) : ""}
        `;
    }).join("");
}

function filtrarEvidenciasIa(filtro = "todas") {
    filtroEvidenciasActualIa = filtro;
    document.querySelectorAll("[data-evidence-filter]").forEach(btn => {
        btn.classList.toggle("active", btn.dataset.evidenceFilter === filtro);
    });
    pintarEstadoEvidenciasIa();
    pintarTablaEvidenciasIa(evidenciasAgrupadasIa || [], filtro);
}

function toggleModoEvidenciasIa() {
    mostrarTodasEvidenciasIa = !mostrarTodasEvidenciasIa;
    pintarEstadoEvidenciasIa();
    pintarTablaEvidenciasIa(evidenciasAgrupadasIa || [], filtroEvidenciasActualIa);
}

function evidenciaKeyIa(item = {}) {
    return normalizarTextoComparacionIa([
        item.codigo_criterio,
        item.criterio,
        item.hablante,
        item.frase,
        item.tipo,
    ].filter(Boolean).join("|"));
}

function toggleAnalisisEvidenciaIa(encoded = "") {
    const key = decodeURIComponent(encoded || "");
    evidenciaExpandidaIa = evidenciaExpandidaIa === key ? null : key;
    if (evidenciaExpandidaIa !== key) criteriosEvidenciaExpandidaIa = null;
    pintarTablaEvidenciasIa(evidenciasAgrupadasIa || [], filtroEvidenciasActualIa);
}

function filaAnalisisEvidenciaIa(item = {}) {
    const recomendacionPrincipal = recomendacionPrincipalEvidenciaIa(item);
    const detalles = [
        ["Lectura general", item.lectura],
        ["Criterio principal", item.criterio],
        ["Grupo SGC principal", grupoSgcCortoEvidenciaIa(item.grupo_sgc)],
        ["Tipo de evidencia", textoTipoEvidenciaIa(item.tipo)],
        ["Confianza", item.confianza || "No disponible"],
        ["Hallazgo relacionado", item.hallazgo],
        ["Recomendación específica", recomendacionPrincipal],
    ].filter(([, value]) => value && String(value).trim());
    return `
        <tr class="evidence-analysis-row">
            <td colspan="6">
                <div class="evidence-analysis-panel">
                    ${detalles.map(([label, value]) => `
                        <article>
                            <span>${escapeHtml(label)}</span>
                            <p>${escapeHtml(value)}</p>
                        </article>
                    `).join("")}
                    ${renderCriteriosRelacionadosEvidenciaIa(item)}
                </div>
            </td>
        </tr>
    `;
}

function recomendacionPrincipalEvidenciaIa(item = {}) {
    const criterios = criteriosTecnicosValidosEvidenciaIa(item);
    const principal = criterios.find(criterio => normalizarTextoComparacionIa(criterio.criterio) === normalizarTextoComparacionIa(item.criterio))
        || criterios[0];
    const candidatos = [
        principal ? recomendacionCriterioRelacionadoIa(principal, item) : "",
        item.recomendacion,
        ...criterios.map(criterio => recomendacionCriterioRelacionadoIa(criterio, item)),
    ];
    return candidatos.find(recomendacionUtilEvidenciaIa) || "Requiere revisión del supervisor.";
}

function recomendacionUtilEvidenciaIa(texto = "") {
    const value = String(texto || "").trim();
    const key = normalizarTextoComparacionIa(value);
    if (!key) return false;
    return ![
        "revisar transcripcion",
        "solicitar recalibracion",
        "si el item fue cubierto",
        "no disponible",
        "no evidenciado",
        "sin informacion",
    ].some(fragmento => key.includes(fragmento));
}

function renderCriteriosRelacionadosEvidenciaIa(item = {}) {
    const criterios = criteriosTecnicosValidosEvidenciaIa(item);
    if (!criterios.length) return "";
    const key = evidenciaKeyIa(item);
    const expandida = criteriosEvidenciaExpandidaIa === key;
    const visibles = expandida || criterios.length <= 3 ? criterios : criterios.slice(0, 3);
    return `
        <article class="evidence-related-criteria">
            <div class="related-head">
                <span>Criterios relacionados</span>
                ${criterios.length > 3 ? `<button type="button" onclick="toggleCriteriosEvidenciaIa('${encodeURIComponent(key)}')">${expandida ? "Mostrar menos" : `Ver los ${formatoNumero(criterios.length)} criterios relacionados`}</button>` : ""}
            </div>
            <div class="related-table">
                <div class="related-row related-header">
                    <b>Código</b>
                    <b>Criterio</b>
                    <b>Resultado</b>
                    <b>Sustento</b>
                    <b>Lectura y recomendación</b>
                </div>
                ${visibles.map(criterio => {
                    const codigo = codigoCriterioDisplayIa(criterio.codigo_criterio);
                    return `
                        <div class="related-row">
                            <div><button type="button" onclick="verCriterioEvidenciaIa('${encodeURIComponent(criterio.codigo_criterio || criterio.criterio)}')">${escapeHtml(codigo)}</button></div>
                            <div><strong>${escapeHtml(nombreCriterioEspecificoIa(criterio))}</strong><small>${escapeHtml(grupoSgcCortoEvidenciaIa(criterio.grupo_sgc))}</small></div>
                            <div>${escapeHtml(resultadoCriterioRelacionadoIa(criterio))}</div>
                            <div><span class="support-pill">${escapeHtml(tipoSustentoCriterioEvidenciaIa(criterio, item))}</span></div>
                            <div><p>${escapeHtml(lecturaCriterioRelacionadoIa(criterio, item))}</p><p><b>Recomendación:</b> ${escapeHtml(recomendacionCriterioRelacionadoIa(criterio, item))}</p></div>
                        </div>
                    `;
                }).join("")}
            </div>
            <small>Confianza de asociación entre frase y criterio.</small>
        </article>
    `;
}

function toggleCriteriosEvidenciaIa(encoded = "") {
    const key = decodeURIComponent(encoded || "");
    criteriosEvidenciaExpandidaIa = criteriosEvidenciaExpandidaIa === key ? null : key;
    pintarTablaEvidenciasIa(evidenciasAgrupadasIa || [], filtroEvidenciasActualIa);
}

function criteriosTecnicosValidosEvidenciaIa(item = {}) {
    const criterios = (item.criterios_relacionados || [])
        .map(criterio => ({ ...criterio, codigo_display: codigoCriterioDisplayIa(criterio.codigo_criterio) }))
        .filter(criterio => criterioTecnicoValidoEvidenciaIa(criterio))
        .map(criterio => ({ ...criterio, criterio: nombreCriterioEspecificoIa(criterio) }));
    return ordenarCriteriosRelacionadosEvidenciaIa(criterios, item);
}

function ordenarCriteriosRelacionadosEvidenciaIa(criterios = [], item = {}) {
    return [...criterios].sort((a, b) => codigoCriterioDisplayIa(a.codigo_criterio).localeCompare(codigoCriterioDisplayIa(b.codigo_criterio), "es", { numeric: true }));
}

function criterioTecnicoValidoEvidenciaIa(criterio = {}) {
    const codigo = codigoCriterioDisplayIa(criterio.codigo_criterio);
    const nombre = normalizarTextoComparacionIa(criterio.criterio);
    if (!/^\d+\.\d+$/.test(codigo) && !/^(PENC|PECUF|PECN|PECC)\.\d+$/i.test(codigo)) return false;
    if (!nombre || ["error no critico", "error critico", "criterio no identificado", "s c"].includes(nombre)) return false;
    return true;
}

function codigoCriterioDisplayIa(codigo = "") {
    const texto = String(codigo || "").trim();
    const mibanco = texto.match(/^(PENC|PECUF|PECN|PECC)[\s._-]*(\d+)$/i);
    if (mibanco) return `${mibanco[1].toUpperCase()}.${mibanco[2]}`;
    const match = texto.match(/^(\d+)[\s._-]+(\d+)$/) || texto.match(/^(\d+)\.(\d+)$/);
    return match ? `${match[1]}.${match[2]}` : texto;
}

function nombreCriterioEspecificoIa(criterio = {}) {
    const codigo = codigoCriterioDisplayIa(criterio.codigo_criterio);
    const nombres = {
        "1.1": "Saludo e identificación del agente",
        "1.2": "Identificación de la entidad",
        "1.3": "Validación de titularidad",
        "1.4": "Motivo de llamada y control de información",
        "2.1": "Identificación de causa raíz / motivo de atraso",
        "2.2": "Diagnóstico de capacidad de pago",
        "2.3": "Fecha probable de ingreso",
        "2.4": "Monto disponible",
        "2.5": "Fuente del dinero o situación económica",
        "3.1": "Presentación clara de la propuesta",
        "3.2": "Claridad del beneficio",
        "3.3": "Exploración de capacidad durante la negociación",
        "3.4": "Negociación escalonada",
        "3.5": "Gestión de objeciones del cliente",
        "3.6": "Inducción a pago o abono",
        "4.1": "Cantidad",
        "4.2": "Fecha exacta",
        "4.3": "Canal de pago",
        "4.4": "Confirmación expresa",
        "4.5": "Resumen y siguiente acción",
        "5.1": "Respeto y ausencia de juicio",
        "5.2": "Empatía y escucha activa",
        "5.3": "Lenguaje claro y presión profesional",
        "5.4": "Despedida y cierre profesional",
    };
    return nombres[codigo] || criterio.criterio || "Criterio no identificado";
}

function resultadoCriterioRelacionadoIa(criterio = {}) {
    const resultado = String(criterio.resultado || "").trim();
    if (/no cumple/i.test(resultado)) return "No cumple";
    if (/revision|revisión/i.test(resultado)) return "Revisión humana";
    if (/parcial/i.test(resultado)) return "Parcial";
    if (/cumple/i.test(resultado)) return "Cumple";
    if (/contexto/i.test(resultado)) return "Contexto";
    return resultado || "Sin resultado";
}

function tipoSustentoCriterioEvidenciaIa(criterio = {}, item = {}) {
    const codigo = codigoCriterioDisplayIa(criterio.codigo_criterio);
    const tipo = item.tipo;
    if (tipo === "revision") return "Revisión humana";
    if (tipo === "contexto") return "Evidencia contextual";
    if (codigo.startsWith("4.") && resultadoCriterioRelacionadoIa(criterio) === "No cumple") return "Ausencia en la secuencia";
    if (["3.3", "3.5", "3.6"].includes(codigo)) return "Evidencia contextual";
    if (resultadoCriterioRelacionadoIa(criterio) === "Revisión humana") return "Revisión humana";
    return "Evidencia directa";
}

function lecturaCriterioRelacionadoIa(criterio = {}, item = {}) {
    return criterio.lectura || item.lectura || "La evidencia sustenta la evaluación del criterio.";
}

function recomendacionCriterioRelacionadoIa(criterio = {}, item = {}) {
    const codigo = codigoCriterioDisplayIa(criterio.codigo_criterio);
    const texto = normalizarTextoComparacionIa(`${criterio.recomendacion || ""} ${item.recomendacion || ""}`);
    const generica = texto.includes("revisar transcripcion") || texto.includes("solicitar recalibracion") || texto.includes("recalibracion si el item");
    if (codigo === "3.6") return "Inducir un abono o compromiso concreto antes de cerrar la llamada.";
    if (codigo === "4.1") return "Confirmar un monto exacto.";
    if (codigo === "4.2") return "Convertir la fecha tentativa en una fecha confirmada.";
    if (codigo === "4.3") return "Acordar el canal por el cual realizará el pago.";
    if (codigo === "4.4") return "Solicitar una confirmación clara del compromiso.";
    if (codigo === "4.5") return "Recapitular monto, fecha, canal y acuerdo antes de despedirse.";
    if (codigo === "5.3") return "Validar el discurso autorizado y explicar cualquier escalamiento sin amenaza ni ambigüedad.";
    if (codigo === "2.3") return "Convertir la fecha mencionada por el cliente en una alternativa verificable.";
    if (codigo === "2.2") return "Usar la información de liquidez para adaptar la propuesta a un monto y fecha viables.";
    if (!generica && criterio.recomendacion && evidenciaEsTextualFichaIa(criterio.recomendacion)) return criterio.recomendacion;
    return "Precisar la conducta esperada en el feedback y practicar una frase aplicable a la siguiente llamada.";
}

function grupoSgcCortoEvidenciaIa(grupo = "") {
    const key = normalizarTextoComparacionIa(grupo);
    if (key.includes("usuario")) return "Crítico del usuario final";
    if (key.includes("cumplimiento")) return "Crítico de cumplimiento";
    if (key.includes("negocio")) return "Crítico del negocio";
    if (key.includes("no critico") || key.includes("no criticos")) return "No crítico";
    return grupo || "Sin grupo SGC";
}

function claseTipoEvidenciaIa(tipo = "") {
    return ({ anulante: "critical", critica: "critical", oportunidad: "opportunity", fortaleza: "strength", contexto: "context", revision: "review" })[tipo] || "review";
}

function textoTipoEvidenciaIa(tipo = "") {
    return ({ anulante: "Falta anulante", critica: "Sustento crítico", oportunidad: "Oportunidad de mejora", fortaleza: "Fortaleza", contexto: "Contexto del cliente", revision: "Revisión humana" })[tipo] || "Revisión humana";
}

function claseHablanteEvidenciaIa(hablante = "") {
    const key = normalizarTextoComparacionIa(hablante);
    if (key.includes("agente")) return "agent";
    if (key.includes("cliente")) return "client";
    return "neutral";
}

function verCriterioEvidenciaIa(encoded = "") {
    const criterio = decodeURIComponent(encoded || "");
    mostrarTabDetalleIa("matriz");
    setTimeout(() => {
        const key = normalizarTextoComparacionIa(criterio);
        const target = [...document.querySelectorAll("#evaluacionCalidadIa [data-criterio]")]
            .find(el => normalizarTextoComparacionIa(el.dataset.criterio || "") === key || normalizarTextoComparacionIa(el.closest("tr")?.textContent || "").includes(key));
        const row = target?.closest("tr");
        if (!row) return;
        row.classList.add("matrix-row-focus");
        row.scrollIntoView({ behavior: "smooth", block: "center" });
        setTimeout(() => row.classList.remove("matrix-row-focus"), 2400);
    }, 120);
}

function pintarEvidenciaDestacadaIa(items, data = {}) {
    const el = document.getElementById("evidenciaDestacadaIa");
    if (!el) return;
    const item = items[0] || {};
    const tieneEvidencia = Boolean(item.frase_textual || item.interpretacion || item.momento);
    el.innerHTML = `
        <article class="highlight-evidence-card ${tieneEvidencia ? "" : "empty-highlight"}">
            <span>${escapeHtml(item.tipo || "Audio evaluado")}</span>
            <strong>${escapeHtml(tieneEvidencia ? (item.frase_textual || data.archivo_nombre || "Evidencia sin frase textual.") : "Sin evidencia clave registrada por la IA.")}</strong>
            <small>Momento: ${escapeHtml(item.momento || "No disponible")}</small>
            <p>${escapeHtml(tieneEvidencia ? (item.interpretacion || data.objecion_principal || "Sin interpretacion adicional.") : "Revisar matriz técnica o transcripcion para mayor detalle.")}</p>
        </article>
    `;
}

function pintarTopCriticosIa(items) {
    const el = document.getElementById("puntosCriticosTopIa");
    if (!el) return;
    const rows = [...items].slice(0, 3);
    if (!rows.length) {
        el.innerHTML = `<div class="empty-segment">Sin puntos criticos registrados.</div>`;
        return;
    }
    el.innerHTML = rows.map(item => `
        <article class="critical-summary-card ${claseFilaPuntoCriticoIa(item)}">
            <div>
                <span class="severity ${claseSeveridadIa(item.severidad)}">${escapeHtml(item.severidad || "MEDIA")}</span>
                <strong>${escapeHtml(formatearSegmentoIa(item.segmento || "-"))}</strong>
            </div>
            <p>${escapeHtml(item.hallazgo || "-")}</p>
            <small><b>Impacto:</b> ${escapeHtml(item.impacto || "-")}</small>
            <small><b>Recomendación:</b> ${escapeHtml(item.recomendacion || "-")}</small>
        </article>
    `).join("");
}

function pintarCalibracionDetalleIa(data) {
    const el = document.getElementById("calibracionResumenIa");
    if (!el) return;
    const recalibraciones = Array.isArray(data.recalibraciones_lista) ? data.recalibraciones_lista : [];
    const haySolicitud = haySolicitudCalibracionIa(data, recalibraciones);
    const exportBtn = document.getElementById("btnExportarTrazabilidadIa");
    if (exportBtn) {
        exportBtn.disabled = !haySolicitud;
        exportBtn.title = haySolicitud ? "Exportar trazabilidad disponible con la información registrada." : "Disponible cuando exista una solicitud de recalibración.";
    }
    el.innerHTML = haySolicitud
        ? renderCalibracionConSolicitudIa(data, recalibraciones)
        : renderCalibracionSinSolicitudIa(data);
}

function haySolicitudCalibracionIa(data = {}, recalibraciones = []) {
    if (Array.isArray(recalibraciones) && recalibraciones.length) return true;
    const estado = normalizarTextoComparacionIa(data.estado_recalibracion || "");
    return Boolean(estado && !["sin apelacion", "sin solicitud", "sin recalibracion", "no disponible", "pendiente integracion"].includes(estado));
}

function scoreIaOriginalCalibracionIa(data = {}) {
    return primerNumeroIa([
        data.score_calidad_ia,
        data.score_ia,
        data.resultado_evaluacion?.score_tecnico,
        data.score_tecnico,
    ]);
}

function scoreTecnicoActualCalibracionIa(data = {}) {
    return primerNumeroIa([
        data.score_final,
        data.score_final_validado,
        data.score_supervisor,
        calcularScoreTecnicoDesdeCriteriosIa(evaluacionCalidadItemsIa(data)),
        data.score_normalizado,
        data.score_calidad,
    ]);
}

function scorePropuestoSupervisorCalibracionIa(recalibraciones = []) {
    const valores = recalibraciones
        .map(item => primerNumeroIa([item.score_sugerido]))
        .filter(value => value !== null);
    if (!valores.length) return null;
    return valores[0];
}

function scoreFinalResueltoCalibracionIa(recalibraciones = []) {
    const resuelta = recalibraciones.find(item => {
        const estado = normalizarTextoComparacionIa(item.estado || "");
        return ["aprobada", "cerrada", "resuelta"].includes(estado) && primerNumeroIa([item.score_final]) !== null;
    });
    return resuelta ? primerNumeroIa([resuelta.score_final]) : null;
}

function estadoCalibracionDetalleIa(data = {}, recalibraciones = []) {
    const estadoItem = recalibraciones.find(item => item.estado)?.estado;
    const estado = String(estadoItem || data.estado_recalibracion || "SIN_SOLICITUD").toUpperCase();
    if (estado.includes("APROBADA") || estado.includes("CERRADA") || estado.includes("RESUELTA")) return "Resuelta";
    if (estado.includes("RECHAZADA")) return "Rechazada";
    if (estado.includes("CANCEL")) return "Cancelada";
    if (estado.includes("ANALISIS") || estado.includes("ANÁLISIS")) return "En análisis";
    if (estado.includes("PENDIENTE") || estado.includes("ENVIADA")) return "Enviada";
    if (estado.includes("BORRADOR")) return "Borrador";
    return "Sin solicitud";
}

function formatScoreCalibracionIa(value) {
    return value !== null && value !== undefined && Number.isFinite(Number(value))
        ? `${formatoPeso(Number(value))} / 100`
        : "Pendiente";
}

function renderCalibracionSinSolicitudIa(data = {}) {
    const scoreIa = scoreIaOriginalCalibracionIa(data);
    const scoreTecnico = scoreTecnicoActualCalibracionIa(data);
    const revision = data.estado_revision || "Pendiente";
    return `
        <section class="calibration-empty-layout">
            <div class="calibration-context-grid">
                ${cardCalibracionIa("Score IA original", scoreIa !== null ? formatScoreCalibracionIa(scoreIa) : "Sin información")}
                ${cardCalibracionIa("Score técnico actual", scoreTecnico !== null ? formatScoreCalibracionIa(scoreTecnico) : "Sin información")}
                ${cardCalibracionIa("Estado de revisión", revision)}
            </div>
            <article class="calibration-empty-state">
                <span>Sin solicitudes de recalibración</span>
                <h5>El supervisor no ha cuestionado criterios o puntajes de esta evaluación.</h5>
                <p>Cuando exista una discrepancia, la solicitud debe registrar criterio, evidencia y motivo antes de enviarse a Calidad.</p>
                <button class="btn-primary btn-small" type="button" onclick="abrirRecalibracionIa()">Solicitar recalibración</button>
            </article>
        </section>
    `;
}

function renderCalibracionConSolicitudIa(data = {}, recalibraciones = []) {
    const scoreIa = scoreIaOriginalCalibracionIa(data);
    const scoreTecnico = scoreTecnicoActualCalibracionIa(data);
    const scorePropuesto = scorePropuestoSupervisorCalibracionIa(recalibraciones);
    const scoreFinal = scoreFinalResueltoCalibracionIa(recalibraciones);
    const estado = estadoCalibracionDetalleIa(data, recalibraciones);
    const criterios = criteriosCuestionadosCalibracionIa(data, recalibraciones);
    const resuelta = ["Resuelta", "Rechazada", "Cancelada"].includes(estado);
    return `
        <div class="calibration-summary-grid">
            ${cardCalibracionIa("Score IA original", scoreIa !== null ? formatScoreCalibracionIa(scoreIa) : "Sin información")}
            ${cardCalibracionIa("Score técnico actual", scoreTecnico !== null ? formatScoreCalibracionIa(scoreTecnico) : "Sin información")}
            ${cardCalibracionIa("Score propuesto supervisor", scorePropuesto !== null ? formatScoreCalibracionIa(scorePropuesto) : "Pendiente de integración")}
            ${cardCalibracionIa("Score final resuelto", scoreFinal !== null ? formatScoreCalibracionIa(scoreFinal) : "Pendiente")}
            ${cardCalibracionIa("Estado calibración", `<span class="calibration-status ${claseEstadoCalibracionIa(estado)}">${escapeHtml(estado)}</span>`, true)}
            ${cardCalibracionIa("Criterios cuestionados", String(criterios.length || recalibraciones.length || 0))}
        </div>
        <section class="calibration-workspace-grid">
            <article class="calibration-panel calibration-request-card">
                <h5>Solicitud de recalibración</h5>
                ${renderDatosSolicitudCalibracionIa(data, recalibraciones, estado)}
                ${renderTablaCriteriosCuestionadosIa(criterios)}
            </article>
            <article class="calibration-panel calibration-trace-card">
                <h5>Trazabilidad</h5>
                ${renderTimelineCalibracionIa(data, recalibraciones, estado, scoreIa, scoreFinal)}
            </article>
        </section>
        ${resuelta ? renderResolucionCalibracionIa(data, recalibraciones, criterios, scoreTecnico, scoreFinal, scoreIa, estado) : renderPendienteResolucionCalibracionIa(estado)}
    `;
}

function cardCalibracionIa(label, value, htmlValue = false) {
    return `
        <article class="calibration-metric-card">
            <span>${escapeHtml(label)}</span>
            <strong>${htmlValue ? value : escapeHtml(value)}</strong>
        </article>
    `;
}

function claseEstadoCalibracionIa(estado = "") {
    const texto = normalizarTextoComparacionIa(estado);
    if (texto.includes("resuelta")) return "ok";
    if (texto.includes("rechazada") || texto.includes("cancelada")) return "danger";
    if (texto.includes("analisis") || texto.includes("enviada")) return "warning";
    return "muted";
}

function renderDatosSolicitudCalibracionIa(data = {}, recalibraciones = [], estado = "") {
    const primera = recalibraciones[0] || {};
    const motivo = primera.motivo || data.motivo_revision || "Solicitud histórica sin detalle por criterio.";
    return `
        <div class="calibration-meta-grid">
            <div><span>Solicitante</span><strong>${escapeHtml(primera.solicitado_por || data.supervisor || "Sin información")}</strong></div>
            <div><span>Fecha de solicitud</span><strong>${escapeHtml(formatoFecha(primera.fecha_solicitud || data.fecha_revision || data.fecha_creacion))}</strong></div>
            <div><span>Responsable de resolver</span><strong>${escapeHtml(primera.resuelto_por || "Sin asignar")}</strong></div>
            <div><span>Estado</span><strong>${escapeHtml(estado)}</strong></div>
        </div>
        <div class="calibration-general-reason">
            <span>Motivo general</span>
            <p>${escapeHtml(motivo)}</p>
        </div>
    `;
}

function criteriosCuestionadosCalibracionIa(data = {}, recalibraciones = []) {
    const criterios = evaluacionCalidadItemsIa(data).map(itemSgcIa);
    return recalibraciones.map(item => {
        const criterio = buscarCriterioCalibracionIa(item.item_cuestionado, criterios);
        return {
            recalibracion: item,
            criterio,
            codigo: criterio ? codigoCriterioHallazgoIa(criterio) : "",
            nombre: criterio ? criterioHallazgoIa(criterio) : (item.item_cuestionado || "Evaluación general"),
            dimension: criterio?.segmento_copc || criterio?.segmento || "-",
            grupo: criterio?.grupo_error_sgc || "-",
            peso: criterio ? Number(criterio.peso ?? criterio.puntaje_maximo ?? 0) : null,
            notaIa: criterio ? Number(criterio.nota ?? criterio.puntaje_obtenido ?? 0) : null,
            resultadoIa: criterio ? resultadoHallazgoFichaIa(criterio) : "Solicitud histórica",
            evidencia: item.evidencia_supervisor || (criterio ? evidenciaHallazgoFichaIa(criterio, data) : ""),
            motivo: item.motivo || "-",
            propuesta: item.nivel_sugerido || (item.score_sugerido != null ? `${formatoPeso(item.score_sugerido)} / 100` : "Sin propuesta"),
            notaPropuesta: primerNumeroIa([item.score_sugerido]),
            decisionFinal: item.estado || "",
            scoreFinal: primerNumeroIa([item.score_final]),
            comentarioResolucion: item.motivo_resolucion || "",
        };
    });
}

function buscarCriterioCalibracionIa(itemCuestionado = "", criterios = []) {
    const clave = normalizarTextoComparacionIa(itemCuestionado);
    if (!clave) return null;
    return criterios.find(item => {
        const codigo = normalizarTextoComparacionIa(codigoCriterioHallazgoIa(item));
        const nombre = normalizarTextoComparacionIa(criterioHallazgoIa(item));
        const itemTexto = normalizarTextoComparacionIa(item.item || item.item_copc || item.criterio || "");
        return (codigo && clave.includes(codigo)) || (nombre && (clave.includes(nombre) || nombre.includes(clave))) || (itemTexto && (clave.includes(itemTexto) || itemTexto.includes(clave)));
    }) || null;
}

function renderTablaCriteriosCuestionadosIa(criterios = []) {
    if (!criterios.length) {
        return `<div class="calibration-empty-inline">Solicitud histórica sin detalle por criterio.</div>`;
    }
    return `
        <div class="calibration-table-wrap">
            <table class="calibration-table">
                <thead>
                    <tr>
                        <th>Criterio</th>
                        <th>Resultado IA</th>
                        <th>Nota IA</th>
                        <th>Propuesta supervisor</th>
                        <th>Evidencia</th>
                        <th>Motivo de discrepancia</th>
                    </tr>
                </thead>
                <tbody>
                    ${criterios.map(item => `
                        <tr>
                            <td>
                                <strong>${escapeHtml(item.codigo ? `${item.codigo} ${item.nombre}` : item.nombre)}</strong>
                                <small>${escapeHtml(item.dimension)} · ${escapeHtml(item.grupo)}</small>
                            </td>
                            <td>${escapeHtml(item.resultadoIa || "-")}</td>
                            <td>${escapeHtml(item.notaIa !== null && Number.isFinite(item.notaIa) ? formatoPeso(item.notaIa) : "-")}</td>
                            <td>${escapeHtml(item.propuesta || "-")}</td>
                            <td>${escapeHtml(item.evidencia || "Sin evidencia textual suficiente")}</td>
                            <td>${escapeHtml(item.motivo || "-")}</td>
                        </tr>
                    `).join("")}
                </tbody>
            </table>
        </div>
    `;
}

function renderTimelineCalibracionIa(data = {}, recalibraciones = [], estado = "", scoreIa = null, scoreFinal = null) {
    const primera = recalibraciones[0] || {};
    const eventos = [];
    recalibraciones.slice().reverse().forEach(item => {
        eventos.push({
            fecha: item.fecha_solicitud,
            titulo: "Solicitud creada",
            descripcion: `${item.solicitado_por || "Supervisor"} cuestionó ${item.item_cuestionado || "la evaluación"}.`,
        });
        if (item.estado) {
            eventos.push({
                fecha: item.fecha_solicitud,
                titulo: normalizarTextoComparacionIa(item.estado).includes("pendiente") ? "Solicitud enviada" : "Estado actualizado",
                descripcion: `Estado: ${formatearEstadoRecalibracionIa(item.estado)}.`,
            });
        }
        if (item.fecha_resolucion) {
            eventos.push({
                fecha: item.fecha_resolucion,
                titulo: normalizarTextoComparacionIa(item.estado).includes("rechazada") ? "Solicitud rechazada" : "Resolución emitida",
                descripcion: item.motivo_resolucion || "Resolución registrada por Calidad.",
            });
        }
    });
    if (!eventos.length) {
        eventos.push({
            fecha: data.fecha_creacion || data.fecha_llamada,
            titulo: "Evaluación sin solicitud",
            descripcion: "Aún no se registran eventos de recalibración.",
        });
    }
    const diferenciaVsIa = scoreIa !== null && scoreFinal !== null ? scoreFinal - scoreIa : null;
    const propuesto = scorePropuestoSupervisorCalibracionIa(recalibraciones);
    const variacion = scoreFinal !== null && propuesto !== null ? scoreFinal - propuesto : null;
    return `
        <div class="calibration-timeline">
            ${eventos.map(evento => `
                <article>
                    <strong>${escapeHtml(evento.titulo)}</strong>
                    <span>${escapeHtml(formatoFecha(evento.fecha))}</span>
                    <p>${escapeHtml(evento.descripcion)}</p>
                </article>
            `).join("")}
        </div>
        <div class="calibration-diff-box">
            <div><span>Diferencia vs IA:</span><strong>${diferenciaVsIa !== null ? `${diferenciaVsIa >= 0 ? "+" : ""}${formatoPeso(diferenciaVsIa)} pts` : "Pendiente"}</strong></div>
            <div><span>Variación por calibración:</span><strong>${variacion !== null ? `${variacion >= 0 ? "+" : ""}${formatoPeso(variacion)} pts` : "Pendiente"}</strong></div>
        </div>
    `;
}

function renderPendienteResolucionCalibracionIa(estado = "") {
    return `
        <article class="calibration-panel calibration-pending-resolution">
            <h5>Resolución por Calidad</h5>
            <p>La solicitud se encuentra en estado <strong>${escapeHtml(estado)}</strong>. El score técnico no cambia hasta que exista una resolución válida.</p>
        </article>
    `;
}

function renderResolucionCalibracionIa(data = {}, recalibraciones = [], criterios = [], scoreTecnico = null, scoreFinal = null, scoreIa = null, estado = "") {
    const rows = criterios.length ? criterios : criteriosCuestionadosCalibracionIa(data, recalibraciones);
    const cambio = scoreTecnico !== null && scoreFinal !== null ? scoreFinal - scoreTecnico : null;
    return `
        <article class="calibration-panel">
            <h5>Resolución por criterio</h5>
            <div class="calibration-table-wrap">
                <table class="calibration-table">
                    <thead>
                        <tr>
                            <th>Criterio</th>
                            <th>Resultado IA</th>
                            <th>Propuesta supervisor</th>
                            <th>Decisión final</th>
                            <th>Comentario de resolución</th>
                            <th>Impacto</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${rows.map(item => `
                            <tr>
                                <td>${escapeHtml(item.codigo ? `${item.codigo} ${item.nombre}` : item.nombre)}</td>
                                <td>${escapeHtml(item.resultadoIa || "-")}</td>
                                <td>${escapeHtml(item.propuesta || "-")}</td>
                                <td>${escapeHtml(item.decisionFinal ? formatearEstadoRecalibracionIa(item.decisionFinal) : "Pendiente")}</td>
                                <td>${escapeHtml(item.comentarioResolucion || "Sin comentario de resolución")}</td>
                                <td>${escapeHtml(item.scoreFinal !== null && scoreIa !== null ? `${item.scoreFinal >= scoreIa ? "+" : ""}${formatoPeso(item.scoreFinal - scoreIa)}` : "-")}</td>
                            </tr>
                        `).join("")}
                    </tbody>
                </table>
            </div>
        </article>
        <article class="calibration-panel">
            <h5>Resultado de calibración</h5>
            <div class="calibration-result-grid">
                ${cardCalibracionIa("Score antes de calibrar", scoreTecnico !== null ? formatScoreCalibracionIa(scoreTecnico) : "Sin información")}
                ${cardCalibracionIa("Score final resuelto", scoreFinal !== null ? formatScoreCalibracionIa(scoreFinal) : "Pendiente")}
                ${cardCalibracionIa("Cambio aplicado", cambio !== null ? `${cambio >= 0 ? "+" : ""}${formatoPeso(cambio)} pts` : "Pendiente")}
                ${cardCalibracionIa("Estado final de la solicitud", estado)}
            </div>
            <p class="calibration-note">La resolución actualiza el score técnico, queda registrada en Historial y no altera la trazabilidad de la evaluación original.</p>
        </article>
    `;
}

function exportarTrazabilidadCalibracionIa() {
    const data = resultadoActualIa || {};
    const recalibraciones = Array.isArray(data.recalibraciones_lista) ? data.recalibraciones_lista : [];
    if (!haySolicitudCalibracionIa(data, recalibraciones)) {
        mostrarMensajeIa("No existe solicitud de recalibración para exportar.", "error");
        return;
    }
    const criterios = criteriosCuestionadosCalibracionIa(data, recalibraciones);
    const rows = [
        ["evaluacion", data.id_feedback || ""],
        ["score_ia_original", scoreIaOriginalCalibracionIa(data) ?? ""],
        ["score_tecnico_actual", scoreTecnicoActualCalibracionIa(data) ?? ""],
        ["estado_calibracion", estadoCalibracionDetalleIa(data, recalibraciones)],
        [],
        ["criterio", "resultado_ia", "propuesta_supervisor", "evidencia", "motivo", "decision_final", "comentario_resolucion"],
        ...criterios.map(item => [
            item.codigo ? `${item.codigo} ${item.nombre}` : item.nombre,
            item.resultadoIa || "",
            item.propuesta || "",
            item.evidencia || "",
            item.motivo || "",
            item.decisionFinal || "",
            item.comentarioResolucion || "",
        ]),
    ];
    const csv = rows.map(row => row.map(value => `"${String(value ?? "").replace(/"/g, '""')}"`).join(",")).join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `trazabilidad_calibracion_${data.id_feedback || "evaluacion"}.csv`;
    link.click();
    URL.revokeObjectURL(url);
}

function pintarHistorialDetalleIa(items) {
    const el = document.getElementById("historialDetalleListaIa");
    if (!el) return;
    const eventos = eventosHistorialConsolidadosIa(resultadoActualIa || {}, items || []);
    const conteos = conteosHistorialDetalleIa(eventos);
    const filtrados = filtroHistorialDetalleIa === "todos"
        ? eventos
        : eventos.filter(item => item.categoria === filtroHistorialDetalleIa);
    if (!eventos.length) {
        el.innerHTML = `
            <div class="history-detail-head">
                <h4>Historial de trazabilidad</h4>
                <p>Registro cronológico de acciones, cambios de estado y decisiones asociadas a la evaluación.</p>
            </div>
            <div class="empty-segment">Sin historial disponible. Todavía no se han registrado acciones o cambios para esta evaluación.</div>
        `;
        return;
    }
    el.innerHTML = `
        <div class="history-detail-head">
            <div>
                <h4>Historial de trazabilidad</h4>
                <p>Registro cronológico de acciones, cambios de estado y decisiones asociadas a la evaluación.</p>
            </div>
            <button class="btn-light btn-small" type="button" onclick="exportarHistorialDetalleIa()">Exportar historial</button>
        </div>
        <div class="history-filter-pills">
            ${["todos", "ia", "supervisor", "calidad", "coaching", "sistema"].map(tipo => `
                <button type="button" class="${filtroHistorialDetalleIa === tipo ? "active" : ""}" onclick="filtrarHistorialDetalleIa('${tipo}')">
                    ${escapeHtml(labelFiltroHistorialIa(tipo))} <span>${conteos[tipo] || 0}</span>
                </button>
            `).join("")}
        </div>
        ${filtrados.length ? renderTimelineHistorialIa(filtrados) : `<div class="empty-segment">No existen eventos de ${escapeHtml(labelFiltroHistorialIa(filtroHistorialDetalleIa).toLowerCase())} para esta evaluación.</div>`}
    `;
}

function construirHistorialBaseIa(data) {
    if (!data || !data.id_feedback) return [];
    return [
        {
            fecha: data.fecha_creacion || data.fecha_llamada,
            accion: "EVALUACION_CREADA",
            usuario: data.supervisor || "-",
            descripcion: `Audio registrado: ${data.archivo_nombre || "-"}`,
        },
        {
            fecha: data.fecha_creacion || data.fecha_llamada,
            accion: "ANALISIS_IA",
            usuario: "IA",
            descripcion: JSON.stringify({
                score_ia_original: scoreIaOriginalCalibracionIa(data),
                score_tecnico: scoreTecnicoActualCalibracionIa(data),
                nivel_riesgo: data.nivel_oportunidad_mejora || data.nivel_riesgo,
                tipo_llamada: data.tipo_llamada,
                confianza: data.confianza_evaluacion,
                estado_inicial: data.estado_revision || "PENDIENTE",
            }),
        },
        {
            fecha: data.fecha_revision || data.fecha_creacion || data.fecha_llamada,
            accion: "REVISION_SUPERVISOR",
            usuario: data.supervisor || "-",
            descripcion: JSON.stringify({
                estado_revision: data.estado_revision || "PENDIENTE",
                tipo_llamada: data.tipo_llamada_supervisor || data.tipo_llamada,
                comentario: data.comentario_feedback || data.comentario_revision || "",
            }),
        },
    ];
}

function eventosHistorialConsolidadosIa(data = {}, items = []) {
    const originales = [...construirHistorialBaseIa(data), ...items];
    const normalizados = originales.map((item, index) => normalizarEventoHistorialIa(item, index, data));
    const ordenados = normalizados.sort((a, b) => (a.fechaOrden - b.fechaOrden) || (a.idOrden - b.idOrden));
    const map = new Map();
    ordenados.forEach(evento => {
        const existente = map.get(evento.claveDuplicado);
        if (!existente) {
            map.set(evento.claveDuplicado, evento);
            return;
        }
        existente.registrosConsolidados = (existente.registrosConsolidados || 1) + 1;
        existente.cambios = fusionarCambiosHistorialIa(existente.cambios, evento.cambios);
        existente.datosTecnicos = { ...evento.datosTecnicos, ...existente.datosTecnicos };
        if (!existente.comentario && evento.comentario) existente.comentario = evento.comentario;
        if (evento.resumen && evento.resumen.length > existente.resumen.length) existente.resumen = evento.resumen;
    });
    return [...map.values()].sort((a, b) => (a.fechaOrden - b.fechaOrden) || (a.idOrden - b.idOrden));
}

function normalizarEventoHistorialIa(item = {}, index = 0, data = {}) {
    const tipoOriginal = item.accion || item.tipo || item.evento || "";
    const tipoNormal = tipoNormalizadoHistorialIa(tipoOriginal);
    const datos = extraerDatosTecnicosHistorialIa(item.descripcion || item.comentario || "");
    const categoria = categoriaHistorialIa(tipoNormal, item, datos);
    const cambios = cambiosHistorialIa(item, datos);
    const comentario = comentarioHistorialIa(item, datos);
    const fecha = item.fecha || item.fecha_evento || item.fecha_creacion || data.fecha_creacion || data.fecha_llamada;
    const fechaOrden = new Date(fecha || 0);
    const actor = actorHistorialIa(item.usuario || item.actor || item.responsable, categoria);
    const tituloVisible = tituloHistorialIa(tipoNormal);
    const resumen = resumenEventoHistorialIa(tipoNormal, item, datos, cambios);
    const estadoNuevo = cambioPorCampoHistorialIa(cambios, "Estado")?.nuevo || datos.estado_revision || datos.estado || item.estado_nuevo || "";
    const scoreNuevo = cambioPorCampoHistorialIa(cambios, "Score técnico")?.nuevo || datos.score_tecnico || datos.score_final || item.valor_nuevo || "";
    const claveBase = [
        tipoNormal,
        fechaClaveHistorialIa(fecha),
        normalizarTextoComparacionIa(actor.nombre),
        normalizarTextoComparacionIa(estadoNuevo),
        normalizarTextoComparacionIa(scoreNuevo),
        normalizarTextoComparacionIa(comentario || resumen).slice(0, 90),
    ].join("|");
    return {
        id: item.id_historial || item.id || `base-${index}`,
        idOrden: Number(item.id_historial || index),
        fecha,
        fechaOrden: Number.isNaN(fechaOrden.getTime()) ? new Date(0) : fechaOrden,
        tipoOriginal,
        tipoNormal,
        tituloVisible,
        categoria,
        actor,
        resumen,
        cambios,
        comentario,
        datosTecnicos: datos,
        enlaceRelacionado: enlaceHistorialIa(categoria, tipoNormal),
        claveDuplicado: claveBase,
        registrosConsolidados: 1,
    };
}

function tipoNormalizadoHistorialIa(value = "") {
    const key = normalizarTextoComparacionIa(value);
    if (key.includes("evaluacion creada") || key.includes("evaluacion_creada")) return "EVALUACION_CREADA";
    if (key.includes("analisis ia") || key.includes("analisis_ia")) return "ANALISIS_IA";
    if (key.includes("revision supervisor") || key.includes("revision_supervisor")) return "REVISION_SUPERVISOR";
    if (key.includes("evaluacion validada") || key.includes("validada")) return "EVALUACION_VALIDADA";
    if (key.includes("recalibracion solicitada") || key.includes("recalibracion_creada") || key.includes("recalibracion_solicitada")) return "RECALIBRACION_CREADA";
    if (key.includes("recalibracion resuelta") || key.includes("recalibracion_resuelta")) return "RECALIBRACION_RESUELTA";
    if (key.includes("coaching creado") || key.includes("coaching_creado")) return "COACHING_CREADO";
    if (key.includes("coaching realizado") || key.includes("coaching_realizado")) return "COACHING_REALIZADO";
    if (key.includes("coaching cerrado") || key.includes("coaching_cerrado")) return "COACHING_CERRADO";
    if (key.includes("seguimiento")) return "SEGUIMIENTO_CREADO";
    if (key.includes("export")) return "EXPORTACION";
    return String(value || "EVENTO").toUpperCase().replace(/\s+/g, "_");
}

function tituloHistorialIa(tipo = "") {
    const map = {
        EVALUACION_CREADA: "Evaluación creada",
        ANALISIS_IA: "Análisis IA generado",
        REVISION_SUPERVISOR: "Revisión del supervisor guardada",
        EVALUACION_VALIDADA: "Evaluación validada",
        RECALIBRACION_CREADA: "Recalibración solicitada",
        RECALIBRACION_RESUELTA: "Recalibración resuelta",
        COACHING_CREADO: "Plan de coaching creado",
        COACHING_REALIZADO: "Coaching realizado",
        COACHING_CERRADO: "Coaching cerrado",
        SEGUIMIENTO_CREADO: "Seguimiento registrado",
        EXPORTACION: "Exportación generada",
    };
    return map[tipo] || capitalizarEventoHistorialIa(tipo);
}

function capitalizarEventoHistorialIa(value = "") {
    return String(value || "Evento")
        .toLowerCase()
        .replace(/_/g, " ")
        .replace(/\b\p{L}/gu, letra => letra.toUpperCase());
}

function categoriaHistorialIa(tipo = "", item = {}, datos = {}) {
    const texto = normalizarTextoComparacionIa(`${tipo} ${item.usuario || ""} ${item.descripcion || ""}`);
    if (texto.includes("analisis") || texto.includes(" ia ")) return "ia";
    if (texto.includes("recalibracion") || texto.includes("calidad")) return "calidad";
    if (texto.includes("coaching") || texto.includes("seguimiento")) return "coaching";
    if (texto.includes("supervisor") || datos.decision_supervisor || datos.estado_revision) return "supervisor";
    return "sistema";
}

function actorHistorialIa(usuario = "", categoria = "sistema") {
    const limpio = String(usuario || "").trim();
    if (categoria === "ia") return { nombre: "IA", rol: "Sistema de evaluación" };
    if (!limpio || limpio === "-") return { nombre: categoria === "calidad" ? "Coordinación de Calidad" : "Sistema", rol: labelFiltroHistorialIa(categoria) };
    return { nombre: limpiarActorHistorialIa(limpio), rol: labelFiltroHistorialIa(categoria) };
}

function limpiarActorHistorialIa(value = "") {
    return String(value || "").replace(/\s+/g, " ").trim();
}

function extraerDatosTecnicosHistorialIa(texto = "") {
    const raw = String(texto || "").trim();
    if (!raw || !/^\s*[\[{]/.test(raw)) return {};
    try {
        return JSON.parse(raw);
    } catch {
        return {};
    }
}

function cambiosHistorialIa(item = {}, datos = {}) {
    const cambios = [];
    const anterior = item.valor_anterior;
    const nuevo = item.valor_nuevo;
    const anteriorJson = extraerDatosTecnicosHistorialIa(anterior);
    const nuevoJson = extraerDatosTecnicosHistorialIa(nuevo);
    if (Object.keys(anteriorJson).length || Object.keys(nuevoJson).length) {
        const keys = new Set([...Object.keys(anteriorJson), ...Object.keys(nuevoJson)]);
        keys.forEach(key => {
            cambios.push({
                campo: etiquetaCampoHistorialIa(key),
                anterior: valorUtilHistorialIa(anteriorJson[key]) ? formatearValorHistorialIa(key, anteriorJson[key]) : "",
                nuevo: valorUtilHistorialIa(nuevoJson[key]) ? formatearValorHistorialIa(key, nuevoJson[key]) : "",
            });
        });
    } else if (valorUtilHistorialIa(anterior) || valorUtilHistorialIa(nuevo)) {
        cambios.push({
            campo: campoCambioHistorialIa(item, datos),
            anterior: valorUtilHistorialIa(anterior) ? String(anterior) : "",
            nuevo: valorUtilHistorialIa(nuevo) ? String(nuevo) : "",
        });
    }
    Object.entries(datos || {}).forEach(([key, value]) => {
        if (!valorUtilHistorialIa(value)) return;
        cambios.push({ campo: etiquetaCampoHistorialIa(key), anterior: "", nuevo: formatearValorHistorialIa(key, value) });
    });
    return deduplicarCambiosHistorialIa(cambios);
}

function campoCambioHistorialIa(item = {}, datos = {}) {
    const texto = normalizarTextoComparacionIa(`${item.accion || ""} ${item.descripcion || ""}`);
    if (texto.includes("score")) return "Score técnico";
    if (texto.includes("estado")) return "Estado";
    if (datos.tipo_llamada) return "Tipo de llamada";
    return "Cambio registrado";
}

function etiquetaCampoHistorialIa(key = "") {
    const map = {
        score_ia_original: "Score IA original",
        score_tecnico: "Score técnico",
        score_final: "Score final resuelto",
        score_calidad: "Score IA original",
        nivel_riesgo: "Nivel de riesgo",
        tipo_llamada: "Tipo de llamada",
        confianza: "Confianza",
        estado_inicial: "Estado inicial",
        estado_revision: "Estado de revisión",
        decision_supervisor: "Decisión del supervisor",
        comentario: "Comentario",
    };
    return map[key] || capitalizarEventoHistorialIa(key);
}

function formatearValorHistorialIa(key = "", value = "") {
    if (/score/i.test(key) && value !== null && value !== undefined && value !== "") return `${formatoPeso(value)}/100`;
    if (/riesgo/i.test(key)) return formatearRiesgoVisibleIa(value);
    return String(value);
}

function comentarioHistorialIa(item = {}, datos = {}) {
    if (datos.comentario) return String(datos.comentario);
    const texto = String(item.descripcion || item.comentario || "").trim();
    if (/^\s*[\[{]/.test(texto)) return "";
    return texto;
}

function resumenEventoHistorialIa(tipo = "", item = {}, datos = {}, cambios = []) {
    if (tipo === "EVALUACION_CREADA") return comentarioHistorialIa(item, datos) || "Audio registrado para evaluación.";
    if (tipo === "ANALISIS_IA") return "La IA generó la evaluación técnica inicial.";
    if (tipo === "REVISION_SUPERVISOR") return "El supervisor guardó la revisión de la evaluación.";
    if (tipo.startsWith("RECALIBRACION")) return comentarioHistorialIa(item, datos) || "Evento asociado al proceso de recalibración.";
    if (tipo.startsWith("COACHING") || tipo === "SEGUIMIENTO_CREADO") return comentarioHistorialIa(item, datos) || "Evento asociado al plan de coaching.";
    if (cambios.length) return `${cambios.length} dato(s) registrado(s).`;
    return comentarioHistorialIa(item, datos) || capitalizarEventoHistorialIa(tipo);
}

function valorUtilHistorialIa(value) {
    const texto = String(value ?? "").trim();
    return Boolean(texto && texto !== "-" && texto.toLowerCase() !== "null" && texto.toLowerCase() !== "undefined");
}

function deduplicarCambiosHistorialIa(cambios = []) {
    const map = new Map();
    cambios.forEach(cambio => {
        const key = [cambio.campo, cambio.anterior, cambio.nuevo].map(normalizarTextoComparacionIa).join("|");
        if (!map.has(key)) map.set(key, cambio);
    });
    return [...map.values()].filter(cambio => valorUtilHistorialIa(cambio.anterior) || valorUtilHistorialIa(cambio.nuevo));
}

function fusionarCambiosHistorialIa(a = [], b = []) {
    return deduplicarCambiosHistorialIa([...a, ...b]);
}

function cambioPorCampoHistorialIa(cambios = [], campo = "") {
    const key = normalizarTextoComparacionIa(campo);
    return cambios.find(cambio => normalizarTextoComparacionIa(cambio.campo) === key);
}

function fechaClaveHistorialIa(value = "") {
    const fecha = new Date(value || 0);
    if (Number.isNaN(fecha.getTime())) return "";
    const rounded = new Date(fecha);
    rounded.setSeconds(0, 0);
    return rounded.toISOString();
}

function enlaceHistorialIa(categoria = "", tipo = "") {
    if (categoria === "calidad") return { tab: "calibracion", label: "Ver calibración" };
    if (categoria === "coaching") return { tab: "coaching", label: "Ver coaching" };
    if (tipo === "ANALISIS_IA") return { tab: "ficha_sgc", label: "Ver ficha SGC/PEC" };
    if (categoria === "supervisor") return { tab: "resumen", label: "Ver ficha" };
    return null;
}

function conteosHistorialDetalleIa(eventos = []) {
    const conteos = { todos: eventos.length, ia: 0, supervisor: 0, calidad: 0, coaching: 0, sistema: 0 };
    eventos.forEach(item => {
        conteos[item.categoria] = (conteos[item.categoria] || 0) + 1;
    });
    return conteos;
}

function labelFiltroHistorialIa(tipo = "") {
    return ({ todos: "Todos", ia: "IA", supervisor: "Supervisor", calidad: "Calidad", coaching: "Coaching", sistema: "Sistema" })[tipo] || capitalizarEventoHistorialIa(tipo);
}

function renderTimelineHistorialIa(eventos = []) {
    const grupos = new Map();
    eventos.forEach(evento => {
        const key = fechaDiaHistorialIa(evento.fecha);
        if (!grupos.has(key)) grupos.set(key, []);
        grupos.get(key).push(evento);
    });
    return `<div class="history-timeline">${[...grupos.entries()].map(([dia, rows]) => `
        <section class="history-day-group">
            <h5>${escapeHtml(dia)}</h5>
            ${rows.map(renderEventoHistorialIa).join("")}
        </section>
    `).join("")}</div>`;
}

function fechaDiaHistorialIa(value = "") {
    const fecha = new Date(value || 0);
    if (Number.isNaN(fecha.getTime())) return "Fecha no disponible";
    return fecha.toLocaleDateString("es-PE", { day: "2-digit", month: "long", year: "numeric" });
}

function horaHistorialIa(value = "") {
    const fecha = new Date(value || 0);
    if (Number.isNaN(fecha.getTime())) return "-";
    return fecha.toLocaleTimeString("es-PE", { hour: "2-digit", minute: "2-digit" });
}

function renderEventoHistorialIa(evento = {}) {
    const expanded = historialDetalleExpandidoIa === String(evento.id);
    return `
        <article class="history-event-card ${claseCategoriaHistorialIa(evento.categoria)}">
            <div class="history-event-main">
                <div class="history-event-dot"></div>
                <div class="history-event-content">
                    <div class="history-event-top">
                        <span>${escapeHtml(horaHistorialIa(evento.fecha))}</span>
                        <em>${escapeHtml(labelFiltroHistorialIa(evento.categoria))}</em>
                    </div>
                    <h6>${escapeHtml(evento.tituloVisible)}</h6>
                    <p>${escapeHtml(evento.resumen)}</p>
                    <div class="history-event-meta">
                        <strong>${escapeHtml(evento.actor.nombre)}</strong>
                        <span>${escapeHtml(evento.actor.rol)}</span>
                    </div>
                    ${renderCambiosResumenHistorialIa(evento.cambios)}
                    <div class="history-event-actions">
                        <button type="button" onclick="toggleDetalleEventoHistorialIa('${escapeHtml(String(evento.id))}')">${expanded ? "Ocultar detalle" : "Ver detalle"}</button>
                        ${evento.enlaceRelacionado ? `<button type="button" onclick="mostrarTabDetalleIa('${escapeHtml(evento.enlaceRelacionado.tab)}')">${escapeHtml(evento.enlaceRelacionado.label)}</button>` : ""}
                    </div>
                    ${expanded ? renderDetalleEventoHistorialIa(evento) : ""}
                </div>
            </div>
        </article>
    `;
}

function claseCategoriaHistorialIa(categoria = "") {
    return ({ ia: "ia", supervisor: "supervisor", calidad: "quality", coaching: "coaching", sistema: "system" })[categoria] || "system";
}

function renderCambiosResumenHistorialIa(cambios = []) {
    const visibles = cambios.filter(c => valorUtilHistorialIa(c.nuevo)).slice(0, 3);
    if (!visibles.length) return "";
    return `<div class="history-change-list">${visibles.map(cambio => `
        <div><span>${escapeHtml(cambio.campo)}</span><strong>${escapeHtml(cambio.anterior ? `${cambio.anterior} → ${cambio.nuevo}` : cambio.nuevo)}</strong></div>
    `).join("")}</div>`;
}

function renderDetalleEventoHistorialIa(evento = {}) {
    const cambios = evento.cambios || [];
    const datos = Object.entries(evento.datosTecnicos || {}).filter(([, value]) => valorUtilHistorialIa(value));
    return `
        <div class="history-event-detail">
            ${evento.comentario ? `<div><span>Comentario o motivo</span><p>${escapeHtml(evento.comentario)}</p></div>` : ""}
            ${cambios.length ? `<div><span>Cambios registrados</span>${cambios.map(cambio => `<p><b>${escapeHtml(cambio.campo)}:</b> ${escapeHtml(cambio.anterior ? `${cambio.anterior} → ${cambio.nuevo}` : cambio.nuevo)}</p>`).join("")}</div>` : ""}
            ${datos.length ? `<div><span>Datos traducidos</span>${datos.map(([key, value]) => `<p><b>${escapeHtml(etiquetaCampoHistorialIa(key))}:</b> ${escapeHtml(formatearValorHistorialIa(key, value))}</p>`).join("")}</div>` : ""}
            ${evento.registrosConsolidados > 1 ? `<small>${evento.registrosConsolidados} registros técnicos consolidados visualmente.</small>` : ""}
        </div>
    `;
}

function toggleDetalleEventoHistorialIa(id = "") {
    historialDetalleExpandidoIa = historialDetalleExpandidoIa === id ? "" : id;
    pintarHistorialDetalleIa(resultadoActualIa?.historial_lista || []);
}

function filtrarHistorialDetalleIa(tipo = "todos") {
    filtroHistorialDetalleIa = tipo;
    historialDetalleExpandidoIa = "";
    pintarHistorialDetalleIa(resultadoActualIa?.historial_lista || []);
}

function exportarHistorialDetalleIa() {
    const eventos = eventosHistorialConsolidadosIa(resultadoActualIa || {}, resultadoActualIa?.historial_lista || []);
    if (!eventos.length) {
        mostrarMensajeIa("No existe historial para exportar.", "error");
        return;
    }
    const rows = [
        ["fecha", "evento", "actor", "categoria", "resumen", "cambios", "comentario"],
        ...eventos.map(evento => [
            formatoFecha(evento.fecha),
            evento.tituloVisible,
            `${evento.actor.nombre} (${evento.actor.rol})`,
            labelFiltroHistorialIa(evento.categoria),
            evento.resumen,
            evento.cambios.map(c => `${c.campo}: ${c.anterior ? `${c.anterior} -> ` : ""}${c.nuevo}`).join(" | "),
            evento.comentario || "",
        ]),
    ];
    const csv = rows.map(row => row.map(value => `"${String(value ?? "").replace(/"/g, '""')}"`).join(",")).join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `historial_evaluacion_${resultadoActualIa?.id_feedback || "detalle"}.csv`;
    link.click();
    URL.revokeObjectURL(url);
}

function construirFeedbackCoachingIa(data = {}) {
    const hallazgos = hallazgosAccionablesCoachingIa(data);
    const evidencias = evidenciasAgrupadasIa.length ? evidenciasAgrupadasIa : agruparEvidenciasVisualesIa(normalizarEvidenciasDetalleIa(data).evidencias);
    const evidenciaPrioritaria = evidenciaPrioritariaCoachingIa(evidencias);
    const brecha = brechaPrioritariaCoachingIa(hallazgos, evidenciaPrioritaria);
    const fortalezas = data.coaching?.feedback_supervisor?.fortalezas?.join?.(", ")
        || data.feedback_supervisor?.fortalezas?.join?.(", ")
        || fortalezaObservableCoachingIa(data);
    const evidenciaTexto = evidenciaPrioritaria?.frase || "Requiere revisión del supervisor.";
    const conducta = brecha.conducta || "Manejo de objeciones.";
    const accion = brecha.accion || "Convertir la objeción principal en una alternativa concreta y verificable.";
    const objetivoSiguiente = data.feedback_supervisor?.objetivo_siguiente_llamada || data.coaching?.feedback_supervisor?.objetivo_siguiente_llamada || "Lograr un compromiso verificable o dejar una siguiente acción clara.";
    const recomendacion = brecha.recomendacion || recomendacionPrincipalEvidenciaIa(evidenciaPrioritaria || {}) || "Requiere revisión del supervisor.";
    const guion = guionCoachingIa(brecha, evidenciaPrioritaria, data);
    return {
        fortalezas,
        brecha: brecha.titulo || brechaPrincipalDetalleIa(data) || "Requiere revisión del supervisor.",
        impacto: brecha.impacto || "La gestión queda sin una acción de recupero verificable.",
        recomendacion,
        ocurrio: fraseCortaCoachingIa(evidenciaTexto),
        guion,
        objetivoGuion: "Practicar una respuesta concreta que conecte la objeción con monto, fecha, canal y confirmación.",
        conducta,
        accion,
        objetivoSiguiente,
        evidencia: fraseCortaCoachingIa(evidenciaTexto),
        objetivoMedible: "En las próximas 5 llamadas monitoreadas, explorar monto disponible, fecha y canal en al menos 4 casos aplicables y obtener confirmación expresa cuando exista intención de pago.",
        compromiso: "Me comprometo a explorar cuánto puede pagar el cliente, en qué fecha y por qué canal antes de cerrar la negociación.",
        evidenciaKey: evidenciaPrioritaria ? evidenciaKeyIa(evidenciaPrioritaria) : "",
    };
}

function poblarResponsablesCoachingIa(data = {}) {
    const select = document.getElementById("responsableCoachingIa");
    if (!select) return;
    const actual = data.responsable_coaching || data.responsable || "";
    const opciones = [
        { value: "", label: "Sin asignar" },
        ...responsablesCoachingSesionIa(data),
    ];
    if (actual && !opciones.some(item => item.value === actual)) {
        opciones.push({ value: actual, label: actual });
    }
    select.innerHTML = opciones.map(item => `<option value="${escapeHtml(item.value)}">${escapeHtml(item.label)}</option>`).join("");
    select.value = opciones.some(item => item.value === actual) ? actual : "";
}

function responsablesCoachingSesionIa(data = {}) {
    const tipo = tipoUsuarioIa();
    const nombre = localStorage.getItem("agente") || localStorage.getItem("nombre") || "";
    const dni = localStorage.getItem("dni") || localStorage.getItem("usuario") || "";
    const perfilesResponsables = ["SUPERVISOR", "GESTOR DE CALIDAD", "CALIDAD", "JEFE DE COBRANZA", "JEFE DE CARTERA", "JEFE DE CARTERAS", "ADMINISTRADOR"];
    const opciones = [];
    if (perfilesResponsables.includes(tipo) && (nombre || dni)) {
        const value = [dni, nombre].filter(Boolean).join(" - ");
        opciones.push({ value, label: `${nombre || dni} · ${formatearTipoResponsableIa(tipo)}` });
    }
    if (data.supervisor) {
        opciones.push({ value: data.supervisor, label: `${data.supervisor} · Supervisor de la evaluación` });
    }
    return opciones.filter((item, index, array) => item.value && array.findIndex(x => x.value === item.value) === index);
}

function formatearTipoResponsableIa(tipo = "") {
    const key = String(tipo || "").toUpperCase();
    if (key === "SUPERVISOR") return "Supervisor";
    if (key === "GESTOR DE CALIDAD" || key === "CALIDAD") return "Gestor de calidad";
    if (key === "JEFE DE COBRANZA") return "Jefe de cobranza";
    if (key === "JEFE DE CARTERA" || key === "JEFE DE CARTERAS") return "Jefe de cartera";
    if (key === "ADMINISTRADOR") return "Administrador";
    return key || "Responsable";
}

function hallazgosAccionablesCoachingIa(data = {}) {
    const items = hallazgosSgcItemsIa(data).length ? hallazgosSgcItemsIa(data) : evaluacionCalidadItemsIa(data);
    const normalizados = repararHallazgosContextualesFichaIa(
        items.map(itemSgcIa).map(normalizarHallazgoFichaIa),
        data,
    );
    return deduplicarHallazgosFichaIa(
        normalizados
            .filter(esHallazgoAccionableFichaIa)
            .filter(item => !esHallazgoGenericoSinEvidenciaIa(item)),
    ).rows;
}

function evidenciaPrioritariaCoachingIa(evidencias = []) {
    const preferida = evidencias.find(item => normalizarTextoComparacionIa(item.criterio || "").includes("manejo de objeciones"))
        || evidencias.find(item => item.tipo === "anulante")
        || evidencias.find(item => item.tipo === "critica")
        || evidencias.find(item => item.tipo === "revision")
        || evidencias[0];
    return preferida || null;
}

function brechaPrioritariaCoachingIa(hallazgos = [], evidencia = null) {
    const orden = [
        item => item.falta_anulante || item.puede_descalificar,
        item => normalizarTextoComparacionIa(item.grupo_error_sgc).includes("usuario"),
        item => normalizarTextoComparacionIa(item.grupo_error_sgc).includes("cumplimiento"),
        item => normalizarTextoComparacionIa(item.grupo_error_sgc).includes("negocio"),
        () => true,
    ];
    const item = orden.map(fn => hallazgos.find(fn)).find(Boolean) || {};
    const factor = criterioHallazgoIa(item) || evidencia?.criterio || "Brecha prioritaria";
    const factorKey = normalizarTextoComparacionIa(factor);
    if (factorKey.includes("manejo de objeciones")) {
        return {
            titulo: "Manejo de objeciones y adaptación de la propuesta.",
            conducta: "Manejo de objeciones.",
            accion: "Preguntar monto disponible y fecha antes de abandonar la negociación.",
            impacto: "La objeción del cliente no se convirtió en una alternativa viable.",
            recomendacion: "Preguntar cuánto sí puede pagar y en qué fecha antes de abandonar la negociación.",
        };
    }
    return {
        titulo: factor,
        conducta: factor,
        accion: item.recomendacion_entrenable || item.recomendacion || "Precisar la conducta esperada y practicar una frase aplicable.",
        impacto: item.impacto_negocio || item.impacto || item.hallazgo || "La brecha afecta la continuidad de la gestión.",
        recomendacion: item.recomendacion_entrenable || item.recomendacion || "",
    };
}

function fortalezaObservableCoachingIa(data = {}) {
    const explicitas = Array.isArray(data.fortalezas_lista) ? data.fortalezas_lista.filter(evidenciaEsTextualFichaIa) : [];
    if (explicitas.length) return explicitas.slice(0, 3).join(" ");
    const texto = normalizarTextoComparacionIa(data.transcripcion || "");
    const fortalezas = [];
    if (texto.includes("le habla") || texto.includes("buenos dias")) fortalezas.push("saludó e inició la conversación");
    if (texto.includes("si digame") || texto.includes("ella habla") || texto.includes("soy yo")) fortalezas.push("obtuvo una confirmación de contacto");
    if (texto.includes("propuesta") || texto.includes("alternativa") || texto.includes("abono")) fortalezas.push("presentó una alternativa o posibilidad de pago");
    return fortalezas.length ? `${capitalizarIa(fortalezas.join(", "))}.` : "Requiere revisión del supervisor.";
}

function guionCoachingIa(brecha = {}, evidencia = null, data = {}) {
    const factor = normalizarTextoComparacionIa(brecha.titulo || evidencia?.criterio || "");
    if (factor.includes("cierre")) return "Entonces confirmamos S/___ para el ___ mediante ___, ¿correcto?";
    if (factor.includes("claridad") || factor.includes("monto")) return "Su deuda total es de S/___ y la alternativa vigente es de S/___. Son conceptos diferentes.";
    if (factor.includes("empatia")) return "Entiendo la dificultad. Para encontrar una opción realista, necesito saber cuánto podría asumir.";
    return data.feedback_asesor?.frase_recomendada || data.guion_sugerido || "Entiendo que ese monto no es viable. ¿Con cuánto podría iniciar y en qué fecha?";
}

function citaCoachingPorPatronIa(data = {}, patron) {
    return extraerCitaFichaIa(String(data.transcripcion || ""), [patron]) || "";
}

function fraseCortaCoachingIa(texto = "") {
    const limpio = String(texto || "").replace(/\s+/g, " ").trim();
    if (!limpio) return "Requiere revisión del supervisor.";
    return limpio.length > 180 ? `${limpio.slice(0, 177)}...` : limpio;
}

function capitalizarIa(texto = "") {
    const value = String(texto || "");
    return value ? value.charAt(0).toUpperCase() + value.slice(1) : value;
}

function irEvidenciaCoachingIa() {
    const sugerido = window.coachingSugeridoIa || {};
    mostrarTabDetalleIa("evidencias");
    const key = sugerido.evidenciaKey || "";
    if (key) evidenciaExpandidaIa = key;
    if (typeof pintarTablaEvidenciasIa === "function") pintarTablaEvidenciasIa(evidenciasAgrupadasIa);
    setTimeout(() => {
        const safeKey = typeof CSS !== "undefined" && CSS.escape ? CSS.escape(key) : key.replace(/"/g, '\\"');
        const target = key
            ? document.querySelector(`[data-evidence-key="${safeKey}"]`)
            : document.getElementById("tablaEvidenciasIa");
        target?.scrollIntoView({ behavior: "smooth", block: "center" });
    }, 120);
}

function cargarCoachingEnFormulario(data) {
    const sugerido = construirFeedbackCoachingIa(data);
    window.coachingSugeridoIa = sugerido;
    window.coachingPlanGuardadoIa = Boolean(data.estado_coaching || data.fecha_coaching || data.compromiso_agente || data.resultado_coaching);
    setText("coachingFortalezasIa", sugerido.fortalezas);
    setText("coachingBrechaIa", sugerido.brecha);
    setText("coachingImpactoIa", sugerido.impacto);
    setText("coachingRecomendacionIa", sugerido.recomendacion);
    setText("coachingOcurrioIa", sugerido.ocurrio);
    setText("coachingGuionIa", sugerido.guion);
    setText("coachingObjetivoGuionIa", sugerido.objetivoGuion);
    setText("coachingConductaPrioritariaIa", sugerido.conducta);
    setText("coachingAccionEntrenableIa", sugerido.accion);
    setText("coachingObjetivoSiguienteIa", sugerido.objetivoSiguiente);
    setText("coachingEvidenciaOrigenIa", sugerido.evidencia);

    setValue("estadoCoachingIa", normalizarEstadoCoachingVistaIa(data.estado_coaching));
    setValue("fechaCoachingIa", data.fecha_coaching ? String(data.fecha_coaching).slice(0, 16) : "");
    poblarResponsablesCoachingIa(data);
    setValue("tipoIntervencionCoachingIa", data.tipo_intervencion || "COACHING_INDIVIDUAL");
    setValue("conductaPlanCoachingIa", data.conducta_prioritaria || sugerido.conducta);
    setValue("objetivoMedibleCoachingIa", data.objetivo_medible || sugerido.objetivoMedible);
    setValue("compromisoAgenteIa", data.compromiso_agente || sugerido.compromiso);
    setValue("fechaEjecucionCoachingIa", data.fecha_ejecucion_coaching ? String(data.fecha_ejecucion_coaching).slice(0, 16) : "");
    setValue("resultadoObservadoCoachingIa", data.resultado_coaching || data.resultado_observado || "");
    setValue("cumplioObjetivoCoachingIa", data.cumplio_objetivo || "");
    setValue("evidenciaMejoraCoachingIa", data.evidencia_mejora || "");
    setValue("proximaRevisionCoachingIa", data.proxima_revision ? String(data.proxima_revision).slice(0, 10) : "");
    setValue("estadoFinalCoachingIa", data.estado_final_coaching || "");
    actualizarAyudaCoachingIa(data.estado_coaching || "NO_PROGRAMADO");
}

function normalizarEstadoCoachingVistaIa(estado = "") {
    const key = String(estado || "").toUpperCase();
    if (!key || key === "PENDIENTE") return "NO_PROGRAMADO";
    return key;
}

function actualizarAyudaCoachingIa(estado) {
    const ayuda = document.getElementById("ayudaCoachingIa");
    const btn = document.getElementById("btnGuardarCoachingIa");
    const btnRealizado = document.getElementById("btnMarcarCoachingRealizadoIa");
    const seguimiento = document.getElementById("formSeguimientoCoachingIa");
    const ayudaSeguimiento = document.getElementById("ayudaSeguimientoCoachingIa");
    const normalizado = normalizarEstadoCoachingVistaIa(estado);
    const planGuardado = Boolean(window.coachingPlanGuardadoIa);
    const puedeMarcarRealizado = Boolean(planGuardado && valor("fechaCoachingIa") && valor("responsableCoachingIa") && !["", "SIN ASIGNAR"].includes(valor("responsableCoachingIa").toUpperCase()));
    const seguimientoActivo = ["EN_PROCESO", "REALIZADO", "CERRADO"].includes(normalizado);
    if (btn) btn.textContent = "Guardar plan";
    if (btnRealizado) {
        btnRealizado.disabled = !puedeMarcarRealizado;
        btnRealizado.title = puedeMarcarRealizado ? "" : "Completa fecha programada y responsable para marcarlo como realizado.";
    }
    if (seguimiento) seguimiento.classList.toggle("coaching-disabled-form", !seguimientoActivo);
    if (ayuda) ayuda.textContent = puedeMarcarRealizado
        ? "Plan listo para marcar como realizado cuando corresponda."
        : "Guarda el plan con fecha y responsable para marcar el coaching como realizado.";
    if (ayudaSeguimiento) ayudaSeguimiento.textContent = seguimientoActivo
        ? "Registra la ejecución y evidencia antes de cerrar el coaching."
        : "El seguimiento se habilita cuando el coaching está en curso o realizado.";
}

async function guardarCoachingIa() {
    const idFeedback = valor("feedbackIdActualIa");
    if (!idFeedback) {
        mostrarMensajeIa("Primero abre una evaluación para registrar coaching.", "error");
        return;
    }
    const btn = document.getElementById("btnGuardarCoachingIa");
    btn.disabled = true;
    btn.textContent = "Guardando...";
    try {
        const formData = new FormData();
        formData.append("estado", valor("estadoCoachingIa") || "PROGRAMADO");
        formData.append("feedback_supervisor", resumenPlanCoachingIa());
        formData.append("compromiso_agente", valor("compromisoAgenteIa"));
        formData.append("fecha_programada", valor("fechaCoachingIa"));
        formData.append("resultado", resultadoSeguimientoCoachingIa());
        formData.append("responsable", valor("responsableCoachingIa") || localStorage.getItem("agente") || localStorage.getItem("dni") || "SIN_USUARIO");
        const response = await fetchIa(`${IA_FEEDBACK_BASE}/${idFeedback}/coaching`, {
            method: "POST",
            body: formData,
        }, 30000);
        const data = await leerJsonSeguro(response);
        if (!response.ok) throw new Error(data.detail || "No se pudo guardar el coaching.");
        resultadoActualIa = data;
        window.coachingPlanGuardadoIa = true;
        actualizarAyudaCoachingIa(valor("estadoCoachingIa"));
        pintarHistorialDetalleIa(data.historial_lista || []);
        pintarCalibracionDetalleIa(data);
        await cargarHistorialIa();
        await cargarReporteriaIa();
        mostrarMensajeIa("Coaching guardado con trazabilidad.", "ok");
    } catch (error) {
        mostrarMensajeIa(error.message || "Error guardando coaching.", "error");
    } finally {
        btn.disabled = false;
        btn.textContent = "Guardar plan";
    }
}

function marcarPlanCoachingPendienteIa() {
    if (!resultadoActualIa) return;
    window.coachingPlanGuardadoIa = false;
    actualizarAyudaCoachingIa(valor("estadoCoachingIa"));
}

async function marcarCoachingRealizadoIa() {
    if (!valor("fechaCoachingIa") || !valor("responsableCoachingIa")) {
        mostrarMensajeIa("Completa fecha programada y responsable antes de marcarlo como realizado.", "error");
        return;
    }
    setValue("estadoCoachingIa", "REALIZADO");
    actualizarAyudaCoachingIa("REALIZADO");
    await guardarCoachingIa();
}

async function guardarSeguimientoCoachingIa() {
    const estado = String(valor("estadoCoachingIa") || "").toUpperCase();
    if (!["EN_PROCESO", "REALIZADO", "CERRADO"].includes(estado)) {
        mostrarMensajeIa("Primero marca el coaching como en curso o realizado para registrar seguimiento.", "error");
        return;
    }
    await guardarCoachingIa();
}

async function cerrarCoachingDesdeSeguimientoIa() {
    const faltantes = [];
    if (!valor("resultadoObservadoCoachingIa")) faltantes.push("resultado observado");
    if (!valor("cumplioObjetivoCoachingIa")) faltantes.push("cumplimiento del objetivo");
    if (!valor("evidenciaMejoraCoachingIa")) faltantes.push("evidencia de mejora o justificación");
    if (!valor("estadoFinalCoachingIa")) faltantes.push("estado final");
    if (faltantes.length) {
        mostrarMensajeIa(`Para cerrar el coaching falta: ${faltantes.join(", ")}.`, "error");
        return;
    }
    setValue("estadoCoachingIa", "CERRADO");
    await guardarCoachingIa();
}

function resumenPlanCoachingIa() {
    const sugerido = window.coachingSugeridoIa || {};
    return [
        `Brecha prioritaria: ${valor("conductaPlanCoachingIa") || sugerido.brecha || "Requiere revisión del supervisor."}`,
        `Tipo de intervención: ${textoSelectIa("tipoIntervencionCoachingIa") || "Sin información"}`,
        `Objetivo medible: ${valor("objetivoMedibleCoachingIa") || "Sin información"}`,
        `Acción entrenable: ${sugerido.accion || "Sin información"}`,
        `Evidencia origen: ${sugerido.evidencia || "Sin información"}`,
    ].join("\n");
}

function resultadoSeguimientoCoachingIa() {
    const partes = [];
    if (valor("resultadoObservadoCoachingIa")) partes.push(`Resultado observado: ${valor("resultadoObservadoCoachingIa")}`);
    if (valor("cumplioObjetivoCoachingIa")) partes.push(`Cumplió objetivo: ${textoSelectIa("cumplioObjetivoCoachingIa")}`);
    if (valor("evidenciaMejoraCoachingIa")) partes.push(`Evidencia de mejora: ${valor("evidenciaMejoraCoachingIa")}`);
    if (valor("proximaRevisionCoachingIa")) partes.push(`Próxima revisión: ${valor("proximaRevisionCoachingIa")}`);
    if (valor("estadoFinalCoachingIa")) partes.push(`Estado final: ${textoSelectIa("estadoFinalCoachingIa")}`);
    return partes.join("\n");
}

function textoSelectIa(id) {
    const el = document.getElementById(id);
    return el?.options?.[el.selectedIndex]?.textContent?.trim() || valor(id);
}

function mostrarVistaCalibracionIa() {
    activarVistaReporteriaIa({ view: "calibracion" });
    cargarReporteriaIa();
}

function mostrarVistaCoachingIa() {
    activarVistaReporteriaIa({ view: "coaching" });
    cargarReporteriaIa();
}

function mostrarVistaAlertasIa() {
    activarVistaReporteriaIa({ view: "alertas" });
    cargarReporteriaIa();
}

function mostrarVistaReportesIa() {
    activarVistaReporteriaIa({ view: "reportes" });
    setVistaActivaIa("reportes");
    cargarReporteriaIa();
    document.querySelector(".report-detail-card")?.scrollIntoView({ behavior: "smooth", block: "start" });
}

function mostrarVistaPromptIa() {
    activarVistaReporteriaIa({ view: "prompt" });
}

function abrirAdministracionPautasIa() {
    window.location.href = "/frontend/views/admin_pautas_evaluacion.html";
}

async function cargarPromptIa() {
    try {
        const perfil = localStorage.getItem("tipo") || "";
        const cartera = valor("promptCarteraIa");
        const params = new URLSearchParams({ perfil });
        if (cartera) params.set("cartera", cartera);
        const response = await fetchIa(`${IA_FEEDBACK_BASE}/prompt?${params.toString()}`, {}, 12000);
        const data = await leerJsonSeguro(response);
        if (!response.ok || !data.puede_editar) return;

        setValue("promptBaseIa", data.prompt_base || "");
        setText("promptOrigenIa", obtenerTextoOrigenPrompt(data));
        setText(
            "promptMetaIa",
            data.usa_prompt_personalizado
                ? `Origen: ${obtenerTextoOrigenPrompt(data)}. Ultima actualizacion: ${formatoFecha(data.fecha_actualizacion)} por ${data.actualizado_por || "-"}`
                : "Prompt base del sistema. Guardalo para crear una version general o especifica de cartera."
        );
        pintarVistaPromptIa();
    } catch {
        // Si no carga la configuración, el análisis sigue usando el prompt general.
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
        mostrarMensajeIa("Prompt guardado correctamente. Se aplicará en los próximos análisis.", "ok");
    } catch (error) {
        mostrarMensajeIa(error.message || "Error guardando prompt.", "error");
    } finally {
        btn.disabled = false;
        btn.textContent = "Guardar prompt";
    }
}

function pintarPuntosCriticos(items) {
    const tbody = document.getElementById("puntosCriticosIa");
    if (!tbody) return;
    if (!items.length) {
        tbody.innerHTML = `<tr><td colspan="9">Sin puntos criticos registrados.</td></tr>`;
        return;
    }

    tbody.innerHTML = items.slice(0, 5).map(item => `
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
            throw new Error("El analisis IA esta tardando mas de lo esperado. Intenta nuevamente en unos minutos o revisa si la evaluacion termino en el historial.");
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

function setWidthIa(id, value) {
    const el = document.getElementById(id);
    if (!el) return;
    el.style.width = `${Math.max(0, Math.min(100, Number(value || 0)))}%`;
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
    document.querySelectorAll(".quality-nav button").forEach(button => {
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
        ["id_llamada", "audio", "agente", "supervisor", "cartera", "notas_por_segmento", "score_final", "grupo_error_sgc", "factor_sgc", "requiere_feedback", "requiere_coaching", "estado_feedback", "estado_coaching", "observacion_supervisor"],
        ...rows.map(item => {
            const sgc = principalSgcDetalleIa(item);
            return [
                item.id_feedback || "",
                item.archivo_nombre || "",
                item.agente || "",
                item.supervisor || "",
                item.cartera || "",
                formatearNotasSegmentoIa(item.notas_segmento),
                Number(item.score_final ?? item.score_calidad ?? 0).toFixed(1),
                sgc.grupo,
                sgc.factor,
                requiereFeedbackIa(item) ? "SI" : "NO",
                requiereCoachingIa(item) ? "SI" : "NO",
                item.estado_feedback || "",
                item.estado_coaching || "",
                item.observacion_supervisor || "",
            ];
        }),
        [],
        ["FICHA SGC/PEC DETALLE AUDITORIA"],
        ["id_llamada", "audio", "agente", "supervisor", "cartera", "grupo_sgc", "factor", "calificacion_corta", "calificacion", "motivo", "evidencia", "recomendacion"],
        ...rows.flatMap(item => itemsFichaAuditoriaSgcIa(itemsSgcDetalleIa(item)).map(fila => [
            item.id_feedback || "",
            item.archivo_nombre || "",
            item.agente || "",
            item.supervisor || "",
            item.cartera || "",
            fila.grupo_auditoria_sgc || "",
            fila.factor_auditoria_sgc || "",
            fila.calificacion_corta || "",
            fila.calificacion || "",
            fila.motivo || fila.hallazgo || "",
            fila.evidencia || "",
            fila.recomendacion || "",
        ]))
    ];
    descargarCsvIa(csvRows, `reporte_calidad_ia_${new Date().toISOString().slice(0, 10)}.csv`);
    mostrarMensajeIa("Reporte exportado correctamente.", "ok");
}

function exportarFichaSgcIa() {
    const evaluacion = evaluacionCalidadItemsIa(resultadoActualIa || {});
    if (!evaluacion.length) {
        mostrarMensajeIa("No hay datos suficientes para exportar la ficha SGC/PEC.", "error");
        return;
    }
    const esPauta = tienePautaAplicadaIa(resultadoActualIa || {});
    const filas = esPauta ? evaluacion.map(itemSgcIa) : itemsFichaAuditoriaSgcIa(evaluacion);
    const csvRows = [
        [esPauta ? "FICHA DE CRITERIOS DE LA PAUTA" : "FICHA DE ERRORES SGC/PEC"],
        ["audio", resultadoActualIa?.archivo_nombre || "-"],
        ["supervisor", resultadoActualIa?.supervisor || "-"],
        ...(esPauta ? [["pauta", resultadoActualIa?.pauta || "-"], ["version_pauta", resultadoActualIa?.pauta_version || "-"]] : []),
        ["score_final", Number(resultadoActualIa?.score_final ?? resultadoActualIa?.score_calidad ?? 0).toFixed(1)],
        [],
        esPauta
            ? ["bloque", "criterio", "peso", "nota", "calificacion", "motivo", "evidencia", "recomendacion"]
            : ["grupo_sgc", "factor", "calificacion_corta", "calificacion", "motivo", "evidencia", "recomendacion"],
        ...filas.map(item => [
            ...(esPauta ? [
                bloquePautaItemIa(item, resultadoActualIa || {}),
                itemCopcVisibleIa(item),
                item.peso ?? item.puntaje_maximo ?? "",
                item.nota ?? item.puntaje_obtenido ?? "",
                item.calificacion || item.resultado || "",
            ] : [
                item.grupo_auditoria_sgc || "",
                item.factor_auditoria_sgc || "",
                item.calificacion_corta || "",
                item.calificacion || "",
            ]),
            item.motivo || item.hallazgo || "",
            item.evidencia || "",
            item.recomendacion || "",
        ])
    ];
    descargarCsvIa(csvRows, `${esPauta ? "criterios_pauta" : "ficha_sgc_pec"}_${new Date().toISOString().slice(0, 10)}.csv`);
    mostrarMensajeIa(esPauta ? "Detalle de la evaluación exportado correctamente." : "Ficha SGC/PEC exportada correctamente.", "ok");
}

function descargarCsvIa(csvRows, filename) {
    const csv = csvRows.map(row => row.map(valorCsvIa).join(";")).join("\r\n");
    const blob = new Blob([`\uFEFF${csv}`], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
}

function filasResumenCarteraSemanaCsv(items) {
    const semanas = [...new Set(items.map(item => claveSemanaClienteIa(item.fecha_llamada || item.fecha_creacion)))].sort();
    const grupos = {};
    items.forEach(item => {
        const cartera = item.cartera || "Sin cartera";
        const semana = claveSemanaClienteIa(item.fecha_llamada || item.fecha_creacion);
        const actual = grupos[cartera] || { cartera, total: 0, scoreTotal: 0, criticos: 0, semanas: {} };
        actual.total += 1;
        actual.scoreTotal += Number(item.score_final ?? item.score_calidad ?? 0);
        actual.criticos += Number(item.total_puntos_criticos || 0);
        const sem = actual.semanas[semana] || { total: 0, scoreTotal: 0 };
        sem.total += 1;
        sem.scoreTotal += Number(item.score_final ?? item.score_calidad ?? 0);
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
window.toggleFiltrosResumenIa = toggleFiltrosResumenIa;
window.aplicarFiltrosResumenIa = aplicarFiltrosResumenIa;
window.abrirAdministracionPautasIa = abrirAdministracionPautasIa;
window.abrirPromptIa = abrirPromptIa;
window.cerrarPromptIa = cerrarPromptIa;
window.mostrarSeccionPromptIa = mostrarSeccionPromptIa;
window.guardarPromptIa = guardarPromptIa;
window.cargarPromptIa = cargarPromptIa;
window.abrirRecalibracionIa = abrirRecalibracionIa;
window.cerrarRecalibracionIa = cerrarRecalibracionIa;
window.mostrarTabDetalleIa = mostrarTabDetalleIa;
window.mostrarTranscripcionIa = mostrarTranscripcionIa;
window.cambiarVelocidadAudioIa = cambiarVelocidadAudioIa;
window.irAEvidenciaAudioIa = irAEvidenciaAudioIa;
window.toggleHallazgoGrupoIa = toggleHallazgoGrupoIa;
window.filtrarHallazgosFichaIa = filtrarHallazgosFichaIa;
window.prepararRecalibracionItemIa = prepararRecalibracionItemIa;
window.guardarBorradorRevisionIa = guardarBorradorRevisionIa;
window.validarEvaluacionDesdeFichaIa = validarEvaluacionDesdeFichaIa;
window.toggleDetalleSgcIa = toggleDetalleSgcIa;
window.exportarFichaSgcIa = exportarFichaSgcIa;
window.guardarCoachingIa = guardarCoachingIa;
window.mostrarVistaCalibracionIa = mostrarVistaCalibracionIa;
window.mostrarVistaCoachingIa = mostrarVistaCoachingIa;
window.mostrarVistaEvaluacionesIa = mostrarVistaEvaluacionesIa;
window.mostrarVistaAlertasIa = mostrarVistaAlertasIa;
window.mostrarVistaReportesIa = mostrarVistaReportesIa;
window.mostrarVistaPromptIa = mostrarVistaPromptIa;

