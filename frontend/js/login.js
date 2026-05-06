async function login() {

    const dniInput = document.getElementById("dni").value.trim();

    if (!dniInput) {
        alert("Ingresa DNI");
        return;
    }

    try {

        // 🔥 limpiar sesión
        localStorage.clear();

        // 🔥 base dinámica (clave para red)
        const BASE_URL = `http://${window.location.hostname}:8000`;

        // 🔥 request correcto
        const res = await fetch(`${BASE_URL}/auth/login`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ dni: dniInput })
        });

        // 🔥 validar respuesta HTTP
        if (!res.ok) {
            throw new Error("Error de conexión con el servidor");
        }

        const data = await res.json();
        console.log("TIPO RAW:", data.user.tipo);
        console.log("TIPO LIMPIO:", data.user.tipo?.trim().toUpperCase());
        console.log("USER:", data.user);

        console.log("RESPUESTA LOGIN:", data);

        // 🔥 validar negocio
        if (!data.ok) {
            alert("Usuario no encontrado");
            return;
        }

        // 🔥 guardar sesión
        localStorage.setItem("dni", data.user.dni);
        localStorage.setItem("agente", data.user.agente);
        localStorage.setItem("tipo", data.user.tipo); // 👈 NUEVO

        console.log("GUARDADO DNI:", localStorage.getItem("dni"));
        console.log("TIPO:", localStorage.getItem("tipo"));

        // 🔥 redirigir
        const tipo = data.user.tipo?.trim().toUpperCase();

        if (tipo === "SUPERVISOR") {
            window.location.href = "supervisor.html";
        } else {
            window.location.href = "compromisos.html";
        }

    } catch (error) {
        console.error("ERROR LOGIN:", error);

        alert("No se pudo conectar con el servidor 🚨");
    }
}