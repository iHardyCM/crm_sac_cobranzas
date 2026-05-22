const BASE_URL = `${window.location.protocol}//${window.location.hostname}:8000`;
let detalleCorporativo = [];
let ordenTabla = {
    campo: "total_promesas",
    direccion: "desc"
};

document.addEventListener("DOMContentLoaded", () => {
    if (!exigirAccesoCorporativo()) return;

    const agente = localStorage.getItem("agente") || "Gerencia";
    document.getElementById("usuario").innerText = agente;

    pintarTituloMes();
    cargarFiltrosCorporativos();
    cargarResumenCorporativo();
});

function pintarTituloMes() {
    const fecha = new Date();

    const mes = fecha.toLocaleDateString("es-PE", {
        month: "long",
        year: "numeric"
    });

    document.getElementById("tituloMes").innerText =
        `Resumen rendimiento corporativo (${mes})`;
}

function pintarTituloFiltros() {
    const fechaDesde = document.getElementById("fechaDesde")?.value;
    const fechaHasta = document.getElementById("fechaHasta")?.value;

    if (!fechaDesde && !fechaHasta) {
        pintarTituloMes();
        return;
    }

    const desde = fechaDesde ? formatearFecha(fechaDesde) : "inicio";
    const hasta = fechaHasta ? formatearFecha(fechaHasta) : "hoy";

    document.getElementById("tituloMes").innerText =
        `Resumen rendimiento corporativo (${desde} - ${hasta})`;
}

async function cargarFiltrosCorporativos() {
    try {
        const response = await fetch(`${BASE_URL}/corporativo/filtros`);

        if (!response.ok) {
            throw new Error("Error al consultar filtros corporativos");
        }

        const result = await response.json();
        pintarOpcionesCartera(result.carteras || []);

    } catch (error) {
        console.error("ERROR CARGANDO FILTROS CORPORATIVOS:", error);
    }
}

function pintarOpcionesCartera(carteras) {
    const select = document.getElementById("filtroCartera");
    const valorActual = select.value;

    select.innerHTML = `<option value="">Todas las carteras</option>`;

    carteras.forEach(x => {
        const option = document.createElement("option");
        option.value = x.idcartera;
        option.textContent = `${x.cartera} (${x.idcartera})`;
        select.appendChild(option);
    });

    select.value = valorActual;
}

async function cargarResumenCorporativo() {
    try {
        const response = await fetch(`${BASE_URL}/corporativo/resumen${obtenerQueryFiltros()}`);

        if (!response.ok) {
            throw new Error("Error al consultar endpoint corporativo");
        }

        const result = await response.json();

        pintarCards(result.resumen || {});
        pintarAlertas(result.alertas || {});
        detalleCorporativo = result.detalle || [];
        pintarTabla();

    } catch (error) {
        console.error("ERROR CARGANDO CORPORATIVO:", error);
        alert("No se pudo cargar el panel corporativo.");
    }
}

function pintarCards(resumen) {
    document.getElementById("totalPromesas").innerText =
        Number(resumen.total_promesas || 0).toLocaleString("es-PE");

    document.getElementById("montoPDP").innerText =
        formatoSoles(resumen.monto_pdp || 0);

    document.getElementById("montoCaido").innerText =
        formatoSoles(resumen.monto_caido || resumen.monto_pendiente || 0);

    document.getElementById("eficacia").innerText =
        `${Number(resumen.eficacia || 0).toFixed(1)}%`;

    document.getElementById("tasaCaida").innerText =
        `${Number(resumen.tasa_caida || 0).toFixed(1)}%`;
}

function obtenerQueryFiltros() {
    const params = new URLSearchParams();
    const idcartera = document.getElementById("filtroCartera")?.value;
    const fechaDesde = document.getElementById("fechaDesde")?.value;
    const fechaHasta = document.getElementById("fechaHasta")?.value;

    if (idcartera) params.append("idcartera", idcartera);
    if (fechaDesde) params.append("fecha_desde", fechaDesde);
    if (fechaHasta) params.append("fecha_hasta", fechaHasta);

    const query = params.toString();
    return query ? `?${query}` : "";
}

function aplicarFiltros() {
    pintarTituloFiltros();
    cargarResumenCorporativo();
}

function limpiarFiltros() {
    document.getElementById("filtroCartera").value = "";
    document.getElementById("fechaDesde").value = "";
    document.getElementById("fechaHasta").value = "";
    pintarTituloMes();
    cargarResumenCorporativo();
}

function pintarAlertas(alertas) {
    const contenedor = document.getElementById("alertasCorporativas");

    const items = [
        {
            titulo: "Mayor caida",
            dato: alertas.mayor_caida,
            valor: item => `${Number(item.tasa_caida || 0).toFixed(1)}%`,
            clase: "alerta-roja"
        },
        {
            titulo: "Menor cumplimiento",
            dato: alertas.menor_cumplimiento,
            valor: item => `${Number(item.calidad || 0).toFixed(1)}%`,
            clase: "alerta-naranja"
        },
        {
            titulo: "Mayor monto caido",
            dato: alertas.mayor_caido || alertas.mayor_pendiente,
            valor: item => formatoSoles(item.monto_caido || item.monto_pendiente || 0),
            clase: "alerta-azul"
        },
        {
            titulo: "Mejor cartera",
            dato: alertas.mejor_cartera,
            valor: item => `${Number(item.calidad || 0).toFixed(1)}%`,
            clase: "alerta-verde"
        }
    ];

    contenedor.innerHTML = items.map(item => {
        const dato = item.dato || {};

        return `
            <article class="alerta ${item.clase}">
                <p>${item.titulo}</p>
                <h3>${dato.cartera || "-"}</h3>
                <small>ID Cartera: ${dato.idcartera || "-"}</small>
                <span>${item.valor(dato)}</span>
            </article>
        `;
    }).join("");
}

function pintarTabla() {
    const tbody = document.getElementById("tablaCorporativo");
    const data = obtenerDetalleOrdenado();

    tbody.innerHTML = "";

    if (!data.length) {
        tbody.innerHTML = `
            <tr>
                <td colspan="12" class="sin-data">
                    No hay compromisos generados para el mes actual.
                </td>
            </tr>
        `;
        return;
    }

    data.forEach(x => {
        const tr = document.createElement("tr");

        tr.innerHTML = `
            <td class="cartera">
                <div class="nombre-cartera">
                    <span class="punto"></span>
                    ${x.cartera || "-"}
                </div>
                <small>ID Cartera: ${x.idcartera || "-"}</small>
            </td>

            <td>
                <span class="badge neutro">
                    ${Number(x.total_promesas || 0).toLocaleString("es-PE")}
                </span>
            </td>

            <td>${formatoSoles(x.monto_pdp)}</td>
            <td>${formatoSoles(x.monto_proyectado)}</td>
            <td>${formatoSoles(x.monto_pagado)}</td>
            <td>${formatoSoles(x.monto_caido || x.monto_pendiente)}</td>

            <td>
                <div class="eficacia-box">
                    <div class="barra">
                        <div style="width:${limitarPorcentaje(x.eficacia)}%"></div>
                    </div>
                    <span>${Number(x.eficacia || 0).toFixed(1)}%</span>
                </div>
            </td>

            <td>
                <span class="semaforo ${claseSemaforo(x.estado_semaforo)}">
                    ${textoSemaforo(x.estado_semaforo)}
                </span>
            </td>

            <td>
                <button class="badge rojo badge-link"
                    onclick="verPdpHoy(${Number(x.idcartera || 0)})"
                    title="Ver promesas que vencen hoy">
                    ${Number(x.pdp_hoy || 0).toLocaleString("es-PE")}
                </button>
            </td>

            <td>
                <span class="badge naranja">
                    ${Number(x.pdp_caida || 0).toLocaleString("es-PE")}
                </span>
            </td>

            <td>
                <span class="badge amarillo">
                    ${Number(x.pdp_vigente || 0).toLocaleString("es-PE")}
                </span>
            </td>

            <td>
                <span class="badge verde">
                    ${Number(x.pdp_cumplida || 0).toLocaleString("es-PE")}
                </span>
            </td>
        `;

        tbody.appendChild(tr);
    });

    actualizarIndicadoresOrden();
}

function obtenerDetalleOrdenado() {
    return [...detalleCorporativo].sort((a, b) => {
        const campo = ordenTabla.campo;
        const valorA = obtenerValorOrden(a, campo);
        const valorB = obtenerValorOrden(b, campo);

        if (typeof valorA === "string" || typeof valorB === "string") {
            return ordenTabla.direccion === "asc"
                ? String(valorA).localeCompare(String(valorB), "es")
                : String(valorB).localeCompare(String(valorA), "es");
        }

        return ordenTabla.direccion === "asc"
            ? Number(valorA || 0) - Number(valorB || 0)
            : Number(valorB || 0) - Number(valorA || 0);
    });
}

function obtenerValorOrden(item, campo) {
    if (campo === "monto_caido") {
        return item.monto_caido || item.monto_pendiente || 0;
    }

    return item[campo] ?? "";
}

function ordenarTabla(campo) {
    if (ordenTabla.campo === campo) {
        ordenTabla.direccion = ordenTabla.direccion === "asc" ? "desc" : "asc";
    } else {
        ordenTabla.campo = campo;
        ordenTabla.direccion = campo === "cartera" ? "asc" : "desc";
    }

    pintarTabla();
}

function actualizarIndicadoresOrden() {
    document.querySelectorAll("[data-sort]").forEach(button => {
        const activo = button.dataset.sort === ordenTabla.campo;
        button.classList.toggle("activo", activo);
        button.setAttribute("aria-sort", activo ? ordenTabla.direccion : "none");

        const indicador = button.querySelector(".orden-icono");
        if (indicador) {
            indicador.innerText = activo
                ? (ordenTabla.direccion === "asc" ? "↑" : "↓")
                : "↕";
        }
    });
}

function formatoSoles(valor) {
    return Number(valor || 0).toLocaleString("es-PE", {
        style: "currency",
        currency: "PEN"
    });
}

function limitarPorcentaje(valor) {
    const n = Number(valor || 0);

    if (n < 0) return 0;
    if (n > 100) return 100;

    return n;
}

function formatearFecha(valor) {
    const [year, month, day] = valor.split("-");
    return `${day}/${month}/${year}`;
}

function claseSemaforo(estado) {
    const valor = String(estado || "").toUpperCase();

    if (valor === "SALUDABLE") return "semaforo-verde";
    if (valor === "SEGUIMIENTO") return "semaforo-amarillo";

    return "semaforo-rojo";
}

function textoSemaforo(estado) {
    const valor = String(estado || "").toUpperCase();

    if (valor === "SALUDABLE") return "Saludable";
    if (valor === "SEGUIMIENTO") return "Seguimiento";

    return "Critico";
}

function verPdpHoy(idcartera) {
    if (!idcartera) return;
    window.location.href = `corporativo_pdp_hoy.html?idcartera=${encodeURIComponent(idcartera)}`;
}

function verPdpHoyGeneral() {
    window.location.href = "corporativo_pdp_hoy.html";
}

function descargarReporte() {
    window.open(`${BASE_URL}/corporativo/exportar${obtenerQueryFiltros()}`, "_blank");
}
