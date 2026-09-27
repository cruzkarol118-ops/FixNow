/* Abre el modal de confirmación al pulsar "Elegir" en una tarjeta o en un popup del mapa (FN-4 / FN-20).
   Bloque H: confirmar navega a /cliente/tecnicos/?elegir=<id> (conservando
   ?solicitud= si la página filtra por una solicitud concreta), que dirige
   ESA solicitud al técnico (él acepta/rechaza). */
document.addEventListener("click", (e) => {
  const btn = e.target.closest("[data-elegir]");
  if (!btn) return;
  document.getElementById("elegirNombre").textContent = btn.dataset.nombre;
  const confirmar = document.getElementById("elegirConfirmar");
  if (confirmar) {
    const params = new URLSearchParams({ elegir: btn.dataset.id });
    const sol = new URLSearchParams(window.location.search).get("solicitud");
    if (sol) params.set("solicitud", sol);
    confirmar.href = `/cliente/tecnicos/?${params.toString()}`;
  }
  bootstrap.Modal.getOrCreateInstance(document.getElementById("modalElegir")).show();
});
