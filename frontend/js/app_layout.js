// app_layout.js
(function () {
    const MODULES = {
        "corporativo.html": {
            key: "corporativo",
            title: "Panel Corporativo",
            subtitle: "Vista general de compromisos por cartera / campaña"
        },
        "corporativo_pdp_hoy.html": {
            key: "pdp_hoy",
            title: "Promesas Hoy",
            subtitle: "Promesas con vencimiento hoy por cartera y agente"
        },
        "pagos.html": {
            key: "pagos",
            title: "Pagos del Negocio",
            subtitle: "Carga, validación y publicación de pagos para BI"
        },
        "canales.html": {
            key: "canales",
            title: "Canales Alternos",
            subtitle: "Importación y validación de archivos por canal"
        },
        "metas.html": {
            key: "metas",
            title: "Seguimiento de Metas",
            subtitle: "Avance de metas mensuales por cartera"
        },
        "control_horario.html": {
            key: "control_horario",
            title: "Gestion y Recupero",
            subtitle: "Seguimiento operativo en tiempo real"
        },
        "control_matriz.html": {
            key: "control_horario",
            title: "Matriz mensual",
            subtitle: "Generacion, recaudacion y proyectado por agente"
        },
        "importacion.html": {
            key: "importacion",
            title: "Importacion de Cartera",
            subtitle: "Analisis previo de archivos de asignacion"
        },
        "admin_supervisores.html": {
            key: "supervisores_admin",
            title: "Mantenimiento de Supervisores",
            subtitle: "Asignacion de carteras por supervisor"
        },
        "admin_metas_agentes.html": {
            key: "metas_agentes_admin",
            title: "Metas por Agente",
            subtitle: "Configuracion de metas mensuales individuales"
        },
        "consumo_ia.html": {
            key: "consumo_ia_admin",
            title: "Consumo de IA",
            subtitle: "Tokens y costo de la API por audio evaluado"
        },
        "admin_accesos.html": {
            key: "accesos_admin",
            title: "Usuarios y accesos",
            subtitle: "Cuentas y permisos individuales de vistas"
        },
        "admin_pautas_evaluacion.html": {
            key: "pautas_evaluacion_admin",
            title: "Pautas de Evaluación",
            subtitle: "Versiones y criterios aplicables por cartera"
        },
        "ritmo_meta.html": {
            key: "ritmo_meta",
            title: "Ritmo de Meta",
            subtitle: "Meta diaria, brecha y semaforo de avance"
        },
        "compromisos.html": {
            key: "compromisos",
            title: "Compromisos",
            subtitle: "Gestión de promesas y clientes asignados"
        },
        "supervisor.html": {
            key: "gestiones",
            title: "Compromisos",
            subtitle: "Seguimiento de compromisos del equipo supervisor"
        },
        "compartamos.html": {
            key: "clientes",
            title: "Radar Compartamos",
            subtitle: "Informacion diaria de clientes activos, deuda, capital y cuotas"
        },
        "ia_feedback.html": {
            key: "ia_feedback",
            title: "Analisis IA",
            subtitle: "Feedback operativo de llamadas para supervision"
        },
        "susurro_ia.html": {
            key: "susurro_ia",
            title: "Susurro IA",
            subtitle: "Asistencia en vivo para llamadas de cobranza"
        },
        "telefonos.html": {
            key: "telefonos",
            title: "Validación de Teléfonos",
            subtitle: "Consulta operativa de teléfonos activos por cliente"
        },
        "documentos.html": {
            key: "documentos",
            title: "Documentos Automatizados",
            subtitle: "Generacion de cartas con datos de Compartamos"
        },
    };

    const FOCUS_MODULES = new Set([
        "corporativo",
        "pdp_hoy",
        "pagos",
        "compromisos",
        "gestiones",
        "telefonos",
        "control_horario"
    ]);

    const NAV_GROUPS = [
        {
            title: "General",
            items: [
                { key: "inicio", label: "Inicio", href: "home.html", icon: iconHome() }
            ]
        },
        {
            title: "Operación",
            items: [
                { key: "clientes", label: "Radar Compartamos", href: "compartamos.html", icon: iconRadar() },
                { key: "compromisos", label: "Mis compromisos", href: "compromisos.html", icon: iconCompromisos() },
                { key: "gestiones", label: "Compromisos del equipo", href: "supervisor.html", icon: iconUsers() },
                { key: "ritmo_meta", label: "Ritmo Meta", href: "ritmo_meta.html", icon: iconMetas() },
                { key: "pdp_hoy", label: "Promesas Hoy", href: getPdpHoyHref(), icon: iconPdpHoy() },
                { key: "telefonos", label: "Validación de Teléfonos", href: "telefonos.html", icon: iconPhone() },
                { key: "documentos", label: "Documentos", href: "documentos.html", icon: iconDocumento() },
            ]
        },
        {
            title: "Control Gerencial",
            items: [
                { key: "corporativo", label: "Panel Corporativo", href: "corporativo.html", icon: iconBars() },
                { key: "metas", label: "Seguimiento de Metas", href: "metas.html", icon: iconMetas() },
                { key: "control_horario", label: "Gestion y Recupero", href: "control_horario.html", icon: iconClock() }
            ]
        },
        {
            title: "Importaciones",
            items: [
                { key: "importacion", label: "Importacion de Cartera", href: "importacion.html", icon: iconUpload() },
                { key: "pagos", label: "Pagos del Negocio", href: "pagos.html", icon: iconWallet() },
                { key: "canales", label: "Canales Alternos", href: "canales.html", icon: iconMegaphone() }
            ]
        },
        {
            title: "Análisis",
            items: [
                { key: "ia_feedback", label: "Analisis IA", href: "ia_feedback.html", icon: iconRobot() },
                { key: "susurro_ia", label: "Susurro IA", href: "susurro_ia.html", icon: iconMic() },
                { key: "reportes", label: "Reportes", disabled: true, icon: iconChart() }
            ]
        },
        {
            title: "Configuración",
            items: [
                { key: "admin", label: "Administración", disabled: true, icon: iconSettings() }
            ]
        }
    ];

    NAV_GROUPS[NAV_GROUPS.length - 1].items.unshift({
        key: "supervisores_admin",
        label: "Supervisores",
        href: "admin_supervisores.html",
        icon: iconPerson()
    });

    NAV_GROUPS[NAV_GROUPS.length - 1].items.unshift({
        key: "metas_agentes_admin",
        label: "Metas Agentes",
        href: "admin_metas_agentes.html",
        icon: iconMetas()
    });

    NAV_GROUPS[NAV_GROUPS.length - 1].items.unshift({
        key: "consumo_ia_admin",
        label: "Consumo de IA",
        href: "consumo_ia.html",
        icon: iconCoins()
    });

    NAV_GROUPS[NAV_GROUPS.length - 1].items.unshift({
        key: "accesos_admin",
        label: "Usuarios",
        href: "admin_accesos.html",
        icon: iconKey()
    });

    NAV_GROUPS[NAV_GROUPS.length - 1].items.unshift({
        key: "pautas_evaluacion_admin",
        label: "Pautas de Evaluación",
        href: "admin_pautas_evaluacion.html",
        icon: iconClipboard()
    });


    const CLAVE_PERMISOS_CACHE = "crmPermisosVistasCache";

    // Pinta el menú y la cabecera de inmediato con lo último que se conoce de la
    // sesión y valida contra el backend en segundo plano. Si la validación cambia
    // permisos o datos del usuario, se vuelve a pintar; si la sesión no es válida,
    // asegurarSesionBackend() redirige al login como antes.
    // Los datos de cada página siguen esperando a asegurarSesionBackend().
    async function initCrmLayout() {
        const page = currentPage();
        const meta = MODULES[page];
        if (!meta) {
            document.documentElement.classList.remove("crm-boot");
            return;
        }

        try {
            restaurarPermisosCache();
            montarCrmLayout(meta);
        } finally {
            document.documentElement.classList.remove("crm-boot");
        }

        if (typeof asegurarSesionBackend === "function" && !(await asegurarSesionBackend())) return;

        guardarPermisosCache();

        if (!puedeAccederModulo(meta.key)) {
            alert("No tienes acceso a este módulo con tu perfil actual.");
            window.location.href = "home.html";
            return;
        }

        refrescarCrmLayout(meta);
    }

    function montarCrmLayout(meta) {
        // Sin animacion en el primer montaje: el contenido no debe "deslizarse"
        // hacia su lugar al abrir la pagina. Se reactiva al terminar el primer pintado.
        document.body.classList.add("crm-sin-transicion");
        requestAnimationFrame(() => requestAnimationFrame(() => document.body.classList.remove("crm-sin-transicion")));
        document.body.classList.add("crm-shell");

        if (localStorage.getItem("crmSidebarCollapsedV2") !== "0") {
            document.body.classList.add("crm-sidebar-collapsed");
        }

        document.body.insertAdjacentHTML("afterbegin", renderTopbar(meta));
        document.body.insertAdjacentHTML("afterbegin", renderSidebar(meta.key));
        asegurarCrmDialog();
        document.addEventListener("keydown", manejarAtajoFoco);
    }

    function refrescarCrmLayout(meta) {
        reemplazarSiCambio(".crm-sidebar", renderSidebar(meta.key));
        reemplazarSiCambio(".crm-topbar", renderTopbar(meta));
    }

    function reemplazarSiCambio(selector, html) {
        const actual = document.querySelector(selector);
        if (!actual) return;
        const plantilla = document.createElement("template");
        plantilla.innerHTML = html.trim();
        const nuevo = plantilla.content.firstElementChild;
        if (nuevo && nuevo.outerHTML !== actual.outerHTML) actual.replaceWith(nuevo);
    }

    // Permisos de vistas de la última validación: evitan que el menú cambie al
    // llegar la respuesta. La validación del backend siempre manda; el logout
    // borra el localStorage y con él esta copia.
    function restaurarPermisosCache() {
        if (window.crmPermisosVistas) return;
        try {
            const guardado = JSON.parse(localStorage.getItem(CLAVE_PERMISOS_CACHE) || "null");
            if (guardado && typeof guardado === "object") window.crmPermisosVistas = guardado;
        } catch (error) {
            // sin copia local: el menú se calcula por perfil hasta validar
        }
    }

    function guardarPermisosCache() {
        try {
            if (window.crmPermisosVistas) {
                localStorage.setItem(CLAVE_PERMISOS_CACHE, JSON.stringify(window.crmPermisosVistas));
            } else {
                localStorage.removeItem(CLAVE_PERMISOS_CACHE);
            }
        } catch (error) {
            // almacenamiento no disponible: no pasa nada
        }
    }

    function asegurarCrmDialog() {
        if (document.getElementById("crmDialogOverlay")) return;

        document.body.insertAdjacentHTML("beforeend", `
            <div id="crmDialogOverlay" class="crm-dialog-overlay oculto" role="presentation">
                <section class="crm-dialog" role="dialog" aria-modal="true" aria-labelledby="crmDialogTitle">
                    <div class="crm-dialog-icon" id="crmDialogIcon">!</div>
                    <div class="crm-dialog-content">
                        <h3 id="crmDialogTitle">Confirmar accion</h3>
                        <p id="crmDialogMessage">Confirma para continuar.</p>
                    </div>
                    <div class="crm-dialog-actions">
                        <button id="crmDialogCancel" class="crm-dialog-btn secondary" type="button">Cancelar</button>
                        <button id="crmDialogAccept" class="crm-dialog-btn primary" type="button">Aceptar</button>
                    </div>
                </section>
            </div>
        `);
    }

    window.crmConfirm = function ({
        title = "Confirmar accion",
        message = "Confirma para continuar.",
        acceptText = "Aceptar",
        cancelText = "Cancelar",
        tone = "primary"
    } = {}) {
        asegurarCrmDialog();

        return new Promise(resolve => {
            const overlay = document.getElementById("crmDialogOverlay");
            const titleEl = document.getElementById("crmDialogTitle");
            const messageEl = document.getElementById("crmDialogMessage");
            const accept = document.getElementById("crmDialogAccept");
            const cancel = document.getElementById("crmDialogCancel");
            const icon = document.getElementById("crmDialogIcon");

            titleEl.textContent = title;
            messageEl.textContent = message;
            accept.textContent = acceptText;
            cancel.textContent = cancelText;
            cancel.classList.toggle("oculto", !cancelText);
            icon.textContent = tone === "danger" ? "!" : "?";
            overlay.className = `crm-dialog-overlay ${tone}`;
            overlay.classList.remove("oculto");

            const cerrar = value => {
                overlay.classList.add("oculto");
                accept.onclick = null;
                cancel.onclick = null;
                overlay.onclick = null;
                document.onkeydown = null;
                resolve(value);
            };

            accept.onclick = () => cerrar(true);
            cancel.onclick = () => cerrar(false);
            overlay.onclick = event => {
                if (event.target === overlay) cerrar(false);
            };
            document.onkeydown = event => {
                if (event.key === "Escape") cerrar(false);
                if (event.key === "Enter") cerrar(true);
            };
        });
    };

    window.crmAlert = function ({
        title = "Aviso",
        message = "",
        acceptText = "Entendido",
        tone = "primary"
    } = {}) {
        return window.crmConfirm({
            title,
            message,
            acceptText,
            cancelText: "",
            tone
        });
    };

    function renderSidebar(activeKey) {
        const grupos = filtrarGruposPorRol();
        return `
            <aside class="crm-sidebar">
                <div class="crm-sidebar-brand">
                    <img src="logo_i_biznescob.png" alt="Biznescob">
                    <div>
                        <strong>Biznescob</strong>
                        <span>CRM - Cobranzas</span>
                    </div>
                </div>
                <nav class="crm-sidebar-nav">
                    ${grupos.map(group => renderGroup(group, activeKey)).join("")}
                </nav>
                <button class="crm-logout" type="button" onclick="crmLogout()">${iconLogout()}<span>Cerrar sesión</span></button>
            </aside>
        `;
    }

    function renderGroup(group, activeKey) {
        if (!group.items.length) return "";
        return `
            <section class="crm-nav-group">
                <h3>${escapeHtml(group.title)}</h3>
                ${group.items.map(item => renderNavItem(item, activeKey)).join("")}
            </section>
        `;
    }

    // Color del icono por area (igual criterio que las areas del Home). Sin entrada = azul.
    const TONO_NAV = {
        ia_feedback: "calidad", susurro_ia: "calidad", consumo_ia_admin: "calidad",
        documentos: "datos", importacion: "datos", pagos: "datos", canales: "datos",
        supervisores_admin: "admin", metas_agentes_admin: "admin", accesos_admin: "admin",
        pautas_evaluacion_admin: "admin", admin: "admin"
    };

    function renderNavItem(item, activeKey) {
        const tono = `tono-${TONO_NAV[item.key] || "operacion"}`;
        if (item.disabled) {
            return `<span class="crm-nav-disabled ${tono}" title="${escapeHtml(item.label)}"><span class="crm-nav-icon">${item.icon}</span><span class="crm-nav-text">${item.label}</span><small>Próx.</small></span>`;
        }
        const active = item.key === activeKey ? " active" : "";
        return `<a class="crm-nav-link ${tono}${active}" href="${item.href}" title="${escapeHtml(item.label)}"><span class="crm-nav-icon">${item.icon}</span><span class="crm-nav-text">${item.label}</span></a>`;
    }

    function renderTopbar(meta) {
        const agente = localStorage.getItem("agente") || localStorage.getItem("dni") || "Usuario";
        const tipo = localStorage.getItem("tipo") || "CRM";

        return `
            <header class="crm-topbar">
                <div class="crm-topbar-left">
                    <button class="crm-menu-button" type="button" onclick="crmToggleSidebar()" title="Contraer o expandir menú">${iconMenu()}</button>
                    ${FOCUS_MODULES.has(meta.key) ? `<button id="crmFocusButton" class="crm-focus-button" type="button" onclick="crmToggleFocus()" title="Enfocar área de trabajo" aria-pressed="false">${iconFocus()}<span>Enfocar</span></button>` : ""}
                    <img class="crm-topbar-logo" src="logo_i_biznescob.png" alt="Biznescob">
                    <div>
                        <h1>${escapeHtml(meta.title)}</h1>
                        <p>${escapeHtml(meta.subtitle)}</p>
                    </div>
                </div>
                <div class="crm-topbar-user">
                    <div class="crm-user-text">
                        <strong>${escapeHtml(agente)}</strong>
                        <span>${escapeHtml(tipo)}</span>
                    </div>
                    <button class="crm-logout-top" type="button" onclick="crmLogout()">Salir</button>
                </div>
            </header>
        `;
    }

    window.crmToggleFocus = function () {
        const activo = document.body.classList.toggle("crm-focus-mode");
        const button = document.getElementById("crmFocusButton");
        if (button) {
            button.setAttribute("aria-pressed", String(activo));
            button.title = activo ? "Salir del modo foco (Esc)" : "Enfocar área de trabajo";
            button.querySelector("span").textContent = activo ? "Salir foco" : "Enfocar";
        }
    };

    function manejarAtajoFoco(event) {
        if (event.key !== "Escape" || !document.body.classList.contains("crm-focus-mode")) return;
        if (!document.getElementById("crmDialogOverlay")?.classList.contains("oculto")) return;
        window.crmToggleFocus();
    }

    function currentPage() {
        return window.location.pathname.split("/").pop() || "";
    }

    function getPdpHoyHref() {
        const tipo = String(localStorage.getItem("tipo") || "").toUpperCase();
        const query = typeof obtenerQueryCarterasSesion === "function"
            ? obtenerQueryCarterasSesion()
            : queryCarterasLocal();

        if (tipo.includes("SUPERVISOR") && query) {
            return `corporativo_pdp_hoy.html?${query}`;
        }
        return "corporativo_pdp_hoy.html";
    }

    function queryCarterasLocal() {
        const ids = [
            ...(localStorage.getItem("idcarteras") || "").split(","),
            localStorage.getItem("idcartera")
        ]
            .map(x => String(x || "").trim())
            .filter(Boolean);
        const unicos = [...new Set(ids)];

        if (unicos.length > 1) return `idcarteras=${encodeURIComponent(unicos.join(","))}`;
        if (unicos.length === 1) return `idcartera=${encodeURIComponent(unicos[0])}`;
        return "";
    }

    function filtrarGruposPorRol() {
        const vistos = new Set();
        return NAV_GROUPS
            .map(group => ({
                ...group,
                items: group.items.filter(item => {
                    if (item.key !== "inicio" && !puedeAccederModulo(item.key)) return false;
                    const destino = item.href || item.key;
                    if (vistos.has(destino)) return false;
                    vistos.add(destino);
                    return true;
                })
            }))
            .filter(group => group.items.length);
    }

    function puedeAccederModulo(key) {
        if (key === "inicio") return true;
        if (typeof puedeUsarVista === "function") {
            const permiso = puedeUsarVista(key);
            if (permiso !== null) return permiso;
        }
        // El consumo de la API es informacion de costo del modulo: solo administracion.
        if (key === "consumo_ia_admin") return tipoUsuario() === "ADMINISTRADOR";
        // Accesos al CRM: solo administracion. La seguridad real esta en el backend (403).
        if (key === "accesos_admin") return tipoUsuario() === "ADMINISTRADOR";
        if (key === "reportes") return true;
        if (key === "documentos") return puedeAccederDocumentos();
        if (key === "admin") return esPerfilGerencial();
        if (esPerfilGerencial()) return true;

        if (esUsuarioMonitorCalidad()) {
            return key === "ia_feedback";
        }

        const compartamos = carteraCompartamos();

        if (esUsuarioSupervisor()) {
            return [
                "gestiones",
                "compromisos",
                "ritmo_meta",
                "pdp_hoy",
                "control_horario",
                "ia_feedback",
                "importacion",
                "pagos",
                "canales",
                "telefonos",
                "documentos",
                ...(compartamos ? ["clientes"] : [])
            ].includes(key);
        }

        return [
            "compromisos",
            "ritmo_meta",
            "telefonos",
            ...(compartamos ? ["clientes"] : [])
        ].includes(key);
    }

    function puedeAccederDocumentos() {
        const tipo = tipoUsuario();
        return esUsuarioSupervisor()
            || ["ADMINISTRADOR", "JEFE DE CARTERA", "JEFE DE CARTERAS", "JEFE CARTERA"].includes(tipo);
    }

    function tipoUsuario() {
        if (typeof normalizarTipoUsuario === "function") {
            return normalizarTipoUsuario(localStorage.getItem("tipo"));
        }
        return String(localStorage.getItem("tipo") || "").trim().toUpperCase();
    }

    function esUsuarioSupervisor() {
        const tipo = tipoUsuario();
        if (typeof esSupervisor === "function") return esSupervisor(tipo);
        return tipo === "SUPERVISOR"
            || tipo === "SUPERVISORA"
            || tipo.includes("SUPERVISOR");
    }

    function esUsuarioMonitorCalidad() {
        const tipo = tipoUsuario();
        return tipo.includes("MONITOR") && tipo.includes("CALIDAD");
    }

    function esPerfilGerencial() {
        if (typeof puedeVerCorporativo === "function") {
            return puedeVerCorporativo(localStorage.getItem("tipo"));
        }
        return ["ADMINISTRADOR", "JEFE DE CARTERA", "JEFE DE CARTERAS", "JEFE DE COBRANZA", "JEFE CARTERA"].includes(tipoUsuario());
    }

    function carteraCompartamos() {
        if (typeof esCarteraCompartamos === "function") {
            return esCarteraCompartamos();
        }
        return ["124", "126", "128", "133", "144"].includes(String(localStorage.getItem("idcartera") || ""));
    }

    function escapeHtml(value) {
        return String(value ?? "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    window.crmToggleSidebar = function () {
        document.body.classList.toggle("crm-sidebar-collapsed");
        localStorage.setItem(
            "crmSidebarCollapsedV2",
            document.body.classList.contains("crm-sidebar-collapsed") ? "1" : "0"
        );
    };

    window.crmLogout = function () {
        if (typeof cerrarSesion === "function") {
            cerrarSesion();
            return;
        }
        localStorage.clear();
        sessionStorage.clear();
        window.location.href = "login.html";
    };

    function svg(path) {
        return `<svg viewBox="0 0 24 24" aria-hidden="true">${path}</svg>`;
    }

    function iconMenu() {
        return svg('<path d="M4 7h16M4 12h16M4 17h16"/>');
    }

    function iconFocus() {
        return svg('<path d="M8 4H4v4M16 4h4v4M20 16v4h-4M4 16v4h4"/>');
    }

    function iconHome() {
        return svg('<path d="M3 11.5 12 4l9 7.5"/><path d="M5.5 10.5V20h13v-9.5"/><path d="M9.5 20v-6h5v6"/>');
    }

    function iconUsers() {
        return svg('<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20c0-3.6 2.9-6 6.5-6s6.5 2.4 6.5 6M16 5.2a3.5 3.5 0 010 5.6M18 14.4c2.2.7 3.5 2.6 3.5 5.6"/>');
    }

    function iconClipboard() {
        return svg('<path d="M8 4h8l1 2h2v14H5V6h2z"/><path d="M9 11h6M9 15h6"/>');
    }

    function iconDocument() {
        return svg('<path d="M7 3h7l5 5v13H7z"/><path d="M14 3v5h5"/><path d="M10 13h6M10 17h6"/>');
    }

    function iconCalendar() {
        return svg('<path d="M6 4v3M18 4v3"/><path d="M4 7h16v13H4z"/><path d="M8 12h3M13 12h3M8 16h3"/>');
    }

    function iconDashboard() {
        return svg('<path d="M4 13a8 8 0 1 1 16 0"/><path d="M12 13l4-5"/><path d="M6 17h12"/>');
    }

    function iconTarget() {
        return svg('<circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="4"/><path d="M12 2v4M22 12h-4M12 22v-4M2 12h4"/>');
    }

    function iconClock() {
        return svg('<circle cx="12" cy="12" r="8"/><path d="M12 7v5l3 2"/>');
    }

    function iconUpload() {
        return svg('<path d="M12 16V4M7 9l5-5 5 5M4 20h16"/>');
    }

    function iconSend() {
        return svg('<path d="M4 12 20 4l-5 16-3-7z"/><path d="m12 13 8-9"/>');
    }

    function iconChart() {
        return svg('<path d="M5 19V9M12 19V5M19 19v-7"/><path d="M3 19h18"/>');
    }

    function iconIa() {
        return svg('<path d="M12 3v3"/><path d="M12 18v3"/><path d="M4.9 4.9 7 7"/><path d="m17 17 2.1 2.1"/><path d="M3 12h3"/><path d="M18 12h3"/><path d="m4.9 19.1 2.1-2.1"/><path d="m17 7 2.1-2.1"/><circle cx="12" cy="12" r="4"/><path d="M10.5 12h3"/><path d="M12 10.5v3"/>');
    }

    function iconSettings() {
        return svg('<circle cx="12" cy="12" r="3"/><path d="M19 12a7 7 0 0 0-.1-1l2-1.5-2-3.4-2.4 1a8 8 0 0 0-1.7-1L14.5 3h-5l-.4 3.1a8 8 0 0 0-1.7 1l-2.4-1-2 3.4L5 11a7 7 0 0 0 0 2l-2 1.5 2 3.4 2.4-1a8 8 0 0 0 1.7 1l.4 3.1h5l.4-3.1a8 8 0 0 0 1.7-1l2.4 1 2-3.4-2-1.5a7 7 0 0 0 .1-1z"/>');
    }

    // Iconos por modulo: mismo set que el Home (home.js, ICONOS_HOME). Si se
    // cambia uno, cambiarlo tambien alli para que menu e inicio coincidan.
    function iconRadar() {
        return svg('<circle cx="11" cy="11" r="7"/><path d="M20 20l-4-4"/>');
    }

    function iconCompromisos() {
        return svg('<rect x="5" y="4" width="14" height="17" rx="2"/><path d="M9 4h6v3H9zM9 14l2 2 4-4"/>');
    }

    function iconMetas() {
        return svg('<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="4.5"/><path d="M12 12l6-6"/>');
    }

    function iconPdpHoy() {
        return svg('<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4M9 15l2 2 4-4"/>');
    }

    function iconPhone() {
        return svg('<path d="M5 4h4l2 5-2.5 1.5a11 11 0 005 5L15 13l5 2v4a2 2 0 01-2 2A16 16 0 013 6a2 2 0 012-2z"/>');
    }

    function iconDocumento() {
        return svg('<path d="M14 3H7a2 2 0 00-2 2v14a2 2 0 002 2h10a2 2 0 002-2V8l-5-5zM14 3v5h5M9 13h6M9 17h6"/>');
    }

    function iconBars() {
        return svg('<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>');
    }

    function iconWallet() {
        return svg('<rect x="3" y="6" width="18" height="13" rx="2"/><path d="M3 10h18M16 15h2"/>');
    }

    function iconMegaphone() {
        return svg('<path d="M3 11v3l12 5V6L3 11zM15 9a4 4 0 010 6M6 14l1.5 6"/>');
    }

    function iconRobot() {
        return svg('<rect x="4" y="8" width="16" height="12" rx="3"/><path d="M12 4v4M9 13v1M15 13v1M9 17h6"/>');
    }

    function iconMic() {
        return svg('<rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0014 0M12 18v3"/>');
    }

    function iconCoins() {
        return svg('<ellipse cx="12" cy="6" rx="8" ry="3"/><path d="M4 6v6c0 1.7 3.6 3 8 3s8-1.3 8-3V6M4 12v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6"/>');
    }

    function iconPerson() {
        return svg('<circle cx="12" cy="8" r="3.5"/><path d="M5 20c0-3.6 3.1-6 7-6s7 2.4 7 6"/>');
    }

    function iconKey() {
        return svg('<circle cx="8" cy="15" r="4"/><path d="M11 12l9-9M16 7l3 3"/>');
    }

    function iconLogout() {
        return svg('<path d="M10 17l5-5-5-5"/><path d="M15 12H3"/><path d="M14 4h6v16h-6"/>');
    }

    // Va al final del IIFE para que todas las constantes (TONO_NAV, etc.) ya existan.
    // app_layout.js va al final del <body>: lo que hay arriba ya existe, asi que el
    // menu se monta de inmediato en vez de esperar a DOMContentLoaded (que aguarda
    // a scripts pesados como ia_feedback.js, ~450 KB). Si el script estuviera en el
    // <head>, no hay body todavia y se usa DOMContentLoaded como antes.
    if (document.body) {
        initCrmLayout();
    } else {
        document.addEventListener("DOMContentLoaded", initCrmLayout);
    }
})();
