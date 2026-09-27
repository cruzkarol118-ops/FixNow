/* FixNow - selector de ubicación por mapa (perfiles de cliente y técnico).
   Lee/escribe los inputs ocultos #id_latitud y #id_longitud del formulario. */
document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("[data-mapa-ubicacion]").forEach((el) => {
    if (typeof L === "undefined") {
      el.innerHTML = '<div class="alert alert-warning mb-0">No se pudo cargar el mapa. Revisa tu conexión a internet y recarga la página.</div>';
      return;
    }
    const latInput = document.getElementById("id_latitud");
    const lngInput = document.getElementById("id_longitud");
    const txt = el.parentElement.querySelector("[data-coords-texto]");
    const BOGOTA = [4.6486, -74.0628];
    const tiene = el.dataset.lat !== "" && el.dataset.lng !== "" &&
      !Number.isNaN(parseFloat(el.dataset.lat));

    const mapa = L.map(el).setView(
      tiene ? [parseFloat(el.dataset.lat), parseFloat(el.dataset.lng)] : BOGOTA,
      tiene ? 15 : 12);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      // Igual que el mapa de técnicos: OSM bloquea las teselas si no se
      // envía Referer (ver "tile usage policy"). Sin esto sale "Access blocked".
      referrerPolicy: "strict-origin-when-cross-origin",
      attribution: "&copy; OpenStreetMap",
    }).addTo(mapa);

    let pin = null;
    const pintarTexto = (lat, lng) => {
      if (txt) txt.textContent = lat == null
        ? "Sin ubicación marcada: no aparecerás en búsquedas por cercanía."
        : `Ubicación marcada: ${lat.toFixed(5)}, ${lng.toFixed(5)}.`;
    };
    const marcar = (lat, lng) => {
      if (pin) pin.remove();
      pin = L.marker([lat, lng]).addTo(mapa);
      if (latInput) latInput.value = lat.toFixed(6);
      if (lngInput) lngInput.value = lng.toFixed(6);
      pintarTexto(lat, lng);
    };
    const limpiar = () => {
      if (pin) { pin.remove(); pin = null; }
      if (latInput) latInput.value = "";
      if (lngInput) lngInput.value = "";
      pintarTexto(null, null);
    };

    if (tiene) {
      marcar(parseFloat(el.dataset.lat), parseFloat(el.dataset.lng));
    } else {
      pintarTexto(null, null);
    }

    mapa.on("click", (e) => marcar(e.latlng.lat, e.latlng.lng));

    const btnGeo = el.parentElement.querySelector("[data-mi-ubicacion]");
    if (btnGeo) {
      btnGeo.addEventListener("click", () => {
        if (!navigator.geolocation) {
          if (window.fxToast) fxToast("Tu navegador no soporta geolocalización.");
          return;
        }
        btnGeo.disabled = true;
        navigator.geolocation.getCurrentPosition(
          (pos) => {
            btnGeo.disabled = false;
            const { latitude, longitude } = pos.coords;
            mapa.setView([latitude, longitude], 15);
            marcar(latitude, longitude);
          },
          () => {
            btnGeo.disabled = false;
            if (window.fxToast) fxToast("No se pudo obtener tu ubicación. Revisa el permiso del navegador.");
          },
          { enableHighAccuracy: true, timeout: 10000 },
        );
      });
    }

    const btnLimpiar = el.parentElement.querySelector("[data-quitar-ubicacion]");
    if (btnLimpiar) btnLimpiar.addEventListener("click", limpiar);
  });
});
