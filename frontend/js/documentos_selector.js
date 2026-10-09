// documentos_selector.js
// Recorrido por niveles para elegir Entidad > Cartera > Tipo de documento.
//
// Solo se ve un nivel a la vez. Lo ya elegido queda arriba como ruta
// (Entidad › Cartera › Tipo) y cada tramo es clicable para volver a ese nivel.
// Los campos de búsqueda y los botones de buscar/limpiar aparecen cuando la
// ruta está completa. La última ruta completada se guarda por usuario en este
// navegador y se ofrece como "Continuar con la última selección" (el cierre de
// sesión borra el localStorage, y con él esta preferencia).
//
// Es una capa encima de los <select> existentes: documentos.js sigue leyendo y
// escribiendo #documentoEntidad, #documentoCartera y #documentoTipo igual que
// antes. Aquí solo se muestran como opciones y, al elegir una, se asigna el
// valor al <select> y se dispara su evento "change". Si este archivo fallara,
// los <select> originales seguirían visibles y funcionando.
(function () {
    "use strict";

    const NIVELES = [
        { id: "documentoEntidad", nombre: "Entidad", pide: () => "¿De qué entidad es el documento?" },
        { id: "documentoCartera", nombre: "Cartera", pide: () => `Elige la cartera de ${textoElegido(0)}` },
        { id: "documentoTipo", nombre: "Tipo de documento", pide: () => "Elige el tipo de documento", buscar: 7 }
    ];
    const COMPLETO = NIVELES.length;
    const CLAVE_ULTIMA_RUTA = "crmDocumentosUltimaRuta";

    let nivel = 0;                          // nivel que se está eligiendo (COMPLETO = ruta terminada)
    const previo = [null, null, null];      // valor confirmado por nivel (para resaltarlo al volver)
    const sinAuto = new Set();              // niveles revisitados: no se saltan solos
    let consulta = "";                      // texto del buscador del nivel actual
    let firmaNivel = "";
    let animar = false;
    let enfocar = false;
    let pendiente = false;
    let tarjeta = null;

    document.addEventListener("DOMContentLoaded", iniciar);

    function iniciar() {
        const rejilla = document.querySelector(".documentos-form-grid");
        const selects = NIVELES.map(n => document.getElementById(n.id));
        if (!rejilla || selects.some(s => !s)) return;

        tarjeta = rejilla.closest(".documentos-form-card") || rejilla.parentNode;
        const panel = document.createElement("div");
        panel.className = "doc-pick";
        panel.innerHTML = '<nav class="doc-pick-trail" aria-label="Ruta del documento"><ol></ol></nav><div class="doc-pick-stage"></div>';
        rejilla.parentNode.insertBefore(panel, rejilla);

        selects.forEach(select => {
            select.closest("label")?.classList.add("doc-pick-oculto");
            new MutationObserver(programarRender).observe(select, { childList: true, subtree: true, attributes: true });
        });
        tarjeta.classList.add("doc-pick-activo", "doc-pick-incompleto");
        programarRender();
    }

    function programarRender() {
        if (pendiente) return;
        pendiente = true;
        requestAnimationFrame(() => {
            pendiente = false;
            pintar();
        });
    }

    // ---- lectura de los <select> -------------------------------------------------

    function opcionesDe(i) {
        const select = document.getElementById(NIVELES[i].id);
        return Array.from(select.options).map(o => ({
            valor: o.value,
            texto: (o.textContent || "").trim(),
            deshabilitada: o.disabled
        }));
    }

    function textoElegido(i) {
        const select = document.getElementById(NIVELES[i].id);
        const opcion = select.options[select.selectedIndex];
        return limpiarEntidad(i, (opcion?.textContent || "").trim());
    }

    function limpiarEntidad(i, texto) {
        return i === 0 ? texto.replace(/\s*\(\d+\)\s*$/, "").replace(/\s+-\s+sin carteras$/i, "") : texto;
    }

    function descomponer(i, op) {
        if (i === 0) {
            const m = op.texto.match(/^(.*?)\s*\((\d+)\)$/);
            const total = m ? Number(m[2]) : 0;
            return {
                titulo: limpiarEntidad(0, op.texto),
                detalle: total ? `${total} ${total === 1 ? "cartera" : "carteras"}` : "Sin carteras",
                insignia: "",
                sinOpciones: total === 0
            };
        }
        if (i === 1) {
            const m = op.texto.match(/^(\d+)\s+-\s+(.*)$/);
            return {
                titulo: m ? m[2] : op.texto,
                detalle: m ? `Cartera ${m[1]}` : "",
                insignia: m ? m[1] : ""
            };
        }
        return { titulo: op.texto, detalle: "", insignia: "" };
    }

    // ---- avance ------------------------------------------------------------------

    function elegir(i, valor, manual = true) {
        const select = document.getElementById(NIVELES[i].id);
        const cambio = select.value !== valor;
        if (cambio) {
            select.value = valor;
            select.dispatchEvent(new Event("change", { bubbles: true }));
            for (let j = i + 1; j < COMPLETO; j++) {
                previo[j] = null;
                sinAuto.delete(j);
            }
        }
        previo[i] = valor;
        sinAuto.delete(i);
        nivel = i + 1;
        if (nivel === COMPLETO) guardarRuta();
        consulta = "";
        animar = manual;
        enfocar = manual;
        programarRender();
    }

    function volverA(i) {
        nivel = i;
        sinAuto.add(i);
        consulta = "";
        animar = true;
        enfocar = true;
        programarRender();
    }

    // Si un nivel solo tiene una opción disponible, se elige sola (salvo que el
    // usuario haya vuelto a ese nivel a propósito).
    function autoAvanzar() {
        for (let guardia = 0; guardia < COMPLETO && nivel < COMPLETO; guardia++) {
            const habilitadas = opcionesDe(nivel).filter(o => o.valor !== "" && !o.deshabilitada
                && !(nivel === 0 && descomponer(0, o).sinOpciones));
            if (habilitadas.length !== 1 || sinAuto.has(nivel)) return;
            elegir(nivel, habilitadas[0].valor, false);
            // elegir() actualiza `nivel`; los <select> hijos ya se repoblaron en el "change"
        }
    }

    // ---- última ruta ---------------------------------------------------------------

    function usuarioSesion() {
        try { return String(localStorage.getItem("dni") || ""); } catch (error) { return ""; }
    }

    function guardarRuta() {
        try {
            const ruta = NIVELES.map(def => {
                const select = document.getElementById(def.id);
                const op = select.options[select.selectedIndex];
                return { v: select.value, t: (op?.textContent || "").trim() };
            });
            if (ruta.some(r => !r.v)) return;
            localStorage.setItem(CLAVE_ULTIMA_RUTA, JSON.stringify({ dni: usuarioSesion(), ruta }));
        } catch (error) {
            // almacenamiento no disponible: simplemente no se recuerda
        }
    }

    function rutaGuardada() {
        try {
            const dato = JSON.parse(localStorage.getItem(CLAVE_ULTIMA_RUTA) || "null");
            if (!dato || dato.dni !== usuarioSesion() || !Array.isArray(dato.ruta) || dato.ruta.length !== COMPLETO) return null;
            if (dato.ruta.some(r => !r || typeof r.v !== "string" || !r.v || typeof r.t !== "string")) return null;
            return dato.ruta;
        } catch (error) {
            return null;
        }
    }

    // Aplica la ruta guardada nivel por nivel. Si algún nivel ya no existe o está
    // deshabilitado, se detiene ahí y el usuario sigue eligiendo desde ese nivel.
    function continuarRuta(ruta) {
        for (let i = 0; i < COMPLETO; i++) {
            const existe = opcionesDe(i).some(o => o.valor === ruta[i].v && !o.deshabilitada);
            if (!existe) break;
            elegir(i, ruta[i].v, false);
        }
        animar = true;
        enfocar = true;
        programarRender();
    }

    // ---- pintado -----------------------------------------------------------------

    function pintar() {
        if (nivel < COMPLETO) autoAvanzar();
        if (nivel > COMPLETO) nivel = COMPLETO;

        tarjeta.classList.toggle("doc-pick-incompleto", nivel < COMPLETO);
        pintarRuta();
        pintarEtapa();
    }

    function pintarRuta() {
        const lista = document.querySelector(".doc-pick-trail ol");
        lista.textContent = "";
        NIVELES.forEach((def, i) => {
            const li = document.createElement("li");
            li.className = "doc-pick-step";
            if (i < nivel) {
                const boton = document.createElement("button");
                boton.type = "button";
                boton.className = "doc-pick-crumb";
                boton.title = `Cambiar ${def.nombre.toLowerCase()}`;
                const select = document.getElementById(def.id);
                const op = select.options[select.selectedIndex];
                const parte = descomponer(i, { texto: (op?.textContent || "").trim() });
                if (parte.insignia) boton.appendChild(crearSpan("doc-pick-badge", parte.insignia));
                boton.appendChild(crearSpan("doc-pick-crumb-text", parte.titulo));
                boton.addEventListener("click", () => volverA(i));
                li.appendChild(boton);
            } else if (i === nivel) {
                li.appendChild(crearSpan("doc-pick-current", def.nombre));
                li.setAttribute("aria-current", "step");
            } else {
                li.appendChild(crearSpan("doc-pick-future", def.nombre));
            }
            lista.appendChild(li);
        });
    }

    function pintarEtapa() {
        const etapa = document.querySelector(".doc-pick-stage");
        if (nivel >= COMPLETO) {
            etapa.hidden = true;
            etapa.textContent = "";
            firmaNivel = "";
            return;
        }
        etapa.hidden = false;

        const def = NIVELES[nivel];
        const select = document.getElementById(def.id);
        const opciones = opcionesDe(nivel);
        const firma = `${nivel}§` + opciones.map(o => `${o.valor}|${o.texto}|${o.deshabilitada}`).join("§");
        if (firma !== firmaNivel) {
            if (!firmaNivel.startsWith(`${nivel}§`)) consulta = "";
            firmaNivel = firma;
        }

        const teniaFoco = etapa.contains(document.activeElement)
            && document.activeElement.classList.contains("doc-pick-opt");
        const buscadorActivo = document.activeElement && document.activeElement.classList.contains("doc-pick-search");
        etapa.textContent = "";
        etapa.classList.toggle("is-entering", animar);
        animar = false;

        let conAtajo = false;
        if (nivel === 0) {
            const ruta = rutaGuardada();
            if (ruta && opciones.some(o => o.valor === ruta[0].v && !o.deshabilitada)) {
                etapa.appendChild(crearContinuar(ruta));
                conAtajo = true;
            }
        }

        const titulo = document.createElement("h3");
        titulo.className = "doc-pick-prompt";
        titulo.id = "docPickPrompt";
        titulo.textContent = conAtajo ? "O elige otra entidad" : def.pide();
        etapa.appendChild(titulo);

        const reales = opciones.filter(o => o.valor !== "");
        if (!reales.length) {
            const vacio = document.createElement("p");
            vacio.className = "doc-pick-empty";
            vacio.textContent = select.options.length ? (opciones[0]?.texto || "Sin opciones disponibles") : "Cargando opciones…";
            etapa.appendChild(vacio);
            return;
        }

        let visibles = reales;
        if (def.buscar && reales.length > def.buscar) {
            etapa.appendChild(crearBuscador());
            const q = normalizar(consulta);
            visibles = q ? reales.filter(o => normalizar(o.texto).includes(q)) : reales;
        }

        const rejilla = document.createElement("div");
        rejilla.className = "doc-pick-grid";
        rejilla.setAttribute("role", "group");
        rejilla.setAttribute("aria-labelledby", "docPickPrompt");
        if (!visibles.length) {
            const vacio = document.createElement("p");
            vacio.className = "doc-pick-empty";
            vacio.textContent = "Ningún documento coincide con la búsqueda.";
            etapa.appendChild(vacio);
        }
        visibles.forEach(op => rejilla.appendChild(crearOpcion(op)));
        etapa.appendChild(rejilla);

        if (buscadorActivo) {
            const input = etapa.querySelector(".doc-pick-search");
            if (input) { input.focus(); input.setSelectionRange(input.value.length, input.value.length); }
        } else if (enfocar || teniaFoco) {
            (rejilla.querySelector(".is-selected") || rejilla.querySelector(".doc-pick-opt:not(:disabled)"))?.focus();
        }
        enfocar = false;
    }

    function crearContinuar(ruta) {
        const boton = document.createElement("button");
        boton.type = "button";
        boton.className = "doc-pick-resume";
        const texto = document.createElement("span");
        texto.className = "doc-pick-resume-text";
        texto.appendChild(crearSpan("doc-pick-resume-label", "Continuar con la última selección"));
        const partes = ruta.map((r, i) => {
            const t = limpiarEntidad(i, r.t);
            return i === 1 ? t.replace(/^(\d+)\s+-\s+/, "$1 · ") : t;
        });
        texto.appendChild(crearSpan("doc-pick-resume-path", partes.join("  ›  ")));
        boton.appendChild(texto);
        boton.appendChild(crearSpan("doc-pick-resume-go", "→")).setAttribute("aria-hidden", "true");
        boton.addEventListener("click", () => continuarRuta(ruta));
        return boton;
    }

    function crearBuscador() {
        const input = document.createElement("input");
        input.type = "search";
        input.className = "doc-pick-search";
        input.placeholder = "Buscar tipo de documento…";
        input.setAttribute("aria-label", "Buscar tipo de documento");
        input.autocomplete = "off";
        input.value = consulta;
        input.addEventListener("input", () => {
            consulta = input.value;
            pintarEtapa();
        });
        return input;
    }

    function crearOpcion(op) {
        const parte = descomponer(nivel, op);
        const deshabilitada = op.deshabilitada || Boolean(parte.sinOpciones);
        const boton = document.createElement("button");
        boton.type = "button";
        boton.className = "doc-pick-opt";
        boton.dataset.valor = op.valor;
        if (deshabilitada) {
            boton.disabled = true;
            boton.classList.add("is-disabled");
        }
        if (previo[nivel] === op.valor) {
            boton.classList.add("is-selected");
            boton.setAttribute("aria-current", "true");
        }

        const cuerpo = document.createElement("span");
        cuerpo.className = "doc-pick-body";
        cuerpo.appendChild(crearSpan("doc-pick-title", parte.titulo));
        if (parte.detalle) cuerpo.appendChild(crearSpan("doc-pick-sub", parte.detalle));
        if (parte.insignia) boton.appendChild(crearSpan("doc-pick-badge", parte.insignia));
        boton.appendChild(cuerpo);
        boton.appendChild(crearSpan("doc-pick-go", "›")).setAttribute("aria-hidden", "true");

        const indice = nivel;
        boton.addEventListener("click", () => elegir(indice, op.valor));
        boton.addEventListener("keydown", moverConTeclado);
        return boton;
    }

    function moverConTeclado(event) {
        const teclas = ["ArrowRight", "ArrowDown", "ArrowLeft", "ArrowUp"];
        if (!teclas.includes(event.key)) return;
        const lista = Array.from(event.currentTarget.parentNode.querySelectorAll(".doc-pick-opt:not(:disabled)"));
        const i = lista.indexOf(event.currentTarget);
        if (i < 0) return;
        const paso = (event.key === "ArrowRight" || event.key === "ArrowDown") ? 1 : -1;
        event.preventDefault();
        lista[(i + paso + lista.length) % lista.length].focus();
    }

    function crearSpan(clase, texto) {
        const span = document.createElement("span");
        span.className = clase;
        span.textContent = texto;
        return span;
    }

    function normalizar(texto) {
        return String(texto || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
    }
})();
