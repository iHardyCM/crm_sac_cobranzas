const BASE_URL = `${window.location.protocol}//${window.location.hostname}:8000`;

async function cargarSupervisor() {

    const dni = localStorage.getItem("dni");

    const res = await fetch(`${BASE_URL}/compromisos/supervisor/resumen?dni=${dni}`);
    const data = await res.json();

    if (!data.ok) {
        alert("Error cargando datos");
        return;
    }

    let html = "";

    let total = 0;
    let monto = 0;
    let cumplida = 0;
    let caida = 0;

    data.data.forEach(row => {

        total += row.TOTAL;
        monto += row.MONTO_TOTAL;
        cumplida += row.CUMPLIDA;
        caida += row.CAIDA;

        html += `
        <tr>
            <td>${row.AGENTE}</td>
            <td>${row.TOTAL}</td>
            <td>${row.HOY}</td>
            <td>${row.CAIDA}</td>
            <td>${row.VIGENTE}</td>
            <td>${row.CUMPLIDA}</td>
            <td>S/ ${Number(row.MONTO_TOTAL).toLocaleString('es-PE')}</td>
            <td>
                <button onclick="verAgente('${row.AGENTE.split(' - ')[0]}')">Ver</button>
            </td>
        </tr>
        `;
    });

    document.getElementById("tablaSupervisor").innerHTML = html;

    // KPIs
    document.getElementById("kpi_total").innerText = total;
    document.getElementById("kpi_monto").innerText =
        `S/ ${monto.toLocaleString('es-PE')}`;

    const eficacia = total ? ((cumplida / total) * 100).toFixed(1) : 0;
    const tasaCaida = total ? ((caida / total) * 100).toFixed(1) : 0;

    document.getElementById("kpi_eficacia").innerText = `${eficacia}%`;
    document.getElementById("kpi_caida").innerText = `${tasaCaida}%`;
}

function verAgente(agente) {

    const usuario = agente.split(" - ")[0];

    console.log("AGENTE SELECCIONADO:", usuario);

    localStorage.setItem("agente_filtro", usuario);

    window.location.href = "compromisos.html";
}