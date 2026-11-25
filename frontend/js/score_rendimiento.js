// frontend/js/score_rendimiento.js
// Rendimiento del score (24/11/2026): tablas para ver si los tramos D y E son malos de verdad o les faltó intento
// (OSIPTEL, horario, orden en el cliente). Solo mide, no cambia el score. Datos: POST /generador-bases/rendimiento,
// que lee score.RendimientoDia (fase 13). Los permisos reales están en el backend.

const BASE_URL = `${location.protocol}//${location.hostname}:8000`;
const API = `${BASE_URL}/generador-bases`;
const TRAMOS = ["A", "B", "C", "D", "E", "SIN SCORE"];
const MIN_MUESTRA = 200;          // intentos mínimos para leer una tasa sin marcarla en gris
const ESPERA_MS = 350;
const FILTROS = [
    { dim: "Tramo", titulo: "Tramo" },
    { dim: "Orden", titulo: "Orden en el cliente" },
    { dim: "Osiptel", titulo: "OSIPTEL" },
    { dim: "Timbra", titulo: "Timbrado" },
    { dim: "Whatsapp", titulo: "WhatsApp" },
    { dim: "Origen", titulo: "Origen" },
    { dim: "Fuente", titulo: "Fuente" },
    { dim: "Color", titulo: "Color" },
    { dim: "Canal", titulo: "Canal de la base" },
];
const RESULTADOS = [
    ["R_Cef", "CEF"], ["R_Tercero", "Tercero"], ["R_ContestaSinId", "Contesta sin identificar"],
    ["R_NoContesta", "No contesta"], ["R_Buzon", "Buzón"], ["R_Apagado", "Apagado"], ["R_NoExiste", "No existe"],
    ["R_Equivocado", "Equivocado"], ["R_Otro", "Otro"], ["R_SinResultado", "Sin resultado"],
];
const FRANJAS = [["Manana", "Mañana"], ["Medio", "Medio día"], ["Tarde", "Tarde"], ["Noche", "Noche"]];

const estado = { carteras: [], idcartera: null, universo: "CARTERA", dias: 7, filtros: {}, datos: null, pedido: 0, modoDesglose: "matriz", cobertura: null, coberturaError: "" };
let espera = null;

const $ = id => document.getElementById(id);
const esc = v => String(v ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const num = v => (v == null || !isFinite(v)) ? "—" : Number(v).toLocaleString("es-PE", { maximumFractionDigits: 0 });
const dec = (v, d = 2) => (v == null || !isFinite(v)) ? "—" : Number(v).toLocaleString("es-PE", { minimumFractionDigits: d, maximumFractionDigits: d });
const pct = (v, d = 1) => (v == null || !isFinite(v)) ? "—" : `${dec(v * 100, d)} %`;
const div = (a, b) => b ? a / b : null;
const fecha = iso => iso ? iso.split("-").reverse().join("/") : "—";

function mostrarMensaje(texto, tipo = "") {
    const caja = $("mensaje");
    if (!texto) { caja.classList.add("hidden"); return; }
    caja.className = `st-mensaje ${tipo}`;
    caja.textContent = texto;
}

async function pedir(url, opciones = {}) {
    const response = await fetchConSesion(url, opciones);
    if (!response.ok) {
        const porDefecto = esAccesoDenegado(response)
            ? "No tienes acceso a esta cartera o al generador de bases."
            : "No se pudo completar la operación.";
        throw new Error(await mensajeErrorRespuesta(response, porDefecto));
    }
    return response.json();
}

function manejarError(error) {
    if (typeof SesionInvalidaError !== "undefined" && error instanceof SesionInvalidaError) return;
    console.error(error);
    mostrarMensaje(error.message || "Ocurrió un error.", "error");
}

// ---------------- Agregación en el navegador ----------------
const MEDIDAS = ["Telefonos", "Marcados", "Intentos", "IntentosHumano", "IntentosMaquina", "Cef", "ConCefPaleta",
    ...RESULTADOS.map(r => r[0]), ...FRANJAS.flatMap(([f]) => [`Int_${f}`, `Cef_${f}`])];

function sumar(filas) {
    const s = Object.fromEntries(MEDIDAS.map(m => [m, 0]));
    s.Dias = 0;
    for (const f of filas) {
        for (const m of MEDIDAS) s[m] += Number(f[m] || 0);
        s.Dias = Math.max(s.Dias, Number(f.Dias || 0));
    }
    return s;
}

function filasDe(dimension) { return (estado.datos?.filas || []).filter(f => f.Dimension === dimension); }
function porTramo() {
    const filas = filasDe("Total");
    const mapa = Object.fromEntries(filas.map(f => [f.Tramo, f]));
    const tramos = TRAMOS.filter(t => mapa[t]).concat(filas.map(f => f.Tramo).filter(t => !TRAMOS.includes(t)));
    return { tramos, mapa, total: sumar(filas) };
}

// ---------------- Medidas ----------------
const cef100 = s => div(s.Cef * 100, s.Intentos);
const MEDIDAS_VISTA = {
    cef100:        { tasa: true,  v: s => cef100(s), txt: x => dec(x) },
    indice:        { tasa: true,  v: (s, ref) => div(cef100(s), cef100(ref)), txt: x => x == null ? "—" : `${dec(x, 1)}×` },
    pctMarcados:   { tasa: true,  v: s => div(s.Marcados, s.Telefonos), txt: x => pct(x) },
    intPorMarcado: { tasa: true,  v: s => div(s.Intentos, s.Marcados), txt: x => dec(x, 1) },
    pctCefMarcados:{ tasa: true,  v: s => div(s.R_Cef, s.Marcados), txt: x => pct(x) },
    pctContestan:  { tasa: true,  v: s => div(s.R_Cef + s.R_Tercero + s.R_ContestaSinId, s.Marcados), txt: x => pct(x) },
    intentos:      { tasa: false, v: s => s.Intentos, txt: num },
    cef:           { tasa: false, v: s => s.Cef, txt: num },
    telDia:        { tasa: false, v: s => div(s.Telefonos, s.Dias), txt: num },
};

// Semáforo: compara el valor con la referencia (fila Total o total del tramo). Gris si la muestra es chica.
function semaforo(v, ref, intentos) {
    if (intentos != null && intentos < MIN_MUESTRA) return "sr-poca";
    if (v == null || ref == null || !ref) return "";
    const r = v / ref;
    if (r >= 1.5) return "sr-v3";
    if (r >= 1.1) return "sr-v2";
    if (r > 0.9) return "sr-n";
    if (r > 0.5) return "sr-r1";
    return "sr-r2";
}
const td = (txt, clase = "", titulo = "", estilo = "") => `<td${clase ? ` class="${clase}"` : ""}${estilo ? ` style="${estilo}"` : ""}${titulo ? ` title="${esc(titulo)}"` : ""}>${txt}</td>`;
// Cobertura e insistencia no son "buenas" o "malas": se pintan en azul, más oscuro cuanto más sobre la referencia
const azul = (v, ref) => `--calor:${(v == null || !ref) ? 0 : Math.max(0, Math.min(1, v / ref / 2)).toFixed(2)}`;
const badge = t => `<span class="sr-tramo sr-t-${String(t).replace(/\s+/g, "")}">${esc(t)}</span>`;
function barras(pInt, pCef) {
    const w = x => Math.max(0, Math.min(100, (x || 0) * 100)).toFixed(1);
    return `<div class="sr-barras" title="Intentos ${pct(pInt)} · CEF ${pct(pCef)}">
        <div><span class="sr-b-int" style="width:${w(pInt)}%"></span><em>${pct(pInt, 0)}</em></div>
        <div><span class="sr-b-cef" style="width:${w(pCef)}%"></span><em>${pct(pCef, 0)}</em></div></div>`;
}

// Columnas de métricas (tabla por tramo y desglose "todas las medidas")
const CABECERA_METRICAS = `
    <th title="Teléfonos del grupo, promedio por día">Teléfonos / día</th>
    <th title="Teléfono-días con al menos una llamada">% marcados</th>
    <th>Intentos</th>
    <th title="Llamadas por teléfono el día que se marcó">Intentos / marcado</th>
    <th class="sr-th-barras" title="Azul: parte de las llamadas · Verde: parte de los CEF">Esfuerzo vs CEF</th>
    <th>CEF</th>
    <th title="CEF por cada 100 llamadas">CEF / 100 int.</th>
    <th title="CEF / 100 del grupo ÷ el de la referencia">Índice</th>
    <th title="Teléfonos marcados que terminaron el día con CEF">% marcados con CEF</th>
    <th title="CEF + tercero + contesta sin identificar, sobre marcados">% contestan</th>
    <th title="Llamadas hechas por la máquina (predictivo / IVR)">% máquina</th>`;

function celdasMetricas(s, ref, total) {
    const m = k => MEDIDAS_VISTA[k].v(s, ref);
    const r = k => MEDIDAS_VISTA[k].v(ref, ref);
    return td(num(m("telDia")))
        + td(pct(m("pctMarcados")), "sr-calor-azul", "", azul(m("pctMarcados"), r("pctMarcados")))
        + td(num(s.Intentos))
        + td(dec(m("intPorMarcado"), 1), "sr-calor-azul", "", azul(m("intPorMarcado"), r("intPorMarcado")))
        + td(barras(div(s.Intentos, total.Intentos), div(s.Cef, total.Cef)), "sr-td-barras")
        + td(num(s.Cef))
        + td(`<strong>${dec(m("cef100"))}</strong>`, semaforo(m("cef100"), r("cef100"), s.Intentos))
        + td(MEDIDAS_VISTA.indice.txt(m("indice")), semaforo(m("cef100"), r("cef100"), s.Intentos))
        + td(pct(m("pctCefMarcados")), semaforo(m("pctCefMarcados"), r("pctCefMarcados"), s.Intentos))
        + td(pct(m("pctContestan")), semaforo(m("pctContestan"), r("pctContestan"), s.Intentos))
        + td(pct(div(s.IntentosMaquina, s.Intentos), 0));
}

// ---------------- Tablas ----------------
// Cobertura del periodo: teléfonos distintos y cuántos recibieron al menos una llamada (llega en un segundo pedido)
function coberturaDe(tramo) {
    const c = estado.cobertura;
    if (!c) return null;
    const filas = tramo === "Total" ? c.filas : c.filas.filter(f => f.Tramo === tramo);
    if (!filas.length) return { vacio: true };
    const s = { TelefonosDistintos: 0, Llamados: 0, LlamadosAsesor: 0, DiasLlamado: 0, SinLlamadaPdp: 0,
                SinLlamadaCefOtro: 0, SinLlamadaOtroTel: 0, SinLlamadaCliente: 0, ClientesSinLlamada: 0 };
    for (const f of filas) for (const k of Object.keys(s)) s[k] += Number(f[k] || 0);
    return s;
}

// Metas de cobertura por tramo: las define el usuario (no hay un ideal universal). Se guardan en este navegador.
const METAS_POR_DEFECTO = { A: 100 };
function metas() {
    try { return { ...METAS_POR_DEFECTO, ...JSON.parse(localStorage.getItem(`sr_metas_${estado.idcartera}`) || "{}") }; }
    catch { return { ...METAS_POR_DEFECTO }; }
}
function guardarMeta(tramo, valor) {
    const m = metas();
    const v = Number(String(valor).replace(",", "."));
    if (valor === "" || !isFinite(v)) delete m[tramo]; else m[tramo] = Math.max(0, Math.min(100, v));
    try { localStorage.setItem(`sr_metas_${estado.idcartera}`, JSON.stringify(m)); } catch { /* sin almacenamiento */ }
    renderCobertura();
}

function renderCobertura() {
    const tabla = $("tblCobertura");
    if (estado.coberturaError) { tabla.innerHTML = `<tbody><tr><td class="st-vacio">${esc(estado.coberturaError)}</td></tr></tbody>`; return; }
    if (!estado.cobertura) { tabla.innerHTML = `<tbody><tr><td class="st-vacio">Contando teléfonos del periodo…</td></tr></tbody>`; $("tblMotivos").innerHTML = ""; return; }
    const tramos = TRAMOS.filter(t => t !== "SIN SCORE" && coberturaDe(t) && !coberturaDe(t).vacio);
    const total = coberturaDe("Total");
    if (!tramos.length || total.vacio) { tabla.innerHTML = `<tbody><tr><td class="st-vacio">Sin datos para lo elegido.</td></tr></tbody>`; return; }
    const { mapa, total: totalDia } = porTramo();
    const m = metas();
    const fila = (t, c, clase = "") => {
        const cob = div(c.Llamados, c.TelefonosDistintos);
        const dia = clase ? totalDia : (mapa[t] ? sumar([mapa[t]]) : null);
        const pDia = dia ? div(dia.Marcados, dia.Telefonos) : null;
        const meta = clase ? null : m[t];
        const faltan = meta != null ? Math.max(0, Math.ceil(c.TelefonosDistintos * meta / 100) - c.Llamados) : null;
        const celdaMeta = clase ? td("") : td(`<input class="sr-meta" type="number" min="0" max="100" step="5" data-tramo="${esc(t)}" value="${meta ?? ""}" placeholder="—" aria-label="Meta de cobertura del tramo ${esc(t)}"> %`, "sr-td-meta");
        const claseFaltan = faltan == null ? "" : (faltan === 0 ? "sr-v2" : (meta && cob * 100 < meta * 0.8 ? "sr-r2" : "sr-r1"));
        return `<tr class="${clase}"><th>${clase ? "Total" : badge(t)}</th>
            ${td(num(c.TelefonosDistintos))}
            ${td(pct(pDia), "sr-calor-azul", "", azul(pDia, div(totalDia.Marcados, totalDia.Telefonos)))}
            ${td(pDia ? `cada ${dec(1 / pDia, 1)} días` : "—", "", "Si cada día se llama a esa parte de los teléfonos, en promedio a un mismo teléfono le toca cada tantos días")}
            ${td(num(c.Llamados))}
            ${td(num(c.TelefonosDistintos - c.Llamados))}
            ${td(`<div class="sr-cobbar"><span style="width:${Math.min(100, (cob || 0) * 100).toFixed(1)}%"></span>${meta != null ? `<i style="left:${meta}%"></i>` : ""}<em>${pct(cob)}</em></div>`, "sr-td-barras")}
            ${celdaMeta}
            ${td(faltan == null ? "—" : (faltan === 0 ? "Cumple" : `${num(faltan)} tel.`), claseFaltan)}
            ${td(pct(div(c.LlamadosAsesor, c.TelefonosDistintos)))}
            ${td(dec(div(c.DiasLlamado, c.Llamados), 1))}</tr>`;
    };
    tabla.innerHTML = `<thead><tr><th>Tramo</th>
            <th title="Teléfonos distintos que estuvieron en el tramo algún día del periodo">Teléfonos distintos</th>
            <th title="En un día promedio, qué parte de los teléfonos del tramo recibió al menos una llamada">% marcados por día</th>
            <th title="1 ÷ % marcados por día">Le toca llamada</th>
            <th title="Recibieron al menos una llamada (asesor o máquina) un día en que estaban en el tramo">Llamados al menos una vez</th>
            <th title="No recibieron ninguna llamada en el periodo mientras estaban en el tramo">Sin ninguna llamada</th>
            <th class="sr-th-barras" title="Llamados ÷ teléfonos distintos. La raya es la meta">Cobertura del periodo</th>
            <th title="Meta de cobertura que tú defines por tramo (se guarda en este navegador)">Meta</th>
            <th title="Teléfonos que faltó llamar al menos una vez para llegar a la meta">Faltan</th>
            <th title="Recibieron al menos una llamada de un asesor">% llamados por asesor</th>
            <th title="De los teléfonos llamados, en cuántos días distintos se les llamó (promedio)">Días con llamada</th>
        </tr></thead>
        <tbody>${tramos.map(t => fila(t, coberturaDe(t))).join("")}${fila("Total", total, "sr-total")}</tbody>`;
    renderMotivos(tramos, total);
}

// Por qué no se llamó: teléfonos sin ninguna llamada en el periodo, según lo que pasó con su cliente
const MOTIVOS = [
    ["SinLlamadaPdp", "Cliente con promesa vigente o pagada (hoy)", "No hacía falta llamarlo: tiene una promesa vigente o ya la pagó, según el estado de hoy"],
    ["SinLlamadaCefOtro", "Cliente con CEF por otro teléfono", "En el periodo se habló con el cliente por otro de sus teléfonos"],
    ["SinLlamadaOtroTel", "Cliente llamado por otro teléfono, sin CEF", "El cliente sí se marcó en el periodo, pero por otros teléfonos: este no se usó"],
    ["SinLlamadaCliente", "Cliente sin ninguna llamada", "Nadie llamó al cliente en el periodo por ningún teléfono, y no tiene promesa vigente ni pagada"],
];
function renderMotivos(tramos, total) {
    const tabla = $("tblMotivos");
    if (!tabla) return;
    if (!total || total.vacio || !(total.TelefonosDistintos - total.Llamados)) { tabla.innerHTML = ""; return; }
    const fila = (t, c, clase = "") => {
        const sin = c.TelefonosDistintos - c.Llamados;
        return `<tr class="${clase}"><th>${clase ? "Total" : badge(t)}</th>${td(num(sin))}
            ${MOTIVOS.map(([k], i) => {
                const v = c[k] || 0, p = div(v, sin);
                const cls = i === 3 ? (v ? "sr-oportunidad" : "") : "";
                return td(`${num(v)}<small>${pct(p, 0)}</small>`, cls);
            }).join("")}
            ${td(clase ? "—" : num(c.ClientesSinLlamada), clase ? "" : "sr-oportunidad", clase ? "Un cliente con teléfonos en dos tramos cuenta en cada uno: el total no se suma" : "")}</tr>`;
    };
    tabla.innerHTML = `<thead><tr><th>Tramo</th><th title="Teléfonos que no recibieron ninguna llamada en el periodo mientras estaban en el tramo">Sin ninguna llamada</th>
            ${MOTIVOS.map(([, n, t]) => `<th title="${esc(t)}">${esc(n)}</th>`).join("")}
            <th title="Clientes distintos detrás de esos teléfonos">Clientes sin ninguna llamada</th></tr></thead>
        <tbody>${tramos.map(t => fila(t, coberturaDe(t))).join("")}${fila("Total", total, "sr-total")}</tbody>`;
}

function renderTramo() {
    const { tramos, mapa, total } = porTramo();
    const fila = (t, s, clase = "") => `<tr class="${clase}"><th>${clase ? "Total" : badge(t)}</th>${celdasMetricas(s, total, total)}</tr>`;
    $("tblTramo").innerHTML = `<thead><tr><th>Tramo</th>${CABECERA_METRICAS}</tr></thead>
        <tbody>${tramos.map(t => fila(t, mapa[t])).join("")}${fila("Total", total, "sr-total")}</tbody>`;
}

function renderResultado() {
    const { tramos, mapa, total } = porTramo();
    // Columnas que en todo el periodo valen 0 no aportan (p. ej. "contesta sin identificar" sin centralita)
    const cols = RESULTADOS.filter(([c]) => total[c] > 0);
    const ocultas = RESULTADOS.filter(([c]) => !(total[c] > 0)).map(r => r[1]);
    const fila = (t, s, clase = "") => `<tr class="${clase}"><th>${clase ? "Total" : badge(t)}</th>${td(num(s.Marcados))}
        ${cols.map(([c]) => { const v = div(s[c], s.Marcados); return td(pct(v), "sr-calor", "", ).replace("<td", `<td style="--calor:${Math.min(1, (v || 0) * 1.6).toFixed(2)}"`); }).join("")}</tr>`;
    $("tblResultado").innerHTML = `
        <thead><tr><th>Tramo</th><th title="Teléfono-días marcados">Marcados</th>${cols.map(r => `<th>${r[0] === "R_SinResultado" ? "Solo máquina (no pasó a asesor)" : r[1]}</th>`).join("")}</tr></thead>
        <tbody>${tramos.map(t => fila(t, mapa[t])).join("")}${fila("Total", total, "sr-total")}</tbody>`;
    const sinCentralita = (estado.datos?.control || []).every(c => !c.centralita);
    $("notaResultado").textContent = [
        sinCentralita ? "El periodo no tiene centralita: de las llamadas de máquina que no pasaron a un asesor no se sabe si fue buzón, apagado o no contesta; quedan como \"Solo máquina\"." : "",
        ocultas.length ? `Sin casos en el periodo: ${ocultas.join(", ")}.` : "",
    ].filter(Boolean).join(" ");
}

function renderFranja() {
    const { tramos, mapa, total } = porTramo();
    const conFranja = s => FRANJAS.reduce((a, [f]) => a + s[`Int_${f}`], 0);
    const haySinFranja = total.Intentos - conFranja(total) > 0;
    const fila = (t, s, clase = "") => {
        const ref = cef100(s);   // cada franja contra el promedio del mismo tramo
        const tasas = FRANJAS.map(([f]) => s[`Int_${f}`] >= MIN_MUESTRA ? div(s[`Cef_${f}`] * 100, s[`Int_${f}`]) : null);
        const mejor = Math.max(...tasas.filter(x => x != null));
        return `<tr class="${clase}"><th>${clase ? "Total" : badge(t)}</th>
            ${FRANJAS.map(([f], i) => {
                const it = s[`Int_${f}`];
                const tasa = div(s[`Cef_${f}`] * 100, it);
                const marca = tasas[i] != null && tasas[i] === mejor ? " sr-mejor" : "";
                return td(`${num(it)}<small>${pct(div(it, s.Intentos), 0)} del tramo</small>`, "sr-col-int")
                     + td(`${dec(tasa)}${marca ? "<small>mejor franja</small>" : ""}`, semaforo(tasa, ref, it) + marca);
            }).join("")}
            ${haySinFranja ? td(num(s.Intentos - conFranja(s))) : ""}</tr>`;
    };
    $("tblFranja").innerHTML = `
        <thead>
            <tr><th rowspan="2">Tramo</th>${FRANJAS.map(f => `<th colspan="2" class="sr-th-grupo">${f[1]}</th>`).join("")}
                ${haySinFranja ? `<th rowspan="2" title="Intentos antes de las 6 a. m., o de días cargados sin franja (antes de la fase 13)">Sin franja</th>` : ""}</tr>
            <tr>${FRANJAS.map(() => `<th>Intentos</th><th>CEF / 100</th>`).join("")}</tr>
        </thead>
        <tbody>${tramos.map(t => fila(t, mapa[t])).join("")}${fila("Total", total, "sr-total")}</tbody>`;
}

function valoresDe(dim, filas) {
    return [...new Set(filas.map(f => f.Valor))].sort((a, b) => dim === "Fecha"
        ? String(a).localeCompare(String(b)) : String(a).localeCompare(String(b), "es", { numeric: true }));
}
const etiquetaValor = (dim, v) => dim === "Fecha" ? `${fecha(v)} <small>${["dom", "lun", "mar", "mié", "jue", "vie", "sáb"][new Date(`${v}T12:00:00`).getDay()]}</small>` : esc(v);

function renderDesglose() {
    const dim = $("selDesglose").value;
    const detalle = estado.modoDesglose === "detalle";
    $("lblMedida").classList.toggle("hidden", detalle);
    $("lblTramoDetalle").classList.toggle("hidden", !detalle);
    const { tramos, mapa, total } = porTramo();
    const filas = filasDe(dim);
    const valores = valoresDe(dim, filas);
    if (!valores.length) { $("tblDesglose").innerHTML = `<tbody><tr><td class="st-vacio">Sin datos.</td></tr></tbody>`; return; }

    if (detalle) {
        const sel = $("selTramoDetalle");
        const previo = sel.value;
        sel.innerHTML = `<option value="">Todos los tramos</option>` + tramos.map(t => `<option value="${esc(t)}">Tramo ${esc(t)}</option>`).join("");
        sel.value = tramos.includes(previo) ? previo : "";
        const tramo = sel.value;
        const delTramo = f => !tramo || f.Tramo === tramo;
        const ref = tramo ? sumar([mapa[tramo]]) : total;
        $("ayudaDesglose").textContent = `Cada fila con todas las medidas${tramo ? ` dentro del tramo ${tramo}` : ""}. Los colores comparan con la fila Total${tramo ? ` del tramo ${tramo}` : ""}.`;
        const cuerpo = valores.map(v => {
            const s = sumar(filas.filter(f => f.Valor === v && delTramo(f)));
            return s.Telefonos || s.Intentos ? `<tr><th>${etiquetaValor(dim, v)}</th>${celdasMetricas(s, ref, ref)}</tr>` : "";
        }).join("");
        $("tblDesglose").innerHTML = `<thead><tr><th>${esc($("selDesglose").selectedOptions[0].text)}</th>${CABECERA_METRICAS}</tr></thead>
            <tbody>${cuerpo}<tr class="sr-total"><th>Total</th>${celdasMetricas(ref, ref, ref)}</tr></tbody>`;
        return;
    }

    const clave = $("selMedida").value;
    const med = MEDIDAS_VISTA[clave];
    const maxConteo = med.tasa ? 0 : Math.max(...valores.flatMap(v => filas.filter(f => f.Valor === v).map(f => med.v(sumar([f])) || 0)));
    $("ayudaDesglose").textContent = med.tasa
        ? "Cada celda se colorea contra el total de su tramo (última fila): verde rinde más que el promedio del tramo, rojo menos. Debajo: intentos y CEF de la celda."
        : "Cada celda se sombrea según su tamaño. Debajo: intentos y CEF de la celda.";
    const celda = (s, ref) => {
        const v = med.v(s, ref);
        const sub = `<small>${num(s.Intentos)} int · ${num(s.Cef)} CEF</small>`;
        if (clave === "pctMarcados" || clave === "intPorMarcado")
            return td(`${med.txt(v)}${sub}`, "sr-calor-azul", "", azul(v, med.v(ref, ref)));
        if (med.tasa) {
            const base = clave === "indice" ? 1 : med.v(ref, ref);
            return td(`${med.txt(v)}${sub}`, semaforo(v, base, s.Intentos));
        }
        return td(`${med.txt(v)}${sub}`, "sr-calor-azul").replace("<td", `<td style="--calor:${maxConteo ? ((v || 0) / maxConteo).toFixed(2) : 0}"`);
    };
    const refTramo = Object.fromEntries(tramos.map(t => [t, sumar([mapa[t]])]));
    const cuerpo = valores.map(v => {
        const deValor = filas.filter(f => f.Valor === v);
        const porT = Object.fromEntries(deValor.map(f => [f.Tramo, sumar([f])]));
        return `<tr><th>${etiquetaValor(dim, v)}</th>${tramos.map(t => porT[t] ? celda(porT[t], refTramo[t]) : td("—")).join("")}${celda(sumar(deValor), total)}</tr>`;
    }).join("");
    const pie = `<tr class="sr-total"><th>Total</th>${tramos.map(t => celda(refTramo[t], refTramo[t])).join("")}${celda(total, total)}</tr>`;
    $("tblDesglose").innerHTML = `<thead><tr><th>${esc($("selDesglose").selectedOptions[0].text)}</th>${tramos.map(t => `<th>${badge(t)}</th>`).join("")}<th>Total</th></tr></thead>
        <tbody>${cuerpo}${pie}</tbody>`;
}

// Avisos de calidad del periodo: días de lunes a sábado sin llamadas de máquina en SISCOB
function renderAvisos() {
    const control = estado.datos?.control || [];
    const conMaquina = control.some(c => c.maquina > 0);
    const sinMaquina = control.filter(c => conMaquina && c.humano > 0 && c.maquina === 0 && new Date(`${c.fecha}T12:00:00`).getDay() !== 0);
    const caja = $("avisos");
    if (!sinMaquina.length) { caja.classList.add("hidden"); return; }
    caja.innerHTML = `⚠ ${sinMaquina.map(c => fecha(c.fecha)).join(", ")}: SISCOB no tiene llamadas de máquina ese día (solo asesores), así que sus tasas salen más altas de lo real. `
        + `Mira el desglose por <strong>Día</strong>. Se vuelve a cargar solo cuando lleguen las llamadas.`;
    caja.classList.remove("hidden");
}

// Lectura en una línea: solo cuentas sobre las filas que llegaron, nada estimado.
function renderLectura() {
    const { mapa, total } = porTramo();
    const caja = $("lectura");
    const de = sumar(["D", "E"].map(t => mapa[t]).filter(Boolean));
    const a = mapa.A ? sumar([mapa.A]) : null;
    if (!total.Intentos || !de.Telefonos) { caja.classList.add("hidden"); return; }
    const partes = [
        `D + E: <strong>${pct(div(de.Intentos, total.Intentos))}</strong> de los intentos y <strong>${pct(div(de.Cef, total.Cef))}</strong> de los CEF.`,
        `Se marcó el <strong>${pct(div(de.Marcados, de.Telefonos))}</strong> de sus teléfono-días, con <strong>${dec(div(de.Intentos, de.Marcados), 1)}</strong> intentos por marcado.`,
    ];
    if (a && a.Intentos) partes.push(`CEF por 100 intentos: A <strong>${dec(cef100(a))}</strong> · D + E <strong>${dec(cef100(de))}</strong>.`);
    const ca = coberturaDe("A");
    if (ca && !ca.vacio) partes.push(`<br>Tramo A en el periodo: se llamó al <strong>${pct(div(ca.Llamados, ca.TelefonosDistintos))}</strong> de sus teléfonos al menos una vez; <strong>${num(ca.TelefonosDistintos - ca.Llamados)}</strong> teléfonos A no recibieron ninguna llamada.`);
    caja.innerHTML = partes.join(" ");
    caja.classList.remove("hidden");
}

function renderTodo() {
    const d = estado.datos;
    if (!d || d.sin_datos) {
        ["tblTramo", "tblResultado", "tblFranja", "tblDesglose"].forEach(id => $(id).innerHTML = `<tbody><tr><td class="st-vacio">Sin datos para lo elegido.</td></tr></tbody>`);
        $("lectura").classList.add("hidden");
        $("avisos").classList.add("hidden");
        $("rango").textContent = d?.mensaje || "Sin datos.";
        if (d?.mensaje) mostrarMensaje(d.mensaje);
        if (d?.valores) renderFiltros();
        return;
    }
    mostrarMensaje("");
    const dias = porTramo().total.Dias;
    const recortado = d.desde_pedido && d.desde_pedido < d.desde;
    $("rango").innerHTML = `Del <strong>${fecha(d.desde)}</strong> al <strong>${fecha(d.hasta)}</strong> · <strong>${dias}</strong> día(s) con datos`
        + (recortado ? ` <small>(antes del ${fecha(d.desde)} no hay datos armados)</small>` : "")
        + (d.carteras?.length > 1 ? ` · suma ${d.carteras.join(" + ")}` : "");
    renderFiltros();
    renderAvisos();
    renderLectura();
    renderTramo();
    renderCobertura();
    renderResultado();
    renderFranja();
    renderDesglose();
}

// ---------------- Filtros ----------------
function renderFiltros() {
    const valores = estado.datos?.valores || {};
    $("filtros").innerHTML = FILTROS.filter(f => (valores[f.dim] || []).length > 1 || (estado.filtros[f.dim] || []).length).map(f => {
        const elegidos = new Set(estado.filtros[f.dim] || []);
        const lista = [...new Set([...(valores[f.dim] || []), ...elegidos])];
        if (f.dim === "Tramo") lista.sort((a, b) => TRAMOS.indexOf(a) - TRAMOS.indexOf(b));
        return `<div class="sr-filtro"><span class="st-label">${f.titulo}</span><div class="sr-pills">
            ${lista.map(v => `<button type="button" class="sr-pill${elegidos.has(v) ? " on" : ""}" data-dim="${f.dim}" data-valor="${esc(v)}">${esc(v)}</button>`).join("")}
        </div></div>`;
    }).join("") || `<span class="st-vacio">Sin atributos para filtrar en este periodo.</span>`;
}

function alternarFiltro(dim, valor) {
    const set = new Set(estado.filtros[dim] || []);
    set.has(valor) ? set.delete(valor) : set.add(valor);
    if (set.size) estado.filtros[dim] = [...set]; else delete estado.filtros[dim];
    renderFiltros();
    programarCarga();
}

// ---------------- Carga ----------------
function programarCarga() { clearTimeout(espera); espera = setTimeout(cargar, ESPERA_MS); }

async function cargar() {
    if (!estado.idcartera) return;
    const pedido = ++estado.pedido;
    document.body.classList.add("sr-cargando");
    try {
        const cuerpo = JSON.stringify({ idcartera: estado.idcartera, dias: estado.dias, universo: estado.universo, filtros: estado.filtros });
        const datos = await pedir(`${API}/rendimiento`, { method: "POST", headers: { "Content-Type": "application/json" }, body: cuerpo });
        if (pedido !== estado.pedido) return;   // llegó una respuesta vieja
        estado.datos = datos;
        estado.cobertura = null;
        estado.coberturaError = "";
        renderTodo();
        if (!datos.sin_datos) cargarCobertura(pedido, cuerpo);
    } catch (error) {
        if (pedido === estado.pedido) manejarError(error);
    } finally {
        if (pedido === estado.pedido) document.body.classList.remove("sr-cargando");
    }
}

async function cargarCobertura(pedido, cuerpo) {
    try {
        const c = await pedir(`${API}/rendimiento/cobertura`, { method: "POST", headers: { "Content-Type": "application/json" }, body: cuerpo });
        if (pedido !== estado.pedido) return;
        estado.cobertura = c;
    } catch (error) {
        if (pedido !== estado.pedido) return;
        if (typeof SesionInvalidaError !== "undefined" && error instanceof SesionInvalidaError) return;
        console.error(error);
        estado.coberturaError = error.message || "No se pudo calcular la cobertura.";
    }
    renderCobertura();
    renderLectura();
}

async function cargarCarteras() {
    const { data } = await pedir(`${API}/carteras`);
    estado.carteras = data || [];
    const sel = $("selCartera");
    if (!estado.carteras.length) {
        sel.innerHTML = `<option>Sin carteras</option>`;
        mostrarMensaje("No tienes carteras con tabla de trabajo armada.");
        return;
    }
    sel.innerHTML = estado.carteras.map(c => `<option value="${c.IdCartera}">${c.IdCartera} · ${esc(c.Nombre)}${c.Entidad ? ` (${esc(c.Entidad)})` : ""}</option>`).join("");
    const pedida = Number(new URLSearchParams(location.search).get("idcartera")) || Number(localStorage.getItem("gb_idcartera"));
    const existe = estado.carteras.some(c => Number(c.IdCartera) === pedida);
    estado.idcartera = existe ? pedida : Number(estado.carteras[0].IdCartera);
    sel.value = String(estado.idcartera);
}

function enlazarEventos() {
    $("minMuestra").textContent = MIN_MUESTRA;
    $("selCartera").addEventListener("change", e => {
        estado.idcartera = Number(e.target.value);
        localStorage.setItem("gb_idcartera", String(estado.idcartera));
        estado.filtros = {};
        cargar();
    });
    document.querySelectorAll(".sr-tab[data-universo]").forEach(b => b.addEventListener("click", () => {
        document.querySelectorAll(".sr-tab[data-universo]").forEach(x => { x.classList.toggle("active", x === b); x.setAttribute("aria-selected", String(x === b)); });
        estado.universo = b.dataset.universo;
        cargar();
    }));
    document.querySelectorAll(".sr-dias").forEach(b => b.addEventListener("click", () => {
        document.querySelectorAll(".sr-dias").forEach(x => x.classList.toggle("active", x === b));
        estado.dias = Number(b.dataset.dias);
        cargar();
    }));
    $("filtros").addEventListener("click", e => {
        const p = e.target.closest(".sr-pill");
        if (p) alternarFiltro(p.dataset.dim, p.dataset.valor);
    });
    $("btnLimpiarFiltros").addEventListener("click", () => { estado.filtros = {}; renderFiltros(); cargar(); });
    $("selDesglose").addEventListener("change", renderDesglose);
    $("tblCobertura").addEventListener("change", e => {
        const i = e.target.closest(".sr-meta");
        if (i) guardarMeta(i.dataset.tramo, i.value);
    });
    $("selTramoDetalle").addEventListener("change", renderDesglose);
    document.querySelectorAll(".sr-modo").forEach(b => b.addEventListener("click", () => {
        document.querySelectorAll(".sr-modo").forEach(x => x.classList.toggle("active", x === b));
        estado.modoDesglose = b.dataset.modo;
        renderDesglose();
    }));
    $("selMedida").addEventListener("change", renderDesglose);
}

document.addEventListener("DOMContentLoaded", async () => {
    const sesionOk = typeof asegurarSesionBackend === "function" && await asegurarSesionBackend();
    if (!sesionOk) return;   // session.js redirige o muestra el error
    enlazarEventos();
    try {
        await cargarCarteras();
        await cargar();
    } catch (error) {
        manejarError(error);
    }
});
