"use client";

/** Mobile-first sticky bottom action bar: one primary action per step so
 *  the Golden Path is thumb-reachable at 360 px. Hidden on md+ where the
 *  inline buttons are visible. Never renders a fake action: when the step
 *  has no primary action (proofs, generating) the bar is not shown. */
export default function ActionBar({
  label, onClick, disabled, testId,
}: { label: string; onClick: () => void; disabled?: boolean; testId: string }) {
  return (
    <div
      className="fixed inset-x-0 bottom-0 z-30 border-t border-stone-200 bg-white/95 p-3 backdrop-blur md:hidden"
      style={{ paddingBottom: "calc(0.75rem + env(safe-area-inset-bottom))" }}
      data-testid="action-bar"
    >
      <button
        data-testid={testId}
        disabled={disabled}
        onClick={onClick}
        className="w-full rounded-xl bg-brand-dark py-3 text-base font-semibold text-white disabled:opacity-40"
      >
        {label}
      </button>
    </div>
  );
}
