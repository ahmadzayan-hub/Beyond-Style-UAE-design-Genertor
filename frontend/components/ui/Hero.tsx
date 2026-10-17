"use client";

import { cx } from "./cx";

export interface HeroProps {
  title: string;
  subtitle: string;
  /** Three short trust lines (exact text, manufacturing check, originality). */
  points: string[];
  /** AI-generated illustration label — printed on the image so nobody
   *  mistakes it for a manufactured piece. */
  imageLabel: string;
  className?: string;
}

/** Landing hero for the first Golden Path step. The photograph is a
 *  decorative, AI-generated brand illustration (see
 *  public/brand/PROVENANCE.json); it is masked with the brand gradient and
 *  labelled, and it is never a product promise. Collapses to a compact
 *  banner on phones so the text field stays above the fold. */
export default function Hero({ title, subtitle, points, imageLabel, className }: HeroProps) {
  return (
    <section
      className={cx(
        "surface-paper relative overflow-hidden rounded-3xl border border-cream-300 bg-cream-50 shadow-soft",
        className,
      )}
      data-testid="hero"
    >
      <div className="grid gap-0 md:grid-cols-[1.1fr_1fr]">
        <div className="flex flex-col justify-center gap-4 p-6 sm:p-8">
          <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-gold-600">Beyond Style · UAE</p>
          <h2 className="font-display text-3xl leading-tight text-ink-900 sm:text-4xl">{title}</h2>
          <p className="max-w-md text-sm text-ink-600 sm:text-base">{subtitle}</p>
          <ul className="mt-1 flex flex-col gap-1.5 text-xs text-ink-700 sm:text-sm">
            {points.map((p) => (
              <li key={p} className="flex items-start gap-2">
                <span aria-hidden className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-gold-500" />
                <span>{p}</span>
              </li>
            ))}
          </ul>
        </div>
        <div className="relative h-40 md:h-auto md:min-h-[260px]">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src="/brand/hero-name-necklace.jpg"
            alt=""
            aria-hidden
            loading="eager"
            decoding="async"
            className="absolute inset-0 h-full w-full object-cover"
          />
          <div className="absolute inset-0 bg-gradient-to-t from-cream-50 via-cream-50/20 to-transparent md:bg-gradient-to-r" />
          <span className="absolute bottom-2 end-2 rounded-full bg-ink-900/70 px-2 py-0.5 text-[10px] text-cream-50">
            {imageLabel}
          </span>
        </div>
      </div>
    </section>
  );
}
