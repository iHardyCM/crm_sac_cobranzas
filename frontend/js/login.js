let loginEnProceso = false;

document.addEventListener("DOMContentLoaded", () => {
    const dni = document.getElementById("dni");
    const mensajeSesion = sessionStorage.getItem("loginMensaje");

    if (dni) {
        dni.addEventListener("input", () => {
            dni.value = dni.value.replace(/\D/g, "").slice(0, 8);
        });
    }

    if (mensajeSesion) {
        mostrarLoginMensaje(mensajeSesion, "info");
        sessionStorage.removeItem("loginMensaje");
    }
});

async function login() {
    if (loginEnProceso) return;

    const dniCampo = document.getElementById("dni");
    const claveCampo = document.getElementById("clave");
    const dniInput = (dniCampo?.value || "").replace(/\D/g, "").trim();
    const claveInput = claveCampo?.value || "";

    if (dniInput.length !== 8) {
        mostrarLoginMensaje("Ingresa un DNI valido de 8 digitos.");
        dniCampo?.focus();
        return;
    }

    if (!claveInput) {
        mostrarLoginMensaje("Ingresa tu contraseña.");
        claveCampo?.focus();
        return;
    }

    try {
        loginEnProceso = true;
        setLoginLoading(true);
        mostrarLoginMensaje("Validando credenciales...", "info");
        localStorage.clear();
        sessionStorage.clear();

        const BASE_URL = `${window.location.protocol}//${window.location.hostname}:8000`;

        let res;
        try {
            res = await fetch(`${BASE_URL}/auth/login`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({ dni: dniInput, clave: claveInput })
            });
        } catch (errorRed) {
            console.error("ERROR LOGIN (red):", errorRed);
            mostrarLoginMensaje("No se pudo conectar con el servidor.");
            return;
        }

        let data = null;
        try {
            data = await res.json();
        } catch (errorJson) {
            data = null;
        }

        if (!res.ok || !data || !data.ok || !data.access_token) {
            mostrarLoginMensaje(data?.msg || "No se pudo validar el acceso.");
            if (claveCampo) {
                claveCampo.value = "";
                claveCampo.focus();
            }
            return;
        }

        // Token de acceso: es la credencial real ante el backend.
        localStorage.setItem("access_token", data.access_token);
        localStorage.setItem("token_type", data.token_type || "bearer");
        localStorage.setItem("requiere_cambio_clave", data.requiere_cambio_clave ? "1" : "0");

        // Datos de compatibilidad para las pantallas actuales.
        // NO son seguridad: el backend resuelve perfil y carteras desde el token.
        localStorage.setItem("dni", data.user.dni);
        localStorage.setItem("agente", data.user.agente);
        localStorage.setItem("tipo", data.user.tipo);
        localStorage.setItem("session_started_at", new Date().toISOString());

        const idcarteras = Array.isArray(data.user.idcarteras)
            ? data.user.idcarteras.filter(Boolean)
            : [data.user.idcartera].filter(Boolean);

        localStorage.setItem("idcartera", data.user.idcartera || idcarteras[0] || "");
        localStorage.setItem("idcarteras", idcarteras.join(","));

        window.location.href = "home.html";

    } catch (error) {
        console.error("ERROR LOGIN:", error);
        mostrarLoginMensaje("No se pudo completar el inicio de sesion.");
    } finally {
        loginEnProceso = false;
        setLoginLoading(false);
    }
}

function setLoginLoading(loading) {
    const boton = document.getElementById("loginBtn");
    const dni = document.getElementById("dni");

    if (boton) {
        boton.disabled = loading;
        boton.textContent = loading ? "Validando..." : "Ingresar";
    }

    if (dni) {
        dni.disabled = loading;
    }

    const clave = document.getElementById("clave");
    if (clave) {
        clave.disabled = loading;
    }
}

function mostrarLoginMensaje(texto, tipo = "error") {
    const mensaje = document.getElementById("loginMensaje");
    if (!mensaje) return;
    mensaje.textContent = texto;
    mensaje.className = `login-message ${tipo}`;
}
