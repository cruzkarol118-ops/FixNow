# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

- **Clientes:** personas en Bogotá que tienen un daño doméstico (plomería, electricidad, cerrajería o electrodomésticos) y necesitan resolverlo sin llamar a desconocidos ni pactar a ciegas.
- **Técnicos:** trabajadores independientes verificados que quieren recibir solicitudes de su especialidad y zona, controlar su disponibilidad y cobrar al terminar.
- **Administradores:** personal de FixNow que verifica técnicos, modera usuarios y reseñas, y consulta la operación.

## Product Purpose

FixNow conecta a un cliente con un técnico verificado cerca de su ubicación. El cliente describe el daño, elige por calificación, distancia y precio de referencia, y paga cuando el trabajo termina. El éxito es que la solicitud llegue al técnico correcto y se cierre sin sorpresas de precio ni de identidad.

## Positioning

La verificación previa de cada técnico por un administrador, combinada con búsqueda por cercanía y especialidad, y un precio que se acuerda y se paga al finalizar. Un marketplace genérico no puede copiar la verificación ni el flujo de orden de servicio sin cambiar su operación.

## Operating Context

- El cliente crea una solicitud abierta o dirigida a un técnico concreto.
- El técnico ve solicitudes de su especialidad o dirigidas a él, acepta o rechaza, y finaliza con monto y notas.
- El cliente acepta o rechaza el monto, paga dentro de la app y califica una sola vez.
- El administrador revisa certificaciones, suspende cuentas con motivo, modera reseñas y consulta reportes por rango de fechas.
- La app se usa en el celular, muchas veces de pie y con prisa; el escritorio se usa para administración y consulta.
- El pago es una simulación de demo: no existe pasarela real.

## Capabilities and Constraints

- Roles: cliente, técnico y administrador, con permisos y flujos separados.
- Búsqueda de técnicos por especialidad, cercanía y calificación, con vista de lista y mapa.
- Solicitudes con categoría, descripción, dirección, fotos, precio ofrecido, visibilidad y urgencia.
- Disponibilidad y zona de cobertura del técnico.
- Verificación de técnicos y documentos; suspensión y reactivación de cuentas.
- Reseñas con moderación y cálculo de promedio.
- Reportes de operación y comisión.
- Sugerencia de categoría por IA y registro de aciertos para reentrenamiento.
- Stack existente: Django, plantillas del servidor, Bootstrap 5 por CDN y Leaflet. No se agregan dependencias nuevas de frontend.
- Contratos que no se pueden romper: rutas, permisos, validaciones, lógica de negocio, clases `fx-*` y atributos `data-*` usados por JavaScript.

## Brand Commitments

- Nombre: FixNow. Voz directa, colombiana, sin superlativos ni promesas infladas.
- La paleta actual se conserva: tinta `#111B2E`, amarillo `#FFC629`, azul `#2454FF`, verde `#0B7F58`, rojo `#C9252F`, gris `#F4F5F7`.
- El amarillo es señalización, no superficie de marca.
- No se inventan cifras, testimonios, reseñas, alianzas, certificaciones ni garantías.
- Contenido sintético debe marcarse como demostración.

## Evidence on Hand

- Aplicación Django funcional con datos demo en `core/management/commands/seed_demo.py`.
- Dirección visual aprobada en `plan_rework_visual_fixnow.md` (2026-11-05): oficio editorial, manual de servicio + orden de trabajo.
- Fotografía documental de Pexels: `static/img/hero-tecnico.jpg` (cottonbro studio, photo 7220892) y `static/img/detalle-plomeria.jpg` (Anıl Karakaya, photo 6419128). Procedencia en `static/img/PROVENANCE.md`.
- No hay testimonios, métricas de usuarios, ingresos, cobertura ni logos de aliados verificados. No deben aparecer.

## Product Principles

1. **La orden manda.** Cada solicitud se presenta como una orden de servicio legible: número, estado, técnico, categoría, tiempo y monto.
2. **Verificación visible.** La condición de técnico verificado se muestra donde ayuda a decidir, no como sello decorativo.
3. **Precio sin sorpresas.** El monto se acuerda y se confirma antes de pagar; la interfaz nunca sugiere cobros que el backend no respalde.
4. **Hechos, no escenografía.** Solo se muestran datos que el producto tiene; lo sintético se marca.
5. **La tarea primero.** En la app, claridad y densidad útil por encima de expresión; la marca vive en el detalle preciso.

## Accessibility & Inclusion

- Objetivo AA de contraste en texto y controles.
- Foco visible en todos los controles, orden de tabulación lógico y `aria-label` en iconos.
- Formularios con label asociado, errores junto al campo y mensajes que explican la recuperación.
- Respeto a `prefers-reduced-motion`.
- Objetivos táctiles de 44px en la app móvil.