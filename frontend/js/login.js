async function login() {

    const dniInput = document.getElementById("dni").value.trim();

    if (!dniInput) {
        alert("Ingresa DNI");
        return;
    }

    try {

        // 🔥 LIMPIA SIEMPRE
        localStorage.clear();

        const res = await fetch("http://localhost:8000/auth/login", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ dni: dniInput })
        });

        const data = await res.json();

        console.log("RESPUESTA LOGIN:", data);

        if (!data.ok) {
            alert("Usuario no encontrado");
            return;
        }

        // 🔥 GUARDAR CORRECTO
        localStorage.setItem("dni", data.user.dni);
        localStorage.setItem("agente", data.user.agente);

        console.log("GUARDADO DNI:", localStorage.getItem("dni"));

        // 🔥 REDIRECCIÓN
        window.location.href = "compromisos.html";

    } catch (error) {
        console.error("ERROR LOGIN:", error);
    }
}