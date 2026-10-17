import type { HTMLAttributes } from "react";
import { cx } from "./cx";

export type BadgeTone = "neutral" | "ok" | "warn" | "danger" | "info" | "gold";

const TONE: Record<BadgeTone, string> = {
  neutral: "bg-cream-200 text-ink-700",
  ok: "bg-ok-50 text-ok-800",
  warn: "bg-warn-50 text-warn-800",
  danger: "bg-danger-50 text-danger-800",
  info: "bg-navy/10 text-navy-600",
  gold: "bg-gold-50 text-gold-700",
};

/** Status pill. Tone is semantic (ok / warn / danger), never decorative. */
export default function Badge({
  tone = "neutral", className, children, ...rest
}: HTMLAttributes<HTMLSpanElement> & { tone?: BadgeTone }) {
  return (
    <span
      className={cx("inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-[11px] font-semibold leading-none", TONE[tone], className)}
      {...rest}
    >
      {children}
    </span>
  );
}
