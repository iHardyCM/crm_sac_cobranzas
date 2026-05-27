const BASE_URL = `${window.location.protocol}//${window.location.hostname}:8000`;

let carteras = [];
let historial = [];

document.addEventListener("DOMContentLoaded", () => {
    if (!exigirSesion()) return;

    document.getElementById("usuarioCarga").value =
        localStorage.getItem("dni") || localStorage.getItem("agente") || "SIN_USUARIO";
    document.getElementById("usuarioVista").innerText = localStorage.getItem("agente") || "Usuario";
    document.getElementById("perfilVista").innerText = localStorage.getItem("tipo") || "CRM";

    document.getElementById("formCanales").addEventListener("submit", importarCanal);
    document.getElementById("archivoCanal").addEventListener("change", actualizarNombreArchivo);
    document.getElementById("buscarHistorial").addEventListener("input", pintarHistorial);

    cargarCarteras();
    cargarHistorial();
});

async function cargarCarteras() {
    const select = document.getElementById("carteraSelect");
    try {
        const res = await fetch(`${BASE_URL}/canales/carteras`);
        const json = await res.json();
        if (!res.ok) throw new Error(json.detail || "No se pudieron cargar carteras.");

        carteras = json.data || [];
        select.innerHTML = `<option value="">Seleccionar cartera</option>` + carteras.map(item =>
            `<option value="${item.idcartera}" data-cartera="${escapeHtml(item.cartera)}">${item.idcartera} - ${escapeHtml(item.cartera)}</option>`
        ).join("");
    } catch (error) {
        select.innerHTML = `<option value="">Error cargando carteras</option>`;
        mostrarMensaje(error.message, "error");
    }
}

async function importarCanal(event) {
    event.preventDefault();

    const canal = document.getElementById("canal").value;
    const carteraSelect = document.getElementById("carteraSelect");
    const idcartera = carteraSelect.value;
    const cartera = carteraSelect.selectedOptions[0]?.dataset?.cartera || "";
    const archivo = document.getElementById("archivoCanal").files[0];

    if (!canal || !idcartera || !archivo) {
        mostrarMensaje("Selecciona canal, cartera y archivo antes de importar.", "error");
        return;
    }

    const data = new FormData();
    data.set("canal", canal);
    data.set("idcartera", idcartera);
    data.set("cartera", cartera);
    data.set("usuario_carga", document.getElementById("usuarioCarga").value || "SIN_USUARIO");
    data.set("archivo", archivo);

    const btn = document.getElementById("btnImportar");
    try {
        btn.disabled = true;
        btn.innerText = "Importando...";

        const res = await fetch(`${BASE_URL}/canales/importar`, { method: "POST", body: data });
        const json = await res.json();

        if (!res.ok) {
            const detalle = json.error || json.detail || "No se pudo importar el archivo.";
            throw new Error(detalle);
        }

        pintarResumen(json);
        mostrarMensaje(`${json.mensaje}. ID Carga: ${json.id_carga} | Archivo: ${json.archivo_nombre}`, "success");
        limpiarFormulario(false);
        await cargarHistorial();
    } catch (error) {
        mostrarMensaje(error.message, "error");
    } finally {
        btn.disabled = false;
        btn.innerText = "Importar";
    }
}

async function cargarHistorial() {
    try {
        const res = await fetch(`${BASE_URL}/canales/importaciones`);
        const json = await res.json();
        if (!res.ok) throw new Error(json.detail || "No se pudo cargar historial.");
        historial = json.data || [];
        pintarHistorial();
        if (historial.length) {
            pintarResumen(historial[0]);
        }
    } catch (error) {
        mostrarMensaje(error.message, "error");
    }
}

function pintarHistorial() {
    const tbody = document.getElementById("tablaHistorial");
    const filtro = document.getElementById("buscarHistorial").value.trim().toLowerCase();
    const data = historial.filter(item => {
        const texto = `${item.canal} ${item.cartera} ${item.archivo_nombre} ${item.usuario_carga}`.toLowerCase();
        return texto.includes(filtro);
    });

    tbody.innerHTML = data.length
        ? data.map(item => `
            <tr>
                <td>${item.id_carga}</td>
                <td>${formatearFechaHora(item.fecha_carga)}</td>
                <td><span class="canal">${item.canal}</span></td>
                <td>${item.idcartera} - ${escapeHtml(item.cartera || "-")}</td>
                <td class="archivo">${escapeHtml(item.archivo_nombre || "-")}</td>
                <td>${escapeHtml(item.usuario_carga || "-")}</td>
                <td>${numero(item.total_registros)}</td>
                <td class="ok">${numero(item.registros_validos)}</td>
                <td class="bad">${numero(item.registros_error)}</td>
                <td>${badge(item.estado)}</td>
                <td>
                    <button class="btn-table" onclick="verDetalle(${item.id_carga})">Ver detalle</button>
                    <button class="btn-table secondary" type="button">Errores</button>
                </td>
            </tr>
        `).join("")
        : `<tr><td colspan="11" class="sin-data">No hay importaciones registradas.</td></tr>`;
}

async function verDetalle(idCarga) {
    try {
        const res = await fetch(`${BASE_URL}/canales/importaciones/${idCarga}`);
        const json = await res.json();
        if (!res.ok) throw new Error(json.detail || "No se pudo cargar detalle.");

        const cab = json.cabecera || {};
        document.getElementById("modalTitulo").innerText = `Detalle de Importación - ID Carga: ${cab.id_carga}`;
        document.getElementById("modalMeta").innerText =
            `Canal: ${cab.canal} | Cartera: ${cab.idcartera} - ${cab.cartera || "-"} | Archivo: ${cab.archivo_nombre || "-"} | Usuario: ${cab.usuario_carga || "-"}`;

        const tbody = document.getElementById("tablaDetalle");
        const detalle = json.detalle || [];
        tbody.innerHTML = detalle.length
            ? detalle.map((item, index) => `
                <tr>
                    <td>${index + 1}</td>
                    <td>${escapeHtml(item.documento || "-")}</td>
                    <td>${escapeHtml(item.telefono || "-")}</td>
                    <td>${escapeHtml(item.email || "-")}</td>
                    <td class="mensaje">${escapeHtml(item.mensaje || "-")}</td>
                    <td>${badge(item.estado_registro)}</td>
                    <td class="bad">${escapeHtml(item.observacion || "-")}</td>
                </tr>
            `).join("")
            : `<tr><td colspan="7" class="sin-data">Sin detalle para mostrar.</td></tr>`;

        document.getElementById("modalDetalle").classList.remove("oculto");
    } catch (error) {
        mostrarMensaje(error.message, "error");
    }
}

function cerrarDetalle() {
    document.getElementById("modalDetalle").classList.add("oculto");
}

function pintarResumen(data) {
    document.getElementById("resTotal").innerText = numero(data.total_registros);
    document.getElementById("resValidos").innerText = numero(data.registros_validos);
    document.getElementById("resErrores").innerText = numero(data.registros_error);
    document.getElementById("resFecha").innerText = formatearFechaHora(data.fecha_carga);
}

function limpiarFormulario(limpiarMensaje = true) {
    document.getElementById("formCanales").reset();
    document.getElementById("usuarioCarga").value =
        localStorage.getItem("dni") || localStorage.getItem("agente") || "SIN_USUARIO";
    actualizarNombreArchivo();
    if (limpiarMensaje) {
        document.getElementById("mensajeResultado").classList.add("oculto");
    }
}

function actualizarNombreArchivo() {
    const archivo = document.getElementById("archivoCanal").files[0];
    document.getElementById("nombreArchivo").innerText = archivo?.name || "Ningún archivo seleccionado";
}

function mostrarMensaje(mensaje, tipo) {
    const box = document.getElementById("mensajeResultado");
    box.className = `result-message ${tipo}`;
    box.innerText = mensaje;
}

function toggleSidebar() {
    document.body.classList.toggle("sidebar-hidden");
}

function irInicio() {
    window.location.href = "home.html";
}

function badge(value) {
    const texto = String(value || "-").toUpperCase();
    const clase = texto === "ERROR" ? "error" : texto === "VALIDO" || texto === "PROCESADO" ? "ok" : "neutral";
    return `<span class="badge ${clase}">${texto}</span>`;
}

function numero(value) {
    return Number(value || 0).toLocaleString("es-PE");
}

function formatearFechaHora(value) {
    if (!value) return "-";
    const fecha = new Date(value);
    if (Number.isNaN(fecha.getTime())) return "-";
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
