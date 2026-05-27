async function buscar() {
    const valorInput = document.getElementById("valor");
    const loader = document.getElementById("loader");
    const resultado = document.getElementById("resultado");
    const valor = valorInput ? valorInput.value.trim() : "";

    if (!valor) {
        mostrarMensajeCliente("Ingresa un DNI, codigo de cliente, operacion o grupo para buscar.", "warning");
        valorInput?.focus();
        return;
    }

    if (loader) loader.style.display = "block";
    if (resultado) resultado.innerHTML = "";

    try {
        const BASE_URL = `${window.location.protocol}//${window.location.hostname}:8000`;
        const res = await fetch(`${BASE_URL}/cliente/buscar?valor=${encodeURIComponent(valor)}`);

        if (!res.ok) {
            throw new Error(`Error HTTP ${res.status}`);
        }

        const data = await res.json();

        if (loader) loader.style.display = "none";

        if (!data.encontrado) {
            mostrarMensajeCliente("No se encontraron clientes u operaciones con ese dato.", "empty");
            return;
        }

        renderCliente(data.data);
    } catch (e) {
        console.error("Error consultando cliente:", e);
        if (loader) loader.style.display = "none";
        mostrarMensajeCliente(`No se pudo completar la consulta. ${e.message || ""}`, "error");
    }
}

function mostrarMensajeCliente(mensaje, tipo = "empty") {
    const resultado = document.getElementById("resultado");
    if (!resultado) return;

    resultado.innerHTML = `
        <div class="clientes-empty clientes-empty-${tipo}">
            <strong>${escapeClienteHtml(mensaje)}</strong>
            <span>Verifica el dato ingresado o intenta nuevamente.</span>
        </div>
    `;
}

function verDetalle(index) {
    const c = window._clientes?.[index];
    const detalle = document.getElementById("detalle");
    if (!c || !detalle) return;

    detalle.innerHTML = `
        <div class="card">
            <h3>${escapeClienteHtml(c.NomCliente)}</h3>
            <p><b>DNI:</b> ${escapeClienteHtml(c.DNI)}</p>
            <p><b>CodCliente:</b> ${escapeClienteHtml(c.codcliente)}</p>
            <p><b>Operacion:</b> ${escapeClienteHtml(c["Cod Operacion"] || c.CodOperacion)}</p>
        </div>
    `;
}

function formatearNumero(valor) {
    if (!valor) return "0";
    return new Intl.NumberFormat("es-PE").format(valor);
}

function copiarTexto(texto) {
    if (!texto) {
        mostrarMensajeCliente("No hay numero para copiar.", "warning");
        return;
    }

    navigator.clipboard.writeText(texto);
    mostrarMensajeCliente("Numero copiado al portapapeles.", "empty");
}

function escapeClienteHtml(value) {
    return String(value ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

window.addEventListener("DOMContentLoaded", () => {
    const params = new URLSearchParams(window.location.search);
    const dni = params.get("dni");
    const codcliente = params.get("codcliente");
    const operacion = params.get("operacion");
    const grupo = params.get("grupo");
    const valor = dni || codcliente || operacion || grupo;

    if (valor) {
        const valorInput = document.getElementById("valor");
        if (valorInput) valorInput.value = valor;
        buscar();
    }
});
