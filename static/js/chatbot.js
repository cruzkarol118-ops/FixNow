/* FixNow - asistente orientador (sin persistencia, sin LLM externo). */
(function () {
  "use strict";

  const MAX_TEXTO = 300;
  const ENDPOINT = "/chatbot/orientar/";
  const CSRF = (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] || "";

  const CATEGORIAS = [
    { id: "plomeria", nombre: "Plomería", icono: "bi-droplet-half" },
    { id: "electricidad", nombre: "Electricidad", icono: "bi-lightning-charge-fill" },
    { id: "cerrajeria", nombre: "Cerrajería", icono: "bi-key-fill" },
    { id: "electrodomesticos", nombre: "Electrodomésticos", icono: "bi-tv-fill" },
    { id: "otro", nombre: "Otro", icono: "bi-tools" },
  ];

  const RUTAS = {
    solicitud_nueva: "/cliente/solicitud/nueva/",
    registro_cliente: "/registro/",
    login: "/ingresar/",
    tecnicos: "/cliente/tecnicos/",
    landing: "/",
  };

  const FAQ = [
    {
      clave: "como",
      titulo: "Cómo funciona FixNow",
      respuesta: "FixNow conecta a un cliente con un técnico verificado cercano. El cliente describe el daño, compara calificación, distancia y precio de referencia, y paga cuando termina el trabajo.",
      accion: { texto: "Pedir un técnico", url: RUTAS.registro_cliente },
    },
    {
      clave: "verificacion",
      titulo: "Verificación de técnicos",
      respuesta: "Cada técnico se registra con sus datos, cédula y certificación. Un administrador revisa la información y aprueba o rechaza la cuenta antes de que pueda recibir solicitudes.",
      accion: { texto: "Registrarme como técnico", url: "/registro/tecnico/" },
    },
    {
      clave: "precio",
      titulo: "Precio de referencia",
      respuesta: "Antes de elegir, ves el precio de referencia del técnico. El monto final se acuerda y se confirma al finalizar el servicio.",
      accion: { texto: "Pedir un técnico", url: RUTAS.registro_cliente },
    },
    {
      clave: "pago",
      titulo: "Pago al terminar",
      respuesta: "El pago se realiza cuando el trabajo está listo y confirmado.",
      accion: null,
    },
    {
      clave: "mapa",
      titulo: "Lista o mapa",
      respuesta: "Puedes ver los técnicos disponibles en lista o en mapa, con distancia y calificación.",
      accion: { texto: "Ver técnicos", url: RUTAS.tecnicos },
    },
    {
      clave: "cuenta",
      titulo: "Crear cuenta",
      respuesta: "Puedes crear cuenta de cliente o registrarte como técnico. El técnico queda pendiente de aprobación hasta que un administrador lo verifique.",
      accion: { texto: "Crear cuenta", url: RUTAS.registro_cliente },
    },
  ];

  // Palabras clave de posible situación urgente (no diagnóstico).
  const RIESGO = ["gas", "humo", "fuego", "chispa", "inund", "explosion", "quemad"];

  function esRiesgo(texto) {
    const t = (texto || "").toLowerCase();
    return RIESGO.some((r) => t.includes(r));
  }

  function crearElemento(tag, clase, texto) {
    const el = document.createElement(tag);
    if (clase) el.className = clase;
    if (texto !== undefined && texto !== null) el.textContent = texto;
    return el;
  }

  function bajar(panel) {
    // Doble rAF: asegura que el layout se haya recalculado tras añadir nodos.
    requestAnimationFrame(() => {
      bajar(panel);
      requestAnimationFrame(() => { panel.scrollTop = panel.scrollHeight; });
    });
  }

  function enlaceAccion(accion) {
    if (!accion) return null;
    const a = document.createElement("a");
    a.className = "fx-chatbot__chip is-primary";
    a.href = accion.url;
    a.textContent = accion.texto;
    return a;
  }

  function agregarMensaje(panel, tipo, texto) {
    const div = crearElemento("div", "fx-chatbot__msg fx-chatbot__msg--" + tipo, texto);
    panel.appendChild(div);
    bajar(panel);
    return div;
  }

  function agregarAcciones(panel, items) {
    const wrap = crearElemento("div", "fx-chatbot__actions");
    items.forEach((item) => {
      if (item) wrap.appendChild(item);
    });
    if (wrap.children.length) panel.appendChild(wrap);
    bajar(panel);
    return wrap;
  }

  function chipsCategorias(onPick) {
    return CATEGORIAS.map((c) => {
      const btn = crearElemento("button", "fx-chatbot__chip", c.nombre);
      btn.type = "button";
      btn.dataset.categoria = c.id;
      btn.addEventListener("click", () => onPick(c));
      return btn;
    });
  }

  async function clasificar(texto) {
    const res = await fetch(ENDPOINT, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": CSRF },
      body: JSON.stringify({ texto: texto.slice(0, MAX_TEXTO) }),
    });
    if (!res.ok) throw new Error("fallo");
    return res.json();
  }

  function mostrarSugerencia(panel, datos, onElegir) {
    if (datos && datos.categoria && datos.nombre) {
      agregarMensaje(panel, "bot", datos.respuesta);
      const wrap = crearElemento("div", "fx-chatbot__actions");
      const principal = crearElemento("button", "fx-chatbot__chip is-primary", "Usar " + datos.nombre);
      principal.type = "button";
      principal.addEventListener("click", () => onElegir(datos.categoria));
      wrap.appendChild(principal);
      const otra = crearElemento("button", "fx-chatbot__chip", "Elegir otra");
      otra.type = "button";
      otra.addEventListener("click", () => mostrarCategorias(panel, onElegir));
      wrap.appendChild(otra);
      panel.appendChild(wrap);
    } else {
      agregarMensaje(panel, "bot", "No tengo suficiente información para sugerir una categoría. Elige la que mejor encaje con tu problema.");
      mostrarCategorias(panel, onElegir);
    }
    bajar(panel);
  }

  function mostrarCategorias(panel, onElegir) {
    agregarMensaje(panel, "bot", "¿Qué tipo de problema es?");
    agregarAcciones(panel, chipsCategorias((c) => onElegir(c.id)));
  }

  function iniciarConversacion(panel, onElegirCategoria) {
    agregarMensaje(panel, "bot", "Hola. Te ayudo a elegir el tipo de servicio o a entender cómo funciona FixNow. No puedo diagnosticar ni dar instrucciones de reparación.");
    const acciones = [];
    const b1 = crearElemento("button", "fx-chatbot__chip is-primary", "Orientarme sobre un daño");
    b1.type = "button";
    b1.addEventListener("click", () => {
      agregarMensaje(panel, "user", "Orientarme sobre un daño");
      agregarMensaje(panel, "bot", "Describe brevemente el problema. Por ejemplo: “gotea el lavaplatos” o “no enciende un tomacorriente”.");
    });
    acciones.push(b1);
    const b2 = crearElemento("button", "fx-chatbot__chip", "Cómo funciona FixNow");
    b2.type = "button";
    b2.addEventListener("click", () => {
      agregarMensaje(panel, "user", "Cómo funciona FixNow");
      const faq = FAQ.find((f) => f.clave === "como");
      agregarMensaje(panel, "bot", faq.respuesta);
      const a = enlaceAccion(faq.accion);
      if (a) agregarAcciones(panel, [a]);
    });
    acciones.push(b2);
    const b3 = crearElemento("button", "fx-chatbot__chip", "Ver preguntas frecuentes");
    b3.type = "button";
    b3.addEventListener("click", () => {
      agregarMensaje(panel, "user", "Ver preguntas frecuentes");
      mostrarFaq(panel);
    });
    acciones.push(b3);
    agregarAcciones(panel, acciones);
  }

  function mostrarFaq(panel) {
    agregarMensaje(panel, "bot", "Elige un tema:");
    const chips = FAQ.map((f) => {
      const btn = crearElemento("button", "fx-chatbot__chip", f.titulo);
      btn.type = "button";
      btn.addEventListener("click", () => {
        agregarMensaje(panel, "user", f.titulo);
        agregarMensaje(panel, "bot", f.respuesta);
        const a = enlaceAccion(f.accion);
        if (a) agregarAcciones(panel, [a]);
      });
      return btn;
    });
    agregarAcciones(panel, chips);
  }

  function destinoPorCategoria(categoria) {
    // Visitante: lleva a registro normal; cliente autenticado: a nueva solicitud con categoría.
    const esCliente = document.body.classList.contains("fx-rol-cliente");
    if (esCliente) {
      return RUTAS.solicitud_nueva + "?categoria=" + encodeURIComponent(categoria);
    }
    return RUTAS.registro_cliente;
  }

  function init() {
    const root = document.createElement("div");
    root.className = "fx-chatbot";
    root.innerHTML = `
      <div class="fx-chatbot__panel" id="fx-chatbot-panel" hidden role="dialog" aria-modal="false" aria-labelledby="fx-chatbot-title">
        <div class="fx-chatbot__head">
          <div>
            <strong id="fx-chatbot-title">Asistente FixNow</strong>
            <small>Te orienta; no diagnostica ni repara.</small>
          </div>
          <button type="button" class="fx-chatbot__close" id="fx-chatbot-close" aria-label="Cerrar asistente"><i class="bi bi-x-lg"></i></button>
        </div>
        <div class="fx-chatbot__body" id="fx-chatbot-body"></div>
        <form class="fx-chatbot__input" id="fx-chatbot-form">
          <input class="form-control form-control-sm" type="text" id="fx-chatbot-text" maxlength="${MAX_TEXTO}" placeholder="Describe tu problema (opcional)" autocomplete="off">
          <button class="btn btn-fx btn-sm" type="submit">Enviar</button>
        </form>
      </div>
      <button type="button" class="fx-chatbot__launcher" id="fx-chatbot-launcher" aria-label="Abrir asistente" aria-expanded="false">
        <i class="bi bi-chat-dots-fill"></i>
      </button>
    `;
    document.body.appendChild(root);

    const panel = root.querySelector("#fx-chatbot-body");
    const launcher = root.querySelector("#fx-chatbot-launcher");
    const closeBtn = root.querySelector("#fx-chatbot-close");
    const form = root.querySelector("#fx-chatbot-form");
    const input = root.querySelector("#fx-chatbot-text");
    const panelWrap = root.querySelector("#fx-chatbot-panel");

    let abierto = false;
    let conversacionIniciada = false;

    function abrir() {
      panelWrap.hidden = false;
      launcher.setAttribute("aria-expanded", "true");
      abierto = true;
      if (!conversacionIniciada) {
        conversacionIniciada = true;
        iniciarConversacion(panel, (categoria) => {
          const url = destinoPorCategoria(categoria);
          if (url === RUTAS.solicitud_nueva + "?categoria=" + encodeURIComponent(categoria)) {
            // cliente: ir a nueva solicitud con categoría preseleccionada
            window.location.href = url;
          } else {
            // visitante: guardar categoría en sessionStorage para retomarla tras registro/login
            try { sessionStorage.setItem("fx_chatbot_categoria", categoria); } catch (e) {}
            window.location.href = url;
          }
        });
      }
      setTimeout(() => input.focus(), 50);
    }
    function cerrar() {
      panelWrap.hidden = true;
      launcher.setAttribute("aria-expanded", "false");
      abierto = false;
      launcher.focus();
    }

    launcher.addEventListener("click", () => (abierto ? cerrar() : abrir()));
    closeBtn.addEventListener("click", cerrar);
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && abierto) cerrar();
    });

    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const texto = (input.value || "").trim();
      if (!texto) return;
      const esRiesgoLocal = esRiesgo(texto);
      agregarMensaje(panel, "user", texto);
      input.value = "";
      if (esRiesgoLocal) {
        agregarMensaje(panel, "warn", "Si hay riesgo de gas, fuego, inundación o descarga eléctrica, aléjate del peligro y llama a los servicios de emergencia. FixNow no diagnostica ni da instrucciones de reparación.");
      }
      const espera = agregarMensaje(panel, "bot", "…");
      try {
        const datos = await clasificar(texto);
        espera.remove();
        if (datos.tipo === "riesgo") {
          // El aviso ya se mostró arriba; aquí ofrecemos la orientación.
          if (datos.categoria && datos.nombre) {
            agregarMensaje(panel, "bot", "Por lo que describes, parece un problema de " + datos.nombre + ". Puedes usar esa categoría o elegir otra; tú decides.");
            const wrap = crearElemento("div", "fx-chatbot__actions");
            const principal = crearElemento("button", "fx-chatbot__chip is-primary", "Usar " + datos.nombre);
            principal.type = "button";
            principal.addEventListener("click", () => {
              const url = destinoPorCategoria(datos.categoria);
              if (url.indexOf("solicitud/nueva") !== -1) window.location.href = url;
              else { try { sessionStorage.setItem("fx_chatbot_categoria", datos.categoria); } catch (e) {} window.location.href = url; }
            });
            wrap.appendChild(principal);
            const otra = crearElemento("button", "fx-chatbot__chip", "Elegir otra");
            otra.type = "button";
            otra.addEventListener("click", () => mostrarCategorias(panel, (categoria) => {
              const url = destinoPorCategoria(categoria);
              if (url.indexOf("solicitud/nueva") !== -1) window.location.href = url;
              else { try { sessionStorage.setItem("fx_chatbot_categoria", categoria); } catch (e) {} window.location.href = url; }
            }));
            wrap.appendChild(otra);
            const a = document.createElement("a");
            a.className = "fx-chatbot__chip";
            a.href = RUTAS.registro_cliente;
            a.textContent = "Pedir un técnico";
            wrap.appendChild(a);
            panel.appendChild(wrap);
            bajar(panel);
          } else {
            agregarMensaje(panel, "bot", "Elige la categoría que mejor encaje con tu problema.");
            mostrarCategorias(panel, (categoria) => {
              const url = destinoPorCategoria(categoria);
              if (url.indexOf("solicitud/nueva") !== -1) window.location.href = url;
              else { try { sessionStorage.setItem("fx_chatbot_categoria", categoria); } catch (e) {} window.location.href = url; }
            });
          }
        } else if (datos.tipo === "producto") {
          agregarMensaje(panel, "bot", datos.respuesta);
          const a = enlaceAccion(datos.accion || null);
          if (a) agregarAcciones(panel, [a]);
        } else {
          mostrarSugerencia(panel, datos, (categoria) => {
            const url = destinoPorCategoria(categoria);
            if (url.indexOf("solicitud/nueva") !== -1) {
              window.location.href = url;
            } else {
              try { sessionStorage.setItem("fx_chatbot_categoria", categoria); } catch (e) {}
              window.location.href = url;
            }
          });
        }
      } catch (err) {
        espera.remove();
        agregarMensaje(panel, "bot", "No pude procesar tu mensaje. Intenta de nuevo o elige una categoría abajo.");
        mostrarCategorias(panel, (categoria) => {
          const url = destinoPorCategoria(categoria);
          if (url.indexOf("solicitud/nueva") !== -1) window.location.href = url;
          else { try { sessionStorage.setItem("fx_chatbot_categoria", categoria); } catch (e) {} window.location.href = url; }
        });
      }
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
