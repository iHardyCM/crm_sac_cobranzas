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
            title: "Consulta Compartamos",
            subtitle: "Informacion diaria de clientes activos, deuda, capital y cuotas"
        }
    };

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
                { key: "clientes", label: "Consulta Compartamos", href: "compartamos.html", icon: iconUsers() },
                { key: getCompromisosKey(), label: "Compromisos", href: getCompromisosHref(), icon: iconClipboard() },
                { key: "pdp_hoy", label: "Promesas Hoy", href: getPdpHoyHref(), icon: iconCalendar() }
            ]
        },
        {
            title: "Control Gerencial",
            items: [
                { key: "corporativo", label: "Panel Corporativo", href: "corporativo.html", icon: iconDashboard() },
                { key: "metas", label: "Seguimiento de Metas", href: "metas.html", icon: iconTarget() }
            ]
        },
        {
            title: "Importaciones",
            items: [
                { key: "pagos", label: "Pagos del Negocio", href: "pagos.html", icon: iconUpload() },
                { key: "canales", label: "Canales Alternos", href: "canales.html", icon: iconSend() }
            ]
        },
        {
            title: "Análisis",
            items: [
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

    document.addEventListener("DOMContentLoaded", initCrmLayout);

    function initCrmLayout() {
        const page = currentPage();
        const meta = MODULES[page];
        if (!meta) return;

        if (!puedeAccederModulo(meta.key)) {
            alert("No tienes acceso a este módulo con tu perfil actual.");
            window.location.href = "home.html";
            return;
        }

        document.body.classList.add("crm-shell");

        if (localStorage.getItem("crmSidebarCollapsedV2") !== "0") {
            document.body.classList.add("crm-sidebar-collapsed");
        }

        const activeKey = meta.key === "compromisos" && tipoUsuario() === "SUPERVISOR"
            ? "gestiones"
            : meta.key;

        document.body.insertAdjacentHTML("afterbegin", renderTopbar(meta));
        document.body.insertAdjacentHTML("afterbegin", renderSidebar(activeKey));
    }

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

    function renderNavItem(item, activeKey) {
        if (item.disabled) {
            return `<span class="crm-nav-disabled" title="${escapeHtml(item.label)}"><span class="crm-nav-icon">${item.icon}</span><span class="crm-nav-text">${item.label}</span><small>Próx.</small></span>`;
        }
        const active = item.key === activeKey ? " active" : "";
        return `<a class="crm-nav-link${active}" href="${item.href}" title="${escapeHtml(item.label)}"><span class="crm-nav-icon">${item.icon}</span><span class="crm-nav-text">${item.label}</span></a>`;
    }

    function renderTopbar(meta) {
        const agente = localStorage.getItem("agente") || localStorage.getItem("dni") || "Usuario";
        const tipo = localStorage.getItem("tipo") || "CRM";

        return `
            <header class="crm-topbar">
                <div class="crm-topbar-left">
                    <button class="crm-menu-button" type="button" onclick="crmToggleSidebar()" title="Contraer o expandir menú">${iconMenu()}</button>
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

    function currentPage() {
        return window.location.pathname.split("/").pop() || "";
    }

    function getPdpHoyHref() {
        const tipo = String(localStorage.getItem("tipo") || "").toUpperCase();
        const idcartera = localStorage.getItem("idcartera");
        if (tipo.includes("SUPERVISOR") && idcartera) {
            return `corporativo_pdp_hoy.html?idcartera=${encodeURIComponent(idcartera)}`;
        }
        return "corporativo_pdp_hoy.html";
    }

    function getCompromisosKey() {
        return tipoUsuario() === "SUPERVISOR" ? "gestiones" : "compromisos";
    }

    function getCompromisosHref() {
        return tipoUsuario() === "SUPERVISOR" ? "supervisor.html" : "compromisos.html";
    }

    function filtrarGruposPorRol() {
        return NAV_GROUPS
            .map(group => ({
                ...group,
                items: group.items.filter(item => item.key === "inicio" || item.disabled || puedeAccederModulo(item.key))
            }))
            .filter(group => group.items.length);
    }

    function puedeAccederModulo(key) {
        if (["inicio", "reportes", "admin"].includes(key)) return true;
        if (key === "compromisos" && esPerfilGerencial()) return false;
        if (esPerfilGerencial()) return true;

        const tipo = tipoUsuario();
        const compartamos = carteraCompartamos();

        if (tipo === "SUPERVISOR") {
            return [
                "gestiones",
                "compromisos",
                "pdp_hoy",
                "pagos",
                "canales",
                ...(compartamos ? ["clientes"] : [])
            ].includes(key);
        }

        return [
            "compromisos",
            ...(compartamos ? ["clientes"] : [])
        ].includes(key);
    }

    function tipoUsuario() {
        if (typeof normalizarTipoUsuario === "function") {
            return normalizarTipoUsuario(localStorage.getItem("tipo"));
        }
        return String(localStorage.getItem("tipo") || "").trim().toUpperCase();
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
        return ["124", "126", "128", "133", "139", "144"].includes(String(localStorage.getItem("idcartera") || ""));
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

    function iconHome() {
        return svg('<path d="M3 11.5 12 4l9 7.5"/><path d="M5.5 10.5V20h13v-9.5"/><path d="M9.5 20v-6h5v6"/>');
    }

    function iconUsers() {
        return svg('<path d="M16 19c0-2.2-1.8-4-4-4s-4 1.8-4 4"/><circle cx="12" cy="8" r="3"/><path d="M20 18c0-1.7-1-3-2.5-3.6"/><path d="M17 5.4a2.5 2.5 0 0 1 0 5"/>');
    }

    function iconClipboard() {
        return svg('<path d="M8 4h8l1 2h2v14H5V6h2z"/><path d="M9 11h6M9 15h6"/>');
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

    function iconUpload() {
        return svg('<path d="M12 16V4"/><path d="m7 9 5-5 5 5"/><path d="M5 18h14v2H5z"/>');
    }

    function iconSend() {
        return svg('<path d="M4 12 20 4l-5 16-3-7z"/><path d="m12 13 8-9"/>');
    }

    function iconChart() {
        return svg('<path d="M5 19V9M12 19V5M19 19v-7"/><path d="M3 19h18"/>');
    }

    function iconSettings() {
        return svg('<circle cx="12" cy="12" r="3"/><path d="M19 12a7 7 0 0 0-.1-1l2-1.5-2-3.4-2.4 1a8 8 0 0 0-1.7-1L14.5 3h-5l-.4 3.1a8 8 0 0 0-1.7 1l-2.4-1-2 3.4L5 11a7 7 0 0 0 0 2l-2 1.5 2 3.4 2.4-1a8 8 0 0 0 1.7 1l.4 3.1h5l.4-3.1a8 8 0 0 0 1.7-1l2.4 1 2-3.4-2-1.5a7 7 0 0 0 .1-1z"/>');
    }

    function iconLogout() {
        return svg('<path d="M10 17l5-5-5-5"/><path d="M15 12H3"/><path d="M14 4h6v16h-6"/>');
    }
})();
