// pagos.js

const BASE_URL = `${window.location.protocol}//${window.location.hostname}:8000`;

let idImportacionActual = null;
let toastTimer = null;
let historialData = [];
let cortesActivosData = [];
let historialModo = "activos";
let historialPaginaActual = 1;
const HISTORIAL_PAGE_SIZE = 8;
const CORTES_ESPERADOS = [
    { idcartera: 112, label: "MiBanco", formato: "MIBANCO" },
    { idcartera: 117, label: "Interbank", formato: "INTERBANK" },
    { idcartera: 132, label: "Financiera OH", formato: "FINANCIERA_OH" },
    { idcartera: 126, label: "Compartamos Vigente IND", formato: "COMPARTAMOS_VIGENTE" },
    { idcartera: 128, label: "Compartamos Vigente CCM", formato: "COMPARTAMOS_VIGENTE" },
    { idcartera: 133, label: "Compartamos Vigente GRU/CSM", formato: "COMPARTAMOS_VIGENTE" },
    { idcartera: 124, label: "Compartamos Castigo IND", formato: "COMPARTAMOS_CASTIGO" },
    { idcartera: 144, label: "Compartamos Castigo GRU/CCM", formato: "COMPARTAMOS_CASTIGO" }
];

document.addEventListener("DOMContentLoaded", () => {
    if (!exigirSesion()) return;

    if (localStorage.getItem("sidebarPagosColapsado") === "1") {
        document.body.classList.add("sidebar-collapsed");
    }

    document.getElementById("formPagos").addEventListener("submit", validarArchivo);
    document.getElementById("archivoPago").addEventListener("change", actualizarNombreArchivo);
    cargarHistorial();
});

async function validarArchivo(event) {
    event.preventDefault();

    const form = document.getElementById("formPagos");
    const btn = document.getElementById("btnValidar");
    const data = new FormData(form);
    data.set("usuario_carga", localStorage.getItem("dni") || "");

    if (!data.get("formato") || !data.get("archivo")?.name) {
        mostrarToast("Selecciona formato y archivo.", "error");
        return;
    }

    try {
        btn.disabled = true;
        btn.innerText = "Validando...";

        const response = await fetch(`${BASE_URL}/pagos/validar`, {
            method: "POST",
            body: data
        });

        const result = await response.json();

        if (!response.ok) {
            throw new Error(result.detail || "No se pudo validar el archivo.");
        }

        idImportacionActual = result.id_importacion;
        pintarResumen(result);
        await cargarHistorial(false);
        mostrarToast("Archivo validado correctamente.", "success");

    } catch (error) {
        console.error("ERROR VALIDANDO PAGOS:", error);
        mostrarToast(error.message || "Error de validación.", "error");
    } finally {
        btn.disabled = false;
        btn.innerText = "Validar archivo";
    }
}

function pintarResumen(data) {
    document.getElementById("resumenPanel").classList.remove("oculto");
    document.querySelector(".pagos-main-grid")?.classList.add("with-preview");
    document.getElementById("rFormato").innerText = texto(data.formato);
    document.getElementById("rArchivo").innerText = texto(data.archivo);
    document.getElementById("rCodmes").innerText = texto(data.codmes || (data.codmeses || []).join(", "));
    document.getElementById("rFechaCorte").innerText = formatearFecha(data.fecha_corte);
    document.getElementById("rFilas").innerText = numero(data.filas_totales);
    document.getElementById("rValidas").innerText = numero(data.filas_validas);
    document.getElementById("rErrores").innerText = numero(data.filas_error);
    document.getElementById("rMonto").innerText = soles(data.total_monto_pago);
    document.getElementById("rCapital").innerText = soles(data.total_capital_contenido);

    const tbody = document.getElementById("tablaResumenCartera");
    const resumen = data.resumen_por_cartera || [];

    tbody.innerHTML = resumen.length
        ? resumen.map(item => `
            <tr>
                <td class="text-left"><b>${texto(item.cartera || "Sin cartera")}</b></td>
                <td class="text-center"><span class="id-cartera">${texto(item.idcartera)}</span></td>
                <td class="text-center">${numero(item.filas)}</td>
                <td class="text-center">${numero(item.validas)}</td>
                <td class="text-center">${numero(item.errores)}</td>
                <td class="text-right">${soles(item.monto_pago)}</td>
                <td class="text-right">${soles(item.capital_contenido)}</td>
            </tr>
        `).join("")
        : `<tr><td colspan="7" class="sin-data">Sin resumen por cartera.</td></tr>`;
}

async function confirmarImportacion() {
    if (!idImportacionActual) {
        mostrarToast("Primero valida un archivo.", "error");
        return;
    }

    if (window.crmConfirm) {
        const confirmado = await crmConfirm({
            title: "Publicar importacion validada",
            message: "Se publicaran los pagos validados para BI y quedaran como corte activo del negocio. Deseas continuar?",
            acceptText: "Publicar",
            cancelText: "Cancelar",
            tone: "primary"
        });
        if (!confirmado) {
            return;
        }
    } else if (!confirm("Confirmar publicación de la importación validada?")) {
        return;
    }

    const btn = document.getElementById("btnConfirmar");

    try {
        btn.disabled = true;
        btn.innerText = "Publicando...";

        const response = await fetch(`${BASE_URL}/pagos/confirmar/${idImportacionActual}`, {
            method: "POST"
        });
        const result = await response.json();

        if (!response.ok) {
            throw new Error(result.detail || "No se pudo publicar la importación.");
        }

        mostrarToast(`Importación publicada correctamente: ${numero(result.filas_publicadas)} filas.`, "success");
        limpiarResumen();
        document.getElementById("formPagos").reset();
        actualizarNombreArchivo();
        await cargarHistorial(false);

    } catch (error) {
        console.error("ERROR CONFIRMANDO PAGOS:", error);
        mostrarToast(error.message || "Error publicando importación.", "error");
    } finally {
        btn.disabled = false;
        btn.innerText = "Confirmar importación";
    }
}

function cancelarResumen() {
    limpiarResumen();
    mostrarToast("Resumen previo cancelado.", "info");
}

function limpiarResumen() {
    idImportacionActual = null;
    document.getElementById("resumenPanel").classList.add("oculto");
    document.querySelector(".pagos-main-grid")?.classList.remove("with-preview");
    document.getElementById("tablaResumenCartera").innerHTML = "";
}

async function actualizarHistorial() {
    await cargarHistorial(false);
    mostrarToast("Historial actualizado.", "info");
}

async function cargarHistorial(mostrarError = true) {
    try {
        const params = new URLSearchParams({ limit: historialModo === "activos" ? "200" : "100" });
        if (historialModo === "activos") {
            params.set("activos", "true");
            params.set("codmes", codmesActual());
        }

        const response = await fetch(`${BASE_URL}/pagos/importaciones?${params.toString()}`);
        const result = await response.json();

        if (!response.ok) {
            throw new Error(result.detail || "No se pudo cargar historial.");
        }

        historialData = result.data || [];
        cortesActivosData = await cargarCortesActivos();
        historialPaginaActual = 1;
        pintarHistorial();
        actualizarFechaVista(historialData);
        actualizarEstadoFormatos(cortesActivosData);
        pintarResumenBI(cortesActivosData);
    } catch (error) {
        console.error("ERROR HISTORIAL PAGOS:", error);
        if (mostrarError) {
            mostrarToast("No se pudo cargar el historial.", "error");
        }
    }
}

async function cargarCortesActivos() {
    const response = await fetch(`${BASE_URL}/pagos/cortes-activos?codmes=${codmesActual()}`);
    const result = await response.json();
    if (!response.ok) {
        throw new Error(result.detail || "No se pudo cargar cortes activos.");
    }
    return result.data || [];
}

function pintarHistorial() {
    const tbody = document.getElementById("tablaHistorial");
    const inicio = (historialPaginaActual - 1) * HISTORIAL_PAGE_SIZE;
    const pagina = historialData.slice(inicio, inicio + HISTORIAL_PAGE_SIZE);

    tbody.innerHTML = pagina.length
        ? pagina.map(item => `
            <tr>
                <td class="text-center">${texto(item.id_importacion)}</td>
                <td>${formatearFechaHora(item.fecha_carga || item.fecha_importacion || item.fecha_registro)}</td>
                <td>${texto(item.formato)}</td>
                <td class="archivo-cell">${texto(item.archivo_nombre || item.archivo)}</td>
                <td class="text-center">${texto(item.codmes)}</td>
                <td>${formatearFecha(item.fecha_corte)}</td>
                <td>${texto(item.usuario_carga)}</td>
                <td class="text-center">${numero(item.total_filas_archivo ?? item.filas_totales)}</td>
                <td class="text-center cell-validas">${numero(item.total_filas_validas ?? item.filas_validas)}</td>
                <td class="text-center cell-errores">${numero(item.total_filas_error ?? item.filas_error)}</td>
                <td class="text-right">${soles(item.total_monto_pago ?? item.monto_pago)}</td>
                <td class="text-right">${soles(item.total_capital_contenido)}</td>
                <td>${badgeActivo(item.activo)}</td>
            </tr>
        `).join("")
        : `<tr><td colspan="13" class="sin-data">No hay importaciones registradas.</td></tr>`;

    actualizarPaginacionHistorial();
}

function cambiarModoHistorial(modo) {
    historialModo = modo;
    document.getElementById("btnHistorialActivos").classList.toggle("activo", modo === "activos");
    document.getElementById("btnHistorialTodos").classList.toggle("activo", modo === "todos");
    document.getElementById("historialSubtitulo").innerText = modo === "activos"
        ? `Importaciones publicadas vigentes para ${codmesActual()}.`
        : "Auditoría de últimas importaciones registradas.";
    cargarHistorial(false);
}

function cambiarPaginaHistorial(delta) {
    const totalPaginas = Math.max(1, Math.ceil(historialData.length / HISTORIAL_PAGE_SIZE));
    historialPaginaActual = Math.min(totalPaginas, Math.max(1, historialPaginaActual + delta));
    pintarHistorial();
}

function actualizarPaginacionHistorial() {
    const total = historialData.length;
    const totalPaginas = Math.max(1, Math.ceil(total / HISTORIAL_PAGE_SIZE));
    const inicio = total ? ((historialPaginaActual - 1) * HISTORIAL_PAGE_SIZE) + 1 : 0;
    const fin = Math.min(historialPaginaActual * HISTORIAL_PAGE_SIZE, total);

    document.getElementById("historialConteo").innerText = total
        ? `Mostrando ${numero(inicio)}-${numero(fin)} de ${numero(total)} registros`
        : "Mostrando 0 registros";
    document.getElementById("historialPagina").innerText = `${historialPaginaActual} / ${totalPaginas}`;
    document.getElementById("btnPaginaAnterior").disabled = historialPaginaActual <= 1;
    document.getElementById("btnPaginaSiguiente").disabled = historialPaginaActual >= totalPaginas;
}

function actualizarEstadoFormatos(data) {
    const contenedor = document.getElementById("estadoFormatos");
    if (!contenedor) return;

    if (historialModo !== "activos") {
        contenedor.classList.add("oculto");
        contenedor.innerHTML = "";
        return;
    }

    const cargados = new Set(data.map(item => Number(item.idcartera)));
    contenedor.classList.remove("oculto");
    contenedor.innerHTML = CORTES_ESPERADOS.map(corte => {
        const cargado = cargados.has(corte.idcartera);
        return `<span class="format-chip ${cargado ? "cargado" : "pendiente"}">${corte.label}: ${cargado ? "Cargado" : "Pendiente"}</span>`;
    }).join("");
}

function pintarResumenBI(data) {
    const tbody = document.getElementById("tablaBIActivo");
    if (!tbody) return;

    const totalPago = data.reduce((sum, item) => sum + Number(item.total_pago || 0), 0);
    const totalCapital = data.reduce((sum, item) => sum + Number(item.total_capital_contenido || 0), 0);
    const ultimo = data
        .filter(item => item.fecha_corte)
        .sort((a, b) => new Date(b.fecha_corte) - new Date(a.fecha_corte))[0];

    document.getElementById("biTotalPago").innerText = soles(totalPago);
    document.getElementById("biTotalCapital").innerText = soles(totalCapital);
    document.getElementById("biFormatosActivos").innerText = numero(new Set(data.map(item => item.idcartera)).size);
    document.getElementById("biUltimoCorte").innerText = ultimo
        ? `${texto(ultimo.cartera)} - ${formatearFecha(ultimo.fecha_corte)}`
        : "-";

    tbody.innerHTML = data.length
        ? data.map(item => `
            <tr>
                <td>${texto(item.cartera)}</td>
                <td class="text-center">${texto(item.tipo_medicion)}</td>
                <td class="text-center">${texto(item.codmes)}</td>
                <td class="text-center">${numero(item.registros)}</td>
                <td class="text-right">${soles(item.total_pago)}</td>
                <td class="text-right">${soles(item.total_capital_contenido)}</td>
                <td class="text-center">${formatearFecha(item.fecha_corte)}</td>
            </tr>
        `).join("")
        : `<tr><td colspan="7" class="sin-data">No hay cortes activos para ${codmesActual()}.</td></tr>`;
}

function badgeEstado(estado) {
    const valor = String(estado || "-").toUpperCase();
    const clase = valor.replace(/_/g, "-").toLowerCase();
    return `<span class="badge estado-${clase}">${valor}</span>`;
}

function badgeActivo(activo) {
    const esActivo = activo === true || activo === 1 || activo === "1";
    return `<span class="badge ${esActivo ? "badge-activo" : "badge-reemplazado"}">${esActivo ? "Activo" : "Reemplazado"}</span>`;
}

function actualizarNombreArchivo() {
    const input = document.getElementById("archivoPago");
    const nombre = input.files?.[0]?.name || "Ningún archivo seleccionado";
    document.getElementById("nombreArchivoPago").innerText = nombre;
}

function actualizarFechaVista(data) {
    const fecha = data.find(item => item.fecha_carga || item.fecha_importacion || item.fecha_registro);
    const valor = fecha
        ? formatearFechaHora(fecha.fecha_carga || fecha.fecha_importacion || fecha.fecha_registro)
        : formatearFechaHora(new Date().toISOString());
    document.getElementById("ultimaActualizacion").innerText = valor;
}

function codmesActual() {
    const hoy = new Date();
    return `${hoy.getFullYear()}${String(hoy.getMonth() + 1).padStart(2, "0")}`;
}

function mostrarToast(mensaje, tipo = "info") {
    const toast = document.getElementById("toastPagos");
    toast.className = `toast toast-${tipo}`;
    toast.innerText = mensaje;

    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => {
        toast.classList.add("oculto");
    }, 3600);
}

function irInicio() {
    window.location.href = "home.html";
}

function toggleSidebar() {
    document.body.classList.toggle("sidebar-collapsed");
    localStorage.setItem(
        "sidebarPagosColapsado",
        document.body.classList.contains("sidebar-collapsed") ? "1" : "0"
    );
}

function texto(valor) {
    if (valor === null || valor === undefined || valor === "") return "-";
    return String(valor);
}

function numero(valor) {
    return Number(valor || 0).toLocaleString("es-PE");
}

function soles(valor) {
    return Number(valor || 0).toLocaleString("es-PE", {
        style: "currency",
        currency: "PEN",
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    });
}

function formatearFecha(valor) {
    if (!valor) return "-";
    if (/^\d{4}-\d{2}-\d{2}$/.test(String(valor))) {
        const [year, month, day] = String(valor).split("-");
        return `${day}/${month}/${year}`;
    }
    const fecha = new Date(valor);
    if (Number.isNaN(fecha.getTime())) return "-";
    return fecha.toLocaleDateString("es-PE");
}

function formatearFechaHora(valor) {
    if (!valor) return "-";
    const fecha = new Date(valor);
    if (Number.isNaN(fecha.getTime())) return "-";
    return fecha.toLocaleString("es-PE", {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit"
    });
}
