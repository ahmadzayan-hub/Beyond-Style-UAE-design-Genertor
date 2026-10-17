import { cx } from "./cx";

/** Loading placeholder that keeps layout stable. Always pair with a
 *  visually hidden status so assistive tech knows something is pending. */
export default function Skeleton({ className, label }: { className?: string; label?: string }) {
  return (
    <div className={cx("skeleton rounded-lg", className)} role="status" aria-live="polite">
      <span className="sr-only">{label ?? "loading"}</span>
    </div>
  );
}
