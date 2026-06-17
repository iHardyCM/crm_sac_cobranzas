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
    const dniInput = (dniCampo?.value || "").replace(/\D/g, "").trim();

    if (dniInput.length !== 8) {
        mostrarLoginMensaje("Ingresa un DNI valido de 8 digitos.");
        dniCampo?.focus();
        return;
    }

    try {
        loginEnProceso = true;
        setLoginLoading(true);
        mostrarLoginMensaje("Validando credenciales...", "info");
        localStorage.clear();
        sessionStorage.clear();

        const BASE_URL = `${window.location.protocol}//${window.location.hostname}:8000`;

        const res = await fetch(`${BASE_URL}/auth/login`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ dni: dniInput })
        });

        if (!res.ok) {
            throw new Error("Error de conexion con el servidor");
        }

        const data = await res.json();

        if (!data.ok) {
            mostrarLoginMensaje(data.msg || "Usuario no encontrado.");
            return;
        }

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
        mostrarLoginMensaje("No se pudo conectar con el servidor.");
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
}

function mostrarLoginMensaje(texto, tipo = "error") {
    const mensaje = document.getElementById("loginMensaje");
    if (!mensaje) return;
    mensaje.textContent = texto;
    mensaje.className = `login-message ${tipo}`;
}
