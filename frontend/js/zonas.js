// frontend/js/zonas.js
// Zonas restringidas: mapa del Perú para elegir departamentos (uno a uno o por zona) y restringir o levantar
// su gestión. El generador de bases quita a los clientes de las zonas vigentes (paso «Sin zona restringida»).
// Los permisos reales están en el backend (/zonas-restringidas/*): ver = jefes y supervisores, registrar = jefes.

const BASE_URL = `${location.protocol}//${location.hostname}:8000`;
const API = `${BASE_URL}/zonas-restringidas`;

// Agrupación propuesta para seleccionar rápido (no cambia nada en la base: solo ayuda a elegir).
// c = color de la zona, t = tinte claro (relleno normal), m = tinte medio (hover).
const ZONAS = [
    { clave: "norte", nombre: "Norte", c: "#e8912b", t: "#fde7c7", m: "#f9cf93",
      deps: ["TUMBES", "PIURA", "LAMBAYEQUE", "LA LIBERTAD", "CAJAMARCA", "ANCASH"] },
    { clave: "lima", nombre: "Lima y Callao", c: "#7c6cf0", t: "#e7e3fd", m: "#cbc3fa",
      deps: ["LIMA", "CALLAO"] },
    { clave: "centro", nombre: "Centro", c: "#1f9e8f", t: "#d7f1ed", m: "#a9e0d8",
      deps: ["HUANUCO", "PASCO", "JUNIN", "HUANCAVELICA", "ICA", "AYACUCHO"] },
    { clave: "sur", nombre: "Sur", c: "#3b7fe0", t: "#e3eefc", m: "#bcd5f7",
      deps: ["AREQUIPA", "MOQUEGUA", "TACNA", "PUNO", "CUSCO", "APURIMAC"] },
    { clave: "oriente", nombre: "Oriente", c: "#4ea64a", t: "#e0f2dc", m: "#b9e1b2",
      deps: ["AMAZONAS", "LORETO", "SAN MARTIN", "UCAYALI", "MADRE DE DIOS"] },
];
const ZONA_DE = {};
ZONAS.forEach(z => z.deps.forEach(d => { ZONA_DE[d] = z; }));
// Etiquetas que no caben dentro del departamento: se dibujan afuera con una guía.
const ETIQUETA_FUERA = { CALLAO: { x: 150, y: 560 }, TUMBES: { x: 30, y: 160 } };
// Etiquetas movidas dentro de su departamento para que no choquen con la del vecino.
const ETIQUETA_POS = { CAJAMARCA: { x: 142, y: 284 }, LAMBAYEQUE: { x: 66, y: 304 } };
const SVG_NS = "http://www.w3.org/2000/svg";

const estado = {
    seleccion: new Set(),
    zonas: [],          // filas de score.ZonaRestringida (activas + historial)
    carteras: [],
    puedeEditar: false,
    excluidos: null,    // { por_zona, por_cartera } con PDP vigentes
    cobertura: null,    // { carteras: [{IdCartera, Clientes, ConDepartamento, SinDepartamento, NoReconocido}], no_reconocidos }
    simulacion: null,   // { porDep: {PIURA: n}, filas: [...] }
};
const nombres = {};     // PIURA -> Piura

const $ = id => document.getElementById(id);
const esc = v => String(v ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const num = v => (v === null || v === undefined || v === "") ? "—" : Number(v).toLocaleString("es-PE");
const fecha = v => {
    if (!v) return "—";
    const [a, m, d] = String(v).slice(0, 10).split("-");
    return d ? `${d}/${m}/${a}` : String(v);
};
const hoyIso = () => {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};
const soles = v => `S/ ${Number(v || 0).toLocaleString("es-PE", { maximumFractionDigits: 0 })}`;
const pct = v => `${(v * 100).toLocaleString("es-PE", { maximumFractionDigits: 1 })}%`;
const nombreDep = c => nombres[c] || c;
// Criterio propuesto para el semáforo del departamento (% de clientes de la base de trabajo con un departamento
// reconocido). Ajustable.
const UMBRAL_OK = 0.98, UMBRAL_REVISAR = 0.90;
const nombreCartera = id => {
    const c = estado.carteras.find(x => x.IdCartera === Number(id));
    return c ? `${c.IdCartera} · ${c.Nombre}` : String(id);
};

function mostrarMensaje(texto, tipo = "") {
    const caja = $("mensaje");
    if (!texto) { caja.classList.add("hidden"); return; }
    caja.className = `zr-mensaje ${tipo}`;
    caja.textContent = texto;
    caja.scrollIntoView({ block: "nearest", behavior: "smooth" });
}

async function pedir(url, opciones = {}) {
    if (opciones.json !== undefined) {
        opciones = { ...opciones, method: opciones.method || "POST", body: JSON.stringify(opciones.json),
                     headers: { "Content-Type": "application/json", ...(opciones.headers || {}) } };
        delete opciones.json;
    }
    const response = await fetchConSesion(url, opciones);
    if (!response.ok) {
        const porDefecto = esAccesoDenegado(response)
            ? "Tu perfil no puede hacer esta operación."
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

async function conBoton(boton, tarea) {
    if (boton.classList.contains("is-busy")) return;
    const texto = boton.textContent;
    boton.classList.add("is-busy");
    boton.disabled = true;
    try {
        return await tarea();
    } finally {
        boton.classList.remove("is-busy");
        boton.disabled = false;
        boton.textContent = texto;
        pintarPanel();
    }
}

// ------------------------------------------------------------------ estado de cada departamento
function zonasActivas() {
    return estado.zonas.filter(z => z.Activo && (z.Estado === "VIGENTE" || z.Estado === "PROGRAMADA"));
}

function activasDe(dep) {
    return zonasActivas().filter(z => z.Departamento === dep);
}

function estadoDep(dep) {
    const act = activasDe(dep);
    if (act.some(z => z.Estado === "VIGENTE")) return "restringido";
    if (act.length) return "programado";
    return "libre";
}

function metricaZona(idZona, campo) {
    if (!estado.excluidos) return null;
    return estado.excluidos.por_zona
        .filter(r => Number(r.IdZona) === Number(idZona))
        .reduce((s, r) => s + Number(r[campo] || 0), 0);
}
const clientesZona = idZona => metricaZona(idZona, "Clientes");

function clientesDep(dep) {
    if (!estado.excluidos) return null;
    return activasDe(dep).reduce((s, z) => s + (clientesZona(z.IdZona) || 0), 0);
}

// ------------------------------------------------------------------ calidad del departamento por cartera
function coberturaDe(id) {
    const c = estado.carteras.find(x => x.IdCartera === Number(id));
    const k = estado.cobertura ? estado.cobertura.carteras.find(x => Number(x.IdCartera) === Number(id)) : null;
    const clientes = k ? k.Clientes : null;
    const con = k ? k.ConDepartamento : 0;
    const share = clientes ? con / clientes : null;
    let nivel = "sincampo";
    if (c && c.TieneDepartamento) nivel = share === null ? "ok" : share >= UMBRAL_OK ? "ok" : share >= UMBRAL_REVISAR ? "revisar" : "incompleta";
    const fuera = clientes === null ? null : (k.SinDepartamento + k.NoReconocido);
    return { cartera: c, clientes, con, sin: k ? k.SinDepartamento : null, noRec: k ? k.NoReconocido : null, share, nivel, fuera };
}
const ETIQUETA_NIVEL = { ok: "Completo", revisar: "Revisar", incompleta: "Incompleto", sincampo: "Sin campo" };

// Carteras alcanzadas por las restricciones vigentes (todas si alguna aplica a todas).
function carterasAlcanzadas() {
    const vig = zonasActivas().filter(z => z.Estado === "VIGENTE");
    if (vig.some(z => z.AplicaTodas)) return estado.carteras.map(c => c.IdCartera);
    return [...new Set(vig.flatMap(z => z.Carteras))];
}

function alcanceTexto(z) {
    if (z.AplicaTodas) return "Todas las carteras";
    return (z.Carteras || []).map(nombreCartera).join(", ") || "—";
}

// ------------------------------------------------------------------ mapa
function crearSvg(tag, attrs = {}) {
    const el = document.createElementNS(SVG_NS, tag);
    Object.entries(attrs).forEach(([k, v]) => el.setAttribute(k, v));
    return el;
}

function dibujarMapa() {
    const svg = $("mapa");
    svg.setAttribute("viewBox", window.MAPA_PERU.viewBox);
    svg.innerHTML = `
        <defs>
            <pattern id="rayaRoja" width="7" height="7" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
                <rect width="7" height="7" fill="#fbd5d6"/><rect width="3" height="7" fill="#e5484d"/>
            </pattern>
            <pattern id="rayaAmbar" width="7" height="7" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
                <rect width="7" height="7" fill="#fde7c7"/><rect width="3" height="7" fill="#f2a33a"/>
            </pattern>
        </defs>`;
    const oceano = crearSvg("text", { x: 40, y: 800, class: "oceano" });
    oceano.textContent = "OCÉANO PACÍFICO";
    svg.appendChild(oceano);

    const capaDeps = crearSvg("g", { id: "capaDeps" });
    const capaEtq = crearSvg("g", { id: "capaEtq" });
    svg.append(capaDeps, capaEtq);

    window.MAPA_PERU.departamentos.forEach(d => {
        nombres[d.codigo] = d.nombre;
        const zona = ZONA_DE[d.codigo];
        const g = crearSvg("g", {
            class: "dep", "data-dep": d.codigo, tabindex: "0", role: "button",
            style: `--c:${zona.c};--t:${zona.t};--m:${zona.m}`,
        });
        g.appendChild(crearSvg("path", { d: d.d }));
        capaDeps.appendChild(g);

        const fuera = ETIQUETA_FUERA[d.codigo];
        const pos = ETIQUETA_POS[d.codigo] || { x: d.lx, y: d.ly };
        if (fuera) {
            capaEtq.appendChild(crearSvg("line", { x1: d.lx, y1: d.ly, x2: fuera.x + 14, y2: fuera.y - 3, class: "guia" }));
        }
        const x = fuera ? fuera.x : pos.x;
        const t = crearSvg("text", { x, y: fuera ? fuera.y : pos.y, class: `etq${fuera ? " fuera" : ""}`, "data-etq": d.codigo });
        const linea = crearSvg("tspan", { x, dy: "0" });
        linea.textContent = d.nombre;
        const cifra = crearSvg("tspan", { x, dy: "11", class: "cifra" });
        t.append(linea, cifra);
        capaEtq.appendChild(t);
    });

    capaDeps.addEventListener("click", e => {
        const g = e.target.closest(".dep");
        if (g) alternar(g.dataset.dep);
    });
    capaDeps.addEventListener("keydown", e => {
        const g = e.target.closest(".dep");
        if (g && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); alternar(g.dataset.dep); }
    });
    capaDeps.addEventListener("mousemove", moverTooltip);
    capaDeps.addEventListener("mouseleave", () => $("tooltip").classList.add("hidden"));
    capaDeps.addEventListener("focusin", e => {
        const g = e.target.closest(".dep");
        if (!g) return;
        const caja = g.getBoundingClientRect(), wrap = $("mapaWrap").getBoundingClientRect();
        pintarTooltip(g.dataset.dep, caja.left + caja.width / 2 - wrap.left, caja.top - wrap.top);
    });
    capaDeps.addEventListener("focusout", () => $("tooltip").classList.add("hidden"));
}

function pintarMapa() {
    document.querySelectorAll("#capaDeps .dep").forEach(g => {
        const dep = g.dataset.dep;
        const est = estadoDep(dep);
        const sel = estado.seleccion.has(dep);
        g.classList.toggle("restringido", est === "restringido");
        g.classList.toggle("programado", est === "programado");
        g.classList.toggle("sel", sel);
        g.setAttribute("aria-pressed", sel ? "true" : "false");
        g.setAttribute("aria-label", `${nombreDep(dep)}${est === "restringido" ? ", restringido" : est === "programado" ? ", programado" : ""}${sel ? ", seleccionado" : ""}`);
        if (sel) g.parentNode.appendChild(g);   // el elegido queda encima de sus vecinos al levantarse
    });
    document.querySelectorAll("#capaEtq .etq").forEach(t => {
        const dep = t.dataset.etq;
        t.classList.toggle("sel", estado.seleccion.has(dep));
        const cifra = t.querySelector(".cifra");
        let n = null;
        if (estado.simulacion && estado.seleccion.has(dep)) n = estado.simulacion.porDep[dep] || 0;
        else if (estadoDep(dep) === "restringido") n = clientesDep(dep);
        cifra.textContent = n === null || n === undefined ? "" : num(n);
    });
}

function moverTooltip(e) {
    const g = e.target.closest(".dep");
    if (!g) { $("tooltip").classList.add("hidden"); return; }
    const wrap = $("mapaWrap").getBoundingClientRect();
    pintarTooltip(g.dataset.dep, e.clientX - wrap.left, e.clientY - wrap.top);
}

function pintarTooltip(dep, x, y) {
    const tip = $("tooltip");
    const zona = ZONA_DE[dep];
    const act = activasDe(dep);
    let estadoHtml = `<div class="zt-estado">Se gestiona con normalidad.</div>`;
    if (act.length) {
        estadoHtml = act.map(z => {
            const clase = z.Estado === "VIGENTE" ? "zt-rojo" : "zt-ambar";
            const titulo = z.Estado === "VIGENTE" ? "Restringido" : `Programado desde ${fecha(z.Desde)}`;
            const n = clientesZona(z.IdZona);
            const np = metricaZona(z.IdZona, "ClientesPdp");
            return `<div class="zt-estado"><span class="${clase}">${titulo}</span> · ${z.Origen === "BANCO" ? "orden del banco" : "decisión interna"}<br>
                ${esc(alcanceTexto(z))}${z.Estado === "VIGENTE" && n !== null ? ` · <b>${num(n)}</b> clientes fuera` : ""}
                ${z.Estado === "VIGENTE" && np ? `<br><span style="color:#cbc3fa">${num(np)} con PDP vigente · ${soles(metricaZona(z.IdZona, "MontoPdp"))}</span>` : ""}</div>`;
        }).join("");
    }
    const sel = estado.seleccion.has(dep);
    tip.innerHTML = `<b>${esc(nombreDep(dep))}</b><span class="zt-zona" style="background:${zona.t}">${esc(zona.nombre)}</span>
        ${estadoHtml}<div class="zt-ayuda">${sel ? "Seleccionado · clic para quitarlo" : "Clic para seleccionarlo"}</div>`;
    tip.classList.remove("hidden");
    const ancho = $("mapaWrap").clientWidth;
    tip.style.left = `${Math.min(Math.max(x, 110), ancho - 110)}px`;
    tip.style.top = `${Math.max(y, 90)}px`;
}

// ------------------------------------------------------------------ selección
function alternar(dep) {
    if (estado.seleccion.has(dep)) estado.seleccion.delete(dep);
    else estado.seleccion.add(dep);
    cambioSeleccion();
}

function alternarZona(clave) {
    const deps = clave === "pais" ? Object.keys(ZONA_DE) : ZONAS.find(z => z.clave === clave).deps;
    const todos = deps.every(d => estado.seleccion.has(d));
    deps.forEach(d => todos ? estado.seleccion.delete(d) : estado.seleccion.add(d));
    cambioSeleccion();
}

function cambioSeleccion() {
    estado.simulacion = null;
    $("simulacion").classList.add("hidden");
    pintarMapa();
    pintarChips();
    pintarPanel();
    const tip = $("tooltip");
    if (!tip.classList.contains("hidden")) {
        const hover = document.querySelector("#capaDeps .dep:hover");
        if (hover) {
            const r = hover.getBoundingClientRect(), w = $("mapaWrap").getBoundingClientRect();
            pintarTooltip(hover.dataset.dep, parseFloat(tip.style.left) || r.left - w.left, parseFloat(tip.style.top) || r.top - w.top);
        }
    }
}

function pintarChips() {
    const chip = (clave, nombre, c, t, deps) => {
        const n = deps.filter(d => estado.seleccion.has(d)).length;
        const clase = n === deps.length ? "completo" : n ? "parcial" : "";
        return `<button type="button" class="zr-chip ${clave === "pais" ? "pais" : ""} ${clase}" data-zona="${clave}"
                    style="--c:${c};--t:${t}" aria-pressed="${n === deps.length}">
                    <i></i>${esc(nombre)} <b>${n}/${deps.length}</b></button>`;
    };
    $("chipsZonas").innerHTML = ZONAS.map(z => chip(z.clave, z.nombre, z.c, z.t, z.deps)).join("")
        + chip("pais", "Todo el Perú", "#12243a", "#e8edf3", Object.keys(ZONA_DE));
}

function ordenSeleccion() {
    const orden = Object.keys(ZONA_DE);
    return [...estado.seleccion].sort((a, b) => orden.indexOf(a) - orden.indexOf(b));
}

// ------------------------------------------------------------------ panel
function modoActual() {
    const r = document.querySelector('input[name="modo"]:checked');
    return r ? r.value : "restringir";
}

function cambiarModo(modo) {
    const r = document.querySelector(`input[name="modo"][value="${modo}"]`);
    if (r && !r.disabled) r.checked = true;
    pintarPanel();
}

function alcanceElegido() {
    const todas = document.querySelector('input[name="alcance"]:checked').value === "todas";
    const carteras = todas ? [] : [...document.querySelectorAll("#listaCarteras input:checked")].map(i => Number(i.value));
    return { todas, carteras };
}

function pintarCarteras() {
    $("listaCarteras").innerHTML = estado.carteras.map(c => `
        <label class="zr-cartera" title="${esc(c.Nombre)}">
            <input type="checkbox" value="${c.IdCartera}">
            <span>${c.IdCartera} · ${esc(c.Nombre)}</span>
            ${c.TieneDepartamento ? "" : "<em>sin dpto.</em>"}
        </label>`).join("") || `<p class="zr-nota">No hay carteras en el generador.</p>`;
}

function pintarPanel() {
    const deps = ordenSeleccion();
    $("cuentaSel").textContent = deps.length;
    $("btnLimpiar").disabled = !deps.length;
    $("seleccion").innerHTML = deps.length ? deps.map(d => {
        const est = estadoDep(d);
        const zona = ZONA_DE[d];
        return `<span class="zr-sel-chip ${est === "restringido" ? "restringido" : ""}" style="--c:${zona.c}">
            ${esc(nombreDep(d))}${est === "restringido" ? "<small>restringido</small>" : est === "programado" ? "<small>programado</small>" : ""}
            <button type="button" data-quitar="${esc(d)}" aria-label="Quitar ${esc(nombreDep(d))}">×</button></span>`;
    }).join("") : `<p class="zr-vacio-sel">Elige departamentos en el mapa o una zona completa arriba del mapa.</p>`;

    const { todas, carteras } = alcanceElegido();
    const alcanceOk = todas || carteras.length > 0;
    $("btnSimular").disabled = !deps.length || !alcanceOk;
    $("btnRestringir").disabled = !estado.puedeEditar || !deps.length || !alcanceOk;
    $("btnRestringir").textContent = deps.length
        ? `Restringir ${deps.length} departamento${deps.length > 1 ? "s" : ""}` : "Restringir";

    // Un formulario a la vez: Restringir o Levantar (Levantar solo para quien puede editar).
    const radioLevantar = document.querySelector('input[name="modo"][value="levantar"]');
    radioLevantar.disabled = !estado.puedeEditar;
    if (radioLevantar.disabled && radioLevantar.checked) document.querySelector('input[name="modo"][value="restringir"]').checked = true;
    const modo = modoActual();
    $("bloqueRestringir").classList.toggle("hidden", modo !== "restringir");
    $("bloqueLevantar").classList.toggle("hidden", modo !== "levantar");

    const conRestriccion = deps.filter(d => activasDe(d).length);
    const ids = conRestriccion.flatMap(d => activasDe(d).map(z => z.IdZona));
    const libres = deps.filter(d => !activasDe(d).length);
    const plural = n => n > 1 ? `${n} restricciones` : `${n} restricción`;
    const hayRestringidos = Object.keys(ZONA_DE).some(d => activasDe(d).length);
    $("btnElegirRestringidos").classList.toggle("hidden", !hayRestringidos);
    $("btnLevantar").disabled = !estado.puedeEditar || !ids.length;
    $("btnLevantar").textContent = ids.length ? `Levantar ${plural(ids.length)}` : "Levantar";
    $("textoLevantar").innerHTML = !hayRestringidos
        ? "No hay restricciones activas para levantar."
        : !ids.length
            ? "Elige en el mapa los departamentos restringidos (rayados) que quieres liberar."
            : `<b>${esc(conRestriccion.map(nombreDep).join(", "))}</b>: ${plural(ids.length)} activa${ids.length > 1 ? "s" : ""}. Al levantarla${ids.length > 1 ? "s" : ""}, sus clientes vuelven a las bases desde la próxima consulta del generador.`
              + (libres.length ? `<br><span class="zr-nota">No tienen restricción y se ignoran: ${esc(libres.map(nombreDep).join(", "))}.</span>` : "");
    $("bloqueRestringir").querySelectorAll("textarea, select, input").forEach(el => { el.disabled = !estado.puedeEditar && el.type !== "radio" && el.type !== "checkbox"; });
}

// ------------------------------------------------------------------ KPIs y tablas
function pintarKpis() {
    const vigentes = zonasActivas().filter(z => z.Estado === "VIGENTE");
    const programadas = zonasActivas().filter(z => z.Estado === "PROGRAMADA");
    const depsVig = new Set(vigentes.map(z => z.Departamento));
    $("kpiDeps").textContent = num(depsVig.size);
    $("kpiDepsNota").textContent = depsVig.size
        ? [...depsVig].map(nombreDep).join(", ") + (programadas.length ? ` · ${programadas.length} programada(s)` : "")
        : (programadas.length ? `${programadas.length} programada(s)` : "Ninguno");

    if (estado.excluidos) {
        const pc = estado.excluidos.por_cartera;
        const suma = campo => pc.reduce((s, r) => s + Number(r[campo] || 0), 0);
        $("kpiPdp").textContent = num(suma("ClientesPdp"));
        $("kpiPdpNota").textContent = suma("ClientesPdp")
            ? `${soles(suma("MontoPdp"))} · ${num(suma("ClientesPdpHoy"))} vencen hoy · ${num(suma("ClientesPdp7Dias"))} en 7 días`
            : "Ninguno";
        const total = suma("Clientes");
        $("kpiClientes").textContent = num(total);
        $("kpiClientesNota").textContent = "sumados por cartera";
        const alcanzadas = estado.excluidos.por_cartera.filter(r => Number(r.Clientes) > 0);
        $("kpiCarteras").textContent = num(alcanzadas.length);
        $("kpiCarterasNota").textContent = alcanzadas.map(r => `${r.IdCartera}: ${num(r.Clientes)}`).join(" · ") || "Ninguna";
    }
    const sinCampo = estado.carteras.filter(c => !c.TieneDepartamento);
    if (!estado.cobertura) {
        $("kpiSinDep").textContent = num(sinCampo.length);
        $("kpiSinDepNota").textContent = sinCampo.length ? `${sinCampo.map(c => c.IdCartera).join(", ")} sin el campo · calculando el resto…` : "calculando…";
    } else {
        const revisar = estado.carteras.map(c => coberturaDe(c.IdCartera)).filter(k => k.nivel !== "ok");
        $("kpiSinDep").textContent = num(revisar.length);
        const sc = revisar.filter(k => k.nivel === "sincampo"), inc = revisar.filter(k => k.nivel !== "sincampo");
        $("kpiSinDepNota").textContent = revisar.length
            ? [sc.length ? `${sc.length} sin el campo (${sc.map(k => k.cartera.IdCartera).join(", ")})` : "",
               inc.length ? `${inc.length} incompleta${inc.length > 1 ? "s" : ""} (${inc.map(k => `${k.cartera.IdCartera}: ${pct(k.share)}`).join(", ")})` : ""]
                .filter(Boolean).join(" · ")
            : "Todas las carteras tienen el departamento completo";
    }
}

// Aviso arriba del mapa: la restricción vigente no alcanza a todos porque falta el departamento.
function pintarAlerta() {
    const caja = $("alertaCobertura");
    const alcanzadas = carterasAlcanzadas();
    if (!alcanzadas.length) { caja.classList.add("hidden"); return; }
    const huecos = alcanzadas.map(coberturaDe).filter(k => k.cartera && k.nivel !== "ok");
    if (!huecos.length) { caja.classList.add("hidden"); return; }
    const deps = [...new Set(zonasActivas().filter(z => z.Estado === "VIGENTE").map(z => nombreDep(z.Departamento)))].join(", ");
    const sinCampo = huecos.filter(k => k.nivel === "sincampo");
    const parciales = huecos.filter(k => k.nivel !== "sincampo" && k.clientes !== null);
    const clientesSinCampo = sinCampo.reduce((t, k) => t + (k.clientes || 0), 0);
    const lineas = (sinCampo.length ? `<li><b>Sin departamento cargado:</b> ${sinCampo.map(k => `${k.cartera.IdCartera} ${esc(k.cartera.Nombre)}`).join(", ")}${clientesSinCampo ? ` (${num(clientesSinCampo)} clientes en la base)` : ""}: ninguno de sus clientes sale.</li>` : "")
        + parciales.map(k => `<li><b>${k.cartera.IdCartera} ${esc(k.cartera.Nombre)}</b>: ${num(k.fuera)} clientes (${pct(1 - k.share)}) sin departamento reconocido${k.noRec ? `, de ellos ${num(k.noRec)} con un valor que no se reconoce` : ""}.</li>`).join("");
    const grave = huecos.some(k => k.nivel === "sincampo" || k.nivel === "incompleta");
    caja.className = `zr-alerta${grave ? " roja" : ""}`;
    caja.innerHTML = `<span class="ic">!</span><div>La restricción de <b>${esc(deps)}</b> no alcanza a todos los clientes:
        si alguno vive ahí y no tiene el departamento, <b>se seguirá gestionando</b>.<ul>${lineas}</ul></div>
        <button type="button" class="zr-btn sm" data-ir="cardCarteras">Ver carteras</button>`;
}

function pintarCarterasTabla() {
    const tbody = $("tbodyCarteras");
    if (!estado.carteras.length) { tbody.innerHTML = `<tr><td colspan="10" class="zr-vacio">No hay carteras en el generador.</td></tr>`; return; }
    const exc = id => estado.excluidos ? estado.excluidos.por_cartera.find(r => Number(r.IdCartera) === id) : null;
    tbody.innerHTML = estado.carteras.map(c => {
        const k = coberturaDe(c.IdCartera);
        const e = exc(c.IdCartera);
        const cob = k.clientes === null
            ? (c.TieneDepartamento ? `<span class="zr-nota">calculando…</span>` : "")
            : `<div class="zr-cob ${k.nivel}"><span class="barra"><i style="width:${Math.round((k.share || 0) * 100)}%"></i></span><b>${k.share === null ? "—" : pct(k.share)}</b></div>`;
        const fueraTxt = estado.excluidos ? num(e ? e.Clientes : 0) : "…";
        return `<tr>
            <td><b>${c.IdCartera}</b> · ${esc(c.Nombre)}</td>
            <td><span class="zr-semaforo ${k.nivel}">${ETIQUETA_NIVEL[k.nivel]}</span></td>
            <td class="num">${k.clientes === null ? "…" : num(k.clientes)}</td>
            <td>${c.TieneDepartamento ? cob : `<span class="zr-nota">No cargado en el generador</span>`}</td>
            <td class="num">${c.TieneDepartamento ? (k.sin === null ? "…" : num(k.sin)) : "—"}</td>
            <td class="num">${c.TieneDepartamento ? (k.noRec === null ? "…" : num(k.noRec)) : "—"}</td>
            <td class="num">${fueraTxt}</td>
            <td class="num">${e && e.ClientesPdp ? `<span class="zr-pdp">${num(e.ClientesPdp)}</span>` : (estado.excluidos ? "0" : "…")}</td>
            <td class="num">${e && e.MontoPdp ? soles(e.MontoPdp) : "—"}</td>
            <td><button type="button" class="zr-btn sm" data-excel="${c.IdCartera}" title="Clientes fuera, PDP y clientes sin departamento de esta cartera">Excel</button></td>
        </tr>`;
    }).join("");

    const nr = estado.cobertura ? estado.cobertura.no_reconocidos : [];
    $("detNoReconocidos").classList.toggle("hidden", !nr.length);
    $("cuentaNoRec").textContent = `(${nr.length})`;
    $("tbodyNoRec").innerHTML = nr.map(v => `<tr><td>${esc(nombreCartera(v.IdCartera))}</td><td><code>${esc(v.Valor)}</code></td><td class="num">${num(v.Clientes)}</td></tr>`).join("");
}

function pintarTablas() {
    const activas = zonasActivas().concat(estado.zonas.filter(z => z.Activo && z.Estado === "VENCIDA"));
    $("tbodyActivas").innerHTML = activas.length ? activas.map(z => {
        const zona = ZONA_DE[z.Departamento];
        const n = z.Estado === "VIGENTE" ? clientesZona(z.IdZona) : null;
        return `<tr>
            <td><span class="dep-nombre" data-ver="${esc(z.Departamento)}" title="Seleccionar en el mapa"><i style="background:${zona ? zona.c : "#8a99ab"}"></i>${esc(nombreDep(z.Departamento))}</span></td>
            <td>${esc(zona ? zona.nombre : "—")}</td>
            <td><span class="zr-estado ${z.Estado.toLowerCase()}">${esc(z.Estado)}</span></td>
            <td>${z.AplicaTodas ? `<span class="zr-todas">Todas</span>` : esc(alcanceTexto(z))}</td>
            <td>${z.Origen === "BANCO" ? "Banco" : "Interno"}</td>
            <td class="motivo">${esc(z.Motivo)}</td>
            <td>${fecha(z.Desde)}</td>
            <td>${z.Hasta ? fecha(z.Hasta) : "Hasta levantarla"}</td>
            <td class="num">${n === null ? (z.Estado === "VIGENTE" ? "…" : "—") : num(n)}</td>
            <td class="num">${n === null ? (z.Estado === "VIGENTE" ? "…" : "—") : (metricaZona(z.IdZona, "ClientesPdp") ? `<span class="zr-pdp">${num(metricaZona(z.IdZona, "ClientesPdp"))}</span><br><small class="zr-nota">${soles(metricaZona(z.IdZona, "MontoPdp"))}</small>` : "0")}</td>
            <td>${esc(z.UsuarioRegistro)}<br><small class="zr-nota">${fecha(z.FechaRegistro)}</small></td>
            <td>${estado.puedeEditar ? `<button type="button" class="zr-btn sm link" data-levantar="${z.IdZona}">Levantar</button>` : ""}</td>
        </tr>`;
    }).join("") : `<tr><td colspan="12" class="zr-vacio">No hay restricciones activas: se gestiona todo el país.</td></tr>`;

    const hist = estado.zonas.filter(z => !z.Activo);
    $("cuentaHist").textContent = `(${hist.length})`;
    $("tbodyHistorial").innerHTML = hist.length ? hist.map(z => `<tr>
            <td><b>${esc(nombreDep(z.Departamento))}</b></td>
            <td>${z.AplicaTodas ? "Todas" : esc(alcanceTexto(z))}</td>
            <td>${z.Origen === "BANCO" ? "Banco" : "Interno"}</td>
            <td class="motivo">${esc(z.Motivo)}</td>
            <td>${fecha(z.Desde)}</td>
            <td>${fecha(z.FechaBaja)}</td>
            <td>${esc(z.UsuarioBaja || "")}</td>
            <td class="motivo">${esc(z.MotivoBaja || "")}</td>
        </tr>`).join("") : `<tr><td colspan="8" class="zr-vacio">Sin restricciones levantadas.</td></tr>`;
}

function pintarTodo() {
    pintarMapa();
    pintarChips();
    pintarPanel();
    pintarKpis();
    pintarAlerta();
    pintarCarterasTabla();
    pintarTablas();
}

// ------------------------------------------------------------------ datos
async function cargarEstado() {
    const r = await pedir(`${API}/estado`);
    estado.zonas = r.zonas || [];
    estado.carteras = r.carteras || [];
    estado.puedeEditar = !!r.puede_editar;
    $("soloLectura").classList.toggle("hidden", estado.puedeEditar);
    pintarCarteras();
    pintarTodo();
}

async function cargarExcluidos() {
    $("kpiClientesNota").textContent = "calculando…";
    try {
        estado.excluidos = await pedir(`${API}/excluidos`);
    } catch (error) {
        estado.excluidos = null;
        $("kpiClientesNota").textContent = "no se pudo calcular";
        throw error;
    }
    pintarTodo();
}

async function cargarCobertura(refrescar = false) {
    try {
        estado.cobertura = await pedir(`${API}/cobertura${refrescar ? "?refrescar=1" : ""}`);
        const hora = estado.cobertura.calculado_en;
        const fechaCalculo = hora ? new Date(hora) : null;
        $("horaCobertura").textContent = fechaCalculo && !Number.isNaN(fechaCalculo.getTime())
            ? `calculado ${fechaCalculo.toLocaleTimeString("es-PE", { hour: "2-digit", minute: "2-digit" })}` : "";
    } catch (error) {
        estado.cobertura = null;
        $("horaCobertura").textContent = "";
        $("kpiSinDepNota").textContent = "no se pudo calcular";
        throw error;
    }
    pintarTodo();
}

async function recargar() {
    await cargarEstado();
    cargarExcluidos().catch(manejarError);
    if (!estado.cobertura) cargarCobertura().catch(manejarError);
}

async function descargarExcel(idcartera) {
    const url = `${API}/excel${idcartera ? `?idcartera=${idcartera}` : ""}`;
    const hoy = hoyIso().replace(/-/g, "");
    await descargarArchivoConSesion(url, `zonas_restringidas_${hoy}${idcartera ? `_${idcartera}` : ""}.xlsx`);
}

// ------------------------------------------------------------------ acciones
async function simular() {
    const deps = ordenSeleccion();
    const { todas, carteras } = alcanceElegido();
    const { data } = await pedir(`${API}/simular`, { json: { departamentos: deps, todas, carteras } });
    const porDep = {}, porCartera = {};
    const totalPdp = (data || []).reduce((s, f) => s + Number(f.ClientesPdp || 0), 0);
    const montoPdp = (data || []).reduce((s, f) => s + Number(f.MontoPdp || 0), 0);
    (data || []).forEach(f => {
        porDep[f.Departamento] = (porDep[f.Departamento] || 0) + Number(f.Clientes);
        (porCartera[f.IdCartera] = porCartera[f.IdCartera] || []).push(f);
    });
    estado.simulacion = { porDep, filas: data || [] };
    const total = Object.values(porDep).reduce((s, n) => s + n, 0);
    const alcanzables = todas ? estado.carteras : estado.carteras.filter(c => carteras.includes(c.IdCartera));
    const sinDep = alcanzables.filter(c => !c.TieneDepartamento);
    const filas = Object.entries(porCartera).sort((a, b) => Number(a[0]) - Number(b[0])).map(([id, fs]) => {
        const n = fs.reduce((s, f) => s + Number(f.Clientes), 0);
        const np = fs.reduce((s, f) => s + Number(f.ClientesPdp || 0), 0);
        const mp = fs.reduce((s, f) => s + Number(f.MontoPdp || 0), 0);
        const detalle = fs.sort((a, b) => b.Clientes - a.Clientes).map(f => `${nombreDep(f.Departamento)} ${num(f.Clientes)}`).join(" · ");
        const k = coberturaDe(id);
        const hueco = k.clientes !== null && k.fuera ? `<small class="gap">+ ${num(k.fuera)} clientes de la cartera sin departamento: si viven ahí, no salen</small>` : "";
        return `<div class="zr-sim-fila"><span>${esc(nombreCartera(id))}<small>${esc(detalle)}</small>
            ${np ? `<small class="zr-pdp">${num(np)} con PDP vigente · ${soles(mp)}</small>` : ""}${hueco}</span><b>${num(n)}</b></div>`;
    }).join("");
    const caja = $("simulacion");
    caja.innerHTML = `
        <h5>Clientes que saldrían de las bases</h5>
        <div class="zr-sim-total">${num(total)}</div>
        ${totalPdp ? `<div class="zr-sim-pdp">${num(totalPdp)} tienen PDP vigente por ${soles(montoPdp)}: si se restringe, no se les hará seguimiento.</div>` : ""}
        <small class="zr-nota">Sumados por cartera, según el departamento de la asignación. Incluye a los que ya están fuera por una restricción activa.</small>
        ${filas || `<p class="zr-nota">Ninguna de las carteras elegidas tiene clientes en esos departamentos.</p>`}
        ${sinDep.length ? `<div class="zr-sim-aviso">Sin departamento cargado: ${sinDep.map(c => esc(`${c.IdCartera} ${c.Nombre}`)).join(", ")}. Sus clientes de estas zonas <b>seguirán en las bases</b> hasta cargar la ubicación${todas ? " (con «Todas» entrarán solas cuando se cargue)" : ""}.</div>` : ""}`;
    caja.classList.remove("hidden");
    pintarMapa();
}

async function restringir() {
    const deps = ordenSeleccion();
    const { todas, carteras } = alcanceElegido();
    const motivo = $("txtMotivo").value.trim();
    if (motivo.length < 5) {
        $("txtMotivo").focus();
        throw new Error("Escribe el motivo (por ejemplo, la orden del banco y su fecha).");
    }
    const desde = $("txtDesde").value || hoyIso();
    const hasta = $("txtHasta").value || null;
    const alcance = todas ? "todas las carteras" : `las carteras ${carteras.join(", ")}`;
    const ok = await crmConfirm({
        title: `Restringir ${deps.length} departamento${deps.length > 1 ? "s" : ""}`,
        message: `${deps.map(nombreDep).join(", ")}: se dejará de gestionar a sus clientes en ${alcance} desde el ${fecha(desde)}${hasta ? ` hasta el ${fecha(hasta)}` : ""}. El generador de bases los quitará desde la próxima consulta.`,
        acceptText: "Restringir",
        tone: "danger",
    });
    if (!ok) return;
    const { data } = await pedir(API, { json: {
        departamentos: deps, todas, carteras, origen: $("selOrigen").value, motivo, desde, hasta } });
    const nuevas = data.filter(r => r.Accion === "NUEVA").map(r => nombreDep(r.Departamento));
    const ampliadas = data.filter(r => r.Accion === "AMPLIADA").map(r => nombreDep(r.Departamento));
    const iguales = data.filter(r => r.Accion === "SIN CAMBIO").map(r => nombreDep(r.Departamento));
    const partes = [];
    if (nuevas.length) partes.push(`Restringido: ${nuevas.join(", ")}.`);
    if (ampliadas.length) partes.push(`Ya estaba restringido y se amplió a las carteras elegidas: ${ampliadas.join(", ")}.`);
    if (iguales.length) partes.push(`Sin cambios (ya aplicaba a esas carteras): ${iguales.join(", ")}.`);
    if (ampliadas.length || iguales.length) partes.push("Las que ya tenían restricción conservan sus fechas y su motivo.");
    estado.seleccion.clear();
    $("txtMotivo").value = "";
    $("txtHasta").value = "";
    await recargar();
    mostrarMensaje(partes.join(" "), "ok");
}

async function levantar(ids, nombresDeps) {
    const motivo = $("txtMotivoBaja").value.trim();
    if (motivo.length < 5) {
        cambiarModo("levantar");
        $("txtMotivoBaja").focus();
        throw new Error("Escribe por qué se levanta la restricción.");
    }
    const ok = await crmConfirm({
        title: "Levantar restricción",
        message: `${nombresDeps.join(", ")}: sus clientes vuelven a las bases desde la próxima consulta del generador.`,
        acceptText: "Levantar",
        tone: "primary",
    });
    if (!ok) return;
    const r = await pedir(`${API}/levantar`, { json: { ids, motivo } });
    estado.seleccion.clear();
    $("txtMotivoBaja").value = "";
    await recargar();
    mostrarMensaje(`Restricción levantada (${r.levantadas}): ${nombresDeps.join(", ")}.`, "ok");
}

function levantarSeleccion() {
    const deps = ordenSeleccion().filter(d => activasDe(d).length);
    const ids = deps.flatMap(d => activasDe(d).map(z => z.IdZona));
    return levantar(ids, deps.map(nombreDep));
}

// ------------------------------------------------------------------ eventos
function enlazarEventos() {
    $("chipsZonas").addEventListener("click", e => {
        const b = e.target.closest("[data-zona]");
        if (b) alternarZona(b.dataset.zona);
    });
    $("seleccion").addEventListener("click", e => {
        const b = e.target.closest("[data-quitar]");
        if (b) alternar(b.dataset.quitar);
    });
    $("btnLimpiar").addEventListener("click", () => { estado.seleccion.clear(); cambioSeleccion(); });
    document.querySelectorAll('input[name="alcance"]').forEach(r => r.addEventListener("change", () => {
        $("listaCarteras").classList.toggle("hidden", alcanceElegido().todas);
        estado.simulacion = null;
        $("simulacion").classList.add("hidden");
        pintarMapa();
        pintarPanel();
    }));
    $("listaCarteras").addEventListener("change", () => {
        estado.simulacion = null;
        $("simulacion").classList.add("hidden");
        pintarMapa();
        pintarPanel();
    });
    $("btnSimular").addEventListener("click", e => conBoton(e.currentTarget, simular).catch(manejarError));
    $("btnRestringir").addEventListener("click", e => conBoton(e.currentTarget, restringir).catch(manejarError));
    $("btnLevantar").addEventListener("click", e => conBoton(e.currentTarget, levantarSeleccion).catch(manejarError));
    $("btnRefrescar").addEventListener("click", e => conBoton(e.currentTarget, recargar).catch(manejarError));
    document.querySelectorAll('input[name="modo"]').forEach(r => r.addEventListener("change", () => pintarPanel()));
    $("btnElegirRestringidos").addEventListener("click", () => {
        Object.keys(ZONA_DE).filter(d => activasDe(d).length).forEach(d => estado.seleccion.add(d));
        cambioSeleccion();
    });
    $("btnExcel").addEventListener("click", e => conBoton(e.currentTarget, () => descargarExcel(null)).catch(manejarError));
    $("btnRecalcularCobertura").addEventListener("click", e => conBoton(e.currentTarget, () => cargarCobertura(true)).catch(manejarError));
    $("tbodyCarteras").addEventListener("click", e => {
        const b = e.target.closest("[data-excel]");
        if (b) conBoton(b, () => descargarExcel(Number(b.dataset.excel))).catch(manejarError);
    });
    $("alertaCobertura").addEventListener("click", e => {
        const b = e.target.closest("[data-ir]");
        if (b) $(b.dataset.ir).scrollIntoView({ block: "start", behavior: "smooth" });
    });
    $("tbodyActivas").addEventListener("click", e => {
        const ver = e.target.closest("[data-ver]");
        if (ver) {
            estado.seleccion.add(ver.dataset.ver);
            cambioSeleccion();
            $("mapaWrap").scrollIntoView({ block: "nearest", behavior: "smooth" });
            return;
        }
        const b = e.target.closest("[data-levantar]");
        if (!b) return;
        const z = estado.zonas.find(x => x.IdZona === Number(b.dataset.levantar));
        if (!z) return;
        estado.seleccion.clear();
        estado.seleccion.add(z.Departamento);
        cambioSeleccion();
        cambiarModo("levantar");
        if ($("txtMotivoBaja").value.trim().length < 5) {
            $("bloqueLevantar").scrollIntoView({ block: "center", behavior: "smooth" });
            $("txtMotivoBaja").focus();
            mostrarMensaje(`Escribe el motivo y pulsa «Levantar» para ${nombreDep(z.Departamento)}.`, "");
            return;
        }
        conBoton(b, () => levantar([z.IdZona], [nombreDep(z.Departamento)])).catch(manejarError);
    });
}

document.addEventListener("DOMContentLoaded", async () => {
    const sesionOk = typeof asegurarSesionBackend === "function" && await asegurarSesionBackend();
    if (!sesionOk) return;
    $("txtDesde").value = hoyIso();
    dibujarMapa();
    pintarChips();
    pintarPanel();
    enlazarEventos();
    try {
        await cargarEstado();
    } catch (error) {
        manejarError(error);
        return;
    }
    cargarExcluidos().catch(manejarError);
    cargarCobertura().catch(manejarError);
});
