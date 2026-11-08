---
name: FixNow
description: Servicios técnicos a domicilio con técnicos verificados y pago al terminar.
colors:
  ink: "#111B2E"
  ink-2: "#1E2C47"
  yellow: "#FFC629"
  yellow-deep: "#E8AE00"
  yellow-soft: "#FFF3CC"
  blue: "#2454FF"
  blue-soft: "#E6ECFF"
  green: "#0B7F58"
  green-soft: "#DDF5EB"
  red: "#C9252F"
  red-soft: "#FDE4E6"
  bg: "#F4F5F7"
  card: "#FFFFFF"
  line: "#E3E6EB"
  line-strong: "#CBD1DA"
  muted: "#5F6B7D"
  warning-ink: "#6B4E00"
typography:
  display:
    fontFamily: "Archivo, system-ui, sans-serif"
    fontSize: "clamp(2.5rem, 5vw, 4rem)"
    fontWeight: 700
    lineHeight: 0.98
    letterSpacing: "-0.03em"
  headline:
    fontFamily: "Archivo, system-ui, sans-serif"
    fontSize: "2rem"
    fontWeight: 700
    lineHeight: 1.1
    letterSpacing: "-0.02em"
  title:
    fontFamily: "Archivo, system-ui, sans-serif"
    fontSize: "1.5rem"
    fontWeight: 600
    lineHeight: 1.2
    letterSpacing: "-0.02em"
  body:
    fontFamily: "Public Sans, system-ui, sans-serif"
    fontSize: "0.9375rem"
    fontWeight: 400
    lineHeight: 1.55
  label:
    fontFamily: "Public Sans, system-ui, sans-serif"
    fontSize: "0.8125rem"
    fontWeight: 500
    lineHeight: 1.4
  overline:
    fontFamily: "Public Sans, system-ui, sans-serif"
    fontSize: "0.6875rem"
    fontWeight: 600
    lineHeight: 1.4
    letterSpacing: "0.08em"
rounded:
  xl: "14px"
  lg: "12px"
  md: "10px"
  sm: "8px"
  pill: "999px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "12px"
  base: "16px"
  lg: "24px"
  xl: "32px"
  2xl: "48px"
  3xl: "64px"
components:
  button-primary:
    backgroundColor: "{colors.yellow}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    padding: "12px 20px"
  button-secondary:
    backgroundColor: "{colors.card}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    padding: "12px 20px"
  button-ink:
    backgroundColor: "{colors.ink}"
    textColor: "#FFFFFF"
    rounded: "{rounded.md}"
    padding: "12px 20px"
  card:
    backgroundColor: "{colors.card}"
    textColor: "{colors.ink}"
    rounded: "{rounded.lg}"
    padding: "20px 24px"
  input:
    backgroundColor: "{colors.card}"
    textColor: "{colors.ink}"
    rounded: "{rounded.sm}"
    padding: "12px 14px"
  badge:
    backgroundColor: "{colors.bg}"
    textColor: "{colors.ink}"
    rounded: "{rounded.sm}"
    padding: "4px 8px"
  service-order:
    backgroundColor: "{colors.card}"
    textColor: "{colors.ink}"
    rounded: "{rounded.lg}"
    padding: "16px 18px"
---

# Design System

## Overview

FixNow se presenta como una orden de servicio real, no como una landing de marketplace. El mundo visual sale del servicio técnico cotidiano: manuales de mantenimiento, comprobantes de trabajo, cinta de seguridad, cuadrícula de plano y marcas de verificación. El amarillo es señalización, no superficie. La jerarquía se construye con escala tipográfica y espacio, no con peso 800 en todo. Las pantallas de app priorizan densidad y claridad; la landing prioriza prueba y acción.

## Colors

La paleta se conserva de la marca original. La tinta es el color dominante de texto y superficies oscuras. El amarillo es un acento de señalización usado en CTA, subrayados activos, cifras y cintas. El azul es funcional para enlaces y foco. El verde y el rojo son exclusivos de estado. El gris es el fondo base.

- **Ink** `#111B2E`: texto principal, botón primario, superficies oscuras.
- **Yellow** `#FFC629`: señalización, CTA, subrayado activo, cifras, cinta.
- **Blue** `#2454FF`: enlaces, foco, información, marcador “tú” en el mapa.
- **Green** `#0B7F58`: disponible, éxito, pagado.
- **Red** `#C9252F`: urgente, error.
- **Neutros**: `#F4F5F7` fondo, `#FFFFFF` superficies, `#E3E6EB` hairlines, `#5F6B7D` texto secundario.

Reglas duras: el amarillo no cubre secciones completas ni se usa como texto sobre blanco. Sobre amarillo siempre va tinta. El texto muted nunca va sobre amarillo, azul o verde.

## Typography

- **Display:** Archivo, pesos 600 y 700. Grotesca técnica con personalidad industrial.
- **UI y cuerpo:** Public Sans, pesos 400, 500 y 600. Alternativa: Inter.
- **Números:** tabulares para precios, distancias, IDs y fechas.

Escala: display `clamp(2.5rem, 5vw, 4rem)` / 700; h1 2rem / 700; h2 1.5rem / 600; h3 1.125rem / 600; body 0.9375rem / 400; label 0.8125rem / 500; overline 0.6875rem / 600 uppercase con tracking 0.08em.

Máximo dos pesos por pantalla. El énfasis se logra con tamaño, contraste y espacio.

## Layout

- Contenedor máximo de 1200px, gutter de 24px.
- Header de 68px en desktop y 56px en mobile.
- Densidad: 24px entre bloques en la app; 64–96px entre secciones en la landing.
- Mobile: barra de navegación inferior fija, objetivos táctiles de 44px.
- Los mapas son sticky en desktop y ocupan toda la columna.

## Elevation & Depth

- Sombra de reposo: `0 1px 2px rgba(17, 27, 46, .04)`.
- Sombra de hover: `0 8px 24px rgba(17, 27, 46, .07)`.
- Las sombras siempre llevan offset y blur suave. Nada de halos de color de offset cero.
- En la app, la elevación es mínima; la jerarquía se construye con hairlines y espacio.

## Shapes

- Tarjetas: radio 12px, borde 1px.
- Inputs y botones: radio 8–10px.
- Chips, badges y avatares: 999px.
- Bordes decorativos de 2px prohibidos.
- La orden de servicio usa una variante con cinta y sello, no una card genérica.

## Components

- **Header:** blanco, hairline inferior, sin sombra en reposo. Logo con subrayado amarillo de 2px.
- **Botones:** altura 44px (sm 36px, lg 52px), radio 10px, peso 600. Primario amarillo con texto tinta; secundario blanco con hairline; oscuro tinta con texto blanco.
- **Cards:** blanco, hairline, radio 12px, padding 20–24px. Hover solo si es interactiva. Sin tarjetas anidadas.
- **Badges:** punto de 6px + texto 11–12px, 600, fondo suave, radio 6px.
- **Inputs:** 44px, radio 8px, borde 1px. Foco: borde tinta + ring azul suave.
- **Filtros:** segmentado con fondo gris, indicador blanco y hairline; chips con borde y activo en tinta.
- **Orden de servicio:** comprobante con número tabular, estado con punto, técnico, categoría, línea de tiempo y sello de verificado.
- **Estados vacíos:** icono lineal discreto, título 600, texto muted y una acción.

## Do's and Don'ts

**Do:**

- Usar la orden de servicio como firma visual.
- Mostrar la verificación donde ayuda a decidir.
- Marcar el contenido sintético como demostración.
- Respetar `prefers-reduced-motion`.
- Tematizar las superficies del navegador: selección, caret, scrollbars, foco, numerales tabulares.

**Don't:**

- No cubrir secciones completas con amarillo.
- No usar píldoras de 999px salvo chips, badges y avatares.
- No usar bordes decorativos de 2px.
- No usar texto muted sobre fondo de color.
- No anidar tarjetas.
- No poner una baldosa de icono redondeada encima de cada título.
- No usar gradientes, glass ni sombras duras como decoración.
- No inventar cifras, testimonios, reseñas, alianzas, certificaciones ni garantías.
- No usar emojis ni glifos Unicode como iconos.
- No usar un kicker o eyebrow encima de un título.