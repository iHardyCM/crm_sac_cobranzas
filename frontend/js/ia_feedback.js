const IA_FEEDBACK_BASE = obtenerBaseUrlIaFeedback();

let historialIa = [];
let iaAudioConfig = {
    formatos: ["MP3", "WAV", "M4A", "OGG"],
    extensiones: [".mp3", ".wav", ".m4a", ".ogg"],
    maxMb: 25,
};

document.addEventListener("DOMContentLoaded", () => {
    if (typeof exigirSesion === "function" && !exigirSesion()) return;

    prepararFormularioIa();
    cargarConfigIa();
    cargarCarterasIa();
    cargarHistorialIa();
    cargarPromptIa();
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
        comentario.placeholder = "Ejemplo: llamada con cliente que solicita descuento; revisar si el asesor aplico negociacion escalonada y cerro las 3C.";
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
        mostrarMensajeIa("Audio registrado. Generando analisis simulado...", "ok");

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
        limpiarFormularioBasicoIa();
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
        { idcartera: 126, cartera: "Compartamos" },
        { idcartera: 128, cartera: "Compartamos" },
        { idcartera: 133, cartera: "Compartamos" },
        { idcartera: 124, cartera: "Compartamos Castigo" },
        { idcartera: 144, cartera: "Compartamos Castigo" },
        { idcartera: 139, cartera: "Crediscotia" },
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
    setText("recomendacionIa", data.recomendaciones || "-");
    setText("guionIa", data.guion_sugerido || "-");

    pintarEvaluacionCalidad(data.evaluacion_calidad_lista || []);
    pintarResumenSegmentos(data.evaluacion_calidad_lista || []);
    pintarLista("fortalezasIa", data.fortalezas_lista || []);
    pintarLista("alertasIa", data.alertas_lista || []);
    pintarPuntosCriticos(data.puntos_criticos_lista || []);
    cargarRevisionEnFormulario(data);
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

        renderResultadoIa(data);
        await cargarHistorialIa();
        mostrarMensajeIa("Revision guardada correctamente.", "ok");
    } catch (error) {
        mostrarMensajeIa(error.message || "Error guardando revision.", "error");
    } finally {
        btn.disabled = false;
        btn.textContent = "Guardar revision";
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
        ? items.map(item => `<li>${escapeHtml(item)}</li>`).join("")
        : `<li>-</li>`;
}

function pintarEvaluacionCalidad(items) {
    const tbody = document.getElementById("evaluacionCalidadIa");
    if (!tbody) return;

    if (!items.length) {
        tbody.innerHTML = `<tr><td colspan="8">Sin evaluacion de calidad registrada.</td></tr>`;
        return;
    }

    tbody.innerHTML = items.map(item => `
        <tr>
            <td>${escapeHtml(item.segmento || "-")}</td>
            <td>${escapeHtml(item.item || "-")}</td>
            <td>${formatoPeso(item.peso)}</td>
            <td><strong>${formatoPeso(item.nota)}</strong></td>
            <td>${escapeHtml(item.resultado || "-")}</td>
            <td>${escapeHtml(item.hallazgo || "-")}</td>
            <td>${escapeHtml(item.evidencia || "-")}</td>
            <td>${escapeHtml(item.recomendacion || "-")}</td>
        </tr>
    `).join("");
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
            <article class="segment-card">
                <div>
                    <span>${escapeHtml(item.segmento)}</span>
                    <strong>${formatoPeso(item.nota)} / ${formatoPeso(item.peso)}</strong>
                </div>
                <div class="segment-bar"><i style="width:${Math.max(0, Math.min(100, porcentaje))}%"></i></div>
                <small>${escapeHtml(item.observaciones.slice(0, 2).join(" | ") || "Sin observaciones criticas.")}</small>
            </article>
        `;
    }).join("");
}

function toggleDetalleCalidadIa() {
    document.getElementById("detalleCalidadIa")?.classList.toggle("oculto");
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
        tbody.innerHTML = `<tr><td colspan="6">Sin puntos criticos registrados.</td></tr>`;
        return;
    }

    tbody.innerHTML = items.map(item => `
        <tr>
            <td>${escapeHtml(item.segmento || "-")}</td>
            <td>${escapeHtml(item.categoria || "-")}</td>
            <td>${escapeHtml(item.hallazgo || "-")}</td>
            <td>${escapeHtml(item.evidencia || "-")}</td>
            <td>${escapeHtml(item.impacto || "-")}</td>
            <td>${escapeHtml(item.recomendacion || "-")}</td>
        </tr>
    `).join("");
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

function limpiarFormularioBasicoIa() {
    document.getElementById("audioIa").value = "";
    document.getElementById("nombreAudioIa").textContent = "Ningun archivo seleccionado";
}

function mostrarMensajeIa(texto, tipo = "ok") {
    const box = document.getElementById("mensajeIa");
    box.className = `ia-message ${tipo}`;
    box.textContent = texto;
    box.classList.remove("oculto");
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
window.abrirPromptIa = abrirPromptIa;
window.cerrarPromptIa = cerrarPromptIa;
window.mostrarSeccionPromptIa = mostrarSeccionPromptIa;
window.guardarPromptIa = guardarPromptIa;
window.cargarPromptIa = cargarPromptIa;
