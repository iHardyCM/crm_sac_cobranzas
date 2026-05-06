// compromisos.js
// 🔐 VALIDAR SESIÓN
const agente =
    localStorage.getItem("agente_filtro")
    || localStorage.getItem("agente");

console.log("AGENTE VISUAL:", agente);

if (!agente) {
    alert("Sesión inválida, vuelve a iniciar sesión");
    window.location.href = "login.html";
}

// 🔥 EXTRAER DNI
const dni = agente.substring(0, 8);

console.log("DNI USADO:", dni);

// 🔥 HEADER
const fecha = new Date();
const mes = fecha.toLocaleString('es-PE', { month: 'long' });
const anio = fecha.getFullYear();

document.getElementById("nombre_agente").innerText = agente;

document.getElementById("titulo_tabla").innerText =
    `Compromisos del mes (${mes} ${anio})`;

// 🔥 VARIABLES GLOBALES
let dataGlobal = [];
let pagina = 1;
let porPagina = 10;

let ordenCampo = null;
let ordenDireccion = "asc"; // asc | desc

let dataFiltrada = [];

// 🔥 CARGA INICIAL
async function cargar() {

    try {

        const BASE_URL = `http://${window.location.hostname}:8000`;

        // 🔥 DECLARAR AQUÍ
        const agenteCompleto = localStorage.getItem("agente_filtro");

        const agenteFiltro = agenteCompleto
            ? agenteCompleto.split(" - ")[0]
            : null;

        let url = "";

        if (agenteFiltro) {

            console.log("🔵 MODO SUPERVISOR → AGENTE:", agenteFiltro);

            url = `${BASE_URL}/compromisos/agente/compromisos?agente=${encodeURIComponent(agenteFiltro)}`;

        } else {

            console.log("🟢 MODO AGENTE NORMAL:", dni);

            url = `${BASE_URL}/compromisos/${dni}`;
        }

        const res = await fetch(url);

        if (!res.ok) {
            throw new Error("Error en API");
        }

        const data = await res.json();

        console.log("PRIMER REGISTRO:", data.data[0]);
        console.log("DATA BACKEND:", data);

        dataGlobal = (data.data || []).map(x => ({
            id: x.IDCOMPROMISO || x.id,
            cliente: x.CLIENTE || x.cliente || x.NOMBRECLIENTE,
            dni: x.DNI || x.dni,
            telefono: x.TELEFONO || x.telefono,
            monto: x.MONTO || x.monto,
            fecha: x.FECHA || x.fecha || x.FECHACOMPROMISO,
            estado: x.ESTADO || x.estado,
            intentos_hoy: x.INTENTOS_HOY ?? x.intentos_hoy ?? 0
        }));

        const dataLimpia = limpiarDataParaTabla(dataGlobal);

        calcularKPIs(dataLimpia);

        dataFiltrada = dataLimpia;

        renderTabla(dataFiltrada);

        // 🔥 LIMPIAR DESPUÉS DE USAR
        if (agenteFiltro) {
            // localStorage.removeItem("agente_filtro");
            // location.reload();
        }

    } catch (error) {
        console.error("ERROR CARGA:", error);
    }
}

cargar();



async function verDetalle(id) {

    try {

        const BASE_URL = `http://${window.location.hostname}:8000`;

        const res = await fetch(`${BASE_URL}/compromisos/detalle/${id}`);
        const d = await res.json();

        const tipoUlt = getGestionUI(d.ult_tipocontacto, d.ult_indicador);
        const tipoComp = getGestionUI(d.contacto, d.indicador);

        const fechaFormateada = d.ult_fecha 
            ? new Date(d.ult_fecha).toLocaleString("es-PE")
            : "-";

        // 🔥 CALCULAR MONTO PENDIENTE
        const montoPendiente = (d.monto || 0) - (d.monto_pagado || 0);

        // 🔥 CALCULAR ESTADO (ya que backend no lo manda)
        const hoy = new Date().toLocaleDateString('en-CA'); 
        // let estado = "Vigente";

        const fechaComp = (d.fecha_compromiso || "").split(" ")[0].split("T")[0];

        let estado = "Vigente";

        if (montoPendiente <= 0) {
            estado = "Cumplida";
        } else if (fechaComp === hoy) {
            estado = "Hoy";
        } else if (fechaComp < hoy) {
            estado = "Caída";
        }

        const estadoColor = {
            "Hoy": "#c0392b",
            "Caída": "#a04000",
            "Vigente": "#f4d03f",
            "Cumplida": "#27ae60"
        }[estado] || "#999";

        const estadoClass = estado
            .toLowerCase()
            .replace("í", "i")
            .replace("á", "a");

        document.getElementById("detalle").innerHTML = `
        <div class="modal-card-pro">

            <!-- HEADER -->
            <div class="modal-header-pro">

                <div>
                    <div class="modal-id">#PDP-ID: ${d.id}</div>
                    <div class="modal-nombre">${d.cliente}</div>
                </div>

                <div class="header-right">
                    <span class="badge-estado estado-${estadoClass}">
                        ${estado}
                    </span>

                    <button class="btn-close" onclick="cerrarModal()">✕</button>
                </div>

            </div>

            <!-- INFO RÁPIDA -->
            <div class="modal-info">
                <div>DNI: ${d.dni}</div>
                <div>Tel: ${d.telefono}</div>
            </div>

            <!-- BLOQUE -->
            <div class="modal-bloque">
                <div class="bloque-titulo">RESUMEN DEL COMPROMISO</div>

                <div class="bloque-row">
                    <span>Num. Préstamo</span>
                    <b>${d.operacion || "-"}</b>
                </div>

                <div class="bloque-row">
                    <span>Monto acordado</span>
                    <b>${d.moneda} ${formatearMonto(d.monto)}</b>
                </div>

                <div class="bloque-row">
                    <span>Monto pagado</span>
                    <b>${d.moneda} ${formatearMonto(d.monto_pagado)}</b>
                </div>

                <div class="bloque-row">
                    <span>Monto pendiente</span>
                    <b>${d.moneda} ${formatearMonto(montoPendiente)}</b>
                </div>

                <div class="bloque-row">
                    <span>Fecha compromiso</span>
                    <span>${formatearFecha(d.fecha_compromiso)}</span>
                </div>

                <div class="bloque-row">
                    <span>Fecha creación</span>
                    <span>${formatearFecha(d.fecha_generado)}</span>
                </div>

                <div class="bloque-row">
                    <span>Tipo pago</span>
                    <span>${d.tipo_pago || "-"}</span>
                </div>
            </div>

            <!-- CLIENTE -->
            <div class="modal-bloque">
                <div class="bloque-titulo">INFORMACIÓN DEL CLIENTE</div>

                <div class="bloque-row">
                    <span>Teléfono</span>
                    <span>${d.telefono}</span>
                </div>

                <div class="bloque-row">
                    <span>DNI</span>
                    <span>${d.dni}</span>
                </div>
            </div>

            <!-- HISTORIAL -->
            <div class="modal-bloque">
                <div class="bloque-titulo">HISTORIAL Y NOTAS</div>

                <div class="historial-item">

                    <div class="historial-box">

                        <!-- 🔵 ÚLTIMA GESTIÓN -->
                        <div class="timeline-item actual">

                            <div class="timeline-dot" style="background:${tipoUlt.color}"></div>

                            <div class="timeline-content">
                                <div class="timeline-header">
                                    ${d.ult_fecha}
                                </div>
                                <div class="timeline-label" style="color:${tipoUlt.color}">
                                    ${tipoUlt.label}
                                </div>
                                <div class="timeline-text">
                                    ${d.ult_gestion || "-"}
                                </div>
                                <div class="timeline-footer">
                                    ${d.ult_agente || ""}
                                </div>
                            </div>
                        </div>

                        <!-- 🟡 GESTIÓN DEL COMPROMISO -->
                        <div class="timeline-item compromiso">
                            <div class="timeline-dot" style="background:${tipoComp.color}"></div>
                            <div class="timeline-content">
                                <div class="timeline-header">
                                    ${d.fecha_generado}
                                </div>

                                <div class="timeline-label" style="color:${tipoComp.color}">
                                    ${tipoComp.label}
                                </div>

                                <div class="timeline-text">
                                    ${d.gestion || "-"}
                                </div>

                                <div class="timeline-footer">
                                    ${d.agente || ""}
                                </div>

                            </div>

                        </div>

                    </div>

                </div>
            </div>

            <!-- BOTONES -->
            <div class="modal-actions">
                <button class="btn-yellow">Re-agendar</button>
                <button class="btn-blue"
                    onclick="enviarWsp('${d.telefono}', ${d.monto}, '${d.fecha_compromiso}')">
                    Contactar
                </button>
                <button class="btn-green">Registrar pago</button>
            </div>

        </div>
        `;

        document.getElementById("modal").classList.add("active");

    } catch (error) {
        console.error("ERROR DETALLE:", error);
    }
}


// 🔒 CERRAR MODAL
function cerrarModal() {
    document.getElementById("modal").classList.remove("active");
}


// 📲 WHATSAPP
function enviarWsp(numero, monto, fecha) {
    const mensaje = encodeURIComponent(
        `Hola, te recordamos tu compromiso de pago de S/ ${monto} para el ${fecha}.`
    );
    window.open(`https://wa.me/51${numero}?text=${mensaje}`, "_blank");
}


// 🔎 FILTROS
function aplicarFiltros() {

    let estado = document.getElementById("filtro_estado").value;
    let fecha = document.getElementById("filtro_fecha").value;
    let texto = document.getElementById("buscar").value.toLowerCase();

    let filtrado = dataGlobal.filter(x => {

        let okEstado = estado
            ? (x.estado || "").toUpperCase() === estado.toUpperCase()
            : true;
        let okFecha = fecha ? x.fecha === fecha : true;

        let okTexto =
            (x.dni || "").toString().includes(texto) ||
            (x.telefono || "").toString().includes(texto);

        return okEstado && okFecha && okTexto;
    });

    pagina = 1;
    dataFiltrada = filtrado;
    renderTabla(dataFiltrada);
}


// 📊 TABLA
function renderTabla(data) {

    let dataLimpia = limpiarDataParaTabla(data);
    let dataOrdenada = ordenarData(dataLimpia);

    const totalPaginas = Math.max(1, Math.ceil(dataLimpia.length / porPagina));

    // 🔥 FIX CLAVE
    if (pagina > totalPaginas) {
        pagina = totalPaginas;
    }

    let inicio = (pagina - 1) * porPagina;
    let fin = inicio + porPagina;

    let paginado = dataOrdenada.slice(inicio, fin);

    let html = "";

    paginado.forEach(c => {

        const intentos = c.intentos_hoy ?? 0;

        const estadoClass = (c.estado || "")
            .toLowerCase()
            .replace("í", "i")
            .replace("á", "a");

        html += `
        <tr>
            <td>${c.cliente || "-"}</td>
            <td>${c.dni || "-"}</td>
            <td>${c.telefono || "-"}</td>
            <td>${c.monto || 0}</td>
            <td>${c.fecha || "-"}</td>
            <td>
                <span class="badge ${estadoClass}">
                    ${c.estado}
                </span>
            </td>
            <td>
                <span class="badge-intentos ${getIntentoClass(intentos)}">
                    ${intentos}
                </span>
            </td>
            <td>
                <button onclick="verDetalle(${c.id})">Ver</button>
                <button onclick="enviarWsp('${c.telefono}', ${c.monto}, '${c.fecha}')">📲</button>
            </td>
        </tr>`;
    });

    document.getElementById("tabla").innerHTML = html;

    document.getElementById("pagina_txt").innerText =
        `Página ${pagina} de ${totalPaginas}`;
}

// ⏭ PAGINACIÓN
function next() {

    const totalPaginas = Math.ceil(
        limpiarDataParaTabla(dataFiltrada).length / porPagina
    );

    if (pagina < totalPaginas) {
        pagina++;
        renderTabla(dataFiltrada);
    }
}

function prev() {

    if (pagina > 1) {
        pagina--;
        renderTabla(dataFiltrada);
    }
}
function calcularKPIs(data) {

    let hoy = 0;
    let caida = 0;
    let vigente = 0;
    let cumplida = 0;

    data.forEach(x => {
        if (x.estado === "Hoy") hoy++;
        if (x.estado === "Caída") caida++;
        if (x.estado === "Vigente") vigente++;
        if (x.estado === "Cumplida") cumplida++;
    });

    document.getElementById("kpi_hoy").innerText = hoy;
    document.getElementById("kpi_caida").innerText = caida;
    document.getElementById("kpi_vigente").innerText = vigente;
    document.getElementById("kpi_cumplida").innerText = cumplida;
}

function formatearFecha(fecha) {
    if (!fecha) return "-";

    let f = new Date(fecha);

    return f.toLocaleDateString("es-PE", {
        day: "2-digit",
        month: "2-digit",
        year: "numeric"
    });
}

function formatearMonto(monto) {
    return Number(monto || 0).toFixed(2);
}

function ordenarData(data) {

    if (!ordenCampo) return data;

    return [...data].sort((a, b) => {

        let valA = a[ordenCampo];
        let valB = b[ordenCampo];

        // 🔥 normalizaciones
        if (ordenCampo === "monto") {
            valA = Number(valA);
            valB = Number(valB);
        }

        if (ordenCampo === "fecha") {
            valA = new Date(valA);
            valB = new Date(valB);
        }

        if (ordenCampo === "estado") {

            const normalizar = (v) =>
                (v || "")
                    .toUpperCase()
                    .replace("Á", "A")
                    .replace("Í", "I");

            const prioridad = {
                "HOY": 1,
                "CAIDA": 2,
                "VIGENTE": 3,
                "CUMPLIDA": 4
            };

            valA = prioridad[normalizar(valA)] || 99;
            valB = prioridad[normalizar(valB)] || 99;
        }

        if (ordenCampo === "intentos_hoy") {
            valA = Number(valA || 0);
            valB = Number(valB || 0);
        }

        if (valA < valB) return ordenDireccion === "asc" ? -1 : 1;
        if (valA > valB) return ordenDireccion === "asc" ? 1 : -1;
        return 0;

    });
}

function ordenarPor(campo) {

    if (ordenCampo === campo) {
        ordenDireccion = ordenDireccion === "asc" ? "desc" : "asc";
    } else {
        ordenCampo = campo;
        ordenDireccion = "asc";
    }

    renderTabla(dataFiltrada);
}

function diasHabilesPasados(fechaStr) {

    let fecha = new Date(fechaStr);
    let hoy = new Date();

    // 🔥 NORMALIZAR
    fecha.setHours(0,0,0,0);
    hoy.setHours(0,0,0,0);

    let dias = 0;

    while (fecha < hoy) {
        fecha.setDate(fecha.getDate() + 1);

        let dia = fecha.getDay();

        if (dia !== 0) { // sin domingo
            dias++;
        }
    }

    return dias;
}

function limpiarDataParaTabla(data) {

    return data.filter(c => {

        if (c.estado !== "Caída") return true;

        const dias = diasHabilesPasados(c.fecha);

        return dias <= 2; // 🔥 SOLO deja máximo 2 días hábiles
    });
}

function getGestionUI(tipo, indicador) {

    if (!tipo) return { icon: "⚪", label: "Sin gestión", color: "#999" };

    tipo = tipo.toUpperCase();

    // 🟢 CONTACTO EFECTIVO
    if (tipo === "CEF") {
        return {
            icon: "🟢",
            label: indicador,
            color: "#27ae60"
        };
    }

    // 🟡 CONTACTO NO EFECTIVO
    if (tipo === "CNE") {
        return {
            icon: "🟡",
            label: indicador || "Contacto no efectivo",
            color: "#f39c12"
        };
    }

    // 🔴 NO CONTACTO
    if (tipo === "NOC") {
        return {
            icon: "🔴",
            label: indicador || "No contacto",
            color: "#c0392b"
        };
    }

    return {
        icon: "⚪",
        label: indicador || tipo,
        color: "#7f8c8d"
    };
}

function getIntentoClass(n) {
    if (n === 0) return "intento-bajo";
    if (n <= 2) return "intento-medio";
    return "intento-alto";
}

// 🧠 CLICK FUERA DEL MODAL
window.onclick = function(event) {
    let modal = document.getElementById("modal");
    if (event.target === modal) {
        cerrarModal();
    }
}