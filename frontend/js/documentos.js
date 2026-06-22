// documento.js
const BASE_URL_DOCUMENTOS = `${window.location.protocol}//${window.location.hostname}:8000`;

let documentosResultados = [];
let documentoSeleccionado = null;

document.addEventListener("DOMContentLoaded", () => {
    cargarTiposDocumento();
    pintarFechaDocumentoHoy();

    document.getElementById("btnBuscar")?.addEventListener("click", buscarDatosDocumento);
    document.getElementById("btnLimpiar")?.addEventListener("click", limpiarVista);
    document.getElementById("btnGenerar")?.addEventListener("click", generarDocumento);
    document.getElementById("cancelacion")?.addEventListener("input", () => {
        actualizarCondonacion();
        pintarPreviewDocumento();
    });
    document.querySelectorAll("[data-formato]").forEach(button => {
        button.addEventListener("click", () => seleccionarFormato(button.dataset.formato));
    });

    ["dni", "operacion", "codigoGrupo", "codCreGrupal"].forEach(id => {
        document.getElementById(id)?.addEventListener("keydown", event => {
            if (event.key === "Enter") buscarDatosDocumento();
        });
    });
});


async function cargarTiposDocumento() {
    try {
        const response = await fetch(`${BASE_URL_DOCUMENTOS}/documentos/tipos`, { cache: "no-store" });
        const result = await response.json();

        if (!response.ok) {
            throw new Error(result.detail || "No se pudieron cargar los tipos de documento.");
        }

        const select = document.getElementById("documentoTipo");
        if (!select) return;

        select.innerHTML = (result.data || []).map(item => (
            `<option value="${escapeAttr(item.id)}">${escapeHtml(item.nombre)}</option>`
        )).join("");
    } catch (error) {
        mostrarEstado(error.message, "error");
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
            <td><button class="documentos-mini-btn" type="button" data-index="${index}">Seleccionar</button></td>
        `;
        tbody.appendChild(tr);
    });

    tbody.querySelectorAll("[data-index]").forEach(button => {
        button.addEventListener("click", () => seleccionarDocumento(Number(button.dataset.index)));
    });

    if (rows.length === 1) {
        seleccionarDocumento(0);
    }
}


function seleccionarDocumento(index) {
    documentoSeleccionado = documentosResultados[index];
    if (!documentoSeleccionado) return;

    document.getElementById("panelGeneracion")?.classList.remove("hidden");
    document.getElementById("clienteSeleccionado").textContent = `${valueOrDash(documentoSeleccionado.NomCliente)} - DNI ${valueOrDash(documentoSeleccionado.NumDocumento)}`;
    document.getElementById("operacionSeleccionada").textContent = `Operacion ${valueOrDash(documentoSeleccionado.Operacion)}`;
    document.getElementById("montoMinimo").textContent = money(documentoSeleccionado.MtoCancelacionCliente);
    document.getElementById("deudaTotal").textContent = money(documentoSeleccionado.DeudaTotal);

    const cancelacion = document.getElementById("cancelacion");
    const minimo = Number(documentoSeleccionado.MtoCancelacionCliente || 0);
    if (cancelacion) {
        cancelacion.min = String(minimo + 0.01);
        cancelacion.value = "";
        cancelacion.focus();
    }

    actualizarCondonacion();
    pintarPreviewDocumento();
}


function actualizarCondonacion() {
    const target = document.getElementById("condonacionEstimada");
    if (!target || !documentoSeleccionado) return;

    const deuda = Number(documentoSeleccionado.DeudaTotal || 0);
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
    const panel = document.getElementById("panelPreview");
    const preview = document.getElementById("documentoPreview");
    if (!panel || !preview || !documentoSeleccionado) return;

    const cancelacion = Number(document.getElementById("cancelacion")?.value || 0);
    const deuda = Number(documentoSeleccionado.DeudaTotal || 0);
    const condonacion = Math.max(deuda - cancelacion, 0);
    const fecha = new Date().toLocaleDateString("es-PE", {
        day: "2-digit",
        month: "long",
        year: "numeric",
    });
    const fechaCorta = new Date().toLocaleDateString("es-PE", {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
    });
    const distrito = documentoSeleccionado.DistritoPrincipal || documentoSeleccionado.Distrito_Principal || documentoSeleccionado.Distrito || "";

    panel.classList.remove("hidden");
    preview.innerHTML = `
        <h1>Transacción extrajudicial y Cancelación de Deuda</h1>
        <p>Conste por el presente documento una Transacción Extrajudicial y Cancelación de Deuda, que celebran de una parte la Empresa de cobranza BIZNESCOB, con RUC 20602593640, con domicilio en Enrique Encinas 284 la victoria y representado por el sr(a) LUIS PORTUGUEZ BERROCAL identificado con DNI 10416012, por encargo de COMPARTAMOS BANCO S.A.,  en adelante COMPARTAMOS, con domicilio en Av. Paseo de la Republica N° 5895 – Interior 1301, distrito de Mira flores, provincia y departamento de Lima, inscrita en la Partida Nro. 13777030 del Registro de Personas Jurídicas de la Zona Registral Nro. IX - Sede Lima y de otra parte el/la Sr (a) <strong>${escapeHtml(documentoSeleccionado.NomCliente)}</strong> identificado con DNI N°.<strong>${escapeHtml(documentoSeleccionado.NumDocumento)}</strong>, con domicilio en ${escapeHtml(documentoSeleccionado.DireccionPrincipal || "")}, distrito de ${escapeHtml(distrito)}, a quien en adelante se le denominara  EL/LA/DEUDOR/A, en los términos y condiciones siguientes:</p>
        <p><strong><u>PRIMERA.-</u></strong> EL DEUDOR reconoce adeudar a COMPARTAMOS BANCO el crédito <strong>${escapeHtml(documentoSeleccionado.Operacion)}</strong>, cuyo  importe asciende  a la suma total de S/  <strong>${moneyNumber(documentoSeleccionado.DeudaTotal)}</strong>,  según liquidación a la fecha.</p>
        <p><strong><u>SEGUNDA-</u></strong> De conformidad con lo señalado en la cláusula anterior EL DEUDOR se obliga a cancelar a   COMPARTAMOS BANCO la deuda antes descrita de la siguiente manera:</p>
        <table>
            <thead><tr><th>Monto</th><th>Fecha de Pago/ Cancelación</th></tr></thead>
            <tbody><tr><td>S/ ${moneyNumber(cancelacion)}</td><td>${fechaCorta}</td></tr></tbody>
        </table>
        <p>La cancelación de la suma antes detallada está sujeta al pago acordado en el párrafo que antecede.</p>
        <p><strong><u>TERCERA .-</u></strong> Sin perjuicio de lo señalado, COMPARTAMOS se reserva el derecho de iniciar, interponer o continuar con las acciones administrativas, legales o judiciales en caso de que el EL/LA/DEUDOR/A incumpla las obligaciones que por el presente documento asume; COMPARTAMOS quedará expedito para su cobro de conformidad con lo estipulado por inciso 8 del artículo 688 del Código Proceso Civil.</p>
        <p><strong><u>CUARTA .-</u></strong> Las garantías y/o fianzas solidarias constituidas en respaldo de la obligación antes señalada subsisten en tanto no se cancele totalmente la misma por el monto acordado, por cuanto la suscripción de presente convenio no constituye una novación de la obligación</p>
        <p><strong><u>QUINTA .-</u></strong> El incumplimiento o retraso en el pago del monto señalado en la cláusula segunda, a criterio de COMPARTAMOS, quedarán sin efecto los beneficios (descuentos u otros) otorgados a EL/LA/DEUDOR/A, recalculando los intereses y mora que se hayan generado posteriormente.</p>
        <p><strong><u>SÉXTA :</u></strong>  EL/LA/DEUDOR/A ratifica su voluntad expresada en el presente instrumento, dejando constancia que no    ha mediado vicio capaz  de invalidarlo.</p>
        <p class="preview-date">${fecha}</p>
        ${previewFirmas(documentoSeleccionado.NumDocumento)}
        <hr>
        <h2>NOTA DE ABONO</h2>
        <p>Por el presente documento COMPARTAMOS, concede condonación sobre la deuda de EL/LA/DEUDOR/A, según las condiciones ofrecidas en la en el presente documento.</p>
        <p class="preview-highlight">Sr(a):${escapeHtml(documentoSeleccionado.NomCliente)} con DNI Nº ${escapeHtml(documentoSeleccionado.NumDocumento)} por la suma de S/ ${moneyNumber(condonacion)}</p>
        <p>EL/LA/DEUDOR/A, acepta el descuento indicado, reduciendo la deuda vigente que se detalla en la presente transacción, la misma que mantiene su validez, si EL/LA/DEUDOR/A cumple todas las condiciones descritas en el documento.</p>
        <p>El descuento está sujeto al cumplimiento del pago de: S/ ${moneyNumber(cancelacion)} en las fechas y formas acordadas en la cláusula segunda.</p>
        ${previewFirmas(documentoSeleccionado.NumDocumento)}
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


async function generarDocumento() {
    if (!documentoSeleccionado) {
        mostrarEstado("Selecciona una operacion antes de generar.", "warning");
        return;
    }

    const cancelacion = Number(document.getElementById("cancelacion")?.value || 0);
    const minimo = Number(documentoSeleccionado.MtoCancelacionCliente || 0);

    if (!cancelacion || cancelacion <= minimo) {
        mostrarEstado(`La cancelacion debe ser mayor a ${money(minimo)}.`, "warning");
        return;
    }

    const formato = document.getElementById("formatoDocumento")?.value || "docx";
    mostrarEstado(`Generando documento ${formato.toUpperCase()}...`, "info");

    const payload = {
        documento_tipo: document.getElementById("documentoTipo")?.value || "transaccion_cancelacion",
        dni: documentoSeleccionado.NumDocumento ? String(documentoSeleccionado.NumDocumento) : "",
        operacion: documentoSeleccionado.Operacion ? String(documentoSeleccionado.Operacion) : "",
        cancelacion: cancelacion,
        fecha_pago: new Date().toISOString().slice(0, 10),
        formato: formato,
    };

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
    const cliente = documentoSeleccionado?.NomCliente || "cliente";
    return `${slugArchivo(tipoTexto)}_${slugArchivo(cliente)}.${formato}`;
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
    ["dni", "operacion", "codigoGrupo", "codCreGrupal", "cancelacion"].forEach(id => {
        const input = document.getElementById(id);
        if (input) input.value = "";
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
    document.getElementById("condonacionEstimada").textContent = "S/ --";
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
