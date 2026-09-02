"use client";

import { Lang, STRINGS } from "@/lib/i18n";
import type { Strings } from "./types";

/** Customer approval: dimensioned agreement proof + exact text + bilingual
 * approval statement. Approval creates the immutable version lock. */
export interface ApproveStepProps {
  t: Strings;
  lang: Lang;
  agreementSvg: string | null;
  selected: { svg?: string };
  normalizedText: string;
  approveChecked: boolean; setApproveChecked: (v: boolean) => void;
  busy: boolean;
  onApprove: () => void;
  onBack: () => void;
}

export default function ApproveStep({
  t, lang, agreementSvg, selected, normalizedText, approveChecked, setApproveChecked,
  busy, onApprove, onBack,
}: ApproveStepProps) {
  return (
    <section className="flex flex-col gap-5">
      <h2 className="text-xl font-bold">{t.approve_title}</h2>
      <div
        className="proof-svg-large rounded-xl border border-stone-200 bg-white p-4"
        data-testid="agreement-proof"
      >
        {(agreementSvg ?? selected.svg) && (
          <div dangerouslySetInnerHTML={{ __html: agreementSvg ?? selected.svg ?? "" }} />
        )}
      </div>
      <p className="text-xs text-stone-500">{t.agreement_note}</p>
      <div
        data-testid="approve-text-display"
        dir="auto"
        className="rounded-xl border-2 border-brand-gold bg-white p-5 text-center text-3xl font-bold whitespace-pre-line"
      >
        {normalizedText}
      </div>
      <label className="flex items-center gap-3 rounded-lg bg-white p-4 text-sm font-medium">
        <input
          type="checkbox"
          data-testid="approve-checkbox"
          checked={approveChecked}
          onChange={(e) => setApproveChecked(e.target.checked)}
          className="h-5 w-5 accent-brand-gold"
        />
        <span>
          {t.approve_statement}
          <br />
          <span className="text-xs text-stone-400">
            {lang === "ar" ? STRINGS.en.approve_statement : STRINGS.ar.approve_statement}
          </span>
        </span>
      </label>
      <button
        data-testid="approve-button"
        disabled={!approveChecked || busy}
        onClick={onApprove}
        className="rounded-xl bg-brand-dark p-4 text-lg font-semibold text-white disabled:opacity-40"
      >
        {t.approve_btn}
      </button>
      <button className="text-sm text-stone-400" onClick={onBack}>
        {t.back}
      </button>
    </section>
  );
}
