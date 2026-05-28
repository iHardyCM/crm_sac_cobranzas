function normalizarTipoUsuario(tipo) {
    return String(tipo || "")
        .trim()
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "")
        .toUpperCase();
}

function puedeVerCorporativo(tipo) {
    const tipoNormalizado = normalizarTipoUsuario(tipo || localStorage.getItem("tipo"));
    return [
        "JEFE DE CARTERA",
        "JEFE DE CARTERAS",
        "JEFE DE COBRANZA",
        "JEFE CARTERA",
        "ADMINISTRADOR"
    ].includes(tipoNormalizado);
}

function esSupervisor(tipo) {
    return normalizarTipoUsuario(tipo || localStorage.getItem("tipo")) === "SUPERVISOR";
}

function obtenerIdCarterasSesion() {
    const ids = [
        ...(localStorage.getItem("idcarteras") || "").split(","),
        localStorage.getItem("idcartera")
    ]
        .map(x => String(x || "").trim())
        .filter(Boolean);

    return [...new Set(ids)];
}

function obtenerQueryCarterasSesion() {
    const ids = obtenerIdCarterasSesion();

    if (ids.length > 1) {
        return `idcarteras=${encodeURIComponent(ids.join(","))}`;
    }

    if (ids.length === 1) {
        return `idcartera=${encodeURIComponent(ids[0])}`;
    }

    return "";
}

function esCarteraCompartamos(idcartera) {
    const carteras = idcartera
        ? [String(idcartera).trim()]
        : obtenerIdCarterasSesion();

    return carteras.some(cartera => ["124", "126", "128", "133", "139", "144"].includes(cartera));
}

function puedeVerPdpHoy(tipo) {
    return puedeVerCorporativo(tipo) || esSupervisor(tipo);
}

function obtenerRutaPorTipo(tipo) {
    const tipoNormalizado = normalizarTipoUsuario(tipo);

    if (puedeVerCorporativo(tipoNormalizado)) {
        return "corporativo.html";
    }

    if (tipoNormalizado === "SUPERVISOR") {
        return "supervisor.html";
    }

    return "compromisos.html";
}

function irInicio() {
    window.location.href = "home.html";
}

function exigirSesion() {
    const dni = localStorage.getItem("dni");
    const agente = localStorage.getItem("agente");

    if (!dni || !agente) {
        alert("Sesion invalida, vuelve a iniciar sesion");
        window.location.href = "login.html";
        return false;
    }

    return true;
}

function exigirAccesoCorporativo() {
    if (!exigirSesion()) return false;

    if (!puedeVerCorporativo()) {
        alert("No tienes acceso al panel corporativo");
        irInicio();
        return false;
    }

    return true;
}

function exigirAccesoPdpHoy() {
    if (!exigirSesion()) return false;

    if (!puedeVerPdpHoy()) {
        alert("No tienes acceso a promesas con vencimiento hoy");
        irInicio();
        return false;
    }

    return true;
}

function cerrarSesion() {
    localStorage.clear();
    sessionStorage.clear();
    window.location.href = "login.html";
}
