const IA_FEEDBACK_BASE = obtenerBaseUrlIaFeedback();

let historialIa = [];
let resultadoActualIa = null;
let reporteriaActualIa = null;
let detalleReporteIa = [];
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
        }, 180000);
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
        if (!response.ok) throw new Error(data.detail || "No se pudo obtener el análisis.");
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

    setText("trazaAudioIa", data.archivo_nombre || "-");
    setText("trazaSupervisorIa", data.supervisor || "-");
    setText("trazaRevisionIa", data.estado_revision || "PENDIENTE");
    setText("resultadoNivelIa", formatearRiesgoVisibleIa(data.nivel_oportunidad_mejora));
    setText("resumenIa", data.resumen || "-");
    setText("tipoContactoIa", data.tipo_contacto || "-");
    setText("resultadoGestionIa", data.resultado_gestion || "-");
    setText("objecionIa", data.objecion_principal || "-");
    const scoreMostrado = data.score_final ?? data.score_normalizado ?? data.score_calidad;
    setText("scoreCalidadIa", scoreMostrado != null ? `${Number(scoreMostrado).toFixed(1)} / 100` : "-");
    setText("scorePreliminarIa", data.score_calidad_ia != null ? `${Number(data.score_calidad_ia).toFixed(1)} / 100` : "-");
    setText("nivelRiesgoDetalleIa", formatearRiesgoVisibleIa(data.nivel_oportunidad_mejora));
    setText("faltaAnulanteIa", data.falta_anulante ? "Si" : "No");
    setText("revisionHumanaIa", data.requiere_revision_humana ? "Sí" : "No");
    aplicarEstadoCardsDetalleIa(data);
    pintarFichaRevisionIa(data);
    setText("estadoRecalibracionIa", formatearEstadoRecalibracionIa(data.estado_recalibracion));
    setText("recomendacionIa", data.recomendaciones || "-");
    setText("guionIa", data.guion_sugerido || "-");

    pintarEvaluacionCalidad(data.evaluacion_calidad_lista || []);
    pintarResumenSegmentos(data.evaluacion_calidad_lista || []);
    const evaluacionSgc = Array.isArray(data.evaluacion_calidad_lista) && data.evaluacion_calidad_lista.length
        ? data.evaluacion_calidad_lista
        : (Array.isArray(data.evaluacion_calidad) ? data.evaluacion_calidad : []);
    pintarCabeceraFichaSgcIa(data);
    pintarFichaAuditoriaSgcIa(evaluacionSgc);
    pintarCierreFichaSgcIa(data);
    pintarHabilidadesBlandas(data.habilidades_blandas_lista || habilidadesBlandasDesdeEvaluacionIa(data.evaluacion_calidad_lista || []));
    pintarLista("fortalezasIa", data.fortalezas_lista || []);
    pintarLista("alertasIa", data.alertas_lista || []);
    pintarPuntosCriticos(data.puntos_criticos_lista || []);
    pintarTopCriticosIa(data.puntos_criticos_lista || []);
    pintarEvidenciasClaveIa(data.evidencias_clave_lista || []);
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
    const scoreIa = scoreIaPreliminarResumenIa(data);
    const scoreFinal = scoreValidadoResumenIa(data);
    const riesgo = formatearRiesgoVisibleIa(data.nivel_oportunidad_mejora || data.nivel_riesgo);
    const errorCritico = Boolean(data.error_critico || data.falta_anulante || Number(data.total_puntos_criticos || 0) > 0);
    const revision = estadoRevisionEvaluacionIa(data);

    setText("detalleBreadcrumbIa", `Evaluaciones / Evaluación #${id}`);
    setText("detalleTituloIa", "Ficha de evaluación");
    setText("detalleSubtituloIa", `Llamada del ${formatoFecha(fecha)} · ${data.cartera || "Sin cartera"}`);
    setText("resultadoNivelIa", riesgo);
    setText("revisionHumanaBadgeIa", data.requiere_revision_humana ? "Requiere revisión humana" : revision.texto);
    const revisionBadge = document.getElementById("revisionHumanaBadgeIa");
    if (revisionBadge) revisionBadge.className = `evaluation-badge ${data.requiere_revision_humana ? "warn" : revision.clase}`;

    const meta = document.getElementById("detalleMetaIa");
    if (meta) {
        meta.innerHTML = [
            ["Tipo de llamada", tipoLlamadaVisibleIa(data)],
            ["Agente", agente],
            ["Score IA", scoreIa == null ? "Sin score" : `${scoreIa.toFixed(1)}%`],
            ["Score final", scoreFinal == null ? "Pendiente" : `${scoreFinal.toFixed(1)}%`],
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
    pintarDimensionesFichaIa(data.evaluacion_calidad_lista || [], data);
    pintarHallazgosAcordeonIa(data.evaluacion_calidad_lista || [], data);
    limpiarDecisionSupervisorIa(data);
    actualizarDecisionSupervisorIa();
}

function pintarAudioYTranscripcionFichaIa(data = {}) {
    const wrap = document.getElementById("audioPlayerWrapIa");
    const audioUrl = data.audio_url || data.url_audio || "";
    const duracion = data.duracion_segundos ? formatoDuracionIa(Number(data.duracion_segundos)) : "Duración no disponible";
    setText("audioDetalleMetaIa", `${data.archivo_nombre || "Audio"} · ${duracion}`);
    const diarizacion = tieneDiarizacionRealIa(data);
    setText("confianzaTranscripcionIa", diarizacion
        ? `Transcripción con separación de interlocutores · Confianza: ${formatearConfianzaEvaluacionIa(data.confianza_evaluacion || data.calidad_transcripcion)}`
        : "Transcripción sin separación de interlocutores · Confianza: BAJA · Requiere revisión humana en criterios dependientes del hablante.");
    if (wrap) {
        wrap.innerHTML = audioUrl
            ? `<audio id="audioRevisionIa" controls preload="metadata" src="${escapeHtml(audioUrl)}"></audio>`
            : `<div class="audio-unavailable"><strong>Audio pendiente de integración</strong><span>El backend guarda la ruta del archivo, pero aún no expone una URL segura para reproducirlo desde la ficha.</span></div>`;
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
        <div><span>Resultado de llamada</span><strong>${escapeHtml(data.resultado_gestion || "Sin información")}</strong></div>
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
    const rows = items.slice(0, 2).map(item => {
        const label = [item.categoria, item.tipificacion].filter(Boolean).join(" - ") || "Tipificación sugerida";
        const confianza = item.confianza_porcentaje != null ? ` · ${Number(item.confianza_porcentaje).toFixed(0)}%` : "";
        return `${label}${confianza}`;
    });
    return `
        <div class="classification-wide">
            <span>Tipificaciones sugeridas IA</span>
            <strong>${rows.map(escapeHtml).join("<br>")}</strong>
        </div>
    `;
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
    const nombres = ["Cumplimiento", "Diagnóstico", "Gestión de solución", "Cierre verificable", "Experiencia y ética"];
    const segmentos = new Map();
    items.forEach(raw => {
        const item = itemSgcIa(raw);
        const resultado = String(item.resultado || "").toLowerCase();
        const segmento = formatearSegmentoIa(item.segmento || item.segmento_copc || "Sin segmento");
        const actual = segmentos.get(segmento) || { peso: 0, nota: 0, total: 0, noAplica: 0, revision: 0 };
        actual.total += 1;
        if (item.aplica === false || resultado.includes("no aplica") || resultado.includes("no evaluable") || resultado.includes("revision") || resultado.includes("revisión")) {
            actual.noAplica += 1;
        } else {
            actual.peso += Number(item.peso || 0);
            actual.nota += Number(item.nota || 0);
        }
        if (String(item.resultado || "").toLowerCase().includes("revision")) actual.revision += 1;
        segmentos.set(segmento, actual);
    });
    el.innerHTML = nombres.map(nombre => {
        const item = segmentos.get(nombre);
        const score = item && item.peso ? (item.nota / item.peso) * 100 : null;
        const estado = !item ? "No evidenciado" : item.total === item.noAplica ? "No aplica" : item.revision ? "Revisión humana" : score >= 85 ? "Cumple" : score >= 60 ? "Parcial" : "No cumple";
        const clase = estado.includes("Cumple") ? "ok" : estado.includes("Parcial") ? "warn" : estado.includes("No aplica") || estado.includes("No evidenciado") ? "info" : "risk";
        const preliminar = esEvaluacionValidadaIa(data) ? "Score validado" : "Score IA preliminar";
        return `
            <article class="${clase}">
                <span>${escapeHtml(nombre)}</span>
                <strong>${score == null ? estado : `${score.toFixed(0)}%`}</strong>
                <div class="summary-progress"><i style="width:${score == null ? 0 : Math.max(3, Math.min(100, score))}%"></i></div>
                <small>${escapeHtml(preliminar)} · ${escapeHtml(estado)}</small>
            </article>
        `;
    }).join("");
}

function pintarHallazgosAcordeonIa(items = [], data = {}) {
    const el = document.getElementById("hallazgosAcordeonIa");
    if (!el) return;
    const normalizados = items.map(itemSgcIa).map(normalizarHallazgoFichaIa);
    const rowsBase = normalizados.filter(item => {
        const cal = String(item.calificacion || item.resultado || "").toLowerCase();
        if (cal.includes("no aplica")) return false;
        return cal.includes("no cumple") || cal.includes("no evidenciado") || cal.includes("parcial") || item.requiere_feedback || item.requiere_coaching;
    });
    const { rows, duplicados } = deduplicarHallazgosFichaIa(rowsBase);
    const grupos = SGC_GRUPOS_IA.map(grupo => ({ grupo, rows: rows.filter(item => item.grupo_error_sgc === grupo) }));
    const totalCriticos = rows.filter(esHallazgoCriticoFichaIa).length;
    const totalNoCriticos = rows.length - totalCriticos;
    const maxIndex = Math.max(0, grupos.reduce((best, grupo, index) => criticidadGrupoIa(grupo.rows) > criticidadGrupoIa(grupos[best]?.rows || []) ? index : best, 0));
    auditoriaFichaIa = {
        criterio: "factor_sgc válido; fallback item COPC",
        resultado: "calificacion; fallback resultado",
        grupo: "grupo_error_sgc normalizado a los 4 grupos SGC/PEC",
        grupos: Object.fromEntries(grupos.map(grupo => [grupo.grupo, grupo.rows.length])),
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
        filtros.innerHTML = `
            <button class="active" type="button" data-findings-filter="todos" onclick="filtrarHallazgosFichaIa('todos')">Todos ${formatoNumero(rows.length)}</button>
            <button type="button" data-findings-filter="criticos" onclick="filtrarHallazgosFichaIa('criticos')">Críticos ${formatoNumero(totalCriticos)}</button>
            <button type="button" data-findings-filter="no-criticos" onclick="filtrarHallazgosFichaIa('no-criticos')">No críticos ${formatoNumero(totalNoCriticos)}</button>
        `;
    }
    el.innerHTML = grupos.map(({ grupo, rows: grupoRows }, index) => `
        <section class="finding-group ${index === maxIndex ? "" : "collapsed"}" data-critical-count="${grupoRows.filter(esHallazgoCriticoFichaIa).length}" data-noncritical-count="${grupoRows.filter(item => !esHallazgoCriticoFichaIa(item)).length}">
            <button type="button" class="finding-group-head" onclick="toggleHallazgoGrupoIa(this)">
                <span>${escapeHtml(grupo.toUpperCase())}</span>
                <b>${formatoNumero(grupoRows.length)}</b>
            </button>
            <div class="finding-group-body">
                ${grupoRows.length ? grupoRows.map(item => renderHallazgoFichaIa(item, data)).join("") : `<div class="empty-segment">Sin hallazgos registrados para este grupo.</div>`}
            </div>
        </section>
    `).join("");
}

function renderHallazgoFichaIa(item = {}, data = {}) {
    const resultado = resultadoHallazgoFichaIa(item);
    const momento = timestampValidoIa(item.momento || item.timestamp) ? (item.momento || item.timestamp) : "";
    const momentoParam = encodeURIComponent(momento);
    const criterio = criterioHallazgoIa(item);
    const itemParam = encodeURIComponent(criterio);
    const audioDisponible = Boolean(data.audio_url || data.url_audio);
    const evidenciaTemporal = audioDisponible && timestampValidoIa(momento);
    const criteriosRelacionados = item.criterios_relacionados?.length || 1;
    const hallazgoBase = item.hallazgo || item.motivo || "-";
    const hallazgoTexto = criteriosRelacionados > 1
        ? `${hallazgoBase} · ${criteriosRelacionados} criterios relacionados`
        : hallazgoBase;
    return `
        <article class="finding-row" data-critical="${esHallazgoCriticoFichaIa(item) ? "1" : "0"}">
            <div><span>Criterio</span><strong>${escapeHtml(criterio)}</strong>${criteriosRelacionados > 1 ? `<small>${criteriosRelacionados} criterios relacionados</small>` : ""}</div>
            <div><span>Estado</span>${badgeResultadoCalidadIa(resultado)}</div>
            <div><span>Evidencia</span><p>${escapeHtml(item.evidencia || "Sin evidencia registrada.")}</p><small>${escapeHtml(momento || "Timestamp no disponible")}</small></div>
            <div><span>Hallazgo</span><p>${escapeHtml(hallazgoTexto)}</p></div>
            <div><span>Recomendación</span><p>${escapeHtml(item.recomendacion || "-")}</p></div>
            <div class="finding-actions">
                <button class="btn-light btn-small" type="button" ${evidenciaTemporal ? `onclick="irAEvidenciaAudioIa('${momentoParam}', true)"` : "disabled title=\"Evidencia temporal no disponible\""}>Escuchar evidencia</button>
                <button class="btn-light btn-small editable-criteria-action" type="button" onclick="prepararRecalibracionItemIa('${itemParam}', true)" disabled>Editar resultado</button>
            </div>
        </article>
    `;
}

function normalizarHallazgoFichaIa(item = {}) {
    const base = { ...item };
    base.grupo_error_sgc = normalizarGrupoSgcFichaIa(base.grupo_error_sgc, base);
    base.factor_sgc = criterioHallazgoIa(base);
    base.calificacion = resultadoHallazgoFichaIa(base);
    return base;
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
        item.criterio,
        item.nombre_criterio,
        item.item_copc,
        itemCopcVisibleIa(item),
        item.item,
    ];
    for (const candidato of candidatos) {
        const texto = String(candidato || "").trim();
        if (texto && !/^(no aplica|na|n\/a|-|null|undefined)$/i.test(texto)) return texto;
    }
    return "Criterio no identificado";
}

function resultadoHallazgoFichaIa(item = {}) {
    const resultado = String(item.calificacion || item.resultado || "").trim();
    if (/no aplica/i.test(resultado)) return "No aplica";
    if (/no evidenciado/i.test(resultado)) return "No evidenciado";
    if (/no cumple/i.test(resultado)) return "No cumple";
    if (/parcial/i.test(resultado)) return "Parcial";
    if (/cumple/i.test(resultado)) return "Cumple";
    return normalizarCalificacionItemIa(item);
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
    const grupo = String(item.grupo_error_sgc || "").toLowerCase();
    return resultado.includes("no cumple") || resultado.includes("no evidenciado") || grupo.includes("crítico") || grupo.includes("critico");
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
    const intervenciones = parseTranscripcionFichaIa(texto, tipo);
    if (!intervenciones.length) {
        el.innerHTML = `<div class="empty-segment">Transcripción no disponible.</div>`;
        return;
    }
    el.innerHTML = intervenciones.map(item => {
        const tieneTimestamp = timestampValidoIa(item.momento);
        const tieneHablante = item.hablante && item.hablante !== "SIN DIARIZACIÓN";
        return `
        <article class="transcript-line ${!tieneTimestamp ? "no-timestamp" : ""} ${!tieneHablante ? "no-speaker" : ""}">
            ${tieneTimestamp ? `<button type="button" onclick="irAEvidenciaAudioIa('${encodeURIComponent(item.momento)}', true)">${escapeHtml(item.momento)}</button>` : ""}
            ${tieneHablante ? `<span class="${item.hablante === "CLIENTE" ? "client" : item.hablante === "AGENTE" ? "agent" : "neutral"}">${escapeHtml(item.hablante)}</span>` : ""}
            <p>${escapeHtml(item.texto)}</p>
        </article>
    `;
    }).join("");
}

function parseTranscripcionFichaIa(texto = "", tipo = "limpia") {
    const diarizacion = tieneDiarizacionRealIa(resultadoActualIa || {});
    const lineas = String(texto || "").split(/\r?\n+/).map(x => x.trim()).filter(Boolean);
    const base = lineas.length ? lineas : String(texto || "").split(/(?<=[.!?])\s+/).map(x => x.trim()).filter(Boolean);
    return base.slice(0, tipo === "limpia" ? 12 : 80).map((linea, index) => {
        const momento = linea.match(/(?:\b|^)(\d{1,2}:\d{2}(?::\d{2})?)(?:\b|$)/)?.[1] || "No disponible";
        const speakerMatch = linea.match(/^(agente|asesor|cliente|titular|deudor|interlocutor)\s*[:\-]/i);
        const hablante = diarizacion && speakerMatch
            ? (/cliente|titular|deudor|interlocutor/i.test(speakerMatch[1]) ? "CLIENTE" : "AGENTE")
            : "SIN DIARIZACIÓN";
        const limpio = linea
            .replace(/^(agente|asesor|cliente|titular|deudor|interlocutor)\s*[:\-]\s*/i, "")
            .replace(/(?:\b|^)\d{1,2}:\d{2}(?::\d{2})?(?:\b|$)/, "")
            .trim();
        return { momento, hablante, texto: limpio || linea, index };
    });
}

function tieneDiarizacionRealIa(data = {}) {
    return Array.isArray(data.transcripcion_diarizada) && data.transcripcion_diarizada.length > 0;
}

function formatoDuracionIa(segundos) {
    if (!Number.isFinite(segundos) || segundos <= 0) return "Duración no disponible";
    const min = Math.floor(segundos / 60);
    const sec = Math.floor(segundos % 60);
    return `${String(min).padStart(2, "0")}:${String(sec).padStart(2, "0")}`;
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

function toggleHallazgoGrupoIa(btn) {
    btn?.closest(".finding-group")?.classList.toggle("collapsed");
}

function prepararRecalibracionItemIa(item, encoded = false) {
    abrirRecalibracionIa();
    setValue("itemRecalibracionIa", encoded ? decodeURIComponent(item || "") : item || "");
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
    setValue("estadoRevisionIa", decision === "modificar" ? "REVISADO" : "REVISADO");
    await guardarRevisionIa();
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
    const texto = String(item?.item || "-");
    const prefijo = texto.match(/^\s*(\d+\.\d+)/)?.[1];
    const match = ITEM_COPC_DISPLAY_IA.find(([codigo]) => codigo === prefijo);
    return match ? match[1] : texto;
}

function itemSgcIa(item = {}) {
    const clasif = clasificarSgcItemIa(item);
    const grupo = esValorNoAplicableIa(item.grupo_error_sgc) ? clasif.grupo : (item.grupo_error_sgc || clasif.grupo);
    const factor = esValorNoAplicableIa(item.factor_sgc) ? clasif.factor : (item.factor_sgc || clasif.factor);
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
    if (resultado.includes("no aplica")) return "No aplica";
    if (resultado.includes("parcial")) return "Parcial";
    if (resultado.includes("no cumple") || resultado.includes("no evidenciado")) return "No cumple";
    if (resultado.includes("cumple")) return "Cumple";
    return Number(item.nota || 0) === 0 ? "No cumple" : "Parcial";
}

function requiereFeedbackItemIa(item = {}) {
    const cal = String(item.calificacion || "").toLowerCase();
    return cal && !["cumple", "no aplica"].includes(cal);
}

function requiereCoachingItemIa(item = {}) {
    const cal = String(item.calificacion || "").toLowerCase();
    const grupo = String(item.grupo_error_sgc || "").toLowerCase();
    return cal !== "cumple" && grupo.includes("cumplimiento");
}

function itemsSgcDetalleIa(row = {}) {
    const items = row.evaluacion_calidad_lista || [];
    if (items.length) return items.map(itemSgcIa);
    return (row.brechas_items || []).map(itemSgcIa);
}

function resumenSgcDesdeItemsIa(items = []) {
    const resumen = Object.fromEntries(SGC_GRUPOS_IA.map(grupo => [grupo, 0]));
    items.forEach(raw => {
        const item = itemSgcIa(raw);
        const cal = String(item.calificacion || "").toLowerCase();
        if (!esValorNoAplicableIa(item.grupo_error_sgc) && !["cumple", "no aplica"].includes(cal)) {
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
                        <td><button class="historial-action" type="button" onclick="verAnalisisIa(${Number(row.idFeedback || 0)})">${String(row.estadoCoaching || "").toUpperCase() === "PENDIENTE" ? "Programar" : "Ver"}</button></td>
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
                        <td><button class="historial-action" type="button" onclick="verAnalisisIa(${Number(row.id_feedback || 0)})">${accionCoachingIa(estado)}</button></td>
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
    return tipo || "Por clasificar";
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

function abrirRecalibracionIa() {
    if (!resultadoActualIa?.id_feedback) {
        mostrarMensajeIa("Primero abre o genera un análisis para solicitar recalibración.", "error");
        return;
    }
    setText("recalibracionIdIa", resultadoActualIa.id_feedback || "-");
    const scoreActual = resultadoActualIa.score_final ?? resultadoActualIa.score_normalizado ?? resultadoActualIa.score_calidad;
    setText("recalibracionNotaIa", scoreActual != null ? `${Number(scoreActual).toFixed(1)} / 100` : "-");
    setText("recalibracionNivelIa", formatearRiesgoVisibleIa(resultadoActualIa.nivel_oportunidad_mejora));
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
        mostrarMensajeIa("Primero abre o genera un análisis para solicitar recalibración.", "error");
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
        if (!response.ok) throw new Error(data.detail || "No se pudo solicitar la recalibración.");

        resultadoActualIa = data.feedback || resultadoActualIa;
        setText("estadoRecalibracionIa", "PENDIENTE");
        setText("trazaRevisionIa", resultadoActualIa.estado_revision || "PENDIENTE");
        cerrarRecalibracionIa();
        await cargarHistorialIa();
        mostrarMensajeIa("Solicitud de recalibración registrada con trazabilidad.", "ok");
    } catch (error) {
        mostrarMensajeIa(error.message || "Error solicitando recalibración.", "error");
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
        const grupo = item.grupo_error_sgc || "No aplica";
        const key = `${grupo}||${segmento}`;
        const actual = grupos.get(key) || { grupo, segmento, peso: 0, nota: 0, brechas: 0, items: [] };
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
                    <td class="matrix-group-cell" rowspan="${grupo.items.length}">
                        <strong>${escapeHtml(grupo.grupo)}</strong>
                    </td>
                    <td class="matrix-segment-cell ${porcentaje < 60 ? "is-critical" : porcentaje < 85 ? "is-partial" : "is-ok"}" rowspan="${grupo.items.length}">
                        <span>Segmento COPC</span>
                        <strong>${escapeHtml(grupo.segmento)}</strong>
                        <small>${formatoPeso(grupo.nota)} / ${formatoPeso(grupo.peso)} · ${escapeHtml(estado)} · ${formatoNumero(grupo.brechas)} brecha(s)</small>
                    </td>
                ` : ""}
                <td class="matrix-item-cell"><strong>${escapeHtml(item.item || "-")}</strong><small>${escapeHtml(item.factor_sgc || "-")}</small></td>
                <td class="matrix-score-cell">${formatoPeso(item.peso)}</td>
                <td class="matrix-score-cell"><strong class="${Number(item.nota || 0) === 0 ? "critical-score" : ""}">${formatoPeso(item.nota)}</strong></td>
                <td>${badgeResultadoCalidadIa(item.resultado)}</td>
                <td><b>Hallazgo</b><p>${escapeHtml(item.hallazgo || "-")}</p></td>
                <td><b>Evidencia</b><p>${escapeHtml(item.evidencia || "-")}</p></td>
                <td><b>Recomendación</b><p>${escapeHtml(item.recomendacion || "-")}</p></td>
            </tr>
        `).join("");
    }).join("");

    contenedor.innerHTML = `
        <table class="quality-grouped-table">
            <thead>
                <tr>
                    <th>Grupo SGC/PEC</th>
                    <th>Segmento COPC</th>
                    <th>Ítem COPC</th>
                    <th>Peso</th>
                    <th>Nota</th>
                    <th>Resultado</th>
                    <th>Hallazgo</th>
                    <th>Evidencia</th>
                    <th>Recomendación</th>
                </tr>
            </thead>
            <tbody>${filas}</tbody>
        </table>
    `;
}

function badgeResultadoCalidadIa(resultado) {
    const texto = String(resultado || "-");
    const key = texto.toLowerCase();
    let clase = "neutro";
    if (key.includes("cumple") && !key.includes("no cumple")) clase = "cumple";
    if (key.includes("parcial")) clase = "parcial";
    if (key.includes("no cumple")) clase = "nocumple";
    if (key.includes("no evidenciado")) clase = "noevidenciado";
    if (key.includes("no aplica")) clase = "noaplica";
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
    const items = (data.evaluacion_calidad_lista || []).map(itemSgcIa);
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
    el.innerHTML = `
        <article><span>Evaluación</span><strong>${escapeHtml(data.id_feedback || "-")}</strong></article>
        <article><span>Cartera</span><strong>${escapeHtml(data.cartera || "-")}</strong></article>
        <article><span>Supervisor</span><strong>${escapeHtml(data.supervisor || "-")}</strong></article>
        <article><span>Fecha llamada</span><strong>${escapeHtml(formatoFecha(data.fecha_llamada || data.fecha_creacion))}</strong></article>
        <article><span>Score COPC</span><strong>${score != null ? `${Number(score).toFixed(1)} / 100` : "-"}</strong></article>
        <article><span>Riesgo</span><strong>${escapeHtml(formatearRiesgoVisibleIa(data.nivel_oportunidad_mejora || data.nivel_riesgo))}</strong></article>
        <p>Base técnica: matriz COPC adaptada a cobranza telefónica. Lectura gerencial: homologación SGC/PEC para clasificar hallazgos y orientar feedback o coaching.</p>
    `;
}

function pintarCierreFichaSgcIa(data = {}) {
    const items = Array.isArray(data.evaluacion_calidad_lista) ? data.evaluacion_calidad_lista : [];
    const prioridad = seleccionarFeedbackAlarmanteSgcIa(items, data);
    setText("fichaFeedbackSgcIa", prioridad || data.recomendaciones || data.recomendacion_feedback_supervisor || "Sin feedback crítico sugerido registrado.");
    setText("fichaObservacionSgcIa", data.comentario_feedback || data.comentario_supervisor || "Sin observación del supervisor registrada.");
}

function calificacionCortaSgcIa(value) {
    const key = String(value || "").toLowerCase();
    if (key.includes("no aplica")) return "NA";
    if (key.includes("parcial")) return "P";
    if (key.includes("no cumple") || key.includes("no evidenciado")) return "NC";
    if (key.includes("cumple")) return "C";
    return "-";
}

function claseFilaFichaSgcIa(item) {
    const key = String(item.calificacion || "").toLowerCase();
    if (key.includes("no cumple") || key.includes("no evidenciado")) return "is-error";
    if (key.includes("parcial")) return "is-partial";
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
    const clase = key === "NC" ? "nocumple" : key === "P" ? "parcial" : key === "C" ? "cumple" : "noaplica";
    const textos = { C: "C - Cumple", NC: "NC - No cumple", P: "P - Parcial", NA: "NA - No aplica" };
    return `<span class="audit-sgc-badge ${clase}" title="${escapeHtml(completa || "-")}">${escapeHtml(textos[key] || "-")}</span>`;
}

function prioridadFichaSgcIa(item = {}) {
    const cal = String(item.calificacion_corta || "").toUpperCase();
    if (cal === "NC") return 0;
    if (cal === "P") return 1;
    if (cal === "NA") return 3;
    return 2;
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

function pintarFichaAuditoriaSgcIa(items) {
    const el = document.getElementById("fichaAuditoriaSgcIa");
    if (!el) return;
    const rows = itemsFichaAuditoriaSgcIa(items);
    const esBrecha = item => ["NC", "P"].includes(String(item.calificacion_corta || "").toUpperCase());
    if (!rows.length) {
        el.innerHTML = `<div class="empty-report-state"><strong>Sin ficha SGC/PEC disponible.</strong><small>La evaluación no contiene ítems suficientes para construir la ficha de auditoría.</small></div>`;
        return;
    }
    el.innerHTML = SGC_GRUPOS_IA.map(grupo => {
        const grupoRows = rows.filter(item => item.grupo_auditoria_sgc === grupo);
        const brechas = grupoRows.filter(esBrecha);
        const visibles = brechas.length
            ? brechas.sort((a, b) => prioridadFichaSgcIa(a) - prioridadFichaSgcIa(b)).slice(0, 5)
            : grupoRows.slice(0, 2);
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
                                    <td><strong>${escapeHtml(item.factor_auditoria_sgc || "-")}</strong></td>
                                    <td>${badgeFichaCalificacionSgcIa(item.calificacion_corta, item.calificacion)}</td>
                                    <td class="${["NC", "P"].includes(item.calificacion_corta) ? "audit-sgc-focus" : ""}">${escapeHtml(item.motivo || item.hallazgo || "-")}</td>
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
    if (tab === "matriz") setText("btnDetalleCalidadIa", "Ver matriz completa");
}

function pintarEvidenciasClaveIa(items) {
    const el = document.getElementById("evidenciasClaveIa");
    if (!el) return;
    if (!items.length) {
        el.innerHTML = `<div class="empty-segment">Sin evidencias clave registradas.</div>`;
        return;
    }
    const visibles = items.slice(0, 6);
    el.innerHTML = visibles.map(item => `
        <article class="evidence-card">
            <div><span>${escapeHtml(item.tipo || "Evidencia")}</span><strong>${escapeHtml(item.momento || "No disponible")}</strong></div>
            <div class="evidence-meta">
                ${badgeGerencialIa(formatearSegmentoIa(item.segmento_copc || item.segmento || "-"), "bajo")}
                ${badgeSgcIa(item.grupo_error_sgc || clasificarSgcItemIa(item).grupo)}
                ${badgeGerencialIa(item.severidad || "MEDIA", claseSeveridadIa(item.severidad) === "sev-high" ? "alto" : "medio")}
            </div>
            <small><b>Factor:</b> ${escapeHtml(item.factor_sgc || clasificarSgcItemIa(item).factor || "-")}</small>
            <p>${escapeHtml(item.frase_textual || "No disponible")}</p>
            <small>${escapeHtml(item.interpretacion || "-")}</small>
            <small><b>Impacto:</b> ${escapeHtml(item.impacto || "-")} <b>Recomendación:</b> ${escapeHtml(item.recomendacion || "-")}</small>
        </article>
    `).join("");
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
            <p>${escapeHtml(tieneEvidencia ? (item.interpretacion || data.objecion_principal || "Sin interpretacion adicional.") : "Revisar matriz COPC o transcripcion para mayor detalle.")}</p>
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
    const recalibraciones = data.recalibraciones_lista || [];
    const scoreIa = data.score_calidad_ia != null ? Number(data.score_calidad_ia) : null;
    const scoreFinal = (data.score_final ?? data.score_calidad) != null ? Number(data.score_final ?? data.score_calidad) : null;
    const diferencia = scoreIa != null && scoreFinal != null ? Math.abs(scoreFinal - scoreIa).toFixed(1) : "-";
    const cards = [
        ["Nota IA inicial", scoreIa != null ? `${scoreIa.toFixed(1)} / 100` : "-"],
        ["Nota final validada", scoreFinal != null ? `${scoreFinal.toFixed(1)} / 100` : "-"],
        ["Diferencia", diferencia === "-" ? "-" : `${diferencia} pts`],
        ["Estado recalibración", formatearEstadoRecalibracionIa(data.estado_recalibracion)],
        ["Confianza evaluación", formatearConfianzaEvaluacionIa(data.confianza_evaluacion)],
        ["Revisión humana", data.requiere_revision_humana ? "Sí" : "No"],
    ];
    el.innerHTML = `
        <div class="calibration-detail-grid">
            ${cards.map(row => `<article><span>${escapeHtml(row[0])}</span><strong>${escapeHtml(row[1])}</strong></article>`).join("")}
        </div>
        <section class="detail-card calibration-reason">
            <h4>Motivo y resolución</h4>
            <p><strong>Motivo:</strong> ${escapeHtml(data.motivo_revision || "-")}</p>
            <p><strong>Comentario resolución:</strong> ${escapeHtml(data.comentario_resolucion || "-")}</p>
            <p><strong>Estado:</strong> ${escapeHtml(formatearEstadoRecalibracionIa(data.estado_recalibracion))}</p>
        </section>
        <div class="calibration-list">
            ${recalibraciones.length ? recalibraciones.map(item => `
                <article>
                    <strong>${escapeHtml(item.estado || "PENDIENTE")} - ${escapeHtml(item.item_cuestionado || "Evaluación general")}</strong>
                    <span>Inicial: ${escapeHtml(item.score_ia ?? "-")} | Sugerida: ${escapeHtml(item.score_sugerido ?? "-")} | Final: ${escapeHtml(item.score_final ?? "-")}</span>
                    <p>${escapeHtml(item.motivo || "-")}</p>
                </article>
            `).join("") : `<div class="empty-segment">Sin solicitudes de recalibración.</div>`}
        </div>
    `;
}

function pintarHistorialDetalleIa(items) {
    const el = document.getElementById("historialDetalleListaIa");
    if (!el) return;
    const base = construirHistorialBaseIa(resultadoActualIa || {});
    const rows = [...base, ...items];
    if (!rows.length) {
        el.innerHTML = `<div class="empty-segment">Sin historial adicional. Cuando se guarde la revisión o recalibración, se mostrará la trazabilidad aquí.</div>`;
        return;
    }
    el.innerHTML = `
        <div class="detail-timeline">
            ${rows.map(item => `
                <article>
                    <span>${formatoFecha(item.fecha)}</span>
                    <strong>${escapeHtml(item.accion || "-")}</strong>
                    <p>${escapeHtml(item.descripcion || item.comentario || "-")}</p>
                    <small>${escapeHtml(item.usuario || "-")} ${item.valor_anterior || item.valor_nuevo ? `| Antes: ${escapeHtml(item.valor_anterior || "-")} | Nuevo: ${escapeHtml(item.valor_nuevo || "-")}` : ""}</small>
                </article>
            `).join("")}
        </div>
    `;
}

function construirHistorialBaseIa(data) {
    if (!data || !data.id_feedback) return [];
    return [
        {
            fecha: data.fecha_creacion || data.fecha_llamada,
            accion: "Evaluación creada",
            usuario: data.supervisor || "-",
            descripcion: `Audio registrado: ${data.archivo_nombre || "-"}`,
        },
        {
            fecha: data.fecha_creacion || data.fecha_llamada,
            accion: "Análisis IA generado",
            usuario: "IA",
            descripcion: `Score final: ${(data.score_final ?? data.score_calidad) != null ? Number(data.score_final ?? data.score_calidad).toFixed(1) : "-"} / 100`,
        },
        {
            fecha: data.fecha_revision || data.fecha_creacion || data.fecha_llamada,
            accion: "Revisión supervisor",
            usuario: data.supervisor || "-",
            descripcion: `Estado: ${data.estado_revision || "PENDIENTE"}`,
        },
    ];
}

function cargarCoachingEnFormulario(data) {
    setValue("estadoCoachingIa", data.estado_coaching || "PENDIENTE");
    setValue("fechaCoachingIa", data.fecha_coaching ? String(data.fecha_coaching).slice(0, 16) : "");
    setValue("compromisoAgenteIa", data.compromiso_agente || "");
    setValue("resultadoCoachingIa", data.resultado_coaching || "");
    actualizarAyudaCoachingIa(data.estado_coaching || "PENDIENTE");
}

function actualizarAyudaCoachingIa(estado) {
    const ayuda = document.getElementById("ayudaCoachingIa");
    const btn = document.getElementById("btnGuardarCoachingIa");
    const normalizado = String(estado || "PENDIENTE").toUpperCase();
    if (btn) btn.textContent = ["REALIZADO", "CERRADO"].includes(normalizado) ? "Guardar cierre de coaching" : "Guardar coaching";
    if (ayuda) ayuda.textContent = ["REALIZADO", "CERRADO"].includes(normalizado)
        ? "Al guardar, el coaching quedara marcado como realizado/cerrado segun el estado seleccionado."
        : "Para cerrar el coaching, cambia el estado a Realizado o Cerrado y guarda el seguimiento.";
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
        formData.append("feedback_supervisor", valor("comentarioFeedbackIa"));
        formData.append("compromiso_agente", valor("compromisoAgenteIa"));
        formData.append("fecha_programada", valor("fechaCoachingIa"));
        formData.append("resultado", valor("resultadoCoachingIa"));
        formData.append("responsable", localStorage.getItem("agente") || localStorage.getItem("dni") || "SIN_USUARIO");
        const response = await fetchIa(`${IA_FEEDBACK_BASE}/${idFeedback}/coaching`, {
            method: "POST",
            body: formData,
        }, 30000);
        const data = await leerJsonSeguro(response);
        if (!response.ok) throw new Error(data.detail || "No se pudo guardar el coaching.");
        resultadoActualIa = data;
        pintarHistorialDetalleIa(data.historial_lista || []);
        pintarCalibracionDetalleIa(data);
        await cargarHistorialIa();
        await cargarReporteriaIa();
        mostrarMensajeIa("Coaching guardado con trazabilidad.", "ok");
    } catch (error) {
        mostrarMensajeIa(error.message || "Error guardando coaching.", "error");
    } finally {
        btn.disabled = false;
        btn.textContent = "Guardar coaching";
    }
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
    cargarReporteriaIa();
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
    const evaluacion = Array.isArray(resultadoActualIa?.evaluacion_calidad_lista) && resultadoActualIa.evaluacion_calidad_lista.length
        ? resultadoActualIa.evaluacion_calidad_lista
        : (Array.isArray(resultadoActualIa?.evaluacion_calidad) ? resultadoActualIa.evaluacion_calidad : []);
    if (!evaluacion.length) {
        mostrarMensajeIa("No hay datos suficientes para exportar la ficha SGC/PEC.", "error");
        return;
    }
    const filas = itemsFichaAuditoriaSgcIa(evaluacion);
    const csvRows = [
        ["FICHA DE ERRORES SGC/PEC"],
        ["audio", resultadoActualIa?.archivo_nombre || "-"],
        ["supervisor", resultadoActualIa?.supervisor || "-"],
        ["score_final", Number(resultadoActualIa?.score_final ?? resultadoActualIa?.score_calidad ?? 0).toFixed(1)],
        [],
        ["grupo_sgc", "factor", "calificacion_corta", "calificacion", "motivo", "evidencia", "recomendacion"],
        ...filas.map(item => [
            item.grupo_auditoria_sgc || "",
            item.factor_auditoria_sgc || "",
            item.calificacion_corta || "",
            item.calificacion || "",
            item.motivo || item.hallazgo || "",
            item.evidencia || "",
            item.recomendacion || "",
        ])
    ];
    descargarCsvIa(csvRows, `ficha_sgc_pec_${new Date().toISOString().slice(0, 10)}.csv`);
    mostrarMensajeIa("Ficha SGC/PEC exportada correctamente.", "ok");
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

