"use client";

import type { Strings } from "./types";

/** Exact-text confirmation gate (the text shown is the normalized source
 * text the backend will lock — never an AI rewrite). */
export interface ConfirmStepProps {
  t: Strings;
  normalizedText: string;
  confirmChecked: boolean; setConfirmChecked: (v: boolean) => void;
  busy: boolean;
  onConfirm: () => void;
  onBack: () => void;
}

export default function ConfirmStep({
  t, normalizedText, confirmChecked, setConfirmChecked, busy, onConfirm, onBack,
}: ConfirmStepProps) {
  return (
    <section className="flex flex-col gap-5">
      <h2 className="text-xl font-bold">{t.confirm_title}</h2>
      <div
        data-testid="confirm-text-display"
        dir="auto"
        className="rounded-xl border-2 border-brand-gold bg-white p-6 text-center text-4xl font-bold whitespace-pre-line"
      >
        {normalizedText}
      </div>
      <p className="text-sm text-stone-500">{t.confirm_hint}</p>
      <label className="flex items-center gap-3 text-sm font-medium">
        <input
          type="checkbox"
          data-testid="confirm-checkbox"
          checked={confirmChecked}
          onChange={(e) => setConfirmChecked(e.target.checked)}
          className="h-5 w-5 accent-brand-gold"
        />
        {t.confirm_exact}
      </label>
      <button
        data-testid="confirm-continue"
        disabled={!confirmChecked || busy}
        onClick={onConfirm}
        className="rounded-xl bg-brand-dark p-4 text-lg font-semibold text-white disabled:opacity-40"
      >
        {t.continue}
      </button>
      <button className="text-sm text-stone-400" onClick={onBack}>
        {t.back}
      </button>
    </section>
  );
}
