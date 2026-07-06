# JETTY™ Waves Build Prompt

You are upgrading JETTY™, a private AI second brain for social purpose companies and Salt Lake City entrepreneurs. Preserve the working backend and app logic. Do not break `/api/chat`, `/api/remember`, `/api/graph`, `/app`, or the private notes vault.

## Goal

Use the generated Spiral Jetty sunset image as the public landing page hero, but animate the water and wave field so the page feels alive. The public page should feel inspired by the Earendil site structure: fixed cinematic canvas, minimal top navigation, dropdown menu, custom cursor, bottom footer/appearance toggle, and a quiet premium front page.

## Required separation

- `/` = public landing page. No private data. No API keys. No user vault content.
- `/app` = private Jetty second brain app. Voice chooser, model chooser, chat, graph, remember-that flow.
- `/api/*` = backend only. Keys stay server-side.

## Brand

Name: **Jetty™**. Always include the ™ mark in the primary wordmark.

Visual source:
- Spiral Jetty basalt rocks → dark surfaces and circular marks
- Great Salt Lake pink water → primary action and wave glow
- Wasatch alpenglow → premium CTA and opportunity color
- Salt flats → clean typography, white space, quiet confidence

## Non-negotiable UX demo

The highest leverage point is the first five minutes:

1. Visitor sees the sunset image with moving water.
2. Visitor opens `/app`.
3. Veronika chooses a voice and a model.
4. She says: “Remember that I’m targeting SLC operations roles with flexible remote work.”
5. Jetty saves it and creates a new star in the private graph.
6. She asks: “Turn this into a five-company job-search plan and a warm introduction message.”

This proves private memory, voice, and useful action without requiring technical explanation.

## Implementation rules

- Use canvas animation for wave shimmer over the generated image.
- Respect `prefers-reduced-motion`.
- Keep cursor effects `pointer-events:none` so dropdowns remain usable.
- Keep app/backend code separate from the landing page animation.
- No stub buttons. Every visible CTA must scroll to a section or open `/app`.
- No secrets in frontend code.


## v1.2 Interaction Upgrade

Apply the JETTY™ v1.2 landing interaction layer:

1. Keep the sunset hero image as the fixed canvas source.
2. Draw the hero image normally first.
3. Apply wave displacement only below the water mask line:
   - desktop: `waterTop = viewportHeight * 0.405`
   - mobile: `waterTop = viewportHeight * 0.455`
   - fade in over 12% of viewport height so the mountain horizon never warps.
4. Keep DOM navigation, headline, CTA, and assistant card outside the canvas, above it, so UI text never distorts.
5. Replace the old center navigation with the Earendil-inspired top-right hamburger/chevron menu:
   - button label: `Menu`
   - three-line hamburger icon
   - chevron rotates when open
   - links stack vertically and close on outside click, Escape, or link tap
   - desktop: small top-right stack
   - mobile: full-width glass panel below the header
6. Add the star cursor effect:
   - use `/assets/cursor-light.svg` and `/assets/cursor-dark.svg`
   - hover targets trigger star spin and sparse spark trail
   - nav links show a spinning star after the label on hover
   - disable custom cursor on touch/mobile
7. Respect `prefers-reduced-motion` by disabling wave displacement, spark trail, and animation loops where practical.

Design principle: the canvas should feel alive; the product UI should feel stable, legible, and premium.
