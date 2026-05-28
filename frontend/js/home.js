document.addEventListener("DOMContentLoaded", () => {
    if (!exigirSesion()) return;

    pintarCabeceraHome();
    pintarModulos();
    pintarRoadmap();
});

function pintarCabeceraHome() {
    const agente = localStorage.getItem("agente") || "Usuario";
    const tipo = localStorage.getItem("tipo") || "Agente";
    const nombre = agente.includes(" - ") ? agente.split(" - ").slice(1).join(" - ") : agente;

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
