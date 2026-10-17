"use client";

import type { ButtonHTMLAttributes, ReactNode } from "react";
import { cx } from "./cx";

export interface ChipProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  selected?: boolean;
  /** Locked = exists but cannot be chosen (e.g. a script whose licensed
   *  source is not installed). Rendered dashed, never as a dead button. */
  locked?: boolean;
  leading?: ReactNode;
  trailing?: ReactNode;
}

/** Selectable pill used for product, script, material and style choices.
 *  `aria-pressed` carries the selection for assistive tech. */
export default function Chip({ selected, locked, leading, trailing, className, children, ...rest }: ChipProps) {
  return (
    <button
      type="button"
      aria-pressed={selected || undefined}
      className={cx(
        "inline-flex h-10 items-center gap-1.5 rounded-full border px-4 text-sm font-medium transition-[background-color,border-color,color,box-shadow] duration-150 ease-out-soft",
        selected
          ? "border-gold-500 bg-gold-500 text-white shadow-gold"
          : locked
            ? "border-dashed border-ink-200 bg-cream-50 text-ink-400"
            : "border-ink-200 bg-white text-ink-800 hover:border-gold-300 hover:bg-gold-50",
        "disabled:cursor-not-allowed",
        className,
      )}
      {...rest}
    >
      {leading}
      <span className="truncate">{children}</span>
      {trailing}
    </button>
  );
}
