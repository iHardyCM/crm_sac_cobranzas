function renderCliente(lista) {
    if (!lista || lista.length === 0) {
        mostrarMensajeCliente("No se encontraron clientes u operaciones con ese dato.", "empty");
        return;
    }

    window._clientes = lista;

    const esGrupo = lista.length > 1 && lista[0].CodigoGrupo != null;
    document.getElementById("resultado").innerHTML = esGrupo
        ? renderGrupo(lista)
        : renderClienteIndividual(lista);
}

function renderClienteIndividual(lista) {
    const c = lista[0];
    const telefonos = [c.Telef_01, c.Telef_02, c.Telef_03, c.Telef_04]
        .filter(t => t && String(t) !== "0")
        .map(t => `<span class="tag">${h(t)}</span>`)
        .join("");

    return `
        <div class="cliente-header">
            <div>
                <span class="section-kicker">Cliente individual</span>
                <div class="cliente-nombre">${h(c.NomCliente)}</div>
                <div class="cliente-sub">
                    <span>DNI: ${h(c.DNI)}</span>
                    <span>Codigo: ${h(c.codcliente)}</span>
                    <span>Operaciones: ${lista.length}</span>
                </div>
            </div>
        </div>

        <div class="cliente-info">
            <div class="cliente-left">
                <div class="avatar">${initials(c.NomCliente)}</div>
            </div>
            <div class="cliente-right">
                <div class="fila">
                    ${infoItem("DNI", c.DNI)}
                    ${infoItem("Codigo cliente", c.codcliente)}
                    ${infoItem("Edad", c.Edad)}
                    ${infoItem("Sexo", c.SexoCliente)}
                    ${infoItem("Nacimiento", formatFecha(c.FecNacimiento))}
                </div>
                <div class="fila">
                    <div class="direccion">
                        <span class="label">Direccion</span>
                        <span class="value">${h(c.Direccion_Principal)}</span>
                    </div>
                    ${infoItem("Distrito", c.Distrito_Principal)}
                </div>
                <div class="fila">
                    <div class="telefonos">
                        <span class="label">Telefonos</span>
                        <div>${telefonos || "<span class='muted'>Sin telefonos registrados</span>"}</div>
                    </div>
                </div>
            </div>
        </div>

        <div class="section-title-row">
            <div>
                <span class="section-kicker">Detalle financiero</span>
                <h3 class="titulo-creditos">Operaciones actualizadas (${lista.length})</h3>
            </div>
        </div>
        <div class="contenedor-creditos creditos-lista">
            ${lista.map(cred => renderCreditoCard(cred)).join("")}
        </div>
    `;
}

function renderGrupo(lista) {
    const grupo = lista[0];
    const totalDeuda = lista.reduce((acc, x) => acc + numberValue(x.Deuda_Total), 0);
    const totalCapital = lista.reduce((acc, x) => acc + numberValue(x.SdoCapital), 0);
    const totalVencido = lista.reduce((acc, x) => acc + numberValue(x.SdoCapitalVencido), 0);
    const totalDesembolso = lista.reduce((acc, x) => acc + numberValue(x.MtoCapDesembolso), 0);
    const maxDias = Math.max(...lista.map(x => numberValue(x.DiasAtraso)));

    return `
        <div class="cliente-header">
            <div>
                <span class="section-kicker">Credito grupal</span>
                <div class="cliente-nombre">${h(grupo.NombreGrupo)}</div>
                <div class="cliente-sub">
                    <span>Codigo grupo: ${h(grupo.CodigoGrupo)}</span>
                    <span>Oficina: ${h(grupo.NomOficina)}</span>
                    <span>Producto: ${h(grupo.Producto)}</span>
                </div>
            </div>
        </div>

        <div class="grupo-kpis">
            ${kpi("Integrantes", lista.length)}
            ${kpi("Deuda total", money(totalDeuda))}
            ${kpi("Capital", money(totalCapital))}
            ${kpi("Capital vencido", money(totalVencido))}
            ${kpi("Desembolsado", money(totalDesembolso))}
            ${kpi("Max. mora", `${maxDias} dias`)}
            ${kpi("Oficina", grupo.NomOficina)}
            ${kpi("Producto", grupo.Producto)}
        </div>

        <div class="section-title-row">
            <div>
                <span class="section-kicker">Detalle financiero</span>
                <h3 class="titulo-creditos">Operaciones del grupo (${lista.length})</h3>
            </div>
        </div>
        <div class="contenedor-creditos creditos-lista">
            ${lista.map(c => renderCreditoCard(c)).join("")}
        </div>
    `;
}

function renderCreditoCard(c) {
    const tramo = getTramo(c);
    return `
        <article class="credito-card credito-card-v2 ${getEstadoClass(c)}">
            <header class="credito-header">
                <div>
                    <span class="section-kicker">Operacion</span>
                    <strong># ${h(c.CodOperacion)}</strong>
                </div>
                <span class="badge ${tramo.class}" title="${h(tramo.descripcion)}">${tramo.label}</span>
            </header>

            <div class="credito-body credito-body-v2">
                ${metricItem("Producto", c.Producto, "wide")}
                ${metricItem("Linea", c.Linea_Negocio)}
                ${metricItem("Oficina", c.NomOficina)}
                ${metricItem("Deuda", money(c.Deuda_Total), "money")}
                ${metricItem("Capital", money(c.SdoCapital), "money")}
                ${metricItem("Dias atraso", c.DiasAtraso, getDiasClass(c))}
                ${metricItem("Cuotas", c.NroCuotas_Aprobadas)}
                ${metricItem("Atrasadas", c.Nro_CuotasAtrasadas)}
                ${metricItem("Vencidas", c.Nro_CuotasVencidas)}
                ${metricItem("Segmento", c.SEGMENTO, "wide")}
                ${metricItem("Score", c.SCORE)}
                ${metricItem("Calificacion", tramo.label, tramo.class)}
            </div>

            ${renderExtra(c)}
        </article>
    `;
}

function renderExtra(c) {
    const cuota1Raw = numberValue(c.CT1) + numberValue(c.CT11) + numberValue(c.CT12) + numberValue(c.CT13) + numberValue(c.CT14) + numberValue(c.CT15);
    const cuota2Raw = numberValue(c.CT2) + numberValue(c.CT21) + numberValue(c.CT22) + numberValue(c.CT23) + numberValue(c.CT24) + numberValue(c.CT25);
    const cuota3Raw = numberValue(c.CT3) + numberValue(c.CT31) + numberValue(c.CT32) + numberValue(c.CT33) + numberValue(c.CT34) + numberValue(c.CT35);

    const condicion = String(c.Condicion || "").toUpperCase();
    const mostrarCuotas = !condicion.includes("CASTIGADO")
        && !condicion.includes("JUDICIAL")
        && (cuota1Raw > 0 || cuota2Raw > 0 || cuota3Raw > 0);

    return `
        <div class="credito-extra">
            ${mostrarCuotas ? `
                <div class="cuotas-box">
                    ${cuota("Cuota 1", cuota1Raw)}
                    ${cuota("Cuota 2", cuota2Raw)}
                    ${cuota("Cuota 3", cuota3Raw)}
                </div>
            ` : ""}
            <div class="extra-grid">
                ${extraItem("Desembolso", money(c.MtoCapDesembolso))}
                ${extraItem("Fec. desembolso", formatFecha(c.FecDesemb))}
                ${extraItem("Ultimo pago", formatFecha(c.FecUltPago))}
                ${c.FecCastigo ? extraItem("Fecha castigo", formatFecha(c.FecCastigo)) : ""}
                ${c.NombreGrupo ? extraItem("Grupo", c.NombreGrupo) : ""}
                ${c.CodigoGrupo ? extraItem("Codigo grupo", c.CodigoGrupo) : ""}
            </div>
        </div>
    `;
}

function limpiarBusqueda() {
    const valor = document.getElementById("valor");
    const loader = document.getElementById("loader");
    const resultado = document.getElementById("resultado");

    if (valor) {
        valor.value = "";
        valor.focus();
    }
    if (loader) loader.style.display = "none";
    if (resultado) {
        resultado.innerHTML = `
            <div class="clientes-empty">
                <strong>Realiza una busqueda para empezar.</strong>
                <span>Los resultados apareceran aqui con la ultima informacion diaria enviada por Compartamos para clientes activos.</span>
            </div>
        `;
    }
}

function getTramo(c) {
    const dias = numberValue(c.DiasAtraso);
    const condicion = String(c.Condicion || "").toUpperCase();

    if (condicion === "CASTIGADO") {
        return { label: "CASTIGADO", class: "tramo-castigado", descripcion: "Operacion castigada" };
    }
    if (condicion === "JUDICIAL") {
        return { label: "JUDICIAL", class: "tramo-castigado", descripcion: "Operacion judicial" };
    }
    if (dias <= 8) {
        return { label: "NORMAL", class: "tramo-normal", descripcion: "Clientes al dia: 0 a 8 dias de atraso" };
    }
    if (dias <= 30) {
        return { label: "CPP", class: "tramo-cpp", descripcion: "Con problemas potenciales: 9 a 30 dias de atraso" };
    }
    if (dias <= 60) {
        return { label: "DEFICIENTE", class: "tramo-deficiente", descripcion: "Deficiente: 31 a 60 dias de atraso" };
    }
    if (dias <= 90) {
        return { label: "DUDOSO 1", class: "tramo-dudoso", descripcion: "Dudoso 1: 61 a 90 dias de atraso" };
    }
    if (dias <= 120) {
        return { label: "DUDOSO 2", class: "tramo-dudoso", descripcion: "Dudoso 2: 91 a 120 dias de atraso" };
    }
    return { label: "PERDIDA", class: "tramo-perdida", descripcion: "Perdida: mas de 120 dias de atraso" };
}

function getEstadoClass(c = {}) {
    const tramo = getTramo(c).label;
    if (tramo === "CASTIGADO" || tramo === "JUDICIAL") return "estado-negro";
    if (tramo === "PERDIDA" || tramo.includes("DUDOSO")) return "estado-rojo";
    if (tramo === "DEFICIENTE") return "estado-naranja";
    if (tramo === "CPP") return "estado-amarillo";
    return "estado-verde";
}

function getDiasClass(c) {
    const tramo = getTramo(c).label;
    if (tramo === "CASTIGADO" || tramo === "JUDICIAL") return "texto-negro";
    if (tramo === "PERDIDA" || tramo.includes("DUDOSO")) return "texto-rojo";
    if (tramo === "DEFICIENTE" || tramo === "CPP") return "texto-naranja";
    return "texto-verde";
}

function formatFecha(fecha) {
    if (!fecha) return "-";
    const str = String(fecha).trim();
    if (/^\d{8}$/.test(str)) {
        return `${str.substring(6, 8)}/${str.substring(4, 6)}/${str.substring(0, 4)}`;
    }
    if (str.includes("T")) {
        const [year, month, day] = str.split("T")[0].split("-");
        return `${day}/${month}/${year}`;
    }
    if (/^\d{4}-\d{2}-\d{2}/.test(str)) {
        const [year, month, day] = str.substring(0, 10).split("-");
        return `${day}/${month}/${year}`;
    }
    return str;
}

function format(n) {
    return new Intl.NumberFormat("es-PE").format(numberValue(n));
}

function money(n) {
    return `S/ ${new Intl.NumberFormat("es-PE", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    }).format(numberValue(n))}`;
}

function numberValue(value) {
    const n = Number(value);
    return Number.isFinite(n) ? n : 0;
}

function safe(v) {
    return v ?? "-";
}

function h(value) {
    return String(safe(value))
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

function initials(name) {
    const parts = String(name || "Cliente")
        .trim()
        .split(/\s+/)
        .filter(Boolean)
        .slice(0, 2);
    return parts.map(part => part[0]).join("").toUpperCase() || "CL";
}

function infoItem(label, value) {
    return `
        <div>
            <span class="label">${h(label)}</span>
            <span class="value">${h(value)}</span>
        </div>
    `;
}

function extraItem(label, value) {
    return `
        <div>
            <span>${h(label)}</span>
            <b>${h(value)}</b>
        </div>
    `;
}

function kpi(label, value) {
    return `
        <div class="kpi">
            <span>${h(label)}</span>
            <b>${h(value)}</b>
        </div>
    `;
}

function cuota(label, value) {
    return `
        <div class="cuota">
            <span>${h(label)}</span>
            <b>${money(value)}</b>
        </div>
    `;
}

function metricItem(label, value, extraClass = "") {
    return `
        <div class="metric-item ${extraClass}">
            <span>${h(label)}</span>
            <b>${h(value)}</b>
        </div>
    `;
}
