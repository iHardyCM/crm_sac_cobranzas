/* ============================================================================
   Consumo de la API de IA — pantalla de Configuración (solo administración).

   De dónde salen los datos: GET /ia-feedback/consumo, que lee
   CRM_IA_CONSUMO_API (una fila por llamada a la API, con los tokens que la
   propia API informó) y multiplica por las tarifas de CRM_IA_TARIFA_MODELO.

   Si no hay tarifas cargadas se muestran tokens y se avisa: un precio inventado
   produciría un costo inventado.
   ============================================================================ */

const CONSUMO_BASE = `http://${window.location.hostname || "127.0.0.1"}:8000/ia-feedback`;
const consumoIa = { data: null, abierto: false, cargando: false };

document.addEventListener("DOMContentLoaded", async () => {
    if (typeof exigirSesion === "function" && !exigirSesion()) return;
    // No se consulta nada hasta que el backend confirme la sesion (GET /auth/me).
    if (typeof asegurarSesionBackend !== "function" || !(await asegurarSesionBackend())) return;
    cargarConsumoIa();
});

function mensajeConsumo(texto, tipo = "ok") {
    const el = document.getElementById("mensajeConsumo");
    if (!el) return;
    el.textContent = texto || "";
    el.className = `ia-message ${tipo}${texto ? "" : " oculto"}`;
}

async function cargarConsumoIa() {
    const dias = document.getElementById("periodoConsumo")?.value || "30";
    const contenedor = document.getElementById("contenidoConsumo");
    consumoIa.cargando = true;
    if (contenedor) {
        contenedor.innerHTML = `<section class="v2-panel"><div class="v2-loading">
            <span class="v2-spinner" aria-hidden="true"></span><strong>Leyendo el consumo de la API…</strong></div></section>`;
    }
    try {
        // El perfil ya no se envia: el backend lo toma de la sesion (JWT).
        const params = new URLSearchParams({ dias, limite: "500" });
        const response = await fetch(`${CONSUMO_BASE}/consumo?${params}`, {
            headers: agregarAuthorizationHeader(),
        });
        if (response.status === 401) {
            cerrarSesionPorBackend();
            return;
        }
        if (response.status === 403) {
            const detalle = await response.clone().json().catch(() => null);
            if (esRespuestaCambioClave(403, detalle)) {
                irACambioClaveObligatorio();
                return;
            }
            consumoIa.data = null;
            pintarVacioConsumo("Tu perfil no tiene acceso al consumo de la API",
                "Es información de costo del módulo, visible solo para administración.");
            return;
        }
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || "No se pudo cargar el consumo.");
        consumoIa.data = data;
        mensajeConsumo("");
        pintarConsumoIa();
    } catch (error) {
        consumoIa.data = null;
        pintarVacioConsumo("No se pudo cargar el consumo",
            `${error.message || error}. Si es la primera vez, ejecuta tools/sql/crear_consumo_ia.sql y reinicia la aplicación.`);
    } finally {
        consumoIa.cargando = false;
    }
}

function pintarVacioConsumo(titulo, detalle) {
    const el = document.getElementById("contenidoConsumo");
    if (el) el.innerHTML = `<section class="v2-panel"><div class="v2-empty"><strong>${escaparConsumo(titulo)}</strong><small>${escaparConsumo(detalle)}</small></div></section>`;
}

function escaparConsumo(valor) {
    return String(valor ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function numeroConsumo(v) {
    return Number(v || 0).toLocaleString("es-PE");
}

function tokensConsumo(v) {
    const n = Number(v || 0);
    return n >= 1000000 ? `${(n / 1000000).toFixed(2)} M` : n >= 1000 ? `${(n / 1000).toFixed(1)} k` : numeroConsumo(n);
}

function costoConsumo(v) {
    return v == null ? "—" : `$${Number(v).toFixed(Number(v) < 1 ? 4 : 2)}`;
}

function fechaConsumo(v) {
    if (!v) return "-";
    const f = new Date(v);
    return Number.isNaN(f.getTime()) ? String(v) : f.toLocaleString("es-PE", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
}

function minutosConsumo(fila) {
    return fila.duracion_segundos ? (Number(fila.duracion_segundos) / 60).toFixed(1) : "—";
}

function kpiConsumo(titulo, valor, detalle = "") {
    return `<article class="v2-kpi"><span>${escaparConsumo(titulo)}</span><strong>${escaparConsumo(valor)}</strong><small>${escaparConsumo(detalle)}</small></article>`;
}

function alternarDetalleConsumo() {
    consumoIa.abierto = !consumoIa.abierto;
    pintarConsumoIa();
}

function pintarConsumoIa() {
    const el = document.getElementById("contenidoConsumo");
    const d = consumoIa.data;
    if (!el || !d) return;
    const r = d.resumen || {};
    if (!r.llamadas_api) {
        pintarVacioConsumo("Todavía no hay consumo registrado",
            "Se registra desde el próximo audio que se analice: lo consumido antes no se puede reconstruir.");
        return;
    }
    const filas = d.evaluaciones || [];
    const visibles = consumoIa.abierto ? filas : filas.slice(0, 15);
    const maxDia = Math.max(...(d.dias_detalle || []).map(x => Number(x.tokens || 0)), 1);
    const porLlamada = r.evaluaciones ? (r.llamadas_api / r.evaluaciones).toFixed(1) : "—";

    el.innerHTML = `
        <div class="v2-kpi-row">
            ${kpiConsumo("Evaluaciones medidas", numeroConsumo(r.evaluaciones), `Últimos ${d.dias} días`)}
            ${kpiConsumo("Llamadas a la API", numeroConsumo(r.llamadas_api), `${porLlamada} por evaluación`)}
            ${kpiConsumo("Tokens", tokensConsumo(r.tokens), "Entrada + salida + audio")}
            ${kpiConsumo("Costo por evaluación", d.con_tarifas ? costoConsumo(r.costo_promedio) : "—",
                d.con_tarifas ? `Total ${costoConsumo(r.costo_total)} en el periodo` : "Carga las tarifas para ver el costo")}
        </div>

        ${d.con_tarifas ? "" : `<div class="v2-note"><strong>Faltan las tarifas.</strong>
            El módulo guarda los tokens que informa la API, pero no inventa precios. Carga los de tu proveedor en
            <code>CRM_IA_TARIFA_MODELO</code>; la plantilla está comentada en <code>tools/sql/crear_consumo_ia.sql</code>.</div>`}

        <section class="v2-panel">
            <header><h4>Por paso del análisis</h4><small>Dónde se van los tokens dentro de cada evaluación.</small></header>
            <div class="v2-table-wrap"><table class="v2-table">
                <thead><tr><th>Paso</th><th>Modelo</th><th>Llamadas</th><th>Evaluaciones</th><th>Entrada</th><th>Cacheado</th><th>Salida</th><th>Audio</th><th>Costo</th></tr></thead>
                <tbody>${(d.pasos || []).map(p => `<tr>
                    <td><b>${escaparConsumo(p.paso)}</b></td>
                    <td>${escaparConsumo(p.modelo)}</td>
                    <td>${numeroConsumo(p.llamadas)}</td>
                    <td>${numeroConsumo(p.evaluaciones)}</td>
                    <td>${tokensConsumo(p.tokens_input)}</td>
                    <td>${tokensConsumo(p.tokens_cacheados)}</td>
                    <td>${tokensConsumo(p.tokens_output)}</td>
                    <td>${tokensConsumo(p.tokens_audio)}</td>
                    <td><b>${d.con_tarifas ? costoConsumo(p.costo) : "—"}</b></td>
                </tr>`).join("")}</tbody>
            </table></div>
        </section>

        <section class="v2-panel">
            <header><h4>Por día</h4><small>${d.con_tarifas ? "Costo del día" : "Tokens del día"}</small></header>
            <div class="v2-bars">${(d.dias_detalle || []).map(dia => `
                <div class="v2-bar-row">
                    <div><b>${escaparConsumo(String(dia.dia).slice(0, 10))}</b>
                        <small>${numeroConsumo(dia.evaluaciones)} evaluación(es) · ${numeroConsumo(dia.llamadas)} llamadas · ${tokensConsumo(dia.tokens)}</small></div>
                    <span class="v2-bar info"><i style="width:${Math.max(2, (Number(dia.tokens) / maxDia) * 100)}%"></i></span>
                    <strong>${d.con_tarifas ? costoConsumo(dia.costo) : tokensConsumo(dia.tokens)}</strong>
                </div>`).join("")}</div>
        </section>

        <section class="v2-panel">
            <header><h4>Por evaluación · ${numeroConsumo(filas.length)}</h4>
            <small>Cada fila es un audio evaluado, con lo que consumieron todas las llamadas a la API que originó.</small></header>
            <div class="v2-table-wrap"><table class="v2-table">
                <thead><tr><th>Evaluación</th><th>Cartera</th><th>Agente</th><th>Minutos</th><th>Llamadas</th><th>Entrada</th><th>Salida</th><th>Audio</th><th>Costo</th><th>Última llamada</th></tr></thead>
                <tbody>${visibles.map(f => `<tr>
                    <td><b>${f.id_feedback ? `#${f.id_feedback}` : "Sin evaluación"}</b></td>
                    <td>${escaparConsumo(f.cartera || "-")}</td>
                    <td>${escaparConsumo(f.agente || "Sin agente")}</td>
                    <td>${minutosConsumo(f)}</td>
                    <td>${numeroConsumo(f.llamadas_api)}</td>
                    <td>${tokensConsumo(f.tokens_input)}</td>
                    <td>${tokensConsumo(f.tokens_output)}</td>
                    <td>${tokensConsumo(f.tokens_audio)}</td>
                    <td><b>${d.con_tarifas ? costoConsumo(f.costo) : "—"}</b></td>
                    <td>${escaparConsumo(fechaConsumo(f.ultima))}</td>
                </tr>`).join("")}</tbody>
            </table></div>
            ${filas.length > 15 ? `<div class="v2-center"><button class="btn-light btn-small" type="button" onclick="alternarDetalleConsumo()">
                ${consumoIa.abierto ? "Ver solo las 15 últimas" : `Ver las ${filas.length} evaluaciones`}</button></div>` : ""}
        </section>`;
}

function exportarConsumoCsv() {
    const d = consumoIa.data;
    if (!d || !(d.evaluaciones || []).length) {
        mensajeConsumo("No hay consumo para exportar en este periodo.", "error");
        return;
    }
    const cabecera = ["id_feedback", "cartera", "agente", "minutos_audio", "llamadas_api",
                      "tokens_entrada", "tokens_cacheados", "tokens_salida", "tokens_audio", "costo", "ultima_llamada"];
    const filas = d.evaluaciones.map(f => [
        f.id_feedback ?? "", f.cartera ?? "", f.agente ?? "", minutosConsumo(f), f.llamadas_api ?? 0,
        f.tokens_input ?? 0, f.tokens_cacheados ?? 0, f.tokens_output ?? 0, f.tokens_audio ?? 0,
        d.con_tarifas && f.costo != null ? Number(f.costo).toFixed(6) : "", f.ultima ?? "",
    ]);
    const csv = [cabecera, ...filas]
        .map(fila => fila.map(v => `"${String(v).replace(/"/g, '""')}"`).join(";"))
        .join("\n");
    const url = URL.createObjectURL(new Blob([`﻿${csv}`], { type: "text/csv;charset=utf-8;" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = `consumo_ia_${new Date().toISOString().slice(0, 10)}.csv`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 2000);
    mensajeConsumo(`Exportadas ${filas.length} evaluaciones.`, "ok");
}
