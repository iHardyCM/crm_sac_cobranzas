const BASE_URL = `${window.location.protocol}//${window.location.hostname}:8000`;

let dataPdpHoy = [];
let dataPdpHoyFiltrada = [];
let ordenPdpHoy = {
    campo: "monto_pdp",
    direccion: "desc"
};

document.addEventListener("DOMContentLoaded", () => {
    if (!exigirAccesoPdpHoy()) return;

    cargarPdpHoy();
    configurarCierreModal();
});

async function cargarPdpHoy() {
    const params = new URLSearchParams(window.location.search);
    let idcartera = params.get("idcartera");
    let idcarteras = params.get("idcarteras");

    if (esSupervisor()) {
        const carterasSupervisor = obtenerCarterasSupervisor();

        if (!carterasSupervisor.length) {
            alert("No se encontraron carteras asignadas para el supervisor.");
            irInicio();
            return;
        }

        const idsUrl = obtenerCarterasUrl(idcartera, idcarteras);
        const idsPermitidos = idsUrl.filter(id => carterasSupervisor.includes(id));

        if (!idsPermitidos.length || idsPermitidos.length !== idsUrl.length) {
            const querySupervisor = construirQueryCarteras(carterasSupervisor);
            window.location.href = `corporativo_pdp_hoy.html?${querySupervisor}`;
            return;
        }

        idcartera = idsPermitidos.length === 1 ? idsPermitidos[0] : null;
        idcarteras = idsPermitidos.length > 1 ? idsPermitidos.join(",") : null;
    }

    const query = idcarteras
        ? `?idcarteras=${encodeURIComponent(idcarteras)}`
        : (idcartera ? `?idcartera=${encodeURIComponent(idcartera)}` : "");

    try {
        const response = await fetch(`${BASE_URL}/corporativo/pdp-hoy${query}`);

        if (!response.ok) {
            throw new Error("Error al consultar PDP hoy");
        }

        const result = await response.json();
        dataPdpHoy = (result.data || []).map(normalizarFila);
        dataPdpHoyFiltrada = [...dataPdpHoy];

        pintarFiltroCartera(dataPdpHoy);
        pintarCabecera(dataPdpHoy, idcartera, idcarteras);
        aplicarFiltrosIniciales();
        renderTablaPdpHoy();

    } catch (error) {
        console.error("ERROR PDP HOY:", error);
        alert("No se pudo cargar el detalle de PDP hoy.");
    }
}

function obtenerCarterasSupervisor() {
    if (typeof obtenerIdCarterasSesion === "function") {
        return obtenerIdCarterasSesion();
    }

    return [
        ...(localStorage.getItem("idcarteras") || "").split(","),
        localStorage.getItem("idcartera")
    ]
        .map(x => String(x || "").trim())
        .filter(Boolean)
        .filter((x, index, arr) => arr.indexOf(x) === index);
}

function obtenerCarterasUrl(idcartera, idcarteras) {
    const ids = [
        idcartera,
        ...(idcarteras || "").split(",")
    ]
        .map(x => String(x || "").trim())
        .filter(Boolean);

    return [...new Set(ids)];
}

function construirQueryCarteras(ids) {
    if (ids.length > 1) return `idcarteras=${encodeURIComponent(ids.join(","))}`;
    return `idcartera=${encodeURIComponent(ids[0])}`;
}

function pintarFiltroCartera(data) {
    const select = document.getElementById("filtroCarteraPdp");
    const carteras = [...new Map(data.map(x => [
        String(x.idcartera),
        { idcartera: x.idcartera, cartera: x.cartera }
    ])).values()].sort((a, b) => String(a.cartera).localeCompare(String(b.cartera), "es"));

    select.innerHTML = `<option value="">Todas las carteras</option>`;

    carteras.forEach(x => {
        const option = document.createElement("option");
        option.value = x.idcartera;
        option.textContent = `${x.cartera} (${x.idcartera})`;
        select.appendChild(option);
    });

    const params = new URLSearchParams(window.location.search);
    const idcartera = params.get("idcartera");
    if (idcartera) {
        select.value = idcartera;
    }
}

function aplicarFiltrosIniciales() {
    const params = new URLSearchParams(window.location.search);
    const soloPendientes = params.get("solo_pendientes") === "1";
    const sinIntentos = params.get("sin_intentos") === "1";
    const buscar = params.get("buscar");

    if (soloPendientes) {
        document.getElementById("filtroEstadoPdp").value = "pendiente";
    }

    if (sinIntentos) {
        document.getElementById("filtroIntentosPdp").value = "0";
    }

    if (buscar) {
        document.getElementById("buscarPdpHoy").value = buscar;
    }

    if (soloPendientes || sinIntentos || buscar) {
        aplicarFiltrosPdpHoy();
    }
}

function normalizarFila(x) {
    const montoPdp = Number(x.monto_hoy || x.monto_pdp || 0);
    const montoPagado = Number(x.monto_pagado_hoy || x.monto_pagado || 0);
    const pendienteHoy = Math.max(montoPdp - montoPagado, 0);

    return {
        ...x,
        cartera: x.cartera || x.CARTERA || "-",
        monto_pdp: montoPdp,
        monto_pagado: montoPagado,
        pendiente_hoy: pendienteHoy,
        estado_calculado: pendienteHoy <= 0 ? "CUMPLIDA" : "PENDIENTE"
    };
}

function pintarCabecera(data, idcartera, idcarteras) {
    const cartera = idcartera
        ? (data[0]?.cartera || `ID Cartera: ${idcartera}`)
        : (idcarteras ? "Carteras asignadas" : "Todas las carteras");
    const total = data.length;

    document.getElementById("tituloPdpHoy").innerText =
        `PDP Hoy - ${cartera}`;

    document.getElementById("subtituloPdpHoy").innerText =
        `${total.toLocaleString("es-PE")} promesas con vencimiento hoy`;
}

function aplicarFiltrosPdpHoy() {
    const texto = document.getElementById("buscarPdpHoy").value.trim().toLowerCase();
    const idcartera = document.getElementById("filtroCarteraPdp").value;
    const estado = document.getElementById("filtroEstadoPdp").value;
    const intentos = document.getElementById("filtroIntentosPdp").value;

    dataPdpHoyFiltrada = dataPdpHoy.filter(x => {
        const contenido = [
            x.cliente,
            x.cartera,
            x.idcartera,
            x.dni,
            x.telefono,
            x.agente,
            x.num_operacion
        ].join(" ").toLowerCase();

        const okTexto = texto ? contenido.includes(texto) : true;
        const okCartera = idcartera ? String(x.idcartera) === idcartera : true;

        const okEstado =
            estado === "pendiente" ? x.pendiente_hoy > 0 :
            estado === "cumplida" ? x.pendiente_hoy <= 0 :
            true;

        const intentosHoy = Number(x.intentos_hoy || 0);
        const okIntentos =
            intentos === "0" ? intentosHoy === 0 :
            intentos === "1_2" ? intentosHoy >= 1 && intentosHoy <= 2 :
            intentos === "3_mas" ? intentosHoy >= 3 :
            true;

        return okCartera && okTexto && okEstado && okIntentos;
    });

    renderTablaPdpHoy();
}

function ordenarPdpHoy(campo) {
    if (ordenPdpHoy.campo === campo) {
        ordenPdpHoy.direccion = ordenPdpHoy.direccion === "asc" ? "desc" : "asc";
    } else {
        ordenPdpHoy.campo = campo;
        ordenPdpHoy.direccion = ["cliente", "cartera", "agente", "estado"].includes(campo) ? "asc" : "desc";
    }

    renderTablaPdpHoy();
}

function renderTablaPdpHoy() {
    const tbody = document.getElementById("tablaPdpHoy");
    const data = ordenarDataPdpHoy(dataPdpHoyFiltrada);
    pintarKpisPdpHoy(dataPdpHoyFiltrada);

    if (!data.length) {
        tbody.innerHTML = `
            <tr>
                <td colspan="11" class="sin-data">
                    No hay promesas que coincidan con los filtros.
                </td>
            </tr>
        `;
        actualizarIndicadoresOrden();
        return;
    }

    tbody.innerHTML = data.map((x, index) => `
        <tr>
            <td class="cartera">
                ${x.cliente || "-"}
                <small>Operacion: ${x.num_operacion || "-"}</small>
            </td>
            <td>
                <b>${x.cartera || "-"}</b>
                <small>ID: ${x.idcartera || "-"}</small>
            </td>
            <td>${x.dni || "-"}</td>
            <td>${x.telefono || "-"}</td>
            <td>${x.agente || "-"}</td>
            <td>${formatoSoles(x.monto_pdp)}</td>
            <td>${formatoSoles(x.monto_pagado)}</td>
            <td>
                <span class="estado-pdp ${x.pendiente_hoy <= 0 ? "estado-pagada" : "estado-pendiente"}">
                    ${x.pendiente_hoy <= 0 ? "Pagada" : "Pendiente"}
                </span>
            </td>
            <td>
                <span class="badge ${claseIntentos(x.intentos_hoy)}">
                    ${Number(x.intentos_hoy || 0).toLocaleString("es-PE")}
                </span>
            </td>
            <td>
                <div class="ultima-gestion-cell" title="${x.ult_indicador || "-"} ${formatearFechaHora(x.ult_fecha)}">
                    <span class="ultima-gestion-tipo">${x.ult_indicador || "Sin gestion"}</span>
                    <span class="ultima-gestion-fecha">${formatearFechaHora(x.ult_fecha)}</span>
                </div>
            </td>
            <td>
                <button class="btn-ver-detalle" onclick="abrirModalPdpHoy(${index})">
                    Ver
                </button>
            </td>
        </tr>
    `).join("");

    window._pdpHoyRenderizada = data;
    actualizarIndicadoresOrden();
}

function pintarKpisPdpHoy(data) {
    const pendiente = data.reduce((total, x) => total + Number(x.pendiente_hoy || 0), 0);
    const impagas = data.filter(x => Number(x.pendiente_hoy || 0) > 0).length;
    const sinIntentos = data.filter(x => Number(x.intentos_hoy || 0) === 0).length;
    const promedioIntentos = data.length
        ? data.reduce((total, x) => total + Number(x.intentos_hoy || 0), 0) / data.length
        : 0;

    document.getElementById("kpiPendienteHoy").innerText = formatoSoles(pendiente);
    document.getElementById("kpiImpagas").innerText = impagas.toLocaleString("es-PE");
    document.getElementById("kpiSinIntentos").innerText = sinIntentos.toLocaleString("es-PE");
    document.getElementById("kpiPromIntentos").innerText = promedioIntentos.toFixed(1);
}

function ordenarDataPdpHoy(data) {
    return [...data].sort((a, b) => {
        const campo = ordenPdpHoy.campo;
        const valorA = valorOrdenPdpHoy(a, campo);
        const valorB = valorOrdenPdpHoy(b, campo);

        if (typeof valorA === "string" || typeof valorB === "string") {
            return ordenPdpHoy.direccion === "asc"
                ? String(valorA).localeCompare(String(valorB), "es")
                : String(valorB).localeCompare(String(valorA), "es");
        }

        return ordenPdpHoy.direccion === "asc"
            ? Number(valorA || 0) - Number(valorB || 0)
            : Number(valorB || 0) - Number(valorA || 0);
    });
}

function valorOrdenPdpHoy(item, campo) {
    if (campo === "estado") return item.estado_calculado;
    if (campo === "ult_fecha") return item.ult_fecha ? new Date(item.ult_fecha).getTime() : 0;
    return item[campo] ?? "";
}

function actualizarIndicadoresOrden() {
    document.querySelectorAll("[data-sort]").forEach(button => {
        const activo = button.dataset.sort === ordenPdpHoy.campo;
        button.classList.toggle("activo", activo);

        const indicador = button.querySelector(".orden-icono");
        if (indicador) {
            indicador.innerText = activo
                ? (ordenPdpHoy.direccion === "asc" ? "↑" : "↓")
                : "↕";
        }
    });
}

function abrirModalPdpHoy(index) {
    const item = window._pdpHoyRenderizada[index];
    if (!item) return;

    document.getElementById("modalPdpId").innerText =
        `#PDP ${item.idcompromiso || "-"} | ${item.cartera}`;
    document.getElementById("modalPdpCliente").innerText =
        item.cliente || "-";

    document.getElementById("modalPdpContenido").innerHTML = `
        <section class="modal-grid">
            <div>
                <p>DNI</p>
                <b>${item.dni || "-"}</b>
            </div>
            <div>
                <p>Telefono</p>
                <b>${item.telefono || "-"}</b>
            </div>
            <div>
                <p>Agente</p>
                <b>${item.agente || "-"}</b>
            </div>
            <div>
                <p>Estado</p>
                <b>${item.estado_calculado}</b>
            </div>
            <div>
                <p>Monto PDP</p>
                <b>${formatoSoles(item.monto_pdp)}</b>
            </div>
            <div>
                <p>Monto pagado</p>
                <b>${formatoSoles(item.monto_pagado)}</b>
            </div>
            <div>
                <p>Pendiente hoy</p>
                <b>${formatoSoles(item.pendiente_hoy)}</b>
            </div>
            <div>
                <p>Intentos hoy</p>
                <b>${Number(item.intentos_hoy || 0)}</b>
            </div>
        </section>

        <section class="modal-bloque-pdp">
            <h3>Gestion del compromiso</h3>
            <p>${item.gestion_compromiso || "-"}</p>
        </section>

        <section class="modal-bloque-pdp">
            <h3>Ultima gestion</h3>
            <p><b>${item.ult_indicador || "-"}</b> | ${formatearFechaHora(item.ult_fecha)}</p>
            <p>${item.ult_gestion || "-"}</p>
            <small>${item.ult_agente || ""}</small>
        </section>
    `;

    document.getElementById("modalPdpHoy").classList.add("activo");
}

function cerrarModalPdpHoy() {
    document.getElementById("modalPdpHoy").classList.remove("activo");
}

function configurarCierreModal() {
    const modal = document.getElementById("modalPdpHoy");

    modal.addEventListener("click", event => {
        if (event.target === modal) {
            cerrarModalPdpHoy();
        }
    });
}

function claseIntentos(valor) {
    const n = Number(valor || 0);
    if (n === 0) return "rojo";
    if (n <= 2) return "amarillo";
    return "verde";
}

function formatoSoles(valor) {
    return Number(valor || 0).toLocaleString("es-PE", {
        style: "currency",
        currency: "PEN"
    });
}

function formatearFechaHora(valor) {
    if (!valor) return "-";
    return new Date(valor).toLocaleString("es-PE", {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit"
    });
}

function volverCorporativo() {
    window.location.href = "corporativo.html";
}
