import type { HTMLAttributes, ReactNode } from "react";
import { cx } from "./cx";

export interface CardProps extends Omit<HTMLAttributes<HTMLDivElement>, "title"> {
  title?: ReactNode;
  subtitle?: ReactNode;
  /** Right-aligned (end) slot in the header: a badge, a toggle. */
  action?: ReactNode;
  tone?: "default" | "muted" | "success" | "warning" | "danger" | "gold";
  padding?: "none" | "sm" | "md" | "lg";
}

const TONE: Record<NonNullable<CardProps["tone"]>, string> = {
  default: "border-ink-100 bg-white",
  muted: "border-cream-300 bg-cream-50",
  success: "border-ok-600/20 bg-ok-50",
  warning: "border-warn-600/20 bg-warn-50",
  danger: "border-danger-600/20 bg-danger-50",
  gold: "border-gold-300 bg-gold-50",
};

const PAD: Record<NonNullable<CardProps["padding"]>, string> = {
  none: "",
  sm: "p-3",
  md: "p-4 sm:p-5",
  lg: "p-5 sm:p-7",
};

/** Surface for every panel. Keeps borders hairline and shadows soft so the
 *  proofs (the real content) stay the loudest thing on screen. */
export default function Card({
  title, subtitle, action, tone = "default", padding = "md", className, children, ...rest
}: CardProps) {
  return (
    <div className={cx("rounded-2xl border shadow-soft", TONE[tone], PAD[padding], className)} {...rest}>
      {(title || action) && (
        <div className="mb-3 flex items-start justify-between gap-3">
          <div>
            {title && <h3 className="text-sm font-bold text-ink-900">{title}</h3>}
            {subtitle && <p className="mt-0.5 text-xs text-ink-500">{subtitle}</p>}
          </div>
          {action}
        </div>
      )}
      {children}
    </div>
  );
}
