"use client";

import { cx } from "./cx";

export interface StepperProps {
  steps: { key: string; label: string }[];
  /** Index of the active step. */
  current: number;
  className?: string;
}

/** Golden Path progress. On phones only the active label is printed (the
 *  others are dots) so six steps fit in 360 px; from `sm` up every label
 *  shows. Purely informational — never a navigation control, because a
 *  step cannot be skipped. */
export default function Stepper({ steps, current, className }: StepperProps) {
  return (
    <ol
      className={cx("flex items-center gap-1.5 sm:gap-2", className)}
      aria-label="progress"
      data-testid="stepper"
    >
      {steps.map((s, i) => {
        const state = i < current ? "done" : i === current ? "active" : "todo";
        return (
          <li key={s.key} className="flex min-w-0 items-center gap-1.5 sm:gap-2" aria-current={state === "active" ? "step" : undefined}>
            <span
              className={cx(
                "flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-[11px] font-bold transition-colors",
                state === "done" && "bg-gold-500 text-white",
                state === "active" && "bg-ink-900 text-cream-50 ring-4 ring-gold-200",
                state === "todo" && "bg-cream-200 text-ink-400",
              )}
            >
              {state === "done" ? "✓" : i + 1}
            </span>
            <span
              className={cx(
                "truncate text-xs",
                state === "active" ? "font-semibold text-ink-900" : "hidden text-ink-500 sm:inline",
              )}
            >
              {s.label}
            </span>
            {i < steps.length - 1 && (
              <span aria-hidden className={cx("h-px w-3 sm:w-6", i < current ? "bg-gold-400" : "bg-ink-200")} />
            )}
          </li>
        );
      })}
    </ol>
  );
}
