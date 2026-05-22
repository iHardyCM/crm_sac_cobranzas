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

    if (tipo !== "SUPERVISOR" && !puedeVerCorporativo(tipo)) {
        modulos.push({
            sigla: "PD",
            titulo: "Mis compromisos",
            descripcion: "Consulta y gestiona los compromisos asignados para el mes.",
            ruta: "compromisos.html",
            destacado: true
        });
    }

    if (tipo === "SUPERVISOR") {
        const idcartera = localStorage.getItem("idcartera");

        modulos.unshift(
            {
                sigla: "SU",
                titulo: "Panel supervisor",
                descripcion: "Seguimiento de agentes, promesas por estado y reporte de cartera.",
                ruta: "supervisor.html",
                destacado: true
            },
            {
                sigla: "PH",
                titulo: "Promesas con vencimiento hoy",
                descripcion: "PDP de hoy filtradas por la cartera asignada al supervisor.",
                ruta: idcartera
                    ? `corporativo_pdp_hoy.html?idcartera=${encodeURIComponent(idcartera)}`
                    : "corporativo_pdp_hoy.html",
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
