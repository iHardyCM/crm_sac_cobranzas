function renderCliente(lista) {

    if (!lista || lista.length === 0) {
        document.getElementById("resultado").innerHTML = "❌ No encontrado";
        return;
    }

    const esGrupo = lista.length > 1 && lista[0].CodigoGrupo;

    let html = "";

    if (esGrupo) {
        html = renderGrupo(lista);
    } else {
        html = renderClienteIndividual(lista);
    }

    document.getElementById("resultado").innerHTML = html;
}

function renderClienteIndividual(lista) {

    const c = lista[0];

    const telefonos = [c.Telef_01, c.Telef_02, c.Telef_03, c.Telef_04]
        .filter(t => t && t !== "0")
        .map(t => `<span class="tag">${t}</span>`)
        .join("");

    let html = `
        <div class="cliente-header">

            <div class="cliente-nombre">
                ${safe(c.NomCliente)}
            </div>

            <div class="cliente-sub">
                <span>🪪 ${safe(c.DNI)}</span>
                <span>🧾 ${safe(c.codcliente)}</span>
            </div>

        </div>

        <div class="cliente-info">

            <div class="cliente-left">
                <div class="avatar">👤</div>
            </div>

            <div class="cliente-right">

                <div class="fila">
                    <div>
                        <span class="label">🪪 DNI</span>
                        <span class="value">${safe(c.DNI)}</span>
                    </div>

                    <div>
                        <span class="label">🧾 Código</span>
                        <span class="value">${safe(c.codcliente)}</span>
                    </div>

                    <div>
                        <span class="label">🎂 Edad</span>
                        <span class="value">${safe(c.Edad)}</span>
                    </div>

                    <div>
                        <span class="label">⚧ Sexo</span>
                        <span class="value">${safe(c.SexoCliente)}</span>
                    </div>

                    <div>
                        <span class="label">📅 Fec. Nacimiento</span>
                        <span class="value">${formatFecha(c.FecNacimiento)}</span>
                    </div>
                </div>

                <div class="fila">
                    <div class="direccion">
                        <span class="label">📍 Dirección</span>
                        <span class="value">${safe(c.Direccion_Principal)}</span>
                    </div>
                </div>

                <div class="fila">
                    <div>
                        <span class="label">🏙 Distrito</span>
                        <span class="value">${safe(c.Distrito_Principal)}</span>
                    </div>

                    <div class="telefonos">
                        <span class="label">📞 Teléfonos</span>
                        <div>${telefonos || "-"}</div>
                    </div>
                </div>

            </div>

        </div>

        <h3 class="titulo-creditos">💳 Créditos (${lista.length})</h3>
        <div class="contenedor-creditos">
    `;

    lista.forEach(cred => {
        html += renderCreditoCard(cred);
    });

    html += `</div>`;

    return html;
}

function renderGrupo(lista) {

    const grupo = lista[0];

    const totalDeuda = lista.reduce((acc, x) => acc + (x.Deuda_Total || 0), 0);
    const totalCapital = lista.reduce((acc, x) => acc + (x.SdoCapital || 0), 0);
    const totalVencido = lista.reduce((acc, x) => acc + (x.SdoCapitalVencido || 0), 0);
    const totalDesembolso = lista.reduce((acc, x) => acc + (x.MtoCapDesembolso || 0), 0);
    const maxDias = Math.max(...lista.map(x => x.DiasAtraso || 0));

    let html = `
        <div class="cliente-header">
            <div class="cliente-nombre">👥 ${grupo.NombreGrupo}</div>
            <div class="cliente-sub">Código: ${grupo.CodigoGrupo}</div>
        </div>

        <div class="grupo-kpis">

            <div class="kpi">
                <span>👥 Integrantes</span>
                <b>${lista.length}</b>
            </div>

            <div class="kpi">
                <span>💰 Deuda Total</span>
                <b>S/ ${format(totalDeuda)}</b>
            </div>

            <div class="kpi">
                <span>🏦 Capital</span>
                <b>S/ ${format(totalCapital)}</b>
            </div>

            <div class="kpi">
                <span>⚠️ Capital Vencido</span>
                <b>S/ ${format(totalVencido)}</b>
            </div>

            <div class="kpi">
                <span>📤 Desembolsado</span>
                <b>S/ ${format(totalDesembolso)}</b>
            </div>

            <div class="kpi">
                <span>🔥 Máx. Mora</span>
                <b>${maxDias} días</b>
            </div>

            <div class="kpi">
                <span>🏢 Oficina</span>
                <b>${grupo.NomOficina || "-"}</b>
            </div>

            <div class="kpi">
                <span>📦 Producto</span>
                <b>${grupo.Producto || "-"}</b>
            </div>

        </div>

        <h3>💳 Créditos (${lista.length})</h3>
        <div class="contenedor-creditos">
    `;

    lista.forEach(c => {
        html += renderCreditoCard(c);
    });

    html += `</div>`;

    return html;
}

function getTramo(c) {

    const dias = c.DiasAtraso || 0;
    const condicion = (c.Condicion || "").toUpperCase();

    // 🔥 prioridad máxima
    if (condicion === "CASTIGADO") return { label: "CASTIGADO", class: "tramo-castigado" };
    if (condicion === "JUDICIAL") return { label: "JUDICIAL", class: "tramo-castigado" };

    if (dias <= 8) return { label: "NORMAL", class: "tramo-normal" };
    if (dias <= 30) return { label: "CPP", class: "tramo-cpp" };
    if (dias <= 60) return { label: "DEFICIENTE", class: "tramo-deficiente" };
    if (dias <= 90) return { label: "DUDOSO 1", class: "tramo-dudoso" };
    if (dias <= 120) return { label: "DUDOSO 2", class: "tramo-dudoso" };

    return { label: "PERDIDA", class: "tramo-perdida" };
}

function getEmoji(t) {
    if (t === "NORMAL") return "🟢";
    if (t === "CPP") return "🟡";
    if (t === "DEFICIENTE") return "🟠";
    if (t.includes("DUDOSO")) return "🔴";
    if (t === "PERDIDA") return "🚨";
    if (t === "CASTIGADO") return "⚫";
    return "";
}

function renderCreditoCard(c) {
    
    const tramo = getTramo(c);
    return `
        <div class="credito-card">

            <div class="credito-header ${getEstadoClass(c)}">
                <span>CRÉDITO # ${safe(c.CodOperacion)}</span>

                <span class="badge ${tramo.class}">
                    ${getEmoji(tramo.label)} ${tramo.label}
                </span>
            </div>

            <div class="credito-body">

                <!-- COLUMNA 1 -->
                <div class="col">
                    <p><b>Producto:</b> ${safe(c.Producto)}</p>
                    <p><b>Línea:</b> ${safe(c.Linea_Negocio)}</p>
                    <p><b>Oficina:</b> ${safe(c.NomOficina)}</p>
                </div>

                <!-- COLUMNA 2 -->
                <div class="col">
                    <p><b>Deuda:</b> S/ ${format(c.Deuda_Total)}</p>
                    <p><b>Capital:</b> S/ ${format(c.SdoCapital)}</p>
                    <p><b>Días:</b> 
                        <span class="${getDiasClass(c)}">
                            ${safe(c.DiasAtraso)}
                        </span>
                    </p>
                </div>

                <!-- COLUMNA 3 -->
                <div class="col">
                    <p><b>Cuotas:</b> ${safe(c.NroCuotas_Aprobadas)}</p>
                    <p><b>Atrasadas:</b> ${safe(c.Nro_CuotasAtrasadas)}</p>
                    <p><b>Vencidas:</b> ${safe(c.Nro_CuotasVencidas)}</p>
                </div>

                <!-- COLUMNA 4 -->
                <div class="col">
                    <p><b>Segmento:</b> ${safe(c.SEGMENTO)}</p>
                    <p><b>Score:</b> ${safe(c.SCORE)}</p>
                    <p><b>Calificación:</b> ${safe(c.Calificacion)}</p>
                </div>

            </div>

            ${renderExtra(c)}

        </div>
    `;
}

//////////////////////////////////////////////////////////////
// 🔥 FUNCIONES AUXILIARES
//////////////////////////////////////////////////////////////

function formatFecha(fecha) {

    if (!fecha) return "-";

    // 🔹 caso 1: número o string tipo 20230325
    let str = fecha.toString().trim();

    if (/^\d{8}$/.test(str)) {
        return `${str.substring(0,4)}-${str.substring(4,6)}-${str.substring(6,8)}`;
    }

    // 🔹 caso 2: datetime SQL (2023-03-25T00:00:00)
    if (str.includes("T")) {
        return str.split("T")[0];
    }

    // 🔹 caso 3: ya viene tipo YYYY-MM-DD
    if (str.includes("-")) {
        return str.substring(0, 10);
    }

    return str;
}

function format(n) {
    return new Intl.NumberFormat("es-PE").format(n || 0);
}

function safe(v) {
    return v ?? "-";
}

function getEstadoClass(c) {

    const tramo = getTramo(c).label;

    if (tramo === "CASTIGADO") return "estado-negro";
    if (tramo === "PERDIDA") return "estado-rojo";
    if (tramo.includes("DUDOSO")) return "estado-rojo";
    if (tramo === "DEFICIENTE") return "estado-naranja";
    if (tramo === "CPP") return "estado-amarillo";

    return "estado-verde";
}

function getDiasClass(c) {

    const tramo = getTramo(c).label;

    if (tramo === "CASTIGADO") return "texto-negro";
    if (tramo === "PERDIDA") return "texto-rojo";
    if (tramo.includes("DUDOSO")) return "texto-rojo";
    if (tramo === "DEFICIENTE") return "texto-naranja";
    if (tramo === "CPP") return "texto-naranja";

    return "texto-verde";
}

function renderExtra(c) {

    // 🔢 valores NUMÉRICOS (para lógica)
    const cuota1_raw = (c.CT1||0)+(c.CT11||0)+(c.CT12||0)+(c.CT13||0)+(c.CT14||0)+(c.CT15||0);
    const cuota2_raw = (c.CT2||0)+(c.CT21||0)+(c.CT22||0)+(c.CT23||0)+(c.CT24||0)+(c.CT25||0);
    const cuota3_raw = (c.CT3||0)+(c.CT31||0)+(c.CT32||0)+(c.CT33||0)+(c.CT34||0)+(c.CT35||0);

    // 🎨 valores FORMATEADOS (para UI)
    const cuota1 = format(cuota1_raw);
    const cuota2 = format(cuota2_raw);
    const cuota3 = format(cuota3_raw);

    // 🔍 normalizamos condición
    const condicion = (c.Condicion || "").toUpperCase();

    // 🚫 reglas de negocio
    const bloquearCuotas = condicion.includes("CASTIGADO") || condicion.includes("JUDICIAL");

    // ✅ mostrar cuotas solo si:
    const mostrarCuotas = !bloquearCuotas &&
        (cuota1_raw > 0 || cuota2_raw > 0 || cuota3_raw > 0);

    let html = `<div class="credito-extra">`;

    // 💰 CUOTAS
    if (mostrarCuotas) {
        html += `
            <div class="cuotas-box">

                <div class="cuota">
                    <span>💸 Cuota 1</span>
                    <b>S/ ${cuota1}</b>
                </div>

                <div class="cuota">
                    <span>💸 Cuota 2</span>
                    <b>S/ ${cuota2}</b>
                </div>

                <div class="cuota">
                    <span>💸 Cuota 3</span>
                    <b>S/ ${cuota3}</b>
                </div>

            </div>
        `;
    }

    // 📊 INFO GENERAL
    html += `
        <p><b>Desembolso:</b> S/ ${format(c.MtoCapDesembolso)}</p>
        <p><b>Fec. Desembolso:</b> ${formatFecha(c.FecDesemb)}</p>
        <p><b>Último Pago:</b> ${formatFecha(c.FecUltPago)}</p>
    `;

    // ⚠️ CASTIGO
    if (c.FecCastigo) {
        html += `<p><b>Fecha Castigo:</b> ${formatFecha(c.FecCastigo)}</p>`;
    }

    // 👥 GRUPO
    if (c.NombreGrupo) {
        html += `
            <p><b>Grupo:</b> ${c.NombreGrupo}</p>
            <p><b>Código Grupo:</b> ${c.CodigoGrupo}</p>
        `;
    }

    html += `</div>`;

    return html;
}

function calcCuota1(c){
    return format((c.CT1||0)+(c.CT11||0)+(c.CT12||0)+(c.CT13||0)+(c.CT14||0)+(c.CT15||0));
}

function calcCuota2(c){
    return format((c.CT2||0)+(c.CT21||0)+(c.CT22||0)+(c.CT23||0)+(c.CT24||0)+(c.CT25||0));
}

function calcCuota3(c){
    return format((c.CT3||0)+(c.CT31||0)+(c.CT32||0)+(c.CT33||0)+(c.CT34||0)+(c.CT35||0));
}

function truncate(text, n = 25) {
    if (!text) return "-";
    return text.length > n ? text.substring(0, n) + "..." : text;
}

