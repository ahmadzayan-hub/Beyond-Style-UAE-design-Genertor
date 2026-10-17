import localFont from "next/font/local";

/**
 * Self-hosted brand type (both faces are SIL Open Font License 1.1; the
 * licence texts sit next to the binaries in ./fonts and in the backend's
 * font registry evidence). Nothing is fetched from a third party at build
 * or run time, which keeps the CSP at font-src 'self'.
 *
 *  - Cairo   — UI sans for Arabic + Latin chrome (variable weight).
 *  - Amiri   — calligraphic serif for display text, the wordmark and the
 *              large exact-text displays on the confirm / approve screens.
 */
export const cairo = localFont({
  src: [{ path: "./fonts/Cairo.ttf", weight: "200 900", style: "normal" }],
  variable: "--font-sans",
  display: "swap",
  preload: true,
});

export const amiri = localFont({
  src: [{ path: "./fonts/Amiri-Regular.ttf", weight: "400", style: "normal" }],
  variable: "--font-display",
  display: "swap",
  preload: true,
});
