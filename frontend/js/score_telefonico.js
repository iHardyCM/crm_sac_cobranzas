// frontend/js/score_telefonico.js
// Score telefónico · generador de bases.
// - Vista central: los teléfonos de la base (top 20/50/100) con tarjetas e impacto por filtro.
// - Filtros: modal casi a pantalla completa, por pestañas (primero el segmento del cliente). Cada filtro
//   es una lista para marcar, como los filtros de Excel: todo marcado al inicio; se desmarcan las
//   excepciones. Rangos y fechas también son listas (tramos fijos / año-mes): nada se escribe a mano.
// - Todo se recalcula solo; los conteos de cada lista tienen en cuenta los demás filtros.
// - Detalle del score: qué significa cada tramo (tasa de contacto medida) y por qué un teléfono tiene su score.
// Los permisos reales están en el backend (/generador-bases/*).

const BASE_URL = `${location.protocol}//${location.hostname}:8000`;
const API = `${BASE_URL}/generador-bases`;
const SIN_DATO = "SIN_DATO";
const ESPERA_CALCULO_MS = 450;
const VALORES_CON_BUSCADOR = 8;
const ORIGENES_FILTRABLES = new Set(["TRABAJO", "DATO"]);
// DESCARTADO: los descartados nunca entran. CAPITAL: se elige por "Rango de capital" (misma escala).
const CAMPOS_OCULTOS = new Set(["DESCARTADO", "CAPITAL"]);
const GRUPOS_SEGMENTO = ["SEGMENTO_BANCO", "SEGMENTO_PROPIO"];
// Tramos propuestos el 15/11/2026, pendientes de confirmar (ver generador_bases_reglas.TRAMOS_RANGO)
const TRAMOS_PROPUESTOS = new Set(["MESES_CASTIGO", "DIAS_MORA", "DIAS_ATRASO", "GESTIONES_HUMANAS_MES",
    "GESTIONES_MAQUINA_MES", "PDP_GENERADAS_MES", "PDP_VIGENTES", "PDP_PENDIENTES", "PDP_EXIGIBLES", "CUENTAS",
    "ORDEN_CLIENTE", "PAGO_ACUMULADO", "PAGO_OFICIAL_ACUMULADO", "PAGO_REGISTRADO_SISCOB", "MONTO_PDP_PAGADO",
    "MONTO_PAGADO_ACUM", "MONTO_PAGADO_MES", "MONTO_SISCOB"]);

// Pestañas del modal de filtros. CONDICION_DIA son las condiciones en vivo (no vienen como campo).
// Un grupo nuevo del catálogo que no esté aquí cae en "Segmento cliente".
const PESTANAS = [
    { clave: "SEGMENTO_CLIENTE", titulo: "Segmento cliente", nota: "Datos del cliente y sus cuentas (cuenta clientes)",
      grupos: ["CLIENTE", "SEGMENTO_BANCO", "SEGMENTO_PROPIO"] },
    { clave: "GESTION_CLIENTE", titulo: "Gestión cliente", nota: "Condiciones de hoy y gestión del mes (cuenta clientes)",
      grupos: ["CONDICION_DIA", "GESTION_CLIENTE"] },
    { clave: "GESTION_TELEFONO", titulo: "Gestión teléfono", nota: "Score, gestión y datos del número (cuenta teléfonos)",
      grupos: ["SCORE", "GESTION_TELEFONO", "TELEFONO"] },
];

// Orden de importancia de cada pestaña (15/11/2026, Hardy: "arriba lo más importante y abajo los complementarios").
// Sigue el orden de los segmentadores de su Excel de MiBanco castigo. Lo que no está aquí va a "Complementarios".
const PRINCIPALES = {
    SEGMENTO_CLIENTE: ["SISCOB_CONDICION", "CONDICION", "PRIORIDAD_BANCO",
        // Segmentos que envía MiBanco aparte (fase 8, 16/11/2026)
        "GESTION_PRIO_MB", "SEG_COBEX_CAST", "SUBSEG_COBEX_CAST", "RANGO_MES_CLASIF_MB", "DSCTO_PREFIERA",
        "SEGMENTO", "SUB_SEGMENTO", "SEGMENTACION", "SEGMENTO_ESTRATEGIA",
        "GRUPO_ASIG", "RANGO_CAPITAL", "RANGO_UIT", "MESES_CASTIGO", "RANGO_MADURACION", "DIAS_MORA", "RANGO_MORA",
        "DIAS_ATRASO", "RANGO_DIAS_ATRASO", "PRODUCTO", "FAMILIA", "TIPO_PRODUCTO", "CUENTAS", "CLUSTER_RFP", "FOGAPI",
        "HIPOTECARIO", "RIESGO_CASTIGO"],
    // 16/11/2026 (fase 7): primero la gestión calculada desde SISCOB, igual para todas las carteras
    GESTION_CLIENTE: ["MG_CONTACTO_MES", "MG_INDICADOR_MES", "MG_FECHA_MES", "UG_CONTACTO_MES", "UG_INDICADOR_MES",
        "UG_FECHA_MES", "COBERTURA_MES", "ESTADO_PDP", "ULTIMO_CEF", "FRECUENCIA_MES", "SEGUIMIENTO_ACTUAL",
        "ESTADO_SEGUIMIENTO", "GESTIONES_HUMANAS_SISCOB", "FRECUENCIA_HUMANA_MES"],
    GESTION_TELEFONO: ["TRAMO", "SCORE", "COLOR", "MG_TEL_MES", "MG_TEL_6M", "UG_TEL_6M", "ULT_GESTION_TEL",
        "GESTIONES_TEL_MES", "GESTIONES_TEL_6M", "EQUIVOCADOS_TEL_6M", "TIMBRA", "WHATSAPP", "OSIPTEL",
        "ORIGEN_DATO", "FUENTE_DATO", "ORDEN_CLIENTE"],
};

const ETIQUETA_RESULTADO = {
    TITULAR: ["Titular", "contacto"], TERCERO_ACUERDO: ["Tercero con acuerdo", "contacto"], TERCERO: ["Tercero", "contacto"],
    FALLECIDO: ["Fallecido", "malo"], CONTESTA_SIN_ID: ["Contesta sin identificar", "medio"], NO_CONTESTA: ["No contesta", "sin"],
    BUZON: ["Buzón", "sin"], APAGADO: ["Apagado", "sin"], SIN_INFORMACION: ["Sin información", "sin"],
    EQUIVOCADO: ["Equivocado", "malo"], NO_EXISTE: ["No existe", "malo"], NO_APLICA: ["No aplica", "sin"],
    SIN_CLASIFICAR: ["Sin clasificar", "sin"],
};

// Características del score (score.Caracteristicas): nombre para mostrar
const CARACTERISTICA = {
    T_ULT_CEF: "Días desde el último contacto directo (CEF)",
    T_ULT_TERCERO: "Días desde el último contacto con un tercero",
    T_TASA_CEF_90: "Tasa de contacto directo en 90 días (CEF ÷ intentos)",
    T_INTENTOS_30: "Intentos en los últimos 30 días",
    T_ULT_INTENTO: "Días desde el último intento",
    T_MAQUINA_90: "Qué pasa cuando no conecta (90 días)",
    S_ORIGEN: "Origen del número",
    S_FUENTE: "Fuente del dato",
    S_ANTIG_DATO: "Antigüedad del dato",
    S_OSIPTEL: "OSIPTEL",
    S_WHATSAPP: "WhatsApp",
    S_TIMBRA: "Timbrado",
    S_TIPO_LINEA: "Tipo de línea",
    S_RELACION: "Relación con el cliente",
    S_COMPARTIDO: "DNI que comparten el número",
};

const estado = {
    carteras: [],
    idcartera: null,
    catalogo: null,
    campos: new Map(),        // Codigo -> campo del catálogo
    desmarcados: new Map(),   // Codigo -> Set de valores desmarcados (como en Excel: todo marcado al inicio)
    condiciones: {},          // Codigo -> QUITAR | SOLO
    segmentadores: null,      // {conteos, clientes} de la última consulta con conteos (o {error})
    segmentadoresClave: null,
    ultima: null,
    recetaConsultada: null,
    calculando: false,
    secuencia: 0,
    temporizador: null,
    enVuelo: false,           // hay una consulta en curso (solo una a la vez)
    pendiente: null,          // cambio que llegó mientras calculaba: se consulta al terminar
    pagina: 1,
    modalAbierto: false,
    pestana: "SEGMENTO_CLIENTE",
    scoreVersion: null,       // caché de /score/version por cartera
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
    const [a, m, d] = String(valor).slice(0, 10).split("-");
    return a && m && d ? `${d}/${m}/${a}` : esc(valor);
}

const MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "set", "oct", "nov", "dic"];

function textoValor(valor, campo) {
    if (valor === SIN_DATO) return "Sin dato";
    if (campo?.TipoFiltro === "SINO") {
        if (valor === "1" || valor === "True" || valor === "true") return "Sí";
        if (valor === "0" || valor === "False" || valor === "false") return "No";
    }
    if (campo?.TipoFiltro === "FECHA" && /^\d{4}-\d{2}$/.test(valor)) {
        const [a, m] = valor.split("-");
        return `${MESES[Number(m) - 1] || m} ${a}`;
    }
    if (valor === "PQ" && campo?.Codigo === "COLOR") return "PQ (plomo)";
    return valor;
}

function pct(parte, total, dec = 1) {
    return total ? `${(parte / total * 100).toFixed(dec)}%` : "—";
}

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

function abrirModal(id) { $(id).classList.remove("hidden"); document.body.classList.add("st-con-modal"); }
function cerrarModal(id) {
    $(id).classList.add("hidden");
    if (!document.querySelector(".st-modal:not(.hidden)")) document.body.classList.remove("st-con-modal");
    if (id === "modalFiltros") estado.modalAbierto = false;
    ocultarAyuda();
}

// ------------------------------------------------------------------ capa de carga (grúa)
// Cubre la página mientras se calcula (Hardy, 15/11/2026: "como en Analytics"). Solo aparece si la espera
// pasa de 300 ms, para que las consultas rápidas no parpadeen. Dentro del modal de filtros no se usa:
// ahí se sigue marcando mientras calcula y el avance se ve en los totales en vivo.
const carga = { activas: new Map(), temporizador: null, saltar: null, omitida: false };

function cargaInicio(clave, texto = "Estamos trabajando en tu resultado", detalle = "") {
    carga.activas.set(clave, { texto, detalle });
    clearTimeout(carga.temporizador);
    carga.temporizador = setTimeout(mostrarCarga, $("cargando").classList.contains("hidden") ? 300 : 0);
}

function cargaFin(clave) {
    carga.activas.delete(clave);
    if (carga.activas.size) { mostrarCarga(); return; }
    clearTimeout(carga.temporizador);
    clearTimeout(carga.saltar);
    carga.omitida = false;
    $("cargando").classList.add("hidden");
    $("btnSeguirSinEsperar").classList.add("hidden");
}

function mostrarCarga() {
    if (!carga.activas.size || carga.omitida) return;
    const { texto, detalle } = [...carga.activas.values()].pop();
    $("cargandoTexto").textContent = texto;
    $("cargandoDetalle").textContent = detalle;
    const capa = $("cargando");
    if (capa.classList.contains("hidden")) {
        capa.classList.remove("hidden");
        clearTimeout(carga.saltar);
        carga.saltar = setTimeout(() => $("btnSeguirSinEsperar").classList.remove("hidden"), 30000);
    }
}

// ------------------------------------------------------------------ catálogo, valores y receta
function cuentaTelefonos(campo) {
    return campo.Origen === "TRABAJO" && ["SCORE", "TELEFONO", "GESTION_TELEFONO"].includes(campo.Grupo);
}

function esFiltrable(campo) {
    return ORIGENES_FILTRABLES.has(campo.Origen);
}

// Todos los valores conocidos de un campo, en orden de pantalla.
function valoresConocidos(campo) {
    const conteos = estado.segmentadores?.conteos?.[campo.Codigo];
    const orden = (campo.Valores || []).map(v => v.valor);
    const extra = conteos ? Object.keys(conteos).filter(v => !orden.includes(v)) : [];
    const posicion = new Map((campo.OrdenValores || "").split("|").filter(Boolean).map((v, i) => [v, i]));
    if (campo.TipoFiltro === "FECHA") extra.sort().reverse();                              // año-mes, del más reciente
    else if (campo.TipoFiltro === "RANGO" && !campo.Tramos) extra.sort((a, b) => Number(a) - Number(b));
    else extra.sort((a, b) => (posicion.get(a) ?? 1e6) - (posicion.get(b) ?? 1e6)       // orden del catálogo
                              || (conteos?.[b] || 0) - (conteos?.[a] || 0));
    const todos = [...orden, ...extra.filter(v => v !== SIN_DATO)];
    if (!todos.length && campo.TipoFiltro === "SINO") todos.push("1", "0");
    const conSinDato = orden.includes(SIN_DATO) || (conteos && SIN_DATO in conteos) || campo.Origen === "DATO";
    if (conSinDato && !todos.includes(SIN_DATO)) todos.push(SIN_DATO);
    for (const v of estado.desmarcados.get(campo.Codigo) || []) if (!todos.includes(v)) todos.push(v);
    return todos;
}

// Filtro de la receta a partir de lo desmarcado. null = sin filtro; {invalido} = no quedó nada marcado.
function filtroDe(campo) {
    const desmarcados = estado.desmarcados.get(campo.Codigo);
    if (!desmarcados || !desmarcados.size) return null;
    const todos = valoresConocidos(campo);
    const marcados = todos.filter(v => !desmarcados.has(v));
    if (!marcados.length) return null;   // nada marcado = "sin elegir": no filtra (para empezar de cero)
    // Campos de una sola fila por teléfono/cliente (TRABAJO): basta con nombrar las excepciones.
    // Campos de cuentas (DATO): se envían los marcados ("entra si alguna cuenta tiene un valor marcado").
    if (campo.Origen === "TRABAJO" && desmarcados.size <= marcados.length) {
        return { campo: campo.Codigo, valores: [...desmarcados], excluir: true };
    }
    return { campo: campo.Codigo, valores: marcados };
}

function filtrosInvalidos() {
    return [...estado.desmarcados.keys()]
        .map(c => estado.campos.get(c))
        .filter(c => c && filtroDe(c)?.invalido);
}

function receta() {
    const filtros = [];
    for (const codigo of estado.desmarcados.keys()) {
        const campo = estado.campos.get(codigo);
        const f = campo && filtroDe(campo);
        if (f && !f.invalido) filtros.push(f);
    }
    const porCliente = $("selPorCliente").value;
    return {
        idcartera: estado.idcartera,
        canal: $("selCanal").value || null,
        filtros,
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

function filtroActivo(codigo) {
    const campo = estado.campos.get(codigo);
    return !!(campo && filtroDe(campo));
}

function numeroFiltros() {
    return [...estado.desmarcados.keys()].filter(filtroActivo).length + Object.keys(estado.condiciones).length;
}

function actualizarBotonGenerar() {
    const total = Number(estado.ultima?.totales?.Telefonos || 0);
    const vigente = estado.ultima && !estado.calculando && estado.recetaConsultada === recetaClave() && !filtrosInvalidos().length;
    const boton = $("btnGenerar");
    boton.disabled = !vigente || total === 0;
    boton.title = !estado.ultima ? "Esperando el cálculo"
        : !vigente ? "Calculando con la selección actual…"
            : total === 0 ? "La selección no tiene teléfonos" : "";
}

// Cada cambio recalcula (con una pequeña espera para juntar varios clics).
function recetaCambio({ inmediato = false } = {}) {
    renderChips();
    marcarTiles();
    actualizarBotonGenerar();
    clearTimeout(estado.temporizador);
    const invalidos = filtrosInvalidos();
    const aviso = $("avisoFiltros");
    if (invalidos.length) {
        aviso.textContent = `Marca al menos un valor en: ${invalidos.map(c => c.Etiqueta).join(", ")}. Mientras tanto no se recalcula.`;
        aviso.classList.remove("hidden");
        indicarCalculo("error", "Falta marcar");
        return;
    }
    aviso.classList.add("hidden");
    // Fuera del modal la grúa aparece desde ya (así no parpadea entre la carga de la cartera y el cálculo)
    if (!estado.modalAbierto) cargaInicio("calculo", "Estamos trabajando en tu resultado", "Contando clientes y teléfonos con la selección actual.");
    estado.temporizador = setTimeout(() => calcular(1), inmediato ? 0 : ESPERA_CALCULO_MS);
    indicarCalculo("ocupado");
}

function indicarCalculo(tipo, texto) {
    const t = texto ?? (tipo === "listo" ? "Actualizado" : "Calculando…");
    for (const id of ["estadoCalculo", "vivoEstado"]) {
        const caja = $(id);
        caja.className = `st-calculo ${tipo === "error" ? "error" : tipo === "listo" ? "" : "ocupado"}`;
        caja.textContent = t;
    }
}

// ------------------------------------------------------------------ chips
function describirFiltro(campo) {
    const desmarcados = estado.desmarcados.get(campo.Codigo);
    const todos = valoresConocidos(campo);
    const marcados = todos.filter(v => !desmarcados.has(v));
    const lista = vs => vs.map(v => textoValor(v, campo)).join(", ");
    if (!marcados.length) return null;
    if (desmarcados.size <= marcados.length) return { texto: `${campo.Etiqueta}: sin ${lista([...desmarcados])}`, excluye: true };
    return { texto: `${campo.Etiqueta}: ${lista(marcados)}`, excluye: false };
}

function renderChips() {
    const chips = [];
    for (const [codigo, set] of estado.desmarcados) {
        const campo = estado.campos.get(codigo);
        if (!campo || !set.size) continue;
        const descripcion = describirFiltro(campo);
        if (!descripcion) continue;   // sin elegir: no filtra
        const { texto, excluye } = descripcion;
        chips.push(`<span class="st-chip ${excluye ? "excluir" : ""}" title="${esc(texto)}"><span>${esc(texto)}</span>
            <button type="button" data-quitar-filtro="${esc(codigo)}" aria-label="Quitar filtro">×</button></span>`);
    }
    for (const [codigo, modo] of Object.entries(estado.condiciones)) {
        const meta = (estado.catalogo?.condiciones || []).find(c => c.Codigo === codigo);
        const texto = `${modo === "QUITAR" ? "Sin" : "Solo"} ${(meta?.etiqueta || codigo).toLowerCase()}`;
        chips.push(`<span class="st-chip cond" title="${esc(meta?.descripcion || "")}"><span>${esc(texto)}</span>
            <button type="button" data-quitar-condicion="${esc(codigo)}" aria-label="Quitar condición">×</button></span>`);
    }
    $("chips").innerHTML = chips.join("") || `<span class="st-vacio">Sin filtros: todos los teléfonos no descartados de la cartera.</span>`;
    $("cntFiltros").textContent = numeroFiltros();
}

// ------------------------------------------------------------------ modal de filtros
function camposVisibles() {
    return [...estado.campos.values()].filter(c => !CAMPOS_OCULTOS.has(c.Codigo) && c.Origen !== "DIA");
}

function pestanaDeGrupo(grupo) {
    const p = PESTANAS.find(x => x.grupos.includes(grupo));
    return p ? p.clave : "SEGMENTO_CLIENTE";
}

function renderPestanas() {
    const activos = {};
    for (const codigo of estado.desmarcados.keys()) {
        const campo = estado.campos.get(codigo);
        if (campo && filtroActivo(codigo)) activos[pestanaDeGrupo(campo.Grupo)] = (activos[pestanaDeGrupo(campo.Grupo)] || 0) + 1;
    }
    activos.GESTION_CLIENTE = (activos.GESTION_CLIENTE || 0) + Object.keys(estado.condiciones).length;
    const total = clave => camposVisibles().filter(c => pestanaDeGrupo(c.Grupo) === clave).length
        + (clave === "GESTION_CLIENTE" && (estado.catalogo?.condiciones || []).length ? 1 : 0);
    $("tabsFiltros").innerHTML = PESTANAS.map(p => `<button type="button" role="tab" class="st-tab ${p.clave === estado.pestana ? "on" : ""}"
            data-pestana="${p.clave}" aria-selected="${p.clave === estado.pestana}">
            <strong>${esc(p.titulo)}</strong><small>${esc(p.nota)} · ${total(p.clave)}</small>
            ${activos[p.clave] ? `<span class="st-badge">${activos[p.clave]}</span>` : ""}
        </button>`).join("");
}

function htmlTileCampo(campo) {
    const codigo = esc(campo.Codigo);
    const filtrable = esFiltrable(campo);
    const unidad = cuentaTelefonos(campo) ? "teléfonos" : "clientes";
    return `<div class="st-tile" data-tile="${codigo}" data-nombre="${esc(`${campo.Etiqueta} ${campo.Codigo}`.toLowerCase())}">
        <div class="st-tile-head">
            <span class="st-tile-titulo">${esc(campo.Etiqueta)}</span>
            ${campo.Nivel === "CUENTA" ? `<span class="st-nivel">cuentas</span>` : ""}
            <button type="button" class="st-ayuda-btn" data-ayuda="${codigo}" aria-label="Qué es ${esc(campo.Etiqueta)}">?</button>
        </div>
        ${filtrable ? `<div class="st-tile-tools">
            <button type="button" data-accion="todo" data-campo="${codigo}">Todo</button>
            <button type="button" data-accion="nada" data-campo="${codigo}">Ninguno</button>
            <button type="button" data-accion="invertir" data-campo="${codigo}">Invertir</button>
            <span class="st-tile-unidad">${unidad}</span>
        </div>
        <input class="st-tile-buscar hidden" type="search" data-buscar-valor="${codigo}" placeholder="Buscar valor…" autocomplete="off">
        <div class="st-valores" data-valores="${codigo}"></div>
        <div class="st-tile-pie hidden" data-pie="${codigo}"></div>`
        : `<div class="st-tile-pie aviso">Todavía no se puede filtrar en el generador.</div>`}
    </div>`;
}

function htmlTileCondiciones(condiciones) {
    if (!condiciones.length) return "";
    const filas = condiciones.map(c => {
        const codigo = esc(c.Codigo);
        const boton = (m, texto, titulo) => `<button type="button" data-condicion="${codigo}" data-modo="${m}" title="${titulo}"
            class="${m === "QUITAR" ? "quitar" : ""}">${texto}</button>`;
        return `<div class="st-cond-fila" data-fila-cond="${codigo}">
            <span class="st-cond-nombre">${esc(c.etiqueta)}
                <button type="button" class="st-ayuda-btn" data-ayuda-cond="${codigo}" aria-label="Qué es ${esc(c.etiqueta)}">?</button></span>
            <span class="st-cond">${boton("QUITAR", "Quitar", "Saca a quienes cumplen")}${boton("SOLO", "Solo", "Deja solo a quienes cumplen")}${boton("INDIFERENTE", "Indiferente", "No filtra")}</span>
        </div>`;
    }).join("");
    return `<div class="st-tile st-tile-cond" data-tile-cond="1" data-nombre="${esc(("condiciones del día " + condiciones.map(c => c.etiqueta).join(" ")).toLowerCase())}">
        <div class="st-tile-head"><span class="st-tile-titulo">Condiciones del día</span><span class="st-nivel vivo">en vivo</span></div>
        ${filas}
    </div>`;
}

function construirMuro() {
    const pestana = PESTANAS.find(p => p.clave === estado.pestana) || PESTANAS[0];
    const campos = camposVisibles();
    const conocidos = new Set(PESTANAS.flatMap(p => p.grupos));
    const grupos = pestana.clave === "SEGMENTO_CLIENTE"
        ? [...pestana.grupos, ...new Set(campos.map(c => c.Grupo).filter(g => !conocidos.has(g)))]
        : pestana.grupos;
    const prioridad = PRINCIPALES[pestana.clave] || [];
    const deLaPestana = campos.filter(c => grupos.includes(c.Grupo));
    const principales = deLaPestana.filter(c => prioridad.includes(c.Codigo))
        .sort((a, b) => prioridad.indexOf(a.Codigo) - prioridad.indexOf(b.Codigo));
    const porEtiqueta = (a, b) => a.Etiqueta.localeCompare(b.Etiqueta, "es");
    const resto = deLaPestana.filter(c => !prioridad.includes(c.Codigo));
    // Los segmentos cargados desde "Segmentos del banco" van juntos, para encontrarlos sin buscar entre todos
    const segmentos = resto.filter(c => GRUPOS_SEGMENTO.includes(c.Grupo)).sort(porEtiqueta);
    const complementarios = resto.filter(c => !GRUPOS_SEGMENTO.includes(c.Grupo)).sort(porEtiqueta);
    const tilesPrincipales = [
        ...(grupos.includes("CONDICION_DIA") ? [htmlTileCondiciones(estado.catalogo?.condiciones || [])] : []),
        ...principales.map(htmlTileCampo),
    ].filter(Boolean);
    const seccion = (titulo, nota, tiles) => tiles.length ? `<section class="st-seccion">
            <div class="st-seccion-titulo"><h4>${esc(titulo)}</h4><small>${esc(nota)} · ${tiles.length}</small></div>
            <div class="st-grupo-cuerpo">${tiles.join("")}</div>
        </section>` : "";
    $("muro").innerHTML = (seccion("Principales", "los que más se usan para armar bases", tilesPrincipales)
        + seccion("Segmentos del banco", "cargados desde la pantalla Segmentos del banco", segmentos.map(htmlTileCampo))
        + seccion("Complementarios", "para afinar", complementarios.map(htmlTileCampo)))
        || `<p class="st-vacio">Sin campos para esta cartera.</p>`;
    for (const campo of campos) if (esFiltrable(campo) && pestanaDeGrupo(campo.Grupo) === pestana.clave) renderValores(campo.Codigo);
    renderPestanas();
    marcarTiles();
}

function renderValores(codigo) {
    const campo = estado.campos.get(codigo);
    const caja = document.querySelector(`[data-valores="${CSS.escape(codigo)}"]`);
    if (!campo || !caja) return;
    const conteos = estado.segmentadores?.conteos?.[codigo];
    const desmarcados = estado.desmarcados.get(codigo) || new Set();
    const todos = valoresConocidos(campo);
    const buscador = document.querySelector(`[data-buscar-valor="${CSS.escape(codigo)}"]`);
    if (buscador) buscador.classList.toggle("hidden", todos.length <= VALORES_CON_BUSCADOR);
    const busqueda = (buscador?.value || "").trim().toLowerCase();
    const n = v => (conteos ? Number(conteos[v] || 0) : null);
    const maximo = Math.max(1, ...todos.map(v => n(v) || 0));
    const visibles = todos.filter(v => !busqueda || String(textoValor(v, campo)).toLowerCase().includes(busqueda));
    const scroll = caja.scrollTop;
    caja.innerHTML = visibles.length ? visibles.map(v => {
        const cantidad = n(v);
        const marcado = !desmarcados.has(v);
        return `<label class="st-valor ${marcado ? "" : "off"} ${cantidad === 0 ? "cero" : ""}" title="${esc(textoValor(v, campo))}">
            <input type="checkbox" data-campo="${esc(codigo)}" data-valor="${esc(v)}" ${marcado ? "checked" : ""}>
            <span class="barra" style="width:${cantidad ? Math.max(2, cantidad / maximo * 100) : 0}%"></span>
            <span class="txt">${esc(textoValor(v, campo))}</span><span class="n">${cantidad === null ? "" : num(cantidad)}</span>
        </label>`;
    }).join("") : `<div class="st-tile-pie">${busqueda ? "Ningún valor coincide." : "Sin valores."}</div>`;
    caja.scrollTop = scroll;

    const pie = document.querySelector(`[data-pie="${CSS.escape(codigo)}"]`);
    if (pie) {
        const sinDatos = conteos && todos.every(v => v === SIN_DATO || !n(v));
        const marcados = todos.filter(v => !desmarcados.has(v)).length;
        let texto = "";
        if (!marcados) texto = "Sin elegir: no filtra. Marca los valores que quieres.";
        else if (desmarcados.size) texto = `${marcados} de ${todos.length} marcados`;
        else if (sinDatos) texto = "Sin datos cargados para esta cartera en el corte actual.";
        pie.textContent = texto;
        pie.classList.toggle("hidden", !texto);
        pie.classList.toggle("aviso", !!sinDatos && !desmarcados.size);
    }
}

function marcarTiles() {
    document.querySelectorAll("[data-tile]").forEach(tile => {
        const set = estado.desmarcados.get(tile.dataset.tile);
        const activo = filtroActivo(tile.dataset.tile);
        tile.classList.toggle("activo", activo);
        tile.classList.toggle("sin-elegir", !!set?.size && !activo);
    });
    document.querySelectorAll("[data-fila-cond]").forEach(fila => {
        const modo = estado.condiciones[fila.dataset.filaCond] || "INDIFERENTE";
        fila.classList.toggle("activa", modo !== "INDIFERENTE");
        fila.querySelectorAll("[data-modo]").forEach(b => b.classList.toggle("on", b.dataset.modo === modo));
    });
    document.querySelector("[data-tile-cond]")?.classList.toggle("activo", Object.keys(estado.condiciones).length > 0);
    if (estado.modalAbierto) renderPestanas();
    filtrarTiles();
}

function filtrarTiles() {
    const q = $("txtBuscarSeg").value.trim().toLowerCase();
    const soloActivos = $("chkSoloActivos").checked;
    document.querySelectorAll("[data-tile], [data-tile-cond]").forEach(tile => {
        const visible = (!q || tile.dataset.nombre.includes(q)) && (!soloActivos || tile.classList.contains("activo"));
        tile.classList.toggle("hidden", !visible);
    });
    document.querySelectorAll("#muro .st-seccion").forEach(s => s.classList.toggle("hidden", !s.querySelector(".st-tile:not(.hidden)")));
    ajustarMosaico();
}

// Mosaico: filas de 4 px; cada filtro ocupa las filas que mide (llena huecos de izquierda a derecha).
const FILA_MOSAICO = 4, HUECO_MOSAICO = 12;
function ajustarMosaico() {
    if (!estado.modalAbierto) return;
    document.querySelectorAll("#muro .st-tile").forEach(tile => {
        if (tile.classList.contains("hidden")) return;
        tile.style.gridRowEnd = "auto";
        const alto = tile.getBoundingClientRect().height;
        tile.style.gridRowEnd = `span ${Math.max(1, Math.ceil((alto + HUECO_MOSAICO) / FILA_MOSAICO))}`;
    });
}

function abrirFiltros() {
    estado.modalAbierto = true;
    abrirModal("modalFiltros");
    construirMuro();
    renderVivo();
    // Los conteos se piden con el modal abierto: si la selección cambió desde el último cálculo, se recalcula
    if (estado.segmentadoresClave !== recetaClave() || estado.segmentadores?.error) recetaCambio({ inmediato: true });
}

function cambiarPestana(clave) {
    estado.pestana = clave;
    $("txtBuscarSeg").value = "";
    construirMuro();
    $("muro").scrollTop = 0;
}

// Búsqueda de filtros: si el filtro está en otra pestaña, se cambia a esa pestaña.
function buscarFiltro() {
    const q = $("txtBuscarSeg").value.trim().toLowerCase();
    if (q && !document.querySelector("#muro [data-nombre*='" + CSS.escape(q) + "']")) {
        const campo = camposVisibles().find(c => `${c.Etiqueta} ${c.Codigo}`.toLowerCase().includes(q));
        if (campo && pestanaDeGrupo(campo.Grupo) !== estado.pestana) {
            estado.pestana = pestanaDeGrupo(campo.Grupo);
            construirMuro();
        }
    }
    filtrarTiles();
}

function renderVivo() {
    const t = estado.ultima?.totales || {};
    $("vivoClientes").textContent = num(t.Clientes);
    $("vivoTelefonos").textContent = num(t.Telefonos);
    $("vivoScore").textContent = num(t.ScorePromedio, 1);
}

// ------------------------------------------------------------------ ayuda flotante
function ayudaCampo(campo) {
    const filas = [];
    const nivel = campo.Nivel === "CUENTA" ? "Cuentas del cliente: entra el cliente si alguna de sus cuentas tiene un valor marcado"
        : cuentaTelefonos(campo) ? "Teléfono" : "Cliente";
    filas.push(["Nivel", nivel]);
    filas.push(["Cuenta", cuentaTelefonos(campo) ? "Teléfonos" : "Clientes"]);
    const fuente = campo.Tabla ? `${campo.Tabla}${campo.Columna ? "." + campo.Columna : ""}` : campo.Fuente;
    if (fuente) filas.push(["Fuente", fuente]);
    if (campo.Actualizacion) filas.push(["Actualización", campo.Actualizacion]);
    if (campo.FechaFuente) filas.push(["Fecha del dato", fecha(campo.FechaFuente)]);
    if (campo.Tramos) filas.push(["Tramos", TRAMOS_PROPUESTOS.has(campo.Codigo) ? "Propuestos (por confirmar)" : "Escala fija"]);
    if (campo.TipoFiltro === "FECHA") filas.push(["Valores", "Por año y mes"]);
    return { titulo: campo.Etiqueta, texto: campo.Descripcion || "", filas };
}

function mostrarAyuda(boton) {
    let datos;
    if (boton.dataset.ayuda) {
        const campo = estado.campos.get(boton.dataset.ayuda);
        if (!campo) return;
        datos = ayudaCampo(campo);
    } else {
        const c = (estado.catalogo?.condiciones || []).find(x => x.Codigo === boton.dataset.ayudaCond);
        if (!c) return;
        datos = { titulo: c.etiqueta, texto: c.descripcion,
                  filas: [["Nivel", c.nivel === "TELEFONO" ? "Teléfono" : "Cliente"], ["Fuente", c.fuente || "—"],
                          ["Cuándo", "En vivo: lo ocurrido hoy en la cartera"]] };
    }
    const pop = $("ayuda");
    pop.innerHTML = `<strong>${esc(datos.titulo)}</strong>${datos.texto ? `<p>${esc(datos.texto)}</p>` : ""}
        <dl>${datos.filas.map(([k, v]) => `<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join("")}</dl>`;
    pop.classList.remove("hidden");
    const r = boton.getBoundingClientRect();
    const ancho = pop.offsetWidth, alto = pop.offsetHeight;
    let left = Math.min(window.innerWidth - ancho - 12, Math.max(12, r.left + r.width / 2 - ancho / 2));
    let top = r.bottom + 8;
    if (top + alto > window.innerHeight - 12) top = Math.max(12, r.top - alto - 8);
    pop.style.left = `${left}px`;
    pop.style.top = `${top}px`;
}

function ocultarAyuda() { $("ayuda").classList.add("hidden"); }

// ------------------------------------------------------------------ cambios de la selección
function alternarValor(codigo, valor, marcado) {
    const set = estado.desmarcados.get(codigo) || new Set();
    if (marcado) set.delete(valor); else set.add(valor);
    if (set.size) estado.desmarcados.set(codigo, set); else estado.desmarcados.delete(codigo);
    renderValores(codigo);
    recetaCambio();
}

// Todo / Ninguno / Invertir. Con texto en el buscador del filtro, actúan solo sobre los valores visibles.
function accionValores(codigo, accion) {
    const campo = estado.campos.get(codigo);
    if (!campo) return;
    const todos = valoresConocidos(campo);
    const busqueda = (document.querySelector(`[data-buscar-valor="${CSS.escape(codigo)}"]`)?.value || "").trim().toLowerCase();
    const objetivo = busqueda ? todos.filter(v => String(textoValor(v, campo)).toLowerCase().includes(busqueda)) : todos;
    const set = new Set(estado.desmarcados.get(codigo) || []);
    for (const v of objetivo) {
        if (accion === "todo") set.delete(v);
        else if (accion === "nada") set.add(v);
        else if (set.has(v)) set.delete(v); else set.add(v);
    }
    if (set.size) estado.desmarcados.set(codigo, set); else estado.desmarcados.delete(codigo);
    renderValores(codigo);
    recetaCambio();
}

function limpiarCampo(codigo) {
    estado.desmarcados.delete(codigo);
    renderValores(codigo);
    recetaCambio();
}

function cambiarCondicion(codigo, modo) {
    if (modo === "INDIFERENTE") delete estado.condiciones[codigo];
    else estado.condiciones[codigo] = modo;
    if (codigo === "ENVIADO_HOY" && modo !== "INDIFERENTE" && !$("selCanal").value) {
        mostrarMensaje("“Ya enviado hoy” compara con las bases del mismo canal: elige el canal.", "aviso");
    }
    recetaCambio();
}

// Para empezar de cero: todas las listas quedan sin marcar ("sin elegir", no filtran) y se marca solo lo que se quiere.
function desmarcarTodo() {
    for (const campo of camposVisibles()) {
        if (!esFiltrable(campo)) continue;
        estado.desmarcados.set(campo.Codigo, new Set(valoresConocidos(campo)));
    }
    if (estado.modalAbierto) construirMuro();
    recetaCambio({ inmediato: true });
}

function limpiarTodo() {
    estado.desmarcados.clear();
    estado.condiciones = {};
    $("selPorCliente").value = "";
    document.querySelectorAll("[data-buscar-valor]").forEach(i => { i.value = ""; });
    if (estado.modalAbierto) construirMuro();
    mostrarMensaje("");
    recetaCambio({ inmediato: true });
}

// ------------------------------------------------------------------ cálculo
// Una sola consulta a la vez (15/11/2026: con muchos clics seguidos se acumulaban consultas en el servidor y
// lo dejaban sin responder). Si llega un cambio mientras calcula, se anota y se consulta al terminar, con la
// selección más reciente. Además, la pantalla corta la espera a los 150 s (el servidor corta a los 120 s).
const SEGUNDOS_ESPERA_MAX = 150;

async function calcular(pagina = 1, conConteos = estado.modalAbierto) {
    if (!estado.idcartera || filtrosInvalidos().length) { cargaFin("calculo"); return; }
    if (estado.condiciones.ENVIADO_HOY && !$("selCanal").value) {
        indicarCalculo("error", "Elige el canal");
        cargaFin("calculo");
        return;
    }
    if (estado.enVuelo) {
        estado.pendiente = { pagina, conConteos: conConteos || !!estado.pendiente?.conConteos };
        indicarCalculo("ocupado", "Calculando… (hay cambios en cola)");
        return;
    }
    estado.enVuelo = true;
    const secuencia = ++estado.secuencia;
    const clave = recetaClave();
    estado.calculando = true;
    actualizarBotonGenerar();
    indicarCalculo("ocupado");
    if (!estado.modalAbierto) cargaInicio("calculo", "Estamos trabajando en tu resultado", "Contando clientes y teléfonos con la selección actual.");
    const inicio = Date.now();
    const reloj = setInterval(() => {
        const s = Math.round((Date.now() - inicio) / 1000);
        indicarCalculo("ocupado", `Calculando… ${s} s${estado.pendiente ? " (hay cambios en cola)" : ""}`);
    }, 1000);
    const control = new AbortController();
    const corte = setTimeout(() => control.abort(), SEGUNDOS_ESPERA_MAX * 1000);
    try {
        const r = await pedir(`${API}/consulta`, {
            method: "POST", headers: { "Content-Type": "application/json" }, signal: control.signal,
            body: JSON.stringify({ ...receta(), pagina, tamano: tamanoPagina(), conteos: conConteos }),
        });
        if (secuencia !== estado.secuencia) return;   // cambió la cartera mientras calculaba
        estado.ultima = r;
        estado.recetaConsultada = clave;
        estado.pagina = pagina;
        if (r.segmentadores) {
            estado.segmentadores = r.segmentadores;
            estado.segmentadoresClave = r.segmentadores.error ? null : clave;
            const aviso = $("avisoFiltros");
            if (r.segmentadores.error) {
                aviso.textContent = `${r.segmentadores.error} La base y la tabla sí se actualizaron; los números de cada filtro no.`;
                aviso.classList.remove("hidden");
            }
            if (estado.modalAbierto) {
                for (const campo of camposVisibles()) if (esFiltrable(campo)) renderValores(campo.Codigo);
                renderChips();
                ajustarMosaico();
            }
        }
        renderResultado();
        renderVivo();
        const ms = Object.values(r.tiempos_ms || {}).reduce((a, b) => a + b, 0);
        indicarCalculo("listo", ms ? `Actualizado · ${(ms / 1000).toFixed(1)} s` : "Actualizado");
        if (r.tiempos_ms) {
            const detalle = Object.entries(r.tiempos_ms).map(([k, v]) => `${k}: ${v} ms`).join(" · ");
            $("estadoCalculo").title = $("vivoEstado").title = `Tiempo en el servidor: ${detalle}`;
            console.info("[generador] tiempos", r.tiempos_ms);
        }
        if ($("mensaje").classList.contains("error")) mostrarMensaje("");
    } catch (error) {
        if (secuencia !== estado.secuencia) return;
        if (error instanceof SesionInvalidaError) return;
        if (error?.name === "AbortError") {
            indicarCalculo("error", "Tardó demasiado");
            mostrarMensaje(`La consulta pasó de ${SEGUNDOS_ESPERA_MAX} segundos y la pantalla dejó de esperarla. `
                + "Prueba con menos filtros a la vez.", "error");
        } else {
            indicarCalculo("error", "No se pudo calcular");
            manejarError(error);
        }
    } finally {
        clearInterval(reloj);
        clearTimeout(corte);
        estado.enVuelo = false;
        if (estado.pendiente) {
            const p = estado.pendiente;
            estado.pendiente = null;
            calcular(p.pagina, p.conConteos || estado.modalAbierto);
        } else {
            estado.calculando = false;
            actualizarBotonGenerar();
            cargaFin("calculo");
        }
    }
}

function tamanoPagina() {
    return Number($("selTop").value) || 50;
}

// Cambiar de página no recalcula los conteos (misma selección, otra página de teléfonos).
async function paginar(pagina) {
    if (!estado.ultima || estado.calculando || estado.recetaConsultada !== recetaClave() || pagina < 1) return;
    const clave = recetaClave();
    cargaInicio("pagina", "Trayendo los teléfonos", `Página ${pagina} de la base.`);
    try {
        const r = await postJson(`${API}/consulta`, { ...receta(), pagina, tamano: tamanoPagina(), conteos: false });
        if (estado.calculando || clave !== recetaClave()) return;
        estado.ultima = { ...estado.ultima, ...r };
        estado.pagina = pagina;
        renderResultado();
    } catch (error) {
        manejarError(error);
    } finally {
        cargaFin("pagina");
    }
}

function renderResultado() {
    const r = estado.ultima;
    const t = r.totales || {};
    const embudo = r.embudo || [];
    const origen = embudo[1] || embudo[0] || {};    // base origen: teléfonos no descartados de la cartera
    const tel = Number(t.Telefonos || 0), cli = Number(t.Clientes || 0);
    const telOrigen = Number(origen.telefonos || 0), cliOrigen = Number(origen.clientes || 0);

    $("kpiClientes").textContent = num(cli);
    $("kpiClientesSub").textContent = cliOrigen ? `de ${num(cliOrigen)} (${pct(cli, cliOrigen)})` : "—";
    $("kpiTelefonos").textContent = num(tel);
    $("kpiTelefonosSub").textContent = telOrigen ? `de ${num(telOrigen)} (${pct(tel, telOrigen)})` : "—";
    $("kpiWhatsapp").textContent = pct(Number(t.WhatsappSi || 0), tel);
    $("kpiWhatsappSub").textContent = t.WhatsappSi === undefined ? "—" : `${num(t.WhatsappSi)} de ${num(tel)}`;
    $("kpiTimbrado").textContent = pct(Number(t.Timbrado34 || 0), tel);
    $("kpiTimbradoSub").textContent = t.Timbrado34 === undefined ? "—" : `${num(t.Timbrado34)} de ${num(tel)}`;
    $("kpiCapital").textContent = num(t.Capital);
    $("kpiScore").textContent = num(t.ScorePromedio, 1);
    $("kpiTramos").innerHTML = tel ? ["A", "B", "C", "D", "E"].map(tr => {
        const n = Number(t[`Tramo${tr}`] || 0);
        const p = n / tel * 100;
        return n ? `<div class="st-tramo-${tr}" style="width:${p}%" title="Tramo ${tr}: ${num(n)} teléfonos (${p.toFixed(1)}%)">${p >= 9 ? tr : ""}</div>` : "";
    }).join("") : "";

    $("redOrigen").textContent = num(telOrigen);
    $("redOrigenSub").textContent = `teléfonos · ${num(cliOrigen)} clientes`;
    $("redResultado").textContent = num(tel);
    $("redResultadoSub").textContent = `teléfonos · ${num(cli)} clientes`;
    const restante = telOrigen ? tel / telOrigen * 100 : 0;
    $("redBarra").style.width = `${Math.min(100, restante)}%`;
    $("redPct").textContent = telOrigen ? `Queda ${restante.toFixed(1)}% · se excluye ${(100 - restante).toFixed(1)}%` : "—";

    renderImpacto(embudo);
    renderFilas(r.filas || [], tel, r.dias_historial);
}

function renderImpacto(embudo) {
    const pasos = embudo.slice(2);
    const tbody = $("tbodyImpacto");
    if (!pasos.length) {
        tbody.innerHTML = `<tr><td colspan="7" class="st-vacio">Sin filtros aplicados.</td></tr>`;
        return;
    }
    let antes = Number(embudo[1]?.telefonos || 0);
    const inicio = antes;
    const filas = pasos.map((p, i) => {
        const despues = Number(p.telefonos || 0);
        const excl = antes - despues;
        const fila = `<tr><td class="num">${i + 1}</td><td>${esc(p.paso)}</td><td class="num">${num(antes)}</td>
            <td class="num">${num(despues)}</td><td class="num">${num(excl)}</td>
            <td class="num ${excl > 0 ? "st-baja" : ""}">${antes ? `−${(excl / antes * 100).toFixed(1)}%` : "—"}</td>
            <td class="num">${num(p.clientes)}</td></tr>`;
        antes = despues;
        return fila;
    });
    const final = Number(pasos[pasos.length - 1].telefonos || 0);
    filas.push(`<tr class="total"><td></td><td>Total</td><td class="num">${num(inicio)}</td><td class="num">${num(final)}</td>
        <td class="num">${num(inicio - final)}</td><td class="num st-baja">${inicio ? `−${((inicio - final) / inicio * 100).toFixed(1)}%` : "—"}</td>
        <td class="num">${num(pasos[pasos.length - 1].clientes)}</td></tr>`);
    tbody.innerHTML = filas.join("");
}

// Semáforo de SISCOB (descripción del catálogo, score.Campo COLOR)
const COLOR_HEX = { V: "#1f9d55", T: "#14a3a3", A: "#e3b13b", R: "#c84646", P: "#9aa5b1", Q: "#9aa5b1", PQ: "#9aa5b1", F: "#d23ca0" };
const COLOR_NOMBRE = { V: "Verde", T: "Turquesa", A: "Amarillo", P: "Plomo", Q: "Plomo", PQ: "Plomo", F: "Fucsia", R: "Rojo" };

function siNo(valor) {
    if (valor === null || valor === undefined || valor === "") return "—";
    const v = String(valor).toUpperCase();
    if (valor === true || v === "1" || v === "SI") return `<span class="st-si">SI</span>`;
    if (valor === false || v === "0" || v === "NO") return `<span class="st-no">NO</span>`;
    return esc(valor);
}

function resultado(codigo, fechaTexto) {
    if (!codigo) return `<span class="st-res sin" title="Sin gestiones en la ventana">—</span>`;
    const [texto, clase] = ETIQUETA_RESULTADO[codigo] || [codigo, "sin"];
    return `<span class="st-res ${clase}" title="${esc(codigo)}${fechaTexto ? " · " + esc(fechaTexto) : ""}">${esc(texto)}</span>`;
}

function renderFilas(filas, total, dias) {
    if (dias) $("thMejorTel").title = `Mejor resultado del teléfono en los últimos ${dias} días`;
    const tbody = $("tbodyFilas");
    if (!filas.length) {
        tbody.innerHTML = `<tr><td colspan="17" class="st-vacio">Ningún teléfono cumple la selección.</td></tr>`;
    } else {
        const combinada = !!estado.carteras.find(x => Number(x.IdCartera) === estado.idcartera)?.Miembros;
        tbody.innerHTML = filas.map(f => {
            const color = f.PrioridadColor
                ? `<span class="st-color" style="background:${COLOR_HEX[f.PrioridadColor] || "#cbd5e1"}"></span>${esc(COLOR_NOMBRE[f.PrioridadColor] || f.PrioridadColor)}` : "—";
            return `<tr>
                <td class="num">${num(f.Posicion)}</td>
                <td>${esc(f.DNI)}${combinada && f.IdCartera ? `<br><small style="color:#64748b" title="Cartera del teléfono">cartera ${esc(f.IdCartera)}</small>` : ""}</td>
                <td>${esc(f.IdCliente ?? "—")}</td>
                <td>${esc(f.Telefono)}</td>
                <td class="num">${num(f.Capital, 2)}</td>
                <td class="num"><button type="button" class="st-score-btn" data-dni="${esc(f.DNI)}" data-telefono="${esc(f.Telefono)}"
                    title="Ver por qué tiene este score">${num(f.Score)}</button></td>
                <td>${f.Tramo ? `<span class="st-tag st-tramo-${esc(f.Tramo)}">${esc(f.Tramo)}</span>` : "—"}</td>
                <td>${esc(f.Timbra ?? "—")}</td>
                <td>${siNo(f.Whatsapp)}</td>
                <td>${siNo(f.Osiptel)}</td>
                <td>${color}</td>
                <td>${resultado(f.MejorResultadoTel, f.FechaMejorTel ? fecha(f.FechaMejorTel) : "")}</td>
                <td>${resultado(f.MejorResultadoCli, f.FechaMejorCli ? fecha(f.FechaMejorCli) : "")}</td>
                <td>${resultado(f.UltimoResultadoTel, f.UltimoEventoTel ? fechaHora(f.UltimoEventoTel) : "")}</td>
                <td class="num">${f.DiasUltCef === null || f.DiasUltCef === undefined ? "—" : num(f.DiasUltCef)}</td>
                <td>${esc(f.FranjaContacto || "—")}</td>
                <td class="num">${num(f.OrdenEnBase)}</td>
            </tr>`;
        }).join("");
    }
    const tam = tamanoPagina();
    const desde = total ? (estado.pagina - 1) * tam + 1 : 0;
    const hasta = Math.min(total, estado.pagina * tam);
    $("tituloTabla").textContent = estado.pagina === 1 ? `Top ${num(Math.min(tam, total))} teléfonos de la base` : "Teléfonos de la base";
    $("infoPagina").textContent = total ? `${num(desde)}–${num(hasta)} de ${num(total)} · orden de salida (score desc.)` : "0 teléfonos";
    $("btnAnterior").disabled = estado.pagina <= 1;
    $("btnSiguiente").disabled = hasta >= total;
}

// ------------------------------------------------------------------ detalle del score
function rangosTramo(cab) {
    if (!cab || cab.Tramo_A === undefined) return {};
    const a = Math.ceil(cab.Tramo_A), b = Math.ceil(cab.Tramo_B), c = Math.ceil(cab.Tramo_C), d = Math.ceil(cab.Tramo_D);
    return { A: `${a}–100`, B: `${b}–${a - 1}`, C: `${c}–${b - 1}`, D: `${d}–${c - 1}`, E: `0–${d - 1}` };
}

async function cargarScoreVersion() {
    if (estado.scoreVersion?.idcartera === estado.idcartera) return estado.scoreVersion;
    estado.scoreVersion = await pedir(`${API}/score/version?idcartera=${estado.idcartera}`);
    return estado.scoreVersion;
}

async function abrirScore() {
    $("cuerpoScore").innerHTML = `<p class="st-vacio">Cargando…</p>`;
    abrirModal("modalScore");
    try {
        const v = await cargarScoreVersion();
        $("cuerpoScore").innerHTML = htmlScoreVersion(v);
    } catch (error) {
        if (error instanceof SesionInvalidaError) return;
        $("cuerpoScore").innerHTML = `<p class="st-mensaje error">${esc(error.message)}</p>`;
    }
}

function htmlScoreVersion(v) {
    if (!v.version) return `<p class="st-vacio">La cartera todavía no tiene score calculado.</p>`;
    const m = v.metricas || {};
    const cab = v.cabecera || {};
    const rangos = rangosTramo(cab);
    const porTramo = Object.fromEntries((m.tasa_por_tramo || []).map(x => [x.tramo, x]));
    if (!m.tasa_por_tramo) {   // versión sin la tabla completa: solo A y E
        if (m.tasa_tramo_A_pct !== undefined) porTramo.A = { tasa_cef_pct: m.tasa_tramo_A_pct };
        if (m.tasa_tramo_E_pct !== undefined) porTramo.E = { tasa_cef_pct: m.tasa_tramo_E_pct };
    }
    const entidad = v.entidad;
    const porEntidad = Object.fromEntries((m.tasa_por_entidad_tramo || []).filter(x => x.entidad === entidad).map(x => [x.tramo, x]));
    const base = Number(m.tasa_cef_prueba_pct || 0);
    const reparto = Object.fromEntries((v.reparto || []).map(x => [x.Tramo, x]));
    const totalCartera = (v.reparto || []).reduce((s, x) => s + Number(x.Telefonos || 0), 0);
    const sel = estado.ultima?.totales || {};
    const totalSel = Number(sel.Telefonos || 0);
    const maxTasa = Math.max(1, ...Object.values(porTramo).map(x => Number(x.tasa_cef_pct || 0)));

    const filas = ["A", "B", "C", "D", "E"].map(tr => {
        const t = porTramo[tr], te = porEntidad[tr];
        const tasa = t ? Number(t.tasa_cef_pct) : null;
        const veces = tasa !== null && base ? tasa / base : null;
        const cart = Number(reparto[tr]?.Telefonos || 0);
        const enSel = Number(sel[`Tramo${tr}`] || 0);
        return `<tr>
            <td><span class="st-tag st-tramo-${tr}">${tr}</span></td>
            <td class="num">${esc(rangos[tr] || "—")}</td>
            <td><div class="st-barra-tasa"><div style="width:${tasa !== null ? Math.max(1, tasa / maxTasa * 100) : 0}%"></div>
                <span>${tasa !== null ? `${num(tasa, 2)}%` : "—"}</span></div>
                ${t?.telefonos ? `<small>${num(t.cef)} CEF de ${num(t.telefonos)} teléfonos</small>` : ""}</td>
            <td class="num">${veces !== null ? `${num(veces, 1)}×` : "—"}</td>
            <td class="num">${te ? `${num(te.tasa_cef_pct, 2)}%` : "—"}</td>
            <td class="num">${num(cart)} <small>${pct(cart, totalCartera)}</small></td>
            <td class="num">${num(enSel)} <small>${pct(enSel, totalSel)}</small></td>
        </tr>`;
    }).join("");

    const aucEnt = entidad ? m.auc_score_por_entidad?.[entidad] : null;
    const reglaEnt = entidad ? m.auc_regla_por_entidad?.[entidad] : null;
    const pesos = {};
    for (const p of v.pesos || []) (pesos[p.Caracteristica] ||= []).push(p);

    return `
        <section class="st-score-intro">
            <p><strong>Score v${esc(v.version)}</strong>${cab.FechaPublicacion ? ` · publicado el ${fecha(cab.FechaPublicacion)}` : ""}
               · score de la cartera calculado al ${fecha(v.fecha_score)}.</p>
            <p>El score ordena los teléfonos por su probabilidad de <strong>contacto directo (CEF: titular o tercero con acuerdo)
               en la semana siguiente</strong>, si se les marca. Los tramos son quintiles: A es el 20% con mejor score del entrenamiento, E el 20% peor.</p>
            <p>La tasa se midió en semanas que el modelo no vio al entrenarse${(m.cortes_prueba || []).length ? ` (${m.cortes_prueba.map(fecha).join(", ")})` : ""}:
               ${m.telefonos_prueba ? `${num(m.telefonos_prueba)} teléfonos marcados, ` : ""}tasa promedio de CEF <strong>${base ? `${num(base, 2)}%` : "—"}</strong>.</p>
        </section>
        <div class="st-tabla-wrap">
            <table class="st-tabla st-tabla-score">
                <thead><tr><th>Tramo</th><th class="num">Score</th><th>Tasa de CEF medida (todas las carteras)</th>
                    <th class="num" title="Cuántas veces la tasa promedio">vs promedio</th>
                    <th class="num">${entidad ? `Tasa en ${esc(entidad)}` : "Tasa en la entidad"}</th>
                    <th class="num">Teléfonos de la cartera hoy</th><th class="num">En tu selección</th></tr></thead>
                <tbody>${filas}</tbody>
            </table>
        </div>
        ${m.tasa_por_tramo ? "" : `<p class="st-mensaje aviso">Esta versión guardó solo la tasa de los tramos A y E. Para ver los cinco, ejecuta el bloque 3 de <code>score_telefonico_fase6.sql</code>.</p>`}
        <section class="st-score-auc">
            <div><small>¿Ordena mejor que una regla simple?</small>
                <p>Si tomamos dos teléfonos de la misma cartera, uno que tuvo contacto y otro que no, el score pone primero al de contacto
                   el <strong>${m.auc_score_dentro_cartera ? num(m.auc_score_dentro_cartera * 100, 1) + "%" : "—"}</strong> de las veces
                   (la regla “primero el que tuvo CEF más reciente”: ${m.auc_regla_simple_dentro_cartera ? num(m.auc_regla_simple_dentro_cartera * 100, 1) + "%" : "—"}; al azar: 50%).
                   ${aucEnt ? `En ${esc(entidad)}: ${num(aucEnt * 100, 1)}% (regla simple ${reglaEnt ? num(reglaEnt * 100, 1) + "%" : "—"}).` : ""}</p></div>
        </section>
        <details class="st-score-pesos">
            <summary>Cómo se suman los puntos (${Object.keys(pesos).length} características)</summary>
            <p class="st-ayuda">Cada teléfono suma los puntos del tramo en que cae en cada característica; el score es esa suma ÷ ${num(cab.PuntosMaximos, 2)} (máximo posible) × 100.
               +20 puntos ≈ el doble de probabilidad relativa de CEF. La tasa es la observada en el entrenamiento, solo descriptiva.</p>
            <div class="st-pesos-grid">
                ${Object.entries(pesos).map(([car, lista]) => `<div class="st-peso">
                    <strong>${esc(CARACTERISTICA[car] || car)}</strong>
                    ${lista.map(p => `<div class="st-peso-fila"><span>${esc(p.Tramo)}</span><b>${num(p.Puntos, 1)} pts</b>
                        <small>${p.TasaExito !== null && p.TasaExito !== undefined ? num(p.TasaExito * 100, 1) + "% CEF" : ""}</small></div>`).join("")}
                </div>`).join("")}
            </div>
        </details>`;
}

async function abrirTelefono(dni, telefono) {
    $("tituloTelefono").textContent = `Por qué ${telefono} tiene este score`;
    $("cuerpoTelefono").innerHTML = `<p class="st-vacio">Cargando…</p>`;
    abrirModal("modalTelefono");
    try {
        const d = await pedir(`${API}/score/telefono?idcartera=${estado.idcartera}&dni=${encodeURIComponent(dni)}&telefono=${encodeURIComponent(telefono)}`);
        let version = null;
        try { version = await cargarScoreVersion(); } catch (e) { version = null; }
        $("cuerpoTelefono").innerHTML = htmlTelefono(d, version);
    } catch (error) {
        if (error instanceof SesionInvalidaError) return;
        $("cuerpoTelefono").innerHTML = `<p class="st-mensaje error">${esc(error.message)}</p>`;
    }
}

function htmlTelefono(d, version) {
    const s = d.score || {};
    const rangos = rangosTramo(version?.cabecera);
    const porTramo = Object.fromEntries((version?.metricas?.tasa_por_tramo || []).map(x => [x.tramo, x]));
    const tasaTramo = porTramo[s.Tramo]?.tasa_cef_pct;
    const filas = [...(d.detalle || [])].sort((a, b) => b.Puntos - a.Puntos).map(x => `<tr>
        <td>${esc(CARACTERISTICA[x.Caracteristica] || x.Caracteristica)}</td>
        <td><strong>${esc(x.Tramo ?? "—")}</strong>${x.TramoConocido ? "" : ` <small title="Valor que la versión no conoce: suma los puntos por defecto">(no visto)</small>`}</td>
        <td class="num"><strong>${num(x.Puntos, 1)}</strong> <small>de ${num(x.Maximo, 1)}</small></td>
        <td><div class="st-barra-tasa st-barra-puntos"><div style="width:${x.Maximo ? Math.max(0, x.Puntos / x.Maximo * 100) : 0}%"></div></div></td>
        <td class="num">${x.TasaExito !== null && x.TasaExito !== undefined ? `${num(x.TasaExito * 100, 1)}%` : "—"}</td>
    </tr>`).join("");
    return `
        <section class="st-tel-cab">
            <div><small>DNI</small><strong>${esc(d.dni)}</strong></div>
            <div><small>Teléfono</small><strong>${esc(d.telefono)}</strong></div>
            <div><small>Score</small><strong>${num(s.Score)}</strong></div>
            <div><small>Tramo</small><strong><span class="st-tag st-tramo-${esc(s.Tramo)}">${esc(s.Tramo)}</span> ${rangos[s.Tramo] ? `<small>(${esc(rangos[s.Tramo])})</small>` : ""}</strong></div>
            <div><small>Orden en el cliente</small><strong>${num(s.OrdenCliente)}</strong></div>
            <div><small>Corte del score</small><strong>${fecha(s.FechaScore)}</strong></div>
        </section>
        <p class="st-ayuda">Suma <strong>${num(d.puntos, 2)}</strong> de ${num(d.puntos_maximos, 2)} puntos posibles → ${num(d.score_calculado)} de 100.
            ${tasaTramo !== undefined ? `En la prueba, los teléfonos del tramo ${esc(s.Tramo)} tuvieron contacto directo la semana siguiente el <strong>${num(tasaTramo, 2)}%</strong> de las veces.` : ""}
            ${s.Descartado ? `<br><span class="st-no">Descartado: ${esc(s.MotivoDescarte || "")}</span>` : ""}</p>
        ${d.con_caracteristicas ? "" : `<p class="st-mensaje aviso">No se encontraron las características de este teléfono para ese corte.</p>`}
        <div class="st-tabla-wrap">
            <table class="st-tabla">
                <thead><tr><th>Característica</th><th>Valor del teléfono</th><th class="num">Puntos</th><th></th>
                    <th class="num" title="Tasa de CEF de ese valor en el entrenamiento (descriptiva)">Tasa CEF del valor</th></tr></thead>
                <tbody>${filas}</tbody>
            </table>
        </div>`;
}

// ------------------------------------------------------------------ carteras
function renderSelectorCartera() {
    const c = estado.carteras.find(x => Number(x.IdCartera) === estado.idcartera);
    $("carteraId").textContent = c ? c.IdCartera : "—";
    $("carteraNombre").textContent = c ? c.Nombre : "Sin carteras";
    $("carteraEntidad").textContent = c?.Entidad || "";
}

function renderMenuCarteras() {
    const q = $("txtBuscarCartera").value.trim().toLowerCase();
    const lista = estado.carteras.filter(c => !q || `${c.IdCartera} ${c.Nombre} ${c.Entidad || ""}`.toLowerCase().includes(q));
    const grupos = new Map();
    for (const c of lista) {
        const g = c.Entidad || "Carteras";
        if (!grupos.has(g)) grupos.set(g, []);
        grupos.get(g).push(c);
    }
    $("listaCarteras").innerHTML = lista.length ? [...grupos.entries()].map(([g, cs]) => `
        <div class="st-menu-grupo">${esc(g)}</div>
        ${cs.map(c => `<button type="button" role="option" class="st-menu-item ${Number(c.IdCartera) === estado.idcartera ? "on" : ""}" data-cartera="${c.IdCartera}">
            <span class="st-cartera-id">${esc(c.IdCartera)}</span>
            <span class="st-cartera-txt"><strong>${esc(c.Nombre)}</strong>
                <small>${c.Miembros ? `Junta ${c.Miembros.join(" + ")} · ` : ""}${c.EnCurso ? "Actualizándose ahora · " : ""}Actualizada ${fechaHora(c.UltimaActualizacion)} · ${num(c.ClientesUniverso)} clientes</small></span>
            ${c.Aviso ? `<span class="st-aviso-ico" title="${esc(c.Aviso)}">⚠</span>` : ""}
        </button>`).join("")}`).join("") : `<p class="st-vacio">Ninguna cartera coincide.</p>`;
}

function abrirMenuCarteras(abrir) {
    $("menuCartera").classList.toggle("hidden", !abrir);
    $("btnCartera").setAttribute("aria-expanded", String(abrir));
    if (abrir) {
        $("txtBuscarCartera").value = "";
        renderMenuCarteras();
        $("txtBuscarCartera").focus();
    }
}

async function cargarCarteras() {
    const { data } = await pedir(`${API}/carteras`);
    estado.carteras = data || [];
    if (!estado.carteras.length) {
        renderSelectorCartera();
        $("estadoCartera").textContent = "No tienes carteras con tabla de trabajo armada.";
        $("btnActualizar").disabled = true;
        return;
    }
    const guardada = Number(localStorage.getItem("gb_idcartera"));
    const id = estado.carteras.some(c => Number(c.IdCartera) === guardada) ? guardada : Number(estado.carteras[0].IdCartera);
    await elegirCartera(id);
}

function renderEstadoCartera() {
    const c = estado.carteras.find(x => Number(x.IdCartera) === estado.idcartera);
    if (!c) { $("estadoCartera").textContent = "—"; return; }
    const partes = [
        `<span>Actualizada <strong>${fechaHora(c.UltimaActualizacion)}</strong>${c.OrigenActualizacion ? ` <small>(${esc(c.OrigenActualizacion)})</small>` : ""}</span>`,
        `<span>Historial hasta <strong>${fecha(c.HistorialHasta)}</strong></span>`,
        `<span>Corte cliente <strong>${fecha(c.FechaCorteFuente)}</strong></span>`,
        c.Miembros ? `<span>Junta <strong>${c.Miembros.join(" + ")}</strong> (un cliente + teléfono en ambas va una vez)</span>` : "",
        `<span><strong>${num(c.ClientesUniverso)}</strong> clientes</span>`,
        `<span><strong>${num(c.Telefonos)}</strong> teléfonos con score</span>`,
        c.Version ? `<span>Score v${esc(c.Version)}</span>` : "",
    ];
    if (c.EnCurso) partes.unshift(`<span class="st-en-curso">Actualizándose ahora…</span>`);
    if (c.Aviso) partes.push(`<span class="st-aviso" title="${esc(c.Aviso)}">⚠ ${esc(String(c.Aviso).slice(0, 120))}</span>`);
    $("estadoCartera").innerHTML = partes.filter(Boolean).join("");
}

async function elegirCartera(idcartera) {
    estado.idcartera = idcartera;
    localStorage.setItem("gb_idcartera", String(idcartera));
    estado.desmarcados.clear();
    estado.condiciones = {};
    estado.segmentadores = null;
    estado.segmentadoresClave = null;
    estado.ultima = null;
    estado.recetaConsultada = null;
    estado.scoreVersion = null;
    estado.secuencia++;
    mostrarMensaje("");
    renderSelectorCartera();
    renderEstadoCartera();

    const c = estado.carteras.find(x => Number(x.IdCartera) === idcartera);
    cargaInicio("cartera", "Estamos trabajando en tu resultado", c ? `Preparando ${c.IdCartera} · ${c.Nombre}.` : "");
    try {
        estado.catalogo = await pedir(`${API}/catalogo?idcartera=${encodeURIComponent(idcartera)}`);
    } finally {
        cargaFin("cartera");
    }
    estado.campos = new Map((estado.catalogo.campos || []).map(c => [c.Codigo, c]));

    const canalPrevio = $("selCanal").value;
    $("selCanal").innerHTML = `<option value="">Elegir…</option>` + Object.entries(estado.catalogo.canales || {})
        .map(([codigo, nombre]) => `<option value="${esc(codigo)}">${esc(nombre)}</option>`).join("");
    if (canalPrevio && estado.catalogo.canales?.[canalPrevio]) $("selCanal").value = canalPrevio;

    if (estado.modalAbierto) construirMuro();
    recetaCambio({ inmediato: true });
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
        cargaInicio("actualizar", `Actualizando ${c.IdCartera} · ${c.Nombre}`,
            "Historial, score y datos del cliente. Puede tardar uno o varios minutos; no cierres la página.");
        try {
            const r = await postJson(`${API}/actualizar/${estado.idcartera}`, {});
            if (r.ocupada) {
                mostrarMensaje(r.mensaje || "La cartera ya se está actualizando.", "aviso");
            } else if (r.ok) {
                const seg = r.detalle?.Segundos;
                const aviso = r.detalle?.Aviso ? ` Aviso: ${r.detalle.Aviso}` : "";
                mostrarMensaje(`Cartera actualizada${seg ? ` en ${num(seg)} s` : ""}.${aviso}`, aviso ? "aviso" : "ok");
            } else {
                const det = r.detalle || {};
                mostrarMensaje(`La actualización terminó con estado ${det.Estado || "desconocido"}. ${det.Error || det.Aviso || ""}`.trim(), "error");
            }
            const { data } = await pedir(`${API}/carteras`);
            estado.carteras = data || [];
            renderEstadoCartera();
            estado.catalogo = await pedir(`${API}/catalogo?idcartera=${estado.idcartera}`);
            estado.campos = new Map((estado.catalogo.campos || []).map(x => [x.Codigo, x]));
            estado.scoreVersion = null;
            if (estado.modalAbierto) construirMuro();
            recetaCambio({ inmediato: true });
        } catch (error) {
            manejarError(error);
        } finally {
            cargaFin("actualizar");
        }
    });
}

// ------------------------------------------------------------------ generar
function abrirGenerar() {
    if (!$("selCanal").value) {
        mostrarMensaje("Elige el canal antes de generar la base.", "aviso");
        $("selCanal").focus();
        return;
    }
    const t = estado.ultima?.totales || {};
    $("resumenGenerar").innerHTML = `
        <div>Clientes<strong>${num(t.Clientes)}</strong></div>
        <div>Teléfonos<strong>${num(t.Telefonos)}</strong></div>
        <div>Canal<strong>${esc($("selCanal").selectedOptions[0]?.textContent || "")}</strong></div>`;
    $("resultadoGenerar").className = "st-resultado-generar hidden";
    $("btnConfirmarGenerar").classList.remove("hidden");
    try {
        const recordado = localStorage.getItem("gb_formato_archivo");
        if (recordado === "csv" || recordado === "xlsx") $("selFormatoArchivo").value = recordado;
    } catch (_) { /* sin almacenamiento: queda Excel */ }
    abrirModal("modalGenerar");
    proponerNombre();
}

// Nombre legible de la base (24/11/2026): el generador lo propone con lo principal de la receta y el usuario lo
// corrige. El código de la base (B123) se agrega solo al final al generar.
const NO_PERMITIDOS_NOMBRE = /[^A-Za-z0-9ÁÉÍÓÚÜÑáéíóúüñ \-_+]/g;
async function proponerNombre() {
    const caja = $("txtNombreBase");
    caja.value = "";
    caja.placeholder = "Armando el nombre…";
    try {
        const { nombre, codigo_probable } = await postJson(`${API}/nombre`, receta());
        caja.value = nombre || "";
        $("sufijoCodigo").textContent = codigo_probable || "B…";
    } catch (error) {
        if (error instanceof SesionInvalidaError) return;
        caja.placeholder = "No se pudo proponer: escríbelo";
    }
}

async function generar() {
    const boton = $("btnConfirmarGenerar");
    const caja = $("resultadoGenerar");
    await conBoton(boton, async () => {
        boton.textContent = "Generando…";
        cargaInicio("generar", "Generando la base", "Se registra cada teléfono con su código y se prepara el archivo.");
        try {
            const base = await postJson(`${API}/generar`, { ...receta(), descripcion: $("txtDescripcion").value.trim() || null,
                                                            nombre: $("txtNombreBase").value.trim() || null });
            caja.className = "st-resultado-generar";
            const formato = formatoArchivo();
            caja.innerHTML = `Base <strong>${esc(base.Codigo)}</strong> registrada: ${num(base.Clientes)} clientes, ${num(base.Telefonos)} teléfonos.<br>${esc(base.NombreArchivo)}.${formato}`;
            boton.classList.add("hidden");
            $("txtDescripcion").value = "";
            cargarHistorico();
            if (Number(base.Telefonos) !== Number(estado.ultima?.totales?.Telefonos)) {
                caja.innerHTML += `<br><small>La cantidad difiere de la pantalla: las condiciones del día se evalúan en vivo al generar.</small>`;
            }
            try {
                await descargarBase(base.IdBase, base.NombreArchivo, formato);
            } catch (error) {
                if (!(error instanceof SesionInvalidaError)) {
                    caja.innerHTML += `<br>La base quedó registrada, pero la descarga falló: ${esc(error.message)}. Descárgala desde el histórico.`;
                }
            }
        } catch (error) {
            if (error instanceof SesionInvalidaError) return;
            caja.className = "st-resultado-generar error";
            caja.textContent = error.message || "No se pudo generar la base.";
        } finally {
            cargaFin("generar");
        }
    });
}

// Formato del archivo: Excel o CSV delimitado por comas. Se recuerda en este navegador.
function formatoArchivo() {
    const valor = $("selFormatoArchivo")?.value === "csv" ? "csv" : "xlsx";
    try { localStorage.setItem("gb_formato_archivo", valor); } catch (_) { /* sin almacenamiento: no pasa nada */ }
    return valor;
}

function descargarBase(idBase, nombre, formato) {
    return descargarArchivoConSesion(`${API}/bases/${idBase}/archivo?formato=${formato}`, `${nombre}.${formato}`);
}

// ------------------------------------------------------------------ histórico
async function cargarHistorico() {
    const tbody = $("tbodyHistorico");
    try {
        const { data } = await pedir(`${API}/bases?idcartera=${estado.idcartera}&dias=30`);
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
            <td class="st-descargas">
                <button type="button" class="st-btn sm" data-descargar="${esc(b.IdBase)}" data-nombre="${esc(b.NombreArchivo)}" data-formato="xlsx" title="Descargar en Excel">Excel</button>
                <button type="button" class="st-btn sm" data-descargar="${esc(b.IdBase)}" data-nombre="${esc(b.NombreArchivo)}" data-formato="csv" title="Descargar CSV delimitado por comas">CSV</button>
            </td>
        </tr>`).join("") : `<tr><td colspan="9" class="st-vacio">Todavía no hay bases generadas para esta cartera.</td></tr>`;
    } catch (error) {
        if (error instanceof SesionInvalidaError) return;
        tbody.innerHTML = `<tr><td colspan="9" class="st-vacio">${esc(error.message)}</td></tr>`;
    }
}

// ------------------------------------------------------------------ eventos
function enlazarEventos() {
    $("btnCartera").addEventListener("click", () => abrirMenuCarteras($("menuCartera").classList.contains("hidden")));
    $("txtBuscarCartera").addEventListener("input", renderMenuCarteras);
    $("txtBuscarCartera").addEventListener("keydown", e => {
        if (e.key === "Enter") document.querySelector("#listaCarteras [data-cartera]")?.click();
    });
    $("listaCarteras").addEventListener("click", e => {
        const item = e.target.closest("[data-cartera]");
        if (!item) return;
        abrirMenuCarteras(false);
        if (Number(item.dataset.cartera) !== estado.idcartera) elegirCartera(Number(item.dataset.cartera)).catch(manejarError);
    });
    $("btnActualizar").addEventListener("click", actualizarCartera);
    $("selCanal").addEventListener("change", () => {
        if (estado.condiciones.ENVIADO_HOY) recetaCambio({ inmediato: true }); else actualizarBotonGenerar();
    });
    $("selPorCliente").addEventListener("change", () => recetaCambio({ inmediato: true }));
    $("btnLimpiar").addEventListener("click", limpiarTodo);
    $("btnLimpiarModal").addEventListener("click", limpiarTodo);
    $("btnDesmarcarTodo").addEventListener("click", desmarcarTodo);
    $("btnGenerar").addEventListener("click", abrirGenerar);
    $("btnConfirmarGenerar").addEventListener("click", generar);
    $("btnProponerNombre").addEventListener("click", proponerNombre);
    $("txtNombreBase").addEventListener("input", e => {
        const limpio = e.target.value.replace(NO_PERMITIDOS_NOMBRE, " ");
        if (limpio !== e.target.value) e.target.value = limpio;   // sin puntos, comas, | ni /
    });
    $("btnRecargarHistorico").addEventListener("click", cargarHistorico);
    $("btnAnterior").addEventListener("click", () => paginar(estado.pagina - 1));
    $("btnSiguiente").addEventListener("click", () => paginar(estado.pagina + 1));
    $("selTop").addEventListener("change", () => { estado.pagina = 1; paginar(1); });
    $("btnFiltros").addEventListener("click", abrirFiltros);
    $("btnScoreInfo").addEventListener("click", abrirScore);
    $("txtBuscarSeg").addEventListener("input", buscarFiltro);
    $("chkSoloActivos").addEventListener("change", filtrarTiles);
    $("tabsFiltros").addEventListener("click", e => {
        const tab = e.target.closest("[data-pestana]");
        if (tab) cambiarPestana(tab.dataset.pestana);
    });
    $("tbodyFilas").addEventListener("click", e => {
        const b = e.target.closest(".st-score-btn");
        if (b) abrirTelefono(b.dataset.dni, b.dataset.telefono);
    });

    const muro = $("muro");
    muro.addEventListener("change", e => {
        const caja = e.target.closest("input[type=checkbox][data-valor]");
        if (caja) alternarValor(caja.dataset.campo, caja.dataset.valor, caja.checked);
    });
    muro.addEventListener("click", e => {
        const accion = e.target.closest("[data-accion]");
        if (accion) return accionValores(accion.dataset.campo, accion.dataset.accion);
        const cond = e.target.closest("[data-condicion]");
        if (cond) return cambiarCondicion(cond.dataset.condicion, cond.dataset.modo);
        const ayuda = e.target.closest("[data-ayuda], [data-ayuda-cond]");
        if (ayuda) { e.preventDefault(); mostrarAyuda(ayuda); }
    });
    muro.addEventListener("mouseover", e => {
        const ayuda = e.target.closest("[data-ayuda], [data-ayuda-cond]");
        if (ayuda) mostrarAyuda(ayuda);
    });
    muro.addEventListener("mouseout", e => {
        if (e.target.closest("[data-ayuda], [data-ayuda-cond]")) ocultarAyuda();
    });
    muro.addEventListener("input", e => {
        if (e.target.dataset.buscarValor) { renderValores(e.target.dataset.buscarValor); ajustarMosaico(); }
    });
    muro.addEventListener("scroll", ocultarAyuda);

    $("chips").addEventListener("click", e => {
        const f = e.target.closest("[data-quitar-filtro]");
        const c = e.target.closest("[data-quitar-condicion]");
        if (f) limpiarCampo(f.dataset.quitarFiltro);
        if (c) cambiarCondicion(c.dataset.quitarCondicion, "INDIFERENTE");
    });

    $("tbodyHistorico").addEventListener("click", e => {
        const b = e.target.closest("[data-descargar]");
        if (!b) return;
        conBoton(b, () => descargarBase(b.dataset.descargar, b.dataset.nombre, b.dataset.formato === "csv" ? "csv" : "xlsx")
            .catch(manejarError));
    });

    document.addEventListener("click", e => {
        const cerrar = e.target.closest("[data-cerrar]");
        if (cerrar) cerrarModal(cerrar.dataset.cerrar);
        else if (e.target.classList?.contains("st-modal")) cerrarModal(e.target.id);
        if (!e.target.closest(".st-selcartera")) abrirMenuCarteras(false);
    });
    document.addEventListener("keydown", e => {
        if (e.key !== "Escape") return;
        if (!$("menuCartera").classList.contains("hidden")) return abrirMenuCarteras(false);
        const abiertos = [...document.querySelectorAll(".st-modal:not(.hidden)")];
        if (abiertos.length) cerrarModal(abiertos[abiertos.length - 1].id);
    });
    let esperaResize = null;
    window.addEventListener("resize", () => { clearTimeout(esperaResize); esperaResize = setTimeout(ajustarMosaico, 150); });
}

document.addEventListener("DOMContentLoaded", async () => {
    // La grúa sale desde el inicio; si el servidor no responde, se dice (15/11/2026: la página quedaba en
    // "Cargando carteras…" sin explicación cuando el backend estaba ocupado).
    $("btnSeguirSinEsperar").addEventListener("click", () => {
        carga.omitida = true;
        $("cargando").classList.add("hidden");
        $("btnSeguirSinEsperar").classList.add("hidden");
    });
    cargaInicio("inicio", "Estamos trabajando en tu resultado", "Conectando con el servidor.");
    const lento = setTimeout(() => {
        $("cargandoDetalle").textContent = "El servidor está tardando en responder. Si sigue así, puede estar ocupado con "
            + "una consulta anterior: reinicia el backend del CRM.";
    }, 15000);
    const sesionOk = typeof asegurarSesionBackend === "function" && await asegurarSesionBackend();
    clearTimeout(lento);
    if (!sesionOk) { cargaFin("inicio"); return; }   // session.js redirige o muestra el error
    enlazarEventos();
    cargaInicio("inicio", "Estamos trabajando en tu resultado", "Cargando tus carteras.");
    try {
        await cargarCarteras();
    } catch (error) {
        manejarError(error);
    } finally {
        cargaFin("inicio");
    }
});
