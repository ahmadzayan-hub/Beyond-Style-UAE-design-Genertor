"use client";

import { Button } from "@/components/ui";

/** Mobile-first sticky bottom action bar: one primary action per step so
 *  the Golden Path is thumb-reachable at 360 px. Hidden on md+ where the
 *  inline buttons are visible. Never renders a fake action: when the step
 *  has no primary action (proofs, generating) the bar is not shown. */
export default function ActionBar({
  label, onClick, disabled, testId,
}: { label: string; onClick: () => void; disabled?: boolean; testId: string }) {
  return (
    <div
      className="pb-safe fixed inset-x-0 bottom-0 z-30 border-t border-cream-300 bg-cream-50/95 p-3 backdrop-blur md:hidden"
      data-testid="action-bar"
    >
      <Button size="lg" block data-testid={testId} disabled={disabled} onClick={onClick}>
        {label}
      </Button>
    </div>
  );
}
