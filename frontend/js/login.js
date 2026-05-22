async function login() {
    const dniInput = document.getElementById("dni").value.trim();

    if (!dniInput) {
        alert("Ingresa DNI");
        return;
    }

    try {
        localStorage.clear();

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
            alert(data.msg || "Usuario no encontrado");
            return;
        }

        localStorage.setItem("dni", data.user.dni);
        localStorage.setItem("agente", data.user.agente);
        localStorage.setItem("tipo", data.user.tipo);
        localStorage.setItem("idcartera", data.user.idcartera || "");

        window.location.href = "home.html";

    } catch (error) {
        console.error("ERROR LOGIN:", error);
        alert("No se pudo conectar con el servidor");
    }
}
