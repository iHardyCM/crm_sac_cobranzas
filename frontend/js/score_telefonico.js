const BASE_URL_SCORE = `${window.location.protocol}//${window.location.hostname}:8000`;

let scorePage = 1;
let scorePageSize = 25;
let scoreTotal = 0;
let scoreTotalPages = 1;
let scoreOrderBy = "SCORE_FINAL";
let scoreOrderDir = "DESC";
let scoreLoading = false;
let scoreSearchTimeout = null;
let scoreCatalogos = {};
let scoreSegmentActivo = "cliente";
let scoreFiltrosSeleccionados = {};
let scoreResumenRequestId = 0;

const SCORE_SEGMENTS = [
    { key: "cliente", label: "Cliente", title: "1. Cliente" },
    { key: "gestion", label: "Gestion", title: "2. Gestion Cliente" },
    { key: "telefono", label: "Telefono", title: "3. Telefono" }
];

const FILTROS_SCORE_CONFIG = [
    { key: "condicion", catalogo: "condiciones", label: "Condicion", seccion: "cliente" },
    { key: "nuevo", catalogo: "nuevos", label: "Nuevo", seccion: "cliente" },
    { key: "rango_mora", catalogo: "rangos_mora", label: "Rango maduracion / mora", seccion: "cliente" },
    { key: "prioridad_banco", catalogo: "prioridades_banco", label: "Prioridad", seccion: "cliente" },
    { key: "rango_capital", catalogo: "rangos_capital", label: "Rango capital", seccion: "cliente" },
    { key: "empresas_reportantes", catalogo: "empresas_reportantes", label: "Empresas reportantes", seccion: "cliente" },
    { key: "cuentas", catalogo: "cuentas", label: "Cuentas", seccion: "cliente" },
    { key: "anio_cd_historico", catalogo: "anios_cd_historico", label: "Anio CD historico [Ult periodo de contacto]", seccion: "cliente" },
    { key: "cluster_ml", catalogo: "clusters_ml", label: "Cluster ML", seccion: "cliente" },
    { key: "flag_top", catalogo: "flags_top", label: "Flag top", seccion: "cliente" },
    { key: "rango_campanas", catalogo: "rangos_campanas", label: "Rango de campanas", seccion: "cliente" },
    { key: "caseros", catalogo: "caseros", label: "Caseros", seccion: "cliente" },
    { key: "mg_contacto_cliente", catalogo: "mg_contacto_cliente", label: "MG contacto cliente", seccion: "gestion" },
    { key: "mg_indicador_cliente", catalogo: "mg_indicador_cliente", label: "MG indicador cliente", seccion: "gestion" },
    { key: "ug_contacto_cliente", catalogo: "ug_contacto_cliente", label: "UG contacto cliente", seccion: "gestion" },
    { key: "ug_indicador_cliente", catalogo: "ug_indicador_cliente", label: "UG indicador cliente", seccion: "gestion" },
    { key: "estado_pdp", catalogo: "estados_pdp", label: "Estado PDP", seccion: "gestion" },
    { key: "origen", catalogo: "origenes", label: "Origen", seccion: "telefono" },
    { key: "tipo_base", catalogo: "tipos_base", label: "Tipo base", seccion: "telefono" },
    { key: "prioridad_fono", catalogo: "prioridades_fono", label: "Prioridad fono", seccion: "telefono" },
    { key: "tipo_fono", catalogo: "tipos_fono", label: "Tipo fono", seccion: "telefono" },
    { key: "orden", catalogo: "ordenes", label: "Orden", seccion: "telefono" },
    { key: "osiptel", catalogo: "osiptel", label: "OSIPTEL", seccion: "telefono" },
    { key: "whatsapp", catalogo: "whatsapp", label: "WhatsApp", seccion: "telefono" },
    { key: "timbrado", catalogo: "timbrados", label: "Timbrado", seccion: "telefono" },
    { key: "intentos_equivocados", catalogo: "intentos_equivocados", label: "Intentos equivocados", seccion: "telefono" },
    { key: "apagados_ivr", catalogo: "apagados_ivr", label: "Apagado IVR", seccion: "telefono" },
    { key: "fallados_ivr", catalogo: "fallados_ivr", label: "Fallados IVR", seccion: "telefono" },
    { key: "zona", catalogo: "zonas", label: "Zona", seccion: "telefono" },
    { key: "marca_operativa", catalogo: "marcas_operativas", label: "Marca operativa", seccion: "telefono" }
];
document.addEventListener("DOMContentLoaded", () => {
    if (typeof exigirSesion === "function" && !exigirSesion()) return;
    if (typeof puedeVerCorporativo === "function" && !puedeVerCorporativo(localStorage.getItem("tipo"))) {
        sessionStorage.setItem("homeMensaje", "Score Telefonico esta reservado para usuarios de gestion gerencial.");
        window.location.href = "home.html";
        return;
    }

    document.addEventListener("click", event => {
        document.querySelectorAll(".dropdown-filter.open").forEach(filter => {
            if (!filter.contains(event.target)) {
                filter.classList.remove("open");
            }
        });
    });

    wireVisualActions();
    iniciarScoreTelefonico();
});

async function iniciarScoreTelefonico() {
    await cargarContextoScore();

    const idcartera = obtenerIdCarteraScore();
    await cargarCatalogosScore(idcartera);

    await cargarUltimaActualizacionScore();

    await Promise.all([
        cargarResumenScore(),
        cargarResultadosScore()
    ]);
}

function obtenerIdCarteraScore() {
    return document.getElementById("filtroCarteraScore")?.value || "";
}

async function cargarContextoScore() {
    const usuario = localStorage.getItem("dni") || localStorage.getItem("agente") || "";
    const perfil = localStorage.getItem("tipoUsuario") || localStorage.getItem("perfil") || "";

    const params = new URLSearchParams();

    if (usuario) params.set("usuario", usuario);
    if (perfil) params.set("perfil", perfil);

    try {
        const response = await fetch(`${BASE_URL_SCORE}/score-telefonico/contexto?${params.toString()}`, {
            cache: "no-store"
        });

        if (!response.ok) throw new Error(`HTTP ${response.status}`);

        const data = await response.json();

        poblarCarterasScore(data.carteras_permitidas || [], data.cartera_default);
    } catch (error) {
        console.error("Error contexto score:", error);

        poblarCarterasScore([
            { idcartera: 112, nombre: "MIBANCO - EQUIPO 1 - MORA 25+" },
            { idcartera: 143, nombre: "MIBANCO - EQUIPO 2 - MORA 0-24" },
            { idcartera: 135, nombre: "MIBANCO VIGENTE" },
            { idcartera: 117, nombre: "INTERBANK" },
            { idcartera: 132, nombre: "FINANCIERA OH" },
            { idcartera: 148, nombre: "FINANCIERA OH PROPIA" }
        ], 112);

        showToast("Contexto no disponible. Se usó cartera base.");
    }
}

function poblarCarterasScore(carteras, defaultId) {
    const select = document.getElementById("filtroCarteraScore");

    if (!select) return;

    select.innerHTML = "";

    carteras.forEach(item => {
        const option = document.createElement("option");
        option.value = item.idcartera;
        option.textContent = `${item.idcartera} - ${item.nombre}`;
        select.appendChild(option);
    });

    select.value = String(defaultId || carteras[0]?.idcartera || "");

    actualizarChipCarteraScore();
}

async function cargarCatalogosScore(idcartera) {
    if (!idcartera) return;

    try {
        const response = await fetch(`${BASE_URL_SCORE}/score-telefonico/catalogos?idcartera=${encodeURIComponent(idcartera)}`, {
            cache: "no-store"
        });

        if (!response.ok) throw new Error(`HTTP ${response.status}`);

        const data = await response.json();

        scoreCatalogos = data || {};

        if (Array.isArray(scoreCatalogos.carteras) && scoreCatalogos.carteras.length) {
            refrescarCarterasDesdeCatalogo(scoreCatalogos.carteras, idcartera);
        }

        pintarFiltrosDinamicosScore(scoreCatalogos);
        renderActiveFiltersScore();
    } catch (error) {
        console.error("Error catálogos score:", error);

        scoreCatalogos = {};

        pintarFiltrosDinamicosScore({});
        renderActiveFiltersScore();

        showToast("No se pudieron cargar los catálogos reales.");
    }
}

function refrescarCarterasDesdeCatalogo(carteras, idcarteraActual) {
    const select = document.getElementById("filtroCarteraScore");

    if (!select) return;

    const valorActual = String(idcarteraActual || select.value || "");

    select.innerHTML = "";

    carteras.forEach(item => {
        const option = document.createElement("option");
        option.value = item.idcartera;
        option.textContent = `${item.idcartera} - ${item.nombre}`;
        select.appendChild(option);
    });

    select.value = valorActual;

    actualizarChipCarteraScore();
}

function pintarFiltrosDinamicosScore(catalogos) {
    const nav = document.getElementById("scoreSegmentNav");
    const body = document.getElementById("scoreSegmentBody");

    if (!nav || !body) return;

    const filtrosConData = FILTROS_SCORE_CONFIG
        .map(filtro => ({
            ...filtro,
            valores: limpiarOpcionesCatalogo(catalogos[filtro.catalogo] || [])
        }))
        .filter(filtro => filtro.valores.length);

    const secciones = agruparFiltrosPorSeccionScore(filtrosConData);
    const activoExiste = SCORE_SEGMENTS.some(segment => segment.key === scoreSegmentActivo);

    if (!activoExiste) scoreSegmentActivo = SCORE_SEGMENTS[0].key;

    nav.innerHTML = `
        <button class="score-segment-arrow" type="button" data-score-segment-arrow="prev" aria-label="Seccion anterior">&lsaquo;</button>
        ${SCORE_SEGMENTS.map(segment => `
            <button class="score-segment-tab ${segment.key === scoreSegmentActivo ? "active" : ""}" type="button" data-score-segment="${escapeHtml(segment.key)}">
                ${escapeHtml(segment.label)}
            </button>
        `).join("")}
        <button class="score-segment-arrow" type="button" data-score-segment-arrow="next" aria-label="Seccion siguiente">&rsaquo;</button>
    `;

    nav.querySelectorAll("[data-score-segment]").forEach(button => {
        button.addEventListener("click", () => {
            scoreSegmentActivo = button.dataset.scoreSegment;
            pintarFiltrosDinamicosScore(scoreCatalogos);
        });
    });

    nav.querySelectorAll("[data-score-segment-arrow]").forEach(button => {
        button.addEventListener("click", () => cambiarSegmentoScore(button.dataset.scoreSegmentArrow));
    });

    renderSegmentBodyScore(secciones);
}

function cambiarSegmentoScore(direction) {
    const index = SCORE_SEGMENTS.findIndex(segment => segment.key === scoreSegmentActivo);
    const delta = direction === "prev" ? -1 : 1;
    const nextIndex = (index + delta + SCORE_SEGMENTS.length) % SCORE_SEGMENTS.length;

    scoreSegmentActivo = SCORE_SEGMENTS[nextIndex].key;
    pintarFiltrosDinamicosScore(scoreCatalogos);
}

function renderSegmentBodyScore(secciones) {
    const body = document.getElementById("scoreSegmentBody");
    const segment = SCORE_SEGMENTS.find(item => item.key === scoreSegmentActivo) || SCORE_SEGMENTS[0];
    const filtros = secciones[segment.key] || [];

    if (!body) return;

    body.innerHTML = `<div class="score-filter-section-title">${escapeHtml(segment.title)}</div>`;

    if (!filtros.length) {
        body.innerHTML += `
            <div class="score-empty-filters">
                No hay filtros disponibles para esta seccion en la cartera seleccionada.
            </div>
        `;
        return;
    }

    filtros.forEach(filtro => {
        body.appendChild(crearFiltroDropdownScore(filtro));
    });
}

function agruparFiltrosPorSeccionScore(filtros) {
    return filtros.reduce((secciones, filtro) => {
        if (!secciones[filtro.seccion]) secciones[filtro.seccion] = [];
        secciones[filtro.seccion].push(filtro);
        return secciones;
    }, {});
}
function crearFiltroDropdownScore(filtro) {
    const wrapper = document.createElement("div");
    wrapper.className = "score-filter-item";
    wrapper.dataset.scoreGenerated = "1";
    const seleccionados = new Set(scoreFiltrosSeleccionados[filtro.key] || []);

    const label = document.createElement("label");
    label.className = "score-filter-label";
    label.textContent = filtro.label;

    const dropdown = document.createElement("div");
    dropdown.className = "dropdown-filter";
    dropdown.dataset.filter = filtro.key;

    dropdown.innerHTML = `
        <button class="dropdown-filter-toggle" type="button">
            <span class="dropdown-filter-text">Todos</span>
            <strong>⌄</strong>
        </button>

        <div class="dropdown-filter-menu">
            <div class="dropdown-filter-actions">
                <button type="button" data-filter-action="all">Todos</button>
                <button type="button" data-filter-action="none">Limpiar</button>
            </div>

            <div class="dropdown-filter-options">
                ${(filtro.valores || []).map(item => `
                    <label class="check-option">
                        <input type="checkbox" value="${escapeHtml(item)}" ${seleccionados.has(String(item)) ? "checked" : ""}>
                        <span>${escapeHtml(item)}</span>
                    </label>
                `).join("")}
            </div>
        </div>
    `;

    wrapper.appendChild(label);
    wrapper.appendChild(dropdown);

    inicializarDropdownScore(dropdown);

    return wrapper;
}

function inicializarDropdownScore(wrapper) {
    const toggle = wrapper.querySelector(".dropdown-filter-toggle");
    const menu = wrapper.querySelector(".dropdown-filter-menu");
    const checks = wrapper.querySelectorAll("input[type='checkbox']");
    const btnTodos = wrapper.querySelector("[data-filter-action='all']");
    const btnLimpiar = wrapper.querySelector("[data-filter-action='none']");

    menu?.addEventListener("click", event => {
        event.stopPropagation();
    });

    menu?.addEventListener("mousedown", event => {
        event.stopPropagation();
    });

    toggle?.addEventListener("click", event => {
        event.stopPropagation();

        document.querySelectorAll(".dropdown-filter.open").forEach(openFilter => {
            if (openFilter !== wrapper) openFilter.classList.remove("open");
        });

        wrapper.classList.toggle("open");
    });

    btnTodos?.addEventListener("click", event => {
        event.stopPropagation();

        checks.forEach(input => {
            input.checked = true;
        });

        sincronizarFiltroDropdownScore(wrapper);
        actualizarTextoDropdownFiltro(wrapper);
        aplicarFiltrosScoreDesdeUI();
    });

    btnLimpiar?.addEventListener("click", event => {
        event.stopPropagation();

        checks.forEach(input => {
            input.checked = false;
        });

        sincronizarFiltroDropdownScore(wrapper);
        actualizarTextoDropdownFiltro(wrapper);
        aplicarFiltrosScoreDesdeUI();
    });

    checks.forEach(input => {
        input.addEventListener("change", () => {
            sincronizarFiltroDropdownScore(wrapper);
            actualizarTextoDropdownFiltro(wrapper);
            aplicarFiltrosScoreDesdeUI();
        });
    });

    actualizarTextoDropdownFiltro(wrapper);
}

function sincronizarFiltroDropdownScore(wrapper) {
    const key = wrapper.dataset.filter;
    const values = Array.from(wrapper.querySelectorAll("input[type='checkbox']:checked"))
        .map(input => input.value)
        .filter(Boolean);

    if (!key) return;

    if (values.length) {
        scoreFiltrosSeleccionados[key] = values;
    } else {
        delete scoreFiltrosSeleccionados[key];
    }
}

function actualizarTextoDropdownFiltro(wrapper) {
    const textEl = wrapper.querySelector(".dropdown-filter-text");
    const checks = Array.from(wrapper.querySelectorAll("input[type='checkbox']"));
    const selected = checks.filter(input => input.checked).map(input => input.value);

    if (!textEl) return;

    if (!selected.length) {
        textEl.textContent = "Todos";
        wrapper.classList.remove("has-selection");
        return;
    }

    wrapper.classList.add("has-selection");

    if (selected.length === checks.length) {
        textEl.textContent = "Todos seleccionados";
        return;
    }

    if (selected.length <= 2) {
        textEl.textContent = selected.join(", ");
        return;
    }

    textEl.textContent = `${selected.length} seleccionados`;
}

function aplicarFiltrosScoreDesdeUI() {
    scorePage = 1;
    renderActiveFiltersScore();
    cargarResumenScore();
    cargarResultadosScore();
}

function agregarFiltrosScoreAParams(params) {
    Object.entries(scoreFiltrosSeleccionados).forEach(([key, values]) => {
        if (values.length) {
            params.set(key, values.join(","));
        }
    });
}

function renderActiveFiltersScore() {
    const container = document.getElementById("activeFiltersScore");

    if (!container) return;

    const chips = [];

    Object.entries(scoreFiltrosSeleccionados).forEach(([param, values]) => {
        const label = obtenerLabelFiltroScore(param);

        if (!values.length) return;

        let detail = "";

        if (values.length === 1) {
            detail = values[0];
        } else if (values.length === 2) {
            detail = values.join(", ");
        } else {
            detail = `${values.length} seleccionados`;
        }

        chips.push(`
            <span class="active-filter-chip" data-chip-filter="${escapeHtml(param)}">
                <span class="chip-text">${escapeHtml(label)}: ${escapeHtml(detail)}</span>
                <button type="button" data-remove-filter="${escapeHtml(param)}" aria-label="Quitar filtro ${escapeHtml(label)}">×</button>
            </span>
        `);
    });

    const search = document.getElementById("busquedaScoreInput")?.value?.trim();

    if (search) {
        chips.push(`
            <span class="active-filter-chip" data-chip-filter="search">
                <span class="chip-text">Búsqueda: ${escapeHtml(search)}</span>
                <button type="button" data-remove-filter="search" aria-label="Quitar búsqueda">×</button>
            </span>
        `);
    }

    if (!chips.length) {
        container.innerHTML = `<span class="active-filters-empty">Sin filtros activos</span>`;
        return;
    }

    container.innerHTML = chips.join("");

    container.querySelectorAll("[data-remove-filter]").forEach(button => {
        button.addEventListener("click", () => {
            quitarFiltroActivoScore(button.dataset.removeFilter);
        });
    });
}

function obtenerLabelFiltroScore(param) {
    const filtroCatalogo = FILTROS_SCORE_CONFIG.find(item => item.key === param);
    if (filtroCatalogo) return filtroCatalogo.label;

    return param;
}

function quitarFiltroActivoScore(filterName) {
    if (filterName === "search") {
        const search = document.getElementById("busquedaScoreInput");

        if (search) search.value = "";

        aplicarFiltrosScoreDesdeUI();
        return;
    }

    delete scoreFiltrosSeleccionados[filterName];

    const wrapper = document.querySelector(`.dropdown-filter[data-filter="${filterName}"]`);

    if (!wrapper) {
        aplicarFiltrosScoreDesdeUI();
        return;
    }

    wrapper.querySelectorAll("input[type='checkbox']").forEach(input => {
        input.checked = false;
    });

    actualizarTextoDropdownFiltro(wrapper);
    aplicarFiltrosScoreDesdeUI();
}

function limpiarFiltrosSecundariosScore() {
    scoreFiltrosSeleccionados = {};

    document.querySelectorAll(".dropdown-filter input[type='checkbox']").forEach(input => {
        input.checked = false;
    });

    document.querySelectorAll(".dropdown-filter").forEach(wrapper => {
        actualizarTextoDropdownFiltro(wrapper);
        wrapper.classList.remove("open");
    });

    const search = document.getElementById("busquedaScoreInput");
    if (search) search.value = "";

    scorePage = 1;
    renderActiveFiltersScore();
}

async function cargarResumenScore() {
    const idcartera = obtenerIdCarteraScore();

    if (!idcartera) return;

    const requestId = ++scoreResumenRequestId;
    const params = new URLSearchParams({ idcartera });

    agregarFiltrosScoreAParams(params);

    const search = document.getElementById("busquedaScoreInput")?.value?.trim();

    if (search) params.set("search", search);

    try {
        setKpisLoading(true);

        const response = await fetch(`${BASE_URL_SCORE}/score-telefonico/resumen?${params.toString()}`, {
            cache: "no-store"
        });

        if (!response.ok) throw new Error(`HTTP ${response.status}`);

        const data = await response.json();
        const telefonosResumen = Number(data?.filtrado?.telefonos ?? data?.telefonos_seleccionados ?? 0);

        if (requestId !== scoreResumenRequestId || idcartera !== obtenerIdCarteraScore()) {
            return;
        }

        if (scoreTotal > 0 && telefonosResumen === 0) {
            console.warn("Resumen score ignorado porque vino vacio mientras resultados tiene registros.", {
                scoreTotal,
                idcartera,
                data
            });
            return;
        }

        renderKpisScore(data);
    } catch (error) {
        console.error("Error resumen score:", error);
        showToast("No se pudieron cargar los KPIs reales del score.");
    } finally {
        setKpisLoading(false);
    }
}

async function cargarResultadosScore() {
    const idcartera = obtenerIdCarteraScore();

    if (!idcartera || scoreLoading) return;

    const params = new URLSearchParams({
        idcartera,
        page: String(scorePage),
        page_size: String(scorePageSize),
        order_by: scoreOrderBy,
        order_dir: scoreOrderDir
    });

    agregarFiltrosScoreAParams(params);

    const search = document.getElementById("busquedaScoreInput")?.value?.trim();

    if (search) params.set("search", search);

    try {
        setTableLoadingScore(true);

        const response = await fetch(`${BASE_URL_SCORE}/score-telefonico/resultados?${params.toString()}`, {
            cache: "no-store"
        });

        if (!response.ok) throw new Error(`HTTP ${response.status}`);

        const data = await response.json();

        scoreTotal = Number(data.total_registros || 0);
        scorePage = Number(data.page || scorePage);
        scorePageSize = Number(data.page_size || scorePageSize);
        scoreTotalPages = Math.max(1, Number(data.total_paginas || Math.ceil(scoreTotal / scorePageSize) || 1));

        renderScoreRows(data.data || []);
        actualizarResumenTablaScore();

        const telefonosKpi = numeroDesdeTexto(document.getElementById("kpiTelefonosScore")?.textContent);
        if (scoreTotal > 0 && !telefonosKpi) {
            cargarResumenScore();
        }
    } catch (error) {
        console.error("Error resultados score:", error);

        renderScoreRows([]);
        actualizarTituloResultadosScore(0);
        setText("resumenPaginacionScore", "No se pudieron cargar los teléfonos.");

        showToast("No se pudieron cargar los resultados del score.");
    } finally {
        setTableLoadingScore(false);
    }
}

function renderKpisScore(data) {
    const universo = data.universo || {};
    const filtrado = data.filtrado || {};

    const clientes = Number(filtrado.clientes ?? data.clientes_seleccionados ?? 0);
    const telefonos = Number(filtrado.telefonos ?? data.telefonos_seleccionados ?? 0);
    const whatsapp = Number(filtrado.whatsapp_validos ?? data.whatsapp_validos ?? 0);
    const timbrado = Number(filtrado.timbrado_3_4 ?? data.timbrado_3_4 ?? 0);
    const pctWhatsapp = Number(filtrado.porcentaje_whatsapp ?? data.porcentaje_whatsapp ?? 0);
    const pctTimbrado = Number(filtrado.porcentaje_timbrado ?? data.porcentaje_timbrado ?? 0);
    const capital = Number(filtrado.capital ?? data.capital_total ?? 0);

    setText("kpiClientesScore", formatNumber(clientes));
    setText("kpiClientesSubScore", `de ${formatNumber(universo.clientes || data.total_base_clientes || 0)} clientes activos`);

    setText("kpiTelefonosScore", formatNumber(telefonos));

    const telSub = document.querySelector("#kpiTelefonosScore + em");
    if (telSub) telSub.textContent = `de ${formatNumber(universo.telefonos || 0)} teléfonos`;

    setText("kpiWhatsappScore", `${pctWhatsapp.toFixed(1)}%`);
    setText("kpiWhatsappSubScore", `${formatNumber(whatsapp)} de ${formatNumber(telefonos)}`);

    setText("kpiTimbradoScore", `${pctTimbrado.toFixed(1)}%`);
    setText("kpiTimbradoSubScore", `${formatNumber(timbrado)} de ${formatNumber(telefonos)}`);

    setText("kpiCapitalScore", formatMoney(capital));
}

function renderScoreRows(rows) {
    const tbody = document.getElementById("scoreTableBody");

    if (!tbody) return;

    if (!rows.length) {
        tbody.innerHTML = `
            <tr>
                <td class="empty-score-row" colspan="12">
                    No hay teléfonos para la cartera o filtros seleccionados.
                </td>
            </tr>
        `;
        return;
    }

    tbody.innerHTML = rows.map(row => {
        const score = Number(valueOf(row, "SCORE_FINAL", "SCORE_TELEFONO", "score") || 0);
        const etiqueta = valueOf(row, "ETIQUETA_SCORE") || scoreLabel(score).text;
        const label = scoreLabelFromText(etiqueta, score);
        const whatsapp = valueOf(row, "WHATSAPP", "whatsapp");
        const osiptel = valueOf(row, "OSIPTEL", "osiptel");
        const timbrado = valueOf(row, "TIMBRADO", "timbrado") ?? 0;
        const resultado = valueOf(row, "MEJOR_RESULTADO", "resultado") || "-";

        return `
            <tr>
                <td>${escapeHtml(valueOf(row, "DNI", "dni") || "-")}</td>
                <td>${escapeHtml(valueOf(row, "IDCLIENTE", "idcliente") || "-")}</td>
                <td class="phone-cell">${phoneIcon(whatsapp)} ${escapeHtml(valueOf(row, "TELEFONO", "telefono") || "-")}</td>
                <td class="money">${formatMoney(valueOf(row, "CAPITAL", "capital"))}</td>
                <td><span class="score-pill ${label.className}">${formatScore(score)}</span></td>
                <td><span class="label-pill ${label.className}">${escapeHtml(label.text)}</span></td>
                <td><span class="round-pill ${timbradoClass(timbrado)}">${escapeHtml(timbrado ?? "-")}</span></td>
                <td>${stateBadge(whatsapp)}</td>
                <td>${stateBadge(osiptel)}</td>
                <td>${escapeHtml(valueOf(row, "INTENTOS_RECIENTES", "intentos") ?? 0)}</td>
                <td class="result-text" title="${escapeHtml(resultado)}">${escapeHtml(resultado)}</td>
                <td>${escapeHtml(valueOf(row, "ORDEN", "orden") || "-")}</td>
            </tr>
        `;
    }).join("");
}

function construirParamsScoreBase() {
    const idcartera = obtenerIdCarteraScore();

    const params = new URLSearchParams({
        idcartera,
        order_by: scoreOrderBy,
        order_dir: scoreOrderDir
    });

    agregarFiltrosScoreAParams(params);

    const search = document.getElementById("busquedaScoreInput")?.value?.trim();

    if (search) params.set("search", search);

    return params;
}

function exportarScoreTelefonico() {
    const idcartera = obtenerIdCarteraScore();

    if (!idcartera) {
        showToast("Selecciona una cartera antes de exportar.");
        return;
    }

    const params = construirParamsScoreBase();
    const url = `${BASE_URL_SCORE}/score-telefonico/exportar?${params.toString()}`;

    showToast("Preparando exportación...");

    const link = document.createElement("a");
    link.href = url;
    link.download = "";
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

function wireVisualActions() {
    document.querySelectorAll("[data-action]").forEach(button => {
        button.addEventListener("click", () => {
            const action = button.dataset.action;

            if (action === "buscar") {
                scorePage = 1;
                renderActiveFiltersScore();
                cargarResumenScore();
                cargarResultadosScore();
                return;
            }

            if (action === "limpiar") {
                limpiarFiltrosSecundariosScore();
                cargarResumenScore();
                cargarResultadosScore();
                showToast("Filtros limpiados.");
                return;
            }

            if (action === "filtrar") {
                scorePage = 1;
                renderActiveFiltersScore();
                cargarResumenScore();
                cargarResultadosScore();
                showToast("Filtros aplicados.");
                return;
            }

            if (action === "exportar") {
                exportarScoreTelefonico();
                return;
            }

            const messages = {
                guardar: "Guardado de vista pendiente para la siguiente fase.",
                columnas: "Selector de columnas pendiente para conectar.",
                acciones: "Acciones pendientes para conectar.",
                metodologia: "Metodología del score pendiente de documentar."
            };

            showToast(messages[action] || "Acción visual preparada.");
        });
    });

    const carteraSelect = document.getElementById("filtroCarteraScore");

    if (carteraSelect) {
        carteraSelect.addEventListener("change", async () => {
            scorePage = 1;
            scoreSegmentActivo = "cliente";

            actualizarChipCarteraScore();
            limpiarFiltrosSecundariosScore();

            const idcartera = obtenerIdCarteraScore();

            await cargarCatalogosScore(idcartera);

            await Promise.all([
                cargarResumenScore(),
                cargarResultadosScore()
            ]);
        });
    }

    const search = document.getElementById("busquedaScoreInput");

    if (search) {
        search.addEventListener("keydown", event => {
            if (event.key === "Enter") {
                event.preventDefault();

                scorePage = 1;
                renderActiveFiltersScore();
                cargarResumenScore();
                cargarResultadosScore();
            }
        });

        search.addEventListener("input", () => {
            clearTimeout(scoreSearchTimeout);

            scoreSearchTimeout = setTimeout(() => {
                scorePage = 1;
                renderActiveFiltersScore();
                cargarResumenScore();
                cargarResultadosScore();
            }, 500);
        });
    }

    const pageSize = document.getElementById("pageSizeScore");

    if (pageSize) {
        pageSize.addEventListener("change", () => {
            scorePageSize = Number(pageSize.value || 25);
            scorePage = 1;
            cargarResultadosScore();
        });
    }

    document.getElementById("prevScorePage")?.addEventListener("click", () => {
        if (scorePage <= 1) return;

        scorePage -= 1;
        cargarResultadosScore();
    });

    document.getElementById("nextScorePage")?.addEventListener("click", () => {
        if (scorePage >= scoreTotalPages) return;

        scorePage += 1;
        cargarResultadosScore();
    });
}

async function cargarUltimaActualizacionScore() {
    try {
        const response = await fetch(`${BASE_URL_SCORE}/score-telefonico/ultima-actualizacion`, {
            cache: "no-store"
        });

        if (!response.ok) throw new Error(`HTTP ${response.status}`);

        const data = await response.json();

        const fecha = data.fecha ? formatDateTime(data.fecha) : currentDateTime();
        const total = Number(data.total_registros || 0).toLocaleString("es-PE");

        const el = document.getElementById("ultimaActualizacionScore");

        if (el) el.textContent = `Última actualización: ${fecha} · ${total} registros`;
    } catch (error) {
        console.error("Error ultima actualizacion score:", error);
        setLastUpdate();
    }
}

function actualizarChipCarteraScore() {
    const select = document.getElementById("filtroCarteraScore");
    const chip = document.getElementById("chipCarteraActivaScore");

    if (!select || !chip) return;

    chip.textContent = `Cartera activa: ${select.options[select.selectedIndex]?.text || "-"}`;
}

function actualizarResumenTablaScore() {
    actualizarTituloResultadosScore(scoreTotal);

    const desde = scoreTotal ? (scorePage - 1) * scorePageSize + 1 : 0;
    const hasta = Math.min(scorePage * scorePageSize, scoreTotal);

    setText("resumenPaginacionScore", `Mostrando ${formatNumber(desde)} a ${formatNumber(hasta)} de ${formatNumber(scoreTotal)} registros`);
    setText("currentScorePage", String(scorePage));
    setText("totalScorePages", `/ ${formatNumber(scoreTotalPages)}`);

    const prev = document.getElementById("prevScorePage");
    const next = document.getElementById("nextScorePage");

    if (prev) prev.disabled = scorePage <= 1;
    if (next) next.disabled = scorePage >= scoreTotalPages;
}

function actualizarTituloResultadosScore(total) {
    setText("tituloResultadosScore", `Resultados (${formatNumber(total)} teléfonos)`);

    setText(
        "subtituloResultadosScore",
        total
            ? `Mostrando página ${formatNumber(scorePage)} de ${formatNumber(scoreTotalPages)}.`
            : "No hay teléfonos para la cartera o filtros seleccionados."
    );
}

function setKpisLoading(loading) {
    document.querySelectorAll(".kpi-card strong").forEach(el => {
        el.classList.toggle("loading-value", loading);
    });
}

function setTableLoadingScore(loading) {
    scoreLoading = loading;

    const card = document.querySelector(".results-card");

    card?.classList.toggle("table-loading", loading);

    if (loading) {
        setText("subtituloResultadosScore", "Consultando datos...");
    }
}

function scoreLabel(score) {
    if (score >= 85) return { text: "TOP CONTACTABLE", className: "top" };
    if (score >= 70) return { text: "CONTACTABLE MEDIO", className: "medium" };
    if (score >= 50) return { text: "DIGITAL PRIORITARIO", className: "digital" };
    return { text: "BAJA PRIORIDAD", className: "low" };
}

function scoreLabelFromText(text, score) {
    const normalized = String(text || "").toUpperCase();

    if (normalized.includes("TOP")) return { text: normalized, className: "top" };
    if (normalized.includes("MEDIO") || normalized.includes("CONTACTABLE")) return { text: normalized, className: "medium" };
    if (normalized.includes("DIGITAL")) return { text: normalized, className: "digital" };
    if (normalized.includes("BAJA")) return { text: normalized, className: "low" };

    return scoreLabel(score);
}

function timbradoClass(value) {
    if (Number(value) >= 3) return "ok";
    if (Number(value) >= 1) return "warn";
    return "muted";
}

function stateBadge(value) {
    const normalized = String(value || "").toUpperCase();
    const className = normalized === "SI" ? "yes" : normalized === "NO" ? "no" : "neutral";

    return `<span class="state-badge ${className}">${escapeHtml(normalized || "-")}</span>`;
}

function phoneIcon(whatsapp) {
    return String(whatsapp).toUpperCase() === "SI"
        ? `<span class="phone-tag wa">WA</span>`
        : `<span class="phone-tag tel">TEL</span>`;
}

function setLastUpdate() {
    const el = document.getElementById("ultimaActualizacionScore");

    if (!el) return;

    el.textContent = `Última actualización: ${currentDateTime()}`;
}

function showToast(message) {
    const toast = document.getElementById("scoreToast");

    if (!toast) return;

    toast.textContent = message;
    toast.classList.add("visible");

    clearTimeout(window.scoreToastTimeout);

    window.scoreToastTimeout = setTimeout(() => {
        toast.classList.remove("visible");
    }, 2200);
}

function formatMoney(value) {
    return `S/ ${Number(value || 0).toLocaleString("es-PE", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    })}`;
}

function formatNumber(value) {
    return Number(value || 0).toLocaleString("es-PE");
}

function numeroDesdeTexto(value) {
    const limpio = String(value || "").replace(/[^\d.-]/g, "");
    return Number(limpio || 0);
}

function formatScore(value) {
    const number = Number(value || 0);

    return Number.isInteger(number) ? String(number) : number.toFixed(1);
}

function formatDateTime(value) {
    const date = new Date(value);

    if (Number.isNaN(date.getTime())) return String(value);

    return date.toLocaleString("es-PE", {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit"
    });
}

function currentDateTime() {
    return new Date().toLocaleString("es-PE", {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit"
    });
}

function valueOf(row, ...keys) {
    for (const key of keys) {
        if (row?.[key] !== undefined && row?.[key] !== null) return row[key];
    }

    return null;
}

function setText(id, value) {
    const el = document.getElementById(id);

    if (el) el.textContent = value;
}

function limpiarOpcionesCatalogo(opciones) {
    return Array.from(new Set(
        (opciones || [])
            .map(item => String(item ?? "").trim())
            .filter(item => item && item.toUpperCase() !== "NULL" && item !== "-")
    ));
}

function escapeHtml(value) {
    return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}
