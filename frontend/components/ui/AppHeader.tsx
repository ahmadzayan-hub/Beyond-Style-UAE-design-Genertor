"use client";

import { cx } from "./cx";

export interface AppHeaderProps {
  lang: "ar" | "en";
  onToggleLang: () => void;
  /** Label for the customer's "my designs" link (already localized). */
  meLabel: string;
  stylesLabel: string;
  hasCustomer?: boolean;
  /** Active route for the nav highlight. */
  active?: "home" | "styles" | "me";
  className?: string;
}

/** Brand header shared by the customer screens. The wordmark is text, not
 *  an image, so it survives high-contrast modes; dir="ltr" keeps the
 *  English wordmark reading "BEYOND STYLE" inside the RTL page. Keeps the
 *  `me-link` and `lang-toggle` test ids the E2E suite depends on. */
export default function AppHeader({ lang, onToggleLang, meLabel, stylesLabel, hasCustomer, active = "home", className }: AppHeaderProps) {
  return (
    <header className={cx("sticky top-0 z-40 -mx-4 mb-5 border-b border-cream-300/80 bg-cream-100/90 px-4 backdrop-blur", className)}>
      <div className="mx-auto flex h-14 w-full max-w-5xl items-center justify-between gap-3">
        <a href="/" dir="ltr" className="flex items-baseline gap-2" aria-label="Beyond Style">
          <span className="font-display text-[22px] font-bold leading-none tracking-tight text-gold-600">BEYOND</span>
          <span className="font-display text-[22px] leading-none tracking-[0.18em] text-ink-900">STYLE</span>
        </a>
        <nav className="flex items-center gap-1.5 sm:gap-2" aria-label="main">
          <a
            href="/styles"
            className={cx(
              "hidden h-9 items-center rounded-full px-3 text-sm sm:inline-flex",
              active === "styles" ? "bg-ink-900 text-cream-50" : "text-ink-700 hover:bg-cream-200",
            )}
          >
            {stylesLabel}
          </a>
          <a
            href="/me"
            data-testid="me-link"
            className={cx(
              "inline-flex h-9 items-center rounded-full border px-3 text-sm transition-colors",
              hasCustomer || active === "me"
                ? "border-ink-900 bg-ink-900 text-cream-50"
                : "border-ink-200 bg-white text-ink-800 hover:border-gold-300",
            )}
          >
            {meLabel}
          </a>
          <button
            type="button"
            onClick={onToggleLang}
            data-testid="lang-toggle"
            className="inline-flex h-9 items-center rounded-full border border-gold-500 bg-white px-3 text-sm font-medium text-gold-700 hover:bg-gold-50"
          >
            {lang === "ar" ? "English" : "عربي"}
          </button>
        </nav>
      </div>
    </header>
  );
}
