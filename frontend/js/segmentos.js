// frontend/js/segmentos.js
// Carga de segmentos del banco (o propios) para el generador de bases.
// Pasos: 1) entidad + archivo → leer columnas; 2) configurar clave, periodo, filtros y columnas;
// 3) vista previa (códigos que no cruzan, conflictos) → cargar. El archivo se vuelve a enviar en cada paso:
// no queda guardado en el servidor. Los permisos reales están en el backend (/segmentos-banco/*).

const BASE_URL = `${location.protocol}//${location.hostname}:8000`;
const API = `${BASE_URL}/segmentos-banco`;
const CLAVES_CODIGO = ["CO_CLIENTE", "COD_CLI", "CODCLIENTE", "COD_CLIENTE", "CODCLIENTEBT", "CTACLIENTE"];
const CLAVES_DNI = ["DNI", "NRO_DOC", "NUMDOC", "NRO_DOCUMENTO", "DOCUMENTO"];
const COLUMNAS_PERIODO = ["PERIODO", "PER_PRO", "CODMES", "MESASIG"];
const COLUMNAS_FILTRO = ["FUNCIONARIO", "USU_FIN", "USU_FIN 2", "USUARIO", "AGENCIA", "PROVEEDOR"];

const estado = { entidades: [], analisis: null, previaClave: null };

const $ = id => document.getElementById(id);
const esc = v => String(v ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const num = v => (v === null || v === undefined || v === "") ? "—" : Number(v).toLocaleString("es-PE");
const norm = t => String(t || "").trim().toUpperCase();

function mostrarMensaje(texto, tipo = "") {
    const caja = $("mensaje");
    if (!texto) { caja.classList.add("hidden"); return; }
    caja.className = `sg-mensaje ${tipo}`;
    caja.textContent = texto;
    caja.scrollIntoView({ block: "nearest", behavior: "smooth" });
}

async function pedir(url, opciones = {}) {
    const response = await fetchConSesion(url, opciones);
    if (!response.ok) {
        const porDefecto = esAccesoDenegado(response)
            ? "Solo administración y jefes de cartera cargan segmentos."
            : "No se pudo completar la operación.";
        throw new Error(await mensajeErrorRespuesta(response, porDefecto));
    }
    return response.json();
}

function manejarError(error) {
    if (error instanceof SesionInvalidaError) return;
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
    }
}

function marcarPaso(n) {
    [1, 2, 3].forEach(i => $(`paso${i}`).classList.toggle("activo", i <= n));
}

// ------------------------------------------------------------------ paso 1
async function cargarEntidades() {
    const { data } = await pedir(`${API}/entidades`);
    estado.entidades = data || [];
    $("selEntidad").innerHTML = estado.entidades.map(e =>
        `<option value="${esc(e.codigo)}">${esc(e.codigo)}</option>`).join("");
    const mibanco = estado.entidades.find(e => e.codigo === "MIBANCO");
    if (mibanco) $("selEntidad").value = "MIBANCO";
    pintarEntidad();
}

function entidadActual() {
    return estado.entidades.find(e => e.codigo === $("selEntidad").value);
}

function pintarEntidad() {
    const e = entidadActual();
    $("carterasEntidad").textContent = e ? `Carteras: ${e.carteras.join(", ") || "ninguna"}` : "";
    const opcion = $("selTipoClave").querySelector('option[value="CODIGO_BANCO"]');
    opcion.disabled = !(e && e.codigo_banco);
    if (opcion.disabled && $("selTipoClave").value === "CODIGO_BANCO") $("selTipoClave").value = "DNI";
    $("notaClave").textContent = e && !e.codigo_banco
        ? "Esta entidad no tiene registrada la tabla para traducir el código del banco a DNI: usa una columna de DNI."
        : "";
    limpiarPrevia();
}

function formulario(extra = {}) {
    const archivo = $("archivo").files[0];
    if (!archivo) throw new Error("Elige el archivo.");
    const datos = new FormData();
    datos.append("archivo", archivo, archivo.name);
    Object.entries(extra).forEach(([k, v]) => { if (v !== null && v !== undefined) datos.append(k, v); });
    return datos;
}

async function leerArchivo(conHoja = true) {
    const hoja = conHoja ? $("selHoja").value : "";
    const r = await pedir(`${API}/analizar`, { method: "POST", body: formulario({ hoja }) });
    estado.analisis = r;
    const sel = $("selHoja");
    sel.innerHTML = (r.hojas || []).map(h => `<option value="${esc(h)}">${esc(h)}</option>`).join("")
        || `<option value="">(CSV)</option>`;
    sel.disabled = !(r.hojas || []).length;
    if (r.hoja) sel.value = r.hoja;
    pintarConfiguracion();
    marcarPaso(2);
    mostrarMensaje("");
}

// ------------------------------------------------------------------ paso 2
function opcionesColumnas(seleccion, conVacio = false) {
    const cols = estado.analisis?.columnas || [];
    return (conVacio ? `<option value="">—</option>` : "")
        + cols.map(c => `<option value="${esc(c.nombre)}" ${c.nombre === seleccion ? "selected" : ""}>${esc(c.nombre)}</option>`).join("");
}

function buscarColumna(lista) {
    const cols = estado.analisis?.columnas || [];
    for (const nombre of lista) {
        const c = cols.find(x => norm(x.nombre) === nombre);
        if (c) return c.nombre;
    }
    return null;
}

function pintarConfiguracion() {
    const a = estado.analisis;
    $("bloqueConfig").classList.remove("hidden");
    $("resumenArchivo").textContent = `${a.archivo}${a.hoja ? ` · hoja ${a.hoja}` : ""}: ${num(a.filas)} filas, ${a.columnas.length} columnas.`;

    const codigo = buscarColumna(CLAVES_CODIGO);
    const dni = buscarColumna(CLAVES_DNI);
    const e = entidadActual();
    const clave = (e?.codigo_banco && codigo) ? codigo : (dni || codigo || a.columnas[0]?.nombre);
    $("selClave").innerHTML = opcionesColumnas(clave);
    $("selTipoClave").value = (clave === codigo && e?.codigo_banco) ? "CODIGO_BANCO" : (clave === dni ? "DNI" : $("selTipoClave").value);

    const periodo = buscarColumna(COLUMNAS_PERIODO);
    $("selPeriodo").innerHTML = `<option value="">Escribirlo (AAAAMM)</option>` + opcionesColumnas(periodo);
    $("selPeriodo").value = periodo || "";
    const hoy = new Date();
    $("txtPeriodo").value = `${hoy.getFullYear()}${String(hoy.getMonth() + 1).padStart(2, "0")}`;
    pintarPeriodo();

    $("filtros").innerHTML = "";
    const colFiltro = buscarColumna(COLUMNAS_FILTRO);
    if (colFiltro) {
        const c = a.columnas.find(x => x.nombre === colFiltro);
        const marcados = (c.valores_filtro || []).filter(v => norm(v).startsWith("BIZNESCOB"));
        agregarFiltro(colFiltro, marcados.length ? marcados : null);
    }
    pintarColumnas();
    limpiarPrevia();
}

function pintarPeriodo() {
    $("txtPeriodo").disabled = !!$("selPeriodo").value;
}

function abreviaturaSugerida(codigo) {
    const partes = codigo.split("_").filter(Boolean);
    let abrev = partes.length > 1 ? partes.map(p => p.slice(0, 3)).join("") : codigo;
    return abrev.replace(/[^A-Z0-9]/g, "").slice(0, 10) || "SEG";
}

function pintarColumnas() {
    const a = estado.analisis;
    const clave = $("selClave").value;
    const quitar = new Set([clave, $("selPeriodo").value, ...[...document.querySelectorAll("[data-filtro-col]")].map(s => s.value)]);
    $("tbodyColumnas").innerHTML = a.columnas.filter(c => !quitar.has(c.nombre)).map(c => {
        const valores = c.valores.slice(0, 6).map(v => `${esc(v.valor)} <small>(${num(v.filas)})</small>`).join(", ");
        const mas = c.distintos > 6 ? ` <small>… ${num(c.distintos)} distintos</small>` : "";
        const pareceFormula = c.valores.some(v => String(v.valor).startsWith("="));
        const pareceNumeroDecimal = c.valores.length && c.valores.every(v => /^0?\.\d+$|^1(\.0+)?$/.test(v.valor));
        return `<tr data-columna="${esc(c.nombre)}">
            <td><input type="checkbox" data-usar aria-label="Cargar ${esc(c.nombre)}"></td>
            <td><strong>${esc(c.nombre)}</strong>${pareceFormula ? `<br><small class="sg-alerta">parece una fórmula</small>` : ""}</td>
            <td class="sg-valores">${valores}${mas}</td>
            <td><input class="sg-input sg-codigo" data-k="campo" value="${esc(c.codigo_sugerido)}" maxlength="60"></td>
            <td><input class="sg-input" data-k="etiqueta" value="${esc(c.nombre)}" maxlength="100"></td>
            <td><input class="sg-input sg-corto" data-k="abreviatura" value="${esc(abreviaturaSugerida(c.codigo_sugerido))}" maxlength="12"></td>
            <td><select class="sg-select" data-k="formato">
                    <option value="TEXTO">Texto</option>
                    <option value="PORCENTAJE" ${pareceNumeroDecimal ? "selected" : ""}>Porcentaje (0.97 → 97%)</option>
                </select></td>
            <td><input class="sg-input" data-k="descripcion" placeholder="Qué significa (opcional)" maxlength="500"></td>
        </tr>`;
    }).join("") || `<tr><td colspan="8" class="sg-vacio">No quedan columnas para cargar.</td></tr>`;
}

function agregarFiltro(columna = null, marcados = null) {
    const a = estado.analisis;
    if (!a) return;
    const caja = document.createElement("div");
    caja.className = "sg-filtro";
    caja.innerHTML = `<select class="sg-select" data-filtro-col>${opcionesColumnas(columna || "", !columna)}</select>
        <div class="sg-filtro-valores"></div>
        <button type="button" class="sg-btn sm" data-quitar-filtro>Quitar</button>`;
    $("filtros").appendChild(caja);
    const sel = caja.querySelector("[data-filtro-col]");
    const pintar = (marcar) => {
        const c = a.columnas.find(x => x.nombre === sel.value);
        const valores = c?.valores_filtro || [];
        caja.querySelector(".sg-filtro-valores").innerHTML = !c ? "<small>Elige una columna.</small>"
            : valores.length ? valores.map(v => `<label class="sg-chip"><input type="checkbox" value="${esc(v)}"
                ${!marcar || marcar.includes(v) ? "checked" : ""}> ${esc(v)}</label>`).join("")
            : "<small>Demasiados valores distintos para filtrar aquí.</small>";
    };
    sel.addEventListener("change", () => { pintar(null); pintarColumnas(); limpiarPrevia(); });
    pintar(marcados);
    pintarColumnas();
}

function definicion() {
    const columnas = [...document.querySelectorAll("#tbodyColumnas tr[data-columna]")]
        .filter(tr => tr.querySelector("[data-usar]").checked)
        .map(tr => {
            const v = k => tr.querySelector(`[data-k="${k}"]`).value.trim();
            return { columna: tr.dataset.columna, campo: v("campo").toUpperCase(), etiqueta: v("etiqueta"),
                     abreviatura: v("abreviatura").toUpperCase(), formato: v("formato"), descripcion: v("descripcion") };
        });
    const filtros = [...document.querySelectorAll(".sg-filtro")].map(f => ({
        columna: f.querySelector("[data-filtro-col]").value,
        valores: [...f.querySelectorAll(".sg-filtro-valores input:checked")].map(i => i.value),
    })).filter(f => f.columna);
    for (const f of filtros) {
        if (!f.valores.length) throw new Error(`El filtro de ${f.columna} no tiene ningún valor marcado.`);
    }
    if (!columnas.length) throw new Error("Marca al menos una columna para cargar.");
    if (!$("txtSegmento").value.trim()) throw new Error("Escribe el nombre del segmento.");
    return {
        entidad: $("selEntidad").value, segmento: $("txtSegmento").value.trim(), fuente: $("selFuente").value,
        hoja: $("selHoja").disabled ? null : $("selHoja").value || null,
        columna_clave: $("selClave").value, tipo_clave: $("selTipoClave").value,
        columna_periodo: $("selPeriodo").value || null, periodo: $("selPeriodo").value ? null : $("txtPeriodo").value.trim(),
        filtros, columnas,
    };
}

// ------------------------------------------------------------------ paso 3
function limpiarPrevia() {
    estado.previaClave = null;
    $("bloquePrevia").classList.add("hidden");
    $("btnCargar").disabled = true;
    if (estado.analisis) marcarPaso(2);
}

async function vistaPrevia() {
    const def = definicion();
    const clave = JSON.stringify(def);
    const r = await pedir(`${API}/previsualizar`, { method: "POST", body: formulario({ definicion: clave }) });
    const bloqueos = (r.errores_catalogo || []).length + Number(r.conflictos || 0);
    $("kpisPrevia").innerHTML = [
        ["Filas del archivo", num(r.filas_archivo)],
        ["Filas después de filtrar", num(r.filas_filtradas)],
        [r.claves === r.clientes ? "Clientes" : "Clientes que cruzan", num(r.clientes)],
        ["Códigos sin cruce", num(r.codigos_sin_cruce)],
        ["En el score", num(r.en_score)],
        ["Conflictos", num(r.conflictos)],
        ["Periodo", esc(r.periodo)],
    ].map(([t, v]) => `<div class="sg-kpi"><small>${t}</small><strong>${v}</strong></div>`).join("");
    const avisos = [];
    (r.errores_catalogo || []).forEach(e => avisos.push(`<div class="sg-mensaje error">${esc(e)}</div>`));
    if (r.conflictos) {
        avisos.push(`<div class="sg-mensaje error">Hay clientes con dos valores distintos en una columna: corrige el archivo
            (o agrega un filtro) antes de cargar. Ejemplos: ${r.ejemplos_conflicto.map(c =>
            `${esc(c.clave)} · ${esc(c.campo)}: ${esc((c.valores || []).join(" / "))}`).join("; ")}</div>`);
    }
    if (r.codigos_sin_cruce) {
        avisos.push(`<div class="sg-mensaje aviso">${num(r.codigos_sin_cruce)} código(s) no están en la asignación vigente
            y quedan fuera. Ejemplos: ${r.ejemplos_sin_cruce.map(esc).join(", ")}</div>`);
    }
    if (r.clientes && Number(r.en_score || 0) < Number(r.clientes)) {
        const detalle = Object.entries(r.por_cartera || {}).map(([c, n]) => `${esc(c)}: ${num(n)}`).join(" · ") || "ninguna";
        const fuera = Number(r.clientes) - Number(r.en_score || 0);
        avisos.push(`<div class="sg-mensaje ${r.en_score ? "aviso" : "error"}">${num(fuera)} de ${num(r.clientes)} cliente(s)
            no están hoy en la base del score de ninguna cartera de ${esc(r.entidad)}: el generador no los mostrará.
            Clientes por cartera: ${detalle}.${r.en_score ? "" : " Revisa que la columna sea la del DNI."}</div>`);
    }
    if (r.sin_clave) avisos.push(`<div class="sg-mensaje aviso">${num(r.sin_clave)} fila(s) sin clave de cliente: quedan fuera.</div>`);
    $("avisosPrevia").innerHTML = avisos.join("");
    $("distribucionPrevia").innerHTML = Object.entries(r.distintos || {}).map(([campo, valores]) => `
        <div class="sg-dist"><h5>${esc(campo)}</h5>
            ${Object.entries(valores).slice(0, 15).map(([v, n]) => `<div><span>${esc(v)}</span><b>${num(n)}</b></div>`).join("")}
            ${Object.keys(valores).length > 15 ? `<small>… ${Object.keys(valores).length} valores</small>` : ""}
        </div>`).join("");
    $("bloquePrevia").classList.remove("hidden");
    estado.previaClave = bloqueos ? null : clave;
    $("btnCargar").disabled = !!bloqueos;
    marcarPaso(3);
    mostrarMensaje(bloqueos ? "" : "Revisa la vista previa y presiona Cargar segmento.", bloqueos ? "" : "ok");
}

async function cargar() {
    const def = definicion();
    const clave = JSON.stringify(def);
    if (clave !== estado.previaClave) {
        limpiarPrevia();
        throw new Error("Cambiaste la configuración: vuelve a hacer la vista previa.");
    }
    const r = await pedir(`${API}/cargar`, { method: "POST", body: formulario({ definicion: clave }) });
    const campos = def.columnas.map(c => `${c.etiqueta} (${c.campo})`).join(", ");
    const carteras = Object.keys(r.por_cartera || {}).join(", ") || "ninguna";
    reiniciarFormulario();
    mostrarMensaje(`Carga ${r.id_carga} hecha: ${num(r.clientes)} clientes, ${num(r.filas_insertadas)} datos. `
        + `En el generador: pestaña Segmento cliente, sección "Segmentos del banco" → ${campos}. `
        + `Carteras con estos clientes en el score: ${carteras}. Si el generador ya estaba abierto, recárgalo.`, "ok");
    cargarHistorial();
}

// Después de cargar: deja la pantalla lista para el siguiente archivo (se mantiene la entidad).
function reiniciarFormulario() {
    estado.analisis = null;
    estado.previaClave = null;
    $("archivo").value = "";
    $("selHoja").innerHTML = `<option value="">Primera hoja</option>`;
    $("selHoja").disabled = true;
    $("txtSegmento").value = "";
    $("filtros").innerHTML = "";
    $("tbodyColumnas").innerHTML = "";
    $("resumenArchivo").textContent = "";
    $("bloqueConfig").classList.add("hidden");
    $("bloquePrevia").classList.add("hidden");
    $("kpisPrevia").innerHTML = "";
    $("avisosPrevia").innerHTML = "";
    $("distribucionPrevia").innerHTML = "";
    $("btnCargar").disabled = true;
    marcarPaso(1);
}

// ------------------------------------------------------------------ historial
async function cargarHistorial() {
    const tbody = $("tbodyCargas");
    try {
        const { data } = await pedir(`${API}/cargas?limite=100`);
        tbody.innerHTML = (data || []).length ? data.map(c => `<tr>
            <td>${esc(c.IdCarga)}</td><td>${esc(c.Entidad)}</td><td><strong>${esc(c.Segmento)}</strong></td>
            <td>${esc(c.Periodo)}</td><td title="${esc(c.Archivo)}">${esc(c.Archivo)}</td>
            <td class="num">${num(c.Campos)}</td><td class="num">${num(c.ClientesCargados)}</td><td class="num">${num(c.CodigosSinCruce)}</td>
            <td><span class="sg-estado ${esc(String(c.Estado).toLowerCase())}">${esc(c.Estado)}</span></td>
            <td>${esc(c.Usuario)}</td><td>${esc(String(c.FechaCarga || "").replace("T", " ").slice(0, 16))}</td>
            <td>${c.Estado === "VIGENTE" ? `<button type="button" class="sg-btn sm" data-anular="${esc(c.IdCarga)}">Anular</button>` : ""}</td>
        </tr>`).join("") : `<tr><td colspan="12" class="sg-vacio">Todavía no hay cargas.</td></tr>`;
    } catch (error) {
        if (error instanceof SesionInvalidaError) return;
        tbody.innerHTML = `<tr><td colspan="12" class="sg-vacio">${esc(error.message)}</td></tr>`;
    }
}

async function anular(boton) {
    if (!window.confirm("¿Anular esta carga? El generador deja de usar estos datos (queda en el historial).")) return;
    await pedir(`${API}/cargas/${boton.dataset.anular}/anular`, { method: "POST" });
    mostrarMensaje(`Carga ${boton.dataset.anular} anulada.`, "ok");
    cargarHistorial();
}

// ------------------------------------------------------------------ eventos
function enlazarEventos() {
    $("selEntidad").addEventListener("change", pintarEntidad);
    $("archivo").addEventListener("change", () => {
        estado.analisis = null;
        $("selHoja").innerHTML = `<option value="">Primera hoja</option>`;
        $("selHoja").disabled = true;
        $("bloqueConfig").classList.add("hidden");
        limpiarPrevia();
        marcarPaso(1);
    });
    $("btnLeer").addEventListener("click", e => conBoton(e.currentTarget, () => leerArchivo(false)).catch(manejarError));
    $("selHoja").addEventListener("change", () => conBoton($("btnLeer"), () => leerArchivo(true)).catch(manejarError));
    $("selClave").addEventListener("change", () => { pintarColumnas(); limpiarPrevia(); });
    $("selPeriodo").addEventListener("change", () => { pintarPeriodo(); pintarColumnas(); limpiarPrevia(); });
    $("btnAgregarFiltro").addEventListener("click", () => agregarFiltro());
    $("filtros").addEventListener("click", e => {
        const b = e.target.closest("[data-quitar-filtro]");
        if (b) { b.closest(".sg-filtro").remove(); pintarColumnas(); limpiarPrevia(); }
    });
    ["bloqueConfig"].forEach(id => $(id).addEventListener("change", e => {
        if (!e.target.closest("#selClave, #selPeriodo, [data-filtro-col]")) limpiarPrevia();
    }));
    $("bloqueConfig").addEventListener("input", () => limpiarPrevia());
    $("btnPrevia").addEventListener("click", e => conBoton(e.currentTarget, vistaPrevia).catch(manejarError));
    $("btnCargar").addEventListener("click", e => conBoton(e.currentTarget, cargar).catch(manejarError));
    $("btnRefrescar").addEventListener("click", cargarHistorial);
    $("tbodyCargas").addEventListener("click", e => {
        const b = e.target.closest("[data-anular]");
        if (b) conBoton(b, () => anular(b)).catch(manejarError);
    });
}

document.addEventListener("DOMContentLoaded", async () => {
    const sesionOk = typeof asegurarSesionBackend === "function" && await asegurarSesionBackend();
    if (!sesionOk) return;
    enlazarEventos();
    try {
        await cargarEntidades();
    } catch (error) {
        manejarError(error);
    }
    cargarHistorial();
});
