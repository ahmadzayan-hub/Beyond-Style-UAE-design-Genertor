import type { HTMLAttributes, ReactNode } from "react";
import { cx } from "./cx";

export type AlertTone = "info" | "success" | "warning" | "danger";

const TONE: Record<AlertTone, string> = {
  info: "border-navy/15 bg-navy/5 text-navy-700",
  success: "border-ok-600/20 bg-ok-50 text-ok-800",
  warning: "border-warn-600/25 bg-warn-50 text-warn-800",
  danger: "border-danger-600/25 bg-danger-50 text-danger-800",
};

const ICON: Record<AlertTone, string> = { info: "i", success: "✓", warning: "!", danger: "!" };

/** Inline message. Danger alerts carry role="alert" so screen readers
 *  announce them; others are polite. */
export default function Alert({
  tone = "info", title, action, className, children, ...rest
}: HTMLAttributes<HTMLDivElement> & { tone?: AlertTone; title?: ReactNode; action?: ReactNode }) {
  return (
    <div
      role={tone === "danger" ? "alert" : "status"}
      className={cx("flex items-start gap-3 rounded-xl border p-3 text-sm animate-fade-up", TONE[tone], className)}
      {...rest}
    >
      <span
        aria-hidden
        className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-white/70 text-[11px] font-bold"
      >
        {ICON[tone]}
      </span>
      <div className="min-w-0 flex-1">
        {title && <p className="font-semibold">{title}</p>}
        <div className={title ? "mt-0.5" : undefined}>{children}</div>
      </div>
      {action}
    </div>
  );
}
