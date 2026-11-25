// frontend/js/generador_bases.js
// Generador de bases: elige cartera, arma la receta (filtros + condiciones del día), consulta,
// genera la base (se registra con su código) y descarga el archivo.
// Todo el permiso real está en el backend (/generador-bases/*): esta vista solo muestra.

const BASE_URL = `${location.protocol}//${location.hostname}:8000`;
const API = `${BASE_URL}/generador-bases`;
const TAMANO_PAGINA = 50;
const SIN_DATO = "SIN_DATO";
const ORIGENES_FILTRABLES = new Set(["TRABAJO", "DATO"]);
const NOMBRE_GRUPO = {
    SCORE: "Score", TELEFONO: "Teléfono", CLIENTE: "Cliente", GESTION_CLIENTE: "Gestión del cliente",
    SEGMENTO_BANCO: "Segmentos del banco", SEGMENTO_PROPIO: "Segmentos propios", CONDICION_DIA: "Condiciones del día",
};

const estado = {
    carteras: [],
    idcartera: null,
    catalogo: null,          // respuesta de /catalogo
    campos: new Map(),       // Codigo -> campo
    filtros: new Map(),      // Codigo -> filtro de la receta
    condiciones: {},         // Codigo -> QUITAR | SOLO
    campoActivo: null,
    pagina: 1,
    ultimaConsulta: null,    // respuesta de /consulta
    recetaConsultada: null,  // JSON de la receta con que se consultó
    ocupado: false,
};

const $ = id => document.getElementById(id);

// ------------------------------------------------------------------ utilidades
function esc(valor) {
    return String(valor ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function num(valor, decimales = 0) {
    if (valor === null || valor === undefined || valor === "") return "—";
    const n = Number(valor);
    if (!Number.isFinite(n)) return esc(valor);
    return n.toLocaleString("es-PE", { minimumFractionDigits: decimales, maximumFractionDigits: decimales });
}

function fechaHora(valor) {
    if (!valor) return "—";
    const d = new Date(valor);
    if (Number.isNaN(d.getTime())) return esc(valor);
    return d.toLocaleString("es-PE", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

function fecha(valor) {
    if (!valor) return "—";
    const texto = String(valor).slice(0, 10);
    const [a, m, d] = texto.split("-");
    return a && m && d ? `${d}/${m}/${a}` : esc(valor);
}

function textoValor(valor) {
    if (valor === SIN_DATO) return "Sin dato";
    if (valor === "1" || valor === "True" || valor === "true") return "Sí";
    if (valor === "0" || valor === "False" || valor === "false") return "No";
    if (valor === "PQ") return "Plomo (P/Q)";
    return valor;
}

function mostrarMensaje(texto, tipo = "") {
    const caja = $("mensaje");
    if (!texto) { caja.classList.add("hidden"); return; }
    caja.className = `gb-mensaje ${tipo}`;
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

function postJson(url, cuerpo) {
    return pedir(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(cuerpo) });
}

function manejarError(error) {
    if (error instanceof SesionInvalidaError) return;   // session.js ya redirige
    console.error(error);
    mostrarMensaje(error.message || "Ocurrió un error.", "error");
}

async function conBoton(boton, tarea) {
    if (boton.classList.contains("is-busy")) return;
    const texto = boton.innerHTML;
    boton.classList.add("is-busy");
    boton.disabled = true;
    try {
        return await tarea();
    } finally {
        boton.classList.remove("is-busy");
        boton.disabled = false;
        boton.innerHTML = texto;
        actualizarBotonGenerar();
    }
}

// ------------------------------------------------------------------ receta
function receta() {
    const porCliente = $("txtPorCliente").value.trim();
    return {
        idcartera: estado.idcartera,
        canal: $("selCanal").value || null,
        filtros: [...estado.filtros.values()],
        condiciones: { ...estado.condiciones },
        telefonos_por_cliente: porCliente ? Number(porCliente) : null,
    };
}

// Lo que cambia el resultado: el canal solo cuenta si se usa "ya enviado hoy (mismo canal)".
function recetaClave() {
    const r = receta();
    if (!r.condiciones.ENVIADO_HOY) delete r.canal;
    return JSON.stringify(r);
}

function recetaCambio() {
    renderChips();
    actualizarBotonGenerar();
}

function actualizarBotonGenerar() {
    const consulta = estado.ultimaConsulta;
    const vigente = consulta && estado.recetaConsultada === recetaClave();
    const telefonos = Number(consulta?.totales?.Telefonos || 0);
    const boton = $("btnGenerar");
    boton.disabled = !vigente || telefonos === 0;
    boton.title = !consulta ? "Primero consulta la base"
        : !vigente ? "Cambiaste la receta: vuelve a consultar"
            : telefonos === 0 ? "La consulta no tiene teléfonos" : "";
}

function describirFiltro(filtro) {
    const campo = estado.campos.get(filtro.campo);
    const nombre = campo?.Etiqueta || filtro.campo;
    let detalle = "";
    if (filtro.valores) detalle = filtro.valores.map(textoValor).join(", ");
    else if (filtro.min !== undefined || filtro.max !== undefined) {
        detalle = [filtro.min !== undefined ? `≥ ${num(filtro.min, 2).replace(/,00$/, "")}` : "",
            filtro.max !== undefined ? `≤ ${num(filtro.max, 2).replace(/,00$/, "")}` : ""].filter(Boolean).join(" y ");
    } else if (filtro.desde || filtro.hasta) {
        detalle = [filtro.desde ? `desde ${fecha(filtro.desde)}` : "", filtro.hasta ? `hasta ${fecha(filtro.hasta)}` : ""].filter(Boolean).join(" ");
    } else if (filtro.texto) detalle = `contiene “${filtro.texto}”`;
    return `${filtro.excluir ? "Sin " : ""}${nombre}: ${detalle}`;
}

function renderChips() {
    const chips = [];
    for (const filtro of estado.filtros.values()) {
        const texto = describirFiltro(filtro);
        chips.push(`<span class="gb-chip ${filtro.excluir ? "excluir" : ""}" title="${esc(texto)}"><span>${esc(texto)}</span>
            <button type="button" data-quitar-filtro="${esc(filtro.campo)}" aria-label="Quitar filtro">×</button></span>`);
    }
    const condiciones = estado.catalogo?.condiciones || [];
    for (const [codigo, modo] of Object.entries(estado.condiciones)) {
        const meta = condiciones.find(c => c.Codigo === codigo);
        const texto = `${modo === "QUITAR" ? "Sin" : "Solo"} ${(meta?.etiqueta || codigo).toLowerCase()}`;
        chips.push(`<span class="gb-chip cond" title="${esc(meta?.descripcion || "")}"><span>${esc(texto)}</span>
            <button type="button" data-quitar-condicion="${esc(codigo)}" aria-label="Quitar condición">×</button></span>`);
    }
    $("chips").innerHTML = chips.length ? chips.join("") : `<span class="gb-vacio" style="padding:0">Sin filtros: entran todos los teléfonos no descartados de la cartera.</span>`;
    $("cntFiltros").textContent = estado.filtros.size;
    $("cntCondiciones").textContent = Object.keys(estado.condiciones).length;
}

// ------------------------------------------------------------------ carteras
async function cargarCarteras(idPreferida) {
    const { data } = await pedir(`${API}/carteras`);
    estado.carteras = data || [];
    const select = $("selCartera");
    if (!estado.carteras.length) {
        select.innerHTML = `<option value="">Sin carteras disponibles</option>`;
        $("estadoCartera").textContent = "No tienes carteras con tabla de trabajo armada.";
        $("btnActualizar").disabled = true;
        $("btnConsultar").disabled = true;
        return;
    }
    select.innerHTML = estado.carteras
        .map(c => `<option value="${c.IdCartera}">${esc(c.IdCartera)} · ${esc(c.Nombre)}</option>`).join("");
    const guardada = idPreferida || Number(localStorage.getItem("gb_idcartera"));
    if (estado.carteras.some(c => Number(c.IdCartera) === guardada)) select.value = String(guardada);
    await elegirCartera(Number(select.value));
}

function renderEstadoCartera() {
    const c = estado.carteras.find(x => Number(x.IdCartera) === estado.idcartera);
    if (!c) { $("estadoCartera").textContent = "—"; return; }
    const partes = [
        `<span>Actualizada: <strong>${fechaHora(c.UltimaActualizacion)}</strong>${c.UsuarioActualizacion ? ` (${esc(c.OrigenActualizacion || "")} ${esc(c.UsuarioActualizacion)})` : ""}</span>`,
        `<span>Historial hasta: <strong>${fecha(c.HistorialHasta)}</strong></span>`,
        `<span>Corte cliente: <strong>${fecha(c.FechaCorteFuente)}</strong></span>`,
        `<span>Clientes: <strong>${num(c.ClientesUniverso)}</strong></span>`,
        `<span>Teléfonos con score: <strong>${num(c.Telefonos)}</strong></span>`,
        c.Version ? `<span>Score v${esc(c.Version)}</span>` : "",
    ];
    if (c.EnCurso) partes.unshift(`<span class="gb-en-curso">Actualizándose ahora…</span>`);
    if (c.Aviso) partes.push(`<span class="gb-aviso" title="${esc(c.Aviso)}">⚠ ${esc(String(c.Aviso).slice(0, 120))}</span>`);
    $("estadoCartera").innerHTML = partes.filter(Boolean).join("");
}

async function elegirCartera(idcartera) {
    estado.idcartera = idcartera;
    localStorage.setItem("gb_idcartera", String(idcartera));
    estado.filtros.clear();
    estado.condiciones = {};
    estado.campoActivo = null;
    estado.ultimaConsulta = null;
    estado.recetaConsultada = null;
    $("panelResultado").classList.add("hidden");
    mostrarMensaje("");
    renderEstadoCartera();

    estado.catalogo = await pedir(`${API}/catalogo?idcartera=${encodeURIComponent(idcartera)}`);
    estado.campos = new Map((estado.catalogo.campos || []).map(c => [c.Codigo, c]));

    const canalPrevio = $("selCanal").value;
    $("selCanal").innerHTML = `<option value="">Elegir canal…</option>` + Object.entries(estado.catalogo.canales || {})
        .map(([codigo, nombre]) => `<option value="${esc(codigo)}">${esc(nombre)}</option>`).join("");
    if (canalPrevio && estado.catalogo.canales?.[canalPrevio]) $("selCanal").value = canalPrevio;

    renderCondiciones();
    recetaCambio();
    cargarHistorico();
}

async function actualizarCartera() {
    const c = estado.carteras.find(x => Number(x.IdCartera) === estado.idcartera);
    if (!c) return;
    const ok = confirm(`Actualizar ${c.IdCartera} · ${c.Nombre}\n\nRecalcula historial, score y datos del cliente. `
        + "Puede tardar uno o varios minutos; mientras tanto la cartera no se puede volver a actualizar.\n\n¿Continuar?");
    if (!ok) return;
    const boton = $("btnActualizar");
    await conBoton(boton, async () => {
        boton.textContent = "Actualizando…";
        mostrarMensaje("Actualizando la cartera. No cierres la página.", "aviso");
        try {
            const r = await postJson(`${API}/actualizar/${estado.idcartera}`, {});
            if (r.ocupada) {
                mostrarMensaje(r.mensaje || "La cartera ya se está actualizando.", "aviso");
            } else if (r.ok) {
                const seg = r.detalle?.Segundos;
                const aviso = r.detalle?.Aviso ? ` Aviso: ${r.detalle.Aviso}` : "";
                mostrarMensaje(`Cartera actualizada${seg ? ` en ${num(seg)} s` : ""}.${aviso} Vuelve a consultar para ver los datos nuevos.`, aviso ? "aviso" : "ok");
            } else {
                const det = r.detalle || {};
                mostrarMensaje(`La actualización terminó con estado ${det.Estado || "desconocido"}. ${det.Error || det.Aviso || ""}`.trim(), "error");
            }
            const filtros = new Map(estado.filtros), condiciones = { ...estado.condiciones };
            const { data } = await pedir(`${API}/carteras`);
            estado.carteras = data || [];
            renderEstadoCartera();
            // el catálogo (valores y conteos) puede cambiar; la receta se conserva
            estado.catalogo = await pedir(`${API}/catalogo?idcartera=${estado.idcartera}`);
            estado.campos = new Map((estado.catalogo.campos || []).map(x => [x.Codigo, x]));
            estado.filtros = filtros;
            estado.condiciones = condiciones;
            estado.recetaConsultada = null;
            recetaCambio();
        } catch (error) {
            manejarError(error);
        }
    });
}

// ------------------------------------------------------------------ consulta
async function consultar(pagina = 1) {
    if (!estado.idcartera) return;
    const boton = $("btnConsultar");
    await conBoton(boton, async () => {
        boton.textContent = "Consultando…";
        try {
            const cuerpo = { ...receta(), pagina, tamano: TAMANO_PAGINA };
            const r = await postJson(`${API}/consulta`, cuerpo);
            estado.ultimaConsulta = r;
            estado.recetaConsultada = recetaClave();
            estado.pagina = pagina;
            mostrarMensaje("");
            renderResultado();
        } catch (error) {
            manejarError(error);
        }
    });
}

function renderResultado() {
    const r = estado.ultimaConsulta;
    const t = r.totales || {};
    $("panelResultado").classList.remove("hidden");
    $("kpiClientes").textContent = num(t.Clientes);
    $("kpiTelefonos").textContent = num(t.Telefonos);
    $("kpiCapital").textContent = num(t.Capital);
    $("kpiScore").textContent = num(t.ScorePromedio, 1);

    const total = Number(t.Telefonos || 0);
    $("kpiTramos").innerHTML = total ? ["A", "B", "C", "D", "E"].map(tr => {
        const n = Number(t[`Tramo${tr}`] || 0);
        const pct = n / total * 100;
        return n ? `<div class="gb-tramo-${tr}" style="width:${pct}%" title="Tramo ${tr}: ${num(n)} teléfonos (${pct.toFixed(1)}%)">${pct >= 8 ? tr : ""}</div>` : "";
    }).join("") : "";

    renderEmbudo(r.embudo || []);
    renderFilas(r.filas || [], total);
}

function renderEmbudo(pasos) {
    if (!pasos.length) { $("embudo").innerHTML = `<p class="gb-vacio">Sin datos.</p>`; return; }
    const base = Number(pasos[0].telefonos) || 1;
    $("embudo").innerHTML = pasos.map((p, i) => {
        const tel = Number(p.telefonos || 0);
        const previo = i > 0 ? Number(pasos[i - 1].telefonos || 0) : null;
        const baja = previo !== null ? previo - tel : 0;
        return `<div class="gb-paso">
            <div class="gb-paso-top"><span>${esc(p.paso)}</span><strong>${num(tel)}</strong></div>
            <div class="gb-paso-bar"><div style="width:${Math.max(0, tel / base * 100)}%"></div></div>
            <small>${num(p.clientes)} clientes${baja > 0 ? ` · <span class="gb-baja">−${num(baja)} tel.</span>` : ""}</small>
        </div>`;
    }).join("");
}

const COLOR_HEX = { V: "#1f9d55", A: "#e3b13b", R: "#c84646", P: "#9aa5b1", Q: "#9aa5b1", N: "#334155" };

function renderFilas(filas, total) {
    const tbody = $("tbodyFilas");
    if (!filas.length) {
        tbody.innerHTML = `<tr><td colspan="13" class="gb-vacio">Ningún teléfono cumple la receta.</td></tr>`;
    } else {
        tbody.innerHTML = filas.map(f => {
            const razones = [f.Razon1, f.Razon2, f.Razon3].filter(Boolean).map(esc).join(" · ")
                + (f.Razon_Resta ? ` <span class="gb-baja">(resta: ${esc(f.Razon_Resta)})</span>` : "");
            const color = f.PrioridadColor ? `<span class="gb-color" style="background:${COLOR_HEX[f.PrioridadColor] || "#cbd5e1"}"></span>${esc(f.PrioridadColor)}` : "—";
            return `<tr>
                <td class="num">${num(f.Posicion)}</td>
                <td>${esc(f.DNI)}</td>
                <td>${esc(f.Telefono)}</td>
                <td class="num">${num(f.OrdenEnBase)}</td>
                <td class="num">${num(f.Score)}</td>
                <td>${f.Tramo ? `<span class="gb-tag gb-tramo-${esc(f.Tramo)}">${esc(f.Tramo)}</span>` : "—"}</td>
                <td>${color}</td>
                <td>${f.Whatsapp === null || f.Whatsapp === undefined ? "—" : (f.Whatsapp ? "Sí" : "No")}</td>
                <td>${f.Osiptel === null || f.Osiptel === undefined ? "—" : (f.Osiptel ? "Sí" : "No")}</td>
                <td>${esc(f.Operador || "—")}</td>
                <td class="num">${num(f.Capital, 2)}</td>
                <td>${esc(f.RangoCapital || "—")}</td>
                <td class="razones">${razones || "—"}</td>
            </tr>`;
        }).join("");
    }
    const desde = total ? (estado.pagina - 1) * TAMANO_PAGINA + 1 : 0;
    const hasta = Math.min(total, estado.pagina * TAMANO_PAGINA);
    $("infoPagina").textContent = total ? `${num(desde)}–${num(hasta)} de ${num(total)} · orden de salida (score desc.)` : "0 teléfonos";
    $("btnAnterior").disabled = estado.pagina <= 1;
    $("btnSiguiente").disabled = hasta >= total;
}

// ------------------------------------------------------------------ modal filtros
function abrirModal(id) { $(id).classList.remove("hidden"); }
function cerrarModal(id) { $(id).classList.add("hidden"); }

function renderListaCampos() {
    const busqueda = $("txtBuscarCampo").value.trim().toLowerCase();
    const grupos = new Map();
    for (const campo of estado.campos.values()) {
        if (campo.Origen === "DIA" || campo.Grupo === "CONDICION_DIA") continue;
        const texto = `${campo.Etiqueta} ${campo.Codigo} ${campo.Descripcion || ""}`.toLowerCase();
        if (busqueda && !texto.includes(busqueda)) continue;
        if (!grupos.has(campo.Grupo)) grupos.set(campo.Grupo, []);
        grupos.get(campo.Grupo).push(campo);
    }
    if (!grupos.size) { $("listaCampos").innerHTML = `<p class="gb-vacio">Ningún campo coincide.</p>`; return; }
    $("listaCampos").innerHTML = [...grupos.entries()].map(([grupo, campos]) => `
        <div class="gb-grupo-titulo">${esc(NOMBRE_GRUPO[grupo] || grupo)}</div>
        ${campos.map(c => `<button type="button" class="gb-campo-item ${c.Codigo === estado.campoActivo ? "activo" : ""}" data-campo="${esc(c.Codigo)}"
            ${ORIGENES_FILTRABLES.has(c.Origen) ? "" : 'title="Todavía no se puede filtrar en el generador"'}>
            <span>${esc(c.Etiqueta)}${ORIGENES_FILTRABLES.has(c.Origen) ? "" : " <small>(próx.)</small>"}</span>
            ${estado.filtros.has(c.Codigo) ? '<span class="punto"></span>' : ""}
        </button>`).join("")}`).join("");
}

function diccionario(campo) {
    const lineas = [];
    if (campo.Descripcion) lineas.push(`<div>${esc(campo.Descripcion)}</div>`);
    if (campo.Nivel === "CUENTA") lineas.push(`<div><strong>Nivel cuenta:</strong> entra el cliente si alguna de sus cuentas cumple.</div>`);
    const fuente = campo.Tabla ? `${campo.Tabla}${campo.Columna ? "." + campo.Columna : ""}` : campo.Fuente;
    if (fuente) lineas.push(`<div><strong>Fuente:</strong> ${esc(fuente)}</div>`);
    if (campo.Actualizacion) lineas.push(`<div><strong>Actualización:</strong> ${esc(campo.Actualizacion)}</div>`);
    if (campo.FechaFuente) lineas.push(`<div><strong>Fecha del dato:</strong> ${fecha(campo.FechaFuente)}</div>`);
    if (campo.ValoresTruncados) lineas.push(`<div class="gb-aviso">Se muestran los valores más frecuentes; la lista está recortada.</div>`);
    return lineas.length ? `<div class="gb-dicc">${lineas.join("")}</div>` : "";
}

function renderEditor() {
    const editor = $("editorCampo");
    const campo = estado.campos.get(estado.campoActivo);
    if (!campo) { editor.innerHTML = `<p class="gb-vacio">Elige un campo de la izquierda.</p>`; return; }
    const actual = estado.filtros.get(campo.Codigo) || {};
    let cuerpo = "";

    if (!ORIGENES_FILTRABLES.has(campo.Origen)) {
        cuerpo = `<p class="gb-vacio">Este campo todavía no se puede usar como filtro en el generador.</p>`;
    } else if (campo.TipoFiltro === "LISTA" || campo.TipoFiltro === "SINO") {
        const valores = [...(campo.Valores || [])];
        // Campos guardados como filas: el "sin dato" no viene en la lista (es la ausencia de fila)
        if (campo.Origen === "DATO" && !valores.some(v => v.valor === SIN_DATO)) valores.push({ valor: SIN_DATO });
        const marcados = new Set(actual.valores || []);
        cuerpo = `
            ${valores.length > 12 ? `<input id="txtBuscarValor" class="gb-input" type="search" placeholder="Buscar valor…" style="margin-bottom:8px">` : ""}
            <div class="gb-editor-acciones" style="margin:0 0 6px"><span class="gb-check">
                <button type="button" class="gb-btn secondary sm" id="btnTodosValores">Marcar visibles</button>
                <button type="button" class="gb-btn secondary sm" id="btnNingunValor">Desmarcar</button></span>
                <small class="gb-vacio" style="padding:0">${valores.some(v => v.clientes !== undefined) ? "clientes" : valores.some(v => v.telefonos !== undefined) ? "teléfonos" : ""}</small>
            </div>
            <div class="gb-valores" id="listaValores">
                ${valores.length ? valores.map(v => `<label class="gb-valor" data-texto="${esc(String(textoValor(v.valor)).toLowerCase())}">
                    <input type="checkbox" value="${esc(v.valor)}" ${marcados.has(v.valor) ? "checked" : ""}>
                    <span>${esc(textoValor(v.valor))}</span>
                    <small>${v.clientes !== undefined ? num(v.clientes) : v.telefonos !== undefined ? num(v.telefonos) : ""}</small>
                </label>`).join("") : `<p class="gb-vacio">Sin valores cargados para esta cartera.</p>`}
            </div>`;
    } else if (campo.TipoFiltro === "RANGO") {
        cuerpo = `<div class="gb-rango">
            <div><label class="gb-label" for="txtMin">Mínimo</label><input id="txtMin" class="gb-input" type="number" step="any" value="${esc(actual.min ?? "")}"></div>
            <div><label class="gb-label" for="txtMax">Máximo</label><input id="txtMax" class="gb-input" type="number" step="any" value="${esc(actual.max ?? "")}"></div>
        </div>`;
    } else if (campo.TipoFiltro === "FECHA") {
        cuerpo = `<div class="gb-rango">
            <div><label class="gb-label" for="txtDesde">Desde</label><input id="txtDesde" class="gb-input" type="date" value="${esc(actual.desde ?? "")}"></div>
            <div><label class="gb-label" for="txtHasta">Hasta</label><input id="txtHasta" class="gb-input" type="date" value="${esc(actual.hasta ?? "")}"></div>
        </div>`;
    } else if (campo.TipoFiltro === "TEXTO") {
        cuerpo = `<label class="gb-label" for="txtTexto">Contiene</label><input id="txtTexto" class="gb-input" value="${esc(actual.texto ?? "")}">`;
    } else {
        cuerpo = `<p class="gb-vacio">Tipo de filtro no soportado: ${esc(campo.TipoFiltro)}.</p>`;
    }

    const filtrable = ORIGENES_FILTRABLES.has(campo.Origen);
    editor.innerHTML = `
        <h4>${esc(campo.Etiqueta)}</h4>
        ${diccionario(campo)}
        ${cuerpo}
        ${filtrable ? `<div class="gb-editor-acciones">
            <label class="gb-check" title="Saca a quienes cumplen; los que no tienen dato se quedan">
                <input type="checkbox" id="chkExcluir" ${actual.excluir ? "checked" : ""}> Excluir (sin ${esc(campo.Etiqueta.toLowerCase())})</label>
            <span style="display:flex;gap:8px">
                ${estado.filtros.has(campo.Codigo) ? `<button type="button" class="gb-btn secondary" id="btnQuitarFiltro">Quitar filtro</button>` : ""}
                <button type="button" class="gb-btn primary" id="btnAplicarFiltro">Aplicar</button>
            </span>
        </div>` : ""}`;
}

function aplicarFiltro() {
    const campo = estado.campos.get(estado.campoActivo);
    if (!campo) return;
    const filtro = { campo: campo.Codigo };
    if (campo.TipoFiltro === "LISTA" || campo.TipoFiltro === "SINO") {
        const valores = [...document.querySelectorAll("#listaValores input:checked")].map(i => i.value);
        if (!valores.length) { alert("Marca al menos un valor."); return; }
        filtro.valores = valores;
    } else if (campo.TipoFiltro === "RANGO") {
        const min = $("txtMin").value.trim(), max = $("txtMax").value.trim();
        if (!min && !max) { alert("Indica un mínimo o un máximo."); return; }
        if (min) filtro.min = Number(min);
        if (max) filtro.max = Number(max);
        if (min && max && filtro.min > filtro.max) { alert("El mínimo es mayor que el máximo."); return; }
    } else if (campo.TipoFiltro === "FECHA") {
        const desde = $("txtDesde").value, hasta = $("txtHasta").value;
        if (!desde && !hasta) { alert("Indica desde o hasta."); return; }
        if (desde) filtro.desde = desde;
        if (hasta) filtro.hasta = hasta;
    } else if (campo.TipoFiltro === "TEXTO") {
        const texto = $("txtTexto").value.trim();
        if (!texto) { alert("Escribe un texto."); return; }
        filtro.texto = texto;
    }
    if ($("chkExcluir")?.checked) filtro.excluir = true;
    estado.filtros.set(campo.Codigo, filtro);
    recetaCambio();
    renderListaCampos();
    renderEditor();
}

function quitarFiltro(codigo) {
    estado.filtros.delete(codigo);
    recetaCambio();
    if (!$("modalFiltros").classList.contains("hidden")) { renderListaCampos(); renderEditor(); }
}

// ------------------------------------------------------------------ condiciones del día
function renderCondiciones() {
    const lista = estado.catalogo?.condiciones || [];
    $("listaCondiciones").innerHTML = lista.map(c => {
        const modo = estado.condiciones[c.Codigo] || "INDIFERENTE";
        const boton = (m, texto) => `<button type="button" data-condicion="${esc(c.Codigo)}" data-modo="${m}"
            class="${modo === m ? "activo" : ""} ${m === "QUITAR" ? "quitar" : ""}">${texto}</button>`;
        return `<div class="gb-condicion">
            <div><strong>${esc(c.etiqueta)}</strong><small>${esc(c.descripcion)}${c.Codigo === "ENVIADO_HOY" ? " Requiere elegir canal." : ""}</small></div>
            <div class="gb-segmento">${boton("QUITAR", "Quitar")}${boton("SOLO", "Solo")}${boton("INDIFERENTE", "Indiferente")}</div>
        </div>`;
    }).join("");
}

function cambiarCondicion(codigo, modo) {
    if (modo === "INDIFERENTE") delete estado.condiciones[codigo];
    else estado.condiciones[codigo] = modo;
    renderCondiciones();
    recetaCambio();
}

// ------------------------------------------------------------------ generar
function abrirGenerar() {
    const r = estado.ultimaConsulta;
    if (!r) return;
    if (!$("selCanal").value) {
        mostrarMensaje("Elige el canal antes de generar la base.", "aviso");
        $("selCanal").focus();
        return;
    }
    const t = r.totales || {};
    $("resumenGenerar").innerHTML = `
        <div>Clientes<strong>${num(t.Clientes)}</strong></div>
        <div>Teléfonos<strong>${num(t.Telefonos)}</strong></div>
        <div>Canal<strong>${esc($("selCanal").selectedOptions[0]?.textContent || "")}</strong></div>`;
    $("resultadoGenerar").classList.add("hidden");
    $("btnConfirmarGenerar").classList.remove("hidden");
    abrirModal("modalGenerar");
}

async function generar() {
    const boton = $("btnConfirmarGenerar");
    await conBoton(boton, async () => {
        boton.textContent = "Generando…";
        try {
            const cuerpo = { ...receta(), descripcion: $("txtDescripcion").value.trim() || null };
            const base = await postJson(`${API}/generar`, cuerpo);
            const caja = $("resultadoGenerar");
            caja.innerHTML = `Base <strong>${esc(base.Codigo)}</strong> registrada: ${num(base.Clientes)} clientes, ${num(base.Telefonos)} teléfonos.<br>${esc(base.NombreArchivo)}.xlsx`;
            caja.classList.remove("hidden");
            boton.classList.add("hidden");
            $("txtDescripcion").value = "";
            cargarHistorico();
            try {
                await descargarArchivoConSesion(`${API}/bases/${base.IdBase}/archivo`, `${base.NombreArchivo}.xlsx`);
            } catch (error) {
                if (!(error instanceof SesionInvalidaError)) {
                    caja.innerHTML += `<br>La base quedó registrada, pero la descarga falló: ${esc(error.message)}. Descárgala desde el histórico.`;
                }
            }
            if (Number(base.Telefonos) !== Number(estado.ultimaConsulta?.totales?.Telefonos)) {
                caja.innerHTML += `<br><small>La cantidad difiere de la consulta: las condiciones del día se evalúan en vivo al generar.</small>`;
            }
        } catch (error) {
            if (error instanceof SesionInvalidaError) return;
            const caja = $("resultadoGenerar");
            caja.style.background = "#fdeeee";
            caja.style.color = "#8a1f1f";
            caja.textContent = error.message || "No se pudo generar la base.";
            caja.classList.remove("hidden");
        }
    });
}

// ------------------------------------------------------------------ histórico
async function cargarHistorico() {
    const tbody = $("tbodyHistorico");
    try {
        const filtro = estado.idcartera ? `?idcartera=${estado.idcartera}&dias=30` : "?dias=30";
        const { data } = await pedir(`${API}/bases${filtro}`);
        const canales = estado.catalogo?.canales || {};
        tbody.innerHTML = (data || []).length ? data.map(b => `<tr>
            <td><strong>${esc(b.Codigo)}</strong></td>
            <td title="${esc(b.Descripcion || "")}">${esc(b.NombreArchivo)}</td>
            <td>${esc(canales[b.Canal] || b.Canal)}</td>
            <td>${fechaHora(b.FechaGeneracion)}</td>
            <td>${esc(b.Usuario)}</td>
            <td class="num">${num(b.Clientes)}</td>
            <td class="num">${num(b.Telefonos)}</td>
            <td class="num">${num(b.Capital)}</td>
            <td><button type="button" class="gb-btn secondary sm" data-descargar="${esc(b.IdBase)}" data-nombre="${esc(b.NombreArchivo)}">Descargar</button></td>
        </tr>`).join("") : `<tr><td colspan="9" class="gb-vacio">Todavía no hay bases generadas para esta cartera.</td></tr>`;
    } catch (error) {
        if (error instanceof SesionInvalidaError) return;
        tbody.innerHTML = `<tr><td colspan="9" class="gb-vacio">${esc(error.message)}</td></tr>`;
    }
}

// ------------------------------------------------------------------ eventos
function enlazarEventos() {
    $("selCartera").addEventListener("change", e => elegirCartera(Number(e.target.value)).catch(manejarError));
    $("btnActualizar").addEventListener("click", actualizarCartera);
    $("selCanal").addEventListener("change", recetaCambio);
    $("txtPorCliente").addEventListener("input", recetaCambio);
    $("btnConsultar").addEventListener("click", () => consultar(1));
    $("btnAnterior").addEventListener("click", () => consultarPagina(estado.pagina - 1));
    $("btnSiguiente").addEventListener("click", () => consultarPagina(estado.pagina + 1));
    $("btnGenerar").addEventListener("click", abrirGenerar);
    $("btnConfirmarGenerar").addEventListener("click", generar);
    $("btnRecargarHistorico").addEventListener("click", cargarHistorico);

    $("btnFiltros").addEventListener("click", () => {
        $("txtBuscarCampo").value = "";
        renderListaCampos();
        renderEditor();
        abrirModal("modalFiltros");
        $("txtBuscarCampo").focus();
    });
    $("btnCondiciones").addEventListener("click", () => { renderCondiciones(); abrirModal("modalCondiciones"); });
    $("txtBuscarCampo").addEventListener("input", renderListaCampos);
    $("btnQuitarTodos").addEventListener("click", () => {
        estado.filtros.clear();
        recetaCambio();
        renderListaCampos();
        renderEditor();
    });

    $("listaCampos").addEventListener("click", e => {
        const item = e.target.closest("[data-campo]");
        if (!item) return;
        estado.campoActivo = item.dataset.campo;
        renderListaCampos();
        renderEditor();
    });

    $("editorCampo").addEventListener("click", e => {
        if (e.target.id === "btnAplicarFiltro") aplicarFiltro();
        else if (e.target.id === "btnQuitarFiltro") quitarFiltro(estado.campoActivo);
        else if (e.target.id === "btnTodosValores" || e.target.id === "btnNingunValor") {
            const marcar = e.target.id === "btnTodosValores";
            document.querySelectorAll("#listaValores .gb-valor").forEach(l => {
                if (l.style.display !== "none") l.querySelector("input").checked = marcar;
            });
        }
    });
    $("editorCampo").addEventListener("input", e => {
        if (e.target.id !== "txtBuscarValor") return;
        const q = e.target.value.trim().toLowerCase();
        document.querySelectorAll("#listaValores .gb-valor").forEach(l => {
            l.style.display = !q || l.dataset.texto.includes(q) ? "" : "none";
        });
    });

    $("listaCondiciones").addEventListener("click", e => {
        const b = e.target.closest("[data-condicion]");
        if (b) cambiarCondicion(b.dataset.condicion, b.dataset.modo);
    });

    $("chips").addEventListener("click", e => {
        const f = e.target.closest("[data-quitar-filtro]");
        const c = e.target.closest("[data-quitar-condicion]");
        if (f) quitarFiltro(f.dataset.quitarFiltro);
        if (c) cambiarCondicion(c.dataset.quitarCondicion, "INDIFERENTE");
    });

    $("tbodyHistorico").addEventListener("click", e => {
        const b = e.target.closest("[data-descargar]");
        if (!b) return;
        conBoton(b, () => descargarArchivoConSesion(`${API}/bases/${b.dataset.descargar}/archivo`, `${b.dataset.nombre}.xlsx`)
            .catch(manejarError));
    });

    document.addEventListener("click", e => {
        const cerrar = e.target.closest("[data-cerrar]");
        if (cerrar) cerrarModal(cerrar.dataset.cerrar);
        else if (e.target.classList?.contains("gb-modal")) cerrarModal(e.target.id);
    });
    document.addEventListener("keydown", e => {
        if (e.key === "Escape") document.querySelectorAll(".gb-modal:not(.hidden)").forEach(m => cerrarModal(m.id));
    });
}

// Cambiar de página usa la receta consultada; si la receta cambió, se reconsulta desde la página 1.
function consultarPagina(pagina) {
    if (estado.recetaConsultada !== recetaClave()) {
        mostrarMensaje("Cambiaste la receta: se consulta de nuevo desde la primera página.", "aviso");
        return consultar(1);
    }
    return consultar(pagina);
}

document.addEventListener("DOMContentLoaded", async () => {
    if (typeof asegurarSesionBackend !== "function" || !(await asegurarSesionBackend())) return;   // session.js redirige
    enlazarEventos();
    try {
        await cargarCarteras();
    } catch (error) {
        manejarError(error);
    }
});
