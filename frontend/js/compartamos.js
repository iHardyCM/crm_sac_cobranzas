function renderCliente(lista) {
    if (!Array.isArray(lista) || lista.length === 0) {
        mostrarMensajeCliente("No se encontraron clientes u operaciones con ese dato.", "empty");
        return;
    }

    const resultado = document.getElementById("resultado");
    if (!resultado) return;

    const esGrupo = esResultadoGrupal(lista);
    window._clientes = lista;
    window._modoConsulta = esGrupo ? "grupo" : "individual";
    window._indiceOperacionSeleccionada = 0;
    resultado.innerHTML = esGrupo
        ? renderConsultaGrupal(lista)
        : renderConsultaIndividual(lista);
}

function esResultadoGrupal(lista) {
    const valorBuscado = document.getElementById("valor")?.value?.trim();
    if (tieneValor(valorBuscado)) {
        return lista.some(item => [
            primerValorReal(item, ["CodigoGrupo", "CODIGOGRUPO"]),
            primerValorReal(item, ["CodCreGrupal", "CODCREGRUPAL"])
        ].some(value => esIdentificadorGrupoReal(value) && String(value).trim() === String(valorBuscado).trim()));
    }

    return lista.some(item => [
        primerValorReal(item, ["CodigoGrupo", "CODIGOGRUPO"]),
        primerValorReal(item, ["CodCreGrupal", "CODCREGRUPAL"]),
        primerValorReal(item, ["NombreGrupo", "NOMBREGRUPO", "NomGrupo"])
    ].some(esIdentificadorGrupoReal));
}

function esIdentificadorGrupoReal(value) {
    if (!tieneValor(value)) return false;
    const texto = String(value).trim();
    return !/^0+(?:[.,]0+)?$/.test(texto);
}

function renderConsultaIndividual(lista) {
    return `
        ${renderCabeceraIndividual(lista)}
        ${renderKpisIndividual(lista)}
        ${renderTablaIndividual(lista)}
        <div id="detalleOperacionSeleccionada" class="detalle-operacion-host is-visible" aria-live="polite">
            ${renderDetalleIndividual(lista[0])}
        </div>
        ${renderDatosComplementariosCliente(lista)}
    `;
}

function renderCabeceraIndividual(lista) {
    const nombre = campoCliente(lista, ["NomCliente", "NOMCLIENTE", "NombreCliente"]);
    const datos = [
        ["DNI", campoCliente(lista, ["DNI"])],
        ["Código cliente", campoCliente(lista, ["codcliente", "CodCliente"])],
        ["Edad", formatNumero(campoClienteReal(lista, ["Edad", "EDAD"]))],
        ["Sexo", campoCliente(lista, ["SexoCliente", "SEXOCLIENTE"])],
        ["Oficina", campoCliente(lista, ["NomOficina", "NOMOFICINA"])],
        ["Territorio", campoCliente(lista, ["Territorio", "TERRITORIO"])],
        ["Segmento", campoCliente(lista, ["SEGMENTO", "Segmento"])],
        ["Línea de negocio", campoCliente(lista, ["Linea_Negocio", "LineaNegocio", "LINEA_NEGOCIO"])],
        ["Calificacion", campoCliente(lista, ["Calificacion", "CALIFICACION", "calificacion"])]
    ];

    return `
        <section class="entidad-cabecera entidad-cabecera-individual" aria-labelledby="tituloClienteIndividual">
            <div class="entidad-identidad">
                <div class="avatar avatar-entidad" aria-hidden="true">${initials(nombre)}</div>
                <div>
                    <span class="section-kicker">Cliente individual</span>
                    <h2 id="tituloClienteIndividual">${h(nombre)}</h2>
                    <p>Vista consolidada de las operaciones asignadas al cliente.</p>
                </div>
            </div>
            <div class="entidad-meta-grid">
                ${datos.map(([label, value]) => datoCabecera(label, value)).join("")}
            </div>
        </section>
    `;
}

function renderKpisIndividual(lista) {
    const moraMaxima = maximoValido(lista.map(item => item.DiasAtraso));
    const ultimoPago = maxFechaValida(lista.map(item => item.FecUltPago));
    const items = [
        ["Operaciones", format(lista.length)],
        ["Deuda total", money(sumarValores(lista, "Deuda_Total"))],
        ["Capital total", money(sumarValores(lista, "SdoCapital"))],
        ["Capital vencido", money(sumarValores(lista, "SdoCapitalVencido"))],
        ["Desembolso total", money(sumarValores(lista, "MtoCapDesembolso"))],
        ["Máxima mora", moraMaxima === null ? "—" : `${format(moraMaxima)} días`],
        ["Último pago", formatFecha(ultimoPago)]
    ];

    return `
        <section class="cliente-kpis-consolidados" aria-label="KPIs consolidados del cliente">
            ${items.map(([label, value]) => kpi(label, value)).join("")}
        </section>
    `;
}

function renderTablaIndividual(lista) {
    return `
        <section class="cuentas-tabla-panel tabla-individual-panel" aria-labelledby="tituloTablaOperaciones">
            ${cabeceraTabla("Operaciones del cliente", lista.length, "Selecciona una operación para actualizar su detalle sin perder el contexto del cliente.")}
            <div class="cuentas-tabla-scroll">
                <table class="cuentas-tabla cuentas-tabla-individual">
                    <thead>
                        <tr>
                            <th scope="col">Operación</th>
                            <th scope="col">Producto</th>
                            <th scope="col">Línea</th>
                            <th scope="col">Condición</th>
                            <th scope="col" class="numero">Deuda</th>
                            <th scope="col" class="numero">Capital</th>
                            <th scope="col" class="numero">Capital vencido</th>
                            <th scope="col" class="numero">Días atraso</th>
                            <th scope="col" class="numero">Cuotas atrasadas</th>
                            <th scope="col" class="numero">Cuotas vencidas</th>
                            <th scope="col">Última cuota atrasada</th>
                            <th scope="col" class="numero">Monto cuota</th>
                            <th scope="col">Último pago</th>
                            <th scope="col">Clasificación</th>
                            <th scope="col">Acción</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${lista.map((cuenta, index) => renderFilaIndividual(cuenta, index)).join("")}
                    </tbody>
                </table>
            </div>
        </section>
    `;
}

function renderFilaIndividual(cuenta, index) {
    const seleccionada = index === 0;
    const operacion = operacionDe(cuenta);
    return `
        <tr class="cuenta-fila${seleccionada ? " is-selected" : ""}" data-cuenta-index="${index}">
            <td data-label="Operación">
                <button class="cuenta-operacion" type="button" data-seleccionar-operacion="${index}" aria-current="${seleccionada}" aria-label="Seleccionar operación ${h(operacion)}">
                    <strong>${h(operacion)}</strong><span aria-hidden="true">›</span>
                </button>
            </td>
            <td data-label="Producto">${h(valorCampo(cuenta, ["Producto", "PRODUCTO"]))}</td>
            <td data-label="Línea">${h(valorCampo(cuenta, ["Linea_Negocio", "LineaNegocio", "LINEA_NEGOCIO"]))}</td>
            <td data-label="Condición">${h(valorCampo(cuenta, ["Condicion", "CONDICION"]))}</td>
            <td data-label="Deuda" class="numero">${h(money(cuenta.Deuda_Total))}</td>
            <td data-label="Capital" class="numero">${h(money(cuenta.SdoCapital))}</td>
            <td data-label="Capital vencido" class="numero">${h(money(cuenta.SdoCapitalVencido))}</td>
            <td data-label="Días atraso" class="numero">${h(formatNumeroUnidad(cuenta.DiasAtraso, "días"))}</td>
            <td data-label="Cuotas atrasadas" class="numero">${h(formatNumero(cuenta.Nro_CuotasAtrasadas))}</td>
            <td data-label="Cuotas vencidas" class="numero">${h(formatNumero(cuenta.Nro_CuotasVencidas))}</td>
            <td data-label="Última cuota atrasada">${h(ultimaCuotaAtrasadaDe(cuenta))}</td>
            <td data-label="Monto cuota" class="numero">${h(money(montoCuotaDe(cuenta)))}</td>
            <td data-label="Último pago">${h(formatFecha(cuenta.FecUltPago))}</td>
            <td data-label="Clasificación">${h(valorCampo(cuenta, ["Calificacion", "CALIFICACION", "calificacion"]))}</td>
            <td data-label="Acción" class="cuenta-accion-celda">
                <button class="cuenta-ver-detalle" type="button" data-seleccionar-operacion="${index}" aria-current="${seleccionada}">Ver detalle</button>
            </td>
        </tr>
    `;
}

function renderDetalleIndividual(cuenta) {
    const operacion = operacionDe(cuenta);
    const cuotas = obtenerCuotasVisuales(cuenta);
    const datos = [
        ["Oficina", valorCampo(cuenta, ["NomOficina", "NOMOFICINA"])],
        ["Segmento", valorCampo(cuenta, ["SEGMENTO", "Segmento"])],
        ["Condición", valorCampo(cuenta, ["Condicion", "CONDICION"])],
        ["Desembolso", money(cuenta.MtoCapDesembolso)],
        ["Fecha desembolso", formatFecha(cuenta.FecDesemb)],
        ["Cuotas aprobadas", formatNumero(cuenta.NroCuotas_Aprobadas)],
        ["Cuotas atrasadas", formatNumero(cuenta.Nro_CuotasAtrasadas)],
        ["Cuotas vencidas", formatNumero(cuenta.Nro_CuotasVencidas)],
        ["Última cuota atrasada", ultimaCuotaAtrasadaDe(cuenta)],
        ["Monto cuota", money(montoCuotaDe(cuenta))],
        ["Capital vencido", money(cuenta.SdoCapitalVencido)],
        ["Capital", money(cuenta.SdoCapital)],
        ["Deuda total", money(cuenta.Deuda_Total)],
        ["Días atraso", formatNumeroUnidad(cuenta.DiasAtraso, "días")],
        ["Último pago", formatFecha(cuenta.FecUltPago)],
        ["Último vencimiento", formatFecha(cuenta.UltFecVen)]
    ];

    return `
        <section class="detalle-operacion-panel" aria-labelledby="tituloDetalleOperacion" data-detalle-operacion="${h(operacion)}">
            <header class="detalle-operacion-header">
                <div>
                    <span class="section-kicker">Operación activa</span>
                    <h3 id="tituloDetalleOperacion">Detalle de operación seleccionada</h3>
                    <p>${h(operacion)} · ${h(valorCampo(cuenta, ["Producto", "PRODUCTO"]))}</p>
                </div>
                <span class="detalle-operacion-indicador">Seleccionada</span>
            </header>
            <div class="detalle-operacion-grid">
                ${datos.map(([label, value]) => detalleDato(label, value)).join("")}
            </div>
            <div class="cuotas-visualizacion">
                <div class="cuotas-visualizacion-copy">
                    <span class="section-kicker">Cálculo visual</span>
                    <strong>Cuotas de cancelación</strong>
                    <small>Se muestran solo cuando todos los componentes de la formula estan disponibles.</small>
                </div>
                ${cuotas.map((value, index) => detalleDato(`Cuota ${index + 1}`, money(value))).join("")}
            </div>
        </section>
    `;
}

function renderDatosComplementariosCliente(lista) {
    const datos = [
        ["Dirección principal", campoCliente(lista, ["Direccion_Principal", "DireccionPrincipal"])],
        ["Distrito", campoCliente(lista, ["Distrito_Principal", "DistritoPrincipal", "Distrito"])],
        ["Dirección negocio", campoCliente(lista, ["Direccion_Negocio", "DireccionNegocio"])],
        ["Teléfonos", telefonosTextoCliente(lista)],
        ["Fecha de nacimiento", formatFecha(campoClienteReal(lista, ["FecNacimiento", "FechaNacimiento"]))],
        ["Actividad económica", campoCliente(lista, ["ActividadEconomica", "Actividad_Economica", "ACTIVIDADECONOMICA"])]
    ];

    return `
        <section class="datos-cliente-panel" aria-labelledby="tituloDatosCliente">
            <header><span class="section-kicker">Información complementaria</span><h3 id="tituloDatosCliente">Datos del cliente</h3></header>
            <div class="datos-cliente-grid">${datos.map(([label, value]) => detalleDato(label, value)).join("")}</div>
        </section>
    `;
}

function renderConsultaGrupal(lista) {
    return `
        ${renderCabeceraGrupo(lista)}
        ${renderKpisGrupo(lista)}
        ${renderTablaGrupo(lista)}
        <div id="detalleOperacionSeleccionada" class="detalle-operacion-host is-visible" aria-live="polite">
            ${renderDetalleGrupo(lista[0])}
        </div>
    `;
}

function renderCabeceraGrupo(lista) {
    const principal = lista[0] || {};
    const nombre = valorCampo(principal, ["NombreGrupo", "NOMBREGRUPO", "NomGrupo"]);
    const datos = [
        ["Codigo grupo", valorCampo(principal, ["CodigoGrupo", "CODIGOGRUPO"])],
        ["Credito grupal", valorCampo(principal, ["CodCreGrupal", "CODCREGRUPAL"])],
        ["Oficina", valorCampo(principal, ["NomOficina", "NOMOFICINA"])]
    ];
    return `
        <section class="entidad-cabecera entidad-cabecera-grupo" aria-labelledby="tituloGrupo">
            <div class="entidad-identidad"><div class="avatar avatar-entidad" aria-hidden="true">${initials(nombre)}</div><div><span class="section-kicker">Grupo</span><h2 id="tituloGrupo">${h(nombre)}</h2><p>Consulta consolidada del credito grupal y sus integrantes.</p></div></div>
            <div class="entidad-meta-grid entidad-meta-grid-grupo">${datos.map(([label, value]) => datoCabecera(label, value)).join("")}</div>
        </section>
    `;
}

function renderKpisGrupo(lista) {
    const moraMaxima = maximoValido(lista.map(item => item.DiasAtraso));
    return `<section class="cliente-kpis-consolidados grupo-kpis-consolidados" aria-label="KPIs consolidados del grupo">
        ${kpi("Operaciones", format(lista.length))}${kpi("Integrantes", format(contarIntegrantes(lista)))}
        ${kpi("Deuda total", money(sumarValores(lista, "Deuda_Total")))}${kpi("Capital total", money(sumarValores(lista, "SdoCapital")))}
        ${kpi("Maxima mora", moraMaxima === null ? "—" : `${format(moraMaxima)} dias`)}
    </section>`;
}

function renderTablaGrupo(lista) {
    return `
        <section class="cuentas-tabla-panel tabla-grupo-panel" aria-labelledby="tituloTablaOperaciones">
            ${cabeceraTabla("Operaciones e integrantes", lista.length, "Selecciona una operacion para revisar al integrante y su informacion disponible.")}
            <div class="cuentas-tabla-scroll"><table class="cuentas-tabla cuentas-tabla-grupo">
                <thead><tr><th scope="col">Estado</th><th scope="col">Operacion</th><th scope="col">Cliente</th><th scope="col">Cartera / condicion</th><th scope="col">Producto</th><th scope="col" class="numero">Deuda</th><th scope="col" class="numero">Capital</th><th scope="col" class="numero">Mora</th><th scope="col">Accion</th></tr></thead>
                <tbody>${lista.map((cuenta, index) => renderFilaGrupo(cuenta, index)).join("")}</tbody>
            </table></div>
        </section>
    `;
}

function renderFilaGrupo(cuenta, index) {
    const tramo = getTramo(cuenta);
    const seleccionada = index === 0;
    const operacion = operacionDe(cuenta);
    return `
        <tr class="cuenta-fila ${getEstadoClass(cuenta)}${seleccionada ? " is-selected" : ""}" data-cuenta-index="${index}">
            <td data-label="Estado"><span class="badge ${tramo.class}" title="${h(tramo.descripcion)}">${h(tramo.label)}</span></td>
            <td data-label="Operacion"><button class="cuenta-operacion" type="button" data-seleccionar-operacion="${index}" aria-current="${seleccionada}"><strong>${h(operacion)}</strong><span aria-hidden="true">›</span></button></td>
            <td data-label="Cliente"><strong class="cuenta-cliente">${h(valorCampo(cuenta, ["NomCliente", "NOMCLIENTE", "NombreCliente"]))}</strong><span class="cuenta-secundario">DNI ${h(cuenta.DNI)}</span></td>
            <td data-label="Cartera / condicion">${h(carteraOCondicion(cuenta))}</td>
            <td data-label="Producto"><strong class="cuenta-producto">${h(valorCampo(cuenta, ["Producto", "PRODUCTO"]))}</strong><span class="cuenta-secundario">${h(valorCampo(cuenta, ["Linea_Negocio", "LineaNegocio", "LINEA_NEGOCIO"]))}</span></td>
            <td data-label="Deuda" class="numero">${h(money(cuenta.Deuda_Total))}</td><td data-label="Capital" class="numero">${h(money(cuenta.SdoCapital))}</td><td data-label="Mora" class="numero">${h(formatNumeroUnidad(cuenta.DiasAtraso, "dias"))}</td>
            <td data-label="Accion" class="cuenta-accion-celda"><button class="cuenta-ver-detalle" type="button" data-seleccionar-operacion="${index}" aria-current="${seleccionada}">Ver detalle</button></td>
        </tr>
    `;
}

function renderDetalleGrupo(cuenta) {
    const operacion = operacionDe(cuenta);
    const datos = [
        ["Cliente", valorCampo(cuenta, ["NomCliente", "NOMCLIENTE", "NombreCliente"])], ["DNI", valorCampo(cuenta, ["DNI"])],
        ["Oficina", valorCampo(cuenta, ["NomOficina", "NOMOFICINA"])], ["Condicion", valorCampo(cuenta, ["Condicion", "CONDICION"])],
        ["Producto", valorCampo(cuenta, ["Producto", "PRODUCTO"])], ["Linea", valorCampo(cuenta, ["Linea_Negocio", "LineaNegocio", "LINEA_NEGOCIO"])],
        ["Deuda total", money(cuenta.Deuda_Total)], ["Capital", money(cuenta.SdoCapital)], ["Capital vencido", money(cuenta.SdoCapitalVencido)],
        ["Dias atraso", formatNumeroUnidad(cuenta.DiasAtraso, "dias")], ["Ultimo pago", formatFecha(cuenta.FecUltPago)],
        ["Calificacion", valorCampo(cuenta, ["Calificacion", "CALIFICACION", "calificacion"])]
    ];
    return `<section class="detalle-operacion-panel detalle-operacion-grupo" aria-labelledby="tituloDetalleOperacion" data-detalle-operacion="${h(operacion)}">
        <header class="detalle-operacion-header"><div><span class="section-kicker">Integrante seleccionado</span><h3 id="tituloDetalleOperacion">Detalle de operacion grupal</h3><p>${h(operacion)}</p></div><span class="detalle-operacion-indicador">Seleccionada</span></header>
        <div class="detalle-operacion-grid">${datos.map(([label, value]) => detalleDato(label, value)).join("")}</div>
    </section>`;
}

function seleccionarOperacion(index, trigger) {
    const cuenta = window._clientes?.[Number(index)];
    const host = document.getElementById("detalleOperacionSeleccionada");
    if (!cuenta || !host) return;
    window._indiceOperacionSeleccionada = Number(index);
    actualizarSeleccionTabla(Number(index));
    host.classList.remove("is-visible");
    host.innerHTML = window._modoConsulta === "grupo" ? renderDetalleGrupo(cuenta) : renderDetalleIndividual(cuenta);
    requestAnimationFrame(() => host.classList.add("is-visible"));
    const rect = host.getBoundingClientRect();
    if (rect.top < 0 || rect.top > window.innerHeight * .82) {
        const reducirMovimiento = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
        host.scrollIntoView({ behavior: reducirMovimiento ? "auto" : "smooth", block: "start" });
    }
    trigger?.setAttribute("aria-current", "true");
}

function actualizarSeleccionTabla(index) {
    document.querySelectorAll(".cuenta-fila[data-cuenta-index]").forEach(fila => {
        const seleccionada = Number(fila.dataset.cuentaIndex) === index;
        fila.classList.toggle("is-selected", seleccionada);
        fila.querySelectorAll("[data-seleccionar-operacion]").forEach(control => control.setAttribute("aria-current", String(seleccionada)));
    });
}

function limpiarBusqueda() {
    window._clientes = [];
    window._modoConsulta = null;
    window._indiceOperacionSeleccionada = null;
    const valor = document.getElementById("valor");
    const loader = document.getElementById("loader");
    const resultado = document.getElementById("resultado");
    if (valor) { valor.value = ""; valor.focus(); }
    if (loader) loader.style.display = "none";
    if (resultado) resultado.innerHTML = `<div class="clientes-empty"><strong>Realiza una busqueda para empezar.</strong><span>Los resultados apareceran aqui con la ultima informacion diaria enviada por Compartamos para clientes activos.</span></div>`;
}

function cabeceraTabla(titulo, cantidad, ayuda) {
    return `<header class="cuentas-tabla-cabecera"><div><span class="section-kicker">Detalle financiero</span><h3 id="tituloTablaOperaciones">${h(titulo)} (${h(cantidad)})</h3><p>${h(ayuda)}</p></div></header>`;
}

function datoCabecera(label, value) { return `<div><span>${h(label)}</span><strong>${h(value)}</strong></div>`; }
function detalleDato(label, value) { return `<div class="cuenta-detalle-item"><span>${h(label)}</span><strong>${h(value)}</strong></div>`; }

function telefonosTextoCliente(lista) {
    const telefonos = [];
    lista.forEach(cliente => [cliente?.Telef_01, cliente?.Telef_02, cliente?.Telef_03, cliente?.Telef_04]
        .filter(tieneValor).map(valor => String(valor).trim()).filter(valor => valor !== "0").forEach(valor => telefonos.push(valor)));
    const unicos = [...new Set(telefonos)];
    return unicos.length ? unicos.join(" · ") : "—";
}

function contarIntegrantes(lista) {
    const unicos = new Set();
    lista.forEach((item, index) => {
        const clave = primerValorReal(item, ["DNI", "codcliente", "CodCliente", "NomCliente"]);
        unicos.add(tieneValor(clave) ? String(clave).trim() : `fila-${index}`);
    });
    return unicos.size;
}

function campoClienteReal(lista, campos) {
    for (const item of lista) {
        const value = primerValorReal(item, campos);
        if (tieneValor(value)) return value;
    }
    return null;
}

function campoCliente(lista, campos) { return campoClienteReal(lista, campos) ?? "—"; }
function operacionDe(cuenta) { return valorCampo(cuenta, ["CodOperacion", "Cod Operacion", "Operacion"]); }
function montoCuotaDe(cuenta) { return primerValorReal(cuenta, ["MTOCUOTA", "MtoCuota", "mto_cuota", "Mto_Cuota", "MontoCuota"]); }
function ultimaCuotaAtrasadaDe(cuenta) { return valorCampo(cuenta, ["ULT_CUOTAATRASADA", "Ult_CuotaAtrasada", "ult_cuotaatrasada", "UltCuotaAtrasada"]); }

function obtenerCuotasVisuales(cuenta) {
    return [
        sumarCamposCompletos(cuenta, ["CT1", "CT11", "CT12", "CT13", "CT14", "CT15"]),
        sumarCamposCompletos(cuenta, ["CT2", "CT21", "CT22", "CT23", "CT24", "CT25"]),
        sumarCamposCompletos(cuenta, ["CT3", "CT31", "CT32", "CT33", "CT34", "CT35"])
    ];
}

function sumarCamposCompletos(item, campos) {
    const valores = campos.map(campo => numeroValido(item?.[campo]));
    if (valores.some(valor => valor === null)) return null;
    return valores.reduce((total, valor) => total + valor, 0);
}

function sumarValores(lista, campo) {
    const valores = lista.map(item => numeroValido(item?.[campo])).filter(valor => valor !== null);
    if (!valores.length) return null;
    return valores.reduce((total, valor) => total + valor, 0);
}

function maximoValido(valores) {
    const validos = valores.map(numeroValido).filter(valor => valor !== null);
    return validos.length ? Math.max(...validos) : null;
}

function maxFechaValida(valores) {
    const validas = valores.filter(tieneValor).map(valor => ({ valor, tiempo: fechaComparable(valor) })).filter(item => item.tiempo !== null);
    if (!validas.length) return null;
    return validas.reduce((maximo, actual) => actual.tiempo > maximo.tiempo ? actual : maximo).valor;
}

function fechaComparable(value) {
    const texto = String(value).trim();
    let year; let month; let day;
    if (/^\d{8}$/.test(texto)) { year = texto.slice(0, 4); month = texto.slice(4, 6); day = texto.slice(6, 8); }
    else if (/^\d{4}-\d{2}-\d{2}/.test(texto)) [year, month, day] = texto.slice(0, 10).split("-");
    else if (/^\d{2}\/\d{2}\/\d{4}$/.test(texto)) [day, month, year] = texto.split("/");
    else return null;
    const tiempo = Date.UTC(Number(year), Number(month) - 1, Number(day));
    if (!Number.isFinite(tiempo)) return null;
    const fecha = new Date(tiempo);
    if (fecha.getUTCFullYear() !== Number(year) || fecha.getUTCMonth() !== Number(month) - 1 || fecha.getUTCDate() !== Number(day)) return null;
    return tiempo;
}

function carteraOCondicion(cuenta) {
    const cartera = primerValorReal(cuenta, ["Cartera", "CARTERA", "NombreCartera", "NOMBRE_CARTERA"]);
    const idCartera = numeroValido(primerValorReal(cuenta, ["IDCARTERA", "idcartera", "IdCartera"]) ?? cartera);
    const nombres = { 124: "Castigo individual", 126: "Vigente individual", 128: "Vigente CCM", 133: "Vigente grupal / CSM", 144: "Castigo grupal" };
    if (idCartera !== null && nombres[idCartera]) return nombres[idCartera];
    if (tieneValor(cartera)) return cartera;
    return valorCampo(cuenta, ["Condicion", "CONDICION"]);
}

function getTramo(cuenta) {
    const dias = numeroValido(cuenta?.DiasAtraso);
    const condicion = String(primerValorReal(cuenta || {}, ["Condicion", "CONDICION"]) || "").trim().toUpperCase();
    const idCartera = numeroValido(primerValorReal(cuenta || {}, ["IDCARTERA", "idcartera", "IdCartera"]));
    if (condicion.includes("JUDICIAL")) return { label: "JUDICIAL", class: "tramo-castigado", descripcion: "Operacion judicial" };
    if (condicion.includes("CASTIG") || [124, 144].includes(idCartera)) return { label: "CASTIGADO", class: "tramo-castigado", descripcion: "Operacion castigada" };
    if (dias === null) return { label: "SIN DATO", class: "tramo-sin-dato", descripcion: "Dias de atraso no disponibles" };
    if (dias <= 8) return { label: "NORMAL", class: "tramo-normal", descripcion: "0 a 8 dias de atraso" };
    if (dias <= 30) return { label: "CPP", class: "tramo-cpp", descripcion: "9 a 30 dias de atraso" };
    if (dias <= 60) return { label: "DEFICIENTE", class: "tramo-deficiente", descripcion: "31 a 60 dias de atraso" };
    if (dias <= 90) return { label: "DUDOSO 1", class: "tramo-dudoso", descripcion: "61 a 90 dias de atraso" };
    if (dias <= 120) return { label: "DUDOSO 2", class: "tramo-dudoso", descripcion: "91 a 120 dias de atraso" };
    return { label: "PERDIDA", class: "tramo-perdida", descripcion: "Mas de 120 dias de atraso" };
}

function getEstadoClass(cuenta) {
    const tramo = getTramo(cuenta).label;
    if (tramo === "CASTIGADO" || tramo === "JUDICIAL") return "estado-negro";
    if (tramo === "PERDIDA" || tramo.includes("DUDOSO")) return "estado-rojo";
    if (tramo === "DEFICIENTE") return "estado-naranja";
    if (tramo === "CPP") return "estado-amarillo";
    if (tramo === "SIN DATO") return "estado-neutro";
    return "estado-verde";
}

function numeroValido(value) {
    if (!tieneValor(value)) return null;
    const normalizado = typeof value === "string" ? value.replace(/,/g, "").trim() : value;
    const numero = Number(normalizado);
    return Number.isFinite(numero) ? numero : null;
}

function tieneValor(value) { return value !== undefined && value !== null && String(value).trim() !== ""; }
function primerValorReal(item, campos) { for (const campo of campos) if (tieneValor(item?.[campo])) return item[campo]; return null; }
function valorCampo(item, campos) { return primerValorReal(item, campos) ?? "—"; }

function formatFecha(fecha) {
    if (!tieneValor(fecha)) return "—";
    const str = String(fecha).trim();
    if (/^\d{8}$/.test(str)) return `${str.substring(6, 8)}/${str.substring(4, 6)}/${str.substring(0, 4)}`;
    if (/^\d{4}-\d{2}-\d{2}/.test(str)) { const [year, month, day] = str.substring(0, 10).split("-"); return `${day}/${month}/${year}`; }
    return str;
}

function format(value) { const numero = numeroValido(value); return numero === null ? "—" : new Intl.NumberFormat("es-PE").format(numero); }
function formatNumero(value) { return format(value); }
function formatNumeroUnidad(value, unidad) { const numero = numeroValido(value); return numero === null ? "—" : `${format(numero)} ${unidad}`; }
function money(value) { const numero = numeroValido(value); return numero === null ? "—" : `S/ ${new Intl.NumberFormat("es-PE", { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(numero)}`; }
function safe(value) { return tieneValor(value) ? value : "—"; }
function h(value) { return String(safe(value)).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;"); }
function initials(name) { const parts = String(tieneValor(name) ? name : "Cliente").trim().split(/\s+/).filter(Boolean).slice(0, 2); return parts.map(part => part[0]).join("").toUpperCase() || "CL"; }
function kpi(label, value) { return `<div class="kpi"><span>${h(label)}</span><b>${h(value)}</b></div>`; }

function configurarConsultaCompartamos() {
    const resultado = document.getElementById("resultado");
    if (!resultado) return;
    resultado.addEventListener("click", event => {
        const trigger = event.target.closest("[data-seleccionar-operacion]");
        if (trigger) { event.stopPropagation(); seleccionarOperacion(trigger.dataset.seleccionarOperacion, trigger); return; }
        const fila = event.target.closest("[data-cuenta-index]");
        if (fila && !event.target.closest("a, button, input, select, textarea")) seleccionarOperacion(fila.dataset.cuentaIndex, fila.querySelector("[data-seleccionar-operacion]"));
    });
}

window.addEventListener("DOMContentLoaded", configurarConsultaCompartamos);
