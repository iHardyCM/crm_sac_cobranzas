async function buscar() {

    let valor = document.getElementById("valor").value.trim();

    if (!valor) {
        alert("Ingresa un valor");
        return;
    }

    document.getElementById("loader").style.display = "block";
    document.getElementById("resultado").innerHTML = "";

    try {

        // 🔥 SOLO MANDAMOS UN PARÁMETRO
        const res = await fetch(`http://localhost:8000/cliente/buscar?valor=${valor}`);
        const data = await res.json();

        document.getElementById("loader").style.display = "none";

        if (!data.encontrado) {
            document.getElementById("resultado").innerHTML = "❌ No encontrado";
            return;
        }

        renderCliente(data.data);

    } catch (e) {
        document.getElementById("loader").style.display = "none";
        document.getElementById("resultado").innerHTML = "⚠️ Error en la consulta";
    }
}

renderCompartamos(data.data);

function verDetalle(index) {
    const c = window._clientes[index];

    document.getElementById("detalle").innerHTML = `
        <div class="card">
            <h3>👤 ${c.NomCliente}</h3>
            <p><b>DNI:</b> ${c.DNI}</p>
            <p><b>CodCliente:</b> ${c.codcliente}</p>
            <p><b>Operación:</b> ${c["Cod Operación"]}</p>
        </div>

        <div class="card deuda">
            <h3>💰 Deuda</h3>
            <p><b>Total:</b> S/ ${formatearNumero(c.Deuda_Total)}</p>
            <p><b>Capital:</b> S/ ${formatearNumero(c.SdoCapital)}</p>
            <p>
                <b>Días atraso:</b> 
                <span style="
                    color: ${c.DiasAtraso > 60 ? 'red' : c.DiasAtraso > 30 ? 'orange' : 'green'};
                    font-weight: bold;
                ">
                    ${c.DiasAtraso}
                </span>
            </p>
        </div>

        <div class="card contacto">
            <h3>📞 Contacto</h3>
            <p>${c.Telef_01 || "-"}</p>
            <p>${c.Telef_02 || "-"}</p>
            <button onclick="copiarTexto('${c.Telef_01}')">📋 Copiar</button>
            function copiarTexto(texto) {
                if (!texto) {
                    alert("No hay número");
                    return;
                }

                navigator.clipboard.writeText(texto);
                alert("Número copiado");
            }
        </div>

        <div class="card segmentacion">
            <h3>🧠 Segmentación</h3>
            <p><b>Score:</b> ${c.SCORE}</p>
            <p><b>Segmento:</b> ${c.SEGMENTO}</p>
            <p><b>Tramo:</b> ${c.Tramo}</p>
        </div>
    `;
}

// 🔢 Formateo bonito de números
function formatearNumero(valor) {
    if (!valor) return "0";
    return new Intl.NumberFormat("es-PE").format(valor);
}

window.onload = function () {
    const params = new URLSearchParams(window.location.search);

    const dni = params.get("dni");
    const codcliente = params.get("codcliente");
    const operacion = params.get("operacion");

    if (dni || codcliente || operacion) {
        const valorInput = document.getElementById("valor");
        const tipoSelect = document.getElementById("tipo");

        if (dni) {
            valorInput.value = dni;
            tipoSelect.value = "dni";
        } else if (codcliente) {
            valorInput.value = codcliente;
            tipoSelect.value = "codcliente";
        } else if (operacion) {
            valorInput.value = operacion;
            tipoSelect.value = "operacion";
        }

        buscar(); // 🔥 ejecuta automáticamente
    }
};