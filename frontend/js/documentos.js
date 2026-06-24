// documento.js
const BASE_URL_DOCUMENTOS = `${window.location.protocol}//${window.location.hostname}:8000`;

let documentosResultados = [];
let documentoSeleccionado = null;
let documentosTipos = [];
let documentosCarteras = [];

document.addEventListener("DOMContentLoaded", () => {
    inicializarCatalogosDocumento();
    pintarFechaDocumentoHoy();

    document.getElementById("btnBuscar")?.addEventListener("click", buscarDatosDocumento);
    document.getElementById("btnLimpiar")?.addEventListener("click", limpiarVista);
    document.getElementById("btnGenerar")?.addEventListener("click", generarDocumento);
    document.getElementById("btnDirectorioAgencias")?.addEventListener("click", abrirDirectorioAgencias);
    document.getElementById("btnCerrarDirectorio")?.addEventListener("click", cerrarDirectorioAgencias);
    document.getElementById("btnBuscarAgencia")?.addEventListener("click", cargarDirectorioAgencias);
    document.getElementById("archivoDirectorioAgencias")?.addEventListener("change", importarDirectorioAgencias);
    document.getElementById("buscarAgencia")?.addEventListener("keydown", event => {
        if (event.key === "Enter") cargarDirectorioAgencias();
    });
    document.getElementById("correoFormato")?.addEventListener("change", pintarPreviewCorreo);
    document.getElementById("btnCopiarCorreo")?.addEventListener("click", copiarCorreoPreview);
    document.addEventListener("click", event => {
        const button = event.target.closest("[data-copy-pago-directo]");
        if (button) copiarCorreoPagoDirecto(button.dataset.copyPagoDirecto);
    });
    document.getElementById("documentoCartera")?.addEventListener("change", () => {
        poblarTiposDocumento();
        limpiarCamposGeneracion();
        limpiarSeleccion();
        actualizarModoDocumento();
    });
    document.getElementById("documentoTipo")?.addEventListener("change", () => {
        limpiarCamposGeneracion();
        limpiarSeleccion();
        actualizarModoDocumento();
    });
    document.getElementById("cancelacion")?.addEventListener("input", () => {
        actualizarCondonacion();
        pintarPreviewDocumento();
    });
    document.getElementById("excepcionDocumento")?.addEventListener("change", pintarPreviewDocumento);
    document.querySelectorAll("[data-formato]").forEach(button => {
        button.addEventListener("click", () => seleccionarFormato(button.dataset.formato));
    });
    document.querySelectorAll("input[name='encargadoModo']").forEach(input => {
        input.addEventListener("change", () => {
            actualizarModoEncargado();
            pintarPreviewDocumento();
        });
    });

    [
        "encargadoParticipante",
        "encargadoProvinciaParticipante",
        "encargadoNombreLibre",
        "encargadoDniLibre",
        "encargadoDireccionLibre",
        "encargadoDistritoLibre",
        "encargadoProvinciaLibre",
    ].forEach(id => {
        document.getElementById(id)?.addEventListener("input", pintarPreviewDocumento);
        document.getElementById(id)?.addEventListener("change", pintarPreviewDocumento);
    });

    ["dni", "operacion", "codigoGrupo", "codCreGrupal"].forEach(id => {
        document.getElementById(id)?.addEventListener("keydown", event => {
            if (event.key === "Enter") buscarDatosDocumento();
        });
    });
});


async function inicializarCatalogosDocumento() {
    try {
        const [tiposResponse, carterasResponse] = await Promise.all([
            fetch(`${BASE_URL_DOCUMENTOS}/documentos/tipos`, { cache: "no-store" }),
            fetch(`${BASE_URL_DOCUMENTOS}/documentos/carteras`, { cache: "no-store" }),
        ]);
        const tiposResult = await tiposResponse.json();
        const carterasResult = await carterasResponse.json();

        if (!tiposResponse.ok) {
            throw new Error(tiposResult.detail || "No se pudieron cargar los tipos de documento.");
        }
        if (!carterasResponse.ok) {
            throw new Error(carterasResult.detail || "No se pudieron cargar las carteras.");
        }

        documentosTipos = tiposResult.data || [];
        documentosCarteras = carterasResult.data || [];
        poblarCarterasDocumento();
        poblarTiposDocumento();
        actualizarModoDocumento();
    } catch (error) {
        mostrarEstado(error.message, "error");
    }
}


function poblarCarterasDocumento() {
    const select = document.getElementById("documentoCartera");
    if (!select) return;

    select.innerHTML = documentosCarteras.map(item => (
        `<option value="${escapeAttr(item.id)}" ${item.activo ? "" : "disabled"}>${escapeHtml(item.id)} - ${escapeHtml(item.nombre)}${item.activo ? "" : " (pendiente)"}</option>`
    )).join("");

    if (!select.value && documentosCarteras.some(item => item.id === 133)) {
        select.value = "133";
    }
}


function poblarTiposDocumento() {
    const select = document.getElementById("documentoTipo");
    if (!select) return;

    const cartera = Number(document.getElementById("documentoCartera")?.value || 133);
    const tipos = documentosTipos.filter(item => Number(item.cartera_id || 0) === cartera);
    select.innerHTML = tipos.map(item => (
        `<option value="${escapeAttr(item.id)}">${escapeHtml(item.nombre)}</option>`
    )).join("");
}


function esDocumentoGrupal() {
    return ["cancelacion_grupal", "compromiso_cuota_grupal"].includes(document.getElementById("documentoTipo")?.value);
}


function esDocumentoCuotaGrupal() {
    return document.getElementById("documentoTipo")?.value === "compromiso_cuota_grupal";
}


function esDocumentoCuotaIndividual() {
    return document.getElementById("documentoTipo")?.value === "compromiso_cuota_individual";
}


function esDocumentoCorreoPagoDirecto() {
    return ["correo_pago_directo_cancelacion", "correo_pago_directo_cuota"].includes(document.getElementById("documentoTipo")?.value);
}


function esDocumentoCorreoPagoDirectoCuota() {
    return document.getElementById("documentoTipo")?.value === "correo_pago_directo_cuota";
}


function actualizarModoDocumento() {
    const cancelacionLabel = document.getElementById("cancelacion")?.closest("label");
    cancelacionLabel?.classList.toggle("hidden", esDocumentoGrupal());
    if (cancelacionLabel?.firstChild) {
        cancelacionLabel.firstChild.textContent = esDocumentoCorreoPagoDirectoCuota() ? "Monto de cuota a ingresar\n" : "Cancelacion a ingresar\n";
    }
    document.getElementById("panelGrupal")?.classList.toggle("hidden", !esDocumentoGrupal() || !documentoSeleccionado);
    document.getElementById("thCuotaGrupal")?.classList.toggle("hidden", !esDocumentoCuotaGrupal());
    document.getElementById("thCuotaCalculada")?.classList.toggle("hidden", !esDocumentoCuotaGrupal());
    document.querySelector(".documentos-format-box")?.classList.toggle("hidden", esDocumentoCorreoPagoDirecto());
    document.querySelector(".documentos-exception-box")?.classList.toggle("hidden", esDocumentoCorreoPagoDirecto());
    document.getElementById("btnGenerar")?.classList.toggle("hidden", esDocumentoCorreoPagoDirecto());
    document.querySelector(".documentos-rule")?.classList.toggle("hidden", esDocumentoCorreoPagoDirecto());
    const tituloPersona = document.getElementById("tituloPersonaGrupal");
    if (tituloPersona) tituloPersona.textContent = esDocumentoCuotaGrupal() ? "Datos del fiador" : "Datos del encargado";
    const ayudaMontos = document.getElementById("ayudaMontosGrupales");
    if (ayudaMontos) {
        ayudaMontos.textContent = esDocumentoCuotaGrupal()
            ? "N° Cuota usa Ult_CuotaAtrasada. La cuota se calcula con CT1 + CT11 + CT12 + CT13 + CT14 + CT15. El monto manual debe ser mayor a la cuota, salvo Excepcion."
            : "La columna Cuenta usa CtaCliente de la consulta SQL. Ingresa el monto a pagar por cada operacion.";
    }
    setSummaryLabels();
}


function setSummaryLabels() {
    const summary = document.querySelectorAll(".documentos-summary span");
    if (summary.length < 3) return;

    if (esDocumentoCuotaGrupal()) {
        summary[0].textContent = "Integrantes";
        summary[1].textContent = "Cuota total calculada";
        summary[2].textContent = "Saldo estimado a condonar";
    } else if (esDocumentoCuotaIndividual() || esDocumentoCorreoPagoDirectoCuota()) {
        summary[0].textContent = "Cuota calculada";
        summary[1].textContent = "Deuda total";
        summary[2].textContent = "Saldo estimado a condonar";
    } else if (esDocumentoGrupal()) {
        summary[0].textContent = "Integrantes";
        summary[1].textContent = "Deuda total SQL";
        summary[2].textContent = "Condonacion estimada";
    } else {
        summary[0].textContent = "Mto CancelacionCliente SQL";
        summary[1].textContent = "Deuda total";
        summary[2].textContent = "Condonacion estimada";
    }
}


function pintarFechaDocumentoHoy() {
    const target = document.getElementById("fechaDocumentoHoy");
    if (!target) return;

    target.textContent = new Date().toLocaleDateString("es-PE", {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
    });
}


function obtenerFiltros() {
    return {
        dni: document.getElementById("dni")?.value.trim() || "",
        operacion: document.getElementById("operacion")?.value.trim() || "",
        codigo_grupo: document.getElementById("codigoGrupo")?.value.trim() || "",
        cod_cre_grupal: document.getElementById("codCreGrupal")?.value.trim() || "",
    };
}


async function buscarDatosDocumento() {
    const filtros = obtenerFiltros();

    if (!Object.values(filtros).some(Boolean)) {
        mostrarEstado("Ingresa DNI, operacion, cta grupal o cod grupal para buscar.", "warning");
        return;
    }

    mostrarEstado("Consultando datos del cliente...", "info");
    limpiarSeleccion();

    try {
        const params = new URLSearchParams();
        Object.entries(filtros).forEach(([key, value]) => {
            if (value) params.append(key, value);
        });

        const response = await fetch(`${BASE_URL_DOCUMENTOS}/documentos/buscar?${params.toString()}`, { cache: "no-store" });
        const result = await response.json();

        if (!response.ok) {
            throw new Error(result.detail || "Error consultando datos.");
        }

        documentosResultados = result.data || [];

        if (!documentosResultados.length) {
            limpiarResultados();
            mostrarEstado("No se encontraron operaciones con esos datos.", "warning");
            return;
        }

        pintarResultados(documentosResultados);
        seleccionarDocumento(0);
        ocultarEstado();
    } catch (error) {
        mostrarEstado(error.message || "No se pudo completar la consulta.", "error");
    }
}


function pintarResultados(rows) {
    const panel = document.getElementById("panelResultados");
    const tbody = document.getElementById("tbodyResultados");
    const contador = document.getElementById("contadorResultados");

    if (!panel || !tbody || !contador) return;

    panel.classList.remove("hidden");
    contador.textContent = `${rows.length} registro${rows.length === 1 ? "" : "s"}`;
    tbody.innerHTML = "";

    rows.forEach((item, index) => {
        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td>
                <strong>${escapeHtml(item.NomCliente)}</strong>
                <small>${escapeHtml(item.DireccionPrincipal || "")}</small>
            </td>
            <td>${escapeHtml(item.NumDocumento)}</td>
            <td>${escapeHtml(item.Operacion)}</td>
            <td>
                <strong>${escapeHtml(item.CodigoGrupo)}</strong>
                <small>${escapeHtml(item.CodCreGrupal || item.NomGrupo || "")}</small>
            </td>
            <td>${money(item.DeudaTotal)}</td>
            <td>${money(item.MtoCancelacionCliente)}</td>
            <td><button class="documentos-mini-btn" type="button" data-index="${index}">${esDocumentoGrupal() ? "Usar grupo" : "Seleccionar"}</button></td>
        `;
        tbody.appendChild(tr);
    });

    tbody.querySelectorAll("[data-index]").forEach(button => {
        button.addEventListener("click", () => seleccionarDocumento(Number(button.dataset.index)));
    });
}


function seleccionarDocumento(index) {
    documentoSeleccionado = documentosResultados[index] || documentosResultados[0];
    if (!documentoSeleccionado) return;

    document.getElementById("panelGeneracion")?.classList.remove("hidden");
    actualizarModoDocumento();

    if (esDocumentoGrupal()) {
        document.getElementById("clienteSeleccionado").textContent = `${valueOrDash(documentoSeleccionado.NomGrupo)} - ${documentosResultados.length} integrante${documentosResultados.length === 1 ? "" : "s"}`;
        document.getElementById("operacionSeleccionada").textContent = `Grupo ${valueOrDash(documentoSeleccionado.CodigoGrupo)}`;
        document.getElementById("montoMinimo").textContent = String(documentosResultadosActivos().length || documentosResultados.length);
        document.getElementById("deudaTotal").textContent = money(esDocumentoCuotaGrupal() ? totalCuotaGrupo() : totalDeudaGrupo());
        pintarEncargadosParticipantes();
        pintarMontosGrupales();
        actualizarCondonacion();
        pintarPreviewDocumento();
        return;
    }

    document.getElementById("clienteSeleccionado").textContent = `${valueOrDash(documentoSeleccionado.NomCliente)} - DNI ${valueOrDash(documentoSeleccionado.NumDocumento)}`;
    document.getElementById("operacionSeleccionada").textContent = `Operacion ${valueOrDash(documentoSeleccionado.Operacion)}`;
    const usaCuotaIndividual = esDocumentoCuotaIndividual() || esDocumentoCorreoPagoDirectoCuota();
    document.getElementById("montoMinimo").textContent = money(usaCuotaIndividual ? cuotaDocumento(documentoSeleccionado) : documentoSeleccionado.MtoCancelacionCliente);
    document.getElementById("deudaTotal").textContent = money(documentoSeleccionado.DeudaTotal);

    const cancelacion = document.getElementById("cancelacion");
    const minimo = Number(usaCuotaIndividual ? cuotaDocumento(documentoSeleccionado) : documentoSeleccionado.MtoCancelacionCliente || 0);
    if (cancelacion) {
        cancelacion.min = String(minimo + 0.01);
        cancelacion.value = "";
        cancelacion.focus();
    }

    actualizarCondonacion();
    pintarPreviewDocumento();
}


function pintarEncargadosParticipantes() {
    const select = document.getElementById("encargadoParticipante");
    if (!select) return;

    select.innerHTML = documentosResultados.map((item, index) => (
        `<option value="${escapeAttr(item.Operacion)}" data-dni="${escapeAttr(item.NumDocumento)}" ${index === 0 ? "selected" : ""}>${escapeHtml(item.NomCliente)} - DNI ${escapeHtml(item.NumDocumento)}</option>`
    )).join("");
    actualizarModoEncargado();
}


function actualizarModoEncargado() {
    const modo = document.querySelector("input[name='encargadoModo']:checked")?.value || "participante";
    document.getElementById("encargadoParticipanteBox")?.classList.toggle("hidden", modo !== "participante");
    document.getElementById("encargadoLibreBox")?.classList.toggle("hidden", modo !== "libre");
}


function pintarMontosGrupales() {
    const tbody = document.getElementById("tbodyMontosGrupales");
    if (!tbody) return;

    tbody.innerHTML = documentosResultados.map(item => `
        <tr>
            <td><input class="integrante-activo-input" type="checkbox" data-operacion="${escapeAttr(item.Operacion)}" checked></td>
            <td><strong>${escapeHtml(cuentaDocumento(item))}</strong></td>
            <td>${escapeHtml(item.Operacion)}</td>
            ${esDocumentoCuotaGrupal() ? `<td>${escapeHtml(nroCuotaDocumento(item))}</td>` : ""}
            <td>
                <strong>${escapeHtml(item.NomCliente)}</strong>
                <small>DNI ${escapeHtml(item.NumDocumento)}</small>
            </td>
            <td>${money(item.DeudaTotal)}</td>
            ${esDocumentoCuotaGrupal() ? `<td>${money(cuotaDocumento(item))}</td>` : ""}
            <td><input class="monto-grupal-input" type="number" step="0.01" min="0.01" data-operacion="${escapeAttr(item.Operacion)}" placeholder="0.00"></td>
        </tr>
    `).join("");

    tbody.querySelectorAll(".monto-grupal-input, .integrante-activo-input").forEach(input => {
        input.addEventListener("input", () => {
            actualizarCondonacion();
            pintarPreviewDocumento();
        });
        input.addEventListener("change", () => {
            actualizarCondonacion();
            pintarPreviewDocumento();
        });
    });
    actualizarCondonacion();
}


function documentosResultadosActivos() {
    if (!esDocumentoGrupal()) return documentosResultados;
    const checks = Array.from(document.querySelectorAll(".integrante-activo-input"));
    if (!checks.length) return documentosResultados;
    const activas = new Set(checks.filter(input => input.checked).map(input => String(input.dataset.operacion || "")));
    return documentosResultados.filter(item => activas.has(String(item.Operacion)));
}


function operacionActiva(operacion) {
    const input = document.querySelector(`.integrante-activo-input[data-operacion="${cssEscape(String(operacion))}"]`);
    return input ? input.checked : true;
}


function totalDeudaGrupo() {
    return documentosResultadosActivos().reduce((total, item) => total + Number(item.DeudaTotal || 0), 0);
}


function cuotaDocumento(item) {
    return ["CT1", "CT11", "CT12", "CT13", "CT14", "CT15"].reduce((total, field) => total + Number(item?.[field] || 0), 0);
}


function nroCuotaDocumento(item) {
    return item?.UltCuotaAtrasada || "1";
}


function totalCuotaGrupo() {
    return documentosResultadosActivos().reduce((total, item) => total + cuotaDocumento(item), 0);
}


function obtenerPagosGrupales() {
    return Array.from(document.querySelectorAll(".monto-grupal-input")).map(input => ({
        operacion: input.dataset.operacion || "",
        monto: Number(input.value || 0),
        activo: operacionActiva(input.dataset.operacion || ""),
    }));
}


function totalPagoGrupo() {
    return obtenerPagosGrupales().filter(item => item.activo).reduce((total, item) => total + Number(item.monto || 0), 0);
}


function tieneExcepcion() {
    return Boolean(document.getElementById("excepcionDocumento")?.checked);
}


function actualizarCondonacion() {
    const target = document.getElementById("condonacionEstimada");
    if (!target || !documentoSeleccionado) return;

    if (esDocumentoGrupal()) {
        const pago = totalPagoGrupo();
        const condonacion = Math.max(totalDeudaGrupo() - pago, 0);
        target.textContent = money(condonacion);
        document.getElementById("montoMinimo").textContent = String(documentosResultadosActivos().length);
        document.getElementById("deudaTotal").textContent = money(esDocumentoCuotaGrupal() ? totalCuotaGrupo() : totalDeudaGrupo());
        const total = document.getElementById("totalGrupalPreview");
        if (total) total.textContent = money(pago);
        return;
    }

    const deuda = Number(documentoSeleccionado.DeudaTotal || 0);
    if (esDocumentoCuotaIndividual() || esDocumentoCorreoPagoDirectoCuota()) {
        const cuota = cuotaDocumento(documentoSeleccionado);
        const pago = Number(document.getElementById("cancelacion")?.value || 0);
        target.textContent = money(Math.max(cuota - pago, 0));
        return;
    }

    const cancelacion = Number(document.getElementById("cancelacion")?.value || 0);
    target.textContent = money(Math.max(deuda - cancelacion, 0));
}


function seleccionarFormato(formato) {
    document.getElementById("formatoDocumento").value = formato || "docx";
    document.querySelectorAll("[data-formato]").forEach(button => {
        button.classList.toggle("active", button.dataset.formato === formato);
    });
}


function pintarPreviewDocumento() {
    document.getElementById("panelPreview")?.classList.toggle("mail-only", esDocumentoCorreoPagoDirecto());
    if (esDocumentoCorreoPagoDirecto()) {
        pintarPreviewPagoDirecto();
    } else if (esDocumentoCuotaGrupal()) {
        pintarPreviewCuotaGrupal();
    } else if (esDocumentoGrupal()) {
        pintarPreviewGrupal();
    } else if (esDocumentoCuotaIndividual()) {
        pintarPreviewCuotaIndividual();
    } else {
        pintarPreviewIndividual();
    }
    if (!esDocumentoCorreoPagoDirecto()) pintarPreviewCorreo();
}


function pintarPreviewPagoDirecto() {
    const panel = document.getElementById("panelPreview");
    const preview = document.getElementById("documentoPreview");
    if (!panel || !preview || !documentoSeleccionado) return;

    const correoAgencia = correoPagoDirectoAgencia();
    const correoSectorista = correoPagoDirectoSectorista();
    panel.classList.remove("hidden");
    preview.innerHTML = `
        <div class="correo-dual-preview">
            ${renderCorreoDirectoCard("Correo agencia", "agencia", correoAgencia)}
            ${renderCorreoDirectoCard("Correo sectorista", "sectorista", correoSectorista)}
        </div>
    `;
}


function renderCorreoDirectoCard(titulo, key, correo) {
    return `
        <section class="correo-directo-card">
            <div class="correo-directo-head">
                <div>
                    <h2>${escapeHtml(titulo)}</h2>
                    <p>Formato listo para copiar con tabla y estilos.</p>
                </div>
                <button class="documentos-mini-btn" type="button" data-copy-pago-directo="${escapeAttr(key)}">Copiar</button>
            </div>
            <label>Asunto<input type="text" value="${escapeAttr(correo.asunto)}" readonly></label>
            <label>Cuerpo<div class="documentos-mail-body correo-directo-body">${correo.html}</div></label>
            <label>Correos obligatorios<textarea readonly>${escapeHtml(correo.destinatarios)}</textarea></label>
        </section>
    `;
}


function pintarPreviewIndividual() {
    const panel = document.getElementById("panelPreview");
    const preview = document.getElementById("documentoPreview");
    if (!panel || !preview || !documentoSeleccionado) return;

    const cancelacion = Number(document.getElementById("cancelacion")?.value || 0);
    const deuda = Number(documentoSeleccionado.DeudaTotal || 0);
    const condonacion = Math.max(deuda - cancelacion, 0);
    const fecha = fechaLargaHoy();
    const fechaCorta = fechaCortaHoy();
    const distrito = documentoSeleccionado.DistritoPrincipal || documentoSeleccionado.Distrito_Principal || documentoSeleccionado.Distrito || "";

    panel.classList.remove("hidden");
    preview.innerHTML = `
        <h1>Transaccion extrajudicial y Cancelacion de Deuda</h1>
        <p>Conste por el presente documento una Transaccion Extrajudicial y Cancelacion de Deuda, que celebran de una parte la Empresa de cobranza BIZNESCOB, con RUC 20602593640, con domicilio en Enrique Encinas 284 la victoria y representado por el sr(a) LUIS PORTUGUEZ BERROCAL identificado con DNI 10416012, por encargo de COMPARTAMOS BANCO S.A.,  en adelante COMPARTAMOS, con domicilio en Av. Paseo de la Republica N° 5895 - Interior 1301, distrito de Mira flores, provincia y departamento de Lima, inscrita en la Partida Nro. 13777030 del Registro de Personas Juridicas de la Zona Registral Nro. IX - Sede Lima y de otra parte el/la Sr (a) <strong>${escapeHtml(documentoSeleccionado.NomCliente)}</strong> identificado con DNI N°.<strong>${escapeHtml(documentoSeleccionado.NumDocumento)}</strong>, con domicilio en ${escapeHtml(documentoSeleccionado.DireccionPrincipal || "")}, distrito de ${escapeHtml(distrito)}, a quien en adelante se le denominara  EL/LA/DEUDOR/A, en los terminos y condiciones siguientes:</p>
        <p><strong><u>PRIMERA.-</u></strong> EL DEUDOR reconoce adeudar a COMPARTAMOS BANCO el credito <strong>${escapeHtml(documentoSeleccionado.Operacion)}</strong>, cuyo  importe asciende  a la suma total de S/  <strong>${moneyNumber(documentoSeleccionado.DeudaTotal)}</strong>,  segun liquidacion a la fecha.</p>
        <p><strong><u>SEGUNDA-</u></strong> De conformidad con lo senalado en la clausula anterior EL DEUDOR se obliga a cancelar a   COMPARTAMOS BANCO la deuda antes descrita de la siguiente manera:</p>
        <table>
            <thead><tr><th>Monto</th><th>Fecha de Pago/ Cancelacion</th></tr></thead>
            <tbody><tr><td>S/ ${moneyNumber(cancelacion)}</td><td>${fechaCorta}</td></tr></tbody>
        </table>
        <p>La cancelacion de la suma antes detallada esta sujeta al pago acordado en el parrafo que antecede.</p>
        <p><strong><u>TERCERA .-</u></strong> Sin perjuicio de lo senalado, COMPARTAMOS se reserva el derecho de iniciar, interponer o continuar con las acciones administrativas, legales o judiciales en caso de que el EL/LA/DEUDOR/A incumpla las obligaciones que por el presente documento asume; COMPARTAMOS quedara expedito para su cobro de conformidad con lo estipulado por inciso 8 del articulo 688 del Codigo Proceso Civil.</p>
        <p><strong><u>CUARTA .-</u></strong> Las garantias y/o fianzas solidarias constituidas en respaldo de la obligacion antes senalada subsisten en tanto no se cancele totalmente la misma por el monto acordado, por cuanto la suscripcion de presente convenio no constituye una novacion de la obligacion</p>
        <p><strong><u>QUINTA .-</u></strong> El incumplimiento o retraso en el pago del monto senalado en la clausula segunda, a criterio de COMPARTAMOS, quedaran sin efecto los beneficios (descuentos u otros) otorgados a EL/LA/DEUDOR/A, recalculando los intereses y mora que se hayan generado posteriormente.</p>
        <p><strong><u>SEXTA :</u></strong>  EL/LA/DEUDOR/A ratifica su voluntad expresada en el presente instrumento, dejando constancia que no ha mediado vicio capaz de invalidarlo.</p>
        <p class="preview-date">${fecha}</p>
        ${previewFirmas(documentoSeleccionado.NumDocumento)}
        <hr>
        <h2>NOTA DE ABONO</h2>
        <p>Por el presente documento COMPARTAMOS, concede condonacion sobre la deuda de EL/LA/DEUDOR/A, segun las condiciones ofrecidas en la en el presente documento.</p>
        <p class="preview-highlight">Sr(a):${escapeHtml(documentoSeleccionado.NomCliente)} con DNI Nº ${escapeHtml(documentoSeleccionado.NumDocumento)} por la suma de S/ ${moneyNumber(condonacion)}</p>
        <p>EL/LA/DEUDOR/A, acepta el descuento indicado, reduciendo la deuda vigente que se detalla en la presente transaccion, la misma que mantiene su validez, si EL/LA/DEUDOR/A cumple todas las condiciones descritas en el documento.</p>
        <p>El descuento esta sujeto al cumplimiento del pago de: S/ ${moneyNumber(cancelacion)} en las fechas y formas acordadas en la clausula segunda.</p>
        ${previewFirmas(documentoSeleccionado.NumDocumento)}
    `;
}


function pintarPreviewCuotaIndividual() {
    const panel = document.getElementById("panelPreview");
    const preview = document.getElementById("documentoPreview");
    if (!panel || !preview || !documentoSeleccionado) return;

    const pago = Number(document.getElementById("cancelacion")?.value || 0);
    const deuda = Number(documentoSeleccionado.DeudaTotal || 0);
    const cuota = cuotaDocumento(documentoSeleccionado);
    const condonacion = Math.max(cuota - pago, 0);
    const fecha = fechaLargaHoy();
    const fechaCorta = fechaCortaHoy();
    const distrito = documentoSeleccionado.DistritoPrincipal || documentoSeleccionado.Distrito_Principal || documentoSeleccionado.Distrito || "";

    panel.classList.remove("hidden");
    preview.innerHTML = `
        <h1>COMPROMISO DE PAGO</h1>
        <p>Conste por el presente documento una Transaccion Extrajudicial y Cancelacion de Deuda, que celebran de una parte la Empresa de cobranza BIZNESCOB, con RUC 20602593640, con domicilio en Enrique Encinas 284 la victoria y representado por el sr(a) LUIS PORTUGUEZ BERROCAL identificado con DNI 10416012, por encargo de COMPARTAMOS BANCO S.A., en adelante COMPARTAMOS, con domicilio en Av. Paseo de la Republica Nro. 5895 - Interior 1301, distrito de Miraflores, provincia y departamento de Lima, inscrita en la Partida Nro. 13777030 del Registro de Personas Juridicas de la Zona Registral Nro. IX - Sede Lima y de otra parte el/la Sr(a) <strong>${escapeHtml(documentoSeleccionado.NomCliente)}</strong> identificado con DNI Nro. <strong>${escapeHtml(documentoSeleccionado.NumDocumento)}</strong>, con domicilio en ${escapeHtml(documentoSeleccionado.DireccionPrincipal || "")}, distrito de ${escapeHtml(distrito)}, a quien en adelante se le denominara EL/LA/DEUDOR/A, en los terminos y condiciones siguientes:</p>
        <p><strong><u>PRIMERA.-</u></strong> EL DEUDOR reconoce adeudar a COMPARTAMOS BANCO el(los) credito(s) <strong>${escapeHtml(documentoSeleccionado.Operacion)}</strong>, cuyo importe asciende a la suma total de S/ <strong>${moneyNumber(deuda)}</strong>. Segun liquidacion a la fecha.</p>
        <p>Asimismo, detallamos que el importe de las cuotas vencidas Nro. ${escapeHtml(nroCuotaDocumento(documentoSeleccionado))}, asciende a S/. ${moneyNumber(cuota)}.</p>
        <p><strong><u>SEGUNDA-</u></strong> De conformidad con lo senalado en la clausula primera EL/LA/DEUDOR/A se obliga a pagar las cuotas mencionadas en la clausula primera, a favor de COMPARTAMOS de la siguiente manera:</p>
        <table>
            <thead><tr><th>Monto</th><th>Fecha de Pago/ Cancelacion</th></tr></thead>
            <tbody><tr><td>S/ ${moneyNumber(pago)}</td><td>${fechaCorta}</td></tr></tbody>
        </table>
        <p>El descuento generado por el compromiso esta sujeto al pago acordado en el parrafo que antecede.</p>
        <p><strong><u>TERCERA .-</u></strong> Sin perjuicio de lo senalado, COMPARTAMOS se reserva el derecho de iniciar, interponer o continuar con las acciones administrativas, legales o judiciales, para lograr el recupero total de la deuda, en caso de que EL/LA/DEUDOR/A incumpla las obligaciones que por el presente documento asume. El pago acordado en el presente no significa cancelacion total de la deuda.</p>
        <p><strong><u>CUARTA .-</u></strong> El incumplimiento o retraso en el pago del monto senalado en la clausula segunda, a criterio de COMPARTAMOS, quedaran sin efecto los beneficios otorgados a EL/LA/DEUDOR/A, recalculando los intereses y moras que se hayan generado posteriormente.</p>
        <p><strong><u>QUINTA .-</u></strong> EL/LA/DEUDOR/A ratifica su voluntad expresada en el presente instrumento, dejando constancia que no ha mediado vicio capaz de invalidarlo.</p>
        <p class="preview-date">${fecha}</p>
        ${previewFirmas(documentoSeleccionado.NumDocumento)}
        <hr>
        <h2>NOTA DE ABONO</h2>
        <p>Por el presente documento COMPARTAMOS, concede condonacion sobre la deuda de EL/LA/DEUDOR/A, segun las condiciones ofrecidas en la en el presente documento.</p>
        <p class="preview-highlight">Sr(a): ${escapeHtml(documentoSeleccionado.NomCliente)} con DNI Nro. ${escapeHtml(documentoSeleccionado.NumDocumento)} por la suma de S/ ${moneyNumber(condonacion)}</p>
        <p>EL/LA/DEUDOR/A, acepta el descuento indicado, reduciendo la deuda vigente que se detalla en la presente transaccion, la misma que mantiene su validez, si EL/LA/DEUDOR/A cumple todas las condiciones descritas en el documento. El descuento esta sujeto al cumplimiento del pago de: S/ ${moneyNumber(pago)} en las fechas y formas acordadas en la clausula segunda.</p>
        ${previewFirmas(documentoSeleccionado.NumDocumento)}
    `;
}


function pintarPreviewGrupal() {
    const panel = document.getElementById("panelPreview");
    const preview = document.getElementById("documentoPreview");
    if (!panel || !preview || !documentoSeleccionado) return;

    const encargado = obtenerEncargadoPreview();
    const deudaTotal = totalDeudaGrupo();
    const totalPago = totalPagoGrupo();
    const totalCondonacion = Math.max(deudaTotal - totalPago, 0);
    const fecha = fechaLargaHoy(true);
    const fechaCorta = fechaCortaHoy();
    const credito = documentoSeleccionado.CodCreGrupal || documentoSeleccionado.CodigoGrupo || "";
    const pagoRows = documentosResultadosActivos().map(item => {
        const pago = obtenerPagoPorOperacion(item.Operacion);
        return `<tr><td>${escapeHtml(cuentaDocumento(item))}</td><td>${escapeHtml(item.Operacion)}</td><td>${escapeHtml(item.NomCliente)}</td><td>${moneyNumber(pago)}</td></tr>`;
    }).join("");
    const abonoRows = documentosResultadosActivos().map(item => {
        const pago = obtenerPagoPorOperacion(item.Operacion);
        const condonacion = Math.max(Number(item.DeudaTotal || 0) - pago, 0);
        return `<tr><td>${escapeHtml(cuentaDocumento(item))}</td><td>${escapeHtml(item.Operacion)}</td><td>${escapeHtml(item.NomCliente)}</td><td>${moneyNumber(condonacion)}</td></tr>`;
    }).join("");

    panel.classList.remove("hidden");
    preview.innerHTML = `
        <h1>Convenio de Pago y Cancelacion de Deuda</h1>
        <p>Conste por el presente documento una Transaccion Extrajudicial y Cancelacion de Deuda, que celebran de una parte la Empresa de cobranza BIZNESCOB, con RUC 20602593640, con domicilio en Enrique Encinas 284 la victoria y representado por el sr(a) LUIS PORTUGUEZ BERROCAL identificado con DNI 10416012, por encargo de COMPARTAMOS BANCO S.A.,  en adelante COMPARTAMOS, con domicilio en Av. Paseo de la Republica N° 5895 - Interior 1301, distrito de Miraflores, provincia y departamento de Lima, inscrita en la Partida Nro. 13777030 del Registro de Personas Juridicas de la Zona Registral Nro. IX - Sede Lima Y de otra parte en representacion del grupo <strong>${escapeHtml(documentoSeleccionado.NomGrupo)}</strong>  el Sr/Sra. <strong>${escapeHtml(encargado.nombre)}</strong>  identificado con DNI N° <strong>${escapeHtml(encargado.dni)}</strong>, con domicilio ${escapeHtml(encargado.direccion)}, distrito de ${escapeHtml(encargado.distrito)}  y provincia ${escapeHtml(encargado.provincia)}, en adelante se denominara EL/LA/DEUDOR/A, en los terminos y condiciones siguientes:</p>
        <p><strong><u>Primera:</u></strong> EL/LA/DEUDOR/A, reconoce adeudar a COMPARTAMOS BANCO, el credito N° ${escapeHtml(credito)}, cuyo importe asciende a la suma total de S/${moneyNumber(deudaTotal)}, segun liquidacion a la fecha.</p>
        <p><strong><u>Segunda:</u></strong> De conformidad con lo senalado en la clausula anterior EL DEUDOR se obliga a cancelar a COMPARTAMOS BANCO la deuda antes descrita de la siguiente manera:</p>
        <table class="preview-wide-table">
            <thead><tr><th>Cuenta</th><th>Operacion</th><th>Nombre de cliente</th><th>Monto</th></tr></thead>
            <tbody>${pagoRows}</tbody>
        </table>
        <p class="preview-total">MONTO TOTAL A PAGAR ${money(totalPago)}</p>
        <p>Fecha de pago / cancelacion: ${fechaCorta}</p>
        <p>La cancelacion de la suma antes detallada esta sujeta al pago acordado en el parrafo que antecede.</p>
        <p><strong><u>Tercera:</u></strong> Sin perjuicio de lo senalado, COMPARTAMOS se reserva el derecho de iniciar, interponer o continuar con las acciones administrativas, legales o judiciales en caso de que EL/LA/DEUDOR/A incumpla las obligaciones que por el presente documento asume; COMPARTAMOS quedara expedito para su cobro de conformidad con lo estipulado por inciso 8 del articulo 688 del Codigo Procesal Civil</p>
        <p><strong><u>Cuarta:</u></strong> Las garantias y/o fianzas solidarias constituidas en respaldo de la obligacion antes senalada subsisten en tanto no se cancele totalmente la misma por el monto acordado, por cuanto la suscripcion de presente convenio no constituye una novacion de la obligacion.</p>
        <p><strong><u>Quinta:</u></strong> El incumplimiento o retraso en el pago del monto senalado en la clausula segunda, a criterio de COMPARTAMOS, quedaran sin efecto los beneficios (descuentos u otros) otorgados a EL/LA/DEUDOR/A, recalculando los intereses y mora que se hayan generado posteriormente.</p>
        <p><strong><u>Sexta:</u></strong> EL/LA/DEUDOR/A ratifica su voluntad expresada en el presente instrumento, dejando constancia que no ha mediado vicio capaz de invalidarlo.</p>
        <p class="preview-date">Lima, ${fecha}</p>
        ${previewFirmas(encargado.dni)}
        <hr>
        <h2>NOTA DE ABONO</h2>
        <p>Por el presente documento COMPARTAMOS, concede condonacion sobre la deuda de EL/LA/DEUDOR/A, segun las condiciones ofrecidas en la en el presente documento.</p>
        <p>Sr(a):  ${escapeHtml(encargado.nombre)}  con DNI Nº  ${escapeHtml(encargado.dni)}</p>
        <table class="preview-wide-table">
            <thead><tr><th>Cuenta</th><th>Operacion</th><th>Nombre de cliente</th><th>Monto</th></tr></thead>
            <tbody>${abonoRows}</tbody>
        </table>
        <p><strong>POR LA SUMA DE: S/ ${moneyNumber(totalCondonacion)}</strong></p>
        <p>EL/LA/DEUDOR/A, acepta el descuento indicado, reduciendo la deuda vigente que se detalla en la presente transaccion, la misma que mantiene su validez, si EL/LA/DEUDOR/A cumple todas las condiciones descritas en el documento. El descuento esta sujeto al cumplimiento del pago de</p>
        <p>S/ ${moneyNumber(totalPago)} en las fechas y formas acordadas en la clausula segunda.</p>
        ${previewFirmas(encargado.dni)}
    `;
}


function pintarPreviewCuotaGrupal() {
    const panel = document.getElementById("panelPreview");
    const preview = document.getElementById("documentoPreview");
    if (!panel || !preview || !documentoSeleccionado) return;

    const fiador = obtenerEncargadoPreview();
    const deudaTotal = totalDeudaGrupo();
    const totalCuota = totalCuotaGrupo();
    const totalPago = totalPagoGrupo();
    const totalCondonacion = Math.max(deudaTotal - totalPago, 0);
    const fecha = fechaLargaHoy(true);
    const fechaCorta = fechaCortaHoy();
    const credito = documentoSeleccionado.CodCreGrupal || documentoSeleccionado.CodigoGrupo || "";
    const pagoRows = documentosResultadosActivos().map(item => {
        const pago = obtenerPagoPorOperacion(item.Operacion);
        return `<tr><td>${escapeHtml(cuentaDocumento(item))}</td><td>${escapeHtml(item.Operacion)}</td><td>${escapeHtml(nroCuotaDocumento(item))}</td><td>${escapeHtml(item.NomCliente)}</td><td>${moneyNumber(pago)}</td></tr>`;
    }).join("");
    const abonoRows = documentosResultadosActivos().map(item => {
        const pago = obtenerPagoPorOperacion(item.Operacion);
        const condonacion = Math.max(Number(item.DeudaTotal || 0) - pago, 0);
        return `<tr><td>${escapeHtml(cuentaDocumento(item))}</td><td>${escapeHtml(item.Operacion)}</td><td>${escapeHtml(nroCuotaDocumento(item))}</td><td>${escapeHtml(item.NomCliente)}</td><td>${moneyNumber(condonacion)}</td></tr>`;
    }).join("");

    panel.classList.remove("hidden");
    preview.innerHTML = `
        <h1>Compromiso de pago Producto Grupal</h1>
        <p>Conste por el presente documento una Transaccion Extrajudicial y Cancelacion de Deuda, que celebran de una parte la Empresa de cobranza BIZNESCOB, con RUC 20602593640, con domicilio en Enrique Encinas 284 la victoria y representado por el sr(a) LUIS PORTUGUEZ BERROCAL identificado con DNI 10416012, por encargo de COMPARTAMOS BANCO S.A.,  en adelante COMPARTAMOS, con domicilio en Av. Paseo de la Republica N° 5895 - Interior 1301, distrito de Miraflores, provincia y departamento de Lima, inscrita en la Partida Nro. 13777030 del Registro de Personas Juridicas de la Zona Registral Nro. IX - Sede Lima y de otra parte en representacion del grupo <strong>${escapeHtml(documentoSeleccionado.NomGrupo)}</strong>  el Sr/Sra. <strong>${escapeHtml(fiador.nombre)}</strong>  identificado con DNI N° <strong>${escapeHtml(fiador.dni)}</strong>, con domicilio ${escapeHtml(fiador.direccion)}, distrito de ${escapeHtml(fiador.distrito)}  y provincia ${escapeHtml(fiador.provincia)}, en adelante se denominara EL/LA/DEUDOR/A, en los terminos y condiciones siguientes:</p>
        <p><strong><u>Primera:</u></strong> EL/LA/DEUDOR/A, reconoce adeudar a COMPARTAMOS, el(los) credito(s) N° ${escapeHtml(credito)}, cuyo importe asciende a la suma total de S/${moneyNumber(deudaTotal)}, segun liquidacion a la fecha.</p>
        <p>Asimismo, detallamos que el importe de las cuotas vencidas a pagar asciende a S/.${moneyNumber(totalCuota)}.</p>
        <p><strong><u>Segunda:</u></strong> De conformidad con lo senalado en la clausula primera EL/LA/DEUDOR/A se obliga a pagar las cuotas mencionadas en la clausula primera, a favor de COMPARTAMOS de la siguiente manera:</p>
        <table class="preview-wide-table">
            <thead><tr><th>Cuenta</th><th>Operacion</th><th>N° Cuota</th><th>Nombre de cliente</th><th>Monto</th></tr></thead>
            <tbody>${pagoRows}</tbody>
        </table>
        <p class="preview-total">MONTO TOTAL A PAGAR ${money(totalPago)}</p>
        <p>Fecha de pago / cancelacion: ${fechaCorta}</p>
        <p>El descuento generado por el compromiso esta sujeto al pago acordado en el parrafo que antecede.</p>
        <p><strong><u>TERCERA. -</u></strong> Sin perjuicio de lo senalado, COMPARTAMOS se reserva el derecho de iniciar, interponer o continuar con las acciones administrativas, legales o judiciales, para lograr el recupero total de la deuda, en caso de que EL/LA/DEUDOR/A incumpla las obligaciones que por el presente documento asume. El pago acordado en el presente no significa cancelacion total de la deuda.</p>
        <p><strong><u>CUARTA. -</u></strong> El incumplimiento o retraso en el pago del monto senalado en la clausula segunda, a criterio de COMPARTAMOS, quedaran sin efecto los beneficios (descuentos u otros) otorgados a EL/LA/DEUDOR/A, recalculando los intereses y moras que se hayan generado posteriormente.</p>
        <p><strong><u>QUINTA. -</u></strong> EL/LA/DEUDOR/A ratifica su voluntad expresada en el presente instrumento, dejando constancia que no ha mediado vicio capaz de invalidarlo.</p>
        <p class="preview-date">Lima, ${fecha}</p>
        ${previewFirmas(fiador.dni)}
        <hr>
        <h2>NOTA DE ABONO</h2>
        <p>Por el presente documento COMPARTAMOS, concede condonacion sobre la deuda de EL/LA/DEUDOR/A, segun las condiciones ofrecidas en la en el presente documento.</p>
        <p>Sr(a):  ${escapeHtml(fiador.nombre)}  con DNI Nº  ${escapeHtml(fiador.dni)}</p>
        <table class="preview-wide-table">
            <thead><tr><th>Cuenta</th><th>Operacion</th><th>N° Cuota</th><th>Nombre de cliente</th><th>Monto</th></tr></thead>
            <tbody>${abonoRows}</tbody>
        </table>
        <p><strong>POR LA SUMA DE: S/ ${moneyNumber(totalCondonacion)}</strong></p>
        <p>EL/LA/DEUDOR/A, acepta el descuento indicado, reduciendo la deuda vigente que se detalla en la presente transaccion, la misma que mantiene su validez, si EL/LA/DEUDOR/A cumple todas las condiciones descritas en el documento. El descuento esta sujeto al cumplimiento del pago de</p>
        <p>S/ ${moneyNumber(totalPago)} en las fechas y formas acordadas en la clausula segunda.</p>
        ${previewFirmas(fiador.dni)}
    `;
}


function previewFirmas(dni) {
    return `
        <div class="preview-signatures">
            <div>
                <div class="preview-line"></div>
                <strong>EL/LA DEUDOR/A</strong>
                <span>D.N.I. ${escapeHtml(dni)}</span>
            </div>
            <div>
                <img src="firma_luis_portuguez.png" alt="Firma Luis Portuguez Berrocal">
            </div>
        </div>
    `;
}


function pintarPreviewCorreo() {
    const asunto = document.getElementById("correoAsunto");
    const cuerpo = document.getElementById("correoCuerpo");
    const cuerpoHtml = document.getElementById("correoCuerpoHtml");
    const destinatarios = document.getElementById("correoDestinatarios");
    if (esDocumentoCorreoPagoDirecto()) return;
    if (!asunto || !cuerpo || !cuerpoHtml || !destinatarios || !documentoSeleccionado) return;

    const correo = construirCorreoPreview();
    asunto.value = correo.asunto;
    cuerpo.value = correo.texto;
    cuerpoHtml.innerHTML = correo.html;
    destinatarios.value = correo.destinatarios;
}


function construirCorreoPreview() {
    const formato = document.getElementById("correoFormato")?.value || "carta";
    if (formato === "agencia") return correoPagoDirectoAgencia();
    if (formato === "sectorista") return correoPagoDirectoSectorista();
    if (esDocumentoCuotaGrupal()) return correoCuotaGrupal();
    if (esDocumentoGrupal()) return correoCancelacionGrupal();
    if (esDocumentoCuotaIndividual()) return correoCuotaIndividual();
    return correoCancelacionIndividual();
}


function correoBase() {
    return {
        destinatarios: [
            "Evelyn Vanessa Tello Rosales <etello@compartamos.pe>",
            "Jhoslyl Venales Martinez <supervisor2.compartamos@biznescob.pe>",
            "Maryoreth Alisson Avalos Inciso <mavalosi@compartamos.pe>",
            "normalizacion <normalizacion@compartamos.pe>",
            "administrativo@biznescob.pe",
        ].join(", "),
    };
}

function montoCorreoActual() {
    if (esDocumentoGrupal()) return totalPagoGrupo();
    return Number(document.getElementById("cancelacion")?.value || 0);
}


function esCorreoCuota() {
    return esDocumentoCuotaGrupal() || esDocumentoCuotaIndividual() || esDocumentoCorreoPagoDirectoCuota();
}


function nombreClienteCorreo() {
    if (esDocumentoGrupal()) {
        const persona = obtenerEncargadoPreview();
        return persona.nombre || documentoSeleccionado?.NomCliente || "";
    }
    return documentoSeleccionado?.NomCliente || "";
}


function dniClienteCorreo() {
    if (esDocumentoGrupal()) {
        const persona = obtenerEncargadoPreview();
        return persona.dni || documentoSeleccionado?.NumDocumento || "";
    }
    return documentoSeleccionado?.NumDocumento || "";
}


function cuentaClienteCorreo() {
    return cuentaDocumento(documentoSeleccionado);
}


function creditoGrupoCorreo() {
    return documentoSeleccionado?.CodCreGrupal || documentoSeleccionado?.CodigoGrupo || "";
}


function correoPagoDirectoAgencia() {
    const pago = montoCorreoActual();
    const cuota = nroCuotaDocumento(documentoSeleccionado);
    const agencia = agenciaDocumento(documentoSeleccionado);
    const cliente = nombreClienteCorreo();
    const dni = dniClienteCorreo();
    const tipo = esCorreoCuota() ? "CUOTA" : "CANCELACIÓN";
    const asunto = `APLICACIÓN PAGOS PARCIALES_${tipo}_${cliente}_${agencia}`;
    const cuerpo = esCorreoCuota()
        ? [
            parrafoCorreo("Buen día"),
            parrafoCorreo("Estimad@"),
            parrafoCorreo(`Agradeceré su apoyo en la atención del cliente ${cliente} con DNI ${dni}, quien cancelará como pago directo su cuota N° ${cuota} que tiene como monto de S/ ${moneyNumber(pago)}.`),
            parrafoCorreo(`a. Recepcionar pago e ingresarlo al código del grupo N° ${creditoGrupoCorreo()}.`),
            parrafoCorreo(`b. Luego Auxiliar de operaciones, abonar a la cuenta del cliente N° ${cuentaClienteCorreo()}.`),
            parrafoCorreo(`El pago lo realizará en la AGENCIA DE ORIGEN ${agencia}.`),
            parrafoCorreo(`El pago lo realizará en la agencia ${agencia}.`),
            parrafoCorreo(`* Nota: Los saldos colocados en el contenido del cliente son a lo indicado en WSAC, dicha información es facilitada por Compartamos Banco. * (${fechaCortaHoy()})`),
            parrafoCorreo("- FOTO SAC"),
        ]
        : [
            parrafoCorreo("Buen día"),
            parrafoCorreo("Estimad@"),
            parrafoCorreo(`Agradeceré su apoyo en la atención del cliente ${cliente} con DNI ${dni}, quien cancelará como pago directo para liquidar su deuda el monto de S/ ${moneyNumber(pago)}.`),
            parrafoCorreo(`a. Ingresarlo al código del grupo N° ${creditoGrupoCorreo()}.`),
            parrafoCorreo(`b. Auxiliar de operaciones, abonar a la cuenta del cliente N° ${cuentaClienteCorreo()}.`),
            parrafoCorreo(`AGENCIA DE ORIGEN ${agencia}.`),
            parrafoCorreo(`El pago lo realizará en la agencia ${agencia}.`),
            parrafoCorreo(`* Nota: Los saldos colocados en el contenido del cliente son a lo indicado en WSAC, dicha información es facilitada por Compartamos Banco. * (${fechaCortaHoy()})`),
            parrafoCorreo("- FOTO SAC"),
        ];

    return correoConHtml({
        ...correoBase(),
        asunto,
    }, cuerpo.join(""));
}


function correoPagoDirectoSectorista() {
    const pago = montoCorreoActual();
    const cuota = nroCuotaDocumento(documentoSeleccionado);
    const agencia = agenciaDocumento(documentoSeleccionado);
    const cliente = nombreClienteCorreo();
    const dni = dniClienteCorreo();
    const grupo = documentoSeleccionado?.NomGrupo || "GRUPO";
    const atraso = documentoSeleccionado?.DiasAtraso || "";
    const tipo = esCorreoCuota() ? "CUOTA" : "CANCELACIÓN";
    const asunto = `APLICACIÓN PAGOS PARCIALES_${tipo}_${cliente}_${agencia}`;
    const cuerpo = esCorreoCuota()
        ? [
            parrafoCorreo("Buen día"),
            parrafoCorreo("Estimados Compartamos:"),
            parrafoCorreo(`Por favor su apoyo con su VB° para realizar aplicación de pago del cliente ${cliente} con DNI ${dni}, quien canceló como pago directo su cuota N° ${cuota} que tiene como monto de S/ ${moneyNumber(pago)}.`),
            parrafoCorreo(`Operación ${valueOrDash(documentoSeleccionado?.Operacion)}${atraso ? ` cuenta con ${atraso} días de atraso` : ""}.`),
            parrafoCorreo(`a. Recepcionar pago e ingresarlo al código del grupo N° ${creditoGrupoCorreo()}.`),
            parrafoCorreo(`b. Luego Auxiliar de operaciones, abonar a la cuenta del cliente N° ${cuentaClienteCorreo()}.`),
            parrafoCorreo(`AGENCIA DE ORIGEN ${agencia}.`),
            parrafoCorreo(`El pago lo realizó en la agencia ${agencia}.`),
            parrafoCorreo(`* Nota: Los saldos colocados en el contenido del cliente son a lo indicado en WSAC, dicha información es facilitada por Compartamos Banco. * (${fechaCortaHoy()})`),
            parrafoCorreo("- FOTO SAC"),
        ]
        : [
            parrafoCorreo("Estimados Compartamos:"),
            parrafoCorreo(`Por favor su apoyo con su VB° para realizar aplicación de pago del cliente ${cliente} con DNI ${dni}, que pertenece al grupo ${grupo} con código ${creditoGrupoCorreo()} por el monto de S/ ${moneyNumber(pago)}.`),
            parrafoCorreo(`Operación ${valueOrDash(documentoSeleccionado?.Operacion)}${atraso ? ` cuenta con ${atraso} días de atraso` : ""}.`),
            parrafoCorreo(`a. Ingresarlo al código del grupo N° ${valueOrDash(documentoSeleccionado?.CodigoGrupo)}.`),
            parrafoCorreo(`b. Auxiliar de operaciones, abonar a la cuenta del cliente N° ${cuentaClienteCorreo()}.`),
            parrafoCorreo(`Nota: Los saldos colocados en el contenido del cliente son a lo indicado en WSAC, dicha información es facilitada por Compartamos Banco. * (${fechaCortaHoy()})`),
        ];

    return correoConHtml({
        ...correoBase(),
        asunto,
    }, cuerpo.join(""));
}


function parrafoCorreo(texto) {
    return `<p>${escapeHtml(texto)}</p>`;
}


function bulletCorreo(items) {
    return `<ul>${items.map(item => `<li>${item}</li>`).join("")}</ul>`;
}


function textoDesdeHtml(html) {
    const div = document.createElement("div");
    div.innerHTML = html.replace(/<br\s*\/?>/gi, "\n");
    return (div.innerText || div.textContent || "").trim();
}


function tablaMitigacionCorreo({ cliente, codigoCliente, operacion, tipo = "Liquidación", cuota = "", agencia = "AGENCIA", monto = 0, fecha = "", sustento = "" }) {
    const esCuota = tipo.toLowerCase().includes("cuota");
    return `
        <table class="documentos-mail-table">
            <tr><th colspan="3">Mitigación Cuota / Liquidación</th></tr>
            <tr><td class="mail-label">Nombre de Cliente:</td><td class="mail-value" colspan="2">${escapeHtml(cliente)}</td></tr>
            <tr><td class="mail-label">Código de cliente</td><td class="mail-value" colspan="2">${escapeHtml(codigoCliente)}</td></tr>
            <tr><td class="mail-label">Operación</td><td colspan="2">${escapeHtml(operacion)}</td></tr>
            <tr><td class="mail-label" rowspan="2">Mitigación</td><td><strong>Cuotas</strong></td><td><strong>Liquidación</strong></td></tr>
            <tr><td>${esCuota ? "x" : ""}</td><td>${esCuota ? "" : "x"}</td></tr>
            <tr><td class="mail-label"># de cuota a condonar</td><td colspan="2">${escapeHtml(cuota)}</td></tr>
            <tr><td class="mail-label">Agencia</td><td colspan="2"><strong>${escapeHtml(agencia)}</strong></td></tr>
            <tr><td class="mail-label">Monto total a cancelar s/</td><td colspan="2">${moneyNumber(monto)}</td></tr>
            <tr><td class="mail-label">Fecha de pago</td><td colspan="2">${escapeHtml(fecha)}</td></tr>
            <tr><td class="mail-label">Sustento</td><td class="mail-sustento" colspan="2">${escapeHtml(sustento)}</td></tr>
        </table>
    `;
}


function correoConHtml(base, html) {
    return {
        ...base,
        html,
        texto: textoDesdeHtml(html),
    };
}


function correoCancelacionIndividual() {
    const pago = Number(document.getElementById("cancelacion")?.value || 0);
    const agencia = agenciaDocumento(documentoSeleccionado);
    const grupo = documentoSeleccionado.NomGrupo || "GRUPO";
    const html = [
        parrafoCorreo("Buen Día"),
        parrafoCorreo("Estimado (a)"),
        parrafoCorreo("Se reporta cliente de cartera Vigente - CSM que se acoge a campaña de cancelación."),
        parrafoCorreo("Una vez concluida la operación el cliente solicitará su constancia de cancelación del crédito."),
        parrafoCorreo("Reciban un cordial saludo."),
        parrafoCorreo(`En relación con el grupo "${grupo}", les informamos que se viene gestionando una pronta solución de pago que permitirá mejorar su calificación crediticia grupal ante la entidad bancaria.`),
        parrafoCorreo("Con ese objetivo, se ha planteado una alternativa de pago con uno(a) de los(as) socios(as), por lo cual solicitamos su apoyo para:"),
        bulletCorreo([
            `Emitir el <strong>convenio de pago</strong> correspondiente.`,
            `Realizar la <strong>cobranza por el monto de S/ ${moneyNumber(pago)}</strong>, destinado a cubrir la <strong>cancelación de la operación Nro. ${escapeHtml(documentoSeleccionado.Operacion)}</strong>.`,
        ]),
        parrafoCorreo("Cabe señalar que los demás integrantes del grupo se encuentran en conversaciones con Biznescob para coordinar un próximo pago."),
        parrafoCorreo("Agradecemos de antemano su atención y quedamos atentos a su pronta respuesta."),
        tablaMitigacionCorreo({
            cliente: valueOrDash(documentoSeleccionado.NomCliente),
            codigoCliente: cuentaDocumento(documentoSeleccionado),
            operacion: valueOrDash(documentoSeleccionado.Operacion),
            tipo: "Liquidación",
            agencia,
            monto: pago,
            fecha: fechaCortaHoy(),
            sustento: "Cliente, este mes cancelará todo su crédito con la campaña ofrecida, ha estado reuniendo este monto para pagar ya que quiere solucionar deuda con el banco.",
        }),
    ].join("");
    return correoConHtml({
        ...correoBase(),
        asunto: `MITIGACION_CSM_CANCELACION_VIGENTE GRUPAL_${valueOrDash(documentoSeleccionado.NomCliente)}_DNI ${valueOrDash(documentoSeleccionado.NumDocumento)}_${valueOrDash(documentoSeleccionado.Operacion)}`,
    }, html);
}


function correoCuotaIndividual() {
    const pago = Number(document.getElementById("cancelacion")?.value || 0);
    const cuota = nroCuotaDocumento(documentoSeleccionado);
    const grupo = documentoSeleccionado.NomGrupo || "GRUPO";
    const agencia = agenciaDocumento(documentoSeleccionado);
    const html = [
        parrafoCorreo("Buen Día"),
        parrafoCorreo("Estimado (a)"),
        parrafoCorreo("Reciban un cordial saludo."),
        parrafoCorreo(`En relación con el grupo "${grupo}", les informamos que se viene gestionando una pronta solución de pago que permitirá mejorar su calificación crediticia grupal ante la entidad bancaria.`),
        parrafoCorreo("Con ese objetivo, se ha planteado una alternativa de pago con uno(a) de los(as) socios(as), por lo cual solicitamos su apoyo para:"),
        bulletCorreo([
            `Emitir el <strong>convenio de pago</strong> correspondiente.`,
            `Realizar la <strong>cobranza por el monto de S/ ${moneyNumber(pago)}</strong>, destinado a cubrir la <strong>cuota Nro. ${escapeHtml(cuota)} de la operación Nro. ${escapeHtml(documentoSeleccionado.Operacion)}</strong>.`,
        ]),
        parrafoCorreo("Cabe señalar que los demás integrantes del grupo se encuentran en conversaciones con Biznescob para coordinar un próximo pago."),
        parrafoCorreo("Agradecemos de antemano su atención y quedamos atentos a su pronta respuesta."),
        tablaMitigacionCorreo({
            cliente: valueOrDash(documentoSeleccionado.NomCliente),
            codigoCliente: cuentaDocumento(documentoSeleccionado),
            operacion: valueOrDash(documentoSeleccionado.Operacion),
            tipo: "Cuotas",
            cuota,
            agencia,
            monto: pago,
            fecha: fechaCortaHoy(),
            sustento: "Cliente informa que ha logrado reunir el monto detallado para cancelar una cuota.",
        }),
        parrafoCorreo("Nota: Los saldos colocados en el contenido del cliente son a lo indicado en WSAC, dicha información es facilitada por Compartamos Banco."),
    ].join("");
    return correoConHtml({
        ...correoBase(),
        asunto: `MITIGACION_CUOTA_VIGENTE GRUPAL_${valueOrDash(documentoSeleccionado.NomCliente)}_OPERACION_${valueOrDash(documentoSeleccionado.Operacion)}`,
    }, html);
}


function correoCancelacionGrupal() {
    const encargado = obtenerEncargadoPreview();
    const totalPago = totalPagoGrupo();
    const grupo = documentoSeleccionado.NomGrupo || "GRUPO";
    const credito = documentoSeleccionado.CodCreGrupal || documentoSeleccionado.CodigoGrupo || "";
    const html = [
        parrafoCorreo("Buen Día"),
        parrafoCorreo("Estimado (a)"),
        parrafoCorreo("Se reporta clientes de cartera Vigente - CSM que se acogen a campaña de cancelación."),
        parrafoCorreo("Una vez concluida la operación los clientes solicitarán su constancia de cancelación de crédito."),
        parrafoCorreo(`Agradeceré tu apoyo en atender el pago del grupo ${grupo}, que realizará la CANCELACIÓN DE SU CRÉDITO GRUPAL ${credito}.`),
        parrafoCorreo(`La persona encargada del pago y firma de convenio es ${encargado.nombre}, con el importe de S/. ${moneyNumber(totalPago)}.`),
        parrafoCorreo("Agradeceré que, una vez realizada la firma, se envíen los documentos escaneados a la agencia de origen para cumplir con el procedimiento correspondiente."),
        parrafoCorreo("Nota: Los saldos colocados en el contenido del cliente son a lo indicado en WSAC, dicha información es facilitada por Compartamos Banco."),
    ].join("");
    return correoConHtml({
        ...correoBase(),
        asunto: `MITIGACION_CSM_CANCELACION_VIGENTE GRUPAL_${grupo}_${credito}`,
    }, html);
}


function correoCuotaGrupal() {
    const fiador = obtenerEncargadoPreview();
    const totalPago = totalPagoGrupo();
    const grupo = documentoSeleccionado.NomGrupo || "GRUPO";
    const credito = documentoSeleccionado.CodCreGrupal || documentoSeleccionado.CodigoGrupo || "";
    const html = [
        parrafoCorreo("Buen Día"),
        parrafoCorreo("Estimado (a)"),
        parrafoCorreo(`Se reporta clientes de cartera Vigente - CSM que se acogen a campaña de cuota. Agradeceré tu apoyo en atender el pago del grupo ${grupo}.`),
        parrafoCorreo(`Realizarán el pago de su cuota del crédito ${credito} según lo detallado en el cuadro.`),
        parrafoCorreo(`La persona encargada del pago y firma de convenio es ${fiador.nombre}, con el importe de S/. ${moneyNumber(totalPago)}, el cual deberá abonarse al crédito individual de cada integrante según lo detallado.`),
        parrafoCorreo("Luego direccionar al cliente a ventanilla y depositar el pago por aplicar."),
        tablaDetalleGrupoCorreo(true),
        parrafoCorreo("Nota: Los saldos colocados en el contenido del cliente son a lo indicado en WSAC, dicha información es facilitada por Compartamos Banco."),
    ].join("");
    return correoConHtml({
        ...correoBase(),
        asunto: `MITIGACION CUOTA_CSM_VIGENTE GRUPAL_${grupo}_${credito}_${valueOrDash(documentoSeleccionado.CodigoGrupo)}`,
    }, html);
}


function tablaDetalleGrupoCorreo(incluirCuota = false) {
    const headers = incluirCuota
        ? ["Cuenta", "Operación", "Nro. Cuota", "Nombre de cliente", "Monto"]
        : ["Cuenta", "Operación", "Nombre de cliente", "Monto"];
    const rows = documentosResultadosActivos().map(item => {
        const pago = obtenerPagoPorOperacion(item.Operacion);
        const cells = [
            cuentaDocumento(item),
            item.Operacion,
        ];
        if (incluirCuota) cells.push(nroCuotaDocumento(item));
        cells.push(item.NomCliente, moneyNumber(pago));
        return cells;
    });

    return `
        <table class="documentos-mail-table">
            <tr>${headers.map(header => `<th>${escapeHtml(header)}</th>`).join("")}</tr>
            ${rows.map(row => `<tr>${row.map(cell => `<td>${escapeHtml(cell)}</td>`).join("")}</tr>`).join("")}
        </table>
    `;
}


function agenciaDocumento(item) {
    return item?.NomOficina || "";
}


async function copiarCorreoPreview() {
    const asunto = document.getElementById("correoAsunto")?.value || "";
    const cuerpoHtml = document.getElementById("correoCuerpoHtml")?.innerHTML || "";
    const cuerpo = document.getElementById("correoCuerpoHtml")?.innerText || document.getElementById("correoCuerpo")?.value || "";
    const destinatarios = document.getElementById("correoDestinatarios")?.value || "";
    await copiarCorreoRich({ destinatarios, asunto, cuerpoHtml, cuerpo });
}


async function copiarCorreoPagoDirecto(tipo) {
    if (!documentoSeleccionado) return;
    const correo = tipo === "sectorista" ? correoPagoDirectoSectorista() : correoPagoDirectoAgencia();
    await copiarCorreoRich({
        destinatarios: correo.destinatarios,
        asunto: correo.asunto,
        cuerpoHtml: correo.html,
        cuerpo: correo.texto,
    });
}


async function copiarCorreoRich({ destinatarios, asunto, cuerpoHtml, cuerpo }) {
    const texto = [`Para: ${destinatarios}`, `Asunto: ${asunto}`, "", cuerpo].join("\n");
    const html = correoHtmlParaCopiar(destinatarios, asunto, prepararHtmlCorreoParaCopiar(cuerpoHtml));

    try {
        if (window.ClipboardItem && navigator.clipboard?.write) {
            await navigator.clipboard.write([
                new ClipboardItem({
                    "text/html": new Blob([html], { type: "text/html" }),
                    "text/plain": new Blob([texto], { type: "text/plain" }),
                }),
            ]);
        } else {
            await navigator.clipboard.writeText(texto);
        }
        mostrarEstado("Correo copiado al portapapeles.", "success");
    } catch (error) {
        copiarCorreoFallbackHtml(html, texto);
    }
}


function prepararHtmlCorreoParaCopiar(cuerpoHtml) {
    const wrapper = document.createElement("div");
    wrapper.innerHTML = cuerpoHtml;

    wrapper.querySelectorAll("p").forEach(p => {
        p.setAttribute("style", "margin:0 0 13px;font-family:Arial,sans-serif;font-size:14px;line-height:1.24;color:#000000;");
    });
    wrapper.querySelectorAll("ul").forEach(ul => {
        ul.setAttribute("style", "margin:0 0 13px 28px;padding:0;font-family:Arial,sans-serif;font-size:14px;line-height:1.24;color:#000000;");
    });
    wrapper.querySelectorAll("li").forEach(li => {
        li.setAttribute("style", "margin:0 0 10px;padding-left:8px;");
    });
    wrapper.querySelectorAll("table.documentos-mail-table").forEach(table => {
        table.setAttribute("style", "width:468px;margin:22px 0 18px;border-collapse:collapse;table-layout:fixed;font-family:Arial,sans-serif;font-size:12px;line-height:1.22;color:#000000;");
    });
    wrapper.querySelectorAll("table.documentos-mail-table th").forEach(th => {
        th.setAttribute("style", "border:1px solid #000000;padding:5px 7px;text-align:center;vertical-align:middle;background:#ffff00;font-weight:700;");
    });
    wrapper.querySelectorAll("table.documentos-mail-table td").forEach(td => {
        const fontWeight = td.classList.contains("mail-label") || td.classList.contains("mail-value") ? "700" : "400";
        td.setAttribute("style", `border:1px solid #000000;padding:5px 7px;text-align:center;vertical-align:middle;font-weight:${fontWeight};`);
    });

    return wrapper.innerHTML;
}


function copiarCorreoFallbackHtml(html, texto) {
    const container = document.createElement("div");
    container.innerHTML = html;
    container.style.position = "fixed";
    container.style.left = "-9999px";
    container.style.top = "0";
    container.style.width = "760px";
    container.style.background = "#ffffff";
    document.body.appendChild(container);

    const selection = window.getSelection();
    const range = document.createRange();
    range.selectNodeContents(container);
    selection.removeAllRanges();
    selection.addRange(range);

    try {
        const ok = document.execCommand("copy");
        selection.removeAllRanges();
        container.remove();
        if (ok) {
            mostrarEstado("Correo copiado con formato.", "success");
            return;
        }
    } catch (fallbackError) {
        selection.removeAllRanges();
        container.remove();
    }

    copiarCorreoFallbackTexto(texto);
}


function copiarCorreoFallbackTexto(texto) {
    const area = document.createElement("textarea");
    area.value = texto;
    area.setAttribute("readonly", "");
    area.style.position = "fixed";
    area.style.left = "-9999px";
    document.body.appendChild(area);
    area.select();

    try {
        const ok = document.execCommand("copy");
        mostrarEstado(ok ? "Correo copiado al portapapeles." : "No se pudo copiar automaticamente. Selecciona el texto del correo y copialo manualmente.", ok ? "success" : "warning");
    } catch (fallbackError) {
        mostrarEstado("No se pudo copiar automaticamente. Selecciona el texto del correo y copialo manualmente.", "warning");
    } finally {
        area.remove();
    }
}


function abrirDirectorioAgencias() {
    document.getElementById("modalDirectorioAgencias")?.classList.remove("hidden");
    cargarDirectorioAgencias();
}


function cerrarDirectorioAgencias() {
    document.getElementById("modalDirectorioAgencias")?.classList.add("hidden");
}


async function cargarDirectorioAgencias() {
    const tbody = document.getElementById("tbodyDirectorioAgencias");
    const estado = document.getElementById("estadoDirectorioAgencias");
    if (!tbody || !estado) return;

    const q = document.getElementById("buscarAgencia")?.value.trim() || "";
    estado.textContent = "Consultando directorio...";

    try {
        const params = new URLSearchParams();
        if (q) params.set("q", q);
        params.set("limit", "500");
        const response = await fetch(`${BASE_URL_DOCUMENTOS}/documentos/agencias?${params.toString()}`, { cache: "no-store" });
        const result = await response.json();
        if (!response.ok) throw new Error(result.detail || "No se pudo cargar el directorio.");

        const rows = result.data || [];
        tbody.innerHTML = rows.length ? rows.map(row => `
            <tr>
                <td><strong>${escapeHtml(row.agencia || "")}</strong><small>${escapeHtml(row.cod || "")} ${escapeHtml(row.estado || "")}</small></td>
                <td>${escapeHtml(row.gerente_agencia || "")}</td>
                <td>${escapeHtml(row.celular_ga || "")}<small>Anexo ${escapeHtml(row.anexo || "")}</small></td>
                <td><strong>${escapeHtml(row.correo_ga || "")}</strong><small>${escapeHtml(row.correo_agencia || "")}</small></td>
                <td>${escapeHtml(row.region || "")}</td>
                <td>${escapeHtml([row.departamento, row.provincia, row.distrito].filter(Boolean).join(" / "))}<small>${escapeHtml(row.direccion || "")}</small></td>
                <td>L-V ${escapeHtml(row.apertura_lv || "")} - ${escapeHtml(row.cierre_lv || "")}<small>SAB ${escapeHtml(row.apertura_sab || "")} - ${escapeHtml(row.cierre_sab || "")}</small></td>
            </tr>
        `).join("") : `<tr><td colspan="7">No hay registros cargados.</td></tr>`;
        estado.textContent = `${rows.length} agencia${rows.length === 1 ? "" : "s"} encontrada${rows.length === 1 ? "" : "s"}.`;
    } catch (error) {
        estado.textContent = error.message || "No se pudo cargar el directorio.";
        tbody.innerHTML = "";
    }
}


async function importarDirectorioAgencias(event) {
    const input = event.target;
    const file = input.files?.[0];
    const estado = document.getElementById("estadoDirectorioAgencias");
    if (!file || !estado) return;

    const confirmar = typeof window.crmConfirm === "function"
        ? await window.crmConfirm({
            title: "Reemplazar directorio",
            message: "Se eliminará el directorio actual y se cargará el Excel seleccionado. ¿Deseas continuar?",
            acceptText: "Importar",
            cancelText: "Cancelar",
            tone: "primary",
        })
        : window.confirm("Se reemplazará el directorio actual. ¿Deseas continuar?");
    if (!confirmar) {
        input.value = "";
        return;
    }

    const formData = new FormData();
    formData.append("file", file);
    estado.textContent = "Importando directorio. Esto puede tardar unos segundos...";

    try {
        const response = await fetch(`${BASE_URL_DOCUMENTOS}/documentos/agencias/importar`, {
            method: "POST",
            body: formData,
        });
        const result = await response.json();
        if (!response.ok) throw new Error(result.detail || "No se pudo importar el directorio.");
        estado.textContent = `Directorio reemplazado correctamente: ${result.data?.total || 0} registros.`;
        input.value = "";
        await cargarDirectorioAgencias();
    } catch (error) {
        estado.textContent = error.message || "No se pudo importar el directorio.";
    }
}


function correoHtmlParaCopiar(destinatarios, asunto, cuerpoHtml) {
    return `
        <html>
        <head>
            <style>
                body { font-family: Arial, sans-serif; font-size: 14px; color: #000000; }
                p { margin: 0 0 13px; }
                ul { margin: 0 0 13px 28px; padding: 0; }
                li { margin: 0 0 10px; padding-left: 8px; }
                table.documentos-mail-table { width: 468px; margin: 22px 0 18px; border-collapse: collapse; table-layout: fixed; font: 12px Arial, sans-serif; color: #000000; }
                table.documentos-mail-table th, table.documentos-mail-table td { border: 1px solid #000000; padding: 5px 7px; text-align: center; vertical-align: middle; }
                table.documentos-mail-table th { background: #ffff00; font-weight: 700; }
                table.documentos-mail-table .mail-label { width: 180px; font-weight: 700; }
                table.documentos-mail-table .mail-value { width: 270px; font-weight: 700; }
                table.documentos-mail-table .mail-sustento { min-height: 96px; font-weight: 400; }
            </style>
        </head>
        <body>
            <p><strong>Para:</strong> ${escapeHtml(destinatarios)}</p>
            <p><strong>Asunto:</strong> ${escapeHtml(asunto)}</p>
            <br>
            ${cuerpoHtml}
        </body>
        </html>
    `;
}


async function generarDocumento() {
    if (!documentoSeleccionado) {
        mostrarEstado("Selecciona una operacion antes de generar.", "warning");
        return;
    }

    if (esDocumentoCorreoPagoDirecto()) {
        mostrarEstado("Este tipo solo muestra los correos de pago directo para copiar.", "info");
        return;
    }

    const formato = document.getElementById("formatoDocumento")?.value || "docx";
    const payload = construirPayloadGeneracion(formato);
    if (!payload) return;

    mostrarEstado(`Generando documento ${formato.toUpperCase()}...`, "info");

    try {
        const response = await fetch(`${BASE_URL_DOCUMENTOS}/documentos/generar`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });

        if (!response.ok) {
            const error = await response.json().catch(() => ({}));
            throw new Error(error.detail || "Error generando documento.");
        }

        const blob = await response.blob();
        const filename = obtenerNombreArchivo(response.headers.get("content-disposition"), formato);
        descargarBlob(blob, filename);
        actualizarUltimaGeneracion();
        mostrarEstado("Documento generado correctamente.", "success");
    } catch (error) {
        mostrarEstado(error.message || "No se pudo generar el documento.", "error");
    }
}


function construirPayloadGeneracion(formato) {
    if (esDocumentoCorreoPagoDirecto()) {
        mostrarEstado("Este tipo solo muestra los correos de pago directo para copiar.", "info");
        return null;
    }

    if (esDocumentoGrupal()) {
        const pagos = obtenerPagosGrupales();
        const activos = pagos.filter(item => item.activo);
        if (!activos.length) {
            mostrarEstado("Selecciona al menos un integrante activo para generar el documento grupal.", "warning");
            return null;
        }
        const incompletos = activos.filter(item => !item.monto || item.monto <= 0);
        if (incompletos.length) {
            mostrarEstado("Ingresa un monto manual mayor a cero para cada operacion del grupo.", "warning");
            return null;
        }
        if (!tieneExcepcion()) {
            const pagosBajos = activos.filter(item => {
                const row = documentosResultados.find(resultado => String(resultado.Operacion) === String(item.operacion));
                const minimo = esDocumentoCuotaGrupal() ? cuotaDocumento(row) : Number(row?.MtoCancelacionCliente || 0);
                return row && Number(item.monto || 0) <= minimo;
            });
            if (pagosBajos.length) {
                const row = documentosResultados.find(resultado => String(resultado.Operacion) === String(pagosBajos[0].operacion));
                const minimo = esDocumentoCuotaGrupal() ? cuotaDocumento(row) : Number(row?.MtoCancelacionCliente || 0);
                const base = esDocumentoCuotaGrupal() ? "la cuota calculada" : "Mto CancelacionCliente";
                mostrarEstado(`El monto de la operacion ${pagosBajos[0].operacion} debe ser mayor a ${money(minimo)} (${base}). Marca Excepcion si se permitira un monto menor.`, "warning");
                return null;
            }
        }

        const encargado = obtenerEncargadoPayload();
        if (!encargado) return null;

        return {
            documento_tipo: esDocumentoCuotaGrupal() ? "compromiso_cuota_grupal" : "cancelacion_grupal",
            dni: "",
            operacion: "",
            codigo_grupo: documentoSeleccionado.CodigoGrupo ? String(documentoSeleccionado.CodigoGrupo) : "",
            cod_cre_grupal: documentoSeleccionado.CodCreGrupal ? String(documentoSeleccionado.CodCreGrupal) : "",
            fecha_pago: new Date().toISOString().slice(0, 10),
            formato: formato,
            excepcion: tieneExcepcion(),
            encargado: encargado,
            pagos_grupales: pagos,
        };
    }

    const cancelacion = Number(document.getElementById("cancelacion")?.value || 0);
    const minimo = Number(esDocumentoCuotaIndividual() ? cuotaDocumento(documentoSeleccionado) : documentoSeleccionado.MtoCancelacionCliente || 0);

    if (!cancelacion || cancelacion <= 0) {
        mostrarEstado("Ingresa un monto de cancelacion valido.", "warning");
        return null;
    }

    if (!tieneExcepcion() && cancelacion <= minimo) {
        const base = esDocumentoCuotaIndividual() ? "la cuota calculada" : "Mto CancelacionCliente";
        mostrarEstado(`El monto debe ser mayor a ${money(minimo)} (${base}). Marca Excepcion si se permitira un monto menor.`, "warning");
        return null;
    }

    return {
        documento_tipo: document.getElementById("documentoTipo")?.value || "transaccion_cancelacion",
        dni: documentoSeleccionado.NumDocumento ? String(documentoSeleccionado.NumDocumento) : "",
        operacion: documentoSeleccionado.Operacion ? String(documentoSeleccionado.Operacion) : "",
        cancelacion: cancelacion,
        fecha_pago: new Date().toISOString().slice(0, 10),
        formato: formato,
        excepcion: tieneExcepcion(),
    };
}


function obtenerEncargadoPayload() {
    const modo = document.querySelector("input[name='encargadoModo']:checked")?.value || "participante";

    if (modo === "libre") {
        const encargado = {
            modo: "libre",
            nombre: document.getElementById("encargadoNombreLibre")?.value.trim() || "",
            dni: document.getElementById("encargadoDniLibre")?.value.trim() || "",
            direccion: document.getElementById("encargadoDireccionLibre")?.value.trim() || "",
            distrito: document.getElementById("encargadoDistritoLibre")?.value.trim() || "",
            provincia: document.getElementById("encargadoProvinciaLibre")?.value.trim() || "",
        };
        if (!encargado.nombre || !encargado.dni || !encargado.direccion || !encargado.distrito || !encargado.provincia) {
            mostrarEstado("Completa nombre, DNI, direccion, distrito y provincia del encargado libre.", "warning");
            return null;
        }
        return encargado;
    }

    const select = document.getElementById("encargadoParticipante");
    const option = select?.selectedOptions?.[0];
    return {
        modo: "participante",
        operacion: select?.value || "",
        dni: option?.dataset?.dni || "",
        provincia: document.getElementById("encargadoProvinciaParticipante")?.value.trim() || "",
    };
}


function obtenerEncargadoPreview() {
    const modo = document.querySelector("input[name='encargadoModo']:checked")?.value || "participante";

    if (modo === "libre") {
        return {
            nombre: document.getElementById("encargadoNombreLibre")?.value.trim() || "NOMBRE DEL ENCARGADO",
            dni: document.getElementById("encargadoDniLibre")?.value.trim() || "DNI",
            direccion: document.getElementById("encargadoDireccionLibre")?.value.trim() || "DIRECCION",
            distrito: document.getElementById("encargadoDistritoLibre")?.value.trim() || "DISTRITO",
            provincia: document.getElementById("encargadoProvinciaLibre")?.value.trim() || "PROVINCIA",
        };
    }

    const selected = documentosResultados.find(item => String(item.Operacion) === String(document.getElementById("encargadoParticipante")?.value)) || documentosResultados[0] || {};
    return {
        nombre: selected.NomCliente || "NOMBRE DEL ENCARGADO",
        dni: selected.NumDocumento || "DNI",
        direccion: selected.DireccionPrincipal || "DIRECCION",
        distrito: selected.DistritoPrincipal || selected.Distrito_Principal || selected.Distrito || "DISTRITO",
        provincia: document.getElementById("encargadoProvinciaParticipante")?.value.trim() || "PROVINCIA",
    };
}


function obtenerPagoPorOperacion(operacion) {
    const input = document.querySelector(`.monto-grupal-input[data-operacion="${cssEscape(String(operacion))}"]`);
    return Number(input?.value || 0);
}


function cuentaDocumento(item) {
    return item?.CtaCliente || item?.CodigoGrupo || "";
}


function cssEscape(value) {
    if (window.CSS && typeof window.CSS.escape === "function") return window.CSS.escape(value);
    return value.replace(/"/g, "\\\"");
}


function obtenerNombreArchivo(disposition, formato = "docx") {
    const fallback = nombreArchivoLocal(formato);
    if (!disposition) return fallback;

    const utfMatch = disposition.match(/filename\*=UTF-8''([^;]+)/i);
    if (utfMatch) return decodeURIComponent(utfMatch[1].replace(/"/g, ""));

    const quotedMatch = disposition.match(/filename="([^"]+)"/i);
    if (quotedMatch) return quotedMatch[1];

    const plainMatch = disposition.match(/filename=([^;]+)/i);
    return plainMatch ? plainMatch[1].trim().replace(/"/g, "") : fallback;
}


function nombreArchivoLocal(formato = "docx") {
    const tipoSelect = document.getElementById("documentoTipo");
    const tipoTexto = tipoSelect?.selectedOptions?.[0]?.textContent || "documento";
    const persona = esDocumentoGrupal()
        ? (documentoSeleccionado?.NomGrupo || "grupo")
        : (documentoSeleccionado?.NomCliente || "cliente");
    return `${slugArchivo(tipoTexto)}_${slugArchivo(persona)}.${formato}`;
}


function slugArchivo(value) {
    return valueOrDash(value)
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "")
        .replace(/[^A-Za-z0-9]+/g, "_")
        .replace(/^_+|_+$/g, "")
        .slice(0, 140) || "documento";
}


function descargarBlob(blob, filename) {
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
}


function limpiarVista() {
    [
        "dni",
        "operacion",
        "codigoGrupo",
        "codCreGrupal",
        "cancelacion",
        "excepcionDocumento",
        "encargadoProvinciaParticipante",
        "encargadoNombreLibre",
        "encargadoDniLibre",
        "encargadoDireccionLibre",
        "encargadoDistritoLibre",
        "encargadoProvinciaLibre",
    ].forEach(id => {
        const input = document.getElementById(id);
        if (input?.type === "checkbox") input.checked = false;
        else if (input) input.value = "";
    });
    pintarFechaDocumentoHoy();
    documentosResultados = [];
    limpiarResultados();
    limpiarSeleccion();
    ocultarEstado();
}


function limpiarResultados() {
    document.getElementById("panelResultados")?.classList.add("hidden");
    const tbody = document.getElementById("tbodyResultados");
    if (tbody) tbody.innerHTML = "";
    const contador = document.getElementById("contadorResultados");
    if (contador) contador.textContent = "0 registros";
}


function limpiarSeleccion() {
    documentoSeleccionado = null;
    document.getElementById("panelGeneracion")?.classList.add("hidden");
    document.getElementById("panelPreview")?.classList.add("hidden");
    document.getElementById("panelGrupal")?.classList.add("hidden");
    ["correoAsunto", "correoCuerpo", "correoDestinatarios"].forEach(id => {
        const input = document.getElementById(id);
        if (input) input.value = "";
    });
    const correoHtml = document.getElementById("correoCuerpoHtml");
    if (correoHtml) correoHtml.innerHTML = "";
    document.getElementById("condonacionEstimada").textContent = "S/ --";
    document.getElementById("montoMinimo").textContent = "S/ --";
    document.getElementById("deudaTotal").textContent = "S/ --";
    const tbodyMontos = document.getElementById("tbodyMontosGrupales");
    if (tbodyMontos) tbodyMontos.innerHTML = "";
    const total = document.getElementById("totalGrupalPreview");
    if (total) total.textContent = "S/ 0.00";
    actualizarModoDocumento();
}


function limpiarCamposGeneracion() {
    [
        "cancelacion",
        "encargadoProvinciaParticipante",
        "encargadoNombreLibre",
        "encargadoDniLibre",
        "encargadoDireccionLibre",
        "encargadoDistritoLibre",
        "encargadoProvinciaLibre",
    ].forEach(id => {
        const input = document.getElementById(id);
        if (input) input.value = "";
    });

    const excepcion = document.getElementById("excepcionDocumento");
    if (excepcion) excepcion.checked = false;

    const modoParticipante = document.querySelector("input[name='encargadoModo'][value='participante']");
    if (modoParticipante) modoParticipante.checked = true;
    actualizarModoEncargado();

    document.querySelectorAll(".monto-grupal-input").forEach(input => {
        input.value = "";
    });
    document.querySelectorAll(".integrante-activo-input").forEach(input => {
        input.checked = true;
    });
}


function actualizarUltimaGeneracion() {
    const target = document.getElementById("ultimaGeneracion");
    if (!target) return;

    target.textContent = new Date().toLocaleString("es-PE", {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
    });
}


function mostrarEstado(message, type) {
    const box = document.getElementById("estadoDocumento");
    if (!box) return;

    box.className = `documentos-estado ${type}`;
    box.textContent = message;
    box.classList.remove("hidden");

    if (type === "success") {
        setTimeout(ocultarEstado, 3000);
    }
}


function ocultarEstado() {
    const box = document.getElementById("estadoDocumento");
    if (!box) return;

    box.className = "documentos-estado hidden";
    box.textContent = "";
}


function money(value) {
    const number = Number(value || 0);
    return `S/ ${number.toLocaleString("es-PE", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}


function moneyNumber(value) {
    const number = Number(value || 0);
    return number.toLocaleString("es-PE", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}


function fechaCortaHoy() {
    return new Date().toLocaleDateString("es-PE", {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
    });
}


function fechaLargaHoy(capitalizarMes = false) {
    const partes = new Date().toLocaleDateString("es-PE", {
        day: "numeric",
        month: "long",
        year: "numeric",
    }).split(" de ");
    if (capitalizarMes && partes.length === 3) {
        partes[1] = partes[1].charAt(0).toUpperCase() + partes[1].slice(1);
    }
    return partes.join(" de ");
}


function valueOrDash(value) {
    if (value === null || value === undefined || value === "") return "--";
    return String(value);
}


function escapeHtml(value) {
    return valueOrDash(value)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}


function escapeAttr(value) {
    return escapeHtml(value).replace(/`/g, "&#096;");
}
