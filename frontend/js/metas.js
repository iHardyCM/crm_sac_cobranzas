const BASE_URL = `${window.location.protocol}//${window.location.hostname}:8000`;

let toastTimer = null;
let detalleMetas = [];

document.addEventListener("DOMContentLoaded", () => {
    if (!exigirSesion()) return;

    prepararMeses();
    document.getElementById("filtroCodmes").addEventListener("change", () => cargarMetas(false));
    document.getElementById("filtroGrupo").addEventListener("change", () => cargarMetas(false));
    document.getElementById("filtroTipo").addEventListener("change", () => cargarMetas(false));
    document.getElementById("filtroVista").addEventListener("change", renderDetalleActual);
    document.getElementById("filtroEstado").addEventListener("change", renderDetalleActual);
    document.getElementById("formImportarMetasMibanco")?.addEventListener("submit", importarMetasMibanco);
    cargarMetas(false);
});

async function cargarMetas(mostrarToastOk = false) {
    const codmes = document.getElementById("filtroCodmes").value;
    const grupo = document.getElementById("filtroGrupo").value;
    const tipo = document.getElementById("filtroTipo").value;
    const params = new URLSearchParams({ codmes });

    if (grupo) {
        params.set("grupo_cartera", grupo);
    }

    if (tipo) {
        params.set("tipo_medicion", tipo);
    }

    try {
        const [resumenRes, detalleRes] = await Promise.all([
            fetch(`${BASE_URL}/metas/resumen?${params.toString()}`),
            fetch(`${BASE_URL}/metas/detalle?${params.toString()}`),
        ]);

        const resumen = await resumenRes.json();
        const detalle = await detalleRes.json();

        if (!resumenRes.ok) throw new Error(resumen.detail || "No se pudo cargar resumen.");
        if (!detalleRes.ok) throw new Error(detalle.detail || "No se pudo cargar detalle.");

        detalleMetas = detalle.data || [];
        renderResumen(resumen);
        renderDetalleActual();
        document.getElementById("ultimaActualizacion").innerText = formatearFechaHora(new Date().toISOString());

        if (mostrarToastOk) {
            mostrarToast("Seguimiento actualizado.", "success");
        }
    } catch (error) {
        console.error("ERROR METAS:", error);
        mostrarToast(error.message || "No se pudo cargar seguimiento de metas.", "error");
    }
}

async function importarMetasMibanco(event) {
    event.preventDefault();

    const codmes = document.getElementById("filtroCodmes").value;
    const archivo = document.getElementById("archivoMetasMibanco")?.files?.[0];
    const btn = document.getElementById("btnImportarMetasMibanco");
    const resultado = document.getElementById("resultadoImportarMetas");

    if (!codmes || !archivo) {
        mostrarToast("Selecciona mes y archivo de metas MiBanco.", "error");
        return;
    }

    const formData = new FormData();
    formData.set("codmes", codmes);
    formData.set("usuario", localStorage.getItem("dni") || localStorage.getItem("usuario") || "SIN_USUARIO");
    formData.set("archivo", archivo);

    try {
        if (btn) {
            btn.disabled = true;
            btn.textContent = "Importando...";
        }
        if (resultado) resultado.innerHTML = `<span>Procesando archivo...</span>`;

        const res = await fetch(`${BASE_URL}/metas/importar/mibanco`, {
            method: "POST",
            body: formData,
        });
        const json = await res.json();
        if (!res.ok) throw new Error(json.detail || "No se pudo importar metas MiBanco.");

        if (resultado) {
            resultado.innerHTML = `
                <span class="ok">Metas importadas: ${numero(json.filas_validas)} filas, total ${soles(json.total_meta)}.</span>
                ${(json.detalle_por_cartera || []).map(item => `
                    <b>${texto(item.cartera)}: ${soles(item.meta_mensual)}</b>
                `).join("")}
            `;
        }
        document.getElementById("archivoMetasMibanco").value = "";
        await cargarMetas(true);
    } catch (error) {
        if (resultado) resultado.innerHTML = `<span class="error">${texto(error.message)}</span>`;
        mostrarToast(error.message || "No se pudo importar metas MiBanco.", "error");
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.textContent = "Importar MiBanco";
        }
    }
}

function renderResumen(data) {
    const timing = data.timing || {};

    document.getElementById("kpiMetaTotal").innerText = soles(data.meta_total);
    document.getElementById("kpiAvance").innerText = soles(data.avance_actual);
    document.getElementById("kpiAvancePct").innerText = `${porcentaje(data.cumplimiento_global)} del total`;
    document.getElementById("kpiCumplimiento").innerText = porcentaje(data.cumplimiento_global);
    document.getElementById("kpiProyeccion").innerText = soles(data.proyeccion_cierre_total);
    document.getElementById("kpiCumplimientoEstimado").innerText = porcentaje(data.cumplimiento_estimado_global);
    document.getElementById("kpiBrechaProyectada").innerText = soles(data.brecha_proyectada_total);
    document.getElementById("kpiBrechaTexto").innerText = Number(data.brecha_proyectada_total || 0) <= 0
        ? "Meta cubierta"
        : "Por cubrir";

    document.getElementById("tDiaActual").innerText = numero(timing.dias_habiles_transcurridos);
    document.getElementById("tDiasMes").innerText = `de ${numero(timing.dias_habiles_mes)} dias habiles`;
    document.getElementById("tEsperado").innerText = porcentaje(timing.avance_esperado_pct);
    document.getElementById("tActual").innerText = porcentaje(timing.cumplimiento_actual_pct);
    document.getElementById("tEstimado").innerText = porcentaje(timing.cumplimiento_estimado_pct);
    document.getElementById("tDesvio").innerText = `${puntos(timing.desvio_pct)} p.p.`;
    document.getElementById("tDesvioTexto").innerText = Number(timing.desvio_pct || 0) >= 0
        ? "Por encima del esperado"
        : "Por debajo del esperado";
    document.getElementById("tNecesario").innerText = soles(timing.necesario_diario);
    document.getElementById("tRestantes").innerText = numero(timing.dias_habiles_restantes);
    document.getElementById("barEsperado").style.width = limitarPct(timing.avance_esperado_pct);
    document.getElementById("barActual").style.width = limitarPct(timing.cumplimiento_actual_pct);
    document.getElementById("barEstimado").style.width = limitarPct(timing.cumplimiento_estimado_pct);

    renderComparativoTipo(data.comparativo_tipo || []);
}

function renderComparativoTipo(data) {
    const contenedor = document.getElementById("comparativoTipo");
    contenedor.innerHTML = data.map(item => `
        <article class="tipo-card">
            <div class="tipo-card-head">
                <strong>${texto(item.tipo_medicion)}</strong>
                ${badgeEstado(item.estado)}
            </div>
            <div class="tipo-metrics">
                <span>Meta <b>${soles(item.meta)}</b></span>
                <span>Avance <b>${soles(item.avance_actual)}</b></span>
                <span>Proyeccion <b>${soles(item.proyeccion_cierre)}</b></span>
                <span>Brecha proyectada <b class="${Number(item.brecha_proyectada || 0) <= 0 ? "positivo" : "negativo"}">${brechaTexto(item.brecha_proyectada)}</b></span>
            </div>
            <div class="tipo-progress">
                <div>
                    <small>Actual ${porcentaje(item.cumplimiento_actual_pct)}</small>
                    <i><b style="width:${limitarPct(item.cumplimiento_actual_pct)}"></b></i>
                </div>
                <div>
                    <small>Estimado ${porcentaje(item.cumplimiento_estimado_pct)}</small>
                    <i><b class="estimado" style="width:${limitarPct(item.cumplimiento_estimado_pct)}"></b></i>
                </div>
            </div>
        </article>
    `).join("");
}

function renderDetalleActual() {
    const estado = normalizarEstado(document.getElementById("filtroEstado").value);
    const data = estado
        ? detalleMetas.filter(item => normalizarEstado(item.estado) === estado)
        : detalleMetas;
    renderDetalle(data);
}

function renderDetalle(data) {
    const tbody = document.getElementById("tablaMetas");
    const thead = document.getElementById("tablaMetasHead");
    const vista = document.getElementById("filtroVista").value || "ejecutiva";
    const columnas = vista === "detallada" ? columnasDetalladas() : columnasEjecutivas();

    thead.innerHTML = columnas.map(col => `<th>${col.label}</th>`).join("");
    tbody.innerHTML = data.length
        ? data.map(item => `<tr>${columnas.map(col => col.render(item)).join("")}</tr>`).join("")
        : `<tr><td colspan="${columnas.length}" class="sin-data">No hay metas principales para el filtro seleccionado.</td></tr>`;
}

function columnasEjecutivas() {
    return [
        col("Cartera", item => carteraCell(item)),
        col("Tipo medicion", item => texto(item.tipo_medicion)),
        col("Meta mensual", item => soles(item.meta_mensual), "text-right"),
        col("Avance actual", item => soles(item.avance_actual), "text-right"),
        col("Cumpl. actual", item => porcentaje(item.cumplimiento_pct), item => `text-center cumplimiento ${claseCumplimiento(item.estado)}`),
        col("Proyeccion cierre", item => soles(item.proyeccion_cierre), "text-right"),
        col("Cumpl. estimado", item => porcentaje(item.cumplimiento_estimado_pct), item => `text-center cumplimiento ${claseCumplimiento(item.estado)}`),
        col("Brecha proyectada", item => brechaTexto(item.brecha_proyectada), item => `text-right ${Number(item.brecha_proyectada || 0) <= 0 ? "positivo" : "negativo"}`),
        col("Estado", item => badgeEstado(item.estado), "text-center"),
        col("Ultimo corte", item => formatearFecha(item.ultimo_corte), "text-center"),
    ];
}

function columnasDetalladas() {
    return [
        col("Cartera", item => carteraCell(item)),
        col("Tipo medicion", item => texto(item.tipo_medicion)),
        col("Funcionario", item => texto(item.funcionario)),
        col("Cluster", item => texto(item.cluster_meta || item.segmentacion)),
        col("Ant. castigo", item => texto(item.ant_castigo)),
        col("Rango ticket", item => texto(item.ran_ticket)),
        col("Meta mensual", item => soles(item.meta_mensual), "text-right"),
        col("Avance actual", item => soles(item.avance_actual), "text-right"),
        col("Cumpl. actual", item => porcentaje(item.cumplimiento_pct), item => `text-center cumplimiento ${claseCumplimiento(item.estado)}`),
        col("Esperado a la fecha", item => soles(item.esperado_a_la_fecha), "text-right"),
        col("Desvio vs esperado", item => solesConSigno(item.desvio), item => `text-right ${Number(item.desvio || 0) < 0 ? "negativo" : "positivo"}`),
        col("Brecha actual", item => soles(item.brecha), "text-right"),
        col("Proyeccion cierre", item => soles(item.proyeccion_cierre), "text-right"),
        col("Cumpl. estimado", item => porcentaje(item.cumplimiento_estimado_pct), item => `text-center cumplimiento ${claseCumplimiento(item.estado)}`),
        col("Brecha proyectada", item => brechaTexto(item.brecha_proyectada), item => `text-right ${Number(item.brecha_proyectada || 0) <= 0 ? "positivo" : "negativo"}`),
        col("Necesario diario", item => soles(item.necesario_diario), "text-right"),
        col("Estado", item => badgeEstado(item.estado), "text-center"),
        col("Ultimo corte", item => formatearFecha(item.ultimo_corte), "text-center"),
    ];
}

function col(label, render, className = "") {
    return {
        label,
        render: (item) => {
            const css = typeof className === "function" ? className(item) : className;
            return `<td class="${css}">${render(item)}</td>`;
        },
    };
}

function carteraCell(item) {
    return `<b title="${texto(item.cartera)}">${texto(item.cartera)}</b>${item.tipo_producto ? `<small>${texto(item.tipo_producto)}</small>` : ""}`;
}

function prepararMeses() {
    const select = document.getElementById("filtroCodmes");
    const hoy = new Date();
    const opciones = [];

    for (let offset = -6; offset <= 1; offset++) {
        const fecha = new Date(hoy.getFullYear(), hoy.getMonth() + offset, 1);
        const codmes = `${fecha.getFullYear()}${String(fecha.getMonth() + 1).padStart(2, "0")}`;
        opciones.push(`<option value="${codmes}">${codmes} - ${nombreMes(fecha)}</option>`);
    }

    select.innerHTML = opciones.join("");
    select.value = `${hoy.getFullYear()}${String(hoy.getMonth() + 1).padStart(2, "0")}`;
}

function badgeEstado(estado) {
    const valor = texto(estado);
    const clase = claseCss(valor);
    return `<span class="badge estado-${clase}">${valor || "-"}</span>`;
}

function claseCumplimiento(estado) {
    return `cumplimiento-${claseCss(texto(estado))}`;
}

function claseCss(value) {
    return normalizarEstado(value).replace(/\s+/g, "-").toLowerCase();
}

function normalizarEstado(value) {
    return String(value || "")
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "")
        .trim()
        .toUpperCase();
}

function toggleSidebar() {
    document.body.classList.toggle("sidebar-hidden");
}

function irInicio() {
    window.location.href = "home.html";
}

function mostrarToast(mensaje, tipo = "info") {
    const toast = document.getElementById("toastMetas");
    toast.className = `toast toast-${tipo}`;
    toast.innerText = mensaje;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toast.classList.add("oculto"), 3200);
}

function texto(value) {
    if (value === null || value === undefined || value === "") return "-";
    return String(value);
}

function numero(value) {
    return Number(value || 0).toLocaleString("es-PE");
}

function dividir(a, b) {
    return Number(b || 0) ? Number(a || 0) / Number(b || 0) : 0;
}

function soles(value) {
    return Number(value || 0).toLocaleString("es-PE", {
        style: "currency",
        currency: "PEN",
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
    });
}

function solesConSigno(value) {
    const numeroValor = Number(value || 0);
    return `${numeroValor < 0 ? "-" : ""}${soles(Math.abs(numeroValor))}`;
}

function brechaTexto(value) {
    return Number(value || 0) <= 0 ? "Cubierta" : soles(value);
}

function porcentaje(value) {
    return `${(Number(value || 0) * 100).toFixed(2)}%`;
}

function puntos(value) {
    return (Number(value || 0) * 100).toFixed(2);
}

function limitarPct(value) {
    return `${Math.min(Math.max(Number(value || 0) * 100, 0), 100)}%`;
}

function formatearFecha(value) {
    if (!value) return "-";
    if (/^\d{4}-\d{2}-\d{2}/.test(String(value))) {
        const [year, month, day] = String(value).slice(0, 10).split("-");
        return `${day}/${month}/${year}`;
    }
    const fecha = new Date(value);
    return Number.isNaN(fecha.getTime()) ? "-" : fecha.toLocaleDateString("es-PE");
}

function formatearFechaHora(value) {
    const fecha = new Date(value);
    return fecha.toLocaleString("es-PE", {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
    });
}

function nombreMes(fecha) {
    return fecha.toLocaleDateString("es-PE", { month: "long", year: "numeric" }).toUpperCase();
}
