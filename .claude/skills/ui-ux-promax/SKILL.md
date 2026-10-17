---
name: ui-ux-promax
description: Project UI/UX standard for Beyond Style — how every customer and staff screen is designed, built with the React design system in frontend/components/ui, and verified. Use when adding or changing any screen, component, colour, type, motion, or layout in frontend/.
---

# UI/UX ProMax — Beyond Style

This is a project-level skill. It is not a marketplace plugin; there is no
"UI-UX-ProMax" skill in the Claude plugin catalogue. The closest published
skills are Anthropic's `frontend-design` plugin and the `VectorLab UI/UX
Skills` plugin (anti-slop, motion, typography, viewports, ux-audit). Install
those for general guidance; follow THIS file for anything in this repo.

## 1. Non-negotiables (from CLAUDE.md, restated for UI work)

- Never fake a feature, state, or number. A control that has no backend
  behind it is rendered disabled with an honest label (see `make-it-disabled`).
- Exact Arabic text is deterministic. The UI never rewrites, "fixes", or
  reads text off an image. The customer types it; the backend normalises it;
  the screen shows the normalised string and asks for confirmation.
- AI/raster images are decoration or preview only. Every generated image
  carries a visible label and an entry in `frontend/public/brand/PROVENANCE.json`.
  Generated artwork must not contain readable letters.
- Private by default. No analytics, no third-party fonts or scripts
  (CSP: `font-src 'self'`), no external image CDNs.
- Every `data-testid` used by `e2e/*.py` is an API. Re-skin freely; never
  rename or hide one (Playwright clicks them at a 390 px viewport, so the
  element must stay visible on phones).

## 2. Design tokens (`frontend/tailwind.config.ts`)

| Token | Use |
|---|---|
| `gold.50–800` (`gold.500` = #B08D3E) | brand accent, primary chips, progress, focus ring |
| `ink.100–900` | text and hairline borders (never pure grey Tailwind `stone-*`) |
| `cream.50–300` | page background (`cream-100`), muted surfaces |
| `sand`, `navy` | secondary surfaces, info tone |
| `ok`, `warn`, `danger` | semantic only, never decorative |
| `font-sans` (Cairo), `font-display` (Amiri) | UI text / Arabic headlines and the customer's text |
| `shadow-soft`, `shadow-lift`, `shadow-gold` | resting card, hover, selected gold chip |
| `animate-fade-up` | step entry only; respects `prefers-reduced-motion` |

Rules: body is `bg-cream-100 text-ink-900`; cards are white with
`border-ink-100` and `shadow-soft`; radii are `xl`/`2xl`/`3xl` (no `rounded`
or `rounded-md`); the customer's text is always `font-display` on a
`surface-paper` panel; one gold primary per screen.

## 3. Primitives (`frontend/components/ui`)

`Button` (primary | gold | secondary | ghost | success | danger; sm/md/lg;
`block`, `loading`), `Chip` (`selected`, `locked`, `leading`, `trailing`),
`Card` (`title`, `subtitle`, `action`, `tone`, `padding`), `Field` +
`Input`/`TextArea`/`Select`/`Range`/`Checkbox`, `Badge`, `Alert`,
`Stepper`, `Skeleton`, `EmptyState`, `AppHeader`, `Hero`.

Every primitive spreads `...rest`, so `data-testid`, `aria-*` and `id`
pass straight through. Build screens from these; add a primitive only when
three screens need the same thing.

## 4. Layout and devices

- Mobile first at 360–390 px; `max-w-5xl` two-column from `md`.
- One thumb-reachable primary action per step (`ActionBar`, hidden on `md+`
  where the inline button is visible). The inline button is never hidden on
  phones (E2E).
- RTL by default (`<html lang="ar" dir="rtl">`); use logical properties
  (`ms-`, `me-`, `text-start`, `end-2`) — never `ml-`/`mr-`/`left-`/`right-`.
- Safe areas: `pb-safe` on fixed bars; `viewportFit: cover`.
- Installable: `public/manifest.webmanifest` + icons. Windows/Android/iOS
  get the app as a PWA (see docs/DEPLOYMENT.md § Installable app). Native
  store builds are a separate Capacitor step and are not claimed until built.

## 5. Motion

Only state changes animate: step entry (`animate-fade-up`), button press
(`active:scale-[0.99]`), hover shadow. No looping decoration, no parallax,
nothing over 300 ms. Everything is disabled under `prefers-reduced-motion`.

## 6. Accessibility checklist

- Visible focus (`:focus-visible` gold ring) on every interactive element.
- Chips carry `aria-pressed`; danger alerts carry `role="alert"`.
- Every slider prints its value (`Range` requires `valueLabel`).
- Decorative images: `alt=""` + `aria-hidden`; informative ones get real alt.
- Contrast: ink-900 on cream-100 and white on gold-500 both pass AA for
  body/large text respectively; do not put gold-500 text on cream.

## 7. Definition of done for a UI change

1. `npx tsc --noEmit` and `npm run lint` clean.
2. `npm run build` succeeds (CSP and fonts self-hosted).
3. `python e2e/golden_path_e2e.py` (and the other `e2e/*.py` the change
   touches) pass against a local backend.
4. Every test id present before the change is present after it
   (`git diff | grep data-testid`).
5. New imagery has a PROVENANCE entry and a visible label.
