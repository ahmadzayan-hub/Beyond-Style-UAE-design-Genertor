import type { ReactNode } from "react";
import { cx } from "./cx";

/** Honest empty state: says what is missing and, when there is one, the
 *  real action that fills it. Never a placeholder that looks like data. */
export default function EmptyState({
  title, body, action, className, icon,
}: { title: ReactNode; body?: ReactNode; action?: ReactNode; className?: string; icon?: ReactNode }) {
  return (
    <div className={cx("flex flex-col items-center gap-2 rounded-2xl border border-dashed border-ink-200 bg-cream-50 px-6 py-10 text-center", className)}>
      {icon && <div className="text-2xl text-gold-500" aria-hidden>{icon}</div>}
      <p className="text-sm font-semibold text-ink-800">{title}</p>
      {body && <p className="max-w-sm text-xs text-ink-500">{body}</p>}
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}
