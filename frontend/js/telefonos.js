const BASE_URL_TELEFONOS = `${window.location.protocol}//${window.location.hostname}:8000`;

let telefonosCache = [];
let telefonoSeleccionado = null;

document.addEventListener("DOMContentLoaded", () => {
    cargarFiltros();

    document.getElementById("btnBuscar")?.addEventListener("click", buscarTelefonos);
    document.getElementById("btnLimpiar")?.addEventListener("click", limpiarVista);
    document.getElementById("btnToggleFiltros")?.addEventListener("click", alternarFiltrosTelefonos);

    ["filtroCartera", "filtroWhatsapp", "filtroTimbra", "filtroTipo", "filtroOrigen"].forEach(id => {
        document.getElementById(id)?.addEventListener("change", actualizarContadorFiltros);
    });

    document.getElementById("txtBuscar")?.addEventListener("keydown", (event) => {
        if (event.key === "Enter") {
            buscarTelefonos();
        }
    });

    document.getElementById("btnCerrarDetalle")?.addEventListener("click", cerrarDetalleTelefonos);
    document.getElementById("telefonosDrawerBackdrop")?.addEventListener("click", cerrarDetalleTelefonos);
    document.getElementById("btnCopiarDetalle")?.addEventListener("click", () => copiarTelefono(telefonoSeleccionado?.TELEFONO));
    document.getElementById("btnLlamarTelefono")?.addEventListener("click", llamarTelefonoSeleccionado);
    document.getElementById("btnWhatsappTelefono")?.addEventListener("click", abrirWhatsappSeleccionado);
    document.getElementById("btnVerMejorOpcion")?.addEventListener("click", () => {
        if (telefonosCache[0]) verDetalle(telefonosCache[0]);
    });
    document.addEventListener("keydown", event => {
        if (event.key === "Escape") cerrarDetalleTelefonos();
    });

    actualizarContadorFiltros();
});

function alternarFiltrosTelefonos() {
    const panel = document.getElementById("panelFiltrosTelefonos");
    const button = document.getElementById("btnToggleFiltros");
    if (!panel || !button) return;

    const seAbrira = panel.classList.contains("hidden");
    panel.classList.toggle("hidden", !seAbrira);
    button.setAttribute("aria-expanded", String(seAbrira));
    button.classList.toggle("is-active", seAbrira);
}

function actualizarContadorFiltros() {
    const target = document.getElementById("contadorFiltros");
    if (!target) return;

    const activos = ["filtroCartera", "filtroWhatsapp", "filtroTimbra", "filtroTipo", "filtroOrigen"]
        .filter(id => valorFiltro(id) !== "TODOS").length;
    target.textContent = activos ? String(activos) : "5";
}


async function cargarFiltros() {
    try {
        const response = await fetch(`${BASE_URL_TELEFONOS}/telefonos/filtros`, { cache: "no-store" });
        const result = await response.json();

        if (!response.ok) {
            throw new Error(result.detail || "No se pudieron cargar filtros.");
        }

        const data = result.data || {};

        cargarSelectCarteras("filtroCartera", data.carteras || []);
        cargarSelectSimple("filtroWhatsapp", data.whatsapp || []);
        cargarSelectSimple("filtroTimbra", data.timbra || []);
        cargarSelectSimple("filtroTipo", data.tipo || []);
        cargarSelectSimple("filtroOrigen", data.origen || []);

    } catch (error) {
        console.error("Error cargando filtros:", error);
    }
}


function cargarSelectCarteras(id, items) {
    const select = document.getElementById(id);
    if (!select) return;

    select.innerHTML = `<option value="TODOS">Todas</option>`;

    items.forEach(item => {
        const option = document.createElement("option");
        option.value = item.idcartera;
        option.textContent = `${item.idcartera} - ${item.cartera}`;
        select.appendChild(option);
    });
}


function cargarSelectSimple(id, items) {
    const select = document.getElementById(id);
    if (!select) return;

    select.innerHTML = `<option value="TODOS">Todos</option>`;

    items.forEach(item => {
        const option = document.createElement("option");
        option.value = item;
        option.textContent = item;
        select.appendChild(option);
    });
}


function valorFiltro(id) {
    const value = document.getElementById(id)?.value;
    return value || "TODOS";
}


async function buscarTelefonos() {
    const q = document.getElementById("txtBuscar")?.value.trim();

    if (!q) {
        mostrarEstado("Ingresa un DNI, ID Cliente, nombre de cliente o teléfono.", "warning");
        return;
    }

    const params = new URLSearchParams({
        q: q,
        idcartera: valorFiltro("filtroCartera"),
        whatsapp: valorFiltro("filtroWhatsapp"),
        timbra: valorFiltro("filtroTimbra"),
        tipo: valorFiltro("filtroTipo"),
        origen: valorFiltro("filtroOrigen"),
    });

    mostrarEstado("Consultando teléfonos activos...", "info");

    try {
        const url = `${BASE_URL_TELEFONOS}/telefonos/buscar?${params.toString()}`;
        console.log("Consultando URL:", url);

        const response = await fetch(url, { cache: "no-store" });
        const result = await response.json();

        console.log("HTTP status:", response.status);
        console.log("Respuesta completa:", result);

        if (!response.ok) {
            throw new Error(result.detail || "Error consultando teléfonos.");
        }

        const data = result.data;

        if (!data || !Array.isArray(data.telefonos) || data.telefonos.length === 0) {
            limpiarResultados();
            mostrarEstado("No se encontraron teléfonos activos para la búsqueda.", "warning");
            return;
        }

        pintarResumen(data.resumen || {}, data.telefonos || []);
        pintarTelefonos(data.telefonos || []);
        pintarRelacionados(data.relacionados || []);

        actualizarUltimaConsulta();
        ocultarEstado();

    } catch (error) {
        console.error("Error real en búsqueda:", error);
        console.error("Stack:", error.stack);
        mostrarEstado(error.message || "Error consultando teléfonos.", "error");
    }
}


function pintarResumen(resumen, telefonos = []) {
    const panel = document.getElementById("panelResumen");
    if (!panel) return;

    panel.classList.remove("hidden");

    const primerTelefono = Array.isArray(telefonos) && telefonos.length > 0 ? telefonos[0] : {};
    const nombreResumen =
        resumen.nombre_cliente ||
        resumen.NOMBRE_CLIENTE ||
        resumen.nom_cli ||
        resumen.NOM_CLI ||
        nombreCliente(primerTelefono);

    document.getElementById("resumenDni").textContent = valueOrDash(resumen.dni);
    document.getElementById("resumenIdCliente").textContent = valueOrDash(resumen.idcliente);
    document.getElementById("resumenNombreCliente").textContent = valueOrDash(nombreResumen);
    document.getElementById("resumenCarteras").textContent = Array.isArray(resumen.carteras)
        ? resumen.carteras.join(", ")
        : "--";

    const total = Number(resumen.total_telefonos || 0);
    const osiptel = Number(resumen.con_osiptel || 0);
    const whatsapp = Number(resumen.con_whatsapp || 0);
    const timbran = Number(resumen.timbran || 0);

    document.getElementById("kpiTotal").textContent = total;
    document.getElementById("kpiOsiptel").textContent = osiptel;
    document.getElementById("kpiWhatsapp").textContent = whatsapp;
    document.getElementById("kpiTimbran").textContent = timbran;
    document.getElementById("kpiRecomendado").textContent = valueOrDash(resumen.telefono_recomendado);

    document.getElementById("kpiScore").textContent = resumen.score_recomendado !== null && resumen.score_recomendado !== undefined
        ? `Score ${resumen.score_recomendado}`
        : "Score --";

    document.getElementById("kpiWhatsappPct").textContent = total ? `${Math.round((whatsapp / total) * 100)}%` : "0%";
    document.getElementById("kpiOsiptelPct").textContent = total ? `${Math.round((osiptel / total) * 100)}%` : "0%";
    document.getElementById("kpiTimbranPct").textContent = total ? `${Math.round((timbran / total) * 100)}%` : "0%";

    const alerta = document.getElementById("alertaResumen");

    if (!alerta) return;

    if (resumen.tiene_compartidos) {
        alerta.classList.remove("hidden");
        alerta.innerHTML = `
            <strong>Atención:</strong> uno o más teléfonos aparecen asociados a otros DNI.
            Validar origen e identidad antes de registrar contacto efectivo.
        `;
    } else if (resumen.tiene_multicartera) {
        alerta.classList.remove("hidden");
        alerta.innerHTML = `
            <strong>Nota:</strong> el cliente tiene teléfonos presentes en más de una cartera.
            Validar cartera antes de registrar gestión.
        `;
    } else {
        alerta.classList.add("hidden");
        alerta.innerHTML = "";
    }
}

function obtenerClasePrioridadDetalle(prioridad) {
    const text = normalize(prioridad);

    if (text === "V") return "telefono-prioridad-v";
    if (text === "A") return "telefono-prioridad-a";
    if (text === "P" || text === "Q") return "telefono-prioridad-q";
    if (text === "T") return "telefono-prioridad-t";
    if (text === "R") return "telefono-prioridad-r";
    if (text === "F") return "telefono-prioridad-f";

    return "telefono-prioridad-default";
}

function pintarTelefonos(telefonos) {
    const tbody = document.getElementById("tbodyTelefonos");
    const contador = document.getElementById("contadorTelefonos");

    if (!tbody || !contador) return;

    telefonosCache = telefonos || [];

    tbody.innerHTML = "";
    contador.textContent = `${telefonosCache.length} registro${telefonosCache.length === 1 ? "" : "s"}`;

    telefonosCache.forEach((item, index) => {
        const tr = document.createElement("tr");
        tr.dataset.index = String(index);

        tr.innerHTML = `
            <td>${badgePrioridad(item.PRIORIDAD)}</td>
            <td>
                <button class="phone-link" type="button" data-index="${index}">
                    ${valueOrDash(item.TELEFONO)}
                </button>
                ${item.RECOMENDACION === "Recomendado para contacto" ? `<small class="tag-recommended">RECOMENDADO</small>` : ""}
            </td>
            <td>
                <strong>${valueOrDash(nombreCliente(item))}</strong>
                <small>DNI ${valueOrDash(item.DNI)} · ID ${valueOrDash(item.IDCLIENTE)} · ${valueOrDash(item.IDCARTERA)} - ${valueOrDash(item.CARTERA)}</small>
            </td>
            <td class="telefonos-signals">
                <span title="WhatsApp">WA ${badgeSiNo(item.WHATSAPP)}</span>
                <span title="Timbra">T ${badgeTimbra(item.TIMBRA)}</span>
                <span title="Osiptel">OS ${badgeOsiptel(item.OSIPTEL)}</span>
            </td>
            <td>${badgeScore(item.SCORE_CONTACTO)}</td>
            <td>${badgeRecomendacion(item.RECOMENDACION)}</td>
            <td>
                <div class="actions">
                    <button type="button" data-copy="${valueOrDash(item.TELEFONO)}" title="Copiar teléfono">⧉</button>
                    <button type="button" data-index="${index}" title="Ver detalle">👁</button>
                </div>
            </td>
        `;

        tbody.appendChild(tr);

        tr.addEventListener("click", event => {
            if (event.target.closest("button")) return;
            verDetalle(telefonosCache[index]);
        });
    });

    pintarMejorOpcionTelefonos();

    tbody.querySelectorAll("[data-index]").forEach(btn => {
        btn.addEventListener("click", () => {
            const index = Number(btn.dataset.index);
            verDetalle(telefonosCache[index]);
        });
    });

    tbody.querySelectorAll("[data-copy]").forEach(btn => {
        btn.addEventListener("click", () => {
            copiarTelefono(btn.dataset.copy);
        });
    });
}


function pintarRelacionados(relacionados) {
    const panel = document.getElementById("panelRelacionados");
    const tbody = document.getElementById("tbodyRelacionados");
    const count = document.getElementById("relacionadosCount");

    if (!panel || !tbody || !count) return;

    if (!relacionados || relacionados.length === 0) {
        panel.classList.add("hidden");
        tbody.innerHTML = "";
        count.textContent = "0";
        return;
    }

    panel.classList.remove("hidden");
    tbody.innerHTML = "";
    count.textContent = relacionados.length;

    relacionados.forEach(item => {
        const tr = document.createElement("tr");

        tr.innerHTML = `
            <td>${valueOrDash(item.DNI)}</td>
            <td>${valueOrDash(item.IDCLIENTE)}</td>
            <td>${valueOrDash(nombreCliente(item))}</td>
            <td>
                <span class="badge badge-blue">${valueOrDash(item.IDCARTERA)}</span>
                <small>${valueOrDash(item.CARTERA)}</small>
            </td>
            <td>${badgeOrigen(item.ORIGEN)}</td>
        `;

        tbody.appendChild(tr);
    });
}


function verDetalle(item) {
    if (!item) return;

    telefonoSeleccionado = item;
    const selectedIndex = telefonosCache.indexOf(item);
    document.querySelectorAll("#tbodyTelefonos tr[data-index]").forEach(row => {
        row.classList.toggle("is-selected", Number(row.dataset.index) === selectedIndex);
    });
    document.getElementById("panelDetalle")?.classList.remove("hidden");
    document.getElementById("telefonosDrawerBackdrop")?.classList.remove("hidden");
    document.body.classList.add("telefonos-drawer-open");

    // document.getElementById("detalleTelefono").textContent = valueOrDash(item.TELEFONO);
    const detalleTelefono = document.getElementById("detalleTelefono");
    detalleTelefono.textContent = valueOrDash(item.TELEFONO);
    detalleTelefono.className = obtenerClasePrioridadDetalle(item.PRIORIDAD);

    const detallePhoneCircle = document.getElementById("detallePhoneCircle");

    if (detallePhoneCircle) {
        detallePhoneCircle.className = `telefonos-phone-circle ${obtenerClasePrioridadDetalle(item.PRIORIDAD)}`;
    }

    document.getElementById("detalleDni").textContent = valueOrDash(item.DNI);
    document.getElementById("detalleIdCliente").textContent = valueOrDash(item.IDCLIENTE);
    document.getElementById("detalleNombreCliente").textContent = valueOrDash(nombreCliente(item));
    document.getElementById("detalleCartera").textContent = `${valueOrDash(item.IDCARTERA)} - ${valueOrDash(item.CARTERA)}`;
    document.getElementById("detalleTipo").textContent = valueOrDash(item.TIPO_FONO);
    document.getElementById("detalleWhatsapp").innerHTML = badgeSiNo(item.WHATSAPP);
    document.getElementById("detalleTimbra").innerHTML = badgeTimbra(item.TIMBRA);
    document.getElementById("detalleOsiptel").innerHTML = badgeOsiptel(item.OSIPTEL);
    document.getElementById("detalleOrigen").innerHTML = badgeOrigen(item.ORIGEN);
    document.getElementById("detalleTipoBase").textContent = valueOrDash(item.TIPO_BASE);
    document.getElementById("detalleAnio").textContent = valueOrDash(item["AÑO_FECH_TELF"]);
    document.getElementById("detalleAnomes").textContent = valueOrDash(item["AÑOMES_TELF"]);
    document.getElementById("detalleTEmp").textContent = valueOrDash(item.T_EMP);
    document.getElementById("detallePrioridad").textContent = valueOrDash(item.PRIORIDAD);
    document.getElementById("detalleScore").innerHTML = badgeScore(item.SCORE_CONTACTO);

    const estado = document.getElementById("detalleEstado");
    if (!estado) return;

    estado.className = "telefonos-estado-operativo";

    if (item.RECOMENDACION === "Recomendado para contacto") {
        estado.classList.add("ok");
    } else if (item.RECOMENDACION === "Buena alternativa") {
        estado.classList.add("good");
    } else if (item.RECOMENDACION === "Usar validando identidad") {
        estado.classList.add("warning");
    } else {
        estado.classList.add("bad");
    }

    estado.textContent = item.RECOMENDACION || "--";

    const telefonoDisponible = normalizarTelefonoAccion(item.TELEFONO);
    const whatsappDisponible = esWhatsappDisponible(item.WHATSAPP) && Boolean(telefonoDisponible);
    document.getElementById("btnCopiarDetalle")?.toggleAttribute("disabled", !telefonoDisponible);
    document.getElementById("btnLlamarTelefono")?.toggleAttribute("disabled", !telefonoDisponible);
    document.getElementById("btnWhatsappTelefono")?.toggleAttribute("disabled", !whatsappDisponible);
}

function pintarMejorOpcionTelefonos() {
    const panel = document.getElementById("mejorOpcionTelefonos");
    const numero = document.getElementById("mejorOpcionNumero");
    const contexto = document.getElementById("mejorOpcionContexto");
    if (!panel || !numero || !contexto) return;

    const mejor = telefonosCache[0];
    if (!mejor) {
        panel.classList.add("hidden");
        return;
    }

    const señales = [];
    if (esWhatsappDisponible(mejor.WHATSAPP)) señales.push("WhatsApp disponible");
    if (Number(mejor.TIMBRA || 0) > 0) señales.push(`Timbra ${mejor.TIMBRA}`);
    señales.push(`Score ${valueOrDash(mejor.SCORE_CONTACTO)}`);

    numero.textContent = valueOrDash(mejor.TELEFONO);
    contexto.textContent = señales.join(" · ");
    panel.classList.remove("hidden");
}

function cerrarDetalleTelefonos() {
    document.getElementById("panelDetalle")?.classList.add("hidden");
    document.getElementById("telefonosDrawerBackdrop")?.classList.add("hidden");
    document.body.classList.remove("telefonos-drawer-open");
}

function normalizarTelefonoAccion(value) {
    const digits = String(value || "").replace(/\D/g, "");
    return digits.length >= 7 ? digits : "";
}

function esWhatsappDisponible(value) {
    const text = normalize(value);
    return text === "SI" || text === "SÍ";
}

function llamarTelefonoSeleccionado() {
    const telefono = normalizarTelefonoAccion(telefonoSeleccionado?.TELEFONO);
    if (!telefono) return;
    window.location.href = `tel:${telefono}`;
}

function abrirWhatsappSeleccionado() {
    const telefono = normalizarTelefonoAccion(telefonoSeleccionado?.TELEFONO);
    if (!telefono || !esWhatsappDisponible(telefonoSeleccionado?.WHATSAPP)) return;

    const telefonoWhatsapp = telefono.length === 9 ? `51${telefono}` : telefono;
    window.open(`https://wa.me/${telefonoWhatsapp}`, "_blank", "noopener,noreferrer");
}


function limpiarVista() {
    document.getElementById("txtBuscar").value = "";

    document.getElementById("filtroCartera").value = "TODOS";
    document.getElementById("filtroWhatsapp").value = "TODOS";
    document.getElementById("filtroTimbra").value = "TODOS";
    document.getElementById("filtroTipo").value = "TODOS";
    document.getElementById("filtroOrigen").value = "TODOS";

    actualizarContadorFiltros();

    limpiarResultados();
    ocultarEstado();
}


function limpiarResultados() {
    document.getElementById("panelResumen")?.classList.add("hidden");
    cerrarDetalleTelefonos();
    document.getElementById("panelRelacionados")?.classList.add("hidden");

    const tbody = document.getElementById("tbodyTelefonos");
    if (tbody) {
        tbody.innerHTML = `
            <tr>
                <td colspan="7" class="telefonos-empty-table">
                    Realiza una búsqueda para ver teléfonos activos.
                </td>
            </tr>
        `;
    }

    const tbodyRelacionados = document.getElementById("tbodyRelacionados");
    if (tbodyRelacionados) tbodyRelacionados.innerHTML = "";

    const contador = document.getElementById("contadorTelefonos");
    if (contador) contador.textContent = "0 registros";

    document.getElementById("mejorOpcionTelefonos")?.classList.add("hidden");
}


function copiarTelefono(telefono) {
    if (!telefono || telefono === "--") return;

    navigator.clipboard.writeText(telefono)
        .then(() => mostrarEstado(`Teléfono ${telefono} copiado.`, "success"))
        .catch(() => mostrarEstado("No se pudo copiar el teléfono.", "error"));
}


function actualizarUltimaConsulta() {
    const now = new Date();

    const target = document.getElementById("ultimaConsulta");
    if (!target) return;

    target.textContent = now.toLocaleString("es-PE", {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit"
    });
}


function mostrarEstado(message, type) {
    const box = document.getElementById("estadoConsulta");

    if (!box) {
        console.warn("No existe #estadoConsulta");
        return;
    }

    box.className = `telefonos-estado ${type}`;
    box.textContent = message;
    box.classList.remove("hidden");

    if (type === "success") {
        setTimeout(() => ocultarEstado(), 2500);
    }
}


function ocultarEstado() {
    const box = document.getElementById("estadoConsulta");
    if (!box) return;

    box.className = "telefonos-estado hidden";
    box.textContent = "";
}


function valueOrDash(value) {
    if (value === null || value === undefined || value === "") return "--";
    return String(value);
}


function nombreCliente(item) {
    return item?.NOMBRE_CLIENTE || item?.nom_cli || item?.NOM_CLI || item?.nombre_cliente || null;
}


function normalize(value) {
    return valueOrDash(value).trim().toUpperCase();
}


function badgePrioridad(value) {
    const text = normalize(value);
    let cls = "badge-gray";
    let title = "Sin clasificación";

    if (text === "V") {
        cls = "badge-green";
        title = "Verde: contacto efectivo";
    } else if (text === "A") {
        cls = "badge-yellow";
        title = "Amarillo: no contesta";
    } else if (text === "P" || text === "Q") {
        cls = "badge-gray";
        title = "Plomo: nuevo / sin gestión";
    } else if (text === "T") {
        cls = "badge-turquoise";
        title = "Turqueza: tercero / familiar";
    } else if (text === "R") {
        cls = "badge-red";
        title = "Rojo: equivocado";
    } else if (text === "F") {
        cls = "badge-fuchsia";
        title = "Fucsia: fallado";
    }

    return `<span class="priority ${cls}" title="${title}">${valueOrDash(value)}</span>`;
}


function badgeSiNo(value) {
    const text = normalize(value);

    if (text === "SI" || text === "SÍ") {
        return `<span class="badge badge-green">Sí</span>`;
    }

    if (text === "LN") {
        return `<span class="badge badge-gray">LN</span>`;
    }

    if (text === "SV") {
        return `<span class="badge badge-gray">SV</span>`;
    }

    return `<span class="badge badge-red">No</span>`;
}


function badgeTimbra(value) {
    const n = Number(value || 0);
    let cls = "badge-red";

    if (n >= 4) cls = "badge-green";
    else if (n === 3) cls = "badge-orange";
    else if (n === 2) cls = "badge-yellow";
    else if (n <= 1) cls = "badge-red";

    return `<span class="badge ${cls}">${valueOrDash(value)}</span>`;
}


function badgeOsiptel(value) {
    const text = normalize(value);

    if (text === "SI" || text === "SÍ") {
        return `<span class="badge badge-green">Sí</span>`;
    }

    if (text === "NO") {
        return `<span class="badge badge-gray">No</span>`;
    }

    if (text === "LN") {
        return `<span class="badge badge-gray">LN</span>`;
    }

    if (text === "SV") {
        return `<span class="badge badge-gray">SV</span>`;
    }

    return `<span class="badge badge-gray">${valueOrDash(value)}</span>`;
}


function badgeOrigen(value) {
    const text = valueOrDash(value);
    const upper = normalize(value);

    if (upper === "EMPRESA") return `<span class="badge badge-purple">${text}</span>`;
    if (upper === "AVAL") return `<span class="badge badge-blue">${text}</span>`;
    if (upper === "CONYUGE") return `<span class="badge badge-blue">${text}</span>`;
    if (upper === "REP LEGAL") return `<span class="badge badge-orange">${text}</span>`;
    if (upper === "HERMANO") return `<span class="badge badge-blue">${text}</span>`;
    if (upper === "BASES INTERNAS") return `<span class="badge badge-green">${text}</span>`;
    if (upper === "SEARCH") return `<span class="badge badge-gray">${text}</span>`;

    return `<span class="badge badge-gray">${text}</span>`;
}


function badgeCondicion(value) {
    const text = valueOrDash(value);
    const upper = normalize(value);

    if (upper.includes("ÚNICO") || upper.includes("UNICO")) {
        return `<span class="badge badge-green">${text}</span>`;
    }

    if (upper.includes("MULTICARTERA")) {
        return `<span class="badge badge-orange">${text}</span>`;
    }

    if (
        upper.includes("AVAL") ||
        upper.includes("CÓNYUGE") ||
        upper.includes("CONYUGE") ||
        upper.includes("REPRESENTANTE") ||
        upper.includes("HERMANO")
    ) {
        return `<span class="badge badge-blue">${text}</span>`;
    }

    if (upper.includes("COMPARTIDO")) {
        return `<span class="badge badge-red">${text}</span>`;
    }

    return `<span class="badge badge-gray">${text}</span>`;
}


function badgeScore(value) {
    const n = Number(value || 0);

    if (n >= 80) return `<span class="badge badge-green">${n}</span>`;
    if (n >= 60) return `<span class="badge badge-blue">${n}</span>`;
    if (n >= 40) return `<span class="badge badge-orange">${n}</span>`;

    return `<span class="badge badge-red">${n}</span>`;
}


function badgeRecomendacion(value) {
    const text = valueOrDash(value);

    if (text === "Recomendado para contacto") {
        return `<span class="badge badge-green">${text}</span>`;
    }

    if (text === "Buena alternativa") {
        return `<span class="badge badge-blue">${text}</span>`;
    }

    if (text === "Usar validando identidad") {
        return `<span class="badge badge-orange">${text}</span>`;
    }

    if (text === "Baja confiabilidad") {
        return `<span class="badge badge-red">${text}</span>`;
    }

    return `<span class="badge badge-gray">${text}</span>`;
}
