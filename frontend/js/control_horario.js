const BASE_URL_CONTROL = `${window.location.protocol}//${window.location.hostname}:8000`;

let dataControlHorario = {
    detalle: [],
    kpis: {},
    top_avance: [],
    pendientes_criticos: [],
    alertas: [],
    horas: [],
    agente_hora: []
};

let resumenCarteras = [];
let resumenOpcionesCarteras = [];
let carteraSeleccionada = null;
let carteraFiltroControl = null;
let idsFiltroCarteraControl = [];
let etiquetaFiltroCarteraControl = "";
let agenteSeleccionado = null;
let metricaHoraActual = "gestiones";
let ordenResumen = { campo: "gestiones", direccion: "desc" };
let ordenAgentes = { campo: "cef", direccion: "desc" };
let ordenAgenteHora = { campo: "gestiones", direccion: "desc" };
let vistaCarteraControl = "AGRUPADO";

const CACHE_CONTROL_HORARIO = "controlHorarioCacheV5";

const CARTERAS_CONTROL = {
    112: "MIBANCO 1",
    143: "MIBANCO 2",
    135: "MIBANCO VIGENTE",
    124: "COMPARTAMOS CASTIGO INDIVIDUAL",
    144: "COMPARTAMOS CASTIGO GRUPAL",
    126: "COMPARTAMOS VIGENTE INDIVIDUAL",
    128: "COMPARTAMOS VIGENTE CCM",
    133: "COMPARTAMOS VIGENTE GRUPAL / CSM",
    117: "INTERBANK",
    132: "FINANCIERA OH",
    137: "INTERBANK CEDIDA"
};

const GRUPOS_CARTERA_CONTROL = [
    { key: "MIBANCO", cartera: "MIBANCO", ids: ["112", "143", "135"] },
    { key: "COMPARTAMOS_VIGENTE", cartera: "COMPARTAMOS VIGENTE", ids: ["126", "128", "133"] },
    { key: "COMPARTAMOS_CASTIGO", cartera: "COMPARTAMOS CASTIGO", ids: ["124", "144"] }
];

const CAMPOS = {
    idcartera: ["IDCARTERA", "IdCartera", "idcartera", "ID_CARTERA"],
    cartera: ["CARTERA", "cartera", "NOM_CARTERA", "nombre_cartera"],
    idusuario: ["IDUSUARIO", "IdUsuario", "idusuario", "ID_USUARIO"],
    agente: ["AGENTE", "agente", "nombre_agente"],
    hora: ["HORA", "hora", "HORA_CORTE", "hora_corte", "TRAMO_HORA", "tramo_hora", "TRAMO", "tramo", "CORTE", "corte", "HORARIO", "horario", "RANGO_HORA", "rango_hora", "HORA_GESTION", "hora_gestion"],
    gestiones: ["GESTIONES", "gestiones", "TOTAL_GESTIONES", "total_gestiones"],
    clientesMes: ["CLIENTES_GESTIONADOS_MES", "clientes_gestionados_mes", "CLIENTES_MES", "clientes_mes"],
    cef: ["CEF", "cef"],
    cne: ["CNE", "cne"],
    noc: ["NOC", "noc"],
    pctCef: ["PCT_CEF", "PORC_CEF", "% CEF", "pct_cef", "porcentaje_cef"],
    qPdp: ["Q_PDP_GEN", "q_pdp_gen", "Q_PDP", "q_pdp", "pdp_generadas", "PDP_GENERADAS"],
    pdpGenerado: ["PDP_GEN", "pdp_gen", "PDP_GENERADO", "pdp_generado", "MONTO_GENERADO", "monto_generado", "MONTO_PDP_GENERADO", "monto_pdp_generado", "MONTO_PDP", "monto_pdp", "MONTO_PDP_GEN", "monto_pdp_gen", "MONTO_GENERADO_PDP", "monto_generado_pdp", "MONTO_GENERADO_HORA", "monto_generado_hora", "PDP_GEN_MONTO", "pdp_gen_monto"],
    proyectado: ["PROYECTADO", "proyectado", "PROYECTADO_HOY", "proyectado_hoy", "MONTO_PROYECTADO", "monto_proyectado"],
    pago: ["PAGO", "pago", "PAGO_HOY", "pago_hoy", "MONTO_PAGO", "monto_pago"],
    pendiente: ["PENDIENTE", "pendiente", "PENDIENTE_HOY", "pendiente_hoy", "MONTO_PENDIENTE", "monto_pendiente"],
    avance: ["AVANCE", "avance", "AVANCE_DIA", "avance_dia", "PORC_AVANCE", "porc_avance"],
    tc: ["TC", "tc"],
    color: ["COLOR_ACCION", "color_accion", "color"],
    accion: ["ACCION", "accion"],
    ultimaGestion: ["ULTIMA_GESTION", "ultima_gestion", "ultima_fecha"]
};

document.addEventListener("DOMContentLoaded", () => {
    if (!exigirSesion()) return;

    const vistaCartera = document.getElementById("filtroVistaCartera");
    if (vistaCartera) {
        vistaCartera.value = vistaCarteraControl;
        vistaCartera.addEventListener("change", cambiarVistaCartera);
    }

    const fecha = document.getElementById("filtroFecha");
    if (fecha && !fecha.value) {
        fecha.value = fechaLocalInput();
    }

    cargarCacheControlHorario();
    cargarControlHorario();
});

async function cargarControlHorario() {
    const fecha = document.getElementById("filtroFecha")?.value;

    try {
        mostrarToast("Actualizando control horario...", "info");

        const data = await obtenerDataControlHorario(fecha);
        procesarDataControlHorario(data);
        guardarCacheControlHorario(fecha || "");
        mostrarToast("Control horario actualizado.", "ok");
    } catch (error) {
        console.error("ERROR CONTROL HORARIO:", error);
        mostrarToast(`No se pudo cargar el control horario. ${error.message || ""}`, "error");
    }
}

async function obtenerDataControlHorario(fecha) {
    const idsSupervisor = carterasPermitidasSupervisor();

    if (idsSupervisor.length) {
        const idsConsulta = idsSupervisor;

        if (!idsConsulta.length) {
            return dataVaciaControlHorario();
        }

        const respuestas = await Promise.all(idsConsulta.map(id => fetchControlHorario(fecha, id)));
        return unirRespuestasControlHorario(respuestas);
    }

    return fetchControlHorario(fecha, "");
}

async function fetchControlHorario(fecha, idcartera) {
    const params = new URLSearchParams();
    if (fecha) params.set("fecha", fecha);
    if (idcartera) params.set("idcartera", idcartera);

    const response = await fetch(`${BASE_URL_CONTROL}/control-horario/resumen?${params.toString()}`, {
        cache: "no-store"
    });
    if (!response.ok) throw new Error(`Error HTTP ${response.status}`);
    return response.json();
}

function unirRespuestasControlHorario(respuestas) {
    const base = dataVaciaControlHorario();

    respuestas.forEach(data => {
        base.detalle.push(...(data.detalle || []));
        base.top_avance.push(...(data.top_avance || []));
        base.pendientes_criticos.push(...(data.pendientes_criticos || []));
        base.alertas.push(...(data.alertas || []));
        base.horas.push(...(data.horas || []));
        base.agente_hora.push(...(data.agente_hora || []));
        base.kpis = sumarKpisControl(base.kpis, data.kpis || {});

        Object.entries(data.dotacion_grupos || {}).forEach(([key, value]) => {
            base.dotacion_grupos[key] = (base.dotacion_grupos[key] || 0) + Number(value || 0);
        });
    });

    return base;
}

function dataVaciaControlHorario() {
    return {
        detalle: [],
        kpis: {},
        top_avance: [],
        pendientes_criticos: [],
        alertas: [],
        horas: [],
        agente_hora: [],
        dotacion_grupos: {}
    };
}

function sumarKpisControl(actual, nuevo) {
    const resultado = { ...actual };
    const sumables = [
        "GESTIONES_ACUMULADAS",
        "CLIENTES_GESTIONADOS_MES",
        "CEF_ACUMULADOS",
        "CNE_ACUMULADOS",
        "NOC_ACUMULADOS",
        "Q_PDP_GENERADAS",
        "PDP_GENERADO",
        "Q_PROYECTADO_HOY",
        "PROYECTADO_HOY",
        "Q_PAGADOS_HOY",
        "PAGO_HOY",
        "PENDIENTE_HOY",
        "AGENTES_TOTAL",
        "AGENTES_CRITICOS",
        "AGENTES_SIN_GESTION",
        "AGENTES_SIN_PDP"
    ];

    sumables.forEach(key => {
        resultado[key] = Number(resultado[key] || 0) + Number(nuevo[key] || 0);
    });

    resultado.FECHA = resultado.FECHA || nuevo.FECHA;
    resultado.MES_INICIO = resultado.MES_INICIO || nuevo.MES_INICIO;
    resultado.ULTIMO_CORTE = maxHoraTexto(resultado.ULTIMO_CORTE, nuevo.ULTIMO_CORTE);
    resultado.PORC_CEF_GENERAL = resultado.GESTIONES_ACUMULADAS > 0
        ? (resultado.CEF_ACUMULADOS * 100) / resultado.GESTIONES_ACUMULADAS
        : 0;
    resultado.TC_GENERAL = resultado.CEF_ACUMULADOS > 0
        ? (resultado.Q_PDP_GENERADAS * 100) / resultado.CEF_ACUMULADOS
        : 0;
    resultado.AVANCE_DIA = resultado.PROYECTADO_HOY > 0
        ? (resultado.PAGO_HOY * 100) / resultado.PROYECTADO_HOY
        : 0;

    return resultado;
}

function maxHoraTexto(a, b) {
    if (!a) return b || "";
    if (!b) return a || "";
    return String(a) > String(b) ? a : b;
}

function fechaLocalInput(date = new Date()) {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, "0");
    const day = String(date.getDate()).padStart(2, "0");
    return `${year}-${month}-${day}`;
}

function carterasPermitidasSupervisor() {
    const tipo = typeof normalizarTipoUsuario === "function"
        ? normalizarTipoUsuario(localStorage.getItem("tipo"))
        : String(localStorage.getItem("tipo") || "").trim().toUpperCase();

    if (tipo !== "SUPERVISOR") return [];

    const ids = typeof obtenerIdCarterasSesion === "function"
        ? obtenerIdCarterasSesion()
        : [
            ...(localStorage.getItem("idcarteras") || "").split(","),
            localStorage.getItem("idcartera")
        ];

    return [...new Set(ids.map(id => String(id || "").trim()).filter(id => /^\d+$/.test(id)))];
}

function grupoPermitidoParaSupervisor(item, idsSupervisor) {
    const idsGrupo = String(item.ids_cartera || item.IDS_CARTERA_GRUPO || item.idcartera || "")
        .split(",")
        .map(id => id.trim())
        .filter(Boolean);

    return idsGrupo.some(id => idsSupervisor.includes(id)) || idsSupervisor.includes(String(item.idcartera));
}

function definirGrupoCartera(row) {
    const id = String(getIdCarteraBase(row) || "").trim();
    if (!id) return null;

    if (modoVistaCarteraActual() === "AGRUPADO") {
        const grupo = GRUPOS_CARTERA_CONTROL.find(item => item.ids.includes(id));
        if (grupo) {
            return {
                idcartera: grupo.key,
                cartera: grupo.cartera,
                ids: grupo.ids
            };
        }
    }

    return {
        idcartera: id,
        cartera: CARTERAS_CONTROL[id] || getCartera(row, id),
        ids: [id]
    };
}

function modoVistaCarteraActual() {
    const select = document.getElementById("filtroVistaCartera");
    vistaCarteraControl = select?.value || vistaCarteraControl || "AGRUPADO";
    return vistaCarteraControl;
}

function idsCarteraSeleccionada() {
    if (carteraSeleccionada) {
        const resumen = resumenDeCartera(carteraSeleccionada);
        if (resumen?.ids?.length) return resumen.ids.map(String);
        return String(carteraSeleccionada).split(",").map(id => id.trim()).filter(Boolean);
    }

    return idsFiltroCarteraControl.map(String);
}

function rowPerteneceACarteraSeleccionada(row) {
    const ids = idsCarteraSeleccionada();
    if (!ids.length) return true;
    return ids.includes(String(getIdCarteraBase(row)));
}

function procesarDataControlHorario(data) {
    dataControlHorario = data || {};
    modoVistaCarteraActual();
    resumenOpcionesCarteras = construirResumenCarteras(detalleFiltradoPorAgente(dataControlHorario.detalle || []));
    resumenCarteras = construirResumenVisible();
    poblarFiltros();
    renderVista();
}

function cargarCacheControlHorario() {
    try {
        const raw = sessionStorage.getItem(CACHE_CONTROL_HORARIO);
        if (!raw) return;

        const cache = JSON.parse(raw);
        if (!cache?.data) return;
        if (cache.fecha) {
            const fecha = document.getElementById("filtroFecha");
            if (fecha && !fecha.value) fecha.value = cache.fecha;
        }

        procesarDataControlHorario(cache.data);
        mostrarToast("Mostrando ultimo corte guardado mientras se actualiza.", "info");
    } catch (error) {
        console.warn("Cache control horario invalido:", error);
    }
}

function guardarCacheControlHorario(fecha) {
    try {
        sessionStorage.setItem(CACHE_CONTROL_HORARIO, JSON.stringify({
            fecha,
            data: dataControlHorario,
            guardado: new Date().toISOString()
        }));
    } catch (error) {
        console.warn("No se pudo guardar cache de control horario:", error);
    }
}

function aplicarFiltroCartera() {
    modoVistaCarteraActual();
    const select = document.getElementById("filtroCartera");
    const idcartera = select?.value || "";
    if (!idcartera || idcartera === "__FILTRO_ACTUAL__") {
        if (!idcartera) limpiarFiltroCarteraControl();
    } else {
        const resumen = resumenOpcionesCarteras.find(item => String(item.idcartera) === String(idcartera));
        carteraFiltroControl = idcartera;
        idsFiltroCarteraControl = resumen?.ids?.map(String) || [String(idcartera)];
        etiquetaFiltroCarteraControl = resumen?.cartera || select?.selectedOptions?.[0]?.textContent || String(idcartera);
    }

    carteraSeleccionada = null;
    resumenCarteras = construirResumenVisible();
    poblarFiltroCarteras();
    poblarFiltroAgentes();
    renderVista();
}

function aplicarFiltroAgente() {
    modoVistaCarteraActual();
    agenteSeleccionado = document.getElementById("filtroAgente")?.value || null;
    resumenOpcionesCarteras = construirResumenCarteras(detalleFiltradoPorAgente(dataControlHorario.detalle || []));
    resumenCarteras = construirResumenVisible();
    renderVista();
}

function cambiarVistaCartera() {
    modoVistaCarteraActual();
    carteraSeleccionada = null;
    resumenOpcionesCarteras = construirResumenCarteras(detalleFiltradoPorAgente(dataControlHorario.detalle || []));
    resumenCarteras = construirResumenVisible();
    poblarFiltros();
    renderVista();
}

function construirResumenVisible() {
    const detalle = detalleFiltradoPorAgente(dataControlHorario.detalle || []);
    const scoped = idsFiltroCarteraControl.length
        ? detalle.filter(row => idsFiltroCarteraControl.includes(String(getIdCarteraBase(row))))
        : detalle;

    return construirResumenCarteras(scoped);
}

function poblarFiltros() {
    poblarFiltroCarteras();
    poblarFiltroAgentes();
}

function poblarFiltroCarteras() {
    const select = document.getElementById("filtroCartera");
    modoVistaCarteraActual();
    const actual = carteraFiltroControl || select.value;
    const idsSupervisor = carterasPermitidasSupervisor();

    const opciones = resumenOpcionesCarteras
        .filter(item => !idsSupervisor.length || grupoPermitidoParaSupervisor(item, idsSupervisor))
        .map(item => ({ id: item.idcartera, texto: item.ids?.length > 1 ? item.cartera : `${item.idcartera} - ${item.cartera}` }))
        .sort((a, b) => String(a.texto).localeCompare(String(b.texto), "es"));
    const existeActual = opciones.some(item => String(item.id) === String(actual));
    const opcionFiltroActual = idsFiltroCarteraControl.length && !existeActual && !select.value
        ? `<option value="__FILTRO_ACTUAL__">Filtro actual: ${h(etiquetaFiltroCarteraControl || idsFiltroCarteraControl.join(", "))}</option>`
        : "";

    select.innerHTML = `<option value="">${vistaCarteraControl === "AGRUPADO" ? "Todas las carteras agrupadas" : "Todas las carteras detalladas"}</option>` + opcionFiltroActual + opciones.map(item =>
        `<option value="${h(item.id)}">${h(item.texto)}</option>`
    ).join("");

    select.value = existeActual ? actual : (opcionFiltroActual ? "__FILTRO_ACTUAL__" : "");
    carteraFiltroControl = select.value && select.value !== "__FILTRO_ACTUAL__" ? select.value : carteraFiltroControl;
    select.disabled = idsSupervisor.length === 1 && vistaCarteraControl === "DETALLADO";
    if (idsSupervisor.length === 1 && opciones.length === 1) {
        select.value = opciones[0].id;
        carteraFiltroControl = opciones[0].id;
        idsFiltroCarteraControl = resumenOpcionesCarteras.find(item => String(item.idcartera) === String(opciones[0].id))?.ids?.map(String) || [String(opciones[0].id)];
        etiquetaFiltroCarteraControl = opciones[0].texto;
    }
}

function poblarFiltroAgentes() {
    const select = document.getElementById("filtroAgente");
    const actual = select.value;
    const idsFiltro = idsFiltroCarteraControl.map(String);

    const agentes = new Map();
    (dataControlHorario.detalle || []).forEach(row => {
        if (idsFiltro.length && !idsFiltro.includes(String(getIdCarteraBase(row)))) return;

        const idusuario = valor(row, CAMPOS.idusuario, "");
        const agente = valor(row, CAMPOS.agente, "");
        if (!idusuario || !agente) return;

        agentes.set(String(idusuario), `${idusuario} - ${agente}`);
    });

    const opciones = [...agentes.entries()]
        .map(([id, texto]) => ({ id, texto }))
        .sort((a, b) => String(a.texto).localeCompare(String(b.texto), "es"));

    select.innerHTML = `<option value="">Todos los agentes</option>` + opciones.map(item =>
        `<option value="${h(item.id)}">${h(item.texto)}</option>`
    ).join("");

    select.value = opciones.some(item => String(item.id) === String(actual)) ? actual : "";
    agenteSeleccionado = select.value || null;
}

function renderVista() {
    modoVistaCarteraActual();
    resumenOpcionesCarteras = construirResumenCarteras(detalleFiltradoPorAgente(dataControlHorario.detalle || []));
    resumenCarteras = construirResumenVisible();
    if (carteraSeleccionada && !resumenDeCartera(carteraSeleccionada)) {
        carteraSeleccionada = null;
    }

    const detalle = detalleActual();
    const resumen = carteraSeleccionada ? resumenDeCartera(carteraSeleccionada) : null;

    renderKpis(calcularKpis(detalle, resumen));
    renderResumenCarteras(resumenCarteras);
    renderDetalleAgentes(agruparDetalleAgentes(detalle));
    renderPanelDerecho(detalle);
    renderGraficoHoras(horasActuales());
    actualizarContexto();
}

function seleccionarCartera(idcartera) {
    carteraSeleccionada = String(idcartera);
    renderVista();
}

function volverResumenCarteras() {
    carteraSeleccionada = null;
    renderVista();
}

function limpiarFiltroCarteraControl() {
    carteraFiltroControl = null;
    idsFiltroCarteraControl = [];
    etiquetaFiltroCarteraControl = "";
}

function actualizarContexto() {
    const resumenCard = document.getElementById("resumenCarterasCard");
    const detalleCard = document.getElementById("detalleAgentesCard");
    const subtitulo = document.getElementById("subtituloControl");
    const subtituloHoras = document.getElementById("subtituloHoras");

    if (carteraSeleccionada) {
        const cartera = resumenDeCartera(carteraSeleccionada);
        resumenCard.classList.add("compact-mode");
        detalleCard.classList.remove("hidden");
        document.getElementById("tituloDetalleAgentes").innerText =
            `Detalle de agentes - ${cartera?.cartera || carteraSeleccionada}`;
        setSubtituloControl(cartera
            ? `Cartera seleccionada: ${cartera.cartera}`
            : `Cartera seleccionada: ${carteraSeleccionada}`);
        subtituloHoras.innerText = "Corte horario filtrado por la cartera seleccionada.";
        document.getElementById("tituloTopAvance").innerText = "Top 5 agentes con mejor avance";
        document.getElementById("tituloPendientes").innerText = "Top 5 agentes con mayor pendiente";
        return;
    }

    resumenCard.classList.remove("compact-mode");
    detalleCard.classList.add("hidden");
    setSubtituloControl(idsFiltroCarteraControl.length
        ? `Filtro cartera: ${etiquetaFiltroCarteraControl || idsFiltroCarteraControl.join(", ")}`
        : "Seguimiento operativo en tiempo real.");
    subtituloHoras.innerText = idsFiltroCarteraControl.length
        ? "Corte horario filtrado por la cartera seleccionada."
        : "Gestion y generacion por tramo horario.";
    document.getElementById("tituloTopAvance").innerText = "Top 5 carteras con mejor avance";
    document.getElementById("tituloPendientes").innerText = "Top 5 carteras con mayor pendiente";
}

function setSubtituloControl(texto) {
    const subtitulo = document.getElementById("subtituloControl");
    const corte = valor(dataControlHorario.kpis || {}, ["ULTIMO_CORTE", "ultimo_corte"], "");
    subtitulo.innerHTML = `${h(texto)}${corte ? ` <span class="last-cut">Ultimo corte: ${h(corte)}</span>` : ""}`;
}

function detalleActual() {
    const detalle = detalleFiltradoPorAgente(dataControlHorario.detalle || []);
    const ids = idsCarteraSeleccionada();
    if (!ids.length) return detalle;
    return detalle.filter(rowPerteneceACarteraSeleccionada);
}

function agruparDetalleAgentes(detalle) {
    const map = new Map();

    detalle.forEach(row => {
        if (numeroCampo(row, CAMPOS.gestiones) <= 0) return;

        const idusuario = String(valor(row, CAMPOS.idusuario, valor(row, CAMPOS.agente, "")));
        if (!idusuario) return;

        const actual = map.get(idusuario) || {
            ...row,
            GESTIONES: 0,
            CLIENTES_GESTIONADOS_MES: 0,
            CEF: 0,
            CNE: 0,
            NOC: 0,
            Q_PDP_GEN: 0,
            PDP_GEN: 0,
            PROYECTADO: 0,
            PAGO: 0,
            PENDIENTE: 0,
            Q_PROYECTADO: 0,
            Q_PAGADOS: 0,
            Q_PENDIENTES: 0
        };

        actual.GESTIONES += numeroCampo(row, CAMPOS.gestiones);
        actual.CLIENTES_GESTIONADOS_MES += numeroCampo(row, CAMPOS.clientesMes);
        actual.CEF += numeroCampo(row, CAMPOS.cef);
        actual.CNE += numeroCampo(row, CAMPOS.cne);
        actual.NOC += numeroCampo(row, CAMPOS.noc);
        actual.Q_PDP_GEN += numeroCampo(row, CAMPOS.qPdp);
        actual.PDP_GEN += getPdpGenerado(row);
        actual.PROYECTADO += numeroCampo(row, CAMPOS.proyectado);
        actual.PAGO += numeroCampo(row, CAMPOS.pago);
        actual.PENDIENTE += numeroCampo(row, CAMPOS.pendiente);
        actual.Q_PROYECTADO += numeroCampo(row, ["Q_PROYECTADO", "q_proyectado"]);
        actual.Q_PAGADOS += numeroCampo(row, ["Q_PAGADOS", "q_pagados"]);
        actual.Q_PENDIENTES += numeroCampo(row, ["Q_PENDIENTES", "q_pendientes"]);
        actual.PORC_CEF = actual.GESTIONES > 0 ? (actual.CEF * 100) / actual.GESTIONES : 0;
        actual.AVANCE = actual.PROYECTADO > 0 ? (actual.PAGO * 100) / actual.PROYECTADO : 0;
        actual.TC = actual.CEF > 0 ? (actual.Q_PDP_GEN * 100) / actual.CEF : 0;

        map.set(idusuario, actual);
    });

    return ordenarFilas([...map.values()].map(row => ({
        ...row,
        ...evaluarAccionAgente(row)
    })), ordenAgentes, valorOrdenAgente);
}

function detalleFiltradoPorAgente(detalle) {
    if (!agenteSeleccionado) return detalle;
    return detalle.filter(row => String(valor(row, CAMPOS.idusuario, "")) === String(agenteSeleccionado));
}

function construirResumenCarteras(detalle) {
    const map = new Map();

    detalle.forEach(row => {
        const grupo = definirGrupoCartera(row);
        if (!grupo) return;

        const key = String(grupo.idcartera);
        const actual = map.get(key) || {
            idcartera: key,
            cartera: grupo.cartera,
            ids: grupo.ids,
            ids_cartera: grupo.ids.join(","),
            gestiones: 0,
            clientes_mes: 0,
            cef: 0,
            pdp_generado: 0,
            proyectado: 0,
            pago: 0,
            pendiente: 0,
            criticos: 0,
            agentes: 0,
            agentes_activos: 0
        };

        actual.gestiones += numeroCampo(row, CAMPOS.gestiones);
        actual.clientes_mes += numeroCampo(row, CAMPOS.clientesMes);
        actual.cef += numeroCampo(row, CAMPOS.cef);
        actual.pdp_generado += getPdpGenerado(row);
        actual.proyectado += numeroCampo(row, CAMPOS.proyectado);
        actual.pago += numeroCampo(row, CAMPOS.pago);
        actual.pendiente += numeroCampo(row, CAMPOS.pendiente);
        actual.criticos += esCritico(row) ? 1 : 0;
        const idusuario = String(valor(row, CAMPOS.idusuario, valor(row, CAMPOS.agente, "")));
        actual._agentesActivos = actual._agentesActivos || new Set();
        if (numeroCampo(row, CAMPOS.gestiones) > 0 && idusuario) actual._agentesActivos.add(idusuario);

        map.set(key, actual);
    });

    return [...map.values()]
        .map(item => {
            const agentesActivos = item._agentesActivos ? item._agentesActivos.size : 0;
            const dotacion = (item.ids || [item.idcartera]).reduce((total, id) =>
                total + Number((dataControlHorario.dotacion_grupos || {})[id] || 0), 0);
            const agentesAsignados = carterasPermitidasSupervisor().length
                ? agentesActivos
                : Number(dotacion || agentesActivos || 0);

            return {
                ...item,
                agentes: agentesAsignados,
                agentes_activos: agentesActivos,
                pct_cef: item.gestiones > 0 ? item.cef / item.gestiones : 0,
                avance: item.proyectado > 0 ? item.pago / item.proyectado : 0
            };
        })
        .sort((a, b) => b.pendiente - a.pendiente);
}

function textoAgentesCartera(row) {
    if (Number(row.agentes || 0) === Number(row.agentes_activos || 0)) {
        return `${num(row.agentes_activos)} agentes activos`;
    }
    return `${num(row.agentes)} agentes | ${num(row.agentes_activos)} activos`;
}

function resumenDeCartera(idcartera) {
    return resumenCarteras.find(item => String(item.idcartera) === String(idcartera));
}

function calcularKpis(detalle, resumen) {
    const base = resumen || detalle.reduce((acc, row) => {
        acc.gestiones += numeroCampo(row, CAMPOS.gestiones);
        acc.cef += numeroCampo(row, CAMPOS.cef);
        acc.pdp_generado += getPdpGenerado(row);
        acc.proyectado += numeroCampo(row, CAMPOS.proyectado);
        acc.pago += numeroCampo(row, CAMPOS.pago);
        acc.pendiente += numeroCampo(row, CAMPOS.pendiente);
        acc.criticos += esCritico(row) ? 1 : 0;
        return acc;
    }, {
        gestiones: 0,
        cef: 0,
        pdp_generado: 0,
        proyectado: 0,
        pago: 0,
        pendiente: 0,
        criticos: 0
    });

    return {
        gestiones: base.gestiones,
        cef: base.cef,
        pdp_generado: base.pdp_generado,
        proyectado: base.proyectado,
        pago: base.pago,
        avance: base.proyectado > 0 ? base.pago / base.proyectado : 0,
        pendiente: base.pendiente,
        criticos: base.criticos
    };
}

function renderKpis(kpis) {
    const cards = [
        ["Gestiones acumuladas", num(kpis.gestiones), "phone", ""],
        ["CEF acumulados", num(kpis.cef), "cef", kpis.cef <= 0 ? "danger" : ""],
        ["PDP generado", money(kpis.pdp_generado), "pdp", kpis.pdp_generado <= 0 ? "danger" : ""],
        ["Proyectado hoy", money(kpis.proyectado), "target", kpis.proyectado <= 0 ? "danger" : ""],
        ["Pago hoy", money(kpis.pago), "pay", ""],
        ["Avance dia", percent(kpis.avance), "trend", kpis.avance < 0.2 ? "danger" : kpis.avance < 0.5 ? "warn" : ""],
        ["Pendiente hoy", money(kpis.pendiente), "clock", kpis.pendiente > 0 ? "warn" : ""],
        ["Agentes criticos", num(kpis.criticos), "alert", kpis.criticos > 0 ? "danger" : ""]
    ];

    document.getElementById("kpiControlHorario").innerHTML = cards.map(([label, value, icon, tone]) => `
        <article class="kpi-card ${tone ? `kpi-${tone}` : ""}">
            <i class="kpi-icon">${iconoKpi(icon)}</i>
            <span>${h(label)}</span>
            <strong>${h(value)}</strong>
        </article>
    `).join("");
}

function renderResumenCarteras(data) {
    const tbody = document.getElementById("tablaResumenCarteras");
    const base = carteraSeleccionada
        ? data.filter(row => String(row.idcartera) === String(carteraSeleccionada))
        : data;
    const visible = ordenarFilas(base, ordenResumen, valorOrdenResumen);

    if (!visible.length) {
        tbody.innerHTML = emptyRow(11, "No hay carteras para el filtro seleccionado.");
        return;
    }

    tbody.innerHTML = visible.map(row => `
        <tr>
            <td class="left cartera-cell">
                <strong>${h(row.cartera)}</strong>
                <small>${textoAgentesCartera(row)}</small>
            </td>
            <td>
                <strong>${num(row.gestiones)}</strong>
                <small class="muted">${num(row.clientes_mes)} clientes</small>
            </td>
            <td>${num(row.cef)}</td>
            <td>${percent(row.pct_cef)}</td>
            <td>${money(row.pdp_generado)}</td>
            <td>${money(row.proyectado)}</td>
            <td>${money(row.pago)}</td>
            <td><span class="avance-pill ${claseAvance(row.avance)}">${percent(row.avance)}</span></td>
            <td>${money(row.pendiente)}</td>
            <td>${num(row.criticos)}</td>
            <td>
                <button class="btn-table" type="button" onclick="seleccionarCartera('${h(row.idcartera)}')">
                    Ver agentes
                </button>
            </td>
        </tr>
    `).join("");
}

function renderDetalleAgentes(data) {
    const tbody = document.getElementById("tablaDetalleControl");
    const visibleData = ordenarFilas(data, ordenAgentes, valorOrdenAgente);
    const escalaVisible = calcularEscalaVisible(visibleData);

    if (!carteraSeleccionada) {
        tbody.innerHTML = emptyRow(11, "Selecciona una cartera para ver agentes.");
        return;
    }

    if (!visibleData.length) {
        tbody.innerHTML = emptyRow(11, "No hay agentes para la cartera seleccionada.");
        return;
    }

    tbody.innerHTML = visibleData.map((row, index) => {
        const color = valor(row, CAMPOS.color, "GRIS");
        const sinPdp = getPdpGenerado(row) <= 0;
        const sinProyectado = numeroCampo(row, CAMPOS.proyectado) <= 0;
        const accionFinal = evaluarAccionAgente(row);
        return `
            <tr>
                <td class="left">${h(valor(row, CAMPOS.agente, "-"))}</td>
                <td>${num(numeroCampo(row, CAMPOS.gestiones))}</td>
                <td><span class="cef-heat ${claseCefVisible(numeroCampo(row, CAMPOS.cef), escalaVisible.cef)}">${num(numeroCampo(row, CAMPOS.cef))}</span></td>
                <td>${percent(valor(row, CAMPOS.pctCef, calcularPctCef(row)))}</td>
                <td><span class="${claseMonto(getPdpGenerado(row), escalaVisible.pdp, 'pdp')}">${money(getPdpGenerado(row))}</span></td>
                <td><span class="${claseMonto(numeroCampo(row, CAMPOS.proyectado), escalaVisible.proyectado, 'proyectado')}">${money(numeroCampo(row, CAMPOS.proyectado))}</span></td>
                <td><span class="${claseMonto(numeroCampo(row, CAMPOS.pago), escalaVisible.pago, 'pago')}">${money(numeroCampo(row, CAMPOS.pago))}</span></td>
                <td>${percent(valor(row, CAMPOS.avance, calcularAvance(row)))}</td>
                <td>${money(numeroCampo(row, CAMPOS.pendiente))}</td>
                <td><div class="accion-stack"><span class="accion-badge ${claseColor(accionFinal.COLOR_ACCION)}">${h(accionFinal.ACCION)}</span></div></td>
                <td><button class="btn-table secondary" type="button" onclick="abrirDetalleAgente(${index})">Ver detalle</button></td>
            </tr>
        `;
    }).join("");

    window._detalleAgentesActual = visibleData;
}

function abrirDetalleAgente(index) {
    const row = window._detalleAgentesActual?.[index];
    if (!row) return;

    const idusuario = String(valor(row, CAMPOS.idusuario, ""));
    const agente = valor(row, CAMPOS.agente, "Agente");
    const cartera = resumenDeCartera(carteraSeleccionada);

    document.getElementById("tituloModalAgente").innerText = agente;
    document.getElementById("subtituloModalAgente").innerText =
        `${cartera?.cartera || "Cartera"} | Ultima gestion: ${formatDateTime(valor(row, CAMPOS.ultimaGestion, ""))}`;

    document.getElementById("modalAgenteKpis").innerHTML = [
        ["Gestiones", num(numeroCampo(row, CAMPOS.gestiones)), "phone"],
        ["CEF", num(numeroCampo(row, CAMPOS.cef)), "cef"],
        ["PDP Gen", money(getPdpGenerado(row)), "pdp"],
        ["Proyectado", money(numeroCampo(row, CAMPOS.proyectado)), "target"],
        ["Pago", money(numeroCampo(row, CAMPOS.pago)), "pay"],
        ["Pendiente", money(numeroCampo(row, CAMPOS.pendiente)), "warn"]
    ].map(([label, value, icon]) => `
        <article class="agent-kpi">
            <span>${iconoTexto(icon)}</span>
            <div>
                <small>${h(label)}</small>
                <strong>${h(value)}</strong>
            </div>
        </article>
    `).join("");

    const horas = agruparHorasAgente(
        agenteHoraFiltrado().filter(item =>
            String(valor(item, CAMPOS.idusuario, "")) === idusuario && rowPerteneceACarteraSeleccionada(item)
        )
    );

    renderTablaHorasAgente(horas);
    document.getElementById("modalAgenteControl").classList.add("activo");
}

function renderPanelDerecho(detalle) {
    const base = carteraSeleccionada ? agruparDetalleAgentes(detalle) : resumenCarteras;

    const topAvance = [...base].sort((a, b) => getAvance(b) - getAvance(a)).slice(0, 5);
    const topPendiente = [...base].sort((a, b) => getPendiente(b) - getPendiente(a)).slice(0, 5);

    renderMiniList("topAvanceControl", topAvance, "avance");
    renderMiniList("pendientesControl", topPendiente, "pendiente");
    renderAlertas(alertasActuales());
}

function renderMiniList(id, data, tipo) {
    const contenedor = document.getElementById(id);

    if (!data.length) {
        contenedor.innerHTML = `<div class="mini-empty">Sin informacion.</div>`;
        return;
    }

    contenedor.innerHTML = data.map((row, index) => {
        const nombre = row.cartera || valor(row, CAMPOS.agente, "-");
        const dato = tipo === "pendiente" ? money(getPendiente(row)) : percent(getAvance(row));
        const clase = tipo === "pendiente"
            ? (getPendiente(row) > 0 ? "mini-critico" : "mini-ok")
            : claseMiniAvance(getAvance(row));

        return `
        <div class="mini-item ${clase}">
            <i>${tipo === "pendiente" ? "!" : index + 1}</i>
            <span>${h(nombre)}</span>
            <strong>${h(dato)}</strong>
        </div>
        `;
    }).join("");
}

function renderAlertas(data) {
    const contenedor = document.getElementById("alertasControl");

    if (!data.length) {
        contenedor.innerHTML = `<div class="mini-empty">Sin alertas para el corte.</div>`;
        return;
    }

    contenedor.innerHTML = data.slice(0, 6).map(row => `
        <div class="alert-item ${claseAlerta(valor(row, ["COLOR", "color"], ""))}">
            <i>${iconoAlerta(valor(row, ["COLOR", "color"], ""))}</i>
            <div>
            <strong>${h(valor(row, ["ALERTA", "alerta", "titulo", "tipo"], "Alerta"))}</strong>
            <span>${h(valor(row, ["MENSAJE", "mensaje", "detalle", "descripcion", "CANTIDAD", "cantidad"], "-"))}</span>
            </div>
        </div>
    `).join("");
}

function alertasActuales() {
    const alertas = dataControlHorario.alertas || [];
    const ids = idsCarteraSeleccionada();
    if (!ids.length) return alertas;

    const filtradas = alertas.filter(row => ids.includes(String(getIdCartera(row))));
    return filtradas.length ? filtradas : alertas;
}

function horasActuales() {
    const agenteHora = agenteHoraFiltrado();
    const ids = idsCarteraSeleccionada();
    if (agenteHora.length) {
        const filtrado = ids.length
            ? agenteHora.filter(rowPerteneceACarteraSeleccionada)
            : agenteHora;

        return agruparHoras(filtrado);
    }

    if (!ids.length) return agruparHoras(dataControlHorario.horas || []);

    const horas = (dataControlHorario.horas || [])
        .filter(rowPerteneceACarteraSeleccionada);

    return agruparHoras(horas);
}

function agruparHoras(data) {
    const map = new Map();
    (data || []).forEach(row => {
        const orden = horaOrden(row);
        const hora = rangoHora(row);
        const item = map.get(hora) || {
            HORA_CORTE: orden,
            RANGO_HORA: hora,
            GESTIONES: 0,
            CEF: 0,
            Q_PDP: 0,
            PDP_GENERADO: 0
        };

        item.GESTIONES += numeroCampo(row, CAMPOS.gestiones);
        item.CEF += numeroCampo(row, CAMPOS.cef);
        item.Q_PDP += numeroCampo(row, CAMPOS.qPdp);
        item.PDP_GENERADO += getPdpGenerado(row);

        map.set(hora, item);
    });

    for (let hora = 6; hora <= 20; hora += 1) {
        const rango = rangoHoraDesdeNumero(hora);
        if (!map.has(rango)) {
            map.set(rango, {
                HORA_CORTE: hora,
                RANGO_HORA: rango,
                GESTIONES: 0,
                CEF: 0,
                Q_PDP: 0,
                PDP_GENERADO: 0
            });
        }
    }

    return ordenarPorHora([...map.values()]);
}

function cambiarMetricaHora(metrica) {
    metricaHoraActual = metrica;
    document.querySelectorAll(".chart-switch button").forEach(button => {
        button.classList.toggle("active", button.dataset.metrica === metrica);
    });
    renderGraficoHoras(horasActuales());
}

function renderGraficoHoras(data) {
    const contenedor = document.getElementById("graficoHoras");

    if (!data.length) {
        contenedor.innerHTML = `<div class="mini-empty">No hay cortes horarios para el filtro seleccionado.</div>`;
        return;
    }

    const ordenado = ordenarPorHora(data);
    const puntos = ordenado.map(row => ({
        hora: getHora(row),
        orden: horaOrden(row),
        valor: valorMetricaHora(row, metricaHoraActual),
        gestiones: numeroCampo(row, CAMPOS.gestiones),
        cef: numeroCampo(row, CAMPOS.cef),
        pdp: getPdpGenerado(row)
    }));
    const max = Math.max(...puntos.map(p => p.valor), 1);
    const width = 920;
    const height = 220;
    const padX = 44;
    const padY = 24;
    const step = puntos.length > 1 ? (width - padX * 2) / (puntos.length - 1) : 0;
    const coords = puntos.map((p, i) => {
        const x = padX + i * step;
        const y = height - padY - (p.valor / max) * (height - padY * 2);
        return { ...p, x, y };
    });
    const polyline = coords.map(p => `${p.x},${p.y}`).join(" ");

    contenedor.innerHTML = `
        <svg class="line-chart" viewBox="0 0 ${width} ${height}" role="img">
            <line x1="${padX}" y1="${height - padY}" x2="${width - padX}" y2="${height - padY}" class="axis" />
            <line x1="${padX}" y1="${padY}" x2="${padX}" y2="${height - padY}" class="axis" />
            <polyline points="${polyline}" class="chart-line" />
            ${coords.map(p => `
                <g class="chart-point" onclick="filtrarHora('${h(p.hora)}')">
                    <circle cx="${p.x}" cy="${p.y}" r="5"></circle>
                    <title>${h(p.hora)} | ${h(etiquetaMetricaHora())}: ${formatoMetricaHora(p.valor)}</title>
                </g>
            `).join("")}
            ${coords.map((p, i) => i % 2 === 0 ? `<text x="${p.x}" y="${height - 5}" class="chart-label">${h(String(p.hora).split(" ")[0])}</text>` : "").join("")}
        </svg>
        <div class="chart-summary">
            ${coords.map(p => `
                <button type="button" onclick="filtrarHora('${h(p.hora)}')">
                    <span>${h(p.hora)}</span>
                    <b>${formatoMetricaHora(p.valor)}</b>
                </button>
            `).join("")}
        </div>
    `;
}

function filtrarHora(hora) {
    const ids = idsCarteraSeleccionada();
    const data = agenteHoraFiltrado().filter(row => {
        const mismaHora = String(getHora(row)) === String(hora) || String(horaOrden(row)) === String(hora);
        const mismaCartera = ids.length ? rowPerteneceACarteraSeleccionada(row) : true;
        return mismaHora && mismaCartera;
    });

    renderAgenteHora(data, hora);
    document.getElementById("modalHoraControl").classList.add("activo");
}

function agenteHoraFiltrado() {
    const data = dataControlHorario.agente_hora || [];
    if (!agenteSeleccionado) return data;
    return data.filter(row => String(valor(row, CAMPOS.idusuario, "")) === String(agenteSeleccionado));
}

function renderAgenteHora(data, hora) {
    const tbody = document.getElementById("tablaAgenteHoraControl");
    document.getElementById("tituloDrillHora").innerText = `Detalle agente/hora - ${hora}`;
    const agrupado = ordenarFilas(agruparAgenteHora(data), ordenAgenteHora, valorOrdenAgenteHora);

    if (!agrupado.length) {
        tbody.innerHTML = emptyRow(7, "No hay detalle agente/hora para este corte.");
        return;
    }

    tbody.innerHTML = agrupado.map(row => `
        <tr>
            <td class="left">${h(valor(row, CAMPOS.agente, "-"))}</td>
            <td>${num(numeroCampo(row, CAMPOS.gestiones))}</td>
            <td>${num(numeroCampo(row, CAMPOS.cef))}</td>
            <td>${percent(valor(row, CAMPOS.pctCef, calcularPctCef(row)))}</td>
            <td>${num(numeroCampo(row, CAMPOS.qPdp))}</td>
            <td>${money(getPdpGenerado(row))}</td>
            <td>${percent(valor(row, CAMPOS.tc, 0))}</td>
        </tr>
    `).join("");
}

function ordenarAgenteHora(campo) {
    ordenAgenteHora = siguienteOrden(ordenAgenteHora, campo);
    const modal = document.getElementById("modalHoraControl");
    if (!modal?.classList.contains("activo")) return;

    const hora = document.getElementById("tituloDrillHora")?.innerText?.split(" - ").pop();
    if (hora) filtrarHora(hora);
}

function valorOrdenAgenteHora(row, campo) {
    const map = {
        agente: valor(row, CAMPOS.agente, ""),
        gestiones: numeroCampo(row, CAMPOS.gestiones),
        cef: numeroCampo(row, CAMPOS.cef),
        pct_cef: Number(valor(row, CAMPOS.pctCef, calcularPctCef(row)) || 0),
        q_pdp: numeroCampo(row, CAMPOS.qPdp),
        pdp: getPdpGenerado(row),
        tc: Number(valor(row, CAMPOS.tc, 0) || 0)
    };

    return map[campo] ?? 0;
}

function agruparAgenteHora(data) {
    const map = new Map();

    (data || []).forEach(row => {
        const idusuario = String(valor(row, CAMPOS.idusuario, valor(row, CAMPOS.agente, "")));
        const hora = String(getHora(row));
        const key = `${idusuario}|${hora}`;
        const actual = map.get(key) || {
            ...row,
            GESTIONES: 0,
            CEF: 0,
            CNE: 0,
            NOC: 0,
            Q_PDP_GEN: 0,
            PDP_GEN: 0
        };

        actual.GESTIONES += numeroCampo(row, CAMPOS.gestiones);
        actual.CEF += numeroCampo(row, CAMPOS.cef);
        actual.CNE += numeroCampo(row, CAMPOS.cne);
        actual.NOC += numeroCampo(row, CAMPOS.noc);
        actual.Q_PDP_GEN += numeroCampo(row, CAMPOS.qPdp);
        actual.PDP_GEN += getPdpGenerado(row);
        actual.PORC_CEF = actual.GESTIONES > 0 ? (actual.CEF * 100) / actual.GESTIONES : 0;
        actual.TC = actual.CEF > 0 ? (actual.Q_PDP_GEN * 100) / actual.CEF : 0;

        map.set(key, actual);
    });

    return [...map.values()].sort((a, b) => {
        const gestiones = numeroCampo(b, CAMPOS.gestiones) - numeroCampo(a, CAMPOS.gestiones);
        if (gestiones !== 0) return gestiones;
        return String(valor(a, CAMPOS.agente, "")).localeCompare(String(valor(b, CAMPOS.agente, "")), "es");
    });
}

function agruparHorasAgente(data) {
    const map = new Map();

    data.forEach(row => {
        const hora = getHora(row);
        const item = map.get(hora) || {
            hora,
            orden: horaOrden(row),
            gestiones: 0,
            cef: 0,
            q_pdp: 0,
            pdp_gen: 0
        };

        item.gestiones += numeroCampo(row, CAMPOS.gestiones);
        item.cef += numeroCampo(row, CAMPOS.cef);
        item.q_pdp += numeroCampo(row, CAMPOS.qPdp);
        item.pdp_gen += getPdpGenerado(row);

        map.set(hora, item);
    });

    return [...map.values()].sort((a, b) => a.orden - b.orden);
}

function renderTablaHorasAgente(data) {
    const tbody = document.getElementById("tablaModalAgenteHoras");

    if (!data.length) {
        tbody.innerHTML = emptyRow(7, "No hay corte horario para este agente.");
        return;
    }

    tbody.innerHTML = data.map(row => `
        <tr>
            <td>${h(row.hora)}</td>
            <td>${num(row.gestiones)}</td>
            <td>${num(row.cef)}</td>
            <td>${percent(row.gestiones > 0 ? row.cef / row.gestiones : 0)}</td>
            <td>${num(row.q_pdp)}</td>
            <td>${money(row.pdp_gen)}</td>
            <td>${percent(row.cef > 0 ? row.q_pdp / row.cef : 0)}</td>
        </tr>
    `).join("");
}

function calcularEscalaVisible(data) {
    const valores = (getter) => (data || [])
        .map(getter)
        .filter(value => Number(value || 0) > 0)
        .sort((a, b) => a - b);

    return {
        cef: valores(row => numeroCampo(row, CAMPOS.cef)),
        pdp: valores(row => getPdpGenerado(row)),
        proyectado: valores(row => numeroCampo(row, CAMPOS.proyectado)),
        pago: valores(row => numeroCampo(row, CAMPOS.pago))
    };
}

function evaluarAccionAgente(row) {
    const gestiones = numeroCampo(row, CAMPOS.gestiones);
    const cef = numeroCampo(row, CAMPOS.cef);
    const qPdp = numeroCampo(row, CAMPOS.qPdp);
    const pdpGen = getPdpGenerado(row);
    const proyectado = numeroCampo(row, CAMPOS.proyectado);
    const pago = numeroCampo(row, CAMPOS.pago);
    const proyectadoRelevante = proyectado >= 900;
    const avanceCobro = proyectado > 0 ? pago / proyectado : 0;

    if (proyectadoRelevante && pago === 0) {
        return { ACCION: "COBRANZA URGENTE", COLOR_ACCION: "ROJO", PESO_ACCION: 1 };
    }

    if (pdpGen === 0 && proyectado === 0 && pago === 0) {
        return { ACCION: "SIN RESULTADO ECONOMICO", COLOR_ACCION: "NEGRO", PESO_ACCION: 2 };
    }

    if (pdpGen > 0 && pago === 0) {
        return { ACCION: "GENERA NO COBRA", COLOR_ACCION: "ROJO", PESO_ACCION: 3 };
    }

    if (gestiones > 0 && cef === 0) {
        return { ACCION: "GESTIONA SIN CEF", COLOR_ACCION: "ROJO", PESO_ACCION: 4 };
    }

    if (pago > 0 && (avanceCobro < 0.5 || (proyectado > 0 && !proyectadoRelevante))) {
        return { ACCION: "AVANCE BAJO", COLOR_ACCION: "ROJO", PESO_ACCION: 5 };
    }

    if (proyectadoRelevante && pago >= proyectado * 0.5 && pago < proyectado) {
        return { ACCION: "SEGUIMIENTO PARCIAL", COLOR_ACCION: "AMBAR", PESO_ACCION: 6 };
    }

    if (cef > 0 && qPdp === 0) {
        return { ACCION: "CONTACTA SIN PDP", COLOR_ACCION: "AMBAR", PESO_ACCION: 7 };
    }

    if (pdpGen > 0 && pdpGen < 1000) {
        return { ACCION: "GENERACION BAJA", COLOR_ACCION: "AMBAR", PESO_ACCION: 8 };
    }

    if (pdpGen >= 1000 && pdpGen < 3000) {
        return { ACCION: "GENERACION REGULAR", COLOR_ACCION: "AZUL", PESO_ACCION: 9 };
    }

    if (proyectado > 0 && pago >= proyectado) {
        return { ACCION: "PROYECTADO CUMPLIDO", COLOR_ACCION: "VERDE", PESO_ACCION: 10 };
    }

    if (pdpGen >= 3000) {
        return { ACCION: "BUENA GENERACION", COLOR_ACCION: "VERDE", PESO_ACCION: 11 };
    }

    if (proyectado === 0) {
        return { ACCION: "SIN COBRO PROGRAMADO", COLOR_ACCION: "GRIS", PESO_ACCION: 12 };
    }

    return { ACCION: "EN MONITOREO", COLOR_ACCION: "AZUL", PESO_ACCION: 13 };
}

function clasePorEscala(valor, escala) {
    const n = Number(valor || 0);
    if (n <= 0) return "cero";
    if (!escala.length) return "medio";

    const max = Math.max(...escala);
    const min = Math.min(...escala);
    if (max === min) return "alto";

    const posicion = (n - min) / (max - min);
    if (posicion >= 0.66) return "alto";
    if (posicion >= 0.33) return "medio";
    return "bajo";
}

function claseCefVisible(value, escala) {
    const nivel = clasePorEscala(value, escala);
    return `cef-${nivel}`;
}

function claseMonto(value, escala, tipo) {
    const n = Number(value || 0);
    let nivel = "cero";

    if (n > 0 && n < 900) nivel = "bajo";
    if (n >= 900 && n < 2000) nivel = "medio";
    if (n >= 2000) nivel = "alto";

    return `monto-heat monto-${tipo} monto-${nivel}`;
}

function cerrarModalHora(event) {
    if (event && event.target !== document.getElementById("modalHoraControl")) return;
    document.getElementById("modalHoraControl").classList.remove("activo");
}

function cerrarModalAgente(event) {
    if (event && event.target !== document.getElementById("modalAgenteControl")) return;
    document.getElementById("modalAgenteControl").classList.remove("activo");
}

function limpiarFiltrosControl() {
    document.getElementById("filtroCartera").value = "";
    document.getElementById("filtroAgente").value = "";
    limpiarFiltroCarteraControl();
    carteraSeleccionada = null;
    agenteSeleccionado = null;
    resumenOpcionesCarteras = construirResumenCarteras(dataControlHorario.detalle || []);
    resumenCarteras = construirResumenVisible();
    poblarFiltroAgentes();
    renderVista();
}

function ordenarResumen(campo) {
    ordenResumen = siguienteOrden(ordenResumen, campo);
    renderVista();
}

function ordenarAgentes(campo) {
    ordenAgentes = siguienteOrden(ordenAgentes, campo);
    renderVista();
}

function siguienteOrden(actual, campo) {
    return {
        campo,
        direccion: actual.campo === campo && actual.direccion === "desc" ? "asc" : "desc"
    };
}

function ordenarFilas(data, orden, getter) {
    const factor = orden.direccion === "asc" ? 1 : -1;
    return [...(data || [])].sort((a, b) => {
        const va = getter(a, orden.campo);
        const vb = getter(b, orden.campo);

        if (typeof va === "string" || typeof vb === "string") {
            return String(va).localeCompare(String(vb), "es") * factor;
        }

        return (Number(va || 0) - Number(vb || 0)) * factor;
    });
}

function valorOrdenResumen(row, campo) {
    const map = {
        cartera: row.cartera || "",
        gestiones: row.gestiones,
        cef: row.cef,
        pct_cef: row.pct_cef,
        pdp_generado: row.pdp_generado,
        proyectado: row.proyectado,
        pago: row.pago,
        avance: row.avance,
        pendiente: row.pendiente,
        criticos: row.criticos
    };

    return map[campo] ?? 0;
}

function valorOrdenAgente(row, campo) {
    const map = {
        agente: valor(row, CAMPOS.agente, ""),
        gestiones: numeroCampo(row, CAMPOS.gestiones),
        cef: numeroCampo(row, CAMPOS.cef),
        pct_cef: Number(valor(row, CAMPOS.pctCef, calcularPctCef(row)) || 0),
        pdp: getPdpGenerado(row),
        proyectado: numeroCampo(row, CAMPOS.proyectado),
        pago: numeroCampo(row, CAMPOS.pago),
        avance: Number(valor(row, CAMPOS.avance, calcularAvance(row)) || 0),
        pendiente: numeroCampo(row, CAMPOS.pendiente)
    };

    return map[campo] ?? 0;
}

function exportarControlHorario() {
    mostrarToast("Exportacion preparada para una siguiente fase.", "info");
}

function getIdCartera(row) {
    return valor(row, CAMPOS.idcartera, "");
}

function getIdCarteraBase(row) {
    return valor(row, ["IDCARTERA_ORIGINAL", "idcartera_original", "IDCARTERA_BASE", "idcartera_base"], getIdCartera(row));
}

function getCartera(row, idcartera) {
    return valor(row, CAMPOS.cartera, `Cartera ${idcartera}`);
}

function getHora(row) {
    return rangoHora(row);
}

function horaOrden(row) {
    const directo = valor(row, ["HORA_CORTE", "hora_corte"], null);
    if (directo !== null && directo !== undefined && directo !== "") return Number(directo);

    const texto = String(valor(row, CAMPOS.hora, "") || "");
    const match = texto.match(/\d{1,2}/);
    return match ? Number(match[0]) : 999;
}

function rangoHoraDesdeNumero(orden) {
    return `${String(orden).padStart(2, "0")}:00 - ${String(orden + 1).padStart(2, "0")}:00`;
}

function rangoHora(row) {
    const rango = valor(row, ["RANGO_HORA", "rango_hora"], "");
    if (rango) return rango;

    const orden = horaOrden(row);
    if (orden === 999) return "-";

    return rangoHoraDesdeNumero(orden);
}

function ordenarPorHora(data) {
    return [...(data || [])].sort((a, b) => horaOrden(a) - horaOrden(b));
}

function getAvance(row) {
    if (row.avance !== undefined) return Number(row.avance || 0);
    return Number(valor(row, CAMPOS.avance, calcularAvance(row)) || 0);
}

function getPendiente(row) {
    if (row.pendiente !== undefined) return Number(row.pendiente || 0);
    return numeroCampo(row, CAMPOS.pendiente);
}

function calcularAvance(row) {
    const proyectado = numeroCampo(row, CAMPOS.proyectado);
    const pago = numeroCampo(row, CAMPOS.pago);
    return proyectado > 0 ? pago / proyectado : 0;
}

function calcularPctCef(row) {
    const gestiones = numeroCampo(row, CAMPOS.gestiones);
    const cef = numeroCampo(row, CAMPOS.cef);
    return gestiones > 0 ? cef / gestiones : 0;
}

function esCritico(row) {
    const color = normalizar(valor(row, CAMPOS.color, ""));
    const accion = normalizar(valor(row, CAMPOS.accion, ""));
    return color.includes("ROJO") || accion.includes("CRITICO");
}

function getPdpGenerado(row) {
    const directo = numeroCampo(row, CAMPOS.pdpGenerado);
    if (directo > 0 || existeCampo(row, CAMPOS.pdpGenerado)) return directo;
    return numeroCampo(row, CAMPOS.proyectado);
}

function valorMetricaHora(row, metrica) {
    if (metrica === "cef") return numeroCampo(row, CAMPOS.cef);
    if (metrica === "pdp") return getPdpGenerado(row);
    return numeroCampo(row, CAMPOS.gestiones);
}

function etiquetaMetricaHora() {
    if (metricaHoraActual === "cef") return "CEF";
    if (metricaHoraActual === "pdp") return "PDP generado";
    return "Gestiones";
}

function formatoMetricaHora(value) {
    return metricaHoraActual === "pdp" ? money(value) : num(value);
}

function claseCef(value) {
    const n = Number(value || 0);
    if (n >= 60) return "cef-alto";
    if (n >= 30) return "cef-medio";
    if (n > 0) return "cef-bajo";
    return "cef-cero";
}

function iconoTexto(tipo) {
    const iconos = {
        phone: "☎",
        cef: "▥",
        pdp: "▣",
        target: "◎",
        pay: "S/",
        warn: "!"
    };
    return iconos[tipo] || "•";
}

function iconoAlerta(color) {
    const value = normalizar(color);
    if (value.includes("ROJO")) return "!";
    if (value.includes("AMBAR")) return "!";
    if (value.includes("AZUL")) return "i";
    return "•";
}

function iconoKpi(tipo) {
    const iconos = {
        phone: '<svg viewBox="0 0 24 24"><path d="M8 5h8v14H8z"/><path d="M10 8h4M10 12h4M10 16h4"/></svg>',
        cef: '<svg viewBox="0 0 24 24"><path d="M5 19V11h4v8M10 19V7h4v12M15 19v-5h4v5"/><path d="M4 19h16"/></svg>',
        pdp: '<svg viewBox="0 0 24 24"><path d="M7 4h10v16H7z"/><path d="M9 8h6M9 12h6M9 16h4"/></svg>',
        target: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="3"/></svg>',
        pay: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="8"/><path d="M12 7v10M9 10c0-1.5 1.4-2.5 3-2.5s3 1 3 2.5c0 3-6 1.5-6 4.5 0 1.5 1.4 2.5 3 2.5s3-1 3-2.5"/></svg>',
        warn: '<svg viewBox="0 0 24 24"><path d="M12 4 21 20H3z"/><path d="M12 9v5M12 17h.01"/></svg>',
        trend: '<svg viewBox="0 0 24 24"><path d="M4 17 9 12l4 4 7-8"/><path d="M15 8h5v5"/></svg>',
        clock: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="8"/><path d="M12 7v5l3 2"/></svg>',
        alert: '<svg viewBox="0 0 24 24"><path d="M12 4 21 20H3z"/><path d="M12 9v5M12 17h.01"/></svg>'
    };
    return iconos[tipo] || "i";
}

function claseMiniAvance(value) {
    const avance = Number(value || 0);
    if (avance >= 0.8) return "mini-ok";
    if (avance >= 0.5) return "mini-alerta";
    return "mini-critico";
}

function claseAlerta(color) {
    const value = normalizar(color);
    if (value.includes("ROJO")) return "alert-rojo";
    if (value.includes("AMBAR") || value.includes("AMARILLO")) return "alert-ambar";
    if (value.includes("AZUL")) return "alert-azul";
    return "alert-info";
}

function existeCampo(row, keys) {
    const actuales = Object.keys(row || {}).map(normalizar);
    return keys.some(key => actuales.includes(normalizar(key)));
}

function numeroCampo(row, keys) {
    return Number(valor(row, keys, 0) || 0);
}

function valor(row, keys, fallback = 0) {
    for (const key of keys) {
        if (row?.[key] !== undefined && row?.[key] !== null && row?.[key] !== "") return row[key];
    }

    const normalizado = Object.keys(row || {}).find(actual =>
        keys.some(key => normalizar(actual) === normalizar(key))
    );

    return normalizado ? row[normalizado] : fallback;
}

function normalizar(texto) {
    return String(texto || "")
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "")
        .replace(/[^a-zA-Z0-9]/g, "")
        .toUpperCase();
}

function num(value) {
    return Number(value || 0).toLocaleString("es-PE", { maximumFractionDigits: 0 });
}

function money(value) {
    return Number(value || 0).toLocaleString("es-PE", {
        style: "currency",
        currency: "PEN",
        minimumFractionDigits: 2
    });
}

function percent(value) {
    const n = Number(value || 0);
    const pct = n > 1 ? n : n * 100;
    return `${pct.toFixed(1)}%`;
}

function formatDateTime(value) {
    if (!value) return "-";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return value;
    return date.toLocaleString("es-PE", {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit"
    });
}

function claseAvance(value) {
    if (value >= 0.8) return "avance-verde";
    if (value >= 0.5) return "avance-ambar";
    return "avance-rojo";
}

function claseColor(color) {
    const value = normalizar(color);
    if (value.includes("VERDE")) return "color-verde";
    if (value.includes("AMBAR") || value.includes("AMARILLO")) return "color-ambar";
    if (value.includes("ROJO")) return "color-rojo";
    if (value.includes("NEGRO")) return "color-negro";
    if (value.includes("AZUL")) return "color-azul";
    return "color-gris";
}

function emptyRow(colspan, mensaje) {
    return `<tr><td colspan="${colspan}" class="empty-table">${h(mensaje)}</td></tr>`;
}

function mostrarToast(texto, tipo = "info") {
    const toast = document.getElementById("controlToast");
    if (!toast) return;

    toast.textContent = texto;
    toast.className = `control-toast activo ${tipo}`;

    clearTimeout(window._controlToastTimer);
    window._controlToastTimer = setTimeout(() => {
        toast.classList.remove("activo");
    }, 2800);
}

function h(value) {
    return String(value ?? "-")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}
