function renderCliente(payload) {
    if (!payload || !Array.isArray(payload.operaciones) || payload.operaciones.length === 0) {
        mostrarMensajeCliente("No se encontraron clientes u operaciones con ese dato.", "empty");
        return;
    }

    const resultado = document.getElementById("resultado");
    if (!resultado) return;

    window._consultaCompartamosCRM = payload;
    window._clientes = payload.operaciones;
    window._modoConsulta = payload.tipo_resultado;
    window._indiceOperacionSeleccionada = 0;

    resultado.innerHTML = `
        ${renderRegresoContextual()}
        ${payload.tipo_resultado === "GRUPO" ? renderCRMGrupo(payload) : renderCRMCliente(payload)}
        ${renderAdvertenciasFuentes(payload)}
    `;
}

function renderCRMCliente(data) {
    const operacion = data.operaciones[0];
    return `
        ${renderCabeceraClienteCRM(data)}
        ${renderKpisClienteCRM(data)}
        <div class="crm-operativo-grid">
            ${renderAlternativasCobro(data.operaciones)}
            ${renderGestionCRM(data)}
            ${renderPagosPdpCRM(data)}
            ${renderContactoCRM(data.contacto)}
            ${renderContencionCRM(data.contencion)}
            ${renderContextoGrupoCRM(data.grupo)}
        </div>
        ${renderTablaOperacionesCRM(data.operaciones)}
        <div id="detalleOperacionSeleccionada" class="detalle-operacion-host is-visible" aria-live="polite">
            ${renderDetalleOperacionCRM(operacion)}
        </div>
        ${renderMasInformacionCRM(data.informacion_adicional)}
    `;
}

function renderCabeceraClienteCRM(data) {
    const cliente = data.cliente || {};
    const situacion = data.situacion || {};
    const metadatos = [
        ["DNI", cliente.dni],
        ["Código cliente", cliente.codigo_cliente],
        ["Edad", tieneValor(cliente.edad) ? `${format(cliente.edad)} años` : null],
        ["Sexo", cliente.sexo],
        ["Oficina", cliente.oficina],
        ["Territorio", cliente.territorio],
        ["Segmento", cliente.segmento],
        ["Línea", cliente.linea_negocio],
        ["Producto principal", cliente.producto_principal]
    ].filter(([, value]) => tieneValor(value));
    return `
        <section class="crm-entidad-header crm-cliente-header" aria-labelledby="tituloClienteCRM">
            <div class="crm-entidad-principal">
                <div class="avatar avatar-entidad" aria-hidden="true">${initials(cliente.nombre)}</div>
                <div>
                    <span class="section-kicker">CLIENTE INDIVIDUAL</span>
                    <h2 id="tituloClienteCRM">${h(cliente.nombre)}</h2>
                    <div class="crm-identidad-linea">${metadatos.map(([label, value]) => `<span><b>${h(label)}</b>${h(value)}</span>`).join("")}</div>
                </div>
            </div>
            <div class="crm-estado-destacado" aria-label="Estado contractual de asignacion">
                ${estadoDestacado("Calificación", cliente.calificacion)}
                ${estadoDestacado("Condición", cliente.condicion)}
                ${estadoDestacado("Mora máxima", tieneValor(situacion.mora_maxima) ? `${format(situacion.mora_maxima)} días` : null)}
            </div>
        </section>
    `;
}

function renderKpisClienteCRM(data) {
    const situacion = data.situacion || {};
    return `<section class="cliente-kpis-consolidados crm-kpis-cliente" aria-label="Situacion consolidada del cliente">
        ${kpi("Operaciones", format(situacion.cantidad_operaciones))}
        ${kpi("Deuda total", money(situacion.deuda_actual))}
        ${kpi("Capital", money(situacion.capital))}
        ${kpi("Capital vencido", money(situacion.capital_vencido))}
        ${kpi("Desembolso", money(situacion.monto_desembolso))}
        ${kpi("Mora máxima", tieneValor(situacion.mora_maxima) ? `${format(situacion.mora_maxima)} días` : null)}
        ${kpi("Último pago", formatFecha(situacion.ultimo_pago_asignacion))}
    </section>`;
}

function renderAlternativasCobro(operaciones) {
    const items = operaciones.filter(item => item.alternativas_cobro?.length);
    if (!items.length) return "";
    return `<section class="crm-operativo-card crm-alternativas-card crm-span-2" aria-labelledby="tituloAlternativasCRM">
        ${encabezadoBloque("Alternativas disponibles", "Qué puedo cobrar", "tituloAlternativasCRM")}
        <div class="crm-alternativas-lista">${items.map(item => `
            <div class="crm-alternativa-operacion">
                <strong>${h(item.operacion)}</strong>
                <div>${item.alternativas_cobro.map(alt => `<span><small>${h(alt.nombre)}</small><b>${money(alt.monto)}</b></span>`).join("")}</div>
            </div>`).join("")}
        </div>
        <p class="crm-card-note">Valores de asignación y cálculos CT visibles, sin recomendación automática.</p>
    </section>`;
}

function renderGestionCRM(data) {
    const gestion = data.gestion || {};
    if (!gestion.disponible) return "";
    const ultima = gestion.ultima_gestion || {};
    return `<section class="crm-operativo-card" aria-labelledby="tituloGestionCRM">
        ${encabezadoBloque("Actividad de cobranza", "Gestión", "tituloGestionCRM")}
        <div class="crm-mini-grid">
            ${miniDato("Gestionado hoy", gestion.gestionado_hoy ? "Sí" : "No")}
            ${miniDato("Gestiones del mes", gestion.gestionado_mes)}
            ${miniDato("Última gestión", fechaDato(ultima.fecha))}
            ${miniDato("Resultado", ultima.resultado)}
            ${miniDato("Contacto", ultima.contacto)}
            ${miniDato("Agente", ultima.agente)}
            ${miniDato("Canal", ultima.canal)}
        </div>
        ${gestion.historial?.length ? `<details class="crm-details"><summary>Ver historial</summary>${renderHistorialGestion(gestion.historial)}</details>` : ""}
    </section>`;
}

function renderPagosPdpCRM(data) {
    const pagos = data.pagos_pdp?.pagos || {};
    const pdp = data.pagos_pdp?.pdp || {};
    if (!pagos.disponible && !pdp.disponible) return "";
    return `<section class="crm-operativo-card" aria-labelledby="tituloPagosPdpCRM">
        ${encabezadoBloque("Fuente operativa", "Pagos y PDP", "tituloPagosPdpCRM")}
        <div class="crm-mini-grid">
            ${pagos.disponible && !pagos.tiene_datos ? miniDato("Pagos reales", "Sin registros") : ""}
            ${pdp.disponible && !pdp.tiene_datos ? miniDato("PDP", "Sin registros") : ""}
            ${pagos.disponible && pagos.tiene_datos ? miniDato("Último pago real", fechaDato(pagos.ultimo_pago_real)) : ""}
            ${pagos.disponible && pagos.tiene_datos ? miniDato("Monto último pago", moneyDato(pagos.monto_ultimo_pago)) : ""}
            ${pagos.disponible && pagos.tiene_datos ? miniDato("Pago acumulado mes", moneyDato(pagos.pago_acumulado_mes)) : ""}
            ${pdp.disponible && pdp.tiene_datos ? miniDato("PDP vigente", pdp.pdp_vigente ? "Sí" : "No") : ""}
            ${pdp.disponible && pdp.tiene_datos ? miniDato("Monto PDP", moneyDato(pdp.monto_pdp)) : ""}
            ${pdp.disponible && pdp.tiene_datos ? miniDato("Fecha compromiso", fechaDato(pdp.fecha_compromiso)) : ""}
            ${pdp.disponible && pdp.tiene_datos ? miniDato("Estado PDP", pdp.estado_pdp) : ""}
            ${pdp.disponible && pdp.tiene_datos ? miniDato("Agente PDP", pdp.agente_pdp) : ""}
        </div>
    </section>`;
}

function renderContactoCRM(contacto = {}) {
    const telefonos = [contacto.telefono_principal, ...(contacto.telefonos_adicionales || [])].filter(tieneValor);
    if (!telefonos.length && !tieneValor(contacto.direccion_principal) && !tieneValor(contacto.distrito)) return "";
    return `<section class="crm-operativo-card" aria-labelledby="tituloContactoCRM">
        ${encabezadoBloque("Datos operativos", "Contacto", "tituloContactoCRM")}
        ${telefonos.length ? `<div class="crm-telefonos">${telefonos.map((telefono, index) => `<span><small>${index ? "Adicional" : "Principal"}</small><b>${h(telefono)}</b><a href="tel:${attr(telefono)}">Llamar</a></span>`).join("")}</div>` : ""}
        <div class="crm-mini-grid">
            ${miniDato("Dirección principal", contacto.direccion_principal)}
            ${miniDato("Distrito", contacto.distrito)}
            ${miniDato("Dirección vivienda", contacto.direccion_vivienda)}
            ${miniDato("Dirección negocio", contacto.direccion_negocio)}
        </div>
    </section>`;
}

function renderContencionCRM(contencion = {}) {
    if (!contencion.disponible) return "";
    return `<section class="crm-operativo-card crm-contencion-card" aria-labelledby="tituloContencionCRM">
        ${encabezadoBloque("Impacto operativo", "Contención", "tituloContencionCRM")}
        <div class="crm-mini-grid">
            ${miniDato("Capital evaluado", moneyDato(contencion.capital_evaluado))}
            ${miniDato("Monto requerido", moneyDato(contencion.monto_requerido))}
            ${miniDato("Capital contenido por pago", moneyDato(contencion.capital_contenido_pago))}
            ${miniDato("Capital contenido por PDP", moneyDato(contencion.capital_contenido_pdp))}
            ${miniDato("Cumple pago", booleanoTexto(contencion.cumple_pago))}
            ${miniDato("Cumple PDP", booleanoTexto(contencion.cumple_pdp))}
            ${miniDato("Operación contenedora", contencion.operacion_contenedora)}
            ${miniDato("Cliente contenedor", booleanoTexto(contencion.cliente_contenedor))}
        </div>
    </section>`;
}

function renderContextoGrupoCRM(grupo = {}) {
    if (!grupo.disponible) return "";
    const buscar = grupo.codigo_grupo || grupo.credito_grupal;
    return `<section class="crm-operativo-card crm-grupo-contexto" aria-labelledby="tituloContextoGrupoCRM">
        ${encabezadoBloque("Vínculo contractual", "Contexto grupal", "tituloContextoGrupoCRM")}
        <div class="crm-mini-grid">
            ${miniDato("Nombre grupo", grupo.nombre)}
            ${miniDato("Código grupo", grupo.codigo_grupo)}
            ${miniDato("Crédito grupal", grupo.credito_grupal)}
            ${miniDato("Oficina", grupo.oficina)}
        </div>
        ${buscar ? `<button class="crm-link-button" type="button" data-buscar-entidad="${attr(buscar)}">Ver grupo</button>` : ""}
    </section>`;
}

function renderTablaOperacionesCRM(operaciones) {
    return `<section class="cuentas-tabla-panel crm-operaciones-panel" aria-labelledby="tituloTablaOperaciones">
        ${cabeceraTabla("Operaciones del cliente", operaciones.length, "Selecciona una operación para revisar su detalle contractual y alternativas.", "tituloTablaOperaciones")}
        <div class="cuentas-tabla-scroll"><table class="cuentas-tabla cuentas-tabla-individual crm-tabla-operaciones">
            <thead><tr><th>Operación</th><th>Producto</th><th>Estado</th><th class="numero">Mora</th><th class="numero">Capital</th><th>Qué cobrar</th><th>Contención</th><th>Acción</th></tr></thead>
            <tbody>${operaciones.map((item, index) => renderFilaOperacionCRM(item, index)).join("")}</tbody>
        </table></div>
    </section>`;
}

function renderFilaOperacionCRM(item, index) {
    const seleccionada = index === 0;
    const alternativas = item.alternativas_cobro || [];
    return `<tr class="cuenta-fila${seleccionada ? " is-selected" : ""}" data-cuenta-index="${index}">
        <td data-label="Operación"><button class="cuenta-operacion" type="button" data-seleccionar-operacion="${index}" aria-current="${seleccionada}"><strong>${h(item.operacion)}</strong><span aria-hidden="true">›</span></button></td>
        <td data-label="Producto"><strong>${h(item.producto)}</strong><span class="cuenta-secundario">${h(item.linea_negocio)}</span></td>
        <td data-label="Estado">${h(item.condicion || item.calificacion)}</td>
        <td data-label="Mora" class="numero">${tieneValor(item.dias_atraso) ? `${format(item.dias_atraso)} días` : "—"}</td>
        <td data-label="Capital" class="numero">${money(item.capital)}</td>
        <td data-label="Qué cobrar">${alternativas.length ? `<span class="crm-count-pill">${alternativas.length} alternativa${alternativas.length === 1 ? "" : "s"}</span>` : "—"}</td>
        <td data-label="Contención">${item.contencion?.disponible ? "Disponible" : "—"}</td>
        <td data-label="Acción" class="cuenta-accion-celda"><button class="cuenta-ver-detalle" type="button" data-seleccionar-operacion="${index}" aria-current="${seleccionada}">Ver detalle</button></td>
    </tr>`;
}

function renderDetalleOperacionCRM(item = {}) {
    const contrato = itemsDisponibles([
        ["Producto", item.producto], ["Línea", item.linea_negocio], ["Oficina", item.oficina],
        ["Territorio", item.territorio], ["Segmento", item.segmento], ["Condición", item.condicion],
        ["Calificación", item.calificacion], ["Score", item.score], ["Tramo", item.tramo]
    ]);
    const credito = itemsDisponibles([
        ["Desembolso", moneyDato(item.monto_desembolso)], ["Fecha desembolso", fechaDato(item.fecha_desembolso)],
        ["Cuotas aprobadas", item.cuotas_aprobadas], ["Cuotas atrasadas", item.cuotas_atrasadas],
        ["Cuotas vencidas", item.cuotas_vencidas], ["Última atrasada", item.ultima_cuota_atrasada],
        ["Monto cuota", moneyDato(item.monto_cuota)]
    ]);
    const saldos = itemsDisponibles([
        ["Deuda", moneyDato(item.deuda_total)], ["Capital", moneyDato(item.capital)],
        ["Capital vencido", moneyDato(item.capital_vencido)], ["Mora", tieneValor(item.dias_atraso) ? `${format(item.dias_atraso)} días` : null],
        ["Último pago asignación", fechaDato(item.fecha_ultimo_pago_asignacion)], ["Último vencimiento", fechaDato(item.ultimo_vencimiento)],
        ["Fecha castigo", fechaDato(item.fecha_castigo)]
    ]);
    const cuotas = Object.entries(item.cuotas_calculadas || {}).filter(([, value]) => value?.disponible).map(([key, value]) => [key.replace("cuota_", "Cuota "), money(value.valor)]);
    return `<section class="detalle-operacion-panel crm-detalle-operacion" aria-labelledby="tituloDetalleOperacion">
        <header class="detalle-operacion-header"><div><span class="section-kicker">Operación seleccionada</span><h3 id="tituloDetalleOperacion">Detalle de operación seleccionada</h3><p>${h(item.operacion)}</p></div><span class="detalle-operacion-indicador">Activa</span></header>
        ${renderGrupoDetalle("Situación contractual", contrato)}
        ${renderGrupoDetalle("Crédito y cuotas", credito)}
        ${cuotas.length ? renderGrupoDetalle("Cuotas calculadas", cuotas, "Cálculo visual: cada componente NULL se considera cero.") : ""}
        ${renderGrupoDetalle("Saldos y fechas", saldos)}
        ${item.alternativas_cobro?.length ? `<div class="crm-detalle-alternativas"><span class="section-kicker">Alternativas existentes</span>${item.alternativas_cobro.map(alt => `<span><b>${h(alt.nombre)}</b>${money(alt.monto)}</span>`).join("")}</div>` : ""}
    </section>`;
}

function renderMasInformacionCRM(informacion = {}) {
    const items = Object.entries(informacion).filter(([, value]) => tieneValor(value));
    if (!items.length) return "";
    const labels = { fecha_nacimiento: "Fecha nacimiento", edad: "Edad", sexo: "Sexo", actividad_economica: "Actividad económica", rubro: "Rubro", vivienda: "Vivienda", direccion_negocio: "Dirección negocio", conyuge: "Cónyuge", avales: "Avales", rcc: "RCC", score: "Score", fecha_carga: "Fecha carga", mes_asignacion: "Mes asignación" };
    return `<details class="crm-mas-informacion"><summary>Más información</summary><div class="detalle-operacion-grid">${items.map(([key, value]) => detalleDato(labels[key] || key, key.includes("fecha") ? formatFecha(value) : value)).join("")}</div></details>`;
}

function renderCRMGrupo(data) {
    const grupo = data.grupo || {};
    const situacion = data.situacion || {};
    const integrantes = data.integrantes || [];
    const gestionDisponible = data.gestion?.disponible === true;
    const gestionados = gestionDisponible ? integrantes.filter(item => item.gestion?.gestionado_mes).length : null;
    const sinGestion = gestionDisponible ? integrantes.length - gestionados : null;
    const cuotasVencidas = integrantes.map(item => numeroValido(item.cuotas_vencidas)).filter(value => value !== null);
    const maxCuotasVencidas = cuotasVencidas.length ? Math.max(...cuotasVencidas) : null;
    return `
        <section class="crm-entidad-header crm-grupo-header" aria-labelledby="tituloGrupoCRM">
            <div class="crm-entidad-principal"><div class="avatar avatar-entidad" aria-hidden="true">${initials(grupo.nombre || grupo.codigo_grupo)}</div><div><span class="section-kicker">CRM Grupo</span><h2 id="tituloGrupoCRM">${h(grupo.nombre || "Grupo Compartamos")}</h2><div class="crm-identidad-linea">${datoLinea("Código grupo", grupo.codigo_grupo)}${datoLinea("Crédito grupal", grupo.credito_grupal)}${datoLinea("Oficina", grupo.oficina)}${datoLinea("Territorio", grupo.territorio)}${datoLinea("Producto", grupo.producto)}</div></div></div>
        </section>
        <section class="cliente-kpis-consolidados grupo-kpis-consolidados" aria-label="Situacion grupal">
            ${kpi("Integrantes", integrantes.length)}${kpi("Deuda total", money(situacion.deuda_actual))}${kpi("Capital", money(situacion.capital))}${kpi("Capital vencido", money(situacion.capital_vencido))}${kpi("Mora máxima", tieneValor(situacion.mora_maxima) ? `${format(situacion.mora_maxima)} días` : null)}${kpi("Cuotas vencidas máx.", format(maxCuotasVencidas))}${gestionDisponible ? kpi("Gestionados", gestionados) + kpi("Sin gestión", sinGestion) : ""}
        </section>
        <section class="crm-insight-grupo"><span class="section-kicker">Insight del grupo</span><p>${integrantes.length} integrante${integrantes.length === 1 ? "" : "s"} y ${data.operaciones.length} ${data.operaciones.length === 1 ? "operación" : "operaciones"} identificadas. ${!gestionDisponible ? "La gestión por integrante no está conectada." : gestionados ? `${gestionados} con gestión registrada en el mes.` : "No se registran gestiones en el mes."}</p></section>
        ${renderTablaIntegrantesCRM(integrantes, gestionDisponible)}
        ${renderContencionCRM(data.contencion)}
        <div class="crm-operativo-grid">${renderGestionCRM(data)}${renderPagosPdpCRM(data)}${renderCampanasGrupoCRM(data.campanas)}</div>
    `;
}

function renderTablaIntegrantesCRM(integrantes, gestionDisponible) {
    return `<section class="cuentas-tabla-panel crm-integrantes-panel" aria-labelledby="tituloIntegrantesCRM">${cabeceraTabla("Integrantes", integrantes.length, "Abre el CRM del cliente sin perder el contexto del grupo.", "tituloIntegrantesCRM")}
        <div class="cuentas-tabla-scroll"><table class="cuentas-tabla crm-tabla-integrantes"><thead><tr><th>Integrante</th><th>DNI</th><th>Rol</th><th>Operación</th><th class="numero">Deuda</th><th class="numero">Capital</th><th class="numero">Mora</th><th>Cuotas vencidas</th><th>Último pago</th><th>Gestión</th><th>Calificación</th><th>Contención</th><th>Acción</th></tr></thead><tbody>
            ${integrantes.map(item => `<tr class="cuenta-fila"><td data-label="Integrante"><strong>${h(item.nombre)}</strong></td><td data-label="DNI">${h(item.dni)}</td><td data-label="Rol">${h(item.rol)}</td><td data-label="Operación">${h(item.operaciones?.[0]?.operacion)}</td><td data-label="Deuda" class="numero">${money(item.deuda)}</td><td data-label="Capital" class="numero">${money(item.capital)}</td><td data-label="Mora" class="numero">${tieneValor(item.mora) ? `${format(item.mora)} días` : "—"}</td><td data-label="Cuotas vencidas">${h(item.cuotas_vencidas)}</td><td data-label="Último pago">${formatFecha(item.ultimo_pago_asignacion)}</td><td data-label="Gestión">${gestionDisponible ? item.gestion?.gestionado_mes ? "Gestionado" : "Sin gestión" : "No conectado"}</td><td data-label="Calificación">${h(item.calificacion)}</td><td data-label="Contención">${item.contencion?.disponible ? "Disponible" : "—"}</td><td data-label="Acción"><button class="cuenta-ver-detalle" type="button" data-buscar-entidad="${attr(item.dni || item.codigo_cliente)}">Ver cliente</button></td></tr>`).join("")}
        </tbody></table></div></section>`;
}

function renderCampanasGrupoCRM(campanas = {}) {
    if (!campanas.disponible) return "";
    return `<section class="crm-operativo-card"><span class="section-kicker">Solo lectura</span><h3>Campañas y excepciones</h3><p class="crm-card-note">Valores entregados por la asignación. No se generan propuestas automáticas.</p></section>`;
}

function seleccionarOperacion(index) {
    const data = window._consultaCompartamosCRM;
    const item = data?.operaciones?.[Number(index)];
    const host = document.getElementById("detalleOperacionSeleccionada");
    if (!item || !host) return;
    window._indiceOperacionSeleccionada = Number(index);
    actualizarSeleccionTabla(Number(index));
    host.classList.remove("is-visible");
    host.innerHTML = renderDetalleOperacionCRM(item);
    requestAnimationFrame(() => host.classList.add("is-visible"));
    const rect = host.getBoundingClientRect();
    if (rect.top < 0 || rect.top > window.innerHeight * .82) host.scrollIntoView({ behavior: reducirMovimiento() ? "auto" : "smooth", block: "start" });
}

function actualizarSeleccionTabla(index) {
    document.querySelectorAll(".cuenta-fila[data-cuenta-index]").forEach(fila => {
        const seleccionada = Number(fila.dataset.cuentaIndex) === index;
        fila.classList.toggle("is-selected", seleccionada);
        fila.querySelectorAll("[data-seleccionar-operacion]").forEach(control => control.setAttribute("aria-current", String(seleccionada)));
    });
}

function navegarEntidadCRM(valor) {
    if (!tieneValor(valor)) return;
    window._historialConsultaCompartamos = window._historialConsultaCompartamos || [];
    const actual = document.getElementById("valor")?.value?.trim();
    if (actual && actual !== valor) window._historialConsultaCompartamos.push(actual);
    const input = document.getElementById("valor");
    if (input) input.value = valor;
    buscar();
}

function volverEntidadCRM() {
    const historial = window._historialConsultaCompartamos || [];
    const valor = historial.pop();
    if (!valor) return;
    const input = document.getElementById("valor");
    if (input) input.value = valor;
    buscar();
}

function renderRegresoContextual() {
    const historial = window._historialConsultaCompartamos || [];
    return historial.length ? `<button class="crm-back-button" type="button" data-volver-entidad>← Volver a la consulta anterior</button>` : "";
}

function renderAdvertenciasFuentes(data) {
    const advertencias = data.advertencias || [];
    return advertencias.length ? `<aside class="crm-source-warning"><strong>Fuentes parcialmente disponibles</strong><span>${advertencias.map(h).join(" ")}</span></aside>` : "";
}

function renderHistorialGestion(items) {
    return `<div class="crm-historial">${items.map(item => `<div><time>${h(formatFecha(item.fecha))}${item.hora ? ` · ${h(item.hora)}` : ""}</time><strong>${h(item.resultado || item.gestion)}</strong><span>${h(item.agente)}${item.canal ? ` · ${h(item.canal)}` : ""}</span></div>`).join("")}</div>`;
}

function renderGrupoDetalle(titulo, items, nota = "") {
    if (!items.length) return "";
    return `<section class="crm-detalle-grupo"><header><h4>${h(titulo)}</h4>${nota ? `<small>${h(nota)}</small>` : ""}</header><div class="detalle-operacion-grid">${items.map(([label, value]) => detalleDato(label, value)).join("")}</div></section>`;
}

function itemsDisponibles(items) { return items.filter(([, value]) => tieneValor(value)); }
function moneyDato(value) { return tieneValor(value) ? money(value) : null; }
function fechaDato(value) { return tieneValor(value) ? formatFecha(value) : null; }

function encabezadoBloque(kicker, titulo, id) { return `<header class="crm-card-header"><span class="section-kicker">${h(kicker)}</span><h3 id="${attr(id)}">${h(titulo)}</h3></header>`; }
function miniDato(label, value) { return tieneValor(value) ? `<div><span>${h(label)}</span><strong>${h(value)}</strong></div>` : ""; }
function estadoDestacado(label, value) { return `<div><span>${h(label)}</span><strong>${h(value)}</strong></div>`; }
function datoLinea(label, value) { return tieneValor(value) ? `<span><b>${h(label)}</b>${h(value)}</span>` : ""; }
function detalleDato(label, value) { return `<div class="cuenta-detalle-item"><span>${h(label)}</span><strong>${h(value)}</strong></div>`; }
function booleanoTexto(value) { return value === true ? "Sí" : value === false ? "No" : null; }

function cabeceraTabla(titulo, cantidad, ayuda, id) {
    return `<header class="cuentas-tabla-cabecera"><div><span class="section-kicker">Vista operativa</span><h3 id="${attr(id)}">${h(titulo)} (${h(cantidad)})</h3><p>${h(ayuda)}</p></div></header>`;
}

function limpiarBusqueda() {
    window._consultaCompartamosCRM = null;
    window._clientes = [];
    window._modoConsulta = null;
    window._indiceOperacionSeleccionada = null;
    window._historialConsultaCompartamos = [];
    const valor = document.getElementById("valor");
    if (valor) { valor.value = ""; valor.focus(); }
    const loader = document.getElementById("loader");
    if (loader) loader.style.display = "none";
    const resultado = document.getElementById("resultado");
    if (resultado) resultado.innerHTML = `<div class="clientes-empty"><strong>Realiza una búsqueda para empezar.</strong><span>Los resultados aparecerán aquí con la información conectada de asignación y cobranza.</span></div>`;
}

function tieneValor(value) { return value !== undefined && value !== null && String(value).trim() !== ""; }
function numeroValido(value) { if (!tieneValor(value)) return null; const numero = Number(String(value).replace(/,/g, "")); return Number.isFinite(numero) ? numero : null; }
function format(value) { const numero = numeroValido(value); return numero === null ? "—" : new Intl.NumberFormat("es-PE").format(numero); }
function money(value) { const numero = numeroValido(value); return numero === null ? "—" : `S/ ${new Intl.NumberFormat("es-PE", { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(numero)}`; }
function formatFecha(value) { if (!tieneValor(value)) return "—"; const raw = String(value).trim(); if (/^\d{4}-\d{2}-\d{2}/.test(raw)) { const [year, month, day] = raw.slice(0, 10).split("-"); return `${day}/${month}/${year}`; } if (/^\d{8}$/.test(raw)) return `${raw.slice(6, 8)}/${raw.slice(4, 6)}/${raw.slice(0, 4)}`; return raw; }
function safe(value) { return tieneValor(value) ? value : "—"; }
function h(value) { return String(safe(value)).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;"); }
function attr(value) { return h(value); }
function initials(value) { const parts = String(tieneValor(value) ? value : "CRM").trim().split(/\s+/).filter(Boolean).slice(0, 2); return parts.map(part => part[0]).join("").toUpperCase() || "CR"; }
function kpi(label, value) { return `<div class="kpi"><span>${h(label)}</span><b>${h(value)}</b></div>`; }
function reducirMovimiento() { return window.matchMedia?.("(prefers-reduced-motion: reduce)").matches; }

function configurarConsultaCompartamos() {
    const resultado = document.getElementById("resultado");
    if (!resultado) return;
    resultado.addEventListener("click", event => {
        const selector = event.target.closest("[data-seleccionar-operacion]");
        if (selector) { seleccionarOperacion(selector.dataset.seleccionarOperacion); return; }
        const buscarEntidad = event.target.closest("[data-buscar-entidad]");
        if (buscarEntidad) { navegarEntidadCRM(buscarEntidad.dataset.buscarEntidad); return; }
        if (event.target.closest("[data-volver-entidad]")) { volverEntidadCRM(); return; }
        const fila = event.target.closest("[data-cuenta-index]");
        if (fila && !event.target.closest("a, button, input, select, textarea")) seleccionarOperacion(fila.dataset.cuentaIndex);
    });
}

window.addEventListener("DOMContentLoaded", configurarConsultaCompartamos);
