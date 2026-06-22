const BASE_URL_MATRIZ = `${window.location.protocol}//${window.location.hostname}:8000`;

let matrizData = { fechas: [], agentes: [], fecha_mes_anterior: "" };
let metricaMatriz = "generacion";
let ordenMatriz = { campo: "total", direccion: "desc" };

document.addEventListener("DOMContentLoaded", () => {
    if (!exigirSesion()) return;
    cargarMatrizPage();
});

async function cargarMatrizPage() {
    const estado = document.getElementById("estadoMatrizPage");
    estado.textContent = "Cargando...";

    try {
        matrizData = await obtenerMatrizPage();
        renderMatrizPage();
        estado.textContent = `${(matrizData.agentes || []).length} agentes`;
    } catch (error) {
        console.error("ERROR MATRIZ PAGE:", error);
        estado.textContent = "Error";
        document.getElementById("tbodyMatrizPage").innerHTML =
            `<tr><td class="empty-row" colspan="6">No se pudo cargar la matriz. ${escapeHtml(error.message || "")}</td></tr>`;
    }
}

async function obtenerMatrizPage() {
    const params = new URLSearchParams(window.location.search);
    const fecha = params.get("fecha") || fechaLocalInput();
    const ids = idsConsultaMatriz(params);

    if (ids.length) {
        const respuestas = await Promise.all(ids.map(id => fetchMatrizPage(fecha, id)));
        return unirMatricesPage(respuestas);
    }

    return fetchMatrizPage(fecha, "");
}

async function fetchMatrizPage(fecha, idcartera) {
    const params = new URLSearchParams();
    if (fecha) params.set("fecha", fecha);
    if (idcartera) params.set("idcartera", idcartera);

    const response = await fetch(`${BASE_URL_MATRIZ}/control-horario/matriz-mensual?${params.toString()}`, {
        cache: "no-store"
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
}

function unirMatricesPage(respuestas) {
    const base = {
        fecha: respuestas.find(item => item?.fecha)?.fecha || "",
        mes: respuestas.find(item => item?.mes)?.mes || "",
        fechas: respuestas.find(item => item?.fechas?.length)?.fechas || [],
        fecha_mes_anterior: respuestas.find(item => item?.fecha_mes_anterior)?.fecha_mes_anterior || "",
        agentes: []
    };
    const agentes = new Map();

    respuestas.forEach(data => {
        (data?.agentes || []).forEach(row => {
            const key = String(row.idusuario || row.agente || "");
            if (!key) return;

            const actual = agentes.get(key) || {
                ...row,
                dias: {},
                mes_anterior: { generacion: 0, recupero: 0, proyectado: 0 },
                mes_anterior_total: { generacion: 0, recupero: 0, proyectado: 0 }
            };

            Object.entries(row.dias || {}).forEach(([fecha, valores]) => {
                const dia = actual.dias[fecha] || { generacion: 0, recupero: 0, proyectado: 0 };
                dia.generacion += Number(valores.generacion || 0);
                dia.recupero += Number(valores.recupero || 0);
                dia.proyectado += Number(valores.proyectado || 0);
                actual.dias[fecha] = dia;
            });

            ["generacion", "recupero", "proyectado"].forEach(keyMetrica => {
                actual.mes_anterior[keyMetrica] += Number(row.mes_anterior?.[keyMetrica] || 0);
                actual.mes_anterior_total[keyMetrica] += Number(row.mes_anterior_total?.[keyMetrica] || 0);
            });

            if (actual.cartera && row.cartera && actual.cartera !== row.cartera) {
                actual.cartera = "Varias carteras";
            }

            agentes.set(key, actual);
        });
    });

    base.agentes = [...agentes.values()];
    return base;
}

function idsConsultaMatriz(params) {
    const idsParam = (params.get("ids") || params.get("cartera") || "")
        .split(",")
        .map(id => id.trim())
        .filter(id => /^\d+$/.test(id));
    if (idsParam.length) return idsParam;

    const tipo = typeof normalizarTipoUsuario === "function"
        ? normalizarTipoUsuario(localStorage.getItem("tipo"))
        : String(localStorage.getItem("tipo") || "").trim().toUpperCase();
    if (tipo !== "SUPERVISOR") return [];

    const idsSesion = typeof obtenerIdCarterasSesion === "function"
        ? obtenerIdCarterasSesion()
        : [
            ...(localStorage.getItem("idcarteras") || "").split(","),
            localStorage.getItem("idcartera")
        ];

    return [...new Set(idsSesion.map(id => String(id || "").trim()).filter(id => /^\d+$/.test(id)))];
}

function cambiarMetricaMatrizPage(metrica) {
    metricaMatriz = metrica;
    document.querySelectorAll(".metric-switch button").forEach(button => {
        button.classList.toggle("active", button.dataset.metrica === metrica);
    });
    ordenMatriz = { campo: "total", direccion: "desc" };
    renderMatrizPage();
}

function renderMatrizPage() {
    const fechaFiltro = new URLSearchParams(window.location.search).get("fecha") || matrizData.fecha || fechaLocalInput();
    const fechas = fechasVisibles(fechaFiltro);
    const rows = ordenarRowsMatriz((matrizData.agentes || []).map(row => prepararRow(row, fechas)));
    const mesTexto = nombreMes(fechaFiltro);
    const comparativo = matrizData.fecha_mes_anterior ? formatoFecha(matrizData.fecha_mes_anterior) : "mes anterior";

    document.getElementById("tituloMatrizPage").textContent = `Matriz mensual por agente - ${mesTexto}`;
    document.getElementById("subtituloMatrizPage").textContent =
        `${etiquetaMetrica()} ${metricaMatriz === "proyectado" ? "del mes completo" : "hasta la fecha filtrada"}. Corte acumulado al ${comparativo}; variacion contra ese mismo corte.`;
    document.getElementById("tituloTablaMatriz").textContent = `${etiquetaMetrica()} por agente`;
    renderResumen(rows);
    renderAlertasMatriz(rows, fechas);
    renderTabla(rows, fechas);
}

function fechasVisibles(fechaFiltro) {
    const fechas = matrizData.fechas || [];
    if (metricaMatriz === "proyectado") return fechas;
    const limite = String(fechaFiltro || "").slice(0, 10);
    return fechas.filter(fecha => String(fecha).slice(0, 10) <= limite);
}

function prepararRow(row, fechas) {
    const total = fechas.reduce((acc, fecha) => acc + valorMetrica(row.dias?.[fecha]), 0);
    const corteAnterior = valorMetrica(row.mes_anterior);
    const totalAnterior = valorMetrica(row.mes_anterior_total);
    const variacion = calcularVariacion(total, corteAnterior);

    return {
        ...row,
        total,
        corteAnterior,
        totalAnterior,
        variacion
    };
}

function ordenarRowsMatriz(rows) {
    const factor = ordenMatriz.direccion === "asc" ? 1 : -1;
    return [...rows].sort((a, b) => {
        const va = valorOrden(a, ordenMatriz.campo);
        const vb = valorOrden(b, ordenMatriz.campo);
        if (typeof va === "string" || typeof vb === "string") {
            return String(va).localeCompare(String(vb), "es") * factor;
        }
        return (Number(va || 0) - Number(vb || 0)) * factor;
    });
}

function valorOrden(row, campo) {
    if (campo === "agente") return row.agente || "";
    if (campo === "total") return row.total;
    if (campo === "corte") return row.corteAnterior;
    if (campo === "total_anterior") return row.totalAnterior;
    if (campo === "variacion") return row.variacion.diferencia;
    if (campo.startsWith("fecha:")) return valorMetrica(row.dias?.[campo.slice(6)]);
    return 0;
}

function ordenarMatriz(campo) {
    ordenMatriz = {
        campo,
        direccion: ordenMatriz.campo === campo && ordenMatriz.direccion === "desc" ? "asc" : "desc"
    };
    renderMatrizPage();
}

function renderResumen(rows) {
    const total = rows.reduce((acc, row) => acc + row.total, 0);
    const corte = rows.reduce((acc, row) => acc + row.corteAnterior, 0);
    const anterior = rows.reduce((acc, row) => acc + row.totalAnterior, 0);
    const variacion = calcularVariacion(total, corte);
    const activos = rows.filter(row => row.total > 0).length;

    const cards = [
        ["Agentes", num(rows.length), ""],
        ["Agentes con monto", num(activos), ""],
        [`Total ${etiquetaMetrica()}`, num(total), ""],
        ["Corte comparable", num(corte), ""],
        ["Total mes anterior", num(anterior), ""],
        ["Var. vs corte", formatoVariacion(variacion), claseVar(variacion)]
    ];

    document.getElementById("resumenMatrizPage").innerHTML = cards.map(([label, value, tone]) => `
        <article class="metric-card ${tone}">
            <span>${escapeHtml(label)}</span>
            <strong>${escapeHtml(value)}</strong>
        </article>
    `).join("");
}

function renderAlertasMatriz(rows, fechas) {
    const alertas = construirAlertasCriticas(rows, fechas).slice(0, 8);
    const contenedor = document.getElementById("alertasMatrizPage");

    if (!alertas.length) {
        contenedor.innerHTML = "";
        return;
    }

    contenedor.innerHTML = alertas.map(alerta => `
        <article class="alerta-critica ${alerta.nivel}">
            <strong>${escapeHtml(alerta.titulo)}</strong>
            <span>${escapeHtml(alerta.detalle)}</span>
        </article>
    `).join("");
}

function construirAlertasCriticas(rows, fechas) {
    const fechaCorte = new URLSearchParams(window.location.search).get("fecha") || matrizData.fecha || fechaLocalInput();
    const fechasHastaCorte = fechas.filter(fecha => String(fecha).slice(0, 10) <= String(fechaCorte).slice(0, 10));
    const ultimas5 = fechasHastaCorte.slice(-5);
    const ultimas3 = fechasHastaCorte.slice(-3);
    const alertas = [];

    rows.forEach(row => {
        const totalGeneracion = totalPorMetrica(row, fechasHastaCorte, "generacion");
        const totalRecaudo = totalPorMetrica(row, fechasHastaCorte, "recupero");
        const totalProyectado = totalPorMetrica(row, matrizData.fechas || [], "proyectado");

        if (ultimas5.length >= 5 && ultimas5.every(fecha => valorMetricaDirecta(row.dias?.[fecha], "generacion") <= 0)) {
            alertas.push({
                nivel: "critica",
                titulo: "5 dias sin generar",
                detalle: row.agente || "-"
            });
        } else if (ultimas3.length >= 3 && ultimas3.every(fecha => valorMetricaDirecta(row.dias?.[fecha], "generacion") <= 0)) {
            alertas.push({
                nivel: "alta",
                titulo: "3 dias sin generar",
                detalle: row.agente || "-"
            });
        }

        if (ultimas5.length >= 5 && ultimas5.every(fecha => valorMetricaDirecta(row.dias?.[fecha], "recupero") <= 0)) {
            alertas.push({
                nivel: "critica",
                titulo: "5 dias sin recaudar",
                detalle: row.agente || "-"
            });
        }

        if (totalProyectado <= 0 && (totalGeneracion > 0 || totalRecaudo > 0)) {
            alertas.push({
                nivel: "alta",
                titulo: "Agente sin proyectado",
                detalle: row.agente || "-"
            });
        }
    });

    const peso = { critica: 1, alta: 2 };
    return alertas.sort((a, b) => (peso[a.nivel] || 9) - (peso[b.nivel] || 9));
}

function totalPorMetrica(row, fechas, metrica) {
    return fechas.reduce((acc, fecha) => acc + valorMetricaDirecta(row.dias?.[fecha], metrica), 0);
}

function valorMetricaDirecta(valores, metrica) {
    return Number((valores || {})[metrica] || 0);
}

function renderTabla(rows, fechas) {
    const thead = document.getElementById("theadMatrizPage");
    const tbody = document.getElementById("tbodyMatrizPage");

    thead.innerHTML = `
        <tr>
            <th class="agent-col sortable" onclick="ordenarMatriz('agente')">Agente</th>
            ${fechas.map(fecha => `<th class="day-col sortable" onclick="ordenarMatriz('fecha:${fecha}')">${escapeHtml(etiquetaFecha(fecha))}</th>`).join("")}
            <th class="summary-col sortable" onclick="ordenarMatriz('total')">Total</th>
            <th class="summary-col sortable" onclick="ordenarMatriz('corte')">Corte mes ant.</th>
            <th class="summary-col sortable" onclick="ordenarMatriz('total_anterior')">Total mes ant.</th>
            <th class="summary-col sortable" onclick="ordenarMatriz('variacion')">Var.</th>
        </tr>
    `;

    if (!rows.length) {
        tbody.innerHTML = `<tr><td class="empty-row" colspan="${fechas.length + 5}">No hay agentes para el filtro seleccionado.</td></tr>`;
        return;
    }

    const cortesTotal = calcularCortesTotal(rows);

    tbody.innerHTML = rows.map(row => `
        <tr>
            <td class="agent-col">
                <strong>${escapeHtml(row.agente || "-")}</strong>
                <small>${escapeHtml(row.cartera || "")}</small>
            </td>
            ${fechas.map(fecha => {
                const value = valorMetrica(row.dias?.[fecha]);
                return `<td class="day-col ${heat(value)}">${num(value)}</td>`;
            }).join("")}
            <td class="summary-col ${claseTotalPorCuartil(row.total, cortesTotal)}">${num(row.total)}</td>
            <td class="summary-col ${claseReferencia(row.corteAnterior)}">${num(row.corteAnterior)}</td>
            <td class="summary-col ${claseReferencia(row.totalAnterior)}">${num(row.totalAnterior)}</td>
            <td class="summary-col ${claseVar(row.variacion)}">${formatoVariacion(row.variacion)}</td>
        </tr>
    `).join("");
}

function valorMetrica(valores) {
    return Number((valores || {})[metricaMatriz] || 0);
}

function calcularVariacion(actual, anterior) {
    const actualNum = Number(actual || 0);
    const anteriorNum = Number(anterior || 0);
    const diferencia = actualNum - anteriorNum;
    return {
        actual: actualNum,
        anterior: anteriorNum,
        diferencia,
        porcentaje: anteriorNum >= 900 ? diferencia / anteriorNum : null
    };
}

function formatoVariacion(value) {
    const dif = Number(value?.diferencia || 0);
    const signo = dif > 0 ? "+" : "";
    const monto = `${signo}${num(dif)}`;

    if (value?.porcentaje === null || value?.porcentaje === undefined) {
        if (Number(value?.anterior || 0) <= 0 && Number(value?.actual || 0) > 0) return `${monto} | nuevo`;
        return monto;
    }

    const pct = Number(value.porcentaje || 0) * 100;
    return `${monto} | ${pct > 0 ? "+" : ""}${pct.toFixed(1)}%`;
}

function claseVar(value) {
    const dif = Number(value?.diferencia || 0);
    if (dif > 0) return "var-up";
    if (dif < 0) return "var-down";
    return "var-flat";
}

function calcularCortesTotal(rows) {
    const valores = rows
        .map(row => Number(row.total || 0))
        .filter(value => value > 0)
        .sort((a, b) => a - b);

    if (!valores.length) return null;

    return {
        q1: valorPercentil(valores, 0.25),
        q2: valorPercentil(valores, 0.50),
        q3: valorPercentil(valores, 0.75),
        min: valores[0],
        max: valores[valores.length - 1]
    };
}

function valorPercentil(valores, percentil) {
    if (valores.length === 1) return valores[0];
    const posicion = (valores.length - 1) * percentil;
    const base = Math.floor(posicion);
    const resto = posicion - base;
    const siguiente = valores[base + 1] ?? valores[base];
    return valores[base] + resto * (siguiente - valores[base]);
}

function claseTotalPorCuartil(value, cortes) {
    const total = Number(value || 0);
    if (total <= 0) return "heat-zero";
    if (!cortes || cortes.max === cortes.min) return "total-ahead";
    if (total <= cortes.q1) return "total-behind";
    if (total <= cortes.q2) return "total-watch";
    if (total <= cortes.q3) return "total-mid";
    return "total-ahead";
}

function claseReferencia(value) {
    return Number(value || 0) <= 0 ? "heat-zero" : "summary-reference";
}

function heat(value) {
    const n = Number(value || 0);
    if (n <= 0) return "heat-zero";
    if (n < 900) return "heat-low";
    if (n <= 1500) return "heat-mid";
    return "heat-high";
}

function etiquetaMetrica() {
    if (metricaMatriz === "recupero") return "Recaudacion";
    if (metricaMatriz === "proyectado") return "Proyectado";
    return "Generacion";
}

function fechaLocalInput(date = new Date()) {
    return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

function fechaDesdeIso(fecha) {
    const parts = String(fecha || "").slice(0, 10).split("-").map(Number);
    if (parts.length !== 3 || parts.some(Number.isNaN)) return null;
    return new Date(parts[0], parts[1] - 1, parts[2]);
}

function etiquetaFecha(fecha) {
    const date = fechaDesdeIso(fecha);
    if (!date) return fecha;
    return `${date.getDate()}/${date.getMonth() + 1}`;
}

function formatoFecha(fecha) {
    const date = fechaDesdeIso(fecha);
    if (!date) return fecha;
    return date.toLocaleDateString("es-PE", { day: "2-digit", month: "2-digit", year: "numeric" });
}

function nombreMes(fecha) {
    const date = fechaDesdeIso(fecha);
    if (!date) return "-";
    return date.toLocaleDateString("es-PE", { month: "long", year: "numeric" });
}

function num(value) {
    return Number(value || 0).toLocaleString("es-PE", { maximumFractionDigits: 0 });
}

function escapeHtml(value) {
    return String(value ?? "-")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}
