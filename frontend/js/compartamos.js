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
        ${renderAvisoOtraCartera(payload)}
        ${payload.tipo_resultado === "GRUPO" ? renderCRMGrupo(payload) : renderCRMCliente(payload)}
        ${renderAdvertenciasFuentes(payload)}
    `;
}

function renderAvisoOtraCartera(data) {
    const otras = Array.isArray(data?.otras_carteras_compartamos) ? data.otras_carteras_compartamos : [];
    if (!otras.length) return "";
    const nombres = otras.map(cartera => `${cartera.nombre} (${cartera.id})`).join(", ");
    return `<aside class="crm-other-portfolio"><strong>Consulta entre carteras Compartamos</strong><span>El resultado incluye carteras fuera de tu asignación: ${h(nombres)}. Puedes consultarlas desde Radar; tu asignación operativa no cambia.</span></aside>`;
}

function renderCRMClienteAnterior(data) {
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

// ---------------------------------------------------------------------------
// Vista de cliente ordenada por lo que se necesita al llamar (2026-10).
// Mismos datos que antes; lo secundario queda plegado. La anterior sigue en renderCRMClienteAnterior.
// ---------------------------------------------------------------------------
function renderCRMCliente(data) {
    const operacion = data.operaciones[0];
    return `
        ${renderCabeceraClienteV2(data)}
        ${renderSituacionClienteV2(data)}
        <div class="crm-v2-grid">
            ${renderAlternativasCobro(data.operaciones).replace("crm-span-2", "")}
            ${renderContactoCRM(data.contacto)}
        </div>
        <div class="crm-v2-grid">
            ${renderUltimaGestionV2(data.gestion)}
            ${renderCompromisosPagosV2(data.pagos_pdp)}
        </div>
        ${renderTablaOperacionesCRM(data.operaciones)}
        <details class="crm-v2-plegable" id="detalleOperacionWrap">
            <summary id="detalleOperacionResumen">Detalle de la operación ${h(operacion.operacion)}</summary>
            <div id="detalleOperacionSeleccionada" class="detalle-operacion-host is-visible" aria-live="polite">
                ${renderDetalleOperacionCRM(operacion)}
            </div>
        </details>
        ${renderMasDatosClienteV2(data)}
    `;
}

function renderCabeceraClienteV2(data) {
    const cliente = data.cliente || {};
    const grupo = data.grupo || {};
    const buscarGrupo = grupo.codigo_grupo || grupo.credito_grupal;
    const metadatos = [
        ["DNI", cliente.dni], ["Código cliente", cliente.codigo_cliente],
        ["Oficina", cliente.oficina], ["Producto", cliente.producto_principal]
    ].filter(([, value]) => tieneValor(value));
    return `
        <section class="crm-entidad-header crm-cliente-header" aria-labelledby="tituloClienteCRM">
            <div class="crm-entidad-principal">
                <div class="avatar avatar-entidad" aria-hidden="true">${initials(cliente.nombre)}</div>
                <div>
                    <div class="crm-titulo-linea"><h2 id="tituloClienteCRM">${h(cliente.nombre)}</h2><span class="crm-tipo">Cliente</span></div>
                    <div class="crm-identidad-linea">${metadatos.map(([label, value]) => `<span><b>${h(label)}</b>${h(value)}</span>`).join("")}</div>
                    ${grupo.disponible && tieneValor(grupo.nombre) ? `<div class="crm-v2-grupo"><span>Grupo</span><strong>${h(grupo.nombre)}</strong>${buscarGrupo ? `<button class="crm-link-button" type="button" data-buscar-entidad="${attr(buscarGrupo)}">Ver grupo</button>` : ""}</div>` : ""}
                </div>
            </div>
            <div class="crm-estado-destacado" aria-label="Estado contractual de asignacion">
                ${estadoCalificacionCRM(cliente)}
                ${estadoDestacado("Condición", cliente.condicion)}
            </div>
        </section>
    `;
}

function cifraV2(etiqueta, valor, sub, alerta = false) {
    return `<div class="crm-v2-cifra${alerta ? " is-alerta" : ""}"><span>${h(etiqueta)}</span><b>${h(valor)}</b>${tieneValor(sub) ? `<small>${h(sub)}</small>` : ""}</div>`;
}

function renderSituacionClienteV2(data) {
    const s = data.situacion || {};
    const ops = numeroValido(s.cantidad_operaciones);
    return `<section class="crm-v2-situacion" aria-label="Situación consolidada del cliente">
        ${cifraV2("Deuda total", money(s.deuda_actual), tieneValor(s.capital) ? `Capital ${money(s.capital)}` : null)}
        ${cifraV2("Capital vencido", money(s.capital_vencido), null, true)}
        ${cifraV2("Mora máxima", tieneValor(s.mora_maxima) ? `${format(s.mora_maxima)} días` : "—", ops !== null ? `Entre ${format(ops)} operación${ops === 1 ? "" : "es"}` : null, true)}
        ${cifraV2("Último pago", formatFecha(s.ultimo_pago_asignacion), "Según asignación")}
    </section>`;
}

function renderUltimaGestionV2(gestion = {}) {
    if (!gestion.disponible) return "";
    const u = gestion.ultima_gestion || {};
    const detalle = [["Contacto", u.contacto], ["Agente", u.agente], ["Canal", u.canal]].filter(([, v]) => tieneValor(v));
    return `<section class="crm-operativo-card crm-v2-card" aria-labelledby="tituloGestionCRM">
        ${encabezadoBloque("Actividad de cobranza", "Última gestión", "tituloGestionCRM")}
        ${tieneValor(u.fecha) || tieneValor(u.resultado) ? `
            <p class="crm-v2-principal"><b>${h(fechaDato(u.fecha))}</b>${tieneValor(u.resultado) ? ` · ${h(u.resultado)}` : ""}</p>
            <p class="crm-v2-linea">${detalle.map(([l, v]) => `<span>${h(l)} <b>${h(v)}</b></span>`).join("")}</p>`
            : `<p class="crm-v2-vacio">Sin gestiones registradas.</p>`}
        <p class="crm-v2-linea crm-v2-linea-suave"><span>Gestionado hoy <b>${gestion.gestionado_hoy ? "Sí" : "No"}</b></span><span>Gestiones del mes <b>${h(gestion.gestionado_mes ?? 0)}</b></span></p>
        ${gestion.historial?.length ? `<details class="crm-details"><summary>Ver historial</summary>${renderHistorialGestion(gestion.historial)}</details>` : ""}
    </section>`;
}

function renderCompromisosPagosV2(pagosPdp = {}) {
    const pagos = pagosPdp.pagos || {};
    const pdp = pagosPdp.pdp || {};
    if (!pagos.disponible && !pdp.disponible) return "";
    const bloquePdp = !pdp.disponible ? "" : pdp.tiene_datos ? `
        <p class="crm-v2-principal"><b>PDP ${pdp.pdp_vigente ? "vigente" : "no vigente"}</b>${tieneValor(pdp.monto_pdp) ? ` · ${h(money(pdp.monto_pdp))}` : ""}${tieneValor(pdp.fecha_compromiso) ? ` · para el ${h(formatFecha(pdp.fecha_compromiso))}` : ""}</p>
        <p class="crm-v2-linea">${[["Estado", pdp.estado_pdp], ["Agente", pdp.agente_pdp]].filter(([, v]) => tieneValor(v)).map(([l, v]) => `<span>${h(l)} <b>${h(v)}</b></span>`).join("")}</p>`
        : `<p class="crm-v2-vacio">Sin PDP registrado.</p>`;
    const bloquePagos = !pagos.disponible ? "" : pagos.tiene_datos ? `
        <p class="crm-v2-linea crm-v2-linea-suave"><span>Último pago real <b>${h(fechaDato(pagos.ultimo_pago_real))}${tieneValor(pagos.monto_ultimo_pago) ? ` · ${h(money(pagos.monto_ultimo_pago))}` : ""}</b></span><span>Acumulado del mes <b>${h(money(pagos.pago_acumulado_mes ?? 0))}</b></span></p>`
        : `<p class="crm-v2-linea crm-v2-linea-suave"><span>Pagos reales <b>Sin registros</b></span></p>`;
    return `<section class="crm-operativo-card crm-v2-card" aria-labelledby="tituloPagosPdpCRM">
        ${encabezadoBloque("Fuente operativa", "Compromiso y pagos", "tituloPagosPdpCRM")}
        ${bloquePdp}${bloquePagos}
    </section>`;
}

function renderMasDatosClienteV2(data) {
    const c = data.cliente || {};
    const s = data.situacion || {};
    const ident = itemsDisponibles([
        ["Edad", tieneValor(c.edad) ? `${format(c.edad)} años` : null], ["Sexo", c.sexo], ["Territorio", c.territorio],
        ["Segmento", c.segmento], ["Línea", c.linea_negocio], ["Desembolso total", moneyDato(s.monto_desembolso)]
    ]);
    const contencion = renderContencionCRM(data.contencion);
    const grupo = renderContextoGrupoCRM(data.grupo);
    const mas = renderMasInformacionCRM(data.informacion_adicional);
    if (!ident.length && !contencion && !grupo && !mas) return "";
    return `<details class="crm-v2-plegable crm-v2-mas">
        <summary>Más datos del cliente <small>contención, grupo, perfil y datos de asignación</small></summary>
        <div class="crm-v2-mas-cuerpo">
            ${ident.length ? renderGrupoDetalle("Perfil", ident) : ""}
            ${contencion || grupo ? `<div class="crm-v2-grid">${contencion}${grupo}</div>` : ""}
            ${mas}
        </div>
    </details>`;
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
                    <div class="crm-titulo-linea"><h2 id="tituloClienteCRM">${h(cliente.nombre)}</h2><span class="crm-tipo">Cliente</span></div>
                    <div class="crm-identidad-linea">${metadatos.map(([label, value]) => `<span><b>${h(label)}</b>${h(value)}</span>`).join("")}</div>
                </div>
            </div>
            <div class="crm-estado-destacado" aria-label="Estado contractual de asignacion">
                ${estadoCalificacionCRM(cliente)}
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
        ${kpi("Capital vencido", money(situacion.capital_vencido), "alerta")}
        ${kpi("Desembolso", money(situacion.monto_desembolso))}
        ${kpi("Mora máxima", tieneValor(situacion.mora_maxima) ? `${format(situacion.mora_maxima)} días` : null, "alerta")}
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
            <thead><tr><th>Operación</th><th>Producto</th><th>Estado</th><th>Calificación / cartera</th><th class="numero">Mora</th><th class="numero">Capital</th><th>Qué cobrar</th><th>Contención</th><th>Acción</th></tr></thead>
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
        <td data-label="Estado">${h(item.condicion)}</td>
        <td data-label="Calificación / cartera">${celdaCalificacionOperacionCRM(item)}</td>
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
        [item.tipo_calificacion || "Calificación", item.calificacion], ["Cartera de la calificación", item.cartera_calificacion], ["Score", item.score], ["Tramo", item.tramo]
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
            <div class="crm-entidad-principal"><div class="avatar avatar-entidad" aria-hidden="true">${initials(grupo.nombre || grupo.codigo_grupo)}</div><div><div class="crm-titulo-linea"><h2 id="tituloGrupoCRM">${h(grupo.nombre || "Grupo Compartamos")}</h2><span class="crm-tipo">Grupo</span></div><div class="crm-identidad-linea">${datoLinea("Código grupo", grupo.codigo_grupo)}${datoLinea("Crédito grupal", grupo.credito_grupal)}${datoLinea("Oficina", grupo.oficina)}${datoLinea("Territorio", grupo.territorio)}${datoLinea("Producto", grupo.producto)}</div></div></div>
        </section>
        <section class="cliente-kpis-consolidados grupo-kpis-consolidados" aria-label="Situacion grupal">
            ${kpi("Integrantes", integrantes.length)}${kpi("Deuda total", money(situacion.deuda_actual))}${kpi("Capital", money(situacion.capital))}${kpi("Capital vencido", money(situacion.capital_vencido), "alerta")}${kpi("Mora máxima", tieneValor(situacion.mora_maxima) ? `${format(situacion.mora_maxima)} días` : null, "alerta")}${kpi("Cuotas vencidas máx.", format(maxCuotasVencidas))}${gestionDisponible ? kpi("Gestionados", gestionados) + kpi("Sin gestión", sinGestion, sinGestion > 0 ? "alerta" : "") : ""}
        </section>
        <section class="crm-insight-grupo"><p>${integrantes.length} integrante${integrantes.length === 1 ? "" : "s"} y ${data.operaciones.length} ${data.operaciones.length === 1 ? "operación" : "operaciones"} identificadas. ${!gestionDisponible ? "La gestión por integrante no está conectada." : gestionados ? `${gestionados} con gestión registrada en el mes.` : "No se registran gestiones en el mes."}</p></section>
        ${renderCronogramaCuotasCRM(data.cronograma_cuotas)}
        ${renderTablaIntegrantesCRM(integrantes, gestionDisponible)}
        ${renderContencionCRM(data.contencion)}
        <div class="crm-operativo-grid">${renderGestionCRM(data)}${renderPagosPdpCRM(data)}${renderCampanasGrupoCRM(data.campanas)}</div>
    `;
}

function renderTablaIntegrantesCRM(integrantes, gestionDisponible) {
    // La mora más alta del grupo se resalta; el resto queda neutro (sin umbrales inventados).
    const moras = integrantes.map(item => numeroValido(item.mora)).filter(value => value !== null);
    const moraMax = moras.length ? Math.max(...moras) : null;
    const pillMora = value => tieneValor(value) ? `<span class="crm-pill ${moraMax !== null && numeroValido(value) === moraMax ? "crm-pill-alerta" : "crm-pill-neutra"}">${format(value)} días</span>` : "—";
    const pillGestion = item => !gestionDisponible ? `<span class="crm-pill crm-pill-neutra">No conectado</span>` : item.gestion?.gestionado_mes ? `<span class="crm-pill crm-pill-ok">Gestionado</span>` : `<span class="crm-pill crm-pill-alerta">Sin gestión</span>`;
    return `<section class="cuentas-tabla-panel crm-integrantes-panel" aria-labelledby="tituloIntegrantesCRM">${cabeceraTabla("Integrantes", integrantes.length, "Abre el CRM del cliente sin perder el contexto del grupo.", "tituloIntegrantesCRM")}
        <div class="cuentas-tabla-scroll"><table class="cuentas-tabla crm-tabla-integrantes"><thead><tr><th>Integrante</th><th>DNI</th><th>Rol</th><th>Operación</th><th class="numero">Deuda</th><th class="numero">Capital</th><th class="numero">Mora</th><th class="numero">Cuotas vencidas</th><th>Último pago</th><th>Gestión</th><th>Calificación / segmentación</th><th>Contención</th><th>Acción</th></tr></thead><tbody>
            ${integrantes.map(item => `<tr class="cuenta-fila"><td data-label="Integrante"><strong>${h(item.nombre)}</strong></td><td data-label="DNI">${h(item.dni)}</td><td data-label="Rol"${tieneValor(item.rol) ? "" : ' class="sin-dato"'}>${h(item.rol)}</td><td data-label="Operación" class="crm-operacion-larga">${h(item.operaciones?.[0]?.operacion)}</td><td data-label="Deuda" class="numero">${money(item.deuda)}</td><td data-label="Capital" class="numero">${money(item.capital)}</td><td data-label="Mora" class="numero">${pillMora(item.mora)}</td><td data-label="Cuotas vencidas" class="numero">${h(item.cuotas_vencidas)}</td><td data-label="Último pago"${tieneValor(item.ultimo_pago_asignacion) ? "" : ' class="sin-dato"'}>${formatFecha(item.ultimo_pago_asignacion)}</td><td data-label="Gestión">${pillGestion(item)}</td><td data-label="Calificación / segmentación">${pildoraCalificacionCRM(item)}</td><td data-label="Contención"${item.contencion?.disponible ? "" : ' class="sin-dato"'}>${item.contencion?.disponible ? "Disponible" : "—"}</td><td data-label="Acción"><button class="cuenta-ver-detalle" type="button" data-buscar-entidad="${attr(item.dni || item.codigo_cliente)}">Ver cliente</button></td></tr>`).join("")}
        </tbody></table></div></section>`;
}

function renderCronogramaCuotasCRM(cronograma = {}) {
    if (!cronograma.disponible) return "";
    return `<div class="crm-cronograma-accion">
            <button class="crm-cronograma-toggle" type="button" data-abrir-cronograma aria-haspopup="dialog" aria-controls="cronogramaModalCRM"><svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true" focusable="false"><path d="M2.5 3.5h11v9h-11zM2.5 6.5h11M6.2 6.5v6" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/></svg><span class="crm-cronograma-toggle-texto">Cronograma de cuotas atrasadas</span></button>
        </div>
        <dialog id="cronogramaModalCRM" class="crm-modal" aria-labelledby="tituloCronogramaCRM">
            <div class="crm-modal-caja">
                <header class="crm-modal-cabecera">
                    <div><h3 id="tituloCronogramaCRM">Cronograma de cuotas atrasadas</h3><p id="subtituloCronogramaCRM"></p></div>
                    <button class="crm-modal-cerrar" type="button" data-cerrar-cronograma aria-label="Cerrar cronograma"><svg viewBox="0 0 16 16" width="16" height="16" aria-hidden="true" focusable="false"><path d="M3.5 3.5l9 9M12.5 3.5l-9 9" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg></button>
                </header>
                <nav class="crm-modal-tabs" role="tablist" aria-label="Secciones del cronograma">
                    <button type="button" role="tab" data-crono-tab="cronograma">Cronograma</button>
                    <button type="button" role="tab" data-crono-tab="pagar">Cuotas a pagar</button>
                    <button type="button" role="tab" data-crono-tab="cuadros">Cuadros</button>
                </nav>
                <div class="crm-modal-barra" id="cronogramaBarraCRM"></div>
                <div class="crm-modal-cuerpo" id="cronogramaCuerpoCRM" role="tabpanel"></div>
            </div>
        </dialog>`;
}

function abrirCronogramaCRM(boton) {
    const dialogo = document.getElementById("cronogramaModalCRM");
    if (!dialogo || typeof dialogo.showModal !== "function") return;
    window._cronogramaEstado = { tab: "cronograma", modo: "capital", animar: true, propuestas: {} };
    window._cronogramaOrigen = boton;
    pintarCronogramaCRM();
    dialogo.showModal();
    dialogo.querySelector(".crm-modal-cuerpo")?.scrollTo?.(0, 0);
}

function cerrarCronogramaCRM() {
    const dialogo = document.getElementById("cronogramaModalCRM");
    if (dialogo?.open) dialogo.close();
}

function cambiarCronogramaCRM(cambio) {
    window._cronogramaEstado = { ...(window._cronogramaEstado || { tab: "cronograma", modo: "capital" }), ...cambio, animar: !!cambio.tab };
    pintarCronogramaCRM();
}

function pintarCronogramaCRM() {
    const data = window._consultaCompartamosCRM;
    const cronograma = data?.cronograma_cuotas;
    const dialogo = document.getElementById("cronogramaModalCRM");
    if (!cronograma || !dialogo) return;
    const estado = window._cronogramaEstado || { tab: "cronograma", modo: "capital" };
    const plan = cronograma.plan || {};
    const hayTotal = (cronograma.integrantes || []).some(item => item.cuotas_total && Object.keys(item.cuotas_total).length);
    const modo = estado.modo === "total" && hayTotal ? "total" : "capital";
    dialogo.querySelectorAll("[data-crono-tab]").forEach(boton => {
        const activo = boton.dataset.cronoTab === estado.tab;
        boton.setAttribute("aria-selected", String(activo));
        boton.tabIndex = activo ? 0 : -1;
    });
    const sub = document.getElementById("subtituloCronogramaCRM");
    if (sub) sub.textContent = `${data.grupo?.nombre || "Grupo"} · ${data.grupo?.codigo_grupo || ""}`.replace(/ · $/, "");

    const parametros = cronograma.parametros || {};
    const chip = (etiqueta, valor, resaltar = false) => `<span class="crm-chip${resaltar ? " crm-chip-resalta" : ""}"><i>${h(etiqueta)}</i><b>${h(valor)}</b></span>`;
    const pct = value => tieneValor(value) ? (String(value).includes("%") ? value : `${value}%`) : null;
    const textoPlan = plan.disponible ? textoCuotasPlanCRM(plan) : null;
    const chips = [
        chip("Producto", parametros.producto_camp),
        chip("Cuotas a pagar", textoPlan ? `${plan.cuotas_por_pagar} (${textoPlan})` : null, !!textoPlan),
        chip("Campaña cliente", pct(parametros.pct_campana)),
        chip("Cuota grupo", pct(parametros.pct_campana_100)),
        chip("Cancelación grupo", pct(parametros.pct_cancelacion))
    ].join("");
    const segmento = estado.tab === "cuadros" ? "" : `<div class="crm-segmento" role="group" aria-label="Qué monto mostrar">
            <button type="button" data-crono-modo="capital" aria-pressed="${modo === "capital"}">Solo capital <small>CT 1, 2, 3</small></button>
            <button type="button" data-crono-modo="total" aria-pressed="${modo === "total"}"${hayTotal ? "" : " disabled"}>Total de la cuota <small>con cargos</small></button>
        </div>`;
    document.getElementById("cronogramaBarraCRM").innerHTML = `<div class="crm-chips">${chips}</div>${segmento}`;

    let cuerpo;
    if (estado.tab === "pagar") cuerpo = renderCronogramaPagarCRM(cronograma, modo);
    else if (estado.tab === "cuadros") cuerpo = renderCronogramaCuadrosCRM(data, cronograma);
    else cuerpo = renderMatrizCronogramaCRM(cronograma, modo, null) + renderLeyendaCronogramaCRM(cronograma, modo);
    const host = document.getElementById("cronogramaCuerpoCRM");
    host.classList.toggle("sin-animacion", estado.animar === false);
    host.innerHTML = cuerpo;
}

function renderLeyendaCronogramaCRM(cronograma, modo) {
    return `<footer class="crm-cronograma-leyenda">
        <span class="crm-leyenda-item"><i class="rango-0"></i>Cuota más antigua</span>
        <span class="crm-leyenda-item"><i class="rango-1"></i>Siguiente</span>
        <span class="crm-leyenda-item"><i class="rango-2"></i>Subsiguiente</span>
        <span class="crm-leyenda-item"><i class="marca-pagar"></i>Cuota a pagar</span>
        <span class="crm-leyenda-nota">${modo === "total" ? "Total de la cuota = capital + otros cargos por atraso (CT k, k1…k5)." : "Solo cuota capital (CT 1, CT 2, CT 3); no incluye otros cargos."} Montos redondeados hacia arriba al sol; el exacto aparece al pasar el cursor. Inicio: compartamos_grupal · Hoy: carga diaria SAC · Proyectado = inicio + ${h(cronograma.dias_proyeccion)} días.</span>
    </footer>`;
}

// Matriz integrantes x cuota. `soloCuotas` limita las columnas (pestaña "Cuotas a pagar").
function renderMatrizCronogramaCRM(cronograma, modo, soloCuotas) {
    const plan = cronograma.plan || {};
    const cuotas = (soloCuotas || cronograma.cuotas || []).map(String);
    const integrantes = cronograma.integrantes || [];
    const montos = item => (modo === "total" ? item.cuotas_total : item.cuotas) || {};
    // La matriz sigue por número de cuota; lo que se paga se marca celda por celda (por fecha de
    // vencimiento: un integrante puede pagar su N.° 2 y otro su N.° 3 si vencen el mismo día).
    const aPagar = (item, numero) => plan.disponible && Object.prototype.hasOwnProperty.call(item.a_pagar || {}, numero);
    const marcadas = new Set(cuotas.filter(numero => integrantes.some(item => aPagar(item, numero))));
    const diasTexto = value => tieneValor(value) ? `${format(value)} d` : "—";
    // Redondeo siempre hacia arriba; los totales suman lo que se ve en pantalla para que la tabla cuadre.
    const celda = (item, numero) => numeroValido(montos(item)[numero]) === null ? 0 : montoArriba(montos(item)[numero]);
    const totalesPorFila = integrantes.map(item => cuotas.reduce((acc, numero) => acc + celda(item, numero), 0));
    const totalColumna = numero => integrantes.reduce((acc, item) => acc + celda(item, numero), 0);
    const maximoFila = Math.max(0, ...totalesPorFila);
    const totalGrupo = totalesPorFila.reduce((acc, value) => acc + value, 0);
    const clasePagar = numero => marcadas.has(numero) && !soloCuotas ? " col-pagar" : "";
    const clasePagarCelda = (item, numero) => aPagar(item, numero) && !soloCuotas ? " col-pagar" : "";
    const filas = integrantes.map((item, index) => {
        const total = totalesPorFila[index];
        const ancho = maximoFila > 0 && total > 0 ? Math.max(6, Math.round(total / maximoFila * 100)) : 0;
        const rol = tieneValor(item.rol) && String(item.rol).toLowerCase() !== "integrante" ? `<em class="crm-rol">${h(item.rol)}</em>` : "";
        return `<tr style="--i:${index}">
        <th scope="row" data-label="Integrante"><strong>${h(item.nombre)}</strong><span>${h(item.dni)}${rol}</span></th>
        ${cuotas.map(numero => {
            const monto = montos(item)[numero];
            const rango = tieneValor(monto) && tieneValor(item.cuota_mas_atrasada) ? Math.min(Math.max(Number(numero) - Number(item.cuota_mas_atrasada), 0), 2) : null;
            return `<td data-label="Cuota ${h(numero)}" class="numero ${rango === null ? "sin-monto" : `rango-${rango}`}${clasePagarCelda(item, numero)}"${rango === null ? "" : ` title="${attr(money(monto) + (aPagar(item, numero) ? " · a pagar" : ""))}"`}>${rango === null ? "—" : montoEntero(monto)}</td>`;
        }).join("")}
        <td data-label="Total" class="numero crm-cronograma-total"><b>${total > 0 ? montoEntero(total) : "—"}</b><i style="--w:${ancho}%"></i></td>
        ${soloCuotas ? "" : `<td data-label="Atraso inicio" class="numero crm-cronograma-corte">${diasTexto(item.dias_atraso_inicio)}</td>
        <td data-label="Atraso hoy" class="numero">${diasTexto(item.dias_atraso_hoy)}</td>
        <td data-label="Proyectado" class="numero crm-cronograma-proyectado">${diasTexto(item.dias_atraso_proyectado)}</td>
        <td data-label="Pagadas" class="numero">${tieneValor(item.cuotas_pagadas) && tieneValor(item.cuotas_aprobadas) ? `${format(item.cuotas_pagadas)}/${format(item.cuotas_aprobadas)}` : "—"}</td>`}
    </tr>`;
    }).join("");
    const colsDatos = cuotas.length + 1;
    const titulo = modo === "total" ? "Total de la cuota (S/)" : "Cuota capital (S/)";
    return `<section class="crm-cronograma-panel" aria-label="${attr(titulo)}">
        <table class="crm-cronograma-tabla">
            <thead>
                <tr><th scope="col" rowspan="2" class="crm-col-nombre">Integrante</th><th scope="colgroup" colspan="${colsDatos}" class="numero">${h(titulo)}</th>${soloCuotas ? "" : `<th scope="colgroup" colspan="3" class="numero crm-cronograma-corte">Días de atraso</th><th scope="col" rowspan="2" class="numero">Pagadas</th>`}</tr>
                <tr>${cuotas.map(numero => `<th scope="col" class="numero${clasePagar(numero)}">N.° ${h(numero)}${marcadas.has(numero) && !soloCuotas ? "<small>a pagar</small>" : ""}</th>`).join("")}<th scope="col" class="numero">Total</th>${soloCuotas ? "" : `<th scope="col" class="numero crm-cronograma-corte">Inicio</th><th scope="col" class="numero">Hoy</th><th scope="col" class="numero">Proyect.</th>`}</tr>
            </thead>
            <tbody>${filas}</tbody>
            <tfoot><tr><th scope="row" data-label="Total">Total</th>${cuotas.map(numero => `<td data-label="Cuota ${h(numero)}" class="numero${clasePagar(numero)}">${montoEntero(totalColumna(numero))}</td>`).join("")}<td data-label="Total" class="numero">${montoEntero(totalGrupo)}</td>${soloCuotas ? "" : `<td class="crm-cronograma-corte crm-cronograma-vacio" colspan="4"></td>`}</tr></tfoot>
        </table>
    </section>`;
}

// Texto corto de una cuota exigida: "N.° 3 · vence 12/08/2026" o, si los números difieren
// entre integrantes, "N.° 2 y 3 · vence 12/08/2026".
function etiquetaVencimientoCRM(venc) {
    const numeros = (venc.numeros && venc.numeros.length ? venc.numeros : [venc.cuota]).map(n => format(n));
    return `N.° ${numeros.join(" y ")} · vence ${formatFecha(venc.fecha_vencimiento)}`;
}

function textoCuotasPlanCRM(plan) {
    const vencimientos = plan.vencimientos || [];
    if (vencimientos.length) return vencimientos.map(etiquetaVencimientoCRM).join(" · ");
    return (plan.cuotas || []).length ? plan.cuotas.join(" y ") : null;
}

// Cuotas a pagar del grupo por FECHA DE VENCIMIENTO (regla 2026-10-13): una columna por cuota
// exigida; cada integrante paga su cuota de esa fecha, aunque su número sea otro.
function renderCronogramaPagarCRM(cronograma, modo) {
    const plan = cronograma.plan || {};
    if (!plan.disponible) return `<div class="crm-modal-aviso"><strong>No se puede determinar las cuotas a pagar.</strong><span>${h(plan.motivo || "Sin información suficiente.")}</span></div>`;
    const vencimientos = plan.vencimientos || [];
    const integrantes = cronograma.integrantes || [];
    const detalle = (item, venc) => (item.a_pagar_detalle || []).find(d => d.fecha_vencimiento === venc.fecha_vencimiento) || null;
    const monto = (item, venc) => { const d = detalle(item, venc); return d ? numeroValido(modo === "total" ? d.total : d.capital) : null; };
    const celda = (item, venc) => { const m = monto(item, venc); return m === null ? 0 : montoArriba(m); };
    const totalesFila = integrantes.map(item => vencimientos.reduce((acc, venc) => acc + celda(item, venc), 0));
    const totalVenc = venc => integrantes.reduce((acc, item) => acc + celda(item, venc), 0);
    const total = totalesFila.reduce((acc, value) => acc + value, 0);
    const maximo = Math.max(0, ...totalesFila);
    const pagan = venc => integrantes.filter(item => monto(item, venc) !== null).length;
    const resumen = vencimientos.map(venc => `<div class="crm-resumen-cuota"><span>${h(etiquetaVencimientoCRM(venc))}</span><b>${montoEntero(totalVenc(venc))}</b><small>${h(format(pagan(venc)))} de ${h(format(integrantes.length))} integrantes</small></div>`).join("");
    const filas = integrantes.map((item, index) => {
        const totalFila = totalesFila[index];
        const ancho = maximo > 0 && totalFila > 0 ? Math.max(6, Math.round(totalFila / maximo * 100)) : 0;
        const rol = tieneValor(item.rol) && String(item.rol).toLowerCase() !== "integrante" ? `<em class="crm-rol">${h(item.rol)}</em>` : "";
        return `<tr style="--i:${index}">
        <th scope="row" data-label="Integrante"><strong>${h(item.nombre)}</strong><span>${h(item.dni)}${rol}</span></th>
        ${vencimientos.map(venc => {
            const d = detalle(item, venc);
            const m = monto(item, venc);
            return m === null
                ? `<td data-label="${attr(etiquetaVencimientoCRM(venc))}" class="numero sin-monto">—</td>`
                : `<td data-label="${attr(etiquetaVencimientoCRM(venc))}" class="numero col-pagar" title="${attr(`${money(m)} · cuota N.° ${d.cuota}`)}">${montoEntero(m)}<small class="crm-cuota-numero">N.° ${h(format(d.cuota))}</small></td>`;
        }).join("")}
        <td data-label="Total" class="numero crm-cronograma-total"><b>${totalFila > 0 ? montoEntero(totalFila) : "—"}</b><i style="--w:${ancho}%"></i></td>
    </tr>`;
    }).join("");
    const titulo = modo === "total" ? "A pagar · total de la cuota (S/)" : "A pagar · cuota capital (S/)";
    const aviso = plan.alineado === false ? `<p class="crm-pagar-nota">Los integrantes tienen cronogramas desplazados: en una misma fecha vencen cuotas de distinto número. Pagan todos los que tienen cuota en esa fecha.</p>` : "";
    return `<div class="crm-pagar-resumen">
            <p><b>${h(plan.cuotas_por_pagar)} cuota${plan.cuotas_por_pagar === 1 ? "" : "s"} por pagar</b> · producto ${h(plan.producto)} · las más atrasadas del grupo por fecha de vencimiento</p>
            ${aviso}
            <div class="crm-resumen-fila">${resumen}<div class="crm-resumen-cuota crm-resumen-total"><span>A cobrar al grupo</span><b>${montoEntero(total)}</b></div></div>
        </div>
        <section class="crm-cronograma-panel" aria-label="${attr(titulo)}">
            <table class="crm-cronograma-tabla">
                <thead>
                    <tr><th scope="col" rowspan="2" class="crm-col-nombre">Integrante</th><th scope="colgroup" colspan="${vencimientos.length + 1}" class="numero">${h(titulo)}</th></tr>
                    <tr>${vencimientos.map(venc => `<th scope="col" class="numero">Vence ${h(formatFecha(venc.fecha_vencimiento))}<small>N.° ${h(((venc.numeros && venc.numeros.length) ? venc.numeros : [venc.cuota]).join(" y "))}</small></th>`).join("")}<th scope="col" class="numero">Total</th></tr>
                </thead>
                <tbody>${filas}</tbody>
                <tfoot><tr><th scope="row" data-label="Total">Total</th>${vencimientos.map(venc => `<td data-label="${attr(etiquetaVencimientoCRM(venc))}" class="numero">${montoEntero(totalVenc(venc))}</td>`).join("")}<td data-label="Total" class="numero">${montoEntero(total)}</td></tr></tfoot>
            </table>
        </section>
        <footer class="crm-cronograma-leyenda"><span class="crm-leyenda-nota">${modo === "total" ? "Incluye capital y otros cargos por atraso de cada cuota." : "Solo cuota capital."} Debajo de cada monto, el número de la cuota de ese integrante. Redondeado hacia arriba al sol por integrante; el exacto aparece al pasar el cursor.</span></footer>`;
}

// Primer número de un texto como "45% Capital" -> 45. Sin número legible no se calcula nada.
function porcentajeCampana(value) {
    const m = String(value ?? "").match(/\d+(?:[.,]\d+)?/);
    return m ? Number(m[0].replace(",", ".")) : null;
}

function solCuadro(value) {
    const n = numeroValido(value);
    return n === null ? "—" : `<span class="crm-monto">${money(n)}</span>`;
}

// Cuadros del correo de campaña.
//  Base de cancelación = capital × (100 − % campaña) / 100.
//  Excepción: el agente ingresa un monto propuesto; % propuesta = (1 − propuesta / capital) × 100
//  (misma convención que la campaña) y el monto por cuota se reparte en proporción al capital de cada cuota.
// Las celdas que aún no tienen regla quedan en "—".
function renderCronogramaCuadrosCRM(data, cronograma) {
    const grupo = data.grupo || {};
    const integrantes = data.integrantes || [];
    const plan = cronograma.plan || {};
    const parametros = cronograma.parametros || {};
    const propuestas = (window._cronogramaEstado || {}).propuestas || {};
    const pctCliente = porcentajeCampana(parametros.pct_campana);
    const pctCuota = porcentajeCampana(parametros.pct_campana_100);
    const pctCancel = porcentajeCampana(parametros.pct_cancelacion);
    const texto = value => tieneValor(value) ? h(value) : "—";
    const pct = value => value === null ? "—" : `${format(Math.round(value * 10) / 10)}%`;
    const base = (capital, porcentaje) => capital === null || porcentaje === null ? null : Math.round(capital * (100 - porcentaje)) / 100;
    const propuestaNumero = clave => { const n = numeroValido(propuestas[clave]); return n !== null && n >= 0 ? n : null; };
    const entrada = (clave, etiqueta, visible = false) => `<label class="crm-propuesta${visible ? "" : " crm-propuesta-compacta"}">${visible ? `<span>${h(etiqueta)}</span>` : ""}<input type="text" inputmode="decimal" autocomplete="off" aria-label="${attr(etiqueta)}" data-propuesta="${attr(clave)}" value="${tieneValor(propuestas[clave]) ? attr(propuestas[clave]) : ""}" placeholder="S/ monto"></label>`;
    const aviso = (propuesta, baseMonto) => propuesta !== null && baseMonto !== null && propuesta < baseMonto ? `<small class="crm-propuesta-nota">Por debajo de la campaña (excepción)</small>` : "";

    // % propuesta = lo que se paga sobre el capital (monto ÷ capital), subido al entero ("siempre buscamos cobrar más").
    const pctPagado = (monto, capital) => monto === null || !capital ? null : monto / capital * 100;
    const pctEntero = value => value === null ? "—" : `${new Intl.NumberFormat("es-PE", { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(value)}%`;

    // La asignación trae el DESCUENTO (45%); para compararlo con la propuesta se muestra lo que se PAGA (55%).
    const pagaDeDescuento = d => d === null ? null : 100 - d;
    const celdaPct = (paga, descuento) => paga === null ? "—" : `${pctEntero(paga)}<span class="crm-pct-chico">Dscto ${pctEntero(descuento)}</span>`;
    const celdaCampana = descuento => descuento === null ? "—" : celdaPct(pagaDeDescuento(descuento), descuento);
    const celdaPropuesta = paga => paga === null ? "—" : celdaPct(paga, 100 - paga);

    // Detalle por cliente: porcentajes propios de cada integrante; el saldo es su capital.
    const saldoGrupo = integrantes.reduce((acc, item) => acc + (numeroValido(item.capital) || 0), 0);
    const hayCapital = integrantes.some(item => numeroValido(item.capital) !== null);
    const porDni = new Map((cronograma.integrantes || []).map(item => [String(item.dni || "").replace(/^0+/, ""), item]));
    const filasA = integrantes.map(item => {
        const par = porDni.get(String(item.dni || "").replace(/^0+/, "")) || {};
        return `<tr><td data-label="Cuenta cliente">${h(item.operaciones?.[0]?.operacion)}<span>${h(item.nombre)}</span></td><td data-label="Campaña cancelación" class="numero">${texto(par.pct_cancelacion)}</td><td data-label="Propuesta" class="sin-dato">—</td><td data-label="% Propuesta" class="sin-dato">—</td><td data-label="Rango atraso" class="numero">${texto(par.rango_atraso)}</td><td data-label="Campaña" class="numero">${texto(par.pct_campana)}</td><td data-label="Saldo capital" class="numero">${solCuadro(numeroValido(item.capital))}</td><td data-label="Top_NroGru" class="sin-dato">—</td><td data-label="N° integrantes" class="numero">${integrantes.length}</td><td data-label="Saldo grupo" class="numero">${hayCapital ? solCuadro(saldoGrupo) : "—"}</td><td data-label="Prioridad" class="sin-dato">—</td></tr>`;
    }).join("");

    // Cancelación grupo: se calcula sobre el capital (saldo capital) del grupo, mientras se confirma la base.
    const vencidoGrupo = hayCapital ? Math.round(saldoGrupo * 100) / 100 : null;
    const baseCancel = base(vencidoGrupo, pctCancel);
    const propCancel = propuestaNumero("cancelacion");
    const pctPropCancel = pctPagado(propCancel, vencidoGrupo);
    const montoPropCancel = propCancel;
    const filaB = `<tr><td data-label="Nombre grupo">${texto(grupo.nombre)}</td><td data-label="Cred. grupal">${texto(grupo.credito_grupal)}</td><td data-label="Saldo grupo" class="numero">${solCuadro(vencidoGrupo)}</td><td data-label="Rango atraso" class="numero">${texto(parametros.rango_atraso)}</td><td data-label="Camp. cancelación" class="numero">${solCuadro(baseCancel)}</td><td data-label="% Campaña" class="numero">${celdaCampana(pctCancel)}</td><td data-label="Propuesta" class="numero">${entrada("cancelacion", "Propuesta")}${aviso(propCancel, baseCancel)}</td><td data-label="% Propuesta" class="numero">${celdaPropuesta(pctPropCancel)}</td><td data-label="Top_NroGru" class="sin-dato">—</td></tr>`;

    const saldo = hayCapital ? Math.round(saldoGrupo * 100) / 100 : null;
    // Cuota grupo: por cada cuota a pagar (fecha de vencimiento), suma del capital de los integrantes
    // que tienen cuota en esa fecha, aunque su número de cuota sea distinto (regla 2026-10-13).
    const vencimientos = plan.disponible ? (plan.vencimientos || []) : [];
    const cuotas = vencimientos.map(etiquetaVencimientoCRM);
    const capitales = vencimientos.map(v => numeroValido(v.capital));
    const capitalTotal = capitales.reduce((acc, v) => acc + (v || 0), 0);
    const baseCuotas = capitales.map(v => base(v, pctCuota));
    const baseTotalCuota = pctCuota === null ? null : Math.round(baseCuotas.reduce((acc, v) => acc + (v || 0), 0) * 100) / 100;
    const propCuota = propuestaNumero("cuota");
    const pctPropCuota = pctPagado(propCuota, capitalTotal);
    const montoPropuesto = capital => pctPropCuota !== null && capital !== null ? capital * pctPropCuota / 100 : null;
    const filasC = cuotas.map((n, i) => {
        const capital = capitales[i];
        return `<tr><td data-label="Nombre grupo">${texto(grupo.nombre)}</td><td data-label="Cred. grupal">${texto(grupo.credito_grupal)}</td><td data-label="Saldo grupo" class="numero">${solCuadro(saldo)}</td><td data-label="Rango atraso" class="numero">${texto(parametros.rango_atraso)}</td><td data-label="N° cuota">${h(n)}</td><td data-label="Capital cuota" class="numero">${solCuadro(capital)}</td><td data-label="% campaña" class="numero">${celdaCampana(pctCuota)}</td><td data-label="Campaña cuota" class="numero">${solCuadro(baseCuotas[i])}</td><td data-label="Propuesta" class="numero">${solCuadro(montoPropuesto(capital))}</td><td data-label="% Propuesta" class="numero">${celdaPropuesta(pctPropCuota)}</td><td data-label="Top_NroGru" class="sin-dato">—</td></tr>`;
    }).join("");
    const sumaArriba = valores => Math.round(valores.reduce((acc, v) => acc + (v === null ? 0 : v), 0) * 100) / 100;
    const pieC = cuotas.length ? `<tfoot><tr><th scope="row" colspan="5">Total</th><td class="numero">${money(sumaArriba(capitales))}</td><td class="numero">${celdaCampana(pctCuota)}</td><td class="numero">${baseTotalCuota === null ? "—" : money(baseTotalCuota)}</td><td class="numero">${pctPropCuota === null ? "—" : money(sumaArriba(capitales.map(montoPropuesto)))}</td><td class="numero">${celdaPropuesta(pctPropCuota)}</td><td></td></tr></tfoot>` : "";
    const entradaCuota = cuotas.length ? `<div class="crm-propuesta-barra">${entrada("cuota", "Monto que ofrece el grupo", true)}${aviso(propCuota, baseTotalCuota)}<small>${pctPropCuota === null ? "Escribe el monto de negociación para calcular el % propuesta y lo que paga cada cuota." : `El grupo pagaría ${pctEntero(pctPropCuota)} del capital (descuento de ${pctEntero(100 - pctPropCuota)}); cada cuota paga su capital × ese %.`}</small></div>` : "";

    const cuadro = (titulo, cabeceras, filas, pie = "", extra = "", footer = "") => `<section class="crm-cuadro"><h4>${h(titulo)}</h4>${extra}<div class="cuentas-tabla-scroll"><table class="crm-cuadro-tabla"><thead><tr>${cabeceras.map(c => `<th scope="col"${/saldo|capital|integrantes|campaña|%|propuesta|camp\./i.test(c) ? ' class="numero"' : ""}>${h(c)}</th>`).join("")}</tr></thead><tbody>${filas}</tbody>${pie}</table></div>${footer}</section>`;
    const preparacion = prepararDocumentoCuotasCRM(data, cronograma, propCuota);
    const accionDocumento = cuotas.length && puedePrepararDocumentoGrupoCRM() ? `<div class="crm-documento-cuotas"><button type="button" data-abrir-documentos-grupo${preparacion ? "" : " disabled"}>Preparar compromiso grupal</button><small>${preparacion ? `${preparacion.pagos.length} integrante${preparacion.pagos.length === 1 ? "" : "s"} · ${cuotas.join(" y ")} · ${money(propCuota)}. Se abrirá en otra pestaña para revisar los montos antes de generar.` : "Ingresa una propuesta válida y verifica las cuotas para preparar el compromiso."}</small></div>` : "";
    const faltaPct = pctCuota === null || pctCancel === null || pctCliente === null ? `<p class="crm-modal-aviso crm-aviso-pct"><strong>No se pudo leer: ${[pctCliente === null ? "% Campaña Cliente" : "", pctCuota === null ? "% Campaña Cliente 100%" : "", pctCancel === null ? "% Cancelación Cliente" : ""].filter(Boolean).join(", ")}.</strong><span>La columna no existe, viene vacía o tiene valores distintos entre integrantes de compartamos_grupal. Sin ese % no se calcula la campaña.</span></p>` : "";
    return `<div class="crm-cuadros">
        ${faltaPct}<ul class="crm-cuadros-nota">
            <li><b>Campaña cuota</b>: capital de la cuota (suma de los integrantes) × (100 − % campaña) ÷ 100. Solo capital, sin intereses ni cargos.</li>
            <li><b>Cancelación grupo</b>: capital del grupo × (100 − % cancelación) ÷ 100 (base en confirmación).</li>
            <li><b>Porcentajes</b>: la asignación trae el descuento (45%); aquí se compara contra lo que se paga (55%) y el descuento queda debajo en letra chica.</li>
            <li><b>Excepción</b>: escribe el monto que ofrece el grupo. El % propuesta es monto ÷ capital, y cada cuota paga su capital × ese %; la suma es exactamente el monto ofrecido.</li>
            <li>Los montos de este cuadro se muestran con decimales, sin redondear. “—” = regla aún no definida.</li>
        </ul>
        ${cuadro("Detalle por cliente", ["Cuenta cliente", "Campaña cancelación", "Propuesta", "% Propuesta", "Rango atraso", "Campaña", "Saldo capital", "Top_NroGru", "N° integrantes", "Saldo grupo", "Prioridad"], filasA)}
        ${cuadro("Cancelación grupo", ["Nombre grupo", "Cred. grupal", "Saldo grupo", "Rango atraso", "Camp. cancelación", "% Campaña", "Propuesta", "% Propuesta", "Top_NroGru"], filaB)}
        ${cuadro("Cuota grupo", ["Nombre grupo", "Cred. grupal", "Saldo grupo", "Rango atraso", "N° cuota", "Capital cuota", "% campaña", "Campaña cuota", "Propuesta", "% Propuesta", "Top_NroGru"], filasC || `<tr><td colspan="11" class="sin-dato">${h(plan.motivo || "Sin cuotas a pagar determinadas.")}</td></tr>`, pieC, entradaCuota, accionDocumento)}
    </div>`;
}

function puedePrepararDocumentoGrupoCRM() {
    const permiso = typeof puedeUsarVista === "function" ? puedeUsarVista("documentos") : null;
    if (permiso !== null) return permiso;
    const tipo = typeof normalizarTipoUsuario === "function"
        ? normalizarTipoUsuario(localStorage.getItem("tipo"))
        : String(localStorage.getItem("tipo") || "").trim().toUpperCase();
    return (typeof esSupervisor === "function" && esSupervisor(tipo)) ||
        ["ADMINISTRADOR", "JEFE DE CARTERA", "JEFE DE CARTERAS", "JEFE CARTERA"].includes(tipo);
}

function prepararDocumentoCuotasCRM(data, cronograma, propuesta) {
    // Cuotas exigidas por fecha de vencimiento (regla 2026-10-13); cada integrante aporta el capital
    // de SU cuota en esas fechas (a_pagar), no el de un mismo número de cuota.
    const vencimientos = cronograma?.plan?.disponible ? (cronograma.plan.vencimientos || []) : [];
    const cuotas = vencimientos.map(etiquetaVencimientoCRM);
    const grupo = data?.grupo || {};
    const total = vencimientos.reduce((suma, venc) => suma + (numeroValido(venc.capital) || 0), 0);
    const totalCentimos = Math.round(total * 100);
    const propuestaCentimos = Math.round(Number(propuesta) * 100);
    if (!cuotas.length || !totalCentimos || !Number.isFinite(propuestaCentimos) || propuestaCentimos <= 0 ||
        Math.abs(Number(propuesta) * 100 - propuestaCentimos) > 1e-7 ||
        (!grupo.codigo_grupo && !grupo.credito_grupal)) return null;

    const integrantes = (cronograma.integrantes || []).map(item => ({
        operacion: String(item.operacion || "").trim(),
        dni: String(item.dni || "").trim(),
        capitalCentimos: Math.round(Object.values(item.a_pagar || {}).reduce((suma, monto) => suma + (numeroValido(monto) || 0), 0) * 100),
    })).filter(item => item.capitalCentimos > 0);
    if (!integrantes.length || integrantes.some(item => !item.operacion || !item.dni) ||
        new Set(integrantes.map(item => item.operacion)).size !== integrantes.length ||
        // Tolerancia de 1 céntimo por integrante: el total por fecha y el de cada integrante se redondean por separado.
        Math.abs(integrantes.reduce((suma, item) => suma + item.capitalCentimos, 0) - totalCentimos) > integrantes.length) return null;

    // Distribuye los centimos residuales por la mayor fraccion para conservar exactamente la oferta del grupo.
    const baseCentimos = integrantes.reduce((suma, item) => suma + item.capitalCentimos, 0);
    const pagos = integrantes.map(item => {
        const exacto = propuestaCentimos * item.capitalCentimos / baseCentimos;
        return { ...item, centimos: Math.floor(exacto), fraccion: exacto - Math.floor(exacto) };
    });
    let residuo = propuestaCentimos - pagos.reduce((suma, item) => suma + item.centimos, 0);
    pagos.sort((a, b) => b.fraccion - a.fraccion || a.operacion.localeCompare(b.operacion));
    for (let index = 0; index < residuo; index += 1) pagos[index].centimos += 1;
    const seleccionados = pagos.filter(item => item.centimos > 0).map(item => ({
        operacion: item.operacion, dni: item.dni, monto: (item.centimos / 100).toFixed(2),
    }));
    if (!seleccionados.length) return null;
    return {
        version: 1,
        creado: Date.now(),
        usuario: String(localStorage.getItem("dni") || ""),
        codigo_grupo: String(grupo.codigo_grupo || ""),
        cod_cre_grupal: String(grupo.credito_grupal || ""),
        cuotas,
        propuesta: (propuestaCentimos / 100).toFixed(2),
        pagos: seleccionados,
    };
}

function abrirDocumentosGrupoCRM() {
    if (!puedePrepararDocumentoGrupoCRM()) return;
    const data = window._consultaCompartamosCRM;
    const propuesta = numeroValido(window._cronogramaEstado?.propuestas?.cuota);
    const preparacion = prepararDocumentoCuotasCRM(data, data?.cronograma_cuotas, propuesta);
    if (!preparacion) return;
    const bytes = new Uint8Array(16);
    window.crypto.getRandomValues(bytes);
    const identificador = Array.from(bytes, byte => byte.toString(16).padStart(2, "0")).join("");
    const clave = `crm_documento_cuotas_grupo:${identificador}`;
    try {
        localStorage.setItem(clave, JSON.stringify(preparacion));
        // El fragmento lleva solo un identificador aleatorio; los datos quedan en el navegador.
        window.open(`documentos.html#radar_cuotas=${identificador}`, "_blank", "noopener");
    } catch (error) {
        try { localStorage.removeItem(clave); } catch (_) { /* almacenamiento no disponible */ }
        window.alert("No se pudo abrir el compromiso grupal. Revisa el almacenamiento del navegador e inténtalo otra vez.");
    }
}

function montoArriba(value) {
    const numero = numeroValido(value);
    // Se limpia el error de punto flotante antes (217.0000001 no debe subir a 218).
    return numero === null ? null : Math.ceil(Math.round(numero * 100) / 100);
}

function montoEntero(value) {
    const redondeado = typeof value === "number" && Number.isInteger(value) ? value : montoArriba(value);
    return redondeado === null ? "—" : new Intl.NumberFormat("es-PE", { maximumFractionDigits: 0 }).format(redondeado);
}

function montoPlano(value) {
    const numero = numeroValido(value);
    return numero === null ? "—" : new Intl.NumberFormat("es-PE", { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(numero);
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
    const envoltorio = document.getElementById("detalleOperacionWrap");
    if (envoltorio) {
        envoltorio.open = true;
        const resumen = document.getElementById("detalleOperacionResumen");
        if (resumen) resumen.textContent = `Detalle de la operación ${item.operacion ?? ""}`;
    }
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
function claseSegmentacionCRM(valor) {
    const k = String(valor ?? "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").trim().toLowerCase();
    return ["verde", "ambar", "rojo"].includes(k) ? `crm-seg crm-seg-${k}` : "";
}
function pildoraCalificacionCRM(entidad) {
    const valor = entidad?.calificacion;
    if (!tieneValor(valor)) return `<span class="crm-pill crm-pill-neutra">${h(valor)}</span>`;
    const clase = entidad.tipo_calificacion === "Segmentación" ? claseSegmentacionCRM(valor) : "";
    return clase ? `<span class="${clase}">${h(valor)}</span>` : `<span class="crm-pill crm-pill-neutra">${h(valor)}</span>`;
}
function claseCarteraCRM(cartera) {
    const k = String(cartera ?? "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().replace(/[^a-z]+/g, "-").replace(/^-|-$/g, "");
    return k ? `crm-cartera crm-cartera-${k}` : "crm-cartera";
}
function celdaCalificacionOperacionCRM(item) {
    if (!tieneValor(item?.calificacion)) return "—";
    const cartera = tieneValor(item.cartera_calificacion) ? `<span class="${claseCarteraCRM(item.cartera_calificacion)}">${h(item.cartera_calificacion)}</span>` : "";
    return `<div class="crm-cal-celda">${pildoraCalificacionCRM(item)}${cartera}</div>`;
}
function carteraCalificacionTextoCRM(entidad) {
    return tieneValor(entidad?.cartera_calificacion) ? `<span class="${claseCarteraCRM(entidad.cartera_calificacion)}">${h(entidad.cartera_calificacion)}</span>` : "";
}
function estadoCalificacionCRM(entidad) {
    const tipo = entidad?.tipo_calificacion || "Calificación";
    if (tipo === "Segmentación" && tieneValor(entidad?.calificacion)) {
        return `<div><span>${h(tipo)}</span><strong>${pildoraCalificacionCRM(entidad)}</strong>${carteraCalificacionTextoCRM(entidad)}</div>`;
    }
    return tieneValor(entidad?.calificacion)
        ? `<div><span>${h(tipo)}</span><strong>${h(entidad.calificacion)}</strong>${carteraCalificacionTextoCRM(entidad)}</div>`
        : estadoDestacado(tipo, entidad?.calificacion);
}
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
function kpi(label, value, tono = "") { return `<div class="kpi${tono ? ` kpi-${tono}` : ""}"><span>${h(label)}</span><b>${h(value)}</b></div>`; }
function reducirMovimiento() { return window.matchMedia?.("(prefers-reduced-motion: reduce)").matches; }

function configurarConsultaCompartamos() {
    const resultado = document.getElementById("resultado");
    if (!resultado) return;
    resultado.addEventListener("input", event => {
        const campo = event.target.closest?.("[data-propuesta]");
        if (!campo) return;
        const clave = campo.dataset.propuesta;
        const posicion = campo.selectionStart;
        const estado = window._cronogramaEstado || {};
        cambiarCronogramaCRM({ propuestas: { ...(estado.propuestas || {}), [clave]: campo.value }, animar: false });
        const nuevo = document.querySelector(`[data-propuesta="${clave}"]`);
        if (nuevo) { nuevo.focus(); try { nuevo.setSelectionRange(posicion, posicion); } catch (e) { /* tipo sin selección */ } }
    });
    resultado.addEventListener("click", event => {
        const selector = event.target.closest("[data-seleccionar-operacion]");
        if (selector) { seleccionarOperacion(selector.dataset.seleccionarOperacion); return; }
        const buscarEntidad = event.target.closest("[data-buscar-entidad]");
        if (buscarEntidad) { navegarEntidadCRM(buscarEntidad.dataset.buscarEntidad); return; }
        if (event.target.closest("[data-volver-entidad]")) { volverEntidadCRM(); return; }
        const abrirCronograma = event.target.closest("[data-abrir-cronograma]");
        if (abrirCronograma) { abrirCronogramaCRM(abrirCronograma); return; }
        if (event.target.closest("[data-cerrar-cronograma]")) { cerrarCronogramaCRM(); return; }
        const tabCrono = event.target.closest("[data-crono-tab]");
        if (tabCrono) { cambiarCronogramaCRM({ tab: tabCrono.dataset.cronoTab }); return; }
        const modoCrono = event.target.closest("[data-crono-modo]");
        if (modoCrono && !modoCrono.disabled) { cambiarCronogramaCRM({ modo: modoCrono.dataset.cronoModo }); return; }
        if (event.target.closest("[data-abrir-documentos-grupo]:not([disabled])")) { abrirDocumentosGrupoCRM(); return; }
        if (event.target.id === "cronogramaModalCRM") { cerrarCronogramaCRM(); return; }
        const fila = event.target.closest("[data-cuenta-index]");
        if (fila && !event.target.closest("a, button, input, select, textarea")) seleccionarOperacion(fila.dataset.cuentaIndex);
    });
}

window.addEventListener("DOMContentLoaded", configurarConsultaCompartamos);
