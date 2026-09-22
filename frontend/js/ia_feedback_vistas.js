/* ============================================================================
   Centro de Calidad — vistas v2 (Resumen/dimensiones, Evaluaciones, Planes de
   mejora, Calibración, Reportes) y estados de carga.

   Se carga DESPUÉS de ia_feedback.js y reemplaza sus funciones de pintado por
   nombre (misma firma). Las funciones antiguas quedan en ia_feedback.js sin
   usarse: quitar este archivo del HTML vuelve a la versión anterior.

   Reglas únicas que usan TODAS las vistas de este archivo:
   - Nota de la llamada = score_final (ya es la vigente: la calibrada si
     Calidad la publicó). null = "No evaluable": fuera de promedios, se cuenta
     aparte.
   - Un criterio está MEDIDO si salió Cumple, No cumple o Parcial. No aplica,
     No evaluable y Requiere revisión no entran a ningún porcentaje.
   - Brecha = No cumple o Parcial (esBrechaItemIa, la misma del Pareto).
   - Cumplimiento de un criterio = llamadas donde cumple / llamadas donde se
     midió. Siempre se muestra N.
   - Cumplimiento de un bloque = puntos obtenidos / puntos posibles de sus
     criterios medidos (la misma lógica del score de la llamada).
   - Meta = 85%, la que la página ya mostraba como "Meta operativa".
   ============================================================================ */

const META_CALIDAD_V2 = 85;
const BASE_MINIMA_V2 = 3; // con menos medidas el % se marca como "base chica"
// Regla ACORDADA el 21/09/2026 (la misma de planes_mejora_service.REGLA).
const REGLA_PLAN_V2 = { ultimas: 5, fallas: 2, minimo: 3, meta: 80, dias: 30 };

/* ---------------------------------------------------------------- modelo */

function estadoItemV2(item = {}) {
    const cal = String(item.calificacion || normalizarCalificacionItemIa(item) || "").toLowerCase();
    if (cal.includes("no cumple") || cal.includes("no evidenciado")) return "NO_CUMPLE";
    if (cal.includes("parcial")) return "PARCIAL";
    if (cal.includes("no aplica")) return "NO_APLICA";
    if (cal.includes("no evaluable")) return "NO_EVALUABLE";
    if (cal.includes("revis")) return "REVISION";
    if (cal.includes("cumple")) return "CUMPLE";
    return "REVISION";
}

function esMedidoV2(estado) {
    return estado === "CUMPLE" || estado === "NO_CUMPLE" || estado === "PARCIAL";
}

function itemsV2(row) {
    return evaluacionCalidadItemsIa(row).filter(i => i && typeof i === "object").map(item => {
        const estado = estadoItemV2(item);
        return {
            codigo: String(item.codigo_criterio || item.codigo || "").trim(),
            nombre: String(item.item || item.nombre || item.factor_sgc || "Criterio").trim(),
            bloque: String(item.bloque || "").trim(),
            bloqueNombre: String(item.bloque_nombre || item.segmento || item.bloque || "Sin bloque").trim(),
            peso: Number(item.peso || 0),
            nota: Number(item.nota || 0),
            estado,
            medido: esMedidoV2(estado),
            brecha: estado === "NO_CUMPLE" || estado === "PARCIAL",
        };
    });
}

function notaV2(row) {
    if (row.evaluable === false) return null;
    const v = row.score_final;
    return v === null || v === undefined || v === "" || Number.isNaN(Number(v)) ? null : Number(v);
}

function fechaV2(row) {
    return row.fecha_llamada || row.fecha_creacion || "";
}

function agenteV2(row) {
    const t = String(row.agente || "").trim();
    return !t || /^sin agente/i.test(t) || ["-", "none", "null"].includes(t.toLowerCase()) ? "" : t;
}

function tieneErrorCriticoV2(row) {
    return Boolean(row.error_critico || row.falta_anulante || Number(row.total_puntos_criticos || 0) > 0);
}

function promedioV2(valores) {
    const v = valores.filter(x => x !== null && x !== undefined && !Number.isNaN(x));
    return v.length ? v.reduce((a, b) => a + b, 0) / v.length : null;
}

function claveCriterioV2(it) {
    return it.codigo || it.nombre;
}

// Cumplimiento por criterio sobre un conjunto de llamadas.
function porCriterioV2(rows) {
    const mapa = new Map();
    rows.forEach(row => itemsV2(row).forEach(it => {
        const k = claveCriterioV2(it);
        const c = mapa.get(k) || { clave: k, codigo: it.codigo, nombre: it.nombre, bloqueNombre: it.bloqueNombre, bloque: it.bloque, peso: it.peso, medidas: 0, cumple: 0, brechas: 0, noMedidas: 0 };
        if (it.medido) {
            c.medidas += 1;
            if (it.estado === "CUMPLE") c.cumple += 1;
            if (it.brecha) c.brechas += 1;
        } else {
            c.noMedidas += 1;
        }
        mapa.set(k, c);
    }));
    return [...mapa.values()].map(c => ({ ...c, pct: c.medidas ? (c.cumple / c.medidas) * 100 : null }));
}

// Cumplimiento por bloque: puntos obtenidos / puntos posibles de lo medido.
function porBloqueV2(rows) {
    const mapa = new Map();
    rows.forEach(row => {
        const vistos = new Set();
        itemsV2(row).forEach(it => {
            const b = mapa.get(it.bloqueNombre) || { nombre: it.bloqueNombre, codigo: it.bloque, num: 0, den: 0, llamadas: 0, criterios: new Map() };
            if (it.medido && it.peso > 0) {
                b.num += Math.min(it.nota, it.peso);
                b.den += it.peso;
                if (!vistos.has(it.bloqueNombre)) { b.llamadas += 1; vistos.add(it.bloqueNombre); }
            }
            const c = b.criterios.get(claveCriterioV2(it)) || { nombre: it.nombre, medidas: 0, cumple: 0 };
            if (it.medido) { c.medidas += 1; if (it.estado === "CUMPLE") c.cumple += 1; }
            b.criterios.set(claveCriterioV2(it), c);
            mapa.set(it.bloqueNombre, b);
        });
    });
    return [...mapa.values()].map(b => {
        const criterios = [...b.criterios.values()].filter(c => c.medidas).map(c => ({ ...c, pct: (c.cumple / c.medidas) * 100 }));
        criterios.sort((x, y) => x.pct - y.pct);
        return { ...b, pct: b.den ? (b.num / b.den) * 100 : null, masDebil: criterios[0] || null, sinMedir: [...b.criterios.values()].filter(c => !c.medidas).map(c => c.nombre) };
    });
}

// Modelo por agente: la base de Planes de mejora, Reportes y la prioridad del Resumen.
function modeloAgentesV2(rows) {
    const mapa = new Map();
    rows.forEach(row => {
        const ag = agenteV2(row);
        if (!ag) return;
        const a = mapa.get(ag) || { agente: ag, rows: [], carteras: new Set() };
        a.rows.push(row);
        if (row.cartera) a.carteras.add(row.cartera);
        mapa.set(ag, a);
    });
    return [...mapa.values()].map(a => {
        const orden = [...a.rows].sort((x, y) => String(fechaV2(y)).localeCompare(String(fechaV2(x))));
        const notas = orden.map(notaV2).filter(n => n !== null);
        const promedio = promedioV2(notas);
        const recientes = notas.slice(0, 3);
        const previas = notas.slice(3, 6);
        const tendencia = recientes.length >= 2 && previas.length >= 2 ? promedioV2(recientes) - promedioV2(previas) : null;
        // Reincidencia: por criterio, en sus últimas N mediciones del agente.
        const historial = new Map();
        orden.forEach(row => itemsV2(row).forEach(it => {
            if (!it.medido) return;
            const k = claveCriterioV2(it);
            const h = historial.get(k) || { nombre: it.nombre, codigo: it.codigo, estados: [], ultimaFalla: null };
            if (h.estados.length < REGLA_PLAN_V2.ultimas) {
                h.estados.push(it.brecha);
                if (it.brecha && !h.ultimaFalla) h.ultimaFalla = row.id_feedback;
            }
            historial.set(k, h);
        }));
        const reincidentes = [...historial.values()]
            .map(h => ({ ...h, fallas: h.estados.filter(Boolean).length, medidas: h.estados.length }))
            .filter(h => h.medidas >= REGLA_PLAN_V2.minimo && h.fallas >= REGLA_PLAN_V2.fallas)
            .sort((x, y) => y.fallas - x.fallas || y.fallas / y.medidas - x.fallas / x.medidas);
        const criticos = a.rows.filter(tieneErrorCriticoV2).length;
        const bajoMeta = promedio !== null && promedio < META_CALIDAD_V2;
        const prioridad = (reincidentes.length ? 1000 : 0) + (criticos * 50) + (bajoMeta ? (META_CALIDAD_V2 - promedio) : 0);
        return {
            agente: a.agente,
            carteras: [...a.carteras],
            total: a.rows.length,
            evaluables: notas.length,
            promedio,
            tendencia,
            notas: notas.slice(0, 8).reverse(),
            reincidentes,
            criticos,
            bajoMeta,
            prioridad,
            ultima: orden[0],
            porRevisar: a.rows.filter(r => !esEvaluacionValidadaIa(r)).length,
        };
    }).sort((x, y) => y.prioridad - x.prioridad || (x.promedio ?? 999) - (y.promedio ?? 999));
}

/* --------------------------------------------------------------- helpers */

function pctV2(v, dec = 0) {
    return v === null || v === undefined ? "—" : `${Number(v).toFixed(dec)}%`;
}

function claseNotaV2(v) {
    if (v === null || v === undefined) return "na";
    return v >= META_CALIDAD_V2 ? "ok" : v >= 70 ? "warn" : "risk";
}

// conMeta=false para barras que no son una nota (frecuencias, conteos).
function barraV2(v, clase = claseNotaV2(v), conMeta = true) {
    const w = v === null || v === undefined ? 0 : Math.max(2, Math.min(100, v));
    return `<span class="v2-bar ${clase}"><i style="width:${w}%"></i>${conMeta ? `<b style="left:${META_CALIDAD_V2}%"></b>` : ""}</span>`;
}

function carterasCortoV2(lista) {
    if (!lista.length) return "Sin cartera";
    return lista.length === 1 ? lista[0] : `${lista[0]} +${lista.length - 1}`;
}

function chipV2(texto, clase = "") {
    return `<span class="v2-chip ${clase}">${escapeHtml(texto)}</span>`;
}

function kpiV2(titulo, valor, detalle = "", clase = "") {
    return `<article class="v2-kpi ${clase}"><span>${escapeHtml(titulo)}</span><strong>${escapeHtml(valor)}</strong><small>${detalle}</small></article>`;
}

function vacioV2(titulo, detalle = "") {
    return `<div class="v2-empty"><strong>${escapeHtml(titulo)}</strong>${detalle ? `<small>${detalle}</small>` : ""}</div>`;
}

function fechaCortaV2(v) {
    if (!v) return "-";
    const f = new Date(v);
    if (Number.isNaN(f.getTime())) return String(v);
    return f.toLocaleString("es-PE", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
}

function tendenciaV2(t) {
    if (t === null || t === undefined) return `<span class="v2-trend na" title="Hacen falta al menos 4 evaluaciones medibles">sin base</span>`;
    const clase = t >= 2 ? "up" : t <= -2 ? "down" : "flat";
    const flecha = t >= 2 ? "▲" : t <= -2 ? "▼" : "▬";
    return `<span class="v2-trend ${clase}" title="Promedio de las 3 últimas vs las 3 anteriores">${flecha} ${t > 0 ? "+" : ""}${t.toFixed(1)} pp</span>`;
}

function sparkV2(notas) {
    if (!notas.length) return "";
    return `<span class="v2-spark" title="Últimas notas, de la más antigua a la más reciente">${notas.map(n => `<i class="${claseNotaV2(n)}" style="height:${Math.max(8, n)}%"></i>`).join("")}</span>`;
}

function skeletonV2(lineas = 3) {
    return `<div class="v2-skeleton">${Array.from({ length: lineas }, (_, i) => `<i style="width:${90 - i * 12}%"></i>`).join("")}</div>`;
}

/* ------------------------------------------------ carga y estados de carga */

let cargaReporteriaV2 = null;

// Fuente de la reporteria: "json" (actual, re-aplica guardas en cada lectura)
// o "sql" (tablas). Mientras se valida con tools/comparar_reporteria.py, la
// fuente SQL se activa abriendo la pagina con ?fuente=sql (queda recordada en
// este navegador) y se vuelve con ?fuente=json.
function fuenteReporteriaV2() {
    try {
        const url = new URLSearchParams(window.location.search).get("fuente");
        if (url === "sql" || url === "json") localStorage.setItem("iaFuenteReporteria", url);
        const guardada = localStorage.getItem("iaFuenteReporteria");
        return guardada === "sql" ? "sql" : "json";
    } catch {
        return "json";
    }
}

// Cada bloque dice que esta construyendo, en su propio espacio.
const CONTENEDORES_CARGA_V2 = {
    resumenKpisEjecutivosIa: "kpis",
    tendenciaCalidadResumenIa: "Construyendo la evolución de calidad…",
    paretoResumenIa: "Calculando las brechas del periodo…",
    dimensionCopcResumenIa: "Calculando el desempeño por bloque…",
    agentesPriorizadosResumenIa: "Identificando agentes a intervenir…",
    accionesMejoraResumenIa: "Revisando acciones de mejora…",
    evaluacionesV2Ia: "Cargando evaluaciones…",
    planesV2Ia: "Analizando a cada agente…",
    reportesV2Ia: "Construyendo reportes…",
};

function cargandoBloqueV2(texto) {
    return `<div class="v2-loading"><span class="v2-spinner" aria-hidden="true"></span><strong>${escapeHtml(texto)}</strong>${skeletonV2(3)}</div>`;
}

function pintarCargandoV2() {
    const primera = !reporteriaActualIa;
    const estado = document.getElementById("estadoDatosResumenIa");
    if (estado) {
        estado.textContent = primera ? "Cargando datos…" : "Actualizando…";
        estado.classList.add("is-loading");
    }
    if (!primera) return;
    const alerta = document.getElementById("alertaEjecutivaIa");
    if (alerta) alerta.innerHTML = `<div><strong>Estamos preparando tu resumen</strong><span>Calculando notas, brechas y agentes del periodo. Suele tardar unos segundos.</span></div><span class="v2-spinner" aria-hidden="true"></span>`;
    Object.entries(CONTENEDORES_CARGA_V2).forEach(([id, texto]) => {
        const el = document.getElementById(id);
        if (!el) return;
        el.innerHTML = texto === "kpis"
            ? Array.from({ length: 5 }, () => `<article class="v2-kpi v2-kpi-loading">${skeletonV2(3)}</article>`).join("")
            : cargandoBloqueV2(texto);
    });
}

function pintarErrorCargaV2(mensaje) {
    const estado = document.getElementById("estadoDatosResumenIa");
    if (estado) { estado.textContent = "No se pudo actualizar"; estado.classList.remove("is-loading"); estado.classList.add("is-error"); }
    if (reporteriaActualIa) {
        mostrarMensajeIa(`${mensaje} Se muestran los últimos datos cargados.`, "error");
        return;
    }
    const alerta = document.getElementById("alertaEjecutivaIa");
    if (alerta) alerta.innerHTML = `<div><strong>No pudimos cargar los reportes</strong><span>${escapeHtml(mensaje)}</span></div><button class="btn-light btn-small" type="button" onclick="cargarReporteriaIa()">Reintentar</button>`;
    Object.keys(CONTENEDORES_CARGA_V2).forEach(id => {
        const el = document.getElementById(id);
        if (el) el.innerHTML = vacioV2("Sin datos por ahora", "La consulta no respondió. Usa Reintentar.");
    });
}

// Reemplaza a la de ia_feedback.js: misma consulta, con estados de carga y sin
// disparar dos consultas iguales cuando se cambia de pestaña rápido.
async function cargarReporteriaIa() {
    if (cargaReporteriaV2) return cargaReporteriaV2;
    pintarCargandoV2();
    cargaReporteriaV2 = (async () => {
        try {
            const params = new URLSearchParams({
                limit: "300",
                perfil: tipoUsuarioIa(),
                supervisor: localStorage.getItem("agente") || localStorage.getItem("dni") || "",
                fuente: fuenteReporteriaV2(),
            });
            const response = await fetchIa(`${IA_FEEDBACK_BASE}/reporteria?${params.toString()}`, {}, 45000);
            const data = await leerJsonSeguro(response);
            if (!response.ok) throw new Error(data.detail || "No se pudo cargar la reportería.");
            renderReporteriaIa(data);
            const estado = document.getElementById("estadoDatosResumenIa");
            estado?.classList.remove("is-loading", "is-error");
            if (estado && data.fuente === "SQL") {
                const sinDetalle = Number(data.llamadas_sin_criterios || 0);
                estado.textContent += ` · fuente: tablas${data.tiempos ? ` (${data.tiempos.total_s} s)` : ""}${sinDetalle ? ` · ${sinDetalle} sin detalle por criterio` : ""}`;
            }
        } catch (error) {
            const msg = error.message || "Error cargando reportería.";
            pintarErrorCargaV2(msg);
        } finally {
            cargaReporteriaV2 = null;
        }
    })();
    return cargaReporteriaV2;
}

/* ------------------------------------------------ Resumen: dimensiones */

function pintarDimensionesCopcResumenIa(_data, detalle) {
    const el = document.getElementById("dimensionCopcResumenIa");
    if (!el) return;
    const card = el.closest(".dimension-card");
    card?.querySelector("h4") && (card.querySelector("h4").textContent = "Desempeño por bloque de la pauta");
    setText("subtituloDimensionCopcIa", "Puntos obtenidos sobre puntos posibles, solo con criterios medidos");
    const bloques = porBloqueV2(detalle).filter(b => b.den > 0 || b.sinMedir.length);
    if (!bloques.length) {
        el.innerHTML = estadoVacioReporteIa(detalle);
        return;
    }
    el.classList.add("v2-dimension-grid");
    el.innerHTML = bloques.map(b => {
        const clase = claseNotaV2(b.pct);
        const brecha = b.pct === null ? null : b.pct - META_CALIDAD_V2;
        return `
            <article class="v2-dim ${clase}">
                <div class="v2-dim-head"><span title="${escapeHtml(b.nombre)}">${escapeHtml(b.codigo || b.nombre)}</span><strong>${pctV2(b.pct)}</strong></div>
                <p>${escapeHtml(b.nombre)}</p>
                ${barraV2(b.pct)}
                <small>${b.pct === null ? "Ningún criterio medido" : `${brecha >= 0 ? "+" : ""}${brecha.toFixed(0)} pp vs meta · ${formatoNumero(b.llamadas)} llamadas`}</small>
                ${b.masDebil && b.masDebil.pct < 100 ? `<small class="v2-dim-weak">Más débil: <b>${escapeHtml(b.masDebil.nombre)}</b> ${pctV2(b.masDebil.pct)} (${b.masDebil.cumple}/${b.masDebil.medidas})</small>` : ""}
                ${b.sinMedir.length ? `<small class="v2-dim-na">No se mide: ${escapeHtml(b.sinMedir.join(", "))}</small>` : ""}
            </article>`;
    }).join("");
}

/* --------------------------------------- Resumen: prioridad de intervención */

function pintarAgentesPriorizadosResumenIa(detalle) {
    const el = document.getElementById("agentesPriorizadosResumenIa");
    if (!el) return;
    const agentes = modeloAgentesV2(detalle).filter(a => a.reincidentes.length || a.bajoMeta || a.criticos).slice(0, 5);
    if (!agentes.length) {
        el.innerHTML = vacioV2("Ningún agente requiere intervención", "Nadie está bajo la meta ni repite brechas en el periodo filtrado.");
        return;
    }
    el.innerHTML = `<div class="v2-agent-mini-list">${agentes.map(a => filaAgenteMiniV2(a)).join("")}</div>`;
}

function filaAgenteMiniV2(a) {
    const motivo = a.reincidentes.length
        ? `Repite: ${escapeHtml(a.reincidentes[0].nombre)} (${a.reincidentes[0].fallas}/${a.reincidentes[0].medidas})`
        : a.criticos ? `${a.criticos} evaluación(es) con error crítico` : "Promedio bajo la meta";
    return `
        <article class="v2-agent-mini">
            <span class="v2-avatar">${escapeHtml(inicialesAgenteIa(a.agente))}</span>
            <div><strong title="${escapeHtml(a.agente)}">${escapeHtml(nombreAgenteCortoIa(a.agente))}</strong><small>${motivo}</small></div>
            <div class="v2-agent-mini-score ${claseNotaV2(a.promedio)}"><b>${pctV2(a.promedio, 1)}</b><small>${a.evaluables} eval.</small></div>
            <button class="btn-light btn-small" type="button" onclick="verAgenteEnPlanesV2(${JSON.stringify(a.agente).replace(/"/g, "&quot;")})">Ver</button>
        </article>`;
}

/* ------------------------------------------------------------ Evaluaciones */

const evalV2 = { filtro: "todas", busqueda: "", orden: "recientes", pagina: 1, porPagina: 15 };

const FILTROS_EVAL_V2 = [
    ["todas", "Todas", () => true],
    ["por_revisar", "Por revisar", r => !esEvaluacionValidadaIa(r)],
    ["sin_agente", "Sin agente", r => !agenteV2(r)],
    ["critico", "Con error crítico", tieneErrorCriticoV2],
    ["ia_revision", "La IA pide revisión", r => Boolean(r.requiere_revision_humana)],
    ["no_evaluable", "No evaluables", r => notaV2(r) === null],
    ["calibradas", "Calibradas por Calidad", r => String(r.origen_score || "").toUpperCase() === "CALIBRACION"],
];

function pintarBandejaEvaluacionesIa(items) {
    const el = document.getElementById("evaluacionesV2Ia");
    if (!el) return;
    const base = items || [];
    const conteos = Object.fromEntries(FILTROS_EVAL_V2.map(([k, , fn]) => [k, base.filter(fn).length]));
    const filtroFn = (FILTROS_EVAL_V2.find(f => f[0] === evalV2.filtro) || FILTROS_EVAL_V2[0])[2];
    const q = evalV2.busqueda.trim().toLowerCase();
    let rows = base.filter(filtroFn).filter(r => !q || [r.id_feedback, r.agente, r.cartera, r.archivo_nombre, r.tipo_llamada].some(v => String(v || "").toLowerCase().includes(q)));
    const nota = r => notaV2(r);
    if (evalV2.orden === "menor") rows.sort((a, b) => (nota(a) ?? 999) - (nota(b) ?? 999));
    else if (evalV2.orden === "mayor") rows.sort((a, b) => (nota(b) ?? -1) - (nota(a) ?? -1));
    else if (evalV2.orden === "antiguas") rows.sort((a, b) => String(fechaV2(a)).localeCompare(String(fechaV2(b))));
    else rows.sort((a, b) => String(fechaV2(b)).localeCompare(String(fechaV2(a))));

    const paginas = Math.max(1, Math.ceil(rows.length / evalV2.porPagina));
    evalV2.pagina = Math.min(evalV2.pagina, paginas);
    const pagina = rows.slice((evalV2.pagina - 1) * evalV2.porPagina, evalV2.pagina * evalV2.porPagina);
    const notas = base.map(nota).filter(n => n !== null);
    const prom = promedioV2(notas);
    const bajoMeta = notas.filter(n => n < META_CALIDAD_V2).length;

    el.innerHTML = `
        <div class="v2-kpi-row">
            ${kpiV2("Evaluaciones", formatoNumero(base.length), `${formatoNumero(notas.length)} con nota · ${formatoNumero(conteos.no_evaluable)} no evaluables`)}
            ${kpiV2("Nota promedio", pctV2(prom, 1), `Meta ${META_CALIDAD_V2}% · ${formatoNumero(bajoMeta)} bajo la meta`, claseNotaV2(prom))}
            ${kpiV2("Por revisar", formatoNumero(conteos.por_revisar), "Sin cierre del supervisor", conteos.por_revisar ? "warn" : "ok")}
            ${kpiV2("Sin agente", formatoNumero(conteos.sin_agente), "No cuentan para ningún agente", conteos.sin_agente ? "risk" : "ok")}
            ${kpiV2("Con error crítico", formatoNumero(conteos.critico), base.length ? `${((conteos.critico / base.length) * 100).toFixed(0)}% del total` : "", conteos.critico ? "risk" : "ok")}
        </div>
        <div class="v2-toolbar">
            <div class="v2-segmented">${FILTROS_EVAL_V2.map(([k, label]) => `<button type="button" class="${evalV2.filtro === k ? "active" : ""}" onclick="filtrarEvaluacionesV2('${k}')">${escapeHtml(label)} <em>${formatoNumero(conteos[k])}</em></button>`).join("")}</div>
            <div class="v2-toolbar-right">
                <input type="search" placeholder="Buscar agente, cartera, #id…" value="${escapeHtml(evalV2.busqueda)}" oninput="buscarEvaluacionesV2(this.value)">
                <select onchange="ordenarEvaluacionesV2(this.value)">
                    ${[["recientes", "Más recientes"], ["antiguas", "Más antiguas"], ["menor", "Menor nota"], ["mayor", "Mayor nota"]].map(([v, t]) => `<option value="${v}" ${evalV2.orden === v ? "selected" : ""}>${t}</option>`).join("")}
                </select>
            </div>
        </div>
        <div class="v2-eval-list">
            ${pagina.length ? pagina.map(filaEvaluacionV2).join("") : vacioV2("No hay evaluaciones con este filtro", "Cambia el filtro o amplía el periodo.")}
        </div>
        <div class="v2-pager">
            <span>${rows.length ? `${(evalV2.pagina - 1) * evalV2.porPagina + 1}–${Math.min(evalV2.pagina * evalV2.porPagina, rows.length)} de ${formatoNumero(rows.length)}` : "0 resultados"}</span>
            <div>
                <button class="btn-light btn-small" type="button" ${evalV2.pagina <= 1 ? "disabled" : ""} onclick="paginarEvaluacionesV2(-1)">Anterior</button>
                <span>Página ${evalV2.pagina} de ${paginas}</span>
                <button class="btn-light btn-small" type="button" ${evalV2.pagina >= paginas ? "disabled" : ""} onclick="paginarEvaluacionesV2(1)">Siguiente</button>
            </div>
        </div>`;
}

function filaEvaluacionV2(r) {
    const n = notaV2(r);
    const ag = agenteV2(r);
    const its = itemsV2(r);
    const brechas = its.filter(i => i.brecha);
    const medidos = its.filter(i => i.medido).length;
    const validada = esEvaluacionValidadaIa(r);
    const calibrada = String(r.origen_score || "").toUpperCase() === "CALIBRACION";
    const id = Number(r.id_feedback);
    const tagsBrecha = brechas.slice(0, 3).map(b => chipV2(b.nombre, "risk")).join("") + (brechas.length > 3 ? chipV2(`+${brechas.length - 3}`, "muted") : "");
    return `
        <article class="v2-eval ${validada ? "" : "pendiente"}">
            <div class="v2-eval-score ${claseNotaV2(n)}">
                <strong>${n === null ? "N/E" : formatoPeso(n)}</strong>
                <small>${n === null ? "No evaluable" : calibrada ? "Calibrada" : "Nota IA"}</small>
            </div>
            <div class="v2-eval-main">
                <div class="v2-eval-title">
                    <strong>${ag ? escapeHtml(nombreAgenteLimpioIa(ag)) : `<span class="v2-noagent">Sin agente</span>`}</strong>
                    <span>#${id} · ${escapeHtml(fechaCortaV2(fechaV2(r)))} · ${escapeHtml(r.cartera || "Sin cartera")}${r.tipo_llamada ? ` · ${escapeHtml(r.tipo_llamada)}` : ""}</span>
                </div>
                <div class="v2-eval-tags">
                    ${tieneErrorCriticoV2(r) ? chipV2("Error crítico", "risk strong") : ""}
                    ${brechas.length ? tagsBrecha : medidos ? chipV2("Sin brechas", "ok") : ""}
                    ${r.requiere_revision_humana ? chipV2("La IA pide revisión", "warn") : ""}
                </div>
            </div>
            <div class="v2-eval-state">
                ${validada ? chipV2("Revisada", "ok") : chipV2("Por revisar", "warn")}
                <small>${brechas.length} brecha(s) en ${medidos} medidos</small>
            </div>
            <button class="${validada ? "btn-light" : "btn-primary"} btn-small" type="button" onclick="verAnalisisIa(${id})">${validada ? "Ver" : "Revisar"}</button>
        </article>`;
}

function filtrarEvaluacionesV2(k) { evalV2.filtro = k; evalV2.pagina = 1; pintarBandejaEvaluacionesIa(detalleReporteIa); }
function ordenarEvaluacionesV2(v) { evalV2.orden = v; evalV2.pagina = 1; pintarBandejaEvaluacionesIa(detalleReporteIa); }
function paginarEvaluacionesV2(d) { evalV2.pagina += d; pintarBandejaEvaluacionesIa(detalleReporteIa); }
let buscarEvalTimerV2 = null;
function buscarEvaluacionesV2(v) {
    clearTimeout(buscarEvalTimerV2);
    buscarEvalTimerV2 = setTimeout(() => {
        evalV2.busqueda = v; evalV2.pagina = 1;
        pintarBandejaEvaluacionesIa(detalleReporteIa);
        const input = document.querySelector("#evaluacionesV2Ia .v2-toolbar input");
        if (input) { input.focus(); input.setSelectionRange(v.length, v.length); }
    }, 250);
}

function verEvaluacionesDeAgenteV2(agente) {
    evalV2.busqueda = nombreAgenteLimpioIa(agente);
    evalV2.filtro = "todas";
    evalV2.pagina = 1;
    mostrarVistaEvaluacionesIa();
}

/* -------------------------------------------------------- Planes de mejora */

let agenteAbiertoV2 = null;

function verAgenteEnPlanesV2(agente) {
    agenteAbiertoV2 = agente;
    mostrarVistaCoachingIa();
}

function pintarVistaCoachingIa(detalle) {
    const el = document.getElementById("planesV2Ia");
    if (!el) return;
    if (!planesV2.cargado && !planesV2.cargando) cargarPlanesV2();
    const agentes = modeloAgentesV2(detalle);
    const sinAgente = detalle.filter(r => !agenteV2(r)).length;
    const candidatos = agentes.filter(a => a.reincidentes.length);
    const bajoMeta = agentes.filter(a => a.bajoMeta);
    const conteoCriterio = new Map();
    candidatos.forEach(a => a.reincidentes.forEach(c => conteoCriterio.set(c.nombre, (conteoCriterio.get(c.nombre) || 0) + 1)));
    const topCriterio = [...conteoCriterio.entries()].sort((x, y) => y[1] - x[1])[0];

    el.innerHTML = `
        <div class="v2-kpi-row">
            ${kpiV2("Agentes evaluados", formatoNumero(agentes.length), `${formatoNumero(detalle.length - sinAgente)} evaluaciones atribuidas`)}
            ${kpiV2("Bajo la meta", formatoNumero(bajoMeta.length), `Promedio < ${META_CALIDAD_V2}%`, bajoMeta.length ? "warn" : "ok")}
            ${kpiV2("Candidatos a plan", formatoNumero(candidatos.length), `Fallan un criterio ${REGLA_PLAN_V2.fallas}+ veces en sus últimas ${REGLA_PLAN_V2.ultimas} mediciones (mín. ${REGLA_PLAN_V2.minimo})`, candidatos.length ? "risk" : "ok")}
            ${kpiV2("Brecha que más se repite", topCriterio ? topCriterio[0] : "—", topCriterio ? `${topCriterio[1]} agente(s)` : "Ningún agente repite brechas")}
        </div>
        ${seccionPlanesActivosV2()}
        <div class="v2-note">
            <strong>Cómo se sugiere un plan.</strong>
            Candidato: falla el mismo criterio en ${REGLA_PLAN_V2.fallas} o más de sus últimas ${REGLA_PLAN_V2.ultimas} mediciones, con al menos ${REGLA_PLAN_V2.minimo} mediciones.
            Meta del plan: ${REGLA_PLAN_V2.meta}% de cumplimiento en las ${REGLA_PLAN_V2.ultimas} mediciones siguientes; si en ${REGLA_PLAN_V2.dias} días no se completan, vence.
            Las tarjetas usan las evaluaciones del periodo filtrado; al abrir el plan, la línea base se toma de todo el historial del agente.
            ${sinAgente ? `<br><b>${formatoNumero(sinAgente)} evaluación(es) sin agente</b> no se atribuyen a nadie y no aparecen aquí.` : ""}
        </div>
        <div class="v2-agent-grid">
            ${agentes.length ? agentes.map(tarjetaAgenteV2).join("") : vacioV2("No hay evaluaciones con agente asignado", "Asigna el agente desde la ficha de cada evaluación para verlas aquí.")}
        </div>`;

    if (agenteAbiertoV2) {
        const card = [...el.querySelectorAll(".v2-agent-card")].find(c => c.dataset.agente === agenteAbiertoV2);
        card?.classList.add("focus");
        card?.scrollIntoView({ behavior: "smooth", block: "center" });
        agenteAbiertoV2 = null;
    }
}

function tarjetaAgenteV2(a) {
    const estado = a.reincidentes.length ? ["Candidato a plan", "risk"] : a.bajoMeta ? ["Bajo la meta", "warn"] : a.evaluables ? ["En meta", "ok"] : ["Sin nota", "muted"];
    const agenteJs = JSON.stringify(a.agente).replace(/"/g, "&quot;");
    return `
        <article class="v2-agent-card ${estado[1]}" data-agente="${escapeHtml(a.agente)}">
            <header>
                <span class="v2-avatar">${escapeHtml(inicialesAgenteIa(a.agente))}</span>
                <div>
                    <strong title="${escapeHtml(a.agente)}">${escapeHtml(nombreAgenteLimpioIa(a.agente))}</strong>
                    <small title="${escapeHtml(a.carteras.join(", "))}">${escapeHtml(codigoAgenteIa(a.agente) || "")}${a.carteras.length ? ` · ${escapeHtml(carterasCortoV2(a.carteras))}` : ""}</small>
                </div>
                ${chipV2(estado[0], estado[1])}
            </header>
            <div class="v2-agent-metrics">
                <div><span>Promedio</span><strong class="${claseNotaV2(a.promedio)}">${pctV2(a.promedio, 1)}</strong><small>${a.evaluables} de ${a.total} con nota</small></div>
                <div><span>Tendencia</span>${tendenciaV2(a.tendencia)}</div>
                <div><span>Error crítico</span><strong>${formatoNumero(a.criticos)}</strong><small>evaluación(es)</small></div>
                <div><span>Últimas notas</span>${sparkV2(a.notas) || "<small>—</small>"}</div>
            </div>
            ${barraV2(a.promedio)}
            <div class="v2-agent-gaps">
                ${a.reincidentes.length
                    ? `<span>Brechas que repite</span>${a.reincidentes.slice(0, 4).map(c => filaBrechaPlanV2(a.agente, c)).join("")}`
                    : `<span class="v2-muted">No repite ninguna brecha en sus últimas mediciones.</span>`}
            </div>
            <footer>
                <button class="btn-light btn-small" type="button" onclick="verEvaluacionesDeAgenteV2(${agenteJs})">Ver sus ${a.total} evaluación(es)</button>
                ${a.ultima ? `<button class="btn-light btn-small" type="button" onclick="verAnalisisIa(${Number(a.ultima.id_feedback)})">Abrir la última</button>` : ""}
                ${a.porRevisar ? `<small>${a.porRevisar} por revisar</small>` : ""}
            </footer>
        </article>`;
}

/* -------------------------------------------------------------- Calibración */

function pintarVistaCalibracionTabIa(_detalle) {
    const tab = document.getElementById("tabCalibracionIa");
    if (tab && !tab.classList.contains("oculto")) cargarVistaCalibracionGlobalIa();
}

async function cargarVistaCalibracionGlobalIa() {
    const el = document.getElementById("calibracionV2Ia");
    if (!el) return;
    if (!el.innerHTML.trim()) el.innerHTML = skeletonV2(5);
    const [cola, precision] = await Promise.all([
        fetchIa(`${CALIBRACION_BASE_IA}/cola`, {}, 15000).then(leerJsonSeguro).catch(() => null),
        fetchIa(`${CALIBRACION_BASE_IA}/reporte/precision?perfil=${encodeURIComponent(tipoUsuarioIa())}`, {}, 15000)
            .then(async r => (r.ok ? leerJsonSeguro(r) : { sin_acceso: r.status === 403 }))
            .catch(() => null),
    ]);
    await cargarPermisosCalibracionIa();

    const pendientes = Array.isArray(cola?.data) ? cola.data : [];
    const criteriosEnCola = pendientes.reduce((t, i) => t + Number(i.en_revision || 0), 0);
    const detallePrec = Array.isArray(precision?.detalle) ? precision.detalle : [];
    const revisados = Number(precision?.criterios_revisados || 0);
    const suma = campo => detallePrec.reduce((t, i) => t + Number(i[campo] || 0), 0);
    const pRes = revisados ? (suma("acierto_resultado") / revisados) * 100 : null;
    const pEvi = revisados ? (suma("acierto_evidencia") / revisados) * 100 : null;
    const avisoMuestra = revisados && !precision?.muestra_suficiente ? `<em class="v2-warn-text">Base chica: menos de 30 criterios revisados</em>` : "";

    // Impacto de la calibración en la nota, con las llamadas del periodo filtrado.
    const calibradas = (detalleReporteIa || []).filter(r => String(r.origen_score || "").toUpperCase() === "CALIBRACION" && r.score_ia != null && r.score_calibrado != null);
    const deltas = calibradas.map(r => Number(r.score_calibrado) - Number(r.score_ia));
    const deltaProm = promedioV2(deltas);
    const hoy = Date.now();
    const diasEspera = r => (r.enviado_desde ? Math.floor((hoy - new Date(r.enviado_desde).getTime()) / 86400000) : null);
    const atrasadas = pendientes.filter(r => (diasEspera(r) ?? 0) >= 2).length;

    el.innerHTML = `
        <div class="v2-flow">
            <div class="v2-flow-step"><span>1</span><div><strong>Supervisor corrige</strong><small>Marca criterios mal evaluados y los envía</small></div></div>
            <div class="v2-flow-step ${pendientes.length ? "active" : ""}"><span>2</span><div><strong>${formatoNumero(pendientes.length)} en Calidad</strong><small>${formatoNumero(criteriosEnCola)} criterio(s) esperando${atrasadas ? ` · <b>${atrasadas} con 2+ días</b>` : ""}</small></div></div>
            <div class="v2-flow-step"><span>3</span><div><strong>${formatoNumero(calibradas.length)} publicadas</strong><small>En el periodo filtrado; su nota ya es la calibrada</small></div></div>
        </div>
        <div class="v2-kpi-row">
            ${kpiV2("Esperando a Calidad", formatoNumero(pendientes.length), `${formatoNumero(criteriosEnCola)} criterio(s)`, pendientes.length ? "warn" : "ok")}
            ${kpiV2("Cambio de nota al calibrar", deltaProm === null ? "—" : `${deltaProm > 0 ? "+" : ""}${deltaProm.toFixed(1)} pts`, calibradas.length ? `Promedio sobre ${calibradas.length} llamada(s)` : "Sin calibraciones publicadas en el periodo")}
            ${kpiV2("La IA acierta el resultado", pctV2(pRes, 1), precision?.sin_acceso ? "Tu perfil no ve la precisión" : `${formatoNumero(revisados)} criterio(s) revisados ${avisoMuestra}`)}
            ${kpiV2("Acierta y cita bien la evidencia", pctV2(pEvi, 1), "Resultado correcto con evidencia válida")}
        </div>
        <section class="v2-panel">
            <header><h4>Cola de Calidad</h4><small>Las que más esperan, primero</small></header>
            ${pendientes.length ? `
            <div class="v2-table-wrap"><table class="v2-table">
                <thead><tr><th>Evaluación</th><th>Agente</th><th>Cartera</th><th>Criterios</th><th>Cambian nota</th><th>Propuesto por</th><th>Espera</th><th>Nota IA</th><th></th></tr></thead>
                <tbody>${pendientes.map(r => {
                    const d = diasEspera(r);
                    return `<tr>
                        <td><b>#${escapeHtml(r.id_feedback)}</b></td>
                        <td>${agenteV2(r) ? escapeHtml(nombreAgenteLimpioIa(r.agente)) : `<span class="v2-noagent">Sin agente</span>`}</td>
                        <td>${escapeHtml(r.cartera || "-")}</td>
                        <td>${formatoNumero(r.en_revision)}</td>
                        <td>${formatoNumero(r.correcciones)}</td>
                        <td>${escapeHtml(r.propuesto_por || "-")}</td>
                        <td>${d === null ? "-" : chipV2(d === 0 ? "hoy" : `${d} día(s)`, d >= 2 ? "risk" : d >= 1 ? "warn" : "ok")}</td>
                        <td>${r.score_final == null ? "N/E" : formatoPeso(r.score_final)}</td>
                        <td><button class="${permisosCalibracionIa.puede_publicar ? "btn-primary" : "btn-light"} btn-small" type="button" onclick="verAnalisisIa(${Number(r.id_feedback)}, 'calibracion')">${permisosCalibracionIa.puede_publicar ? "Revisar" : "Ver"}</button></td>
                    </tr>`;
                }).join("")}</tbody>
            </table></div>` : vacioV2("No hay calibraciones esperando a Calidad", "Aparecen aquí cuando un supervisor envía correcciones desde la ficha.")}
        </section>
        <div class="v2-two-col">
            <section class="v2-panel">
                <header><h4>¿En qué criterios se equivoca la IA?</h4><small>Solo criterios revisados por una persona</small></header>
                ${precision?.sin_acceso ? vacioV2("Tu perfil no tiene acceso a la precisión", "Visible para Calidad y jefaturas.")
                    : !detallePrec.length ? vacioV2("Todavía no hay criterios revisados", "Lo que nadie revisó no cuenta como acierto ni como error.")
                    : `<div class="v2-bars">${agruparPrecisionV2(detallePrec).map(p => `
                        <div class="v2-bar-row">
                            <div><b>${escapeHtml(p.nombre)}</b><small>${p.revisados} revisado(s)${p.revisados < BASE_MINIMA_V2 ? " · base chica" : ""}</small></div>
                            ${barraV2(p.pct, p.pct >= 90 ? "ok" : p.pct >= 75 ? "warn" : "risk")}
                            <strong>${pctV2(p.pct)}</strong>
                        </div>`).join("")}</div>`}
            </section>
            <section class="v2-panel">
                <header><h4>Por qué se corrige</h4><small>Motivos registrados por supervisores y Calidad</small></header>
                ${(precision?.motivos || []).length
                    ? `<div class="v2-bars">${precision.motivos.slice(0, 6).map(m => {
                        const max = Math.max(...precision.motivos.map(x => Number(x.veces || 0)), 1);
                        return `<div class="v2-bar-row"><div><b>${escapeHtml(m.nombre)}</b><small>${escapeHtml(m.categoria || "")}</small></div>${barraV2((Number(m.veces) / max) * 100, "info", false)}<strong>${formatoNumero(m.veces)}</strong></div>`;
                    }).join("")}</div>`
                    : vacioV2("Sin motivos registrados todavía")}
                ${calibradas.length ? `<header class="v2-sub"><h4>Cómo cambió la nota</h4></header>
                    <div class="v2-delta-list">${calibradas.slice(0, 8).map(r => {
                        const d = Number(r.score_calibrado) - Number(r.score_ia);
                        return `<button type="button" onclick="verAnalisisIa(${Number(r.id_feedback)}, 'calibracion')"><b>#${r.id_feedback}</b> ${formatoPeso(r.score_ia)} → ${formatoPeso(r.score_calibrado)} <em class="${d >= 0 ? "up" : "down"}">${d > 0 ? "+" : ""}${d.toFixed(1)}</em></button>`;
                    }).join("")}</div>` : ""}
            </section>
        </div>`;
}

// La precisión viene por criterio y cartera: se agrega por criterio para leerla.
function agruparPrecisionV2(detalle) {
    const mapa = new Map();
    detalle.forEach(i => {
        const k = i.codigo_criterio;
        const a = mapa.get(k) || { nombre: `${i.codigo_criterio} ${i.nombre_criterio || ""}`.trim(), revisados: 0, aciertos: 0 };
        a.revisados += Number(i.revisados || 0);
        a.aciertos += Number(i.acierto_resultado || 0);
        mapa.set(k, a);
    });
    return [...mapa.values()].map(a => ({ ...a, pct: a.revisados ? (a.aciertos / a.revisados) * 100 : null })).sort((x, y) => (x.pct ?? 0) - (y.pct ?? 0));
}

/* ----------------------------------------------------------------- Reportes */

const DIMENSIONES_V2 = {
    cartera: { label: "Cartera", plural: "carteras", fn: r => r.cartera || "Sin cartera" },
    agente: { label: "Agente", plural: "agentes", fn: r => agenteV2(r) || "Sin agente" },
    supervisor: { label: "Supervisor", plural: "supervisores", fn: r => String(r.supervisor || "").trim() || "Sin supervisor" },
    tipo: { label: "Tipo de llamada", plural: "tipos de llamada", fn: r => r.tipo_llamada || "Sin tipo" },
};
const repV2 = { dim: "cartera", todos: false };

function cambiarDimensionReporteV2(dim) {
    repV2.dim = dim;
    repV2.todos = false;
    pintarVistaReportesSgcIa(null, detalleReporteIa);
}

function verTodosGruposReporteV2() {
    repV2.todos = true;
    pintarVistaReportesSgcIa(null, detalleReporteIa);
}

function etiquetaGrupoV2(dim, valor) {
    return dim === "agente" || dim === "supervisor" ? nombreAgenteLimpioIa(valor) : valor;
}

function agruparV2(detalle, dim) {
    const fn = DIMENSIONES_V2[dim].fn;
    const mapa = new Map();
    detalle.forEach(r => {
        const k = fn(r);
        if (!mapa.has(k)) mapa.set(k, []);
        mapa.get(k).push(r);
    });
    return [...mapa.entries()].map(([clave, rows]) => {
        const ns = rows.map(notaV2).filter(n => n !== null);
        return { clave, rows, notas: ns, promedio: promedioV2(ns) };
    });
}

// Dónde falla más un grupo: sus criterios con más brechas y cuánto peor están
// que el total del periodo. La diferencia es lo que distingue "falla porque
// todos fallan ahí" de "falla más que el resto".
function focoGrupoV2(grupo, criteriosTotal) {
    const total = new Map(criteriosTotal.map(c => [c.clave, c]));
    const criterios = porCriterioV2(grupo.rows)
        .filter(c => c.medidas && c.brechas)
        .map(c => {
            const t = total.get(c.clave);
            const falla = (c.brechas / c.medidas) * 100;
            const fallaTotal = t && t.medidas ? (t.brechas / t.medidas) * 100 : null;
            return { ...c, falla, dif: fallaTotal === null ? null : falla - fallaTotal };
        })
        .sort((a, b) => b.falla - a.falla || b.brechas - a.brechas);
    const bloques = porBloqueV2(grupo.rows).filter(b => b.pct !== null).sort((a, b) => a.pct - b.pct);
    return { criterios, bloqueDebil: bloques[0] || null };
}

function tarjetaFocoV2(dim, g, criteriosTotal) {
    const foco = focoGrupoV2(g, criteriosTotal);
    const top = foco.criterios.slice(0, 3);
    const criticos = g.rows.filter(tieneErrorCriticoV2).length;
    const nombre = etiquetaGrupoV2(dim, g.clave);
    return `
        <article class="v2-foco ${claseNotaV2(g.promedio)}">
            <header>
                <div><strong title="${escapeHtml(g.clave)}">${escapeHtml(nombre)}</strong>
                <small>${g.rows.length} eval. · ${g.notas.length} con nota${criticos ? ` · ${criticos} con error crítico` : ""}</small></div>
                <b>${pctV2(g.promedio, 1)}</b>
            </header>
            ${barraV2(g.promedio)}
            ${top.length ? `<ol>${top.map(c => `
                <li>
                    <span><b>${escapeHtml(c.nombre)}</b><small>falla ${c.brechas} de ${c.medidas}${c.medidas < BASE_MINIMA_V2 ? " · base chica" : ""}</small></span>
                    <em>${c.falla.toFixed(0)}%</em>
                    ${c.dif === null ? "" : `<i class="${c.dif > 5 ? "peor" : c.dif < -5 ? "mejor" : "igual"}" title="Contra el % de falla de todo el periodo">${c.dif > 0 ? "+" : ""}${c.dif.toFixed(0)} pp vs total</i>`}
                </li>`).join("")}</ol>` : `<p class="v2-muted">Sin brechas en lo medido.</p>`}
            ${foco.bloqueDebil ? `<small class="v2-foco-bloque">Bloque más débil: <b>${escapeHtml(foco.bloqueDebil.codigo || foco.bloqueDebil.nombre)}</b> ${pctV2(foco.bloqueDebil.pct)}</small>` : ""}
            ${dim === "agente" && g.clave !== "Sin agente" ? `<button class="btn-light btn-small" type="button" onclick="verAgenteEnPlanesV2(${JSON.stringify(g.clave).replace(/"/g, "&quot;")})">Ver agente</button>` : ""}
        </article>`;
}

function pintarVistaReportesSgcIa(_data, detalle) {
    const el = document.getElementById("reportesV2Ia");
    if (!el) return;
    if (!detalle.length) {
        el.innerHTML = estadoVacioReporteIa(detalle);
        return;
    }
    const dim = repV2.dim;
    const D = DIMENSIONES_V2[dim];
    const notas = detalle.map(notaV2).filter(n => n !== null);
    const criteriosTotal = porCriterioV2(detalle);
    const filasCriterio = [...criteriosTotal].sort((a, b) => String(a.codigo).localeCompare(String(b.codigo), "es", { numeric: true }));
    const grupos = agruparV2(detalle, dim).sort((a, b) => (a.promedio ?? 999) - (b.promedio ?? 999));
    const gruposMapa = grupos.filter(g => g.notas.length || dim !== "agente");
    const porGrupo = new Map(gruposMapa.map(g => [g.clave, new Map(porCriterioV2(g.rows).map(x => [x.clave, x]))]));
    const celda = x => {
        if (!x || !x.medidas) return `<td class="v2-heat na" title="No se midió">—</td>`;
        const chica = x.medidas < BASE_MINIMA_V2;
        return `<td class="v2-heat ${claseNotaV2(x.pct)} ${chica ? "chica" : ""}" title="${x.cumple} de ${x.medidas} cumplen${chica ? " · base chica" : ""}">${x.pct.toFixed(0)}%<small>${x.cumple}/${x.medidas}</small></td>`;
    };
    const visibles = repV2.todos ? grupos : grupos.slice(0, 9);

    const agentes = modeloAgentesV2(detalle).filter(a => a.evaluables).sort((a, b) => (a.promedio ?? 0) - (b.promedio ?? 0));
    const semanas = new Map();
    detalle.forEach(r => {
        const k = claveSemanaClienteIa(fechaV2(r));
        const s = semanas.get(k) || { semana: k, total: 0, notas: [], criticos: 0 };
        s.total += 1;
        const n = notaV2(r);
        if (n !== null) s.notas.push(n);
        if (tieneErrorCriticoV2(r)) s.criticos += 1;
        semanas.set(k, s);
    });
    const filasSemana = [...semanas.values()].sort((a, b) => a.semana.localeCompare(b.semana));
    const pareto = criteriosTotal.filter(c => c.brechas).sort((a, b) => b.brechas - a.brechas);
    const totalBrechas = pareto.reduce((t, c) => t + c.brechas, 0);
    let acum = 0;

    el.innerHTML = `
        <div class="v2-kpi-row">
            ${kpiV2("Nota promedio", pctV2(promedioV2(notas), 1), `${formatoNumero(notas.length)} evaluaciones con nota de ${formatoNumero(detalle.length)}`, claseNotaV2(promedioV2(notas)))}
            ${kpiV2("En meta", notas.length ? pctV2((notas.filter(n => n >= META_CALIDAD_V2).length / notas.length) * 100) : "—", `Evaluaciones con ${META_CALIDAD_V2}% o más`)}
            ${kpiV2("Criterios medidos", formatoNumero(filasCriterio.filter(c => c.medidas).length), `${formatoNumero(filasCriterio.filter(c => !c.medidas).length)} no se pudieron medir en el periodo`)}
            ${kpiV2("Agentes con nota", formatoNumero(agentes.length), `${formatoNumero(agentes.filter(a => a.bajoMeta).length)} bajo la meta`)}
        </div>

        <div class="v2-dim-selector">
            <span>Analizar por</span>
            <div class="v2-segmented">${Object.entries(DIMENSIONES_V2).map(([k, d]) => `<button type="button" class="${dim === k ? "active" : ""}" onclick="cambiarDimensionReporteV2('${k}')">${escapeHtml(d.label)}</button>`).join("")}</div>
            <button class="btn-primary btn-small" type="button" onclick="exportarReporteIa()">Exportar a Excel</button>
        </div>

        <section class="v2-panel">
            <header><h4>¿Dónde falla más cada ${escapeHtml(D.label.toLowerCase())}?</h4><small>Sus 3 criterios con mayor % de falla. «vs total» compara con el % de falla de todo el periodo: en rojo, falla más que el resto.</small></header>
            <div class="v2-foco-grid">${visibles.map(g => tarjetaFocoV2(dim, g, criteriosTotal)).join("")}</div>
            ${!repV2.todos && grupos.length > visibles.length ? `<div class="v2-center"><button class="btn-light btn-small" type="button" onclick="verTodosGruposReporteV2()">Ver los ${grupos.length} ${escapeHtml(D.plural)}</button></div>` : ""}
        </section>

        <section class="v2-panel">
            <header><h4>Mapa de cumplimiento: criterio × ${escapeHtml(D.label.toLowerCase())}</h4><small>% de llamadas que cumplen sobre las llamadas donde el criterio se midió. Atenuado: menos de ${BASE_MINIMA_V2} medidas.</small></header>
            <div class="v2-table-wrap"><table class="v2-table v2-heatmap">
                <thead><tr><th>Criterio</th>${gruposMapa.map(g => `<th title="${escapeHtml(g.clave)}">${escapeHtml(etiquetaGrupoV2(dim, g.clave))}</th>`).join("")}<th>Total</th></tr></thead>
                <tbody>
                    <tr class="v2-heat-total"><td><b>Nota promedio</b></td>${gruposMapa.map(g => `<td class="v2-heat ${claseNotaV2(g.promedio)}">${pctV2(g.promedio, 1)}<small>${g.notas.length} eval.</small></td>`).join("")}<td class="v2-heat ${claseNotaV2(promedioV2(notas))}">${pctV2(promedioV2(notas), 1)}<small>${notas.length} eval.</small></td></tr>
                    ${filasCriterio.map(c => `<tr><td><b>${escapeHtml(c.codigo)}</b> ${escapeHtml(c.nombre)}</td>${gruposMapa.map(g => celda(porGrupo.get(g.clave).get(c.clave))).join("")}${celda(c)}</tr>`).join("")}
                </tbody>
            </table></div>
        </section>

        <div class="v2-two-col">
            <section class="v2-panel">
                <header><h4>Pareto de brechas</h4><small>No cumple o Parcial. No incluye lo que no se pudo medir.</small></header>
                ${pareto.length ? `<div class="v2-bars">${pareto.slice(0, 10).map(c => {
                    acum += c.brechas;
                    return `<div class="v2-bar-row"><div><b>${escapeHtml(c.nombre)}</b><small>falla en ${c.brechas} de ${c.medidas} medidas (${((c.brechas / c.medidas) * 100).toFixed(0)}%) · ${((acum / totalBrechas) * 100).toFixed(0)}% acumulado</small></div>${barraV2((c.brechas / pareto[0].brechas) * 100, "risk", false)}<strong>${c.brechas}</strong></div>`;
                }).join("")}</div>` : vacioV2("Sin brechas en el periodo")}
            </section>
            <section class="v2-panel">
                <header><h4>Evolución semanal</h4><small>Semana del mes según la fecha de la llamada. La marca es la meta (${META_CALIDAD_V2}%).</small></header>
                <div class="v2-bars">${filasSemana.map(s => {
                    const p = promedioV2(s.notas);
                    const enMeta = s.notas.length ? (s.notas.filter(n => n >= META_CALIDAD_V2).length / s.notas.length) * 100 : null;
                    const ne = s.total - s.notas.length;
                    return `<div class="v2-bar-row"><div><b>${escapeHtml(s.semana)}</b><small>${s.total} eval.${ne ? ` (${ne} N/E)` : ""} · ${pctV2(enMeta)} en meta · ${s.criticos} con error crítico</small></div>${barraV2(p)}<strong>${pctV2(p, 1)}</strong></div>`;
                }).join("")}</div>
            </section>
        </div>

        <section class="v2-panel">
            <header><h4>Ranking de agentes</h4><small>De menor a mayor nota. N = evaluaciones con nota.</small></header>
            <div class="v2-table-wrap"><table class="v2-table">
                <thead><tr><th>Agente</th><th>Cartera</th><th>N</th><th>Nota promedio</th><th>vs meta</th><th>Tendencia</th><th>Error crítico</th><th>Brecha que repite</th><th></th></tr></thead>
                <tbody>${agentes.map(a => `<tr>
                    <td><b>${escapeHtml(nombreAgenteLimpioIa(a.agente))}</b><small class="v2-block">${escapeHtml(codigoAgenteIa(a.agente))}</small></td>
                    <td title="${escapeHtml(a.carteras.join(", "))}">${escapeHtml(carterasCortoV2(a.carteras))}</td>
                    <td>${a.evaluables}${a.evaluables < BASE_MINIMA_V2 ? ` <small class="v2-muted">base chica</small>` : ""}</td>
                    <td><div class="v2-inline">${barraV2(a.promedio)}<b>${pctV2(a.promedio, 1)}</b></div></td>
                    <td class="${a.promedio >= META_CALIDAD_V2 ? "v2-pos" : "v2-neg"}">${a.promedio - META_CALIDAD_V2 >= 0 ? "+" : ""}${(a.promedio - META_CALIDAD_V2).toFixed(1)} pp</td>
                    <td>${tendenciaV2(a.tendencia)}</td>
                    <td>${a.criticos}</td>
                    <td>${a.reincidentes[0] ? `${escapeHtml(a.reincidentes[0].nombre)} <small>(${a.reincidentes[0].fallas}/${a.reincidentes[0].medidas})</small>` : "—"}</td>
                    <td><button class="btn-light btn-small" type="button" onclick="verAgenteEnPlanesV2(${JSON.stringify(a.agente).replace(/"/g, "&quot;")})">Ver</button></td>
                </tr>`).join("")}</tbody>
            </table></div>
        </section>`;
}

// "Ver Pareto completo" y "Reportes" ya no saltan al detalle legacy.
function mostrarVistaReportesIa() {
    activarVistaReporteriaIa({ view: "reportes" });
    setVistaActivaIa("reportes");
    cargarReporteriaIa();
}

function mostrarVistaCalibracionIa() {
    activarVistaReporteriaIa({ view: "calibracion" });
    setVistaActivaIa("calibracion");
    const el = document.getElementById("calibracionV2Ia");
    if (el && !el.innerHTML.trim()) el.innerHTML = skeletonV2(5);
    // Al terminar, renderReporteriaIa llama a pintarVistaCalibracionTabIa,
    // que carga la cola y la precision porque la pestana ya esta visible.
    cargarReporteriaIa();
}

/* ------------------------------------------------------ Exportar a Excel */

// El Excel se arma en el servidor con lo que esta pagina ya filtro y calculo:
// asi el archivo y la pantalla no pueden contar historias distintas.
function payloadExcelV2(detalle) {
    const si = v => (v ? "Sí" : "No");
    const supervisorDe = r => String(r.supervisor || "").trim() || "Sin supervisor";
    const evaluaciones = detalle.map(r => {
        const brechas = itemsV2(r).filter(i => i.brecha).map(i => i.nombre);
        const n = notaV2(r);
        return {
            id_feedback: Number(r.id_feedback),
            fecha: fechaV2(r),
            cartera: r.cartera || "Sin cartera",
            agente: agenteV2(r) || "Sin agente",
            supervisor: supervisorDe(r),
            tipo_llamada: r.tipo_llamada || "",
            nota: n,
            origen: n === null ? "No evaluable" : String(r.origen_score || "").toUpperCase() === "CALIBRACION" ? "Calibrada" : "IA",
            nota_ia: r.score_ia ?? null,
            evaluable: si(n !== null),
            error_critico: si(tieneErrorCriticoV2(r)),
            estado_revision: esEvaluacionValidadaIa(r) ? "Revisada" : "Por revisar",
            ia_pide_revision: si(r.requiere_revision_humana),
            brechas: brechas.join("; "),
            observacion: r.observacion_supervisor || "",
        };
    });
    const criterios = detalle.flatMap(r => itemsV2(r).map(i => ({
        id_feedback: Number(r.id_feedback),
        fecha: fechaV2(r),
        cartera: r.cartera || "Sin cartera",
        agente: agenteV2(r) || "Sin agente",
        supervisor: supervisorDe(r),
        tipo_llamada: r.tipo_llamada || "",
        bloque: i.bloque,
        bloque_nombre: i.bloqueNombre,
        codigo: claveCriterioV2(i),
        criterio: i.nombre,
        peso: i.peso,
        nota: i.medido ? i.nota : null,
        resultado: { CUMPLE: "Cumple", NO_CUMPLE: "No cumple", PARCIAL: "Parcial", NO_APLICA: "No aplica", NO_EVALUABLE: "No evaluable", REVISION: "Requiere revisión" }[i.estado],
        medido: i.medido ? 1 : 0,
        cumple: i.estado === "CUMPLE" ? 1 : 0,
        brecha: i.brecha ? 1 : 0,
    })));
    const criteriosTotal = porCriterioV2(detalle);
    const textoTop = (dim, g) => focoGrupoV2(g, criteriosTotal).criterios.slice(0, 3).map(c =>
        `${c.nombre} — falla ${c.falla.toFixed(0)}% (${c.brechas}/${c.medidas})${c.dif === null ? "" : `, ${c.dif > 0 ? "+" : ""}${c.dif.toFixed(0)} pp vs total`}`);
    const foco = Object.fromEntries(["cartera", "supervisor", "agente"].map(dim => [dim,
        agruparV2(detalle, dim).sort((a, b) => (a.promedio ?? 999) - (b.promedio ?? 999)).map(g => ({ grupo: g.clave, top: textoTop(dim, g) }))]));
    const agentes = modeloAgentesV2(detalle).map(a => ({
        agente: a.agente,
        tendencia: a.tendencia === null ? null : Math.round(a.tendencia * 10) / 10,
        brecha_repite: a.reincidentes[0] ? `${a.reincidentes[0].nombre} (${a.reincidentes[0].fallas}/${a.reincidentes[0].medidas})` : "",
    }));
    const catalogo = [...criteriosTotal].sort((a, b) => String(a.codigo).localeCompare(String(b.codigo), "es", { numeric: true }))
        .map(c => ({ codigo: c.clave, criterio: c.nombre }));
    const pareto = criteriosTotal.filter(c => c.brechas).sort((a, b) => b.brechas - a.brechas).map(c => ({ codigo: c.clave, criterio: c.nombre }));
    const filtros = [...document.querySelectorAll("#chipsFiltrosIa span")]
        .map(s => s.textContent.trim())
        .filter(t => t.includes(":"))
        .map(t => [t.slice(0, t.indexOf(":")).trim(), t.slice(t.indexOf(":") + 1).trim()]);
    return {
        generado_por: localStorage.getItem("agente") || "",
        periodo: document.getElementById("periodoHeaderIa")?.textContent?.trim() || "",
        filtros,
        meta: META_CALIDAD_V2,
        evaluaciones,
        criterios,
        foco,
        agentes,
        catalogo_criterios: catalogo,
        pareto,
    };
}

async function exportarReporteIa() {
    const rows = detalleReporteIa || [];
    if (!rows.length) {
        mostrarMensajeIa("No hay evaluaciones para exportar con los filtros seleccionados.", "error");
        return;
    }
    const botones = [...document.querySelectorAll("button[onclick^='exportarReporteIa']")];
    botones.forEach(b => { b.disabled = true; b.dataset.texto = b.textContent; b.textContent = "Generando Excel…"; });
    try {
        const response = await fetchIa(`${IA_FEEDBACK_BASE}/reporteria/exportar-excel`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payloadExcelV2(rows)),
        }, 90000);
        if (!response.ok) {
            const data = await leerJsonSeguro(response);
            throw new Error(data.detail || "No se pudo generar el Excel.");
        }
        const blob = await response.blob();
        const disp = response.headers.get("Content-Disposition") || "";
        const nombre = (disp.match(/filename="?([^"]+)"?/) || [])[1] || `reporte_calidad_${new Date().toISOString().slice(0, 10)}.xlsx`;
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = nombre;
        document.body.appendChild(a);
        a.click();
        a.remove();
        setTimeout(() => URL.revokeObjectURL(url), 2000);
        mostrarMensajeIa(`Excel generado con ${formatoNumero(rows.length)} evaluaciones del filtro actual.`, "ok");
    } catch (error) {
        mostrarMensajeIa(error.message || "No se pudo generar el Excel.", "error");
    } finally {
        botones.forEach(b => { b.disabled = false; b.textContent = b.dataset.texto || "Exportar"; });
    }
}


/* ------------------------------------ Resumen: brechas y alerta (modelo v2) */

function pintarParetoResumenIa(_data, detalle) {
    const el = document.getElementById("paretoResumenIa");
    if (!el) return;
    const pareto = porCriterioV2(detalle).filter(c => c.brechas).sort((a, b) => b.brechas - a.brechas);
    if (!pareto.length) {
        el.innerHTML = detalle.length ? vacioV2("Sin brechas en el periodo", "Ningún criterio medido salió No cumple.") : estadoVacioReporteIa(detalle);
        return;
    }
    const total = pareto.reduce((t, c) => t + c.brechas, 0);
    const max = pareto[0].brechas;
    let acum = 0;
    el.innerHTML = `<div class="v2-bars">${pareto.slice(0, 5).map(c => {
        acum += c.brechas;
        return `<div class="v2-bar-row"><div><b>${escapeHtml(c.nombre)}</b><small>falla en ${c.brechas} de ${c.medidas} medidas (${((c.brechas / c.medidas) * 100).toFixed(0)}%) · ${((acum / total) * 100).toFixed(0)}% acumulado</small></div>${barraV2((c.brechas / max) * 100, "risk", false)}<strong>${c.brechas}</strong></div>`;
    }).join("")}</div>`;
}

function pintarAlertaEjecutivaIa(_data, detalle) {
    const el = document.getElementById("alertaEjecutivaIa");
    if (!el) return;
    if (!detalle.length) {
        el.innerHTML = `<div><strong>Sin información disponible</strong><span>No hay evaluaciones para los filtros seleccionados.</span></div>`;
        return;
    }
    const top = porCriterioV2(detalle).filter(c => c.brechas && c.medidas >= BASE_MINIMA_V2)
        .sort((a, b) => b.brechas / b.medidas - a.brechas / a.medidas || b.brechas - a.brechas)[0];
    if (!top) {
        el.innerHTML = `<div><strong>Sin alerta prioritaria</strong><span>Ningún criterio con base suficiente presenta brechas en el periodo.</span></div>`;
        return;
    }
    const pct = (top.brechas / top.medidas) * 100;
    el.innerHTML = `
        <div>
            <strong>Atención requerida</strong>
            <span><b>${escapeHtml(top.nombre)}</b> falla en el ${pct.toFixed(0)}% de las llamadas donde se midió (${top.brechas} de ${top.medidas}). Es el criterio con mayor tasa de falla del periodo.</span>
        </div>
        <button class="link-button" type="button" onclick="mostrarVistaReportesIa()">Ver dónde falla cada cartera →</button>`;
}


/* ------------------------------------------ Planes de mejora persistidos */

const PLANES_BASE_V2 = IA_FEEDBACK_BASE.replace(/\/ia-feedback\/?$/, "/planes-mejora");
const planesV2 = { data: [], cargado: false, cargando: false, error: "" };

async function cargarPlanesV2() {
    planesV2.cargando = true;
    try {
        const response = await fetchIa(PLANES_BASE_V2, {}, 30000);
        const data = await leerJsonSeguro(response);
        if (!response.ok) throw new Error(data.detail || "No se pudieron cargar los planes.");
        planesV2.data = Array.isArray(data.data) ? data.data : [];
        planesV2.error = "";
    } catch (error) {
        planesV2.error = error.message || "No se pudieron cargar los planes.";
    } finally {
        planesV2.cargado = true;
        planesV2.cargando = false;
    }
    pintarVistaCoachingIa(detalleReporteIa || []);
}

function planActivoV2(agente, codigo) {
    return planesV2.data.find(p => p.estado === "ACTIVO" && p.agente === agente && p.codigo_criterio === codigo);
}

function filaBrechaPlanV2(agente, c) {
    const plan = planActivoV2(agente, c.codigo);
    const args = [agente, c.codigo, c.nombre].map(v => JSON.stringify(v).replace(/"/g, "&quot;")).join(",");
    return `<div class="v2-gap">
        <span><b>${escapeHtml(c.nombre)}</b><em>falla ${c.fallas} de ${c.medidas}</em></span>
        ${plan ? chipV2(`Plan #${plan.id_plan} activo`, "ok") : c.codigo ? `<button class="btn-light btn-small" type="button" onclick="abrirPlanV2(${args})">Abrir plan</button>` : ""}
    </div>`;
}

async function abrirPlanV2(agente, codigo, nombre) {
    const accion = window.prompt(
        `Plan de mejora para ${nombreAgenteLimpioIa(agente)}\nCriterio: ${nombre}\n\nAcción acordada con el agente (opcional):`, "");
    if (accion === null) return;
    try {
        const response = await fetchIa(PLANES_BASE_V2, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ agente, codigo_criterio: codigo, accion_acordada: accion, responsable: localStorage.getItem("agente") || "", usuario: localStorage.getItem("agente") || "" }),
        }, 30000);
        const data = await leerJsonSeguro(response);
        if (!response.ok) throw new Error(data.detail || "No se pudo abrir el plan.");
        mostrarMensajeIa(`Plan #${data.id_plan} abierto. ${data.motivo || ""}`, "ok");
        await cargarPlanesV2();
    } catch (error) {
        mostrarMensajeIa(error.message || "No se pudo abrir el plan.", "error");
    }
}

async function cerrarPlanV2(id, estado) {
    const etiqueta = { CUMPLIDO: "cumplido", NO_CUMPLIDO: "no cumplido", VENCIDO: "vencido", ANULADO: "anulado" }[estado] || estado;
    const comentario = window.prompt(`Cerrar el plan #${id} como ${etiqueta}.\n\nComentario de cierre (opcional):`, "");
    if (comentario === null) return;
    try {
        const response = await fetchIa(`${PLANES_BASE_V2}/${id}/cerrar`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ estado, comentario, usuario: localStorage.getItem("agente") || "" }),
        }, 30000);
        const data = await leerJsonSeguro(response);
        if (!response.ok) throw new Error(data.detail || "No se pudo cerrar el plan.");
        mostrarMensajeIa(`Plan #${id} cerrado como ${etiqueta}.`, "ok");
        await cargarPlanesV2();
    } catch (error) {
        mostrarMensajeIa(error.message || "No se pudo cerrar el plan.", "error");
    }
}

const ETIQUETA_SUGERIDO_V2 = {
    CUMPLIDO: ["Listo para cerrar: cumplido", "ok"],
    NO_CUMPLIDO: ["Listo para cerrar: no cumplido", "risk"],
    VENCIDO: ["Venció sin completar mediciones", "warn"],
    ACTIVO: ["En curso", "muted"],
};

function seccionPlanesActivosV2() {
    if (planesV2.cargando && !planesV2.cargado) return `<section class="v2-panel">${cargandoBloqueV2("Cargando planes de mejora…")}</section>`;
    if (planesV2.error) {
        return `<section class="v2-panel"><header><h4>Planes de mejora</h4></header>${vacioV2("No se pudieron cargar los planes", `${escapeHtml(planesV2.error)} Si es la primera vez, ejecuta tools/sql/crear_plan_mejora.sql.`)}</section>`;
    }
    const activos = planesV2.data.filter(p => p.estado === "ACTIVO");
    const cerrados = planesV2.data.filter(p => p.estado !== "ACTIVO");
    const porCerrar = activos.filter(p => p.avance && p.avance.estado_sugerido !== "ACTIVO").length;
    return `
        <section class="v2-panel">
            <header><h4>Planes activos · ${activos.length}${porCerrar ? ` <em class="v2-warn-text">(${porCerrar} listo(s) para cerrar)</em>` : ""}</h4>
            <small>El avance cuenta las mediciones del criterio en llamadas posteriores al inicio del plan.</small></header>
            ${activos.length ? `<div class="v2-plan-grid">${activos.map(tarjetaPlanV2).join("")}</div>`
                : vacioV2("No hay planes activos", "Ábrelos desde las brechas que repite cada agente, más abajo.")}
            ${cerrados.length ? `<details class="v2-plan-cerrados"><summary>Planes cerrados · ${cerrados.length}</summary>
                <div class="v2-table-wrap"><table class="v2-table"><thead><tr><th>#</th><th>Agente</th><th>Criterio</th><th>Línea base</th><th>Resultado</th><th>Estado</th><th>Cerrado</th><th>Comentario</th></tr></thead>
                <tbody>${cerrados.map(p => `<tr>
                    <td>${p.id_plan}</td><td>${escapeHtml(nombreAgenteLimpioIa(p.agente))}</td><td>${escapeHtml(p.nombre_criterio || p.codigo_criterio)}</td>
                    <td>${p.base_cumple}/${p.base_mediciones}</td>
                    <td>${p.cierre_mediciones == null ? "—" : `${p.cierre_cumple}/${p.cierre_mediciones}`}</td>
                    <td>${chipV2(p.estado.replace("_", " ").toLowerCase(), p.estado === "CUMPLIDO" ? "ok" : p.estado === "ANULADO" ? "muted" : "risk")}</td>
                    <td>${escapeHtml(fechaCortaV2(p.fecha_cierre))}</td><td>${escapeHtml(p.comentario_cierre || "")}</td>
                </tr>`).join("")}</tbody></table></div></details>` : ""}
        </section>`;
}

function tarjetaPlanV2(p) {
    const av = p.avance || { mediciones: 0, cumple: 0, pct: null, estado_sugerido: "ACTIVO", dias_restantes: 0, detalle: [] };
    const [texto, clase] = ETIQUETA_SUGERIDO_V2[av.estado_sugerido] || ETIQUETA_SUGERIDO_V2.ACTIVO;
    const basePct = p.base_mediciones ? (p.base_cumple / p.base_mediciones) * 100 : null;
    const puntos = Array.from({ length: p.mediciones_objetivo }, (_, i) => {
        const m = av.detalle[i];
        return m ? `<i class="${m.resultado === "CUMPLE" ? "ok" : "risk"}" title="#${m.id_feedback} · ${escapeHtml(m.resultado)}"></i>` : `<i class="pend" title="Pendiente"></i>`;
    }).join("");
    const cierre = av.estado_sugerido !== "ACTIVO"
        ? `<button class="btn-primary btn-small" type="button" onclick="cerrarPlanV2(${p.id_plan}, '${av.estado_sugerido}')">Cerrar como ${escapeHtml(av.estado_sugerido.replace("_", " ").toLowerCase())}</button>`
        : "";
    return `
        <article class="v2-plan ${clase}">
            <header>
                <div><strong>${escapeHtml(nombreAgenteLimpioIa(p.agente))}</strong><small>Plan #${p.id_plan} · ${escapeHtml(p.nombre_criterio || p.codigo_criterio)}</small></div>
                ${chipV2(texto, clase)}
            </header>
            <div class="v2-plan-nums">
                <div><span>Línea base</span><b>${pctV2(basePct)}</b><small>${p.base_cumple}/${p.base_mediciones} cumplen</small></div>
                <div><span>Avance</span><b>${pctV2(av.pct)}</b><small>${av.cumple}/${av.mediciones} de ${p.mediciones_objetivo} mediciones</small></div>
                <div><span>Meta</span><b>${formatoPeso(p.meta_pct)}%</b><small>${av.dias_restantes} día(s) restantes</small></div>
            </div>
            <div class="v2-plan-dots">${puntos}</div>
            ${p.accion_acordada ? `<p class="v2-plan-accion">«${escapeHtml(p.accion_acordada)}»</p>` : ""}
            <footer>
                ${cierre}
                <button class="btn-light btn-small" type="button" onclick="cerrarPlanV2(${p.id_plan}, 'ANULADO')">Anular</button>
                <small>Desde ${escapeHtml(fechaCortaV2(p.fecha_inicio))}</small>
            </footer>
        </article>`;
}
