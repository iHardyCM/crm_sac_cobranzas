// 🔐 VALIDAR SESIÓN
const agente = localStorage.getItem("agente");

if (!agente) {
    alert("Sesión inválida, vuelve a iniciar sesión");
    window.location.href = "login.html";
}

// 🔥 EXTRAER DNI DESDE AGENTE (CORRECTO)
const dni = agente.substring(0, 8);
console.log("DNI USADO:", dni);

// 🔥 HEADER
const fecha = new Date();
const mes = fecha.toLocaleString('es-PE', { month: 'long' });
const anio = fecha.getFullYear();

document.getElementById("titulo_tabla").innerText =
    `Compromisos del mes (${mes} ${anio})`;

document.getElementById("usuario").innerText = `👤 ${agente}`;

// 🔥 VARIABLES GLOBALES
let dataGlobal = [];
let pagina = 1;
let porPagina = 10;

// 🔥 CARGA INICIAL
async function cargar() {

    try {

        const res = await fetch(`http://localhost:8000/compromisos/${dni}`);

        if (!res.ok) {
            throw new Error("Error en API");
        }

        const data = await res.json();

        console.log("DATA BACKEND:", data);

        dataGlobal = data.data || [];

        calcularKPIs(dataGlobal);
        renderTabla(dataGlobal);

    } catch (error) {
        console.error("ERROR CARGA:", error);
    }
}

cargar();


// 🔍 DETALLE
async function verDetalle(id) {

    try {

        const res = await fetch(`http://localhost:8000/compromisos/detalle/${id}`);
        const d = await res.json();

        document.getElementById("detalle").innerHTML = `
        <div class="modal-card">

            <!-- HEADER -->
            <div class="modal-header">
                <div>
                    <h3>Detalle del Compromiso</h3>
                    <small>#PDP-ID: ${d.id || "-"}</small>
                </div>
                <div class="badge-hoy">${d.estado || ""}</div>
            </div>

            <!-- CLIENTE -->
            <div class="modal-subheader">
                <div><b>${d.cliente || "-"}</b></div>
                <div>DNI: ${d.dni}</div>
                <div>Tel: ${d.telefono}</div>
            </div>

            <!-- RESUMEN -->
            <div class="modal-section">
                <h4>💰 Resumen del compromiso</h4>
                <div class="grid">
                    <div>Monto acordado:</div>
                    <div><b>${d.moneda} ${d.monto}</b></div>

                    <div>Monto pendiente:</div>
                    <div><b>${d.moneda} ${d.monto - (d.monto_pagado || 0)}</b></div>

                    <div>Fecha compromiso:</div>
                    <div>${d.fecha_compromiso}</div>

                    <div>Fecha creación:</div>
                    <div>${d.fecha_generado}</div>

                    <div>Tipo pago:</div>
                    <div>${d.tipo_pago || "-"}</div>
                </div>
            </div>

            <!-- INFO CLIENTE -->
            <div class="modal-section">
                <h4>📞 Información del cliente</h4>
                <div class="grid">
                    <div>Teléfono:</div>
                    <div>${d.telefono}</div>

                </div>
            </div>

            <!-- HISTORIAL -->
            <div class="modal-section">
                <h4>📝 Historial / Gestión</h4>
                <div class="box">
                    ${d.gestion || "Sin gestión registrada"}
                </div>
            </div>

            <!-- ACCIONES -->
            <div class="acciones">
                <button class="btn-yellow">⏳ Re-agendar</button>
                <button class="btn-blue" onclick="enviarWsp('${d.telefono}', ${d.monto}, '${d.fecha_compromiso}')">
                    📲 Contactar
                </button>
                <button class="btn-green">✔ Registrar pago</button>
            </div>

        </div>
        `;

        document.getElementById("modal").style.display = "flex";

    } catch (error) {
        console.error("ERROR DETALLE:", error);
    }
}


// 🔒 CERRAR MODAL
function cerrarModal() {
    document.getElementById("modal").style.display = "none";
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

        let okEstado = estado ? x.estado === estado : true;
        let okFecha = fecha ? x.fecha === fecha : true;

        let okTexto =
            (x.dni || "").toString().includes(texto) ||
            (x.telefono || "").toString().includes(texto);

        return okEstado && okFecha && okTexto;
    });

    pagina = 1;
    renderTabla(filtrado);
}


// 📊 TABLA
function renderTabla(data) {

    let inicio = (pagina - 1) * porPagina;
    let fin = inicio + porPagina;

    let paginado = data.slice(inicio, fin);

    let html = "";

    paginado.forEach(c => {

        let color = {
            "Hoy": "#e74c3c",
            "Caída": "#e67e22",
            "Vigente": "#f1c40f",
            "Cumplida": "#2ecc71"
        }[c.estado] || "#999";

        html += `
        <tr>
            <td>${c.cliente || "-"}</td>
            <td>${c.dni || "-"}</td>
            <td>${c.telefono || "-"}</td>
            <td>${c.monto || 0}</td>
            <td>${c.fecha || "-"}</td>
            <td><span class="badge" style="background:${color}">${c.estado}</td>
            <td>
                <button onclick="verDetalle(${c.id})">Ver</button>
                <button onclick="enviarWsp('${c.telefono}', ${c.monto}, '${c.fecha}')">📲</button>
            </td>
        </tr>`;
    });

    document.getElementById("tabla").innerHTML = html;

    document.getElementById("pagina_txt").innerText =
        `Página ${pagina} de ${Math.max(1, Math.ceil(data.length / porPagina))}`;
}


// ⏭ PAGINACIÓN
function next() {
    if (pagina < Math.ceil(dataGlobal.length / porPagina)) {
        pagina++;
        renderTabla(dataGlobal);
    }
}

function prev() {
    if (pagina > 1) {
        pagina--;
        renderTabla(dataGlobal);
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


// 🧠 CLICK FUERA DEL MODAL
window.onclick = function(event) {
    let modal = document.getElementById("modal");
    if (event.target === modal) {
        cerrarModal();
    }
}