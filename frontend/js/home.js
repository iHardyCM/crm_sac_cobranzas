// Home es la puerta de sesion del CRM: nada del usuario se pinta hasta que el
// backend confirma la sesion (GET /auth/me). Con 401 vuelve al login, con cambio
// obligatorio va a cambiar_clave.html y con error tecnico queda bloqueada.
// Nombre, perfil y carteras salen de la respuesta del backend, no de localStorage.
document.addEventListener("DOMContentLoaded", iniciarHome);

// Volver con "Atras" puede mostrar la pagina desde la cache del navegador sin
// ejecutar nada: en ese caso se recarga para revalidar la sesion.
window.addEventListener("pageshow", event => {
    if (event.persisted) window.location.reload();
});

async function iniciarHome() {
    if (typeof asegurarSesionBackend !== "function") {
        console.error("session.js desactualizado: falta asegurarSesionBackend().");
        return;
    }

    const usuario = await asegurarSesionBackend();
    if (!usuario) return;

    pintarCabeceraHome(usuario);
    pintarModulos(usuario);
    pintarRoadmap();
    pintarMensajeHome();
    document.body.classList.remove("home-validando-sesion");
}

function pintarCabeceraHome(usuario) {
    const agente = usuario.agente || usuario.dni || "Usuario";
    const tipo = usuario.tipo || "Agente";
    const nombre = agente.includes(" - ") ? agente.split(" - ").slice(1).join(" - ") : agente;
    const carteras = Array.isArray(usuario.idcarteras)
        ? usuario.idcarteras.filter(Boolean).map(String)
        : [];
    const inicioSesion = localStorage.getItem("session_started_at");

    document.getElementById("homeUsuario").innerText = agente;
    const avatar = document.getElementById("homeAvatar");
    if (avatar) avatar.textContent = (nombre.trim().charAt(0) || "U").toUpperCase();
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

    if (esSupervisor(tipoNormalizado)) {
        return "Puedes revisar tu equipo, entrar a la vista de agentes y dar seguimiento a las promesas del dia.";
    }

    if (esUsuarioMonitorCalidad(tipoNormalizado)) {
        return "Puedes cargar llamadas, revisar evaluaciones y apoyar la calibración del análisis IA.";
    }

    return "Puedes revisar tus compromisos, gestionar clientes y controlar el avance de tus promesas.";
}

function pintarModulos(usuario) {
    const tipo = normalizarTipoUsuario(usuario.tipo);
    const contenedor = document.getElementById("modulosHome");
    const permisos = usuario.permisos_vistas || {};
    const clavesPorRuta = {
        "compartamos.html": "clientes",
        "compromisos.html": "compromisos",
        "supervisor.html": "gestiones",
        "telefonos.html": "telefonos",
        "ia_feedback.html": "ia_feedback"
    };
    const modulos = obtenerModulosPorPerfil(tipo).filter(modulo => {
        const clave = clavesPorRuta[modulo.ruta.split("?")[0]];
        return !clave || permisos[clave] !== false;
    });
    const extras = [
        ["clientes", "compartamos.html", "CL", "Radar Compartamos", "Consulta de clientes de tus carteras."],
        ["compromisos", "compromisos.html", "PD", "Mis compromisos", "Compromisos propios y asignados."],
        ["gestiones", "supervisor.html", "SU", "Compromisos del equipo", "Seguimiento del equipo en tus carteras."],
        ["telefonos", "telefonos.html", "TF", "Validación de Teléfonos", "Consulta de teléfonos de tus carteras."],
        ["ia_feedback", "ia_feedback.html", "IA", "Análisis IA", "Feedback operativo de llamadas."]
    ];
    for (const [clave, ruta, sigla, titulo, descripcion] of extras) {
        if (permisos[clave] === true && !modulos.some(modulo => modulo.ruta.split("?")[0] === ruta)) {
            modulos.push({ sigla, titulo, descripcion, ruta, destacado: false });
        }
    }
    // Un mismo destino no se muestra dos veces.
    const vistos = new Set();
    modulosMostrados = modulos.filter(modulo => {
        if (vistos.has(modulo.ruta)) return false;
        vistos.add(modulo.ruta);
        return true;
    });

    const contador = document.getElementById("homeModulos");

    if (contador) {
        contador.innerText = String(modulosMostrados.length);
    }

    renderizarModulos(contenedor, "");

    const buscador = document.getElementById("homeBuscar");
    if (buscador && typeof buscador.addEventListener === "function") {
        buscador.addEventListener("input", () => renderizarModulos(contenedor, buscador.value));
    }
}

// ---------------------------------------------------------------------------
// Presentacion de los modulos: agrupados por area, con icono y buscador.
// La lista de modulos por perfil (obtenerModulosPorPerfil) no cambia; aqui solo
// se decide como se muestra.
// ---------------------------------------------------------------------------
let modulosMostrados = [];

const GRUPOS_HOME = [
    { clave: "operacion", titulo: "Operación y seguimiento", tono: "" },
    { clave: "calidad", titulo: "Calidad e IA", tono: "tono-calidad" },
    { clave: "datos", titulo: "Cargas y documentos", tono: "tono-datos" },
    { clave: "admin", titulo: "Administración", tono: "tono-admin" }
];

const GRUPO_POR_PAGINA = {
    "ia_feedback.html": "calidad",
    "susurro_ia.html": "calidad",
    "consumo_ia.html": "calidad",
    "importacion.html": "datos",
    "pagos.html": "datos",
    "canales.html": "datos",
    "documentos.html": "datos",
    "admin_supervisores.html": "admin",
    "admin_accesos.html": "admin"
};

// Trazos de 24x24 (estilo linea). Si una pagina no tiene icono se muestra la sigla.
const ICONOS_HOME = {
    "corporativo.html": '<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>',
    "metas.html": '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="4.5"/><path d="M12 12l6-6"/>',
    "compromisos.html": '<rect x="5" y="4" width="14" height="17" rx="2"/><path d="M9 4h6v3H9zM9 14l2 2 4-4"/>',
    "supervisor.html": '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20c0-3.6 2.9-6 6.5-6s6.5 2.4 6.5 6M16 5.2a3.5 3.5 0 010 5.6M18 14.4c2.2.7 3.5 2.6 3.5 5.6"/>',
    "corporativo_pdp_hoy.html": '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4M9 15l2 2 4-4"/>',
    "control_horario.html": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    "compartamos.html": '<circle cx="11" cy="11" r="7"/><path d="M20 20l-4-4"/>',
    "telefonos.html": '<path d="M5 4h4l2 5-2.5 1.5a11 11 0 005 5L15 13l5 2v4a2 2 0 01-2 2A16 16 0 013 6a2 2 0 012-2z"/>',
    "ia_feedback.html": '<rect x="4" y="8" width="16" height="12" rx="3"/><path d="M12 4v4M9 13v1M15 13v1M9 17h6"/>',
    "susurro_ia.html": '<rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0014 0M12 18v3"/>',
    "consumo_ia.html": '<ellipse cx="12" cy="6" rx="8" ry="3"/><path d="M4 6v6c0 1.7 3.6 3 8 3s8-1.3 8-3V6M4 12v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6"/>',
    "importacion.html": '<path d="M12 16V4M7 9l5-5 5 5M4 20h16"/>',
    "pagos.html": '<rect x="3" y="6" width="18" height="13" rx="2"/><path d="M3 10h18M16 15h2"/>',
    "canales.html": '<path d="M3 11v3l12 5V6L3 11zM15 9a4 4 0 010 6M6 14l1.5 6"/>',
    "documentos.html": '<path d="M14 3H7a2 2 0 00-2 2v14a2 2 0 002 2h10a2 2 0 002-2V8l-5-5zM14 3v5h5M9 13h6M9 17h6"/>',
    "admin_supervisores.html": '<circle cx="12" cy="8" r="3.5"/><path d="M5 20c0-3.6 3.1-6 7-6s7 2.4 7 6"/>',
    "admin_accesos.html": '<circle cx="8" cy="15" r="4"/><path d="M11 12l9-9M16 7l3 3"/>'
};

function paginaDeRuta(ruta) {
    return String(ruta || "").split("?")[0].split("/").pop();
}

function escaparHtmlHome(texto) {
    return String(texto ?? "").replace(/[&<>"']/g, c => (
        { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
    ));
}

function normalizarBusquedaHome(texto) {
    return String(texto || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().trim();
}

function tarjetaModuloHome(modulo) {
    const pagina = paginaDeRuta(modulo.ruta);
    const trazo = ICONOS_HOME[pagina];
    const icono = trazo
        ? `<svg viewBox="0 0 24 24" aria-hidden="true">${trazo}</svg>`
        : escaparHtmlHome(modulo.sigla);

    return `
        <a class="module-card ${modulo.destacado ? "destacado" : ""}" href="${escaparHtmlHome(modulo.ruta)}">
            <span class="module-icon">${icono}</span>
            <span class="module-text">
                <h4>${escaparHtmlHome(modulo.titulo)}</h4>
                <p>${escaparHtmlHome(modulo.descripcion)}</p>
            </span>
            <svg class="module-arrow" viewBox="0 0 24 24" aria-hidden="true"><path d="M9 6l6 6-6 6"/></svg>
        </a>`;
}

function renderizarModulos(contenedor, filtro) {
    const consulta = normalizarBusquedaHome(filtro);
    const visibles = consulta
        ? modulosMostrados.filter(m => normalizarBusquedaHome(`${m.titulo} ${m.descripcion}`).includes(consulta))
        : modulosMostrados;

    if (!visibles.length) {
        contenedor.innerHTML = `<p class="modulos-vacio">${consulta
            ? "Ningún módulo coincide con tu búsqueda."
            : "Tu perfil no tiene módulos habilitados por ahora."}</p>`;
        return;
    }

    // Con pocos modulos los encabezados de area sobran: una sola rejilla.
    if (modulosMostrados.length <= 6) {
        contenedor.innerHTML = `<div class="module-grid">${visibles.map(tarjetaModuloHome).join("")}</div>`;
        return;
    }

    contenedor.innerHTML = GRUPOS_HOME.map(grupo => {
        const delGrupo = visibles.filter(m => (GRUPO_POR_PAGINA[paginaDeRuta(m.ruta)] || "operacion") === grupo.clave)
            .sort((a, b) => Number(!!b.destacado) - Number(!!a.destacado));
        if (!delGrupo.length) return "";
        return `
            <section class="module-group ${grupo.tono}">
                <h3 class="group-head">${grupo.titulo} <b>${delGrupo.length}</b></h3>
                <div class="module-grid">${delGrupo.map(tarjetaModuloHome).join("")}</div>
            </section>`;
    }).join("");
}

function obtenerModulosPorPerfil(tipo) {
    const modulos = [];
    const compartamos = esCarteraCompartamos();

    if (esUsuarioMonitorCalidad(tipo)) {
        return [{
            sigla: "IA",
            titulo: "Analisis IA",
            descripcion: "Carga audios, revisa resultados y realiza pruebas de calidad del análisis.",
            ruta: "ia_feedback.html",
            destacado: true
        }];
    }

    if (!esSupervisor(tipo) && !puedeVerCorporativo(tipo)) {
        if (compartamos) {
            modulos.push({
                sigla: "CL",
                titulo: "Radar Compartamos",
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

        modulos.push({
            sigla: "TF",
            titulo: "Validación de Teléfonos",
            descripcion: "Consulta teléfonos activos por DNI, ID Cliente o número de teléfono.",
            ruta: "telefonos.html",
            destacado: false
        });

    }

    if (esSupervisor(tipo)) {
        const queryCarteras = typeof obtenerQueryCarterasSesion === "function"
            ? obtenerQueryCarterasSesion()
            : "";

        modulos.unshift(
            ...(compartamos ? [{
                sigla: "CL",
                titulo: "Radar Compartamos",
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
                sigla: "TF",
                titulo: "Validación de Teléfonos",
                descripcion: "Consulta teléfonos activos y valida prioridad, Osiptel, timbrado y origen.",
                ruta: "telefonos.html",
                destacado: false
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
                sigla: "IC",
                titulo: "Importacion de cartera",
                descripcion: "Analisis previo y carga de archivos de asignacion al CRM.",
                ruta: "importacion.html",
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
                sigla: "PD",
                titulo: "Compromisos",
                descripcion: "Consulta y gestiona compromisos del mes desde la vista operativa.",
                ruta: "compromisos.html",
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
                titulo: "Radar Compartamos",
                descripcion: "Informacion diaria de clientes activos, deuda, capital y cuotas.",
                ruta: "compartamos.html",
                destacado: false
            },
            {
                sigla: "TF",
                titulo: "Validación de Teléfonos",
                descripcion: "Consulta teléfonos activos y valida prioridad, Osiptel, timbrado y origen.",
                ruta: "telefonos.html",
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

    // Consumo de la API de IA: es informacion de costo del modulo, solo administracion.
    if (String(tipo || "").trim().toUpperCase() === "ADMINISTRADOR") {
        modulos.push({
            sigla: "CI",
            titulo: "Consumo de IA",
            descripcion: "Tokens y costo de la API por cada audio evaluado.",
            ruta: "consumo_ia.html",
            destacado: false
        });
        // La seguridad real esta en el backend: /admin-accesos responde 403 si no es administrador.
        modulos.push({
            sigla: "AC",
            titulo: "Usuarios y accesos",
            descripcion: "Gestiona cuentas y permisos individuales de vistas.",
            ruta: "admin_accesos.html",
            destacado: false
        });
    }

    if (puedeAccederDocumentos(tipo)) {
        modulos.unshift({
            sigla: "DO",
            titulo: "Documentos automatizados",
            descripcion: "Genera documentos según la entidad, cartera y condiciones de pago seleccionadas.",
            ruta: "documentos.html",
            destacado: false
        });
    }

    return modulos;
}

function puedeAccederDocumentos(tipo) {
    const tipoNormalizado = normalizarTipoUsuario(tipo || localStorage.getItem("tipo"));
    return esSupervisor(tipoNormalizado)
        || ["ADMINISTRADOR", "JEFE DE CARTERA", "JEFE DE CARTERAS", "JEFE CARTERA"].includes(tipoNormalizado);
}

function esUsuarioMonitorCalidad(tipo) {
    const tipoNormalizado = normalizarTipoUsuario(tipo || localStorage.getItem("tipo"));
    return tipoNormalizado.includes("MONITOR") && tipoNormalizado.includes("CALIDAD");
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
