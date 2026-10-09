async function buscar() {
    const valorInput = document.getElementById("valor");
    const loader = document.getElementById("loader");
    const resultado = document.getElementById("resultado");
    const valor = valorInput ? valorInput.value.trim() : "";
    const submit = valorInput?.closest("form")?.querySelector("button[type='submit']");

    if (!valor) {
        mostrarMensajeCliente("Ingresa un DNI, codigo de cliente, operacion o grupo para buscar.", "warning");
        valorInput?.focus();
        return;
    }

    window._clientes = [];
    window._indiceOperacionSeleccionada = null;
    if (loader) loader.style.display = "block";
    if (resultado) {
        resultado.innerHTML = "";
        resultado.setAttribute("aria-busy", "true");
    }
    if (submit) {
        submit.disabled = true;
        submit.setAttribute("aria-disabled", "true");
    }

    try {
        // Seguridad: ninguna consulta sale antes de validar la sesion con el backend.
        if (!(await asegurarSesionBackend())) return;

        const BASE_URL = `${window.location.protocol}//${window.location.hostname}:8000`;
        const res = await fetchConSesion(`${BASE_URL}/cliente/buscar?valor=${encodeURIComponent(valor)}`);

        if (res.status === 403) {
            mostrarMensajeCliente(await mensajeErrorRespuesta(res, "No tienes acceso a este cliente."), "warning");
            return;
        }
        if (!res.ok) {
            throw new Error(`Error HTTP ${res.status}`);
        }

        const data = await res.json();

        if (!data.encontrado) {
            mostrarMensajeCliente("No se encontraron clientes u operaciones con ese dato.", "empty");
            return;
        }

        renderCliente(data);
    } catch (e) {
        if (e instanceof SesionInvalidaError) return;
        console.error("Error consultando cliente:", e);
        mostrarMensajeCliente(`No se pudo completar la consulta. ${e.message || ""}`, "error");
    } finally {
        if (loader) loader.style.display = "none";
        if (resultado) resultado.setAttribute("aria-busy", "false");
        if (submit) {
            submit.disabled = false;
            submit.removeAttribute("aria-disabled");
        }
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

function escapeClienteHtml(value) {
    return String(value ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

window.addEventListener("DOMContentLoaded", async () => {
    // La pagina no consulta nada hasta que /auth/me confirme la sesion.
    if (!(await asegurarSesionBackend())) return;

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
