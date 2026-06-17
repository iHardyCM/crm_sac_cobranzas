document.addEventListener("DOMContentLoaded", () => {
    if (!exigirSesion()) return;

    pintarCabeceraHome();
    pintarModulos();
    pintarRoadmap();
    pintarMensajeHome();
});

function pintarCabeceraHome() {
    const agente = localStorage.getItem("agente") || "Usuario";
    const tipo = localStorage.getItem("tipo") || "Agente";
    const nombre = agente.includes(" - ") ? agente.split(" - ").slice(1).join(" - ") : agente;
    const carteras = typeof obtenerIdCarterasSesion === "function" ? obtenerIdCarterasSesion() : [];
    const inicioSesion = localStorage.getItem("session_started_at");

    document.getElementById("homeUsuario").innerText = agente;
    document.getElementById("homePerfil").innerText = tipo;
    document.getElementById("homeTitulo").innerText = `Hola, ${nombre}`;
    document.getElementById("homeFecha").innerText = new Date().toLocaleDateString("es-PE", {
        weekday: "long",
        day: "2-digit",
        month: "long",
        year: "numeric"
    });

    document.getElementById("homeDescripcion").innerText = obtenerDescripcionPerfil(tipo);

    const homeCarteras = document.getElementById("homeCarteras");
    const homeSesion = document.getElementById("homeSesion");

    if (homeCarteras) {
        homeCarteras.innerText = carteras.length ? carteras.join(", ") : "Sin cartera";
    }

    if (homeSesion) {
        homeSesion.innerText = inicioSesion
            ? `Activa desde ${new Date(inicioSesion).toLocaleTimeString("es-PE", { hour: "2-digit", minute: "2-digit" })}`
            : "Activa";
    }
}

function obtenerDescripcionPerfil(tipo) {
    const tipoNormalizado = normalizarTipoUsuario(tipo);

    if (puedeVerCorporativo(tipoNormalizado)) {
        return "Tienes acceso a la vista general de carteras, promesas del dia y reportes corporativos.";
    }

    if (tipoNormalizado === "SUPERVISOR") {
        return "Puedes revisar tu equipo, entrar a la vista de agentes y dar seguimiento a las promesas del dia.";
    }

    return "Puedes revisar tus compromisos, gestionar clientes y controlar el avance de tus promesas.";
}

function pintarModulos() {
    const tipo = normalizarTipoUsuario(localStorage.getItem("tipo"));
    const contenedor = document.getElementById("modulosHome");
    const modulos = obtenerModulosPorPerfil(tipo);
    const contador = document.getElementById("homeModulos");

    if (contador) {
        contador.innerText = String(modulos.length);
    }

    contenedor.innerHTML = modulos.map(modulo => `
        <article class="module-card ${modulo.destacado ? "destacado" : ""}">
            <div class="module-icon">${modulo.sigla}</div>
            <div>
                <h4>${modulo.titulo}</h4>
                <p>${modulo.descripcion}</p>
            </div>
            <button onclick="abrirModulo('${modulo.ruta}')">Abrir</button>
        </article>
    `).join("");
}

function obtenerModulosPorPerfil(tipo) {
    const modulos = [];
    const compartamos = esCarteraCompartamos();

    if (tipo !== "SUPERVISOR" && !puedeVerCorporativo(tipo)) {
        if (compartamos) {
            modulos.push({
                sigla: "CL",
                titulo: "Consulta Compartamos",
                descripcion: "Informacion diaria de clientes activos, deuda, capital y cuotas.",
                ruta: "compartamos.html",
                destacado: false
            });
        }

        modulos.push({
            sigla: "PD",
            titulo: "Mis compromisos",
            descripcion: "Consulta y gestiona los compromisos asignados para el mes.",
            ruta: "compromisos.html",
            destacado: true
        });
    }

    if (tipo === "SUPERVISOR") {
        const queryCarteras = typeof obtenerQueryCarterasSesion === "function"
            ? obtenerQueryCarterasSesion()
            : "";

        modulos.unshift(
            ...(compartamos ? [{
                sigla: "CL",
                titulo: "Consulta Compartamos",
                descripcion: "Informacion diaria de clientes activos, deuda, capital y cuotas.",
                ruta: "compartamos.html",
                destacado: false
            }] : []),
            {
                sigla: "SU",
                titulo: "Compromisos supervisor",
                descripcion: "Seguimiento de agentes, promesas por estado y reporte de cartera.",
                ruta: "supervisor.html",
                destacado: true
            },
            {
                sigla: "PH",
                titulo: "Promesas con vencimiento hoy",
                descripcion: "PDP de hoy filtradas por las carteras asignadas al supervisor.",
                ruta: queryCarteras
                    ? `corporativo_pdp_hoy.html?${queryCarteras}`
                    : "corporativo_pdp_hoy.html",
                destacado: false
            },
            {
                sigla: "GR",
                titulo: "Gestion y recupero",
                descripcion: "Seguimiento operativo de gestiones, PDP y recupero por corte horario.",
                ruta: "control_horario.html",
                destacado: false
            },
            {
                sigla: "IA",
                titulo: "Analisis IA",
                descripcion: "Feedback operativo de llamadas para seguimiento del supervisor.",
                ruta: "ia_feedback.html",
                destacado: false
            },
            {
                sigla: "PA",
                titulo: "Pagos del negocio",
                descripcion: "Validacion y publicacion de pagos normalizados para BI.",
                ruta: "pagos.html",
                destacado: false
            },
            {
                sigla: "CA",
                titulo: "Canales alternos",
                descripcion: "Carga y validacion de archivos para SMS, WAPI, Email, IVR y Bot.",
                ruta: "canales.html",
                destacado: false
            }
        );
    }

    if (puedeVerCorporativo(tipo)) {
        modulos.unshift(
            {
                sigla: "CO",
                titulo: "Panel corporativo",
                descripcion: "Resumen gerencial por cartera, filtros y reporte corporativo.",
                ruta: "corporativo.html",
                destacado: true
            },
            {
                sigla: "PH",
                titulo: "Promesas con vencimiento hoy",
                descripcion: "Vista global de PDP hoy para seguimiento por cartera y agente.",
                ruta: "corporativo_pdp_hoy.html",
                destacado: false
            },
            {
                sigla: "CL",
                titulo: "Consulta Compartamos",
                descripcion: "Informacion diaria de clientes activos, deuda, capital y cuotas.",
                ruta: "compartamos.html",
                destacado: false
            },
            {
                sigla: "PA",
                titulo: "Importacion de pagos",
                descripcion: "Validacion y publicacion de pagos normalizados para BI.",
                ruta: "pagos.html",
                destacado: false
            },
            {
                sigla: "IC",
                titulo: "Importacion de cartera",
                descripcion: "Analisis previo de archivos de asignacion contra tablas destino.",
                ruta: "importacion.html",
                destacado: false
            },
            {
                sigla: "CA",
                titulo: "Canales alternos",
                descripcion: "Carga y validacion de archivos para SMS, WAPI, Email, IVR y Bot.",
                ruta: "canales.html",
                destacado: false
            },
            {
                sigla: "ME",
                titulo: "Seguimiento de metas",
                descripcion: "Control de metas mensuales, avance, brecha y timing por cartera.",
                ruta: "metas.html",
                destacado: false
            },
            {
                sigla: "GR",
                titulo: "Gestion y recupero",
                descripcion: "Seguimiento operativo de gestiones, PDP y recupero por corte horario.",
                ruta: "control_horario.html",
                destacado: false
            },
            {
                sigla: "IA",
                titulo: "Analisis IA",
                descripcion: "Carga audios de llamadas y genera feedback operativo para supervision.",
                ruta: "ia_feedback.html",
                destacado: false
            },
            {
                sigla: "SI",
                titulo: "Susurro IA",
                descripcion: "Monitoreo y sugerencias en vivo para llamadas de cobranza.",
                ruta: "susurro_ia.html",
                destacado: false
            },
            {
                sigla: "SV",
                titulo: "Supervisores",
                descripcion: "Mantenimiento de carteras visibles por supervisor.",
                ruta: "admin_supervisores.html",
                destacado: false
            }
        );
    }

    return modulos;
}

function pintarRoadmap() {
    const items = [
        {
            sigla: "PR",
            titulo: "Proyectado",
            descripcion: "Monto esperado por periodo, cartera y fecha de compromiso."
        },
        {
            sigla: "ME",
            titulo: "Metas",
            descripcion: "Objetivos por cartera, supervisor y agente para medir cumplimiento real."
        },
        {
            sigla: "RK",
            titulo: "Ranking de agentes",
            descripcion: "Comparativo por recupero, cumplimiento, llamadas e intentos efectivos."
        },
        {
            sigla: "AL",
            titulo: "Alertas parametradas",
            descripcion: "Reglas gerenciales configurables para riesgo, caida y baja gestion."
        }
    ];

    document.getElementById("roadmapHome").innerHTML = items.map(item => `
        <article class="roadmap-card">
            <div>${item.sigla}</div>
            <h4>${item.titulo}</h4>
            <p>${item.descripcion}</p>
            <span>Proximamente</span>
        </article>
    `).join("");
}

function abrirModulo(ruta) {
    window.location.href = ruta;
}

function pintarMensajeHome() {
    const mensaje = sessionStorage.getItem("homeMensaje");
    const contenedor = document.getElementById("homeMensaje");

    if (!mensaje || !contenedor) return;

    contenedor.textContent = mensaje;
    contenedor.classList.remove("oculto");
    sessionStorage.removeItem("homeMensaje");
}
