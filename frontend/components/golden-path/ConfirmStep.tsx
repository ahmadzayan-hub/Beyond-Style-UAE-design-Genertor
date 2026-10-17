"use client";

import IntegrityPanel, { IntegrityReport } from "./IntegrityPanel";
import type { Strings } from "./types";
import { Button, Card, Checkbox } from "@/components/ui";

/** Exact-text confirmation gate (the text shown is the normalized source
 * text the backend will lock — never an AI rewrite). */
export interface ConfirmStepProps {
  t: Strings;
  lang: "ar" | "en";
  integrity: IntegrityReport | null;
  normalizedText: string;
  confirmChecked: boolean; setConfirmChecked: (v: boolean) => void;
  busy: boolean;
  onConfirm: () => void;
  onBack: () => void;
}

export default function ConfirmStep({
  t, lang, integrity, normalizedText, confirmChecked, setConfirmChecked, busy, onConfirm, onBack,
}: ConfirmStepProps) {
  return (
    <section className="flex flex-col gap-5 animate-fade-up">
      <div>
        <h2 className="font-display text-2xl text-ink-900">{t.confirm_title}</h2>
        <p className="mt-1 text-sm text-ink-500">{t.confirm_hint}</p>
      </div>
      <div
        data-testid="confirm-text-display"
        dir="auto"
        className="surface-paper rounded-3xl border-2 border-gold-400 bg-white p-8 text-center font-display text-4xl text-ink-900 shadow-soft whitespace-pre-line sm:text-5xl"
      >
        {normalizedText}
      </div>
      {integrity && <IntegrityPanel t={t} lang={lang} report={integrity} />}
      <Card tone="gold" padding="sm">
        <Checkbox
          data-testid="confirm-checkbox"
          checked={confirmChecked}
          onChange={(e) => setConfirmChecked(e.target.checked)}
          label={t.confirm_exact}
        />
      </Card>
      <Button size="lg" block data-testid="confirm-continue" disabled={!confirmChecked || busy} loading={busy} onClick={onConfirm}>
        {t.continue}
      </Button>
      <Button variant="ghost" size="sm" onClick={onBack} className="self-center">
        {t.back}
      </Button>
    </section>
  );
}
