const supervisor =
    new URLSearchParams(window.location.search).get("agente")
    || localStorage.getItem("agente")
    || "Supervisor";

if (!exigirSesion()) {
    throw new Error("Sesion invalida");
}

document.getElementById("usuario").innerText =
    `👤 Supervisor: ${supervisor}`;

let dataGlobal = [];
let ordenCampo = null;
let ordenDireccion = "desc";

const BASE_URL = `${window.location.protocol}//${window.location.hostname}:8000`;

async function cargarSupervisor() {

    const params = new URLSearchParams(window.location.search);
    const dni = params.get("dni") || localStorage.getItem("dni");

    const res = await fetch(`${BASE_URL}/compromisos/supervisor/resumen?dni=${dni}`);
    const data = await res.json();

    console.log("DATA SUPERVISOR:", data);

    if (!data.ok) {
        alert("Error cargando datos");
        return;
    }

    let total = 0;
    let monto = 0;
    
    let montoPdpAlDia = 0;
    let montoPagadoAlDia = 0;
    let montoCaidoAlDia = 0;

    data.data.forEach(row => {

        total += row.TOTAL;
        monto += row.MONTO_TOTAL;

        montoPdpAlDia += Number(row.MONTO_PDP_AL_DIA || 0);
        montoPagadoAlDia += Number(row.MONTO_PAGADO_AL_DIA || 0);
        montoCaidoAlDia += Number(row.MONTO_CAIDO_AL_DIA || 0);

    });

    dataGlobal = data.data;

    renderTablaSupervisor(dataGlobal);

    // KPIs
    document.getElementById("kpi_total").innerText = total;

    document.getElementById("kpi_monto").innerText =
        `S/ ${monto.toLocaleString('es-PE', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        })}`;

    document.getElementById("kpi_recupero").innerText =
        `S/ ${montoPagadoAlDia.toLocaleString('es-PE', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        })}`;

    const eficacia =
        montoPdpAlDia
            ? ((montoPagadoAlDia / montoPdpAlDia) * 100).toFixed(1)
            : 0;

    const tasaCaida =
        montoPdpAlDia
            ? ((montoCaidoAlDia / montoPdpAlDia) * 100).toFixed(1)
            : 0;

    document.getElementById("kpi_eficacia").innerText =
        `${eficacia}%`;

    document.getElementById("kpi_caida").innerText =
        `${tasaCaida}%`;
}

function verAgente(agente) {

    console.log("AGENTE SELECCIONADO:", agente);

    localStorage.setItem("agente_filtro", agente);

    const params = new URLSearchParams(window.location.search);
    const supervisorDni = params.get("dni") || localStorage.getItem("dni") || "";

    window.location.href =
        `compromisos.html?agente=${encodeURIComponent(agente)}&supervisor_dni=${encodeURIComponent(supervisorDni)}`;
}

function verAgenteEstado(agenteCodificado, estado) {
    const agente = decodeURIComponent(agenteCodificado);
    const params = new URLSearchParams(window.location.search);
    const supervisorDni = params.get("dni") || localStorage.getItem("dni") || "";

    localStorage.setItem("agente_filtro", agente);

    window.location.href =
        `compromisos.html?agente=${encodeURIComponent(agente)}&estado=${encodeURIComponent(estado)}&supervisor_dni=${encodeURIComponent(supervisorDni)}`;
}

function renderTablaSupervisor(data){

    let html = "";

    data.forEach(row => {

        html += `
        <tr>
            <td>${row.AGENTE}</td>

            <td>${row.TOTAL}</td>

            <td>
                S/ ${Number(row.MONTO_TOTAL).toLocaleString('es-PE')}
            </td>

            <td>
                <button class="badge badge-red badge-click"
                    onclick="verAgenteEstado('${encodeURIComponent(row.AGENTE)}', 'Hoy')"
                    title="Ver PDP de hoy del agente">
                    ${row.HOY}
                </button>
            </td>

            <td>
                <span class="badge badge-orange">
                    ${row.CAIDA}
                </span>
            </td>

            <td>
                <span class="badge badge-yellow">
                    ${row.VIGENTE}
                </span>
            </td>

            <td>
                <span class="badge badge-green">
                    ${row.CUMPLIDA}
                </span>
            </td>

            <td>
                <button class="btn-ver"
                    onclick="verAgente('${row.AGENTE}')">
                    Ver
                </button>
            </td>
        </tr>
        `;
    });

    document.getElementById("tablaSupervisor").innerHTML = html;
}

function ordenarPor(campo){

    if(ordenCampo === campo){
        ordenDireccion =
            ordenDireccion === "asc"
            ? "desc"
            : "asc";
    }else{
        ordenCampo = campo;
        ordenDireccion = "desc";
    }

    dataGlobal.sort((a,b)=>{

        let valA = a[campo];
        let valB = b[campo];

        if(typeof valA === "string"){
            valA = valA.toUpperCase();
            valB = valB.toUpperCase();
        }

        if(valA < valB)
            return ordenDireccion === "asc" ? -1 : 1;

        if(valA > valB)
            return ordenDireccion === "asc" ? 1 : -1;

        return 0;
    });

    renderTablaSupervisor(dataGlobal);
}

function exportarCartera(){

    const params = new URLSearchParams(window.location.search);
    const dni = params.get("dni") || localStorage.getItem("dni");

    window.open(
        `${BASE_URL}/compromisos/supervisor/exportar-cartera?dni=${dni}`
    );
}
